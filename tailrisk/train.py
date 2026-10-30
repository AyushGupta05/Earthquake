"""Train one arm with leave-sequence-out CV and save out-of-fold predictions.

Each arm trains one network for all three deadlines (shared weights, duration
one-hot) with a fixed schedule. Nothing on the held-out fold selects an epoch,
hyperparameter or decision rule. Output: <out>/<arm>/fold<k>.npz with the
held-out rows, decision summaries (common.DECISION_NAMES) and coarse PMFs.

  python tailrisk/train.py --arm cat_ce --head cat --loss nll
  python tailrisk/train.py --arm eq_nll --head eq --loss nll
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from common import (DECISION_NAMES, DURATIONS, PMF_CENTERS, WORK, GPUData, decisions,
                    load_meta, metric_table)
from models import MagnitudeModel, distance_bin


def label_weights(y_train, y, kind, sigma=0.2, power=0.5, clip=20.0):
    """Per-record loss weights from the TRAIN label histogram (LDS-style)."""
    if kind == 'none':
        return torch.ones_like(y)
    bins = torch.arange(0, 7.01, 0.1, device=y.device)
    hist = torch.histc(y_train, bins=len(bins), min=-0.05, max=7.05)
    if kind == 'lds':
        k = torch.arange(-15, 16, device=y.device, dtype=torch.float32) * 0.1
        kern = torch.exp(-0.5 * (k / sigma) ** 2)
        hist = F.conv1d(hist[None, None], (kern / kern.sum())[None, None], padding=15)[0, 0]
    dens = hist / hist.sum()
    w_bin = dens.clamp_min(1e-12) ** (-power)
    idx = torch.round(y_train * 10).long().clamp(0, len(bins) - 1)
    w_bin = w_bin / w_bin[idx].mean()            # mean weight 1 over TRAIN records
    w_bin = w_bin.clamp(max=clip)
    return w_bin[torch.round(y * 10).long().clamp(0, len(bins) - 1)]


def loss_fn(dist, y, w, kind):
    if kind == 'nll':
        return (w * -dist.log_prob_label(y)).sum() / w.sum()
    if kind == 'hubce':   # prior project's strongest recipe: emphasized Huber + 0.075 CE
        hub = F.huber_loss(dist.mean(), y, reduction='none', delta=0.5)
        emph = 1 + 5.0 * (y - 3.5).clamp_min(0)
        return (w * (emph * hub - 0.075 * dist.log_prob_label(y))).sum() / w.sum()
    raise ValueError(kind)


def train_fold(args, data, train_idx, test_idx, fold_name, out_dir, device, extra=None):
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    data.fit_static_norm(train_idx)
    n_static = data.static_raw.shape[1]
    model = MagnitudeModel(args.head, n_static, k=args.k, aux_dist=args.aux_dist, width_mult=args.width_mult, kappa_min=args.kappa_min,
                           beta_fixed=args.beta_fixed, train_cap=args.train_mag_cap, kappa_fixed=args.kappa_fixed,
                           cap_conditional=args.cap_latent == 'conditional').to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.wd)
    steps_per_epoch = math.ceil(len(train_idx) / args.batch)
    total = steps_per_epoch * args.epochs
    warm = min(1000, total // 20)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total))))
    y_train = data.mag[train_idx]
    w_all = label_weights(y_train, data.mag, args.weighting)
    hyp = torch.from_numpy(data.meta['hyp_km'][data.rows].astype(np.float32)).to(device)
    r_valid = torch.isfinite(hyp)
    r_bin = distance_bin(torch.nan_to_num(hyp, nan=50.0))   # distance: training label only
    # reported magnitude scale (0 = ML/Md, 1 = Mw): training label only, for 'eqtgr'
    scale_idx = torch.from_numpy(np.char.startswith(data.meta['mag_type'][data.rows].astype(str), 'Mw').astype(np.int64)).to(device)
    history = []
    t0 = time.time()
    gen = torch.Generator(device=device)
    gen.manual_seed(args.seed)
    for epoch in range(args.epochs):
        model.train()
        perm = train_idx[torch.randperm(len(train_idx), device=device, generator=gen)]
        running, nb = 0.0, 0
        for b in range(steps_per_epoch):
            idx = perm[b * args.batch:(b + 1) * args.batch]
            y, w = data.mag[idx], w_all[idx]
            static = data.static(idx)
            loss = 0.0
            with torch.autocast('cuda', dtype=torch.bfloat16):
                if args.amp_aug > 0:   # scale physical amplitude by 10^delta, shift label by delta
                    delta = (torch.rand(len(idx), device=device, generator=gen) * 2 - 1) * args.amp_aug
                    y_fit = (y + delta).clamp(0.0, 7.0)
                else:
                    delta, y_fit = None, y
                for d_i, d in enumerate(DURATIONS):
                    shape, A, inv = data.prefix(idx, d)
                    if delta is not None:
                        A = A + delta
                    dur = torch.full((len(idx),), d_i, device=device, dtype=torch.long)
                    dist, aux = model.forward_train(shape, A, inv, static, dur)
                    base_head = args.head[len('magnet_'):] if args.head.startswith('magnet_') else args.head
                    if base_head == 'eqtgr':   # joint likelihood over (reported scale, magnitude)
                        term = (w * -dist.log_prob_joint(y_fit, scale_idx[idx])).sum() / w.sum()
                    elif base_head in ('eqd', 'eqdgr', 'mixd', 'mixdgr'):   # joint likelihood p(r|s) p(m|r,x); marginal if r missing
                        lp = torch.where(r_valid[idx], dist.log_prob_joint(y_fit, r_bin[idx]),
                                         dist.log_prob_label(y_fit))
                        term = (w * -lp).sum() / w.sum()
                    else:
                        term = loss_fn(dist, y_fit, w, args.loss)
                    if aux is not None:
                        ce = F.cross_entropy(aux, r_bin[idx], reduction='none') * r_valid[idx]
                        term = term + (w * ce).sum() / w.sum()
                    loss = loss + term / len(DURATIONS)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            sched.step()
            running += float(loss)
            nb += 1
            if b % 200 == 0:
                print(f'{fold_name} ep{epoch} step{b}/{steps_per_epoch} loss {running / nb:.4f} '
                      f'{time.time() - t0:.0f}s', flush=True)
        history.append({'epoch': epoch, 'train_loss': running / nb, 'elapsed_s': time.time() - t0})
    torch.save(model.state_dict(), out_dir / f'{fold_name}_model.pt')
    # ---- predict held-out rows
    model.eval()
    D = len(DECISION_NAMES)
    dec = np.zeros((len(test_idx), 3, D), np.float32)
    pmf = np.zeros((len(test_idx), 3, len(PMF_CENTERS)), np.float16)
    with torch.no_grad():
        for s in range(0, len(test_idx), 4096):
            idx = test_idx[s:s + 4096]
            static = data.static(idx)
            for d_i, d in enumerate(DURATIONS):
                shape, A, inv = data.prefix(idx, d)
                dur = torch.full((len(idx),), d_i, device=device, dtype=torch.long)
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    h = model.trunk(shape, A, inv, static, dur)
                dist = model.head(h.float(), A)
                o, p = decisions(dist, data.mag[idx])
                dec[s:s + len(idx), d_i] = o.cpu().numpy()
                pmf[s:s + len(idx), d_i] = p.cpu().numpy().astype(np.float16)
    rows = data.rows[test_idx.cpu().numpy()]
    np.savez(out_dir / f'{fold_name}.npz', rows=rows, dec=dec, pmf=pmf, **(extra or {}))
    y = data.meta['mag'][rows]
    ev = data.meta['event'][rows]
    summary = {}
    for d_i, d in enumerate(DURATIONS):
        m = metric_table(dec[:, d_i, 0], y, ev)
        summary[f'{d}s'] = {k: m[k] for k in ('MAE', 'MedAE', 'CVaR95', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE')}
    print(fold_name, json.dumps(summary), flush=True)
    return {'history': history, 'heldout_mean_action': summary}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True)
    ap.add_argument('--head', choices=['cat', 'mix', 'eq', 'eqgr', 'eqh', 'eqd', 'mixgr', 'eqdgr', 'eqtgr', 'magnet', 'mixd', 'mixdgr',
                                       'magnet_mix', 'magnet_mixgr', 'magnet_eqgr', 'magnet_eqdgr'], required=True)
    ap.add_argument('--aux-dist', action='store_true', help='auxiliary distance classifier (training only)')
    ap.add_argument('--loss', choices=['nll', 'hubce'], default='nll')
    ap.add_argument('--weighting', choices=['none', 'invsqrt', 'lds'], default='none')
    ap.add_argument('--mode', choices=['cv', 'std'], default='cv')
    ap.add_argument('--folds', default='0,1,2,3,4')
    ap.add_argument('--epochs', type=int, default=6)
    ap.add_argument('--batch', type=int, default=1024)
    ap.add_argument('--lr', type=float, default=2e-3)
    ap.add_argument('--wd', type=float, default=1e-4)
    ap.add_argument('--k', type=int, default=6)
    ap.add_argument('--seed', type=int, default=20261018)
    ap.add_argument('--amp-aug', type=float, default=0.0,
                    help='amplitude-scaling augmentation half-width in log10 units (label shifted equally)')
    ap.add_argument('--width-mult', type=float, default=1.0, help='trunk width multiplier (capacity check)')
    ap.add_argument('--kappa-min', type=float, default=0.3, help='lower bound of the equivariant slope kappa(s)')
    ap.add_argument('--kappa-fixed', type=float, default=None,
                    help='fix the equivariant slope (1.0 reproduces the kappa=1 construction of Zhang, Zhang & Tian 2021)')
    ap.add_argument('--beta-fixed', type=float, default=None,
                    help='pin the GR tail slope of the prior factor (nats per magnitude unit, e.g. -2.29 for b = 1) instead of learning it')
    ap.add_argument('--no-static', action='store_true', help='no station metadata inputs (catalogue-agnostic model for transfer tests)')
    ap.add_argument('--train-mag-cap', type=float, default=None,
                    help='extrapolation test: train only on records with label < cap (a catalogue without large '
                         'events); GR heads truncate their prior factor at the cap during training only')
    ap.add_argument('--cap-latent', choices=('joint', 'conditional'), default='joint',
                    help='joint latent heads (eqdgr/eqsgr) under --train-mag-cap: truncate the whole joint over '
                         '(latent, magnitude) (original) or only the magnitude conditional, with the latent '
                         'marginal from the untruncated joint (models.joint_log_prob)')
    ap.add_argument('--hold-stations', type=float, default=0.0,
                    help='fraction of stations withheld from training in every fold (held-station test)')
    ap.add_argument('--max-train', type=int, default=0, help='smoke test: subsample training rows')
    ap.add_argument('--out', default=str(WORK / 'arms'))
    args = ap.parse_args()
    device = torch.device('cuda')
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    out_dir = Path(args.out) / args.arm
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = load_meta()
    data = GPUData(device, meta, no_static=args.no_static)
    fold = torch.from_numpy(meta['fold'].astype(np.int64)).to(device)
    split = torch.from_numpy(meta['split'].astype(np.int64)).to(device)
    record = {'args': vars(args), 'folds': {}}
    if args.mode == 'cv':
        plan = [(f'fold{f}', torch.nonzero(fold != f)[:, 0], torch.nonzero(fold == f)[:, 0])
                for f in map(int, args.folds.split(','))]
    else:
        plan = [('std', torch.nonzero(split == 0)[:, 0], torch.nonzero(split > 0)[:, 0])]
    held_row = None
    if args.hold_stations > 0:
        # a fixed random subset of stations never enters training; their held-fold records
        # are evaluated separately (held event AND held station)
        station = meta['station']
        held_sta = np.random.default_rng(0).random(int(station.max()) + 1) < args.hold_stations
        held_row = torch.from_numpy(held_sta[station]).to(device)
        record['held_stations'] = int(held_sta.sum())
    if args.train_mag_cap is not None and args.amp_aug > 0 and args.head not in ('mix', 'cat', 'eq', 'magnet', 'mixd', 'eqd', 'eqh'):
        raise SystemExit('amplitude augmentation creates labels above the cap, which a truncated prior factor forbids')
    for name, tr, te in plan:
        if held_row is not None:
            tr = tr[~held_row[tr]]
        if args.train_mag_cap is not None:
            tr = tr[data.mag[tr] < args.train_mag_cap - 1e-6]
        record.setdefault('train_records', {})[name] = {'n': int(len(tr)), 'max_label': float(data.mag[tr].max())}
        if args.max_train:
            g = torch.Generator(device=device).manual_seed(0)
            tr = tr[torch.randperm(len(tr), device=device, generator=g)[:args.max_train]]
            te = te[torch.randperm(len(te), device=device, generator=g)[:args.max_train // 4]]
        extra = {'held_station': held_row[te].cpu().numpy()} if held_row is not None else None
        record['folds'][name] = train_fold(args, data, tr, te, name, out_dir, device, extra)
        (out_dir / 'record.json').write_text(json.dumps(record, indent=1))


if __name__ == '__main__':
    main()

"""Zero-shot cross-catalogue transfer: models trained on one catalogue predict another.

For each fold k of the destination catalogue, the source arm's fold-k model (trained on 80% of
the source catalogue, never on the destination) predicts the destination's fold-k records. Two
outputs per source arm, written as ordinary arm directories of the destination so that
geofon_eval.py / evaluate.py can score them with the destination's folds and cluster bootstrap:

  <out>            zero-shot posterior
  <out>_ls         label-shift adapted: p(m|x) * pi_dst(m) / pi_src(m), with pi the smoothed
                   training-label histograms (source: its training folds; destination: folds != k),
                   the same correction for every head (Saerens et al. 2002). Only the
                   destination's magnitude histogram is used, never its waveforms.

The source arm must be trained with --no-static (station metadata differ between catalogues).

  TAILWORK_DIR=<src> python tailrisk/transfer_eval.py --arm eqgr_ns --dst /mnt/.../chile --out eqgr_ns_from_instance
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from common import DECISION_NAMES, DURATIONS, PMF_CENTERS, WORK, GPUData, cap_keep, decisions, load_meta
from models import Binned, MagnitudeModel, Mixture, log_interval

GRID = torch.round(torch.arange(-1.0, 8.5 + 1e-6, 0.1) * 10) / 10      # the GR heads' 0.1 grid


def hist_logprior(y, sigma=0.25, floor=1e-5):
    c = GRID.numpy().astype(np.float64)
    idx = np.round((y - c[0]) * 10).astype(int).clip(0, len(c) - 1)
    h = np.bincount(idx, minlength=len(c)).astype(np.float64)
    hs = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sigma) ** 2) @ h
    hs /= hs.sum()
    return torch.tensor(np.log(np.maximum(hs, floor)), dtype=torch.float32)


def binned_logp(dist, device):
    g = GRID.to(device)
    if isinstance(dist, Binned):
        idx = torch.round((g - float(dist.centers[0])) * 10).long()
        ok = (idx >= 0) & (idx < dist.logp.shape[1])
        out = torch.full((dist.logp.shape[0], len(g)), -1e4, device=device)
        out[:, ok] = dist.logp[:, idx[ok]]
    elif isinstance(dist, Mixture):
        lw = dist.logit_w.log_softmax(-1)
        cols = [torch.logsumexp(lw + log_interval(dist.mu, dist.sigma, torch.full((dist.mu.shape[0],), float(c) - 0.05, device=device),
                                                  torch.full((dist.mu.shape[0],), float(c) + 0.05, device=device)), -1) for c in g]
        out = torch.stack(cols, 1)
    else:
        raise SystemExit(f'unsupported distribution {type(dist)}')
    return out - torch.logsumexp(out, 1, keepdim=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True, help='source arm (trained with --no-static) under $TAILWORK_DIR/arms')
    ap.add_argument('--dst', required=True, help='destination catalogue cache directory')
    ap.add_argument('--out', required=True, help='name of the destination arm directory to write')
    args = ap.parse_args()
    device = torch.device('cuda')
    src_dir = WORK / 'arms' / args.arm
    targs = json.loads((src_dir / 'record.json').read_text())['args']
    if not targs.get('no_static'):
        raise SystemExit('source arm must be trained with --no-static')
    src_meta = load_meta()
    src_fold = src_meta['fold'].astype(int)
    dst = Path(args.dst)
    dst_meta = np.load(dst / 'meta.npz', allow_pickle=True)
    dst_meta = {k: dst_meta[k] for k in dst_meta.files}
    data = GPUData(device, dst_meta, no_static=True, work=dst)
    data.fit_static_norm(torch.arange(len(data.mag), device=device))
    dst_fold = dst_meta['fold'].astype(int)
    out_dirs = {name: dst / 'arms' / name for name in (args.out, args.out + '_ls')}
    for d in out_dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    for k in sorted(np.unique(dst_fold)):
        avail = sorted(int(q.stem[4]) for q in src_dir.glob('fold?_model.pt'))
        f_src = k if k in avail else avail[0]
        model = MagnitudeModel(targs['head'], 1, k=targs.get('k', 6), width_mult=targs.get('width_mult', 1.0),
                               kappa_min=targs.get('kappa_min', 0.3), beta_fixed=targs.get('beta_fixed'), kappa_fixed=targs.get('kappa_fixed')).to(device)
        model.load_state_dict(torch.load(src_dir / f'fold{f_src}_model.pt', map_location=device))
        model.eval()
        y_src = src_meta['mag'][src_fold != f_src]
        if targs.get('train_mag_cap') is not None:
            y_src = y_src[cap_keep(y_src, targs['train_mag_cap'], targs.get('cap_filter', 'label'))]
        shift = (hist_logprior(dst_meta['mag'][dst_fold != k]) - hist_logprior(y_src)).to(device)
        te = torch.nonzero(torch.from_numpy(dst_fold == k).to(device))[:, 0]
        res = {name: (np.zeros((len(te), 3, len(DECISION_NAMES)), np.float32), np.zeros((len(te), 3, len(PMF_CENTERS)), np.float16)) for name in out_dirs}
        with torch.no_grad():
            for s in range(0, len(te), 4096):
                idx = te[s:s + 4096]
                static = data.static(idx)
                for d_i, d in enumerate(DURATIONS):
                    shape, A, inv = data.prefix(idx, d)
                    dur = torch.full((len(idx),), d_i, device=device, dtype=torch.long)
                    with torch.autocast('cuda', dtype=torch.bfloat16):
                        h = model.trunk(shape, A, inv, static, dur)
                    lp = binned_logp(model.head(h.float(), A), device)
                    for name, logp in ((args.out, lp), (args.out + '_ls', lp + shift[None])):
                        dist = Binned(logp.log_softmax(-1), GRID.to(device))
                        o, p = decisions(dist, data.mag[idx])
                        res[name][0][s:s + len(idx), d_i] = o.cpu().numpy()
                        res[name][1][s:s + len(idx), d_i] = p.cpu().numpy().astype(np.float16)
        rows = te.cpu().numpy()
        for name, (dec, pmf) in res.items():
            np.savez(out_dirs[name] / f'fold{k}.npz', rows=rows, dec=dec, pmf=pmf)
        print(f'{args.arm} -> {dst.name} fold{k}: {len(rows)} records (source model fold{f_src})', flush=True)
    for name, d in out_dirs.items():
        (d / 'record.json').write_text(json.dumps({'transfer_from': str(src_dir), 'label_shift': name.endswith('_ls'), 'args': targs}, indent=1))


if __name__ == '__main__':
    main()

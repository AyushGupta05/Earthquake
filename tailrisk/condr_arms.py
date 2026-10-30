"""Distance-informed inference with a trained distance-marginalized head (no retraining).

`eqdgr` models the joint p(r, m | x) over a log-distance bin r (a training label) and magnitude,
and marginalizes r at inference because a single station does not know its distance in the
first seconds. When a distance estimate r_hat is available (a network location after a few
stations, or the catalogue as an oracle), the same model gives

    p(m | x, r_hat) ∝ Σ_r p(r, m | x) · N(r_hat; r, σ²),

which for σ = 0 is the conditional p(m | r, x) of the true bin. This is the like-for-like
comparison with the classical inverse law fitted with catalogue distance (`linear_arms.py`
invR), and σ > 0 shows how much of the gain survives location error (σ in log10 km; .1 ≈ 26%).

Re-runs inference with the saved fold checkpoints (train.py's fold plan, cap and static
normalization) and writes <WORK>/arms/<arm>_condR<tag>/fold<k>.npz in train.py's format.
Records without a catalogue distance keep the marginal. With --logpmf, the conditioned
log-posteriors are also written in export_logpmf.py's format to <WORK>/logpmf/<arm>_condR<tag>/
(for multi-station fusion), with the fold's learned prior factor.

  TAILWORK_DIR=... python condr_arms.py --arm eqdgr_nll --sigmas 0,0.1,0.2 [--logpmf]
"""
import argparse
import json

import numpy as np
import torch

from common import DECISION_NAMES, DURATIONS, PMF_CENTERS, WORK, GPUData, cap_keep, decisions, load_meta
from export_logpmf import binned_logpmf
from models import R_CENTERS, Binned, JointBinned, MagnitudeModel


def tag(sigma):
    return '' if sigma == 0 else f'_s{int(round(sigma * 100)):02d}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True)
    ap.add_argument('--sigmas', default='0,0.1,0.2')
    ap.add_argument('--logpmf', action='store_true', help='also write full-precision log-posteriors for fusion')
    args = ap.parse_args()
    sigmas = [float(s) for s in args.sigmas.split(',')]
    device = torch.device('cuda')
    arm_dir = WORK / 'arms' / args.arm
    rec = json.loads((arm_dir / 'record.json').read_text())
    targs = rec['args']
    meta = load_meta()
    data = GPUData(device, meta, no_static=targs.get('no_static', False))
    fold = torch.from_numpy(meta['fold'].astype(np.int64)).to(device)
    hyp = torch.from_numpy(meta['hyp_km'][data.rows].astype(np.float32)).to(device)
    r_valid = torch.isfinite(hyp)
    log_r = torch.log10(torch.nan_to_num(hyp, nan=50.0).clamp_min(1.0))
    rc = R_CENTERS.to(device)
    outs = {}
    for s in sigmas:
        d = WORK / 'arms' / f'{args.arm}_condR{tag(s)}'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'record.json').write_text(json.dumps({'args': {**targs, 'arm': d.name, 'cond_sigma': s, 'source_arm': args.arm,
                                                            'note': 'distance-informed inference; see condr_arms.py'},
                                                   'folds': {}}, indent=1))
        outs[s] = d
    folds = [int(p.stem[4]) for p in sorted(arm_dir.glob('fold?_model.pt'))]
    for f in folds:
        tr = torch.nonzero(fold != f)[:, 0]
        te = torch.nonzero(fold == f)[:, 0]
        if targs.get('train_mag_cap') is not None:
            tr = tr[cap_keep(data.mag[tr], targs['train_mag_cap'], targs.get('cap_filter', 'label'))]
        data.fit_static_norm(tr)
        model = MagnitudeModel(targs['head'], data.static_raw.shape[1], k=targs.get('k', 6),
                               aux_dist=targs.get('aux_dist', False), width_mult=targs.get('width_mult', 1.0),
                               kappa_min=targs.get('kappa_min', 0.3), beta_fixed=targs.get('beta_fixed'),
                               kappa_fixed=targs.get('kappa_fixed')).to(device)
        model.load_state_dict(torch.load(arm_dir / f'fold{f}_model.pt', map_location=device))
        model.eval()
        res = {s: (np.zeros((len(te), 3, len(DECISION_NAMES)), np.float32),
                   np.zeros((len(te), 3, len(PMF_CENTERS)), np.float16)) for s in sigmas}
        lpo = {s: np.zeros((len(te), 3, len(PMF_CENTERS)), np.float16) for s in sigmas} if args.logpmf else None
        with torch.no_grad():
            for b in range(0, len(te), 4096):
                idx = te[b:b + 4096]
                static = data.static(idx)
                for d_i, dd in enumerate(DURATIONS):
                    shape, A, inv = data.prefix(idx, dd)
                    dur = torch.full((len(idx),), d_i, device=device, dtype=torch.long)
                    with torch.autocast('cuda', dtype=torch.bfloat16):
                        h = model.trunk(shape, A, inv, static, dur)
                    dist = model.head(h.float(), A)
                    if not isinstance(dist, JointBinned):
                        raise SystemExit(f'{args.arm}: head has no joint (distance, magnitude) posterior')
                    for s in sigmas:
                        if s == 0:
                            lw = torch.full((len(idx), len(rc)), -1e4, device=device)
                            lw.scatter_(1, torch.round((log_r[idx] - float(rc[0])) * 10).long().clamp(0, len(rc) - 1)[:, None], 0.0)
                        else:
                            lw = -0.5 * ((rc[None, :] - log_r[idx, None]) / s) ** 2
                        lp = torch.logsumexp(dist.logjoint + lw[:, :, None], 1)
                        lp = lp - torch.logsumexp(lp, 1, keepdim=True)
                        lp = torch.where(r_valid[idx, None], lp, dist.logp)
                        o, p = decisions(Binned(lp, dist.centers), data.mag[idx])
                        res[s][0][b:b + len(idx), d_i] = o.cpu().numpy()
                        res[s][1][b:b + len(idx), d_i] = p.cpu().numpy().astype(np.float16)
                        if lpo is not None:
                            lq = binned_logpmf(Binned(lp, dist.centers), PMF_CENTERS)
                            lq = lq - torch.logsumexp(lq, 1, keepdim=True)
                            lpo[s][b:b + len(idx), d_i] = lq.clamp_min(-6e4).cpu().numpy().astype(np.float16)
        rows = data.rows[te.cpu().numpy()]
        for s in sigmas:
            np.savez(outs[s] / f'fold{f}.npz', rows=rows, dec=res[s][0], pmf=res[s][1])
        if lpo is not None:
            with torch.no_grad():
                phi = model.head.prior.log_prior()
                c0 = float(model.head.prior.centers[0])
                ci = torch.round((torch.tensor(PMF_CENTERS, device=device) - c0) * 10).long()
                ok = (ci >= 0) & (ci < len(phi))
                phi_out = torch.full((len(PMF_CENTERS),), float('nan'), device=device)
                phi_out[ok] = phi[ci[ok]]
            for s in sigmas:
                d = WORK / 'logpmf' / f'{args.arm}_condR{tag(s)}'
                d.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(d / f'fold{f}.npz', rows=rows, logpmf=lpo[s], log_prior=phi_out.cpu().numpy().astype(np.float32))
        print(f'{args.arm} fold{f}: {len(te)} rows', flush=True)
        del model
        torch.cuda.empty_cache()


if __name__ == '__main__':
    main()

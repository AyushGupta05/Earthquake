"""Export full-precision out-of-fold log-posteriors (and each fold's learned prior) for an arm.

The fold npz files written by train.py hold float16 PMFs, whose far tails underflow to zero;
multi-station combination needs log-probabilities. This re-runs inference with the saved
fold checkpoints, reproducing train.py's fold plan and static normalization exactly, and
writes <WORK>/logpmf/<arm>/fold<k>.npz with
  rows      held-out record indices
  logpmf    (n, 3, len(PMF_CENTERS)) float16 log-probabilities on the saved coarse grid
  log_prior (len(PMF_CENTERS),) the fold's learned log prior factor phi on the same grid
            for GR-factorized heads (eqgr, mixgr, eqdgr, eqtgr); absent otherwise.

  TAILWORK_DIR=... python tailrisk/export_logpmf.py --arm eqgr_nll
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from common import DURATIONS, PMF_CENTERS, WORK, GPUData, load_meta
from models import Binned, MagnitudeModel, Mixture, log_interval


def binned_logpmf(dist, centers_out):
    """Log mass on the output 0.1 grid from a Binned posterior (its own 0.1 grid)."""
    c0 = float(dist.centers[0])
    idx = torch.round((torch.as_tensor(centers_out, device=dist.logp.device) - c0) * 10).long()
    ok = (idx >= 0) & (idx < dist.logp.shape[1])
    out = torch.full((dist.logp.shape[0], len(centers_out)), -1e4, device=dist.logp.device)
    out[:, ok] = dist.logp[:, idx[ok]]
    return out


def mixture_logpmf(dist, centers_out):
    """Stable log bin masses of a Gaussian mixture on the output 0.1 grid."""
    lw = dist.logit_w.log_softmax(-1)
    cols = []
    for c in centers_out:
        lo = torch.full((dist.mu.shape[0],), float(c) - 0.05, device=dist.mu.device)
        hi = lo + 0.1
        cols.append(torch.logsumexp(lw + log_interval(dist.mu, dist.sigma, lo, hi), -1))
    return torch.stack(cols, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arm', required=True)
    ap.add_argument('--folds', default=None, help='subset, e.g. 0,1 (default: all folds with checkpoints)')
    ap.add_argument('--out', default=str(WORK / 'logpmf'))
    args = ap.parse_args()
    device = torch.device('cuda')
    arm_dir = WORK / 'arms' / args.arm
    rec = json.loads((arm_dir / 'record.json').read_text())
    targs = rec['args']
    meta = load_meta()
    data = GPUData(device, meta)
    fold = torch.from_numpy(meta['fold'].astype(np.int64)).to(device)
    held_row = None
    if targs.get('hold_stations', 0) > 0:
        station = meta['station']
        held_sta = np.random.default_rng(0).random(int(station.max()) + 1) < targs['hold_stations']
        held_row = torch.from_numpy(held_sta[station]).to(device)
    out_dir = Path(args.out) / args.arm
    out_dir.mkdir(parents=True, exist_ok=True)
    folds = [int(f) for f in args.folds.split(',')] if args.folds else [int(p.stem[4]) for p in sorted(arm_dir.glob('fold?_model.pt'))]
    centers_out = torch.tensor(PMF_CENTERS, dtype=torch.float32, device=device)
    for f in folds:
        tr = torch.nonzero(fold != f)[:, 0]
        te = torch.nonzero(fold == f)[:, 0]
        if held_row is not None:
            tr = tr[~held_row[tr]]
        data.fit_static_norm(tr)
        n_static = data.static_raw.shape[1]
        model = MagnitudeModel(targs['head'], n_static, k=targs.get('k', 6), aux_dist=targs.get('aux_dist', False),
                               width_mult=targs.get('width_mult', 1.0), kappa_min=targs.get('kappa_min', 0.3)).to(device)
        model.load_state_dict(torch.load(arm_dir / f'fold{f}_model.pt', map_location=device))
        model.eval()
        logpmf = np.zeros((len(te), 3, len(PMF_CENTERS)), np.float16)
        with torch.no_grad():
            for s in range(0, len(te), 4096):
                idx = te[s:s + 4096]
                static = data.static(idx)
                for d_i, d in enumerate(DURATIONS):
                    shape, A, inv = data.prefix(idx, d)
                    dur = torch.full((len(idx),), d_i, device=device, dtype=torch.long)
                    with torch.autocast('cuda', dtype=torch.bfloat16):
                        h = model.trunk(shape, A, inv, static, dur)
                    dist = model.head(h.float(), A)
                    if isinstance(dist, Binned):
                        lp = binned_logpmf(dist, PMF_CENTERS)
                    elif isinstance(dist, Mixture):
                        lp = mixture_logpmf(dist, PMF_CENTERS)
                    else:
                        raise SystemExit(f'unsupported distribution {type(dist)}')
                    lp = lp - torch.logsumexp(lp, 1, keepdim=True)
                    logpmf[s:s + len(idx), d_i] = lp.clamp_min(-6e4).cpu().numpy().astype(np.float16)
        extra = {}
        head = model.head
        prior_mod = head if hasattr(head, 'log_prior') else getattr(head, 'prior', None)   # eqgr/mixgr: head; eqdgr/eqtgr: head.prior
        if prior_mod is not None and hasattr(prior_mod, 'log_prior'):
            with torch.no_grad():
                phi = prior_mod.log_prior()
                c0 = float(prior_mod.centers[0])
                idx = torch.round((centers_out - c0) * 10).long()
                ok = (idx >= 0) & (idx < len(phi))
                phi_out = torch.full((len(PMF_CENTERS),), float('nan'), device=device)
                phi_out[ok] = phi[idx[ok]]
                extra['log_prior'] = phi_out.cpu().numpy().astype(np.float32)
        rows = data.rows[te.cpu().numpy()]
        np.savez_compressed(out_dir / f'fold{f}.npz', rows=rows, logpmf=logpmf, **extra)
        print(f'{args.arm} fold{f}: {len(te)} rows, prior={"yes" if extra else "no"}', flush=True)
        del model
        torch.cuda.empty_cache()


if __name__ == '__main__':
    main()

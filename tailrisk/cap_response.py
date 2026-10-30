"""Amplitude response beyond a training cap (mechanism check for Proposition 3).

Held-out records whose label lies just below the training cap are amplified by 10^delta
(delta = 0 ... 2 decades of ground motion) and the posterior median is recorded. A model that
learned an amplitude law keeps rising past the cap; a model that saturates at the cap flattens.
Models are rebuilt from each arm's saved arguments with train.py's fold plan, cap filter and
static normalization (as in export_logpmf.py).

  TAILWORK_DIR=... python cap_response.py --arms mix_cap50,eqgr_cap50 --band 4.5,5.0 --out f.json
"""
import argparse
import json

import numpy as np
import torch

from common import DURATIONS, PMF_CENTERS, WORK, GPUData, load_meta
from export_logpmf import binned_logpmf, mixture_logpmf
from models import Binned, MagnitudeModel, Mixture


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', required=True)
    ap.add_argument('--band', default='4.5,5.0', help='label band of the records to amplify')
    ap.add_argument('--deltas', default='0,0.25,0.5,0.75,1,1.25,1.5,1.75,2')
    ap.add_argument('--per-fold', type=int, default=2000)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    lo, hi = map(float, args.band.split(','))
    deltas = [float(x) for x in args.deltas.split(',')]
    device = torch.device('cuda')
    meta = load_meta()
    data = GPUData(device, meta)
    fold = torch.from_numpy(meta['fold'].astype(np.int64)).to(device)
    mag_t = torch.from_numpy(np.asarray(meta['mag'], np.float32)).to(device)
    centers = torch.tensor(PMF_CENTERS, dtype=torch.float32, device=device)
    report = {'band': [lo, hi], 'deltas': deltas, 'arms': {}}
    for arm in args.arms.split(','):
        targs = json.loads((WORK / 'arms' / arm / 'record.json').read_text())['args']
        meds_all = []
        for f in range(5):
            ckpt = WORK / 'arms' / arm / f'fold{f}_model.pt'
            if not ckpt.exists():
                continue
            tr = torch.nonzero(fold != f)[:, 0]
            if targs.get('train_mag_cap') is not None:
                tr = tr[mag_t[tr] < targs['train_mag_cap'] - 1e-6]
            data.fit_static_norm(tr)
            model = MagnitudeModel(targs['head'], data.static_raw.shape[1], k=targs.get('k', 6),
                                   kappa_min=targs.get('kappa_min', 0.3), beta_fixed=targs.get('beta_fixed'),
                                   kappa_fixed=targs.get('kappa_fixed')).to(device)
            model.load_state_dict(torch.load(ckpt, map_location=device))
            model.eval()
            te = torch.nonzero((fold == f) & (mag_t >= lo) & (mag_t < hi))[:, 0]
            g = torch.Generator(device='cpu').manual_seed(f)
            te = te[torch.randperm(len(te), generator=g)[:args.per_fold].to(device)]
            meds = np.zeros((len(deltas), len(DURATIONS), len(te)), np.float32)
            with torch.no_grad():
                static = data.static(te)
                for d_i, d in enumerate(DURATIONS):
                    shape, A, inv = data.prefix(te, d)
                    dur = torch.full((len(te),), d_i, device=device, dtype=torch.long)
                    for k, delta in enumerate(deltas):
                        with torch.autocast('cuda', dtype=torch.bfloat16):
                            h = model.trunk(shape, A + delta, inv, static, dur)
                        dist = model.head(h.float(), A + delta)
                        lp = binned_logpmf(dist, PMF_CENTERS) if isinstance(dist, Binned) else mixture_logpmf(dist, PMF_CENTERS)
                        cdf = torch.cumsum(torch.softmax(lp, 1), 1)
                        meds[k, d_i] = centers[torch.argmax((cdf >= 0.5).int(), 1)].cpu().numpy()
            meds_all.append(meds)
            del model
            torch.cuda.empty_cache()
        if not meds_all:
            print(arm, 'no fold checkpoints; skipped', flush=True)
            continue
        meds = np.concatenate(meds_all, 2)
        res = {}
        for d_i, d in enumerate(DURATIONS):
            mean = meds[:, d_i].mean(1)
            res[f'{d}s'] = {'mean_median': mean.tolist(),
                            'q10': np.quantile(meds[:, d_i], .1, 1).tolist(),
                            'q90': np.quantile(meds[:, d_i], .9, 1).tolist(),
                            'slope_0_1': float(mean[deltas.index(1.0)] - mean[deltas.index(0.0)]),
                            'slope_1_2': float(mean[deltas.index(2.0)] - mean[deltas.index(1.0)])}
        report['arms'][arm] = {'n': int(meds.shape[2]), **res}
        print(arm, {k: (round(v['slope_0_1'], 3), round(v['slope_1_2'], 3), [round(x, 2) for x in v['mean_median']])
                    for k, v in res.items()}, flush=True)
    with open(args.out, 'w') as fh:
        json.dump(report, fh, indent=1)
    print('wrote', args.out)


if __name__ == '__main__':
    main()

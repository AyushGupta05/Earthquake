"""Mechanism diagnostics on held-out folds.

1. Amplitude response: multiply the physical ground motion of held-out records
   by 10^delta and record the change in the predicted median. A well-posed
   amplitude-magnitude relation moves ~1 unit per decade; a saturating model
   moves much less at large amplitudes.
2. Conditional calibration: mean true magnitude within bins of predicted
   median (E[M | prediction]); systematic E[M|pred] > pred in the upper range
   is excess shrinkage beyond Bayes.

  python tailrisk/diagnostics.py --arms cat_ce,eq_nll --fold 0
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from common import DURATIONS, GRID, WORK, GPUData, inverse_cdf, load_meta
from evaluate import load_arm, wmed_from_pmf
from models import MagnitudeModel

DELTAS = (-1.0, -0.5, 0.0, 0.5, 1.0)


def amplitude_response(arm, head, fold, data, meta, device, n_bulk=4000, seed=0):
    model = MagnitudeModel(head, data.static_raw.shape[1]).to(device)
    model.load_state_dict(torch.load(WORK / 'arms' / arm / f'fold{fold}_model.pt', map_location=device), strict=False)
    model.eval()
    fold_rows = np.flatnonzero(meta['fold'] == fold)
    train_rows = np.flatnonzero(meta['fold'] != fold)
    data.fit_static_norm(torch.from_numpy(train_rows).to(device))
    y = meta['mag'][fold_rows]
    rng = np.random.default_rng(seed)
    groups = {'M>=4': fold_rows[y >= 4], 'M<3 sample': rng.choice(fold_rows[y < 3], n_bulk, replace=False)}
    out = {}
    with torch.no_grad():
        for gname, rows in groups.items():
            idx = torch.from_numpy(rows).to(device)
            res = {}
            for d_i, d in enumerate(DURATIONS):
                meds = []
                for delta in DELTAS:
                    m_all = []
                    for s in range(0, len(idx), 4096):
                        b = idx[s:s + 4096]
                        shape, A, inv = data.prefix(b, d)
                        dur = torch.full((len(b),), d_i, device=device, dtype=torch.long)
                        dist = model(shape, A + delta, inv, data.static(b), dur)
                        F = dist.cdf(GRID.to(device)).float().clamp(0, 1)
                        m_all.append(inverse_cdf(F, GRID.to(device), torch.full((len(b), 1), .5, device=device))[:, 0])
                    meds.append(torch.cat(m_all).cpu().numpy())
                meds = np.stack(meds)                               # (deltas, n)
                res[f'{d}s'] = {f'{delta:+.1f}': float((meds[i] - meds[2]).mean()) for i, delta in enumerate(DELTAS)}
                res[f'{d}s']['slope_up'] = float(((meds[4] - meds[2]) / 1.0).mean())
                res[f'{d}s']['slope_down'] = float(((meds[2] - meds[0]) / 1.0).mean())
            out[gname] = res
    return out


def calibration(arm, meta, edges=np.arange(0, 6.01, 0.5)):
    dec, pmf, _ = load_arm(arm, len(meta['mag']), WORK / 'arms')
    y = meta['mag']
    res = {}
    for d_i, d in enumerate(DURATIONS):
        ok = np.isfinite(dec[:, d_i, 0])
        med = wmed_from_pmf(pmf[ok, d_i], np.array([1.0]))[:, 0]
        yy = y[ok]
        rows = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            sel = (med >= lo) & (med < hi)
            if sel.sum() >= 20:
                rows.append({'pred_lo': float(lo), 'n': int(sel.sum()), 'mean_pred': float(med[sel].mean()),
                             'mean_true': float(yy[sel].mean())})
        res[f'{d}s'] = rows
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', required=True, help='arm:head pairs, e.g. cat_ce:cat,eq_nll:eq')
    ap.add_argument('--folds', default='0,2')
    args = ap.parse_args()
    device = torch.device('cuda')
    meta = load_meta()
    data = GPUData(device, meta)
    report = {}
    for spec in args.arms.split(','):
        arm, head = spec.split(':')
        report[arm] = {'calibration': calibration(arm, meta), 'amplitude_response': {}}
        for f in map(int, args.folds.split(',')):
            report[arm]['amplitude_response'][f'fold{f}'] = amplitude_response(arm, head, f, data, meta, device)
        print(arm, json.dumps(report[arm]['amplitude_response'], indent=1), flush=True)
    out = WORK / 'arms' / f'diagnostics_{"_".join(s.split(":")[0] for s in args.arms.split(","))}.json'
    out.write_text(json.dumps(report, indent=1))
    print('wrote', out)


if __name__ == '__main__':
    main()

"""Binned mean prediction (median action) against the label for capped-training figures.

Usage: TAILWORK_DIR=... python cap_curve_data.py --arms a,b,c --out file.json
Records are binned by label in 0.25-unit bins; a bin is kept if it has >= 2 events.
"""
import argparse, glob, json, os
import numpy as np
from common import load_meta, PMF_CENTERS, WORK

ap = argparse.ArgumentParser()
ap.add_argument('--arms', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--lo', type=float, default=2.0)
ap.add_argument('--hi', type=float, default=8.5)
args = ap.parse_args()
m = load_meta(); mag = np.asarray(m['mag'], float); ev = np.asarray(m['event'])
edges = np.arange(args.lo, args.hi + 1e-9, 0.25)
out = {'edges': edges.tolist(), 'arms': {}}
for arm in args.arms.split(','):
    rows, meds = [], []
    for f in sorted(glob.glob(str(WORK / 'arms' / arm / 'fold*.npz'))):
        z = np.load(f); c = np.cumsum(z['pmf'].astype(np.float64), 2)
        rows.append(z['rows']); meds.append(PMF_CENTERS[np.argmax(c >= 0.5, 2)])
    r = np.concatenate(rows); med = np.concatenate(meds); y = mag[r]; e = ev[r]
    res = []
    for a, b in zip(edges[:-1], edges[1:]):
        s = (y >= a) & (y < b)
        ue = np.unique(e[s])
        if len(ue) < 2:
            res.append(None); continue
        res.append({'n_rec': int(s.sum()), 'n_ev': int(len(ue)), 'label_mean': float(y[s].mean()),
                    'pred_mean': med[s].mean(0).tolist(),
                    'pred_q25': np.quantile(med[s], .25, 0).tolist(), 'pred_q75': np.quantile(med[s], .75, 0).tolist()})
    out['arms'][arm] = res
json.dump(out, open(args.out, 'w'))
print('wrote', args.out)

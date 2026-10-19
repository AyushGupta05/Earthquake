"""Reliability of the tail probabilities P(M>=4) and P(M>=5) per arm (CPU, one arm at a time).

Bins predicted probability on a log scale (rare events), reports observed frequency,
counts, and the decomposition of the Brier score into reliability / resolution.

  python tailrisk/calibration_check.py --arms mix_nll,eqgr_nll
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import DECISION_NAMES, DURATIONS, WORK, load_meta
from evaluate import load_arm, KEEP

EDGES = np.array([0, 1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0001])


def reliability(p, y_bin):
    p = np.clip(p.astype(np.float64), 0, 1)
    idx = np.digitize(p, EDGES) - 1
    rows, rel, res = [], 0.0, 0.0
    base = y_bin.mean()
    for b in range(len(EDGES) - 1):
        sel = idx == b
        n = int(sel.sum())
        if n == 0:
            continue
        pm, om = float(p[sel].mean()), float(y_bin[sel].mean())
        rows.append({'p_lo': float(EDGES[b]), 'n': n, 'mean_pred': pm, 'obs_freq': om, 'n_events': int(y_bin[sel].sum())})
        rel += n * (pm - om) ** 2
        res += n * (om - base) ** 2
    N = len(p)
    return {'bins': rows, 'brier': float(np.mean((p - y_bin) ** 2)), 'reliability': rel / N,
            'resolution': res / N, 'uncertainty': float(base * (1 - base)), 'base_rate': float(base)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', required=True)
    ap.add_argument('--root', default=str(WORK / 'arms'))
    args = ap.parse_args()
    meta = load_meta()
    y = meta['mag']
    out = {}
    for arm in args.arms.split(','):
        dec, pmf, _ = load_arm(arm, len(y), Path(args.root))
        del pmf
        out[arm] = {}
        for d_i, d in enumerate(DURATIONS):
            for thr, col in ((4.0, 'p_ge4'), (5.0, 'p_ge5')):
                r = reliability(dec[:, d_i, KEEP.index(col)], (y >= thr - 1e-6).astype(np.float64))
                out[arm][f'{d}s_M>={thr:g}'] = r
                print(f'{arm:<22} {d} M>={thr:g}: Brier {r["brier"]:.6f} = reliability {r["reliability"]:.6f} '
                      f'- resolution {r["resolution"]:.6f} + uncertainty {r["uncertainty"]:.6f}')
        del dec
    for key in ('1s_M>=4', '5s_M>=4', '5s_M>=5'):
        print(f'\n{key}: predicted-probability bins (mean predicted -> observed frequency, n events / n records)')
        arms = list(out)
        print('   bin  ' + ''.join(f'{a:>34}' for a in arms))
        for b in range(len(EDGES) - 1):
            cells = []
            for a in arms:
                row = next((x for x in out[a][key]['bins'] if x['p_lo'] == EDGES[b]), None)
                cells.append('' if row is None else f'{row["mean_pred"]:.4f} -> {row["obs_freq"]:.4f} ({row["n_events"]}/{row["n"]})')
            if any(cells):
                print(f'  {EDGES[b]:<7g}' + ''.join(f'{c:>34}' for c in cells))
    Path(args.root, f'calibration_{"_".join(out)}.json').write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()

"""Seed x fold consistency of one arm against another (median action, no bootstrap).

Loads one arm at a time (low memory) and reports, for every seed pair, fold and
deadline, the difference in bulk MAE, M>=4 MAE, M>=4 event-MAE and M>=5 MAE,
then a sign test over all cells.

  python tailrisk/seed_consistency.py --pairs mix_nll:eqgr_nll,mix_nll_s2:eqgr_nll_s2,mix_nll_s3:eqgr_nll_s3
"""
import argparse
import json
from math import comb
from pathlib import Path

import numpy as np

from common import DURATIONS, WORK, load_meta, metric_table
from evaluate import load_arm, wmed_from_pmf

KEYS = ('MAE', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE')


def per_fold(arm, meta, root):
    dec, pmf, _ = load_arm(arm, len(meta['mag']), root)
    y, ev, fold = meta['mag'], meta['event'], meta['fold']
    out = {}
    for d_i, d in enumerate(DURATIONS):
        med = wmed_from_pmf(pmf[:, d_i], np.array([1.0]))[:, 0]
        out[f'{d}s'] = {'pooled': {k: metric_table(med, y, ev)[k] for k in KEYS}}
        for f in np.unique(fold):
            sel = fold == f
            out[f'{d}s'][f'fold{f}'] = {k: metric_table(med[sel], y[sel], ev[sel])[k] for k in KEYS}
    del dec, pmf
    return out


def sign_test(n_better, n):
    """Two-sided exact binomial p-value for n_better successes out of n at p = 1/2."""
    k = min(n_better, n - n_better)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', required=True, help='ref:arm,ref:arm,... (one per seed)')
    ap.add_argument('--root', default=str(WORK / 'arms'))
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    root = Path(args.root)
    meta = load_meta()
    pairs = [p.split(':') for p in args.pairs.split(',')]
    cache = {}
    for ref, arm in pairs:
        for a in (ref, arm):
            if a not in cache:
                cache[a] = per_fold(a, meta, root)
                print('loaded', a, flush=True)
    report = {'pairs': pairs, 'cells': [], 'summary': {}}
    for ref, arm in pairs:
        for d in (f'{x}s' for x in DURATIONS):
            for f in sorted(k for k in cache[ref][d] if k.startswith('fold')):
                report['cells'].append({'ref': ref, 'arm': arm, 'deadline': d, 'fold': f,
                                        **{k: cache[arm][d][f][k] - cache[ref][d][f][k] for k in KEYS}})
    for k in KEYS:
        deltas = np.array([c[k] for c in report['cells']])
        n_better = int((deltas < 0).sum())
        by_d = {}
        for d in (f'{x}s' for x in DURATIONS):
            dd = np.array([c[k] for c in report['cells'] if c['deadline'] == d])
            by_d[d] = {'n_better': int((dd < 0).sum()), 'n': int(len(dd)), 'median_delta': float(np.median(dd)),
                       'p_sign': sign_test(int((dd < 0).sum()), len(dd))}
        report['summary'][k] = {'n_better': n_better, 'n': int(len(deltas)), 'median_delta': float(np.median(deltas)),
                                'mean_delta': float(deltas.mean()), 'p_sign': sign_test(n_better, len(deltas)),
                                'by_deadline': by_d}
        print(f'{k:<16} arm better in {n_better}/{len(deltas)} seed x fold x deadline cells '
              f'(median Δ {np.median(deltas):+.4f}, sign-test p = {sign_test(n_better, len(deltas)):.2e}); '
              + '; '.join(f'{d}: {v["n_better"]}/{v["n"]}' for d, v in by_d.items()))
    print('\npooled per seed (arm − ref):')
    for ref, arm in pairs:
        for d in (f'{x}s' for x in DURATIONS):
            p = {k: cache[arm][d]['pooled'][k] - cache[ref][d]['pooled'][k] for k in KEYS}
            print(f'  {arm:<14} vs {ref:<12} {d}: ' + ' '.join(f'{k} {v:+.4f}' for k, v in p.items()))
    out = Path(args.out) if args.out else root / f'seedcons_{pairs[0][1]}_vs_{pairs[0][0]}.json'
    out.write_text(json.dumps(report, indent=1))
    print('wrote', out)


if __name__ == '__main__':
    main()

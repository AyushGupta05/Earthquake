"""Second-dataset evaluation (GEOFON): tails at M>=6 and M>=7, median and mean actions.

Reads fold npz files written by train.py under TAILWORK_DIR, pools out-of-fold
predictions, and reports per-arm metrics plus paired differences against a reference
with a cluster bootstrap over aftershock sequences.

  TAILWORK_DIR=.../geofon TAILWORK_MAXMAG=9.5 python tailrisk/geofon_eval.py --arms mix_nll,eqgr_nll --ref mix_nll
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import DURATIONS, WORK, load_meta
from evaluate import load_arm, wmed_from_pmf, COL

import os
THR = tuple(float(x) for x in os.environ.get('TAILWORK_THR', '6,6.5,7').split(','))   # tail thresholds


def metrics(pred, y, ev):
    err = np.abs(pred - y)
    out = {'MAE': float(err.mean()), 'MedAE': float(np.median(err)),
           'CVaR95': float(np.sort(err)[-max(1, int(np.ceil(.05 * len(err)))):].mean())}
    ev_err = np.bincount(ev, err) / np.maximum(np.bincount(ev), 1)
    ev_mag = np.zeros(ev.max() + 1); ev_mag[ev] = y
    present = np.bincount(ev) > 0
    for t in THR:
        sel = y >= t - 1e-6
        out[f'M>={t:g}_MAE'] = float(err[sel].mean()) if sel.any() else float('nan')
        out[f'M>={t:g}_bias'] = float((pred[sel] - y[sel]).mean()) if sel.any() else float('nan')
        e_sel = present & (ev_mag >= t - 1e-6)
        out[f'M>={t:g}_eventMAE'] = float(ev_err[e_sel].mean()) if e_sel.any() else float('nan')
        out[f'M>={t:g}_n_events'] = int(e_sel.sum())
    out[f'M<{THR[0]:g}_MAE'] = float(err[y < THR[0] - 1e-6].mean())
    return out


class Boot:
    def __init__(self, cluster, y, ev, reps=1000, seed=0):
        self.cl = np.unique(cluster, return_inverse=True)[1]
        self.nc = self.cl.max() + 1
        self.w = np.random.default_rng(seed).multinomial(self.nc, np.full(self.nc, 1 / self.nc), size=reps).astype(float)
        self.masks = {'MAE': np.ones(len(y), bool), f'M>={THR[0]:g}_MAE': y >= THR[0] - 1e-6, f'M>={THR[2]:g}_MAE': y >= THR[2] - 1e-6}
        ev_i = np.unique(ev, return_inverse=True)[1]
        first = np.unique(ev_i, return_index=True)[1]
        self.ev_i, self.cnt = ev_i, np.bincount(ev_i)
        self.first6 = first[y[first] >= THR[0] - 1e-6]

    def stats(self, err):
        out = {}
        with np.errstate(divide='ignore', invalid='ignore'):
            for k, m in self.masks.items():
                S = np.bincount(self.cl[m], err[m], self.nc); N = np.bincount(self.cl[m], minlength=self.nc).astype(float)
                out[k] = (self.w @ S) / (self.w @ N)
        ev_mean = np.bincount(self.ev_i, err) / self.cnt
        E = np.bincount(self.cl[self.first6], ev_mean[self.ev_i[self.first6]], self.nc)
        C = np.bincount(self.cl[self.first6], minlength=self.nc).astype(float)
        out[f'M>={THR[0]:g}_eventMAE'] = (self.w @ E) / (self.w @ C)
        return out

    def diff(self, ea, eb):
        a, b = self.stats(ea), self.stats(eb)
        out = {}
        for k in a:
            d = a[k] - b[k]
            d = d[np.isfinite(d)]                    # replicates with no record in a sparse tail are dropped
            out[k] = ({'mean': float(d.mean()), 'lo': float(np.quantile(d, .025)), 'hi': float(np.quantile(d, .975)),
                       'n_reps': int(len(d))} if len(d) >= 50 else None)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', required=True)
    ap.add_argument('--ref', default=None)
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--out', default=None)
    ap.add_argument('--station-subset', default=None, choices=['held', 'seen'],
                    help="restrict to records at stations withheld from (held) or present in (seen) "
                         "training, using the 'held_station' arrays saved by a --hold-stations arm")
    ap.add_argument('--station-arm', default=None, help='arm whose held_station arrays define the subset')
    args = ap.parse_args()
    meta = load_meta()
    y, ev, cl = meta['mag'], meta['event'], meta['cluster']
    arms = args.arms.split(',')
    root = WORK / 'arms'
    dec, pmf = {}, {}
    for a in arms:
        dec[a], pmf[a], files = load_arm(a, len(y), root)
        print(a, files, flush=True)
    have = np.all([np.isfinite(d[:, :, 0]).all(1) for d in dec.values()], 0)
    if args.station_subset:
        held = np.zeros(len(y), bool)
        src = root / (args.station_arm or arms[0].split('+')[0])
        files = sorted(src.glob('fold*.npz'))
        if not files:
            raise SystemExit(f'no fold files in {src}')
        for f in files:
            z = np.load(f)
            if 'held_station' not in z:
                raise SystemExit(f'{f} has no held_station array; use --station-arm with a --hold-stations arm')
            held[z['rows']] = z['held_station']
        have &= held if args.station_subset == 'held' else ~held
        print(f'station subset {args.station_subset}: {int(have.sum())} records', flush=True)
    y_, ev_, cl_ = y[have], ev[have], cl[have]
    print('records', int(have.sum()), 'events', len(np.unique(ev_)), f'M>={THR[0]:g} events', len(np.unique(ev_[y_ >= THR[0]])),
          f'M>={THR[2]:g} events', len(np.unique(ev_[y_ >= THR[2]])), flush=True)
    boot = Boot(cl_, y_, ev_, args.reps)
    rep = {'n_records': int(have.sum()), 'arms': {}, 'vs_ref': {}}
    acts = {}
    for d_i, d in enumerate(DURATIONS):
        for a in arms:
            med = wmed_from_pmf(pmf[a][have, d_i], np.array([1.0]))[:, 0]
            mean = dec[a][have, d_i, COL['mean']]
            acts[a, d] = (med, mean)
            bins = np.arange(THR[0] - 3.0, THR[2] + 2.01, 0.5)
            by_mag = [{'lo': float(b), 'n': int(((y_ >= b) & (y_ < b + .5)).sum()),
                       'bias_median': float((med - y_)[(y_ >= b) & (y_ < b + .5)].mean()) if ((y_ >= b) & (y_ < b + .5)).any() else None}
                      for b in bins]
            rep['arms'].setdefault(a, {})[f'{d}s'] = {'median_action': metrics(med, y_, ev_), 'mean_action': metrics(mean, y_, ev_),
                                                      'nll_bin': float(np.mean(dec[a][have, d_i, COL['nll_bin']])),
                                                      'crps': float(np.mean(dec[a][have, d_i, COL['crps']])), 'by_magnitude_median': by_mag}
        if args.ref:
            for a in arms:
                if a == args.ref:
                    continue
                rep['vs_ref'].setdefault(a, {})[f'{d}s'] = {
                    'median': boot.diff(np.abs(acts[a, d][0] - y_), np.abs(acts[args.ref, d][0] - y_)),
                    'mean': boot.diff(np.abs(acts[a, d][1] - y_), np.abs(acts[args.ref, d][1] - y_))}
    out = Path(args.out) if args.out else root / f'geofon_eval_{"_".join(arms)}.json'
    out.write_text(json.dumps(rep, indent=1))
    a, c = f'{THR[0]:g}', f'{THR[2]:g}'
    cols = ('MAE', 'MedAE', 'CVaR95', f'M>={a}_MAE', f'M>={a}_eventMAE', f'M>={c}_MAE', f'M>={c}_eventMAE', f'M>={a}_bias', f'M>={c}_bias', f'M<{a}_MAE')
    for d in DURATIONS:
        print(f'\n=== {d}s')
        print(f'{"arm":<22}' + ''.join(f'{c:>14}' for c in cols))
        for a in arms:
            for act in ('median_action', 'mean_action'):
                r = rep['arms'][a][f'{d}s'][act]
                print(f'{a + (" med" if act == "median_action" else " mean"):<22}' + ''.join(f'{r[c]:>14.4f}' for c in cols))
        for a in rep['vs_ref']:
            for act in ('median', 'mean'):
                c = rep['vs_ref'][a][f'{d}s'][act]
                print(f'  {a} - {args.ref} ({act}): ' + ' | '.join(
                    f'{k} ' + ('n/a' if v is None else f'{v["mean"]:+.4f} [{v["lo"]:+.4f},{v["hi"]:+.4f}]') for k, v in c.items()))


if __name__ == '__main__':
    main()

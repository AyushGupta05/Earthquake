"""Pool out-of-fold predictions and compare arms on the bulk/tail frontier.

All point decisions are recomputed from each arm's saved 0.1-bin PMF (uniform
within bins), so every arm uses an identical decision procedure:
  * mean action (saved continuous mean),
  * the tail-weighted-median family a_r = argmin E[w_r(M)|a-M|],
    w_r = r for M >= 4.0 and 1 below. r = 1 is the median; r > 1 is the
    user's 'multiply tail mass and take the median' rule; r < 1 trades tail
    for bulk. Sweeping r traces each arm's bulk/tail frontier.
Comparison at matched bulk MAE interpolates the frontier, so no arm can win by
trading bulk error for tail error. Uncertainty: paired bootstrap over
Gardner-Knopoff sequence clusters (whole sequences resampled together).

  python tailrisk/evaluate.py --arms cat_ce,eq_nll --ref cat_ce
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import DECISION_NAMES, DURATIONS, PMF_CENTERS, WORK, load_meta, metric_table

FRONTIER_R = np.unique(np.round(np.concatenate([np.geomspace(0.03, 100, 57), [1.0]]), 4))
J1 = int(np.argmin(np.abs(FRONTIER_R - 1)))      # index of the median action (r = 1)
KEY = ['MAE', 'MedAE', 'RMSE', 'CVaR95', 'CVaR99', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=4_bias',
       'M>=4.5_MAE', 'M>=5_MAE', 'M>=5_eventMAE', 'M>=5_bias', 'M<4_MAE', 'FP4_rate']
KEEP = ('mean', 'nll_bin', 'crps', 'p_ge4', 'p_ge5')       # decision columns kept in memory
COL = {n: i for i, n in enumerate(KEEP)}
EDGES = np.concatenate([PMF_CENTERS - 0.05, [PMF_CENTERS[-1] + 0.05]])
T_EDGE = int(np.argmin(np.abs(EDGES - 3.95)))


def load_arm(arm, n, root):
    """Load one arm, or an ensemble 'a+b+c' (mixture of the members' posteriors)."""
    if '+' in arm:
        names = arm.split('+')
        dec, pmf, files = load_arm(names[0], n, root)
        dec, acc = dec / len(names), pmf.astype(np.float32) / len(names)
        for a in names[1:]:                       # mixture of posteriors, accumulated in place
            d2, p2, _ = load_arm(a, n, root)
            dec += d2 / len(names)
            acc += p2.astype(np.float32) / len(names)
            del d2, p2
        return dec, acc.astype(np.float16), files
    keep = [DECISION_NAMES.index(c) for c in KEEP]
    dec = np.full((n, 3, len(KEEP)), np.nan, np.float32)
    pmf = np.zeros((n, 3, len(PMF_CENTERS)), np.float16)
    files = sorted((root / arm).glob('fold*.npz')) or sorted((root / arm).glob('std.npz'))
    for f in files:
        z = np.load(f)
        dec[z['rows']] = z['dec'][..., keep]
        pmf[z['rows']] = z['pmf']
    return dec, pmf, [f.stem for f in files]


def wmed_from_pmf(p, ratios, chunk=200000):
    """Tail-weighted medians (N, len(ratios)) from 0.1-bin PMFs (N, K)."""
    if len(p) > chunk:
        return np.concatenate([wmed_from_pmf(p[i:i + chunk], ratios, chunk) for i in range(0, len(p), chunk)])
    p = p.astype(np.float64)
    p /= np.maximum(p.sum(1, keepdims=True), 1e-12)
    F = np.concatenate([np.zeros((len(p), 1)), np.cumsum(p, 1)], 1)    # at EDGES
    FT = F[:, T_EDGE]
    out = np.empty((len(p), len(ratios)), np.float32)
    for j, r in enumerate(ratios):
        half = 0.5 * (FT + r * (1 - FT))
        q = np.where(half <= FT, half, FT + 0.5 * (1 - FT) - 0.5 * FT / r)
        q = np.clip(q, 1e-9, 1 - 1e-9)
        k = (F < q[:, None]).sum(1).clip(1, F.shape[1] - 1)          # F[k-1] < q <= F[k]
        f0 = F[np.arange(len(p)), k - 1]
        f1 = F[np.arange(len(p)), k]
        w = np.clip((q - f0) / np.maximum(f1 - f0, 1e-15), 0, 1)
        out[:, j] = EDGES[k - 1] + w * 0.1
    return out


class Boot:
    """Cluster bootstrap of record/event ratio metrics for many prediction sets."""

    def __init__(self, cluster, y, ev, reps, seed=0):
        self.cl = np.unique(cluster, return_inverse=True)[1]
        self.nc = self.cl.max() + 1
        rng = np.random.default_rng(seed)
        self.w = rng.multinomial(self.nc, np.full(self.nc, 1 / self.nc), size=reps).astype(np.float64)
        self.hi = y >= 4 - 1e-6
        self.hi5 = y >= 5 - 1e-6
        self.ev = np.unique(ev, return_inverse=True)[1]
        first = np.unique(self.ev, return_index=True)[1]
        self.first4 = first[y[first] >= 4 - 1e-6]
        self.cnt_ev = np.bincount(self.ev)
        self.N = np.bincount(self.cl, minlength=self.nc).astype(float)
        self.N4 = np.bincount(self.cl[self.hi], minlength=self.nc).astype(float)
        self.N5 = np.bincount(self.cl[self.hi5], minlength=self.nc).astype(float)
        self.C4 = np.bincount(self.cl[self.first4], minlength=self.nc).astype(float)
        self.lo35 = y < 3.5
        self.N35 = np.bincount(self.cl[self.lo35], minlength=self.nc).astype(float)

    def fp4(self, pred):
        """False-M4 rate (share of M<3.5 records predicted >= 3.95) per replicate."""
        s = np.bincount(self.cl[self.lo35], (pred[self.lo35] >= 3.95).astype(float), self.nc)
        return (self.w @ s) / (self.w @ self.N35)

    def sums(self, err):
        ev_mean = np.bincount(self.ev, err) / self.cnt_ev
        return np.stack([np.bincount(self.cl, err, self.nc),
                         np.bincount(self.cl[self.hi], err[self.hi], self.nc),
                         np.bincount(self.cl[self.hi5], err[self.hi5], self.nc),
                         np.bincount(self.cl[self.first4], ev_mean[self.ev[self.first4]], self.nc)])

    def metrics(self, S):
        """S: (..., 4, nc) cluster sums -> dict of (reps, ...) arrays."""
        w = self.w
        return {'MAE': np.einsum('rc,...c->r...', w, S[..., 0, :]) / (w @ self.N)[:, None],
                'M>=4_MAE': np.einsum('rc,...c->r...', w, S[..., 1, :]) / (w @ self.N4)[:, None],
                'M>=5_MAE': np.einsum('rc,...c->r...', w, S[..., 2, :]) / (w @ self.N5)[:, None],
                'M>=4_eventMAE': np.einsum('rc,...c->r...', w, S[..., 3, :]) / (w @ self.C4)[:, None]}


def interp_rows(x, y, x0):
    """Per-row linear interpolation of y(x) at x0 (rows: bootstrap replicates)."""
    out = np.empty(len(x))
    for i in range(len(x)):
        o = np.argsort(x[i])
        xs, ys = x[i][o], y[i][o]
        out[i] = np.interp(x0[i], xs, ys) if xs[0] <= x0[i] <= xs[-1] else np.nan
    return out


def constrained_best(bulk, tail, budget):
    """Per replicate: min tail over r subject to bulk <= budget (NaN if infeasible)."""
    masked = np.where(bulk <= budget[:, None] + 1e-12, tail, np.inf)
    best = masked.min(1)
    return np.where(np.isfinite(best), best, np.nan)


def ci(d):
    d = d[np.isfinite(d)]
    if not len(d):
        return None
    return {'mean': float(d.mean()), 'lo': float(np.quantile(d, .025)), 'hi': float(np.quantile(d, .975)),
            'p_arm_better': float((d < 0).mean()), 'n': int(len(d))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', required=True)
    ap.add_argument('--ref', default=None)
    ap.add_argument('--root', default=str(WORK / 'arms'))
    ap.add_argument('--out', default=None)
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--split', default='all', choices=['all', 'train', 'val', 'test'],
                    help='restrict to an original INSTANCE split (for --mode std arms)')
    ap.add_argument('--station-subset', default=None, choices=['held', 'seen'],
                    help="restrict to records at stations withheld from (held) or present in (seen) "
                         "training, using the 'held_station' arrays saved by a --hold-stations arm")
    ap.add_argument('--station-arm', default=None, help='arm whose held_station arrays define the subset')
    args = ap.parse_args()
    root = Path(args.root)
    meta = load_meta()
    y, ev, cluster, fold = meta['mag'], meta['event'], meta['cluster'], meta['fold']
    arms = args.arms.split(',')
    dec, pmf = {}, {}
    for a in arms:
        dec[a], pmf[a], files = load_arm(a, len(y), root)
        print(a, 'folds', files, flush=True)
    have = np.all([np.isfinite(d[:, :, 0]).all(1) for d in dec.values()], 0)
    if args.split != 'all':
        have &= meta['split'] == {'train': 0, 'val': 1, 'test': 2}[args.split]
    if args.station_subset:
        held = np.zeros(len(y), bool)
        src = root / (args.station_arm or arms[0].split('+')[0])
        n_files = 0
        for f in sorted(src.glob('fold*.npz')):
            z = np.load(f)
            if 'held_station' not in z:
                raise SystemExit(f'{f} has no held_station array; use --station-arm with a --hold-stations arm')
            held[z['rows']] = z['held_station']
            n_files += 1
        if not n_files:
            raise SystemExit(f'no fold files in {src}')
        have &= held if args.station_subset == 'held' else ~held
        print(f'station subset {args.station_subset}: {int(have.sum())} records', flush=True)
    print('records with predictions in every arm:', int(have.sum()), 'of', len(y), flush=True)
    y_, ev_, cl_, fo_ = y[have], ev[have], cluster[have], fold[have]
    boot = Boot(cl_, y_, ev_, args.reps)
    report = {'n_records': int(have.sum()), 'n_M4_events': int(len(np.unique(ev_[y_ >= 4]))),
              'frontier_r': FRONTIER_R.tolist(), 'arms': {}}
    report['vs_ref'] = {a: {} for a in arms if args.ref and a != args.ref}
    for a in arms:
        report['arms'][a] = {}
    for d_i, d in enumerate(DURATIONS):
        actions = {}
        for a in arms:
            wm = wmed_from_pmf(pmf[a][have, d_i], FRONTIER_R)
            mean = dec[a][have, d_i, COL['mean']]
            actions[a, d] = (mean, wm)
            front = []
            for j, r in enumerate(FRONTIER_R):
                m = metric_table(wm[:, j], y_, ev_)
                front.append({'r': float(r), **{k: m[k] for k in KEY}})
            med = front[int(np.argmin(np.abs(FRONTIER_R - 1)))]
            mm = metric_table(mean, y_, ev_)
            per_fold = {int(f): metric_table(wm[fo_ == f, J1], y_[fo_ == f], ev_[fo_ == f])
                        for f in np.unique(fo_)}
            bins = np.arange(0, 7.0, 0.5)
            by_mag = [{'lo': float(b), 'n': int(((y_ >= b) & (y_ < b + .5)).sum()),
                       'MAE_median': float(np.abs(wm[(y_ >= b) & (y_ < b + .5), J1] - y_[(y_ >= b) & (y_ < b + .5)]).mean())
                       if ((y_ >= b) & (y_ < b + .5)).any() else None,
                       'bias_median': float((wm[(y_ >= b) & (y_ < b + .5), J1] - y_[(y_ >= b) & (y_ < b + .5)]).mean())
                       if ((y_ >= b) & (y_ < b + .5)).any() else None} for b in bins]
            report['arms'][a][f'{d}s'] = {
                'mean_action': {k: mm[k] for k in KEY}, 'median_action': {k: med[k] for k in KEY},
                'frontier': front,
                'nll_bin': float(np.mean(dec[a][have, d_i, COL['nll_bin']])),
                'crps': float(np.mean(dec[a][have, d_i, COL['crps']])),
                # tail-probability quality: Brier score and event rate vs mean forecast
                'brier_M4': float(np.mean((dec[a][have, d_i, COL['p_ge4']] - (y_ >= 4 - 1e-6)) ** 2)),
                'brier_M5': float(np.mean((dec[a][have, d_i, COL['p_ge5']] - (y_ >= 5 - 1e-6)) ** 2)),
                'mean_p_ge4_on_M4': float(np.mean(dec[a][have, d_i, COL['p_ge4']][y_ >= 4 - 1e-6])),
                'mean_p_ge4_on_M_lt35': float(np.mean(dec[a][have, d_i, COL['p_ge4']][y_ < 3.5])),
                'per_fold_median': {f: {k: v[k] for k in ('MAE', 'M>=4_MAE', 'M>=4_eventMAE', 'CVaR95')}
                                    for f, v in per_fold.items()},
                'by_magnitude_median': by_mag}
        for a in (arms if args.ref else []):
            if a == args.ref:
                continue
            (mean_a, wm_a), (mean_b, wm_b) = actions[a, d], actions[args.ref, d]
            Sa = np.stack([boot.sums(np.abs(wm_a[:, j] - y_)) for j in range(len(FRONTIER_R))])
            Sb = np.stack([boot.sums(np.abs(wm_b[:, j] - y_)) for j in range(len(FRONTIER_R))])
            Ma, Mb = boot.metrics(Sa), boot.metrics(Sb)       # each (reps, nR)
            cmp = {}
            j1 = int(np.argmin(np.abs(FRONTIER_R - 1)))
            for name, pa, pb in [('mean', mean_a, mean_b), ('median', wm_a[:, j1], wm_b[:, j1])]:
                da = boot.metrics(boot.sums(np.abs(pa - y_))[None])
                db = boot.metrics(boot.sums(np.abs(pb - y_))[None])
                cmp[name] = {k: ci((da[k] - db[k])[:, 0]) for k in da}
                cmp[name]['FP4_rate'] = ci(boot.fp4(pa) - boot.fp4(pb))
            # bulk-constrained tail: best tail over each arm's r-family subject to
            # bulk MAE <= the reference median-action bulk MAE (x (1 + tol)), both arms
            # optimized the same way, per bootstrap replicate
            bulk_ref = Mb['MAE'][:, j1]
            for tol in (0.0, 0.002):
                budget = bulk_ref * (1 + tol)
                for key in ('M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE'):
                    ta = constrained_best(Ma['MAE'], Ma[key], budget)
                    tb = constrained_best(Mb['MAE'], Mb[key], budget)
                    cmp[f'bulkcap{tol:g}_{key}'] = ci(ta - tb)
            # tail-constrained bulk: least bulk MAE subject to M>=4 MAE <= ref median-action M>=4 MAE
            cap = Mb['M>=4_MAE'][:, j1]
            cmp['tailcap_MAE'] = ci(constrained_best(Ma['M>=4_MAE'], Ma['MAE'], cap)
                                    - constrained_best(Mb['M>=4_MAE'], Mb['MAE'], cap))
            report['vs_ref'][a][f'{d}s'] = cmp
        del actions
    if not args.ref:
        report.pop('vs_ref')
    out = Path(args.out) if args.out else root / f'eval_{"_".join(arms)}.json'
    out.write_text(json.dumps(report, indent=1))
    cols = ('MAE', 'MedAE', 'CVaR95', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE', 'M>=4_bias', 'FP4_rate')
    for d in DURATIONS:
        print(f'\n=== {d}s')
        print(f'{"arm":<26}' + ''.join(f'{k:>14}' for k in cols))
        for a in arms:
            for action in ('mean_action', 'median_action'):
                r = report['arms'][a][f'{d}s'][action]
                print(f'{a + (" mean" if action == "mean_action" else " med"):<26}' +
                      ''.join(f'{r[k]:>14.4f}' for k in cols))
        for a in arms:
            r = report['arms'][a][f'{d}s']
            print(f'  {a:<24} NLL {r["nll_bin"]:.4f} CRPS {r["crps"]:.4f} Brier(M>=4) {r["brier_M4"]:.5f} '
                  f'Brier(M>=5) {r["brier_M5"]:.6f} mean P(M>=4) on M>=4 {r["mean_p_ge4_on_M4"]:.3f} on M<3.5 {r["mean_p_ge4_on_M_lt35"]:.5f}')
        if args.ref:
            for a in report['vs_ref']:
                c = report['vs_ref'][a][f'{d}s']
                fmt = lambda v: 'n/a' if v is None else f'{v["mean"]:+.4f} [{v["lo"]:+.4f},{v["hi"]:+.4f}]'
                print(f'  {a} - {args.ref}: bulk-capped best tail: M>=4 {fmt(c["bulkcap0_M>=4_MAE"])} | '
                      f'event {fmt(c["bulkcap0_M>=4_eventMAE"])} | M>=5 {fmt(c["bulkcap0_M>=5_MAE"])} | '
                      f'(+0.2% bulk) M>=4 {fmt(c["bulkcap0.002_M>=4_MAE"])} | tail-capped bulk {fmt(c["tailcap_MAE"])}')
                print(f'     median action: ' + ' | '.join(f'{k} {fmt(v)}' for k, v in c['median'].items()))


if __name__ == '__main__':
    main()

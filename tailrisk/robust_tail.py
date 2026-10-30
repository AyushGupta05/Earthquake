"""Small-cluster-robust paired comparison of tail errors (arm − reference).

For every `arm:ref` pair (either side may be an ensemble 'a+b+c': the mixture of the members'
posteriors, as in evaluate.py's load_arm), every tail threshold t and every deadline (1/3/5 s),
for the median action (from the saved 0.1-bin PMF, uniform within bins: evaluate.wmed_from_pmf
with r = 1) and the mean action (the saved continuous mean), this reports the OBSERVED
full-sample values and difference arm − ref of

  bulk_MAE        MAE over all evaluated records
  M>=t_MAE        record-level tail MAE (label >= t)
  M>=t_eventMAE   event-level tail MAE (mean over tail events of the mean over their records)
  FP4_per_1e4     share of records with label < --fp-low (3.5) whose estimate is >= --fp-cut (3.95)

and four views of each difference's uncertainty:

  boot        paired cluster-bootstrap percentile interval as in evaluate.py (multinomial weights
              over all GK clusters of the evaluated records, --reps replicates, seed 0); also its mean
  jackknife   delete-one-cluster jackknife over the clusters that carry the metric (for a tail
              metric: the clusters containing tail events), interval delta ± t_{.975}(G−1)·se
  loco        range of delta over leave-one-cluster-out samples; delta without the largest cluster
              (most tail records, resp. events) and that cluster's share of the delta
  sign        clusters with delta < 0 / > 0 and the two-sided exact sign-test p over them

Subsets: --station-subset held|seen (records at stations withheld from / present in training,
from the 'held_station' arrays of --station-arm, as evaluate.py); --mask SPEC restricts every
metric, --tail-mask SPEC restricts only the tail records (both repeatable, combined with AND).
SPEC is [!]SOURCE:KEY[=VALUE], SOURCE 'meta' or an .npz row-aligned with meta.npz (relative paths
resolve against the cache directory); VALUE compares an integer array to a number or to a name in
KEY_names. Examples: --tail-mask subgroups.npz:mw_tail  --mask '!subgroups.npz:gain_suspect'
--mask subgroups.npz:region=Greece-Aegean  --tail-mask meta:label_ok.

Memory: one fold file per ensemble member at a time; per-record predictions are kept as float32;
bootstrap weights are drawn in chunks. ~1M records fit in < 2 GB.

  TAILWORK_DIR=/mnt/eew-research/runs/tailwork python tailrisk/robust_tail.py \\
      --pairs eqgr_nll:mix_nll,eqgr_nll+eqgr_nll_s2+eqgr_nll_s3:mix_nll+mix_nll_s2+mix_nll_s3 \\
      --thr 4,5 --out tailrisk/results/robust_instance.json        (also writes robust_instance.md)
"""
import argparse
import json
import math
import os
from pathlib import Path

import numpy as np

DEADLINES = ('1s', '3s', '5s')
MEAN_COL = 0                       # common.DECISION_NAMES[0] == 'mean'
LO_EDGE = -0.55                    # common.PMF_CENTERS start at -0.5 for every cache

try:
    from scipy import stats as _stats
except ImportError:                # pragma: no cover
    _stats = None


def t975(df):
    if _stats is not None:
        return float(_stats.t.ppf(0.975, df))
    return 1.96 + 2.4 / df          # rough fallback (exact to ~1% for df >= 5)


def sign_p(k, n):
    """Two-sided exact binomial p for k successes out of n at 1/2."""
    if n == 0:
        return None
    if _stats is not None:
        return float(_stats.binomtest(k, n, 0.5).pvalue)
    k = min(k, n - k)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


# ------------------------------------------------------------------ predictions
def median_from_pmf(p, chunk=100000):
    """Median of 0.1-bin PMFs (N, K), uniform within bins (= evaluate.wmed_from_pmf, r = 1)."""
    out = np.empty(len(p), np.float32)
    for s in range(0, len(p), chunk):
        q = p[s:s + chunk].astype(np.float64)
        q /= np.maximum(q.sum(1, keepdims=True), 1e-300)
        F = np.cumsum(q, 1)
        k = np.minimum((F < 0.5).sum(1), q.shape[1] - 1)
        r = np.arange(len(q))
        f0 = np.where(k > 0, F[r, np.maximum(k - 1, 0)], 0.0)
        frac = np.clip((0.5 - f0) / np.maximum(q[r, k], 1e-300), 0, 1)
        out[s:s + chunk] = LO_EDGE + 0.1 * k + 0.1 * frac
    return out


def fold_files(root, name):
    d = root / name
    files = sorted(d.glob('fold*.npz')) or sorted(d.glob('std.npz'))
    if not files:
        raise SystemExit(f'no fold files in {d}')
    return files


def side_available(spec, root, n):
    avail = None
    for name in spec.split('+'):
        a = np.zeros(n, bool)
        for f in fold_files(root, name):
            a[np.load(f)['rows']] = True
        avail = a if avail is None else avail & a
    return avail


def load_side(spec, root, n):
    """Median and mean actions (n, 3) float32 of one arm or posterior-mixture ensemble."""
    names = spec.split('+')
    med = np.full((n, 3), np.nan, np.float32)
    mean = np.full((n, 3), np.nan, np.float32)
    for f in fold_files(root, names[0]):
        z = np.load(f)
        rows = z['rows']
        acc = z['pmf'].astype(np.float32)
        mu = z['dec'][..., MEAN_COL].astype(np.float64)
        del z
        where = None
        for other in names[1:]:
            z2 = np.load(root / other / f.name)
            r2 = z2['rows']
            if np.array_equal(r2, rows):
                acc += z2['pmf']
                mu += z2['dec'][..., MEAN_COL]
            else:
                if where is None:
                    where = np.full(n, -1, np.int64)
                    where[rows] = np.arange(len(rows))
                pos = where[r2]
                if len(r2) != len(rows) or (pos < 0).any():
                    raise SystemExit(f'{other}/{f.name}: held-out rows differ from {names[0]}/{f.name}')
                acc[pos] += z2['pmf']
                mu[pos] += z2['dec'][..., MEAN_COL]
            del z2
        acc /= len(names)
        mu /= len(names)
        for d in range(3):
            med[rows, d] = median_from_pmf(acc[:, d])
        mean[rows] = mu
        del acc, mu
    return med, mean


# ------------------------------------------------------------------ subsets
def resolve_mask(spec, meta, work, n):
    neg = spec.startswith('!')
    s = spec[1:] if neg else spec
    src, _, key = s.partition(':')
    if not key:
        raise SystemExit(f'mask {spec!r}: expected SOURCE:KEY')
    key, _, val = key.partition('=')
    if src == 'meta':
        store = meta
    else:
        p = Path(src)
        if not p.is_absolute() and not p.exists():
            p = work / p
        store = np.load(p, allow_pickle=True)
    a = store[key]
    if len(a) != n:
        raise SystemExit(f'mask {spec!r}: {len(a)} rows, meta has {n}')
    if val:
        if val.lstrip('-').isdigit():
            m = a == int(val)
        elif key + '_names' in store.files:
            names = [str(x) for x in store[key + '_names']]
            if val not in names:
                raise SystemExit(f'mask {spec!r}: {val!r} not in {names}')
            m = a == names.index(val)
        else:
            m = a.astype(str) == val
    else:
        m = a.astype(bool)
    return ~m if neg else m


# ------------------------------------------------------------------ statistics
class Layout:
    """Cluster/event indexing of the evaluated records and the tail definitions."""

    def __init__(self, y, ev, cl, thr, tail_ok, fp_low):
        self.y = y
        self.cl_ids, self.cl = np.unique(cl, return_inverse=True)
        self.G = len(self.cl_ids)
        self.ev = np.unique(ev, return_inverse=True)[1]
        self.E = int(self.ev.max()) + 1
        self.cl_of_ev = np.zeros(self.E, np.int64)
        self.cl_of_ev[self.ev] = self.cl
        self.thr = thr
        self.tail = {t: (y >= t - 1e-6) & tail_ok for t in thr}
        self.low = y < fp_low
        self.N = np.bincount(self.cl, minlength=self.G).astype(np.float64)
        self.N_low = np.bincount(self.cl[self.low], minlength=self.G).astype(np.float64)
        self.N_t, self.C_t, self.ev_tail = {}, {}, {}
        for t, m in self.tail.items():
            self.N_t[t] = np.bincount(self.cl[m], minlength=self.G).astype(np.float64)
            cnt = np.bincount(self.ev[m], minlength=self.E)
            self.ev_tail[t] = (np.nonzero(cnt > 0)[0], cnt)
            self.C_t[t] = np.bincount(self.cl_of_ev[cnt > 0], minlength=self.G).astype(np.float64)

    def event_sums(self, x, t):
        """Cluster sums of event means of x over tail records, and per-event means."""
        m = self.tail[t]
        evs, cnt = self.ev_tail[t]
        s = np.bincount(self.ev[m], x[m], self.E)[evs] / cnt[evs]
        return np.bincount(self.cl_of_ev[evs], s, self.G), s

    def columns(self, err_a, err_b, fp_a, fp_b):
        """(name, cluster sums of a, of b, denominator vector, scale) for every metric."""
        out = [('bulk_MAE', np.bincount(self.cl, err_a, self.G), np.bincount(self.cl, err_b, self.G), self.N, 1.0)]
        for t in self.thr:
            m = self.tail[t]
            out.append((f'M>={t:g}_MAE', np.bincount(self.cl[m], err_a[m], self.G),
                        np.bincount(self.cl[m], err_b[m], self.G), self.N_t[t], 1.0))
            out.append((f'M>={t:g}_eventMAE', self.event_sums(err_a, t)[0], self.event_sums(err_b, t)[0],
                        self.C_t[t], 1.0))
        lo = self.low
        out.append(('FP4_per_1e4', np.bincount(self.cl[lo], fp_a[lo].astype(np.float64), self.G),
                    np.bincount(self.cl[lo], fp_b[lo].astype(np.float64), self.G), self.N_low, 1e4))
        return out


def cluster_views(Sa, Sb, N, ids, scale):
    """Observed values and jackknife / LOCO / sign views from per-cluster sums."""
    sel = N > 0
    Nt = N.sum()
    if Nt == 0:
        return {'n': 0}
    a, b = Sa.sum() / Nt, Sb.sum() / Nt
    D, Nn, idn = (Sa - Sb)[sel], N[sel], ids[sel]
    Dt = D.sum()
    obs = Dt / Nt
    res = {'n': float(Nt), 'ref': b * scale, 'arm': a * scale, 'delta': obs * scale, 'G': int(len(D))}
    G = len(D)
    if G >= 2:
        theta = (Dt - D) / (Nt - Nn)
        se = math.sqrt((G - 1) / G * float(((theta - theta.mean()) ** 2).sum()))
        q = t975(G - 1)
        big = int(np.argmax(Nn))
        res.update({'jackknife': [(obs - q * se) * scale, (obs + q * se) * scale], 'jackknife_se': se * scale,
                    'loco': [float(theta.min()) * scale, float(theta.max()) * scale],
                    'largest_cluster': int(idn[big]), 'largest_share_of_n': float(Nn[big] / Nt),
                    'without_largest': float(theta[big]) * scale,
                    'largest_share_of_delta': float(D[big] / Dt) if Dt != 0 else None})
    cd = D / Nn
    neg, pos = int((cd < -1e-12).sum()), int((cd > 1e-12).sum())
    res.update({'clusters_neg': neg, 'clusters_pos': pos, 'sign_p': sign_p(neg, neg + pos)})
    return res


def bootstrap(columns, G, reps, seed, budget=1.2e7):
    """Paired cluster bootstrap (evaluate.py weights) for many (diff, denominator) columns.

    columns: list of (key, D (G,), N (G,), scale). Returns {key: (lo, hi, mean, n_finite)}."""
    if not columns:
        return {}
    dens, den_idx = [], {}
    for _, _, N, _ in columns:
        if id(N) not in den_idx:
            den_idx[id(N)] = len(dens)
            dens.append(N)
    X = np.stack([c[1] for c in columns] + dens, 1)              # (G, M)
    nd = len(columns)
    jcol = np.array([nd + den_idx[id(c[2])] for c in columns])
    rng = np.random.default_rng(seed)
    p = np.full(G, 1.0 / G)
    chunk = max(1, int(budget / G))
    reps_out = np.empty((reps, nd))
    done = 0
    while done < reps:
        c = min(chunk, reps - done)
        W = rng.multinomial(G, p, size=c).astype(np.float64)
        with np.errstate(all='ignore'):          # some BLAS builds raise spurious FP flags in matmul
            WX = W @ X
            reps_out[done:done + c] = WX[:, :nd] / WX[:, jcol]
        done += c
    out = {}
    for j, (key, _, _, scale) in enumerate(columns):
        d = reps_out[:, j]
        d = d[np.isfinite(d)]
        out[key] = ((float(np.quantile(d, .025)) * scale, float(np.quantile(d, .975)) * scale,
                     float(d.mean()) * scale, int(len(d))) if len(d) >= 50 else None)
    return out


# ------------------------------------------------------------------ report
def fmt(x, nd=4):
    return 'n/a' if x is None else f'{x:+.{nd}f}'


def interval(v, nd=4):
    return 'n/a' if not v else f'[{v[0]:+.{nd}f}, {v[1]:+.{nd}f}]'


def markdown(rep):
    lines = [f'# Robust tail comparison — `{rep["cache"]}`', '',
             f'Records evaluated: {rep["n_records"]:,} ({rep["n_clusters"]:,} GK clusters). '
             f'Subset: {rep["subset"] or "all records"}. Bootstrap: {rep["reps"]} replicates, seed {rep["seed"]}. '
             f'Δ = arm − ref, observed on the full sample. Jackknife: delete-one-cluster over the clusters '
             f'carrying the metric, t(G−1). FP4 = share of records with label < {rep["fp_low"]:g} estimated '
             f'≥ {rep["fp_cut"]:g}, per 10⁴.', '']
    for t, v in rep['tail'].items():
        lines.append(f'* M≥{t}: {v["records"]:,} records, {v["events"]} events, {v["clusters"]} clusters; '
                     f'largest cluster {v["largest_cluster"]} holds {v["largest_share_of_records"]:.0%} of the '
                     f'tail records')
    for pair, body in rep['pairs'].items():
        arm, ref = pair.split(':')
        lines += ['', f'## `{arm}` − `{ref}`', '', '### Median action', '',
                  '| deadline | metric | ref | arm | Δ | bootstrap 95% | jackknife 95% (G) | LOCO range | '
                  'Δ w/o largest (its share of Δ) | clusters Δ<0 / Δ>0 | sign p |',
                  '|---|---|---|---|---|---|---|---|---|---|---|']
        for d in DEADLINES:
            for key, r in body['median'][d].items():
                nd = 2 if key.startswith('FP4') else 4
                if r.get('n', 0) == 0:
                    lines.append(f'| {d} | {key} | — | — | — | — | — | — | — | — | — |')
                    continue
                share = r.get('largest_share_of_delta')
                share = '' if share is None or abs(share) > 5 else f' ({share:.0%})'   # undefined as Δ -> 0
                sp = 'n/a' if r['sign_p'] is None else f'{r["sign_p"]:.3g}'
                lines.append(
                    f'| {d} | {key} | {r["ref"]:.{nd}f} | {r["arm"]:.{nd}f} | **{fmt(r["delta"], nd)}** | '
                    f'{interval(r.get("boot"), nd)} | {interval(r.get("jackknife"), nd)} ({r["G"]}) | '
                    f'{interval(r.get("loco"), nd)} | {fmt(r.get("without_largest"), nd)}{share} | '
                    f'{r["clusters_neg"]} / {r["clusters_pos"]} | {sp} |')
        lines += ['', '### Mean action', '',
                  '| deadline | metric | Δ | bootstrap 95% | jackknife 95% (G) | clusters Δ<0 / Δ>0 |',
                  '|---|---|---|---|---|---|']
        for d in DEADLINES:
            for key, r in body['mean'][d].items():
                nd = 2 if key.startswith('FP4') else 4
                if r.get('n', 0) == 0:
                    continue
                lines.append(f'| {d} | {key} | {fmt(r["delta"], nd)} | {interval(r.get("boot"), nd)} | '
                             f'{interval(r.get("jackknife"), nd)} ({r["G"]}) | {r["clusters_neg"]} / {r["clusters_pos"]} |')
    return '\n'.join(lines) + '\n'


def rounded(x):
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, dict):
        return {k: rounded(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rounded(v) for v in x]
    return x


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--pairs', required=True, help='arm:ref,arm:ref,... (each side may be a+b+c)')
    ap.add_argument('--thr', default='4,5', help='tail thresholds')
    ap.add_argument('--out', required=True, help='output JSON; the markdown table goes next to it (.md)')
    ap.add_argument('--root', default=None, help='arms directory (default $TAILWORK_DIR/arms)')
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--fp-low', type=float, default=3.5)
    ap.add_argument('--fp-cut', type=float, default=3.95)
    ap.add_argument('--station-subset', default=None, choices=['held', 'seen'])
    ap.add_argument('--station-arm', default=None, help="arm whose 'held_station' arrays define the subset")
    ap.add_argument('--mask', action='append', default=[], help='restrict every metric (repeatable)')
    ap.add_argument('--tail-mask', action='append', default=[], help='restrict tail records only (repeatable)')
    args = ap.parse_args()
    work = Path(os.environ.get('TAILWORK_DIR', '/mnt/eew-research/runs/tailwork'))
    root = Path(args.root) if args.root else work / 'arms'
    thr = [float(t) for t in args.thr.split(',')]
    pairs = [tuple(p.split(':')) for p in args.pairs.split(',')]
    meta = np.load(work / 'meta.npz', allow_pickle=True)
    y_all = meta['mag'].astype(np.float64)
    n = len(y_all)
    sides = list(dict.fromkeys(s for p in pairs for s in p))

    have = np.ones(n, bool)
    for s in sides:
        have &= side_available(s, root, n)
    subset = []
    if args.station_subset:
        src = root / (args.station_arm or pairs[0][1].split('+')[0])
        held = np.zeros(n, bool)
        for f in fold_files(root, src.name):
            z = np.load(f)
            if 'held_station' not in z.files:
                raise SystemExit(f'{f} has no held_station array; pass --station-arm with a --hold-stations arm')
            held[z['rows']] = z['held_station']
        have &= held if args.station_subset == 'held' else ~held
        subset.append(f'{args.station_subset} stations ({src.name})')
    for spec in args.mask:
        have &= resolve_mask(spec, meta, work, n)
        subset.append(f'mask {spec}')
    tail_ok = np.ones(n, bool)
    for spec in args.tail_mask:
        tail_ok &= resolve_mask(spec, meta, work, n)
        subset.append(f'tail mask {spec}')
    print(f'records evaluated: {int(have.sum())} of {n}', flush=True)

    y = y_all[have]
    lay = Layout(y, meta['event'][have], meta['cluster'][have], thr, tail_ok[have], args.fp_low)
    rep = {'cache': str(work), 'root': str(root), 'n_records': int(have.sum()), 'n_clusters': lay.G,
           'subset': '; '.join(subset), 'reps': args.reps, 'seed': args.seed, 'fp_low': args.fp_low,
           'fp_cut': args.fp_cut, 'thresholds': thr, 'tail': {}, 'pairs': {}}
    for t in thr:
        evs, _ = lay.ev_tail[t]
        big = int(np.argmax(lay.N_t[t])) if lay.N_t[t].sum() else 0
        rep['tail'][f'{t:g}'] = {'records': int(lay.tail[t].sum()), 'events': int(len(evs)),
                                 'clusters': int((lay.N_t[t] > 0).sum()), 'largest_cluster': int(lay.cl_ids[big]),
                                 'largest_share_of_records': float(lay.N_t[t][big] / max(lay.N_t[t].sum(), 1))}

    preds = {}
    for s in sides:
        med, mean = load_side(s, root, n)
        preds[s] = (med[have], mean[have])
        del med, mean
        print('loaded', s, flush=True)

    boot_cols, views = [], {}
    for arm, ref in pairs:
        key = f'{arm}:{ref}'
        for ai, action in enumerate(('median', 'mean')):
            for di, d in enumerate(DEADLINES):
                pa, pb = preds[arm][ai][:, di], preds[ref][ai][:, di]
                cols = lay.columns(np.abs(pa - y), np.abs(pb - y), pa >= args.fp_cut, pb >= args.fp_cut)
                for name, Sa, Sb, N, scale in cols:
                    views[key, action, d, name] = cluster_views(Sa, Sb, N, lay.cl_ids, scale)
                    if N.sum() > 0:
                        boot_cols.append(((key, action, d, name), Sa - Sb, N, scale))
    print(f'bootstrap: {len(boot_cols)} columns x {lay.G} clusters x {args.reps} replicates', flush=True)
    boots = bootstrap(boot_cols, lay.G, args.reps, args.seed)
    for (key, action, d, name), v in views.items():
        b = boots.get((key, action, d, name))
        if b is not None:
            v['boot'] = [b[0], b[1]]
            v['boot_mean'] = b[2]
            v['boot_finite'] = b[3]
        rep['pairs'].setdefault(key, {}).setdefault(action, {}).setdefault(d, {})[name] = v
    out = Path(args.out)
    out.write_text(json.dumps(rounded(rep), indent=1))
    out.with_suffix('.md').write_text(markdown(rep))
    print('wrote', out, out.with_suffix('.md'), flush=True)
    for key, body in rep['pairs'].items():
        for d in DEADLINES:
            r = body['median'][d]
            top = f'M>={thr[-1]:g}_MAE'
            print(f'{key} {d}: bulk {fmt(r["bulk_MAE"]["delta"])} | {top} {fmt(r[top].get("delta"))} '
                  f'jk {interval(r[top].get("jackknife"))} boot {interval(r[top].get("boot"))} '
                  f'w/o largest {fmt(r[top].get("without_largest"))} | FP4 {fmt(r["FP4_per_1e4"].get("delta"), 2)}')


if __name__ == '__main__':
    main()

"""Multi-station (event-level) combination of single-station magnitude posteriors.

For a factorized posterior p(m|x) = L(m|x) pi(m) / Z, k stations of one event combine as

    p(m | x_1..x_k)  oc  prod_i L(m|x_i) . pi(m)                      rule 'lik_prior'

(the prior counted once). A posterior without an identifiable prior factor can only be
combined by rules that are wrong or heuristic:

    prod_i p(m|x_i)                                   'post_prod'   (prior counted k times)
    (1/k) sum_i p(m|x_i)                              'post_mean'   (no sharpening)
    prod_i [p(m|x_i)/e^phi(m)] . e^(phi(m)+gamma (m-M_C)+)  'lik_prior_cal' (gamma: one tilt of the
                                                       prior above M_C per held-out fold, chosen
                                                       to minimize the other folds' fused
                                                       all-event MAE at k = all; cross-fitted)
    prod_i [p(m|x_i)/pi_hat(m)] . pi_hat(m) e^(gamma m)  'hist_adj_cal' (same calibrated tilt on pi_hat)
    prod_i p(m|x_i)/pi_hat(m) . pi_hat(m)             'hist_adj'    (pi_hat = training-label
                                                       histogram of the fold, smoothed with a
                                                       0.25-unit kernel and floored at 1e-5:
                                                       the logit-adjustment analogue)

Stations are ordered by hypocentral distance (a proxy for P-arrival order); each contributes
its d-second posterior. Events with >= k usable records are evaluated at k = 1, 2, 3, 4, 6, 8
and 'all'. Decisions: median and mean of the combined posterior. Metrics: event-level MAE over
all events, M>=T1 events and M>=T2 events, with a cluster bootstrap over aftershock sequences
for paired differences.

Inputs are the float16 *log*-posteriors written by export_logpmf.py (the saved PMFs underflow
in the tail), plus each fold's learned log prior for GR-factorized heads.

  python tailrisk/multistation.py --arms mix_nll,mixgr_nll,eqgr_nll,eqdgr_nll --thr 4,5 --out results/multistation_instance.json
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import DURATIONS, PMF_CENTERS, WORK, load_meta
from evaluate import wmed_from_pmf

RULES = ('post_prod', 'post_mean', 'hist_adj', 'hist_adj_cal', 'lik_prior', 'lik_prior_cal')
GAMMAS = np.arange(-3.0, 3.01, 0.25)
M_C = 3.5                                   # the tilt acts only where the prior factor is GR-linear
HINGE = np.maximum(PMF_CENTERS - M_C, 0.0).astype(np.float32)


def extend_prior(phi):
    """The learned prior is defined on the head's grid (up to M8.5); beyond it the GR tail is
    linear, so extrapolate with the slope of the last two defined bins."""
    phi = phi.astype(np.float64).copy()
    ok = np.isfinite(phi)
    if ok.all():
        return phi.astype(np.float32)
    last = np.nonzero(ok)[0][-1]
    slope = phi[last] - phi[last - 1]
    for j in range(last + 1, len(phi)):
        phi[j] = phi[j - 1] + slope
    first = np.nonzero(ok)[0][0]
    for j in range(first - 1, -1, -1):
        phi[j] = phi[j + 1] - (phi[first + 1] - phi[first])
    return phi.astype(np.float32)


def load_logpmf(arm, n, root):
    lp = np.full((n, 3, len(PMF_CENTERS)), np.nan, np.float16)
    prior = {}
    for f in sorted((root / arm).glob('fold*.npz')):
        z = np.load(f)
        lp[z['rows']] = z['logpmf']
        if 'log_prior' in z:
            prior[int(f.stem[4:])] = extend_prior(z['log_prior'])
    return lp, prior


def train_hist_logprior(mag, fold, nf, sigma=0.25, floor=1e-5):
    """Fold-wise log of the training-label histogram on the PMF grid, Gaussian-smoothed
    (sigma magnitude units) and floored at `floor` of the total, so that empty bins do not
    receive an unbounded correction."""
    out = {}
    c = PMF_CENTERS.astype(np.float64)
    for f in range(nf):
        y = mag[fold != f]
        idx = np.round((y - PMF_CENTERS[0]) * 10).astype(int).clip(0, len(PMF_CENTERS) - 1)
        h = np.bincount(idx, minlength=len(PMF_CENTERS)).astype(np.float64)
        kern = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sigma) ** 2)
        hs = kern @ h
        hs = hs / hs.sum()
        out[f] = np.log(np.maximum(hs, floor)).astype(np.float32)
    return out


def normalize(S):
    S = S - S.max(1, keepdims=True)
    p = np.exp(S)
    return p / p.sum(1, keepdims=True)


def combine(lp_rows, rule, k, phi_ev, pihat_ev, gamma_ev=None):
    """lp_rows: (n_ev, k, K) float32 log-posteriors of the k stations. Returns normalized pmf."""
    if rule == 'post_mean':
        S = np.logaddexp.reduce(lp_rows, axis=1) - np.log(k)
    else:
        S = lp_rows.sum(1)
        if rule == 'lik_prior':
            S = S - (k - 1) * phi_ev
        elif rule == 'lik_prior_cal':
            S = S - (k - 1) * (phi_ev + gamma_ev['phi'][:, None] * HINGE[None, :])
        elif rule == 'hist_adj':
            S = S - (k - 1) * pihat_ev
        elif rule == 'hist_adj_cal':
            S = S - (k - 1) * (pihat_ev + gamma_ev['hist'][:, None] * HINGE[None, :])
    return normalize(S)


def calibrate_gamma(S_all, kv, phi_ev, m_ev, ev_fold, mask):
    """Cross-fitted tilt of the prior above M_C: for each held-out fold f, the gamma that minimizes
    the fused event MAE (median action) over the masked events of the *other* folds at k = all.
    Returns gamma per event and the chosen value per fold."""
    errs = np.zeros((len(GAMMAS), len(m_ev)), np.float32)
    for gi, g in enumerate(GAMMAS):
        p = normalize(S_all - (kv - 1) * (phi_ev + g * HINGE[None, :]))
        errs[gi] = np.abs(wmed_from_pmf(p, np.array([1.0]))[:, 0] - m_ev)
    gamma_ev = np.zeros(len(m_ev), np.float32)
    chosen = {}
    for f in np.unique(ev_fold):
        sel = mask & (ev_fold != f)
        gi = int(np.argmin(errs[:, sel].mean(1))) if sel.any() else int(np.argmin(np.abs(GAMMAS)))
        chosen[int(f)] = float(GAMMAS[gi])
        gamma_ev[ev_fold == f] = GAMMAS[gi]
    return gamma_ev, chosen


def decide(p):
    med = wmed_from_pmf(p, np.array([1.0]))[:, 0]
    mean = p @ PMF_CENTERS.astype(np.float32)
    return {'median': med, 'mean': mean}


class EventBoot:
    def __init__(self, cluster_ev, reps, seed=0):
        self.cl = np.unique(cluster_ev, return_inverse=True)[1]
        self.nc = self.cl.max() + 1
        self.w = np.random.default_rng(seed).multinomial(self.nc, np.full(self.nc, 1 / self.nc), size=reps).astype(np.float64)

    def rep_means(self, err, mask):
        """Replicate means of err over events in mask: (reps,)."""
        S = np.bincount(self.cl[mask], err[mask], self.nc)
        N = np.bincount(self.cl[mask], minlength=self.nc).astype(np.float64)
        with np.errstate(invalid='ignore', divide='ignore'):
            return (self.w @ S) / (self.w @ N)


def ci(d):
    d = d[np.isfinite(d)]
    if len(d) < 50:
        return None
    return {'mean': float(d.mean()), 'lo': float(np.quantile(d, .025)), 'hi': float(np.quantile(d, .975)), 'n_reps': int(len(d))}


def collapse_by_station(lp, meta, extra=()):
    """Merge the co-located instruments of each (event, station) into one posterior: the mean of
    their log-posteriors (a geometric mean, so the training prior is still counted once), then
    renormalized. Returns the collapsed log-posteriors per arm and the per-group metadata
    (mag, event, cluster, fold, hyp_km, and any `extra` fields, averaged)."""
    ev, st = meta['event'].astype(np.int64), meta['station'].astype(np.int64)
    ok = np.all([np.isfinite(v[:, 0, 0]) for v in lp.values()], 0) & np.isfinite(meta['hyp_km'])
    idx = np.nonzero(ok)[0]
    key = ev[idx] * (int(st.max()) + 1) + st[idx]
    order = np.argsort(key, kind='stable')
    idx, key = idx[order], key[order]
    starts = np.r_[0, np.nonzero(np.diff(key))[0] + 1]
    sizes = np.diff(np.r_[starts, len(idx)]).astype(np.float32)
    out_lp = {}
    for a, v in lp.items():
        x = v[idx].astype(np.float32)
        S = np.add.reduceat(x, starts, axis=0) / sizes[:, None, None]
        S = S - S.max(-1, keepdims=True)
        S = S - np.log(np.exp(S).sum(-1, keepdims=True))
        out_lp[a] = S.astype(np.float16)
    first = idx[starts]
    m = {k: meta[k][first] for k in ('mag', 'event', 'cluster', 'fold', 'station')}
    m['hyp_km'] = np.minimum.reduceat(meta['hyp_km'][idx], starts)
    for k in extra:
        vals = meta[k][idx].astype(np.float64)
        m[k] = np.add.reduceat(np.nan_to_num(vals, nan=0.0), starts) / np.maximum(np.add.reduceat(np.isfinite(vals).astype(float), starts), 1)
    print(f'collapsed {len(idx)} records to {len(starts)} station-event groups ({len(idx) / len(starts):.2f} instruments per station)', flush=True)
    return out_lp, m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', required=True)
    ap.add_argument('--root', default=str(WORK / 'logpmf'))
    ap.add_argument('--thr', default='4,5')
    ap.add_argument('--ks', default='1,2,3,4,6,8,all')
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--out', required=True)
    ap.add_argument('--hist-sigma', type=float, default=0.25, help='kernel width (magnitude units) of the smoothed training-label prior')
    ap.add_argument('--hist-floor', type=float, default=1e-5, help='floor of the smoothed training-label prior (fraction of total)')
    ap.add_argument('--cal-on', default='all', choices=['all', 'tail'], help='events whose fused MAE selects the calibrated tilt (cross-fitted over folds)')
    ap.add_argument('--dedupe-stations', action='store_true', help='merge co-located instruments of a station into one posterior per event before fusing (audit M4)')
    args = ap.parse_args()
    thr = [float(t) for t in args.thr.split(',')]
    arms = args.arms.split(',')
    root = Path(args.root)
    meta = load_meta()
    mag, ev, cl, fold, hyp = meta['mag'], meta['event'], meta['cluster'], meta['fold'].astype(int), meta['hyp_km']
    n = len(mag)
    lp, phi = {}, {}
    for a in arms:
        lp[a], phi[a] = load_logpmf(a, n, root)
        print(a, 'folds with prior:', sorted(phi[a]), flush=True)
    pihat = train_hist_logprior(mag, fold, int(fold.max()) + 1, args.hist_sigma, args.hist_floor)
    if args.dedupe_stations:
        lp, cm = collapse_by_station(lp, meta)
        mag, ev, cl, fold, hyp = cm['mag'], cm['event'], cm['cluster'], cm['fold'].astype(int), cm['hyp_km']
    usable = np.all([np.isfinite(lp[a][:, 0, 0]) for a in arms], 0) & np.isfinite(hyp)
    # order usable records by (event, hypocentral distance)
    order = np.lexsort((hyp, ev))
    order = order[usable[order]]
    ev_o = ev[order]
    starts = np.r_[0, np.nonzero(np.diff(ev_o))[0] + 1]
    sizes = np.diff(np.r_[starts, len(order)])
    ev_ids = ev_o[starts]
    ev_mag = mag[order[starts]]
    ev_fold = fold[order[starts]]
    ev_cl = cl[order[starts]]
    print(f'{len(ev_ids)} events with usable records; sizes: median {np.median(sizes):.0f}, '
          f'>=4: {(sizes >= 4).sum()}, >=8: {(sizes >= 8).sum()}', flush=True)
    rep = {'arms': arms, 'thr': thr, 'hist_sigma': args.hist_sigma, 'hist_floor': args.hist_floor, 'dedupe_stations': bool(args.dedupe_stations), 'ks': {}, 'metrics': {}, 'vs_ref': {}, 'gamma': {}}
    ks = [k for k in args.ks.split(',')]
    # calibrated tilt per arm and deadline (cross-fitted over folds at k = all, on M>=thr[0] events)
    gamma = {}
    cal_mask = np.ones(len(ev_mag), bool) if args.cal_on == 'all' else ev_mag >= thr[0] - 1e-6
    pihat_all = np.stack([pihat[f] for f in ev_fold])
    kv_all = sizes[:, None].astype(np.float32)
    for a in arms:
        bases = {'hist': pihat_all}
        if phi[a]:
            bases['phi'] = np.stack([phi[a][f] for f in ev_fold])
        for d_i, d in enumerate(DURATIONS):
            x = lp[a][order, d_i].astype(np.float32)
            S_all = np.add.reduceat(x, starts, axis=0)
            gamma[a, d] = {}
            for base, prior_all in bases.items():
                gamma[a, d][base], chosen = calibrate_gamma(S_all, kv_all, prior_all, ev_mag, ev_fold, cal_mask)
                rep['gamma'].setdefault(a, {}).setdefault(f'{d}s', {})[base] = chosen
                print(f'{a} {d}s calibrated tilt on {base} per held-out fold: {chosen}', flush=True)
    for ks_ in ks:
        kk = None if ks_ == 'all' else int(ks_)
        sel = sizes >= (kk or 1)
        idx_ev = np.nonzero(sel)[0]
        m_ev = ev_mag[idx_ev]
        masks = {'all': np.ones(len(idx_ev), bool)}
        for t in thr:
            masks[f'M>={t:g}'] = m_ev >= t - 1e-6
        rep['ks'][ks_] = {'n_events': int(len(idx_ev)), **{f'n_{k}': int(v.sum()) for k, v in masks.items()}}
        boot = EventBoot(ev_cl[idx_ev], args.reps)
        if kk is not None:
            rows = np.stack([order[starts[idx_ev] + j] for j in range(kk)], 1)       # (n_ev, k)
        for d_i, d in enumerate(DURATIONS):
            reps_store = {}
            for a in arms:
                phi_ev = np.stack([phi[a][f] for f in ev_fold[idx_ev]]) if phi[a] else None
                pihat_ev = np.stack([pihat[f] for f in ev_fold[idx_ev]])
                gamma_ev = {b: g[idx_ev] for b, g in gamma[a, d].items()}
                for rule in RULES:
                    if rule in ('lik_prior', 'lik_prior_cal') and phi_ev is None:
                        continue
                    if kk is not None:
                        lpr = lp[a][rows, d_i].astype(np.float32)                   # (n_ev, k, K)
                        p = combine(lpr, rule, kk, phi_ev, pihat_ev, gamma_ev)
                    else:   # all stations of each event, ragged: reduce over sorted rows
                        x = lp[a][order, d_i].astype(np.float32)
                        if rule == 'post_mean':
                            S = np.stack([np.logaddexp.reduce(x[s:s + z], axis=0) - np.log(z) for s, z in zip(starts[idx_ev], sizes[idx_ev])])
                        else:
                            S = np.add.reduceat(x, starts, axis=0)[idx_ev]
                            kv = sizes[idx_ev][:, None].astype(np.float32)
                            if rule == 'lik_prior':
                                S = S - (kv - 1) * phi_ev
                            elif rule == 'lik_prior_cal':
                                S = S - (kv - 1) * (phi_ev + gamma_ev['phi'][:, None] * HINGE[None, :])
                            elif rule == 'hist_adj':
                                S = S - (kv - 1) * pihat_ev
                            elif rule == 'hist_adj_cal':
                                S = S - (kv - 1) * (pihat_ev + gamma_ev['hist'][:, None] * HINGE[None, :])
                        p = normalize(S)
                    for act, dec in decide(p).items():
                        err = np.abs(dec - m_ev)
                        key = f'{a}:{rule}:{act}'
                        met = rep['metrics'].setdefault(key, {}).setdefault(ks_, {})
                        met[f'{d}s'] = {mk: float(err[mv].mean()) if mv.any() else None for mk, mv in masks.items()}
                        met[f'{d}s'].update({f'{mk}_bias': float((dec - m_ev)[mv].mean()) if mv.any() else None for mk, mv in masks.items()})
                        reps_store[key] = {mk: boot.rep_means(err, mv) for mk, mv in masks.items()}
            # paired differences: every config against the mixture's three rules and against its own post_prod
            for key, r in reps_store.items():
                a, rule, act = key.split(':')
                refs = [f'{arms[0]}:{rr}:{act}' for rr in ('post_prod', 'post_mean', 'hist_adj')] + [f'{a}:post_prod:{act}']
                for ref in refs:
                    if ref == key or ref not in reps_store:
                        continue
                    out = rep['vs_ref'].setdefault(key, {}).setdefault(ref, {}).setdefault(ks_, {})
                    out[f'{d}s'] = {mk: ci(r[mk] - reps_store[ref][mk]) for mk in masks}
            print(f'k={ks_} {d}s done', flush=True)
    Path(args.out).write_text(json.dumps(rep, indent=1))
    # compact view: event-level MAE of the top tail vs k, median action
    top = f'M>={thr[-1]:g}'
    for d in DURATIONS:
        print(f'\n=== {d}s  event-level MAE, median action; columns k = {ks}; rows arm:rule  [{top} events | all events]')
        for key in rep['metrics']:
            if not key.endswith(':median'):
                continue
            vals = [rep['metrics'][key][k_][f'{d}s'] for k_ in ks]
            print(f'{key[:-7]:<24}' + ' '.join(f'{(v[top] if v[top] is not None else float("nan")):6.3f}/{v["all"]:.3f}' for v in vals))


if __name__ == '__main__':
    main()

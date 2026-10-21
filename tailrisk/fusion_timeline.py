"""Event magnitude versus time since the first P arrival, fusing whatever each station has.

At wall-clock time T after the event's first P arrival, station i (P at t_i after the first)
has T - t_i seconds of P wave and contributes its posterior at the largest deadline d in
{1, 3, 5} s with d <= T - t_i (none if < 1 s). P arrival times are approximated from the
hypocentral distance, t_i = hyp_km / V_P, V_P = 6.5 km/s (stated assumption; the catalogues do
not all carry per-station picks). Rules as in multistation.py: posterior product (naive),
posterior mean, histogram-adjusted product and, for GR heads, the own factor counted once.
Event-level MAE of the top tail and of all events at T = 2, 3, 4, 6, 8, 10, 15, 20 s, cluster
bootstrap for paired differences against the free mixture's histogram-adjusted product and
its naive product.

  python tailrisk/fusion_timeline.py --arms mix_nll,eqgr_nll,eqdgr_nll --thr 4,5 --out results/fusion_timeline_instance_s1.json
"""
import argparse
import json
from pathlib import Path

import numpy as np

from common import PMF_CENTERS, WORK, load_meta
from multistation import EventBoot, ci, decide, load_logpmf, normalize, train_hist_logprior

V_P = 6.5
TIMES = (2, 3, 4, 6, 8, 10, 15, 20)
RULES = ('post_prod', 'post_mean', 'hist_adj', 'lik_prior')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--arms', required=True)
    ap.add_argument('--root', default=str(WORK / 'logpmf'))
    ap.add_argument('--thr', default='4,5')
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--out', required=True)
    ap.add_argument('--timing', default='proxy', choices=['proxy', 'measured'],
                    help="'proxy': t_i = hyp_km / V_P; 'measured': per-station P delays from meta['p_after_network_s'] (Chile)")
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
    pihat = train_hist_logprior(mag, fold, int(fold.max()) + 1)
    usable = np.all([np.isfinite(lp[a][:, 0, 0]) for a in arms], 0) & np.isfinite(hyp)
    order = np.lexsort((hyp, ev))
    order = order[usable[order]]
    ev_o = ev[order]
    starts = np.r_[0, np.nonzero(np.diff(ev_o))[0] + 1]
    sizes = np.diff(np.r_[starts, len(order)])
    ev_idx = np.repeat(np.arange(len(starts)), sizes)              # event index per sorted row
    ev_mag, ev_fold, ev_cl = mag[order[starts]], fold[order[starts]], cl[order[starts]]
    if args.timing == 'measured':
        t_abs = meta['p_after_network_s'].astype(np.float64)[order]
        usable_t = np.isfinite(t_abs)
    else:
        t_abs = hyp[order] / V_P
        usable_t = np.ones(len(order), bool)
    first = np.minimum.reduceat(np.where(usable_t, t_abs, np.inf), starts)
    t_rel = t_abs - np.repeat(first, sizes)                          # seconds after the event's first P
    t_rel = np.where(usable_t, t_rel, np.inf)
    masks = {'all': np.ones(len(starts), bool)}
    for t in thr:
        masks[f'M>={t:g}'] = ev_mag >= t - 1e-6
    boot = EventBoot(ev_cl, args.reps)
    rep = {'arms': arms, 'thr': thr, 'v_p': V_P, 'timing': args.timing, 'times': TIMES, 'n_events': int(len(starts)),
           'n_tail': {k: int(v.sum()) for k, v in masks.items()}, 'metrics': {}, 'vs_ref': {}, 'stations_used': {}}
    pihat_ev = np.stack([pihat[f] for f in ev_fold])
    for T in TIMES:
        avail = T - t_rel
        d_idx = np.where(avail >= 5, 2, np.where(avail >= 3, 1, np.where(avail >= 1, 0, -1)))
        sel = d_idx >= 0
        k_ev = np.bincount(ev_idx[sel], minlength=len(starts)).astype(np.float32)
        has = k_ev > 0
        rep['stations_used'][str(T)] = {'median_k': float(np.median(k_ev[has])), 'events_with_data': int(has.sum()),
                                        'share_at_5s': float((d_idx[sel] == 2).mean()), 'share_at_1s': float((d_idx[sel] == 0).mean())}
        reps_store = {}
        e_sel = ev_idx[sel]                                                   # sorted: contiguous groups
        g_start = np.r_[0, np.nonzero(np.diff(e_sel))[0] + 1] if sel.any() else np.zeros(0, int)
        g_ev = e_sel[g_start]
        for a in arms:
            x = lp[a][order[sel], d_idx[sel]].astype(np.float32)                  # (n_sel, K)
            S = np.zeros((len(starts), len(PMF_CENTERS)), np.float32)
            M = np.full((len(starts), len(PMF_CENTERS)), -np.inf, np.float32)   # logsumexp for the mean rule
            E = np.zeros_like(S)
            if len(g_start):
                S[g_ev] = np.add.reduceat(x, g_start, axis=0)
                M[g_ev] = np.maximum.reduceat(x, g_start, axis=0)
                E[g_ev] = np.add.reduceat(np.exp(x - M[e_sel]), g_start, axis=0)
            phi_ev = np.stack([phi[a][f] for f in ev_fold]) if phi[a] else None
            for rule in RULES:
                if rule == 'lik_prior' and phi_ev is None:
                    continue
                if rule == 'post_mean':
                    Z = M + np.log(np.maximum(E, 1e-30)) - np.log(np.maximum(k_ev, 1))[:, None]
                elif rule == 'lik_prior':
                    Z = S - (k_ev - 1)[:, None] * phi_ev
                elif rule == 'hist_adj':
                    Z = S - (k_ev - 1)[:, None] * pihat_ev
                else:
                    Z = S
                p = normalize(np.where(has[:, None], Z, 0.0))
                for act, dec in decide(p).items():
                    err = np.abs(dec - ev_mag)
                    key = f'{a}:{rule}:{act}'
                    met = rep['metrics'].setdefault(key, {}).setdefault(str(T), {})
                    for mk, mv in masks.items():
                        m = mv & has
                        met[mk] = float(err[m].mean()) if m.any() else None
                        met[f'{mk}_bias'] = float((dec - ev_mag)[m].mean()) if m.any() else None
                    reps_store[key] = {mk: boot.rep_means(err, mv & has) for mk, mv in masks.items()}
        for key, r in reps_store.items():
            a, rule, act = key.split(':')
            for ref in (f'{arms[0]}:hist_adj:{act}', f'{arms[0]}:post_prod:{act}'):
                if ref == key or ref not in reps_store:
                    continue
                out = rep['vs_ref'].setdefault(key, {}).setdefault(ref, {})
                out[str(T)] = {mk: ci(r[mk] - reps_store[ref][mk]) for mk in masks}
        print(f'T={T}s: events with data {int(has.sum())}, median stations {np.median(k_ev[has]):.0f}', flush=True)
    Path(args.out).write_text(json.dumps(rep, indent=1))
    top = f'M>={thr[-1]:g}'
    print(f'\nevent-level MAE [{top} | all], median action, vs T (s): ' + ' '.join(str(t) for t in TIMES))
    for key, by in rep['metrics'].items():
        if key.endswith(':median'):
            print(f'{key[:-7]:<22}' + ' '.join(f'{by[str(T)][top]:.3f}/{by[str(T)]["all"]:.3f}' for T in TIMES))


if __name__ == '__main__':
    main()

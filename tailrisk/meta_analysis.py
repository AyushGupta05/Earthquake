"""Pooled cross-catalogue comparison from robust_tail.py outputs (PREREGISTRATION_STEAD.md, amendment 2).

Each catalogue contributes one paired difference per deadline, Δ = arm ensemble − reference ensemble
at its primary tail threshold, with the delete-one-cluster jackknife standard error. The script
reports the fixed-effect and DerSimonian–Laird random-effects pooled Δ (normal interval), the
Hartung–Knapp–Sidik–Jonkman interval (t on k − 1 df, the conservative one for few catalogues),
the between-catalogue SD τ, and a pooled sign test over all clusters that carry tail events
(each cluster counted once, in its own catalogue).

  python meta_analysis.py --spec INSTANCE:results/robust_instance.json:5 \
      --spec Chile:results/robust_chile.json:6 --spec GEOFON:results/robust_geofon.json:7 \
      --spec STEAD:results/robust_stead.json:5 --pair 'eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3:mix_nll+mix_nll_s2+mix_nll_s3' \
      --out results/meta_eqdgr.json
"""
import argparse
import json
import math

from scipy import stats


def pool(d, se):
    w = [1 / s ** 2 for s in se]
    fe = sum(wi * di for wi, di in zip(w, d)) / sum(w)
    fe_se = math.sqrt(1 / sum(w))
    k = len(d)
    q = sum(wi * (di - fe) ** 2 for wi, di in zip(w, d))
    c = sum(w) - sum(wi ** 2 for wi in w) / sum(w)
    tau2 = max(0.0, (q - (k - 1)) / c) if k > 1 else 0.0
    wr = [1 / (s ** 2 + tau2) for s in se]
    re = sum(wi * di for wi, di in zip(wr, d)) / sum(wr)
    re_se = math.sqrt(1 / sum(wr))
    out = {'k': k, 'fixed': fe, 'fixed_ci': [fe - 1.96 * fe_se, fe + 1.96 * fe_se],
           'random': re, 'random_ci': [re - 1.96 * re_se, re + 1.96 * re_se], 'tau': math.sqrt(tau2),
           'Q': q, 'Q_p': float(stats.chi2.sf(q, k - 1)) if k > 1 else None}
    if k > 1:
        hk = sum(wi * (di - re) ** 2 for wi, di in zip(wr, d)) / ((k - 1) * sum(wr))
        hk_se = math.sqrt(max(hk, 1e-300))
        t = stats.t.ppf(0.975, k - 1)
        out['hksj_ci'] = [re - t * hk_se, re + t * hk_se]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--spec', action='append', required=True, help='label:robust_json:threshold')
    ap.add_argument('--pair', required=True, help='pair key as written by robust_tail.py (arm:ref)')
    ap.add_argument('--action', default='median', choices=['median', 'mean'])
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    specs = []
    for s in args.spec:
        label, path, thr = s.split(':')
        specs.append((label, json.load(open(path)), thr))
    rep = {'pair': args.pair, 'action': args.action, 'catalogues': [s[0] for s in specs], 'deadlines': {}}
    lines = [f'# Pooled cross-catalogue comparison: `{args.pair}` ({args.action} action)', '',
             'Δ = arm − reference at each catalogue\'s primary threshold; SE = delete-one-cluster jackknife.',
             'Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over',
             'all tail-carrying clusters.', '']
    for t in ('1s', '3s', '5s'):
        rows, d, se, neg, pos = [], [], [], 0, 0
        for label, rob, thr in specs:
            thr_s = thr if '.' not in thr else thr.rstrip('0').rstrip('.')
            m = rob['pairs'][args.pair][args.action][t][f'M>={thr_s}_MAE']
            b = rob['pairs'][args.pair][args.action][t]['bulk_MAE']
            rows.append({'catalogue': label, 'thr': float(thr), 'delta': m['delta'], 'se': m['jackknife_se'], 'G': m['G'],
                         'clusters_neg': m['clusters_neg'], 'clusters_pos': m['clusters_pos'],
                         'bulk_delta': b['delta'], 'bulk_se': b['jackknife_se']})
            d.append(m['delta'])
            se.append(m['jackknife_se'])
            neg += m['clusters_neg']
            pos += m['clusters_pos']
        tail = pool(d, se)
        bulk = pool([r['bulk_delta'] for r in rows], [r['bulk_se'] for r in rows])
        sign_p = float(stats.binomtest(neg, neg + pos, 0.5).pvalue) if neg + pos else None
        rep['deadlines'][t] = {'catalogues': rows, 'tail': tail, 'bulk': bulk,
                               'clusters_neg': neg, 'clusters_pos': pos, 'sign_p': sign_p}
        lines += [f'## {t}', '', '| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |',
                  '|---|---|---|---|---|---|---|']
        for r in rows:
            lines.append(f"| {r['catalogue']} | M≥{r['thr']:g} | {r['delta']:+.4f} | {r['se']:.4f} | {r['G']} | "
                         f"{r['clusters_neg']} / {r['clusters_pos']} | {r['bulk_delta']:+.4f} |")
        lines += ['',
                  f"Pooled tail Δ: fixed {tail['fixed']:+.4f} [{tail['fixed_ci'][0]:+.4f}, {tail['fixed_ci'][1]:+.4f}]; "
                  f"random {tail['random']:+.4f} [{tail['random_ci'][0]:+.4f}, {tail['random_ci'][1]:+.4f}]"
                  + (f"; HKSJ [{tail['hksj_ci'][0]:+.4f}, {tail['hksj_ci'][1]:+.4f}]" if 'hksj_ci' in tail else '')
                  + f"; τ = {tail['tau']:.4f}" + (f", Q p = {tail['Q_p']:.3g}" if tail['Q_p'] is not None else ''),
                  f"Pooled bulk Δ: random {bulk['random']:+.4f} [{bulk['random_ci'][0]:+.4f}, {bulk['random_ci'][1]:+.4f}]",
                  f"Clusters favouring the arm: {neg} of {neg + pos} (sign test p = {sign_p:.3g})", '']
    json.dump(rep, open(args.out, 'w'), indent=1)
    open(args.out.rsplit('.', 1)[0] + '.md', 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()

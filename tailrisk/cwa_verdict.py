"""Apply the pre-registered CWA decision rules (PREREGISTRATION_CWA.md, D1-D5) to the saved results.

Mechanical: reads the robust_tail.py, meta_analysis.py and geofon_eval.py outputs written by
cwa_eval.sh and prints PASS / FAIL per criterion with the numbers, so the verdict is on record
before anyone reads it. Writes results/CWA_VERDICT.md.

  python cwa_verdict.py
"""
import json
from pathlib import Path

R = Path(__file__).resolve().parent / 'results'
M = 'mix_nll+mix_nll_s2+mix_nll_s3'
E = 'eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3'
Q = 'eqgr_nll+eqgr_nll_s2+eqgr_nll_s3'
K = 'eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR'
F = 'mixdgr_nll_condR+mixdgr_nll_s2_condR+mixdgr_nll_s3_condR'
Z = 'eqdgr_k1_nll+eqdgr_k1_nll_s2+eqdgr_k1_nll_s3'
H = 'eqdgr_kp10_nll+eqdgr_kp10_nll_s2+eqdgr_kp10_nll_s3'
ZQ = 'eqgr_k1_nll+eqgr_k1_nll_s2+eqgr_k1_nll_s3'
HQ = 'eqgr_kp10_nll+eqgr_kp10_nll_s2+eqgr_kp10_nll_s3'
BULK_GUARD = 0.002
out = []


def say(s=''):
    out.append(s)
    print(s)


def cell(rob, pair, t, metric):
    return rob['pairs'][pair]['median'][t][metric]


def fmt(c):
    return f"{c['delta']:+.4f} [{c['jackknife'][0]:+.4f}, {c['jackknife'][1]:+.4f}]"


def tail_lower(rob, pair, metric='M>=5_MAE'):
    """E1 < 0 at 3 s and 5 s with jackknife intervals excluding zero."""
    ok, txt = True, []
    for t in ('3s', '5s'):
        c = cell(rob, pair, t, metric)
        ok &= c['delta'] < 0 and c['jackknife'][1] < 0
        txt.append(f'{t} {fmt(c)}')
    return ok, '; '.join(txt)


def bulk_guard(rob, pair, lim=BULK_GUARD):
    ok, txt = True, []
    for t in ('1s', '3s', '5s'):
        c = cell(rob, pair, t, 'bulk_MAE')
        ok &= c['delta'] <= lim
        txt.append(f"{t} {c['delta']:+.4f}")
    return ok, '; '.join(txt)


def d1_like(rob, pair, label):
    a, ta = tail_lower(rob, pair)
    b, tb = bulk_guard(rob, pair)
    say(f'* {label}: tail {"PASS" if a else "FAIL"} ({ta}); bulk guard {"PASS" if b else "FAIL"} ({tb}) → **{"PASS" if a and b else "FAIL"}**')
    return a and b


def load(name):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else None


say('# CWA pre-registered verdict (mechanical; PREREGISTRATION_CWA.md and amendment 1)')
say()
rob = load('robust_cwa_ens3.json')
say('## D1 — main test against the free-mixture ensemble')
d1 = {}
if rob:
    d1['eqdgr'] = d1_like(rob, f'{E}:{M}', 'eqdgr (primary)')
    d1['eqgr'] = d1_like(rob, f'{Q}:{M}', 'eqgr (secondary)')
else:
    say('* results missing')
say()
say('## D2 — equal information: eqdgr|r against mixdgr|r')
rob = load('robust_cwa_equalinfo.json')
d2 = d1_like(rob, f'{K}:{F}', 'eqdgr|r vs mixdgr|r') if rob else say('* results missing')
say()
say('## D3 — capped at M5: eqdgr_cap50_cond against mix_cap50 and mix_cap50_aug15')
rob = load('robust_cwa_cap50.json')
ev = load('cwa_eval_cap50.json')
d3 = None
if rob and ev:
    a, ta = tail_lower(rob, 'eqdgr_cap50_cond:mix_cap50')
    b, tb = tail_lower(rob, 'eqdgr_cap50_cond:mix_cap50_aug15')
    arms = ev['arms']
    g = [arms['eqdgr_cap50_cond'][t]['median_action']['M<5_MAE'] - arms['mix_cap50'][t]['median_action']['M<5_MAE'] for t in ('1s', '3s', '5s')]
    c = all(x <= 0.005 for x in g)
    d3 = a and b and c
    say(f'* vs mix_cap50: {"PASS" if a else "FAIL"} ({ta})')
    say(f'* vs mix_cap50_aug15: {"PASS" if b else "FAIL"} ({tb})')
    say(f'* M<5 MAE guard (+.005): {"PASS" if c else "FAIL"} ({" ".join(f"{x:+.4f}" for x in g)})')
    say(f'* → **{"PASS" if d3 else "FAIL"}**; secondary eqgr_cap50: vs mix_cap50 {tail_lower(rob, "eqgr_cap50:mix_cap50")[1]}; vs aug15 {tail_lower(rob, "eqgr_cap50:mix_cap50_aug15")[1]}')
else:
    say('* results missing')
say()
say('## D4 — pooled over five catalogues (HKSJ at 3 s and 5 s; pooled bulk ≤ +.002)')
d4 = {}
for name, label in (('meta5_eqdgr.json', 'eqdgr − mix (marginal)'), ('meta5_equalinfo.json', 'eqdgr|r − mixdgr|r')):
    rep = load(name)
    if not rep:
        say(f'* {label}: results missing')
        continue
    ok = True
    parts = []
    for t in ('3s', '5s'):
        lo, hi = rep['deadlines'][t]['tail'].get('hksj_ci', rep['deadlines'][t]['tail']['random_ci'])
        ok &= hi < 0
        parts.append(f"{t} Δ {rep['deadlines'][t]['tail']['random']:+.4f} HKSJ [{lo:+.4f}, {hi:+.4f}]")
    bulk = [rep['deadlines'][t]['bulk']['random'] for t in ('1s', '3s', '5s')]
    ok &= all(b <= BULK_GUARD for b in bulk)
    d4[label] = ok
    say(f'* {label}: {"PASS" if ok else "FAIL"} ({"; ".join(parts)}; pooled bulk {" ".join(f"{b:+.4f}" for b in bulk)}; '
        f'sequences favouring {rep["deadlines"]["5s"]["clusters_neg"]} of {rep["deadlines"]["5s"]["clusters_neg"] + rep["deadlines"]["5s"]["clusters_pos"]} at 5 s)')
say()
say('## D5 — hybrid (slope prior λ=10) against κ≡1 and against the mixture')
rob = load('robust_cwa_hybrid.json')
d5 = None
if rob:
    i = d1_like(rob, f'{H}:{M}', 'hybrid vs mix (D1 criteria)')
    ok_b, tb = True, []
    for t in ('1s', '3s', '5s'):
        c = cell(rob, f'{H}:{Z}', t, 'bulk_MAE')
        ok_b &= c['delta'] < 0 and c['jackknife'][1] < 0
        tb.append(f'{t} {fmt(c)}')
    ok_t, tt = True, []
    for t in ('3s', '5s'):
        c = cell(rob, f'{H}:{Z}', t, 'M>=5_MAE')
        ok_t &= c['delta'] <= 0 or c['jackknife'][0] <= 0 <= c['jackknife'][1]
        tt.append(f'{t} {fmt(c)}')
    d5 = i and ok_b and ok_t
    say(f'* hybrid vs κ≡1, bulk lower at every deadline: {"PASS" if ok_b else "FAIL"} ({"; ".join(tb)})')
    say(f'* hybrid vs κ≡1, tail not higher at 3 / 5 s: {"PASS" if ok_t else "FAIL"} ({"; ".join(tt)})')
    say(f'* → **D5 {"PASS" if d5 else "FAIL"}**')
    say(f'* reported: κ≡1 (eqdgr_k1) vs mix under D1: tail {tail_lower(rob, f"{Z}:{M}")[1]}; bulk {bulk_guard(rob, f"{Z}:{M}")[1]}')
    say(f'* reported: plain forms, hybrid vs κ≡1: bulk {"; ".join(fmt(cell(rob, f"{HQ}:{ZQ}", t, "bulk_MAE")) for t in ("1s","3s","5s"))}; tail {tail_lower(rob, f"{HQ}:{ZQ}")[1]}')
    say(f'* reported: hybrid vs the learned slope (eqdgr): tail {tail_lower(rob, f"{H}:{E}")[1]}; bulk {bulk_guard(rob, f"{H}:{E}")[1]}')
else:
    say('* results missing')
say()
say(f'Summary: D1 eqdgr {d1.get("eqdgr")}, D1 eqgr {d1.get("eqgr")}, D2 {d2}, D3 {d3}, D4 {d4}, D5 {d5}')
(R / 'CWA_VERDICT.md').write_text('\n'.join(out) + '\n')

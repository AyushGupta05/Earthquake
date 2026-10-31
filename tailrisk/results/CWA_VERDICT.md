# CWA pre-registered verdict (mechanical; PREREGISTRATION_CWA.md and amendment 1)

## D1 — main test against the free-mixture ensemble
* eqdgr (primary): tail FAIL (3s +0.0209 [+0.0146, +0.0271]; 5s +0.0196 [+0.0128, +0.0264]); bulk guard FAIL (1s +0.0043; 3s +0.0023; 5s +0.0004) → **FAIL**
* eqgr (secondary): tail FAIL (3s +0.0127 [+0.0088, +0.0166]; 5s +0.0110 [+0.0065, +0.0155]); bulk guard FAIL (1s +0.0031; 3s +0.0027; 5s +0.0021) → **FAIL**

## D2 — equal information: eqdgr|r against mixdgr|r
* results missing

## D3 — capped at M5: eqdgr_cap50_cond against mix_cap50 and mix_cap50_aug15
* results missing

## D4 — pooled over five catalogues (HKSJ at 3 s and 5 s; pooled bulk ≤ +.002)
* eqdgr − mix (marginal): FAIL (3s Δ -0.0980 HKSJ [-0.2330, +0.0371]; 5s Δ -0.1326 HKSJ [-0.3122, +0.0471]; pooled bulk +0.0039 +0.0016 +0.0004; sequences favouring 385 of 624 at 5 s)
* eqdgr|r − mixdgr|r: results missing

## D5 — hybrid (slope prior λ=10) against κ≡1 and against the mixture
* hybrid vs mix (D1 criteria): tail FAIL (3s +0.0300 [+0.0223, +0.0376]; 5s +0.0271 [+0.0189, +0.0353]); bulk guard FAIL (1s +0.0072; 3s +0.0046; 5s +0.0023) → **FAIL**
* hybrid vs κ≡1, bulk lower at every deadline: FAIL (1s -0.0000 [-0.0003, +0.0003]; 3s +0.0002 [-0.0002, +0.0007]; 5s +0.0001 [-0.0002, +0.0005])
* hybrid vs κ≡1, tail not higher at 3 / 5 s: PASS (3s -0.0006 [-0.0017, +0.0005]; 5s -0.0008 [-0.0019, +0.0003])
* → **D5 FAIL**
* reported: κ≡1 (eqdgr_k1) vs mix under D1: tail 3s +0.0306 [+0.0235, +0.0376]; 5s +0.0279 [+0.0201, +0.0356]; bulk 1s +0.0072; 3s +0.0044; 5s +0.0022
* reported: plain forms, hybrid vs κ≡1: bulk -0.0005 [-0.0008, -0.0001]; -0.0001 [-0.0004, +0.0002]; -0.0001 [-0.0005, +0.0002]; tail 3s -0.0000 [-0.0009, +0.0009]; 5s +0.0001 [-0.0008, +0.0010]
* reported: hybrid vs the learned slope (eqdgr): tail 3s +0.0091 [+0.0068, +0.0114]; 5s +0.0075 [+0.0053, +0.0097]; bulk 1s +0.0029; 3s +0.0023; 5s +0.0019

Summary: D1 eqdgr False, D1 eqgr False, D2 None, D3 None, D4 {'eqdgr − mix (marginal)': False}, D5 False

# Pooled cross-catalogue comparison: `eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR:lin_invR` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.0568 | 0.1040 | 11 | 7 / 4 | -0.7540 |
| Chile | M≥6 | +0.1288 | 0.0484 | 8 | 2 / 6 | -0.1989 |
| GEOFON | M≥7 | +0.4468 | 0.0561 | 46 | 3 / 43 | -0.3386 |
| STEAD | M≥5 | -0.0642 | 0.0188 | 456 | 260 / 196 | -0.2428 |

Pooled tail Δ: fixed +0.0025 [-0.0298, +0.0348]; random +0.1164 [-0.1247, +0.3575]; HKSJ [-0.2650, +0.4977]; τ = 0.2379, Q p = 9.24e-18
Pooled bulk Δ: random -0.2725 [-0.3282, -0.2168]
Clusters favouring the arm: 272 of 521 (sign test p = 0.335)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1932 | 0.0825 | 11 | 9 / 2 | -0.7216 |
| Chile | M≥6 | -0.0389 | 0.0504 | 8 | 5 / 3 | -0.1987 |
| GEOFON | M≥7 | +0.2941 | 0.0479 | 46 | 9 / 37 | -0.2769 |
| STEAD | M≥5 | -0.0610 | 0.0150 | 456 | 258 / 198 | -0.2240 |

Pooled tail Δ: fixed -0.0346 [-0.0611, -0.0080]; random +0.0053 [-0.1715, +0.1821]; HKSJ [-0.3215, +0.3322]; τ = 0.1725, Q p = 1.2e-11
Pooled bulk Δ: random -0.2382 [-0.2725, -0.2040]
Clusters favouring the arm: 281 of 521 (sign test p = 0.0796)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1981 | 0.0769 | 11 | 9 / 2 | -0.6915 |
| Chile | M≥6 | -0.1166 | 0.0753 | 8 | 6 / 2 | -0.2184 |
| GEOFON | M≥7 | +0.2548 | 0.0503 | 46 | 11 / 35 | -0.2491 |
| STEAD | M≥5 | -0.0511 | 0.0156 | 456 | 264 / 192 | -0.2185 |

Pooled tail Δ: fixed -0.0337 [-0.0619, -0.0056]; random -0.0217 [-0.1951, +0.1516]; HKSJ [-0.3358, +0.2923]; τ = 0.1670, Q p = 1.1e-08
Pooled bulk Δ: random -0.2299 [-0.2491, -0.2107]
Clusters favouring the arm: 290 of 521 (sign test p = 0.011)


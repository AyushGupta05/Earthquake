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

Pooled tail Δ: fixed +0.2290 [+0.1612, +0.2968]; random +0.1826 [-0.0856, +0.4507]; HKSJ [-0.4448, +0.8099]; τ = 0.2258, Q p = 1.45e-06
Pooled bulk Δ: random -0.3262 [-0.4584, -0.1940]
Clusters favouring the arm: 12 of 65 (sign test p = 2.79e-07)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1932 | 0.0825 | 11 | 9 / 2 | -0.7216 |
| Chile | M≥6 | -0.0389 | 0.0504 | 8 | 5 / 3 | -0.1987 |
| GEOFON | M≥7 | +0.2941 | 0.0479 | 46 | 9 / 37 | -0.2769 |

Pooled tail Δ: fixed +0.0864 [+0.0237, +0.1492]; random +0.0259 [-0.2539, +0.3057]; HKSJ [-0.5922, +0.6440]; τ = 0.2395, Q p = 1.21e-08
Pooled bulk Δ: random -0.2646 [-0.3438, -0.1854]
Clusters favouring the arm: 23 of 65 (sign test p = 0.0248)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1981 | 0.0769 | 11 | 9 / 2 | -0.6915 |
| Chile | M≥6 | -0.1166 | 0.0753 | 8 | 6 / 2 | -0.2184 |
| GEOFON | M≥7 | +0.2548 | 0.0503 | 46 | 11 / 35 | -0.2491 |

Pooled tail Δ: fixed +0.0628 [-0.0092, +0.1348]; random -0.0157 [-0.3170, +0.2857]; HKSJ [-0.6196, +0.5883]; τ = 0.2574, Q p = 1.26e-07
Pooled bulk Δ: random -0.2418 [-0.2810, -0.2026]
Clusters favouring the arm: 26 of 65 (sign test p = 0.136)


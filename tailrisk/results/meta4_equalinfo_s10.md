# Pooled cross-catalogue comparison: `eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10:mixdgr_nll_condR_s10+mixdgr_nll_s2_condR_s10+mixdgr_nll_s3_condR_s10` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1322 | 0.0696 | 11 | 7 / 4 | +0.0002 |
| Chile | M≥6 | -0.0490 | 0.0472 | 8 | 6 / 2 | -0.0004 |
| GEOFON | M≥7 | +0.0005 | 0.0110 | 46 | 22 / 24 | +0.0054 |
| STEAD | M≥5 | -0.0502 | 0.0105 | 456 | 276 / 180 | +0.0001 |

Pooled tail Δ: fixed -0.0279 [-0.0425, -0.0133]; random -0.0369 [-0.0797, +0.0058]; HKSJ [-0.1046, +0.0307]; τ = 0.0333, Q p = 0.00346
Pooled bulk Δ: random +0.0002 [-0.0005, +0.0010]
Clusters favouring the arm: 311 of 521 (sign test p = 1.11e-05)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1659 | 0.0768 | 11 | 9 / 2 | -0.0001 |
| Chile | M≥6 | -0.2297 | 0.0482 | 8 | 8 / 0 | -0.0009 |
| GEOFON | M≥7 | -0.0241 | 0.0160 | 46 | 30 / 16 | +0.0026 |
| STEAD | M≥5 | -0.0864 | 0.0096 | 456 | 320 / 136 | -0.0008 |

Pooled tail Δ: fixed -0.0754 [-0.0913, -0.0596]; random -0.1045 [-0.1690, -0.0400]; HKSJ [-0.2453, +0.0362]; τ = 0.0550, Q p = 3.71e-05
Pooled bulk Δ: random -0.0006 [-0.0011, -0.0001]
Clusters favouring the arm: 367 of 521 (sign test p = 4.39e-21)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1649 | 0.0698 | 11 | 11 / 0 | +0.0005 |
| Chile | M≥6 | -0.3105 | 0.0612 | 8 | 8 / 0 | -0.0015 |
| GEOFON | M≥7 | -0.0569 | 0.0196 | 46 | 33 / 13 | +0.0019 |
| STEAD | M≥5 | -0.1018 | 0.0096 | 456 | 324 / 132 | -0.0009 |

Pooled tail Δ: fixed -0.0983 [-0.1150, -0.0817]; random -0.1300 [-0.1949, -0.0652]; HKSJ [-0.2900, +0.0299]; τ = 0.0540, Q p = 0.000551
Pooled bulk Δ: random -0.0008 [-0.0017, -0.0000]
Clusters favouring the arm: 376 of 521 (sign test p = 1.17e-24)


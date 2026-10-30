# Pooled cross-catalogue comparison: `eqgr_nll+eqgr_nll_s2+eqgr_nll_s3:mix_nll+mix_nll_s2+mix_nll_s3` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.0276 | 0.0355 | 11 | 6 / 5 | -0.0006 |
| Chile | M≥6 | +0.0634 | 0.0682 | 8 | 3 / 5 | +0.0007 |
| GEOFON | M≥7 | +0.0501 | 0.0131 | 46 | 10 / 36 | +0.0097 |
| STEAD | M≥5 | -0.0096 | 0.0081 | 456 | 235 / 221 | +0.0012 |

Pooled tail Δ: fixed +0.0063 [-0.0068, +0.0195]; random +0.0137 [-0.0314, +0.0587]; HKSJ [-0.0504, +0.0777]; τ = 0.0370, Q p = 0.000807
Pooled bulk Δ: random +0.0012 [-0.0001, +0.0025]
Clusters favouring the arm: 254 of 521 (sign test p = 0.599)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1152 | 0.0774 | 11 | 7 / 4 | -0.0012 |
| Chile | M≥6 | -0.2445 | 0.0840 | 8 | 7 / 1 | +0.0000 |
| GEOFON | M≥7 | +0.0085 | 0.0149 | 46 | 19 / 27 | +0.0092 |
| STEAD | M≥5 | -0.0557 | 0.0079 | 456 | 276 / 180 | -0.0000 |

Pooled tail Δ: fixed -0.0437 [-0.0572, -0.0302]; random -0.0583 [-0.1199, +0.0034]; HKSJ [-0.1969, +0.0803]; τ = 0.0490, Q p = 9.9e-05
Pooled bulk Δ: random +0.0006 [-0.0009, +0.0022]
Clusters favouring the arm: 309 of 521 (sign test p = 2.47e-05)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1617 | 0.0964 | 11 | 10 / 1 | -0.0026 |
| Chile | M≥6 | -0.3760 | 0.0762 | 8 | 7 / 1 | -0.0012 |
| GEOFON | M≥7 | -0.0058 | 0.0185 | 46 | 20 / 26 | +0.0081 |
| STEAD | M≥5 | -0.0690 | 0.0092 | 456 | 293 / 163 | -0.0001 |

Pooled tail Δ: fixed -0.0608 [-0.0769, -0.0448]; random -0.1104 [-0.1931, -0.0276]; HKSJ [-0.3467, +0.1259]; τ = 0.0695, Q p = 3.93e-06
Pooled bulk Δ: random -0.0002 [-0.0020, +0.0016]
Clusters favouring the arm: 330 of 521 (sign test p = 1.19e-09)


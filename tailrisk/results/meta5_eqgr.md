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
| CWA | M≥5 | +0.0134 | 0.0011 | 103 | 17 / 86 | +0.0031 |

Pooled tail Δ: fixed +0.0132 [+0.0111, +0.0154]; random +0.0133 [-0.0078, +0.0345]; HKSJ [-0.0224, +0.0491]; τ = 0.0179, Q p = 0.00135
Pooled bulk Δ: random +0.0017 [+0.0004, +0.0030]
Clusters favouring the arm: 271 of 624 (sign test p = 0.00117)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1152 | 0.0774 | 11 | 7 / 4 | -0.0012 |
| Chile | M≥6 | -0.2445 | 0.0840 | 8 | 7 / 1 | +0.0000 |
| GEOFON | M≥7 | +0.0085 | 0.0149 | 46 | 19 / 27 | +0.0092 |
| STEAD | M≥5 | -0.0557 | 0.0079 | 456 | 276 / 180 | -0.0000 |
| CWA | M≥5 | +0.0127 | 0.0020 | 103 | 21 / 82 | +0.0027 |

Pooled tail Δ: fixed +0.0085 [+0.0048, +0.0122]; random -0.0349 [-0.0829, +0.0131]; HKSJ [-0.1301, +0.0603]; τ = 0.0448, Q p = 4.05e-17
Pooled bulk Δ: random +0.0013 [-0.0004, +0.0030]
Clusters favouring the arm: 330 of 624 (sign test p = 0.161)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1617 | 0.0964 | 11 | 10 / 1 | -0.0026 |
| Chile | M≥6 | -0.3760 | 0.0762 | 8 | 7 / 1 | -0.0012 |
| GEOFON | M≥7 | -0.0058 | 0.0185 | 46 | 20 / 26 | +0.0081 |
| STEAD | M≥5 | -0.0690 | 0.0092 | 456 | 293 / 163 | -0.0001 |
| CWA | M≥5 | +0.0110 | 0.0023 | 103 | 25 / 78 | +0.0021 |

Pooled tail Δ: fixed +0.0059 [+0.0016, +0.0102]; random -0.0692 [-0.1301, -0.0084]; HKSJ [-0.2299, +0.0914]; τ = 0.0583, Q p = 1.39e-20
Pooled bulk Δ: random +0.0004 [-0.0012, +0.0021]
Clusters favouring the arm: 355 of 624 (sign test p = 0.000655)


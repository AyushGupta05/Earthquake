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

Pooled tail Δ: fixed +0.0416 [+0.0179, +0.0652]; random +0.0273 [-0.0286, +0.0833]; HKSJ [-0.0872, +0.1419]; τ = 0.0363, Q p = 0.114
Pooled bulk Δ: random +0.0022 [-0.0009, +0.0052]
Clusters favouring the arm: 19 of 65 (sign test p = 0.00109)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1152 | 0.0774 | 11 | 7 / 4 | -0.0012 |
| Chile | M≥6 | -0.2445 | 0.0840 | 8 | 7 / 1 | +0.0000 |
| GEOFON | M≥7 | +0.0085 | 0.0149 | 46 | 19 / 27 | +0.0092 |

Pooled tail Δ: fixed -0.0033 [-0.0316, +0.0250]; random -0.1012 [-0.2579, +0.0555]; HKSJ [-0.4189, +0.2166]; τ = 0.1235, Q p = 0.00416
Pooled bulk Δ: random +0.0021 [-0.0020, +0.0062]
Clusters favouring the arm: 33 of 65 (sign test p = 1)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1617 | 0.0964 | 11 | 10 / 1 | -0.0026 |
| Chile | M≥6 | -0.3760 | 0.0762 | 8 | 7 / 1 | -0.0012 |
| GEOFON | M≥7 | -0.0058 | 0.0185 | 46 | 20 / 26 | +0.0081 |

Pooled tail Δ: fixed -0.0310 [-0.0656, +0.0036]; random -0.1743 [-0.4206, +0.0720]; HKSJ [-0.6438, +0.2951]; τ = 0.2062, Q p = 5.53e-06
Pooled bulk Δ: random +0.0006 [-0.0030, +0.0041]
Clusters favouring the arm: 37 of 65 (sign test p = 0.321)


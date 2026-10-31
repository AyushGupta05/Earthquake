# Pooled cross-catalogue comparison: `eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR:mixdgr_nll_condR+mixdgr_nll_s2_condR+mixdgr_nll_s3_condR` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1243 | 0.0640 | 11 | 6 / 5 | +0.0007 |
| Chile | M≥6 | +0.0043 | 0.0567 | 8 | 5 / 3 | -0.0005 |
| GEOFON | M≥7 | +0.0162 | 0.0098 | 46 | 20 / 26 | +0.0055 |
| STEAD | M≥5 | -0.0273 | 0.0099 | 456 | 257 / 199 | +0.0001 |
| CWA | M≥5 | +0.0169 | 0.0025 | 103 | 19 / 84 | +0.0033 |

Pooled tail Δ: fixed +0.0142 [+0.0096, +0.0188]; random -0.0019 [-0.0277, +0.0239]; HKSJ [-0.0450, +0.0412]; τ = 0.0224, Q p = 0.000103
Pooled bulk Δ: random +0.0014 [+0.0000, +0.0028]
Clusters favouring the arm: 307 of 624 (sign test p = 0.719)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1564 | 0.0670 | 11 | 9 / 2 | +0.0007 |
| Chile | M≥6 | -0.1965 | 0.0345 | 8 | 8 / 0 | -0.0010 |
| GEOFON | M≥7 | -0.0102 | 0.0160 | 46 | 27 / 19 | +0.0025 |
| STEAD | M≥5 | -0.0678 | 0.0095 | 456 | 296 / 160 | -0.0008 |
| CWA | M≥5 | +0.0088 | 0.0017 | 103 | 29 / 74 | +0.0024 |

Pooled tail Δ: fixed +0.0058 [+0.0026, +0.0090]; random -0.0681 [-0.1235, -0.0127]; HKSJ [-0.1758, +0.0395]; τ = 0.0569, Q p = 9.03e-22
Pooled bulk Δ: random +0.0006 [-0.0009, +0.0021]
Clusters favouring the arm: 369 of 624 (sign test p = 5.75e-06)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1603 | 0.0630 | 11 | 9 / 2 | +0.0009 |
| Chile | M≥6 | -0.2694 | 0.0481 | 8 | 8 / 0 | -0.0015 |
| GEOFON | M≥7 | -0.0442 | 0.0188 | 46 | 32 / 14 | +0.0014 |
| STEAD | M≥5 | -0.0828 | 0.0094 | 456 | 326 / 130 | -0.0008 |
| CWA | M≥5 | +0.0054 | 0.0015 | 103 | 35 / 68 | +0.0020 |

Pooled tail Δ: fixed +0.0025 [-0.0005, +0.0054]; random -0.0924 [-0.1567, -0.0281]; HKSJ [-0.2204, +0.0356]; τ = 0.0663, Q p = 3.01e-27
Pooled bulk Δ: random +0.0003 [-0.0015, +0.0022]
Clusters favouring the arm: 410 of 624 (sign test p = 3.52e-15)


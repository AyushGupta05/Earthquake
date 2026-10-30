# Pooled cross-catalogue comparison: `eqdgr_nll_condR+eqdgr_nll_s2_condR+eqdgr_nll_s3_condR:mix_nll+mix_nll_s2+mix_nll_s3` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2375 | 0.1273 | 11 | 9 / 2 | -0.0952 |
| Chile | M≥6 | +0.0307 | 0.0508 | 8 | 4 / 4 | -0.0250 |
| GEOFON | M≥7 | -0.1677 | 0.0267 | 46 | 40 / 6 | -0.0894 |

Pooled tail Δ: fixed -0.1285 [-0.1740, -0.0830]; random -0.1085 [-0.2678, +0.0509]; HKSJ [-0.4444, +0.2274]; τ = 0.1231, Q p = 0.00173
Pooled bulk Δ: random -0.0695 [-0.1214, -0.0177]
Clusters favouring the arm: 53 of 65 (sign test p = 2.79e-07)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2587 | 0.1250 | 11 | 9 / 2 | -0.0821 |
| Chile | M≥6 | -0.2755 | 0.0465 | 8 | 7 / 1 | -0.0270 |
| GEOFON | M≥7 | -0.1360 | 0.0283 | 46 | 39 / 7 | -0.0931 |

Pooled tail Δ: fixed -0.1767 [-0.2231, -0.1302]; random -0.2087 [-0.3222, -0.0952]; HKSJ [-0.4138, -0.0036]; τ = 0.0805, Q p = 0.03
Pooled bulk Δ: random -0.0666 [-0.1183, -0.0149]
Clusters favouring the arm: 55 of 65 (sign test p = 1.18e-08)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2810 | 0.1310 | 11 | 9 / 2 | -0.0648 |
| Chile | M≥6 | -0.3860 | 0.0508 | 8 | 8 / 0 | -0.0325 |
| GEOFON | M≥7 | -0.1656 | 0.0221 | 46 | 38 / 8 | -0.0966 |

Pooled tail Δ: fixed -0.2026 [-0.2419, -0.1633]; random -0.2725 [-0.4473, -0.0978]; HKSJ [-0.5685, +0.0234]; τ = 0.1375, Q p = 0.000309
Pooled bulk Δ: random -0.0644 [-0.1151, -0.0137]
Clusters favouring the arm: 55 of 65 (sign test p = 1.18e-08)


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
| STEAD | M≥5 | -0.1319 | 0.0170 | 456 | 300 / 156 | -0.0411 |
| CWA | M≥5 | -0.3109 | 0.0367 | 103 | 96 / 7 | -0.1224 |

Pooled tail Δ: fixed -0.1528 [-0.1779, -0.1276]; random -0.1575 [-0.2482, -0.0669]; HKSJ [-0.3160, +0.0009]; τ = 0.0906, Q p = 7.68e-07
Pooled bulk Δ: random -0.0734 [-0.1019, -0.0448]
Clusters favouring the arm: 449 of 624 (sign test p = 1.06e-28)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2587 | 0.1250 | 11 | 9 / 2 | -0.0821 |
| Chile | M≥6 | -0.2755 | 0.0465 | 8 | 7 / 1 | -0.0270 |
| GEOFON | M≥7 | -0.1360 | 0.0283 | 46 | 39 / 7 | -0.0931 |
| STEAD | M≥5 | -0.1709 | 0.0141 | 456 | 327 / 129 | -0.0305 |
| CWA | M≥5 | -0.2737 | 0.0291 | 103 | 100 / 3 | -0.1152 |

Pooled tail Δ: fixed -0.1873 [-0.2093, -0.1654]; random -0.2102 [-0.2699, -0.1504]; HKSJ [-0.2938, -0.1265]; τ = 0.0550, Q p = 0.00164
Pooled bulk Δ: random -0.0674 [-0.0923, -0.0425]
Clusters favouring the arm: 482 of 624 (sign test p = 3.4e-44)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2810 | 0.1310 | 11 | 9 / 2 | -0.0648 |
| Chile | M≥6 | -0.3860 | 0.0508 | 8 | 8 / 0 | -0.0325 |
| GEOFON | M≥7 | -0.1656 | 0.0221 | 46 | 38 / 8 | -0.0966 |
| STEAD | M≥5 | -0.1907 | 0.0141 | 456 | 343 / 113 | -0.0211 |
| CWA | M≥5 | -0.2661 | 0.0278 | 103 | 101 / 2 | -0.1100 |

Pooled tail Δ: fixed -0.2051 [-0.2259, -0.1843]; random -0.2399 [-0.3024, -0.1774]; HKSJ [-0.3471, -0.1327]; τ = 0.0585, Q p = 0.000197
Pooled bulk Δ: random -0.0640 [-0.0925, -0.0355]
Clusters favouring the arm: 499 of 624 (sign test p = 8.18e-54)


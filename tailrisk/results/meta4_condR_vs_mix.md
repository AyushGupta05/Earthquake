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

Pooled tail Δ: fixed -0.1307 [-0.1575, -0.1039]; random -0.1138 [-0.1882, -0.0393]; HKSJ [-0.2677, +0.0402]; τ = 0.0604, Q p = 0.00525
Pooled bulk Δ: random -0.0618 [-0.0891, -0.0344]
Clusters favouring the arm: 353 of 521 (sign test p = 3.71e-16)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2587 | 0.1250 | 11 | 9 / 2 | -0.0821 |
| Chile | M≥6 | -0.2755 | 0.0465 | 8 | 7 / 1 | -0.0270 |
| GEOFON | M≥7 | -0.1360 | 0.0283 | 46 | 39 / 7 | -0.0931 |
| STEAD | M≥5 | -0.1709 | 0.0141 | 456 | 327 / 129 | -0.0305 |

Pooled tail Δ: fixed -0.1724 [-0.1961, -0.1486]; random -0.1842 [-0.2367, -0.1317]; HKSJ [-0.2799, -0.0884]; τ = 0.0379, Q p = 0.07
Pooled bulk Δ: random -0.0547 [-0.0767, -0.0326]
Clusters favouring the arm: 382 of 521 (sign test p = 3.17e-27)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2810 | 0.1310 | 11 | 9 / 2 | -0.0648 |
| Chile | M≥6 | -0.3860 | 0.0508 | 8 | 8 / 0 | -0.0325 |
| GEOFON | M≥7 | -0.1656 | 0.0221 | 46 | 38 / 8 | -0.0966 |
| STEAD | M≥5 | -0.1907 | 0.0141 | 456 | 343 / 113 | -0.0211 |

Pooled tail Δ: fixed -0.1947 [-0.2172, -0.1721]; random -0.2328 [-0.3070, -0.1585]; HKSJ [-0.3936, -0.0719]; τ = 0.0612, Q p = 0.000938
Pooled bulk Δ: random -0.0516 [-0.0779, -0.0253]
Clusters favouring the arm: 398 of 521 (sign test p = 7.91e-35)


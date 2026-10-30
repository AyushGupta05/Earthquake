# Pooled cross-catalogue comparison: `eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10:mix_nll+mix_nll_s2+mix_nll_s3` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2145 | 0.1241 | 11 | 9 / 2 | -0.0901 |
| Chile | M≥6 | +0.0121 | 0.0389 | 8 | 4 / 4 | -0.0186 |
| GEOFON | M≥7 | -0.1841 | 0.0264 | 46 | 41 / 5 | -0.0865 |
| STEAD | M≥5 | -0.1260 | 0.0143 | 456 | 309 / 147 | -0.0371 |

Pooled tail Δ: fixed -0.1257 [-0.1491, -0.1024]; random -0.1142 [-0.1931, -0.0353]; HKSJ [-0.2641, +0.0357]; τ = 0.0673, Q p = 0.000441
Pooled bulk Δ: random -0.0574 [-0.0865, -0.0283]
Clusters favouring the arm: 363 of 521 (sign test p = 1.34e-19)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2419 | 0.1198 | 11 | 9 / 2 | -0.0756 |
| Chile | M≥6 | -0.2754 | 0.0504 | 8 | 8 / 0 | -0.0190 |
| GEOFON | M≥7 | -0.1470 | 0.0272 | 46 | 39 / 7 | -0.0911 |
| STEAD | M≥5 | -0.1630 | 0.0116 | 456 | 346 / 110 | -0.0262 |

Pooled tail Δ: fixed -0.1660 [-0.1864, -0.1456]; random -0.1773 [-0.2215, -0.1332]; HKSJ [-0.2587, -0.0959]; τ = 0.0296, Q p = 0.129
Pooled bulk Δ: random -0.0497 [-0.0713, -0.0281]
Clusters favouring the arm: 402 of 521 (sign test p = 6.58e-37)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2714 | 0.1248 | 11 | 10 / 1 | -0.0588 |
| Chile | M≥6 | -0.3891 | 0.0588 | 8 | 8 / 0 | -0.0222 |
| GEOFON | M≥7 | -0.1749 | 0.0215 | 46 | 40 / 6 | -0.0942 |
| STEAD | M≥5 | -0.1819 | 0.0120 | 456 | 356 / 100 | -0.0175 |

Pooled tail Δ: fixed -0.1873 [-0.2074, -0.1671]; random -0.2219 [-0.2862, -0.1577]; HKSJ [-0.3711, -0.0727]; τ = 0.0503, Q p = 0.00518
Pooled bulk Δ: random -0.0461 [-0.0717, -0.0204]
Clusters favouring the arm: 414 of 521 (sign test p = 1.32e-43)


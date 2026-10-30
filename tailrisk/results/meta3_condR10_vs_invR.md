# Pooled cross-catalogue comparison: `eqdgr_nll_condR_s10+eqdgr_nll_s2_condR_s10+eqdgr_nll_s3_condR_s10:lin_invR` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.0339 | 0.1031 | 11 | 7 / 4 | -0.7488 |
| Chile | M≥6 | +0.1103 | 0.0353 | 8 | 2 / 6 | -0.1925 |
| GEOFON | M≥7 | +0.4303 | 0.0580 | 46 | 6 / 40 | -0.3356 |

Pooled tail Δ: fixed +0.1786 [+0.1218, +0.2353]; random +0.1773 [-0.0708, +0.4255]; HKSJ [-0.4066, +0.7612]; τ = 0.2081, Q p = 1.51e-06
Pooled bulk Δ: random -0.3226 [-0.4578, -0.1874]
Clusters favouring the arm: 15 of 65 (sign test p = 1.57e-05)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1763 | 0.0923 | 11 | 8 / 3 | -0.7151 |
| Chile | M≥6 | -0.0388 | 0.0358 | 8 | 5 / 3 | -0.1907 |
| GEOFON | M≥7 | +0.2831 | 0.0493 | 46 | 11 / 35 | -0.2749 |

Pooled tail Δ: fixed +0.0501 [-0.0041, +0.1043]; random +0.0298 [-0.2235, +0.2830]; HKSJ [-0.5527, +0.6122]; τ = 0.2149, Q p = 3.21e-08
Pooled bulk Δ: random -0.2622 [-0.3466, -0.1779]
Clusters favouring the arm: 24 of 65 (sign test p = 0.0464)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1886 | 0.0889 | 11 | 8 / 3 | -0.6855 |
| Chile | M≥6 | -0.1197 | 0.0581 | 8 | 6 / 2 | -0.2081 |
| GEOFON | M≥7 | +0.2455 | 0.0519 | 46 | 12 / 34 | -0.2467 |

Pooled tail Δ: fixed +0.0401 [-0.0294, +0.1096]; random -0.0159 [-0.2964, +0.2646]; HKSJ [-0.5980, +0.5661]; τ = 0.2385, Q p = 3.23e-07
Pooled bulk Δ: random -0.2380 [-0.2834, -0.1926]
Clusters favouring the arm: 26 of 65 (sign test p = 0.136)


# Pooled cross-catalogue comparison: `eqdgr_nll+eqdgr_nll_s2+eqdgr_nll_s3:mix_nll+mix_nll_s2+mix_nll_s3` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1354 | 0.1122 | 11 | 6 / 5 | -0.0006 |
| Chile | M≥6 | -0.0117 | 0.0509 | 8 | 5 / 3 | -0.0025 |
| GEOFON | M≥7 | -0.0946 | 0.0215 | 46 | 35 / 11 | +0.0242 |

Pooled tail Δ: fixed -0.0837 [-0.1219, -0.0455]; random -0.0774 [-0.1311, -0.0237]; HKSJ [-0.1920, +0.0371]; τ = 0.0245, Q p = 0.291
Pooled bulk Δ: random +0.0051 [-0.0011, +0.0113]
Clusters favouring the arm: 46 of 65 (sign test p = 0.00109)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1893 | 0.1153 | 11 | 7 / 4 | -0.0029 |
| Chile | M≥6 | -0.2717 | 0.0599 | 8 | 8 / 0 | -0.0042 |
| GEOFON | M≥7 | -0.0881 | 0.0251 | 46 | 33 / 13 | +0.0171 |

Pooled tail Δ: fixed -0.1184 [-0.1629, -0.0739]; random -0.1734 [-0.3116, -0.0351]; HKSJ [-0.4215, +0.0747]; τ = 0.1031, Q p = 0.0152
Pooled bulk Δ: random +0.0023 [-0.0039, +0.0084]
Clusters favouring the arm: 48 of 65 (sign test p = 0.000152)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2064 | 0.1272 | 11 | 8 / 3 | -0.0044 |
| Chile | M≥6 | -0.3829 | 0.0737 | 8 | 8 / 0 | -0.0057 |
| GEOFON | M≥7 | -0.1229 | 0.0233 | 46 | 39 / 7 | +0.0158 |

Pooled tail Δ: fixed -0.1482 [-0.1910, -0.1054]; random -0.2317 [-0.4192, -0.0442]; HKSJ [-0.5769, +0.1134]; τ = 0.1464, Q p = 0.00311
Pooled bulk Δ: random +0.0010 [-0.0057, +0.0078]
Clusters favouring the arm: 55 of 65 (sign test p = 1.18e-08)


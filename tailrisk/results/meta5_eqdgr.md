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
| STEAD | M≥5 | -0.0453 | 0.0122 | 456 | 265 / 191 | +0.0024 |
| CWA | M≥5 | +0.0203 | 0.0028 | 103 | 21 / 82 | +0.0043 |

Pooled tail Δ: fixed +0.0151 [+0.0099, +0.0204]; random -0.0386 [-0.0952, +0.0180]; HKSJ [-0.1062, +0.0290]; τ = 0.0543, Q p = 1.93e-11
Pooled bulk Δ: random +0.0039 [+0.0001, +0.0077]
Clusters favouring the arm: 332 of 624 (sign test p = 0.118)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1893 | 0.1153 | 11 | 7 / 4 | -0.0029 |
| Chile | M≥6 | -0.2717 | 0.0599 | 8 | 8 / 0 | -0.0042 |
| GEOFON | M≥7 | -0.0881 | 0.0251 | 46 | 33 / 13 | +0.0171 |
| STEAD | M≥5 | -0.0838 | 0.0113 | 456 | 303 / 153 | +0.0004 |
| CWA | M≥5 | +0.0209 | 0.0032 | 103 | 18 / 85 | +0.0023 |

Pooled tail Δ: fixed +0.0110 [+0.0051, +0.0169]; random -0.0980 [-0.1782, -0.0177]; HKSJ [-0.2330, +0.0371]; τ = 0.0804, Q p = 3.73e-25
Pooled bulk Δ: random +0.0016 [-0.0021, +0.0052]
Clusters favouring the arm: 369 of 624 (sign test p = 5.75e-06)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2064 | 0.1272 | 11 | 8 / 3 | -0.0044 |
| Chile | M≥6 | -0.3829 | 0.0737 | 8 | 8 / 0 | -0.0057 |
| GEOFON | M≥7 | -0.1229 | 0.0233 | 46 | 39 / 7 | +0.0158 |
| STEAD | M≥5 | -0.1056 | 0.0123 | 456 | 304 / 152 | +0.0000 |
| CWA | M≥5 | +0.0196 | 0.0034 | 103 | 26 / 77 | +0.0004 |

Pooled tail Δ: fixed +0.0071 [+0.0007, +0.0134]; random -0.1326 [-0.2295, -0.0357]; HKSJ [-0.3122, +0.0471]; τ = 0.0982, Q p = 1.49e-33
Pooled bulk Δ: random +0.0004 [-0.0036, +0.0044]
Clusters favouring the arm: 385 of 624 (sign test p = 5.53e-09)


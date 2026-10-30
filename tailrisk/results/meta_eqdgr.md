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

Pooled tail Δ: fixed -0.0561 [-0.0764, -0.0358]; random -0.0613 [-0.0985, -0.0240]; HKSJ [-0.1180, -0.0045]; τ = 0.0238, Q p = 0.154
Pooled bulk Δ: random +0.0038 [-0.0005, +0.0081]
Clusters favouring the arm: 311 of 521 (sign test p = 1.11e-05)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1893 | 0.1153 | 11 | 7 / 4 | -0.0029 |
| Chile | M≥6 | -0.2717 | 0.0599 | 8 | 8 / 0 | -0.0042 |
| GEOFON | M≥7 | -0.0881 | 0.0251 | 46 | 33 / 13 | +0.0171 |
| STEAD | M≥5 | -0.0838 | 0.0113 | 456 | 303 / 153 | +0.0004 |

Pooled tail Δ: fixed -0.0906 [-0.1105, -0.0708]; random -0.1241 [-0.1859, -0.0622]; HKSJ [-0.2555, +0.0074]; τ = 0.0474, Q p = 0.0167
Pooled bulk Δ: random +0.0014 [-0.0028, +0.0055]
Clusters favouring the arm: 351 of 521 (sign test p = 1.63e-15)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.2064 | 0.1272 | 11 | 8 / 3 | -0.0044 |
| Chile | M≥6 | -0.3829 | 0.0737 | 8 | 8 / 0 | -0.0057 |
| GEOFON | M≥7 | -0.1229 | 0.0233 | 46 | 39 / 7 | +0.0158 |
| STEAD | M≥5 | -0.1056 | 0.0123 | 456 | 304 / 152 | +0.0000 |

Pooled tail Δ: fixed -0.1158 [-0.1368, -0.0949]; random -0.1646 [-0.2393, -0.0899]; HKSJ [-0.3477, +0.0185]; τ = 0.0589, Q p = 0.00237
Pooled bulk Δ: random +0.0006 [-0.0043, +0.0054]
Clusters favouring the arm: 359 of 521 (sign test p = 3.55e-18)


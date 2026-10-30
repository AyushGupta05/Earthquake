# Pooled cross-catalogue comparison: `mixdgr_nll_condR+mixdgr_nll_s2_condR+mixdgr_nll_s3_condR:mix_nll+mix_nll_s2+mix_nll_s3` (median action)

Δ = arm − reference at each catalogue's primary threshold; SE = delete-one-cluster jackknife.
Pooled: fixed effect, DerSimonian–Laird random effects (normal), HKSJ (t, k − 1 df). Sign test over
all tail-carrying clusters.

## 1s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1132 | 0.0697 | 11 | 10 / 1 | -0.0960 |
| Chile | M≥6 | +0.0264 | 0.0342 | 8 | 4 / 4 | -0.0245 |
| GEOFON | M≥7 | -0.1839 | 0.0242 | 46 | 42 / 4 | -0.0950 |
| STEAD | M≥5 | -0.1046 | 0.0133 | 456 | 302 / 154 | -0.0413 |

Pooled tail Δ: fixed -0.1075 [-0.1288, -0.0862]; random -0.0948 [-0.1746, -0.0149]; HKSJ [-0.2378, +0.0482]; τ = 0.0730, Q p = 1.31e-05
Pooled bulk Δ: random -0.0631 [-0.0910, -0.0353]
Clusters favouring the arm: 358 of 521 (sign test p = 7.88e-18)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1023 | 0.0703 | 11 | 10 / 1 | -0.0828 |
| Chile | M≥6 | -0.0790 | 0.0361 | 8 | 6 / 2 | -0.0260 |
| GEOFON | M≥7 | -0.1258 | 0.0220 | 46 | 39 / 7 | -0.0957 |
| STEAD | M≥5 | -0.1031 | 0.0127 | 456 | 303 / 153 | -0.0297 |

Pooled tail Δ: fixed -0.1062 [-0.1266, -0.0857]; random -0.1062 [-0.1266, -0.0857]; HKSJ [-0.1290, -0.0833]; τ = 0.0000, Q p = 0.699
Pooled bulk Δ: random -0.0551 [-0.0774, -0.0327]
Clusters favouring the arm: 358 of 521 (sign test p = 7.88e-18)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1207 | 0.0760 | 11 | 9 / 2 | -0.0657 |
| Chile | M≥6 | -0.1166 | 0.0403 | 8 | 5 / 3 | -0.0310 |
| GEOFON | M≥7 | -0.1214 | 0.0225 | 46 | 39 / 7 | -0.0980 |
| STEAD | M≥5 | -0.1079 | 0.0127 | 456 | 311 / 145 | -0.0203 |

Pooled tail Δ: fixed -0.1118 [-0.1325, -0.0910]; random -0.1118 [-0.1325, -0.0910]; HKSJ [-0.1224, -0.1011]; τ = 0.0000, Q p = 0.96
Pooled bulk Δ: random -0.0513 [-0.0768, -0.0259]
Clusters favouring the arm: 364 of 521 (sign test p = 5.79e-20)


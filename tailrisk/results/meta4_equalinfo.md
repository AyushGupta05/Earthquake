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

Pooled tail Δ: fixed -0.0065 [-0.0200, +0.0070]; random -0.0144 [-0.0543, +0.0255]; HKSJ [-0.0851, +0.0564]; τ = 0.0303, Q p = 0.00422
Pooled bulk Δ: random +0.0005 [-0.0005, +0.0014]
Clusters favouring the arm: 288 of 521 (sign test p = 0.0179)

## 3s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1564 | 0.0670 | 11 | 9 / 2 | +0.0007 |
| Chile | M≥6 | -0.1965 | 0.0345 | 8 | 8 / 0 | -0.0010 |
| GEOFON | M≥7 | -0.0102 | 0.0160 | 46 | 27 / 19 | +0.0025 |
| STEAD | M≥5 | -0.0678 | 0.0095 | 456 | 296 / 160 | -0.0008 |

Pooled tail Δ: fixed -0.0617 [-0.0772, -0.0463]; random -0.0937 [-0.1588, -0.0287]; HKSJ [-0.2290, +0.0415]; τ = 0.0582, Q p = 3.43e-06
Pooled bulk Δ: random -0.0004 [-0.0011, +0.0002]
Clusters favouring the arm: 340 of 521 (sign test p = 3.04e-12)

## 5s

| catalogue | threshold | Δ tail MAE | jackknife SE | clusters | Δ<0 / Δ>0 | Δ bulk MAE |
|---|---|---|---|---|---|---|
| INSTANCE | M≥5 | -0.1603 | 0.0630 | 11 | 9 / 2 | +0.0009 |
| Chile | M≥6 | -0.2694 | 0.0481 | 8 | 8 / 0 | -0.0015 |
| GEOFON | M≥7 | -0.0442 | 0.0188 | 46 | 32 / 14 | +0.0014 |
| STEAD | M≥5 | -0.0828 | 0.0094 | 456 | 326 / 130 | -0.0008 |

Pooled tail Δ: fixed -0.0822 [-0.0983, -0.0661]; random -0.1199 [-0.1846, -0.0552]; HKSJ [-0.2731, +0.0333]; τ = 0.0561, Q p = 0.000118
Pooled bulk Δ: random -0.0007 [-0.0016, +0.0002]
Clusters favouring the arm: 375 of 521 (sign test p = 3.03e-24)


# Findings log (newest first)

All numbers are pooled out-of-fold predictions over 1,159,249 INSTANCE records (346 M≥4
events, 31 M≥5) from 5 leave-sequence-out folds. Δ = arm − reference, with 95% cluster-bootstrap
intervals (1,000 replicates; whole GK sequences resampled). Negative Δ in an error is better.

## 2026-10-30 11:25 UTC — INSTANCE capped with three seeds: replicated (M ≥ 5 −.82 / −.99 / −1.04 against the capped mixture, 11 of 11 sequences; level with the full-data mixture). Correction: the truncation margin has a real tail cost on the plain head

Three-seed ensembles, trained below M4.0. Jackknife over 11 M ≥ 5 sequences / 194 M ≥ 4 clusters.

| Δ (1 / 3 / 5 s) | bulk MAE | M ≥ 4 MAE | M ≥ 5 MAE | false M4 per 10⁴ |
|---|---|---|---|---|
| `eqdgr_cap40_cond` ens − `mix_cap40` ens | −.002 / −.006 / −.008 | **−.24 / −.26 / −.28** | **−.82 / −.99 / −1.04** (11 / 11) | +10.5 / +6.4 / +4.6 |
| `eqgr_cap40` ens − `mix_cap40` ens | −.001 / −.003 / −.004 | **−.23 / −.26 / −.28** | **−.71 / −.95 / −1.04** (11 / 11) | +8.1 / +7.4 / +6.7 |
| `eqdgr_cap40_cond` ens − `mix_nll` ens (all magnitudes) | +.001 / −.002 / −.004 | +.024 / +.022 / +.007 | −.05 / −.13 / −.17 (n.s.) | +5.5 / +2.2 / +1.3 |
| `eqgr_cap40_m10` − `eqgr_cap40` (margin) | −.003 / −.003 / −.001 | +.035 / +.017 / +.011 | **+.19 / +.15 / +.12** (0–1 of 11 favour) | **−7.9 / −6.7 / −6.0** |

**Correction to the 09:15 entry, point 5.** The truncation margin removes the false-alarm cost on
both heads as predicted. On `eqgr` it also raises M ≥ 5 error by .12–.19, with intervals excluding
zero. On `eqdgr` (cond) the same margin cost +.05 to +.09, n.s. So the margin is a trade-off between
tail and false alarms, not a free fix. With it, `eqgr` capped is level with the full-data mixture at
3–5 s on M ≥ 5 (+.06 / −.03, n.s.) and has fewer false alarms, but it is no longer ahead of the
unmargined head on the tail. The remark in THEORY.md is qualified accordingly.

Files: `results/robust_instance_cap40_ens3.{json,md}`.

## 2026-10-30 11:15 UTC — Chile retrained on independent magnitudes (audit M1): the full-data tail gain survives only on M ≥ 6 (−.13 to −.20 at 3–5 s, significant on MW_SIPPL, n.s. on M_EXT); capped training still beats the capped mixture by a wide margin but only ties the full-data mixture

Chile's MA labels are amplitude-derived. The relabelled caches replace the large events' labels by
M_EXT (65 M ≥ 5 events / 29 clusters, 9 M ≥ 6 / 7) or MW_SIPPL (44 / 21; 6 / 5). Every arm is
retrained on them (seed 1; SageMaker), and tail records are restricted to events with an independent
label. Jackknife intervals; 1 / 3 / 5 s.

| Δ (seed 1) | M_EXT M ≥ 5 | M_EXT M ≥ 6 | MW_SIPPL M ≥ 5 | MW_SIPPL M ≥ 6 | bulk |
|---|---|---|---|---|---|
| `eqdgr_nll` − `mix_nll` | +.015 / +.015 / −.010 | −.009 / −.134 / −.195 (n.s.) | +.039 / −.011 / −.038 | +.018 / **−.204 / −.193** | −.002 to −.006 |
| `eqgr_nll` − `mix_nll` | +.082 / +.022 / +.002 | +.10 / −.13 / −.23 | +.088 / −.014 / −.038 | +.11 / −.22 / **−.23** | +.000 to +.002 |
| `eqdgr_cap50_cond` − `mix_cap50` | **−.15 / −.32 / −.36** | **−.27 / −.85 / −.94** | **−.18 / −.25 / −.28** | **−.58 / −.75 / −.72** | −.002 to −.006 |
| `eqdgr_cap50_cond` − `mix_nll` | +.15 / +.04 / +.005 | +.38 / −.09 / −.21 | +.11 / +.06 / +.04 | +.07 / −.09 / −.05 | −.001 to −.006 |

* **Full data:** on independent labels the distance-marginalized head's Chile tail advantage is
  confined to M ≥ 6 at 3–5 s. That is −.20 / −.19 on MW_SIPPL (5 of 5 and 4 of 5 clusters, intervals
  excluding zero) and −.13 / −.20 on M_EXT (n.s., 7 clusters). On MA labels the same comparison was
  −.27 / −.38 at M ≥ 6 and −.03 / −.09 at M ≥ 5. Its bulk advantage is unchanged.
* **Capped (M < 5):** against the identically capped mixture the gain holds fully on both labelings,
  with 20–29 of 21–29 clusters favouring the head on M ≥ 5. Against the free mixture trained on all
  magnitudes it is a tie: M ≥ 5 slightly worse (+.005 to +.06), M ≥ 6 slightly better at 3–5 s, n.s.
  The "three capped seeds beat three full-data seeds on M ≥ 6" result of the 11:10 entry is
  specific to the amplitude labels.
* This is the audit's point (05:10 entry) confirmed by retraining, not only rescoring. Part of the
  Chile tail result, both full-data and capped, comes from the label being an amplitude magnitude,
  which an amplitude-equivariant model fits by construction.

Files: `results/robust_chile_relabel_{mext,mwsippl}.{json,md}`,
`robust_chile_relabel_cap50_{mext,mwsippl}.{json,md}`.

## 2026-10-30 11:10 UTC — Chile capped (M < 5.0) rerun with the binning fix and the conditional truncation: the leak is gone, the head beats augmentation (M ≥ 6 −.36 / −.44 at 3 / 5 s, 8 of 8 clusters), and three seeds of the capped head beat three seeds of the free mixture trained on all magnitudes

Bin-consistent cap filter (`--cap-filter bin`, the 05:10 audit fix), suffix `b`. Median action,
1 / 3 / 5 s; jackknife over 28 M ≥ 5 / 8 M ≥ 6 clusters. MA (amplitude) labels; the relabelled
retraining on independent magnitudes is in `relabel_eval.sh`.

| trained below M5.0 (seed 1) | bulk MAE | M ≥ 5 MAE | M ≥ 6 MAE | top-bin bias |
|---|---|---|---|---|
| `mix_cap50b` | .208 / .165 / .149 | 1.179 / .975 / .946 | 2.001 / 1.666 / 1.648 | −2.00 / −1.67 / −1.65 |
| `mix_cap50b_aug15` | .223 / .174 / .157 | .968 / .657 / .593 | 1.691 / 1.061 / .983 | −1.69 / −1.06 / −.98 |
| `mixgr_cap50b` (prior swap only) | .209 / .166 / .150 | .998 / .783 / .767 | 1.741 / 1.389 / 1.392 | −1.74 / −1.39 / −1.39 |
| `eqgr_k1_cap50b` (κ ≡ 1) | .212 / .167 / .150 | .933 / .608 / .545 | 1.553 / .760 / .690 | −1.55 / −.74 / −.68 |
| `magnet_cap50b` | .253 / .246 / .256 | 1.721 / 1.243 / 1.120 | 2.983 / 2.377 / 2.043 | −2.98 / −2.38 / −2.04 |
| `eqgr_cap50b` | .211 / .167 / .149 | .996 / .592 / .510 | 1.659 / .721 / .554 | −1.65 / −.60 / −.47 |
| `eqdgr_cap50b_cond` | **.206 / .161 / .143** | **.941 / .581 / .490** | **1.527 / .701 / .538** | −1.52 / −.57 / −.39 |
| *`mix_nll` (all magnitudes)* | *.208 / .164 / .148* | *.857 / .591 / .556* | *1.260 / .861 / .858* | |

* **The leak is gone.** `eqdgr_cap50b_cond` has the lowest bulk error of any Chile arm, capped or
  not (−.002 to −.006 below the full-data mixture). The joint-truncation arm leaked 30–80% of
  small records' mass above M6 (04:15 entry).
* **Against augmentation** (`eqdgr_cap50b_cond` − `mix_cap50b_aug15`): M ≥ 5 −.03 / **−.08 / −.10**
  (28 clusters, 19 of 28 favour the head), M ≥ 6 **−.16 / −.36 / −.44** (6 / 8 / 8 of 8), bulk −.013 to
  −.017. `eqgr_cap50b` is likewise ahead at 3–5 s (M ≥ 6 −.34 / −.43). On Chile the method beats the
  data-side baseline, unlike GEOFON and STEAD.
* **Prior swap alone** (bug-free now) gives M ≥ 5 −.18 / −.19 / −.18 and M ≥ 6 −.26 / −.28 / −.26
  against the capped mixture: a third to a quarter of the equivariant heads' gain here (on
  INSTANCE it was most of it).
* **κ ≡ 1** is worse than the learned slope at 5 s (M ≥ 5 +.035, M ≥ 6 +.14, 8 / 8 clusters), as
  expected where the amplitude scale (MA) is consistent across the cap.
* **Three seeds.** Capped `eqdgr` ensemble − capped mixture ensemble: M ≥ 6 −.44 / −1.03 / −1.13
  (jackknife excluding zero), bulk −.002 / −.004 / −.006. Capped `eqdgr` ensemble − full-data mixture
  ensemble: M ≥ 6 +.26 / **−.18 / −.31** (intervals excluding zero at 3 and 5 s, [−.30, −.06] and
  [−.47, −.15]), bulk −.002 / −.004 / −.006. On the amplitude labels, three capped seeds that never saw
  an M ≥ 5 label beat three full-data seeds on M ≥ 6 at 3–5 s.
* **Truncation margin** on this head (`_m10`): M ≥ 6 +.12 / −.02 / +.00 (n.s.), bulk −.001, false
  alarms −0.3 to −0.5 per 10⁴ from a base near 1. Neutral, as expected where capped false alarms
  are already rare.

Files: `results/chile_eval_cap50b{,_base,_vs_full}.json`, `robust_chile_cap50b.{json,md}`,
`robust_chile_cap50b_ens3.{json,md}`.

## 2026-10-30 11:10 UTC — Pre-registered capped test on STEAD: **not confirmed**. The equivariant heads trained below M5 beat the identically capped mixture by .28–.31 on M ≥ 5 and .77–.87 on M ≥ 6, and even beat the free mixture trained on all of STEAD, but amplitude augmentation is better on M ≥ 5

`PREREGISTRATION_STEAD_CAP.md` (commit bc5ab2b, amendments 1–2). Seed 1, trained on M < 5.0 (bin
filter), all 996,894 records scored. Median action, 1 / 3 / 5 s; jackknife over 456 M ≥ 5 /
51 M ≥ 6 clusters.

| arm (trained below M5.0) | M < 5 MAE (C4) | M ≥ 5 MAE (C1) | M ≥ 5 event MAE (C2) | M ≥ 6 MAE (C3) | false M4 per 10⁴ (C5) |
|---|---|---|---|---|---|
| `mix_cap50` | .2402 / .2007 / .1832 | 1.020 / .898 / .880 | 1.035 / .918 / .897 | 1.900 / 1.698 / 1.668 | 6.6 / 6.3 / 6.4 |
| `mix_cap50_aug15` | .2665 / .2181 / .1981 | .681 / .537 / .490 | .693 / .561 / .506 | 1.324 / .989 / .881 | 18.0 / 14.4 / 13.0 |
| `mixgr_cap50` | .2404 / .2006 / .1835 | .912 / .783 / .752 | .923 / .802 / .771 | 1.762 / 1.526 / 1.477 | 8.8 / 8.6 / 8.8 |
| `eqgr_cap50` | .2418 / .2010 / .1835 | .823 / .634 / .601 | .857 / .675 / .645 | 1.490 / 1.070 / .927 | 8.8 / 7.8 / 7.5 |
| `eqdgr_cap50_cond` (primary) | .2439 / .2015 / .1832 | .786 / .614 / .574 | .799 / .645 / .610 | 1.324 / .923 / .801 | 8.5 / 7.3 / 6.3 |
| `eqgr_k1_cap50` (κ ≡ 1) | .2504 / .2067 / .1884 | .765 / .599 / .546 | .776 / .624 / .573 | 1.182 / .771 / .670 | 11.9 / 10.1 / 9.2 |
| `magnet_cap50` | .3428 / .2968 / .2752 | 1.308 / 1.133 / 1.023 | 1.283 / 1.105 / .985 | 2.453 / 2.143 / 1.993 | 17 / 18 / 24 |
| `lin_invR_cap50` (classical, oracle distance) | .434 / .387 / .375 | .741 / .561 / .509 | .790 / .615 / .564 | 1.210 / .845 / .719 | 66 / 49 / 44 |
| *`mix_nll` (all magnitudes, seed 1)* | | *.814 / .676 / .654* | *.823 / .698 / .677* | *1.540 / 1.223 / 1.194* | *7.5 / 7.2 / 7.2* |

**Decision rule (3 and 5 s), primary `eqdgr_cap50_cond`:**
1. C1 against `mix_cap50`: −.284 [−.314, −.254] and −.306 [−.337, −.275]. **Pass.**
2. C1 against `mix_cap50_aug15`: +.077 [+.059, +.096] and +.084 [+.064, +.104]. Augmentation is
   better. **Fail.**
3. C4 against `mix_cap50`: +.0008 and +.0000 (+.0037 at 1 s, not part of the rule). **Pass.**

Secondary `eqgr_cap50`: criterion 1 passes (−.265, −.279); criterion 2 fails (+.097, +.112).
**Extrapolation is not confirmed on STEAD.**

Context (not part of the decision):
* On M ≥ 6 the primary head is level with augmentation at 3 s (−.066, n.s.) and better at 5 s
  (−.080 [−.152, −.009]).
* Against augmentation, it has .015–.022 lower bulk error and half the false alarms (6–8 against
  13–18 per 10⁴).
* The capped primary head beats the free mixture trained on all magnitudes. M ≥ 5: −.028 / −.062 /
  −.080. M ≥ 6: −.22 / −.30 / −.39. Bulk: +.004 / +.001 / .000. All tail intervals exclude zero.
  The capped head never saw an M ≥ 5 label.
* The prior swap alone (`mixgr`) recovers −.11 to −.13 on M ≥ 5 here, far less than on INSTANCE.
* κ ≡ 1 is better than the learned slope on the tail (M ≥ 5 −.02 / −.03, M ≥ 6 −.13 to −.15), at
  +.005 bulk.
* The Mw-only and gain-QC subgroups give the same numbers within .01.

**Pattern across the four capped tests.**

| | label scale across the cap | head vs augmentation on the top tail | pre-registered? |
|---|---|---|---|
| INSTANCE (cap 4) | ML below, ML and Mw above (switch at about M5) | head better, −.15 to −.23 | no |
| Chile (cap 5) | amplitude magnitude MA throughout | head better (M ≥ 6 .65 / .53 against 1.03 / .98) | no |
| GEOFON (cap 6) | 81% mb at M4–5 → almost all Mw above 6 | augmentation better, +.07 | yes, failed |
| STEAD (cap 5) | 62% mb at M4–5 → 66% Mw at M5–6, 82% above 6 | augmentation better on M ≥ 5 (+.08); head level or better on M ≥ 6 | yes, failed |

The equivariant head extrapolates the amplitude law it learned below the cap. Where the label
definition changes at the cap (mb → Mw), that law is the wrong one, and augmentation's imposed
unit slope happens to fit the new scale better. This explanation is post hoc. It fits all four
results and the measured slopes (GEOFON .44–.61 learned against ≈1 needed). But the two tests in
which the method beat augmentation were not pre-registered, and the two pre-registered ones failed.
Stated plainly: **capped-training extrapolation beyond the existing data-side baseline is
demonstrated only on catalogues with a consistent magnitude scale, and was not confirmed in either
pre-registered test.** What did hold in every capped test is the gain over the identically capped
free mixture, which saturates at the cap. That holds with lower bulk error than augmentation and
with false alarms at or below the mixture's.

Files: `results/stead_eval_cap50{,_base,_vs_full}.json`, `robust_stead_cap50{,_mw,_noqc}.{json,md}`.

## 2026-10-30 10:35 UTC — Distance-informed inference on STEAD, and pooled over four catalogues: conditioned on distance, the distance-marginalized head beats the free mixture on large events at 3 and 5 s on every catalogue (pooled HKSJ interval excluding zero) with lower bulk error everywhere

Exploratory, not pre-registered. STEAD three-seed `eqdgr` ensembles conditioned on the catalogue
distance (`K`, σ = 0; `K10`, σ = .1), against the free-mixture ensemble (`M`) and the classical
inverse law with the same distance. Jackknife over the 456 M ≥ 5 / 51 M ≥ 6 clusters.

| STEAD | Δ bulk MAE 1 / 3 / 5 s | Δ M ≥ 5 MAE | Δ M ≥ 6 MAE | Δ false M4 per 10⁴ |
|---|---|---|---|---|
| `K` − `M` | **−.041 / −.031 / −.021** | **−.132 / −.171 / −.191** | **−.29 / −.39 / −.45** | −1.8 / −2.5 / −2.9 |
| `K10` − `M` | −.037 / −.026 / −.018 | −.126 / −.163 / −.182 | −.30 / −.39 / −.46 | −2.3 / −3.0 / −3.3 |
| `K` − `eqdgr` (marginal) | −.044 / −.031 / −.021 | −.087 / −.087 / −.085 | −.04 / −.01 / +.00 (n.s.) | −2.2 / −2.4 / −2.3 |
| `K` − `lin_invR` | −.243 / −.224 / −.219 | **−.064 / −.061 / −.051** | +.06 / +.02 / +.03 (n.s.) | −63 / −46 / −41 |

Every interval excludes zero except those marked n.s. Conditioning removes the marginal head's
1 s bulk excess that failed the pre-registered rule (+.0024 → −.041). Absolute, `K`:
bulk .193 / .164 / .157, M ≥ 5 .676 / .500 / .458, M ≥ 6 1.257 / .856 / .750.

Pooled over INSTANCE, Chile, GEOFON and STEAD (`meta4_*`):

| contrast | Δ tail, random effects (1 / 3 / 5 s) | HKSJ interval at 3 s / 5 s | pooled Δ bulk | sequences favouring (of 521) |
|---|---|---|---|---|
| `K` − `M` | −.114 / −.184 / −.233 | **[−.280, −.088] / [−.394, −.072]** | −.062 / −.055 / −.052 | 353 / 382 / 398 |
| `K10` − `M` | −.114 / −.177 / −.222 | **[−.259, −.096] / [−.371, −.073]** | −.057 / −.050 / −.046 | 363 / 402 / 414 |
| `K` − `lin_invR` | +.116 / +.005 / −.022 | [−.32, +.33] / [−.34, +.29] | −.27 / −.24 / −.23 | 272 / 281 / 290 |

So with a located event, even with a 26% distance error, the trained head is better than the free
mixture on the largest events of every catalogue and better on bulk. This would meet the
pre-registered pooled criteria that the marginal head missed (10:25 entry), but it is not that
test. The free mixture here has no distance. Against the classical law with the same distance,
the network wins on INSTANCE, Chile M ≥ 5 and STEAD M ≥ 5, and loses on GEOFON M ≥ 7, so the pooled
tail is level (τ = .17). The equal-information test against a free distance head conditioned the
same way is pre-registered (`PREREGISTRATION_EQUALINFO.md`, commit cbe6476) and training.

Files: `results/robust_stead_condR3.{json,md}`, `meta4_condR_vs_mix.{json,md}`,
`meta4_condR10_vs_mix.{json,md}`, `meta4_condR_vs_invR.{json,md}`.

## 2026-10-30 10:25 UTC — Pre-registered STEAD test: the method is **confirmed** through the plain equivariant head (`eqgr`). The primary distance-marginalized head has the larger tail gain at every deadline but misses the 1 s bulk guard by .0004, so under the rule it is **not confirmed**. The pooled four-catalogue secondary claim is **not met**

`PREREGISTRATION_STEAD.md` (written and committed before any STEAD model was trained; amendments 1–2
before any STEAD evaluation). STEAD: 996,894 records, 718 M ≥ 5 events in 456 GK clusters,
63 M ≥ 6 in 51. Three-seed ensembles (posterior mixtures), median action, observed differences;
intervals are the delete-one-cluster jackknife (t, G − 1) over the clusters carrying the tail.
Driver `stead_eval.sh`; nothing was tuned on STEAD.

Absolute values (1 / 3 / 5 s):

| ensemble | bulk MAE (E3) | M ≥ 5 MAE (E1) | M ≥ 5 event MAE (E2) | M ≥ 6 MAE | false M4 per 10⁴ (E4) | NLL at 5 s |
|---|---|---|---|---|---|---|
| `mix` (reference) | .2337 / .1949 / .1781 | .807 / .670 / .648 | .815 / .694 / .671 | 1.552 / 1.241 / 1.200 | 6.8 / 6.5 / 6.5 | 2.150 |
| `eqdgr` (primary) | .2361 / .1952 / .1782 | .762 / .587 / .543 | .774 / .611 / .574 | 1.298 / .867 / .746 | 7.1 / 6.3 / 5.9 | 2.161 |
| `eqgr` (secondary) | .2349 / .1948 / .1781 | .798 / .615 / .579 | .814 / .647 / .613 | 1.463 / 1.014 / .879 | 7.2 / 6.2 / 6.0 | 2.160 |
| `mixgr` (prior only) | .2336 / .1947 / .1778 | .798 / .655 / .629 | .804 / .679 / .653 | 1.518 / 1.217 / 1.163 | 6.3 / 5.9 / 6.1 | — |

**Decision rule.**

| head | E1 at 3 s | E1 at 5 s | E3 at 1 / 3 / 5 s (≤ +.002) | verdict |
|---|---|---|---|---|
| `eqdgr` | **−.084 [−.106, −.062]** | **−.106 [−.130, −.082]** | **+.0024** / +.0004 / +.0000 | criterion 1 passes; criterion 2 fails at 1 s (by .0004) → **not confirmed** |
| `eqgr` | **−.056 [−.071, −.040]** | **−.069 [−.087, −.051]** | +.0012 / −.0000 / −.0001 | **confirmed** |

Supporting numbers:
* E1 at 1 s: `eqdgr` −.045 [−.069, −.021], `eqgr` −.010 (n.s.).
* E2 (event level), `eqdgr` −.041 / −.082 / −.097 and `eqgr` −.002 / −.047 / −.058. All exclude zero except `eqgr` at 1 s.
* Sequences favouring `eqdgr` on M ≥ 5: 265, 303 and 304 of 456. On M ≥ 6 (51 clusters):
  −.25 / −.37 / −.45, with 38, 47 and 48 of 51 favouring it.
* The 1 s bulk excess of `eqdgr` (+.0024, interval [+.0012, +.0036]) appears in every seed (+.0031 to
  +.0034). Its 3 s and 5 s bulk is level.
* E4 is level with the reference at every deadline: `eqdgr` +0.4 / −0.2 / −0.6 per 10⁴, all n.s.
* NLL is .01 nats worse for both equivariant heads; CRPS is equal.

**Seeds (descriptive).** In every seed both heads lower M ≥ 5 error at 3 and 5 s. Ranges: `eqdgr`
−.064 to −.088 and −.091 to −.103; `eqgr` −.048 to −.062 and −.062 to −.071. Bulk at 1 s:
`eqdgr` +.0031 to +.0034, `eqgr` +.0020 to +.0024.

**Pre-specified subgroups** (not part of the decision). `eqdgr` M ≥ 5 at 3 / 5 s, with
jackknife intervals excluding zero in every row:

| subgroup | M ≥ 5 clusters | Δ M ≥ 5 at 3 s | Δ M ≥ 5 at 5 s |
|---|---|---|---|
| Mw-type labels only | 355 | −.078 | −.108 |
| gain-QC suspects excluded | 452 | −.084 | −.106 |
| Alaska–Aleutians | 138 | −.075 | −.089 |
| Chile–Argentina | 81 | −.071 | −.090 |
| Greece–Aegean | 56 | −.151 | −.175 |
| New Zealand | 34 | −.195 | −.220 |
| California–Nevada | 36 | −.067 | −.102 |

`eqgr` is negative in every row too (−.031 to −.144). California–Nevada, the one dense local
network, also has lower bulk error for both heads (−.002).

**Secondary ablation and context.** κ ≡ 1 (`eqgr_k1_nll`, seed 1) has the best tail of the
equivariant heads: M ≥ 5 −.042 / −.097 / −.123 and M ≥ 6 −.32 / −.46 / −.53 against `mix_nll`. Its bulk
cost is +.010 / +.006 / +.005, which would fail the bulk guard, and NLL is +.03. Against it, the
learned slope gives up .02–.05 on M ≥ 5 for .004–.008 of bulk error. The classical inverse law with
the catalogue distance is about level with `eqdgr` on M ≥ 5 (+.022 / +.026 / +.034, n.s.). It has
twice the bulk error (.39 against .195) and 45–68 false M4 per 10⁴.

**Pooled four-catalogue analysis (amendment 2), `eqdgr` − `mix`.**

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| random-effects Δ | −.061 | −.124 | −.165 |
| HKSJ interval (3 df) | **[−.118, −.005]** | [−.256, +.007] | [−.348, +.019] |
| pooled bulk Δ | +.0038 | +.0014 | +.0006 |
| sequences favouring (of 521) | 311 (p = 1e−5) | 351 (p = 2e−15) | 359 (p = 4e−18) |

The HKSJ interval must exclude zero at 3 s and 5 s, and it does not (it reaches +.007 and +.019).
The pooled bulk guard fails at 1 s. **The secondary claim is not met.** The between-catalogue SD τ is
.05–.06, with GEOFON's +.016 bulk cost the outlier. For `eqgr` the pooled tail Δ is +.014 / −.058 /
−.110, with HKSJ intervals including zero.

**Reading.** On the held-out fourth catalogue, chosen and locked before any model saw it, both
equivariant heads lower large-event error at 3 and 5 s by robust margins. That holds in every seed,
region and label-type subgroup, with no rise in false alarms. The plain head does it with level
bulk error and passes the pre-registered rule. The distance-marginalized head gives 50% more tail
gain (M ≥ 5 −.08 / −.11, M ≥ 6 −.37 / −.45). It pays .0024 of bulk error at 1 s, a 1% relative cost,
which the rule set at .002, so under the rule it is not confirmed. The bulk guard was chosen in
advance, and the result is reported against it unchanged.

Files: `results/robust_stead_{ens3,ens3_mw,ens3_noqc,ens3_region_*,k1}.{json,md}`,
`stead_eval_{ens3,ens3_prior,seed_s1,seed_s2,seed_s3,k1_classical}.json`, `meta_eqdgr.{json,md}`,
`meta_eqgr.{json,md}`. The pre-registered capped STEAD test is evaluated when its seven arms finish.

## 2026-10-30 09:15 UTC — INSTANCE capped (M < 4.0) complete. The prior swap of Proposition 3 does most of the extrapolation, even for a free likelihood; equivariance adds tail (n.s.) and halves the false alarms; the truncation margin removes the remaining false-alarm cost. A head trained only on M < 4 then matches the free mixture trained on everything

Seed 1, median action, 1 / 3 / 5 s; jackknife over the 11 M ≥ 5 sequences. INSTANCE has no
labels in the masked cap bin, so the binning bug never applied here.

| trained below M4.0 | bulk MAE | M ≥ 4 MAE | M ≥ 5 MAE | false M4 per 10⁴ |
|---|---|---|---|---|
| `mix_cap40` (free mixture) | .332 / .275 / .243 | 1.025 / .857 / .810 | 1.807 / 1.605 / 1.566 | 0 / 0 / 0 |
| `mix_cap40_aug15` (augmentation ±1.5 decades) | .363 / .292 / .256 | .757 / .595 / .539 | 1.129 / .811 / .723 | 11 / 6 / 4 |
| `mixgr_cap40` (free mixture × GR factor, truncated in training) | .332 / .275 / .242 | .716 / .557 / .518 | 1.061 / .793 / .756 | 28 / 28 / 27 |
| `eqgr_cap40` | .332 / .274 / .239 | .807 / .615 / .550 | 1.097 / .671 / .554 | 13 / 11 / 10 |
| `eqdgr_cap40` (joint truncation) | .329 / .270 / .235 | .779 / .580 / .522 | .978 / .582 / .507 | 15 / 12 / 9 |
| `eqdgr_cap40_cond` (conditional truncation) | .330 / .272 / .237 | .803 / .614 / .552 | 1.042 / .665 / .578 | 13 / 16 / 15 |
| `eqdgr_cap40_cond_m10` (+ truncation margin 1.0) | .330 / .268 / .233 | .825 / .627 / .565 | 1.131 / .734 / .631 | **9 / 5 / 3** |
| *`mix_nll` (all magnitudes)* | *.328 / .270 / .238* | *.764 / .577 / .530* | *1.051 / .765 / .703* | *6 / 5 / 5* |

1. **The prior swap alone recovers most of the extrapolation.** The free mixture with a GR factor
   is truncated at the cap in training and untruncated at test. On M ≥ 5 that gives −.75 / −.81 /
   −.81 against the plain capped mixture, jackknife intervals excluding zero, with unchanged
   bulk error. This is Proposition 3's swap applied to a free likelihood. The likelihood of a
   head trained against a truncated prior need not encode the cap, because the prior does that.
   So the posterior with the untruncated prior rises past it. The cost is 25 extra false M4
   predictions per 10⁴ small records. (Chile's prior-only control was confounded by the binning
   bug; its rerun is in the Chile queue.)
2. **Equivariance on top of the swap** adds M ≥ 5 +.04 / −.12 / −.20 (`eqgr`) and −.08 / −.21 / −.25
   (`eqdgr`), not significant over 11 sequences. It halves the false alarms (−11 to −15 per 10⁴)
   and lowers bulk error by up to .007. The capped amplitude response (04:30 entry) and the
   GEOFON result suggest the equivariant likelihood matters most where the learned slope is right.
   So the mechanism claim is restated: **the truncated-in-training, untruncated-at-test GR factor
   is the main extrapolation device; the equivariant likelihood makes it cleaner (fewer false
   alarms, more tail at 3–5 s).**
3. **Against amplitude augmentation** (the existing data-side remedy) the equivariant heads win on
   INSTANCE. `eqdgr_cap40` gives M ≥ 5 −.15 / **−.23 / −.22** (intervals excluding zero at 3 / 5 s) and
   `eqdgr_cap40_cond` −.09 / **−.15 / −.15**, both with .02–.03 lower bulk error. GEOFON (08:55 entry)
   is the opposite. Augmentation's unit slope suits GEOFON's Mw tail, and the learned mb slope
   does not.
4. **The conditional truncation costs a little here.** `eqdgr_cap40_cond` − `eqdgr_cap40`: M ≥ 5
   +.06 / +.08 / +.07 (n.s.), M ≥ 4 +.02 / +.03 / +.03 (intervals excluding zero). The joint
   truncation did not leak on INSTANCE, so the fix that Chile needs is not free.
5. **The truncation margin removes the false-alarm cost** (*see the 11:25 correction: on `eqgr` it
   also costs .12–.19 on M ≥ 5*). `eqdgr_cap40_cond_m10` − `eqdgr_cap40_cond`:
   false M4 −4.7 / −10.5 / −11.7 per 10⁴ (bootstrap intervals excluding zero; the cluster jackknife
   over 19,280 clusters is wider). M ≥ 5 +.09 / +.07 / +.05 (n.s.), M ≥ 4 +.01 to +.02, bulk −.0005 to
   −.004. This is the predicted effect (THEORY.md, remark after Proposition 3). Against the free
   mixture trained on all magnitudes, the margin head is level on every metric: M ≥ 5 +.08 / −.03 /
   −.07, false M4 +2.3 / −0.2 / −1.2, bulk +.002 / −.002 / −.005, all n.s. That is a model that never
   saw an M ≥ 4 label. The same margin on Chile `eqgr` (09:00 note) was neutral, as expected where
   capped false alarms were already rare.

Files: `results/eval_cap40{,_bfix_aug,_vs_full}.json`, `robust_instance_cap40_attr.{json,md}`,
`robust_instance_cap40_cond.{json,md}`. Seeds 2–3 of `mix_cap40`, `eqgr_cap40` and `eqdgr_cap40_cond`,
and the `eqgr` margin arm, are training on SageMaker.

## 2026-10-30 08:55 UTC — Pre-registered capped test on GEOFON: **not confirmed**. The equivariant heads beat the identically capped mixture by .28–.31 on M ≥ 6, but amplitude augmentation beats them on the tail and the bulk guard fails. Cause: the label type changes at the cap (mb below, Mw above)

`PREREGISTRATION_GEOFON_CAP.md` (commit 25e1657, written before training). The heads are trained
on records whose label bin is below M6.0 and scored on all 31,020 records (276 M ≥ 6 events in
208 clusters, 50 M ≥ 7 in 46). Median action, 1 / 3 / 5 s.

| arm (trained below M6.0) | M < 6 MAE (G4) | M ≥ 6 MAE (G1) | M ≥ 7 MAE (G3) | false alarms* | response per decade (1st / 2nd) at 3 s |
|---|---|---|---|---|---|
| `mix_cap60` (3-seed ens.) | .467 / .419 / .397 | 1.249 / 1.094 / 1.024 | 2.04 / 1.88 / 1.79 | 0 | .25 / .14 |
| `mix_cap60_aug15` | .546 / .490 / .471 | .976 / .744 / .632 | 1.60 / 1.33 / 1.18 | 78 / 61 / 70 | .68 / .37 |
| `eqgr_cap60` (3-seed ens.) | .493 / .436 / .412 | 1.088 / .916 / .825 | 1.84 / 1.61 / 1.47 | 16 / 12 / 13 | .44 / .44 |
| `eqdgr_cap60_cond` (3-seed ens.) | .502 / .443 / .418 | .997 / .816 / .714 | 1.67 / 1.44 / 1.25 | 32 / 26 / 21 | .61 / .60 |
| `eqgr_k1_cap60` (κ ≡ 1) | .627 / .549 / .519 | .848 / .709 / .628 | 1.28 / 1.00 / .84 | — | .98 / .86 |
| `magnet_cap60` | .599 / .589 / .565 | 1.680 / 1.716 / 1.558 | 2.35 / 2.58 / 2.41 | — | — |
| `lin_invR_cap60` (classical, oracle distance) | .695 / .612 / .571 | .897 / .758 / .681 | .97 / .81 / .69 | 564 / 355 / 286 | — |
| *`mix_nll` all magnitudes (3-seed ens.)* | *.484 / .428 / .406* | *.889 / .665 / .577* | *1.55 / 1.24 / 1.11* | | *.54 / .37* |

\* M < 5 records predicted ≥ 5.95, per 10⁴. Full-data `eqgr_nll` and `eqdgr_nll` respond .55 and
.67 per decade (the capped `eqgr` .44).

**Decision rule (3 and 5 s), primary `eqdgr_cap60_cond`:**
1. Ensemble G1 against the `mix_cap60` ensemble: −.279 [−.311, −.246] and −.310 [−.346, −.275]
   (jackknife over 208 clusters). **Pass.**
2. Seed-1 G1 against `mix_cap60_aug15`: +.070 [+.050, +.090] and +.073 [+.055, +.091].
   Augmentation is better. **Fail.**
3. Ensemble G4 against the `mix_cap60` ensemble: +.025 and +.021, above the +.005 guard.
   **Fail.**

Secondary `eqgr_cap60` fails 2 (+.12 to +.18) and 3 (+.018, +.015). **Extrapolation is not
confirmed on GEOFON.** The equivariant heads are still far better than the capped free mixture
and than MagNet (M ≥ 7 −1.15 at 3 s). Against augmentation they have .03 lower bulk error and half
the false alarms, but a worse tail. κ ≡ 1 and the oracle-distance classical law are best on the
tail, at the largest bulk costs. No capped arm reaches the free mixture trained on all magnitudes
(M ≥ 6 .67 / .58).

**Why it fails here.** GEOFON's label type changes at the cap. M4–5 labels are 81% mb, M5–6 48% mb
and 37% Mw, and M ≥ 6 almost all Mw (mB- or Mwp-based). A head trained below M6 learns the
amplitude slope of mb labels, .44–.61 magnitude units per decade (capped `eqgr` even lower than
its full-data twin, .44 vs .55). It carries that slope to Mw events, whose apparent slope at these
windows is steeper. Augmentation and κ ≡ 1 impose a unit slope, which happens to suit them better.
The classical law's fitted A-on-M slope (.55–.68) implies an even steeper inverse. This is the
"mixed ML / Mw labels" failure the method's assumptions list (THEORY.md table). Proposition 3
requires the amplitude law below the cap to hold above it, and on GEOFON the label definition
breaks that. INSTANCE (local magnitudes below the cap, 22 of 31 M ≥ 5 events in Mw) did not show
it. Its label-type change happens at M ~5, well above the M4.0 cap, and the capped head matched
full-data training on the Mw subset. The claim is restricted accordingly: capped training
extrapolates where the label scale is consistent across the cap.

Files: `results/geofon_eval_cap60{,_base,_ens}.json`, `geofon_eval_classical.json`,
`robust_geofon_cap60.{json,md}`, `cap_response_geofon.json`.

## 2026-10-30 08:55 UTC — Distance-informed inference with three seeds and on GEOFON; pooled over three catalogues

Three-seed ensembles conditioned on the catalogue distance (`K`), against the free-mixture ensemble
(`M`), median action; jackknife intervals over the clusters carrying the tail.

| catalogue | Δ bulk MAE (1 / 3 / 5 s) | Δ top-tail MAE | Δ M ≥ 4 (INSTANCE) / M ≥ 5 (Chile) / M ≥ 6 (GEOFON) |
|---|---|---|---|
| INSTANCE (M ≥ 5, 11 seq.) | −.095 / −.082 / −.065 | −.24 / −.26 / −.28 (intervals reach +.01 to +.05) | −.25 / −.24 / −.24 (all exclude 0) |
| Chile (M ≥ 6, 8 clusters) | −.025 / −.027 / −.033 | +.03 / **−.28 / −.39** | −.04 / −.10 / −.14 (all exclude 0) |
| GEOFON (M ≥ 7, 46 clusters) | −.089 / −.093 / −.097 | **−.17 / −.14 / −.17** | −.08 / −.04 / −.04 (all exclude 0) |

On GEOFON, distance removes the distance-marginalized head's bulk cost. The marginal head was
+.014 to +.019 behind the mixture; conditioned, it is .09 ahead, and −.11 against itself.
Pooled over the three catalogues (`meta_analysis.py`), Δ top-tail against the mixture is −.11 /
**−.21 / −.27** (random effects). The HKSJ interval excludes zero at 3 s ([−.41, −.004]) and just
includes it at 5 s ([−.57, +.02]). Sequences favouring the head: 53 / 55 / 55 of 65.

Against the classical inverse law with the same distance, the result splits by catalogue:

| catalogue | Δ bulk | Δ top-tail (1 / 3 / 5 s) |
|---|---|---|
| INSTANCE M ≥ 5 | −.75 / −.72 / −.69 | −.06 / **−.19 / −.20** |
| Chile M ≥ 6 (M ≥ 5) | −.20 / −.20 / −.22 | +.13 / −.04 / −.12 (M ≥ 5 −.04 / **−.14 / −.20**) |
| GEOFON M ≥ 7 (M ≥ 6) | −.34 / −.28 / −.25 | **+.45 / +.29 / +.25** (M ≥ 6 **−.11 / −.15 / −.14**) |

On GEOFON M ≥ 7 the oracle-distance classical law is clearly better (.94 / .81 / .69 against
1.38 / 1.10 / .94). Its cost is .25–.34 more bulk error and false M ≥ 6 calls on 3–6% of M < 5
records. The network's remaining M ≥ 7 deficit has two parts. One is the same label-type slope
problem as the capped test. The other is the Gutenberg–Richter shrinkage that a median under the
natural prior applies to wide posteriors; the classical law has no prior. So the claim "with the
same information the network beats the classical law on the tail" holds for local and regional
networks (INSTANCE, Chile M ≥ 5) and not for the largest GEOFON events.

Files: `results/robust_{instance,chile,geofon}_condR3.{json,md}`,
`meta3_condR_vs_{mix,invR}.{json,md}`, `meta3_condR10_vs_invR.{json,md}`.

**Also (09:00):** the first truncation-margin arm (Chile `eqgr_cap50b_m10`, seed 1) against the
same arm without the margin: bulk −.001 / −.002 / .000, M ≥ 6 −.07 / −.05 / −.03 (n.s.). Chile's
false-alarm rate is too low to test what the margin targets; INSTANCE arms are training. The
capped Chile result replicates in seed 2 (`eqgr_cap50b_s2` − `mix_cap50b_s2`: M ≥ 6 −.31 / −1.03 /
−1.12, jackknife intervals excluding zero). **Transparency:** while checking job progress after
amendment 2 of the STEAD pre-registration, two STEAD fold-4 training-log summaries were displayed:
the reference `mix_nll_s2`, and the start of `eqdgr_nll`'s 1 s line. The STEAD analyses had already
been fixed and committed, and nothing about them changes.

## 2026-10-30 07:30 UTC — Distance-informed inference: one trained distance-marginalized head, conditioned on a known distance at test time, cuts INSTANCE bulk error by 30% and M ≥ 4 error by 42%; with the same distance it beats the classical inverse law and an identically conditioned free head on M ≥ 5

`eqdgr` models the joint p(r, m | x) over a log-distance bin and magnitude, and marginalizes r at
inference. `condr_arms.py` instead conditions on a distance r̂, with no retraining:
p(m | x, r̂) ∝ Σ_r p(r, m | x) N(r̂; r, σ²). This uses the catalogue hypocentral distance, which a
network location supplies after a few stations. σ = 0 is the exact bin; σ = .1 / .2 (log10 km,
≈ 26% / 58%) mimic location error. The same is done for the free distance-mixture head `mixdgr`,
which has the same latent but no equivariance. The comparison of record is the classical
inverse law fitted with the same catalogue distance (`lin_invR`). Seed 1, median action, 1 / 3 / 5 s.

INSTANCE

| arm | bulk MAE | M ≥ 4 MAE | M ≥ 5 MAE | top-bin bias | false M4 per 10⁴ | NLL at 5 s |
|---|---|---|---|---|---|---|
| `eqdgr_nll` (marginal, no distance) | .327 / .268 / .234 | .738 / .559 / .504 | .898 / .578 / .503 | −.78 / −.41 / −.33 | 12.2 / 7.7 / 5.5 | 2.40 |
| `eqdgr_nll` given r (σ = 0) | **.229 / .185 / .171** | **.512 / .337 / .290** | **.800 / .491 / .413** | −.75 / −.43 / −.35 | 3.7 / 2.0 / 1.6 | 2.15 |
| given r̂, σ = .1 | .234 / .192 / .177 | .537 / .360 / .311 | .820 / .510 / .424 | −.77 / −.44 / −.35 | 2.6 / 1.5 / 1.1 | 2.18 |
| given r̂, σ = .2 | .260 / .215 / .195 | .593 / .419 / .370 | .835 / .524 / .440 | −.77 / −.43 / −.34 | 3.4 / 1.9 / 1.4 | 2.26 |
| `mixdgr_nll` given r (free head) | .228 / .184 / .170 | .516 / .350 / .303 | .939 / .655 / .585 | −.92 / −.63 / −.56 | 3.5 / 2.1 / 1.7 | 2.13 |
| `lin_invR` (classical, same distance) | .980 / .904 / .859 | .915 / .785 / .729 | .857 / .687 / .615 | −.32 / −.16 / −.09 | 1626 / 1336 / 1224 | 3.85 |

Jackknife over the 11 M ≥ 5 sequences (t on 10 df), Δ M ≥ 5 MAE:

| contrast | 1 s | 3 s | 5 s |
|---|---|---|---|
| `eqdgr` given r − `lin_invR` | −.057 [−.271, +.157] | **−.196 [−.363, −.029]** | **−.202 [−.357, −.047]** |
| `eqdgr` given r̂ (σ = .1) − `lin_invR` | −.037 [−.250, +.176] | −.177 [−.369, +.015] | **−.192 [−.377, −.006]** |
| `eqdgr` given r − `mixdgr` given r | **−.139 [−.265, −.012]** | **−.164 [−.301, −.026]** | **−.172 [−.297, −.047]** |
| `eqdgr` given r − `eqdgr` marginal | −.097 [−.261, +.066] | −.087 [−.232, +.058] | −.090 [−.232, +.052] |

M ≥ 4 against `lin_invR` is −.40 / −.45 / −.44, with 184–186 of 194 sequences favouring the head.
Equivariant against free, both given r: M ≥ 4 −.004 / −.012 / −.013, bulk +.001.

Northern Chile (seed 1; `mixdgr` not trained there)

| arm | bulk MAE | M ≥ 5 MAE | M ≥ 6 MAE | top-bin bias |
|---|---|---|---|---|
| `eqdgr_nll` (marginal) | .205 / .160 / .142 | .845 / .554 / .468 | 1.258 / .600 / .484 | −1.23 / −.35 / −.24 |
| `eqdgr_nll` given r | .181 / .136 / .114 | .799 / .497 / .419 | 1.291 / .586 / .471 | −1.29 / −.44 / −.35 |
| given r̂, σ = .1 | .188 / .144 / .125 | .822 / .524 / .441 | 1.277 / .580 / .473 | −1.26 / −.38 / −.30 |
| `lin_invR` | .377 / .331 / .329 | .845 / .628 / .615 | 1.188 / .610 / .586 | −1.16 / −.27 / +.08 |

Given r against marginal: M ≥ 5 is −.045 / −.057 / −.049, jackknife over 28 clusters excluding
zero at every deadline (21 / 28 favour). Bulk is −.024 to −.029, and M ≥ 6 is unchanged. Against
`lin_invR`: M ≥ 5 −.131 [−.175, −.087] at 3 s and −.196 [−.240, −.153] at 5 s (23 / 28 and
25 / 28). M ≥ 6 is n.s. at 3 s, and −.115 [−.277, +.047] at 5 s (σ = .2: −.111 [−.200, −.023]).

Reading.

1. **A free byproduct of the distance-marginalized form.** The trained joint posterior answers
   "magnitude given this waveform and this distance" exactly (THEORY.md, corollary to
   Proposition 1). A system can use the marginal at the first station and switch to the
   conditional once it has a location, with one model. On INSTANCE, a local network with a
   wide range of distances, this lowers bulk error by 30% and M ≥ 4 error by 42%. It cuts false
   M4 alarms threefold and lowers NLL by .25–.32 nats. A 26% distance error keeps most of it. On
   Chile the gain is smaller: bulk −.024 to −.029, M ≥ 5 −.05.
2. **Given the same distance, the network beats the classical law on the tail.** The
   distance-conditioned head is ahead of the inverse classical law with the same oracle distance
   on M ≥ 5 at 3 and 5 s, on both catalogues, with small-cluster-robust intervals excluding zero.
   It has a third (INSTANCE) to half (Chile) of the bulk error and 1/400 of the false alarms.
   Without distance it had tied that law (06:55 entry).
3. **Equivariance, not distance, fixes the tail.** Conditioned on the same distance, the free
   distance-mixture head improves bulk and M ≥ 4 as much as the equivariant one. Its M ≥ 5 error
   stays .14–.17 higher at every deadline (jackknife intervals excluding zero), and its top-bin
   bias stays near −.6 at 3–5 s against −.4. This mirrors the classical result: forward
   regression saturates even with distance, the inverse law does not.
4. **The remaining bias of the largest events is not distance ambiguity.** Conditioning does
   not change the top-bin bias (INSTANCE −.43 / −.35 at 3 / 5 s; Chile slightly worse). So the
   residual is the waveform not yet carrying the event's size, not GR shrinkage from an
   unknown distance.

Seed 1 only. Seeds 2–3 for INSTANCE and Chile, and GEOFON seeds 1–3, are running
(`condr_batch2.sh`), with the pooled comparison against the classical law. Files:
`results/eval_condR.json`, `eval_condR_free.json`, `chile_eval_condR.json`,
`robust_{instance,chile}_condR.{json,md}`.

## 2026-10-30 06:55 UTC — Classical amplitude laws as ordinary arms (all magnitudes): with the true catalogue distance the inverse law ties the networks on large events, at 2–4× their bulk error and 100–300× their false-M4 rate; without distance, or in the forward direction, it fails

The audit's classical baseline, rerun as arms (`linear_arms.py`): fitted per fold on the training
rows, Gaussian predictive distribution with the training residual SD, scored by the same
evaluation and robust statistics as the networks. The networks get no distance; `invR` and
`fwdR` use the catalogue hypocentral distance (an oracle at 1–5 s after the first P).
Median action, 1 / 3 / 5 s.

INSTANCE (1,159,249 records; M ≥ 5: 31 events in 11 sequences)

| arm | bulk MAE | M ≥ 4 MAE | M ≥ 5 MAE | false M4 per 10⁴ (M < 3.5) | NLL / CRPS at 5 s |
|---|---|---|---|---|---|
| `mix_nll` (free mixture) | .328 / .270 / .238 | .764 / .577 / .530 | 1.051 / .765 / .703 | 6.3 / 5.2 / 4.6 | 2.43 / .172 |
| `eqdgr_nll` | .327 / .268 / .234 | .738 / .559 / .504 | .898 / .578 / .503 | 12.2 / 7.7 / 5.5 | 2.40 / .168 |
| `lin_invR` A ~ M + log R, solved for M | .980 / .904 / .859 | .915 / .785 / .729 | .857 / .687 / .615 | 1626 / 1336 / 1224 | 3.85 / .630 |
| `lin_inv` A ~ M + invariants | 1.287 / 1.257 / 1.199 | 1.316 / 1.382 / 1.354 | .926 / .936 / .964 | 2625 / 2359 / 2135 | 4.52 / 1.174 |
| `lin_fwdR` M ~ A + log R | .418 / .410 / .405 | 1.408 / 1.325 / 1.278 | 2.349 / 2.216 / 2.140 | 1.4 / 2.4 / 3.2 | 3.07 / .289 |

Northern Chile (505,666 records, MA labels; M ≥ 6: 12 events in 8 clusters)

| arm | bulk MAE | M ≥ 5 MAE | M ≥ 6 MAE | top-bin bias | NLL / CRPS at 5 s |
|---|---|---|---|---|---|
| `mix_nll` | .208 / .164 / .148 | .857 / .591 / .556 | 1.260 / .861 / .858 | −1.26 / −.86 / −.86 | 1.97 / .108 |
| `eqdgr_nll` | .205 / .160 / .142 | .845 / .554 / .468 | 1.258 / .600 / .484 | −1.23 / −.35 / −.24 | 1.91 / .103 |
| `lin_invR` | .377 / .331 / .329 | .845 / .628 / .615 | 1.188 / .610 / .586 | −1.16 / −.27 / +.08 | 3.01 / .247 |
| `lin_inv` | .578 / .509 / .510 | 1.373 / 1.345 / 1.447 | 1.327 / 1.422 / 1.682 | +.48 / +1.04 / +1.36 | 3.43 / .380 |
| `lin_fwdR` | .303 / .278 / .274 | 2.244 / 1.789 / 1.606 | 3.052 / 2.332 / 2.046 | −3.05 / −2.33 / −2.05 | 2.76 / .201 |

`eqdgr_nll` − `lin_invR`, delete-one-cluster jackknife (t, G − 1) and cluster bootstrap:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| INSTANCE bulk | −.652 | −.636 | −.625 (all intervals exclude 0) |
| INSTANCE M ≥ 5 (11 seq.) | +.041 [−.171, +.252], 4 / 7 | −.109 [−.329, +.111], 8 / 3 | −.112 [−.339, +.115], 8 / 3 |
| Chile bulk | −.171 | −.171 | −.186 (all exclude 0) |
| Chile M ≥ 5 (28 clusters) | +.000 [−.059, +.059] | **−.074 [−.123, −.025]**, 20 / 8 | **−.148 [−.194, −.101]**, 22 / 6 |
| Chile M ≥ 6 (8 clusters) | +.069 [−.067, +.206] | −.010 [−.068, +.047] | **−.102 [−.180, −.024]**, 6 / 2 |

Reading.

1. **The forward direction fails even with all magnitudes and the true distance.** `lin_fwdR`
   underestimates the top bin by 2–3 units: regression dilution. E[M | A, R] shrinks toward the
   bulk by the ratio of signal to noise variance in A, here about one third of the inverse slope.
   Training on large events does not cure a forward law. That is the classical form of
   magnitude saturation, and the free network's −.7 to −1.3 top-bin bias is its smooth analogue.
2. **The inverse law with the true distance is a strong tail baseline.** On INSTANCE M ≥ 5 it is
   statistically tied with the distance-marginalized head at every deadline. It is slightly ahead
   at 1 s, where distance carries the most information and the network has the least waveform.
   On Chile the head is ahead at 3–5 s (M ≥ 5 and, at 5 s, M ≥ 6), with intervals excluding zero.
3. **It is not a usable estimator.** Its bulk error is 2× (Chile) to 4× (INSTANCE) the
   network's. Its proper scores are far worse: NLL +1.1 to +1.5 nats, CRPS 2.4–3.7×. On INSTANCE
   it calls 12–16% of M < 3.5 records M ≥ 4, against 0.05–0.12% for the networks. A single
   residual SD in magnitude units, divided by a slope of about .5–.7, is a very wide
   distribution, and its median wanders. Without distance (`lin_inv`) it is worse on everything.
4. **So the networks' tail advantage over the free mixture is not "a better classical law".**
   The equivariant head matches the oracle-distance inverse law on the events where the free
   network saturates. It keeps the free network's bulk accuracy, calibration and false-alarm
   rate, and it uses no distance. The like-for-like comparison, the same head conditioned on the
   catalogue distance, is the next entry.

Files: `results/eval_classical.json`, `chile_eval_classical.json`,
`robust_{instance,chile}_classical.{json,md}`; arms `lin_{fwd,fwdR,inv,invR}` and `_cap40` /
`_cap50b` under each work directory.

## 2026-10-30 05:10 UTC — Independent audit of the capped-training result: no leak, headline numbers reproduced; a label-binning bug at the cap, two overstated comparisons, and a classical baseline

An adversarial audit (a separate agent, read-only, CPU) tried to break the capped-training
result. Report: scratchpad `AUDIT_CAP.md`, summarized here with the responses.

**No problem found.** Every capped arm's training rows match the cap in every fold (max label 3.9
on INSTANCE, 4.99 on Chile), static normalization is fitted after the cap, no sequence or event
spans folds, every arm scores identical rows, the truncation is active in training and absent at
evaluation for every GR head, static inputs are instrument metadata only, and the mean action
gives the same ordering. Headline numbers recomputed independently to three decimals (Chile M ≥ 6
`eqgr_cap50` .654 / .532, `mix_cap50` 1.610 / 1.590; INSTANCE M ≥ 5 `eqdgr_cap40` .978 / .582 /
.507, `mix_cap40` 1.807 / 1.605 / 1.566; the 22 Mw events likewise). Capped-vs-capped is
unanimous across sequences: 8/8 Chile M ≥ 6 clusters, 11/11 INSTANCE M ≥ 5 clusters.

**Findings and responses.**

* **Label-binning bug at the cap (minor for the method, material for one control).** Labels in
  [cap − 0.05, cap) round into the cap's own 0.1 bin, which the truncated prior masks, so each
  costs ~10⁴ nats (Chile: 84 training rows; INSTANCE: none, its labels are on the 0.1 grid). It
  shows as loss spikes in the Chile capped GR heads and flattens their learned tail slope
  (β −.20 to −.30 capped vs −.53 to −.67 uncapped). Its effect on `eqgr_cap50` is small (the
  pinned-slope arm agrees), but it confounds the prior-only control `mixgr_cap50` (β ≈ 0, +1.2 bias
  at M4–4.5, 149 false M4 per 10⁴), so the 04:15 and 04:30 entries' reading of that control is
  withdrawn until the rerun. **Fix:** `common.cap_keep` keeps a row only if its bin lies below the
  cap (`--cap-filter bin`, the new default; old arms replay with the old filter). INSTANCE rows
  are unchanged; every Chile capped arm is being retrained under the fix (suffix `b`,
  `capcond_batch_v2.sh`); the STEAD capped pre-registration was amended before any capped STEAD
  arm ran (23 affected rows there).
* **"Capped `eqgr` beats the free mixture trained on all magnitudes" on Chile M ≥ 6 holds only on
  the amplitude labels (material).** Scored against Chile's independent magnitudes: M_EXT M ≥ 6 (9
  events) `eqgr_cap50` .692 / .573 at 3 / 5 s vs `mix_nll` (three seeds) .673–.703 / .687–.708;
  MW_SIPPL M ≥ 6 (6 events) .673 / .614 vs .616–.687 / .659–.673. So it is a tie at 3 s and a modest
  gain at 5 s. MA runs .1–.4 above M_EXT for these events. The capped-vs-capped gap survives
  relabelling (M_EXT: .69 / .57 vs `mix_cap50` 1.47 / 1.44). The claim is restated below.
* **The INSTANCE headline arm `eqdgr_cap40` was trained with the joint truncation (material for
  wording, not for the conclusion).** It finished before the conditional fix; the gross leak did
  not occur, but small records carry P(m ≥ 5) > .3 at 2.0 per 10⁴ vs .1–.3 for `eqdgr_nll`. The
  leak-free reference is `eqgr_cap40` (M ≥ 5 1.10 / .67 / .55), still about one unit better than
  `mix_cap40`; `eqdgr_cap40_cond` is queued.
* **A mixture's component index is also an unobserved latent (minor).** Capped `eqgr_cap40` puts
  5–8× more likelihood weight on components centred above M4.5 for small records than `eqgr_nll`
  (.0016 / .0010 / .0007 vs .0002 / .0002 / .0001), raising small-record P(m ≥ 5) 5–10× and the
  false-M4 rate 1.5–2×; per-event tail predictions of capped and uncapped heads agree. This is the
  likely source of the capped heads' extra false alarms. THEORY.md's remark now covers it.
* **"Keeps rising linearly" is built in (minor).** `cap_response.py` adds δ to A only, and the
  equivariant trunk never sees A, so the location shifts by exactly κ(s)·δ. The evidence in the
  04:30 entry is the *value* of κ under the cap (equal to the full-data κ within .04 per decade on
  INSTANCE) and the contrast with the free heads, not the linearity.
* **Classical baseline (matters for the framing).** Fitted on the same capped rows and folds
  (`linear_baseline.py`):

  | classical law (trained below the cap) | Chile bulk | Chile M ≥ 6 (1 / 3 / 5 s) | INSTANCE bulk | INSTANCE M ≥ 5 |
  |---|---|---|---|---|
  | forward regression M ~ A (+ invariants) | .32–.36 | 2.26–3.37 (bias −2.3 to −3.4) | .47–.51 | 2.48–3.05 (saturated) |
  | inverse law A ~ M + invariants, solved for M | .53–.62 | 1.43 / 1.55 / 1.90 (overshoots) | 1.8–3.2 | 2.7–4.5 |
  | inverse law A ~ M + log R, **true catalogue distance** | .34–.39 | 1.21 / .61 / .59 | .91–1.08 | 1.01 / .80 / .71 |
  | `eqgr_cap50` / `eqdgr_cap40` (no distance input) | .15–.21 | 1.56 / .65 / .53 | .23–.33 | .98 / .58 / .51 |

  Forward regression saturates like the free network, because truncation on M biases E[M | A];
  the inverse (generative) direction A | M is not biased by selection on M, which is the
  classical counterpart of Proposition 3. With the true distance the inverse law extrapolates
  about as well as the equivariant head at 3–5 s (better at 1 s on Chile), at two (Chile) to four
  (INSTANCE) times its bulk error, and it needs a distance a single station does not have in the
  first seconds. Without distance it is useless. **Restated contribution:** extrapolating past the
  training range is a property of a generative amplitude law; the equivariant neural head is that
  law inside a learned posterior, so it extrapolates like the oracle-distance classical law while
  keeping the network's bulk accuracy and needing no distance.
* **Small, clustered tails (minor, already stated).** Chile M ≥ 6: 103 records, 12 events, 8
  clusters; INSTANCE Mw M ≥ 5: 22 events in 7 clusters (9 from Central Italy). Capped arms are
  single-seed. On Chile, 7,994 events from the sequences of the 12 M ≥ 6 events sit in other folds
  (only their M < 5 part is admitted), equally for all arms.
* **Chile component order may be swapped (minor, affects all arms equally).** The source manifest
  says ZNE but the cache was built with `--order ENZ`; stored channel 0 has the largest P energy in
  76% of records, so the picker probably ran on a horizontal. Picks still follow P moveout (median
  7.6 km/s, ≤ 1.7% S-like). To be checked in `chile_prep.py`.

## 2026-10-30 04:30 UTC — Mechanism of the capped-training result: the equivariant heads keep the amplitude law they learned below the cap; the free mixture flattens at the cap

**Test.** Held-out records just below the cap (INSTANCE M3.5–4.0, Chile M4.5–5.0; up to 2,000
per fold, five folds) have their ground motion multiplied by 10^x for x = 0 … 2 decades, and the
posterior median is recorded (`cap_response.py`; `results/cap_response_*.json`;
`figures/capped_amplitude_response.png`). Response = rise of the mean median per decade over
the first / second decade, at 1 / 3 / 5 s.

| arm | INSTANCE (cap 4.0) | Chile (cap 5.0) |
|---|---|---|
| free mixture, capped | .35/.23, .37/.21, .38/.20 | .45/.24, .41/.20, .40/.20 |
| free mixture + augmentation ±1.5, capped | ⟨pending⟩ | .80/.54, .79/.50, .78/.49 |
| prior only (`mixgr`), capped | ⟨pending⟩ | −.13/−.14, −.28/−.12, −.28/−.12 |
| **`eqgr`, capped** | .58/.60, .66/.67, .70/.70 | .95/.95, 1.03/1.03, 1.03/1.03 |
| `eqdgr`, capped | .70/.78, .78/.83, .80/.83 | ⟨retraining⟩ |
| free mixture, all magnitudes | .56/.54, .63/.57, .64/.55 | .67/.44, .67/.40, .67/.39 |
| `eqgr`, all magnitudes | .61/.62, .68/.68, .71/.70 | — |
| `eqdgr`, all magnitudes | .74/.78, .81/.82, .81/.83 | 1.01/1.01, 1.09/1.09, 1.10/1.11 |

**Reading.** (i) The capped free mixture's response halves in the second decade and its mean
estimate stalls just below the cap (INSTANCE 3.6–3.8, Chile 4.9–5.0 at +2 decades): it has
learned that magnitudes stop at the cap. (ii) The capped equivariant heads respond linearly, by
the same slope in both decades, and their slope equals that of the same head trained on all
magnitudes to within .04 per decade on INSTANCE: removing every large event from training does
not change the amplitude law they learn. This is Proposition 3's mechanism, measured.
(iii) Augmentation bends, like the free mixture trained on all data. (iv) The capped prior-only
model responds *negatively* and starts above the cap. *[Corrected 05:10: this control is
confounded by the label-binning bug at the cap found by the audit; its reading is withdrawn until
the rerun `mixgr_cap50b`. Also, the equivariant heads' linearity is built in (the trunk never
sees A); the evidence is the value of κ, not the linearity.]* The INSTANCE learned slope (.6–.8) is
below Chile's (≈ 1.0), consistent with different magnitude types and distance ranges.

## 2026-10-30 04:25 UTC — Interim: capped-training extrapolation on INSTANCE (trained on M < 4.0) replicates, including on moment-magnitude labels

Interim, seed 1, point estimates computed directly from the saved out-of-fold predictions;
bootstrap intervals follow when the second host's batch (`eval_cap40*.json`) completes. Every
M ≥ 4 record (346 events) and every M ≥ 5 record (31 events) lies beyond the training range.
Record-level MAE at 1 / 3 / 5 s; FP4 = share of M < 3.5 records predicted ≥ 3.95, per 10⁴.

| arm | bulk MAE | M≥4 MAE | M≥5 MAE | FP4 per 10⁴ | bias, M5.5–6.6 |
|---|---|---|---|---|---|
| `mix_cap40` (free mixture, M < 4) | .331 / .274 / .242 | 1.025 / .856 / .810 | 1.805 / 1.605 / 1.566 | 0 / 0 / 0 | −2.21 / −2.05 / −2.03 |
| `eqgr_cap40` (M < 4) | .331 / .273 / .238 | .807 / .616 / .550 | 1.100 / .673 / .555 | 11.6 / 10.3 / 9.3 | −1.21 / −.60 / −.46 |
| **`eqdgr_cap40`** (M < 4; joint truncation, see the 05:10 audit entry) | .328 / .268 / .233 | .779 / .580 / .522 | **.978 / .582 / .511** | 14.8 / 11.7 / 8.8 | −1.02 / −.50 / −.43 |
| *all magnitudes:* `mix_nll` | .327 / .269 / .237 | .763 / .577 / .530 | 1.052 / .765 / .703 | 6.3 / 5.3 / 4.6 | −1.30 / −1.02 / −.97 |
| *all magnitudes:* `eqdgr_nll` | .326 / .266 / .232 | .739 / .559 / .504 | .898 / .579 / .505 | 12.1 / 7.7 / 5.5 | −.93 / −.49 / −.40 |

**Not an amplitude-label artefact.** Chile's labels are amplitude magnitudes, so extrapolating
them could be easier for an amplitude-equivariant model. INSTANCE trains on mostly local
magnitudes (97% of events below M3.5 are ML), while 22 of its 31 M ≥ 5 events carry moment
magnitudes. On those 22 Mw events (event-level MAE, 1 / 3 / 5 s): `mix_cap40` 1.83 / 1.62 / 1.58,
`eqgr_cap40` 1.14 / .64 / .49, `eqdgr_cap40` .99 / .53 / .44; with all magnitudes in training,
`mix_nll` 1.05 / .72 / .64 and `eqdgr_nll` .89 / .52 / .44. The distance-marginalized head
trained without a single M ≥ 4 label matches itself trained on everything at 3–5 s and is ahead
of the free mixture trained on everything in point estimate (see the robust statistics below:
the intervals against that reference include zero). The Chile capped arms are also being retrained on the
relabelled caches (independent M_EXT and MW_SIPPL magnitudes for the large events).

**Cost.** The capped equivariant heads raise false M4 alarms at 9–15 per 10⁴ small records,
against 5–6 for the full-data free mixture (the full-data distance head is at 6–12). The capped
free mixture's zero is the other face of its saturation: it cannot predict M4 at all.

**Small-cluster-robust statistics** (`robust_tail.py`, `results/robust_instance_cap40.md`; median
action; jackknife over the 11 sequences holding M ≥ 5 events and the 194 holding M ≥ 4 events):

| comparison | M≥5 Δ (jackknife 95%) at 1 / 3 / 5 s | sequences Δ<0 | M≥4 Δ at 1 / 3 / 5 s | bulk Δ at 5 s | FP4 Δ per 10⁴ |
|---|---|---|---|---|---|
| `eqdgr_cap40` − `mix_cap40` | −.83 [−1.19, −.46] / −1.02 [−1.35, −.70] / −1.06 [−1.34, −.78] | 11 / 11 | −.25 / −.28 / −.29 (all exclude 0) | −.0086 | +15 / +12 / +9 |
| `eqgr_cap40` − `mix_cap40` | −.71 [−.91, −.51] / −.93 [−1.16, −.70] / −1.01 [−1.24, −.78] | 11 / 11 | −.22 / −.24 / −.26 (all exclude 0) | −.0043 | +12 / +10 / +9 |
| `eqdgr_cap40` − `mix_nll` (full data) | −.07 [−.41, +.26] / −.18 [−.47, +.10] / −.20 [−.48, +.09] | 4–6 / 11 | +.015 / +.004 / −.008 (n.s.) | −.0035 | +8.7 / +6.6 / +4.5 |
| `eqgr_cap40` − `mix_nll` (full data) | +.05 / −.09 / −.15 (n.s.) | 4–6 / 11 | +.02 at 5 s (n.s.) | +.0008 | +4.7 at 5 s |

So against the identically capped free mixture the gain is large and holds in every sequence;
against the free mixture trained *with* the large events the capped equivariant heads are
statistically indistinguishable on M ≥ 4 and M ≥ 5 error (point estimates favour them at 3–5 s),
with lower bulk error and roughly twice its false-alarm rate.

Figure: `figures/capped_extrapolation.png` (`capped_figure.py`, data from `cap_curve_data.py`).

## 2026-10-30 04:15 UTC — Capped-training extrapolation on Chile: trained only on M < 5.0, the equivariant head predicts M6+ events better than a free mixture trained *with* them; a training leak in the distance-marginalized head, and its fix

**Design (Proposition 3).** Every head is trained on Chile records with M < 5.0 only
(`--train-mag-cap 5.0`; same folds, schedule and seed 1 as the full-data arms) and scored on all
held-out records, so every M ≥ 5 event (67 events, 12 with M ≥ 6) lies entirely beyond the
training range. GR heads truncate their prior factor at the cap during training only.
Baselines trained the same way: the free mixture (TEAM-LM-style), the free mixture with the GR
factor (`mixgr`, prior only), and the free mixture with amplitude-scaling augmentation of ±0.5
and ±1.5 decades (the Zhang & Zhang-type way of inducing an amplitude law). `_bfix` pins the
tail slope to the catalogue b-value (−1.79 nats per unit). Median action; MAE at 1 / 3 / 5 s;
n = 505,666 records; `results/chile_eval_cap50*.json`.

| arm (trained on M < 5.0) | bulk MAE | M≥5 MAE | M≥6 MAE |
|---|---|---|---|
| `mix_cap50` (free mixture) | .208 / .165 / .149 | 1.155 / .935 / .898 | 1.956 / 1.610 / 1.590 |
| `mix_cap50_aug05` | .214 / .168 / .152 | 1.065 / .801 / .762 | 1.799 / 1.341 / 1.312 |
| `mix_cap50_aug15` | .222 / .174 / .157 | .957 / .649 / .592 | 1.675 / 1.026 / .980 |
| `mixgr_cap50` (prior only) | .241 / .208 / .196 | .778 / .692 / .664 | 1.486 / 1.533 / 1.555 |
| **`eqgr_cap50`** | .211 / .167 / .149 | .971 / **.587 / .502** | 1.562 / **.654 / .532** |
| `eqgr_cap50_bfix` | .209 / .165 / .149 | .974 / .586 / .501 | 1.488 / .650 / .540 |
| *for reference, trained on all magnitudes:* `mix_nll` | .208 / .164 / .148 | .857 / .591 / .556 | 1.260 / .861 / .858 |
| *trained on all magnitudes:* `eqdgr_nll` | .205 / .160 / .142 | .845 / .554 / .468 | 1.258 / .600 / .484 |

Δ `eqgr_cap50` − `mix_cap50` (cluster bootstrap): bulk +.003 / +.003 / +.0005; M≥5 −.18 / −.34 /
−.39 and M≥6 −.40 / −.97 / −1.07, every interval excluding zero (e.g. M≥6 at 5 s [−1.35, −.88]).

**Signed bias by magnitude bin** (mean of median − label, 1 / 3 / 5 s):

| arm | 5.0–5.5 | 5.5–6.0 | 6.0–6.5 | 6.5–7.0 |
|---|---|---|---|---|
| `mix_cap50` | −.92 / −.74 / −.70 | −1.23 / −1.02 / −.99 | −1.78 / −1.43 / −1.41 | −2.07 / −1.74 / −1.71 |
| `mix_cap50_aug15` | −.73 / −.51 / −.45 | −.91 / −.62 / −.59 | −1.47 / −.86 / −.82 | −1.88 / −1.15 / −1.11 |
| `eqgr_cap50` | −.62 / −.38 / −.34 | −.73 / −.36 / −.35 | −1.35 / **−.30 / −.24** | −1.73 / −.54 / −.45 |
| `mix_nll` (all data) | −.67 / −.43 / −.40 | −.74 / −.52 / −.52 | −1.17 / −.68 / −.69 | −1.19 / −1.05 / −1.01 |

**What this shows.**
1. The free mixture saturates at the cap, as Proposition 3 predicts: it under-predicts M6–6.5
   events by 1.4 units at 3–5 s. The equivariant head, which never saw an M ≥ 5 label, is within
   .24–.30 of them, and on M ≥ 6 its MA-label error is below the free mixture trained on the full
   catalogue (.65 vs .86 at 3 s, .53 vs .86 at 5 s). *[Corrected 05:10: on the independent M_EXT
   and MW_SIPPL labels this is a tie at 3 s and a modest gain at 5 s; see the audit entry.]*
   Bulk error is unchanged.
2. The gain is the equivariant likelihood, not the prior: the prior-only head pushes mass up
   indiscriminately (+0.6 bias at M4.5–5, bulk +.03 to +.05) and stays saturated above M6.
   *[Corrected 05:10: this control is confounded by the label-binning bug at the cap; rerun
   pending as `mixgr_cap50b`.]*
3. Augmentation helps the free mixture (M≥6 1.59 → .98 at 5 s at ±1.5 decades) at a bulk cost
   (+.006 to +.015) and remains far behind the equivariant head at 3–5 s (M≥6 .98 vs .53).
4. At 1 s every head saturates at M6+ (bias −1.2 to −1.8), consistent with the physical limit
   of about M5.7 for a 1 s window (LITREVIEW_2026-10-30.md): equivariance cannot recover
   information that is not yet in the waveform. At 3 s (limit ≈ M6.5–6.7) the equivariant head's
   bias stays near −.3 through M6.5 and grows above it; at 5 s (limit ≈ M7) it is −.45 at M6.5–7.
5. Pinning the slope to the b-value changes nothing for this head (rows 5–6), as Proposition 2
   predicts for single-station error.

**A training leak in the capped distance-marginalized head.** `eqdgr_cap50` has bulk MAE 4.0–4.4
(`eqdgr_cap50_bfix` 1.2–1.5): in four of five folds it puts 30–80% of the probability of M < 3
records above M6. Cause: the head normalizes a joint over (distance bin, magnitude), and
truncating that joint lets training raise the true bin's probability by moving the wrong bins'
components above the cap, where the truncated prior hides them; at test time they reappear.
The INSTANCE run capped at M4.0 did not do this (per-fold M<3 mass above M5 ≤ .0004). THEORY.md
(remark after Proposition 3) gives the argument and the fix: truncate only the magnitude
conditional and take the distance marginal from the untruncated joint (`--cap-latent
conditional`, bit-identical to the old loss without a cap, unit-tested against the old code).
`eqdgr_cap50_cond`, `eqdgr_cap50_bfix_cond` and `eqdgr_cap40_cond` are training now, together
with two more existing-method baselines under the same cap: κ ≡ 1 (`eqgr_k1_cap50`, the Zhang,
Zhang & Tian 2021 construction) and the published MagNet architecture (`magnet_cap50`,
`magnet_cap40`). The small-cluster-robust statistics (`robust_tail.py`) run on the full set.

## 2026-10-30 04:10 UTC — Fusion with co-located instruments merged into one station: conclusions unchanged

**Why.** The audit noted that INSTANCE has several instruments (e.g. HH and HN channels) at one
site, so "k stations" could count one site twice and its fused errors could be optimistic. The
fusion and wall-clock studies were rerun with `--dedupe-stations` (geometric mean of the
co-located instruments' posteriors before fusion), three seeds each; `results/*dedup*`.

**Result.** Chile has one instrument per site and is unchanged to the third decimal; GEOFON moves
by ≤ .013. On INSTANCE the median number of distinct stations with data at 20 s after the first
P drops from 14 to 11, so about a fifth of the "stations" were co-located instruments. At all
stations, M≥5 event errors move by ≤ .02 (e.g. free mixture with the prior divided out .327 /
.259 / .257 vs .331 / .264 / .252 before; `eqdgr` .244 / .221 / .252 vs .262 / .221 / .229), and
all-event errors change by +.001 to −.020 (mostly small decreases). The naive product still
fails: the free mixture's M≥5 error at all stations is .906 / .636 / .580, against .327 / .259 /
.257 with the prior divided out and .653 / .635 / .649 at its nearest station alone (so at 1 s
the product is worse than one station, at 3–5 s it barely beats it). In wall-clock time the free
mixture's naive-product estimate still stays at .58–.74 for 20 s while the structured heads with
the prior divided out reach about .3 within 4–6 s. No conclusion in the fusion entries changes.

## 2026-10-21 01:40 UTC — Multi-station fusion: the naive product of free posteriors makes large-event estimates *worse* as stations are added; dividing out the training prior repairs it; the equivariant heads keep their advantage at the event level on INSTANCE and Chile, tie on GEOFON

**Question.** EEW systems combine stations. For a factorized posterior p(m|x) ∝ L(m|x)·π(m),
Bayes gives p(m|x₁..x_k) ∝ Π_i L(m|x_i)·π(m) with the prior counted once. A posterior with no
identifiable prior factor can only be multiplied (Π p_i: prior counted k times), averaged, or
divided by an *assumed* prior before multiplying. Four rules were compared on every head
(`multistation.py`; stations ordered by hypocentral distance as a proxy for arrival order,
each with the same d seconds; events with ≥ k usable stations; event-level MAE, median
action; cluster bootstrap over sequences; three seeds per dataset):

* `post_prod` Π_i p(m|x_i) — the naive rule;
* `post_mean` (1/k) Σ_i p(m|x_i);
* `hist_adj` Π_i p(m|x_i)/π̂(m) · π̂(m), π̂ = the fold's training-label histogram, smoothed
  (σ = 0.25) and floored (10⁻⁵) — the logit-adjustment analogue, available to any posterior;
* `lik_prior` Π_i [p(m|x_i)/e^φ(m)] · e^φ(m), with φ the head's own learned prior factor
  (GR heads only).

Full-precision log-posteriors were re-exported from the fold checkpoints (`export_logpmf.py`;
the saved float16 PMFs underflow in the tail). Tables: `results/multistation_summary_*.md`
(every k, every deadline, per seed); figures `figures/multistation_*_s1.png`.

**1. The naive product fails on large events, on all three catalogues** (three-seed means,
event-level MAE at 1 / 3 / 5 s, k = all stations of the event, median ≈ 15 stations on INSTANCE):

| | nearest station only | Π posteriors (naive) | posterior mean | ÷ training prior (`hist_adj`) |
|---|---|---|---|---|
| INSTANCE M≥5 (31 events), free mixture | .670 / .649 / .629 | **.921 / .651 / .600** | .932 / .655 / .603 | .331 / .264 / .252 |
| Chile M≥6 (12), free mixture | 1.022 / .798 / .790 | **1.281 / .870 / .846** | 1.234 / .794 / .780 | .840 / .547 / .526 |
| GEOFON M≥7 (50), free mixture | 1.546 / 1.150 / .999 | **1.562 / 1.226 / 1.071** | 1.517 / 1.219 / 1.069 | .864 / .693 / .603 |

Adding every station of the event to the free mixture's posterior product leaves the M≥5 /
M≥6 / M≥7 error equal to or *worse* than the nearest station alone (INSTANCE 1 s: .67 → .92).
This is prior over-counting (THEORY.md, Proposition 2): each posterior carries the
Gutenberg–Richter prior, so the product carries it k times and is pulled toward the bulk.
Averaging does not help. Dividing each posterior by the training-label histogram before
multiplying removes it: .25 / .53 / .60 at 5 s. Seeds agree (every one of the 9 seed ×
deadline cells has the naive product worse than `hist_adj` on the top tail, CIs exclude zero).

**2. The equivariant heads are far less sensitive to the rule, and their nearest-station
estimates are already better** (same layout; eqgr = plain, eqdgr = distance-marginalized):

| | nearest station | Π posteriors | `hist_adj` | own factor once (`lik_prior`) |
|---|---|---|---|---|
| INSTANCE M≥5, eqgr | .548 / .379 / .432 | .889 / .514 / .392 | .304 / .202 / .207 | .698 / .401 / .309 |
| INSTANCE M≥5, eqdgr | .621 / .728 / .616 | .733 / .346 / .277 | .262 / .221 / .229 | **.273 / .203 / .226** |
| Chile M≥6, eqgr | .811 / .397 / .300 | 1.146 / .361 / .235 | .730 / .314 / .226 | 1.017 / .342 / .221 |
| Chile M≥6, eqdgr | .736 / .384 / .299 | 1.241 / .339 / .212 | .751 / .302 / .217 | 1.032 / .319 / **.199** |
| GEOFON M≥7, eqgr | 1.621 / 1.197 / .972 | 1.630 / 1.231 / 1.066 | 1.027 / .873 / .687 | 1.636 / 1.236 / 1.070 |
| GEOFON M≥7, eqdgr | 1.362 / 1.025 / .802 | 1.450 / 1.131 / .956 | 1.039 / .728 / .609 | 1.458 / 1.136 / .961 |

* With the best rule for each head, at all stations and 5 s: INSTANCE M≥5 eqgr .207 and
  eqdgr .226 against the mixture's .252; Chile M≥6 eqdgr .199 and eqgr .221 against .526;
  GEOFON M≥7 eqdgr .609 against .603 (tie). Paired against the mixture's `hist_adj`
  (seed 1; sign over three seeds): INSTANCE eqgr `hist_adj` M≥5 −.001 / −.058 / **−.038
  [−.074,−.001]** (3/3 seeds negative at every deadline); eqdgr `lik_prior` −.051 / −.054 /
  −.012 (3/3 negative; CIs include zero with 31 events). Chile eqdgr `lik_prior` M≥6 −.170
  [−.308,+.029] / **−.337 [−.581,−.121]** at 3 / 5 s and eqgr `lik_prior` **−.316
  [−.531,−.134]** at 5 s (3/3 negative). GEOFON: the mixture's `hist_adj` is as good as any
  rule of any head on M≥7 (eqdgr `hist_adj` +.008 [−.098,+.109]; eqgr +.126 [−.009,+.262]).
* **Bulk (all events, event level) at all stations** is where the factorized rule pays:
  INSTANCE eqdgr `lik_prior` .239 / .190 / .168 and eqgr `lik_prior` .243 / .192 / .168
  against the mixture's best (`hist_adj`) .250 / .201 / .176 — Δ = **−.007 [−.016,+.002] /
  −.008 [−.011,−.004] / −.007 [−.009,−.004]** for eqdgr (3/3 seeds negative at every
  deadline); Chile eqdgr `lik_prior` .106 / .082 / .073 vs .102 / .084 / .078 (3 s −.002,
  5 s **−.004 [−.006,−.003]**, 3/3). On GEOFON the histogram rule costs bulk (+.03 for the
  mixture at 5 s; it destroys eqdgr's broad posteriors: 1.02) while the factorized rule does
  not (eqdgr `lik_prior` .350 vs the naive .348).

**3. Why the learned prior factor is only sometimes the right prior to divide out.** Proposition 2
(THEORY.md) shows that the tail slope of the factor is not identified from single-station
data: an exponential tilt of a Gaussian mixture is a shifted mixture, so any slope can be
absorbed by the likelihood head. The learned slopes confirm this — they are arbitrary and
differ by head and catalogue, and fusion with the learned factor works exactly where the
slope happens to be close to the catalogue's:

| catalogue (empirical ln-density slope above M3.5–4.8) | eqgr β | mixgr β | eqdgr β | `lik_prior` vs `hist_adj` at 5 s, top tail |
|---|---|---|---|---|
| INSTANCE (−2.29 / unit, b = 1.00) | −0.81 | −0.17 | **−1.85** | eqdgr: equal (.226 vs .229); eqgr: worse (.309 vs .207) |
| Chile (−1.79, b = 0.78) | −0.60 | −0.04 | −0.46 | eqdgr: better (.199 vs .217); eqgr: equal; both worse at 1 s |
| GEOFON (−1.32, b = 0.57) | +0.02 | +0.02 | +0.02 | identical to the naive product (flat factor) |

(β in nats per magnitude unit, mean over folds.) mixgr's factor is nearly flat on every
catalogue, so its `lik_prior` is the naive product in disguise (INSTANCE M≥5 .878 / .604 /
.534); eqgr's is flatter than the catalogue's, so counting it once under-corrects; eqdgr's is
close to the catalogue's on INSTANCE and its rule is the best there on both axes. **The prior
a fusion rule must divide out is the label distribution the posteriors were trained under,
not a learned factor whose slope is free.** A model whose factor is pinned to the catalogue
b-value during training (β fixed, not learned) would make the two coincide; that is the
natural next experiment and was not run.

**4. Practical reading.** (i) Never multiply free neural posteriors across stations without
dividing out the training prior: on all three catalogues the naive product makes M≥5–7
estimates worse than the nearest station alone, by up to .25 units. (ii) The histogram rule
is a one-line fix but needs a smoothing/floor choice and is fragile where posteriors are broad
(GEOFON bulk +.03 to +.7). (iii) The structured heads give better single-station estimates of
large events (nearest station: INSTANCE eqgr .43 vs .63, Chile .30 vs .79 at 5 s) *and* better
fused bulk error at every deadline; at the fused tail they are better on INSTANCE and Chile
and tie on GEOFON. (iv) The decision rule matters less than the fusion rule: all numbers are
medians; mean-action values are in the JSONs.

**5. Signed bias of the fused M≥5 estimates (INSTANCE seed 1, k = all, 1 / 3 / 5 s).** The naive
product is more biased than the nearest station (mixture −.93 / −.67 / −.62 vs −.62 / −.56 /
−.53): over-counting pulls down. `hist_adj` leaves the mixture at −.25 / −.22 / −.15 and eqgr at
−.18 / −.03 / −.03; eqgr with its own flat factor stays at −.69 / −.38 / −.29 (under-corrected,
as Proposition 2 predicts for a learned slope of −0.81 against −2.29), while eqdgr with its own
factor (slope −1.85) is nearly unbiased, −.13 / +.06 / +.05.

**6. Sensitivity of the histogram rule (INSTANCE seed 1, k = all, M≥5 / bulk at 5 s;
`results/multistation_instance_s1_hist_*.json`).** Default (σ = 0.25, floor 10⁻⁵): mixture
.242 / .176, eqgr .205 / .172, eqdgr .231 / .175. σ = 0.1: .252 / .179, .213 / .175, .254 / .181.
σ = 0.5: .304 / .176, .255 / .170, .285 / .172. Floor 10⁻⁴: .284 / .176, .224 / .171, .191 / .174.
Floor 10⁻⁶: .298 / .176, .229 / .172, .488 / .177. The level of the fused tail error moves by
±.06 for the mixture and the ordering eqgr < mixture holds in every setting at 3 and 5 s; the
distance-marginalized head's broad posteriors make it floor-sensitive (.19 to .49), which is
why its own factor, which needs no such choice, is the better rule for it.

## 2026-10-30 01:30 UTC — Independent audit and literature review: what they change, and what is being done

Two independent sessions reviewed the study on 30 Oct: an adversarial audit of code and
evaluation (`AUDIT_2026-10-30.md`) and a literature search for prior art (`LITREVIEW_2026-10-30.md`).

**What the audit confirmed.** No leakage that invalidates the comparisons: folds, clusters and
held stations are clean; inputs are causal on INSTANCE; normalization uses training rows only;
every arm uses the same schedule; `eqgr` was specified before its results; an independent
recomputation from the saved fold PMFs reproduces the headline numbers to four decimals. The
**M≥4 claims are robust** (194 clusters; eqgr ensemble Δ at 5 s −.028, jackknife [−.055,−.001]).

**What it found, and the response:**

| finding | response |
|---|---|
| H1: the 31 INSTANCE M≥5 events are 11 sequences; Central Italy carries ~72% of every M≥5 gain; outside it the gain is −.06 to −.09, and a small-cluster jackknife interval includes zero for every M≥5 comparison except eqgr on held stations | `robust_tail.py` (jackknife t(G−1), LOCO, Δ without the largest cluster, cluster sign tests, observed Δ) is being written; the README will report M≥5 as "31 events in 11 sequences" with those intervals. The decisive test of the tail claim moves to catalogues with many sequences: STEAD (718 M≥5 events in 456 clusters, pre-registered) and the capped-training test (346 M≥4 events above the cap). |
| H2: false-M4 rates from 21 Oct onward were per 10³ written as per 10⁴ in five places, hiding that `eqdgr` doubles the false-alarm rate on unseen stations (17.9 vs 9.0 per 10⁴ at 1 s) | Corrected in README, PAPER and FINDINGS (erratum, this commit series). |
| M1: Chile's labels (MA) are amplitude-derived; scored against independent magnitudes (M_EXT, MW_SIPPL) most of the M≥5 and about half of the M≥6 gain disappears | Relabelled Chile caches are being built; mix and eqdgr will be retrained on M_EXT and MW_SIPPL. Until then the Chile tail gain is described as fidelity to an amplitude-based label. |
| M2: the 45-cell sign tests treat dependent cells as independent | Replaced by cluster-level sign tests in `robust_tail.py`; the old p-values are withdrawn. |
| M3: `eqdgr`, the 20-epoch model and the "best fusion rule" were chosen on the same folds | Pre-registered, locked test on STEAD (`PREREGISTRATION_STEAD.md`, committed before training). "Single best model" is now marked post hoc. |
| M4: fusion counted co-located instruments (HH+HN) as separate stations | `--dedupe-stations` merges each station's instruments into one posterior; the fusion studies are being rerun. |
| L1: reported Δ are bootstrap means | `robust_tail.py` reports observed Δ. |
| L2–L8 | Noted; all arm-neutral (Visso duplicate entries, GK window residue, temporal "standard split", GEOFON resampling, oracle bulk-capped numbers, Chile picker). |

**What the literature review found.** The κ = 1 core (an exactly log-amplitude-equivariant
predicted magnitude distribution for EEW) is anticipated by Zhang, Zhang & Tian 2021 and the arXiv
versions of Zhang & Zhang; the joint magnitude–distance posterior with distance marginalized is
the Gutenberg algorithm's structure (Meier et al. 2015, kNN); the algebra of Propositions 1–2 is
classical (Malmquist, Tinti & Mulargia, exponential tilting); dividing the training prior out of
fused posteriors is textbook (Kittler, BCM, ProbEn, Geffner et al.). Not found anywhere: a learned
waveform-dependent slope κ(s) inside a mixture sharing the shift; a learned GR-tail prior factor
kept at test time and shaped to preserve equivariance; the non-identifiability of that factor's
slope and its fusion consequence; the diagnosis that EEW posterior fusion double-counts the prior
(the Gutenberg algorithm itself multiplies posteriors); and a controlled capped-training
extrapolation test. Response: a κ ≡ 1 ablation (the Zhang construction on the same trunk) is
queued on INSTANCE, on the capped test and on STEAD; NOVELTY.md and PAPER.md will cite the
precedents; one in-domain 2026 paper (P. Zhang, X. Zhang & Tian, single-station on INSTANCE) could
not be read and is being retried.

## 2026-10-30 00:30 UTC — Held-station test of the 20-epoch distance-marginalized head: longer training helps on seen stations and hurts on unseen ones, for both models; at unseen stations the 10-epoch head is the best model

`eqdgr_nll_e20_hs` and `mix_nll_e20_hs` (20 epochs, same 20% of INSTANCE stations withheld,
seed 1), evaluated together with the 10-epoch held-station arms against the 20-epoch mixture
(`eval_hs_e20_{held,seen}.json`). Δ vs mix_nll_e20_hs, median action, 1 / 3 / 5 s:

| | held stations: bulk | held: M≥5 | seen stations: bulk | seen: M≥5 |
|---|---|---|---|---|
| eqdgr, 20 epochs | +.0002 / −.0032 / **−.0044** | −.070 / −.111 / −.121 (CIs reach +.003 to +.08) | **−.0077 / −.0105 / −.0120** | −.119 / **−.120 / −.124** |
| mixture, 10 epochs | **−.0049 / −.0083 / −.0064** | **+.079 / +.064 / +.045** | **−.0038 / −.0038 / −.0034** | **+.055 / +.057** / +.048 |
| eqdgr, 10 epochs | **−.0076 / −.0102 / −.0101** | −.079 / **−.137 / −.172** | **−.0049 / −.0079 / −.0102** | −.114 / **−.134 / −.148** |

* On stations seen in training, 20 epochs improve the bulk of the distance-marginalized head
  by about .003–.005 over its 10-epoch version (as on the full data, 22 Oct entry).
* On stations never seen in training the opposite holds for both models: the 10-epoch mixture
  has lower bulk error than the 20-epoch mixture (−.005 to −.008), and the 10-epoch
  distance-marginalized head beats its 20-epoch version by .006–.008 bulk and .01–.05 on M≥5.
  Longer training fits station-specific detail that does not transfer.
* So the 22 Oct "single best INSTANCE model" statement needs a qualifier: 20 epochs for a
  fixed network, 10 epochs for a network that must serve new stations. Against an equally
  trained mixture the distance-marginalized head wins on both subsets at both lengths.

## 2026-10-22 22:10 UTC — Fusion with the 20-epoch distance-marginalized head: the histogram rule is its best fusion prior (M≥5 .22 / .19 / .23 at all stations, three seeds); its own learned factor no longer is, as Proposition 2 predicts for a re-trained split

`multistation.py` and `fusion_timeline.py` on the three 20-epoch seeds of the mixture and the
distance-marginalized head (`multistation_summary_instance_e20.md`,
`fusion_timeline_summary_instance_e20.md`). Event-level M≥5 MAE at k = all stations, 1 / 3 / 5 s,
three-seed means (all-events MAE at 5 s in parentheses):

| rule | mixture, 20 epochs | distance-marginalized, 20 epochs |
|---|---|---|
| naive product | .908 / .641 / .577 (.178) | .739 / .327 / .270 (.171) |
| ÷ training histogram | .368 / .296 / .285 (.168) | **.224 / .193 / .229** (.167) |
| own factor once | — | .269 / .319 / .313 (.171) |
| nearest station only | .676 / .640 / .684 | .911 / .864 / .727 |

* With the histogram rule the 20-epoch head fuses to .22 / .19 / .23, better than the 10-epoch
  head's best rule (.27 / .20 / .23) and far better than the 20-epoch mixture's (.37 / .30 / .29),
  at equal fused bulk (.167 vs .168 at 5 s). In wall-clock time it is ahead of the mixture's
  best rule from 6 s after the first P (.27 vs .34 at 6 s, .23 vs .33 at 10 s, .23 vs .29 at
  20 s).
* Its *own* factor counted once is now the worse rule (.27 / .32 / .31), whereas for the
  10-epoch head it was the best: the learned tail slope moved with training length, from
  −1.85 nats per unit at 10 epochs (folds −1.34 to −2.31) to −2.73 at 20 epochs (−2.30 to
  −3.04, all three seeds alike), now steeper than the catalogue's −2.29, so counting it once
  over-corrects — exactly the non-identifiability of Proposition 2, and the same over-correction
  the pinned slope showed on 21 Oct. The practical rule stands: divide out the training-label
  prior, and validate the fused bias per model.
* Its nearest-station estimate of M≥5 events is poor (.91 / .86 / .73 vs .68 / .64 / .68 for
  the mixture; one seed 1.21 at 1 s): with longer training the head leans harder on the
  distance mixture, and the single nearest station, often the one with the most saturated
  record, mis-places the distance hypothesis. Two or more stations repair this at once (k = 4:
  .47 / .43 / .33 with the histogram rule); single-station deployment of the 20-epoch head at
  1 s should be avoided or combined with the prior-only head as in the 16:45 entry of 20 Oct.

## 2026-10-22 21:40 UTC — 20 epochs replicated: on INSTANCE the distance-marginalized head's larger bulk gain and vanishing false-alarm cost hold in three seeds; on Chile longer training helps neither model and on GEOFON it helps both, and in every case the head keeps its advantage over the equally trained mixture

20-epoch arms of the mixture and the distance-marginalized head on Chile and GEOFON (seed 1;
`chile_eval_e20.json`, `geofon_eval_e20.json`) and seeds 2–3 on INSTANCE with three-seed
ensembles (`eval_e20_ens3.json`, `eval_e20_seeds23.json`). Δ = arm − the 20-epoch mixture
(same seeds / ensemble), median action, 1 / 3 / 5 s.

| | bulk | top tail | false-M4 per 10⁴ |
|---|---|---|---|
| INSTANCE, eqdgr 20 ep, ensembles (3 v 3) | **−.0040 / −.0061 / −.0073** | M≥5 −.106 / **−.154 / −.161** | +1.6 [−0.1,+2.9] / +0.3 / −0.1 (abs. 7.9 vs 6.0 at 1 s) |
| INSTANCE, seed 2 / seed 3 | −.006 / −.009 / −.010 (both) | M≥5 −.10 / −.17 / −.16 and −.09 / −.17 / −.16 | +1.1 / +0.3 / −0.4 and +0.8 / +0.7 / +0.1 |
| INSTANCE, 10-epoch mixture ensemble vs 20-epoch | **+.0025 / +.0032 / +.0033** | M≥4 **+.019 / +.019 / +.022** | **−0.9** / −0.4 / −0.3 |
| Chile, eqdgr 20 ep | **−.0045 / −.0064 / −.0080** | M≥6 **−.107 / −.229 / −.310** | — |
| Chile, 10-epoch mixture vs 20-epoch | **−.0022 / −.0039 / −.0046** | M≥6 −.002 / **+.061** / +.029 | — |
| GEOFON, eqdgr 20 ep | **+.014 / +.009 / +.009** | M≥7 **−.073 / −.062 / −.084** | — |
| GEOFON, 10-epoch mixture vs 20-epoch | **+.020 / +.020 / +.020** | M≥7 **+.042 / +.123 / +.133** | — |

* Training length is a property of the catalogue, not of the head: 20 epochs improve the
  mixture on INSTANCE (bulk −.003, M≥4 −.02) and strongly on the small GEOFON set (bulk −.02,
  M≥7 −.04 to −.13), and slightly hurt it on Chile (bulk +.002 to +.005). The
  distance-marginalized head moves the same way on each catalogue.
* Against the equally trained mixture the head keeps its advantage everywhere: INSTANCE bulk
  −.004 / −.006 / −.007 with M≥5 −.15 / −.16 at 3 / 5 s and a 1 s false-alarm excess reduced
  from +4.0 to +1.6 per 10⁴ (n.s.; three seeds agree on the reduction); Chile bulk −.005 / −.006
  / −.008 and M≥6 −.11 / −.23 / −.31; GEOFON M≥7 −.07 / −.06 / −.08 at a bulk cost halved to
  +.009 (from +.019 at 10 epochs).
* Practical reading for INSTANCE: the 20-epoch distance-marginalized head is the single best
  model of the study on this catalogue — lower bulk error than any mixture, the same M≥5
  gain, and the mixture's false-alarm rate — and its 10-epoch version was already the most
  portable across catalogues.

## 2026-10-21 20:20 UTC — Capacity, training length and five seeds for the distance-marginalized head on INSTANCE: its gains hold or grow at 1.5× width and at 20 epochs, and the five-seed ensembles replicate the three-seed result

`eqdgr_nll_w15` (trunk width ×1.5) and `eqdgr_nll_e20` (20 epochs) against the matching mixture
arms (`eval_w15_3.json`, `eval_e20_3.json`), and five-seed ensembles of the mixture, plain and
distance-marginalized heads (`eval_ens5.json`; single seeds 4 and 5 in `eval_seeds45.json`).
Δ = arm − matching mixture, median action, 1 / 3 / 5 s (bold: CI excludes zero).

| | bulk | M≥4 MAE | M≥5 MAE | false-M4 per 10⁴ |
|---|---|---|---|---|
| plain, ×1.5 width | **−.0022 / −.0025 / −.0034** | **−.018 / −.021 / −.027** | −.031 / **−.109 / −.133** | +0.6 / **+1.1** / +0.8 |
| distance-marg., ×1.5 width | **−.0027 / −.0065 / −.0083** | −.021 / **−.027 / −.031** | −.112 / **−.163 / −.171** | **+4.1 / +2.9 / +1.6** |
| plain, 20 epochs | −.0001 / **−.0017 / −.0038** | **−.014 / −.011 / −.017** | −.047 / **−.098 / −.110** | +0.1 / −0.2 / +0.1 |
| distance-marg., 20 epochs | **−.0064 / −.0084 / −.0104** | +.002 / −.007 / −.014 (n.s.) | −.065 / **−.120 / −.142** | +1.6 / +0.2 / −0.3 |
| plain, 5-seed ensembles | −.0004 / −.0012 / **−.0023** | **−.015 / −.014 / −.024** | −.022 / **−.095 / −.138** | **+1.6** / +0.5 / +0.5 |
| distance-marg., 5-seed ensembles | −.0007 / **−.0032 / −.0047** | −.015 / −.017 / −.023 (n.s.) | −.119 / **−.168 / −.183** | **+4.0 / +1.6 / +0.9** |

* Capacity: at 2.2× the parameters the distance-marginalized head's bulk gain is larger
  (−.008 at 5 s vs −.005 at the standard width) and its M≥5 gain unchanged, so the gain is not
  what a bigger free mixture would also learn.
* Training length: at 20 epochs its bulk gain triples (−.0064 / −.0084 / −.0104) and its 1 s
  false-alarm excess falls from +4.0 to +1.6 per 10⁴ (n.s.), while its M≥4 gain shrinks to insignificance and the M≥5 gain
  is kept (−.12 / −.14 at 3 / 5 s). Longer training moves this head toward the bulk; the
  tail gain survives.
* Seeds: the five-seed ensembles reproduce the three-seed ones (plain: M≥5 −.022 / −.095 /
  −.138 vs −.024 / −.105 / −.149; distance-marginalized: −.119 / −.168 / −.183 vs −.122 /
  −.174 / −.189), and seeds 4 and 5 individually fall inside the spread of seeds 1–3. The
  mixture's own seed-to-seed spread (seed 5 − seed 4) is −.001 / −.002 / −.002 bulk and ±.01
  M≥5, i.e. an order of magnitude below the between-head differences.

## 2026-10-21 13:00 UTC — Seed × fold sign test for the distance-marginalized head on INSTANCE: ahead of the mixture on M≥5 error in 33/45 cells (p = .002) and on bulk in 30/45 (p = .04); M≥4 event error is a coin flip

`seed_consistency.py --pairs mix_nll:eqdgr_nll,…_s2,…_s3` (`results/seedcons_eqdgr_nll_vs_mix_nll.json`),
median action, 3 seeds × 5 folds × 3 deadlines, same-seed pairs:

| metric | cells with eqdgr better | by deadline (1 / 3 / 5 s) | median Δ | sign-test p |
|---|---|---|---|---|
| bulk MAE | 30/45 | 6/15 / 12/15 / 12/15 | −.0022 | .036 |
| M≥4 MAE | 28/45 | 6/15 / 10/15 / 12/15 | −.0036 | .13 |
| M≥4 event-MAE | 22/45 | 7/15 / 7/15 / 8/15 | +.0004 | 1.0 |
| M≥5 MAE | 33/45 | 7/15 / 13/15 / 13/15 | −.050 | .0025 |

Pooled per seed, eqdgr − mix: M≥5 −.153 / −.187 / −.200 (seed 1), −.115 / −.158 / −.174
(seed 2), −.119 / −.185 / −.212 (seed 3) at 1 / 3 / 5 s; bulk −.0003 / −.0028 / −.0048,
−.0003 / −.0026 / −.0048, +.0003 / −.0033 / −.0055. Compared with the plain head's sign test
(M≥4 better in 36/45, all nine exceptions in the Emilia fold), the distance-marginalized head
wins the M≥5 cells more consistently at 3 and 5 s (13/15 each) but is a coin flip at 1 s and on
the M≥4 *event* error, where its gains at the record level come with more 1 s false alarms.
The exceptions are again concentrated in the Emilia fold (fold 1, M_L-labelled large events):
it holds 9 of the 15 bulk cells and 7 of the 12 M≥5 cells where eqdgr is worse, and all 9 of its
own M≥4 cells; folds 0 and 3 (Central Italy, the largest M_w events) have no M≥4 or M≥5 cell
where eqdgr is worse.

## 2026-10-21 12:50 UTC — Calibration of the three-seed ensembles on INSTANCE: the distance-marginalized head has the best Brier score for P(M≥4) and P(M≥5) at 3 and 5 s and is the best-calibrated for P(M≥4); at 1 s it is slightly over-confident

`calibration_check.py` on the three-seed ensembles (`results/calibration_ens3.json`; reliability
diagram `figures/reliability_ens3.png`). Brier score (reliability / resolution components),
mixture → plain equivariant → distance-marginalized:

| | P(M≥4) | P(M≥5) |
|---|---|---|
| 1 s | .01068 → .01070 → .01083 (rel. .00001 / .00000 / .00008) | .00110 → .00110 → .00114 |
| 3 s | .00911 → .00904 → **.00903** | .00095 → **.00091** → .00092 |
| 5 s | .00857 → .00830 → **.00822** (res. .00870 / .00895 / .00903) | .00091 → .00083 → **.00082** |

Reliability bins at 5 s: for P(M≥4) the mixture is under-confident in every mid bin (predicted
.27 / .42 / .57 / .72 / .85 → observed .31 / .47 / .62 / .79 / .90), the plain head less so
(.28 / .43 / .60 / .75 / .87) and the distance-marginalized head is on the diagonal (.26 / .42 /
.57 / .73 / .85). For P(M≥5) the mixture under-predicts (.14 → .21, .27 → .36, .42 → .52), the
plain head is close in the middle (.14 / .27 / .46) and the distance-marginalized head
over-predicts (.14 → .09, .27 → .22, .42 → .37; top bin .97 → .77 for both structured heads).
So the distance-marginalized head's higher false-M4 rate is the price of its sharper, on
average correct, M≥4 probabilities, and its M≥5 probabilities are somewhat too confident; the
mixture's probabilities are too low throughout, which is the same under-estimation seen in the
point estimates.

**Chile (`results/chile_calibration_ens3.json`, 67 M≥5 events).** The picture differs: for
P(M≥5) the Brier scores tie (5 s: mixture .00046, plain .00044, distance-marginalized .00046; at
1 and 3 s the mixture is marginally better, .00063 vs .00070 and .00047 vs .00050) and the
reliability terms are tiny for all three, but in the mid bins at 5 s the structured heads
over-predict (predicted .42 / .57 / .73 → observed .27 / .41 / .60 for the plain head and .23 /
.39 / .53 for the distance-marginalized head) where the mixture is closer (.37 / .50 / .69). On
this catalogue the structured heads' better point estimates of M≥6 events do not come with
better-calibrated tail probabilities; a probability-based alert would need recalibration.

## 2026-10-21 12:50 UTC — Event magnitude versus time since the first P arrival: with the naive rule the free mixture's M≥5 estimate never improves as stations arrive; with the prior divided out the equivariant heads reach .3 within 4 s of the first P on INSTANCE and Chile

`fusion_timeline.py`: at wall-clock time T after an event's first P, each station contributes its
posterior at the largest deadline it has reached (1, 3 or 5 s; none below 1 s). Arrival times are
t_i = hyp_km / 6.5 km/s (a stated proxy; on Chile the measured per-station picks give the same
curves, `fusion_timeline_summary_chile_measured.md`). Event-level MAE, median action, three seeds
(`fusion_timeline_summary_{instance,chile}.md`; figures `figures/fusion_timeline_*.png`;
GEOFON is single-station at every T — stations 300–2,000 km apart — and is reported for
completeness only).

**INSTANCE, 31 M≥5 events (median stations with data: 3 at T = 2 s, 6 at 4 s, 8 at 6 s, 14 at
15 s), three-seed means:**

| rule | T = 2 s | 3 s | 4 s | 6 s | 8 s | 10 s | 15 s | 20 s |
|---|---|---|---|---|---|---|---|---|
| mixture, naive product | .61 | .70 | .75 | .69 | .68 | .68 | .63 | .60 |
| mixture, ÷ training histogram | .43 | .39 | .34 | .31 | .32 | .31 | .27 | .26 |
| plain equivariant, ÷ histogram | .45 | .37 | .31 | **.24** | **.25** | **.23** | **.22** | **.21** |
| distance-marginalized, own factor once | .54 | .37 | .35 | .30 | .29 | .26 | .23 | .24 |
| all events (bulk): mixture naive / mixture ÷ hist / eqgr factor / eqdgr factor at 20 s | | | | | | | | .182 / .176 / **.167** / .169 |

**Chile, 12 M≥6 events (median stations: 1 at 2 s, 2 at 4 s, 3 at 6 s, 7 at 20 s):**

| rule | T = 2 s | 3 s | 4 s | 6 s | 8 s | 10 s | 15 s | 20 s |
|---|---|---|---|---|---|---|---|---|
| mixture, naive product | 1.03 | .85 | .88 | .88 | .95 | .87 | .85 | .85 |
| mixture, ÷ training histogram | 1.00 | .75 | .71 | .67 | .69 | .59 | .54 | .55 |
| plain equivariant, ÷ histogram | .84 | .39 | .36 | .28 | .25 | .23 | .20 | .22 |
| distance-marginalized, own factor once | .77 | **.34** | **.28** | **.24** | .26 | .23 | **.17** | **.19** |

* With the naive product the free mixture's large-event estimate does not improve as stations
  arrive: on INSTANCE it is *worse* at 4–10 s than at 2 s (.75 vs .61), on Chile flat at .85–.95.
  Paired against the mixture's histogram rule, the naive rule is worse by +.32 to +.36 (INSTANCE,
  CIs exclude zero from T = 4 s) and +.20 to +.32 (Chile, from 4 s). This is the over-counting of
  the 01:40 entry seen in wall-clock time: every additional station adds another copy of the
  prior.
* With the prior divided out, the structured heads converge fastest: on Chile the M≥6 error is
  .28–.36 four seconds after the first P against .71 for the mixture's best rule (Δ −.33 to −.41,
  CIs exclude zero from T = 3–4 s, 3/3 seeds), and .17–.20 at 15 s against .54. On INSTANCE
  the plain head reaches .24 at 6 s against .31 (Δ −.04 to −.07, n.s. with 31 events; 3/3 seeds
  below the mixture at every T ≥ 3 s), and the fused bulk at 20 s is best for the equivariant
  factors (.167 / .169 vs .176).
* The 2 s column is the nearest one to three stations with 1 s of data each: all rules agree and
  all are poor (INSTANCE .43–.61, Chile .77–1.03). The information arrives with the 3 s and 5 s
  windows of the first stations, between 3 and 6 s after the first P.

## 2026-10-21 10:50 UTC — Bias by magnitude bin on all three catalogues: the structural heads cut the large-event under-estimation by half to two thirds on INSTANCE and Chile, by a tenth on GEOFON

Mean signed error of the median action per 0.5-unit label bin, three-seed ensembles
(`bias_by_magnitude.py`; figure `figures/bias_by_magnitude_all.png`; full table
`results/bias_by_magnitude.md`, 509 rows). Records, not events, so sequences with many stations
dominate the top bins (INSTANCE [6.5, 7.0) is the 2016 Norcia M6.5, 75 records).

| catalogue, bin (records) | mixture | plain equivariant | distance-marginalized |
|---|---|---|---|
| INSTANCE [6.0, 6.5) (89), 5 s | −.72 | −.38 | **−.20** |
| INSTANCE [6.5, 7.0) (75), 5 s | −1.50 | −.65 | **−.36** |
| INSTANCE [6.5, 7.0), 1 s | −1.88 | −1.66 | **−1.27** |
| Chile [6.5, 7.0) (31), 5 s | −1.01 | −.41 | **−.31** |
| Chile [8.0, 8.5) (6), 5 s | −1.88 | **−.51** | −.56 |
| Chile [8.0, 8.5), 1 s | −2.67 | −2.26 | **−2.13** |
| GEOFON [7.5, 8.0) (113), 5 s | −1.29 | −1.22 | **−1.16** |
| GEOFON [8.0, 8.5) (38), 5 s | −1.74 | −1.72 | **−1.56** |

The small-magnitude bins are identical across heads (the prior-dominated regime), the curves
separate above M5 on INSTANCE and Chile exactly where the amplitude-response diagnostic
showed the free mixture saturating, and on GEOFON every head saturates with only the
distance-marginalized one slightly less so. At 1 s all heads remain strongly biased on the
largest events (the first second does not carry the information), which is the honest
reading of the 1 s columns throughout this study.

## 2026-10-21 10:15 UTC — Chile held-station test, three seeds: bulk gain on unseen stations holds in every seed; the M≥6 gain at 5 s is negative in all three (two with CIs excluding zero) and the ensemble's interval just includes zero; nothing at 1 s

Seeds 2 and 3 of `eqdgr_nll_hs` and `mix_nll_hs` on Chile (same 7 of 22 stations withheld);
per-seed Δ = eqdgr_hs − mix_hs of the same seed, and three-seed ensembles
(`chile_eval_hs_{held,seen}_{s2,s3,ens3}.json`), median action, 1 / 3 / 5 s.

**Held stations (165,670 records; 58 M≥5, 10 M≥6 events).**

| | bulk | M≥5 MAE | M≥6 MAE |
|---|---|---|---|
| seed 1 | **−.004 / −.013 / −.010** | +.047 / +.011 / −.059 | +.052 / −.092 / −.233 |
| seed 2 | −.003 / −.007 / −.003 | +.064 / −.011 / −.041 | +.047 / **−.295 [−.497,−.045] / −.294 [−.582,−.008]** |
| seed 3 | **+.004** / **−.007 / −.008** | **+.091** / +.047 / −.012 | +.163 / +.043 / **−.225 [−.439,−.014]** |
| ensembles (3 v 3) | −.001 / **−.009 [−.014,−.005] / −.007 [−.013,−.001]** | +.066 / +.010 / −.045 | +.079 / −.102 / −.263 [−.530,+.026] |

**Seen stations (339,996 records), ensembles:** bulk **−.002 / −.004 / −.006**, M≥5 −.008 /
**−.087 / −.127**, M≥6 −.024 / **−.401 [−.538,−.292] / −.477 [−.655,−.352]** — the full-data
pattern, as in seed 1.

On the 7 unseen Chilean stations the bulk gain of the distance-marginalized head holds at 3 and
5 s in every seed and in the ensemble; its large-event gain at 5 s is negative in all three
seeds (−.23 / −.29 / −.23) with two intervals excluding zero and the ensemble's just including
it (10 M≥6 events); at 3 s the seeds disagree and at 1 s the head is slightly worse on M≥5
(+.05 to +.09, one seed significant). The held-station tail evidence on Chile therefore
stays "same sign, underpowered" at 5 s and inconclusive earlier, while the INSTANCE
held-station test (09:05 entry) is where the tail claim is replicated with power.

## 2026-10-21 09:05 UTC — INSTANCE held-station test, three seeds: the distance-marginalized head's M≥5 gain on unseen stations replicates in every seed and in the ensemble

Seeds 2 and 3 of `eqdgr_nll_hs` and `mix_nll_hs` (same 20% of stations withheld, rng 0);
per-seed Δ = eqdgr_hs − mix_hs of the same seed, and three-seed ensembles
(`eval_hs_{held,seen}_{s2,s3,ens3}.json`), median action, 1 / 3 / 5 s.

**Held stations (279,812 records).**

| | bulk | M≥5 MAE | false-M4 per 10⁴ |
|---|---|---|---|
| seed 1 | −.003 / −.002 / −.004 | −.158 / **−.201 / −.217** | −3.5 / +2.7 / −2.7 (n.s.) |
| seed 2 | +.001 / −.000 / −.003 | −.159 / **−.207 / −.197** | **+9.9 / +6.0 / +4.2** |
| seed 3 | +.002 / +.002 / +.001 | −.146 / **−.215 / −.202** | +2.7 / +1.5 / −1.8 (n.s.) |
| ensembles (3 v 3) | −.000 / −.001 / −.002 (n.s.) | −.154 [−.316,+.012] / **−.216 [−.367,−.062] / −.218 [−.367,−.063]** | **+9.4 / +6.3 / +4.3** (abs. 17.9 vs 9.0, 11.4 vs 6.1, 9.0 vs 5.5) |

**Seen stations (879,437 records), ensembles:** bulk −.001 / **−.004 / −.007**, M≥4 **−.031 /
−.024 / −.027**, M≥5 **−.160 / −.195 / −.194** (all CIs exclude zero), false-M4 **+6.1 / +3.3 /
+2.0 per 10⁴** (abs. 12.4 vs 6.0 at 1 s).

The large-event gain on stations never seen in training is the same size in all three seeds
and in the ensemble (−.20 to −.22 at 3 and 5 s, intervals excluding zero), at equal bulk error;
the head's false-alarm rate roughly doubles on held stations (ensemble 17.9 vs 9.0 per 10⁴ at
1 s, Δ +9.4 [+7.5,+13.1]; +6.3 and +4.3 at 3 and 5 s). This completes the held-station evidence for the portable model on INSTANCE; the
Chile replication (seeds 2–3) is running.

## 2026-10-21 05:45 UTC — Pinned prior slope on Chile and GEOFON: harmless and useful for fusion on Chile; on GEOFON it costs the distance-marginalized head accuracy and does not make fusion competitive

`eqgr_bfix`, `eqdgr_bfix` with β = −1.79 (Chile) and −1.32 (GEOFON), seed 1
(`chile_eval_bfix.json`, `geofon_eval_bfix.json`, `multistation_{chile,geofon}_bfix.json`).

**Chile.** Single-station Δ vs the mixture is the same as with the learned slope (eqgr_bfix
M≥6 +.105 / **−.220 / −.365** vs eqgr +.108 / −.266 / −.367; eqdgr_bfix bulk **−.0028 / −.0044 /
−.0059**, M≥6 +.018 / **−.259 / −.331** vs eqdgr −.002 / −.262 / −.378). Fusion with the pinned
factor counted once, k = all, M≥6: eqgr_bfix .733 / .356 / **.201**, eqdgr_bfix .788 / .299 /
.205 (learned-slope factors: 1.017 / .342 / .221 and 1.032 / .319 / .199), both nearly unbiased
at 3–5 s (−.02 / +.09 and +.03 / +.12) against the mixture's histogram rule .837 / .511 / .533,
with the fused bulk unchanged (.079 / .073 at 5 s). On this catalogue the prescription works
for both heads.

**GEOFON.** Pinning is not harmless here: eqdgr_bfix is worse than eqdgr at one station
(bulk +.031 / +.028 / +.026 vs +.019 / +.014 / +.014; M≥7 −.059 / −.036 / −.047 vs **−.103 /
−.114 / −.141**), and eqgr_bfix is marginally worse than eqgr. Proposition 2 guarantees that a
compensating solution exists, not that training finds it; with the prior tilted by 1.3 nats per
unit over M4–9 the compensating component shifts are large, and the optimizer evidently did not
recover them in 10 epochs. Fusion with the pinned factor (k = all, M≥7: eqgr_bfix 1.052 / .855 /
.763, eqdgr_bfix .948 / .788 / .701) is better than with the learned, flat factors (1.64 / 1.24 /
1.07 and 1.46 / 1.14 / .96) but still behind the mixture's histogram rule (.805 / .696 / .590),
and costs bulk (.45–.51 vs .38 at 5 s).

**Across catalogues (seed 1, fused top-tail error at 5 s, factor counted once; learned →
pinned):** INSTANCE eqgr .299 → .258, eqdgr .226 → .286; Chile eqgr .221 → .201, eqdgr .199 →
.205; GEOFON eqgr 1.070 → .763, eqdgr .961 → .701. Pinning helps wherever the learned slope was
far from the catalogue's (INSTANCE eqgr, GEOFON) and hurts where the learned slope was already
the better fusion prior (INSTANCE eqdgr); where it is used, single-station accuracy should be
re-checked (GEOFON eqdgr lost .05–.09 on M≥7).

## 2026-10-21 05:30 UTC — Calibrated fusion prior: a cross-fitted one-parameter tilt helps where the learned factor is wrong (Chile), cannot help where bulk and tail want opposite tilts (GEOFON), and does not beat the plain histogram rule on INSTANCE

Rules `lik_prior_cal` and `hist_adj_cal` (`multistation.py`): the fusion prior (the head's own
factor, or the training histogram) gets one tilt γ·max(m − 3.5, 0) per held-out fold, γ ∈
[−3, 3] chosen on the *other* folds' fused events at k = all (leakage-free). Two objectives:
mean fused event MAE over all events (default; `multistation_*_s{1,2,3}.json`) or over the
tail events (`--cal-on tail`; GEOFON only, `multistation_geofon_s*_caltail.json`). Three
seeds; k = all stations; event-level MAE of the top tail at 1 / 3 / 5 s, three-seed means:

| | uncalibrated | calibrated (all-event objective) | calibrated (tail objective) |
|---|---|---|---|
| INSTANCE M≥5, mixture ÷ histogram | .331 / .264 / .252 | .482 / .374 / .361 | — |
| INSTANCE M≥5, eqgr ÷ histogram | .304 / .202 / .207 | .518 / .313 / .272 | — |
| INSTANCE M≥5, eqdgr own factor | .273 / .203 / .226 | .412 / .213 / .212 | — |
| Chile M≥6, mixture ÷ histogram | .840 / .547 / .526 | .907 / .632 / .602 | — |
| Chile M≥6, mixgr own factor | 1.283 / .830 / .793 | .998 / .492 / .483 | — |
| Chile M≥6, eqgr own factor | 1.017 / .342 / .221 | .758 / .317 / **.196** | — |
| Chile M≥6, eqdgr own factor | 1.032 / .319 / .199 | .781 / **.282 / .177** | — |
| GEOFON M≥7, mixture ÷ histogram | .864 / .693 / .603 | 1.135 / .797 / .658 | 1.015 / .751 / .646 |
| GEOFON M≥7, eqgr own factor | 1.636 / 1.236 / 1.070 | 1.636 / 1.292 / 1.123 | .769 / .635 / **.522** |
| GEOFON M≥7, eqdgr own factor | 1.458 / 1.136 / .961 | 1.556 / 1.210 / 1.025 | .746 / .615 / .541 |
| GEOFON M≥7, eqdgr ÷ histogram | 1.039 / .728 / .609 | .716 / .645 / .481 (bulk .82) | .685 / .698 / .542 (bulk .88) |

* **INSTANCE.** The all-event objective is dominated by the hundreds of M3.5–4.5 events that
  the hinge touches, and the tilt it picks worsens the 31 M≥5 events for the histogram rule
  (+.15 / +.11 / +.11) and leaves eqdgr's own factor about where it was (.412 / .213 / .212 vs
  .273 / .203 / .226). Fused bulk is unchanged (.168 at 5 s for eqdgr). The uncalibrated
  rules of the 01:40 entry stand.
* **Chile.** Calibration turns every GR head's own factor into its best rule at 3 and 5 s:
  eqdgr .282 / .177 and eqgr .317 / .196 (from .319 / .199 and .342 / .221), and repairs the
  prior-only head's flat factor (.793 → .483). It makes the histogram rule worse. Fused bulk
  unchanged (eqdgr .073 at 5 s, the best of any rule). Chosen tilts are consistent across
  folds (eqdgr: −0.75 to −1.0 at 5 s).
* **GEOFON.** Bulk (M4.5–6) and the M≥7 tail want opposite tilts: with the all-event
  objective the GR heads' factors stay flat and gain nothing; with the tail objective the
  equivariant heads reach .52–.54 at 5 s against the mixture's best .60, at +.20 bulk. The
  only rule that improves the GEOFON tail without a tail-specific objective, eqdgr ÷ histogram
  calibrated (.481 at 5 s), destroys the bulk (.82 vs .35). No single tilt serves both.

**What this settles.** The prior that fusion must divide out is catalogue- and head-specific
and must be validated on held-out *fused* events; it is neither the catalogue b-value (04:20
entry) nor the learned factor in general, and a one-parameter correction recovers it only
where bulk and tail agree on it (INSTANCE, Chile). What does not change across any rule,
objective or catalogue: the naive product is worst, and wherever a sensible prior is divided
out the equivariant heads give the best fused large-event error (INSTANCE .20–.23 vs .25,
Chile .18–.20 vs .53, GEOFON .52–.54 vs .60 at 5 s) and the best fused bulk on the two
local/regional networks.

## 2026-10-21 04:20 UTC — Pinning the prior slope to the catalogue b-value: single-station results unchanged (as Proposition 2 predicts); fusion with the pinned factor repairs the plain head's tail but is not the best rule overall

`--beta-fixed −2.29` (INSTANCE's empirical ln-density slope above M3.5, b = 1.00) replaces the
learned tail slope of the prior factor by a constant; `eqgr_bfix`, `eqdgr_bfix` (seed 1;
`eval_bfix.json`, `multistation_instance_bfix.json`).

**Single-station, Δ vs mix_nll (median action, 1 / 3 / 5 s).** eqgr_bfix: bulk −.0007 / −.0010 /
**−.0030**, M≥4 **−.011** / −.009 / **−.020**, M≥5 −.045 / **−.117 / −.161**, false-M4 6.2 / 5.4 /
4.8 per 10⁴ (the mixture's 6.3 / 5.2 / 4.6; the learned-slope eqgr had 7.8 / 6.0 / 5.2).
eqdgr_bfix: bulk −.0007 / **−.0027 / −.0044**, M≥5 −.124 / **−.174 / −.192**, false-M4 10.4 / 7.7 /
6.2 (learned slope: 12.2 / 7.7 / 5.5). Absolute M≥5 MAE at 5 s: .527 (eqgr_bfix) vs .548
(eqgr), .495 (eqdgr_bfix) vs .503 (eqdgr). Pinning the slope changes nothing that matters at
one station — the tilt is absorbed by the mixture, as the proposition says — and removes the
plain head's small 1 s false-alarm excess.

**Fusion (k = all stations, M≥5 event MAE / all-events MAE, signed M≥5 bias in parentheses).**

| rule | 1 s | 3 s | 5 s |
|---|---|---|---|
| mixture, ÷ training histogram | .327 / .249 (−.25) | .272 / .199 (−.22) | .242 / .176 (−.15) |
| eqgr, learned factor once | .693 / .244 (−.69) | .387 / .193 (−.37) | .299 / .168 (−.28) |
| **eqgr_bfix, pinned factor once** | .323 / .266 (−.16) | .224 / .203 (−.03) | .258 / .175 (−.04) |
| eqdgr, learned factor once | .271 / .240 (−.13) | .210 / .191 (+.06) | .226 / .169 (+.05) |
| eqdgr_bfix, pinned factor once | .262 / .263 (+.04) | .292 / .205 (+.16) | .286 / .178 (+.11) |

* For the plain head the prescription works: with the catalogue slope in the factor, "prior
  counted once" is nearly unbiased and matches the histogram rule's tail (vs the mixture's
  histogram rule: +.002 / −.039 / +.018, n.s.), where the learned factor under-corrected by
  .3–.4 units.
* For the distance-marginalized head it does not: its *learned* slope (−1.85) fused better than
  the catalogue's (−2.29), which now over-corrects (+.16 / +.11 bias at 3 / 5 s). So the prior a
  trained posterior actually carries is only approximately the label histogram — the
  interval-censored fit, finite capacity and the sequence structure of the data all move it —
  and no single a-priori slope is right for every head.
* Both pinned heads lose the fused *bulk* advantage at 1 s (+.019 / +.016 vs the mixture's
  histogram rule, CIs exclude zero) that the learned-slope heads had (−.004 / −.007): with the
  tail pinned, the free part of the factor adapts and the fused bulk suffers.

**Reading.** The slope of the prior factor is free at one station (Proposition 2, now confirmed
empirically: pinning it leaves single-station error unchanged), so it must be *chosen* for
fusion. Neither the catalogue b-value nor the learned value is right for every head; the
fused large-event bias is the observable that tells which, and it can be driven to zero with a
single tilt parameter calibrated on held-out fused events. That calibrated rule is the next
step. Chile (β = −1.79) and GEOFON (β = −1.32) pinned-slope arms are queued.

## 2026-10-21 01:50 UTC — INSTANCE held-station test now includes the distance-marginalized head: its M≥5 gain survives on stations never seen in training

`eqdgr_nll_hs` (20% of stations withheld, seed 1) joins the three held-station arms of 19 Oct;
four-arm evaluation on records at held stations only (279,812 records; `eval_hs_held4.json`),
Δ = arm − mix_nll_hs, median action, 1 / 3 / 5 s:

| | bulk | M≥4 MAE | M≥5 MAE |
|---|---|---|---|
| eqgr_hs | −.002 / −.000 / −.003 (n.s.) | **−.017 [−.026,−.010]** / −.005 / **−.011 [−.019,−.004]** | **−.068 [−.107,−.032] / −.111 [−.176,−.041] / −.139 [−.208,−.068]** |
| mixgr_hs | **−.004** / −.002 / **−.002** | −.003 / −.007 / −.006 | −.026 / **−.044 [−.084,−.006] / −.065 [−.101,−.027]** |
| **eqdgr_hs** | −.003 / −.002 / −.004 (n.s.) | −.021 / −.004 / −.010 (n.s.) | −.158 [−.332,+.018] / **−.201 [−.345,−.060] / −.217 [−.365,−.066]** |

Absolute M≥5 MAE at held stations, 5 s: mixture .771, prior-only .702, plain equivariant .624,
distance-marginalized .538. So on unseen stations the distance-marginalized head keeps the
largest M≥5 gain of any arm (as on seen stations), at equal bulk error and, for this seed, a
false-M4 difference that is not significant (−3.5 / +2.7 / −2.7 per 10⁴; the three-seed
ensemble shows a doubling, 21 Oct 09:05 entry).
On the seen-station subset (879,437 records; `eval_hs_seen4.json`) the full-data pattern
repeats: eqdgr_hs − mix_hs M≥5 **−.169 [−.316,−.044] / −.191 [−.326,−.085] / −.195
[−.350,−.077]**, bulk −.001 / **−.004 / −.007**, false-M4 **+6.9 / +3.2 / +1.8 per 10⁴** (its known
1 s cost; absent on the held-station subset); eqgr_hs M≥5 **−.075 / −.107 / −.135**, bulk
−.002 / **−.002 / −.003**, false-M4 equal. Absolute M≥5 MAE at 5 s, seen stations: mixture
.703, prior-only .650, plain .556, distance-marginalized .493.

## 2026-10-20 21:20 UTC — Chile held-station test: the distance-marginalized head's bulk gain is at least as large on unseen stations; its tail gain there is same-signed at 5 s but underpowered (10 M≥6 events)

Arms retrained with 7 of the 22 Chile stations withheld from training in every fold
(`--hold-stations 0.2`, rng 0; `queue_chile_hs.txt`; seed 1; 32% fewer training records).
Records at held stations (held event *and* held station) and at seen stations are evaluated
separately with `geofon_eval.py --station-subset`, Δ = arm − mix_nll_hs, median action
(`chile_eval_hs_held.json`, `chile_eval_hs_seen.json`).

**Held stations** (165,670 records; 58 M≥5, 10 M≥6 events). Absolute mix_hs: bulk .259 / .252 /
.250; M≥5 .927 / .726 / .701; M≥6 1.366 / 1.011 / 1.026. Every arm is worse on unseen stations
than on seen ones (bulk ≈ +.05 at 1 s), the usual station-generalization gap.

| | bulk 1 / 3 / 5 s | M≥5 MAE 1 / 3 / 5 s | M≥6 MAE 1 / 3 / 5 s |
|---|---|---|---|
| eqgr_hs | +.0039 / +.0027 / +.0024 (n.s.) | **+.086 [+.030,+.159]** / −.008 / −.056 | +.186 / −.215 / −.300 (n.s.) |
| **eqdgr_hs** | **−.0041 [−.0074,−.0006] / −.0131 [−.0154,−.0102] / −.0099 [−.0132,−.0069]** | +.047 / +.011 / −.059 (n.s.) | +.052 / −.092 / −.233 (n.s.) |

**Seen stations** (339,996 records; 67 M≥5, 12 M≥6). eqdgr_hs: bulk −.0018 (n.s.) / **−.0045
[−.0054,−.0034] / −.0076 [−.0085,−.0066]**; M≥5 −.010 / **−.094 [−.127,−.059] / −.126
[−.169,−.086]**; M≥6 +.019 / **−.348 [−.529,−.222] / −.422 [−.633,−.273]**. eqgr_hs: bulk
**+.0027 / +.0018** / +.0002; M≥5 **+.062** / **−.061 / −.107**; M≥6 +.135 / **−.325 / −.425**.
The full-data three-seed pattern (20:10 entry) repeats on the seen-station subset.

* The distance-marginalized head's bulk advantage is at least as large on unseen stations
  (−1.6% / −5.2% / −4.0% of the mixture's error) as on seen ones (−0.9% / −2.6% / −4.9%):
  a per-distance amplitude law with a learned distance mixture transfers to stations never
  seen in training at least as well as the free mixture's station-specific fit.
* Its large-event gain on unseen stations has the same sign as on seen stations at 5 s
  (M≥6 −.23 vs −.42; M≥5 −.06 vs −.13) but, with 10 M≥6 events recorded at 7 stations, the
  intervals include zero; at 1 and 3 s the held-station M≥5 point estimates are slightly
  positive (+.05, +.01, n.s.). On Chile the held-station evidence therefore supports the bulk
  claim and is inconclusive for the tail; the held-station test with power for the tail claim
  is the INSTANCE one (19 Oct entry), where the eqgr gain survived on unseen stations.
* eqgr_hs repeats its full-data behaviour on both subsets: worse at 1 s, better large-event
  estimates at 3–5 s (significant on seen stations, not on held).

## 2026-10-20 20:10 UTC — Chile, three seeds: the distance-marginalized equivariant head beats the free mixture on bulk at every deadline and on the tail at 3 and 5 s; every seed agrees

Three-seed ensembles (each arm = mean of its three seeds' posteriors; `chile_eval_ens3.json`),
Δ = arm − mix_nll ensemble, median action. Absolute mix ensemble: bulk .203 / .159 / .143;
M≥5 .845 / .580 / .553; M≥6 1.287 / .847 / .855 (12 events; bootstrap replicates without an
M≥6 event are dropped, so M≥6 intervals are now reported).

| | bulk 1 / 3 / 5 s | M≥5 MAE 1 / 3 / 5 s | M≥6 MAE 1 / 3 / 5 s |
|---|---|---|---|
| eqgr | **+.0008** / +.0001 / **−.0012** | **+.049 [+.024,+.079]** / **−.038 [−.070,−.001]** / **−.089 [−.133,−.040]** | +.062 / **−.248 [−.423,−.060]** / **−.377 [−.566,−.215]** |
| mixgr | +.0000 / **+.0002** / +.0002 | +.006 / +.001 / −.005 | **+.023** / −.022 / −.022 |
| **eqdgr** | **−.0024 [−.0033,−.0015] / −.0042 [−.0052,−.0034] / −.0057 [−.0070,−.0047]** | +.002 / **−.043 [−.074,−.006]** / **−.090 [−.137,−.040]** | −.014 / **−.276 [−.399,−.148]** / **−.385 [−.565,−.230]** |

M≥5 event-MAE follows the record-level numbers (eqdgr −.009 / **−.047 [−.077,−.010]** /
**−.095 [−.145,−.040]**). Absolute M≥6 MAE at 5 s: mix .855, mixgr .835, eqgr .479,
**eqdgr .472**; the M≥6 bias moves from −.86 (mix) to −.28 (eqdgr). Under the mean action the
5 s picture is the same (eqdgr bulk −.0055 [−.0065,−.0047], M≥5 −.071 [−.114,−.026], M≥6
−.324 [−.508,−.155]), so the gain is not a property of the decision rule.

**Seed consistency** (single seeds, each Δ against the same-seed free mixture, `chile_eval_seed{1,2,3}.json`):

* eqdgr bulk is negative with a CI excluding zero in **9 of 9** seed × deadline cells
  (−.0019 to −.0059). M≥5 MAE is negative in 3/3 seeds at 3 s (−.034 / −.033 / −.051) and
  at 5 s (−.086 / −.083 / −.090); M≥6 −.23 / −.28 (3 s) and −.36 / −.39 (5 s) in seeds 2–3
  (seed 1's M≥6 interval was not computable before the finite-replicate fix). At 1 s the M≥5
  sign varies (−.012 / +.016 / +.005): no 1 s tail effect either way.
* eqgr is worse at 1 s on M≥5 in 3/3 seeds (+.045 / +.063 / +.049) and better at 5 s in 3/3
  (−.076 / −.082 / −.090); its bulk sign varies (+.0017 / +.0019 / +.0008 at 1 s, ≈0 at 5 s).
* mixgr has no consistent sign on any tail metric (e.g. 5 s M≥5 −.010 / +.012 / −.015).

**Reading.**

* On this regional network (40–230 km) both equivariant heads reach the same large-event
  accuracy at 3 and 5 s. What the distance marginalization adds is the 1 s tail (eqgr +.05,
  eqdgr ±0) and the bulk (eqgr ≈ 0, eqdgr −1.2% to −4%): one amplitude law across all
  distances is too rigid where attenuation varies across the population, and the
  per-distance law with a learned mixture over distance hypotheses fixes it without any
  distance input at test time.
* With three seeds on all three catalogues the attribution is settled. The prior factor
  alone (`mixgr`) never moves the tail (INSTANCE: bulk only; GEOFON: neutral; Chile: neutral).
  The plain equivariant likelihood (`eqgr`) wins the tail where a single amplitude law holds
  (INSTANCE at every deadline, Chile at 3–5 s), loses where it does not (GEOFON; Chile at 1 s).
  The distance-marginalized equivariant likelihood (`eqdgr`) is never worse than the free
  mixture on the tail and improves it on every dataset (INSTANCE M≥5 −.12 to −.19, GEOFON M≥7
  −.09 to −.12, Chile M≥6 −.28 to −.39), with lower bulk error on INSTANCE and Chile and a
  +.02 bulk cost on GEOFON only. Its recorded cost on INSTANCE (more 1 s false-M4 alarms) is
  removed by averaging with `mixgr` (16:45 entry).
* Headline for the cross-dataset claim: `eqdgr` − free mixture, three-seed ensembles, 5 s,
  median action — INSTANCE bulk −.005 / M≥5 −.19; GEOFON bulk +.02 / M≥7 −.12; Chile bulk
  −.006 / M≥6 −.39. Table: `results/cross_dataset_table.md`.

**Size-matched average on Chile (20:15 UTC, `chile_eval_combo6.json`).** As on INSTANCE
(16:45 entry), the structured six-model average mixgr×3 + eqdgr×3 against the free + prior-only
six-model average mix×3 + mixgr×3, median action: bulk **−.0033 [−.0038,−.0030] / −.0040
[−.0047,−.0034] / −.0049 [−.0059,−.0042]**; M≥5 −.013 [−.029,+.004] / **−.061 [−.087,−.033] /
−.088 [−.124,−.050]**; M≥6 −.011 / **−.252 [−.312,−.177] / −.333 [−.422,−.242]**. Under the
mean action the same cells are significant (5 s: bulk −.0046, M≥5 −.067, M≥6 −.246). So on
Chile the structured average dominates the matched free average on both axes at every deadline
(1 s tail equal), without the 1 s false-alarm cost seen on INSTANCE; the gain is not an
ensemble-size effect. `eqdgr` alone against the six-model free average: bulk −.0015 / −.0033 /
−.0045 (CIs exclude zero), tail as above.

## 2026-10-20 16:45 UTC — INSTANCE: the distance-marginalized equivariant head as a three-seed ensemble

eqdgr (3 seeds) − mix (3 seeds), median action: bulk −.0008 [−.0026,+.0005] / **−.0032
[−.0048,−.0021] / −.0047 [−.0062,−.0037]**; M≥4 −.015 / −.016 / −.023 (wide CIs, n.s.); M≥5
−.122 [−.279,+.030] / **−.174 [−.338,−.025] / −.189 [−.371,−.035]**; false-M4 **+4 / +2 / +1 per 10⁴**
(all CIs exclude zero; ≈2× the mixture's rate at 1 s). Averaging its posterior with the
prior-only model (6 members, not size-matched) keeps the tail (M≥4 −.022 / −.024 / −.028, M≥5
−.083 / −.132 / −.148, all CIs exclude zero), lowers bulk further (−.0055 / −.0067 / −.0076) and
removes the false-alarm cost (+1 / +0 / −0 per 10⁴). So the distance-marginalized form's
false-alarm cost on INSTANCE is a property of its sharper tail probabilities and is
controllable by model averaging. **Size-matched (6 vs 6: mixgr+eqdgr against mix+mixgr):**
bulk **−.0033 [−.0038,−.0023] / −.0042 [−.0047,−.0036] / −.0047 [−.0053,−.0043]**; M≥4 −.017
[−.042,+.003] / **−.018 [−.035,−.004] / −.021 [−.039,−.004]**; M≥5 −.077 [−.174,+.007] / **−.118
[−.231,−.033] / −.129 [−.253,−.041]**; false-M4 +1 [+1,+1] / +0 / +0 per 10⁴. The structured
average beats the matched free + prior-only average on bulk at every deadline and on the
tail at 3 and 5 s, with a one-per-10⁴ false-alarm increase confined to 1 s.

## 2026-10-20 14:35 UTC — third dataset built: single-station Northern Chile (TEAM-LM data); seed-1 results (three seeds: 20:10 entry)

To decide whether the INSTANCE regime (plain equivariance wins) or the GEOFON regime (needs
distance conditioning) is the typical early-warning case, a third, *local/regional* cache with
a real tail was built from the project's existing Northern-Chile TEAM-LM data
(`chile_prep.py`; sensitivity-corrected m/s, 100 Hz, MA labels). The release has only a
network-first-P clock, so each station trace was picked: causal 1–20 Hz band-pass on Z,
STA/LTA 0.5 s/5 s with trigger ≥ 4 after the network P, AIC refinement ±1 s, accepted when
RMS(1 s after)/RMS(1 s before) ≥ 3 and 5 s of data remain. 505,666 of 1,049,297 traces pass
(48%). Pick sanity: station P delay after the network P grows with epicentral distance
(r = 0.78; medians 1.0 s at <80 km, 4.9 s at 80–150 km, 10.3 s at 150–250 km, 17.9 s at
250–400 km). Cache: 67,284 events, 7,774 GK sequences, epicentral 42 / 126 / 233 km
(5th / 50th / 95th pct), **67 M≥5 and 12 M≥6 events** (max M8.05) balanced over 5 folds.
Arms queued: mix / eqgr / mixgr / eqdgr × 3 seeds; tails reported at M≥5, 5.5, 6.

**Seed 1 (16:30 UTC), Δ = arm − mix_nll, median action** (absolute mix: bulk .208 / .164 / .148;
M≥5 .857 / .591 / .556; M≥6 1.260 / .861 / .858):

| | bulk 1 / 3 / 5 s | M≥5 1 / 3 / 5 s | M≥6 (point) 1 / 3 / 5 s |
|---|---|---|---|
| eqgr | **+.0017 / +.0014** / +.0002 | **+.045** / −.037 / **−.076 [−.120,−.026]** | +.110 / **−.260 / −.366** |
| mixgr | +.0003 / +.0004 / +.0003 | +.004 / −.010 / −.010 | −.001 / −.066 / −.066 |
| **eqdgr** | **−.0025 / −.0042 / −.0059** (all CIs exclude zero) | −.012 / −.034 / **−.086 [−.129,−.037]** | −.002 / **−.261 / −.374** |

* Chile sits between the other two regimes: the plain equivariant head wins the tail at 3 and
  5 s (the twelve M≥6 events: −.26 / −.37 magnitude units of error) with equal bulk at 5 s, but
  loses at 1 s on both axes.
* **The distance-marginalized equivariant head dominates the free mixture on both axes at every
  deadline here**: lower bulk error everywhere (−1.2% to −4%), equal tail at 1 s and the same
  large-event gains as eqgr at 3–5 s. With INSTANCE (largest M≥5 gains, bulk −.0004 / −.0030 /
  −.0049) and GEOFON (only arm with M≥7 gains), `eqdgr` is the most portable single model; its
  one recorded cost is the higher 1 s false-M4 rate on INSTANCE (12 vs 6 per 10⁴).
* M≥6 intervals are not reported for seed 1: with 12 events, bootstrap replicates can contain
  none (fixed afterwards by dropping such replicates; the 20:10 entry reports them).
* **Mechanism on Chile (amplitude-response diagnostic, folds 0–1, M≥5 records):** the free
  mixture responds .74–.85 magnitude units per decade of amplitude *downward* but only
  .46–.57 *upward*, i.e. it saturates exactly as on INSTANCE and GEOFON; eqgr and eqdgr respond
  symmetrically at .93–1.16, the slope of an amplitude-based local scale (the learned κ was
  ≈.6–.8 on INSTANCE, where most labels are M_L with M_w above M4, and ≈.57 on GEOFON). On
  small events (M<3) all heads respond ≈.4–.9 and asymmetrically, as the prior dominates.

## 2026-10-20 08:30 UTC — distance-marginalized free mixture on INSTANCE: best bulk of any arm, no tail gain

`mixdgr_nll` (free distance-marginalized mixture × GR prior, distance a training label only,
seed 1) − mix_nll, median action: bulk **−.0031 [−.0043,−.0008] / −.0042 [−.0051,−.0026] /
−.0061 [−.0071,−.0045]** (absolute .3244 / .2661 / .2320, the lowest of any single model);
M≥4 +.006 / +.001 / −.013 (all n.s.); M≥5 **+.065 [+.014,+.125]** / +.010 / −.029 (n.s.);
false-M4 equal. For comparison, eqdgr (equivariant, same distance mixing) has M≥5 −.139 /
−.173 / −.184 and eqgr −.032 / −.115 / −.141.

Across both datasets the attribution is now consistent: **the GR prior factor and distance
marginalization improve bulk error; only the equivariant likelihood improves the
high-magnitude tail** (plainly on INSTANCE, per distance on GEOFON). Distance information
without the equivariant structure does not extrapolate to large events.

## 2026-10-20 07:20 UTC — capacity: a 2.2×-larger free mixture does not close the gap

`mix_nll_w15` and `eqgr_nll_w15` (trunk width ×1.5, 1.47 M parameters vs 0.66 M, seed 1).
eqgr_w15 − mix_w15, median action: bulk **−.0022 [−.0032,−.0017] / −.0025 [−.0039,−.0014] /
−.0034 [−.0043,−.0026]**; M≥4 **−.018 [−.023,−.010] / −.021 [−.034,−.007] / −.027 [−.045,−.010]**;
M≥5 −.031 [−.057,+.013] / **−.109 [−.206,−.022] / −.133 [−.263,−.034]**; event-M≥4 **−.016 / −.017 /
−.023** (CIs exclude zero); false-M4 +0.1 per 10⁴ (n.s.). The gap is unchanged or slightly
wider at higher capacity. The standard eqgr (0.66 M) against the 2.2×-larger free mixture:
bulk −.0009 / −.0015 / −.0025 (3 and 5 s CIs exclude zero), M≥4 +.000 / −.004 / −.012 (n.s.),
M≥5 +.008 / **−.091 / −.125**: extra capacity lets the free model reach eqgr's M≥4 error but
not its M≥5 error or its bulk error. The constraint is not a substitute for capacity; it is
information the free model does not recover with more parameters.

## 2026-10-20 04:25 UTC — training length: the gain persists at 20 epochs; longer training itself trades bulk for tail

`mix_nll_e20` and `eqgr_nll_e20` (20 epochs instead of 10, same schedule shape, seed 1).
eqgr_e20 − mix_e20, median action: bulk −.0001 [−.0026,+.0018] / **−.0017 [−.0038,−.0001] /
−.0038 [−.0047,−.0032]**; M≥4 **−.014 [−.020,−.004] / −.011 [−.019,−.001] / −.017 [−.024,−.007]**;
M≥5 −.047 [−.113,+.019] / **−.098 [−.164,−.043] / −.110 [−.198,−.033]**; false-M4 equal. Same
pattern and magnitude as at 10 epochs, so the result is not an under-training artefact.
Doubling the epochs is not itself an improvement: for both heads bulk MAE rises by +.004–.005
(mix_e20 .332 / .275 / .242 vs .328 / .270 / .238) while M≥4 falls by ≈.02, i.e. a move along the
trade-off, consistent with the model starting to overfit the bulk.

## 2026-10-20 01:20 UTC — INSTANCE, size-matched posterior average: the structured pair dominates the free + prior-only pair on every axis

Exploratory (same construction as the GEOFON check): three `mixgr` + three `eqgr` posteriors
averaged, against three `mix` + three `mixgr` (6 vs 6 models), median action, Δ = structured −
reference: bulk **−.0015 [−.0019,−.0012] / −.0018 [−.0024,−.0014] / −.0024 [−.0028,−.0021]**;
M≥4 **−.010 [−.015,−.004] / −.010 [−.018,−.003] / −.017 [−.028,−.007]**; M≥5 −.016 [−.046,+.012] /
**−.063 [−.133,−.010] / −.090 [−.179,−.030]**; event-M≥4 −.007 / −.008 / −.014; false-M4 rate
+0.0 per 10⁴ at every deadline (CI [−0.0, +0.1]). Bulk-capped best M≥4 −.088 / −.092 / −.101.
Mixing the prior-only posterior in removes eqgr's small false-alarm cost while keeping its tail
gain. Reported as a post-hoc combination; the pre-specified single-model claims stand above.

## 2026-10-19 23:40 UTC — NEGATIVE on a second dataset: on the GEOFON regional subset the equivariant head is worse than the free mixture

Second dataset (`geofon_prep.py`, `results/geofon_folds.json`): GEOFON (SeisBench), records
within 2,000 km of the epicentre with a catalogue P pick, sensitivity and ≥99% completeness:
**31,020 records, 2,212 events, 276 M≥6 and 50 M≥7 events**; labels mostly mb (49%), with
Mw(mB), M, MLv, Mw(Mwp); 78% of traces at 20 Hz (BH), resampled to 100 Hz; GK sequence folds
balanced on M≥6/M≥7. Same code, seed 1, median action, Δ = arm − mix_nll (`geofon_eval.py`):

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| eqgr Δ bulk | **+.015 [+.010,+.020]** | **+.014 [+.009,+.019]** | **+.013 [+.008,+.018]** |
| eqgr Δ M≥6 | **+.043 [+.020,+.064]** | **+.053 [+.038,+.067]** | **+.060 [+.047,+.074]** |
| eqgr Δ M≥7 | **+.067 [+.031,+.104]** | +.026 [−.008,+.063] | +.018 [−.020,+.058] |
| mixgr Δ bulk | +.001 [−.001,+.002] | +.001 [−.000,+.003] | +.002 [+.001,+.004] |
| mixgr Δ M≥6 | **−.008 [−.014,−.002]** | **−.009 [−.014,−.005]** | −.004 [−.009,+.001] |

Absolute mix_nll: bulk .533 / .460 / .429, M≥6 .888 / .670 / .579, M≥7 1.542 / 1.243 / 1.108,
M≥6 bias −.84 / −.61 / −.52 (all models underestimate large events heavily at these windows).

**Diagnosis so far**
* The deficit is uniform: +.01–.02 in every magnitude-type, sampling-rate, distance and channel
  subgroup; largest for MLv (+.045, over-predicted by both) and for Mw-labelled M≥6 records
  (+.05–.07, where eqgr underestimates *more*: bias −.92 vs −.87).
* The free mixture saturates here too (M≥6, fold 0: response .52 per decade downward, .41
  upward at 1 s; .49 / .34 at 5 s) while eqgr responds symmetrically with κ ≈ .57, yet the
  free model is still more accurate. So on this data the symmetric response is not the right
  prior: with emergent P onsets at 300–2,000 km sampled at 20 Hz, the 1–5 s RMS amplitude is
  often noise-dominated, and a head that must respond to it with κ ≥ 0.3 cannot learn to
  ignore it, whereas a free head can.
* The prior factor alone (`mixgr`) is neutral on bulk and slightly better on M≥6, as on INSTANCE.

**Three-seed ensembles (23:48 UTC) confirm it:** eqgr − mix = bulk **+.010 / +.009 / +.008**,
M≥6 **+.036 / +.042 / +.047**, M≥7 +.050 / +.008 / −.006 (all bulk and M≥6 CIs exclude zero);
mixgr − mix = bulk +.001 / +.001 / +.000 (n.s.), M≥6 −.003 / −.003 / −.003 (5 s CI excludes zero).

**Variants on GEOFON (23:58 UTC, seed 1, Δ vs mix_nll, median action):**

| | bulk 1 / 3 / 5 s | M≥6 1 / 3 / 5 s | M≥7 1 / 3 / 5 s |
|---|---|---|---|
| eqgr (κ ≥ 0.3) | +.015 / +.014 / +.013 | +.043 / +.053 / +.060 | +.067 / +.026 / +.018 |
| eqgr, κ ≥ 0 (`eqgr_k0`) | +.017 / +.014 / +.014 | +.059 / +.055 / +.058 | +.085 / +.021 / +.011 |
| eqtgr (two slopes) | +.016 / +.021 / +.021 | +.087 / +.104 / +.122 | +.180 / +.185 / +.201 |
| **eqdgr** (distance-marginalized) | +.019 / +.014 / +.014 | **−.027** / −.008 / −.002 | **−.103 / −.114 / −.141** |

* Letting κ reach 0 changes nothing (three-seed ensembles, 00:35 UTC: κ≥0 − mix = bulk
  +.009 / +.008 / +.007, M≥6 +.051 / +.045 / +.041, CIs exclude zero), so the "forced response to
  a noise-dominated amplitude" explanation above is **refuted**: the rigidity is in the
  additive form κ(s)·A + g(s) itself, not in the slope's lower bound.
* The distance-marginalized GR head recovers the large-event tail (M≥7 −.10 to −.14, the
  largest tail gain of any arm on GEOFON; M≥7 bias −1.44 vs −1.54 at 1 s) while still paying
  ≈+.015 bulk. At 300–2,000 km the attenuation term spans several magnitude units, and a head
  that must infer distance from the waveform shape and apply it as one additive offset is too
  rigid; mixing over explicit distance hypotheses restores the flexibility for large events.
* Separate scale slopes make everything worse (two half-size slope estimates).

**Distance-marginalized free mixture (`mixdgr`, 00:35 UTC), the ablation for eqdgr.** Three-seed
ensembles, Δ vs mix ensemble, median action:

| | bulk 1 / 3 / 5 s | M≥6 1 / 3 / 5 s | M≥7 1 / 3 / 5 s |
|---|---|---|---|
| mixdgr (free, distance-marginalized, GR prior) | +.013 / +.011 / +.012 | −.015 / +.011 / +.023 | −.014 / +.015 / +.020 |
| **eqdgr** (equivariant, distance-marginalized, GR prior) | +.024 / +.017 / +.016 | −.027 / −.003 / +.002 | **−.094 / −.089 / −.123** |

Distance marginalization by itself does *not* recover the large events; the M≥7 gain appears
only when the per-distance likelihood is equivariant. On GEOFON, then, the two structural
pieces are complementary in the other direction from INSTANCE: equivariance alone is too rigid
(one additive attenuation offset for 300–2,000 km), distance mixing alone is too free, and the
equivariant-per-distance head extrapolates to M≥7 (bias −1.45 vs −1.55 at 1 s; −.97 vs −1.11 at
5 s). Both distance heads pay +.011–.024 bulk here. **Extending the distance grid to 2,500 km
(01:07 UTC, `*_r34`, 3 seeds) changes nothing:** eqdgr_r34 ensemble − mix = bulk +.026 / +.020 /
+.018, M≥7 **−.095 / −.083 / −.117**; mixdgr_r34 − mix = M≥7 −.010 / +.034 / +.050. So the clamped
distance label was not the cause; the result is structural and replicated across seeds and grids.

**Exploratory (chosen after seeing the above): posterior averaging on GEOFON (01:15 UTC).** With
existing predictions only, averaging the three `mixgr` and three `eqdgr` posteriors against a
size-matched average of three `mix` and three `mixgr` posteriors gives, median action: bulk
+.004 [+.000,+.007] / −.000 [−.003,+.002] / −.001 [−.004,+.001]; M≥6 **−.019 / −.010** / −.008
(1 s and 3 s CIs exclude zero); M≥7 **−.048 / −.053 / −.070** (all exclude zero). So a
GR-structured posterior average does reach the far-regional tail without losing bulk at 3 and
5 s; at 1 s it costs +.004 bulk. This is a post-hoc combination and is reported as such.

**Consequence for the claim.** On INSTANCE (local records within a few hundred km, 100 Hz,
mostly M_L) the plain equivariant head is the right prior and wins outright. On the GEOFON
regional/teleseismic subset it is not: the amplitude law must be conditioned on distance, and
then it buys the M≥7 tail at a bulk cost. The GR prior factor is neutral-to-positive on both.

## 2026-10-19 22:50 UTC — published-architecture control (MagNet-style CNN+BiLSTM) is far behind the shared trunk

`magnet_nll`: Mousavi & Beroza (2020) layout (two convolutions, 64 and 32 kernels of size 3,
no activation, dropout 0.2, 4× max-pooling, BiLSTM 100) on amplitude-retaining waveforms, the
same station metadata, a Gaussian head trained with NLL, same folds and schedule. Pooled,
median action: bulk MAE **.397 / .377 / .355**, M≥4 **1.032 / .866 / .796**, M≥5 1.768 / 1.550 /
1.429, NLL 3.03 / 3.01 / 2.96 (vs .328 / .270 / .238, .764 / .577 / .530, 1.051 / .765 / .703,
2.75 / 2.56 / 2.43 for the free mixture).

* Every arm on the residual-CNN trunk beats it by ≈.07–.12 bulk MAE and ≈.25 M≥4 MAE; eqgr −
  magnet: bulk −.071 / −.107 / −.116, M≥4 −.279 / −.288 / −.271, M≥5 −.740 / −.883 / −.846.
* This is a *short-window adaptation* of an architecture designed for 30 s records, so it says
  little about MagNet at its intended window. What it establishes is that the trunk shared by
  all arms here is a strong one, so the head comparisons are not made on a weak backbone.

## 2026-10-19 22:20 UTC — held-station test: the gain survives on stations never seen in training

`mix_nll_hs` and `eqgr_nll_hs` were trained with a fixed random **20% of stations withheld in
every fold** (`--hold-stations 0.2`, seed 0), so their held-fold records at those stations are
*both* held-event and held-station: a station fingerprint cannot explain a gain there.
Δ = eqgr_hs − mix_hs, median action, 95% cluster-bootstrap CIs (`results/eval_hs_*.json`).

**Held-station records (279,812; 341 of the 346 M≥4 events have at least one held-station record):**

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0019 [−.0056,+.0035] | −.0003 [−.0015,+.0018] | −.0031 [−.0069,+.0017] |
| Δ M≥4 MAE | **−.017 [−.026,−.010]** | −.005 [−.018,+.004] | **−.011 [−.019,−.004]** |
| Δ M≥5 MAE | **−.068 [−.107,−.032]** | **−.111 [−.176,−.041]** | **−.139 [−.208,−.068]** |
| Δ M≥4 event-MAE | −.009 [−.020,+.002] | +.003 [−.009,+.013] | −.004 [−.013,+.005] |
| Δ false-M4 rate | −.0012 [−.0029,+.0006] | −.0002 | −.0005 [−.0010,+.0001] |
| CVaR95 (eqgr vs mix) | 1.275 vs 1.350 | 1.126 vs 1.145 | 1.077 vs 1.107 |

**Seen-station records (879,437), same two models:** bulk −.0015 / −.0019 / −.0034; M≥4
**−.024 / −.013 / −.021**; M≥5 **−.075 / −.107 / −.135**; event-M≥4 **−.020 / −.010 / −.018**
(all tail CIs exclude zero).

* On unseen stations the M≥5 improvement is as large as on seen ones and significant at all
  three deadlines; M≥4 is significant at 1 and 5 s (3 s: same sign, n.s.); event-level M≥4 is
  not significant on this subset (fewer events per station group). Bulk is never worse.
* The free mixture degrades more on unknown stations than eqgr does: its false-M4 rate at 1 s
  is 2.9 per 10³ vs 1.2 for eqgr, and its CVaR95 is higher at every deadline. A constrained
  amplitude response transfers to new instruments better than a learned one.
* **Prior-only ablation under the same protocol (`mixgr_nll_hs`, 23:35 UTC):** on held stations
  mixgr − mix is bulk −.0035 / −.0015 / −.0018 (1 s CI excludes zero), M≥4 −.003 / −.007 / −.006
  (n.s.), M≥5 −.026 / −.044 / −.065 (3 and 5 s significant). So both components transfer to
  unseen stations; equivariance carries the larger tail gain (M≥5 −.068 / −.111 / −.139) and,
  unlike mixgr, also lowers CVaR95 (1.275 / 1.126 / 1.077 vs mixgr 1.317 / 1.167 / 1.120) and the
  false-M4 rate (1.2 / 0.9 / 0.8 vs mixgr 2.5 / 2.0 / 2.3 per 10³) on unknown instruments.
* On seen stations these reduced-data models are within .003 bulk MAE of the full-data arms;
  on held stations both are ≈.02–.025 worse (unknown instruments), so the held-station numbers
  are comparable only to each other, not to the main table.

## 2026-10-19 21:10 UTC — third seed: 3-seed ensembles confirm eqgr; eqdgr's M≥5 gain and its false-alarm cost both replicate

Seed-3 arms (queue3) and eqdgr seeds 2–3 (`queue4.txt`), evaluated by `eval_replication.sh`
(`results/eval_ens3.json`, `eval_eqd_*.json`). Ensembles are posterior mixtures. `evaluate.py`
now also bootstraps the **false-M4 rate**: the share of M<3.5 records whose prediction is ≥3.95,
given here per 10⁴ such records.

### Three-seed ensembles, Δ = arm ensemble − free-mixture (`mix_nll`) ensemble, median action

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| eqgr Δ bulk | −.0008 [−.0021,+.0000] | **−.0015 [−.0031,−.0003]** | **−.0028 [−.0039,−.0020]** |
| eqgr Δ M≥4 | **−.015 [−.023,−.005]** | **−.015 [−.026,−.003]** | **−.025 [−.042,−.009]** |
| eqgr Δ M≥5 | −.024 [−.075,+.028] | **−.105 [−.220,−.010]** | **−.149 [−.291,−.040]** |
| eqgr bulk-capped M≥4 / M≥5 | **−.056 / −.061** | **−.078 / −.132** | **−.107 / −.166** |
| eqgr Δ false-M4 per 10⁴ | **+1.5 [+1.0,+2.3]** | **+0.65 [+0.05,+1.02]** | **+0.63 [+0.03,+1.04]** |
| mixgr Δ bulk / M≥4 / event-M≥4 | **−.0015 / −.008 / −.008** | **−.0022 / −.008 / −.006** | **−.0028 / −.012 / −.010** |
| cat_ce Δ M≥4 / M≥5 | **+.018 / +.058** | **+.030 / +.094** | **+.032 / +.113** |

* The third seed changes none of the two-seed conclusions; no Δ moves by more than .007.
  eqgr still lowers M≥4 at every deadline and M≥5 at 3 and 5 s, with bulk equal or better.
* False-M4 per 10⁴ M<3.5 records (ensembles): mix 5.0 / 4.2 / 3.4, mixgr 5.6 / 4.0 / 3.3,
  eqgr 6.4 / 4.9 / 4.1, cat_ce 7.5 / 5.2 / 4.2. **eqgr's small false-alarm rise over the mixture
  is significant at every deadline** (each single seed shows it at 1 s). It stays below plain CE.

### eqdgr replication (seeds 1–3)

M≥5 MAE, median action, eqdgr vs eqgr of the same seed:

| seed | 1 s | 3 s | 5 s | false-M4 per 10⁴ at 1 s |
|---|---|---|---|---|
| 1 | .898 vs 1.012 | .578 vs .638 | .503 vs .548 | 12.2 vs 7.8 |
| 2 | .929 vs 1.022 | .594 vs .651 | .525 vs .549 | 11.8 vs 7.8 |
| 3 | .918 vs 1.014 | .576 vs .646 | .507 vs .546 | 11.5 vs 7.9 |
| mix_nll (seed 1) | 1.051 | .765 | .703 | 6.3 |

Each eqdgr seed − mix_nll, M≥5: −.139 / **−.173 / −.184** (seed 1), −.107 / **−.157** / −.163
[−.367,+.030] (seed 2), −.120 / **−.174 / −.180** (seed 3). Each eqdgr seed − mix_nll, false-M4 at
1 s: **+5.4 / +5.1 / +4.8** per 10⁴ (all CIs exclude zero).

Three-seed ensembles, Δ = eqdgr ensemble − eqgr ensemble, median action:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk | +.0000 [−.0007,+.0010] | **−.0016 [−.0022,−.0007]** | **−.0018 [−.0024,−.0013]** |
| Δ M≥4 | −.001 [−.030,+.025] | −.001 [−.013,+.010] | +.002 [−.009,+.014] |
| Δ M≥4 event | −.001 [−.032,+.023] | +.002 [−.011,+.013] | +.008 [−.004,+.018] |
| Δ M≥5 | −.099 [−.212,+.012] | **−.070 [−.126,−.011]** | −.042 [−.090,+.012] |
| bulk-capped M≥4 / M≥5 | −.007 / **−.120** | **−.066 / −.108** | **−.073 / −.076** |
| Δ false-M4 per 10⁴ | **+3.0 [+0.7,+4.6]** | **+1.4 [+0.7,+1.8]** | +0.4 [−0.2,+1.4] |

Against the mix ensemble, the eqdgr ensemble has bulk −.0008 / **−.0032 / −.0047**, M≥4 −.016 /
−.016 / −.023 (no CI excludes zero), M≥5 −.124 [−.287,+.034] / **−.176 [−.346,−.020] / −.191
[−.379,−.034]**, bulk-capped M≥5 **−.162 / −.223 / −.225**, and false-M4 **+4.5 / +2.0 / +1.0** per 10⁴.

* **The M≥5 advantage replicates.** In every seed, eqdgr's M≥5 MAE is below the same-seed eqgr
  at every deadline: by .09–.11 at 1 s, .06–.07 at 3 s and .02–.05 at 5 s. In the ensembles
  the gap is significant at 3 s, and bulk-capped at all three deadlines. eqdgr also has the
  lowest bulk MAE at 3 and 5 s (.2611 / .2277 vs .2628 / .2295 for eqgr) and the lowest NLL at
  every deadline of all the 3-seed ensembles.
* **The higher 1 s false-M4 rate replicates too.** It is 11.5–12.2 per 10⁴ in every seed,
  against 7.8–7.9 for eqgr. In the ensembles the rates are 9.9 (eqdgr), 6.4 (eqgr), 5.0 (mix)
  and 7.5 (cat_ce). The excess shrinks with time (3 s +1.4, significant; 5 s n.s.). The
  other seed-1 costs also hold: CVaR95 is higher than eqgr's (+.005 / +.007 / +.008), and
  Emilia (fold 1) gets worse (M≥4 .879 / .533 / .477 vs .844 / .513 / .442).
* **No M≥4 gain over eqgr.** Record and event M≥4 MAE match eqgr within ±.01 at every deadline.
  The gain is in the largest events and in the unseen Central Italy fold (fold-0 M≥4
  .609 / .434 / .369 vs .669 / .457 / .389).
* **Verdict:** eqdgr is a replicated trade-off, not a replacement. It gives better M≥5
  extrapolation and 3–5 s bulk, but has about 1.5× eqgr's 1 s false-M4 rate and no M≥4 gain.
  eqgr remains the main method; eqdgr stays exploratory (designed after the eqgr results).

## 2026-10-19 18:30 UTC — seed × fold consistency (3 seeds × 5 folds × 3 deadlines) and the component trade-off

Sign tests over 45 cells (seed-matched pairs, median action, `seed_consistency.py`).

**eqgr − mix_nll (strongest baseline):**
* M≥4 MAE: eqgr better in **36/45** cells (sign-test p = 7×10⁻⁵). The 9 exceptions are **all fold 1
  (Emilia)**; every other fold, seed and deadline improves. M≥4 event-MAE 36/45; M≥5 34/45
  (p = 8×10⁻⁴); bulk MAE 33/45 (p = 2×10⁻³, median Δ −.0014).
* Pooled per seed: all 9 seed×deadline comparisons are negative for M≥4, event-M≥4 and M≥5;
  bulk is ≤ 0 in all 9 (worst case +.0000 at 1 s, seed 1).

**Ablations, 3 seeds each:**
* mixgr − mix: bulk better in **40/45** (p = 8×10⁻⁸), M≥4 31/45 (p = .016), M≥5 29/45 (p = .07).
* eqgr − mixgr: M≥4 better in **35/45** (p = 2.5×10⁻⁴), M≥5 30/45 (p = .036), event-M≥4 32/45;
  bulk better in only 11/45 (median Δ **+.0006**, p = 8×10⁻⁴ in mixgr's favour).

**Other tail views (single seed, median action, eqgr vs mix_nll):** M≥4.5 MAE .876 / .639 / .584
vs .899 / .678 / .635; event-level M≥5 MAE .989 / .606 / .513 vs 1.009 / .706 / .644; M≥5 bias
−.96 / −.56 / −.46 vs −1.02 / −.74 / −.68. The **worst-1% errors over all records (CVaR99)** are
*not* improved: 1.663 / 1.487 / 1.429 vs 1.660 / 1.478 / 1.430 (+.009 at 3 s). Those errors are
dominated by records whose waveform carries little magnitude information at the deadline, not
by large events, and the method does not address them. CVaR95 is unchanged (≤ ±.002).

**Tail-probability reliability (`calibration_check.py`):** both arms are well calibrated
(Brier reliability terms 2×10⁻⁶ to 4×10⁻⁵). eqgr's lower Brier for P(M≥4) and P(M≥5) at 3 s and
5 s (e.g. 5 s M≥5: .000849 vs .000929) comes from higher resolution. The free mixture is
systematically **under-confident for M≥5** (predicted .14 → observed .20; .42 → .55; .57 → .64 at
5 s), the probabilistic face of amplitude saturation; eqgr is near the diagonal in that range
and slightly over-confident at the top (.97 → .78, 475 records). At 1 s the two are equal.

So both components beat the baseline on both axes, but they are not equivalent: the GR prior
factor is the bulk-safest change, and equivariance buys the tail for a median +.0006 bulk MAE
relative to that ablation (still below the baseline's bulk). The pre-specified claim ("tail
down at 1/3/5 s, bulk not worse than the baseline") holds for eqgr; relative to its own
ablation it is a stated trade-off.

## 2026-10-19 16:00 UTC — two-seed ensembles vs the strongest baseline, exploratory heads, and the standard split

### Two-seed ensembles, Δ = arm ensemble − free-mixture (`mix_nll`) ensemble, median action

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| eqgr Δ bulk | −.0007 [−.0020,+.0001] | **−.0015 [−.0030,−.0003]** | **−.0030 [−.0039,−.0024]** |
| eqgr Δ M≥4 | **−.016 [−.023,−.005]** | **−.014 [−.024,−.001]** | **−.022 [−.037,−.006]** |
| eqgr Δ M≥5 | −.028 [−.084,+.029] | **−.106 [−.220,−.006]** | **−.143 [−.281,−.031]** |
| eqgr bulk-capped M≥4 / M≥5 | **−.051 / −.059** | **−.078 / −.135** | **−.113 / −.166** |
| mixgr Δ bulk / M≥4 / event-M≥4 | **−.0014 / −.009 / −.010** | **−.0023 / −.008 / −.007** | **−.0028 / −.008 / −.007** |
| cat_ce Δ M≥4 / M≥5 | **+.015 / +.059** | **+.030 / +.099** | **+.034 / +.120** |

With ensembles on both sides, eqgr beats the strongest existing approach on high-magnitude
error at all three deadlines (M≥4 CIs exclude zero everywhere; M≥5 at 3 and 5 s), with bulk
error equal (1 s) or better (3 s, 5 s).

### Exploratory heads (single seed, designed after seeing the eqgr results)

* **eqtgr** (separate ML / Mw equivariant slopes, joint likelihood with the reported scale):
  **negative**. It does not fix Emilia (fold 1 M≥4 .866/.542/.480 vs .853/.530/.455 for eqgr), and
  pooled it is no better than eqgr anywhere. 1 s M≥5 is *worse* than the free mixture
  (+.028 [+.002,+.063]).
* **eqdgr** (distance-aware equivariant likelihood p(r|s)·N(m; κA+G_r(s)) × the same GR prior,
  distance used only as a training label): **promising**. It has the largest M≥5 gains of any
  arm, −.139 / −.173 / −.184 vs mix_nll (3 and 5 s CIs exclude zero), and bulk-capped M≥5
  −.165 / −.223 / −.225. Bulk is −.0004 / −.0030 / −.0049. On fold 0 (unseen Central Italy)
  1 s M≥5 MAE is .798 vs 1.03 (eqgr) vs 1.26 (mix). Costs: a higher 1 s false-M4 rate (.0012 vs
  .0006), CVaR95 +.004 to +.009, wider intervals (still worse on Emilia). It needs seed
  replication before it could replace eqgr.

### Standard INSTANCE split (train 2005–17 → VAL 2018 / TEST 2019–20; no selection on VAL/TEST)

eqgr − mix_nll, median action. **VAL** (13 M≥4 events): bulk −.0000 / **−.0013 / −.0024**;
M≥4 **−.025 / −.022 / −.038** (CIs exclude zero). **TEST** (10 M≥4 events, max M4.5): bulk
−.0014 / −.0006 / **−.0014**; M≥4 −.014 / −.009 / −.007 (same direction, n.s.). mixgr improves
bulk on both splits at every deadline (−.0019 to −.0038, all significant).

**Against the previous project's best reported VAL model** (static instrument features,
mean action: bulk .365 / .316 / .286, M≥4 .686 / .551 / .487, CVaR95 1.327 / 1.195 / 1.147):
at the same M≥4 MAE, std_eqgr needs **14% / 19% / 20% less bulk MAE** (.3145 / .2574 / .2278)
and also has lower CVaR95 (1.240 / 1.073 / 1.025) and MedAE. Most of this cross-project gain
comes from the new end-to-end physical-unit pipeline, which every arm here shares (the
free-mixture baseline gets 14% / 18% / 20%). The head's contribution is the within-pipeline
gain reported above.

## 2026-10-19 09:50 UTC — negative for deep-imbalanced-regression reweighting: LDS is dominated

`cat_lds` (categorical CE with LDS inverse-sqrt smoothed-density weights, Yang et al. 2021)
pooled, median action: bulk MAE .3554 / .2924 / .2574 (+.028 / +.021 / +.017 vs cat_ce, ≈+8%);
M≥4 MAE .638 / .503 / .475; false-M4 rate .0035 / .0021 / .0017 (4× cat_ce).

* Plain CE reaches the same M≥4 MAE with **.023 / .019 / .016 less bulk MAE**, so LDS is
  dominated on the frontier. It buys tail error with bulk error and false alarms.
* eqgr − cat_lds: bulk **−.028 / −.024 / −.023**; bulk-capped M≥4 **−.148 / −.147 / −.152**;
  bulk-capped M≥5 **−.036 / −.078 / −.118** (all CIs exclude zero).
* **All six baselines** (cat_ce, cat_hubce, mix_nll, cat_aug, cat_lds, gbm_e3ws) are now
  dominated by eqgr on the bulk–tail frontier at 1, 3 and 5 s.

## 2026-10-19 08:35 UTC — negative for the "just augment" alternative: amplitude-scaling augmentation is dominated

`cat_aug` (categorical CE + waveform ×10^Δ with label +Δ, Δ~U(−.5,.5)) pooled, median action:
bulk MAE .3374 / .2796 / .2467 (vs .3272 / .2714 / .2400 for cat_ce, i.e. +3–4%); M≥4 MAE
.737 / .569 / .523; M≥5 1.036 / .782 / .734.

* It lowers tail error only by moving along the trade-off. Plain CE reaches the same M≥4 MAE
  with **.010 / .008 / .007 less bulk MAE** (tail-capped comparison), so augmentation is
  dominated even by the baseline.
* eqgr − cat_aug: bulk **−.0107 / −.0112 / −.0121**; bulk-capped M≥4 **−.171 / −.170 / −.171**;
  M≥5 −.022 [−.075,+.044] / **−.136 [−.235,−.027] / −.176 [−.276,−.074]**.
* Teaching the symmetry through data (fixed slope 1, shifted labels) distorts small-event
  predictions and extrapolates less far than building it into the posterior with a learned
  slope κ(s).

## 2026-10-19 07:40 UTC — gains survive two-seed ensembling

eqgr (seeds 1+2, posterior mixture) − cat_ce (seeds 1+2), median action:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0005 [−.0026,+.0013] | **−.0028 [−.0050,−.0009]** | **−.0048 [−.0062,−.0039]** |
| Δ M≥4 MAE | **−.031 [−.049,−.011]** | **−.044 [−.069,−.020]** | **−.056 [−.089,−.027]** |
| Δ M≥5 MAE | **−.087 [−.155,−.012]** | **−.205 [−.309,−.100]** | **−.263 [−.385,−.154]** |
| Δ M≥4 event-MAE | **−.022 [−.042,−.003]** | **−.036 [−.065,−.014]** | **−.047 [−.083,−.022]** |
| bulk-capped best M≥4 / M≥5 | **−.068 / −.114** | **−.130 / −.240** | **−.160 / −.287** |

Ensembling lowers both arms' bulk MAE by ≈.005 (single seed → 2-seed), but the tail gap is
unchanged, so the improvement is not seed noise or a variance effect. With ensembles, every
tail metric at every deadline has a 95% interval excluding zero; bulk is equal (1 s) or better.

## 2026-10-19 06:40 UTC — per-fold consistency and the Emilia exception

Arm − mix_nll per held-out fold (median action; bulk / M≥4 / M≥4-event):
* **mixgr** improves M≥4 in 14/15 fold×deadline cells and bulk in 13/15. Both bulk
  exceptions are in fold 1, the smallest fold (9.8k records).
* **eqgr** improves the tail in folds 0, 2, 3, 4 at every deadline (fold 0, the unseen M6.5
  Central Italy sequence: M≥4 −.046 / −.038 / −.056). It is **worse in fold 1** (M≥4 +.06 at
  1–3 s, +.044 at 5 s; bulk +.003 to +.005).
* Fold 1 is the **2012 Emilia (Po Plain) sequence**: M5.8 and M5.6, 32 M≥4 events, 24 of them
  ML-labelled. All models underestimate it. eqgr's extra error is on the **ML-labelled**
  events (3 s bias −.48 vs −.42 for mix_nll), while it is better on the Mw-labelled ones (5 s
  bias −.08 vs −.18). The equivariant head learns one amplitude slope κ(s) ≈ 0.7, close to Mw's
  ⅔ scaling. ML scales ≈1:1 with amplitude, so a sequence dominated by large ML labels is where
  a single learned slope fits worst. **Limitation and future work:** scale-specific slopes
  (an ML and an Mw head) or magnitude-type-homogeneous labels.

## 2026-10-19 06:30 UTC — full attribution against the strongest existing baseline (TEAM-LM-style free mixture)

All 1,159,249 records; Δ = arm − `mix_nll` (free Gaussian-mixture posterior, the strongest
existing-method baseline here). Median action; 95% cluster-bootstrap CIs.

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| cat_ce: Δ bulk / Δ M≥4 / Δ M≥5 | −.0002 / **+.016** / **+.061** | **+.0012 / +.030 / +.095** | **+.0018 / +.033 / +.114** |
| **mixgr**: Δ bulk | **−.0011 [−.0019,−.0006]** | **−.0025 [−.0030,−.0022]** | **−.0032 [−.0035,−.0027]** |
| **mixgr**: Δ M≥4 | **−.013 [−.022,−.003]** | **−.011 [−.018,−.003]** | **−.012 [−.020,−.004]** |
| **mixgr**: Δ M≥4 event | **−.012 [−.021,−.002]** | **−.010 [−.018,−.001]** | **−.011 [−.020,−.002]** |
| **mixgr**: bulk-capped M≥4 / M≥5 | **−.070 / −.080** | **−.107 / −.094** | **−.115 / −.082** |
| **eqgr**: Δ bulk | −.0002 [−.0017,+.0008] | **−.0015 [−.0028,−.0006]** | **−.0032 [−.0038,−.0029]** |
| **eqgr**: Δ M≥4 | **−.020 [−.034,−.002]** | −.015 [−.028,+.001] | **−.023 [−.040,−.005]** |
| **eqgr**: Δ M≥5 | −.032 [−.119,+.040] | −.115 [−.246,+.000] | **−.141 [−.289,−.021]** |
| **eqgr**: bulk-capped M≥4 / M≥5 | −.033 / −.032 (n.s.) | **−.076 / −.143** | **−.114 / −.169** |
| eq_nll (no prior factor): Δ bulk | **+.0051** | **+.0046** | **+.0032** |

**Interpretation**
1. A smooth parametric mixture head (as in TEAM-LM) already beats a categorical head on the
   tail. That part is prior art.
2. **New, the Gutenberg–Richter-factorized posterior** p(m|x) ∝ L_θ(m|x)·e^{φ(m)}, with φ
   learned, free below M3.5 and GR-linear above. On top of the mixture it improves bulk,
   M≥4 and event-level M≥4 at every deadline, all CIs excluding zero: a strict Pareto gain
   over the strongest baseline.
3. **New, the scale-equivariant likelihood** (eqgr) adds extrapolation for the largest events
   (M≥5: −.115 / −.141 at 3 / 5 s vs mix; .548 vs .655 for mixgr at 5 s). Without the
   prior factor, equivariance costs ≈+.005 bulk MAE because of the M2.0 label-prior cliff. The
   two components are complementary and should be used together.

## 2026-10-19 05:40 UTC — replicated across seeds; ablation attributes the gain

**eqgr seed 2 − cat_ce (median action):** bulk −.0000 [−.0022,+.0016] / **−.0021 [−.0044,−.0001]** /
**−.0045 [−.0057,−.0037]**; M≥4 **−.030 [−.052,−.008] / −.042 [−.069,−.017] / −.055 [−.089,−.023]**;
M≥5 **−.085 [−.151,−.014] / −.198 [−.315,−.087] / −.255 [−.397,−.141]**; M≥4 event-MAE
**−.021 [−.044,−.002] / −.035 [−.065,−.013] / −.045 [−.082,−.018]** (1 / 3 / 5 s). Seed 1 and
seed 2 agree to within ≈.006 on every tail metric.

**Probabilistic quality (both seeds):** eqgr beats cat_ce on NLL, CRPS, and Brier(M≥4) and
Brier(M≥5) at every deadline. Mean P(M≥4) on true M≥4 records rises from .374/.445/.467 to
≈.40/.49/.52, while on M<3.5 records it moves only from .0072/.0051/.0042 to .0079/.0055/.0046.

**Ablation `mixgr` (free mixture × the identical learned prior factor):**

| median action | 1 s | 3 s | 5 s |
|---|---|---|---|
| cat_ce − mixgr, M≥4 MAE | +.029 [+.010,+.048] | +.041 [+.017,+.067] | +.044 [+.018,+.073] |
| cat_ce − mixgr, M≥5 MAE | +.085 [+.040,+.120] | +.137 [+.071,+.191] | +.156 [+.083,+.220] |
| eqgr − mixgr, M≥4 MAE | −.007 [−.015,+.008] | −.004 [−.013,+.009] | −.012 [−.021,+.002] |
| eqgr − mixgr, M≥5 MAE | −.007 [−.064,+.058] | −.073 [−.153,+.022] | **−.100 [−.186,−.009]** |
| eqgr − mixgr, bulk MAE | +.0009 [−.0000,+.0015] | +.0010 [−.0001,+.0018] | −.0000 [−.0008,+.0004] |

* The **Gutenberg–Richter-factorized posterior** (smooth likelihood × learned global log-prior:
  free in the bulk, GR-linear above M3.5) gives most of the M≥4 improvement and preserves the
  bulk. It takes over the label-prior structure (the M2.0 cliff, the steep GR decay) that a
  categorical head must otherwise learn per input, and underfits in the rare bins.
* **Scale equivariance** adds extrapolation for the *largest* events: M≥5 MAE at 5 s
  .548 (eqgr) vs .655 (mixgr) vs .818 (cat_ce), at a ≈.001 (0.3%) bulk cost at 1–3 s.
* Still pending: `mix_nll` (free mixture without the prior factor) to separate the mixture
  family from the factorization; augmentation / LDS baselines; seed 3; standard split.

## 2026-10-19 03:45 UTC — eqgr (equivariant likelihood × learned bulk prior × GR tail) improves the tail at all deadlines without worsening the bulk (seed 1)

**Same decision rule (posterior median) for both, eqgr − cat_ce:**

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0000 [−.0025,+.0019] | **−.0027 [−.0046,−.0013]** | **−.0050 [−.0062,−.0044]** |
| Δ M≥4 MAE | **−.036 [−.060,−.011]** | **−.045 [−.075,−.017]** | **−.056 [−.092,−.024]** |
| Δ M≥5 MAE | **−.093 [−.175,−.003]** | **−.210 [−.334,−.092]** | **−.255 [−.401,−.137]** |
| Δ M≥4 event-MAE | −.025 [−.053,+.002] | **−.036 [−.072,−.008]** | **−.046 [−.086,−.015]** |

MedAE (.2402/.1929/.1649 vs .2398/.1957/.1699), CVaR95 (1.214/1.059/.989 vs 1.215/1.058/.990)
and the false-M4 rate (.0008/.0006/.0005, identical) are unchanged or better.

**Bulk-capped best tail** (each arm picks its best tail-weight r subject to bulk MAE ≤ cat_ce's):
M≥4 MAE −.065 [−.112,−.003] (1 s), **−.128 [−.150,−.101] (3 s), −.161 [−.186,−.127] (5 s)**;
M≥5 MAE −.101 [−.181,−.023], −.245 [−.350,−.143], −.282 [−.407,−.173].

* At 3 s and 5 s the eqgr frontier lies strictly below every baseline across the whole
  bulk range (`figures/frontier_Mge4MAE.png`).
* At 1 s the gain is real at the operating point but modest. With a 0.2% bulk tolerance the
  M≥4 gap is −.025 [−.081,+.035], and the frontiers converge for aggressive r. This is
  physically expected: at 1 s large ruptures are still growing.
* The ablation without the prior factor (eq_nll) loses bulk accuracy (+.005 at 1 s). The
  equivariant constraint and the learned bulk prior are both needed.
* **Caveats still open:** one optimization seed (seed-2/3 runs queued); `mixgr` ablation (free
  mixture × same prior) queued to separate equivariance from the prior factor; augmentation /
  LDS / free-mixture baselines queued. eqgr was specified before the eq_nll results were seen
  (queue2 created 23:30 UTC); later variants are exploratory.

## 2026-10-19 02:20 UTC — interim: equivariance fixes the largest events; bulk cost traced to a label-prior cliff

### Baseline (cat_ce, categorical CE, median action)

| deadline | MAE | MedAE | CVaR95 | M≥4 MAE | M≥4 bias | M≥5 MAE |
|---|---|---|---|---|---|---|
| 1 s | .3272 | .2398 | 1.215 | .7814 | −.733 | 1.110 |
| 3 s | .2714 | .1957 | 1.058 | .6101 | −.557 | .860 |
| 5 s | .2400 | .1699 | .990 | .5660 | −.511 | .818 |

* The tail-weighted median (your "×r tail mass, take median" rule) is almost free near r = 1.
  At 1 s, r = 2 raises bulk MAE by only +.0009 but cuts M≥4 MAE from .781 to .712. So any new
  posterior is judged at **matched bulk MAE**, not at its own default action.
* The classical E3WS-style feature + gradient-boosting baseline is far weaker at every
  deadline (5 s: MAE .310, M≥4 .713, M≥5 .961).

### Negative: the previous project's strongest recipe (emphasized Huber + 0.075 CE) is dominated

At the median action it lowers M≥4 MAE by .06–.09 but raises bulk MAE by +.006. On the
frontier, matching the CE posterior's M≥4 MAE costs **+.0049 [+.0040,+.0059] (1 s),
+.0054 [+.0046,+.0060] (3 s), +.0059 [+.0043,+.0073] (5 s)** more bulk MAE. Its apparent tail
gain is a move along the trade-off curve, not a better posterior.

### Mechanism evidence: the free model saturates

Scaling held-out M≥4 ground motion ×10 raises the categorical model's predicted median by only
**0.39–0.58** magnitude units. In the unseen Central Italy fold at 5 s the response is 0.39.
The amplitude–magnitude relation implies ≈1. Under a Gutenberg–Richter prior the Bayes
posterior is exactly shift-equivariant in log amplitude, even with unknown distance
(THEORY.md). The free network's flattened response is learned under-extrapolation.

### Scale-equivariant head (eq_nll): large gains for the largest events, but a bulk cost

| deadline | Δ bulk MAE | Δ M≥4 MAE | Δ M≥5 MAE | M≥5 at matched bulk |
|---|---|---|---|---|
| 1 s | +.0052 [+.0021,+.0077] | −.001 [−.014,+.018] | −.038 [−.108,+.038] | n/a (frontier never reaches ref bulk) |
| 3 s | +.0034 [−.0001,+.0065] | −.020 [−.037,+.001] | **−.185 [−.278,−.084]** | **−.117 [−.213,−.036]** |
| 5 s | +.0014 [−.0017,+.0039] | **−.036 [−.065,−.007]** | **−.249 [−.374,−.137]** | −.101 [−.219,+.049] |

(median action, eq − cat_ce)

* On the unseen 2016–17 Central Italy sequence (fold 0, includes the M6.5), the M≥5 MAE at 5 s
  falls from **1.008 to 0.550**. The bias for M6.5+ records goes from −1.62 to −0.62.
* **Where the bulk cost comes from:** essentially all of it is the M2.0–2.5 bin (44% of
  records; 1 s MAE .219 → .243). Every other bin is equal or better. The INSTANCE label
  histogram has a 9× cliff at M2.0 (14,790 records at M1.9 vs 130,227 at M2.0), a dataset
  selection rule rather than physics. A categorical head learns the cliff exactly; a smooth
  equivariant likelihood cannot.
* **Verdict for eq_nll alone:** it does not meet the objective (bulk is not preserved at 1 s).
  The next arm, `eqgr` (equivariant likelihood × free 0.1-bin prior below M3.5 × GR-linear tail
  prior), is designed to absorb exactly this cliff while keeping the equivariant tail.

Figures: `figures/frontier_*.png`, `figures/bias_by_magnitude.png`, `figures/amplitude_response.png`.

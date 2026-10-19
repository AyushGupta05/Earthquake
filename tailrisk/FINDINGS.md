# Findings log (newest first)

All numbers are pooled out-of-fold predictions over 1,159,249 INSTANCE records (346 M≥4
events, 31 M≥5) from 5 leave-sequence-out folds. Δ = arm − reference, with 95% cluster-bootstrap
intervals (1,000 replicates; whole GK sequences resampled). Negative Δ in an error is better.

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

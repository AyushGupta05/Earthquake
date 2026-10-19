# Findings log (newest first)

All numbers are pooled out-of-fold predictions over 1,159,249 INSTANCE records (346 M≥4
events, 31 M≥5) from 5 leave-sequence-out folds. Δ = arm − reference, with 95% cluster-bootstrap
intervals (1,000 replicates; whole GK sequences resampled). Negative Δ in an error is better.

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

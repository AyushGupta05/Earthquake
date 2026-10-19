# GR-factorized, scale-equivariant magnitude posteriors for early earthquake warning

**Started 18–19 Oct 2026.** A self-contained, re-runnable study of **reducing high-magnitude
(tail) error of single-station early magnitude estimates at 1, 3 and 5 s after the P arrival,
without worsening bulk error**, on INSTANCE (1,159,249 records, 54,008 events). The full
dated log, including negative results, is in [FINDINGS.md](FINDINGS.md); the theory is in
[THEORY.md](THEORY.md). An explanatory notebook is in
[tail_risk_study.ipynb](tail_risk_study.ipynb).

## Result in one paragraph

A deep magnitude posterior of the form

    p(m | x)  ∝  L_θ(m | A, s) · exp(φ(m))

* **L_θ** is a scale-equivariant Gaussian-mixture likelihood: component locations are
  κ(s)(A − A0) + g_k(s), where A is the log RMS amplitude in physical units and s the
  scale-free remainder of the waveform plus station metadata.
* **φ** is one learned global log-prior over magnitude, free below M3.5 and
  Gutenberg–Richter-linear above.

Against the plain categorical posterior (CE) and every other baseline tested, this lowers
high-magnitude error at 1, 3 and 5 s while bulk error stays equal (1 s) or improves
(3 s, 5 s). The leave-sequence-out cross-validation has 346 M≥4 and 31 M≥5 events, with
95% cluster-bootstrap intervals; the result was replicated across seeds and survives
ensembling. Two-seed ensembles, eqgr − CE, median action:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0005 [−.0026,+.0013] | **−.0028 [−.0050,−.0009]** | **−.0048 [−.0062,−.0039]** |
| Δ M≥4 MAE | **−.031 [−.049,−.011]** | **−.044 [−.069,−.020]** | **−.056 [−.089,−.027]** |
| Δ M≥5 MAE | **−.087 [−.155,−.012]** | **−.205 [−.309,−.100]** | **−.263 [−.385,−.154]** |
| Δ M≥4 event-MAE | **−.022 [−.042,−.003]** | **−.036 [−.065,−.014]** | **−.047 [−.083,−.022]** |

MedAE, CVaR95 (largest 5% of all errors) and the false-M4 rate are unchanged or better.
On the completely unseen 2016–17 Central Italy sequence, the 5 s M≥5 MAE falls from 1.008
to 0.502.

## Why it works: two failure mechanisms, two components

1. **Rare-bin prior learning.** A categorical (or free) posterior has to learn the label
   prior separately in every region of input space. The INSTANCE prior has sharp, non-physical
   structure: a 9× selection cliff at M2.0, and a steep Gutenberg–Richter decay that leaves
   M5+ bins nearly empty. **The GR-factorized prior φ** moves all of this into one global 1-D
   function, estimated from every record. The x-dependent likelihood can then stay smooth, and
   the tail is forced to be GR-linear rather than learned from a handful of events. On top of
   a TEAM-LM-style free mixture, this alone improves bulk, M≥4 and event-level M≥4 at every
   deadline (all CIs exclude zero).
2. **Learned amplitude saturation.** On held-out large events, free networks raise their
   prediction by only .39–.54 magnitude units per 10× of ground motion when amplitudes go
   *beyond* the training range, against .54–.66 when they go down. They flatten exactly
   where they must extrapolate. Under a GR prior the Bayes posterior is exactly
   shift-equivariant in log amplitude even with unknown distance (THEORY.md). **The
   equivariant likelihood** imposes this, with a learned slope κ(s) ≈ 0.6–0.8, and adds the
   large-event extrapolation: M≥5 −.115 / −.141 at 3 / 5 s beyond the factorized free mixture.

Equivariance without the prior factor *hurts* bulk (+.005 MAE, from the M2.0 cliff). The
two components are complementary.

## Baselines (identical trunk, data, folds, schedule)

| arm | what it is | verdict vs eqgr |
|---|---|---|
| `cat_ce` | 71-bin categorical posterior, cross-entropy | dominated (table above) |
| `cat_hubce` | previous project's best recipe: emphasized Huber + 0.075 CE | dominated on the frontier; needs +.005 bulk MAE to match CE's tail |
| `mix_nll` | free Gaussian mixture (TEAM-LM-style head), the strongest existing baseline | eqgr: bulk equal / −.0015 / −.0032, M≥4 −.020 / −.015 / −.023, M≥5 −.03 / −.115 / −.141 |
| `cat_aug` | amplitude-scaling augmentation (×10^Δ, label +Δ) | dominated even by CE; eqgr bulk −.011, bulk-capped M≥4 −.17 at every deadline |
| `cat_lds` | LDS loss reweighting (deep imbalanced regression) | see FINDINGS.md |
| `gbm_e3ws` | E3WS-style P-wave features + gradient boosting | far weaker (5 s MAE .310, M≥4 .713) |

Ablations: `eq_nll` (equivariant, no prior factor), `mixgr_nll` (prior factor, no
equivariance), `eqh_nll`, `eqd_nll` / `eqdgr_nll` (distance-aware), and `eqtgr_nll` (separate
ML/Mw slopes; exploratory). FINDINGS.md lists which were pre-specified and which exploratory.

**Known limitation:** in the 2012 Emilia sequence (fold 1, mostly ML-labelled large events),
eqgr is worse than the free mixture. One learned slope κ ≈ 0.7 (Mw-like) under-responds for
large ML labels, which scale ≈1:1 with amplitude.

## Protocol

* **Folds.** Gardner–Knopoff (1974) aftershock-sequence clusters, visited largest-first, so
  background seismicity is not chained together. They are assigned to 5 folds balancing M≥5,
  M≥4 and records. Fold 0 is the entire 2016–17 Central Italy sequence (M6.5, 43% of records).
* **Inputs** (causal, available at the deadline): the 1/3/5 s P-relative 3-component prefix
  converted to physical units with the StationXML sensitivity, 34 static instrument/site
  fields, and station coordinates. Catalogue source fields are used only to build folds and
  for analysis. Distance and magnitude type appear only as *training* labels in the
  exploratory joint heads.
* **Training.** One network serves all three deadlines. Every arm uses the same fixed
  schedule (10 epochs, AdamW 2e-3, cosine) and nothing on a held-out fold is selected.
* **Decisions.** The mean, the median, and the tail-weighted median a_r (r times the weight
  on M≥4 errors). r > 1 is exactly the original "multiply tail mass by r, take the median"
  rule. For a fixed posterior it is Bayes-optimal for every bulk/tail trade-off, so arms are
  also compared on their *frontiers*: the best tail error achievable without exceeding the
  reference's bulk MAE.
* **Uncertainty.** A paired bootstrap that resamples whole aftershock sequences (1,000
  replicates).

## Files

| file | purpose |
|---|---|
| `prep_data.py`, `prep_waveforms.py` | metadata, static instrument features, GK folds, float16 waveform copy |
| `common.py` | GPU data, causal amplitude/shape features, decision rules, metrics |
| `models.py` | encoder; categorical, mixture, equivariant, GR-factorized, distance- and scale-mixture heads |
| `train.py`, `run_queue.sh`, `master.sh`, `queue*.txt` | training and the exact commands run |
| `evaluate.py`, `summary_table.py` | pooled metrics, frontiers, bulk-capped comparisons, cluster bootstrap |
| `diagnostics.py` | amplitude-response (saturation) and calibration diagnostics |
| `gbm_baseline.py` | E3WS-style classical baseline |
| `test_decisions.py` | decision-rule checks against brute force |
| `make_figures.py`, `build_notebook.py` | figures and the explanatory notebook |
| `results/` | evaluation JSON, diagnostics, fold summary |
| `figures/` | frontier, bias-by-magnitude and amplitude-response plots |

Large arrays (waveform copy, per-record predictions, checkpoints) live in
`/mnt/eew-research/runs/tailwork` on the AWS host and are not in Git.

Reproduce one arm: `python tailrisk/train.py --arm eqgr_nll --head eqgr --loss nll --epochs 10`
(≈1 h on one A10G for all 5 folds), then
`python tailrisk/evaluate.py --arms cat_ce,eqgr_nll --ref cat_ce`.

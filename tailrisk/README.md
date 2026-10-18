# Tail-risk study: scale-equivariant magnitude distributions (started 18–19 Oct 2026)

This directory contains a self-contained, re-runnable study of **reducing the high-magnitude
(tail) error of early magnitude estimates at 1, 3 and 5 s while keeping bulk error
constant**, on INSTANCE. It replaces the earlier VAL-only protocol (13 M≥4 events, one M≥5)
with leave-sequence-out cross-validation over every recording (346 M≥4 events, 31 M≥5).

## Why a new protocol

* The old 2018 VAL split has only 13 M≥4 events and one M5.1 event. A tail claim on it rests
  on one or two earthquakes, and VAL had already been reused for many earlier selections.
* We pool TRAIN+VAL+TEST (1,159,249 records, 54,008 events) and split events into
  **Gardner–Knopoff (1974) aftershock sequences**. Each event's GK window (distance
  10^(0.1238M+0.983) km; time 10^(0.5409M−0.547) days, longer above M6.5) claims later
  events, and a quarter of that window claims earlier ones (foreshocks). Visiting
  events largest-first prevents the chaining that a naive space–time linkage produced
  (55% of all events in one cluster).
* Sequences are assigned to 5 folds, balancing M≥5 events, M≥4 events and records. The
  whole 2016–17 Central Italy sequence (M6.5, 43% of records, 74 M≥4 events) forms fold 0, so
  one fold tests a completely unseen major sequence.
* Every record gets one out-of-fold prediction. Uncertainty comes from a **paired cluster
  bootstrap**, which resamples whole sequences.

## What is compared

All arms share one waveform encoder/trunk (residual 1-D CNN on the scale-normalized
physical-unit prefix, amplitude-ratio features, 34 static instrument/site fields plus
station coordinates, and a duration one-hot). One network serves all three deadlines.
Every arm uses the same fixed schedule (10 epochs, AdamW 2e-3, cosine), and no held-out
fold selects anything. Arms differ only in head/loss:

| arm | description |
|---|---|
| `cat_ce` | 71-bin categorical posterior, cross-entropy (natural-population proper score) |
| `cat_hubce` | the prior project's strongest recipe: emphasized Huber on the mean (1+5·max(M−3.5,0)) + 0.075·CE |
| `mix_nll` | free Gaussian-mixture posterior (log amplitude as an ordinary input) |
| `cat_aug` | categorical + amplitude-scaling augmentation (×10^Δ, label +Δ, Δ~U(−0.5,0.5)) |
| `cat_lds` | categorical + LDS (Yang et al. 2021) inverse-sqrt smoothed-density loss weights |
| **`eq_nll`** | **scale-equivariant mixture posterior** (proposed) |
| **`eqgr_nll`** | equivariant likelihood × learned prior that is Gutenberg–Richter-linear above M3.5 (proposed) |
| `eqh_nll` | ablation: equivariant + bounded (±0.5) free amplitude correction |

### The proposed constraint

Let A = log10 RMS of the physical-unit (counts / sensitivity) prefix and s its
scale-free description (normalized waveform, amplitude ratios, station metadata, duration).
The equivariant posterior is a mixture with component locations

    mu_k(x) = kappa(s) * (A - A0) + g_k(s),     kappa in [0.3, 1.5]

and weights and widths that depend only on s. Multiplying the ground motion by c moves
the whole predictive distribution by kappa·log10 c, exactly. This is the classical
log-amplitude magnitude relation (M ≈ log A + f(distance, site)), imposed on a deep
distributional model. The free model can only learn this relation from data, and data are
scarcest exactly where it matters: large amplitudes from rare large earthquakes. With a
Gutenberg–Richter (exponential) prior and a Gaussian amplitude likelihood, Bayes shrinkage
is a constant shift, so the constrained family still contains the Bayes posterior. The
constraint removes data-driven saturation in the sparse tail without forbidding legitimate
shrinkage.

### Decisions and the frontier

From each saved posterior we compute the mean, the median and the tail-weighted medians
a_r = argmin_a E[w_r(M)|a−M|], where w_r = r above M4 and 1 below. r>1 is exactly the
original "multiply tail mass by r and take the median" rule; r<1 trades tail for bulk.
Sweeping r traces each arm's bulk-MAE vs tail-MAE frontier. For a fixed posterior this
rule is Bayes-optimal for every bulk/tail trade-off, so **a better frontier can only come
from a better posterior**. Arms are compared at matched bulk MAE, so no arm can win by
moving along the trade-off.

## Files

* `prep_data.py` – metadata, 34 static instrument features (reuses the audited StationXML
  join), GK sequence clusters, folds.
* `prep_waveforms.py` – float16 copy of the 5 s cache (1 s and 3 s are exact prefixes).
* `common.py` – GPU data, causal features, decision rules, metrics.
* `models.py` – encoder, categorical / mixture / equivariant / equivariant-GR heads.
* `train.py` – trains one arm across folds and saves out-of-fold decisions and PMFs.
* `evaluate.py` – pooled metrics, frontiers, matched-bulk comparisons, cluster bootstrap.
* `run_queue.sh`, `queue*.txt` – the exact arm commands that were run.

Large arrays live in `/mnt/eew-research/runs/tailwork` (not in Git).

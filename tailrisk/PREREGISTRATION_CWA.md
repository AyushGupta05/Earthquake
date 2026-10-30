# Pre-registered test on a fifth catalogue: CWA (Taiwan)

Written 30 Oct 2026 at about 21:05 UTC (commit 5be5d4f), while the cache is being built, before any model has been
trained or evaluated on CWA, and committed before the first CWA training run starts. Only metadata
summaries (trace, event and family counts; unit checks against the catalogue PGA / PGV) have been
looked at. Nothing below may change after CWA results are seen.

## Why CWA

* It is a dense local network: 1,115 stations, median epicentral distance 94 km.
* It has many large events: 317 M ≥ 5, 43 M ≥ 6 and 3 M ≥ 7 events after selection.
* Every event carries the same magnitude type (CWA local magnitude, ML) on both sides of M5. That
  makes it a direct test of the post hoc explanation for the two failed capped tests (FINDINGS.md,
  11:10 entry): capped extrapolation beats amplitude augmentation where the label scale is
  consistent across the cap.

## Data

`cwa_prep.py` (SeisBench mirror, 2011–2021). The cache keeps:
* the 1,237,801 traces at 100 Hz, dropping the 7% TSMIP traces at 200 / 500 Hz;
* families HL (accelerometer, m/s²), EH and HH (velocity, m/s), with the catalogue's manual P pick
  and a finite, non-zero vertical component;
* a 5 s window after P, components E, N, Z.

Labels are the catalogue ML. Folds are 5 Gardner–Knopoff leave-sequence-out folds (`prep_data.py`
rules). Environment: `TAILWORK_DIR=<cwa cache> TAILWORK_MAXMAG=9.5`, default distance bins.

## Arms (10 epochs, all other arguments at their defaults; seeds 20261018, 2, 3)

| arm | seeds | role |
|---|---|---|
| `mix_nll` | 1–3 | reference: free Gaussian mixture (TEAM-LM-style) |
| `eqdgr_nll` | 1–3 | method, primary: distance-marginalized equivariant head × GR prior factor |
| `eqgr_nll` | 1–3 | method, secondary |
| `mixgr_nll` | 1–3 | ablation: prior factor only |
| `mixdgr_nll` | 1–3 | equal-information control: free distance-mixture head |
| `eqgr_k1_nll` | 1 | ablation: κ ≡ 1 |
| `mix_cap50`, `mix_cap50_aug15`, `eqgr_cap50`, `eqdgr_cap50_cond`, `mixgr_cap50`, `eqgr_k1_cap50` | 1 | capped test, trained on M < 5.0 (bin filter) |

## Endpoints and statistics

At 1, 3 and 5 s, median action, as in `PREREGISTRATION_STEAD.md`:
* E1 record-level M ≥ 5 MAE, E2 event-level M ≥ 5 MAE, E3 bulk MAE, E4 false-M4 rate (M < 3.5
  records predicted ≥ 3.95, per 10⁴).
* M ≥ 6 is reported, not decided on.
* Three-seed ensembles are posterior mixtures. Intervals are the delete-one-cluster jackknife over
  the clusters carrying the tail (t, G − 1), plus the cluster bootstrap (`robust_tail.py`).

## Decision rules

* **D1, main (as STEAD).** For a head's ensemble against the `mix` ensemble: E1 < 0 at 3 s and 5 s
  with jackknife intervals excluding zero, and E3 ≤ +0.002 at every deadline. `eqdgr` is primary,
  `eqgr` secondary.
* **D2, equal information.** Both conditioned on the catalogue distance (σ = 0): `eqdgr` ensemble −
  `mixdgr` ensemble, E1 < 0 at 3 s and 5 s with jackknife intervals excluding zero, and E3 ≤ +0.002 at
  every deadline.
* **D3, capped (the label-scale prediction).** `eqdgr_cap50_cond` against `mix_cap50` and against
  `mix_cap50_aug15`: E1 < 0 at 3 s and 5 s, jackknife intervals excluding zero, in both comparisons.
  Its M < 5 MAE may be no more than 0.005 above `mix_cap50`'s. `eqgr_cap50` is secondary. If D3
  fails, the label-scale explanation of the GEOFON and STEAD failures is not supported.
* **D4, pooled over five catalogues.** INSTANCE M ≥ 5, Chile M ≥ 6, GEOFON M ≥ 7, STEAD M ≥ 5 and
  CWA M ≥ 5, three-seed ensembles, `meta_analysis.py`. For `eqdgr` − `mix` (marginal) and separately
  for `eqdgr` given r − `mixdgr` given r: the HKSJ interval (4 df) of the random-effects tail Δ
  excludes zero at 3 s and 5 s, and the pooled bulk Δ ≤ +0.002 at every deadline. These are new
  secondary claims, stated before CWA is seen. They do not replace the four-catalogue analyses
  already reported.

Every outcome, including failures, goes into FINDINGS.md and the README.

## Compute

The cache is built on the second GPU host. Training runs on the EC2 GPU hosts and/or SageMaker,
with the queue in `sm_queues/queue_cwa.txt`. Where an arm runs does not change it.

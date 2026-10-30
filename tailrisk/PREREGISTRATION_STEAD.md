# Pre-registered out-of-sample test on STEAD (fourth catalogue)

Written 30 Oct 2026, **before any model has been trained or evaluated on STEAD**, and committed
before the first STEAD training run starts. Its purpose is to answer the audit's model-selection
concern (`AUDIT_2026-10-30.md`, M3): every architecture and setting below was chosen on INSTANCE,
GEOFON and Chile, and none may be changed after STEAD results are seen.

## Data

The STEAD cache built by `stead_prep.py` and described in `STEAD_DATA.md`: 996,894 P-aligned
three-component records (5 s at 100 Hz, ground velocity in m/s), 435,893 events, 2,579 stations,
5 Gardner–Knopoff leave-sequence-out folds; 718 M≥5 events in 456 clusters and 63 M≥6 events in
51 clusters. Labels as built (one magnitude per event; preferred type Mw* > ML > Md > mbLg > mb).
Environment: `TAILWORK_DIR=/mnt/scratch/stead TAILWORK_MAXMAG=9.5 TAILWORK_MAXLOGR=3.0`, `--mode cv`.

## Arms (fixed; no tuning on STEAD)

Exactly the INSTANCE recipe: `train.py --loss nll --epochs 10`, all other arguments at their
defaults, seeds 20261018 (seed 1), 2 and 3.

| arm | head | role |
|---|---|---|
| `mix_nll`, `_s2`, `_s3` | free Gaussian mixture (TEAM-LM-style) | reference |
| `mixgr_nll`, `_s2`, `_s3` | free mixture × GR prior factor | ablation (prior only) |
| `eqgr_nll`, `_s2`, `_s3` | equivariant mixture × GR prior factor | method (plain) |
| `eqdgr_nll`, `_s2`, `_s3` | distance-marginalized equivariant × GR prior factor | **method (primary, locked 10-epoch version)** |
| `eqgr_k1_nll` (seed 1) | `eqgr` with κ ≡ 1 | secondary ablation (Zhang, Zhang & Tian 2021 construction) |

## Endpoints (each at 1, 3 and 5 s; median action; three-seed ensembles = mixture of posteriors)

- **E1** record-level M≥5 MAE; **E2** event-level M≥5 MAE (mean over events of the mean over
  their records); **E3** bulk MAE over all records; **E4** false-M4 rate: share of M<3.5 records
  whose estimate is ≥ 3.95, per 10⁴.
- Also reported, not part of the decision: M≥4 and M≥6 MAE, signed bias by 0.5-unit bin, NLL,
  CRPS.

## Statistics

- Differences are **observed** values (full-sample arm − reference), not bootstrap means.
- Intervals: (i) the project's paired cluster bootstrap (1,000 replicates over GK clusters);
  (ii) for E1 and E2, a delete-one-cluster jackknife over the clusters that contain M≥5 events,
  with t quantiles on G − 1 degrees of freedom; plus leave-one-cluster-out range, the Δ without
  the single largest M≥5 cluster, and the count of clusters with Δ < 0.
- Seeds are reported descriptively (no sign test over dependent cells).

## Decision rule

The method is **confirmed on STEAD** for a head if, for its ensemble against the mixture
ensemble:

1. E1 < 0 at 3 s and at 5 s with the jackknife interval (ii) excluding zero, and
2. E3 ≤ +0.002 at every deadline.

`eqdgr` is the primary test; `eqgr` is secondary. E4 is reported whatever the outcome, with
absolute rates. Any outcome, including failure, is written to `FINDINGS.md` and the README.

## Pre-specified subgroups (reported, not part of the decision)

Mw-type tail only (`mag_type` starting with `Mw`); excluding the gain-QC suspects
(`gain_qc.npz`); per region (Alaska–Aleutians, Chile–Argentina, Greece–Aegean, New Zealand,
California–Nevada).

## What may not change after results are seen

Hyperparameters, epochs, folds, labels, thresholds, the decision action (median), the
reference arm and this decision rule.

# Pre-registered capped-training test on GEOFON (fourth capped catalogue)

Written 30 Oct 2026 at about 07:20 UTC, before any capped GEOFON arm has been trained, and
committed before they are queued. It repeats the extrapolation test of Proposition 3 (THEORY.md),
which was designed on INSTANCE and Chile, on the catalogue with the most independent large
events. Nothing below may change after capped GEOFON results are seen.

## Data

The GEOFON regional cache (`geofon_prep.py`; 31,020 records, 2,212 events; label median M4.76).
It has 276 M ≥ 6 events in 208 clusters and 50 M ≥ 7 events in 46 clusters. Folds and
environment are those of the existing GEOFON runs: `TAILWORK_DIR=$W/geofon TAILWORK_MAXMAG=9.5`,
default distance bins. Training keeps only records whose label bin lies below M6.0
(`--train-mag-cap 6.0`, bin filter; 27,322 of the 31,020 records, all folds). Every held-out record
is scored, so every M ≥ 6 event lies beyond the training range.

## Arms (10 epochs, all other arguments at their defaults)

| arm | seeds | role |
|---|---|---|
| `mix_cap60` | 1, 2, 3 | reference: free Gaussian mixture (TEAM-LM-style) |
| `mix_cap60_aug15` | 1 | existing-method baseline: amplitude-scaling augmentation ±1.5 decades |
| `eqdgr_cap60_cond` | 1, 2, 3 | method (primary): distance-marginalized form, `--cap-latent conditional` |
| `eqgr_cap60` | 1, 2, 3 | method (plain) |
| `eqgr_k1_cap60` | 1 | existing-method baseline: κ ≡ 1 (Zhang, Zhang & Tian 2021) |
| `magnet_cap60` | 1 | existing-method baseline: published MagNet architecture, Gaussian NLL |
| `mixgr_cap60` | 1 | ablation: prior factor only |

The classical laws are fitted on the same capped rows (`linear_arms.py --cap 6.0`). The free
mixture trained on all magnitudes (`mix_nll`, three seeds) gives context. Neither is part of the
decision.

## Endpoints (1, 3 and 5 s; median action)

- **G1** record-level M ≥ 6 MAE; **G2** event-level M ≥ 6 MAE; **G3** record-level M ≥ 7 MAE;
  **G4** MAE over records with M < 6; **G5** false-alarm rate, the share of M < 5 records
  predicted ≥ 5.95, per 10⁴. Signed bias by 0.5-unit label bin from M6.0 up.
- Statistics as in `PREREGISTRATION_STEAD_CAP.md`: observed differences, paired cluster
  bootstrap, and for G1–G3 the delete-one-cluster jackknife over the clusters carrying the tail,
  with t on G − 1 df (`robust_tail.py --thr 6,7 --fp-low 5.0 --fp-cut 5.95`).

## Decision rule

Extrapolation is **confirmed on GEOFON** for a method head if, at 3 s and at 5 s:

1. the three-seed ensemble's G1 is lower than that of the `mix_cap60` three-seed ensemble, with
   the jackknife interval excluding zero;
2. the seed-1 arm's G1 is lower than that of `mix_cap60_aug15`, with the jackknife interval
   excluding zero;
3. the ensemble's G4 is no more than 0.005 above that of the `mix_cap60` ensemble.

`eqdgr_cap60_cond` is primary and `eqgr_cap60` secondary. The 1 s deadline is reported, not
decided on. Any outcome goes into FINDINGS.md.

## Compute

GEOFON arms train in a few GPU-minutes, so all 13 run on the main host
(`queue_geofon_cap60.txt`).

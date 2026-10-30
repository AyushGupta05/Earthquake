# Pre-registered capped-training test on STEAD

Written 30 Oct 2026 at about 04:25 UTC, **before any STEAD arm has finished training (one fold
of the reference arm had) and before any STEAD prediction has been looked at**, and committed
before these arms are queued (first commit bc5ab2b; this wording and the time corrected after). It
extends `PREREGISTRATION_STEAD.md` with the extrapolation test of Proposition 3 (THEORY.md),
which was designed on INSTANCE and Chile (FINDINGS.md, 30 Oct 04:15 and 04:25). Nothing below
may change after STEAD results are seen.

## Data

The STEAD cache of `PREREGISTRATION_STEAD.md` (996,894 records; 718 M ≥ 5 events in 456
clusters; 63 M ≥ 6 events in 51 clusters), same folds and environment. Training uses only
records with label M < 5.0 (`--train-mag-cap 5.0`); every record of every held-out fold is
scored, so all M ≥ 5 events lie beyond the training range.

## Arms (seed 20261018, 10 epochs, all other arguments at their defaults)

| arm | role |
|---|---|
| `mix_cap50` | reference: free Gaussian mixture (TEAM-LM-style) |
| `mix_cap50_aug15` | existing-method baseline: free mixture with ±1.5-decade amplitude-scaling augmentation |
| `eqgr_cap50` | method (plain): equivariant mixture × GR prior factor, prior truncated at the cap in training |
| `eqdgr_cap50_cond` | method (primary): distance-marginalized form, `--cap-latent conditional` |
| `eqgr_k1_cap50` | existing-method baseline: κ ≡ 1 (Zhang, Zhang & Tian 2021 construction) |
| `magnet_cap50` | existing-method baseline: published MagNet architecture with Gaussian NLL |
| `mixgr_cap50` | ablation: prior factor only |

## Endpoints (1, 3 and 5 s; single seed; median action)

- **C1** record-level M ≥ 5 MAE; **C2** event-level M ≥ 5 MAE; **C3** record-level M ≥ 6 MAE;
  **C4** bulk MAE over records with M < 5; **C5** false-M4 rate (share of M < 3.5 records
  predicted ≥ 3.95, per 10⁴); signed bias by 0.5-unit label bin from M5.0 up.
- Comparisons are observed differences against `mix_cap50`, and against `mix_cap50_aug15`, with
  the paired cluster bootstrap (1,000 replicates) and, for C1–C3, the delete-one-cluster jackknife
  over the clusters that contain M ≥ 5 (resp. M ≥ 6) events with t quantiles on G − 1 degrees of
  freedom (`robust_tail.py`). Also reported, not part of the decision: the comparison with the
  full-data free mixture `mix_nll` (seed 1 of the main pre-registered test).

## Decision rule

Extrapolation is **confirmed on STEAD** for a method arm if, at 3 s and at 5 s:

1. C1 is lower than for `mix_cap50` with the jackknife interval excluding zero;
2. C1 is lower than for `mix_cap50_aug15` with the jackknife interval excluding zero;
3. C4 is no more than 0.005 above `mix_cap50`'s.

`eqdgr_cap50_cond` is primary and `eqgr_cap50` secondary. The 1 s deadline is reported but not
part of the decision, because the physical saturation of a 1 s window (about M5.7) bounds what
any model can recover there. The κ ≡ 1 and MagNet arms are reported against the method arms with
the same statistics. Any outcome, including failure, goes into FINDINGS.md and the README.

## Pre-specified subgroups (reported, not part of the decision)

Moment-magnitude labels only (`mag_type` starting with `Mw`), which removes any advantage an
amplitude-equivariant model could have on amplitude-defined labels; excluding the gain-QC
suspects; per region (as in `PREREGISTRATION_STEAD.md`).

## Compute

Seven arms of about one GPU-hour each, queued after STEAD seed 3 on the second host (or on a
further host if the GPU quota allows).

## Amendment 1 (30 Oct 2026, 05:10 UTC; before any capped STEAD arm has started)

An adversarial audit of the INSTANCE and Chile capped runs found an implementation bug: labels in
[cap − 0.05, cap) round into the cap's own 0.1 bin, which the truncated prior factor masks, so
each such training record costs about 10⁴ nats. STEAD has 23 such rows. All STEAD capped arms
therefore use the bin-consistent filter (`--cap-filter bin`, the default from this commit on):
a record is kept if its label's bin lies below the cap. Nothing else changes.

Also reported, as context and **not part of the decision rule**: the classical log-amplitude laws
of `linear_baseline.py` fitted on the same capped training rows and folds. These are forward
regression of M on amplitude, and the inverse law A = a + bM + c·z solved for M, with z either
the scale-free invariants or the true catalogue log distance (an oracle the networks do not get).

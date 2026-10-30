# Pre-registered equal-information test: equivariant vs free distance head, both conditioned on distance

Written 30 Oct 2026 at about 10:35 UTC, before the free distance-mixture arms this test needs have
been trained on STEAD, Chile or INSTANCE seeds 2–3, and committed before they are queued.

## Question

Conditioned on a known distance at inference (`condr_arms.py`), the distance-marginalized
equivariant head (`eqdgr`) beats the free mixture on large events on all four catalogues
(FINDINGS.md, 07:30, 08:55 and 10:35 entries). But the free mixture is not given the distance, so
that comparison does not show equivariance is needed once distance is known. The equal-information
control is the free distance-mixture head (`mixdgr`). It has the same latent distance label, the
same joint training and the same conditioning at inference, but no equivariance.

## What has already been seen (disclosed)

* INSTANCE seed 1: `eqdgr` given r against `mixdgr` given r, M ≥ 5 −.14 / −.16 / −.17 at 1 / 3 / 5 s,
  jackknife intervals excluding zero (FINDINGS.md 07:30 entry).
* GEOFON `mixdgr_nll` seeds 1–3 exist and have been evaluated marginally, with no distance
  conditioning (20–22 Oct). Their distance-conditioned predictions have not been computed.
* No `mixdgr` arm exists on STEAD or Chile.

## Arms (10 epochs, defaults, seeds 20261018 / 2 / 3)

`mixdgr_nll`, `mixdgr_nll_s2`, `mixdgr_nll_s3` (`--head mixdgr --loss nll`) on STEAD, Chile and
GEOFON (GEOFON already trained), and `mixdgr_nll_s2`, `mixdgr_nll_s3` on INSTANCE (seed 1 exists).
The `eqdgr` arms are the existing three seeds. Both heads are conditioned with `condr_arms.py`
(σ = 0, the catalogue hypocentral distance; σ = 0.1 also reported).

## Endpoints and statistics

Per catalogue: record-level MAE at the primary threshold (INSTANCE M ≥ 5, Chile M ≥ 6, GEOFON
M ≥ 7, STEAD M ≥ 5) and bulk MAE. Three-seed ensembles, median action, contrast
`eqdgr` given r − `mixdgr` given r. Delete-one-cluster jackknife per catalogue (`robust_tail.py`),
pooled with `meta_analysis.py`: DerSimonian–Laird random effects with the HKSJ interval of
record, plus the pooled cluster sign test.

## Decision rule

Equivariance is **shown to matter at equal information** if the pooled HKSJ interval for the tail
Δ excludes zero at 3 s and at 5 s, and the pooled bulk Δ (random effects) is ≤ +0.002 at every
deadline. Per-catalogue results are reported whatever the outcome, with STEAD alone also judged by
its jackknife interval at 3 and 5 s.

## Compute

STEAD and Chile arms: one SageMaker job (`sm_queues/queue_sm_mixdgr.txt`). INSTANCE seeds 2–3: a
second job. GEOFON: none.

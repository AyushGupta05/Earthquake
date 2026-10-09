# Earthquake research — live checkpoint, 9 October 2026

**Research and AWS experiments remain active. No novel method or superiority to a published benchmark has yet been established.** The strongest completed practical result is adding instrument/site information to a matched residual-distribution model: both training seeds improve bulk, high-magnitude and worst-error measures at 1, 3 and 5 seconds. The reused validation set contains only 13 M≥4 earthquakes and one M≥5 earthquake. Sensor-family and station effects require further controls.

Current reports:

- [Method status and decisions](earthquake_method_status.md): one table covering completed, rejected and running approaches.

- [Instrument results](earthquake_instrument_results.md): two-seed comparisons, event-bootstrap intervals and remaining limitations.
- [Full TRAIN replication](earthquake_instrument_full_results.md): gains survive all 979,487 training records.
- [Instrument feature ablations](earthquake_instrument_factor_results.md): gain/unit and station-related information.
- [Instrument scientific audit](earthquake_instrument_scientific_audit.md): station fingerprints, sensor families and per-event evidence.
- [Affine-prefix results](earthquake_affine_results.md): completed six-run control; high-magnitude objective not met.
- [Residual support audit](earthquake_residual_support_audit.md): exact limits of the existing bounded logit correction.
- [Physical prefix preflight](earthquake_physical_prefix_preflight.md): causal synthetic controls; covariance alone fails the tail objective.
- [Censored sequential results](earthquake_censored_results.md): completed likelihood/update controls and independent audit; no sub-second continuation.
- [Additional 2026 architecture audit](earthquake_recent_architecture_audit.md): SeisMamba, MP-Net, South Asian classification and strain/DAS approaches.
- [Future-growth results](earthquake_growth_results.md): completed matched grid; the conditional likelihood fails the objective.
- [Resolution-head results](earthquake_resolution_results.md): completed two-seed grid; the revision candidate fails the all-duration tail objective.
- [Current competitors](earthquake_current_competitors.md): recent primary papers, source-code checks and incompatible evaluation protocols.
- [Revision prior art](earthquake_revision_prior_art.md): why forecast-revision prediction and distillation alone are not new.
- [Amplitude-distribution analysis](earthquake_amplitude_distribution_research.md): conditional growth models, derivations and negative synthetic results.
- [Current Chile protocol](earthquake_chile_execution_protocol.md): verified data, true split counts, timing, models and recovery.
- [Alaska cohort audit](earthquake_alaska_cohort_audit.md): 781 archive names resolve to 780 current events; published 530-event membership remains unresolved.
- [October conformal-PGA paper audit](earthquake_conformal_pga_audit.md): useful uncertainty controls, with an important April-code/October-paper mismatch.
- [Additional external validation resources](earthquake_external_validation_expansion.md): recorded Alaska events and controlled Cascadia simulations.
- [External benchmark plan](earthquake_external_benchmark_plan.md): the Chile TEAM-LM data and evaluation protocol; implementation and worker setup have since advanced.
- [AWS execution note](aws_execution_note.md): verified quota, credits, new worker, automatic stop and cleanup obligations.

Reviewed implementations are committed and pushed to `AyushGupta05/Earthquake` on `main`. Recent commits include `75caeb7` (full-data results and audits), `01023ca` (deterministic controls and completed negative results), `d655c3a` (censored/uncensored sequential updates), `8504094` (reviewed sequential-export I/O fix), `f3f18e4` (proper-score controls/full Chile launch), `b5f8ad1` (method and external-data audits), `d91a1c3` (censored negative result), `823366d` (verified cache exporter), `1d7510d` (residual support audit and cache launch), `ba6a852`/`98c9d13` (cache integration and proof), and `373be20` (completed affine audit). Focused tests and clean Codex reviews are retained with the experiments.

Resolution replication, instrument-factor ablations, full TRAIN instrument replication and future-growth target extraction are complete. The matched future-growth grid is complete and rejected. All four TRAIN-only Chile hardware pilots passed. The full deterministic TEAM-style baseline started at 19:30 UTC with 25 station-pretraining and 100 event-training epochs. The censored amplitude-innovation pilot completed and failed the intended mechanism comparison; deterministic affine-prefix controls are complete and fail the high-magnitude objective; the reviewed five-arm proper-score experiment is running on the original worker. Chile TEST waveforms have not been loaded. The dedicated worker has a 35-hour process limit and a verified automatic stop at 07:28:52 UTC on 11 October; the authorized experiment ceiling remains $2,000 in AWS credits.

Historical reports remain available for transparency:

- [Initial literature review](earthquake_literature_review.md), [initial experiments](earthquake_experiment_results.md), and [experiment log](earthquake_experiment_log.md).
- [Phase-two results](earthquake_phase2_results.md) and [sequential-method research](earthquake_sequential_method_research.md).
- [Initial reproducibility archive](earthquake_research_reproducibility.zip): **historical snapshot only**; later source, reviews and results are in the Git repository.

Comparisons with published papers require matched data, time origin, event split, available stations and magnitude definition. Smaller error on INSTANCE cannot be directly compared with TEAM's multi-station Chile error.

A thread continuation check runs every 30 minutes, staying quiet unless there is a meaningful change. Paid work remains subject to verified credit coverage, the $2,000 ceiling and resource stop timers.

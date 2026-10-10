# Earthquake research — live checkpoint, 10 October 2026

**Research and AWS experiments remain active. No novel method or superiority to a published benchmark has yet been established.** The strongest completed practical result is adding instrument/site information to a matched residual-distribution model: both training seeds improve bulk, high-magnitude and worst-error measures at 1, 3 and 5 seconds. The reused validation set contains only 13 M≥4 earthquakes and one M≥5 earthquake. Sensor-family and station effects require further controls.

Current reports:

- [Frozen distribution pilots](earthquake_distribution_pilots.md): both grids complete and independently audited; both fail the fixed improvement criteria; all negative results and reporting-recovery evidence retained.

- [Method status and decisions](earthquake_method_status.md): one table covering completed, rejected and running approaches.

- [Instrument results](earthquake_instrument_results.md): two-seed comparisons, event-bootstrap intervals and remaining limitations.
- [Full TRAIN replication](earthquake_instrument_full_results.md): gains survive all 979,487 training records.
- [Instrument feature ablations](earthquake_instrument_factor_results.md): gain/unit and station-related information.
- [Instrument scientific audit](earthquake_instrument_scientific_audit.md): station fingerprints, sensor families and per-event evidence.
- [Affine-prefix results](earthquake_affine_results.md): completed six-run control; high-magnitude objective not met.
- [Residual support audit](earthquake_residual_support_audit.md): exact limits of the existing bounded logit correction.
- [Proper-score results](earthquake_proper_score_results.md): completed thirty-model comparison, independent metrics and full GPU replay.
- [Context-weighted results](earthquake_context_reference_results.md): completed, independently audited negative pilot; both seeds regress on high magnitudes at every deadline.
- [Polarization results](earthquake_polarization_results.md): completed 18-fit negative diagnostic with new event/station panels; all six fixed criteria fail.
- [Shared-cap preflight](earthquake_shared_cap_preflight.md): completed negative conditional-likelihood result.
- [Retrieval prior-art addendum](earthquake_retrieval_prior_art.md): RATE/EQ-RAG narrows the novelty claim for historical-waveform references.
- [Missing-evidence hypotheses](earthquake_missing_evidence_hypotheses.md): noise-aware vector motion, historical path references and label-scale limits.
- [Source-scaling audit](earthquake_source_scaling_audit.md): why stretching recordings can manufacture misleading early-magnitude evidence.
- [Physical prefix preflight](earthquake_physical_prefix_preflight.md): causal synthetic controls; covariance alone fails the tail objective.
- [Censored sequential results](earthquake_censored_results.md): completed likelihood/update controls and independent audit; no sub-second continuation.
- [Additional 2026 architecture audit](earthquake_recent_architecture_audit.md): SeisMamba, MP-Net, South Asian classification and strain/DAS approaches.
- [Future-growth results](earthquake_growth_results.md): completed matched grid; the conditional likelihood fails the objective.
- [Resolution-head results](earthquake_resolution_results.md): completed two-seed grid; the revision candidate fails the all-duration tail objective.
- [Current competitors](earthquake_current_competitors.md): recent primary papers, source-code checks and incompatible evaluation protocols.
- [Revision prior art](earthquake_revision_prior_art.md): why forecast-revision prediction and distillation alone are not new.
- [Amplitude-distribution analysis](earthquake_amplitude_distribution_research.md): conditional growth models, derivations and negative synthetic results.
- [Completed Chile floor diagnostic](earthquake_chile_floor_diagnostic.md): verified negative mechanism result; baseline complete and preserved, dedicated worker verified stopped.
- [Chile density-objective claim audit](earthquake_chile_density_claim_audit.md): exact likelihood-floor and normalized-Huber prior art; completed TRAIN-fit-only diagnostic fails its incidence gate; no Huber continuation.
- [Current Chile protocol](earthquake_chile_execution_protocol.md): verified data, true split counts, timing, models and recovery.
- [Alaska header audit](earthquake_alaska_header_audit.md): all 296,990 channels join metadata after fixing location-code normalization; timing/coverage limits remain explicit.
- [Alaska cohort audit](earthquake_alaska_cohort_audit.md): 781 archive names resolve to 780 current events; published 530-event membership remains unresolved.
- [October conformal-PGA paper audit](earthquake_conformal_pga_audit.md): useful uncertainty controls, with an important April-code/October-paper mismatch.
- [Additional external validation resources](earthquake_external_validation_expansion.md): recorded Alaska events and controlled Cascadia simulations.
- [External benchmark plan](earthquake_external_benchmark_plan.md): the Chile TEAM-LM data and evaluation protocol; implementation and worker setup have since advanced.
- [AWS execution note](aws_execution_note.md): verified quota, credits, new worker, automatic stop and cleanup obligations.

Reviewed implementations are committed and pushed to `AyushGupta05/Earthquake` on `main`. The new distribution pilots and independent export audit were frozen before fitting in `95db8b5`. Recent commits include `75caeb7` (full-data results and audits), `01023ca` (deterministic controls and completed negative results), `d655c3a` (censored/uncensored sequential updates), `8504094` (reviewed sequential-export I/O fix), `f3f18e4` (proper-score controls/full Chile launch), `b5f8ad1` (method and external-data audits), `d91a1c3` (censored negative result), `823366d` (verified cache exporter), `1d7510d` (residual support audit and cache launch), `ba6a852`/`98c9d13` (cache integration and proof), `373be20` (completed affine audit), `6c31e29` (reviewed context pilot), `e27b860` (negative shared-cap audit), `76443bc` (proper-score full audits and GPU replay), `63f4376` (corrected feature inventory and new information hypotheses), `9ca16ce` (frozen polarization protocol), and `de5fe8b` (reviewed extraction and AWS launcher). Focused tests and clean Codex reviews are retained with the experiments.

Resolution replication, instrument-factor ablations, full TRAIN instrument replication and future-growth target extraction are complete. The matched future-growth grid is complete and rejected. All four TRAIN-only Chile hardware pilots passed. The full deterministic TEAM-style baseline started at 19:30 UTC with 25 station-pretraining and 100 event-training epochs. The censored amplitude-innovation pilot completed and failed the intended mechanism comparison; deterministic affine-prefix controls are complete and fail the high-magnitude objective; the five-arm proper-score experiment is complete and fails the tail objective, with independent CPU audits and all 30 checkpoints verified by GPU replay. The reviewed six-arm context-weighted pilot is complete and rejected: high-magnitude error worsens in both seeds at all deadlines. The original worker completed the TRAIN-only polarization extraction and all 18 fixed CPU fits; the gate fails, so no geometry-density expansion is launched. The Chile baseline resumed at 21:28:57 UTC from a preserved completed-epoch 2 checkpoint; its flat-cache migration passed a bounded exact CUDA comparison, and completed the repeated epoch 3 in 16.3 minutes. The complete preserved history contains all 25 station-pretraining and 100 event-training epochs; the run exited successfully and selected epoch 97 by TRAIN-calibration NLL. DEV reporting followed selection. Chile TEST waveforms have not been loaded. The corrected TRAIN-fit-only likelihood-floor diagnostic completed in 199.73 seconds and failed its frozen gate with zero qualifying tail events; the proposed Huber continuation is not launched. The first incomplete STARTED-only attempt is preserved. The dedicated worker was verified stopped on 10 October after completed results were preserved, ahead of its automatic stop deadline at 07:28:52 UTC on 11 October; the authorized experiment ceiling remains $2,000 in AWS credits.

Historical reports remain available for transparency:

- [Initial literature review](earthquake_literature_review.md), [initial experiments](earthquake_experiment_results.md), and [experiment log](earthquake_experiment_log.md).
- [Phase-two results](earthquake_phase2_results.md) and [sequential-method research](earthquake_sequential_method_research.md).
- [Initial reproducibility archive](earthquake_research_reproducibility.zip): **historical snapshot only**; later source, reviews and results are in the Git repository.

Comparisons with published papers require matched data, time origin, event split, available stations and magnitude definition. Smaller error on INSTANCE cannot be directly compared with TEAM's multi-station Chile error.

Credits were refreshed at about 12:04 UTC on 10 October: main eligible-credit estimated remainder $4,075.53, expiration 31 October. The balance is shared and delayed, not a task allocation; the conservative task-owned worker resource allowance remains $60. The Chile stop and read-only mount were reverified.

A thread continuation check runs every 30 minutes, staying quiet unless there is a meaningful change. Paid work remains subject to verified credit coverage, the $2,000 ceiling and resource stop timers.

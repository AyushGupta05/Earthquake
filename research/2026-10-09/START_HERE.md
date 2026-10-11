# Earthquake research — live checkpoint, 11 October 2026 (London)

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
- [Matched early-clock control](earthquake_chile_clock_control.md): four-fit grid running after 28 AWS tests, exact CUDA replay and exact first 16 TRAIN predictions.
- [GeoNet tail census](earthquake_geonet_tail_census.md): completed independent metadata audit, 149 Mw≥5.5/60 Mw≥6/15 Mw≥7; separately verified waveform sample now complete.
- [GeoNet waveform feasibility](earthquake_geonet_waveform_feasibility.md): complete independent replay: 15/18 strict three-component prefixes at1/3/5; six larger-event stress cases, no model result.
- [GeoNet lower-magnitude metadata](earthquake_geonet_bulk_metadata.md): frozen 346-event lower-M sample plus 149 cached tail events; reviewed source pushed as 6c11dc5; bounded collection completed at 00:51 UTC: 346 requests and 70.2MB; frozen gate independently passes for all346new events, with all495outcomes retained.
- [Prospective GeoNet method shortlist](earthquake_geonet_method_shortlist.md): spectral-encoder and inferred-location mixture controls; no fitted result or novelty claim.
- [Geometry-distribution mechanism preflight](earthquake_geonet_location_mechanism_preflight.md): chosen synthetic tail gate fails; all negative panels retained, no geometry fit.
- [Full CMT sequence planning check](earthquake_geonet_cmt_sequence_preflight.md): primary support ceilings and stricter sensitivity percolation; no new data query.
- [Next GeoNet data plan](earthquake_geonet_next_data_plan.md): proposed direct 96-event waveform screen and larger fixed-cohort benchmark; no acquisition or fit launched.
- [Continuous prior audit](earthquake_continuous_prior_audit.md): exact noisy-label/repeat-law constraints; no new correction fit.
- [Rupture survival audit](earthquake_rupture_survival_audit.md): primary full texts and stop/grow identifiability controls; no additional fit.
- [Causal response-state audit](earthquake_causal_response_state_audit.md): same-input likelihood identities and uncertain pre-P state; no learned fit earned.
- [Response-posterior consistency](earthquake_response_posterior_consistency_audit.md): close SymVAE/distillation overlap; unequal noisy sensor posteriors are valid; zero fits.
- [Physical clipping audit](earthquake_physical_clipping_audit.md): established censored-likelihood/sensor-switching prior art; hardware rails and health unverified; zero fits.
- [Active-station silence audit](earthquake_active_station_silence_audit.md): strong prior art and unverified operational state; no new fit.
- [Rapid strain source audit](earthquake_strain_source_audit.md): missing middle source stage cancels the suspected mean leak for complete traces; negative hypothesis retained.
- [Completed Chile baseline](earthquake_chile_baseline_results.md): preserved selected checkpoint and DEV metrics; large-event validation remains insufficient.
- [Sequential distribution claim audit](earthquake_sequential_probability_claim_audit.md): incremental evidence, entropy and June-2026 forecast-calibration prior art.
- [Completed Chile floor diagnostic](earthquake_chile_floor_diagnostic.md): verified negative mechanism result; baseline complete and preserved, dedicated worker verified stopped.
- [Chile density-objective claim audit](earthquake_chile_density_claim_audit.md): exact likelihood-floor and normalized-Huber prior art; completed TRAIN-fit-only diagnostic fails its incidence gate; no Huber continuation.
- [Current Chile protocol](earthquake_chile_execution_protocol.md): verified data, true split counts, timing, models and recovery.
- [Alaska header audit](earthquake_alaska_header_audit.md): all 296,990 channels join metadata after fixing location-code normalization; timing/coverage limits remain explicit.
- [Alaska cohort audit](earthquake_alaska_cohort_audit.md): 781 archive names resolve to 780 current events; published 530-event membership remains unresolved.
- [October conformal-PGA paper audit](earthquake_conformal_pga_audit.md): useful uncertainty controls, with an important April-code/October-paper mismatch.
- [Additional external validation resources](earthquake_external_validation_expansion.md): recorded Alaska events and controlled Cascadia simulations.
- [External benchmark plan](earthquake_external_benchmark_plan.md): the Chile TEAM-LM data and evaluation protocol; implementation and worker setup have since advanced.
- [AWS execution note](aws_execution_note.md): verified quota, credits, new worker, automatic stop and cleanup obligations.

Reviewed implementations are committed and pushed to `AyushGupta05/Earthquake` on `main`. The new distribution pilots and independent export audit were frozen before fitting in `95db8b5`; independently audited negative grid results and the completed Chile baseline/floor diagnosis are retained in `136eb47`. Recent commits include `75caeb7` (full-data results and audits), `01023ca` (deterministic controls and completed negative results), `d655c3a` (censored/uncensored sequential updates), `8504094` (reviewed sequential-export I/O fix), `f3f18e4` (proper-score controls/full Chile launch), `b5f8ad1` (method and external-data audits), `d91a1c3` (censored negative result), `823366d` (verified cache exporter), `1d7510d` (residual support audit and cache launch), `ba6a852`/`98c9d13` (cache integration and proof), `373be20` (completed affine audit), `6c31e29` (reviewed context pilot), `e27b860` (negative shared-cap audit), `76443bc` (proper-score full audits and GPU replay), `63f4376` (corrected feature inventory and new information hypotheses), `9ca16ce` (frozen polarization protocol), and `de5fe8b` (reviewed extraction and AWS launcher). Focused tests and clean Codex reviews are retained with the experiments.

Resolution replication, instrument-factor ablations, full TRAIN instrument replication and future-growth target extraction are complete. The matched future-growth grid is complete and rejected. All four TRAIN-only Chile hardware pilots passed. The full deterministic TEAM-style baseline started at 19:30 UTC with 25 station-pretraining and 100 event-training epochs. The censored amplitude-innovation pilot completed and failed the intended mechanism comparison; deterministic affine-prefix controls are complete and fail the high-magnitude objective; the five-arm proper-score experiment is complete and fails the tail objective, with independent CPU audits and all 30 checkpoints verified by GPU replay. The reviewed six-arm context-weighted pilot is complete and rejected: high-magnitude error worsens in both seeds at all deadlines. The original worker completed the TRAIN-only polarization extraction and all 18 fixed CPU fits; the gate fails, so no geometry-density expansion is launched. The Chile baseline resumed at 21:28:57 UTC from a preserved completed-epoch 2 checkpoint; its flat-cache migration passed a bounded exact CUDA comparison, and completed the repeated epoch 3 in 16.3 minutes. The complete preserved history contains all 25 station-pretraining and 100 event-training epochs; the run exited successfully and selected epoch 97 by TRAIN-calibration NLL. DEV reporting followed selection. Chile TEST waveforms have not been loaded. The corrected TRAIN-fit-only likelihood-floor diagnostic completed in 199.73 seconds and failed its frozen gate with zero qualifying tail events; the proposed Huber continuation is not launched. The first incomplete STARTED-only attempt is preserved. The dedicated worker was verified stopped on 10 October after completed results were preserved, ahead of its automatic stop deadline at 07:28:52 UTC on 11 October; the authorized experiment ceiling remains $2,000 in AWS credits.

Historical reports remain available for transparency:

- [Initial literature review](earthquake_literature_review.md), [initial experiments](earthquake_experiment_results.md), and [experiment log](earthquake_experiment_log.md).
- [Phase-two results](earthquake_phase2_results.md) and [sequential-method research](earthquake_sequential_method_research.md).
- [Initial reproducibility archive](earthquake_research_reproducibility.zip): **historical snapshot only**; later source, reviews and results are in the Git repository.

Comparisons with published papers require matched data, time origin, event split, available stations and magnitude definition. Smaller error on INSTANCE cannot be directly compared with TEAM's multi-station Chile error.

Credits were refreshed again on the evening of 10 October: main eligible-credit estimated remainder $4,037.24, expiration 31 October. The balance is shared and delayed, not a task allocation; the conservative task-owned worker resource allowance remains $60. The owned Chile worker was restarted after this check. Its correct persistent data source is bound read-only, and its new automatic STOP was verified for 11 October 10:50:21 UTC (11:50 London). The conservative $248 task-resource envelope remains below the $2,000 eligible-credit ceiling.

A thread continuation check runs every 30 minutes, staying quiet unless there is a meaningful change. Paid work remains subject to verified credit coverage, the $2,000 ceiling and resource stop timers.

Current work: the source-pinned matched Chile clock grid launched at 23:00:57 UTC on 10 October, after all 28 worker tests, invented CUDA update/RNG equality and exact first16 TRAIN parameter replay. The prefit source/protocol milestone is pushed as 408cbd2; runtime proofs and the completed census are pushed as cf0641f. Causal response-state and active-station evidence gates are pushed as 53962ad. Four fixed fits must complete before calibration/DEV evaluation; TEST remains sealed. The GeoNet recovery completed and independent replay verified 158 artifact hashes and 149 event outcomes. The small waveform/response audit is complete after pre-acquisition freeze0c37764,38 fixtures and clean review. Independent replay confirms 15/18 strict three-component prefixes at 1/3/5 seconds; 9/11/13 targets also have their observed station P before the respective deadline. All 54 denominator slots are retained. Larger acquisition requires its own frozen plan; none has started. The next metadata-only feasibility design samples lower Mw bands before any larger waveform acquisition or new fit; its implementation is now reviewed, with 64 passing synthetic tests and a compatible independently replayed private plan; the reviewed source was pushed as 6c11dc5 and the one bounded collection launched at 00:39 UTC. Independent raw replay now passes the frozen metadata gate; all 495 outcome denominators are retained. These are known-method/data-feasibility controls, not claimed novel results. Preserve the earlier source-header failure and all negative experiment results.

Latest execution checkpoint: at 01:02 UTC three of four clock fits are complete, and the final discrete 1/3/5-second fit has started. Read-only data and automatic worker stop remain verified. No new calibration/DEV evaluation runs until all four fits complete; TEST remains sealed. The first two fits are locally preserved against their completion hashes; third fit is also preserved against all completion hashes.

Completed metadata acquisition: exit0 at 00:51:37 UTC; 346 requests, 70,172,690 body bytes, 744.36 seconds. Parent verified all 350 final-manifest members. Independent raw replay now matches all495base/origin/status outcomes and 3,356 aggregate values, and passes the frozen new-only metadata gate. Preserve 76 incomplete positive-P subsets and two descriptive clock anomalies; no exclusions or re-clocking. A separate fixed96-event native-count engineering screen is undergoing source review before its own Git freeze, private receipt and bounded acquisition. No successor waveform acquisition or new fit has started.

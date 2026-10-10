# Chile multistation mechanism: source-level gate and next decision

10 October 2026. Read-only design audit. This pass inspected local source and documentation only: no waveform arrays, metadata tables, checkpoints, predictions, DEV/TEST outcomes or cloud resources. Training status is parent-reported: the 25+100-epoch baseline completed and selected epoch 97; the separately frozen likelihood-floor diagnostic is pending. This document does not alter that diagnostic or authorize a fit.

**Decision: do not launch the proposed correlated-station likelihood preflight now. No missing multistation observable has been established in the current TEAM input.** A small covariance-density experiment could answer a legitimate surrogate question, but it would not demonstrate that TEAM ignores dependence, distinguish a new geometry mechanism, or establish an improvement in rare-event magnitude. Prioritize the existing objective diagnostic and exact benchmark feasibility. A geometry architecture remains a conditional hypothesis, not an earned next training run.

This is an explicit qualification of option 3 in `labels_limits_and_next_gates.md`, whose original bytes are preserved. Its phrase “missing information/inductive bias” was too loose: only a potentially useful **inductive bias** was identified. The source audit does not establish missing information.

## What the current model already receives

The inspected implementation is `work/repo/research/2026-10-09/phase3/team_lm.py`, adapted from author commit `8df20877f3a6ef47d3af4d1484ecdb0cdf37e903`. See the [primary model source](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/models.py) and [TEAM-LM paper](https://doi.org/10.1093/gji/ggab139).

| Proposed information | Source-verified status and implication |
|---|---|
| Interstation arrival differences and coherent waveform evolution | Every station has the same network-relative sample clock. Time-major flattening follows convolutions; absolute within-window timing is not deliberately discarded by a whole-trace invariant pooling operation. Cross-station processing follows station compression. Pairwise delays may be represented imperfectly, but their absence has not been demonstrated. |
| Amplitude and normalized waveform shape | Each station supplies normalized 3C waveforms and `log(peak+1e-8)/100` to the station MLP. Adding another peak-amplitude feature is not new evidence. Layer normalization after the MLP can alter its encoding but does not prove amplitude is lost. |
| Station geometry | Latitude/longitude/depth sinusoidal embeddings are added to station representations. No catalog source coordinates or distances enter inference. Station geometry is present; the source hypothesis that explains it is implicit. |
| Dependence across stations | Six full self-attention blocks jointly process all station tokens and an event token. This is not a product of independent station posteriors or likelihoods. It has no diagonal-station-covariance assumption to repair. |
| High-magnitude support | Five continuous Gaussian components have unbounded upper support. ReLU component means do not create a categorical magnitude ceiling. Broader support is not the missing mechanism. |
| An explicit shared hypocentre posterior | Absent from the magnitude-only port. The author's joint configuration has separate magnitude/location mixture heads on a shared embedding. This is a missing *output parameterization*, not proof of absent geometry evidence. |
| Full instrument transfer functions | The release describes sensitivity-corrected velocity, without full response removal. These response functions are not supplied to the current model. This is a real potential nuisance omission, but no newly verified Chile response metadata or positive matched response evidence justifies transferring the failed INSTANCE mechanism to Chile now. |

The [official release description](https://doi.org/10.5880/GFZ.2.4.2021.002) establishes the synchronous 100 Hz ZNE velocity convention, five seconds before the first network P arrival. Inference uses 600/800/1,000 samples at 1/3/5 seconds. Later samples are masked before mean and amplitude calculations. Individual-station P picks are unavailable; pre-arrival noise remains a valid continuous observation. The retrospective network-first-P alignment is part of the benchmark, not a demonstrated operational trigger/association system. Strict prefix masking also does not certify the earlier release preprocessing as causal.

## Why a seemingly positive cheap diagnostic could mislead

Let the available prefix and station coordinates be X, the completed event representation E=e(X), and a proposed inferred location distribution Q=g(E). As deterministic model outputs, Q adds no information conditional on E: I(M;Q|E)=0. A decoder using Q can still supply a useful constrained function class, optimization path or training regularizer. It cannot be described as acquiring independent location evidence. If the new branch reads raw X separately, it can recover information discarded by e; that must be demonstrated rather than inferred from a failed linear probe.

Likewise, an optimized low-rank Gaussian for station amplitudes may beat an optimized diagonal Gaussian because physical station residuals are correlated. That establishes a property of the chosen observation-density family. It does not establish that the discriminative transformer lacks that dependence, and a likelihood improvement need not improve the posterior mean or median. The earlier synthetic covariance and polarization pilots already make this distinction consequential here.

Catalog source location could help train a representation, but it is not admissible inference evidence. Known M can condition a TRAIN observation-density diagnostic; it must never be smuggled into feature construction or null covariance and then treated as a deployed predictor. An obsolete single-station pretraining head is not a calibrated station likelihood: event training subsequently changes its encoder.

## What an exact optimized null would require

For a *future* explicit geometry integration experiment, the question should be: does integrating a single uncertain source location improve a fixed magnitude estimator beyond extra location supervision, decoder flexibility and a point-location approximation?

The minimum meaningful family is:

1. **Direct null:** the same trainable encoder and event attention, an optimized direct continuous magnitude density, and the same auxiliary location task/labels as the candidate. A magnitude-only TEAM comparison alone confounds extra supervision.
2. **Point-location null:** the same location predictor, station features, shared distance-conditioned magnitude decoder and training budget, but an explicitly defined deterministic inferred location. Train this arm to its own objective; collapsing the candidate's location distribution after fitting is only an intervention control, not an optimized competitor.
3. **Integrated candidate:** one inferred location hypothesis determines the entire station-distance vector; average normalized conditional magnitude densities with positive weights. Reuse waveform context through a conditional factorization, not by multiplying two independently interpreted posteriors from the same prefix.
4. **Density-flexibility control:** match the effective magnitude output family. Fifteen location hypotheses times five Gaussian components can yield up to 75 magnitude components; beating a five-component head would not isolate geometry. Match the effective mixture budget or constrain the candidate to an explicitly equivalent output family. Parameter count alone does not match density expressiveness.

All arms need the same selected score convention, cutoff/augmentation draws, source sampling, smoothing, station masks, optimization budget and event populations. The existing max-pool model has far fewer parameters and is not this null. Adding a magnitude–location covariance to a joint Gaussian mixture is also insufficient: those cross-covariances integrate out of the magnitude marginal. Generic joint uncertainty is already present in [Virtual Seismologist](https://doi.org/10.1007/978-3-540-72241-0_7); station/model-space geometry processing has [graph-network precedent](https://arxiv.org/abs/2203.05144v1). Correlated station residuals were considered in the [Chile magnitude-label study, Appendix E](https://doi.org/10.1093/gji/ggz416). A specific useful EEW implementation is possible, but these ingredients are established.

No implementation meeting these controls has been reduced to a justified 1,800-second CPU experiment. Calling a much smaller descriptor regression its “optimized TEAM null” would be incorrect. Accordingly this audit recommends **zero new fits**, rather than specifying an arbitrary cheap surrogate that cannot answer the mechanism question.

## Counts, validation constraints and a bounded decision procedure

Only already documented counts are used:

- Original TRAIN: 57,679 events, including 22 MA≥5.5, 12 MA≥6 and one MA≥7/MA≥8 event.
- Existing fitting partition: 51,912 events, 776,742 station records, 20 MA≥5.5 events.
- Existing calibration: 5,767 events, 86,353 station records, two MA≥5.5 events. It already selected/scheduled the baseline, so it is not untouched discovery validation.

A balanced five-fold partition of the fitting events would have two folds of 10,383 events and three of 10,382; training complements would be 41,529 or 41,530. These are arithmetic planning counts, **not a newly inspected split**. The 20 tail events could be allocated four per fold only by a newly declared magnitude-stratified rule; a label-blind event hash does not guarantee that allocation. No station-group or spatial-fold counts have been inspected, so none are asserted.

Crucially, the completed station encoder and transformer have already used all those fitting-event labels. Splitting their frozen embeddings into new folds does not produce independently held-out evidence for the complete predictor. It is permissible as an explicitly conditional representation/readout probe, but it cannot validate a new end-to-end geometry method. Honest new encoder folds would require excluding held events from both station pretraining and event training. That is not a cheap head-only diagnostic.

The bounded decision procedure therefore stops at its first prerequisite:

- **Gate 0, source audit (completed):** identify a causal observable absent from the input, or a specific falsifiable representation failure rather than a general limitation of finite compression. **Not established.** An explicit latent variable being absent from the outputs does not pass.
- **Gate 1, only after Gate 0:** preregister the observable, eligible events, training-only folds, station groups, exact optimized null and extraction validity rules before reading targets/outcomes. Budget all extraction and fits, not just optimizer time, within 1,800 seconds CPU and two threads. If the necessary controls do not fit, reject feasibility before starting.
- **Gate 2, only after a valid diagnostic:** improvements must transfer to magnitude proper scores and mean/median decisions. Observation NLL or location MAE alone cannot earn the required high-M/bulk claim. Twenty fitting tail events and two existing calibration tails cannot support a confident all-deadline external superiority claim; no number of station records changes the event count.

Future-suffix perturbation, station permutation and padding invariance are essential correctness tests. Artificially shuffling station coordinates or time-shifting traces creates distribution shift; a resulting performance drop proves neither a missing observable nor a benefit from a new architecture. Such interventions are not replacements for an optimized null.

## Earned next work: make the benchmark claim executable

Keep the frozen floor diagnostic independent of this decision. A positive result earns its specified floored/proper-Gaussian controls, not geometry training. A negative result closes that rationale without forcing another latent head.

Before a new architectural investment, produce a source-only comparison contract for the paper figure/table actually being targeted: author magnitude-only versus joint configuration, single model versus ensemble, chronological split, internal calibration deviation, cutoff/decision convention, selected checkpoint and all preprocessing differences. No public author weights were found in the previously inspected repository/software archive; that documented absence is not a claim that weights cannot exist elsewhere. The current port has not established TensorFlow numerical equivalence. Report it as a controlled TEAM-style baseline until the relevant reproduction is verified.

For the final frozen comparison, retain identical events and 1/3/5-second network clocks, original MA labels, mean and median decisions, event-level high-M counts, CRPS/NLL and worst-error diagnostics. TEST stays sealed while methods/analysis are being chosen. Do not use a rare TEST event to design a new head. External Alaska resources have unresolved published-cohort identity and timing/response requirements in existing audits; they are not an immediately matched substitute.

The defensible present conclusion is narrow: **the source does not earn a new multistation dependence mechanism, and the cheap proposed covariance gate would not resolve that deficit.** This does not prove geometry conditioning cannot help. It identifies the evidence and controls that must precede that claim and avoids treating another surrogate win as the user's requested magnitude improvement.

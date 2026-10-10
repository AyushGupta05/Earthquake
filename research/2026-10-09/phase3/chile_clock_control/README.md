# Matched Chile clock continuation — source-only implementation

This is a known-method baseline control, not a proposed novel loss, a from-scratch paper replication, or evidence of improvement. No production waveform/checkpoint arrays have been opened or fitted during implementation. The parent must run the reviewed synthetic runtime proof and initial-state replay before fitting.

`protocol.json` is the prospective specification. It builds on `work/chile_training_clock_audit/AUDIT.md` and the primary [TEAM source at 8df20877](https://github.com/yetinam/TEAM/tree/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903), [TEAM-LM paper](https://arxiv.org/abs/2101.02010), and [software DOI](https://doi.org/10.5880/GFZ.2.4.2021.003). The existing port is a documented PyTorch adaptation, with no verified numerical TensorFlow equivalence. Original author code is not copied into this control. `baseline_guards.py` is copied unchanged from this project's previously reviewed `work/chile_floor_diagnostic/guards.py`; its unused floor-selection helpers are not used by the training grid.

## Fixed comparison

Both arms start from the exact same TRAIN-calibration-selected epoch97 model, with fresh empty Adam moments. They use seeds20261011 and20261012, batch64, six event epochs, constant9e-6 LR, source magnitude resampling, MA>4 Gaussian label noise, author-style station blinding, five-Gaussian density-floor loss epsilon1e-6, and all original event parameters. The unused single-station head is excluded as in the source event trainer. There is no additional pretraining, scheduler, checkpoint selection, or architecture change.

* `source_uniform`: retain integer n uniform100…2999, including pre-P crops. This preserves the current port's per-event marginal law; the author's original code drew one cutoff per batch.
* `discrete_1_3_5`: choose1/3/5 seconds independently and uniformly per event, retaining600/800/1000 samples including the five-second lead-in. Only the cutoff generator differs.

The original saved TRAIN-fit/calibration split is mandatory; continuation seeds never repartition events. No source event label is relabeled as noise. Event identities/order, station permutations, base blinding/noise draws and CPU/CUDA model RNG are hashed per epoch and matched across arms. Final masks can differ when different clocks change observed station availability. All draw occurrences and the incomplete final batch are retained. Initial state hashes must be identical across all four fits; each arm/seed has a distinct INIT provenance identity and empty optimizer.

Clock draws use an independent generator. Base station-count uniforms, station-rank uniforms, label normals, loader permutation and model RNG are isolated. The unchanged source EventDataset performs station permutation deterministically from seed/epoch/event. The source architecture has zero dropout. This reproduces paired random inputs, not an assertion that floating-point updates across different clocks should match.

## Evaluation and limits

All four epoch6 final artifacts must pass the completion/hash barrier before any TRAIN-calibration or DEV target parsing or forward. Every seed and1/3/5 deadline is reported with mean and median decisions, MAE/MedAE, MA>=5.5 tail errors, bias, CVaR95, linear P95, maximum error, proper mixture NLL and analytic Gaussian-mixture CRPS. The floored training score is not a proper normalized density score; reported NLL uses epsilon0. The original initial model is contextual only; the causal contrast is discrete continuation minus equally trained uniform continuation.

The existing primary gate is unchanged: both seeds must reduce equal-deadline-average DEV mean-decision MAE, while per-deadline mean-decision MAE and MedAE worsen by at most0.002. Paired event-bootstrap intervals use2000 draws, fixed seed20261013, the same resampled events across arms/deadlines. A point pass remains inconclusive when either average bulk CI includes zero. Proper-NLL and all worst-error regressions remain explicit tradeoffs. No winning seed, deadline or point decision is selected.

Only two TRAIN-calibration and one DEV events have MA>=5.5. Their error differences and bootstrap intervals are descriptive; zero-tail bootstrap samples have undefined tail statistics and are counted/omitted only for those statistics. A bulk pass cannot establish the user's high-magnitude goal, worst-error improvement, novelty, paper superiority or independent external generalization. Existing DEV has already been examined by the project and is not a fresh test set. No TEST waveform group is present in the accepted cache; TEST remains sealed.

## Integrity, lifecycle and recovery

The dry default reads only the supplied source/plan/protocol JSON and source files. Execution first hashes all nine pinned input artifacts and validates baseline completion25+100, selected97, metadata/cache/split identity and runtime precision. The full HDF has TRAIN+DEV only; fit training loads only original-fit groups. Cache hashing and HDF group/header validation are integrity operations, not a claim that no held-out container bytes are ever scanned. Held-out target values and waveform arrays are not used for optimization.

The new supervisor keeps its single worker in the parent's process group/cgroup, kills/reaps it on cancellation or hard timeout, and removes a false completion marker. Parent must also supply an external timeout, `KillMode=control-group`, a systemd runtime margin beyond timeout+kill grace, and an OS STOP deadline. Source/protocol bytes are rechecked at completion. Existing output paths are rejected. The original model, dataset and source files are never modified.

`latest.pth` is atomically replaced only after a complete epoch; it contains model, Adam state, independent RNGs, global CPU/CUDA/Python/NumPy RNG, identity and full history. It does **not** implement an exact-resume CLI. Do not silently restart a partial run or reset its optimizer. A later continuation would require a separately tested recovery contract. Only a complete epoch6 final checkpoint can be scored, and only after all four fits finish.

The parent-authorized budget amends the earlier source-only memo from6h to10h total fitting: at most9000s per fit,36000s total fitting,39600s grid wall time,43200s worker-stop window. There is no automatic extension; timeout means incomplete, not a negative scientific result. Original event loading uses the full HDF directly; flat station-pretraining cache rebuilding is unnecessary. No resource provisioning is in this code.

## Parent-only prefit checks

Run the local/worker synthetic suite with warnings as errors (28 cases; 27 local passes and one explicit h5py skip). It uses invented arrays and checks actual TEAM strict-prefix invariance, exact identical-clock CPU model/Adam updates over two epochs with64+1 remainder, independent RNGs, augmentation equations, split/barrier/hash rejection, Gaussian proper scores, fixed gate and initial-replay tolerance. Local h5py absence causes one explicit skip; the production Python environment must run that header fixture without skips. Test source-helper extraction by AST avoids installing HDF dependencies locally; the worker proof imports the complete pinned trainer normally.

The `--synthetic-runtime` mode uses only three invented events/two stations and a fresh randomly initialized TEAM model. With a120s hard bound it performs source/source/discrete CUDA updates and requires bitwise-identical model/optimizer/loss/trace for the repeated source clock, plus identical non-clock traces for the different clock. It opens no production artifacts. It is a bounded runtime check, not a batch64 performance or full-recovery proof.

The `--initial-replay DIRECTORY` mode has a600s maximum. It checks the exact completed floor-diagnostic receipt and arrays hashes, then loads only its first16 selected original TRAIN-fit events for unaugmented batch16 at1/3/5. It compares native float32 logits/means/scales to the stored float64 copies with fixed atol1e-6 and rtol1e-6; all values and identities must match. It performs no optimizer steps and no calibration/DEV/TEST forwards. This is a limited input-behavior check, not full-population replay or TensorFlow parity.

`HANDOFF.md` gives the exact parent commands after source review and promotion. Neither proof nor a fit is launched by this implementation task. Keep model/NPZ/full selection or split rows out of Git; promote code, protocol, tests, source hashes, compact receipts and review evidence only.

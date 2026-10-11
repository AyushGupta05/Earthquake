# Independent replay after the four-fit completion barrier

**Preparation only.** Parent reports the barrier has not passed. This task reads frozen source/protocol/handoff and local progress receipts only. It does not access new calibration/DEV targets, predictions, checkpoint tensors, forwards or remote files. GeoNet metadata replay takes priority when its completed-run handoff arrives.

The controlling [protocol](../chile_clock_control/protocol.json) has SHA256 `8d4e2e3ed43c072356d539bb822316ed8f8d2cee3213ff8a02ef419a6f33777b`; source-manifest SHA256 is `af88e1269ef1678c5434a0c5d483adebc24fac7374baded4579ea83fdc8df60f`. Twelve runtime source members match their frozen hashes. The latest inspected local progress snapshot is 2026-10-11T00:13:30Z: one FIT_COMPLETE receipt and zero evaluation filenames. This is a dated snapshot, not a fresh remote observation. Completion and result values remain unverified.

## 1. Completion, identity and saved final-six barrier

After the parent supplies a completed local artifact handoff, first verify normal worker/supervisor exit and final `COMPLETE.json`: schema `chile-clock-grid-complete-v1`, exact plan/source/protocol bindings, fits=4, selection=`fixed_final6`, TEST reads=0, and every listed artifact size/hash independently. Check `STARTED.json`, `grid_identity.json` and `TRAINING_COMPLETE.json` agree, including all four FIT_COMPLETE hashes and no substituted/missing identity. A partial run or missing final COMPLETE is incomplete, not a scientific negative. No resume/restart, fresh fit or forward is part of this saved-artifact replay.

| Required fit | Seed | Only scoring checkpoint |
|---|---:|---|
| source_uniform | 20261011 | completed epoch 6 |
| discrete_1_3_5 | 20261011 | completed epoch 6 |
| source_uniform | 20261012 | completed epoch 6 |
| discrete_1_3_5 | 20261012 | completed epoch 6 |

For each FIT_COMPLETE, independently verify its exact `model.pth`, `latest.pth`, `history.json`, `INIT.json` hash set and identity. Verify final-model schema `chile-clock-final-v1`, completed_epochs=6, and latest-snapshot schema `chile-clock-completed-epoch-v1`, completed_epoch=6, identical final model tensor state, identity and six-entry history. Hashes already obtained through a receipt are still independently matched to actual handed-off bytes. Do not deserialize unverified artifacts. If later authorized to inspect Torch payloads, use the exact recorded runtime's restricted `weights_only=True` loader; do not import production training modules.

All four identities must share the original nine artifact hashes, original TRAIN-fit identity, baseline initial-state digest, epochs=6, batch64, Adam 9e-6/betas(.9,.999)/eps1e-8/weight_decay0/amsgradFalse, clipping1 and pinned runtime. Only arm and continuation seed vary. INIT must have identical starting-model hashes, zero optimizer entries and within-seed equal initial model/generator RNG hashes. The progress receipt records baseline state digest `4acb798e74e7263b3a570c01008f66271440e9d951bb012448ddc359f567143e` and fit-ID digest `1b9ad34f6e7c976311a8edd07e24cd9ef075f579754306b4092bb6af312d7c14`; verify them against complete provenance rather than promote a progress claim alone.

Reconstruct tensor-state digests independently: sorted tensor names; name UTF-8 plus NUL; compact JSON [Torch dtype string, shape] plus NUL and contiguous CPU tensor bytes in native stored order, all streamed into SHA256. Compare final-six/latest model **state** digests, not their different checkpoint-file hashes. Within each seed compare persisted final count/rank/label generator states and global CPU/CUDA/Python/NumPy RNG states; clock-generator states are exempt. Do not require learned final weights to match across clocks.

## 2. Split, clock, draw budget and RNG integrity

Verify the pinned original split manifest, metadata/cache provenance and run configuration. Fit/calibration/DEV IDs and source rows must be unique, ordered, nonoverlapping, exhaustive within original TRAIN+DEV boundaries, and match each stored split/run digest/count. Identity hashes encode UTF-8 newline-joined IDs **without a trailing newline**. Continuation seeds do not repartition events. TEST remains sealed. Preserve 1/3/5 seconds from network-first P with the five-second lead-in and retained600/800/1000 samples.

Independently compare six histories and all six paired trace digests, each epoch and seed: `event_order`, `station_order`, `station_count_draw`, `station_rank_draw`, `label_draw`, `model_rng`. Also require equal examples, batches and batch-size lists, including the remainder. Verify LR is always9e-6, epochs1…6 and complete draw budget. Saved `clock` and `final_mask` digests may differ: changed clocks can change observed station availability. Equality of six recorded digests establishes recorded pairing; it is not a fresh replay of all underlying waveforms or RNG generation.

Clock histograms sum to the recorded examples per epoch. Uniform-arm nonzero bins must lie in100…2999; discrete bins only600/800/1000. Uniform cutoff is (n+.5)/100−5; discrete cutoff is n/100−5. Do not demand exact one-third empirical balance. Source resampling repeats TRAIN events with r=2**(k−1) on k<MA<=k+1, k=4…8, otherwise1; no evaluation resampling. Loader seed is seed+1000+zero-based epoch; station seed is the first8 SHA256 bytes of `seed/epoch/event`, little-endian. Separate clock/count/rank/label generators use first8 SHA256 bytes of `chile-clock-v1/seed/name`, little-endian modulo(2**63−1). No resimulation of training or new fit is earned by a digest mismatch.

## 3. Saved parameters and point/probability replay

After the barrier, check ten prediction archives: four final-six fits plus starting_epoch97, each on calibration and DEV. Use safe array decoding with pickle disabled and exactly26 keys: event_ids/targets, then logits/weights/means/scales/mean/median/nll/crps for each1/3/5 seconds. Require unique ordered IDs, finite targets, N×5 component arrays and length-N action/score arrays. Within each split all five archives must match original IDs/targets exactly. Initial97 is contextual; the causal comparison is discrete-final6 minus equally trained uniform-final6 for the same seed. Baseline was calibration-selected and DEV has previously been examined, so neither is a fresh independent test.

The saved mixture arrays are float64 copies of native float32 model outputs. Require positive scales and nonnegative stored weights with sums within the existing1e-6 mass guard. Independently compare stored weights to softmax(logits) within1e-6 absolute tolerance; do not silently replace or renormalize stored weights. Replay using independent math formulas, not clock_metrics/evaluate/mixture helper imports. This verifies calculations from saved parameters, not a new checkpoint-to-waveform forward.

Mean action is sum(w_j*mu_j). Median uses the stored-weight CDF sum(w_j*Phi((x−mu_j)/sigma_j)): initialize min(mu−12sigma), max(mu+12sigma), perform48 bisections at probability.5 with the source `<.5` lower/`>=.5` upper rule, then midpoint. Preserve continuous magnitude values with no bins, threshold boost, floor or clipping.

For proper NLL, use normalized **log-softmax of saved logits**, Gaussian log densities and stable log-sum-exp. There is no1e-6 density floor in evaluation: the floored training loss cannot substitute. For analytic CRPS define A(d,s)=s*sqrt(2/pi)*exp(−d²/(2s²))+d*erf(d/(s*sqrt(2))). Then CRPS=sum_j w_j*A(y−mu_j,sigma_j)−0.5*sum_jk w_j*w_k*A(mu_j−mu_k,sqrt(sigma_j²+sigma_k²)). Replay each event's mean/median/NLL/CRPS before aggregates. Declare1e-9 absolute plus1e-9 relative calculation tolerances prospectively; a failure is reported/investigated without widening. Native weight rounding and logit-normalized NLL are explicitly distinct source conventions.

## 4. Error metrics and paired event bootstrap

For each split/arm/seed/deadline/action, signed error is prediction−target and absolute error a. Recompute MAE=sum(a)/N, MedAE=ordinary median(a), bias=mean(signed), max=max(a), CVaR95=mean of the largest max(1,ceil(.05N)) errors, and linear-interpolated P95 at h=(N−1)*.95 between sorted errors. Tail mask is literal MA>=5.5; compute tail MAE/MedAE and retain each tail error privately. Zero-tail statistics are undefined, not zero. Proper NLL/CRPS aggregates are unweighted event means. Equal-deadline primary MAE is the ordinary average of the three mean-action MAEs, not a pooled station/trace error.

Recompute discrete-minus-uniform statistics for each seed separately. For each split/seed comparison, independently reset the exact parent bootstrap RNG backend to20261013; use2000 length-N integer-index resamples with replacement. Match the NumPy version/backend from the completed-runtime handoff or verify a privately supplied bootstrap-index checksum; do not substitute Python random or assume a different backend is equivalent. The same indices must serve both arms, both actions and all deadlines in each draw. Recompute each nonlinear statistic on each sampled arm and then subtract; do not take a median/CVaR/max of per-event error differences. Do not pool fitted seeds as independent events.

Use linear2.5%/97.5% percentile bounds of paired deltas and retain requested/valid draw counts for every statistic. Draws without tail cases are omitted only for undefined tail statistics. All other draws remain. Source-independent replay may use verified array/RNG primitives, but not the production score, bootstrap or gate functions.

## 5. Exact decision and claim limits

DEV point criteria pass only if **both seeds** have equal-deadline mean-action MAE delta<0 and, at each1/3/5 deadline, mean-action MAE and MedAE deltas<=.002. If any point condition fails, status=`failed`. If points pass and both paired bulk CI upper bounds are strictly<0, status=`pass`; otherwise `inconclusive`. Calibration is supporting, with no tuning or gate substitution. Median-action results remain visible, but are not substituted into the primary mean-action gate.

Report all NLL deltas and flag any positive value as a probability-quality tradeoff. Report every CVaR95/P95/max regression even when the bulk gate passes. The existing formal gate does not guarantee preservation of all worst-error or probability metrics. Only2 calibration/1 DEV MA>=5.5 events are expected; verify counts after completion, retain descriptive cases/intervals and make no large-event generalization claim. A six-epoch allocation-control failure rejects this fixed adaptation only, not full clock-specific retraining. No novelty, TensorFlow parity, convergence, external generalization or matched published-benchmark superiority is earned by this audit.

Publish aggregate-only mismatches, all seeds/actions/deadlines, intervals, criteria and exact artifact hashes. Keep IDs, rows, arrays, checkpoints and full tail cases private. Any subsequent code implementation is a separate reviewed task; none is created here.

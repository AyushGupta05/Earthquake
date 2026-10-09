# Affine-prefix controls: completed two-seed result

9 October 2026, 20:42 UTC. **This preprocessing control fails the requested high-magnitude objective.** It improves several ordinary-error measures, especially at 3/5 seconds, but affine projection worsens the sole M≥5 validation event in both seeds at every horizon. The guard variant is also mixed and does not rescue that result. This is ordinary least-squares preprocessing, not a proposed novel distribution method.

Each run uses all 979,487 TRAIN records, ten fixed epochs, batch size 512, the same independent-prefix backbone and weighted Huber + .075 CE objective. Controls within each seed have identical initial weights and all ten realized training permutations; source, labels, inclusion weights, row identities and runtime are matched. Validation is the reused 96,993-record/3,711-event cohort, with 13 M≥4 and one M5.1 event. No TEST inference occurred.

`raw` uses the existing released count windows. `affine` removes each currently observed prefix's least-squares constant and linear trend before waveform and amplitude branches. `affine_guard1` discards the final sample first, then projects and appends one zero to retain input length. Neither operation establishes full raw-stream causality of prior filtering, resampling or quantization. See the [preprocessing audit](earthquake_causal_preprocessing.md).

## Two-seed mixture-mean decisions

Averaging seed distribution means gives the exact mean of their equally weighted mixture. MedAE below is the median absolute error of that mean decision. We do not average seed medians or claim to have recovered a mixture median.

| Control | Seconds | MAE | MedAE | M≥4 record MAE | M≥4 event-macro MAE | CVaR95 | M≥5 MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 1 | 0.387201 | 0.292565 | 0.835844 | 0.818890 | 1.370157 | 1.444375 |
| raw | 3 | 0.333915 | 0.251283 | 0.683726 | 0.653640 | 1.224689 | 0.940527 |
| raw | 5 | 0.311407 | 0.229860 | 0.624800 | 0.589579 | 1.176704 | 0.729348 |
| affine | 1 | 0.385940 | 0.291940 | 0.833258 | 0.821024 | 1.367929 | 1.531570 |
| affine | 3 | 0.330308 | 0.248928 | 0.671867 | 0.651856 | 1.204935 | 0.980235 |
| affine | 5 | 0.306573 | 0.228267 | 0.597567 | 0.570706 | 1.148730 | 0.753689 |
| affine_guard1 | 1 | 0.385434 | 0.290982 | 0.846599 | 0.831866 | 1.366419 | 1.552943 |
| affine_guard1 | 3 | 0.329313 | 0.247399 | 0.682135 | 0.660486 | 1.202918 | 1.006398 |
| affine_guard1 | 5 | 0.305711 | 0.226757 | 0.605708 | 0.578578 | 1.146489 | 0.749442 |

For `affine` versus `raw`, overall MAE changes by −.001261/−.003607/−.004833 at 1/3/5 seconds; M≥4 event-macro MAE changes by +.002134/−.001784/−.018873; the single M5.1 event worsens by +.087195/+.039708/+.024341. These observed differences do not establish population significance or general large-earthquake behavior. No additional hyperparameter tuning is justified by this control alone.

## Every seed

| Run | Seconds | MAE | M≥4 event-macro MAE | M≥5 MAE |
|---|---:|---:|---:|---:|
| affine_guard1_seed20261009 | 1 | 0.392422 | 0.819302 | 1.527356 |
| affine_guard1_seed20261009 | 3 | 0.335720 | 0.659056 | 0.992449 |
| affine_guard1_seed20261009 | 5 | 0.313654 | 0.569142 | 0.748553 |
| affine_guard1_seed20261010 | 1 | 0.390985 | 0.860847 | 1.578531 |
| affine_guard1_seed20261010 | 3 | 0.334601 | 0.680600 | 1.031675 |
| affine_guard1_seed20261010 | 5 | 0.309799 | 0.608871 | 0.792004 |
| affine_seed20261009 | 1 | 0.392779 | 0.826956 | 1.520760 |
| affine_seed20261009 | 3 | 0.338261 | 0.667394 | 0.975394 |
| affine_seed20261009 | 5 | 0.315546 | 0.573833 | 0.771055 |
| affine_seed20261010 | 1 | 0.391948 | 0.831810 | 1.543779 |
| affine_seed20261010 | 3 | 0.334590 | 0.655173 | 1.002856 |
| affine_seed20261010 | 5 | 0.309865 | 0.588041 | 0.764451 |
| raw_seed20261009 | 1 | 0.393939 | 0.827286 | 1.435968 |
| raw_seed20261009 | 3 | 0.340415 | 0.665015 | 0.972590 |
| raw_seed20261009 | 5 | 0.318521 | 0.601064 | 0.754748 |
| raw_seed20261010 | 1 | 0.393813 | 0.832489 | 1.468495 |
| raw_seed20261010 | 3 | 0.339585 | 0.662445 | 0.934527 |
| raw_seed20261010 | 5 | 0.316555 | 0.604867 | 0.745984 |

## Independent verification

The independent NumPy auditor ran on AWS and locally. Six focused tests pass in both environments; Codex autoreview is clean. All 42 transferred artifact hashes/lengths match. Recomputed point metrics agree with saved metrics within 1.5543122344752192e−15, and local/AWS audit JSONs are identical. It also verifies fixed epoch count, control/seed completeness, validation alignment and matching initialization/permutation hashes.

This audit does **not** replay the trained networks or independently recover unsaved full probability vectors, CRPS or a mixture median. Those quantities are not presented as verified results here. Small source/provenance/metric files are committed under `results/2026-10-09/phase2/affine_audit`; full checkpoints, row arrays and predictions remain under `/mnt/eew-research/runs/affine_prefix_*` on AWS and in the local audit workspace. This negative result does not invalidate affine invariance as an algebraic check; it rejects it as the sought tail-error improvement on this experiment.

# Independent proper-score grid audit: 1, 3 and 5 seconds

All three completed horizons pass independent CPU artifact, probability and metric audits. These established proper-score controls do **not** improve the priority high-magnitude error while preserving bulk behavior relative to the matched Huber/CE reference. No model, threshold, epoch or seed was selected. No TEST waveform/target records were accessed.

Each horizon trained all 979,487 TRAIN records for 15 fixed epochs, using the same 291-column head, normalizer, seed-specific initialization and realized minibatch order. Both prespecified seeds (20261009, 20261010) and their equal-PMF ensemble are retained. The audit independently replays CPU shuffle hashes, verifies all 30 serialized head hashes, TRAIN prior/row digests, event/trace disjointness, PMF mass and all 15 ensembles. All 96 mean/median comparison rows are in `all_comparisons.csv`; complete calibration bins, score definitions and checks are in `report_1s_v2.json`, `report_3s.json`, `report_5s.json`.

Validation contains 96,993 recordings from 3,711 events, including 1,027 M≥4 recordings from only 13 events and 91 M≥5 recordings from one event. It has been repeatedly reused. These are exploratory comparisons, not external-test performance or superiority to another paper.

The table reports equal two-seed ensembles with the mean decision. All individual seeds and median decisions remain in the CSV and reports.

| Seconds | Control | MAE | MedAE | Event MAE | M≥4 MAE | M≥4 event MAE | CVaR95 | CRPS | Brier(M≥4) |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | huber_ce | 0.365343 | 0.272028 | 0.412189 | 0.686116 | 0.659724 | 1.327444 | 0.261034 | 0.009537 |
| 1 | crps_ce | 0.361541 | 0.275845 | 0.413936 | 0.834918 | 0.802485 | 1.277012 | 0.257498 | 0.007650 |
| 1 | tail_crps_ce | 0.362445 | 0.276719 | 0.414593 | 0.838418 | 0.805105 | 1.278258 | 0.257997 | 0.007654 |
| 1 | marginal_crps_ce | 0.364106 | 0.277339 | 0.417653 | 0.832808 | 0.800227 | 1.289834 | 0.259462 | 0.007692 |
| 1 | ranked_bce_ce | 0.362449 | 0.278275 | 0.415076 | 0.835574 | 0.802781 | 1.273931 | 0.257869 | 0.007664 |
| 3 | huber_ce | 0.315881 | 0.232202 | 0.353124 | 0.551167 | 0.514938 | 1.195389 | 0.226866 | 0.008621 |
| 3 | crps_ce | 0.313513 | 0.235448 | 0.354878 | 0.670390 | 0.634918 | 1.151872 | 0.224032 | 0.007096 |
| 3 | tail_crps_ce | 0.315311 | 0.236593 | 0.358316 | 0.669447 | 0.633568 | 1.157585 | 0.225262 | 0.007175 |
| 3 | marginal_crps_ce | 0.315294 | 0.236424 | 0.357272 | 0.667486 | 0.631484 | 1.162033 | 0.225161 | 0.007126 |
| 3 | ranked_bce_ce | 0.313603 | 0.236534 | 0.354919 | 0.669739 | 0.634749 | 1.146760 | 0.223636 | 0.007130 |
| 5 | huber_ce | 0.286189 | 0.203790 | 0.317608 | 0.486910 | 0.444278 | 1.146738 | 0.206733 | 0.007886 |
| 5 | crps_ce | 0.284914 | 0.206453 | 0.320652 | 0.578975 | 0.535565 | 1.114600 | 0.204776 | 0.006672 |
| 5 | tail_crps_ce | 0.286134 | 0.207561 | 0.322117 | 0.587548 | 0.543585 | 1.115678 | 0.205688 | 0.006554 |
| 5 | marginal_crps_ce | 0.288063 | 0.208833 | 0.324700 | 0.579065 | 0.534900 | 1.121914 | 0.206775 | 0.006561 |
| 5 | ranked_bce_ce | 0.286699 | 0.208859 | 0.323282 | 0.568518 | 0.526615 | 1.109029 | 0.205445 | 0.006617 |

**Interpretation.** Plain CRPS/CE ensemble reduces aggregate MAE from 0.36534→0.36154,0.31588→0.31351 and0.28619→0.28491 at 1/3/5 s, but M≥4 MAE rises from 0.68612→0.83492,0.55117→0.67039 and0.48691→0.57898. Median absolute error and event-macro MAE also worsen. All four proper-score ensemble arms have larger M≥4 recording/event-macro error than Huber at every horizon; the same M≥4 recording-error direction holds within both seeds. Their record-CVaR95 and Brier score improve, illustrating a real objective tradeoff. Most CRPS values improve, but 5-second marginal weighting slightly worsens CRPS as well. No standard proper-score arm meets the stated tail-priority/constant-bulk goal here.

**Calibration definitions matter.** Nominal 90% center-endpoint intervals cover raw magnitudes only 84.48–87.26% across these ensembles, but cover the clipped categorical bin set 90.94–91.44%. A half-bin representation offset accounts for much of this bulk discrepancy. Event-weighted bin-set coverage is also reported separately. Rare M≥4 coverage remains weak under either definition: Huber bin-set coverage is 73.71/77.90/79.65% at 1/3/5 s; proper-score controls span 59.69–61.44%,63.68–65.04%,68.74–71.57%. Lower overall Brier/ECE therefore does not establish rare-event reliability.

**Scores are not interchangeable.** Training uses 0.1-spaced scores against `clip(floor(y/0.1+1e-5),0,65)`, with centers 0.05…6.55. The audit separately integrates exact CRPS of the discrete predictive distribution against original continuous y, including off-support observations. Fixed tail weighting is a grid-threshold score; it is not identically the shared evaluator’s tail-clamped continuous CRPS. The positive TRAIN-marginal vector is data-fitted, capped and frozen; its population propriety statement is conditional on a fixed weight vector. The original Huber objective is magnitude-emphasized and not proper. Equal CE/lr settings do not isolate objective scale from shape.

**Verification.** Nineteen focused CPU tests passed locally and on AWS, including analytical CRPS cases, off-support/quantization cases, event weighting, corruption, swapped alignment, wrong ensembles, changed checkpoints, nonfinite PMFs, and exact final batch sizes. Final Codex autoreview `review_v3.json` is clean. The latest CPU audits took 16.7/17.0/15.2s on one thread. Tiny float32 probability-sum drift is checked before normalization; reported score discrepancies are approximately 1e-11. Raw recomputed CNN PMFs were not saved by the runner, so their probability-score reconstruction is not claimed exact; raw point metrics are verified.

**Checkpoint inference correspondence.** CPU-only sample replay fails unchanged numerical tolerances (max frozen-CNN logit difference 0.03264; head PMF difference up to0.000294, mean up to0.002643). This does not invalidate saved-PMF arithmetic, but prevents a CPU inference-reproduction claim. The parent completed the separately reviewed same-runtime GPU replay on all 96,993 validation rows for all 30 heads, with original 256/2048 batch sizes. All horizons PASS: frozen-CNN logits match exactly (max difference 0), maximum saved-PMF discrepancy is 2.972e-08, and maximum mean discrepancy is 2.168e-07. See `gpu_replay_all.json`. This resolves saved-checkpoint correspondence in the production runtime; it does not establish CPU/GPU bitwise equivalence or isolate TF32 from other device/batch effects. That replay reuses source-pinned feature functions, so it is a correspondence check, not an independent feature implementation. GPU script SHA256=`902c220d696736d5e687d8919389861a7ae95be6eede0c64377635ac1f4e79bf`.

All changes are standalone audit/evidence files under `work/proper_score_audit`; producer code, live training configuration and original run artifacts were unchanged.

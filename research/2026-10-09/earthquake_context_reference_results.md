# Contextual frozen-reference score: independent pilot conclusion

Reject the current-context score as a high-magnitude improvement under this fixed pilot. It worsens M≥4 MAE versus the TRAIN-average threshold weights in both seeds at all three deadlines, and it fails against shuffled weights as well. The result does not justify a full-data replication or a sequential-reference extension on its own. This is a negative result for this prespecified construction and training budget, not a theorem that contextual proper scores cannot help.

## Fixed comparison

Each deadline uses the same 197,676 selected TRAIN rows/inverse inclusion weights, 291-column instrument student with native slots zero, 15 fixed epochs, seeds 20261009/20261010, identical initialization and shuffle order. Five event-excluding CE teachers use 51 prefix descriptors + 34 static fields. All six arms were retained; validation was not used for early stopping or arm selection. The reused validation contains 96,993 recordings, 3,711 events, 1,027 M≥4 recordings from 13 events, and 91 M≥5 recordings from just one event.

## Ensemble mean decision

| Seconds | Arm | Bulk MAE | MedAE | M≥4 MAE | M≥4 event MAE | M≥5 MAE | CVaR95 | CRPS | NLL |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | crps_ce | 0.376454 | 0.286928 | 0.882867 | 0.849307 | 1.406855 | 1.317366 | 0.268397 | 2.841608 |
| 1 | context_ce | 0.375864 | 0.286490 | 0.897011 | 0.863728 | 1.414318 | 1.313504 | 0.267957 | 2.837239 |
| 1 | shuffled_ce | 0.376443 | 0.287015 | 0.886262 | 0.852855 | 1.406293 | 1.315605 | 0.268393 | 2.841435 |
| 1 | average_ce | 0.375806 | 0.286699 | 0.879012 | 0.844667 | 1.394626 | 1.315026 | 0.267871 | 2.839254 |
| 1 | ranked_bce_ce | 0.376448 | 0.286684 | 0.886471 | 0.852634 | 1.398016 | 1.312698 | 0.268224 | 2.836224 |
| 1 | properized_ad_ce | 0.383895 | 0.295902 | 0.911443 | 0.879371 | 1.430582 | 1.314151 | 0.272955 | 2.854939 |
| 3 | crps_ce | 0.329364 | 0.248318 | 0.728102 | 0.691688 | 1.033129 | 1.199266 | 0.235449 | 2.708354 |
| 3 | context_ce | 0.329598 | 0.248538 | 0.732770 | 0.697637 | 1.047215 | 1.196735 | 0.235606 | 2.706808 |
| 3 | shuffled_ce | 0.330559 | 0.249385 | 0.722132 | 0.686330 | 1.011780 | 1.197311 | 0.236244 | 2.710708 |
| 3 | average_ce | 0.329214 | 0.248102 | 0.718260 | 0.682539 | 1.008651 | 1.197065 | 0.235365 | 2.707432 |
| 3 | ranked_bce_ce | 0.328722 | 0.248097 | 0.720235 | 0.684738 | 1.012511 | 1.188909 | 0.234890 | 2.703445 |
| 3 | properized_ad_ce | 0.340081 | 0.257940 | 0.707362 | 0.675486 | 0.927223 | 1.201411 | 0.242607 | 2.737867 |
| 5 | crps_ce | 0.299299 | 0.217390 | 0.624243 | 0.584180 | 0.742592 | 1.156751 | 0.215450 | 2.598497 |
| 5 | context_ce | 0.299401 | 0.217841 | 0.630170 | 0.590264 | 0.759678 | 1.149369 | 0.215338 | 2.596261 |
| 5 | shuffled_ce | 0.299886 | 0.218165 | 0.609789 | 0.570293 | 0.705628 | 1.155476 | 0.215724 | 2.598532 |
| 5 | average_ce | 0.299073 | 0.217283 | 0.608449 | 0.568798 | 0.704125 | 1.153549 | 0.215159 | 2.595418 |
| 5 | ranked_bce_ce | 0.299683 | 0.218915 | 0.610533 | 0.570206 | 0.702557 | 1.142908 | 0.215390 | 2.595571 |
| 5 | properized_ad_ce | 0.314635 | 0.232227 | 0.651524 | 0.611401 | 0.861996 | 1.170712 | 0.226214 | 2.657301 |

## Paired context effect

Positive deltas mean worse contextual performance. Both-seed M≥4 deltas below compare against the fixed weighted TRAIN-average vector.

| Seconds | Seed 20261009 ΔM≥4 MAE | Seed 20261010 ΔM≥4 MAE | Ensemble ΔM≥4 MAE | Tail events improved (mean / median) |
|---:|---:|---:|---:|---|
| 1 | +0.022891 | +0.013119 | +0.018000 | 0/13 / 0/13 |
| 3 | +0.014276 | +0.015290 | +0.014510 | 1/13 / 3/13 |
| 5 | +0.024857 | +0.018842 | +0.021721 | 1/13 / 1/13 |

All 13 individual tail events and every seed/mean/median comparison are preserved in each `tail_events.csv`; no event was excluded after seeing results. Event-macro errors also worsen, so the finding is not solely caused by prolific stations for one tail event. M≥5 is one event and provides no robust generalization estimate.

Context has slightly lower CVaR95 than average weights at all deadlines, but higher M≥4 error and higher ordinary CRPS at all three. NLL improves very slightly at 1 and 3 seconds but worsens at 5. There is no simultaneous tail/bulk win. Properized AD trades lower M≥4 error at 3 seconds for materially worse bulk MAE/MedAE/CRPS and is worse at 1 and 5 seconds. Ranked BCE is a useful known-score comparator, not evidence of new EEW methodology.

## Reference and optimization diagnostics

| Seconds | OOF teacher NLL | Threshold cap fraction before normalization | Context-minus-average weight RMS | Max weighted threshold mean shift under shuffle |
|---:|---:|---:|---:|---:|
| 1 | 2.862428 | 0.710024 | 0.252555 | 0.080691 |
| 3 | 2.784571 | 0.728854 | 0.255113 | 0.093672 |
| 5 | 2.706323 | 0.743525 | 0.255733 | 0.100543 |

The weights vary materially; failure is not an accidental constant-weight implementation. The same-event donor fraction is 0.000344 and every donor remains in its recipient’s held-out event fold. Population inclusion weights differ across rows, so within-fold row shuffling changes weighted threshold means by up to 0.081–0.101; the separate average-vector control is essential and this shuffle is not a perfect marginal-preserving control.

At 1 second, mean preclip gradient norms are about .027 for context versus .046 for CRPS and .036 for average weights. No updates in those arms are clipped. Per-record mean-one threshold normalization does not force equal gradient norms. Properized AD has larger gradients and about 1.4% clipped steps at 1 second; all values remain available in the audit JSON. These are diagnostics, not established causal explanations or invitations to retune on validation.

## Full-data Huber reference (different budget)

| Seconds | Full-data Huber bulk MAE | Full-data Huber M≥4 MAE | Pilot context bulk MAE | Pilot context M≥4 MAE |
|---:|---:|---:|---:|---:|
| 1 | 0.365343 | 0.686116 | 0.375864 | 0.897011 |
| 3 | 0.315881 | 0.551167 | 0.329598 | 0.732770 |
| 5 | 0.286189 | 0.486910 | 0.299401 | 0.630170 |

The 979,487-record Huber instrument baseline remains much stronger, but this is descriptive because the pilot has 197,676 recordings and a different objective. It cannot isolate the effect of the score. The older Huber runner has no COMPLETE/artifact manifest: its comparison probability/point files and run config are hashed, and validation identities align, but it does not receive the new pilot’s full artifact-provenance certification.

## Audit and limits

Each pilot has 34 manifested artifacts. Checks cover completion/manifest/source pins, all 12 student and 5 reference checkpoint hashes, reconstructed initialization and epoch orders, disjoint event folds, within-fold donor bijection, exactly reconstructed reference weights and weighted average vector, validation row identities, original mean/median decisions, ordinary continuous-label CRPS, discrete NLL, bulk/tail/event-macro/CVaR metrics. No GPU, inference, retraining, TEST evaluation, job change, or model selection was used for this audit.

Raw 85-feature tensors were not archived. Teacher normalizer checkpoint values match their saved hashes and source fold-exclusion logic, but independent numerical normalizer reconstruction and teacher-forward replay are unavailable. Student CNN is trained on all TRAIN; only the reference pipeline excludes that CNN. Upstream count normalization sees all TRAIN covariates. Source manual-P and whole-record release preprocessing limits remain. A completed audit is not a guarantee of external causality or superiority over published EEW systems.

Final review-fixed reports use the `_final` directories. Initial reports remain preserved; stricter probability checks do not change metric definitions. All 14 CPU tests pass (1.449 s). Final isolated Codex autoreview is clean (0.92) after three accepted numerical validation fixes; all three final real audits pass, with metrics and per-event rows exactly unchanged. See verification.json for hashes, commands, and accepted/rejected review decisions.

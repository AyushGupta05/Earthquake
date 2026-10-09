# Instrument and native-amplitude controls: two seeds, three windows

Three matched residual-distribution controls completed on the AWS A10G, using seeds 20261009 and 20261010, 15 fixed epochs, and the same 197,676 TRAIN recordings at each duration. The sample retains every M>=4 recording and up to four recordings of other events; inverse inclusion weights recover the recording population in expectation. No validation-based selection is used within these runs.

**Finding:** adding the allowed static instrument/site features consistently improves bulk and high-magnitude errors in both seeds at every requested duration. This is a stronger practical baseline, not a novel EEW principle. Detailed response and site tuples can identify station/domain characteristics, so a separate ablation is needed before attributing the entire gain to physical sensor correction.

## Matched probability ensembles

The table averages the two predicted probability vectors and takes their mean as the point estimate. Both seeds were fixed before training; every control uses the same ensembling rule. MedAE is median absolute prediction error, not the distribution-median decision.

| Seconds | Input control | MAE | MedAE | M>=4 MAE | CVaR95 | Event-macro MAE | M>=4 event-macro MAE |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | base | 0.405669 | 0.305301 | 0.870775 | 1.425276 | 0.461568 | 0.853183 |
| 1 | instrument | 0.377325 | 0.281630 | 0.709830 | 1.358248 | 0.425380 | 0.679983 |
| 1 | instrument_native | 0.376462 | 0.279799 | 0.704072 | 1.368693 | 0.422064 | 0.672888 |
| 3 | base | 0.356927 | 0.264070 | 0.728964 | 1.303962 | 0.400241 | 0.699005 |
| 3 | instrument | 0.329443 | 0.243162 | 0.588089 | 1.232876 | 0.365040 | 0.550153 |
| 3 | instrument_native | 0.328952 | 0.241978 | 0.584310 | 1.240476 | 0.364645 | 0.546569 |
| 5 | base | 0.327979 | 0.235165 | 0.639201 | 1.266235 | 0.364440 | 0.608256 |
| 5 | instrument | 0.299253 | 0.212464 | 0.505174 | 1.201221 | 0.329152 | 0.465082 |
| 5 | instrument_native | 0.298719 | 0.211646 | 0.503565 | 1.205229 | 0.329445 | 0.462857 |

Static instrument/site information accounts for most of the gain. Extra approximate native-unit prefix summaries further reduce bulk and high-magnitude errors slightly, but worsen CVaR95 compared with static features alone. Both remain better than their matched base control on these measures. The single M>=5 validation event also improves, but one earthquake is insufficient to establish performance on rare damaging events.

## Individual seeds

| Seconds | Seed | Control | MAE | MedAE | M>=4 MAE | CVaR95 |
|---|---|---|---:|---:|---:|---:|
| 1 | 20261009 | base | 0.405860 | 0.305459 | 0.867007 | 1.426515 |
| 1 | 20261009 | instrument | 0.379462 | 0.283703 | 0.703877 | 1.358322 |
| 1 | 20261009 | instrument_native | 0.378285 | 0.281706 | 0.696485 | 1.369835 |
| 1 | 20261010 | base | 0.405742 | 0.305245 | 0.875024 | 1.425016 |
| 1 | 20261010 | instrument | 0.376482 | 0.280182 | 0.718166 | 1.362641 |
| 1 | 20261010 | instrument_native | 0.375985 | 0.278903 | 0.713854 | 1.371391 |
| 3 | 20261009 | base | 0.356073 | 0.263738 | 0.741387 | 1.300594 |
| 3 | 20261009 | instrument | 0.330579 | 0.245095 | 0.588004 | 1.233771 |
| 3 | 20261009 | instrument_native | 0.330427 | 0.244126 | 0.583297 | 1.243982 |
| 3 | 20261010 | base | 0.358096 | 0.264539 | 0.716892 | 1.308980 |
| 3 | 20261010 | instrument | 0.329083 | 0.242411 | 0.588790 | 1.233699 |
| 3 | 20261010 | instrument_native | 0.328365 | 0.241126 | 0.585918 | 1.239526 |
| 5 | 20261009 | base | 0.328865 | 0.235638 | 0.645292 | 1.269045 |
| 5 | 20261009 | instrument | 0.301439 | 0.214111 | 0.503845 | 1.207009 |
| 5 | 20261009 | instrument_native | 0.301074 | 0.213534 | 0.501487 | 1.213477 |
| 5 | 20261010 | base | 0.327679 | 0.234653 | 0.633387 | 1.266768 |
| 5 | 20261010 | instrument | 0.298009 | 0.211324 | 0.507942 | 1.199831 |
| 5 | 20261010 | instrument_native | 0.297544 | 0.210296 | 0.507207 | 1.202487 |

## Exact input difference

- Base: 66 centered frozen-CNN logits, 128 frozen features and 51 descriptors computed from the actual 1/3/5-second input.
- Instrument: additionally 34 allowed sensor/site features: sensor family, elevation, Vs30, missingness and per-component sensitivity/unit/calibration-frequency/sample-rate information. No station IDs, geographic coordinates, event location, catalog distance, magnitude type, full-trace SNR or peak-motion metadata enter the model.
- Instrument + native: also 12 prefix amplitude/energy summaries after undoing audited count normalization and dividing by the correctly matched component sensitivity. This approximates native units; it is not frequency-response deconvolution. Velocity and acceleration sensors are distinguished.

Every control has the same 291-input residual network, parameter count, initialization, sample order, dropout stream and fixed loss (beta=5 weighted Huber +0.075 CE). Unused feature columns are zero-masked after the same TRAIN-only weighted standardization. Inventory joins use network/station/location/channel and recording epoch, not current hardware assumptions. Original source preprocessing still used full-record detrending/resampling, so these checks do not establish raw operational causality.

## Verification and interpretation

Twelve focused CPU tests, all-window synthetic extraction checks and isolated Codex autoreview passed before launch. Exact target/trace/event alignment, source metadata/checkpoint/normalizer hashes, sampled raw-prefix equality and exhaustive validation-logit agreement are recorded in each run. All three components match inventory for 99.48% of training and 99.41% of validation recordings; missing-response cases remain represented by explicit masks.

The remaining scientific checks are gain-only versus site/family features, station/fingerprint overlap, event-cluster confidence intervals and a stronger full-recording fit. These reused validation results cannot establish independent superiority to published papers. A new method must beat this stronger baseline, not merely the old count-only CNN.

## Provenance

- 1s: `results/2026-10-09/phase2/instrument_residual_1s_1bbf4f4d67e5_2b94eb7e7f00`; 98.1 seconds total. Large probability/checkpoint files: `/mnt/eew-research/runs/instrument_residual_1s_1bbf4f4d67e5_2b94eb7e7f00` on the earthquake worker.
- 3s: `results/2026-10-09/phase2/instrument_residual_3s_1ebd2ac6e35d_c019cf0c8deb`; 112.1 seconds total. Large probability/checkpoint files: `/mnt/eew-research/runs/instrument_residual_3s_1ebd2ac6e35d_c019cf0c8deb` on the earthquake worker.
- 5s: `results/2026-10-09/phase2/instrument_residual_5s_8ffeb0a0aeba_55cd3e5f1074`; 115.7 seconds total. Large probability/checkpoint files: `/mnt/eew-research/runs/instrument_residual_5s_8ffeb0a0aeba_55cd3e5f1074` on the earthquake worker.

Full metrics JSON also includes distribution-median decisions, CRPS, threshold Brier scores, false positives, tail bias, and every seed. No outcome is discarded.

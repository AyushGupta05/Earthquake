# Earthquake distribution experiments — 9 October 2026

## Outcome

**No tested correction achieved lower high-magnitude error while preserving ordinary and worst-error performance.** The useful results are an audited duration-correct baseline, a clearer diagnosis of the current distribution method, and reproducible negative controls. These experiments are exploratory because the validation data previously selected the backbone checkpoints and earlier corrections. They are not a new independent test or a state-of-the-art result.

## Data and input audit

| Split | Recordings | Distinct events | M>=4 events | M>=5 events | M>=6 events | Maximum magnitude |
|---|---:|---:|---:|---:|---:|---:|
| Train | 979,487 | 47,273 | 323 | 30 | 3 | 6.5 |
| Validation | 96,993 | 3,711 | 13 | 1 | 0 | 5.1 |
| Test | 82,769 | 3,024 | 10 | 0 | 0 | 4.5 |

Source IDs and trace names are disjoint across the three splits. The split is chronological: training through 2017, validation in 2018, test in 2019–January 2020. Labels mix ML, Mw and Md, predominantly ML. Hundreds of stations for one event are not hundreds of independent earthquakes. The 91 M>=5 validation recordings all belong to one M5.1 event.

The old 1-second investigation notebooks import a loader for the **300-sample / 3-second** cache. A variable-length CNN accepts that input without an error. This makes notebook names unreliable evidence of observation duration. The new exporter explicitly checks 100/300/500 samples, all cached targets, and sampled waveform identities against raw traces under the required training normalization. It records metadata, normalization and checkpoint hashes. Identity sampling covers up to 24 rows per split per duration; it does not claim an exhaustive raw-waveform comparison.

The model has 66 magnitude bins, centred at 0.05 through 6.55. The supplied September correction study concerns M>=4, despite the informal description of M>=6. These thresholds must remain explicit in any paper. No test predictions were made in this work; historical checkpoint metadata indicates the test split has already been used previously, so it should not be labelled untouched.

## Duration-correct baseline and direct tail weighting

All point-error numbers below are magnitude units; FP4 counts recordings whose true magnitude is below 4 but whose point estimate is at least 4. This is a magnitude-threshold diagnostic, not an operational ground-shaking false-alert count. CVaR95 is mean absolute error among the worst 5% of recordings. M4 macro MAE gives each M>=4 event equal weight.

| Window | Decision | Overall MAE | MedAE | M>=4 MAE | M4 macro MAE | CVaR95 | FP4 |
|---|---|---:|---:|---:|---:|---:|---:|
| 1s | Raw mean | 0.414320 | 0.318424 | 0.899153 | 0.876611 | 1.414283 | 609 |
| 1s | Raw median | 0.410544 | 0.250000 | 0.919133 | 0.898696 | 1.434103 | 676 |
| 1s | 11x tail mass, median | 0.454032 | 0.350000 | 0.701607 | 0.688416 | 1.693670 | 4,644 |
| 3s | Raw mean | 0.363262 | 0.273805 | 0.751692 | 0.720239 | 1.293831 | 615 |
| 3s | Raw median | 0.362275 | 0.250000 | 0.781646 | 0.751259 | 1.322680 | 759 |
| 3s | 11x tail mass, median | 0.393228 | 0.250000 | 0.583106 | 0.552423 | 1.528206 | 4,003 |
| 5s | Raw mean | 0.331355 | 0.238753 | 0.651258 | 0.618804 | 1.256338 | 635 |
| 5s | Raw median | 0.331025 | 0.250000 | 0.686806 | 0.654898 | 1.290928 | 752 |
| 5s | 11x tail mass, median | 0.362118 | 0.250000 | 0.516699 | 0.493093 | 1.498660 | 4,179 |

The 11x intervention improves high-magnitude error at every duration but worsens overall MAE, the worst-error tail, and false positives. At one second, M>=4 MAE falls from 0.899 to 0.702 while false M4 predictions rise from 609 to 4,644. This demonstrates a changed decision cost; it does not establish better calibrated probabilities.

The fresh one-second raw MAE is 0.414320, whereas the September PDF used 0.442075. These are not a before/after improvement comparison: checkpoint/input protocol differences must be reconciled first. The new values closely reproduce the corresponding saved checkpoints' validation metadata.

## Controlled distribution readouts

Three input families use the same five event folds and ExtraTrees configuration (64 trees, maximum depth 16, minimum leaf size 50, random seed 20261009 + fold): raw mean only, five prior-response features, and all 66 probabilities. For each outer fold, three folds fit the tree and a separate fourth fold chooses a decision; the fifth evaluates it. The tree uses equal total event weights and a fixed 0.0001 mixture with the training prior to avoid zero bins. This experiment is a controlled new configuration, not an exact reimplementation of every September forest setting.

The five features are the alpha=1 mean plus differences for alpha=0.25, 0.5, 0.75, and 1.25. Calibration selects among tail multipliers 1/2/4/8/11 and blend strengths 0.25/0.5/1. Its fixed exploratory tolerances are +0.01 for overall MAE, MedAE, RMSE and event-macro MAE; +0.02 for CVaR95; and +0.002 absolute FPR. These are empirical tolerances, not proof of constant population risk. The unmodified mean is always a fallback.

| Window | Selected policy family | Overall MAE | MedAE | M>=4 MAE | M4 macro MAE | CVaR95 | FP4 |
|---|---|---:|---:|---:|---:|---:|---:|
| 1s | mean | 0.414320 | 0.318424 | 0.899153 | 0.876611 | 1.414283 | 609 |
| 1s | probe5 | 0.414320 | 0.318424 | 0.899153 | 0.876611 | 1.414283 | 609 |
| 1s | full66 | 0.414320 | 0.318424 | 0.899153 | 0.876611 | 1.414283 | 609 |
| 3s | mean | 0.363262 | 0.273805 | 0.751692 | 0.720239 | 1.293831 | 615 |
| 3s | probe5 | 0.363262 | 0.273805 | 0.751692 | 0.720239 | 1.293831 | 615 |
| 3s | full66 | 0.363262 | 0.273805 | 0.751692 | 0.720239 | 1.293831 | 615 |
| 5s | mean | 0.330249 | 0.236745 | 0.657343 | 0.625955 | 1.257624 | 665 |
| 5s | probe5 | 0.328171 | 0.233341 | 0.661406 | 0.629995 | 1.260975 | 688 |
| 5s | full66 | 0.329966 | 0.236800 | 0.659590 | 0.628368 | 1.260232 | 665 |

Every calibration fold selected the unchanged baseline at 1 and 3 seconds. At 5 seconds, some folds accepted an 11x-mass median blended at 0.5, but aggregate held-out tail MAE worsened. The full-probability unshifted tree at 5 seconds achieved overall MAE 0.325566 versus 0.331355 for the CNN, while M>=4 MAE worsened from 0.651258 to 1.236059. A bulk improvement alone is therefore a misleading success criterion for this project.

## Frozen waveform encoder, retrained probability layer

The 1-second pilot uses a deterministic maximum of four stations from every training event: 180,562 recordings across 47,273 events. All waveform and hidden layers are frozen in evaluation mode; only the final 128-to-66 linear layer is retrained. The three arms share initial weights, samples, event weights, AdamW learning rate 0.001, and five fixed epochs. Results use the final epoch; no best-epoch selection occurred. Feature extraction and head fitting completed in about 13.7 seconds on the A10G, excluding process startup and earlier audits.

CE denotes cross-entropy; ordinal CRPS denotes the positive-weight ordered-bin CDF score. The tail arm gives CDF thresholds at or above M4 an additional weight of 10 (total 11). It changes threshold weights, not label-dependent sample weights. It is a proper score for the discrete ordered-bin target. It does not guarantee better point errors, and event weighting changes the target population relative to a recording-weighted fit.

| Fixed final-epoch mean | Overall MAE | MedAE | M>=4 MAE | CVaR95 | FP4 | CRPS | Tail CRPS at 4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original | 0.414320 | 0.318424 | 0.899153 | 1.414283 | 609 | 0.293597 | 0.004875 |
| CE | 0.406410 | 0.314526 | 1.222222 | 1.382253 | 86 | 0.288848 | 0.003766 |
| Ordinal CRPS | 0.407792 | 0.313481 | 1.277417 | 1.396583 | 65 | 0.290114 | 0.003708 |
| Ordinal CRPS + tail | 0.407807 | 0.313403 | 1.288917 | 1.395783 | 57 | 0.290075 | 0.003679 |

All three fits improve overall MAE and proper scores but substantially worsen M>=4 MAE. The tail-weighted arm improves tail CRPS while worsening the high-magnitude point estimate; the metrics ask different questions. These results do not show that proper scoring is ineffective when training the entire network. Comparing the three arms isolates their objectives under a fixed setup; comparison against the original also changes fitting population and optimisation history. No architecture-scale conclusion follows from a five-epoch final-layer pilot.

## Interpretation and next experiment

The current evidence favours adding **causal evidence for when to correct**, while keeping forecast probabilities separate from a cost-sensitive point decision. The companion literature review specifies an evidence-gated residual distribution and calibration-constrained decision family, along with controls that can disprove its value. TEAM-LM, physical amplitude/geometry methods, and proper scoring are the most relevant ingredients to borrow. The next training comparison needs recording-weighted and event-weighted controls, a genuine feature ablation, and an independent high-magnitude benchmark.

These exploratory point estimates are not accompanied by generalisation confidence claims. In particular, one M5 event cannot support a population-level M5 conclusion. A final paper needs paired event/sequence-level uncertainty and fresh data; extra station recordings cannot repair that sample-size limitation.

## Reproducibility and verification

Scripts, their exact commands, and limitations are in `research/2026-10-09/README.md`. Aggregate JSON, fold choices, checkpoint/metadata hashes, environment versions, and pilot epoch history are in `results/2026-10-09/`. Waveforms, checkpoints and prediction arrays stay out of Git. The existing dataset was mounted read-only; no new instance was launched and the GPU was idle after completion.

All 10 focused tests passed on the experiment host. They cover CRPS against an independent pairwise formula, event weighting/splitting, rejection of an unsafe correction, support preservation, differentiability/propriety of the CDF loss, station sampling, and rejection of incompatible preprocessing. Codex autoreview accepted one preprocessing finding, which was fixed and tested; the final helper run returned clean. Its invocation used `autoreview --mode local --engine codex --no-web-search` with the installed app's Codex binary because the global wrapper was broken.

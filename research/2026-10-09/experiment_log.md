# Experiment log

## 2026-10-09 — A0: recover and inspect

Source checkout: `8332ad2` (`main`). Clean remote working tree on arrival. Existing host: g5.xlarge, one NVIDIA A10G, no active GPU processes. Dataset was not mounted; existing XFS EBS volume was mounted read-only at `/data`. No new instance provisioned.

Metadata audit: train 979,487 records / 47,273 events; validation 96,993 / 3,711; test 82,769 / 3,024. All pairwise source-ID and trace-name intersections are empty. Training covers 2005–2017; validation 2018; test 2019–January 2020. M>=4 event counts are 323 / 13 / 10; M>=5 are 30 / 1 / 0; M>=6 are 3 / 0 / 0. The validation maximum is 5.1 and test maximum 4.5. Labels mix ML, Mw, and Md; the main dataset is mostly ML.

Inference audit identified an explicit duration mismatch in existing notebooks: `instancepipelineprior` loads the 3-second cache even when the notebook/checkpoint name says 1 second. Complete target alignment, sampled raw waveform identity, and fresh correct-window predictions were completed before model comparison. All caches use global training standardization.

The September report's 1,027 M>=4 recordings therefore cannot be interpreted as 1,027 independent large earthquakes. Results from reused validation data remain exploratory. Event-macro and recording-micro metrics will be reported separately.

## A0 completion

Duration-correct overall/M>=4 MAE: 1s 0.414320/0.899153; 3s 0.363262/0.751692; 5s 0.331355/0.651258. Checkpoint metadata reproduces these scores closely. The first raw-identity audit rejected the standardized cache because it initially compared unnormalized counts. The check was corrected to account explicitly for the saved training mean/std, and then tightened to reject raw-count or mixed caches for these fixed checkpoints. The final audit rerun returned identical predictions.

## A1 completion

Ran 3 durations x 3 input families x 5 folds = 45 tree fits. At 1/3s all constrained choices fell back to raw predictions. At 5s a few corrections were selected but aggregate M>=4 error increased. Raw 11x tail weighting reduced M>=4 error and worsened bulk/worst errors and false positives. Full tables and all negative outcomes are recorded in experiment_results.md and aggregate JSON.

## A2 pilot completion

Ran CE, ordered-bin CRPS, and CRPS with an added tail weight of 10, five epochs each, starting from the same frozen 1s encoder and final-layer weights. Fixed final epochs; no test evaluation. 180,562 training records / 47,273 events, max four stations each. Initial feature-reproduction check failed when extraction and inference used different GPU batch shapes; matching the audited batch size of 256 and chunking the head check restored agreement without loosening tolerance. Completed pilot runtime 13.7 seconds. All three probability-layer fits improved bulk/proper scores and worsened M>=4 MAE. This is not evidence against all end-to-end proper-score models.

## Verification and review

Ten focused unit tests passed on the existing host. Local bundled Python lacked SciPy, so tests ran in the existing experiment environment. No dependencies were changed on the host. The first autoreview invocation hit a broken global Codex wrapper; the installed app binary resolved it. A later helper rejected an absolute-path finding format; retrying with repository-relative finding paths produced one actionable cache-normalization finding. The fix requires training_global_standardization for all named checkpoints. Focused tests and an audit rerun passed; the final Codex autoreview returned no actionable findings. No Crabbox configuration was present.

## Current scientific status

The research review and initial controls are complete. A method that improves high-magnitude and worst-error tails while preserving mean/median error has NOT been established. End-to-end feature/objective ablations, matched external baselines, and an independent high-magnitude benchmark remain necessary. No test predictions or new cloud instances were created in this milestone.

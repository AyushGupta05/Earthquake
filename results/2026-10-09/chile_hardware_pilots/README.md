# A10G TRAIN-only runtime pilots, 2026-10-09

Both completed with exit 0; DEV scoring was disabled and the official TEST data were absent. Worker was confirmed idle at closeout (no training process, no GPU process, GPU 0 MiB / 0%). No event64 or station64 pilot was run: dispatches were held at the parent's hardware-decision request.

Code commit: `f682100`; Python 3.12.10, Torch 2.8.0+cu129, A10G 23,028 MiB, four vCPUs, about 15.4 GiB RAM. Focused CPU verification passed all 30 model/training tests. Full-cache SHA and metadata SHA were checked by the runner on each invocation. Data remained on the read-only mount.

Both pilots used one event epoch, no station pretraining, seed 20261009, the fixed 5,767-event TRAIN calibration partition, author -4 to +25 s training cutoffs, author station blinding, training-only label smoothing, magnitude resampling 2, and TRAIN-calibration NLL scheduling/selection. Each had a 900-second timeout with 30-second termination grace. No timeout occurred. Fit subsets were fixed before model construction. These are execution measurements, not convergence or scientific-performance evidence.

| Measure | Event16 | Event32 |
|---|---:|---:|
| Fit events | 2048 | 4096 |
| Resampled presentations | 2229 | 4368 |
| Training batches | 140 | 137 |
| First 100 batches, seconds | 40.30 | 23.81 |
| Complete training, seconds | 45.50 | 31.85 |
| Calibration plus selection, seconds | 44.68 | 28.82 |
| Complete epoch, seconds | 90.18 | 60.68 |
| Complete invocation, seconds | 309.78 | 259.24 |
| Other invocation overhead, seconds | 219.59 | 198.56 |
| Whole-epoch peak allocated, GiB | 8.19 | 1.06 |
| Whole-epoch peak reserved, GiB | 10.80 | 2.64 |

The invocation overhead is predominantly full 30.43 GB cache verification and metadata setup, but it also includes final artifact writes; the current instrumentation does not isolate those components. Calibration time is computed by subtraction and includes selection/checkpoint work before the epoch timer ends. The final recovery checkpoint is written afterward.

Batch32 used much less peak GPU memory than batch16. The measured peak therefore does not scale monotonically with batch size in these runs; a shape-dependent convolution workspace is a possible cause, not a proven diagnosis. Do not infer batch64 feasibility from a linear memory multiplier. Neither pilot had an out-of-memory failure.

## What these pilots support

The runner executes a full training/calibration/checkpoint cycle on verified real Chile TRAIN data and remains finite. A source-sized batch64 and single-station pretraining still need measurements. The A10G batch32 observation gives a literal linear projection of about 11.95 hours for 100 full event epochs (55,053 resampled presentations plus full TRAIN calibration per epoch), before pretraining. Batch16 gives 32.46 hours under the same naive formula. This wide discrepancy demonstrates why these are not reliable whole-training forecasts: different fit-subset sizes, initial kernel setup, varying station shapes, OS cache state, and compressed-HDF read amplification are confounded. A small subset can remain cached while the complete training set cannot fit in this worker's RAM.

For a defensible full-budget forecast, run at least two TRAIN-only pilot epochs on the eventual hardware, separately measure single-station training/calibration, and record first versus second epoch throughput. Pretraining needs 12,137 fitting batches per epoch at batch64, and its TRAIN calibration needs 1,350 batches evaluated at each of 1/3/5 s. Event training needs 861 batches per epoch at batch64; event calibration needs 91 batches at each time. The planned 25+100 budget therefore has 303,425 station-training batches, 86,100 event-training batches, 101,250 station-evaluation forwards, and 27,300 event-evaluation forwards. Include per-epoch checkpoint and CPU proper-score overhead in the forecast.

A move to 32 GiB system RAM may improve cache residence: the compressed file is 28.34 GiB. Complete residence is not guaranteed after OS/Python/CUDA-host overhead. GPU and system-memory changes require a new runtime pilot; these G5 results must not be relabeled as L40S evidence. No convergence schedule or model-selection choice should be based on DEV/TEST.

The JSON evidence includes immutable run identity, full split membership, history, runner config, log, start/end and exit code. `summary.json` records hashes of each evidence file. Original model/checkpoint artifacts remain in each recorded worker run directory. Billing was not queried by this subtask; the parent applies its verified AWS price and credit ledger.

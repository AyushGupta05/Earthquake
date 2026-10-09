# Chile TEAM-LM benchmark: protocol and runner

This is a PyTorch architecture port and a controlled benchmark adaptation. Numerical equivalence to the original TensorFlow implementation has **not** been established. Cite [TEAM-LM](https://doi.org/10.1093/gji/ggab139), the [author software](https://doi.org/10.5880/GFZ.2.4.2021.003), and the [Chile dataset](https://doi.org/10.5880/GFZ.2.4.2021.002). Source-specific architecture details and deviations are documented in `team_lm.py`.

## Data and heldout events

The runner accepts only the checksum-verified `chile-team-prefix-v1` export plus its adjacent `.hdf5.manifest.json`, `.hdf5.metadata.csv`, and `.hdf5.metadata.csv.manifest.json`. The metadata sidecar contains exactly `EVENT,MA,TIME,source_row_index,benchmark_split`, exported/readback-verified from that cache's pandas table. Its own checksum and parent-cache checksum are required, and its event IDs and source rows must exactly match the HDF split datasets. Numeric values use round-trip CSV parsing. The HDF cache remains unchanged.

Both raw, uncentered float32 ZNE caches are supported:1,000 or3,000 samples,100Hz, index zero at network-first-P minus five seconds. Coordinates remain latitude/longitude degrees and depth km. Chile has continuous stations and no per-station P-pick field; no trigger gating is invented. The source has at most21 stations/event, so the default cap25 retains all stations.

The AWS Python3.9 environment has NumPy2.0.2. Installing the normally resolved PyTables3.9.2 wheel exposed an ABI incompatibility (`numpy.dtype size changed`). Shared NumPy/ML packages were not downgraded. PyTables3.9.2 remains installed but is unused by this runner and its h5py/CSV-only tests. The verified sidecar removes PyTables from training-time requirements; metadata export occurs in the already compatible local environment.

Only the original chronological TRAIN and DEV event groups are present. The original metadata `SPLIT` column is unrelated and is ignored. Explicit `benchmark_split`, original source rows, split datasets, and exporter membership digests must agree. A full cache hash is computed at startup. TEST waveform groups are neither present nor opened.

Original TRAIN is divided into fitting and calibration events using seed20261009 and fixed magnitude bands `<4`, `[4,5)`, `[5,5.5)`, `[5.5,6)`, `>=6`. Approximately10% from each band goes to calibration; a band with at least two events contributes at least one and retains at least one, while singleton bands stay in fitting. Exact event memberships and checksums are saved. A different DEV magnitude cannot change this partition. Pilot row limits are applied only after this partition and are recorded.

`--selection final` reports the fixed final epoch. `--selection calibration-nll` runs the same complete epoch budget and selects the epoch with lowest mean proper Gaussian-mixture NLL across1/3/5s on **TRAIN calibration only**. DEV is first evaluated after training and selection. Neither its metrics nor its labels select an epoch, schedule, or optimizer setting.

## Matched architecture controls and training

`--aggregation transformer` uses six transformer blocks and the event token. `--aggregation pool` retains the same station encoder, coordinate embeddings, magnitude MLP, and five-Gaussian output, replacing attention with the source-style two-layer station MLP and explicitly masked max pooling. Inputs and training budget match; parameter counts do not. They are recorded separately.

Common density-head initializations are seeded independently of aggregator size. Training uses Adam at1e-4, gradient norm clipping at1, no dropout/scheduler, and fixed epochs. Fitting events shuffle deterministically each epoch. Optional station dropout and random station capping affect fitting events only; evaluation retains deterministic source station order. Default station dropout is zero.

The default magnitude resampling factor2 follows the author exactly: `(4,5]` events repeat8 times, `(5,6]`16 times, and so on through `(8,9]`128 times. Evaluation and calibration never resample. `--magnitude-resampling 1` is an explicit ablation. Oversampling changes the training distribution; this runner does not claim the resulting probabilities are deployment calibrated.

Optional `--pretrain-epochs N` trains the encoder and a separate station density head over **every station of fitting TRAIN events**, then discards that head for event fitting. Source label perturbation aboveM4 is applied only during this pretraining. Source single-station pretraining zeroes the suffix without demeaning; event-model preprocessing demeans the strictly observed prefix. Pretraining and event fitting use separate Adam moments. No pretraining selection uses DEV or calibration labels.

Training cutoff choices:

- `discrete`: uniform random1/3/5s per training example; supported by both caches and useful for matched early-window experiments.
- `uniform-early`: integer cutoffs between−4 and+5s; an early-window adaptation supported by both caches.
- `author`: original integer cutoffs between−4 and+25s; rejected unless the verified cache stores3,000 samples. A half-sample interior time representation avoids floating-point floor errors while preserving the exact integer masks.

Every experiment evaluates1/3/5s. Source settings25 pretraining epochs and100 event epochs can be supplied explicitly; the default2-epoch/no-pretraining pilot cannot reproduce the published optimization budget. Training currently retains the author's NLL density floor1e-6; `--density-epsilon 0` enables exact proper log loss and must be compared consistently. Evaluation always reports the normalized mixture's proper NLL and analytic CRPS.

## Run

```bash
# Smoke/pilot: matched early-window controls; repeat with --aggregation pool.
python research/2026-10-09/phase3/train_team_lm.py \
  --cache /mnt/eew-research/chile/chile_train_dev_prefix1000.hdf5 \
  --aggregation transformer --epochs 2 --batch-size 16 \
  --pretrain-epochs 0 --training-cutoff discrete --selection final \
  --output /mnt/eew-research/runs

# Source-sized observation/training schedule (still a PyTorch port and
# TRAIN-calibration adaptation, not a verified numerical reproduction).
python research/2026-10-09/phase3/train_team_lm.py \
  --cache /mnt/eew-research/chile/chile_train_dev_full3000.hdf5 \
  --aggregation transformer --pretrain-epochs 25 --epochs 100 \
  --batch-size 64 --pretrain-batch-size 64 \
  --training-cutoff author --selection calibration-nll \
  --output /mnt/eew-research/runs
```

Use `CUDA_VISIBLE_DEVICES='' python -m unittest discover -s tests -p 'test_team*.py' -v` for focused CPU verification. The runner prints first100-batch timing for runtime estimates. Batch16 is a conservative starting point on a24GB A10G; actual memory/runtime must be measured before increasing batch size. Lazy HDF reads avoid loading the full cache into GPU memory. Each optimizer recovery checkpoint is approximately0.2GB, depending on architecture; retain space for final weights and the13GB compact or approximately30GB full data cache.

Outputs include immutable run identity, source/cache/split hashes, full event membership, epoch history, atomic optimizer/model/RNG recovery checkpoints, final selected weights, and per-event DEV mixture parameters/predictions. Mean and median decisions have MAE, median absolute error, RMSE, bias, CVaR95, and magnitude-stratified errors includingM≥5.5. Probability diagnostics include proper NLL, exact Gaussian-mixture CRPS, M≥5.5 Brier score,90% coverage and interval width. Empty magnitude strata are reported as null, never zero error.

Recovery checkpoints preserve completed epochs but automatic resume is not implemented yet. An interrupted run must not be reported as completing its fixed budget. No training jobs are automatically started by importing these modules.

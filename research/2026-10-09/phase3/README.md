# Chile TEAM-LM benchmark: protocol and runner

This is a PyTorch architecture port and a controlled benchmark adaptation. Numerical equivalence to the original TensorFlow implementation has **not** been established. Cite [TEAM-LM](https://doi.org/10.1093/gji/ggab139), the [author software](https://doi.org/10.5880/GFZ.2.4.2021.003), and the [Chile dataset](https://doi.org/10.5880/GFZ.2.4.2021.002). Source-specific architecture details and deviations are documented in `team_lm.py`.

## Data and heldout events

The runner accepts only the checksum-verified `chile-team-prefix-v1` export plus its adjacent `.hdf5.manifest.json`, `.hdf5.metadata.csv`, and `.hdf5.metadata.csv.manifest.json`. The metadata sidecar contains exactly `EVENT,MA,TIME,source_row_index,benchmark_split`, exported/readback-verified from that cache's pandas table. Its own checksum and parent-cache checksum are required, and its event IDs and source rows must exactly match the HDF split datasets. Numeric values use round-trip CSV parsing. The HDF cache remains unchanged.

Both raw, uncentered float32 ZNE caches are supported:1,000 or3,000 samples,100Hz, index zero at network-first-P minus five seconds. Coordinates remain latitude/longitude degrees and depth km. Chile has continuous stations and no per-station P-pick field; no trigger gating is invented. The source has at most21 stations/event, so the default cap25 retains all stations.

The AWS Python3.9 environment has NumPy2.0.2. Installing the normally resolved PyTables3.9.2 wheel exposed an ABI incompatibility (`numpy.dtype size changed`). Shared NumPy/ML packages were not downgraded. PyTables3.9.2 remains installed but is unused by this runner and its h5py/CSV-only tests. The verified sidecar removes PyTables from training-time requirements; metadata export occurs in the already compatible local environment.

Only the original chronological TRAIN and DEV event groups are present. The original metadata `SPLIT` column is unrelated and is ignored. Explicit `benchmark_split`, original source rows, split datasets, and exporter membership digests must agree. A full cache hash is computed at startup. TEST waveform groups are neither present nor opened.

Original TRAIN is divided into fitting and calibration events using seed20261009 and fixed magnitude bands `<4`, `[4,5)`, `[5,5.5)`, `[5.5,6)`, `>=6`. Approximately10% from each band goes to calibration; a band with at least two events contributes at least one and retains at least one, while singleton bands stay in fitting. Exact event memberships and checksums are saved. A different DEV magnitude cannot change this partition. Pilot row limits are applied only after this partition and are recorded.

`--selection final` reports the fixed final epoch. `--selection calibration-nll` runs the same complete epoch budget and selects the epoch with lowest mean proper Gaussian-mixture NLL across1/3/5s on **TRAIN calibration only**. DEV is first evaluated after training and selection. Neither its metrics nor its labels select an epoch, schedule, or optimizer setting. Use `--skip-dev` for every development or throughput pilot: it skips DEV waveform loading, scoring, and prediction artifacts entirely. DEV metadata is still verified as part of cache membership checks.

The frozen seed20261009 partition contains51,912 fitting events and5,767 calibration events. Original TRAIN has only22 M≥5.5 earthquakes, of which20 are in fitting and two (M5.608 and6.106) in calibration. The only M≥7 TRAIN event (M8.054) remains in fitting. This calibration partition is suitable for aggregate convergence checks; its two tail events cannot establish high-magnitude improvement. More stable tail development requires prespecified event-disjoint TRAIN folds, with the unique M8 event reported separately and never represented as replicated independent evidence.

## Matched architecture controls and training

`--aggregation transformer` uses six transformer blocks and the event token. `--aggregation pool` retains the same station encoder, coordinate embeddings, magnitude MLP, and five-Gaussian output, replacing attention with the source-style two-layer station MLP and explicitly masked max pooling. Inputs and training budget match; parameter counts do not. They are recorded separately.

Common density-head initializations are seeded independently of aggregator size. Training uses Adam at1e-4, gradient norm clipping at1, no neural-layer dropout, and fixed epochs. The default has no learning-rate scheduler. Fitting events shuffle deterministically each epoch. Optional Bernoulli station dropout and random station capping affect fitting events only; evaluation retains deterministic source station order. Default station dropout is zero.

Source-derived training behaviors are explicit opt-ins, preserving the existing early-window defaults:

- `--station-blinding author` draws the number of hidden currently active stations uniformly from0 through S−1 and chooses that subset uniformly, independently for each training presentation. Availability is measured from the strictly observed prefix. This differs from the optional Bernoulli `--station-drop`; combining the two is rejected. Calibration and DEV never hide stations.
- `--event-label-smoothing` adds zero-mean Gaussian noise with standard deviation0.05×max(M−4,0) to event-training labels. Original targets and held-out labels remain unchanged.
- `--lr-schedule author-plateau` multiplies learning rate by0.3 after four pretraining or six event-stage calibration observations without an absolute1e-4 improvement. The PyTorch patience value is reduced by one to match Keras's inclusive waiting rule. Pretraining uses every station from held-out TRAIN events; event fitting uses held-out TRAIN events. Both monitor mean proper NLL at fixed1/3/5s, and scheduler state is saved in recovery checkpoints. No schedule observes DEV.

The default magnitude resampling factor2 follows the author exactly: `(4,5]` events repeat8 times, `(5,6]`16 times, and so on through `(8,9]`128 times. Evaluation and calibration never resample. `--magnitude-resampling 1` is an explicit ablation. Oversampling changes the training distribution; this runner does not claim the resulting probabilities are deployment calibrated.

Optional `--pretrain-epochs N` trains the encoder and a separate station density head over **every station of fitting TRAIN events**, then discards that head for event fitting. Source label perturbation aboveM4 always applies in pretraining; event-stage perturbation requires the explicit flag above. Source single-station pretraining zeroes the suffix without demeaning; event-model preprocessing demeans the strictly observed prefix. Pretraining and event fitting use separate Adam moments. Pretraining retains its fixed final epoch; optional learning-rate changes use TRAIN calibration only.

Completed pretraining writes `pretrained_encoder.pth` and its SHA256-bound `.manifest.json`. The versioned artifact records the original source/cache/metadata identities, exact fitting and calibration event hashes, ordered station IDs and counts, preprocessing, cutoff sampling, label noise, loss, optimizer, schedule, seed, batch size, completed epoch count, station-only implementation fingerprint, and originating run config. `--pretrained-encoder PATH --pretrain-epochs 25` requires exactly25 completed compatible pretraining epochs and skips their execution. It loads only the station encoder; the event aggregator/head and event optimizer remain newly initialized. Pooling and transformer architectures can therefore share exactly the same pretrained weights.

`--pretrain-cutoff` and `--pretrain-density-epsilon` default to the event-stage values. Set them explicitly when reusing, for example, an author-cutoff encoder for a discrete1/3/5s event-stage experiment. The import must still match all pretraining identities, including the exact verified cache; switching between compact/full caches is deliberately rejected even if their early prefixes match. Event-only augmentation, density objective, aggregation and epoch budget may differ without invalidating the encoder. Pretraining seed/batch/schedule and the TRAIN fitting/calibration membership must match. Legacy, arbitrary, incomplete, nonfinite or mismatched artifacts fail closed. These are recorded-provenance checks, not a cryptographic attestation against a deliberately forged training history.

Training cutoff choices:

- `discrete`: uniform random1/3/5s per training example; supported by both caches and useful for matched early-window experiments.
- `uniform-early`: integer cutoffs between−4 and+5s; an early-window adaptation supported by both caches.
- `author`: original integer cutoffs between−4 and+25s; rejected unless the verified cache stores3,000 samples. A half-sample interior time representation avoids floating-point floor errors while preserving the exact integer masks.

Every experiment evaluates1/3/5s. Source settings25 pretraining epochs and100 event epochs can be supplied explicitly; the default2-epoch/no-pretraining pilot cannot reproduce the published optimization budget. Training currently retains the author's NLL density floor1e-6; `--density-epsilon 0` enables exact proper log loss and must be compared consistently. Evaluation always reports the normalized mixture's proper NLL and analytic CRPS.

Even with all author-style flags, this remains an adaptation: source training draws one cutoff per minibatch, whereas this runner draws one per example; source validation repeats stochastic random-cutoff, station-blinded events, whereas this runner uses clean deterministic1/3/5s TRAIN calibration; original validation is DEV, which is reserved here for final assessment. The source station generator discards an incomplete final batch, whereas this runner retains it. The source event generator and this runner both retain incomplete event batches. Framework initialization, optimizer numerics, and strict-prefix boundary corrections are not a TensorFlow equivalence test. The original call sites force event label smoothing and station blinding on even though their generator defaults are false.

## Run

```bash
# Smoke/pilot: matched early-window controls; repeat with --aggregation pool.
python research/2026-10-09/phase3/train_team_lm.py \
  --cache /mnt/eew-research/chile/chile_train_dev_prefix1000.hdf5 \
  --aggregation transformer --epochs 2 --batch-size 16 \
  --pretrain-epochs 0 --training-cutoff discrete --selection final --skip-dev \
  --output /mnt/eew-research/runs

# Source-sized observation/training schedule (still a PyTorch port and
# TRAIN-calibration adaptation, not a verified numerical reproduction).
python research/2026-10-09/phase3/train_team_lm.py \
  --cache /mnt/eew-research/chile/chile_train_dev_full3000.hdf5 \
  --aggregation transformer --pretrain-epochs 25 --epochs 100 \
  --batch-size 64 --pretrain-batch-size 64 \
  --training-cutoff author --selection calibration-nll \
  --station-blinding author --event-label-smoothing --lr-schedule author-plateau \
  --output /mnt/eew-research/runs

# Reuse that completed encoder for a matched pooling control without repeating
# the25 pretraining epochs. Replace the path with the actual immutable run.
python research/2026-10-09/phase3/train_team_lm.py \
  --cache /mnt/eew-research/chile/chile_train_dev_full3000.hdf5 \
  --aggregation pool --pretrain-epochs 25 --epochs 100 \
  --pretrained-encoder /mnt/eew-research/runs/ORIGIN/pretrained_encoder.pth \
  --batch-size 64 --pretrain-batch-size 64 --pretrain-cutoff author \
  --training-cutoff author --selection calibration-nll \
  --station-blinding author --event-label-smoothing --lr-schedule author-plateau \
  --output /mnt/eew-research/runs
```

Use `CUDA_VISIBLE_DEVICES='' python -m unittest discover -s tests -p 'test_team*.py' -v` for focused CPU verification. The runner prints first100-batch timing for both stages, then records complete training time separately from epoch time including calibration, plus peak CUDA allocated/reserved bytes and next-epoch learning rate. Per-batch scalar loss collection synchronizes outstanding GPU work. First-epoch timing includes cold file/cache and accelerator setup costs; estimate sustained throughput from a subsequent epoch. Batch16 is a conservative starting point on a24GB A10G; actual memory/runtime must be measured before increasing batch size. Both cache lengths are padded to3,000 samples, so cropping storage does not reduce encoder convolution work.

The fit split has776,742 station records and55,053 event presentations after source magnitude resampling. At batch64 this gives12,137 pretraining updates and861 event updates per epoch:25+100 epochs require303,425+86,100 updates. With the optional plateau schedule, calibration adds1,350 station batches×3 times×25 epochs and91 event batches×3 times×100 epochs. Actual wall time must be estimated from measured stage-specific throughput; two pilot epochs are enough for feasibility and initial optimization diagnosis, not convergence or method ranking. The station dataset reads individual records from eight-station compressed chunks, so randomly shuffled pretraining may be limited by decompression/I/O.

Lazy HDF reads avoid loading the full cache into GPU memory. The transformer event model has13,273,293 parameters; its FP32 parameters, gradients and Adam moments occupy about203MiB before activations/workspaces. Pooling has1,752,793 parameters, so it is an input/training control, not a parameter-matched control. Each transformer optimizer checkpoint is about0.16GB, or0.21GB when it embeds the best selected weights; atomic replacement temporarily requires both old and new copies. Retain space for final weights and the13GB compact or approximately30GB full data cache.

Outputs include immutable run identity, source/cache/split hashes, full event membership, epoch history, atomic optimizer/model/RNG recovery checkpoints, final selected weights, and per-event DEV mixture parameters/predictions. Mean and median decisions have MAE, median absolute error, RMSE, bias, CVaR95, and magnitude-stratified errors includingM≥5.5. Probability diagnostics include proper NLL, exact Gaussian-mixture CRPS, M≥5.5 Brier score,90% coverage and interval width. Empty magnitude strata are reported as null, never zero error.

Recovery is supported at completed epoch boundaries with `--resume /absolute/original/run/latest.pth`, repeating the original command's other arguments unchanged. It continues in the original run directory and fixed budget. A versioned checkpoint includes the precise pretraining/event stage, completed epoch, model, optimizer, scheduler, Python/NumPy/CPU/CUDA random state, complete histories, and selected-checkpoint weights/state. Loaders rebuild the original seeded next-epoch order. Pretraining recovery finishes that stage before creating the event optimizer; event recovery never repeats or silently resets pretraining. Text histories and selected artifacts can be repaired from the atomic checkpoint after an interrupted write. A separate resume audit records the input checkpoint hash and continuation boundary.

Resume rejects legacy/incomplete checkpoints, changed code/config/cache/splits/runtime, moved run directories, and already-complete runs. It cannot extend the epoch budget, change hardware or resume a partial epoch; partial work after the latest complete epoch is discarded. Both pretraining and event-boundary recovery are tested against uninterrupted runs with **exact CPU tensor equality**, including optimizer, scheduler, random state and selected weights. GPU kernels can remain nondeterministic despite matching recorded hardware/software, so no universal GPU bitwise-equivalence claim is made. An interrupted run must not be reported as completing its fixed budget. Final `wall_seconds` covers the current invocation; `recorded_training_seconds` sums completed training epochs across recovery. No jobs launch automatically on import.

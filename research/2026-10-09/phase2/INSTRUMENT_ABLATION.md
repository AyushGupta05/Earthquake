# Matched instrument residual controls

`instrument_residual.py` compares three prespecified controls at each exact 1/3/5-second prefix. It freezes the existing CNN and trains a bounded residual over its 66 magnitude logits. The purpose is to test whether instrument gain/type and approximate native-unit prefix amplitudes remove a nuisance factor. This is a feature ablation, not a novelty claim for instrument correction.

| Control | Active features |
|---|---|
| `base` | Centered 66 logits, 128 frozen hidden features, 51 existing prefix summaries |
| `instrument` | Base plus 34 instrument/site fields |
| `instrument_native` | Instrument plus 12 sensitivity-normalized prefix summaries |

All controls use the same 291-dimensional architecture. Inactive groups are zero-masked **after** normalization, so every paired seed has exactly the same parameter count, initial parameters, dropout schedule and minibatch order. The default objective is population-weighted Huber + 0.075 CE. Optional `--beta` and `--anchor` are fixed for all controls and must be chosen before looking at the resulting validation scores. These losses do not guarantee calibrated posterior probabilities.

Training samples up to four recordings per event with the existing fixed sampling seed, retaining every M≥4 recording. Inverse inclusion weights recover the recording population in expectation. Both training loss and training-only feature mean/variance use those weights. `--max-per-event 0` trains on all recordings. Existing checkpoint pretraining is unchanged. Every requested seed/control is evaluated at its fixed final epoch; there is no validation checkpointing, candidate selection, blend search or threshold tuning. Mean, median, individual-seed results and the prespecified probability ensemble are all saved.

## Instrument fields and allowed information

`instrument_inventory.py` is copied from the separately reviewed StationXML prototype. `model_features()` permits exactly 34 numeric values: HH/EH/HN/HL/EN/unknown indicators; elevation and Vs30 with missingness flags; and per-component response missingness, log10 sensitivity, velocity/acceleration indicators, log1p sensitivity frequency/native sample rate with missingness flags. Coordinates, station IDs, event IDs, timestamps and epoch endpoints do not enter the model.

The join uses network/station/location/channel plus recording start time. Numeric CSV locations `1.0`/`2.0` are repaired only when the trace's SCNL suffix confirms `01`/`02`; its event-ID prefix is ignored. Multiple epochs are rejected, not chosen arbitrarily. Component mappings are exact E/N/Z; no silent HH1/HH2 rotation is attempted. The full train/validation feasibility audit matched all components for 99.4793%/99.4092% of records. Remaining gaps were historical IV.GIGS horizontals, which retain missing masks and the counts-based features. No rows are dropped for response coverage.

The 12 added summaries are log10 RMS, peak absolute value, mean absolute value, and sum-of-squares times 0.01 seconds, each for E/N/Z. The runner first inverts the saved count normalization `x * (std + 1e-8) + mean`, then divides by each component's sensitivity and demeans only the observed prefix. Missing responses produce zero summaries together with explicit response-missing features. Velocity and acceleration units remain distinguishable. Statistics are calculated only from the supplied 100/300/500 samples; no stored SNR, PGA, PGV or other full-trace statistics are read.

The [official INSTANCE release](https://github.com/INGV/instance/blob/main/README.md) supplies the [StationXML archive](http://repo.pi.ingv.it/instance/responses.tgz), SHA256 `71eccc6304afad15e9c45534ca374b4b4f974c9f93ccfc0f2683616ee6421ef2`. Pass its already downloaded local/AWS path; the runner never downloads data. It refuses a different archive unless its expected hash is explicitly supplied.

Sensitivity normalization is not full frequency-dependent instrument response removal. The [INSTANCE paper](https://essd.copernicus.org/articles/13/5509/2021/) documents whole-record detrending/resampling of count data; this runner cannot undo those preprocessing choices or establish strict raw-sensor operational causality. It also assumes the audited waveform component layout is E/N/Z. Static site descriptors can be available before an operational event, but their precise historical publication time is not audited. Site fields may introduce geographical shortcuts; any promising result needs a gain/type-only and held-out-station/region follow-up. Finite positive sensitivity is a syntactic check, not independent calibration certification.

## Identity checks and output

The runner pins the original metadata, normalization arrays, checkpoint and audit hashes, checks train/validation event and trace disjointness, and compares validation trace names and event IDs in exact row order against the audited NPZ. Cache targets are checked exhaustively in canonical float32, and cache shape must match every row and exact duration. Instrument features are computed in the same `.iloc[rows]` order used to index waveforms; no join-sort occurs.

Waveform identity is additionally checked at up to 80 deterministic raw-record rows per split, and **all** validation logits must reproduce the duration-audited reference within the existing numerical tolerance. Raw-waveform identity checks are sampled, not exhaustive: the cache does not store per-row trace identities. This limitation is recorded in the run. Input hashes, selected row/trace/event identities, weights, feature schema/masks, source hashes and raw-check indices are saved alongside every run. No test data are opened.

Every run gets an immutable directory through `create_run`. It contains all model states, training loss histories, metrics, paired prediction arrays, per-control probabilities with exact trace/event identities, and alignment/provenance manifests. There is no “selected” result. The historical validation split is reused exploratory material, so numerical improvements here alone are not independent confirmation or a high-magnitude state-of-the-art claim.

## CLI

From `/home/ec2-user/Earthquake`, after placing the pinned archive at the chosen path:

```bash
.venv/bin/python research/2026-10-09/phase2/instrument_residual.py \
  --seconds 1 --inventory /path/to/responses.tgz \
  --epochs 15 --seeds 20261009 20261010 --max-per-event 4
```

Repeat with `--seconds 3` and `--seconds 5`. GPU launches are controlled by the parent experiment queue; this implementation task does not launch training.

Focused CPU tests:

```bash
CUDA_VISIBLE_DEVICES='' .venv/bin/python -m unittest discover -s tests \
  -p 'test_instrument_residual.py' -v
```

Tests cover source and row alignment, wrong-duration rejection, gain/component order, affine inversion, unobserved-suffix invariance, missing responses, exclusion of future fields, inverse weighting, normalization without validation information, identical parameter budgets and reproducible fixed-seed fitting that ignores validation labels.

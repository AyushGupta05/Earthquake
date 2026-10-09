# Chile benchmark: current execution protocol

Updated 9 October 2026. Acquisition and TRAIN-only hardware pilots are complete or progressing as recorded in the pilot artifacts. Full-budget training has not yet started at this checkpoint. No DEV scores or TEST waveform predictions have been produced.

The [official TEAM-LM data](https://doi.org/10.5880/GFZ.2.4.2021.002) are now downloaded, extracted, audited and checksum verified. The older acquisition memo is historical; the following counts come from the actual HDF5 metadata using the author loader's chronological row-position split, not the dataset's different `SPLIT` column.

| Split | Events | MA≥5.5 | MA≥6 | MA≥7 | MA≥8 |
|---|---:|---:|---:|---:|---:|
| TRAIN | 57,679 | 22 | 12 | 1 | 1 |
| DEV | 9,614 | 1 | 0 | 0 | 0 |
| TEST | 28,840 | 30 | 12 | 3 | 2 |

These are magnitude MA labels as supplied, not interchangeable with INSTANCE ML or universal Mw. TEST metadata were inspected to establish split identity and support. TEST waveforms were not loaded or exported.

The full TRAIN+DEV export contains 67,293 events and 1,049,297 station records. It stores 3,000 samples at 100 Hz, five seconds before through 25 seconds after the network's first P arrival, with ZNE velocity components in m/s. At evaluation, 1/3/5-second cutoffs correspond to 600/800/1,000 available samples including the pre-event interval. Per-example demeaning uses only observed samples; later values are masked before normalization or feature extraction. This does not certify the unknown original release preprocessing as raw-stream causal.

Chile provides no individual-station P picks. The implementation uses the supplied continuous station traces, including pre-arrival noise when a wave has not yet reached a station. It does not use future station arrival labels to decide which stations exist. Station coordinates are inputs; catalogue epicentre, depth and source distance are not. This network-relative protocol is separate from INSTANCE's single-station P-relative track.

The reviewed implementation is a magnitude-only PyTorch adaptation of [TEAM-LM](https://arxiv.org/abs/2101.02010), with a waveform/amplitude encoder, coordinate embeddings, six attention blocks and a five-Gaussian mixture head. It is not claimed to be numerically identical to the original TensorFlow release. A pooling comparator shares input/encoder/head conventions but has fewer aggregation parameters; both differences must be reported. The original code is attributed in the implementation documentation.

The intended full baseline uses the author's 25 station-pretraining and 100 event-training epoch budgets, random −4 to +25-second training cutoffs, magnitude resampling, station blinding, label smoothing for the specified large-event regime, and plateau learning-rate schedules. A deterministic launcher will record backend settings before the full run. Batch size is selected from TRAIN-only runtime/memory measurements, not prediction scores.

For seed 20261009, original TRAIN is split into 51,912 fitting and 5,767 event-disjoint calibration events, containing 776,742 and 86,353 station records respectively. Checkpoint selection and scheduling use only that calibration partition. It contains only two MA≥5.5 events, so it cannot support extensive tail tuning. The published DEV split is evaluated only after a fixed model has been selected; TEST remains sealed until the comparison and method choices are frozen. The internal TRAIN partition changes the original author's fitting/selection protocol and must be disclosed.

Report all 1/3/5-second mean and posterior-median decisions, MAE, MedAE, RMSE, bias, worst-5% error, magnitude-stratified counts/errors, NLL, analytic mixture CRPS, threshold Brier score and coverage. Comparisons use paired events and identical available waveforms. Inference latency must be measured separately from the observation deadline. A different dataset's headline MAE is not a valid direct comparator.

## Storage and recovery

The dedicated task worker is `i-08b9781ed60d8497f`, currently g5.xlarge with one A10G. The full cache is read-only at `/mnt/eew-data/chile/chile_train_dev_full3000.hdf5`, SHA256 `c59f7c7d2398b453a2aebf29fb713c44ddd0a2376cf2319a99e31ee3bb6c05cb`. Its verified metadata CSV SHA256 is `8840a482419afff5a54681beeb901e5a227e12e64cdf76b1faddf5b3d38285a1`.

Code lives at `/home/ec2-user/eew-work/Earthquake`; pilot checkpoints and logs are under `/home/ec2-user/eew-work/pilot-runs` and `pilot-logs`. Atomic completed-epoch recovery retains optimizer, scheduler, random states, selected model and histories. Resume with the original configuration; a shortened pilot checkpoint is not silently reused as a completed full-budget pretraining artifact.

The worker's verified automatic stop is 10 October 2026 at 19:10:26 UTC, with EC2 shutdown behavior STOP. Reboots require restoring the read-only bind mount and rearming the timer. The rejected L40S upgrade produced no L40S training. The $2,000 credit-only ceiling and 16 G/VT-vCPU quota remain in force; exact settled incremental billing is not yet available.

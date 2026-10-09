# Chile station-cache handoff evidence

The original full-budget TEAM-style run completed two station-pretraining epochs. A read-only independent checkpoint copy was validated and pinned, then only the verified original training process was terminated at 21:13:23 UTC. Its latest published checkpoint matched the safety copy. The unpublished partial third epoch is discarded and will be recomputed from the completed second-epoch state.

The entire 863,095-station TRAIN cache passed bit-preservation checks. The separate CUDA comparison passed on two recorded mini-epochs, with fitting batches [64,64,38], calibration batches [64,17], real full-cohort remainder sizes, and an epoch-boundary restore. It produced identical batch/noise, loss/gradient/update, model/optimizer/scheduler/RNG, and calibration trace hashes. This establishes equivalence for the recorded runtime and bounded subsets, not a universal full-training theorem.

A separate migration checkpoint was prepared without modifying the original run. The resume process launched at **2026-10-09 21:28:57 UTC** with **118,867 seconds** remaining until the original **2026-10-11 06:30:04 UTC** process deadline, plus the original 120-second kill grace. The OS stop remains **2026-10-11 07:28:52.690056 UTC**. Startup validation passed. Epoch3 completed on all776,742 fitting stations:957.694s of training and976.684s including calibration, versus2462.986s/2614.873s total for the earlier epochs. This observed2.52–2.68× throughput improvement compares different epochs; the bounded CUDA proof separately checks identical computations on recorded subsets. Epoch4 is running. TRAIN-internal calibration NLL at1/3/5s is .666563/.625451/.567934; these are training-selection diagnostics, not heldout accuracy.

The raw HDF, checkpoints, proof, migration manifest and cache metadata remain on durable EBS. The mapped waveform cache is disposable instance storage; stopping the worker can erase it, and recovery must preserve the pinned provenance rather than silently rebuilding a different manifest.

| Artifact | SHA-256 |
|---|---|
| Flat cache manifest | d7db84d664f9b8d0e26f9f3623609d2e486744c77cede78ffcb4ba392e1e054e |
| Frozen epoch2 checkpoint | afaeed68a43d4c26199514e70b2d202e22d749f33be4ca562cbe2e6440c892db |
| CUDA proof | 0b78936752a1d2422e0be11fc348786592e5bced12ffa0aba7fabb1a6a9b9b9a |
| Migration manifest | a09b072124cb44b93c56fa65f18164d37c286f88a3f87ba36902d727a6dd9da7 |

Run: `/home/ec2-user/eew-work/full-runs/team_flat_epoch02_20261009T212200Z`.
Log: `/home/ec2-user/eew-work/full-logs/team_flat_resume_epoch02_20261009T212857Z.log`.

Ten focused CPU integration tests and clean Codex review preceded the real-data migration. The original model, trainer, optimization schedule, split, selection rule and epoch budgets are unchanged. The manifest explicitly records the new data backend and implementation identity.

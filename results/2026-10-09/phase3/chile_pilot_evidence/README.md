# Chile TRAIN-only hardware pilots and deterministic launcher

All four bounded A10G pilots completed with exit0. Every pilot used `--skip-dev`; the official TEST data are absent from the verified cache. Training and calibration use disjoint original-TRAIN event partitions. Worker was confirmed idle after the final pilot (0MiB,0%,no training process);21GiB root free. The later synthetic deterministic CUDA smoke also completed with exit0. No full-budget training was launched by this subtask.

Model/trainer source commit`f682100`; deterministic wrapper commit`01023ca`. Runtime: Python3.12.10,Torch2.8.0+cu129,A10G23028MiB,4vCPUs,about15.4GiB RAM. All30 existing CPU tests passed; all6 new launcher tests passed with realTorchCPU. Codex autoreview of only the new launcher/tests was clean, confidence0.96.

The fixed TRAIN calibration set has5,767events/86,353stations. Fit subsets were selected before scores, seed20261009. Shared options: author −4 to +25s cutoffs, author station blinding, train-only label smoothing, magnitude resampling2, TRAIN-calibration NLL scheduling/selection, workers0,FP32. Each invocation had a900s guard plus30s grace; none timed out.

| Case/stage/epoch | Fit events | Presentations | First100(s) | Train(s) | Cal+selection(s) | Peak allocated(GiB) | Peak reserved(GiB) |
|---|---:|---:|---:|---:|---:|---:|---:|
| event16/event/1 | 2048 | 2229 | 40.30 | 45.50 | 44.68 | 8.19 | 10.80 |
| event32/event/1 | 4096 | 4368 | 23.81 | 31.85 | 28.82 | 1.06 | 2.64 |
| event64/event/1 | 8192 | 8715 | 48.93 | 66.18 | 40.32 | 17.75 | 20.43 |
| event64/event/2 | 8192 | 8715 | 26.87 | 36.84 | 22.04 | 16.00 | 20.43 |
| station64/pretrain/1 | 1024 | 15259 | 17.95 | 36.82 | 107.29 | 5.18 | 5.43 |
| station64/pretrain/2 | 1024 | 15259 | 13.66 | 32.39 | 105.02 | 5.18 | 5.43 |
| station64/event/1 | 1024 | 1095 | n/a | 6.21 | 24.28 | 10.27 | 12.42 |

Batch64 retained the full station/calibration protocol and passed twice. Its peak reserved memory was20.43GiB, leaving limited headroom on the22.49GiB device; another GPU process must not share the worker. Shape-dependent convolution workspace behavior is a possible explanation for nonmonotonic batch16/32/64 peaks, not a verified diagnosis.

Full-cache hashing/metadata initialization plus final artifact overhead was roughly198–241s per invocation, except the station invocation also builds its station index. Checkpoints persist independently of the SSH session. Calibration times above are epoch minus training timers and include any selection work before the epoch timer ends; final recovery-checkpoint writes are outside that timer. Six CPU launcher tests ran briefly during the station pilot (3.52s total), so tiny CPU contention is possible.

## Full25+100 budget

| Scaling scenario | Station25(h) | Event100(h) | Total(h) | Compute($) |
|---|---:|---:|---:|---:|
| first_epoch_scaling | 13.76 | 12.73 | 26.49 | 26.65 |
| second_epoch_scaling | 12.18 | 7.08 | 19.26 | 19.37 |

These scenarios are not confidence bounds. Full fitting data contain51,912events/776,742stations and55,053 resampled event presentations. At batch64 this is12,137 station-training batches and861 event-training batches per epoch. Full held-out TRAIN calibration requires1,350 station batches or91 event batches, each evaluated at1/3/5s. The measurements scale those full counts while retaining measured complete calibration cost.

A practical initial envelope is24–36h ($24.14–36.22compute at the parent-verified$1.006/h), within the parent-authorized$60 worker allowance. This excludes storage, the original worker, and idle time. Re-estimate after the first full-data deterministic pretraining epoch. Full TRAIN exceeds RAM, shuffled single-station HDF reads decompress shared chunks repeatedly, and deterministic kernels may have different performance. These effects can exceed the subset-based scenarios. Parent owns the35h process guard/36h OS STOP and final launch.

Two pilot epochs show execution stability and warm-up effects; they cannot establish convergence or justify claims of beating TEAM. Preserve the fixed25+100 training budget and TRAIN-only scheduler/selection. DEV remains untouched until the separately planned final assessment; do not shorten or select the method based on DEV.

## Recovery and encoder reuse

Keep atomic `latest.pth` after every completed epoch. It stores stage, completed epoch, model, optimizer, scheduler, all tracked RNG states, histories and selected-model state. A stop mid-epoch loses at most that uncompleted epoch. Resume with the exact original trainer CLI plus `--resume <original-run>/latest.pth`, through the same deterministic wrapper and a new audit-file path. Do not launch a second writer into that run. Changed code/config/runtime/splits are rejected; GPU bitwise equality across all contexts is not promised.

Preserve `pretrained_encoder.pth` and its manifest after all25 full-fit station epochs, then reuse that exact artifact for matched event-model variants with strict provenance checks. The two-epoch/1,024-event pilot encoder is incompatible with the full25-epoch fit identity and must not substitute for it. Atomic recovery checkpoints overwrite in place; storage does not grow with every epoch. Back up completed-epoch checkpoints/encoder manifests at stage boundaries before changing the worker.

## Deterministic launcher verification

`run_team_deterministic.py --determinism-audit NEW.json -- <unchanged trainer CLI>` sets cuBLAS`:4096:8` beforeTorch import, enables strict deterministic algorithms and cuDNN determinism, disablesbenchmark, and preservesTF32. It prints and exclusively saves wrapper/runnerSHA, settings and forwardedCLI. The unchanged trainer records resulting flags in its own identity. Runtime-control changes do not imply a TensorFlow-equivalent port.

The one bounded synthetic GPU smoke exercised this exact wrapper SHA`d864fa298fccff2b3c1a19804a4815c8eab23c63353173b4db6fd59246fda586` with the productionTEAM model and a temporary synthetic runner, batch2×21stations×3000samples. Station and event forward/backward completed with36 and111 finite gradient tensors; station0.636s,event0.242s. No data were read. This validates supported operations for the exercised shapes; it does not establish fullbatch64 throughput or universal GPU repeatability.

Evidence: `event16.json`,`event32.json`,`event64.json`,`station64.json` contain original logs, configs, memberships and histories; `summary.json` hashes those files; `full_run_forecast.json` contains formulas/scenarios; `deterministic_cuda_smoke.json` contains audit and synthetic results. Original checkpoints remain at the recorded worker run directories.

## Full authoritative baseline and follow-up investigation

Parent launched the full deterministic baseline at19:30:04UTC. Run identity is`team_transformer_06742dc492a1_7ec986ada2e7`, with25station+100event epochs, batch64 at both stages, all author options, TRAIN-calibration selection and DEV only after the complete budget/selection. The audit and initial timing are saved in`full_run_startup.json`; exact unexecuted recovery and pooled-model encoder-reuse commands are in`recovery_and_reuse_commands.md`.

The first100 full-data station batches took22.9586s. Scaling those12,137batches/epoch and retaining pilot calibration time suggests about20.1h for pretraining and27–33h total using the earlier event-stage scenarios. This is a provisional scenario, not a confidence bound; the first completed full epoch and deterministic event throughput remain necessary. Parent authorized a35h process guard and36h OS stop under its$60worker allowance.

`loader_optimization_memo.md` contains the separate read-only CPU/I/O investigation, a2.894s CPU-only512station equality probe, minimal future alternatives, and exact recovery/provenance implications. No live training setting, cache bytes or storage device was changed.

# Independent proper-score artifact audit

Audit only completed `artifacts.json` runs. No training, model selection, TEST discovery or GPU access. CPU environment variables are fixed to one thread. The caller must use `timeout --kill-after=30s 600` on AWS. Reports are written outside immutable training runs.

`audit_scores.py` checks file hashes, source/config identity, all TRAIN-row array digests, train-only marginal weights, event/trace disjointness, validation-reference alignment, checkpoint tensor hashes/architecture/masks/normalizers, paired initial/order traces, seeded CPU permutation replay when Torch versions match, PMF sums and equal-seed ensembles. Every mean/median point metric is independently recalculated; exact discrete-support CRPS is integrated over CDF intervals against continuous target magnitudes. Quantized CRPS, weighted scores, ranked log score, categorical NLL, event-macro error/CVaR and fixed-bin tail calibration are separate readouts. Float32 PMFs receive only a documented tiny mass-roundoff correction. Zero-probability log losses remain explicitly infinite, represented by null mean plus count.

`replay_checkpoint_sample.py` additionally runs all ten saved heads on at most32 deterministically chosen validation records (uniform plus highest-label stress cases). It uses source-pinned feature functions and a separately declared head; this is correspondence checking, not an independent feature implementation or exhaustive inference. Fixed CPU/CUDA numerical tolerances are in the source. Only validation waveform rows are read.

Important limits: frozen backbone and original released-count preprocessing persist; validation was repeatedly reused. Raw recomputed CNN PMFs were not saved, so raw probability scores cannot be exactly audited from the artifact; raw point metrics can. The clipped categorical objective is not the same as continuous-target CRPS, and a score improvement need not lower point MAE or rare-event error. No comparison is selected after seeing validation. Hashes prove consistency with the manifest, not external authenticity.

Run focused tests: `python3 -m unittest discover -s work/proper_score_audit -p test_audit_scores.py -v`. Supply explicit `--run`, `--source-root`, `--reference validation_1s.npz` and `--output` to the main audit. Optional bounded inference requires `--data-root` and `--inventory`. Existing output files are never overwritten.

`replay_gpu_grid.py` is **parent-scheduled only**. It verifies the exact saved Python/Torch/CUDA/cuDNN/device/TF32/determinism identity before work; uses original CNN256 and head2048 batching including real remainder sizes; replays all validation rows for every head; writes a separate PASS/FAIL JSON; and keeps the original numeric thresholds. An external600-second timeout is mandatory. This is not CPU verification and has not been launched by the audit agent.

Exact command pattern on the original instance, after the grid finishes and the parent schedules a free GPU:

```sh
timeout --kill-after=30s 600 env CUBLAS_WORKSPACE_CONFIG=:4096:8 CUDA_VISIBLE_DEVICES=0 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 /home/ec2-user/Earthquake/.venv/bin/python -B -u /tmp/eew_proper_score_audit_20261009/replay_gpu_grid.py --runs /mnt/eew-research/runs/instrument_scores_1s_ed6e8d1cb99d_cf5e44fc7c1e /mnt/eew-research/runs/instrument_scores_3s_091b0511b303_a29c0e7200e8 --source-root /home/ec2-user/Earthquake --data-root /data --inventory /mnt/eew-research/instance/responses.tgz --output /tmp/eew_proper_score_audit_20261009/gpu_replay_1s_3s.json
```

Add the exact completed5-second run directory to `--runs` when available and choose a fresh output file. A nonzero exit is a failed/incomplete audit, not permission to widen tolerances.

Interval diagnostics report **both** continuous magnitude coverage within selected center endpoints and coverage of the clipped categorical bin set actually scored in training. Their difference can be a half-bin representation effect; do not label it entirely miscalibration.

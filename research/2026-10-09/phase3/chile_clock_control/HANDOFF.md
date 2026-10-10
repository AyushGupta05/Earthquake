# Parent launch handoff

Status: source implementation and local synthetic tests only; final review result and exact source-manifest SHA are recorded in `handoff.json` after closeout. No production arrays, GPU jobs or AWS resources were accessed by this agent.

1. Preserve this source/protocol/test/review milestone in Git. Copy only the manifest-listed control files, test/README/HANDOFF and the three exact phase3 dependencies to a fresh directory on the existing task-owned A10G. Put dependencies in `control/dependencies` so synthetic tests can discover them. Keep all production input files and prior outputs unchanged.
2. Verify copied bytes against `source_manifest.json` and its independently supplied SHA. Use `/opt/pytorch/bin/python`, the completed baseline Torch2.8+cu129 environment, not the unrelated original-worker Python3.9 environment. Parent must verify credits, exact worker identity, resource quota, ro cache mount, disk space, no concurrent GPU work, and rearm STOP with the12h outer deadline. This code starts no resources and installs nothing.
3. Run `python -W error -m unittest discover -s CONTROL -p test_clock_control.py -v` under `CUDA_VISIBLE_DEVICES=''`, CPU2, external120s and a dedicated memory-limited cgroup. Require all tests, including synthetic h5py header validation; no skip is a production-ready pass. A documented environment-only warning filter may target an existing dependency warning precisely; do not suppress test warnings broadly.
4. Dry source preflight. Then run the synthetic CUDA mode under timeout120s, kill grace30s, cgroup RuntimeMaxSec270/TimeoutStopSec30/KillModecontrol-group. It reads no production input artifacts. Verify its COMPLETE exact repeated-clock loss/model/Adam/trace checks and non-clock pairing. This proof does not establish full batch64 throughput; batch64 is already the fixed completed baseline setting.
5. Run initial-state first16-fit replay under timeout600s, kill grace30s, cgroup RuntimeMaxSec750/TimeoutStopSec30/KillModecontrol-group. Verify receipt schema, exact source/protocol/checkpoint/reference hashes, allfinite native float32 parameter comparisons, exact event identity digest, optimizer_steps0 and calibration_dev_test_forwards0. Do not proceed if any tolerance fails. No source tuning or widening tolerance based on failure.
6. Launch the four-fit grid serially under the existing owned worker only. Use a fresh output, timeout39600s, kill grace120s, systemd RuntimeMaxSec39840/TimeoutStopSec120/KillModecontrol-group, CPUQuota200%, MemoryMax12G, and a STOP deadline43200s from launch (or earlier remaining approved deadline). The worker itself enforces9000s per fit and36000s aggregate fit budgets. Parent controls durable journal/log retention and checks process/cgroup death on timeout. Do not automatically extend or restart a partial run.
7. Accept results only if final COMPLETE hashes and all four FIT_COMPLETE/final6 identities verify. Independently replay saved metrics and pairing before interpretation. All seeds/deadlines/mean and median decisions remain visible. No calibration/DEV-driven rerun, alternate crop/LR or selected epoch. Model and NPZ outputs/full split/selection rows stay out of Git.

## Exact CLI template

The source manifest SHA in `handoff.json` must be filled from the independent verified handoff, not calculated from untrusted remote bytes and accepted without comparison. `CONTROL` is the parent's fresh deployment directory, `DIAGNOSTIC` is the existing pinned real_v2 output path and `NEW_*` are nonexisting sibling output directories outside all input/source trees. Shell variables here are task-specific, never HOME/CODEX_HOME.

```sh
clock_control=/home/ec2-user/eew-work/CHOSEN_NEW_DEPLOYMENT/control
clock_sources_sha=EXACT_SHA_FROM_HANDOFF_JSON
clock_plan=/home/ec2-user/eew-work/CHOSEN_NEW_DEPLOYMENT/artifact_plan.json
clock_plan_sha=8bb46ac1ae4296a5aa20ab4724491052ec729c96dba04cf2dd7d3656afe5323d

/opt/pytorch/bin/python "$clock_control/run_clock_control.py" \
  --plan "$clock_plan" --plan-sha256 "$clock_plan_sha" \
  --source-dir "$clock_control/dependencies" \
  --source-manifest "$clock_control/source_manifest.json" --source-manifest-sha256 "$clock_sources_sha" \
  --output /home/ec2-user/eew-work/full-runs/NEW_CLOCK_GRID
```

Dry default does not open the paths listed inside the artifact plan. For actual execution use the same required arguments, a different fresh output each time, and these suffixes:

```sh
--synthetic-runtime --max-seconds 120 --execute
--initial-replay DIAGNOSTIC --max-seconds 600 --execute
--max-seconds 39600 --execute
```

These are parent commands to place inside the supervised scopes above, not permission for this implementation agent to launch. The data path remains `/mnt/eew-data/chile/chile_train_dev_full3000.hdf5`; the starting baseline directory remains `/home/ec2-user/eew-work/full-runs/team_flat_epoch02_20261009T212200Z`. No station-pretraining flat cache is needed. The existing baseline artifact plan must remain byte-identical; if paths have actually changed, a separately reviewed path-only deployment plan amendment with the same nine hashes is needed rather than editing baseline artifacts.

The existing diagnostic directory is `/home/ec2-user/eew-work/chile_floor_diagnostic_v2`. The initial reference is fixed to COMPLETE SHA `cea808da6d430263dd1aca8d3b48fc9d59cddda1d9b3b127e57922083d086223` and diagnostics NPZ SHA `d48cb0696e4dfdc2f4164c0b8570b602382cc415292f342834a2233243309439`. The replay validates the diagnostic's original input plan too. Do not substitute a similarly named incomplete first attempt.

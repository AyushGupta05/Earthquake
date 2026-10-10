# Immutable response-grid reporting recovery

This wrapper recovers reporting only after all eight fixed A/B/C/D fits have
completed. It imports the unchanged pinned `train_response_grid.report_grid`.
It does not load model checkpoints, call forward, fit anything, change scoring,
filter report fields, change decisions, or resample observations. Existing
reporter checks of normalizers, schedules, predictions, and row alignment remain
authoritative. Its only report change is the serializer: `json.dump` writes the
same sorted, two-space-indented, ASCII-escaped JSON plus one final LF directly
to a temporary file. This avoids a second whole-report string allocation.

The prior OOM is suspected to have occurred during whole-string serialization;
this is not established. The unchanged report object can still exceed 12 GiB.
Stage and peak-RSS logging distinguishes construction from serialization without
logging performance values. No report contents are omitted to lower memory.

## Frozen inputs and transaction

`recover_report.py` hard-pins the original 41-file deployment manifest, original
five-file training bundle, frozen protocol, and completed export manifest. The
CLI additionally requires the current `training_complete` root manifest SHA and
the exact wrapper SHA. It checks source hashes before importing original modules,
disables bytecode writes in that deployment, hides CUDA, uses two CPU threads,
and verifies all eight fit completions and artifact hashes before reporting.
Original reporter validation is then run exactly once, inside `report_grid`.

Under an exclusive root lock, a new receipt directory saves the exact original
root manifest bytes and SHA. After streaming the report, source/export/fit hashes
are checked again. The root manifest is promoted using exactly the original
successful schema, retaining training_seconds and adding report_sha256. A
separate receipt records recovery provenance and before/after fit hashes; it
never changes the original eight fit directories. Root COMPLETE.json is written
atomically last using the original schema. A receipt is successful evidence only
when its grid manifest SHA matches that root completion marker.

Caught failures leave no root completion marker and restore the exact original
root manifest if promotion had occurred. A kill/OOM can leave a partial report or
a promoted manifest without COMPLETE; such a state is incomplete and requires
inspection. Existing report/partial/completion files are rejected, never quietly
overwritten. Fit artifacts are never modified or deleted. This wrapper does not
promise recovery from a full disk or hard kill via Python exception handling.

## Launch contract (parent owns execution)

Default is dry-run: no source imports, input reads, or writes. Only the parent
may add `--execute` after deploying the reviewed source. Paths below describe
the intended production input, not a job launched by this task.

```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 \
  /home/ec2-user/Earthquake/.venv/bin/python recover_report.py \
  --deployment-root /home/ec2-user/distribution_grids_7204ab1d \
  --export /mnt/eew-research/runs/response_prefix_export_v1 \
  --grid /mnt/eew-research/runs/response_architecture_grid_v1 \
  --receipt-dir /mnt/eew-research/runs/response_reporting_recovery_v1 \
  --grid-manifest-sha256 CURRENT_PARENT_VERIFIED_TRAINING_COMPLETE_SHA \
  --wrapper-sha256 REVIEWED_WRAPPER_SHA --max-seconds 1800
```

The parent must impose the planned task-specific systemd cgroup with 12 GiB,
two CPU threads, and an outer 1800-second hard timeout (plus parent cleanup
margin as appropriate). The wrapper checks elapsed time at stage boundaries;
those checks cannot interrupt the original report function. No GPU or new cloud
resource is needed. Report computation is the original fixed CPU workload.

## Synthetic checks

`python -W error -m unittest -v test_recover_report` verifies byte/semantic
equivalence, no full-string serializer, schema/rollback/missing-fit failures,
no completion after error, artifact identity, safe paths, and dry-run behavior.
`test_original_report_integration.py` additionally imports exact frozen sources
and generates an invented completed export and eight fake prediction artifacts.
No real arrays or model forwards are used. It compares every report byte with
the original serializer and exercises the original prediction alignment guard.

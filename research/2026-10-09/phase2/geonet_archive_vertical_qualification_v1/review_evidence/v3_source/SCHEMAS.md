# Gate and callable schema

`supervisor.supervise(runtime, runtime_sha256, child, child_sha256, supervisor_sha256, plan, plan_sha256, authorization, authorization_sha256, out_dir, max_seconds=120)` launches fresh `-I -B -S` child and returns a private receipt. Runtime is the exact existing venv executable path; its resolved interpreter bytes are hashed. Source and scientific file inventories are verified in the gated child. The supervisor hashes its own source and the child entry buffer before launch. Receipt completion additionally needs successful return, validated bounded result envelope and confirmed entire process-group termination. Parent must verify receipt/hash/return status before interpreting results; a private candidate file alone is insufficient.

CLI: `python supervisor.py --runtime VENV_PYTHON --runtime-sha256 SHA --child ABS_CHILD --child-sha256 SHA --supervisor-sha256 SHA --plan ABS_PLAN --plan-sha256 SHA --authorization ABS_AUTH --authorization-sha256 SHA --out-dir NEW_ABS_DIR`. No actual invocation is authorized by this documentation.

Plan exact fields:

```
protocol_id: "geonet-archive-vertical-qualification-v1"
limits: exact child_harness.LIMITS
source_files: {name: sha256} for exact child_harness.SOURCE_NAMES
slots: exactly four ordered objects:
  slot_index: integer 0,1,2,3
  body_path: canonical absolute regular file path; four distinct literal paths
  body_sha256: lower-case 64-hex
  body_bytes: integer 1..67108864
  expected_nslc: {network,station,location,channel}
  t0_ns: preserved signed integer UTC nanoseconds
  pick_ns: metadata signed integer UTC nanoseconds
  filename_year: integer 1900..2100
  filename_doy: integer 1..366, valid for that year
```

Literal supported miniSEED identity is two upper-case alphanumeric network characters, 1..5 station characters, two location characters, three channel characters ending Z. No rewriting. Unsupported identity is a plan failure. Neither model nor timestamp fields accept bool/float. Timestamp range is signed 64-bit nanoseconds with 10-second arithmetic margin. Unknown/absent original clocks are not substituted; parent must supply independently verified nonnull original clocks for all four slots.

Authorization exact fields:

```
protocol_id: same literal
plan_sha256: externally expected plan SHA
source_files: identical mapping
limits: identical constants
offline_decode_authorized: true
code_only_review_clean: true
focused_tests_passed: true
pushed_source_commit: lower-case 40-hex
source_manifest_sha256: lower-case 64-hex
review_receipt_sha256: lower-case 64-hex
test_receipt_sha256: lower-case 64-hex
```

Parent supplies expected plan and authorization hashes as trusted arguments. Plan does not contain its own authorization hash. No body is read until that authorization and all source/runtime/slot checks pass. Child does not reopen source modules after validation: verified module buffers are compiled directly. Body bytes are read once per object, checked and decoded from BytesIO; no filename/URL is given to ObsPy. Body/hash failure aborts; decode/grid unsupported exceptions produce retained failed slot rows, with no exception text. Memory/deadline failures abort.

Envelope exact keys `{protocol_id, private, public_aggregate}`. Private `slots` retains four ordered rows. Each decoded row contains observed NSLC and rational trace grids, full-object adjacency and day diagnostics, original clock/pick offset, and all three `windows` with exact left/deadline, strict catalogue-pick deadline diagnostic and unchanged core result. Failed objects retain three core `available:null` rows. Successful execution can contain failed scientific diagnostics; complete invocation is not universal qualification. Private provenance binds plan/auth/source commit/source files, validated-body count and successfully decoded advertised sample count.

Public aggregate exact keys are defined by `qualification.aggregate`: slots/decoded/failed/literal-identity/observed-consistent-rate counts, three complete-window counts and filename-boundary trace count, followed by fixed false metadata-rate/partition/response/clipping/3C/operational/model flags. No IDs, NSLC, timestamps, raw samples, body hashes, paths, URLs, warning text, arbitrary error classes or variable-key status labels enter this aggregate. The supervisor's receipt and result pins stay private. Its CLI stdout only reports `complete` and a finite internal `reason`.

`qualification.decode(body, obspy.read, remaining_samples) -> (stream, count, warning_count)`; `qualification.analyze(stream, slot, unchanged_core) -> private decoded row`; `qualification.aggregate(four_rows) -> public aggregate`; `child_harness.run(trusted_args) -> envelope` is a private gated entry used only by the reviewed child/supervisor. Pure analysis callables are tested only on invented streams during preparation.

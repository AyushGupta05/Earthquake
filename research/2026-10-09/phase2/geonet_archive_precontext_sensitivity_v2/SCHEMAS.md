# Gate and callable schema

`supervisor.supervise(runtime, runtime_sha256, child, child_sha256, supervisor_sha256, plan, plan_sha256, authorization, authorization_sha256, out_dir, max_seconds=120)` launches fresh `-I -B -S` child and returns a private receipt. Runtime is the exact existing venv executable path; its resolved interpreter bytes are hashed. Source and scientific file inventories are verified in the gated child. The supervisor hashes its own source and the child entry buffer before launch. Receipt completion additionally needs successful return, validated bounded four-slot/48-cell result and exact aggregate/provenance schema and confirmed entire process-group termination. Parent must verify receipt/hash/return status before interpreting results; a private candidate file alone is insufficient.

CLI: `python supervisor.py --runtime VENV_PYTHON --runtime-sha256 SHA --child ABS_CHILD --child-sha256 SHA --supervisor-sha256 SHA --plan ABS_PLAN --plan-sha256 SHA --authorization ABS_AUTH --authorization-sha256 SHA --out-dir NEW_ABS_DIR`. No actual invocation is authorized by this documentation.

Plan exact fields:

```
protocol_id: "geonet-archive-precontext-sensitivity-v2"
precontexts_seconds: exactly [0,1,3,5], ordered integer list (not bool/float)
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
precontexts_seconds: exactly [0,1,3,5], ordered integer list (not bool/float)
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

Envelope exact keys `{protocol_id, private, public_aggregate}`. Private `slots` retains four ordered rows. Each decoded row contains observed NSLC and rational trace grids, full-object adjacency and day diagnostics, original clock/pick offset, and `precontext_windows` keyed by "0","1","3","5", each keyed by "1","3","5" with exact left/deadline, strict catalogue-pick deadline diagnostic and unchanged core result. `precontext_masks` has the same keys, each value exactly `available` for true, `incomplete` for false or `unknown` for null. `windows` is the exact p=5 legacy-shaped reference view and equals `precontext_windows["5"]`. Failed objects retain all 12 core `available:null` cells and unknown masks, plus the identical legacy p=5 view. The supervisor validates every context/horizon, decoded half-open timestamp and strict pick predicate, mask and p=5 equality. Successful execution can contain failed scientific diagnostics; complete invocation is not universal qualification. Private provenance binds plan/auth/source commit/source files, validated-body count and successfully decoded advertised sample count and the exact `precontexts_seconds` list.

Public aggregate exact keys are defined by `qualification.aggregate`: slots/decoded/failed/literal-identity/observed-consistent-rate counts, three legacy p=5 complete-window counts, `precontext_window_states` and filename-boundary trace count, followed by fixed false metadata-rate/partition/response/clipping/3C/operational/model flags. No IDs, NSLC, timestamps, raw samples, body hashes, paths, URLs, warning text, arbitrary error classes or variable-key status labels enter this aggregate. The supervisor's receipt and result pins stay private. Its CLI stdout only reports `complete` and a finite internal `reason`.

`qualification.decode(body, obspy.read, remaining_samples) -> (stream, count, warning_count)`; `qualification.analyze(stream, slot, unchanged_core) -> private decoded row`; `qualification.aggregate(four_rows) -> public aggregate`; `child_harness.run(trusted_args) -> envelope` is a private gated entry used only by the reviewed child/supervisor. Pure analysis callables are tested only on invented streams during preparation.

`public_aggregate.precontext_window_states[p][h]` has exact keys `{denominator, available, incomplete, unknown, complete_and_catalogue_pick_before_deadline}`. Denominator is always integer 4; three disjoint state counts sum to 4. The last count intersects core availability true with the separately reported strict catalogue pick predicate true; it does not change the mask. Each public integer is exact (bool disallowed). Recursive validation prohibits extra keys at every public nesting level. No context preference or accuracy metric is included.

Processing source allowlist remains the exact seven names `core.py`, `qualification.py`, `child_harness.py`, `supervisor.py`, `PROTOCOL.md`, `SCHEMAS.md`, `RUNTIME_PINS.json`. Fixed numeric limits are unchanged: objects=4, object_bytes=67108864, total_bytes=268435456, object_advertised_samples=16000000, total_advertised_samples=64000000, whole_seconds=120, output_bytes=8388608. No new actual plan or authorization exists in this public source packet.

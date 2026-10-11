# First clean source-only joint adapter

Codex autoreview attempt6 exited0 with findings=[] (confidence0.89).
40 invented tests passed in test_receipt_v6.json. Processing source, tests and
protocol match the reviewed source_snapshot_v6.json byte-for-byte; no further
source edits or reviews occurred. Attempts1–5 and their source snapshots are
retained. Attempt1 completed but helper rejected absolute finding paths; its
raw log and verified fixes are retained, with no valid structured-review claim.

Only the exact current reviewed processing source is eligible for a later actual
gate. Historical review_inputs_v1–v5 are evidence, never fallback implementations.
No actual event inputs or private plans/receipts were read. Frozen algorithm
modules were not imported or executed. Public-only dependency byte hashing
verified every86 producer and34
independent source member against the frozen packets; both remain unchanged.
The source-only mappings are in public_dependency_bundles.json, not authorization.

Parent sequence: independently retest/check this freeze; create the adapter plan
with the same already-fixed six IDs,18paths/pins and original census clocks;
independently validate source mappings/runtime/clock bindings; publish the adapter
source freeze; create separate private authorization binding that plan SHA plus
published commit, source, runtime, tests and clean-review receipt. Native profiles
may be null in the plan and are then safely recognized only after the actual read
gate. No actual read is authorized by this handoff.

The parent invokes only after its gate, using the exact reviewed runtime/source:

```
RESOLVED_PYTHON -I -B ABS_SUPERVISOR \
  --runtime RESOLVED_PYTHON --runtime-sha256 RUNTIME_SHA \
  --child ABS_CHILD_HARNESS --child-sha256 ADAPTER_SHA \
  --supervisor-sha256 SUPERVISOR_SHA \
  --plan ABS_PRIVATE_PLAN --plan-sha256 PLAN_SHA \
  --authorization ABS_PRIVATE_AUTH --authorization-sha256 AUTH_SHA \
  --out-dir ABS_NEW_PRIVATE_OUTPUT
```

Or import the reviewed supervisor and call `supervise` with the same keyword
arguments (`child_sha256` is the adapter digest), default max_seconds=120.
Source schema is SCHEMAS.json. Child invocation is fresh `-I -B -c` executing
its verified source buffer; verified frozen dependency buffers are loaded without
second source reads. Parent output directory must be absent and canonical.

Require normal supervision return / CLI exit0 AND receipt.complete AND correct
private_result hash before considering any public_aggregate for publication.
Failure/interrupt/deadline/unconfirmed group termination stays incomplete. Keep
all actual input/authorization/receipt/projection output private and excluded
from Git/reviewer. Original results and clocks remain untouched.

Full output preserves producer + independent representations and comparisons,
all18 unknown slots, own clocks, original T0 and signed earliest-minus-original
diagnostics. Known clock mismatch flags remain evidence, not forced equality.
Producer guarded recovery is all-network; independent guarded recovery is NZ.
Primary independent QML profile follows producer bound-native-ok policy.
Zero clock mismatches alone does not permit a shared operational clock claim.
There is no recovery, converter, physical, novelty or model-improvement claim.

Limits and cautions are fixed in PROTOCOL.md: max120whole seconds with cleanup
reserved inside;4MiB/body,96MiB total,8MiB child stdout,128KiB stderr; exclusive
outputs, capped stream writes, process-group kill/probe; protected owned receipt
finalization. Buffers have logical caps; no OS RSS ceiling is claimed. Python/OS
scheduling, process creation or disk stalls are not hard-real-time guarantees;
late/unconfirmed cases cannot be promoted. Parent retains independent execution
control, process return, elapsed time, resource and provenance evidence.

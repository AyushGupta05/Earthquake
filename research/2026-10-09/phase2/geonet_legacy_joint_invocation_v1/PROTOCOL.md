# Joint cached representation invocation v1

This is a source-only adapter for one separately authorized, fixed six-event,
eighteen-body post-collection compatibility diagnostic. It does not select events,
request data, change original results or clocks, or implement a magnitude model.
No actual inputs were read to develop or test this packet. The frozen producer V2
and independent semantic V3 remain unchanged. Actual use requires a later pushed
adapter freeze and a separately pinned private parent authorization receipt.

## Authority and input gate

The parent independently verifies the pushed Git commit, clean source-only
review, tests, all public source members, runtime and the original census clock
bindings for all six events. Those are parent assertions, not checks the child
independently repeats. No Git/network API is implemented here.

The plan is pinned first and contains no authorization hash. Authorization binds
that plan, adapter, supervisor, exact runtime, source bundle mappings, review/test
receipts and pushed commit. Trusted invocation arguments supply the plan and
authorization digests plus entry/runtime digests. After verifying them the child
injects authorization SHA into producer provenance. There is no cyclic pin.

Only the parent creates the actual plan and authorization. The supervisor reads
its own source, child source and runtime, then starts a fresh `-I -B` interpreter
in a new process session. It executes the verified UTF-8 child source buffer
through `-c`, rather than reopening the script for execution. The exact runtime
and source files must remain immutable throughout use; this is not an atomic
filesystem or executable replacement defense. The child reads no plan,
authorization, dependency sources or body until its one-byte stdin gate receives
`G`, sent only after the supervisor retains the process handle. EOF fails closed.
A late `Popen` return never releases the gate after the processing deadline.

The child verifies bounded, duplicate-key-free JSON and complete source mappings
before any frozen module execution. Full bundles have exactly 86 producer and
34 auditor public members. Canonical nested relative names are supported without
flattening; absolute/dot/parent/backslash paths and symlink components fail.
The parent supplies the exact frozen allowlists
and mapping digests; the child hashes every listed file, checks the mapping's
authorization binding and independently checks four literal implementation SHA
pins. It does not independently reconstruct the upstream publication allowlist.
It compiles only already verified buffers under producer generic names
`projection`, `comparison`, `shadow` and a distinct independent module name.
Existing names fail the fresh-namespace check. No author code or XML transform
is executed. Source modules are our already reviewed pure implementations.

Six unique raw event IDs, eighteen distinct canonical regular-file paths, exact
body lengths/hashes, valid integer UTC original clocks (or explicit null), and
supported native roots are required. Parent native_profile may be null when no
per-event profile was previously recorded: after authorized body reads the child
recognizes its exact root, supplies that enum to the producer and records the
parent's explicit profile absence. Nonnull requested profiles must match. No
unrecognized root is forced into a default profile. Bodies are read once read-only,
with no-follow final opens and canonical paths. Parent preserves the roster,
source selection, original plan/manifest and census evidence; no replacements
or clock inference are allowed. Original bodies can contain unresolved metadata.

## Independent profiles, semantics and clocks

An independent stdlib root probe recognizes only exact SC3ML namespace/root and
root `version` for 0.10/0.11, rejects DOCTYPE before internal subset processing,
and requires UTF-8 bytes/declaration with no forbidden NUL characters, preventing
UTF-16/32 ASCII/NUL autodetection bypass. It stops at root start. It is not full XML
validation and does not turn unsupported native content into a known projection.
An unsupported producer may withhold its recognized profile. The primary QML
profile supplied to the independent projector follows the producer's actual
native-status-ok binding; independently recognized root alone does not bind it.
The native independent call retains its root profile. No alternative profile
diagnostic is silently substituted.

The adapter calls `shadow.run_shadow` and independently calls V3 `project` and
`compare`. It saves both complete outputs. Unknown representations remain in
all eighteen slots with null clocks, never zero counts. No universal equality
test is claimed: producer guarded recovery counters cover all networks, while
independent guarded counters cover newly accepted NZ references. Unrecognized
native boolean handling, binary-float versus exact-Decimal geometry, and
any-valid versus all-present-aware recorded revision policy remain explicit.

Independent clocks are reconstructed from the independent accepted picks using
aware UTC microseconds, earliest pick per (network,station), NZ subset and strict
`pick_time < anchor + horizon` for horizons 1/3/5. Negative offsets are retained.
Own earliest subset clock and separately supplied original T0 are both retained.
Signed own-earliest-minus-original-T0 values are descriptive observed-subset/
revision diagnostics, not physical or operational first-station timing evidence.
The original T0 is never overwritten. Empty known subsets and unknown coverage
remain distinct through the saved projections and null anchor counts.

For each slot where both projections are known, the entire independently
reconstructed clock dictionary is compared with the producer-reported clock.
Mismatches are counted and preserved privately; they prohibit a shared clock
claim. Even zero mismatches are not independent operational/complete-network
availability proof, so `shared_clock_claim_permitted` remains false. This task
does not declare recovery, converter correctness, novelty or model improvement.

## Bounds, watchdog and outputs

Supervision starts its monotonic deadline before preflight and covers child
imports, source/auth/plan validation, reads, projection, serialization and output
handling. Maximum whole invocation is 120 seconds. Three seconds (or one quarter
of a shorter synthetic limit) are reserved inside it for termination and final
handling. Processing stops at the earlier deadline. OS scheduling, stalled
process creation or denied signals cannot be made hard-real-time by Python;
late/unconfirmed cases remain incomplete and retain elapsed time.

Limits: plan 1 MiB; authorization 64 KiB; individual body 4 MiB; total bodies
96 MiB (eighteen individual caps further imply at most72 MiB); source member
2 MiB and each source bundle16 MiB; supervisor's child entry64 KiB; runtime
hash read128 MiB. Child stdout/private JSON envelope is at most8 MiB including
newline; stderr is separately bounded128 KiB; public aggregate copy at most64
KiB. Streaming stdout/stderr writes cap retained partial files. Serialization
accumulates only capped result bytes. These are logical input/buffer/output
bounds, not an OS RSS ceiling for frozen XML/parser/projector working objects.
No hard process-memory-limit claim is made.

The supervisor never uses unbounded `communicate`. Deadline, output overflow,
child failure or exception kills the entire child process group. It waits for
the leader and probes group disappearance. Permission denial, surviving group,
or inability to confirm disappearance means incomplete; receipt is not proof of
termination in that case. Partial stdout/stderr remain privately preserved.
Receipt records reason, elapsed time, return code, gate state, byte counts and
termination confirmation. Existing/symlink output directories fail before
launch. All outputs use an exclusive fresh directory and exclusive opens.
The first receipt is always incomplete until its write/close succeeds. Protected
finalization rechecks elapsed time after receipt I/O; an overrun or interruption
finalizes only its own inode-verified receipt as incomplete before propagation.
It never updates a replaced
receipt or a previous invocation's directory. OS I/O stalls can exceed the limit,
but cannot leave that returned completed result eligible for publication.

A complete child envelope has only `protocol_id`, `private`, `public_aggregate`.
On successful exit, bounded valid JSON, confirmed group termination and time
remaining, the supervisor saves private_result.json plus public_aggregate.json
and receipt.json. A public aggregate is eligible for parent publication only if
supervision returned normally (CLI exit0) AND the receipt says complete; the parent
must check both. A persisted candidate alone is never authority. If interruption
also prevents receipt invalidation, lack of normal completion still prohibits
publication. Any later write/receipt limit failure retains it as
an incomplete candidate. Raw identities, all projections, coordinates, body
paths and authorization details belong only in private output/inputs. The
public aggregate has counters/claim limits only. Parent independently checks
receipt/result hash and excludes all actual inputs, receipts and private output
from review/Git. Failed invocation cannot be resumed or promoted by this code.

## Callable and invocation

`supervisor.supervise(runtime, runtime_sha256, child, child_sha256,
supervisor_sha256, plan, plan_sha256, authorization, authorization_sha256,
out_dir, max_seconds=120)` returns the private receipt dictionary. `out_dir`
must not exist. Parent may import this reviewed source before the actual gate;
all child imports are covered by its supervision. The source CLI offers these
same required arguments, with default120seconds. It emits only completion/reason
and exits0 only when receipt complete. See SCHEMAS.json for exact private inputs.

```
PINNED_PYTHON -I -B supervisor.py --runtime RESOLVED_PYTHON \
  --runtime-sha256 RUNTIME_SHA --child ABS_CHILD_HARNESS \
  --child-sha256 ADAPTER_SHA --supervisor-sha256 SUPERVISOR_SHA \
  --plan PRIVATE_PLAN --plan-sha256 PLAN_SHA \
  --authorization PRIVATE_AUTH --authorization-sha256 AUTH_SHA \
  --out-dir ABS_NEW_PRIVATE_OUTPUT
```

Invented tests cover gating, source/input pins, unknowns, exact root profiles,
strict clock edges/negative offsets, policy scope retention, known clock mismatch,
timeout/group signaling, output overflow, failed launches and exclusive outputs.
They use synthetic pure-interface stubs, not imports of either frozen scientific
implementation. Parent owns the later actual integration call after the freeze.
The separate public_dependency_integration_check.json additionally validates exact
frozen manifest/allowlist pins and all120 source members through the adapter's
source-bundle reader, without importing/executing either frozen algorithm or
reading any event metadata/body/private plan. public_dependency_bundles.json is
a source-only mapping usable for the parent-built plan, not authorization.

# Conditional ENZ qualifier V3 source handoff

The exact thirteen-file candidate reached its first clean default Codex review on attempt 4, exit 0 and findings=[]; `REVIEW_RECEIPT.json` binds it. Source, tests and protocol were frozen immediately with no subsequent processing edits or review. `reviewed_source_v4/` is the byte-identical source-only copy. Forty-four invented tests passed in 4.841 seconds (`TEST_PROOF.json`, `tests_v9.txt`), including twelve invented miniSEED bodies through the fresh supervised runtime. Reviewer inspected tests without executing them.

This is source preparation only. No actual metadata, key, body, plan, receipt, result or credential was read; no actual invocation, acquisition, AWS action, fitting, installation or shared Git operation occurred. The required complete-eight V5 transport and new receipt-auditor V4 gate has not been established by this packet. Do not invoke it without every original prerequisite; no alternate gate or subset is provided.

## Fixed source and contract

Protocol `geonet-archive-enz-precontext3-qualification-v3`; exact precontext 3 seconds, horizons 1/3/5 seconds, four ordered unchanged parent-fixed slots, literal E/N/Z components. Retain all 36 component and 12 joint cells. Joint availability requires all three components available, one exact rational observed rate and compatible rational lattices. Original reference and catalogue-pick clocks are preserved; catalogue pick-before-deadline is a separate strict comparison, including negative pick offsets. No clock substitution or inferred receipt timing.

`SCHEMAS.md` contains exact plan, authorization and output fields. The actual source map has exactly eight names: core.py, qualification.py, child_harness.py, supervisor.py, PROTOCOL.md, SCHEMAS.md, RUNTIME_PINS.json, PUBLIC_TRANSPORT_PROPOSAL.md. `handoff.json` provides their hashes. Tests, prompt and byte-exact V2 reference are review context, outside the processing source map.

Unchanged core SHA-256 `70c2a53c7beef5f1ddfae7d46e52bcdae97ee711cd10636da6250bd20ab9144e`; unchanged science runtime inventory SHA-256 `a5a273ffad973848521d08bb5b730fe226c7a45440c298ac25e20624a158c9f6`; exact normative root V5 proposal SHA-256 `9db9d9a06d0ae5c01740b5e5c7befd96a1c34e8b7eef9527639f70b4d4538bb4`. The V2 Z/context-3 reference parity is tested on ten invented pathologies and the failed-cell case; it is not an actual replay.

## Gate and execution interface

Parent must verify the same fixed metadata/body/clock custody, all eight NEW V5 transfers and independent NEW receipt-auditor V4 passing all eight, original Z/V2 source/body/result custody, exact runtime/source pins, successful review/tests and pushed source publication. The failed old transport V4 gate is never substituted. Pin the exact four-slot/twelve-body plan first; its prerequisite pin object contains the V5 protocol/study/proposal plus collection manifest, returned summary, independent audit, vertical V2 result and parent metadata-custody hashes. Authorization separately binds that plan, exact source/prerequisite/limit mappings, pushed commit and source/review/test closure pins, with all required true assertions. No authorization hash is inserted into the plan, avoiding a circular pin. The child checks binding/schema equality; parent verifies documentary truth outside the child.

Callable:

```
supervisor.supervise(runtime, runtime_sha256, child, child_sha256,
                     supervisor_sha256, plan, plan_sha256,
                     authorization, authorization_sha256,
                     out_dir, max_seconds=120)
```

The supervisor CLI uses the same names prefixed by `--`, with underscores changed to hyphens; out-dir must be new, canonical and exclusive. Tests can be rerun using the existing runtime:

```
work/geonet_waveform_feasibility/.venv/bin/python -I -B work/geonet_archive_enz_precontext3_qualification_v3/run_tests.py
```

Actual startup is fresh `-I -B -S` from the verified entry buffer, gated after the supervisor retains its process handle. Source buffers and the full 7,448-file scientific inventory are verified before waveform reads; site startup, .pth and current-directory import behavior stay disabled. Existing Python 3.14/ObsPy runtime only; no full standard-library hash inventory or hard RSS guarantee is claimed.

Limits remain 12 objects, 64 MiB each and 768 MiB total input, 16,000,000 advertised samples per object and 192,000,000 total. Head-only checks precede each full decode; objects are decoded sequentially, with header/full count/grid/dtype agreement. Float64 payload may total 1.536 GB across the advertised sample cap; this is not a hard RSS limit. Whole supervised invocation including reads/imports/processing/output is capped at 120 seconds, stdout 8 MiB, stderr 128 KiB. Group timeout/overflow termination and exclusive incomplete receipts are retained. OS scheduling/uninterruptible I/O cannot provide a mathematical wall-return guarantee; uncertain/late cleanup never qualifies completion.

Normal output retains private_result.json, bounded stderr.part and private receipt.json; only independently schema-checked count fields are written to public_aggregate.json. Failure preserves capped partial stdout/stderr and an incomplete receipt. Completion requires successful normal process return, timely receipt and result/member hash checks and confirmed whole-group termination. Scientific incomplete/unknown cells do not by themselves invalidate a correctly completed diagnostic. The supervisor independently replays retained summary geometry and counts for qualified/incomplete states, but not amplitude finiteness.

## Evidence and limits

`COALESCENCE_EVIDENCE.json` retains a meaningful invented counterexample: concatenated 100 Hz records separated by a 5 ms phase offset are coalesced by this pinned ObsPy read into one returned trace whose decoded grid passes; the same uncoalesced pieces fail the unchanged core. Genuine 10 ms gap/overlap fixtures remain rejected. No wrapper merge, padding, interpolation, deduplication, append, response correction or repair occurs, but library coalescing is possible. This is decoded returned-trace qualification; raw_record_timing_verified and raw_record_segmentation_verified are explicitly false. Filename-day crossing remains descriptive, with partition unverified. Metadata rate, physical orientation/units/clipping, instrument response/state, calibrated motion, operational availability, model input and model improvement remain unverified.

All reviewer attempts are retained. Attempt 1 produced two accepted guard findings but the helper failed path validation, with raw structured engine result and infrastructure receipt preserved. Attempts 2 and 3 added verified NSLC/schema and clock-range guards. Negative reproductions, source snapshots, every test output and the initial failed coalescence assumption remain in the allowlist. No claim of novelty, data feasibility success or benchmark improvement follows from this source packet. `safe_to_promote_paths.json` is the exact closed public allowlist; initialized review Git, actual/local-run artifacts and external source downloads are excluded. Parent owns any publication or later authorization.

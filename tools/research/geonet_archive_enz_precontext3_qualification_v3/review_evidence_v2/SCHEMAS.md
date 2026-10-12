# Fixed ENZ plan, authorization and callable schemas

Protocol `geonet-archive-enz-precontext3-qualification-v3`. Call `supervisor.supervise(runtime, runtime_sha256, child, child_sha256, supervisor_sha256, plan, plan_sha256, authorization, authorization_sha256, out_dir, max_seconds=120)`. The unchanged CLI accepts `--runtime --runtime-sha256 --child --child-sha256 --supervisor-sha256 --plan --plan-sha256 --authorization --authorization-sha256 --out-dir`. Fresh canonical exclusive output directory only. None of this is actual execution authority.

Plan exact fields:

```
protocol_id: exact new literal
precontext_s: exact integer3, rejecting bool/float/omission
limits: exact child_harness.LIMITS key/value mapping; every value exact int (no float/bool)
source_files: exact eight-entry {name:lower-case64hex}
prerequisites: exact object described below
slots: exactly four ordered:
  slot_index: exact integer0..3
  t0_ns,pick_ns: preserved signed integer UTC nanoseconds
  filename_year: integer1900..2100
  filename_doy: calendar-valid integer1..366
  components: exactly E,N,Z, each:
    body_path: canonical absolute regular cached file path
    body_sha256: lower-case64hex
    body_bytes: exact integer1..67108864
    expected_nslc: exactly {network,station,location,channel}
```

All12 paths distinct; all12 validated canonical before waveform reads, actual regular-file/cap checks use descriptor-level bounded reads. NSLC literal supported shape: network2 uppercase alphanumeric, station1..5, nonblank location2, channel2-character prefix plus the exact E/N/Z suffix. Network/station/location/prefix match across all three in each slot. No rewriting or alias. Clocks signed64-bit with10s arithmetic margin; null, floats/bools and substitution are rejected. No independently expected rate field exists.

Exact `prerequisites` fields:

```
transport_protocol_id: geonet-anonymous-archive-transport-v5
transport_study_id: geonet-configured-eight-horizontal-precontext3-transport-v5
transport_proposal_sha256:9db9d9a06d0ae5c01740b5e5c7befd96a1c34e8b7eef9527639f70b4d4538bb4
v5_collection_manifest_sha256:lower-case64hex
v5_returned_summary_sha256:lower-case64hex
independent_v4_audit_sha256:lower-case64hex
vertical_v2_result_sha256:lower-case64hex
parent_metadata_custody_sha256:lower-case64hex
```

These are expected documentary pins supplied and verified by parent, not evidence read/certified by child. Parent must establish complete eight V5 transfers, independent receipt auditorV4 passing eight, original Z/V2 body-clock/source/result custody and same fixed metadata. Do not confuse new receipt auditorV4 with the failed old transportV4 gate. Plan is pinned first; no authorization SHA within plan.

Authorization exact fields:

```
protocol_id: same new literal
precontext_s: exact integer3
plan_sha256: externally expected planSHA
source_files,limits,prerequisites: identical plan mappings
pushed_source_commit:lower-case40hex
source_manifest_sha256,review_receipt_sha256,test_receipt_sha256:lower-case64hex
offline_decode_authorized,code_only_review_clean,focused_tests_passed:true
v5_transfer_all_eight_complete,independent_v4_all_eight_passed,parent_fixed_bindings_verified:true
```

All booleans must be true, not1. Parent independently verifies documentary truth/Git/publication and provides trusted plan/auth/runtime/entry/supervisor SHA arguments. No real authorization is supplied here. Child verifies exact pin/schema equality; false/missing prerequisite assertions fail before data reads.

Eight processing source names: `core.py`, `qualification.py`, `child_harness.py`, `supervisor.py`, `PROTOCOL.md`, `SCHEMAS.md`, `RUNTIME_PINS.json`, `PUBLIC_TRANSPORT_PROPOSAL.md`. The last is the exact normative root proposal copy. Core/runtime/proposal hashes also have hard fixed gates. `qualification_v2_reference.py` is byte-exact testing/review context only; exclude it and tests from actual source mapping. Fixed LIMITS: objects12; object_bytes67108864; total_bytes805306368; object_advertised_samples16000000; total_advertised_samples192000000; whole_seconds120; output_bytes8388608. Stderr bound131072. Runtime/source inventories and original startup/control machinery are described in PROTOCOL.md.

Envelope exact keys `{protocol_id,private,public_aggregate}`. Private exact keys `{slots,provenance}`. Slots4ordered, each exact keys `{slot_index,precontext_s,preserved_t0_ns,metadata_pick_ns,pick_minus_t0_ns,catalogue_pick_before_deadline,components,joint_windows}`. Catalogue map h="1","3","5" strict booleans. Components map E/N/Z contains a decoded or failed row and three `windows[h]`. Decoded rows retain literal identity/rate flags, observed exact rational rate `{numerator,denominator}` or null, all returned-trace summaries, object grid/day flags, same original clocks, head/full advertised samples/warning count and core windows. Each known component window has exact `{left_ns,deadline_ns,target_pick_strictly_before_deadline,core}`. Failed rows exactly `{slot_index,status:"failed",reason:"decode_or_grid_unsupported",windows:{h:{core:{available:null}}}}`; clocks and separate pick booleans still retained by parent slot row. An object failure never removes slots/cells.

Joint `joint_windows[h]` exact fields: `{left_ns,deadline_ns,available,mask,reason,common_observed_rate,lattices_compatible}`. Available true/false/null maps to available/incomplete/unknown. Reasons finite literals `qualified`, `component_incomplete`, `component_unknown`, `mixed_component_rates`, `common_lattice_mismatch`. Common rate/lattice fields null when incomplete/unknown prevents the common-grid check; if all components pass same exact rate, report rational common rate and bool lattice compatibility. This is arithmetic compatibility, not calibrated physical clock/orientation proof.

Private provenance exact `{plan_sha256,authorization_sha256,source_files,pushed_source_commit,validated_body_count:12,advertised_samples_decoded,precontext_s:3,prerequisites}`. Successfully decoded count includes an object later unsupported in analysis and stays ≤192M. Body/hash failures abort; unsupported valid bodies produce scientific unknowns. Completion means verified bounded execution, not all scientific cells available. Parent verifies return, private receipt, result/member hashes and complete confirmed group termination before interpretation.

`public_aggregate`: fixed slots4/objects12, decoded/failed/literal-identity/consistent-rate object counts, `component_window_states[E|N|Z][h]` and `joint_window_states[h]`. Each state object exactly `{denominator:4,available,incomplete,unknown,complete_and_catalogue_pick_before_deadline}`; states partition denominator4. Separate `catalogue_pick_before_deadline_counts[h]` counts allfour parent-fixed picks independent of decode/grid status. Add filename-boundary trace count and fixed false metadata-rate/filename-partition/physical-orientation/physical-units/response-calibration/response-state/clipping/calibrated-three-component-motion/raw-record-timing/raw-record-segmentation/operational-availability/model-input/model-improvement flags. Public extra keys, IDs, NSLC/timestamps/samples/paths/URLs/body or source pins/warning text/private errors are forbidden. Supervisor replays qualified rational timing/count geometry from retained trace summaries, reconstructs joint decisions, recomputes exact counts and enforces exact types recursively. Trace summaries do not contain amplitudes and cannot independently revalidate finiteness. Its own CLI stdout reports only complete/reason; receipt/provenance remain private.

Pure callables: `decode(body,read,remaining_samples)->stream,count,warning_count`; `analyze(stream,flat_slot,unchanged_core)->component_row`; `failed(index,reason)->unknown_component`; `make_slot(parent_slot,components,core)->slot_row`; `aggregate(four_slot_rows)->public_counts`. `child_harness.run(trusted_args)` reads only after gate. Source preparation/tests call these only on invented inputs.

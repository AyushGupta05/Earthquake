# Exact public V6 plan and accounting schema

Authored generic contract only: no actual plan, keys, IDs, clocks, XML, bodies, receipts, inventory or credentials. JSON is UTF8; duplicate keys and nonfinite constants are rejected. Original plan bytes, including formatting, are SHA256-bound. Numbers below are strict integers where identified; clocks are finite JSON-round-tripped monotonic numbers with no epsilon.

## Immutable plan

Exactly eleven top-level fields, byte length1–16,384:

- `protocol`: `geonet-anonymous-archive-transport-v6`.
- `study_id`: exact production `geonet-configured-two-numbered-horizontal-precontext3-transport-v6`, or invented fixture ASCII `[a-z][a-z0-9-]{0,63}` starting `invented-`.
- `proposal_sha256`: `9958454926c5d90b8084c862bd117adda4b306e88d7ad35a13af997920f0d229`.
- `template_source_sha256`: `3194fa79e8993b99f0514239d7735dc4461b9d31aefd031b2f43e725612b6412`.
- `mapping_status`: `unverified_hypothesis`.
- `transport_hypothesis`: `anonymous_official_configured_literal_key_gets`.
- `uncertainty_evidence_sha256`: `d3f826d1b1e45c59fdd5760dc3b5e9f0a8e954a60c2ec7ee628e80031462ec74`.
- `preregistration_sha256`: lowercase64-hex parent document SHA.
- `precontext_s`: exact JSON integer3, excluding booleans/floats/strings/null/aliases/omission/other integers.
- `prerequisites`: the exact fifteen-pin object below; each value is a lowercase64-hex string.
- `slots`: exactly two ordered objects with `slot_id:"numbered_1"`, then `slot_id:"numbered_2"`.

Prerequisite pin fields (no extra/missing field):

```text
v5_collection_manifest_sha256
v5_execution_summary_sha256
v5_independent_audit_sha256
v5_parent_custody_sha256
v4_qualification_result_sha256
v4_parent_custody_sha256
cached_channel_audit_result_sha256
cached_channel_parent_custody_sha256
original_selection_sha256
original_vertical_p3_result_sha256
fixed_positional_join_sha256
numbered_literal_epoch_binding_sha256
independent_auditor_source_manifest_sha256
independent_auditor_review_receipt_sha256
independent_auditor_test_proof_sha256
```

Each slot has exactly `slot_id`, `key` (non-null literal string), `unavailable_reason:null`, `uncertainties` (exact ordered array `["utc_filename_partition","channel_key_identity","location_key_encoding","endpoint_key_correspondence"]`). Null/unavailable/duplicate keys and any wrong order or suffix are rejected. Both literal keys must have identical all-other configured fields and channel prefix; their channel suffixes are respectively1/2. Full experimental syntax:

`waveforms/miniseed/[yyyy]/[yyyy].[doy]/[SITE].[NC]/[yyyy].[doy].[SITE].[LC]-[CHA].[NC].D`

YEAR is four digits with Gregorian range1–9999; DOY is repeated valid three-digit day for that year; SITE repeated3/4 uppercase ASCII alphanumeric; NETWORK repeated2; nonblank LOCATION independent2; CHANNEL3 uppercase ASCII alphanumeric with the required1/2 suffix. No case/space normalization, blank alias, E/N rewrite, wildcard, query/path field, alternative key or semantic/inventory assertion. These restrictions are experimental syntax, not proof of actual formatter/deployed holdings or physical axes. Original event, role, clock, membership and all-prior-key distinctness remain private parent assertions.

## Production constants and output claims

`limits` exactly `{connection_s:10.0,first_body_s:20.0,request_s:45.0,start_spacing_s:1.0,no_new_after_s:75.0,transfer_stop_s:105.0,run_s:120.0,per_body_bytes:67108864,total_body_bytes:134217728}`. Byte fields are strict JSON integers; time fields are finite numeric values with these exact values. Invented fixtures have `fixture:true` and explicit shortened valid limits; they cannot qualify as actual archive execution.

`claims`: exactly seven strict booleanfalse fields `semantic_mapping_verified`, `utc_filename_basis_verified`, `channel_key_identity_verified`, `location_key_encoding_verified`, `endpoint_mapping_verified`, `waveform_coverage_verified`, `failed96_repaired`. `request_policy`: exactly `method:"GET"`, `endpoint:"https://geonet-open-data.s3.ap-southeast-2.amazonaws.com"`; strict booleanfalse `redirects`, `retries`, `head`, `listing`, `auth`, `requester_payer`, `fallback`. Fixtures require canonical numeric-loopback `http://127.0.0.1:PORT` only, port1–5digits and valid parsed port, no auth/path/query/fragment.

## Private saved members

Fresh exclusive directory contains original `roster.private.json`, `initial.private.json`, finalized `000.slot.private.json` and `001.slot.private.json`, zero to two original-index `NNN.body.private` members, `receipt.private.json`, `manifest.private.json`. Error/empty/partial files are retained if created; nothing is resumed/repaired/replaced. Safe manifest-member pin exactly `{name:string,bytes:nonnegative strict integer,sha256:lowercase64-hex}`. Final manifest exactly `{protocol:V6,members:list}` with unique names, roster/initial/two journals/final receipt/every created body, excluding itself:5–7 members. Full filesystem membership is parent-verified separately. External returned `manifest_sha256` binds exact manifest bytes.

Initial receipt exact fields: `protocol`, `study_id`, `plan_sha256`, `complete:false`, `fixture:boolean`, `limits`, `mapping_status`, `transport_hypothesis`, `template_source_sha256`, `uncertainty_evidence_sha256`, `preregistration_sha256`, `claims`, `run_begin:number`, `request_policy`, `slots`. Two ordered initial rows exactly `{slot_id,status:"unattempted",uncertainties}`. Context/prerequisite object remain bound by original plan SHA; no new output field is added.

Final receipt adds exactly `attempts:strict integer`, `consumed_upper:strict integer`, `observed_body_bytes:strict integer`, `all_slots_transport_pass:boolean`, `elapsed_s:number`, replacing `complete` and `slots`. Each journal must equal its final row. Every row has exact `slot_id`, original `key`, original `uncertainties`, plus either:

- `status:"unattempted"`, `reason:"new_request_deadline"|"total_body_cap"`.
- `status:"attempted"`, consecutive zero-based strict integer `request_index`, and all exact result fields below.

Unavailable/shared rows are invalid V6 even though unreachable inherited controller branches remain. Denominator is always two; never remove failed/unknown/unattempted rows.

Attempt result fields: `start:number`, `connected_at:number|null`, `headers_at:number|null`, `first_body_at:number|null`, `end:number`, `http_status:strict integer|null`, `declared:nonnegative strict integer|null`, `outcome:string`, `consumed:nonnegative strict integer|null`, `body:member-pin|null`, `observed_bytes:nonnegative strict integer`, `consumed_upper:nonnegative strict integer`, `consumption_exact:boolean`, `receipt_verified:boolean`, `worker_exit_confirmed:true`, `transport_pass:boolean`. A missing body means null pin and zero observed bytes. Writer exit must be confirmed before pinning any body; failure prevents final accounting. The body name must match that slot's original index and retained bytes/hash.

Outcomes: `body_complete`, `empty_body`, `incomplete_body`, `body_cap_boundary`, `declared_size_rejected`, `invalid_content_length`, `worker_exit`, `body_receipt_mismatch`, `connection_deadline`, `first_body_deadline`, `complete_deadline`, `transfer_deadline`, or `worker_error_` plus exception class name. No raw error/header/URL text is stored.

## Exact arithmetic and finalization

All clocks use one host/boot monotonic domain; not UTC/event/P clocks. Present connected/header/first-body values must be ordered between start/end. Starts≥begin and strictly<begin+75; successive attempted starts differ≥1. End≥start,≤begin+saved-final-elapsed and≤returned_at. Saved final elapsed≥0 and≤outer elapsed. Exact returned `elapsed_s=returned_at-begin`; no tolerance.

Per-attempt allowance=min(67,108,864,134,217,728 minus earlier charged upper bounds). Observed≤charged-upper≤allowance; every present consumed≤allowance. `receipt_verified=consumption_exact`. Exact rows require consumed=observed=upper, including zero-byte size/error outcomes. Nonexact rows charge the full allowance even if a consumed count exists. Aggregate sums count attempted rows only once. At most two requests, one per distinct literal key; no repeated or replacement attempt. A cap/deadline unattempted row prevents complete.

Independently replay `transport_pass`: nonempty pinned body, consumption exact/receipt verified, confirmed writer exit, HTTP200, `body_complete`, connection≤start+10, first body≤start+20, end≤start+45 and≤begin+105. Failing/late/HTTP404 rows remain nonpassing; exit-confirmation cleanup may use only the whole120-second budget. Complete error bodies count toward limits but never establish scientific absence/coverage.

`complete` exactly absence of unattempted rows; `all_slots_transport_pass` conjunction over both fixed rows. Callable returned summary exact finalized fields: `result:"finalized"`, matching strict `complete`/`all_slots_transport_pass`, `manifest_sha256`, `mapping_status`, false `claims`, `begin`, `returned_at`, `elapsed_s`. Failed `controller_failed`/`run_deadline` returns are always incomplete/nonpassing and may lack digest; deadline failure can preserve digest. Qualifying actual finalization requires normal outer return and elapsed≤120, matching saved flags/manifest and separately parent-pinned returned bytes. A saved earlier receipt timestamp alone does not prove whole finalization. Missing/mismatched/failed evidence never qualifies.

## Separate authority and scientific separation

`ActualInvocationGate` exactly: `plan_sha256`, `reviewed_source_sha256`, `reviewed_test_sha256`, `reviewed_protocol_sha256`, `source_manifest_sha256`, `review_receipt_sha256`, `pushed_freeze_commit`, `authorization_reference`, `mapping_status`, `uncertainty_evidence_sha256`, `preregistration_sha256`, `hypothesis_preregistered`, `uncertainty_acknowledged`, `actual_acquisition_authorized`, `prerequisites_sha256`, `prerequisite_assertions`. Source/test/protocol local bytes are checked; other documentary facts are independently verified by the parent. Pins are lower64hex, commit lower40hex, authorization reference ASCII letter/digit first followed by max255 allowed letters/digits/space/dot/underscore/colon/slash/hyphen. Existing three booleans must be stricttrue. `prerequisites_sha256` hashes sorted compact UTF8 prerequisite-object JSON plus one newline. Ten assertion fields, no extras/missing, all stricttrue:

```text
v5_terminal_accounting_complete
v4_joint_outcome_verified
cached_channel_positive_custody_verified
original_unknown_slot_join_verified
original_vertical_p3_grid_verified
numbered_literal_epoch_bindings_verified
keys_distinct_from_prior_requests_verified
independent_auditor_clean_review_verified
independent_auditor_focused_tests_passed
independent_auditor_published_freeze_verified
```

Assertions do not certify calibration/orientation/clock/model gains. Parent must preserve complete V5 six-success/two-failure terminal accounting, V4 three-available/one-unknown per horizon, cached four positive documents with one supported1/2/Z slot, positional identity to the original unknown slot, original Zp3 grids, literal/epoch bindings and full source/result/member custody. Collector/fixture source cannot read those actual facts. No actual invocation is granted here, and no decoder is part of V6.

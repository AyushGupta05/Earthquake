# Public V4 configured-key plan and unchanged accounting contract

This schema contains no actual plan, keys, IDs, bodies or receipts. All hashes below describe generic source/evidence pins or field types. JSON is UTF-8; duplicate keys and nonfinite constants are rejected. Public metadata must not contain actual output members. Actual member/returned-summary custody is parent-owned and private.

## Plan bytes

Exactly nine top-level fields, at most 16,384 bytes:

| Field | Type / exact rule |
|---|---|
| `protocol` | string `geonet-anonymous-archive-transport-v4` |
| `study_id` | production: exact `geonet-configured-eight-horizontal-transport-v4`; invented fixtures: `invented-` prefix and ASCII `[a-z][a-z0-9-]{0,63}` |
| `proposal_sha256` | string `6283180bd493d2846e08b866ade3910afe2896ceea27ad3b309e21460b7d1a0a` |
| `template_source_sha256` | string `3194fa79e8993b99f0514239d7735dc4461b9d31aefd031b2f43e725612b6412` |
| `mapping_status` | string `unverified_hypothesis` |
| `transport_hypothesis` | string `anonymous_official_configured_literal_key_gets` |
| `uncertainty_evidence_sha256` | string `d3f826d1b1e45c59fdd5760dc3b5e9f0a8e954a60c2ec7ee628e80031462ec74` |
| `preregistration_sha256` | parent document pin, lowercase hexadecimal string of length 64 |
| `slots` | exactly eight objects, ordered `ordinary_e`, `ordinary_n`, `higher_e`, `higher_n`, `boundary_e`, `boundary_n`, `final_e`, `final_n` |

Each slot has exactly `slot_id` (the ordered string), `key` (literal string or null), `unavailable_reason` (null for a string key; otherwise ASCII `[a-z][a-z0-9_]{0,63}`), and `uncertainties`. The latter is exactly this ordered string array in **every slot**:

```json
["utc_filename_partition","channel_key_identity","location_key_encoding","endpoint_key_correspondence"]
```

Literal keys must match the official configured-order hypothesis: year four digits, repeated year/DOY/site/network fields consistent, Gregorian year 1–9999 with valid three-digit DOY, site 3/4 uppercase ASCII alphanumeric characters, network/location 2, channel 3 with terminal E/N matching the role. E/N suffixes are literal hypotheses, not physical orientation or inventory evidence. The path is `waveforms/miniseed/[yyyy]/[yyyy].[doy]/[SITE].[NC]/[yyyy].[doy].[SITE].[LC]-[CHA].[NC].D`. Filename final NC repeats directory NC; LC is independent and precedes the hyphen. These shape restrictions are experimental syntax; no UTC/day/content/channel/LC/endpoint verification occurs. Blank LC, aliases, extra query/path fields, `day_basis`, `mapping_verified`, metadata inventory assertions and alternate-key lists are outside the contract. Plan SHA is over original bytes, not a reserialized equivalent.

The nine-field plan and per-row accounting shapes are unchanged from V3. V4 changes protocol/proposal/study identity, exactly eight ordered E/N roles, terminal E/N role matching and the aggregate cap to 512 MiB. Source/template/uncertainty/hypothesis pins and all other controls remain unchanged. The raw config SHA is the `template_source_sha256`, while authored template-profile SHA `7031bb9cdb97d1c1463bd0b2f8527bf4fbbec279d81e37d836003a687e98e5da` is separately bound in the curated source/protocol packet; it adds no private plan field. Exact duplicate-key sharing remains a generic capability. Parent must independently verify the narrower actual proposal's eight fixed candidate keys from the same four fixed TRAIN/DEV events, E then N per event before authorization; no actual roster is supplied here.

## Fixed production values and false claims

`limits` is exactly `{connection_s:10.0, first_body_s:20.0, request_s:120.0, start_spacing_s:1.0, no_new_after_s:660.0, transfer_stop_s:780.0, run_s:900.0, per_body_bytes:67108864, total_body_bytes:536870912}`. Invented fixture receipts have `fixture:true` and explicit shortened limits; actual qualifying audit must require `fixture:false` and these production values.

`claims` has exactly seven keys, **all boolean false**: `semantic_mapping_verified`, `utc_filename_basis_verified`, `channel_key_identity_verified`, `location_key_encoding_verified`, `endpoint_mapping_verified`, `waveform_coverage_verified`, `failed96_repaired`. They remain false after every outcome. `request_policy` has exactly `method:"GET"`, `endpoint:"https://geonet-open-data.s3.ap-southeast-2.amazonaws.com"`, and boolean false for `redirects`, `retries`, `head`, `listing`, `auth`, `requester_payer`, `fallback`. Fixture endpoint is numeric-loopback HTTP; it cannot qualify as actual archive execution.

## Saved members and manifest

The absolute output directory path must encode as UTF-8 and use at most 4,096 bytes. Private controller/worker argument envelopes admit at most 65,536 bytes so every valid 16 KiB plan fits after worst-case JSON escaping and bounded metadata/path overhead. The public plan and transport limits are unchanged.

The exclusive private directory contains `roster.private.json` (original plan bytes), `initial.private.json`, exactly eight sequential `000.slot.private.json` through `007.slot.private.json` when finalized, zero to eight numeric `NNN.body.private` files, `receipt.private.json`, and `manifest.private.json`. A body belongs to its original attempted slot index; shared slots have no extra body/attempt. Error, empty and partial files are retained if created. In incomplete runs only extant members may exist; they must not be repaired/replaced to synthesize a final state.

Each member pin is exactly `{name:string, bytes:nonnegative integer, sha256:lowercase 64-hex string}`. Basenames must be safe fixed members; no path traversal. The final manifest has exactly `protocol` and `members` (list of unique pins). It includes roster, initial receipt, eight journals, every created body and final receipt; it does not include itself. Thus finalized membership has 11–19 members, depending on created bodies. Membership must match final rows exactly, with no missing or added member. Independently hash bounded bytes for every listed member. The returned `manifest_sha256` is over the exact manifest file bytes and is its external linkage.

The initial receipt has exactly: `protocol`, `study_id`, `plan_sha256`, `complete:false`, `fixture:boolean`, `limits`, `mapping_status`, `transport_hypothesis`, `template_source_sha256`, `uncertainty_evidence_sha256`, `preregistration_sha256`, `claims`, `run_begin:number`, `request_policy`, `slots`. Its eight initial slots have exactly `slot_id`, `status` (`unavailable` for null key, otherwise `unattempted`) and `uncertainties`.

The final receipt has those same top-level fields, replacing `complete` and `slots`, and adding exactly `attempts:integer`, `consumed_upper:integer`, `observed_body_bytes:integer`, `all_slots_transport_pass:boolean`, `elapsed_s:number`. Journals equal their corresponding final slot objects. Every final slot has `slot_id`, the original `key`, and original `uncertainties`, plus:

| Status | Additional exact fields |
|---|---|
| `unavailable` | `status`, `reason` equals plan unavailable reason |
| `unattempted` | `status`, `reason` is `new_request_deadline` or `total_body_cap` |
| `shared_object` | `status`, `source_slot_index` is an earlier attempted slot with exactly the same key; `request_index` and `transport_pass` equal that source row |
| `attempted` | `status`, consecutive zero-based `request_index`; all request-result fields below |

Request-result fields are `start:number`, `connected_at:number|null`, `headers_at:number|null`, `first_body_at:number|null`, `end:number`, `http_status:integer|null`, `declared:nonnegative integer|null`, `outcome:string`, `consumed:nonnegative integer|null`, `body:member-pin|null`, `observed_bytes:nonnegative integer`, `consumed_upper:nonnegative integer`, `consumption_exact:boolean`, `receipt_verified:boolean`, `worker_exit_confirmed:true`, `transport_pass:boolean`. Returned request rows exist only after writer exit confirmation; unconfirmed exit prevents final accounting. `body` names the corresponding `NNN.body.private` member and must independently match its count/hash. A missing file has `body:null` and observed bytes zero.

Outcomes include `body_complete`, `empty_body`, `incomplete_body`, `body_cap_boundary`, `declared_size_rejected`, `invalid_content_length`, `worker_exit`, `body_receipt_mismatch`, phase deadlines (`connection_deadline`, `first_body_deadline`, `complete_deadline`, `transfer_deadline`) and `worker_error_` plus an exception class name. No raw response header/error text is stored. Outcome alone cannot diagnose scientific mapping or availability.

## Parent-pinned returned execution summary

The callable returns an object with `result` (`finalized`, `controller_failed` or `run_deadline`), `complete:boolean`, `all_slots_transport_pass:boolean`, `mapping_status:"unverified_hypothesis"`, false `claims`, `begin:number`, `returned_at:number`, `elapsed_s:number`. A controller-finalized return also contains `manifest_sha256`; an outer over-budget result can preserve that digest while overriding result/completion/pass to failure. Other failed returns need not have a digest. Missing/failed execution evidence never qualifies as completed transport.

The parent must serialize, preserve and separately hash this returned object in an exclusive private execution receipt before independent audit. Its hash/custody are separate from the collector's saved manifest. A pure independent auditor therefore needs exact plan bytes, exact final manifest bytes, this pinned returned summary, and a bounded member reader (or an equivalent parent custody wrapper). The saved final receipt's earlier elapsed timestamp alone cannot establish finalization. No actual execution summary is supplied in this source task.

All numbers used as clocks are finite monotonic values from the same host/boot clock; they are not UTC or event/P-arrival clocks. Use JSON-round-tripped numeric values with exact arithmetic and strict cap comparisons; no epsilon/tolerance is authorized. `elapsed_s = returned_at - begin` in the returned summary; final receipt `run_begin = begin` and its earlier `elapsed_s` is nonnegative and no greater than the returned elapsed. Recorded request starts are at/after begin, strictly before begin+660; successive attempted starts differ by at least one second. Request end is at/after start, no later than `run_begin + final_receipt.elapsed_s`, and no later than returned time. Present connected/header/first-body values lie in their applicable chronological order between start and end. These are recorded arithmetic checks, not independent physical-timing verification.

Qualifying `transport_pass` requires independently matched nonempty body bytes/hash, exact verified consumption, confirmed writer exit, HTTP200, `body_complete`, connected by start+10, first body by start+20, end by start+120 and by begin+780. Any late/failing row stays nonpassing; termination cleanup can use the finalization reserve. Per-attempt allowance is min(64 MiB, 512 MiB minus previously charged upper bounds). Observed bytes ≤ charged upper ≤ allowance; every present consumed count is at most allowance. `receipt_verified` equals `consumption_exact`; exact rows require `consumed = observed_bytes = consumed_upper`, including exact zero-byte error/size-rejection outcomes. Nonexact rows charge the full current allowance regardless of any present consumed count. Final aggregate observed/upper totals count attempted rows once, never shared slots. Attempts are at most eight distinct keys; aliases, replacement and new requests after the cutoff are forbidden. After an earlier attempted identical key, every later such slot must be `shared_object`, including when the source failed or a cap/deadline has since expired; never a new or unattempted replacement. An earlier unattempted row is not an attempted dedup source.

Final `complete` equals absence of requestable `unattempted` rows; unavailable slots can coexist with complete accounting. `all_slots_transport_pass` is the conjunction over all eight fixed slots, including shared source results; unavailable/unattempted slots cannot pass. The outer summary must say `finalized`, agree with the final receipt's flags, and have elapsed ≤900 for qualifying finalization. Missing/failed/mismatched evidence remains incomplete or nonqualifying. Passing transport never changes the seven false scientific/mapping claims.

## Conditional parent prerequisite

Production acquisition requires all four earlier vertical objects to pass the separate offline decoded literal NSLC, consistent observed-rate and all fixed 1/3/5 sample-grid checks. The parent must bind that prerequisite, same four events/roles/prefixes, E/N pair-prefix correspondence, TRAIN/DEV membership, original clocks and exact proposal/preregistration pins before authorization. The collector cannot inspect or certify those private facts. A failed prerequisite bars new requests.

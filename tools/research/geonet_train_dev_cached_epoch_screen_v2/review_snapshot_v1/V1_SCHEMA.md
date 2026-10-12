# Python API schema

`documents` is an exact built-in list of length four. Each member is exact built-in bytes or None; tuples, bytearray, str and subclasses are rejected. Oversize documents produce retained unknown rows rather than successful interpretation.

`slots` is an exact built-in list of four exact built-in dicts. Every dict has exactly these 17 keys:

- `slot_id`: exact built-in string ordinary, higher, boundary, final in that order.
- `network`, `station`: literal uppercase ASCII alphanumeric strings of length 1..8.
- `location`: literal uppercase ASCII alphanumeric string length 0..8; empty remains empty.
- `prefix`: exactly two uppercase ASCII alphanumeric characters.
- `t0_ns`: exact int (not bool/float), signed64 with at least five seconds margin at both ends.
- `body_sha256`: None or exact lowercase 64-hex string.
- `individual_http200_complete`, `custody_verified`: exact bool parent assertions, required true for interpretation.
- `source_run_complete`: exact bool required false, preserving failed96 whole-run provenance.
- `request_level`: exact string `channel`.
- `request_network`, `request_station`, `request_location`: exact strings identical to the respective fixed slot identities.
- `request_channel`: exact string equal to prefix plus `?`; Z-only or broader filters are not substituted.
- `request_start_ns`, `request_end_ns`: exact int equal to unchanged t0 minus/plus five seconds.

There are 17 keys because each name separated by commas above denotes its own key. Identity/filter strings remain private. The source auditor trusts the explicitly supplied custody assertions only after its strict type/schema check and byte SHA256 match; it does not authenticate transport provenance. That is a parent responsibility.

Return keys are exactly `private_rows` and `public_counts`. `private_rows` has four rows, each retaining role, t0, fixed scope, expected/observed SHA256, byte length, source completeness=false, valid/unknown document state, detailed reason, recognized schema version/node count, literal codes and per-channel epochs/horizon states. Unknown input yields no invented channel code. Total-cap excess preserves expected pins and known byte lengths without parsing/hashing the rejected bodies.

Every retained channel record has code/location/suffix-kind, all epochs and horizon support strings `supported`, `not_supported`, `boundary_unknown`, `unknown`. Network/station/channel bound dictionaries retain raw values, parsed UTC ns, open-end status, validity and reason. Per-epoch fields describe azimuth/dip/rate presence/raw/exact-decimal validity and response-fragment/stage/sensitivity/unit evidence. These contents must stay local and private.

`public_counts` contains the protocol/proposal pin, fixed_slots=4, valid_scope_documents, unknown_documents, generic suffix-document counts, literal-channel/epoch counts, per-horizon channel-state counts, orientation/rate/response counters and explicit false scientific flags. It contains no identity, timestamps, body pins, paths, raw XML, unit names or detailed parser errors. See PROTOCOL for each denominator and exact scope limits. This API does not assert full XSD validation.

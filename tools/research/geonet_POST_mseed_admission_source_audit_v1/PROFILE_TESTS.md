# Prospective profile and invented test matrix

This is an advisory contract for a later authored header scanner, not executable source or a frozen root protocol. The parent must resolve and freeze the layout, limit and containment choices before implementation. Tests below are proposed shapes only; no binary bytes were generated or decoded.

## Narrow initial header profile

Input: exactly one immutable byte sequence whose positive whole-body transport custody and byte pin were independently verified by the parent; length at most 8 MiB. Record offset starts at zero and advances only by the explicitly admitted current record length. No seek outside the current body, heuristic search, control-record skip, recursion, fallback length detector or silent trailing-byte discard is allowed.

Require data-record quality/control code D, R, Q or M; the fixed 48-byte header; strict ASCII literal NSLC fields with documented field padding removed only; and no invented aliases or repaired non-ASCII. Full-SEED controls, blank padding, other formats including MiniSEEDv3 and ambiguous interpretations are unsupported unknowns. Header date fields may be carried descriptively; raw-record timestamp, correction and leap handling stays unverified.

For each record, evaluate a bounded set of structural header-byte-order candidates. Admit exactly one structurally coherent interpretation; reject zero or multiple candidates. Do not choose an interpretation for a convenient timestamp, count or family. Require payload word order 0 or 1 from Blockette 1000; do not require it to equal header byte order. Freeze and test this ambiguity rule against the applicable MiniSEEDv2 specification before code publication.

Require exactly one explicit Blockette 1000. Its advertised record-length exponent must be 8 through 20, giving 256 bytes through 1 MiB. Record end must lie inside the body, and the body must end exactly at an enumerated record boundary. The minimum/maximum here are study admission choices anchored to the inspected installed length list, not claims that other record sizes are invalid MiniSEED.

Require offsets, declared blockette count, forward blockette links, each admitted blockette extent and the data start to be structurally inside the current record. No repeated/overlapping blockette extent or link to another record; at most 16 links. The smallest initial extension set is exactly Blockette 1000 plus only specifically verified optional 100/1001 layouts. Unknown extensions are retained unsupported unknowns. The sizes and field/offset rules for every admitted layout need a pinned specification or matched source check in the next implementation; this audit does not certify the complete MiniSEED grammar.

Propose initial encoding whitelist 1, 3, 4, 5, 10, 11 (INT16, INT32, FLOAT32, FLOAT64, STEIM1, STEIM2). Other encodings are unsupported unknowns, including ASCII. For fixed-width encodings, verify advertised samples fit the admitted payload capacity. For STEIM encodings, freeze the required frame alignment and bounded structural frame accounting from a primary format source before implementation; this is not decompression correctness. If those checks cannot be specified and tested narrowly, STEIM must remain gated rather than treated as safely admitted.

For the smallest initial decoder profile, propose one uniform record length and header byte order per body. Individual encoding and payload word order must still be recorded and validated per record. Mixed record lengths/header endianness remain retained unsupported unknowns initially. This restriction is a prospective study choice, not a statement that ObsPy cannot support mixed records. It must not be changed in response to actual success rates.

Output a bounded private per-record descriptor ledger (offset, length, encoding, advertised sample count and literal identity); public output contains generic counts/dispositions only, no identities, bytes, clocks or source-native contents. Sum EACH enumerated `npts`, rather than first-record count multiplied by inferred record count. No payload array or decoded trace is returned by the scanner. All 65 row and 195 horizon placeholders remain retained by the later parent accounting layer.

## Proposed tests

| Invented shape | Required disposition or assertion |
| --- | --- |
| Empty/short input, 8 MiB exact and one byte over | Bounded unknown for insufficient structure/cap; no vendor call |
| Explicit minimum/maximum length; exponent 0/255; record end outside body | Positive advance only for admitted layout; reject invalid/incomplete boundary |
| Multiple valid records with different `npts` | Exact integer per-record sum; no first-count multiplication |
| Many compressed records advertising excessive samples | Sample ceiling checked before vendor import or payload decode |
| Missing or duplicate Blockette 1000 | Retained unsupported/malformed unknown; never `ms_detect` fallback |
| Self/backward/duplicate/cross-record links; 17 links; count mismatch | Bounded rejection within record; no recursion or seek outside bound |
| Unknown/overlapping extensions and extension crossing the data start | Retained unknown; no guessed extent |
| Two header interpretations; non-ASCII literal identity; padded blank location | Ambiguity/non-ASCII rejection; strict padding rule, no alias repair |
| Header endian differs from legal payload word order | Treat the two fields independently; no convenient swap |
| Full-SEED control, blank padding, MiniSEEDv3, trailing garbage | Retained unsupported unknown; no resynchronization |
| Mixed record lengths or header endianness | Retained unsupported unknown under frozen initial profile |
| Allowed numeric/STEIM and excluded encoding codes | Each record independently checked; no first-record-only proof |
| Fixed-width capacity mismatch or unverified STEIM frame layout | Reject mismatch or keep unresolved admission gate |
| Declared counts exceed per-body or study aggregate limits | No payload decode; original row denominator retained |
| Scanner input bytes replaced between scan and decoder | Pin/immutable handoff failure; no promoted decode |
| Decoder returns count, identity, encoding or record-ledger disagreement | Retained unknown; no convenience crop or partly valid success |
| Standard decoder exceeds planning envelope / worker deliberately over limit | Effective hard containment independently demonstrated before actual use; kill retains unknown |
| Head-only or coalesced traces despite structural header success | `raw_record_timing_verified=false`; never upgrade clock claim |

Future implementation must include meaningful strict/cap tests and the authorized code-only default Codex review before publication. The review bundle may contain authored source, invented tests, frozen public protocol and public pins only. It must exclude vendor source and actual inventories, bodies, receipts, identifiers and credentials. This document-only packet does not invoke review.

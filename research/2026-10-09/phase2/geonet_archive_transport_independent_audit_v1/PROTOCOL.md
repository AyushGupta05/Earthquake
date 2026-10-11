# Independent archive transport replay v1

This independent module implements only the public collector V2 contract. It has not read or imported collector processing code or actual plans, keys, metadata, bodies, receipts, credentials or accounts. Prior frozen sources and the final nine-file mapping uncertainty packet remain unchanged. Development uses Python 3.14.5 stdlib and invented in-memory fixtures, with no installation, HTTP execution, filesystem artifact reader or shared Git changes.

The collector agent's reported first-clean public contract pins match the copied files in `public_contract/`: schema `d4d73425418a641e0afee5f9c53a6d198e137ec540ec8d294345fc75c585b692`, protocol `12cf9340f9c43850debab9cff01157fcd6084ebb02906ea5ad5fb44603e574c2`, gate `33e31c09d69895f6314efd7669e95e324fdd566427a38619c57c90b8d7177f78`. Those three authored files are the sole collector inputs to development. Parent verification of the collector review receipt, authorization, input custody, pushed freezes, runtime/source pins and actual acquisition/replay gate remain separate.

## Pure interface and custody

```python
audit(plan_bytes, manifest_bytes, bounded_member_reader,
      execution_summary_bytes=summary_bytes,
      execution_summary_pin={"bytes": summary_count, "sha256": summary_sha})
```

The keyword arguments above are mandatory for qualification. The callback is `bounded_member_reader(name, maximum_bytes) -> bytes`; it may raise. The parent supplies exact bytes from independently authorized, preserved private members. No local path or network reference is accepted. The separately parent-pinned returned summary must link to the exact manifest digest, original plan bytes must match the retained roster, and every read member must independently match its manifest pin.

Plan bytes are capped at 16 KiB; manifest and each JSON member at 64 KiB; returned summary at 16 KiB; JSON at depth 32 and 16,384 nodes. There are exactly seven required metadata members and at most four body members. Each body is capped at 64 MiB and all bodies at 256 MiB. The callback receives these caps and must return exact bytes within them; the parent must also enforce bounds while reading, before delivering bytes. The auditor checks the callback result but cannot constrain external callback behavior.

The module checks only declared manifest membership. It cannot discover unlisted private artifacts or establish filesystem inventory completeness. The parent must independently establish full inventory and custody; `filesystem_inventory_verified` always remains false. Extra declared body members and bodies attributed to unattempted/unavailable/shared slots are rejected before body reads. Each validated manifest member is read at most once; no retries or alternative member names are requested.

Journal agreement preserves exact decoded JSON types, so boolean/integer substitutions and integer-only fields serialized as floats are rejected. The same conservative comparison also rejects differing int/float representations of otherwise equal clock numbers between a journal and final row. Whitespace and object-key order do not affect decoded journal agreement.

## Assertions and limits

`valid` means the bounded production-contract replay passed. `finalization_verified` means the parent-pinned returned summary and retained metadata agree, including recorded same-clock arithmetic and the finalization bound; it is not an independently measured elapsed time. `complete_accounting` is the contract's absence of requestable unattempted slots. Unavailable slots remain in the four-slot denominator. `qualified_slot_count` counts fixed-slot transport passes, so shared successful slots count separately while request counts and byte totals count attempts once.

Missing/failed/over-budget execution evidence, missing/inconsistent final manifests or any validation failure returns zero qualified slots. A consistent final manifest containing unattempted requestable slots also returns zero qualified slots. Extant failures and partial artifacts remain parent-owned and must be preserved; `preserve_parent_artifacts` is always true. Successful replay returns fixed slot IDs and statuses without raw keys, study ID, body content or private exception text.

The auditor checks exact four-slot order, literal nominal key syntax and immutable evidence pins; deduplication; no replacement attempts; production limits; GET endpoint and false redirect/retry/HEAD/listing/auth/payer/fallback policy assertions; worker exit confirmation; exact/nonexact consumption charging; body counts/hashes and slot attribution; journal/final equality; recorded chronology, spacing and deadline flags; summary/manifest linkage; final totals and completion/pass flags. Complete/empty body outcomes require exact counts, and any declared Content-Length must equal the retained/consumed count. A complete body at its allowance with no declared length is conservatively unsupported because these fields lack independent EOF/chunk-finalization proof. HTTP status, framing outcomes and policy fields are recorded assertions, not independent wire observations. Exact retained bytes do not prove their scientific identity.

`mapping_status` is always `unverified_hypothesis`. The seven contract mapping/coverage/failed96 claims remain false, as do physical timing and filesystem inventory claims. The module cannot establish UTC filename partitioning, blank-location encoding, endpoint/key correspondence, NSLC/day identity, miniSEED validity/coverage, causal waveform availability, physical motion, EEW feasibility, model improvement or complete archive mapping. A negative literal GET says nothing about alternative keys or scientific absence. No all-known, event-clock, atomic database, deployed-converter or model claims are emitted.

## Review and freeze

Focused invented tests precede isolated code-only Codex autoreview using the default authorized helper/engine and no web search. The review snapshot includes only this authored source, invented tests, this protocol/README and curated public contract copies. It excludes actual/private inputs, raw third-party source texts, collector implementation, network execution and nested reviewers. Findings are advisory; accepted defects receive focused tests and a same-engine review. Stop edits/reviews at first clean, then freeze exact reviewed source bytes, public allowlist and source/runtime/test/review pins. No actual replay is granted by source review.

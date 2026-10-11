# NEW offline legacy SC3ML compatibility protocol proposal

Proposed name: `geonet_legacy_sc3ml_010_011_offline_v1`. This is an explicitly **post-collection exploratory offline shadow**, with fixed six-event / 18-slot accounting and zero new event requests. Status: docs only; no adapter, transform execution, invented fixture run, review, pushed freeze, or actual-read handoff has occurred in this audit.

This is a separate diagnostic with a new protocol ID and output location. Parent-provided context is that the completed frozen six-event / 12-GET diagnostic observed native SC3ML 0.10 once and 0.11 five times, while its unchanged parser supports 0.13/0.14 and conservatively retains 16/18 unknown slots. Those aggregates were not reverified here. The new diagnostic must preserve the original result, unknowns, event selection, request history, clocks, and freeze exactly; any later compatibility result must carry its own protocol ID and provenance.

## Scope and proposed adapter contract

1. Work offline only. After all gates below pass, the parent may hand off only the already frozen local diagnostic pairs through its separately authorized actual-read route. No new event request, source selection, clock substitution, AWS access, model input, or private-receipt scan is part of this protocol.
2. Use an explicitly new native reader for only these two root namespaces: `http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.10` and `/0.11`. Require root/version consistency and exactly one EventParameters container. Unsupported, mixed, missing, or contradictory namespaces remain unknown. A namespace alias/rewrite is not an adapter.
3. Preserve raw record identity, parentage, exact reference graph, original lexical values, and original namespace. Expose source-derived mapped candidates as separate annotations. Never create a known correspondence using missing IDs, `NA`, translated-ID collisions, unresolved targets, or duplicate IDs. Reject ambiguous graph paths as unknown; do not silently choose a first/last record.
4. Match only the documented referenced-origin scope; retain picks selected through arrival IDs and amplitude pickIDs as separate provenance paths. Preserve record multiplicity and whether a referenced amplitude lacks its amplitude child. Mark native-but-outside-conversion-scope records separately. Do not equate broader native content with missing converted content or any defect.
5. Represent absent/false/true/unrecognized arrival flags separately. Test exact `true`/`1` predicates and every weight/default branch. Preserve `reported` status as native metadata even when the source-derived conversion expectation omits it. Keep modificationTime/passedQC as SeisComP extension metadata; apply the 0.10 versus 0.11 passedQC distinction explicitly. No flag or status becomes a timing claim.
6. Keep every clock independent, with explicit original field and object path: origin time, pick time, creationTime, modificationTime, and retrieval/observation time. Absent clocks stay absent. Emit only a diagnostic correspondence/disagreement/unknown classification; any broader latency, warning, physical, operational, or novelty inference is outside scope.

The contract is inferred conservatively from pinned source text. The exact event-scope, ID, arrival, and metadata locations are cited in `PRIMARY_SOURCE_AUDIT.md`; hashes and immutable official URLs are in `source_pins.json`. The implementation must document version-specific source-profile proof for each accepted field. Stylesheet fallback does not prove that a field belongs to that version's official schema; 0.10 passedQC validity is unverified here. These mappings are evidence to test, not an assumption that a deployed producer used this commit or stylesheet.

## Required invented fixtures before actual reads

| Fixture family | Required cases / invariant |
|---|---|
| Version and namespace | Separate 0.10/0.11 documents; wrong version literal; missing namespace; mixed namespace; foreign same-local-name element; multiple EventParameters. Exact recognition or unknown only. |
| Event scope | Multiple events with different origin references; unreferenced origins; preferredOriginID without originReference; dangling and duplicate origin IDs. No broader scope fallback. |
| Pick/amplitude/stationMagnitude graph | Arrival-only pick; amplitude-only pick; shared pick; duplicate publicIDs; missing target; amplitude without value child; two stationMagnitude references to one amplitude; explicit versus synthesized parent originID. Multiplicity and unknowns retained. |
| ID mapping | Plain, smi:, quakeml:, empty/missing, space/colon, translated collisions, NA versus explicit NA, arrival composite IDs. Raw identity kept; candidate mapping is never asserted unique without evidence. |
| Flags / weights | Weight present/absent/zero/empty/non-numeric; each flag absent, true, 1, false, 0, unrecognized text; no flags; mixed flags. Cover exact lexical branches and information loss. |
| Status and extensions | reported/other/missing status; creationTime with/without modificationTime; passedQC under 0.10 versus 0.11; same local name in foreign namespace. Original metadata retained, downstream expectation distinct. |
| Fail-closed input bounds | Invented malformed XML, DOCTYPE/external entity, unsupported namespace, oversized/deep/object-heavy input; no network or external resolution. Limits and failure classes frozen before actual input. |
| Clock preservation | Invented conflicting and absent times on different objects; no substitutions; untouched original result artifact asserted by hashes using invented baselines. |

## Gates and actual-read handoff

The parent should decide the implementation before any actual read. A bounded parser/read ceiling, permitted output schema, exact relation/field allowlist, and immutable input handoff are unresolved details to freeze. A conservative initial code proposal is a dedicated reader plus relation-aware comparison harness; any decision to execute official XSLT needs a separate explicit protocol and licence/dependency assessment and is not granted by this source audit.

Required order:

1. Author adapter/harness and deterministic invented fixtures only, in a new isolated compatibility work area. Pin protocol, source hashes, runtime/dependency versions, parser security settings, hard input bounds, exact commands, and pass/fail criteria. Do not edit the original parser or result artifacts.
2. Run focused invented-fixture checks. Submit only authored code, invented tests, protocol, and curated documentation/pins to Codex review. Do not submit raw event/data/model content, actual diagnostic receipts, raw public stylesheet files, or HTTP headers. Verify advisory findings in code; fix accepted actionable issues and rerun affected checks/review until clean.
3. Freeze and push the reviewed code/test/protocol state through the parent's permitted Git workflow. Record immutable commit/hash and the exact reviewed allowlist. A changed implementation requires renewed tests/review/freeze before actual reads.
4. Return to the parent with the clean review evidence, pushed freeze, bounded offline invocation, input/output allowlists, no-network guarantee, and unresolved unknown policy. The parent obtains/uses a **separate actual-read handoff**; code-only review is not raw-data permission.
5. Only the parent executes the authorized bounded actual-read step on the frozen local pairs. Emit a new diagnostic result with separate provenance; do not replace original outcomes or carry new information back into original selection, clock, or unknown-count accounting.

Successful completion of this proposed protocol means the new adapter's behavior is frozen, tested with invented fixtures, cleanly reviewed, and its separately authorized offline diagnostic is reproducible. It does not by itself mean the 16/18 unknown slots become known; structural ambiguity, insufficient semantics, mapping loss, or unavailable evidence must remain unknown.

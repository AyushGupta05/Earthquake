# Independent semantic audit preparation

This is a narrow source-only companion to the separate selection, transport,
artifact integrity and saved-subset clock auditor. It implements semantics anew
from the public protocol, an explicit public predicate description from the
parent, and the complete pinned official transform texts. It imports no producer
projection, comparison, helper, waveform or array package, and never executes an
XSLT. All test metadata is invented. No real XML, event/pick/origin identities,
roster, request URLs, plan, authorization receipt or credentials were read.

## Callable interface

Import this standalone stdlib module after verifying its freeze SHA256:

```python
from semantic_audit import project, compare
qml_evidence = project(qml_body_bytes, requested_event_id, "qml")
scml_evidence = project(scml_body_bytes, requested_event_id, "scml")
comparison = compare(qml_evidence, scml_evidence)
```

`project` has no file, network, receipt or clock-anchor parameter. Bodies must be
bytes of at most4MiB and requested identity a nonempty string of at most4096
characters. UTF-8 only; DTD/entity declarations, over100000 elements, and depth
over64 fail as unknown. Structural ambiguity and unsupported metadata also
return `status=unknown_representation` with null accepted/denominator evidence.
Caller interface type/format violations raise exceptions. MemoryError and other
unexpected process/resource failures propagate; they must stop a caller's audit,
never be promoted to success. The parent controls later private-input authority.

`compare` accepts only two intact results from this module's `project`. It is not
a validator for arbitrary caller dictionaries. The parent must compare a replay
result against saved producer output separately and must retain unknown results
without replacing them with the saved accepted subset.

The output follows the public semantic field names: picks, arrivals,
accepted_picks, event_creation, origin, denominators, unresolved_pick_ids,
reasons and incomplete_associated_P_structure. It adds event-scoped object
counts and qualifying-reference decisions. Accepted times are canonical UTC ISO
strings; raw pick times retain stripped source text. Geometry uses exact Decimal
tuple normalization, yielding numeric text such as `1.2E+4`. This implementation
never silently rounds or underflows; unusually precise or extreme source decimals
can remain exactly representable here while a more restrictive producer field is
unknown. Such a discrepancy must stay explicit, not be converted to agreement.
The module emits no own-clock or preserved-clock counts.

## Semantic scope

- Exact QML root1.2/BED1.2 and SCML0.13/0.14 namespace/version; singleton
  eventParameters and event; exact requested mapped event identity; uniquely
  resolved projected preferred origin.
- Literal native originReference scoping and preferred membership; picks scoped
  through all those origins' arrivals and stationMagnitude→amplitude→pick links.
  Unrelated global picks do not supply evidence. This is the pick-scope rule even
  when an amplitude has no value and would not itself be emitted by the XSLT.
- P/Pg/Pn/Pb is case sensitive after stripping. References resolve uniquely before
  weight rejection. Missing/empty projected weight accepts; otherwise finite
  binary-float strictly greater than0. Duplicate pick objects stay unresolved.
- Native ID mapping preserves `smi:`/`quakeml:` literals and translates colon and
  space for other IDs; reference stripping happens afterward. Distinct raw IDs
  colliding within the event's relevant identity/reference scope make it unknown.
- Native weights/use flags retained literally. Supplied weight is projected only
  for exact timeUsed=`true`/`1` or all three absent use flags; missing weight with
  exact timeUsed=`true`/`1` projects1. False/padded flags can yield absent weight,
  which the QML-equivalent predicate accepts. No physical use claim follows.
- Rejected status is exact lowercase `rejected` after stripping. The XSLT drops
  exact native `reported`, but padded ` reported ` survives and then strips.
  Network/station strip and must both exist; NZ is exactly uppercase. Channel
  and location attributes stay literal. Python3.14 datetime.fromisoformat,
  mandatory timezone and UTC microseconds determine time eligibility; this is
  broader than XML-schema date syntax, and submicrosecond fractions truncate.
- Accepted-ID deduplication occurs after all eligibility checks; zero unresolved
  subsets cannot imply known zero true coverage. A positive incomplete subset
  remains a lower bound. NZ_coverage_known follows the public predicate
  bool(accepted_NZ) or no incomplete qualifying reference.
- Preferred arrival signatures are multisets of exact projected pickID/phase/
  weight values, preserving multiplicity and lexical weight serialization.
- Four core origin fields and seven event/origin creationInfo fields support
  conservative content/revision comparison. Missing geometry/time prevents a
  content match; known lexical revision conflicts prevent resolution candidates.
  Matching recorded revisions additionally require equal creationInfo and all
  present recorded timestamps valid and aware, with at least one timestamp.
- Native modificationTime remains lexical. In QML it is accepted only in a
  supported SCML namespace directly under BED creationInfo, unique across
  namespaces. BED modificationTime is explicitly unsupported, even if a
  producer accepts it. Native agencyURI/authorURI remain source lexical values,
  so transform URI normalization can conservatively conflict.
- Recovery uses distinct left qualifying reference IDs. A newly unique object
  and a newly accepted reference are separate counts; repaired time/station on
  an existing object can be newly accepted. Recovery candidates additionally
  require identity, complete equal origin, equal arrival multisets, and no known
  revision conflict. Recorded-revision recovery also requires matching recorded
  revision evidence.

This is a narrow accepted-P projection, not full XML schema validation or a full
SCML→QML transformer. Structural evidence namespace checking is conservative
throughout the supplied body. Additional schema-valid extensions outside these
fields are not certified. The API does not certify transport, source selection,
roster/order, denominators beyond parsed metadata, receipt timing, station physical
validity, waveform onset, atomic database revision, model or magnitude gain. All
physical, operational, atomic-revision, converter-bug, automatic-reclock and
model-improvement claims are hard false.

## Source-only review and freeze

Focused verification uses the existing pinned Python3.14.5 runtime, no installs:

```sh
work/geonet_waveform_feasibility/.venv/bin/python -m unittest discover -s work/geonet_paired_semantic_audit -v
```

The isolated `.review_snapshot` contains only this independent source, invented
tests and public contract/transform text. Its own Git is separate from shared Git.
Codex autoreview uses the mandated helper and `--no-web-search`; review findings
are advisory, verified here before any fix. Each attempt and test log is retained
in review_evidence. After the first clean helper run, source and tests freeze and
no further edits/reviews occur. The final manifest pins source, runtime, public
inputs, tests and that review. A later explicit pinned parent handoff is required
before this agent reads actual metadata.

The exact safe-public allowlist is in the final freeze manifest. No API output
from actual metadata may be added to it. Exclude .review_snapshot, .git,
__pycache__, any local_runs, actual XML/projections/receipts, and environment or
credential files from publication.

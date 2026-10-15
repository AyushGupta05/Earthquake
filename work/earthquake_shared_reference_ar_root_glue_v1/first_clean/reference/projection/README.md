# Source-only historical comparator mapper

`projection.make_projector(...)` returns the exact seven-positional-argument
`trusted.project_comparators` callback consumed by frozen L `bridge.Adapter.bind`.
It returns exactly `reused_results`, `strong_results`, `origins`. The production
module is a small pure mapper with no files, subprocesses, provider, optimizer,
Torch, execution permission, or scientific conclusions.

ROOT must independently authenticate the expected contract and separately hold
its `expected_pin` before constructing this callback. Merely choosing a contract
and hashing it, a requested digest, or `verified=True` cannot authenticate it.
This module checks the trusted boundary; it does not create one. ROOT must bind
the frozen `transport.canonical`, `packet_digest.sha`, L
`processor.validate_population`, and a closure of frozen
`l_auditor.comparators_checked(report,origins,packet,held_schema,held_authority)`.
In particular the checker must raise on rejection. It returns comparator records
on success; this module does not convert arbitrary booleans into authority.
The frozen bridge has already authenticated raw bytes and canonically decoded
them. ROOT must carry those exact raw identities into this contract. No raw
artifact is fetched or decoded here.

Expected contract schema is `root-held-L-comparator-projection-v1`, exact fields:

- `scope`: exact frozen bridge scope including original-admission raw SHA,
  new/old source maps and raw historical/report/origins pins.
- `receipt`: exact ROOT-authenticated bridge input receipt, including closure
  and proof identities. Scope/receipt are matched using canonical bytes.
- `inputs`: six ordered `reused_scores` pins and the `stronger_envelope`,
  `closed_comparator_report`, `comparator_origins` pins, each `{bytes,sha256}`.
  These identify both the authenticated raw canonical bytes and re-encoding of
  decoded inputs; original 2 MiB / 16 MiB caps remain.
- `joins`: 14 seed-major S/P/D then B/F/H/T objects. Exact fields `seed,arm,
  historical_closure,comparison_closure,comparison_packet_sha256,records_sha256,
  semantics`. Both closures use the frozen six-key closure schema. Their values
  must already be established by ROOT's independently closed evidence.
  `comparison_closure` equals the historical closure except for its explicit
  same-cohort comparison packet. Semantics is exactly
  `same-cohort-only; historical-fit-packet-retained`.

The full independently closed old `marked-sixfit-independent-aggregate-v1`
report retains all 924 records, paired output, guards, authority SHA and exact
6+8 order. The checker recomputes old metrics/guards using the frozen auditor;
it does not rerun forecasts. The six raw original scores bind their original
study, admission, source map, checkpoint and historical packet. Their forecasts
are preserved, including float type and signed zero. The eight stronger input
projections must be exactly the **already ROOT-authenticated old auditor list8**
`{seed,arm,predictions,closure}`; closure packet is the comparison packet, as in
`earthquake_marked_audit_input_adapter_v1/adapter.py:148-160`.

The public bridge does not specify the outer historical `fits8` envelope decoder.
Therefore ROOT must supply this list8 by the previously reviewed
`project_stronger` boundary, positively preserving/authenticating old original
result/checkpoint/source/proof and packet storage-pair references. This mapper
rejects an outer envelope. It does not invent another decoder or elevate a
requested hash into proof. ROOT must also supply 14 complete immutable origins
with historical `packet_sha256` plus existing extra original provenance. Their
whole canonical identity must equal the raw origins pin, and each record-list
pin must bind the full old report. Origins are deep-copied unchanged.

Each mapped result contains its unchanged historical closure and full origin,
an explicit comparison join, and the independently approved comparison closure
required by the processor ABI. A comparison packet identity does not claim old
fits used new native observations. For stronger forecasts only missing
seed/arm/status labels are added; existing contradictory labels reject. Numerical
fields, raw payload pins and historical origin objects are never replaced by
fresh independent-audit values.

Run invented tests with:

```
/Users/ayush/.venvs/ml/bin/python3 -m unittest -v test_projection
```

Tests invoke selected exact frozen source functions via AST to avoid importing
producer/Torch. They execute the frozen bridge acceptance statements and L
population validation, and the independent comparator checker. They cover
missing/mismatched held contracts, raw/canonical mutations, source/admission/
checkpoint bindings, duplicate/reordered arms, event joins, scalar types,
preserved float bits and historical packet identity. They are deliberately not
native acquisition, independent evidence authentication, training, bootstrap
execution, a production data run, or execution authority. Earlier environment
and fixture failures remain in `review/`.

# Independent GeoNet metadata replay

The cached 149 tail bodies have been replayed independently. The new 346-body phase is **pending the parent's completed-run handoff**. This directory contains aggregate audit records and this plan; it contains no collector, reusable parser, raw XML, event roster, pick rows, acquisition URL, private plan/receipt, model or executable implementation.

The authoritative scientific contract is the checksum-pinned [frozen protocol](../geonet_benchmark_feasibility_design/PROTOCOL.md) and [specification](../geonet_benchmark_feasibility_design/sample_specification.json). The original census source and seven input pins are fixed. Active bulk source hashes read during this audit are context, not the final reviewed production freeze. Parent fixes do not create cached-data mismatches.

## Required handoff and input boundary

The parent supplies the final private run directory, plan/receipt hashes, pushed source freeze, clean code-only review receipt and final runtime/source hashes. No request, resume, retry, replacement or external verification is performed here. An independently verified normal exit and completed final manifest are needed to interpret the full new sample as collected. If incomplete, preserve all 346 new plus 149 reused outcomes; inspect saved receipts as an incomplete audit, never as observed scientific absence.

Before parsing, verify the exact original seven input pins, original manifest completion, all manifest member sizes/SHA256 and all 149 raw-body pins. Independently check the final plan and parent receipt bindings, source/cap/runtime fields, collector files and immutable census SHA. Use the compatible original Python 3.14.5 binary and native UTC semantics. Its resolved binary SHA256 is `2477b47fa3ae65b9574eb18a15edb364e96948eaa1875ad3f1c80d780efc9c12`. Do not rewrite times or cached fields to accommodate Python 3.10.

## Frozen population and transport reconciliation

Derive eligible CMT groups from the pinned frame. Retain literal dates, methods, magnitudes, duplicate provenance and all exclusion rules. Confirm 3,437 eligible groups, 286 excluded groups, exact 149 tail identities, all 15 new strata, sample counts 120/106/120 and 346 total. Independently rank the UTF-8 selection strings with the frozen salts, tie by ID. Verify selected-set/query-order hashes and all n/N and N/n values. No selected failure loses its row or weight.

Verify every new run manifest member, including empty/partial bodies. All requests must be a prefix of the planned 346 order, with no duplicate, replacement, tail/source refetch or additional target. Match each attempted body, successful or failed, to its private request ledger and accounted outcome. Reconcile body bytes and attempts against recorded totals/caps. Verify the 1,800-second outer limit, 20-second request limits, one-second start spacing and 4 MiB/128 MiB body caps from available receipts; recorded wall times cannot prove unavailable monotonic timings. A failed or unfinished body is not parsed as a complete scientific observation.

## Independent associated-P reconstruction

Use only standard-library UTF-8/XML/UTC/hash/math tools; do not import or execute census.py, bulk.py, sampling.py, origin.py, aggregate.py, tests or author code. Reject embedded NUL/DTD/entity, wrong QML/BED namespaces, nonunique eventParameters and absent/duplicate requested event identity. Required singleton containers/values and preferred-origin linkage must be unique; missing/ambiguous structures are not choose-first.

Follow only the preferred origin's arrival-to-pick references. Retain phases P/Pg/Pn/Pb. Apply the original precedence: other phase, absent/ambiguous pick reference, invalid/nonpositive present time weight, rejected pick, absent station/network, invalid or timezone-naive observed time, duplicate accepted pick reference. Accept and explicitly count missing weights. Preserve evaluation fields, waveform attributes, normalized UTC and accepted-arrival order privately for comparison; publish only mismatch counts.

Collapse accepted station picks by earliest observed time with the original network.station identity. T0 is the earliest accepted NZ pick. Count unique stations strictly before T0+1/3/5 seconds; equality at the boundary is excluded. Origin diagnostics, phaseHint, theoretical arrivals and CMT dates cannot substitute for this clock. Compare the 149 entire original base outcomes exactly, including reasons, accepted picks, all-network/NZ station counts, T0 and horizon counts. Compare new independently reconstructed fields with final collection outcomes, preserving legitimate parse/identity/linkage failure statuses.

Known positive means at least one accepted NZ subset member even if other references are unresolved. Known zero requires a successfully parsed identity/preferred-origin set with no unresolved qualifying references/times/station identities. An unresolved zero is unknown. Positive incomplete subsets retain an incomplete flag. Their clocks are earliest **accepted** picks; at that fixed clock their accepted station counts are lower bounds, but an unresolved earlier pick could change a hypothetical complete clock. Do not claim fully resolved-clock early coverage from those counts.

## Origin, calendar and geometry reconstruction

Independently extract a uniquely linked preferred origin even when unrelated malformed P fields make P coverage unknown. Require one container/value for origin UTC, latitude, longitude and depth. Keep UTC-aware valid time separate from in-window time and complete geometry. Require finite latitude [-90,90], longitude [-180,180], depth in metres; finite negative depth is retained and flagged. Missing, naive, nonfinite, range-invalid or ambiguous values remain separately described, with no imputation. Count optional origin type/referenceSystemID, and publish only absent/ambiguous/present-value-hash categories for reference URIs.

For valid reference pairs, count literal CMT-minute versus origin UTC day, year and candidate-calendar-partition matches/disagreements/unknowns, signed offset bins and abs(offset)>=300s. Count origin/T0 outside [2003-08-01,2025-01-01), negative T0-origin and T0-origin>600s. No anomaly alters a denominator, a target, a clock, a weight or a split. Where a needed time/link is invalid, the comparison is unknown rather than false.

Publish outward-rounded aggregate latitude/longitude/depth bounds, origin type/reference categories, split by Mw>=5.5/6/7 and the literal external_wphase flag. The flag refers to two original CMT anchors; it does not classify arbitrary W-phase method rows or global sources. Signed longitude extrema crossing the dateline do not define a broad geographic footprint. No geographic exclusion is selected during this phase.

## Aggregation, weights and investment gate

Count all frozen outcomes, linkage/time/geometry evidence, rejection reasons, known/zero/unknown/positive P coverage, incomplete-positive subsets and strict station-count histograms overall and for each stratum. Use exact rational N/n sums internally, with explicitly stated float comparison tolerance for the collector's serialized floats. For denominator W, positive weight P and unknown weight U, the coverage interval is [P/W,(P+U)/W]. Include failed/unknown/unattempted rows and weights. Tail weights are one. Weighting describes the hash-ranked CMT frame and does not correct availability, CMT or station-record selection.

A completed new metadata gate requires all 346 outcomes accounted, >=312 identity-matched uniquely linked in-window UTC origins, >=277 positive NZ-P events, and >=ceil(n/2) positive events in every frozen stratum (12/24 or 5/10). Count valid-origin/positive-P/anomaly overlaps explicitly. Geometry completeness is separate from the 312 time gate. Do not use tail results to pass this new-only gate or silently drop/repartition flagged dates after outcomes.

Produce aggregate-only JSON and results prose with input/output hashes and per-field mismatch counts. A mismatch requires investigation and a retained finding; it does not authorize new acquisition. Metadata feasibility verifies neither calibrated waveform prefixes, operational picker/packet receipts, sequence-independent splits, model accuracy, novelty nor published-benchmark superiority. A later response/waveform tranche needs its separate frozen scope.

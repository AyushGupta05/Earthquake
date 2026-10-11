# Cached 149 tail XML: independent aggregate audit

All 149 cached bodies reproduce their complete original census outcomes exactly under native Python 3.14.5. This includes accepted pick rows/order, exclusions, preferred-origin linkage, station totals, earliest accepted times and strict 1/3/5-second counts. Every original manifest member (158), seven input JSON pins and all 36,932,474 XML bytes were checked first. No census/bulk module was imported. The one-off analysis used isolated standard-library Python; it made no request, fit, model load, AWS action or Git edit.

All 149 have a uniquely linked preferred origin, valid timezone-aware UTC inside the frozen source window, finite in-range latitude/longitude and finite depth. There are zero negative depths, off-window origins or accepted NZ clocks, CMT UTC-day/year/partition disagreements, absolute origin-CMT-minute offsets >=300s, negative accepted-NZ-T0 minus origin offsets, or offsets >600s. One origin is 60–299 seconds after its CMT-minute anchor; 148 are 0–59 seconds after it. No anomaly causes an exclusion. Origin type is absent in all 149; referenceSystemID is absent in 102 and present in 47 across two value hashes.

All 149 prove >=1 accepted NZ-associated P station. **22 have incomplete associated-P structure**, containing 707 unresolved qualifying pick references. Their valid accepted subsets remain positive; no unresolved zero is observed. The replay retained 8,984 accepted picks across all networks, 8,902 NZ picks, 4,248 explicitly accepted missing-weight arrivals and 5,534 nonpositive/invalid-weight exclusions. Full reason counts are in [cached149_audit.json](cached149_audit.json).

The T0 and station counts of an incomplete event describe its accepted subset. An unresolved earlier pick could alter a hypothetical complete clock. The counts are lower bounds at the preserved accepted clock, and do not certify coverage at a different fully resolved earliest-pick clock.

| Mw threshold | Events | >=3 NZ stations before +1s | Before +3s | Before +5s |
|---|---:|---:|---:|---:|
| >=5.5 | 149 | 23 | 57 | 82 |
| >=6 | 60 | 10 | 22 | 30 |
| >=7 | 15 | 2 | 6 | 7 |

Latitude/depth coarse aggregate bounds are [-52,-29] degrees and [4,365] km for all 149; [-52,-29] degrees/[5,242] km for the 60 Mw>=6 cases; and [-52,-29] degrees/[10,127] km for the 15 Mw>=7 cases. Signed longitude extrema cross the dateline, so [-180,180] aggregate extrema do not describe a worldwide geographic footprint. The same coordinates represented in [0,360) have outward-rounded longitude bounds [159,185] degrees for the entire tail; this is a coordinate representation, with no geographic exclusion. The two literal external_wphase cases, both Mw>=7, have outward-rounded bounds [-46,-42] latitude, [166,174] longitude and [12,16] km depth. No unresolved qualifying P reference occurs in those two. These are descriptive geometry/provenance checks, not a geographic selection or global-source classifier.

The complete aggregate panels split by threshold, calendar partition and external_wphase flag, strict station histograms and per-field mismatch counts are in [cached149_audit.json](cached149_audit.json). [input_provenance.json](input_provenance.json) pins every source/input used and the exact compatible runtime. Coarse coordinate bounds round outward at one degree and depth bounds at 1 km; no event-level identifiers, times, picks, URLs or coordinate rows are published.

## Material negative runtime finding

An independent native Python 3.10.20 replay changed full outcomes/station totals in 99/149 events, earliest accepted T0 in 11, and strict 1/3/5-second station counts in 16/33/45. It rejected 1,516 originally valid pick times solely because their fractional seconds had 1,2,4 or 5 digits, reducing accepted picks from 8,984 to 7,468. It also rejected 16 preferred-origin UTC times with 4/5 fractional digits. Python 3.14 accepted them. The immutable source/data did not change. The independent 3.14 replay has zero mismatches; no time adapter or source rewrite was used. The parent was informed before acquisition so the collector can freeze the original-compatible runtime. See [runtime_drift310.json](runtime_drift310.json).

## Still pending

The 346 new lower-M bodies have **not** been inspected or claimed here. [REPLAY_PLAN.md](REPLAY_PLAN.md) defines the post-handoff reconciliation, known-zero/unknown accounting, weighted intervals, anomaly overlaps and new-only gate. This result is retrospective annotation/geometry evidence, not waveform/response availability, online receipt/picker replay, earthquake-sequence independence, model improvement or novelty.

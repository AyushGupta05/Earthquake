# GeoNet tail metadata census: complete, feasibility gate passed

The frozen population contains **149 unique catalogued Mw≥5.5 IDs, 60 Mw≥6 IDs and 15 Mw≥7 IDs** dated 2003-08-01 through 2024-12-31. Every queried ID has accepted NZ preferred-origin-associated P/Pg/Pn/Pb picks. Lower and upper magnitude bounds coincide; no duplicate-ID or conflicting-Mw groups occur in this pinned source. The predeclared ≥60 / ≥20 observed-pick support gate passes. This earns a small separate waveform/response availability audit only.

| CMT threshold | Unique-ID lower / upper | Known NZ P-pick coverage | Unknown coverage | Failed / unqueried |
|---|---:|---:|---:|---:|
| Mw≥5.5 | 149 / 149 | 149 | 0 | 0 / 0 |
| Mw≥6 | 60 / 60 | 60 | 0 | 0 / 0 |
| Mw≥7 | 15 / 15 | 15 | 0 | 0 / 0 |

There are 3,727 CMT data rows and 3,723 resolvable unique IDs, of which 3,437 pass the frozen date/Mw eligibility rules. Four rows use the explicitly unknown ID 9999999; 286 rows fall outside the date window. There are no invalid-date, invalid-Mw or unresolvable-syntax exclusions. These are unique catalogue identities, not independent tectonic sequences. Year/month concentration and literal method counts remain in [aggregate_summary.json](aggregate_summary.json). The two README-documented USGS W-phase solutions remain explicitly marked in all three tail bands; CMT Mw is not substituted with catalogue ML.

Complete associated-pick sets contain at least five NZ stations for all tail events. The early annotation clock has much less multi-station support. The following entries are event counts with **at least 3 / at least 5 NZ stations** strictly before each horizon, measured from the earliest accepted NZ pick:

| CMT threshold | +1 s | +3 s | +5 s |
|---|---:|---:|---:|
| Mw≥5.5 | 23 / 15 | 57 / 30 | 82 / 45 |
| Mw≥6 | 10 / 6 | 22 / 11 | 30 / 15 |
| Mw≥7 | 2 / 0 | 6 / 2 | 7 / 3 |

Pick evidence remains imperfect. Of 8,984 accepted pick records, 2,558 have manual evaluation mode and 6,426 automatic mode; 7,623 have missing evaluation status and 1,361 confirmed status. The frozen policy retained 4,248 accepted arrivals with missing timeWeight and excluded 5,534 nonpositive/invalid timeWeight arrivals and 707 missing/ambiguous pick references. Other-phase exclusions are preserved in [independent_replay.json](independent_replay.json). These are aggregate record counts, not event exclusions. Retrospective picks do not establish real-time detection, packet arrival, continuous calibrated three-component data or unclipped waveforms.

The authorized recovery completed on 10 October 2026 in 395.97 seconds, with **152 combined request attempts and 37,598,159 response-body bytes**: the original three source requests plus 149 event requests. There were no source refetches, redirects, retries, failed/incomplete events or unqueried candidates. HTTP/TLS overhead is outside the stated body-byte cap. The old run remains an incomplete column-alias failure; its zero-count placeholder is not absence evidence. The explicit recovery amendment granted one fresh 30-minute window while retaining combined 500-attempt / 100-MiB ceilings.

Independent local replay matched every group projection and query-order entry, all 149 event outcomes, 8,984 accepted pick records and their exclusion reasons, both network scopes for every event, all threshold coverage/concentration/method aggregates, and all 158 local file sizes/SHA256 values. No census-helper imports were used. This checks artifact and aggregate consistency, not scientific independence or prediction performance. Exact source/runtime/protocol/review bindings appear in [HANDOFF.json](HANDOFF.json) and the frozen [execution plan](approved_recovery_execution_manifest.json).

The reviewed helper passed 36 invented-fixture tests. The final authorized code-only autoreview returned no findings after two verified XML fixes: preserve QuakeML/BED namespaces and reject duplicate singleton containers. Source bytes have not changed since that clean review and frozen plan. Real CMT rows, event IDs/picks and raw QuakeML remain in ignored local_runs and are excluded from Git and reviewer inputs.

This census supplies stronger tail-event feasibility evidence than Chile DEV's single MA≥5.5 event. It supplies no new model, error reduction, bulk-error preservation, novelty or published-benchmark superiority evidence. A benchmark still needs waveform/response integrity, a causal processing/clock contract, an independently separated event/sequence test design, and small-event support for bulk-error claims.

Primary sources: [pinned official CMT directory](https://github.com/GeoNet/data/tree/13573971f8cfbefbb329adeba46da6f31b614f25/moment-tensor), [official FDSN documentation](https://www.geonet.org.nz/data/access/FDSN), [data policy](https://www.geonet.org.nz/policy). Real source hashes and the complete aggregate tables are preserved locally; no author contact or cloud resource was involved.

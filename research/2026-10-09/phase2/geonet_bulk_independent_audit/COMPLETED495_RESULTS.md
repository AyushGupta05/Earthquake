# Completed GeoNet metadata replay

The frozen new-only metadata gate **passes independently**. All 346 new XML responses have a uniquely matched preferred origin with valid UTC time inside the source window, finite in-range latitude/longitude and finite depth, and at least one accepted NZ associated P pick. Every frozen stratum passes: 24/24 positive events in each 24-event stratum and 10/10 in the smaller DEV stratum. The thresholds remain 312 valid origin times, 277 positive events, and 12/24 or 5/10 per stratum. No row, failure denominator, sampling weight or clock was changed.

This is a metadata result. It establishes neither usable calibrated waveform prefixes nor operational picker/packet timing, sequence independence, magnitude accuracy, novelty or superiority over a published method.

## Independent reconstruction and provenance

An isolated standard-library Python 3.14.5 one-off reconstructed all 495 associated-P base outcomes and origin diagnostics from XML without importing or executing the collector, original census, tests or audit modules. All base/origin/status fields match the producer exactly; all 149 original cached base outcomes also match their immutable original outcomes. The earlier Python 3.10 incompatibility remains a retained failed preflight and is not used here.

The replay verified the final private plan, parent authorization/review receipt, normal exit, exact ten source hashes, immutable census source, compatible runtime binary/build, seven original input pins, all 158 original manifest members and all 350 completed bulk manifest members. It independently reconstructed the 3,437 eligible/286 excluded frame, all 15 strata, 346 selected new identities, 149 reused identities, private row provenance, selection/query hash order and rational sampling probabilities. Private identifiers, row values, picks, XML and query URLs are absent from this report.

The parent receipt records pushed freeze `6c11dc558df0cf918bb23a046640810fabd99d7f` before launch. That binding and time order were checked locally; this audit made no remote Git verification request. The source and synthetic-test review receipts bind the same ten files. Original cached149 reports and their manifest remain byte-identical; new results use separate files.

There are 3,142 main replay assertions and 3,356 recursively compared summary values. Counts, statuses, linkage, reasons and diagnostics match exactly. Weighted calculations used exact fractions internally; producer floats differed by at most 5.684341886080802e-14, within the declared 1e-10 absolute / 1e-12 relative tolerance. An additional 1,490 checks covered five invented absence/unknown/weight cases and integer-microsecond station-clock verification for all 495 previously reconstructed accepted-pick sets. Five, three and one events respectively have an accepted station exactly at the 1/3/5-second boundary; those stations remain excluded from the strict counts.

## Coverage and missing references

| Population | Events | Positive NZ P | Unknown / known zero | Incomplete positive P structure | At least 3 NZ stations before 1 / 3 / 5 s |
|---|---:|---:|---:|---:|---:|
| New lower-M sample | 346 | 346 | 0 / 0 | 54 | 86 / 197 / 263 |
| Reused Mw ≥5.5 census | 149 | 149 | 0 / 0 | 22 | 23 / 57 / 82 |
| Combined | 495 | 495 | 0 / 0 | 76 | 109 / 254 / 345 |

All 54 incomplete new cases are in the 120-event TEST sample; the 22 incomplete tail cases are in its 49-event TEST tail census. New TRAIN/DEV counts are 120/106 and have no such unresolved references. This is an observed catalogue-structure asymmetry, with no inferred cause. There are 1,210 unresolved qualifying arrival-to-pick references in the new sample and 707 in the reused tail. Positive accepted subsets prove at least one accepted NZ P; they do not make the unresolved picks disappear.

Each T0 remains the earliest **accepted resolved NZ P**. Accepted station counts are lower bounds at that preserved accepted-subset clock. They are not guaranteed lower bounds at a hypothetical earlier T0 obtained by resolving all missing references. No catalogue origin time, theoretical arrival, phaseHint or unobserved operational trigger replaces T0.

The lower-M inverse-probability frame weight totals 3,288. Weighted positive and unknown totals are 3,288 and zero, giving [1,1] positive-coverage bounds for this fixed sampled frame. Weighted totals with at least three stations at 1/3/5 seconds are 891.0833333333334 / 2013.375 / 2586.25. These are descriptive hash-sampling estimates, not additional observed events or a correction for CMT, waveform or station selection. Tail weights remain one. The full accepted P totals are 28,110 across networks and 28,007 for NZ.

## Origin diagnostics retained

All 495 preferred origin times are inside [2003-08-01,2025-01-01), and all agree with the literal CMT date on UTC day, year and candidate calendar partition. No finite negative depth, earliest NZ pick outside the source window or earliest NZ pick more than 600 seconds after origin was found. Original CMT date interpretation remains the frozen literal UTC-minute convention; the cached README does not independently establish its timezone, and CD is centroid depth rather than hypocentral depth.

Two separate new TRAIN events carry descriptive clock flags: one absolute origin-minus-CMT-minute offset ≥300 seconds and one earliest accepted NZ P before origin. They do not overlap, and neither has an incomplete P subset. Both remain in the gate and every denominator. The new origin-minus-CMT offset bins are 341 in [0,60) seconds, three in [60,300), one negative and one ≥300. These diagnostics do not justify rejecting, reassigning, refetching or re-clocking either event.

Outward-rounded preferred-origin ranges for all 495 are latitude [-52,-29] degrees, wrapped longitude [159,185] degrees and depth [0,365] km. The new-only ranges are [-51,-34], [163,182] and [0,310] km. These are coarse aggregate bounds, with no arbitrary geographic filter. Signed longitude extrema crossing the dateline are not a broad geographic footprint. Origin type is absent for all 495; referenceSystemID is absent for 351 and present in two value-hash categories for 134 and 10. The literal external_wphase flag still denotes only the two original tail anchors; it is not a global-source classifier. Full threshold/flag panels are in the diagnostic JSON.

The [cached full-CMT graph preflight](../geonet_cmt_sequence_preflight/RESULTS.md) is a separate exploratory epicentre/minute graph. Its primary candidate TEST ceilings 1107/49/19/5 and sensitivity ceilings 89/30/15/4 are not verified full preferred-origin graph outcomes. The sensitivity graph percolation remains a heuristic warning, not proof of one physical sequence. This metadata gate does not settle that independent benchmark-design limitation.

## Recorded transport limits

Exactly 346 planned new requests completed with HTTP 200/ok, in frozen order, with no duplicate, replacement, source or tail refetch. Bodies total 70,172,690 bytes; each is below 4 MiB and the total below 128 MiB. No interruption marker or received-chunk sidecar remains. Recorded monotonic minimum start spacing is 1.1663034159992094 seconds; maximum whole-request elapsed time is 2.868758290999722 seconds. The last recorded request ends 744.1342993750004 seconds after the outer start, within the shared 1,800-second deadline and ten-second finalization reserve. Parent elapsed time is 744.3622120830005 seconds and exit code is zero.

Those recorded timings and parent UTC/elapsed receipts are internally consistent. They do not supply an independent packet stopwatch or EEW receipt log. This replay made zero network requests, cloud actions, Git actions, model loads or fits; no reusable production source was added. Any response/waveform tranche requires its own frozen scope, and this completed audit authorizes no expansion itself.

Full aggregate records: [replay checks](completed495_replay.json), [independent summary](completed495_summary.json), [extra diagnostics](completed495_extra_diagnostics.json), [additional verification](completed495_additional_verification.json) and [input provenance](completed495_input_provenance.json). Final extension hashes are recorded separately in completed495_manifest.json.

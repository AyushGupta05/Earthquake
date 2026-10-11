# GeoNet lower-magnitude metadata feasibility: frozen proposal

**Next step: 346 new lower-Mw metadata queries, reusing the exact 149 tail-event artifacts.** This is a bounded feasibility screen, not a selected training/evaluation cohort or a waveform acquisition. No requests, code changes, review, fits or AWS actions were performed by this design task. The user's broad project authorization covers the purpose; implementation, source freeze and execution receipts remain the parent's workflow.

## Pinned frame and uniform stratified sample

Input: `work/geonet_tail_census/local_runs/recovery_20261010/groups.json`, SHA256 `2270bd1969f8565dfd2cc683a17c08c766324ab67425d289956f9b68f19a44a8`. Independent aggregation finds 3,437 unique eligible IDs, zero Mw conflicts and identical lower/upper Mw bounds. The 286 ineligible groups stay outside the existing population. Eligible labels span Mw 2.8–8.0. CMT dates are literal catalogue fields documented as YYYYMMDDHHMM00, not inferred origin/onset/receipt seconds.

Use five disjoint lower bands and three **candidate calendar strata**, with exact labels in `sample_specification.json`. The calendar boundaries stratify this metadata sample; they do not select the final benchmark split.

| Mw band | TRAIN candidate 2003–2014 N / n | DEV candidate 2015–2017 N / n | TEST candidate 2018–2024 N / n |
|---|---:|---:|---:|
| <3.5 | 43 / 24 | 10 / 10 | 118 / 24 |
| [3.5,4) | 569 / 24 | 132 / 24 | 404 / 24 |
| [4,4.5) | 640 / 24 | 220 / 24 | 327 / 24 |
| [4.5,5) | 300 / 24 | 133 / 24 | 183 / 24 |
| [5,5.5) | 111 / 24 | 40 / 24 | 58 / 24 |
| New total | 1,663 / 120 | 535 / 106 | 1,090 / 120 |

Within each of these 15 strata, take `n=min(24,N)` IDs by ascending SHA256 of the UTF-8 string `geonet-bulk-feasibility-v1|PARTITION|BAND|EVENT_ID`, tie by ID. This is reproducible pseudorandom stratification, independent of pick/response/model outcomes. Under an exchangeable random-hash-ranking interpretation, its design inclusion probability is `n/N` and frame weight is `N/n`; the fixed hash selection is not a new stochastic draw or an empirical unbiasedness guarantee. All selected failures keep their weight and denominator. These weights do not correct availability- or response-dependent missingness, CMT selection, or station-record selection. Later bulk claims apply to a prespecified evaluable CMT population, not all NZ earthquakes. Do not force year anchors, replace failures, oversample convenient stations or condition on waveform success.

Globally order new queries by SHA256 of `geonet-bulk-feasibility-query-v1|EVENT_ID`, tie by ID. This order disperses any capped prefix, but a cap remains incomplete coverage, not an imputed full-population result.

Publish hashes/counts only. Selection-set hash: `6ed849d32a6ab180b7ddb4ddbf85d085d6819011fcebe7c093384c0806452d7c`; query-order hash: `8490814535ee0f74e47e7307794a7f296b9694e8aeef68d6c78f293990331993`. Both hash UTF-8 newline-delimited IDs with a final newline; the set hash sorts IDs lexicographically. No ID roster is published here. The new 346 plus existing 149 form a **495-event metadata screen**. This screen does not become a training/evaluation cohort automatically.

## Retrieval, clock and additional audit fields

Reuse the pinned CMT bytes and all 149 tail raw/outcome artifacts exactly; verify their existing manifests. No current-main resolution, newer label substitution, source refetch or tail-event refetch. If cached tail records lack the added audit fields, derive them offline from the same verified QuakeML bytes; preserve and independently match the old pick counts/T0. Missing fields remain missing.

New requests are individual-event archive QuakeML only, using the existing documented event-ID endpoint and original namespace/identity/reference validation. Accept exactly one event whose publicID resolves to the requested ID. Follow its uniquely resolved preferred origin and arrival-to-pick references. Accepted phases remain P/Pg/Pn/Pb, timezone-aware observed pick times, valid network/station identities, rejected-status and nonpositive-weight exclusions, and explicit missing-weight counts. A phaseHint without preferred-origin association cannot substitute.

Collapse accepted NZ station picks to their earliest observed UTC pick; T0 is the earliest accepted NZ pick. Preserve the originating pick/arrival IDs, phase, network/station/location/channel, original time, evaluation flags and weights locally, plus the tie rule and source-body hash. Count stations strictly before T0+1/3/5 seconds; exact-boundary picks are excluded. Preserve the complete pick list and exclusions. No theoretical arrivals or origin-time subtraction may replace this annotation clock.

Also retain preferred-origin UTC time, latitude, longitude, depth in metres and source unit/reference provenance locally, alongside the original CMT date/label/method/source-row references. These origin fields are for **offline identity, date and sequence audit only**, never magnitude-model inputs under this proposal. Accept finite latitude in [-90,90], longitude in [-180,180] and depth in metres. Preserve finite negative depth with a descriptive flag; it is not a physical exclusion. Retain missing/invalid/ambiguous fields without imputation. Preferred catalogue ML or another magnitude does not replace the pinned CMT Mw target.

Retain the reviewed parser's event/origin/P statuses. Diagnose origin fields separately: zero or multiple preferredOriginID elements, or zero or multiple matching origins, mean missing/ambiguous linkage; do not choose the first. A time, latitude, longitude or depth requires one container and one value, with duplicated containers/values recorded as ambiguous. Invalid or timezone-naive origin time remains unknown; invalid geometry does not erase a uniquely linked origin or separately valid associated P coverage. Report unique-link counts, valid in-window UTC-time counts and complete finite time/latitude/longitude/depth counts separately. The 312 gate below requires valid in-window time; it does not require geometry or depth.

Keep acquisition/identity/origin status separate from P coverage. Required labels include HTTP/timeout/body-cap/unattempted; returned-ID mismatch/duplicate matching events; missing/ambiguous/dangling preferred-origin reference; missing/invalid/timezone-naive origin time; missing/invalid geometry/depth; invalid pick references/times; and no accepted NZ-associated P picks. Known zero coverage requires a successfully parsed identity-matched preferred-origin pick set; unresolved structure is unknown, not zero.

Record independent anomaly flags:

- `preferred_origin_off_window`: valid origin UTC outside [2003-08-01,2025-01-01).
- `cmt_origin_calendar_date_disagreement`, `cmt_origin_calendar_year_disagreement` and `cmt_origin_candidate_partition_disagreement`: compare the literal CMT anchor with origin UTC day, year and candidate partition. Retain explicit match/mismatch/unknown states.
- `cmt_origin_abs_delta_ge_300_seconds`: retain signed `originUTC - pinnedCMTMinuteStartUTC` in seconds and flag absolute differences ≥300 seconds. CMT's minute-start is the audit anchor, not a claim of actual origin seconds.
- `earliest_nz_pick_off_window`, `earliest_nz_pick_before_origin` and `earliest_nz_pick_origin_delta_gt_600_seconds`: retain signed `earliestAcceptedNZP - originUTC` in seconds and flag negative or >600-second offsets. Do not manufacture a new T0, infer a theoretical P, or silently reject other valid picks.
- `preferred_origin_negative_depth`: finite negative depth is preserved and counted descriptively.

An anomaly retains the frozen denominator and all provenance. It is not proof of a wrong ID; unresolved date/identity joins cannot silently enter a final benchmark or be repartitioned after viewing predictions. Flagged origin fields do not erase separately valid raw-pick coverage, and unavailable geometry prevents a sequence-isolation claim rather than every ordinary engineering test.

## Hard caps and missingness gate

One local serial CPU metadata run. **400 new attempts maximum; exactly 346 planned event queries; 128 MiB combined response bodies; 4 MiB per event; 1,800-second outer deadline; 20 seconds per request; at least one second between request starts.** The extra attempt ceiling grants no additional targets. No retry, redirect following, replacement, automatic resume, StationXML, miniSEED or AWS. Every partial body/failed attempt counts. Start the outer clock before validation/import/loading, and preserve all 346 outcomes on cap/interruption. Existing cached bytes are provenance, not new download bytes. HTTP/TLS overhead is outside the body cap and must be stated.

The investment gate earns only a separately frozen response/availability screen:

- All 346 selected IDs have an accounted outcome, including unknown/unattempted.
- At least **312/346** have an identity-matched unique preferred origin and valid timezone-aware origin time inside the source window; report date/partition anomalies separately and resolve them before benchmark inclusion.
- At least **277/346** have known ≥1 accepted NZ-associated P station; within each stratum require at least `ceil(n/2)` such events: 12 of 24, or 5 of 10. Report overlap with valid origin/time/date audit states explicitly.
- Publish weighted and unweighted coverage with all frozen denominators, per-band/calendar missingness reasons and strict 1/3/5 station-count distributions. Do not require three early stations: that would erase much of the existing large-event support.

These are practical feasibility floors, not statistical power guarantees. A timeout/cap is incomplete, not scientific absence. A failed gate yields a retained feasibility limitation; it does not trigger replacement, a larger transfer limit or a different sample.

## Separate later phases

After independent replay, a small response-only tranche can examine **all 60 Mw≥6 events**, plus two hash-ranked screened events per lower-band/calendar cell and two per [5.5,6)/calendar cell: at most **96 events and 288 first-three-station targets**. Freeze its exact targets and reuse matching cached responses before requesting anything. Suggested separate ceilings are 300 attempts, 512 MiB bodies, 4 MiB/StationXML and 3,600 seconds; these are a future draft, not part of this metadata run. Missing/late picks, responses and units stay in the denominators. No replacement by a more convenient instrument. Waveform acquisition and any benchmark fitting require their own frozen scope after this screen.

The completed small audit independently verified 15/18 strict three-component plus screen targets at all horizons, intersecting the observed-P condition in 9/11/13 targets. All six targets from its two Mw≥7 events passed the raw screen, with P intersections 4/4/5. This deterministic six-event sample is not representative and cannot project the survival rate for 495 events. Source/data freeze: `0c377649b06feb81824169d98b4b51291d6db72e`; aggregate summary SHA256 `17a2aba101bd8894849704436c67e5efa39763c75d395fde6fe58fed0582c671`.

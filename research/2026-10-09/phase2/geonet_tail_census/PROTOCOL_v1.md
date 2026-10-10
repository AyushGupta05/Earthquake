# GeoNet CMT / associated-arrival census — frozen v1

Frozen 10 October 2026 before any CMT CSV or event QuakeML retrieval in this task. This is metadata feasibility, not model training or a benchmark score. No Chile TEST access, waveforms, StationXML, credentials, cloud resources, or author contact.

## Population and identity

Retrieve the main commit SHA from the official GeoNet/data GitHub API, then pin both `moment-tensor/GeoNet_CMT_solutions.csv` and `README.md` to that SHA. Preserve exact response bytes, SHA256, URL, acquisition UTC and original 1-based data-row indices. CSV required columns (case-insensitive, stripped): EVENT_ID, Date, Mw, Method. Date follows documented YYYYMMDDHHMM00; use literal calendar date, not an inferred onset or CMT timestamp in seconds. Eligible dates are 2003-08-01 inclusive to 2025-01-01 exclusive. Mw must be finite. Record malformed or missing fields separately; do not convert ML.

Resolvable ID syntax: 5–7 digits or YYYYp plus six digits. `9999999` is explicitly unknown, never merged into one earthquake or nearest-time joined. Group all rows with the same resolvable EVENT_ID. Report duplicate rows and conflicting Mw/date/method. All rows remain local. A group enters the primary population only if every row has valid in-window date and Mw; mixed/missing groups are excluded with reasons. For threshold u, lower count requires min(Mw)>=u; upper count requires max(Mw)>=u. Thus ambiguous solutions never silently pick a convenient magnitude. Count unique IDs, not statistically independent tectonic sequences. List calendar-year/month concentration as descriptive; no claim of sequence separation.

Preserve literal Method values. Do not infer method from date: older events can be reprocessed. Mark the two documented external USGS W-phase solutions by their exact README Date strings 20090715092200 and 20161113110200. Other external provenance is unknown unless the pinned README documents it. NS describes stations in CMT inversion, not early-P coverage.

## Deterministic query and missingness

Fetch individual-event QuakeML only for valid groups with max(Mw)>=5.5. Query order is ascending SHA256 of `geonet-tail-census-v1|EVENT_ID`, tie by ID, fixed independently of any prediction or coverage. This disperses any capped partial census over time; partial coverage remains descriptive, not weighted/imputed full-population coverage. At most one request attempt per event; no replacement, no retries, no redirect following. Request URL is exactly the documented archive event query with eventid, no waveform/station paths. Returned event publicID must have the queried ID as its last URI path segment; exactly one matching event required. Failures/empty responses/schema conflicts remain explicit and do not shrink denominators. Other-event returns cannot enter coverage.

Primary pick set: follow preferredOriginID, uniquely resolve origin; follow each arrival.pickID to one uniquely defined pick. Accepted direct regional P phases are exactly P, Pg, Pn, Pb. Require timezone-aware observed pick.time.value, networkCode and stationCode; reject evaluationStatus=rejected and arrival timeWeight<=0 (missing weight is retained but counted). No theoretical arrival reconstruction, catalog source distance, origin subtraction or location ranking. Record other phases, missing references/times/identities and evaluation status/mode. phaseHint alone is not an associated arrival and cannot substitute. A missing/ambiguous preferred origin yields unknown coverage, never zero good stations.

Collapse multiple accepted picks/channels/location codes at each network.station to its earliest observed UTC pick time. Report all-network and NZ-only station counts separately. Define t0 as the earliest accepted pick **within each reported network scope**. Count distinct stations with pick.time−t0 strictly less than 1,3,5 seconds; exact-boundary picks are excluded. UTC values refer to recorded pick times, not origin times, waveform start times, packet reception or online declaration. Retrospective picks may depend on future data. An earliest reviewed pick is an annotation clock, not a real-time trigger. Report per-event any/3/5-station coverage and horizon station-count histograms, with failed/unqueried events separately. Do not infer continuous, 3C, calibrated or unclipped waveform support from this metadata.

## Bounds and execution

One local process, standard library, no GPU. Total real census (pin + two files + event requests + parsing) <=1800 seconds; SIGALRM stops blocking I/O at the deadline, allowing only bounded local finalization afterward. <=500 request attempts TOTAL, <=100 MiB downloaded response bodies TOTAL; HTTP headers/TLS overhead excluded and stated. Timeout <=20 seconds per request, starts at least one second apart. Per-response limits: commit JSON1MiB, README1MiB, CSV10MiB, QuakeML4MiB. Headers declaring excessive body sizes are rejected before reading; chunk reads cannot exceed residual total limit. Exact-limit unknown-length response is conservatively incomplete unless EOF verified without another byte. Errors consume requests and received bytes, preserved with partial bytes/hash. These are ceiling limits, not target expenditure. Do not raise limits based on results. Output directory must not exist. Raw content is never printed.

Write outputs under ignored `local_runs/`. All real rows, derived event/pick ledgers and raw files stay local and out of Git/review. Curated aggregate summary and provenance hashes may be copied out after independent verification. Reviewer sees only helper, invented fixtures, this protocol and documentation citations. Review must be clean and focused tests pass before real fetch. Any changed processing policy gets an explicit amendment before further real execution; no silent rerun selection.

## Decision and interpretation

Report Mw>=5.5,6,7 unique-ID bounds and with recorded associated P picks. A practical further-acquisition gate is at least60 unambiguously Mw>=5.5 IDs and20 unambiguously Mw>=6 IDs with >=1 NZ associated P-pick station. This earns only a small separate waveform/response audit, not model training. Partial census counts are observed lower support, not a failed population conclusion unless the complete population proves insufficient. No power or novelty claim. CMT-selected events cannot establish preservation of small-event bulk error. A later benchmark requires response/units/causal preprocessing, waveform availability and independent event/sequence splits before encoder fitting.

## Primary documentation

- CMT schema and external provenance: https://github.com/GeoNet/data/tree/main/moment-tensor (official README; pin bytes in run).
- Catalogue IDs/detail: https://www.geonet.org.nz/data/types/eq_catalogue
- Event endpoint: https://www.geonet.org.nz/data/access/FDSN
- QuakeML1.2 BED: https://quake.ethz.ch/quakeml/docs/REC?action=AttachFile&do=get&target=QuakeML-BED-20130214.pdf (pick observed time, arrival association).
- Data license/citation: https://www.geonet.org.nz/policy ; CC BY3.0 New Zealand, CMT DOI10.21420/MMJ9-CZ67, catalogue DOI10.21420/0S8P-TZ38. No redistribution of real tables in this task.

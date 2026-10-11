# GeoNet archive transport: source-only feasibility

11 October 2026. **A separate anonymous daily-object transport preflight is plausible; avoidance of the observed timeout is unproved.** Official documentation establishes access and a nominal miniSEED key layout. It does not establish availability, size, timing or completeness for any selected object. This packet authorizes no acquisition.

The failed 96-event screen remains incomplete: 412/417 planned requests, first waveform body read timeout, and no native-prefix qualification. Its 96-event/411-target denominators, interrupted slots and zeros retain their original meaning. The older next-data memo still says “not launched”; the completed counts-screen report and checkpoint supply the later status. No retry, resume, repair, replacement or revised historical result follows. [Counts screen](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/outputs/earthquake_geonet_counts_screen.md), [checkpoint](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/outputs/START_HERE.md), [earlier planning memo](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/outputs/earthquake_geonet_next_data_plan.md).

## What the official documentation establishes

| Source / issue | Documented finding | Boundary |
|---|---|---|
| [GeoNet FDSN](https://www.geonet.org.nz/data/access/FDSN), Data Select | miniSEED record boundaries can extend before/after requested times; no server trimming/padding. | Extra samples cannot enter an earlier inference deadline. |
| Same page, Service Limits | Large requests take longer; connections can break after 5–10 minutes without transmission, and HTTP200 may precede useful data. Single-user size limits exist, but no numeric threshold is given. Combine related selections; use AWS Open Data for large volumes. | These warnings do not diagnose the failed screen's 20-second timeout or promise archive speed. |
| Same page, Current webservices | FDSN archive is seven days behind; near-real-time access retains eight days and may be incomplete. | A historical transport study needs no change to its waveform information clock. |
| [GeoNet AWS page](https://www.geonet.org.nz/data/access/aws) | miniSEED prefix `s3://geonet-open-data/waveforms/miniseed`; daily synchronization; data free of charge under the stated CC3 licence with acknowledgement. | Daily synchronization is not complete coverage or a latency guarantee. |
| [Official GeoNet tutorial](https://github.com/GeoNet/data-tutorials/blob/main/AWS_Open_Data/README.md), Data access / Miniseed waveform data | No sign-in is needed; unsigned access is documented. Continuous miniSEED objects cover 24 hours at differing sample rates. Synchronization is still described as ongoing. | A nominal key can be constructed; its existence, contents and size are unverified. |
| [GeoNet AWS registry](https://registry.opendata.aws/geonet/) | GeoNet-managed `geonet-open-data`, region `ap-southeast-2`; no AWS account required. | No account or bucket configuration was inspected. Explicit Requester Pays configuration is not stated in these documents. |

The tutorial's nominal object key is:

`waveforms/miniseed/[yyyy]/[yyyy].[doy]/[SITE].[NC]/[yyyy].[doy].[SITE].[NC]-[CHA].[LC].D`

It defines four-digit year, three-digit day-of-year, uppercase 3/4-character site, two-character network/location and three-character channel. This is documentation of the naming scheme, **not a verified event-to-object mapping**. Blank-location exceptions, nonconforming identifiers, timestamp basis for day boundaries, object revisions, record spillover, gaps/duplicates and archive/FDSN equivalence are unavailable from the inspected text. Triggered strong-motion binaries and derived products are different collections and cannot silently substitute for continuous native-count miniSEED. [Official tutorial](https://github.com/GeoNet/data-tutorials/blob/main/AWS_Open_Data/README.md).

## Transport inference and remaining gate

A direct daily-object request could bypass FDSN time-window query assembly; this is an inference about the proposed request path, not an observed backend cause or performance result. Whole-day over-delivery can greatly exceed a short-prefix download. Published free data/anonymous access supports a credential-free proposal; it is not a measurement of transfer charges or client-resource costs. Do not add credentials, requester-payment flags or a paid fallback when an anonymous request fails.

The smallest useful next step is the separately versioned, four-slot proposal in [PROSPECTIVE_PREFLIGHT.md](/Users/ayush/Documents/Codex/2026-10-09/ok-x20/work/geonet_archive_transport_source_audit/PROSPECTIVE_PREFLIGHT.md). Source review, invented tests, a pushed implementation/protocol freeze and a separate parent input/acquisition authorization must precede any real roster read or request. Passing transport cannot establish strict three-component prefixes, physical calibration, benchmark support or model accuracy. All old freezes remain unchanged.

Only the three named local reports and official documentation were read. No event/waveform endpoint, object HEAD/GET, bucket listing, private artifact, AWS account API, code installation/execution, fit or Git operation occurred. Web tools returned rendered documentation; immutable publisher bytes/commits were not obtained.

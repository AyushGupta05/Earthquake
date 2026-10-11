# Prospective four-slot configured-key transport proposal v1

Protocol ID: `geonet-official-configured-literal-key-transport-proposal-v1`.
Target preparation: a NEW collector V3; this proposal does not amend V1, V2, failed96, earlier source freezes, selections, outcomes or clocks. This document authorizes no actual invocation.

## Fixed design

Parent retains the previously selected, ordered roles `ordinary`, `higher`, `boundary`, `final`: exactly four distinct event slots and four distinct literal candidate keys, three TRAIN and one DEV, no TEST. The event/pick selection, role assignments, split assignments and scientific reference clocks remain fixed. Parent privately freezes the exact new plan and its SHA-256 before any request. This packet contains no actual roster, identifier, timestamp or key.

The sole format is the pinned GEONET configuration in [CONFIGURED_TEMPLATE.json](CONFIGURED_TEMPLATE.json), [official config](https://github.com/GeoNet/geonet-obspy-utils/blob/5bce92270ba19f30bf8829cdcb471e3a3d28fad7/geonet_obspy_utils/clients/aws/client_config.yml#L1-L7). Substitute existing fixed metadata literally into:

`waveforms/miniseed/{year}/{year}.{day_of_year:03d}/{station}.{network}/{year}.{day_of_year:03d}.{station}.{location}-{channel}.{network}.D`

The source-declared prospective base URL is `https://geonet-open-data.s3.ap-southeast-2.amazonaws.com`. The new experiment tests this literal URL/key hypothesis. It does not assert live endpoint correspondence. The source reader's UTC convention justifies declaring a UTC year/day hypothesis; it does not verify the archive writer's partitioning. [Official client](https://github.com/GeoNet/geonet-obspy-utils/blob/5bce92270ba19f30bf8829cdcb471e3a3d28fad7/geonet_obspy_utils/clients/aws/client.py#L169-L229)

Experimental shape restriction: already selected uppercase STATION3-or-4, NETWORK2, CHANNEL3 and nonblank LOCATION2; no wildcard, empty LC, `--`, whitespace, percent encoding, case conversion or normalization. This restriction is our bounded plan rule, not a claim that the formatter enforces it. A channel prefix plus `Z` may remain an explicitly recorded channel hypothesis; channel-inventory certification is not a prerequisite for this transport-only test. No alternate day/field order/LC/channel/endpoint is tried after failure. Calendar validity must be checked in code using invented tests before parent plan serialization.

## Unchanged numerical limits

| Measurement | Limit |
|---|---:|
| Distinct GETs | At most 4, one per fixed slot |
| DNS/connect/TLS | 10 s from each request start |
| First body byte | 20 s from each request start; headers alone do not pass |
| Complete request, including write/flush | 120 s from each request start |
| Minimum GET start spacing | 1 s |
| Stop new requests | 660 s from collection begin |
| Stop transfers | 780 s from collection begin |
| Whole supervised collection, including preparation/finalization | 900 s |
| Per delivered response body | 67,108,864 bytes |
| Total delivered response bodies | 268,435,456 bytes |

Count partial and error body bytes; do not count headers or claim wire/kernel byte bounds. Use the established conservative allowance accounting when a terminated worker lacks verified consumption. No extra read probes at a byte cap. Unknown/chunked exact-cap endings remain incomplete unless framing proves completion. Hard parent watchdogs encompass DNS, connection, first body, complete body and finalization; a missing final manifest, unconfirmed writer termination or over-budget returned summary cannot qualify as a complete run. These limits match the original numerical proposal, SHA-256 `ae85f4f2a1431cc4b30c91fcc5caab8cc040d36c51ce744f93ef62ae34290a1a`.

Use anonymous literal GETs only, identity encoding, exclusive outputs and immutable plan. No redirects, retries, HEAD, listing, wildcard selection, aliases, replacement, range repair, credentials, signing, payer flag, payment or alternate-service fallback. Retain every unavailable, unattempted, error and partial result. New monotonic transport clocks are captured for the new execution; earlier scientific or transport clocks are never overwritten or reused as its measurements.

## Claims and separate actual gate

Require `mapping_status: unverified_hypothesis`. Selected channel identity, deployed archive writer rules, UTC partition, LC storage semantics, endpoint/key correspondence and waveform coverage remain unverified. All semantic/coverage/physical/EEW/magnitude/failed96-repair claims remain false. Four HTTP200 bodies, if observed, mean complete bounded literal transport only; four errors do not prove waveform absence.

Before actual requests, parent must bind this proposal, audit/uncertainty document, template and exact external source pins into a separately versioned collector and private fixed plan; complete invented-fixture tests and default code-only Codex review to first clean; freeze and push the curated public source/review packet; and supply the explicit parent-owned actual invocation gate. Parent must preserve the plan, member hashes, complete manifest and separately pinned outer returned execution summary. A separately reviewed independent receipt replay must pass before any qualifying transport assertion. This proposal contains no mapper implementation and grants no decoding, training, acquisition expansion or blind retry authority.

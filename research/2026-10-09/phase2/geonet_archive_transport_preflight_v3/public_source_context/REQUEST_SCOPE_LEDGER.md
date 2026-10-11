# Request and scope ledger

Investigation v1 stopped after the finite discovery/source budget. No further search or retrieval is proposed in this packet.

## Discovery via web tool

Six focused queries, in two batches:

1. `site:github.com/GeoNet "geonet-open-data" miniseed archive write`
2. `site:github.com/GeoNet "archive/waveforms" filename`
3. `site:geonet.org.nz waveform archive historical data AWS daily files retention`
4. `site:github.com/GeoNet miniseed "Location" "Year" archive writer`
5. `site:github.com/GeoNet/ miniseed archive writer filename`
6. `site:github.com/GeoNet/ "YearDay" "Location"`

Four web-tool batches in total: six searches, five opens and two finds. Opens/finds concerned the official GeoNet organization/repository pages or documentation. Organization page 2 returned 429; the guessed hyphenated seismic-waveform URL was unavailable. Search results from other institutions/third-party authors were not used as GeoNet mapping evidence. Web-tool underlying HTTP counts, delivered-byte counts, response-byte hashes and request timestamps are unavailable; these are not represented as native request measurements.

## Native bounded source/document retrievals

[native_request_ledger.json](native_request_ledger.json) retains all ten native GETs: eight HTTP200 and two HTTP404. Delivered HTTP response bodies totaled **614,774 bytes**; decoded source bytes are not counted again. Native transport used no retries or redirect following, a 20-second request maximum, 10-second connection limit, and the exact per-response caps recorded in the ledger. The declared total native cap was 1,048,576 bytes; every delivered body remained within its cap. Curl user configuration was disabled; no credentials, cookies, signing, payer/account or AWS API was used.

The two 404s were public documentation paths `/data/types/seismic-waveforms` and `/data/types`; each returned 1,082 bytes and is retained. The later underscore path was separately discovered, not a transport retry. No actual archive-object request was sent.

Source-only discovery consisted of one bounded 39-entry public repository inventory page, two public source trees, a utility commit response, two exact inert source blobs and official access documentation. No repository fixture or waveform payload was retrieved. GeoNet/kit names did not reveal a clearly named archive writer in this bounded inspection; that is not evidence of global writer absence. Older archive clients were not fetched after the budget ended.

## Inert verification and exclusions

The utility API tree selector and commit response identified revision `5bce92270ba19f30bf8829cdcb471e3a3d28fad7`. Reconstructing all six tree objects from metadata matched each declared SHA1 and the commit root `795fbb5a7e8cc4c639bdfd0dffc2383a8c1df98c`. The API tree response's top-level selector SHA is the commit SHA; it must not be relabeled the root-tree SHA. Both decoded source files matched their size, Git blob SHA1, tree membership and recorded SHA256. CRLF source bytes were preserved. This used inert bytes/stdlib hashing only; no source execution, import, validation of actual data or install.

Only relevant authored earlier source audits and the public V2 numerical protocol were read locally. No actual metadata/plan/keys/IDs/objects, private execution receipts, AWS/account configuration, fits or model artifacts were read. No existing freeze or shared/remote Git was modified. Parent's aggregate description of four prior 404/NoSuchKey outcomes is context only, not independently re-audited here.

Raw external code, HTML, API responses and HTTP headers are kept outside the curated allowlist. Repository LICENSE content was not fetched, so this packet makes no raw-source redistribution/license determination. Only original authored documentation, generic template/pins and request-scope metadata are curated. No code implementation was made; no code autoreview or fit was warranted by this documentation-only task.

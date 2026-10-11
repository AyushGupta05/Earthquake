# Bounded source trail

Only official GeoNet primary pages/code were relied upon. Generic search results from third-party archives were not treated as mapping evidence and were not followed. No actual event/station/waveform data endpoints were requested.

Focused discovery queries, in two batches:

1. `site.geonet.org.nz AWS S3 waveform archive year day location code filename`
2. `site.github.com/GeoNet waveform archive S3 UTC location`
3. `site:github.com/GeoNet "mseed" "archive"`
4. `site:github.com/GeoNet "YearDay" "Location"`

Official trail: GeoNet AWS access page → GeoNet data-tutorials/AWS_Open_Data README → official GeoNet organization/FDSN repository README → FDSN internal dataselect/time parser and command holdings/dataselect → holdings miniSEED dependency → vendored GeoNet kit header/time helpers. Only generic authored source files were downloaded; test fixtures, actual data, environment/configuration secrets, vendor package metadata, and deployment accounts were not read.

The web tool could read documentation but several direct raw/source-tree pages had cache misses. A guarded anonymous HTTPS read followed only github.com/raw.githubusercontent.com source/document URLs, with per-response byte caps and15-second timeouts. Redirects to other hosts/protocols were excluded. No AWS client/account/service was invoked. One tutorial file-page fetch returned503; a final official repository revision pin plus immutable README read succeeded. `retrieval_log.json` preserves direct-source successes/failure; web-tool cache misses are listed here.

Known web-cache misses: official GeoNet repository filter q=mseed; GitHub tutorial raw refs/heads/main and raw.githubusercontent main README; immutable FDSN internal and cmd/fdsn-ws tree pages. These were tool retrieval limits, not absence evidence.

Outcome: documented layout supported; UTC daily-key basis and blank-location filename mapping not proven. Stop source discovery at this bounded coverage limit. Keep explicit hypotheses without authorizing acquisition.

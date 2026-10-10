# GeoNet independent tail cohort: metadata feasibility

The completed census identifies 149 unique Mw≥5.5 earthquakes, including 60 Mw≥6 and 15 Mw≥7, in the pinned official moment-tensor catalogue for August 2003 through December 2024. All 149 have accepted NZ P-family picks associated with their preferred origin. This passes the frozen metadata gate for a small waveform/response audit.

Early network evidence is much sparser than the complete pick lists. Among the 15 Mw≥7 events, only 2, 6 and 7 have at least three NZ stations picked before +1, +3 and +5 seconds from the earliest accepted NZ pick. These are retrospective annotations; online picking and telemetry latency have not been reproduced.

Independent replay checked 158 artifact hashes, all 149 event outcomes, 8,984 accepted picks and every aggregate table. The acquisition used 152 combined requests and 37.6 MB of response bodies, with zero failed, unqueried or unknown-coverage events. The earlier header failure and its zero-count placeholder remain preserved as incomplete acquisition, not absence evidence.

No waveform, StationXML, model or fit was acquired by the census. The next separate audit checks actual three-component samples, gaps and epoch-specific responses under a frozen deterministic request list. It cannot establish bulk-error preservation without small-event support or generalization without an independent event/sequence split. GeoNet Mw and Chile MA remain separate targets.

[Full counts and caveats](phase2/geonet_tail_census/RESULTS.md) · [Independent replay](phase2/geonet_tail_census/independent_replay.json) · [Official data access](https://www.geonet.org.nz/data/access/FDSN)

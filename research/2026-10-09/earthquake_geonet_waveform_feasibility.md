# GeoNet small waveform audit: independently verified result

The six-event audit confirms strict, aligned three-component prefixes and matching transfer-response metadata for 15 of 18 frozen station targets at each requested deadline. All six targets from the two Mw>=7 events pass coverage and the clipping screen. This is data feasibility, not a magnitude-prediction result.

| Time after earliest annotated NZ P | Frozen targets | Usable three-component prefix and screen | Also annotated P before deadline |
|---|---:|---:|---:|
| 1 second | 18 | 15 | 9 |
| 3 seconds | 18 | 15 | 11 |
| 5 seconds | 18 | 15 | 13 |

Two metadata requests returned HTTP204; their paired waveforms were unattempted. One other target lacked the required prebuffer/left-edge coverage. All failures remain in the denominator, with no replacement or filling.

The run completed using 34 requests, 1,167,804 body bytes and 67.85 seconds of reported worker elapsed. Independent replay verified 36 artifact hashes, all 54 denominator slots, 144 component and 144 response checks, and 48 actual future-suffix mutations. The source/protocol freeze was committed and pushed as 0c377649b06feb81824169d98b4b51291d6db72e before requests. It passed 38 invented tests and clean code-only Codex review; earlier review findings and the zero-request startup path failure remain retained.

This deterministic oldest/latest-year sample cannot estimate availability for all 149 larger events. Finite response metadata does not establish independent physical calibration; a clean screen does not verify absence of clipping. P picks and the clock are retrospective, with no operational picker or telemetry replay. No model training or new AWS resource followed from this audit.

[Full results](phase2/geonet_waveform_feasibility/RESULTS.md) · [Independent replay](phase2/geonet_waveform_feasibility/independent_replay.json) · [Frozen protocol](phase2/geonet_waveform_feasibility/PROTOCOL_v1.md)

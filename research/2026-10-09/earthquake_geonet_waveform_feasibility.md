# GeoNet small waveform audit: frozen preparation

The six-event audit has passed 38 invented fixtures and a clean final code-only Codex review. Independent replay reproduced all five census inputs, six event selections, 18 station targets and 36 planned archive requests. No real waveform or StationXML response has yet been requested.

The fixed sample spans Mw bands [5.5,6), [6,7) and >=7, with one event from the earliest and latest eligible years in each band. It retains the first three NZ stations per event at their observed location and channel prefix, with no replacement after an acquisition failure.

The source is ready for a pre-acquisition Git freeze. Only after that freeze will the parent create the hash-bound receipt and execute one local CPU audit, capped at 30 minutes, 100 attempts and 128 MiB of response bodies. No additional AWS resource or model training is involved.

At 1, 3 and 5 seconds, the audit checks strict absolute prefixes, coherent response epochs, three-component coverage, sample-grid alignment and clipping candidates. A finite transfer response establishes metadata consistency; it does not prove physical calibration, absence of clipping or operational warning latency. Raw rows, station identities, response inventories and waveforms remain local and excluded from Git and review.

[Protocol](phase2/geonet_waveform_feasibility/PROTOCOL_v1.md) · [Review and tests](phase2/geonet_waveform_feasibility/REVIEW_CLOSEOUT.md) · [Independent frozen selection](phase2/geonet_waveform_feasibility/independent_plan_replay.json)

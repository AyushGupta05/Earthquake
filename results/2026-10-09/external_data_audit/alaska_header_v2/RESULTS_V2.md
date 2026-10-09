# Alaska header audit v2 — 2026-10-09

The fixed, checksum-gated audit completed all 781 release containers and 296,990 channels/segments in 37.13 seconds. Every header channel now joins its metadata: zero missing rows in either direction, zero ambiguous identities, zero reported inter-segment gaps or overlaps. The original 281,216 missing joins in each direction were caused by one-sided normalization of the literal `--` location. The new normalization is symmetric, specific to this release, and retains the original IDs. Distinct raw identifiers that collapse within either source are rejected instead of merged.

Fifteen focused tests pass. Scoped Codex autoreview is clean (`review_v2.json`). The full audit read every selected ZIP member to EOF for CRC validation, used ObsPy `headonly=True`, and encountered no reader warnings. It decoded no real waveform sample arrays and computed no picks, predictions or magnitude-dependent selections.

The v2 results are in `work/benchmark_research/alaska/header_audit_v2`. Its `events.json` SHA-256 is `ab2d99734367545773c274241448d9279241486ecc39dd3753e193c58c408367`; auditor SHA-256 is `80d59d3d607ad200b19988b3c81450b73996bf649825b08da9b90377d62cbf4d`. Source ZIP size is 8,372,439,484 bytes and its checked published MD5 is `38449cb548b3e5c7119b267f6a12a400`. The previously verified SHA-256 is recorded in `full_download_provenance.json`. Complete evidence and output/source hashes are in `verification_v2.json`.

The v1 `events.json` still matches its original `f85b56a5c4e98afbb109d38865e4849fb62745d44f6a2570534e13bf656bda6e` SHA-256. The original auditor is saved as `header_audit_v1.py`. Independent comparison confirms every one of the 296,990 raw header start/end/count/rate tuples is unchanged after accounting for the location join.

## Remaining issues for an executable benchmark

| Nominal metadata rate | All channels | Nonexact header rates |
|---|---:|---:|
| 50 Hz | 232,677 | 674 |
| 100 Hz | 27,301 | 47 |
| 200 Hz | 37,012 | 112 |

There are 833 nonexact comparisons across 130 events, including those that v1 failed to join. No rates were rounded. The largest deviation is a header rate of `49.998473282442745` against nominal 50 Hz: −0.001526717557254642 Hz, or −30.53435114509284 ppm. Over the declared trace this changes `(npts−1)/rate` by at most 0.01099209136156861 seconds. This is a comparison of header conventions, not proof of a physical clock fault. A future loader must retain exact timestamps and choose an explicit causal resampling rule rather than silently replacing them with nominal rates.

Zero inter-segment gaps does not certify complete input windows: each event/channel has only one returned segment. First-to-last sample spans range from 0.04 to 599.99 seconds (median 359.98 seconds). There are 82 channels shorter than 1 second, 214 shorter than 3 seconds, 383 shorter than 5 seconds, and 9,287 shorter than 359 seconds. These totals do not measure post-P availability. A future event clock must check each requested station/component window and expose missingness; zero padding must not be reported as observed waveform data.

Matched unit strings are `DU/M/S` for 206,024 channels and `DU/M/S**2` for 90,966. Sensitivity, physical-unit conversion, component orientation and P-arrival availability need a separate source audit before model inputs can be specified. No sample quality, response correction or waveform timing accuracy is certified here. The 781 release containers remain distinct from both the unresolved published 530-event analysis cohort and the 780 current ComCat identities; no events were removed to force agreement.

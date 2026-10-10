# Noise-relative polarization: completed negative information diagnostic

10 October 2026. **The fixed F−D acceptance gate fails at all six deadline/station-panel comparisons.** This implementation does not earn a geometry or distribution-model expansion. All 18 fits completed on the existing AWS worker; no additional resources were launched.

B contains the 51 existing waveform descriptors and 34 static instrument/site fields. D adds 21 pre-P marginal noise descriptors. F adds 21 cross-component covariance, lag, generalized-eigenvalue and principal-axis descriptors. The same 127 input slots, 128 fixed ReLU features, ridge penalty 0.01, two seeds and fitting populations are used. All inputs are computed from the allowed observed prefix or pre-P noise. The three separately fitted targets are magnitude, log-distance and log-depth; geometry errors below are in original kilometres.

The primary table compares the mean of the two original-unit predictions. Negative differences favour F. Each panel contains 66 M≥4 earthquakes; the two panels can contain the same earthquakes and must not be counted as 132 independent events.

| Deadline | Station panel | Bulk MAE Δ | MedAE Δ | CVaR95 Δ | M≥4 event MAE: D → F | Tail Δ 95% event-bootstrap interval |
|---|---|---:|---:|---:|---:|---:|
| 1 s | seen | -0.000197 | +0.001110 | +0.002280 | 1.025022 → 1.037833 | [+0.000546, +0.026228] |
| 1 s | held | +0.000921 | -0.000898 | +0.003879 | 1.021816 → 1.031493 | [-0.001360, +0.020626] |
| 3 s | seen | +0.001022 | +0.002936 | -0.003334 | 0.953330 → 0.967543 | [+0.000169, +0.029267] |
| 3 s | held | +0.001021 | +0.001724 | -0.003704 | 0.980805 → 0.980870 | [-0.013073, +0.013543] |
| 5 s | seen | +0.000228 | +0.001363 | +0.001295 | 0.957859 → 0.951268 | [-0.021765, +0.009281] |
| 5 s | held | -0.003511 | -0.001478 | -0.008585 | 0.984122 → 0.982956 | [-0.016257, +0.013422] |

At 1 and 3 seconds the ensemble tail error increases in both station panels. At 5 seconds the tail gains are only 0.00659 and 0.00117, below the prespecified 0.02 requirement, and both confidence intervals include zero. The held-station 5 second gain is not reproduced by both seeds. The 1 second seen-station tail interval is entirely above zero. F never produces the required 5% event-level distance/depth improvement across all six panels.

This is a negative result for these descriptors under this fixed ridge probe. It does not establish that all polarization information is useless or that a larger waveform model cannot use cross-component motion. Hyperparameters, station subsets or deadlines will not be chosen after seeing this failure.

| Deadline | Station panel | Distance event MAE: D → F (km) | Depth event MAE: D → F (km) | Seed tail deltas F−D |
|---|---|---:|---:|---:|
| 1 s | seen | 29.7174 → 29.7641 | 12.2392 → 12.2522 | +0.018462, +0.004496 |
| 1 s | held | 31.0354 → 31.1807 | 13.8109 → 13.7988 | +0.009499, +0.009481 |
| 3 s | seen | 29.8138 → 29.8819 | 12.2035 → 12.2193 | +0.007448, +0.016705 |
| 3 s | held | 30.8572 → 30.9293 | 13.6600 → 13.6521 | -0.008362, +0.007937 |
| 5 s | seen | 29.0417 → 29.0599 | 12.1734 → 12.1705 | -0.011783, -0.002461 |
| 5 s | held | 29.8572 → 29.8446 | 13.5174 → 13.4976 | -0.007033, +0.004528 |

Sampling used 112,660 TRAIN records: 55,967 fitting, 34,841 held-event/seen-station and 21,852 held-event/held-station. The waveform-quality pass fraction exceeds 99.94% at every deadline. Valid event counts are 14,997 fit, 9,357 seen-panel and 7,757 held-panel. There are only two M≥5 events in each evaluation panel. Sampling weights restore metadata event-record exposure; they do not correct waveform-quality nonresponse. Event-bootstrap intervals use 1000 fixed paired resamples, and do not model all station dependence.

The events and stations are held out from these 18 fits. These are new partitions of the project’s TRAIN data, which earlier experiments used; they are not a globally untouched external benchmark. No Chile DEV/TEST results or published-method superiority follows from this probe. Manual picks and released full-record preprocessing also limit claims about raw-stream causality.

The extractor completed in 716.65 seconds on 9 October, with exit 0. The fitter started 12:39:03 UTC on 10 October and finished 12:39:35 UTC, with a 32.62 second watchdog result, exit 0, no timeout, a 1800 second internal limit and 1860 second outer limit. All 48 local synthetic tests and 17 AWS focused tests passed; another 17 tests passed on the exact deployed fitter. Final Codex autoreview has no findings. Accepted fixes covered invalidating a persisted passing gate after provenance/artifact/worker failure, and stable reporting of very negative predicted depth. The frozen protocol and extraction bundle remain unchanged. An independent read-only audit verified all 73 saved artifact hashes and recomputed weighted-record and event-macro errors for both D/F arms at all six panels to within 1e-11; it did not refit models or replay the bootstrap.

Code and results are archived in the Earthquake repository under `research/2026-10-09/phase3/polarization_preflight/` and `results/2026-10-09/phase3/polarization_preflight/`. Models/predictions remain on durable EBS at `/mnt/eew-research/runs/polarization_probe_v2`, with per-artifact SHA 256 values in the result manifest. The raw 167 GB waveform source is identified by path/stat/format rather than a full-file hash; all extracted descriptor artifacts are hashed.

The next controls examine where instrument response enters the representation, and whether prior-corrected rare-magnitude exposure improves end-to-end learning. They require their own reviews and fixed protocols; neither is accepted as novel by itself. The independent Chile TEAM-style baseline continues through its fixed 25+100 epoch budget before DEV scoring.

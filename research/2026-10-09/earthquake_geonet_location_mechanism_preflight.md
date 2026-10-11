# Geometry-distribution mechanism preflight

**The chosen synthetic geometry-integration experiment fails its fixed high-magnitude objective. No geometry fit is earned by this preflight.** It tests two seeds of4,096 invented events at three prescribed one/two/three-station snapshots, with both a base law and a locator-stress law. These are not measured1/3/5-second GeoNet waveforms.

Arrival-only location mixing fails all12 tail/bulk/median/CVaR guards. Correct joint conditioning improves ordinary and probability scores but still fails the all-snapshot tail objective. One base joint panel passes individually; it does not satisfy the complete gate. Original numerical results, failed panels and floating warnings are retained.

Two exact controls matter. If the conditional magnitude mean is linear in log distance, integrating the geometry gives the same mean as using expected log distance; the checked identity agrees within8e−15. Independently sampling each station's distance is also an incorrect substitute for one common source: in this toy it cuts average log-distance variance from.2091 to.0702 and creates impossible distance combinations.

This chosen synthetic failure is not a universal impossibility for nonlinear learned timing fusion. Ordinary current-arrival inputs remain a justified baseline option once waveform data support it. A future coupling test must share location supervision, out-of-fold predictions, observations, summaries and capacity with direct/point controls, and demonstrate tail improvement with bulk and worst errors preserved. Better density scores alone do not meet the project objective.

[Derivation, all failed comparisons and primary sources](phase2/geonet_location_mechanism_preflight/REPORT.md). Recovered inert calculation source plus a safe replay runner reproduce all three original calculation outputs byte for byte, including warnings. Twelve focused tests pass and code-only Codex autoreview is clean. The original aggregates remain immutable. [Replay instructions and recovery qualification](phase2/geonet_location_mechanism_preflight/REPRODUCTION.md). No real data, acquisition, fitted model or AWS resource was used.

autoreview findings: 2
[P2] Preserve hard deadline enforcement during child launch
work/geonet_clock_paired_check/paired.py:374
If Popen remains blocked when the soft deadline alarm fires, this handler only records the signal. The one-shot timer is then exhausted, and hard_watchdog is installed only after Popen returns and pending cancellation is raised. A stalled launch can therefore exceed the absolute 360-second limit indefinitely. Launch supervision must preserve child ownership while independently enforcing the hard deadline.

[P2] Include scoped amplitude identities in collision detection
work/geonet_clock_paired_check/projection.py:306
The collision registry contains event, origin and pick identities but excludes amplitude identities used to establish pick scope. For example, referenced amplitudes named `amp:A` and `amp A` both map to the same publicID, yet this parser returns an ok representation when their picks have distinct IDs. PROTOCOL_v1.md requires mapping collisions to produce unknown representations. Register scoped amplitude IDs and their references before applying the collision check so these unsupported projections cannot contribute content-matched resolution claims.

overall: patch is incorrect (0.94)
The launch guard can consume deadline enforcement during a stalled launch, and scoped amplitude mapping collisions escape the required conservative rejection. Review used read-only source inspection; no tests or acquisition were run.

The AWS numerical smoke checks passed; no real-data L fits have run yet.

| Check | Result | Seconds |
|---|---|---|
| Frozen fixture suite | 19 passed, zero failures/errors/skips | 10.07 |
| Independent probability scoring | 60 components at 1, 3 and 5 seconds | 15.07 |
| Producer optimizer | Exactly three synthetic Adam updates, 576 genuine parameters | 20.57 |

The source clocks include imports and verification. CPU float64 used the pinned Python3.9.25/NumPy2.0.2/SciPy1.13.1 runtime; the producer additionally used pinned Torch2.8.0+cu128 with CUDA hidden and one thread. Each child returned zero with full untruncated output, under its original resource and time limits.

The parent controller remains **INCOMPLETE**: after its successful numerical work, the combined cleanup command reported that its dormant stop service had already unloaded when the timer was stopped. That failure is preserved. Separate reconciliation confirms all three science services, the stop service and the timer are absent/inactive with empty service control groups. ROOT verified all28 read-only artifacts,35,126bytes, against their fetched hashes and checked each child return, stream custody and live limits. No numerical retry occurred.

This accepts narrow cold numerical readiness only. The bridge, ROOT input/manager custody checks and actual nine-stage L experiment still require their separate execution checks. These synthetic values are not earthquake accuracy evidence. The original shared-noise study remains independently negative on all36 fixed checks, and its results remain preserved.

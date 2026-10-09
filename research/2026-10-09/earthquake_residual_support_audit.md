# Is the residual-logit bound causing the remaining tail error?

9 October 2026. Completed CPU diagnostic on AWS; this is a hindsight bound, not a new predictor or a performance result.

The current residual head adds at most ±5 to each frozen logit. This allows an odds ratio to change by at most exp(10). We calculated the smallest and largest possible distribution mean independently for every record under that constraint. The resulting error floor is optimistic: it allows arbitrary corrections for each record and ignores shared neural-network capacity. A tanh head approaches the closed-box endpoints rather than attaining them exactly.

| Prefix | Overall MAE floor | M≥4 MAE floor | M≥5 MAE floor | M≥4 records whose true value is above the largest allowed mean |
|---|---:|---:|---:|---:|
| 1 s | 0.000686 | 0.023379 | 0.110399 | 6.91% |
| 3 s | 0.000746 | 0.017455 | 0.087882 | 6.23% |
| 5 s | 0.000732 | 0.009910 | 0.060219 | 3.99% |

Only one of 1,027 M≥4 records at 1 s, one at 3 s, and none at 5 s is provably unable to reach an M4 median because of the correction bound. The M≥4 error floors are much smaller than the measured static-head errors (.6861/.5512/.4869). The correction range therefore cannot explain most of the remaining aggregate error by itself. It can still constrain individual difficult records; this diagnostic does not prove that finite shared networks can learn the required corrections.

For ordered centers, the derivative of the weighted mean with respect to a bin multiplier has the sign of that center minus the resulting mean. An extreme mean therefore places maximum weight on one side of a threshold and minimum weight on the other. Enumerating all threshold vertices gives the extrema; projecting the true label onto the resulting interval gives the optimistic absolute-error floor. Zero-probability bins retain zero mass.

Four focused tests passed locally and on the original AWS worker. They include exhaustive comparison against all 32 vertices for nine five-bin distributions at four correction bounds, random interior corrections, zero support, known error floors and invalid input rejection. Codex autoreview returned no actionable findings. The final audit records code and input hashes and verifies that inputs do not change while read. No GPU, training checkpoint, model output, or validation selection was changed.

The reused validation comprises 96,993 recordings from 3,711 earthquakes, with only 13 M≥4 events and one M5.1. These bounds do not establish generalization, identifiability, or large-earthquake performance.

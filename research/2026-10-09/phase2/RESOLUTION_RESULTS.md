# Future-CDF and revision-head controls: first full-data seed

All four runs completed on the existing AWS A10G. Each uses all 979,487 TRAIN recordings, the same compact independent-prefix backbone, batch 512, seed 20261009, and ten fixed epochs. Validation never selects an epoch. The main objective is the existing magnitude-weighted Huber plus 0.075 cross-entropy; this is not a calibration guarantee. All runs allocate the same 8,385-parameter auxiliary head, including controls where it is inactive.

**Result:** squared-CDF-revision supervision improves recording-level MAE, median absolute error, M>=4 MAE, and worst-5% error over the matched supervised control at all three durations. Most of the gain is already achieved by ordinary future-CDF distillation. The revision head has mixed incremental effects compared with that stronger control; it is not a demonstrated general improvement or a novelty claim.

## Complete comparison

| Seconds | Control | MAE | MedAE | M>=4 MAE | CVaR95 | Event-macro MAE | CRPS |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 | supervised | 0.393184 | 0.295446 | 0.865396 | 1.400760 | 0.443843 | 0.279968 |
| 1 | cdf_distill | 0.389383 | 0.296545 | 0.846989 | 1.361218 | 0.444072 | 0.275551 |
| 1 | cdf_brier_gain | 0.389441 | 0.295337 | 0.855270 | 1.368525 | 0.444472 | 0.275673 |
| 1 | cdf_resolution | 0.388938 | 0.295052 | 0.847529 | 1.368975 | 0.444322 | 0.275280 |
| 3 | supervised | 0.340846 | 0.255801 | 0.712730 | 1.254101 | 0.374353 | 0.243371 |
| 3 | cdf_distill | 0.336678 | 0.252579 | 0.692486 | 1.221903 | 0.375499 | 0.239188 |
| 3 | cdf_brier_gain | 0.337269 | 0.253855 | 0.686971 | 1.224000 | 0.376838 | 0.239418 |
| 3 | cdf_resolution | 0.336767 | 0.254015 | 0.681420 | 1.219647 | 0.375869 | 0.238854 |
| 5 | supervised | 0.318531 | 0.235684 | 0.653386 | 1.201044 | 0.349552 | 0.228315 |
| 5 | cdf_distill | 0.314609 | 0.233111 | 0.616272 | 1.178564 | 0.347447 | 0.224538 |
| 5 | cdf_brier_gain | 0.315057 | 0.233878 | 0.609718 | 1.181839 | 0.348096 | 0.224876 |
| 5 | cdf_resolution | 0.315421 | 0.234075 | 0.604896 | 1.181090 | 0.348319 | 0.224727 |

The main table uses the distribution mean as its decision; MedAE means the median absolute error of that decision. The JSON also reports a separate distribution-median decision, which must not be conflated with MedAE or selected after observing the results.

## Increment attributable to the revision head

| Seconds | Delta MAE | Delta MedAE | Delta M>=4 MAE | Delta CVaR95 |
|---|---:|---:|---:|---:|
| 1 | -0.000446 | -0.001493 | +0.000540 | +0.007757 |
| 3 | +0.000089 | +0.001436 | -0.011066 | -0.002256 |
| 5 | +0.000813 | +0.000964 | -0.011376 | +0.002526 |

Negative changes favor the revision head. The 3- and 5-second rare-magnitude gains are about 0.011 and 0.011 magnitude units; the one-second rare-magnitude error is essentially unchanged. Worst-5% error improves only at three seconds versus distillation. At one second, event-macro MAE remains slightly worse than the supervised control despite better recording-weighted MAE. The single M>=5 validation event does not provide robust evidence about damaging large earthquakes.

## What was tested

- `supervised`: original supervised loss only.
- `cdf_distill`: additionally matches the frozen later teacher CDF at 1->3 and 3->5 seconds.
- `cdf_brier_gain`: also predicts realized improvement in threshold Brier scores through a shared auxiliary head.
- `cdf_resolution`: instead predicts squared later-minus-current CDF changes. Both auxiliary targets are detached and remain unclipped; the nonnegative head cannot express negative expected Brier gain.

The five-second output has no later teacher target, but shares the representation with earlier windows. Training targets come from the actual longer prefix of the same record. Audited legacy teachers are frozen; their historical training used validation for selection, and training-record targets may reflect memorization. A clean future benchmark needs event-disjoint or cross-fitted teachers.

## Prior art and limits

[DIME (ICLR 2024)](https://arxiv.org/abs/2306.03301) already studies learned conditional value/variance prediction. [Foo and Chang (August 2026)](https://arxiv.org/abs/2608.03163) explicitly study conditional forecast-revision scale, squared-risk reduction, and supervised prediction of revision scale. [SSATKD](https://arxiv.org/abs/2501.01921) uses a squared teacher/student CDF loss. The conditional-expectation identity behind a squared-revision target is standard Rao-Blackwellization for an ideal nested teacher; it is not new mathematics, and it fails as a calibration guarantee for imperfect teachers.

Only a narrowly scoped EEW auxiliary-training contribution remains a hypothesis. It requires repeat seeds, a detached-head control, stronger ordinary auxiliaries, and independently locked earthquake evaluation. This validation has 13 M>=4 events, one M>=5 event, and no M>=6 event. Whole-record preprocessing in the original INSTANCE files also limits operational causality claims.

## Provenance

- `supervised`: `results/2026-10-09/phase2/resolution_supervised_seed20261009_50be4ca3df5f_b41d58215139`, 506.5 seconds including audit/load/evaluation.
- `cdf_distill`: `results/2026-10-09/phase2/resolution_cdf_distill_seed20261009_575b542bf64c_ea40c6efbc0a`, 516.0 seconds including audit/load/evaluation.
- `cdf_brier_gain`: `results/2026-10-09/phase2/resolution_cdf_brier_gain_seed20261009_49066d636c96_5b7884203b4d`, 527.0 seconds including audit/load/evaluation.
- `cdf_resolution`: `results/2026-10-09/phase2/resolution_cdf_resolution_seed20261009_418ccb71f29b_4462c23e6a3e`, 553.4 seconds including audit/load/evaluation.

All code passed focused model/runner tests and isolated Codex autoreview before launch. Completed metrics, histories, hashes and logs are retained; waveform arrays and checkpoints remain outside Git.

## Auxiliary-head diagnostics

The revision head approximately matches mean held-out revision energy: predicted/observed integrated values are0.04794/0.04693 for1->3s and0.03701/0.03831 for3->5s. Correlation with observed revision is0.284/0.297, but correlation with actual absolute-error improvement from waiting is only0.063/0.010. It should therefore not be advertised as a validated waiting or alert policy. These are descriptive diagnostics against imperfect teachers, not uncertainty guarantees.

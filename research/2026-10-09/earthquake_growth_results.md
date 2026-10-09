# Future-growth supervision: completed matched negative result

**The conditional future-growth likelihood does not pass the intended objective.** It worsens bulk MAE and median absolute error at all three durations, and worsens M≥4 error at 5 seconds. Plain future-growth regression gives small tail improvements, but worsens CVaR95 at all durations and bulk error at 5 seconds. No candidate is promoted from this grid.

The experiment asks whether predicting the remaining rise of the vertical running peak up to 10 seconds during TRAIN can improve a magnitude distribution inferred using only the observed 1-, 3- or 5-second prefix. Every arm uses the same strong static instrument residual, selected 197,676 training records, two fixed seeds, 15 epochs, optimizer and initial magnitude model. The auxiliary coefficient is fixed at 0.05. Inference never reads the later peak or true magnitude. The target archive covers every TRAIN row, with 979,485 valid targets out of 979,487; fitting uses the selected rows and masks invalid targets.

| Seconds | Control | MAE | MedAE | M≥4 MAE | CVaR95 |
|---|---|---:|---:|---:|---:|
| 1 | supervised | 0.377325 | 0.281630 | 0.709830 | 1.358248 |
| 1 | growth_mse | 0.377112 | 0.281117 | 0.705911 | 1.358798 |
| 1 | unconditional_nll | 0.379831 | 0.283720 | 0.704740 | 1.361768 |
| 1 | conditional_nll | 0.379719 | 0.283306 | 0.705257 | 1.361067 |
| 1 | conditional_detached | 0.377325 | 0.281630 | 0.709830 | 1.358248 |
| 3 | supervised | 0.329443 | 0.243162 | 0.588089 | 1.232876 |
| 3 | growth_mse | 0.329150 | 0.242503 | 0.580545 | 1.236270 |
| 3 | unconditional_nll | 0.331404 | 0.244866 | 0.581235 | 1.239013 |
| 3 | conditional_nll | 0.331183 | 0.244851 | 0.582645 | 1.238176 |
| 3 | conditional_detached | 0.329443 | 0.243162 | 0.588089 | 1.232876 |
| 5 | supervised | 0.299253 | 0.212464 | 0.505174 | 1.201221 |
| 5 | growth_mse | 0.299750 | 0.212808 | 0.499781 | 1.202074 |
| 5 | unconditional_nll | 0.301155 | 0.213561 | 0.508261 | 1.201484 |
| 5 | conditional_nll | 0.301284 | 0.213654 | 0.507436 | 1.202163 |
| 5 | conditional_detached | 0.299253 | 0.212464 | 0.505174 | 1.201221 |

Each row uses the mean of two probability vectors and its distribution mean. The hurdle likelihood predicts a zero-growth atom and lognormal positive growth. `conditional_nll` additionally conditions the TRAIN growth head on the true magnitude bin. `conditional_detached` fits that same auxiliary with its features detached, preventing any gradient into the magnitude model.

A direct AWS check found that **all saved probability arrays match bitwise** between the supervised and detached arms, including each seed and the ensemble, at all three durations. They also exactly reproduce the earlier static instrument baseline. This gives a concrete negative control for this experiment, distinct from the older recurrent resolution experiment's CUDA reproducibility issue.

The result does not rule out every future-target loss or coefficient. It rejects this prespecified construction as evidence for the desired advance; repeated tuning on the same 13 high-magnitude validation events would not establish an independent discovery. Conditional density auxiliary training and future supervision are established methods, so the failed experiment is not presented as a novel method.

The next observation-likelihood experiment instead uses newly arriving waveform blocks at inference. It will compare censored and uncensored observations, a free zero-mass model, a direct discriminative update, and the unchanged 1-second start. A separate affine-prefix experiment tests sensitivity to released-waveform preprocessing.

## Provenance

- `instrument_growth_1s_eb2a875f333c_ae996f5a66d0`
- `instrument_growth_3s_c95814006236_e6d3b50b7118`
- `instrument_growth_5s_ef603c3a4d7a_9bf452d3c157`

Reviewed implementation: commit `e3b6aaf`; ten focused CPU tests and clean Codex review before launch. Probabilities, checkpoints, row identities, target digests, source hashes, masks and per-seed results are preserved. This is reused exploratory INSTANCE validation; no new TEST evaluation occurred.

# TRAIN-only amplitude-distribution experiment: negative result

The four-parameter amplitude/observation-age likelihood failed the frozen improvement gate at **1, 3 and 5 seconds**. All five outer folds selected lambda100, the strongest fixed regularization. Posterior predictions were almost the prior; differences were roughly one hundred-thousandth of a magnitude, with no meaningful high-Mw gain. This is a negative result for this observable/model/cohort, not proof that early waveforms contain no information.

| Duration | High Mw>=5.5 MAE, model | Prior | Bulk MAE, model | Prior | NLL, model | Prior |
|---|---:|---:|---:|---:|---:|---:|
| 1s | 0.48261039 | 0.48259642 | 0.70023461 | 0.70022222 | 1.41274595 | 1.41272892 |
| 3s | 0.48260187 | 0.48259642 | 0.70022881 | 0.70022222 | 1.41274241 | 1.41272892 |
| 5s | 0.48259729 | 0.48259642 | 0.70022511 | 0.70022222 | 1.41273891 | 1.41272892 |

The fixed common TRAIN cohort contains34events/25 operational groups,26Mw>=5.5 (24>=6) and8lower. Metrics weight groups equally, then events within each group. They describe this selected TRAIN cohort; they are not natural-population or external-benchmark scores. The original65rows/195cells remain;24DEV have no extracted amplitude values or predictions, seven non-common TRAIN rows remain explicit.

Five outer group folds, four inner group folds, five lambdas and one final fit per outer fold produced exactly105 successful fits. Folds are fixed by opaque group SHA rank, all parameter/prior/scaler selection uses fitting groups only, no DEV selection, no restarts. Every common event has all three horizons. All102observations are uncensored, so independent closed-form Gaussian posterior replay verifies816 saved mean/median/NLL/CRPS scalars to maximum absolute difference2.22e-16, plus held-group exclusions and group-weighted pooled MAE/NLL/CRPS/bias. This shares actual inputs and author with the producer; it is arithmetic independence, not an independent population test. No new fit was needed for replay.

The exact root protocol was published before native feature extraction; statistical source was reviewed, tested and published before its actual invocation. V1 synthetic tests preserved31LinuxPASS/one exact floating-point assertion failure; V2 changes only that invented tolerance, leaving model, processing, schema and proposal byte-identical, and passes32local/32Linux tests with clean default Codex review1. The first statistical wrapper failed before any fit because native component names were not converted to the schema integer. A separate V3 wrapper uses the exact positively qualified literal channel order. Original features and failed wrapper artifacts are preserved. Neither correction changes the scientific gate or values.

The sole successful science unit returns normally in3.146seconds,105fits, zero full-TRAIN continuation because the gate failed, zeroDEVpredictions and zero requests. Live1GiB/swap0/32tasks/threads1,900second study/960second manager stop and empty own cgroup after return were verified. It uses the existing AWS host; no new instance/GPU or worker restart.

The earlier six-fit waveform CNN remains negative. The receiver-activity study still has four off-transition groups against the frozen five required. These are separate retained failures.

Next: broader fixed TRAIN coverage under a new prospective protocol, plus a narrowly controlled uncertainty-aware observation likelihood if justified. The fixed50extension can add14near-tail[5.5,6) and36lower events, **no newMw>=6**; its maximum84common TRAIN and improved mixture are ceilings until qualification. Noise uncertainty, Student-t regression, hierarchical likelihoods and sequential Bayesian inference are established prior art; a novel contribution needs a distinct mechanism and matched ablation gains on independent data. No novel winner or published superiority is claimed.

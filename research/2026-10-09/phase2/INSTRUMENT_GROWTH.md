# Future growth supervision on the instrument-conditioned residual head

This is a fixed empirical multitask ablation against the stronger static-instrument baseline. No methodological novelty or earthquake performance improvement is asserted by the implementation.

## Unchanged magnitude path

`instrument_growth.py` reuses `instrument_residual.extract` and its TRAIN-only weighted normalizer. Every arm uses 291 inputs: 245 original logits/hidden/prefix features, all 34 allowed static instrument/site fields, and 12 native-amplitude slots forced to zero **after** the common normalization. Frozen waveform backbones, inventory joins, selected records, weights, validation reference checks and masks are unchanged. Each 1/3/5 s model is independent.

Defaults match the successful instrument run: up to four random records per event plus all M>=4 records (197,676 total), inverse inclusion weights normalized to mean one, seeds 20261009/20261010, 15 fixed epochs, batch 2048, AdamW learning rate .0005 and weight decay .0001. The supervised objective is exactly

`mean(w * [(1 + 5 max(M-3.5,0)) Huber(mean(p),M; delta=.5) + .075 CE(p,bin(M))])`.

Anchor defaults to zero. This is decision-oriented and does not provide a proper-probability calibration guarantee. Final epochs and auxiliary weight are fixed before results, with no validation selection. Nondefault CLI settings are recorded and must be reported as a different protocol. Expected TRAIN count defaults to 197676 and fails closed on mismatch.

## Five matched controls

All arms allocate an identical 65->64->4 auxiliary network, fed the residual head's 64-dimensional hidden state and one conditioning scalar. It has no dropout. Auxiliary initialization restores CPU RNG, preserving the exact residual initialization and subsequent dropout draws. Magnitude and auxiliary optimizers/clipping are separate; shared-state gradients from a connected auxiliary still update the residual representation.

| Control | Additional TRAIN loss, multiplied by fixed .05 |
|---|---|
| `supervised` | None. Exact replay of `instrument_residual.fit_one(..., mask=instrument)` is tested. |
| `growth_mse` | Squared error of a softplus nonnegative growth prediction; condition scalar is zero. |
| `unconditional_nll` | Hurdle/lognormal negative log likelihood `-log q(G|h)`; condition scalar is zero. |
| `conditional_nll` | `-log q(G|Y,h)` using the true magnitude **bin** only inside the TRAIN auxiliary loss. |
| `conditional_detached` | Same conditional density with detached `h`; auxiliary learns, but magnitude updates must exactly match supervised. |

The conditional scalar is `(bin+.5)/66-.5`, using the same clipped bins as supervised CE. Every arm has the same parameter count, minibatch order, magnitude dropout stream and magnitude initialization. Output 0 supplies the MSE mean; outputs 1–3 supply zero logit, positive-log-growth location and scale. Unused outputs remain allocated. Shared numeric bounds: sigma in [.1,5], lognormal location clamped to [-20,10]. Probability at exactly zero is the hurdle atom; positive growth includes the lognormal Jacobian. The borrowed `future_growth.hurdle_log_prob` implements this density.

Auxiliary loss is the inverse-weighted mean over **all** selected minibatch rows; missing targets contribute zero, without dropping records or renormalizing to observed targets. The reported auxiliary history is unscaled, and total loss includes .05 times that history. No marginal-growth mixture score is included: earlier synthetic analysis showed that it can bias tail prevalence and worsen bulk error.

Deployed `forward(features, original_logits)` accepts neither labels nor future values. It returns only magnitude logits through the unchanged bounded residual correction. The auxiliary density normalizes independently, so `p(M,G|prefix)=p(M|prefix)q(G|M,h)` has magnitude marginal `p(M|prefix)` at fixed parameters. Training can change the shared representation; this is the only proposed benefit of conditional NLL. It is not Bayesian feedback from unseen future observations.

## Target identity and causality

The separate reviewed `train_future_growth.py export` produces TRAIN-only vertical-component running-peak log growth from each 1/3/5 s prefix to 10 s. It uses the SAME preceding-1-s mean as baseline for every peak and records the zero atom, missingness reasons, raw-window hashes and exact raw/5s-cache alignment. No VAL or TEST growth is exported or used.

Use the all-TRAIN export, currently intended as `/mnt/eew-research/runs/growth_train_all979487.npz`. The independent-backbone exporter samples numeric event groups when asked for a subset, while the instrument baseline samples string event groups. These can select different records. This runner preserves the **instrument** sample and uses `train_future_growth.load_targets` to map that exact subset from the archive. Incomplete coverage fails; there is no resampling or silently dropping rows.

The adapter checks extracted row/event/trace/label identities against TRAIN metadata, archive array digests and peak-derived growth, shared audit and normalization hashes, and unchanged raw/5s-cache file identities. It records archive SHA256 plus selected row/growth/mask digests and per-horizon missing/zero counts. Whole-release preprocessing (120 s detrending/resampling), manual P alignment and historical availability of archived static metadata remain shared benchmark limitations. Static site information may encode station/domain priors; auxiliary growth does not resolve that confound. A local peak increase is not a direct rupture-duration or completion label.

## Run after review, in the parent's training queue

```bash
.venv/bin/python research/2026-10-09/phase2/instrument_growth.py \
  --seconds 1 --targets /mnt/eew-research/runs/growth_train_all979487.npz \
  --inventory /path/to/pinned/responses.tgz --device cuda
```

Repeat the same fixed command for 3 and 5 seconds. Extraction occurs once per invocation; all requested controls/seeds then share those feature arrays. `--controls` can split an execution queue, but all five controls must be reported for the planned comparison. Actual reviewed inventory path is supplied by the parent; its SHA256 remains pinned to the audited archive.

Each unique run saves all seed and ensemble probabilities, mean/median decisions, metrics, exact selected training rows/weights, separate supervised/auxiliary/total histories, checkpoints with normalizer/mask, source hashes, target provenance and an output SHA256 manifest. Raw baseline probabilities are also saved. VAL is reused exploratory material; no superiority claim over literature follows from these runs. Compare tail event-macro error, bulk/median error, CVaR, bias, FPR and distribution scores against the exact `supervised` arm and the stronger existing baseline. The detached arm must be identical; any disagreement is an implementation problem.

## Attribution and interpretation

Shared-representation auxiliary tasks are established [multitask learning](https://link.springer.com/article/10.1023/A:1007379606734). Conditional likelihood factorization is ordinary probability, and continuous conditional densities have long been modeled with [mixture density networks](https://publications.aston.ac.uk/id/eprint/373/). EEW already uses probabilistic [TEAM-LM magnitude distributions](https://arxiv.org/abs/2101.02010), and unresolved rupture tails are discussed by [Münchmeyer et al. 2022](https://arxiv.org/abs/2203.08622). Predicting later waveform growth as privileged training information and conditioning an auxiliary on a label are not asserted to be new principles. This experiment asks whether that supervision adds value beyond the demonstrated instrument-conditioned representation; negative results should be preserved.

Focused verification: `CUDA_VISIBLE_DEVICES='' .venv/bin/python -m unittest discover -s tests -p test_instrument_growth.py -v`. Tests cover two-seed exact baseline replay, detached-update equality under a large auxiliary weight, RNG/dropout identity, masks/weights, target identity/coverage/missingness, and complete CPU output artifacts using synthetic features. The end-to-end runner fixture mocks baseline waveform extraction; no real training is launched by tests.

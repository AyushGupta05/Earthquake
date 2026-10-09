# Shared-cap contrast preflight: negative result

**Do not advance this construction to GPU/posterior training on the present evidence.** The fixed follow-up gate failed. Keeping a three-state cap mixture did not consistently improve conditional observation likelihood over an independently fitted Gaussian with the same moment model. This pilot tested density of observed amplitude contrasts given true magnitude; it never predicted magnitude. There is no 1-second improvement, magnitude MAE result, physical rupture-state identification, or novelty claim.

## Design and boundaries

The protocol was fixed locally before loading real TRAIN targets, at 2026-10-09 20:43:19 UTC, SHA256 `92b54f5f57cec682956ce5a0e2d584292cd85a83c8d7980ce9336bdc0e282c21`. It was not externally registered. After tests and a clean Codex autoreview, real fitting began at 20:52:14 UTC and completed in **92.84 seconds**, using one CPU thread with CUDA uninitialized. No GPU, VAL, TEST, raw-waveform read, or existing trainer edit occurred.

The pinned source was `train_observations.npz`, SHA256 `16e40eb8c69d1bbcbad107d11241d0c2670ae93313ba1f061c11d00cec202612`, from the earlier censored pilot. It contains 197,676 records / 47,273 TRAIN events. Source validity/floor masks were preserved. Event identities determine a fixed SHA256 two-fold split; folds reverse roles, with separate acceleration and velocity fits. The two seeds are optimizer initializations, **not two independently sampled event splits**. Fit and evaluation both give equal weight to eligible events within unit strata.

Signed saved innovations recover `d=(b-a,c-a)`, where `a,b,c` are log10 vertical block peaks over [0,1), [1,3), [3,5). Their source baseline is the first ten post-P samples. A common scalar log-gain/intercept cancels; frequency-dependent response/site/path effects do not. At 3 seconds, only the first contrast is scored and the future coordinate is replaced by NaN. At 1 second, no contrast exists and the likelihood is identically one. Source-native floor exclusions and catalogue-pick/full-record preprocessing limitations remain.

The empirical conditional mean for shared cap offset ξ is `b_j + κ[min(M,s_j+ξ)-min(M,s_1+ξ)]`, with fixed offsets −0.5, 0, +0.5 and fitted ordered caps, weights, offsets, and full residual covariance. A single state is shared across both contrast coordinates. `shared_cap` keeps its normalized mixture; `moment_matched` independently fits the exact first-two-moment Gaussian of that same 11-parameter family, from byte-identical starts. `linear_gaussian` is a 7-parameter coarse reference. `moment_match_from_shared_cap` is an evaluation-only Gaussian at the mixture's fitted parameters. All Gaussian determinants are included. No held-fold selection, tuning, or reoptimization was performed.

## Main result

Δ is **mixture NLL minus independently fitted moment-matched Gaussian NLL**; negative is better. Numbers below pool held events across the two folds with equal event weight. Confidence intervals use the fixed 500-resample paired event bootstrap and condition on the fitted models; they do not include training-refit uncertainty. The protocol's tail/3-second sign checks use the specified average of fold means; they reach the same rejection.

| Native unit / initialization | 5s ΔNLL, all events | Paired bootstrap 95% interval | 5s ΔNLL, M≥4 |
|---|---:|---:|---:|
| Velocity / 20261009 | −0.0000693 | [−0.0001395, +0.0000015] | +0.0117034 |
| Velocity / 20261010 | −0.0000758 | [−0.0001561, +0.0000117] | +0.0115647 |
| Acceleration / 20261009 | +0.0009905 | [+0.0005419, +0.0014444] | +0.0259832 |
| Acceleration / 20261010 | +0.0000322 | [−0.0006062, +0.0006073] | −0.0128866 |

Velocity has only a tiny, statistically inconclusive bulk difference and worse M≥4 likelihood in both starts. At 3 seconds, its pooled tail deterioration is +0.00968 / +0.00816. Acceleration is unstable across starts and folds; start 1 also worsens 3-second bulk likelihood. The mixture loses the 5-second all-event comparison in 3 of the 8 unit/fold/start cells; none of the four pooled bootstrap comparisons satisfies the specified upper-CI<0 gate. All unit/fold support requirements were met.

The same-parameter shape comparison is also unpersuasive: mixture-minus-Gaussian 5-second NLL is about −0.000128 / −0.000138 for velocity, but +0.000197 / +0.000102 for acceleration. Velocity M≥4 differences are only −0.000037 / −0.000029 in this comparison; its poorer tail result against the independently fitted control comes mainly from the fitted moment/covariance parameters, not a useful tail-shape gain. A shared-state mechanism is not established by a generic mixture-versus-Gaussian comparison in any case.

The coarse affine reference is worse than the refitted moment Gaussian for velocity (5-second pooled NLL about −0.06148 versus −0.06694), but better in acceleration bulk (about −0.09829 versus −0.09727 / −0.09717). This is additional reason not to promote the cap construction from a single favorable comparison.

## Support and optimization limits

At 5 seconds, eligible velocity support is 47,043 events, including 323 M≥4 and 30 M≥5; acceleration has 25,113 events, including 262 M≥4 and 28 M≥5. These unit groups overlap in events and must not be added as independent support. The source magnitude range reaches 6.5 in one fold, but these are the source catalogue magnitude labels, not a newly homogenized Mw catalogue. This is entirely held-TRAIN likelihood evaluation and does not change the separate VAL/TEST support limitations.

All 24 fits and scores were finite. However, **7 fits hit the 100-iteration limit and 1 reached the evaluation limit**; PyTorch's strong-Wolfe search completed that iteration at 146 function calls despite `max_eval=140`. No fit met the stringent gradient-norm stopping threshold 1e−7; other fits generally stopped on objective/step-change criteria. The hard `min` response is nonsmooth, and fitted cap parameters vary substantially across acceleration starts. These are material optimization/identifiability limitations. The negative conclusion is that this prespecified pilot did not earn a follow-up, not a proof that a globally optimized cap-mixture family could never help. No retrospective optimizer enlargement or start selection was used.

## Verification and saved evidence

- **17 focused tests passed**, with RuntimeWarning and UserWarning treated as errors: signed contrast recovery, gain invariance away from floors, no future-coordinate dependence, full Gaussian determinant, exact moments, numerical mixture normalization, magnitude-uninformative null, single-component/covariance-floor limits, independent fitting, split/identity/floor gates, and event-weighted scoring.
- Actual bundled Codex autoreview exited 0 with no findings on an isolated snapshot. Command: `/Users/ayush/.codex/skills/autoreview/scripts/autoreview --mode local --engine codex --codex-bin /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex --no-web-search --prompt-file ../review_context.txt --output ../review_result.txt --json-output ../review_result.json`. Review did not run the tests; the separate AWS CPU test log is saved.
- The independent local audit verified **all 70 manifest files / 100,186,452 bytes**, all source array hashes and event-fold assignments, and all 64 per-row score archives (**3,161,928 row scores**). Exact source row/event/trace/target/mask alignment passed. Recomputed event NLL summaries matched with maximum absolute error **0**. All eight matched cap/Gaussian pairs had identical initialization hashes.
- `run_20261009/` contains fit logs, all starts, scores, PIT histograms, per-row likelihoods, source identities/masks, protocol/code/runtime provenance, decision checks and the SHA256 manifest. `independent_artifact_audit.json`, `pooled_summary.json`, `tests.log`, and `review_result.json` contain the independent audit and review evidence. No datasets belong in Git; the small code, protocol, memo, and JSON summaries are sufficient for repository provenance.

## Relation to the proposed method

The distinguishing construction was a likelihood mixture over shared uncertain cap response, compared with averaging its response into a Gaussian. [Trugman et al. (2019)](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf) already model magnitude-dependent early-amplitude saturation and use Bayesian inference; [RTMag](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007JB005386) already uses probabilistic real-time magnitude inference and saturation handling. Generic latent mixtures, nuisance projection, and sequential likelihood algebra are established ideas. The preceding `work/instrument_research/shared_cap_state_recommendation.md` records the narrower construction and nearby shape/amplitude prior art. This pilot supplies no empirical basis for advancing that construction as a new EEW magnitude method.

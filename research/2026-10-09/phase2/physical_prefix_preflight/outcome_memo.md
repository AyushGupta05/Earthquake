# Outcome: causal physical-prefix preflight

**Decision:** correctness and identifiability gates pass; the proposed covariance correction does not demonstrate the desired tail-plus-bulk improvement. Do not advance a covariance-only GPU method on the basis of this toy. Preserve it as a falsification fixture for any later physical likelihood. This is not a real EEW benchmark or a novelty claim.

The unchanged local protocol was pinned before results: `511f8678157e6d36f24ab79a79361755fd61bbc0ca74c2bb8acf528a6e1955a9`. Exact equations, priors, observation operators, failure tolerances and reproduction commands are in `README.md` and `protocol.json`. This is local prespecification, not an external registry.

## Completed checks

- Local CPU only; 0.262 seconds simulation, 48 conditions, 12 compressed prediction artifacts, 4,635,044 NPZ bytes. No real records, TEST, GPU, live trainer or shared repository were touched.
- All 14 focused tests pass with RuntimeWarnings treated as errors. The actual Codex autoreview helper returned exit 0 and zero findings on an isolated immutable code snapshot. No review fixes or rejected findings were needed.
- All causal source/noise prefix discrepancies are exactly zero. Both causal arms have exactly zero log likelihood-ratio discrepancy within each indistinguishable final-magnitude family, across both sensors, all deadlines and both seeds. Maximum conditional-null posterior error is 3.06e-16.
- All 12 artifact SHA256 hashes verified; log-probabilities finite; maximum probability-sum error 5.56e-16. An independent CDF-integral calculation of CRPS agrees with the reported energy-form CRPS within 4.45e-16 across all 48 conditions and both population weightings.
- The deliberately wrong complete-event template fails every null condition: maximum absolute log likelihood contrasts to the first null hypothesis range from 41.4 to 1.36e8. This only validates the negative control. It is not evidence against a published early spectral estimator.
- Source covariance is zero; noise covariance is identical for every magnitude hypothesis. Off-diagonal coefficient correlations reach 0.544 in the velocity-like operator and 0.437 in the acceleration-like operator. All six prefix covariance matrices are positive definite. Full normalized Gaussian determinants are retained.

## Fixed-prior population results

Entries below are the arithmetic average of the two independently simulated seed risks, not an ensemble prediction. The population weighting uses the protocol prior; the balanced-duration diagnostics are separate. Columns show diagonal → full covariance under the same correct causal mean.

| Toy sensor | Time | Mean MAE | Mean MedAE | Median MAE | Tail mean MAE (M≥5) | CRPS | CVaR95 mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| velocity_like | 1s | 0.368310 → 0.327140 | 0.236139 → 0.236483 | 0.280300 → 0.230245 | 2.146447 → 2.402521 | 0.209518 → 0.176661 | 1.414501 → 1.299431 |
| velocity_like | 3s | 0.292490 → 0.290488 | 0.205836 → 0.204364 | 0.202114 → 0.198821 | 0.287225 → 0.285638 | 0.154524 → 0.153083 | 1.054804 → 1.056471 |
| velocity_like | 5s | 0.291838 → 0.291813 | 0.205560 → 0.207225 | 0.200785 → 0.201595 | 0.079780 → 0.079780 | 0.154241 → 0.153948 | 1.061595 → 1.058963 |
| acceleration_like | 1s | 0.326875 → 0.327388 | 0.234374 → 0.233000 | 0.231353 → 0.229994 | 2.382060 → 2.398156 | 0.176735 → 0.176849 | 1.292415 → 1.299548 |
| acceleration_like | 3s | 0.296412 → 0.292839 | 0.202295 → 0.204235 | 0.203325 → 0.200558 | 0.286098 → 0.285152 | 0.156974 → 0.154986 | 1.089164 → 1.069092 |
| acceleration_like | 5s | 0.294135 → 0.293412 | 0.201776 → 0.207543 | 0.200221 → 0.200682 | 0.079780 → 0.079780 | 0.155300 → 0.154978 | 1.077694 → 1.066895 |

Full covariance has lower population categorical NLL in 11/12 seed×sensor×deadline comparisons, lower CRPS in 8/12, lower mean MAE in 10/12, lower mean MedAE in only 5/12, and lower CVaR95 in 7/12. Tail MAE is lower in 6/12, higher in all four 1-second comparisons, and exactly tied in both velocity-like 5-second comparisons. Some nominal 5-second tail improvements are only numerical-scale differences below 5e-7, not useful gains. All median-estimate MedAEs are zero because the discrete population prior assigns 73.4% mass to its lowest-magnitude class; those zeros are not a real-world accuracy result.

## Every seed, including reversals

Full-minus-diagonal differences; negative is better for these error/score columns. No seed or deadline was selected after seeing results.

| Seed | Sensor | Time | Δ mean MAE | Δ mean MedAE | Δ median MAE | Δ tail mean MAE | Δ CRPS | Δ CVaR95 |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 20261009 | velocity_like | 1s | -0.031902 | +0.002755 | -0.042009 | +0.235304 | -0.022737 | +0.006053 |
| 20261009 | velocity_like | 3s | -0.001472 | -0.000556 | -0.001061 | -0.002880 | -0.000524 | +0.014899 |
| 20261009 | velocity_like | 5s | +0.000427 | +0.004467 | +0.000689 | +0.000000 | +0.000099 | +0.004267 |
| 20261009 | acceleration_like | 1s | -0.000048 | -0.005754 | -0.000140 | +0.013777 | +0.000061 | +0.007395 |
| 20261009 | acceleration_like | 3s | -0.004457 | +0.003531 | -0.002885 | -0.001867 | -0.002067 | -0.019655 |
| 20261009 | acceleration_like | 5s | -0.000868 | +0.009010 | -0.000884 | -0.000000 | -0.000701 | -0.010147 |
| 20261010 | velocity_like | 1s | -0.050439 | -0.002066 | -0.058101 | +0.276844 | -0.042977 | -0.236192 |
| 20261010 | velocity_like | 3s | -0.002531 | -0.002389 | -0.005525 | -0.000295 | -0.002359 | -0.011564 |
| 20261010 | velocity_like | 5s | -0.000476 | -0.001137 | +0.000930 | +0.000000 | -0.000685 | -0.009530 |
| 20261010 | acceleration_like | 1s | +0.001075 | +0.003005 | -0.002578 | +0.018415 | +0.000168 | +0.006872 |
| 20261010 | acceleration_like | 3s | -0.002689 | +0.000349 | -0.002651 | -0.000026 | -0.001909 | -0.020488 |
| 20261010 | acceleration_like | 5s | -0.000580 | +0.002523 | +0.001806 | -0.000000 | +0.000056 | -0.011452 |

## Interpretation and limits

The full covariance is the exact data-generating covariance, so a proper-score advantage under the matching prior is expected in population. Even here the finite Monte Carlo comparisons are not uniformly positive. Better population density estimation does not imply lower conditional rare-magnitude error, lower MedAE, or lower CVaR. At one second, the velocity-like full-covariance posterior improves mean MAE by 0.0412 on average while increasing tail mean MAE by 0.2561; the acceleration-like mean bulk error and tail error both get slightly worse. This fails the requested universal tail-plus-bulk objective.

The grid was deliberately sampled in balanced form to expose conditional behavior, while inference uses a steep fixed population prior. Full covariance lowers balanced NLL/CRPS/mean MAE in only 4/12 conditions, all acceleration-like 3/5-second cases. This does not contradict proper scoring: the balanced evaluation distribution has a different source prior. Reweighting or changing the prior after inspecting these results would be a new experiment, not a rescue of this one.

The largest final magnitudes cannot be separated within the causal-null family. At one second the indistinguishable duration set is {2.5,4,7,12,20,40}; at three seconds it is {7,12,20,40}; at five seconds it is {12,20,40}. Their conditional posterior remains the fixed conditional prior. In the five-second set its mean is 5.7313709655 and median 5.5563025008. If an oracle perfectly identifies the observable equivalence class while preserving this unresolved conditional prior, its tail mean-estimate MAE is 0.0797800955341, exactly the value achieved numerically by both five-second velocity-like arms. This is an equivalence-class reference for the posterior mean, not a universal lower bound on MAE: using the conditional median gives 0.0578405692622. A tail-policy change could alter conditional error, but it does not create missing information about final magnitude.

The complete-template controls do not consume future observations. Instead they deliberately assume the wrong mapping from a final source hypothesis to the observed prefix. Their failure illustrates why an explicit prefix observation operator matters. They are not faithful implementations of Caprio et al. (2011), who already made real-time spectral updates. Generic waveform likelihoods, covariance propagation, Bayesian nuisance marginalization and finite-window spectral correction are existing ideas. Their existence does not automatically defeat a specific new EEW method, but this experiment has not established a distinct useful one.

Important constructed advantages/limits: the correct source family, response operators, nuisance prior, noise law and all initial states are known; the source is deterministic with no stress-drop/path/source variability; only nine coefficient dimensions are used; real sensor responses, unknown baselines, aftershocks, catalog magnitude types and event/station transfer are absent. Two seeds with 128 replicates per class are a bounded diagnostic, not uncertainty-qualified performance evidence. No significance or robustness claim is made.

## Next scientific decision

Do not spend a new GPU run on full covariance alone. A narrowly differentiated EEW construction remains possible: explicitly map a transient source distribution through a known causal instrument response, infer only the actually observed prefix, and propagate causally estimable nuisance uncertainty into a full magnitude distribution. The differentiating claim would be that this particular construction improves sensor-transfer and partial-rupture errors under event-held-out evaluation, not that Gaussian likelihoods or covariance are new.

Before implementing that construction, require a cheap real-data diagnostic on already permitted TRAIN/validation records: does a physically justified response/gain normalization leave stable, measurable coefficient correlations that matter after conditioning on available source/path information? Compare against plain sensitivity/unit correction and the same causal model with diagonal covariance. Use paired records of the same event where possible and a held-out station/response family to distinguish sensor corrections from station priors. Full response correction requires valid response metadata; gain fields alone cannot establish a frequency transfer function. Estimate any noise or initial-state prior from causally available context or training data, without importing future event energy. Do not add a magnitude-dependent covariance that manufactures distinguishability in the causal null.

The smallest eventual decisive ablation is: (1) strong physical-unit/gain baseline; (2) the exact same prefix source/context model with diagonal coefficient covariance; (3) identical model with a train-estimated full covariance/observation-operator treatment, with priors, parameter capacity and decision rule matched. All arms must retain the null fixture, 1/3/5-second event identities, proper scores, bulk mean/median errors, event-macro tail error and uncertainty. A robust real-data gain over both (1) and (2) would justify investigating the EEW-specific combination. This preflight supplies no evidence that such a gain exists.

## Provenance

The code and test files exactly match the clean reviewed snapshot. The review did static inspection; the agent separately executed the tests and simulation. The local NumPy Accelerate warning anomaly and independent finite-sum comparison are preserved in `numpy_matmul_probe.json`; explicit unoptimized contractions resolved it without suppressing warnings. See `outcome_summary.json` for all per-seed/per-duration values and check provenance; `run_20261009/results.json` contains every arm, including negative controls.

- `protocol.json` SHA256 `511f8678157e6d36f24ab79a79361755fd61bbc0ca74c2bb8acf528a6e1955a9`
- `preflight.py` SHA256 `34f01b3d974874a169ad224eacbba5318defcfdc414db0be7827a705a89861e0`
- `test_preflight.py` SHA256 `c85e8348e70e224803bd20a78cf8e7682894b3e5f3c68f3699f42071628104ef`
- `run_20261009/results.json` SHA256 `71805b3e59dce824a28d6f071ee0bd53b9d00c97449712cb1cfce4717f61782b`
- `outcome_summary.json` SHA256 `085105bc733fc6bfff75d752255772d84f710538be5e7a8f1e47147a656d597c`
- `review_result.json` SHA256 `e759a42f9927438babc6c6c3f60d36ec735a1edc9b044c2fc5e6645443e387bf`

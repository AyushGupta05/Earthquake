# Independent censored-innovation outcome audit

9 October 2026. Completed run `censored_innovation_6c1510b97725_c9dd74d23d87`. CPU-only read of completed TRAIN/VAL artifacts; no GPU training, waveform or TEST reads, and no remote writes.

## Decision

**Do not spend the next training run on the sub-second censored extension.** Later scalar amplitude evidence improves a frozen 1-second forecast, but the CDF tie has no consistent bulk/probability-score advantage over its matched controls. Retaining signed innovations is better for bulk error in both seeds at both later deadlines; free-hurdle Gaussian likelihoods fit the observed evidence better. The tied model does show a small rare-event point-error advantage over the free-hurdle Gaussian, so the evidence is a tradeoff, not proof that censoring can never help. It does not meet the project objective of a stronger 1/3/5-second method.

No 1-second improvement is possible in this pilot: all controls start from exactly the same frozen predictor. Independent full-prefix instrument models remain substantially stronger at 3/5 seconds. Novelty, operational causality and superiority to published EEW systems are not established.

## Verified integrity

- 36 output/provenance artifacts verified against the completed SHA256 manifest. Five original frozen-source file hashes separately match their recorded provenance.
- Both seeds, all five trained controls, and all 15 final-epoch histories are complete, finite, and use identical per-seed training row orders. Learned controls each allocate 21,187 parameters. There was no validation epoch selection.
- 197,676 TRAIN records from 47,273 events; 96,993 VAL records from 3,711 events. TRAIN and VAL event identities are disjoint. The validation tail has 1,027 records but only 13 events with M>=4, including one M5.1 and no M>=6.
- Every saved 1-second probability is bit-identical to the corresponding frozen control. Frozen predictions are identical at all three deadlines. Ensembles are exactly the arithmetic mean of the saved seed predictions.
- Invalid updates leave all probabilities exactly unchanged. Maximum probability normalization error is `2.1094237468e-14`; maximum NumPy/Torch exponentiation difference from saved log-prior is `5.5511151231e-17`. Neither forecast/replay gate was relaxed.
- Independent mean/median, MAE, MedAE, RMSE, CVaR95, event-macro tail error, exact discrete CRPS, threshold-weighted CRPS, and Brier recomputation agree with reported shared metrics within `1.1102230246e-15`. Categorical NLL was additionally computed independently.
- Deterministic algorithms enabled; CUBLAS `:4096:8`; cuDNN deterministic; benchmark off; TF32 matmul off, cuDNN TF32 on. Runtime was 1,035.37 seconds on the original A10G.

## Ensemble point decisions

Each pair is **3 s / 5 s**. Tail MAE weights the 13 M>=4 events equally. CVaR95 is the mean of the largest ceil(5% N) absolute errors.

| Control | Mean-decision MAE | Mean-decision MedAE | CVaR95 | M>=4 event MAE |
|---|---:|---:|---:|---:|
| frozen | 0.37732 / 0.37732 | 0.28163 / 0.28163 | 1.35825 / 1.35825 | 0.67998 / 0.67998 |
| censored | 0.36941 / 0.36732 | 0.27591 / 0.27310 | 1.33248 / 1.32492 | 0.61534 / 0.60015 |
| hurdle | 0.37458 / 0.37382 | 0.27955 / 0.27916 | 1.34953 / 1.34481 | 0.66839 / 0.66042 |
| hurdle_truncated | 0.36920 / 0.36701 | 0.27507 / 0.27313 | 1.33249 / 1.32613 | 0.62287 / 0.61192 |
| uncensored | 0.36846 / 0.36334 | 0.27469 / 0.26991 | 1.33433 / 1.32217 | 0.60862 / 0.60555 |
| discriminative | 0.37037 / 0.36973 | 0.27983 / 0.28015 | 1.31324 / 1.30323 | 0.74260 / 0.75283 |

The tied model improves the frozen ensemble bulk MAE from 0.37732 to 0.36941/0.36732 and tail event MAE from 0.67998 to 0.61534/0.60015. Full-Z improves bulk to 0.36846/0.36334; its tail event MAE is 0.60862/0.60555. Thus full-Z wins the 3-second tail too, while the tied model has a small 5-second tail advantage. Tied versus free-hurdle Gaussian tail improvement is 0.00753/0.01176, with slightly worse ensemble bulk MAE.

| Control | Median-decision MAE | Median-decision CVaR95 | Median-decision M>=4 event MAE |
|---|---:|---:|---:|
| frozen | 0.37544 / 0.37544 | 1.37775 / 1.37775 | 0.69565 / 0.69565 |
| censored | 0.36835 / 0.36659 | 1.35569 / 1.34924 | 0.63392 / 0.61415 |
| hurdle | 0.37298 / 0.37250 | 1.37027 / 1.36619 | 0.68737 / 0.67909 |
| hurdle_truncated | 0.36820 / 0.36634 | 1.35573 / 1.34930 | 0.64061 / 0.62822 |
| uncensored | 0.36777 / 0.36306 | 1.35740 / 1.34757 | 0.62904 / 0.62221 |
| discriminative | 0.36905 / 0.36822 | 1.33647 / 1.32687 | 0.74473 / 0.75514 |

All ensemble median-decision MedAEs are 0.25 because of the 0.1-magnitude grid and label discretization. This equality is not evidence of equal continuous-resolution performance.

## Replication across seeds

Pairs remain 3 s / 5 s. These are single-seed mean decisions.

| Seed | Control | Bulk MAE | M>=4 event MAE |
|---|---|---:|---:|
| 20261009 | frozen | 0.37946 / 0.37946 | 0.67409 / 0.67409 |
| 20261009 | censored | 0.37133 / 0.36919 | 0.61100 / 0.59726 |
| 20261009 | hurdle | 0.37706 / 0.37649 | 0.66089 / 0.64982 |
| 20261009 | hurdle_truncated | 0.37076 / 0.36852 | 0.61993 / 0.60887 |
| 20261009 | uncensored | 0.37025 / 0.36460 | 0.60180 / 0.60779 |
| 20261009 | discriminative | 0.37114 / 0.37020 | 0.74236 / 0.74893 |
| 20261010 | frozen | 0.37648 / 0.37648 | 0.68838 / 0.68838 |
| 20261010 | censored | 0.36891 / 0.36693 | 0.62444 / 0.60812 |
| 20261010 | hurdle | 0.37348 / 0.37255 | 0.67835 / 0.67302 |
| 20261010 | hurdle_truncated | 0.36903 / 0.36696 | 0.62896 / 0.62014 |
| 20261010 | uncensored | 0.36836 / 0.36463 | 0.62429 / 0.61489 |
| 20261010 | discriminative | 0.37030 / 0.37010 | 0.74474 / 0.76029 |

The tied tail advantage over free-hurdle Gaussian appears in both seeds/deadlines, but its bulk advantage occurs only for seed20261010 and is tiny. Full-Z has lower bulk MAE and CRPS than tied in both seeds/deadlines. Tied beats full-Z tail error at 5 seconds in both seeds; it loses at 3 seconds. A tradeoff on this reused 13-event tail does not establish a robust new method.

## Proper distribution scores and decisions

| Control | CRPS | Categorical NLL | Brier(M>=4) | Tail CRPS above4 |
|---|---:|---:|---:|---:|
| frozen | 0.270081 / 0.270081 | 2.846721 / 2.846721 | 0.009790 / 0.009790 | 0.004510 / 0.004510 |
| censored | 0.264695 / 0.263459 | 2.828083 / 2.824423 | 0.009507 / 0.009319 | 0.004466 / 0.004399 |
| hurdle | 0.268284 / 0.267704 | 2.841416 / 2.839344 | 0.009706 / 0.009719 | 0.004459 / 0.004458 |
| hurdle_truncated | 0.264629 / 0.263307 | 2.827915 / 2.823192 | 0.009518 / 0.009441 | 0.004449 / 0.004423 |
| uncensored | 0.264135 / 0.260728 | 2.826839 / 2.815536 | 0.009549 / 0.009428 | 0.004595 / 0.004502 |
| discriminative | 0.265082 / 0.264502 | 2.828643 / 2.826837 | 0.008453 / 0.008233 | 0.003625 / 0.003461 |

Scores apply to distributions, so mean and median decisions have the same probability scores. Full-Z has the best ensemble CRPS and categorical NLL. The discriminative residual gives the lowest Brier/tail CRPS and lowest CVaR, but worse M>=4 point errors: its 5-second mean-decision tail bias is -0.74730 versus tied -0.50330. It also predicts fewer high magnitudes: 272 false-positive/293 true-positive records versus tied641/474 and frozen611/447 at the mean-decision threshold4. These are correlated station records, not event alert counts.

The 5-second tied mean P(M>=4) is 0.02035 against observed record prevalence0.01059; frozen is0.02086, full-Z0.02030, discriminative0.01396. This is inconsistent with claiming calibrated posterior probabilities. The initial predictor was cost-sensitive beta5 Huber+.075CE, and the density arms use conditional observation NLL while the discriminative arm uses posterior CE; this objective difference is an explicit confound, not an isolated proof of generative versus discriminative superiority.

## Likelihood calibration

Values below are held-out **forecast NLL** for the same censored observation space. Lower is better. Do not compare absolute full-Z NLL to censored NLL, because their measures/sample spaces differ.

| Seed | Tied3s/5s | Free-hurdle Gaussian3s/5s |
|---|---:|---:|
| 20261009 | 0.134800 / 0.342613 | 0.108828 / 0.326515 |
| 20261010 | 0.135875 / 0.340706 | 0.106501 / 0.322114 |

Free-hurdle Gaussian also wins conditional NLL at the true magnitude in every seed/deadline, independently of the cost-sensitive prior mixture. Positive-PIT means are tied0.453–0.457 at3s and0.472–0.481 at5s, versus free-hurdle0.486–0.498 and0.501–0.511. The latter histograms are flatter; the full histograms are retained in the JSON. PIT mean alone is not a calibration test.

The tied zero-mass forecast is reasonably informative in bulk: zero-event Brier0.1683–0.1685 at3s and0.2323 at5s, compared with constant-prevalence Brier0.2190/0.2453. Its descriptive ten-bin ECE is0.0148–0.0199/0.0174–0.0176. In the M>=4 tail at5s, however, its zero-event Brier0.2540–0.2595 is worse than the tail-prevalence constant0.24996. Free-hurdle Gaussian is also worse than that tail constant; full-Z0.2325–0.2435 is better. No event-independent significance test is claimed.

The first strict audit flagged harmless float64 endpoints: twelve positive-PIT values across density arms exceeded1 by2.22e-16, and one full-Z zero probability exceeded1 by2.0e-15. The audit records raw bounds/counts, rejects excursions larger than1e-12, and clips only descriptive calibration endpoints. Saved arrays are unchanged. Original histograms can omit those twelve endpoint records; this has negligible numerical impact, now explicitly accounted for.

## Invalid observations and rare-event concentration

| Split |3s valid/total|5s valid/total|Invalid M>=4 records|
|---|---:|---:|---:|
|TRAIN|197621/197676|197620/197676|1 at each step|
|VAL|96961/96993|96955/96993|0|

Invalidity is from floor/nonfinite peak flags and propagated earlier invalidity; no usable-response/sensitivity/unit missingness codes occurred in these selected rows. All rows remain in evaluation. G=max(0,Z), mask/reason identities, and fallback equality passed. The observation baseline is the first10post-P samples, not pre-P noise. Ratio invariance applies only to the innovation statistic away from the floor, not to the entire model because the frozen context contains count-dependent and station/site features.

The tied ensemble improves 11/13 tail events at3s and10/13 at5s versus frozen. Against free-hurdle Gaussian it wins10/13 and9/13; against full-Z6/13 and8/13. The sole M5.1 event improves MAE1.16508→0.70613 at5s, accounting for about44% of the total event-macro tail improvement over frozen. Thus the gain is not exclusively that event, but the claimed large-magnitude evidence remains very limited. Full-Z reaches0.69175 on that same event. Event identities, counts and errors are retained in the audit JSON.

## Stronger available comparator and next action

On the same197676-row training sample, previously completed independent full-prefix static models achieved bulk MAE0.32944/0.29925 and M>=4 event MAE0.55015/0.46508 at3/5s. These have more waveform information and earlier nondeterministic training settings, so they are an operational comparison rather than an exact architecture ablation. Their large advantage makes the current scalar-update route uncompetitive. Comparator metrics/hashes are in the committed `source_scaling_evidence_snapshot.json` evidence.

Retain this as a useful negative/control result: observed evidence helps a stale forecast; discarding negative innovations loses predictive information; the CDF tie trades modest tail point-error gains against bulk/likelihood fit. Do not present a sub-second version as an earned next experiment or a foundational mechanism. A future investigation would need a different evidence representation or constraint with a decisive matched control, proper-score/bulk constraints, and real large-event evaluation. Repeatedly adapting to this VAL tail risks finding-fishing.

## Reproduction and review

`audit_artifacts.py` ran through SSH stdin with CUDA hidden and one CPU thread against the immutable completed-run path. It imports only NumPy/stdlib and does not invoke the model. `artifact_audit.json` is450855bytes and contains all seed/ensemble scores, tail event rows, mask counts, calibration histograms and checked hashes. The source manifest and original-frozen SHA list are preserved beside it.

Seven focused CPU tests passed (CRPS including off-support and collapsed support; decision/event weights; bad normalization; calibration endpoints; NaN/Inf metric rejection). The first valid Codex autoreview found a NaN acceptance bug in the independent audit comparison; it was accepted, fixed and tested. A preceding review attempt failed structured-path validation and was retried. The final isolated autoreview returned exit0 with no actionable findings. No experiment code or artifacts were modified.

Review command:
```text
/Users/ayush/.codex/skills/autoreview/scripts/autoreview --mode local --engine codex --codex-bin /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex --no-web-search --prompt-file ../review_context.txt --output ../review_result.txt --json-output ../review_result.json
```

Key SHA256 values:
```text
76a2eb4631c06937d7a499e5c10f99a8725dee24a378e4f9e4bb94e8a41325b1  artifact_audit.json
3b0dd050a703229751a9aedf7d47eec6c63eb301ef2d9fa959205bebcec7d08c  artifacts.json
9858443e591fcfddaa3bdca7754590dae566eb857c2c78b19867f017a61f3e07  metrics.json
dc14958992ca830ab17012c67181b496c79f50d89d71f69952fe38566257cc86  audit_artifacts.py
700750fc75e7015b98236c649af6b9f8b96d3b66b5cc5daad352f96c42d46e0e  test_audit_artifacts.py
7c711a8e262d9723241ac7b8ace8d157498581626777a9dfa770fc378b7610df  review_result.json
4cef590552ae87af382f033b03c61098a994b929d2a7df788765665238a7bf6e  source_frozen_sha256.txt
```

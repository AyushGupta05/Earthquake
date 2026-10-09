# Independent 3 s contextual-score audit

complete CPU artifact/metric audit with stated normalization boundary

Validated 34 manifested files; 96993 validation recordings, 3711 events, 13 M≥4 events and 1 M≥5 events.

Each row below uses the ensemble mean decision. All seed/median results and individual tail-event comparisons are in the CSV/JSON files.

| Arm | MAE | MedAE | M≥4 MAE | M≥4 event MAE | M≥5 MAE | CVaR95 | CRPS | NLL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| crps_ce | 0.329364 | 0.248318 | 0.728102 | 0.691688 | 1.033129 | 1.199266 | 0.235449 | 2.708354 |
| context_ce | 0.329598 | 0.248538 | 0.732770 | 0.697637 | 1.047215 | 1.196735 | 0.235606 | 2.706808 |
| shuffled_ce | 0.330559 | 0.249385 | 0.722132 | 0.686330 | 1.011780 | 1.197311 | 0.236244 | 2.710708 |
| average_ce | 0.329214 | 0.248102 | 0.718260 | 0.682539 | 1.008651 | 1.197065 | 0.235365 | 2.707432 |
| ranked_bce_ce | 0.328722 | 0.248097 | 0.720235 | 0.684738 | 1.012511 | 1.188909 | 0.234890 | 2.703445 |
| properized_ad_ce | 0.340081 | 0.257940 | 0.707362 | 0.675486 | 0.927223 | 1.201411 | 0.242607 | 2.737867 |

Context-only benefit requires improvement over both shuffled and average weights, with comparison to ranked BCE and properized AD. Improvement over ordinary CRPS alone cannot establish a context-specific effect.

Normalizer provenance: Checkpoint values and hashes verified; raw85 inputs absent, numerical recomputation unavailable.

- Reused exploratory validation;13 tail events in the real protocol, no independent SOTA claim
- No raw85 archive: normalizer values hash-verified but not numerically reconstructed
- NLL uses saved float32 PMF; zero target probabilities are infinite, never floored
- No training/inference performed; CPU parameter initialization and shuffle reconstruction only

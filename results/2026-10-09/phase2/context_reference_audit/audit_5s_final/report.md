# Independent 5 s contextual-score audit

complete CPU artifact/metric audit with stated normalization boundary

Validated 34 manifested files; 96993 validation recordings, 3711 events, 13 M≥4 events and 1 M≥5 events.

Each row below uses the ensemble mean decision. All seed/median results and individual tail-event comparisons are in the CSV/JSON files.

| Arm | MAE | MedAE | M≥4 MAE | M≥4 event MAE | M≥5 MAE | CVaR95 | CRPS | NLL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| crps_ce | 0.299299 | 0.217390 | 0.624243 | 0.584180 | 0.742592 | 1.156751 | 0.215450 | 2.598497 |
| context_ce | 0.299401 | 0.217841 | 0.630170 | 0.590264 | 0.759678 | 1.149369 | 0.215338 | 2.596261 |
| shuffled_ce | 0.299886 | 0.218165 | 0.609789 | 0.570293 | 0.705628 | 1.155476 | 0.215724 | 2.598532 |
| average_ce | 0.299073 | 0.217283 | 0.608449 | 0.568798 | 0.704125 | 1.153549 | 0.215159 | 2.595418 |
| ranked_bce_ce | 0.299683 | 0.218915 | 0.610533 | 0.570206 | 0.702557 | 1.142908 | 0.215390 | 2.595571 |
| properized_ad_ce | 0.314635 | 0.232227 | 0.651524 | 0.611401 | 0.861996 | 1.170712 | 0.226214 | 2.657301 |

Context-only benefit requires improvement over both shuffled and average weights, with comparison to ranked BCE and properized AD. Improvement over ordinary CRPS alone cannot establish a context-specific effect.

Normalizer provenance: Checkpoint values and hashes verified; raw85 inputs absent, numerical recomputation unavailable.

- Reused exploratory validation;13 tail events in the real protocol, no independent SOTA claim
- No raw85 archive: normalizer values hash-verified but not numerically reconstructed
- NLL uses saved float32 PMF; zero target probabilities are infinite, never floored
- No training/inference performed; CPU parameter initialization and shuffle reconstruction only

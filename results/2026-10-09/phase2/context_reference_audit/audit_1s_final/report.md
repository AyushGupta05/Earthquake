# Independent 1 s contextual-score audit

complete CPU artifact/metric audit with stated normalization boundary

Validated 34 manifested files; 96993 validation recordings, 3711 events, 13 M≥4 events and 1 M≥5 events.

Each row below uses the ensemble mean decision. All seed/median results and individual tail-event comparisons are in the CSV/JSON files.

| Arm | MAE | MedAE | M≥4 MAE | M≥4 event MAE | M≥5 MAE | CVaR95 | CRPS | NLL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| crps_ce | 0.376454 | 0.286928 | 0.882867 | 0.849307 | 1.406855 | 1.317366 | 0.268397 | 2.841608 |
| context_ce | 0.375864 | 0.286490 | 0.897011 | 0.863728 | 1.414318 | 1.313504 | 0.267957 | 2.837239 |
| shuffled_ce | 0.376443 | 0.287015 | 0.886262 | 0.852855 | 1.406293 | 1.315605 | 0.268393 | 2.841435 |
| average_ce | 0.375806 | 0.286699 | 0.879012 | 0.844667 | 1.394626 | 1.315026 | 0.267871 | 2.839254 |
| ranked_bce_ce | 0.376448 | 0.286684 | 0.886471 | 0.852634 | 1.398016 | 1.312698 | 0.268224 | 2.836224 |
| properized_ad_ce | 0.383895 | 0.295902 | 0.911443 | 0.879371 | 1.430582 | 1.314151 | 0.272955 | 2.854939 |

Context-only benefit requires improvement over both shuffled and average weights, with comparison to ranked BCE and properized AD. Improvement over ordinary CRPS alone cannot establish a context-specific effect.

Normalizer provenance: Checkpoint values and hashes verified; raw85 inputs absent, numerical recomputation unavailable.

- Reused exploratory validation;13 tail events in the real protocol, no independent SOTA claim
- No raw85 archive: normalizer values hash-verified but not numerically reconstructed
- NLL uses saved float32 PMF; zero target probabilities are infinite, never floored
- No training/inference performed; CPU parameter initialization and shuffle reconstruction only

# Which instrument information produces the improvement?

All five controls use identical 291-column networks, initialization, normalization, sample order and fixed 15-epoch training. Each window uses both prespecified seeds and the same 197,676 TRAIN records. Unused inputs are zero-masked after the common TRAIN-weighted standardizer. Native-amplitude summaries are disabled in every arm.

**Finding:** gain/unit fields alone recover much of the improvement. Family/site information also produces strong tail gains; combining all static fields gives the lowest bulk MAE at every duration, but does not always give the lowest high-magnitude error. This supports a stronger baseline, not an isolated causal explanation or a new method claim.

| Seconds | Control | MAE | MedAE | M≥4 MAE | CVaR95 |
|---|---|---:|---:|---:|---:|
| 1 | base | 0.405669 | 0.305301 | 0.870775 | 1.425276 |
| 1 | gain_units | 0.384219 | 0.286221 | 0.703950 | 1.384293 |
| 1 | family_site | 0.385848 | 0.291996 | 0.697701 | 1.368608 |
| 1 | response_all | 0.380293 | 0.283578 | 0.710582 | 1.367352 |
| 1 | full_static | 0.377325 | 0.281630 | 0.709830 | 1.358248 |
| 3 | base | 0.356927 | 0.264070 | 0.728964 | 1.303962 |
| 3 | gain_units | 0.334770 | 0.248398 | 0.594422 | 1.245367 |
| 3 | family_site | 0.341414 | 0.255803 | 0.597661 | 1.240811 |
| 3 | response_all | 0.332140 | 0.245490 | 0.591021 | 1.241999 |
| 3 | full_static | 0.329443 | 0.243162 | 0.588089 | 1.232876 |
| 5 | base | 0.327979 | 0.235165 | 0.639201 | 1.266235 |
| 5 | gain_units | 0.302236 | 0.215886 | 0.509846 | 1.202410 |
| 5 | family_site | 0.312052 | 0.227220 | 0.503590 | 1.203156 |
| 5 | response_all | 0.300380 | 0.213418 | 0.507998 | 1.204649 |
| 5 | full_static | 0.299253 | 0.212464 | 0.505174 | 1.201221 |

The table uses the mean of the two probability vectors and its distribution mean as the decision. MedAE is the median absolute error of that decision. It is not a posterior-median estimate.

- `gain_units`: 12 component sensitivity/unit fields.
- `family_site`: six sensor-family indicators plus elevation/Vs30 and their missingness fields.
- `response_all`: all 24 component response fields, including calibration frequency, advertised sampling rate and missingness.
- `full_static`: all 34 static response/family/site fields.

At 5 seconds, gain/unit fields reduce M≥4 MAE by 0.1294, compared with 0.1340 for all static fields. At 1 second, family/site features have a lower tail MAE (0.6977) than all static features (0.7098), with worse bulk MAE (0.3858 versus 0.3773). The all-static model was already selected as a strong comparison before these ablations; these exploratory results do not justify retrospectively picking a different feature mask at each deadline.

**Limits:** elevation/Vs30 and response tuples can fingerprint stations; almost 98% of validation recordings use TRAIN stations. This dataset still has 13 M≥4 validation events, one M≥5 event and none M≥6. The count-release detrending/resampling and archived metadata timing remain limitations. A station-held-out/end-to-end physical-unit comparison is needed to separate instrument correction from learned station/domain priors.

Base and all-static controls reproduce the corresponding earlier instrument-control metrics exactly at both seeds and all three windows. New future-growth objectives must improve on this baseline under the same inputs and sampling. The [full 979,487-record replication](earthquake_instrument_full_results.md) is complete; the growth pilot remains a separately matched 197,676-record comparison.

## Provenance

- `instrument_factors_1s_bb40c7b1292d_2e752a738524`: scalar results in Git; probabilities/checkpoints remain under `/mnt/eew-research/runs/` on the original AWS worker.
- `instrument_factors_3s_96ff2e86243e_926bd84067a9`: scalar results in Git; probabilities/checkpoints remain under `/mnt/eew-research/runs/` on the original AWS worker.
- `instrument_factors_5s_4969123a4c39_813ed091ac97`: scalar results in Git; probabilities/checkpoints remain under `/mnt/eew-research/runs/` on the original AWS worker.

Eleven focused CPU tests and clean isolated Codex review passed before launch. Per-family/per-event diagnostics, TRAIN/VAL identities, masks, source hashes and probabilities are retained.

# Instrument baseline: replication on all TRAIN records

The improvement survives training on all 979,487 TRAIN records rather than the 197,676-record pilot subset. Both seeds use the same fixed 15-epoch budget, architecture and input dimension for all controls. These remain exploratory results on the reused 2018 validation split, with only 13 M≥4 events and one M≥5 event.

| Seconds | Control | MAE | MedAE | M≥4 MAE | CVaR95 |
|---|---|---:|---:|---:|---:|
| 1 | base | 0.395628 | 0.296521 | 0.852221 | 1.406155 |
| 1 | instrument | 0.365343 | 0.272028 | 0.686116 | 1.327444 |
| 1 | instrument_native | 0.364887 | 0.272413 | 0.683725 | 1.328035 |
| 3 | base | 0.346881 | 0.256702 | 0.719547 | 1.271668 |
| 3 | instrument | 0.315881 | 0.232202 | 0.551167 | 1.195389 |
| 3 | instrument_native | 0.312923 | 0.230436 | 0.558577 | 1.186369 |
| 5 | base | 0.317999 | 0.229551 | 0.633145 | 1.221063 |
| 5 | instrument | 0.286189 | 0.203790 | 0.486910 | 1.146738 |
| 5 | instrument_native | 0.284532 | 0.202126 | 0.474926 | 1.142364 |

Each row evaluates the mean of two predicted probability vectors, using its distribution mean as the point estimate. `base` zero-masks all instrument fields; `instrument` enables static response/family/site fields; `instrument_native` additionally enables amplitude summaries divided by instrument sensitivity. Sensitivity division alone is not full instrument deconvolution.

All-static features improve every listed measure at every duration over the matched counts baseline. Native-amplitude features give a further clear point improvement at 5 seconds, but the 1- and 3-second results involve tradeoffs. These controls use the same observations and no extra inference time. They do not establish a new probabilistic principle or a published-benchmark win.

The full-data run changes both the sampling population and the number of optimizer updates per epoch, so comparison with the smaller pilot does not isolate sample count alone. Future-growth pilots remain matched to the smaller subset; they must be replicated here if they pass all criteria. Station reuse, mixed magnitude types and released-waveform preprocessing remain unresolved generalization limits. Event-bootstrap intervals from the earlier subset must not be reused as intervals for this run.

## Provenance

- `instrument_residual_1s_4aba2801c52c_79d6b7a1cef8`
- `instrument_residual_3s_c947223bad53_de267ee80165`
- `instrument_residual_5s_43395c855d8e_fd9e97e5fafa`

Small JSON artifacts and source are preserved in Git; full checkpoints and probabilities remain under `/mnt/eew-research/runs/` on the original AWS worker. No new TEST predictions were made.

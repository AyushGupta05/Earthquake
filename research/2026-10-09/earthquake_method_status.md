# Method status and decisions

9 October 2026, 21:06 UTC. **A useful baseline improvement is verified on reused validation; a novel method with an independently matched published-benchmark win is not yet established.** All scientific failures remain part of the experiment record.

| Approach | What was tested | Current finding / decision |
|---|---|---|
| Original prior-response / distribution readouts | Reweight or correct existing probability responses | Can lower large-event error, often at the expense of bulk error or false alerts. Insufficient by itself. |
| Prefix-waveform residual features | Distribution logits, CNN embedding, observed amplitude/growth/spectral summaries | More information helps ordinary error; stronger magnitude weighting retains a tail/bulk tradeoff. Established supervised method. |
| Sequential logit updates and entropy gate | Shared compact backbone, disjoint new time blocks, 1→3→5 distributions | Completed controls did not beat independent-prefix inference. Entropy is not a reliable sign of error. |
| Full-data independent waveform model | All 979,487 TRAIN records, fixed budget | Stronger than the historical CNN; retained as a baseline. New deterministic two-seed replication is underway. |
| CVaR objective | Explicit worst-error training plus magnitude emphasis | Some improvements, but remaining median/event-weighting and largest-event tradeoffs. Not a complete solution. |
| Future-CDF / revision-energy auxiliary heads | Conventional distillation, realized gain, squared revisions, detached controls | Completed two-seed grid did not meet the all-duration tail objective. Much of the apparent gain is explained by ordinary distillation; old CUDA runs were not exactly repeatable. |
| Static instrument/site features | Same distribution head and parameter count, two seeds, all TRAIN | Strongest completed practical gain: improves MAE, MedAE, M≥4 MAE and CVaR95 at all three times. Station effects and gain/unit information explain much of it; not a new probability principle. |
| Sensitivity-normalized amplitude features | Added observed-prefix amplitudes to the static model | Further clear gain at 5 s; smaller tradeoffs at 1/3 s. Not full instrument-response deconvolution. |
| Conditional future-amplitude growth | MSE, unconditional density, magnitude-conditioned density, detached control | Completed grid rejected: conditional likelihood worsens ordinary error at all three times; small tail gains do not preserve worst-error performance. |
| Censored observed-amplitude innovations | Frozen matched 1 s distribution; new 1→3→5 peak evidence; tied/free hurdle, uncensored and discriminative controls | Completed and independently audited. Improves the stale 1 s forecast but loses to full-prefix inference; the tied mechanism loses likelihood fit to its free-hurdle control. Sub-second continuation rejected. [Results](earthquake_censored_results.md). |
| Prefix affine projection | Re-estimate/remove trend using only each observed prefix, with a last-sample guard control | Completed six runs and independent AWS/local audit. Some bulk gains, but the single M≥5 event worsens under affine at all horizons in both seeds. Rejected for the primary objective. [Results](earthquake_affine_results.md). |
| Residual-logit support bound | Exact per-record mean limits under ±5 corrections; exhaustive tests and actual AWS exports | M≥4 optimistic floors .0234/.0175/.0099, much smaller than observed errors. Bound is not the main aggregate bottleneck. [Audit](earthquake_residual_support_audit.md). |
| Proper distribution scores | Huber/CE, ordinary CRPS, fixed-tail CRPS, TRAIN-marginal weighted CRPS, ranked log score | Completed full-TRAIN two-seed 1/3/5 grid. Every proper-score control worsens M≥4 MAE in both seeds at all horizons. CPU artifact/metric audits pass; all30 heads pass full-VAL same-runtime GPU replay. [Complete audit](earthquake_proper_score_results.md). |
| Causal physical prefix / correlated noise | Fixed protocol, two seeds, 48 synthetic conditions, exact marginalization and causal nulls | 14 tests and clean review; full covariance improves NLL in 11/12 comparisons but worsens all four one-second tail comparisons. No covariance-only GPU extension. [Preflight](earthquake_physical_prefix_preflight.md). |
| Shared-cap contrast likelihood | 24 TRAIN-only CPU fits; independently refitted matched Gaussian control | Fixed follow-up gate fails; no GPU expansion. [Preflight](earthquake_shared_cap_preflight.md). |
| Contextual reference score | Five event-excluded teachers; context/shuffle/global/CRPS/ranked-log/properized-AD controls, two student seeds | Reviewed pilot running on AWS at1/3/5 s. Known proper-score construction; no novelty claim. [Protocol](earthquake_context_reference_protocol.md). |
| Chile TEAM-style external baseline | Published architecture adaptation, full 25+100 epoch budget; TRAIN-only selection | Running on dedicated AWS A10G. DEV scoring follows completed training; TEST remains sealed. |

The all-static model's completed exploratory scores are:

| Observation | Overall MAE: matched baseline → static | M≥4 MAE: matched baseline → static |
|---|---:|---:|
| 1 s | .395628 → .365343 | .852221 → .686116 |
| 3 s | .346881 → .315881 | .719547 → .551167 |
| 5 s | .317999 → .286189 | .633145 → .486910 |

These are means of two seed probability distributions with the distribution mean as the decision. The same validation contains 3,711 earthquakes, only 13 M≥4 and one M≥5; it has been used repeatedly during this research. Record-level sample size does not turn those 13 earthquakes into many independent large events. [Full results and event-bootstrap intervals](earthquake_instrument_full_results.md).

The censored pilot does not earn a finer sub-second extension. Proper-score controls completed without meeting the tail objective; a frozen, event-cross-fitted reference distribution is being investigated as a way to focus threshold errors without magnitude-label reweighting. The bounded pilot is now running on AWS after 12 focused CPU tests and clean Codex autoreview. [Frozen protocol](earthquake_context_reference_protocol.md). This is not a novelty claim. Geometry-aware or source-growth proposals also have close prior art and identifiability limits; they are hypotheses, not accepted contributions.

[Live checkpoint](START_HERE.md) · [Current literature](earthquake_current_competitors.md) · [External data audit](earthquake_external_validation_expansion.md) · [AWS resource controls](aws_execution_note.md)

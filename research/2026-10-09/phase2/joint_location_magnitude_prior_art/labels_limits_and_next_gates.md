# Label scales, observable rupture history, and three bounded next options

10 October 2026. Primary-source research and design only. No waveform, checkpoint, raw catalog, prediction-array or held-out Chile outcome reads; no cloud actions or fit code. Existing completed project reports and author source were inspected. Thresholds below are **proposals to freeze before any new diagnostic**, not executed results or amendments to the existing density-floor protocol.

**Recommendation:** first run the already frozen TRAIN density-floor diagnostic and a small independent label-provenance audit. A correlated, geometry-aware multistation likelihood is the one architectural alternative worth retaining, conditional on a real-data information gate. Neither mixed-label harmonization nor another rupture-growth/tail-weighting construction currently has evidence sufficient to justify a broad training sweep. The negative INSTANCE score, revision, growth, censoring and polarization pilots motivate these gates; they do not prove that a multistation Chile mechanism must fail.

## What the labels do—and do not—mean

TEAM-LM identifies Chile's target as displacement-based **MA**, without the Wood–Anderson response; Italy instead mixes ML, Mw and mb in proportions that depend partly on event size. Its Chile benchmark is therefore already more homogeneous than a generic mixed-magnitude catalog. MA and Mw remain different observables, and lower MA error cannot automatically be compared with a paper's Mw error. The released waveform is sensitivity-corrected velocity, not fully response-corrected displacement. [TEAM-LM, §2.1](https://academic.oup.com/gji/article/226/2/1086/6223459), [official data description](https://datapub.gfz-potsdam.de/download/10.5880.GFZ.2.4.2021.002noeUVRE/2021-002_Muenchmeyer-et-al_data-description.pdf).

The underlying magnitude study ties its scales weakly to **114 GCMT Mw 5–6 events**, because the scales need not agree elsewhere. It finds MA approximately tracks Mw over the studied range, whereas ML, velocity and acceleration scales show different saturation. Its labels include source/path/station corrections; Appendix E explicitly considers correlated station residuals when estimating event uncertainty. These labels are estimates, but the paper does not justify treating every disagreement with Mw as an error. [Münchmeyer et al., *Low uncertainty multifeature magnitude estimation with 3-D corrections and boosting tree regression: application to North Chile*, §§2.5,3.1, Appendix E](https://academic.oup.com/gji/article/220/1/142/5571095).

Consequences for this project:

- `MA`, `ML`, `MW_SIPPL`, `M_EXT` and `std_MA` exist in the previously audited schema. Names alone do not establish the provenance, independence, missing-value convention or uncertainty meaning of each field. In particular, `M_EXT` must not be silently called Mw, and `std_MA` must not be silently called known independent Gaussian measurement noise.
- Converting all labels to Mw changes the estimand. A MA benchmark still needs MA scores; a harmonized Mw experiment needs its own declared labels and matched comparator. A monotone conversion also changes absolute-error weighting through its local slope, so numerical error reduction is not automatically better information.
- Label errors may share the same stations and corrections as model inputs. A more accurate reproduction of the catalog's processing need not be a better estimate of physical seismic moment. Independent provenance and spatial/response transfer are needed to distinguish them.
- The author loader adds Gaussian target jitter above M4, with standard deviation `0.05*(M−4)` (`team_util.py`, lines 279–281). At M8 this is 0.2 magnitude units. That is training augmentation, not a measured catalog uncertainty. It must remain matched in an objective ablation and must not be counted again as an independent noise source in a label model. [Pinned source](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/util.py#L279).

## What can be observed at network-first-P +1/+3/+5 seconds

Three different clocks must remain separate: source onset, each station's P arrival, and the first network P arrival. For a point-source travel-time illustration, station i has observed at most

\[
u_i(t)=\max\{0,\ t+T_{P,\min}(L)-T_{P,i}(L)\}
\]

seconds after its P arrival at network deadline t. Thus the nearest station may have t seconds while many others still contain noise. This equation explains the information limit; its catalog L and travel times are **not permitted inference inputs**. Real finite ruptures complicate it through directivity: radiation from a subfault reaches station i at its activation time plus that subfault's travel time. Receiving several stations does not reveal unobserved future asperities.

Keep four saturation/failure mechanisms distinct: full-record magnitude-scale response, sensor clipping or missing long periods, truncated observations of an ongoing rupture, and a learned model's objective/representation failure. Removing Wood–Anderson saturation in MA does not remove the latter three. Nor does continuous Gaussian support guarantee enough training information about M7–9.

The main primary-source evidence remains contested, with different observation protocols:

| Evidence inspected | What follows for our fixed deadlines |
|---|---|
| [Trugman et al.2019, *Peak Ground Displacement Saturates Exactly When Expected*](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf), full paper. | Window-dependent Pd saturation is compatible with nondeterministic rupture; the paper constructs a posterior whose high-magnitude uncertainty persists. A GR prior changes the posterior mean/alert tradeoff. This is not evidence that multiplying tail probabilities improves both bulk and rare-event point error. Its station-trigger timing and processing are not our network-first-P protocol. |
| [Münchmeyer, Leser & Tilmann2022, *A probabilistic view on rupture predictability*](https://arxiv.org/html/2203.08622v1), full text and appendices. | Their STF and teleseismic experiments find separation primarily around peak moment release, with apparent earlier SCARDEC predictability affected by onset/processing artifacts. This is strong evidence against assuming early determinism, not a theorem forbidding useful regional information. Their Gaussian-mixture/CRPS model and discussion of long posterior tails already cover the broad probabilistic idea. |
| [Longobardi, Colombelli & Zollo2025, *The deterministic behaviour of earthquake rupture beginning*](https://www.nature.com/articles/s43247-025-02814-z), publisher results/method descriptions verified. | Reports early displacement-growth differences, but chooses station rings using epicentral geometry and evaluates slopes relative to a fitted plateau/curvature time. The authors identify online plateau estimation as unfinished. This motivates a causal test; it does not provide an already deployable fixed 1/3/5-second feature. The final paper's station-ring selection also differs from the five-nearest-station preprint. |
| [Zeng et al.2025, *Whether and When Large Earthquake Magnitudes Can Be Determined From Rupture Onsets*](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JH000801), publisher §3.4/discussion verified; complete training code not audited here. | Reports STF-based early magnitude skill and characteristic times derived from fractions of final rupture duration. Those fractions and reconstructed STFs are not automatically available at a fixed regional waveform deadline. The paper itself identifies real-time STF production as a deployment obstacle. Do not label the work invalid; require a causal absolute-time reproduction before importing its headline seconds. |

These observations do not earn a new latent “rupture maturity” head without an identifiable causal observable. The current negative growth/censored pilots already show that a chosen peak-growth statistic can lose to the full prefix. Future plateau times, source duration fractions, catalog origin times, theoretical arrivals from true location and after-the-fact nearest-station choices cannot rescue that statistic in an operational comparison.

## Option 1 — label-channel audit, then a model only if justified

**Missing information:** whether large residuals represent a consistent target scale, a provenance discontinuity, or genuinely uncertain labels. This is a measurement-model hypothesis, not permission to relabel inconvenient events.

**Cheap diagnostic:** freeze official TRAIN identities and an event-hash five-fold partition; export only label values, type/provenance flags, uncertainty definitions, date and station-count summaries under separate authorization. No waveform or checkpoint is required. Resolve native field definitions first, report missingness/paired-label counts by magnitude band, and identify which Mw anchors also participated in MA calibration. On independent pairs only, compare an identity relation and an affine errors-in-variables relation with uncertainty; report differences by source/date and leave-one-largest-event-out sensitivity. Do not fill absent Mw values using MA and then call them independent targets.

**Proposed gate:** require documented provenance, at least 30 independent paired labels overall and at least 10 above the prespecified MA5.5 threshold, plus an out-of-fold systematic discrepancy of at least 0.10 magnitude units whose event-bootstrap interval excludes zero and remains after removing the largest event. The count gate is a minimum to consider a small pilot, not adequate evidence for M7–9 extrapolation. If unavailable or null, retain MA and stop harmonization work. A pairwise correlation alone does not pass.

**Matched control if earned:** direct MA proper-density training versus the same architecture with an explicitly normalized label observation channel, plus constant-noise and shuffled-uncertainty controls. A latent density and an observation density are distinct:

\[
p(y_s\mid X)=\int r_s(y_s\mid m)q(m\mid X)dm.
\]

For genuinely justified independent Gaussian label error, convolution adds its variance to each component. The noise model is training/evaluation metadata, never a future input at deployment. Fix the latent scale through a declared anchor; otherwise location/scale transformations of m and r are not identified. Benchmark MA through the observation channel and report independent Mw separately. If improvement exists only after redefining the target or inflating its error bars, it has not solved the original objective. Label harmonization and noisy-target likelihoods are established tools, not a new probability principle.

## Option 2 — keep the frozen likelihood-floor decision, with a limited claim

For the existing score \(-\log(p+\epsilon)\), the proper-NLL gradient is multiplied by \(p/(p+\epsilon)\). The port's stable log-sum-exp does not remove this statistical attenuation. Preserve the existing gate unchanged: at least four distinct TRAIN-fit MA≥5.5 events must each combine attenuation <0.1 and mean underestimation >0.5 at two or more deadlines. This is current checkpoint incidence, not evidence of historical training causation. [Frozen protocol](../chile_next_mechanism/diagnostic_protocol_v1.json).

- **Negative:** do not continue a Huber-head sweep under this rationale. Consider label provenance or missing conditional information; do not lower the threshold to manufacture support.
- **Positive:** it supports a matched continuation, not a heavy-tail-family claim. Compare floored Gaussian, epsilon-zero proper Gaussian, and normalized moment-matched Huber with identical initialization, exposure, smoothing and optimizer budgets. Responsibility collapse, excessive variances, inactive mean activations and clipping remain separate explanations.
- **Proper Gaussian wins:** retain a baseline/objective correction. **Huber wins only against the floored model:** no evidence for a new component family. **Huber also beats proper Gaussian:** require proper Gaussian-CRPS and independent event evidence before attributing a tail benefit to robust density shape. These densities and scores have direct prior art documented in the [existing claim audit](../chile_next_mechanism_prior_art/claim_audit.md).

This is the cheapest conditional next experiment because its proposed failure mechanism is present in source. A positive gain would not establish new rupture information or solve magnitude-scale ambiguity.

## Option 3 — a real multistation dependence gate before coupled geometry training

**Missing information/inductive bias:** the dependence among simultaneous station observations, including their common source/path ambiguity. A product of station likelihoods can become spuriously precise when multiple stations repeat the same uncertain evidence. The existing synthetic covariance preflight showed that improved NLL alone need not improve tail point errors. A real observation-conditioned test must precede another covariance model.

**Cheap diagnostic:** after a new frozen TRAIN extraction is separately authorized, use native prefix log amplitudes and normalized station-shape summaries at 1/3/5 seconds, with station coordinates and explicit floor/noise masks. Do not use catalog distance, origin time or future picks as covariates. Condition on known M **only when fitting/evaluating the observation likelihood**; label that a likelihood diagnostic, not deployable prediction. Fit inside event-excluded folds rather than extracting supervised features from a backbone already trained on the nominal held fold. Bound CPU fitting to 1,800 seconds.

Compare a diagonal conditional Gaussian with a small low-rank-plus-diagonal event covariance, including its log determinant and all constants. Use both a same-marginal-variance covariance ablation and a separately optimized diagonal model with at least the same total parameter budget. Hold the conditional-mean family, covariates, population, masks and fitting budget fixed; report any necessary scale-head capacity differences. Include a station-group holdout and a conditional independence/null simulation. Do not give final M to an observation operator or noise covariance in the null. Floors and missing stations stay explicit rather than silently deleting difficult events. An amplitude recorded at a numerical floor requires an integrated censoring probability, not a continuous density evaluated at that floor. If that likelihood cannot be normalized and checked within the bounded preflight, do not run it; first simplify the observation definition without discarding information or selectively replacing rows.

**Proposed gate:** on event-held folds, correlated likelihood must improve NLL by ≥0.02 nats per observed station against the optimized diagonal control at every deadline, with paired event-bootstrap upper bound below zero; improvements must persist under the station-group holdout. Then require a matched posterior/readout comparison to improve MA≥5.5 event-macro MAE by ≥0.02 while bulk MAE/MedAE increase ≤0.005, for both mean and median at all deadlines, without worse CVaR95 or CRPS. If only likelihood/coverage improves, report that narrower result and stop a tail-error claim. Scarce large-event support may make this inconclusive; “inconclusive” does not justify unsealing TEST.

**Architectural control if earned:** the earlier [geometry-conditioned proposal](assessment.md) supplies the deployable comparison: magnitude-only TEAM; auxiliary location head; an optimized point-location decoder; the same decoder integrating one coherent location distribution. A conditional likelihood factorization can be

\[
q(M,L\mid S_t,A_t)\propto q(M,L\mid S_t)\,f(A_t\mid M,L,S_t),
\]

where S is prefix shape/context and A is the amplitude vector. This requires a properly conditional f, not an assumption that shape and amplitude are independent. Use one joint covariance/shared latent source for all stations, and a declared training-population prior. Never multiply independent station *posteriors* (which repeats the prior), never multiply nested time-prefix posteriors, and never append another amplitude likelihood to an already full-amplitude posterior.

This construction changes the inductive bias relative to TEAM's separate marginal heads. The coupling principle is already present in [Virtual Seismologist](https://doi.org/10.1007/978-3-540-72241-0_7), while physics-conditioned neural station/model-space processing has precedent in [McBrearty & Beroza2022](https://arxiv.org/html/2203.05144v1). A publishable contribution would require the specific controlled neural construction and transferable benefit, not relabeling generic Bayes or station covariance.

## What would count as progress

There are three distinct possible outcomes: a label-quality finding, a correction to the training objective, or improved extraction/combination of causal multistation information. Each is useful if supported; they must not be pooled into a claim of new source physics. Count independent earthquakes, preserve MA scores, report all deadlines and decisions, and retain failed controls. No inspected paper establishes a guarantee that posterior heavy tails reduce both high-magnitude MAE and bulk MAE/MedAE. That remains an empirical requirement for this project.

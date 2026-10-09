# Next method candidates: what survives the closest prior art

Research memo, 9 October 2026. Research only: no AWS access, dataset changes, training, existing-code edits, or commits for this task. Numerical results below are synthetic equation checks, not earthquake performance.

## Recommendation

I have not established a genuinely new statistical principle. Three tempting claims are already covered by close EEW literature: using an earlier magnitude posterior as a prior; preserving an unresolved high-magnitude tail; and a saturation/survival-dependent amplitude likelihood. A generic growth auxiliary head or mixture responsibility loss does not change that conclusion.

The most precise remaining small experiment is a **censored conditional likelihood for newly observed peak records**, computed in a representation invariant to a simultaneous change of digital counts and instrument sensitivity. Its narrow architectural change is to tie the probability of no new record and the density of positive growth to one underlying block-peak CDF. Use that likelihood only on evidence that the previous posterior has not already seen. This differs from a free hurdle head and from training-only future-growth supervision, but it is an application of classical censored regression and Bayesian conditioning. It is a candidate integration to test, not an established novel method.

A second, less ambitious candidate is exact instrument-unit canonicalization with a paired invariance constraint. That has a stronger immediate empirical motivation, but canonicalization/consistency regularization themselves are established. Do not force a rupture-continuation story onto what may be a sensor-unit correction.

## What our current evidence actually supports

I read `instrument_scientific_audit.md`, the paired instrument result, and `growth_mixture_score_checks.json`. The static instrument/site residual improves M≥4 event-macro MAE from .85318 to .67998 at 1 s, .69901 to .55015 at 3 s, and .60826 to .46508 at 5 s, while improving overall and median errors. Those are the stronger operational baselines for any candidate.

However, 94–98% of the record-weighted tail error reduction comes from HN records. The HH tail is slightly worse. Approximately 98% of VAL records use stations present in full TRAIN, and site features nearly identify stations. VAL has only 13 M≥4 events, five M≥4.5 events, one M5.1, and none M≥6. These findings support an instrument/domain investigation, not a claim to have solved large-rupture saturation. The audit's gain/unit versus family/site ablations should precede a larger physics claim.

The negative mixture-score experiment is also material: an intentionally wrong frozen growth model increased predicted tail prevalence from .05 to .08663. Tail mean-decision MAE improved from 2.85 to 2.7401 while bulk MAE worsened from .285 to .38391. With the correct known growth model, adding the overlapping marginal-growth score increased estimator variance by about 10% in that toy. An apparent tail improvement can therefore be a biased shift, and extra supervision is not automatically extra information about an already labeled target.

## Closest primary prior art and the claims it rules out

All links below are primary papers, author/institution-hosted papers, or official technical documentation. Some publisher pages only expose abstracts; those limits are identified. Search absence is not evidence of novelty.

| Primary source | Verified overlap and boundary |
|---|---|
| [Lancieri & Zollo 2008, RTMag, DOI 10.1029/2007JB005386](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007JB005386) | Full text, sections 3 and 6.2: evolutionary magnitude PDFs, previous PDF/prior information, early P/S peak likelihoods, and a uniform likelihood above early-P saturation. Consequently the high tail can remain controlled by the prior. This is particularly close prior art against “1 s posterior becomes the 3 s prior” or a flat unresolved-tail likelihood. Their implementation selects P-window measurements and assumes independent observations; this is not evidence that arbitrary overlapping neural posteriors may be multiplied. |
| [Trugman et al. 2019, DOI 10.1029/2018JB017093, author PDF](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf) | Full text: finite-window displacement saturation is tied to rupture duration and stress-drop variability; a time-dependent amplitude likelihood combines with a Gutenberg–Richter prior. Between-event variability limits the value of additional stations. This already supplies the core survival/saturation likelihood idea. It does not establish the same mapping for raw acceleration/velocity counts, mixed magnitude labels, or arbitrary learned record increments. |
| [Münchmeyer, Leser & Tilmann 2022, DOI 10.1029/2022GL098344](https://arxiv.org/html/2203.08622v1) | Full text: the conceptual posterior includes a Gaussian part and a declining Gutenberg–Richter part representing possible later asperities. Neural Gaussian-mixture distributions are learned from partial moment-rate functions and teleseismic waveforms. Their analysis distinguishes current-asperity development from additional asperities. The paper explicitly leaves local-waveform/geodetic possibilities open; it does not prove that every local 1 s recording is uninformative. A continuation mixture or a skewed magnitude density alone is therefore not new. |
| [Biasi & Wesnousky 2021, DOI 10.1785/0120200370](https://pubs.usgs.gov/publication/70263925) and [author draft](https://files.scec.org/s3fs-public/reports/2017/17064_report.pdf) | Official abstract and author draft: rupture arrest probabilities compound along fault bends/steps to form conditional rupture-length probabilities after initiation. A physical continuation hazard is established. Their known fault geometry is not available from our current single-station input; it cannot simply be inserted using the final catalogue location. |
| [Colombelli, Festa & Zollo 2020, DOI 10.1093/gji/ggaa343](https://academic.oup.com/gji/article/223/1/692/5873011) | Publisher-indexed full text: early P-peak amplitude rate is used to study final magnitude; the interpretation differs from some nondeterministic-rupture studies. Therefore a log-peak slope/relative amplitude growth feature is already nearby seismological prior art. A measured increase is not a direct observation of rupture survival. |
| [Cua 2004, Virtual Seismologist technical report](https://authors.library.caltech.edu/records/xze43-bdq08) | Official report record: Bayesian envelope modeling includes source, path, site and phase structure. Physical amplitude conditioning and static site effects are not new. |
| [Moore & Russell 2017, SIGVISA](https://proceedings.mlr.press/v54/moore17a.html) | Primary conference paper: generative waveform/envelope modeling with physical latent quantities and correlated waveform structure. A latent source/path nuisance model is established, although this is seismic monitoring rather than our strict-prefix high-tail benchmark. |
| [TEAM-LM, Münchmeyer et al. 2021](https://arxiv.org/abs/2101.02010) | Normalized waveforms with amplitude retained, multi-station structure and mixture-density magnitude prediction. A distribution head plus log amplitude is not new. |
| [Tobin, working-paper version of the 1958 limited-dependent-variable paper](https://cowles.yale.edu/sites/default/files/2022-08/d0003-r.pdf), [published DOI](https://doi.org/10.2307/1907382) | Original scanned working paper is accessible. Censoring creates an atom at a boundary plus a continuous density away from it; this is classical censored regression, not a new loss principle. The record-growth equations below are our derivation of that observation map. |
| [Thapa et al. 2026, DOI 10.1007/s10518-026-02403-1](https://link.springer.com/article/10.1007/s10518-026-02403-1) | Publisher abstract only: physics-informed preprocessing, U-Net++/attention for picking and Bayesian MCMC magnitude estimates. This rules out a broad claim that combining neural features, instrument-oriented preprocessing and probabilistic magnitude inference is new. The abstract does not establish matched 1/3/5 s performance against our baseline. |

Related author material for [Li, Taflanidis & Zhang 2023, DOI 10.1785/0120220259](https://doi.org/10.1785/0120220259) describes Bayesian model-class selection and heteroscedastic uncertainty in predominant-period magnitude regression. The publisher did not resolve in this session, so I do not rely on unverified implementation details from it.

## Candidate 1: a CDF-tied likelihood for newly observed peak growth

### Observation map and instrument symmetry

Let `x_c(s)` be counts, `S_c>0` the matched epoch sensitivity, and `b_c` the mean of a fixed 1 s pre-P baseline. Define native-unit motion `u_c(s)=(x_c(s)-b_c)/S_c`. Use the same baseline for every prefix. For the initial small pilot use the vertical component and preserve separate acceleration/velocity unit branches. Scalar sensitivity division is not full response removal; the [FDSN StationXML reference](https://docs.fdsn.org/projects/stationxml/en/latest/reference.html) and [ObsPy sensitivity-removal documentation](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.remove_sensitivity.html) specify the relevant metadata/operation.

For a previous deadline `a` and current deadline `b`, define

\[
A_a=\max(\epsilon,\max_{0<s\le a}|u(s)|),\quad
B_{a:b}=\max(\epsilon,\max_{a<s\le b}|u(s)|),
\]
\[
Z_{a:b}=\log_{10}B_{a:b}-\log_{10}A_a,\qquad
G_{a:b}=\log_{10}A_b-\log_{10}A_a=\max(0,Z_{a:b}).
\]

Here epsilon is fixed in the native physical unit, not a count floor silently changed by rescaling. `B` uses only the new interval. The operator is invariant to the digital re-expression `(x,b,S) -> (cx,cb,cS)`, `c>0`. This transformation does not change the earthquake or its magnitude. Applying it to a standardized count cache requires undoing and reapplying the saved standardization and recomputing all affected frozen-backbone features. Simply scaling standardized inputs is a different transformation.

For one unchanged channel, the gain cancels from the ratio in `G` even without explicit sensitivity correction, away from mismatched floors. Gain correction still matters for initial absolute amplitude and for cross-instrument comparisons. A ratio does not correct frequency response, and acceleration growth is not physically identical to velocity growth. Unknown response remains masked. INSTANCE's released 120 s detrending/resampling and manual P alignment remain upstream causality limitations; this head cannot undo them.

### One CDF determines both the atom and positive density

Given magnitude `m` and a precisely specified retained history `H_a`, model `Z` by a normalized CDF `F_m(z|H_a)` with density `f_m`. The observed growth likelihood, with respect to a point mass at zero plus Lebesgue measure on positive values, is

\[
q_m(g\mid H_a)=
\begin{cases}
F_m(0\mid H_a),&g=0,\\
f_m(g\mid H_a),&g>0.
\end{cases}
\]

Normalization follows immediately: `F(0)+integral_0^infinity f=1`. A practical two-output pilot uses `Z ~ Normal(mu(m,H_a),sigma(m,H_a)^2)` with a fixed positive sigma floor. Its loss is

\[
\ell_{\rm record}=
-\mathbf1_{g=0}\log\Phi(-\mu/\sigma)
+\mathbf1_{g>0}\left[\log\sigma+\tfrac12((g-\mu)/\sigma)^2+\tfrac12\log(2\pi)\right].
\]

The Gaussian has negative **latent** `Z` support, which is appropriate: a new block can have a smaller peak. The observed `G` never becomes negative. This fixes the invalid-negative-growth interpretation of an ordinary Gaussian `G` head. It also ties zero mass and positive shape, unlike a free hurdle/lognormal model. That restriction may be wrong; the free hurdle is the essential control. If numerical tolerance coarsens `0<=G<=delta` into a zero bin, its mass must be `F(delta)`, not `F(0)`. Finite-resolution positive bins require CDF differences rather than treating rounded values as exact densities.

There is also a stronger-information control: since we actually possess the new waveform, `Z` itself is observed even when negative. A model using its full density `f_m(Z|H_a)` discards less information. The censored representation is justified only if ignoring sub-record fluctuations improves finite-sample robustness or transfer. There is no information-theoretic superiority over the uncensored block peak. **This is a decisive falsification control**, not an optional cosmetic ablation.

### Valid 1 -> 3 -> 5 s recursion, including the hidden filtration trap

For a deliberately small model, let `H_1` contain the first 1 s waveform representation and allowed real-time instrument descriptors. Retain

\[
H_3=(H_1,G_{1:3}),\qquad H_5=(H_1,G_{1:3},G_{3:5}).
\]

For magnitude grid points `m_k`, define

\[
p_{b,k}=\frac{p_{a,k}\,q_k(G_{a:b}\mid H_a)}{\sum_j p_{a,j}\,q_j(G_{a:b}\mid H_a)}.
\]

This is exact within the specified generative model when `p_a` represents the same retained history used to condition `q`. No independence of the overlapping waveform prefixes is asserted. The first one-second representation is not multiplied again. An uninformative new likelihood, equal across magnitudes, leaves the distribution unchanged. **Zero growth does not imply zero information**: different magnitudes can assign different probabilities to a quiet new interval.

Do not silently replace `H_3` in the next likelihood by a full new 3 s waveform embedding while keeping `p_3` based on only `H_1,G13`. The new embedding carries information that was never assimilated into that posterior. One must either retain only the stated history, or jointly model and assimilate the added shape features. Similarly, multiplying `q13` onto the existing full-prefix 3 s predictor double-counts the observed growth. A trainable residual using full-prefix logits may still be a discriminative model, but it is not this exact recursion.

A stable source/path/site latent `U` requires joint state propagation,

\[
p_b(m,U)\propto p_a(m,U)q(G_{a:b}\mid m,U,H_a),
\]

or conditionals that correctly integrate `U` under its **updated** distribution. Independently re-integrating a fresh nuisance prior at each deadline falsely treats persistent uncertainty as new noise. Conditioning a flexible likelihood on sufficient retained history can implicitly account for this; a short embedding is only an approximation to sufficiency. Do not add a large latent module in the first pilot.

This recursion is not novel. The testable engineering delta is a tied censored likelihood plus gain-invariant observations under explicitly nested information. It replaces arbitrary posterior multiplication with a normalized observation model.

### Why no physically named survival state is yet justified

A positive mark indicates a new **local waveform record**, not proof of an ongoing rupture. S arrival, path effects, directivity, noise and filter transients can generate new peaks. A zero mark does not prove rupture arrest. Thus neither `F_m(0)` nor `1-F_m(0)` should be called a rupture survival probability. A future asperity can appear after an apparently quiet interval.

Magnitude dependence of `mu` and `sigma` can be shared smoothly by a small MLP receiving candidate `m`; this is an interpolation regularizer, not evidence for extrapolation. A duration scale proportional to `10^(M/2)` needs moment-magnitude/constant-stress-drop source assumptions and is inappropriate as an unquestioned constraint on mixed ML/Mw/Md labels. Likewise, imposing a saturated high-M likelihood is already close to RTMag and Trugman, and may deliberately preserve prior odds rather than reduce high-tail point error. Start with empirical, unit-specific conditional growth and test its held-event likelihood before adding such physics.

## Candidate 2: physical invariance with an explicitly separated sensor branch

Construct a new canonical prefix encoder from native-unit waveforms, normalized shape and retained physical log amplitude. Keep acceleration and velocity inputs distinguishable; do not concatenate their amplitudes as if they shared units. Exclude site coordinates/IDs and raw sensitivity from the canonical prediction path, while retaining response-validity and unit flags where needed. Use a separate optional site branch to measure its added value.

A diagnostic/regularizer is

\[
\mathcal L_{\rm gain}=\mathbb E_{c>0}\,D_{\rm JS}
\bigl(p(M\mid x,S),p(M\mid cx,cS)\bigr).
\]

For exact canonicalization this term is identically zero up to numerical effects; it is a test, not an extra learning signal. For a counts-based hybrid it penalizes dependence on digital representation, but cannot prove the model learned the correct source physics. A sensitivity-only perturbation changes the inferred physical motion and must not be treated as a label-preserving transformation. Randomly amplitude-scaling a physical waveform and shifting its label is yet another intervention, with different source/duration assumptions.

Compare counts plus gain/unit metadata; exact native-unit canonicalization; canonicalization plus family/site; and the current full-static baseline. Hold sensor family and event sampling fixed. Any new claim would have to concern demonstrated transfer across instruments/stations with calibrated magnitude distributions; canonicalization and JS consistency are not new methodological principles. This should be pursued only after the current factor ablations show what drives the improvement.

## Small, falsifiable pilot for candidate 1

1. **Use TRAIN only for fitting and design.** Preassign event folds, stratified where feasible without splitting events. Preserve source-row/trace/event/label digests. Existing reused VAL remains descriptive; sealed TEST is untouched until the method is frozen. No catalogue distance, magnitude type as an input, full-trace PGA/PGV/SNR, future picks, or future inventory end dates.
2. **Fit a common 1 s starting distribution with ordinary categorical log loss**, with the same allowed instrument-conditioned inputs and the same sampling-restoration weights across all arms. Use out-of-fold first-stage predictions/features where stacking/calibration is fitted. The current beta=5 weighted-Huber+.075CE predictor is an operational comparison, not automatically a calibrated Bayesian prior. An approximate or cost-weighted starting distribution breaks a claim of true-posterior calibration even if the update normalizes correctly.
3. **Freeze the common start and first-second encoder for the first comparison.** Fit separate 1->3 and 3->5 conditionals by labelled conditional NLL. Use actually observed new blocks at their deadlines, not 10 s TRAIN-only targets. No future values enter inference. Define exact history once and retain it consistently. Two fixed seeds and fixed epochs; no validation-based epoch/loss selection. This initial pilot has identical 1 s predictions by design and cannot claim a new 1 s gain.
4. **Matched controls:** common 1 s distribution with no update; a direct discriminative head on the same `H1,G13,G35`; a free hurdle/lognormal update on that same history; the CDF-tied censored update; and an uncensored `Z13,Z35` likelihood update with its correspondingly richer retained history. Parameter counts, input differences, fit objective and computation must be disclosed; use the same backbone and comparable head budgets. Compare all against full-prefix current instrument-conditioned predictors at 3/5 s, which retain more waveform-shape information. Different head parameterizations cannot be advertised as bitwise identical initialization.
5. **Mechanism checks before point-error claims:** held-event zero-mass calibration; positive-growth conditional PIT; whole mixed-distribution NLL; log likelihood ratios versus magnitude; sensitivity to digital gain changes; station/family splits; magnitude label errors; noise/clip failures; and actual missing-response masks. A free hurdle beating the tied CDF refutes the specific proposed restriction. Uncensored `Z` beating censored `G` weakens the rationale for discarding sub-record motion. A direct same-input head matching the recursion means the benefit is the feature, not sequential generative structure.
6. **Prespecified success rule:** exploratory bulk MAE, median AE and CVaR95 degradation each no greater than .005 magnitude relative to the stronger instrument baseline, with M≥4 event-macro MAE improvement at both 3 and 5 s and both seeds. Report uncertainty by event and each of the 13 reused-VAL tail events; the margin is a proposed practical tolerance, not a theorem or a post-hoc confidence claim. On a confirmatory evaluation, require the upper confidence bound on bulk degradation to meet the locked margin and the tail improvement interval to exclude zero; insufficient event support is inconclusive. Report mean and median decisions separately, bias, FPR/recall at M4, CRPS/Brier and coverage. A tail gain accompanied by a broad upward shift fails the intended task.
7. **Stop condition:** no incremental event-fold growth likelihood beyond magnitude-independent conditionals, failure against the same-input direct/hurdle controls, or failure against the full-static baseline is a negative result. Do not escalate architecture or tune repeatedly on the 13 VAL tail events merely to obtain a win.

This is a cheap feature/likelihood study, not justification for a large GPU search. Only if the normalized conditional observation model is both well fit and useful should it be integrated with learned new-window shape density, causal response correction, or a source-duration latent. Each addition would require a matched ablation and a fresh prior-art check.

## Local numerical checks and what they do not show

`check_record_innovation.py` is stdlib-only. Five assertions verify atom-plus-density normalization by numerical integration; digital gain invariance; informative zero increments; unchanged posterior for equal likelihoods; and propagation of a shared latent versus incorrectly resetting it. `record_innovation_checks.json` stores a fixed 100,000-record binary toy with magnitudes 2/5, prevalence .05, and `Z|Y` Gaussian with means -.7/.8 and sigma .6. Parameters are known, not learned; the toy was deliberately chosen to distinguish zero-growth probabilities.

| Oracle toy arm | Bulk mean-decision MAE | Tail MAE | Brier | NLL |
|---|---:|---:|---:|---:|
| Prior only | .284136 | 2.850000 | .047212 | .197573 |
| Correct censored likelihood | .142466 | 1.418769 | .023515 | .089619 |
| Incorrect density evaluated at zero | .230915 | 1.409174 | .024581 | .110939 |

The incorrect model has **slightly better tail MAE** despite worse bulk error and proper scores. This reproduces the need for the user's joint bulk/tail objective rather than offering a tail-only victory. At zero growth, correct posterior tail probability is .005436, versus .040982 for the wrong density-at-zero calculation. This is a specification sanity check, not evidence that Gaussian latent block peaks fit INSTANCE or beat a free hurdle.

Two additional exact calculations expose common update errors. A prior tail probability .05 updated once to .2 by a likelihood ratio 4.75 must remain .2 if the same evidence is replayed; falsely reusing that likelihood yields .542857. In a Gaussian shared-nuisance example with prior variance 4, persistent nuisance variance 1, independent observation noise variance .04 and three readings, correct posterior variance is .808511; treating the readings as independent marginal observations gives .319018. Extra windows do not remove a shared uncertainty by repetition.

These checks establish that the proposed equations are coherent under their assumptions and that the negative controls fail in the expected ways. They establish neither novelty nor improved earthquake error. A paper-worthy claim would need repeatable gains beyond the instrument-conditioned baseline, on independent events and stations, with enough large events and an honest comparison to RTMag/Trugman/TEAM-LM and same-input statistical controls.

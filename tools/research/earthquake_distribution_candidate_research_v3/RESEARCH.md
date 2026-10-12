# Distribution candidate research V3: shared short-noise uncertainty

Research-only recommendation, 12 October 2026. No actual records, private metadata, predictions, new features, fits, cloud controls or processing-source changes were used in this task. Read the public current checkpoint, completed native-count pilot report, amplitude adequacy proposal and older growth/censor/revision reports. Findings below are hypotheses and primary-source comparisons, not novelty certification or accuracy results.

## Decision

Finish and preserve the current four-parameter TRAIN-only amplitude-age adequacy study before changing its observation model. The smallest worthwhile NEW experiment is an uncertainty-aware amplitude likelihood in which the uncertainty of the three-second precontext normalization is an explicit observation nuisance, shared across deadlines. Compare it against ordinary heavy-tailed and heteroscedastic likelihood controls and an ordinary-feature control. Do not start with another network, tail multiplier, rupture-survival model or cumulative-posterior multiplication.

The possible contribution is narrow: an effective, native-grid-preserving treatment of finite short-precontext normalization and its cross-deadline dependence for early Mw inference, demonstrably better than matched ordinary controls. Uncertain-noise marginalization, Student-t likelihoods, heteroscedastic regression, Bayesian updating and constrained risk calibration are already established. No exact EEW implementation of this entire narrow recipe was verified in the inspected primary sources; that bounded search does not establish priority.

The native-count six-fit pilot failed its fixed information gate: W high-Mw error worsened at every deadline in both seeds, despite some lower-Mw gains. The separate activity preflight had four off-transition groups against five required. Those negative results remain. The earlier INSTANCE censored-innovation and growth-auxiliary studies also failed the project objective; a new name for either is not a contribution. The new amplitude baseline and any noise study need their own prospective protocols and retained negative outcomes.

## Primary prior art that changes the proposal

| Primary work | Verified scope and implication |
|---|---|
| [Lancieri & Zollo 2008, Bayesian real-time magnitude from P/S peaks](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2007JB005386) | Sequential/evolving peak-based magnitude PDFs precede this project. Its inspected methods assume lognormal, independent station observations. Generic “1s posterior becomes the 3s prior” is not new. |
| [Trugman et al. 2019, peak-displacement saturation](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf) | Time-dependent saturation, magnitude priors and Bayesian amplitude uncertainties are established. The paper discusses between-event variability and dependence among stations. Noise marginalization cannot overcome an intrinsically uninformative early rupture prefix. |
| [Münchmeyer et al., probabilistic rupture predictability](https://arxiv.org/html/2203.08622v1) | Rupture-duration survival and probabilistic early-size reasoning are occupied. This is not a new physical rupture-arrest model, and receiver noise/count peaks are not moment-rate source histories. |
| [Wu et al., multi-event Bayesian EEW, 2015](https://academic.oup.com/gji/article/200/2/791/610068) | Gaussian amplitude/time likelihoods and station noise means/variances already enter EEW source inference. Noise-aware Bayesian estimation is not itself a novelty claim. |
| [Prior-informed IPF with ETAS, 2026](https://link.springer.com/article/10.1186/s40623-026-02488-7) | Inspected full methods use observed five-second velocity maxima, trigger-time likelihoods and noise contributions for untriggered stations. It is a different network/location problem, but constrains generic “noise plus prior plus likelihood” claims. |
| [Zollo et al. 2023, evolutionary shaking forecast](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022EA002657) | Inspected preprocessing compares current displacement peaks with pre-event noise peaks and adapts filtering by quality. SNR normalization/filtering is already used. A future modification should retain unreliable rows rather than manufacture improvement by deleting them. |
| [Hongjie Li 2023, Notre Dame dissertation](https://curate.nd.edu/articles/thesis/Bayesian_Methods_for_Magnitude_Estimation_in_Earthquake_Early_Warning_Application/24884454) and [Li et al. BSSA, DOI 10.1785/0120220259](https://doi.org/10.1785/0120220259) | The university/author-authored indexed primary abstracts explicitly describe heteroscedastic magnitude-regression errors, parameter uncertainty and Bayesian model selection; the dissertation describes station hierarchy. Publisher full BSSA text was inaccessible here. Claiming first heteroscedastic or hierarchical EEW likelihood would be false. |
| [Talbot & Thrane 2020, uncertain noise PSD](https://arxiv.org/html/2006.05292v2) | Full primary text derives noise-estimate-dependent likelihoods, including a distinction between mean-estimated PSD and median-estimated PSD. Student-t uncertainty from a particular mean-PSD construction does not justify a Student-t law for our median of twelve time-domain powers. This is the closest conceptual cross-domain predecessor. |
| [Aravkin et al. 2012, robust seismic inversion](https://slim.gatech.edu/Publications/Public/Journals/MathematicalProgramming/aravkin2012MPrid/aravkin2012MPrid.pdf) | Student-t robust error penalties are established in seismic inversion. A global Student-t amplitude likelihood is an essential comparator, not the novel arm. |
| [Gouveia & Scales 1998, Bayesian seismic waveform inversion](https://doi.org/10.1029/97JB02933) | Ambient measurement noise and theoretical/model errors are distinct uncertainty contributions. Estimating ambient noise accurately does not calibrate all magnitude-model residual variance. |
| [Miller & Dunson 2019, coarsened posterior](https://pmc.ncbi.nlm.nih.gov/articles/PMC6961963/) | Fractional likelihood/tempering for model robustness is established. A noise-dependent likelihood power is not ordinary Bayes unless a coherent observation model is supplied; its magnitude posterior still needs proper-score evaluation. |
| [Minson et al. 2019, limits and alerting](https://pmc.ncbi.nlm.nih.gov/articles/PMC6385233/) | Optimal alerting depends on costs and ground-motion uncertainty. Lower missed-alert costs do not establish lower magnitude MAE or preserve calibrated Mw probabilities. |
| [Conformal Risk Control, ICLR 2024](https://openreview.net/pdf?id=33XGfHLtZg) and [Learn then Test](https://arxiv.org/abs/2110.01052) | Risk-control calibration and simultaneous non-monotone risk tests are established. Independent calibration assumptions, risk definitions and bounds are required; tiny stratified reused TRAIN does not magically certify natural-population zero-regression MAE, NLL, median or maximum error. |

## What should change in the distribution

Keep the frozen baseline observable definitions. For component c, center native counts using only the same [T0-3,T0) mean. Let Q_cj be its twelve exact quarter-second centered powers. The existing estimate is Nhat_c=sqrt(max(1, median_j Q_cj)); noise-floor status is observed and retained. At deadline h, the selected current native peak yields y_h=log10(max(A_h,1)/Nhat), L_h=-log10 Nhat, and u_h=T0+h-P. No sample beyond the original cutoff enters y_h.

The baseline likelihood treats Nhat as known. The proposed research asks whether some apparent extreme scalar evidence instead reflects an unstable short noise reference. It might prevent an unreliable low or high normalized peak from pulling magnitude excessively. This is a plausible reason for better tail and bulk behavior, not a guarantee. If noise is stable, the uncertainty-aware arm should converge to the original baseline.

A low-parameter empirical experiment can compute twelve delete-one-quarter estimates per component, without touching later data:

    eta_cj = log10 sqrt(max(1, median_{k != j} Q_ck))
    eta_bar_c = mean_j eta_cj
    d_cj = eta_cj - eta_bar_c
    v_c = (11/12) sum_j d_cj^2.

The full precontext centering remains fixed; do not recompute it by horizon or by delete-one subset. Delete the same quarter index across all three components, so each nuisance draw is a vector and preserves observed cross-component block dependence. v is a jackknife sensitivity proxy, not a certified posterior variance of true noise: adjacent quarters can be correlated; median non-smoothness, the even/odd median convention and floor censoring matter. In particular v=0 can result from a floor or repeated order statistics, and does not prove exact noise knowledge. Floor events must be reported separately; no post-result epsilon or support repair.

For an uncensored scalar model with baseline mean mu(m,u)=a+b*x_m+c*x_u, the first sensitivity-mixture arm is

    ell_h(m) = (1/12) sum_j Normal(y_h; mu(m,u_h)+d_selected,j, sigma).

For A_h<=1, use the corresponding mixture of CDFs:

    ell_h(m) = (1/12) sum_j Phi((L_h-mu(m,u_h)-d_selected,j)/sigma).

This is a normalized empirical conditional observation model with four fitted baseline parameters and twelve fixed component offsets; all-real-line magnitude prior normalization remains necessary. Its uncertainty proxy construction is not a genuine latent-noise posterior derived from colored waveform physics. Call it a noise-reference sensitivity mixture until independently calibrated. Offsets are centered to avoid covertly replacing the baseline noise estimator. A conventional Gaussian width control uses sigma_h^2=sigma^2+v_selected; a global fixed-df Student-t control distinguishes the effect from generic robust tails.

The original peak selector depends on observed component amplitudes. Holding the original winner fixed for the mixture is a conditional feature-model approximation; it does not marginalize the random winner selection. This must be stated and tested with a matched fixed-literal-Z or fixed-first-deadline-component control. An eventual full generative model needs the joint component amplitudes and winner event. Do not call arbitrary scalar-mixture normalization proof that the complete waveform observation model or magnitude posterior is calibrated.

## When an analytic Student-t is actually justified

For an assumed Gaussian residual e conditional on unknown variance s2, use a proper inverse-gamma law with shape alpha and scale beta:

    e | s2 ~ Normal(0,s2),  s2 ~ InvGamma(alpha,beta)
    p(e) = Gamma(alpha+1/2)/(Gamma(alpha)*sqrt(2*pi*beta))
           * (1 + e^2/(2*beta))^(-alpha-1/2)
         = StudentT(df=2*alpha, location=0, scale=sqrt(beta/alpha)).

This identity is standard marginalization, not a contribution. Choosing alpha/beta from this project's twelve median/floored power estimates requires a separate justified observation model; simply setting df to twelve or to the raw native sample count is invalid under unknown autocorrelation. Log native maxima are not Gaussian raw samples, and ambient waveform noise variance is not the same as total log-amplitude model error. An empirical fixed-df Student-t arm can nevertheless be fitted and evaluated honestly as a robust baseline.

## Sequential 1 -> 3 -> 5 without duplicate evidence

The initial low-cost experiment should retain independent per-deadline inference from a common original prior, as the current adequacy protocol does. This avoids introducing a second untested operator simultaneously. Multiplying the 1s, 3s and 5s cumulative-amplitude likelihoods is wrong if it treats repeated early samples/noise as independent.

A later conditional update needs a shared state, not three separately marginalized noise draws:

    q_1(m,eta,g) proportional to prior(m,eta,g | precontext) * p(D_1 | m,eta,g)
    q_3(m,eta,g) proportional to q_1 * p(D_(1,3] | D_1,m,eta,g)
    q_5(m,eta,g) proportional to q_3 * p(D_(3,5] | D_1,D_(1,3],m,eta,g).

eta is the same precontext noise nuisance; g is an optional station/path/gain nuisance, not known true sensitivity. New D windows are disjoint original received/native windows. The precontext likelihood is incorporated once. Marginalize eta/g only for reported Mw probabilities; do not reset their posterior each update. A discretized noise-mixture component index can be retained as the shared state in a later empirical implementation.

For cumulative maxima C_new=max(C_old,B_new), an unchanged maximum has conditional probability P(B_new<=C_old | history,m,eta,g), an atom; a new record uses the appropriate conditional density above C_old. Independence of B_new from history is a modeling assumption that needs tests because waveforms have serial correlation. The earlier failed CDF-tied censored-innovation model already explored closely related atom logic. This is therefore a compatibility requirement and later mechanistic ablation, not the fresh contribution of this note.

Likewise q_3 proportional to q_1 * ell_3/ell_1 merely replaces one marginal evidence model with another if ell_1/ell_3 are separately fitted cumulative marginal likelihoods. It is not equivalent to conditioning on the full observed path. Plain ell_3 multiplication counts the early prefix twice; a ratio may discard historical record timing. Neither algebra alone is a new inference method. Future-noise invariance, unchanged-max handling, correct censor mass and sequential-vs-joint equality on invented models are mandatory before actual updating.

## Gains, units, site effects and selected priors

For a positive representation scaling x -> k*x, both physical signal and ambient noise counts scale together, so A/N is invariant away from the fixed one-count floor. The jackknife centered log offsets are invariant too. This is a useful invented representation test, not an earthquake-magnitude augmentation: native integer quantization and the one-count floor break the continuous idealization. Scaling signal alone changes SNR and is a different intervention.

Unknown frequency response, source distance, directivity, site amplification and station-specific ambient noise do not cancel simply through count SNR. A site can have quiet ambient noise and strong earthquake amplification; an accelerometer and velocity sensor need not encode the same source variable. The present sensitivities have no full response stages, so no calibrated displacement or moment-scaling law is earned. A shared log-gain/random station intercept is established hierarchical modeling and, with sparse repeats, can be confounded with magnitude. It needs a matched ordinary station/context comparator and leave-station/group stress tests, not a new free scalar per event.

The current public common cohort has34TRAIN with26Mw>=5.5 versus22DEV with13Mw>=5.5; lower counts are8/9. This selected prior is materially unlike natural earthquake prevalence. Correct noise uncertainty cannot fix prior selection shift, missing typed Mw anchors, station confounding or physical nonidentifiability. Do not multiply Mw>6 mass by ten and call the result calibrated. That is a tilted decision distribution; reported density and point action must be evaluated separately.

## Feasible next controlled experiment

This note supplies a recommendation only: it grants no new extraction, fitting, DEV prediction or acquisition authority.

1. Preserve the current amplitude adequacy outcome first. If it fails its fixed gate, record that failure; do not revise its lambda grid or folds. A new noise study requires its own explicit rationale/protocol and a narrow observation-reliability hypothesis, with no automatic larger roster.
2. Freeze new TRAIN-only extraction of twelve precontext powers per literal component plus the original scalar features. Use the same original65/195 manifest/common cohort, clocks, native hash checks and bounds. All common TRAIN missingness vetoes the study; no DEV waveform inspection or new queries. Current feature source remains unchanged.
3. Use the same fixed operational-group outer/inner folds, group/event/h weights, four baseline coefficients, optimizer limits and lambda candidates across arms. The small matched set is G0 plug-in Gaussian; T5 fixed-df5 Student-t; GV Gaussian sigma2+v; NM centered12-component noise mixture; GF ordinary Gaussian with a mean feature d*sqrt(v), one extra slope; and a fixed TRAIN-event permutation of nuisance vectors for NM. GF has one extra coefficient and must be identified as a capacity control, not an exact parameter match. NM/GV add no fitted coefficients. Each selects regularization only inside fitting groups. No post-result df/mixture/epsilon search.
4. First compare each deadline independently. Main scores are held-group TRAIN posterior NLL/CRPS, highMw>=5.5/>=6 MAE, bulk MAE/MedAE/CVaR95/maximum and lower-Mw error; actual mean/median are uncapped. Report floor/non-floor and noise-sensitivity strata without searching a winning subset. Every candidate must beat G0 and the strongest ordinary matched control at ALL1/3/5 under frozen criteria; parent defines simultaneous uncertainty/maximum veto. Positive nested TRAIN is adequacy only, not independent validation.
5. Observation-nuisance evidence requires NM beating GV/T5/GF and shuffled NM; otherwise prefer the simpler established model and reject the mechanistic claim. If fixed-component controls erase the gain, winner-selection coupling may be the cause. If a Student-t alone wins, report robust regression as the finding; no claimed noise-marginalization invention.
6. Only after reproducible independent improvement consider shared-state conditional sequential updates, with fixed-prefix, fresh-prefix replacement, stale-prefix multiplication negative control and empirical shared-vs-redrawn-noise ablations. Keep current proper-score-trained density separate from any risk-sensitive action.
7. Natural bulk-preservation claims need a fresh representative calibration/test cohort with typedMw, matched clocks/station availability, group isolation and calibration not reused for architecture discovery. Larger-study support floors are not power calculations. Existing conditional50-roster rules and old failed gates remain unchanged. Station/region transfer and physical sensor-response compatibility must be audited before a published-performance claim.

No inference-only rule can guarantee better conditional high-Mw MAE and equal natural bulk/worst/proper-score error for arbitrary uninformative early observations. A tail-prior or asymmetric action can buy missed-event reduction at an overprediction cost. The experiment must demonstrate information/robustness gains, rather than rename that tradeoff.

## Decision/risk controls remain a separate layer

For calibrated q(m|prefix), density mean minimizes squared error; density median minimizes absolute error. A weighted/asymmetric loss yields a different Bayes action. Multiplying upper-tail mass changes q, not merely the action. Save and score the original density, mean, median and any separate action so a changed cost preference cannot masquerade as distributional accuracy.

A later fixed finite action family could be calibrated with Learn then Test against paired loss differences to a baseline across deadlines. With genuinely independent group-level calibration, valid risk tests and predeclared bounded risks, simultaneous rejection can identify noninferior actions. This is standard LTT specialization, not a new theorem. Unclipped MAE/NLL/CRPS and worst-case maximum do not automatically satisfy bounded-loss finite-sample assumptions; clipping risk for a bound changes the certified metric and must not replace uncapped reporting. Zero-margin simultaneous natural-bulk nondegradation may be unresolvable with the present sparse selected sample. Ordinary split conformal coverage or a bootstrap confidence interval is not proof of the requested whole metric vector.

The proposed six-arm nested comparison has at most630 outer/inner fits before any fullTRAIN continuation (6*105), or525 new fits only if the already frozen G0 artifact is exactly reusable under identical folds/observations/objective. This is a bounded CPU study, not six GPU trainings. Fit/source/whole deadlines must be fixed anew; do not assume the old900s adequacy controller can contain a six-arm maximum. Prefer no fullTRAIN continuation in this research screen. The cost and fit count are advisory; no actual run was authorized or launched by this note.

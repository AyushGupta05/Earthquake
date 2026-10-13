# Prospective marked-noise distribution operator V1

13 October 2026. PUBLIC source/research preparation only. This is a separately proposed scientific operator, not a modification/continuation of frozen receiver-renewal V2, processing continuation V3 or numerical adapters. No actual rows, waveforms, weights, forecasts, agreement records or current comparison outcomes were inspected. Existing negative/incomplete studies retain their status. Root scientific review precedes independent numerical-core implementation; actual feature extraction/fits require later separate source/runtime/input/resource/publication/admission gates.

## Hypothesis and prior art boundary

A shared finite uncertainty distribution for the same short pre-T0 noise reference, carried jointly with Mw through continuous new-cell amplitude evidence, may prevent repeated false certainty and preserve within-state magnitude information. The narrow falsifiable contribution is this noise-conditioned *observation operator and evidence accounting* for native EEW prefixes, not generic Bayesian updating, Tobit regression, Gaussian mixtures, AR models, HSMMs, entropy or duration. No global firstness or accuracy claim is made.

Evolving Bayesian magnitude PDFs already appear in [Lancieri & Zollo2008](https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2007JB005386). Time-dependent displacement saturation/between-event uncertainty precede us in [Trugman etal2019](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf). [TEAM-LM2021](https://arxiv.org/pdf/2101.02010) already predicts magnitude densities from waveforms and documents rare-event/data-coverage bias. [Münchmeyer etal2022](https://arxiv.org/html/2203.08622v1) separates distributional growth potential from point predictability, with important source-time/teleseismic limits. [Zollo etal2023](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022EA002657) already uses evolving growth/plateau observations; [Beyreuther & Wassermann2011](https://npg.copernicus.org/articles/18/81/2011/) already uses explicit duration in seismic classification. Estimator-specific uncertain-noise likelihoods are established in [Talbot & Thrane2020](https://journals.aps.org/prresearch/abstract/10.1103/PhysRevResearch.2.043298); their PSD law is not a law for our correlated/floored time-domain median. Limited-variable censor likelihood is classical [Tobin1958](https://doi.org/10.2307/1907382). A useful specialized result must survive the controls below.

## Native observables and causal boundary

Retain literal E,N,Z or1,2,Z component order, exact original integer/rational clocks/pieces, pre-T0 mean and twelve nonoverlapping .25-second pre-T0 noise powers. With selected P>=T0, this is also pre-P. Let Q_cj be each post-P complete .25-second cell's centered native power and Nhat_c=max(1,median of twelve pre-T0 powers). Use all THREE component ratios R_cj=Q_cj/Nhat_c, not a selected maximum alone. No new frequency/response/sensitivity conversion, interpolation, rotation or source distance. New extraction would need its own qualified-native hash/clock/complete-roster source, before any values; this proposal permits no extraction.

Forecast h uses ONLY complete cells [P+(j-1)*.25,P+j*.25) with end<=T0+h. Exact h1/3/5 prefixes extend by8cells; partial cells are not treated as zero or completed with future samples. The first .25-second cell enters ONCE. The prior below excludes first-cell waveform/mark/activity; do not reuse an amplitude-conditioned first-cell prior and append an independent noise prior. Cached q_.25 is the *joint* Mw/noise posterior from the first complete cell; later q_1/q_3/q_5 add suffix cells only. No terminal exit or permanent arrest is invented at a deadline.

The observed activity bit, if needed as a past-history covariate, is exactly b_j=1[max_c R_cj>9], with equality quiet. It is deterministic from the same marks. It NEVER contributes another Bernoulli/hazard likelihood. Continuous amplitude carries the state probability implicitly.

## A fixed, empirical shared noise sensitivity distribution

For each pre-T0 quarter index ell=1..12 and component c, compute

    eta_(ell,c)=log(max(1, median_{k!=ell} noisePower_(c,k))),
    nu_(ell,c)=eta_(ell,c) - (1/12)*sum_d eta_(d,c).

Delete the SAME quarter across allthree components. Fixed weights w_ell=1/12 and the joint vector nu_ell preserve the observed cross-component sensitivity. Centering fixes the nuisance-location gauge; use natural log of POWER, not amplitude log. These points are a **finite noise-reference sensitivity prior**, not a derived posterior for true noise power. No iid twelve-degree Student-t/inverse-Gamma claim, floor-zero certainty claim or independent-component resampling. All identical points/zero spread remain valid and unmodified; the candidate then reduces to plug-in uncertainty. Fixed spread multiplier1, no DEV calibration/tuning. All learned regression/prior/noise-residual coefficients are TRAIN-only; per-event precontext support construction is an operational fixed transform permitted at prediction after source admission, not DEV fitting.

Let m~pi(m|s), a proper all-real five-Gaussian prior conditional only on available immutable descriptors/precontext. Let ell~Categorical(w), independent of m GIVEN those observed initial descriptors in this working model. It is the SAME ell through every component/cell/deadline. This assumption is explicit; event selection/site/noise correlations may invalidate calibration. Unknown station gain is not another unrestricted per-event latent variable.

## Normalized conditional marked observation law

Use a declared coarsened log-ratio observation with delta=-12, fixed before values: if R<=exp(delta), including exact0, report the symbol C (left-censored); otherwise report y=log(R)>delta. Raw R remains retained for diagnostics. C is a designed report bin aggregating zero/tiny ratios; it is NOT an assertion that the native ADC has a known physical threshold or that the one-count noise floor measures uncertainty. Never substitute delta as an uncensored likelihood point. No after-data epsilon, zero-event deletion or magnitude clipping. Finite native quantization above this bin is a working continuous-density approximation; a separately frozen interval-quantization control would be needed before a claim of exact ADC likelihood.

For component c at cell j and shared state ell, latent logratio V_cj is Normal(mu_cj(m,H_(j-1))+nu_(ell,c),sigma_c²). Report C if V<=delta, otherwise y=V. Components are conditionally independent given m,ell,observed past in the first prototype; serial dependence enters observed-history regression, not a claim of independent normalized cells. With sigma_c>=.05 fixed prospective lower numerical bound in log-ratio units,

    K_c(C|m,ell,H)=Phi((delta-mu_cj(m,H)-nu_(ell,c))/sigma_c),
    K_c(y>delta|m,ell,H)=NormalDensity(y;mu_cj(m,H)+nu_(ell,c),sigma_c).

Under the mixed measure (one C atom plus Lebesgue density above delta), each kernel integrates to1. The apparent absence of a truncated-density denominator is deliberate: the positive density integrates to its complement probability. A positive mark's Jacobian 1/R is unnecessary when the modeled/output observation coordinate is y; use it if comparing a density in raw-R coordinates. Jacobians independent of m/ell cancel in normalized Mw inference but not observation likelihood reporting.

This is a normalized statistical feature-report model, not a physical source-moment process. For a=log9>delta, the model-implied active probability is 1-product_c Phi((a-mu_cj-nu_ellc)/sigma_c), including zero/censor mass in the quiet probability. Do NOT multiply that probability by the continuous kernels again.

The prototype conditional mean is affine in m:

    mu_cj=a_c+b_c*m+d_c*log(1+u_j)+e_c*m*log(1+u_j)
          +rho_c*previousObservedLog_c+kappa_c*previousCensorFlag_c,
    u_j=.25*(j-1).

For first cell, previousObservedLog=0 and previousCensorFlag=0. Thereafter a past C symbol uses its known bound delta ONLY as a regression covariate, together with flag1; it remains a censor probability in its own observation likelihood. This conditions on observed past, rather than pretending a censored past latent value was measured. There is no future-horizon input or final magnitude-dependent parameter fitted per event. No reset-age term in V1: duration/age mechanisms remain separate falsifiers and are not combined with both new changes initially.

## Joint updating and identifiability

    q_J(m,ell) ∝ pi(m|s)*w_ell*product_(j<=J,c) K_c(observation_cj|m,ell,H_(j-1)).

Report q_J(m)=sum_ell q_J(m,ell). Noise-state posterior probabilities are retained, not reset to w per deadline. Update suffix kernel factors ONCE using the original observed history. Sequential and joint evaluation must agree. Do not multiply cumulative1/3/5 likelihoods; do not integrate ell per cell then call the result a shared reference.

If b_c=0 and e_c=0 for every c, marks do not distinguish m, and the posterior must remain pi; source tests enforce this. If an unrestricted gain g could shift mu by beta*m+g, m+d/g-beta*d is observationally equivalent. Centered finite nu is a statistical reference assumption, not a physical gain anchor. Ambient noise, station/path response and earthquake signal amplification do not generally cancel. Scaling all signal+noise counts together leaves R invariant away from the fixed one-count floor/quantization; that is a representation test, not a magnitude augmentation. Receiver power evolution/quiet intervals are not calibrated rupture duration or released moment. Saturated/uninformative prefixes must retain uncertainty, not receive automatic high-tail mass uplift.

## Practical numerical core, not a training architecture

Implement a SMALL independent pure NumPy/SciPy core accepting supplied prior arrays, fixed12 joint nu vectors/weights and bounded already-causal per-cell affine means/scales/point-or-censor observations. No data IO, waveform builder, NN, optimizer, actual inference permission or learned parameter fitting. At most20cells/3components/12states/5prior components, all-real m; no finite magnitude support. Source10-second whole-call budget/1million evaluation cap and parent hard controls are prospective requirements, not guaranteed performance.

All-positive uncensored marks permit analytic Gaussian-product completion for EACH(ell,prior-component), resulting in up to60 Gaussian components with exact marginalized weights. This special case permits analytic mixture CDF/mean/NLL/CRPS/quantiles. Censored marks add Gaussian CDF/probit factors and destroy that conjugate closure; the even/odd/floored median sensitivity prior itself is NOT an inverse-Gamma conjugate noise estimator. Treat the finite prior as fixed input, not as evidence of an analytic true-noise marginalization.

For any censoring, retain positive-mark Gaussian completion, then independently integrate each remaining log-concave Gaussian-times-probit component over the entire real line using mode/curvature scaling, with GH64/128 and adaptive mean/logZ/targetNLL parity<=1e-4. Stable logPhi and signed/censored extremes must be tested. Independent proper CDF/quantiles/CRPS use the same normalized conditional density, no Gaussian surrogate. Fail closed on numerical/time/normalization disagreement, keep full inputs/errors, no pointwise repair/fallback. Before actual admission, test and time worst-case60components×60censored factors, not just analytic easy cases. The implementation may initially expose only independently verified normalization/mean/NLL/CDF; no unverified proper-score output may be used in an actual comparison.

## Matched controls and scientific falsifiers

The numerical core is not a fitting authorization. A later separately frozen fitting protocol retains original300updates/seeds20261012/13/noDEV tuning/finalonly and original all1/3/5 bothseed .02high55-improvement/bulk-worst/proper guard, with no epoch/tolerance/criterion rescue. Exact fitted-capacity architectures and fixed data support require ROOT admission before values; no inference from this paper draft.

1. Shared-noise candidate above vs same-parameter plug-in nu=0 control; finite uncertainty adds NO fitted parameters. The independent-noise control redraws ell per cell (normalize each conditional kernel mixture) with same regression/prior parameters: a valid different model, not the candidate's sequential semantics.
2. Mark-only/time control replaces the six past-history coefficients with genuine extra global-time/magnitude-time curvature regressors; same18 means/3scales/15prior nominal coefficients=36. AR shared-noise candidate vs this control tests whether temporal history is useful. A correlated/heteroscedastic Gaussian observation control and an ordinary robust residual control are essential competitors before claiming special nuisance value.
3. Same-capacity ordinary-feature F control: five-Gaussian prior (15 nominal coefficients) with a shared direct posterior mean shift from20 fixed causal prefix summaries and one global variance scale (21 real coefficients)=36. Summaries: percomponent last/mean/max/least-squares-time-slope/censor fraction (15), current log1+elapsed time, complete-cell count (2), precontext nuisance SD percomponent (3). All learned only in TRAIN. Every declared coefficient must receive meaningful TRAIN gradients/variation before inference; dummy allocations/unused coefficients forbidden. Exact architecture/scaler/static-prior implementation is frozen only in the later fitting protocol; if real used-degree matching<=5% cannot be met, no capacity-matched claim/automatic fit.
4. Keep the strong full-prefix waveform B/F controls from the project as separate required competitors; the small mark core is a compression and does not retain waveform phase/spectral information. A nominal36-parameter F control alone cannot prove superiority to modern waveforms. Never call raw counts a response-calibrated reproduction of published displacement/acceleration benchmarks.

Reject the narrow claim if plug-in/redrawn/correlated-noise/directF controls erase its gain, if shuffled noise-support vectors retain the effect, if nuisance posteriors absorb the magnitude prior without held-group proper gains, if floor/site strata determine the effect, or if any original high/bulk/worst/proper guard fails. Report scalar conditional information/proper scores, noise-state posterior, allzero/censor/floor cases, station/group strata, each deadline/seed and invalid numerical cases. Within-TRAIN grouped validation/admission precedes fresh DEV evaluation; existing reused exploratory DEV cannot certify population bulk preservation, global novelty or published-benchmark superiority. Independent representative typed-Mw/event/station/region/time-clock validation remains necessary.

This proposal asks whether coherent continuous observations with one shared uncertain reference help. No guaranteed gain follows from Bayes or more latent states. Current fixed C/T comparison is completed or retained separately before choosing the next actual scientific experiment.

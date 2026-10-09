# Nuisance and rupture-state candidates: narrow hypotheses, not novelty claims

9 October 2026. Read-only research and inline numerical equation checks. Only this
memo was written; no repository code, dataset, AWS resource, GPU job or commit was
changed. Coordinated with `external_benchmark`, which is separately investigating
source-only amplitude/time transport through a fixed path/instrument operator.
That augmentation proposal is not duplicated here.

## Recommendation

I have **not established a new statistical principle or an unoccupied architecture**.
Free nuisance-marginalized location/scale distributions reduce to known mixture
models. Joint magnitude/distance inference, station-specific calibration,
stress-drop estimation, saturation likelihoods and probabilistic rupture tails all
have strong primary precedents. Two limited empirical modifications remain worth
considering, in this order:

1. **Geometry-anchored amplitude likelihood:** retain a learned joint distribution
   over magnitude and geometry from the available waveform shape, then update it
   with one physically calibrated amplitude likelihood and integrate geometry.
   This is principally a stronger nuisance baseline. A possible contribution would
   be an independently validated correction of a specific fixed-depth bias at
   fixed deadlines, not “Bayesian magnitude estimation” or “learning uncertainty.”
2. **Prospective growth/turnover likelihood:** infer a distribution over a local
   envelope's turnover time from fixed, already observed time blocks, explicitly
   carrying the same path/site offset through 1→3→5 s. Compare a universal-growth
   null against a constrained magnitude-dependent growth alternative. This has a
   sharper scientific question, but currently insufficient evidence to justify a
   large training run or the claim that its latent variable is rupture duration.

Neither automatically improves tail point error while preserving bulk error.
Nuisance removal can reduce estimation variance; broadening unresolved tails may
instead increase mean error and false alerts. Performance must be measured against
the strongest instrument/proper-score baseline, not the old counts-only backbone.

## Closest primary work and what it rules out

| Source and access | Verified relevance |
| --- | --- |
| [Zhang, Zhang & Tian 2021, DOI 10.1029/2020GL089394; author paper](https://arxiv.org/pdf/2006.01332) | Normalizes network waveforms and predicts a magnitude-residual distribution, restoring log amplitude afterward. Amplitude plus normalized shape, or shifting a predicted PDF by log amplitude, is not a new construction. |
| [Meier, Heaton & Clinton 2015, Gutenberg, DOI 10.1785/0120150098; institutional abstract](https://www.research-collection.ethz.ch/entities/publication/0614efee-93a6-45c8-8708-980276fa9f2f) | Filter-bank observations drive evolutionary joint magnitude/distance PDFs. Jointly inferring attenuation geometry to reduce early uncertainty is established; an additional depth component would be a particular extension, not the first joint source inference. |
| [Trugman et al. 2019, DOI 10.1029/2018JB017093; full author PDF](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf) | Fits finite-window displacement saturation from rupture-duration/stress-drop variability and combines amplitude likelihood with a magnitude prior. The paper treats 1–20 s windows and discusses shared event variability. Saturation, survival integration and a GR-controlled unresolved tail are close prior art. |
| [Münchmeyer, Leser & Tilmann 2022, DOI 10.1029/2022GL098344; full author text](https://arxiv.org/html/2203.08622v1) | Learns probabilistic magnitude from partial source-time functions/waveforms and discusses Gaussian-like resolved structure plus a declining tail for possible later rupture. A latent continuation mixture or skewed high tail alone is insufficient novelty. |
| [Longobardi, Colombelli & Zollo 2025, DOI 10.1038/s43247-025-02814-z; publisher-indexed full text](https://www.nature.com/articles/s43247-025-02814-z) | Reports magnitude-dependent initial displacement growth, using a slope endpoint derived from the later LPDT plateau/curvature. This motivates testing growth, but its hindsight-defined measurement window cannot enter a fixed 1 s predictor. Their azimuth/distance aggregation also differs from one arbitrary local station. |
| [Li, Taflanidis & Brewick 2023, DOI 10.1016/j.soildyn.2023.108198; publisher-indexed abstract/sections](https://www.sciencedirect.com/science/article/abs/pii/S0267726123004438) | Hierarchical Bayesian station-specific nonlinear moment-magnitude models share regional information. Learned station distributions or hierarchical magnitude calibration are already present. Full publisher retrieval was intermittent; no unverified implementation detail is assumed. |
| [Spallarossa et al. 2019, DOI 10.1093/gji/ggy470; full publisher text](https://academic.oup.com/gji/article/216/2/919/5173041) | Early-P displacement/energy to PGV models include site random effects, with independent-event and newly installed-station applications. Non-ergodic/site-aware EEW is established, including in Italy. This concerns shaking prediction, not exactly our magnitude target. |
| [Lior & Ziv 2020, DOI 10.1785/0120190140; author summary](https://openscholar.huji.ac.il/itzhak.lior/publications/generic-source-parameter-determination-and-ground-motion-prediction), [author paper](https://www.tau.ac.il/~zivalon/papers/lior_ziv_2020.pdf) | Uses displacement/velocity/acceleration RMS to estimate moment and stress drop under an omega-squared source model, with a physical inconsistency measure. Joint source-state estimation and physically meaningful RMS ratios are not new. Paper text was available through primary-source indexing. |
| [Saoulis et al., full-waveform source inversion, arXiv 2410.23238](https://arxiv.org/html/2410.23238) | Neural density inference handles realistic noise and discusses marginalizing uncertain instrument/earth-model parameters. It is not a fixed 1/3/5 s EEW study, but rules out broad novelty claims for neural nuisance marginalization in seismology. |
| [Alsing & Wandelt 2019, nuisance-hardened inference](https://arxiv.org/abs/1903.01473) | Latent nuisance marginalization and locally nuisance-insensitive compression are established general inference tools. Their information-retention conditions must not be interpreted as invariance to an arbitrary gain confounded with magnitude. |

A relevant new failure case is [EPIC in Alaska, DOI 10.1785/0120260139](https://doi.org/10.1785/0120260139): its fixed 8 km depth can underestimate magnitudes of deep events near stations. The public replay suite contains 530 M4.5–8.2 events, with raw waveforms and gain/unit metadata. This motivates a geometry-stratified test; its initial-alert results are not fixed single-station 1/3/5 s results. [Williamson, Lux & Allen, DOI 10.1785/0220240453](https://rallen.berkeley.edu/pub/2025WilliamsonLux/WilliamsonLuxAllen-EPICmag-SRL-2025.pdf) is another necessary operational amplitude-scaling comparator.

The debate over early determinism is not settled by selecting one paper: [Zeng et
al. 2025, STF-MgNet, DOI 10.1029/2025JH000801](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2025JH000801)
reports early discrimination using inverted STFs, whereas the above probabilistic
studies emphasize unresolved rupture. Inverted-STF inputs and rupture-percentage
analysis do not establish equivalent information in a local fixed-time prefix.

Additional close search lead, not used for unverified method details: Sharma et
al. 2024, *Earthquake Magnitude Estimation through Mixed-Effects Ground-Motion
Modeling of Early P-Wave Arrivals*, DOI 10.1785/0220240183. The paper-text mirror and
indexed abstract describe 1/2/3 s displacement/site corrections; direct publisher
access failed during this search. No claim of “first site-aware early magnitude”
should be made without comparing this work.

## Preliminary identifiability and equivalence checks

Let one physical log amplitude satisfy `a = alpha*M + b + epsilon`. If the offset
b is unconstrained, `(M,b)` and `(M+d,b-alpha*d)` generate the same observation.
An arbitrary learned latent offset cannot be called identified geometry or site
response. TRAIN magnitude labels anchor a regression, but do not uniquely assign
unobserved residuals to stress drop, radiation, site response or attenuation.

Making a predictor invariant to *all* amplitude gains would remove the alpha*M
signal as well. The legitimate instrumental symmetry is joint scaling of counts
and gain by the same factor, leaving physical motion unchanged. Changing physical
motion alone is a different intervention. A temporal difference removes a static
offset, but also removes any magnitude contribution constant across those times.
Keep the common amplitude and its uncertainty; do not replace everything by ratios.

If `b ~ N(mu_b,tau^2)` and `epsilon ~ N(0,sigma^2)`, marginalization gives exactly
`a|M ~ N(alpha*M+mu_b,sigma^2+tau^2)`. With free means/variances, this is an ordinary
heteroscedastic Gaussian; with discrete latent classes it is a mixture density.
For a 3-time vector with the **same** b, covariance is

`Sigma = sigma^2 I + tau^2 11'`,

not `(sigma^2+tau^2)I`. The first form preserves a common uncertainty that more
windows cannot average away. In the linear case, magnitude information is
`alpha^2 J/(sigma^2+J*tau^2)`, saturating as J increases. Re-marginalizing a fresh
independent offset at each update incorrectly supplies unlimited new information.

Finally, if `p(a|M,z,c)` is constant in M above a saturation threshold, posterior
odds between any two such magnitudes are exactly their prior odds conditional on
z,c. A high-tail point improvement in that region must come from other measured
features, a more useful prior, or decision changes—not the saturated amplitude.

## Proposal 1: geometry-anchored amplitude likelihood

**Specific hypothesis:** a calibrated distribution over geometry, kept coupled to
magnitude while applying an amplitude likelihood, can correct deep/far-event bias
better than a point geometry correction or a free variance head. This can improve
the first second because it does not wait for the next window; its benefit comes
from using whatever distance/depth information already exists in waveform shape
and preserving uncertainty about what remains unresolved.

Let `a_t` be one log physical-amplitude summary, `z_t` the normalized waveform
shape through deadline t, c predeployment instrument/site information, and
`eta=(log R, depth, ...)` a small explicitly defined geometry state. R/depth are
catalogue **TRAIN supervision only**. Deployed inference receives `(a_t,z_t,c)`.
Use the valid conditional joint model

`p_theta(M,eta,a_t | z_t,c) = q_theta(M,eta | z_t,c) L_theta(a_t | M,eta,z_t,c)`.

The magnitude posterior is

`p_theta(M | a_t,z_t,c) = integral q_theta(M,eta|z_t,c)L_theta(a_t|M,eta,z_t,c)deta / Z(a_t,z_t,c)`.

Crucially, this is an integral of the **joint** conditional prior and likelihood.
Multiplying a marginal magnitude PDF by a likelihood averaged under an unrelated
`q(eta|z,c)` silently assumes conditional independence. If one instead averages
already-normalized posteriors over eta, the mixing weights must be the updated
`p(eta|a,z,c)`, not the pre-amplitude eta weights.

A bounded initial likelihood is a physical log-amplitude location/scale model,

`L = Normal(a_t; g_t(M,eta) + b_phi(c), sigma_t(eta,c)^2)`.

`g_t` may use the established distance-attenuation and finite-window saturation
forms, calibrated on TRAIN. A free neural `g_t(M,eta,z,c)` would make a powerful
generic classifier but destroy most of the intended physical test. Start with a
small prespecified physical/empirical family and an explicit model-discrepancy
scale. Distinguish scalar sensitivity from full transfer-function removal and
velocity from acceleration. Using displacement laws on mixed native counts is not
the proposed experiment. Where a target is ML rather than Mw, do not impose a
moment/stress-drop scaling coefficient without a separate label model.

For examples with observed TRAIN eta, fit the full conditional joint score

`-log q_theta(M_i,eta_i|z_i,c_i) - log L_theta(a_i|M_i,eta_i,z_i,c_i)`.

Use missing-eta marginalization where needed. Do not supervise an “instrument
uncertainty” latent using final magnitude alone and then claim physical recovery.
Magnitude-specific source residuals and station calibration need constraints or
repeated observations; condition-independent uncertainty cannot all be assigned
to geometry. To add a discriminative magnitude-NLL term would be a composite
score/optimization choice, not a new probabilistic identity, and requires its own
matched ablation. A continuous distribution with an explicitly evaluated tail is
needed for extrapolation; the existing 66-bin support cannot demonstrate M>6.6.

**What could distinguish the implementation:** independently verified geometry
supervision, physical unit handling, preserved M–geometry dependence, and a
measurable correction of a specified depth bias with identical early inputs. This
is a constrained neural extension of known joint Bayesian inference. If its effect
is replicated by an equally expressive ordinary mixture head or a standard
geometry auxiliary task, do not claim an inference-method contribution.

**Decisive controls, all fixed before evaluation:**

- Same waveform/metadata inputs and capacity: direct continuous magnitude density;
  magnitude plus ordinary distance/depth auxiliary supervision; proposed joint
  posterior; and proposed model with geometry collapsed to its mean.
- Freeze amplitude/path calibration from TRAIN; compare free heteroscedastic
  variance with the geometry-induced mixture. Removing geometry labels or
  shuffling them **within magnitude/station strata** tests whether physical
  anchoring matters rather than merely additional parameters or magnitude priors.
- Oracle catalogue geometry is a labelled diagnostic upper bound, never an
  operational score. If oracle geometry does not improve the relevant subgroup,
  this hypothesis has little headroom. Poor eta calibration that worsens tail
  risk defeats the proposed practical advantage even if oracle geometry helps.
- Report deep/shallow and near/far events, seen/unseen stations, event-macro error,
  all three deadlines, proper distribution scores and tail false alarms. Match
  P-pick conventions and actual availability; do not compare to EPIC aggregate
  first-alert numbers as if they were the same benchmark.
- A saturated likelihood must preserve within-unresolved-tail prior odds in a
  synthetic test. Any claimed extra amplitude information there is a bug or a
  violation of the model assumptions.

## Proposal 2: prospective growth/turnover likelihood with persistent nuisance

**Specific hypothesis:** observable within-prefix curvature, modeled jointly with
the absolute level and a persistent station/path uncertainty, contains useful
magnitude information beyond a peak, slope feature, or free CDF head. The model
must fail gracefully when all candidate magnitudes have the same early growth.

Use fixed disjoint short time blocks within 0–1, 1–3 and 3–5 s. Let `a_j` be a
physical log RMS envelope summary for block j; evaluate its prediction by averaging
the hypothesized envelope over the **same** block. This is a local measured
envelope model, not a claim that RMS equals source moment rate. A real-valued
Gaussian on log block amplitudes is at least a coherent approximate observation
family; a Gaussian on an unconstrained *running-maximum* sequence would allocate
probability to impossible decreasing paths. If floor-censoring is applied to RMS,
score its censoring probability instead of pretending the floor value is exact.

A small testable latent family is

`mu(t;M,T,q,b) = b + beta*(M-Mref) + q*log10(t/T) - (q/r)*log10(1+(t/T)^r)`,

with r fixed, q positive, and a TRAIN-fitted distribution over log T and q. T is a
**local-envelope turnover scale**, not an observed plateau or established rupture
end. Let `b ~ Normal(b_phi(c),tau_phi(c)^2)` and block residual covariance K have a
small prespecified temporal structure. Marginalizing b gives

`L_t(M) = integral Normal(a_<=t; mu_<=t(M,T,q,b_phi(c)), K_<=t + tau_phi(c)^2 11') p(T,q|M,c) dT dq`.

This is a constrained mixture likelihood, not novel latent-variable mathematics.
The relevant modification relative to scalar saturation is **prospective
fixed-block shape evidence plus an explicitly shared nuisance covariance**, tested
against a null where early shape cannot distinguish final magnitudes. A free
unconstrained mixture over all these quantities is unlikely to be identifiable.
Use a small quadrature grid or similarly bounded integration before considering
a larger neural inference network.

Sequential inference must retain the joint state `(M,T,q,b)` or use the matching
conditional block likelihood obtained from the same joint model:

`p_t(M,T,q,b) proportional p_previous(M,T,q,b) * p(a_new | a_previous,M,T,q,b)`.

If one keeps only the magnitude PDF and resets T,q,b to their initial priors at
each deadline, the update is generally wrong. Multiplying full-prefix likelihoods
at 1, 3 and 5 s counts old blocks more than once. The marginal conditional can be
written as `L(a_<=t|M)/L(a_<=previous|M)` only when both use the same projectively
consistent joint model and prior. Do not re-fit a different latent prior per time
and then call that ratio a valid Bayes innovation.

**First-second benefit and the essential null:** fix `log10 T = k + gamma*(M-Mref)+eta`.
For t much smaller than T, the mean reduces to

`b + (beta-q*gamma)*(M-Mref) - q*(k+eta) + q*log10(t)`.

Thus for beta=1, gamma=1/2 and q=2, the M term cancels exactly in the early-power
limit. This is the same confounding exposed by a constant-stress-drop quadratic
source-growth example, not a theorem that real ruptures universally obey it.
Arbitrary source/path offset uncertainty compounds the problem. At 1 s, the model
can help only if turnover is already partly observed, growth shape varies with
magnitude after nuisance control, or better calibration of the absolute level
is useful. It cannot gain information merely by attaching the name “rupture
state” to q or T. Allowing q to depend on M is an explicit empirical alternative
to test, not a physical truth to impose because it improves the existing VAL.

Longobardi's eventual-plateau endpoint may be a TRAIN descriptive target, but it
must never select the online slope window. Using a predictor of that endpoint is
still uncertain; integrating its distribution matters, and plain future-target
distillation is already known. This proposal can instead fit the observed block
likelihood directly, using only available blocks at each inference deadline.
P-pick jitter, S arrivals, response-filter transients and dispersive path effects
can all mimic curvature. A scalar b does not absorb those effects. Full response
forward modeling or carefully restricted sensor/unit groups are necessary before
interpreting a successful local-envelope fit as source physics.

**Decisive controls:**

- Common inputs: scalar amplitude + static metadata; the same inputs plus simple
  fixed-time slope/curvature features; a generic small mixture density; universal
  growth model; and magnitude-dependent q/T model. Match training data, objective,
  capacity as closely as possible and report unavoidable capacity differences.
- Preserve b across all blocks versus the deliberately wrong independent-b-per-
  block control. The latter may improve apparent point fits but should become
  overconfident under a shared-offset simulation.
- Apply a joint digital count/gain rescaling, fixed-prefix future replacement and
  explicit onset jitter. The first should preserve physical features; the second
  must leave the deadline output unchanged; jitter sensitivity must be measured.
- Synthetic universal growth gives identical early likelihoods for unresolved M;
  synthetic magnitude-dependent growth provides a positive recoverability control.
  Randomly shuffling q–M association while preserving amplitudes/nuisance gives a
  stronger null than merely dropping the new branch.
- The narrow scientific claim fails if inferred q/T mainly tracks station family,
  depth or pick quality, if a simple prefix-feature baseline matches its gains,
  or if any advantage vanishes on untouched station/event/region partitions.
  Better future-growth likelihood alone is insufficient: require better magnitude
  risk/calibration with prespecified bulk-error tolerances and all seeds reported.

## Inline numerical checks (not earthquake experiments)

Executed in JavaScript without writing code or using AWS:

1. Numerically integrated `N(a;mu+b,sigma^2)N(b;0,tau^2)` on b∈[-6,6], step .002,
   for a=1.3, mu=.8, sigma=.35, tau=.6. Integral .44325116238552864; analytic
   combined-variance density .44325116238552875; absolute difference 1.11e-16.
   This verifies the simple nuisance head's exact equivalence to variance addition.
2. For three observations with tau²=.25 and sigma²=.04, correct variance of their
   mean is .2633333. Re-sampling b independently per time gives .0966667, making
   the nominal precision 2.724 times too large. The example tests dependence, not
   a measured error inflation in this earthquake dataset.
3. With beta=1, q=r=2, gamma=.5, Mref=4, k=eta=b=0, early power-law log amplitudes
   for M7 and M9 agree within 4.44e-16 at 1/3/5 s. The smooth-turnover toy leaves
   M9−M7 log-amplitude differences only .0004297/.0038521/.0106153. At 1 s its
   derivative with respect to M is .000999 at M7 and .0000099999 at M9. This toy's
   time scale is deliberately illustrative, not calibrated to real earthquakes;
   the exact cancellation and weak-information mechanism are the relevant checks.

## What would justify proceeding

First verify causal physical preprocessing and magnitude-label meaning on a
TRAIN-only subset with actual nuisance supervision. Current INSTANCE results
include mixed ML/Mw/Md, released whole-record detrending/resampling, and reused VAL
with only 13 M≥4 events and no M≥6. The audited static-feature improvement is
real within that exploratory protocol but does not establish high-M extrapolation.
Current counts/site controls and the independent affine-prefix benchmark remain
essential comparisons.

The geometry candidate has a concrete external failure case and should be treated
as a disciplined baseline extension. The turnover candidate has a potentially
interesting scientific contrast, but the smallest first task is a held-event
likelihood/identifiability audit at fixed 1/3/5 s, with universal-growth and
pick-jitter controls. Do not deploy a flexible latent model and retrospectively
name its latent coordinates “stress drop” or “rupture continuation.” A defensible
new contribution would require a specific observable constraint, a demonstrable
benefit beyond these known models, and honest limits—not merely the absence of
an exact formula in this search.

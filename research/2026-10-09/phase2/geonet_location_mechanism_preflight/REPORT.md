# Inferred-location integration: data-free mechanism preflight

**The prespecified arrival-only mixture fails the synthetic mechanism gate; no geometry fit is justified by this preflight.** This result concerns one fixed invented observation law, not a universal impossibility for nonlinear learned timing fusion. Ordinary current-arrival information remains a legitimate baseline input when independently justified by the data design. Neither this experiment nor its primary sources establishes novelty or a matched published-score improvement.

The [fixed protocol](PROTOCOL.md) was written before calculation. Two seeds each generated 4,096 events, with 202/187 events at M≥5.5 and 191/178 at M≥6. Seven exact analytic arms were evaluated at three snapshots in a base law and a fixed locator stress: 12 panels, retaining both mean and median point decisions, proper scores and all negative results. The snapshots use prescribed one/two/three-station availability, not a GeoNet picker or delivery simulation. There is no learned training, real catalogue input or architecture sweep. Full aggregates are in [CALCULATIONS.json](CALCULATIONS.json).

## What integration can identify

Let l(g) be the vector of log10 station distances from one source, a the available log-amplitudes and T the available relative arrivals. Under the invented law a=M1−αl(g)+η, η~N(0,Σ), and M~N(µ0,v0), define v=(1/v0+1ᵀΣ⁻¹1)⁻¹. The conditional mean is

`µ(g,a)=v(µ0/v0+1ᵀΣ⁻¹a)+αv1ᵀΣ⁻¹l(g)`.

For **any common fixed geometry weights for this observation**, its integrated mean equals the same conditional mean evaluated at E[l]. This algebra does not require independent station distances, and it also holds for waveform-conditioned weights when both controls use those same weights. It does not hold if an arm gets different geometry information or coefficients. The fixed calculations verify the identity to 7.99e−15. Averaging distance R or coordinates g before taking logs is a different, confounded plug-in.

The predictive variance includes `bᵀCov(l)b`, where b=αvΣ⁻¹1. Our two-state shared source gives a rank-one covariance, with variance of average log distance 0.209065; independent station draws give 0.070209, almost threefold smaller. Six of eight three-station independent state combinations cannot arise from either actual toy source. The direction of this variance error depends on covariance signs; shrinking uncertainty is specific to the positive correlations here. The independent-distance diagnostic improves some tail point scores while worsening bulk/CVaR/proper scores, so a favorable tail alone would not validate a common-source mechanism.

With a nonlinear conditional mean, `E[f(l)]` can differ from `f(E[l])`: for f(l)=4+l², equal l=1/2 weights give 6.5 versus 6.25. With correctly conditioned weights and head, the integrated mean is the conditional expectation and minimizes squared risk; a plug-in's excess conditional squared risk is its squared distance from that expectation. This does **not** guarantee magnitude-tail MAE or CVaR gains. A mixture can also change multimodality, median, NLL, CRPS and tail probabilities while leaving its mean unchanged. The moment-matched Gaussian control has exactly identical primary mean errors in every panel, illustrating that distribution shape alone is not the requested point-error result.

A direct flexible density using the same observations can represent the identical exact posterior. Integration creates no information advantage over that oracle. A learned gain against finite direct heads would concern inductive bias, estimation or optimization. TRAIN-only catalogue geometry gives auxiliary information to learning; it must be shared across direct/point/integrated controls rather than credited to marginalization. An arbitrary learned conditional head can ignore g entirely, so normalized integration or a good NLL does not prove its components are physically conditional source models.

## Arrival-only weights are an approximation

The shortlist has `q(g|T) q(M|a,g)`. Correct joint conditioning instead uses

`p(g|a,T) ∝ p(g|T) p(a|g,T)`

before integrating `p(M|a,g,T)`. Omitting that waveform evidence changes geometry weights when amplitudes inform location. Our exact-joint and arrival-only arms share the same conditional head, priors, covariance and observations, so this comparison isolates the weighting approximation without labels or capacity differences. ElogR comparisons separately use timing-only or exact-joint weights as labelled; they are not interchangeable.

For one P report with unknown origin time there is no relative-arrival measurement. An amplitude alias M=5 at R=10 and M=7 at R=100 yields the same a=3 under α=2. No universal point decision can have absolute error below one for both indistinguishable sources. A 0.99/0.01 near/far posterior gives mean 5.02 and far-source error 1.98 even with full magnitude support. This is an identifiability counterexample, not a claim that real waveform shape never carries additional location/source information. A TRAIN geographical prior can choose an alternative; it cannot create timing evidence, and a rare unfamiliar large source can defeat it.

## Exact gate and retained failed comparisons

The fixed mean-decision gate versus **timing ElogR plug-in** requires both tail gains ≥0.02 at every snapshot/seed, MAE/MedAE increases ≤0.005 and CVaR95 increase ≤0.02. Tail gain is comparator error minus candidate error; other changes are candidate minus comparator. These invented-problem tolerances were fixed before results. No result selected a revised law, gate, prior, repair or blend.

| Seed | Regime | Snapshot | Tail ≥5.5 gain | Tail ≥6 gain | MAE change | MedAE change | CVaR95 change | Pass |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 20261011 | base | 1 | -0.079706 | -0.098700 | +0.159693 | +0.158825 | +0.009559 | False |
| 20261011 | base | 3 | -0.038283 | -0.043762 | +0.053420 | +0.049513 | +0.061574 | False |
| 20261011 | base | 5 | +0.000034 | -0.000137 | +0.000664 | +0.000121 | +0.008890 | False |
| 20261011 | locator_stress | 1 | -0.001071 | -0.000823 | +0.000597 | +0.001000 | -0.002804 | False |
| 20261011 | locator_stress | 3 | -0.002704 | -0.002865 | +0.005676 | +0.001984 | -0.002555 | False |
| 20261011 | locator_stress | 5 | -0.000653 | -0.000691 | +0.000129 | +0.000000 | +0.002100 | False |
| 20261012 | base | 1 | -0.021027 | -0.035791 | +0.161493 | +0.153379 | +0.011185 | False |
| 20261012 | base | 3 | -0.029284 | -0.029970 | +0.051688 | +0.050587 | +0.059685 | False |
| 20261012 | base | 5 | -0.000520 | -0.000546 | +0.001151 | -0.000073 | +0.018576 | False |
| 20261012 | locator_stress | 1 | +0.000470 | +0.000413 | +0.001098 | +0.007424 | -0.002922 | False |
| 20261012 | locator_stress | 3 | -0.005559 | -0.005890 | +0.005020 | +0.000621 | -0.000250 | False |
| 20261012 | locator_stress | 5 | -0.000000 | -0.000000 | +0.000069 | +0.000000 | +0.001062 | False |

Arrival-only fails all six base and all six stress panels. At the first snapshot it often improves NLL substantially while making bulk and tail errors worse. At five seconds its proper-score gain has almost no tail point benefit. The expected ElogR mean equivalence is exact for the single-Gaussian null; the observed nonlinear-prior failure here is empirical for this chosen law.

The exact-joint diagnostic improves bulk/CVaR strongly but fails the all-duration tail gate; its base comparisons are:

| Seed | Snapshot | Tail ≥5.5 gain | Tail ≥6 gain | MAE change | CVaR95 change | Max-error change | Pass |
|---|---:|---:|---:|---:|---:|---:|---|
| 20261011 | 1 | -0.145872 | -0.153592 | -0.298742 | -0.193095 | +0.483012 | False |
| 20261011 | 3 | +0.011629 | +0.038997 | -0.303928 | -0.578589 | +0.021361 | False |
| 20261011 | 5 | +0.002573 | +0.005863 | -0.008246 | -0.108010 | -0.349134 | False |
| 20261012 | 1 | -0.066244 | -0.069885 | -0.313725 | -0.287308 | +0.581650 | False |
| 20261012 | 3 | +0.081989 | +0.110124 | -0.308920 | -0.656829 | -0.043035 | True |
| 20261012 | 5 | -0.000226 | -0.000132 | -0.012498 | -0.175171 | -0.314850 | False |

Only one base joint panel passes its full guard. Its one-report tail MAE and maximum error exceed ElogR despite much better bulk error and NLL. That is the rare-source/prior tradeoff under a correctly specified density, not a failure to normalize a distribution. In the fixed prior/timing stress, five-second tail error remains about 0.95–1.02; the favorable well-specified five-second tail result near 0.16 does not survive. The stress is deliberately adversarial and says nothing about its frequency in GeoNet.

## Small independently recomputable cases and numeric limits

[ANALYTIC_CASES.json](ANALYTIC_CASES.json) provides three explicit invented amplitude/geometry/conditional-mixture cases, all priors, covariance, component means/variances/weights, point errors and independently integrated posterior means. The one-report a=2.8 case gives arrival/joint/ElogR means 5.539856/4.912802/6.095195; the two-report ambiguous case gives 5.687107/5.757945/6.002332. These illustrations were added after the fixed experiment and do not change its gate. Scalar quadrature errors are below 3.56e−15 in these cases and below 7.11e−15 in six fixed generated checks. Gaussian weights normalize within 2e−12; no density floor is used. CRPS uses `sum w_i B(y−µ_i,σ_i) − 0.5 sum w_i w_j B(µ_i−µ_j,sqrt(v_i+v_j))`, with B(d,s)=d(2Φ(d/s)−1)+2sφ(d/s).

The original calculation emitted divide-by-zero/overflow/invalid warnings at the mean-location NumPy matrix multiply. All saved aggregates are finite. An independent explicit weighted-broadcast calculation matches that multiply within 1.43e−14 in all twelve panels; the matrix warning recurs, while the broadcast is finite. [WARNING_CHECK.json](WARNING_CHECK.json) retains this check. The runtime-warning cause is undiagnosed; the original run is not described as warning-free. No metric or original output was replaced.

Runtime: Python3.10.20, NumPy2.2.6, SciPy1.15.3. Per seed, default_rng draws in order: 4,096 uniform component choices, 4,096 normal magnitudes, 4,096 uniform source choices, 4,096×3 pick normals, 4,096 shared-amplitude normals, then 4,096×3 amplitude normals. Base/stress and all arms share these draws. Median uses 52 CDF bisections; P95 is NumPy's default quantile and CVaR95 averages the largest ceil(0.05N)=205 errors. No persistent Python source was created: equations, settings, aggregate results and validation are retained, while exact implementation replay would require a separately reviewed implementation.

## Primary overlap and next decision

Virtual Seismologist already treats joint magnitude/location uncertainty and explicitly discusses the one-station magnitude–distance ambiguity, geometry priors and the rare-event/false-alarm tradeoff. Generic source marginalization is not new. [Author chapter](https://www.its.caltech.edu/~heatont/papers/VSmethod_cua_heaton%20%282%29.pdf).

Zollo et al. already combine differential arrival times with amplitude ratios and backazimuth for evolving probabilistic location. That is closer to waveform-informed geometry than a timing-only locator. [Primary paper](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020JB020359).

TEAM-LM already fuses variable-station waveforms and coordinates with explicit amplitude preservation; a geometry branch must beat that strong same-information direct model. Its paper also examines multitask source estimation. [Primary preprint](https://arxiv.org/pdf/2101.02010).

Yu et al.'s March2026 v2 uses a neural travel-time surrogate, Student-t scale mixtures and explicit phase contamination for robust catalogue location. Robustifying a locator is established prior art, not an EEW magnitude-tail result or a repair demonstrated here. [Versioned primary preprint](https://arxiv.org/html/2512.06407v2).

**Status: prespecified synthetic mechanism gate failed; zero geometry fits earned.** This does not prohibit the independently justified ordinary current-arrival baseline control. If later data establish timing utility, a further coupling test must share geometry supervision, out-of-fold predictions, full location summaries/ElogR, magnitude support, capacity and updates. It must beat direct and point controls on independently held events while preserving the project guard. Correlated source sampling, robust timing likelihood or proper-score gains alone do not earn that claim.

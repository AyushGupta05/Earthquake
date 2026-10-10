# Chile continuous prior and resampling audit

10 October 2026. **Decision: do not launch another prior-correction fit from this audit.** The exact source sampling law is recoverable, but the current trained density is neither an unsmoothed natural posterior nor an exact resampled posterior. Dividing it by a smooth exponential or the source repeat factor has no established high-magnitude benefit. Normalized prior adjustment for continuous regression is established prior art.

This is a source and mathematical audit. No checkpoint, model forward, real metadata row, waveform, prediction array, calibration output, or fit was accessed. The completed INSTANCE result dossier was read only for its existing aggregate conclusion. The frozen Chile clock-control protocol remains unchanged.

## Exact source behavior

The author source is pinned to commit `8df20877f3a6ef47d3af4d1484ecdb0cdf37e903`. Relevant files are `util.py`, `train.py`, `models.py`, and `magloc_configs/chile_mag_noloc.json`. The checked port is pinned by the source hashes in `manifest.json`.

`util.py:145–150` starts with one occurrence per event, then adds `2**(i-1)-1` occurrences for `i < M <= i+1`, with `i=4,5,6,7,8` in the Chile magnitude configuration. The resulting exposure function is:

| Original label M | Presentations a(M) |
| --- | ---: |
| M ≤ 4 | 1 |
| 4 < M ≤ 5 | 8 |
| 5 < M ≤ 6 | 16 |
| 6 < M ≤ 7 | 32 |
| 7 < M ≤ 8 | 64 |
| 8 < M ≤ 9 | 128 |
| M > 9 | 1 |

The last row is a literal consequence of the source loop ending at 8, not a scientifically justified extrapolation. At M=4 the factor is 1, at M=5 it is 8, and immediately above M=5 it is 16. **This is not `2**(M-4)`**, and substituting that smooth law would change the experiment. The port's `resampling_indices` (`train_team_lm.py:245–253`) matches these right-closed boundaries. Source event batches retain the remainder (`util.py:182–189`). No event counts were examined here.

Training labels are subsequently changed to

`Y = M + s(M) Z`, where `Z ~ N(0,1)` and `s(M) = 0.05 max(M-4,0)`.

This is source `util.py:279–281` and port `smooth_training_magnitudes` at `train_team_lm.py:371–375`. Repetition depends on **original M**, not on the realized noisy Y. The source magnitude-only event training enables smoothing (`train.py:327–337`). This is synthetic training augmentation, not evidence that the reported MA label uncertainty is independent Gaussian measurement noise.

There is also an existing validation difference. Source `train.py:339–350` changes the event generator's `oversample` to 4 but keeps `magnitude_resampling=2`; it does not enable validation label smoothing. Thus source validation repeats each event `4 a(M)` times, with random cutoffs and station blinding. The constant 4 does not change the ideal conditional distribution, while `a(M)` changes its weighting. In the port, only TRAIN-fit is repeated (`train_team_lm.py:658–664`), and `evaluate` (`299–331`) requires unique event IDs, uses original labels at 1/3/5 seconds, and reports normalized density scores. Port TRAIN-calibration selection is therefore a deliberate departure from source validation selection. This audit does not restore source validation or alter either matched clock arm.

Primary source links: [author resampling and smoothing](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/util.py), [author event training and validation](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/train.py), [Chile configuration](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/magloc_configs/chile_mag_noloc.json), and [author density loss](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/models.py).

## What distribution would a proper density learner target?

These are population identities, not claims about a finite neural network. Let X be the evidence after the *same specified* waveform, clock, and station augmentations. Let `p(m|x)` denote the natural reference population's conditional distribution under those augmentations. Define `A(x)=∫ a(m)p(m|x) dm`. Sampling the repeat stream then gives

`p_a(m|x) = a(m)p(m|x) / A(x)`.

This identity requires selection depending only on original M as specified; it does not account for arbitrary missing stations, region shifts, catalogue selection, or a different target population. With unchanged labels, an unrestricted density learner using the proper log score would target `p_a`. Only in that ideal case does

`p(m|x) = [q(m|x)/a(m)] / ∫ [q(u|x)/a(u)] du`

exactly undo exposure. The exposure factor is distinct from the natural marginal prior: `p_a(m) ∝ a(m)p(m)`. Dividing by `a(m)` returns the natural population; dividing by `p_a(m)` instead targets a flat-label reference under additional label-shift assumptions. Those are different desired posteriors.

With source label noise, define the Markov kernel `K(y|m)` as a point mass at m for m≤4 and a Gaussian of mean m and standard deviation `s(m)` for m>4. The proper-score target becomes

`r_a(y|x) = [∫ a(m)p(m|x) K(y|m) dm] / A(x)`.

It is generally **not** `a(y) ∫ p(m|x)K(y|m) dm / A(x)`. Multiplication by a and the noise kernel do not commute. The difference of their unnormalized forms is

`∫ [a(m)-a(y)] p(m|x) K(y|m) dm`.

Consequently `r_a(y|x)/a(y)` neither recovers the original-label posterior nor generally the naturally smoothed posterior. A posterior-only inverse adjustment cannot identify how noisy target mass came from different original labels without further assumptions. A heteroscedastic inverse problem would be needed for latent-label recovery; no such inverse is implemented or justified here.

An invented counterexample isolates the boundary: every true M=5, so exposure is the constant 8, and the smoothed label is `N(5,0.05²)`. Its natural and resampled noisy distributions are identical. Dividing by `a(Y)` nevertheless weights labels immediately below 5 twice as much as labels immediately above 5. Ignoring less than approximately `6e-89` total probability beyond ±20 standard deviations, the adjusted lower-half probability is 2/3, upper-half probability 1/3, and the adjusted mean is `5 − 0.05 sqrt(2/pi)/3 = 4.986701923986619`. This distortion is produced by the correction itself. It is not an observed Chile error.

## The density floor prevents the exact proper-score identity

Author `models.py:497–515` sums the normalized Gaussian components, adds `epsilon=1e-6`, and takes minus the log. Port `team_lm.py:336–347` reproduces this through `logaddexp`. The added constant is a density floor; over the real line `q+epsilon` is not a normalized probability density.

For an unrestricted density q and a continuous target density r, minimizing `−∫ r(y) log(q(y)+epsilon) dy` under `q≥0` and `∫q=1` yields the KKT condition

`q*(y) = max(r(y)/lambda − epsilon, 0)`

with lambda chosen to normalize q, under the usual existence/regularity conditions. Where r is sufficiently small, the optimum can allocate zero density. For epsilon=0 this reduces to q*=r. For positive epsilon, q=r is not generally the optimum. A five-component neural Gaussian mixture has a constrained parameter space and positive tails, so this unrestricted solution is a counterexample to strict propriety, **not** a characterization of the actual trained checkpoint.

The invented four unit-width-bin witness in `synthetic_arithmetic.json` uses target density `(0.4999995,0.4999995,0.0000005,0.0000005)` and the actual numerical epsilon `1e-6`. The candidate `(0.5,0.5,0,0)` has a smaller expected floored score by `5.945323919842593e-7`. This establishes the mathematical limitation without reading predictions. It does not estimate the floor's practical magnitude in Chile. The completed TRAIN-only floor diagnostic is separate evidence and is not reinterpreted by this audit.

Thus even without noise, a finite-capacity model trained using the source floor cannot be assumed to satisfy `q ∝ a p`. Both factors must be stated when proposing an exposure correction. Removing the floor would be a separate controlled experiment, not an unreported adjustment to the frozen clock comparison.

## Exact Gaussian integrals available in the unsmoothed ideal case

For any normalized mixture `q(m)=Σ_k pi_k N(m;mu_k,sigma_k²)`, use intervals `I_j=(l_j,u_j]` with boundaries `(-inf,4,5,6,7,8,9,inf)` and the factors in the source table. For any piecewise constant weights `c_j`, let

`D_kj = Phi((u_j-mu_k)/sigma_k) − Phi((l_j-mu_k)/sigma_k)`.

Then the normalizer and unnormalized first moment are exactly

`Z_c = Σ_k pi_k Σ_j c_j D_kj`,

`B_c = Σ_k pi_k Σ_j c_j [mu_k D_kj + sigma_k {phi((l_j-mu_k)/sigma_k) − phi((u_j-mu_k)/sigma_k)}]`.

The normalized mean is `B_c/Z_c`. Forward exposure uses `c_j=a_j`; inverse exposure uses `c_j=1/a_j`. A CDF follows by replacing the upper bound in each interval by `min(u_j,y)` and omitting intervals with y≤l_j. This gives a **mixture of truncated interval pieces**, not a new five-component untruncated Gaussian mixture. Tail probabilities and quantiles require this piecewise CDF, with appropriate numerical tail handling.

One possible forward exposure-aware likelihood for an unsmoothed natural density model p_theta is `r_theta(m|x)=a(m)p_theta(m|x)/Z_a(x)`. Its proper NLL is `−log p_theta(m|x) − log a(m) + log Z_a(x)`. The normalizer depends on theta and cannot be omitted from training. Such a normalization is an application of known prior-adjusted regression likelihoods.

Under the source noise process the corresponding exact forward likelihood would instead be

`r_theta(y|x) = [∫ a(m)p_theta(m|x)K(y|m) dm] / Z_a(x)`.

The denominator still has the piecewise Gaussian formula. The numerator is not the usual product of fixed-variance Gaussians because `K` has variance `0.0025(m-4)²` above 4, plus its point-mass branch. There is no justified finite Gaussian-product/CDF shortcut here. A claimed analytic training loss must handle that numerator, or explicitly switch to unsmoothed labels in a new protocol. Smooth exponential tilting formulas likewise do not apply to the actual integer repeat law.

The invented mixture `(pi,mu,sigma)=((.3,.7),(3.8,5.1),(.2,.35))` gives native mean 4.71, forward exposure mean 5.109405880529888, and inverse exposure mean 3.9882751610759843. Piecewise numerical quadrature agrees with both normalizers and both unnormalized first moments within `3.34e-13`. These are one-off scalar arithmetic checks, not a training test suite or a forecast result.

## Direction and the high-magnitude objective

On support M≤9, source a(M) is nondecreasing and `w(M)=1/a(M)` is nonincreasing. When the expectation exists,

`E_corrected[M] − E_q[M] = Cov_q(M,w(M))/E_q[w(M)] ≤ 0`.

The same ordering gives no larger upper-tail exceedance probabilities after inverse correction. Therefore inverse exposure naturally shifts predictions downward in this supported range. It may improve natural-population calibration if the ideal assumptions hold; that is not a mechanism for fixing already underestimated large earthquakes. No guarantee follows for tail MAE, median absolute error, or maximum error. The literal factor reset above 9 breaks the global monotonicity argument; Gaussian outputs are unbounded, so this exception must not be hidden by silently truncating their support.

Even a correct natural posterior's mean or median can have conditional high-M bias: the mean minimizes population squared loss and the median minimizes population absolute loss. Replacing the deployment prior by an artificially heavy tail changes the decision problem. It does not create new early-waveform information or ensure preservation of bulk metrics. An error tail and a magnitude tail also remain different evaluation objects.

## Primary prior art and what can be borrowed

**Balanced MSE, CVPR 2022.** Ren et al. assume unchanged `p(x|y)` and a specified balanced label distribution. Their Theorem 1 and equations 3.4–3.6 normalize the product of a desired posterior and the training label prior. They provide Gaussian-mixture analytic integration and Monte Carlo options. This directly precedes a proposal to add `log Z_a` to a continuous Gaussian likelihood; the original method's goal is a balanced evaluation population, while our source repeat law is a known sampling transformation of a natural population. Their benchmark does not guarantee a simultaneous tail improvement and unchanged natural MAE. The connection is conceptual prior art, not evidence of EEW superiority. [Published paper](https://openaccess.thecvf.com/content/CVPR2022/html/Ren_Balanced_MSE_for_Imbalanced_Visual_Regression_CVPR_2022_paper.html), [full author preprint with Theorem 1](https://arxiv.org/pdf/2203.16427), [author code](https://github.com/jiawei-ren/BalancedMSE).

**Deep Imbalanced Regression, ICML 2021.** Yang et al.'s LDS smooths the empirical label-frequency distribution to account for continuity; FDS smooths feature statistics across nearby target bins. LDS density smoothing for loss weights is different from injecting noisy labels into each repeated event. It does not make `a(Y)` equal to `a(M)`. The useful lesson is to treat adjacent magnitudes as related and state the target metric/distribution; a generic smoother is neither new nor automatically appropriate for MA. [Primary paper and proceedings](https://proceedings.mlr.press/v139/yang21m.html), [full paper](https://proceedings.mlr.press/v139/yang21m/yang21m.pdf).

**Variational Imbalanced Regression, NeurIPS 2023.** Wang and Wang combine representations from neighboring labels and predict normal-inverse-gamma parameters with smoothed-density importance weighting. Probabilistic reweighting and uncertainty-aware continuous regression are therefore established techniques. Adapting that entire framework would introduce representation, density-family, capacity, and training-objective changes simultaneously; this audit supplies no evidence that those changes address a demonstrated Chile mechanism or preserve bulk/worst-error performance. [Published primary paper](https://proceedings.neurips.cc/paper_files/paper/2023/hash/612a56f193d031687683445cd0001083-Abstract-Conference.html), [full paper](https://proceedings.neurips.cc/paper_files/paper/2023/file/612a56f193d031687683445cd0001083-Paper-Conference.pdf).

The primary indexed OpenReview draft *Bayesian Imbalanced Regression Debiasing* already gives bidirectional posterior/prior normalization in equation 1.1. Its full PDF fetch returned a browser verification page during this audit, and its publication status was not established. It is supplementary prior-art evidence, not a source for a benchmark or acceptance claim. [Primary draft indexed by the search tool](https://openreview.net/pdf/8d45045dbd66e3added7030750fce10e665d8780.pdf). The published Balanced MSE paper independently establishes the key normalization precedent.

## Existing result and the next-action gate

The completed INSTANCE categorical exposure grid failed all 12 frozen scientific comparisons. Its C-corrected versus natural-CE ensembles worsen M≥4 event MAE in all six panels and also worsen all three reported worst-error statistics in all six panels. This is documented in `../independent_distribution_result_audit/RESULTS.md`; this audit did not replay its artifacts. It weakens a generic exposure-correction default, but it does **not** settle the Chile continuous problem: categorical support, sampler, labels, and model family differ. Response support is 0.0–6.5; exposure support is 0.05–6.55. Neither their supports nor their sampling streams may be pooled to make a common result.

Keep the reviewed 1/3/5-second clock allocation control unchanged. For any later continuous prior experiment, require a separate frozen protocol that specifies all of:

1. The reference population and desired posterior, with the exact original-label repeat law, its >9 behavior, and selection assumptions.
2. Whether the density models original M or augmented Y, and a mathematically consistent treatment of heteroscedastic noise and the density floor.
3. A TRAIN-only demonstrated error mechanism with direction consistent with the proposed correction, plus a natural-population baseline and a proper-score baseline under matched capacity/training exposure.
4. Sufficient independent high-magnitude event support and jointly prespecified bulk, magnitude-tail, and worst-error gates. A normalization identity cannot substitute for these data.

None of those missing empirical requirements was supplied by this source audit. No new fit, retrospective calibration search, posterior adjustment, or novelty claim is justified by it. The specific useful result is the exact repeat-law/noise/floor constraint, which prevents an attractive but invalid shortcut and helps define a future controlled likelihood if evidence warrants one.

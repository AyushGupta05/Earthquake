# One physical hypothesis after the censored pilot

9 October 2026. Research/design only. No new training, real-data reads, downloads or model edits. The completed censored-pilot audit is in `../censored_result_audit/outcome_memo.md`.

## Recommendation

Do not launch another likelihood head merely because it is physically named. The strongest remaining physical hypothesis is narrower: **evaluate the distribution of the actually observed, instrument-filtered prefix, including its covariance, rather than fitting a completed-source spectral curve to a truncated signal.** This could prevent false certainty about the upper magnitude tail when the low-frequency plateau/source duration is not resolved.

A cheap synthetic preflight is justified; a new GPU run is not yet justified. The mathematical ingredients are established. I have not established a novel method, nor found evidence that this construction will beat the existing instrument-static network. A possible contribution would be a demonstrated EEW-specific failure mode and its correction under matched 1/3/5-second information, not “Bayesian spectral magnitude estimation” or “covariance-aware inversion” in general.

This directly addresses the strongest real finding: sensitivity/unit fields explain much of our improvement. HH velocity and HN acceleration need different transfer operators; a gain feature alone is not a physical conversion between them. However, the current INSTANCE M>=4 subset does not prove incomplete-rupture saturation. Its underestimation may mainly reflect label imbalance, source/path/site variation, magnitude type and sensor representation. The one M5.1 event and absence of M>=6 cannot validate a large-rupture mechanism.

## Closest primary antecedents

| Primary source | What is already established; consequence |
|---|---|
| Caprio, Lancieri, Cua, Zollo & Wiemer (2011), **An evolutionary approach to real-time moment magnitude estimation via inversion of displacement spectra**, [10.1029/2010GL045403](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2010GL045403) | Spectrum Inversion estimates plateau, corner frequency and attenuation, converts moment to magnitude, and updates each second after the first network P arrival. It uses 158 California and25 Japan events, M3–7; catalogue location in evaluation; at least1s per station. Available-prefix baseline correction/integration precedes an acausal0.01–15Hz filter and FFT. The paper reports systematic early underestimation. Its uncertainty derives from station estimates, not the proposed full finite-prefix covariance model. Acausal filtering **within an already cut available prefix** is not by itself access to post-cutoff samples. |
| Supino, Festa & Zollo (2019), **A probabilistic method for the estimation of earthquake source parameters from spectral inversion: application to the2016–2017 Central Italy seismic sequence**, [10.1093/gji/ggz206](https://academic.oup.com/gji/article/218/2/988/5484842) | Joint posterior over moment, corner frequency, falloff and attenuation; investigates source-parameter correlations and resolvable bandwidth. Equation6 is a covariance likelihood, but their implementation takes total log-spectrum covariance diagonal, `I*MSE`. They neglect site amplification and assume geometrical factors known. Parameter covariance is distinct from correlation between observed frequency coefficients. |
| Sykulski etal. (2019), **The debiased Whittle likelihood**, [published article](https://academic.oup.com/biomet/article/106/2/251/5318578), [author preprint](https://arxiv.org/abs/1605.06718) | Replaces the population spectrum by the expected finite-sample/tapered periodogram, correcting blurring and aliasing. It explicitly discusses correlations introduced by tapering and spectral leakage. Thus finite-window correction is prior art and must be a baseline; using this correction in an EEW application does not create a new statistical principle. Its stationary-process assumptions do not automatically describe an ongoing transient rupture. |
| Duputel etal. (2012), **Uncertainty estimations for seismic source inversions**, [primary article](https://academic.oup.com/gji/article/190/2/1243/645429) | Correlated errors/covariance in seismic source inversion are established. A claim that “using full covariance is new” would be false. |
| Saoulis etal. (2025), **Full-waveform earthquake source inversion using simulation-based inference**, [author paper](https://arxiv.org/abs/2410.23238) | Neural density inference for source inversion and propagation of realistic noise/covariance uncertainty already exist. Replacing the numerical posterior calculation by an amortized network is not a new mechanism by itself. |
| [PRESTo documentation](https://www.prestoews.org/documentation.php), [PRESTo2010 paper](https://basin.earth.ncu.edu.tw/Course/SeminarII/abstract2014_1/2015.03.19_Chiao%20Chu%20Hsu/PRESTo2010.pdf), [Trugmanetal.2019](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf), [Münchmeyeretal.2022](https://arxiv.org/html/2203.08622v1) | Saturation-aware likelihoods and Gutenberg–Richter upper tails are old. PRESTo describes a2s-P likelihood flat aboveM6.5; Trugman models saturation with measurement time; Münchmeyer learns Gaussian-mixture magnitude distributions and studies GR-like tails. The last paper should not be misdescribed as inventing a literal hard Gaussian-plus-GR graft: its learned mixtures and probabilistic argument are the relevant antecedent. |

The targeted search did not reveal an exact early-window implementation combining all the operators below and evaluating the specific null/ablation below. That absence is not proof of novelty. Standard linear-Gaussian marginalization is sufficient to derive it.

## Precise candidate: an observed-prefix likelihood with response and covariance

Let `u` be a latent source-time vector over a sufficiently long horizon. Let `G_eta` propagate it to physical ground motion (distance, attenuation, radiation/site nuisance `eta`), `H_s` be the known sensor response and unit conversion to counts, and `R_t` retain only samples actually available at1/3/5s. A chosen prefix-only linear preprocessing/projection is `P_t`; `B_t` is a fixed real-valued spectral basis (cosine/sine rows, or another full-row-rank linear compression). Use real coefficients to avoid silently dropping the pseudo-covariance of a complex Fourier vector.

Define

`A_(t,s,eta) = B_t P_t R_t H_s G_eta`.

If a **nonstationary transient source model** has conditional mean `mu_(M,eta)` and covariance `K_(M,eta)`, the Gaussian working likelihood is

`z_t | M,eta,s ~ N(A mu, A K A^T + C_noise + C_model)`.

Known sensor initial-state uncertainty needs its own projected covariance or nuisance marginalization. It cannot automatically be removed by subtracting the first10samples. All nuisance priors and model-error/noise fitting must use TRAIN or genuinely pre-event data. Absolute response/sensitivity and HH/HN unit conversion remain explicit in `H_s`; they are not replaced by a station-ID embedding.

The magnitude distribution is the normalized marginal

`p(M | z_t,s) proportional to pi(M) integral q(z_t | M,eta,s) pi(eta | M,s) d eta`.

The determinant term in the density is essential. Dropping it while optimizing a learned covariance rewards arbitrary variance inflation. A marginal covariance uses the observed rows/columns; it does not condition on unseen future samples being zero. The same distinction must hold in any simulator/amortization.

In a stationary toy case, a tapered spectral coefficient is the convolution of the process spectrum with the observation window. Its expected periodogram differs from the infinite-duration spectrum; nearby frequency coefficients can be correlated. Correcting the expected diagonal alone is the debiased-Whittle baseline. Retaining off-diagonal covariance is the additional proposed ablation. With a finite transient source, the correct object is the time-dependent kernel followed by the observation operator, not a stationary Brune PSD with a time label appended.

**Unresolved design requirement:** the transient kernel/generator must actually represent ongoing rupture and its possible arrest. A Brune amplitude spectrum alone does not specify that process, its phases or causal prefix law. Assigning a completed-event spectrum according to finalM can inject fictitious early information. This is the reason to run the null below before building a neural architecture.

Use the likelihood as a separate distribution estimator, or train a single amortized estimator against its simulations. Do not multiply it into a full-prefix network that already saw the same spectral evidence. If eventually combined by a learned mixture, include a plain matched mixture baseline and describe it as discriminative fusion; density normalization alone does not confer Bayesian correctness.

## Decisive causal null and identifiability checks

Construct moment-rate histories

`r_T(v) = c * min(v,T-v)^2` for `0 <= v <= T`, and zero otherwise.

Their final moments are `M0(T)=c*T^3/12`, so finalMw changes withT. For every `T>2t`, however, the observed source prefix through `t` is exactly `c*v^2`. Under the same causal path/response and noise law, all such candidates induce **the same observed-prefix distribution**. A correct likelihood therefore cannot discriminate those final magnitudes using this prefix. Its posterior along this family is determined by the prior. The claim is about this constructed null, not every real earthquake.

This null is stronger than showing that an estimator's error decreases with time. Reject a proposed generator/likelihood if it creates magnitude information in the null simply from final-duration spectral assumptions, zero-padding as observations, a magnitude-dependent onset alignment, or full-record normalization. Adding more Fourier bins cannot repair that error.

A second check concerns amplitude confounding. In a high-frequency Brune asymptote, log amplitude depends on the combination `logM0 + 2logfc + log(path/site gain)`. With unknown stress drop and path gain, this can be weakly identified even if the spectral fit looks sharp. Do not fix stress drop, distance or site amplification and label the resulting narrowM posterior “data-driven”. A known-location oracle can diagnose representation, but it is a separate protocol from operational early location.

For diagnostics, the ordinary Gaussian Fisher information includes both mean and covariance derivatives. Its nuisance-adjusted Schur complement can quantify local magnitude resolution, but neither Fisher information nor nuisance projection is new. It should diagnose when a posterior is prior-dominated, not serve as an unvalidated threshold that automatically boosts large magnitudes. A global GR tail can reduce overconfidence while worsening rare-event MAE; the user’s bulk/tail objective must still be tested directly.

## Smallest useful preflight and training gate

Before GPU training, freeze the same source/noise/nuisance priors, sensor operators, selected coefficients and inference grid. At1/3/5s compare the following two-by-two design:

| | Diagonal frequency covariance | Full covariance |
|---|---|---|
| Completed-source spectral-curve approximation | Familiar spectral-fit reference | Tests whether covariance alone helps a misspecified source law |
| Actual transient-prefix/window operator | Expected-prefix diagonal/debiased reference | Candidate |

Also retain a simple sensitivity-normalized, unit-aware waveform baseline. Counts plus sensitivity *features* is not identical to this baseline. Report how full response transport differs from scalar normalization; do not credit a new covariance mechanism with an improvement obtained from converting units.

First run the causal null, completed small-source cases, long-source cases, response changes (HH/HN), and noise/attenuation perturbations. Use the same latent physical sources for paired sensor comparisons. Under truly invertible noiseless sensor transforms, correct posterior information should be unchanged; with bandwidth/noise loss, forcing equal posteriors is wrong. Test calibration/coverage and magnitude mean/median errors, not only likelihood fit. A covariance correction could legitimately improve uncertainty without improving the desired point errors.

Only if the candidate passes those checks and improves on the expected-prefix diagonal control should we fit its nuisance/source population on event-disjoint TRAIN and test real held-out records. Start with a bounded representative sample and a low-dimensional spectral projection; no full neural simulator is needed to establish whether the mechanism exists. Choose the projection and nuisance ranges before looking at VALtail results. If a deliberately misspecified simulator is easy but a physically credible one erases the gain, stop.

A subsequent real-data experiment must match events, station availability, source metadata, normalization, priors and decision rule across all four arms. Evaluate bulk MAE/MedAE/CVaR, event-macro high-magnitude error, CRPS/NLL and threshold calibration at all three deadlines. Add station/response-family holdout. Do not use catalogue distances or S arrivals without marking the run as an oracle. The new Alaska large-event data could challenge the mechanism once its causal data/protocol audit is complete; its magnitude distribution is not a calibrated population prior.

Abort this direction if (1) ordinary sensitivity/response normalization explains the gain; (2) diagonal expected-prefix likelihood matches full covariance; (3) realistic nuisance marginalization removes apparent magnitude resolution; (4) only uncertainty widens while tail MAE fails the bulk constraint; or (5) improvement is confined to the already reused13-event INSTANCEtail.

## Why the alternative generic loss-difference gate is not a new principle

Three close primary sources were verified:

- Vasilyev, Wang, Li & Chen (2026), **Calibrating Conditional Risk**, [arXiv2604.20409](https://arxiv.org/html/2604.20409v1): estimates conditional expected prediction loss through regression and studies deferral.
- Joshi, Wang, Hassani & Dobriban (2026), **Risk-Controlled Post-Processing of Decision Policies**, [arXiv2605.06479](https://arxiv.org/html/2605.06479v1): derives thresholding of conditional excess violation risk and calibrates the threshold on held-out data under stated assumptions.
- Mao, Mohri & Zhong (2024), **Regression with Multi-Expert Deferral**, [arXiv2403.19494](https://arxiv.org/abs/2403.19494): regression expert routing with consistent surrogate learning.

For fixed baseline and candidate decisions, learning `E[L1-L0 | X]` is ordinary conditional-risk estimation. Adding an M>=threshold weight changes the estimand/cost; it does not create a different routing mechanism. A budget on bulk loss and an objective for tail loss gives a standard constrained-policy Lagrangian. An EEW-specific, event-cross-fitted constraint can be a useful empirical construction, but a substantive claim needs more than substituting magnitude into an existing optimization.

No physical or risk-gating candidate here has yet earned a foundational novelty claim. The source/window/covariance interaction is the more concrete **physical falsification target**, and it should be tested cheaply before using the remaining credits.

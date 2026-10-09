# Amplitude-aware distributions and future-growth supervision for EEW

Research memo, 9 October 2026. Research only: no model implementation, dataset modification, or AWS training was performed for this task. A small standard-library Python calculation verifies the probability identities below; it does not test an earthquake model.

## Decision

**Do not present a log-amplitude shift plus an amplitude-normalized magnitude distribution as new.** Zhang, Zhang and Tian already implemented that construction in 2021. A 2026 INSTANCE paper describes a closely related single-station probabilistic approach. TEAM-LM, magnitude/PGA multitask models, Bayesian saturation models, and future-wavefield prediction further narrow the available contribution.

The most useful next hypothesis is a **conditional future-growth auxiliary objective** that preserves the magnitude marginal by construction. Its possible contribution is a demonstrated benefit of modeling the dependence between magnitude and yet-unobserved amplitude growth, beyond ordinary future-amplitude regression. The exact variable transformation, the probability chain rule, Gaussian covariance propagation, and generic multitask learning are all established mathematics—not proposed novelties. No search can certify that the remaining narrow combination is first.

Prioritize a matched, inexpensive falsification pilot before a larger architecture. Keep a saturation-aware conditional likelihood as a second, more demanding research option. Neither formulation makes final magnitude identifiable from an uninformative early prefix.

## Verified nearby primary work

| Work and direct source | What is established and why it matters |
|---|---|
| [Zhang, Zhang & Tian (2021), GRL, DOI 10.1029/2020GL089394](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020GL089394); [author preprint, equation in supplement p. 9–10](https://arxiv.org/pdf/2006.01332) | Normalizes a 12-station waveform array by maximum amplitude and predicts a one-dimensional distribution for normalized magnitude. The explicit label is `Mr = M − log(Amax)`; amplitude is restored to obtain magnitude. Gaussian-shaped labels are trained, rather than establishing that output width is calibrated posterior uncertainty. The journal text discusses early underestimation, clipping and saturation. This directly occupies the generic residual-distribution construction. |
| [An end-to-end deep learning approach for epicentral distance and magnitude determination from single station waveforms (2026), DOI 10.1016/j.acags.2026.100356](https://www.sciencedirect.com/science/article/pii/S2590197426000406) | The publisher abstract explicitly describes INSTANCE, amplitude/shape decoupling through pseudo-normalization, prediction of magnitude contribution excluding absolute amplitude, Gaussian outputs and multiple streaming windows. Only the indexed publisher abstract was accessible here; precise equations, splitting and timing need full-text verification before numerical comparison. Its aggregate MAE is not evidence of a matched 1/3/5-second benchmark. |
| [TEAM-LM (2021), DOI 10.1093/gji/ggab139](https://arxiv.org/abs/2101.02010); [authors' implementation](https://github.com/yetinam/TEAM) | Normalized waveform features retain log peak amplitude; the magnitude head is a Gaussian mixture. The paper identifies high-magnitude underestimation and cross-region transfer as a mitigation. Its streaming, changing station set is an appropriate network reference, not proof that amplitude-preserving features alone solve extrapolation. |
| [Kuang, Yuan & Zhang (2021), DOI 10.1785/0220200317](https://doi.org/10.1785/0220200317); [indexed text of the paper](https://www.researchgate.net/publication/349469943_Network-Based_Earthquake_Magnitude_Determination_via_Deep_Learning) | Full-network MagNet uses augmented magnitudes and Gaussian-shaped output labels. Indexed primary-paper text verifies amplitude-altered examples and explicitly limits augmentation where finite-fault behavior invalidates a point-source assumption. The reported difficulty above 6.5 is explicit. The parent identified simulated magnitudes 1–7; that exact interval was not independently recovered here. This is a paper-text mirror, not a secondary review. |
| [Trugman et al. (2019), DOI 10.1029/2018JB017093](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf) | Gives a time-dependent, smoothly saturating displacement–magnitude relation and a Bayesian posterior using a magnitude prior and an amplitude likelihood. Thus, a saturation curve plus Gutenberg–Richter prior is prior art. At large magnitudes early amplitudes can provide mainly a lower constraint, leaving the prior influential; network observations also have correlated errors. |
| [Zhang & Zhang (2024), Universal neural networks…, DOI 10.1038/s43247-024-01718-8](https://www.nature.com/articles/s43247-024-01718-8) | Indexed publisher methods specify single-station magnitude inputs containing normalized three-component waveforms, distance and log normalization factor; a Gaussian-shaped magnitude target; and random truncation at 1–25 seconds. This is another direct amplitude-plus-shape, variable-window predecessor. |
| [SeismNet, An end-to-end multi-task network for early prediction of instrumental intensity and magnitude (2024)](https://www.sciencedirect.com/science/article/abs/pii/S136791202400364X) | The publisher abstract explicitly describes simultaneous magnitude/intensity prediction and comparison with a single-task model. This is the closest verified generic argument for using a future shaking target to improve magnitude. Full loss details and the intensity measurement window were inaccessible; do not infer a conditional joint density or exact future-growth target from the abstract. |
| [DFTQuake (2025), DOI 10.1016/j.engappai.2025.110077](https://www.sciencedirect.com/science/article/pii/S0952197625000776) | Publisher text describes early-three-second magnitude and PGA prediction using acceleration, velocity and displacement attention. It establishes that predicting both quantities is existing work. This reading does not establish whether its training uses a shared probabilistic joint head; that distinction requires full methods. |
| [DHLnet (2024), DOI 10.1029/2023EA003363](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023EA003363) | Hybrid CNN/GCN methods estimate distance, magnitude, PGA and PGV, embedding distance in the latter estimators. Physical inputs and multiple EEW targets are established. The methods use separately named prediction models; do not call this proof of the particular shared conditional-growth objective below. |
| [WaveCastNet (2025), DOI 10.1038/s41467-025-65435-2](https://www.nature.com/articles/s41467-025-65435-2) | Forecasts future wavefields from early observations and derives ground-motion measures. Its emphasis is direct shaking prediction, not the proposed magnitude auxiliary factorization. The paper also discusses limitations from finite-fault diversity and its low-frequency simulation setting. Future-waveform supervision itself is therefore not a new EEW concept. |
| [Statistical Characterization of P-wave Growth for EEW (2018)](https://www.jstage.jst.go.jp/article/rtriqr/59/2/59_128/_pdf/-char/en) | Investigates early P-wave growth characteristics versus magnitude before peak arrival. A new method should not claim the first use of envelope growth as magnitude information. |
| [Determination of Event Magnitudes with Correlated Data and Censoring (1988)](https://academic.oup.com/gji/article/95/1/31/601798) | Publisher-indexed abstract describes correlated measurements and censoring by clipping/non-detection. Censored amplitude likelihoods are established in seismology. Instrument clipping must be distinguished from an ongoing rupture's physical saturation. |

Targeted searches covered amplitude equivariance, normalized magnitude distributions, future peak/energy privileged supervision, magnitude/intensity multitask learning, waveform forecasting, clipping/censoring and saturation-aware neural magnitude estimation. There was no verified primary source in this search implementing exactly `p(M|prefix) p(future log-peak growth|M,prefix)` for improving the magnitude marginal. That is a search result with incomplete full-text coverage, not a novelty conclusion.

## 1. Separate three different scaling operations

Let `x` be counts, `s` instrument sensitivity, and `u=x/s` approximate native motion. All amplitude logarithms below mean `a=log10(A/A0)` with a declared reference amplitude `A0` in the same units.

1. **Instrument representation change:** `(x,s) → (c x,c s)` leaves `u` unchanged. The desired magnitude distribution must be invariant. This is a valid nuisance test. Changing counts alone while keeping the true sensitivity fixed is a different operation. Sensitivity division is only a gain approximation; frequency-dependent response correction remains separate.
2. **Fixed-shape physical scaling:** `u → c u` keeps the entire waveform shape/time history fixed. Under the stated fixed-source geometry/time interpretation, seismic moment scales by `c`, giving `ΔMw=(2/3)log10(c)`, and stress drop also scales by `c`. This differs from a usual larger rupture with approximately constant stress drop. The [primary amplitude-scaling analysis](https://arxiv.org/pdf/2305.05631) derives this interpretation and its empirical constraints. For a fixed local-magnitude amplitude definition, the corresponding shift is `ΔML=log10(c)`. These coefficients cannot be interchanged.
3. **Natural high-magnitude growth:** larger rupture area/duration, changed corner frequency, directivity, site nonlinearity and truncation alter shape. In a Brune-type constant-stress-drop scaling, increasing moment also lowers corner frequency; multiplying all recorded samples does not reproduce this. A hard shift is an inductive assumption on a restricted family, not a general physical law for final earthquake magnitude.

Mixed magnitude labels further complicate an enforced coefficient. Do not provide the eventual catalog magnitude type as an inference feature. Either specify the output scale prospectively, evaluate homogeneous labels, or treat a learned slope as an empirical training parameter and audit its transfer. Velocity and acceleration amplitudes need separate references/types; sensitivity-normalized counts are not automatically displacement.

For shape `z=x/A(x)` and a shift head `p(m|x)=q(m−αa|z)`, positive global scaling yields `p(m|cx)=p(m−αlog10(c)|x)` whenever preprocessing and the support respect that transformation. This is straightforward algebra, already reflected in normalized-magnitude predecessors. Adding amplitude-dependent mixture weights, width or a gate generally breaks exact equivariance. An empirical posterior also reflects a magnitude prior, recording selection and noise; physical likelihood scaling does not guarantee a universally shifted posterior. Finite magnitude bounds are another failure of exact translation.

## 2. Define future growth without leaking it

At time `t∈{1,3,5}` seconds after the allowed P pick, choose a **prespecified training reference horizon** `T>t`. For the first pilot use `T=10 s` for every input horizon; this is a future supervision deadline, not extra inference input. Alternatively, the already available 5-second prefixes can supervise only 1/3 seconds, but `T=t=5` gives a trivial zero-growth target and cannot test the 5-second claim.

Use a fixed causal stream `u(τ)` and its running peak:

```
A_t = max_{0≤τ≤t, components} |u(τ)|
a_t = log10(max(A_t, A_floor)/A0)
G_tT = a_T − a_t ≥ 0
R_T = M − α a_T
M = α a_t + R_T + α G_tT.                         (1)
```

The last equality is an exact target identity for any chosen `α`. It proves no earthquake scaling law and no early predictability. `G` describes later recorded amplitude growth, which can include later P/S energy, noise, clipping, path effects and wave interference. Do not call `G=0` rupture completion, or call a 10-second running peak final PGA/PGV.

Important preprocessing consequence: **do not recompute a different demean/detrend on each prefix** when defining a nonnegative running-peak increment. The prefix `[0,10,10]` has demeaned peak `6.667`, while its extension `[0,10,10,0]` has demeaned peak `5`. Horizon-specific demeaning can therefore make apparent growth negative. Use the same fixed baseline/causal filtering state for all horizons. Any pre-P initialization must be equally available to all inference models and explicitly reported. Existing INSTANCE whole-record preprocessing remains a separate causal limitation.

At a network deadline, only received samples and causally available station identities can be used. A global maximum over an expanding observed set is monotone; a median over a changing station set need not be. Avoid catalog-distance station selection and synchronization that gives every station a full prefix before it actually arrives. The first pilot should stay single-station to avoid changing its evaluation task.

Training may compute `a_T/G/R_T` from later **training** data. Neither labels nor realized future amplitude may enter the early encoder, feature normalization, gating, checkpoint selection or inference. Event-disjoint splits remain essential. Missing future labels must be reported; keep magnitude-only training/evaluation available rather than filtering the target population silently. Long traces are training supervision, not additional early evidence.

## 3. What a correlated residual/growth head actually buys

Suppose, conditionally on the early prefix, an ordinary bivariate Gaussian is predicted:

```
(R,G) ~ N([μR, μG], [[σR², ρσRσG], [ρσRσG, σG²]])
μM = α a_t + μR + α μG
σM² = σR² + α²σG² + 2αρσRσG.                    (2)
```

This is tractable and the projection is exact. But Gaussian `G` assigns probability to impossible negative growth. Clipping sampled `G` at zero changes the distribution and requires the atom/changed projection to be modeled; truncation also changes normalization and generally removes the Gaussian closed form. A Gaussian can be a diagnostic baseline with reported `P(G<0)`, not an automatically valid physical growth model.

Covariance matters. The numerical example in the accompanying script has `σR=1`, `σG=.9`, `ρ=−.95`, `α=1`: correct magnitude variance is `0.10`; an incorrect independent convolution gives `1.81`. The same example assigns `32.84%` probability to negative growth. Dropping covariance is a large modeling error, but retaining it is standard probability propagation.

**Reparameterization check:** conditional on `a_t`, the map `(R,G)→(M,G)` has determinant one. An unrestricted bivariate Gaussian remains an unrestricted bivariate Gaussian after this affine transformation. Thus:

```
−log q_RG(M−αa_t−αG, G | X_t)
   = −log q_MG(M,G | X_t).                       (3)
```

If parameterizations and optimization are correspondingly transformed, there is no new statistical model. The one-dimensional magnitude marginal is still Gaussian. Improvements can arise from restrictions, representation sharing, regularization or optimization, not from the coordinate identity or a newly created source of information. Likewise, any proper joint `(R,G)` can be written as `p(M|X)p(G|M,X)`.

For the Gaussian case, write `p(M|X)=N(μ,σ²)` and `p(G|M,X)=N(γ+β(M−μ),τ²)`. Its NLL is, up to constants:

```
L = log σ + (M−μ)²/(2σ²)
  + log τ + [G−γ−β(M−μ)]²/(2τ²).                (4)
```

This displays the actual modified training objective: the future-growth residual is conditional on the magnitude residual. Setting `β=0` gives the independent Gaussian auxiliary task. Conditional gradients can alter finite-capacity training, but this formula is not a new theorem and provides no guarantee of better magnitude error.

## 4. Recommended valid head: retain the magnitude marginal

Let `h_t` be a trainable representation of the available prefix, instrument information and `t`. Keep exactly the same magnitude density `pθ(M|h_t)` in all pilot arms. It can be a continuous mixture, or the existing binned distribution. For binned output, condition the auxiliary on the magnitude bin and state that the joint random variable is the bin; do not mix a discrete mass with an unspecified continuous density.

Add a nonnegative conditional growth distribution:

```
pθ,φ(M,G | X_t) = pθ(M | h_t) pφ(G | M,h_t,t,T)

pφ(G | M,h) = πφ(M,h) δ0(G)
             + [1−πφ(M,h)] LogNormal(G; μφ(M,h), σφ(M,h)²).
                                                               (5)
```

Use a sigmoid for `π` and positive, numerically bounded `σ`. The point mass at zero represents the genuine event that the maximum observed by `t` remains the maximum at `T`. For `G>0`, the density includes the `1/G` Jacobian. Exact zeros and small positive values must be distinguished consistently. A tolerance-binned version is possible, but defines a different observation model and must state its bin width.

Since the conditional factor integrates to one:

```
∫ pθ,φ(M,G | X_t) dG = pθ(M | h_t).             (6)
```

At inference the output is **just the magnitude head**. Do not condition on observed future `G`, replace it by a guessed point value and treat that as new evidence, or feed true `M` into the deployed network. To display a growth forecast, marginalize over predicted `M` (sum over bins or use quadrature/sampling). During supervised training the true magnitude/bin is a legitimate input to this conditional auxiliary; it is absent from the deployed magnitude path.

The literal joint NLL is:

```
Ljoint = −log pθ(M|h)
         −1[G=0] log πφ(M,h)
         −1[G>0] {log[1−πφ(M,h)]
                    − log G − log σφ − .5 log(2π)
                    − [log G−μφ]²/(2σφ²)}.                    (7)
```

Inverse sampling weights apply to the **whole per-record loss** when population scores are the goal. A multiplier `λ` on the auxiliary is a composite multitask objective; `λ=1` is the joint NLL. Positive conditional losses can still cause negative transfer in a finite shared network. Keep main-head scoring, loss scaling and training budget matched and chosen before evaluation.

For an interpretable low-cost conditional head, make `μφ(M,h)=b(h)+β(h)(M−m_ref)` and `logit πφ(M,h)=c(h)+d(h)(M−m_ref)`, with a fixed training-defined reference. This does not require a predicted-magnitude residual or let the growth head directly recalibrate the output at inference. It tests whether magnitude-dependent future dynamics improve the shared representation. An unconstrained conditional MLP is a later ablation, not necessary initially.

Equation (6) means the auxiliary does not change the magnitude **family or marginal for fixed parameters**. Training shared parameters can of course change the fitted magnitude predictions. With a frozen encoder and disjoint heads there is no route for the auxiliary to improve magnitude; that is a useful negative control.

### Comparison with simpler future supervision

* A head minimizing `(a_T−â_T)²` is ordinary future-amplitude regression. If `â_T=a_t+ĝ`, its squared error is identically `(G−ĝ)²`. Growth versus future-amplitude MSE with that skip is only a target reparameterization. Do not claim one is new because its notation differs.
* `p(M|h)p(G|h)` is probabilistic multitask learning with an independence assumption in the joint. The conditional factor in (5) relaxes that assumption while retaining the exact magnitude marginal.
* Joint residual/growth projection can account for covariance **if a residual decomposition is used**. It creates no extra expressive power over a comparably flexible direct joint density. The marginal-preserving form makes this transparent and avoids an independence-induced variance artifact.
* A conditional `p(G|M,t,instrument)` that ignores waveform features is a strong diagnostic: it tests whether the auxiliary merely learns a label-to-growth relationship. Compare its held-out conditional likelihood with `p(G|M,h,t,instrument)`. This is evidence about the auxiliary, not sufficient evidence of improved magnitude.
* Conditional likelihood, auxiliary future-target learning and hurdle/lognormal distributions are established techniques. The only defensible prospective contribution is an explicitly scoped EEW formulation plus reproducible evidence of an advantage over these controls at equal input time and capacity.

## 5. Alternative: shape-conditioned saturating amplitude likelihood

A more physical but harder model would separately estimate a shape-conditioned magnitude prior `q(M|z_t,c)` and a **conditional** amplitude likelihood `L(a_t|M,z_t,c)`:

```
p(M|z,a,c) ∝ q(M|z,c) L(a|M,z,c).
```

Both factors must describe the same training population. Multiplying a full-waveform posterior by another amplitude likelihood double-counts amplitude; multiplying two posteriors also counts their prior twice. Shape-normalized observations still encode magnitude-dependent duration/noise, so using a shape-conditioned prior is deliberate.

One simple likelihood mean is `b(z,c)+κ(z,c)[M−τ softplus((M−s_t(z,c))/τ)]`, with `κ,τ>0`. Its magnitude slope decreases smoothly toward zero. This mathematical saturation class is closely related to integrating a survival function, as in Trugman's existing construction. Its possible delta is learned prefix-shape conditioning and explicit response/path uncertainty, **not saturation or Bayes' rule**. Distance correction must use a current probabilistic estimate, not catalog distance. Shared event effects or a correlated multistation likelihood are needed before treating station products as independent evidence.

When the amplitude likelihood becomes nearly constant across large magnitudes, broad asymmetric posterior tails are appropriate. A mixture gate cannot manufacture evidence resolving that ambiguity. Learned sigmoid gating alone is neither a physical validation nor a strong method contribution. Finite-fault simulations and enough independent large events would be needed to validate extrapolation; a cheap INSTANCE head pilot is insufficient for that claim.

## 6. Prespecified falsifiable pilot

Use the same training/validation event split, input traces, inverse sampling weights, frozen waveform encoder (if desired), **trainable shared residual representation**, feature scaling, magnitude head, seed set, batches and fixed epochs. All auxiliary inputs are generated from the same eligible prefix. No test set is consulted. Use a common later target horizon `T=10 s`; derive its peak from the actual waveform with the same fixed causal baseline as early peaks, not stored full-trace PGA/PGV/SNR.

Core arms at **each 1/3/5-second horizon**:

| Arm | Objective beyond the identical magnitude score | Question |
|---|---|---|
| A | None; allocate the same auxiliary parameters but disable their gradient | Matched magnitude-only baseline |
| B | Future-log-amplitude MSE with `â_T=a_t+ĝ` | Does ordinary privileged future supervision suffice? |
| C | Unconditional hurdle/lognormal growth NLL `p(G|h)` | Does a proper nonnegative distribution help beyond MSE? |
| D | Conditional hurdle/lognormal NLL `p(G|M,h)` | Does dependence modeling help beyond C? |
| E | Same as D, but detach `h` before auxiliary evaluation | Tests the hypothesized representation pathway; magnitude behavior should match A up to controlled numerical randomness |

Use matched auxiliary parameter counts where possible (for example provide an always-zero magnitude input in C). Preserve magnitude-path RNG consumption across disabled/detached controls; otherwise a changed dropout sequence can confound E. Keep any future target normalization fitted only on training. Fix `λ` and numerical scale floors in advance; start with `λ=1` for the likelihood comparison, reporting magnitudes of both losses and gradients. Do not choose a weight by repeatedly inspecting the reused validation tail.

Prespecified diagnostic extensions after the core comparison:

1. `p(G|M,t,instrument)` without waveform features, and a within-magnitude-bin shuffled-growth label control, to expose a label shortcut or nonspecific auxiliary regularization. Shuffling is a diagnostic training intervention, never a physical synthetic earthquake.
2. A correlated-Gaussian joint `(M,G)` versus its equivalent `(R,G)` implementation with analytically transformed parameters. Their outputs/NLL should agree. Differences in this equivalence test are implementation errors, not evidence for a new method.
3. Ordinary amplitude-shift residual distribution and shape-plus-log-amplitude unconstrained baseline, using identical input information. This measures practical value against the closest architectural prior art, separately from the auxiliary-objective question.
4. Source-scale tests only in a predeclared limited range, with the label scale and stress-drop interpretation explicit. Instrument gain countertransform tests should preserve outputs without shifting magnitude. Do not count a model passing its enforced identity as proof of real-earthquake generalization.

Primary success criterion: D improves event-macro and recording-level error on M≥4 versus A **and B/C**, with paired event-bootstrap uncertainty, while overall MAE and MedAE stay inside a predeclared noninferiority margin. A candidate margin is 0.01 magnitude units, to be agreed/frozen before runs; it is not an empirical result. Report all seeds and all three times, tail bias, CVaR95, false-positive rates, and proper distribution scores (NLL/CRPS, interval coverage/PIT). M≥4 is a dataset-relative tail; it does not establish performance on M7–9 events. Do not select the best decision rule after seeing results: report the prespecified mean and median.

Falsification: if D does not beat B/C across matched seeds, or only improves with label shortcuts/invalid preprocessing, the conditional-density contribution is unsupported. If all future-supervision arms improve similarly, the contribution is useful multitask training rather than a special transport/covariance mechanism. If only uncertainty scores improve, claim calibration/forecast quality rather than improved point error. Existing 66-bin support cannot test arbitrary magnitudes beyond its upper range; expanding to a continuous or overflow model is a separate matched experiment.

## 7. Numerical checks completed

Run `python3 work/instrument_research/check_amplitude_density_equations.py`. It uses only Python's standard library and synthetic numbers, with no GPU or earthquake data. Results are saved in `amplitude_equation_checks.json`.

| Check | Result |
|---|---:|
| Correlated Gaussian projection versus analytic magnitude density | Maximum absolute error `4.77e−15` |
| `(R,G)` versus `(M,G)` change-of-variable NLL | Maximum error `4.88e−15` |
| Gaussian joint versus conditional-factor NLL | Maximum error `4.44e−16` |
| Hurdle conditional integrated out versus unchanged magnitude mixture | Maximum absolute error `6.66e−16` |
| Covariance example: correct versus independent magnitude variance | `0.10` versus `1.81` |
| Gaussian growth example's probability below zero | `0.32836` |
| Prefix-specific demeaning counterexample | Peak falls from `6.667` to `5.0` after extension |

These checks support the algebra/support cautions only. No claim of empirical magnitude improvement or scientific novelty follows from them.

## 8. Extension: score the predicted growth mixture as well as the labeled joint

**Conclusion before implementation:** this is a valid composite proper score when its component models can express the truth. It provides a direct magnitude-logit gradient, but that gradient is the established mixture-responsibility gradient. The extra score supplies no independent information when magnitude and growth are already observed on the same training records. Its possible benefit is a finite-capacity inductive bias; there are simple settings in which it does nothing, increases variance, or creates misleading tail gains. Stop-gradient protects one gradient path, not against a wrong growth model.

### 8.1 Exact objective and consistency statement

Use the existing discrete magnitude variable `Y=k`, rather than mixing a bin probability with an undefined continuous-magnitude density. At a fixed prefix `X=X_t`, define

```
p_k = P_theta(Y=k | X),
q_k(g) = q_phi(G=g | Y=k, X),
z(g) = sum_k p_k q_k(g),

L = -log p_Y - lambda log q_Y(G) - gamma log z(G),
lambda > 0, gamma >= 0.                                         (6)
```

For the hurdle model, all experts use the same dominating measure: a point mass at zero plus Lebesgue measure on positive growth. At `G=0`, evaluate the hurdle probabilities, not positive-density values at zero. At `G>0`, include the positive density and `(1-pi_k)`. Compute `log z` by `logsumexp(log p_k + log q_k)`. Retain the inverse sampling weight on the **whole record loss**, so the marginal score targets the same event/recording population as the magnitude score. The teacher conditioning variable at training is the true magnitude **bin**; the deployed predictor still takes only `X`.

At `lambda=1, gamma=0`, (6) is the ordinary joint NLL. For `gamma>0`, it multiplies that joint likelihood by an overlapping marginal factor. It is not the likelihood of two independent observations. Conditional on `X`, its excess population risk relative to the true joint is exactly

```
KL(P_Y || p)
 + lambda sum_k P_Y(k) KL(Q_k || q_k)
 + gamma KL(P_G || z).                                         (7)
```

Thus it is minimized at the true joint when the truth is achievable; with positive magnitude and conditional weights it identifies that joint on classes of positive true probability. The added term is redundant at that population optimum. This statement is about the loss with ordinary gradients, not a claim that arbitrary neural optimization finds the optimum or that a misspecified family preserves calibration. If `lambda=0`, magnitude CE still identifies `p` in an unrestricted well-specified model, but the individual `q_k` are not identified by the mixture; they can all equal `P_G`.

This is an application of established composite likelihood, which combines weighted marginal and conditional terms and requires care with their dependence. Standard inverse-Hessian uncertainty calculations do not automatically apply; use event-level resampling for the actual EEW experiment. See [Varin, Reid and Firth (2011), Sections 2.1–2.3](https://utstat.utoronto.ca/reid/research/varin_reid_firth.pdf). Equation (7) and the toy calculations below are direct derivations here, not claims of a new general scoring principle.

### 8.2 What gradient is new relative to the existing auxiliary head?

Holding the `q_k` values fixed, with magnitude logits `v_k`, let

```
r_k = p_k q_k(G) / z(G).
d[-log z(G)]/dv_k = p_k - r_k.
d[-log p_Y - gamma log z(G)]/dv_k
    = (1+gamma)p_k - 1[Y=k] - gamma r_k.                        (8)
```

`r` is the posterior class responsibility after the **training-only** future target is revealed. It is not an additional available observation at time `t`. Never deploy `r` by substituting the actual future target, and never describe this term as independent Bayesian evidence about an already-observed event. Its direct gradient can change the magnitude head even with a frozen feature encoder.

In ordinary joint NLL, `-log q_Y(G)` has no direct magnitude-logit derivative if the two heads are disjoint; it can help only through their trainable shared representation. The same is true of a disjoint future-amplitude MSE head. A simple counter-control can also create a direct gradient: predict `E[G|X]=sum_k p_k mu_k(X)` with frozen growth-expert means and minimize its squared error. Beating ordinary disjoint MSE alone does not demonstrate that a full mixture density is needed.

The mixture likelihood and expert-responsibility mechanism are explicit in [Jacobs, Jordan, Nowlan and Hinton (1991), equations 3–6](https://people.eecs.berkeley.edu/~jordan/papers/mixtures-of-experts.pdf). Class-conditional generative training with class-marginal likelihood for missing labels is also established; see [Nigam et al. (2000)](https://www.cs.columbia.edu/~jebara/6772/papers/nigam99text.pdf). The distinction here is that **the same EEW records already have magnitude labels**: hiding their labels in an additional term creates a composite objective, not new unlabeled data. The Columbia PDF's browser extraction is corrupted, but its indexed primary-paper abstract and bibliographic identity are readable; no unverified detail of its algorithm is needed for the comparison.

### 8.3 Collusion, identifiability and stop-gradient

Several failure conditions are directly testable:

* **Magnitude-independent experts:** if every `q_k(G|X)` is the same, `r=p` and the mixture term supplies zero magnitude-logit gradient. This can be correct if growth has no class information given the prefix, or a shortcut if a flexible expert predicts growth from `X` while ignoring `k`.
* **Saturated empirical fitting:** if free `p` and free `q` fit an empirical joint table, that same joint already fits the empirical growth marginal. Adding the marginal NLL leaves the global fit unchanged. A different fitted solution in a constrained neural model is regularization or optimization behavior, not new likelihood information.
* **Unanchored experts:** the marginal term alone cannot assign physical magnitude meanings to mixture components. Magnitude CE and supervised `q_Y` anchor their labels, but rare classes have fewer anchors. Their conditional density can remain wrong despite a good aggregate growth score.
* **Density spikes and memorization:** continuous experts may fit individual growth targets with tiny scales, while all experts can bypass class structure by memorizing `X`. Use fixed scale floors and examine held-out conditional likelihood. A low training NLL is insufficient evidence of a physical relationship.
* **Wrong conditional growth:** instrument effects, site/path effects, changing preprocessing, pick errors and the finite target horizon can all be absorbed incorrectly as a magnitude effect. Even a perfectly frozen expert then pushes `p` toward its own misspecification. Physical growth is not guaranteed monotone in magnitude conditional on a short local prefix.

`-log sum_k p_k stop_gradient[q_k(G)]` blocks the marginal term from changing the experts or their shared-feature route. It retains (8) through `p`. It can prevent experts from adapting **to that particular term**, but does not correct miscalibration, class-independent collapse in the conditional objective, or earlier memorization. If `q` is still trained via `-log q_Y`, these updates are generally not the full gradient of the displayed scalar (6): they form a modular training rule. At a correctly specified population solution the component expected gradients still vanish, but the ordinary full-objective proof is not an optimization guarantee for this rule.

A cleaner diagnostic is a separately trained, frozen growth teacher whose inputs are fixed causal prefix features. Use event-level cross-fitting to obtain `q_k(G_i|X_i)` on training records that the teacher did not fit. This reduces same-record memorization; it does not make the teacher correct, add information, or prove consistency of a finite model. Out-of-fold teacher likelihoods may be cached for all bins. A trainable shared student representation then cannot change the teacher behind the stop-gradient boundary. Treat cross-fit teacher quality as part of the experiment, not an oracle.

Cutting feedback has a substantial existing literature on controlling misspecified modules, for example [Liu and Goudie, A General Framework for Cutting Feedback within Modularised Bayesian Inference](https://arxiv.org/abs/2211.03274). Neural stop-gradient here is only an analogy, not an implementation of their Bayesian cut posterior. It protects `q` from this loss while deliberately allowing `q` to influence the scientifically central `p`; it therefore does **not** shield magnitude predictions from a suspect growth model. The broader possibility of generative marginal training degrading classification through bias is established in [Cozman, Cohen and Cirelo (2003)](https://aiinternational.org/Library/ICML/2003/icml03-016.php).

### 8.4 A fully labeled counterexample with an efficiency calculation

Take one uninformative prefix stratum, `Y~Bernoulli(pi)`, and binary nonnegative growth with known `P(G=1|Y=0)=q0` and `P(G=1|Y=1)=q1`. Let `d=q1-q0`, `r=q0+d*pi`. The complete-data magnitude-label score and the growth-marginal score are

```
s_Y = (Y-pi)/(pi(1-pi)),
s_G = d(G-r)/(r(1-r)),
I_Y = 1/[pi(1-pi)],   I_G = d²/[r(1-r)],
Cov(s_Y,s_G) = I_G.
```

For the estimating score `s_Y+gamma*s_G`, the sensitivity is `I_Y+gamma*I_G`, while its variance is `I_Y+(2gamma+gamma²)*I_G`. Relative to using observed labels alone, its asymptotic estimator variance is

```
kappa = I_G/I_Y in [0,1],
V_composite/V_label
 = [1+(2gamma+gamma²)kappa]/(1+gamma*kappa)²
 = 1 + gamma²*kappa(1-kappa)/(1+gamma*kappa)² >= 1.              (9)
```

The bounds follow because the observed `Y` is at least as informative about its own prevalence as the noisy growth it generates. Equality occurs for irrelevant growth, perfectly class-revealing growth, or zero extra weight. Intermediate noisy growth reuses a less informative correlated observation and loses efficiency. This proof concerns known `q`, free `p`, regular interior parameters and fully observed labels; it does not rule out a useful representation bias in a constrained waveform network. It does rule out claiming the extra term must improve magnitude estimates because it adds a physical observation.

If genuinely additional records have growth but no magnitude label, their marginal likelihood can add data under appropriate assumptions. That is ordinary semi-supervised generative learning, and is a different experiment from double-scoring the current fully labeled records.

### 8.5 Reproducible CPU experiment, not an EEW result

Run `python3 work/instrument_research/check_growth_mixture_score.py`. It runs six focused algebra checks and 5,000 paired synthetic training repetitions with 250 records each, seeds `100000..104999`. All records have the same uninformative `X`, true tail prevalence `pi=.05`, true `q0=.10`, `q1=.80`, and `gamma=1`. Define artificial magnitude `M=2+3Y`; evaluate exact population risks of the predictive mean `2+3p`. This deliberately isolates the direct logit route, without representation learning. Results are saved to `growth_mixture_score_checks.json`.

| Estimator | Mean estimated tail probability | Probability-estimation MSE | Overall mean-prediction MAE | Tail mean-prediction MAE |
|---|---:|---:|---:|---:|
| Magnitude CE only | .049892 | .000186451 | .284708 | 2.850324 |
| Joint NLL, separate free auxiliary head | .049892 | .000186451 | .284708 | 2.850324 |
| Future-growth MSE, separate free auxiliary head | .049892 | .000186451 | .284708 | 2.850324 |
| Added marginal NLL, known-correct frozen q | .050145 | .000205419 | .285391 | 2.849566 |
| Added marginal NLL, wrong frozen q0=.02 | .086489 | .001619117 | .383519 | 2.740534 |
| Added marginal NLL, same-sample empirical conditional q | .049892 | .000186451 | .284708 | 2.850324 |

The joint-NLL and independent-MSE rows are analytically identical estimators in this toy and are set to the same label-frequency estimate; they are not separate neural training runs. The saturated empirical-q solution agrees with CE to `1.39e-17`. The correct frozen-q composite increases finite-sample probability variance by **10.17%**, compared with **11.10%** asymptotically from (9). Its paired probability-MSE increase is `1.897e-5` with Monte Carlo standard error `1.959e-6`.

Under the wrong frozen expert, the **population** optimum moves from `.05` to `.0866329`. That improves the synthetic tail mean-prediction MAE from `2.85` to `2.74010` while worsening overall MAE from `.285` to `.383909`; the predictive median remains `2`. This is a concrete warning about apparent tail gains obtained by shifting everyone upward. It persists with perfect optimization and unlimited training data, and therefore also persists with stop-gradient. These numbers are not forecasts of the earthquake pilot.

### 8.6 Small pilot that could justify further work

Keep the original A/B/C/D controls from Section 6, but add a **direct-gradient comparison** before scaling up:

1. Fit one low-capacity, event-cross-fit `q_k(G|X_t)` teacher using only training labels and future training growth. Freeze its inputs/parameters. Report out-of-fold conditional NLL against class-independent and label-only alternatives, per magnitude band. If it is poorly calibrated in the rare band, the mixture constraint is not ready to be treated as physical guidance.
2. With the identical student, run `CE` alone; `CE + ordinary disjoint future-amplitude MSE`; `CE + conditional joint auxiliary NLL`; `CE + gamma*(-log sum p_k q_k)` with frozen q; and `CE + gamma*(G-sum p_k E_q[G|k,X])²` with those same frozen experts. The last comparison separates a direct gradient through magnitude probabilities from the value of modeling the full growth density. Scale targets once from training and state that MSE and NLL weights have different units; do not interpret equal numeric weights as equal gradient strengths.
3. For the proposed learnable joint-plus-marginal version, add matched `joint NLL + marginal NLL` with full gradient and with stop-gradient q. Neither should replace the frozen-q diagnostic. Allocate the same head parameters/RNG sequence in all arms; report their actual gradient norms, fixed weights and all seed outcomes. Prespecify a small `gamma` and optionally `gamma=1` as a sensitivity arm; never select the better one after inspecting the tail and present it as confirmatory.
4. Evaluate each **1/3/5-second** input and the same fixed future target horizon, event splits and exact weights. Use the earlier overall-error noninferiority criterion, tail bias, false positives and proper distribution scores. Inspect whether changes in magnitude probability agree with out-of-fold growth responsibilities, rather than merely increasing all magnitudes. No observed future target is available on the deployed input path.

The core falsification is explicit: if the mixture arm does not beat the ordinary auxiliary and mixture-mean controls at matched overall risk, the full density/responsibility story is unsupported. If improvements occur only with a flexible same-record teacher or disappear under cross-fitting, investigate leakage/memorization before calling them signal. If full-gradient and stop-gradient versions differ, that is evidence about their optimization paths, not a proof of physical correctness. A defensible eventual contribution would be a carefully validated, causal EEW training formulation and its measured advantage; composite scores, mixture responsibilities, stop-gradient and future supervision themselves are established ideas.

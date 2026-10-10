# Chile next mechanism: test density-floor suppression before changing the head

10 October 2026. Research proposal only; no checkpoint, waveform or prediction arrays were inspected, no DEV/TEST outcomes were used, and no jobs or production-code changes were made. The current source-faithful run must finish unchanged. Source fingerprints and the proposed diagnostic gate are in the adjacent manifest/protocol files.

**Recommendation:** first measure whether the completed Chile model still makes badly underestimated large TRAIN events nearly gradient-silent because its training likelihood adds `1e-6`. Only if that mechanism is present, test a five-component **normalized Huber density** against both the existing floored Gaussian and the same Gaussian with the floor removed. This is a specific optimization/distribution hypothesis, not new rupture information or a claim of novel robust statistics. The mandatory proper-Gaussian control could make the proposed head unnecessary.

## What the present model actually observes and predicts

The current implementation is `work/repo/research/2026-10-09/phase3/{team_lm,train_team_lm}.py`; the requested `external_benchmarks` directory is not present. Its station inputs are ZNE velocity in m/s, station coordinates and continuous station availability. The 1/3/5-second deadlines are relative to the network's first P arrival: 600/800/1,000 samples including the preceding five seconds. Chile has no individual-station P picks. A station may therefore contribute pre-arrival noise, and a new method cannot introduce catalogue-arrival gating or source-distance inputs. Strict-prefix demeaning and amplitude normalization already exclude future samples. Original release preprocessing remains a separate causality limitation.

The encoder preserves log peak amplitude as well as waveform shape; six attention blocks aggregate stations jointly. It is **not** a product of independent station posteriors. Its five-Gaussian mixture already has unbounded upper support, despite nonnegative component means. Extending a categorical ceiling, adding a plain amplitude feature, or correcting supposed independent-station double counting would address the wrong model. These facts are verified in the local source and consistent with [TEAM-LM's pinned author source](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/models.py).

## The exact mechanism and its limits

The author's `mixture_density_loss`, lines 497–515, adds epsilon after summing the component densities. The port preserves that behavior using stable log-sum-exp and log-add-exp. For normalized mixture density p and epsilon e,

\[
 L_e=-\log(p+e),\qquad
 \nabla L_e=a\nabla(-\log p),\qquad a=\frac{p}{p+e}.
\]

At e=1e-6, `a < .1` exactly when `log(p) < -16.0127351353`. This attenuation affects **all output and backbone gradients from that observation**, before batch averaging/clipping. It is mathematical saturation caused by the additive floor, not floating-point underflow. For illustration only, a single Gaussian with standard deviation .2 and magnitude error 1.5 gives a≈1.22e-6; a real five-component prediction may instead retain substantial density through a broad component. No prevalence of suppression in real Chile predictions has yet been established.

This differs from **mixture responsibility collapse**. With Gaussian responsibility r_k, component-mean derivative is `a * r_k * (mu_k-y)/sigma_k²`. Proper responsibilities sum to one even if four components have almost none; the floor additionally suppresses the entire observation. Record both a and responsibility entropy/effective count. Small network gradients can also come from ReLU head Jacobians, optimizer state or global gradient clipping; density outputs alone cannot attribute those effects.

The floor may intentionally protect against noisy labels. Removing it can let extreme labels dominate, widen components, or harm common-event accuracy. A completed checkpoint can establish only **current TRAIN suppression**, not its historical causal role, generalization, or a guarantee that the lost gradient was useful. A null diagnostic rejects spending on this particular continuation mechanism; it does not prove that the floor never mattered earlier in training.

## One distribution modification, with the same parameter count

Use five symmetric Huber-density components, fixed delta=2, with unchanged logits, component means and predicted component standard deviations. Define

\[
 h_d(r)=\begin{cases}r^2/2,&|r|\le d\\d|r|-d^2/2,&|r|>d,\end{cases}\quad
 Z_d=\sqrt{2\pi}\operatorname{erf}(d/\sqrt2)+2e^{-d^2/2}/d,
\]
\[
 v_d=\frac{\sqrt{2\pi}\operatorname{erf}(d/\sqrt2)+4e^{-d^2/2}(1/d+1/d^3)}{Z_d},\quad
 f_d(y;\mu,\sigma)=\frac{\sqrt{v_d}}{\sigma Z_d}
 \exp\{-h_d(\sqrt{v_d}(y-\mu)/\sigma)\}.
\]

This parameterization has component mean mu and variance sigma². At delta=2, Z≈2.52791131 and v≈1.08030461. Thus loading the same Gaussian head weights preserves the whole mixture's initial mean and variance exactly, while changing higher-order shape. Use normalized mixture NLL with stable log-sum-exp and **no density floor**. It has a Gaussian center and exponential tails; its location score is bounded in standardized residual and does not return to zero for a large residual. The bound is proportional to 1/sigma, so this is not a uniform bound on network gradients. Keep the existing scale lower bound and global gradient clipping in all arms.

This could restore learning from underpredicted events without the proper Gaussian's quadratic residual penalty, while leaving the central density similar. It could instead merely widen distributions, harm point estimates, or encourage memorization of the only very large fitting event. Symmetric heavy tails are an optimization choice, **not an identified model of one-sided rupture growth**. No mean/median accuracy guarantee follows from the likelihood.

## Frozen TRAIN-only incidence gate, before any new fitting

The adjacent `diagnostic_protocol_v1.json` is the machine-readable proposal. Freeze the completed checkpoint/source hashes before execution. Use only the already pinned original-TRAIN fitting split: all MA≥5.5 fitting events, plus up to 1,024 events in each of MA<4 and 4≤MA<5.5 chosen by a fixed salted SHA256 event-ID ordering. Do not repeat oversampled events in this audit. Keep the current calibration partition untouched during this stage.

Evaluate deterministic, unblinded full available station sets at 1/3/5 seconds, with the existing strict prefix preprocessing. Save per-event identity, true MA, mixture parameters, proper log density, a, component responsibilities, mean/median errors and predicted standard deviation. Report every tail event and each horizon, including the bulk samples' inclusion fractions; the bulk sample is a diagnostic reference, not a population-performance estimate. No predictions need be generated for DEV/TEST.

**Investment gate:** at least four distinct MA≥5.5 fitting events must each have `a<.1` and mean underestimation exceeding .5 at **at least two** of the three deadlines. If fewer than four such events exist, stop this proposed continuation. This is a deliberately fixed practical threshold, not a significance test. The source split documentation implies only 20 fitting events above the threshold; verify membership from the pinned manifest rather than assuming that count. Report concentration by event so one earthquake cannot satisfy the gate through many station records or resampling repetitions.

On the same saved parameters, compute the analytic output gradients for floored Gaussian, proper Gaussian and the moment-matched Huber mixture. Verify the exact attenuation identity, finite densities/gradients, responsibility normalization, component moments, CDF limits and future-suffix/station-padding invariance. Do not interpret different Huber responsibilities as an isolated epsilon effect. A bounded implementation would make a single no-optimizer pass, at most 30 minutes, saving all outputs or marking the audit incomplete on timeout. It requires separate implementation/review/launch authorization; nothing is running now.

## Matched pilot if the mechanism gate passes

Three arms are essential: **A** existing Gaussian/floored NLL, **B** identical Gaussian/proper NLL (`epsilon=0`), **C** normalized moment-matched Huber mixture/proper NLL. Start all from the same completed checkpoint, reset optimizer identically, and use two fixed new optimization seeds. These are two continuation seeds, not two independently pretrained replications. Keep every other source convention: all original fitting events, magnitude resampling, author station blinding, author cutoffs −4 to +25 s, magnitude-label smoothing, batch size, station ordering, deterministic runtime, gradient clipping and input normalization. Do not change pretraining, add temporal teachers, weight tail labels differently, or multiply predictions across deadlines.

Proposed pilot budget is **six fixed event epochs per arm/seed**, Adam at 1e-5, no scheduler or validation selection, final epoch only. Realized sampling, cutoff, station and label-noise draws must match within seed. A common six-GPU-hour total cap bounds expenditure; measure TRAIN throughput before committing to the experiment and reject an infeasible budget rather than shorten selected arms after seeing scores. A timed-out comparison is incomplete. Fresh optimizer/learning rate are deliberate continuation choices shared by A; this is not a replacement of the full source-faithful baseline.

The untouched TRAIN calibration partition can gate **bulk** investment: for both posterior-mean and posterior-median decisions, at each deadline require C−A and C−B MAE and MedAE ≤+.005 magnitude units; also require no increase in calibration CRPS. Report paired-event uncertainty, proper NLL, threshold Brier scores, interval coverage, worst-5% errors and every seed. These are pilot point-estimate gates, not proven noninferiority. Its two MA≥5.5 events are descriptive only and cannot establish tail benefit or select delta. If any bulk/score gate fails, stop without searching delta or choosing a favorable seed/deadline.

If C only beats A, this is evidence for removing saturation, **not** evidence for the robust head. If B and C are comparable, prefer B's simpler known correction. If only uncertainty scores improve and high-M mean/median errors do not, the user's point-error objective remains unmet. Any eventual tail claim needs a separately preregistered locked comparison, adequate independent events, paired confidence intervals and a second dataset; this memo does not authorize opening TEST. Include a Gaussian-mixture **CRPS training** control before attributing a confirmatory benefit to this density family, because it is already an EEW alternative to likelihood optimization.

## Prior art and the defensible claim boundary

[Münchmeyer et al. (2021), *Earthquake magnitude and location estimation from real time seismic waveforms with a transformer network*](https://doi.org/10.1093/gji/ggab139), establishes the architecture/distribution baseline; the inspected author source establishes the precise floor. Bibliographic identity was reverified through the authors' GFZ repository. The web reader could not fetch the pinned GitHub blob on this pass, so its implementation evidence is the locally cached, hashed author file plus the port, not a freshly verified remote blob.

[Münchmeyer, Leser & Tilmann (2022), *A probabilistic view on rupture predictability: all earthquakes evolve similarly*](https://arxiv.org/html/2203.08622v1), already uses Gaussian-mixture magnitude distributions and CRPS, motivated by optimization with skewed distributions. Its Gaussian/GR discussion is a physical interpretation, not evidence that the code has an explicit GR component. Its STF/teleseismic results do not prove a local Chile impossibility theorem. This substantially narrows any claim about using distributions or heavy tails for EEW.

[Barron (2019), *A General and Adaptive Robust Loss Function*, §2](https://arxiv.org/html/1701.03077v10), explicitly constructs normalized robust densities and neural likelihood training. Huber penalties, non-redescending influence and normalized robust mixture components are established ingredients. No exact EEW Huber-head priority claim is made and no exhaustive priority search was performed. These primary arXiv full texts were verified in this pass; the CVF mirror returned HTTP403.

The possible contribution is narrower: **a documented failure mode of an existing early-warning density objective, with a controlled remedy that retains useful rare-event gradients and demonstrably protects bulk accuracy**. Unlike the rejected INSTANCE scalar-innovation, future-growth and revision pilots, the change directly trains the full multistation representation and can affect all three deadlines, including 1 s. That makes it a distinct experiment, not evidence that it will work. If the TRAIN incidence gate is negative, or the proper Gaussian explains the gain, the honest outcome is a baseline diagnosis/correction rather than a new foundational EEW method.

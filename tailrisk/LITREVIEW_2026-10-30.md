# Adversarial literature review of the novelty claims (30 Oct 2026)

Purpose: test the five claims behind NOVELTY.md / PAPER.md against prior work, looking for anything that
would let a reviewer say "this was already done". This extends NOVELTY.md (19–21 Oct); it does not repeat
its rows except where they need correcting.

**Method.** Web search of 2019–2026 literature (including 2025–2026 arXiv / ESSOAr / EarthArXiv), plus the
classical sources each claim leans on. Searched: ML EEW magnitude estimation; Bayesian EEW; saturation
studies; gain- and scale-equivariant networks; label and prior shift; product-of-experts and posterior
fusion; simulation-based inference; truncated regression; extrapolation beyond the training range.

**Verification tags** (on every reference):
- **[V]**: the relevant passage was read in the primary text during this review.
- **[A]**: only the abstract, metadata or a reliable secondary source was read.
- **[M]**: standard citation from memory; check equation and page numbers before citing.
- **[U]**: could not be verified; the detail comes from a search snippet.

Absence from this list is not proof of absence. Paywalled full texts (Wiley, Springer, ScienceDirect)
were often unreachable.

## Bottom line (details below)

| # | Claim | Verdict |
|---|---|---|
| 1 | Equivariant mixture likelihood × learned GR-tail prior factor kept at test | **Partially anticipated.** The κ = 1 core (exact log-amplitude equivariance of a predicted magnitude distribution, by construction, for EEW) is in Zhang, Zhang & Tian 2021 and Zhang & Zhang 2023 (arXiv v1). Not found: learned κ(s), a mixture sharing the shift, or a learned GR-tail factor kept at test. |
| 2 | Distance-marginalized form, distance a training label only | **Partially anticipated** by the Gutenberg algorithm (joint M–log R posterior from amplitudes, R marginalized; kNN, not neural, not equivariant). No neural EEW paper marginalizes a distance latent. |
| 3 | Proposition 1 (GR ⇒ Bayes posterior shift-equivariant despite unknown nuisances) | **Partially anticipated.** The algebra is classical (Eddington/Malmquist, Tinti–Mulargia, Tweedie). "Invariant joint ⇒ equivariant conditional" is a general principle. The EEW statement with arbitrary nuisances and its use to justify a neural head were not found. Present it as a short proposition with citations. |
| 4 | Proposition 2 (tail slope not identified) and fusion double counting | **Fusion fix anticipated** (textbook; already applied to deep posteriors: ProbEn 2022, MVAE 2018, Geffner et al. 2023). **EEW diagnosis not found**: the field's own Bayesian algorithm (Gutenberg) does the naive product. **Tilt non-identifiability with its fusion consequence not found**, but it is a short corollary of textbook algebra. |
| 5 | Capped training: truncate prior during training, untruncated GR tail at test (Proposition 3) | **Training mechanism anticipated** (truncated-likelihood regression, Ilyas et al. 2020; proposal-prior correction and truncated priors in simulation-based inference). **Extrapolation design and experiment for neural magnitude estimation not found.** |

## Corrections and additions NOVELTY.md / PAPER.md need

1. **Cite Zhang, Zhang & Tian 2021 [1] and the arXiv versions of Zhang & Zhang [2] as the κ = 1 precedent.**
   - [1] predicts a 1-D distribution over M_r = M − log A_max from max-normalized waveforms and adds log A_max back. Their stated aim is "equalizing the labeled magnitude range between large and small earthquakes" [V].
   - The arXiv versions of [2] do the same per station: "a tenfold increase in amplitude correspond[s] to a one-unit increase in magnitude … must add the logarithm of the waveform amplitude" [V].
   - The published 2024 version replaced this with the log normalization factor as a fifth input channel [V]. NOVELTY.md describes only the published version.
   - Add a **κ ≡ 1 ablation** (the Zhang construction on the same trunk). Without it, a reviewer can argue the learned κ(s) adds nothing.
   - For ML-labelled catalogues κ = 1 is the physically expected slope (cf. the Emilia limitation in README), so the ablation may win there.
2. **Correct the description of the Gutenberg algorithm.**
   - NOVELTY.md says it "multiplies hand-built per-station likelihoods and applies the GR prior once". That is wrong.
   - Meier et al. 2015 [16] state that their kNN-based per-station densities are posteriors: the GR × R prior is "an integral part of the estimation procedure … directly returns the desired posterior". They then combine stations by "multiplying single-station marginal probabilities" (their eq. 5), never dividing the prior out [V].
   - Yin 2018 [18] then treats that output as a "likelihood", multiplies it across stations and adds an ETAS prior on top [V].
   - This strengthens the fusion story: the study can say it corrects a published EEW practice. The Virtual Seismologist [17] does apply its prior once [V].
3. **Credit the fusion fix.** "Divide each posterior by the training prior before multiplying" is Kittler et al. 1998 [32], the Bayesian committee machine [33], hybrid HMM/ANN "scaled likelihoods" [37], occupancy grids [36], and for deep networks ProbEn [38], MVAE [39] and Geffner et al. 2023 [40].
   - ProbEn already states that averaging "double counts class prior" [V via search agent].
   - Counter-evidence to cite honestly: ProbEn found a uniform prior worked better than the class-count prior. Deisenroth & Ng [34] show the prior-division (BCM) fix "breaks" with weak experts.
   - So "the histogram rule is the robust fix" should be worded as an empirical, catalogue-specific finding.
4. **Cite the classical algebra behind Propositions 1 and 2.** These are the Eddington/Malmquist shift under exponential counts [25, 26], Tinti & Mulargia 1985 [27], Tweedie's formula [28] and exponential tilting [31]. A seismology reviewer will know Tinti–Mulargia.
5. **Credit the mechanism of Proposition 3.**
   - Training under a truncated label factor is the truncated-likelihood objective. Ilyas et al. 2020 [57] use it on a deep regressor trained on label-truncated data.
   - Swapping the training prior at test time is the SNPE-A / APT proposal correction [59, 60].
   - TSNPE [61] trains under a truncated prior but requires the truncation to cover the posterior support. That is exactly the gap that equivariance fills.
6. **Prepare for three reviewer objections to the extrapolation claim.**
   - (a) Xu et al. 2021 [62]: ReLU networks extrapolate *linearly* along rays, so "free networks saturate" needs the mechanism shown (bounded or mixture heads, the training-range prior baked into the posterior), not just asserted.
   - (b) Physics: early P amplitude saturates above a window-dependent magnitude (Trugman et al. 2019 [23]; Meier et al. 2015 [16]; Meier, Ampuero & Heaton 2017 [24]). Above that magnitude assumption 2 of Proposition 1 fails, so equivariance can extrapolate only up to the physical saturation point. Compare the gains with the Trugman break.
   - (c) Data-side alternatives: amplitude-scaling augmentation with label shift (Kuang et al. 2021 [7], detail [U]; the study's `cat_aug`), synthetic large events (M-LARGE [67]), and transfer learning (TEAM-LM [4]).

---

## Claim 1 — scale-equivariant mixture likelihood × learned global prior factor kept at test time

Claim: p(m|x) ∝ L_θ(m|A,s)·e^φ(m), with mixture locations κ(s)(A−A₀)+g_k(s), A = log RMS in physical units,
and φ free below completeness and GR-linear above, kept at test.

| Prior work | What it does | How the claim differs | Closeness |
|---|---|---|---|
| Zhang, Zhang & Tian 2021, GRL [1] [V] | 12-station FCN on waveforms normalized by the network-wide max. Outputs a 1-D distribution over **M_r = M − log A_max**; M = M_r + log A_max. Exactly translation-equivariant in log amplitude by construction, κ ≡ 1. Motivated by large/small-event label imbalance. No prior; no cap test. | κ fixed at 1, not learned or s-dependent. One global peak amplitude, not per-station RMS. Categorical-style 1-D output, not a mixture. No prior factor, so a completeness cliff cannot be represented. No Bayesian justification. | **High** |
| Zhang & Zhang, arXiv 2312.15218 v1 (2023) → *Commun. Earth Environ.* 2024 [2] [V] | arXiv: per-station network with epicentral distance as an input. Label = ML − log A_max ("tenfold amplitude → +1 magnitude"). 1-D Gaussian-labelled output. Published version: log normalization factor as a free 5th input channel, output is the magnitude itself. Event magnitude = mean over stations. | arXiv version: same differences as [1]. Published version: non-equivariant (NOVELTY's `mix_nll`/`cat_ce` analogue). The reason for the switch is not stated. | **High** (arXiv), medium (published) |
| P. Zhang, X. Zhang & Tian 2026, *Appl. Comput. Geosci.* [3] [U] | Per abstract snippets: single-station "pseudo-normalization" that keeps the log normalization factor "as a critical physical constraint". Predicts the magnitude contribution excluding absolute amplitude, jointly with epicentral distance. Gaussian outputs. **Trained on INSTANCE.** | Probably κ = 1 again, with distance a co-output rather than a marginalized latent. **Full text not reached: check before submission.** It is in-domain, recent and on the same dataset. | **High (unverified)** |
| TEAM-LM, Münchmeyer et al. 2021, GJI [4] [V] | Peak-normalized waveforms + log peak amplitude as a free input; 5-component Gaussian mixture head; transformer over stations. Blames large-event underestimation on the GR training distribution and calls for "physics derived constraints". | No equivariance, no prior factor. This is the study's `mix_nll` baseline. | Medium-high (baseline) |
| McBrearty & Beroza 2022, ICIP [6] [V] | Pick-based GNN. Input features place each station's log amplitude on a magnitude axis through a calibrated linear log A–M scale, so a uniform amplitude shift translates the feature pattern. Uniform synthetic magnitude prior. | Approximate, feature-level structure with a fixed slope, not an exact output constraint. No prior factor. | Medium |
| Classical EEW magnitude formulas, M = a log Pd + b log R + c (Wu & Zhao 2006; Kuyuk & Allen 2013) [21] [M]; Virtual Seismologist envelope laws, linear in M [17] [V] | Parametric magnitude estimates, exactly linear in log amplitude with a fixed slope. | The study is a learned, waveform-conditioned generalization (slope and offsets depend on s; a mixture). Say so explicitly. | Medium (conceptual) |
| Normalize-then-rescale predictive distributions: DeepAR [53] [V via agent], RevIN, Chronos; units-equivariant learning (Villar et al. 2023) [54] [A]; learned canonicalization (Kaba et al. 2023) [55] [A] | Exact scale equivariance of a predictive distribution or point output by canonicalizing with a norm; output exponent fixed by units. | Fixed exponent and label in the same units as the input. Here the label is a different quantity, and the shift κ(s)·log c depends on the orbit invariant s, which is non-standard in canonicalization theory. | Medium |
| Bias-free / normalization-equivariant networks (Mohan et al. 2020; Herbreteau et al. 2023) [56] [A] | Exact homogeneity f(cx) = c f(x) for denoisers. | Point outputs in signal space, κ = 1. | Low |
| Label-prior factors that are **removed**: logit adjustment [47], balanced softmax [48], LADE [49], Balanced MSE [50], Prior2Posterior [45] [A] | Posterior ∝ model × known or estimated label prior, removed for a balanced target. | The target here is the natural distribution and the factor is learned and kept (as NOVELTY says). Reviewer objection to pre-empt: a softmax or mixture bias is already a learned label log-prior kept at test. | Medium |
| Prior factor **kept**, but fixed: Posterior Network (class counts × learned density) [52] [A]; MVAE "prior expert" [39] [A]; Gutenberg algorithm (natural-distribution data embed GR × R) [16] [V] | A known or implicit prior multiplied with a learned density at test time. | None learns a GR-shaped factor jointly with a neural likelihood or designs it to preserve equivariance. | Medium |
| Training-prior manipulation in neural EEW: CREIME (resample to uniform, no test correction) [9] [V via agent]; Kuang et al. 2021 (evenly distributed augmented magnitudes) [7] [U]; Käufl et al. (MDN posterior depends on prior-sample density) [13] [A] | Show the field knows the training label distribution shapes the posterior. | None models the prior explicitly as a factor. | Low-medium |

**Verdict: partially anticipated.**
- **Anticipated:** an exactly log-amplitude-equivariant *predicted magnitude distribution* for EEW, by construction and motivated by large-event imbalance (κ = 1: [1], [2] arXiv). In parametric form, any linear log-amplitude magnitude formula is equivariant too.
- **Not found:**
  - a learned, waveform-dependent slope κ(s);
  - a mixture whose components share the equivariant shift;
  - a learned global log-prior that is free below completeness and GR-linear above, kept at test time and shaped so it preserves equivariance;
  - the controlled evidence that each part is needed.
- **Positioning:** Under Proposition 1 with a pure GR prior, the Zhang construction is already Bayes-consistent when κ = 1. What it cannot represent is (i) κ ≠ 1 (Mw-like labels) and (ii) the completeness cliff, which THEORY.md shows breaks equivariance. These two are the defensible increments, and the κ ≡ 1 ablation should demonstrate them.

## Claim 2 — distance-marginalized form, distance a training label only

Claim: p(m|x) ∝ Σ_r p(r|s)·N(m; κ(s)(A−A₀)+G_r(s), σ_r²)·e^φ(m), with r a log-distance bin used only as a
training label.

| Prior work | What it does | How the claim differs | Closeness |
|---|---|---|---|
| Gutenberg algorithm, Meier, Heaton & Clinton 2015, BSSA [16] [V] | From filter-bank log amplitudes, kNN (n = 30) finds similar training records and fits a bivariate Gaussian over (M, log₁₀R). This is the joint posterior with prior ∝ R·10^(−bM), embedded via the natural data distribution. Magnitude marginal by integrating out R. Distance is a training label only. | Same probabilistic structure: a joint (M, R) posterior from amplitudes with R marginalized. But nonparametric kNN, not a neural network. Not equivariant: kNN cannot exceed the largest training amplitudes and saturates by construction. Prior implicit, not a learned factor. | **High** (structure) |
| Lomax, Michelini & Jozinović 2019, SRL [8] [V via agent] | Single-station CNN with separate softmax heads for binned distance, magnitude, depth and azimuth; stream maximum appended as amplitude input. | Distance and magnitude are separate outputs; no mixture over distance hypotheses; no marginalization, equivariance or prior. | Medium |
| Mousavi & Beroza 2020 (TGRS) [11] [V via agent]; Yoon et al. 2023 [15] [A]; Ristea & Radoi [U]; P. Zhang et al. 2026 [3] [U] | Distance as a predicted output (multi-task), sometimes with uncertainty. | Co-output, not a latent that structures the magnitude likelihood. | Low-medium |
| Zhang & Zhang 2024 [2]; Hou et al. 2024 [14] [A]; Kuyuk–Allen-type relations [21] | Distance (catalogue or arrival-time differences) as an input. | The claim needs no distance at inference. | Low |
| Learning using privileged information (Vapnik & Vashist 2009) [68] [M]; supervised mixture-of-experts | General ML idea: use a variable available only at training time to shape the model. | The general idea is known. The specific use (an equivariant per-distance amplitude law mixed by p(r|s), jointly with a GR-factorized prior) was not found. | Low-medium |

**Verdict: partially anticipated.**
- The joint magnitude–distance posterior from single-station amplitudes, with distance used only as a training label and marginalized at inference, is the Gutenberg algorithm's structure (2015).
- Not found: a neural, exactly equivariant per-distance likelihood mixed over learned distance hypotheses and combined with a learned GR-tail prior.
- Not found in any neural EEW paper: distance marginalized as a latent (it is always an input or a co-output).
- NOVELTY.md already names the Gutenberg algorithm here. It should add that the kNN likelihood is the archetypal *non-extrapolating* estimator, which sharpens the contrast.

## Claim 3 — Proposition 1: under GR, a log-linear amplitude law and self-similar shape, the Bayes posterior is shift-equivariant in A even with unknown nuisances

| Prior work | What it does | How the claim differs | Closeness |
|---|---|---|---|
| Eddington 1913 [25] [A]; Malmquist 1922 [26] [M] | For exponentially falling counts and Gaussian log-errors, the correction from observed to true value is a **constant** independent of the observed value. Malmquist's homogeneous-density case (unknown distance, exponential number counts) gives a constant −1.38σ² offset in absolute magnitude. | Same mathematics: an exponential prior turns a Gaussian error into a constant shift, and unknown distance does not break this. Different field and estimand; no neural model. | **High** (algebra) |
| Tinti & Mulargia 1985, BSSA [27] [A]; EPRI 1988 / Kagan [29] [A]; Rhoades 1996 [A] | Gaussian magnitude error + GR: b unbiased, a biased, and a constant magnitude shift of order βσ² (β = b ln 10). | The seismology instance of the same algebra, without amplitude, nuisances or equivariance framing. | **High** (algebra) |
| Efron 2011, Tweedie's formula [28] [A] | E[μ | z] = z + σ² d/dz log f(z). For an exponential marginal the posterior-mean shift is constant. | General empirical-Bayes form of the same fact. | Medium-high |
| Bloem-Reddy & Teh 2020, JMLR [30] [M] | Equivariant conditional distributions from (jointly) invariant models (compact groups). | Proposition 1 is an instance: GR + log-linear amplitude + M-independent shape makes p(A, s, M) quasi-invariant under (A, M) ↦ (A+κδ, M+δ), so the Bayes conditional is equivariant. The group here is non-compact and the joint invariant only up to a constant, but the three-line proof stands. | Medium |
| Meier et al. 2015 [16] [V] | Qualitative: a GR prior pulls the most probable magnitude below the GMPE-implied value; the distance prior pushes the other way. | No equivariance statement; no amplitude-independence of the shift. | Medium |
| Cua 2005 / Virtual Seismologist [17] [V]; Lancieri & Zollo 2008 [20] [A]; Applied Sciences 2022 Bayesian EEW with GR prior [22] [A] | Gaussian log-amplitude likelihood × GR prior in EEW, so the posterior is a shifted Gaussian. | No nuisance-marginalization argument or equivariance claim; used for estimation, not to justify a network architecture. | Medium |
| Trugman et al. 2019 [23] [A]; Meier, Ampuero & Heaton 2017 [24] [A] | Early P amplitude stops scaling with final M above a window-length-dependent magnitude; rupture onsets look universal. | Not prior art but a **challenge to assumption 2** at short windows for large M. The proposition holds where the assumptions hold; the study should state the window-dependent magnitude above which they fail. | n/a (caveat) |

**Verdict: partially anticipated.**
- **Classical:** that an exponential (GR) prior turns Gaussian log-error into a *constant*, amplitude-independent shift, including with unknown distance (Malmquist). So is the fact that an invariant joint gives an equivariant posterior.
- **Not found:** the explicit EEW statement with arbitrary unknown nuisances (distance, site, path, radiation); the companion result that a completeness cliff breaks equivariance; and the use of both to *design* a neural head.
- Present Proposition 1 as a short, cited proposition. Its value is the architectural consequence, not the algebra.

## Claim 4 — Proposition 2 (prior-factor tail slope not identified from single-station data) and multi-station fusion

Claim:
- An exponential tilt of a Gaussian mixture is a shifted mixture, so the tail slope of the prior factor is not identified from single-station data.
- The product of per-station neural posteriors counts the training prior once per station, so the fused large-event estimate does not improve as stations arrive unless that prior is divided out.

| Prior work | What it does | How the claim differs | Closeness |
|---|---|---|---|
| **Fusion principle, classical:** Kittler et al. 1998 [32] [M]; Bayesian committee machine, Tresp 2000 [33] [A]; Deisenroth & Ng 2015 rBCM [34] [V via agent]; consensus Monte Carlo [35] [A]; occupancy grids, subtract l₀ per update [36] [M]; hybrid HMM/ANN "scaled likelihoods", posteriors ÷ training-label frequencies [37] [M]; interim-prior division in hierarchical inference (Hogg et al. 2010) [43] [A] | Product rule P(ω)^−(R−1) Π P(ω|x_i). Dividing by the training-label frequencies is standard for neural posteriors in speech. rBCM calls the M−1 prior divisions "the decisive difference" and shows the fix degrades with weak experts. | Textbook. The study's rules ("prior once", "divide by histogram") are these. | **High** (anticipates the fix) |
| **Fusion of deep posteriors:** ProbEn, Chen et al. 2022 ECCV [38] [V via agent]; MVAE, Wu & Goodman 2018 [39] [A]; Geffner, Papamakarios & Mnih 2023 ICML [40] [V]; Linhart et al. 2024 [41] [V via agent]; discriminative Kalman filter, Burkhart et al. 2020 [42] [V via agent]; Papamakarios & Murray 2016 [59] [V] | ProbEn: Π p(y|x_m)/p(y)^(M−1) with the class-count prior; "average score fusion … double counts class prior" (but a uniform prior worked better). MVAE: unimodal posteriors parameterized as q̃(z|x_i)·p(z) so the prior is counted once, nearly the L·e^φ design with a fixed prior. Geffner eq. 4: p(θ|x₁..x_n) ∝ p(θ)^(1−n) Π_j p(θ|x_j). Linhart: performance degrades as n grows (score error, not prior tilt). DKF: p(z|x)/p(z) from a learned regressor. Papamakarios & Murray: an MDN trained under prior p̃ learns p̃/p · posterior; divided out analytically for Gaussian mixtures. | All already apply prior division to neural posteriors. None is in EEW. None has a *learned* prior factor whose slope is unidentified, or the rare-large-label regime. | **High** (fix and "averaging fails") |
| **Seismology / EEW:** Gutenberg algorithm [16] [V]; Yin 2018 thesis [18] [V]; Zhang & Zhang 2024 [2] [V]; ShakeAlert prototype (Minson et al. 2017) [19] [V]; Virtual Seismologist [17] [V]; TEAM / TEAM-LM [4, 5] [V] | Gutenberg multiplies posteriors that embed the GR prior (prior counted k times) and reports −0.1 to −0.35 bias with few stations. Yin multiplies the same outputs as "likelihoods" and adds an ETAS prior. Zhang & Zhang and the ShakeAlert prototype average station estimates. VS multiplies physics likelihoods and applies the prior once. TEAM-LM fuses inside a transformer. | **No EEW paper found that identifies prior double counting or divides it out.** The field's own Bayesian algorithm makes the error the study diagnoses. | High (as the target the study corrects) |
| **Tilt algebra:** exponential tilting / Esscher [31] [M]; Tinti & Mulargia [27]; Tweedie [28]; Balanced MSE's closed-form GMM integrals [50] [A]; Papamakarios & Murray App. C [59] [V] | Gaussian (mixture) × exp(βm) is a shifted, reweighted Gaussian (mixture). | Proposition 2's identity is textbook. | High (algebra only) |
| **Identifiability:** Maity et al. 2023 ICLR [44] [A]; Allman, Matias & Rhodes 2009 [46] [A]; Prior2Posterior 2025 [45] [A]; hybrid-ASR tuned prior-scale exponents [37] | Maity: non-identifiability of a different (label-switching) kind of exponential tilt. Allman: latent structure needs ≥3 conditionally independent views. Prior2Posterior: a trained model's effective prior differs from the histogram. ASR practitioners tune the prior exponent. | None states that the slope of a learned prior factor is unidentified from single-sensor training, or derives the residual (k−1)γ tilt under fusion. | Low-medium |

**Verdict.**
- **Fusion fix: anticipated.** Dividing out the prior each posterior was trained under is textbook. ProbEn and Geffner/Linhart already apply it to deep posteriors, and ProbEn already reports that averaging double counts the prior.
- **EEW diagnosis: not found.** No EEW work identifies the problem, and the closest EEW precedent (Gutenberg algorithm, then Yin 2018) commits it. The empirical evidence on three catalogues is new.
- **Proposition 2: algebra textbook, consequence not found.** The non-identifiability statement for a learned prior factor, and its fusion consequence, were not found. Frame it as a corollary.

Two cautions:
- (i) ProbEn and rBCM are counter-evidence to "histogram division is *the* robust fix". The README already says the right prior is catalogue- and head-specific; keep that wording.
- (ii) "Does not improve as stations arrive" has an elementary explanation worth adding (my derivation, not from the literature):
  - With Gaussian per-station likelihoods of width σ and π ∝ e^(−βm), the naive product π^k Π L_i has its mean shifted by −βσ² **for every k**, while its width shrinks as σ/√k.
  - The correctly fused posterior has shift −βσ²/k.
  - So the naive product's prior bias does not decay and its z-score grows like √k.
  - A learned factor with slope error γ leaves a shift (k−1)γσ²/k that saturates at γσ².
  - So "grows with k" should be phrased in terms of the exponent or z-score, not the absolute shift.

## Claim 5 — capped-training extrapolation (THEORY.md Proposition 3)

Claim:
- Train only on M < C, with the prior factor truncated (× 1[M < C]) during training.
- At test time use the untruncated GR tail.
- The equivariant likelihood carries what it learned below C to M ≥ C; a free network cannot.

| Prior work | What it does | How the claim differs | Closeness |
|---|---|---|---|
| Ilyas, Zampetakis & Daskalakis 2020, AISTATS [57] [V via agent] | SGD on the truncated log-likelihood for samples truncated on the dependent variable, including a ResNet-50 regressor trained only on labels in [0°, 180°]. | The training objective of Proposition 3 *is* this truncated likelihood. Differences: homoscedastic Gaussian model, no exponential prior tail, no equivariance, evaluation near the truncation boundary rather than far above it. | **High** (mechanism) |
| Truncated-statistics theory: Daskalakis et al. 2018–2021, including truncated regression (COLT 2019) and extrapolation of truncated densities (COLT 2021) [58] [A] | In parametric (linear or polynomial log-density) models, extrapolation beyond the truncation set follows from the parametric form. | The study is the nonlinear analogue, with structure supplied by exact equivariance plus an exponential tail. | Medium-high |
| Simulation-based inference: SNPE-A (Papamakarios & Murray 2016) [59] [V]; APT (Greenberg et al. 2019) [60] [A]; TSNPE (Deistler et al. 2022) [61] [A] | Train a neural posterior under a proposal or truncated prior, then correct to the true prior. TSNPE uses the prior truncated to a region **and requires the truncation to contain the posterior support**. | Same "truncated prior in training, true prior at test" swap. The difference is extrapolating outside the training-prior support. Label-shift theory likewise assumes target labels lie inside the source support (Lipton et al. 2018 [51]). | Medium-high |
| Balanced MSE [50], logit adjustment [47] [A] | Keep the label-prior factor in training, swap at test. | Overlapping support assumed; no extrapolation. | Medium-low |
| TEAM-LM [4] [V]; TEAM [5] [V via agent] | Uncontrolled extrapolation. Italy's test set holds a larger event than training; magnitude saturates near M5.5 (Italy) and M6.0 (Chile). Transfer learning removes the Italy saturation. TEAM extrapolates PGA above the training maximum. | Evidence that free heads saturate, but no controlled cap and no parametric tail. Cite as motivation. | Medium |
| Physics-structured extrapolation in ground-motion ML: Kubo et al. 2020 (ML on GMPE residuals) [64] [V via agent]; Chen et al. 2023 PISL (train R_JB ≥ 30 km, test near field) [65] [A]; Okazaki et al. 2021 (monotonic network) [A] | Delegate extrapolation to a parametric physical law. PISL runs a controlled cap test on *distance*. | The cap is on an input, not the label. No predictive distribution, no prior truncation. | Medium |
| Data-side routes: Kuang et al. 2021 amplitude-scaled augmentation [7] [U]; M-LARGE synthetic large ruptures [67] [A]; Zhang & Zhang 2024 oversampling of M > 6 [2] [V] | Fill the large-M range with data instead of structure. | Alternatives to compare against (`cat_aug` covers the first). | Medium-low |
| General extrapolation: Xu et al. 2021 ICLR [62] [A]; Netanyahu et al. 2023 (train-low / test-high regression benchmarks) [63] [A]; Pasche & Engelke 2024 (neural GPD tails) [66] [A]; Polyakov 2023 (homogeneous networks for "global extrapolation from local data") [69] [A] | ReLU MLPs extrapolate linearly along rays. A train-low/test-high protocol already exists. Parametric tails extrapolate a conditional distribution. Symmetry is used to extrapolate. | The "symmetry ⇒ extrapolation" idea and the protocol exist in general. Their combination for a label-shifted predictive distribution with a GR prior tail was not found. **Xu et al. is a counter-argument**: a free network fed log A need not saturate, so the saturation mechanism must be shown. | Medium |
| Trugman et al. 2019 [23]; Meier et al. 2015 [16]; Meier, Ampuero & Heaton 2017 [24] | Physical saturation of early-window amplitudes above a window-dependent magnitude. | Bounds how far any amplitude-based extrapolation is physically valid (THEORY.md already notes this qualitatively). | n/a (caveat) |

**Verdict: mechanism anticipated, design and experiment not found.**
- **Anticipated:** training with a truncated label factor and swapping the prior at test (truncated regression; SNPE/TSNPE); the train-low/test-high protocol (materials and molecules); extrapolation via parametric or symmetric structure (truncated-density theory, homogeneous networks, GMPE hybrids).
- **Not found:** any neural magnitude or ground-motion paper running a controlled train-below-cap / test-above-cap experiment with an exactly equivariant likelihood and an untruncated GR tail.
- **Not found:** the observation that a factorized posterior can make the prior swap at all, whereas a free posterior "has learned P(M ≥ C | x) = 0".
- **Needed to make the claim robust:**
  - the κ ≡ 1 head;
  - an amplitude-augmentation baseline;
  - a free head fed log A (to answer Xu et al.);
  - a statement of the window-dependent physical saturation limit.

---

## Overall verdict

The study's individual ingredients nearly all have precedents:
- an exactly log-amplitude-equivariant magnitude distribution with κ = 1 (Zhang, Zhang & Tian 2021; Zhang & Zhang 2023 arXiv);
- a joint magnitude–distance posterior marginalized over distance (Gutenberg algorithm 2015);
- the constant GR-induced shift (Eddington, Malmquist, Tinti & Mulargia);
- dividing the training prior out of fused posteriors (classifier combination, BCM, hybrid ASR, and for deep networks ProbEn, MVAE and Geffner et al.);
- training on a truncated label range (Ilyas et al. 2020; TSNPE).

None of these works combines them, and several pieces were not found anywhere:
- **a learned, waveform-dependent slope κ(s)** inside a mixture whose components share the shift;
- **a learned GR-tail prior factor kept at test time** and chosen to preserve equivariance below and above completeness;
- **the non-identifiability of that factor's slope** and its consequence for multi-station fusion;
- **the diagnosis that EEW posterior fusion double counts the prior.** The field's own Bayesian algorithm does this;
- **a controlled capped-training extrapolation test** for neural magnitude estimation.

A reviewer is most likely to cite Zhang, Zhang & Tian 2021 against claim 1 and the classifier-combination / deep-fusion literature against claim 4. Neither makes the study redundant. Both must be cited, and claim 1 needs the κ ≡ 1 ablation to show the learned slope matters. The propositions are correct but elementary; present them as short, cited results whose value is the design consequences, not as new theory. The strongest novelty claims are:
- (a) the equivariant-head-plus-learned-prior design with its controlled evidence on three catalogues;
- (b) the EEW fusion diagnosis and fix;
- (c) the capped extrapolation experiment, if it shows equivariant heads tracking events above the cap up to the physical saturation limit.

## Not verified (check before submission)

- P. Zhang, X. Zhang & Tian 2026 [3]: full text unreachable (ScienceDirect and SSRN returned 403 or redirects). It is single-station, on INSTANCE, with a log-amplitude "physical constraint". **Highest-priority check.**
- Kuang, Yuan & Zhang 2021 [7]: whether the augmentation rescales amplitudes with a label shift (Richter scaling to M1–7).
- Thapa et al. 2026, *Bull. Earthq. Eng.* (doi:10.1007/s10518-026-02403-1) [U]: a "physics-informed" network plus Bayesian MCMC for single-station magnitude; which prior its MCMC uses is unknown.
- Hou et al. 2024 [14]; Ristea & Radoi; "DHLnet" (no paper of that name found); "augmentation-induced homogeneity (2025)" cited in NOVELTY.md (not located; NOVELTY should give the full reference or drop it).
- Items tagged [M] below: confirm equation and page numbers.

## References

ML / deep-learning EEW
1. Zhang, X., Zhang, M., Tian, X. (2021). Real-time earthquake early warning with deep learning: application to the 2016 M 6.0 Central Apennines, Italy earthquake. *GRL* 48, e2020GL089394. https://doi.org/10.1029/2020GL089394 ; https://arxiv.org/abs/2006.01332 [V]
2. Zhang, X., Zhang, M. (2023/2024). Generalized neural networks for real-time earthquake early warning (arXiv v1) / Universal neural networks for real-time earthquake early warning trained with generalized earthquakes. *Commun. Earth Environ.* 5. https://arxiv.org/abs/2312.15218 ; https://doi.org/10.1038/s43247-024-01718-8 ; https://pmc.ncbi.nlm.nih.gov/articles/PMC11488472/ [V]
3. Zhang, P., Zhang, X., Tian, X. (2026). An end-to-end deep learning approach for epicentral distance and magnitude determination from single station waveforms. *Applied Computing and Geosciences*. https://doi.org/10.1016/j.acags.2026.100356 [U]
4. Münchmeyer, J., Bindi, D., Leser, U., Tilmann, F. (2021). Earthquake magnitude and location estimation from real time seismic waveforms with a transformer network. *GJI* 226(2), 1086–1104. https://doi.org/10.1093/gji/ggab139 ; https://arxiv.org/abs/2101.02010 [V]
5. Münchmeyer, J., Bindi, D., Leser, U., Tilmann, F. (2021). The transformer earthquake alerting model. *GJI* 225(1), 646–656. https://doi.org/10.1093/gji/ggaa609 [V via agent]
6. McBrearty, I. W., Beroza, G. C. (2022). Earthquake location and magnitude estimation with graph neural networks. *IEEE ICIP*. https://arxiv.org/abs/2203.05144 [V via agent]
7. Kuang, W., Yuan, C., Zhang, J. (2021). Network-based earthquake magnitude determination via deep learning. *SRL* 92(4), 2245–2254. https://doi.org/10.1785/0220200317 [A; augmentation U]
8. Lomax, A., Michelini, A., Jozinović, D. (2019). An investigation of rapid earthquake characterization using single-station waveforms and a convolutional neural network. *SRL* 90(2A), 517–529. https://doi.org/10.1785/0220180311 [V via agent]
9. Chakraborty, M., et al. (2022). CREIME — a convolutional recurrent model for earthquake identification and magnitude estimation. *JGR Solid Earth* 127, e2022JB024595. https://doi.org/10.1029/2022JB024595 [V via agent]
10. Mousavi, S. M., Beroza, G. C. (2020). A machine-learning approach for earthquake magnitude estimation. *GRL* 47, e2019GL085976. https://doi.org/10.1029/2019GL085976 [V via agent]
11. Mousavi, S. M., Beroza, G. C. (2020). Bayesian-deep-learning estimation of earthquake location from single-station observations. *IEEE TGRS*. https://doi.org/10.1109/TGRS.2020.2988770 [V via agent]
12. Dybing, S. N., Yeck, W. L., Cole, H. M., Melgar, D. (2024). Rapid estimation of single-station earthquake magnitudes with machine learning on a global scale. *BSSA* 114(3), 1523–1538. https://doi.org/10.1785/0120230171 [A]
13. Käufl, P., Valentine, A. P., Trampert, J. (2016). Probabilistic point source inversion of strong-motion data in 3-D media using pattern recognition: a case study for the 2008 Mw 5.4 Chino Hills earthquake. *GRL*. https://doi.org/10.1002/2016GL069887 [A]
14. Hou, B., Zhou, Y., Li, S., Wei, Y., Song, J. (2024). Real-time earthquake magnitude estimation via a deep learning network based on waveform and text mixed modal. *Earth Planets Space* 76:58. https://doi.org/10.1186/s40623-024-02005-8 [A]
15. Yoon, D., et al. (2023). Estimation of magnitude and epicentral distance from seismic waves using deeper CRNN. *IEEE GRSL*. https://doi.org/10.1109/LGRS.2023.3234299 [A]

Bayesian and classical EEW, saturation
16. Meier, M.-A., Heaton, T., Clinton, J. (2015). The Gutenberg algorithm: evolutionary Bayesian magnitude estimates for earthquake early warning with a filter bank. *BSSA* 105(5), 2774–2786. https://doi.org/10.1785/0120150098 ; https://authors.library.caltech.edu/records/dwtkf-yg519 [V]
17. Cua, G. (2005). Creating the Virtual Seismologist (Caltech PhD thesis), https://thesis.library.caltech.edu/572/ ; Cua, G., Heaton, T. (2007), The Virtual Seismologist method, in *Earthquake Early Warning Systems*, Springer, https://doi.org/10.1007/978-3-540-72241-0_7 ; Cua, G., Fischer, M., Heaton, T., Wiemer, S. (2009). *SRL* 80(5), 740–747. https://doi.org/10.1785/gssrl.80.5.740 [V for 2009]
18. Yin, L. (2018). Reducing latencies in earthquake early warning. Caltech PhD thesis, ch. 4. https://thesis.library.caltech.edu/10451/ [V]
19. Minson, S. E., Wu, S., Beck, J. L., Heaton, T. H. (2017). Combining multiple earthquake models in real time for earthquake early warning. *BSSA* 107(4), 1868–1882. https://doi.org/10.1785/0120160331 [V]
20. Lancieri, M., Zollo, A. (2008). A Bayesian approach to the real-time estimation of magnitude from the early P and S wave displacement peaks. *JGR* 113, B12302. https://doi.org/10.1029/2007JB005386 [A]
21. Wu, Y.-M., Zhao, L. (2006). Magnitude estimation using the first three seconds P-wave amplitude in earthquake early warning. *GRL* 33, L16312. https://doi.org/10.1029/2006GL026871 ; Kuyuk, H. S., Allen, R. M. (2013). A global approach to provide magnitude estimates for earthquake early warning alerts. *GRL* 40. https://doi.org/10.1002/2013GL058580 [M]
22. Bayesian earthquake early warning with a Gutenberg–Richter prior (KiK-net, first 3 s) (2022). *Applied Sciences* 12, 12849. https://doi.org/10.3390/app122412849 [A; authors not checked; probably NOVELTY's "Yang et al. 2022"]
23. Trugman, D. T., Page, M. T., Minson, S. E., Cochran, E. S. (2019). Peak ground displacement saturates exactly when expected: implications for earthquake early warning. *JGR Solid Earth* 124(5), 4642–4653. https://doi.org/10.1029/2018JB017093 [A]
24. Meier, M.-A., Ampuero, J.-P., Heaton, T. H. (2017). The hidden simplicity of subduction megathrust earthquakes. *Science* 357, 1265–1269. https://doi.org/10.1126/science.aan5643 [A]

Classical bias and symmetry
25. Eddington, A. S. (1913). On a formula for correcting statistics for the effects of a known error of observation. *MNRAS* 73(5), 359–360. https://doi.org/10.1093/mnras/73.5.359 [A]
26. Malmquist, K. G. (1922). On some relations in stellar statistics. *Medd. Lunds Astron. Obs. Ser. I* 100, 1–52. https://ui.adsabs.harvard.edu/abs/1922MeLuF.100....1M ; overview https://en.wikipedia.org/wiki/Malmquist_bias [M]
27. Tinti, S., Mulargia, F. (1985). Effects of magnitude uncertainties on estimating the parameters in the Gutenberg–Richter frequency-magnitude law. *BSSA* 75(6), 1681–1697. https://doi.org/10.1785/BSSA0750061681 [A]
28. Efron, B. (2011). Tweedie's formula and selection bias. *JASA* 106, 1602–1614. https://doi.org/10.1198/jasa.2011.tm11181 [A]
29. Kagan, Y. Y. (2010). Earthquake size distribution: power-law with exponent β = 1/2? *Tectonophysics* 490. https://arxiv.org/abs/0908.1207 (gives the GR magnitude-error correction m_corr = m − bσ² ln10/2) [A]
30. Bloem-Reddy, B., Teh, Y. W. (2020). Probabilistic symmetries and invariant neural networks. *JMLR* 21(90), 1–61. https://jmlr.org/papers/v21/19-322.html [M for the specific statement]
31. Exponential tilting / Esscher transform (Esscher 1932; Gerber & Shiu 1994). https://en.wikipedia.org/wiki/Exponential_tilting [M]

Fusion and prior multiplicity
32. Kittler, J., Hatef, M., Duin, R. P. W., Matas, J. (1998). On combining classifiers. *IEEE TPAMI* 20(3), 226–239. https://doi.org/10.1109/34.667881 [M]
33. Tresp, V. (2000). A Bayesian committee machine. *Neural Computation* 12(11), 2719–2741. https://doi.org/10.1162/089976600300014908 [A]
34. Deisenroth, M. P., Ng, J. W. (2015). Distributed Gaussian processes. *ICML*. https://arxiv.org/abs/1502.02843 [V via agent]
35. Scott, S. L., et al. (2016). Bayes and big data: the consensus Monte Carlo algorithm. *Int. J. Management Science and Engineering Management* 11(2). https://research.google/pubs/pub41849 [A]
36. Thrun, S., Burgard, W., Fox, D. (2005). *Probabilistic Robotics*, MIT Press (occupancy-grid log-odds update minus l₀, Table 9.1). https://mitpress.mit.edu/9780262201629/probabilistic-robotics/ [M]
37. Bourlard, H., Morgan, N. (1994). *Connectionist Speech Recognition: A Hybrid Approach*. Kluwer. https://doi.org/10.1007/978-1-4615-3210-1 [M]
38. Chen, Y.-T., Shi, J., Ye, Z., Mertz, C., Ramanan, D., Kong, S. (2022). Multimodal object detection via probabilistic ensembling (ProbEn). *ECCV*. https://arxiv.org/abs/2104.02904 [V via agent]
39. Wu, M., Goodman, N. (2018). Multimodal generative models for scalable weakly-supervised learning. *NeurIPS*. https://arxiv.org/abs/1802.05335 [A]
40. Geffner, T., Papamakarios, G., Mnih, A. (2023). Compositional score modeling for simulation-based inference. *ICML*, PMLR 202:11098–11116. https://proceedings.mlr.press/v202/geffner23a.html ; https://arxiv.org/abs/2209.14249 (eq. 4) [V]
41. Linhart, J., Cardoso, G. V., Gramfort, A., Le Corff, S., Rodrigues, P. L. C. (2024). Diffusion posterior sampling for simulation-based inference in tall data settings. https://arxiv.org/abs/2404.07593 [V via agent]
42. Burkhart, M. C., Brandman, D. M., Franco, B., Hochberg, L. R., Harrison, M. T. (2020). The discriminative Kalman filter for Bayesian filtering with nonlinear and nongaussian observation models. *Neural Computation* 32(5), 969–1017. https://doi.org/10.1162/neco_a_01275 [V via agent, through a reproduction paper]
43. Hogg, D. W., Myers, A. D., Bovy, J. (2010). Inferring the eccentricity distribution. *ApJ* 725, 2166. https://arxiv.org/abs/1008.4146 [A]
44. Maity, S., Yurochkin, M., Banerjee, M., Sun, Y. (2023). Understanding new tasks through the lens of training data via exponential tilting. *ICLR*. https://arxiv.org/abs/2205.13577 [A]
45. Bhat, S., More, A., Soni, M., Agrawal, S. (2025). Prior2Posterior: model prior correction for long-tailed learning. *WACV*. https://arxiv.org/abs/2412.16540 [A]
46. Allman, E. S., Matias, C., Rhodes, J. A. (2009). Identifiability of parameters in latent structure models with many observed variables. *Ann. Statist.* 37(6A), 3099–3132. https://arxiv.org/abs/0809.5032 [A]

Label prior and label shift
47. Menon, A. K., et al. (2021). Long-tail learning via logit adjustment. *ICLR*. https://arxiv.org/abs/2007.07314 [M]
48. Ren, J., et al. (2020). Balanced meta-softmax for long-tailed visual recognition. *NeurIPS*. https://arxiv.org/abs/2007.10740 [M]
49. Hong, Y., Han, S., Choi, K., Seo, S., Kim, B., Chang, B. (2021). Disentangling label distribution for long-tailed visual recognition (LADE). *CVPR*. https://arxiv.org/abs/2012.00321 [A]
50. Ren, J., Zhang, M., Yu, C., Liu, Z. (2022). Balanced MSE for imbalanced visual regression. *CVPR*. https://arxiv.org/abs/2203.16427 [A]
51. Saerens, M., Latinne, P., Decaestecker, C. (2002). Adjusting the outputs of a classifier to new a priori probabilities. *Neural Computation* 14(1), 21–41. https://doi.org/10.1162/089976602753284446 ; Lipton, Z., Wang, Y.-X., Smola, A. (2018). Detecting and correcting for label shift with black box predictors. *ICML*. https://arxiv.org/abs/1802.03916 [M]
52. Charpentier, B., Zügner, D., Günnemann, S. (2020). Posterior Network. *NeurIPS*. https://arxiv.org/abs/2006.09239 [M]

Equivariance
53. Salinas, D., Flunkert, V., Gasthaus, J., Januschowski, T. (2020). DeepAR: probabilistic forecasting with autoregressive recurrent networks. *Int. J. Forecasting* 36(3). https://arxiv.org/abs/1704.04110 [V via agent]
54. Villar, S., Yao, W., Hogg, D. W., Blum-Smith, B., Dumitrascu, B. (2023). Dimensionless machine learning: imposing exact units equivariance. *JMLR* 24. https://arxiv.org/abs/2204.00887 [A]
55. Kaba, S.-O., Mondal, A. K., Zhang, Y., Bengio, Y., Ravanbakhsh, S. (2023). Equivariance with learned canonicalization functions. *ICML*. https://arxiv.org/abs/2211.06489 [A]
56. Mohan, S., Kadkhodaie, Z., Simoncelli, E. P., Fernandez-Granda, C. (2020). Robust and interpretable blind image denoising via bias-free CNNs. *ICLR*. https://arxiv.org/abs/1906.05478 ; Herbreteau, S., Moebel, E., Kervrann, C. (2023). Normalization-equivariant neural networks. *NeurIPS*. https://arxiv.org/abs/2306.05037 [A]

Truncation, prior swap, extrapolation
57. Ilyas, A., Zampetakis, M., Daskalakis, C. (2020). A theoretical and practical framework for regression and classification from truncated samples. *AISTATS*, PMLR 108:4463–4473. https://proceedings.mlr.press/v108/ilyas20a.html [V via agent]
58. Daskalakis, C., Gouleakis, T., Tzamos, C., Zampetakis, M. (2019). Computationally and statistically efficient truncated regression. *COLT*. https://arxiv.org/abs/2010.12000 ; Daskalakis, C., Kontonis, V., Tzamos, C., Zampetakis, M. (2021). A statistical Taylor theorem and extrapolation of truncated densities. *COLT*. https://arxiv.org/abs/2106.15908 [A]
59. Papamakarios, G., Murray, I. (2016). Fast ε-free inference of simulation models with Bayesian conditional density estimation. *NeurIPS*. https://arxiv.org/abs/1605.06376 (Proposition 1, eqs. 2–3; App. C) [V]
60. Greenberg, D., Nonnenmacher, M., Macke, J. (2019). Automatic posterior transformation for likelihood-free inference. *ICML*. https://arxiv.org/abs/1905.07488 [A]
61. Deistler, M., Gonçalves, P. J., Macke, J. H. (2022). Truncated proposals for scalable and hassle-free simulation-based inference. *NeurIPS*. https://arxiv.org/abs/2210.04815 [A]
62. Xu, K., Zhang, M., Li, J., Du, S. S., Kawarabayashi, K., Jegelka, S. (2021). How neural networks extrapolate: from feedforward to graph neural networks. *ICLR*. https://arxiv.org/abs/2009.11848 [A]
63. Netanyahu, A., Gupta, A., Simchowitz, M., Zhang, K., Agrawal, P. (2023). Learning to extrapolate: a transductive approach. *ICLR*. https://arxiv.org/abs/2304.14329 [A]
64. Kubo, H., Kunugi, T., Suzuki, W., Suzuki, S., Aoi, S. (2020). Hybrid predictor for ground-motion intensity with machine learning and conventional ground motion prediction equation. *Sci. Rep.* 10. https://doi.org/10.1038/s41598-020-68630-x [V via agent]
65. Chen, S., et al. (2023). Physics symbolic learner for discovering ground-motion models via NGA-West2 database. *Earthq. Eng. Struct. Dyn.* https://doi.org/10.1002/eqe.4013 ; https://arxiv.org/abs/2303.14179 [A]
66. Pasche, O. C., Engelke, S. (2024). Neural networks for extreme quantile regression with an application to forecasting of flood risk. *Ann. Appl. Stat.* https://arxiv.org/abs/2208.07590 [A]
67. Lin, J.-T., Melgar, D., Thomas, A. M., Searcy, J. (2021). Early warning for great earthquakes from characterization of crustal deformation patterns with deep learning (M-LARGE). *JGR Solid Earth*. https://doi.org/10.1029/2021JB022703 [A]
68. Vapnik, V., Vashist, A. (2009). A new learning paradigm: learning using privileged information. *Neural Networks* 22(5–6), 544–557. https://doi.org/10.1016/j.neunet.2009.06.042 [M]
69. Polyakov, A. (2023). Homogeneous artificial neural network. https://arxiv.org/abs/2311.17973 [A]

Search notes: per-area working notes with more entries (about 40 ML-EEW papers judged low relevance, plus GP
product-of-experts, federated EP and decentralized-fusion references) are in the shared side-session notes
folder, `~/Library/Application Support/Claude/side-session-notes/local_3aba941c-c398-4d1d-a335-0d20cb969822/litreview_2026-10-30/`
(`lit_A_eew_ml.md`, `lit_B_fusion_prior.md`, `lit_C_equiv_extrap.md`, `lit_main_notes.md`). Only the entries
that bear on the five claims are carried into this file.

---

## Update — 30 Oct 2026 (follow-up requested by the main session)

### U1. The previously unverified papers

**P. Zhang, X. Zhang & Tian (2026), *Applied Computing and Geosciences* 30, 100356 [3].**

Access attempts:
- OpenAlex lists it as gold open access (CC BY-NC-ND, published 25 May 2026), with no repository copy beyond DOAJ.
- ScienceDirect refused both plain fetches and the in-app browser ("There was a problem providing the content you requested").
- DOAJ served a Cloudflare challenge. I did not try to get past either check.
- SSRN returned 403.
- No arXiv / ESSOAr / EarthArXiv version, author page or GitHub/Zenodo code was found.

**The full text was not read.** The complete abstract was read through the OpenAlex and Semantic Scholar APIs [A]. It establishes the following:

| Question | What the abstract says | Status |
|---|---|---|
| Output M − κ·log A, κ fixed or learned? | "Pseudo-normalization": the input is normalized but "preserving the normalization factor", so the network can "decouple waveform shape features from amplitude scaling". Normalized waveforms predict "the epicentral distance and magnitude contribution excluding the absolute amplitude". | Additive recombination with the log normalization factor is clear. The slope is not stated. The authors' earlier papers [1, 2] use a fixed slope of 1, so **κ ≡ 1 is likely but unconfirmed**. Nothing suggests a learned or waveform-dependent slope. |
| Prior factor? | None mentioned. Output is "one-dimensional Gaussian distributions" to quantify uncertainty. | No evidence of a GR or label prior. |
| Distance co-output or marginalized? | "Simultaneous estimation of magnitude and epicentral distance". | **Co-output**, not marginalized. Distance does not enter the magnitude likelihood as a latent, as far as the abstract says. |
| INSTANCE split and metrics | Trained on INSTANCE with a "multi-time-window strategy". Test MAE 0.1977 (magnitude) and 1.67 km (epicentral distance). | Split, windows and per-magnitude-bin error unknown. The pooled MAE is not comparable with the study's bulk/tail MAE without the split. |
| Large-magnitude error | Not reported in the abstract. | Unknown. |

**Action:** ask someone with ordinary web access to download the open PDF from https://doi.org/10.1016/j.acags.2026.100356 and check:
- the exact magnitude reconstruction formula;
- the INSTANCE split (event- or record-level; temporal or random);
- any error-by-magnitude figure.

If it is κ ≡ 1 on INSTANCE, the queued κ ≡ 1 ablation *is* this construction on the study's trunk, which is the right comparison.

**Kuang, Yuan & Zhang (2021), *SRL* 92(4) [7].**
- Closed access; OpenAlex reports no repository copy. The full abstract was read [A]:
  - a network-wide encoder–decoder "MagNet" whose output is "a Gaussian probability distribution representing the magnitude";
  - "trained with an augmented data set, which includes 21,700 training samples with evenly distributed magnitudes";
  - test mean error −0.017 ± 0.21 for 600 M3–5.9 events;
  - "it remains challenging for large earthquakes (magnitude > 6.5), due to the lack of sufficient historical large earthquakes".
- How the augmentation creates evenly distributed magnitudes (amplitude rescaling with a label shift, or resampling) **remains unverified**.
- Either way it is a *flat training prior with no test-time correction* (the CREIME pattern [9]), not an equivariant head.
- If the full text shows Richter-type amplitude rescaling, it is the published precedent for the study's `cat_aug` baseline.

**Thapa et al. (2026), *Bull. Earthquake Eng.* 24, 3465–3492; preprint Research Square rs-7479899 [72] [V, preprint read].**
- U-Net++ with attention for P detection, double-integrated acceleration features, and Gaussian-labelled picks.
- Magnitude is computed from an energy relation, M = log₁₀(E_total) + C (eq. 14), where E_total is the summed squared displacement. The paper calls this "Gutenberg–Richter's relation", but it is the energy–magnitude relation, not the frequency law.
- MCMC (emcee, 32 walkers) samples the magnitude, with the target stated as "P(M | D) is proportional to the likelihood". **The prior is therefore implicitly flat; there is no Gutenberg–Richter frequency prior.**
- Data: a STEAD subsample "covering magnitudes from M3.0 to M8.0" and described as balanced.
- Relevance: low. A fixed parametric amplitude–energy law, with no learned equivariant head, no prior factor and no extrapolation test.

### U2. Physical saturation limit the capped-training results must respect

These are the magnitudes above which early-window P amplitude stops growing with final magnitude. Windows run from the P arrival (Meier 2015/2016, Trugman 2019) or from the rupture onset (Münchmeyer 2022). Values marked † are my interpolations in log t between published values.

| Window | Trugman et al. 2019 model (weak predictability; peak displacement; K-NET/KiK-net) | Meier et al. 2015 (filter-bank PGV, Gutenberg algorithm) | Meier et al. 2016 (near-source pgd, < 25 km) | Münchmeyer et al. 2022 (source time functions) |
|---|---|---|---|---|
| 1 s | **M ≈ 5.7** | "clear magnitude saturation for events with M > 6" at 1 s | Bin medians for M5.5–6.0 and M6.0–6.5 start to diverge at ~1 s, but the bins are not statistically distinct | Buckets "mostly identical" for the first ~2 s |
| 2 s | M ≈ 6.4 | for windows < 4 s, "saturation starts at M ∼ 6.5" | — | Mw 6.5–7.0 bucket separates at ~2 s |
| 3 s | M ≈ 6.7 † | M > 6.5 not significantly higher than M ≈ 6.5 at 3 s | M6.5–8 indistinguishable from M6.0–6.5 | — |
| 4–5 s | M ≈ 7.0 at 4 s; ≈ 7.1 at 5 s † | — | M6.5–8 separates from M6.0–6.5 only after **5–6 s** | Mw 7.0–7.5 separates at ~8 s |
| 8–10 s | M ≈ 7.4 at 8 s | M > 7.5: "even 10 s are not long enough" | — | Mw 7.5–8.0 at ~16 s; 8.0–8.5 at 25–40 s |

Sources and checks:
- Trugman values as quoted in TEAM-LM [4] ("magnitude saturation at approximately magnitude 5.7 after 1 s; 6.4 after 2 s; 7.0 after 4 s; 7.4 after 8 s") [V in TEAM-LM; Trugman's own text not reachable: OSTI refused the connection and Wiley is closed].
- Meier 2015 [16] [V]. Meier, Heaton & Clinton 2016 [70] [V]. Münchmeyer, Leser & Tilmann 2022 [71] [V].
- The common physical reading: magnitude becomes identifiable only after about half the rupture duration.

Implications for the capped-training claim:
- At **1 s**, no amplitude-based estimator should recover magnitudes much above **M ≈ 5.7–6**.
  - A cap at M5 on INSTANCE leaves only ~0.7–1 magnitude units of physically recoverable extrapolation at 1 s.
  - The README's observation that "at 1 s every head stays strongly biased on the largest events" is expected physics, not a model failure.
- At **3 s** the limit is **M ≈ 6.5–6.7**; at **5 s** it is **M ≈ 7.0–7.1**, or about 6.5 if one follows Meier 2016's near-source 5–6 s separation time.
- INSTANCE's largest events (M6–6.5) therefore sit near the 3 s limit and below the 5 s limit, so extrapolation gains there at 3–5 s are physically possible.
- GEOFON's M≥7 tail lies **above** the 3 s limit and at the 5 s limit, so saturation of every head there (README: "on GEOFON all heads saturate") is expected.
- **Suggested presentation:** plot the capped-training bias by magnitude bin with a vertical line at the Trugman saturation magnitude for each window. Claim extrapolation only between the cap and that line.

Caveats:
- These limits are for *peak* displacement or velocity at mostly near-source distances. The study's A is the RMS of the whole window, which grows more slowly than the peak, so its saturation may set in at slightly lower magnitudes.
- At far-regional distances the P window also contains path-dependent coda.
- TEAM-LM observed its own saturation *below* these thresholds (Italy ≈ M5.5, Chile ≈ M6.0) and attributed it to data sparsity. That is the effect the capped-training test is designed to separate from physics.

### U3. Draft "Related work" for PAPER.md (≈450 words, ready to paste; citation keys as in the reference list)

Note: "Chen et al. 2022" is ProbEn [38]. Do not confuse it with Chen et al. 2023 (PISL) [65] if both enter the bibliography.

> **Related work.** Deep-learning early-warning magnitude estimators keep amplitude in the waveform (Mousavi &
> Beroza 2020) or feed the log normalization factor as a free input (Münchmeyer et al. 2021; Zhang & Zhang
> 2024), and underestimate the largest events, which Münchmeyer et al. attribute to the Gutenberg–Richter (GR)
> imbalance of the training data. Closest to
> our likelihood, Zhang, Zhang & Tian (2021) and the preprint of Zhang & Zhang (2023) predict a distribution
> over a normalized magnitude M − log A_max and add log A_max back, which makes the prediction exactly
> equivariant to amplitude scaling with unit slope; P. Zhang et al. (2026) apply a related pseudo-normalization
> to single-station INSTANCE records. We generalize this construction in three ways: the slope κ(s) is learned
> and depends on the scale-free waveform, all components of a Gaussian mixture share the equivariant shift,
> and the posterior carries a learned global prior factor, free below the completeness magnitude and GR-linear
> above it, that preserves the equivariance. The unit-slope head is one of our ablations.
>
> Bayesian early warning has long combined amplitude likelihoods with a GR prior (Cua & Heaton 2007; Lancieri
> & Zollo 2008; Meier et al. 2015), and the constant magnitude shift that a GR prior induces under Gaussian
> errors is classical (Tinti & Mulargia 1985; cf. Eddington 1913). The Gutenberg algorithm (Meier et al. 2015)
> also forms a joint magnitude–distance posterior from single-station amplitudes and marginalizes distance, as
> our distance-marginalized head does, but with a nearest-neighbour likelihood that cannot exceed the training
> amplitudes. Proposition 1 states when this shift makes the exact posterior equivariant despite unknown
> distance, site and path.
>
> Fusing per-sensor posteriors requires dividing out the prior that each was computed under: the product rule
> of Kittler et al. (1998), the Bayesian committee machine (Tresp 2000) and, for deep networks, probabilistic
> ensembling (Chen et al. 2022) and compositional score modelling (Geffner et al. 2023). We found no early-warning
> system that does so: the Gutenberg algorithm multiplies per-station posteriors that already contain the GR
> prior, and neural systems average station magnitudes (Zhang & Zhang 2024). We measure the resulting bias on
> three catalogues, and Proposition 2 adds that a learned prior factor's tail slope is not identified from
> single-station data, so the prior to divide out is the training-label prior.
>
> Finally, training on a label-truncated catalogue is a truncated-likelihood problem (Daskalakis et al. 2019;
> Ilyas et al. 2020), and replacing the training prior by the target prior at inference is the proposal
> correction of neural posterior estimation (Papamakarios & Murray 2016; Deistler et al. 2022). Both are valid
> only inside the training support. Proposition 3 shows that exact equivariance carries the likelihood above
> the cap, up to the window-dependent magnitude at which early P amplitudes saturate physically (Meier et al.
> 2015; Trugman et al. 2019).

Before pasting, check one point: the sentence on P. Zhang et al. (2026) rests on its abstract only (U1).

### References added in this update

70. Meier, M.-A., Heaton, T., Clinton, J. (2016). Evidence for universal earthquake rupture initiation behavior. *GRL* 43(15), 7991–7996. https://doi.org/10.1002/2016GL070081 [V]
71. Münchmeyer, J., Leser, U., Tilmann, F. (2022). A probabilistic view on rupture predictability: all earthquakes evolve similarly. https://arxiv.org/abs/2203.08622 [V]
72. Thapa, S., Basnet, R., Panwar, A., Rayat, S. S., Verma, A., Dahiya, S., Rathod, A. P. S. (2026). A physics-informed deep learning and probabilistic inference framework for real-time single-station earthquake detection and magnitude estimation. *Bull. Earthquake Eng.* 24, 3465–3492. https://doi.org/10.1007/s10518-026-02403-1 ; preprint https://doi.org/10.21203/rs.3.rs-7479899/v1 [V, preprint]

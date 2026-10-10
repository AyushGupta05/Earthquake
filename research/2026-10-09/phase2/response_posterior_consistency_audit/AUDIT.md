# Prefix posterior consistency across causal instrument responses

**Decision: zero learned or paid fits.** A precise, admissible modification survives as an engineering hypothesis: distill a joint, state/noise-aware prefix posterior into each instrument view using teacher-to-student KL, while reserving exact posterior equality for verified information-preserving response transformations. This is ordinary probabilistic distillation with stricter measurement constraints. No new probability principle, earthquake error improvement or benchmark superiority is established. The cheap invented controls below reject the more tempting unconditional invariance loss.

This refinement is separate from the immutable `causal_response_mechanism_audit` published at commit `53962ad`. It reads existing reports and a small set of primary papers. No real rows, waveforms, response inventories, pair census, prediction arrays, models or checkpoints were read. No implementation file, author-code execution, fit, AWS action, data request or expansion of the frozen GeoNet requests occurred. Files here are documentation, source-access records and invented arithmetic only.

## Closest prior art

Paper-derived descriptions are short; mathematical deductions below are ours.

- **Bharadwaj 2024:** [variational SymAE primary text](https://arxiv.org/html/2411.15613v1), sections 3.2–3.5, factors shared coherent-source and trace-specific nuisance distributions, accumulates source information and evaluates real/virtual traces through source-posterior KL. It can swap nuisance codes and optimize a virtual trace. Generic probabilistic source/nuisance separation and posterior preservation under virtual redatuming already overlap this proposal.
- **Bharadwaj et al. 2025:** [published author-hosted text, DOI 10.1785/0120250071](https://ceas.iisc.ac.in/~geophyinv/publication/bharadwaj-2023-learning-earthquakes/bharadwaj-2023-learning-earthquakes.pdf), equations 14–17, applies SymVAE source/path factorization. Equation 16 minimizes KL between a group source posterior and a virtual-trace posterior while changing path code. Its instrument-corrected, standardized, ±200-second teleseismic windows and spatial-scale assumptions do not verify our 1/3/5-second clock. Coherent scattering can remain inseparable from source effects. This is closer overlap than merely an autoencoder architecture.
- **Gupta, Hoffman and Malik 2016:** [CVPR primary PDF](https://www.cv-foundation.org/openaccess/content_cvpr_2016/papers/Gupta_Cross_Modal_Distillation_CVPR_2016_paper.pdf), section 3, transfers supervision between paired modalities by matching learned representations. Their main experiments use intermediate features; this is prior art for paired supervision transfer, not evidence that all modality-specific posteriors should coincide.
- **Lopez-Paz et al. 2016:** [ICLR author-hosted primary PDF](https://leon.bottou.org/publications/pdf/iclr-2016.pdf), sections 3–4, trains students on soft teacher outputs from privileged representations absent at deployment. It includes different input modalities, hard/soft target mixtures and cases where privileged information does not help. A teacher with both HH/HN views is an instance of this established framework.
- **Hinton, Vinyals and Dean 2015:** [primary preprint](https://arxiv.org/pdf/1503.02531), sections 2 and 5.4, uses soft-target cross-entropy. Section 5.4 explicitly distinguishes arithmetic versus geometric aggregation according to KL direction. Our forward/reverse KL distinction therefore is not a new general principle.
- **Zhu, Mousavi and Beroza 2020:** [primary publisher abstract/introduction](https://doi.org/10.1016%2Fbs.agph.2020.07.003) motivates physically appropriate seismic augmentation, including noise recombination and channel/station dropout. Full chapter access was not resolved; the DOE mirror failed. No full causal response replacement or prefix posterior-consistency result is inferred from that access.

These are bounded nearest-overlap checks, not an exhaustive proof of novelty. None supplies an independently matched early-magnitude comparison for our proposal.

## Three different meanings of consistency

Let `V_i=(d_i, b_i, R_i, available-clock/mask information)` be everything a deployed view may use. `b_i` is its received pre-P context and `R_i` its full effective causal response. A nominal response does not undo unknown whole-record preprocessing. Let `M` be the final magnitude, with any common physical ground-motion history and response states marginalized in a valid joint model.

**1. Information-preserving representation.** If `V_B=T(V_A)` is a one-to-one, causal, available-prefix mapping, with its inverse and complete transformed state/noise law available, normalized posteriors must agree. For a linear count transform,

`p(Td | M)=p(d | M)/|det T|`.

The determinant cancels in the normalized magnitude posterior. This changes representation, not information. Coherent scalar-gain augmentation is a special case; full temporal filters can be another. Two instruments measuring the same ground motion are not automatically such a mapping.

**2. A verified information-losing channel.** Suppose a known causal kernel generates `V_B` from `V_A`, and `M ⟂ V_B | V_A`. Then

`p(M | V_B)=E[p(M | V_A) | V_B]`.

The target is a conditional mixture, not the posterior of one paired A realization or the teacher evaluated at an estimated A mean. Noise addition can be such a channel. Arbitrary replacement by `H_B H_A^(-1)` cannot: finite-prefix inverses may fail, require unavailable boundary/future values, be unstable or alter noise. Physical response and state/noise compatibility must be proved together.

**3. Independently noisy collocated sensors.** In general neither view is a garbling of the other: each can contribute independent evidence. Use an accurate joint teacher `q_J(M | V_A,V_B)` instead. The identity

`E[p(M | V_A,V_B) | V_i]=p(M | V_i)`

holds without independent-sensor assumptions. Consequently, population minimization of `E[KL(q_J || q_i)]` over an unrestricted student recovers its own calibrated posterior when the teacher is exact. It does **not** require every paired KL to vanish. Reverse or symmetric equality penalties need separate justification. Temperature one is required for this literal posterior statement; arbitrary softened targets change it.

A joint likelihood must retain shared ground/path noise and source/state dependence. Multiplying two already-prior-conditioned magnitude posteriors can count the prior twice. SymAE's latent-product construction is not a license to multiply any calibrated sensor posteriors.

## Exact invented no-fit controls

`synthetic_arithmetic.json` uses deterministic rational Gaussian algebra, with floating-point normal tails only for illustration. `U~N(0,1)` is an invented physical-amplitude latent, **not magnitude**. One sample per second labels the 1/3/5-prefix examples; this is neither realistic instrument sampling nor a real-time proof.

- **Independent views refute pointwise equality.** With `A=U+ε_A`, `B=U+ε_B`, independent unit-variance noises, and observations `A=1,B=-1`, the individual posteriors are `N(0.5,0.5)` and `N(-0.5,0.5)`. The joint posterior is `N(0,1/3)`. Each directed individual KL is 1. These are all correct; forcing them equal is wrong.
- **A known garbling needs mixture variance.** With `Var(ε_A)=1/4`, `B=A+δ`, `Var(δ)=1`, and `B=1`, `A|B~N(5/9,5/9)`. Averaging `U|A~N(4A/5,1/5)` gives `U|B~N(4/9,5/9)` exactly. Plugging in `E[A|B]` incorrectly keeps variance `1/5`.
- **Distinct full causal responses tie only with matching uncertainty.** An invented stable response has state `r_k=(4/5)r_(k-1)+U`, initial `S0|b~N(3/10,1/2)` and external output noise variance `1/4`. A known, zero-initialized extra causal FIR channel `T=I+(1/2)L` generates view B from the observed A prefix. Its full state contribution and colored noise covariance transform with T. Exact raw and transformed posteriors tie at all three lengths. Leaving B noise white changes the posterior at lengths 3 and 5. This counterfactual is not an independently noisy second instrument. Reducing boundary-state variance using extra context adds information; it cannot be attributed to regularization.
- **Truncated replacement can be impossible.** A one-sample-delay response maps histories `[1,2]` and `[1,9]` to the same available prefix `[0,1]`. An identity response distinguishes them. No deterministic mapping of that delayed prefix can recreate the identity-response observation on this support.

For n independent unit-noise observations in each real-view toy, condition on every B observation being 1. The correct B variance is `1/(1+n)`, while the joint teacher variance is `1/(1+2n)`. Forward KL retains the conditional variance of teacher means; reverse KL discards it.

| Invented prefix length | Correct / forward-KL variance | Reverse-KL variance | Actual coverage of reverse-KL nominal 95% interval |
|---|---:|---:|---:|
| 1 | 0.500000 | 0.333333 | 89.05% |
| 3 | 0.250000 | 0.142857 | 86.16% |
| 5 | 0.166667 | 0.090909 | 85.23% |

These controls verify probability identities and expose overconfidence. They do not measure any earthquake error or establish that the discrepancy occurs in our data.

## Concrete surviving hypothesis and its controls

The narrow candidate is **state/noise-aware joint-prefix soft-target transfer with a causal admissibility check**. Training pairs may be genuinely collocated instruments, or invented forward observations from a common physical history with explicitly modeled states and noise. Counterfactuals may never be obtained by assuming a truncated real trace uniquely determines the hidden physical history. At deployment each student uses only its own received prefix and context. Any improvement is a finite-sample learning or calibration effect until demonstrated otherwise.

Compare identical input information, clocks, physical amplitude, masks, splits and capacity:

| Control | What it decides |
|---|---|
| Supervised raw counts + full response + pre-P context | Does explicit transfer add anything beyond the complete discriminative input? |
| Causal deterministic canonicalization + matching metadata/context | Does the proposed model merely choose another representation? Exact invertible likelihoods must tie; bandwidth-losing canonicalization changes information. |
| Ordinary joint-teacher forward-KL distillation | Does anything remain beyond conventional paired privileged-information training? If identical, the candidate is this control. |
| Shared source / separate nuisance representation such as SymAE | Is the proposed distinction more than already-established latent disentanglement and posterior-preserving virtual traces? Spatial assumptions need independent justification for local early prefixes. |

Hard pairwise equality, reverse KL and the untransformed-noise arm are falsified examples, not reasons to start another grid. A hypothetical clipped HH plus unclipped HN can add deployment information through fusion; distillation cannot recover information absent from a particular clipped student prefix. New metadata or pre-P context supplied to only one arm would also add information and confound attribution.

The completed response-FiLM/coherent-gain grid failed its frozen criteria, and the later-CDF distillation/revision grid failed replication. This proposal does not erase those negatives. Temporal-shape channels and inherited state differ from scalar gain, but generic distillation and covariance-only expansions are already tested or established controls.

## Data and investment gates, not new requests

Before any learned expansion, existing authorized evidence must establish genuine physical colocation, orientation, response epochs/units, effective preprocessing, causal timestamp/receipt alignment, unclipped usable prefixes, and sufficient available pre-P state/noise context. HH/HN names, a common event ID or a common station name alone do not prove that. Independent sensors cannot be declared information-equivalent from waveform similarity. Unknown/unmodeled state, differing noise or response null spaces falsify that declaration.

A real joint teacher needs a defensible common-history/noise law and independent calibration evidence; a full-event teacher does not validate early-prefix physics. TRAIN-only pairing/design and adequate independent large-event, event/station/instrument holdouts are necessary. No pair census is performed here and no frozen GeoNet requests are expanded.

The invented identities already supply a cheap no-fit rejection of unconditional invariance. A later bounded unknown-state fixture must compare exact counts and exact canonical likelihoods at the same information and reproduce the mixture identities before learning is considered. Passing it is measurement correctness, not a tail-risk win. Proceed beyond zero fits only if admissible data and a distinct testable mechanism remain after the conventional distillation control. Current evidence does not meet that gate; the narrow adaptation remains a documented hypothesis with strong prior-art overlap.

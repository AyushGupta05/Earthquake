# Why scale equivariance, and when it is the Bayes-correct structure

## Setting

At one station and deadline t we observe a prefix x. Split it into
* A = log10 of its RMS in physical units (counts / sensitivity), and
* s = everything scale-free: the waveform divided by its RMS, amplitude ratios,
  station metadata and the deadline.

The pair (A, s) is a lossless reparameterization of x.

## Proposition (GR equivariance)

Assume
1. Gutenberg–Richter prior: p(M) ∝ 10^(−bM) over the magnitude range of interest;
2. log-linear amplitude: A = κ M + h(z) + ε, where z collects every nuisance (distance,
   depth, radiation pattern, site, path, instrument), p(z) does not depend on M, and ε is
   noise independent of M;
3. self-similar shape: p(s | M, z) does not depend on M.

Then for every δ the Bayes posterior satisfies p(M | A + κδ, s) = p(M − δ | A, s): it is
exactly shift-equivariant in A, *even though distance and the other nuisances are unknown*.

*Proof.* By Bayes,
p(M | A, s) ∝ 10^(−bM) ∫ φ_ε(A − κM − h(z)) p(s | z) p(z) dz = 10^(−bM) G_s(A − κM).
Replace A by A + κδ and M by M + δ. The factor G_s is unchanged and 10^(−b(M+δ)) changes
only by a constant, which normalization removes. ∎

`test_theory.py` checks this numerically with an arbitrary non-linear attenuation term h(z),
a broad unknown-distance distribution and κ = 0.7: the shifted and re-evaluated posteriors
agree to a relative 10⁻¹⁵. Replacing the GR prior by one with a 9× selection cliff at M2.0
(as in INSTANCE) breaks the identity by up to 84% of the posterior peak when the posterior
straddles the cliff, and not at all once it lies above it. That is why `eqgr` leaves the
prior free below M3.5 and makes it GR-linear above: the head is then exactly equivariant
exactly where the large events are.

Two consequences:
* Under GR the *amplitude-implied magnitude is never discounted for being large*. The
  shrinkage that GR imposes is a constant shift (for Gaussian ε, −b ln10 σ²/κ), the same
  for an M2 and an M6 with the same shape. Unknown distance does not break this, because
  the exponential prior makes the distance posterior p(z | A, s) independent of A.
* A flexible network trained on finitely many large events need not learn this. In the
  sparse upper tail it is free to flatten the amplitude response and regress to the bulk,
  which is the classic large-event underestimation.
* **Measured (diagnostics_*.json, held-out folds):** for held-out M≥4 records the equivariant
  head learns κ ≈ 0.61–0.77 per decade of RMS amplitude (consistent with Mw ∝ ⅔ log M0), and
  its response is symmetric under ×10 and ÷10. The free heads respond less in the
  *extrapolation* direction. On the unseen M6.5 Central Italy sequence the upward response is
  .46/.44/.39 (categorical) and .53/.54/.51 (free mixture × same prior) at 1/3/5 s, against
  .54–.66 for the downward response. That asymmetry is saturation where training data end;
  the equivariant head removes it by construction.

**Corollary (conditioning on distance).** Write z = (r, z′) with r the log distance. The same
proof, run with p(z′ | r) in place of p(z), shows that p(M | A, s, r) is equivariant too. Its
G_{s,r} is narrower, because it no longer averages over r. The distance-marginalized head
(`eqdgr`) models the joint p(r, M | x) with exactly this structure: an equivariant Gaussian per
distance bin, with weights p(r | s). So one trained model gives both posteriors. The marginal
serves a station that does not yet know its distance. The conditional p(M | r̂, x) ∝ Σ_r p(r, M | x)
N(r̂; r, σ²) serves a station once a network location r̂ with log-error σ exists (`condr_arms.py`;
no retraining). The GR shrinkage −b ln10 σ²/κ uses the residual scatter given what is conditioned
on, so conditioning lowers the scatter and that constant shift with it. Any bias that remains for
the largest events is therefore not shrinkage: it is the waveform not yet carrying the event's
size (rupture still growing).

## Where the assumptions fail, and how the method handles it

| failure | effect on the Bayes posterior | handled by |
|---|---|---|
| catalogue incompleteness (prior not GR below the completeness magnitude) | small-amplitude records are pulled *up*: response to amplitude decreases < κ at small A | `eqgr`: learned free log-prior below M3.5 times a GR-linear factor above. A linear-exponential factor keeps the head exactly equivariant in the tail |
| magnitude-dependent shape (corner frequency, rupture still growing at 1 s) | s carries magnitude information, so the slope can differ from κ | κ(s) ∈ [0.3, 1.5] and all mixture weights/offsets depend on s |
| mixed ML / Mw labels | different amplitude slopes per label type | κ(s) learned; residual misfit visible in per-bin bias |
| clipping / non-linear sensors | A saturates at the rail | shape (flat tops) is visible in s; accelerometers (HN) are unclipped |

## Proposition 2 (the tail slope of the prior factor is not identified from single-station data)

Let the likelihood be a Gaussian mixture in M, L(M | A, s) = Σ_k w_k N(M; μ_k, σ_k²), and the
prior factor exponential in the tail, π(M) ∝ exp(βM). Then

    L(M) π(M) ∝ Σ_k w_k' N(M; μ_k + βσ_k², σ_k²),   w_k' = w_k exp(βμ_k + β²σ_k²/2):

an exponential tilt of a Gaussian mixture is again a Gaussian mixture, with every component
shifted by βσ_k² and re-weighted. The pairs (L, β) and (L', 0), with L' the tilted mixture,
give the same single-station posterior for every (A, s). So no amount of single-station
training can identify β: the split of the posterior into "likelihood" and "prior factor" is
determined only up to an exponential tilt wherever the prior is linear. (`test_theory.py`
checks the identity numerically.) The equivariance proposition is unaffected, because the
shift βσ_k² does not depend on A, and so is every single-station result in this study, which
compares posteriors.

What the split *does* change is multi-station fusion. For k stations of one event, Bayes
gives p(M | x_1..x_k) ∝ Π_i L(M | x_i) · π(M) with the prior counted once. If the model's split
is (L̃_i, π̃) with π̃ = π · exp(−γM) (a flatter learned factor), then L̃_i = L_i exp(γM) and

    Π_i L̃_i · π̃ = [Π_i L_i · π] · exp((k − 1) γ M):

the fused posterior carries a residual tilt that grows with the number of stations. The
product of *posteriors*, Π_i p(M | x_i) = Π_i L_i · π^k, is the special case γ = β and
over-counts the whole prior k − 1 times, which pulls fused estimates of large events toward
the bulk. The prior that fusion must divide out is therefore the prior the posterior was
trained under, i.e. the label distribution of the training set, not a learned factor whose
tail slope is free. The multi-station study (`multistation.py`) tests exactly this: the
posterior product, the posterior mean, the product with the learned factor counted once, and
the product with the empirical training-label prior counted once.

## Proposition 3 (extrapolation beyond a truncated training catalogue)

Suppose the training catalogue contains only events with M < C (a cap), while the target
population follows π(M) with the Gutenberg–Richter tail above C. The training population has
p_train(M, x) ∝ p(x | M) π(M) 1[M < C], so its Bayes posterior is
p_train(M | x) ∝ p(x | M) π(M) 1[M < C], and the target posterior is p(M | x) ∝ p(x | M) π(M).
For a factorized model p_θ(M | x) ∝ L_θ(M | x) · e^φ(M):

* training with the factor φ_train = φ + log 1[M < C] fits L_θ ∝ p(x | M) on M < C, and replacing
  φ_train by φ at test time yields the target posterior — *if* L_θ is also right for M ≥ C;
* nothing in the training data constrains L_θ above C. A free likelihood is arbitrary there,
  and a free posterior (no factor) cannot even express the swap: it has learned that
  P(M ≥ C | x) = 0;
* under the assumptions of Proposition 1, p(x | M) for M ≥ C is determined by values below C:
  scaling a record by 10^(−κδ) maps an event of magnitude M to one of magnitude M − δ with the
  same shape distribution, so p(A, s | M) = p(A − κδ, s | M − δ). An equivariant likelihood,
  whose dependence on (A, M) is through κ(s)(A − A₀) − M alone, therefore carries what it
  learned below the cap to every magnitude above it, and the swap of φ_train for φ is the exact
  Bayes extrapolation.

*Measured (30 Oct).* The swap matters even for a free likelihood. On INSTANCE capped at M4.0 a
free mixture × GR factor, truncated in training and untruncated at test, cuts M ≥ 5 error from
1.6 to .8 at 3–5 s, against .55–.67 for the equivariant heads. A likelihood fitted next to a
truncated prior is not itself forced to vanish above C, so it is "free" there in practice rather
than adversarial. Equivariance pins it down, which shows as fewer false alarms and a further
(not significant) tail gain. When the scale changes across the cap (GEOFON: mb below, Mw above),
the amplitude law learned below C is the wrong one above, and neither head reaches a unit-slope
baseline.

The tail slope of φ is then either learned from the labels between M_C = 3.5 and the cap or
pinned to the catalogue b-value (`--beta-fixed`). The prediction is testable: train every head
on M < C only (`train.py --train-mag-cap C`), and compare them on held-out events above C. Free
heads must saturate at the cap; equivariant heads with the untruncated tail should not, to the
extent that real waveforms are self-similar (corner frequency and rupture duration break it for
the largest events, which bounds how far the extrapolation can reach).

**Remark (heads with a latent training label).** The distance-marginalized head (`eqdgr`) models
a joint p_θ(r, M | x) over a distance bin r that is observed during training and marginalized at
test time; the scale-mixture head does the same with the magnitude type. Truncating that joint,
p_θ(r, M | x)·1[M < C] / P_θ(M < C | x), is *not* identified: the components p_θ(M | r′, x) of
the wrong bins r′ ≠ r can be moved above C, where the truncated factor hides them. That costs
nothing during training and raises p_θ(r | x, M < C), so a training run may take it, and it is
undone at test time when the full factor returns. On Chile capped at M5.0 it happened in four
of five folds (30–80% of the mass of M < 3 records above M6); on INSTANCE capped at M4.0 it did
not happen. The remedy truncates only the magnitude conditional: −log p_θ(r | x) − log
p_θ(M | r, x, M < C), with p_θ(r | x) taken from the untruncated joint (`--cap-latent
conditional`, `models.joint_log_prob`). Each conditional is then a truncated Gaussian
regression, which is identified. The marginal of r is fitted on a sample selected on M, which
biases it only through P(M < C | r, x), negligible when the cap sits well above the bulk. Without
a cap the two losses coincide exactly. The same non-identifiability, in a milder form, applies to
any latent that is *not* observed, such as a mixture's component index: components lying wholly
above C are invisible to the truncated likelihood, so their weight is unconstrained. The audit
of 30 Oct measured it in the capped plain head (5–8× more likelihood weight above M4.5 on small
records than the uncapped head, a 1.5–2× higher false-M4 rate, unchanged large-event estimates).
A remedy for unobserved latents is a *truncation margin* (`--cap-margin Δ`,
`models.MarginTruncated`). Labels at least Δ below C are scored by the untruncated posterior,
labels within Δ of C by the truncated one. For y < C − Δ the selection-correct likelihood is
p(y | x) / P(m < C | x), and under the true posterior the denominator is within
P(m ≥ C | x, y < C − Δ) of 1. That is negligible once Δ is a few posterior SDs. So dropping it
costs almost no bias, and it charges the model for any mass it hides above C on those records.
The near-cap labels keep the truncation that lets the head extrapolate. Predicted effect: the
capped heads' false-alarm rate falls toward the uncapped heads', with large-event estimates
unchanged. Δ = 1.0 is fixed in advance, more than twice the largest bulk posterior SD; under
test on INSTANCE and Chile.

**Classical counterpart.** Under selection on M, a forward regression of M on log amplitude is
biased (truncation acts on the response), while the inverse regression of log amplitude on M is
not (truncation acts on the regressor). Fitted on capped rows, the forward law saturates like a
free network and the inverse law extrapolates (`linear_baseline.py`), though without a distance
term its bulk error is large. The equivariant head is the generative, inverse-direction law
inside a learned posterior, which is why it extrapolates.

## Relation to the decision rule

For any posterior p, the tail-weighted median a_r (r times the weight on M ≥ 4) is the
Bayes action for the loss r·|e|·1[M≥4] + |e|·1[M<4]. Sweeping r gives the best bulk/tail
trade-off available from p. So the comparison that matters is between *posteriors*,
judged at matched bulk error. That is how every arm is compared.

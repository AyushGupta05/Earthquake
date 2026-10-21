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

## Relation to the decision rule

For any posterior p, the tail-weighted median a_r (r times the weight on M ≥ 4) is the
Bayes action for the loss r·|e|·1[M≥4] + |e|·1[M<4]. Sweeping r gives the best bulk/tail
trade-off available from p. So the comparison that matters is between *posteriors*,
judged at matched bulk error. That is how every arm is compared.

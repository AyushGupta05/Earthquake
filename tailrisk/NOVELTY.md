# Novelty audit: what is new, what is prior art, and what was done to check

Written 19 Oct 2026 after a bounded literature search (web search and primary-paper reads,
not a systematic review; absence from this list is not proof of absence). Each row names
the closest prior work and states the precise difference.

## The claim

The method is the posterior

    p(m | x) ∝ L_θ(m | A, s) · exp(φ(m)),

with (i) a **scale-equivariant likelihood** L_θ: a Gaussian mixture whose component
locations are κ(s)(A − A0) + g_k(s), so that multiplying the ground motion by c translates
the whole predictive distribution by κ(s)·log10 c exactly; (ii) a **learned global
magnitude prior factor** φ that is free below M3.5 and Gutenberg–Richter-linear above, kept
at test time; (iii) a proof that under a GR prior, a log-linear amplitude law and a
self-similar waveform shape, the exact Bayes posterior has this equivariance even when
distance, site and path are unknown (THEORY.md); and (iv) a diagnostic showing that free
networks lose this property where training data end (amplitude response 0.39–0.54 per
decade upward vs 0.54–0.66 downward on held-out large events).

## Closest prior art

| prior work | what it does | how this differs |
|---|---|---|
| Bayesian EEW with a GR prior: Virtual Seismologist (Cua & Heaton 2007), Gutenberg algorithm (Meier et al. 2015), Yang et al. 2022 | Parametric amplitude/frequency likelihoods × Gutenberg–Richter prior; analytic posteriors. Meier et al. note magnitude saturation that depends on signal length | Same Bayesian structure, but the likelihood is a neural network trained end-to-end on waveforms; the GR structure is a constraint on that network's head, and the prior below completeness is learned rather than assumed. The equivariance proposition is, as far as found, not stated in this literature |
| TEAM-LM (Münchmeyer et al. 2021) | Gaussian-mixture magnitude head; magnitude resampling; saturation attributed to few large training events | Run as the `mix_nll` control (same trunk). The new method beats it with CIs excluding zero. TEAM-LM uses no prior factor and no equivariance |
| Zhang & Zhang 2024, "generalized earthquakes" | Per-station normalization with the log normalization factor as a separate input channel; synthetic training events scaled with the Hutton–Boore ML relation; Gaussian labels; large events augmented | Log amplitude as a *free input* is exactly the `mix_nll` / `cat_ce` baselines here. Inducing the amplitude law through synthetic/augmented data is the `cat_aug` baseline, which is dominated even by plain CE. Here the law is imposed on the output distribution with a learned slope |
| MagNet (Mousavi & Beroza 2020) | CNN + BiLSTM regressor on un-normalized waveforms (amplitude retained), MSE | Run as the `magnet_nll` control (same inputs, Gaussian NLL). No structural amplitude constraint, no prior |
| Logit adjustment / balanced softmax / Prior2Posterior (Menon et al. 2021; Tian et al. 2020; Bhat et al. 2025); Balanced MSE (Ren et al. 2022) | Posterior ∝ model × label prior, with the prior known from label counts and used to **remove** training imbalance for a balanced test distribution | The prior factor here is **learned**, shape-constrained (free bulk, GR-linear tail) and **kept** at test time: the target is the natural distribution and bulk error must not rise. Its role is to let the x-dependent part stay smooth and parametric. A categorical head's bias vector is already such a factor; the gain (`mixgr` vs `cat_ce`) comes from the smooth-likelihood × global-prior factorization, not from having a prior |
| Deep imbalanced regression: LDS/FDS (Yang et al. 2021), heteroscedastic DIR (2026) | Reweighting / feature smoothing toward rare labels | `cat_lds` control: dominated (buys tail error with +8% bulk and 4× false alarms). The new method changes the posterior's structure, not the weighting |
| Scale/gain invariance in networks: scale-invariant classification stages, zero-mean convolutions for loudness invariance (ISMIR 2018), augmentation-induced homogeneity (2025), equivariant imaging for declipping (2026) | Output unchanged under gain, or gain equivariance induced through data | Here the output is a *distribution over a label* that must translate by a learned, input-dependent amount; exact by construction; combined with a prior factor that preserves it; justified by a Bayesian argument rather than a symmetry of the input domain alone |
| Previous project (this repository, Sept–Oct 2026): prior-response probes (q_α ∝ p·π^(α−1)), exposure-corrected CE, 11× tail-mass median | Post-hoc re-tempering of the prior of a trained categorical model; training-time prior correction; cost-sensitive decision | All operate on an already-learned categorical posterior or on the decision. None constrained the likelihood's amplitude response. Their negative results are consistent with the finding here that decision rules and reweighting move along the trade-off while the posterior structure moves the frontier |

## Not claimed as new

Mixture density heads; Gutenberg–Richter priors in Bayesian EEW; separating amplitude from
waveform shape as inputs; label-prior adjustment in classification; the tail-weighted
median as a cost-sensitive decision. The contribution is the specific combination, its
justification, and the controlled evidence that each component is necessary (`eq_nll`
without the prior hurts bulk; `mixgr_nll` without equivariance loses the M≥5 extrapolation).

## Tests run to check that the gain is real

* Leave-sequence-out 5-fold CV over all 1,159,249 records (346 M≥4, 31 M≥5 events), paired
  cluster bootstrap over aftershock sequences.
* Replication with 2 and 3 optimization seeds; ensemble-vs-ensemble comparisons.
* Frontier comparison at matched bulk error, so decision-rule shifts cannot masquerade as gains.
* Six baselines and three ablations on an identical trunk, data and schedule.
* Standard INSTANCE split (train 2005–17 → VAL 2018 / TEST 2019–20) with no selection.
* Mechanism diagnostic (amplitude response) on held-out folds.
* Held-station test (`*_hs` arms: 20% of stations withheld from training; metrics on
  held-event-and-held-station records) and a published-architecture control (`magnet_nll`).
  Results are logged in FINDINGS.md when complete.

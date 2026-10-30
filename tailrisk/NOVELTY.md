# Novelty audit: what is new, what is prior art, and what was done to check

Written 19 Oct 2026 after a bounded literature search (web search and primary-paper reads,
not a systematic review; absence from this list is not proof of absence). Each row names
the closest prior work and states the precise difference.

## Corrections from the 30 Oct literature review (LITREVIEW_2026-10-30.md)

* **κ = 1 precedent.** Zhang, Zhang & Tian 2021 (GRL) and the arXiv versions of Zhang & Zhang
  (2023) already predict a magnitude distribution over M − log A_max and add log A_max back: an
  exactly log-amplitude-equivariant predicted distribution with unit slope. The published 2024
  version of Zhang & Zhang feeds the log factor as an input instead (the row below describes only
  that version). The increments here are the learned, waveform-dependent slope κ(s), the mixture
  sharing the shift, and the learned GR-tail prior factor kept at test time. *Result of the
  κ ≡ 1 ablation (30 Oct):* on STEAD, GEOFON (capped) and INSTANCE the unit slope gives *lower*
  large-event error than the learned slope (by .03–.4), at .002–.01 more bulk error. Chile is the
  exception. So the learned slope buys bulk accuracy, not tail accuracy, and the large-event
  advantage over free networks comes from equivariance itself (shared by κ ≡ 1) and the GR factor.
* **The Gutenberg algorithm row was wrong.** Meier et al. 2015 state that their kNN densities are
  posteriors that already embed the GR × distance prior, and they combine stations by multiplying
  those posteriors (their eq. 5) without dividing the prior out; Yin 2018 multiplies them again as
  "likelihoods". So the field's own Bayesian algorithm makes the double-counting error the fusion
  study diagnoses. The Virtual Seismologist applies its prior once.
* **The fusion fix is textbook** (Kittler et al. 1998; Bayesian committee machine; hybrid HMM/ANN
  scaled likelihoods; ProbEn 2022; MVAE 2018; Geffner et al. 2023). What is new is its diagnosis
  and measurement in EEW and the non-identifiability of a learned factor's slope.
* **Propositions 1–3 rest on classical algebra** (Eddington/Malmquist; Tinti & Mulargia 1985;
  exponential tilting; truncated regression and SNPE proposal correction); their value is the
  design consequence, and they are presented as short, cited results.
* The "augmentation-induced homogeneity (2025)" row below could not be located and should be
  treated as unreferenced.

## Capped-training test: prior art (30 Oct; LITREVIEW_CAPPED_2026-10-30.md)

A focused search (web, full texts where reachable; publisher pages often blocked) found no study
of learned magnitude estimation that trains only below a magnitude cap and compares an
unconstrained network with a structurally constrained one on the events above it. The claim is
worded narrowly because of four neighbours: TEAM-LM (Münchmeyer et al. 2021b) studies how
saturation moves with training-set size and composition and tests incidentally on an event
0.4 units above its training maximum; TEAM (2021a) frames that event as an extrapolation test for
PGA; WaveCastNet (Lyu et al. 2025, Nat. Commun.) runs a deliberate capped design (simulations below
M4.5, tests to M7) for wavefield forecasting; and Zhang, Zhang & Tian (2021) / Zhang & Zhang
(2024) introduced the κ = 1 normalized-magnitude target without testing beyond their training
range. Dividing a network's output by its training sampling prior also appears in Münchmeyer,
Leser & Tilmann (2022). Confidence about 75–80% for the main venues; lower for low-visibility and
non-English venues.

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
| Bayesian EEW with a GR prior: Virtual Seismologist (Cua & Heaton 2007), Gutenberg algorithm (Meier et al. 2015), Yang et al. 2022 | Virtual Seismologist: parametric amplitude likelihoods × GR prior, prior applied once. Gutenberg algorithm: kNN posteriors over (M, log R) that embed the GR prior, multiplied across stations (prior counted per station). Meier et al. note magnitude saturation that depends on signal length | Same Bayesian structure, but the likelihood is a neural network trained end-to-end on waveforms; the GR structure is a constraint on that network's head, and the prior below completeness is learned rather than assumed. The equivariance proposition is, as far as found, not stated in this literature |
| TEAM-LM (Münchmeyer et al. 2021) | Gaussian-mixture magnitude head; magnitude resampling; saturation attributed to few large training events | Run as the `mix_nll` control (same trunk). The new method beats it with CIs excluding zero. TEAM-LM uses no prior factor and no equivariance |
| Zhang & Zhang 2024, "generalized earthquakes" | Per-station normalization with the log normalization factor as a separate input channel; synthetic training events scaled with the Hutton–Boore ML relation; Gaussian labels; large events augmented | Log amplitude as a *free input* is exactly the `mix_nll` / `cat_ce` baselines here. Inducing the amplitude law through synthetic/augmented data is the `cat_aug` baseline, which is dominated even by plain CE. Here the law is imposed on the output distribution with a learned slope |
| MagNet (Mousavi & Beroza 2020) | CNN + BiLSTM regressor on un-normalized waveforms (amplitude retained), MSE | Run as the `magnet_nll` control (same inputs, Gaussian NLL). No structural amplitude constraint, no prior |
| Logit adjustment / balanced softmax / Prior2Posterior (Menon et al. 2021; Tian et al. 2020; Bhat et al. 2025); Balanced MSE (Ren et al. 2022) | Posterior ∝ model × label prior, with the prior known from label counts and used to **remove** training imbalance for a balanced test distribution | The prior factor here is **learned**, shape-constrained (free bulk, GR-linear tail) and **kept** at test time: the target is the natural distribution and bulk error must not rise. Its role is to let the x-dependent part stay smooth and parametric. A categorical head's bias vector is already such a factor; the gain (`mixgr` vs `cat_ce`) comes from the smooth-likelihood × global-prior factorization, not from having a prior |
| Deep imbalanced regression: LDS/FDS (Yang et al. 2021), heteroscedastic DIR (2026) | Reweighting / feature smoothing toward rare labels | `cat_lds` control: dominated (buys tail error with +8% bulk and 4× false alarms). The new method changes the posterior's structure, not the weighting |
| Scale/gain invariance in networks: scale-invariant classification stages, zero-mean convolutions for loudness invariance (ISMIR 2018), augmentation-induced homogeneity (2025), equivariant imaging for declipping (2026) | Output unchanged under gain, or gain equivariance induced through data | Here the output is a *distribution over a label* that must translate by a learned, input-dependent amount; exact by construction; combined with a prior factor that preserves it; justified by a Bayesian argument rather than a symmetry of the input domain alone |
| Previous project (this repository, Sept–Oct 2026): prior-response probes (q_α ∝ p·π^(α−1)), exposure-corrected CE, 11× tail-mass median | Post-hoc re-tempering of the prior of a trained categorical model; training-time prior correction; cost-sensitive decision | All operate on an already-learned categorical posterior or on the decision. None constrained the likelihood's amplitude response. Their negative results are consistent with the finding here that decision rules and reweighting move along the trade-off while the posterior structure moves the frontier |

## The distance-marginalized form (added 20 Oct)

`eqdgr`: p(m|x) ∝ Σ_r p(r|s)·N(m; κ(s)(A−A₀) + G_r(s), σ_r(s)²)·exp φ(m), with r a log-distance
bin that is a *training label only* (joint likelihood p(r|x)·p(m|r,x) during training,
marginalized at inference). Closest prior art: the Gutenberg algorithm (Meier et al. 2015)
forms a joint magnitude–distance posterior from filter-bank amplitudes with hand-built
likelihoods and a GR prior; TEAM/TEAM-LM feed station coordinates and let the network infer
geometry; Hou et al. 2024 and DHLnet use differential arrivals or catalogue distance as inputs;
Kuyuk–Allen-type relations use catalogue distance. The difference here: the distance variable
is never an input, the per-distance likelihood is an exactly equivariant neural amplitude law,
and the mixture over distance hypotheses is learned jointly with the GR-factorized prior. Its
necessity is shown empirically: without equivariance the same distance mixing gives bulk gains
only (INSTANCE −.003 to −.006 bulk, no tail change; GEOFON no M≥7 change), and without distance
mixing the equivariant head loses on far-regional data. On a third catalogue (Northern Chile,
regional, three seeds) the distance-marginalized form beats the free mixture on bulk error at
every deadline and on M≥5/M≥6 error at 3–5 s, where the plain form loses the 1 s tail.

## Multi-station fusion (added 21 Oct)

Closest prior art: the Virtual Seismologist (Cua & Heaton 2007) multiplies parametric
per-station likelihoods and applies the GR prior once; the Gutenberg algorithm (Meier et al.
2015) multiplies per-station kNN posteriors that already embed the GR prior, so the prior is
counted once per station (corrected 30 Oct); network systems such as ElarmS average per-station magnitudes; TEAM/TEAM-LM
fuse stations inside the network. What is new here: (i) the demonstration, on three
catalogues and three seeds, that the natural fusion of *neural* posteriors (their product)
counts the training prior once per station and leaves M≥5–7 event estimates no better than
the nearest station alone (much worse at 1 s on INSTANCE, .67 → .92), with averaging no better; (ii) the proof that the tail slope of a
learned prior factor is not identified from single-station data (THEORY.md, Proposition 2),
so "prior counted once" with a learned factor is only correct when that factor happens to
match the catalogue's, which the measured slopes show is not generally the case; (iii) the
controlled comparison of the four rules across heads, showing that dividing out the empirical
training prior is the robust fix for any posterior, that the equivariant heads need it less,
and that they keep their large-event advantage at the event level on local/regional networks;
(iv) the follow-ups that bound the claim: pinning the factor's slope to the catalogue b-value
leaves single-station accuracy unchanged (the proposition's prediction) but is the right fusion
prior only for some heads and catalogues, a cross-fitted one-parameter tilt helps on Chile and
cannot serve bulk and tail on GEOFON, and in wall-clock time the naive product leaves the free
mixture's large-event estimate flat as stations arrive while the structured heads with the
prior divided out reach .3 units within four seconds of the first P on INSTANCE and Chile.

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
  held-event-and-held-station records) on INSTANCE and on Northern Chile, and a
  published-architecture control (`magnet_nll`).
* Capped-training extrapolation (Proposition 3): every head trained on Chile M < 5.0 only and
  scored on the 67 held-out M ≥ 5 events; the equivariant head's M ≥ 6 error is .53 at 5 s
  against 1.59 for the identically trained free mixture and .98 for the mixture with amplitude
  augmentation (30 Oct; INSTANCE capped at M4.0 and the κ ≡ 1 and MagNet baselines under the
  same cap follow).
  Results are logged in FINDINGS.md when complete.

# Scale-equivariant, Gutenberg–Richter-factorized magnitude posteriors for single-station early warning

*Draft, 19–20 October 2026. Numbers are from `FINDINGS.md`; slots marked ⟨pending⟩ are
filled when the corresponding run completes.*

## Abstract

Neural magnitude estimators for earthquake early warning underestimate the largest events.
We show on 1.16 million INSTANCE records that this is, in part, a structural failure of the
output distribution rather than only a shortage of large training events: on held-out large
earthquakes, free networks raise their estimate by only 0.39–0.54 magnitude units per tenfold
increase in ground motion when amplitudes exceed the training range, against 0.54–0.66 when
they fall below it. We propose a magnitude posterior of the form p(m|x) ∝ L_θ(m|A,s)·exp φ(m):
a Gaussian-mixture likelihood that is exactly equivariant to the log amplitude A of the
physical-unit waveform (component locations κ(s)(A−A₀)+g_k(s), with a learned slope κ and a
scale-free waveform descriptor s), multiplied by a single learned magnitude prior that is
free below the completeness magnitude and Gutenberg–Richter-linear above it. We prove that
under a Gutenberg–Richter prior, a log-linear amplitude law and self-similar waveform shape,
the exact Bayes posterior has this equivariance even when distance, path and site are
unknown, so the constraint removes learned saturation without forbidding Bayesian shrinkage.
In leave-sequence-out cross-validation with 346 M≥4 and 31 M≥5 events, three-seed ensembles
of the proposed model lower M≥4 error at 1, 3 and 5 s after the P arrival by .015/.015/.025
and M≥5 error at 3 and 5 s by .105/.149 relative to a TEAM-LM-style free mixture on the same
trunk, with bulk error equal or lower, better NLL, CRPS and Brier scores, and the same
decision rule. The gains hold on stations never seen in training, replicate across seeds in
36 of 45 seed×fold×deadline cells, and dominate plain cross-entropy, emphasized-Huber
training, amplitude-scaling augmentation, LDS reweighting and a feature-plus-boosting
baseline on the bulk/tail frontier. The cost is roughly one additional false M≥4 prediction
per 10⁴ small records at 1 s. The one sequence where the method loses, Emilia 2012, is one
whose large events carry local-magnitude labels, whose amplitude scaling differs from the
moment-magnitude slope the model learns. Fusing the stations of an event exposes a second
structural failure: the product of free neural posteriors counts the training prior once per
station, and on all three catalogues the fused M≥5–7 estimate is no better than the nearest
station alone; dividing out the training prior repairs it, and the equivariant heads keep the
best fused large-event and bulk error on the two local/regional networks.

## 1. Introduction

Early warning needs a magnitude estimate from the first seconds of P-wave motion at a
station. Deep networks trained on large catalogues (MagNet, TEAM-LM, CREIME and successors)
match or beat classical amplitude relations on average but are known to underestimate the
largest events, which the literature attributes to the scarcity of large training events
and, at short windows, to the rupture still being in progress. Both are real; this paper
isolates a third cause that is architectural and fixable.

The classical magnitude scales are themselves amplitude laws: M = log A + f(distance, site)
up to a scale-dependent slope. A network given the raw amplitude as an input can learn this
law only where it has data, and the data run out exactly where the law matters, at large
amplitudes. We measure the consequence directly (§5.3) and remove it by building the law
into the output distribution.

Contributions. (i) A scale-equivariant likelihood head whose predictive distribution
translates by κ(s)·log₁₀c when the ground motion is multiplied by c, with κ learned from the
scale-free shape; and its distance-marginalized form, Σ_r p(r|s)·L_eq(m|A,s,r), in which the
equivariant amplitude law is conditioned on an explicit distance variable that is a training
label only and is integrated out at inference. (ii) A learned, shape-constrained magnitude
prior factored out of the network and kept at test time: free in the bulk,
Gutenberg–Richter-linear in the tail. (iii) A proposition, checked numerically, that this is
the exact Bayes structure under a GR prior with unknown nuisances. (iv) A controlled
evaluation protocol for tail claims: leave-sequence-out folds over the whole catalogue, a
frontier comparison at matched bulk error so that decision rules cannot masquerade as better
posteriors, cluster-bootstrap intervals, seed replication, and held-station validation,
applied on three catalogues (INSTANCE, a GEOFON regional subset, Northern Chile). (v) Negative
results for the obvious alternatives, and an explicit map of where each component helps:
the prior factor and distance marginalization move bulk error, only the equivariant
likelihood moves the high-magnitude tail, and the plain equivariant head is the right prior
only where one amplitude law holds across the population. (vi) A multi-station fusion study
with a second proposition: the tail slope of a learned prior factor is not identified from
single-station data, so the prior a fusion rule must divide out is the training-label
distribution; the naive product of neural posteriors over-counts it and worsens large-event
estimates on every catalogue tested.

## 2. Related work

Bayesian early warning (Virtual Seismologist; the Gutenberg algorithm; Yang et al. 2022)
combines hand-built amplitude or frequency likelihoods with a Gutenberg–Richter prior; we
keep that structure and learn the likelihood from waveforms end-to-end. TEAM-LM uses a
Gaussian-mixture head and large-event resampling; it is our strongest baseline. Zhang & Zhang
(2024) separate amplitude from shape by feeding the log normalization factor as an input and
induce the scaling law with synthetic "generalized" events; both the free-amplitude-input
design and augmentation-induced symmetry are baselines here and lose. Logit adjustment,
balanced softmax and Balanced MSE use a *known* label prior to remove training imbalance; our
prior factor is learned, shape-constrained and retained because the target is the natural
distribution. Deep imbalanced regression (LDS/FDS) reweights; we show reweighting moves along
the bulk/tail trade-off rather than improving the posterior. Gain-invariant networks exist in
audio and vision, but as invariances of the input, not as an equivariance of a label
distribution with a learned, input-dependent slope. A fuller audit is in NOVELTY.md.

## 3. Method

### 3.1 Inputs

At deadline t ∈ {1, 3, 5} s after the catalogue P pick, the three-component prefix is
converted to physical units with the station sensitivity. We split it losslessly into
A = log₁₀ RMS over all samples and components, and s = (the prefix divided by its RMS,
eight log-amplitude ratios between components and between the first and last fifth of the
window, 34 static instrument/site fields, station coordinates, and the deadline). s is
invariant to a gain change by construction. No catalogue quantity (distance, depth,
magnitude type) is an input.

### 3.2 Likelihood

A residual 1-D CNN encodes the normalized prefix; an MLP maps [encoding, ratios, static,
deadline] to h(s). The head outputs mixture weights w_k(s), widths σ_k(s), offsets g_k(s)
and a slope κ(s) = 0.3 + 1.2·sigmoid(·), and sets component locations

    μ_k(x) = κ(s)·(A − A₀) + g_k(s).

Labels are reported to 0.1, so the likelihood of a label y is the mixture mass on
[y−0.05, y+0.05) (interval-censored), which makes the categorical and continuous heads
directly comparable. Multiplying the ground motion by c leaves s unchanged and adds log₁₀c
to A, so the whole predictive distribution translates by κ(s)·log₁₀c exactly.

### 3.3 Prior factor

The posterior is p(b|x) ∝ P_mix(b|x)·exp φ_b over 0.1-wide bins b from −1.0 to 8.5, where φ is
a free vector below M_C = 3.5 and φ_b = φ(M_C) + β(c_b − M_C) above. Because an exponential
factor times a Gaussian mixture is a shifted mixture, the head stays exactly equivariant
wherever φ is linear, i.e. for all large events. φ and β are learned jointly with the
network by maximum likelihood.

### 3.4 Why this is the Bayes structure

Assume M ~ 10^(−bM), A = κM + h(z) + ε with nuisances z (distance, depth, site, path,
instrument) independent of M, and p(s|M,z) independent of M. Then p(M|A+κδ, s) = p(M−δ|A, s)
for every δ (THEORY.md gives the two-line proof: the marginal over z depends on A and M only
through A−κM, and the prior ratio is a constant). Under GR, Bayesian shrinkage is therefore a
constant shift, never a discount for being large. `test_theory.py` verifies this to 10⁻¹⁵ with
an arbitrary non-linear h and a broad unknown-distance distribution, and shows that a
selection cliff in the prior (INSTANCE has a 9× step at M2.0) breaks the identity only where
the posterior straddles the cliff, which is why the prior is free below M_C.

### 3.5 Decisions

For a loss that weights M≥4 errors r times more than others, the Bayes action is the
tail-weighted median a_r of the posterior. r = 1 is the median; r > 1 recovers the "multiply
tail mass and take the median" rule of earlier work. Sweeping r traces, for a fixed posterior,
the best achievable bulk/tail trade-off, so we compare posteriors by their frontiers at
matched bulk error, and report the median and mean actions as fixed rules.

### 3.6 Multi-station fusion

For k stations of one event, Bayes gives p(m | x₁..x_k) ∝ Π_i L(m|x_i) · π(m): the prior is
counted once. A posterior with no identifiable prior factor can only be multiplied, which
counts the prior k times, averaged, or divided by an assumed prior before multiplying. The
second proposition (THEORY.md) shows that the factor learned here is only determined up to an
exponential tilt in the GR tail, because a tilted Gaussian mixture is again a Gaussian mixture
with shifted components; single-station training therefore cannot pin the slope, and the prior
to divide out is the label distribution the posteriors were trained under. Section 5.7 compares
the four rules.

## 4. Data and protocol

INSTANCE: 1,159,249 three-component records from 54,008 Italian events (2005–2020), labels
mostly M_L with M_w for most events above M4. All records are pooled and split into
Gardner–Knopoff aftershock sequences, visited largest-first so that background seismicity is
not chained; sequences go to five folds balancing M≥5, M≥4 and record counts. Fold 0 is the
entire 2016–17 Central Italy sequence (M6.5, 43% of records), fold 1 is the 2012 Emilia
sequence. Every record receives one out-of-fold prediction. Intervals are 95% percentile
intervals from a paired bootstrap that resamples whole sequences (1,000 replicates).

All arms share the trunk, inputs, folds, batch order and a fixed schedule (10 epochs, AdamW
2·10⁻³, cosine, one network for all three deadlines, 57–65 min per arm on one A10G); nothing
on a held-out fold is selected. Parameter counts differ by < 0.3% between heads.

Baselines: categorical cross-entropy (71 bins); the previous project's emphasized-Huber + CE
recipe; TEAM-LM-style free Gaussian mixture with A as an input (`mix`); amplitude-scaling
augmentation (×10^Δ with label +Δ); LDS reweighting; an E3WS-style P-wave-feature gradient
boosting model; a MagNet-style CNN+BiLSTM on amplitude-retaining waveforms (a short-window
adaptation of a 30 s architecture; it trails every arm on the shared trunk by ≈.07–.12 bulk
and ≈.25 M≥4 MAE, which establishes that the trunk is strong rather than saying much about
MagNet at its own window).
Ablations: equivariance without the prior factor (`eq`); the prior factor without
equivariance (`mixgr`); separate M_L/M_w slopes (`eqtgr`); a distance-aware variant (`eqdgr`).

## 5. Results

### 5.1 Main comparison

Three-seed ensembles, median action, Δ = eqgr − mix (95% intervals):

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0008 [−.0021, +.0000] | −.0015 [−.0031, −.0003] | −.0028 [−.0039, −.0020] |
| Δ M≥4 MAE | −.015 [−.023, −.005] | −.015 [−.026, −.003] | −.025 [−.042, −.009] |
| Δ M≥5 MAE | −.024 [−.075, +.028] | −.105 [−.220, −.010] | −.149 [−.291, −.040] |
| Δ false-M4 per 10⁴ small records | +1.5 [+1.0, +2.3] | +0.65 [+0.05, +1.02] | +0.63 [+0.03, +1.04] |

Against plain cross-entropy (three-seed ensembles) the margins are larger: M≥4
−.033/−.045/−.057, M≥5 −.083/−.199/−.262, bulk −.0009/−.0029/−.0046, with a lower false-M4
rate at 1 s. Absolute values for the eqgr ensemble: bulk
.320/.263/.230; M≥4 .737/.553/.497; M≥5 1.010/.638/.537. On the unseen Central Italy sequence,
5 s M≥5 MAE falls from 1.008 (CE) to 0.502.

### 5.2 Frontier and dominated alternatives

Every baseline is dominated on the bulk/tail frontier at all three deadlines. The
emphasized-Huber recipe, augmentation and LDS lower M≥4 error at their default operating
points only by raising bulk error (+.006, +.010, +.028 at 1 s) and false alarms (LDS: 4×);
plain CE reaches the same tail error with less bulk error than any of them. The feature +
boosting model is far weaker (5 s bulk .310 vs .240).

### 5.3 Mechanism

On held-out M≥4 records, multiplying the waveform by 10 raises the median of the categorical
model by .46/.44/.39 units at 1/3/5 s in the Central Italy fold, and by .53/.54/.51 for the free
mixture with the prior factor, against .54–.66 for a tenfold decrease. The equivariant head
responds by its learned κ ≈ .61–.77 in both directions. The probabilistic counterpart: the
free mixture is under-confident for M≥5 (predicted .14 → observed .20; .42 → .55 at 5 s)
while eqgr sits near the diagonal; both are otherwise well calibrated (Brier reliability
terms ≤ 4·10⁻⁵), and eqgr's lower Brier scores for P(M≥4) and P(M≥5) at 3 and 5 s come from
higher resolution.

### 5.4 Ablations

Three seeds each, sign tests over 45 seed×fold×deadline cells. The prior factor alone
(`mixgr`) is a strict Pareto improvement over the mixture (bulk better in 40/45, M≥4 in 31/45).
Equivariance on top of it buys the tail (M≥4 better in 35/45, M≥5 in 30/45) for a median
+.0006 bulk MAE, still below the baseline's bulk. Equivariance without the prior factor
costs +.005 bulk MAE at 1 s, because a smooth likelihood cannot represent the M2.0
selection cliff. Separate M_L/M_w slopes do not help. The distance-aware variant gives the
largest M≥5 gains (three-seed ensembles −.12/−.17/−.19 vs mix; single seeds −.14/−.17/−.18,
replicated) with lower bulk error (−.0008/−.0032/−.0047) but doubles the 1 s false-alarm rate.
Averaging its posterior with the prior-only model removes that cost: size-matched, the six-model
average mixgr + eqdgr against the six-model free + prior-only average mix + mixgr has bulk
−.0033/−.0042/−.0047, M≥4 −.017/−.018/−.021 and M≥5 −.077/−.118/−.129 (3 and 5 s intervals
exclude zero) at +1 false alarm per 10⁴ confined to 1 s. Its own ablation, the same distance
mixing without equivariance (`mixdgr`), has the best bulk error of any single model
(−.003/−.004/−.006 vs mix) and no tail gain (M≥5 +.065 at 1 s, otherwise n.s.): across both
datasets, the prior factor and distance mixing move bulk error, and only the equivariant
likelihood moves the high-magnitude tail.

### 5.5 Robustness

*Seeds.* eqgr beats the mixture on M≥4 error in 36/45 cells; all nine exceptions are the
Emilia fold. *Held stations.* With 20% of stations withheld from training, on records whose
station and event were both unseen (279,812 records, 341 M≥4 events): M≥5 −.068/−.111/−.139
(all CIs exclude zero), M≥4 −.017/−.005/−.011 (significant at 1 and 5 s), bulk never worse,
false-M4 rate lower (1.2 vs 2.9 per 10³ at 1 s) and CVaR95 lower at every deadline; the
distance-marginalized head keeps the largest M≥5 gain there, −.158 / −.201 [−.345,−.060] /
−.217 [−.365,−.066], at equal bulk error and false-M4 rate (M≥5 MAE at 5 s: mixture .771,
plain head .624, distance-marginalized .538). *Standard
split* (train 2005–17, VAL 2018): M≥4 −.025/−.022/−.038 vs the mixture with bulk equal or
better. *Training length.* At 20 epochs the eqgr − mix differences are unchanged (bulk
−.000/−.002/−.004, M≥4 −.014/−.011/−.017, M≥5 −.098/−.110 at 3/5 s), while doubling the epochs
itself moves both heads along the trade-off (+.004–.005 bulk, −.02 M≥4). *Capacity.* With a
1.5×-wide trunk (2.2× parameters) the differences are unchanged or larger (bulk
−.002/−.003/−.003, M≥4 −.018/−.021/−.027, M≥5 −.109/−.133 at 3/5 s); a 2.2×-larger free
mixture reaches the standard eqgr's M≥4 error but not its M≥5 or bulk error.

*Second dataset (negative for the equivariant component).* On a GEOFON subset (31,020
records within 2,000 km, 2,212 events, 276 M≥6 and 50 M≥7, labels mostly mb, 78% of traces at
20 Hz), the same code gives the opposite ordering: eqgr is worse than the free mixture by
+.015/+.014/+.013 bulk and +.043/+.053/+.060 M≥6 MAE (CIs exclude zero), while the prior factor
alone is neutral on bulk and slightly better on M≥6 (−.008/−.009/−.004). The free mixture
saturates on this data as well (upward response .34–.46 per decade vs .49–.55 downward on
M≥6), and the equivariant head responds symmetrically with κ ≈ .57, yet it is less accurate.
Allowing κ → 0 does not help (three seeds), nor do scale-specific slopes, so the rigidity is in
the single additive attenuation offset κ(s)·A + g(s): at 300–2,000 km the attenuation term
spans several magnitude units and must be inferred from the waveform shape. Making the
equivariant likelihood conditional on an explicit distance variable and marginalizing it
(`eqdgr`, distance used only as a training label) recovers the largest events: M≥7 MAE
−.094/−.089/−.123 (three-seed ensembles, CIs exclude zero; M≥7 bias −1.45 vs −1.55 at 1 s) at a
bulk cost of +.016–.024. The same distance marginalization without equivariance (`mixdgr`)
gains nothing at M≥7 (−.014/+.015/+.020), so on this data equivariance is necessary but not
sufficient. The GR prior factor alone is neutral on bulk and slightly better at M≥6 (−.003).
The honest summary across datasets: the amplitude-equivariant structure is the right prior
where a single amplitude law holds across the population (local networks like INSTANCE),
must be conditioned on distance where attenuation dominates (far-regional data like GEOFON),
and in the latter regime it improves only the largest events while costing bulk error.

*Third dataset (Northern Chile, regional).* A single-station cache built from the TEAM-LM
release (505,666 station traces picked with STA/LTA + AIC from 67,284 events at 40–230 km;
67 M≥5 and 12 M≥6 events; m/s units, MA labels). Three-seed ensembles against the free-mixture
ensemble: the plain equivariant head is worse at 1 s (bulk +.0008 [+.0002,+.0014], M≥5 +.049
[+.024,+.079]) but wins the tail at 3 and 5 s (M≥5 −.038 [−.070,−.001] / −.089 [−.133,−.040];
the twelve M≥6 events: −.25 [−.42,−.06] / −.38 [−.57,−.21] units) at equal (3 s) or lower
(5 s, −.0012) bulk. The distance-marginalized equivariant head beats the free mixture on bulk
at every deadline, −.0024 [−.0033,−.0015] / −.0042 [−.0052,−.0034] / −.0057 [−.0070,−.0047],
negative in all nine seed × deadline cells, with the same large-event gains at 3 and 5 s
(M≥5 −.043 [−.074,−.006] / −.090 [−.137,−.040]; M≥6 −.28 [−.40,−.15] / −.39 [−.57,−.23]) and
an equal tail at 1 s; the prior factor alone is neutral on every axis. The mean action gives
the same picture (5 s: bulk −.0055, M≥5 −.071, M≥6 −.32, CIs exclude zero). The size-matched
comparison of §5.4 repeats here: the six-model average of the prior-only and distance-marginalized
heads beats the six-model free + prior-only average on bulk at every deadline (−.0033 / −.0040 /
−.0049) and on M≥5 and M≥6 at 3 and 5 s (−.061 / −.088 and −.25 / −.33), all intervals excluding
zero, with no false-alarm cost. With 7 of the 22 stations withheld from training (seed 1),
records at unseen stations show a bulk gain at least as large as on seen stations (−.0041
[−.0074,−.0006] / −.0131 [−.0154,−.0102] / −.0099 [−.0132,−.0069]) and a same-signed 5 s
large-event gain (M≥6 −.23) that is not significant with the 10 M≥6 events recorded there; on
seen stations the full-data pattern repeats (M≥5 −.094 / −.126 at 3 / 5 s). Across the three
catalogues the distance-marginalized form is therefore the most
portable member of the family: on INSTANCE it has the largest M≥5 gains with lower bulk
error (and a higher 1 s false-alarm rate), on GEOFON it is the only arm that improves M≥7,
and on Chile it dominates. The plain form is its collapse to a single distance hypothesis,
which suffices on a dense local network.

### 5.6 What does not improve

The worst 1% of errors over all records (CVaR99) are unchanged; they are dominated by
records whose waveform carries little magnitude information at the deadline. At 1 s the M≥5
difference is within noise. In the Emilia sequence, where the large events carry M_L labels,
the method is worse than the mixture (M≥4 +.06 at 1–3 s): one learned slope near the M_w
value under-responds to amplitude for M_L labels, which scale about 1:1 with amplitude.

### 5.7 Multi-station fusion

Stations of an event are combined, nearest first, each contributing its d-second posterior;
event-level MAE over events with at least k usable stations, three seeds per catalogue
(`results/multistation_summary_*.md`). With every station of the event (median 15 on INSTANCE),
the free mixture's posterior product has M≥5 / M≥6 / M≥7 error of .600 / .846 / 1.071 at 5 s on
INSTANCE / Chile / GEOFON against .629 / .790 / .999 for its nearest station alone, and .921
against .670 at 1 s on INSTANCE; the posterior mean is no better. Dividing each posterior by the
fold's smoothed training-label histogram before multiplying gives .252 / .526 / .603 (CIs
against the product exclude zero in every seed and deadline). The equivariant heads are less
sensitive to the rule (their products still improve with k on INSTANCE and Chile), start from
better nearest-station estimates (5 s: .432 vs .629 on INSTANCE, .300 vs .790 on Chile), and
with the best rule per head reach .207 (plain) and .226 (distance-marginalized) on INSTANCE
against the mixture's .252 (plain-head difference −.038 [−.074,−.001], three seeds negative at
every deadline), .199 and .221 on Chile against .526 (−.337 [−.581,−.121]), and .609 on GEOFON
against .603 (a tie). On the fused bulk the distance-marginalized head with its own factor
counted once is best at every deadline on INSTANCE (−.007 / −.008 / −.007 against the mixture's
best rule, three seeds) and at 3–5 s on Chile. The learned factor is the right prior to divide
out only when its slope matches the catalogue's: measured slopes are −1.85 (distance-marginalized
head, INSTANCE), −0.81 (plain), −0.17 (prior-only) and +0.02 on GEOFON for every head, against
catalogue slopes of −2.29, −1.79 and −1.32 nats per unit, and fusion quality with the learned
factor tracks that match exactly as the proposition predicts. The histogram rule is the robust
fix for any posterior but needs a smoothing and floor choice and costs bulk error where
posteriors are broad (GEOFON +.03 for the mixture); across smoothing widths of 0.1–0.5 and
floors of 10⁻⁴–10⁻⁶ its fused M≥5 error on INSTANCE moves by ±.06 for the mixture while the
plain equivariant head stays better at 3 and 5 s in every setting, and the distance-marginalized
head, whose broad posteriors make the rule floor-sensitive (.19–.49), is better served by its own
factor, which needs no such choice. The signed bias of the fused M≥5 estimates makes the
mechanism visible: the naive product is more biased than the nearest station alone (mixture
−.93 / −.67 / −.62 against −.62 / −.56 / −.53 at 1 / 3 / 5 s), the histogram rule leaves −.25 /
−.22 / −.15, the plain head with its flat learned factor stays at −.69 / −.38 / −.29, and the
distance-marginalized head with its own factor is nearly unbiased (−.13 / +.06 / +.05).

## 6. Limitations

Three catalogues, but one trunk and one training recipe; mixed magnitude types; catalogue P picks
rather than an online picker; a sequence-based rather than physically certified independence
structure; the comparisons are to re-implementations of baseline ideas on a shared trunk, not
to the authors' code. The method does not help where the waveform is uninformative, and its
false-alarm cost at 1 s, while small, is real. The learned prior factor's tail slope is not
identified, so fusion with it is only correct by coincidence; pinning the slope to the
catalogue b-value during training is the obvious remedy and was not run. The fusion study orders
stations by distance rather than by measured arrival and gives every station the same window.

## 7. Conclusion

Building the amplitude law and the Gutenberg–Richter prior into the output distribution of a
deep magnitude estimator removes a measurable, learned saturation and lowers high-magnitude
error at 1, 3 and 5 s without worsening bulk error, with a Bayesian justification and
controlled, replicated evidence. The structure is independent of the trunk and should apply
to any waveform encoder and any amplitude-defined magnitude.

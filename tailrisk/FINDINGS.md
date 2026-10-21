# Findings log (newest first)

All numbers are pooled out-of-fold predictions over 1,159,249 INSTANCE records (346 M≥4
events, 31 M≥5) from 5 leave-sequence-out folds. Δ = arm − reference, with 95% cluster-bootstrap
intervals (1,000 replicates; whole GK sequences resampled). Negative Δ in an error is better.

## 2026-10-21 01:40 UTC — Multi-station fusion: the naive product of free posteriors makes large-event estimates *worse* as stations are added; dividing out the training prior repairs it; the equivariant heads keep their advantage at the event level on INSTANCE and Chile, tie on GEOFON

**Question.** EEW systems combine stations. For a factorized posterior p(m|x) ∝ L(m|x)·π(m),
Bayes gives p(m|x₁..x_k) ∝ Π_i L(m|x_i)·π(m) with the prior counted once. A posterior with no
identifiable prior factor can only be multiplied (Π p_i: prior counted k times), averaged, or
divided by an *assumed* prior before multiplying. Four rules were compared on every head
(`multistation.py`; stations ordered by hypocentral distance as a proxy for arrival order,
each with the same d seconds; events with ≥ k usable stations; event-level MAE, median
action; cluster bootstrap over sequences; three seeds per dataset):

* `post_prod` Π_i p(m|x_i) — the naive rule;
* `post_mean` (1/k) Σ_i p(m|x_i);
* `hist_adj` Π_i p(m|x_i)/π̂(m) · π̂(m), π̂ = the fold's training-label histogram, smoothed
  (σ = 0.25) and floored (10⁻⁵) — the logit-adjustment analogue, available to any posterior;
* `lik_prior` Π_i [p(m|x_i)/e^φ(m)] · e^φ(m), with φ the head's own learned prior factor
  (GR heads only).

Full-precision log-posteriors were re-exported from the fold checkpoints (`export_logpmf.py`;
the saved float16 PMFs underflow in the tail). Tables: `results/multistation_summary_*.md`
(every k, every deadline, per seed); figures `figures/multistation_*_s1.png`.

**1. The naive product fails on large events, on all three catalogues** (three-seed means,
event-level MAE at 1 / 3 / 5 s, k = all stations of the event, median ≈ 15 stations on INSTANCE):

| | nearest station only | Π posteriors (naive) | posterior mean | ÷ training prior (`hist_adj`) |
|---|---|---|---|---|
| INSTANCE M≥5 (31 events), free mixture | .670 / .649 / .629 | **.921 / .651 / .600** | .932 / .655 / .603 | .331 / .264 / .252 |
| Chile M≥6 (12), free mixture | 1.022 / .798 / .790 | **1.281 / .870 / .846** | 1.234 / .794 / .780 | .840 / .547 / .526 |
| GEOFON M≥7 (50), free mixture | 1.546 / 1.150 / .999 | **1.562 / 1.226 / 1.071** | 1.517 / 1.219 / 1.069 | .864 / .693 / .603 |

Adding every station of the event to the free mixture's posterior product leaves the M≥5 /
M≥6 / M≥7 error equal to or *worse* than the nearest station alone (INSTANCE 1 s: .67 → .92).
This is prior over-counting (THEORY.md, Proposition 2): each posterior carries the
Gutenberg–Richter prior, so the product carries it k times and is pulled toward the bulk.
Averaging does not help. Dividing each posterior by the training-label histogram before
multiplying removes it: .25 / .53 / .60 at 5 s. Seeds agree (every one of the 9 seed ×
deadline cells has the naive product worse than `hist_adj` on the top tail, CIs exclude zero).

**2. The equivariant heads are far less sensitive to the rule, and their nearest-station
estimates are already better** (same layout; eqgr = plain, eqdgr = distance-marginalized):

| | nearest station | Π posteriors | `hist_adj` | own factor once (`lik_prior`) |
|---|---|---|---|---|
| INSTANCE M≥5, eqgr | .548 / .379 / .432 | .889 / .514 / .392 | .304 / .202 / .207 | .698 / .401 / .309 |
| INSTANCE M≥5, eqdgr | .621 / .728 / .616 | .733 / .346 / .277 | .262 / .221 / .229 | **.273 / .203 / .226** |
| Chile M≥6, eqgr | .811 / .397 / .300 | 1.146 / .361 / .235 | .730 / .314 / .226 | 1.017 / .342 / .221 |
| Chile M≥6, eqdgr | .736 / .384 / .299 | 1.241 / .339 / .212 | .751 / .302 / .217 | 1.032 / .319 / **.199** |
| GEOFON M≥7, eqgr | 1.621 / 1.197 / .972 | 1.630 / 1.231 / 1.066 | 1.027 / .873 / .687 | 1.636 / 1.236 / 1.070 |
| GEOFON M≥7, eqdgr | 1.362 / 1.025 / .802 | 1.450 / 1.131 / .956 | 1.039 / .728 / .609 | 1.458 / 1.136 / .961 |

* With the best rule for each head, at all stations and 5 s: INSTANCE M≥5 eqgr .207 and
  eqdgr .226 against the mixture's .252; Chile M≥6 eqdgr .199 and eqgr .221 against .526;
  GEOFON M≥7 eqdgr .609 against .603 (tie). Paired against the mixture's `hist_adj`
  (seed 1; sign over three seeds): INSTANCE eqgr `hist_adj` M≥5 −.001 / −.058 / **−.038
  [−.074,−.001]** (3/3 seeds negative at every deadline); eqdgr `lik_prior` −.051 / −.054 /
  −.012 (3/3 negative; CIs include zero with 31 events). Chile eqdgr `lik_prior` M≥6 −.170
  [−.308,+.029] / **−.337 [−.581,−.121]** at 3 / 5 s and eqgr `lik_prior` **−.316
  [−.531,−.134]** at 5 s (3/3 negative). GEOFON: the mixture's `hist_adj` is as good as any
  rule of any head on M≥7 (eqdgr `hist_adj` +.008 [−.098,+.109]; eqgr +.126 [−.009,+.262]).
* **Bulk (all events, event level) at all stations** is where the factorized rule pays:
  INSTANCE eqdgr `lik_prior` .239 / .190 / .168 and eqgr `lik_prior` .243 / .192 / .168
  against the mixture's best (`hist_adj`) .250 / .201 / .176 — Δ = **−.007 [−.016,+.002] /
  −.008 [−.011,−.004] / −.007 [−.009,−.004]** for eqdgr (3/3 seeds negative at every
  deadline); Chile eqdgr `lik_prior` .106 / .082 / .073 vs .102 / .084 / .078 (3 s −.002,
  5 s **−.004 [−.006,−.003]**, 3/3). On GEOFON the histogram rule costs bulk (+.03 for the
  mixture at 5 s; it destroys eqdgr's broad posteriors: 1.02) while the factorized rule does
  not (eqdgr `lik_prior` .350 vs the naive .348).

**3. Why the learned prior factor is only sometimes the right prior to divide out.** Proposition 2
(THEORY.md) shows that the tail slope of the factor is not identified from single-station
data: an exponential tilt of a Gaussian mixture is a shifted mixture, so any slope can be
absorbed by the likelihood head. The learned slopes confirm this — they are arbitrary and
differ by head and catalogue, and fusion with the learned factor works exactly where the
slope happens to be close to the catalogue's:

| catalogue (empirical ln-density slope above M3.5–4.8) | eqgr β | mixgr β | eqdgr β | `lik_prior` vs `hist_adj` at 5 s, top tail |
|---|---|---|---|---|
| INSTANCE (−2.29 / unit, b = 1.00) | −0.81 | −0.17 | **−1.85** | eqdgr: equal (.226 vs .229); eqgr: worse (.309 vs .207) |
| Chile (−1.79, b = 0.78) | −0.60 | −0.04 | −0.46 | eqdgr: better (.199 vs .217); eqgr: equal; both worse at 1 s |
| GEOFON (−1.32, b = 0.57) | +0.02 | +0.02 | +0.02 | identical to the naive product (flat factor) |

(β in nats per magnitude unit, mean over folds.) mixgr's factor is nearly flat on every
catalogue, so its `lik_prior` is the naive product in disguise (INSTANCE M≥5 .878 / .604 /
.534); eqgr's is flatter than the catalogue's, so counting it once under-corrects; eqdgr's is
close to the catalogue's on INSTANCE and its rule is the best there on both axes. **The prior
a fusion rule must divide out is the label distribution the posteriors were trained under,
not a learned factor whose slope is free.** A model whose factor is pinned to the catalogue
b-value during training (β fixed, not learned) would make the two coincide; that is the
natural next experiment and was not run.

**4. Practical reading.** (i) Never multiply free neural posteriors across stations without
dividing out the training prior: on all three catalogues the naive product makes M≥5–7
estimates worse than the nearest station alone, by up to .25 units. (ii) The histogram rule
is a one-line fix but needs a smoothing/floor choice and is fragile where posteriors are broad
(GEOFON bulk +.03 to +.7). (iii) The structured heads give better single-station estimates of
large events (nearest station: INSTANCE eqgr .43 vs .63, Chile .30 vs .79 at 5 s) *and* better
fused bulk error at every deadline; at the fused tail they are better on INSTANCE and Chile
and tie on GEOFON. (iv) The decision rule matters less than the fusion rule: all numbers are
medians; mean-action values are in the JSONs.

Sensitivity of `hist_adj` to σ and floor and the INSTANCE held-station eqdgr arm are reported
below when complete.

## 2026-10-20 21:20 UTC — Chile held-station test: the distance-marginalized head's bulk gain is at least as large on unseen stations; its tail gain there is same-signed at 5 s but underpowered (10 M≥6 events)

Arms retrained with 7 of the 22 Chile stations withheld from training in every fold
(`--hold-stations 0.2`, rng 0; `queue_chile_hs.txt`; seed 1; 32% fewer training records).
Records at held stations (held event *and* held station) and at seen stations are evaluated
separately with `geofon_eval.py --station-subset`, Δ = arm − mix_nll_hs, median action
(`chile_eval_hs_held.json`, `chile_eval_hs_seen.json`).

**Held stations** (165,670 records; 58 M≥5, 10 M≥6 events). Absolute mix_hs: bulk .259 / .252 /
.250; M≥5 .927 / .726 / .701; M≥6 1.366 / 1.011 / 1.026. Every arm is worse on unseen stations
than on seen ones (bulk ≈ +.05 at 1 s), the usual station-generalization gap.

| | bulk 1 / 3 / 5 s | M≥5 MAE 1 / 3 / 5 s | M≥6 MAE 1 / 3 / 5 s |
|---|---|---|---|
| eqgr_hs | +.0039 / +.0027 / +.0024 (n.s.) | **+.086 [+.030,+.159]** / −.008 / −.056 | +.186 / −.215 / −.300 (n.s.) |
| **eqdgr_hs** | **−.0041 [−.0074,−.0006] / −.0131 [−.0154,−.0102] / −.0099 [−.0132,−.0069]** | +.047 / +.011 / −.059 (n.s.) | +.052 / −.092 / −.233 (n.s.) |

**Seen stations** (339,996 records; 67 M≥5, 12 M≥6). eqdgr_hs: bulk −.0018 (n.s.) / **−.0045
[−.0054,−.0034] / −.0076 [−.0085,−.0066]**; M≥5 −.010 / **−.094 [−.127,−.059] / −.126
[−.169,−.086]**; M≥6 +.019 / **−.348 [−.529,−.222] / −.422 [−.633,−.273]**. eqgr_hs: bulk
**+.0027 / +.0018** / +.0002; M≥5 **+.062** / **−.061 / −.107**; M≥6 +.135 / **−.325 / −.425**.
The full-data three-seed pattern (20:10 entry) repeats on the seen-station subset.

* The distance-marginalized head's bulk advantage is at least as large on unseen stations
  (−1.6% / −5.2% / −4.0% of the mixture's error) as on seen ones (−0.9% / −2.6% / −4.9%):
  a per-distance amplitude law with a learned distance mixture transfers to stations never
  seen in training at least as well as the free mixture's station-specific fit.
* Its large-event gain on unseen stations has the same sign as on seen stations at 5 s
  (M≥6 −.23 vs −.42; M≥5 −.06 vs −.13) but, with 10 M≥6 events recorded at 7 stations, the
  intervals include zero; at 1 and 3 s the held-station M≥5 point estimates are slightly
  positive (+.05, +.01, n.s.). On Chile the held-station evidence therefore supports the bulk
  claim and is inconclusive for the tail; the held-station test with power for the tail claim
  is the INSTANCE one (19 Oct entry), where the eqgr gain survived on unseen stations.
* eqgr_hs repeats its full-data behaviour on both subsets: worse at 1 s, better large-event
  estimates at 3–5 s (significant on seen stations, not on held).

## 2026-10-20 20:10 UTC — Chile, three seeds: the distance-marginalized equivariant head beats the free mixture on bulk at every deadline and on the tail at 3 and 5 s; every seed agrees

Three-seed ensembles (each arm = mean of its three seeds' posteriors; `chile_eval_ens3.json`),
Δ = arm − mix_nll ensemble, median action. Absolute mix ensemble: bulk .203 / .159 / .143;
M≥5 .845 / .580 / .553; M≥6 1.287 / .847 / .855 (12 events; bootstrap replicates without an
M≥6 event are dropped, so M≥6 intervals are now reported).

| | bulk 1 / 3 / 5 s | M≥5 MAE 1 / 3 / 5 s | M≥6 MAE 1 / 3 / 5 s |
|---|---|---|---|
| eqgr | **+.0008** / +.0001 / **−.0012** | **+.049 [+.024,+.079]** / **−.038 [−.070,−.001]** / **−.089 [−.133,−.040]** | +.062 / **−.248 [−.423,−.060]** / **−.377 [−.566,−.215]** |
| mixgr | +.0000 / **+.0002** / +.0002 | +.006 / +.001 / −.005 | **+.023** / −.022 / −.022 |
| **eqdgr** | **−.0024 [−.0033,−.0015] / −.0042 [−.0052,−.0034] / −.0057 [−.0070,−.0047]** | +.002 / **−.043 [−.074,−.006]** / **−.090 [−.137,−.040]** | −.014 / **−.276 [−.399,−.148]** / **−.385 [−.565,−.230]** |

M≥5 event-MAE follows the record-level numbers (eqdgr −.009 / **−.047 [−.077,−.010]** /
**−.095 [−.145,−.040]**). Absolute M≥6 MAE at 5 s: mix .855, mixgr .835, eqgr .479,
**eqdgr .472**; the M≥6 bias moves from −.86 (mix) to −.28 (eqdgr). Under the mean action the
5 s picture is the same (eqdgr bulk −.0055 [−.0065,−.0047], M≥5 −.071 [−.114,−.026], M≥6
−.324 [−.508,−.155]), so the gain is not a property of the decision rule.

**Seed consistency** (single seeds, each Δ against the same-seed free mixture, `chile_eval_seed{1,2,3}.json`):

* eqdgr bulk is negative with a CI excluding zero in **9 of 9** seed × deadline cells
  (−.0019 to −.0059). M≥5 MAE is negative in 3/3 seeds at 3 s (−.034 / −.033 / −.051) and
  at 5 s (−.086 / −.083 / −.090); M≥6 −.23 / −.28 (3 s) and −.36 / −.39 (5 s) in seeds 2–3
  (seed 1's M≥6 interval was not computable before the finite-replicate fix). At 1 s the M≥5
  sign varies (−.012 / +.016 / +.005): no 1 s tail effect either way.
* eqgr is worse at 1 s on M≥5 in 3/3 seeds (+.045 / +.063 / +.049) and better at 5 s in 3/3
  (−.076 / −.082 / −.090); its bulk sign varies (+.0017 / +.0019 / +.0008 at 1 s, ≈0 at 5 s).
* mixgr has no consistent sign on any tail metric (e.g. 5 s M≥5 −.010 / +.012 / −.015).

**Reading.**

* On this regional network (40–230 km) both equivariant heads reach the same large-event
  accuracy at 3 and 5 s. What the distance marginalization adds is the 1 s tail (eqgr +.05,
  eqdgr ±0) and the bulk (eqgr ≈ 0, eqdgr −1.2% to −4%): one amplitude law across all
  distances is too rigid where attenuation varies across the population, and the
  per-distance law with a learned mixture over distance hypotheses fixes it without any
  distance input at test time.
* With three seeds on all three catalogues the attribution is settled. The prior factor
  alone (`mixgr`) never moves the tail (INSTANCE: bulk only; GEOFON: neutral; Chile: neutral).
  The plain equivariant likelihood (`eqgr`) wins the tail where a single amplitude law holds
  (INSTANCE at every deadline, Chile at 3–5 s), loses where it does not (GEOFON; Chile at 1 s).
  The distance-marginalized equivariant likelihood (`eqdgr`) is never worse than the free
  mixture on the tail and improves it on every dataset (INSTANCE M≥5 −.12 to −.19, GEOFON M≥7
  −.09 to −.12, Chile M≥6 −.28 to −.39), with lower bulk error on INSTANCE and Chile and a
  +.02 bulk cost on GEOFON only. Its recorded cost on INSTANCE (more 1 s false-M4 alarms) is
  removed by averaging with `mixgr` (16:45 entry).
* Headline for the cross-dataset claim: `eqdgr` − free mixture, three-seed ensembles, 5 s,
  median action — INSTANCE bulk −.005 / M≥5 −.19; GEOFON bulk +.02 / M≥7 −.12; Chile bulk
  −.006 / M≥6 −.39. Table: `results/cross_dataset_table.md`.

**Size-matched average on Chile (20:15 UTC, `chile_eval_combo6.json`).** As on INSTANCE
(16:45 entry), the structured six-model average mixgr×3 + eqdgr×3 against the free + prior-only
six-model average mix×3 + mixgr×3, median action: bulk **−.0033 [−.0038,−.0030] / −.0040
[−.0047,−.0034] / −.0049 [−.0059,−.0042]**; M≥5 −.013 [−.029,+.004] / **−.061 [−.087,−.033] /
−.088 [−.124,−.050]**; M≥6 −.011 / **−.252 [−.312,−.177] / −.333 [−.422,−.242]**. Under the
mean action the same cells are significant (5 s: bulk −.0046, M≥5 −.067, M≥6 −.246). So on
Chile the structured average dominates the matched free average on both axes at every deadline
(1 s tail equal), without the 1 s false-alarm cost seen on INSTANCE; the gain is not an
ensemble-size effect. `eqdgr` alone against the six-model free average: bulk −.0015 / −.0033 /
−.0045 (CIs exclude zero), tail as above.

## 2026-10-20 16:45 UTC — INSTANCE: the distance-marginalized equivariant head as a three-seed ensemble

eqdgr (3 seeds) − mix (3 seeds), median action: bulk −.0008 [−.0026,+.0005] / **−.0032
[−.0048,−.0021] / −.0047 [−.0062,−.0037]**; M≥4 −.015 / −.016 / −.023 (wide CIs, n.s.); M≥5
−.122 [−.279,+.030] / **−.174 [−.338,−.025] / −.189 [−.371,−.035]**; false-M4 **+4 / +2 / +1 per 10⁴**
(all CIs exclude zero; ≈2× the mixture's rate at 1 s). Averaging its posterior with the
prior-only model (6 members, not size-matched) keeps the tail (M≥4 −.022 / −.024 / −.028, M≥5
−.083 / −.132 / −.148, all CIs exclude zero), lowers bulk further (−.0055 / −.0067 / −.0076) and
removes the false-alarm cost (+1 / +0 / −0 per 10⁴). So the distance-marginalized form's
false-alarm cost on INSTANCE is a property of its sharper tail probabilities and is
controllable by model averaging. **Size-matched (6 vs 6: mixgr+eqdgr against mix+mixgr):**
bulk **−.0033 [−.0038,−.0023] / −.0042 [−.0047,−.0036] / −.0047 [−.0053,−.0043]**; M≥4 −.017
[−.042,+.003] / **−.018 [−.035,−.004] / −.021 [−.039,−.004]**; M≥5 −.077 [−.174,+.007] / **−.118
[−.231,−.033] / −.129 [−.253,−.041]**; false-M4 +1 [+1,+1] / +0 / +0 per 10⁴. The structured
average beats the matched free + prior-only average on bulk at every deadline and on the
tail at 3 and 5 s, with a one-per-10⁴ false-alarm increase confined to 1 s.

## 2026-10-20 14:35 UTC — third dataset built: single-station Northern Chile (TEAM-LM data); seed-1 results (three seeds: 20:10 entry)

To decide whether the INSTANCE regime (plain equivariance wins) or the GEOFON regime (needs
distance conditioning) is the typical early-warning case, a third, *local/regional* cache with
a real tail was built from the project's existing Northern-Chile TEAM-LM data
(`chile_prep.py`; sensitivity-corrected m/s, 100 Hz, MA labels). The release has only a
network-first-P clock, so each station trace was picked: causal 1–20 Hz band-pass on Z,
STA/LTA 0.5 s/5 s with trigger ≥ 4 after the network P, AIC refinement ±1 s, accepted when
RMS(1 s after)/RMS(1 s before) ≥ 3 and 5 s of data remain. 505,666 of 1,049,297 traces pass
(48%). Pick sanity: station P delay after the network P grows with epicentral distance
(r = 0.78; medians 1.0 s at <80 km, 4.9 s at 80–150 km, 10.3 s at 150–250 km, 17.9 s at
250–400 km). Cache: 67,284 events, 7,774 GK sequences, epicentral 42 / 126 / 233 km
(5th / 50th / 95th pct), **67 M≥5 and 12 M≥6 events** (max M8.05) balanced over 5 folds.
Arms queued: mix / eqgr / mixgr / eqdgr × 3 seeds; tails reported at M≥5, 5.5, 6.

**Seed 1 (16:30 UTC), Δ = arm − mix_nll, median action** (absolute mix: bulk .208 / .164 / .148;
M≥5 .857 / .591 / .556; M≥6 1.260 / .861 / .858):

| | bulk 1 / 3 / 5 s | M≥5 1 / 3 / 5 s | M≥6 (point) 1 / 3 / 5 s |
|---|---|---|---|
| eqgr | **+.0017 / +.0014** / +.0002 | **+.045** / −.037 / **−.076 [−.120,−.026]** | +.110 / **−.260 / −.366** |
| mixgr | +.0003 / +.0004 / +.0003 | +.004 / −.010 / −.010 | −.001 / −.066 / −.066 |
| **eqdgr** | **−.0025 / −.0042 / −.0059** (all CIs exclude zero) | −.012 / −.034 / **−.086 [−.129,−.037]** | −.002 / **−.261 / −.374** |

* Chile sits between the other two regimes: the plain equivariant head wins the tail at 3 and
  5 s (the twelve M≥6 events: −.26 / −.37 magnitude units of error) with equal bulk at 5 s, but
  loses at 1 s on both axes.
* **The distance-marginalized equivariant head dominates the free mixture on both axes at every
  deadline here**: lower bulk error everywhere (−1.2% to −4%), equal tail at 1 s and the same
  large-event gains as eqgr at 3–5 s. With INSTANCE (largest M≥5 gains, bulk −.0004 / −.0030 /
  −.0049) and GEOFON (only arm with M≥7 gains), `eqdgr` is the most portable single model; its
  one recorded cost is the higher 1 s false-M4 rate on INSTANCE (12 vs 6 per 10⁴).
* M≥6 intervals are not reported for seed 1: with 12 events, bootstrap replicates can contain
  none (fixed afterwards by dropping such replicates; the 20:10 entry reports them).
* **Mechanism on Chile (amplitude-response diagnostic, folds 0–1, M≥5 records):** the free
  mixture responds .74–.85 magnitude units per decade of amplitude *downward* but only
  .46–.57 *upward*, i.e. it saturates exactly as on INSTANCE and GEOFON; eqgr and eqdgr respond
  symmetrically at .93–1.16, the slope of an amplitude-based local scale (the learned κ was
  ≈.6–.8 on INSTANCE, where most labels are M_L with M_w above M4, and ≈.57 on GEOFON). On
  small events (M<3) all heads respond ≈.4–.9 and asymmetrically, as the prior dominates.

## 2026-10-20 08:30 UTC — distance-marginalized free mixture on INSTANCE: best bulk of any arm, no tail gain

`mixdgr_nll` (free distance-marginalized mixture × GR prior, distance a training label only,
seed 1) − mix_nll, median action: bulk **−.0031 [−.0043,−.0008] / −.0042 [−.0051,−.0026] /
−.0061 [−.0071,−.0045]** (absolute .3244 / .2661 / .2320, the lowest of any single model);
M≥4 +.006 / +.001 / −.013 (all n.s.); M≥5 **+.065 [+.014,+.125]** / +.010 / −.029 (n.s.);
false-M4 equal. For comparison, eqdgr (equivariant, same distance mixing) has M≥5 −.139 /
−.173 / −.184 and eqgr −.032 / −.115 / −.141.

Across both datasets the attribution is now consistent: **the GR prior factor and distance
marginalization improve bulk error; only the equivariant likelihood improves the
high-magnitude tail** (plainly on INSTANCE, per distance on GEOFON). Distance information
without the equivariant structure does not extrapolate to large events.

## 2026-10-20 07:20 UTC — capacity: a 2.2×-larger free mixture does not close the gap

`mix_nll_w15` and `eqgr_nll_w15` (trunk width ×1.5, 1.47 M parameters vs 0.66 M, seed 1).
eqgr_w15 − mix_w15, median action: bulk **−.0022 [−.0032,−.0017] / −.0025 [−.0039,−.0014] /
−.0034 [−.0043,−.0026]**; M≥4 **−.018 [−.023,−.010] / −.021 [−.034,−.007] / −.027 [−.045,−.010]**;
M≥5 −.031 [−.057,+.013] / **−.109 [−.206,−.022] / −.133 [−.263,−.034]**; event-M≥4 **−.016 / −.017 /
−.023** (CIs exclude zero); false-M4 +0.1 per 10⁴ (n.s.). The gap is unchanged or slightly
wider at higher capacity. The standard eqgr (0.66 M) against the 2.2×-larger free mixture:
bulk −.0009 / −.0015 / −.0025 (3 and 5 s CIs exclude zero), M≥4 +.000 / −.004 / −.012 (n.s.),
M≥5 +.008 / **−.091 / −.125**: extra capacity lets the free model reach eqgr's M≥4 error but
not its M≥5 error or its bulk error. The constraint is not a substitute for capacity; it is
information the free model does not recover with more parameters.

## 2026-10-20 04:25 UTC — training length: the gain persists at 20 epochs; longer training itself trades bulk for tail

`mix_nll_e20` and `eqgr_nll_e20` (20 epochs instead of 10, same schedule shape, seed 1).
eqgr_e20 − mix_e20, median action: bulk −.0001 [−.0026,+.0018] / **−.0017 [−.0038,−.0001] /
−.0038 [−.0047,−.0032]**; M≥4 **−.014 [−.020,−.004] / −.011 [−.019,−.001] / −.017 [−.024,−.007]**;
M≥5 −.047 [−.113,+.019] / **−.098 [−.164,−.043] / −.110 [−.198,−.033]**; false-M4 equal. Same
pattern and magnitude as at 10 epochs, so the result is not an under-training artefact.
Doubling the epochs is not itself an improvement: for both heads bulk MAE rises by +.004–.005
(mix_e20 .332 / .275 / .242 vs .328 / .270 / .238) while M≥4 falls by ≈.02, i.e. a move along the
trade-off, consistent with the model starting to overfit the bulk.

## 2026-10-20 01:20 UTC — INSTANCE, size-matched posterior average: the structured pair dominates the free + prior-only pair on every axis

Exploratory (same construction as the GEOFON check): three `mixgr` + three `eqgr` posteriors
averaged, against three `mix` + three `mixgr` (6 vs 6 models), median action, Δ = structured −
reference: bulk **−.0015 [−.0019,−.0012] / −.0018 [−.0024,−.0014] / −.0024 [−.0028,−.0021]**;
M≥4 **−.010 [−.015,−.004] / −.010 [−.018,−.003] / −.017 [−.028,−.007]**; M≥5 −.016 [−.046,+.012] /
**−.063 [−.133,−.010] / −.090 [−.179,−.030]**; event-M≥4 −.007 / −.008 / −.014; false-M4 rate
+0.0 per 10⁴ at every deadline (CI [−0.0, +0.1]). Bulk-capped best M≥4 −.088 / −.092 / −.101.
Mixing the prior-only posterior in removes eqgr's small false-alarm cost while keeping its tail
gain. Reported as a post-hoc combination; the pre-specified single-model claims stand above.

## 2026-10-19 23:40 UTC — NEGATIVE on a second dataset: on the GEOFON regional subset the equivariant head is worse than the free mixture

Second dataset (`geofon_prep.py`, `results/geofon_folds.json`): GEOFON (SeisBench), records
within 2,000 km of the epicentre with a catalogue P pick, sensitivity and ≥99% completeness:
**31,020 records, 2,212 events, 276 M≥6 and 50 M≥7 events**; labels mostly mb (49%), with
Mw(mB), M, MLv, Mw(Mwp); 78% of traces at 20 Hz (BH), resampled to 100 Hz; GK sequence folds
balanced on M≥6/M≥7. Same code, seed 1, median action, Δ = arm − mix_nll (`geofon_eval.py`):

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| eqgr Δ bulk | **+.015 [+.010,+.020]** | **+.014 [+.009,+.019]** | **+.013 [+.008,+.018]** |
| eqgr Δ M≥6 | **+.043 [+.020,+.064]** | **+.053 [+.038,+.067]** | **+.060 [+.047,+.074]** |
| eqgr Δ M≥7 | **+.067 [+.031,+.104]** | +.026 [−.008,+.063] | +.018 [−.020,+.058] |
| mixgr Δ bulk | +.001 [−.001,+.002] | +.001 [−.000,+.003] | +.002 [+.001,+.004] |
| mixgr Δ M≥6 | **−.008 [−.014,−.002]** | **−.009 [−.014,−.005]** | −.004 [−.009,+.001] |

Absolute mix_nll: bulk .533 / .460 / .429, M≥6 .888 / .670 / .579, M≥7 1.542 / 1.243 / 1.108,
M≥6 bias −.84 / −.61 / −.52 (all models underestimate large events heavily at these windows).

**Diagnosis so far**
* The deficit is uniform: +.01–.02 in every magnitude-type, sampling-rate, distance and channel
  subgroup; largest for MLv (+.045, over-predicted by both) and for Mw-labelled M≥6 records
  (+.05–.07, where eqgr underestimates *more*: bias −.92 vs −.87).
* The free mixture saturates here too (M≥6, fold 0: response .52 per decade downward, .41
  upward at 1 s; .49 / .34 at 5 s) while eqgr responds symmetrically with κ ≈ .57, yet the
  free model is still more accurate. So on this data the symmetric response is not the right
  prior: with emergent P onsets at 300–2,000 km sampled at 20 Hz, the 1–5 s RMS amplitude is
  often noise-dominated, and a head that must respond to it with κ ≥ 0.3 cannot learn to
  ignore it, whereas a free head can.
* The prior factor alone (`mixgr`) is neutral on bulk and slightly better on M≥6, as on INSTANCE.

**Three-seed ensembles (23:48 UTC) confirm it:** eqgr − mix = bulk **+.010 / +.009 / +.008**,
M≥6 **+.036 / +.042 / +.047**, M≥7 +.050 / +.008 / −.006 (all bulk and M≥6 CIs exclude zero);
mixgr − mix = bulk +.001 / +.001 / +.000 (n.s.), M≥6 −.003 / −.003 / −.003 (5 s CI excludes zero).

**Variants on GEOFON (23:58 UTC, seed 1, Δ vs mix_nll, median action):**

| | bulk 1 / 3 / 5 s | M≥6 1 / 3 / 5 s | M≥7 1 / 3 / 5 s |
|---|---|---|---|
| eqgr (κ ≥ 0.3) | +.015 / +.014 / +.013 | +.043 / +.053 / +.060 | +.067 / +.026 / +.018 |
| eqgr, κ ≥ 0 (`eqgr_k0`) | +.017 / +.014 / +.014 | +.059 / +.055 / +.058 | +.085 / +.021 / +.011 |
| eqtgr (two slopes) | +.016 / +.021 / +.021 | +.087 / +.104 / +.122 | +.180 / +.185 / +.201 |
| **eqdgr** (distance-marginalized) | +.019 / +.014 / +.014 | **−.027** / −.008 / −.002 | **−.103 / −.114 / −.141** |

* Letting κ reach 0 changes nothing (three-seed ensembles, 00:35 UTC: κ≥0 − mix = bulk
  +.009 / +.008 / +.007, M≥6 +.051 / +.045 / +.041, CIs exclude zero), so the "forced response to
  a noise-dominated amplitude" explanation above is **refuted**: the rigidity is in the
  additive form κ(s)·A + g(s) itself, not in the slope's lower bound.
* The distance-marginalized GR head recovers the large-event tail (M≥7 −.10 to −.14, the
  largest tail gain of any arm on GEOFON; M≥7 bias −1.44 vs −1.54 at 1 s) while still paying
  ≈+.015 bulk. At 300–2,000 km the attenuation term spans several magnitude units, and a head
  that must infer distance from the waveform shape and apply it as one additive offset is too
  rigid; mixing over explicit distance hypotheses restores the flexibility for large events.
* Separate scale slopes make everything worse (two half-size slope estimates).

**Distance-marginalized free mixture (`mixdgr`, 00:35 UTC), the ablation for eqdgr.** Three-seed
ensembles, Δ vs mix ensemble, median action:

| | bulk 1 / 3 / 5 s | M≥6 1 / 3 / 5 s | M≥7 1 / 3 / 5 s |
|---|---|---|---|
| mixdgr (free, distance-marginalized, GR prior) | +.013 / +.011 / +.012 | −.015 / +.011 / +.023 | −.014 / +.015 / +.020 |
| **eqdgr** (equivariant, distance-marginalized, GR prior) | +.024 / +.017 / +.016 | −.027 / −.003 / +.002 | **−.094 / −.089 / −.123** |

Distance marginalization by itself does *not* recover the large events; the M≥7 gain appears
only when the per-distance likelihood is equivariant. On GEOFON, then, the two structural
pieces are complementary in the other direction from INSTANCE: equivariance alone is too rigid
(one additive attenuation offset for 300–2,000 km), distance mixing alone is too free, and the
equivariant-per-distance head extrapolates to M≥7 (bias −1.45 vs −1.55 at 1 s; −.97 vs −1.11 at
5 s). Both distance heads pay +.011–.024 bulk here. **Extending the distance grid to 2,500 km
(01:07 UTC, `*_r34`, 3 seeds) changes nothing:** eqdgr_r34 ensemble − mix = bulk +.026 / +.020 /
+.018, M≥7 **−.095 / −.083 / −.117**; mixdgr_r34 − mix = M≥7 −.010 / +.034 / +.050. So the clamped
distance label was not the cause; the result is structural and replicated across seeds and grids.

**Exploratory (chosen after seeing the above): posterior averaging on GEOFON (01:15 UTC).** With
existing predictions only, averaging the three `mixgr` and three `eqdgr` posteriors against a
size-matched average of three `mix` and three `mixgr` posteriors gives, median action: bulk
+.004 [+.000,+.007] / −.000 [−.003,+.002] / −.001 [−.004,+.001]; M≥6 **−.019 / −.010** / −.008
(1 s and 3 s CIs exclude zero); M≥7 **−.048 / −.053 / −.070** (all exclude zero). So a
GR-structured posterior average does reach the far-regional tail without losing bulk at 3 and
5 s; at 1 s it costs +.004 bulk. This is a post-hoc combination and is reported as such.

**Consequence for the claim.** On INSTANCE (local records within a few hundred km, 100 Hz,
mostly M_L) the plain equivariant head is the right prior and wins outright. On the GEOFON
regional/teleseismic subset it is not: the amplitude law must be conditioned on distance, and
then it buys the M≥7 tail at a bulk cost. The GR prior factor is neutral-to-positive on both.

## 2026-10-19 22:50 UTC — published-architecture control (MagNet-style CNN+BiLSTM) is far behind the shared trunk

`magnet_nll`: Mousavi & Beroza (2020) layout (two convolutions, 64 and 32 kernels of size 3,
no activation, dropout 0.2, 4× max-pooling, BiLSTM 100) on amplitude-retaining waveforms, the
same station metadata, a Gaussian head trained with NLL, same folds and schedule. Pooled,
median action: bulk MAE **.397 / .377 / .355**, M≥4 **1.032 / .866 / .796**, M≥5 1.768 / 1.550 /
1.429, NLL 3.03 / 3.01 / 2.96 (vs .328 / .270 / .238, .764 / .577 / .530, 1.051 / .765 / .703,
2.75 / 2.56 / 2.43 for the free mixture).

* Every arm on the residual-CNN trunk beats it by ≈.07–.12 bulk MAE and ≈.25 M≥4 MAE; eqgr −
  magnet: bulk −.071 / −.107 / −.116, M≥4 −.279 / −.288 / −.271, M≥5 −.740 / −.883 / −.846.
* This is a *short-window adaptation* of an architecture designed for 30 s records, so it says
  little about MagNet at its intended window. What it establishes is that the trunk shared by
  all arms here is a strong one, so the head comparisons are not made on a weak backbone.

## 2026-10-19 22:20 UTC — held-station test: the gain survives on stations never seen in training

`mix_nll_hs` and `eqgr_nll_hs` were trained with a fixed random **20% of stations withheld in
every fold** (`--hold-stations 0.2`, seed 0), so their held-fold records at those stations are
*both* held-event and held-station: a station fingerprint cannot explain a gain there.
Δ = eqgr_hs − mix_hs, median action, 95% cluster-bootstrap CIs (`results/eval_hs_*.json`).

**Held-station records (279,812; 341 of the 346 M≥4 events have at least one held-station record):**

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0019 [−.0056,+.0035] | −.0003 [−.0015,+.0018] | −.0031 [−.0069,+.0017] |
| Δ M≥4 MAE | **−.017 [−.026,−.010]** | −.005 [−.018,+.004] | **−.011 [−.019,−.004]** |
| Δ M≥5 MAE | **−.068 [−.107,−.032]** | **−.111 [−.176,−.041]** | **−.139 [−.208,−.068]** |
| Δ M≥4 event-MAE | −.009 [−.020,+.002] | +.003 [−.009,+.013] | −.004 [−.013,+.005] |
| Δ false-M4 rate | −.0012 [−.0029,+.0006] | −.0002 | −.0005 [−.0010,+.0001] |
| CVaR95 (eqgr vs mix) | 1.275 vs 1.350 | 1.126 vs 1.145 | 1.077 vs 1.107 |

**Seen-station records (879,437), same two models:** bulk −.0015 / −.0019 / −.0034; M≥4
**−.024 / −.013 / −.021**; M≥5 **−.075 / −.107 / −.135**; event-M≥4 **−.020 / −.010 / −.018**
(all tail CIs exclude zero).

* On unseen stations the M≥5 improvement is as large as on seen ones and significant at all
  three deadlines; M≥4 is significant at 1 and 5 s (3 s: same sign, n.s.); event-level M≥4 is
  not significant on this subset (fewer events per station group). Bulk is never worse.
* The free mixture degrades more on unknown stations than eqgr does: its false-M4 rate at 1 s
  is 2.9 per 10³ vs 1.2 for eqgr, and its CVaR95 is higher at every deadline. A constrained
  amplitude response transfers to new instruments better than a learned one.
* **Prior-only ablation under the same protocol (`mixgr_nll_hs`, 23:35 UTC):** on held stations
  mixgr − mix is bulk −.0035 / −.0015 / −.0018 (1 s CI excludes zero), M≥4 −.003 / −.007 / −.006
  (n.s.), M≥5 −.026 / −.044 / −.065 (3 and 5 s significant). So both components transfer to
  unseen stations; equivariance carries the larger tail gain (M≥5 −.068 / −.111 / −.139) and,
  unlike mixgr, also lowers CVaR95 (1.275 / 1.126 / 1.077 vs mixgr 1.317 / 1.167 / 1.120) and the
  false-M4 rate (1.2 / 0.9 / 0.8 vs mixgr 2.5 / 2.0 / 2.3 per 10³) on unknown instruments.
* On seen stations these reduced-data models are within .003 bulk MAE of the full-data arms;
  on held stations both are ≈.02–.025 worse (unknown instruments), so the held-station numbers
  are comparable only to each other, not to the main table.

## 2026-10-19 21:10 UTC — third seed: 3-seed ensembles confirm eqgr; eqdgr's M≥5 gain and its false-alarm cost both replicate

Seed-3 arms (queue3) and eqdgr seeds 2–3 (`queue4.txt`), evaluated by `eval_replication.sh`
(`results/eval_ens3.json`, `eval_eqd_*.json`). Ensembles are posterior mixtures. `evaluate.py`
now also bootstraps the **false-M4 rate**: the share of M<3.5 records whose prediction is ≥3.95,
given here per 10⁴ such records.

### Three-seed ensembles, Δ = arm ensemble − free-mixture (`mix_nll`) ensemble, median action

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| eqgr Δ bulk | −.0008 [−.0021,+.0000] | **−.0015 [−.0031,−.0003]** | **−.0028 [−.0039,−.0020]** |
| eqgr Δ M≥4 | **−.015 [−.023,−.005]** | **−.015 [−.026,−.003]** | **−.025 [−.042,−.009]** |
| eqgr Δ M≥5 | −.024 [−.075,+.028] | **−.105 [−.220,−.010]** | **−.149 [−.291,−.040]** |
| eqgr bulk-capped M≥4 / M≥5 | **−.056 / −.061** | **−.078 / −.132** | **−.107 / −.166** |
| eqgr Δ false-M4 per 10⁴ | **+1.5 [+1.0,+2.3]** | **+0.65 [+0.05,+1.02]** | **+0.63 [+0.03,+1.04]** |
| mixgr Δ bulk / M≥4 / event-M≥4 | **−.0015 / −.008 / −.008** | **−.0022 / −.008 / −.006** | **−.0028 / −.012 / −.010** |
| cat_ce Δ M≥4 / M≥5 | **+.018 / +.058** | **+.030 / +.094** | **+.032 / +.113** |

* The third seed changes none of the two-seed conclusions; no Δ moves by more than .007.
  eqgr still lowers M≥4 at every deadline and M≥5 at 3 and 5 s, with bulk equal or better.
* False-M4 per 10⁴ M<3.5 records (ensembles): mix 5.0 / 4.2 / 3.4, mixgr 5.6 / 4.0 / 3.3,
  eqgr 6.4 / 4.9 / 4.1, cat_ce 7.5 / 5.2 / 4.2. **eqgr's small false-alarm rise over the mixture
  is significant at every deadline** (each single seed shows it at 1 s). It stays below plain CE.

### eqdgr replication (seeds 1–3)

M≥5 MAE, median action, eqdgr vs eqgr of the same seed:

| seed | 1 s | 3 s | 5 s | false-M4 per 10⁴ at 1 s |
|---|---|---|---|---|
| 1 | .898 vs 1.012 | .578 vs .638 | .503 vs .548 | 12.2 vs 7.8 |
| 2 | .929 vs 1.022 | .594 vs .651 | .525 vs .549 | 11.8 vs 7.8 |
| 3 | .918 vs 1.014 | .576 vs .646 | .507 vs .546 | 11.5 vs 7.9 |
| mix_nll (seed 1) | 1.051 | .765 | .703 | 6.3 |

Each eqdgr seed − mix_nll, M≥5: −.139 / **−.173 / −.184** (seed 1), −.107 / **−.157** / −.163
[−.367,+.030] (seed 2), −.120 / **−.174 / −.180** (seed 3). Each eqdgr seed − mix_nll, false-M4 at
1 s: **+5.4 / +5.1 / +4.8** per 10⁴ (all CIs exclude zero).

Three-seed ensembles, Δ = eqdgr ensemble − eqgr ensemble, median action:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk | +.0000 [−.0007,+.0010] | **−.0016 [−.0022,−.0007]** | **−.0018 [−.0024,−.0013]** |
| Δ M≥4 | −.001 [−.030,+.025] | −.001 [−.013,+.010] | +.002 [−.009,+.014] |
| Δ M≥4 event | −.001 [−.032,+.023] | +.002 [−.011,+.013] | +.008 [−.004,+.018] |
| Δ M≥5 | −.099 [−.212,+.012] | **−.070 [−.126,−.011]** | −.042 [−.090,+.012] |
| bulk-capped M≥4 / M≥5 | −.007 / **−.120** | **−.066 / −.108** | **−.073 / −.076** |
| Δ false-M4 per 10⁴ | **+3.0 [+0.7,+4.6]** | **+1.4 [+0.7,+1.8]** | +0.4 [−0.2,+1.4] |

Against the mix ensemble, the eqdgr ensemble has bulk −.0008 / **−.0032 / −.0047**, M≥4 −.016 /
−.016 / −.023 (no CI excludes zero), M≥5 −.124 [−.287,+.034] / **−.176 [−.346,−.020] / −.191
[−.379,−.034]**, bulk-capped M≥5 **−.162 / −.223 / −.225**, and false-M4 **+4.5 / +2.0 / +1.0** per 10⁴.

* **The M≥5 advantage replicates.** In every seed, eqdgr's M≥5 MAE is below the same-seed eqgr
  at every deadline: by .09–.11 at 1 s, .06–.07 at 3 s and .02–.05 at 5 s. In the ensembles
  the gap is significant at 3 s, and bulk-capped at all three deadlines. eqdgr also has the
  lowest bulk MAE at 3 and 5 s (.2611 / .2277 vs .2628 / .2295 for eqgr) and the lowest NLL at
  every deadline of all the 3-seed ensembles.
* **The higher 1 s false-M4 rate replicates too.** It is 11.5–12.2 per 10⁴ in every seed,
  against 7.8–7.9 for eqgr. In the ensembles the rates are 9.9 (eqdgr), 6.4 (eqgr), 5.0 (mix)
  and 7.5 (cat_ce). The excess shrinks with time (3 s +1.4, significant; 5 s n.s.). The
  other seed-1 costs also hold: CVaR95 is higher than eqgr's (+.005 / +.007 / +.008), and
  Emilia (fold 1) gets worse (M≥4 .879 / .533 / .477 vs .844 / .513 / .442).
* **No M≥4 gain over eqgr.** Record and event M≥4 MAE match eqgr within ±.01 at every deadline.
  The gain is in the largest events and in the unseen Central Italy fold (fold-0 M≥4
  .609 / .434 / .369 vs .669 / .457 / .389).
* **Verdict:** eqdgr is a replicated trade-off, not a replacement. It gives better M≥5
  extrapolation and 3–5 s bulk, but has about 1.5× eqgr's 1 s false-M4 rate and no M≥4 gain.
  eqgr remains the main method; eqdgr stays exploratory (designed after the eqgr results).

## 2026-10-19 18:30 UTC — seed × fold consistency (3 seeds × 5 folds × 3 deadlines) and the component trade-off

Sign tests over 45 cells (seed-matched pairs, median action, `seed_consistency.py`).

**eqgr − mix_nll (strongest baseline):**
* M≥4 MAE: eqgr better in **36/45** cells (sign-test p = 7×10⁻⁵). The 9 exceptions are **all fold 1
  (Emilia)**; every other fold, seed and deadline improves. M≥4 event-MAE 36/45; M≥5 34/45
  (p = 8×10⁻⁴); bulk MAE 33/45 (p = 2×10⁻³, median Δ −.0014).
* Pooled per seed: all 9 seed×deadline comparisons are negative for M≥4, event-M≥4 and M≥5;
  bulk is ≤ 0 in all 9 (worst case +.0000 at 1 s, seed 1).

**Ablations, 3 seeds each:**
* mixgr − mix: bulk better in **40/45** (p = 8×10⁻⁸), M≥4 31/45 (p = .016), M≥5 29/45 (p = .07).
* eqgr − mixgr: M≥4 better in **35/45** (p = 2.5×10⁻⁴), M≥5 30/45 (p = .036), event-M≥4 32/45;
  bulk better in only 11/45 (median Δ **+.0006**, p = 8×10⁻⁴ in mixgr's favour).

**Other tail views (single seed, median action, eqgr vs mix_nll):** M≥4.5 MAE .876 / .639 / .584
vs .899 / .678 / .635; event-level M≥5 MAE .989 / .606 / .513 vs 1.009 / .706 / .644; M≥5 bias
−.96 / −.56 / −.46 vs −1.02 / −.74 / −.68. The **worst-1% errors over all records (CVaR99)** are
*not* improved: 1.663 / 1.487 / 1.429 vs 1.660 / 1.478 / 1.430 (+.009 at 3 s). Those errors are
dominated by records whose waveform carries little magnitude information at the deadline, not
by large events, and the method does not address them. CVaR95 is unchanged (≤ ±.002).

**Tail-probability reliability (`calibration_check.py`):** both arms are well calibrated
(Brier reliability terms 2×10⁻⁶ to 4×10⁻⁵). eqgr's lower Brier for P(M≥4) and P(M≥5) at 3 s and
5 s (e.g. 5 s M≥5: .000849 vs .000929) comes from higher resolution. The free mixture is
systematically **under-confident for M≥5** (predicted .14 → observed .20; .42 → .55; .57 → .64 at
5 s), the probabilistic face of amplitude saturation; eqgr is near the diagonal in that range
and slightly over-confident at the top (.97 → .78, 475 records). At 1 s the two are equal.

So both components beat the baseline on both axes, but they are not equivalent: the GR prior
factor is the bulk-safest change, and equivariance buys the tail for a median +.0006 bulk MAE
relative to that ablation (still below the baseline's bulk). The pre-specified claim ("tail
down at 1/3/5 s, bulk not worse than the baseline") holds for eqgr; relative to its own
ablation it is a stated trade-off.

## 2026-10-19 16:00 UTC — two-seed ensembles vs the strongest baseline, exploratory heads, and the standard split

### Two-seed ensembles, Δ = arm ensemble − free-mixture (`mix_nll`) ensemble, median action

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| eqgr Δ bulk | −.0007 [−.0020,+.0001] | **−.0015 [−.0030,−.0003]** | **−.0030 [−.0039,−.0024]** |
| eqgr Δ M≥4 | **−.016 [−.023,−.005]** | **−.014 [−.024,−.001]** | **−.022 [−.037,−.006]** |
| eqgr Δ M≥5 | −.028 [−.084,+.029] | **−.106 [−.220,−.006]** | **−.143 [−.281,−.031]** |
| eqgr bulk-capped M≥4 / M≥5 | **−.051 / −.059** | **−.078 / −.135** | **−.113 / −.166** |
| mixgr Δ bulk / M≥4 / event-M≥4 | **−.0014 / −.009 / −.010** | **−.0023 / −.008 / −.007** | **−.0028 / −.008 / −.007** |
| cat_ce Δ M≥4 / M≥5 | **+.015 / +.059** | **+.030 / +.099** | **+.034 / +.120** |

With ensembles on both sides, eqgr beats the strongest existing approach on high-magnitude
error at all three deadlines (M≥4 CIs exclude zero everywhere; M≥5 at 3 and 5 s), with bulk
error equal (1 s) or better (3 s, 5 s).

### Exploratory heads (single seed, designed after seeing the eqgr results)

* **eqtgr** (separate ML / Mw equivariant slopes, joint likelihood with the reported scale):
  **negative**. It does not fix Emilia (fold 1 M≥4 .866/.542/.480 vs .853/.530/.455 for eqgr), and
  pooled it is no better than eqgr anywhere. 1 s M≥5 is *worse* than the free mixture
  (+.028 [+.002,+.063]).
* **eqdgr** (distance-aware equivariant likelihood p(r|s)·N(m; κA+G_r(s)) × the same GR prior,
  distance used only as a training label): **promising**. It has the largest M≥5 gains of any
  arm, −.139 / −.173 / −.184 vs mix_nll (3 and 5 s CIs exclude zero), and bulk-capped M≥5
  −.165 / −.223 / −.225. Bulk is −.0004 / −.0030 / −.0049. On fold 0 (unseen Central Italy)
  1 s M≥5 MAE is .798 vs 1.03 (eqgr) vs 1.26 (mix). Costs: a higher 1 s false-M4 rate (.0012 vs
  .0006), CVaR95 +.004 to +.009, wider intervals (still worse on Emilia). It needs seed
  replication before it could replace eqgr.

### Standard INSTANCE split (train 2005–17 → VAL 2018 / TEST 2019–20; no selection on VAL/TEST)

eqgr − mix_nll, median action. **VAL** (13 M≥4 events): bulk −.0000 / **−.0013 / −.0024**;
M≥4 **−.025 / −.022 / −.038** (CIs exclude zero). **TEST** (10 M≥4 events, max M4.5): bulk
−.0014 / −.0006 / **−.0014**; M≥4 −.014 / −.009 / −.007 (same direction, n.s.). mixgr improves
bulk on both splits at every deadline (−.0019 to −.0038, all significant).

**Against the previous project's best reported VAL model** (static instrument features,
mean action: bulk .365 / .316 / .286, M≥4 .686 / .551 / .487, CVaR95 1.327 / 1.195 / 1.147):
at the same M≥4 MAE, std_eqgr needs **14% / 19% / 20% less bulk MAE** (.3145 / .2574 / .2278)
and also has lower CVaR95 (1.240 / 1.073 / 1.025) and MedAE. Most of this cross-project gain
comes from the new end-to-end physical-unit pipeline, which every arm here shares (the
free-mixture baseline gets 14% / 18% / 20%). The head's contribution is the within-pipeline
gain reported above.

## 2026-10-19 09:50 UTC — negative for deep-imbalanced-regression reweighting: LDS is dominated

`cat_lds` (categorical CE with LDS inverse-sqrt smoothed-density weights, Yang et al. 2021)
pooled, median action: bulk MAE .3554 / .2924 / .2574 (+.028 / +.021 / +.017 vs cat_ce, ≈+8%);
M≥4 MAE .638 / .503 / .475; false-M4 rate .0035 / .0021 / .0017 (4× cat_ce).

* Plain CE reaches the same M≥4 MAE with **.023 / .019 / .016 less bulk MAE**, so LDS is
  dominated on the frontier. It buys tail error with bulk error and false alarms.
* eqgr − cat_lds: bulk **−.028 / −.024 / −.023**; bulk-capped M≥4 **−.148 / −.147 / −.152**;
  bulk-capped M≥5 **−.036 / −.078 / −.118** (all CIs exclude zero).
* **All six baselines** (cat_ce, cat_hubce, mix_nll, cat_aug, cat_lds, gbm_e3ws) are now
  dominated by eqgr on the bulk–tail frontier at 1, 3 and 5 s.

## 2026-10-19 08:35 UTC — negative for the "just augment" alternative: amplitude-scaling augmentation is dominated

`cat_aug` (categorical CE + waveform ×10^Δ with label +Δ, Δ~U(−.5,.5)) pooled, median action:
bulk MAE .3374 / .2796 / .2467 (vs .3272 / .2714 / .2400 for cat_ce, i.e. +3–4%); M≥4 MAE
.737 / .569 / .523; M≥5 1.036 / .782 / .734.

* It lowers tail error only by moving along the trade-off. Plain CE reaches the same M≥4 MAE
  with **.010 / .008 / .007 less bulk MAE** (tail-capped comparison), so augmentation is
  dominated even by the baseline.
* eqgr − cat_aug: bulk **−.0107 / −.0112 / −.0121**; bulk-capped M≥4 **−.171 / −.170 / −.171**;
  M≥5 −.022 [−.075,+.044] / **−.136 [−.235,−.027] / −.176 [−.276,−.074]**.
* Teaching the symmetry through data (fixed slope 1, shifted labels) distorts small-event
  predictions and extrapolates less far than building it into the posterior with a learned
  slope κ(s).

## 2026-10-19 07:40 UTC — gains survive two-seed ensembling

eqgr (seeds 1+2, posterior mixture) − cat_ce (seeds 1+2), median action:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0005 [−.0026,+.0013] | **−.0028 [−.0050,−.0009]** | **−.0048 [−.0062,−.0039]** |
| Δ M≥4 MAE | **−.031 [−.049,−.011]** | **−.044 [−.069,−.020]** | **−.056 [−.089,−.027]** |
| Δ M≥5 MAE | **−.087 [−.155,−.012]** | **−.205 [−.309,−.100]** | **−.263 [−.385,−.154]** |
| Δ M≥4 event-MAE | **−.022 [−.042,−.003]** | **−.036 [−.065,−.014]** | **−.047 [−.083,−.022]** |
| bulk-capped best M≥4 / M≥5 | **−.068 / −.114** | **−.130 / −.240** | **−.160 / −.287** |

Ensembling lowers both arms' bulk MAE by ≈.005 (single seed → 2-seed), but the tail gap is
unchanged, so the improvement is not seed noise or a variance effect. With ensembles, every
tail metric at every deadline has a 95% interval excluding zero; bulk is equal (1 s) or better.

## 2026-10-19 06:40 UTC — per-fold consistency and the Emilia exception

Arm − mix_nll per held-out fold (median action; bulk / M≥4 / M≥4-event):
* **mixgr** improves M≥4 in 14/15 fold×deadline cells and bulk in 13/15. Both bulk
  exceptions are in fold 1, the smallest fold (9.8k records).
* **eqgr** improves the tail in folds 0, 2, 3, 4 at every deadline (fold 0, the unseen M6.5
  Central Italy sequence: M≥4 −.046 / −.038 / −.056). It is **worse in fold 1** (M≥4 +.06 at
  1–3 s, +.044 at 5 s; bulk +.003 to +.005).
* Fold 1 is the **2012 Emilia (Po Plain) sequence**: M5.8 and M5.6, 32 M≥4 events, 24 of them
  ML-labelled. All models underestimate it. eqgr's extra error is on the **ML-labelled**
  events (3 s bias −.48 vs −.42 for mix_nll), while it is better on the Mw-labelled ones (5 s
  bias −.08 vs −.18). The equivariant head learns one amplitude slope κ(s) ≈ 0.7, close to Mw's
  ⅔ scaling. ML scales ≈1:1 with amplitude, so a sequence dominated by large ML labels is where
  a single learned slope fits worst. **Limitation and future work:** scale-specific slopes
  (an ML and an Mw head) or magnitude-type-homogeneous labels.

## 2026-10-19 06:30 UTC — full attribution against the strongest existing baseline (TEAM-LM-style free mixture)

All 1,159,249 records; Δ = arm − `mix_nll` (free Gaussian-mixture posterior, the strongest
existing-method baseline here). Median action; 95% cluster-bootstrap CIs.

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| cat_ce: Δ bulk / Δ M≥4 / Δ M≥5 | −.0002 / **+.016** / **+.061** | **+.0012 / +.030 / +.095** | **+.0018 / +.033 / +.114** |
| **mixgr**: Δ bulk | **−.0011 [−.0019,−.0006]** | **−.0025 [−.0030,−.0022]** | **−.0032 [−.0035,−.0027]** |
| **mixgr**: Δ M≥4 | **−.013 [−.022,−.003]** | **−.011 [−.018,−.003]** | **−.012 [−.020,−.004]** |
| **mixgr**: Δ M≥4 event | **−.012 [−.021,−.002]** | **−.010 [−.018,−.001]** | **−.011 [−.020,−.002]** |
| **mixgr**: bulk-capped M≥4 / M≥5 | **−.070 / −.080** | **−.107 / −.094** | **−.115 / −.082** |
| **eqgr**: Δ bulk | −.0002 [−.0017,+.0008] | **−.0015 [−.0028,−.0006]** | **−.0032 [−.0038,−.0029]** |
| **eqgr**: Δ M≥4 | **−.020 [−.034,−.002]** | −.015 [−.028,+.001] | **−.023 [−.040,−.005]** |
| **eqgr**: Δ M≥5 | −.032 [−.119,+.040] | −.115 [−.246,+.000] | **−.141 [−.289,−.021]** |
| **eqgr**: bulk-capped M≥4 / M≥5 | −.033 / −.032 (n.s.) | **−.076 / −.143** | **−.114 / −.169** |
| eq_nll (no prior factor): Δ bulk | **+.0051** | **+.0046** | **+.0032** |

**Interpretation**
1. A smooth parametric mixture head (as in TEAM-LM) already beats a categorical head on the
   tail. That part is prior art.
2. **New, the Gutenberg–Richter-factorized posterior** p(m|x) ∝ L_θ(m|x)·e^{φ(m)}, with φ
   learned, free below M3.5 and GR-linear above. On top of the mixture it improves bulk,
   M≥4 and event-level M≥4 at every deadline, all CIs excluding zero: a strict Pareto gain
   over the strongest baseline.
3. **New, the scale-equivariant likelihood** (eqgr) adds extrapolation for the largest events
   (M≥5: −.115 / −.141 at 3 / 5 s vs mix; .548 vs .655 for mixgr at 5 s). Without the
   prior factor, equivariance costs ≈+.005 bulk MAE because of the M2.0 label-prior cliff. The
   two components are complementary and should be used together.

## 2026-10-19 05:40 UTC — replicated across seeds; ablation attributes the gain

**eqgr seed 2 − cat_ce (median action):** bulk −.0000 [−.0022,+.0016] / **−.0021 [−.0044,−.0001]** /
**−.0045 [−.0057,−.0037]**; M≥4 **−.030 [−.052,−.008] / −.042 [−.069,−.017] / −.055 [−.089,−.023]**;
M≥5 **−.085 [−.151,−.014] / −.198 [−.315,−.087] / −.255 [−.397,−.141]**; M≥4 event-MAE
**−.021 [−.044,−.002] / −.035 [−.065,−.013] / −.045 [−.082,−.018]** (1 / 3 / 5 s). Seed 1 and
seed 2 agree to within ≈.006 on every tail metric.

**Probabilistic quality (both seeds):** eqgr beats cat_ce on NLL, CRPS, and Brier(M≥4) and
Brier(M≥5) at every deadline. Mean P(M≥4) on true M≥4 records rises from .374/.445/.467 to
≈.40/.49/.52, while on M<3.5 records it moves only from .0072/.0051/.0042 to .0079/.0055/.0046.

**Ablation `mixgr` (free mixture × the identical learned prior factor):**

| median action | 1 s | 3 s | 5 s |
|---|---|---|---|
| cat_ce − mixgr, M≥4 MAE | +.029 [+.010,+.048] | +.041 [+.017,+.067] | +.044 [+.018,+.073] |
| cat_ce − mixgr, M≥5 MAE | +.085 [+.040,+.120] | +.137 [+.071,+.191] | +.156 [+.083,+.220] |
| eqgr − mixgr, M≥4 MAE | −.007 [−.015,+.008] | −.004 [−.013,+.009] | −.012 [−.021,+.002] |
| eqgr − mixgr, M≥5 MAE | −.007 [−.064,+.058] | −.073 [−.153,+.022] | **−.100 [−.186,−.009]** |
| eqgr − mixgr, bulk MAE | +.0009 [−.0000,+.0015] | +.0010 [−.0001,+.0018] | −.0000 [−.0008,+.0004] |

* The **Gutenberg–Richter-factorized posterior** (smooth likelihood × learned global log-prior:
  free in the bulk, GR-linear above M3.5) gives most of the M≥4 improvement and preserves the
  bulk. It takes over the label-prior structure (the M2.0 cliff, the steep GR decay) that a
  categorical head must otherwise learn per input, and underfits in the rare bins.
* **Scale equivariance** adds extrapolation for the *largest* events: M≥5 MAE at 5 s
  .548 (eqgr) vs .655 (mixgr) vs .818 (cat_ce), at a ≈.001 (0.3%) bulk cost at 1–3 s.
* Still pending: `mix_nll` (free mixture without the prior factor) to separate the mixture
  family from the factorization; augmentation / LDS baselines; seed 3; standard split.

## 2026-10-19 03:45 UTC — eqgr (equivariant likelihood × learned bulk prior × GR tail) improves the tail at all deadlines without worsening the bulk (seed 1)

**Same decision rule (posterior median) for both, eqgr − cat_ce:**

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0000 [−.0025,+.0019] | **−.0027 [−.0046,−.0013]** | **−.0050 [−.0062,−.0044]** |
| Δ M≥4 MAE | **−.036 [−.060,−.011]** | **−.045 [−.075,−.017]** | **−.056 [−.092,−.024]** |
| Δ M≥5 MAE | **−.093 [−.175,−.003]** | **−.210 [−.334,−.092]** | **−.255 [−.401,−.137]** |
| Δ M≥4 event-MAE | −.025 [−.053,+.002] | **−.036 [−.072,−.008]** | **−.046 [−.086,−.015]** |

MedAE (.2402/.1929/.1649 vs .2398/.1957/.1699), CVaR95 (1.214/1.059/.989 vs 1.215/1.058/.990)
and the false-M4 rate (.0008/.0006/.0005, identical) are unchanged or better.

**Bulk-capped best tail** (each arm picks its best tail-weight r subject to bulk MAE ≤ cat_ce's):
M≥4 MAE −.065 [−.112,−.003] (1 s), **−.128 [−.150,−.101] (3 s), −.161 [−.186,−.127] (5 s)**;
M≥5 MAE −.101 [−.181,−.023], −.245 [−.350,−.143], −.282 [−.407,−.173].

* At 3 s and 5 s the eqgr frontier lies strictly below every baseline across the whole
  bulk range (`figures/frontier_Mge4MAE.png`).
* At 1 s the gain is real at the operating point but modest. With a 0.2% bulk tolerance the
  M≥4 gap is −.025 [−.081,+.035], and the frontiers converge for aggressive r. This is
  physically expected: at 1 s large ruptures are still growing.
* The ablation without the prior factor (eq_nll) loses bulk accuracy (+.005 at 1 s). The
  equivariant constraint and the learned bulk prior are both needed.
* **Caveats still open:** one optimization seed (seed-2/3 runs queued); `mixgr` ablation (free
  mixture × same prior) queued to separate equivariance from the prior factor; augmentation /
  LDS / free-mixture baselines queued. eqgr was specified before the eq_nll results were seen
  (queue2 created 23:30 UTC); later variants are exploratory.

## 2026-10-19 02:20 UTC — interim: equivariance fixes the largest events; bulk cost traced to a label-prior cliff

### Baseline (cat_ce, categorical CE, median action)

| deadline | MAE | MedAE | CVaR95 | M≥4 MAE | M≥4 bias | M≥5 MAE |
|---|---|---|---|---|---|---|
| 1 s | .3272 | .2398 | 1.215 | .7814 | −.733 | 1.110 |
| 3 s | .2714 | .1957 | 1.058 | .6101 | −.557 | .860 |
| 5 s | .2400 | .1699 | .990 | .5660 | −.511 | .818 |

* The tail-weighted median (your "×r tail mass, take median" rule) is almost free near r = 1.
  At 1 s, r = 2 raises bulk MAE by only +.0009 but cuts M≥4 MAE from .781 to .712. So any new
  posterior is judged at **matched bulk MAE**, not at its own default action.
* The classical E3WS-style feature + gradient-boosting baseline is far weaker at every
  deadline (5 s: MAE .310, M≥4 .713, M≥5 .961).

### Negative: the previous project's strongest recipe (emphasized Huber + 0.075 CE) is dominated

At the median action it lowers M≥4 MAE by .06–.09 but raises bulk MAE by +.006. On the
frontier, matching the CE posterior's M≥4 MAE costs **+.0049 [+.0040,+.0059] (1 s),
+.0054 [+.0046,+.0060] (3 s), +.0059 [+.0043,+.0073] (5 s)** more bulk MAE. Its apparent tail
gain is a move along the trade-off curve, not a better posterior.

### Mechanism evidence: the free model saturates

Scaling held-out M≥4 ground motion ×10 raises the categorical model's predicted median by only
**0.39–0.58** magnitude units. In the unseen Central Italy fold at 5 s the response is 0.39.
The amplitude–magnitude relation implies ≈1. Under a Gutenberg–Richter prior the Bayes
posterior is exactly shift-equivariant in log amplitude, even with unknown distance
(THEORY.md). The free network's flattened response is learned under-extrapolation.

### Scale-equivariant head (eq_nll): large gains for the largest events, but a bulk cost

| deadline | Δ bulk MAE | Δ M≥4 MAE | Δ M≥5 MAE | M≥5 at matched bulk |
|---|---|---|---|---|
| 1 s | +.0052 [+.0021,+.0077] | −.001 [−.014,+.018] | −.038 [−.108,+.038] | n/a (frontier never reaches ref bulk) |
| 3 s | +.0034 [−.0001,+.0065] | −.020 [−.037,+.001] | **−.185 [−.278,−.084]** | **−.117 [−.213,−.036]** |
| 5 s | +.0014 [−.0017,+.0039] | **−.036 [−.065,−.007]** | **−.249 [−.374,−.137]** | −.101 [−.219,+.049] |

(median action, eq − cat_ce)

* On the unseen 2016–17 Central Italy sequence (fold 0, includes the M6.5), the M≥5 MAE at 5 s
  falls from **1.008 to 0.550**. The bias for M6.5+ records goes from −1.62 to −0.62.
* **Where the bulk cost comes from:** essentially all of it is the M2.0–2.5 bin (44% of
  records; 1 s MAE .219 → .243). Every other bin is equal or better. The INSTANCE label
  histogram has a 9× cliff at M2.0 (14,790 records at M1.9 vs 130,227 at M2.0), a dataset
  selection rule rather than physics. A categorical head learns the cliff exactly; a smooth
  equivariant likelihood cannot.
* **Verdict for eq_nll alone:** it does not meet the objective (bulk is not preserved at 1 s).
  The next arm, `eqgr` (equivariant likelihood × free 0.1-bin prior below M3.5 × GR-linear tail
  prior), is designed to absorb exactly this cliff while keeping the equivariant tail.

Figures: `figures/frontier_*.png`, `figures/bias_by_magnitude.png`, `figures/amplitude_response.png`.

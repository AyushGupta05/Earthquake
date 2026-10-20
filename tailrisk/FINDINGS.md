# Findings log (newest first)

All numbers are pooled out-of-fold predictions over 1,159,249 INSTANCE records (346 M≥4
events, 31 M≥5) from 5 leave-sequence-out folds. Δ = arm − reference, with 95% cluster-bootstrap
intervals (1,000 replicates; whole GK sequences resampled). Negative Δ in an error is better.

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

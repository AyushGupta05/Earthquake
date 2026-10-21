# GR-factorized, scale-equivariant magnitude posteriors for early earthquake warning

**Started 18–19 Oct 2026.** A self-contained, re-runnable study of **reducing high-magnitude
(tail) error of single-station early magnitude estimates at 1, 3 and 5 s after the P arrival,
without worsening bulk error**, on INSTANCE (1,159,249 records, 54,008 events). The full
dated log, including negative results, is in [FINDINGS.md](FINDINGS.md); every arm's metrics
at 1, 3 and 5 s on every dataset, with paired differences, are tabulated in
[RESULTS.md](RESULTS.md); the theory is in
[THEORY.md](THEORY.md); the prior-art audit (what is new, what is not) is in
[NOVELTY.md](NOVELTY.md). An explanatory notebook is in
[tail_risk_study.ipynb](tail_risk_study.ipynb).

## Result in one paragraph

A deep magnitude posterior of the form

    p(m | x)  ∝  L_θ(m | A, s) · exp(φ(m))

* **L_θ** is a scale-equivariant Gaussian-mixture likelihood: component locations are
  κ(s)(A − A0) + g_k(s), where A is the log RMS amplitude in physical units and s the
  scale-free remainder of the waveform plus station metadata.
* **φ** is one learned global log-prior over magnitude, free below M3.5 and
  Gutenberg–Richter-linear above.

Against the plain categorical posterior (CE) and every other baseline tested, this lowers
high-magnitude error at 1, 3 and 5 s while bulk error stays equal (1 s) or improves
(3 s, 5 s). The leave-sequence-out cross-validation has 346 M≥4 and 31 M≥5 events, with
95% cluster-bootstrap intervals; the result was replicated across seeds and survives
ensembling. Three-seed ensembles, eqgr − CE, median action:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0009 [−.0026,+.0006] | **−.0029 [−.0050,−.0011]** | **−.0046 [−.0061,−.0035]** |
| Δ M≥4 MAE | **−.033 [−.053,−.013]** | **−.045 [−.071,−.021]** | **−.057 [−.089,−.028]** |
| Δ M≥5 MAE | **−.083 [−.149,−.009]** | **−.199 [−.293,−.100]** | **−.262 [−.379,−.160]** |
| Δ M≥4 event-MAE | **−.025 [−.046,−.006]** | **−.038 [−.067,−.016]** | **−.048 [−.083,−.022]** |
| Δ false-M4 rate | lower (−1.0 per 10⁴, CI excludes zero) | equal | equal |

MedAE, CVaR95 (largest 5% of all errors) and the false-M4 rate are unchanged or better.
On the completely unseen 2016–17 Central Italy sequence, the 5 s M≥5 MAE falls from 1.008
to 0.502.

**Against the strongest existing approach** (a TEAM-LM-style free Gaussian-mixture
posterior on the same trunk), both as **three-seed ensembles**, eqgr − mix, median action:

| | 1 s | 3 s | 5 s |
|---|---|---|---|
| Δ bulk MAE | −.0008 [−.0021,+.0000] | **−.0015 [−.0031,−.0003]** | **−.0028 [−.0039,−.0020]** |
| Δ M≥4 MAE | **−.015 [−.023,−.005]** | **−.015 [−.026,−.003]** | **−.025 [−.042,−.009]** |
| Δ M≥4 event-MAE | −.010 [−.020,+.002] | −.011 [−.025,+.003] | **−.020 [−.039,−.003]** |
| Δ M≥5 MAE | −.024 [−.075,+.028] | **−.105 [−.220,−.010]** | **−.149 [−.291,−.040]** |
| Δ false-M4 rate (per 10⁴ records < M3.5) | +1.4 [+0.6,+2.0] | +0.7 [+0.1,+1.3] | +0.7 [+0.2,+1.2] |

The one cost is a small rise in false M≥4 predictions on small events (6.4 vs 5.0 per 10⁴ at
1 s; plain CE is 7.5). Seed-by-fold sign tests (3 seeds × 5 folds × 3 deadlines) put eqgr
ahead on M≥4 error in 36/45 cells, all 9 exceptions in the Emilia fold, and the
distance-marginalized head ahead on M≥5 error in 33/45 (13/15 at both 3 and 5 s; p = .002) and on
bulk error in 30/45 (FINDINGS.md).

**On the original INSTANCE split** (train 2005–17, no selection on VAL), eqgr − mix on VAL 2018:
M≥4 MAE −.025 / −.022 / −.038 (CIs exclude zero), with bulk equal / −.0013 / −.0024. Against the
previous project's best reported VAL model (bulk .365 / .316 / .286, M≥4 .686 / .551 / .487),
the new model matches its M≥4 error with 14% / 19% / 20% less bulk MAE and lower CVaR95.
Most of that cross-project gap comes from the new end-to-end pipeline, which the baselines
here share.

## Why it works: two failure mechanisms, two components

1. **Rare-bin prior learning.** A categorical (or free) posterior has to learn the label
   prior separately in every region of input space. The INSTANCE prior has sharp, non-physical
   structure: a 9× selection cliff at M2.0, and a steep Gutenberg–Richter decay that leaves
   M5+ bins nearly empty. **The GR-factorized prior φ** moves all of this into one global 1-D
   function, estimated from every record. The x-dependent likelihood can then stay smooth, and
   the tail is forced to be GR-linear rather than learned from a handful of events. On top of
   a TEAM-LM-style free mixture, this alone improves bulk, M≥4 and event-level M≥4 at every
   deadline (all CIs exclude zero).
2. **Learned amplitude saturation.** On held-out large events, free networks raise their
   prediction by only .39–.54 magnitude units per 10× of ground motion when amplitudes go
   *beyond* the training range, against .54–.66 when they go down. They flatten exactly
   where they must extrapolate. Under a GR prior the Bayes posterior is exactly
   shift-equivariant in log amplitude even with unknown distance (THEORY.md). **The
   equivariant likelihood** imposes this, with a learned slope κ(s) ≈ 0.6–0.8, and adds the
   large-event extrapolation: M≥5 −.115 / −.141 at 3 / 5 s beyond the factorized free mixture.

Equivariance without the prior factor *hurts* bulk (+.005 MAE, from the M2.0 cliff). The
two components are complementary.

## Baselines (identical trunk, data, folds, schedule)

| arm | what it is | verdict vs eqgr |
|---|---|---|
| `cat_ce` | 71-bin categorical posterior, cross-entropy | dominated (table above) |
| `cat_hubce` | previous project's best recipe: emphasized Huber + 0.075 CE | dominated on the frontier; needs +.005 bulk MAE to match CE's tail |
| `mix_nll` | free Gaussian mixture (TEAM-LM-style head), the strongest existing baseline | eqgr: bulk equal / −.0015 / −.0032, M≥4 −.020 / −.015 / −.023, M≥5 −.03 / −.115 / −.141 |
| `cat_aug` | amplitude-scaling augmentation (×10^Δ, label +Δ) | dominated even by CE; eqgr bulk −.011, bulk-capped M≥4 −.17 at every deadline |
| `cat_lds` | LDS loss reweighting (deep imbalanced regression) | dominated even by CE (+8% bulk, 4× false-M4); eqgr bulk −.023 to −.028, bulk-capped M≥4 −.15 at every deadline |
| `gbm_e3ws` | E3WS-style P-wave features + gradient boosting | far weaker (5 s MAE .310, M≥4 .713) |
| `magnet_nll` | MagNet-style CNN+BiLSTM on amplitude-retaining waveforms (Mousavi & Beroza 2020 layout), Gaussian NLL | far behind at these windows (1 s bulk .397, M≥4 1.03); shows the shared trunk is strong |

**Held-station test.** `mix_nll_hs` and `eqgr_nll_hs` withhold 20% of stations from training in
every fold and are scored on records that are both held-event *and* held-station (279,812
records, 341 M≥4 events). There eqgr − mix is: M≥5 MAE **−.068 / −.111 / −.139** (CIs exclude
zero at all deadlines), M≥4 MAE **−.017 / −.005 / −.011** (significant at 1 and 5 s), bulk
−.002 / −.000 / −.003 (never worse), false-M4 rate lower (1.2 vs 2.9 per 10³ at 1 s) and CVaR95
lower at every deadline. A station fingerprint cannot explain the gain, and the constrained
amplitude response transfers to unknown instruments better than a learned one. The
distance-marginalized head, added to this test on 21 Oct (`eqdgr_nll_hs`), keeps the largest
M≥5 gain on unseen stations: −.158 / **−.201 [−.345,−.060] / −.217 [−.365,−.066]** at equal bulk
error (absolute M≥5 MAE at 5 s: mixture .771, plain equivariant .624, distance-marginalized
.538); replicated in seeds 2 and 3 (−.207 / −.197 and −.215 / −.202 at 3 / 5 s) and as
three-seed ensembles (**−.216 [−.367,−.062] / −.218 [−.367,−.063]**, bulk equal, false-M4 +.4 to
+.9 per 10⁴).

Ablations and exploratory heads:
* `eq_nll`: equivariant, no prior factor. Hurts bulk (+.005).
* `mixgr_nll`: prior factor, no equivariance. A strict Pareto gain over mix, but smaller M≥5 gains.
* `eqtgr_nll`: separate ML/Mw slopes. Negative: no gain over eqgr.
* `mixdgr_nll`: distance-marginalized *free* mixture × GR prior. Best bulk of any single model
  (−.003/−.004/−.006 vs mix) but no tail gain; distance mixing moves bulk, equivariance moves
  the tail (the same holds on GEOFON).
* `eqdgr_nll`: distance-aware likelihood × GR prior. Replicated over three seeds as a
  trade-off, not a replacement. It has the largest M≥5 gains (3-seed ensemble −.12 / −.18 / −.19
  vs mix, −.10 / −.07 / −.04 vs eqgr) and lower 3–5 s bulk. But it gives no M≥4 gain over eqgr
  and has about 1.5× eqgr's 1 s false-M4 rate (9.9 vs 6.4 per 10⁴).

FINDINGS.md records which arms were pre-specified (eq, eqgr), which were ablations added after the first results (mixgr, mixdgr), and which exploratory (eqtgr, eqdgr, the posterior averages).

**Second dataset, negative for equivariance (19 Oct 23:40 UTC).** On a GEOFON regional subset
(31k records, 2,212 events, 276 M≥6, labels mostly mb, mostly 20 Hz broadband at 300–2,000 km),
eqgr is *worse* than the free mixture (three-seed ensembles: bulk +.008–.010, M≥6 +.04–.05),
while the GR prior factor alone is neutral-to-better. Allowing κ → 0 or using scale-specific
slopes does not help. Conditioning the equivariant likelihood on an explicit distance variable
and marginalizing it (`eqdgr`) recovers the largest events (M≥7 −.09 to −.12, three seeds,
CIs exclude zero) at +.02 bulk, and the same distance mixing without equivariance (`mixdgr`)
gains nothing. So: the plain equivariant head is the right prior for local networks like
INSTANCE; on far-regional data the amplitude law must be conditioned on distance, and there it
buys only the largest events. Details in FINDINGS.md.

**Capacity and training length.** At 1.5× trunk width (2.2× parameters) and at 20 epochs the
eqgr − mix differences are unchanged or larger (width: bulk −.002/−.003/−.003, M≥4
−.018/−.021/−.027; epochs: bulk −.000/−.002/−.004, M≥4 −.014/−.011/−.017). A 2.2×-larger free
mixture matches the standard eqgr on M≥4 error but not on M≥5 or bulk error.

**Third dataset, Northern Chile (regional, 40–230 km; 505k station traces picked with
STA/LTA + AIC from the TEAM-LM release; 67 M≥5, 12 M≥6 events; three-seed ensembles, 20 Oct).**
Plain eqgr: worse at 1 s (bulk +.0008, M≥5 +.049, CIs exclude zero), wins the tail at 3–5 s
(M≥5 −.038 / −.089; M≥6 −.25 / −.38, CIs exclude zero; M≥6 error .48 vs .86 at 5 s) at equal
(3 s) or lower (5 s) bulk. The distance-marginalized equivariant head (`eqdgr`) beats the free
mixture on bulk at every deadline (−.0024 / −.0042 / −.0057, CIs exclude zero, negative in all
nine seed × deadline cells), with the same large-event gains at 3–5 s (M≥5 −.043 / −.090;
M≥6 −.28 / −.39) and an equal tail at 1 s. The prior factor alone (`mixgr`) is neutral on
every axis. Size-matched: the six-model average mixgr + eqdgr beats the six-model free + prior-only
average on bulk at every deadline (−.0033 / −.0040 / −.0049) and on M≥5 / M≥6 at 3–5 s
(−.061 / −.088; −.25 / −.33), all CIs excluding zero. Held-station test (7 of the 22 stations
withheld from training, seed 1): on records at unseen stations eqdgr's bulk gain is at least as
large (−.004 / −.013 / −.010, CIs exclude zero; three-seed ensembles −.001 / −.009 / −.007) and
its 5 s large-event gain is negative in all three seeds (M≥6 −.23 / −.29 / −.23, two intervals
excluding zero; ensemble −.26 [−.53,+.03] with 10 M≥6 events) but absent at 1 s; on seen
stations the full-data pattern repeats (ensembles: M≥5 −.087 / −.127, M≥6 −.40 / −.48 at
3 / 5 s). **Which model to use:** on a dense local network
with one magnitude scale, eqgr; otherwise the distance-marginalized form, which is the most
portable across the three catalogues (its one recorded cost: more 1 s false alarms on INSTANCE).

**Calibration (three-seed ensembles, INSTANCE).** The distance-marginalized head has the best
Brier score for P(M≥4) and P(M≥5) at 3 and 5 s (.00822 / .00082 at 5 s vs .00857 / .00091 for the
mixture) and lies on the reliability diagonal for P(M≥4), where the mixture is under-confident
throughout; at 1 s it is slightly over-confident, and both structured heads over-predict P(M≥5) in
the top bin ([figures/reliability_ens3.png](figures/reliability_ens3.png), `results/calibration_ens3.json`).

**What to deploy.** A single station: the distance-marginalized head (`eqdgr`), or the plain
head (`eqgr`) on a dense local network with one magnitude scale. A network: never multiply raw
posteriors; divide each by the training-label prior before multiplying (or use `eqdgr`'s own
factor once on a local network), and check the fused large-event bias on held-out events of the
target catalogue, since the right fusion prior is catalogue- and head-specific. Decide with the
median (or the tail-weighted median for a cost-sensitive alert).

**Three catalogues, one model.** `eqdgr` − free mixture, three-seed ensembles, median action
(bold = 95% cluster-bootstrap CI excludes zero; full table in
[results/cross_dataset_table.md](results/cross_dataset_table.md)):

| dataset (tail metric) | Δ bulk MAE 1 / 3 / 5 s | Δ tail MAE 1 / 3 / 5 s |
|---|---|---|
| INSTANCE, local (M≥5, 31 events) | −.001 / **−.003** / **−.005** | −.12 / **−.17** / **−.19** |
| GEOFON, far-regional (M≥7, 50 events) | **+.024 / +.017 / +.016** | **−.09 / −.09 / −.12** |
| Northern Chile, regional (M≥6, 12 events) | **−.002 / −.004 / −.006** | −.01 / **−.28 / −.39** |

**Event magnitude versus time since the first P** ([figures/fusion_timeline_instance_s1.png](figures/fusion_timeline_instance_s1.png),
[…chile_s1.png](figures/fusion_timeline_chile_s1.png); tables `results/fusion_timeline_summary_*.md`): each station
contributes the posterior of the longest window it has reached. With the naive product the free
mixture's M≥5 / M≥6 estimate never improves as stations arrive (INSTANCE .61 → .75 → .60 from 2 to
4 to 20 s after the first P; Chile flat at .85–.95). With the prior divided out, the equivariant
heads reach .28–.36 on Chile's M≥6 events four seconds after the first P against .71 for the
mixture's best rule (three seeds, CIs exclude zero), and .24 on INSTANCE's M≥5 events at six
seconds against .31.

**Bias by magnitude on all three catalogues** ([figures/bias_by_magnitude_all.png](figures/bias_by_magnitude_all.png),
[results/bias_by_magnitude.md](results/bias_by_magnitude.md)): at 5 s the mean under-estimation of
M6–7 records falls from −.72 / −1.50 (mixture, INSTANCE bins [6, 6.5) / [6.5, 7)) to −.20 / −.36
with the distance-marginalized head, and from −1.01 to −.31 on Chile's [6.5, 7) bin; on GEOFON all
heads saturate (−1.74 vs −1.56 at M8+). At 1 s every head stays strongly biased on the largest
events.

**Multi-station fusion (21 Oct).** Combining the stations of one event exposes a failure mode
of free posteriors: the naive product Π_i p(m|x_i) counts the Gutenberg–Richter prior once per
station, so on all three catalogues the fused M≥5 / M≥6 / M≥7 estimate of the free mixture is
*no better or worse than the nearest station alone* (INSTANCE 1 s: .67 → .92; Chile 5 s: .79 →
.85; GEOFON 5 s: 1.00 → 1.07 event-level MAE), and averaging does not help. Dividing each
posterior by the training-label histogram before multiplying repairs it (.25 / .53 / .60 at 5 s).
The equivariant heads are much less sensitive to the rule, start from better nearest-station
estimates (5 s: INSTANCE .43 vs .63, Chile .30 vs .79), and with the best rule per head give the
best fused large-event error on INSTANCE (eqgr .207, eqdgr .226 vs .252) and Chile (eqdgr .199,
eqgr .221 vs .526; CIs exclude zero) and a tie on GEOFON, plus the best fused bulk error at every
deadline on INSTANCE and Chile (eqdgr with its own factor counted once: −.007 / −.008 / −.007 vs the
mixture's best rule on INSTANCE, three seeds agree). A new proposition (THEORY.md, Proposition 2)
explains when the learned factor is the right prior to divide out: its tail slope is not
identified from single-station data (any exponential tilt is absorbed by the mixture), and the
learned slopes range from −1.85 (eqdgr, INSTANCE) to +0.02 (GEOFON) nats per unit against
catalogue slopes of −2.3 to −1.3; with its own factor the distance-marginalized head's fused
M≥5 estimates are nearly unbiased (−.13 / +.06 / +.05) where the plain head's stay at −.69 /
−.38 / −.29. The histogram rule's level depends on its smoothing and floor (±.06 for the
mixture; the ordering plain-equivariant < mixture holds in every setting at 3–5 s). Pinning
the factor's slope to the catalogue b-value or calibrating a one-parameter tilt on held-out
fused events fixes some heads on some catalogues (Chile: eqdgr .177 at 5 s) and not others
(GEOFON: bulk and tail want opposite tilts), so the fusion prior must be validated per
catalogue; with any sensible prior divided out, the equivariant heads give the best fused
large-event error on all three (.20–.23 vs .25, .18–.20 vs .53, .52–.54 vs .60 at 5 s). Tables: [results/multistation_summary_instance.md](results/multistation_summary_instance.md),
[…chile.md](results/multistation_summary_chile.md), […geofon.md](results/multistation_summary_geofon.md); figures `figures/multistation_*`.

**Known limitation:** in the 2012 Emilia sequence (fold 1, mostly ML-labelled large events),
eqgr is worse than the free mixture. One learned slope κ ≈ 0.7 (Mw-like) under-responds for
large ML labels, which scale ≈1:1 with amplitude.

## Protocol

* **Folds.** Gardner–Knopoff (1974) aftershock-sequence clusters, visited largest-first, so
  background seismicity is not chained together. They are assigned to 5 folds balancing M≥5,
  M≥4 and records. Fold 0 is the entire 2016–17 Central Italy sequence (M6.5, 43% of records).
* **Inputs** (causal, available at the deadline): the 1/3/5 s P-relative 3-component prefix
  converted to physical units with the StationXML sensitivity, 34 static instrument/site
  fields, and station coordinates. Catalogue source fields are used only to build folds and
  for analysis. Distance and magnitude type appear only as *training* labels in the
  exploratory joint heads.
* **Training.** One network serves all three deadlines. Every arm uses the same fixed
  schedule (10 epochs, AdamW 2e-3, cosine) and nothing on a held-out fold is selected.
  The heads differ by a few hundred parameters at most (661,474 for `mix`, 661,521 for
  `eqgr`, 675,095 for `cat`; `eqdgr` 676,941) and all CV arms take 57–65 min for five folds
  on one A10G, so no arm has a capacity or compute advantage.
* **Decisions.** The mean, the median, and the tail-weighted median a_r (r times the weight
  on M≥4 errors). r > 1 is exactly the original "multiply tail mass by r, take the median"
  rule. For a fixed posterior it is Bayes-optimal for every bulk/tail trade-off, so arms are
  also compared on their *frontiers*: the best tail error achievable without exceeding the
  reference's bulk MAE.
* **Uncertainty.** A paired bootstrap that resamples whole aftershock sequences (1,000
  replicates).

## Files

| file | purpose |
|---|---|
| `prep_data.py`, `prep_waveforms.py` | metadata, static instrument features, GK folds, float16 waveform copy |
| `common.py` | GPU data, causal amplitude/shape features, decision rules, metrics |
| `models.py` | encoder; categorical, mixture, equivariant, GR-factorized, distance- and scale-mixture heads |
| `train.py`, `run_queue.sh`, `master.sh`, `queue*.txt` | training and the exact commands run |
| `evaluate.py`, `summary_table.py` | pooled metrics, frontiers, bulk-capped comparisons, cluster bootstrap |
| `diagnostics.py` | amplitude-response (saturation) and calibration diagnostics |
| `gbm_baseline.py` | E3WS-style classical baseline |
| `test_decisions.py` | decision-rule checks against brute force |
| `make_figures.py`, `build_notebook.py` | figures and the explanatory notebook |
| `geofon_prep.py`, `chile_prep.py`, `geofon_eval.py`, `cross_dataset_table.py` | second and third datasets, their evaluator and the cross-dataset summary |
| `results_tables.py` → `RESULTS.md` | every arm's metrics at 1, 3 and 5 s with paired differences, from the evaluation JSONs |
| `export_logpmf.py`, `multistation.py`, `multistation_summary.py`, `multistation_table.py` | full-precision log-posterior export and the multi-station (event-level) fusion study with its cross-seed summaries |
| `fusion_timeline.py` | event magnitude versus time since the first P arrival, fusing whatever each station has |
| `bias_by_magnitude.py`, `test_fusion.py`, `test_theory.py` | bias-by-magnitude figure and table for every catalogue; synthetic checks of the fusion rules and of the two propositions |
| `make_results.sh`, `make_notebook.sh` | regenerate RESULTS.md and the executed notebook |
| `results/` | evaluation JSON, diagnostics, fold summary |
| `figures/` | frontier, bias-by-magnitude and amplitude-response plots |

Large arrays (waveform copy, per-record predictions, checkpoints) live in
`/mnt/eew-research/runs/tailwork` on the AWS host and are not in Git.

Reproduce one arm: `python tailrisk/train.py --arm eqgr_nll --head eqgr --loss nll --epochs 10`
(≈1 h on one A10G for all 5 folds), then
`python tailrisk/evaluate.py --arms cat_ce,eqgr_nll --ref cat_ce`.

# Literature check: "no precedent for a controlled capped-training test" in DL magnitude estimation

Date of search: 2026-10-30. Web search plus full-text reading where I could get it (arXiv PDFs and author preprints, parsed locally). Publisher pages from Wiley, GeoScienceWorld, Springer, ScienceDirect and MDPI mostly returned 403 errors. The "Access" line on each entry says what I actually read.

## Bottom line

- **I found no magnitude-estimation paper (deep learning or classical ML) that does what the work does.** That would mean training only below a magnitude cap, scoring on held-out events above it, and comparing a standard network with a structurally constrained one. The narrow claim survives.
- **The claim still needs qualifying.** Four lines of prior work sit close enough that a reviewer will raise them:
  1. **A deliberate capped-training test exists in deep EEW, for a different target.** WaveCastNet (Lyu et al. 2025) trains on simulations below M4.5 and tests on M4.5–7 ruptures, comparing architectures.
  2. **Incidental extrapolation tests exist for magnitude and PGA.** TEAM and TEAM-LM (Münchmeyer et al. 2021a,b) explicitly evaluate on an event larger than any training event (Mw 6.5 against a training maximum of Mw 6.1). TEAM-LM also studies how the saturation threshold moves with training-set size and composition.
  3. **The amplitude-equivariant output is not new in itself.** Zhang, Zhang & Tian (2021) and Zhang & Zhang (2024) already predict a normalized magnitude Mr = M − log(Amax) and add log(Amax) back. That is the κ = 1 case of the equivariance, argued explicitly as "equalizing the labeled magnitude range between large and small earthquakes". They never tested it under a cap.
  4. **Correcting a network's posterior for its training magnitude prior is not new either.** Münchmeyer, Leser & Tilmann (2022) note that resampling by ρ(M) means the network learns ρ(M)·P(M|O), to be divided by ρ(M). The general-ML version is prior-shift correction (Saerens et al. 2002).

## Closest prior works, ranked

| # | Work | Closeness to a controlled capped-training test |
|---|---|---|
| 1 | Lyu et al. 2025, WaveCastNet (wavefield forecasting) | **Partial, closest in design.** Deliberate cap (M<4.5) and out-of-distribution test above it, with an architecture comparison. Different task, synthetic data. |
| 2 | Münchmeyer et al. 2021b, TEAM-LM (magnitude) | **Partial, closest in magnitude estimation.** Saturation against training data (subsampling, large-only training, upsampling ablation) and an incidental test above the training maximum. No cap. |
| 3 | Münchmeyer et al. 2021a, TEAM (PGA) | **Partial.** Explicitly frames the Norcia Mw 6.5 test as extrapolation. Separate model with 2011 held out tests Tohoku Mw 9.1. Not magnitude, no cap. |
| 4 | Zhang, Zhang & Tian 2021; Zhang & Zhang 2024 | **Unrelated to the cap test, but direct prior art for the equivariant output** (Mr = M − log Amax). |
| 5 | Münchmeyer, Leser & Tilmann 2022 | **Unrelated to the cap test, but prior art for the GR prior and prior correction** in a neural-network magnitude posterior. |

## 1. Seismology: training-range extrapolation in magnitude estimation

**Münchmeyer, Bindi, Leser & Tilmann (2021b). "Earthquake magnitude and location estimation from real time seismic waveforms with a transformer network" (TEAM-LM).** GJI 226(2), 1086–1104. doi:10.1093/gji/ggab139; arXiv:2101.02010.
- **Access:** full arXiv text read.
- **What they did:**
  - Oversampled large events, and ablated that. Removing upsampling degrades large-event performance.
  - Saturation sets in at about M5.5 for Italy and about M6.0 for Chile. Japan shows none up to about M7, because its training set includes Tohoku 2011.
  - They argue saturation comes from scarce training labels, not rupture physics. They read Mousavi & Beroza (2020) as saturating near M3.
  - Section 4.3 trains on every k-th event (k = 2 to 64). "The lower the amount of training data, the lower is the saturation threshold." With the smallest subsets the largest events fall further below that threshold.
  - Section 4.4 trains on large events only, a truncation from below. It is worse even on large events.
  - The Italy chronological split makes the Mw 6.5 test event larger than the largest training event (Mw 6.1). They blame degraded fine-tuned performance on exactly this.
  - Transfer learning from other regions removes Italian saturation.
  - Log peak amplitude is fed as an extra input, not built in as equivariance.
- **Closeness: partial.** This is the most relevant magnitude paper. It studies saturation against training-data size and composition and has one uncontrolled, roughly 0.4-unit extrapolation case. It applies no magnitude cap and compares no structural model with a free one.

**Münchmeyer, Bindi, Leser & Tilmann (2021a). "The transformer earthquake alerting model: a new versatile approach to earthquake early warning" (TEAM).** GJI 225(1), 646–656. doi:10.1093/gji/ggaa609; arXiv:2009.06316.
- **Access:** full arXiv text read.
- **What they did:**
  - The target is PGA, not magnitude.
  - The Italy test year 2016 contains Mw 6.5 Norcia, "notably larger than any in the training set (Mw 6.1)… challenging the extrapolation capabilities of TEAM."
  - They "domain adapt" by adding large events from other regions.
  - A separate model with 2011 held out is tested on Tohoku Mw 9.1 and "underestimates the main shock" (the last point is from the SSA abstract).
- **Closeness: partial.** It states extrapolation as a goal and tests it incidentally through chronological splits, but uses no cap, no ablation and a different target.

**Zhang, Zhang & Tian (2021). "Real-Time Earthquake Early Warning With Deep Learning: Application to the 2016 M 6.0 Central Apennines, Italy Earthquake".** GRL 48, e2020GL089394. doi:10.1029/2020GL089394; arXiv:2006.01332.
- **Access:** full arXiv text read.
- **What they did:**
  - The network outputs a 1D Gaussian over a normalized magnitude Mr = M − log(Amax). The final M is Mr + log(Amax), so κ is fixed at 1.
  - The stated aim is "excluding the contribution of absolute amplitudes and equalizing the labeled magnitude range between large and small earthquakes."
  - Training uses 2,506 events from a catalogue spanning M2.5–6.5, which includes events larger than the test mainshock.
  - The test set is the M6.0 mainshock plus 500 aftershocks. The mainshock and the M5.4 aftershock are underestimated, which they attribute to clipping.
- **Closeness to the cap test: unrelated, since there is no extrapolation test.** It is still the most important precedent for the equivariant output, and the paper should cite it and say how its version differs (learned κ, distributional output, the cap test itself).

**Zhang & Zhang (2024). "Universal neural networks for real-time earthquake early warning trained with generalized earthquakes".** Commun. Earth Environ. 5. doi:10.1038/s43247-024-01718-8; arXiv:2312.15218.
- **Access:** full arXiv v1 text read; the published version was read through a WebFetch summary of the PMC page.
- **What they did:**
  - "Generalized earthquakes" recombine real single-station records by distance and depth.
  - Amplitudes are normalized to an equivalent ML 3.0 using Hutton & Boore (1987). The magnitude network again predicts Mr = M − log(Amax).
  - The base training data are Italy (M≥2.5), Oklahoma (M≥3) and southern California (M≥2.5).
  - The published version adds 21 Japanese M>6 events, augmented to about 100k samples, for the magnitude network. That widens the training range instead of testing extrapolation.
  - Kumamoto M7.3 reaches M7.1 at 15 s. The paper notes small events dominate training.
  - I saw no ablation with and without the large events.
- **Closeness: unrelated (no cap test).** It is relevant as a synthetic or recombination route and as further prior art for amplitude normalization.

**Mousavi & Beroza (2020). "A Machine-Learning Approach for Earthquake Magnitude Estimation" (MagNet).** GRL 47, e2019GL085976. doi:10.1029/2019GL085976; arXiv:1911.05975.
- **Access:** arXiv text only; the GRL page returned 403.
- **What they did:** single-station CNN plus LSTM on STEAD (within 1°). Performance is "worst at upper and lower bounds", which they attribute to few samples there. No experiment varies the training magnitude range.
- **Closeness: unrelated.** It only observes saturation.

**Lomax, Michelini & Jozinović (2019). "An Investigation of Rapid Earthquake Characterization Using Single-Station Waveforms and a CNN".** SRL 90(2A). doi:10.1785/0220180311.
- **Access:** author preprint read.
- **What they did:** waveforms normalized with `stream_max` appended for magnitude, and 0–10 magnitude bins. Training and test both span the target range, with no extrapolation analysis.
- **Closeness: unrelated.**

**Kuang, Yuan & Zhang (2021). "Network-Based Earthquake Magnitude Determination via Deep Learning".** SRL 92(4), 2245. doi:10.1785/0220200317.
- **Access:** abstract only, via Semantic Scholar.
- **What they did:** multi-station network at the China Seismic Experimental Site. It does well for small and moderate events but poorly above M6.5, which they attribute to few large training events.
- **Closeness: unrelated (observational).**

**Chakraborty et al. (2022). "CREIME".** JGR Solid Earth 127. doi:10.1029/2022JB024595; arXiv:2204.02924.
- **Access:** arXiv text read.
- **What they did:** under- and over-sampling to flatten the magnitude distribution, plus a loss that penalizes underestimating large events. Underestimation persists above about M5.5. No range test.
- **Follow-up:** Li et al. (2024), Solid Earth 15:197, doi:10.5194/se-15-197-2024, apply CREIME to Kahramanmaraş aftershocks only (roughly ML −0.8 to 5.7 per a search snippet), not the mainshocks. I found no paper titled "CREIME_RT".
- **Closeness: unrelated.**

**Dybing, Yeck, Cole & Melgar (2024). "Rapid estimation of single-station earthquake magnitudes with machine learning on a global scale" (AIMag).** BSSA 114(3), 1523–1538. doi:10.1785/0120230171.
- **Access:** USGS abstract plus the matching dissertation chapter.
- **What they did:**
  - MagNet architecture trained on about 2.4M global P arrivals.
  - Accurate from about M2.3 to M7.6 with a 114 s window, but underestimates above about M7.
  - Shorter windows move the onset of underestimation to lower magnitudes. They attribute this to saturation (the window misses the source time function) plus scarce large training events.
  - This is saturation against window length, not against training-label range.
- **Ridgecrest:** I found no Ridgecrest experiments in this paper. In Dybing's 2024 dissertation, Ridgecrest appears in a strain-based rupture-predictability chapter with SW4 simulations, not in the neural-network magnitude work. The brief's "Ridgecrest experiments" may refer to a different paper.
- **Closeness: unrelated.**

**Joshi et al. (2024). Two papers.**
- **Access:** abstract only for the TGRS paper; no abstract was available for the NCA paper.
- **Papers:**
  - "An integrated approach for prediction of magnitude using deep learning techniques", Neural Comput. Appl. 36, 16991–17006 (doi:10.1007/s00521-024-09891-9).
  - "A Deep Attention Model for Onsite Estimation of Earthquake Epicenter Distance and Magnitude", IEEE TGRS 62 (doi:10.1109/TGRS.2024.3459425). It uses LSTM with attention plus XGBoost on 3 s of P wave, on Japanese data.
- **What I saw:** nothing on range extrapolation in the abstracts. A related 2025 paper (Geodesy & Geodynamics, doi:10.1016/j.geog.2024.10.001) uses CTGAN-synthesized features to counter imbalance among large Japanese events. That is augmentation, not a cap test.
- **Closeness: unrelated, at abstract level only.**

**Others checked, all with no cap test:**
- **Zhu et al. (2021), Front. Earth Sci., DCNN-M** (doi:10.3389/feart.2021.653226; read). K-NET data up to about M_JMA 7.2. Underestimation for M_JMA ≥ 7.5 "remains to be studied", and they suggest extending the training range.
- **Ren et al. (2023), GJI 234(2):1355** (doi:10.1093/gji/ggad137; read through WebFetch). An ML≥5 against ML<5 classifier. They claim "reliable estimation for events larger than any in the training data" (CENC training, STEAD test up to Mw 7.7). That is incidental, and classifying above a threshold does not require extrapolating a label value.
- **Jozinović et al. (2020), GJI 222(2):1379** (doi:10.1093/gji/ggaa233; read). This predicts intensity measures, not magnitude. Under 5-fold cross-validation, performance on the three largest events (M5.9, 6.0, 6.5) degrades because only 5 events above M5 are in training. They cite Gutenberg–Richter imbalance and suggest augmenting large events.

## 2. Synthetic and physics-based routes to large magnitudes

These train on simulated large events that cover the target range, so they avoid extrapolation rather than test it.

- **Lin, Melgar et al. (2021), M-LARGE, JGR Solid Earth.** HR-GNSS with FakeQuakes megathrust ruptures, tested on real Chilean events.
- **Lin et al. (2023), JGR Solid Earth** (doi:10.1029/2023JB027255).
- **Quinteros-Cartaya et al. (2023), arXiv:2304.09912.** Synthetic Chilean Mw ~7–9.6. Overestimation at Mw ≤ 6.9 and underestimation at Mw ≥ 9.5, at the edges of the training distribution.
- **Dybing et al. (2026), BSSA** (doi:10.1785/0120250220; GNSS PGD).
- **PEGS models:** Licciardi et al. 2022, Nature; Commun. Earth Environ. 2024, doi:10.1038/s43247-024-01725-9.
- **Duan et al. (2025), arXiv:2509.16874, diffusion waveform generator.** Says generated data "reduced prediction bias from uneven training data" for magnitude. Abstract only; I did not see any test above the training range.

**Closeness: all unrelated to the cap test.** WaveCastNet (below) is the exception, because it does test above its training range.

## 3. Deliberate capped training in deep EEW, non-magnitude target

**Lyu, Nakata, et al. (2025). "Rapid wavefield forecasting for earthquake early warning via deep sequence to sequence learning" (WaveCastNet).** Nat. Commun. doi:10.1038/s41467-025-65435-2; arXiv:2405.20516.
- **Access:** arXiv v2 HTML read through WebFetch.
- **What they did:**
  - Trained only on point-source simulations below M4.5.
  - Tested out of distribution on finite-fault ruptures from M4.5 to M7.
  - Accuracy holds to about M5.5 (0.95), then drops to 0.88, 0.66 and 0.53 at M6.0, 6.5 and 7.0, with amplitudes underestimated.
  - Transformers generalize worse than their ConvLEM model.
  - They attribute the drop to rupture durations exceeding the input window.
- **Closeness: partial, but the closest in design** (a cap, a test above it, and a structural comparison). The differences: the target is wavefield forecasting, not magnitude; the data are synthetic; and the cap coincides with a change of source type.

Ground-motion ML shows the same pattern under truncation. Chen et al. (2023), arXiv:2303.14179, hold out the near field by distance and find a physics-symbolic model extrapolates better than an ANN. I saw snippets only, and the truncated variable is distance, not magnitude.

## 4. General ML: the closest three

1. **Villar, Yao, Hogg, Blum-Smith & Dumitrascu (2023). "Dimensionless machine learning: imposing exact units equivariance".** JMLR 24; arXiv:2204.00887.
   - **Access:** read.
   - **What they did:** springy double pendulum. Train with parameters drawn from Unif(1, 2), test on Unif(1, 5) and on unit-rescaled inputs. They compare a units-equivariant model with a same-size non-equivariant baseline (0.044 against 0.189, and 0.009 against 0.367).
   - **Fit:** the closest structural analogue, since amplitude scaling is a units or scale symmetry. But it shifts the input range, not a capped scalar label with a prior.
2. **Wang, Walters & Yu (2021). "Incorporating symmetry into deep dynamics models for improved generalization".** ICLR 2021; arXiv:2002.03061.
   - **Access:** read.
   - **What they did:** scale-equivariant against standard ResNet and U-net on test data rescaled by λ drawn from U(1/5, 2), outside the training distribution. "EquScal-ResNet is very robust across various scaling factors while ResNet does not generalize."
3. **Xu et al. (2021). "How neural networks extrapolate: from feedforward to graph neural networks".** ICLR 2021; arXiv:2009.11848.
   - **What they found:** ReLU MLPs extrapolate linearly. Extrapolation succeeds only when the right nonlinearity is built into the architecture or features. This is theoretical support for "structure enables extrapolation".

**Protocol-only precedents** (they truncate the label range but do not compare structural and free models):
- Yang et al. (2021, ICML), "Delving into Deep Imbalanced Regression": removes target ranges and evaluates zero-shot interpolation and extrapolation.
- Xiong et al. (2020), Comput. Mater. Sci. 171:109203, doi:10.1016/j.commatsci.2019.109203: k-fold forward cross-validation, which sorts by label, trains on low values and tests on high ones.

**For the train/test prior swap:** Saerens, Latinne & Decaestecker (2002), Neural Computation 14(1):21–41, on adjusting a model's outputs to new prior probabilities. Classical Bayesian EEW already uses a Gutenberg–Richter prior: Cua & Heaton's Virtual Seismologist, and Meier, Heaton & Clinton (2015, BSSA), the "Gutenberg algorithm".

## 5. Verdict and suggested wording

**Verdict: accurate as narrowly stated, but it must be qualified.** "No prior work has run a controlled capped-training extrapolation test for deep-learning magnitude estimation" holds for what I could find. As written it invites three objections. TEAM and TEAM-LM did test on events above the training maximum and studied saturation against training data. WaveCastNet ran exactly this kind of cap experiment in deep EEW. Zhang et al. already built the amplitude-normalized output.

**Suggested rewording:**

> "To our knowledge, no prior study of learned magnitude estimation has run a controlled capped-training test: training only on events below a magnitude cap and evaluating on held-out events above it, comparing an unconstrained network with a structurally constrained one. Previous work documents saturation near the upper end of the training distribution and its dependence on training-set size and composition (Mousavi & Beroza 2020; Münchmeyer et al. 2021b; Dybing et al. 2024). It also reports incidental tests on events modestly larger than any training event (Münchmeyer et al. 2021a,b). Amplitude-normalized magnitude targets, which correspond to our equivariance with κ = 1, were introduced by Zhang et al. (2021) and Zhang & Zhang (2024), but were not evaluated beyond the training range. A capped design comparable to ours has so far appeared only for wavefield forecasting (Lyu et al. 2025), where a model trained on M < 4.5 simulations degrades on M6–7 ruptures."

Also position the GR-prior swap against Münchmeyer, Leser & Tilmann (2022), which corrects a network posterior for its resampled magnitude prior, and against Saerens et al. (2002).

## 6. Confidence and gaps

- **Confidence:** moderately high, about 75–80%, that no controlled cap test for magnitude estimation exists in the main venues (GJI, GRL, JGR, SRL, BSSA, Nature-family journals, arXiv physics.geo-ph). Confidence is lower for:
  - the long tail of low-visibility ML-for-magnitude papers (Sci. Rep., IEEE, Elsevier and Springer AI journals, MDPI);
  - non-English venues, for example Acta Seismologica Sinica and Chinese J. Geophys.;
  - conference abstracts (AGU, SSA, EGU);
  - 2026 papers not yet indexed.
- **Could not access, or saw only partly:**
  - Wiley GRL/JGR, GeoScienceWorld (SRL/BSSA), Springer, ScienceDirect and MDPI full texts returned 403. For MagNet, CREIME and Zhang 2021 I relied on the arXiv preprints.
  - Abstract only: Kuang et al. 2021, Joshi et al. 2024 (TGRS), the 2025 Applied Sciences systematic review (doi:10.3390/app15073492), and the 2026 ScienceDirect and Sci. Rep. magnitude papers (snippets only).
  - No abstract at all: Joshi et al. 2024 (NCA).
  - The published Zhang & Zhang 2024 version was read only through a WebFetch summary of the PMC page.
  - The arXiv API was rate-limited, so I could not do a systematic arXiv listing sweep and relied on web search instead.
- **Brief discrepancies:**
  - I found no Ridgecrest experiments in Dybing et al. 2024 (see above).
  - No paper is titled "CREIME_RT".

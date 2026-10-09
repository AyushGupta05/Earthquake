# Early earthquake magnitude distributions: evidence, limits, and a defensible method

**Research date: 9 October 2026. Status: research synthesis and exploratory experiments, not a completed paper or a state-of-the-art claim.**

## Recommendation

Retain the distribution approach, but change its scientific target. Learn a well-scored conditional magnitude distribution, expose how strongly it depends on the magnitude prior, and only then derive a point estimate or an alert under explicitly measured costs. The most promising contribution is a **prior-aware, tail-sensitive distributional correction with protected average accuracy**, demonstrated across backbones and independently held-out earthquakes. Neither a probability output, a Bayesian prior, a weighted median, nor threshold-weighted CRPS is individually new.

The September report is useful evidence of a trade-off, not proof that the underlying waveform contains insufficient information. Its stronger corrections often reduced M>=4 error while increasing the worst-error tail or false alerts. The new repository audit also found an input-duration mismatch in old notebooks, and only 13 distinct M>=4 events in their validation set. Resolve these issues before using those results to choose an architecture or to write a strong conclusion.

The supplied `2608.18864v1.pdf` is **RVLoss**, a LiDAR scene-flow loss paper; it is not the separate ICP-Flow paper. Its relevant research pattern is: identify a concrete failure of the existing objective, introduce a mechanism that fixes that failure, and demonstrate the mechanism across backbones and datasets. Its geometric voting algorithm is not directly justified for earthquake probabilities. [RVLoss](https://arxiv.org/abs/2608.18864)

## Search scope and evidence standard

This is a broad, targeted review of early magnitude estimation, probabilistic EEW, early rupture predictability, large-event imbalance, and decision calibration. Searches covered foundational methods through material available on 9 October 2026. Query families included “earthquake early warning magnitude probabilistic distribution,” named models, Bayesian magnitude priors, early rupture predictability, 2025/2026 magnitude methods, imbalanced regression, and proper tail scoring. Reference trails in TEAM-LM, CREIME, and Hou et al. were followed. Primary papers, author preprints, official dataset documentation, and USGS technical material support the recommendations.

It is not a claim to have screened every publication in every bibliographic database. Preprints are identified, publisher access failures are not presented as full-text reviews, and unrelated pre-event earthquake forecasting is excluded. Reported scores below are contextual: differences in magnitude scale, event split, station count, duration, SNR filtering, and latency mean they cannot be ranked against the current INSTANCE MAE.

## What the relevant methods establish

| Work | Mechanism and evidence relevant here | What to adopt or test |
|---|---|---|
| [Wu & Zhao, 2006: first-three-second P-wave amplitude](https://doi.org/10.1029/2006GL026871) | Relates early peak displacement to magnitude while correcting for distance. A direct physical-feature baseline. | Compare a calibrated amplitude/distance baseline. Use physical units and an online distance estimate; catalog distance is an explicitly labelled oracle control. |
| [Kuyuk & Allen, 2013: global EEW magnitude relation](https://seismo.berkeley.edu/~rallen/pub/2013kuyuk2/KuyukAllen-GlobalEEWMagRelation-GRL-2013.pdf) | Studies transferable early amplitude-based magnitude estimation. | Test physically interpretable observables before assuming a larger neural backbone is necessary. |
| [Virtual Seismologist: Cua / Cua & Heaton](https://ocmsnode25-02-b.ethz.ch/en/knowledge/earthquake-data-and-analysis-tools/EEW/Virtual-Seismologist/) | Bayesian early magnitude/location/shaking estimation already combines early observations with prior information, including Gutenberg–Richter alternatives. | Acknowledge Bayesian EEW as prior art. Separate the prior from waveform evidence and document which population each prior represents. |
| [Lancieri & Zollo, 2008: RTMag](https://basin.earth.ncu.edu.tw/Course/SeminarII/abstract2014_1/2015.03.19_Chiao%20Chu%20Hsu/RTmag.pdf) | Bayesian magnitude estimation from early P and S displacement peaks. | Sequential probabilistic updates are an established comparator, not an independent novelty claim. |
| [Bayesian multiple-event EEW, 2015](https://academic.oup.com/gji/article/200/2/791/610068) | Explicitly discusses a seismicity prior that underestimates magnitude when warnings matter, and chooses a uniform alternative in that application. | “Removing the prior reduces underestimation” is also not new. Compare uniform-prior and calibrated-prior controls. |
| [MagNet, Mousavi & Beroza, 2020](https://arxiv.org/abs/1911.05975) | Single-station learned magnitude estimation from seismic signals; an important neural baseline. | Adapt its backbone only with the same causal prefix protocol. Do not compare full-record results to 1-second predictions. |
| [TEAM, Münchmeyer et al., 2021](https://arxiv.org/abs/2009.06316) | Transformer-based, flexible-station probabilistic ground-motion prediction. Its target is shaking rather than just magnitude. | Borrow station masking and probability-to-alert evaluation. Magnitude MAE is only one component of EEW utility. |
| [TEAM-LM, Münchmeyer et al., 2021](https://arxiv.org/abs/2101.02010) | Dynamic station sets, a five-Gaussian magnitude mixture, likelihood training, temporal masking, high-magnitude oversampling, transfer learning, and uncertainty calibration analysis. The paper documents large-event underestimation and benefits of regional transfer. | This is the closest essential probabilistic magnitude baseline. Borrow mixture heads, causal station availability, ensembles, and large-event transfer. Reproduce on a common split before claiming superiority. |
| [CREIME, Chakraborty et al., 2022](https://doi.org/10.1029/2022JB024595) | CNN/recurrent identification and magnitude estimation with about 1–2 seconds of P-wave signal. Uses imbalance remedies and an underestimation penalty; high-magnitude bias remains. | Match the short-window task and compare weighted objectives. Its authors also flag limited unique high-magnitude examples and mixed magnitude scales. |
| [EEWNet, 2023](https://www.sciencedirect.com/science/article/pii/S1342937X2200185X) | CNN-based magnitude estimation from less than 3 seconds at one station. | Include a compact CNN comparator; expensive attention is not the only credible baseline. Detailed replication requires the full preprocessing/training protocol. |
| [EEWMagNet, 2023](https://www.sciencedirect.com/science/article/pii/S2666544123000187) | Dense convolutional blocks and attention using 7-second three-component records. | Architecture ideas are transferable; the reported observation duration is not matched to this project. |
| [Hou et al., 2024](https://doi.org/10.1186/s40623-024-02005-8) | Combines multiple waveforms, differential P arrivals, and differential station locations. Reports MAE below 0.29 after 3 seconds from the earliest P arrival, using its own Japanese data protocol. | Borrow the treatment of distance as uncertain information inferred from station geometry and arrivals. A later station must contribute only its actually available prefix. |
| [Zhang & Zhang, 2024: generalized earthquakes](https://doi.org/10.1038/s43247-024-01718-8) | Recombines recordings across stations/locations, truncates for real time, and augments M>6 recordings. Magnitude is represented by a Gaussian-shaped output. | Borrow causal augmentation and explicit amplitude/distance channels. A Gaussian training label alone does not establish calibrated predictive uncertainty. |
| [FisH, 2024 preprint](https://arxiv.org/abs/2408.06629) | RetNet streaming architecture jointly handles picking, location, and magnitude. Reports a 3-second magnitude error of 0.18 on its STEAD experiment. | Borrow recurrent inference and evaluate real pick latency. The headline error is not an INSTANCE benchmark or a demonstrated M>=6 guarantee. |
| [DFTQuake, 2025](https://www.sciencedirect.com/science/article/pii/S0952197625000776) | Fourier/attention/dendrite architecture for early magnitude and PGA. Publisher abstract/indexed material located; full text was not available through the research tool. | Frequency and time views are a candidate ablation, not an established reason to add a complex backbone. Replication details remain to be obtained. |
| [MDLNet, 2025](https://doi.org/10.1186/s40562-025-00412-7) | Fuses time, frequency, and ground-motion parameters to classify noise, M<5.5, and M>=5.5 from a 3-second P-wave prefix. | Test an auxiliary exceedance task. Coarse high/low classification does not replace a calibrated continuous magnitude distribution. |
| [A2MAG, 2026](https://doi.org/10.1038/s44304-026-00242-3) | Attention-based 3-second strong-motion estimation on Japanese K-NET data; reported MAE 0.33, with systematic M>6 underestimation. | A recent matched-duration reference, and motivation to report magnitude-stratified bias. Its error cannot be compared directly with mixed-scale Italian data. |
| [SeisMamba, August 2026 preprint](https://arxiv.org/abs/2608.24561) | Compact convolution/state-space backbone with a regional holdout diagnostic and reported low inference latency. | A later efficiency baseline. Verify exact early-window and split details before quoting its benchmark as an EEW improvement. Abstract-level assessment in this review. |
| [USGS ShakeAlert technical plan, 2025](https://pubs.usgs.gov/of/2025/1003/ofr20251003.pdf) | Describes EPIC point-source, FinDer finite-fault, and GFAST-PGD geodetic information contributing complementary source estimates. | Large events may need additional physical information. A single-station magnitude experiment must not be presented as replacing a complete operational warning system. |
| [USGS GNSS/slip study, 2026](https://www.usgs.gov/publications/potential-impact-three-dimensional-distributed-slip-models-derived-real-time-gnss-data) | Examines real-time GNSS/distributed-slip information for large subduction earthquakes. | Treat nonsaturating geodetic evidence as a distinct later/multisensor task, not something a short-window probability correction creates. |
| [Zhang, Zhang & Tian, 2021](https://arxiv.org/abs/2006.01332) | Fully convolutional detection, location, and magnitude from continuous network streams, evaluated on the Central Apennines sequence. | Test the entire evolving pipeline and common first-arrival clock. A sequence result is not evidence of general regional transfer. Abstract-level assessment here. |
| [AMagDN, Joshi et al., 2024](https://doi.org/10.1007/s00521-024-09891-9) | LSTM/BiLSTM, autocorrelation attention, waveform-derived series and seven source/geospatial parameters on Japanese M5.5–8.0 records. Publisher abstract available; full text is subscription-only. | Physical feature fusion is relevant. Audit when every source/geospatial feature becomes available and verify event separation before replication. A magnitude-restricted population is not the natural small-to-large distribution. |
| [M-LARGE, Lin et al., 2021](https://doi.org/10.1029/2021JB022703) and [finite-fault extension, 2023](https://doi.org/10.1029/2023JB027255) | Learns evolving magnitude from HR-GNSS deformation with synthetic ruptures and checks real Chilean events; later adds source location and fault size. | Simulated large-event training is relevant but requires real-event validation. Tens-of-seconds geodetic results are not a matched 1-second seismic comparator. |
| [MagEs, 2025 preprint](https://arxiv.org/abs/2503.20584) | Single/up-to-three-station HR-GNSS magnitude model, synthetic Chile training, coupled with detection in SAIPy. | Separate detection delay from time since rupture. Candidate additional sensor evidence; abstract-level assessment, not a replicated benchmark. |
| [Italian high-speed railway EEW, 2026](https://nhess.copernicus.org/articles/26/299/2026/) | Converts uncertain PGA predictions into exceedance decisions and requires configurable spatial/temporal station coincidence. | Borrow explicit decision thresholds and evaluate unnecessary interruptions. Magnitude MAE alone does not establish end-user warning benefit. |

## What physics says—and what it does not say

[Meier, Heaton & Clinton (2016)](https://doi.org/10.1002/2016GL070081) found similar initial rupture behaviour over their studied magnitude range. [Goldberg et al. (2018)](https://doi.org/10.1029/2018JB015962) examined weak determinism with geodetic observations. [Colombelli, Festa & Zollo (2020)](https://academic.oup.com/gji/article/223/1/692/5873011) reported useful early rupture-growth signals. These are not interchangeable experiments and should not be compressed into a universal statement that either “one second determines final magnitude” or “nothing is knowable.”

[Münchmeyer, Leser & Tilmann (2022)](https://arxiv.org/abs/2203.08622) is particularly close to the intended motivation: it studies conditional magnitude distributions, distinguishes information about becoming large from a sharply determined final magnitude, and reports limits on early predictability for its observables. Borrow its distinction between point predictability and probabilistic information gain. It does not prove an information bound for the present INSTANCE CNN.

A practical test is whether new waveform/station features improve event-held-out probability scores or rare-event ranking. An upward shift that lowers high-magnitude absolute error without improving those measures is a decision trade-off, not demonstrated extraction of additional rupture information.

## Methods outside seismology that must be compared

| Work | Relevance and limitation |
|---|---|
| [Deep Imbalanced Regression: LDS/FDS, Yang et al., ICML 2021](https://arxiv.org/abs/2102.09554) | Smooth label densities and learned feature distributions. Include LDS weighting; FDS requires actual learned features. Do not silently substitute test-label-conditioned smoothing. |
| [Balanced MSE, Ren et al., CVPR 2022](https://openaccess.thecvf.com/content/CVPR2022/html/Ren_Balanced_MSE_for_Imbalanced_Visual_Regression_CVPR_2022_paper.html) | Corrects a regression objective for label imbalance. It targets a different population balance and need not preserve natural-population MAE. |
| [Logit adjustment, Menon et al., ICLR 2021](https://arxiv.org/abs/2007.07314) | Prior-dependent logit corrections are established. The current alpha sweep belongs to this family; its distinctive contribution would need to be elsewhere. |
| [Threshold/quantile-weighted proper scores, Gneiting & Ranjan](https://citeseerx.ist.psu.edu/document?doi=07b14f69099d1fdab8f09ff4e4155f379a5fcd8d&repid=rep1&type=pdf) | Emphasises a forecast tail while retaining propriety. This provides the cleanest mathematical alternative to pretending cost-inflated probabilities are posterior beliefs. The linked author report precedes the 2011 journal version. |
| [Conformal risk control, Angelopoulos et al., ICLR 2024](https://research.google/pubs/conformal-risk-control/) | Controls expected monotone losses under its assumptions. Ordinary MAE differences under arbitrary magnitude corrections are not automatically monotone. |
| [Non-monotonic conformal risk control, Angelopoulos, 2026 preprint](https://arxiv.org/abs/2602.20151) | Extends the framework using algorithm stability. A possible later theory component, but no guarantee is imported into the current empirical selection rule. |

## Precise interpretation of the current method

The original CNN exposes 66 bins with centres 0.05, 0.15, …, 6.55. Let its softmax be p(k|x), and let pi(k) be the saved training magnitude prior. The notebook computes

    q_alpha(k|x) ∝ p(k|x) * pi(k)^(alpha - 1),
    mu_alpha(x) = sum_k m_k q_alpha(k|x).

Five such means describe sensitivity to a prior perturbation. They are deterministic functions of the same waveform output, not five independent observations. For a fixed positive prior,

    d mu_alpha / d alpha = Cov_q_alpha(M, log pi(M)).

For an exactly exponential Gutenberg–Richter prior, log pi(M)=constant−b ln(10) M, this becomes −b ln(10) Var_q_alpha(M). Thus prior sensitivity can encode spread. It need not add information beyond the full distribution; its value may be efficient compression or a useful inductive bias. The exponential identity does not hold for an arbitrary smoothed empirical prior.

A tree distribution followed by multiplying M>=4 mass by r and taking a median minimises a magnitude-dependent weighted absolute loss under that tree distribution. It does **not** automatically recover the true posterior. Ignoring a boundary tie, its median reaches the high group when the original high-group probability exceeds 1/(r+1): for r=11, only about 8.3% high-group probability is needed. This explains why false alerts can rise strongly.

The current CNN was trained with weighted Huber on the output mean plus cross-entropy. Its output need not be a calibrated training posterior. Therefore dividing it by an empirical prior is a hypothesis to validate, not an exact Bayesian inversion. A natural magnitude prior, a resampled training prior, a regional deployment prior, and an alert cost are four different objects.

A basic limitation follows: if the conditional distribution were already correct, its median would minimise conditional absolute error. No method using only that same information can guarantee strict overall MAE improvement over the Bayes median. Improvement requires existing miscalibration/model error, additional information, a changed objective, or a distribution shift. Preserving mean and median *error* must be tested; preserving the mean/median of predicted magnitudes is a different constraint.

## Proposed contribution: separate tail learning, prior sensitivity, and decisions

Working description: **prior-aware tail calibration for early magnitude distributions**. This is a research hypothesis, not a claimed new named algorithm.

1. **Train a causal distribution, with explicit prior accounting.** Start with the current CNN and a second backbone such as a compact residual CNN or TEAM-LM-style station encoder. Preserve physical amplitude through a separate log-amplitude channel if per-trace normalisation is used. Enforce waveform prefixes and available station masks. Prefer physically calibrated units when testing across instruments/regions. State the magnitude scale, or model scale explicitly; do not silently equate ML, Mw, and Md.
2. **Emphasise tail CDF accuracy with a proper objective.** For predicted CDF F and target y, use ordinary CRPS plus a nonnegative threshold-weighted component. For example:

       S(F,y) = integral [1 + lambda * 1(u >= u0)] * (F(u) - 1(y <= u))^2 du.

   Here u0 is fixed before fitting (M4 for the current diagnostic; M5/M6 for a suitable external benchmark). The weight is a function of the evaluation threshold, not the realised target. For a true CDF G, the expected score gap is the weighted integral of (F−G)^2. Positive weights preserve the true distribution as the optimum. This is established proper-scoring theory, not our novelty claim. It does not guarantee finite-sample MAE gains.
3. **Learn where prior sensitivity is informative.** Compare full probabilities, five prior-response means, and mean-only inputs under identical event splits and model budgets. Add causal waveform evidence—amplitude growth, frequency content, SNR, clipping indicators, and uncertainty in distance—to test whether they distinguish a genuinely large event from a broad/uncertain small-event prediction. No target magnitude, future P/S arrival, or later waveform may enter an early decision.
4. **Protect ordinary accuracy at decision time.** Define a small family of corrections a_lambda(x) using the learned distribution, with the unmodified prediction always available. Select only on separate calibration events, minimising high-magnitude event-macro MAE subject to tolerances on overall MAE, median absolute error, RMSE, and the worst-error tail. Evaluate false-positive/recall curves separately. The pilot uses empirical constraints; a later theorem needs exchangeability or justified stability conditions and enough independent tail events.
5. **Test independent evidence rather than repeated votes.** If adding stations, combine their evidence with a prior only once, and account for correlation. Under conditional independence a likelihood combination is proportional to pi(M) times the product of station posterior/prior ratios; naive multiplication of posteriors repeatedly counts the prior. Independence is doubtful for nearby stations, so learn/validate pooling or compare TEAM-LM attention. Five alpha probes of one station cannot serve as independent votes.

The potential contribution is the *specific calibrated correction mechanism, its conditions, and demonstrated cross-backbone generalisation*. “CRPS + a prior + a gate” without an ablation explaining why it works would remain an incremental combination. If five probes match the full posterior, a separate, narrower compression claim is possible; if they lose useful tail information, retain the full posterior.

## Evaluation required for a strong paper

- Define two tails separately: high true magnitude and the worst absolute-error quantile. Report both improvements; the September report shows these can move in opposite directions.
- Use event IDs for all splits and confidence intervals. Report station-record micro averages and equal-event macro averages. Hundreds of recordings from one earthquake do not create hundreds of independent large events.
- Preserve the existing chronological split as a diagnostic, but obtain an external benchmark with enough M>=5/M>=6 events. INSTANCE alone in its present split cannot test a great-earthquake claim. [INSTANCE dataset documentation](https://github.com/INGV/instance/blob/main/README.md) describes the records and instrument units; [the dataset paper](https://doi.org/10.5194/essd-13-5509-2021) supplies its scientific context.
- Keep a final event/sequence/region holdout untouched. The existing validation set has already selected backbone checkpoints, priors, and numerous corrections. New readout cross-fitting cannot remove that historical reuse.
- Fix 1, 3, and 5 seconds relative to P arrival at one station for the single-station benchmark. For networks, use a common clock from the first detected arrival, with only causal station data. Add a second evaluation with predicted picks, timing jitter, telemetry/inference delay, clipping, and missing stations.
- Report MAE, MedAE, RMSE, signed bias, M4/M5/M6 errors and unique event counts, severe underprediction frequency, CVaR95 absolute error, CRPS, tail CRPS, interval coverage/width, and exceedance calibration. A magnitude-threshold “false alert” here is not a full ground-shaking alert metric.
- Compare raw mean/median; constant-shift and high-quantile controls; prior removal/logit adjustment; weighted Huber; LDS; Balanced MSE; the old five-probe forest; full-posterior forest; a proper-score head; and the same method on at least two backbones. Compare at matched false-alert and average-error budgets.
- Use paired event-level intervals and disclose every tested configuration. M>=5 validation uncertainty cannot be estimated meaningfully from one distinct earthquake. Report its case study, not a generalisation interval.

## Ordered experiment programme

| Stage | Question | Completion criterion |
|---|---|---|
| A0 — executed | Are source IDs, durations, caches, and checkpoint identities credible? | Disjoint event IDs; complete target agreement; explicit 100/300/500 lengths; sampled waveform identity; checkpoint hashes. |
| A1 — executed | Does full output retain useful information lost by five means? | Same event folds, same forest capacity, separate calibration events; all trade-offs saved, including failures. |
| A2 — frozen-head pilot executed; end-to-end pending | Does a proper tail score help without inflating probabilities? | Matched seeds/backbone/data: CE, current weighted-Huber+CE, CRPS, CRPS+tail-CRPS. Calibrate on held-out events. |
| A3 | Is improvement from better evidence or changed decisions? | Full posterior versus probes versus waveform/geometry features; exceedance ranking and probability scores alongside point errors. |
| A4 | Does it transfer to truly large events? | External region and magnitude support, common causal timing, consistent scale, no test tuning. |
| A5 | Is there a general method contribution? | Multiple backbones/datasets, mechanism ablations, uncertainty, latency, released reproducible code. |

The bounded A2 pilot used 180,562 training recordings from all 47,273 training events, at most four stations per event, a frozen encoder, and five fixed final-layer epochs per objective. It improved overall and probability scores but worsened M>=4 error. A1 similarly did not achieve the joint objective: stronger tail decisions increased false positives, while selected five-second corrections improved bulk error slightly and worsened tail error. See `experiment_results.md` for all measured values. These are negative results for these configurations, not a rejection of end-to-end proper scoring or all distributional models.

Additional GPU memory cannot create missing large-event labels or correct an invalid evaluation window. The current evidence supports prioritising benchmark support and a causal feature ablation before a large architecture search.

## Concrete next candidate and falsification test

A small, testable modification is an **evidence-gated distribution residual**, with the existing CNN as a frozen starting point. Let z contain causal amplitude-growth, spectral, clipping/SNR features and learned waveform features, and s contain the five prior-response summaries. Form

    q_phi(k|x,z) = softmax(log p_theta(k|x) + r_phi(k,z,s)).

Initialise the residual at zero. Fit it on training events with a proper CDF score and a controlled regularisation term towards the original distribution; compare an identical residual using probabilities alone and one using additional causal waveform features. Event balancing changes the target population, so include both recording-weighted and event-weighted arms rather than attributing a difference to the score alone. Explicit prior adjustment is a separate ablation, not automatically added to this formula.

Keep q as the forecast distribution. Separately define a gated decision family

    a_kappa(x) = a_0(x) + kappa * g_phi(z,s) * max(0, Q_tau(q_phi)-a_0(x)),
    0 <= g_phi <= 1, 0 <= kappa <= 1.

Fit g and a small fixed quantile grid on training events. Choose kappa on distinct calibration events using predeclared MAE, MedAE, RMSE, worst-error and false-positive budgets. Always include kappa=0. This is a concrete candidate, not a new-theorem or priority claim: residual calibration, quantile decisions and gating each have prior art. Its possible contribution is a reproducible mechanism that uses early evidence to distinguish genuine large-event underestimation from broad small-event uncertainty, and demonstrates a better constrained frontier across models.

**Falsify it** if additional waveform features do not improve rare-event ranking or proper scores, if gains disappear at matched false-positive rates, if the unchanged baseline is always selected, or if held-out high-magnitude events lose the gain. Freeze the full candidate family before final testing. A finite calibration search does not guarantee population non-inferiority, particularly with only 13 validation tail events. Do not call the candidate foundational until mechanism and transfer experiments support that claim.

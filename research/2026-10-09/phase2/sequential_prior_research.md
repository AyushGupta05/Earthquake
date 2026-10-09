# Sequential probability updates for 1, 3 and 5 second EEW

Research memo, 9 October 2026. This is a set of testable hypotheses, not a novelty certificate or an experimentally validated result. The targeted searches found direct prior art for sequential Bayesian EEW, probabilistic neural magnitude heads, entropy-based gating, future-to-past distillation and martingale forecast calibration. The promising contribution is therefore a carefully specified combination that solves an identifiable EEW failure mode, with matched experimental evidence.

## Recommended first experiment

Train a three-horizon model with **suffix-conditioned probability innovations**, ordinary supervised losses at every horizon, and an optional **ordinal forecast-revision constraint**. Test a later-to-earlier distributional teacher as a separate component. At inference, the 1-second output receives exactly 100 samples, 3 seconds receives 300, and 5 seconds receives 500; no later feature or normalization statistic can enter an earlier head.

Use a modest causal CNN or the existing CNN initially. A larger transformer should come after establishing that the proposed update rule helps. Compare every variant to equally trained direct prefix heads, a shared encoder with three independent heads, simple temporal probability stacking, and the existing checkpoints. Improving an old checkpoint alone is insufficient to establish a method contribution.

## What is already known

| Closest primary source | Verified overlap and implication |
|---|---|
| [An Earthquake Early Warning Method Based on Bayesian Inference, 2022](https://www.mdpi.com/2076-3417/12/24/12849) | The indexed primary article explicitly makes the previous posterior the next prior in equation 13. This exact general idea is already published. The direct page subsequently failed to fetch; the equation and surrounding text were available in the publisher search result. |
| [Multi-events EEW using a Bayesian approach, 2015](https://academic.oup.com/gji/article/200/2/791/610068) | Sequential proposals using the previous posterior and probabilistic dependencies between waveform features and event parameters are already discussed. Direct full-page retrieval failed this session; the primary indexed text was readable. |
| [TEAM-LM, 2021](https://academic.oup.com/gji/article/226/2/1086/6223459), [official implementation](https://github.com/yetinam/TEAM) | Probabilistic magnitude from streaming waveforms and flexible stations already exists. The implementation exposes a five-component magnitude mixture, high-magnitude resampling and station masking. Preserve the amplitude information and enforce causal station/data availability when borrowing its design. |
| [Zhang et al., real-time deep EEW, 2021](https://arxiv.org/abs/2006.01332) | A fully convolutional system refines magnitude and location as continuous data arrive. Merely producing an evolving magnitude is insufficient novelty. |
| [Discriminative Bayesian filtering, 2018](https://arxiv.org/abs/1807.06173) | Discriminative state-given-observation models can be converted into Bayesian measurement updates. A discriminative probability output is not automatically a likelihood. |
| [Recurrent networks and universal approximation of Bayesian filters, 2023](https://proceedings.mlr.press/v206/bishop23a.html) | Neural/recurrent approximation of Bayesian filtering is established in general. A recurrent classifier called a Bayesian filter needs stronger justification. |
| [Progressive Knowledge Distillation for Early Action Recognition, ICIP 2021](https://www3.cs.stonybrook.edu/~minhhoai/papers/distill4earlyRec_ICIP21.pdf) | Explicitly distils later predictions into earlier predictions, including KL(S_later || S_earlier). Full primary PDF read. Using a 5-second teacher for a 1-second student is a useful baseline, not a new general learning principle. |
| [BranchyNet, 2016](https://www.eecs.harvard.edu/~htk/publication/2016-icpr-teerapittayanon-mcdanel-kung.pdf) | Uses entropy thresholds for early exits. Entropy-based confidence gating has a long history outside EEW. |
| [Calibrated Probability Forecast Sequences and Measure-Valued Martingales, June 2026](https://arxiv.org/abs/2606.31621), [full text](https://arxiv.org/html/2606.31621v1) | Develops calibration for repeated forecasts of one eventual observation and characterizes it through a martingale property, with statistical tests. This is especially close mathematical prior art for temporal probability coherence. It is a preprint. |
| [Reverse-martingale RNNs for precipitation warning, July 2026](https://arxiv.org/abs/2607.00331) | Applies backward hidden-state coherence to a different environmental warning task. Do not claim that a temporal coherence regularizer is itself unprecedented. Abstract read; not a validation of our proposed EEW loss. |
| [Kernel conditional moment tests, UAI 2020](https://proceedings.mlr.press/v124/muandet20a/muandet20a.pdf), [kernel maximum moment loss](https://arxiv.org/abs/2010.07684) | Conditional moment restrictions, their kernel representation, and U/V-statistic losses are established. They offer tools for a principled revision penalty. |
| [Conformal Risk Control, ICLR 2024](https://research.google/pubs/conformal-risk-control/) | Controls expected monotone losses under its assumptions. It does not automatically guarantee simultaneous improvement of mean absolute error, median error, tail error and false-alarm rate under earthquake sequence shift. |
| [A probabilistic view on rupture predictability, 2022](https://arxiv.org/abs/2203.08622) | The authors distinguish uncertainty about eventual size from point prediction and report important limits on early size differentiation in their studied data. This does not prove that every local 1-second waveform is uninformative; it argues against pretending that future rupture evolution is already known. |

## Mechanism A: conditional probability innovations

Let X_s be the observed prefix and U_(s,t) the newly arrived, non-overlapping suffix. For magnitude bin k, exact probability obeys

```
p_t(k) ∝ p_s(k) p(U_(s,t) | M=k, X_s).
```

An implementable discriminative update is

```
h_s = encoder(X_s)
u_t = suffix_encoder(U_(s,t))
r_t = MLP(h_s, u_t, log(q_s + eps), causal_quality_features)
g_t = sigmoid(gate(h_s, u_t, uncertainty_and_quality_features))
q_t = softmax(log(q_s + eps) + g_t * r_t)
```

Center r_t across bins for numerical identifiability. Zero-initialize the last residual layer. A quality gate is optional: test an ungated update first. Features can include early/late RMS and peak amplitude, suffix-to-prefix energy ratio, spectral shape, predictive entropy, and divergence between a direct current-prefix head and the preceding posterior. Features need only information available at t. Catalogue distance, source location, final-event duration and full-record amplitude are forbidden inference inputs unless a separate real-time estimator supplies them with its uncertainty.

This is a learned discriminative correction. Calling exp(r_t) a physical likelihood requires evidence or a separately identified generative model. The update can represent a corrected full posterior without assuming that adjacent waveform segments are independent. Conditioning on the prior prefix is important because the event, path, station and instrument produce strongly dependent segments.

**Double-counting control:** multiplying q_1(M | X_1) and q_3(M | X_3), even after dividing by a common prior once, repeats X_1 because X_3 contains it. For ideal nested posteriors, q_3/q_1 is already the relative innovation; multiplying q_1 by that ratio simply gives q_3. Any claimed benefit must arise from learning/correcting approximation errors or incorporating genuinely additional information. Likewise, five prior probes from the same distribution are not five independent observations.

**Decisive ablations:** full prefix versus suffix conditioning; prior probability versus shuffled probability input; constant versus learned gate; entropy alone versus entropy plus waveform quality; identical direct head without residual update. Add an explicit no-new-data mask that gives an identity update. Test a repeated segment and a contradictory high-energy suffix: the model must be able to revise a confidently wrong low-magnitude early result.

**Novelty assessment:** generic posterior recursion is established. A demonstrated suffix-conditioned correction that separates probability from alert cost and substantially improves high-magnitude error without damaging central error could be an EEW contribution. The exact architecture is a hypothesis, not yet shown to be unprecedented.

## Mechanism B: ordinal innovations with conditional-zero-drift checks

For cutoff a_j, define F_t(a_j) = sum_(k≤j) q_t(k), and Δ_(s,t,j) = F_t(a_j) - F_s(a_j). Under the correct conditional distribution,

```
E[Δ_(s,t,j) | X_s] = 0.
```

This follows immediately from iterated conditional expectation. It is a standard probability identity, not a new theorem. A particular record can undergo a large positive or negative revision. Entropy can increase on a surprising observation. Enforcing F_t≈F_s record by record, decreasing entropy on every record, or monotonically increasing predicted magnitude would suppress legitimate learning.

Proposed EEW implementation: construct bounded early-only features φ(X_s), including a constant and a small frozen projection of early embeddings; penalize conditional revision moments at magnitude cutoffs. Jointly train the early and late heads with label supervision, rather than forcing all later probabilities to inherit a frozen early model's bias. The cutoff weighting can emphasize M4/M5 while retaining positive weights throughout the support.

```
v_i = vectorize(sqrt(w_j) * Δ_(i,j) * φ(X_(i,s)))
L_revision = (||sum_i v_i||² - sum_i ||v_i||²) / [B(B-1)]
L_total = sum_t [CE(q_t, y) + η * ordinal_CRPS(q_t, y)]
          + λ_revision * L_revision
```

The displayed off-diagonal estimator assumes independent event-level examples. Sampling one station per event per batch is the simplest pilot. Multiple stations from one event must not be treated as independent pairs in that formula. Equal-event sampling and ordinary record sampling target different probability populations; use the same population consistently for supervision, revision moments and evaluation. A record-level full-data experiment can instead exclude within-event pairs and document its weighting.

The ordinary squared minibatch mean also penalizes variance of legitimate innovations, by an O(1/B) term. The off-diagonal form removes that finite-batch term in expectation. It can be negative in a batch; that is expected for an unbiased statistic. Use bounded features and a small coefficient, compare λ=0, and monitor ordinary proper scores. This is a proposed application of existing conditional-moment machinery, not a claim to invent U-statistics.

A low-cost alternative is to begin with **diagnostics only**: regress held-out Δ on early entropy, tail mass, amplitude, magnitude estimate and latent features; report predictable revision drift. A regularizer is useful only if it improves held-out scores beyond a matched model, not merely because the diagnostic shrinks. Separate unconditional probability calibration from temporal coherence; a constant wrong distribution can have zero revisions.

**Candidate contribution:** a tail-aware, event-correct conditional innovation model with empirical tests showing that it avoids early-probability lock-in. Strong nearby 2026 prior art prevents calling the underlying martingale idea novel. Evidence would need repeat seeds, external events, and equal-compute ablations.

## Mechanism C: later-to-earlier CDF distillation

The direct 1-second head has no earlier model to update. Train it with a 3/5-second teacher during training only. Distil a probability distribution, not a later point estimate:

```
L_teacher = sum_(s<t) sum_j w_j [F_student,s(a_j) - stopgrad(F_teacher,t(a_j))]²
L_student = sum_s S_w(F_student,s, y) + λ_teacher L_teacher
S_w(F,y) = sum_j w_j [F(a_j) - 1{y≤a_j}]² Δa_j
```

Choose fixed positive cutoff weights, for example 1 + 2*1{a_j≥4}, not a label-dependent sample multiplier presented as if it preserved the ordinary posterior. Keep the supervised term. Compare with conventional forward-KL teacher distillation and with no teacher. Start with a calibrated teacher and λ∈{0.1, 0.3}; an inaccurate teacher can transmit its bias. Fixed-temperature softening is an empirical variant, not a guarantee of calibration.

Why this is sensible despite future information being absent at test time: if the future teacher were the true F_t, squared CDF regression onto X_s would have conditional mean E[F_t|X_s]=F_s as its population optimum. It can train an early uncertainty estimate without requiring the early model to know the realized future. This argument fails if one replaces the objective with hard high-magnitude pseudo-labels or selectively keeps only confident future teachers without accounting for the selection.

**Novelty assessment:** progressive future-to-past distillation is explicitly published in computer vision. Ordinal, tail-weighted distillation coupled to an audited sequential EEW model may be useful, but adding it alone is unlikely to justify a foundational general-method claim. It should be a comparison and possibly one component of the complete method.

## Concrete pilot matrix and acceptance criteria

1. Direct 1/3/5-second heads, equal training budget and causal inputs.
2. Shared encoder, direct heads, no sequential probability input.
3. Conditional innovation heads with proper losses.
4. Variant 3 with waveform-quality gate.
5. Variant 3 with revision penalty; then, only if helpful, combine gate and penalty.
6. Best sequential candidate with early CDF distillation; conventional KL distillation as the matched control.

Select on a training-internal event-disjoint development set, not repeatedly on the old validation set used to choose checkpoint epochs. Do not tune a new method on the same 13 high-magnitude validation events until it looks successful and then call that verification. Repeated stations from one event provide useful waveform diversity, not independent evidence of performance across large earthquakes.

Predeclare micro and event-macro MAE, MedAE, RMSE, M≥4 and M≥5 event-macro error, signed underestimation, CRPS, tail CRPS, Brier scores, false M4 alarms, and worst-5% absolute error. Report event-cluster confidence intervals and all tested seeds. For a first pilot, require tail improvement at all requested horizons with micro MAE and MedAE no worse by more than a small declared tolerance; follow up with stricter and external evaluation. Failing one horizon should be reported, not averaged away.

The existing held-out data cannot demonstrate M6+ performance because it has no such events. A paper-to-paper scalar MAE comparison across different regions, magnitude populations, time origins and station availability is not a superiority test. Reproduce at least one published architecture on the same data, or evaluate both models on its official split. Literature numbers such as A2MAG's 3-second result are context until that comparison is matched. Establish the useful result first; then audit the precise claimed mechanism against the closest literature and narrow the novelty claim accordingly.

## Follow-up: event consensus, privileged station information and a modified objective

### Nested teachers are different from leave-one-station-out consensus

Let A be the student's own observed prefix and Z be peer-station/later-waveform information. A nested ideal teacher T(a)=P(Y≤a | A,Z) satisfies

```
E[T(a) | A] = P(Y≤a | A).
```

Therefore squared CDF distillation and forward teacher-to-student cross-entropy have the correct population target under ideal teacher probabilities. Peers may be correlated; this identity requires nesting, not conditional independence of stations. Using later data in a training-only teacher is privileged learning, provided no teacher features or probabilities enter the deployed early student. Event-disjoint cross-fitting is necessary to stop a teacher from merely memorizing the labelled training event.

If the teacher excludes A, T_minus(a)=P(Y≤a | Z), this equality generally fails. An exact binary counterexample: Y is equiprobable, A=Y is perfect, and Z is an 80%-accurate independent noisy measurement conditional on Y. The peer teacher gives 0.8 or 0.2. Conditional on A=1, its average is 0.8²+0.2²=0.68, whereas P(Y=1|A=1)=1. Training toward that teacher shrinks a correct prediction. Conditional independence given Y does not repair it.

Concrete construction: for each target station and horizon, randomly draw several peer subsets; every teacher input contains the target station's own prefix, along with the selected privileged peers and optionally its later waveform. Use a permutation-invariant, supervised event teacher, and average its CDFs. Random subset selection should be independent of the label conditional on the student's inputs. Do not average individual-station posteriors and call that the joint posterior. Do not multiply them under a false independence assumption.

If subset teachers are each ideal for nested information, an arithmetic average preserves the conditional expectation. Weights depending only on A also preserve it. Weights depending on future entropy, observed teacher correctness, or peer consensus generally do not. Label-based teacher filtering can still be an empirical objective, but it loses this probability-preservation argument.

The general setting is already covered by [generalized distillation/LUPI](https://arxiv.org/abs/1511.03643). Multi-view/single-view mutual probability distillation appears in [Black et al., WACV 2024](https://openaccess.thecvf.com/content/WACV2024/papers/Black_Multi-View_Classification_Using_Hybrid_Fusion_and_Mutual_Distillation_WACV_2024_paper.pdf), although their inference target is multi-view. The targeted search found no direct EEW paper establishing the particular nested event-teacher construction above. Absence from the search is not proof of novelty.

### Proposal D: learn how much uncertainty the next waveform segment can resolve

The more distinctive hypothesis is to modify the objective so that an early network learns **both its current magnitude distribution and the expected resolution supplied by later/peer observations**. Predictive entropy alone cannot distinguish uncertainty that the next segment should resolve from uncertainty likely to persist.

For cutoff a and a nested ideal teacher T=P(Y≤a|A,Z), set F=P(Y≤a|A). The conditional variance decomposition gives

```
R(a,A) = E[(T-F)² | A]          # uncertainty resolved by privileged information
U(a,A) = E[T(1-T) | A]          # uncertainty remaining after that information
R(a,A) + U(a,A) = F(1-F).
```

This decomposition is a standard consequence of conditional variance, not a new theorem. But it identifies a concrete target that ordinary entropy-gated EEW ignores. At F=0.5, a teacher that always remains at 0.5 has R=0; a teacher that later resolves the event to 0 or 1 has R=0.25. The student's current entropy is identical in both cases. These exact examples and the non-nested counterexample were checked with a local Python calculation.

Implement a small resolution head from the same early representation:

```
F_t = cumulative_sum(softmax(logits_t))
R_hat_t = stopgrad(F_t*(1-F_t)) * sigmoid(resolution_logits_t)
L_R = mean_j w_j * (R_hat_tj - stopgrad((T_j-F_tj)²))²
L = L_supervised_ordinal + λ_CDF * ||F_t-stopgrad(T)||²_w + λ_R * L_R
```

Keep the mean-head scale detached in L_R so it cannot directly reduce the auxiliary loss by manipulating the current distribution. Gradients through shared early features remain an empirical representation-learning intervention. Train at pairs 1→3, 1→5 and 3→5, with a distinct conditioning variable describing the future horizon and available teacher-station subset. Give the 5-second output a multi-station teacher or a longer training-only teacher only if that experiment is explicitly specified. No future teacher is required at inference.

Start with λ_R=0 versus a small fixed value and test whether the same-size head without the resolution loss changes performance. Measure resolution-head calibration on event-held-out examples as well as magnitude error. The method may improve representation and tail handling; there is no theorem that it improves MAE. If the teacher is miscalibrated, R is partly teacher error. Estimate that error using independent events rather than treating all teacher disagreement as physical uncertainty. A teacher learned only from the same few large events cannot manufacture independent tail evidence.

A richer version outputs a small distribution over possible later CDFs and learns it with an energy score, while constraining their mean to the current magnitude distribution and retaining current-label supervision. That avoids reducing all possible later outcomes to one confident target. [Ensemble Distribution Distillation](https://arxiv.org/abs/1905.00076) already transfers distributions of model predictions, and its [regression/classification generalization](https://arxiv.org/abs/2002.11531) preserves uncertainty decomposition. The proposed distinction is to model the variability caused by information that has not arrived, rather than model-parameter ensemble diversity. That distinction must be reflected in the teacher construction, loss, evaluation and claim—not only the terminology.

This provides an RVLoss-like contribution candidate at the level of a modified objective: identify a specific failure of entropy as a training signal; derive a resolvable-uncertainty target; add a cheap objective to multiple existing backbones; demonstrate that the added term improves the tail/ordinary-error frontier across 1/3/5 seconds. It remains a hypothesis until those tests succeed.

### Ordinal transport caution

Earth-mover/Wasserstein distillation is not new: [OrdPrune-KD, 2026](https://www.mdpi.com/1424-8220/26/12/3636) explicitly uses absolute CDF differences for ordinal teacher transfer. Generic learned prior-to-posterior transport is also established in [Particle Flow Bayes' Rule](https://arxiv.org/abs/1902.00640).

For early uncertainty, replacing squared CDF loss with absolute CDF distance changes the population target. If a future teacher perfectly resolves a binary outcome whose early probability is 0.2, minimizing expected absolute CDF error chooses 0; minimizing expected squared CDF error chooses 0.2. A naive Wasserstein-1 teacher loss can therefore sharpen away rare-event probability even with a perfect nested teacher. This is a mathematical objective mismatch, not a numerical implementation bug. Use squared CDF scoring when the claim is calibrated early probability, and test transport losses as separate empirical alternatives.

Representing temporal revisions as mass flow between neighbouring magnitude bins could be a useful architecture, but magnitude itself is static: the transported object is belief, not physical magnitude growth. Bidirectional updates and long jumps must remain possible. A new name for this transport would not establish a new inference principle.

## Follow-up: INSTANCE features and instrument response

The [official INGV README](https://github.com/INGV/instance/blob/main/README.md) links a roughly 15 MB [StationXML response inventory](http://repo.pi.ingv.it/instance/responses.tgz). Its physical-unit data use velocity for HH/EH and acceleration for HN. Inventory download was not performed in this research subtask.

The [INSTANCE paper, sections 2.1.5–2.2](https://essd.copernicus.org/articles/13/5509/2021/) documents these critical facts: counts traces were mean/linear-detrended over 120-second records and resampled; ground-motion traces additionally underwent frequency-domain response correction with end tapers; stored SNR uses a five-second post-S window (or predicted S from hypocentral distance); PGA/PGV and spectral measures derive from processed records. Static station metadata include network, station, location/channel, coordinates, elevation and Vs30. Thus stored SNR, waveform summary statistics, path distance and catalogue source parameters should not be deployed as early inputs. Whole-trace preprocessing can contaminate an otherwise correctly cropped prefix.

Suggested implementation map (recommendations, not a claim that preprocessing is already causal):

| Input | Treatment |
|---|---|
| Instrument response | Resolve network.station.location.channel and the observation epoch, not station name alone. Record missing or ambiguous matches. |
| Sensitivity and units | Use inventory sensitivity with its frequency and native input units; do not treat all count amplitudes as directly comparable. |
| HH/EH/HN type | Include a type indicator and use separate native-unit amplitude branches or a validated common-unit correction. |
| Station coordinates/elevation/Vs30 | Available before the event, but audit held-out station/region generalization to expose geographic shortcuts. |
| Prefix amplitude features | Recompute peak/RMS/energy and spectral bands from only data available by the deadline. Preserve an amplitude branch alongside normalized waveform shape. |
| SNR | Compute a new causal ratio using pre-P noise and the current observed prefix; never reuse post-S metadata SNR. |
| Catalogue P pick | Useful for a controlled post-P benchmark; an operational pipeline must include picker error and latency. |

[USGS gmprocess](https://ghsc.code-pages.usgs.gov/esi/groundmotion-processing/contents/manual/instrument_response.html) states that sensitivity-only conversion is generally acceptable for flat-response accelerometers, whereas seismometers need response treatment; its workflow also checks sensitivity and units consistency. A sensitivity-normalized HH/EH experiment is an approximation and must be labelled accordingly. [ObsPy removal of sensitivity](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.remove_sensitivity.html) is distinct from [full response deconvolution](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.remove_response.html), whose default processing includes mean removal and tapering. Applying an FFT inverse to a prefix does not use future samples, but edge effects and lack of streaming equivalence still need checking.

For strict real-time verification, compare the winning model on a subset re-extracted from original continuous miniSEED using causal detrending/filter state and appropriately initialized response processing. For a cheap current-data ablation, remove a prefix-estimated trend again: a linear projection fitted on the prefix cancels a previously removed global linear trend algebraically, aside from finite precision. It does not undo nonlocal resampling or frequency-domain response leakage. An invariance test should replace all samples after the forecast deadline before preprocessing and confirm the prediction is unchanged. Avoid downloading the 156 GB ground-motion dataset merely to claim physical causality from a crop.

## Follow-up: closest prior art for the resolution head (9 October 2026)

**Novelty assessment revised downward:** predicting how much future information will reduce uncertainty, training a neural value head for this quantity, sharing its backbone with a predictor, and bounding it by current uncertainty are already established. The strongest verified match is DIME. A useful EEW contribution remains possible, but it must be positioned as a concrete modification and validated against this precedent.

| Primary source | Verified proximity and implication |
|---|---|
| [Gadgil, Covert & Lee, *Estimating Conditional Mutual Information for Dynamic Feature Selection*, ICLR 2024](https://arxiv.org/html/2306.03301v3) | DIME trains a value network on observed prediction-loss improvement. Appendix A.3 derives the regression optimum as Var(E[Y\|observed,new]\|observed). Appendix C uses shared predictor/value backbones and sigmoid times current entropy to bound the output. These directly anticipate the general resolution-head idea. |
| [Covert et al., *Learning to Maximize Mutual Information for Dynamic Feature Selection*, ICML 2023](https://proceedings.mlr.press/v202/covert23a.html) | Amortized selection policies minimize next-observation prediction loss; its regression formulation minimizes expected remaining conditional variance. |
| [Ma et al., EDDI, ICML 2019](https://proceedings.mlr.press/v97/ma19c.html) | A partial VAE supports expected-information-gain acquisition. This establishes the broader value-of-unobserved-information framing; our discriminative targets would avoid generating missing waveforms. |
| [Achenchabe et al., *Early Classification of Time Series: Cost-based Optimization Criterion and Algorithms*, 2020 preprint](https://arxiv.org/abs/2005.09945) | Anticipates future prediction benefit against the cost of delaying a decision. Adaptive waiting is a mature problem, not a new EEW principle. |
| [Manca, Kunze & Fay, *Predicting Uncertainty Reduction in Online Alarm Flood Classification*, IFAC-PapersOnLine 59(25), 119–124, 2025](https://doi.org/10.1016/j.ifacol.2025.11.935) | Directly relevant title and task: predicting future resolution of class ambiguity. Publication details verified at the [authors' university bibliography](https://bibliographie.ub.rub.de/work/461459); the publisher full text was inaccessible in this session. Do not claim detailed architectural equivalence without obtaining that text. |
| [Allen, Ferro & Kwasniok, *A conditional decomposition of proper scores*, 2023](https://rmets.onlinelibrary.wiley.com/doi/10.1002/qj.4478) | Conditional reliability/resolution decomposition of proper scores is established. It helps diagnose whether apparent information gain instead reflects correction of a biased forecast. |

The earlier sources on progressive future-window distillation, ensemble distribution distillation, and calibrated probability forecast martingales remain relevant. A search of EEW terms with future-posterior, information-gain and distillation terminology did not locate a directly matching threshold-wise revision-energy training objective. That is a search result, not proof of priority. Earthquake catalogue forecasting papers about the magnitude of the next event address a different task from estimating the magnitude of an event already underway.

### What the target actually measures

The following identities are derived here to audit the proposal; the probability identities themselves are standard. Let A be early information and G=(A,Z) nested later information. At cutoff a, let B=1[Y≤a], F=E[B|A] and T=E[B|G]. Then

```
R(A) = E[(T−F)^2 | A]
     = F(1−F) − E[T(1−T) | A]
     = E[(F−B)^2 − (T−B)^2 | A].
```

Thus threshold resolution is the expected value of later information under Brier loss. Summing with fixed nonnegative cutoff weights gives the expected reduction in the corresponding ranked probability score / discretized CRPS. It is not automatically the expected reduction in MAE or the magnitude median's error. Its value depends on the chosen future horizon and sensor set.

For arbitrary trained early prediction f, even if T is a good later forecast, the learned squared target instead satisfies

```
mu(A) = E[T | A]
E[(T−f)^2 | A] = Var(T | A) + (mu(A)−f)^2.
```

This combines future-observation variability and predictable forecast drift. Until drift is small on held-out events, use the name **predicted revision energy**, not a pure resolvable-uncertainty estimate. This also corrects the earlier proposed cap: f(1−f) is an ideal-posterior bound, not a valid bound for an arbitrary trained f. For f=.01 and T=.9, the target is .7921 while f(1−f)=.0099. A capped head can therefore be incapable of representing exactly the confident rare-event failures we want to study. Start with sigmoid in [0,1] or a nonnegative head; compare the tighter cap separately after calibration. Alternatively learn mu and a bounded conditional variance v≤mu(1−mu), with energy v+(mu−f)^2.

Do not reduce the current predictive variance by subtracting R: the future observation has not arrived. Do not infer the sign of a magnitude correction from R: squared revision loses that sign. Both operations would confuse the value of future data with data already available.

### A precise modification worth testing: teacher-conditioned ordinal gain targets

DIME's observed-loss target suggests the matched comparison. Define, at each cutoff,

```
D = (f−B)^2 − (T−B)^2                     # observed Brier gain
Z = (T−f)^2                               # teacher revision target
L_value = mean_j w_j (r_j(A)−stopgrad(target_j))^2.
```

If T is the true nested later posterior, conditioning on G yields

```
E[D | G] = (T−f)^2 = Z.
```

Consequently Z is a Rao–Blackwellized version of D: it has the same conditional mean given A and no greater conditional target variance. This holds for any A-measurable f, though interpreting that mean as pure information resolution additionally requires f=F. Z is also nonnegative, whereas individual observed gains D can be negative. The potentially useful modification is to train the early representation with these threshold-wise teacher-conditioned targets for multiple horizons, alongside supervised ordinal scoring and optional CDF distillation. Neither the variance-reduction identity nor using CDFs alone is new theory.

With an imperfect later teacher T and true later probability p=E[B|G], the targets no longer agree:

```
Z − E[D | G] = 2 (T−f)(T−p).
```

Teacher miscalibration can therefore trade lower target noise for bias. Cross-fit teachers by event, calibrate using held-out training events, and test both targets. The strongest experiment is exactly this bias–variance tradeoff rather than a generic claim of better uncertainty.

A simple analytical check: an early probability F=.3 followed by equally probable later probabilities T=.1 or .5 has R=.04. The squared-revision target is always .04, while the observed Brier-gain target has conditional variance .0272. Both have mean .04. This is an illustrative calculation, not evidence of improvement on earthquake data.

### Optional multi-horizon consistency extension

For ideal nested forecasts at 1, 3 and 5 seconds, the two innovations are conditionally orthogonal. At every cutoff,

```
R_1→5(X1) = R_1→3(X1) + E[R_3→5(X3) | X1].
```

This provides an information-budget constraint across horizons, rather than a pointwise rule that entropy must decrease. A trainable extension can regress r_1→5−r_1→3 onto a detached r_3→5 target, using early inputs only on the left. Its population target is the conditional mean, so a sample's two sides need not match exactly. Avoid backpropagating through both sides in a way that makes later variability collapse to satisfy a pointwise penalty. The identity follows ordinary martingale variance decomposition; a methodological claim would concern a stable learning objective and its measured benefit, not discovery of that identity. This extension should follow, rather than precede, evidence that the simpler head helps.

### Falsifiable fixed-horizon experiment

At a fixed 1-, 3-, or 5-second deadline, r(A) is a function of the same observations already available to the predictor. It cannot add information to a Bayes-optimal predictor. Its plausible benefit is better finite-data representation learning. Adaptive waiting or adding stations can use it as a decision value, but that does not establish a lower 1-second error.

Use the same encoder, parameter budget, teacher folds, batches and training steps for these variants:

1. Supervised magnitude/ordinal objective alone.
2. Supervised plus CDF future-teacher distillation, without a revision head loss.
3. Variant 2 plus a head trained on current uncertainty or current prediction error: auxiliary-learning control.
4. Variant 2 plus observed Brier-gain targets D: the relevant DIME-style adaptation.
5. Variant 2 plus teacher-conditioned squared revision Z: the proposed target modification.
6. Variant 5 with encoder gradients from the auxiliary head detached: diagnostic-only control. If the point gain disappears, it supports the shared-representation mechanism.

An additional shuffled-future control may shuffle teachers across events within coarse early-prediction/entropy groups; it should never shuffle across train/validation boundaries. It tests whether learning specific future predictability matters beyond a generic auxiliary target. Treat it as a negative control, not a calibration method.

Report both point performance and whether the auxiliary quantity means what is claimed: event-weighted MAE/RMSE and median error at each fixed deadline; high-magnitude bias/MAE with event counts; largest-error quantiles; ordinal score/calibration; predicted versus realized revision-energy curves; predictable drift; and observed Brier gain within resolution bins. Bootstrap whole events, not station records. Compare at least two seeds for screening, then more seeds and an independent event/region dataset for a positive candidate. Current held-out scarcity above magnitude 5 prevents a strong high-magnitude state-of-the-art claim regardless of an average numerical gain.

A defensible provisional description is: **an ordinal, future-teacher revision objective for early magnitude inference, evaluated as a modification of neural value-of-information learning**. Whether the modification constitutes a publishable method depends on a clear empirical advantage over the matched DIME target, ordinary future distillation, and proper ordinal-loss controls.

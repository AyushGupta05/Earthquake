# Prior-art challenge: future revision auxiliaries for early magnitude inference

Research audit dated 9 October 2026. This memo supplements the existing `phase2/sequential_prior_research.md`. It is an assessment of a candidate training modification, not a novelty certification or a report of earthquake accuracy gains. No TEST waveforms or predictions were used for this work.

The broad idea is already established: estimate how much later information could change a prediction, learn that quantity with a supervised head, and use privileged future observations during training. A defensible experiment remains: determine whether an ordinal, future-teacher revision auxiliary improves a matched EEW backbone more than ordinary future distillation, a current-error auxiliary, and an observed-loss-gain auxiliary. The contribution would have to be the specific training method and its reproducible benefit under a bulk-error constraint.

## The newly verified 2026 near match

Hui-Mean Foo and Yuan-chin Ivan Chang's [*Estimating the Conditional Forecast-Revision Scale in Sequential Models*](https://arxiv.org/abs/2608.03163) is a 4 August 2026 preprint. Its [full text](https://arxiv.org/html/2608.03163v1), Definition 2.1, defines conditional RMS forecast revision; §2 identifies its square with expected reduction in optimal squared prediction risk. The authors explicitly distinguish conditional, realized, and unconditional revision size.

Its §3.6 conditional-variance estimator is a fitted GARCH scale multiplied by autoregressive sensitivity, not a generic neural head. §3.7 studies a matched state-space estimator. Supplement §S1.4 fits an ordinary-least-squares probe from a 32-dimensional recurrent gate vector to the exact revision scale, with disjoint fitting/evaluation sequences. The naive averaged-gate proxy fails. Thus supervised readout of revision scale is also prior art.

Scope matters: the local-smoothing limitation concerns a specified externally tuned, lag-only estimator class. It is not an impossibility result for learned conditional models. The reported large cost advantage concerns the paper's volatility simulations. The text does not demonstrate jointly trained ordinal-CDF auxiliaries for earthquake magnitude. It leaves architectures directly exposing the scale as future work. These distinctions preserve an experimental question, not a claim to invent the underlying quantity.

Our mathematical interpretation: applying a conditional-mean revision construction to the vector of binary magnitude-threshold indicators yields a threshold-CDF/exceedance revision construction directly. This is a specialization of existing conditional-expectation mathematics. Calling it “distributional” does not create a new population identity.

## Other primary sources that constrain the claim

| Source, inspected evidence | Consequence for this project |
|---|---|
| [Gadgil, Covert and Lee, DIME, ICLR 2024](https://arxiv.org/html/2306.03301v3), §4.1 and Appendix A.3 | Trains a value network on incremental observed prediction-loss improvement. Its regression derivation gives the conditional variance of a later conditional mean. Shared predictor/value backbones are described in Appendix C. A neural “resolution head” or shared backbone is not sufficient novelty. |
| [Covert et al., ICML 2023](https://proceedings.mlr.press/v202/covert23a.html) | Learns dynamic feature acquisition by optimizing prediction after acquiring information. Our fixed-deadline magnitude objective differs from choosing another feature, but the information-value framing is established. |
| [Menon et al., *A statistical perspective on distillation*, ICML 2021](https://proceedings.mlr.press/v139/menon21a.html) | Analyzes teacher-probability supervision through variance reduction and the bias–variance consequences of imperfect teachers. “Soft teacher targets reduce noise” is not a new principle. |
| [Dao et al., *Knowledge Distillation as Semiparametric Inference*, ICLR 2021](https://arxiv.org/abs/2104.09732) | Develops cross-fitting and loss correction to mitigate teacher error. Cross-fitting or a teacher-residual correction alone cannot be the claimed contribution. |
| [SSATKD, 2025 preprint](https://arxiv.org/html/2501.01921v1), Equation 12 | Explicitly uses mean squared student–teacher CDF difference as a distillation objective. A squared CDF distance is therefore already used in distillation. Predicting the conditional size of future CDF change is a different objective, but the constituent distance is not new. |
| [Liu et al., LuPIET](https://arxiv.org/abs/2301.10887), ALTA 2022 paper, arXiv 2023 | Distills privileged longer input windows into early predictors for text time series. Later observations supervising an earlier model are established. |
| [GDPD primary repository](https://github.com/hewadehigaha/GDPD_ICLR26), linked [manuscript](https://openreview.net/pdf?id=e5tepxQfE1) | Describes a diffusion prior over complete-input teacher representations, conditioned on partial time series. It challenges any broad claim to first model the distribution of future teacher representations. Bibliographic metadata is inconsistent: the repository description says ICLR 2025, while its citation says 2026 and Anonymous. Do not assert a resolved venue/year/authorship from this page. |
| [Stephen Wu, Caltech thesis, 2014](https://thesis.caltech.edu/8243/), covering ePAD | Explicitly discusses the value of delaying EEW mitigation to obtain lower uncertainty at the next update. Adaptive waiting/value of a future EEW update is not a new application principle. |

Another close title is [Manca, Kunze and Fay, *Predicting Uncertainty Reduction in Online Alarm Flood Classification*, 2025](https://doi.org/10.1016/j.ifacol.2025.11.935). Its [university bibliography](https://bibliographie.ub.rub.de/work/461459) confirms publication details, but full-text access was unavailable. This is a remaining comparison gap; title-level proximity does not establish architectural equivalence.

## The exact distinction worth testing

The following algebra is our audit of the proposal, using standard conditional-expectation identities. Let A be information available at an early deadline and G contain A plus a later prefix. At magnitude threshold a, use the exceedance label B=1[M>a]. Let f=f(A) be the early probability, T=T(G) a fixed later teacher, and p=P(B=1|G) the true later probability. Using exceedance rather than CDF probabilities makes upward tail revisions easy to interpret; squared differences are unchanged by complementing both probabilities.

Define the two competing auxiliary targets:

```text
D = (f − B)² − (T − B)²       observed Brier improvement
Z = (T − f)²                  squared teacher revision

D − Z = 2(T − f)(B − T)
Z − E[D | G] = 2(T − f)(T − p)
```

When T=p, Z=E[D|G]. It is a Rao–Blackwellized target with the same conditional mean given A and no greater conditional variance than D. This statement permits an arbitrary A-measurable f. Interpreting that mean as pure information resolution additionally requires f=P(B=1|A).

With an imperfect teacher, lower target noise can be exchanged for teacher-dependent bias. In particular, adding the apparently new “de-biasing correction” 2(T−f)(B−T) to Z gives D exactly. It must be identified as the observed-gain endpoint, not presented as a new target under another name.

For an arbitrary teacher and early forecast:

```text
mu(A) = E[T | A]
E[Z | A] = Var(T | A) + (mu(A) − f(A))².
```

The auxiliary then predicts both future variability and predictable drift. Use the name **predicted revision energy** until held-out evidence supports the stronger uncertainty-resolution interpretation. A cap of f(1−f) is invalid for arbitrary f and T; use the valid [0,1] target range or explicitly model the drift and conditional variance separately. Never subtract predicted future resolution from today's uncertainty before the future observation arrives. Squared energy also supplies no sign for a magnitude correction.

The local `revision_energy_algebra_checks.json` records a 1,000-triplet numerical check of these identities, with maximum absolute discrepancy 2.22×10⁻¹⁶. In an ideal toy example f=.3 and equally likely T=.1/.5, E[D]=E[Z]=.04, while Var(D)=.0272 and Var(Z)=0. In a biased-teacher example f=.05, T=.2, p=.8, E[D]=.2025 but Z=.0225. These are synthetic algebra checks, not earthquake performance evidence.

## Narrow candidate variations

**Primary candidate: ordinal revision supervision with an explicit target-noise control.** Fit event-disjoint, calibrated later teachers, then train the early shared encoder on its usual supervised magnitude objective plus threshold-wise revision regression. Compare Z against D using identical teacher folds, encoder, head capacity, batches and training budget. Plain CDF distillation remains a separate control. The potential contribution is an effective training modification for scarce large-event observations, not the conditional variance identity.

A small optional shrinkage experiment uses

```text
U_rho = Z + rho * 2(T − f)(B − T),    rho in {0, .25, .5, 1}.
```

The endpoints recover Z and D exactly. Intermediate values trade teacher bias against label noise. This is a candidate implementation of a familiar statistical tradeoff, not a new general principle. Choose rho only within TRAIN-derived calibration/validation folds. Do not fit an adaptive rho on the tiny Chile DEV high-magnitude subset.

**Secondary candidate: directional revision auxiliaries at tail thresholds.** Separate Zplus=max(T−f,0)² and Zminus=max(f−T,0)² into two heads, with Zplus+Zminus=Z. For exceedance probabilities, the first describes prospective upward revisions. Its plausible role is to shape representations associated with underestimation risk. Semivariance is a standard construction; a defensible claim would concern the particular ordinal EEW objective and measured benefit. Compare against one total-energy head with matched capacity. Do not convert either positive quantity directly into an upward point-prediction shift.

Keep later horizons explicit: 1→3, 1→5 and 3→5 answer different questions. A 25-second teacher is a useful privileged-information experiment but changes the target and training resources. Report it separately from the 1/3/5-only comparison. Enforce nested observed samples and station availability. No use of future normalization statistics, station triggers or waveform values at inference is permitted.

## Controls, interpretation and acceptance

At a fixed deadline an auxiliary head is a function of the same observed input. It adds no Bayes information. A successful result would therefore support better representation learning, optimization or calibration in the finite-data regime. A head that only predicts future revisions accurately is not by itself a magnitude-accuracy improvement.

The minimum matched suite is supervised-only, supervised plus future CDF distillation, distillation plus a current-error auxiliary, distillation plus D, and distillation plus Z. For a positive Z result, detach the auxiliary head from the encoder as a mechanism control. A teacher shuffle confined to TRAIN is an additional negative control. All runs need matched backbone, available information and selection budget; a larger teacher can otherwise confound the proposed objective with privileged compute.

Fix whether f is a frozen early reference or a detached current student. A frozen cross-fitted reference yields stationary targets; a current student yields changing targets as its predictions improve. Either can be studied, but D and Z controls must use the same convention. If teacher ensembles are used, distinguish variation across fitted teachers from revision due to later observations.

TEAM's magnitude oversampling changes the effective training distribution. The teacher calibration, target interpretation and validation event weights must refer to a declared distribution. Otherwise an apparent revision effect can simply reflect prior mismatch. Any importance weighting or prior correction should be documented as a separate known component.

Before unlocking TEST, declare the event-weighted mean absolute error and median absolute-error non-inferiority tolerances at each of 1, 3 and 5 seconds, plus the high-magnitude primary threshold and upper-error-tail metrics. “Constant” must have a numerical tolerance and uncertainty assessment. Compare paired event errors and report the uncertainty in the bulk-error difference as well as in the tail gain. For correlated earthquake sequences, add sequence/time-block sensitivity to an event bootstrap. Lower ordinal score does not logically guarantee lower median-estimator MAE.

The verified Chile chronological TRAIN/DEV/TEST counts at MA≥5.5 are 22/1/30; at MA≥6 they are 12/0/12; at MA≥7 they are 1/0/3. DEV cannot support reliable high-magnitude architecture tuning. Use TRAIN-only folds for selection with the scarcity stated explicitly, keep TEST sealed until a protocol is frozen, and avoid treating the three M≥7 test events as evidence of a general large-earthquake superiority claim. A second event/region benchmark is needed for a broad conclusion.

## Positioning and remaining search limits

An accurate provisional description is: **a future-teacher ordinal revision auxiliary for early magnitude estimation, tested against neural observed-information-gain supervision and ordinary future distillation under a bulk-error constraint**.

The focused search covered conditional forecast revision, neural value of information, early time-series prediction, future/privileged distillation, CDF distillation and EEW decision delay. Primary sources were used for substantive claims. No exact published EEW implementation of this combined objective was located in the inspected sources; that is a bounded search result, not proof of priority. The 2026 CFRS paper, DIME and existing distillation theory materially narrow the claim. A foundational-paper claim should wait for matched external results, repeated seeds, calibration checks, mechanistic ablations and independent-domain validation.

# What imbalance training remains untested

Read-only audit, 9 October 2026. Repository snapshot `9671730b80cf9473daef2772f10ebf021d89f8cc`; exact source hashes, notebook-source searches and 41 local phase-2 run summaries are in `source_inventory.json`. No recording arrays were loaded and no model was fitted for this audit. Absence below means no matching implementation/completed run was found in this snapshot, not proof about unavailable experiments.

**Recommendation:** test end-to-end magnitude-balanced exposure with explicit recovery of the natural-population distribution. Use a fresh same-input waveform backbone and the new TRAIN event/station partition. This is a missing established baseline, not a novel loss. The earlier negative readout experiments do not settle it.

## What the project has actually tried

| Method | Evidence and what was trained | What remains open |
|---|---|---|
| LDS | Supplied September report, pp.6/22: Gaussian-smoothed training-label density, inverse powers .5/1, fitted histogram-gradient-boosting readouts of saved 1 s predictions. Density fit within each outer training fold. | End-to-end LDS waveform representation learning. |
| Balanced MSE | Same report, pp.7/22–23: empirical-prior bin integration and an additive spline on saved prediction features; fixed noise scales .35/.7. This is a genuine trained Balanced-MSE readout, not merely a prediction shift. | End-to-end waveform Balanced MSE; no BMC or GAI implementation found. |
| FDS | Report explicitly says learned representations were unavailable and FDS was not imitated using true test-label bins. No FDS source found. | TRAIN-only target-conditioned feature smoothing, removed at inference. |
| Logit/prior adjustment | `bayesianprior/investigateentropy{1,3,5}sfixed.ipynb` uses saved validation logits, smoothed supported priors, capped boosts and a tau grid. No encoder optimizer in those cells. `distribution_experiment.py` similarly constructs prior-response features. | Training-time sampling/prior-aware waveform representation learning. |
| Proper ordinal scores | `frozen_head_pilot.py` freezes every CNN parameter. Later `train_instrument_scores.py` trains a residual network on extracted features and original logits. Its five controls are Huber+CE, CRPS+CE, tail-CRPS+CE, marginal-CRPS+CE and ranked-BCE+CE. | End-to-end versions of these proper objectives. Threshold weights in a CDF score are not the same as magnitude-class sampling weights. |
| Weighted regression | Historical discretized CNNs and current independent/sequential models train waveform parameters. `train_sequential.py` uses high-M weighted Huber on the PMF mean plus .075 CE. Resolution/affine experiments also train their backbone. | It would be false to say all negative pilots freeze the encoder. These experiments test other hypotheses, with an established decision-weighted objective. |
| Proper option in the end-to-end runner | `train_sequential.py` implements CE + .2 tail-ordinal score. The 41 inspected local phase-2 run summaries contain 15 `weighted`, 7 explicitly named weighted-Huber objectives, and 19 without an objective field. | No completed `objective=proper` run was found; source availability is not an executed experiment. |
| Chile magnitude resampling | TEAM port repeats high-M training examples according to the authors' rule and adds optional Gaussian label noise. Its source-sized training is a separate active experiment. | This is real encoder training with imbalance handling, but not LDS/FDS or a demonstrated natural-prior density recovery comparison on INSTANCE. Gaussian target noise is not label-density smoothing. |

The supplied report's LDS-.5 readout had overall/M≥4 MAE .442078/1.027873; LDS-1 had .514080/.914256. Its Balanced-MSE response spline at sigma .7 had .556372/.902245. These are **reported**, not rerun here, results on reused 96,993 one-second exports. That report lacked event IDs and used contiguous row folds; its 91 M≥5 recordings all have M5.1. They cannot be used as independent-event evidence against an end-to-end method.

The current independent waveform model is a different, 355,682-parameter comparison trained on all 979,487 original TRAIN records. Its completed full-data runs demonstrate that the waveform representation can change outcomes. Do not equate a failed frozen-head objective with an information-theoretic limit of the first second.

## What the primary literature establishes

[Balanced MSE, Ren et al., CVPR 2022](https://arxiv.org/html/2203.16427), sections3.3–3.5, models a balanced-label Gaussian conditional and converts it to the training prior inside the likelihood. GAI integrates a fitted Gaussian-mixture prior; BMC approximates the denominator using batch labels; BNI uses label bins. Its default balanced target is not the user's natural-population error objective. A frozen spline test is therefore neither an end-to-end test nor a direct test of natural-prior density learning. BMC additionally needs the intended batch-label distribution; oversampling or correlated station records should not be silently treated as independent draws from a different prior.

[Deep Imbalanced Regression, Yang et al., ICML 2021](https://proceedings.mlr.press/v139/yang21m/yang21m.pdf), section3, distinguishes smoothing the label density from smoothing target-conditional feature statistics. FDS calibrates training features using smoothed means/covariances and running statistics; its inference discussion removes that module. Neither Gaussian noise on magnitude labels nor smoothing an inference prior implements FDS. These are useful further controls, but add bandwidth/statistics choices beyond the minimal test below.

[Balanced Meta-Softmax, Ren et al., NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/file/2ba61cc3a8f44143e1f2f13b2b729ab3-Paper.pdf), section3, explicitly connects class priors to training logits and warns about combining balancing and a class-balanced sampler incorrectly. The proposal below uses the **actual sampler**, rather than applying the original population prior twice.

[Logit Adjustment, Menon et al., ICLR 2021](https://arxiv.org/html/2007.07314), sections4–5, distinguishes posthoc adjustment from an adjusted training loss. Its principal target is balanced classification error. Prior correction, resampling, and their combination are established ideas; applying them to EEW is not itself a new general principle.

## The missing control, with explicit probability semantics

At each deadline t, let V_t contain only valid **fitting** records. Let w_i be the unchanged metadata-subsampling restoration weight supplied by the shared export. Use the existing CE category k=floor(M/.1+1e−5), with centers (.5+k)*.1 for k=0,...,65. Define fixed exposure groups g(k)=min(k//10,5): labels0–9,10–19,20–29,30–39,40–49,50–65. The grouping uses the CE label, not a second floating-point threshold comparison. Define the natural reference over available fitting records as

\[
 P_t(i)=w_i/\sum_{j\in V_t}w_j,\quad
 n_{tg}=\sum_{i\in V_t}w_i\,1[g(y_i)=g],\quad
 \pi_{tk}=\sum_{i\in V_t}P_t(i)1[y_i=k].
\]

This reference accounts for label-independent record subsampling. It does not repair waveform-quality nonresponse or become the population of all physical earthquakes. If all eligible rows are exported without subsampling, w_i=1.

Require all six groups to have positive n_tg at every deadline. If a group is absent, this protocol is not executable: report it and stop, without choosing new boundaries after outcomes. Freeze square-root exposure weights and the sampler:

\[
 a_{tk}=n_{t,g(k)}^{-1/2},\qquad
 Q_t(i)=\frac{w_i a_{t,y_i}}{\sum_{j\in V_t}w_j a_{t,y_j}},\qquad
 q_{tk}\propto\pi_{tk}a_{tk}.
\]

Thus rare magnitude bands get more actual encoder updates, without extreme sampling of individual .1 bins. Sampling remains proportional to P_t within each band and fine bin; do not replace that with uniform-event sampling inside a band. Both low and high rare bands receive emphasis. More presentations of a rare event do not create new independent earthquakes.

Let z_theta(x,t) be the 66 natural-distribution logits. Draw from Q_t and train

\[
 L_t=\operatorname{CE}\{z_\theta(x,t)+\log a_t,\ y\},\qquad
 \widehat p_{\rm natural}(k\mid x,t)=\operatorname{softmax}(z_\theta)_k.
\]

On occupied bins, log a differs from log q−log pi by a common constant. For any natural conditional p, the sampler conditional is a_k p_k / sum_j a_j p_j. CE estimates that sampler conditional; the invertible transformation recovers p. Equivalently, a model trained to output sampler logits u deploys softmax(u−log a). This is an algebraic target identity under the sampling construction, **not** a finite-sample calibration or tail-improvement guarantee. It does not justify correcting an arbitrary external region by a marginal-prior ratio when its class-conditional waveforms differ.

Because groups are nonempty, a is finite and positive for all66 logits, including fine bins with zero training count. Empty fine bins have no sampled records and q=pi=0; the direct log-a formula never evaluates log(0/0). It creates no examples in those bins and asserts no learned coverage there. Keep the same66 logits in every arm, without support masks or pseudocounts; report fit-empty/held-occupied bins separately. Out-of-range labels must be reported before any clipping, not silently admitted as supported magnitudes. Retain their actual continuous targets in descriptive point-error reporting; a categorical support failure is not a reason to quietly discard a hard heldout event.

Do **not** additionally multiply this loss by inverse Q/P weights: that would change the intended exposure objective. Original restoration weights enter Q once. Do not add natural-distribution CRPS uncorrected under Q; it targets the sampler conditional instead. The first experiment uses CE alone to isolate the mechanism.

A fixed-offset trap matters: with a trainable decoder bias, CE(s+log pi) on the unchanged natural sampler followed by outputting softmax(s+log pi) can be merely ordinary CE under a bias reparameterization. It is not persuasive evidence of a new mechanism. The control above changes exposure and propagates its gradients through the waveform encoder. Even then, success establishes usefulness of known imbalance training, not novelty.

## Frozen minimal comparison and shared export contract

Use `work/polarization_preflight/protocol.md` v2, SHA256 `a9b12a88be3a46e96d0f3f208f64b7728d1a17bb132e146887694e40288a448b`, for population, manual-P clock, metadata/response gates, label-independent sampling and deadline-specific validity. Event hash salt `polarization-event-v1` assigns buckets0/1 to held events and2–9 to fit events. Station salt `polarization-station-v1` assigns0/1 to held stations; all channel families/locations/epochs and qualifying co-located aliases belong to one connected component. Fit only fitting events at seen stations. Evaluate the same held-event set separately at seen and held stations; preserve every identity and exclusion reason. **Do not use old VAL or TEST.**

The current polarization export contains descriptors, not waveforms; it cannot train this encoder. A shared future waveform export must retain source row/trace/event/station identities, sampled counts, unchanged restoration weights, per-axis gains/units, immutable metadata and response hashes, and one validity mask per deadline. Export counts once. Native log amplitudes can be derived from gains; duplicating a gain-normalized and per-axis RMS-normalized waveform branch can be algebraically redundant. Input/target normalizers and n_tg use fit rows only. Neither a five-second quality failure nor a five-second normalization statistic may remove/change an otherwise valid one-second case.

Use the planned response-control **B, native-late** backbone in all three objective arms: one count-prefix shape encoder, native log amplitudes, the same late static/response metadata (including gain), and neutral-initialized late FiLM. The response-conditioned encoder's architecture comparison is separate; do not vary conditioning and balancing simultaneously. All three objectives must share the final audited architecture/export hash before any fit; an incompatible old normalized cache or frozen historical CNN is forbidden. This inherits polarization's population/split rules, not its random-feature ridge model. The TRAIN optimizer sampling below is an explicitly new experiment; it never changes initial population selection or replaces quality failures.

| Arm | Example sampler | Objective |
|---|---|---|
| A, established strong loss | P_t | Existing Huber(delta1), weight1+5 max(M−3.5,0), plus .075 CE |
| B, natural proper baseline | P_t | CE(z,y) |
| C, exposure control | Q_t | CE(z+log a_t,y) |

Use seeds20261009/20261010; identical initialization per seed;10 fixed epochs; batch512 per deadline; AdamW3e−4, decay1e−4, cosine minimum3e−5, clip5; deterministic CUDA/cuBLAS with pinned runtime. Let D=max_t |V_t|, determined only from fitting validity counts. Each epoch is D draws with replacement per horizon in every arm, giving exactly ceil(D/512) optimizer steps and an identical final remainder size. It is not an enlarged rare-class epoch. A/B share exact orders; C necessarily has a different sampled order. Save every order hash, draw counts and unique event counts. No temperature, tau, density bandwidth, seed, best epoch or sampling-exponent selection.

One shared model trains all deadlines jointly by averaging three prefix losses before each update. Each loss draws from its own V_t and P_t/Q_t, so an earlier deadline never inherits later quality selection. The implementation must expose a strict prefix-only forward path; do not compute all deadlines on an invalid suffix merely to select an earlier output. Test the common optimizer-step schedule, sampler law, suffix mutation, restoration weighting and gradient flow before running. This memo freezes the comparison; the final audited code/config/export hashes must instantiate it before a fit.

There is no calibration partition in polarization v2. This fixed comparison therefore fits no calibration transform and evaluates both held panels only after every final checkpoint exists. A later calibration study must carve a new event-heldout partition strictly inside fitting events before its labels or predictions are examined.

Report both seeds and their fixed equal-PMF ensemble at1/3/5: MAE for PMF mean and median, MedAE, CVaR95, M≥4/M≥5 error and bias, recording-weighted and event-macro metrics, unit/family strata and individual tail-event deltas. Report ordinary continuous-target CRPS as well as the quantized categorical NLL/ordinal score; do not call a binned target score exact continuous-target CRPS. Report tail probability reliability with counts. Use the polarization v2 fixed paired-event bootstrap. No cherry-picked best seed/window.

Before results, adopt the existing development tolerances, using the PMF mean as the fixed primary action: C versus B must have M≥4 event-macro MAE at least .02 lower, bulk MAE/MedAE no worse by .002, both seeds nonpositive tail deltas, and at least20 independent M≥4 events in each held panel, at all three horizons. Require the upper95% paired-event bootstrap bound on bulk MAE difference <=.005 and on tail event-macro difference <0. Also compare C with A using the same reporting and tolerances: beating weak CE alone does not satisfy the user's strong-baseline goal. PMF-median results are secondary; do not choose between actions after scoring. Failure/sparse support remains a result; no split changes. These are exploratory investment gates, not familywise confirmatory tests.

The closest deterministic raw-backbone reference took approximately510–512 seconds for10 epochs on979,487 rows/all three horizons/A10G. The new sampled population is smaller, but response inputs, deadline-specific sampling and rebuilt normalization change the workload. Measure TRAIN-only throughput after implementation; do not promise the old runtime or launch extra jobs from this memo.

## What would count as progress toward the user's paper

The attached reference is **RVLoss**, which identifies a failure of nearest-neighbor pseudo-label construction and changes the mechanism imposing motion rigidity. Its lesson here is to identify and falsify a specific failure mechanism. It is not a template for calling every new auxiliary objective foundational.

A C-over-B/C-over-A improvement would justify investigating rare-example gradient exposure and representation quality; a failure would rule out this particular known control on the fixed population. It would not establish that all balancing methods fail, that the first second has no useful tail signal, or that a new EEW principle has been discovered. Improvements cannot be guaranteed while holding natural Bayes-optimal MAE fixed; the plausible opportunity is correcting finite-data/model/optimization error. Cross-region data with enough independent large events remains necessary for a paper-level superiority claim.

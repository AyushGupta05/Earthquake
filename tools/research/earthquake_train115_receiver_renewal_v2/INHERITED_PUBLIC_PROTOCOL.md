# Prospective receiver-activity renewal pilot

Advisory, not actual-run authority. Root freezes exact support, input tensors, implementation and checks before execution. Use only original65TRAIN/DEV selections,41/24; preserve all65/195 placeholders, original clocks, picks, literal channels and failures. Exclude all31TEST inputs. No actual waveform body or model was opened to design this.

## 1. Freeze the observation before values are inspected

Use only strictly qualified original samples. Let `P_s` be the selected station's frozen accepted P time, `T0` the unchanged common clock, and `a_h=T0+h-P_s`. Neither shifts to make a longer local window. A station not yet arrived is not quiet. For this pilot, a usable prediction requires>=.25s local post-P at that horizon and complete pre-P noise support; otherwise all arms retain an unavailable prediction for that cell. Never replace its station/event. Primary paired metrics use the common fully qualified event intersection, with original65 coverage/failure accounting alongside it.

For each literal component, subtract its mean over `[T0-3,T0)`. Split that same interval into12 nonoverlapping.25s cells. Noise power `n_c` is the median of their mean squared centered counts, floored at1count². This is a receiver count statistic; it is not response calibration or physical-motion normalization. The floor and its activation are reported. For local post-P cell `j`, `[P_s+.25(j-1),P_s+.25j)`, compute

`R_j = max_c mean_cell(centered_counts_c²)/n_c`,

`b_j = 1[R_j>9]`.

Only complete cells ending at/before the common deadline are used; exact integer timestamps determine membership. No interpolation/filtering/rotation or future taper/normalization. The ratio threshold9 is frozen prospectively, not fitted to DEV or selected among a grid. Per-record noise estimation uses only received pre-P data; any cohort-level standardization uses TRAIN alone. Tiny/constant noise, gaps, missing channel/noise support remain explicit. RetainE/N/Z versus literal1/2/Z and metadata/rate strata.

This defines observed high-energy activity, **not P-only/source-active truth**. S waves, coda, other signals, radiation and instrument response can change it. Treat `b=0` as quiet and allow a subsequent `b=1`; do not stop the evidence chain at the first quiet interval. The threshold and cadence are conventional measurement choices, not novel ingredients.

Let `z` be an embedding of only the first.25s local waveform plus fixed pre-P noise/context; let `b_1` be part of that initial information. For every later complete cell, `r_{j-1}` is the number of consecutive preceding cells in the current observed state. Bound it by the observed20cell maximum, without inventing unobserved history. Use local time `u_j=.25(j-1)`. At network1/3/5, predictions include respectively all currently complete cells; new3/5 factors come only from the nonoverlapping portions since the previous deadline.

## 2. Exact conditional model

The base density is `pi_theta(m|z,c)=sum_{k=1}^5 w_k Normal(m;mu_k,sigma_k²)`, with uncapped means, softmax weights and `sigma_k=.05+softplus(rho_k)`. Context `c` contains only available station location/elevation, qualified channel-family/rate/gain/unit descriptors with missing masks, and initial local timing. No station/eventID, source location, magnitude, absolute date, later picks or future station identities are inference inputs. Strong metadata controls receive these identical fields.

For `s in {on,off}`, use one affine logit

`ell_s = alpha_s + beta_s*(m-mref) + v_s^T z + w_s^T c + gamma_s*log(1+u_j) + eta_s*log(1+r_{j-1})`,

where `mref` is the TRAIN-label mean. Set

`P(b_j=0|b_{j-1}=1,history,m,z,c)=sigmoid(ell_off)`,

`P(b_j=1|b_{j-1}=0,history,m,z,c)=sigmoid(ell_on)`.

All coefficients are unrestricted: do not force highMw to have longer activity or impose an artificial tail lift. Current state and run age summarize history in this deliberately small conditional family; this Markov/renewal approximation can be wrong. Initial state `b_1` is observed. No physically unidentifiable hidden stop/grow component is fitted.

Define the observed prefix likelihood and deployed density as

`L_h(m)=product_{j=2}^{floor(a_h/.25)} P_phi(b_j|b_<j,m,z,c)`,

`q_h(m)=pi_theta(m|z,c)*L_h(m) / integral pi_theta(v|z,c)*L_h(v)dv`.

Each cell appears once. Conditioning every factor on initial `z,c` is legitimate; independently multiplying a full-prefix posterior by the same feature's likelihood is not. The law is a generative classifier on a lossy activity representation; it is not the exact posterior of the original waveform. When no new cell is available `L=1`. When a run has no observed exit, its stay factors are right-censored exposure. Do not append an exit at1/3/5 or substitute duration=deadline as an uncensored target. Quiet-to-active factors permit later arrival/reexcitation without claiming a renewed rupture.

For illustration, an observed active run with per-cell exit hazard `d_j` contributes `product(1-d_j)` if censored, or `product_{j<k}(1-d_j)*d_k` if an exit is actually observed in cellk. Its time resolution is interval-censored. A three-quiet-cell confirmed gap is a reporting summary, not an absorbing physical end or a separate likelihood factor.

Fit the plain supervised joint objective once/event:

`J=-log pi_theta(Mw|z,c)-sum_{j=2}^{J_5} log P_phi(b_j|history,Mw,z,c)`.

This uses final TRAINMw and the observed TRAIN activity through5s. It is an ordinary joint likelihood, not independent future information or a new proper-score theorem. No prior resampling correction, CVaR/entropy objective, growth auxiliary, teacher or TEST calibration is bundled in. More cells give more likelihood contributions; report the two loss/gradient scales. The conditional family is anchored by actual TRAIN labels, not by interpretation of mixture components.

Use a small shared CNN encoder as in the prior native-count baseline (3->8->16->16, kernels9/5/5, SiLU, masked mean/max, retained prefix logamplitude), but restrict the candidate's `z` to its first.25s. A32-unit MLP emits the15 base-density parameters. Hazard logits are the displayed affine forms. Root records actual field dimensions/parameter counts; comparable arms must be within5% trainable parameters. Added harmless unused parameters do not count as a matched-capacity control.

Normalization is one-dimensional. A proposed differentiable implementation uses64-point Gauss–Hermite quadrature per base Gaussian, logsumexp and no magnitude-support truncation. Before accepting any saved inference, independently recompute normalization/mean/NLL using128points or adaptive quadrature; require agreement within1e-4. A failure remains a numerical failure, not a physical result or permission to change the head after DEV. Test sigma extremes and far-tail observations on invented examples. Primary action is the integrated density mean; the distribution median remains secondary.

## 3. Minimal matched controls

| Arm | Model and inputs | Isolates |
|---|---|---|
|B|Current full-prefix CNN plus static context and uncapped5Gaussian density; proper conditional MwNLL at1/3/5|Strong usable waveform benchmark, including event/station confounding context|
|F|B with direct same current `R_j,b_j,state/run-age` features supplied through an equal-capacity branch|Feature value versus a special likelihood/operator story|
|H|Same candidate base, transitions, objective and observations, with `eta_on=eta_off=0`; reallocate those two degrees of freedom to initial-feature interactions|Free memoryless/geometric hazard, rather than run-age mechanism|
|C|Displayed run-age renewal candidate|Whether explicit activity age is useful|

B/F receive exactly the same common deadline samples and context as C, so C has no observation advantage; they can also use waveform details C compresses away. F never receives5s features at1/3. C/H share initial tensors, final fixed update, optimizer and full joint loss. Because B/F have conditional objectives and C/H a joint objective, C-H is the clean run-age mechanism contrast; C versusB/F is practical competition, not an isolated generative/discriminative theorem. Root may reject an unmatchable parameter-budget design before fitting; freeze the chosen design, not a post-result best architecture.

Use the already proposed metadata-only/label-permutation baseline first. A waveform-versus-metadata gain is necessary context and does not by itself validate C. The old positive-peak censor model is a historical negative result. H is the new free-hazard matched control; calling it the old hurdle is inaccurate because its observation space is different.

## 4. Low-cost staged falsification

**Stage0, source/invented tests:** verify activity extraction is deadline/prefix invariant, localP delays exclude unavailable cells, on/off history/run age is correct, censored exposure has no appendedexit, and reactivation remains legal. Check on invented traces: continuing subpeak oscillations versus zero growth have differentactivity; identical activity/initialcontext gives identical C posteriors despite differing invisible future ruptures; H is exactly age independent. Tests verify implementation, not magnitude predictability.

**Stage1, qualified TRAIN only, no fit:** count active-to-quiet and quiet-to-active transitions, censored runs, noise-floor activations, nativefamily/rate/station groups and events supporting each. No DEV threshold tuning. Require>=5 independent TRAIN events with an active-to-quiet transition and>=5 with an active run censored at5s; require variation in run ages, both Mw>=5.5 and lowerMw among usable TRAIN, and the prospective sequence-qualified support floor in the prior pilot. Reactivation is reported, not required. If this gate fails, stop without a hazard fit. Transition counts cannot identify the whole magnitude-conditioned law; this is only a minimum variation gate.

**Stage2, one frozen comparison:** fourarms×two seeds20261012/20261013, no architecture/threshold/loss grid. Uniform event batches8; Adam1e-3, no weightdecay, normcap5,300updates, finalcheckpoint, fixed TRAIN-only standardization and shared event orders. ForB/F, average NLL across its three deadlines per event. ForC/H, use the displayed joint J once/event. No DEV selection/replacement, no ensemble-action switch. Proposed CPU caps:5min/fit,45minwhole comparison including score replay. If unmet, retain incomplete status; the small pilot does not justify automatically starting a GPU.

Per-seed fit states, timings, observations, every prediction and source/runtime identities stay private for independent replay. Public summaries contain approved aggregates only. A later nontrivial implementation requires focused tests and autoreview; this doc-only packet does not invoke a code reviewer.

## 5. Fixed descriptive continuation gate

At **each1/3/5** and **bothseeds**, C must improve event-macroMw>=5.5 MAE by>=.02 againstB,F,H and improve full common-cohortNLL/CRPS againstB,F. It must not worsen observed lowerMwMAE/MedAE or common-cohortCVaR95/maximum versus any comparator. Report>=6 separately, all>=7cases separately, signed tailbias/P95/PIT/50-80-95%coverage, original65/195coverage, censor/transition counts and all seed/horizon failures. Use the fixed density-mean action; median gains cannot substitute. Tail-conditioned scores are descriptive, not proof of a proper population forecast. Current staticmetadata remains in every waveform arm.

This deliberately strict observed gate can be inconclusive or fail. With only24stratifiedDEV and two nominalMw>=7, no paired interval turns it into representative bulk preservation, a new winning method, or a highMwgeneralization result. Descriptive sequence-paired intervals should be shown when supported; no cross-seed/event independence fiction. A favorable gate earns a separately frozen larger independent test. A failed C-H contrast rejects the run-age hypothesis; a tie withF credits ordinary features; a tail-only gain with worse bulk/max rejects the user objective. A1s failure prevents an all1/3/5 claim. All old negative results remain unchanged.

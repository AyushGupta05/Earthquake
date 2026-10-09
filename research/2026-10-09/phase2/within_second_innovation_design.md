# Within-first-second censored innovations: prospective design

9 October 2026. Theory/design only. No implementation, GPU launch, data acquisition or TEST waveform reads. Await the current 1→3→5 censored-innovation result before choosing this extension.

## Recommendation and claim boundary

A **0.2→0.5→1→3→5 s** version is coherent and can improve 1 s because it assimilates two additional observations before that deadline. It requires a newly trained 0.2 s prior/context; feeding a short zero-padded record into the frozen 1 s CNN is not a matched substitute.

The potentially useful modification is to share a magnitude/time-conditioned likelihood across unequal observation blocks while tying no-record mass and positive growth to the same CDF. Test whether that restriction transfers evidence across the rare magnitude bins better than a free hurdle or a discriminative head. This is a temporal/data inductive bias, **not new probability theory**. Finer sequential conditioning, censoring, shared parameters and density normalization are established. The closest EEW antecedents remain [RTMag 2008](https://doi.org/10.1029/2007JB005386), [Gutenberg 2015](https://doi.org/10.1785/0120150098), [Trugman et al. 2019](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf), and [Münchmeyer et al. 2022](https://arxiv.org/html/2203.08622v1); the distinction must be demonstrated against explicit matched controls.

The completed static instrument result is the relevant operational comparator. Its gain/unit controls already explain substantial improvement; a record likelihood must not receive credit for physical normalization or station descriptors that its baseline lacks. The generic future-growth auxiliary failed to deliver a robust gain, so this design uses observed evidence at inference, with no future teacher.

## Observation and information contract

Use 100 Hz samples with deadlines `[20,50,100,300,500]`, all indexed from the same P alignment. The first 10 post-P samples define the fixed baseline mean, disclosed as such; no future or pre-P sample is required by this statistic. This is not an operational automatic-picker latency claim. Released-array preprocessing limitations persist.

For one vertical channel, recover counts with the audited prefix normalizers and use the epoch sensitivity/physical-unit flags already verified. Define a fixed native-unit floor and

\[
A_j=\max\{\epsilon,\max_{0\le n<n_j}|u_n-b|\},\quad
B_j=\max\{\epsilon,\max_{n_{j-1}\le n<n_j}|u_n-b|\},
\]
\[
Z_j=\log_{10}B_j-\log_{10}A_{j-1},\qquad
G_j=\log_{10}A_j-\log_{10}A_{j-1}=\max(0,Z_j).
\]

The amplitude formula must use one convention: if `u` denotes sensitivity-divided motion, `b` must be sensitivity-divided too; alternatively subtract the count baseline before dividing. Keep HH velocity and HN acceleration distinguishable. Ratios are invariant to simultaneous positive rescaling of counts, baseline and sensitivity, away from the same floor. This is **statistic invariance**, not full-method invariance if the initial encoder retains count-dependent features. Scalar sensitivity removal does not remove the frequency-dependent response.

Let `h0` encode only the first 20 samples and allowed static descriptors. The retained history for the censored model is

\[
H_j=(h_0,\log A_0,G_1,\ldots,G_j,\text{validity history}).
\]

Later contexts may be a deterministic recurrent encoding of that exact history. They may also use the candidate magnitude `m`, previous deadline and block duration. The current record `log A_j` is derivable from `log A0 + ΣG`; it is not extra waveform information. The full-Z control retains `Z1,...,Zj`, from which the running record is updated using `max(0,Z)`.

**Do not introduce a full 0.5/1/3/5 s waveform embedding into a later likelihood while the posterior has seen only record summaries.** Either assimilate that extra embedding through its own jointly specified likelihood, or keep it out. Likewise, do not multiply the record likelihood onto an independent full-prefix network that already observed those same samples.

Floor/missingness rules must match all arms. A conservative first pilot freezes updates after the first invalid block, preserving all rows and recording the reason. It must not silently evaluate only high-SNR valid rows. If missingness/floor activation depends on magnitude, this fallback is an operational heuristic: exact Bayesian claims apply only to a correctly modeled observation/missingness process, not automatically to the fallback. Report validity by magnitude, sensor family and deadline.

## Shared likelihood and recursion

One small shared head receives `(H_{j-1}, m, t_{j-1}, Δt_j)` and returns `μ,σ>0` for latent `Z_j`. For each candidate grid magnitude,

\[
q_j(g\mid m,H)=
\begin{cases}
\Phi(-\mu_j/\sigma_j),&g=0,\\
\phi((g-\mu_j)/\sigma_j)/\sigma_j,&g>0.
\end{cases}
\]

The measure is a point mass at zero plus Lebesgue measure on positive growth. If zero is defined through a positive numerical tolerance, use the corresponding interval mass, not `F(0)`. The shortest blocks may exhibit very different mark distributions; supplying exposure does not prove that the shared Gaussian family fits them.

Update in log space:

\[
\log p_j(m_k)=\log p_{j-1}(m_k)+\log q_j(G_j\mid m_k,H_{j-1})-\log Z_j^{\rm norm}.
\]

The normalization symbol is distinct from the observed `Z_j` innovation. Predictions at 1/3/5 s use exactly 2/3/4 updates. A magnitude-independent likelihood leaves the distribution unchanged. No-record observations can be informative if their mass differs across magnitudes; they are not observations of rupture arrest.

A numerical magnitude input promotes sharing across rare bins, but it does not establish extrapolation beyond the label range. Fix the magnitude grid/support before comparing arms, disclose the largest TRAIN label, and do not present bounded-grid interpolation as M8–9 extrapolation.

## Clean two-stage training

**Stage A:** Train a new compact 20-sample encoder and prior with an ordinary proper categorical score, fixed epochs and event/sampling-restoration weights. A short-window-compatible CNN is required; its receptive field/pooling must actually support 20 samples. A counts-plus-instrument baseline and a sensitivity-normalized, unit-aware baseline are scientifically distinct. For the first mechanism pilot choose one prespecified baseline and use its *identical seed-specific checkpoints* in every update arm; report the other as a separate representation control if run. Full static site features must be identical across all mechanism arms.

**Stage B:** Freeze the shared prior/encoder per seed, and train the update heads for 15 fixed epochs. This isolates the observation model. End-to-end training can follow only as a separately registered comparison because it also changes the 0.2 s representation/prior. For Stage B training rows, event-cross-fit Stage A outputs would be stronger than same-record features; at minimum disclose reuse and include it consistently across every arm. No validation epoch/loss selection.

Compare two objectives for the **same tied model**:

1. Generative conditional NLL: minimize `−Σ_j log q_j(G_j | M_true,H_{j−1})` on valid observations. The fixed proper prior and a correct likelihood would support Bayesian semantics; finite models and calibration errors remain empirical questions.
2. Posterior CE: minimize the mean of `−log p_j(M_true)` at the prespecified output deadlines, e.g. 1/3/5 equally. This directly optimizes magnitude prediction. Its normalized `q` functions are discriminatively trained factors; class-posterior loss alone does not establish that they are calibrated conditional observation densities. Report them as a normalized likelihood-shaped update, not a true observation model.

Do not mix both objectives with a selected coefficient in the first comparison. Their separation is the scientific question. If only posterior CE works, the plausible conclusion is useful constrained discriminative evidence accumulation, not validation of the Gaussian growth law. A beta-weighted Huber/CE initial predictor changes this interpretation, so the current cost-sensitive 1 s checkpoint cannot be silently repurposed as the proper 0.2 s prior.

## Minimum controls and decisive falsifiers

Keep row identities, masks, normalizers, allocation/RNG sequence, parameter budget, seeds and optimizer steps matched. A shared-time-head comparison is not matched to a collection of much larger independent heads without reporting that difference.

| Control | Question it resolves |
|---|---|
| Frozen common 0.2 s prior | Does later observed evidence help at all? |
| Same-input discriminative recurrent/residual head on `h0,A0,G` | Does the tied likelihood outperform an ordinary predictor with the same evidence? |
| Tied censored Gaussian, conditional NLL | Does a supervised observation model support the recursion? |
| Tied censored Gaussian, posterior CE | Is the useful effect discriminative optimization rather than density calibration? |
| Free-hurdle truncated Gaussian, matched objective | Does tying zero mass to the positive Gaussian shape help? The positive density is `f(g)/(1−F(0))`; this avoids confounding the tie with a lognormal positive shape. |
| Full-Z Gaussian, matched objective | Does throwing away negative block-peak innovations help or merely lose signal? |
| Independent full-prefix 1/3/5 s model using the same instrument representation | Does the restricted evidence path beat an operational model allowed to use all observed waveform shape? This is a richer-information comparator, not proof about the likelihood factor alone. |

Run the core tied/free-hurdle/full-Z/discriminative arms with the same chosen objective first; the NLL-versus-posterior-CE paired comparison isolates training semantics. Do not report a win over a weaker objective as a win for censoring. Allocate dummy unused output slots when needed to keep initialization order and counts identical, as in the current pilot. Separately score the actual learned conditional distributions; allocated parameter equality does not equal functional-capacity equality.

The main success criterion is replicated rare-event **event-macro** improvement with prespecified bulk MAE and median-error noninferiority, plus proper distribution scores and false-positive behavior at all 1/3/5 s deadlines. Do not select one favorable seed/deadline. The reused 13-event M≥4 VAL tail remains exploratory; external real large events and a sealed evaluation are required for the paper's large-magnitude claim.

Stop or narrow the interpretation if:

- The current long-block pilot cannot match its same-input discriminative/full-Z controls and diagnostics show poor conditional fit. More temporal steps add assumptions and should not be justified simply by a desire to improve 1 s.
- The new prior or floor policy performs badly at 0.2 s, invalidating many relevant observations. Report this before expanding the model.
- Free-hurdle matches/beats the tied model. The atom/positive-shape restriction is unsupported, even if all update models beat a frozen prior.
- Full-Z wins. Record censoring was information loss; retain uncensored evidence rather than defending the censoring story.
- Same-input discrimination wins. The generative restriction is not helping under the chosen compute/data budget.
- Gains vanish against sensitivity-normalized or response-aware waveform baselines. The main benefit was representation/calibration, not the new distribution mechanism.

No new theory is needed to justify running a well-controlled EEW adaptation. Conversely, more sub-second steps cannot turn an established recursion into a foundational principle by naming it differently. A defensible claim would specify precisely which shared conditional restriction improved which real-data error/calibration measures under fixed information and compute.

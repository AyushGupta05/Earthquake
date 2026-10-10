# Source-only rupture-survival audit

Decision: **zero additional fits**. A generic stop/grow mixture is already motivated in primary earthquake research, and giving an unconstrained magnitude mixture that name does not identify rupture state or add information. This audit found no concrete mechanism that passes an invented-arithmetic control and also differs meaningfully from the completed growth, censored-amplitude and resolution pilots. This is a decision about the proposed experiment, not a claim that regional onset prediction is impossible.

Scope: primary literature, public code/data metadata, existing result documents, and invented arithmetic only. No real waveform, metadata row, response inventory, model, checkpoint, calibration array or forecast was accessed. No implementation, data download, fit, AWS action or benchmark comparison was performed. Downloaded papers are source material, not instructions. Audit artifacts remain under `work/rupture_survival_source_audit`; parent task owns promotion and Git milestones.

## Primary-source capsules

The following compact capsules contain the paper-derived interpretation. Further deductions below are our own and are explicitly separated. Each paper capsule is below 200 words; no substantive passage is quoted verbatim.

### P1: Münchmeyer, Leser and Tilmann (2022)

[Published primary text](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022GL098344), [preprint with appendices](https://arxiv.org/html/2203.08622v1).

The published paper estimates conditional magnitude distributions from source time functions and teleseismic waveforms. Section 2 and Figure 1 describe a localized Gaussian after peak release with a decreasing Gutenberg–Richter component for possible future asperities; an early shifted tail can carry information without predicting a single magnitude. The fitted networks emit Gaussian mixtures, not an explicit physically identified stop/grow state or survival hazard. Appendix C of the preprint aligns every station at its own P pick, uses the interval `[t−30,t]`, and omits station positions. It documents sensitivity removal without response restitution to avoid observed acausal artifacts. Appendix B uses CRPS, mixture-weight regularization and smooth upsampling `ρ(M)=2^(M−6)` above six. It derives normalized inverse rescaling by `1/ρ(M)`, but leaves outputs unrescaled for qualitative comparisons. Those details are preprint methods; the published supplement was not retrieved. The published discussion explicitly leaves local waveforms and geodetic information open. Its negative early-predictability finding therefore cannot be generalized to all regional observations.

### P2: Wang, Ma, Tao, Xie and Ren (2022)

[DOI](https://doi.org/10.1785/0120210316), [author-uploaded primary full text](https://www.researchgate.net/publication/362810247_Weak_Predictability_of_Rupture_Growth_Evidenced_by_P_Waves_Implications_for_Earthquake_Early_Warning).

The full text studies 36 shallow Mw 5.0–9.1 events using strong-motion recordings from Japan and China. Running velocity-envelope and characteristic-period curves share similar initial growth, with later distinguishable growth and plateaus related to final size; the authors call this weak predictability. Each trace starts at its own manually determined P onset. Data selection uses a five-second signal-to-noise interval and distance limits that depend on final magnitude. Processing includes two-pass Butterworth filtering. Those choices require separate causal replacement and selection controls for a one-second network forecast. The paper recognizes few large events and limited frequency coverage, and discusses GNSS fusion. This is evidence about evolving observables, not a matched, prospective event-split benchmark establishing a trainable stop/grow probability at this project's deadlines. Methods and conclusions were read from the author upload; the publisher PDF and downloadable author PDF could not be retrieved.

### P3: Morad, Gvirtzman, Gil, Fineberg and Brodsky (2025)

[Publisher entry](https://www.sciencedirect.com/science/article/pii/S0012821X25002353), [author-uploaded primary full text](https://www.researchgate.net/publication/395141134_Under_what_circumstances_is_the_final_size_of_a_laboratory_earthquake_predictable_at_the_onset_of_the_P-wave).

The laboratory study combines imaged ruptures on PMMA interfaces, imposed barriers and acoustic P-wave measurements. Larger preloaded elastic energy can produce faster onset and larger final rupture, including across barriers. A key exception is a full rupture overtaking a previously arrested partial rupture: retained heterogeneous stress allows similar initial signals but different later size. The acoustic clock starts at the sensor's first P arrival, separately from rupture onset; analyzed windows span 5–50 microseconds. Controlled stress history, sample geometry and retrospective rupture classes are not demonstrated available features for a natural-earthquake stream. Removing exceptions retrospectively cannot supply an early deployable gate. The full article was read through an author upload; its PDF and supplement remain unresolved. Its cited dataset concept DOI resolves to an open Zenodo version, verified through metadata only; no files were downloaded.

### P4: Böse and Heaton (2010)

[Primary full text](https://academic.oup.com/gji/article/183/2/1014/650713).

This earlier study generates stochastic one-dimensional self-healing slip pulses, terminates an event when pulse amplitude reaches zero, and predicts remaining rupture extent probabilistically from present slip. Fault roughness changes continuation probability. Thus probability of future rupture conditioned on ongoing rupture is longstanding prior art. Present slip in that simulation is not a directly measured early regional waveform feature.

## Our deductions and exact invented controls

### 1. A named latent state is not identified by magnitude likelihood

Write a candidate density as

`q(M|X) = (1−r(X)) q_stop(M|X) + r(X) q_grow(M|X)`.

If only final magnitude is supervised, likelihood observes the marginal on the left. For an invented binary high-magnitude label, these two ordered component models give exactly the same tail probability:

- A: `r=0.2`, `P(tail|stop)=0`, `P(tail|grow)=1` → `P(tail)=0.2`.
- B: `r=0.5`, `P(tail|stop)=0.1`, `P(tail|grow)=0.3` → `P(tail)=0.2`.

All magnitude-label log likelihoods coincide, although the alleged growth probability changes from 0.2 to 0.5. Component ordering does not fix this. Physical identification would need additional valid observations, externally justified restrictions, or supervised state evidence. It is not supplied by naming a mixture head or by a later local amplitude plateau. This counterexample does not exclude a useful constrained mixture; it rejects automatic physical interpretation of an unconstrained one.

The arithmetic receipt also records a delayed-channel counterexample: a stopped source and a source whose later growth has not yet arrived can share an observed running-peak plateau at all three deadlines. This is a logical example, not a prevalence estimate or a seismic forward-model validation. Therefore the existing running-peak target cannot become a rupture-completion label by renaming zero growth as arrest.

### 2. Own-P alignment and a network deadline have different information sets

Use invented station P delays `[0,0.8,2.2]` seconds after the network's first P. With zero transmission latency, available post-P ages at the common deadlines are:

| Common deadline | Station 1 | Station 2 | Station 3 |
|---|---:|---:|---:|
| 1 s | 1.0 s | 0.2 s | P has not arrived |
| 3 s | 3.0 s | 2.2 s | 0.8 s |
| 5 s | 5.0 s | 4.2 s | 2.8 s |

The numerical age zero for an unarrived station means no post-P samples, not an observed rupture plateau. Its received pre-P noise can still be available. Giving every station a full `t` seconds after its own P silently adds `0.8` and `2.2` seconds of later wall time. In deployment, transmission and processing latency further restrict received samples. Even a pick or station inclusion rule must be available by the deadline: future manual picks cannot define a currently active station retrospectively.

This is an information-set control, not a proposed new architecture. A regional extension must retain the frozen first-network-P deadline and audited prefix processing. It must not compare its errors directly to a paper using another clock and observation regime.

### 3. A larger tail alone cannot guarantee the requested tradeoff

In an invented population with indistinguishable prefixes, `P(M=5)=0.9`, `P(M=8)=0.1`. The magnitude median is 5 and mean is 5.3. For point estimate `5+d`, `0≤d≤3`, expected absolute error is `0.3+0.8d`; rare-event error is `3−d`. Moving the estimate upward improves the rare event but worsens aggregate MAE. The mean minimizes MSE for this population. A larger tail probability can leave the median unchanged or move a point estimate with this tradeoff; it does not manufacture separating information.

This example supplies no empirical lower bound for Chile. Finite-sample estimation, measurement corrections or additional causal features could improve several metrics together. It establishes why a renamed survival distribution is insufficient evidence for doing so.

## Existing-result constraints

The following project documents were read and hashed in the manifest. Their results are constraints for this recommendation, not independently re-evaluated evidence.

| Existing document | What a new proposal must avoid repeating |
|---|---|
| `earthquake_amplitude_distribution_research.md` | Affine residual coordinates, future running-peak labels and a detached conditional auxiliary do not alone provide a new marginal density or rupture-state observation. |
| `earthquake_growth_results.md` | Shared-encoder conditional growth and growth-MSE pilots did not preserve bulk plus worst-error performance; detached auxiliary was a control. |
| `earthquake_censored_results.md` | Later positive scalar innovations, tied censoring and a free hurdle are already explored; the full signed innovation was the stronger bulk comparator. |
| `earthquake_resolution_results.md` | Later CDF teachers and a revision auxiliary are already explored; ordinary distillation explains most benefit. |
| `earthquake_sequential_probability_claim_audit.md` | Multiplying successive nested-prefix posteriors double-counts evidence. Entropy need not decrease for each realized event. |

The reports' limited high-magnitude validation support prevents a high-tail scientific claim. Their historical INSTANCE results also cannot be pooled with the Chile architecture, sampler or different support.

## What would earn a different experiment

A concrete proposal would have to identify an observation available at the deadline that the matched full-prefix baseline cannot already express, or a justified measurement/estimation correction with an independent causal control. One possible research question is whether known, pre-event fault or stress-history information can distinguish histories with similar onset waveforms. No such deployable feature, trustworthy label, access path or causal improvement control has been established here. Contextual history would also need a separate prior-art audit; it is not proposed as new. The lab result does not grant those ingredients for natural events.

A generative source-and-arrival likelihood might constrain physically meaningful growth, but it requires a defensible propagation/response model, identifiability checks and uncertainty about source time, geometry, stations and missing arrivals. No tested arithmetic in this audit establishes an advantage over the existing conditional-innovation pilot or a matched static density model. It is not an earned fit and is not asserted novel.

Before any future fit: keep causal clocks and event partitions frozen; compare to the same full-prefix density baseline; use only early-available state/context; retain all exception classes; isolate effect from extra observations, reweighting and teacher information; report proper scores and bulk/upper-error/high-magnitude metrics with event-level uncertainty. Published superiority requires matched independent evidence. This source audit authorizes **no additional fit**.

## Access and reproducibility

- The arXiv v1 PDF/HTML and published institutional PDF were downloaded and hashed. Preprint Figure 1 and published PDF pages 2–3 were rendered and inspected; the conceptual panels match, but figure layout/numbering and supplementary references differ. No blanket version-equivalence claim is made.
- The published 2022 supplement fetch failed. Appendix-specific details above are explicitly preprint-derived. Publisher data availability and a bounded public author-repository inventory did not resolve paper-specific modified code. [TEAM source](https://github.com/yetinam/TEAM) is available, but it does not establish exact 2022 implementation parity.
- Wang and Morad full text was read from identified author uploads with matching article DOI/journal headers; equations rendered as HTML may be imperfect. Direct publisher/downloadable author PDFs failed. Neither missing original PDF is treated as missing all full text; neither paper is inferred from secondary citations.
- [Morad dataset version metadata](https://zenodo.org/records/15499523) is open, published 23 May 2025, DOI `10.5281/zenodo.15499523`, API license `cc-by-4.0`. The cited concept endpoint `14219442` redirects to that version. File names, sizes and checksums only were recorded. No dataset content or accompanying source code was inspected.
- `synthetic_arithmetic.json` contains the invented exact-rational controls. Assertions passed locally; this is mathematical verification, not model testing. No nontrivial implementation was edited and no external code reviewer was invoked for this documentation-only source audit.
- `source_access.json`, download receipts and `manifest.json` separate verified access, failed routes, document inputs and SHA-256 evidence. Large downloaded source files should remain local unless the parent deliberately chooses a licensed source-archival policy; documentation and hashes are the intended promotion artifacts.

# A response-conditioned end-to-end magnitude control

Research/protocol memo, 9 October 2026. **Recommendation: a bounded architecture pilot is justified, after a metadata-only response audit.** The missing comparison is an end-to-end encoder whose nonlinear waveform features depend on the acquisition response, against an equally expressive model receiving exactly the same response information after pooling. This is a useful missing control, not an established novel statistical principle or a claim of better error. Do not train a duplicate scalar-gain-normalized waveform branch.

Scope: local source and existing small result summaries, primary literature, and three StationXML response schemas. No signal arrays, new implementation, training, AWS activity, or model scoring. Source hashes and links are in `sources_and_code.json` beside this memo.

## What has actually been trained

| Existing experiment | Waveform encoder trained? | Sensor information enters waveform encoder? |
|---|---|---|
| INSTANCE independent/sequential/entropy models | Yes; shared compact CNN/GRU, 66-bin density, 1/3/5 losses | No; standardized counts, prefix RMS normalization, retained log RMS/peak |
| INSTANCE affine-prefix controls | Yes; same independent model | No; counts with raw or prefix-affine-projected input |
| INSTANCE future-growth and resolution/distillation | Yes; independent counts backbone plus auxiliary training losses | No |
| Strong instrument, factor, native-summary, growth, proper-score and contextual-reference heads | Only the residual distribution head; historical waveform CNN frozen | No; instrument/site fields and prefix descriptors enter after frozen CNN features |
| Chile TEAM-LM / pooling comparisons | Yes; multistation encoder and Gaussian mixture | Physical waveform input and station geometry; no explicit acquisition-response conditioner |

The inspected INSTANCE independent model has 355,682 trainable parameters. Each deadline re-encodes its complete observed prefix and resets the GRU; weights are shared across deadlines. It is not three independent training jobs. Its convolutional sequence uses per-example GroupNorm and ends in 128 feature channels with mean/max pooling. The 263-dimensional pooled/amplitude/duration input is projected to 128 features.

The strong residual head has 291 slots: 66 centered original logits, 128 hidden features, 51 prefix summaries, 34 static fields, and 12 optional sensitivity-normalized prefix summaries. Its 34 static fields contain family/site, sensitivity, units, calibration frequency, native sample rate and missingness. They do **not** encode poles, zeros, FIR/decimation shape, or phase. The inventory parser currently retains scalar summaries even though the XML contains full stages.

Instrument gains are substantial but not proof of recovered physics: the documented full-TRAIN instrument ensemble has M≥4 record MAE about 0.686/0.551/0.487 at 1/3/5 s. Gain/unit-only and family/site-only sampled controls were close. Almost 98% of validation records use training stations; the validation tail comprises only 13 M≥4 events and one M≥5 event. Static metadata can identify a station/domain. These numbers motivate stronger controls rather than attributing the benefit to response correction.

## Two algebraic traps to avoid

Let a consistently baseline-removed supplied component be q, with positive scalar sensitivity g. If no numerical floor activates, u=q/g obeys

\[
\frac{u}{\operatorname{RMS}(u)}
=\frac{q/g}{\operatorname{RMS}(q)/g}
=\frac{q}{\operatorname{RMS}(q)},\qquad
\log\operatorname{RMS}(u)=\log\operatorname{RMS}(q)-\log g.
\]

The same log shift holds for the peak. Therefore, with the current **per-component** prefix RMS normalization, counts and native-sensitivity waveform branches have identical normalized shape. Only retained amplitudes change. Offset handling, positive gain, component normalization and numerical floors must match; arbitrary global standardization must first be undone or avoided. Compute one shape and native log amplitudes algebraically. Calling two copies independent physical modalities would be misleading.

Also, positive channelwise affine modulation **after the last nonlinearity** commutes with mean/max pooling:

\[
\operatorname{pool}(\gamma a+\beta)
=\gamma\operatorname{pool}(a)+\beta,\qquad\gamma>0.
\]

That placement would be a redundant early/late comparison. Modulate **before a nonlinearity** for the proposed test.

Sensitivity division is not full response removal. Acceleration and velocity have different physical units and spectral meaning; rolloff, poles/zeros and digitizer filters are frequency dependent. Scalar gain cannot convert these to a common physical waveform. Official [ObsPy sensitivity-removal documentation](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.remove_sensitivity.html) treats it as a distinct operation.

## Closest primary work and novelty boundary

- [FiLM, Perez et al.](https://arxiv.org/abs/1709.07871) introduced feature-wise affine conditioning. A response-to-FiLM network is an application of that method.
- [Lee, Lee and Park, 2026 author preprint](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6794461) conditions CNN motion features on site profiles, comparing with concatenation for site-amplification prediction. The abstract explicitly describes channelwise modulation at CNN blocks. Thus even the seismic argument that conditioning can outperform late fusion has close prior art. This is not early source-magnitude inference; the inspected evidence is the author abstract, not reproduced code.
- [ConProSeis, Meng et al., 2026](https://www.sciencedirect.com/science/article/pii/S0952197626016015) uses physics-guided waveform augmentations intended to represent instrumental and attenuation variability, with prototype contrastive learning and magnitude-regression transfer. The publisher abstract, introduction and section snippets were inspected; its exact augmentation code was not. Instrument-invariant seismic representation learning is already an explicit objective.
- [CREIME, Chakraborty et al., 2022](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JB024595), Appendix C, compares raw counts with corrected acceleration, velocity and displacement using a matched cohort. Table C2 reports magnitude MAE 0.49 for smaller-cohort raw training versus 0.44/0.47/0.54 for those physical inputs. Response availability removes roughly a quarter of the original data. Its early-P/window protocol differs from ours; these are prior-art controls, not comparable benchmark scores.
- [TEAM-LM, Münchmeyer et al., 2021](https://academic.oup.com/gji/article/226/2/1086/6223459) already preserves observed-window log amplitude alongside normalized waveform embeddings and learns magnitude mixture densities. [MagNet, Mousavi and Beroza, 2020](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019GL085976) learns magnitudes from raw waveforms without explicit response correction. Neither justifies discarding amplitude or assuming station transfer.
- [D’Alessandro, 2026](https://academic.oup.com/gji/article/246/3/ggag265/8729092) analyzes causal, regularized response inversion, digital stages and response/noise uncertainty. This is a warning against treating scalar gain or an unconstrained neural conditioner as a causal deconvolution. A learned mixture over response uncertainty would also be ordinary nuisance marginalization unless an independently identified uncertainty model and a specific new mechanism were supplied.

The potentially useful contribution is narrow: a finite-prefix distribution encoder using epoch-resolved acquisition-response shape, with native-amplitude controls and verified transfer across acquisition conditions. A positive experiment could support a new EEW method implementation. The current literature search does not establish that this precise design is first, and generic FiLM, physical preprocessing, softmax densities or response augmentation cannot carry that claim alone.

## Metadata that can add information

The existing official `responses.tgz` has 632 XML members. A schema-only probe of three nonempty responses found 6, 6 and 4 stages, including poles/zeros, coefficients, FIR, gain and decimation entries. This establishes availability of the representation, **not** archive-wide completeness or correctness. Previously audited scalar matches cover all components for approximately 99.48% TRAIN and 99.41% VAL; full-stage evaluation needs its own audit.

For an exact station/channel epoch, define a descriptor of the nominal native acquisition response H at fixed frequencies f=(0.5,1,2,4,8,16) Hz:

\[
\rho_c(f)=\left[\log|H_c(f)/g_c|,
\cos\arg H_c(f),\sin\arg H_c(f),v_c(f)\right].
\]

Use a finite-validity mask v, explicit units and calibration metadata. Frequencies at or above 0.4 times native sample rate are masked; this is a conservative sampling restriction, **not** a certified passband. Freeze the grid before outcome inspection. Evaluate all native stages consistently, including stage gains and decimation, and compare a small metadata-only sample with ObsPy/evalresp. Record the exact epoch join, unit convention, inventory SHA, calculation version, validity masks, conflicts and missingness. No dropping unmatched records; use a documented masked fallback. Input normalization uses fit rows only.

This descriptor is real-time available static metadata. It does not use event depth, distance, catalog location, full-trace SNR/PGA/PGV, future maxima or picks beyond the P clock already supplied. A 1 s model can use it immediately to interpret the same amplitude and spectral shape differently for different acquisition chains; it cannot reconstruct rupture that has not been observed.

The [INSTANCE release](https://essd.copernicus.org/articles/13/5509/2021/) has already undergone whole-record mean/trend operations and resampling. H is the **nominal native acquisition response**, not a verified effective transfer function of those later operations. Descriptor conditioning avoids inversion and filter-state problems, but does not certify raw-stream causality. Do not replace this input with the release’s whole-record response-corrected files and call the first second causally corrected.

## One minimal comparison, with a decisive same-input control

Use a fresh compact independent backbone. No original CNN, logits, hidden features, future teacher or event labels enter the input. Every arm uses exactly the supplied [P,P+t) samples at t=1,3,5 s, the same prefix baseline rule, the same amplitude floors and one normalized shape encoder. Prefix demeaning is a reasonable common rule; it must be frozen identically across arms and distinguished from old runs.

All arms receive the same static 34 fields and response descriptor. Keep metadata late-concatenation identical in every arm. The conditioning MLP sees response shape/units/calibration fields, not station identity or site fields. All trainable parameter counts and parameter initializations match.

| Arm | Retained amplitude | Conditioning placement | Purpose |
|---|---|---|---|
| A: counts-late | log count RMS/peak | After pooling | End-to-end counts plus full late metadata baseline |
| B: native-late | log RMS/peak minus log sensitivity; explicit unit/fallback | After pooling | Same-input comparator for C; isolates simple preprocessing from encoder conditioning |
| C: native-conditioned | Exactly B | Before final residual-block SiLU | Main architecture hypothesis |
| D: counts-late + joint gain augmentation | A with coherent training rescaling | After pooling | Ordinary augmentation control, if the four-arm budget is accepted |

More precisely, let z be the 128-channel output of the last residual addition, before SiLU σ. A response MLP produces channelwise γ and β. The paired features are

\[
v_B=\gamma\odot\operatorname{pool}(\sigma(z))+\beta,
\qquad
v_C=\operatorname{pool}\{\sigma(\gamma\odot z+\beta)\}.
\]

Apply the same pair to both pooled mean/max vectors. A positive bounded γ=1+0.5 tanh(a), β=0.5 tanh(b), with the final MLP layer initialized to zero, gives γ=1, β=0 and identical B/C outputs at initialization. Both have the same active parameters and computational backbone. This is conditioning within the last nonlinear encoder block, not conditioning the first convolution or a new filter bank. The modest placement is deliberately falsifiable. A/C amplitude differences are not the main inference; **C versus B is**.

For D, apply q→cq, g→cg and H→cH, with per-component positive c sampled from a prespecified log-uniform range, for example 10^[-1,1], using a separate RNG. This changes the digital representation, not the earthquake magnitude. It leaves H/g and native motion unchanged. Do not use q→cq with unchanged gain and unchanged magnitude: that confounds instrument and source amplitude. Do not add D to already canonical native inputs as a nominally new waveform augmentation; that can cancel exactly. This rescaling is an ideal floating-point representation control, not a simulation of clipping or integer quantization.

Because B/C retain the same 34 fields, including absolute gain, their **whole prediction is not structurally gain invariant** even though their shape/native-amplitude path is. This preserves the strong same-input comparator. Measure coherent-rescaling sensitivity separately; do not advertise an invariance theorem. An exactly invariant design would have to remove or canonically transform every absolute-gain input in both B and C.

Keep the magnitude objective unchanged: weighted Huber of the distribution mean with β=5 high-magnitude weighting plus 0.075 categorical CE, averaged over deadlines. This isolates architecture. It is not a proper scoring rule overall; report ordinary CRPS/NLL separately. Do not add sequential updates, entropy losses or auxiliary future supervision to this pilot.

## Splits, falsification and operational limits

Recommended first scientific split: freeze target-independent event hashes within TRAIN for a new held-event diagnostic, since the existing VAL cohort has been repeatedly examined. Fit the waveform encoder, all normalizers and metadata conditioner from scratch using only the complementary events. A station-transfer subtest should exclude a prespecified station-group hash from fitting as well, treating all channels, locations and epochs at a site together and documenting known aliases. Evaluate seen/unseen stations on the **same held-out events** where coverage permits. Audit event/station/tail counts before launch; do not adjust hashes to improve results or match a desired tail error. A sparse tail makes that transfer conclusion inconclusive rather than a reason to leak held-event waveforms into training.

Use raw released-count prefixes or rebuild fit-only normalization. Reusing a globally normalized cache is acceptable only if its original affine transformation is explicitly and accurately undone before fitting new normalizers; it still is not a pristine raw-stream signal. The old frozen CNN is prohibited in this split. Inventory information known before the event may cross the split; learned waveform/label transformations may not.

Use matched seeds 20261009/20261010, example order, 10 epochs, batch 512, AdamW 3e-4 with cosine decay to 3e-5, decay 1e-4, gradient clip 5 and deterministic CUDA settings. Preserve CUBLAS configuration before CUDA initialization, runtime versions, TF32 flags and full source/data/split hashes. All arms train all deadlines jointly. A sample-limited smoke pilot can verify behavior before the full comparison; its exact population and inclusion weights must be identical across arms.

The decisive falsification is C failing to improve over B. A B-over-A gain alone means sensitivity-amplitude preprocessing helps; it does not establish encoder conditioning. An improvement confined to seen stations, or removed by ordinary joint-gain augmentation, weakens the proposed response-transfer mechanism. If C improves, a subsequent prespecified scalar/unit-only versus full-response conditioner ablation is required to attribute improvement to frequency response rather than unit/family information. Removing/shuffling response inputs only at evaluation is an out-of-distribution diagnostic, not a sufficient matched ablation.

Report both seeds and every deadline: mean/median prediction MAE, MedAE, M≥4 and M≥5 errors, event-macro errors, individual tail-event deltas, CVaR, NLL/CRPS, calibration and coherent-rescaling sensitivity. Use event bootstrap uncertainty and unit/family/seen-station strata. A prospective practical acceptance rule can require improvement of both record and event-macro tail MAE, with bulk MAE/MedAE degradation no more than 0.005; that margin is a proposed protocol choice, not an observed result or guarantee. Do not choose the arm/window after seeing validation outcomes. External data with independently audited response, clocks and magnitude conventions remains necessary.

An ordinary 66-bin density is sufficient for this experiment. The existing support reaches only about M6.55, so even a successful INSTANCE comparison does not demonstrate M7–9 extrapolation. A learned uncertainty mixture over H would add nonidentifiability: a single short record cannot separately determine source magnitude, site/path gain and response error without additional constraints. Do not add that density merely to create a novelty label.

## Cost and next concrete step

The closest measured reference is the deterministic full-TRAIN affine runner’s **raw** arm on one NVIDIA A10G: 511.85 and 510.47 seconds for 10 epochs, all 979,487 rows and all three deadlines per seed. The older non-deterministic independent runs took 419–423 seconds; they are not an exact runtime reference for this protocol.

Estimate 9–13 GPU minutes per full-row model for the small conditioner, or roughly 72–104 minutes for four arms and two seeds. Fifteen epochs would scale that estimate by roughly 1.5. These are extrapolations, not measured benchmarks; a smaller fit split is cheaper and rebuilding/auditing data adds CPU/I/O time. Use the existing GPU and the parent’s verified regional credit accounting; no new instance is required by this plan. Avoid multiplying by three for deadlines.

The 979,487×3×500 float32 TRAIN array is about 5.88 GB. Response/static features add a few hundred MB; the gain-normalized duplicate waveform array is unnecessary. Existing A10G runs already fit the base waveform cache/model. Before a GPU decision, perform only the bounded epoch/stage/units/response-evaluation audit and publish split coverage. If full-stage metadata cannot be interpreted reliably, reduce the hypothesis to unit-conditioned versus late-unit models and state that it tests conventional fusion, not response-shape recovery.

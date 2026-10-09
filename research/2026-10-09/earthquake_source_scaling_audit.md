# Causal waveform shape, source maturity, and self-similar augmentation

2026-10-09. Read-only theory/primary-source check after the negative shared-cap preflight. No code, waveform extraction, or GPU experiment was added.

**Recommendation:** do not generate high-magnitude training labels by stretching the released INSTANCE traces. The operator is physically defensible for a restricted source pulse, but generally not for a recorded trace with fixed propagation and instrument response. The next observable worth a cheap identifiability check is **noise-referenced spectral shape within the available prefix**, beyond the two block-peak ratios. It is measurable, but is not itself rupture maturity or a novel EEW method. Establish an incremental, held-event and held-station signal before constructing another latent-state head.

## What is—and is not—new evidence

Writing a nonzero waveform as amplitude times normalized shape is a lossless reparameterization, not additional data. A full-prefix CNN can in principle already use that shape. The failed contrast models used only two scalar peak changes, however; frequency allocation and phase/polarization structure are not determined by those scalars. Our current 12 native features are RMS, peak, mean-absolute value, and energy-seconds on E/N/Z, not explicit frequency-band statistics.

Amplitude/shape separation is already close prior art: Zhang et al.'s normalized-amplitude magnitude PDF construction and the 2026 INSTANCE paper's pseudo-normalization both preserve an amplitude factor alongside normalized waveform information. Merely adding a separate shape encoder, or shifting a density by log amplitude, does not distinguish a new method. The latter paper's publisher abstract was accessible, but its full method was not retrieved in this check. [Zhang et al., 2021](https://arxiv.org/abs/2006.01332); [An end-to-end deep learning approach for epicentral distance and magnitude determination from single station waveforms, 2026](https://doi.org/10.1016/j.acags.2026.100356).

At one station, let the frequency-domain observation be `Y_i(f)=H_i(f)S(f)+N_i(f)`, where H includes propagation, site and instrument response. If H is unrestricted, `S→C(f)S` and `H_i→H_i/C(f)` leave the noiseless data unchanged. This is an identifiability problem, not something a more flexible latent head solves. Known sensor response removes one part of H; sensitivity alone only removes a scalar. Pre-P noise estimates observational reliability, not the earthquake's path response. Even multiple stations retain a common source/path spectral ambiguity unless physical or historical calibration constrains H.

Likewise, exact **digital-gain invariance** transforms counts and the stated gain together, leaving the physical waveform and magnitude unchanged. **Source-amplitude equivariance** instead changes physical motion. In a linear fixed-geometry source model, multiplying the moment-rate function by c changes Mw by `(2/3)log10(c)` while leaving its duration unchanged; that also changes stress drop rather than preserving constant-stress-drop scaling. It is not a universal relabelling rule for a mixed ML/Md/Mw catalogue. The distinction between amplitude scaling and changes in source parameters is explicitly studied by [Dhulipala, 2023, author preprint](https://arxiv.org/abs/2305.05631); it is not a new augmentation principle.

## Exact source scaling, and why raw-trace stretching fails

[Prieto, Shearer, Vernon & Kilb (2004), §3, equations 3–5](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2004JB003084) explicitly derive the self-similar far-field displacement-pulse transformation under identical source/receiver geometry and no attenuation. A spatial scale b gives moment b³ and pulse height b² with duration b. Their observational support uses clustered small events, spectral stacking and empirical Green's-function corrections; it is not unrestricted large-event relabelling of noisy early traces.

The resulting operators and derivative relations are:

\[
u_b(t)=b^2u(t/b),\qquad
v_b(t)=b\,v(t/b),\qquad
a_b(t)=a(t/b),\qquad
M_{w,b}=M_w+2\log_{10}b.
\]

Thus the amplitude exponent depends on physical units. Applying the same multiplier to HN acceleration and HH velocity is wrong for this scaling. For b≥1, the ideal scaled prefix through t needs source samples only through t/b; this part is causal. A discrete implementation still needs an explicit interpolation kernel, support, initialization and timestamp convention. It must not use a symmetric interpolation/filter support that reaches beyond the available source prefix, nor rescale pre-P noise as though it were source motion.

The following obstruction is our direct algebraic check, not a claim from a new paper. For a fixed linear path/instrument response G and displacement spectrum U,

\[
Y_{\mathrm{physical},b}(f)=G(f)b^3U(bf),\qquad
Y_{\mathrm{stretch},b}(f)=b^3G(bf)U(bf).
\]

Naively stretching the recording changes G too. It moves instrument corners, scattering delays, spectral site peaks, P–S separation, and noise correlation times. Dividing by sensitivity does not fix this. In the prefix setting, windowing introduces another spectral convolution, so even ratios of two truncated spectra do not exactly cancel a shared G. A defensible simulator scales an identified/assumed source **before** applying the same causal observation operator and adding unscaled receiver noise. Unknown path response makes that an approximate simulation requiring external validation, not an exact transformation of these data.

Self-similarity is also not universal across source size and geometry. [Denolle & Shearer (2016)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2016JB013105) analyze 942 Mw≥5.5 thrust events and find size-dependent geometry and spectral shapes despite approximately invariant stress drop/scaled energy. [Shi et al. (2024)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2024JH000220) already use self-similar rescaling for cross-scale phase picking; that is relevant ML prior art, but does not validate magnitude relabelling or early-tail error gains.

## A decisive one-second null

Take a causal growing displacement pulse `u(t)=Ct²` up to an unknown turnover time T. Under the operator above, `u_b(t)=b²C(t/b)²=Ct²` for t<bT. The corresponding velocity and acceleration prefixes are also unchanged. Different final moments can therefore have **identical** prefixes, even under physically correct scaling and a fixed receiver operator. [Juhel et al. (2018), §3.2, equations 2–3](https://www.ipgp.fr/~vallee/PUBLICATIONS/2018_Juhel_et_al_EarlyWarning_PEGS_JGRaccepted.pdf) explicitly use a universal early self-similar moment-rate model of this type as a limiting EEW case.

Relabelling such identical prefixes with larger magnitudes changes the training conditional prior. It cannot create distinguishing evidence. A model that separates them must be using a simulator artefact, metadata correlation, or future information. A correct probabilistic model should remain uncertain. This is a null for that source/nuisance class, not a universal claim that no earthquake can be characterized at 1 second: a short completed event, a departure from universal growth, or informative independent measurements may be distinguishable.

Additional stations can improve location, radiation-pattern sampling, noise averaging, and constraints on station/path effects. At the same network deadline, they do not reveal future emissions shared by none of the received prefixes. A fair network experiment must use the actual samples available at each station at first-network-P +1/+3/+5 seconds; giving every station a full local 5 seconds silently changes the deadline. Catalogue location or all future station triggers cannot be supplied as though known then.

Source-time evidence also does not establish a universal 1-second maturity marker. [Meier, Ampuero & Heaton (2017)](https://doi.org/10.1126/science.aan5643) find scalable, approximately triangular median source-time functions for Mw≥7 subduction events and argue against prediction from rupture onsets. [Melgar & Hayes (2019)](https://pubs.usgs.gov/publication/70205335) instead find useful M7–9 distinctions after roughly 10 seconds. The disputed scope and observation times should accompany any proposed latent “completion” variable.

“Structural fault maturity” is different from how far the current rupture has progressed. [Böse et al., FinDerS(+), 2021](https://www.frontiersin.org/journals/earth-science/articles/10.3389/feart.2021.685879/full) already combine spatially inferred source geometry, displacement backprojection and a geological maturity-gradient/slip relation. Their three large-event playback cases did not speed up calculations by adding low-frequency/maturity information. This is close prior art for physical rupture extrapolation, but neither evidence for a single-station first-second completion classifier nor a reason to equate these two meanings of maturity.

## Nearest spectral EEW methods

- [Caprio et al. (2011), Spectrum Inversion](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2010GL045403) already infer spectral plateau, corner frequency and attenuation from evolving observations, then moment magnitude and uncertainty. The full methods/results were inspected. Their 158 Southern California/25 Japan events span M3–7; clocks reference first network P. Location is treated as known without uncertainty. One-second estimates underpredict, and larger events need longer convergence. Filtering is described after each available window is cut: its acausal Butterworth operation is not, by that description alone, proof of using samples past the deadline.
- [Meier, Heaton & Clinton (2015), Gutenberg](https://www.research-collection.ethz.ch/entities/publication/0614efee-93a6-45c8-8708-980276fa9f2f) already uses a real-time filter bank for joint magnitude/distance posterior estimation, starting at one station and adding stations. Its author-institution abstract reports good 3-second performance but length-dependent magnitude saturation. The abstract, not the complete implementation, was verified here.
- [Ziv & Lior (2016)](https://www.tau.ac.il/~zivalon/papers/ziv_lior_2016.pdf) already estimate moment/corner frequency/stress drop from growing velocity spectra and use a spectral-vs-RMS consistency statistic. Their source PDF shows that the algorithm waits for an S pick and starts with `max(S−P,5s)`; the study substitutes catalogue-distance-derived S−P, and reported closing windows average 27 seconds. It is not a clean first-1/3/5-second P-only competitor. Their quality checks and fixed-path assumptions must not be presented as new if reused.

## One observable and the smallest meaningful next check

The proposed observable is a small vector of **prefix band-energy fractions with separately measured pre-P noise power/uncertainty**. For a predeclared causal filter bank, compute prefix energies `E_b(t)=sum_{n≤t}(h_b*x)_n²` and ratios such as `log(E_b/E_c)` only where supported. Fixed filters run from known pre-P history; do not fit a full-record spectrum or normalize by a later peak. Keep unit/response strata explicit and carry unsupported bands as missing/reliability information rather than interpreting a floor as a source corner. This observes spectral allocation beyond `Z13/Z35`; calling it a resolved final corner frequency or rupture maturity would be premature.

Before a latent posterior model, one small TRAIN-only study should test whether this vector adds held-event information **conditional on** current physical amplitude, the two signed contrasts and sensor/unit metadata. A matched discriminative density control receives those same features directly. Its comparison with a “maturity” head isolates the latent construction; a comparison only to peak ratios would merely show benefit from additional waveform features. Include the current static/full-prefix embedding as the practical baseline, and a held-station/response-family evaluation because station spectral response can masquerade as magnitude information. A stratified feature-permutation control within unit, amplitude and SNR bins tests whether an apparent gain comes only from those marginals. No post hoc band selection on held events is acceptable.

Require a frozen event split, replicated proper-score and tail-error improvement without bulk degradation, and persistence when known instrument response is modeled. The low-frequency feature must disappear or become uncertain when the available prefix/noise makes it unresolved. For 1-second M6+ cases this may be the expected outcome, not a failed feature extractor. Multisite consistency can later strengthen the test, but only among genuinely available station prefixes and with geometry uncertainty retained. A finite-frequency/noise statistic is measurable; an absolute source corner under unrestricted unknown H is not identified.

For any later self-similar augmentation, the **first** falsification is operator-level: compare source-scaling-before-fixed-G against raw-trace stretching under the same source law, noise, labels and sample counts; include amplitude-only and time-only controls, plus the exact universal-onset null above. If raw stretching succeeds but the correct fixed-G construction does not, it is exploiting a nuisance change. Empirical validation must then use unaugmented held events, calibrated physical units and compatible Mw labels. This is a proposed prerequisite, not a completed experiment or a recommendation to launch a broad sweep. None of the reviewed physics justifies treating stretched INSTANCE counts as genuinely observed rare large earthquakes.

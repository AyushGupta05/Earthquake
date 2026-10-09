# Next-method audit: source scaling, finite observation, and sensor nuisance

Research memo, 9 October 2026. Read-only scientific investigation; no AWS jobs, model edits, or TEST waveform access. This follows the censored-innovation pilot and complements the separate nuisance/latent-plateau investigation.

## Decision

**I have not established a new foundational principle.** The most defensible remaining physical experiment is to replace amplitude-only synthetic enlargement with **source-only amplitude–time scaling through a fixed propagation and sensor operator, followed by the actual observation cutoff**. This is a concrete modification to test, not a novelty claim. Its distinctive hypothesis is that retaining the correct instrument response, propagation delays, and fraction of the source observed supplies a better training constraint for the full magnitude distribution than a shifted amplitude PDF or a stretched recording.

Do not launch this as another inexpensive waveform augmentation until a source/propagation generator has been validated. Arbitrarily stretching existing INSTANCE counts would implement a different, generally unphysical operation. A generic hierarchical station distribution, survival head, finer record recursion, or nuisance-invariant encoder does not by itself supply a new principle. The more immediately implementable within-first-second extension is specified separately in `within_second_innovation_design.md`; it must wait for the current censored pilot.

## What the completed results motivate

The two-seed, full-TRAIN instrument runs improve both bulk and rare-event error. These are ensemble-mean decisions; the high-magnitude column is **event-macro MAE for M≥4**, not an M≥6 result.

| Prefix | Base bulk MAE → static instrument | Base M≥4 event-macro MAE → static instrument |
|---|---:|---:|
| 1 s | .39563 → .36534 | .83348 → .65972 |
| 3 s | .34688 → .31588 | .68899 → .51494 |
| 5 s | .31800 → .28619 | .60094 → .44428 |

The sampled factor controls also improve with either gain/unit fields or family/site fields. The prior audit found that station/site descriptors are highly identifying, most VAL stations overlap TRAIN, and most tail improvement comes from HN traces. Thus the evidence supports fixing representation and domain effects; it does not identify instrument calibration as the sole mechanism. VAL contains only 13 M≥4 events and no M≥6 events.

The future-growth conditional-NLL auxiliary worsened bulk MAE at all three deadlines and did not improve the 5 s tail. The full sequential model worsened the tail relative to the independent model at the same seed. Revision-score gains did not replicate consistently. These negative findings argue against adding another unconstrained auxiliary density and calling its gradient physical evidence.

Exact run names, selected metric objects, and SHA-256 hashes of the eight inspected result files are in `source_scaling_evidence_snapshot.json`. These older comparisons predate the newly established deterministic CUDA controls; small differences remain exploratory. The current deterministic affine and censored runs were not evaluated for this memo.

## Primary prior art that narrows the claim

| Source | Verified overlap; remaining distinction |
|---|---|
| [Zhang, Zhang & Tian 2021, DOI 10.1029/2020GL089394](https://arxiv.org/abs/2006.01332) | Normalized waveform inputs and an amplitude-residual magnitude PDF already separate shape and amplitude. Replacing a scalar magnitude with a shifted density is occupied. |
| [Trugman et al. 2019, DOI 10.1029/2018JB017093](https://www.its.caltech.edu/~pagem/EEW_PGD_Saturation.pdf) | Full text, equations 2–6: rupture duration/stress-drop variability determines finite-window displacement saturation; a time-dependent likelihood and GR prior yield magnitude PDFs. A learned saturating amplitude likelihood would extend this model, not introduce its principle. |
| [Münchmeyer, Leser & Tilmann 2022, DOI 10.1029/2022GL098344](https://arxiv.org/html/2203.08622v1) | Partial observations and an unresolved later-rupture tail are already modeled probabilistically. A Gaussian-plus-heavy-tail output is insufficient novelty. |
| [Meier, Heaton & Clinton 2015, Gutenberg algorithm, DOI 10.1785/0120150098](https://www.research-collection.ethz.ch/entities/publication/0614efee-93a6-45c8-8708-980276fa9f2f) | Frequency-band evidence already drives evolving joint magnitude/distance posteriors; the reported estimates saturate with available signal duration. A filter bank plus Bayesian time updating is not new. Institutional abstract verified; causal filter implementation is also documented in the [official USGS project report](https://earthquake.usgs.gov/cfusion/external_grants/reports/G16AC00356.pdf). |
| [Li, Taflanidis & Brewick 2023, DOI 10.1016/j.soildyn.2023.108198](https://www.sciencedirect.com/science/article/abs/pii/S0267726123004438) | Publisher abstract/introduction: station-specific early-Mw regression distributions share hierarchical hyperparameters, addressing local site/path variability and scarce station data. The demonstrated feature is maximum predominant period. Generic station-nuisance marginalization is occupied. Full technical text was not accessible. |
| [Saoulis et al. 2025, DOI 10.1093/gji/ggaf112](https://arxiv.org/html/2410.23238v2) | Full-waveform source inversion already uses simulation-based neural density estimation. Section 6 discusses marginalizing Earth-model and practical instrument errors through simulation. Their task is not strict-prefix EEW, but the general statistical machinery is established. |
| [Alsing & Wandelt 2019, DOI 10.1093/mnras/stz1900](https://arxiv.org/abs/1903.01473) | Nuisance-hardened compression and nuisance-marginalized simulation-based inference are established beyond seismology. Merely projecting out nuisance scores is not a new principle. |
| [Longobardi, Colombelli & Zollo 2025, DOI 10.1038/s43247-025-02814-z](https://www.nature.com/articles/s43247-025-02814-z) | They report magnitude-dependent initial displacement growth and discuss disagreement with universal-onset interpretations. The initial slope is measured over a window defined relative to a fitted plateau, with a shorter-window sensitivity check. An online adaptation cannot obtain that window from the eventual plateau at inference. This result motivates testing early growth, not assuming a universal law or importing their retrospective proxy unchanged. |
| [Zhang & Zhang 2024, DOI 10.1038/s43247-024-01718-8](https://doi.org/10.1038/s43247-024-01718-8) | Their generalized-earthquake training recombines observations and uses partial windows; the magnitude network retains physical amplitude and distance. Large events receive additional random-window samples. This already challenges broad synthetic/generalized-training novelty. It is not the source-only counterfactual below. |
| [Meng et al. 2026, ConProSeis, DOI 10.1016/j.engappai.2026.115317](https://www.sciencedirect.com/science/article/pii/S0952197626016015) | Publisher text explicitly describes physics-guided instrumental/attenuation perturbations and downstream magnitude regression. Generic physics-aware augmentation or transfer representation claims are occupied. Its abstract does not establish matched 1/3/5 s tail-distribution results. |
| [Ma, Li & Wang 2022, DOI 10.1093/gji/ggac215](https://academic.oup.com/gji/article/231/1/692/6605903) | Learned source-spectral models for large earthquakes already exist. A learned source shape is not new by itself; using full-source spectra to evaluate an early prefix without the window operator would be invalid. |
| [Nye et al. 2026, DOI 10.26443/seismica.v5i2.1411](https://seismica.library.mcgill.ca/article/download/1411/4166/39575) | Their FakeQuakes pipeline already combines source, path and high-frequency attenuation terms, causal matched filters and separately added noise. It supplies 112 M6.6–9.4 simulated ruptures at 191 sites for EEW validation. Physics-based synthetic EEW training is therefore occupied; simulation-specific 1/3/5 s behavior still needs validation. |

This is a focused novelty challenge, not a complete systematic review or proof of priority. Search absence cannot certify novelty.

## One testable derivation: change the source, preserve the observing system

Let `s(t)` be a causal moment-rate function, whose integral is seismic moment. Under a point-source, constant-stress-drop self-similar model, a duration scale `λ>0` gives

\[
s_\lambda(t)=\lambda^2s(t/\lambda),\qquad
\int s_\lambda(t)dt=\lambda^3M_0,\qquad
M_{w,\lambda}=M_w+2\log_{10}\lambda.
\]

These are established scaling assumptions, not newly derived earthquake physics. They fail as a universal description when stress drop, directivity, source complexity or finite fault width changes. They also do not license applying Mw label shifts to the current mixture of ML/Mw/Md catalogue targets. For large finite ruptures, use a finite-fault generator and verify its scaling instead of extrapolating this point-source rule without qualification. The parent owns acquisition/audit of the Alaska real-event and Cascadia synthetic data; no acquisition was duplicated here.

Write an idealized recording at prefix deadline `τ` as

\[
x_\tau=R_\tau\{I_s * \partial_t^r[G_\eta*s]+n\},
\quad
x_{\tau,\lambda}=R_\tau\{I_s * \partial_t^r[G_\eta*s_\lambda]+n'\}.
\tag{1}
\]

`Rτ` is the actual causal crop, `I_s` the instrument operator, `Gη` a fixed path/radiation/site operator, and `r=0,1,2` refers to a displacement, velocity or acceleration convention. The derivative convention and instrument response must not be counted twice. Noise should be sampled separately and appropriately for the sensor; source enlargement must not enlarge background noise automatically.

Only for a flat, delay-aligned propagation/measurement operator does the motion reduce to

\[
u_\lambda^{(r)}(t)=\lambda^{2-r}u^{(r)}(t/\lambda).
\tag{2}
\]

Thus even the ideal scaling factors differ across displacement, velocity and acceleration. Multiplying all native acceleration and velocity counts by the same magnitude factor is not this model. Equation (2) also compares a new prefix of duration `τ` with an old prefix of duration `τ/λ`, not with the entire old `τ`-second prefix.

The order of operations matters. For the elementary path `G=δ0+ρδd`, equation (1) preserves the second arrival at delay `d`. Stretching the recorded trace moves it to `λd`. Instrument corners are likewise kept fixed in (1), but shifted by whole-record dilation. This counterexample needs no assumption about a particular earthquake: convolution and source time dilation generally do not commute.

### Full distribution, including the unresolved tail

The honest generative formulation is

\[
L_\tau(x\mid m,s_{\rm meta})
=\int p\{x\mid R_\tau\mathcal H_{s_{\rm meta},\eta}
[s(m,\zeta)]\}\,p(\eta,\zeta\mid m,s_{\rm meta})\,d\eta d\zeta,
\]
\[
p_\tau(m\mid x,s_{\rm meta})\propto
\pi(m\mid s_{\rm meta})L_\tau(x\mid m,s_{\rm meta}).
\tag{3}
\]

Here `ζ` contains source shape/stress-drop uncertainty; `η` contains propagation and unknown site uncertainty. Known gain is a measurement conversion, while uncertain site amplification is integrated or learned under an explicit prior. Catalogue distance, final rupture duration, final source location and held-out event identity cannot be inference inputs. Source-generation parameters may be known for training simulations without becoming available at real inference.

Equation (3) is ordinary nuisance-marginalized Bayesian inversion. The possible contribution is the **specific source-scale/crop constraint and demonstrated real-data advantage**, not normalization by Bayes' rule. A small amortized density-ratio or conditional-likelihood model could implement it; a discriminative model trained on these simulations is a simpler implementation, but then the result is a training-data/regularization contribution. Neither is automatically calibrated on real earthquakes.

Do not enforce a posterior shift as an exact law. Even with an invertible observation transform and matching nuisance/noise assumptions, a likelihood transformation leads to

\[
p(m+\Delta\mid T_\lambda x)
\propto p(m\mid x)\,\pi(m+\Delta)/\pi(m),
\]

with the appropriate change of deadline and support. Prior, magnitude boundaries and noise/SNR changes matter. A pure exponential GR prior has a constant ratio in its interior, but truncation and other priors break this simplification. With noninvertible filtering there may be no deterministic `Tλ` on observed prefixes at all. A label augmentation objective is possible; an unjustified posterior-equivariance penalty is not.

### Essential null: physics cannot create absent information

Take a source with common initial growth `s(t)=c t²` before arrest. Scaling yields

\[
s_\lambda(t)=\lambda^2c(t/\lambda)^2=ct^2
\]

for every time before the relevant arrest/transition. Identical nuisance and noise distributions then give identical early-observation likelihoods for these alternatives. Their posterior odds must equal prior odds. The correct output is uncertainty, not a confident high-magnitude classification. This is a controlled null, not a claim that all natural earthquakes have identical onset; Longobardi and other studies explicitly challenge that universal interpretation.

This also explains why improving rare-event MAE without any bulk cost is an empirical possibility, not a theorem. If our generator creates magnitude information in this null through padding, sensor choice, simulation boundaries, noise power or source family labels, it is leaking the synthetic label.

## Smallest decisive experiment, if the generator passes its checks

Use one shared encoder/density architecture, fixed 1/3/5 s inputs, fixed two seeds and training budget. Fit a proper magnitude score; keep sampling-restoration weights and any operational point-decision rule identical. Do not let a changed synthetic class balance silently become a changed prior. All source seeds, empirical Green functions and calibration records must be TRAIN-only, with grouped source-event splits before augmentation.

Compare five training recipes with the same synthetic count and magnitude support for augmented arms, and identical total optimizer steps. Give the real-only arm matched repeated real draws:

1. Real data only, plus the strongest static instrument baseline as the operational comparator.
2. Amplitude-only enlargement with shifted magnitude labels, the common inexpensive assumption.
3. Whole-record amplitude/time dilation, explicitly an intentionally imperfect physical control.
4. Source-only scaling passed through the same fixed operators and then cropped, equation (1).
5. The same source-only recipe with independently resampled nuisance operators, to test whether pairing or a source–site shortcut drives the effect.

Record actual source-moment integrals, duration scales, sensor units/response, prefix support and noise treatment. Add the identical-onset null above and a two-arrival path example. For fixed digital re-expression `(counts,sensitivity)→(c·counts,c·sensitivity)`, outputs should be unchanged after correct canonicalization. Do **not** demand invariance when only the physical ground amplitude or unknown site gain changes.

Before GPU training, require a held-out-TRAIN simulation check against real **prefix** amplitude, spectral and growth distributions separately by sensor family and Mw band. Exact agreement with full-trace spectra is insufficient. If no credible source/path decomposition or independently validated simulator exists, the candidate is not ready; do not relabel stretched INSTANCE traces as physical source simulations.

The real-data falsifier is failure to beat amplitude-only and whole-record-dilation controls on rare-event macro error **and** the prespecified bulk/median noninferiority margins at each deadline. Also require proper scores, tail bias, false alarms and event-bootstrap intervals. Cross-station/site holdouts must remove entire events from fit when those events are evaluated; same-event different-station records are not independent earthquake generalization. A real large-M external set is necessary for a large-rupture claim. Current reused INSTANCE VAL is exploratory and cannot establish that claim.

## Sensor invariance: necessary controls, no new loss established

The strongest finding supports a plain physical-unit waveform branch as a mandatory baseline. For positive scalar sensitivity `S`, exact invariance `p(cx,cS)=p(x,S)` for every positive `c` implies `p(x,S)=p(x/S,1)` by setting `c=1/S`. Thus every such invariant predictor factors through sensitivity normalization (and retained nongain descriptors). A gain-consistency loss cannot be claimed to encode information beyond this canonical representation. If the architecture already receives only that canonical input, the loss is identically zero except numerical error.

HH velocity and HN acceleration require more than that scalar quotient: different physical units, frequency-dependent instrument responses, integration/derivative noise, and initial filter states must be handled. A causal common-unit conversion or response-aware forward model needs exact epoch response metadata and an explicit pre-P/state protocol. It is not legitimate to call gain division full response removal, or to use a full-record zero-phase inverse to improve an early-prefix benchmark.

For two genuinely different noisy response channels, equal physical motion does **not** imply equal magnitude posteriors. Suppose a controlled degradation `Y` is generated from a richer causal observation `X`, with `M ⟂ Y | X`. For a properly calibrated teacher CDF `T_k(X)=P(M≤m_k|X)`, the valid relation is

\[
F_k(Y)=E[T_k(X)\mid Y].
\]

A squared-CDF distillation loss has this conditional expectation as its population minimizer. This is ordinary conditional-expectation/distillation theory, not a new loss; established antecedents include [Hinton, Vinyals & Dean 2015](https://arxiv.org/abs/1503.02531) and [Lopez-Paz et al. 2016](https://arxiv.org/abs/1511.03643) for distillation across representations. Supervised proper scoring on the same degraded observations has the same correct population target. An advantage can only come from finite-sample regularization or a better teacher; teacher error and same-event reuse can harm it. A lossy channel must not be forced to reproduce each individual richer posterior exactly. HH and HN are not automatically ordered as richer/poorer channels, so arbitrary response swapping does not establish the required Markov relation.

If investigated later, decisive controls are sensitivity-normalized input alone; causal common-unit/response-aware input alone; the same physical degradation augmentation with ordinary supervised proper loss; and only then cross-fit teacher distillation. Keep response/unit flags and available-information differences explicit. The current cost-sensitive static predictor is not a calibrated teacher by default. This pass did not identify a genuinely new sensor-invariance loss that survives equivalence to normalization or known distillation.

## What observed-record extensions can legitimately claim

An observed-record clock could model threshold-crossing times, positive marks and no-crossing exposure from the beginning of the first second. That can retain information lost by the current two scalar increments, and an end-to-end version could change 1 s predictions. However, multiplying conditional crossing/mark likelihoods is standard event-history modeling; using smaller blocks reduces to the current CDF-tied censoring construction with a finer partition. Without a separately tested source-scale constraint it is an engineering extension, not a new principle.

Observed silence means no new **local waveform record**, not rupture arrest. A fitted eventual plateau cannot set the operational window; a future-derived plateau may be a TRAIN-only target but then the method is privileged/future supervision, whose generic form is already known and whose current auxiliary pilot did not provide a robust gain. The uncensored block-peak and same-input discriminative controls remain essential: record censoring discards observable information and has no information-theoretic advantage over retaining it.

Finally, `a=αm+b_site+ε` is invariant under `(m,b_site)→(m+δ,b_site−αδ)`. Arbitrary site-gain invariance therefore also removes the amplitude evidence for magnitude unless an anchor, informative prior or additional identifying measurement is retained. This elementary identifiability argument rules out a broad promise that a nuisance-free representation simultaneously preserves every magnitude cue.

**Recommended claim ceiling if the proposed recipe eventually succeeds:** a validated finite-prefix, source-scale training constraint improves magnitude-distribution transfer and rare-event errors under specified sensor and magnitude regimes. No evidence currently justifies “foundational,” “first probabilistic physics model,” or “better than existing research” without matched experiments.

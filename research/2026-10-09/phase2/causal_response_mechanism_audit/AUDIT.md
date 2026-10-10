# Causal instrument-response mechanism audit

**Decision: no learned or paid fit earned.** A specific untested measurement mechanism remains: the full causal acquisition response with uncertain state inherited from before the available P-wave prefix. A small, no-fit synthetic falsification is defensible because the earlier physical-prefix fixture assumed known initial states. It must compare equal information and retain an exact canonicalization control. Nothing here establishes a new probability principle, natural-earthquake improvement or published-benchmark superiority.

Scope: four existing project documents, primary papers/official documentation and invented arithmetic. No real rows, waves, response inventories or forecast arrays were read. No author code was executed, no datasets or broad source bundles were downloaded, and no implementation, training, AWS action or new resource was created. Changes are confined to this audit directory.

## What remains outside completed controls

The static-feature result used scalar sensitivity, native unit, rate, calibration frequency, channel family and site descriptors; scalar division did not remove the full frequency response. The later four-arm grid supplied nominal full-chain response descriptors and tested early FiLM against equal-capacity late metadata, native amplitudes and coherent gain augmentation. Its fixed criteria failed; maximum error worsened in every panel. It did not apply a full causal transfer function to counts or estimate inherited response state. Thus its negative result does not directly test the proposed observation model.

The physical-prefix preflight already tested exact correlated noise under known causal toy operators and known initial states. It rejected covariance-only expansion. Its explicit limits include absent real responses and unknown baselines/initial states. Repeating full versus diagonal covariance without those distinctions would repeat that rejected experiment. A state-initialization experiment is narrower, not an automatic reason to reopen the method search or train a larger architecture.

The project documents also identify whole-record INSTANCE preprocessing. Nominal StationXML response is not the effective transfer function of that preprocessing. A new physical model on the released cache cannot be described as raw-stream inference without a separate audited observation operator and causal availability proof.

## Primary-source boundaries

Paper-derived capsules are deliberately short; deductions in later sections are our own.

- **Haney et al. 2012, DOI 10.1785/0220120031:** the [primary institutional abstract](https://scholarworks.boisestate.edu/cgiss_facpubs/173/) treats correction as covering seismometer, telemetry, digitizer and anti-alias filters. The [publisher supplement landing page](https://www.seismosoc.org/Publications/SRL/SRL_83/srl_83-5_es_I/) confirms causal-correction prior art. Main full text and linked code were not resolved or executed; no particular initialization formula is attributed to this paper.
- **Anderson and Lees 2014, DOI 10.1785/0220130062:** [author-uploaded primary text](https://www.researchgate.net/publication/274245062_Instrument_Corrections_by_Time-Domain_Deconvolution) gives recursive time-domain correction, digitization-aware coefficients and causal Butterworth stabilization, explicitly discussing EEW. It compares distinct collocated sensors and protects early unclipped phases against later clipping artifacts. Generic causal deconvolution, heterogeneous-sensor equalization and end-artifact avoidance therefore have close prior art. The upload identifies Jonathan Lees and the article DOI; no package was executed.
- **Burky et al. 2021, DOI 10.1785/0220210118:** [author-hosted primary PDF](https://alexburky.github.io/papers/Burky%2B2021b.pdf) presents the linear time-invariant counts/ground-motion model and gain/phase response removal, including SAC-reproducing routines. It supplies a processing reference, not evidence for a new 1/3/5-second magnitude posterior.
- **D'Alessandro 2026 preprint, DOI 10.5194/egusphere-2026-2672:** [primary preprint](https://egusphere.copernicus.org/preprints/2026/egusphere-2026-2672/egusphere-2026-2672.pdf) connects response correction, propagated instrument self-noise, station detection probabilities and network completeness. It uses a stabilized frequency-response expression and a simplified independent-station aggregation. It describes a theoretical detectability framework, not validated prefix magnitude estimation or inherited-state marginalization. Its preprint status and simplifications matter; it is not a performance comparator.
- **Bock, Melgar and Crowell 2011, DOI 10.1785/0120110007:** the [primary author-uploaded abstract](https://www.researchgate.net/publication/258488939_Real-Time_Strong-Motion_Broadband_Displacements_from_Collocated_GPS_and_Accelerometers) combines collocated GPS displacement and accelerometer data with a Kalman filter. This is genuine observation fusion. Its displayed examples include smoothed estimates; no claim of identical causal deadlines is inferred from them. Full methods were not resolved here.
- **Saoulis et al. 2025, DOI 10.1093/gji/ggaf112:** the [primary arXiv abstract/version record](https://arxiv.org/abs/2410.23238) describes probabilistic full-waveform source inversion and shows that simplified Gaussian errors can produce overconfident source posteriors. It is prior art for empirical error inference, not a validation of this audit's Gaussian toy or an EEW timing result. Only the abstract/version record was checked.
- The [Virtual Seismologist's institutional description](https://www.seismo.ethz.ch/en/knowledge/earthquake-data-and-analysis-tools/EEW/Virtual-Seismologist/) already describes Bayesian magnitude/location/shaking inference from earliest picks, amplitudes and prior information. Combining stations and priors is not new by itself.

Official implementation references reinforce the boundary conditions. [ObsPy response removal](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.remove_response.html) documents frequency-domain prefilter/water-level choices and warns of suppression when output differs from the native quantity. [SciPy lfilter](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html) explicitly defaults to initial rest; [lfilter_zi](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter_zi.html) instead constructs a steady-step state, not a measured uncertain seismic state. [filtfilt](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.filtfilt.html) runs forward/backward with edge handling. [StationXML](https://docs.fdsn.org/projects/stationxml/en/latest/reference.html) defines digital-stage delay and applied timestamp correction. A timestamp shifted earlier does not make a sample arrive sooner. These are references, not proposed code to execute.

## Available-prefix observation model: our derivation

Choose one declared physical motion unit and a native sampling clock. A known linear causal response can be written

`x[k+1] = A_R x[k] + B_R u[k]`

`d[k] = C_R x[k] + D_R u[k] + e[k]`.

`u` is physical motion at that sensor, not final earthquake magnitude. Relating it to magnitude still requires a valid causal source/path/site distribution. The response must include relevant digital stages, gains, sample-rate transitions, delays and any known preprocessing. Velocity/acceleration conversion and orientation cannot be silently substituted for scalar gain division.

Stack only samples received by the frozen first-network-P deadline:

`d_≤t = H_R,t u_≤t + O_R,t x0 + e_≤t`.

With valid pre-P context `b`, infer `p(x0|b,R)` before using the new prefix. In an illustrative conditionally independent Gaussian model,

`E[d|M,b,R] = H μ_u(M) + O μ0`

`Cov[d|M,b,R] = H K_u(M) Hᵀ + O P0 Oᵀ + N`.

Cross-covariances must be retained if the conditional independence assumptions fail. Noise units and injection stages must be explicit: physical environmental motion propagates through `H`; noise injected later propagates only through its remaining stages. A single noise term arbitrarily interpreted as both counts and ground units is invalid. Missing, wrong-epoch or unresolved-clock responses fail closed or use an identical mask across controls.

Compute the normalized finite-prefix likelihood, including covariance determinant, and marginalize valid source/path/state nuisance variables. Pre-P context may include earlier events or picking latency, so it cannot automatically be treated as pure stationary noise. State uncertainty must come from available context/TRAIN assumptions, not later event energy. Indistinguishable source prefixes must stay indistinguishable after the response model.

## Invented controls and what they establish

`synthetic_arithmetic.json` records one-off arithmetic with no fitting. Its illustrative response is `y[k]=0.9 y[k−1]+2 u[k]`, with noisy counts and an uncertain boundary state. The toy has one sample per second solely to make the 1/3/5 prefix arithmetic readable; it is not a realistic instrument or sampling rate.

1. **Boundary ambiguity:** with gain one, first count 2.8 can arise from physical amplitude 1 and prior response state 2, or amplitude 2.8 and state zero. A hard reset can misattribute inherited motion. This is an identifiability counterexample, not evidence that real tail errors have this cause.
2. **Equal-information canonicalization ties:** an invertible causal transformation `z=T(d−Oμ0)` with transformed mean and covariance gives `p(z|M)=p(d|M)/|det T|`. The Jacobian is independent of magnitude, so normalized posteriors are identical. All three toy deadlines pass this check. A proper raw-count observation likelihood must not outperform its exact canonical likelihood; such a difference is a bug or changed inputs/assumptions.
3. **Coherent digital gain is a representation change:** scale counts, output response/state contribution and count covariance by `c`, `c`, and `c²`. Likelihood changes by the magnitude-independent factor `c^(−n)` and posterior stays unchanged. Tested scales 0.1, 10 and 100 pass. Changing actual hardware gain can change clipping or quantization; that is a different physical intervention.
4. **Information cannot be recreated:** a difference response maps constant physical histories 3 and 8 to the same output; known metadata cannot recover their DC difference. A pure delay similarly hides the latest motion. Priors can fill those gaps but do not constitute new measurements.
5. **End handling matters:** invented unpadded circular convolution moves a last-sample pulse into the beginning, while causal linear convolution does not. This illustrates a wrong periodic-boundary assumption, not an alleged bug in a named package. Prefix-only forward/backward processing avoids reading beyond its current deadline but can revise earlier outputs when the prefix grows; that differs from a fixed streaming filter with retained state.

The arithmetic verifies identities and falsifies unsafe interpretations. It does not estimate magnitude errors, nuisance prevalence or generalization.

## Minimal remaining falsification, with no learned fit

The substantive extra factor is unknown inherited response state under distinct causal transfer functions; it is absent from the known-state covariance fixture and FiLM grid. A future tiny CPU fixture could predeclare zero/known/unknown boundary states, short/long available pre-P contexts, two stable responses, a DC-null/delay control and identical causal source prefixes. Use the same invented observations and priors throughout. Compare:

- Wrong zero-state physical likelihood, as an explicit failure control.
- Full causal counts likelihood with analytically marginalized state.
- The exact same-input canonical likelihood with transformed full uncertainty; it must tie the preceding arm.
- A plug-in state estimate with its uncertainty discarded, to expose overconfidence.

Require gain invariance, prefix consistency, causal-null equality and agreement with independent quadrature/Kalman algebra before interpreting risk. A proper-score gain over a deliberately wrong reset is insufficient to justify real training. Any subsequent learned test must give the strong discriminative and canonicalization controls the **same full response information and pre-P context**, retain physical amplitude, and match causal bandwidth, masks, capacity, priors and decisions. Adding pre-P context only to the physical arm would add information and confound attribution. Comparing full `R` only to old scalar descriptors would also change information.

No such future fixture is implemented here. The present arithmetic suggests a measurement-correctness question worth bounded falsification; it supplies no evidence that this mechanism achieves the user's joint tail/bulk/worst-error objective. Raw-stream/response availability, event and station independence, and an identifiable magnitude likelihood remain prerequisites. **Zero learned/paid fits are recommended now.**

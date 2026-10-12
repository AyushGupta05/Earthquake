# One bounded causal-count information pilot

Prospective advisory protocol; root must freeze actual support and implementation separately. This packet contains no actual rows, private input pins or run authority. No fit occurred.

## Observation and support gate

Use only the original65TRAIN/DEV selections,41/24, one originally selected queryable station/event. At `T0+h`, `h in {1,3,5}`, crop original samples to `[T0-3,T0+h)` with the unchanged integer-clock and strict-grid rule. The station's local age is `h-(P_station-T0)`; require its frozen accepted pick before the cutoff. No event/station replacement, interpolation, family renaming, rotation, response removal, future station information or catalogue source coordinates at inference. Numbered1/2 remain literal1/2. Native samples, rates, channel identities and metadata missingness must be independently qualified first. Keep counts declared as counts; metadata sensitivity is not full calibration.

The fit cohort requires supported triplets at all three deadlines, unchanged identities, and an independently documented TRAIN/DEV sequence-exclusion rule. Retain all65/195 placeholders; unsupported rows do not vanish. As a **new diagnostic floor**, require>=20TRAIN and>=12DEV, with>=8TRAIN and>=5DEV Mw>=5.5, >=5TRAIN and>=5DEV lower-Mw, and>=3 independent DEV sequence groups containing high-Mw events. Freeze the grouping rule without looking at predictions. These small counts permit a descriptive engineering run only. A failed gate means no fit, no repair/reselection and a retained support report. It does not modify the larger200/30/15 benchmark floor.

## Exact small architecture

For each event/horizon, subtract each component's mean over supported `[T0-3,T0)` samples. Let `a=max(abs(centered_counts))` over only the cropped prefix; set `s=max(a,1 count)`. Supply normalized samples `x/s`, three channel-valid masks and the valid-time mask. Retain `log10(s)` and per-component prefix logRMS, so normalization cannot discard all amplitude information.

One shared sample-domain encoder: three1D convolutions with channels3->8->16->16, kernel sizes9/5/5, stride1, same zero padding, SiLU after each. Apply masks after every layer; pooling uses only supported positions. Concatenate masked temporal mean and maximum for each of16channels, then the four amplitude values and declared context. The convolution is an endpoint statistic on already observed samples, not a claim of a physically causal internal filter. It never receives samples beyond the deadline. Operate at each record's original qualified rate; no sample interpolation. Native sample-rate effects are an engineering limitation; include sample rate/lograte in context and report rate strata.

Context consists only of horizon, station local age, station latitude/longitude/elevation, three channel-family indicators, literal suffix indicators, sample rate, and previously qualified gain/unit descriptor values with missing flags. No stationID/eventID, target magnitude, origin/source coordinates, absolute calendar timestamp, later phase pick or final peak. Standardize continuous context with TRAIN-only mean/std, with constant columns mapped to0. Exact field availability is frozen before fits; use a missing mask for unavailable metadata, never a recovered post-outcome field.

MLP: concatenated vector->32SiLU->15 linear outputs. For `k=1..5`, `pi=softmax(alpha)`, `mu=unbounded linear output`, `sigma=.05+softplus(rho)`. Density `q(m|x,c,h)=sum_k pi_k Normal(m;mu_k,sigma_k²)`. Initialize all means to the TRAIN-label mean, sigmas to max(TRAIN-label std,.1), with small independent seed perturbations of means. Never import cross-scale trained weights as if Mw-calibrated.

Primary inference action is `sum_k pi_k mu_k`. A mean action is not the Bayes action for MAE; retain it solely to match the project convention. Report the distribution median secondarily without switching the primary action. Density scores use stable analytic logsumexp; no log-likelihood floor in the loss beyond the explicit sigma parameterization.

## Three arms, two seeds, one budget

| Arm | Inputs / training target | Purpose |
|---|---|---|
| W | Current cropped waveform, amplitudes, context; true TRAIN Mw | Causal-count engineering baseline |
| M | Same architecture with samples, amplitudes and sample-dependent masks replaced by constants; same qualified-record context/length; true TRAIN Mw | Equal-parameter metadata/rate/geometry baseline |
| P | Same W inputs; one fixed permutation of TRAIN Mw across whole events, reused at every horizon | Gross label/membership leakage and finite-budget null |

M retains native length/rate and predeclared component availability, so its null includes acquisition-support clues; it cannot receive signal-derived valid masks or amplitude. All arms receive only the common fully qualified cohort. The whole-event permutation is seed7919 and has no DEV labels. It destroys waveform-label association and metadata-label association together; it does **not** isolate one nuisance source or provide a formal randomization test.

Seeds20261012/20261013; six fits total. Initialize matched W/M/P tensors identically within each seed. Uniform TRAIN-event batches of8, every event contributes all three horizons and their NLLs are averaged before event averaging. No rare-band weighting or oversampling. Adam learningrate1e-3, no weight decay, gradient norm cap5, exactly300updates, fixed final checkpoint. DEV is never used for tuning/stopping or density calibration. Keep all losses, timings, seeds, final weights and predictions; no failed-fit replacement. Under deterministic CPU execution, cap the whole pilot at30minutes and each fit at5minutes; if those bounds fail, preserve incomplete status and stop. This is a cost proposal, not a measured runtime. It needs no new GPU worker.

Before fitting, verify split/clock/prefix/mask tests, no future-input dependence, deterministic seed replay, logdensity normalization and analytic Gaussian-mixture CRPS on invented examples. Focused tests and required autoreview apply to a later implementation; this authored document is not that implementation.

## Staged falsification and reporting

Stage0: the qualification/sequence gate above. Stage1: one invented normalized-density/mask/clock test and a no-data computational budget measurement; no architecture sweep. Stage2: run all six fits once, keeping1/3/5 as paired outcomes of the same event.

Report per-seed W-M and W-P paired event differences for NLL, CRPS, MAE, MedAE, high-Mw MAE>=5.5/>=6, signed tail bias, CVaR95/P95/max, calibration coverage and all failure/unknown counts. Compute overall-event and lower-Mw summaries separately; neither is a natural-population bulk estimate on this stratified set. Save every DEV prediction for independent recomputation. Public reporting contains only approved aggregate summaries, not actual rows or private hashes.

A **descriptive advance signal** requires W better than M in both NLL and CRPS and tailMAE>=5.5 by>=.02 at all three horizons in both seeds, with no observed degradation in lower-Mw MAE/MedAE or whole-cohort CVaR95/max. W must also beat P in NLL/CRPS; P approaching W flags an uninformative fit or leakage for investigation, not proof of leakage. If any horizon/seed fails, do not launch a method expansion from this diagnostic. No confidence interval here establishes bulk/tail preservation; show sequence-paired intervals descriptively when groups permit and otherwise say unsupported.

If W beats M, finite waveform-model utility is established only for this split/budget. If W does not, one small count-domain model is inadequate or information is weak; distinguish those alternatives in the retained result. A positive result earns separately frozen expanded-cohort baseline work, not a novel architecture claim or a sealed-TEST peek. Compatible-Mw donor transfer remains conditional on a real qualified donor and independent target evaluation.

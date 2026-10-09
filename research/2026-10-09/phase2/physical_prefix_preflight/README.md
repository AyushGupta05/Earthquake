# Causal physical-prefix synthetic preflight

This is a small, locally prespecified correctness and identifiability experiment. It uses no earthquake records, trains no model, and establishes neither novelty nor real EEW improvement. Parent agent owns any repository integration. Files here do not edit a live trainer.

`protocol.json` was fixed before simulation output at 2026-10-09T20:14:16Z. SHA256: `511f8678157e6d36f24ab79a79361755fd61bbc0ca74c2bb8acf528a6e1955a9`. This is a local protocol, not an external preregistration. The runner refuses a changed protocol. No results-dependent settings changes are permitted.

## Source and observations

At 20 Hz, the deterministic, dimensionless source moment-rate is

\[
r_T(v)=\max\{\min(v,T-v),0\}^2,\quad M_0(T)=\int r_T(v)dv=T^3/12,
\quad M(T)=4+2\log_{10}(T/2).
\]

The nine possible durations are 0.4, 0.8, 1.5, 2.5, 4, 7, 12, 20 and 40 seconds. The final magnitude mapping uses an arbitrary reference; this is not a calibrated source-to-ground-motion model. Discrete source probabilities are proportional to `10**(-M)` on that grid, with no bin-width correction. They are applied once per posterior. Source covariance is exactly zero.

The path is a causal one-pole low-pass with time constant 0.12 seconds. A fixed source/path amplitude nuisance takes values 0.7, 1.0 and 1.4 with probabilities 0.25, 0.5 and 0.25, independent of final magnitude. It multiplies only the deterministic signal. The likelihood marginalizes this nuisance exactly; it does not estimate its prior from observations.

Two abstract sensor operators apply to signal and physical noise: sensitivity 2 with 0.08-second low-pass, or causal first difference times sample rate followed by sensitivity 0.4 and 0.06-second low-pass. The names `velocity_like` and `acceleration_like` describe the operators only; these are not response models fitted to real sensors. Every path, sensor and noise state starts at zero, a known initial-state assumption shared by generator and likelihood.

Physical noise is a causal AR(1) process with time constant 0.35 seconds and innovation SD 0.4. It enters after the signal path filter and before the sensor. Independent count noise has SD 0.06. Both laws are independent of source duration and magnitude. The two sensors receive paired innovations, but each posterior uses one sensor alone.

At deadlines 1, 3 and 5 seconds, samples have times `[0, t)`; the last included sample is `t - 0.05`. For `n=20t`, let `B_n` contain the real orthonormal Fourier DC coefficient and four cosine/sine pairs. Let `H_n` be the causal sensor, `P_n` the signal path, and `A_n` the AR noise operator. The observation is

\[
y_n=gB_nH_nP_nr_T[0:n]+\sigma_p B_nH_nA_n\epsilon+\sigma_c B_n\eta,
\]

with covariance

\[
C_n=\sigma_p^2(B_nH_nA_n)(B_nH_nA_n)^\top+\sigma_c^2B_nB_n^\top.
\]

`C_n` is identical across every source and gain hypothesis. There is no final-magnitude-dependent noise scale, terminal moment covariance, fitted covariance, jitter, mean removal or post-cutoff preprocessing. The basis covers different physical frequency grids at different deadlines. This is a complex-spectrum equivalent expressed in real coefficients, not a likelihood for periodogram powers.

## Matched arms and mandatory null

All four arms use the same data, source prior, gain prior and coefficient marginals:

- `prefix_full`: causal prefix mean and full observed-prefix covariance.
- `prefix_diagonal`: same causal mean, replacing the covariance by its diagonal.
- `complete_full`: deliberately wrong mean formed by projecting all 40.5 seconds of the hypothesis signal into the prefix basis; full prefix-noise covariance.
- `complete_diagonal`: same deliberately wrong mean; diagonal prefix-noise covariance.

The complete-template arms intentionally fit unavailable complete-event coefficients to prefix observations. They are a negative control and **not a reproduction of Caprio et al. (2011) or another paper's estimator**. They do not read future *observed* samples, but their likelihood assumes an inappropriate observation operator. Poor performance in that control is not evidence that a published spectral method performs poorly.

Every Gaussian uses its quadratic term, log determinant and `d*log(2*pi)`. Gain marginalization uses log-sum-exp, followed by a stabilized posterior normalization. The determinant is constant across source classes within a fixed arm here, but is retained in the normalized likelihood and tested independently. It cannot be discarded in an extension whose covariance depends on source or nuisance.

For any deadline `t`, all durations `T > 2t` have exactly the same source prefix, because their rise is `v**2`. Their causal observations and covariances are therefore identically distributed. The likelihood ratio between any two such hypotheses must be exactly one, and the posterior **conditioned on that null family** must equal its conditional prior. The total posterior can still move mass between that family and shorter, distinguishable events. The experiment also includes sources that are completed by the deadline and sources with an observed declining phase, so not every hypothesis is null.

The code tests joint numerical unit/gain rescaling `(y, mu, C) -> (c*y, c*mu, c*c*C)`: posterior invariance and the expected density Jacobian `-d*log(c)`. This is an invariance of numerical representation, not a claim that physically changing a sensor's gain while count noise stays fixed preserves information. Different bandwidth, noise and derivative operators need not produce identical posteriors.

## Sampling, metrics and failure criteria

Each of two fixed seeds draws 128 observations per true duration (1,152 per seed); unknown gains follow the fixed nuisance prior. Shared physical/count innovations pair sensors and nested deadlines. The report covers 48 combinations of seed, sensor, deadline and arm. It saves all four normalized log-posteriors, observed coefficients, templates, covariance, labels, nuisance draws and priors in twelve compressed artifacts with SHA256 hashes.

Balanced-duration metrics and fixed-prior-population metrics are reported separately. Population weights reweight the balanced duration sample by the fixed source prior. Nuisance/noise integration remains finite Monte Carlo, not an exact population integral. Reported scores include categorical NLL, exact discrete-distribution CRPS, mean/median absolute error and MedAE, upper-5%-mass CVaR of mean absolute error, discrete 90% interval coverage/width, M>=5 tail mean MAE, and all per-duration values. Conservative coverage is expected from discrete quantiles. The synthetic M>=5 group comprises durations >=7 seconds and has no direct relation to INSTANCE tail support.

Hard failure gates are pinned in the protocol:

- Any causal source-prefix or noise-operator disagreement >1e-12.
- Null log likelihood ratio >1e-10 or conditional null posterior error >1e-12 for either causal arm.
- Magnitude-dependent noise covariance, nonfinite output, or nonpositive covariance.
- Posterior normalization error >1e-12.
- Rescaling posterior discrepancy >1e-11 or density-Jacobian discrepancy >1e-10.
- Simulation time >15 minutes or saved NPZ data >1 GiB.

The complete-template controls are expected to fail the null and record their discrepancy without aborting. After correctness gates pass, full and diagonal causal models are compared at every seed/sensor/deadline. There is no aggregate-only rescue or results-dependent threshold tuning. Any advantage in a generator with known correlated Gaussian noise is constructed. It can motivate investigating whether comparable correlation exists and is estimable causally in real data; it cannot justify a real EEW or foundational novelty claim.

## Reproduce and numerical provenance

Use the existing local research environment from this directory:

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 ../benchmark_research/.venv/bin/python -W error::RuntimeWarning -B -m unittest -v test_preflight.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 ../benchmark_research/.venv/bin/python -W error::RuntimeWarning -B preflight.py --protocol protocol.json --output run_20261009
```

An output path must not already exist. This prevents accidental overwriting. `numpy_matmul_probe.json` records a local NumPy 2.2.6 / macOS Accelerate anomaly: ordinary matmul reported floating exception warnings even when results were finite, identical to explicit contractions and within 1.8e-15 of independent `math.fsum`. The code uses unoptimized `einsum` for matrix products, without suppressing warnings. All tests and the simulation run with RuntimeWarnings converted to errors. Test and code hashes, runtime version and thread settings are recorded. The focused autoreview uses an isolated Git snapshot and the actual bundled Codex CLI; its results are saved alongside the experiment.

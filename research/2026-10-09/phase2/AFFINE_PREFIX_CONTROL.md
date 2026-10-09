# Fully projected prefix benchmark

This is established least-squares nuisance projection applied consistently to an existing magnitude network. It is a correctness/control experiment, not a novel EEW method or certification that the INSTANCE release is causal. Every information-bearing branch is retrained; no original frozen CNN/logits remain.

## Matched experiment

Compare `raw`, `affine`, and optional `affine_guard1` using the existing `MagnitudeDistributionModel(mode="independent")`. All have the same 355,682 trainable parameters, initialization and RNG draws, reset the GRU for each complete prefix, and supervise 1/3/5-second outputs jointly. The shared backbone is independently applied to each deadline; these are not three separately trained networks.

The raw arm delegates to the original forward implementation. Each projected arm separately transforms its 100/300/500-sample prefix **before** `PrefixAmplitudeEncoder`: both normalized waveform and log-RMS/log-peak paths see the transformed samples. Reusing a five-second fit at the one-second deadline would violate this construction and is explicitly tested against.

Defaults match the original independent experiment: all 979,487 TRAIN rows (`max_per_event=10000000`), existing inverse inclusion weights, 10 fixed epochs, batch 512, seeds 20261009 and 20261010, AdamW lr .0003/weight decay .0001, cosine minimum .00003, gradient norm cap 5. Average across deadlines the original loss:

\[
(1+5(M-3.5)_+)\operatorname{Huber}_{\delta=1}(\mathbb E_p[M],M)
+0.075\operatorname{CE}(p,\lfloor M/0.1\rfloor).
\]

Reused INSTANCE validation is monitored at fixed epochs without checkpoint selection. No test inference. The existing validation export supplies only labels, event/trace identities and bin centers; historical CNN logits never enter the model or loss. No teacher, auxiliary target, future waveform, station metadata or instrument response enters this model. Static instrument conditioning is a later separate experiment; these results cannot establish superiority over that stronger baseline.

## Projection and exact scope

For each component prefix of length n, with centered sample time `t_i=i−(n−1)/2`, compute

\[
Q_nx=x-\overline{x}-t\frac{t^T(x-\overline{x})}{t^Tt}.
\]

Accumulate statistics in float64 and return the input dtype. There are no learned parameters or RNG calls. For ideal real-valued affine subtraction, a contiguous prefix satisfies `Q_n R(x−a−b*time)=Q_n R x`. Whole-record affine subtraction alone therefore cannot transmit changed future samples through this representation, up to arithmetic precision. Projection also removes physically meaningful prefix constant/linear components; it does not reconstruct raw amplitudes, and its error cost must be measured.

This is the standard orthogonal-projection identity. The detailed processing audit is in `../earthquake_causal_preprocessing.md`. The [INSTANCE primary publication](https://essd.copernicus.org/articles/13/5509/2021/) describes full-record mean/trend removal and resampling without enough implementation provenance to certify every release prefix.

`affine_guard1` discards the final supplied sample **before** projection, then pads one zero to preserve input length. For a separately established interior, same-rate, even-length, single Hann-resampling operation equivalent to a three-tap smoother with one-sample lookahead, this addresses the last-sample dependence. It retains n−1 values while the tensor length/duration feature remain n through padding. This is an optional conditional control, not a generic resampling/filtering cure. File-edge wraparound, other windows/rates, repeated operations, nonlocal filters and unknown construction order require separate analysis.

Audited sample INSTANCE counts use int32 storage. Quantization after global detrending can preserve non-affine future dependence after Q; the tests deliberately demonstrate this counterexample. Float64 accumulation cannot undo upstream quantization. **Ideal projection invariance and release-level raw causality are different claims.** The cache is not content-hashed by this runner: size/mtime are labeled as a stat, while the existing loader's metadata and target alignment checks remain in force.

## Running after parent scheduling

From the original AWS repository (no jobs launched by this implementation):

```bash
.venv/bin/python research/2026-10-09/phase2/train_affine_prefix.py --control raw --seed 20261009
.venv/bin/python research/2026-10-09/phase2/train_affine_prefix.py --control affine --seed 20261009
.venv/bin/python research/2026-10-09/phase2/train_affine_prefix.py --control affine_guard1 --seed 20261009
```

Repeat all compared arms with `--seed 20261010`. Do not choose an arm or epoch from validation performance. Report both raw-versus-affine seeds and every deadline, bulk MAE/MedAE, M≥4 error with event counts, worst-error tail, and event-macro metrics. Treat the guard as a prespecified extra processing hypothesis. Magnitude-tail claims remain limited by existing validation event support.

Outputs include immutable configuration/source identity, initial/final model hashes, TRAIN row/target/weight hashes and saved row indices, validation identity hashes, each epoch's realized order hash, runtime/backend flags, final model, metrics and predictions. The runner defaults to deterministic algorithms and cuDNN, disables benchmarking, and sets `CUBLAS_WORKSPACE_CONFIG=:4096:8` before CUDA initialization unless a supported explicit setting already exists. A fresh process is required. This deliberately changes the historical numerical protocol: the raw arm is a newly matched baseline, not a promise of matching old predictions. The recorded `--no-deterministic` opt-out must be identical across all compared arms. CPU replay tests verify implementation equivalence; they do not by themselves establish GPU reproducibility.

Focused CPU tests cover exact original raw optimizer replay for both seeds, unchanged parameter/init RNG, horizon and guard gradient isolation, projection before every encoder path, ideal full-record affine/future invariance, the known three-tap guard case, a quantization counterexample, zero-prefix gradients, and a complete runner artifact fixture.

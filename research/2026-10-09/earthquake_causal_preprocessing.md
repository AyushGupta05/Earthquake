# Conditional rehabilitation of released seismic prefixes

Audit date: 9 October 2026. This is a mathematical and source audit, not a new magnitude-prediction method. No GPU jobs, model edits or waveform-data mutations were performed. Synthetic tests use an isolated local environment. The population diagnostic reads the previously verified TRAIN/VAL station-metadata export and public inventory. Small HDF5 format descriptors, shapes and attributes were inspected for six verified INSTANCE TRAIN examples and one Chile TRAIN event; no real waveform values or TEST waveform values were accessed.

## Finding

**A prefix linear projection exactly removes contamination caused solely by subtracting a whole-record affine trend.** Prefix demeaning alone only removes a whole-record constant. The result is an elementary projection identity, not a novelty claim. It does not automatically rehabilitate a record that was subsequently filtered, resampled, tapered, clipped or quantized.

There is a useful conditional exception: in the inspected ObsPy implementations, same-rate Fourier resampling with the default Hann window and an **even input length** is exactly a circular three-tap smoother. Away from file boundaries, dropping one last output sample before prefix linear detrending gives a causal smoothed-prefix representation, including after global affine detrending. This was verified analytically and numerically. Neither available dataset description establishes that all its records used this exact sequence, so neither entire release can currently be certified by this argument. Moreover, all six inspected local INSTANCE TRAIN records are stored as int32: quantization is an additional obstacle to an exact identity on the stored arrays.

## 1. Projection identity and its scope

Let `x ∈ R^N` be one unprocessed component and let `B_N=[1,u]` span constants and sample time. For full-record least-squares linear detrending,

\[
D_N=I-B_N(B_N^TB_N)^{-1}B_N^T.
\]

Let `R` select an available, contiguous interval of `m` samples, possibly starting at a P pick rather than record index zero. The restricted columns `R B_N` span the same affine subspace as `B_m=[1,v]`. Therefore `D_m R B_N=0` and

\[
\boxed{D_m R D_N x=D_m R x.}
\]

If two raw records agree on every available sample but differ arbitrarily afterward, their rehabilitated prefixes are identical in exact arithmetic. No knowledge of the removed full-record intercept or slope is required. More generally this remains true for *any* subtraction `x−B_N a(x)`, even when the coefficients are nonlinear functions of the complete record. Thus ObsPy's endpoint-based `simple` detrending also qualifies: its removed function is affine. A discontinuous piecewise trend or spline needs the appropriate larger nuisance space, not merely two columns. [SciPy detrend](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.detrend.html), [pinned ObsPy detrend dispatch](https://github.com/obspy/obspy/blob/a629e8c021052904b6b8d62699d03f2a3721ae63/obspy/core/trace.py#L1971).

For centering `C_m=I−11^T/m`, `C_m R C_N x=C_m R x`. But if `D_N x=x−a−bu`, then

\[
C_m R D_Nx=C_m Rx-b\,C_m Ru,
\]

so the full-record slope, potentially determined by later strong shaking, survives prefix demeaning. The existing prefix-demeaned features therefore cannot by themselves certify removal of released global linear detrending. Every information-bearing branch, including a frozen backbone, must receive the rehabilitated representation for a model-level invariance claim. Correcting only a side branch leaves any original contaminated logits intact.

This operation recovers **the raw prefix after its own linear projection**, not the original waveform. It sacrifices the prefix's own constant and linear components, which can carry physically useful long-period/growth information. It is causal at the forecast deadline, although it can revise how earlier samples are represented as that deadline advances. Refit/compare all model arms under the same convention and report any magnitude-error cost.

### Integer-storage qualification

An attribute-only check of six verified TRAIN examples in the locally mounted `/data/Instance_events_counts.hdf5` found `int32[3,12000]` arrays. They span advertised native rates 100/200/125/80/50/0.1 Hz. Root, data-group and those trace attributes are empty; `data_format` confirms counts, ENZ components and no restituted instrument response. This establishes these local examples' storage type, not the exact rounding stage or the dtype of every official-release version. The checked original Chile TRAIN event uses float64 and likewise has no processing attributes. JSON inspection records are preserved.

If stored `y=quantize(D_N x)=D_Nx+e`, then

\[
D_m R y=D_m Rx+D_m Re.
\]

The residual rounding error need not be affine and can depend on the future through the globally fitted trend. Conditional on nearest rounding with quantum `q`, no clipping/overflow, and no further transformation, `||e||∞≤q/2`. Since an orthogonal projection is nonexpansive in L2, the error RMS relative to the projected raw prefix is at most `q/2`; between two equal-raw-prefix/different-future records it is at most `q`. Truncation toward zero gives bounds `<q` and `<2q` instead. These are conditional bounds, not an assertion about the unknown actual writer. Normalizing to physical units rescales them only when the instrument gain is known and fixed.

The synthetic unit-rounding experiment retains approximately .40–.41 count RMS of future dependence despite the affine projection. Therefore use **bounded or reduced dependence**, not exact causal certification, for quantized data unless the relevant transformation and tolerance are explicitly established. Small absolute error is not proof a model cannot exploit it. Quantization before any affine processing is different from quantization after it; source provenance decides which argument applies.

## 2. What the primary sources actually establish

| Dataset/stage | Verified evidence | Remaining gap |
|---|---|---|
| INSTANCE counts | Paper §2.1.5 lists 120 s windowing, mean/linear-trend removal and resampling to 100 Hz. | Construction code, exact detrend option/order, resampling API/window/version, same-rate bypass, original sample counts and original MiniSEED rates are not pinned by the publication. |
| INSTANCE ground-motion release | Paper §2.1.6 additionally describes response deconvolution, frequency taper corners .01/.04/25/40 Hz and a 5% end taper. | Prefix linear detrending cannot generally remove that full-record frequency processing. The present project uses counts, so these extra steps should not be attributed to its input. |
| TEAM Chile release | Official description gives 100 Hz ZNE velocity, sensitivity correction without full response removal, and a common −5 to +25 s interval around the first network P arrival. | Native acquisition rates and the exact operations before export are not given. Do not infer a filter from the filename `chile_filtered.hdf5`. |
| TEAM public reader/generator | Pinned loader reads waveforms directly; optional sample-rate override is strided slicing. Its event generator performs prefix demeaning and zeros the suffix. | These are operations after release construction. They do not prove how the released HDF5 was created. |

Sources: [INSTANCE publication](https://essd.copernicus.org/articles/13/5509/2021/), [official Chile description](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2021.002noeUVRE/2021-002_Muenchmeyer-et-al_data-description.pdf), [TEAM loader at pinned commit](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/loader.py#L99), [TEAM event generator](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/util.py#L246).

The entire public [INGV/instance tree at `95dc7e4933feade5e5d05482c4fbb3785ef9014a`](https://github.com/INGV/instance/tree/95dc7e4933feade5e5d05482c4fbb3785ef9014a) was inspected. It contains release links and exploratory plotting notebooks, not the dataset-construction pipeline. `Def_plot_waveform.py` reads existing HDF5 records and optionally detrends/bandpasses them for plotting. That is **not evidence those optional plotting operations created the released counts**. The tree and relevant files are pinned locally. This is a scoped finding about the inspected repository, not proof no construction code exists elsewhere.

The [TEAM tree at `8df20877f3a6ef47d3af4d1484ecdb0cdf37e903`](https://github.com/yetinam/TEAM/tree/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903) and [official v1.0 source archive](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2021.003oeucb/2021-003_TEAM-v.1.0.zip) contain Japan extraction code and no Chile construction script identified in either file inventory. The archive SHA256 is `f645cc615ba303afb6a42f1c390bd6983bac0d810bc1a6c9962de8cb6d5de80b`.

TEAM's `resample_trace` helper is explicit: skip an already equal rate; otherwise use `Trace.decimate` for integer factors and `Trace.resample` for other ratios. The inspected ObsPy decimation uses a forward Chebyshev-II lowpass and striding, so it is causal as an operation on its supplied stream. Calling this helper on two identical raw prefixes with different futures preserves the prefix in synthetic tests. **We have not established that this helper produced the Chile release.** [Pinned helper](https://github.com/yetinam/TEAM/blob/8df20877f3a6ef47d3af4d1484ecdb0cdf37e903/util.py#L23), [ObsPy decimation](https://github.com/obspy/obspy/blob/0f79f5580ab4cff69c6d4873d56bdb24d5800f2d/obspy/core/trace.py#L1758), [forward filter implementation](https://github.com/obspy/obspy/blob/0f79f5580ab4cff69c6d4873d56bdb24d5800f2d/obspy/signal/filter.py#L353).

The original TEAM generator centers `:cutout+1` and then zeros from `cutout`, exposing one sample beyond its retained interval through the mean. Our current port already uses the strict `:cutout` convention. That is a separate, source-verifiable boundary issue; fixing it does not establish the release-construction pipeline.

## 3. Same-rate ObsPy resampling is not a no-op

Source inspected and hashed:

- ObsPy 1.2.2, commit `0f79f5580ab4cff69c6d4873d56bdb24d5800f2d`, 29 June 2020: [`Trace.resample`](https://github.com/obspy/obspy/blob/0f79f5580ab4cff69c6d4873d56bdb24d5800f2d/obspy/core/trace.py#L1638), default `window='hanning'`.
- ObsPy 1.4.2, commit `a629e8c021052904b6b8d62699d03f2a3721ae63`, 30 April 2025: [`Trace.resample`](https://github.com/obspy/obspy/blob/a629e8c021052904b6b8d62699d03f2a3721ae63/obspy/core/trace.py#L1645), default `window='hann'`.

Neither implementation returns early for equal rates. Both transform with `scipy.fftpack.rfft`, multiply by an `ifftshift(get_window(...))` frequency window, interpolate the real/imaginary spectral arrays with `numpy.interp`, and inverse-transform. This is their inspected implementation; do not assume it is simply the current `scipy.signal.resample` function. `no_filter=True` disables an additional automatic lowpass; it does **not** disable the spectral window.

For an even `N`, unchanged rate, no extra filter, and the periodic Hann default, the spectral multiplier is

\[
W_k=\tfrac12+\tfrac12\cos(2\pi k/N),
\qquad
(H_Nx)_j=\tfrac14x_{j-1}+\tfrac12x_j+\tfrac14x_{j+1},
\]

with circular boundary indices. [SciPy get_window defines the periodic default](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.get_window.html). The result is **not identity**, but away from file edges it needs only one raw future sample. At a strict cutoff `b` with raw indices `<b` available, discard released output `b−1` before computing any normalization/projection. If the left edge includes record index zero, discard that wrap-contaminated sample too. The remaining outputs are causally computable from past/current raw samples; equivalently this smoothing has a one-sample delay at 100 Hz. A P-aligned interior interval also uses one pre-P raw sample, which is past context and must be disclosed.

On an interior interval, `H_N` preserves affine functions, so with this guard `G`,

\[
D_{|G|}G H_N D_Nx=D_{|G|}G H_Nx.
\]

Discard the boundary sample **before** prefix detrending: otherwise its future contribution spreads across all samples through the fitted trend. Using the last sample and merely zeroing it afterward does not repair that dependence.

Conditions matter. Odd input lengths do not produce this exact three-tap formula in the inspected real-spectrum implementation. Unequal-rate Fourier resampling generally has nonlocal dependence. The original processing length must be known; a final 12,000-sample array does not prove an earlier FFT had even length or skipped earlier filtering. `window=None` at equal rate is identity to numerical precision, but it must be established that this was the call used. Repeated same-rate Hann passes increase the required guard; another window changes the kernel.

## 4. Filters do not generally commute with this repair

For known linear processing `A` after detrending, the whole-record nuisance becomes `A B_N a`. A projection `Q` annihilating `R A B_N` gives

\[
Q R A D_Nx=Q R Ax.
\]

If `A` is causal, the right side is causal, but ordinary affine detrending need not equal `Q`: filter startup transients can transform an affine input into a non-affine waveform. Synthetic tests below exhibit that failure and verify the appropriate filtered-basis projection. Its use requires the exact operator and initial-state convention. This is standard linear nuisance elimination, not a novel EEW architecture.

If `E_+` injects unobserved future samples, strict invariance additionally requires

\[
\boxed{Q R A E_+=0.}
\]

General Fourier resampling and forward–backward filtering fail this condition after a two-dimensional affine projection. A finite guard may bound a known finite-support kernel; an arbitrary guard is not an exact proof for an IIR or sinc kernel. Some known invertible full-record operators could in principle be inverted offline, but that is a different construction requiring full operator/boundary provenance and stable access to information absent from the prefix. Downsampling, frequency zeros, clipping and quantization can remove information. Do not label all filtered data universally irrecoverable, or promise that a prefix projection reconstructs it.

A deterministic taper is similarly not an affine subtraction: it changes the nuisance basis and may erase values at zeros. Unknown full-trace amplitude normalization is multiplicative, so removing an affine component does not recover physical amplitudes. Fixed TRAIN-derived mean/std constants are different: they are available before a new event and can be accounted for without consulting that event's future.

## 5. INSTANCE inventory-advertised native rates

The exact prior station/epoch join was rerun on the unchanged 979,487 TRAIN and 96,993 VAL metadata rows. This uses the official inventory archive, not MiniSEED header evidence:

| All E/N/Z advertised rate | TRAIN records | VAL records |
|---|---:|---:|
| 100 Hz | 720,809 | 72,337 |
| 200 Hz | 136,916 | 19,222 |
| 125 Hz | 102,257 | 4,809 |
| 80 Hz | 2,380 | 52 |
| 50 Hz | 12,022 | 0 |
| 0.1 Hz (suspicious inventory value) | 3 | 0 |
| E/N unmatched, Z 100 Hz | 5,100 | 573 |

Thus 73.590% of TRAIN and 74.580% of VAL have complete advertised 100 Hz responses. These are **candidate same-rate rows**, not a causality-certified subset. The three 0.1 Hz records belong to IV.CDCA.EN; do not treat that implausible value as proof of its actual waveform acquisition rate. Original headers and processing logs are necessary. Missing horizontal matches are the previously identified IV.GIGS historical naming case. The output retains an exact example trace per pattern and input hashes in `instance_inventory_rate_audit.json`.

The Chile HDF5 metadata verified earlier contains only `sampling_rate=100`, `time_before=5`, `time_after=25` plus event metadata; event arrays contain waveforms, station names and coordinates. It does not supply original rate/channel or per-trace processing history. Provider inventory queries alone would not prove which native traces or resampling path populated this release. Exact historical native rates for every Chile record remain unverified here.

## 6. Synthetic results

`check_causal_preprocessing.py` uses Python 3.10.20, NumPy 1.26.4, SciPy 1.13.1 and installed ObsPy 1.4.2. It also executes only the inspected AST-extracted 1.2.2 resample method, with explicit `window='hann'` replacing the historical alias spelling unsupported by modern SciPy. Results verify the algorithm under the present numerical libraries, not a complete binary reproduction of the old environment.

| Check | Maximum absolute difference or remaining response |
|---|---:|
| `D_t R D_full x` versus `D_t R x`, 1/3/5 s | ≤1.06×10⁻¹⁴ |
| Same available raw prefix, huge modified future, then both linear detrends | ≤2.61×10⁻¹² |
| Prefix demeaning fails to remove whole-record slope, 1/3/5 s | .2476 / .7478 / 1.2480 |
| Float32 quantization after global detrending, residual versus projected raw | ≈0.9–1.2×10⁻⁷ in this fixture |
| Nearest-integer quantization after global detrending, changed-future RMS | .40–.41 counts remains; conditional unit-rounding bound ≤1 count |
| Same-rate even Hann versus exact circular three-tap convolution, both ObsPy versions | 1.12×10⁻¹⁵ |
| Unit future impulse at cutoff, last available output | .25 |
| That impulse after prefix linear detrending without guard | .24668 |
| Guard first, then detrend | 4.46×10⁻¹⁷ |
| Global-linear → same-rate-even-Hann → guard → prefix-linear, future changed | 7.12×10⁻¹³ |
| Odd-length same-rate Hann, one-sample guard and linear projection | 1.25×10⁻⁶ remains |
| 200→100 Fourier resampling, same guard/projection | .03158 remains |
| Causal IIR after global detrending, naive prefix-linear projection | 1600.21 remains in deliberately amplified fixture |
| Same IIR, correct filtered nuisance basis | 2.99×10⁻¹² |
| Forward–backward lowpass, prefix-linear projection | .09494 remains |

These are controlled algebra/kernel demonstrations, not estimates of contamination or predictive-error inflation in real earthquakes. No magnitude labels or real waveforms enter them. Float precision and operator norms matter: rounding noise caused by a removed large trend is not necessarily itself affine, so the exact real-arithmetic identity becomes approximate on stored finite-precision arrays.

## 7. Recommended benchmark action

1. Add a **matched affine-projected input control** for every model path and deadline, with prefix-only normalization afterward. Call it an affine-invariant released-data benchmark while source resampling remains unresolved. It can improve causal defensibility without certifying the entire release.
2. Establish raw processing provenance for a small TRAIN-only set before promoting a same-rate subset: original native rate and length, full operation sequence, method/version/window, precision, boundaries and trim order. Compare original raw processing against released values. Do not infer the pipeline from a matching histogram or almost-zero full-record mean.
3. If the even-length, same-rate, single-Hann pipeline and relevant storage precision are confirmed, preregister the one-sample guard **before** detrending, account for file-edge wrap and pre-P context, and report the 0.01 s representation delay. Apply the same restriction to baseline and proposed methods. For quantized inputs, report a conditional dependence bound instead of an exact identity. Quantify retained event/tail support and selection shifts.
4. For records with other/unknown rates, zero-phase filtering or deconvolution, obtain original continuous data and apply an explicitly causal streaming pipeline, or retain the records only under a clearly labeled released-data benchmark. Affine projection alone is insufficient.
5. Separately report catalogue P alignment, future-informed record/quality selection, event split and station availability. Waveform projection removes none of those benchmark assumptions. Keep TEST sealed while developing this protocol.

Exact source commits, downloaded-file hashes and archive inventory are in `preprocessing_sources/source_manifest.json`; synthetic source/runtime hashes and measurements are in `causal_preprocessing_checks.json`. Inventory audit inputs are the same archived response SHA `71eccc6304afad15e9c45534ca374b4b4f974c9f93ccfc0f2683616ee6421ef2` and station export SHA `1a7f1df9d5d3553b38c333adb240d87f94aea607c178d80e30f511e3d9e31f82` used in the instrument audit. All revised synthetic assertions passed. The final focused Codex autoreview of both scripts and the memo, including integer-storage and conditional quantization bounds, was clean with no actionable findings (`causal_preprocessing_review_result.json`). Review was static; the synthetic checks and inventory aggregation were executed separately.

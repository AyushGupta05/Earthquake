# Rapid strain source causality audit

The suspected whole-record demeaning path does **not** establish a future-data leak through the documented CSV lineage for a complete finite trace. The missing middle script subtracts the baseline before the feature filter, canceling the future-dependent constant in exact arithmetic. This rejects the initial shortcut-based suspicion; it does not certify the published experiments or every missing-data path.

All four source files are pinned to [author commit 7106f9b52d15a7b911489c893af719627b55d2d3](https://gitlab.com/tsawi1/rapideqmag/-/tree/7106f9b52d15a7b911489c893af719627b55d2d3/scripts/mtj_borehole/src). The original three files and manifest remain byte-identical. The additional public script was downloaded once, 9,884 bytes, with a 500,000-byte cap and 20-second request timeout. No author module was imported or executed. No actual strain traces, earthquake catalogues, picks, models, predictions or AWS resources were accessed.

## Verified source lineage

| Source | Relevant lines | Source-derived finding |
|---|---:|---|
| [01_Load_BSM_Waveforms.py](https://gitlab.com/tsawi1/rapideqmag/-/blob/7106f9b52d15a7b911489c893af719627b55d2d3/scripts/mtj_borehole/src/01_Load_BSM_Waveforms.py) | 70–72, 193–225 | Requests an origin-centered 80-second record; calls `Linearize` with nanostrain scaling disabled; merges then saves linearized channel miniSEED. Its output directory matches the next script's input. |
| [functions.py](https://gitlab.com/tsawi1/rapideqmag/-/blob/7106f9b52d15a7b911489c893af719627b55d2d3/scripts/mtj_borehole/src/functions.py) | 94, 126–151, 318–354 | Count-to-strain conversion is samplewise. The missing-value, scaling and demeaning blocks are outside the trace loop, so they act on its final trace in this version. Demeaning uses that trace's whole-record finite-value mean. The CWT helper transforms the supplied block. AST inspection independently confirmed the indentation. |
| [02_PickP_STALTA.py](https://gitlab.com/tsawi1/rapideqmag/-/blob/7106f9b52d15a7b911489c893af719627b55d2d3/scripts/mtj_borehole/src/02_PickP_STALTA.py) | 123–126, 219–255 | Reads the linearized miniSEED, interpolates missing values, subtracts the first200-sample mean, and writes this interpolated **unfiltered** array to CSV. A separate filtered array supports picking. The saved unfiltered directory exactly matches the feature script's input. |
| [03_ExtractFeatures.py](https://gitlab.com/tsawi1/rapideqmag/-/blob/7106f9b52d15a7b911489c893af719627b55d2d3/scripts/mtj_borehole/src/03_ExtractFeatures.py) | 178–184, 218–274 | Reads that CSV, high-pass filters with `lfilter`, subtracts the filtered first200-sample mean, then restricts the record to ten seconds before and four after the P pick. CWT windows operate inside that restriction. These scripts show a source path, not a verified hash chain for the actual arrays used in the paper. |

The listed directory templates use the same network, station, channel and date settings. This establishes the intended 01→02→03 source connection; actual generated files and execution history were deliberately not inspected.

## Algebra: the omitted middle operation matters

For a single complete trace per channel, let `s` denote a finite, already samplewise-converted record of length N; let `mu_N(s)` be its whole-record mean and `mu_B(s)` its first-B mean. For the affected channel the first stage gives `u = s - mu_N(s)`. The unfiltered CSV stores

`v = u - mu_B(u) = s - mu_B(s)`.

The whole-record constant therefore disappears **before** any filter state is created. If two records have identical observed prefixes containing the baseline, their resulting CSV prefixes coincide in exact arithmetic even when their future suffixes differ. A causal filter with fixed initialization, followed by subtraction of a mean from an already-observed baseline, preserves that equality. For complete traces that were not globally demeaned, direct baseline subtraction yields the same result.

This assumes one complete finite trace per channel, an observed baseline and matched samplewise conversion. For fragmented streams, the final-trace-only demeaning followed by merging can create piecewise offsets; the single-constant proof then does not apply automatically. No fragment or gap inventory was inspected. Interpolation, rounding and retrospectively chosen picks also remain outside this proof.

If the prefilter subtraction is omitted, the output difference can instead be

`delta_z[n] = -delta_mu_N * (g[n] - mean(g[:B]))`,

where `g` is the causal filter's zero-initial-state response to a constant input. A high-pass has zero steady-state DC gain, but its finite step response generally varies. A later baseline subtraction does not erase this transient. This explains why inspecting only the first and third scripts gave the wrong suspicion for the documented path.

## Own finite-array counterexample and negative control

The exact rational illustration uses `s_a=[0,0,0,0]`, `s_b=[0,0,0,8]`, an identical observed prefix of three samples, baseline B=2, and our illustrative high-pass recurrence `y[0]=x[0]`, `y[n]=x[n]-x[n-1]+y[n-1]/2`. These are invented values, not strain data or an author implementation.

With whole-record centering, filtering, then baseline centering, the outputs are `[0,0,0,0]` and `[-1/2,1/2,1,37/4]`: the third observed output changes by exactly1 because of an unobserved suffix. Adding baseline centering **before** filtering gives `[0,0,0,0]` and `[0,0,0,8]`; their observed prefixes agree exactly. Both assertions passed using Python `Fraction` arithmetic.

A separate finite numerical illustration used NumPy2.2.6/SciPy1.15.3, 1,600 samples at20Hz, baseline200, invented P sample800, exclusive deadline880, and a unit suffix starting at880. Using the published filter parameters in our own arithmetic, omitting the middle subtraction changed the earlier filtered prefix by up to0.23434017233120305. Including it left a maximum residual5.781560221407152e-17. The initial bitwise-equality demand failed and is retained in [finite_counterexample.json](finite_counterexample.json); exact cancellation is algebraic, while floating-point subtraction carries rounding. These examples do not measure predictive error or identify actual affected paper records.

## Filter units and remaining bounds

With an explicit sampling frequency, SciPy interprets `Wn` in the same frequency units. Thus the feature script's supplied value `0.01/(20/2)` means a critical frequency of **0.001Hz**, rather than the named0.01Hz setting. This is a source-level units discrepancy, not a measured explanation for its accuracy. [SciPy butter documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.butter.html) defines these units; [lfilter documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.lfilter.html) specifies initial rest when no state is supplied.

Full-record linear interpolation remains a **conditional** concern: filling an observed missing interval can depend on a valid sample later than a deployment deadline. The documented default interpolation is supported by [pandas documentation](https://pandas.pydata.org/docs/reference/api/pandas.Series.interpolate.html). No gap inventory was read, so its occurrence and effect here are unknown. Merging with interpolation and manual picks similarly require their own real-time provenance before an operational latency claim.

A transform computed exclusively from the record available at P+4 is compatible with a four-second information boundary, including its earlier baseline. That does not authorize reuse of those same features at P+1 or P+3: earlier deadlines require recomputation from their own available prefixes. We have not reproduced any saved feature, classifier, training split or performance result.

## Research consequence

Do not cite a demonstrated global-demean leak in this paper. Do retain this rejected hypothesis, the verified missing source stage and the0.001Hz interpretation. Any future feature transfer should preserve samplewise calibration, observed-baseline subtraction before filtering, causal filter state, and deadline-specific transforms; gap handling and P-pick availability need explicit checks. This audit earns no GPU experiment and no novelty or published-benchmark superiority claim.

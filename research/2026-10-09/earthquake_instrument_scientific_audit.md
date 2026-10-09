# Scientific audit of the INSTANCE instrument-feature result

Audit: 9 October 2026. Scope: original TRAIN and reused exploratory VAL only. No TEST metadata/waveforms were read. The three fitted instrument models were not changed or retrained by this audit. Metadata and existing predictions were exported read-only from AWS; CPU diagnostics preserve source row, event and trace identity. Statistics below compare the two-seed ensemble mean decisions for matched `base` and `instrument` heads.

## Assessment

The improvement is substantial and internally consistent as an **exploratory gain from adding static station/instrument metadata to the existing counts-based model**. It survives averaging errors within events and omitting any one of the 13 larger validation events. The audit found no event magnitude, magnitude type, source location/distance, future waveform statistic, or explicit station identifier in the 34-field feature interface.

The evidence does not yet isolate physical gain correction. Validation is event-disjoint but overwhelmingly uses training stations; elevation/Vs30 together almost uniquely distinguish a station. Moreover, roughly 94–98% of the aggregate tail error reduction comes from HN records. These are concrete reasons for matched factor ablations and held-station evaluation, not evidence of a forbidden-field leak. All 13 tail events have HN, HH and EH recordings, so family differences are not simply comparisons of disjoint event sets. They still mix stations, distances, noise and recording conditions.

## Exact population and comparison

TRAIN contains 979,487 records from 47,273 events; VAL contains 96,993 records from 3,711 events. Event and trace intersections are both zero. The fitted sample has 197,676 TRAIN records and retains every training record with magnitude at least 4. VAL has only **1,027 records from 13 events at M≥4**, five events at M≥4.5, one event at M≥5 (M5.1), and none at M≥6. These results cannot establish extrapolation to major earthquakes.

| Deadline | Bulk MAE, base → static | Median AE | M≥4 MAE | M≥4 event-macro MAE | CVaR95 |
|---|---:|---:|---:|---:|---:|
| 1 s | .40567 → .37732 | .30530 → .28163 | .87077 → .70983 | .85318 → .67998 | 1.42528 → 1.35825 |
| 3 s | .35693 → .32944 | .26407 → .24316 | .72896 → .58809 | .69901 → .55015 | 1.30396 → 1.23288 |
| 5 s | .32798 → .29925 | .23516 → .21246 | .63920 → .50517 | .60826 → .46508 | 1.26624 → 1.20122 |

Both individual training seeds improve bulk and M≥4 MAE. The static ensemble improves event MAE for 12/13, 13/13, and 11/13 tail events at 1/3/5 s. The tail event-macro improvement remains positive when any one event is omitted: reductions range .15266–.19040, .13580–.16117, and .13117–.15736 respectively. This is a sensitivity diagnostic, not a confidence interval or correction for repeated validation use.

The three tail families each cover all 13 events, with 131 EH, 551 HH and 345 HN records:

| Deadline | EH tail MAE | HH tail MAE | HN tail MAE | HN share of total absolute-error reduction |
|---|---:|---:|---:|---:|
| 1 s | .81661 → .71482 | .56486 → .58273 | 1.37992 → .91093 | 97.89% |
| 3 s | .62438 → .53745 | .50573 → .50995 | 1.12521 → .73211 | 93.74% |
| 5 s | .52497 → .44741 | .43670 → .44056 | 1.00598 → .63031 | 94.16% |

The near-flat/slightly worse HH tail result must accompany any overall tail claim. In contrast, bulk error improves for every family; EH has the largest absolute bulk improvement (.31140→.24562 at 5 s). The M5.1 event improves from .80675→.57079 at 5 s across 91 records. Full per-event identities and errors are preserved in the JSON, including the two 5 s tail events that worsen.

## What the 34 fields can encode

The inventory is joined by exact network/station/location/channel and recording-start epoch. Numeric location repairs require corroborating SCNL suffixes; the event component of the trace name is ignored. Multiple matching epochs are rejected. The model receives only the following allowlist:

| Fields | Count | Physical interpretation | Potential proxy |
|---|---:|---|---|
| `family_HH, family_EH, family_HN, family_HL, family_EN, family_unknown` | 6 | Sensor/channel family | Network composition, regional deployment, time period, typical magnitude/record-selection mix |
| `station_elevation_m`, `station_vs_30_mps`, each with `_missing` | 4 | Site geometry and near-surface shear-wave speed | Highly distinctive station/site fingerprint; regional seismicity and propagation |
| E/N/Z each: `_response_missing`, `_log10_sensitivity`, `_velocity`, `_acceleration` | 12 | Scalar gain, native physical unit and validity | Instrument/model/epoch fingerprint; missingness identifies one historical station regime |
| E/N/Z each: `_log1p_sensitivity_frequency_hz`, `_sensitivity_frequency_hz_missing` | 6 | Calibration frequency | Sensor configuration/model/epoch; does not specify full transfer function |
| E/N/Z each: `_log1p_native_sample_rate_hz`, `_native_sample_rate_hz_missing` | 6 | Acquisition rate before dataset resampling | Instrument/network/epoch and acquisition practice |

StationXML sensitivity has units determined by its input/output declarations and a reference frequency; scalar division is not removal of the full frequency response. Velocity and acceleration amplitudes cannot be treated as the same physical quantity. These distinctions follow the [FDSN StationXML reference](https://docs.fdsn.org/projects/stationxml/en/latest/reference.html) and [ObsPy sensitivity-removal documentation](https://docs.obspy.org/packages/autogen/obspy.core.trace.Trace.remove_sensitivity.html).

All current site values are present, so the site-missing flags are constant. The unknown-family flag and vertical response/frequency/rate missing flags are also constant. Incomplete responses occur only for historical IV.GIGS horizontal HH components. This affects 0.52% of TRAIN and 0.59% of VAL; the missingness flags can identify that regime. There are no silently dropped recordings.

### Station overlap and feature fingerprints

| Definition | TRAIN identities | VAL identities | Shared identities | VAL records seen in TRAIN |
|---|---:|---:|---:|---:|
| Physical station: network.station, full TRAIN | 561 | 458 | 428 | 95,036 / 96,993 = 97.982% |
| Physical station, sampled fit TRAIN | 543 | 458 | 415 | 94,299 / 96,993 = 97.222% |
| Instrument: network.station.location.family, full TRAIN | 807 | 630 | 573 | 93,797 / 96,993 = 96.705% |
| Instrument, sampled fit TRAIN | 774 | 630 | 549 | 93,039 / 96,993 = 95.923% |

Of the 1,027 tail records, 1,010 use physical stations in full TRAIN; 996 use stations represented in sampled fit TRAIN.

Exact feature-tuple fingerprints were computed over combined TRAIN+VAL **for diagnosis only**. Site-only features give 576 distinct tuples, of which 561 map to one physical station; 99.007% of VAL records have a tuple unique to a station in this observed population. All 34 fields give 1,011 tuples, of which 1,002 map to one station; 99.612% of VAL records have a station-unique tuple. The 12 gain/unit/missingness features give 176 tuples; only 4.543% of VAL records have a station-unique tuple. No hash collision was observed against exact tuple uniqueness.

These calculations use raw float32 features, before training standardization and clipping at ±15. They demonstrate available identifying information, not that the trained neural network memorized it or that all these distinctions survive clipping. Physical site correction and station-specific priors can coexist.

### Magnitude type and recording history

VAL contains 94,475 ML, 2,237 Mw and 281 Md records. The tail contains 329 ML records from three events and 698 Mw records from ten events. Magnitude type is not a model input. Conditional record populations nevertheless matter: temporary deployments, sensor changes, geography and station response can be associated with catalogue regime. This is a plausible indirect mechanism, not an identified cause of the improvement.

The [INSTANCE paper](https://essd.copernicus.org/articles/13/5509/2021/) documents network upgrades and temporary deployments during earthquake sequences. Its preferred magnitude is generally ML, with Mw/Md in other cases; Mw is calculated for sufficiently well-recorded events with ML≥3.5, and Md mainly concerns earlier analogue data. Thus a response/epoch descriptor is not guaranteed independent of label type.

## Preprocessing and weighting limits

The backbone still uses the original count-waveform cache standardized with audited TRAIN constants. Prefix features demean only the supplied 1/3/5 s window. Static features contain no trace SNR, PGA, PGV, catalogue distance, coordinates, future P/S travel times, epoch-end flag, or source magnitude. Recording time is used only to select the instrument epoch. No new forbidden future quantity was found in the static interface.

However, the benchmark already has limitations shared by every arm. The [INSTANCE paper](https://essd.copernicus.org/articles/13/5509/2021/) describes mean/trend removal and resampling after 120 s windowing, and catalogue-reviewed P/S picks and location-quality conditions for record selection. Current windows begin at the manual P sample. Prefix-only operations cannot undo this whole-record preprocessing or establish raw-stream causality. Archived inventory and Vs30 values have not been proven available at each historical event time; they can be configured before future deployment. Most Vs30 values are map-derived, and some metadata elevations differ from channel inventory elevations.

The sample retains up to four randomly selected records per event, then adds every M≥4 record. Weight `n_full(event)/n_selected(event)`, normalized to mean one, restores each event's full record mass. It estimates a **record-population** objective, not equal-event risk. It is shared across all controls, so it does not explain a paired ablation advantage by itself. Its sampled-family mass differs slightly from full TRAIN (EH +0.61%, HH −0.25%, HN −0.012%, HL +1.98%; EN has only three original records). Weighted effective sample size is about 94,606 rather than 197,676.

The beta=5 objective multiplies Huber error by `1+5*max(M−3.5,0)`, adds .075 cross entropy, and uses zero anchor. This intentionally emphasizes larger labels; it is not a proper probability-scoring objective with a calibration guarantee. Lower CRPS/Brier on reused VAL is useful empirical evidence, not such a guarantee. All arms use fixed 15 epochs, common seeds and minibatch order; neither epochs nor these current controls are selected using validation. Earlier backbone selection and repeated exploratory evaluation still make this VAL unsuitable as a confirmatory holdout.

The native-amplitude variant adds little (.70983→.70407, .58809→.58431, .50517→.50356 tail MAE). That does not refute the gain-correction interpretation: after prefix demeaning, native log RMS/peak/mean-absolute are largely algebraic combinations of count-prefix log amplitude, saved standard deviation and log sensitivity. Energy is also redundant with RMS and duration. Floors and finite precision are qualifications. Scalar sensitivity conversion is still not deconvolution.

## Decisive next experiments

The new `instrument_factor_ablation.py` implements five matched controls on the same 291-column residual input:

1. `base`: 245 existing logits/hidden/prefix features.
2. `gain_units`: base plus the 12 gain/unit/response-missing fields.
3. `family_site`: base plus six family and four elevation/Vs30 fields.
4. `response_all`: base plus all 24 component response fields.
5. `full_static`: base plus all 34 fields.

Every inactive input, including all 12 native-amplitude slots, is zero after the **same TRAIN-only normalization**. There are no extra IDs. Architecture, parameter count, extraction, initialization, sample, minibatches, 15 epochs, beta=5 and two seeds are reused unchanged. Name/schema changes fail closed. Results save each seed and ensemble, both mean and median decisions, probabilities, selected rows/identities, feature masks, normalizer, source/input hashes, and output checksums. Station overlap and paired same-event EH/HH/HN diagnostics are explicitly descriptive. The default retains the original 197,676-record fit; `--max-per-event 0` enables a matched full-TRAIN replication.

If gain/unit fields reproduce the benefit, split gains from unit-only indicators next and test fixed canonicalization. If family/site wins, split family-only versus site-only next. If response_all exceeds gain_units, examine calibration-frequency/rate fields rather than immediately attributing the difference to sensor physics. These staged checks keep the first experiment small and interpretable.

A physically motivated diagnostic is a joint digital rescaling: multiply counts and the matching sensitivity by the same factor, keeping physical motion unchanged, and recompute all affected inputs including frozen-backbone outputs. Gain-only changes are not that intervention. Lack of invariance exposes sensitivity to count scale; it does not by itself invalidate a learned model whose original backbone was trained on counts.

For a stronger generalization design, preassign station groups using TRAIN only, grouping all locations/families/epochs for each network.station and co-located aliases when documented. Hold out complete station groups and disjoint events; compare seen-station and unseen-station records from the **same held-out events**, stratified by family/unit and magnitude, reporting both record and event macro risk. Separate sequence/region or temporal event blocks reduce near-sequence dependence. Keep every threshold and group assignment fixed before evaluation.

Strict unseen-station testing requires refitting normalization, backbone and heads without those stations; withholding stations only from the residual fit while reusing the current all-station backbone is a weaker, explicitly residual-only transfer test. Valid predeployment gain/site metadata may still be supplied at new stations. Prefer several TRAIN-derived station/event folds to extract information from the larger training tail, then use the sealed TEST once after freezing the design. Do not repeatedly tune on these 13 VAL tail events. This program separates physical nuisance correction, site generalization and station-specific learning without treating either as misconduct.

## Verification and exact identities

The independent audit script passed three focused CPU tests and clean isolated Codex autoreview (no actionable findings). The ablation passed eleven focused CPU tests with CUDA disabled, including exact schema/masks, inactive native inputs, training-only normalization, identical initial parameters, bitwise reproduction of the existing base/full controls, reporting alignment and a complete synthetic run that checks every saved probability/decision and output checksum. The separate final Codex autoreview is clean (`factor_ablation_review_result.json`): its first review identified missing persistence of raw-baseline probabilities, which was fixed and covered by the synthetic artifact test. The reviewed source hashes and CPU command are in `factor_ablation_provenance.json`.

The JSON `instrument_scientific_audit.json` contains full subgroup rows and identity-preserving tail diagnostics. `audit_identity_signatures.csv.gz` preserves split, original row index, trace/event identity, magnitude type, physical station, instrument family and diagnostic feature fingerprints. No waveform data are included. The following hashes identify the exact audit population and results; probability archives were hashed in place on AWS, while scalar prediction NPZs were copied and verified against every VAL identity and label.

| Input | SHA256 |
|---|---|
| Original train metadata | `168b5d861804e9707f68125dc8bc9453c8e0a47a48ef4055a7920c6526f1535d` |
| Original val metadata | `3e1b2781559fc1da8c1d1de03af3148f4399c556df84741ae1e38b32d476698f` |
| station_metadata.csv.gz | `1a7f1df9d5d3553b38c333adb240d87f94aea607c178d80e30f511e3d9e31f82` |
| audit_labels.csv.gz | `f9c8a38c9dd8f899ed46b5b310028706755a955b30b96420861d8551cee34f1c` |
| responses.tgz | `71eccc6304afad15e9c45534ca374b4b4f974c9f93ccfc0f2683616ee6421ef2` |
| instrument_inventory_code_sha256 | `9a942c4773e5c18264aa2db432ba4669f965004aeb9a1f67f25a67d6c812c227` |
| audit_script_sha256 | `a30b610bb9ee73538380dc7bf6420a132f1668b8f741b9d809ee5ec0212b04f4` |
| identity_signatures_sha256 | `f6d50f3ce39b685ce687280fa8cccf4d322d64caeb1a8fc63a457ed54ec7e787` |

| Deadline scalar prediction archive | SHA256 |
|---|---|
| 1s_predictions.npz | `d92eef26354188cd69e6c98b52a32ac2f13970a37bb7f676e08b0fb5920736cb` |
| 3s_predictions.npz | `d77393a6ab06e83b31124fa5837ac42c6f909a2f7e80c06851da0e4e4c03e43d` |
| 5s_predictions.npz | `a1b115291ec6b65fd1b3c66db2c364d90666069cce5e941530593d5273b49b01` |

Exact probability archive identities (AWS `/mnt/eew-research/runs/`):

- `instrument_residual_1s_1bbf4f4d67e5_2b94eb7e7f00`
  - `base_probabilities.npz`: `1bcf88de4ec5a33d57a01b6b2e21d42f8d991ae6c48b6abcab99e37d69c6685e` (74,237,248 bytes).
  - `instrument_native_probabilities.npz`: `643b0a58c89034dc7495881072777443004c136b2ee0e7f4bd7737b1e2539a0c` (74,348,342 bytes).
  - `instrument_probabilities.npz`: `a1957a3672e7f0674c714985f9c863597ada5dc5bee3feecced02d6d21bd163b` (74,334,594 bytes).
- `instrument_residual_3s_1ebd2ac6e35d_c019cf0c8deb`
  - `base_probabilities.npz`: `6c70622302043061cd7c2a607331b06bbaf4824a23ea000d51ab9dfc1d48fda3` (74,186,407 bytes).
  - `instrument_native_probabilities.npz`: `92907f6fbd527da043d1aff39999f9932319dfa7985a24629e81b938045045a3` (74,299,544 bytes).
  - `instrument_probabilities.npz`: `79ae7b8017e355442c375c76afeda77c1a619aff718dfedf08bde9d7dcab6c5c` (74,285,957 bytes).
- `instrument_residual_5s_8ffeb0a0aeba_55cd3e5f1074`
  - `base_probabilities.npz`: `ed42c543c6a9cce8fb431dbd03c2800eba63c960bc855503201259f48f3dbdcb` (73,670,284 bytes).
  - `instrument_native_probabilities.npz`: `7040c7d7fcac5c47def8f3033b56a7debe9e3103b925af622dfec23b37649ca1` (73,809,906 bytes).
  - `instrument_probabilities.npz`: `406c7628c92c14d3b46d4135321f83407ee2ec2b57c948d3357002df30211075` (73,786,110 bytes).

The probability-manifest SHA256 is `618f63897f19d642e560dd71e860c42cf5b1b3ece6487a3d97af70dd4186e045`. Existing run `identity.json` and `input_identities.json` pin source, checkpoint, normalization and validation-reference hashes. The new ablation additionally hashes every completed output in `artifacts.json`; the manifest excludes itself.

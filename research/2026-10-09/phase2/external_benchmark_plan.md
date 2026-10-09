# External benchmark acquisition and fair comparison

Verified 9 October 2026. All sources below are primary publications, authors' code, or official data repositories. This memo records access facts and provisional calculations; no external benchmark model has yet been evaluated.

## Recommended benchmark: TEAM-LM Northern Chile

The official dataset is [GFZ 10.5880/GFZ.2.4.2021.002](https://doi.org/10.5880/GFZ.2.4.2021.002), licensed CC-BY-4.0. Its [direct public archive](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2021.002noeUVRE/chile.tgz) needs no account. Verified HTTP HEAD reports 42,902,965,249 compressed bytes and byte-range support. Inspecting the first archive member gives `chile_filtered.hdf5`, 115,893,796,855 bytes. Keeping both totals 147.9 GiB, within the authorized 160 GiB local acquisition limit. The official [data description](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2021.002noeUVRE/2021-002_Muenchmeyer-et-al_data-description.pdf) was downloaded and read.

The description specifies 100 Hz velocity in m/s, sensitivity corrected but not full response corrected, component order ZNE, and 30 seconds from five seconds before the first P arrival anywhere in the network to 25 seconds afterward. The HDF5 contains per-event station coordinates and waveforms plus pandas event metadata. These conventions differ from INSTANCE counts and per-station P-relative windows; feeding this directly through the existing normalization would be invalid.

The [TEAM-LM paper](https://arxiv.org/html/2101.02010) reports 96,133 Chile events, 24 stations, 1,605,983 three-component records, and maximum MA 8.27. At one second after the network's first P arrival, its plain model reports overall MAE 0.18 and large-event MAE 0.78, where large means MA≥5.5. Its tabulated times are 0.5, 1, 2, 4, 8, 16, and 25 seconds; 3/5-second comparisons require rerunning the baseline. These figures are not directly comparable with INSTANCE single-station errors.

### Exact published code and split

Author repository: [yetinam/TEAM](https://github.com/yetinam/TEAM), GPLv3. Local copies of the relevant loader, evaluation, utility, magnitude baseline, and configuration files are saved beside this memo; `team_tree.json` records the inspected tree revision. No released pretrained weights were found in that tree.

`loader.py` implements the default split by metadata row index: test starts at `int(0.7*N)`. Of the non-test events, training occupies the first `int(0.6/0.7 * non_test_count)` rows, with the rest development. The Chile config does not request shuffling. The implementation assumes metadata are already chronologically ordered; verify actual timestamps and event keys after extraction.

The author evaluation CLI accepts `--times 1,3,5 --test`, with a cutoff of `int(sampling_rate * (noise_seconds + time))`. Waveforms after that cutoff are zeroed. Original code also selects stations and handles triggers through its generators. Preserve its causal station availability rules. The published implementation uses old TensorFlow/Keras APIs and deprecated h5py `.value`; a faithful modern port must be checked against the original equations and a small fixture. Its loader eagerly holds waveforms in memory; replace only storage access with event-wise HDF5 loading for a small-memory AWS instance.

A lower-cost compact export can retain the first 1,000 samples (-5 to +5 seconds) as float32, approximately 19.3 GB of waveform payload, or just samples500:1000 (+0 to+5 seconds), approximately 9.6 GB. The latter changes the available pre-event information and must also be applied to every baseline. Actual shape/dtype/size still await inspection.

### Provisional magnitude support from a separate source catalog

The official [IPOC magnitude catalog](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2019.004/IPOC_catalog_magnitudes.csv) is 7,351,604 bytes, independently downloadable without waveforms. I computed its chronological60:10:30 counts for acquisition planning:

| Portion | Events | MA≥5.5 | MA≥6 | MA≥7 | Maximum MA |
|---|---:|---:|---:|---:|---:|
| Training |57,679|22|12|1|8.054|
| Development |9,613|1|0|0|5.715|
| Test |28,840|29|11|2|8.055|

**These are not verified TEAM HDF5 split counts.** The catalog has 96,132 rows versus 96,133 reported by TEAM-LM, and its maximum differs. The exact dataset must settle that discrepancy. Even the provisional catalog suggests the development set is too weak to tune M≥6 corrections credibly; a nested training-only event split or another region is needed for tail hyperparameters, with the published test sealed.

## Alternative: TEAM Italy

Official [dataset DOI](https://doi.org/10.5880/GFZ.2.4.2020.004), CC-BY-4.0; [direct public archive](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2020.004nujar/2020-004_Muenchmeyer-et-al_data.tar.xz). Verified compressed size21,394,782,208 bytes, first HDF5 member`italy.hdf5`35,801,647,031 bytes. Its [description](https://datapub.gfz.de/download/10.5880.GFZ.2.4.2020.004nujar/2020-004_Muenchmeyer-et-al_data-description.pdf) gives100Hz acceleration m/s², NEZ order, and the same -5:+25-second network-aligned window. P picks are retrospective STA/LTA picks informed by catalog origin/location, with no quantitative pick-quality validation. They are useful benchmark annotations but do not prove real-time detection performance.

Author`loader.py` reserves every metadata`Time`starting`2016`for test. Remaining events are shuffled using NumPy seed equal to the number of metadata rows, then split6:1 train/development. This includes large 2016 events, but those same earthquakes may already appear in INSTANCE training. Consequently an INSTANCE-initialized model cannot call Italy2016 an independent event holdout; train a fresh benchmark-only model or audit/remove event overlap before claiming transfer generalization.

## Japan

The author TEAM repository supplies `japan.py` download/extraction scripts and a fixed event catalog. Download requires the user's NIED account; raw NIED data are not redistributed by TEAM. No available credentials were used or requested. Japan is attractive for additional very large events, but it is not an immediately anonymous public download. Do not bypass its login or licensing restrictions.

## CREIME and MagNet: useful baseline architectures, limited direct score comparison

[CREIME author release](https://github.com/srivastavaresearchgroup/CREIME) provides a model and an inference notebook; [Zenodo release](https://zenodo.org/records/6700315) is10.9MB. It uses512sample 100 Hz windows containing1–2seconds after P preceded by noise. Magnitude is the mean of the final 10 predicted samples. The repository tree does not supply the original train/dev/test event-ID lists or a full retraining pipeline. The [paper](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JB024595) uses ML-only STEAD, SNR > 10 dB, and event-separated splits. Adapting this architecture to fixed1/3/5seconds is reasonable but must be described as a reimplementation, with identical data and timing for all compared models. Repository licensing needs clarification before redistributing copied source; no license file was visible in the inspected root.

[MagNet author repository](https://github.com/smousavi05/MagNet) includes architecture/training source, pretrained weights and`test_results.csv`. Its current source crops3000samples fromP−1s throughP+29s, filters ML,SNR ≥ 20 dB,distance ≤ 110 km plus several label-completeness criteria, and randomly shuffles trace names before splitting. This visible source does not enforce event separation. Do not assume it exactly reproduces every published experiment: filenames/report mention a1000sample model while the current code crops3000samples. The public results CSV contains 49,291 records from 41,001 unique source IDs; maximum ML5.2, only 3 M≥5events and no M≥5.5events (computed locally). It cannot establish strong large-earthquake performance for this project.

[STEAD source](https://github.com/smousavi05/STEAD) offers roughly 14 GB waveform chunks and an 85 GB merged archive, with a SeisBench fallback. [SeisBench STEAD implementation](https://github.com/seisbench/seisbench/blob/main/seisbench/data/stead.py) labels the data CC-BY-4.0 and applies the EQTransformer trace-level test list plus every 18th remaining trace for development. Those splits are not automatically the CREIME or MagNet splits and do not by themselves verify source-ID separation. Inspect and enforce event exclusivity before use. The source normalizes component order from original ENZ into ZNE and declares velocity counts without restituted instrument response.

## Additional strong global reference: AIMag and MLAAPDE

[AIMag, Dybing et al. (2024)](https://pubs.usgs.gov/publication/70256598) adapts MagNet to about 2.4 million P arrivals and explicitly studies large-event underestimation across window lengths. The [complete primary PDF](https://par.nsf.gov/servlets/purl/10576069) and [author training/evaluation repository](https://github.com/UO-Geophysics/AIMag) were inspected. Its named window length includes both pre-event noise and signal, with picks approximately central and random shifts up to ±3 seconds; it is not a fixed post-P observation duration. The historical test extension includes 78 earthquakes above M7.5 from 2000–July2013, in addition to a 2020 MLAAPDE test. This is a useful stress-test design but requires reconstructing a matched causal timing convention before comparing errors.

[USGS MLAAPDE documentation](https://www.usgs.gov/publications/mlaapde-a-machine-learning-dataset-determining-global-earthquake-source-parameters) describes 5.1 million 120-second three-component records; 14% are local, 36% regional and 50% teleseismic. Broad global magnitude capability cannot directly establish local EEW performance. The [official USGS software](https://code.usgs.gov/ghsc/neic/neic-mlaapde) supports customized phase, length, sampling and distance selections. Prefer official releases/SeisBench to third-party mirrors for provenance. No MLAAPDE waveforms were downloaded during this acquisition.

## Required comparison protocol

The existing66-bin support0.05–6.55 cannot represent Chile’s largest labels. Extend the magnitude support before experimentation, equally for all matched baselines, or use an unbounded continuous mixture. Record MA rather than conflating it with ML or Mw.

1. Preserve the published Chile test event IDs, train baselines from training data, and create an event-disjoint internal training calibration split for the proposed correction. Record any model selection on development, particularly its scarcity of large events.
2. Run TEAM-style Gaussian mixture, a matched pooling baseline, and the existing CNN probability model on exactly the same1/3/5-second causal inputs. Include network timing and a separate single-station track; do not mix their headline scores.
3. Compute every per-example amplitude normalization, SNR, entropy, and feature from samples available at the evaluated time. In particular, do not normalize a one-second input by its five-second peak. Event aggregation must exclude stations that have not yet arrived at the network evaluation time.
4. Report mean/median absolute error, RMSE, worst5%absolute-error mean, event-level tail error/bias, probabilistic proper scores, calibration, and false-tail predictions. Bootstrap paired **events**, never individual station records.
5. Evaluate the new distribution/sequential method against its own identical backbone ablation, including posterior-only versus waveform-innovation corrections. Distinguish a new useful correction from merely a stronger backbone or changed dataset.
6. Read out the sealed test only after predeclaring comparison and hyperparameters. Report all tested variants, failed attempts, and uncertainty. The objective is a defensible improvement; novelty and superiority are outcomes to demonstrate.

## Acquisition status

Local, authorized, no AWS mutations. `chile_manifest.json` records provenance/expected sizes/deadline;`chile_download_state.json` records verified completed byte ranges. `download_chile.py` checks HTTP206 and exact Content-Range for each disjoint 16 MiB segment, resumes completed ranges, uses 8 workers, and enforces the original three-hour wall-clock deadline. `chile_range_download.log` records progress. The archive is sparse-preallocated, so **file size is not download completion**; use the manifest's completed-range bytes and final SHA256. Extraction and actual HDF5 audit will be recorded when acquisition completes.

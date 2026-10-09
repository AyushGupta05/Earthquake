# Additional large-earthquake validation resources

Research checkpoint, 9 October 2026. These resources were identified during the primary-literature search. Their published results have not been reproduced here; no new model has been scored on their waveforms. The ongoing Chile benchmark remains the active external comparison.

## Recorded Alaska earthquakes

[Williamson et al. (2026)](https://doi.org/10.1785/0120260139) evaluate EPIC on 530 Alaska earthquakes, M4.5–8.2, with eight M7+ events. The released inputs include miniSEED recordings and station coordinates, gains and units. EPIC detected and matched 345 events; its initial magnitude underestimate was larger for deep events. The study identifies its fixed shallow-depth assumption as a source of error. This is useful evidence for testing geometry uncertainty, not a demonstration that a new probabilistic head will solve it.

The [author dataset](https://zenodo.org/records/19897535) API confirms CC-BY-4.0 and one 8,372,439,484-byte archive, `testsuite_data_williamson.zip`, with MD5 `38449cb548b3e5c7119b267f6a12a400`. A local full download is underway; its archive checksum remains unverified. A bounded ZIP-directory audit found 781 `.dat` metadata files and 781 matching `_replay.seed` waveform names. All metadata files passed ZIP CRC checks: 296,990 station-channel rows have finite coordinates and positive rates/gains, with velocity and acceleration units at 50/100/200 Hz. No waveform was decompressed. The paper’s 530-event cohort has not yet been reconciled with these 781 identifiers; neither count may silently substitute for the other. Full transfer functions are not supplied by these gain-only tables.

Proposed use: a frozen cross-region stress test with an explicitly specified time origin and causal preprocessing. Preserve detection failures in end-to-end reporting. A magnitude predictor conditioned on a known P pick is a separate task from EPIC's detection/association system. Catalogue depth/distance may define reporting strata but cannot become inference features. The mix of supplied magnitude types must be audited before comparing INSTANCE ML, Chile MA and Alaska preferred catalogue labels. This large-event-only collection cannot establish unchanged error for the small-event bulk.

## Recent operational magnitude correction

[Williamson, Lux and Allen](https://rallen.berkeley.edu/pub/2025WilliamsonLux/WilliamsonLuxAllen-EPICmag-SRL-2025.pdf), published online in 2025 and in the January 2026 journal issue, modify EPIC's near/far-station scaling around a 30 km boundary. They report magnitude error changing from .41 to .27 in their retrospective analysis and account for S-wave energy at close stations. This supports investigating physical observation regimes before attributing all tail error to label imbalance. The reported scalar is not a matched 1/3/5-second neural-model benchmark; its exact metric and selection must be checked before tabulating it alongside our results.

## Cascadia simulations

[Nye et al. (2026)](https://seismica.library.mcgill.ca/article/view/1411) provide 112 simulated M6.6–9.4 ruptures and waveforms at 191 sites. Their evaluation includes P-wave magnitude scaling and operational EEW replays. The analysis examines longer P windows than our one-second target and uses known geometry in parts of its physical validation. Simulated support can test a proposed mechanism under controlled assumptions; it cannot replace real large-event validation.

The [Borealis release](https://doi.org/10.5683/SP3/CZECEG) API lists 149 files totaling 74,541,030,569 bytes under CC-BY-4.0. Only metadata and the 6,434-byte README have been downloaded. Its accelerations are sampled at 100 Hz, with separate signal/noise variants and rupture models. No waveform bulk download has been launched. A useful later experiment would compare source-only physical changes against amplitude-only augmentation using a declared generator, then test transfer to real earthquakes. Any gain confined to the simulation assumptions would remain a synthetic result.

## Prior-art implications

Station-specific probabilistic calibration already exists in [Li, Taflanidis and Brewick (2023)](https://doi.org/10.1016/j.soildyn.2023.108198). Physics-aware seismic augmentation and prototype contrastive learning are also explicit in [ConProSeis (2026)](https://doi.org/10.1016/j.engappai.2026.115317). Neither adding a station latent variable nor calling an augmentation physical establishes novelty. A new method needs a precisely different observation model or training mechanism, a matched simpler control, and consistent improvements on independent real events.

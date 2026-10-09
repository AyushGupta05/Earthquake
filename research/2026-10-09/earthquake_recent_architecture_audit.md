# Additional 2026 architecture audit

9 October 2026. These papers extend the literature inventory; none supplies a directly comparable published win for our current INSTANCE validation. Source code was inspected, not trained or executed.

## SeisMamba

[Yeo et al., arXiv:2608.24561v1](https://arxiv.org/html/2608.24561v1) uses 30-second, three-component waveforms with a zero-phase 1–40 Hz filter. It combines multiscale convolutions, sparse Mamba blocks and scalar/temporal MSE supervision. Reported STEAD MAE is .1566; its table gives AMAG a lower MAE (.1467), while SeisMamba leads MSE/RMSE. A Chile–Taiwan geographic holdout gives MAE .2808. Its .55 ms figure is computational latency for a batch of 32, not the observation duration. The temporal auxiliary output does not by itself establish a causal 1-second prediction. This is an architecture lead, not a numerical early-warning comparator. A matched adaptation would crop before filtering/normalization and retrain at our deadlines. The main random-split grouping and exact release artifacts remain unverified.

## MP-Net

[Wang et al., DOI 10.1093/gji/ggag204](https://doi.org/10.1093/gji/ggag204) processes five seconds before and five seconds after P arrival, combining waveform, spectrogram and retained log-amplitude inputs. It reports STEAD MAE .2801 with ML .5–4.5, plus separate KiK-net validation over MJ 3–6.5. Its scalar pinball objective is not a calibrated probability distribution. Its 5-second setup makes it a relevant architecture comparator, but different magnitude scales, sampling and stations prevent direct comparison to our numbers. We should adapt both its scalar head and a matched distribution head before attributing any gain to a new loss or PDF mechanism.

The [author repository](https://github.com/hlw12/Mag/tree/d8b32231e74d9f95d4fa455f3d8c5148131718ee) was pinned to `d8b32231e74d9f95d4fa455f3d8c5148131718ee`. Inspection found:

- `main.py` partitions unique source IDs, preserving event separation in that code path. The default configuration samples up to 300 events per half-magnitude interval; this differs from evaluating the natural record population.
- `Trainer.py` constructs `QuantileLoss(quantile=0.5)` despite the class default .65 and the paper's asymmetric-loss discussion. The pinned code and paper cannot be assumed identical.
- Each cross-attention call receives one query token and one key/value token. The one-element softmax is exactly one: at evaluation its output is independent of the query. Subsequent concatenation still fuses both branches, but this operation is not content-dependent cross-modal selection. A small standard-PyTorch calculation with distinct random queries verified identical outputs, maximum difference zero. This establishes an algebraic implementation property, not a performance defect in the trained model.
- The README says MIT and refers to a LICENSE file, but that file is absent in this checkout. Preserve attribution and resolve reuse terms before distributing copied implementation code; independent implementation from the published architecture remains a separate option.

The source-file hashes and numerical attention check are saved in the research evidence. Changing to multiple tokens would be an ordinary attention correction, not sufficient novelty by itself.

## South Asian initial-P classification

[Fahim et al., arXiv:2605.22836v1](https://arxiv.org/html/2605.22836v1) studies a seven-second vertical-component, five-class task. Its transformer reports 76.23% exact accuracy and 81.56% boundary-tolerant accuracy. Only eight test cases fall in the M≥7 class. Quality filtering uses magnitude-conditioned amplitude percentiles and P/S information; the reported stratified split needs an independent event-identity audit before reuse. These are curated-cohort classification results, not continuous 1/3/5-second magnitude errors. The paper explicitly leaves shorter windows for future work. Its sampling, focal loss and ordinary augmentations are useful controls, but none independently resolves calibrated rare-event magnitude estimation.

## Strain and DAS classification

[Sawi et al., Nature Communications 2026](https://www.nature.com/articles/s41467-026-72223-z) classifies M≥5.4 using four seconds of post-P strain and ten seconds of preceding data. Its important predictors include low-frequency .2–.5 Hz wavelet summaries and amplitude. Training uses borehole strainmeters; a later M7 earthquake provides an independent DAS case. This supports testing information retained by suitable sensors, not assuming that another network's velocity/count signals contain the same evidence. The paper groups earthquake records across splits, but describes a target-correlation feature screen over all waveforms; our reproduction would nest feature selection inside TRAIN. It explicitly distinguishes its offline single-station task from operational ShakeAlert. Its [published code](https://gitlab.com/tsawi1/rapideqmag) is a useful further audit lead. This is binary classification and cannot be ranked against continuous magnitude MAE.

## Research consequence

Observation duration, computation time and magnitude scale need separate columns in every comparison. The strongest current practical improvement remains instrument/site information on our reused validation. The new contribution still needs a specific failure mechanism, a matched control that isolates it, and independent large-event evidence. The ongoing Chile baseline and Alaska archive audit serve that test; changing the architecture name does not establish it.


## September 2026 multi-station LLM study

Bassani et al. adapt TinyLlama with LoRA to station coordinates, relative P-arrival times and vertical peak velocity. They report magnitude MAE 0.20 and RMSE 0.28 for P inputs; high-magnitude underestimation remains. Their cohort requires at least five velocity stations with P arrivals within five seconds of the first station. Its 0.2-second peak-measurement window is therefore not a 0.2-second event warning deadline. Our single-station INSTANCE results cannot establish superiority to this network protocol. The reusable idea is compact physical and geometry inputs; the paper does not show that an LLM is necessary for our distribution target. [Primary paper, published 21 September 2026](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2026JH001578).

Independent inspection of the [author code](https://github.com/AuroraBassani/LLM-for-Earthquake-Characterization/tree/ff4dfa7069cf19cf99cc2b0b22625d568c2401c3) confirms event grouping, the five-station filter, and magnitude-stratified 80/10/10 event splitting with seed 42. `InputOutput.py` measures P velocity from samples P−10:P+10 and selects arrivals up to the five-second boundary; strict online availability may therefore extend 0.1 seconds beyond that boundary. Its joint `dropna` excludes records missing S information even for the P-only comparison. Inputs contain station coordinates, relative arrivals and amplitudes; source coordinates and travel time are output targets, not input fields. Amplitudes undergo two successive scaling operations (10^5 and 10^4). The default preprocessing branch assigns `data_md` but later accesses `data`; it is not directly runnable as written without resolving that branch. These code observations do not invalidate the reported trained results, which we have not reproduced. Source hashes are retained; no repository license file was found, and no source was copied into our model.


## October 2026 conformal uncertainty study

See the [source/version audit](earthquake_conformal_pga_audit.md) of Shin and Jeong's [October 5 PGA-interval paper](https://academic.oup.com/gji/advance-article/doi/10.1093/gji/ggag415/8865294). It identifies reusable uncertainty controls and distinguishes the older public implementation from the accepted paper.

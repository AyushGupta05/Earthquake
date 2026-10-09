# Phase 2: waveform evidence, sequential distributions, and future information

Status on 9 October 2026: exploratory experiments on the existing AWS g5.xlarge
with one A10G; no new instance or quota increase. Reused INSTANCE validation is
not an untouched test. No claim of novel or state-of-the-art performance follows
from these experiments. The original test waveforms have not been evaluated by
this research loop. Prior checkpoint selection already used historical splits.

## Completed waveform-evidence correction

The residual distribution uses either centered 66-bin logits alone or those
logits plus the frozen 128-dimensional CNN embedding and 51 prefix waveform
descriptors. The latter include log amplitudes, four-interval amplitude growth,
frequency-band fractions, spectral entropy, roughness, crossings, and crest.
All descriptors use only samples in the supplied prefix. They are counts-based
descriptors, not response-corrected physical source measurements.

Fits use 197,676 training recordings: at most four randomly selected stations
per ordinary training event and all M>=4 recordings. Inverse inclusion weights
recover the recording population in expectation. Feature normalizers use only
training examples. The same 15-epoch grid tests magnitude-emphasis beta=0,5,15
and an optional anchor to the original prediction. Five source-event folds
separate policy selection from each fold's readout, but years of earlier
validation reuse and this adaptive research loop prevent a clean confirmatory
interpretation. The selection helper permits small degradation budgets.

| Seconds | Original MAE | Selected MAE | Original M>=4 MAE | Selected M>=4 MAE | Original CVaR95 | Selected CVaR95 |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0.414320 | 0.413392 | 0.899153 | 0.855772 | 1.414283 | 1.420824 |
| 3 | 0.363262 | 0.362816 | 0.751692 | 0.701364 | 1.293831 | 1.309731 |
| 5 | 0.331355 | 0.332584 | 0.651258 | 0.614540 | 1.256338 | 1.271584 |

These are modest tail gains with remaining worst-error tradeoffs. They do not
satisfy the full objective. The beta=0 evidence model improves ordinary errors
substantially but worsens rare-magnitude error; weighting reverses this tradeoff.
All eight configurations per duration are preserved in aggregate JSON, including
negative outcomes. `robust_residual.py` adds an established CVaR training control
to test whether explicitly optimizing worst errors improves that frontier.

## Completed end-to-end sequence controls

All three compact models share a residual convolution encoder, amplitude branch,
GRU cell, and 66-bin head, with 355,682 parameters (entropy gating adds 130).
Independent mode recomputes each full prefix. Sequential modes process disjoint
0–1, 1–3, and 3–5 second segments and add a learned logit innovation to the prior
log probabilities. This is a discriminative update, not a calibrated likelihood.
The entropy gate sees new waveform evidence and can override confident errors.

Training uses the same sampled records, seed 20261009, batch 512, AdamW,
weighted Huber plus CE, and 20 fixed epochs. Validation is monitored every five
epochs but does not choose a checkpoint. These initial runs visibly overfit;
reporting an intermediate best epoch as an untouched result would be invalid.

| Model | 1s MAE / M>=4 MAE | 3s MAE / M>=4 MAE | 5s MAE / M>=4 MAE |
|---|---|---|---|
| Independent prefix | 0.449441 / 0.914374 | 0.399097 / 0.732829 | 0.376669 / 0.666338 |
| Sequential innovation | 0.467201 / 0.931456 | 0.425645 / 0.829580 | 0.408209 / 0.774915 |
| Entropy-gated innovation | 0.461873 / 0.950850 | 0.421979 / 0.846900 | 0.404774 / 0.803649 |

Neither sequential variant improves its matched independent control. Training
times excluding audit/data load were approximately 6–8 seconds per epoch; no
larger GPU was required. The first independent launch hung on a huge HDF5 target
index operation before training. It was stopped, the target array was read once
then indexed in memory, and a fresh run completed. That failed launch is not an
additional independent replicate.

## Next falsifiable hypothesis

`resolution_distillation.py` predicts a current magnitude CDF and a vector of
expected squared changes in the later CDF for 1→3 and 3→5 seconds. A frozen
teacher always receives the full later prefix, including the student's earlier
input. Squared CDF matching estimates a conditional mean under ideal nesting;
absolute-CDF matching can instead remove rare probability by targeting a median.

The theoretical variance decomposition and value-of-information head have close
prior art, notably DIME (ICLR 2024). They must not be presented as new principles.
A narrower hypothesis compares an ordinal vector of squared posterior revisions
against the realized improvement in Brier scores. With an ideal nested teacher,
the squared revision is the conditional expectation of that realized improvement,
giving a standard variance-reduction argument. Whether this helps fixed-horizon
magnitude accuracy through shared representation learning remains untested.
An imperfect teacher can be biased; predicted revision energy is not automatically
resolvable uncertainty. See the linked research memo for citations and caveats.

## Causality and external validation

The INSTANCE source paper says stored counts were whole-record detrended and
resampled. Model prefix and gradient tests establish model-input causality, not
a fully causal raw acquisition/preprocessing pipeline. Stored SNR and peak-motion
metadata depend on later samples and are excluded. Instrument identities and
response inventories are potentially available at inference but require correct
channel/epoch matching. No post-S SNR or catalog-derived distance is an input.

The public TEAM-LM Chile archive is being acquired locally for a matched external
benchmark with genuinely larger events. It uses network-first-P timing, physical
velocity, and MA labels. Its published scores cannot be compared directly with
our per-station INSTANCE results. A fresh model must extend the magnitude support
beyond the current 6.55 maximum. The official test is to stay sealed until model
and comparison choices are fixed; train/development data support initial work.

## Reproduction and checks

Run from the remote repository root using `.venv/bin/python`. Entry points:
`feature_residual.py --seconds {1,3,5}`,
`train_sequential.py --mode {independent,sequential,entropy_gate}`,
and `robust_residual.py --seconds {1,3,5}`. New runs allocate unique directories,
record full configuration and hashes of research source dependencies, and never
overwrite earlier models. Existing initial directories predate that change.

39 focused tests passed in the AWS environment, covering correct sample weighting,
future-input independence, finite gradients, ordered proper scores, CVaR algebra,
teacher detachment/nesting, and immutable run allocation. Codex autoreview accepted
two actionable artifact-provenance findings across iterations; both were fixed,
and the final scoped review returned no actionable findings. New experiment
runners added later require their own test/review cycle.

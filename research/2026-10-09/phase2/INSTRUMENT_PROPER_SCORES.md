# Established proper-score controls on the instrument head

This grid strengthens the distribution baseline. It introduces no novel scoring
rule, architecture, conditional reference model, or sequential update. Run all
prespecified arms at 1, 3 and 5 seconds; report both seeds and their equal ensemble.
No validation tuning, checkpoint selection, or selective reporting is permitted
by this protocol. Validation has already been reused extensively, so these are
exploratory comparisons, not untouched test estimates or cross-paper superiority.

## Matched design and fixed protocol

The runner calls the existing `instrument_residual.extract` and `design_inputs`.
It uses the exact 291-column design: 66 centered frozen logits, 128 frozen CNN
hidden features, 51 prefix features, 34 epoch-matched static instrument/site
fields, and 12 native amplitude slots set to zero after TRAIN normalization.
The existing bounded residual distribution network, including dropout, is
unchanged. All arms have identical parameters, initialization, batch order,
optimizer, normalization and inclusion weights. All 979487 TRAIN records are the
default (`--max-per-event 0`); an explicit smaller sample must also override the
expected record count and is only a smoke/pilot experiment. Sampling, if requested,
uses the inherited TRAIN inclusion weights, not uniform event weighting.

Defaults are 15 epochs, seeds 20261009 and 20261010, AdamW learning rate 0.0005,
weight decay 0.0001, batch size 2048 and gradient clipping at norm 5. The final
epoch is evaluated; training never reads validation labels. The TRAIN prior
and normalizer are fitted once and then shared across arms. Source hashes,
TRAIN identities, target/weight digests, realized order hashes, initial/final
model hashes, deterministic flags and all metrics/predictions are saved.

Deterministic algorithms and cuDNN are enabled; `CUBLAS_WORKSPACE_CONFIG` is set
before CUDA initialization. This supplies a **new matched Huber/CE reference**.
Historical GPU runs used nondeterministic settings and are not expected to replay
bitwise. Determinism is not a guarantee across hardware/software changes.

## Objectives

There are K=66 bins of width d=0.1 and centers (k+0.5)d. The existing label map
is `clip(floor(y/d+1e-5),0,65)`. For an interior cut z_j=(j+1)d, j=0,...,64,
let F_j=sum_{k<=j}p_k and O_j=1[label<=j]. Scores are for this **clipped,
quantized magnitude target**, not a continuum or an unbounded high tail.

Every arm includes 0.075 categorical cross entropy (CE):

| Control | Main objective before +0.075 CE |
| --- | --- |
| `huber_ce` | Existing `(1+5 max(y-3.5,0))*Huber_delta=.5(E_p[M],y)` |
| `crps_ce` | `d sum_j (F_j-O_j)^2` |
| `tail_crps_ce` | `d sum_j [1+4 I(z_j>=4)] (F_j-O_j)^2` |
| `marginal_crps_ce` | `d sum_j w_j (F_j-O_j)^2` with the TRAIN-only weights below |
| `ranked_bce_ce` | `-d sum_j [O_j log F_j+(1-O_j)log(1-F_j)]` |

`huber_ce` preserves the original beta=5, anchor=0 operation order for numerical
replay. It is not a proper distribution score. The other objectives use fixed
positive threshold weights, or the sum of binary logarithmic scores, plus CE;
they are strictly proper for the finite categorical target in population.
Their optimum need not improve MAE, median absolute error or rare-event error
under finite data and restricted model capacity. Report the raw-magnitude CRPS
already computed by the shared evaluator as well; it is not identical to the
training score against rounded bin labels.

For `marginal_crps_ce`, estimate R_j as the inverse-inclusion-weighted TRAIN
fraction with label<=j. Fix `u_j=min(25,1/(0.01+R_j(1-R_j)))`, then
`w_j=u_j/mean_j(u_j)`. This is one vector shared by every record, fitted from TRAIN
only. It is **not** a conditional forecast, an OOF reference, an uncertainty head,
or evidence that a particular input is unresolved. The cap, normalization,
weighted histogram and saturated-threshold fraction are archived. The data-fitted
vector is frozen during optimization; a population propriety statement considers
a fixed vector and a new outcome, not the reuse of that outcome in estimating it.

The fixed tail vector is deliberately not normalized, matching the prespecified
`1+4I[z>=4]` control. Thus main-score scales and the relative CE contribution differ
between controls. Learning rate and CE coefficient are fixed rather than tuned;
this comparison cannot isolate weighting shape from objective scale. Report
failures and gradient saturation rather than choosing a winning scale afterward.
Ranked BCE uses log-cumulative-sum-exp calculations without probability clipping,
so finite separated logits do not cause log(0) or 0*infinity.

For a fixed positive vector w, expected weighted squared-CDF score excess at
forecast F over the true CDF G is `d sum_j w_j(F_j-G_j)^2`. Inverse Bernoulli
variance weighting approximates local binary-log-score curvature; the ranked BCE
arm is consequently an essential established comparator. The standard threshold
weights, fixed TRAIN prior weighting and rank-log score are **known methods**.
Relevant primary literature: [Gneiting and Ranjan (2011)](https://doi.org/10.1198/jbes.2010.08110),
[Tödter and Ahrens (2012), ranked ignorance](https://doi.org/10.1175/MWR-D-11-00266.1),
[Ólafsdóttir et al. (2024), scaled weighted CRPS](https://doi.org/10.1016/j.ijforecast.2024.02.007),
and [Wessel et al. (2025), training with twCRPS](https://doi.org/10.1175/MWR-D-24-0151.1).
Scaled weighted CRPS is not the inverse Bernoulli-variance rule implemented here.

## Scope and execution

This head inherits frozen CNN selection and the INSTANCE released counts'
whole-record preprocessing and manual P-pick limitations. It does not establish
raw-stream causality. Instrument/site fields can encode station/domain priors.
The independent affine-prefix benchmark separately investigates those concerns.
The upper clipped bin cannot demonstrate extrapolation beyond the data support.

On the existing AWS environment, after the parent schedules the job:

```sh
.venv/bin/python research/2026-10-09/phase2/train_instrument_scores.py \
  --seconds 1 --inventory /path/to/official/responses.tgz
```

Repeat with `--seconds 3` and `--seconds 5`. Each invocation runs all five controls
and both seeds, with an immutable output directory. This implementation does not
launch GPU work automatically. Focused verification (CPU only):

```sh
CUDA_VISIBLE_DEVICES='' .venv/bin/python -m unittest discover -s tests \
  -p test_instrument_proper_scores.py -v
```

Tests cover finite-grid propriety, threshold placement, stable extreme logits,
population-weighted TRAIN prior construction, exact CPU Huber replay including
RNG state, validation-target and unused-prior negative controls, matched orders
and initialization, reloadable checkpoints and artifact provenance. The complete
runner test mocks waveform extraction; its existing source/alignment checks are
reused rather than replaced by a new data loader.

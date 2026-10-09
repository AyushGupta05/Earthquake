# Future-growth auxiliary pilot

This is an exploratory counts-only independent-prefix experiment. It asks
whether predicting later observed waveform growth improves the current
magnitude representation. It does not establish novelty, physical rupture
prediction, or superiority over the instrument-conditioned residual baseline,
which has already shown substantially stronger tail performance in this
project. If this pilot helps, instrument conditioning needs a later matched
comparison. No GPU run is launched by importing these modules or exporting
targets.

## Model and prespecified controls

`FutureGrowthModel.backbone` is the unchanged
`MagnitudeDistributionModel(mode="independent")`. It re-encodes each complete
1/3/5-second prefix and resets recurrent state at each time, sharing weights
across times exactly as the existing independent baseline does. Its deployed
`forward(x)` accepts only a prefix and returns magnitude logits. Future growth
and true magnitude labels enter only the separate training loss.

Every control allocates the same backbone and a `129 -> 64 -> 4` auxiliary
head. The four outputs are a nonnegative MSE prediction and three
hurdle/lognormal parameters. The conditional controls supply a normalized
magnitude-bin index as the extra input; unconditional controls supply zero.
Unused outputs remain allocated. All controls use matched initialization and
a separate CPU shuffle generator with the same seed. No auxiliary dropout
changes the magnitude-path random sequence.

The magnitude loss is **exactly the current baseline**, averaged over times:

```
mean_i w_i [(1 + 5 max(M_i-3.5,0)) Huber_delta=1(E_p[M], M_i)
           + .075 CE(p, floor(M_i/.1 + 1e-5))].
```

Bin indices are clipped to `[0,65]` and centers are `.05,.15,...,6.55`.
This cost-sensitive Huber/CE combination is **not** a proper distribution
score. The composite proper-score argument below applies to an idealized
unit-weight CE formulation, not automatically to this actual baseline.

| Control | Additional TRAIN-only loss | Direct gradient to magnitude logits? |
|---|---|---|
| `supervised` | None | No auxiliary gradient |
| `growth_mse` | `.05 * (G - growth_mean(h))^2` | No; through shared representation |
| `unconditional_nll` | `.05 * -log q(G|h)` | No; through shared representation |
| `conditional_nll` | `.05 * -log q(G|Y,h)` | No; through shared representation |
| `conditional_detached` | Same conditional NLL using `h.detach()` | No; negative control |
| `conditional_marginal_stopq` | Conditional NLL plus `.01 * -log sum_k p_k stopgrad(q_k(G|h))` | Yes; optional established-mixture ablation |

The last control is optional and is not the default scientific claim.
`q(G|Y,h)` is supervised with the **true bin** only during training. It never
feeds a predicted growth or a label back into the deployed decoder. The model
factorization `p(Y|X) q(G|Y,X)` integrates to exactly `p(Y|X)` at fixed
parameters. Auxiliary training can still change those parameters and their
calibration. Its use of a true training label is not an inference input.

For `G=0`, `q` is a point mass `sigmoid(zero_logit)`. For `G>0`, use
`(1-sigmoid(zero_logit)) LogNormal(G; mu, sigma)`, including the `1/G`
Jacobian. `mu` is bounded to `[-20,10]`; `sigma=softplus(raw)+.1`, capped at
5. These fixed numerical constraints prevent vanishing-scale spikes and keep
the cheap pilot bounded; they are model assumptions, not fitted physical
constants. MSE uses `softplus(raw_mean)`. Positive target growth is not
clipped; zero is represented by the actual hurdle atom.

Defaults are fixed **10 epochs**, AdamW `lr=3e-4`, `weight_decay=1e-4`, cosine
decay to `3e-5`, batch size 512. Prespecified seeds are `20261009` and
`20261010`. CLI overrides must be recorded and reported as distinct runs,
not selected retrospectively as winners. The `.05` auxiliary weight is fixed
for this pilot; identical numeric weights do not equate MSE and NLL gradient
strengths. Both auxiliary and marginal terms use the recording-population
inverse sampling weights once. Average over **all** batch records, with
missing future targets contributing zero auxiliary loss; do not silently
renormalize to available targets. This changes auxiliary population coverage
when missingness is informative, which the manifest makes visible.

Backbone and auxiliary gradient norms are clipped separately at 5, so a
large detached-head gradient cannot rescale the backbone. The focused tests
check that the supervised and detached controls produce exactly identical
backbone parameters after two AdamW steps, including weight decay and
clipping. Validation is evaluated only at the fixed final epoch; the runner
never selects weights, epochs, thresholds or loss coefficients from it.

## TRAIN target definition and provenance

For each selected `train_full_metadata.csv` row, read its named raw trace
from `Instance_events_counts.hdf5`, in documented INSTANCE ENZ order at
100 Hz. Use vertical component Z, index 2, and the existing P-arrival sample.
The [official waveform reader](https://raw.githubusercontent.com/INGV/instance/main/notebooks/Def_plot_waveform.py)
explicitly maps indices 0/1/2 to E/N/Z. The
[INSTANCE paper](https://essd.copernicus.org/articles/13/5509/2021/)
documents 100 Hz sampling and the count-data preprocessing.
No full-trace PGA, PGV, SNR, catalog distance, validation future waveform or
test record is used.

```
b = mean(x_Z[P-100:P])
A_t = max(1e-8 counts, max_{0 <= j < 100*t} |x_Z[P+j] - b|)
G_t = log10(A_10) - log10(A_t), t in {1,3,5}.
```

All four peaks use **the same** preceding-one-second baseline. Thus `G>=0`
by construction and `G=0` is a genuine atom when no later larger amplitude
occurs. It does not indicate rupture completion: source, propagation, later
phases and noise can all determine the next peak. Constant multiplicative
instrument gain cancels in this ratio away from the numerical floor, but
instrument bandwidth, saturation and noise do not. This is an observed
counts-derived target, not a response-corrected displacement estimate.

The exporter requires integral nonnegative P samples and checks exact
raw-to-cache equality of all three post-P early components for **every
selected available trace**, using the audited global standardization. Same
magnitude values cannot conceal a trace swap. Cache magnitude ordering is
checked exhaustively. Missing raw traces, missing pre-P coverage, missing
10-second coverage and nonfinite extended windows receive explicit masks
and reason codes; waveform/cache disagreement aborts. An invalid five-second
input window aborts because it cannot agree with the magnitude input.

The archive includes selected metadata row indices, event IDs, trace names,
magnitudes, P samples, three growth values and masks, peaks, baselines,
per-window source hashes, metadata/audit hashes, raw/cache path-size-mtime,
normalization hashes, extractor source hashes, and a dtype/shape/byte digest
for every stored array. It reports zero-atom counts and missing reasons.
Training checks all array digests and exact row/event/trace/magnitude/P
identity again, rejects incomplete target coverage, verifies the cache and
normalization identity, and records the whole target archive hash.

Raw-file path/size/mtime is **not** a full-file cryptographic hash; exact
source-window hashes identify the actual selected observations. The cached
input was exhaustively compared to them at export time. Validation cache
waveform identity inherits the earlier sampled audit; this new exporter
does not revisit validation raw traces. The training loader does verify
validation metadata/reference event, trace and target ordering.

The underlying released counts may already have whole-trace detrending and
resampling. This pilot does not repair that upstream causal limitation.
P times are catalog picks from the existing experiment, not the arrival
times of a separately evaluated online picker. Real-time claims require a
separate causally processed/triggered study. A floor-zero target on a truly
zero signal is mathematical, not evidence of an earthquake's final size.

## Explicit CLI, with no automatic execution

Run from the repository root in the existing environment. First validate
target export on a small sample, which is permanently marked `smoke_only`:

```bash
CUDA_VISIBLE_DEVICES='' .venv/bin/python research/2026-10-09/phase2/train_future_growth.py export \
  --data /data --max-per-event 4 --sample-limit 64 \
  --output results/2026-10-09/phase2/growth_train_smoke64.npz
```

Then export the full baseline-selected training sample (four recordings per
event plus all M>=4 records), or omit `--max-per-event 4` to export all
training metadata rows. Existing target paths are never overwritten:

```bash
CUDA_VISIBLE_DEVICES='' .venv/bin/python research/2026-10-09/phase2/train_future_growth.py export \
  --data /data --max-per-event 4 \
  --output results/2026-10-09/phase2/growth_train_selected.npz
```

Only after reviewing the target manifest, invoke a chosen control explicitly:

```bash
.venv/bin/python research/2026-10-09/phase2/train_future_growth.py train \
  --targets results/2026-10-09/phase2/growth_train_selected.npz \
  --control supervised --seed 20261009 --epochs 10 --device cuda
```

Repeat matched controls/seeds as a separately authorized queue. The default
training sample is the same four-per-event-plus-tail sample as the current
independent runner, with inverse inclusion weights.
Preserve the original inferred numeric event-ID dtype during sampling:
lexicographic string sorting changes which groups consume each seeded draw.
IDs are converted to strings afterward for stored identity comparisons.
`--max-per-event 0`
trains on all rows and requires an all-row target archive. A sample-limited
archive requires `--allow-smoke-targets`; it trains on only its stored rows
and cannot estimate the full population, even though within-represented-event
weights are supplied. Do not compare smoke metrics with full-data results.

Each training invocation creates an immutable run directory containing
configuration and code identities, target manifest, training row indices,
loss history, a latest recovery artifact, the fixed final checkpoint,
validation metrics and mean/median predictions. Recovery artifacts do not
implement an automatic resume policy. No target generation is performed by
the training command. The deployed forward does not load this archive.

Focused CPU fixture tests:

```bash
CUDA_VISIBLE_DEVICES='' .venv/bin/python -m unittest discover -s tests -p test_future_growth.py -v
```

## Attribution and mathematical limits

Future-target multitask supervision and magnitude/intensity joint prediction
already exist; see [SeismNet (2024)](https://www.sciencedirect.com/science/article/abs/pii/S136791202400364X).
Distributional EEW architectures retaining log amplitude also predate this
work, for example [TEAM-LM](https://arxiv.org/abs/2101.02010). A fixed-amplitude
residual alone is especially close to [Zhang et al. (2021)](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2020GL089394).
None of these architectural ingredients is claimed as new here.

The optional marginal score has the standard mixture responsibility
`r_k=p_k q_k(G)/sum_j p_j q_j(G)` and logit derivative `p_k-r_k`. This
mechanism appears in [Jacobs et al. (1991)](https://people.eecs.berkeley.edu/~jordan/papers/mixtures-of-experts.pdf).
Adding magnitude, conditional-growth and growth-marginal NLL is an
overlapping composite score, not independent evidence; see
[Varin, Reid and Firth (2011)](https://utstat.utoronto.ca/reid/research/varin_reid_firth.pdf).
For correctly specified unrestricted models, its excess risk is a positive
sum of the magnitude KL, the class-weighted conditional-growth KL and the
growth-marginal KL. Correlation does not invalidate that consistency
statement, but the extra term repeats information. Stop-gradient removes
one feedback route and does not correct a misspecified teacher.

A local standard-library derivation and 5,000-repetition synthetic test were
completed before this implementation. In a fully labeled two-class problem
with 5% tail prevalence, n=250 and known growth probabilities `.1/.8`, adding
unit-weight marginal growth NLL increased probability-estimation variance by
10.17% (analytic asymptotic penalty 11.10%). The variance ratio is
`1+gamma^2*kappa*(1-kappa)/(1+gamma*kappa)^2 >= 1`, where `kappa` is the
growth-to-label information ratio. A saturated same-sample empirical joint
already matches its growth marginal, so adding that score changed nothing.
With a wrong frozen common-class growth probability `.02`, the population
tail prediction moved `.05 -> .08663`: artificial tail mean-prediction MAE
improved `2.85 -> 2.74010`, but overall MAE worsened `.285 -> .38391` and the
median stayed unchanged. These are negative synthetic controls, not
earthquake measurements. Established generative-learning bias failures are
also discussed by [Cozman et al. (2003)](https://aiinternational.org/Library/ICML/2003/icml03-016.php).

The intended test is therefore modest and falsifiable: improve both proper
distribution diagnostics and high-magnitude point error beyond ordinary
auxiliary supervision at matched overall MAE/MedAE and fixed 1/3/5-second
inputs. Report every seed/time and paired event uncertainty; M>=4 INSTANCE
support is not evidence about M7–9 extrapolation. If only the mixture score
helps by shifting all estimates upward, or if it loses to instrument-aware
controls, the hypothesized stronger method is unsupported. No superiority
or foundational-method claim follows from this implementation.

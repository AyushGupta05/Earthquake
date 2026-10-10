# Fixed ridge probe and scoring stage

This implements the frozen protocol v2 plus the dated kilometre metric-scale
addendum. It does not change descriptors, populations, masks, seeds or thresholds.
Real fits have not been launched. Synthetic tests fit constructed arrays only.

The fixed basis has127 input slots,128 ReLU features and an intercept. Every
arm uses the same matrix/bias draws for each of two seeds, and every horizon
uses the same predefined B/D/F masks. Input normalization, basis normalization,
and target normalization use only valid fitting rows and their original sampling
weights. Inputs are clipped at±8 before projection and unused slots are zeroed
after normalization. The basis is weighted-centered, permitting an exact
unpenalized intercept represented by the target mean. The255 other coefficients
per output minimize weighted-mean squared error plus0.01 squared coefficient
norm. All arms expose the same768 fitted coefficient/intercept slots.

Distance is trained as log10(max(Rhyp,1)); depth as log1p(depth). Predictions
are inverted exactly. Original-unit MAE is the primary geometry gate;
transformed errors are separately reported. Negative predicted depth and
predicted distance below depth are counted, not clipped. Nonfinite predictions
cause failure. Ensemble predictions average the two seeds in original units;
transformed-space ensemble reporting applies the exact transform to that mean.
It uses the equivalent log-sum-exp identity on retained seed log predictions,
so a finite negative depth that rounds to -1 does not create log1p(-1).

Metrics include weighted-record and unweighted-event-macro MAE/RMSE, weighted
magnitude MedAE/CVaR95, M≥4/M≥5 MAE and signed bias, counts, each unit/family
stratum, and event intersections represented in both held subsets. A weighted
median uses the first cumulative weight reaching0.5. CVaR95 includes exactly
the worst5% of weight, including fractional weight at its boundary.
Event-macro MAE first averages recording errors within each observed event.
Event-macro RMSE averages each event's within-event RMSE. Event-bootstrap
intervals use1000 fixed-seed event resamples with paired arms and retained
within-event rows. The reported95% interval is percentile[2.5%,97.5%]. This
does not model additional station dependence or repair waveform nonresponse.

The gate requires all six horizon/held-subset comparisons and a single geometry
target that passes across all six. It checks both seed tail deltas, ensemble
bulk/tail differences, bootstrap limits, independent tail event counts and
at least90% waveform response in fitting and evaluation populations. Empty
subsets or inconsistent event magnitude labels fail closed. There is no
hyperparameter, seed, horizon or ensemble selection.

`run_probe.py` has a dry-run default. A real invocation, after parent approval:

```
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
/home/ec2-user/Earthquake/.venv/bin/python run_probe.py \
  --cache /mnt/eew-research/runs/polarization_preflight_v2 \
  --output /mnt/eew-research/runs/polarization_probe_v2 --execute
```

The runner requires an extraction manifest marked complete, correct protocol,
metadata/inventory/importer pins, a matching features.npz SHA and descriptor
code hashes, exact feature schema/masks, per-horizon validity, identities, split
hashes and sampling weights. It writes every completed model, prediction and
score before continuing. Models persist all normalizers, masks, random draws
and ridge coefficients. Predictions persist source row, trace, event, station
group, subset, targets, weights and validity. The result includes source/code
hashes and all fixed settings. No original waveform source is opened by fitting.

A separate parent process enforces1800 wall-clock seconds across cache loading,
all18 fits, scoring and bootstrap. It terminates the worker even during BLAS,
then waits up to5 seconds before using a hard kill. Timeouts retain completed
artifacts, mark the run incomplete and prohibit a passing gate. There is no
automatic retry, reduced sample, changed hyperparameter or additional budget.
The extraction stage has its own parent-scheduled outer timeout.

Synthetic null/informative controls exercise the probe and bootstrap. A
constant-target null is an intentionally simple implementation check; one
realization is not an estimate of statistical false-positive rate. The
constructed informative case exposes the label only through a cross-component
slot and holds all marginal inputs fixed. Its success is not evidence that
these descriptors contain useful new earthquake information.

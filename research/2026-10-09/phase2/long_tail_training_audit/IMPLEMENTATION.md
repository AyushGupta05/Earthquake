# Six-band exposure controls: implementation

This is an implementation of an established sampler/prior correction control,
not a claim of a new method or an empirically calibrated posterior. Verification
so far uses synthetic CPU data only. No real waveform export, real fitting,
AWS launch, or held-data assessment is performed by these files.

## Fixed comparison

`exposure_training.py` accepts a caller-supplied `forward_prefix(batch, seconds)`
backbone and loader. It trains three controls from matching initial weights:

| Control | Replacement sampler | Loss | Deployment probability |
| --- | --- | --- | --- |
| `huber_ce` | Natural restoration mass | Magnitude-weighted Huber plus 0.075 CE | `softmax(z)` |
| `natural_ce` | Natural restoration mass | CE | `softmax(z)` |
| `band_exposure_ce` | Natural mass times band exposure factor | CE of `z + log(a)` | `softmax(z)` |

Labels are `floor(M / 0.1 + 1e-5)` with 66 categories; unsupported fit labels
fail. Bands contain labels 0–9, 10–19, 20–29, 30–39, 40–49 and 50–65. For each
deadline separately, `n[g]` is the fit restoration mass in band `g`, and
`a[k] = n[g(k)]**(-1/2)`. All six bands must have positive mass. Empty fine bins
remain in the 66-bin output and receive their band's finite correction; no
pseudocount claims to create examples.

If natural conditional probabilities are `p(k|x)`, the exposure conditional is
`q(k|x) = a[k]*p(k|x) / sum_j(a[j]*p(j|x))`. Minimizing exposure CE with logits
`z+log(a)` therefore admits natural `softmax(z)=p` at the population optimum.
This identity is not a finite-sample guarantee. Restoration weights enter the
sampler once and are not multiplied into the sampled loss again.

Training jointly averages separate 1/3/5-second losses. Each deadline draws
`max_t(N_fit_valid_t)` records with replacement per epoch, so the three horizons
have the same final batch remainder. The two natural-sampler controls consume
identical orders. The fixed schedule is ten epochs, batch 512, seeds 20261009 and
20261010, AdamW learning rate 0.0003 and decay 0.0001, cosine final learning rate
0.00003, gradient clip 5. All encoder parameters train. Deterministic Torch and
cuBLAS settings are recorded; TF32 settings are preserved.

## Shared B integration

`shared_response_adapter.bind_shared_response(dataset, normalizers, provenance,
model_class, fitting_digest)` binds an already-open immutable export. It creates
the native-late B model and enforces the agreed 380706 parameters. It verifies
export, implementation and normalizer-array hashes plus exact fit identities and
restoration weights, both for metadata statistics and separately at each valid
deadline. It does not discover data, export waveforms or fit normalizers.

The current shared export has scalar magnitude targets, float64 counts with
shape `[N,3,500]`, and independent validity masks for each deadline. Source rows
can be noncontiguous. The adapter maps them to storage positions without changing
the requested order or repeated samples. Only these four inputs reach the model:

| Input | Shape for batch B and deadline t |
| --- | --- |
| `counts` | `[B,3,100*t]` |
| `sensitivity` | `[B,3]` |
| `static` | `[B,34]` |
| `response` | `[B,72]` |

Labels, event identities and station identities remain outside `forward_prefix`.
The caller must supply the reviewed shared dataset/model/digest implementations;
the standalone callback API cannot certify arbitrary external code by itself.

```python
binding = bind_shared_response(dataset, normalizers, provenance,
                               model_class, fitting_digest)
fit_control(binding.model_factory, binding.loader, binding.plans,
            control, seed, new_output_directory, binding.identity,
            device="cuda")
```

This example is an integration interface, not authorization to start a run.

## Artifacts and assessment

Each completed epoch atomically replaces the checkpoint containing model,
optimizer, scheduler, all training RNG states, exact configuration and sampler
traces. `completed.json` is published last after fixed epoch ten. There is no
resume API or cross-runtime bitwise recovery claim in this prototype.

`evaluate_completed_grid` requires `identity=binding.identity` and
`population_validator=binding.validate_population` from the same shared binding
as the supplied factory and loader. It checks that identity against all
completed runs before any model creation or waveform load. It requires all six
fixed final runs and verifies artifact hashes, common data/config/runtime,
matching initialization and the two controls'
identical natural sampling orders before scoring. Initialization hashes are also
cross-checked against the hash-verified configurations. The caller supplies the six
held panels and archives the returned report and PMFs. No calibration fitting or
checkpoint selection occurs. PMF mean is primary; PMF median is secondary.
Reports contain every seed and equal-PMF ensemble, record and event metrics,
tail errors and reliability, exact continuous-target CRPS distinct from quantized
CDF score, paired event bootstrap intervals, unit/family strata and common-event
panel comparisons. The all-panel investment gate is fixed; sparse tail samples
are inconclusive. Unsupported held labels retain continuous error metrics and
have explicitly unavailable categorical scores.

The shared validator matches each complete held panel against its own export's
rows, event/station identities, targets, weights and deadline masks before
inference. It rejects substituted fitting-waveform IDs and held subselections.

## Synthetic verification and review boundary

Run from this directory:

```sh
/Users/ayush/.venvs/ml/bin/python3 -W error -m unittest -v test_exposure test_shared_response
```

The standalone tests exercise analytic sampling correction, empty fine bins,
support failures, deadline isolation, exact objectives and remainders, repeated
CPU updates, immutable completion checks and metric equations. The optional
shared integration tests build a wholly synthetic export and verify the actual B
callback, gradients and fit-only normalizer provenance. They skip when the shared
source files are absent, as they are in the isolated review bundle. Local test
receipts separately pin the dependency sources that were used.

The external review bundle contains only this implementation document, the three
implementation modules and two synthetic test modules. It excludes research audit
documents, shared response source/protocol material, real metadata and real data.

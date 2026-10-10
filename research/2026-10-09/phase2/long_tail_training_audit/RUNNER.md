# Fixed exposure grid runner

`run_exposure_grid.py` executes the frozen three objectives and two seeds with the
shared native-late B backbone. All ten epochs train all 1/3/5-second prefixes.
Control order is weighted Huber+CE, natural CE, then corrected exposure CE, with
seeds 20261009 and 20261010 for each. There are no epoch, objective, sampler,
threshold or seed tuning arguments. This is an established imbalance control.

The default is a dry run that does not read datasets or import the shared model.
The parent must first verify the completed export and reviewed source hashes.
The command below is a template; substitute the final reviewed identities and a
new output directory. `--execute` starts fitting under the process guard.

```sh
python run_exposure_grid.py \
  --export-dir /absolute/path/to/completed_export \
  --response-source /absolute/path/to/reviewed_response_code \
  --export-sha256 EXACT_EXPORT_MANIFEST_SHA256 \
  --model-sha256 EXACT_RESPONSE_MODEL_SHA256 \
  --data-sha256 EXACT_RESPONSE_DATA_SHA256 \
  --output /absolute/path/to/new_exposure_grid \
  --device cuda --threads 2 --max-seconds 14400 --execute
```

The maximum runtime covers source/cache checks, fit-only normalization, all six
fits and assessment. A fresh worker sets the fixed cuBLAS environment before
importing Torch. The supervisor sends TERM when the budget expires, then KILL
after at most 30 seconds. It also cleans up its child on SIGTERM or a Python
interruption. As with other process supervisors, SIGKILL of the supervisor cannot
run cleanup; the existing instance-stop guard remains the final backstop. The caller
should run under the project's existing durable logging and instance-stop guard;
this script does not create, stop or resize any AWS resource.

An output path must be new. Incomplete runs retain atomically saved completed
epochs. Successful execution requires both a complete `job_status.json` and the
hash-valid grid completion marker. No automatic resume is
implemented. A stopped partial next epoch is not presented as completed work.

Assessment starts only after all six final checkpoints pass completion,
initialization, order and identity checks. Every held panel is validated against
the same export's full valid row/label/weight/deadline metadata. The runner
preserves native units from `native_units` and derives channel family from the
exact six-category raw static one-hot fields. The validity gate uses the minimum
of fit and panel sampled-record fractions, matching the frozen diagnostic law;
restoration weights are used separately for the intended sampling/metrics.

`report.json` includes all seeds/ensembles, fixed metrics and comparisons,
fine bins absent from fit but occupied in held panels, out-of-support held labels,
validity denominators and evaluation runtime. `predictions.npz` preserves all 36
natural PMFs and exact panel IDs, targets, weights and reporting strata. Its
arrays contain no pickle objects. Normalizer arrays/provenance are saved once.
The final manifest hashes all report artifacts; `COMPLETE.json` is written last.
Both source and export hashes are checked again before assessment and publication.

Run the synthetic tests from this directory:

```sh
/Users/ayush/.venvs/ml/bin/python3 -W error -m unittest -v \
  test_exposure test_shared_response test_exposure_runner
```

The integration test runs the complete six-run path on newly generated synthetic
arrays with the actual shared B model, verifies all output hashes and PMFs, and
checks the fixed 380706-parameter architecture. This is evidence of executable
plumbing, not a real-data accuracy result or a CUDA numerical-equivalence claim.

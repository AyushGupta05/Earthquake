# Independent completed-distribution audit

This code reimplements the frozen response and exposure report checks without
importing either trainer's scoring or validation functions. Development and
tests use only newly invented arrays. Real result access requires a later,
explicit parent-authorized execution; no real predictions have been read here.

The CLI is dry-run unless `--execute` is present. The entire fixed grid must be
complete before any prediction array is decoded: eight response runs or six
exposure runs, with both seeds and all 1/3/5 s seen/held-station panels. Exact
source-contract, completed-grid and immutable export manifest SHA256 values are
required. Artifact bytes, metadata rows, normalizer provenance, recorded initial
state identities, runtime controls, ten-epoch schedules and sampler orders are
checked independently. The response permutation/cycle law is replayed in NumPy;
exposure replacement draws are replayed with a CPU Torch Generator and require
the recorded Torch version. Both require the actual final remainder, not a
rounded batch count. Checkpoints are hashed as opaque bytes and never unpickled.

The auditor decodes only export metadata and saved prediction PMFs. It does not
open counts, fit normalizers, run model inference, access original DEV/TEST,
change a job or discover alternative runs. It verifies all input/output hashes
declared by the fixed result schema, excluding the counts blob whose content
integrity belongs to the completed export audit. Source files are matched by
their previously pinned manifest identities, not imported or executed.

Every fixed seed and equal-PMF ensemble is scored for both PMF mean and median.
Replayed reported values include weighted MAE/MedAE/bias, event-macro errors,
individual events, M>=4/M>=5 tails, CVaR95, exact continuous-target CRPS,
categorical NLL, interval coverage and tail reliability. The independent CRPS
implementation integrates piecewise-constant CDFs against continuous truth;
quantized CRPS is a separate exposure score. Weighted P95 and maximum absolute
error are added as descriptive supplements. Candidate-minus-reference worst-error
contrasts cover both actions and seeds/ensemble; they never alter frozen gates.
A primary gate pass alone cannot establish the user's full objective when
worst-error behavior regresses.

The six response C-minus-B contrasts and twelve exposure C-minus-B/C-minus-A
contrasts are replayed, including the fixed 1,000 paired event bootstraps with
seed20261011. The exact gate and its support/precision statuses are then checked.
Response uses support0.0:0.1:6.5 and its stricter both-seed tail improvement rule.
Exposure uses0.05:0.1:6.55 and its frozen0.02 event-tail margin against each of two
controls. Supports, samplers, objectives and gates must not be merged. These are
exploratory investment criteria, not guarantees or published superiority tests.

Numeric report replay uses absolute tolerance2e-10, with no probability repair
and no threshold relaxation. PMF normalization retains the producer's1e-8
tolerance; complete PMF bytes remain hash-pinned. Unit/family/station stratum
metrics and common-event subpanels are deliberately outside this first bounded
audit. The main six panels and individual event metrics are checked. Recorded
checkpoint/model identities do not constitute an independent forward replay.

Example after parent authorization and completed-manifest pinning:

```sh
OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
timeout 600 /home/ec2-user/Earthquake/.venv/bin/python artifact_audit.py \
  --kind response --root /path/to/completed_grid \
  --grid-sha256 EXACT_COMPLETED_GRID_SHA \
  --export /mnt/eew-research/runs/response_prefix_export_v1 \
  --export-sha256 55ba19f81f59c106964ae92302258aba7780d5bc1a48cd3ec20617c8f2ba2a46 \
  --contract source_contract.json --contract-sha256 EXACT_CONTRACT_SHA \
  --output /own/audit/directory/new_receipt.json --execute
```

For exposure use its completed `manifest.json` hash; response uses
`grid_manifest.json`. Output must be new and is written only after a passing
audit. No script-internal AWS operations or resource changes exist. The external
timeout bounds CPU wall time; exit failure produces no passing receipt.

Focused synthetic tests:

```sh
/Users/ayush/.venvs/ml/bin/python3 -W error -m unittest -v test_distribution_audit
```

Fixtures exercise complete artifact schemas and wrong hashes, incomplete grids,
row reordering, deadline masks, matched versus balanced orders, nonfinite or
unnormalized PMFs, analytic weighted quantiles/CVaR, continuous versus quantized
CRPS, fixed paired bootstrap and gate boundaries. Source artifacts are pinned in
`source_contract.json`; no scientific dataset or result is bundled for review.

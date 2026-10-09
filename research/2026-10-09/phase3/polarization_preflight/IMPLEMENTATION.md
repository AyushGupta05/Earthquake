# Polarization information diagnostic: extraction implementation

This bundle implements protocol v2 metadata eligibility, identity-only sampling,
approximate native-unit conversion, and127 prefix descriptors. It does **not**
fit a model, export waveform arrays, or claim an earthquake accuracy improvement.
The fixed ridge fitting/scoring stage and its model-level null/bootstrap tests
remain a separate implementation gate. No real extraction has been run.

`extract_features.py` is deliberately a dry run unless `--execute` is present.
Production data paths and metadata/inventory/protocol hashes are pinned. There
is no validation/test argument or skip-verification switch. Parent must review
and authorize the real command before execution:

```
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 \
/home/ec2-user/Earthquake/.venv/bin/python extract_features.py \
  --output /mnt/eew-research/runs/polarization_preflight_v2 --execute
```

All Python modules in this directory plus protocol.md must be present together.
`instrument_inventory.py` is loaded from its pinned original location. h5py and
NumPy are the only extraction runtime libraries beyond Python's standard library.
The metadata cache is128MiB, matching the existing reviewed raw-HDF reader.
Metadata eligibility precedes sampling; waveform failure never triggers replacement.
Output directory creation fails if the directory already exists.

`features.npz` contains float64 features `[sample,deadline,127]`, deadlines1/3/5,
boolean validity, integer reason codes, covariance degeneracy flags, explicit
B/D/F masks, identities, unit strata, sensitivities, source-row indices, targets,
and original inverse record-sampling weights. Targets are `[M,Rhyp_km,depth_km]`
and never enter the descriptor function. Invalid features stay NaN. The later
fit must use the same valid rows for all arms at each deadline and mask unused
slots **after fit-only normalization**. No original CNN, posterior or normalizer
is imported. Incomplete extraction leaves `manifest.json` status `started`;
only a completed manifest with verified output hashes is fit-eligible.

`selected_metadata.csv` preserves the sampled source rows before waveform
inspection, including invalid rows. `station_groups.json` records conservative
co-location unions and missing coordinates. A full raw HDF SHA is deliberately
not computed; source path/stat/format are recorded and descriptor outputs are
hashed. This is weaker source integrity than a raw waveform checksum and is
explicit in the manifest. Input metadata, response archive, importer, protocol
and descriptor code are checked before/after extraction.

Protocol v2's evaluation cap salt is interpreted literally as
`polarization-fit-sample-v1eval`. Station aliases union across any recorded
epoch, even if epochs differ, conservatively limiting train/held overlap.
Undefined lag correlation is a uniform missing-feature rejection shared by all
arms; no undefined number is replaced with a physical zero. Leading covariance
direction degeneracy instead uses the preregistered six-zero encoding and flag.

The original51 formulas are recomputed on raw counts after prefix demeaning.
The synthetic parity check uses the existing Torch function extracted by AST,
without importing its training/data-access code. Its crossing fraction and FFT
frequency grid use float32, so numerical parity is checked at atol5e-8/rtol1e-7,
not claimed bitwise. This does not replay historical global input scaling.

Current tests check feature-level nulls and informative controls, exact schema,
gain/response co-transformation, marginal/sign contrasts, singular covariance,
per-deadline suffix causality, response windows/orientation/units, metadata
allowlisting, identity-based splitting, co-location union, sampling weights,
raw-HDF format and no-execute behavior. No claim about the later fitted probe
or bootstrap false-positive rate is made before its separate tests exist.

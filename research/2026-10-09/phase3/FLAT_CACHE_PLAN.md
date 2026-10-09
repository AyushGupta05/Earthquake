# Station-cache artifact and proposed later integration

Status: standalone exporter and readonly NumPy adapter only. The active HDF-backed TEAM run, trainer, recovery contract and selection protocol are unchanged. No real-data export or disk formatting has been performed by this module. The source cache and its metadata sidecars remain authoritative.

## Artifact contract

`flat_station_cache.py` exports **all original TRAIN events**, including the internal TRAIN calibration events, in original event-row and then original station-index order. Original DEV and TEST waveform arrays are excluded. The fitting subset is still explicitly selected later; storing internal calibration arrays in the same artifact does not authorize their use for optimization.

The exporter requires the externally pinned HDF cache and metadata CSV SHAs, its completed source manifest, verified CSV sidecar and sidecar manifest, matching chronological metadata and explicit HDF split lists. It requires raw finite float32 arrays with 100 Hz, first-P-minus-5-second timing and 1,000 or 3,000 samples. It copies each complete TRAIN event to a station-major `.npy` file, flushes it, and compares **every byte of every output tensor** to freshly read source arrays. It rechecks the source content and sidecar identities after export. This preserves signed zero and performs no normalization or resampling. Only the final atomic `manifest.json` publishes a completed artifact; interrupted directories are unusable and must not be resumed or overwritten automatically.

The manifest binds source-cache, source-manifest, original-source and metadata hashes; canonical event and station membership; exporter code SHA; derived-file SHA/size; shape, dtype and order. The reader requires both an externally recorded manifest SHA and the original source-cache SHA, hashes both derived files, and verifies their structure. An ordered fitting/calibration subset requires the expected station-membership digest, using the same JSON record encoding as `training_artifacts.station_membership`. Unknown, duplicate or DEV event IDs fail closed. Views are readonly; their lifetime can outlive the reader's `close()`.

The current full source contains 863,095 TRAIN station records. A float32 `[863095,3000,3]` map needs 31,071,420,000 waveform bytes (28.94 GiB) plus a small NPY header and index/manifest. This exceeds the worker's roughly 21 GiB root free space. Export belongs on a parent-approved task-owned disk. Instance storage is temporary: retain source data, completion identities, model checkpoints and evidence on durable storage; regenerate this derivative after its loss.

## Proposed execution contract — not implemented

A separate audited launcher is preferable to silently replacing the live dataset implementation. It must preserve the unchanged trainer source, model, sample order, complete arguments, random seeds/generators, cutoff and label-noise draws, batch sizes, partial batches, optimizer/scheduler and calibration/selection logic. Its explicit runtime provenance must additionally bind its own code SHA, adapter code SHA, flat manifest SHA, original HDF SHA, fitting and calibration membership digests, and the exact replaced call sites. Current `pretraining_implementation_sha256()` includes `StationDataset`; replacing that class changes the implementation identity and must never be hidden by returning an old hash.

The adapter should be used only for station pretraining and station calibration initially. Event training still needs coordinates, masks and multistation groups, which this artifact does not contain. Preserve the HDF-derived frame and counts as reference identities. Construct each subset in the exact original frame order, and compare `len`, labels and counts before creating a DataLoader. Convert readonly NumPy views to owned tensors (for example copy before `torch.from_numpy`) at the integration boundary; never give writable Torch operations a shared readonly map view. The adapter performs no RNG operations.

Reader unpickling currently revalidates and rehashes the whole artifact. This is intentionally conservative but can make spawned DataLoader workers expensive; the first backend comparison should keep the authoritative `workers=0` setting. Changing worker count, prefetching, copy policy or hash-validation policy requires its own measured and reviewed runtime contract.

## Proof required before any checkpoint migration

1. Under a fixed CPU environment, load a bounded deterministic list containing both fitting and calibration TRAIN stations. Compare raw arrays, float32 labels, batch ordering, partial batches and transformed cutoff tensors bitwise between original and flat loaders. Reproduce the actual epoch-seeded DataLoader order, not just sorted reads.
2. Starting from cloned model, optimizer, scheduler and all RNG states, run several pretraining updates including independently sampled cutoffs and label noise. Require exact losses, gradients, parameters, optimizer states and next RNG states. Verify calibration outputs and scheduler decisions. Repeat across an epoch checkpoint boundary and a short final partial batch.
3. On the intended CUDA environment, repeat the bounded update comparison with the exact deterministic launcher and recorded TF32 flags. A passing CPU test alone does not establish CUDA or arbitrary-runtime equivalence.
4. Before adopting an existing checkpoint, compare its immutable original configuration, code, runtime, data, order, optimizer/scheduler and selection state, and verify the new backend proof artifact. Keep the original checkpoint and identity intact. Introduce a **new versioned migration/recovery artifact** that pins the original checkpoint SHA and the added backend/proof identities. Do not disable or loosen `load_epoch_recovery` equality checks, patch old identity files, or relabel the changed process as an ordinary exact resume.
5. Subsequent resumes must require the same backend identity and proof chain. New seeds may share the verified raw cache; they do not share the training RNG or fit/calibration partition automatically. Encoder reuse remains subject to the existing full protocol and membership checks, with an explicit provenance extension if the implementation identity changes.

The current implementation proves artifact integrity and ordering only. It does not prove full training-update equivalence, speed improvement, model convergence or numerical equivalence to the authors' TensorFlow system.

## Export command template after disk approval

```sh
python research/2026-10-09/phase3/flat_station_cache.py \
  --source /mnt/eew-data/chile/chile_train_dev_full3000.hdf5 \
  --destination /PARENT_APPROVED_INSTANCE_STORE/chile-train-stations-v1 \
  --expected-source-cache-sha256 c59f7c7d2398b453a2aebf29fb713c44ddd0a2376cf2319a99e31ee3bb6c05cb \
  --expected-source-metadata-sha256 8840a482419afff5a54681beeb901e5a227e12e64cdf76b1faddf5b3d38285a1
```

Record the returned manifest SHA externally. Do not point this command at an existing destination. Export reads the full source cache twice for SHA validation, TRAIN arrays twice for copy/readback, and the derived file for its checksum, so it is a substantial sequential I/O workload. A future low-priority export requires parent scheduling; none has been dispatched.

## Focused validation

Twelve tests passed on the isolated dedicated-worker CPU directory in 0.262 s with Torch/GPU unused. The final Codex autoreview is clean after accepting and fixing externally pinned metadata authentication and exact timing validation. Tests use small HDF/CSV fixtures, including poisoned DEV arrays to detect accidental DEV reads, and exercise source/derived identity failures, bit preservation, canonical order, reordered subset membership, readonly lifetime, pickle reopening, nonfinite/dtype rejection and interrupted publication. The local system Python lacked h5py; no package was installed there. No real HDF was exported in these tests.

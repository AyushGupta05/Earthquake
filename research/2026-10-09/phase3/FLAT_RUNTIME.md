# Explicit flat station runtime and checkpoint migration

These new files leave the original trainer, model and general recovery validator unchanged:

- `flat_station_runtime.py` supplies owned float32 tensors from the verified readonly map and an explicit temporary installation context. It preserves station order, labels, calibration isolation and the original DataLoader. Only station pretraining and station calibration use the map; event fitting/evaluation retain the HDF backend.
- `flat_station_proof.py` compares the actual station training loop on two bounded epochs. It traces shuffled batches, raw/noised labels, cutoffs, losses, finite clipped gradients, model updates, Adam state, calibration at 1/3/5 seconds, scheduler and Python/NumPy/Torch/CUDA RNG. One path continues directly; the other restores a cloned completed-epoch snapshot before its second epoch. Each epoch has two full batches and one partial batch. Starting optimizer tensors are cloned because PyTorch's CPU optimizer loader may otherwise share their storage.
- `flat_station_migration.py` validates a versioned proof and creates a separate checkpoint and run identity at a completed epoch boundary.
- `run_team_flat.py` is the only intended execution entrypoint. It sets strict deterministic settings before importing Torch and preserves TF32. Its actions are `prove`, `prepare-migration` and `resume`.

The implementation fingerprint genuinely changes. It includes the replacement dataset source plus whole adapter/cache module hashes. Runtime provenance also includes all new launcher, proof and migration code hashes, the flat manifest and source identities, copy policy, NumPy version, deterministic/TF32 flags and migration lineage. Changing these values invalidates the proof or resumed configuration; there is no old-hash impersonation.

## Preconditions and isolation

Migration accepts only the original versioned **completed-epoch** checkpoint with `1 <= completed_epoch < pretrain_epochs`, unchanged complete histories, no imported encoder, no completed `run.json`, and workers=0. An intra-epoch partial state is never exact recovery. The old checkpoint SHA, old config and splits, original model/trainer hashes, hardware/runtime values, original deterministic-launch audit, new implementation and flat artifact must match the proof. CPU proof cannot authorize CUDA migration: the device and runtime records must agree exactly.

The origin checkpoint must remain pinned and unchanged while proof and migration preparation occur. The launcher rejects checksum changes; it does not stop or lock the live job. The parent must schedule a completed-epoch handoff and preserve the original checkpoint and run. No CUDA proof, full-data migration, or live run change has been launched during this implementation work.

Original flags are reconstructed from the origin configuration. All old config fields must remain equal except the explicit backend addition to runtime and its true pretraining implementation fingerprint. The new destination must be absent and inside the original output root. Preparation copies model/optimizer/scheduler/RNG/history/selection state into `migration_checkpoint.pth`, validates it through the unchanged `load_epoch_recovery`, and publishes a versioned `migration_manifest.json` last. The manifest pins both configs/runtimes, both implementation identities, origin checkpoint/audit, flat metadata/membership, proof and migrated checkpoint. Failed preparation never publishes completion.

Resumption requires an externally pinned migration-manifest SHA, unchanged backend proof/config and the preserved migration checkpoint. It then calls ordinary strict recovery for the selected new-run checkpoint. After the first resumed epoch, use the new run's `latest.pth`; the same migration manifest continues to bind its origin. Original checkpoint and identity files are never rewritten. This launcher currently handles migration and its subsequent resumes, not a new fresh-seed run.

## Scheduled proof and handoff commands

The placeholders below must be replaced with parent-recorded paths/hashes. The full flat export must already have a completed manifest. The source checksum is `c59f7c7d2398b453a2aebf29fb713c44ddd0a2376cf2319a99e31ee3bb6c05cb`.

```sh
/opt/pytorch/bin/python -u research/2026-10-09/phase3/run_team_flat.py \
  --action prove --device cuda \
  --flat-directory /mnt/eew-fast/chile-train-stations-v1 \
  --flat-manifest-sha256 FLAT_MANIFEST_SHA \
  --source-cache /mnt/eew-data/chile/chile_train_dev_full3000.hdf5 \
  --source-cache-sha256 c59f7c7d2398b453a2aebf29fb713c44ddd0a2376cf2319a99e31ee3bb6c05cb \
  --origin-checkpoint ORIGINAL_COMPLETED_EPOCH_CHECKPOINT \
  --origin-checkpoint-sha256 ORIGIN_SHA \
  --origin-determinism-audit ORIGINAL_LAUNCH_AUDIT \
  --origin-determinism-audit-sha256 AUDIT_SHA \
  --proof NEW_PROOF_JSON --proof-time-limit 120
```

The 120-second deadline bounds the update comparison, not the preceding full-file identity checks. A separate parent-owned process timeout must bound the whole command. Proof uses only original fitting and internal TRAIN calibration waveforms; DEV and TEST are not evaluated. It samples `2*pretrain_batch_size+1` fitting station indices spread deterministically over the fitting dataset and at most `pretrain_batch_size+1` calibration stations. The proof records these exact indices and the complete original fit/calibration membership digests.

Repeat the common arguments with `--action prepare-migration`, add `--proof-sha256 PROOF_SHA --migration-destination NEW_RUN_DIRECTORY`, and keep the same proof path, origin checkpoint and audit pins. This action stops before training and returns the migrated checkpoint path and completion-manifest SHA. Then use:

```sh
/opt/pytorch/bin/python -u research/2026-10-09/phase3/run_team_flat.py \
  --action resume --device cuda \
  --flat-directory /mnt/eew-fast/chile-train-stations-v1 \
  --flat-manifest-sha256 FLAT_MANIFEST_SHA \
  --source-cache /mnt/eew-data/chile/chile_train_dev_full3000.hdf5 \
  --source-cache-sha256 c59f7c7d2398b453a2aebf29fb713c44ddd0a2376cf2319a99e31ee3bb6c05cb \
  --resume-checkpoint NEW_RUN_DIRECTORY/migration_checkpoint.pth \
  --migration-manifest-sha256 MIGRATION_MANIFEST_SHA
```

Use durable logs, process and instance-stop guards, and the parent's GPU schedule. CUDA testing and checkpoint migration remain pending until separately scheduled.

## Interpretation

A passing proof is evidence of bitwise equality for its recorded runtime, checkpoint and bounded subsets, including the tested boundary restoration. It does not establish universal CUDA reproducibility, full-epoch timing, convergence or equivalence to the authors' TensorFlow implementation. Waveform bit preservation for every TRAIN tensor is separately enforced by the flat export. The original checkpoint did not record every possible environment property; the new backend adds explicit provenance, but cannot retroactively attest missing historical fields.

## Completed CPU validation

Nine focused tests passed on the isolated worker in 16.884 seconds with CUDA hidden and synthetic fixtures only. They include the actual station-loop bitwise comparison, strict rejection cases, immutable origin preservation, and subprocess proof -> prepare-only migration -> resume through fixture completion. The final isolated Codex autoreview returned no actionable findings. CUDA and real-checkpoint migration remain pending.

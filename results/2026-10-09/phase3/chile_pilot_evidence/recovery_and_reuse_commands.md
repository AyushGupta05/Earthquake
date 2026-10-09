# Exact recovery and encoder-reuse commands

These are prepared commands, not authorization to run concurrently with the current job. Execute on the dedicated worker. Confirm the original process has exited before recovery; retain the parent's timeout/OS-stop controls and redirect each invocation to a new log. Each audit path must be new.

Current immutable run: `/home/ec2-user/eew-work/full-runs/team_transformer_06742dc492a1_7ec986ada2e7`.

## Recovery

The first completed epoch must have created `latest.pth`. Keep every original trainer option, including25+100budgets; only add`--resume`. The checkpoint selects its saved stage/epoch and preserves optimizer,scheduler,RNG and checkpoint selection.

```bash
/opt/pytorch/bin/python -u /home/ec2-user/eew-work/Earthquake/research/2026-10-09/phase3/run_team_deterministic.py --determinism-audit /home/ec2-user/eew-work/full-logs/team_full_seed20261009_resume01.audit.json -- --cache /mnt/eew-data/chile/chile_train_dev_full3000.hdf5 --aggregation transformer --epochs 100 --pretrain-epochs 25 --batch-size 64 --pretrain-batch-size 64 --workers 0 --seed 20261009 --training-cutoff author --station-blinding author --event-label-smoothing --lr-schedule author-plateau --magnitude-resampling 2 --selection calibration-nll --output /home/ec2-user/eew-work/full-runs --resume /home/ec2-user/eew-work/full-runs/team_transformer_06742dc492a1_7ec986ada2e7/latest.pth
```

## Matched pooling control with the completed25-epoch encoder

Run only once all25 full-fit station epochs have finished and the encoder plus manifest exist. This uses the same seed, station sampling, cutoffs, label smoothing and TRAIN membership; import skips pretraining but requires the recorded25-epoch budget. Architecture changes to pooling and a new event model is fitted. DEV scoring remains after its completed fixed event budget and TRAIN-only selection. Do not use the incompatible two-epoch pilot encoder.

```bash
/opt/pytorch/bin/python -u /home/ec2-user/eew-work/Earthquake/research/2026-10-09/phase3/run_team_deterministic.py --determinism-audit /home/ec2-user/eew-work/full-logs/team_pool_shared_encoder_seed20261009.audit.json -- --cache /mnt/eew-data/chile/chile_train_dev_full3000.hdf5 --aggregation pool --epochs 100 --pretrain-epochs 25 --batch-size 64 --pretrain-batch-size 64 --workers 0 --seed 20261009 --training-cutoff author --station-blinding author --event-label-smoothing --lr-schedule author-plateau --magnitude-resampling 2 --selection calibration-nll --output /home/ec2-user/eew-work/full-runs --pretrained-encoder /home/ec2-user/eew-work/full-runs/team_transformer_06742dc492a1_7ec986ada2e7/pretrained_encoder.pth
```

The unchanged runner and wrapper must remain available at the recorded paths. New audit paths are excluded from the underlying trainer arguments, so recovery identity is unchanged. Exact GPU bitwise equivalence across different runtimes is not promised.

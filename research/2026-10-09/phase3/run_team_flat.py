"""Audited flat-station proof, migration preparation and strict resume launcher.

All operations are explicit. Preparation stops before model training. A new
backend never overwrites the original run or relaxes ordinary exact recovery.
"""
import argparse
import json
import os
from pathlib import Path
import sys


def trainer_arguments(config, resume):
    values = ('cache', 'aggregation', 'epochs', 'pretrain_epochs', 'batch_size', 'pretrain_batch_size',
              'workers', 'max_stations', 'station_drop', 'station_blinding', 'lr_schedule',
              'magnitude_resampling', 'seed', 'calibration_fraction', 'selection', 'training_cutoff',
              'pretrain_cutoff', 'density_epsilon', 'pretrain_density_epsilon', 'limit_fit_events',
              'limit_dev_events', 'output')
    arguments = []
    for name in values:
        arguments.extend(['--' + name.replace('_', '-'), str(config[name])])
    for name in ('event_label_smoothing', 'skip_dev'):
        if config[name]:
            arguments.append('--' + name.replace('_', '-'))
    if config.get('pretrained_encoder') is not None:
        raise ValueError('This migration launcher does not support imported-encoder origins')
    arguments.extend(['--resume', str(resume)])
    return arguments


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=('prove', 'prepare-migration', 'resume'), required=True)
    parser.add_argument('--flat-directory', type=Path, required=True)
    parser.add_argument('--flat-manifest-sha256', required=True)
    parser.add_argument('--source-cache', type=Path, required=True)
    parser.add_argument('--source-cache-sha256', required=True)
    parser.add_argument('--origin-checkpoint', type=Path)
    parser.add_argument('--origin-checkpoint-sha256')
    parser.add_argument('--origin-determinism-audit', type=Path)
    parser.add_argument('--origin-determinism-audit-sha256')
    parser.add_argument('--proof', type=Path)
    parser.add_argument('--proof-sha256')
    parser.add_argument('--proof-time-limit', type=float, default=120.)
    parser.add_argument('--migration-destination', type=Path)
    parser.add_argument('--resume-checkpoint', type=Path)
    parser.add_argument('--migration-manifest-sha256')
    parser.add_argument('--device', choices=('cpu', 'cuda'), required=True)
    args = parser.parse_args()
    if 'torch' in sys.modules:
        raise RuntimeError('The audited launcher must set cuBLAS configuration before importing Torch')
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
    import torch
    import train_team_lm as trainer
    from flat_station_cache import FlatStationCache, file_sha256
    from flat_station_runtime import backend_identity, install_flat_backend, strict_runtime
    from flat_station_migration import (PROOF_SCHEMA, create_migration, load_origin_checkpoint,
        read_pinned_json, validate_determinism_audit, validate_migrated_resume)
    from flat_station_proof import prove_updates
    from training_artifacts import atomic_json_save, json_sha256, station_membership
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    torch.set_num_threads(2)
    device = torch.device(args.device)
    if (device.type == 'cuda') != torch.cuda.is_available():
        raise ValueError('Device must match trainer auto-selection; hide CUDA explicitly for CPU proofs')
    flat = FlatStationCache(args.flat_directory, expected_manifest_sha256=args.flat_manifest_sha256,
                            expected_source_cache_sha256=args.source_cache_sha256)
    backend = backend_identity(flat, file_sha256(__file__))
    runtime = {'base': trainer.runtime_identity(device), 'strict': strict_runtime(), 'torch_version': str(torch.__version__)}
    old_implementation = trainer.pretraining_implementation_sha256()
    original_dataset = trainer.StationDataset
    if args.action == 'resume':
        if args.resume_checkpoint is None or args.migration_manifest_sha256 is None:
            raise ValueError('Resume requires its checkpoint and externally pinned migration manifest')
        manifest = read_pinned_json(args.resume_checkpoint.parent / 'migration_manifest.json', args.migration_manifest_sha256)
        config = manifest['old_config']
        lineage = manifest['new_config']['runtime']['station_backend']['lineage']
    else:
        if any(value is None for value in (args.origin_checkpoint, args.origin_checkpoint_sha256,
                args.origin_determinism_audit, args.origin_determinism_audit_sha256, args.proof)):
            raise ValueError('Proof/migration requires pinned origin checkpoint, deterministic audit and proof path')
        origin, split = load_origin_checkpoint(args.origin_checkpoint, args.origin_checkpoint_sha256)
        config = origin['config']
        audit = read_pinned_json(args.origin_determinism_audit, args.origin_determinism_audit_sha256)
        validate_determinism_audit(audit, config, strict_runtime())
        lineage = {'origin_checkpoint_sha256': args.origin_checkpoint_sha256,
                   'origin_determinism_audit_sha256': args.origin_determinism_audit_sha256,
                   'proof_sha256': args.proof_sha256}
    if (runtime['base'] != config['runtime'] or runtime['torch_version'] != config['torch_version']
            or Path(config['cache']).resolve() != args.source_cache.resolve()
            or config['cache_sha256'] != args.source_cache_sha256
            or config['metadata_sidecar_sha256'] != flat.manifest['source_identity']['source_metadata_sha256']
            or config['pretraining_identity']['implementation_sha256'] != old_implementation
            or any(file_sha256(Path(__file__).with_name(name)) != sha for name, sha in config['source_sha256_files'].items())):
        raise ValueError('Original code, cache, metadata, implementation or runtime changed')
    print(json.dumps({'action': args.action, 'backend': backend, 'runtime': runtime, 'lineage': lineage}), flush=True)
    with install_flat_backend(trainer, flat, args.source_cache, identity=backend, lineage=lineage):
        new_implementation = trainer.pretraining_implementation_sha256()
        if args.action == 'prove':
            if args.proof.exists() or not 1 <= args.proof_time_limit <= 300:
                raise ValueError('Proof needs a new output path and a 1..300 second training deadline')
            metadata, source_manifest = trainer.load_verified_metadata(args.source_cache)
            if (source_manifest['sha256'] != args.source_cache_sha256
                    or source_manifest['metadata_sidecar_sha256'] != config['metadata_sidecar_sha256']
                    or source_manifest['metadata_sidecar_manifest_sha256'] != config['metadata_sidecar_manifest_sha256']):
                raise ValueError('Source cache or metadata identity changed')
            events = {}
            for name in ('fit', 'calibration'):
                ids = split[name]['event_ids']
                frame = metadata.set_index('EVENT', drop=False).loc[ids].reset_index(drop=True)
                if frame.source_row_index.tolist() != split[name]['source_rows']:
                    raise ValueError('Proof split source rows changed')
                events[name] = trainer.EventDataset(args.source_cache, frame, training=name == 'fit',
                    seed=config['seed'], stored_samples=config['stored_samples'])
                if station_membership(events[name]) != config['pretraining_identity'][name + '_stations']:
                    raise ValueError('Proof must retain the complete original TRAIN partition identities')
            try:
                report = prove_updates(trainer, origin,
                    original_dataset(events['fit']), original_dataset(events['calibration'], calibration=True),
                    trainer.StationDataset(events['fit']), trainer.StationDataset(events['calibration'], calibration=True),
                    device=device, max_seconds=args.proof_time_limit)
            finally:
                for dataset in events.values():
                    dataset.close()
            proof = {'schema': PROOF_SCHEMA, 'passed': True, 'origin_checkpoint_sha256': args.origin_checkpoint_sha256,
                     'origin_determinism_audit_sha256': args.origin_determinism_audit_sha256,
                     'old_config_sha256': json_sha256(config), 'backend': backend,
                     'old_implementation_sha256': old_implementation, 'new_implementation_sha256': new_implementation,
                     'runtime': runtime, 'fit_membership': config['pretraining_identity']['fit_stations'],
                     'calibration_membership': config['pretraining_identity']['calibration_stations'], **report}
            args.proof.parent.mkdir(parents=True, exist_ok=True)
            atomic_json_save(proof, args.proof)
            print(json.dumps({'proof': str(args.proof), 'proof_sha256': file_sha256(args.proof), 'report': report}), flush=True)
            return
        original_loader = trainer.load_epoch_recovery
        class Prepared(Exception):
            pass
        def load(path, new_config, split_manifest):
            if args.action == 'prepare-migration':
                if args.migration_destination is None or args.proof_sha256 is None:
                    raise ValueError('Migration requires a fresh destination and externally pinned proof')
                checkpoint, manifest_sha = create_migration(path, args.migration_destination,
                    origin_sha256=args.origin_checkpoint_sha256, origin_audit_sha256=args.origin_determinism_audit_sha256,
                    proof_path=args.proof, proof_sha256=args.proof_sha256, new_config=new_config, split_manifest=split_manifest,
                    backend=backend, old_implementation=old_implementation, new_implementation=new_implementation,
                    runtime=runtime, atomic_save=trainer.atomic_save)
                print(json.dumps({'migration_checkpoint': str(checkpoint), 'migration_manifest_sha256': manifest_sha}), flush=True)
                raise Prepared()
            return validate_migrated_resume(path, manifest_sha256=args.migration_manifest_sha256, config=new_config,
                split_manifest=split_manifest, backend=backend, old_implementation=old_implementation,
                new_implementation=new_implementation, runtime=runtime)
        trainer.load_epoch_recovery = load
        previous_argv = sys.argv
        checkpoint = args.origin_checkpoint if args.action == 'prepare-migration' else args.resume_checkpoint
        sys.argv = [str(Path(trainer.__file__))] + trainer_arguments(config, checkpoint)
        try:
            trainer.main()
        except Prepared:
            pass
        finally:
            trainer.load_epoch_recovery = original_loader
            sys.argv = previous_argv
    flat.close()


if __name__ == '__main__':
    main()

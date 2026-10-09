"""Versioned, allowlisted migration at a completed pretraining epoch boundary.

This does not relax the general trainer recovery checks. It creates a new run
and validates its checkpoint through those unchanged checks. Provenance records
are evidence from a trusted experiment operator, not remote attestation.
"""
import copy
import json
from pathlib import Path

import torch

from flat_station_cache import file_sha256
from flat_station_proof import proof_batch_plan
from training_artifacts import atomic_json_save, json_sha256, load_epoch_recovery

MIGRATION_SCHEMA = 'team-flat-checkpoint-migration-v1'
PROOF_SCHEMA = 'team-flat-update-equivalence-v1'


def read_pinned_json(path, expected_sha256):
    path = Path(path)
    data = path.read_bytes()
    import hashlib
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('JSON evidence differs from its externally pinned SHA')
    return json.loads(data)


def load_origin_checkpoint(path, expected_sha256):
    path = Path(path).resolve()
    if file_sha256(path) != expected_sha256:
        raise ValueError('Origin checkpoint does not match its pinned identity')
    payload = torch.load(path, map_location='cpu', weights_only=True)
    split = json.loads((path.parent / 'split_manifest.json').read_text())
    payload, _ = load_epoch_recovery(path, payload['config'], split)
    config = payload['config']
    if (payload['stage'] != 'pretrain' or not 1 <= payload['completed_epoch'] < config['pretrain_epochs']
            or config.get('pretrained_encoder') is not None or config.get('workers') != 0
            or 'station_backend' in config['runtime']):
        raise ValueError('Migration requires an original HDF completed epoch inside unfinished pretraining, workers=0')
    if file_sha256(path) != expected_sha256:
        raise ValueError('Origin checkpoint changed while it was being validated')
    return payload, split


def validate_determinism_audit(audit, config, actual_flags):
    if (audit.get('schema') != 'team-deterministic-launch-v1'
            or audit.get('runner_sha256') != config['source_sha256_files']['train_team_lm.py']
            or audit.get('torch_version') != config['torch_version']
            or any(audit.get(key) != value for key, value in actual_flags.items())):
        raise ValueError('Origin deterministic-launch audit does not match this execution context')
    if (not actual_flags['deterministic_algorithms'] or actual_flags['deterministic_warn_only']
            or not actual_flags['cudnn_deterministic'] or actual_flags['cudnn_benchmark']
            or actual_flags['cublas_workspace_config'] != ':4096:8'):
        raise ValueError('Migration proof requires the strict original deterministic launcher settings')


def validate_proof(proof, *, origin_sha256, origin_audit_sha256, old_config, backend, old_implementation, new_implementation, runtime):
    identities = old_config['pretraining_identity']
    plan = proof_batch_plan(identities['fit_stations']['records'], identities['calibration_stations']['records'],
                            old_config['pretrain_batch_size'])
    required = {'schema': PROOF_SCHEMA, 'passed': True, 'origin_checkpoint_sha256': origin_sha256,
                'origin_determinism_audit_sha256': origin_audit_sha256,
                'old_config_sha256': json_sha256(old_config), 'backend': backend,
                'old_implementation_sha256': old_implementation,
                'new_implementation_sha256': new_implementation, 'runtime': runtime,
                'epoch_boundary_restore_tested': True, **plan,
                'cutoff_and_label_noise_traced': True}
    if any(proof.get(key) != value for key, value in required.items()):
        raise ValueError('Equivalence proof is not for this checkpoint, backend, implementation and runtime')
    if proof.get('epochs') != 2 or proof.get('steps_per_epoch') != len(plan['fit_batch_sizes']):
        raise ValueError('Proof must cover two epochs, multiple updates and an epoch-boundary restore')
    checks = proof.get('checks', {})
    expected = {'batch_and_noise_trace', 'loss_gradient_update_trace', 'model_optimizer_scheduler_rng', 'calibration'}
    if set(checks) != expected or any(not isinstance(value, dict) or set(value) != {'original', 'flat'}
            or not isinstance(value['original'], str) or len(value['original']) != 64
            or value['original'] != value['flat'] for value in checks.values()):
        raise ValueError('Equivalence proof must contain equal complete trace hashes')
    if (proof.get('fit_membership') != identities['fit_stations']
            or proof.get('calibration_membership') != identities['calibration_stations']):
        raise ValueError('Proof does not bind the original fitting/calibration station memberships')


def validate_transition(old_config, new_config, *, backend, lineage, old_implementation, new_implementation):
    if old_config['pretraining_identity']['implementation_sha256'] != old_implementation:
        raise ValueError('Origin implementation differs from the current original trainer')
    expected = copy.deepcopy(old_config)
    expected['runtime']['station_backend'] = {**copy.deepcopy(backend), 'lineage': copy.deepcopy(lineage)}
    expected['pretraining_identity']['implementation_sha256'] = new_implementation
    if new_config != expected:
        raise ValueError('Migration may change only the explicit station backend and its true implementation fingerprint')


def create_migration(origin_path, destination, *, origin_sha256, origin_audit_sha256, proof_path, proof_sha256,
                     new_config, split_manifest, backend, old_implementation, new_implementation, runtime,
                     atomic_save):
    """Publish a new checkpoint/run; never modify the original checkpoint/run."""
    origin_path, destination = Path(origin_path).resolve(), Path(destination).resolve()
    old, old_split = load_origin_checkpoint(origin_path, origin_sha256)
    if split_manifest != old_split or destination.exists() or destination.parent != Path(old['config']['output']).resolve():
        raise ValueError('Migration needs the unchanged split and a fresh directory under the original output root')
    proof = read_pinned_json(proof_path, proof_sha256)
    validate_proof(proof, origin_sha256=origin_sha256, origin_audit_sha256=origin_audit_sha256,
                   old_config=old['config'], backend=backend, old_implementation=old_implementation,
                   new_implementation=new_implementation, runtime=runtime)
    lineage = {'origin_checkpoint_sha256': origin_sha256, 'origin_determinism_audit_sha256': origin_audit_sha256,
               'proof_sha256': proof_sha256}
    validate_transition(old['config'], new_config, backend=backend, lineage=lineage,
                        old_implementation=old_implementation, new_implementation=new_implementation)
    destination.mkdir(parents=True, exist_ok=False)
    payload = dict(old, config=copy.deepcopy(new_config), run_directory=str(destination))
    checkpoint = destination / 'migration_checkpoint.pth'
    atomic_json_save(new_config, destination / 'identity.json')
    atomic_json_save(split_manifest, destination / 'split_manifest.json')
    atomic_save(payload, checkpoint)
    # The generic exact-resume validator stays unchanged and must accept the
    # newly explicit identity before a completion manifest can be published.
    load_epoch_recovery(checkpoint, new_config, split_manifest)
    if file_sha256(origin_path) != origin_sha256:
        raise ValueError('Origin changed before migration completion; new directory remains unpublished')
    manifest = {'schema': MIGRATION_SCHEMA, 'complete': True, 'origin_checkpoint': str(origin_path),
                'origin_checkpoint_sha256': origin_sha256, 'origin_determinism_audit_sha256': origin_audit_sha256,
                'proof_sha256': proof_sha256, 'proof': proof, 'backend': backend,
                'old_config': old['config'], 'new_config': new_config,
                'old_config_sha256': json_sha256(old['config']), 'new_config_sha256': json_sha256(new_config),
                'old_implementation_sha256': old_implementation, 'new_implementation_sha256': new_implementation,
                'old_runtime': old['config']['runtime'], 'new_runtime': new_config['runtime'],
                'split_manifest_sha256': json_sha256(split_manifest), 'stage': old['stage'],
                'completed_epoch': old['completed_epoch'], 'checkpoint_sha256': file_sha256(checkpoint),
                'run_directory': str(destination)}
    atomic_json_save(manifest, destination / 'migration_manifest.json')
    return checkpoint, file_sha256(destination / 'migration_manifest.json')


def validate_migrated_resume(path, *, manifest_sha256, config, split_manifest, backend, old_implementation, new_implementation, runtime):
    """Additional migration lineage checks, followed by ordinary strict recovery."""
    path = Path(path).resolve()
    manifest = read_pinned_json(path.parent / 'migration_manifest.json', manifest_sha256)
    lineage = config['runtime']['station_backend']['lineage']
    if (manifest.get('schema') != MIGRATION_SCHEMA or manifest.get('complete') is not True
            or manifest.get('run_directory') != str(path.parent) or manifest.get('new_config') != config
            or manifest.get('backend') != backend
            or manifest.get('new_config_sha256') != json_sha256(config)
            or manifest.get('old_config_sha256') != json_sha256(manifest['old_config'])
            or manifest.get('split_manifest_sha256') != json_sha256(split_manifest)
            or file_sha256(path.parent / 'migration_checkpoint.pth') != manifest.get('checkpoint_sha256')):
        raise ValueError('Migrated resume requires the pinned completed migration and unchanged backend/config')
    validate_transition(manifest['old_config'], config, backend=backend, lineage=lineage,
                        old_implementation=old_implementation, new_implementation=new_implementation)
    validate_proof(manifest['proof'], origin_sha256=lineage['origin_checkpoint_sha256'],
                   origin_audit_sha256=lineage['origin_determinism_audit_sha256'], old_config=manifest['old_config'],
                   backend=backend, old_implementation=old_implementation, new_implementation=new_implementation, runtime=runtime)
    return load_epoch_recovery(path, config, split_manifest)

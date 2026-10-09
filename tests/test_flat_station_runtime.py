"""CPU proof of the real station training step and strict migration boundaries."""
import copy
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':4096:8'
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / 'research/2026-10-09/phase3'))
import train_team_lm as trainer
from test_team_training import fixture
from flat_station_cache import FlatStationCache, export_flat_station_cache, file_sha256
from flat_station_runtime import backend_identity, install_flat_backend, strict_runtime
from flat_station_migration import (PROOF_SCHEMA, create_migration, load_origin_checkpoint,
    validate_migrated_resume, validate_proof, validate_transition, validate_determinism_audit)
from flat_station_proof import prove_updates, state_digest
from training_artifacts import atomic_json_save, json_sha256, load_epoch_recovery
from run_team_flat import trainer_arguments


class FlatStationRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)
        torch.use_deterministic_algorithms(True, warn_only=False)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.source, cls.frame, source_manifest = fixture(cls.root)
        cls.source_sha = source_manifest['sha256']
        cls.flat_dir = cls.root / 'flat'
        exported = export_flat_station_cache(cls.source, cls.flat_dir,
            expected_source_cache_sha256=cls.source_sha,
            expected_source_metadata_sha256=file_sha256(Path(str(cls.source) + '.metadata.csv')))
        cls.flat = FlatStationCache(cls.flat_dir, expected_manifest_sha256=exported['manifest_sha256'],
                                    expected_source_cache_sha256=cls.source_sha)
        original_save = trainer.atomic_save
        class CompleteEpoch(Exception):
            pass
        def save_and_stop(payload, path):
            original_save(payload, path)
            if payload.get('stage') == 'pretrain' and payload['completed_epoch'] == 1:
                cls.origin_path = Path(path)
                raise CompleteEpoch()
        argv = ['train_team_lm.py', '--cache', str(cls.source), '--aggregation', 'pool', '--epochs', '2',
                '--pretrain-epochs', '3', '--pretrain-batch-size', '2', '--batch-size', '2', '--workers', '0',
                '--lr-schedule', 'author-plateau', '--training-cutoff', 'discrete', '--selection', 'calibration-nll',
                '--skip-dev', '--output', str(cls.root / 'runs')]
        with patch.object(sys, 'argv', argv), patch.object(trainer, 'atomic_save', side_effect=save_and_stop):
            try:
                trainer.main()
            except CompleteEpoch:
                pass
        cls.origin_sha = file_sha256(cls.origin_path)
        cls.origin, cls.split = load_origin_checkpoint(cls.origin_path, cls.origin_sha)
        cls.config = cls.origin['config']
        cls.original_dataset = trainer.StationDataset
        cls.old_impl = trainer.pretraining_implementation_sha256()
        cls.backend = backend_identity(cls.flat, file_sha256(Path(trainer.__file__).with_name('run_team_flat.py')))
        cls.runtime = {'base': trainer.runtime_identity(torch.device('cpu')), 'strict': strict_runtime(), 'torch_version': str(torch.__version__)}
        cls.audit = {'schema': 'team-deterministic-launch-v1', 'runner_sha256': cls.config['source_sha256_files']['train_team_lm.py'],
                     'torch_version': cls.config['torch_version'], **strict_runtime()}
        cls.audit_path = cls.root / 'origin_audit.json'
        atomic_json_save(cls.audit, cls.audit_path)
        cls.audit_sha = file_sha256(cls.audit_path)
        cls.events = {}
        for name in ('fit', 'calibration'):
            frame = cls.frame.set_index('EVENT', drop=False).loc[cls.split[name]['event_ids']].reset_index(drop=True)
            cls.events[name] = trainer.EventDataset(cls.source, frame, training=name == 'fit', stored_samples=1000)
        with install_flat_backend(trainer, cls.flat, cls.source, identity=cls.backend, lineage={}):
            cls.new_impl = trainer.pretraining_implementation_sha256()
            report = prove_updates(trainer, cls.origin,
                cls.original_dataset(cls.events['fit']), cls.original_dataset(cls.events['calibration'], calibration=True),
                trainer.StationDataset(cls.events['fit']), trainer.StationDataset(cls.events['calibration'], calibration=True),
                device=torch.device('cpu'), max_seconds=90)
        cls.proof = {'schema': PROOF_SCHEMA, 'passed': True, 'origin_checkpoint_sha256': cls.origin_sha,
                     'origin_determinism_audit_sha256': cls.audit_sha, 'old_config_sha256': json_sha256(cls.config),
                     'backend': cls.backend, 'old_implementation_sha256': cls.old_impl, 'new_implementation_sha256': cls.new_impl,
                     'runtime': cls.runtime, 'fit_membership': cls.config['pretraining_identity']['fit_stations'],
                     'calibration_membership': cls.config['pretraining_identity']['calibration_stations'], **report}
        cls.proof_path = cls.root / 'proof.json'
        atomic_json_save(cls.proof, cls.proof_path)
        cls.proof_sha = file_sha256(cls.proof_path)
        cls.lineage = {'origin_checkpoint_sha256': cls.origin_sha, 'origin_determinism_audit_sha256': cls.audit_sha,
                       'proof_sha256': cls.proof_sha}
        cls.new_config = copy.deepcopy(cls.config)
        cls.new_config['runtime']['station_backend'] = {**cls.backend, 'lineage': cls.lineage}
        cls.new_config['pretraining_identity']['implementation_sha256'] = cls.new_impl

    @classmethod
    def tearDownClass(cls):
        for event in cls.events.values():
            event.close()
        cls.flat.close()
        cls.directory.cleanup()

    def test_actual_batch_cutoff_noise_loss_gradient_update_and_rng_equivalence(self):
        self.assertEqual(self.proof['steps_per_epoch'], 3)
        self.assertTrue(self.proof['partial_batch_tested'])
        self.assertTrue(self.proof['epoch_boundary_restore_tested'])
        for trace in self.proof['checks'].values():
            self.assertEqual(trace['original'], trace['flat'])
        self.assertTrue((self.events['fit'].frame.MA > 4).any())
        self.assertEqual(file_sha256(self.origin_path), self.origin_sha)

    def test_context_records_changed_implementation_and_owns_tensor_storage(self):
        before = trainer.runtime_identity(torch.device('cpu'))
        with install_flat_backend(trainer, self.flat, self.source, identity=self.backend, lineage=self.lineage):
            self.assertNotEqual(trainer.pretraining_implementation_sha256(), self.old_impl)
            self.assertEqual(trainer.runtime_identity(torch.device('cpu'))['station_backend']['lineage'], self.lineage)
            dataset = trainer.StationDataset(self.events['fit'])
            original = dataset[0][0].clone()
            writable = dataset[0][0]
            writable.fill_(123.)
            self.assertTrue(torch.equal(dataset[0][0], original))
            with self.assertRaises(RuntimeError):
                with install_flat_backend(trainer, self.flat, self.source, identity=self.backend, lineage={}):
                    pass
        self.assertIs(trainer.StationDataset, self.original_dataset)
        self.assertEqual(trainer.pretraining_implementation_sha256(), self.old_impl)
        self.assertEqual(trainer.runtime_identity(torch.device('cpu')), before)

    def test_migration_keeps_original_state_and_passes_unchanged_strict_recovery(self):
        destination = self.root / 'runs' / 'migrated'
        checkpoint, manifest_sha = create_migration(self.origin_path, destination,
            origin_sha256=self.origin_sha, origin_audit_sha256=self.audit_sha, proof_path=self.proof_path,
            proof_sha256=self.proof_sha, new_config=self.new_config, split_manifest=self.split,
            backend=self.backend, old_implementation=self.old_impl, new_implementation=self.new_impl,
            runtime=self.runtime, atomic_save=trainer.atomic_save)
        loaded, out = load_epoch_recovery(checkpoint, self.new_config, self.split)
        self.assertEqual(out, destination)
        unchanged = set(self.origin) - {'config', 'run_directory'}
        self.assertEqual(state_digest({k: loaded[k] for k in unchanged}), state_digest({k: self.origin[k] for k in unchanged}))
        self.assertEqual(file_sha256(self.origin_path), self.origin_sha)
        validate_migrated_resume(checkpoint, manifest_sha256=manifest_sha, config=self.new_config, split_manifest=self.split,
            backend=self.backend, old_implementation=self.old_impl, new_implementation=self.new_impl, runtime=self.runtime)
        with self.assertRaises(ValueError):
            load_epoch_recovery(checkpoint, self.config, self.split)
        with self.assertRaises(ValueError):
            validate_migrated_resume(checkpoint, manifest_sha256='wrong', config=self.new_config, split_manifest=self.split,
                backend=self.backend, old_implementation=self.old_impl, new_implementation=self.new_impl, runtime=self.runtime)

    def test_config_transition_rejects_any_non_backend_change(self):
        for field, value in [('epochs', 9), ('seed', 13), ('cache_sha256', 'changed'), ('batch_size', 5)]:
            changed = copy.deepcopy(self.new_config)
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_transition(self.config, changed, backend=self.backend, lineage=self.lineage,
                    old_implementation=self.old_impl, new_implementation=self.new_impl)

    def test_proof_rejects_mismatched_origin_runtime_membership_and_failed_comparison(self):
        for change in ('origin', 'runtime', 'membership', 'trace', 'partial'):
            proof = copy.deepcopy(self.proof)
            if change == 'origin':
                proof['origin_checkpoint_sha256'] = 'different'
            elif change == 'runtime':
                proof['runtime']['base']['threads'] += 1
            elif change == 'membership':
                proof['fit_membership']['records'] -= 1
            elif change == 'trace':
                proof['checks']['loss_gradient_update_trace']['flat'] = '0' * 64
            else:
                proof['partial_batch_tested'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_proof(proof, origin_sha256=self.origin_sha, origin_audit_sha256=self.audit_sha, old_config=self.config,
                    backend=self.backend, old_implementation=self.old_impl, new_implementation=self.new_impl, runtime=self.runtime)

    def test_intra_epoch_or_finished_pretraining_origins_are_rejected(self):
        for completed in (0, self.config['pretrain_epochs']):
            directory = self.root / f'bad_origin_{completed}'
            directory.mkdir()
            altered = copy.deepcopy(self.origin)
            altered['run_directory'] = str(directory)
            altered['completed_epoch'] = completed
            altered['run_state']['pretrain_history'] = [{'epoch': i + 1} for i in range(completed)]
            atomic_json_save(self.config, directory / 'identity.json')
            atomic_json_save(self.split, directory / 'split_manifest.json')
            path = directory / 'latest.pth'
            trainer.atomic_save(altered, path)
            with self.assertRaises(ValueError):
                load_origin_checkpoint(path, file_sha256(path))

    def test_tf32_and_determinism_are_bound_to_origin_audit(self):
        validate_determinism_audit(self.audit, self.config, strict_runtime())
        changed = copy.deepcopy(self.audit)
        changed['cuda_matmul_allow_tf32'] = not changed['cuda_matmul_allow_tf32']
        with self.assertRaises(ValueError):
            validate_determinism_audit(changed, self.config, strict_runtime())

    def test_launcher_proof_preparation_and_resume_end_to_end_cpu(self):
        launcher = Path(trainer.__file__).with_name('run_team_flat.py')
        common = [sys.executable, str(launcher), '--flat-directory', str(self.flat_dir),
            '--flat-manifest-sha256', self.flat.expected_manifest_sha256,
            '--source-cache', str(self.source), '--source-cache-sha256', self.source_sha, '--device', 'cpu']
        proof_path = self.root / 'cli_proof.json'
        origin = ['--origin-checkpoint', str(self.origin_path), '--origin-checkpoint-sha256', self.origin_sha,
            '--origin-determinism-audit', str(self.audit_path), '--origin-determinism-audit-sha256', self.audit_sha,
            '--proof', str(proof_path)]
        def run(arguments):
            result = subprocess.run(common + arguments, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        run(['--action', 'prove', *origin, '--proof-time-limit', '60'])
        destination = self.root / 'runs' / 'cli_migrated'
        run(['--action', 'prepare-migration', *origin, '--proof-sha256', file_sha256(proof_path),
             '--migration-destination', str(destination)])
        self.assertFalse((destination / 'latest.pth').exists())
        self.assertFalse((destination / 'run.json').exists())
        self.assertEqual(file_sha256(self.origin_path), self.origin_sha)
        manifest_path = destination / 'migration_manifest.json'
        run(['--action', 'resume', '--resume-checkpoint', str(destination / 'migration_checkpoint.pth'),
             '--migration-manifest-sha256', file_sha256(manifest_path)])
        self.assertTrue((destination / 'run.json').exists())
        latest = torch.load(destination / 'latest.pth', map_location='cpu', weights_only=True)
        self.assertEqual(latest['stage'], 'event')
        self.assertEqual(latest['completed_epoch'], self.config['epochs'])
        self.assertEqual(len(latest['run_state']['pretrain_history']), self.config['pretrain_epochs'])
        self.assertEqual(file_sha256(self.origin_path), self.origin_sha)
        self.assertFalse((self.origin_path.parent / 'run.json').exists())

    def test_argument_reconstruction_preserves_protocol_and_uses_explicit_resume(self):
        arguments = trainer_arguments(self.config, self.origin_path)
        self.assertIn('--skip-dev', arguments)
        self.assertEqual(arguments[-2:], ['--resume', str(self.origin_path)])
        self.assertEqual(arguments[arguments.index('--pretrain-epochs') + 1], '3')


if __name__ == '__main__':
    unittest.main()

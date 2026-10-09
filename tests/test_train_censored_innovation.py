from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import h5py
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/2026-10-09/phase2'))
import train_censored_innovation as runner
from test_instrument_residual import synthetic_data, row, epoch


class RunnerTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)

    def fixture(self, root):
        inventory = runner.source.Inventory([epoch(c) for c in 'ENZ'])
        (root / 'inventory.tgz').write_bytes(b'fixture archive replaced by explicit test inventory')
        mean, std = np.array([10., 20., 30.], dtype=np.float32), np.array([3., 4., 5.], dtype=np.float32)
        np.save(root / 'train_mean_full.npy', mean)
        np.save(root / 'train_std_full.npy', std)
        frames, arrays, traces, data = {}, {}, {}, {}
        generator = np.random.default_rng(789)
        for split, n in [('train', 2), ('val', 1)]:
            frame = pd.DataFrame([dict(row(trace=f'{split}{i}.AA.STA..HH'), source_id=f'{split}{i}') for i in range(n)])
            frame.to_csv(root / ('train_full_metadata.csv' if split == 'train' else 'val_metadata.csv'), index=False)
            frames[split] = frame
            arrays[split] = []
            for trace in frame.trace_name:
                counts = generator.integers(-1000, 1000, size=(3, 550), dtype=np.int32)
                traces[trace] = counts
                scaled = (torch.from_numpy(counts[:, 20:520].astype(np.float32)) - torch.from_numpy(mean[:, None])) / (torch.from_numpy(std[:, None]) + 1e-8)
                arrays[split].append(scaled.numpy())
            arrays[split] = np.stack(arrays[split])
        for seconds, filename in [(1, 'one.h5'), (5, 'five.h5')]:
            with h5py.File(root / filename, 'w') as h:
                for split in ('train', 'val'):
                    h.create_dataset(f'{split}/waveforms', data=arrays[split][:, :, :seconds*100])
                    h.create_dataset(f'{split}/targets', data=frames[split].source_magnitude.to_numpy(np.float32))
                h.create_dataset('test/DO_NOT_READ', data=np.array([-999]))
        with h5py.File(root / 'Instance_events_counts.hdf5', 'w') as h:
            for trace, value in traces.items():
                h.create_dataset('data/' + trace, data=value)
        audit = {'windows': {'1': {'cache': 'one.h5'}, '5': {'cache': 'five.h5'}}}
        audit_path = root / 'results/2026-10-09/audit.json'
        audit_path.parent.mkdir(parents=True)
        audit_path.write_text(json.dumps(audit))
        data['train_rows'] = np.array([1], dtype=np.int64)
        for split in ('train', 'val'):
            selected = frames[split].iloc[data['train_rows']] if split == 'train' else frames[split]
            features, _, _, names, _ = runner.source.instrument_arrays(selected, inventory)
            data[split + '_instrument'] = features
            data[split + '_ids'] = selected.source_id.to_numpy(str)
            data[split + '_trace_names'] = selected.trace_name.to_numpy(str)
            data[split + '_y'] = selected.source_magnitude.to_numpy(np.float32)
        identities = {'audit_sha256': runner.source.sha256(audit_path),
                      'inventory_sha256': runner.source.sha256(root / 'inventory.tgz'),
                      'normalization_sha256': {name: runner.source.sha256(root / name) for name in ('train_mean_full.npy', 'train_std_full.npy')},
                      'metadata_sha256': {split: runner.source.sha256(root / filename) for split, filename in [('train', 'train_full_metadata.csv'), ('val', 'val_metadata.csv')]}}
        args = runner.parse_args(['--inventory', str(root / 'inventory.tgz'), '--root', str(root), '--data', str(root), '--device', 'cpu'])
        return args, data, identities, names, inventory

    def test_exact_real_format_extraction_checks_every_selected_named_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args, data, identity, names, inventory = self.fixture(root)
            with patch.object(runner.source.Inventory, 'from_archive', return_value=inventory), redirect_stdout(io.StringIO()):
                observed, reporting, provenance = runner.extract_observations(args, data, identity, names)
            self.assertEqual(provenance['raw_identity_checks'], {'train': 1, 'val': 1})
            np.testing.assert_array_equal(observed['train']['valid'], [[True, True]])
            np.testing.assert_array_equal(observed['train']['invalid_reason_code'], [[0, 0]])
            self.assertEqual(reporting['val']['station_ids'].tolist(), ['AA.STA'])
            self.assertEqual(observed['train']['z'].dtype, np.float64)
            with h5py.File(root / 'five.h5', 'r+') as h:
                values = h['train/waveforms'][1]
                values[:, 200] += 1  # unchanged labels and first second, wrong later trace evidence
                h['train/waveforms'][1] = values
            with patch.object(runner.source.Inventory, 'from_archive', return_value=inventory), self.assertRaisesRegex(ValueError, 'Named raw prefix differs'):
                runner.extract_observations(args, data, identity, names)

    def test_metadata_and_normalizer_changes_rejected_before_use(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args, data, identity, names, inventory = self.fixture(root)
            np.save(root / 'train_std_full.npy', np.ones(3))
            with patch.object(runner.source.Inventory, 'from_archive', return_value=inventory), self.assertRaisesRegex(ValueError, 'Normalization changed'):
                runner.extract_observations(args, data, identity, names)

    def test_raw_metadata_cache_configured_before_lookup_and_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args, data, identity, names, inventory = self.fixture(root)
            original_file = h5py.File
            configured = []
            config = SimpleNamespace(max_size=1, min_size=1, initial_size=1, set_initial_size=0)

            class RawWithFakeConfiguration:
                def __init__(self, path, mode):
                    self.handle = original_file(path, mode)
                    self.id = SimpleNamespace(get_mdc_config=lambda: config,
                                              set_mdc_config=lambda value: configured.append(vars(value).copy()))

                def __enter__(self):
                    return self

                def __exit__(self, *exc):
                    self.handle.close()

                def __getitem__(self, key):
                    if not configured:
                        raise AssertionError('Raw data accessed before metadata cache configuration')
                    return self.handle[key]

            def open_file(path, mode):
                if Path(path).name == 'Instance_events_counts.hdf5':
                    return RawWithFakeConfiguration(path, mode)
                return original_file(path, mode)

            with patch.object(runner.h5py, 'File', side_effect=open_file), \
                 patch.object(runner.source.Inventory, 'from_archive', return_value=inventory), redirect_stdout(io.StringIO()):
                _, _, provenance = runner.extract_observations(args, data, identity, names)
            self.assertEqual(configured, [{'max_size': 128 * 1024**2, 'min_size': 32 * 1024**2,
                                            'initial_size': 128 * 1024**2, 'set_initial_size': 1}])
            self.assertEqual(provenance['raw_metadata_cache_bytes'],
                             {'maximum': 128 * 1024**2, 'minimum': 32 * 1024**2, 'initial': 128 * 1024**2})

    def test_reason_codes_account_for_each_skipped_observation(self):
        x = torch.ones(4, 500).double()
        x[:, 10:100] = 2.
        x[:, 100:300] = 3.
        x[:, 300:] = 4.
        x[3, 100:300] = 1.
        gains = torch.tensor([1., -1., 1., 1.]).double()
        usable = torch.tensor([True, True, False, True])
        units = torch.tensor([1, 1, 0, 1])
        observation = runner.pilot.vertical_innovations(x, gains, usable, units)
        codes = runner.invalid_codes(observation, gains, usable, units)
        torch.testing.assert_close(codes == 0, observation.valid)
        self.assertEqual(int(codes[1, 0]), 2)
        self.assertEqual(int(codes[2, 0]), 5)
        self.assertEqual(int(codes[3, 0]), 16)
        self.assertEqual(int(codes[3, 1]), 64)

    def test_evaluation_diagnostics_and_normalization_all_controls(self):
        generator = np.random.default_rng(13)
        context = generator.normal(size=(7, 5)).astype(np.float32)
        prior = torch.from_numpy(generator.normal(size=(7, 66))).log_softmax(1).numpy()
        observed = {'z': generator.normal(size=(7, 2)), 'valid': np.ones((7, 2), dtype=bool)}
        observed['valid'][0] = False
        centers = (np.arange(66) + .5) * .1
        y = np.linspace(1, 5, 7)
        for arm in runner.CONTROLS:
            model = None if arm == 'frozen' else runner.pilot.InnovationHead(5, arm)
            p, diagnostic = runner.evaluate(model, context, prior, observed, centers, y, 3, torch.device('cpu'))
            np.testing.assert_allclose(p.sum(2), 1., atol=1e-12, rtol=0)
            np.testing.assert_allclose(p[:, 0], np.exp(prior), atol=1e-15, rtol=1e-14)
            if arm in runner.pilot.GENERATIVE_ARMS:
                self.assertEqual(set(diagnostic), {'conditional_nll', 'forecast_nll', 'zero_probability', 'positive_pit'})
                for value in diagnostic.values():
                    self.assertTrue(np.isfinite(value).all())
                    np.testing.assert_array_equal(value[0], 0)
                self.assertTrue(((diagnostic['positive_pit'] >= 0) & (diagnostic['positive_pit'] <= 1)).all())
                summary = runner.mechanism_summary(diagnostic, observed)
                self.assertEqual(summary['3']['valid_records'], 6)
                self.assertAlmostEqual(summary['3']['predicted_zero_fraction'], .5, places=12)
            else:
                self.assertEqual(diagnostic, {})

    def run_fixture(self, directory, prepare_only=False):
        data = synthetic_data()
        data['train_rows'] = np.arange(len(data['train_y']))
        observed, reporting = {}, {}
        for split in ('train', 'val'):
            n = len(data[split + '_y'])
            data[split + '_ids'] = np.array([f'{split}{i}' for i in range(n)])
            data[split + '_trace_names'] = np.array([f'{split}trace{i}' for i in range(n)])
            z = np.linspace(-.5, .5, 2*n).reshape(n, 2)
            observed[split] = dict(z=z, g=np.maximum(z, 0), valid=np.ones((n, 2), dtype=bool),
                                   above_floor=np.ones((n, 3), dtype=bool), invalid_reason_code=np.zeros((n, 2), dtype=np.int16))
            reporting[split] = {'families': np.array(['HH']*n), 'station_ids': np.array(['AA.STA']*n)}
        args = runner.parse_args(['--inventory', 'unused.tgz', '--output', str(directory), '--device', 'cpu', '--batch-size', '4'])
        args.epochs = 1
        args.seeds = [runner.pilot.SEEDS[0], runner.pilot.SEEDS[1]]
        args.prepare_only = prepare_only
        contexts = [np.zeros((len(data[s + '_y']), 5), dtype=np.float32) for s in ('train', 'val')]
        prior_by_seed = {}

        def starting(*unused):
            seed = unused[4]
            priors = [torch.from_numpy(data[s + '_logits']).double().log_softmax(1).numpy() for s in ('train', 'val')]
            prior_by_seed[seed] = priors
            return contexts, priors, {'seed': seed}

        original_fit = runner.pilot.fit_arm
        replayed = []

        def replay(*a, **kw):
            replayed.append(a[4])
            return starting(*a, **kw)

        def fit(*a, **kw):
            self.assertEqual(replayed, args.seeds)  # both priors verified before ANY fit
            return original_fit(*a, **kw)

        original_sha = runner.source.sha256

        def checkpoint_hash(path):
            for seed, digest in runner.STARTING_CHECKPOINT_SHA256.items():
                if Path(path).name == f'instrument_seed{seed}.pth':
                    return digest
            return original_sha(path)

        with patch.object(runner, 'parse_args', return_value=args), \
             patch.object(runner, 'EXPECTED_TRAIN_RECORDS', len(data['train_y'])), \
             patch.object(runner.source, 'extract', return_value=(data, {}, {}, list(runner.EXPECTED_INSTRUMENT_NAMES))), \
             patch.object(runner, 'extract_observations', return_value=(observed, reporting, {})), \
             patch.object(runner.pilot, 'load_frozen_start', side_effect=replay), \
             patch.object(runner.pilot, 'fit_arm', side_effect=fit) as fitting, \
             patch.object(runner.source, 'sha256', side_effect=checkpoint_hash), redirect_stdout(io.StringIO()):
            runner.main()
            self.assertEqual(fitting.call_count, 0 if prepare_only else len(args.seeds)*len(runner.pilot.ARMS))
        destination, = Path(directory).iterdir()
        return destination, data

    def test_complete_fixture_persists_all_seed_and_ensemble_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            destination, data = self.run_fixture(directory)
            manifest = json.loads((destination / 'artifacts.json').read_text())['files']
            self.assertEqual(set(manifest), {p.name for p in destination.iterdir()} - {'artifacts.json'})
            run = json.loads((destination / 'run.json').read_text())
            self.assertEqual(run['status'], 'complete')
            self.assertEqual(len(set(n for n in run['parameter_counts'].values() if n)), 1)
            with np.load(destination / 'predictions.npz', allow_pickle=False) as predictions:
                for arm in runner.CONTROLS:
                    p1 = []
                    for seed in runner.pilot.SEEDS:
                        name = f'{arm}_seed{seed}_probabilities.npz'
                        self.assertEqual(manifest[name]['sha256'], runner.source.sha256(destination / name))
                        with np.load(destination / name, allow_pickle=False) as saved:
                            p = saved['probability']
                            self.assertEqual(p.dtype, np.float64)
                            np.testing.assert_array_equal(saved['trace_names'], data['val_trace_names'])
                            np.testing.assert_array_equal(p[:, 2] @ saved['centers'], predictions[f'{arm}_seed{seed}_5s_mean'])
                            p1.append(p)
                    with np.load(destination / f'{arm}_ensemble_probabilities.npz', allow_pickle=False) as ensemble:
                        np.testing.assert_array_equal(ensemble['probability'], np.mean(p1, axis=0))
            histories = json.loads((destination / 'history.json').read_text())
            for seed in runner.pilot.SEEDS:
                orders = [histories[f'{arm}_seed{seed}'][0]['row_order_sha256'] for arm in runner.pilot.ARMS]
                self.assertEqual(len(set(orders)), 1)

    def test_prepare_only_never_fits_and_fixed_defaults(self):
        args = runner.parse_args(['--inventory', 'unused.tgz'])
        self.assertEqual((args.epochs, args.max_per_event, args.seconds), (15, 4, 1))
        self.assertEqual(args.seeds, list(runner.pilot.SEEDS))
        with tempfile.TemporaryDirectory() as directory:
            destination, _ = self.run_fixture(directory, prepare_only=True)
            self.assertEqual(json.loads((destination / 'run.json').read_text())['status'], 'prepared_only')
            self.assertFalse(list(destination.glob('*_probabilities.npz')))
            for seed in runner.pilot.SEEDS:
                self.assertTrue((destination / f'frozen_p1_seed{seed}.npz').exists())

    def test_deterministic_contract_and_late_cuda_initialization_guard(self):
        with patch.object(torch.cuda, 'is_initialized', return_value=False), patch.dict(os.environ, {}, clear=False):
            flags = runner.configure_determinism()
            self.assertTrue(flags['deterministic_algorithms'])
            self.assertFalse(flags['deterministic_warn_only'])
            self.assertTrue(flags['cudnn_deterministic'])
            self.assertFalse(flags['cudnn_benchmark'])
            self.assertEqual(flags['cublas_workspace_config'], ':4096:8')
        with patch.object(torch.cuda, 'is_initialized', return_value=True), patch.dict(os.environ, {'CUBLAS_WORKSPACE_CONFIG': 'wrong'}):
            with self.assertRaises(RuntimeError):
                runner.configure_determinism()


if __name__ == '__main__':
    unittest.main()

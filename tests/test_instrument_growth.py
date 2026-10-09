from argparse import Namespace
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/2026-10-09/phase2'))
import instrument_growth as runner
import instrument_residual as baseline
from feature_residual import ResidualDistribution
from future_growth import PEAK_FLOOR_COUNTS, hurdle_log_prob
from train_future_growth import array_digest, file_stat
from audit_and_export import sha256


def fixture_data():
    rng = np.random.default_rng(723)
    data = {'centers': (np.arange(66) + .5) * .1}
    for split, n in [('train', 12), ('val', 6)]:
        for key, dim in [('logits', 66), ('hidden', 128), ('prefix', 51), ('instrument', 34), ('native', 12)]:
            data[split + '_' + key] = rng.normal(size=(n, dim)).astype(np.float32)
        data[split + '_y'] = np.tile([1., 2., 4.5], n // 3).astype(np.float32)
        data[split + '_ids'] = np.array([f'{split}{i}' for i in range(n)])
        data[split + '_trace_names'] = np.array([f'{split}_trace{i}' for i in range(n)])
    data['train_rows'] = np.arange(12)
    data['weights'] = np.linspace(.5, 1.5, 12).astype(np.float32)
    return data


def fit_args(**kwargs):
    options = dict(epochs=3, batch_size=4, learning_rate=5e-4, beta=5., anchor=0., auxiliary_weight=.05)
    options.update(kwargs)
    return Namespace(**options)


def target_fixture(root, data):
    root = Path(root)
    directory = root / 'data'
    directory.mkdir()
    for filename in ('Instance_events_counts.hdf5', 'cache5.hdf5'):
        # The adapter only stats these; waveform extraction is a separate,
        # already-tested baseline contract and is mocked in the end-to-end test.
        (directory / filename).write_bytes(b'fixture source identity')
    frame = pd.DataFrame({'source_id': data['train_ids'], 'trace_name': data['train_trace_names'],
                          'source_magnitude': data['train_y'], 'trace_P_arrival_sample': 100})
    metadata = root / 'train_full_metadata.csv'
    frame.to_csv(metadata, index=False)
    frame = pd.read_csv(metadata, dtype={'source_id': str, 'trace_name': str})
    normalization = {}
    for name in ('train_mean_full.npy', 'train_std_full.npy'):
        np.save(root / name, np.ones(3, dtype=np.float32))
        normalization[name] = sha256(root / name)
    audit_path = root / 'results/2026-10-09/audit.json'
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(json.dumps({'windows': {'5': {'cache': 'cache5.hdf5'}}}))
    identities = {'metadata_sha256': {'train': sha256(metadata)},
                  'audit_sha256': sha256(audit_path), 'normalization_sha256': normalization}
    n = len(frame)
    valid = np.ones((n, 3), dtype=bool)
    valid[2] = False
    peaks = np.tile([2., 4., 8., 8.], (n, 1))
    growth = np.log10(peaks[:, -1:]) - np.log10(peaks[:, :3])
    growth[2], peaks[2] = 0., 0.
    arrays = {'rows': np.arange(n), 'event_ids': frame.source_id.to_numpy(dtype=str),
              'trace_names': frame.trace_name.to_numpy(dtype=str),
              'magnitudes': frame.source_magnitude.to_numpy(dtype=np.float64),
              'p_samples': frame.trace_P_arrival_sample.to_numpy(dtype=np.int64),
              'growth': growth, 'valid': valid, 'reason': np.where(valid[:, 0], 'ok', 'missing_future'),
              'peaks': peaks, 'baseline': np.zeros(n),
              'source_window_sha256': np.where(valid[:, 0], 'a' * 64, '')}
    manifest = {'schema': 'instance_future_growth_v1', 'split': 'train', 'records': n,
                'input_seconds': [1, 3, 5], 'target_seconds': 10, 'sample_rate_hz': 100,
                'peak_floor_counts': PEAK_FLOOR_COUNTS, 'smoke_only': False,
                'metadata_sha256': identities['metadata_sha256']['train'],
                'audit_sha256': identities['audit_sha256'], 'normalization_sha256': normalization,
                'raw_source': file_stat(directory / 'Instance_events_counts.hdf5'),
                'cache_source': file_stat(directory / 'cache5.hdf5')}
    path = root / 'targets.npz'
    rewrite_archive(path, arrays, manifest)
    args = fit_args(root=root, data=directory, targets=path, seconds=3)
    return args, identities, arrays, manifest


def rewrite_archive(path, arrays, manifest):
    m = dict(manifest, arrays_sha256={key: array_digest(value) for key, value in arrays.items()})
    np.savez_compressed(path, manifest_json=np.array(json.dumps(m)), **arrays)


class InstrumentGrowthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_initialization_and_rng_match_existing_magnitude_model(self):
        torch.manual_seed(81)
        original = ResidualDistribution(291)
        expected_rng = torch.get_rng_state().clone()
        torch.manual_seed(81)
        model = runner.InstrumentGrowthModel()
        torch.testing.assert_close(torch.get_rng_state(), expected_rng, atol=0, rtol=0)
        for key, value in original.state_dict().items():
            torch.testing.assert_close(model.magnitude.state_dict()[key], value, atol=0, rtol=0)
        sizes = []
        for _ in runner.CONTROLS:
            torch.manual_seed(81)
            sizes.append(sum(p.numel() for p in runner.InstrumentGrowthModel().parameters()))
        self.assertEqual(len(set(sizes)), 1)

    def test_forward_state_path_and_inference_interface(self):
        model = runner.InstrumentGrowthModel()
        x, original = torch.randn(5, 291), torch.randn(5, 66)
        torch.manual_seed(103)
        expected = model(x, original)
        torch.manual_seed(103)
        actual, state = model.forward_with_state(x, original)
        torch.testing.assert_close(actual, expected, atol=0, rtol=0)
        self.assertEqual(state.shape, (5, 64))
        with self.assertRaises(TypeError):
            model(x, original, future=torch.ones(5))
        with self.assertRaises(TypeError):
            model(x, original, labels=torch.ones(5))

    def test_design_is_exact_full_static_mask(self):
        data = fixture_data()
        arrays, mean, std, mask, base = runner.instrument_design(data)
        expected, emean, estd, masks, ebase = baseline.design_inputs(data)
        for a, b in zip(arrays, expected):
            np.testing.assert_array_equal(a, b)
            np.testing.assert_array_equal((a * mask)[:, -12:], 0)
        np.testing.assert_array_equal(mask, masks['instrument'])
        np.testing.assert_array_equal(mean, emean)
        np.testing.assert_array_equal(std, estd)
        self.assertEqual(base, ebase)

    def test_supervised_fit_replays_original_bitwise_for_both_seeds(self):
        data = fixture_data()
        arrays, _, _, mask, _ = runner.instrument_design(data)
        args = fit_args()
        growth, valid = np.ones(12, dtype=np.float32), np.ones(12, dtype=bool)
        device = torch.device('cpu')
        for seed in (20261009, 20261010):
            expected, original, loss = baseline.fit_one(data, arrays, mask, args, seed, device)
            actual, state, history = runner.fit_one(data, arrays, mask, growth, valid, args, seed, device, 'supervised')
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(history['supervised'], loss)
            self.assertEqual(history['total'], loss)
            for key in original:
                torch.testing.assert_close(state['magnitude'][key], original[key], atol=0, rtol=0)

    def test_detached_control_preserves_magnitude_updates_even_with_large_auxiliary(self):
        data = fixture_data()
        arrays, _, _, mask, _ = runner.instrument_design(data)
        args = fit_args(auxiliary_weight=100.)
        g = np.array([0., .01, 5.] * 4, dtype=np.float32)
        valid = np.ones(12, dtype=bool)
        a, ast, ah = runner.fit_one(data, arrays, mask, g, valid, args, 20261009, torch.device('cpu'), 'supervised')
        b, bst, bh = runner.fit_one(data, arrays, mask, g, valid, args, 20261009, torch.device('cpu'), 'conditional_detached')
        np.testing.assert_array_equal(a, b)
        self.assertEqual(ah['supervised'], bh['supervised'])
        for key in ast['magnitude']:
            torch.testing.assert_close(ast['magnitude'][key], bst['magnitude'][key], atol=0, rtol=0)
        self.assertTrue(any(not torch.equal(ast['growth_head'][k], bst['growth_head'][k]) for k in ast['growth_head']))

    def test_missing_mask_and_population_weights_once(self):
        model = runner.InstrumentGrowthModel()
        state = torch.randn(3, 64, requires_grad=True)
        labels, weights = torch.tensor([10, 20, 45]), torch.tensor([.5, 1., 1.5])
        growth, valid = torch.tensor([.2, float('nan'), 0.]), torch.tensor([True, False, True])
        actual = runner.growth_loss(model, state, labels, weights, growth, valid, 'conditional_nll')
        q = model.growth_parameters(state[[0, 2]], labels[[0, 2]])
        expected = -(weights[[0, 2]] * hurdle_log_prob(q, growth[[0, 2]])).sum() / 3
        torch.testing.assert_close(actual, expected)
        actual.backward()
        self.assertTrue(torch.isfinite(state.grad).all())
        torch.testing.assert_close(state.grad[1], torch.zeros(64), atol=0, rtol=0)
        with self.assertRaises(ValueError):
            runner.growth_loss(model, state, labels, weights, growth, torch.ones(3, dtype=torch.bool), 'conditional_nll')

    def test_loss_controls_condition_only_the_auxiliary_and_train_shared_state(self):
        model = runner.InstrumentGrowthModel()
        for control in ('growth_mse', 'unconditional_nll', 'conditional_nll'):
            state = torch.randn(3, 64, requires_grad=True)
            loss = runner.growth_loss(model, state, torch.tensor([1, 20, 45]), torch.ones(3),
                                     torch.tensor([0., .1, .8]), torch.ones(3, dtype=torch.bool), control)
            loss.backward()
            self.assertGreater(state.grad.abs().sum().item(), 0)
        h = torch.randn(3, 64)
        weights, g, valid = torch.ones(3), torch.ones(3), torch.ones(3, dtype=torch.bool)
        a = runner.growth_loss(model, h, torch.tensor([1, 2, 3]), weights, g, valid, 'unconditional_nll')
        b = runner.growth_loss(model, h, torch.tensor([60, 61, 62]), weights, g, valid, 'unconditional_nll')
        torch.testing.assert_close(a, b, atol=0, rtol=0)

    def test_target_adapter_preserves_identity_missingness_and_each_horizon(self):
        data = fixture_data()
        with tempfile.TemporaryDirectory() as d:
            args, identities, arrays, _ = target_fixture(d, data)
            for j, t in enumerate((1, 3, 5)):
                args.seconds = t
                g, valid, report = runner.load_aligned_growth(args, data, identities)
                np.testing.assert_array_equal(g, arrays['growth'][:, j].astype(np.float32))
                np.testing.assert_array_equal(valid, arrays['valid'][:, j])
                self.assertEqual(report['selected_records'], 12)
                self.assertEqual(report['archive_sha256'], sha256(args.targets))
            corrupted = copy.deepcopy(data)
            corrupted['train_trace_names'][0] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'identity mismatch'):
                runner.load_aligned_growth(args, corrupted, identities)

    def test_target_adapter_rejects_digest_row_mask_and_source_changes(self):
        for corruption in ('identity', 'coverage', 'mask', 'source', 'digest'):
            with self.subTest(corruption=corruption), tempfile.TemporaryDirectory() as d:
                data = fixture_data()
                args, identities, arrays, manifest = target_fixture(d, data)
                if corruption == 'identity':
                    arrays['trace_names'][0] = arrays['trace_names'][1]
                elif corruption == 'coverage':
                    arrays = {k: v[1:] for k, v in arrays.items()}
                elif corruption == 'mask':
                    arrays['valid'][2, 0] = True
                elif corruption == 'source':
                    (args.data / 'Instance_events_counts.hdf5').write_bytes(b'changed source')
                elif corruption == 'digest':
                    with np.load(args.targets, allow_pickle=False) as a:
                        payload = {k: a[k] for k in a.files}
                    payload['growth'] = payload['growth'].copy()
                    payload['growth'][0, 0] += 1
                    np.savez_compressed(args.targets, **payload)
                if corruption not in ('source', 'digest'):
                    rewrite_archive(args.targets, arrays, manifest)
                with self.assertRaises(ValueError):
                    runner.load_aligned_growth(args, data, identities)

    def test_complete_cpu_runner_saves_aligned_predictions_and_artifact_hashes(self):
        data = fixture_data()
        with tempfile.TemporaryDirectory() as d:
            args, identities, _, _ = target_fixture(d, data)
            args.__dict__.update(output=Path(d) / 'runs', controls=list(runner.CONTROLS), seeds=[20261009],
                epochs=1, expected_train_records=12, extract_batch_size=8, inventory=Path(d) / 'unused.tgz',
                inventory_sha256=baseline.INVENTORY_SHA256, max_per_event=4, device='cpu')
            with patch.object(baseline, 'extract', return_value=(data, identities, {'scope': 'synthetic fixture'}, [f'f{i}' for i in range(34)])):
                output = runner.run(args)
            with np.load(output / 'predictions.npz', allow_pickle=False) as predictions:
                np.testing.assert_array_equal(predictions['event_ids'], data['val_ids'])
                for control in runner.CONTROLS:
                    with np.load(output / f'{control}_probabilities.npz', allow_pickle=False) as p:
                        np.testing.assert_array_equal(p['trace_names'], data['val_trace_names'])
                        np.testing.assert_allclose(p['mean_probability'] @ p['centers'], predictions[control + '_ensemble_mean'], atol=2e-7)
                np.testing.assert_array_equal(predictions['supervised_seed20261009_mean'], predictions['conditional_detached_seed20261009_mean'])
            artifacts = json.loads((output / 'artifacts.json').read_text())
            self.assertNotIn('artifacts.json', artifacts)
            for name, record in artifacts.items():
                self.assertEqual(record['sha256'], sha256(output / name))
                self.assertEqual(record['bytes'], (output / name).stat().st_size)
            with np.load(output / 'training_rows.npz', allow_pickle=False) as rows:
                np.testing.assert_array_equal(rows['row_index'], data['train_rows'])
                np.testing.assert_array_equal(rows['weights'], data['weights'])


if __name__ == '__main__':
    unittest.main()

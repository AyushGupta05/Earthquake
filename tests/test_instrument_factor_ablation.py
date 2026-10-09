from argparse import Namespace
from contextlib import redirect_stdout
import io
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
import instrument_factor_ablation as runner
from test_instrument_residual import synthetic_data, epoch, row
from instrument_inventory import Inventory


class FactorAblationTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.data = synthetic_data()
        self.names = list(runner.EXPECTED_INSTRUMENT_NAMES)

    def test_exact_current_schema_and_five_named_masks(self):
        actual = runner.source.instrument_arrays(pd.DataFrame([row()]), Inventory([epoch(c) for c in 'ENZ']))[3]
        self.assertEqual(actual, self.names)
        arrays, _, _, masks, dim = runner.factor_design(self.data, actual)
        self.assertEqual(dim, 245)
        self.assertEqual(arrays[0].shape[1], 291)
        self.assertEqual([int(m.sum()) for m in masks.values()], [245, 257, 255, 269, 279])
        for name, mask in masks.items():
            np.testing.assert_array_equal(mask[:245], 1)
            np.testing.assert_array_equal(mask[-12:], 0)
            observed = [feature for i, feature in enumerate(actual) if mask[245 + i]]
            self.assertEqual(set(observed), set(runner.CONTROL_NAMES[name]))
        self.assertEqual(len(runner.GAIN_NAMES), 12)
        self.assertTrue(set(runner.GAIN_NAMES) <= set(runner.RESPONSE_NAMES))
        self.assertFalse(set(runner.GAIN_NAMES) & set(runner.CONTROL_NAMES['family_site']))

    def test_schema_changes_fail_closed(self):
        bad = [self.names[::-1], self.names[:-1], self.names + ['source_magnitude'],
               ['station_id'] + self.names[1:], self.names[:1] + self.names[:-1]]
        for names in bad:
            with self.subTest(names=names), self.assertRaises(ValueError):
                runner.factor_design(self.data, names)

    def test_reuses_exact_source_normalization_and_existing_controls(self):
        old_arrays, old_mean, old_std, old_masks, _ = runner.source.design_inputs(self.data)
        arrays, mean, std, masks, _ = runner.factor_design(self.data, self.names)
        np.testing.assert_array_equal(mean, old_mean)
        np.testing.assert_array_equal(std, old_std)
        for before, after in zip(old_arrays, arrays):
            np.testing.assert_array_equal(before, after)
        np.testing.assert_array_equal(masks['base'], old_masks['base'])
        np.testing.assert_array_equal(masks['full_static'], old_masks['instrument'])

    def test_val_and_native_values_cannot_affect_any_active_input_or_fit(self):
        arrays, mean, std, masks, _ = runner.factor_design(self.data, self.names)
        changed = {key: value.copy() for key, value in self.data.items()}
        changed['train_native'][:] = 12345
        changed['val_native'][:] = -67890
        other, other_mean, other_std, _, _ = runner.factor_design(changed, self.names)
        np.testing.assert_array_equal(mean[:-12], other_mean[:-12])
        np.testing.assert_array_equal(std[:-12], other_std[:-12])
        for mask in masks.values():
            for first, second in zip(arrays, other):
                np.testing.assert_array_equal(first * mask, second * mask)
        for name in ('logits', 'hidden', 'prefix', 'instrument', 'native'):
            changed['val_' + name][:] = 1e8
        _, val_mean, val_std, _, _ = runner.factor_design(changed, self.names)
        np.testing.assert_array_equal(val_mean, other_mean)
        np.testing.assert_array_equal(val_std, other_std)

    def test_same_initial_parameters_and_budget_for_every_mask(self):
        arrays, _, _, masks, _ = runner.factor_design(self.data, self.names)
        original = torch.from_numpy(self.data['train_logits'])
        states, counts = [], []
        for mask in masks.values():
            torch.manual_seed(234)
            model = runner.source.ResidualDistribution(291).eval()
            states.append(model.state_dict())
            counts.append(sum(p.numel() for p in model.parameters()))
            torch.testing.assert_close(model(torch.from_numpy(arrays[0] * mask), original), original, rtol=0, atol=0)
        self.assertEqual(len(set(counts)), 1)
        for state in states[1:]:
            for key in states[0]:
                torch.testing.assert_close(states[0][key], state[key], rtol=0, atol=0)

    def test_fixed_training_reproduces_existing_base_and_full(self):
        arrays, _, _, masks, _ = runner.factor_design(self.data, self.names)
        old_arrays, _, _, old_masks, _ = runner.source.design_inputs(self.data)
        args = Namespace(epochs=2, batch_size=4, learning_rate=5e-4, beta=5., anchor=0.)
        for new, old in [('base', 'base'), ('full_static', 'instrument')]:
            p, state, losses = runner.source.fit_one(self.data, arrays, masks[new], args, 111, torch.device('cpu'))
            q, other, old_losses = runner.source.fit_one(self.data, old_arrays, old_masks[old], args, 111, torch.device('cpu'))
            np.testing.assert_array_equal(p, q)
            self.assertEqual(losses, old_losses)
            for key in state:
                torch.testing.assert_close(state[key], other[key], rtol=0, atol=0)

    def test_reporting_uses_identity_order_and_never_adds_columns_to_design(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            metadata = {}
            frames = {}
            for split, events, stations in [('train', ['t1', 't2'], ['A', 'B']), ('val', ['v1', 'v1'], ['A', 'C'])]:
                frame = pd.DataFrame({'source_id': events, 'trace_name': [f'{e}.{s}' for e, s in zip(events, stations)],
                                      'station_network_code': ['IV']*2, 'station_code': stations, 'station_channels': ['HH', 'HN']})
                path = root / ('train_full_metadata.csv' if split == 'train' else 'val_metadata.csv')
                frame.to_csv(path, index=False)
                frames[split] = frame
                metadata[split] = runner.source.sha256(path)
            data = {'train_rows': np.array([1]), 'val_y': np.array([4., 4.])}
            for split in frames:
                f = frames[split].iloc[[1]] if split == 'train' else frames[split]
                data[split + '_ids'] = f.source_id.to_numpy(str)
                data[split + '_trace_names'] = f.trace_name.to_numpy(str)
            val, overlap = runner.reporting_metadata(Namespace(root=root), data, {'metadata_sha256': metadata})
            self.assertEqual(val.station_id.tolist(), ['IV.A', 'IV.C'])
            self.assertEqual(overlap['full_train']['seen_validation_records'], 1)
            self.assertEqual(overlap['sampled_train']['seen_validation_records'], 0)
            data['val_trace_names'] = data['val_trace_names'][::-1]
            with self.assertRaises(ValueError):
                runner.reporting_metadata(Namespace(root=root), data, {'metadata_sha256': metadata})

    def test_same_event_family_groups_exclude_nonshared_events(self):
        y = np.array([4., 4., 4., 4., 2., 2., 2.])
        ids = np.array(['a', 'a', 'a', 'b', 'c', 'c', 'c'])
        families = np.array(['HN', 'HH', 'EH', 'HN', 'HN', 'HH', 'EH'])
        baseline = y - 1
        alternative = y - .5
        result = runner.subgroup_diagnostics(y, ids, families, baseline, alternative)
        self.assertEqual(result['same_event_count'], 2)
        self.assertEqual(result['same_event_tail_count'], 1)
        shared = {x['family']: x for x in result['groups']['same_events_tail']}
        self.assertEqual(shared['HN']['records'], 1)
        self.assertEqual(shared['HN']['alternative_event_macro_mae'], .5)
        all_tail = {x['family']: x for x in result['groups']['tail']}
        self.assertEqual(all_tail['HN']['records'], 2)
        with self.assertRaises(ValueError):
            runner.subgroup_diagnostics(y[:-1], ids, families, baseline, alternative)

    def test_manifest_hashes_all_outputs_without_self_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'one.txt').write_text('one')
            np.savez_compressed(root / 'probabilities.npz', p=np.array([[.25, .75]]))
            runner.write_artifact_manifest(root)
            manifest = json.loads((root / 'artifacts.json').read_text())['files']
            self.assertEqual(set(manifest), {'one.txt', 'probabilities.npz'})
            for name, item in manifest.items():
                self.assertEqual(item['sha256'], runner.source.sha256(root / name))
                self.assertEqual(item['bytes'], (root / name).stat().st_size)

    def test_prespecified_defaults_and_full_population_option(self):
        args = runner.parse_args(['--seconds', '1', '--inventory', 'responses.tgz'])
        self.assertEqual((args.beta, args.anchor, args.epochs, args.max_per_event), (5., 0., 15, 4))
        self.assertEqual(args.seeds, [20261009, 20261010])
        full = runner.parse_args(['--seconds', '5', '--inventory', 'responses.tgz', '--max-per-event', '0'])
        self.assertEqual(full.max_per_event, 0)

    def test_complete_synthetic_run_persists_every_probability_and_hash(self):
        data = self.data
        data['train_rows'] = np.arange(len(data['train_y']))
        for split in ('train', 'val'):
            count = len(data[split + '_y'])
            data[split + '_ids'] = np.array([f'{split}event{i}' for i in range(count)])
            data[split + '_trace_names'] = np.array([f'{split}trace{i}' for i in range(count)])
        reporting = pd.DataFrame({'station_id': ['IV.A']*6, 'station_channels': ['EH', 'HH', 'HN']*2})
        with tempfile.TemporaryDirectory() as directory:
            args = runner.parse_args(['--seconds', '1', '--inventory', 'unused.tgz', '--output', directory,
                                      '--device', 'cpu', '--epochs', '1', '--seeds', '123', '--batch-size', '4'])
            with patch.object(runner, 'parse_args', return_value=args), \
                 patch.object(runner.source, 'extract', return_value=(data, {}, {}, self.names)), \
                 patch.object(runner, 'reporting_metadata', return_value=(reporting, {})), \
                 redirect_stdout(io.StringIO()):
                runner.main()
            destination, = Path(directory).iterdir()
            manifest = json.loads((destination / 'artifacts.json').read_text())['files']
            self.assertEqual(set(manifest), {p.name for p in destination.iterdir()} - {'artifacts.json'})
            with np.load(destination / 'predictions.npz', allow_pickle=False) as predictions:
                for label in ('raw', *runner.CONTROL_NAMES):
                    filename = label + '_probabilities.npz'
                    self.assertIn(filename, manifest)
                    self.assertEqual(manifest[filename]['sha256'], runner.source.sha256(destination / filename))
                    with np.load(destination / filename, allow_pickle=False) as probabilities:
                        key = 'probability' if label == 'raw' else 'mean_probability'
                        p = probabilities[key]
                        self.assertEqual(p.dtype, np.dtype('float64'))
                        np.testing.assert_array_equal(probabilities['trace_names'], data['val_trace_names'])
                        decision = label + ('_mean' if label == 'raw' else '_ensemble_mean')
                        np.testing.assert_array_equal(p @ probabilities['centers'], predictions[decision])
                        np.testing.assert_allclose(p.sum(1), 1., rtol=0, atol=1e-12)
            run = json.loads((destination / 'run.json').read_text())
            self.assertEqual(len(set(run['parameter_counts'].values())), 1)


if __name__ == '__main__':
    unittest.main()

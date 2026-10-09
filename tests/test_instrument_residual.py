from argparse import Namespace
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

import h5py
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/2026-10-09/phase2'))
import instrument_residual as runner
from instrument_inventory import Epoch, Inventory, location_code, model_features, utc_seconds


def epoch(component, gain=10., location=''):
    return Epoch('AA', 'STA', location, 'HH' + component, 0., 4102444800.,
                 gain, .2, 'M/S', 'COUNTS', 100., 0., 0., 40., 12., 100.,
                 'test sensor', 'fixture.xml')


def row(trace='1.AA.STA..HH', location=''):
    return {'source_id': '1', 'source_magnitude': 4., 'trace_name': trace,
            'trace_P_arrival_sample': 20, 'trace_start_time': '2016-11-16T01:35:48.20Z',
            'station_network_code': 'AA', 'station_code': 'STA',
            'station_location_code': location, 'station_channels': 'HH',
            'station_latitude_deg': 40., 'station_longitude_deg': 12.,
            'station_elevation_m': 100., 'station_vs_30_mps': 500.,
            'station_vs_30_detail': 'fixture'}


def synthetic_data():
    rng = np.random.default_rng(123)
    data = {'centers': (np.arange(66) + .5) * .1}
    for split, n in [('train', 12), ('val', 6)]:
        data[split + '_logits'] = rng.normal(size=(n, 66)).astype('float32')
        data[split + '_hidden'] = rng.normal(size=(n, 128)).astype('float32')
        data[split + '_prefix'] = rng.normal(size=(n, 51)).astype('float32')
        data[split + '_instrument'] = rng.normal(size=(n, 34)).astype('float32')
        data[split + '_native'] = rng.normal(size=(n, 12)).astype('float32')
        data[split + '_y'] = np.linspace(1., 4.5, n).astype('float32')
    data['weights'] = np.linspace(.5, 1.5, 12).astype('float32')
    return data


class InstrumentResidualTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)

    def test_join_is_row_and_component_aligned_with_partial_fallback(self):
        inventory = Inventory([epoch(c, gain=g) for c, g in zip('ENZ', (10., 20., 30.))])
        frame = pd.DataFrame([dict(row(), station_code='UNKNOWN'), row()])
        features, gain, mask, names, report = runner.instrument_arrays(frame, inventory)
        self.assertEqual(features.shape, (2, 34))
        np.testing.assert_array_equal(gain, [[1., 1., 1.], [10., 20., 30.]])
        np.testing.assert_array_equal(mask, [[False]*3, [True]*3])
        self.assertEqual(report['complete_records'], 1)
        self.assertEqual(features[0, names.index('Z_response_missing')], 1.)

    def test_future_fields_cannot_change_allowed_features(self):
        inventory = Inventory([epoch(c) for c in 'ENZ'])
        first = row()
        second = dict(first, source_magnitude=6.5, path_hyp_distance_km=99999,
                      trace_E_snr_db=99999, trace_pga_cmps2=99999,
                      trace_name='DIFFERENT.AA.STA..HH')
        np.testing.assert_array_equal(runner.instrument_arrays(pd.DataFrame([first]), inventory)[0],
                                      runner.instrument_arrays(pd.DataFrame([second]), inventory)[0])
        names = runner.instrument_arrays(pd.DataFrame([first]), inventory)[3]
        self.assertFalse(any(name.startswith(('trace_', 'source_', 'path_')) for name in names))

    def test_epoch_and_location_are_not_guessed(self):
        r = row('1.AA.STA.02.HH', '2.0')
        self.assertEqual(location_code(r), ('02', True))
        self.assertEqual(location_code(dict(r, trace_name='1.AA.OTHER.02.HH')), ('2.0', False))
        inventory = Inventory([epoch('Z'), replace(epoch('Z'), sensitivity=20.)])
        self.assertEqual(inventory.lookup(('AA', 'STA', '', 'HHZ'), utc_seconds(r['trace_start_time']))[0], 'multiple_epochs')
        self.assertEqual(Inventory([epoch('Z')]).lookup(('AA', 'STA', '02', 'HHZ'), utc_seconds(r['trace_start_time']))[0], 'no_channel_key')

    def test_affine_inverse_then_gain_conversion_is_correct(self):
        # Native signal alternates +/-1,2,3; unequal gains prevent a component swap.
        signal = torch.tensor([1., -1.]).repeat(50).reshape(1, 1, 100) * torch.tensor([1., 2., 3.]).reshape(1, 3, 1)
        gains = torch.tensor([[10., 20., 40.]])
        mean = torch.tensor([100., -50., 20.]).reshape(3, 1)
        std = torch.tensor([5., 2., 4.]).reshape(3, 1)
        counts = signal * gains[..., None]
        standardized = (counts - mean) / (std + 1e-8)
        result = runner.native_prefix_features(standardized, mean, std, gains, torch.ones(1, 3, dtype=torch.bool))
        expected = torch.tensor([[0., np.log10(2), np.log10(3)]]).float()
        torch.testing.assert_close(result[:, :3], expected)
        torch.testing.assert_close(result[:, 3:6], expected)
        torch.testing.assert_close(result[:, 9:12], 2*expected)

    def test_prefix_invariance_silence_and_missing_response(self):
        original = torch.randn(2, 3, 500)
        changed = original.clone()
        changed[..., 100:] = 1e20
        mean, std = torch.zeros(3, 1), torch.ones(3, 1)
        gain, mask = torch.ones(2, 3), torch.tensor([[True, False, True], [False]*3])
        a = runner.native_prefix_features(original[..., :100], mean, std, gain, mask)
        b = runner.native_prefix_features(changed[..., :100], mean, std, gain, mask)
        torch.testing.assert_close(a, b)
        torch.testing.assert_close(a[1], torch.zeros(12))
        torch.testing.assert_close(a[:, [1, 4, 7, 10]], torch.zeros(2, 4))
        for n in (100, 300, 500):
            output = runner.native_prefix_features(torch.zeros(2, 3, n), mean, std, gain, mask)
            self.assertTrue(torch.isfinite(output).all())

    def test_invalid_prefix_or_gain_fails(self):
        args = (torch.zeros(3, 1), torch.ones(3, 1), torch.ones(2, 3), torch.ones(2, 3, dtype=torch.bool))
        with self.assertRaises(ValueError):
            runner.native_prefix_features(torch.zeros(2, 3, 200), *args)
        with self.assertRaises(ValueError):
            runner.native_prefix_features(torch.zeros(2, 3, 100), args[0], args[1], torch.zeros(2, 3), args[3])

    def test_reference_rejects_same_label_permutation(self):
        frame = pd.DataFrame([row(), dict(row(), trace_name='1.AA.OTHER..HH')])
        reference = {'targets': np.array([4., 4.]), 'trace_names': frame.trace_name.to_numpy(),
                     'event_ids': np.array(['1', '1']), 'centers': (np.arange(66) + .5)*.1,
                     'logits': np.zeros((2, 66))}
        runner.assert_reference_alignment(frame, reference)
        reference['trace_names'] = reference['trace_names'][::-1]
        with self.assertRaises(ValueError):
            runner.assert_reference_alignment(frame, reference)

    def test_cache_rejects_wrong_duration_or_target_order(self):
        frame = pd.DataFrame([row(), dict(row(), source_magnitude=2.)])
        with tempfile.TemporaryDirectory() as directory:
            with h5py.File(Path(directory) / 'cache.hdf5', 'w') as h:
                group = h.create_group('train')
                group.create_dataset('waveforms', data=np.zeros((2, 3, 100), dtype='float32'))
                group.create_dataset('targets', data=np.array([4., 2.], dtype='float32'))
                runner.assert_cache_alignment(group, frame, 1)
                with self.assertRaises(ValueError):
                    runner.assert_cache_alignment(group, frame, 3)
                group['targets'][:] = [2., 4.]
                with self.assertRaises(ValueError):
                    runner.assert_cache_alignment(group, frame, 1)

    def test_inverse_sampling_and_weighted_normalization_recover_population(self):
        frame = pd.DataFrame({'source_id': ['a']*9+['b']*3, 'source_magnitude': [1.]*9+[4.]*3})
        rows = runner.sample_rows(frame, max_per_event=2)
        self.assertEqual(sum(rows >= 9), 3)
        weights = runner.population_weights(frame, rows)
        values = frame.source_magnitude.to_numpy()[rows, None]
        mean, std = runner.weighted_normalizer(values, weights)
        self.assertAlmostEqual(float(mean[0]), 1.75)
        self.assertAlmostEqual(float(std[0]), np.std(frame.source_magnitude.to_numpy()), places=6)

    def test_equal_dimension_masks_and_training_only_normalizer(self):
        data = synthetic_data()
        arrays, mean, std, masks, base_dim = runner.design_inputs(data)
        self.assertEqual(base_dim, 245)
        self.assertEqual(arrays[0].shape[1], 291)
        self.assertEqual([int(m.sum()) for m in masks.values()], [245, 279, 291])
        for name in ('logits', 'hidden', 'prefix', 'instrument', 'native'):
            data['val_' + name][:] = 1e10
        _, other_mean, other_std, _, _ = runner.design_inputs(data)
        np.testing.assert_array_equal(mean, other_mean)
        np.testing.assert_array_equal(std, other_std)

    def test_fixed_seed_training_is_reproducible_and_ignores_validation_labels(self):
        data = synthetic_data()
        arrays, _, _, masks, _ = runner.design_inputs(data)
        args = Namespace(epochs=2, batch_size=4, learning_rate=5e-4, beta=0., anchor=0.)
        first, state, losses = runner.fit_one(data, arrays, masks['instrument'], args, 123, torch.device('cpu'))
        data['val_y'][:] = 1000
        second, other_state, other_losses = runner.fit_one(data, arrays, masks['instrument'], args, 123, torch.device('cpu'))
        np.testing.assert_array_equal(first, second)
        self.assertEqual(losses, other_losses)
        for key in state:
            torch.testing.assert_close(state[key], other_state[key], rtol=0, atol=0)
        np.testing.assert_allclose(first.sum(1), 1., atol=1e-12)

    def test_zero_residual_and_parameter_budget_are_identical(self):
        data = synthetic_data()
        arrays, _, _, masks, _ = runner.design_inputs(data)
        states, counts = [], []
        for family in runner.FAMILIES:
            torch.manual_seed(123)
            model = runner.ResidualDistribution(arrays[0].shape[1]).eval()
            original = torch.from_numpy(data['train_logits'])
            output = model(torch.from_numpy(arrays[0] * masks[family]), original)
            torch.testing.assert_close(output, original, rtol=0, atol=0)
            states.append(model.state_dict())
            counts.append(sum(p.numel() for p in model.parameters()))
        self.assertEqual(len(set(counts)), 1)
        for key in states[0]:
            torch.testing.assert_close(states[0][key], states[1][key], rtol=0, atol=0)


if __name__ == '__main__':
    unittest.main()

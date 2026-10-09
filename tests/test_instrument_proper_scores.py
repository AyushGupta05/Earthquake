from argparse import Namespace
import copy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/2026-10-09/phase2'))
import instrument_proper_scores as scores
import instrument_residual as baseline
import train_instrument_scores as runner
from audit_and_export import sha256
from feature_residual import ResidualDistribution


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
    options = dict(epochs=3, batch_size=4, learning_rate=5e-4, beta=5., anchor=0.)
    options.update(kwargs)
    return Namespace(**options)


class InstrumentProperScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runner.configure_runtime()

    def test_design_matches_baseline_and_normalizes_from_train_only(self):
        data = fixture_data()
        arrays, mean, std, mask, base = runner.instrument_design(data)
        expected, expected_mean, expected_std, masks, expected_base = baseline.design_inputs(data)
        for a, b in zip(arrays, expected):
            np.testing.assert_array_equal(a, b)
            np.testing.assert_array_equal((a * mask)[:, -12:], 0)
        np.testing.assert_array_equal(mask, masks['instrument'])
        np.testing.assert_array_equal(mean, expected_mean)
        np.testing.assert_array_equal(std, expected_std)
        self.assertEqual(base, expected_base)
        altered = copy.deepcopy(data)
        for key in altered:
            if key.startswith('val_') and altered[key].dtype.kind == 'f':
                altered[key] *= 100
        changed, changed_mean, changed_std, _, _ = runner.instrument_design(altered)
        np.testing.assert_array_equal(arrays[0], changed[0])
        np.testing.assert_array_equal(mean, changed_mean)
        np.testing.assert_array_equal(std, changed_std)

    def test_population_weighted_train_prior_and_empty_threshold_cap(self):
        weights, report = scores.train_marginal_weights([.05, .15, .25], [1., 2., 3.], num_bins=4)
        expected_cdf = np.array([1/6, 3/6, 1.])
        raw = np.minimum(25., 1 / (.01 + expected_cdf * (1 - expected_cdf)))
        np.testing.assert_allclose(report['cdf'], expected_cdf)
        np.testing.assert_allclose(weights, raw / raw.mean(), atol=1e-7)
        self.assertEqual(report['weighted_bin_mass'], [1., 2., 3., 0.])
        self.assertEqual(report['source_split'], 'train')
        self.assertAlmostEqual(report['clipped_threshold_fraction'], 1/3)
        self.assertAlmostEqual(float(weights.mean()), 1., places=6)
        for y, w in [([], []), ([1], [0]), ([1], [-1]), ([1], [np.nan]), ([np.inf], [1]), ([1, 2], [1])]:
            with self.subTest(y=y, w=w), self.assertRaises(ValueError):
                scores.train_marginal_weights(y, w)

    def test_bin_boundaries_and_tail_cut_at_four(self):
        labels = scores.magnitude_labels([-.2, 0, .099, .1, 3.999, 4., 6.6, 7.])
        np.testing.assert_array_equal(labels, [0, 0, 0, 1, 39, 40, 65, 65])
        weights = scores.fixed_tail_weights()
        self.assertEqual(weights.shape, (65,))
        torch.testing.assert_close(weights[:39], torch.ones(39), atol=0, rtol=0)
        torch.testing.assert_close(weights[39:], torch.full((26,), 5.), atol=0, rtol=0)

    def test_proper_scores_have_zero_population_gradient_and_positive_excess(self):
        truth = torch.tensor([.07, .18, .25, .5], dtype=torch.float64)
        labels = torch.arange(4)
        for logarithmic, weights in [(False, None), (False, torch.tensor([1., 5., 5.], dtype=torch.float64)),
                                    (False, torch.tensor([2.2, .4, .4], dtype=torch.float64)), (True, None)]:
            with self.subTest(logarithmic=logarithmic, weights=weights):
                logits = truth.log().requires_grad_()
                batch = logits.expand(4, -1)
                expected = truth @ (scores.ranked_score(batch, labels, weights, logarithmic) + .075 * F.cross_entropy(batch, labels, reduction='none'))
                expected.backward()
                torch.testing.assert_close(logits.grad, torch.zeros_like(logits), atol=2e-16, rtol=0)
                alternative = (truth.log() + torch.tensor([1., -.5, .2, -.3])).expand(4, -1)
                excess = truth @ (scores.ranked_score(alternative, labels, weights, logarithmic) + .075 * F.cross_entropy(alternative, labels, reduction='none')) - expected.detach()
                self.assertGreater(excess.item(), 0.)

    def test_weighted_crps_excess_matches_squared_cdf_distance(self):
        p = torch.tensor([.1, .2, .3, .4], dtype=torch.float64)
        q = torch.tensor([.3, .1, .2, .4], dtype=torch.float64)
        w = torch.tensor([.3, 1., 4.], dtype=torch.float64)
        labels = torch.arange(4)
        actual = q @ (scores.ranked_score(p.log().expand(4, -1), labels, w) - scores.ranked_score(q.log().expand(4, -1), labels, w))
        expected = .1 * (w * (p.cumsum(0)[:-1] - q.cumsum(0)[:-1]).square()).sum()
        torch.testing.assert_close(actual, expected, atol=1e-16, rtol=0)

    def test_extreme_logits_have_finite_losses_and_gradients(self):
        logits0 = torch.full((3, 66), -1e4)
        logits0[0, 0] = logits0[1, 32] = logits0[2, 65] = 1e4
        labels = torch.tensor([65, 0, 32])
        for control in scores.CONTROLS:
            logits = logits0.clone().requires_grad_()
            value = scores.objective_vector(logits, labels.float() * .1, labels,
                (torch.arange(66) + .5) * .1, torch.zeros(3), control, torch.ones(65))
            self.assertTrue(torch.isfinite(value).all())
            self.assertEqual(value.shape, (3,))
            value.sum().backward()
            self.assertTrue(torch.isfinite(logits.grad).all())

    def test_rejects_inconsistent_thresholds_labels_and_controls(self):
        logits, labels = torch.zeros(2, 66), torch.tensor([0, 65])
        for weights in [torch.ones(66), torch.zeros(65), torch.full((65,), float('nan'))]:
            with self.assertRaises(ValueError):
                scores.ranked_score(logits, labels, weights)
        for bad in [torch.tensor([-1, 2]), torch.tensor([0, 66]), torch.tensor([0])]:
            with self.assertRaises(ValueError):
                scores.ranked_score(logits, bad)
        with self.assertRaises(TypeError):
            scores.ranked_score(logits, labels.float())
        with self.assertRaises(ValueError):
            scores.ranked_score(torch.zeros(2, 1), torch.zeros(2, dtype=torch.int64))
        with self.assertRaises(ValueError):
            scores.objective_vector(logits, labels.float(), labels, torch.arange(66), torch.zeros(2), 'marginal_crps_ce', None)

    def test_huber_fit_exactly_replays_original_both_seeds_and_rng(self):
        data, args = fixture_data(), fit_args()
        arrays, _, _, mask, _ = runner.instrument_design(data)
        prior, _ = scores.train_marginal_weights(data['train_y'], data['weights'])
        for seed in (20261009, 20261010):
            expected, original, loss = baseline.fit_one(data, arrays, mask, args, seed, torch.device('cpu'))
            rng = torch.get_rng_state().clone()
            actual, state, history, _ = runner.fit_one(data, arrays, mask, args, seed, torch.device('cpu'), 'huber_ce', prior)
            np.testing.assert_array_equal(actual, expected)
            self.assertEqual(history, loss)
            torch.testing.assert_close(torch.get_rng_state(), rng, atol=0, rtol=0)
            for key in original:
                torch.testing.assert_close(state[key], original[key], atol=0, rtol=0)

    def test_huber_ignores_prior_and_all_fits_ignore_validation_targets(self):
        data, args = fixture_data(), fit_args(epochs=2)
        arrays, _, _, mask, _ = runner.instrument_design(data)
        prior, _ = scores.train_marginal_weights(data['train_y'], data['weights'])
        for control in scores.CONTROLS:
            a, ast, ah, atrace = runner.fit_one(data, arrays, mask, args, 20261009, torch.device('cpu'), control, prior)
            rng = torch.get_rng_state().clone()
            changed = copy.deepcopy(data)
            changed['val_y'][:] = -900.
            unused_prior = np.full_like(prior, np.nan) if control == 'huber_ce' else prior
            b, bst, bh, btrace = runner.fit_one(changed, arrays, mask, args, 20261009, torch.device('cpu'), control, unused_prior)
            np.testing.assert_array_equal(a, b)
            self.assertEqual(ah, bh)
            self.assertEqual(atrace, btrace)
            torch.testing.assert_close(torch.get_rng_state(), rng, atol=0, rtol=0)
            for key in ast:
                torch.testing.assert_close(ast[key], bst[key], atol=0, rtol=0)

    def test_every_control_has_identical_initialization_order_and_rng_consumption(self):
        data, args = fixture_data(), fit_args(epochs=2)
        arrays, _, _, mask, _ = runner.instrument_design(data)
        prior, _ = scores.train_marginal_weights(data['train_y'], data['weights'])
        traces, rngs = [], []
        for control in scores.CONTROLS:
            _, _, _, trace = runner.fit_one(data, arrays, mask, args, 20261009, torch.device('cpu'), control, prior)
            traces.append(trace)
            rngs.append(torch.get_rng_state().clone())
        for trace, rng in zip(traces[1:], rngs[1:]):
            for key in ('initial_model_sha256', 'epoch_order_sha256', 'parameters'):
                self.assertEqual(trace[key], traces[0][key])
            torch.testing.assert_close(rng, rngs[0], atol=0, rtol=0)

    def test_complete_runner_archives_train_provenance_and_reloadable_checkpoints(self):
        data = fixture_data()
        with tempfile.TemporaryDirectory() as directory:
            args = runner.parse_args(['--seconds', '3', '--inventory', str(Path(directory) / 'fixture.tgz'),
                '--output', str(Path(directory) / 'runs'), '--device', 'cpu', '--epochs', '1', '--seeds', '20261009',
                '--expected-train-records', '12', '--batch-size', '4'])
            identities = {'scope': 'mocked extraction; loss/runner exercised', 'train_metadata_sha256': 'a' * 64}
            with patch.object(baseline, 'extract', return_value=(data, identities, {'synthetic': True}, [f'f{i}' for i in range(34)])):
                output = runner.run(args)
            traces = json.loads((output / 'training_traces.json').read_text())
            prior = json.loads((output / 'train_marginal_prior.json').read_text())
            self.assertEqual(prior['targets_sha256'], runner.array_digest(data['train_y']))
            self.assertEqual(prior['weights_sha256'], runner.array_digest(data['weights']))
            self.assertEqual(prior['source_split'], 'train')
            expected_weights, _ = scores.train_marginal_weights(data['train_y'], data['weights'])
            np.testing.assert_array_equal(prior['weights'], expected_weights)
            runtime = json.loads((output / 'run.json').read_text())['runtime']
            self.assertTrue(runtime['deterministic_algorithms'])
            self.assertTrue(runtime['cudnn_deterministic'])
            self.assertFalse(runtime['cudnn_benchmark'])
            self.assertEqual(type(runtime['torch']), str)
            with np.load(output / 'training_rows.npz', allow_pickle=False) as rows:
                np.testing.assert_array_equal(rows['row_index'], data['train_rows'])
                np.testing.assert_array_equal(rows['targets'], data['train_y'])
            with np.load(output / 'predictions.npz', allow_pickle=False) as predictions:
                np.testing.assert_array_equal(predictions['event_ids'], data['val_ids'])
                for control in scores.CONTROLS:
                    name = control + '_seed20261009'
                    checkpoint = torch.load(output / (name + '.pth'), map_location='cpu', weights_only=True)
                    model = ResidualDistribution(291)
                    model.load_state_dict(checkpoint['model'])
                    self.assertEqual(runner.model_digest(model), traces[name]['final_model_sha256'])
                    self.assertEqual(checkpoint['feature_mask'].shape, (291,))
                    with np.load(output / (control + '_probabilities.npz'), allow_pickle=False) as probabilities:
                        np.testing.assert_array_equal(probabilities['trace_names'], data['val_trace_names'])
                        np.testing.assert_allclose(probabilities['mean_probability'] @ probabilities['centers'],
                            predictions[control + '_ensemble_mean'], atol=3e-7, rtol=0)
            artifacts = json.loads((output / 'artifacts.json').read_text())
            self.assertNotIn('artifacts.json', artifacts)
            for name, identity in artifacts.items():
                self.assertEqual(identity['sha256'], sha256(output / name))
                self.assertEqual(identity['bytes'], (output / name).stat().st_size)

    def test_default_protocol_and_argument_rejections(self):
        base = ['--seconds', '1', '--inventory', 'fixture.tgz']
        args = runner.parse_args(base)
        self.assertEqual((args.max_per_event, args.expected_train_records, args.epochs), (0, 979487, 15))
        self.assertEqual(args.seeds, [20261009, 20261010])
        self.assertEqual(args.controls, list(scores.CONTROLS))
        for extra in [['--epochs', '0'], ['--learning-rate', 'nan'], ['--expected-train-records', '0'],
                      ['--max-per-event', '-1'], ['--seeds', '1', '1'], ['--controls', 'crps_ce', 'crps_ce']]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                runner.parse_args(base + extra)


if __name__ == '__main__':
    unittest.main()

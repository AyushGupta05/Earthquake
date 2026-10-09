import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/2026-10-09/phase2'))
import censored_innovation as pilot


def prepared(n=12):
    generator = torch.Generator().manual_seed(37)
    context = torch.randn(n, 5, generator=generator)
    prior = torch.randn(n, 3, generator=generator).double().log_softmax(1)
    z = torch.randn(n, 2, generator=generator).double()
    valid = torch.ones(n, 2, dtype=torch.bool)
    valid[0] = False
    valid[1, 1] = False
    return context, prior, z, valid, torch.arange(3).float() + .5


class InnovationTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)

    def waveform(self):
        x = torch.full((1, 600), 10., dtype=torch.double)
        x[:, 10:100] = 12.
        x[:, 100:300] = 11.
        x[:, 300:500] = 14.
        return x

    def observe(self, x, gain=None, usable=None, unit=None, floor=1e-12):
        n = len(x)
        return pilot.vertical_innovations(x, torch.ones(n).double() if gain is None else gain,
                                          torch.ones(n, dtype=torch.bool) if usable is None else usable,
                                          torch.ones(n, dtype=torch.long) if unit is None else unit, floor)

    def test_fixed_first_ten_post_p_baseline_and_block_ratio_identity(self):
        o = self.observe(self.waveform())
        expected = torch.tensor([[-np.log10(2), np.log10(2)]], dtype=torch.double)
        torch.testing.assert_close(o.z, expected, atol=1e-14, rtol=0)
        torch.testing.assert_close(o.g, expected.clamp_min(0), atol=1e-14, rtol=0)
        self.assertTrue(o.valid.all())
        # Prefix-dependent demeaning would produce different ratios here.
        shifted = self.observe(self.waveform() + 1234.)
        torch.testing.assert_close(o.z, shifted.z, atol=0, rtol=0)

    def test_prefixes_and_post_deadline_values_cannot_affect_earlier_innovation(self):
        x = self.waveform()
        full, short = self.observe(x), self.observe(x[:, :300])
        torch.testing.assert_close(full.z[:, 0], short.z[:, 0], atol=0, rtol=0)
        self.assertFalse(short.valid[:, 1].any())
        self.assertFalse(self.observe(x[:, :100]).valid.any())
        self.assertFalse(self.observe(x[:, :299]).valid.any())
        x[:, 300:] = float('nan')
        changed = self.observe(x)
        torch.testing.assert_close(changed.z[:, 0], full.z[:, 0], atol=0, rtol=0)
        self.assertTrue(changed.valid[:, 0].all())
        self.assertFalse(changed.valid[:, 1].any())
        x = self.waveform()
        x[:, 500:] = float('nan')
        torch.testing.assert_close(self.observe(x).z, full.z, atol=0, rtol=0)

    def test_gain_invariance_and_floor_missingness(self):
        x = self.waveform().expand(3, -1).clone()
        gain = torch.tensor([1., 1000., 1e-4], dtype=torch.double)
        c = torch.tensor([1e-3, 1e6, 40.], dtype=torch.double)
        first = self.observe(x, gain)
        second = self.observe(x * c[:, None], gain * c)
        torch.testing.assert_close(first.z, second.z, atol=1e-12, rtol=0)
        torch.testing.assert_close(first.valid, second.valid)
        # Away from the floor, the ratio itself also cancels scalar sensitivity.
        torch.testing.assert_close(first.z, self.observe(x).z, atol=1e-12, rtol=0)
        bad_gain = torch.tensor([float('nan'), 0., -1.], dtype=torch.double)
        self.assertFalse(self.observe(x, bad_gain).valid.any())
        self.assertFalse(self.observe(x, unit=torch.zeros(3, dtype=torch.long)).valid.any())
        self.assertFalse(self.observe(x, usable=torch.zeros(3, dtype=torch.bool)).valid.any())
        self.assertFalse(self.observe(x, floor=4.).valid.any())
        self.assertTrue(torch.isfinite(self.observe(x, bad_gain).z).all())
        z = x.clone()
        z[:, 100:300] = 10.  # no new-block motion: omitted identically by every arm
        self.assertFalse(self.observe(z).valid.any())
        with self.assertRaises(ValueError):
            self.observe(x, unit=torch.tensor([1, 2, 3]))

    def test_affine_cache_inverse_uses_exact_float32_epsilon(self):
        raw = torch.tensor([[[1., 2.], [3., 4.], [5., 6.]]])
        mean = torch.tensor([1., 2., 3.]).reshape(1, 3, 1)
        std = torch.tensor([1e-7, .5, 4.]).reshape(1, 3, 1)
        scaled = (raw - mean) / (std + 1e-8)
        restored = pilot.undo_count_standardization(scaled, mean, std)
        torch.testing.assert_close(restored, raw.double(), atol=1e-7, rtol=0)
        with self.assertRaises(ValueError):
            pilot.undo_count_standardization(scaled, mean, -std)

    def test_mixed_likelihood_normalizes_and_zero_is_not_density(self):
        sigma = .4
        raw_scale = np.log(np.expm1(sigma - .03))
        parameters = torch.tensor([-.2, raw_scale, -.7], dtype=torch.double)
        grid = torch.linspace(1e-8, 15., 100000, dtype=torch.double)
        for arm in ('censored', 'hurdle', 'hurdle_truncated'):
            atom = pilot.observation_log_likelihood(arm, torch.tensor(0.), parameters).exp()
            density = pilot.observation_log_likelihood(arm, grid, parameters).exp()
            total = atom + torch.trapezoid(density, grid)
            self.assertAlmostEqual(float(total), 1., places=5)
        zero = pilot.observation_log_likelihood('censored', torch.tensor(0.), parameters)
        wrong = pilot.observation_log_likelihood('uncensored', torch.tensor(0.), parameters)
        self.assertGreater(abs(float(zero - wrong)), .1)
        with self.assertRaises(ValueError):
            pilot.observation_log_likelihood('censored', torch.tensor(-.1), parameters)

    def test_extreme_atom_nll_and_gradients_are_finite(self):
        for arm in pilot.GENERATIVE_ARMS:
            parameters = torch.tensor([[1000., -1000., 1000.], [-1000., 1000., -1000.]], dtype=torch.double, requires_grad=True)
            for values in (torch.tensor([0., 0.]), torch.tensor([1e-12, 1e4])):
                loss = -pilot.observation_log_likelihood(arm, values, parameters).sum()
                self.assertTrue(torch.isfinite(loss))
                gradient, = torch.autograd.grad(loss, parameters, retain_graph=True)
                self.assertTrue(torch.isfinite(gradient).all())

    def test_free_truncated_hurdle_matches_censored_when_atom_is_tied(self):
        parameters = torch.tensor([[-1., -.4, 0.], [.3, .2, 0.], [2., -.6, 0.]], dtype=torch.double)
        sigma = torch.nn.functional.softplus(parameters[:, 1]) + .03
        a = parameters[:, 0] / sigma
        parameters[:, 2] = torch.special.log_ndtr(-a) - torch.special.log_ndtr(a)
        for value in (0., .01, .5, 3.):
            observation = torch.full((3,), value, dtype=torch.double)
            tied = pilot.observation_log_likelihood('censored', observation, parameters)
            free = pilot.observation_log_likelihood('hurdle_truncated', observation, parameters)
            torch.testing.assert_close(tied, free, atol=1e-13, rtol=0)

    def test_zero_observation_updates_and_equal_likelihood_does_not(self):
        log_prior = torch.tensor([[.9, .1]], dtype=torch.double).log()
        parameters = torch.tensor([[[-1., 0., 0.], [1., 0., 0.]]], dtype=torch.double)
        log_q = pilot.observation_log_likelihood('censored', torch.zeros(1, 1), parameters)
        updated = pilot.normalized_update(log_prior, log_q, torch.tensor([True]))
        self.assertLess(float(updated.exp()[0, 1]), .1)
        same = pilot.normalized_update(log_prior, torch.full_like(log_prior, 12.), torch.tensor([True]))
        torch.testing.assert_close(same, log_prior, rtol=0, atol=0)
        masked = pilot.normalized_update(log_prior, log_q, torch.tensor([False]))
        torch.testing.assert_close(masked, log_prior, rtol=0, atol=0)
        self.assertAlmostEqual(float(updated.exp().sum()), 1., places=14)
        with self.assertRaises(ValueError):
            pilot.normalized_update(log_prior + 1, log_q, torch.tensor([True]))

    def test_equal_initial_likelihood_keeps_discriminative_gradients(self):
        prior = torch.tensor([[.9, .1]], dtype=torch.double).log()
        log_q = torch.zeros_like(prior, requires_grad=True)
        p = pilot.normalized_update(prior, log_q, torch.tensor([True]))
        (-p[0, 1]).backward()
        torch.testing.assert_close(log_q.grad, torch.tensor([[.9, -.9]], dtype=torch.double), atol=1e-14, rtol=0)

    def test_huge_common_log_density_offset_preserves_prior_odds_and_normalization(self):
        prior = torch.tensor([[.2, .3, .5]], dtype=torch.double).log()
        likelihood = torch.tensor([[-1e20, -1e20, -2e20]], dtype=torch.double)
        updated = pilot.normalized_update(prior, likelihood, torch.tensor([True])).exp()
        torch.testing.assert_close(updated, torch.tensor([[.4, .6, 0.]], dtype=torch.double), atol=1e-14, rtol=0)

    def test_all_arm_initializations_parameters_and_one_second_predictions_match(self):
        context, prior, z, valid, centers = prepared()
        states, counts = [], []
        for arm in pilot.ARMS:
            torch.manual_seed(14)
            model = pilot.InnovationHead(5, arm)
            states.append(model.state_dict())
            counts.append(sum(p.numel() for p in model.parameters()))
            p = model(context, prior, z, valid, centers)
            torch.testing.assert_close(p, pilot.frozen_predictions(prior), rtol=0, atol=0)
        self.assertEqual(len(set(counts)), 1)
        for state in states[1:]:
            for key in states[0]:
                torch.testing.assert_close(state[key], states[0][key], rtol=0, atol=0)

    def test_generative_parameters_cannot_see_current_and_13_cannot_see_history(self):
        context, prior, z, valid, centers = prepared()
        for arm in pilot.ARMS:
            torch.manual_seed(91)
            model = pilot.InnovationHead(5, arm)
            torch.nn.init.normal_(model.net[-1].weight, std=.1)
            m = centers[None].expand(len(context), -1)
            first = model.parameters_for(context, m, z[:, 0], z[:, 1], 0)
            altered_history = model.parameters_for(context, m, z[:, 0] + 10, z[:, 1], 0)
            torch.testing.assert_close(first, altered_history, rtol=0, atol=0)
            if arm != 'discriminative':
                second = model.parameters_for(context, m, z[:, 0], z[:, 1], 1)
                altered_current = model.parameters_for(context, m, z[:, 0], z[:, 1] + 20, 1)
                torch.testing.assert_close(second, altered_current, rtol=0, atol=0)
            outputs = model(context, prior, z, valid, centers)
            later = z.clone()
            later[:, 1] += 2
            changed = model(context, prior, later, valid, centers)
            torch.testing.assert_close(outputs[:, :2], changed[:, :2], rtol=0, atol=0)

    def test_censored_history_discards_negative_values_uncensored_retains_them(self):
        context, prior, z, valid, centers = prepared()
        z[:, 0] = -.2
        z[:, 1] = .3
        changed = z.clone()
        changed[:, 0] = -3.
        for arm in pilot.ARMS:
            torch.manual_seed(56)
            model = pilot.InnovationHead(5, arm)
            torch.nn.init.normal_(model.net[-1].weight, std=.1)
            p = model(context, prior, z, valid, centers)
            q = model(context, prior, changed, valid, centers)
            if arm == 'uncensored':
                self.assertGreater(float((p - q).detach().abs().max()), 1e-5)
            else:
                torch.testing.assert_close(p, q, rtol=0, atol=0)

    def test_masked_values_and_missing_first_step(self):
        context, prior, z, valid, centers = prepared()
        changed = z.clone()
        changed[~valid] = 1e100
        for arm in pilot.ARMS:
            model = pilot.InnovationHead(5, arm)
            torch.nn.init.normal_(model.net[-1].weight, std=.1)
            p = model(context, prior, z, valid, centers)
            q = model(context, prior, changed, valid, centers)
            torch.testing.assert_close(p, q, rtol=0, atol=0)
            torch.testing.assert_close(p[0], prior[0].expand(3, -1), rtol=0, atol=0)
        bad = valid.clone()
        bad[0] = torch.tensor([False, True])
        with self.assertRaises(ValueError):
            model(context, prior, z, bad, centers)

    def test_training_fixed_order_reproducible_and_frozen_inputs_receive_no_gradient(self):
        context, prior, z, valid, centers = prepared()
        context.requires_grad_(True)
        prior.requires_grad_(True)
        z.requires_grad_(True)
        labels = torch.arange(len(context)) % 3
        weights = torch.linspace(.5, 2., len(context))
        config = pilot.FitConfig(epochs=2, batch_size=4, width=8)
        orders = []
        for arm in pilot.ARMS:
            model, history = pilot.fit_arm(context, prior, z, valid, labels, weights, centers, arm, 20, config)
            other, history2 = pilot.fit_arm(context, prior, z, valid, labels, weights, centers, arm, 20, config)
            self.assertEqual(history, history2)
            orders.append([h['row_order_sha256'] for h in history])
            for key, value in model.state_dict().items():
                torch.testing.assert_close(value, other.state_dict()[key], rtol=0, atol=0)
            self.assertGreater(float(model.net[-1].weight.detach().abs().sum()), 0.)
            self.assertTrue(all(np.isfinite(h['loss']) for h in history))
            log_p = model(context, prior, z, valid, centers)
            torch.testing.assert_close(log_p.exp().sum(-1), torch.ones(log_p.shape[:2], dtype=torch.double), rtol=0, atol=1e-12)
        self.assertTrue(all(order == orders[0] for order in orders))
        self.assertIsNone(context.grad)
        self.assertIsNone(prior.grad)
        self.assertIsNone(z.grad)
        self.assertEqual(pilot.FitConfig().epochs, 15)
        self.assertEqual(pilot.SEEDS, (20261009, 20261010))

    def test_checkpoint_adapter_identity_and_probability_reproduction(self):
        import instrument_residual as source
        from test_instrument_residual import synthetic_data
        data = synthetic_data()
        for split in ('train', 'val'):
            n = len(data[split + '_y'])
            data[split + '_ids'] = np.array([f'{split}{i}' for i in range(n)])
            data[split + '_trace_names'] = np.array([f'{split}trace{i}' for i in range(n)])
        data['train_rows'] = np.arange(len(data['train_y']))
        identities = {k: k for k in ('metadata_sha256', 'normalization_sha256', 'inventory_sha256', 'checkpoint_sha256', 'preprocessing')}
        arrays, mean, std, masks, base_dim = source.design_inputs(data)
        names = [f'feature{i}' for i in range(34)]
        model = source.ResidualDistribution(291).eval()
        torch.nn.init.normal_(model.net[-1].weight, std=.01)
        with torch.inference_mode():
            val_probability = model(torch.from_numpy(arrays[1] * masks['instrument']), torch.from_numpy(data['val_logits'])).double().softmax(1).numpy()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = {'config': {'seconds': 1, 'epochs': 15, 'beta': 5., 'anchor': 0., 'max_per_event': 4},
                          'family': 'instrument', 'seed': 123, 'model': model.state_dict(),
                          'feature_mean': torch.from_numpy(mean), 'feature_std': torch.from_numpy(std),
                          'feature_mask': torch.from_numpy(masks['instrument']), 'base_dim': base_dim,
                          'instrument_names': names, 'native_names': source.NATIVE_FEATURE_NAMES}
            torch.save(checkpoint, root / 'instrument_seed123.pth')
            (root / 'input_identities.json').write_text(json.dumps(identities))
            np.savez(root / 'training_rows.npz', row_index=data['train_rows'], event_ids=data['train_ids'], trace_names=data['train_trace_names'], weights=data['weights'])
            np.savez(root / 'instrument_probabilities.npz', targets=data['val_y'], event_ids=data['val_ids'], trace_names=data['val_trace_names'], centers=data['centers'], seed123=val_probability.astype(np.float32))
            contexts, priors, provenance = pilot.load_frozen_start(data, identities, names, root, 123, batch_size=4)
            np.testing.assert_array_equal(contexts[0][:, -12:], 0.)
            np.testing.assert_allclose(np.exp(priors[1]), val_probability, atol=2e-8, rtol=0)
            self.assertEqual(len(provenance['files_sha256']), 4)
            changed = copy.deepcopy(data)
            changed['train_trace_names'] = changed['train_trace_names'][::-1]
            with self.assertRaises(ValueError):
                pilot.load_frozen_start(changed, identities, names, root, 123)
            wrong = dict(identities, checkpoint_sha256='wrong')
            with self.assertRaises(ValueError):
                pilot.load_frozen_start(data, wrong, names, root, 123)
            checkpoint['config']['seconds'] = 3
            torch.save(checkpoint, root / 'instrument_seed123.pth')
            with self.assertRaises(ValueError):
                pilot.load_frozen_start(data, identities, names, root, 123)


if __name__ == '__main__':
    unittest.main()

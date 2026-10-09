import copy
import json
import math
import unittest
from pathlib import Path

import numpy as np
import torch

from shared_cap import (COUNTERFACTUAL, FLOOR, PROTOCOL_SHA, Density, contrasts,
                        covariance, equal_event_weights, event_folds, gaussian_logpdf,
                        initial_parameters, moment_match, sha256, validate_arrays)
from run_preflight import bootstrap, event_values, fit, summarize

torch.set_num_threads(1)
torch.set_default_dtype(torch.float64)


def base_parameters():
    p = torch.zeros(11)
    p[:3] = torch.logit(torch.tensor([3.5 / 8, .7 / 4, .6 / 4]))
    p[3] = torch.logit(torch.tensor((1 - .05) / 2.95))
    p[8], p[9], p[10] = -1., .1, -.8
    return p


class ContrastTests(unittest.TestCase):
    def test_signed_innovation_recovery(self):
        peaks = torch.tensor([[2., 1., 4.], [2., 8., 1.], [4., 3., 1.]])
        logs = peaks.log10()
        z = torch.stack((logs[:, 1] - logs[:, 0], logs[:, 2] - logs[:, :2].amax(1)), 1)
        torch.testing.assert_close(contrasts(z, 5), logs[:, 1:] - logs[:, :1])
        self.assertLess(float(z[0, 0]), 0)

    def test_gain_invariance_away_from_floor(self):
        x = torch.tensor([[2., 7., 4.], [9., 2., 1.]])
        def observe(peaks):
            a = peaks.log10()
            return torch.stack((a[:, 1] - a[:, 0], a[:, 2] - a[:, :2].amax(1)), 1)
        for gain in (1e-7, .1, 1e7):
            torch.testing.assert_close(contrasts(observe(x), 5), contrasts(observe(x * gain), 5), atol=1e-14, rtol=0)

    def test_future_coordinate_is_not_read(self):
        first = torch.tensor([[.2, .7], [-.4, -.2]])
        bad = first.clone()
        bad[:, 1] = float('nan')
        for arm in ('shared_cap', 'moment_matched', COUNTERFACTUAL):
            model = Density(arm, base_parameters())
            mag = torch.tensor([3.8, 4.2])
            self.assertTrue(torch.equal(model.log_likelihood(first, mag, 3), model.log_likelihood(bad, mag, 3)))
            self.assertTrue(torch.equal(model.marginal_pit(first, mag, 3), model.marginal_pit(bad, mag, 3)))
            self.assertTrue(torch.equal(model.log_likelihood(bad, mag, 1), torch.zeros(2)))


class DensityTests(unittest.TestCase):
    def test_full_gaussian_matches_reference(self):
        mean = torch.tensor([[.3, -.7], [2., 3.]])
        cov = torch.tensor([[[.5, .1], [.1, .8]], [[2., -.4], [-.4, 1.]]])
        x = torch.tensor([[-.5, 1.], [1., 2.]])
        expected = torch.distributions.MultivariateNormal(mean, covariance_matrix=cov).log_prob(x)
        torch.testing.assert_close(gaussian_logpdf(x, mean, cov), expected)
        expected1 = torch.distributions.Normal(mean[:, 0], cov[:, 0, 0].sqrt()).log_prob(x[:, 0])
        torch.testing.assert_close(gaussian_logpdf(x[:, :1], mean[:, :1], cov[:, :1, :1]), expected1)

    def test_exact_moment_matching(self):
        weights = torch.tensor([.2, .3, .5])
        means = torch.tensor([[[0., 0.], [1., 2.], [3., -1.]], [[2., 1.], [0., 0.], [1., -2.]]])
        noise = torch.tensor([[.3, -.08], [-.08, .2]])
        mu, cov = moment_match(weights, means, noise)
        manual_mu = sum(weights[k] * means[:, k] for k in range(3))
        manual_cov = torch.stack([noise + sum(weights[k] * torch.outer(means[i, k] - manual_mu[i], means[i, k] - manual_mu[i])
                                              for k in range(3)) for i in range(2)])
        torch.testing.assert_close(mu, manual_mu)
        torch.testing.assert_close(cov, manual_cov)
        self.assertTrue((torch.linalg.eigvalsh(cov) > 0).all())

    def test_mixture_normalization_1d_and_2d(self):
        model = Density('shared_cap', base_parameters())
        x = torch.linspace(-8., 8., 501)
        z = torch.stack((x, torch.zeros_like(x)), 1)
        pdf = model.log_likelihood(z, torch.full_like(x, 4.), 3).exp()
        self.assertAlmostEqual(float(torch.trapezoid(pdf, x).detach()), 1., places=10)
        a, b = torch.meshgrid(x, x, indexing='ij')
        # Inverse of contrasts: z35=d15-max(0,d13), unit Jacobian.
        z = torch.stack((a.flatten(), b.flatten() - a.flatten().clamp_min(0)), 1)
        pdf = model.log_likelihood(z, torch.full((len(z),), 4.), 5).exp().reshape(len(x), len(x))
        integral = torch.trapezoid(torch.trapezoid(pdf, x, dim=1), x)
        self.assertAlmostEqual(float(integral.detach()), 1., places=10)

    def test_uninformative_amplitude_null(self):
        z = torch.tensor([[-.2, .4], [-.2, .4]])
        for magnitude in (torch.tensor([-3., -2.]), torch.tensor([12., 13.])):
            for seconds in (3, 5):
                results = []
                for arm in ('shared_cap', 'moment_matched'):
                    ll = Density(arm, base_parameters()).log_likelihood(z, magnitude, seconds)
                    torch.testing.assert_close(ll[0], ll[1], atol=1e-14, rtol=0)
                    results.append(ll)
                torch.testing.assert_close(*results, atol=1e-14, rtol=0)

    def test_single_component_limit(self):
        p = base_parameters()
        p[4], p[5] = 100., -100.
        z, m = torch.tensor([[.2, -.3]]), torch.tensor([4.])
        mixture = Density('shared_cap', p)
        gaussian = Density('moment_matched', p)
        torch.testing.assert_close(mixture.log_likelihood(z, m, 5), gaussian.log_likelihood(z, m, 5), atol=1e-14, rtol=0)

    def test_covariance_floor_and_finite_gradient(self):
        p = base_parameters()
        p[8:] = torch.tensor([-100., 0., -100.])
        model = Density('shared_cap', p)
        cov = covariance(model.raw[8:])
        torch.testing.assert_close(cov, torch.eye(2) * FLOOR, atol=1e-16, rtol=0)
        loss = -model.log_likelihood(torch.tensor([[.1, -.2]]), torch.tensor([3.8]), 5).sum()
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertTrue(torch.isfinite(model.raw.grad).all())

    def test_determinant_penalizes_uninformative_variance(self):
        x = torch.zeros(1, 2)
        narrow = gaussian_logpdf(x, x, torch.eye(2))
        broad = gaussian_logpdf(x, x, torch.eye(2) * 4)
        self.assertAlmostEqual(float(narrow - broad), math.log(4), places=13)

    def test_initialization_identical_and_fit_independent(self):
        gen = torch.Generator().manual_seed(11)
        m = torch.linspace(2., 5., 50)
        z = torch.randn((50, 2), generator=gen) * .3
        weights = torch.ones(50) / 50
        initial = initial_parameters(m, contrasts(z, 5), weights, 20261009)
        other = initial_parameters(m, contrasts(z, 5), weights, 20261009)
        self.assertTrue(torch.equal(initial, other))
        options = {'max_iter': 10, 'max_eval': 15, 'history_size': 5, 'line_search': 'strong_wolfe',
                   'tolerance_grad': 1e-7, 'tolerance_change': 1e-10}
        mm, ml = fit('moment_matched', initial, z, m, weights, options)
        cap, cl = fit('shared_cap', initial, z, m, weights, options)
        self.assertEqual(ml['initial_sha256'], cl['initial_sha256'])
        self.assertFalse(torch.equal(mm.raw, cap.raw))
        for log in (ml, cl):
            self.assertLessEqual(log['closure_nll'][-1], log['closure_nll'][0])

    def test_probability_integral_transform(self):
        model = Density('moment_matched', base_parameters())
        m = torch.tensor([4.])
        w, means, cov = model.components(m)
        mu, _ = moment_match(w, means, cov)
        z = torch.stack((mu[:, 0], mu[:, 1] - mu[:, 0].clamp_min(0)), 1)
        torch.testing.assert_close(model.marginal_pit(z, m, 5), torch.full((1, 2), .5))


class IdentityTests(unittest.TestCase):
    def fixture(self):
        data = {'z': np.zeros((4, 2)), 'valid': np.ones((4, 2), dtype=bool),
                'above_floor': np.ones((4, 3), dtype=bool), 'invalid_reason_code': np.zeros((4, 2), dtype=np.int16),
                'physical_unit_z': np.array([1, 2, 1, 2]), 'targets': np.array([3., 3., 4., 4.]),
                'row_index': np.array([1, 3, 5, 7]), 'event_ids': np.array(['a', 'a', 'b', 'b']),
                'trace_names': np.array(['a1', 'a2', 'b1', 'b2'])}
        return data, {'expected_rows': 4, 'required_columns': list(data)}

    def test_pinned_protocol_hash(self):
        self.assertEqual(sha256(Path(__file__).with_name('protocol.json')), PROTOCOL_SHA)

    def test_source_validation(self):
        data, protocol = self.fixture()
        validate_arrays(data, protocol)
        for key, index, value in [('targets', 1, 3.01), ('row_index', 2, 3), ('trace_names', 1, 'a1')]:
            bad = copy.deepcopy(data)
            bad[key][index] = value
            with self.assertRaises(ValueError):
                validate_arrays(bad, protocol)

    def test_invalid_floor_mask_and_reason_preserved(self):
        data, protocol = self.fixture()
        data['valid'][1, 1] = False
        data['invalid_reason_code'][1, 1] = 32
        data['above_floor'][1, 2] = False
        validated = validate_arrays(data, protocol)
        self.assertEqual(validated['invalid_reason_code'][1, 1], 32)
        data['valid'][1, 1] = True
        with self.assertRaises(ValueError):
            validate_arrays(data, protocol)

    def test_event_split_and_weighting(self):
        ids = np.array(['x', 'x', 'y', 'z', 'z', 'z'])
        folds = event_folds(ids, 'salt')
        self.assertEqual(folds[0], folds[1])
        self.assertEqual(folds[3], folds[5])
        weight = equal_event_weights(ids)
        for event in np.unique(ids):
            self.assertAlmostEqual(float(weight[ids == event].sum()), 1 / 3)
        events, values = event_values(np.arange(6.), ids)
        np.testing.assert_array_equal(events, ['x', 'y', 'z'])
        np.testing.assert_allclose(values, [.5, 2., 4.])

    def test_summary_event_macro_and_bootstrap_sign(self):
        ids = np.array(['a', 'a', 'a', 'b'])
        y = np.array([3., 3., 3., 4.])
        result = summarize(np.array([1., 1., 1., 5.]), ids, y)
        self.assertEqual(result['all']['nll'], 3.)
        self.assertEqual(result['M_ge_4.0']['nll'], 5.)
        boot = bootstrap(np.full(20, -.1))
        np.testing.assert_allclose(boot['ci95'], [-.1, -.1])


if __name__ == '__main__':
    unittest.main()

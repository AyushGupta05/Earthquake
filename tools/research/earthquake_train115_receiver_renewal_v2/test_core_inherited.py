"""Invented low-level observations only; no scientific data or learned fit."""
import math
import unittest
import numpy as np
from numerical_core import (Mixture, Hazard, NumericalFailure, transitions, log_likelihood,
                     joint_loss, gauss_hermite, adaptive, checked_inference)


def mixture(sigma=.4):
    return Mixture([.1, .2, .3, .25, .15], [3., 4., 5., 6., 7.], [sigma] * 5)


def hazard(arm="C", beta=(.1, -.1), extra=(.15, -.2)):
    return Hazard(arm, [-.4, -.7], beta, np.array([[.1, -.2], [-.1, .2]]),
                  np.array([[.1], [-.1]]), [.1, .2], extra, 5.)


Z = np.array([.2, -.3])
C = np.array([.5])


class RenewalTests(unittest.TestCase):
    def test_reactivation_edges_and_ages(self):
        i, y, u, r = transitions([1, 1, 0, 0, 1, 1])
        np.testing.assert_array_equal(i, [1, 1, 0, 0, 1])
        np.testing.assert_array_equal(y, [0, 1, 0, 1, 0])
        np.testing.assert_array_equal(r, [1, 2, 1, 2, 1])
        np.testing.assert_array_equal(u, [.25, .5, .75, 1., 1.25])

    def test_no_appended_exit(self):
        h = hazard(beta=(0., 0.), extra=(0., 0.))
        i, y, u, r = transitions([1, 1, 1, 1])
        ell = h.logits(5., Z, C, i, u, r)
        expected = sum(-math.log1p(math.exp(float(t))) for t in ell)
        self.assertAlmostEqual(float(log_likelihood(5., h, Z, C, [1] * 4)), expected)
        self.assertEqual(len(y), 3)
        np.testing.assert_array_equal(y, [0, 0, 0])

    def test_first_cell_only_likelihood_one(self):
        self.assertEqual(float(log_likelihood(5., hazard(), Z, C, [1])), 0.)

    def test_prefix_invariant_to_later_states(self):
        a = [1, 1, 0, 1, 0, 0, 0]
        b = [1, 1, 0, 1, 1, 1, 1]
        np.testing.assert_array_equal(log_likelihood([4., 5., 6.], hazard(), Z, C, a, 4),
                                      log_likelihood([4., 5., 6.], hazard(), Z, C, b, 4))

    def test_disjoint_extensions_not_overlapping_posteriors(self):
        b = [1, 1, 0, 0, 1, 1, 0, 1]
        h = hazard()
        ll4 = log_likelihood(5., h, Z, C, b, 4)
        ll8 = log_likelihood(5., h, Z, C, b)
        i, y, u, r = transitions(b)
        e = h.logits(5., Z, C, i[3:], u[3:], r[3:])
        extension = -np.logaddexp(0., np.where(y[3:] == 1, -e, e)).sum()
        self.assertAlmostEqual(float(ll8), float(ll4 + extension))

    def test_h_age_independence(self):
        h = hazard("H")
        a = h.logits(5., Z, C, np.array([0, 1]), [.5, .5], [1, 2])
        b = h.logits(5., Z, C, np.array([0, 1]), [.5, .5], [17, 20])
        np.testing.assert_array_equal(a, b)

    def test_c_age_dependence(self):
        h = hazard()
        a = h.logits(5., Z, C, np.array([0, 1]), [.5, .5], [1, 2])
        b = h.logits(5., Z, C, np.array([0, 1]), [.5, .5], [17, 20])
        np.testing.assert_allclose(b - a, h.extra * (np.log1p([17, 20]) - np.log1p([1, 2])))

    def test_h_extra_parameters_are_effective(self):
        a = hazard("H", extra=(0., 0.))
        b = hazard("H", extra=(.5, -.7))
        ea = a.logits(5., Z, C, np.array([0, 1]), [.5, .5], [1, 1])
        eb = b.logits(5., Z, C, np.array([0, 1]), [.5, .5], [1, 1])
        np.testing.assert_allclose(eb - ea, [.5 * Z[0] * Z[1], -.7 * Z[0] * C[0]])
        self.assertEqual(a.parameter_count, hazard("C").parameter_count)

    def test_shared_pi_zero_extra_h_c_equal(self):
        pi = mixture()
        a = gauss_hermite(pi, hazard("C", extra=(0, 0)), Z, C, [1, 0, 1], 7., 64)
        b = gauss_hermite(pi, hazard("H", extra=(0, 0)), Z, C, [1, 0, 1], 7., 64)
        self.assertEqual(a, b)

    def test_beta_zero_returns_base_after_normalization(self):
        pi = mixture()
        result = checked_inference(pi, hazard(beta=(0., 0.)), Z, C, [1, 0, 0, 1], 8.)
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["gh64"].mean, float(pi.weights @ pi.means), places=12)
        self.assertAlmostEqual(result["gh64"].nll, -float(pi.logpdf(8.)), places=12)

    def test_empty_evidence_returns_base(self):
        pi = mixture()
        result = checked_inference(pi, hazard(), Z, C, [0], 6.)
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["gh64"].log_normalizer, 0., places=12)

    def test_joint_loss_is_not_posterior_nll(self):
        pi = mixture()
        h = hazard()
        b = [1, 1, 0, 0, 1]
        loss = joint_loss(7., pi, h, Z, C, b)
        result = gauss_hermite(pi, h, Z, C, b, 7., 128)
        self.assertAlmostEqual(loss["joint_nll"], loss["base_nll"] + loss["sequence_nll"])
        self.assertAlmostEqual(result.nll, loss["joint_nll"] + result.log_normalizer)
        self.assertGreater(abs(result.log_normalizer), .1)

    def test_moderate_inference_agrees_independent(self):
        result = checked_inference(mixture(), hazard(beta=(.8, -.7)), Z, C,
                                   [1, 1, 0, 0, 1, 1, 1, 0], 7.5)
        self.assertTrue(result["accepted"], result["errors"])
        self.assertTrue(all(e <= 1e-4 for e in result["errors"].values()))

    def test_far_label_tail_stays_finite(self):
        result = checked_inference(mixture(), hazard(), Z, C, [1, 0, 1], 1000.)
        self.assertTrue(result["accepted"])
        self.assertTrue(math.isfinite(result["gh64"].nll))
        self.assertGreater(result["gh64"].nll, 1e6)

    def test_sigma_floor_regime(self):
        result = checked_inference(mixture(.05), hazard(beta=(1., -1.)), Z, C, [1] * 20, 8.)
        self.assertTrue(result["accepted"], result["errors"])

    def test_broad_sigma_beta_zero_regime(self):
        pi = mixture(1000.)
        result = checked_inference(pi, hazard(beta=(0., 0.)), Z, C, [1, 0, 1], 8.)
        self.assertTrue(result["accepted"], result["errors"])

    def test_steep_broad_quadrature_failure_retained(self):
        # Smooth hazards can still be too sharply varying for fixed GH orders.
        result = checked_inference(mixture(10.), hazard(beta=(50., -50.), extra=(0, 0)),
                                   Z, C, [0, 1, 1, 1], 7.)
        self.assertFalse(result["accepted"])
        self.assertGreater(max(result["errors"].values()), 1e-4)

    def test_gaussian_mean_not_support_truncated(self):
        pi = Mixture([.2] * 5, [-50., -20., 10., 40., 100.], [1.] * 5)
        result = checked_inference(pi, hazard(beta=(0, 0)), Z, C, [0, 1], 100.)
        self.assertTrue(result["accepted"])
        self.assertAlmostEqual(result["gh64"].mean, 16., places=10)

    def test_raw_head_and_readonly_owned_arrays(self):
        raw = np.zeros(15)
        raw[5:10] = np.arange(5)
        pi = Mixture.from_raw(raw)
        raw[:] = 99.
        np.testing.assert_allclose(pi.weights, [.2] * 5)
        self.assertGreater(pi.sigmas.min(), .05)
        self.assertFalse(pi.means.flags.writeable)

    def test_zero_weight_component(self):
        pi = Mixture([1., 0., 0., 0., 0.], [5.] * 5, [.5] * 5)
        result = checked_inference(pi, hazard(), Z, C, [1, 0, 1], 6.)
        self.assertTrue(result["accepted"])

    def test_log_likelihood_never_positive(self):
        values = log_likelihood(np.linspace(-100., 100., 51), hazard(), Z, C, [1, 0] * 10)
        self.assertTrue(np.all(values <= 0))

    def test_input_validation(self):
        for invalid in ([], [2], [1.] , [0] * 21, [[0, 1]]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                transitions(invalid)
        with self.assertRaises(ValueError):
            transitions([1, 0], 3)
        with self.assertRaises(ValueError):
            Mixture([.1] * 5, [5.] * 5, [.2] * 5)
        with self.assertRaises(ValueError):
            Mixture([.2] * 5, [5.] * 5, [.049] * 5)

    def test_numerical_overflow_is_failure(self):
        with self.assertRaises(NumericalFailure):
            mixture().logpdf(1e308)
        with self.assertRaises(ValueError):
            gauss_hermite(mixture(), hazard(), Z, C, [1], 6., 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)

import unittest
import numpy as np
from features import describe, prefix51, masks, FEATURE_NAMES, InvalidObservation


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.x = np.random.default_rng(20261009).normal(size=(3, 700))*1000
        self.g = np.array([1e8, 2e8, 4e8])
        self.static = np.zeros(34)

    def f(self, x=None, t=1, gains=None, units=None):
        return describe(self.x if x is None else x, self.g if gains is None else gains,
                        ['m/s']*3 if units is None else units, self.static, t)

    def test_schema_and_masks(self):
        self.assertEqual(len(FEATURE_NAMES), 127)
        self.assertEqual(len(set(FEATURE_NAMES)), 127)
        self.assertEqual({k: int(v.sum()) for k, v in masks().items()}, {'B': 85, 'D': 106, 'F': 127})
        self.assertTrue(all(v.shape == (127,) for v in masks().values()))

    def test_strict_suffix_invariance_features_and_validity(self):
        for t in (1, 3):
            reference = self.f(t=t)
            changed = self.x.copy()
            changed[:, 200+100*t:] = np.nan
            actual = self.f(changed, t=t)
            np.testing.assert_array_equal(reference[0], actual[0])
            self.assertEqual(reference[1], actual[1])
            with self.assertRaisesRegex(InvalidObservation, 'nonfinite'):
                self.f(changed, t=5)

    def test_native_digital_gain_invariance(self):
        factors = np.array([2., 8., .25])
        for t in (1, 3, 5):
            a = self.f(t=t)[0]
            b = self.f(self.x*factors[:, None], t=t, gains=self.g*factors)[0]
            np.testing.assert_array_equal(a[85:], b[85:])
            self.assertFalse(np.array_equal(a[:51], b[:51]))

    def test_identical_marginals_distinct_cross_components(self):
        # Sign reversal leaves all original marginal power/amplitude summaries
        # and marginal-noise descriptors unchanged, but changes cross structure.
        x = self.x.copy()
        x[1] *= -1
        for t in (1, 3, 5):
            a, b = self.f(t=t)[0], self.f(x, t=t)[0]
            np.testing.assert_array_equal(a[:106], b[:106])
            self.assertGreater(np.linalg.norm(a[106:]-b[106:]), .01)

    def test_constant_marginal_informative_control(self):
        # Constructed control only: the sign label changes channel dependence,
        # while all B/D inputs are exactly identical. No model is fitted.
        x = self.x.copy()
        x[1] = x[0]
        a = self.f(x)[0]
        x[1] *= -1
        b = self.f(x)[0]
        np.testing.assert_array_equal(a[:106], b[:106])
        self.assertGreater(a[109], .999999)
        self.assertLess(b[109], -.999999)

    def test_causal_null_unemitted_suffix(self):
        # Different hypothetical final targets/future traces cannot change an
        # identical observed prefix. No target argument exists in this API.
        a = self.x.copy()
        b = self.x.copy()
        b[:, 300:] *= 100
        np.testing.assert_array_equal(self.f(a)[0], self.f(b)[0])

    def test_noise_only_and_near_singular(self):
        x = self.x.copy()
        x[1:] = x[0]
        for t in (1, 3, 5):
            out, _ = self.f(x, t=t, gains=np.ones(3))
            self.assertTrue(np.isfinite(out).all())
            self.assertTrue((out[118:121] >= 0).all())
        self.assertTrue(np.isfinite(self.f()[0]).all())

    def test_isotropic_direction_degeneracy(self):
        time = np.arange(700)/100
        x = np.stack([np.sin(2*np.pi*f*time) for f in (2, 4, 6)])
        out, degenerate = self.f(x, gains=np.ones(3))
        self.assertTrue(degenerate)
        np.testing.assert_array_equal(out[-6:], 0)

    def test_band_fractions_and_scale(self):
        result, _ = self.f()
        np.testing.assert_allclose(result[91:106].reshape(3, 5).sum(1), 1, atol=1e-14)
        # Physical values are small: a counts-sized denominator floor would
        # break normalization and gain invariance in these noise fractions.
        small = self.f(gains=self.g*1e3)[0]
        np.testing.assert_allclose(small[91:106], result[91:106], atol=1e-14)

    def test_invalid_inputs(self):
        checks = [(self.x[:, :299], self.g, ['m/s']*3, 'short_segment'),
                  (self.x, [0, 1, 1], ['m/s']*3, 'invalid_gain'),
                  (self.x, self.g, ['m/s', 'm/s^2', 'm/s'], 'mixed_or_unknown_units'),
                  (np.zeros_like(self.x), self.g, ['m/s']*3, 'variance_floor')]
        for x, gain, units, reason in checks:
            with self.assertRaisesRegex(InvalidObservation, reason):
                self.f(x, gains=gain, units=units)
        changed = self.x.copy()
        changed[0, 100] = np.inf
        with self.assertRaisesRegex(InvalidObservation, 'nonfinite'):
            self.f(changed)

    def test_no_input_mutation(self):
        original = self.x.copy()
        for t in (1, 3, 5):
            self.f(t=t)
        np.testing.assert_array_equal(original, self.x)

    def test_constant_baseline_is_finite(self):
        self.assertTrue(np.isfinite(prefix51(np.zeros((3, 100)))).all())


if __name__ == '__main__':
    unittest.main()

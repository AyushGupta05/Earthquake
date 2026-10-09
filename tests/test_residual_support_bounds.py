import importlib.util
import itertools
from pathlib import Path
import unittest

import numpy as np

path = Path(__file__).resolve().parents[1] / 'research/2026-10-09/phase2/residual_support_bounds.py'
spec = importlib.util.spec_from_file_location('residual_support_bounds', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SupportBoundsTest(unittest.TestCase):
    def test_matches_all_box_vertices(self):
        rng = np.random.default_rng(5728)
        p = rng.dirichlet(np.ones(5), size=9)
        centers = np.array([-2., -.1, .4, 3., 6.])
        for bound in (0., .25, 2., 5.):
            values = []
            for signs in itertools.product([-1, 1], repeat=5):
                q = p * np.exp(bound * np.array(signs))
                q /= q.sum(1, keepdims=True)
                values.append(q @ centers)
            lower, upper = module.mean_bounds(p, centers, bound)
            np.testing.assert_allclose(lower, np.min(values, axis=0), atol=2e-14, rtol=0)
            np.testing.assert_allclose(upper, np.max(values, axis=0), atol=2e-14, rtol=0)

    def test_interior_samples_and_zero_support(self):
        rng = np.random.default_rng(182)
        p = np.array([[0., .7, .3, 0.], [0., 0., 1., 0.]])
        c = np.array([0., 1., 2., 10.])
        lo, hi = module.mean_bounds(p, c)
        self.assertEqual(lo[1], 2.)
        self.assertEqual(hi[1], 2.)
        self.assertLessEqual(hi[0], 2.)
        for _ in range(50):
            q = p * np.exp(rng.uniform(-5, 5, p.shape))
            q /= q.sum(1, keepdims=True)
            value = q @ c
            self.assertTrue(np.all(value >= lo - 1e-12))
            self.assertTrue(np.all(value <= hi + 1e-12))

    def test_hindsight_floor_and_no_tail(self):
        r = module.summarize([[1., 0.], [0., 1.]], [1., 4.], [2., 5.], ['a', 'b'])
        self.assertEqual(r['all_mean_error_floor'], 1.)
        self.assertEqual(r['m4']['mean_error_floor'], 1.)
        empty = module.summarize([[1., 0.]], [1., 4.], [2.], ['a'])
        self.assertIsNone(empty['m4']['mean_error_floor'])

    def test_reject_invalid_inputs(self):
        cases = [([[.4, .4]], [1, 2], 5), ([[np.nan, .5]], [1, 2], 5),
                 ([[-.1, 1.1]], [1, 2], 5), ([[.5, .5]], [2, 1], 5),
                 ([[.5, .5]], [1, np.inf], 5), ([[.5, .5]], [1, 2], -1),
                 ([[.5, .5]], [1, 2], np.nan)]
        for p, c, bound in cases:
            with self.assertRaises(ValueError):
                module.mean_bounds(p, c, bound)
        with self.assertRaises(ValueError):
            module.summarize([[.5, .5]], [1., 2.], [np.nan], ['a'])


if __name__ == '__main__':
    unittest.main()

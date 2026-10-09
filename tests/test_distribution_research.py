"""Independent checks of scientific scoring and event separation."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

path = Path(__file__).parents[1] / 'research/2026-10-09/distribution_experiment.py'
spec = importlib.util.spec_from_file_location('experiment', path)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class DistributionTests(unittest.TestCase):
    def test_crps_matches_independent_pairwise_definition(self):
        rng = np.random.default_rng(1)
        c = np.array([.1, 1.4, 3.2, 5.1])
        p = rng.dirichlet(np.ones(4), size=7)
        y = np.linspace(-1, 7, 7)
        distance = np.abs(c[:, None]-c[None, :])
        reference = (p*np.abs(c-y[:, None])).sum(1) - .5*np.einsum('ni,ij,nj->n', p, distance, p)
        np.testing.assert_allclose(e.crps(p,c,y), reference, atol=1e-12)

    def test_threshold_score_is_proper_for_a_known_population(self):
        c = np.array([2., 4., 6.])
        truth = np.array([.8, .15, .05])
        threshold_c = np.maximum(c,4.)
        correct = np.tile(truth,(3,1))
        distorted = np.tile(np.array([.3,.2,.5]),(3,1))
        self.assertLess(truth @ e.crps(correct, threshold_c, threshold_c),
                        truth @ e.crps(distorted, threshold_c, threshold_c))

    def test_event_weighting_not_station_count_weighting(self):
        w = e.event_weights(np.array(['a','a','a','b']))
        self.assertAlmostEqual(w[:3].sum(), .5)
        self.assertAlmostEqual(w[3], .5)

    def test_event_folds_keep_all_stations_together(self):
        ids = np.repeat(np.arange(30).astype(str),3)
        y = np.repeat(np.r_[np.full(10,4.2),np.full(20,2.)],3)
        fold = e.event_folds(y,ids)
        for event in np.unique(ids):
            self.assertEqual(len(np.unique(fold[ids==event])),1)
        for k in range(5):
            self.assertEqual(len(np.unique(ids[(fold==k)&(y>=4)])),2)

    def test_unconstrained_tail_improvement_rejected(self):
        y = np.r_[np.full(100,2.),4.5]
        ids = np.arange(len(y)).astype(str)
        raw = np.full(len(y),2.)
        self.assertEqual(e.safe_choice(y,ids,raw,{'always_large': np.full(len(y),4.5)}), 'raw_fallback')

    def test_zero_tail_mass_cannot_be_created_by_reweighting(self):
        p = np.array([[.7,.3,0.]])
        self.assertEqual(e.tilted(p,np.array([2.,3.,5.]),100.)[0,2],0.)


if __name__ == '__main__':
    unittest.main()

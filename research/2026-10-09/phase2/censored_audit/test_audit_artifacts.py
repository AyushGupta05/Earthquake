import unittest
import numpy as np
from audit_artifacts import bounded_calibration, check_probability, compared_metric_difference, discrete_crps, decisions_and_scores, reliability


class AuditTests(unittest.TestCase):
    def test_crps_matches_pairwise_definition_off_support(self):
        p = np.array([[.1,.2,.7],[.5,.5,0],[0,0,1],[.2,.3,.5]])
        c = np.array([.05,.15,.25]); y = np.array([-.2,.12,.4,.15])
        expected = (p*np.abs(c[None]-y[:,None])).sum(1)-.5*np.einsum('bi,bj,ij->b',p,p,np.abs(c[:,None]-c[None,:]))
        np.testing.assert_allclose(discrete_crps(p,c,y),expected,atol=1e-15)

    def test_collapsed_tail_support(self):
        p = np.array([[.2,.3,.5],[.5,.4,.1]])
        c = np.array([4.,4.,4.5]); y = np.array([4.,5.])
        expected = (p*np.abs(c[None]-y[:,None])).sum(1)-.5*np.einsum('bi,bj,ij->b',p,p,np.abs(c[:,None]-c[None,:]))
        np.testing.assert_allclose(discrete_crps(p,c,y),expected,atol=1e-15)

    def test_normalization_rejects_bad_array(self):
        p = np.ones((2,3,4))/4
        self.assertEqual(check_probability(p,2,4),0)
        p[0,0,0]=.3
        with self.assertRaises(ValueError):check_probability(p,2,4)

    def test_point_decisions_scores_and_event_weights(self):
        c=(np.arange(66)+.5)*.1; p=np.zeros((3,66)); p[:,10]=1
        y=np.array([1.05,1.55,4.05]);ids=np.array(['a','a','b'])
        dec,s=decisions_and_scores(p,c,y,ids)
        np.testing.assert_allclose(dec['mean'],1.05)
        self.assertAlmostEqual(s['mean']['mae'],3.5/3)
        self.assertAlmostEqual(s['mean']['event_macro_mae'],(0.25+3)/2)
        self.assertAlmostEqual(s['mean']['m4_mae'],3)
        self.assertAlmostEqual(s['mean']['crps'],3.5/3)
        self.assertAlmostEqual(s['mean']['cvar95'],3)

    def test_reliability_includes_endpoint_one(self):
        r=reliability(np.array([0.,.2,.8,1.]),np.array([0.,0.,1.,1.]))
        self.assertEqual(sum(b['records'] for b in r['bins']),4)
        self.assertAlmostEqual(r['brier'],.02)
        self.assertAlmostEqual(r['ece10_descriptive'],.1)

    def test_diagnostic_roundoff_is_recorded_and_material_errors_rejected(self):
        p, info = bounded_calibration(np.array([-1e-16, .5, 1+2e-15]))
        np.testing.assert_array_equal(p, [0., .5, 1.])
        self.assertEqual(info['endpoint_roundoff_count'], 2)
        self.assertGreater(info['raw_maximum'], 1.)
        for values in ([np.nan], [-1e-9], [1+1e-9]):
            with self.assertRaises(ValueError):
                bounded_calibration(np.array(values))

    def test_metric_comparison_rejects_nonfinite_values(self):
        self.assertAlmostEqual(compared_metric_difference(.2,.3),.1)
        for actual, reported in [(1,np.nan),(np.nan,1),(1,np.inf),(np.inf,1)]:
            with self.assertRaises(ValueError):
                compared_metric_difference(actual,reported)


if __name__ == '__main__':unittest.main()

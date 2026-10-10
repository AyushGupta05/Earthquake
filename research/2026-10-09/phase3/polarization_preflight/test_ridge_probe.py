import copy
import unittest
import numpy as np
from features import masks
from ridge_probe import (fit,predict,ensemble_predictions,normalization,random_map,transform_target,inverse_target,
                         score,paired_bootstrap,gate,weighted_cvar)


class RidgeTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(11)
        self.x = rng.normal(size=(120,127))
        self.y = np.column_stack((4.5+.1*self.x[:,0],10+abs(self.x[:,1]),3+abs(self.x[:,2])))
        self.w = np.linspace(1,2,len(self.x))

    def test_identical_zero_added_slots_and_matched_draws(self):
        x = self.x.copy()
        x[:,85:] = 0
        states = [fit(x,self.y,self.w,mask,20261009) for mask in masks().values()]
        predictions = [predict(x,state)[0] for state in states]
        for i in (1,2):
            np.testing.assert_array_equal(predictions[0],predictions[i])
            np.testing.assert_array_equal(states[0]['random_weight'],states[i]['random_weight'])
            self.assertEqual(int(states[i]['fitted_coefficient_count']),768)

    def test_fit_only_normalization_and_no_mutation(self):
        state = fit(self.x,self.y,self.w,masks()['F'],20261009)
        expected = copy.deepcopy(state)
        predict(self.x*100+50,state)
        for key in state:
            np.testing.assert_array_equal(state[key],expected[key])
        np.testing.assert_allclose(state['input_mean'],np.average(self.x,axis=0,weights=self.w),atol=1e-14)

    def test_weight_scaling_same_solution(self):
        first = fit(self.x,self.y,self.w,masks()['D'],20261009)
        second = fit(self.x,self.y,self.w*100,masks()['D'],20261009)
        np.testing.assert_allclose(predict(self.x,first)[0],predict(self.x,second)[0],atol=1e-10,rtol=1e-10)

    def test_target_transform_exact_and_invalid_not_clipped(self):
        target = np.array([[4.,10.,2.],[5.,1.,0.]])
        np.testing.assert_allclose(inverse_target(transform_target(target)),target)
        predicted = inverse_target(np.array([[4.,-1.,-.5]]))
        self.assertLess(predicted[0,2],0)
        self.assertAlmostEqual(predicted[0,1],.1)
        result = score(predicted,np.array([[4.,2.,0.]]),np.ones(1),np.array(['event']))
        self.assertEqual(result['physical_invalid_predictions']['negative_depth'],1)
        with self.assertRaises((ValueError,FloatingPointError)):
            inverse_target(np.array([[4.,1000.,0.]]))

    def test_ensemble_log_reporting_retains_finite_underflowed_depths(self):
        logs = np.array([[4.,-400.,-40.],[5.,1.,-50.]])
        raw = inverse_target(logs)
        self.assertEqual(raw[0,2],-1.)
        mean,transformed = ensemble_predictions([raw,raw],[logs,logs],np.ones(2,dtype=bool))
        np.testing.assert_array_equal(mean,raw)
        np.testing.assert_allclose(transformed,logs,atol=1e-12)
        result = score(mean,np.array([[4.,10.,2.],[5.,10.,3.]]),np.ones(2),np.array(['a','b']),transformed)
        self.assertEqual(result['physical_invalid_predictions']['negative_depth'],2)
        self.assertEqual(result['physical_invalid_predictions']['nonpositive_distance'],1)

    def test_weighted_tail_metrics_and_event_macro(self):
        truth = np.array([[4.,10.,2.],[4.,10.,2.],[5.,10.,2.]])
        prediction = truth.copy(); prediction[:,0] += [0,2,4]
        result = score(prediction,truth,np.array([1.,1.,2.]),np.array(['a','a','b']))
        self.assertEqual(result['targets']['magnitude']['weighted_mae'],2.5)
        self.assertEqual(result['targets']['magnitude']['event_macro_mae'],2.5)
        self.assertEqual(result['magnitude_medae'],2)
        self.assertEqual(result['magnitude_cvar95'],4)
        self.assertEqual(result['tail']['4']['events'],2)
        self.assertEqual(result['tail']['5']['events'],1)
        self.assertAlmostEqual(weighted_cvar(np.array([10.,0.]),np.array([1.,99.])),2.)

    def test_paired_bootstrap_identity_and_determinism(self):
        event = np.array([str(i//3) for i in range(len(self.y))])
        first = paired_bootstrap(self.y,self.y,self.y,self.w,event)
        second = paired_bootstrap(self.y,self.y,self.y,self.w,event)
        self.assertEqual(first,second)
        self.assertEqual(first['weighted_magnitude_mae_ci95'],[0.,0.])
        self.assertEqual(first['m4_event_macro_mae_ci95'],[0.,0.])

    def test_invalid_inputs_and_seed_determinism(self):
        for bad in (np.zeros(120),np.ones(119),np.full(120,np.nan)):
            with self.assertRaises(ValueError):
                fit(self.x,self.y,bad,masks()['B'],1)
        with self.assertRaises(ValueError):
            fit(self.x[:,:85],self.y,self.w,masks()['B'],1)
        first,second = random_map(1),random_map(1)
        np.testing.assert_array_equal(first[0],second[0])
        self.assertFalse(np.array_equal(first[0],random_map(2)[0]))

    def test_gate_requires_all_horizons_and_same_geometry_target(self):
        base = {'targets':{'magnitude':{'weighted_mae':.3},'distance_km':{'event_macro_mae':10.},'depth_km':{'event_macro_mae':10.}},
                'magnitude_medae':.2,'tail':{'4':{'events':30,'event_macro_mae':.5}}}
        rows = []
        for t in (1,3,5):
            for subset in ('eval_seen','eval_held'):
                f = copy.deepcopy(base)
                f['tail']['4']['event_macro_mae'] = .4
                f['targets']['distance_km']['event_macro_mae'] = 9
                rows.append({'seconds':t,'subset':subset,'F':f,'D':copy.deepcopy(base),
                             'bootstrap':{'weighted_magnitude_mae_ci95':[-.01,0.],'m4_event_macro_mae_ci95':[-.2,-.01]},
                             'seed_m4_event_macro_deltas':[-.1,-.1],'valid_fraction':1.})
        self.assertTrue(gate(rows)['pass'])
        self.assertFalse(gate(rows[:-1])['pass'])
        rows[-1]['F']['targets']['distance_km']['event_macro_mae'] = 10
        rows[-1]['F']['targets']['depth_km']['event_macro_mae'] = 9
        self.assertFalse(gate(rows)['pass'])
        rows[-1]['F']['tail']['4']['events'] = 19
        self.assertEqual(gate(rows)['status'],'inconclusive_tail_sample')


if __name__ == '__main__':
    unittest.main()

import unittest
import numpy as np
from audit import point_metrics, close_metrics, array_sha


class AuditTests(unittest.TestCase):
    def test_hand_calculated_event_and_tail(self):
        result=point_metrics([2,2,5],[1,3,3],['a','a','b'])
        self.assertAlmostEqual(result['mae'],4/3)
        self.assertEqual(result['medae'],1)
        self.assertEqual(result['event_macro_mae'],1.5)
        self.assertEqual(result['m4_event_macro_mae'],2)
        self.assertEqual(result['m5_bias'],-2)
        self.assertEqual(result['cvar95'],2)
        self.assertIsNone(result['m6_mae'])

    def test_false_alert_denominator(self):
        result=point_metrics([2,3,4,5],[4,2,5,2],['a','b','c','d'])
        self.assertEqual(result['fp4'],1)
        self.assertEqual(result['tp4'],1)
        self.assertEqual(result['fpr4'],.5)

    def test_no_nontail_is_explicit(self):
        result=point_metrics([5],[5],['a'])
        self.assertIsNone(result['fpr4'])
        self.assertEqual(result['mae'],0)

    def test_rejects_bad_data(self):
        for y,p,ids in [([],[],[]),([1],[float('nan')],['a']),([1,2],[1,2],['a','a']),([1],[2,3],['a'])]:
            with self.assertRaises(ValueError):point_metrics(y,p,ids)

    def test_metric_validation(self):
        self.assertLess(close_metrics({'mae':1.,'m6_mae':None},{'mae':1+1e-12,'m6_mae':None}),1e-10)
        for saved in [{'mae':float('nan')},{'mae':None},{'mae':1.1}]:
            with self.assertRaises(ValueError):close_metrics({'mae':1.},saved)
        with self.assertRaises(ValueError):close_metrics({'m6_mae':None},{'m6_mae':0})

    def test_hash_binds_dtype_and_shape(self):
        a=np.arange(6,dtype=np.float32)
        self.assertNotEqual(array_sha(a),array_sha(a.reshape(2,3)))
        self.assertNotEqual(array_sha(a),array_sha(a.astype(np.float64)))
        self.assertEqual(array_sha(a),array_sha(a.copy()))


if __name__=='__main__':unittest.main()

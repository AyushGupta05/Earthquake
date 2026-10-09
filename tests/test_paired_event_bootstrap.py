from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research/2026-10-09/phase2'))
from paired_event_bootstrap import ordered_metrics,bootstrap


class BootstrapTests(unittest.TestCase):
    def test_weighted_order_statistics_match_explicit_replication(self):
        e=np.array([0.,1.,2.,4.,6.,9.])
        for count in [np.array([0,1,2,0,9,1]),np.array([3,0,1,8,2,0])]:
            full=np.repeat(e,count)
            med,cvar=ordered_metrics(e,count)
            self.assertEqual(med,np.median(full))
            self.assertEqual(cvar,np.sort(full)[-int(np.ceil(len(full)*.05)):].mean())

    def test_identical_prediction_intervals_are_zero_with_unequal_clusters(self):
        y=np.array([1.,1.,1.,2.,4.,4.])
        ids=np.array(['a','a','a','b','c','c'])
        pred=y+np.array([1.,2.,3.,.5,-1.,1.])
        result=bootstrap(y,ids,pred,pred,replicates=20)
        for interval in result['paired_delta_intervals'].values():
            self.assertEqual(interval['lower_95'],0.)
            self.assertEqual(interval['upper_95'],0.)


if __name__=='__main__':
    unittest.main()

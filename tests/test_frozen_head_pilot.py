import sys
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
import torch
sys.path.insert(0,str(Path(__file__).parents[1]/'research/2026-10-09'))
from frozen_head_pilot import ordinal_score, choose_rows


class HeadPilotTests(unittest.TestCase):
    def test_checkpoint_rejects_raw_or_mixed_preprocessing(self):
        from audit_and_export import require_checkpoint_preprocessing
        require_checkpoint_preprocessing({'training_global_standardization'})
        for invalid in [{'raw_counts'}, {'raw_counts', 'training_global_standardization'}, set()]:
            with self.assertRaises(ValueError):
                require_checkpoint_preprocessing(invalid)

    def test_cdf_loss_gradient(self):
        torch.manual_seed(5)
        x=torch.randn(2,42,dtype=torch.double,requires_grad=True)
        y=torch.tensor([2,41])
        self.assertTrue(torch.autograd.gradcheck(lambda z: ordinal_score(z,y,10.).mean(),(x,)))

    def test_positive_threshold_weights_keep_true_distribution_optimal(self):
        truth=torch.full((42,),.001,dtype=torch.double)
        truth[2]=.7
        truth[41]=.26
        truth/=truth.sum()
        labels=torch.arange(42)
        correct=truth.log().repeat(42,1)
        altered=truth.clone()
        altered[2]-=.2
        altered[41]+=.2
        correct_risk=(ordinal_score(correct,labels,10.)*truth).sum()
        altered_risk=(ordinal_score(altered.log().repeat(42,1),labels,10.)*truth).sum()
        self.assertLess(correct_risk.item(),altered_risk.item())

    def test_station_sample_preserves_every_event(self):
        metadata=pd.DataFrame({'source_id':['a']*10+['b']*2+['c']})
        rows=choose_rows(metadata)
        self.assertEqual(len(rows),7)
        self.assertEqual(metadata.iloc[rows].source_id.value_counts().to_dict(),{'a':4,'b':2,'c':1})
        np.testing.assert_array_equal(rows,choose_rows(metadata))


if __name__=='__main__':
    unittest.main()

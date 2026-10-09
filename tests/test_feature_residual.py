import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
import torch

path=Path(__file__).parents[1]/'research/2026-10-09/phase2/feature_residual.py'
spec=importlib.util.spec_from_file_location('feature_residual',path)
f=importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class FeatureResidualTests(unittest.TestCase):
    def test_zero_correction_initialization(self):
        model=f.ResidualDistribution(7).eval()
        original=torch.randn(10,66)
        torch.testing.assert_close(model(torch.randn(10,7),original),original)

    def test_features_finite_for_silence_and_all_durations(self):
        for n in [100,300,500]:
            for x in [torch.zeros(2,3,n),torch.randn(2,3,n)]:
                self.assertEqual(f.prefix_features(x).shape,(2,51))
                self.assertTrue(torch.isfinite(f.prefix_features(x)).all())

    def test_no_unobserved_suffix_can_change_prefix_features(self):
        a=torch.randn(2,3,500)
        b=a.clone()
        b[:,:,100:]=10000
        torch.testing.assert_close(f.prefix_features(a[:,:,:100]),f.prefix_features(b[:,:,:100]))

    def test_population_weights_recover_recording_counts(self):
        meta=pd.DataFrame({'source_id':['a']*9+['b']*3})
        rows=np.array([0,1,2,9,10,11])
        w=f.population_weights(meta,rows)
        self.assertAlmostEqual(w[:3].sum()/w[3:].sum(),3)

    def test_normalizer_does_not_use_validation(self):
        data={'train_logits':np.random.default_rng(1).normal(size=(20,66)).astype('float32'),
              'val_logits':np.zeros((2,66),dtype='float32')}
        _,a,b=f.inputs(data,'posterior')
        data['val_logits'][:]=1e9
        _,aa,bb=f.inputs(data,'posterior')
        np.testing.assert_array_equal(a,aa)
        np.testing.assert_array_equal(b,bb)


if __name__=='__main__':
    unittest.main()

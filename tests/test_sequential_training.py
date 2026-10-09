import sys
from pathlib import Path
import unittest
import torch
sys.path.insert(0,str(Path(__file__).parents[1]/'research/2026-10-09/phase2'))
from train_sequential import conditional_drift, supervised_loss

class SequentialTrainingTests(unittest.TestCase):
    def test_zero_drift_for_identical_distributions(self):
        x=torch.randn(16,66)
        self.assertAlmostEqual(conditional_drift({1:x,3:x+4,5:x-2},torch.ones(16)).item(),0,places=10)

    def test_systematic_drift_is_penalized(self):
        a=torch.zeros(32,66)
        b=a.clone();b[:,:20]=3
        self.assertGreater(conditional_drift({1:a,3:b,5:b},torch.ones(32)).item(),0)

    def test_finite_drift_and_supervised_gradients(self):
        outputs={t:torch.randn(16,66,requires_grad=True) for t in [1,3,5]}
        y=torch.linspace(0,6.5,16)
        for objective in ['weighted','proper']:
            loss=supervised_loss(outputs,y,torch.ones(16),torch.arange(66)*.1+.05,objective)
            loss=loss+conditional_drift(outputs,torch.ones(16))
            loss.backward(retain_graph=True)
            for x in outputs.values():
                self.assertTrue(torch.isfinite(x.grad).all())

if __name__=='__main__':unittest.main()

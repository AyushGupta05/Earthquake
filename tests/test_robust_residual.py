from pathlib import Path
import sys
import unittest

import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research/2026-10-09/phase2'))
from robust_residual import cvar_surrogate


class CVaRTests(unittest.TestCase):
    def test_matches_worst_quartile_at_optimal_threshold(self):
        e=torch.arange(1.,9.)
        for eta in [6.,6.5,7.]:
            self.assertAlmostEqual(cvar_surrogate(e,torch.ones(8),torch.tensor(eta),.75).item(),7.5)

    def test_population_weights_recover_duplicated_examples(self):
        e=torch.tensor([1.,5.,9.])
        w=torch.tensor([2.,1.,3.])*.5
        full=torch.tensor([1.,1.,5.,9.,9.,9.])
        eta=torch.tensor(5.)
        self.assertAlmostEqual(cvar_surrogate(e,w,eta,.5).item(),
                               cvar_surrogate(full,torch.ones(6),eta,.5).item())

    def test_only_errors_above_threshold_receive_cvar_gradient(self):
        e=torch.tensor([.2,.5,2.],requires_grad=True)
        eta=torch.tensor(1.,requires_grad=True)
        cvar_surrogate(e,torch.ones(3),eta).backward()
        self.assertEqual(e.grad[:2].abs().sum().item(),0.)
        self.assertGreater(e.grad[2].item(),0.)
        self.assertTrue(torch.isfinite(eta.grad).item())


if __name__=='__main__':
    unittest.main()

"""Invented CPU forward/backward only, not an actual pilot fit."""
import math
import unittest
import numpy as np
import density
try:
    import torch
    from model import PilotNet,mixture_nll
except ImportError:
    torch=None


@unittest.skipIf(torch is None,"Torch absent in local declared runtime; Linux invented lane required")
class ModelTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1);torch.use_deterministic_algorithms(True);torch.manual_seed(12)
        self.net=PilotNet();self.net.initialize(5.,1.)
        self.wave=torch.randn(2,3,11);self.amplitude=torch.randn(2,4);self.context=torch.randn(2,29)
        self.mask=torch.ones(2,11,dtype=torch.bool);self.mask[0,7:]=False

    def test_architecture_and_normalized_proper_output(self):
        self.assertEqual([(c.in_channels,c.out_channels,c.kernel_size) for c in self.net.convs],[(3,8,(9,)),(8,16,(5,)),(16,16,(5,))])
        p,m,s=self.net(self.wave,self.amplitude,self.context,self.mask)
        self.assertEqual(tuple(p.shape),(2,5));torch.testing.assert_close(p.sum(1),torch.ones(2));self.assertTrue(torch.all(s>=.05))
        self.assertEqual((self.net.hidden.in_features,self.net.head.out_features),(65,15))

    def test_padding_invariance_even_nan_future(self):
        with torch.no_grad():self.net.head.weight.normal_()
        a=self.net(self.wave,self.amplitude,self.context,self.mask)
        changed=self.wave.clone();changed[0,:,7:]=float("nan")
        b=self.net(changed,self.amplitude,self.context,self.mask)
        for x,y in zip(a,b):torch.testing.assert_close(x,y)
        # Appending masked positions changes neither convolutions nor valid pooling.
        longer=torch.cat((self.wave,torch.full((2,3,9),1e9)),dim=2);mask=torch.cat((self.mask,torch.zeros(2,9,dtype=torch.bool)),dim=1)
        c=self.net(longer,self.amplitude,self.context,mask)
        for x,y in zip(a,c):torch.testing.assert_close(x,y)

    def test_metadata_only_and_matched_seed_initialization(self):
        with torch.no_grad():self.net.head.weight.normal_()
        a=self.net(self.wave,self.amplitude,self.context,self.mask,metadata_only=True)
        b=self.net(self.wave*100,self.amplitude*100,self.context,self.mask,metadata_only=True)
        for x,y in zip(a,b):torch.testing.assert_close(x,y)
        states=[]
        for arm in ("W","M","P"):
            torch.manual_seed(20261012);n=PilotNet();n.initialize(5.,.7);states.append(n.state_dict())
        for k in states[0]:torch.testing.assert_close(states[0][k],states[1][k]);torch.testing.assert_close(states[0][k],states[2][k])

    def test_stable_log_mixture_and_scalar_score_replay_backward(self):
        y=torch.tensor([4.,6.]);logp,m,s=self.net(self.wave,self.amplitude,self.context,self.mask,return_log=True)
        losses=mixture_nll(y,logp,m,s,log_input=True)
        for i in range(2):
            reference=density.nll(float(y[i]),logp[i].exp().detach().tolist(),m[i].detach().tolist(),s[i].detach().tolist())
            self.assertAlmostEqual(float(losses[i].detach()),reference,places=5)
        losses.mean().backward();self.assertTrue(all(p.grad is None or torch.isfinite(p.grad).all() for p in self.net.parameters()))
        logits=torch.tensor([[1000.,-1000.,-1000.,-1000.,-1000.]],requires_grad=True)
        loss=mixture_nll(torch.tensor([100.]),torch.log_softmax(logits,-1),torch.zeros(1,5),torch.ones(1,5)*.05,log_input=True)
        loss.sum().backward();self.assertTrue(torch.isfinite(loss).all());self.assertTrue(torch.isfinite(logits.grad).all())

    def test_empty_mask_rejected(self):
        with self.assertRaises(ValueError):self.net(self.wave,self.amplitude,self.context,torch.zeros_like(self.mask))

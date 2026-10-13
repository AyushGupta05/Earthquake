"""Structural calendar-curvature falsifier; invented observations/parameters only."""
import unittest
import numpy as np
import torch
import numerical_core as core
import models
import pilot


def hazard(arm):
    return core.Hazard(arm,[-.3,.2],[.3,-.2],np.array([[.1,-.2],[-.2,.1]]),np.array([[.2],[-.1]]),[.1,.2],[.4,-.2],5.)


class TimeControlTests(unittest.TestCase):
    def test_exact_c_t_initial_uninterrupted_logits_likelihood_and_posterior(self):
        z,c=[.2,.4],[.3]
        mixture=core.Mixture([.2]*5,[4.,4.5,5.,5.5,6.],[.7]*5)
        for state in (0,1):
            states=[state]*20;idx,y,u,r=core.transitions(states)
            np.testing.assert_array_equal(r,4*u)
            np.testing.assert_array_equal(hazard('C').logits([4.,6.],z,c,idx,u,r),hazard('T').logits([4.,6.],z,c,idx,u,r))
            self.assertEqual(float(core.log_likelihood(6.,hazard('C'),z,c,states)),float(core.log_likelihood(6.,hazard('T'),z,c,states)))
            a=core.checked_inference(mixture,hazard('C'),z,c,states,6.);b=core.checked_inference(mixture,hazard('T'),z,c,states,6.)
            self.assertTrue(a['accepted']);self.assertEqual(a,b)
    def test_reset_changes_c_vs_t_without_appending_exit(self):
        states=[1,1,0,0,1,1];idx,y,u,r=core.transitions(states)
        self.assertFalse(np.array_equal(r,4*u));self.assertEqual(len(y),len(states)-1)
        a=hazard('C').logits(6.,[.2,.4],[.3],idx,u,r);b=hazard('T').logits(6.,[.2,.4],[.3],idx,u,r)
        np.testing.assert_array_equal(a[:2],b[:2]);self.assertFalse(np.array_equal(a[2:],b[2:]))
        mixture=core.Mixture([.2]*5,[4.,4.5,5.,5.5,6.],[.7]*5)
        ca=core.checked_inference(mixture,hazard('C'),[.2,.4],[.3],states,6.);ta=core.checked_inference(mixture,hazard('T'),[.2,.4],[.3],states,6.)
        self.assertTrue(ca['accepted'] and ta['accepted']);self.assertNotEqual(ca['gh64'].mean,ta['gh64'].mean)
    def test_t_age_independent_time_curved_h_operator_unchanged(self):
        h=hazard('T')
        a=h.logits(5.,[.2,.4],[.3],np.array([0,1]),[.5,.5],[1,2]);b=h.logits(5.,[.2,.4],[.3],np.array([0,1]),[.5,.5],[17,20])
        np.testing.assert_array_equal(a,b)
        self.assertFalse(np.array_equal(a,h.logits(5.,[.2,.4],[.3],np.array([0,1]),[.75,.75],[1,2])))
        initial=hazard('H').logits(5.,[.2,.4],[.3],np.array([0,1]),[.5,.5],[1,2])
        np.testing.assert_array_equal(initial,hazard('H').logits(5.,[.2,.4],[.3],np.array([0,1]),[.5,.5],[17,20]))
    def test_torch_c_t_exact_initial_run_then_reset_difference_and_gradients(self):
        torch.manual_seed(32);c=models.Net('C',5.).double();t=models.Net('T',5.).double()
        c.hazards.beta.data[:]=torch.tensor([.3,-.2],dtype=torch.float64);c.hazards.extra.data[:]=torch.tensor([.4,-.2],dtype=torch.float64);t.load_state_dict(c.state_dict())
        wave=torch.randn(1,3,19,dtype=torch.float64);amp=torch.randn(1,4,dtype=torch.float64);ctx=torch.randn(1,35,dtype=torch.float64);wm=torch.ones(1,19,dtype=torch.bool)
        raw,z=c.initial(wave,amp,ctx,wm);traw,tz=t.initial(wave,amp,ctx,wm);self.assertTrue(torch.equal(raw,traw) and torch.equal(z,tz))
        states=torch.ones(1,20,dtype=torch.int64);mask=torch.ones(1,20,dtype=torch.bool)
        a=c.hazards.likelihood(torch.tensor([6.],dtype=torch.float64),z,ctx,states,mask);b=t.hazards.likelihood(torch.tensor([6.],dtype=torch.float64),tz,ctx,states,mask)
        self.assertTrue(torch.equal(a,b))
        ca=models.torch_gh(raw,c.hazards,z,ctx,states,mask,64);ta=models.torch_gh(traw,t.hazards,tz,ctx,states,mask,64)
        self.assertTrue(all(torch.equal(x,y) for x,y in zip(ca,ta)))
        states[:,2:4]=0
        a=c.hazards.likelihood(torch.tensor([6.],dtype=torch.float64),z,ctx,states,mask);b=t.hazards.likelihood(torch.tensor([6.],dtype=torch.float64),tz,ctx,states,mask)
        self.assertFalse(torch.equal(a,b));b.sum().backward();self.assertTrue(torch.isfinite(t.hazards.extra.grad).all());self.assertTrue(torch.any(t.hazards.extra.grad!=0))
    def test_frozen_ten_fit_order_and_strict_t_bulk_tail_guard(self):
        self.assertEqual(pilot.ARMS,('B','F','H','T','C'));self.assertEqual(models.parameter_counts(),{'B':5007,'F':5147,'H':5125,'T':5125,'C':5125})
        fits=[]
        for seed in pilot.SEEDS:
            for arm in pilot.ARMS:
                m=dict(tail_mae_5_5=.4 if arm=='C' else .5,nll=.4 if arm=='C' else .5,crps=.4 if arm=='C' else .5,mae=.4,medae=.4,lower_mae=.4,lower_medae=.4,cvar95=.4,maximum=.4)
                fits.append(dict(seed=seed,arm=arm,status='complete',metrics={str(h):dict(m) for h in (1,3,5)}))
        self.assertTrue(pilot.advance(fits)['pass_all'])
        next(f for f in fits if f['arm']=='T' and f['seed']==20261013)['metrics']['1']['mae']=.39
        self.assertFalse(pilot.advance(fits)['pass_all'])


if __name__=='__main__':unittest.main()

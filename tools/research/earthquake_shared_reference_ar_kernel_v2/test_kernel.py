"""Invented observation laws and analytic/gradient identities, no real fits."""
import math
import time
import unittest
import numpy as np
import torch
import kernel as k
import reference as r
import inherited_kernel as old
import ast
from pathlib import Path

DT=torch.float64

def inputs(cells=4,rho=(.2,-.4,.8),noise=True):
    g=torch.Generator().manual_seed(1920)
    logw=torch.log_softmax(torch.tensor([[-.5,.2,.1,-.3,0.]],dtype=DT),1)
    mu=torch.tensor([[4.,4.4,4.8,5.2,5.6]],dtype=DT);sd=torch.tensor([[.6,.7,.8,.9,1.]],dtype=DT)
    coeff=torch.tensor([[.1,.15,.02,.01,rho[c],.4]for c in range(3)],dtype=DT,requires_grad=True)
    marks=torch.randn((cells,3),generator=g,dtype=DT)*.2+.3
    nu=torch.randn((1,12,3),generator=g,dtype=DT)*.1 if noise else torch.zeros((1,12,3),dtype=DT)
    return (logw,mu,sd),(marks,),coeff,nu,torch.tensor([5.],dtype=DT)

def run(v,mode='L',h=1,offset=0):return k.marked_nll(*v[:4],v[4],mode,4.8,(h,),(offset,),processing_begin=time.monotonic())
def arrays(v):return tuple(x.detach().numpy()[0].copy()for x in v[0])
def ref(v,mode='L',marks=None):
    state=r.start(arrays(v),v[3].numpy()[0].copy(),mode,processing_begin=time.monotonic());state=r.append(state,v[1][0].numpy().copy()if marks is None else marks,v[2].detach().numpy().copy(),4.8);return r.complete(state)

class Tests(unittest.TestCase):
    def assertposterior(self,x,y,atol=1e-10):
        for field in('nll','logz'):np.testing.assert_allclose(x[field].detach().numpy(),y[field].detach().numpy(),atol=atol,rtol=atol)
        np.testing.assert_allclose(x['mu'].detach().numpy(),y['mu'].detach().numpy(),atol=atol,rtol=atol)
    def test_loading_and_autograd(self):
        rho=torch.tensor([-.4,.2,1.],dtype=DT,requires_grad=True);d=k.reference_loading(rho,False,'L');d.sum().backward();self.assertEqual(d.tolist(),[1.4,.8,0.]);self.assertEqual(rho.grad.tolist(),[-1.,-1.,-1.])
    def test_rho_zero_equals_S(self):
        v=inputs(rho=(0.,0.,0.));self.assertposterior(run(v,'L'),run(v,'S'),1e-12)
    def test_zero_noise_equals_P(self):
        v=inputs(noise=False);x=run(v,'L');y=run(v,'P')
        for f in('nll','logz'):np.testing.assert_allclose(x[f].detach(),y[f].detach(),atol=1e-12,rtol=1e-12)
        np.testing.assert_allclose(x['mu'].detach().numpy().reshape(12,5),np.tile(y['mu'].detach().numpy(),(12,1)),atol=1e-12)
    def test_first_cell_same_S(self):
        v=inputs(cells=1);self.assertposterior(run(v,'L',offset=750000000),run(v,'S',offset=750000000),1e-12)
    def test_rho_one_later_loading_zero(self):
        v=inputs(rho=(1.,1.,1.));out=run(v);self.assertEqual(out['loadings'][0].tolist(),[1.,1.,1.]);self.assertEqual([x.tolist()for x in out['loadings'][1:]],[[0.,0.,0.]]*3)
    def test_latent_substitution_scalar(self):
        y=np.array([[.2,.5,.9],[.8,.1,.4]],dtype=np.float64);coef=np.array([[.1,.2,.03,.01,x,.4]for x in(-.8,0.,1.)],dtype=np.float64);u=np.array([.15,-.2,.3]);f=r.facts(y,coef,4.8,'L');z=y-u
        for j in range(2):
            for c in range(3):
                a,b,sd,d,value=f[3*j+c];latent=float(value-a-b*r.decimal(5.)-d*r.decimal(u[c]));t=math.log1p(.25*j);priorz=z[j-1,c]if j else 0.;expected=z[j,c]-coef[c,0]-coef[c,2]*t-(coef[c,1]+coef[c,3]*t)*(.2)-coef[c,4]*priorz;self.assertAlmostEqual(latent,expected,places=13)
    def test_coordinate_shift(self):
        v=inputs();x=run(v);shift=torch.tensor([.5,-.25,.125],dtype=DT);changed=(v[0],(v[1][0]+shift,),v[2],v[3]+shift,v[4]);self.assertposterior(x,run(changed),1e-12)
    def test_coordinate_shift_S_not_invariant(self):
        v=inputs();x=run(v,'S');shift=torch.tensor([.5,-.25,.125],dtype=DT);changed=(v[0],(v[1][0]+shift,),v[2],v[3]+shift,v[4]);self.assertGreater(abs(float((x['nll']-run(changed,'S')['nll']).detach())),1e-4)
    def test_prefix_suffix_same_joint_state(self):
        v=inputs(cells=12);p=arrays(v);nu=v[3].numpy()[0].copy();marks=v[1][0].numpy().copy();coef=v[2].detach().numpy().copy();a=r.start(p,nu,'L',processing_begin=time.monotonic());full=r.complete(r.append(a,marks,coef,4.8));b=r.start(p,nu,'L',processing_begin=time.monotonic());prefix=r.append(b,marks[:4],coef,4.8);r.complete(prefix);suffix=r.complete(r.append(prefix,marks[4:],coef,4.8));np.testing.assert_array_equal(full.logw,suffix.logw);np.testing.assert_array_equal(full.mu,suffix.mu);np.testing.assert_array_equal(full.sd,suffix.sd)
    def test_future_cells_do_not_change_prefix(self):
        v=inputs(cells=12);prefix=(v[0],(v[1][0][:4].clone(),),v[2],v[3],v[4]);a=run(prefix);v[1][0][4:]=100.;self.assertposterior(a,run(prefix),1e-12)
    def test_decimal_posterior(self):
        v=inputs();x=run(v);y=ref(v);np.testing.assert_allclose(x['mu'].detach().numpy()[0],y.mu,atol=1e-12,rtol=1e-12);np.testing.assert_allclose(x['sigma'].detach().numpy()[0],y.sd,atol=1e-12,rtol=1e-12);np.testing.assert_allclose(x['logw'].detach().numpy()[0],y.logw,atol=1e-12,rtol=1e-12);self.assertAlmostEqual(float(x['logz'].detach()[0]),y.logz,places=12);self.assertAlmostEqual(float(x['nll'].detach()[0]),y.nll(5.),places=12)
    def test_all_rho_gradients_finite_difference(self):
        for rho in((-.9,.4,.99),(1.,-1.2,0.),(4.,-3.,.8)):
            v=inputs(rho=rho);out=run(v);out['nll'].sum().backward();anal=v[2].grad[:,4].clone()
            for c in range(3):
                delta=1e-5;plus=v[2].detach().clone();minus=plus.clone();plus[c,4]+=delta;minus[c,4]-=delta;pv=(v[0],v[1],plus,v[3],v[4]);mv=(v[0],v[1],minus,v[3],v[4]);finite=(float(run(pv)['nll'][0])-float(run(mv)['nll'][0]))/(2*delta);self.assertAlmostEqual(float(anal[c]),finite,delta=1e-8)
    def test_correct_derivative_y_previous_minus_u(self):
        v=inputs();rho=v[2][:,4];d=k.reference_loading(rho,False,'L');intercept=rho*v[1][0][0]+d*v[3][0,0];grad=torch.autograd.grad(intercept.sum(),v[2])[0][:,4];torch.testing.assert_close(grad,v[1][0][0]-v[3][0,0],rtol=0,atol=0)
    def test_proper_scores_integral(self):
        v=inputs();m=ref(v);scores=m.scores(5.);integral,error=m.integrated_crps(5.);self.assertLess(error,1e-6);self.assertAlmostEqual(scores['crps'],integral,delta=1e-8)
        for q,x in scores['quantiles'].items():self.assertAlmostEqual(m.cdf(x),float(q),delta=1e-9)
        self.assertAlmostEqual(scores['median'],scores['quantiles']['0.5']);self.assertTrue(math.isfinite(scores['nll']))
    def test_kernel_cdf_crps_vs_reference(self):
        v=inputs();out=run(v);other=ref(v);mix=r.Mixture(out['logw'].detach().numpy()[0].copy(),out['mu'].detach().numpy()[0].copy(),out['sigma'].detach().numpy()[0].copy(),float(out['logz'].detach()[0]),r.Budget(time.monotonic()))
        for x in(-10.,0.,4.,5.,6.,20.):self.assertAlmostEqual(mix.cdf(x),other.cdf(x),delta=1e-12);self.assertAlmostEqual(mix.crps(x),other.crps(x),delta=1e-11)
    def test_all_coefficient_gradients(self):
        v=inputs();run(v)['nll'].sum().backward();gradient=v[2].grad.clone()
        for c in range(3):
            for j in range(6):
                plus=v[2].detach().clone();minus=plus.clone();plus[c,j]+=1e-5;minus[c,j]-=1e-5;pv=(v[0],v[1],plus,v[3],v[4]);mv=(v[0],v[1],minus,v[3],v[4]);difference=(float(run(pv)['nll'][0])-float(run(mv)['nll'][0]))/2e-5;self.assertAlmostEqual(float(gradient[c,j]),difference,delta=1e-8)
    def test_mixed_horizon_batch_no_padding_evidence(self):
        values=[inputs(cells=n,rho=(-.99,1.,.9999))for n in(1,9,17)];prior=tuple(torch.cat([v[0][j]for v in values])for j in range(3));marks=tuple(v[1][0]for v in values);nu=torch.cat([v[3]for v in values]);targets=torch.cat([v[4]for v in values]);out=k.marked_nll(prior,marks,values[0][2],nu,targets,'L',4.8,(1,3,5),(750000000,)*3,processing_begin=time.monotonic());self.assertEqual(out['density_points'],tuple(60*(n*3+1)for n in(1,9,17)))
        for j,v in enumerate(values):self.assertAlmostEqual(float(out['nll'][j].detach()),ref(v).nll(5.),delta=1e-11)
    def test_rho_representation_extreme_rejected_without_rescue(self):
        v=inputs(rho=(1e6,-1e6,1.))
        with self.assertRaises(ValueError):run(v)
    def test_shared_support_not_redrawn_each_cell(self):
        v=inputs();f=r.facts(v[1][0].numpy().copy(),v[2].detach().numpy().copy(),4.8,'L');noise=v[3].numpy()[0];logs=[];local=[]
        for n,(a,b,sd,d,y)in enumerate(f):
            terms=[-.5*math.log(2*math.pi*float(sd)**2)-.5*((float(y-a-b*r.decimal(5.)-d*r.decimal(u[n%3])))/float(sd))**2 for u in noise];local.append(float(r.logsumexp(terms)-math.log(12)));logs.append(terms)
        shared=float(r.logsumexp(np.asarray(logs).sum(0))-math.log(12));redrawn=sum(local);self.assertGreater(abs(shared-redrawn),1e-6)
    def test_reference_budget_expires(self):
        v=inputs()
        with self.assertRaisesRegex(ValueError,'deadline'):r.start(arrays(v),v[3].numpy()[0].copy(),'L',processing_begin=time.monotonic()-11)
    def test_S_and_P_inherited_values_gradients(self):
        for mode in('S','P'):
            v=inputs();new=run(v,mode);new['nll'].sum().backward();gradient=v[2].grad.clone();v[2].grad.zero_();original=old.marked_nll(*v[:4],v[4],mode,4.8,(1,),(0,),processing_begin=time.monotonic());original['nll'].sum().backward();self.assertposterior(new,original,1e-12);torch.testing.assert_close(gradient,v[2].grad,rtol=1e-12,atol=1e-12)
    def test_direct_loss_and_guard_AST_preserved(self):
        def functions(path):return {node.name:ast.dump(node)for node in ast.parse(Path(path).read_text()).body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
        original=functions(old.__file__);new=functions(k.__file__)
        for name in('direct_nll','loss24','Budget','tensor','ulp','precision','inputs','finish'):self.assertEqual(new[name],original[name])
    def test_reference_input_domain_matches_kernel(self):
        v=inputs();nu=v[3].numpy()[0].copy();nu[0,0]=1e6+1
        with self.assertRaisesRegex(ValueError,'input_representation'):r.start(arrays(v),nu,'L',processing_begin=time.monotonic())
    def test_reference_boolean_mref_denied(self):
        v=inputs()
        with self.assertRaisesRegex(ValueError,'mref'):r.facts(v[1][0].numpy().copy(),v[2].detach().numpy().copy(),True,'L')
    def test_reference_rejects_huge_evidence_before_normalization(self):
        prior=(np.log(np.array([.05,.1,.15,.3,.4])),np.array([4.,4.4,4.8,5.2,5.6]),np.ones(5));nu=np.full((12,3),1e6);coeff=np.array([[0.,0.,0.,0.,1e6,.4]]*3);marks=np.zeros((4,3))
        state=r.append(r.start(prior,nu,'L',processing_begin=time.monotonic()),marks,coeff,4.8)
        with self.assertRaisesRegex(ValueError,'evidence_precision'):r.complete(state)
    def test_reference_rejects_improper_weights_not_CDF_only_normalization(self):
        with self.assertRaisesRegex(ValueError,'proper_mixture'):r.Mixture(np.zeros(60),np.zeros(60),np.ones(60),0.,r.Budget(time.monotonic()))
    def test_invalid_clock(self):
        v=inputs()
        with self.assertRaisesRegex(ValueError,'allpositive|tensor'):run(v,h=3)
    def test_unknown_mode(self):
        with self.assertRaisesRegex(ValueError,'arm'):run(inputs(),'X')
    def test_false_first(self):
        with self.assertRaisesRegex(ValueError,'loading'):k.reference_loading(torch.zeros(3,dtype=DT),1,'L')
    def test_deadline(self):
        v=inputs()
        with self.assertRaisesRegex(ValueError,'deadline'):k.marked_nll(*v[:4],v[4],'L',4.8,(1,),(0,),processing_begin=time.monotonic()-11)
    def test_precision_large_target(self):
        v=inputs();v=(*v[:4],torch.tensor([1e8],dtype=DT))
        with self.assertRaisesRegex(ValueError,'target_precision'):run(v)
    def test_softplus_twenty(self):
        for x in(19.999,20.,20.001,-20.,-100.):self.assertAlmostEqual(float(r.softplus(x)),float(torch.nn.functional.softplus(torch.tensor(x,dtype=DT))),delta=1e-14)

if __name__=='__main__':unittest.main()

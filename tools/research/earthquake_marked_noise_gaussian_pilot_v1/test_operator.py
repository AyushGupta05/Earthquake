"""Invented no-optimizer float64 mathematical checks."""
import math,time,unittest
from unittest.mock import patch
import numpy as np
import torch
from scipy.integrate import quad
from scipy.special import ndtr,logsumexp
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('marked_operator',Path(__file__).with_name('gaussian_operator.py'));op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)
import reference_core

DT=torch.float64

def fixture(j=4):
    p=torch.tensor([.1,.2,.3,.2,.2],dtype=DT).log();mu=torch.tensor([-2.,-.5,.3,1.5,3.],dtype=DT);s=torch.tensor([.6,.7,.8,.9,1.],dtype=DT)
    coeff=torch.tensor([[.1,.2,.04,.01,.1,.4],[-.1,.1,.02,-.01,.12,.3],[.2,-.15,-.03,.02,.07,.5]],dtype=DT)
    mark=torch.tensor([[.3+.1*k,.2-.04*k,.1+.03*k] for k in range(j)],dtype=DT)
    nu=torch.tensor([[.02*(k-5.5),-.01*(k-5.5),.015*(k-5.5)] for k in range(12)],dtype=DT)
    return (p,mu,s),mark,coeff,nu


def run(arm='S',j=4):
    prior,mark,coef,nu=fixture(j);return op.marked(prior,mark,coef,nu,arm,5.,processing_begin=time.monotonic())


class Tests(unittest.TestCase):
    def test_checked_nonGaussian_mixture_proper_scores(self):
        p=run();score=op.checked_scores(p,.7,reference_core)
        self.assertTrue(all(v<=1e-6 for k,v in score['diagnostics']['errors'].items() if k in ('crps','pit')))
        self.assertTrue(all(type(score['coverage_'+str(k)]) is bool for k in (50,80,95)))
        self.assertEqual(score['median'],score['quantiles']['0.5']);self.assertGreater(score['crps'],0)
    def test_gaussian_closed_reference(self):
        prior,marks,coeff,nu=fixture(1);prior=(torch.tensor([0.,-100.,-100.,-100.,-100.],dtype=DT),torch.zeros(5,dtype=DT),torch.ones(5,dtype=DT));coeff.zero_();coeff[:,5]=math.log(math.expm1(.95));coeff[0,1]=1;marks[0]=torch.tensor([2.,0.,0.],dtype=DT)
        p=op.marked(prior,marks,coeff,nu*0,'P',0.,processing_begin=time.monotonic())
        self.assertAlmostEqual(op.scalar(p.mean()),1.,places=12);self.assertAlmostEqual(float(p.sigma[0]),math.sqrt(.5),places=12)
        self.assertAlmostEqual(p.cdf(1.),.5,places=12)
        crps=p.crps(1.);expected=math.sqrt(.5)*(math.sqrt(2/math.pi)-1/math.sqrt(math.pi));self.assertAlmostEqual(crps,expected,places=12)
    def test_differentiable_normalization_gradcheck(self):
        prior,marks,coef,nu=fixture(3);coef.requires_grad_()
        def loss(c):return op.marked(prior,marks,c,nu,'S',5.,processing_begin=time.monotonic()).nll(torch.tensor(.7,dtype=DT))
        self.assertTrue(torch.autograd.gradcheck(loss,(coef,),eps=1e-6,atol=1e-5,rtol=1e-4));loss(coef).backward();self.assertTrue(torch.isfinite(coef.grad).all());self.assertTrue((coef.grad!=0).all())
    def test_prior_all_parameters_used_and_no_first_mark_input(self):
        torch.manual_seed(19);net=op.Prior(6);context=torch.tensor([.1,.2,-.1,.3,.5,-.7],dtype=DT);prior=net(context);saved=tuple(x.detach().clone() for x in prior)
        _,mark,coef,nu=fixture();p=op.marked(prior,mark,coef,nu,'S',5.,processing_begin=time.monotonic());p.nll(torch.tensor(.7,dtype=DT)).backward()
        self.assertTrue(all(x.grad is not None and bool((x.grad!=0).all()) for x in net.parameters()));self.assertTrue(all(torch.equal(a,b) for a,b in zip(saved,net(context))))
        with self.assertRaises(ValueError):net(torch.zeros(7,dtype=DT))
        self.assertEqual(sum(x.numel() for x in net.parameters()),16*6+526)
    def test_zero_static_dimension_no_torch_warning(self):
        net=op.Prior(0);prior=net(torch.empty(0,dtype=DT));op.validate_prior(prior);self.assertEqual(sum(x.numel() for x in net.parameters()),526)
    def test_future_prefix_invariance_and_not_posterior_as_prior(self):
        prior,mark,c,nu=fixture(20);c.requires_grad_();original=op.marked(prior,mark[:4],c,nu,'S',5.,processing_begin=time.monotonic());mark[4:]+=3
        repeat=op.marked(prior,mark[:4],c,nu,'S',5.,processing_begin=time.monotonic());self.assertTrue(torch.equal(original.mu,repeat.mu));self.assertTrue(torch.equal(original.logw,repeat.logw));original.nll(torch.tensor(.7,dtype=DT)).backward();self.assertTrue(torch.isfinite(c.grad).all())
        with self.assertRaises(ValueError):op.marked((original.logw,original.mu,original.sigma),mark[:4],c,nu,'S',5.,processing_begin=time.monotonic())
    def test_joint_fact_suffix_no_evidence_duplication_reference(self):
        p=run(j=12);data=p.reference;prior,mu,sd=data['prior'];state=reference_core.start(prior.exp().tolist(),mu.tolist(),sd.tolist(),data['nu'].tolist(),[1/12]*12)
        cells=[dict(cell=j,a=a.tolist(),b=b.tolist(),sigma=s.tolist(),value=y.tolist()) for j,(a,b,s,y) in enumerate(data['facts'],1)]
        joint=reference_core.append(state,cells);seq=reference_core.append(reference_core.append(state,cells[:4]),cells[4:]);self.assertEqual(joint,seq)
        result=reference_core.Posterior(seq,.7,processing_begin=time.monotonic());self.assertAlmostEqual(op.scalar(p.logz),result.logz,places=10)
    def test_shared_vs_redrawn_joint_noise_different(self):
        prior,mark,c,nu=fixture(2);mark[:,0]=torch.tensor([1.,-1.],dtype=DT);c.zero_();c[:,5]=0.;c[0,1]=.8
        nu.zero_();nu[:6,0]=-1;nu[6:,0]=1
        shared=op.marked(prior,mark,c,nu,'S',0.,processing_begin=time.monotonic());logs=[]
        for a in (-1.,1.):
            for b in (-1.,1.):
                altered=mark.clone();altered[0,0]-=a;altered[1,0]-=b
                p=op.marked(prior,altered,c,nu*0,'P',0.,processing_begin=time.monotonic());logs.append(op.scalar(p.logz)+math.log(.25))
        self.assertGreater(abs(op.scalar(shared.logz)-float(logsumexp(logs))),.1)
    def test_no_magnitude_slope_preserves_prior(self):
        prior,mark,c,nu=fixture();c[:,1]=0;c[:,3]=0;p=op.marked(prior,mark,c,nu,'S',5.,processing_begin=time.monotonic())
        expected=(prior[0].exp()*prior[1]).sum();self.assertAlmostEqual(op.scalar(p.mean()),op.scalar(expected),places=12)
    def test_whole_cohort_censor_and_prefix_failure_denied(self):
        _,mark,_,_=fixture(20);packet=[(mark[:4].clone(),mark[:12].clone(),mark.clone()) for _ in range(87)];self.assertTrue(op.admit_allpositive(packet))
        packet[86][2][19,2]=-12
        with self.assertRaisesRegex(ValueError,'allpositive_admission'):op.admit_allpositive(packet)
        with self.assertRaises(ValueError):op.admit_allpositive(packet[:86])
    def test_censor_operator_never_coerces_or_drops(self):
        prior,marks,c,nu=fixture();marks[0,0]=-12
        with self.assertRaisesRegex(ValueError,'allpositive_admission'):op.marked(prior,marks,c,nu,'S',5.,processing_begin=time.monotonic())
    def test_D_mask_constants_capacity_and_gradient(self):
        x=torch.arange(195*20,dtype=DT).reshape(195,20);x[:,[4,9,14]]=0;x[:,17]=.1
        active=op.summary_mask(x);self.assertNotIn(17,active);self.assertEqual(len(active),16);counts=op.capacity(6,active);self.assertLessEqual(max(counts.values())/min(counts.values()),1.05)
        prior,*_=fixture();theta=torch.full((16,),.01,dtype=DT,requires_grad=True);tau=torch.tensor(.1,dtype=DT,requires_grad=True);summary=torch.linspace(.1,2.,20,dtype=DT)
        p=op.direct(prior,summary,theta,tau,active,processing_begin=time.monotonic());p.nll(torch.tensor(.7,dtype=DT)).backward();self.assertTrue((theta.grad!=0).all());self.assertNotEqual(float(tau.grad),0)
        self.assertLess(op.checked_scores(p,.7,reference_core)['diagnostics']['errors']['crps'],1e-6)
    def test_parameter_tensor_caps_dtype_and_budget(self):
        prior,mark,c,nu=fixture()
        with self.assertRaises(ValueError):op.marked(prior,mark.float(),c,nu,'S',5.,processing_begin=time.monotonic())
        with self.assertRaises(ValueError):op.marked(prior,mark,c,nu,'I',5.,processing_begin=time.monotonic())
        with self.assertRaisesRegex(ValueError,'deadline'):op.marked(prior,mark,c,nu,'S',5.,processing_begin=time.monotonic()-11)
        b=op.Budget(time.monotonic())
        with self.assertRaisesRegex(ValueError,'evaluation_cap'):b.check(1000001)
    def test_huge_evidence_precision_rejection(self):
        prior,mark,c,nu=fixture(20);mark.fill_(1e6);c.zero_();c[:,5]=-20
        with self.assertRaisesRegex(ValueError,'evidence_precision'):op.marked(prior,mark,c,nu,'S',5.,processing_begin=time.monotonic())
    def test_summary_fields_scaling_and_initializer(self):
        prior,mark,c,nu=fixture();v=op.summaries(mark,nu);self.assertEqual(v.shape,(20,));self.assertTrue((v[[4,9,14]]==0).all());self.assertAlmostEqual(float(v[3]),.4,places=12)
        batch=torch.stack([op.summaries(fixture(j)[1],nu) for j in (4,12,20)]*65);mean,std,active=op.summary_scaler(batch);scaled=op.standardized_summary(v,mean,std);self.assertTrue(torch.isfinite(scaled).all());self.assertTrue((scaled[std==0]==0).all())
        net=op.Prior(6);net.initialize(5.,.8);self.assertTrue((net.head.bias[:4]==0).all());self.assertTrue((net.head.weight!=0).all());self.assertAlmostEqual(float((.05+torch.nn.functional.softplus(net.head.bias[9:])).mean().detach()),.8,places=12)
    def test_clock_count_wrapper_future_h2_and_offsets(self):
        prior,mark,c,nu=fixture(20)
        for h,j in ((1,4),(3,12),(5,20)):op.forecast(prior,mark[:j],c,nu,'S',5.,h,0,processing_begin=time.monotonic())
        op.forecast(prior,mark[:1],c,nu,'S',5.,1,750000000,processing_begin=time.monotonic())
        for h,j,offset in ((2,4,0),(1,5,0),(3,4,0),(1,4,True)):
            with self.assertRaises(ValueError):op.forecast(prior,mark[:j],c,nu,'S',5.,h,offset,processing_begin=time.monotonic())

    def test_real_parameterized_S_P_D_counts_and_all_gradients(self):
        _,mark,_,nu=fixture(4);context=torch.tensor([.1,.2,-.1,.3,.5,-.7],dtype=DT);active=tuple(i for i in range(20) if i not in (4,9,14));expected=op.capacity(6,active)
        for arm in ('S','P','D'):
            torch.manual_seed(20261012);net=op.DirectNet(6,active) if arm=='D' else op.MarkedNet(6,arm,5.);net.prior.initialize(5.,.8)
            posterior=net(context,torch.linspace(.1,2.,20,dtype=DT),processing_begin=time.monotonic()) if arm=='D' else net(context,mark,nu,processing_begin=time.monotonic())
            posterior.nll(torch.tensor(.7,dtype=DT)).backward();self.assertEqual(sum(x.numel() for x in net.parameters()),expected[arm]);self.assertTrue(all(x.grad is not None and bool((x.grad!=0).all()) for x in net.parameters()))

    def test_far_separated_narrow_components_proper_reference(self):
        prior,marks,c,nu=fixture(1);prior=(torch.tensor([0.,-100.,-100.,-100.,-100.],dtype=DT),torch.zeros(5,dtype=DT),torch.full((5,),1000.,dtype=DT))
        nu.zero_();nu[:6,0]=-1000.;nu[6:,0]=1000.;c.zero_();c[:,5]=math.log(math.expm1(.001));c[0,1]=1.;marks.zero_()
        p=op.marked(prior,marks,c,nu,'S',0.,processing_begin=time.monotonic());score=op.checked_scores(p,1000.,reference_core)
        self.assertLess(score['diagnostics']['errors']['crps'],1e-6);self.assertGreater(score['crps'],499.);self.assertLess(score['crps'],501.)
    def test_reference_budget_reserved_before_any_call(self):
        p=run();p.budget.points=1000000-239
        with patch.object(reference_core,'Posterior') as call:
            with self.assertRaisesRegex(ValueError,'evaluation_cap'):op.checked_scores(p,.7,reference_core)
            call.assert_not_called()
    def test_full_invented65TRAIN22DEV_allprefix_gradient_union(self):
        begin=time.monotonic();rows=[];contexts=[]
        for i in range(87):
            _,mark,_,nu=fixture(20);mark=mark+.001*i;nu=nu*(1+.005*i);rows.append(((mark[:4],mark[:12],mark),nu));contexts.append(torch.tensor([math.sin(.1*i+k)+.01*i for k in range(6)],dtype=DT))
        self.assertTrue(op.admit_allpositive([r[0] for r in rows]));train_summaries=torch.stack([op.summaries(mark,nu) for prefixes,nu in rows[:65] for mark in prefixes]);mean,std,active=op.summary_scaler(train_summaries);expected=op.capacity(6,active)
        for arm in ('S','P','D'):
            torch.manual_seed(20261012);net=op.DirectNet(6,active) if arm=='D' else op.MarkedNet(6,arm,5.);net.prior.initialize(5.,.8);union=[torch.zeros_like(p,dtype=torch.bool) for p in net.parameters()]
            for i,(prefixes,nu) in enumerate(rows[:65]):
                for mark in prefixes:
                    net.zero_grad();posterior=net(contexts[i],op.standardized_summary(op.summaries(mark,nu),mean,std),processing_begin=time.monotonic()) if arm=='D' else net(contexts[i],mark,nu,processing_begin=time.monotonic());posterior.nll(torch.tensor(5.+.3*math.sin(i),dtype=DT)).backward()
                    for present,param in zip(union,net.parameters()):present|=param.grad!=0
            self.assertEqual(sum(int(u.sum()) for u in union),expected[arm]);self.assertEqual(sum(p.numel() for p in net.parameters()),expected[arm])
        # All22DEV current prefixes represented and all3h scored at each boundary.
        for i in (65,86):
            prefixes,nu=rows[i]
            for mark in prefixes:op.checked_scores(op.marked(fixture()[0],mark,fixture()[2],nu,'S',5.,processing_begin=time.monotonic()),.7,reference_core)
        print('INVENTED_FULL65_22_PROFILE_SECONDS',time.monotonic()-begin)

    def test_direct_entry_exit_and_mean_deadline_enforced(self):
        prior,*_=fixture();active=tuple(i for i in range(20) if i not in (4,9,14));summary=torch.zeros(20,dtype=DT);theta=torch.zeros(17,dtype=DT);tau=torch.zeros((),dtype=DT)
        with self.assertRaisesRegex(ValueError,'deadline'):op.direct(prior,summary,theta,tau,active,processing_begin=time.monotonic()-11)
        p=op.direct(prior,summary,theta,tau,active,processing_begin=time.monotonic())
        with patch.object(op.time,'monotonic',return_value=p.budget.begin+11):
            with self.assertRaisesRegex(ValueError,'deadline'):p.mean()
        begin=time.monotonic()
        with patch.object(op.time,'monotonic',side_effect=[begin,begin,begin+11]):
            with self.assertRaisesRegex(ValueError,'deadline'):op.direct(prior,summary,theta,tau,active,processing_begin=begin)

    def test_independent_rejection_no_scorer_replacement(self):
        p=run()
        with patch.object(reference_core,'Posterior',side_effect=ValueError('invented independent failure')):
            with self.assertRaisesRegex(ValueError,'invented independent failure'):op.checked_scores(p,.7,reference_core)

if __name__=='__main__':unittest.main()

"""Invented mathematical checks only; no actual inputs, waveform, optimizer or IO."""
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr,logsumexp
import core


def base(noise=None,weights=None,full=False):
    if noise is None:noise=[[-.5,0.,0.],[.5,0.,0.]]+[[0.,0.,0.]]*10
    if weights is None:weights=[.5,.5]+[0.]*10
    return core.start([.1,.2,.3,.2,.2] if full else [1.,0.,0.,0.,0.],[-2.,-.5,.3,1.5,3.] if full else [0.]*5,[.6,.7,.8,.9,1.] if full else [1.]*5,noise,weights)


def cell(j,y=(.3,.2,.1),b=(.6,.2,-.1),a=(0.,0.,0.),sigma=(.7,.8,.9)):
    return dict(cell=j,a=list(a),b=list(b),sigma=list(sigma),value=list(y))


def posterior(state,target=.7):return core.Posterior(state,target,processing_begin=time.monotonic())


class CoreTests(unittest.TestCase):
    def test_noise_support_centered_joint_and_floor_retained(self):
        nu,w=core.noise_support([[2.+j for j in range(12)],[3.+2*j for j in range(12)],[.1]*12])
        self.assertEqual(len(nu),12);self.assertAlmostEqual(math.fsum(w),1.)
        for c in range(3):self.assertAlmostEqual(math.fsum(v[c] for v in nu),0.,places=12)
        self.assertTrue(all(v[2]==0 for v in nu));self.assertEqual(core.noise_support([[0.]*12]*3)[0],((0.,0.,0.),)*12)
    def test_censor_kernel_mixed_mass_is_normalized(self):
        for mean,sigma in ((-12.,.7),(1.,2.),(-15.,1.)):
            mass=float(ndtr((core.DELTA-mean)/sigma))
            positive,_=quad(lambda y:math.exp(-.5*((y-mean)/sigma)**2)/(sigma*math.sqrt(2*math.pi)),core.DELTA,math.inf)
            self.assertAlmostEqual(mass+positive,1.,places=10)
    def test_allpositive_sequential_suffix_equals_joint_exact(self):
        initial=base(full=True);cells=[cell(1),cell(2,(.8,.4,.2)),cell(3,(.4,.3,.2))]
        one=core.append(initial,cells);sequential=core.append(core.append(core.append(initial,cells[:1]),cells[1:2]),cells[2:])
        self.assertEqual(one,sequential);p,q=posterior(one),posterior(sequential)
        self.assertEqual(p.summary()['integrals'],q.summary()['integrals']);self.assertEqual(p.noise_probabilities,q.noise_probabilities)
    def test_shared_and_independently_redrawn_noise_are_different(self):
        nu=[[-1.,0.,0.],[1.,0.,0.]]+[[0.,0.,0.]]*10;w=[.5,.5]+[0.]*10
        cells=[cell(1,(1.,0.,0.),(1.,0.,0.),sigma=(.3,1.,1.)),cell(2,(-1.,0.,0.),(1.,0.,0.),sigma=(.3,1.,1.))]
        shared=posterior(core.append(base(nu,w),cells));masses=[]
        for first in (-1.,1.):
            for second in (-1.,1.):
                independent=[dict(cells[0],a=[first,0.,0.]),dict(cells[1],a=[second,0.,0.])]
                fixed=posterior(core.append(base([[0.,0.,0.]]*12,[1.]+[0.]*11),independent))
                masses.append(math.log(.25)+fixed.logz)
        independent_logz=float(logsumexp(masses))
        self.assertGreater(abs(shared.logz-independent_logz),1.)
    def test_no_magnitude_slope_preserves_prior_but_updates_noise(self):
        s=core.append(base(full=True),[cell(1,b=(0.,0.,0.))]);p=posterior(s)
        expected=math.fsum(w*m for w,m in zip(s.pi,s.mu));self.assertAlmostEqual(p.integrals['adaptive']['mean'],expected,places=12)
        for x in (-3.,0.,2.,5.):self.assertAlmostEqual(p.cdf(x),math.fsum(w*float(ndtr((x-m)/sd)) for w,m,sd in zip(s.pi,s.mu,s.sigma)),places=12)
        self.assertNotAlmostEqual(p.noise_probabilities[0],.5)
    def test_posterior_density_allreal_normalized_and_uncensored_closed_form(self):
        s=core.append(base(noise=[[0.,0.,0.]]*12,weights=[1.]+[0.]*11),[cell(1,y=(2.,0.,0.),b=(1.,0.,0.),sigma=(1.,1.,1.))]);p=posterior(s,target=1.)
        self.assertAlmostEqual(p.integrals['adaptive']['mean'],1.,places=12);self.assertAlmostEqual(p.components[0].sd,math.sqrt(.5),places=12)
        norm,_=quad(p.density,-math.inf,math.inf,epsabs=1e-9);self.assertAlmostEqual(norm,1.,places=9)
        self.assertEqual(p.cdf(-math.inf),0.);self.assertEqual(p.cdf(math.inf),1.)
    def test_censored_nonGaussian_reference_and_cdf(self):
        s=core.append(base(noise=[[0.,0.,0.]]*12,weights=[1.]+[0.]*11),[cell(1,y=(None,0.,0.),b=(.4,0.,0.),a=(-12.,0.,0.),sigma=(1.,1.,1.))]);p=posterior(s,target=.3)
        norm,_=quad(lambda x:math.exp(-.5*x*x)/math.sqrt(2*math.pi)*float(ndtr(-.4*x)),-math.inf,math.inf)
        mean,_=quad(lambda x:x*math.exp(-.5*x*x)/math.sqrt(2*math.pi)*float(ndtr(-.4*x)),-math.inf,math.inf)
        cdf,_=quad(lambda x:math.exp(-.5*x*x)/math.sqrt(2*math.pi)*float(ndtr(-.4*x)),-math.inf,.3)
        self.assertAlmostEqual(p.integrals['adaptive']['mean'],mean/norm,places=8);self.assertAlmostEqual(p.cdf(.3),cdf/norm,places=8);self.assertTrue(all(x<=1e-4 for x in p.errors.values()));self.assertFalse(p.summary()['censored_CRPS_verified'])
    def test_duplicate_skipped_cells_and_future_append_do_not_change_old_state(self):
        original=base();first=core.append(original,[cell(1)]);saved=posterior(first).summary()['integrals'];later=core.append(first,[cell(2)])
        self.assertEqual(posterior(first).summary()['integrals'],saved);self.assertEqual(len(first.cells),1);self.assertEqual(len(later.cells),2)
        for bad in (cell(1),cell(3)):
            with self.assertRaises(core.NumericalFailure):core.append(first,[bad])
    def test_noise_state_permutation_invariant_but_sign_spread_sensitive(self):
        s=core.append(base(),[cell(1)]);p=posterior(s);order=list(reversed(range(12)))
        perm=core.start(s.pi,s.mu,s.sigma,[s.noise[i] for i in order],[s.noise_weights[i] for i in order]);q=posterior(core.append(perm,[cell(1)]));self.assertAlmostEqual(p.logz,q.logz,places=12)
        zero=posterior(core.append(base([[0.,0.,0.]]*12),[cell(1)]));self.assertGreater(abs(p.logz-zero.logz),1e-4)
        asym=base([[.2,0.,0.],[.8,0.,0.]]+[[0.,0.,0.]]*10);signed=base([[-.2,0.,0.],[-.8,0.,0.]]+[[0.,0.,0.]]*10)
        self.assertGreater(abs(posterior(core.append(asym,[cell(1)])).logz-posterior(core.append(signed,[cell(1)])).logz),1e-4)
    def test_censor_is_not_a_boundary_point_and_allzero_still_retained(self):
        s=core.append(base(),[cell(1,y=(None,None,None),a=(-12.,-12.,-12.),b=(.1,.1,.1))]);p=posterior(s);self.assertEqual(len(s.cells),1);self.assertEqual(len(p.noise_probabilities),12)
        with self.assertRaises(core.NumericalFailure):core.append(base(),[cell(1,y=(-12.,0.,0.))])
    def test_budget_and_caps_reject_without_accepted_repair(self):
        with patch.object(core.time,'monotonic',return_value=2000000.):
            core.Budget(2000000.,10).check()
            result=core.infer(base(),0.,processing_begin=1999980.);self.assertFalse(result['accepted']);self.assertIs(result['state'].__class__,core.State)
        with self.assertRaises(core.NumericalFailure):core.append(base(),[cell(j) for j in range(1,22)])
    def test_sharp_censored_GH_failure_keeps_errors_and_whole_state(self):
        s=core.append(base([[0.,0.,0.]]*12,[1.]+[0.]*11),[cell(1,y=(None,0.,0.),a=(-12.,0.,0.),b=(80.,0.,0.),sigma=(1.,1.,1.))])
        result=core.infer(s,.7,processing_begin=time.monotonic());self.assertFalse(result['accepted']);self.assertEqual(result['reason'],'quadrature_parity');self.assertIs(result['state'],s);self.assertIn('errors',result['evidence']);self.assertIn('integrals',result['evidence'])
    def test_large_native_noise_powers_and_cdf_not_support_clipped(self):
        nu,_=core.noise_support([[1e20]*12,[1e24]*12,[0.]*12]);self.assertEqual(nu,((0.,0.,0.),)*12)
        p=posterior(core.append(base(full=True),[cell(1)]));self.assertEqual(p.cdf(1e7),1.);self.assertEqual(p.cdf(-1e7),0.)
    def test_forged_state_or_mutable_input_cannot_bypass_schema(self):
        original=base();c=cell(1);s=core.append(original,[c]);c['a'][0]=999.;self.assertNotEqual(s.cells[0][1][0],999.)
        forged=core.State(original.pi,original.mu,(0.,)*5,original.noise,original.noise_weights)
        result=core.infer(forged,0.,processing_begin=time.monotonic());self.assertFalse(result['accepted'])

    def test_huge_common_logmass_rejected_not_false_normal_density(self):
        s=core.append(base([[0.,0.,0.]]*12,[1.]+[0.]*11),[cell(j,y=(1e6,)*3,b=(0.,)*3,sigma=(.05,)*3) for j in range(1,21)])
        result=core.infer(s,0.,processing_begin=time.monotonic())
        self.assertFalse(result['accepted']);self.assertEqual(result['reason'],'evidence_precision');self.assertIs(result['state'],s)
        self.assertEqual(result['evidence']['failure']['label'],'positive_logmass');self.assertIn('value',result['evidence']['failure']);self.assertGreaterEqual(result['evidence']['work']['density_points'],0)
        # Moderately rare, magnitude-independent evidence still preserves N(0,1).
        moderate=core.append(base([[0.,0.,0.]]*12,[1.]+[0.]*11),[cell(1,y=(10.,)*3,b=(0.,)*3,sigma=(1.,)*3)])
        p=posterior(moderate,target=0.)
        self.assertAlmostEqual(p.integrals['adaptive']['nll'],.5*math.log(2*math.pi),places=10)
        self.assertAlmostEqual(p.density(0.),1/math.sqrt(2*math.pi),places=10)
    def test_broad_prior_steep_slope_stable_completion_matches_reference(self):
        s=core.start([1.,0.,0.,0.,0.],[1e6,0.,0.,0.,0.],[1e6,1.,1.,1.,1.],[[0.,0.,0.]]*12,[1.]+[0.]*11)
        s=core.append(s,[cell(1,y=(1.,0.,0.),b=(1e6,0.,0.),sigma=(.05,1.,1.))]);target=1.05e-6;p=posterior(s,target)
        mean=(1e6*.05**2+1e12*1e6)/(1e24+.05**2);variance=1e12*.05**2/(1e24+.05**2)
        nll=.5*(math.log(2*math.pi*variance)+(target-mean)**2/variance)
        self.assertAlmostEqual(p.integrals['adaptive']['mean'],mean,places=18);self.assertLess(abs(p.integrals['adaptive']['nll']-nll),1e-8)
        with self.assertRaisesRegex(core.NumericalFailure,'gaussian_mean_precision'):
            core.gaussian_update(1e6,1e12,0.,0.,1.,.05,1e6)
    def test_adaptive_constructor_failure_retains_partial_work_component(self):
        s=core.append(base([[0.,0.,0.]]*12,[1.]+[0.]*11),[cell(1,y=(None,0.,0.),a=(-12.,0.,0.),b=(.4,0.,0.),sigma=(1.,1.,1.))])
        def fail_quad(fn,*args,**kwargs):
            fn(0.);raise core.IntegrationWarning('invented failure after counted work')
        with patch.object(core,'quad',side_effect=fail_quad):result=core.infer(s,.7,processing_begin=time.monotonic())
        self.assertFalse(result['accepted']);self.assertIs(result['state'],s);self.assertGreater(result['evidence']['work']['density_points'],0);self.assertIn('peak',result['evidence']['current_component']);self.assertEqual(result['evidence']['completed_components'],[])
    def test_later_GH_failure_retains_already_completed_integrals(self):
        original=core.Component.gh
        def fail128(component,order):
            if order==128:raise core.NumericalFailure('invented_gh_failure')
            return original(component,order)
        with patch.object(core.Component,'gh',new=fail128):result=core.infer(core.append(base(),[cell(1)]),.7,processing_begin=time.monotonic())
        self.assertFalse(result['accepted']);self.assertEqual(set(result['evidence']['integrals']),{'adaptive','gh64'});self.assertGreater(result['evidence']['work']['density_points'],0);self.assertEqual(len(result['evidence']['completed_components']),2)

    def test_nested_mutable_forged_state_denied_before_append_or_infer(self):
        original=core.append(base(),[cell(1)])
        cases=[dict(pi=list(original.pi)),dict(noise=(list(original.noise[0]),)+original.noise[1:]),dict(cells=((1,list(original.cells[0][1]),original.cells[0][2],original.cells[0][3],original.cells[0][4]),))]
        for change in cases:
            values=dict(pi=original.pi,mu=original.mu,sigma=original.sigma,noise=original.noise,noise_weights=original.noise_weights,cells=original.cells)
            values.update(change);forged=core.State(**values)
            result=core.infer(forged,0.,processing_begin=time.monotonic());self.assertFalse(result['accepted']);self.assertEqual(result['reason'],'state_immutable');self.assertIs(result['state'],forged)
            with self.assertRaisesRegex(core.NumericalFailure,'state_immutable'):core.append(forged,[cell(2)])
        mutable=cell(2);new=core.append(original,[mutable]);mutable['value'][0]=999.
        self.assertEqual(new.cells[1][4][0],.3);self.assertEqual(len(original.cells),1)

    def test_deadline_counts_horizon2_future_zero_and_noise_override_denied(self):
        s=base();first=core.append(s,[cell(1)])
        for state,h in ((s,1),(first,2),(first,1),(core.append(s,[cell(j) for j in range(1,6)]),1)):
            result=core.forecast(state,.7,h,processing_begin=time.monotonic());self.assertFalse(result['accepted'])
        clocked=core.start(s.pi,s.mu,s.sigma,s.noise,s.noise_weights,arrival_offset_ns=750000000)
        one=core.append(clocked,[cell(1)]);self.assertTrue(core.forecast(one,.7,1,processing_begin=time.monotonic())['accepted'])
        nine=core.append(one,[cell(j) for j in range(2,10)]);self.assertTrue(core.forecast(nine,.7,3,processing_begin=time.monotonic())['accepted']);self.assertEqual(nine.noise,one.noise);self.assertEqual(nine.noise_weights,one.noise_weights)
        with self.assertRaises(TypeError):core.forecast(nine,.7,3,processing_begin=time.monotonic(),noise=[[0.]*3]*12)
        with self.assertRaises(core.NumericalFailure):core.start(s.pi,s.mu,s.sigma,s.noise,s.noise_weights,arrival_offset_ns=True)

    def test_dimensional_worst_60components_by60censor_timed(self):
        nu=[[.02*(j-5.5),-.01*(j-5.5),.015*(j-5.5)] for j in range(12)]
        s=core.append(base(nu,[1/12]*12,full=True),[cell(j,y=(None,None,None),a=(-12.,-12.,-12.),b=(.03,-.02,.01),sigma=(1.,1.,1.)) for j in range(1,21)])
        begin=time.monotonic();result=core.infer(s,.7,processing_begin=begin);self.assertTrue(result['accepted'],result);self.assertEqual(result['components'],60);self.assertLess(result['work']['seconds'],10.);self.assertLessEqual(result['work']['density_points'],1000000)
        print('INVENTED_WORST',result['work'])


if __name__=='__main__':unittest.main()

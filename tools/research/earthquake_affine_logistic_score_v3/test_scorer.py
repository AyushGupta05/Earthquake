"""Synthetic operator accuracy, GH rejection, speed path and gradients."""
import copy
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.special import expit
from scorer import score,NumericalFailure
from reference import Posterior,gaussian_score,factors
from benchmarks import CASES
from third_reference import grid_reference,missed_mode_diagnostic,gaussian_absolute_moments


def new(case,**kwargs):
    c={k:v for k,v in case.items()if k!='name'}
    return score(**c,processing_begin=time.monotonic(),**kwargs)


class AccuracyTests(unittest.TestCase):
    def test_normal_analytic_reference(self):
        result=new(CASES[0]);s=result['score'];self.assertTrue(result['accepted'])
        self.assertAlmostEqual(s['crps'],(math.sqrt(2)-1)/math.sqrt(math.pi),places=9)
        self.assertAlmostEqual(s['nll'],.5*math.log(2*math.pi),places=10)
        self.assertAlmostEqual(s['quantiles']['0.975'],1.959963984540054,places=9)

    def test_moderate_multimodal_tail_and_broad_narrow_scalar_fields_match_reference(self):
        for c in CASES[1:5]:
            s=new(c);r=Posterior(c['pi'],c['mu'],c['sigma'],c['affine'])
            try:
                old=dict(log_normalizer=r.log_normalizer,mean=r.mean,nll=-r.log_pdf(c['target']),median=r.quantile(.5),pit=r.cdf_survival(c['target'])[0])
                for k in('log_normalizer','mean','nll','median','pit'):self.assertAlmostEqual(s['score'][k],old[k],delta=1e-6,msg=c['name']+' '+k)
            finally:r.components.clear();r._cdf_cache.clear()
            self.assertLess(s['work']['vector_points'],20000);self.assertTrue(s['accepted'])

    def test_sharp_curve_diagnostic_is_not_accepted_or_silently_repaired(self):
        c=CASES[5]
        with self.assertRaises(NumericalFailure)as e:new(c)
        self.assertEqual(str(e.exception),'gh_parity');self.assertGreater(e.exception.evidence['mean'],1e-4)
        s=new(c,require_gh=False);self.assertFalse(s['accepted']);self.assertTrue(s['diagnostic_only'])
        self.assertAlmostEqual(s['score']['log_normalizer'],math.log(.5),places=9)

    def test_far_label_sigma_floor_uncapped_support(self):
        c=CASES[6];s=new(c);reference=Posterior(c['pi'],c['mu'],c['sigma'],c['affine'])
        self.assertGreater(s['score']['nll'],100000);self.assertGreater(s['score']['crps'],20)
        self.assertAlmostEqual(s['score']['mean'],reference.mean,places=9);self.assertEqual(s['score']['pit'],1.)

    def test_constant_magnitude_likelihood_and_empty_factors(self):
        c=copy.deepcopy(CASES[2]);c['affine']=[[200.,0.],[-1000.,0.]]
        result=new(c);g=gaussian_score(c['target'],c['pi'],c['mu'],c['sigma'])
        for k in('mean','nll','crps','median','pit'):self.assertAlmostEqual(result['score'][k],g[k],delta=1e-6)
        self.assertLess(result['score']['log_normalizer'],-999.)

    def test_reactivation_and_censor_same_factor_operator(self):
        h=dict(alpha=[.1,-.2],beta=[.3,-.1],v=[[.2,.1],[-.1,.3]],w=[[.4],[.2]],gamma=[.4,-.5],eta=[.8,-.6])
        z=[.2,.5];ctx=[.8];states=[1,1,0,0,1,1]
        c=copy.deepcopy(CASES[2]);c['affine']=factors('C',states,z,ctx,h,5.)
        self.assertEqual(len(c['affine']),5);s=new(c);r=Posterior(c['pi'],c['mu'],c['sigma'],c['affine'])
        self.assertAlmostEqual(s['score']['mean'],r.mean,delta=1e-7)
        self.assertEqual(factors('C',[1]*6,z,ctx,h,5.),factors('T',[1]*6,z,ctx,h,5.))
        self.assertNotEqual(factors('C',states,z,ctx,h,5.),factors('T',states,z,ctx,h,5.))

    def test_error_control_refinement_and_identity_evidence(self):
        s=new(CASES[2],tolerance=1e-8)
        self.assertLess(s['error']['crps_identity'],1e-8);self.assertLess(s['reference_error']['cdf'],1e-8)
        self.assertGreater(s['work']['intervals'],1)

    def test_gradients_log_normalizer_finite_difference(self):
        c=copy.deepcopy(CASES[2]);result=new(c,gradients=True);g=result['gradients'];eps=1e-5
        for field,index in(('mu',2),('log_sigma',2),('intercept',0),('slope',0),('logits',2)):
            left=copy.deepcopy(c);right=copy.deepcopy(c)
            if field=='mu':left['mu'][index]-=eps;right['mu'][index]+=eps
            elif field=='log_sigma':left['sigma'][index]*=math.exp(-eps);right['sigma'][index]*=math.exp(eps)
            elif field in('intercept','slope'):
                j=0 if field=='intercept'else 1;left['affine'][index][j]-=eps;right['affine'][index][j]+=eps
            else:
                a=np.log(np.asarray(c['pi']));b=a.copy();a[index]-=eps;b[index]+=eps
                left['pi']=(np.exp(a)/np.exp(a).sum()).tolist();right['pi']=(np.exp(b)/np.exp(b).sum()).tolist()
            fd=(new(right)['score']['log_normalizer']-new(left)['score']['log_normalizer'])/(2*eps)
            self.assertAlmostEqual(g[field][index],fd,delta=2e-6,msg=field)

    def test_reject_parameter_types_no_sigma_repair(self):
        for key,value in(('pi',[.1]*5),('sigma',[.049]*5),('mu',[math.inf]*5),('affine',[[0.,1.]]*20),('target',True)):
            c=copy.deepcopy(CASES[0]);c[key]=value
            with self.assertRaises(NumericalFailure):new(c)

    def test_deadline_and_work_bounds(self):
        c={k:v for k,v in CASES[0].items()if k!='name'}
        with self.assertRaises(NumericalFailure):score(**c,processing_begin=time.monotonic()-11)
        with self.assertRaises(NumericalFailure):new(CASES[0],budget_seconds=11)

    def test_reference_or_gh_disagreement_cannot_accept(self):
        import reference
        old=reference.hermite
        def shift(*args):v=old(*args);v['mean']+=.01;return v
        with patch.object(reference,'hermite',side_effect=shift):
            with self.assertRaises(NumericalFailure):new(CASES[0])

    def test_rare_far_mass_not_removed_by_density_cutoff(self):
        s=new(CASES[7]);self.assertTrue(s['accepted'])
        g=gaussian_absolute_moments(CASES[7]['pi'],CASES[7]['mu'],CASES[7]['sigma'],CASES[7]['target'])
        self.assertAlmostEqual(s['score']['crps'],g['crps'],places=10)
        self.assertLess(s['reference_error']['mean'],1e-4)
        for k in('absolute_moment','cdf_product'):self.assertAlmostEqual(s['score'][k],g[k],places=10)

    def test_zero_weight_components_permitted(self):
        c=copy.deepcopy(CASES[0]);c['pi']=[1.,0.,0.,0.,0.];c['mu']=[0.,100.,200.,300.,400.]
        s=new(c);self.assertAlmostEqual(s['score']['crps'],(math.sqrt(2)-1)/math.sqrt(math.pi),places=9)


class IndependentCRPSTests(unittest.TestCase):
    def test_zero_hazard_remote_narrow_mode_counterexample(self):
        c=copy.deepcopy(CASES[3]);c['affine']=[]
        diagnostic=missed_mode_diagnostic(c['pi'],c['mu'],c['sigma'],c['affine'],c['target'])
        analytic=gaussian_score(c['target'],c['pi'],c['mu'],c['sigma'])
        v3=new(c)['score']
        closed=gaussian_absolute_moments(c['pi'],c['mu'],c['sigma'],c['target'])
        self.assertAlmostEqual(v3['crps'],closed['crps'],places=9)
        self.assertAlmostEqual(analytic['crps']-diagnostic['original_crps'],.155,places=10)
        self.assertEqual(diagnostic['components'][0]['original_absolute'],0.)
        self.assertGreater(diagnostic['components'][0]['label_split'],399)
        self.assertAlmostEqual(diagnostic['mode_split_absolute_moment']-diagnostic['original_absolute_moment'],.155,places=10)
        for k in('mean','nll','pit'):self.assertAlmostEqual(v3[k],diagnostic[k],places=10)
        self.assertAlmostEqual(v3['cdf_product'],diagnostic['original_cdf_product'],places=9)

    def test_nonzero_hazard_grid_converges_with_explicit_tail_bounds(self):
        c=CASES[3];args={k:v for k,v in c.items()if k!='name'}
        grids=[grid_reference(**args,resolution=n)for n in(20,40,80)]
        v3=new(c)['score']
        errors=[abs(v3['crps']-g['crps'])for g in grids]
        self.assertLess(errors[2],errors[1]);self.assertLess(errors[1],errors[0]);self.assertLess(errors[2],2e-8)
        self.assertLess(grids[-1]['tail_absolute_bound'],1e-30)
        self.assertLess(grids[-1]['tail_probability_bound'],1e-30)
        for k in('log_normalizer','mean','nll','pit','absolute_moment','cdf_product'):
            self.assertAlmostEqual(v3[k],grids[-1][k],delta=2e-8,msg=k)

    def test_moderate_and_multimodal_third_grid_crps(self):
        for c in CASES[1:3]:
            args={k:v for k,v in c.items()if k!='name'}
            grid=grid_reference(**args,resolution=120)
            self.assertAlmostEqual(new(c)['score']['crps'],grid['crps'],delta=8e-6)
            self.assertLess(grid['tail_absolute_bound'],1e-28)

    def test_far_label_analytic_gaussian_moment_not_zero(self):
        c=copy.deepcopy(CASES[6]);c['affine']=[]
        analytic=gaussian_score(c['target'],c['pi'],c['mu'],c['sigma'])
        actual=new(c)['score']
        self.assertAlmostEqual(actual['absolute_moment'],25.,places=10)
        self.assertAlmostEqual(actual['crps'],analytic['crps'],places=10)


class BoundaryTests(unittest.TestCase):
    def test_three_invented_censor_horizons_and_extreme_log_mass(self):
        for edges in(3,11,19):
            c=copy.deepcopy(CASES[2]);c['affine']=[[-40.,0.]for _ in range(edges)]
            s=new(c)
            self.assertTrue(s['accepted']);self.assertLess(s['score']['log_normalizer'],-39*edges)
            self.assertGreater(s['score']['crps'],0.);self.assertLess(s['reference_error']['absolute_moment'],1e-7)

    def test_shift_equivariance_of_operator_and_proper_scores(self):
        c=copy.deepcopy(CASES[2]);shift=100.
        shifted=copy.deepcopy(c);shifted['mu']=[m+shift for m in c['mu']];shifted['target']+=shift
        shifted['affine']=[[a-b*shift,b]for a,b in c['affine']]
        a=new(c)['score'];b=new(shifted)['score']
        for k in('crps','nll','pit','log_normalizer','absolute_moment','cdf_product'):
            self.assertAlmostEqual(a[k],b[k],delta=1e-7,msg=k)
        self.assertAlmostEqual(a['mean']+shift,b['mean'],delta=1e-7)

    def test_compactification_contains_both_infinite_tails(self):
        from scorer import Density
        d=Density([.2]*5,[0.]*5,[1.]*5,[],processing_begin=time.monotonic())
        near=np.asarray([-.999999,.999999])
        self.assertLess(d.real(near)[0],-499999);self.assertGreater(d.real(near)[1],499999)
        self.assertTrue(np.allclose(d.compact(d.real(near)),near,rtol=0,atol=1e-15))


class MissedCDFTransitionTests(unittest.TestCase):
    def test_remote_zero_hazard_modes_expose_pair_integral_failure(self):
        c=CASES[7];d=missed_mode_diagnostic(**{k:v for k,v in c.items()if k!='name'})
        ground=gaussian_absolute_moments(c['pi'],c['mu'],c['sigma'],c['target'])
        self.assertGreater(abs(d['original_cdf_product']-ground['cdf_product']),.23)
        self.assertAlmostEqual(d['mode_split_absolute_moment'],ground['absolute_moment'],places=10)
        self.assertAlmostEqual(d['mode_split_absolute_moment']-d['original_absolute_moment'],.00002,places=10)
        self.assertAlmostEqual(new(c)['score']['crps'],ground['crps'],places=10)

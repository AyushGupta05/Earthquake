"""Invented mathematics, state/censor/time controls and strict saved bindings."""
import copy
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import quad
from scipy.special import expit
from numerical import Posterior,factors,ages,gaussian_score,NumericalFailure
import auditor
from packet_validation import validate,scaler,diagnostics,model_context
from metrics import advance,paired
from invented import fixture


def hazard():return dict(alpha=[.1,-.2],beta=[.3,-.1],v=[[.2,.1],[-.1,.3]],w=[[.4],[.2]],gamma=[.4,-.5],eta=[.8,-.6])


class NumericTests(unittest.TestCase):
    def test_normal_closed_form_all_real_crps(self):
        p=Posterior([.2]*5,[0.]*5,[1.]*5,[]);s=p.score(0.)
        self.assertAlmostEqual(s['crps'],(math.sqrt(2)-1)/math.sqrt(math.pi),places=9)
        self.assertAlmostEqual(s['nll'],.5*math.log(2*math.pi),places=10);self.assertAlmostEqual(s['mean'],0.,places=12)
        self.assertAlmostEqual(s['pit'],.5,places=12);self.assertAlmostEqual(s['median'],0.,places=8)

    def test_non_gaussian_logistic_tilt_against_direct_standard_integrals(self):
        p=Posterior([1.,0.,0.,0.,0.],[0.]*5,[1.]*5,[[0.,2.]])
        norm=quad(lambda x:math.exp(-x*x/2)/math.sqrt(2*math.pi)*float(expit(2*x)),-math.inf,math.inf)[0]
        mean=quad(lambda x:x*math.exp(-x*x/2)/math.sqrt(2*math.pi)*float(expit(2*x)),-math.inf,math.inf)[0]/norm
        self.assertAlmostEqual(p.log_normalizer,math.log(.5),places=9);self.assertAlmostEqual(p.mean,mean,places=9)
        self.assertNotAlmostEqual(p.quantile(.5),p.mean,places=3)
        for x in(-2.,0.,2.):
            direct=quad(lambda v:math.exp(-v*v/2)/math.sqrt(2*math.pi)*float(expit(2*v)),-math.inf,x)[0]/norm
            self.assertAlmostEqual(p.cdf_survival(x)[0],direct,places=8)

    def test_multimodal_non_gaussian_crps_against_grid_cdf(self):
        pi=[.1,.2,.3,.15,.25];mu=[-2.,-1.,0.,2.,3.];sd=[.4,.5,1.,2.,.2];affine=[[.2,.6],[-.5,-.3]]
        p=Posterior(pi,mu,sd,affine);y=.5
        grid=np.linspace(-18,18,40001);pdf=sum(w*np.exp(-.5*((grid-m)/s)**2)/(s*math.sqrt(2*math.pi))for w,m,s in zip(pi,mu,sd))
        pdf*=expit(.2+.6*grid)*expit(-.5-.3*grid);cdf=np.cumsum((pdf[:-1]+pdf[1:])*.5*np.diff(grid));cdf=np.r_[0.,cdf]/cdf[-1]
        reference=float(np.trapezoid((cdf-(grid>=y))**2,grid))
        self.assertAlmostEqual(p.crps(y),reference,delta=.0005);self.assertGreater(p.mean,0.)

    def test_constant_magnitude_likelihood_preserves_base_posterior(self):
        p=Posterior([.2]*5,[-2.,-1.,0.,2.,3.],[1.]*5,[[2.,0.],[-3.,0.]])
        q=gaussian_score(.5,[.2]*5,[-2.,-1.,0.,2.,3.],[1.]*5)
        self.assertAlmostEqual(p.mean,q['mean'],places=9);self.assertAlmostEqual(p.crps(.5),q['crps'],places=8)
        self.assertAlmostEqual(-p.log_pdf(.5),q['nll'],places=9)

    def test_uncapped_far_mode_sigma_floor_and_quadrature_admission(self):
        p=Posterior([.2]*5,[20.]*5,[.05]*5,[])
        self.assertAlmostEqual(p.mean,20.,places=10);self.assertGreater(p.quantile(.975),20.)
        with self.assertRaises(NumericalFailure):Posterior([.1]*5,[0.]*5,[1.]*5,[])
        with self.assertRaises(NumericalFailure):Posterior([.2]*5,[0.]*5,[.049]*5,[])
        with patch('numerical.MAX_EVALUATIONS',1):
            with self.assertRaises(NumericalFailure):Posterior([.2]*5,[0.]*5,[1.]*5,[])

    def test_c_t_initial_run_equality_reset_and_h_time_control(self):
        h=hazard();z=[.2,.5];c=[.8]
        self.assertEqual(factors('C',[1]*6,z,c,h,5.),factors('T',[1]*6,z,c,h,5.))
        self.assertNotEqual(factors('C',[1,0,1,1],z,c,h,5.),factors('T',[1,0,1,1],z,c,h,5.))
        a,b=[1,0,0,1],[0,1,0,1]
        self.assertEqual(factors('H',a,z,c,h,5.)[-1],factors('H',b,z,c,h,5.)[-1])
        self.assertEqual(factors('T',a,z,c,h,5.)[-1],factors('T',b,z,c,h,5.)[-1])
        self.assertNotEqual(factors('C',a,z,c,h,5.)[-1],factors('C',b,z,c,h,5.)[-1])

    def test_censor_reactivation_edges_and_disjoint_prefix(self):
        h=hazard();states=[1,1,0,0,1,1];z=[.2,.3];c=[.1]
        f=factors('C',states,z,c,h,5.);self.assertEqual(len(f),5);self.assertEqual(ages(states),[1,2,1,2,1,2])
        self.assertEqual(factors('C',states[:3],z,c,h,5.),f[:2])
        self.assertEqual(len(factors('C',[1],z,c,h,5.)),0)
        constant=dict(alpha=[0.,0.],beta=[0.,0.],v=[[0.,0.],[0.,0.]],w=[[0.],[0.]],gamma=[0.,0.],eta=[0.,0.])
        p=Posterior([.2]*5,[0.]*5,[1.]*5,factors('C',[1]*4,z,c,constant,0.))
        self.assertAlmostEqual(p.log_normalizer,-3*math.log(2),places=10)


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result,cls.packet=fixture();cls.report=auditor.audit(cls.result,cls.packet,processing_begin=time.monotonic())

    def test_complete_ten_fit_false_gate_independent_reference(self):
        self.assertEqual(self.report['status'],'pass');self.assertFalse(self.report['advance']['pass_all'])
        self.assertEqual(len(self.report['fits']),10);self.assertEqual(len(self.report['advance']['checks']),24)
        self.assertEqual(sum(len(f['predictions'])for f in self.report['fits']),660)

    def test_packet_roles_no_test_common_unknown_and_state_tamper(self):
        for mutate in(lambda p:p['rows'][65].update(partition='DEV'),lambda p:p['rows'][41].update(partition='TEST'),lambda p:p['rows'][41].update(group=-1),
                      lambda p:p['rows'][41]['horizons'][0]['states'].__setitem__(0,True),lambda p:p['rows'][41]['horizons'][0]['run_ages'].__setitem__(1,True),
                      lambda p:p['rows'][41]['horizons'][1]['ratios'].__setitem__(0,9.),lambda p:p.update(fit_authorized=True)):
            p=copy.deepcopy(self.packet);mutate(p)
            with self.assertRaises((NumericalFailure,ValueError)):validate(p)

    def test_scalers_train_only_and_float32_model_context(self):
        p=copy.deepcopy(self.packet);roles=validate(p);original=scaler(p,roles)
        for i in roles['DEV']:
            p['rows'][i]['initial']['context'][9]=100.
            for h in p['rows'][i]['horizons']:h['context'][10]=100.
        changed=scaler(p,roles)
        for k in original:np.testing.assert_array_equal(original[k],changed[k])
        self.assertEqual(model_context(self.packet['rows'][41]['initial']['context'],original),self.result['fits'][2]['predictions'][0]['numerical']['c'])

    def test_activity_reactivation_censor_diagnostics_and_immutable_delta(self):
        roles=validate(self.packet);d=diagnostics(self.packet,roles)
        self.assertEqual(d['TRAIN']['horizons']['5'],dict(off=5,on=0,active_censored=60));self.assertEqual(d['DEV']['horizons']['1']['active_censored'],22)
        p=copy.deepcopy(self.packet);p['rows'][41]['horizons'][1]['context'][8]=.25
        with self.assertRaises(NumericalFailure):validate(p)

    def test_labels_order_horizon_rate_family_receiver_before_math(self):
        for key,value in(('ordinal',True),('target',6.5),('horizon',5),('rate',[200,2]),('family','12Z'),('receiver',[1.,0.,0.])):
            r=copy.deepcopy(self.result);r['fits'][0]['predictions'][0][key]=value
            with patch.object(auditor,'numerical_record',side_effect=AssertionError('math')):out=auditor.audit(r,self.packet,processing_begin=time.monotonic())
            self.assertEqual(out['status'],'fail');self.assertFalse(out['advance']['pass_all'])

    def test_numeric_tamper_retains_fresh_integral_discrepancy(self):
        row=self.packet['rows'][41];r=copy.deepcopy(self.result['fits'][2]['predictions'][0]['numerical']);r['integrals']['gh64']['mean']+=.1
        with self.assertRaises(NumericalFailure)as error:auditor.numerical_record(r,'H',row,row['horizons'][0],scaler(self.packet,validate(self.packet)),row['mw'],self.result['fits'][2]['mref'],{})
        self.assertIsNotNone(error.exception.evidence);self.assertIn('integrals',error.exception.evidence)

    def test_context_amplitude_states_torch_parity_and_float32_tamper(self):
        row=self.packet['rows'][41];s=scaler(self.packet,validate(self.packet));mref=self.result['fits'][2]['mref']
        for mutate in(lambda r:r['c'].__setitem__(0,.1),lambda r:r['z'].__setitem__(-1,1.),lambda r:r['states'].__setitem__(1,0),lambda r:r['torch_errors'].update({'128':.001})):
            r=copy.deepcopy(self.result['fits'][2]['predictions'][0]['numerical']);mutate(r)
            with self.assertRaises(NumericalFailure):auditor.numerical_record(r,'H',row,row['horizons'][0],s,row['mw'],mref,{})

    def test_history_mref_capacity_and_incomplete_no_score(self):
        for mutate in(lambda r:r.update(status='incomplete'),lambda r:r['capacity']['counts'].update(C=5126),lambda r:r['fits'][0].update(mref=0.),
                      lambda r:r['fits'][0]['history'][0].update(sequence_nll=1.),lambda r:r['fits'][0]['history'][1].update(update=1)):
            r=copy.deepcopy(self.result);mutate(r)
            with patch.object(auditor,'numerical_record',side_effect=AssertionError('math')):out=auditor.audit(r,self.packet,processing_begin=time.monotonic())
            self.assertEqual(out['status'],'fail')

    def test_all24_guards_and_no_action_seed_horizon_selection(self):
        fits=[]
        for seed in(20261012,20261013):
            for arm in('B','F','H','T','C'):
                m=dict(nll=2.,crps=2.,tail_mae_5_5=.5,mae=.3,medae=.3,lower_mae=.2,lower_medae=.2,cvar95=1.,maximum=1.)
                if arm=='C':m.update(nll=1.,crps=1.,tail_mae_5_5=.47)
                fits.append(dict(seed=seed,arm=arm,status='complete',metrics={str(h):dict(m)for h in(1,3,5)}))
        self.assertTrue(advance(fits)['pass_all'])
        for key,value in(('mae',.31),('medae',.31),('lower_mae',.21),('lower_medae',.21),('cvar95',1.1),('maximum',1.1),('tail_mae_5_5',.49),('nll',2.),('crps',2.)):
            bad=copy.deepcopy(fits);bad[-1]['metrics']['1'][key]=value;self.assertFalse(advance(bad)['pass_all'])

    def test_small_group_intervals_and_wrong_pair_bindings(self):
        p=self.report['fits'][0]['predictions'][:3];intervals=paired(p,p)
        self.assertEqual(intervals['nll']['status'],'unsupported');self.assertIsNone(intervals['nll']['interval'])
        wrong=copy.deepcopy(p);wrong[0]['target']+=.1
        with self.assertRaises(ValueError):paired(p,wrong)

    def test_deadline_and_private_output_cap_never_promote(self):
        out=auditor.audit(self.result,self.packet,processing_begin=time.monotonic()-1000)
        self.assertEqual(out['status'],'fail');self.assertFalse(out['advance']['pass_all'])
        with patch.object(auditor,'MAX_OUTPUT',15000):out=auditor.audit(self.result,self.packet,processing_begin=time.monotonic())
        self.assertEqual(out['status'],'fail');self.assertFalse(out['advance']['pass_all']);self.assertLessEqual(len(auditor.canonical(out)),15000)

    def test_stored_scores_metrics_strata_extremes_diagnostics_and_gate(self):
        r=copy.deepcopy(self.result);r['fits'][0]['predictions'][0]['crps']+=.1;r['fits'][0]['metrics']['1']['mae']+=.1
        r['fits'][0]['strata']['1']['rates'][0]['metrics']['mae']+=.1;r['fits'][0]['extreme_cases']=[r['fits'][0]['predictions'][0]]
        r['diagnostics']['DEV']['horizons']['1']['off']=1;r['advance']['pass_all']=True;r['comparisons'][0]['intervals']['nll']['delta']=.1
        out=auditor.audit(r,self.packet,processing_begin=time.monotonic())
        self.assertEqual(set(out['reasons']),{'stored_score','stored_metrics','stored_strata','stored_extreme_cases','stored_diagnostics','stored_advance','stored_comparisons'})
        self.assertFalse(out['advance']['pass_all'])

    def test_independent_gh_disagreement_retained_and_no_normal_fallback(self):
        row=self.packet['rows'][41];record=self.result['fits'][2]['predictions'][0]['numerical'];s=scaler(self.packet,validate(self.packet))
        import numerical
        original=numerical.hermite
        def shifted(*args):
            v=original(*args);v['mean']+=.01;return v
        with patch.object(auditor,'hermite',side_effect=shifted):
            with self.assertRaises(NumericalFailure)as error:auditor.numerical_record(record,'H',row,row['horizons'][0],s,row['mw'],self.result['fits'][2]['mref'],{})
        self.assertGreater(error.exception.evidence['errors']['mean'],1e-4)

    def test_failed_verification_blocks_recomputed_passing_guard(self):
        # The scorer/gate mathematics are tested separately. This composition
        # seam verifies that a positive diagnostic can never authorize a failed audit.
        r=copy.deepcopy(self.result);r['diagnostics']['DEV']['common']=21
        guard=dict(pass_all=True,checks=[dict(seed=s,horizon=h,comparator=a,tail=True,proper=True,bulk_worst={k:True for k in('mae','medae','lower_mae','lower_medae','cvar95','maximum')},passed=True)for s in(20261012,20261013)for h in(1,3,5)for a in('B','F','H','T')])
        with patch.object(auditor,'advance',return_value=guard):out=auditor.audit(r,self.packet,processing_begin=time.monotonic())
        self.assertEqual(out['status'],'fail');self.assertEqual(out['advance'],dict(pass_all=False,checks=[]))
        self.assertEqual(out['recomputed_advance'],guard);self.assertIn('stored_diagnostics',out['reasons'])


    def test_fresh_per_record_coverage_builtin_bool_for_covered_uncovered(self):
        for target,truth in((0.,True),(10.,False)):
            base=gaussian_score(target,[.2]*5,[0.]*5,[1.]*5)
            tilted=Posterior([.2]*5,[0.]*5,[1.]*5,[])
            try:post=tilted.score(target)
            finally:tilted.components.clear();tilted._cdf_cache.clear()
            for scores in(base,post):
                for level in(50,80,95):
                    fresh=scores['coverage_%d'%level]
                    self.assertIs(type(fresh),bool);self.assertIs(fresh,truth)
                    self.assertTrue(auditor.close(truth,fresh,0))
                    for malformed in(int(truth),float(truth),str(truth),None,np.bool_(truth)):
                        self.assertFalse(auditor.close(malformed,fresh))
                    self.assertFalse(auditor.close(not truth,fresh))

    def test_complete_replay_preserves_bool_predictions_float_coverage_averages(self):
        for fit in self.report['fits']:
            for prediction in fit['predictions']:
                for level in(50,80,95):self.assertIs(type(prediction['coverage_%d'%level]),bool)
            for panel in fit['metrics'].values():
                for level in(50,80,95):self.assertIs(type(panel['coverage_%d'%level]),float)
        self.assertEqual(self.report['schema'],'earthquake-TRAIN115-renewal-score-audit-v3')
        self.assertEqual(self.report['status'],'pass');self.assertFalse(self.report['advance']['pass_all'])
        self.assertFalse(auditor.close(True,1.));self.assertFalse(auditor.close(False,0.))

    def test_saved_per_record_malformed_coverage_cannot_pass(self):
        r=copy.deepcopy(self.result);first=r['fits'][0]['predictions'][0]
        first.update(coverage_50=0.,coverage_80='False',coverage_95=1.)
        out=auditor.audit(r,self.packet,processing_begin=time.monotonic())
        self.assertEqual(out['status'],'fail');self.assertIn('stored_score',out['reasons'])
        self.assertEqual(out['advance'],dict(pass_all=False,checks=[]))

    def test_scalar_score_type_does_not_relax_bool_false_or_numeric_tolerance(self):
        self.assertTrue(auditor.close(False,False));self.assertTrue(auditor.close(True,True))
        self.assertFalse(auditor.close(True,False));self.assertFalse(auditor.close(False,True))
        self.assertTrue(auditor.close(1.00005,1.));self.assertFalse(auditor.close(1.0002,1.))
        self.assertFalse(auditor.close('1.0',1.));self.assertFalse(auditor.close(True,1.))

"""Invented numeric fixtures only; whole nested grids mock optimizer/predictor."""
import copy
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr
from scipy.stats import norm
import adequacy as study
import fit as estimator
import metrics
import numerics


def fixture():
    coverage=[];events=[]
    for slot in range(65):
        common=slot<20
        status='available' if common else 'NON_COMMON' if slot<41 else 'DEFERRED_DEV'
        coverage.append({'slot':slot,'partition':'TRAIN' if slot<41 else 'DEV','common':common,
                         'horizon_statuses':[status]*3})
        if not common:continue
        mw=6.2 if slot<10 else 4.5
        horizons=[]
        for h in (1,3,5):
            y=.1+.4*mw+.2*math.log10(h)+.03*math.sin(slot)
            peak=10**y
            horizons.append({'seconds':h,'status':'available','features':{
                'y':y,'L':0.,'censored':False,'u':float(h),'selected_component':0,
                'noise_floor':True,'peak':peak,'noise':1.}})
        events.append({'slot':slot,'mw':mw,'group':'g'+str(slot%5),'horizons':horizons})
    return {'schema':study.SCHEMA,'coverage':coverage,'events':events}


def predictions_for(events):
    out={h:[] for h in ('1','3','5')}
    for e in events:
        for h in out:
            out[h].append({'slot':e['slot'],'group':e['group'],'mw':e['mw'],
                           'model':{'mean':e['mw']+.01,'median':e['mw']+.01,'nll':1.,'crps':.01,'numerical_error':0.},
                           'prior':{'mean':5.35,'median':5.35,'nll':2.,'crps':.7,'numerical_error':0.}})
    return out


def fake_fit(events,penalty,deadline):
    prior,scaler=estimator.statistics(events)
    return {'parameters':[0.,0.,0.,1.],'prior':prior,'scaler':scaler,'lambda':float(penalty),
            'training_groups':sorted({e['group'] for e in events}),'training_slots':[e['slot'] for e in events],
            'objective':0.,'iterations':1,'function_evaluations':1,'success':True,'elapsed_seconds':0.}


def fake_evaluate(events,model,deadline,score=True):
    return predictions_for(events)


class SchemaTests(unittest.TestCase):
    def test_valid_copy_no_input_mutation(self):
        d=fixture();v=study.validate_input(d);self.assertEqual(d,v);self.assertIsNot(d,v)
    def test_fixed_common_missing_is_retained_and_no_fit(self):
        d=fixture();d['coverage'][0]['horizon_statuses'][1]='BAD_WINDOW'
        d['events'][0]['horizons'][1].update(status='BAD_WINDOW',features=None)
        with patch('adequacy.estimator.fit',side_effect=AssertionError('fit forbidden')):
            r=study.run_outer(d)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(r['fits'],[])
        self.assertEqual(r['coverage'][0]['horizon_statuses'][1],'BAD_WINDOW')
    def test_extra_and_bool_rejected(self):
        for change in (lambda d:d.update(extra=1),lambda d:d['events'][0].update(mw=True),
                       lambda d:d['coverage'][0].update(slot=False),
                       lambda d:d['events'][0]['horizons'][0]['features'].update(y=float('nan'))):
            d=fixture();change(d)
            with self.assertRaises(ValueError):study.validate_input(d)
    def test_DEV_features_and_dropped_common_rejected(self):
        d=fixture();d['coverage'][41]['horizon_statuses']=['available']*3
        with self.assertRaises(ValueError):study.validate_input(d)
        d=fixture();d['events'].pop()
        with self.assertRaises(ValueError):study.validate_input(d)
    def test_scalar_floor_age_noise_tamper_rejected(self):
        for key,val in [('L',1.),('censored',True),('noise',2.),('u',.1),('noise_floor',1),('peak',0.)]:
            d=fixture();d['events'][0]['horizons'][0]['features'][key]=val
            with self.assertRaises(ValueError):study.validate_input(d)
    def test_unavailable_values_forbidden(self):
        d=fixture();d['coverage'][0]['horizon_statuses'][0]='BAD_NOISE';d['events'][0]['horizons'][0]['status']='BAD_NOISE'
        with self.assertRaises(ValueError):study.validate_input(d)
    def test_same_component_noise_and_cumulative_peak_checks(self):
        d=fixture();f=d['events'][0]['horizons'][2]['features'];f['noise']=2.;f['noise_floor']=False
        f['L']=-math.log10(2);f['y']=math.log10(f['peak']/2)
        with self.assertRaises(ValueError):study.validate_input(d)
    def test_cutoff_age_increments(self):
        d=fixture();d['events'][0]['horizons'][1]['features']['u']=2.9
        with self.assertRaises(ValueError):study.validate_input(d)


class FitTests(unittest.TestCase):
    def test_group_weight_and_horizon_weights(self):
        es=fixture()['events'];w=estimator.event_weights(es)
        for g in {e['group'] for e in es}:self.assertAlmostEqual(sum(w[i] for i,e in enumerate(es) if e['group']==g),.2)
        p,s=estimator.statistics(es);x,y,l,c,hw=estimator.matrix(es,p,s)
        self.assertAlmostEqual(hw.sum(),1.);self.assertEqual(len(hw),3*len(es))
        self.assertAlmostEqual(float(hw@x[:,1]),0.,places=12);self.assertAlmostEqual(float(hw@x[:,2]),0.,places=12)
    def test_held_group_labels_features_cannot_change_fit_statistics(self):
        d=fixture();train=[e for e in d['events'] if e['group']!='g0'];held=[e for e in d['events'] if e['group']=='g0']
        before=estimator.statistics(train)
        for e in held:e['mw']=8.;e['horizons'][0]['features']['u']=.25
        self.assertEqual(before,estimator.statistics(train))
    def test_prior_SD_floor_and_constant_age(self):
        es=fixture()['events'][:3]
        for e in es:
            e['mw']=6.
            for h in e['horizons']:h['features']['u']=1.
        prior,scaler=estimator.statistics(es);self.assertEqual(prior['sd'],.5);self.assertEqual(scaler['age_sd'],0.)
        self.assertTrue(np.all(estimator.matrix(es,prior,scaler)[0][:,2]==0))
    def test_exact_censor_gradient(self):
        es=fixture()['events'];es[0]['horizons'][0]['features'].update(y=0.,L=0.,censored=True)
        p,s=estimator.statistics(es);x,y,l,c,w=estimator.matrix(es,p,s);t=np.array([2.,.3,.1,math.log(.5)])
        v,g=estimator.objective(t,x,y,l,c,w,.1,time.monotonic()+10)
        for i in range(4):
            delta=np.zeros(4);delta[i]=1e-6
            a=estimator.objective(t+delta,x,y,l,c,w,.1,time.monotonic()+10)[0]
            b=estimator.objective(t-delta,x,y,l,c,w,.1,time.monotonic()+10)[0]
            self.assertAlmostEqual(g[i],(a-b)/2e-6,places=5)
    def test_one_tiny_invented_fit(self):
        es=fixture()['events'];r=estimator.fit(es,.1,time.monotonic()+10)
        self.assertTrue(r['success']);self.assertGreaterEqual(r['parameters'][1],0.)
        self.assertGreaterEqual(r['parameters'][2],0.);self.assertGreaterEqual(r['parameters'][3],.1)
        self.assertLess(r['elapsed_seconds'],10.)
    def test_deadline_and_optimizer_nonconvergence(self):
        with self.assertRaises(TimeoutError):estimator.fit(fixture()['events'],0.,time.monotonic()-1)
        class Failed:
            success=False;x=np.zeros(4);fun=0.
        with patch('fit.minimize',return_value=Failed()):
            with self.assertRaises(ArithmeticError):estimator.fit(fixture()['events'],0.,time.monotonic()+10)


class PosteriorTests(unittest.TestCase):
    def test_normal_posterior_reference_density_and_moments(self):
        prior={'mean':6.,'sd':.8};scaler={'age_mean':0.,'age_sd':1.};f={'y':2.,'L':0.,'censored':False,'u':1.}
        p=numerics.posterior([1.,.5,.2,.3],prior,scaler,f,time.monotonic()+10)
        expected_mean=6+.8*.5/(.3**2+.5**2);expected_sd=.8*.3/math.sqrt(.3**2+.5**2)
        self.assertAlmostEqual(p.mean,expected_mean);self.assertAlmostEqual(p.sd,expected_sd)
        self.assertAlmostEqual(p.logpdf(6.),norm.logpdf(6.,expected_mean,expected_sd))
        self.assertGreater(p.score(6.)['crps'],0.)
    def test_censor_all_real_normalization_mean_and_crps(self):
        p=numerics.CensoredPosterior(6.,.8,.3,.5,.4,-.2,time.monotonic()+30)
        z=ndtr((-.2-.3)/math.hypot(.5,.4))
        def raw(m):return norm.pdf(m,6,.8)*ndtr((-.2-.3-.5*(m-6)/.8)/.4)/z
        mass=quad(raw,-np.inf,np.inf,epsabs=1e-10)[0]
        mean=quad(lambda m:m*raw(m),-np.inf,np.inf,epsabs=1e-10)[0]
        self.assertAlmostEqual(mass,1.,places=8);self.assertAlmostEqual(mean,p.mean,places=8)
        for m in (5.,6.,7.):self.assertAlmostEqual(p.cdf(m),quad(raw,-np.inf,m)[0],places=7)
        result=p.score(6.);self.assertLess(result['numerical_error'],1e-4);self.assertGreater(result['crps'],0.)
        self.assertLess(p.mean,6.);self.assertLess(p.median(),6.)
    def test_far_tail_censor_no_truncation_or_clip(self):
        p=numerics.CensoredPosterior(6.,1.,0.,2.,.1,-80.,time.monotonic()+30)
        self.assertLess(p.mean,-30.);self.assertTrue(math.isfinite(p.logpdf(6.)))
        self.assertLess(p._mass_error,1e-4);self.assertGreater(p.sd,0.)
        self.assertAlmostEqual(p.cdf(p.median()),.5,places=7)
    def test_zero_slope_censor_returns_prior(self):
        p=numerics.CensoredPosterior(6.,.8,2.,0.,.3,0.,time.monotonic()+30)
        self.assertAlmostEqual(p.mean,6.);self.assertAlmostEqual(p.sd,.8)
        self.assertAlmostEqual(p.score(6.)['crps'],numerics.normal_crps(6.,6.,.8),places=6)
    def test_expired_numerics_rejected(self):
        with self.assertRaises(TimeoutError):numerics.CensoredPosterior(6.,.8,2.,1.,.3,0.,time.monotonic()-1)
    def test_quadrature_failure_is_unknown(self):
        with patch('numerics.quad',return_value=(1.,.01)):
            with self.assertRaises(ArithmeticError):numerics.integrate(lambda x:x,0.,1.,time.monotonic()+10)


class MetricTests(unittest.TestCase):
    def test_fractional_CVaR_and_weighted_median(self):
        self.assertAlmostEqual(metrics.cvar95(np.array([10.,4.,0.]),np.array([.03,.07,.9])),7.6)
        self.assertEqual(metrics.weighted_median(np.array([1.,2.,3.]),np.array([.2,.3,.5])),2.)
    def test_subset_weights_renormalize_original_weights(self):
        rows=predictions_for(fixture()['events'])['1'][:4]
        for r in rows:r['group']='a';r['mw']=4.
        rows[0]['mw']=6.;rows[0]['model']['mean']=7.
        rows[3]['group']='b';rows[3]['mw']=6.;rows[3]['model']['mean']=9.
        out=metrics.summarize(rows,'model');self.assertAlmostEqual(out['high5_5']['mae'],2.5)
    def test_gate_requires_every_score_and_horizon(self):
        ps=predictions_for(fixture()['events']);m={h:{a:metrics.summarize(rs,a) for a in ('model','prior')} for h,rs in ps.items()}
        self.assertTrue(metrics.observed_gate(m)['passed'])
        for key in ('nll','crps','mae','medae','cvar95','maximum'):
            bad=copy.deepcopy(m);bad['3']['model'][key]=bad['3']['prior'][key]+.1
            self.assertFalse(metrics.observed_gate(bad)['passed'])
    def test_fixed_paired_group_bootstrap(self):
        rows=predictions_for(fixture()['events']);d=time.monotonic()+20
        a=metrics.bootstrap(rows,d,numerics.check_deadline);b=metrics.bootstrap(rows,d,numerics.check_deadline)
        self.assertEqual(a,b);self.assertEqual(a['replicates'],1000)
        self.assertEqual(a['delta_model_minus_prior']['1']['nll']['quantiles_2_5_50_97_5'],[-1.,-1.,-1.])


class OrchestrationTests(unittest.TestCase):
    def test_folds_label_independent_and_group_intact(self):
        es=fixture()['events'];a=study.folds(es,5)
        for e in es:e['mw']=8.
        self.assertEqual(a,study.folds(es,5));self.assertEqual(set(a.values()),set(range(5)))
    def test_105_outer_mocked_fits_then_separate26_gate(self):
        d=fixture()
        with patch('adequacy.estimator.fit',side_effect=fake_fit) as f,patch('adequacy.evaluate',side_effect=fake_evaluate),patch('adequacy.risk.bootstrap',return_value={'invented_orchestration_only':True}):
            r=study.run_outer(d);self.assertEqual(f.call_count,105);self.assertEqual(r['status'],'complete')
            self.assertTrue(r['gate']['passed']);self.assertEqual(r['full_TRAIN_fits'],0)
            self.assertTrue(all(c['lambda']==100. for c in r['choices']))
            final=study.continue_train(d,r);self.assertEqual(f.call_count,131)
            self.assertEqual(final['status'],'complete');self.assertEqual(len(final['fits']),26)
    def test_no_held_group_in_inner_or_outer_fitting(self):
        d=fixture();outer=study.folds(d['events'],5)
        with patch('adequacy.estimator.fit',side_effect=fake_fit),patch('adequacy.evaluate',side_effect=fake_evaluate),patch('adequacy.risk.bootstrap',return_value={}):r=study.run_outer(d)
        for rec in r['fits']:
            oi=int(rec['role'][5]);self.assertTrue(all(outer[g]!=oi for g in rec['training_groups']))
            if 'inner' in rec['role']:
                ii=int(rec['role'][-1]);training=[e for e in d['events'] if outer[e['group']]!=oi];inner=study.folds(training,4)
                self.assertTrue(all(inner[g]!=ii for g in rec['training_groups']))
    def test_failed_fit_stops_and_no_continue(self):
        with patch('adequacy.estimator.fit',side_effect=ArithmeticError('invented_failure')) as f:r=study.run_outer(fixture())
        self.assertEqual(f.call_count,1);self.assertEqual(r['status'],'incomplete');self.assertEqual(r['fits'][0]['status'],'failed')
        with self.assertRaises(ValueError):study.continue_train(fixture(),r)
    def test_deadline_before_fit(self):
        with self.assertRaises(TimeoutError):study.run_outer(fixture(),deadline=time.monotonic()-1)
    def test_continuation_tamper_rejected(self):
        d=fixture()
        with patch('adequacy.estimator.fit',side_effect=fake_fit),patch('adequacy.evaluate',side_effect=fake_evaluate),patch('adequacy.risk.bootstrap',return_value={}):r=study.run_outer(d)
        r['gate']['passed']=False
        with self.assertRaises(ValueError):study.continue_train(d,r)
        d['events'][0]['mw']=7.
        with self.assertRaises(ValueError):study.continue_train(d,r)
    def test_continuation_cannot_reset_outer_deadline(self):
        d=fixture()
        with patch('adequacy.estimator.fit',side_effect=fake_fit),patch('adequacy.evaluate',side_effect=fake_evaluate),patch('adequacy.risk.bootstrap',return_value={}):r=study.run_outer(d)
        r['source_deadline']=time.monotonic()-1
        r.pop('result_hash');r=study.seal(r)
        with self.assertRaises(TimeoutError):study.continue_train(d,r)
    def test_public_no_rows_labels_groups_pins(self):
        d=fixture();d['events'][0]['horizons'][0].update(status='BAD_WINDOW',features=None);d['coverage'][0]['horizon_statuses'][0]='BAD_WINDOW'
        r=study.run_outer(d);pub=study.public_summary(r)
        self.assertEqual(pub['fit_attempts'],0);self.assertEqual(pub['original_horizon_cells'],195)
        self.assertFalse(any(k in pub for k in ('predictions','coverage','input_hash','result_hash','fits','groups','mw')))


if __name__=='__main__':unittest.main()

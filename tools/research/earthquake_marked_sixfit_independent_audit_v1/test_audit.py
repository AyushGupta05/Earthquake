"""Meaningful invented tests. No real inputs, producer imports or training."""
import copy,json,math,time,unittest
from unittest.mock import patch
import numpy as np
from scipy.integrate import quad
from scipy.special import logsumexp
import auditor,math_core as c,packet,transport as tx,metrics,fixtures as f

class MathTests(unittest.TestCase):
 def prior(self):return(np.full(5,-math.log(5)),np.linspace(-1,1,5),np.full(5,.8))
 def test_cdf_integral_crps(self):
  m=c.Mixture(*self.prior());self.assertAlmostEqual(m.crps(.3),m.integral_crps(.3),places=8)
 def test_distant_small_mode(self):
  m=c.Mixture(np.log(np.asarray([.998,.0005,.0005,.0005,.0005])),np.asarray([0.,100000.,-100000.,10.,-10.]),np.ones(5));self.assertAlmostEqual(m.crps(1.),m.integral_crps(1.),places=6)
 def test_zero_magnitude_coefficients(self):
  prior=self.prior();facts=[[np.zeros(3),np.zeros(3),np.ones(3),np.ones(3)]];m=c.complete(prior,facts,np.zeros((12,3)),'P',c.Budget());np.testing.assert_allclose(m.logw,prior[0],atol=1e-14);np.testing.assert_array_equal(m.mu,prior[1])
 def test_completion_against_independent_density(self):
  prior=self.prior();facts=[[np.zeros(3),np.full(3,.7),np.full(3,.6),np.asarray([.2,.4,.9])]];m=c.complete(prior,facts,np.zeros((12,3)),'P',c.Budget())
  def logjoint(x):return float(logsumexp(prior[0]-.5*((x-prior[1])/prior[2])**2-np.log(prior[2])-.5*math.log(2*math.pi)))-.5*float(np.sum(((facts[0][3]-.7*x)/.6)**2))-3*math.log(.6)-1.5*math.log(2*math.pi)
  z=quad(lambda x:math.exp(logjoint(x)),-math.inf,math.inf,epsabs=1e-11)[0];mean=quad(lambda x:x*math.exp(logjoint(x)),-math.inf,math.inf,epsabs=1e-11)[0]/z;self.assertAlmostEqual(m.logz,math.log(z),places=9);self.assertAlmostEqual(m.mean(),mean,places=9)
 def test_shared_noise_is_not_redrawn(self):
  nu=np.zeros((12,3));nu[:6]=-.9;nu[6:]=.9;fact=[np.zeros(3),np.ones(3),np.full(3,.3),np.ones(3)];shared=c.complete(self.prior(),[fact,fact],nu,'S',c.Budget());first=c.complete(self.prior(),[fact],nu,'S',c.Budget());redrawn=0.
  for i in range(12):
   for j in range(12):
    # Independent nuisance redraw supports 144 pairs, unlike the shared 12.
    z=quad(lambda x:math.exp(-first.nll(x))*math.exp(-.5*float(np.sum(((fact[3]-x-nu[j])/.3)**2)))/(math.sqrt(2*math.pi)*.3)**3,-8,8,epsabs=1e-7)[0];redrawn+=z/144
  self.assertGreater(abs(shared.logz-(first.logz+math.log(redrawn))),.01)
 def test_normalization_noise_weights(self):
  m=c.complete(self.prior(),[],np.zeros((12,3)),'S',c.Budget());self.assertEqual(len(m.mu),60);np.testing.assert_allclose(m.noise,np.full(12,1/12),atol=1e-15)
 def test_no_double_prior_or_first_mark(self):
  prior=self.prior();one=[np.zeros(3),np.ones(3),np.ones(3),np.ones(3)];a=c.complete(prior,[one],np.zeros((12,3)),'P',c.Budget());b=c.complete(prior,[one,one],np.zeros((12,3)),'P',c.Budget());self.assertGreater(abs(a.mean()-b.mean()),.05)
 def test_quarter_previous_zero(self):
  coeff=np.zeros((3,6));coeff[:,4]=1.;facts=c.factors(np.full((2,3),2.),coeff,5.);np.testing.assert_array_equal(facts[0][0],np.zeros(3));np.testing.assert_array_equal(facts[1][0],np.full(3,2.))
 def test_quantiles_probability_all_real(self):
  m=c.Mixture(*self.prior())
  for q in c.Q:self.assertAlmostEqual(m.cdf(m.quantile(q)),q,places=10)
 def test_coverage_builtin_bool(self):
  x=c.Mixture(*self.prior()).scores(.1);self.assertIs(type(x['coverage_95']),bool)
 def test_softplus_exact_threshold(self):
  x=np.asarray([-100.,-1.,0.,20.,20.0001]);out=c.softplus(x);self.assertGreater(out[3],20.);self.assertEqual(out[4],x[4])
 def test_softplus_ambiguous_interval(self):
  with self.assertRaises(c.AuditFailure):c.softplus(np.asarray([20.]),np.asarray([1e-14]))
 def test_large_integer_cannot_be_array(self):
  with self.assertRaises(c.AuditFailure):c.array(np.asarray([2**60],dtype=np.int64),(1,))
 def test_budget_deadline(self):
  with self.assertRaises(c.AuditFailure):c.Budget(time.monotonic()-11)
 def test_budget_points(self):
  with self.assertRaises(c.AuditFailure):c.Budget().charge(1_000_001,0)
 def test_unresolved_nn_bound(self):
  with self.assertRaises(c.AuditFailure):c.bound_ok(np.ones(1),np.ones(1))
 def test_nn_torch_float64_operational_bound(self):
  import torch
  rng=np.random.default_rng(4)
  for K in(0,2):
   p=f.state(K,3,'P')
   for key in p:
    if key.startswith('prior.'):p[key]=np.asarray(rng.normal(0,.15,p[key].shape),dtype=np.float64)
   z=np.asarray(rng.normal(size=K));result,bounds=c.prior_forward(z,p,K)
   t={k:torch.from_numpy(v.copy())for k,v in p.items()};x=torch.from_numpy(z.copy());x=t['prior.first.weight']@x+t['prior.first.bias']if K else t['prior.first_bias'];x=torch.nn.functional.silu(x);x=torch.nn.functional.silu(t['prior.second.weight']@x+t['prior.second.bias']);out=t['prior.head.weight']@x+t['prior.head.bias'];logits=torch.cat((out[:4],torch.zeros(1,dtype=torch.float64)));actual=(torch.log_softmax(logits,0).numpy(),out[4:9].numpy(),(.05+torch.nn.functional.softplus(out[9:])).numpy())
   for a,b,e in zip(actual,result,bounds):c.compare(a,b,e)
 def test_torch_softplus_positive_negative_twenty(self):
  import torch
  x=np.asarray([-40.,-1.,0.,19.99999,20.,20.00001,50.]);np.testing.assert_allclose(c.softplus(x),torch.nn.functional.softplus(torch.from_numpy(x)).numpy(),rtol=0,atol=8*np.finfo(float).eps*(1+abs(x)).max())

class CustodyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.p=f.packet_fixture();cls.ad=f.admission_fixture(cls.p);cls.cp=f.checkpoint_fixture(cls.ad);cls.score=f.score_fixture(cls.p,cls.ad,cls.cp);cls.auth=f.authority_fixture(cls.p,cls.ad,cls.cp,cls.score)
 def test_packet_all_roles(self):self.assertEqual({k:len(v)for k,v in packet.validate(self.p).items()},{'TRAIN':65,'DEV':22})
 def test_train_only_schema(self):
  p=copy.deepcopy(self.p);p['rows'][91]['precontext'][8]+=1000.;p['rows'][91]['mw']+=.5;self.assertTrue(auditor.close(packet.schema(p,packet.validate(p)),self.ad['schema']))
 def test_false_static_prior(self):
  p=copy.deepcopy(self.p);p['rows'][0]['precontext'][8]+=1.;self.assertFalse(auditor.close(packet.schema(p,packet.validate(p)),self.ad['schema']))
 def test_censor_reject_no_deletion(self):
  p=copy.deepcopy(self.p);p['rows'][0]['horizons'][0]['censor'][0,0]=1
  with self.assertRaises(c.AuditFailure):packet.validate(p)
 def test_prefix_tamper(self):
  p=copy.deepcopy(self.p);p['rows'][91]['horizons'][1]['reported'][0,0]+=.1
  with self.assertRaises(c.AuditFailure):packet.validate(p)
 def test_noise_support_tamper(self):
  p=copy.deepcopy(self.p);p['rows'][0]['noise']['nu'][0,0]=.1
  with self.assertRaises(c.AuditFailure):packet.validate(p)
 def test_initial_receipt_bound(self):
  ad=copy.deepcopy(self.ad);ad['models']['20261012:P']['initial_receipt']['sha256']='c'*64
  with self.assertRaises(c.AuditFailure):auditor.admission_checked(ad,self.p,self.auth)
 def test_checkpoint_parameter_substitution(self):
  cp=copy.deepcopy(self.cp);cp['parameters']['coefficients'][0,0]+=.01
  with self.assertRaises(c.AuditFailure):auditor.checkpoint_checked(cp,self.ad,self.ad['schema'],(20261012,'P'),self.auth)
 def test_history_permutation(self):
  cp=copy.deepcopy(self.cp);cp['history'][0]['ordinals'].reverse()
  with self.assertRaises(c.AuditFailure):auditor.checkpoint_checked(cp,self.ad,self.ad['schema'],(20261012,'P'),self.auth)
 def test_optimizer_not_loaded_but_shape_checked(self):
  cp=copy.deepcopy(self.cp);cp['optimizer']['0']['exp_avg']=np.zeros(1)
  with self.assertRaises(c.AuditFailure):auditor.optimizer_checked(cp['optimizer'],cp['parameters'])
 def test_numeric_transport_exact_roundtrip(self):self.assertTrue(auditor.close(tx.decode(json.loads(tx.canonical(self.cp))),self.cp,0))
 def test_numeric_transport_nan_reject(self):
  with self.assertRaises(c.AuditFailure):tx.decode(json.loads(tx.canonical(np.asarray([np.nan]))))
 def test_root_authority_never_default(self):
  a=copy.deepcopy(self.auth);a['native_verified']=False
  with self.assertRaises(c.AuditFailure):auditor.authority_checked(a)
 def test_full66_independent_replay(self):
  retained=[];r=auditor.audit_fit(self.score,self.p,self.ad,self.cp,self.auth,processing_begin=time.monotonic(),retain=retained.append);self.assertEqual(r['status'],'pass',r.get('failure'));self.assertEqual(r['checked'],66);self.assertEqual(len(retained),66);self.assertFalse(r['advance']['pass_all'])
 def test_boolean_coverage_not_float(self):
  score=copy.deepcopy(self.score);score['predictions'][0]['coverage_95']=1.;auth=f.authority_fixture(self.p,self.ad,self.cp,score);retained=[];r=auditor.audit_fit(score,self.p,self.ad,self.cp,auth,processing_begin=time.monotonic(),retain=retained.append);self.assertEqual(r['status'],'fail');self.assertEqual(r['checked'],0);self.assertIn('coverage',r['failure']['reason']);self.assertEqual(len(retained),1)
 def test_callback_failure_no_retry(self):
  calls=[]
  def bad(v):calls.append(v);raise RuntimeError('invented durable write failure')
  r=auditor.audit_fit(self.score,self.p,self.ad,self.cp,self.auth,processing_begin=time.monotonic(),retain=bad);self.assertEqual(r['status'],'fail');self.assertEqual(len(calls),1)
 def test_record_retained_before_expired_postcheck(self):
  calls=[]
  def retain(v):calls.append(v)
  with patch.object(c.Budget,'tick',side_effect=[None]*200+[c.AuditFailure('invented late deadline')]):r=auditor.audit_fit(self.score,self.p,self.ad,self.cp,self.auth,processing_begin=time.monotonic(),retain=retain)
  self.assertEqual(r['status'],'fail');self.assertTrue(calls)
 def test_partial_aggregate_never_success(self):
  self.assertEqual(auditor.aggregate([],[],self.p,self.ad,[],{},processing_begin=time.monotonic())['status'],'fail')
 def test_guard_count_36(self):
  panel={str(h):dict(mae=.1,medae=.1,lower_mae=.1,lower_medae=.1,cvar95=.1,maximum=.1,tail_mae_5_5=.1,nll=.1,crps=.1)for h in(1,3,5)};oldpanel={str(h):{k:v+.05 for k,v in p.items()}for h,p in panel.items()};fits=[dict(seed=s,arm=a,metrics=panel if a=='S'else oldpanel)for s,a in auditor.IDS];old=[dict(seed=s,arm=a,metrics=oldpanel)for s in(20261012,20261013)for a in('B','F','H','T')];g=metrics.guards(fits,old);self.assertEqual(len(g['checks']),24);self.assertEqual(len(g['additional']),12);self.assertTrue(g['pass_all']);fits[0]['metrics']['1']['mae']=.2;self.assertFalse(metrics.guards(fits,old)['pass_all'])
 def test_metric_mean_action_worst_tail(self):
  rows=[dict(ordinal=i,target=t,mean=m,median=m,nll=0.,crps=0.,group=i,coverage_50=True,coverage_80=True,coverage_95=True)for i,(t,m)in enumerate([(6.,5.),(4.,4.1),(5.,5.2)])];p=metrics.panel(rows);self.assertEqual(p['tail_mae_6'],1.);self.assertEqual(p['maximum'],1.);self.assertAlmostEqual(p['mae'],1.3/3)

if __name__=='__main__':unittest.main()

class AggregateTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.p,cls.ad,cls.audits,cls.scores,cls.old,cls.authority=f.aggregate_fixture()
 def test_complete_396_with_preserved_negative_gate(self):
  # Bootstrap math separately tested; avoid redundant 36k repetitions in unit fixtures.
  with patch.object(metrics,'paired',return_value={'invented':'external'}):r=auditor.aggregate(self.audits,self.scores,self.p,self.ad,self.old,self.authority,processing_begin=time.monotonic())
  self.assertEqual(r['status'],'pass',r);self.assertEqual(r['checked'],396);self.assertEqual(len(r['advance']['checks']),24);self.assertEqual(len(r['advance']['additional']),12);self.assertEqual(len(r['paired']),36);self.assertFalse(r['advance']['pass_all'])
 def test_swapped_fit_even_root_pin_rebinding_fails(self):
  audits=copy.deepcopy(self.audits);audits[0],audits[1]=audits[1],audits[0];self.assertEqual(auditor.aggregate(audits,self.scores,self.p,self.ad,self.old,self.authority,processing_begin=time.monotonic())['status'],'fail')
 def test_missing_old_comparator_fails(self):
  auth=copy.deepcopy(self.authority);auth['stronger_closure_sha256']=tx.sha(self.old[:-1]);self.assertEqual(auditor.aggregate(self.audits,self.scores,self.p,self.ad,self.old[:-1],auth,processing_begin=time.monotonic())['status'],'fail')
 def test_old_closure_false_fails(self):
  old=copy.deepcopy(self.old);old[0]['closure']['verified']=False;auth=copy.deepcopy(self.authority);auth['stronger_closure_sha256']=tx.sha(old);self.assertEqual(auditor.aggregate(self.audits,self.scores,self.p,self.ad,old,auth,processing_begin=time.monotonic())['status'],'fail')
 def test_original_quantiles_not_fabricated(self):self.assertNotIn('quantiles',self.old[0]['predictions'][0]);self.assertIn('quantiles',self.old[2]['predictions'][0])
 def test_bootstrap_actual_paired_groups(self):
  rows=self.audits[0]['records'][::3];b=[dict(v,mean=v['mean']+.1)for v in rows];r=metrics.paired(rows,b);self.assertEqual(r['mae']['groups'],22);self.assertEqual(len(r['mae']['interval']),2);self.assertEqual(r['mae']['status'],'descriptive')
 def test_aggregate_retention_exception_exact_once(self):
  called=[]
  def bad(v):called.append(v);raise OSError('invented')
  with patch.object(metrics,'paired',return_value={}):r=auditor.aggregate(self.audits,self.scores,self.p,self.ad,self.old,self.authority,processing_begin=time.monotonic(),retain=bad)
  self.assertEqual(r['status'],'fail');self.assertEqual(len(called),1)


class AcceptedReviewTests(unittest.TestCase):
 def test_admitted_schema_hash_allows_one_ulp_reduction(self):
  p=f.packet_fixture();ad=f.admission_fixture(p);ad['schema']['summary']['mean'][0]=np.nextafter(ad['schema']['summary']['mean'][0],math.inf)
  for seed,arm in auditor.IDS:
   m=ad['models'][str(seed)+':'+arm];initial=dict(status='initial',study=auditor.STUDY,seed=seed,arm=arm,update=0,parameters=m['initial'],schema_sha256=tx.sha(ad['schema']),packet_sha256=tx.sha(p),source_pins=ad['source_pins'],prior_sha256=m['prior_sha256']);m['initial_receipt']['sha256']=tx.sha(initial)
  self.assertIs(auditor.admission_checked(ad,p,{'packet_sha256':tx.sha(p)}),ad['schema'])
 def test_group_identity_independent_of_ordinal(self):
  p=f.packet_fixture()
  for row in p['rows']:row['group']+=500
  self.assertEqual(len(packet.validate(p)['TRAIN']),65)
 def test_cancellation_dot_bound_includes_absolute_terms(self):
  raw=np.asarray([1.,1.,1e-8]);e=np.full(3,1e-16);sc=dict(mean=np.zeros(3),std=np.ones(3),active=[0,1,2]);theta=np.asarray([1000.,-1000.,1.]);v,b=c.direct_shift(raw,e,sc,theta);self.assertGreater(b,1e-13);self.assertLess(b,1e-10*(1+abs(v)))
 def test_unresolved_large_cancellation_reject(self):
  raw=np.ones(2);sc=dict(mean=np.zeros(2),std=np.ones(2),active=[0,1])
  with self.assertRaises(c.AuditFailure):c.direct_shift(raw,np.zeros(2),sc,np.asarray([1e6,-1e6]))
 def test_summary_standardization_small_std_reject(self):
  with self.assertRaises(c.AuditFailure):c.standardize_bound(np.ones(1),np.full(1,1e-10),np.ones(1),np.full(1,1e-10))


class FurtherAcceptedReviewTests(unittest.TestCase):
 def test_nonconstant_tiny_std_cannot_zero_map(self):
  p=f.packet_fixture()
  for i in range(65):p['rows'][i]['precontext'][8]=1.+i*1e-12
  ad=f.admission_fixture(p);ad['schema']['static']['std'][8]=0.
  with self.assertRaises(c.AuditFailure):auditor.admission_checked(ad,p,{'packet_sha256':tx.sha(p)})
 def test_material_relative_scaler_substitution_reject(self):
  p=f.packet_fixture();ad=f.admission_fixture(p);ad['schema']['summary']['std'][0]*=1+1e-9
  with self.assertRaises(c.AuditFailure):auditor.admission_checked(ad,p,{'packet_sha256':tx.sha(p)})
 def test_failure_current_identity_posterior_work_and_errors_retained(self):
  p=f.packet_fixture();ad=f.admission_fixture(p);cp=f.checkpoint_fixture(ad);score=f.score_fixture(p,ad,cp);score['predictions'][0]['mean']+=.1;auth=f.authority_fixture(p,ad,cp,score);retained=[];r=auditor.audit_fit(score,p,ad,cp,auth,processing_begin=time.monotonic(),retain=retained.append);self.assertEqual(r['status'],'fail');v=r['failure'];self.assertEqual(v['current_record']['ordinal'],91);self.assertIn('posterior',v['current_record']);self.assertGreater(v['current_record']['errors']['mean'],.09);self.assertGreater(v['current_work']['density_points'],0);self.assertEqual(len(retained),1)


class InternalPartialScoreTests(unittest.TestCase):
 def test_crps_crosscheck_failure_retains_available_proper_fields(self):
  p=f.packet_fixture();ad=f.admission_fixture(p);cp=f.checkpoint_fixture(ad);score=f.score_fixture(p,ad,cp);auth=f.authority_fixture(p,ad,cp,score);retained=[]
  with patch.object(c.Mixture,'integral_crps',side_effect=c.AuditFailure('invented integral deadline')):r=auditor.audit_fit(score,p,ad,cp,auth,processing_begin=time.monotonic(),retain=retained.append)
  v=r['failure']['current_record']['fresh'];self.assertEqual(r['status'],'fail');self.assertTrue({'mean','median','nll','crps','pit','quantiles'}<=set(v));self.assertEqual(len(v['quantiles']),7);self.assertEqual(len(retained),1)
 def test_quantile_failure_retains_completed_fields_and_prefix(self):
  prior=(np.full(5,-math.log(5)),np.linspace(-1,1,5),np.ones(5));m=c.Mixture(*prior);original=m.quantile;calls=[];evidence={}
  def fail_at_second(q):
   calls.append(q)
   if len(calls)==3:raise c.AuditFailure('invented partial quantile')
   return original(q)
  with patch.object(m,'quantile',side_effect=fail_at_second):
   with self.assertRaises(c.AuditFailure):m.scores(0.,evidence=evidence)
  self.assertEqual(set(evidence['quantiles']),{'0.025'});self.assertTrue({'mean','median','nll','crps','pit'}<=set(evidence))


class FrozenOperatorDomainTests(unittest.TestCase):
 def test_generated_affine_domain_matches_frozen_contract(self):
  coeff=np.zeros((3,6));coeff[:,1]=300000.;coeff[:,5]=300000.
  with self.assertRaises(c.AuditFailure):c.factors(np.ones((1,3)),coeff,5.)
 def test_accepted_inside_numeric_domain_all_real_support(self):
  prior=(np.full(5,-math.log(5)),np.full(5,10000.),np.ones(5));m=c.Mixture(*prior);self.assertGreater(m.quantile(.975),10000.);self.assertTrue(math.isfinite(m.nll(10000.)))


class RawParameterDomainTests(unittest.TestCase):
 def test_large_finite_hidden_weight_with_benign_output(self):
  p=f.state(1,3,'P');p['prior.first.weight'][:]=1000001.;self.assertGreater(auditor.shape_state(p,1,[0,1,2],'P'),0);prior,bounds=c.prior_forward(np.ones(1),p,1)
  for value,bound in zip(prior,bounds):c.bound_ok(value,bound)
 def test_finite_shape_does_not_limit_raw_tau_theta(self):
  p=f.state(0,3,'D');p['theta'][:]=1000001.;p['tau']=np.asarray(1000001.);self.assertGreater(auditor.shape_state(p,0,[0,1,2],'D'),0)
 def test_raw_coefficient_operator_domain_still_enforced(self):
  coeff=np.zeros((3,6));coeff[0,0]=1000001.
  with self.assertRaises(c.AuditFailure):c.factors(np.ones((1,3)),coeff,5.)
 def test_prior_output_domain_is_distinct_from_parameter_shape(self):
  p=f.state(0,3,'P');p['prior.head.bias'][4]=1000001.;auditor.shape_state(p,0,[0,1,2],'P')
  with self.assertRaises(c.AuditFailure):c.prior_forward(np.empty(0),p,0)


class VerifiedDirectDomainTests(unittest.TestCase):
 def test_direct_theta_boundary_rejects_at_operator_not_snapshot(self):
  scaler=dict(mean=np.zeros(20),std=np.ones(20),active=[0]);raw=np.zeros(20)
  with self.assertRaises(c.AuditFailure):c.direct_shift(raw,np.zeros(20),scaler,np.asarray([1000001.]))
 def test_direct_standardized_input_domain_is_full_twenty(self):
  scaler=dict(mean=np.zeros(20),std=np.ones(20),active=[0]);raw=np.zeros(20);raw[19]=1000001.
  with self.assertRaises(c.AuditFailure):c.direct_shift(raw,np.zeros(20),scaler,np.asarray([0.]))


class ReconstructionFailureEvidenceTests(unittest.TestCase):
 def test_generated_sigma_above_domain_denied_and_retained(self):
  coeff=np.zeros((3,6));coeff[:,5]=1e6;facts=[]
  with self.assertRaises(c.AuditFailure):c.factors(np.ones((1,3)),coeff,5.,evidence=facts)
  self.assertEqual(len(facts),1);self.assertGreater(facts[0][2][0],1e6)
 def test_mid_completion_failure_retains_prior_factors_rawinputs(self):
  p=f.packet_fixture();ad=f.admission_fixture(p);cp=f.checkpoint_fixture(ad);score=f.score_fixture(p,ad,cp);auth=f.authority_fixture(p,ad,cp,score);retained=[]
  with patch.object(c,'complete',side_effect=c.AuditFailure('invented completion representation')):r=auditor.audit_fit(score,p,ad,cp,auth,processing_begin=time.monotonic(),retain=retained.append)
  e=r['failure']['current_record']['reconstruction'];self.assertEqual(r['status'],'fail');self.assertTrue({'raw_context','parameters','reported','nu','prior','facts','reference'}<=set(e));self.assertEqual(len(e['facts']),4);self.assertEqual(len(retained),1)


class AdmittedResidualAndAggregatePartialTests(unittest.TestCase):
 def test_admitted_coefficient_perturbation_fails_absolute_residual(self):
  p=f.packet_fixture();p['rows'][0]['precontext'][8]=100.;ad=f.admission_fixture(p);s=ad['schema']['static'];s['reconstruction'][0,0]=9e-11
  with self.assertRaises(c.AuditFailure):auditor.reconstruction_checked(s,p,packet.validate(p))
 def test_late_aggregate_failure_keeps_all_completed_results(self):
  p,ad,audits,scores,old,auth=f.aggregate_fixture();calls=[]
  def paired(*args,**kwargs):
   calls.append(1)
   if len(calls)==2:kwargs['evidence']['completed']=37;raise c.AuditFailure('invented bootstrap deadline')
   return {'invented':'complete'}
  with patch.object(metrics,'paired',side_effect=paired):r=auditor.aggregate(audits,scores,p,ad,old,auth,processing_begin=time.monotonic())
  self.assertEqual(r['status'],'fail');e=r['partial'];self.assertEqual(len(e['fits']),6);self.assertEqual(len(e['stronger']),8);self.assertEqual(len(e['paired']),1);self.assertEqual(e['current_paired']['bootstrap']['completed'],37);self.assertEqual(len(e['computed_guard_outcomes']['checks']),24);self.assertFalse(r['advance']['pass_all'])
 def test_bootstrap_partial_draw_evidence_available_before_next_tick(self):
  p,ad,audits,scores,old,auth=f.aggregate_fixture();rows=audits[0]['records'][::3];e={};calls=[]
  def tick():
   calls.append(1)
   if len(calls)==4:raise c.AuditFailure('invented deadline')
  with self.assertRaises(c.AuditFailure):metrics.paired(rows,rows,tick,evidence=e)
  self.assertEqual(e['completed'],3);self.assertEqual(len(e['draws']['mae']),3)


class StrongPartialEvidenceTests(unittest.TestCase):
 def test_reused_comparator_partial_validation_retained(self):
  p,ad,audits,scores,old,auth=f.aggregate_fixture();old[1]['predictions'][3]['coverage_95']=1.;auth['stronger_closure_sha256']=tx.sha(old);r=auditor.aggregate(audits,scores,p,ad,old,auth,processing_begin=time.monotonic());self.assertEqual(r['status'],'fail');self.assertEqual(len(r['partial']['stronger']),1);self.assertEqual(len(r['partial']['current_stronger']['records']),3)


class CompletionAndNLLResolutionTests(unittest.TestCase):
 def test_cancellation_mean_small_ulp_is_not_certificate(self):
  prior=(np.full(5,-math.log(5)),np.full(5,512.),np.ones(5));facts=[[np.zeros(3),np.full(3,1e6),np.ones(3),np.ones(3)]]
  with self.assertRaises(c.AuditFailure):c.complete(prior,facts,np.zeros((12,3)),'P',c.Budget())
 def test_extreme_direct_nll_resolution_denied(self):
  mix=c.Mixture(np.full(5,-math.log(5)),np.full(5,1e6),np.full(5,.05))
  with self.assertRaises(c.AuditFailure):mix.nll(0.)
 def test_normal_completion_stays_resolved(self):
  prior=(np.full(5,-math.log(5)),np.full(5,5.),np.full(5,.5));facts=[[np.ones(3),np.full(3,.1),np.ones(3),np.full(3,1.6)]];mix=c.complete(prior,facts,np.zeros((12,3)),'P',c.Budget());self.assertTrue(math.isfinite(mix.nll(5.5)))


class NLLIntervalEvidenceTests(unittest.TestCase):
 def test_far_small_mode_does_not_force_irrelevant_kernel_bound(self):
  mix=c.Mixture(np.log(np.asarray([.999,.00025,.00025,.00025,.00025])),np.asarray([0.,1e5,-1e5,2e5,-2e5]),np.ones(5));self.assertTrue(math.isfinite(mix.nll(.1)))
 def test_nll_rejection_retains_raw_candidate_bits(self):
  mix=c.Mixture(np.full(5,-math.log(5)),np.full(5,1e6),np.full(5,.05));evidence={}
  with self.assertRaises(c.AuditFailure):mix.scores(0.,evidence=evidence)
  self.assertIn('mean',evidence);self.assertIn('median',evidence);self.assertIn('candidate_float64_hex',evidence['rejected_nll'])

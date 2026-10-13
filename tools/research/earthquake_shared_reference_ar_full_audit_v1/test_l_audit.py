"""Invented source-only full L tests; no producer imports or training."""
import copy,json,time,unittest,sys
from unittest.mock import patch
import numpy as np
import fixtures as oldf,l_fixtures as f,l_auditor as a,transport as tx,math_core as c,packet

class AuditTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=oldf.packet_fixture();cls.o=oldf.admission_fixture(cls.p);cls.ad=f.admission(cls.p,cls.o);cls.cps=[f.checkpoint(cls.ad,cls.o,s)for s,_ in a.IDS];cls.scores=[f.score(cls.p,cls.ad,cp)for cp in cls.cps];cls.auths=[f.authority(cls.p,cls.ad,cls.o,cp,s)for cp,s in zip(cls.cps,cls.scores)]
  cls.reports=[a.audit_fit(s,cls.p,cls.ad,cls.o,cp,au,processing_begin=time.monotonic())for s,cp,au in zip(cls.scores,cls.cps,cls.auths)]
  for r in cls.reports:
   if r['status']!='pass':raise AssertionError(r.get('failure'))
  cls.closed,cls.origins=f.closed(cls.p,cls.ad,cls.scores);cls.agg=f.agg_authority(cls.p,cls.ad,cls.o,cls.reports,cls.scores,cls.closed,cls.origins)
 def audit(self,s=None,cp=None,ad=None,o=None,retain=None):
  s=copy.deepcopy(self.scores[0])if s is None else s;cp=self.cps[0]if cp is None else cp;ad=self.ad if ad is None else ad;o=self.o if o is None else o
  s['checkpoint_sha256']=tx.sha(cp)
  return a.audit_fit(s,self.p,ad,o,cp,f.authority(self.p,ad,o,cp,s),processing_begin=time.monotonic(),retain=retain)
 def test_full132(self):self.assertEqual(sum(r['checked']for r in self.reports),132);self.assertTrue(all(r['status']=='pass'and not r['advance']['pass_all']for r in self.reports))
 def test_roles_all345(self):self.assertEqual({k:len(v)for k,v in packet.validate(self.p).items()},{'TRAIN':65,'DEV':22});self.assertEqual(len(self.ad['slots']),115)
 def test_train_only_schema(self):
  p=copy.deepcopy(self.p);p['rows'][91]['precontext'][8]+=1000.;p['rows'][91]['mw']+=.3;self.assertTrue(a.old.close(packet.schema(p,packet.validate(p)),self.ad['schema']))
 def test_changed_schema(self):
  ad=copy.deepcopy(self.ad);ad['schema']['mref']+=.1;self.assertEqual(self.audit(ad=ad)['failure']['reason'],'original_schema')
 def test_original_admission_authority(self):
  au=copy.deepcopy(self.auths[0]);au['original_admission_sha256']='0'*64
  with self.assertRaises(c.AuditFailure):a.admission_checked(self.ad,self.o,self.p,au)
 def test_trained_initial_substitution(self):
  ad=copy.deepcopy(self.ad);ad['models']['20261012:L']['initial']['coefficients'][0,0]+=.1;self.assertEqual(self.audit(ad=ad)['failure']['reason'],'original_initial_state')
 def test_original_s_p_mismatch(self):
  o=copy.deepcopy(self.o);o['models']['20261012:P']['initial']['coefficients'][0,0]+=.1;self.assertEqual(self.audit(o=o)['status'],'fail')
 def test_both_initial_probes(self):
  ad=copy.deepcopy(self.ad);ad['models']['20261013:L']['probe']['masks']['coefficients'][2,5]=0;r=self.audit(ad=ad);self.assertEqual(r['checked'],0);self.assertEqual(r['failure']['reason'],'probe_mask')
 def test_initial_receipt(self):
  ad=copy.deepcopy(self.ad);ad['models']['20261012:L']['initial_receipt']['sha256']='0'*64;self.assertEqual(self.audit(ad=ad)['failure']['reason'],'initial_receipt_binding')
 def test_capacity_no_padding(self):
  ad=copy.deepcopy(self.ad);ad['capacity']['L']+=1;self.assertEqual(self.audit(ad=ad)['failure']['reason'],'L_capacity')
 def test_history_permutation(self):
  cp=copy.deepcopy(self.cps[0]);cp['history'][0]['ordinals'].reverse();self.assertEqual(self.audit(cp=cp)['failure']['reason'],'history_order')
 def test_final_probe_mask(self):
  cp=copy.deepcopy(self.cps[0]);cp['final_probe']['masks']['coefficients'][0,0]=0;self.assertEqual(self.audit(cp=cp)['failure']['reason'],'probe_mask')
 def test_final299(self):
  cp=copy.deepcopy(self.cps[0]);cp['update']=299;self.assertEqual(self.audit(cp=cp)['failure']['reason'],'final_checkpoint')
 def test_optimizer_shapes(self):
  cp=copy.deepcopy(self.cps[0]);cp['optimizer']['0']['exp_avg']=np.zeros(1);self.assertEqual(self.audit(cp=cp)['status'],'fail')
 def test_loading_override(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source']['reference']['facts'][1]['loading'][0]=1.;r=self.audit(s);self.assertEqual(r['checked'],0);self.assertEqual(r['status'],'fail');self.assertIn('reference',r['failure']['current_record']['reconstruction']);self.assertIn('posterior',r['failure']['current_record']['reconstruction'])
 def test_source_keys_rejection_keeps_posterior(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source'].pop('noise_probabilities')
  with patch.object(a.ar,'complete',wraps=a.ar.complete)as complete:r=self.audit(s)
  self.assertEqual(r['status'],'fail');self.assertEqual(complete.call_count,1)
  self.assertIn('posterior',r['failure']['current_record']['reconstruction'])
 def test_loading_rejection_completion_once(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source']['reference']['facts'][1]['loading'][0]=1.
  with patch.object(a.ar,'complete',wraps=a.ar.complete)as complete:r=self.audit(s)
  self.assertEqual(r['status'],'fail');self.assertEqual(complete.call_count,1)
  self.assertEqual(r['failure']['current_record']['reconstruction']['posterior']['means'].shape,(60,))
 def test_previous_override(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source']['reference']['facts'][1]['previous'][0]+=.1;self.assertEqual(self.audit(s)['status'],'fail')
 def test_future_horizon(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source']['reference']['horizon']=3;self.assertEqual(self.audit(s)['status'],'fail')
 def test_posterior_override(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source']['means'][0]+=.01
  calls=[];r=self.audit(s,retain=calls.append);self.assertEqual(r['status'],'fail')
  evidence=r['failure']['current_record']['reconstruction'];self.assertIn('posterior',evidence)
  self.assertAlmostEqual(evidence['posterior_errors']['means'][0],.01)
  self.assertEqual(evidence['posterior']['means'].shape,(60,));self.assertEqual(len(calls),1)
 def test_evidence_normalizer_rejection(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source']['log_normalizer']+=.01
  r=self.audit(s);evidence=r['failure']['current_record']['reconstruction']
  self.assertEqual(r['status'],'fail');self.assertIn('posterior',evidence)
  self.assertAlmostEqual(evidence['posterior_errors']['log_normalizer'],.01)
 def test_completion_not_rerun_on_parity_failure(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['source']['means'][0]+=.01
  with patch.object(a.ar,'complete',wraps=a.ar.complete)as complete:r=self.audit(s)
  self.assertEqual(r['status'],'fail');self.assertEqual(complete.call_count,1)
 def test_proper_score(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['crps']+=.01;self.assertEqual(self.audit(s)['failure']['reason'],'proper_disagreement')
 def test_quantile(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['quantiles']['0.5']+=.01;self.assertEqual(self.audit(s)['failure']['reason'],'quantile_disagreement')
 def test_coverage_bool(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['coverage_95']=1.;self.assertEqual(self.audit(s)['failure']['reason'],'coverage_bool')
 def test_diagnostic_work(self):
  s=copy.deepcopy(self.scores[0]);s['predictions'][0]['diagnostics']['work']['seconds']=10.01;self.assertEqual(self.audit(s)['failure']['reason'],'diagnostic_work')
 def test_unchanged_operator_role(self):
  ad=copy.deepcopy(self.ad);ad['source_pins']['operator']['sha256']='f'*64
  self.assertEqual(self.audit(ad=ad)['failure']['reason'],'unchanged_role_binding')
 def test_seven_sources(self):
  au=copy.deepcopy(self.auths[0]);au['source_pins'].pop('kernel')
  with self.assertRaises(c.AuditFailure):a.authority_checked(au)
 def test_numeric_roundtrip(self):self.assertEqual(tx.sha(tx.decode(json.loads(tx.canonical(self.cps[0])))),tx.sha(self.cps[0]))
 def test_callback_failure_no_retry(self):
  calls=[]
  def reject(v):calls.append(v);raise RuntimeError('invented disk failure')
  r=self.audit(retain=reject);self.assertEqual(r['status'],'fail');self.assertEqual(len(calls),1)
 def test_final_retention_failure(self):
  calls=[]
  def retain(v):
   calls.append(v)
   if v.get('schema')==a.REPORT:raise RuntimeError('invented final write failure')
  r=self.audit(retain=retain);self.assertEqual(r['status'],'fail');self.assertEqual(len(calls),67);self.assertEqual(r['failure']['reason'],'retention_failed')
 def test_final_report_late_return_is_incomplete(self):
  calls=[];expired=[False]
  def retain(v):
   calls.append(v)
   if v.get('schema')==a.REPORT:expired[0]=True
  def tick(begin):
   if expired[0]:raise c.AuditFailure('invented late return')
   a.old.stage_tick(begin)
  with patch.object(a,'stage_tick',side_effect=tick):r=self.audit(retain=retain)
  self.assertEqual(r['status'],'fail');self.assertFalse(r['advance']['pass_all']);self.assertEqual(r['checked'],66)
  self.assertEqual(len(calls),68);self.assertEqual(calls[-2]['status'],'pass');self.assertEqual(calls[-1]['status'],'fail')
 def test_wrong_role_order_does_not_authorize(self):
  ad=copy.deepcopy(self.ad);ad['models']['20261012:L']['order'][0,0]=91
  self.assertEqual(self.audit(ad=ad)['failure']['reason'],'original_initial_order')
 def test_packet_mutated_noise_rejected(self):
  p=copy.deepcopy(self.p);p['rows'][91]['noise']['nu'][0,0]=.1
  with self.assertRaises(c.AuditFailure):packet.validate(p)
 def test_packet_mutated_prefix_rejected(self):
  p=copy.deepcopy(self.p);p['rows'][91]['horizons'][1]['reported'][0,0]+=.1
  with self.assertRaises(c.AuditFailure):packet.validate(p)
 def test_expired_entry(self):
  r=a.audit_fit(self.scores[0],self.p,self.ad,self.o,self.cps[0],self.auths[0],processing_begin=time.monotonic()-901);self.assertEqual(r['status'],'fail');self.assertEqual(r['checked'],0)
 def test_closed924_and_original_semantics(self):
  values=a.comparators_checked(self.closed,self.origins,self.p,self.ad['schema'],self.agg);self.assertEqual(sum(len(v['records'])for v in values),924);self.assertNotIn('quantiles',values[6]['records'][0]);self.assertIn('original_packet_sha256_semantics',self.origins[0])
 def test_comparator_hash_mismatch(self):
  report=copy.deepcopy(self.closed);report['fits'][0]['records'][0]['mean']+=.1
  with self.assertRaises(c.AuditFailure):a.comparators_checked(report,self.origins,self.p,self.ad['schema'],self.agg)
 def test_old_guard_recomputed(self):
  report=copy.deepcopy(self.closed);report['advance']['pass_all']=True;au=copy.deepcopy(self.agg);au['closed_comparator_report_sha256']=tx.sha(report)
  with self.assertRaises(c.AuditFailure):a.comparators_checked(report,self.origins,self.p,self.ad['schema'],au)
 def test_origin_record_swap(self):
  origins=copy.deepcopy(self.origins);origins[0]['records_sha256']='a'*64;au=copy.deepcopy(self.agg);au['origins_sha256']=tx.sha(origins)
  with self.assertRaises(c.AuditFailure):a.comparators_checked(self.closed,origins,self.p,self.ad['schema'],au)
 def test_42_guards(self):
  fits=[dict(seed=s,arm='L',metrics={str(h):dict(mae=.1,medae=.1,lower_mae=.1,lower_medae=.1,cvar95=.1,maximum=.1,tail_mae_5_5=.1,nll=.1,crps=.1)for h in(1,3,5)})for s,_ in a.IDS];other=[dict(seed=s,arm=arm,metrics={str(h):{k:v+.05 for k,v in fits[0]['metrics'][str(h)].items()}for h in(1,3,5)})for s,_ in a.IDS for arm in a.COMPARATORS];g=a.guards(fits,other);self.assertEqual((len(g['checks']),len(g['additional'])),(24,18));self.assertTrue(g['pass_all']);fits[0]['metrics']['1']['lower_mae']=.2;self.assertFalse(a.guards(fits,other)['pass_all']);fits[0]['metrics']['1']['lower_mae']=.1;fits[0]['metrics']['1']['nll']=.16;self.assertFalse(a.guards(fits,other)['pass_all'])
 def test_missing_comparator(self):
  r=a.aggregate(self.reports,self.scores,self.p,self.ad,self.o,self.closed,self.origins[:-1],self.agg,processing_begin=time.monotonic());self.assertEqual(r['status'],'fail');self.assertFalse(r['advance']['pass_all'])
 def test_full1056_and42_bootstraps(self):
  retained=[];r=a.aggregate(self.reports,self.scores,self.p,self.ad,self.o,self.closed,self.origins,self.agg,processing_begin=time.monotonic(),retain=retained.append);self.assertEqual(r['status'],'pass',r.get('reason'));self.assertEqual(r['record_counts']['total'],1056);self.assertEqual(len(r['paired']),42);self.assertEqual(sum(v['role']=='mechanistic'for v in r['paired']),6);self.assertFalse(r['advance']['pass_all']);self.assertEqual(len(retained),1);self.assertTrue(all(v['metrics']['mae']['delta']==0. for v in r['paired']))
 def test_aggregate_retention_failure(self):
  calls=[]
  def reject(v):calls.append(v);raise RuntimeError('invented failure')
  with patch.object(a.metrics,'paired',return_value={'invented':'test-only'}):r=a.aggregate(self.reports,self.scores,self.p,self.ad,self.o,self.closed,self.origins,self.agg,processing_begin=time.monotonic(),retain=reject)
  self.assertEqual(r['status'],'fail');self.assertFalse(r['advance']['pass_all']);self.assertEqual(len(calls),1)
 def test_no_producer_imports(self):self.assertFalse({'torch','processor','l_math','level_kernel','gaussian_operator'} & set(sys.modules))

if __name__=='__main__':unittest.main()

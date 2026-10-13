"""Invented bounded continuation policy, durability and unchanged function handoff."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import numpy as np
import custody as c
import controls as x
import base
import controller as p
import processor as science
import score_child as child
import invented
import fixture_math as fm

class BatchedTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.g,self.begin=invented.batched(self.root)
 def tearDown(self):self.tmp.cleanup()
 def value(self,spec):return c.strict_json(base.load(spec))
 def math(self):return fm.complete(self.value(self.g['result']),self.g)
 def test_fixed_ten_plus_one_stage_and_forward660(self):
  p.gate_checked(self.g,self.begin);result=base.custody_checked(p.old_gate(self.g));proof=p.forward_checked(self.g,result);self.assertEqual(proof['forward_records'],660)
  for index,pair in enumerate(p.IDS):
   g=copy.deepcopy(self.g);g.update(index=index,seed=pair[0],arm=pair[1],previous=[g['preparation']]*index);p.gate_checked(g,self.begin)
  g=copy.deepcopy(self.g);g.update(index=10,stage='aggregate',seed=None,arm=None,previous=[g['preparation']]*10);p.gate_checked(g,self.begin)
 def test_journal_parameter_or_identity_tamper_prevents_claim(self):
  raw=base.load(self.g['forward']['journal'],1048576);rows=[c.strict_json(v,4096)for v in raw.splitlines()];rows[17]['forward_parameter_pin']['sha256']='f'*64;bad=b''.join((json.dumps(v)+'\n').encode()for v in rows);spec=self.g['forward']['journal'];path=Path(spec['path']);path.chmod(0o600);path.write_bytes(bad);path.chmod(0o400);spec['pin']=c.pin(bad);proof=self.value(self.g['forward']['authority']);proof['journal_pin']=spec['pin'];invented.replace(self.g['forward']['authority'],proof)
  with self.assertRaisesRegex(ValueError,'forward_parameter_pin'):p.claim(self.g,self.begin)
  self.assertEqual(list(Path(self.g['output_root']).iterdir()),[])
 def test_authority_must_bind_original_source_packet_result_and_ten_anchors(self):
  spec=self.g['forward']['authority'];original=self.value(spec)
  for key,v in(('verified',False),('models',9),('forward_records',659),('result_pin',{'bytes':1,'sha256':'f'*64})):
   wrong=copy.deepcopy(original);wrong[key]=v;invented.replace(spec,wrong)
   with self.assertRaises(ValueError):p.forward_checked(self.g,self.value(self.g['result']))
  invented.replace(spec,original)
  wrong=copy.deepcopy(original);wrong['source_pins']['parent']={};invented.replace(spec,wrong)
  with self.assertRaisesRegex(ValueError,'forward_parent_source'):p.forward_checked(self.g,self.value(self.g['result']))
 def test_whole12000_clock_order_never_resets(self):
  with self.assertRaises(ValueError):p.science_tick(self.begin,self.begin+1)
  with self.assertRaises(ValueError):p.science_tick(time.monotonic(),time.monotonic()-12001)
  with self.assertRaises(ValueError):p.science_tick(self.begin,True)
  self.assertFalse(p.within(self.begin-901,self.begin-901))
 def test_durable_claim_once_before_numeric_imports(self):
  out=p.claim(self.g,self.begin);self.assertEqual((Path(self.g['output_root'])/'claim_00.private.json').stat().st_mode&0o777,0o400);self.assertTrue((out/'parent_gate.private.json').exists())
  with self.assertRaises(ValueError):p.claim(self.g,self.begin)
 def test_fixed_profile_fingerprint_excludes_only_stage_role_prefix(self):
  fp=p.fingerprint(self.g);g=copy.deepcopy(self.g);g.update(index=1,arm='F',previous=[{}]);self.assertEqual(fp,p.fingerprint(g));g['forward']['authority']['pin']['sha256']='f'*64;self.assertNotEqual(fp,p.fingerprint(g))
 def test_fit66_calls_same_frozen_numeric_interface_once_per_record(self):
  result,packet,scalers,histories,ad=self.math();outcomes=[];report=science.fit_audit(result,packet,0,scalers,histories,ad,np,lambda:None,outcomes.append);self.assertTrue(report['complete']);self.assertEqual(report['status'],'pass');self.assertEqual(len(outcomes),66);self.assertEqual(len(ad.calls),66);self.assertEqual([(v['ordinal'],v['horizon'])for v in outcomes],[(i,h)for i in self.g['dev_ordinals']for h in(1,3,5)])
 def test_numerical_failure_retained_before_next_clock_and_not_success(self):
  result,packet,scalers,histories,ad=self.math();outcomes=[]
  def failed(*args):raise ValueError('invented_numeric')
  ad.numerical_record=failed;report=science.fit_audit(result,packet,0,scalers,histories,ad,np,lambda:None,outcomes.append);self.assertFalse(report['complete']);self.assertEqual(report['status'],'fail');self.assertEqual(len(outcomes),1);self.assertIsNone(outcomes[0]['fresh']);self.assertEqual(outcomes[0]['reason'],'invented_numeric');self.assertEqual(report['advance'],dict(pass_all=False,checks=[]))
 def test_initial_hazard_invariance_and_discrete_bind_stay_strict(self):
  result,packet,scalers,histories,ad=self.math();result['fits'][2]['predictions'][1]['numerical']['hazard']['alpha'][0]=1.;outcomes=[];report=science.fit_audit(result,packet,2,scalers,histories,ad,np,lambda:None,outcomes.append);self.assertFalse(report['complete']);self.assertEqual(len(outcomes),2);self.assertIsNotNone(outcomes[-1]['fresh']);self.assertIsNotNone(outcomes[-1]['returned_record']);self.assertEqual(outcomes[-1]['reason'],'initial_invariance');self.assertEqual(outcomes[-1]['exception_type'],'ValueError')
 def test_stored_score_mismatch_retained_and_verification_fails(self):
  result,packet,scalers,histories,ad=self.math();result['fits'][0]['predictions'][0]['mean']=4.01;outcomes=[];report=science.fit_audit(result,packet,0,scalers,histories,ad,np,lambda:None,outcomes.append);self.assertTrue(report['complete']);self.assertEqual(report['status'],'fail');self.assertIn('stored_score',report['reasons']);self.assertEqual(outcomes[0]['status'],'fail')
 def test_ten_aggregate_recomputes_all24_metrics_strata_guards(self):
  result,packet,scalers,histories,ad=self.math();reports=[science.fit_audit(result,packet,i,scalers,histories,ad,np,lambda:None,lambda v:None)for i in range(10)];report=science.aggregate(result,packet,reports,scalers,histories,ad,np,lambda:None);self.assertEqual(report['status'],'pass');self.assertEqual(len(report['fits']),10);self.assertEqual(len(report['comparisons']),24);self.assertEqual(len(report['advance']['checks']),24);self.assertFalse(report['advance']['pass_all'])
  reports[0]['status']='fail';reports[0]['reasons']=['stored_score'];report=science.aggregate(result,packet,reports,scalers,histories,ad,np,lambda:None);self.assertEqual(report['status'],'fail');self.assertEqual(report['advance'],dict(pass_all=False,checks=[]))
 def test_aggregate_missing_tenth_or_foreign_row_never_passes(self):
  result,packet,scalers,histories,ad=self.math();reports=[science.fit_audit(result,packet,i,scalers,histories,ad,np,lambda:None,lambda v:None)for i in range(10)]
  with self.assertRaises(ValueError):science.aggregate(result,packet,reports[:-1],scalers,histories,ad,np,lambda:None)
  reports[9]['fit']['predictions'][0]['group']+=1
  with self.assertRaises(ValueError):science.aggregate(result,packet,reports,scalers,histories,ad,np,lambda:None)
 def child_setup(self):
  out=p.claim(self.g,self.begin);result,packet,scalers,histories,ad=self.math();loader=types.SimpleNamespace(load=lambda *args,**kw:packet);return out,result,packet,scalers,histories,ad,loader
 def test_returned_fit_report_persists_even_when_clock_expired(self):
  out,result,packet,scalers,histories,ad,loader=self.child_setup();report=dict(schema='receiver-fit-score-audit-v1',status='fail',complete=False,seed=20261012,arm='B',advance=dict(pass_all=False,checks=[]),reasons=['deadline']);clock=[self.begin]
  def returned(*args):clock[0]=self.begin+901;return report
  with patch.object(child,'before_import',return_value=(result,b'a',b'm',{})),patch.object(child,'dependencies',return_value=(np,loader,ad)),patch.object(child,'numeric_anchors',return_value=(scalers,histories)),patch.object(science,'fit_audit',side_effect=returned),patch.object(p.time,'monotonic',side_effect=lambda:clock[0]):
   with self.assertRaises(ValueError):child.main(out)
  saved=c.strict_json((out/'stage_report.private.json').read_bytes());self.assertEqual(saved['report'],report);self.assertFalse(saved['within_budget']);self.assertTrue((out/'failure.private.json').exists())
 def test_returned_record_persists_before_post_score_expiry(self):
  out,result,packet,scalers,histories,ad,loader=self.child_setup();clock=[self.begin]
  def late(*args):clock[0]=self.begin+901;return fm.score(4.,'B'),None
  ad.numerical_record=late
  with patch.object(child,'before_import',return_value=(result,b'a',b'm',{})),patch.object(child,'dependencies',return_value=(np,loader,ad)),patch.object(child,'numeric_anchors',return_value=(scalers,histories)),patch.object(p.time,'monotonic',side_effect=lambda:clock[0]):
   with self.assertRaises(ValueError):child.main(out)
  self.assertTrue((out/'record_00.private.json').exists());self.assertTrue((out/'failure.private.json').exists());self.assertEqual(c.strict_json((out/'failure.private.json').read_bytes())['records'],1)
 def test_manager_and_failure_capture_has_no_expired_science_tick(self):
  clock=[self.begin];answer=dict(code=1,timeout=False,raw={'stdout':b'\xffretained','stderr':b'failure'},streams={k:dict(truncated=False,complete_observation=True)for k in('stdout','stderr')})
  def runner(*args):clock[0]=self.begin+1000;return answer
  with patch.object(p.time,'monotonic',side_effect=lambda:clock[0]):returned=p.run_stage(self.g,processing_begin=self.begin,runner=runner,check_output=lambda *a,**kw:'Result=exit-code\nActiveState=failed\nControlGroup=\n')
  self.assertEqual(returned['status'],'incomplete');self.assertEqual(returned['advance'],dict(pass_all=False,checks=[]));out=Path(self.g['output_root'])/'stage_00';self.assertEqual((out/'manager_stdout.private.bin').read_bytes(),b'\xffretained');self.assertTrue((out/'parent_return.private.json').exists())
 def test_aggregate_reports_exact_durable_outcomes_closed_pins(self):
  result,packet,scalers,histories,ad=self.math();g=copy.deepcopy(self.g);g.update(index=10,stage='aggregate',seed=None,arm=None,previous=[])
  for i,pair in enumerate(p.IDS):
   directory=Path(g['output_root'])/('stage_%02d'%i);directory.mkdir();store=c.Store(directory);outcomes={}
   def retain(v):
    name='record_%02d.private.json'%v['position'];outcomes[name]=store.put(name,dict(schema='receiver-batched-score-record-wrapper-v1',binding=p.bindings(g),outcome=v))
   report=science.fit_audit(result,packet,i,scalers,histories,ad,np,lambda:None,retain);store.put('stage_report.private.json',dict(schema='receiver-batched-score-stage-report-v1',binding=p.bindings(g),index=i,stage='fit',within_budget=True,report=report,outcomes=outcomes));files,total=store.inventory();returned=dict(schema='receiver-batched-score-parent-return-v1',index=i,stage='fit',seed=pair[0],arm=pair[1],status='complete',unit_exit=0,owned_unit_inactive=True,owned_cgroup_empty=True,fingerprint=p.fingerprint(g),output_directory=str(directory),files=files,no_retry=True);g['previous'].append(invented.write(directory,'parent_return.private.json',returned))
  reports=p.completed_reports(g);self.assertEqual(len(reports),10);self.assertEqual(sum(len(r['fit']['predictions'])for r in reports),660)
  wrong=self.value(g['previous'][0]);wrong['files']['record_00.private.json']['sha256']='f'*64;invented.replace(g['previous'][0],wrong)
  with self.assertRaisesRegex(ValueError,'outcome_closed_pin'):p.completed_reports(g)
 def test_aggregate_deadline_return_report_is_durable_not_lost(self):
  out,result,packet,scalers,histories,ad,loader=self.child_setup();self.g.update(index=10,stage='aggregate',seed=None,arm=None);gatefile=out/'parent_gate.private.json';spec={'path':str(gatefile),'pin':c.pin(gatefile.read_bytes())};invented.replace(spec,self.g);clock=[self.begin]
  report=dict(schema='earthquake-TRAIN115-renewal-score-audit-v3',status='fail',advance=dict(pass_all=False,checks=[]),reasons=['invented'])
  def returned(*args):clock[0]=self.begin+901;return report
  with patch.object(child,'before_import',return_value=(result,b'a',b'm',{})),patch.object(child,'dependencies',return_value=(np,loader,ad)),patch.object(child,'numeric_anchors',return_value=(scalers,histories)),patch.object(p,'completed_reports',return_value=[]),patch.object(science,'aggregate',side_effect=returned),patch.object(p.time,'monotonic',side_effect=lambda:clock[0]):
   with self.assertRaises(ValueError):child.main(out)
  self.assertEqual(c.strict_json((out/'stage_report.private.json').read_bytes())['report'],report);self.assertTrue((out/'failure.private.json').exists())
 def test_cleanup_query_failure_durable_incomplete_without_claiming_cleanup(self):
  answer=dict(code=1,timeout=False,raw={'stdout':b'kept','stderr':b'failed'},streams={k:dict(truncated=False,complete_observation=True)for k in('stdout','stderr')})
  def post(*args,**kwargs):raise __import__('subprocess').TimeoutExpired('invented_show',5,output=b'Result=exit-code\n')
  result=p.run_stage(self.g,processing_begin=self.begin,runner=lambda *args:answer,check_output=post);self.assertEqual(result['status'],'incomplete');self.assertIsNone(result['owned_unit_inactive']);self.assertIsNone(result['owned_cgroup_empty']);self.assertFalse(result['cleanup_verified']);out=Path(self.g['output_root'])/'stage_00';self.assertEqual((out/'post_properties_observed.private.bin').read_bytes(),b'Result=exit-code\n');self.assertTrue((out/'cleanup_failure.private.json').exists());self.assertTrue((out/'parent_return.private.json').exists())
 def test_populated_cgroup_properties_retained_not_verified_or_advanced(self):
  answer=dict(code=0,timeout=False,raw={'stdout':b'','stderr':b''},streams={k:dict(truncated=False,complete_observation=True)for k in('stdout','stderr')});text='Result=success\nActiveState=active\nControlGroup=/notempty\n';result=p.run_stage(self.g,processing_begin=self.begin,runner=lambda *args:answer,check_output=lambda *args,**kwargs:text);self.assertEqual(result['status'],'incomplete');self.assertFalse(result['cleanup_verified']);self.assertEqual(result['advance'],dict(pass_all=False,checks=[]));self.assertEqual((Path(self.g['output_root'])/'stage_00/post_properties_observed.private.bin').read_bytes(),text.encode())
 def test_private_no_overwrite_nonfinite_and_caps(self):
  d=self.root/'private';d.mkdir();c.private_put(d,'one.json',{})
  with self.assertRaises(FileExistsError):c.private_put(d,'one.json',{})
  with self.assertRaises(ValueError):c.private_put(d,'bad.json',{'x':math.nan})
  with self.assertRaises(ValueError):c.private_put(d,'big.json',{'x':'a'*100},16)
 def test_no_model_or_optimizer_in_numeric_child_source(self):
  import ast
  tree=ast.parse(Path(child.__file__).read_text());names=[n.names[0].name for n in ast.walk(tree)if isinstance(n,ast.Import)];self.assertNotIn('torch',names);self.assertNotIn('models',names);self.assertNotIn('engine',names);self.assertNotIn('optimizer',Path(child.__file__).read_text().lower())
 def test_reference_bootstrap_1000_groups_and_strict_discrete_coverage(self):
  import reference_metrics as m
  left=[dict(ordinal=i,horizon=1,target=y,group=i,mean=y+.1,median=y+.1,nll=1.,crps=.1,coverage_50=True,coverage_80=True,coverage_95=True)for i,y in enumerate((4.,5.6,6.3))];right=[dict(v,mean=v['mean']+.2)for v in left];one=m.paired(left,right);two=m.paired(left,right);self.assertEqual(one,two);self.assertEqual(one['mae']['status'],'descriptive');self.assertEqual(one['mae']['groups'],3);self.assertEqual(one['tail_mae_5_5']['status'],'unsupported');ad=fm.Fake([]);self.assertFalse(ad.close(True,1));self.assertFalse(ad.close(1,True))
 def test_posterior_numeric_functions_and_math_are_external_unchanged(self):
  text=Path(science.__file__).read_text();self.assertIn('ad.numerical_record(',text);self.assertIn('ad.paired(',text);self.assertIn('ad.advance(',text);self.assertNotIn('Posterior(',text);self.assertNotIn('hermite(',text);self.assertNotIn('quad(',text)

if __name__=='__main__':unittest.main()

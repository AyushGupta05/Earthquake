"""Invented integration-control tests; no auditor/data/module/provider imports."""
import copy
import hashlib
import json
import time
import unittest
from unittest.mock import patch
import wrapper as w


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def report(stage):
 if stage<6:return dict(schema='marked-sixfit-independent-audit-v1',status='pass',seed=w.PAIRS[stage][0],arm=w.PAIRS[stage][1],checked=66,advance=dict(pass_all=False,checks=[]))
 return dict(schema='marked-sixfit-independent-aggregate-v1',status='pass',checked=396,fits=[{}for _ in range(6)],stronger=[{}for _ in range(8)],advance=dict(pass_all=False,checks=[{}for _ in range(24)],additional=[{}for _ in range(12)]))

class Fixture:
 def __init__(self,stage=0):
  self.stage=stage;self.calls=[];self.retained=[];self.claims=[];self.claimed=False;self.clock=time.monotonic();self.inputs=dict(score=dict(seed=w.PAIRS[stage][0],arm=w.PAIRS[stage][1]),packet={},admission={},checkpoint=dict(seed=w.PAIRS[stage][0],arm=w.PAIRS[stage][1]),authority={})if stage<6 else dict(fit_audits=[report(i)for i in range(6)],score_results=[],packet={},admission={},stronger=[],authority={})
  self.bindings=w.Bindings(self.audit,self.aggregate,encode,'a'*64);previous=[]
  for i in range(stage):previous.append(dict(stage=i,seed=w.PAIRS[i][0],arm=w.PAIRS[i][1],inputs_sha256='b'*64,binding_sha256='a'*64,report_sha256=w.sha(encode(report(i))),closed_proof_sha256='c'*64,known_verified=True,exit_status=0,unit_inactive=True,cgroup_empty=True))
  self.gate=dict(schema='root-marked-sixfit-audit-wrapper-gate-v1',study=w.STUDY,stage=stage,root_verified=True,proofs={k:dict(known_verified=True,sha256='d'*64)for k in('source','runtime','native','stronger','history_gradient','resources')},binding_sha256='a'*64,inputs_sha256=w.sha(encode(self.inputs)),whole_begin=self.clock,whole_seconds=7200,closure_seconds=200,lease_deadline=self.clock+7300,disk_available_bytes=1024*1024*1024,disk_reserve_bytes=0,stage_payload_cap_bytes=w.TOTAL,previous=previous)
 def claim(self,data,digest):
  if self.claimed:raise FileExistsError('invented duplicate claim')
  self.claimed=True;self.claims.append((data,digest));self.calls.append('claim');return dict(status='durable',sha256=digest)
 def retain(self,kind,index,data,digest):
  self.assert_bytes(data,digest);self.calls.append(kind);self.retained.append((kind,index,data,digest));return dict(status='durable',sha256=digest)
 def assert_bytes(self,data,digest):
  assert type(data)is bytes and hashlib.sha256(data).hexdigest()==digest
 def audit(self,score,packet,admission,checkpoint,authority,*,processing_begin,retain=None):
  assert self.claimed;self.calls.append('audit');retain(dict(position=0,status='pass',invented=True));return report(self.stage)
 def aggregate(self,fit_audits,score_results,packet,admission,stronger,authority,*,processing_begin,retain=None):
  assert self.claimed;self.calls.append('aggregate');retain(report(6));return report(6)
 def run(self):return w.run_stage(self.stage,self.inputs,self.gate,self.bindings,claim=self.claim,retain=self.retain,processing_begin=self.clock)

class WrapperTests(unittest.TestCase):
 def test_claim_before_science_and_raw_report(self):
  f=Fixture();r=f.run();self.assertEqual(r['status'],'complete');self.assertEqual(f.calls,['claim','audit','record','raw_report']);self.assertFalse(r['advance']['pass_all']);self.assertEqual(r['report_pin']['sha256'],w.sha(encode(report(0))))
 def test_all_six_fixed_pairs(self):
  for index,pair in enumerate(w.PAIRS):
   f=Fixture(index);r=f.run();self.assertEqual(r['status'],'complete');self.assertEqual((r['seed'],r['arm']),pair)
 def test_aggregate396_and36guards(self):
  f=Fixture(6);r=f.run();self.assertEqual(r['status'],'complete');self.assertEqual(len(r['advance']['checks']),24);self.assertEqual(len(r['advance']['additional']),12);self.assertEqual(f.calls,['claim','aggregate','record','raw_report'])
 def test_duplicate_claim_no_retry_or_second_science(self):
  f=Fixture();self.assertEqual(f.run()['status'],'complete');r=f.run();self.assertEqual(r['status'],'fail');self.assertEqual(f.calls.count('audit'),1);self.assertEqual(len(f.claims),1)
 def test_false_root_proof_no_claim_or_science(self):
  f=Fixture();f.gate['proofs']['native']['known_verified']=False;r=f.run();self.assertEqual(r['status'],'fail');self.assertFalse(f.claimed);self.assertNotIn('audit',f.calls)
 def test_boolean_stage_not_integer(self):
  f=Fixture();f.stage=True;r=f.run();self.assertEqual(r['status'],'fail');self.assertFalse(f.claimed)
 def test_input_tamper_before_claim(self):
  f=Fixture();f.inputs['packet']['tampered']=1;r=f.run();self.assertEqual(r['status'],'fail');self.assertFalse(f.claimed)
 def test_pair_reordering_before_claim(self):
  f=Fixture();f.inputs['score']['arm']='D';f.gate['inputs_sha256']=w.sha(encode(f.inputs));self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_previous_count_missing(self):
  f=Fixture(2);f.gate['previous'].pop();self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_previous_uncertain_cleanup(self):
  f=Fixture(2);f.gate['previous'][0]['cgroup_empty']=False;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_previous_forged_source_binding(self):
  f=Fixture(2);f.gate['previous'][0]['binding_sha256']='f'*64;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_aggregate_prior_report_substitution(self):
  f=Fixture(6);f.inputs['fit_audits'][0]['checked']=65;f.gate['inputs_sha256']=w.sha(encode(f.inputs));self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_lease_expired_before_claim(self):
  f=Fixture();f.gate['whole_begin']-=100.;f.gate['lease_deadline']=f.clock-1;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_whole_expired_before_claim(self):
  f=Fixture();f.gate['whole_begin']-=7201.;f.gate['lease_deadline']=f.clock+10.;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_source_deadline_before_claim(self):
  f=Fixture();f.clock-=901.;f.gate['whole_begin']=f.clock;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_disk_reservation_before_claim(self):
  f=Fixture();f.gate['disk_available_bytes']=w.TOTAL-1;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_negative_disk_or_boolean_reserve(self):
  f=Fixture();f.gate['disk_reserve_bytes']=True;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_raw_partial_report_preserved_before_rejection(self):
  f=Fixture()
  def audit(**kw):return dict(status='fail',checked=3,partial=dict(invented='numeric evidence'),advance=dict(pass_all=False,checks=[]))
  f.bindings=w.Bindings(audit,f.aggregate,encode,'a'*64);r=f.run();self.assertEqual(r['status'],'fail');payload=json.loads(next(data for kind,index,data,digest in f.retained if kind=='raw_report'));self.assertEqual(payload['checked'],3);self.assertEqual(r['available_report'],payload);self.assertEqual(f.calls[-1],'wrapper_failure')
 def test_raw_report_persisted_before_late_deadline(self):
  f=Fixture();original=f.retain
  def retain(kind,index,data,digest):
   result=original(kind,index,data,digest)
   if kind=='raw_report':f.gate['lease_deadline']=f.clock-1
   return result
  r=w.run_stage(0,f.inputs,f.gate,f.bindings,claim=f.claim,retain=retain,processing_begin=f.clock);self.assertEqual(r['status'],'fail');self.assertIsNotNone(r['report_pin']);self.assertEqual([k for k,i,d,h in f.retained],['record','raw_report','wrapper_failure'])
 def test_record_retention_failure_stops_all_callbacks(self):
  f=Fixture();calls=[]
  def retain(*args):calls.append(args[0]);raise OSError('invented durable write failure')
  r=w.run_stage(0,f.inputs,f.gate,f.bindings,claim=f.claim,retain=retain,processing_begin=f.clock);self.assertEqual(r['status'],'fail');self.assertTrue(r['failed_retention']);self.assertEqual(calls,['record'])
 def test_bad_receipt_indeterminate_no_callback_retry(self):
  f=Fixture();calls=[]
  def retain(*args):calls.append(args[0]);return dict(status='durable',sha256='0'*64)
  r=w.run_stage(0,f.inputs,f.gate,f.bindings,claim=f.claim,retain=retain,processing_begin=f.clock);self.assertEqual(r['status'],'fail');self.assertEqual(calls,['record'])
 def test_claim_receipt_bad_no_science(self):
  f=Fixture()
  def claim(*args):return dict(status='durable',sha256='0'*64)
  r=w.run_stage(0,f.inputs,f.gate,f.bindings,claim=claim,retain=f.retain,processing_begin=f.clock);self.assertEqual(r['status'],'fail');self.assertNotIn('audit',f.calls)
 def test_nonfinite_canonical_failure_no_claim(self):
  f=Fixture();f.inputs['packet']['nonfinite']=math_nan=float('nan');self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)
 def test_member_cap_before_callback(self):
  f=Fixture();calls=[]
  def audit(**kwargs):kwargs['retain']({'payload':'x'*(w.MEMBER+1)});return report(0)
  f.bindings=w.Bindings(audit,f.aggregate,encode,'a'*64);r=f.run();self.assertEqual(r['status'],'fail');self.assertFalse(any(k=='record'for k,i,b,h in f.retained))
 def test_record_count_cap_before71st_callback(self):
  f=Fixture()
  def audit(**kwargs):
   for i in range(71):kwargs['retain']({'position':i})
   return report(0)
  f.bindings=w.Bindings(audit,f.aggregate,encode,'a'*64);r=f.run();self.assertEqual(r['status'],'fail');self.assertEqual(sum(k=='record'for k,i,b,h in f.retained),70)
 def test_whole_stage_byte_cap(self):
  f=Fixture()
  def audit(**kwargs):
   for i in range(5):kwargs['retain']({'payload':'x'*(w.MEMBER-100)})
   return report(0)
  f.bindings=w.Bindings(audit,f.aggregate,encode,'a'*64);r=f.run();self.assertEqual(r['status'],'fail');self.assertEqual(sum(k=='record'for k,i,b,h in f.retained),4)
 def test_original_exception_preserved_without_science_retry(self):
  f=Fixture();calls=[]
  def audit(**kwargs):calls.append(1);raise RuntimeError('invented processing error')
  f.bindings=w.Bindings(audit,f.aggregate,encode,'a'*64);r=f.run();self.assertEqual(r['status'],'fail');self.assertEqual(r['exception_type'],'RuntimeError');self.assertEqual(len(calls),1)
 def test_aggregate_wrong_count_preserved_then_rejected(self):
  f=Fixture(6)
  def agg(**kwargs):r=report(6);r['checked']=395;return r
  f.bindings=w.Bindings(f.audit,agg,encode,'a'*64);r=f.run();self.assertEqual(r['status'],'fail');self.assertEqual(r['available_report']['checked'],395)
 def test_binding_fingerprint_mismatch_before_claim(self):
  f=Fixture();f.gate['binding_sha256']='f'*64;self.assertEqual(f.run()['status'],'fail');self.assertFalse(f.claimed)



class AttemptedVsDurableTests(unittest.TestCase):
 def test_failed_ack_does_not_count_durable(self):
  f=Fixture()
  def retain(*args):raise OSError('invented')
  r=w.run_stage(0,f.inputs,f.gate,f.bindings,claim=f.claim,retain=retain,processing_begin=f.clock);self.assertEqual(r['retained_count'],0);self.assertEqual(r['attempted_count'],1)
 def test_returned_partial_report_available_when_publisher_fails(self):
  f=Fixture()
  def audit(**kw):return dict(status='fail',checked=3,partial='invented',advance=dict(pass_all=False,checks=[]))
  f.bindings=w.Bindings(audit,f.aggregate,encode,'a'*64)
  def retain(*args):raise OSError('invented')
  r=w.run_stage(0,f.inputs,f.gate,f.bindings,claim=f.claim,retain=retain,processing_begin=f.clock);self.assertEqual(r['available_report']['checked'],3);self.assertEqual(r['retained_count'],0);self.assertEqual(r['attempted_count'],1)

class SignatureTests(unittest.TestCase):
 def test_fake_signature_matches_actual_public_frozen_abi(self):
  import inspect
  from pathlib import Path
  contract=json.loads((Path(__file__).parent/'PUBLIC_ABI_BINDING.json').read_bytes());f=Fixture()
  for name,function in(('audit_fit',f.audit),('aggregate',f.aggregate)):
   signature=inspect.signature(function);pos=[k for k,v in signature.parameters.items()if v.kind==inspect.Parameter.POSITIONAL_OR_KEYWORD];kw=[k for k,v in signature.parameters.items()if v.kind==inspect.Parameter.KEYWORD_ONLY];self.assertEqual(pos,contract['functions'][name]['positional']);self.assertEqual(kw,contract['functions'][name]['keyword_only'])

if __name__=='__main__':unittest.main()

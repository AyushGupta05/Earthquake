"""Invented full bridge contracts, cold context and preserved semantic pin tests."""
import copy
import sys
from types import SimpleNamespace
from contextlib import ExitStack
import unittest
import numpy as np
import fixtures as f
import bridge as b
from codec import Numeric

class BridgeTests(unittest.TestCase):
 def test_real_child_admission_bridge_retention_and_cold_lifetime(self):
  # Frozen child is exercised with invented science and an in-memory journal.
  old=sys.modules.get('control');sys.modules['control']=f.c
  try:child=f.module('child')
  finally:
   if old is None:sys.modules.pop('control',None)
   else:sys.modules['control']=old
  for index,fail in((0,False),(0,True),(6,'reject_previous')):
   x=f.Fixture();a=x.adapter();r=x.request(index);r.update(schema='shared-reference-AR-L-stage-request-v1',dispatch_begin=1000.)
   if fail=='reject_previous':x.trusted.reject_previous=True
   proofs=dict(source=x.io.pin(x.io.canonical(x.g['source_pins'])),runtime=x.g['runtime_pin'],native=x.g['input_pins']['feature_authority'],original_initialization=x.g['input_pins']['original_admission_authority'],reused924=x.g['input_pins']['comparator_authority'],resources=x.io.pin(b'invented-resources'),storage=x.io.pin(b'invented-storage'))
   def authority(scope,*args):return dict(schema='root-shared-reference-AR-L-stage-authority-v1',scope=scope,decision='authorized',expires=8400.,proofs=proofs)
   r['parent_authority']=authority(f.c.scope(x.g,r['stage'],'parent'));x.trusted.authorize=authority
   x.sd.live=lambda s:dict(unit=s['unit'],active=True,limits=s['limits'],runtime_max_seconds=s['manager_seconds'])
   saved={(index,'dispatch.json'):x.io.canonical(r)}
   def write(i,name,raw,**kwargs):
    self.assertTrue(x.loader.active or name=='claim.json');saved[i,name]=raw;return dict(status='durable',sha256=x.io.pin(raw)['sha256'])
   def read(i,name,pin=None):
    raw=saved[i,name]
    if pin is not None:self.assertEqual(x.io.pin(raw),pin)
    return raw
   j=SimpleNamespace(read=read,write=write,object=lambda i,name,value:write(i,name,x.io.canonical(value)))
   real=x.loader.load
   from contextlib import contextmanager
   @contextmanager
   def load(*args,**kwargs):
    with real(*args,**kwargs)as loaded:
     def prepare(packet,bindings,emit,processing_begin):
      self.assertTrue(x.loader.active);self.assertEqual(processing_begin,1000.)
      if fail:raise ValueError('invented science failure')
      for seed in b.SEEDS:emit('initial',f.ns.encode(dict(seed=seed,arm='L',status='initial',update=0,study=f.c.STUDY)))
      raw=f.ns.encode(dict(status='admitted',study=f.c.STUDY));emit('admission',raw);return raw
     if loaded['mode']=='producer':loaded['groups']['processor']['processor'].prepare=prepare
     yield loaded
   x.loader.load=load
   report=child.execute(r,j,a,expected_config_pin=f.c.config_pin(x.g),source_begin=1000.,clock=lambda:1000.)
   self.assertEqual(report['status'],'incomplete'if fail else'complete');self.assertTrue(x.loader.active);self.assertIn((index,'child_report.json'),saved)
   if fail=='reject_previous':
    self.assertEqual(report['failure']['reason'],'ROOT rejects current closure');self.assertNotIn('native_decode',x.events)
   elif fail:self.assertEqual(report['failure']['reason'],'invented science failure')
   else:self.assertEqual(report['result_pin'],x.io.pin(saved[0,'result.json']));self.assertEqual(len(report['callbacks']),3)
   x.stack.close();self.assertFalse(x.loader.active)
 def test_loaded_source_identity_mismatch_denied_before_raw_auth_or_decode(self):
  for wrong in('new','old'):
   x=f.Fixture();a=x.adapter()
   if wrong=='new':x.new['reference']=x.io.pin(b'wrong-new-source')
   else:x.old['reference']=x.io.pin(b'wrong-old-source')
   with self.assertRaisesRegex(ValueError,'loader_source_subjects'):a.bind(x.request(0),x.raw())
   self.assertNotIn('raw_authenticated',x.events);self.assertNotIn('native_decode',x.events);x.stack.close()
 def test_previous_authentication_happens_before_numeric_decode(self):
  x=f.Fixture();a=x.adapter();r=x.request(6);out=a.bind(r,x.raw());original=out['numeric'].decode
  def decode(*args,**kwargs):
   self.assertIn('previous_authenticated',x.events);return original(*args,**kwargs)
  out['numeric'].decode=decode;pins=[dict(stage=n,result_pin=v['result_pin'])for n,v in enumerate(r['previous'])];a.audit_authority(r,pins,out);x.stack.close()
 def test_changed_previous_raw_or_pin_scope_rejected_before_previous_auth(self):
  for wrong in('raw','scope'):
   x=f.Fixture();a=x.adapter();r=x.request(6)
   if wrong=='raw':
    x.previous[1]+=b'changed'
    with self.assertRaises((ValueError,AssertionError)):a.bind(r,x.raw())
    self.assertNotIn('previous_authenticated',x.events)
   else:
    out=a.bind(r,x.raw());pins=[dict(stage=n,result_pin=v['result_pin'])for n,v in enumerate(r['previous'])];pins[0]['result_pin']=x.io.pin(b'wrong')
    with self.assertRaises(ValueError):a.audit_authority(r,pins,out)
   x.stack.close()
 def test_all_stage_prior_decode_roles_authenticated_during_bind(self):
  needed={1:('0',),2:('0','1'),3:('0',),4:('0','3'),5:('0','2','4'),6:('0','1','2'),7:('0','3','4'),8:('0','2','4','6','7')}
  for index,expected in needed.items():
   x=f.Fixture();a=x.adapter();a.bind(x.request(index),x.raw());self.assertEqual(tuple(a.previous_raws),expected)
   self.assertLess(x.events.index('previous_authenticated'),x.events.index('native_decode'));x.stack.close()
 def test_producer_bind_auth_before_decode_originalraw_exact_frozenBindings(self):
  x=f.Fixture();a=x.adapter();out=a.bind(x.request(0),x.raw())
  self.assertLess(x.events.index('raw_authenticated'),x.events.index('native_decode'));self.assertTrue(x.loader.active)
  self.assertEqual(x.loader.calls,['producer']);self.assertEqual(out['bindings'][6],x.g['input_pins']['original_admission']['sha256'])
  self.assertEqual(out['bindings'][5],x.io.raw[x.inputs['original_admission']['path']]);self.assertEqual(out['bindings'][4],x.new);self.assertEqual(out['bindings'][7],x.old)
  self.assertEqual(len(out['reused_results']),6);self.assertEqual(len(out['strong_results']),8);self.assertEqual(len(out['origins']),14)
  self.assertTrue(all(v['packet_sha256']=='b'*64 for v in out['origins']))
  self.assertEqual(out['binding_receipt']['input_pins'],x.g['input_pins']);x.stack.close();self.assertFalse(x.loader.active);self.assertEqual(x.loader.exited,1)
 def test_independent_bind_only_native_auditor_and_transport_no_producer(self):
  x=f.Fixture();a=x.adapter();out=a.bind(x.request(6),x.raw());self.assertEqual(x.loader.calls,['independent']);self.assertIsNone(out['processor']);self.assertIsNone(out['bindings']);self.assertEqual(out['auditor'],'independentauditor')
  self.assertIs(out['numeric'].tx,f.tx);self.assertIsNone(out['numeric'].np);self.assertTrue(x.loader.active);x.stack.close()
 def test_cold_context_kept_through_use_and_once_rejection(self):
  x=f.Fixture();a=x.adapter();out=a.bind(x.request(0),x.raw());self.assertEqual(x.loader.exited,0)
  self.assertEqual(out['numeric'].decode(out['numeric'].encode({'invented':True}),x.io.pin(out['numeric'].encode({'invented':True}))['sha256']),{'invented':True})
  with self.assertRaises(ValueError):a.bind(x.request(0),x.raw())
  x.stack.close();self.assertEqual(x.loader.exited,1)
 def test_ROOT_reject_raw_provenance_before_native_or_numeric_decode(self):
  x=f.Fixture();x.trusted.reject_raw=True;a=x.adapter()
  with self.assertRaises(ValueError):a.bind(x.request(0),x.raw())
  self.assertNotIn('native_decode',x.events);self.assertTrue(x.loader.active);x.stack.close()
 def test_base_pin_mode_history_order_and_trained_original_denied(self):
  for wrong in('mode','history','base','trained'):
   x=f.Fixture()
   if wrong=='mode':x.inputs['feature_archive']['mode']=0o600
   if wrong=='history':x.history['reused_scores'][0]['arm']='P'
   if wrong in('mode','history'):
    with self.assertRaises(ValueError):x.adapter()
    continue
   a=x.adapter();raw=x.raw()
   if wrong=='base':raw['feature_archive']+=b'changed'
   else:
    value=f.ns.decode(raw['original_admission'],x.io.pin(raw['original_admission'])['sha256']);value['status']='final';new=f.ns.encode(value);x.io.raw[x.inputs['original_admission']['path']]=new
    # Independently matching rawpin does NOT make a trained checkpoint an admission.
    x.inputs['original_admission']['pin']=x.io.pin(new);x.g['input_pins']['original_admission']=x.io.pin(new);a=x.adapter();raw=x.raw()
   with self.assertRaises(ValueError):a.bind(x.request(0),raw)
   x.stack.close()
 def test_owned9Systemd_only_delegation_and_exact_launchrequest(self):
  x=f.Fixture();a=x.adapter();request=x.request(0);a.run(request,360)
  self.assertEqual(len(x.sd.owned),9);name,argv,timeout,unit=x.sd.calls[0];self.assertEqual(name,'run');self.assertIn('RuntimeMaxSec=360',argv);self.assertEqual(unit,request['stage']['unit']);self.assertIn('CUDA_VISIBLE_DEVICES=',str(argv))
  a.stop(unit,0);a.inspect(unit,5);a.live(unit)
  for method,args in((a.stop,('foreign.service',0)),(a.inspect,('foreign.service',5)),(a.live,('foreign.service',))):
   with self.assertRaises(ValueError):method(*args)
  original=x.trusted.launch;x.trusted.launch=lambda request:dict(original(request),request_pin=x.io.pin(b'wrong'))
  with self.assertRaises(ValueError):a.run(request,360)
 def test_documents_and_authorization_prior_delegate_no_default_flags(self):
  x=f.Fixture();a=x.adapter();scope={'invented':True};self.assertEqual(a.documents(scope),x.documents);self.assertEqual(a.authorize(scope,x.documents,1000.),{'delegated':'ROOT'});self.assertEqual(a.prior_closed(x.g,0,{},{}),{'delegated':'ROOT'})
 def test_actualdecoded_origins_projection_mutation_or_population_denied(self):
  for wrong in('origins','counts'):
   x=f.Fixture();real=x.trusted.project_comparators
   def changed(*args):
    value=real(*args)
    if wrong=='origins':value['origins'][0]['packet_sha256']='a'*64
    else:value['strong_results'][0]['predictions'].pop()
    return value
   x.trusted.project_comparators=changed;a=x.adapter()
   with self.assertRaises(ValueError):a.bind(x.request(0),x.raw())
   x.stack.close()
 def test_PERFIT_authority_original_closure_and_rawsemanticSHA_only_after_ROOT(self):
  for index,ck,score in((6,1,2),(7,3,4)):
   x=f.Fixture();a=x.adapter();r=x.request(index);out=a.bind(r,x.raw());pins=[dict(stage=n,result_pin=v['result_pin'])for n,v in enumerate(r['previous'])];authority=a.audit_authority(r,pins,out)
   self.assertEqual(authority['checkpoint_sha256'],x.io.pin(x.previous[ck])['sha256']);self.assertEqual(authority['score_sha256'],x.io.pin(x.previous[score])['sha256'])
   self.assertEqual(authority['original_admission_sha256'],x.g['input_pins']['original_admission']['sha256']);self.assertEqual(authority['original_execution_closure_sha256'],'c'*64)
   self.assertTrue(authority['optimizer_history_verified']);self.assertIn('ROOT_audit_verified',x.events);self.assertIn('previous_authenticated',x.events);x.stack.close()
 def test_aggregate_authority_two_seeds_old924_and14_origins_not_relabelled(self):
  x=f.Fixture();a=x.adapter();r=x.request(8);out=a.bind(r,x.raw());pins=[dict(stage=n,result_pin=v['result_pin'])for n,v in enumerate(r['previous'])];authority=a.audit_authority(r,pins,out)
  self.assertEqual([(v['seed'],v['arm'])for v in authority['fits']],[(20261012,'L'),(20261013,'L')]);self.assertEqual(authority['origins_sha256'],x.g['input_pins']['comparator_origins']['sha256']);self.assertEqual(authority['closed_comparator_report_sha256'],x.g['input_pins']['closed_comparator_report']['sha256']);self.assertTrue(authority['comparators_verified']);x.stack.close()
 def test_previous_or_finalROOT_verification_denial_never_promotes(self):
  for wrong in('previous','audit','change'):
   x=f.Fixture();a=x.adapter();r=x.request(6)
   if wrong=='previous':
    x.trusted.reject_previous=True
    with self.assertRaises(ValueError):a.bind(r,x.raw())
    x.stack.close();continue
   out=a.bind(r,x.raw());pins=[dict(stage=n,result_pin=v['result_pin'])for n,v in enumerate(r['previous'])]
   if wrong=='audit':x.trusted.reject_audit=True
   if wrong=='change':x.trusted.change_audit=True
   with self.assertRaises(ValueError):a.audit_authority(r,pins,out)
   x.stack.close()
 def test_data_read_exact400spec_and_unknown_load_pin_denied(self):
  x=f.Fixture();a=x.adapter();self.assertEqual(a.load('original_admission',x.g['input_pins']['original_admission']),x.io.raw[x.inputs['original_admission']['path']])
  for name,pin in(('unknown',x.io.pin(b'unknown')),('original_admission',x.io.pin(b'wrong'))):
   with self.assertRaises(ValueError):a.load(name,pin)

class CodecTests(unittest.TestCase):
 def test_codec_exact_frozen_transport_parity_bothfacades(self):
  io=f.IO();producer=Numeric(io,np=np);independent=Numeric(io,transport=f.tx);value={'x':np.asarray([1.,-2.]),'s':np.asarray(300.,dtype='<f4'),'i':np.asarray([1,2],dtype='<i8'),'b':True}
  raw=f.tx.canonical(value);self.assertEqual(producer.encode(value),raw);self.assertEqual(independent.encode(value),raw)
  for codec in(producer,independent):
   decoded=codec.decode(raw,io.pin(raw)['sha256']);self.assertEqual(decoded['x'].tobytes(),value['x'].tobytes());self.assertIs(type(decoded['b']),bool)
 def test_no_pickle_dtype_badhex_nonfinite_noncanonical_wronghash(self):
  io=f.IO();codec=Numeric(io,np=np)
  for value in({'__array__':'O','shape':[1],'hex':'00'}, {'__array__':'<f8','shape':[1],'hex':'g'*16},{'__array__':'<f8','shape':[1],'hex':'000000000000f07f'}):
   raw=io.canonical(value)
   with self.assertRaises(ValueError):codec.decode(raw,io.pin(raw)['sha256'])
  with self.assertRaises(ValueError):codec.decode(b'{"x": 1}',io.pin(b'{"x": 1}')['sha256'])
  with self.assertRaises(ValueError):codec.decode(b'{}','0'*64)
 def test_historical16M_cap_does_not_raise_producer2Mcodec(self):
  io=f.IO();codec=Numeric(io,np=np);value={'text':'x'*(2*1024*1024+1)};raw=codec.encode(value)
  self.assertGreater(len(raw),2*1024*1024);self.assertEqual(codec.decode(raw,io.pin(raw)['sha256']),value)
  with self.assertRaises(ValueError):f.ns.decode(raw,io.pin(raw)['sha256'])
  with self.assertRaises(ValueError):codec.decode(raw,io.pin(raw)['sha256'],cap=2*1024*1024)
  with self.assertRaises(ValueError):codec.encode({'text':'x'*(16*1024*1024)})

if __name__=='__main__':unittest.main()

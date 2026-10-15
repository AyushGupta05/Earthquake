"""Invented IO/ROOT facts/cold contexts only; no actual files/models/OS calls."""
from contextlib import contextmanager,ExitStack
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import bridge as b
from codec import Numeric

BASE=Path(__file__).parent
PINS=json.loads((BASE/'INHERITED_PINS.json').read_text())
def module(name):
 path=BASE/'reference'/(name+'.py');raw=path.read_bytes();pin=PINS['reference/'+name+'.py'];assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256']
 spec=importlib.util.spec_from_file_location('fixture_'+name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
baseio=module('secure_io');sys.modules['secure_io']=baseio;c=module('control');ns=module('numeric_state')
previous=sys.modules.get('math_core');sys.modules['math_core']=SimpleNamespace(need=baseio.need)
try:tx=module('transport')
finally:
 if previous is None:sys.modules.pop('math_core',None)
 else:sys.modules['math_core']=previous

class IO:
 pin=staticmethod(baseio.pin);pin_check=staticmethod(baseio.pin_check);parts=staticmethod(baseio.parts);canonical=staticmethod(baseio.canonical);json_read=staticmethod(baseio.json_read);need=staticmethod(baseio.need)
 def __init__(self):self.raw={};self.reads=[]
 def read_file(self,spec,cap):
  self.reads.append(spec['path']);raw=self.raw[spec['path']];assert spec['mode']==0o400 and len(raw)<=cap and self.pin(raw)==spec['pin'];return raw
 def spec(self,name,value):
  raw=ns.encode(value)if type(value)is not bytes else value;path='/fake/invented/'+name;self.raw[path]=raw;return dict(path=path,pin=self.pin(raw),mode=0o400)

class SD:
 def __init__(self):self.owned=set();self.calls=[]
 def own(self,unit):
  import re
  assert re.fullmatch('eew-marked-[a-z0-9-]{1,48}-[0-9]{2}\\.service',unit);self.owned.add(unit)
 def run(self,args,timeout,unit):assert unit in self.owned;self.calls.append(('run',args,timeout,unit));return {'invented':True}
 def stop(self,unit,timeout):assert unit in self.owned;self.calls.append(('stop',unit,timeout));return {}
 def inspect(self,unit,timeout):assert unit in self.owned;self.calls.append(('inspect',unit,timeout));return {}
 def live(self,spec):assert spec['unit']in self.owned;self.calls.append(('live',spec));return {'unit':spec['unit']}

class Loader:
 def __init__(self,fixture):self.f=fixture;self.active=False;self.calls=[];self.entered=0;self.exited=0
 @contextmanager
 def load(self,mode,config,**kwargs):
  assert not self.calls;self.calls.append(mode);self.entered+=1;self.active=True
  f=self.f;native=SimpleNamespace(np=np)
  def load(archive,manifest,pins,processing_begin):
   assert self.active and f.authenticated;f.events.append('native_decode');assert archive==f.io.raw[f.inputs['feature_archive']['path']];return copy.deepcopy(f.packet)
  native.load=load
  if mode=='producer':
   op=SimpleNamespace(ns=ns,packet_hash=lambda p:f.packet_sha,Bindings=lambda *args:args)
   groups=dict(native={'packet_io':native},processor={'processor':op,'numeric_state':ns},gaussian={'gaussian_operator':'unchangedoperator'},reference={'ar_core':'Lreference'},kernel={'kernel':'frozenkernel'})
  else:groups=dict(native={'packet_io':native},auditor={'transport':tx,'packet_digest':SimpleNamespace(sha=lambda p:f.packet_sha),'l_auditor':'independentauditor'})
  try:yield dict(mode=mode,groups=groups,source_pins=f.new,original_source_pins=f.old,observed_versions={},adapter_config_pin=f.loader_pin)
  finally:self.active=False;self.exited+=1

class Trusted:
 def __init__(self,f):self.f=f;self.reject_raw=False;self.reject_previous=False;self.reject_audit=False;self.change_audit=False
 def documents(self,s):return self.f.documents
 def authorize(self,*a):return {'delegated':'ROOT'}
 def prior_closed(self,*a):return {'delegated':'ROOT'}
 def launch(self,request):return dict(python='/fake/python',code='pass',code_pin=self.f.io.pin(b'pass'),request_pin=self.f.io.pin(self.f.io.canonical(request)))
 def authenticate_raw(self,scope,base,history,now):
  if self.reject_raw:raise ValueError('ROOT rejects provenance')
  f=self.f;assert set(base)==c.INPUTS;assert len(history['reused_scores'])==6;f.authenticated=True;f.events.append('raw_authenticated')
  return dict(schema='root-L-bridge-input-authentication-v1',scope=scope,decision='authorized',packet_sha256=f.packet_sha,original_execution_closure_sha256='c'*64,source_pins=f.new,original_source_pins=f.old,proof_pin=f.io.pin(b'held-input-proof'))
 def project_comparators(self,scope,packet,six,stronger,closed,origins,receipt):
  assert self.f.authenticated;self.f.events.append('ROOT_projection');return dict(reused_results=six,strong_results=stronger,origins=origins)
 def previous_raw(self,request,index,pin):
  raw=self.f.previous[index];assert self.f.io.pin(raw)==pin;return raw
 def authenticate_previous(self,scope,raw,receipt,now):
  if self.reject_previous:raise ValueError('ROOT rejects current closure')
  self.f.events.append('previous_authenticated');return dict(schema='root-L-bridge-previous-authentication-v1',scope=scope,decision='authorized',proof_pin=self.f.io.pin(b'held-previous-proof'))
 def verify_audit_authority(self,scope,candidate,raw,receipt,now):
  if self.reject_audit:raise ValueError('ROOT rejects audit semantic pins')
  f=self.f;f.events.append('ROOT_audit_verified');authority=copy.deepcopy(candidate)
  flags=('verified','native_verified','optimizer_history_verified','gradient_probes_verified','original_initialization_verified')if scope['stage']['index']<8 else('verified','native_verified','original_initialization_verified','comparators_verified')
  authority.update({k:True for k in flags})
  if self.change_audit:authority['admission_sha256']='0'*64
  return dict(schema='root-L-bridge-audit-verification-v1',scope=scope,decision='authorized',authority=authority,proof_pin=f.io.pin(b'held-audit-proof'))

class Fixture:
 def __init__(self):
  self.io=IO();self.stack=ExitStack();self.sd=SD();self.events=[];self.authenticated=False;self.packet_sha='a'*64;self.packet=dict(schema='earthquake-TRAIN115-marked-noise-observations-v1',study='earthquake-TRAIN115-marked-noise-study-v1',invented=True)
  self.new={k:self.io.pin(k.encode())for k in('operator','native_validator','reference','kernel','processor','protocol','numeric_state')};self.old={k:self.io.pin(k.encode())for k in('operator','native_validator','reference','processor','protocol')}
  original=dict(study='earthquake-TRAIN115-marked-noise-fitting-v2',status='admitted',source_pins=self.old,packet_sha256=self.packet_sha,parameters={'invented':np.asarray([1.,2.])})
  self.six=[dict(seed=s,arm=a,status='complete',no_optimizer=True,packet_sha256=self.packet_sha,predictions=[{'invented':True}]*66)for s,a in b.REUSED]
  strong=[dict(seed=s,arm=a,status='complete',no_optimizer=True,packet_sha256=self.packet_sha,predictions=[{'invented':True}]*66)for s,a in b.STRONG]
  self.origins=[dict(seed=s,arm=a,origin='held-original-not-relabelled',packet_sha256='b'*64)for s,a in b.REUSED+b.STRONG]
  closed=dict(schema='marked-sixfit-independent-aggregate-v1',status='pass',fits=[{'records':[{}]*66}]*6,stronger=[{'records':[{}]*66}]*8)
  self.inputs={k:self.io.spec(k,{'invented':k})for k in c.INPUTS};self.inputs['original_admission']=self.io.spec('original_admission',original);self.inputs['closed_comparator_report']=self.io.spec('closed_comparator_report',closed);self.inputs['comparator_origins']=self.io.spec('comparator_origins',self.origins)
  self.history=dict(reused_scores=[dict(seed=s,arm=a,spec=self.io.spec('reused_%d'%i,record))for i,((s,a),record)in enumerate(zip(b.REUSED,self.six))],stronger_envelope=self.io.spec('stronger_envelope',strong))
  self.documents={k:self.io.canonical({'invented':k})for k in('funding','publication','protocol','root_context')}
  self.g=dict(schema='shared-reference-AR-L-nine-stage-config-v1',study=c.STUDY,feature_schema=self.packet['schema'],feature_study=self.packet['study'],experiment_id='bridge-invented',whole_begin=1000.,lease_deadline=8400.,source_pins={k:self.io.pin(k.encode())for k in c.SOURCES},runtime_pin=self.io.pin(b'runtime'),input_pins={k:v['pin']for k,v in self.inputs.items()},funding_pin=self.io.pin(self.documents['funding']),publication_pin=self.io.pin(self.documents['publication']),protocol_pin=self.io.pin(self.documents['protocol']),storage_limit_bytes=9*64*1024*1024)
  self.loader_config=dict(runtime=dict(python='/fake/python'),sources={},role_subjects={},original_source_pins=self.old);self.loader_pin=self.io.pin(self.io.canonical(self.loader_config));self.loader=Loader(self);self.trusted=Trusted(self)
  self.previous={i:ns.encode({'stage':i})for i in range(8)};self.previous[0]=ns.encode({'status':'admitted','study':c.STUDY})
  for score,audit,seed in((2,6,20261012),(4,7,20261013)):
   self.previous[score]=ns.encode(dict(seed=seed,arm='L',checkpoint_sha256=self.io.pin(self.previous[score-1])['sha256']))
   self.previous[audit]=ns.encode(dict(seed=seed,arm='L',authority_sha256='d'*64))
 def check(self):self.events.append('checked')
 def adapter(self):return b.make_adapter(self.g,expected_config_pin=c.config_pin(self.g),input_specs=self.inputs,historical_specs=self.history,loader_config=self.loader_config,expected_loader_config_pin=self.loader_pin,io=self.io,sb='positivelybound',runtime_adapter=self.loader,control=c,systemd=self.sd,trusted=self.trusted,stack=self.stack,check=self.check,source_begin=1000.,prefix='eew_l_invented',python='/fake/python',clock=lambda:1000.)
 def request(self,index):return dict(config=self.g,config_pin=c.config_pin(self.g),stage=c.spec(self.g,index),previous=[dict(stage=i,result_pin=self.io.pin(self.previous[i]))for i in range(index)])
 def raw(self):return {k:self.io.read_file(v,16*1024*1024)for k,v in self.inputs.items()}

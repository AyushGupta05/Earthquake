"""Invented in-memory ROOT primitives, custody, runtime and scientific returns.
No actual data, model/optimizer import, provider, financial values or credentials.
"""
import copy
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import root_glue as glue
import comparator_population as population

BASE=Path(__file__).parent
sys.path.insert(0,str(BASE/'reference/bridge'))
import bridge
import codec
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
f=module('bridge_invented_fixtures',BASE/'reference/bridge/fixtures.py')
old=sys.modules.get('control');sys.modules['control']=f.c
try:child=module('frozen_child',BASE/'reference/bridge/reference/child.py')
finally:
 if old is None:sys.modules.pop('control',None)
 else:sys.modules['control']=old
projection=module('frozen_projection',BASE/'reference/projection/projection.py')
sys.modules['projection']=projection
pf=module('projection_invented_fixtures',BASE/'reference/projection/test_projection.py')

class Journal:
 def __init__(self,x):self.x=x;self.saved={};self.events=[]
 def read(self,i,name,pin=None):
  raw=self.saved[i,name]
  if pin is not None:assert self.x.io.pin(raw)==pin
  return raw
 def write(self,i,name,raw,**kwargs):
  assert type(raw)is bytes and len(raw)<=16*1024*1024
  assert (i,name)not in self.saved or kwargs.get('replace')is True
  self.saved[i,name]=raw;self.events.append((i,name,self.x.runtime.active))
  return dict(status='durable',sha256=self.x.io.pin(raw)['sha256'])
 def object(self,i,name,value):return self.write(i,name,self.x.io.canonical(value))
 def inventory(self):return {'invented_members':len(self.saved)}
 def exists(self,i,name):return(i,name)in self.saved

class Custody:
 def __init__(self,x):self.x=x;self.snapshots={}
 def snapshot(self,index):return copy.deepcopy(self.snapshots[index])

class Primitives:
 """Only invented test evidence is accepted; never an actual authorizer."""
 def __init__(self,x):self.x=x;self.reject=None;self.calls=[]
 def attest(self,kind,scope,held,claims,evidence=None):
  self.calls.append(kind)
  if self.reject==kind:raise ValueError('invented '+kind+' rejected')
  pin=evidence if evidence is not None else held['evidence'][kind]['pin']
  return dict(schema='root-L-primitive-verification-v1',kind=kind,scope_pin=self.x.io.pin(self.x.io.canonical(scope)),evidence_pin=pin,claims=claims)
 def source_runtime(self,scope,held,modules,raw,now):
  assert raw==self.x.io.raw[held['evidence']['source_runtime']['path']]
  return self.attest('source_runtime',scope,held,dict(source=self.x.io.pin(self.x.io.canonical(held['execution']['source_pins'])),runtime=held['execution']['runtime_pin']))
 def current(self,scope,held,documents,raw,now):
  assert documents==self.x.documents
  return self.attest('current',scope,held,dict(expires=8400.,resources=self.x.io.pin(b'invented resource observation'),storage=self.x.io.pin(b'invented storage observation')))
 def inputs(self,scope,held,base,history,raw,projection_raw,now):
  assert all(self.x.io.pin(v)==held['inputs'][k]['pin']for k,v in base.items())
  assert projection_raw==self.x.io.raw[held['evidence']['projection']['path']]
  return self.attest('inputs',scope,held,copy.deepcopy(held['facts']))
 def prior(self,scope,held,snapshot,inventory,now):
  # Invented custody is independently held by this fixture object.
  index=scope['stage'];assert snapshot==self.x.custody.snapshots[index]
  files=snapshot['files'];claims=dict(known_return_pin=snapshot['known_pin'],closed_pin=files['closed.json']['pin'],result_pin=files['result.json']['pin'])
  return self.attest('prior',scope,held,claims,snapshot['known_pin'])
 def audit(self,scope,held,raw,receipt,prior,evidence,now):
  io=self.x.io;i=scope['stage']['index'];facts=held['facts'];candidate=dict(schema='root-shared-reference-AR-L-audit-authority-v1'if i<8 else'root-shared-reference-AR-L-aggregate-authority-v1',packet_sha256=facts['packet_sha256'],admission_sha256=io.pin(raw['0'])['sha256'],original_admission_sha256=held['execution']['input_pins']['original_admission']['sha256'],original_execution_closure_sha256=facts['original_execution_closure_sha256'],source_pins={k:held['execution']['source_pins'][k]for k in glue.ROLES},original_source_pins=held['loader']['original_source_pins'])
  if i<8:
   ck,score=('1','2')if i==6 else('3','4');candidate.update(checkpoint_sha256=io.pin(raw[ck])['sha256'],score_sha256=io.pin(raw[score])['sha256']);flags=('verified','native_verified','optimizer_history_verified','gradient_probes_verified','original_initialization_verified')
  else:
   candidate.update(closed_comparator_report_sha256=held['execution']['input_pins']['closed_comparator_report']['sha256'],origins_sha256=held['execution']['input_pins']['comparator_origins']['sha256'],fits=[])
   for seed,score_idx,audit_idx in((20261012,'2','6'),(20261013,'4','7')):
    a=io.json_read(raw[audit_idx]);score=io.json_read(raw[score_idx]);candidate['fits'].append(dict(seed=seed,arm='L',audit_sha256=io.pin(raw[audit_idx])['sha256'],authority_sha256=a['authority_sha256'],score_sha256=io.pin(raw[score_idx])['sha256'],checkpoint_sha256=score['checkpoint_sha256']))
   flags=('verified','native_verified','original_initialization_verified','comparators_verified')
  candidate.update({k:True for k in flags});return self.attest('audit',scope,held,dict(authority=candidate))

class Runtime:
 AUDIT_NAMES=('math_core','transport','packet_digest','packet','metrics','auditor','proper_core','ar_core','l_auditor')
 def __init__(self,x):self.x=x;self.active=False;self.calls=[];self.exits=0;self.extra=0
 def _source(self,*args):assert self.active;return {'invented_source':b'pinned'}
 def _group(self,*args):assert self.active;self.extra+=1;return self.auditor_group()
 def auditor_group(self):
  x=self.x;np=f.np;m=pf.core;tx=pf.tx;pd=pf.pd;pkt=pf.pkt;metrics=pf.metrics;old=pf.old
  # Exact selected independent functions are exercised; models are invented.
  old.np=np;old.core=m;old.pkt=pkt;old.tx=tx;old.packet_digest=pd;old.metrics=metrics
  proper=SimpleNamespace(np=np);ar=SimpleNamespace(np=np,p=proper)
  a=SimpleNamespace(np=np,old=old,core=m,ar=ar,pkt=pkt,packet_digest=pd,tx=tx,metrics=metrics,comparators_checked=pf.audit.comparators_checked)
  def audit_fit(score,packet,admission,original,checkpoint,authority,processing_begin,retain):
   assert self.active and x.authenticated;assert 'torch'not in sys.modules
   records=[{'invented_audit_record':n}for n in range(66)]
   for record in records:retain(record)
   result=dict(schema='shared-reference-AR-L-independent-audit-v1',status='pass',checked=66,seed=score['seed'],arm='L',records=records,authority_sha256=x.io.pin(tx.canonical(authority))['sha256']);retain(result);return result
  def aggregate(*args,processing_begin,retain):
   assert self.active and 'torch'not in sys.modules
   result=dict(schema='shared-reference-AR-L-independent-aggregate-v1',status='pass',checked=132,record_counts=dict(new_L=132,reused_SPD=396,reused_BFHT=528,total=1056),paired=[{}]*42,advance=dict(checks=[{}]*24,additional=[{}]*18,pass_all=False));retain(result);return result
  a.audit_fit=audit_fit;a.aggregate=aggregate
  return dict(math_core=m,transport=tx,packet_digest=pd,packet=pkt,metrics=metrics,auditor=old,proper_core=proper,ar_core=ar,l_auditor=a)
 @contextmanager
 def load(self,mode,config,**kwargs):
  self.active=True;self.calls.append(mode);x=self.x;native=SimpleNamespace(np=f.np)
  def load(*args,**kwargs):
   assert self.active and x.authenticated;x.events.append('native_decode');return copy.deepcopy(x.packet)
  native.load=load
  if mode=='independent':groups=dict(native={'packet_io':native},auditor=self.auditor_group())
  else:
   def prepare(packet,bindings,emit,processing_begin):
    assert self.active
    if x.fail_science:raise ValueError('invented dependency failure')
    for seed in(20261012,20261013):emit('initial',f.ns.encode(dict(study=f.c.STUDY,status='initial',seed=seed,arm='L',update=0)))
    raw=f.ns.encode(dict(study=f.c.STUDY,status='admitted',schema={'dev':list(range(65,87))}));emit('admission',raw);return raw
   op=SimpleNamespace(packet_hash=pf.pd.sha,Bindings=lambda *a:a,prepare=prepare)
   groups=dict(native={'packet_io':native},processor={'processor':op,'numeric_state':f.ns},gaussian={'gaussian_operator':'invented'},reference={'ar_core':'invented'},kernel={'kernel':'invented'})
  try:yield dict(mode=mode,groups=groups,source_pins=x.new,original_source_pins=x.old,adapter_config_pin=x.loader_pin,observed_versions={})
  finally:self.active=False;self.exits+=1

class Fixture(f.Fixture):
 def __init__(self):
  super().__init__();expected,args=pf.fixture();_,packet,six,strong,report,origins,_=args
  packet.update(schema=self.g['feature_schema'],study=self.g['feature_study']);self.packet=packet;self.packet_sha=pf.pd.sha(packet)
  self.old=copy.deepcopy(six[0]['source_pins']);self.new.update({k:self.old[k]for k in('operator','native_validator')});self.g['source_pins'].update(self.new)
  original=dict(study='earthquake-TRAIN115-marked-noise-fitting-v2',status='admitted',source_pins=self.old,packet_sha256=self.packet_sha,parameters={'invented':f.np.asarray([1.,2.])})
  self.inputs['original_admission']=self.io.spec('original_admission',original)
  joins=expected['joins']
  for i,(origin,join)in enumerate(zip(origins,joins)):
   join['comparison_packet_sha256']=self.packet_sha;join['comparison_closure']['packet_sha256']=self.packet_sha
   if i<6:
    origin['packet_sha256']=self.packet_sha;join['historical_closure']['packet_sha256']=self.packet_sha
    six[i].update(packet_sha256=self.packet_sha,source_pins=self.old,admission_sha256=self.inputs['original_admission']['pin']['sha256'])
   else:strong[i-6]['closure']['packet_sha256']=self.packet_sha
  self.inputs['closed_comparator_report']=self.io.spec('closed_comparator_report',report);self.inputs['comparator_origins']=self.io.spec('comparator_origins',origins)
  self.history=dict(reused_scores=[dict(seed=s,arm=a,spec=self.io.spec('score%d'%i,v))for i,((s,a),v)in enumerate(zip(bridge.REUSED,six))],stronger_envelope=self.io.spec('stronger',strong))
  self.g['input_pins']={k:v['pin']for k,v in self.inputs.items()};self.loader_config=dict(runtime={'python':'/fake/python'},sources=dict(auditor={'invented':True},processor={'files':{'processor.py':population.SOURCE_PROCESSOR_PIN}}),role_subjects={},original_source_pins=self.old);self.loader_pin=self.io.pin(self.io.canonical(self.loader_config))
  self.runtime=Runtime(self);self.journal=Journal(self);self.custody=Custody(self);self.primitives=Primitives(self);self.fail_science=False
  specs={n:self.io.spec('module_'+n,b'# invented support source\n')for n in glue.MODULES}
  documents={k:self.io.spec('document_'+k,v)for k,v in self.documents.items()}
  evidence={k:self.io.spec('proof_'+k,{'schema':'invented-'+k})for k in('source_runtime','current','inputs','audit')}
  evidence['projection']=self.io.spec('proof_projection',dict(schema='root-L-held-comparator-joins-v1',joins=joins,comparison_schema={'dev':list(range(65,87))}))
  self.held=dict(schema='root-held-L-composition-v1',execution=self.g,execution_pin=f.c.config_pin(self.g),loader=self.loader_config,loader_pin=self.loader_pin,inputs=self.inputs,history=self.history,documents=documents,evidence=evidence,facts=dict(packet_sha256=self.packet_sha,original_execution_closure_sha256='c'*64),launch=dict(bootstrap=self.io.spec('bootstrap_source',b'# invented bootstrap\n'),primitive_source=self.io.spec('primitive_source',b'# invented private verifier source\n'),modules=specs,store_directory='/fake/journal',prefix='eew_l_invented',python='/fake/python',commands={}))
  self.root_spec=self.io.spec('held_root',self.io.canonical(self.held));self.root_pin=self.root_spec['pin']
  self.modules=dict(secure_io=self.io,control=f.c,projection=projection,comparator_population=population,bridge=bridge,child=child,runtime_adapter=self.runtime,source_binding='inventedbound')
  self.oldinputs=self.primitives.inputs
  def verified(*args):
   result=self.oldinputs(*args);self.authenticated=True;self.events.append('raw_authenticated');return result
  self.primitives.inputs=verified
  for i,raw in self.previous.items():self.closed(i,raw)
 def closed(self,index,result):
  gpin=f.c.config_pin(self.g);io=self.io
  dispatch=io.canonical({'invented_dispatch':index});claim=io.canonical({'invented_claim':index})
  childreport=io.canonical(dict(status='complete',stage=index,config_pin=gpin,result_pin=io.pin(result),claim_pin=io.pin(claim)))
  closed=dict(schema='shared-reference-AR-L-parent-return-v1',status='complete',stage=index,unit=f.c.spec(self.g,index)['unit'],config_pin=gpin,cleanup_verified=True,errors=[],no_retry=True,result_pin=io.pin(result),claim_pin=io.pin(claim),child_report_pin=io.pin(childreport))
  raws={'closed.json':io.canonical(closed),'result.json':result,'child_report.json':childreport,'claim.json':claim,'dispatch.json':dispatch}
  inventory={'invented_stage_members':len(raws)};known=io.canonical(dict(schema='root-L-known-parent-return-v1',stage=index,config_pin=gpin,returned=closed,inventory=inventory))
  files={n:io.spec('custody_%d_%s'%(index,n),v)for n,v in raws.items()};self.custody.snapshots[index]=dict(known_raw=known,known_pin=io.pin(known),files=files,inventory=inventory)
  for name,raw in raws.items():self.journal.saved[index,name]=raw
 def root(self,source_begin=1000.):return glue.Root(self.held,expected_pin=self.root_pin,root_spec=self.root_spec,io=self.io,control=f.c,projection=projection,population=population,primitives=self.primitives,custody=self.custody,journal=self.journal,modules=self.modules,source_begin=source_begin,clock=lambda:1000.)
 def request(self,index):
  r=super().request(index);r.update(schema='shared-reference-AR-L-stage-request-v1',dispatch_begin=1000.)
  root=self.root();scope=f.c.scope(self.g,r['stage'],'parent');r['parent_authority']=root.authorize(scope,root.documents(scope),1000.)
  for n,item in enumerate(r['previous']):
   snap=self.custody.snapshots[n];item.update(closed_pin=snap['files']['closed.json']['pin'],claim_pin=snap['files']['claim.json']['pin'],known_return_pin=snap['known_pin'])
  self.journal.saved={k:v for k,v in self.journal.saved.items()if k[0]<index}
  self.journal.saved[index,'dispatch.json']=self.io.canonical(r)
  self.sd.live=lambda s:dict(unit=s['unit'],active=True,limits=s['limits'],runtime_max_seconds=s['manager_seconds'])
  return r

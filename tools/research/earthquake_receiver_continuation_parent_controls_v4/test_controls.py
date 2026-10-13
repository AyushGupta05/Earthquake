"""Invented state/claim/runtime/resource/NPZ/control tests; no actual models/jobs."""
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
import custody as c
import controller as p
import stage_child as child
import invented

class ControlsTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.root=Path(self.t.name);self.g,self.begin,self.summary=invented.fixture(self.root)
 def tearDown(self):self.t.cleanup()
 def test_fixed18_identity_order_original_score_only(self):
  self.assertEqual(len(p.PLAN),18);self.assertEqual(p.PLAN[:3],tuple(('score',20261012,a)for a in('B','F','H')));self.assertEqual(sum(s=='train'for s,_,_ in p.PLAN),7);self.assertEqual(p.PLAN[-1],('aggregate',None,None));p.gate_checked(self.g,self.begin)
 def test_barred_partial178_never_claims(self):
  for key,value in [('original_independent_scores',1),('original_replay_agreed',False),('passed',False),('native_observations_verified',False)]:
   summary=copy.deepcopy(self.summary);summary[key]=value;invented.bind_summary(self.g,summary)
   with self.assertRaises(ValueError):p.claim_stage(self.g,self.begin)
   self.assertEqual(list(Path(self.g['experiment_root']).iterdir()),[])
  self.g['admission']['original_replay_verified']=False
  with self.assertRaises(ValueError):p.claim_stage(self.g,self.begin)
 def test_role_types_and_identity_tamper(self):
  for key,value in [('index',True),('seed',True),('arm','C'),('stage','train'),('score_results',[]),('source_commit','bad')]:
   g=copy.deepcopy(self.g);g[key]=value
   with self.assertRaises(ValueError):p.gate_checked(g,self.begin)
 def test_durable_claim_exact_once_before_model(self):
  out,claim,_=p.claim_stage(self.g,self.begin);self.assertEqual(claim['gate_pin'],c.pin((out/'parent_gate.private.json').read_bytes()));self.assertEqual(claim['study_fingerprint'],p.study_fingerprint(self.g));self.assertEqual((Path(self.g['experiment_root'])/'claim_00_score.private.json').stat().st_mode&0o777,0o400)
  with self.assertRaises(ValueError):p.claim_stage(self.g,self.begin)
  ack=p.ClaimAcknowledgement(claim,20261012,'B','scoring');self.assertTrue(ack(20261012,'B','scoring'))
  with self.assertRaises(ValueError):ack(20261012,'B','scoring')
 def test_failed_ack_is_consumed_no_retry(self):
  _,claim,_=p.claim_stage(self.g,self.begin);ack=p.ClaimAcknowledgement(claim,20261012,'B','scoring')
  with self.assertRaises(ValueError):ack(True,'B','scoring')
  with self.assertRaises(ValueError):ack(20261012,'B','scoring')
 def test_clock_source_whole_and_order(self):
  with self.assertRaises(ValueError):p.tick(True,self.begin,900)
  with self.assertRaises(ValueError):p.tick(self.begin,self.begin+1,900)
  with self.assertRaises(ValueError):p.tick(time.monotonic()-901,time.monotonic()-901,900)
  with self.assertRaises(ValueError):p.tick(time.monotonic(),time.monotonic()-7201,900)
 def test_full_study_source_scorer_fingerprint(self):
  old=p.study_fingerprint(self.g)
  for key in('runtime','sources','packet','admission'):
   g=copy.deepcopy(self.g)
   if key=='runtime':g[key]['canonical_sha256']='4'*64
   elif key=='sources':g[key]['parent']['files']['s_000.txt']['sha256']='4'*64
   elif key=='packet':g[key]['archive']['pin']['sha256']='4'*64
   else:g[key]['scorer_binding']='changed'
   self.assertNotEqual(p.study_fingerprint(g),old)
 def test_source_membership_exact_transport_manifest_only(self):
  spec=self.g['sources']['parent'];child.source_verify(spec,lambda:None);d=Path(spec['directory']);invented.write(d,'parent_upload_manifest.private.json',spec['files']);child.source_verify(spec,lambda:None)
  invented.write(d,'parent_runtime_pins_v3.private.json',{})
  with self.assertRaises(ValueError):child.source_verify(spec,lambda:None)
 def test_source_transport_manifest_wrong_map_and_symlink(self):
  spec=self.g['sources']['parent'];d=Path(spec['directory']);invented.write(d,'parent_upload_manifest.private.json',{})
  with self.assertRaises(ValueError):child.source_verify(spec,lambda:None)
  (d/'parent_upload_manifest.private.json').unlink();(d/'link').symlink_to(d/'s_000.txt')
  with self.assertRaises(ValueError):child.source_verify(spec,lambda:None)
 def test_optional_unadmitted_no_fallback(self):
  g=copy.deepcopy(self.g);g['admission']['scorer_mode']='reviewed_optional'
  with self.assertRaises(ValueError):p.gate_checked(g,self.begin)
  g=copy.deepcopy(self.g);g['sources']['optional']={}
  with self.assertRaises(ValueError):p.gate_checked(g,self.begin)
 def test_private_put_caps_nonfinite_symlink_no_overwrite(self):
  d=self.root/'private';d.mkdir();c.private_put(d,'a.json',{'invented':1});before=(d/'a.json').read_bytes()
  with self.assertRaises(FileExistsError):c.private_put(d,'a.json',{})
  self.assertEqual((d/'a.json').read_bytes(),before)
  for value in(math.nan,math.inf):
   with self.assertRaises(ValueError):c.private_put(d,'bad.json',{'x':value})
  with self.assertRaises(ValueError):c.private_put(d,'big.json',{'x':'a'*100},cap=16)
  (d/'link').symlink_to(d/'a.json')
  with self.assertRaises(FileExistsError):c.private_put(d,'link',{})
  self.assertFalse((d/'bad.json').exists());self.assertFalse((d/'big.json').exists())
 def test_new_directory_parent_fsync_and_partial_write(self):
  d=self.root/'new';real=os.fsync;seen=[]
  def fsync(fd):seen.append(os.fstat(fd).st_ino);return real(fd)
  with patch.object(os,'fsync',side_effect=fsync):c.make_output_directory(d)
  self.assertEqual(seen,[self.root.stat().st_ino]);store=c.Store(d)
  with patch.object(os,'fsync',side_effect=OSError('invented')):
   with self.assertRaises(OSError):store.put('partial.json',{})
  self.assertEqual((d/'partial.json').stat().st_mode&0o777,0o400)
  with self.assertRaises(FileExistsError):store.put('partial.json',{})
 def test_store_closed_total_members_before_write(self):
  d=self.root/'out';d.mkdir();store=c.Store(d,reserve_bytes=1,reserve_members=1)
  with patch.object(c,'MAX_TOTAL',10):
   with self.assertRaises(ValueError):store.put('x.bin',b'a'*10)
  with patch.object(c,'MAX_MEMBERS',1):
   with self.assertRaises(ValueError):store.put('y.json',{})
  self.assertEqual(list(d.iterdir()),[])
 def stats(self):return {k:np.ones(35 if k.startswith('initial')else 36,dtype=np.float64)for k in('initial_mean','initial_std','current_mean','current_std')}
 def callbacks(self):
  d=self.root/'callbacks';d.mkdir();return c.Callbacks(c.Store(d),20261012,'T',np)
 def test_checkpoint_four_scalers_nonpickle_roundtrip_and_once(self):
  cb=self.callbacks();state={'weight':np.arange(6,dtype=np.float32).reshape(2,3)};stats=self.stats();cb.checkpoint(20261012,'T',state,stats);a,s=c.checkpoint_load((cb.store.directory/'checkpoint.private.npz').read_bytes(),np)
  self.assertEqual(a['weight'].tobytes(),state['weight'].tobytes());self.assertEqual(set(s),set(stats))
  for k in s:self.assertEqual(s[k].tobytes(),stats[k].tobytes())
  with self.assertRaises(ValueError):cb.checkpoint(20261012,'T',state,stats)
 def test_failed_checkpoint_attempt_is_not_retryable(self):
  cb=self.callbacks()
  with self.assertRaises(ValueError):cb.checkpoint(20261012,'T',{'weight':np.array([math.nan],dtype=np.float32)},self.stats())
  with self.assertRaises(ValueError):cb.checkpoint(20261012,'T',{'weight':np.zeros(1,dtype=np.float32)},self.stats())
  self.assertEqual(list(cb.store.directory.iterdir()),[])
 def test_checkpoint_dtype_shape_object_header_and_cap_reject(self):
  for arrays in [{'x':np.array([object()],dtype=object)},{'x':np.ones(100001,dtype=np.float32)},{'x':np.ones(1,dtype=np.float64)}]:
   b=io.BytesIO();np.savez_compressed(b,**arrays)
   with self.assertRaises(ValueError):c.checkpoint_load(b.getvalue(),np)
  with self.assertRaises(ValueError):c.checkpoint_load(b'x'*(8388608+1),np)
 def item(self,i):return dict(update=i,base_nll=1.,sequence_nll=0.,joint_or_conditional_nll=1.,gradient_norm=1.,base_gradient_norm=1.,sequence_gradient_norm=0.,seconds=float(i))
 def test_history300_durable_order_partial_no_overwrite(self):
  cb=self.callbacks()
  for i in range(1,301):cb.history(20261012,'T',self.item(i))
  cb.close();path=cb.store.directory/'history.private.jsonl';self.assertEqual(len(path.read_bytes().splitlines()),300);self.assertEqual(path.stat().st_mode&0o777,0o400)
  with self.assertRaises(ValueError):cb.history(20261012,'T',self.item(301))
 def test_history_invalid_record_before_write(self):
  cb=self.callbacks()
  for row in [self.item(2),dict(self.item(1),base_nll=math.nan),dict(self.item(1),update=True)]:
   with self.assertRaises(ValueError):cb.history(20261012,'T',row)
  self.assertEqual(list(cb.store.directory.iterdir()),[])
 def test_each_prediction66_once_and_identity(self):
  cb=self.callbacks()
  with self.assertRaises(ValueError):cb.prediction(20261013,'T',{})
  for i in range(66):cb.prediction(20261012,'T',{'invented':i})
  with self.assertRaises(ValueError):cb.prediction(20261012,'T',{})
  self.assertEqual(len(list(cb.store.directory.iterdir())),66)
 def test_cleanup_exact_empty_cgroup_not_substring(self):
  self.assertEqual(p.post_checked('Result=success\nActiveState=inactive\nControlGroup=\n')['Result'],'success')
  for text in('ActiveState=active\nControlGroup=\n','ActiveState=inactive\nControlGroup=/foreign\n','ActiveState=inactive\nControlGroup=\nControlGroup=/x\n'):
   with self.assertRaises(ValueError):p.post_checked(text)
 def test_manager_raw_retained_before_fallible_postproperties(self):
  answer=dict(code=1,timeout=False,raw={'stdout':b'\xffpartial','stderr':b'error'},streams={k:dict(original_bytes=1,original_sha256='0'*64,retained_bytes=1,truncated=False,complete_observation=True)for k in('stdout','stderr')})
  def post(*a,**kw):raise OSError('invented-post-failure')
  with self.assertRaises(OSError):p.run_stage(self.g,processing_begin=self.begin,runner=lambda *a:answer,check_output=post)
  out=Path(self.g['experiment_root'])/'stage_00_score';self.assertEqual((out/'manager_stdout.private.bin').read_bytes(),b'\xffpartial');self.assertTrue((out/'manager_return.private.json').exists())
 def test_manager_launch_exception_durable_no_retry(self):
  def runner(*a):raise OSError('invented-launch')
  def stop(*a,**kw):raise subprocess.TimeoutExpired('invented-stop',10)
  with self.assertRaises(OSError):p.run_stage(self.g,processing_begin=self.begin,runner=runner,run=stop,check_output=lambda *a,**kw:(_ for _ in()).throw(OSError('post')))
  out=Path(self.g['experiment_root'])/'stage_00_score';self.assertTrue((out/'manager_return.private.json').exists());self.assertTrue((out/'manager_stop.private.json').exists())
  with self.assertRaises(ValueError):p.claim_stage(self.g,self.begin)
 def test_live_controls_synthetic_kernel_before_import(self):
  unit='eew-receiver-continuation-v4-00.service';proc=self.root/'proc';proc.write_text('0::/owned/'+unit+'\n');base=self.root/'cgroups';group=base/'owned'/unit;group.mkdir(parents=True)
  for k,v in {'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64','cgroup.procs':str(os.getpid())}.items():(group/k).write_text(v)
  manager='RuntimeMaxUSec=16min\nTimeoutStopUSec=5s\nKillMode=control-group\nActiveState=active\nCPUWeight=10\n';env={'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
  with patch.dict(os.environ,env),patch.object(child.sys,'dont_write_bytecode',True):child.live_controls(self.g,lambda *a,**kw:manager,proc,base)
  (group/'memory.swap.max').write_text('1')
  with patch.dict(os.environ,env),patch.object(child.sys,'dont_write_bytecode',True):
   with self.assertRaises(ValueError):child.live_controls(self.g,lambda *a,**kw:manager,proc,base)
 def test_import_identity_collision_before_import(self):
  import types
  with patch.dict(child.sys.modules,{'invented':types.SimpleNamespace(__file__='/wrong/invented.py')}):
   with self.assertRaises(ValueError):child.import_bound('invented',self.root)
 def test_managed_raw_stream_prefix_hash_invalid_UTF8_bounded(self):
  stdout=b'\xff'*100000;stderr=b'\x00'*150000;threads=[]
  class Fake:
   def __init__(self,*a,**kw):
    for name,payload in [('stdout',stdout),('stderr',stderr)]:
     r,w=os.pipe();setattr(self,name,os.fdopen(r,'rb'))
     def writer(fd=w,data=payload):
      try:
       with os.fdopen(fd,'wb')as f:f.write(data)
      except BrokenPipeError:pass
     thread=threading.Thread(target=writer);thread.start();threads.append(thread)
   def wait(self,timeout):
    for thread in threads:thread.join(1)
    return 0
   def terminate(self):pass
   def kill(self):pass
  result=p.managed_process(['invented'],10,popen=Fake)
  self.assertEqual(result['raw']['stdout'],stdout[:65536]);self.assertEqual(result['raw']['stderr'],stderr[:131072]);self.assertFalse(result['timeout'])
  for key,payload in [('stdout',stdout),('stderr',stderr)]:self.assertEqual(result['streams'][key]['original_sha256'],hashlib.sha256(payload).hexdigest());self.assertEqual(result['streams'][key]['original_bytes'],len(payload));self.assertTrue(result['streams'][key]['truncated'])
 def test_managed_timeout_hash_scope_marked_incomplete(self):
  pipes=[]
  class Fake:
   def __init__(self,*a,**kw):
    for name in('stdout','stderr'):
     r,w=os.pipe();setattr(self,name,os.fdopen(r,'rb'));pipes.append(w)
   def terminate(self):
    for fd in pipes:os.close(fd)
   def wait(self,timeout):return -15
   def kill(self):pass
  clocks=iter([0.,2.]);result=p.managed_process(['invented'],1,popen=Fake,clock=lambda:next(clocks));self.assertTrue(result['timeout']);self.assertTrue(all(not v['complete_observation']for v in result['streams'].values()))
 def test_closed_anchor_pin_wrong_final_blocks_before_claim(self):
  self.g['anchor']['checkpoint']['pin']={'bytes':1,'sha256':'0'*64}
  with self.assertRaises(ValueError):p.claim_stage(self.g,self.begin)
  self.assertEqual(list(Path(self.g['experiment_root']).iterdir()),[])
 def test_exact_previous_prefix_failure_or_mode_change_blocks(self):
  g=copy.deepcopy(self.g);g.update(index=1,arm='F');record=dict(schema='receiver-continuation-stage-return-v3',index=0,stage='score',seed=20261012,arm='B',status='complete',unit_exit=0,owned_unit_inactive=True,owned_cgroup_empty=True,experiment_begin=g['experiment_begin'],source_commit=g['source_commit'],scorer_binding=g['admission']['scorer_binding'],capacity=g['admission']['capacity'],study_fingerprint=p.study_fingerprint(g))
  g['previous']=[invented.write(self.root/'inputs','previous.private.json',record)];p.previous_checked(g)
  for key,value in [('status','incomplete'),('unit_exit',False),('owned_cgroup_empty',False),('scorer_binding','changed'),('study_fingerprint','bad')]:
   wrong=dict(record);wrong[key]=value;path=Path(g['previous'][0]['path']);path.chmod(0o600);raw=(json.dumps(wrong)+'\n').encode();path.write_bytes(raw);path.chmod(0o400);g['previous'][0]['pin']=c.pin(raw)
   with self.assertRaises(ValueError):p.previous_checked(g)
 def test_anchor_load_exact_scalers_history_kind_once(self):
  d=self.root/'anchor';d.mkdir();store=c.Store(d);cb=c.Callbacks(store,20261012,'B',np);stats=self.stats();cb.checkpoint(20261012,'B',{'w':np.zeros(1,dtype=np.float32)},stats)
  for i in range(1,301):cb.history(20261012,'B',self.item(i))
  cb.close();metadata=dict(schema='receiver-final-anchor-metadata-v3',seed=20261012,arm='B',kind='original_final',mref=4.,train_population_std=1.,retained_predictions=[{}]*66);mp=invented.write(d,'metadata.private.json',metadata)
  specs={k:dict(path=str(d/name),pin=c.pin((d/name).read_bytes()))for k,name in [('checkpoint','checkpoint.private.npz'),('history','history.private.jsonl')]};specs['metadata']=mp;g=copy.deepcopy(self.g);g['anchor']=specs;reader=child.anchor_reader(g,np,stats);anchor=reader(20261012,'B');self.assertEqual(len(anchor['history']),300);self.assertEqual(anchor['kind'],'original_final')
  with self.assertRaises(ValueError):reader(20261012,'B')
  wrong=self.stats();wrong['initial_mean'][0]=np.nextafter(1.,2.)
  with self.assertRaises(ValueError):child.anchor_reader(g,np,wrong)(20261012,'B')
 def test_optional_adoption_exact_profile_fixed_before_study(self):
  opt=dict(adapter=self.g['sources']['parent'],fast=self.g['sources']['parent'],module='adapter',factory='make_adapter',binding='invented-fast');g=copy.deepcopy(self.g);g['admission'].update(scorer_mode='reviewed_optional',scorer_binding='invented-fast',optional_scorer_verified=True)
  proof=dict(schema='receiver-fixed-optional-scorer-adoption-v3',binding='invented-fast',published=True,linux_zero_skips=True,source_verified=True,authority_before_first_stage=True,sources={k:opt[k]['files']for k in('adapter','fast')});opt['proof']=invented.write(self.root/'inputs','optional.private.json',proof);g['sources']['optional']=opt;p.gate_checked(g,self.begin);child.optional_proof(g)
  proof['authority_before_first_stage']=False;path=Path(opt['proof']['path']);path.chmod(0o600);raw=(json.dumps(proof)+'\n').encode();path.write_bytes(raw);path.chmod(0o400);opt['proof']['pin']=c.pin(raw)
  with self.assertRaises(ValueError):child.optional_proof(g)
 def test_optional_factory_once_per_child_same_dependencies_no_fallback(self):
  import types
  candidate=Path(self.g['sources']['candidate']['directory']);calls=[]
  modules={n:types.SimpleNamespace(__file__=str(candidate/(n+'.py')))for n in('mixture_density','numerical_core','posterior_scores','models','observations','packet_io','pilot')}
  modules['pilot'].core=modules['numerical_core'];modules['pilot'].density=modules['mixture_density'];modules['pilot'].observations=modules['observations'];modules['pilot'].posterior_scores=modules['posterior_scores']
  fake_torch=types.SimpleNamespace(__version__='2.8.0+cu128',cuda=types.SimpleNamespace(is_initialized=lambda:False),set_num_threads=lambda n:None,set_num_interop_threads=lambda n:None,use_deterministic_algorithms=lambda value:None)
  adapter=types.SimpleNamespace()
  def factory(deps):
   calls.append('factory');self.assertIs(deps.core,modules['numerical_core']);self.assertIs(deps.models,modules['models']);self.assertIs(deps.torch,fake_torch);self.assertIs(deps.fast_scorer,modules['scorer']);return lambda *args:calls.append('score')
  adapter.make_adapter=factory;modules.update(engine=types.SimpleNamespace(),reference=types.SimpleNamespace(),scorer=types.SimpleNamespace(),adapter=adapter)
  def bound(name,directory):child.sys.modules[name]=modules[name];return modules[name]
  g=copy.deepcopy(self.g);g['sources']['optional']=dict(adapter=g['sources']['parent'],fast=g['sources']['parent'],module='adapter',factory='make_adapter',binding='invented')
  injected={'numpy':types.SimpleNamespace(__version__='2.0.2'),'torch':fake_torch,'scipy':types.SimpleNamespace(__version__='1.13.1')}
  with patch.dict(child.sys.modules,injected),patch.object(child.sys,'version_info',(3,9,25)),patch.object(child.sys,'path',list(child.sys.path)),patch.object(child,'import_bound',side_effect=bound):
   engine,deps,packetio,numpy,scorer=child.deps_load(g)
   for i in range(66):scorer(None)
  self.assertEqual(calls.count('factory'),1);self.assertEqual(calls.count('score'),66)
 def test_runtime_full_membership_and_every_pin_no_sampling(self):
  prefix=self.root/'runtime-prefix';venv=prefix/'venv';venv.mkdir(parents=True);raw=b'invented';pins={}
  for i in range(10112):
   name='venv/f_%05d'%i;path=prefix/name;path.write_bytes(raw);path.chmod(0o444);pins[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  manifest=dict(files=pins);directory=self.root/'inputs';spec=invented.write(directory,'fullruntime.private.json',manifest);runtime=dict(self.g['runtime'],prefix_directory=str(prefix),manifest=spec,canonical_sha256=hashlib.sha256(child.canonical(manifest)).hexdigest());seen=[]
  with patch.object(c,'hash_file',side_effect=lambda path,*args:seen.append(str(path))):child.runtime_verify(runtime,lambda:None)
  self.assertEqual(len(seen),10122);self.assertEqual(len(set(seen)),10122)
  extra=venv/'unbound';extra.write_bytes(b'x')
  with self.assertRaises(ValueError):child.runtime_verify(runtime,lambda:None)
 def test_aggregate_results_exact_closed_score_pin_before_claim(self):
  g=copy.deepcopy(self.g);g.update(index=17,stage='aggregate',seed=None,arm=None,anchor=None,previous=[],score_results=[])
  for i,(stage,seed,arm)in enumerate(p.PLAN[:-1]):
   result=invented.write(self.root/'inputs','result_%02d.private.json'%i,{'invented_score':i})
   record=dict(schema='receiver-continuation-stage-return-v3',index=i,stage=stage,seed=seed,arm=arm,status='complete',unit_exit=0,owned_unit_inactive=True,owned_cgroup_empty=True,experiment_begin=g['experiment_begin'],source_commit=g['source_commit'],scorer_binding=g['admission']['scorer_binding'],capacity=g['admission']['capacity'],study_fingerprint=p.study_fingerprint(g),files={'stage_result.private.json':result['pin']})
   g['previous'].append(invented.write(self.root/'inputs','previous_%02d.private.json'%i,record))
   if stage=='score':g['score_results'].append(result)
  p.previous_checked(g);p.aggregate_custody(g)
  g['score_results'][0]=invented.write(self.root/'inputs','unrelated_score.private.json',{'same_identity_but_other_score':True})
  with self.assertRaisesRegex(ValueError,'aggregate_score_custody'):p.claim_stage(g,self.begin)
  self.assertEqual(list(Path(g['experiment_root']).iterdir()),[])
 def test_capture_failure_preserves_observed_bytes_hashes_and_no_retry(self):
  payload=b'\xffobserved-before-error';real_read=os.read;calls=[0]
  class Fake:
   def __init__(self,*a,**kw):
    for name in('stdout','stderr'):
     r,w=os.pipe();setattr(self,name,os.fdopen(r,'rb'));os.write(w,payload if name=='stdout'else b'');os.close(w)
   def terminate(self):pass
   def wait(self,timeout):return 1
   def kill(self):pass
  def read(fd,count):
   calls[0]+=1
   if calls[0]>1:raise OSError('invented-capture')
   return real_read(fd,count)
  with patch.object(p.os,'read',side_effect=read):answer=p.managed_process(['invented'],10,popen=Fake)
  self.assertEqual(answer['raw']['stdout'],payload);self.assertEqual(answer['streams']['stdout']['original_sha256'],hashlib.sha256(payload).hexdigest());self.assertEqual(answer['streams']['stdout']['original_bytes'],len(payload));self.assertTrue(answer['timeout']);self.assertEqual(answer['exception_type'],'OSError');self.assertFalse(answer['streams']['stdout']['complete_observation'])
  with self.assertRaises(OSError):p.run_stage(self.g,processing_begin=self.begin,runner=lambda *a:answer,run=lambda *a,**kw:type('Stop',(),{'returncode':0})(),check_output=lambda *a,**kw:(_ for _ in()).throw(OSError('post')))
  out=Path(self.g['experiment_root'])/'stage_00_score';self.assertEqual((out/'manager_stdout.private.bin').read_bytes(),payload);journal=c.strict_json((out/'manager_return.private.json').read_bytes());self.assertEqual(journal['streams']['stdout']['original_bytes'],len(payload));self.assertEqual(journal['exception_type'],'OSError')
 def test_deadline_blocks_before_first_scientific_import(self):
  import builtins
  real=builtins.__import__;seen=[]
  def imp(name,*a,**kw):seen.append(name);return real(name,*a,**kw)
  def expired():raise ValueError('parent_deadline')
  with patch.object(builtins,'__import__',side_effect=imp),patch.object(child.sys,'path',list(child.sys.path)):
   with self.assertRaisesRegex(ValueError,'parent_deadline'):child.deps_load(self.g,expired)
  self.assertFalse(any(n in('numpy','torch','scipy')for n in seen))
 def test_git_elapsed_deadline_blocks_return_before_import(self):
  out,claim,_=p.claim_stage(self.g,self.begin);clock=[self.begin]
  def git(*a,**kw):clock[0]=self.begin+901;return self.g['source_commit']+'\n'
  with patch.object(child,'source_verify'),patch.object(child,'runtime_verify'),patch.object(child,'live_controls',return_value={}),patch.object(child.subprocess,'check_output',side_effect=git),patch.object(p.time,'monotonic',side_effect=lambda:clock[0]),patch.object(c,'__file__',str(Path(self.g['sources']['parent']['directory'])/'custody.py')),patch.object(p,'__file__',str(Path(self.g['sources']['parent']['directory'])/'controller.py')):
   with self.assertRaisesRegex(ValueError,'parent_deadline'):child.before_import(self.g,out,claim)
 def test_expiry_during_claim_publication_never_launches_retains_claim(self):
  real=p.claim_stage;clock=[self.begin];launch=[]
  def claimed(*args):
   result=real(*args);clock[0]=self.begin+7201;return result
  with patch.object(p,'claim_stage',side_effect=claimed),patch.object(p.time,'monotonic',side_effect=lambda:clock[0]):
   with self.assertRaisesRegex(ValueError,'parent_deadline'):p.run_stage(self.g,processing_begin=self.begin,runner=lambda *args:launch.append(args))
  self.assertEqual(launch,[]);root=Path(self.g['experiment_root']);self.assertTrue((root/'claim_00_score.private.json').exists());out=root/'stage_00_score';self.assertTrue((out/'parent_gate.private.json').exists());self.assertTrue((out/'stage_claim.private.json').exists());self.assertFalse((out/'manager_return.private.json').exists())
 def test_critical_original_mode664_admitted_exact_pin_and_unlisted_barred(self):
  path=self.root/'invented_RECORD';raw=b'invented critical text\n';path.write_bytes(raw);path.chmod(0o664);g=copy.deepcopy(self.g);name=next(iter(g['runtime']['critical_files']));del g['runtime']['critical_files'][name];g['runtime']['critical_files'][str(path)]=dict(c.pin(raw),mode='0o664');p.gate_checked(g,self.begin);c.hash_file(path,g['runtime']['critical_files'][str(path)],0o664)
  self.assertEqual(path.stat().st_mode&0o777,0o664);wrong=copy.deepcopy(g);wrong['runtime']['critical_files'][str(path)]['mode']='0o666'
  with self.assertRaisesRegex(ValueError,'critical_pin'):p.gate_checked(wrong,self.begin)
  wrong=copy.deepcopy(g);wrong['runtime']['critical_files'][str(path)]['sha256']='bad'
  with self.assertRaisesRegex(ValueError,'pin'):p.gate_checked(wrong,self.begin)
 def test_critical_original_mode775_exact_hash_and_mode_never_normalized(self):
  path=self.root/'invented_native_library';raw=b'\x00synthetic-library\xff';path.write_bytes(raw);path.chmod(0o775);g=copy.deepcopy(self.g);name=next(iter(g['runtime']['critical_files']));del g['runtime']['critical_files'][name];expected=dict(c.pin(raw),mode='0o775');g['runtime']['critical_files'][str(path)]=expected;p.gate_checked(g,self.begin);c.hash_file(path,expected,0o775);self.assertEqual(path.stat().st_mode&0o777,0o775)
  path.write_bytes(raw[:-1]+b'x')
  with self.assertRaisesRegex(ValueError,'runtime_pin'):c.hash_file(path,expected,0o775)
  path.write_bytes(raw);path.chmod(0o755)
  with self.assertRaisesRegex(ValueError,'runtime_file'):c.hash_file(path,expected,0o775)
  self.assertEqual(path.stat().st_mode&0o777,0o755)
 def test_public_future_receipt_source_only_and_fit_provenance_separate(self):
  self.assertEqual(p.PUBLICATION,'earthquake_receiver_continuation_parent_source_push_v4_20261013.json');path=self.root/p.PUBLICATION;c.private_put(self.root,path.name,{'pushed_commit':'a'*40});self.assertEqual(p.publication_commit(self.root),'a'*40)

if __name__=='__main__':unittest.main()

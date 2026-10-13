"""Invented custody/claim/forward contracts; no external files/model fits."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
import custody as c
import controls as x
import controller as p
import replay_child as child
import invented

class ReplayTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.g,self.begin=invented.fixture(self.root)
 def tearDown(self):self.tmp.cleanup()
 def value(self,spec):return c.strict_json(p.load(spec))
 def test_full_ten660_closed_gate_before_claim(self):p.gate_checked(self.g,self.begin);v=p.custody_checked(self.g);self.assertEqual(sum(len(f['predictions'])for f in v['fits']),660);self.assertEqual(len(self.g['anchors']),10)
 def test_missing_ninth_or_tenth_anchor_barred(self):
  for n in(8,9):
   g=copy.deepcopy(self.g);g['anchors']=g['anchors'][:n]
   with self.assertRaises(ValueError):p.claim(g,self.begin)
  self.assertEqual(list(Path(self.g['output_root']).iterdir()),[])
 def test_fixed_identity_and_discrete_bool_rejection(self):
  for path,value in(('anchor',True),('ordinal',True)):
   g=copy.deepcopy(self.g)
   if path=='anchor':g['anchors'][0]['seed']=value
   else:g['dev_ordinals'][0]=value
   with self.assertRaises(ValueError):p.gate_checked(g,self.begin)
 def test_preparation_false_never_claims(self):
  for k in('passed','original_replay_verified','native_verified','continuation_closed','funding_resource_verified','publication_verified','linux_zero_skips','no_test'):
   g=copy.deepcopy(self.g);v=self.value(g['preparation']);v[k]=False;invented.replace(g['preparation'],v)
   with self.assertRaises(ValueError):p.claim(g,self.begin)
   v[k]=True;invented.replace(g['preparation'],v)
  self.assertEqual(list(Path(self.g['output_root']).iterdir()),[])
 def test_exact_projection_never_casts_or_repairs(self):
  g=copy.deepcopy(self.g);v=self.value(g['result']);v['fits'][0]['history'][0]['base_nll']=1.00001;invented.replace(g['result'],v)
  with self.assertRaisesRegex(ValueError,'projection_exact_values'):p.custody_checked(g)
 def test_projection_requires_all_seven_fields(self):
  g=copy.deepcopy(self.g);v=self.value(g['result']);del v['diagnostics'];invented.replace(g['result'],v)
  with self.assertRaises(ValueError):p.custody_checked(g)
 def test_aggregate_pin_binds_stage17_not_same_shape_other_file(self):
  g=copy.deepcopy(self.g);g['aggregate']=invented.write(self.root/'inputs','other.private.json',dict(self.value(g['aggregate']),unbound=True))
  with self.assertRaisesRegex(ValueError,'aggregate_closed_custody'):p.custody_checked(g)
 def test_incomplete_cleanup_or_foreign_profile_barred(self):
  for k,value in(('status','incomplete'),('unit_exit',False),('owned_cgroup_empty',False),('study_fingerprint','foreign'),('scorer_binding','foreign')):
   g=copy.deepcopy(self.g);v=self.value(g['stages'][4]);v[k]=value;invented.replace(g['stages'][4],v)
   with self.assertRaises(ValueError):p.custody_checked(g)
   original=self.value(self.g['stages'][0]);v[k]=original[k]if k in original else None;invented.replace(g['stages'][4],v)
 def test_original_and_fresh_checkpoint_substitution_barred(self):
  for index in(0,9):
   g=copy.deepcopy(self.g);g['anchors'][index]['checkpoint']['pin']={'bytes':1,'sha256':'f'*64}
   with self.assertRaisesRegex(ValueError,'anchor_closed_custody'):p.custody_checked(g)
 def test_durable_claim_once_no_overwrite(self):
  out=p.claim(self.g,self.begin);self.assertTrue((out/'parent_gate.private.json').exists());self.assertEqual((Path(self.g['output_root'])/'replay_claim.private.json').stat().st_mode&0o777,0o400)
  with self.assertRaises(ValueError):p.claim(self.g,self.begin)
 def test_expiry_after_claim_never_launches(self):
  real=p.claim;clock=[self.begin];seen=[]
  def claimed(*a):v=real(*a);clock[0]=self.begin+901;return v
  with patch.object(p,'claim',side_effect=claimed),patch.object(x.time,'monotonic',side_effect=lambda:clock[0]):
   with self.assertRaisesRegex(ValueError,'replay_deadline'):p.run_replay(self.g,processing_begin=self.begin,runner=lambda *a:seen.append(a))
  self.assertEqual(seen,[]);self.assertTrue((Path(self.g['output_root'])/'replay_claim.private.json').exists())
 def test_raw_manager_kept_before_cleanup_failure(self):
  answer=dict(code=1,timeout=False,raw={'stdout':b'\xffpartial','stderr':b'error'},streams={k:dict(truncated=False,complete_observation=True)for k in('stdout','stderr')})
  with self.assertRaises(OSError):p.run_replay(self.g,processing_begin=self.begin,runner=lambda *a:answer,check_output=lambda *a,**kw:(_ for _ in()).throw(OSError('invented')))
  out=Path(self.g['output_root'])/'replay';self.assertEqual((out/'manager_stdout.private.bin').read_bytes(),b'\xffpartial');self.assertTrue((out/'manager_return.private.json').exists())
 def test_source_closed_only_equal_optional_upload_manifest(self):
  s=self.g['sources']['parent'];x.source_verify(s,lambda:None);d=Path(s['directory']);invented.write(d,'parent_upload_manifest.private.json',s['files']);x.source_verify(s,lambda:None);invented.write(d,'runtime_extra.private.json',{})
  with self.assertRaises(ValueError):x.source_verify(s,lambda:None)
 def test_runtime_modes664775_exact_hash_not_normalized(self):
  for mode in(0o664,0o775):
   path=self.root/('mode_%s'%mode);raw=b'invented';path.write_bytes(raw);path.chmod(mode);c.hash_file(path,c.pin(raw),mode);self.assertEqual(path.stat().st_mode&0o777,mode);path.write_bytes(b'tampered')
   with self.assertRaises(ValueError):c.hash_file(path,c.pin(raw),mode)
  p.gate_checked(self.g,self.begin)
 def test_strict_private_caps_nonfinite_nofollow_nooverwrite(self):
  d=self.root/'private';d.mkdir();c.private_put(d,'a.json',{'invented':True})
  with self.assertRaises(FileExistsError):c.private_put(d,'a.json',{})
  with self.assertRaises(ValueError):c.private_put(d,'b.json',{'x':math.nan})
  with self.assertRaises(ValueError):c.private_put(d,'c.json',{'x':'a'*100},16)
  d2=self.root/'link';d2.symlink_to(d)
  with self.assertRaises(OSError):c.private_put(d2,'d.json',{})
 def test_forward_exact_float64_bytes_signed_zero_and_ulp(self):
  child.exact_numeric([1.,-0.],[1.,-0.],np)
  for a,b in(([1.],[np.nextafter(1.,2.)]),([-0.],[0.]),([math.nan],[math.nan])):
   with self.assertRaises(ValueError):child.exact_numeric(a,b,np)
 def test_history300_order_finite_no_truncation(self):
  history=self.value(self.g['result'])['fits'][0]['history'];child.histories_checked(history)
  for data in(history[:-1],[dict(v,update=1)for v in history],[dict(v,seconds=-1.)for v in history]):
   with self.assertRaises(ValueError):child.histories_checked(data)
 def test_forward_journal660_private_durable_cap(self):
  d=self.root/'journal';d.mkdir();journal=child.Journal(c.Store(d))
  for i in range(660):journal.put(dict(index=i,matched=True))
  with self.assertRaises(ValueError):journal.put({})
  journal.close();self.assertEqual(len((d/'forward.private.jsonl').read_bytes().splitlines()),660);self.assertEqual((d/'forward.private.jsonl').stat().st_mode&0o777,0o400)
 def test_journal_failure_keeps_partial_and_nooverwrite(self):
  d=self.root/'partial';d.mkdir();journal=child.Journal(c.Store(d));journal.put({'first':True})
  with self.assertRaises(ValueError):journal.put({'x':'a'*5000})
  journal.close();self.assertEqual(len((d/'forward.private.jsonl').read_bytes().splitlines()),1)
  other=child.Journal(c.Store(d))
  with self.assertRaises(FileExistsError):other.put({})
 def test_record_target_group_receiver_family_rate_binding(self):
  row=dict(ordinal=91,mw=4.,group=7,initial={'context':np.zeros(35)},horizons=[{'rate':[100,1]}]*3);item=dict(ordinal=91,horizon=1,target=4.,group=7,receiver=[0.,0.,0.],family='12Z',rate=[100,1]);child.record_binding(item,row,1)
  for k,v in(('target',4.1),('group',8),('family','ENZ'),('receiver',[1.,0.,0.]),('rate',[200,1])):
   bad=dict(item);bad[k]=v
   with self.assertRaises(ValueError):child.record_binding(bad,row,1)
 def test_deadline_before_science_import(self):
  import builtins
  real=builtins.__import__;seen=[]
  def imp(n,*a,**kw):seen.append(n);return real(n,*a,**kw)
  with patch.object(builtins,'__import__',side_effect=imp):
   with self.assertRaises(ValueError):child.dependencies(self.g,lambda:(_ for _ in()).throw(ValueError('expired')))
  self.assertFalse(any(n in('numpy','torch','scipy')for n in seen))
 def test_ten_saved_forward660_no_fit_and_complete_scaler_handoff(self):
  import invented_forward as f
  result,packet,stats,torch,mods=f.setup(self.value(self.g['result']),self.g);d=self.root/'forward';d.mkdir();journal=child.Journal(c.Store(d));f.Net.created=[]
  def anchored(a,fit,st,mean,std,net,*args):self.assertEqual(st,stats);return stats,fit['history']
  with patch.object(child,'anchor',side_effect=anchored):scalers,histories=child.forward(result,packet,self.g,np,torch,mods,journal,lambda:None)
  journal.close();self.assertEqual(journal.count,660);self.assertEqual(len(f.Net.created),10);self.assertEqual(set(scalers),set(p.IDS));self.assertEqual(set(histories),set(p.IDS));self.assertEqual(len((d/'forward.private.jsonl').read_bytes().splitlines()),660)
 def test_forward_disagreement_retains_prefix_never_claims660(self):
  import invented_forward as f
  result,packet,stats,torch,mods=f.setup(self.value(self.g['result']),self.g);result['fits'][0]['predictions'][5]['numerical']['mu'][0]=2.000001;d=self.root/'forward_failed';d.mkdir();journal=child.Journal(c.Store(d))
  with patch.object(child,'anchor',return_value=(stats,result['fits'][0]['history'])):
   with self.assertRaisesRegex(ValueError,'checkpoint_forward_mismatch'):child.forward(result,packet,self.g,np,torch,mods,journal,lambda:None)
  journal.close();self.assertEqual(journal.count,5);self.assertEqual(len((d/'forward.private.jsonl').read_bytes().splitlines()),5)
 def test_real_numeric_anchor_saved_state_scalers_and300history(self):
  import invented_forward as f
  result,packet,stats,torch,mods=f.setup(self.value(self.g['result']),self.g);d=self.root/'realanchor';d.mkdir();cb=c.Callbacks(c.Store(d),20261012,'B',np);cb.checkpoint(20261012,'B',{'w':np.array([2.],dtype=np.float32)},stats)
  for v in result['fits'][0]['history']:cb.history(20261012,'B',v)
  cb.close();a=dict(seed=20261012,arm='B',checkpoint=dict(path=str(d/'checkpoint.private.npz'),pin=c.pin((d/'checkpoint.private.npz').read_bytes())),history=dict(path=str(d/'history.private.jsonl'),pin=c.pin((d/'history.private.jsonl').read_bytes())),metadata=invented.write(d,'metadata.private.json',dict(schema='receiver-final-anchor-metadata-v3',seed=20261012,arm='B',kind='original_final',mref=4.,train_population_std=0.,retained_predictions=[{}]*66)))
  net=f.Net('B',4.);scalers,history=child.anchor(a,result['fits'][0],stats,4.,0.,net,np,torch);self.assertEqual(net.w,2.);self.assertEqual(len(history),300)
  wrong={k:v.copy()for k,v in stats.items()};wrong['initial_mean'][0]=np.nextafter(1.,2.)
  with self.assertRaisesRegex(ValueError,'saved_scalers_exact'):child.anchor(a,result['fits'][0],wrong,4.,0.,net,np,torch)
 def test_auditor_called_only_after660_unchanged_result_scalers_history(self):
  import types
  out=p.claim(self.g,self.begin);result=self.value(self.g['result']);calls=[];fakeaudit=types.SimpleNamespace()
  def audit(received,packet,**kwargs):
   self.assertIs(received,result);self.assertEqual(kwargs['processing_begin'],self.begin);self.assertEqual(kwargs['wall_seconds'],900);self.assertEqual(set(kwargs['checkpoint_scalers']),set(p.IDS));self.assertEqual(set(kwargs['histories']),set(p.IDS));calls.append('audit');return dict(schema='earthquake-TRAIN115-renewal-score-audit-v3',status='pass',advance=dict(pass_all=False,checks=[{}]*24),fits=[dict(seed=s,arm=a,predictions=[{}]*66)for s,a in p.IDS],comparisons=[{}]*24)
  fakeaudit.audit=audit
  def forward(result,packet,g,np,torch,mods,journal,check):
   for i in range(660):journal.put({'index':i})
   return {pair:{}for pair in p.IDS},{pair:[]for pair in p.IDS}
  torch=types.SimpleNamespace();mods={'packet_io':types.SimpleNamespace(load=lambda *a,**kw:{'invented':True})}
  with patch.object(child,'before_import',return_value=(result,b'archive',b'manifest',{})),patch.object(child,'dependencies',return_value=(np,torch,mods,fakeaudit)),patch.object(child,'forward',side_effect=forward):report=child.main(out)
  self.assertEqual(calls,['audit']);self.assertEqual(report['checkpoint_forward_records'],660);self.assertEqual(report['independent_scores'],660);self.assertFalse(report['advance']['pass_all'])
 def test_partial_forward_never_calls_auditor_failure_remains_false(self):
  import types
  out=p.claim(self.g,self.begin);called=[];audit=types.SimpleNamespace(audit=lambda *a,**kw:called.append(True));mods={'packet_io':types.SimpleNamespace(load=lambda *a,**kw:{})}
  def failed(result,packet,g,np,torch,mods,journal,check):journal.put({'partial':True});raise ValueError('invented_mismatch')
  with patch.object(child,'before_import',return_value=(self.value(self.g['result']),b'a',b'm',{})),patch.object(child,'dependencies',return_value=(np,types.SimpleNamespace(),mods,audit)),patch.object(child,'forward',side_effect=failed):
   with self.assertRaisesRegex(ValueError,'invented_mismatch'):child.main(out)
  self.assertEqual(called,[]);v=c.strict_json((out/'replay_failure.private.json').read_bytes());self.assertEqual(v['checkpoint_forward_records'],1);self.assertEqual(v['advance'],dict(pass_all=False,checks=[]));self.assertFalse((out/'replay_result.private.json').exists())
 def test_publication_elapsed_deadline_stops_before_dependencies(self):
  out=p.claim(self.g,self.begin);claim=c.strict_json((out/'replay_claim.private.json').read_bytes());clock=[self.begin];hashes=[]
  def git(*a,**kw):clock[0]=self.begin+901;return self.g['source_commit']+'\n'
  d=Path(self.g['sources']['parent']['directory'])
  with patch.object(child,'live_controls',return_value={}),patch.object(x,'source_verify'),patch.object(x,'runtime_verify'),patch.object(c,'hash_file',side_effect=lambda *a:hashes.append(a)),patch.object(child.subprocess,'check_output',side_effect=git),patch.object(x.time,'monotonic',side_effect=lambda:clock[0]),patch.object(c,'__file__',str(d/'custody.py')),patch.object(x,'__file__',str(d/'controls.py')),patch.object(p,'__file__',str(d/'controller.py')):
   with self.assertRaisesRegex(ValueError,'replay_deadline'):child.before_import(self.g,out,claim)
  self.assertEqual(len(hashes),30)
 def test_live2GiB64_controls_invented_kernel(self):
  unit=p.UNIT;proc=self.root/'proc';proc.write_text('0::/owned/'+unit+'\n');base=self.root/'cgroups';group=base/'owned'/unit;group.mkdir(parents=True)
  for k,v in {'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64','cgroup.procs':str(os.getpid())}.items():(group/k).write_text(v)
  manager='RuntimeMaxUSec=16min\nTimeoutStopUSec=5s\nKillMode=control-group\nActiveState=active\nCPUWeight=10\n';env={'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
  with patch.dict(os.environ,env),patch.object(child.sys,'dont_write_bytecode',True):child.live_controls(self.g,lambda *a,**kw:manager,proc,base)
  (group/'memory.swap.max').write_text('1')
  with patch.dict(os.environ,env),patch.object(child.sys,'dont_write_bytecode',True):
   with self.assertRaises(ValueError):child.live_controls(self.g,lambda *a,**kw:manager,proc,base)
 def test_real_runtime_manifest_full10112_and_ten_original_critical_modes(self):
  root=self.root/'fullprefix';venv=root/'venv';venv.mkdir(parents=True);raw=b'invented-runtime';pins={}
  for i in range(10112):
   name='venv/f_%05d'%i;file=root/name;file.write_bytes(raw);file.chmod(0o444);pins[name]=c.pin(raw)
  manifest={'files':pins};spec=invented.write(self.root/'inputs','full_manifest.private.json',manifest);critical={}
  for i in range(10):
   file=self.root/('original_critical_%02d'%i);file.write_bytes(raw);mode=0o664 if i<3 else 0o775;file.chmod(mode);critical[str(file)]=dict(c.pin(raw),mode=oct(mode))
  runtime=dict(self.g['runtime'],prefix_directory=str(root),manifest=spec,canonical_sha256=hashlib.sha256(x.canonical(manifest)).hexdigest(),critical_files=critical,symlinks=invented.write(self.root/'inputs','full_symlinks.private.json',dict(schema='root-prefix-runtime-symlink-manifest-v1',prefix_directory=str(root),links={})));checks=[];x.runtime_verify(runtime,lambda:checks.append(True));self.assertEqual(len(checks),20234)
  bad=root/'venv/f_00123';bad.chmod(0o644)
  with self.assertRaisesRegex(ValueError,'runtime_file'):x.runtime_verify(runtime,lambda:None)
  bad.chmod(0o444);extra=root/'venv/extra';extra.write_bytes(raw)
  with self.assertRaisesRegex(ValueError,'runtime_membership'):x.runtime_verify(runtime,lambda:None)
  extra.unlink();filelink=root/'venv/rogue_module.py';filelink.symlink_to(root/'venv/f_00000')
  with self.assertRaisesRegex(ValueError,'runtime_membership'):x.runtime_verify(runtime,lambda:None)
  filelink.unlink();dirlink=root/'venv/rogue_package';dirlink.symlink_to(root/'venv',target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'runtime_membership'):x.runtime_verify(runtime,lambda:None)
  dirlink.unlink();pipe=root/'venv/unexpected_fifo';os.mkfifo(pipe)
  with self.assertRaisesRegex(ValueError,'runtime_unexpected_entry'):x.runtime_verify(runtime,lambda:None)
  pipe.unlink();declared=root/'venv/declared';declared.symlink_to('f_00000');links=self.value(runtime['symlinks']);links['links']={'venv/declared':'f_00000'};invented.replace(runtime['symlinks'],links);x.runtime_verify(runtime,lambda:None)
  declared.unlink();outside=self.root/'outside_intermediate';outside.symlink_to(Path(next(iter(critical))));declared.symlink_to(outside);links['links']={'venv/declared':str(outside)};invented.replace(runtime['symlinks'],links);x.runtime_verify(runtime,lambda:None)
  declared.unlink();unbound=self.root/'unbound_target';unbound.write_bytes(raw);declared.symlink_to(unbound);links['links']={'venv/declared':str(unbound)};invented.replace(runtime['symlinks'],links)
  with self.assertRaisesRegex(ValueError,'runtime_link_target'):x.runtime_verify(runtime,lambda:None)
  declared.unlink();declared.symlink_to('declared');links['links']={'venv/declared':'declared'};invented.replace(runtime['symlinks'],links)
  with self.assertRaises((RuntimeError,OSError)):x.runtime_verify(runtime,lambda:None)
 def test_own_cleanup_exact_and_future_publication(self):
  x.post_checked('Result=success\nActiveState=inactive\nControlGroup=\n')
  with self.assertRaises(ValueError):x.post_checked('ActiveState=inactive\nControlGroup=/foreign\n')
  self.assertEqual(p.PUBLICATION,'earthquake_receiver_complete_replay_source_push_v1_20261013.json');self.assertEqual(p.UNIT,'eew-receiver-complete-replay-v1.service')

if __name__=='__main__':unittest.main()

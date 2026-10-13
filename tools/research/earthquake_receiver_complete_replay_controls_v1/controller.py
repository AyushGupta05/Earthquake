"""One independent no-fit final replay, with root-bound readonly authority."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import custody as c
import controls as x

STUDY='earthquake-TRAIN115-receiver-renewal-v2'
IDS=tuple((s,a)for s in(20261012,20261013)for a in('B','F','H','T','C'))
PLAN=tuple([('score',s,a)for s,a in IDS[:3]]+[v for s,a in IDS[3:]for v in(('train',s,a),('score',s,a))]+[('aggregate',None,None)])
RESULT_KEYS={'status','fits','capacity','advance','comparisons','diagnostics','fit_authorized'}
GATE_KEYS={'schema','study','source_commit','sources','runtime','packet','result','aggregate','anchors','original_closed','stages','preparation','output_root','dev_ordinals'}
PUBLICATION='earthquake_receiver_complete_replay_source_push_v1_20261013.json'
UNIT='eew-receiver-complete-replay-v1.service'

def publication_commit(work):
 value=c.strict_json((Path(work)/PUBLICATION).read_bytes(),262144)['pushed_commit'];c.need(type(value)is str and len(value)==40 and all(t in'0123456789abcdef'for t in value),'publication_commit');return value

def load(spec,cap=c.MAX_MEMBER):return c.read_file(spec['path'],spec['pin'],cap)

def gate_checked(g,begin):
 x.tick(begin);c.need(type(g)is dict and set(g)==GATE_KEYS and g['schema']=='receiver-complete-replay-parent-gate-v1'and g['study']==STUDY,'gate');commit=g['source_commit'];c.need(type(commit)is str and len(commit)==40 and all(t in'0123456789abcdef'for t in commit),'commit')
 c.need(type(g['sources'])is dict and set(g['sources'])=={'candidate','auditor','parent'},'sources')
 for k,n in(('candidate',69),('auditor',34),('parent',None)):x.source_spec(g['sources'][k],n)
 r=g['runtime'];c.need(type(r)is dict and set(r)=={'prefix_directory','manifest','canonical_sha256','critical_files','torch_site','symlinks'}and all(type(r[k])is str and Path(r[k]).is_absolute()for k in('prefix_directory','torch_site'))and type(r['critical_files'])is dict and len(r['critical_files'])==10,'runtime');x.file_spec(r['manifest'],4194304);x.file_spec(r['symlinks'],65536);c.pin_checked({'bytes':0,'sha256':r['canonical_sha256']},0)
 for path,pin in r['critical_files'].items():c.need(type(path)is str and Path(path).is_absolute()and type(pin)is dict and set(pin)=={'bytes','sha256','mode'}and pin['mode']in('0o400','0o444','0o555','0o644','0o664','0o755','0o775'),'critical_pin');c.pin_checked({k:pin[k]for k in('bytes','sha256')},2**34)
 c.need(type(g['packet'])is dict and set(g['packet'])=={'archive','manifest'},'packet');x.file_spec(g['packet']['archive'],134217728);x.file_spec(g['packet']['manifest'],4194304)
 for k in('result','aggregate','original_closed','preparation'):x.file_spec(g[k],c.MAX_MEMBER)
 c.need(type(g['output_root'])is str and Path(g['output_root']).is_absolute(),'output_root')
 d=g['dev_ordinals'];c.need(type(d)is list and len(d)==22 and all(type(i)is int and 0<=i<115 for i in d)and d==sorted(set(d)),'dev_order')
 c.need(type(g['stages'])is list and len(g['stages'])==18,'stages')
 for spec in g['stages']:x.file_spec(spec,262144)
 c.need(type(g['anchors'])is list and len(g['anchors'])==10,'ten_anchors')
 for a,pair in zip(g['anchors'],IDS):
  c.need(type(a)is dict and set(a)=={'seed','arm','checkpoint','history','metadata'}and type(a['seed'])is int and type(a['arm'])is str and(a['seed'],a['arm'])==pair,'anchor_order')
  for k,cap in(('checkpoint',8388608),('history',1048576),('metadata',c.MAX_MEMBER)):x.file_spec(a[k],cap)
 return g

def result_checked(result,g):
 c.need(type(result)is dict and set(result)==RESULT_KEYS and result['status']=='complete'and result['fit_authorized']is False,'complete_result')
 c.need(type(result['fits'])is list and len(result['fits'])==10 and type(result['comparisons'])is list and len(result['comparisons'])==24,'complete_counts');guard=result['advance'];c.need(type(guard)is dict and set(guard)=={'pass_all','checks'}and type(guard['pass_all'])is bool and type(guard['checks'])is list and len(guard['checks'])==24,'complete_guard')
 order=[(i,h)for i in g['dev_ordinals']for h in(1,3,5)]
 for fit,pair in zip(result['fits'],IDS):
  c.need(type(fit)is dict and type(fit['seed'])is int and type(fit['arm'])is str and(fit['seed'],fit['arm'])==pair and fit['status']=='complete'and fit['numerical_failures']==[],'fit_complete')
  c.need(type(fit['history'])is list and len(fit['history'])==300 and type(fit['predictions'])is list and len(fit['predictions'])==66,'fit_counts')
  for item,(ordinal,h)in zip(fit['predictions'],order):c.need(type(item)is dict and type(item['ordinal'])is int and type(item['horizon'])is int and(item['ordinal'],item['horizon'])==(ordinal,h),'record_order')
 return result

def positive_pin(v):
 c.need(type(v)is dict and set(v)in({'bytes','sha256'},{'bytes','sha256','mode'}),'closed_pin')
 if 'mode'in v:c.need(v['mode']=='0o400','closed_mode')
 pin={k:v[k]for k in('bytes','sha256')};c.pin_checked(pin,c.MAX_MEMBER);return pin

def custody_checked(g):
 prep=c.strict_json(load(g['preparation']));keys={'schema','passed','original_replay_verified','native_verified','continuation_closed','funding_resource_verified','publication_verified','linux_zero_skips','no_test','inputs'}
 c.need(type(prep)is dict and set(prep)==keys and prep['schema']=='receiver-complete-replay-preparation-v1'and all(prep[k]is True for k in keys-{'schema','inputs'}),'preparation_barred')
 c.need(type(prep['inputs'])is dict and {'original_provenance','native_agreement','continuation_agreement'}<=set(prep['inputs'])and len(prep['inputs'])<=32,'preparation_inputs')
 for spec in prep['inputs'].values():x.file_spec(spec,c.MAX_MEMBER);load(spec)
 stages=[];binding=None
 for i,(spec,identity)in enumerate(zip(g['stages'],PLAN)):
  v=c.strict_json(load(spec,262144));c.need(v['schema']=='receiver-continuation-stage-return-v3'and type(v['index'])is int and v['index']==i and(v['stage'],v['seed'],v['arm'])==identity and v['study']==STUDY and v['status']=='complete'and type(v['unit_exit'])is int and v['unit_exit']==0 and v['owned_unit_inactive']is True and v['owned_cgroup_empty']is True and type(v['files'])is dict,'closed_stage')
  value={k:v[k]for k in('experiment_begin','source_commit','scorer_binding','capacity','study_fingerprint')}
  if binding is None:binding=value
  c.need(value==binding,'closed_study_binding');stages.append(v)
 c.need(g['aggregate']['pin']==positive_pin(stages[17]['files']['stage_result.private.json']),'aggregate_closed_custody')
 aggregate=c.strict_json(load(g['aggregate']));result=result_checked(c.strict_json(load(g['result'])),g)
 c.need(RESULT_KEYS<=set(aggregate)and all(x.canonical(result[k])==x.canonical(aggregate[k])for k in RESULT_KEYS),'projection_exact_values')
 original=c.strict_json(load(g['original_closed']))['files']
 for a,pair in zip(g['anchors'],IDS):
  if pair in IDS[:3]:files=original;names={'checkpoint':'checkpoint_%s_%s.private.npz'%pair,'history':'history_%s_%s.private.jsonl'%pair}
  else:
   train=next(v for v in stages if(v['stage'],v['seed'],v['arm'])==('train',*pair));files=train['files'];names={'checkpoint':'checkpoint.private.npz','history':'history.private.jsonl'}
  for k,n in names.items():c.need(a[k]['pin']==positive_pin(files[n]),'anchor_closed_custody')
 return result

def claim(g,begin):
 gate_checked(g,begin);custody_checked(g);x.tick(begin);root=Path(g['output_root']);c.need(root.is_dir()and not root.is_symlink(),'output_directory');out=root/'replay';c.need(not out.exists(),'replay_exists')
 raw=(json.dumps(g,sort_keys=True,allow_nan=False)+'\n').encode();value=dict(schema='receiver-complete-replay-claim-v1',study=STUDY,processing_begin=begin,source_commit=g['source_commit'],gate_pin=c.pin(raw),no_retry=True);c.private_put(root,'replay_claim.private.json',value,262144);c.make_output_directory(out);store=c.Store(out);store.put('parent_gate.private.json',raw,1048576);store.put('replay_claim.private.json',value,262144);return out

def run_replay(gate,*,processing_begin,runner=x.managed_process,run=subprocess.run,check_output=subprocess.check_output):
 out=claim(gate,processing_begin);python=Path(gate['runtime']['prefix_directory'])/'venv/bin/python';parent=gate['sources']['parent']['directory'];code="import sys;sys.path.insert(0,%r);import replay_child;replay_child.main(%r)"%(parent,str(out))
 args=['systemd-run','--user','--unit='+UNIT[:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']+['--setenv='+k+'=1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]+['-p','MemoryMax=2147483648','-p','MemorySwapMax=0','-p','TasksMax=64','-p','CPUWeight=10','-p','RuntimeMaxSec=960','-p','TimeoutStopSec=5','-p','KillMode=control-group',str(python),'-I','-B','-c',code]
 x.tick(processing_begin)
 try:answer=runner(args,980)
 except Exception as e:answer=dict(code=None,timeout=True,exception_type=type(e).__name__,raw={k:b''for k in('stdout','stderr')},streams={k:dict(original_bytes=0,original_sha256=hashlib.sha256(b'').hexdigest(),retained_bytes=0,truncated=False,complete_observation=False)for k in('stdout','stderr')})
 store=c.Store(out);store.put('manager_stdout.private.bin',answer['raw']['stdout'],65536);store.put('manager_stderr.private.bin',answer['raw']['stderr'],131072);store.put('manager_return.private.json',{k:v for k,v in answer.items()if k!='raw'},262144)
 if answer['timeout']:
  try:stopped=run(['systemctl','--user','stop',UNIT],capture_output=True,timeout=10);store.put('manager_stop.private.json',dict(code=stopped.returncode,no_retry=True),262144)
  except Exception as e:store.put('manager_stop.private.json',dict(exception_type=type(e).__name__,no_retry=True),262144)
 text=check_output(['systemctl','--user','show',UNIT,'-p','Result','-p','ActiveState','-p','ControlGroup'],text=True,timeout=5);post=x.post_checked(text);store.put('post_properties.private.json',dict(raw=text,owned_unit_inactive=True,owned_cgroup_empty=True),262144);files,total=store.inventory(reserve=262144)
 result=None
 if 'replay_result.private.json'in files:result=c.strict_json(c.read_file(out/'replay_result.private.json',files['replay_result.private.json'],c.MAX_MEMBER))
 complete=post.get('Result')=='success'and type(answer['code'])is int and answer['code']==0 and not answer['timeout']and not any(v['truncated']or not v['complete_observation']for v in answer['streams'].values())and result is not None and result.get('status')=='pass'and result.get('checkpoint_forward_records')==660
 # Manager evidence is retained even if source deadline expiry makes finalization fail.
 x.tick(processing_begin);returned=dict(schema='receiver-complete-replay-parent-return-v1',status='pass'if complete else'fail',unit_exit=answer['code'],owned_unit_inactive=True,owned_cgroup_empty=True,files=files,total_bytes=total,no_retry=True,advance=result.get('advance')if complete else dict(pass_all=False,checks=[]));store.put('parent_return.private.json',returned,262144);return returned

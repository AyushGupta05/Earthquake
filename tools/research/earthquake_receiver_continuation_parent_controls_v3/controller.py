"""Single owned remote stage. No SSH, automatic loop, retry or science imports."""
from pathlib import Path
import hashlib
import json
import math
import os
import selectors
import subprocess
import sys
import time
import custody as c

STUDY='earthquake-TRAIN115-receiver-renewal-v2'
SEEDS=(20261012,20261013);ARMS=('B','F','H','T','C')
IDS=tuple((s,a)for s in SEEDS for a in ARMS)
PLAN=tuple([('score',s,a)for s,a in IDS[:3]]+[x for s,a in IDS[3:]for x in [('train',s,a),('score',s,a)]]+[('aggregate',None,None)])
GATE_KEYS={'schema','study','index','stage','seed','arm','experiment_begin','source_commit','admission','sources','runtime','packet','prerequisites','anchor','score_results','previous','experiment_root'}
PUBLICATION='earthquake_receiver_continuation_parent_source_push_v3_20261013.json'

def tick(begin,experiment,limit):
 now=time.monotonic()
 c.need(type(begin)in(int,float)and type(experiment)in(int,float)and math.isfinite(begin)and math.isfinite(experiment)and 0<=experiment<=begin<=now,'clock')
 c.need(now-begin<=limit and now-experiment<=7200,'parent_deadline')

def publication_commit(work):
 raw=(Path(work)/PUBLICATION).read_bytes();value=c.strict_json(raw,262144)['pushed_commit'];c.need(type(value)is str and len(value)==40 and all(x in'0123456789abcdef'for x in value),'publication_commit');return value

def file_spec(v,cap):
 c.need(type(v)is dict and set(v)=={'path','pin'}and type(v['path'])is str and len(v['path'])<=4096 and Path(v['path']).is_absolute(),'file_spec');c.pin_checked(v['pin'],cap)
 return v

def source_spec(v,count=None):
 c.need(type(v)is dict and set(v)=={'directory','files'}and type(v['directory'])is str and Path(v['directory']).is_absolute()and type(v['files'])is dict and 1<=len(v['files'])<=128,'source_spec')
 if count is not None:c.need(len(v['files'])==count,'source_members')
 for n,pin in v['files'].items():c.name_checked(n);c.pin_checked(pin,c.MAX_MEMBER)

def gate_checked(gate,begin):
 c.need(type(gate)is dict and set(gate)==GATE_KEYS and gate['schema']=='receiver-continuation-parent-gate-v3'and gate['study']==STUDY,'gate')
 i=gate['index'];c.need(type(i)is int and 0<=i<len(PLAN)and type(gate['stage'])is str and(gate['stage'],gate['seed'],gate['arm'])==PLAN[i],'stage_identity')
 c.need(gate['seed']is None if gate['stage']=='aggregate'else type(gate['seed'])is int,'seed_type');c.need(gate['arm']is None if gate['stage']=='aggregate'else type(gate['arm'])is str,'arm_type')
 tick(begin,gate['experiment_begin'],300 if gate['stage']=='train'else 900)
 commit=gate['source_commit'];c.need(type(commit)is str and len(commit)==40 and all(x in'0123456789abcdef'for x in commit),'source_commit')
 a=gate['admission'];c.need(type(a)is dict and set(a)=={'schema','original_replay_verified','source_runtime_verified','resource_verified','capacity','scorer_mode','scorer_binding','optional_scorer_verified'}and a['schema']=='receiver-continuation-admission-v3','admission')
 c.need(all(a[k]is True for k in('original_replay_verified','source_runtime_verified','resource_verified')),'admission_barred');c.need(a['scorer_mode']in('original','reviewed_optional')and type(a['scorer_binding'])is str and 0<len(a['scorer_binding'])<=128 and type(a['optional_scorer_verified'])is bool,'scorer_binding')
 c.need(type(a['capacity'])is dict and set(a['capacity'])=={'counts','nonzero_TRAIN_probe_gradient_degrees'},'capacity')
 c.need(a['capacity']['counts']=={'B':5007,'F':5147,'H':5125,'T':5125,'C':5125},'capacity')
 for d in a['capacity'].values():c.need(type(d)is dict and set(d)==set(ARMS)and all(type(v)is int and v>0 for v in d.values())and max(d.values())/min(d.values())<=1.05,'capacity')
 sources=gate['sources'];c.need(type(sources)is dict and set(sources)=={'candidate','engine','parent','optional'},'sources');source_spec(sources['candidate'],69);source_spec(sources['engine'],34);source_spec(sources['parent'])
 opt=sources['optional']
 if a['scorer_mode']=='original':c.need(opt is None and not a['optional_scorer_verified'],'optional_unadmitted')
 else:
  c.need(a['optional_scorer_verified']and type(opt)is dict and set(opt)=={'adapter','fast','factory','module','binding','proof'},'optional_unadmitted');source_spec(opt['adapter']);source_spec(opt['fast']);file_spec(opt['proof'],c.MAX_MEMBER)
  c.need(opt['factory']=='make_adapter'and type(opt['module'])is str and opt['module'].isidentifier()and opt['binding']==a['scorer_binding'],'optional_binding')
 r=gate['runtime'];c.need(type(r)is dict and set(r)=={'prefix_directory','manifest','canonical_sha256','critical_files','torch_site'}and all(type(r[k])is str and Path(r[k]).is_absolute()for k in('prefix_directory','torch_site'))and type(r['critical_files'])is dict and len(r['critical_files'])==10,'runtime');file_spec(r['manifest'],4194304);c.pin_checked({'bytes':0,'sha256':r['canonical_sha256']},0)
 for path,pin in r['critical_files'].items():c.need(type(path)is str and Path(path).is_absolute()and type(pin)is dict and set(pin)=={'bytes','sha256','mode'}and pin['mode']in('0o400','0o444','0o555','0o644','0o755'),'critical_pin');c.pin_checked({k:pin[k]for k in('bytes','sha256')},2**34)
 p=gate['packet'];c.need(type(p)is dict and set(p)=={'archive','manifest'},'packet_spec');file_spec(p['archive'],134217728);file_spec(p['manifest'],4194304);file_spec(gate['prerequisites'],c.MAX_MEMBER)
 c.need(type(gate['previous'])is list and len(gate['previous'])==i,'previous_prefix')
 for x in gate['previous']:file_spec(x,262144)
 c.need(type(gate['experiment_root'])is str and Path(gate['experiment_root']).is_absolute(),'experiment_root')
 if gate['stage']=='score':
  c.need(type(gate['anchor'])is dict and set(gate['anchor'])=={'checkpoint','history','metadata'},'anchor_spec')
  for k,cap in(('checkpoint',8388608),('history',1048576),('metadata',c.MAX_MEMBER)):file_spec(gate['anchor'][k],cap)
 else:c.need(gate['anchor']is None,'unexpected_anchor')
 if gate['stage']=='aggregate':
  c.need(type(gate['score_results'])is list and len(gate['score_results'])==10,'score_results')
  for x in gate['score_results']:file_spec(x,c.MAX_MEMBER)
 else:c.need(gate['score_results']is None,'unexpected_results')
 return gate

def prerequisites(gate):
 v=c.strict_json(c.read_file(gate['prerequisites']['path'],gate['prerequisites']['pin'],c.MAX_MEMBER));keys={'schema','passed','native_observations_verified','original_checkpoint_forward_records','original_independent_scores','original_replay_agreed','prior_units_inactive','prior_cgroups_empty','publication_verified','linux_zero_skips','funding_resource_authorized','inputs'}
 c.need(type(v)is dict and set(v)==keys and v['schema']=='receiver-continuation-prerequisites-v3','prerequisites')
 c.need(all(v[k]is True for k in keys-{'schema','original_checkpoint_forward_records','original_independent_scores','inputs'}),'prerequisites_barred')
 c.need(type(v['original_checkpoint_forward_records'])is int and v['original_checkpoint_forward_records']==178 and type(v['original_independent_scores'])is int and v['original_independent_scores']==178,'original_replay_barred')
 c.need(type(v['inputs'])is dict and {'native','original_replay','original_agreement','original_closed_output'}<=set(v['inputs'])and len(v['inputs'])<=32,'prerequisite_inputs')
 for x in v['inputs'].values():file_spec(x,c.MAX_MEMBER);c.read_file(x['path'],x['pin'],c.MAX_MEMBER)
 return v

def previous_checked(gate):
 for i,spec in enumerate(gate['previous']):
  v=c.strict_json(c.read_file(spec['path'],spec['pin'],262144));c.need(v['schema']=='receiver-continuation-stage-return-v3'and v['index']==i and type(v['index'])is int and(v['stage'],v['seed'],v['arm'])==PLAN[i]and v['status']=='complete'and type(v['unit_exit'])is int and v['unit_exit']==0 and v['owned_unit_inactive']is True and v['owned_cgroup_empty']is True,'previous_incomplete')
  c.need(v['experiment_begin']==gate['experiment_begin']and v['source_commit']==gate['source_commit']and v['scorer_binding']==gate['admission']['scorer_binding']and v['capacity']==gate['admission']['capacity']and v['study_fingerprint']==study_fingerprint(gate),'study_binding')

def aggregate_custody(gate):
 if gate['stage']!='aggregate':return
 scored=[spec for spec,identity in zip(gate['previous'],PLAN)if identity[0]=='score']
 c.need(len(scored)==10,'aggregate_closed_count')
 for spec,result in zip(scored,gate['score_results']):
  closed=c.strict_json(c.read_file(spec['path'],spec['pin'],262144))
  prior=closed['files']['stage_result.private.json'];c.pin_checked(prior,c.MAX_MEMBER)
  c.need(result['pin']==prior,'aggregate_score_custody')

def study_fingerprint(gate):
 value={k:gate[k]for k in('study','experiment_begin','source_commit','admission','sources','runtime','packet','prerequisites','experiment_root')}
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def anchor_custody(gate,proof):
 if gate['stage']!='score':return
 if (gate['seed'],gate['arm'])in IDS[:3]:
  spec=proof['inputs']['original_closed_output'];closed=c.strict_json(c.read_file(spec['path'],spec['pin'],c.MAX_MEMBER));files=closed['files'];names={'checkpoint':'checkpoint_%s_%s.private.npz'%(gate['seed'],gate['arm']),'history':'history_%s_%s.private.jsonl'%(gate['seed'],gate['arm'])}
 else:
  spec=gate['previous'][-1];closed=c.strict_json(c.read_file(spec['path'],spec['pin'],262144));c.need(closed['stage']=='train'and(closed['seed'],closed['arm'])==(gate['seed'],gate['arm']),'fresh_anchor_training');files=closed['files'];names={'checkpoint':'checkpoint.private.npz','history':'history.private.jsonl'}
 for kind,name in names.items():
  prior=files[name];c.need(type(prior)is dict and set(prior)in({'bytes','sha256'},{'bytes','sha256','mode'}),'anchor_closed_pin')
  if 'mode'in prior:c.need(prior['mode']=='0o400','anchor_closed_mode')
  c.need(gate['anchor'][kind]['pin']=={k:prior[k]for k in('bytes','sha256')},'anchor_final_custody')

def claim_stage(gate,begin):
 gate_checked(gate,begin);proof=prerequisites(gate);previous_checked(gate);anchor_custody(gate,proof);aggregate_custody(gate);tick(begin,gate['experiment_begin'],300 if gate['stage']=='train'else 900)
 root=Path(gate['experiment_root']);c.need(root.is_dir()and not root.is_symlink(),'experiment_directory')
 label='%02d_%s'%(gate['index'],gate['stage']);out=root/('stage_'+label);c.need(not out.exists(),'stage_exists')
 claim=dict(schema='receiver-continuation-durable-stage-claim-v3',study=STUDY,index=gate['index'],stage=gate['stage'],seed=gate['seed'],arm=gate['arm'],experiment_begin=gate['experiment_begin'],processing_begin=begin,source_commit=gate['source_commit'],scorer_binding=gate['admission']['scorer_binding'],gate_pin=c.pin((json.dumps(gate,sort_keys=True,allow_nan=False)+'\n').encode()),study_fingerprint=study_fingerprint(gate),no_retry=True)
 c.private_put(root,'claim_'+label+'.private.json',claim,262144);c.make_output_directory(out);store=c.Store(out);claim_pin=store.put('stage_claim.private.json',claim,262144);store.put('parent_gate.private.json',gate,1048576)
 return out,claim,claim_pin

class ClaimAcknowledgement:
 def __init__(self,claim,seed,arm,stage):
  c.need(type(claim)is dict and claim.get('schema')=='receiver-continuation-durable-stage-claim-v3'and claim.get('no_retry')is True and(claim.get('seed'),claim.get('arm'),claim.get('stage'))==(seed,arm,'train'if stage=='training'else'score'),'claim_identity')
  self.claim=claim;self.seed=seed;self.arm=arm;self.stage=stage;self.used=False
 def __call__(self,seed,arm,stage):
  c.need(not self.used,'claim_once');self.used=True
  c.need(type(seed)is int and type(arm)is str and type(stage)is str and(seed,arm,stage)==(self.seed,self.arm,self.stage),'claim_identity');return True

# Drains continuously with bounded retained raw prefixes; hashes/counts all observed bytes.
def managed_process(args,timeout,popen=subprocess.Popen,clock=time.monotonic):
 buffers={k:bytearray()for k in('stdout','stderr')};hashes={k:hashlib.sha256()for k in buffers};counts={k:0 for k in buffers};caps={'stdout':65536,'stderr':131072};proc=None;selector=None;code=None;interrupted=False;failure=None
 try:
  start=clock();proc=popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE);selector=selectors.DefaultSelector()
  for k,pipe in(('stdout',proc.stdout),('stderr',proc.stderr)):os.set_blocking(pipe.fileno(),False);selector.register(pipe,selectors.EVENT_READ,k)
  while selector.get_map():
   if clock()-start>timeout:interrupted=True;proc.terminate();break
   for key,_ in selector.select(.1):
    b=os.read(key.fileobj.fileno(),65536)
    if not b:selector.unregister(key.fileobj);continue
    k=key.data;hashes[k].update(b);counts[k]+=len(b);buffers[k].extend(b[:max(0,caps[k]-len(buffers[k]))])
  try:code=proc.wait(timeout=5)
  except subprocess.TimeoutExpired:interrupted=True;proc.kill();code=proc.wait(timeout=5)
 except Exception as error:
  interrupted=True;failure=type(error).__name__
  if proc is not None:
   try:proc.terminate()
   except Exception:pass
   try:code=proc.wait(timeout=5)
   except Exception:
    try:proc.kill();code=proc.wait(timeout=5)
    except Exception:pass
 finally:
  if selector is not None:
   try:selector.close()
   except Exception:interrupted=True
  if proc is not None:
   for pipe in(proc.stdout,proc.stderr):
    try:pipe.close()
    except Exception:interrupted=True
 streams={k:dict(original_bytes=counts[k],original_sha256=hashes[k].hexdigest(),retained_bytes=len(buffers[k]),truncated=counts[k]>len(buffers[k]),complete_observation=not interrupted)for k in buffers}
 answer=dict(code=code,timeout=interrupted,raw={k:bytes(v)for k,v in buffers.items()},streams=streams)
 if failure is not None:answer['exception_type']=failure
 return answer

def post_checked(text):
 c.need(type(text)is str and len(text.encode())<=16384,'post_cap');props={}
 for line in text.splitlines():
  if '='in line:k,v=line.split('=',1);c.need(k not in props,'post_duplicate');props[k]=v
 c.need(props.get('ActiveState')in('inactive','failed')and props.get('ControlGroup')=='','owned_cleanup_unverified');return props

def run_stage(gate,*,processing_begin,runner=managed_process,run=subprocess.run,check_output=subprocess.check_output):
 out,claim,claim_pin=claim_stage(gate,processing_begin);stage=gate['stage'];manager=360 if stage=='train'else 960;unit='eew-receiver-continuation-v3-%02d.service'%gate['index'];parent=gate['sources']['parent']['directory'];python=Path(gate['runtime']['prefix_directory'])/'venv/bin/python';code="import sys;sys.path.insert(0,%r);import stage_child;stage_child.main(%r)"%(parent,str(out))
 args=['systemd-run','--user','--unit='+unit[:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']+['--setenv='+k+'=1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]+['-p','MemoryMax=2147483648','-p','MemorySwapMax=0','-p','TasksMax=64','-p','CPUWeight=10','-p','RuntimeMaxSec='+str(manager),'-p','TimeoutStopSec=5','-p','KillMode=control-group',str(python),'-I','-B','-c',code]
 tick(processing_begin,gate['experiment_begin'],300 if stage=='train'else 900)
 try:answer=runner(args,manager+20)
 except Exception as e:
  answer=dict(code=None,timeout=True,raw={'stdout':b'','stderr':b''},streams={k:dict(original_bytes=0,original_sha256=hashlib.sha256(b'').hexdigest(),retained_bytes=0,truncated=False,complete_observation=False)for k in('stdout','stderr')},exception_type=type(e).__name__)
 store=c.Store(out)
 store.put('manager_stdout.private.bin',answer['raw']['stdout'],65536);store.put('manager_stderr.private.bin',answer['raw']['stderr'],131072)
 journal=dict(schema='receiver-continuation-manager-return-v3',unit_exit=answer['code'],timeout=answer['timeout'],streams=answer['streams'],status='incomplete_pending_owned_cleanup',no_retry=True,exception_type=answer.get('exception_type'));store.put('manager_return.private.json',journal,262144)
 if answer['timeout']:
  try:stop=run(['systemctl','--user','stop',unit],capture_output=True,timeout=10);store.put('manager_stop.private.json',{'code':stop.returncode,'no_retry':True},262144)
  except Exception as e:store.put('manager_stop.private.json',{'exception_type':type(e).__name__,'no_retry':True},262144)
 text=check_output(['systemctl','--user','show',unit,'-p','Result','-p','ActiveState','-p','ControlGroup'],text=True,timeout=5);post=post_checked(text)
 store.put('post_properties.private.json',dict(raw=text,owned_unit_inactive=True,owned_cgroup_empty=True),262144)
 files,total=store.inventory(reserve=262144);result_path=out/'stage_result.private.json';result=None
 if result_path.name in files:result=c.strict_json(c.read_file(result_path,files[result_path.name],c.MAX_MEMBER))
 normal=post.get('Result')=='success'and type(answer['code'])is int and answer['code']==0 and not answer['timeout']and not any(v['truncated']or not v['complete_observation']for v in answer['streams'].values())and result is not None and result.get('status')==('trained'if stage=='train'else'complete')
 tick(processing_begin,gate['experiment_begin'],manager+35)
 returned=dict(schema='receiver-continuation-stage-return-v3',study=STUDY,index=gate['index'],stage=stage,seed=gate['seed'],arm=gate['arm'],experiment_begin=gate['experiment_begin'],source_commit=gate['source_commit'],scorer_binding=gate['admission']['scorer_binding'],capacity=gate['admission']['capacity'],study_fingerprint=study_fingerprint(gate),status='complete'if normal else'incomplete',unit_exit=answer['code'],owned_unit_inactive=True,owned_cgroup_empty=True,post_properties=text,files=files,total_bytes=total,stage_claim_pin=claim_pin,no_retry=True)
 store.put('parent_return.private.json',returned,262144);return returned

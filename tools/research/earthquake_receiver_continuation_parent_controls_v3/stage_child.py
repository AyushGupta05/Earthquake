"""Owned stage child: stdlib until every source/runtime/input/live claim gate passes."""
from pathlib import Path
import importlib
import json
import math
import os
import subprocess
import sys
import time
from types import SimpleNamespace
import custody as c
import controller as parent


def read_raw(path,cap):
 path=Path(path);c.need(path.is_file()and not path.is_symlink(),'raw_file')
 with path.open('rb')as f:raw=f.read(cap+1)
 c.need(len(raw)<=cap,'raw_cap');return raw

def load_spec(spec,cap):return c.read_file(spec['path'],spec['pin'],cap)

def live_controls(gate,check_output=subprocess.check_output,proc=Path('/proc/self/cgroup'),base=Path('/sys/fs/cgroup')):
 unit='eew-receiver-continuation-v3-%02d.service'%gate['index'];rows=read_raw(proc,16384).decode().splitlines();paths=[s[3:]for s in rows if s.startswith('0::')];c.need(len(paths)==1 and paths[0].startswith('/')and Path(paths[0]).name==unit,'owned_unit');group=base/paths[0].lstrip('/');limits={k:read_raw(group/k,128).decode().strip()for k in('memory.max','memory.swap.max','pids.max')};c.need(limits=={'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64'},'live_limits');c.need(str(os.getpid())in read_raw(group/'cgroup.procs',16384).decode().split(),'live_membership')
 text=check_output(['systemctl','--user','show',unit,'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode','-p','ActiveState','-p','CPUWeight'],text=True,timeout=5);c.need(len(text.encode())<=16384,'manager_cap');properties=dict(line.split('=',1)for line in text.splitlines()if '='in line)
 duration={'6min','6min 0s','360s','360000000us'}if gate['stage']=='train'else{'16min','16min 0s','960s','960000000us'}
 c.need(properties.get('RuntimeMaxUSec')in duration and properties.get('TimeoutStopUSec')in{'5s','5000000us'}and properties.get('KillMode')=='control-group'and properties.get('ActiveState')=='active'and properties.get('CPUWeight')=='10','live_manager')
 c.need(os.environ.get('CUDA_VISIBLE_DEVICES')==''and all(os.environ.get(k)=='1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'))and sys.dont_write_bytecode,'live_environment')
 return dict(limits=limits,manager=text)

def source_verify(spec,check):
 directory=Path(spec['directory']);c.need(directory.is_dir()and not directory.is_symlink(),'source_directory');actual={p.name for p in directory.iterdir()if p.is_file()};extra='parent_upload_manifest.private.json';allowed=set(spec['files'])
 if extra in actual:
  metadata=directory/extra;c.need(metadata.stat().st_mode&0o777==0o400 and c.strict_json(read_raw(metadata,1048576),1048576)==spec['files'],'source_upload_manifest');allowed=allowed|{extra}
 c.need(actual==allowed and all(p.is_file()and not p.is_symlink()for p in directory.iterdir()),'source_membership')
 for n,pin in spec['files'].items():check();c.read_file(directory/n,pin,c.MAX_MEMBER)

def runtime_verify(runtime,check):
 root=Path(runtime['prefix_directory']);raw=load_spec(runtime['manifest'],4194304);m=c.strict_json(raw,4194304);c.need(hashlib_sha(canonical(m))==runtime['canonical_sha256']and type(m.get('files'))is dict and len(m['files'])==10112,'runtime_manifest')
 actual={str(p.relative_to(root))for p in(root/'venv').rglob('*')if p.is_file()and not p.is_symlink()};c.need(actual==set(m['files']),'runtime_membership')
 for n,pin in m['files'].items():
  c.need(type(n)is str and Path(n).parts[0]=='venv'and not Path(n).is_absolute()and '..'not in Path(n).parts,'runtime_path');check();c.hash_file(root/n,pin,0o444)
 for n,pin in runtime['critical_files'].items():check();c.hash_file(n,pin,int(pin['mode'],8))

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode('utf8')
def hashlib_sha(v):return __import__('hashlib').sha256(v).hexdigest()

def import_bound(module,directory):
 expected=Path(directory)/ (module+'.py')
 if module in sys.modules:c.need(Path(sys.modules[module].__file__).resolve()==expected.resolve(),'ambient_module_collision')
 loaded=importlib.import_module(module);c.need(Path(loaded.__file__).resolve()==expected.resolve(),'import_identity');return loaded

def deps_load(gate,check=lambda:None):
 sources=gate['sources'];candidate=Path(sources['candidate']['directory']);sys.path.append(gate['runtime']['torch_site']);sys.path.insert(0,str(candidate))
 check();import numpy as np
 check();import torch
 check();import scipy
 check()
 c.need(sys.version_info[:3]==(3,9,25)and np.__version__=='2.0.2'and torch.__version__=='2.8.0+cu128'and scipy.__version__=='1.13.1'and not torch.cuda.is_initialized(),'runtime_versions');torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
 modules={}
 for n in('mixture_density','numerical_core','posterior_scores','models','observations','packet_io','pilot'):check();modules[n]=import_bound(n,candidate)
 check()
 c.need(modules['pilot'].core is modules['numerical_core']and modules['pilot'].density is modules['mixture_density']and modules['pilot'].observations is modules['observations']and modules['pilot'].posterior_scores is modules['posterior_scores'],'transitive_import_identity')
 sys.path.insert(0,sources['engine']['directory']);check();engine=import_bound('engine',sources['engine']['directory']);deps=SimpleNamespace(pilot=modules['pilot'],models=modules['models'],torch=torch,core=modules['numerical_core']);scorer=None
 optional=sources['optional']
 if optional is not None and gate['stage']=='score':
  sys.path.insert(0,optional['fast']['directory']);check();reference=import_bound('reference',optional['fast']['directory']);check();fast=import_bound('scorer',optional['fast']['directory']);c.need(sys.modules.get('reference')is reference,'fast_reference_identity')
  sys.path.insert(0,optional['adapter']['directory']);check();adapter=import_bound(optional['module'],optional['adapter']['directory']);deps.fast_scorer=fast;check();scorer=getattr(adapter,optional['factory'])(deps);c.need(callable(scorer),'adapter_callable');check()
 return engine,deps,modules['packet_io'],np,scorer

def optional_proof(gate):
 opt=gate['sources']['optional']
 if opt is None:return
 v=c.strict_json(load_spec(opt['proof'],c.MAX_MEMBER));c.need(type(v)is dict and set(v)=={'schema','binding','published','linux_zero_skips','source_verified','authority_before_first_stage','sources'}and v['schema']=='receiver-fixed-optional-scorer-adoption-v3'and v['binding']==gate['admission']['scorer_binding'],'optional_adoption')
 c.need(all(v[k]is True for k in('published','linux_zero_skips','source_verified','authority_before_first_stage'))and v['sources']=={k:opt[k]['files']for k in('adapter','fast')},'optional_adoption_barred')

def before_import(gate,out,claim):
 begin=claim['processing_begin'];parent.gate_checked(gate,begin);check=lambda:parent.tick(begin,gate['experiment_begin'],300 if gate['stage']=='train'else 900)
 proof=parent.prerequisites(gate);parent.previous_checked(gate);parent.anchor_custody(gate,proof);parent.aggregate_custody(gate);optional_proof(gate);live=live_controls(gate)
 c.need(claim['gate_pin']==c.pin(read_raw(out/'parent_gate.private.json',1048576))and claim['study_fingerprint']==parent.study_fingerprint(gate),'durable_claim_binding')
 label='%02d_%s'%(gate['index'],gate['stage']);global_path=Path(gate['experiment_root'])/('claim_'+label+'.private.json');global_raw=read_raw(global_path,262144);c.need(c.strict_json(global_raw,262144)==claim and global_path.stat().st_mode&0o777==0o400,'global_claim_binding')
 for kind in('candidate','engine','parent'):source_verify(gate['sources'][kind],check)
 if gate['sources']['optional']is not None:
  for kind in('adapter','fast'):source_verify(gate['sources']['optional'][kind],check)
 c.need(Path(c.__file__).parent.resolve()==Path(gate['sources']['parent']['directory']).resolve()and Path(parent.__file__).parent.resolve()==Path(gate['sources']['parent']['directory']).resolve(),'parent_module_identity')
 runtime_verify(gate['runtime'],check);check();archive=load_spec(gate['packet']['archive'],134217728);manifest=load_spec(gate['packet']['manifest'],4194304);check()
 head=subprocess.check_output(['git','-C','/home/ec2-user/Earthquake','rev-parse','HEAD'],text=True,timeout=5).strip();c.need(head==gate['source_commit'],'published_head');check()
 return archive,manifest,live

def anchor_reader(gate,np,stats):
 used=[False]
 def read(seed,arm):
  c.need(not used[0]and(seed,arm)==(gate['seed'],gate['arm']),'anchor_once');used[0]=True;spec=gate['anchor'];state,scalers=c.checkpoint_load(load_spec(spec['checkpoint'],8388608),np)
  c.need(set(scalers)==set(stats)and all(a.dtype==stats[k].dtype and a.shape==stats[k].shape and a.tobytes()==stats[k].tobytes()for k,a in scalers.items()),'anchor_scalers_exact')
  raw=load_spec(spec['history'],1048576);history=[c.strict_json(line,4096)for line in raw.splitlines()];c.need(len(history)==300,'anchor_history')
  m=c.strict_json(load_spec(spec['metadata'],c.MAX_MEMBER));c.need(type(m)is dict and set(m)=={'schema','seed','arm','kind','mref','train_population_std','retained_predictions'}and m['schema']=='receiver-final-anchor-metadata-v3'and type(m['seed'])is int and m['seed']==seed and m['arm']==arm,'anchor_metadata')
  c.need(m['kind']==('original_final'if(seed,arm)in parent.IDS[:3]else'v3_final'),'anchor_kind')
  return dict(schema='receiver-final-anchor-v3',seed=seed,arm=arm,kind=m['kind'],state=state,scalers=scalers,history=history,mref=m['mref'],train_population_std=m['train_population_std'],retained_predictions=m['retained_predictions'])
 return read

def main(directory):
 out=Path(directory);store=c.Store(out,reserve_bytes=2097152,reserve_members=8);callbacks=None
 try:
  gate_raw=read_raw(out/'parent_gate.private.json',1048576);gate=c.strict_json(gate_raw,1048576);claim=c.strict_json(read_raw(out/'stage_claim.private.json',262144),262144)
  archive,manifest,live=before_import(gate,out,claim);store.put('live_controls.private.json',dict(live,source_members={k:len(gate['sources'][k]['files'])for k in('candidate','engine','parent')},prefix_files=10112,critical_files=10,study_fingerprint=parent.study_fingerprint(gate)),262144)
  check=lambda:parent.tick(claim['processing_begin'],gate['experiment_begin'],300 if gate['stage']=='train'else 900);check();engine,deps,packet_io,np,scorer=deps_load(gate,check);check();packet=packet_io.load(archive,manifest,pins={k:gate['packet'][k]['pin']for k in('archive','manifest')},processing_begin=claim['processing_begin']);roles=deps.pilot.validate(packet);c.need(len(roles['TRAIN'])==65 and len(roles['DEV'])==22,'packet_population')
  common=dict(admission=gate['admission'],processing_begin=claim['processing_begin'],experiment_begin=gate['experiment_begin']);stage=gate['stage'];seed=gate['seed'];arm=gate['arm']
  if stage=='aggregate':
   results=[c.strict_json(load_spec(s,c.MAX_MEMBER))for s in gate['score_results']];result=engine.aggregate(packet,results,deps,**common)
  else:
   acknowledgement=parent.ClaimAcknowledgement(claim,seed,arm,'training'if stage=='train'else'scoring');callbacks=c.Callbacks(store,seed,arm,np)
   if stage=='train':result=engine.train_stage(packet,seed,arm,deps,acknowledgement,callbacks.checkpoint,callbacks.history,**common)
   else:result=engine.score_stage(packet,seed,arm,deps,acknowledgement,anchor_reader(gate,np,deps.pilot.scaler(packet,roles['TRAIN'])),callbacks.prediction,scorer,**common)
  store.put('stage_result.private.json',result);store.put('completed.private.json',dict(status=result['status'],no_retry=True,stage=stage,seed=seed,arm=arm,CUDA_uninitialized=not deps.torch.cuda.is_initialized()),262144)
  c.need(result['status']==('trained'if stage=='train'else'complete'),'stage_incomplete');return result
 except BaseException as error:
  try:store.put('child_failure.private.json',dict(exception_type=type(error).__name__,reason=str(error)[:128],no_retry=True),262144)
  except Exception:pass
  raise
 finally:
  if callbacks is not None:callbacks.close()

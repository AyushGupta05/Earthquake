"""Replay all saved final forward values, then unchanged independent score audit."""
from pathlib import Path
import json
import math
import os
import subprocess
import sys
import custody as c
import controls as x
import controller as parent

HISTORY_KEYS={'update','base_nll','sequence_nll','joint_or_conditional_nll','gradient_norm','base_gradient_norm','sequence_gradient_norm','seconds'}

def live_controls(g,check_output=subprocess.check_output,proc=Path('/proc/self/cgroup'),base=Path('/sys/fs/cgroup')):
 paths=[row[3:]for row in x.read_raw(proc,16384).decode().splitlines()if row.startswith('0::')];c.need(len(paths)==1 and paths[0].startswith('/')and Path(paths[0]).name==parent.UNIT,'owned_unit');group=base/paths[0].lstrip('/');limits={k:x.read_raw(group/k,128).decode().strip()for k in('memory.max','memory.swap.max','pids.max')};c.need(limits=={'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64'}and str(os.getpid())in x.read_raw(group/'cgroup.procs',16384).decode().split(),'live_limits')
 text=check_output(['systemctl','--user','show',parent.UNIT,'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode','-p','ActiveState','-p','CPUWeight'],text=True,timeout=5);c.need(len(text.encode())<=16384,'manager_cap');v=dict(row.split('=',1)for row in text.splitlines()if '='in row)
 c.need(v.get('RuntimeMaxUSec')in('16min','16min 0s','960s','960000000us')and v.get('TimeoutStopUSec')in('5s','5000000us')and v.get('KillMode')=='control-group'and v.get('ActiveState')=='active'and v.get('CPUWeight')=='10','live_manager');c.need(sys.dont_write_bytecode and os.environ.get('CUDA_VISIBLE_DEVICES')==''and all(os.environ.get(k)=='1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')),'live_environment');return dict(limits=limits,manager=text)

def before_import(g,out,claim):
 begin=claim['processing_begin'];check=lambda:x.tick(begin);parent.gate_checked(g,begin);result=parent.custody_checked(g);live=live_controls(g)
 c.need(type(claim)is dict and set(claim)=={'schema','study','processing_begin','source_commit','gate_pin','no_retry'}and claim['schema']=='receiver-complete-replay-claim-v1'and claim['study']==parent.STUDY and claim['source_commit']==g['source_commit']and claim['no_retry']is True and claim['gate_pin']==c.pin(x.read_raw(out/'parent_gate.private.json',1048576)),'claim_binding')
 global_path=Path(g['output_root'])/'replay_claim.private.json';c.need(global_path.stat().st_mode&0o777==0o400 and c.strict_json(x.read_raw(global_path,262144),262144)==claim,'global_claim')
 for spec in g['sources'].values():x.source_verify(spec,check)
 d=Path(g['sources']['parent']['directory']).resolve();c.need(all(Path(module.__file__).parent.resolve()==d for module in(c,x,parent)),'parent_module_identity');x.runtime_verify(g['runtime'],check)
 for a in g['anchors']:
  for k in('checkpoint','history','metadata'):check();c.hash_file(a[k]['path'],a[k]['pin'],0o400)
 archive=parent.load(g['packet']['archive'],134217728);manifest=parent.load(g['packet']['manifest'],4194304);check();head=subprocess.check_output(['git','-C','/home/ec2-user/Earthquake','rev-parse','HEAD'],text=True,timeout=5).strip();c.need(head==g['source_commit'],'publication_head');check();return result,archive,manifest,live

def dependencies(g,check):
 check();sys.path.append(g['runtime']['torch_site']);candidate=g['sources']['candidate']['directory'];sys.path.insert(0,candidate)
 check();import numpy as np
 check();import torch
 check();import scipy
 check();c.need(sys.version_info[:3]==(3,9,25)and np.__version__=='2.0.2'and torch.__version__=='2.8.0+cu128'and scipy.__version__=='1.13.1'and not torch.cuda.is_initialized(),'runtime_versions');torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
 modules={}
 for n in('mixture_density','numerical_core','posterior_scores','models','observations','packet_io','pilot'):check();modules[n]=x.import_bound(n,candidate)
 p=modules['pilot'];c.need(p.core is modules['numerical_core']and p.density is modules['mixture_density']and p.posterior_scores is modules['posterior_scores']and p.observations is modules['observations'],'candidate_transitive');c.need(modules['packet_io'].obs is modules['observations']and modules['packet_io'].pilot is p and modules['models'].torch is torch,'candidate_packet_transitive')
 auditdir=g['sources']['auditor']['directory'];sys.path.insert(0,auditdir);auditmods={}
 for n in('numerical','packet_validation','metrics','auditor'):check();auditmods[n]=x.import_bound(n,auditdir)
 auditor=auditmods['auditor']
 for name,fields in(('numerical',('Posterior','factors','mixture_from_raw','hermite','gaussian_score','finite','NumericalFailure')),('packet_validation',('validate','scaler','model_context','diagnostics','keys','integer')),('metrics',('SEEDS','ARMS','HORIZONS','metrics','strata','paired','advance'))):
  c.need(all(getattr(auditor,n)is getattr(auditmods[name],n)for n in fields),'audit_transitive_identity')
 c.need(auditmods['packet_validation'].ages is auditmods['numerical'].ages and auditmods['packet_validation'].NumericalFailure is auditmods['numerical'].NumericalFailure,'audit_packet_transitive');check();return np,torch,modules,auditor

def histories_checked(items):
 c.need(type(items)is list and len(items)==300,'history300')
 for i,v in enumerate(items,1):c.need(type(v)is dict and set(v)==HISTORY_KEYS and type(v['update'])is int and v['update']==i and all(type(t)in(int,float)and math.isfinite(t)for k,t in v.items()if k!='update')and v['seconds']>=0,'history_entry')

def exact_numeric(saved,fresh,np):
 pending=[saved,fresh]
 while pending:
  value=pending.pop()
  if type(value)is list:pending.extend(value)
  else:c.need(type(value)in(int,float)and math.isfinite(value),'forward_builtin_numeric')
 a=np.asarray(saved,dtype=np.float64);b=np.asarray(fresh,dtype=np.float64);c.need(a.shape==b.shape and np.isfinite(a).all()and np.isfinite(b).all()and a.tobytes()==b.tobytes(),'checkpoint_forward_mismatch')

class Journal:
 def __init__(self,store):self.store=store;self.f=None;self.count=0
 def put(self,item):
  c.need(self.count<660,'forward_count');raw=(json.dumps(item,sort_keys=True,allow_nan=False)+'\n').encode();c.need(len(raw)<=4096 and self.store.total+len(raw)<=c.MAX_TOTAL-self.store.reserve_bytes,'forward_cap')
  if self.f is None:
   c.need(self.store.members+1<=c.MAX_MEMBERS-self.store.reserve_members,'forward_cap');fd=os.open(self.store.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
   try:
    f=os.open('forward.private.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=fd);self.f=os.fdopen(f,'wb');os.fchmod(f,0o400);self.store.members+=1;os.fsync(fd)
   finally:os.close(fd)
  c.need(self.f.tell()+len(raw)<=1048576,'forward_cap');self.f.write(raw);self.f.flush();os.fsync(self.f.fileno());self.store.total+=len(raw);self.count+=1
 def close(self):
  if self.f is not None:self.f.flush();os.fsync(self.f.fileno());self.f.close();self.f=None

def anchor(a,fit,stats,mean,std,net,np,torch):
 pair=(a['seed'],a['arm']);state,scalers=c.checkpoint_load(parent.load(a['checkpoint'],8388608),np);history=[c.strict_json(line,4096)for line in parent.load(a['history'],1048576).splitlines()];histories_checked(history);c.need(x.canonical(history)==x.canonical(fit['history']),'saved_history_exact');m=c.strict_json(parent.load(a['metadata']));keys={'schema','seed','arm','kind','mref','train_population_std','retained_predictions'}
 c.need(type(m)is dict and set(m)==keys and m['schema']=='receiver-final-anchor-metadata-v3'and type(m['seed'])is int and type(m['arm'])is str and(m['seed'],m['arm'])==pair and m['kind']==('original_final'if pair in parent.IDS[:3]else'v3_final'),'anchor_metadata')
 c.need(type(m['mref'])in(int,float)and type(m['train_population_std'])in(int,float)and m['mref']==mean and fit['mref']==mean and m['train_population_std']==std and fit['train_population_std']==std,'anchor_label_stats');n=(66 if pair[1]in('B','F')else 46)if pair in parent.IDS[:3]else 0;c.need(type(m['retained_predictions'])is list and len(m['retained_predictions'])==n,'anchor_retained')
 c.need(set(scalers)==set(stats)and all(scalers[k].dtype==stats[k].dtype and scalers[k].shape==stats[k].shape and scalers[k].tobytes()==stats[k].tobytes()for k in stats),'saved_scalers_exact');expected=net.state_dict();c.need(set(state)==set(expected)and all(state[k].shape==tuple(expected[k].shape)for k in state),'checkpoint_state_shapes');net.load_state_dict({k:torch.from_numpy(v.copy())for k,v in state.items()},strict=True);return scalers,history

def record_binding(item,row,h):
 c.need(type(item['ordinal'])is int and item['ordinal']==row['ordinal']and type(item['horizon'])is int and item['horizon']==h and type(item['target'])in(int,float)and math.isfinite(item['target'])and item['target']==row['mw']and type(item['group'])is int and item['group']==row['group']and item['receiver']==row['initial']['context'][9:12].tolist()and item['family']==('ENZ'if row['initial']['context'][15]==1 else'12Z')and item['rate']==row['horizons'][(1,3,5).index(h)]['rate'],'record_binding')

def forward(result,packet,g,np,torch,mods,journal,check):
 p=mods['pilot'];roles=p.validate(packet);c.need(roles['DEV']==g['dev_ordinals']and len(roles['TRAIN'])==65,'packet_roles');stats=p.scaler(packet,roles['TRAIN']);labels=np.asarray([packet['rows'][i]['mw']for i in roles['TRAIN']]);mean=float(labels.mean());std=float(labels.std(ddof=0));scalers={};histories={}
 with torch.no_grad():
  for a,fit,pair in zip(g['anchors'],result['fits'],parent.IDS):
   check();net=mods['models'].Net(pair[1],mean);scalers[pair],histories[pair]=anchor(a,fit,stats,mean,std,net,np,torch);net.eval()
   for item,(ordinal,h)in zip(fit['predictions'],((i,h)for i in roles['DEV']for h in(1,3,5))):
    check();row=packet['rows'][ordinal];record_binding(item,row,h);initial=pair[1]in('C','H','T');args=p.batch(packet,[ordinal],stats,initial,None if initial else h,pair[1]=='F');saved=item['numerical'];fresh={}
    if initial:
     raw,z=net.initial(*args);states,mask=p.state_batch(packet,[ordinal],h)
     fresh=dict(base_raw=raw[0].detach().cpu().double().tolist(),z=z[0].detach().cpu().double().tolist(),c=args[2][0].detach().cpu().double().tolist(),states=states[0,mask[0]].cpu().tolist(),hazard={k:getattr(net.hazards,k).detach().cpu().double().tolist()for k in('alpha','beta','z_weights','c_weights','gamma','extra')},mref=net.hazards.mref)
     c.need(type(saved['states'])is list and all(type(v)is int and v in(0,1)for v in saved['states'])and saved['states']==fresh['states'],'checkpoint_states');c.need(type(saved['hazard'])is dict and set(saved['hazard'])==set(fresh['hazard']),'checkpoint_hazard');exact_numeric(saved['mref'],fresh['mref'],np)
     for k in('base_raw','z','c'):exact_numeric(saved[k],fresh[k],np)
     for k in fresh['hazard']:exact_numeric(saved['hazard'][k],fresh['hazard'][k],np)
    else:
     raw=net.current(*args);mix=mods['numerical_core'].Mixture.from_raw(raw[0].detach().cpu().double().numpy());fresh={k:v.tolist()for k,v in(('pi',mix.weights),('mu',mix.means),('sigma',mix.sigmas))}
     for k in fresh:exact_numeric(saved[k],fresh[k],np)
    journal.put(dict(seed=pair[0],arm=pair[1],ordinal=ordinal,horizon=h,matched=True,saved_parameter_pin=c.pin(x.canonical({k:saved[k]for k in fresh})),forward_parameter_pin=c.pin(x.canonical(fresh))));check()
   del net
 c.need(journal.count==660 and set(scalers)==set(parent.IDS)and set(histories)==set(parent.IDS),'full660');return scalers,histories

def main(directory):
 out=Path(directory);store=c.Store(out,reserve_bytes=2097152,reserve_members=8);journal=Journal(store);begin=None
 try:
  g=c.strict_json(x.read_raw(out/'parent_gate.private.json',1048576),1048576);claim=c.strict_json(x.read_raw(out/'replay_claim.private.json',262144),262144);begin=claim['processing_begin'];check=lambda:x.tick(begin);result,archive,manifest,live=before_import(g,out,claim);store.put('live_controls.private.json',live,262144);check();np,torch,mods,auditor=dependencies(g,check);check();packet=mods['packet_io'].load(archive,manifest,pins={k:g['packet'][k]['pin']for k in('archive','manifest')},processing_begin=begin);check();scalers,histories=forward(result,packet,g,np,torch,mods,journal,check);journal.close();check();report=auditor.audit(result,packet,checkpoint_scalers=scalers,histories=histories,processing_begin=begin,wall_seconds=900);check();store.put('independent_audit.private.json',report);accepted=report['schema']=='earthquake-TRAIN115-renewal-score-audit-v3'and report['status']=='pass'
  if accepted:c.need(type(report['fits'])is list and len(report['fits'])==10 and all((v['seed'],v['arm'])==pair and type(v['predictions'])is list and len(v['predictions'])==66 for v,pair in zip(report['fits'],parent.IDS))and type(report['comparisons'])is list and len(report['comparisons'])==24,'audit_full660')
  value=dict(schema='receiver-complete-replay-result-v1',status='pass'if accepted else'fail',checkpoint_forward_records=journal.count,independent_scores=660 if accepted else 0,advance=report['advance']if accepted else dict(pass_all=False,checks=[]),fit_authorized=False,no_retry=True);check();store.put('replay_result.private.json',value);check();c.need(accepted,'independent_audit_failed');return value
 except BaseException as e:
  try:store.put('replay_failure.private.json',dict(schema='receiver-complete-replay-failure-v1',status='fail',reason=type(e).__name__,checkpoint_forward_records=journal.count,advance=dict(pass_all=False,checks=[]),fit_authorized=False,no_retry=True),262144)
  except Exception:pass
  raise
 finally:journal.close()

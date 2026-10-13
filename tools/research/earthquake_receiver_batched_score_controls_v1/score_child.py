"""Numeric-only child; every returned record/report persists before deadline checks."""
from pathlib import Path
import math
import os
import subprocess
import sys
import custody as c
import controls as x
import base
import controller as parent
import processor


def live(g,check_output=subprocess.check_output,proc=Path('/proc/self/cgroup'),root=Path('/sys/fs/cgroup')):
 unit='eew-receiver-batched-score-v1-%02d.service'%g['index'];paths=[v[3:]for v in x.read_raw(proc,16384).decode().splitlines()if v.startswith('0::')];c.need(len(paths)==1 and Path(paths[0]).name==unit and paths[0].startswith('/'),'owned_unit');group=root/paths[0].lstrip('/');limits={k:x.read_raw(group/k,128).decode().strip()for k in('memory.max','memory.swap.max','pids.max')};c.need(limits=={'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64'}and str(os.getpid())in x.read_raw(group/'cgroup.procs',16384).decode().split(),'live_limits');text=check_output(['systemctl','--user','show',unit,'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode','-p','ActiveState','-p','CPUWeight'],text=True,timeout=5);c.need(len(text.encode())<=16384,'live_cap');p=dict(v.split('=',1)for v in text.splitlines()if '='in v);c.need(p.get('RuntimeMaxUSec')in('16min','16min 0s','960s','960000000us')and p.get('TimeoutStopUSec')in('5s','5000000us')and p.get('KillMode')=='control-group'and p.get('ActiveState')=='active'and p.get('CPUWeight')=='10','live_manager');c.need(sys.dont_write_bytecode and os.environ.get('CUDA_VISIBLE_DEVICES')==''and all(os.environ.get(k)=='1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')),'live_environment');return dict(limits=limits,manager=text)

def before_import(g,out,claim):
 begin=claim['processing_begin'];check=lambda:parent.science_tick(begin,g['experiment_begin']);parent.gate_checked(g,begin);result=base.custody_checked(parent.old_gate(g));parent.forward_checked(g,result);parent.previous_checked(g);owned=live(g);c.need(claim['schema']=='receiver-batched-score-claim-v1'and type(claim['index'])is int and claim['index']==g['index']and claim['no_retry']is True and claim['fingerprint']==parent.fingerprint(g)and claim['gate_pin']==c.pin(x.read_raw(out/'parent_gate.private.json',1048576)),'claim_binding');globalfile=Path(g['output_root'])/('claim_%02d.private.json'%g['index']);c.need(globalfile.stat().st_mode&0o777==0o400 and c.strict_json(x.read_raw(globalfile,262144),262144)==claim,'global_claim')
 for spec in g['sources'].values():x.source_verify(spec,check)
 directory=Path(g['sources']['parent']['directory']).resolve();c.need(all(Path(module.__file__).parent.resolve()==directory for module in(c,x,base,parent,processor)),'parent_module_identity');x.runtime_verify(g['runtime'],check)
 for a in g['anchors']:
  for k in('checkpoint','history','metadata'):check();c.hash_file(a[k]['path'],a[k]['pin'],0o400)
 archive=base.load(g['packet']['archive'],134217728);manifest=base.load(g['packet']['manifest'],4194304);check();head=subprocess.check_output(['git','-C','/home/ec2-user/Earthquake','rev-parse','HEAD'],text=True,timeout=5).strip();c.need(head==g['source_commit'],'publication_head');check();return result,archive,manifest,owned

def dependencies(g,check):
 check();import numpy as np
 check();import scipy
 check();c.need(sys.version_info[:3]==(3,9,25)and np.__version__=='2.0.2'and scipy.__version__=='1.13.1','versions');c.need(not any(n in sys.modules for n in('torch','models','engine','adapter')),'no_model_import');candidate=g['sources']['candidate']['directory'];sys.path.insert(0,candidate);mods={}
 for n in('observations','numerical_core','mixture_density','posterior_scores','pilot','packet_io'):check();mods[n]=x.import_bound(n,candidate)
 p=mods['pilot'];c.need(p.observations is mods['observations']and p.core is mods['numerical_core']and p.density is mods['mixture_density']and p.posterior_scores is mods['posterior_scores']and mods['packet_io'].obs is mods['observations']and mods['packet_io'].pilot is p,'candidate_transitive');adirectory=g['sources']['auditor']['directory'];sys.path.insert(0,adirectory);audit={}
 for n in('numerical','packet_validation','metrics','auditor'):check();audit[n]=x.import_bound(n,adirectory)
 ad=audit['auditor']
 for n,fields in(('numerical',('Posterior','factors','mixture_from_raw','hermite','gaussian_score','finite','NumericalFailure')),('packet_validation',('validate','scaler','model_context','diagnostics','keys','integer')),('metrics',('SEEDS','ARMS','HORIZONS','metrics','strata','paired','advance'))):c.need(all(getattr(ad,k)is getattr(audit[n],k)for k in fields),'audit_transitive')
 c.need(audit['packet_validation'].ages is audit['numerical'].ages and audit['packet_validation'].NumericalFailure is audit['numerical'].NumericalFailure,'audit_packet_transitive');c.need(not any(n in sys.modules for n in('torch','models','engine','adapter')),'no_model_import');check();return np,mods['packet_io'],ad

def numeric_anchors(g,result,np):
 scalers={};histories={}
 for a,fit,pair in zip(g['anchors'],result['fits'],parent.IDS):
  state,st=c.checkpoint_load(base.load(a['checkpoint'],8388608),np);del state;history=[c.strict_json(line,4096)for line in base.load(a['history'],1048576).splitlines()];m=c.strict_json(base.load(a['metadata']));fields={'schema','seed','arm','kind','mref','train_population_std','retained_predictions'};c.need(type(m)is dict and set(m)==fields and m['schema']=='receiver-final-anchor-metadata-v3'and type(m['seed'])is int and type(m['arm'])is str and(m['seed'],m['arm'])==pair and m['kind']==('original_final'if pair in parent.IDS[:3]else'v3_final')and m['mref']==fit['mref']and m['train_population_std']==fit['train_population_std'],'anchor_metadata');n=(66 if pair[1]in('B','F')else 46)if pair in parent.IDS[:3]else 0;c.need(type(m['retained_predictions'])is list and len(m['retained_predictions'])==n,'anchor_retained');scalers[pair]=st;histories[pair]=history
 return scalers,histories

def main(directory):
 out=Path(directory);store=c.Store(out,reserve_bytes=2097152,reserve_members=8);outcomes={};g=None;begin=None;record_count=0
 try:
  g=c.strict_json(x.read_raw(out/'parent_gate.private.json',1048576),1048576);claim=c.strict_json(x.read_raw(out/'stage_claim.private.json',262144),262144);begin=claim['processing_begin'];check=lambda:parent.science_tick(begin,g['experiment_begin']);result,archive,manifest,owned=before_import(g,out,claim);store.put('live_controls.private.json',owned,262144);check();np,loader,ad=dependencies(g,check);check();packet=loader.load(archive,manifest,pins={k:g['packet'][k]['pin']for k in('archive','manifest')},processing_begin=begin);c.need(ad.validate(packet)['DEV']==g['dev_ordinals'],'dev_binding');check();scalers,histories=numeric_anchors(g,result,np);check()
  def retain(outcome):
   nonlocal record_count
   c.need(record_count<66 and type(outcome['position'])is int and outcome['position']==record_count,'outcome_order');name='record_%02d.private.json'%record_count;wrapped=dict(schema='receiver-batched-score-record-wrapper-v1',binding=parent.bindings(g),outcome=outcome)
   try:pin=store.put(name,wrapped)
   except (TypeError,ValueError):
    fallback=dict(schema='receiver-batched-score-record-wrapper-v1',binding=parent.bindings(g),outcome=dict(position=record_count,seed=g['seed'],arm=g['arm'],ordinal=outcome['ordinal'],horizon=outcome['horizon'],status='fail',fresh=None,reason='returned_outcome_unserializable'));store.put('unserializable_%02d.private.json'%record_count,fallback,262144);raise
   outcomes[name]=pin;record_count+=1
  if g['stage']=='fit':report=processor.fit_audit(result,packet,g['index'],scalers,histories,ad,np,check,retain)
  else:reports=parent.completed_reports(g);report=processor.aggregate(result,packet,reports,scalers,histories,ad,np,check)
  # No scientific tick between function return and durable report capture.
  wrapped=dict(schema='receiver-batched-score-stage-report-v1',binding=parent.bindings(g),index=g['index'],stage=g['stage'],within_budget=parent.within(begin,g['experiment_begin']),report=report,outcomes=outcomes);store.put('stage_report.private.json',wrapped);timely=parent.within(begin,g['experiment_begin']);store.put('completion.private.json',dict(within_budget=timely,no_retry=True,records=record_count,status=report['status']),262144);c.need(timely and parent.within(begin,g['experiment_begin']),'returned_report_late');c.need(g['stage']=='aggregate' or report['complete']is True,'partial_fit');return report
 except BaseException as error:
  # Failure retention has no expired scientific deadline gate.
  try:store.put('failure.private.json',dict(schema='receiver-batched-score-failure-v1',status='fail',reason=type(error).__name__,records=record_count,advance=dict(pass_all=False,checks=[]),within_budget=parent.within(begin,g['experiment_begin'])if g is not None and begin is not None else False,no_retry=True),262144)
  except Exception:pass
  raise

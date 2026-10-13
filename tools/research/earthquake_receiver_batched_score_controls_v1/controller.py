"""Fixed eleven-stage numeric-only continuation, no forwards/fits/retries."""
from pathlib import Path
import hashlib
import json
import math
import subprocess
import time
import custody as c
import controls as x
import base

IDS=base.IDS
EXTRA={'index','stage','seed','arm','experiment_begin','forward','previous'}
PUBLICATION='earthquake_receiver_batched_score_source_push_v1_20261013.json'

def science_tick(begin,experiment):
 x.tick(begin);now=time.monotonic();c.need(type(experiment)in(int,float)and math.isfinite(experiment)and 0<=experiment<=begin<=now and now-experiment<=12000,'experiment_deadline')

def within(begin,experiment):
 now=time.monotonic();return type(begin)in(int,float)and type(experiment)in(int,float)and math.isfinite(begin)and math.isfinite(experiment)and 0<=experiment<=begin<=now and now-begin<=900 and now-experiment<=12000

def old_gate(g):
 v={k:g[k]for k in base.GATE_KEYS};v['schema']='receiver-complete-replay-parent-gate-v1';return v

def publication_commit(work):
 v=c.strict_json((Path(work)/PUBLICATION).read_bytes(),262144)['pushed_commit'];c.need(type(v)is str and len(v)==40 and all(t in'0123456789abcdef'for t in v),'publication_commit');return v

def fingerprint(g):return hashlib.sha256(x.canonical({k:g[k]for k in set(g)-{'index','stage','seed','arm','previous'}})).hexdigest()

def gate_checked(g,begin):
 c.need(type(g)is dict and set(g)==base.GATE_KEYS|EXTRA and g['schema']=='receiver-batched-score-parent-gate-v1','gate');science_tick(begin,g['experiment_begin']);base.gate_checked(old_gate(g),begin);i=g['index'];c.need(type(i)is int and 0<=i<=10 and g['stage']==('fit'if i<10 else'aggregate'),'stage')
 if i<10:c.need(type(g['seed'])is int and type(g['arm'])is str and(g['seed'],g['arm'])==IDS[i],'stage_identity')
 else:c.need(g['seed']is None and g['arm']is None,'aggregate_identity')
 c.need(type(g['forward'])is dict and set(g['forward'])=={'journal','authority'},'forward')
 for k,cap in(('journal',1048576),('authority',c.MAX_MEMBER)):x.file_spec(g['forward'][k],cap)
 c.need(type(g['previous'])is list and len(g['previous'])==i,'previous_prefix')
 for spec in g['previous']:x.file_spec(spec,262144)
 return g

def forward_checked(g,result):
 proof=c.strict_json(base.load(g['forward']['authority']));keys={'schema','verified','forward_records','models','journal_pin','result_pin','packet_pins','source_pins','anchors'};c.need(type(proof)is dict and set(proof)==keys and proof['schema']=='root-complete660-forward-authority-v1'and proof['verified']is True and type(proof['forward_records'])is int and proof['forward_records']==660 and type(proof['models'])is int and proof['models']==10,'forward_authority')
 c.need(proof['journal_pin']==g['forward']['journal']['pin']and proof['result_pin']==g['result']['pin']and proof['packet_pins']=={k:g['packet'][k]['pin']for k in('archive','manifest')},'forward_input_binding');source=proof['source_pins'];c.need(type(source)is dict and set(source)=={'candidate','auditor','parent'}and source['candidate']==g['sources']['candidate']['files']and source['auditor']==g['sources']['auditor']['files'],'forward_source_binding');original=c.strict_json(x.read_raw(Path(__file__).parent/'ORIGINAL_FORWARD_SOURCE_PINS.json',65536),65536);c.need(source['parent']==original['parent'],'forward_parent_source')
 expected=[dict(seed=a['seed'],arm=a['arm'],**{k+'_pin':a[k]['pin']for k in('checkpoint','history','metadata')})for a in g['anchors']];c.need(proof['anchors']==expected,'forward_anchor_binding');rows=[c.strict_json(line,4096)for line in base.load(g['forward']['journal'],1048576).splitlines()];c.need(len(rows)==660,'forward660');pos=0
 for fit,pair in zip(result['fits'],IDS):
  for saved in fit['predictions']:
   v=rows[pos];pos+=1;c.need(type(v)is dict and set(v)=={'seed','arm','ordinal','horizon','matched','saved_parameter_pin','forward_parameter_pin'}and type(v['seed'])is int and type(v['ordinal'])is int and type(v['horizon'])is int and(v['seed'],v['arm'],v['ordinal'],v['horizon'])==(*pair,saved['ordinal'],saved['horizon'])and v['matched']is True,'forward_record')
   fields=('pi','mu','sigma')if pair[1]in('B','F')else('base_raw','z','c','states','hazard','mref');pin=c.pin(x.canonical({k:saved['numerical'][k]for k in fields}));c.need(v['saved_parameter_pin']==pin and v['forward_parameter_pin']==pin,'forward_parameter_pin')
 return proof

def previous_checked(g):
 rows=[]
 for i,spec in enumerate(g['previous']):
  v=c.strict_json(base.load(spec,262144));c.need(v['schema']=='receiver-batched-score-parent-return-v1'and type(v['index'])is int and v['index']==i and(v['seed'],v['arm'])==IDS[i]and v['status']=='complete'and v['stage']=='fit'and type(v['unit_exit'])is int and v['unit_exit']==0 and v['owned_unit_inactive']is True and v['owned_cgroup_empty']is True and v['fingerprint']==fingerprint(g)and v['no_retry']is True and v['output_directory']==str(Path(g['output_root'])/('stage_%02d'%i)),'previous_incomplete');rows.append(v)
 return rows

def bindings(g):return dict(fingerprint=fingerprint(g),source_commit=g['source_commit'],result_pin=g['result']['pin'],packet_pins={k:g['packet'][k]['pin']for k in('archive','manifest')},forward_authority_pin=g['forward']['authority']['pin'],forward_journal_pin=g['forward']['journal']['pin'])

def completed_reports(g):
 reports=[]
 for i,closed in enumerate(previous_checked(g)):
  directory=Path(closed['output_directory']);files=closed['files'];wrapper=c.strict_json(c.read_file(directory/'stage_report.private.json',files['stage_report.private.json'],c.MAX_MEMBER));c.need(wrapper['schema']=='receiver-batched-score-stage-report-v1'and wrapper['binding']==bindings(g)and wrapper['index']==i and wrapper['stage']=='fit'and wrapper['within_budget']is True,'report_binding');report=wrapper['report'];c.need(report['complete']is True and type(report['seed'])is int and type(report['arm'])is str and report['status']in('pass','fail')and type(report['reasons'])is list and((report['status']=='pass')==(not report['reasons']))and(report['seed'],report['arm'])==IDS[i]and type(wrapper['outcomes'])is dict and len(wrapper['outcomes'])==66,'report66')
  for j,item in enumerate(report['fit']['predictions']):
   name='record_%02d.private.json'%j;pin=wrapper['outcomes'][name];c.need(pin==files[name],'outcome_closed_pin');v=c.strict_json(c.read_file(directory/name,pin,c.MAX_MEMBER));c.need(v['schema']=='receiver-batched-score-record-wrapper-v1'and v['binding']==bindings(g)and v['outcome']['schema']=='receiver-numerical-record-outcome-v1'and v['outcome']['status']in('pass','fail')and((v['outcome']['status']=='pass')==(v['outcome']['reason']is None))and type(v['outcome']['position'])is int and v['outcome']['position']==j and(v['outcome']['seed'],v['outcome']['arm'])==IDS[i]and v['outcome']['fresh']==item and(v['outcome']['ordinal'],v['outcome']['horizon'])==(item['ordinal'],item['horizon']),'outcome_binding')
  reports.append(report)
 return reports

def claim(g,begin):
 gate_checked(g,begin);result=base.custody_checked(old_gate(g));forward_checked(g,result);previous_checked(g);science_tick(begin,g['experiment_begin']);root=Path(g['output_root']);c.need(root.is_dir()and not root.is_symlink(),'output_root');out=root/('stage_%02d'%g['index']);c.need(not out.exists(),'stage_exists');raw=(json.dumps(g,sort_keys=True,allow_nan=False)+'\n').encode();value=dict(schema='receiver-batched-score-claim-v1',index=g['index'],processing_begin=begin,gate_pin=c.pin(raw),fingerprint=fingerprint(g),no_retry=True);c.private_put(root,'claim_%02d.private.json'%g['index'],value,262144);c.make_output_directory(out);store=c.Store(out);store.put('parent_gate.private.json',raw,1048576);store.put('stage_claim.private.json',value,262144);return out

def run_stage(gate,*,processing_begin,runner=x.managed_process,run=subprocess.run,check_output=subprocess.check_output):
 out=claim(gate,processing_begin);unit='eew-receiver-batched-score-v1-%02d.service'%gate['index'];python=Path(gate['runtime']['prefix_directory'])/'venv/bin/python';source=gate['sources']['parent']['directory'];code="import sys;sys.path.insert(0,%r);import score_child;score_child.main(%r)"%(source,str(out));args=['systemd-run','--user','--unit='+unit[:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']+['--setenv='+k+'=1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]+['-p','MemoryMax=2147483648','-p','MemorySwapMax=0','-p','TasksMax=64','-p','CPUWeight=10','-p','RuntimeMaxSec=960','-p','TimeoutStopSec=5','-p','KillMode=control-group',str(python),'-I','-B','-c',code];science_tick(processing_begin,gate['experiment_begin'])
 try:answer=runner(args,980)
 except Exception as e:answer=dict(code=None,timeout=True,exception_type=type(e).__name__,raw={k:b''for k in('stdout','stderr')},streams={k:dict(original_bytes=0,original_sha256=hashlib.sha256(b'').hexdigest(),retained_bytes=0,truncated=False,complete_observation=False)for k in('stdout','stderr')})
 store=c.Store(out);store.put('manager_stdout.private.bin',answer['raw']['stdout'],65536);store.put('manager_stderr.private.bin',answer['raw']['stderr'],131072);store.put('manager_return.private.json',{k:v for k,v in answer.items()if k!='raw'},262144)
 if answer['timeout']:
  try:stopped=run(['systemctl','--user','stop',unit],capture_output=True,timeout=10);store.put('manager_stop.private.json',dict(code=stopped.returncode,no_retry=True),262144)
  except Exception as e:store.put('manager_stop.private.json',dict(exception_type=type(e).__name__,no_retry=True),262144)
 text=None
 try:
  text=check_output(['systemctl','--user','show',unit,'-p','Result','-p','ActiveState','-p','ControlGroup'],text=True,timeout=5)
  raw=text.encode('utf8',errors='replace')if type(text)is str else text if type(text)is bytes else b''
  store.put('post_properties_observed.private.bin',raw[:16384],16384);store.put('post_properties_observed.private.json',dict(original_bytes=len(raw),original_sha256=hashlib.sha256(raw).hexdigest(),retained_bytes=min(len(raw),16384),truncated=len(raw)>16384),262144)
  post=x.post_checked(text)
 except Exception as error:
  if text is None:
   partial=getattr(error,'output',None);raw=partial.encode('utf8',errors='replace')if type(partial)is str else partial if type(partial)is bytes else b''
   store.put('post_properties_observed.private.bin',raw[:16384],16384);store.put('post_properties_observed.private.json',dict(original_bytes=len(raw),original_sha256=hashlib.sha256(raw).hexdigest(),retained_bytes=min(len(raw),16384),truncated=len(raw)>16384),262144)
  store.put('cleanup_failure.private.json',dict(schema='receiver-batched-score-cleanup-failure-v1',exception_type=type(error).__name__,reason=str(error)[:128],cleanup_verified=False,no_retry=True),262144);files,total=store.inventory(reserve=262144)
  value=dict(schema='receiver-batched-score-parent-return-v1',index=gate['index'],stage=gate['stage'],seed=gate['seed'],arm=gate['arm'],status='incomplete',audit_status='fail',fingerprint=fingerprint(gate),output_directory=str(out),unit_exit=answer['code'],owned_unit_inactive=None,owned_cgroup_empty=None,cleanup_verified=False,files=files,total_bytes=total,no_retry=True,advance=dict(pass_all=False,checks=[]));store.put('parent_return.private.json',value,262144);return value
 store.put('post_properties.private.json',dict(raw=text,owned_unit_inactive=True,owned_cgroup_empty=True),262144);files,total=store.inventory(reserve=262144);report=None
 if 'stage_report.private.json'in files:report=c.strict_json(c.read_file(out/'stage_report.private.json',files['stage_report.private.json'],c.MAX_MEMBER))
 complete=post.get('Result')=='success'and type(answer['code'])is int and answer['code']==0 and not answer['timeout']and not any(v['truncated']or not v['complete_observation']for v in answer['streams'].values())and report is not None and report['schema']=='receiver-batched-score-stage-report-v1'and report['index']==gate['index']and report['stage']==gate['stage']and report['binding']==bindings(gate)and report['within_budget']is True and report['report']['status']in('pass','fail') and report['report'].get('complete',gate['stage']=='aggregate')is True
 value=dict(schema='receiver-batched-score-parent-return-v1',index=gate['index'],stage=gate['stage'],seed=gate['seed'],arm=gate['arm'],status='complete'if complete else'incomplete',audit_status=report['report']['status']if report else'fail',fingerprint=fingerprint(gate),output_directory=str(out),unit_exit=answer['code'],owned_unit_inactive=True,owned_cgroup_empty=True,files=files,total_bytes=total,no_retry=True,advance=report['report']['advance']if complete and report['report']['status']=='pass'else dict(pass_all=False,checks=[]));store.put('parent_return.private.json',value,262144);return value

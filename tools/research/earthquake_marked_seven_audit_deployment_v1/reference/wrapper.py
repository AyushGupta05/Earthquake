"""Pure bounded stage wrapper; no IO, provider, optimizer, scientific imports."""
import hashlib
import math
import time
from dataclasses import dataclass

STUDY='earthquake-TRAIN115-marked-noise-fitting-v2'
PAIRS=tuple((s,a)for s in(20261012,20261013)for a in('S','P','D'))
MEMBER=16*1024*1024
TOTAL=64*1024*1024

class ControlError(ValueError):pass

def need(v,reason):
 if not v:raise ControlError(reason)

def keys(v,names):need(type(v)is dict and set(v)==set(names),'keys')
def sha(v):return hashlib.sha256(v).hexdigest()
def hash_string(v):need(type(v)is str and len(v)==64 and all(c in'0123456789abcdef'for c in v),'sha256')
def finite(v):return type(v)in(int,float)and math.isfinite(v)

@dataclass(frozen=True)
class Bindings:
 audit_fit:object
 aggregate:object
 canonical:object
 binding_sha256:str
 def __post_init__(self):
  need(all(callable(v)for v in(self.audit_fit,self.aggregate,self.canonical)),'bindings');hash_string(self.binding_sha256)

def tick(gate,begin):
 now=time.monotonic();need(finite(begin)and 0<=gate['whole_begin']<=begin<=now,'processing_begin');need(now-begin<=900 and now-gate['whole_begin']<=7200 and now<=gate['lease_deadline'],'deadline')

def raw(value,bindings):
 encoded=bindings.canonical(value);need(type(encoded)is bytes and len(encoded)<=MEMBER,'canonical_bytes_cap');return encoded

def previous_checked(previous,stage,bindings,inputs):
 need(type(previous)is list and len(previous)==stage,'previous_count')
 for index,item in enumerate(previous):
  keys(item,('stage','seed','arm','inputs_sha256','binding_sha256','report_sha256','closed_proof_sha256','known_verified','exit_status','unit_inactive','cgroup_empty'));need(type(item['stage'])is int and item['stage']==index and type(item['seed'])is int and type(item['arm'])is str and(item['seed'],item['arm'])==PAIRS[index],'previous_identity');need(item['known_verified']is True and type(item['exit_status'])is int and item['exit_status']==0 and item['unit_inactive']is True and item['cgroup_empty']is True,'previous_closure')
  for key in('inputs_sha256','binding_sha256','report_sha256','closed_proof_sha256'):hash_string(item[key])
  need(item['binding_sha256']==bindings.binding_sha256,'previous_binding')
  if stage==6:
   audit=inputs['fit_audits'][index];need(item['report_sha256']==sha(raw(audit,bindings))and audit['status']=='pass'and type(audit['checked'])is int and audit['checked']==66 and(audit['seed'],audit['arm'])==PAIRS[index],'previous_report')

def preflight(stage,inputs,gate,bindings,begin):
 need(type(stage)is int and 0<=stage<=6 and type(bindings)is Bindings,'stage');keys(gate,('schema','study','stage','root_verified','proofs','binding_sha256','inputs_sha256','whole_begin','whole_seconds','closure_seconds','lease_deadline','disk_available_bytes','disk_reserve_bytes','stage_payload_cap_bytes','previous'));need(gate['schema']=='root-marked-sixfit-audit-wrapper-gate-v1'and gate['study']==STUDY and type(gate['stage'])is int and gate['stage']==stage and gate['root_verified']is True,'root_gate');keys(gate['proofs'],('source','runtime','native','stronger','history_gradient','resources'))
 for proof in gate['proofs'].values():keys(proof,('known_verified','sha256'));need(proof['known_verified']is True,'root_proof');hash_string(proof['sha256'])
 hash_string(gate['binding_sha256']);hash_string(gate['inputs_sha256']);need(gate['binding_sha256']==bindings.binding_sha256,'binding');need(type(gate['whole_seconds'])is int and gate['whole_seconds']==7200 and type(gate['closure_seconds'])is int and gate['closure_seconds']==200 and finite(gate['whole_begin'])and gate['whole_begin']>=0 and finite(gate['lease_deadline'])and gate['whole_begin']<gate['lease_deadline']<=gate['whole_begin']+7400,'clock_envelope');need(all(type(gate[k])is int and gate[k]>=0 for k in('disk_available_bytes','disk_reserve_bytes','stage_payload_cap_bytes'))and gate['stage_payload_cap_bytes']==TOTAL and gate['disk_available_bytes']-gate['disk_reserve_bytes']>=TOTAL,'disk_reservation');tick(gate,begin)
 if stage<6:
  keys(inputs,('score','packet','admission','checkpoint','authority'));score=inputs['score'];checkpoint=inputs['checkpoint'];need(type(score)is dict and type(checkpoint)is dict and type(score['seed'])is int and type(checkpoint['seed'])is int and(score['seed'],score['arm'])==(checkpoint['seed'],checkpoint['arm'])==PAIRS[stage],'fit_identity')
 else:
  keys(inputs,('fit_audits','score_results','packet','admission','stronger','authority'));need(type(inputs['fit_audits'])is list and len(inputs['fit_audits'])==6,'aggregate_six')
 need(sha(raw(inputs,bindings))==gate['inputs_sha256'],'input_binding');previous_checked(gate['previous'],stage,bindings,inputs);tick(gate,begin)

def receipt(value,digest):keys(value,('status','sha256'));need(value['status']=='durable'and value['sha256']==digest,'durable_receipt')

def result_checked(stage,result):
 need(type(result)is dict and result.get('status')=='pass'and type(result.get('checked'))is int,'audit_not_pass')
 if stage<6:need(result.get('schema')=='marked-sixfit-independent-audit-v1'and result['checked']==66 and type(result.get('seed'))is int and(result['seed'],result.get('arm'))==PAIRS[stage],'fit_report')
 else:need(result.get('schema')=='marked-sixfit-independent-aggregate-v1'and result['checked']==396 and type(result.get('fits'))is list and len(result['fits'])==6 and type(result.get('stronger'))is list and len(result['stronger'])==8,'aggregate_report')
 advance=result.get('advance');need(type(advance)is dict and type(advance.get('pass_all'))is bool and type(advance.get('checks'))is list,'advance')
 if stage==6:need(len(advance['checks'])==24 and type(advance.get('additional'))is list and len(advance['additional'])==12,'fixed_guards')
 return advance

def run_stage(stage,inputs,gate,bindings,*,claim,retain,processing_begin):
 report_pin=None;claim_digest=None;count=0;used=0;durable_count=0;durable_bytes=0;failed_retention=False;ordinal={'record':0,'raw_report':0,'wrapper_failure':0};audit_result=None
 def save(kind,value):
  nonlocal count,used,failed_retention,durable_count,durable_bytes
  need(not failed_retention,'retention_already_failed');encoded=raw(value,bindings);need(count<70 and used+len(encoded)<=TOTAL,'stage_payload_cap');digest=sha(encoded);index=ordinal[kind];ordinal[kind]+=1;count+=1;used+=len(encoded)
  try:ack=retain(kind,index,encoded,digest);receipt(ack,digest)
  except Exception:failed_retention=True;raise ControlError('retention_failed')
  durable_count+=1;durable_bytes+=len(encoded);return dict(bytes=len(encoded),sha256=digest)
 try:
  need(callable(claim)and callable(retain),'callbacks');preflight(stage,inputs,gate,bindings,processing_begin);claim_value=dict(schema='marked-sixfit-audit-wrapper-claim-v1',study=STUDY,stage=stage,seed=PAIRS[stage][0]if stage<6 else None,arm=PAIRS[stage][1]if stage<6 else None,inputs_sha256=gate['inputs_sha256'],binding_sha256=bindings.binding_sha256,whole_begin=gate['whole_begin']);encoded=raw(claim_value,bindings);claim_digest=sha(encoded);receipt(claim(encoded,claim_digest),claim_digest);tick(gate,processing_begin)
  if stage<6:audit_result=bindings.audit_fit(**inputs,processing_begin=processing_begin,retain=lambda value:save('record',value))
  else:audit_result=bindings.aggregate(**inputs,processing_begin=processing_begin,retain=lambda value:save('record',value))
  # Always preserve the unchanged returned report before interpretation or clocks.
  report_pin=save('raw_report',audit_result);advance=result_checked(stage,audit_result);tick(gate,processing_begin)
  return dict(schema='marked-sixfit-audit-wrapper-return-v1',status='complete',stage=stage,seed=PAIRS[stage][0]if stage<6 else None,arm=PAIRS[stage][1]if stage<6 else None,input_sha256=gate['inputs_sha256'],binding_sha256=bindings.binding_sha256,claim_sha256=claim_digest,report_pin=report_pin,retained_count=durable_count,retained_bytes=durable_bytes,attempted_count=count,attempted_bytes=used,advance=advance)
 except Exception as error:
  failure=dict(schema='marked-sixfit-audit-wrapper-return-v1',status='fail',stage=stage if type(stage)is int else None,reason=str(error)[:128],exception_type=type(error).__name__,claim_sha256=claim_digest,report_pin=report_pin,retained_count=durable_count,retained_bytes=durable_bytes,attempted_count=count,attempted_bytes=used,failed_retention=failed_retention,advance=dict(pass_all=False,checks=[],additional=[]))
  if audit_result is not None and type(bindings)is Bindings:
   try:
    available=raw(audit_result,bindings)
    if len(available)<=MEMBER-4096:failure['available_report']=audit_result;failure['available_report_pin']=dict(bytes=len(available),sha256=sha(available))
   except Exception:failure['available_report_unserializable']=True
  if not failed_retention and callable(retain)and type(bindings)is Bindings:
   try:save('wrapper_failure',failure)
   except Exception as retention_error:failure['failed_retention']=True;failure['retention_exception_type']=type(retention_error).__name__
  failure.update(retained_count=durable_count,retained_bytes=durable_bytes,attempted_count=count,attempted_bytes=used)
  return failure

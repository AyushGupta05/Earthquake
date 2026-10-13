"""Exactly seven once-only audit stages; all authority and OS actions injected."""
import math
import re
import time
import secure_io as io

STUDY='earthquake-TRAIN115-marked-noise-fitting-v2'
ORDER=tuple((s,a) for s in (20261012,20261013) for a in ('S','P','D'))
LIMITS=dict(memory=2147483648,swap=0,tasks=64,cpu_weight=10,threads=1,cuda_hidden=True,kill_mode='control-group',stop_seconds=5)

def finite(x):return type(x)in(int,float) and math.isfinite(x)
def spec(config,index):
    io.need(type(index)is int and 0<=index<7,'stage_index')
    seed,arm=ORDER[index] if index<6 else (None,None)
    return dict(index=index,kind='audit_fit' if index<6 else 'audit_aggregate',seed=seed,arm=arm,source_seconds=900,manager_seconds=960,unit='eew-marked-'+config['audit_id']+'-%02d.service'%index,limits=dict(LIMITS))
def config_check(c,now):
    keys={'schema','audit_id','study','feature_schema','feature_study','whole_begin','lease_deadline','binding_sha256','wrapper_binding_sha256','sources','runtime','bundle_template','publication','protocol','hooks_source','hooks_config','commands','store_directory','storage_limit_bytes'}
    io.need(type(c)is dict and set(c)==keys and c['schema']=='marked-seven-audit-deployment-v1' and c['study']==STUDY,'config_schema')
    io.need(c['feature_schema']=='earthquake-TRAIN115-marked-noise-observations-v1' and c['feature_study']=='earthquake-TRAIN115-marked-noise-study-v1','feature_identity')
    io.need(type(c['audit_id'])is str and re.fullmatch('[a-z0-9-]{1,48}',c['audit_id']),'audit_id')
    io.need(finite(now) and finite(c['whole_begin']) and finite(c['lease_deadline']) and 0<=c['whole_begin']<=now and c['whole_begin']<c['lease_deadline']<=c['whole_begin']+7400,'clock_domain')
    io.need(type(c['binding_sha256'])is str and re.fullmatch('[0-9a-f]{64}',c['binding_sha256']),'binding_hash')
    io.need(type(c['wrapper_binding_sha256'])is str and re.fullmatch('[0-9a-f]{64}',c['wrapper_binding_sha256']),'wrapper_binding_hash')
    io.need(type(c['storage_limit_bytes'])is int and c['storage_limit_bytes']==7*64*1024*1024,'fixed_envelope')
def parse(raw):
    value=io.json_read(raw);io.need(io.canonical(value)==raw,'canonical_control');return value
def config_pin(c):return io.pin(io.canonical(c))
def namepin(j,index,name):return io.pin(j.read(index,name))
def prior(c,index,j):
    out=[]
    for i in range(index):
        io.need(not j.exists(i,'late_or_failed.json') and not j.exists(i,'child_failure.json'),'prior_failed')
        closed=parse(j.read(i,'closed.json'))
        io.need(closed['status']=='complete' and closed['stage']==i and closed['config_pin']==config_pin(c) and closed['cleanup_verified']is True and closed['errors']==[] and closed['no_retry']is True,'prior_closure')
        report=parse(j.read(i,'child_report.json',closed['child_report_pin']))
        io.need(report['status']=='complete' and report['stage']==i and report['config_pin']==config_pin(c),'prior_child')
        j.read(i,'return.json',report['return_pin']);j.read(i,'raw_report_000.json',report['report_pin']);j.read(i,'claim.json',report['claim_pin'])
        out.append(dict(stage=i,closed_pin=namepin(j,i,'closed.json'),return_pin=report['return_pin'],report_pin=report['report_pin'],claim_pin=report['claim_pin']))
    return out
def clipped(raw,cap,custody):
    if type(raw)is not bytes:return dict(retained_hex='',retained_pin=None,truncated=True)
    return dict(retained_hex=raw[:cap].hex(),retained_pin=io.pin(raw[:cap]),truncated=len(raw)>cap or type(custody)is not dict or custody.get('truncated')is not False)
def streams_checked(answer):
    """Original observed-stream hashes remain distinct from stored-prefix hashes."""
    custody=answer.get('stream_custody')
    io.need(type(custody)is dict and set(custody)=={'stdout','stderr'},'stream_custody')
    for key,cap in (('stdout',65536),('stderr',131072)):
        c=custody[key];raw=answer.get(key)
        io.need(type(c)is dict and set(c)=={'original_bytes','original_sha256','retained_bytes','truncated','complete_observation'} and type(raw)is bytes,'stream_metadata')
        io.need(type(c['original_bytes'])is int and type(c['retained_bytes'])is int and 0<=c['retained_bytes']==len(raw)<=cap and c['original_bytes']>=len(raw),'stream_counts')
        io.need(type(c['original_sha256'])is str and re.fullmatch('[0-9a-f]{64}',c['original_sha256']) and type(c['truncated'])is bool and type(c['complete_observation'])is bool and c['truncated']==(c['original_bytes']>len(raw)),'stream_flags')
        if not c['truncated']:io.need(c['original_sha256']==io.pin(raw)['sha256'],'full_stream_hash')
        io.need(c['complete_observation']is True and c['truncated']is False,'stream_incomplete')
def clean_post(value,unit):
    io.need(type(value)is dict and set(value)=={'unit','result','active_state','control_group'} and value['unit']==unit and value['active_state']in('inactive','failed') and value['control_group']=='','cleanup_unverified')

def run_stage(c,index,bundle_spec,j,dep,*,clock=time.monotonic):
    """ROOT persists this final return too; a provisional closed file is insufficient."""
    config_check(c,clock());s=spec(c,index);previous=prior(c,index,j)
    science_end=min(c['whole_begin']+7200,c['lease_deadline']);closure_end=min(c['whole_begin']+7400,c['lease_deadline'])
    io.need(clock()+960<=science_end,'whole_science_budget')
    receipt=dep.authorize(s,'parent',bundle_spec)
    closure_end=min(closure_end,receipt['expires'])
    dispatch=clock();io.need(dispatch+960<=science_end and receipt['expires']>=dispatch+960,'late_authority')
    request=dict(schema='marked-seven-audit-request-v1',config_pin=config_pin(c),stage=s,dispatch_begin=dispatch,previous=previous,bundle_spec=bundle_spec)
    j.object(index,'dispatch.json',request) # exclusive before any dispatch
    errors=[];cleanup=False;child_pin=None;report_pin=None;return_pin=None;answer=None
    try:
        io.need(clock()+960<=science_end and receipt['expires']>=clock()+960,'late_claim')
        timeout=min(dispatch+980,closure_end)-clock();io.need(timeout>0,'transport_budget')
        answer=dep.run(request,timeout)
    except Exception as exc:answer=dict(code=None,timeout=True,streams_complete=False,stdout=b'',stderr=b'',exception=type(exc).__name__)
    finished=clock()
    if type(answer)is not dict:answer={}
    evidence={k:answer.get(k) for k in ('code','timeout','streams_complete','exception')}
    custody=answer.get('stream_custody')
    evidence['stream_custody']=custody
    evidence.update(stdout=clipped(answer.get('stdout'),65536,custody.get('stdout') if type(custody)is dict else None),stderr=clipped(answer.get('stderr'),131072,custody.get('stderr') if type(custody)is dict else None))
    try:j.object(index,'manager_return.json',evidence)
    except Exception as exc:errors.append('manager_persist:'+type(exc).__name__)
    try:streams_checked(answer)
    except Exception as exc:errors.append('stream_custody:'+type(exc).__name__)
    uncertain=answer.get('timeout')is not False or type(answer.get('code'))is not int or answer.get('code')!=0
    stopped=False
    def stop_once():
        nonlocal stopped
        if stopped:return
        stopped=True
        try:j.object(index,'stop.json',dep.stop(s['unit'],min(10,max(0,closure_end-clock()))))
        except Exception as exc:errors.append('stop:'+type(exc).__name__)
    if uncertain:stop_once()
    try:
        remaining=min(5,max(0,closure_end-clock()));io.need(remaining>0,'closure_expired')
        post=dep.inspect(s['unit'],remaining);j.object(index,'post.json',post);clean_post(post,s['unit']);cleanup=True
        io.need(post['result']=='success','unit_result')
    except Exception as exc:
        errors.append('cleanup:'+type(exc).__name__);stop_once()
        try:
            remaining=min(5,max(0,closure_end-clock()));io.need(remaining>0,'closure_expired')
            post=dep.inspect(s['unit'],remaining);j.object(index,'post_after_stop.json',post);clean_post(post,s['unit']);cleanup=True
        except Exception as exc:errors.append('cleanup_reconcile:'+type(exc).__name__)
    try:
        io.need(not j.exists(index,'child_failure.json'),'child_failure')
        raw=j.read(index,'child_report.json');child_pin=io.pin(raw);child=parse(raw)
        io.need(child['status']=='complete' and child['stage']==index and child['config_pin']==config_pin(c) and child['request_pin']==io.pin(io.canonical(request)) and child['within_source']is True,'child_report')
        returned=parse(j.read(index,'return.json',child['return_pin']))
        io.need(returned['status']=='complete' and returned['stage']==index and returned['binding_sha256']==c['wrapper_binding_sha256'],'wrapper_return')
        j.read(index,'raw_report_000.json',child['report_pin']);j.read(index,'claim.json',child['claim_pin'])
        return_pin=child['return_pin'];report_pin=child['report_pin']
    except Exception as exc:errors.append('child:'+type(exc).__name__)
    if uncertain or answer.get('streams_complete')is not True or any(evidence[k]['truncated'] for k in ('stdout','stderr')):errors.append('transport_incomplete')
    if finished>min(dispatch+980,closure_end):errors.append('late_transport')
    if clock()>closure_end:errors.append('late_return')
    result=dict(schema='marked-seven-audit-manager-return-v1',status='complete' if not errors else 'incomplete',stage=index,unit=s['unit'],config_pin=config_pin(c),cleanup_verified=cleanup,child_report_pin=child_pin,return_pin=return_pin,report_pin=report_pin,errors=errors,no_retry=True)
    try:j.object(index,'closed.json',result)
    except Exception as exc:result['status']='incomplete';errors.append('closed_persist:'+type(exc).__name__)
    if clock()>closure_end:result['status']='incomplete';errors.append('late_finalization')
    if result['status']!='complete':
        try:j.object(index,'late_or_failed.json',result)
        except Exception:errors.append('failure_marker_unverified')
    return result

def command(s,python,code):
    args=['systemd-run','--user','--unit='+s['unit'][:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']
    args+=['--setenv='+k+'=1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]
    args+=sum((['-p',p] for p in ('MemoryMax=2147483648','MemorySwapMax=0','TasksMax=64','CPUWeight=10','RuntimeMaxSec=960','TimeoutStopSec=5','KillMode=control-group')),[])
    return args+[python,'-I','-B','-c',code]

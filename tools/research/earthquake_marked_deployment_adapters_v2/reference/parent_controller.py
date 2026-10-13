"""Stdlib-only fixed-stage control. All authority/OS/storage operations injected."""
import hashlib
import json
import math
import re
import time

STUDY = 'earthquake-TRAIN115-marked-noise-fitting-v2'
FEATURE = 'earthquake-TRAIN115-marked-noise-observations-v1'
FEATURE_STUDY = 'earthquake-TRAIN115-marked-noise-study-v1'
ORDER = tuple((s,a) for s in (20261012,20261013) for a in ('S','P','D'))
STAGES = [('admission',None,None)] + [(kind,s,a) for s,a in ORDER for kind in ('fit','score')] + [('aggregate',None,None)]
CAP = 2*1024*1024
INPUTS = {'feature_archive','feature_manifest','feature_authority','strong_results','strong_authority'}
LIMITS = dict(memory=2147483648,swap=0,tasks=64,cpu_weight=10,threads=1,cuda_hidden=True,kill_mode='control-group',stop_seconds=5)


def need(condition, reason):
    if not condition: raise ValueError(reason)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def pin(raw):
    need(type(raw) is bytes,'bytes'); return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def valid_pin(value, cap=16*1024*1024):
    need(type(value) is dict and set(value)=={'bytes','sha256'} and type(value['bytes']) is int and 0<value['bytes']<=cap
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']),'pin')


def number(x): return type(x) in (int,float) and math.isfinite(x)


def parse(raw, cap=CAP):
    need(type(raw) is bytes and len(raw)<=cap,'json_cap')
    def pairs(items):
        out={}
        for k,v in items: need(k not in out,'duplicate'); out[k]=v
        return out
    def bad(_): raise ValueError('nonfinite')
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)
    need(canonical(value)==raw,'canonical'); return value


def gate_check(g, now):
    keys={'schema','study','feature_schema','feature_study','experiment_id','experiment_begin','source_pins','runtime_pin','input_pins','funding_pin','storage_limit_bytes'}
    need(type(g) is dict and set(g)==keys and g['schema']=='marked-sixfit-parent-gate-v1' and g['study']==STUDY
         and g['feature_schema']==FEATURE and g['feature_study']==FEATURE_STUDY,'gate_identity')
    need(type(g['experiment_id']) is str and re.fullmatch('[a-z0-9-]{1,48}',g['experiment_id']),'experiment_id')
    need(number(now) and number(g['experiment_begin']) and 0<=g['experiment_begin']<=now,'clock_domain')
    need(type(g['source_pins']) is dict and set(g['source_pins'])=={'processor','operator','native','reference','parent','protocol'},'source_groups')
    for p in g['source_pins'].values(): valid_pin(p)
    valid_pin(g['runtime_pin']); valid_pin(g['funding_pin'])
    need(type(g['input_pins']) is dict and set(g['input_pins'])==INPUTS,'input_groups')
    for p in g['input_pins'].values(): valid_pin(p)
    need(type(g['storage_limit_bytes']) is int and 0<g['storage_limit_bytes']<=2**34,'storage_gate')


def identity(g): return pin(canonical(g))['sha256']


def stage_spec(g, index):
    need(type(index) is int and 0<=index<len(STAGES),'index')
    kind,seed,arm=STAGES[index]
    source=900 if kind=='score' else 300
    return dict(index=index,kind=kind,seed=seed,arm=arm,source_seconds=source,manager_seconds=source+60,
                unit='eew-marked-'+g['experiment_id']+'-%02d.service'%index,limits=dict(LIMITS))


def artifact_name(index, name): return 'stage_%02d/%s'%(index,name)


class Journal:
    """Store must atomically enforce cap/no-overwrite and fsync; readback is additional."""
    def __init__(self, store, cap): self.store=store; self.cap=cap
    def put(self,name,raw,*,replace=False):
        need(type(name) is str and re.fullmatch(r'[a-z0-9_/-]+\.json',name) and '..' not in name,'name')
        need(type(raw) is bytes and len(raw)<=CAP,'artifact_cap')
        result=self.store.write(name,raw,replace=replace,total_cap=self.cap)
        need(result==dict(status='durable',pin=pin(raw)),'durable_receipt')
        need(self.store.read(name)==raw,'durable_readback')
        return pin(raw)
    def object(self,name,value,**kw): return self.put(name,canonical(value),**kw)
    def read(self,name,expected=None):
        raw=self.store.read(name); need(type(raw) is bytes and len(raw)<=CAP,'stored_cap')
        if expected is not None: need(pin(raw)==expected,'stored_binding')
        return raw


def receipt_ok(proof,g,spec,now):
    need(type(proof) is dict and set(proof)=={'authorized','gate_sha256','index','unit','funding_pin','expires','verified'}
         and proof['authorized'] is True and proof['gate_sha256']==identity(g) and type(proof['index']) is int
         and proof['index']==spec['index'] and proof['unit']==spec['unit'] and proof['funding_pin']==g['funding_pin'],'authority')
    need(proof['verified']==dict(source_runtime=True,native_agreement=True,strong_closure=True,owned_unit_available=True),'positive_bindings')
    need(number(proof['expires']) and now+spec['manager_seconds']<=proof['expires'],'authority_expired')


def prior_outputs(g,index,journal):
    outputs={}
    for i in range(index):
        need(not journal.store.exists(artifact_name(i,'late_or_failed.json')) and not journal.store.exists(artifact_name(i,'child_late_or_failed.json')),'prior_late')
        closed=parse(journal.read(artifact_name(i,'closed.json')))
        need(closed['status']=='complete' and closed['gate_sha256']==identity(g) and closed['index']==i
             and closed['unit']==stage_spec(g,i)['unit'] and closed['cleanup_verified'] is True
             and closed['no_retry'] is True,'prior_incomplete')
        report=parse(journal.read(artifact_name(i,'child_report.json'),closed['report_pin']))
        need(report['status']=='complete' and report['index']==i and report['gate_sha256']==identity(g),'prior_report')
        name=artifact_name(i,'result.json'); journal.read(name,report['result_pin']); outputs[str(i)]=dict(name=name,pin=report['result_pin'])
    return outputs


def clipped(raw,cap):
    if type(raw) is not bytes: return dict(retained_hex='',original_pin=None,truncated=True)
    return dict(retained_hex=raw[:cap].hex(),original_pin=pin(raw),truncated=len(raw)>cap)


def run_stage(g,index,store,adapter,*,clock=time.monotonic):
    """Exactly one exclusive stage. No loop retry; ROOT owns the transport adapter."""
    now=clock(); gate_check(g,now); spec=stage_spec(g,index); journal=Journal(store,g['storage_limit_bytes'])
    outputs=prior_outputs(g,index,journal)
    need(now+spec['manager_seconds']<=g['experiment_begin']+7200,'insufficient_science_budget')
    proof=adapter.authorize(g,spec,now); receipt_ok(proof,g,spec,clock())
    request=dict(schema='marked-sixfit-stage-request-v1',gate=g,gate_sha256=identity(g),stage=spec,
                 authority=proof,previous=outputs,dispatch_begin=clock())
    need(request['dispatch_begin']+spec['manager_seconds']<=g['experiment_begin']+7200,'late_authorization')
    # Exclusive write is the cross-process once-only guard, preceding any dispatch.
    journal.object(artifact_name(index,'claim.json'),request)
    answer=None; report=None; cleanup=None; errors=[]; result_pin=None
    try:
        launch_now=clock()
        need(launch_now+spec['manager_seconds']<=g['experiment_begin']+7200,'late_claim')
        receipt_ok(proof,g,spec,launch_now)
        timeout=min(request['dispatch_begin']+spec['manager_seconds']+20,g['experiment_begin']+7400)-clock()
        need(timeout>0,'closure_budget')
        answer=adapter.run(request,timeout)
    except Exception as exc:
        answer=dict(code=None,timeout=True,stdout=b'',stderr=b'',streams_complete=False,exception=type(exc).__name__)
    transport_finished=clock()
    if type(answer) is not dict:
        answer=dict(code=None,timeout=True,stdout=b'',stderr=b'',streams_complete=False,exception='InvalidTransportResult')
    # Preserve full bounded transport evidence before interpreting deadline/exit/cleanup.
    transport=dict(code=answer.get('code'),timeout=answer.get('timeout'),streams_complete=answer.get('streams_complete'),
                   stdout=clipped(answer.get('stdout'),65536),stderr=clipped(answer.get('stderr'),131072),exception=answer.get('exception'))
    try: journal.object(artifact_name(index,'manager_return.json'),transport)
    except Exception as exc: errors.append('manager_persist:'+type(exc).__name__)
    uncertain=answer.get('timeout') is not False or type(answer.get('code')) is not int or answer['code']!=0
    stop_attempted=False
    if uncertain:
        stop_attempted=True
        try:
            stopped=adapter.stop(spec['unit'],min(10,max(0,g['experiment_begin']+7400-clock())))
            journal.object(artifact_name(index,'stop.json'),stopped)
        except Exception as exc: errors.append('stop:'+type(exc).__name__)
    try:
        observed=adapter.inspect(spec['unit'],min(5,max(0,g['experiment_begin']+7400-clock())))
        journal.object(artifact_name(index,'post.json'),observed)
        need(type(observed) is dict and set(observed)=={'unit','result','active_state','control_group'} and observed['unit']==spec['unit']
             and observed['active_state'] in ('inactive','failed') and observed['control_group']=='','cleanup_unverified')
        cleanup=True
        if observed['result']!='success': errors.append('unit_result')
    except Exception as exc:
        errors.append('cleanup:'+type(exc).__name__)
        # A successful transport exit is not proof of an empty owned cgroup.
        # Stop once on newly observed uncertainty, then attempt one bounded
        # reconciliation. The original uncertainty still makes this incomplete.
        if not stop_attempted:
            stop_attempted=True
            try:
                remaining=max(0,g['experiment_begin']+7400-clock())
                # Even an expired closure requests a nonblocking owned-unit stop;
                # zero timeout must not acquire another blocking wait budget.
                stopped=adapter.stop(spec['unit'],min(10,remaining))
                journal.object(artifact_name(index,'stop_after_inspection.json'),stopped)
            except Exception as stop_exc: errors.append('cleanup_stop:'+type(stop_exc).__name__)
        try:
            remaining=max(0,g['experiment_begin']+7400-clock())
            need(remaining>0,'closure_expired')
            observed=adapter.inspect(spec['unit'],min(5,remaining))
            journal.object(artifact_name(index,'post_after_stop.json'),observed)
            need(type(observed) is dict and set(observed)=={'unit','result','active_state','control_group'} and observed['unit']==spec['unit']
                 and observed['active_state'] in ('inactive','failed') and observed['control_group']=='','cleanup_unverified')
            cleanup=True
        except Exception as final_exc: errors.append('cleanup_reconciliation:'+type(final_exc).__name__)
    try:
        need(not store.exists(artifact_name(index,'child_late_or_failed.json')),'child_late')
        report_raw=journal.read(artifact_name(index,'child_report.json')); report_pin=pin(report_raw); report=parse(report_raw)
        need(report['schema']=='marked-sixfit-child-report-v1' and report['gate_sha256']==identity(g) and report['index']==index
             and report['request_pin']==pin(canonical(request)) and report['status']=='complete'
             and report['within_source'] is True and report['within_experiment'] is True,'child_report')
        result_pin=report['result_pin']; journal.read(artifact_name(index,'result.json'),result_pin)
    except Exception as exc: errors.append('report:'+type(exc).__name__); report_pin=None
    if uncertain or answer.get('streams_complete') is not True or any(transport[k]['truncated'] for k in ('stdout','stderr')): errors.append('transport_incomplete')
    now=clock()
    if transport_finished>min(g['experiment_begin']+7400,request['dispatch_begin']+spec['manager_seconds']+20): errors.append('late_transport')
    if now>g['experiment_begin']+7400: errors.append('late_return')
    result=dict(schema='marked-sixfit-parent-return-v1',status='complete' if not errors else 'incomplete',index=index,
                unit=spec['unit'],gate_sha256=identity(g),cleanup_verified=cleanup is True,report_pin=report_pin,
                result_pin=result_pin,errors=errors,no_retry=True,scientific_pass=None)
    if index==13 and not errors:
        try: result['scientific_pass']=parse(journal.read(artifact_name(index,'result.json')))['pass_all']
        except Exception: result['status']='incomplete'; errors.append('aggregate_pass_missing')
    try: journal.object(artifact_name(index,'closed.json'),result)
    except Exception as exc: result['status']='incomplete'; errors.append('close_persist:'+type(exc).__name__)
    # A failed/late final write must never authorize the next stage, even if the
    # provisional closed file was already durable. ROOT must reconcile this marker.
    if clock()>g['experiment_begin']+7400: result['status']='incomplete'; errors.append('late_finalization')
    if result['status']!='complete':
        try: journal.object(artifact_name(index,'late_or_failed.json'),result)
        except Exception: errors.append('failure_marker_unverified')
    return result


def systemd_command(request,python,child_code):
    """Command construction only. ROOT binds paths/code; this function launches nothing."""
    need(type(python) is str and python.startswith('/') and type(child_code) is str,'launch_binding')
    spec=request['stage']
    need(spec==stage_spec(request['gate'],spec['index']),'stage_limits')
    args=['systemd-run','--user','--unit='+spec['unit'][:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']
    args+=['--setenv='+k+'=1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]
    for x in ('MemoryMax=2147483648','MemorySwapMax=0','TasksMax=64','CPUWeight=10','RuntimeMaxSec='+str(spec['manager_seconds']),'TimeoutStopSec=5','KillMode=control-group'): args+=['-p',x]
    return args+[python,'-I','-B','-c',child_code]

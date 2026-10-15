"""Narrow nine-stage L control, inherited stream/cleanup/finalization semantics."""
import math
import re
import time
import secure_io as io

STUDY='earthquake-TRAIN115-shared-reference-AR-L-study-v1'
STAGES=(('admission',None,None),('fit',20261012,'L'),('score',20261012,'L'),('fit',20261013,'L'),('score',20261013,'L'),('aggregate',None,None),('audit_fit',20261012,'L'),('audit_fit',20261013,'L'),('audit_aggregate',None,None))
LIMITS=dict(memory=2147483648,swap=0,tasks=64,cpu_weight=10,threads=1,cuda_hidden=True,kill_mode='control-group',stop_seconds=5)
SOURCES={'processor','operator','native_validator','reference','kernel','numeric_state','auditor','executor','adapters','protocol'}
INPUTS={'feature_archive','feature_manifest','feature_authority','original_admission','original_admission_authority','closed_comparator_report','comparator_origins','comparator_authority'}

def finite(x):return type(x)in(int,float) and math.isfinite(x)
def spec(config,index):
    io.need(type(index)is int and 0<=index<9,'stage_index')
    kind,seed,arm=STAGES[index]
    source=900 if kind in ('score','audit_fit','audit_aggregate') else 300
    return dict(index=index,kind=kind,seed=seed,arm=arm,source_seconds=source,manager_seconds=source+60,unit='eew-marked-'+config['experiment_id']+'-%02d.service'%index,limits=dict(LIMITS))

def config_check(c,now,expected_config_pin):
    keys={'schema','study','feature_schema','feature_study','experiment_id','whole_begin','lease_deadline','source_pins','runtime_pin','input_pins','funding_pin','publication_pin','protocol_pin','storage_limit_bytes'}
    io.need(type(c)is dict and set(c)==keys and c['schema']=='shared-reference-AR-L-nine-stage-config-v1' and c['study']==STUDY,'config_schema')
    io.need(c['feature_schema']=='earthquake-TRAIN115-marked-noise-observations-v1' and c['feature_study']=='earthquake-TRAIN115-marked-noise-study-v1','feature_identity')
    io.need(type(c['experiment_id'])is str and re.fullmatch('[a-z0-9-]{1,48}',c['experiment_id']),'experiment_id')
    io.need(finite(now) and finite(c['whole_begin']) and finite(c['lease_deadline']) and 0<=c['whole_begin']<=now and c['whole_begin']<c['lease_deadline']<=c['whole_begin']+7400,'clock_domain')
    io.need(type(c['source_pins'])is dict and set(c['source_pins'])==SOURCES and type(c['input_pins'])is dict and set(c['input_pins'])==INPUTS,'bindings')
    for p in list(c['source_pins'].values())+list(c['input_pins'].values())+[c[k] for k in ('runtime_pin','funding_pin','publication_pin','protocol_pin')]:
        io.pin_check(p);io.need(p['bytes']>0,'positive_pin')
    io.pin_check(expected_config_pin);io.need(io.pin(io.canonical(c))==expected_config_pin,'held_config_pin')
    io.need(type(c['storage_limit_bytes'])is int and c['storage_limit_bytes']==9*64*1024*1024,'fixed_envelope')

def scope(c,s,phase):
    io.need(phase in ('parent','child'),'phase')
    return dict(schema='shared-reference-AR-L-stage-scope-v1',config_pin=config_pin(c),study=STUDY,experiment_id=c['experiment_id'],stage=s,unit=s['unit'],phase=phase,
                source_pins=c['source_pins'],runtime_pin=c['runtime_pin'],input_pins=c['input_pins'],funding_pin=c['funding_pin'],publication_pin=c['publication_pin'],protocol_pin=c['protocol_pin'],whole_begin=c['whole_begin'],lease_deadline=c['lease_deadline'])

def authorize(c,s,phase,adapter,now):
    requested=scope(c,s,phase);documents=adapter.documents(requested)
    io.need(type(documents)is dict and set(documents)=={'funding','publication','protocol','root_context'},'authority_documents')
    for key in ('funding','publication','protocol'):io.need(type(documents[key])is bytes and io.pin(documents[key])==c[key+'_pin'],'authority_document_pin')
    io.need(type(documents['root_context'])is bytes and 0<len(documents['root_context'])<=1048576,'root_context')
    receipt=adapter.authorize(requested,documents,now)
    return receipt_checked(c,s,phase,receipt,now)

def receipt_checked(c,s,phase,receipt,now):
    io.need(type(receipt)is dict and set(receipt)=={'schema','scope','decision','expires','proofs'} and receipt['schema']=='root-shared-reference-AR-L-stage-authority-v1' and receipt['scope']==scope(c,s,phase) and receipt['decision']=='authorized','authority_receipt')
    io.need(finite(receipt['expires']) and now<receipt['expires']<=c['lease_deadline'],'authority_lease')
    io.need(type(receipt['proofs'])is dict and set(receipt['proofs'])=={'source','runtime','native','original_initialization','reused924','resources','storage'},'authority_proofs')
    for proof in receipt['proofs'].values():
        io.pin_check(proof);io.need(proof['bytes']>0,'positive_proof')
    io.need(receipt['proofs']['source']==io.pin(io.canonical(c['source_pins'])) and receipt['proofs']['runtime']==c['runtime_pin'] and receipt['proofs']['native']==c['input_pins']['feature_authority']
            and receipt['proofs']['original_initialization']==c['input_pins']['original_admission_authority'] and receipt['proofs']['reused924']==c['input_pins']['comparator_authority'],'proof_subjects')
    if phase=='parent':io.need(now+s['manager_seconds']<=receipt['expires'],'authority_manager_cover')
    return receipt

def parse(raw):
    value=io.json_read(raw);io.need(io.canonical(value)==raw,'canonical_control');return value
def config_pin(c):return io.pin(io.canonical(c))
def namepin(j,index,name):return io.pin(j.read(index,name))
def prior(c,index,j,adapter):
    out=[]
    for i in range(index):
        io.need(not j.exists(i,'late_or_failed.json') and not j.exists(i,'child_failure.json'),'prior_failed')
        closed=parse(j.read(i,'closed.json'))
        io.need(closed['status']=='complete' and closed['stage']==i and closed['config_pin']==config_pin(c) and closed['unit']==spec(c,i)['unit'] and closed['cleanup_verified']is True and closed['errors']==[] and closed['no_retry']is True,'prior_closure')
        report=parse(j.read(i,'child_report.json',closed['child_report_pin']))
        io.need(report['status']=='complete' and report['stage']==i and report['config_pin']==config_pin(c),'prior_child')
        j.read(i,'result.json',report['result_pin']);j.read(i,'claim.json',report['claim_pin']);j.read(i,'dispatch.json')
        # Actual last-return/full-inventory/OS truth is held outside the child journal.
        held=adapter.prior_closed(c,i,closed,j.inventory())
        io.need(type(held)is dict and set(held)=={'schema','stage','config_pin','closed_pin','result_pin','known_return_pin'} and held['schema']=='root-shared-reference-AR-L-prior-closure-v1' and held['stage']==i and held['config_pin']==config_pin(c) and held['closed_pin']==namepin(j,i,'closed.json') and held['result_pin']==report['result_pin'],'held_prior_return')
        io.pin_check(held['known_return_pin'])
        out.append(dict(stage=i,closed_pin=held['closed_pin'],result_pin=report['result_pin'],claim_pin=report['claim_pin'],known_return_pin=held['known_return_pin']))
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

def run_stage(c,expected_config_pin,index,j,dep,*,clock=time.monotonic):
    """ROOT persists this final return too; a provisional closed file is insufficient."""
    config_check(c,clock(),expected_config_pin);s=spec(c,index);previous=prior(c,index,j,dep)
    science_end=min(c['whole_begin']+7200,c['lease_deadline']);closure_end=min(c['whole_begin']+7400,c['lease_deadline'])
    io.need(clock()+s['manager_seconds']<=science_end,'whole_science_budget')
    receipt=authorize(c,s,'parent',dep,clock())
    closure_end=min(closure_end,receipt['expires'])
    config_check(c,clock(),expected_config_pin)
    dispatch=clock();io.need(dispatch+s['manager_seconds']<=science_end and receipt['expires']>=dispatch+s['manager_seconds'],'late_authority')
    request=dict(schema='shared-reference-AR-L-stage-request-v1',config=c,config_pin=expected_config_pin,stage=s,dispatch_begin=dispatch,previous=previous,parent_authority=receipt)
    j.object(index,'dispatch.json',request) # exclusive before any dispatch
    errors=[];cleanup=False;child_pin=None;report_pin=None;result_pin=None;answer=None
    try:
        io.need(clock()+s['manager_seconds']<=science_end and receipt['expires']>=clock()+s['manager_seconds'],'late_claim')
        timeout=min(dispatch+s['manager_seconds']+20,closure_end)-clock();io.need(timeout>0,'transport_budget')
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
    try:
        child_report=parse(j.read(index,'child_report.json'))
        claim=parse(j.read(index,'claim.json',child_report['claim_pin']))
        io.need(type(claim)is dict and set(claim)=={'schema','stage','request_pin','config_pin','authority'} and claim['schema']=='shared-reference-AR-L-child-claim-v1' and type(claim['stage'])is int and claim['stage']==index and claim['request_pin']==io.pin(io.canonical(request)) and claim['config_pin']==expected_config_pin,'child_claim')
        issued=receipt_checked(c,s,'child',claim['authority'],dispatch)
        io.need(issued['expires']<=receipt['expires'],'child_lease_extension')
        closure_end=min(closure_end,issued['expires'])
    except Exception as exc:errors.append('child_claim:'+type(exc).__name__)
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
        j.read(index,'result.json',child['result_pin']);j.read(index,'claim.json',child['claim_pin'])
        result_pin=child['result_pin'];report_pin=child['claim_pin']
    except Exception as exc:errors.append('child:'+type(exc).__name__)
    if uncertain or answer.get('streams_complete')is not True or any(evidence[k]['truncated'] for k in ('stdout','stderr')):errors.append('transport_incomplete')
    if finished>min(dispatch+s['manager_seconds']+20,closure_end):errors.append('late_transport')
    if clock()>closure_end:errors.append('late_return')
    result=dict(schema='shared-reference-AR-L-parent-return-v1',status='complete' if not errors else 'incomplete',stage=index,unit=s['unit'],config_pin=config_pin(c),cleanup_verified=cleanup,child_report_pin=child_pin,result_pin=result_pin,claim_pin=report_pin,errors=errors,no_retry=True)
    try:j.object(index,'closed.json',result)
    except Exception as exc:result['status']='incomplete';errors.append('closed_persist:'+type(exc).__name__)
    if clock()>closure_end:result['status']='incomplete';errors.append('late_finalization')
    if result['status']!='complete':
        try:j.object(index,'late_or_failed.json',result)
        except Exception:errors.append('failure_marker_unverified')
    return result

def command(s,python,code):
    io.need(type(python)is str and python.startswith('/') and len(python)<=4096 and type(code)is str and 0<len(code.encode())<=262144,'launch_binding')
    args=['systemd-run','--user','--unit='+s['unit'][:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']
    args+=['--setenv='+k+'=1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]
    args+=sum((['-p',p] for p in ('MemoryMax=2147483648','MemorySwapMax=0','TasksMax=64','CPUWeight=10','RuntimeMaxSec='+str(s['manager_seconds']),'TimeoutStopSec=5','KillMode=control-group')),[])
    return args+[python,'-I','-B','-c',code]

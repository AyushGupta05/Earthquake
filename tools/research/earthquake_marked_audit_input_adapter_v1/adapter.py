"""Read-only custody projection into a frozen independent auditor; no science/IO."""
import hashlib
import json
import math
import time
from dataclasses import dataclass

STUDY='earthquake-TRAIN115-marked-noise-fitting-v2'
PAIRS=tuple((s,a) for s in (20261012,20261013) for a in ('S','P','D'))
SOURCES={'operator','native_validator','reference','processor','protocol'}
BASE={'claim.json','manager_return.json','post.json','child_report.json','result.json','closed.json'}
CAP=2*1024*1024

class BindingError(ValueError):pass

def need(ok,reason):
    if not ok:raise BindingError(reason)
def keys(v,expected):need(type(v)is dict and set(v)==set(expected),'keys')
def sha(raw):return hashlib.sha256(raw).hexdigest()
def pin(raw):return dict(bytes=len(raw),sha256=sha(raw))
def digest(v):need(type(v)is str and len(v)==64 and all(c in '0123456789abcdef' for c in v),'digest')
def integer(v,n=None):need(type(v)is int and (n is None or v==n),'integer')
def pcheck(v,cap=16*1024*1024):
    keys(v,('bytes','sha256'));integer(v['bytes']);need(0<=v['bytes']<=cap,'pin_cap');digest(v['sha256'])
def plain(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def parse(raw):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate_key');out[k]=v
        return out
    v=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(BindingError('nonfinite_json')))
    need(plain(v)==raw,'canonical_json');return v

@dataclass(frozen=True)
class Bindings:
    read:object
    decode:object
    canonical:object
    load_native:object
    packet_sha:object
    project_stronger:object
    authenticate:object
    stage_spec:object
    binding_sha256:str
    def __post_init__(self):
        need(all(callable(getattr(self,k)) for k in ('read','decode','canonical','load_native','packet_sha','project_stronger','authenticate','stage_spec')),'bindings');digest(self.binding_sha256)

def expected_members(index):
    extra=set()
    if index==0:extra={'initial_%02d.json'%j for j in range(6)}
    elif index%2 and index<13:extra={'begin_fit.json','latest_update.json'}|{'update_%03d.json'%j for j in range(1,301)}
    elif index<13:extra={'forecast_%02d.json'%j for j in range(66)}
    return BASE|extra

def callback(kind,name,p):return dict(kind=kind,name=name,pin=p)
def same(a,b,d):return d.canonical(a)==d.canonical(b)
def sources(v):
    keys(v,SOURCES)
    for p in v.values():pcheck(p);need(p['bytes']>0,'source_bytes')

def prepare_inputs(stage,bundle,d,*,processing_begin):
    """External authentication is an injected reviewed ROOT trust boundary, not flags.

    ROOT verifies runtime/source closure, native semantics, old report origins,
    actual parent return truth/absence of late flags and previous audit manager
    closure against independently held pins. This function verifies all bytes and
    deterministic relationships below before constructing any authority booleans.
    """
    def tick():
        now=time.monotonic();need(type(processing_begin)in(int,float) and math.isfinite(processing_begin) and 0<=processing_begin<=now and now-processing_begin<=900,'source_deadline')
    tick();integer(stage);need(0<=stage<=6 and type(d)is Bindings,'stage')
    keys(bundle,('schema','binding_sha256','wrapper_binding_sha256','native','stronger','stages','previous_audits','root_context'))
    need(bundle['schema']=='root-marked-audit-input-bundle-v1' and bundle['binding_sha256']==d.binding_sha256,'bundle_binding')
    keys(bundle['native'],('feature_archive','feature_manifest','feature_authority'))
    keys(bundle['stronger'],('strong_results','strong_authority'))
    need(type(bundle['stages'])is list and len(bundle['stages'])==14,'fourteen_stages')
    need(type(bundle['previous_audits'])is list and len(bundle['previous_audits'])==stage,'previous_audits')
    # Hash public-shaped specs/context before loading; ROOT authenticates this scope.
    digest(bundle['wrapper_binding_sha256']);bundle_sha=sha(plain(bundle));artifact_pins={};rawstages=[];stages=[];gate=None;gate_sha=None
    def read(spec,label,cap=CAP):
        tick();keys(spec,('path','pin','mode'));need(type(spec['path'])is str and spec['path'].startswith('/') and type(spec['mode'])is int and spec['mode']==0o400,'readonly_spec');pcheck(spec['pin'],cap)
        raw=d.read(spec);need(type(raw)is bytes and len(raw)<=cap and pin(raw)==spec['pin'],'read_pin');artifact_pins[label]=pin(raw);tick();return raw
    def numeric(raw):
        v=d.decode(raw,sha(raw));need(d.canonical(v)==raw,'numeric_roundtrip');return v
    for i,files in enumerate(bundle['stages']):
        keys(files,expected_members(i));raw={name:read(spec,'stage_%02d/%s'%(i,name)) for name,spec in files.items()};rawstages.append(raw)
        r={name:parse(raw[name]) for name in BASE-{'result.json'}};request=r['claim.json'];closed=r['closed.json'];child=r['child_report.json'];manager=r['manager_return.json'];post=r['post.json']
        keys(request,('schema','gate','gate_sha256','stage','authority','previous','dispatch_begin'))
        need(request['schema']=='marked-sixfit-stage-request-v1','request_schema')
        if gate is None:gate=request['gate'];gate_sha=sha(plain(gate))
        need(request['gate']==gate and request['gate_sha256']==gate_sha and request['stage']==d.stage_spec(gate,i),'request_chain');spec=request['stage'];integer(spec['index'],i)
        need(type(request['dispatch_begin'])in(int,float) and math.isfinite(request['dispatch_begin']),'dispatch_clock')
        keys(request['previous'],[str(j)for j in range(i)])
        for j in range(i):need(request['previous'][str(j)]==dict(name='stage_%02d/result.json'%j,pin=pin(rawstages[j]['result.json'])),'previous_result_chain')
        keys(manager,('code','timeout','streams_complete','stdout','stderr','exception'));integer(manager['code'],0);need(manager['timeout']is False and manager['streams_complete']is True and manager['exception']is None,'manager_incomplete')
        for stream,limit in (('stdout',65536),('stderr',131072)):
            clip=manager[stream];keys(clip,('retained_hex','original_pin','truncated'));need(clip['truncated']is False and type(clip['retained_hex'])is str and len(clip['retained_hex'])<=2*limit,'manager_stream');pcheck(clip['original_pin'],limit);need(pin(bytes.fromhex(clip['retained_hex']))==clip['original_pin'],'manager_stream_pin')
        keys(post,('unit','result','active_state','control_group'));need(post['unit']==spec['unit'] and post['result']=='success' and post['active_state']in('inactive','failed') and post['control_group']=='','owned_cleanup')
        keys(closed,('schema','status','index','unit','gate_sha256','cleanup_verified','report_pin','result_pin','errors','no_retry','scientific_pass'));integer(closed['index'],i)
        need(closed['schema']=='marked-sixfit-parent-return-v1' and closed['status']=='complete' and closed['unit']==spec['unit'] and closed['gate_sha256']==gate_sha and closed['cleanup_verified']is True and closed['errors']==[] and closed['no_retry']is True,'closed_stage')
        need((type(closed['scientific_pass'])is bool if i==13 else closed['scientific_pass']is None),'scientific_pass_type')
        need(closed['report_pin']==pin(raw['child_report.json']) and closed['result_pin']==pin(raw['result.json']),'closed_pins')
        keys(child,('schema','index','gate_sha256','request_pin','status','result_pin','within_source','within_experiment','callbacks','failure','exception_evidence_pin'));integer(child['index'],i)
        need(child['schema']=='marked-sixfit-child-report-v1' and child['gate_sha256']==gate_sha and child['request_pin']==pin(raw['claim.json']) and child['status']=='complete' and child['result_pin']==pin(raw['result.json']) and child['within_source']is True and child['within_experiment']is True and child['failure']is None and child['exception_evidence_pin']is None,'child_complete')
        value=numeric(raw['result.json']);stages.append(value);expected=[]
        if i==0:
            for j,pair in enumerate(PAIRS):
                name='initial_%02d.json'%j;v=numeric(raw[name]);integer(v['seed'],pair[0]);integer(v['update'],0);need(v['arm']==pair[1] and v['study']==STUDY and v['status']=='initial','initial_identity');expected.append(callback('initial',name,pin(raw[name])))
            expected.append(callback('admission','result.json',pin(raw['result.json'])))
        elif i<13 and i%2:
            expected.append(callback('begin_fit','begin_fit.json',pin(raw['begin_fit.json'])))
            need(type(child['callbacks'])is list and len(child['callbacks'])==302,'fit_callback_count')
            need(type(value['history'])is list and len(value['history'])==300,'history300')
            for j in range(1,301):
                u=parse(raw['update_%03d.json'%j]);keys(u,('update','checkpoint_pin','history_last'));integer(u['update'],j);pcheck(u['checkpoint_pin'],CAP)
                need(same(u['history_last'],value['history'][j-1],d),'history_receipt');expected.append(callback('step','latest_update.json',u['checkpoint_pin']))
            expected.append(callback('final','result.json',pin(raw['result.json'])))
            need(expected[-2]['pin']==pin(raw['latest_update.json']),'latest_step_pin')
            latest=numeric(raw['latest_update.json']);begin=numeric(raw['begin_fit.json']);pair=PAIRS[(i-1)//2]
            for v,status,update in ((begin,'initial',0),(latest,'partial',300),(value,'final',300)):
                integer(v['seed'],pair[0]);integer(v['update'],update);need(v['arm']==pair[1] and v['status']==status and v['study']==STUDY,'checkpoint_identity')
            for field in ('history','parameters','optimizer','current'):need(same(latest[field],value[field],d),'latest_final_'+field)
            need(begin['history']==[] and begin['optimizer']=={},'begin_without_updates')
        elif i<13:
            need(type(value['predictions'])is list and len(value['predictions'])==66,'score66')
            for j,pred in enumerate(value['predictions']):
                name='forecast_%02d.json'%j;need(raw[name]==d.canonical(pred),'forecast_bytes');expected.append(callback('forecast',name,pin(raw[name])))
            expected.append(callback('score_final','result.json',pin(raw['result.json'])))
        need(child['callbacks']==expected,'callback_chain')
    sources(stages[0]['source_pins']);source_pins=stages[0]['source_pins'];admission=stages[0];admission_sha=sha(rawstages[0]['result.json'])
    need(gate['study']==STUDY and admission['study']==STUDY and admission['status']=='admitted' and admission['order']==[list(p)for p in PAIRS],'admission_order')
    keys(source_pins,SOURCES)
    expected_sources={k:gate['source_pins'][{'native_validator':'native','operator':'operator','reference':'reference','processor':'processor','protocol':'protocol'}[k]]for k in SOURCES}
    need(source_pins==expected_sources,'source_gate')
    for j,pair in enumerate(PAIRS):
        entry=admission['models'][str(pair[0])+':'+pair[1]];initial=numeric(rawstages[0]['initial_%02d.json'%j]);need(same(initial['parameters'],entry['initial'],d) and entry['initial_receipt']==dict(status='durable',sha256=sha(rawstages[0]['initial_%02d.json'%j])),'initial_durability')
        cp=stages[2*j+1];score=stages[2*j+2];begin=numeric(rawstages[2*j+1]['begin_fit.json']);integer(score['seed'],pair[0])
        need(score['arm']==pair[1] and score['status']=='complete' and score['study']==STUDY and score['no_optimizer']is True,'score_identity')
        for v in (cp,score,begin):need(v['source_pins']==source_pins and v['admission_sha256']==admission_sha and v['packet_sha256']==admission['packet_sha256'],'fit_source_binding')
        need(score['checkpoint_sha256']==sha(rawstages[2*j+1]['result.json']),'score_checkpoint')
        need(cp['prior_sha256']==entry['prior_sha256'] and cp['initial_sha256']==sha(d.canonical(entry['initial'])) and cp['order_sha256']==sha(d.canonical(entry['order'])),'initial_order_binding')
        need(same(begin['parameters'],entry['initial'],d),'begin_initial_parameters')
        for n,item in enumerate(cp['history']):
            keys(item,('update','loss','gradient_norm','ordinals'));integer(item['update'],n+1);need(type(item['loss'])in(int,float) and math.isfinite(item['loss']) and type(item['gradient_norm'])in(int,float) and math.isfinite(item['gradient_norm']) and item['gradient_norm']>=0,'history_numeric');order=entry['order'][n];need(item['ordinals']==(order.tolist()if hasattr(order,'tolist')else order),'history_order')
        # Frozen auditor validates the optimizer/probe tensor shapes and masks;
        # ROOT authority binds actual source execution, not a fabricated flag.
        need(type(cp['optimizer'])is dict and cp['optimizer'] and type(cp['final_probe'])is dict and type(entry['probe'])is dict,'optimizer_probe_presence')
    need(stages[13]['status']=='complete' and type(stages[13]['pass_all'])is bool and stages[13]['pass_all']==parse(rawstages[13]['closed.json'])['scientific_pass'],'producer_aggregate_complete')
    native_raw={k:read(v,'native/'+k,16*1024*1024) for k,v in bundle['native'].items()}
    strong_raw={k:read(v,'stronger/'+k,16*1024*1024) for k,v in bundle['stronger'].items()}
    for k,raw in dict(native_raw,**strong_raw).items():need(gate['input_pins'][k]==pin(raw),'gate_input_pin')
    packet=d.load_native(native_raw['feature_archive'],native_raw['feature_manifest'],processing_begin=processing_begin)
    packet_sha=d.packet_sha(packet);digest(packet_sha);need(packet_sha==admission['packet_sha256'],'native_packet_binding')
    old=parse(strong_raw['strong_results']);projected=d.project_stronger(packet,old,pin(strong_raw['strong_authority']),packet_sha)
    keys(projected,('fits','origins'));stronger=projected['fits'];need(type(stronger)is list and len(stronger)==8 and type(projected['origins'])is list and len(projected['origins'])==8,'strong_eight')
    for j,(item,pair) in enumerate(zip(stronger,((s,a)for s in(20261012,20261013)for a in('B','F','H','T')))):
        keys(item,('seed','arm','predictions','closure'));integer(item['seed'],pair[0]);need(item['arm']==pair[1] and type(item['predictions'])is list and len(item['predictions'])==66,'strong_identity');keys(item['closure'],('verified','no_optimizer','checkpoint_sha256','source_sha256','packet_sha256','independent_audit_sha256'));need(item['closure']['verified']is True and item['closure']['no_optimizer']is True and item['closure']['packet_sha256']==packet_sha,'strong_closure')
        for key in('checkpoint_sha256','source_sha256','packet_sha256','independent_audit_sha256'):digest(item['closure'][key])
        original=old['fits'][j];origin=projected['origins'][j];need(same(item['predictions'],original['predictions'],d),'strong_predictions_changed');need(origin['schema']=='old-model-new-comparison-join-v1' and origin['packet_sha256_semantics']=='comparison_population_only' and origin['old_model_reexecuted']is False and origin['original_packet_sha256']==old['original_packet_sha256'] and origin['original_packet_pins']==old['original_packet_pins'] and origin['original_result_pin']==original['result_pin'] and origin['original_checkpoint_sha256']==original['checkpoint_sha256'] and origin['original_source_sha256']==original['independent_closure']['source_sha256'] and origin['original_closure_proof_pin']==original['independent_closure']['proof_pin'] and origin['comparison_join_proof_pin']==pin(strong_raw['strong_authority']),'strong_origin_binding')
        need(item['closure']['checkpoint_sha256']==origin['original_checkpoint_sha256'] and item['closure']['source_sha256']==origin['original_source_sha256'] and item['closure']['independent_audit_sha256']==origin['original_closure_proof_pin']['sha256'],'strong_report_origin')
    stronger_sha=sha(d.canonical(stronger));previous=[];fit_audits=[]
    for j,files in enumerate(bundle['previous_audits']):
        keys(files,('claim','return','report','closed'));raw={k:read(v,'audit_%02d/%s'%(j,k),16*1024*1024)for k,v in files.items()};r=parse(raw['return']);claim=parse(raw['claim']);report=numeric(raw['report'])
        need(r['schema']=='marked-sixfit-audit-wrapper-return-v1' and r['status']=='complete' and type(r['stage'])is int and r['stage']==j and (r['seed'],r['arm'])==PAIRS[j] and r['binding_sha256']==bundle['wrapper_binding_sha256'] and r['report_pin']==pin(raw['report']) and r['claim_sha256']==sha(raw['claim']),'previous_audit_return')
        integer(claim['stage'],j);need(claim['schema']=='marked-sixfit-audit-wrapper-claim-v1' and claim['study']==STUDY and type(claim['seed'])is int and (claim['seed'],claim['arm'])==PAIRS[j],'previous_claim_identity')
        need(claim['stage']==j and claim['inputs_sha256']==r['input_sha256'] and claim['binding_sha256']==r['binding_sha256'],'previous_audit_claim')
        need(report['status']=='pass' and type(report['checked'])is int and report['checked']==66 and (report['seed'],report['arm'])==PAIRS[j],'previous_audit_report');fit_audits.append(report)
        previous.append(dict(stage=j,seed=PAIRS[j][0],arm=PAIRS[j][1],inputs_sha256=r['input_sha256'],binding_sha256=r['binding_sha256'],report_sha256=sha(raw['report']),closed_proof_sha256=sha(raw['closed']),known_verified=True,exit_status=0,unit_inactive=True,cgroup_empty=True))
    scope=dict(schema='marked-audit-input-authentication-scope-v1',stage=stage,bundle_sha256=bundle_sha,binding_sha256=d.binding_sha256,artifact_pins=artifact_pins,gate_sha256=gate_sha,source_pins=source_pins,packet_sha256=packet_sha,admission_sha256=admission_sha,stronger_closure_sha256=stronger_sha,stronger_origins_sha256=sha(d.canonical(projected['origins'])))
    tick();receipt=d.authenticate(scope,bundle['root_context'],processing_begin=processing_begin);keys(receipt,('schema','scope','decision','proofs'));need(receipt['schema']=='root-marked-audit-input-authentication-v1' and receipt['scope']==scope and receipt['decision']=='authorized','external_authentication')
    keys(receipt['proofs'],('source','runtime','native','stronger','history_gradient','resources'))
    for v in receipt['proofs'].values():keys(v,('known_verified','sha256'));need(v['known_verified']is True,'known_root_proof');digest(v['sha256'])
    tick()
    common=dict(packet_sha256=packet_sha,admission_sha256=admission_sha,source_pins=source_pins,stronger_closure_sha256=stronger_sha)
    prior_authorities=[]
    for j in range(stage):
        authority=dict(schema='root-marked-sixfit-independent-authority-v1',verified=True,native_verified=True,optimizer_history_verified=True,gradient_probes_verified=True,stronger_verified=True,checkpoint_sha256=sha(d.canonical(stages[2*j+1])),score_sha256=sha(d.canonical(stages[2*j+2])),**common)
        expected_inputs=dict(score=stages[2*j+2],packet=packet,admission=admission,checkpoint=stages[2*j+1],authority=authority)
        need(fit_audits[j]['authority_sha256']==sha(d.canonical(authority)) and previous[j]['inputs_sha256']==sha(d.canonical(expected_inputs)),'previous_authority_inputs_binding');prior_authorities.append(authority)
    if stage<6:
        cp=stages[2*stage+1];score=stages[2*stage+2]
        authority=dict(schema='root-marked-sixfit-independent-authority-v1',verified=True,native_verified=True,optimizer_history_verified=True,gradient_probes_verified=True,stronger_verified=True,checkpoint_sha256=sha(d.canonical(cp)),score_sha256=sha(d.canonical(score)),**common)
        inputs=dict(score=score,packet=packet,admission=admission,checkpoint=cp,authority=authority)
    else:
        fits=[]
        for j,(seed,arm)in enumerate(PAIRS):
            a=prior_authorities[j]
            fits.append(dict(seed=seed,arm=arm,audit_sha256=sha(d.canonical(fit_audits[j])),authority_sha256=sha(d.canonical(a)),score_sha256=a['score_sha256'],checkpoint_sha256=a['checkpoint_sha256']))
        authority=dict(schema='root-marked-sixfit-aggregate-authority-v1',verified=True,native_verified=True,stronger_verified=True,fits=fits,**common)
        inputs=dict(fit_audits=fit_audits,score_results=[stages[j]for j in (2,4,6,8,10,12)],packet=packet,admission=admission,stronger=stronger,authority=authority)
    return dict(inputs=inputs,inputs_sha256=sha(d.canonical(inputs)),previous=previous,proofs=receipt['proofs'],evidence=scope)

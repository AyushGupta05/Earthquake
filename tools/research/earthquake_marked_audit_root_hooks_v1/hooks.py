"""Unchanged original native/strong positive-provenance checks; no new authority."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import math
OLD_ORDER=[(s,a) for s in (20261012,20261013) for a in ('B','F','H','T','C')]
STRONG_ORDER=[p for p in OLD_ORDER if p[1]!='C']
CLOSED_FLAGS={'all660_forward_parameters_previously_agreed','all10_fit_reports_agree_with_final_aggregate','all30_horizon_metrics_independently_recomputed','all24_guards_independently_recomputed','owned_units_stopped_empty'}
def need(v,why):
    if not v:raise ValueError(why)

def keys(v,k):return type(v) is dict and set(v)==set(k) and all(type(x) is str for x in v)
def integer(v,a,b):return type(v) is int and a<=v<=b

def finite(v):
    try:return type(v) in (int,float) and math.isfinite(v)
    except OverflowError:return False


def utc(value):
    need(type(value) is str and len(value)<=40,'utc');d=datetime.fromisoformat(value.replace('Z','+00:00'));need(d.tzinfo is not None and d.utcoffset()==timedelta(0),'utc_domain');return d.timestamp()


def money(v):
    need(finite(v) and v>=0,'money');d=Decimal(str(v));need(d.as_tuple().exponent>=-2,'money_precision');return d


def file_spec(io,s,cap=16*1024*1024):
    need(keys(s,('path','pin','mode')) and s['mode']==0o400 and type(s['mode']) is int,'readonly_spec');io.parts(s['path'],True);io.pin_check(s['pin'],cap)


def object_read(io,s,cap=16*1024*1024):file_spec(io,s,cap);return io.json_read(io.read_file(s,cap),cap)


def original_id(io,pins):
    need(keys(pins,('archive','manifest')),'original_packet')
    for p in pins.values():io.pin_check(p,128*1024*1024)
    return io.pin(io.canonical(pins))['sha256']


def normal_return(io,s,expected_schema):
    v=object_read(io,s,262144);need(v['schema']==expected_schema and v['status']=='complete' and integer(v['unit_exit'],0,0) and v['owned_unit_inactive'] is True and v['owned_cgroup_empty'] is True and v['no_retry'] is True,'closed_unit')
    need(type(v['files']) is dict and 1<=len(v['files'])<=128,'closed_files');root=str(Path(s['path']).parent);total=0
    for name,p in v['files'].items():
        io.parts(name);need('/' not in name,'closed_member');io.pin_check(p,64*1024*1024);total+=p['bytes'];io.read_file(dict(path=root+'/'+name,pin=p,mode=0o400),64*1024*1024)
    need(integer(v['total_bytes'],total,total) and total<=64*1024*1024,'closed_total');return v


def roles(io,rows):
    need(type(rows) is list and len(rows)==87,'roster');seen=set();counts=dict(TRAIN=0,DEV=0)
    for r in rows:
        need(keys(r,('ordinal','partition','mw','group','horizons')) and integer(r['ordinal'],0,114) and r['ordinal'] not in seen and integer(r['group'],0,114) and finite(r['mw']) and -5<=r['mw']<=15 and type(r['partition']) is str and r['partition'] in counts and io.canonical(r['horizons'])==io.canonical([1,3,5]),'role');seen.add(r['ordinal']);counts[r['partition']]+=1
    need([r['ordinal'] for r in rows]==sorted(seen) and counts==dict(TRAIN=65,DEV=22),'same87');return [r for r in rows if r['partition']=='DEV']



def verify(io,ac,config,gate,documents):
    feature=io.json_read(documents['feature_authority']);need(keys(feature,('schema','feature_schema','feature_study','events','horizon_cells','common_train','common_dev','allpositive','archive_pin','manifest_pin','packet_sha256','roster','native_return_pins')) and feature['schema']=='root-marked-native-feature-authority-v1' and feature['feature_schema']==gate['feature_schema'] and feature['feature_study']==gate['feature_study'] and integer(feature['events'],115,115) and integer(feature['horizon_cells'],345,345) and integer(feature['common_train'],65,65) and integer(feature['common_dev'],22,22) and feature['allpositive'] is True and feature['archive_pin']==gate['input_pins']['feature_archive'] and feature['manifest_pin']==gate['input_pins']['feature_manifest'],'feature_authority');dev=roles(io,feature['roster']);io.pin_check(dict(bytes=1,sha256=feature['packet_sha256']))
    need(type(ac['native_returns']) is list and len(ac['native_returns'])==3 and feature['native_return_pins']==[s['pin'] for s in ac['native_returns']],'native_closures')
    returns=[normal_return(io,s,'marked-native-root-preparation-return-v1' if i==0 else 'marked-native-parent-return-v1') for i,s in enumerate(ac['native_returns'])]
    need(returns[1]['stage']=='build' and returns[2]['stage']=='audit' and returns[1]['input_fingerprint']==returns[2]['input_fingerprint'] and returns[1]['files']['features.private.npz']==feature['archive_pin'] and returns[1]['files']['features_manifest.private.json']==feature['manifest_pin'],'native_result_pins')
    for i in (1,2):
        s=ac['native_returns'][i];result=object_read(io,dict(path=str(Path(s['path']).parent/'result.private.json'),pin=returns[i]['files']['result.private.json'],mode=0o400));need(result['status']=='complete' and result['fit_authorized'] is False,'native_result')
        if i==1:need(result['archive_pin']==feature['archive_pin'] and result['manifest_pin']==feature['manifest_pin'] and integer(result['events'],115,115) and integer(result['horizon_cells'],345,345),'build_result')
        else:
            a=result['audit'];need(a['schema']=='marked-native-independent-semantic-audit-v1' and a['semantic_agreed'] is True and a['allpositive_pilot_admission'] is True and a['fit_authorized'] is False and integer(a['events'],115,115) and integer(a['horizon_cells'],345,345) and integer(a['common_train'],65,65) and integer(a['common_dev'],22,22),'native_semantic')
    # Hash feature bytes without interpreting a numerical waveform or mark.
    io.read_file(config['inputs']['feature_archive']);io.read_file(config['inputs']['feature_manifest'])
    strong=io.json_read(documents['strong_authority']);old=io.json_read(documents['strong_results']);need(keys(strong,('schema','whole_closure_pin','whole_result_pin','whole_parent_pin','original_packet_pins','original_packet_sha256','roster','origins')) and strong['schema']=='root-original-strong-authority-v1' and strong['whole_closure_pin']==ac['whole_closure']['pin'] and strong['whole_result_pin']==ac['whole_result']['pin'] and strong['whole_parent_pin']==ac['whole_audit']['pin'] and io.canonical(strong['roster'])==io.canonical(feature['roster']),'strong_authority')
    need(keys(old,('schema','original_packet_pins','original_packet_sha256','roster','fits')) and old['schema']=='root-original-strong-comparison-input-v1' and old['original_packet_pins']==strong['original_packet_pins'] and old['original_packet_sha256']==strong['original_packet_sha256']==original_id(io,strong['original_packet_pins']) and io.canonical(old['roster'])==io.canonical(feature['roster']),'old_origin_packet')
    need(keys(ac['original_packet'],('archive','manifest')) and {k:s['pin'] for k,s in ac['original_packet'].items()}==strong['original_packet_pins'],'original_packet_specs')
    for k,s in ac['original_packet'].items():file_spec(io,s,128*1024*1024 if k=='archive' else 4*1024*1024);io.read_file(s,128*1024*1024 if k=='archive' else 4*1024*1024)
    whole=object_read(io,ac['whole_closure']);need(whole['schema']=='root-full-receiver-score-closure-v1' and all(whole[k] is True for k in CLOSED_FLAGS) and integer(whole['complete_stages'],11,11) and integer(whole['fits'],10,10) and integer(whole['independent_probability_records'],660,660) and integer(whole['new_optimizer_steps'],0,0) and whole['TEST_opened'] is False and whole['aggregate_report_pin']==ac['whole_result']['pin'],'whole660')
    parent=normal_return(io,ac['whole_audit'],'receiver-batched-score-parent-return-v1');need(parent['stage']=='aggregate' and integer(parent['index'],10,10) and parent['audit_status']=='pass' and ac['whole_result']['pin'] in parent['files'].values(),'whole_parent')
    wrapped=object_read(io,ac['whole_result']);need(wrapped['schema']=='receiver-batched-score-stage-report-v1' and integer(wrapped['index'],10,10) and wrapped['stage']=='aggregate' and wrapped['within_budget'] is True and wrapped['outcomes']=={} and wrapped['binding']['packet_pins']==strong['original_packet_pins'] and wrapped['binding']['source_commit']==whole['frozen_source_commit'],'whole_binding');report=wrapped['report'];need(report['schema']=='earthquake-TRAIN115-renewal-score-audit-v3' and report['status']=='pass' and report['reasons']==[] and type(report['fits']) is list and len(report['fits'])==10 and type(report['comparisons']) is list and len(report['comparisons'])==24,'closed_scores')
    need(type(ac['checkpoints']) is list and len(ac['checkpoints'])==8 and type(strong['origins']) is list and len(strong['origins'])==8 and type(old['fits']) is list and len(old['fits'])==8,'eight_origins')
    fit_by={}
    for fit,pair in zip(report['fits'],OLD_ORDER):
        need(integer(fit['seed'],pair[0],pair[0]) and fit['arm']==pair[1] and fit['status']=='complete' and type(fit['predictions']) is list and len(fit['predictions'])==66,'ten_fit_order');fit_by[pair]=fit
        for p,(r,h) in zip(fit['predictions'],[(r,h) for r in dev for h in (1,3,5)]):need(integer(p['ordinal'],r['ordinal'],r['ordinal']) and integer(p['horizon'],h,h) and integer(p['group'],r['group'],r['group']) and io.canonical(p['target'])==io.canonical(r['mw']),'whole_population')
    for descriptor,origin,fit,pair in zip(ac['checkpoints'],strong['origins'],old['fits'],STRONG_ORDER):
        need(keys(descriptor,('seed','arm','checkpoint','fit_report','source_pin','source_spec')) and integer(descriptor['seed'],pair[0],pair[0]) and descriptor['arm']==pair[1] and integer(fit['seed'],pair[0],pair[0]) and fit['arm']==pair[1] and fit['status']=='complete' and fit['no_optimizer'] is True and fit['packet_sha256']==old['original_packet_sha256'],'eight_order');file_spec(io,descriptor['checkpoint']);io.read_file(descriptor['checkpoint']);single=object_read(io,descriptor['fit_report']);single_report=single['report'];need(single['schema']=='receiver-batched-score-stage-report-v1' and single['stage']=='fit' and single['within_budget'] is True and single_report['schema']=='receiver-fit-score-audit-v1' and single_report['status']=='pass' and single_report['complete'] is True and single_report['reasons']==[] and io.canonical(single_report['fit'])==io.canonical(fit_by[pair]),'perfit_closed')
        need(origin==dict(seed=pair[0],arm=pair[1],checkpoint_pin=descriptor['checkpoint']['pin'],result_pin=descriptor['fit_report']['pin'],source_pin=descriptor['source_pin'],closure_pin=ac['whole_result']['pin']),'origin_subjects');io.pin_check(descriptor['source_pin']);need(descriptor['source_spec']['pin']==descriptor['source_pin'],'original_source_pin');file_spec(io,descriptor['source_spec']);io.read_file(descriptor['source_spec']);need(fit['checkpoint_sha256']==descriptor['checkpoint']['pin']['sha256'] and fit['result_pin']==descriptor['fit_report']['pin'],'checkpoint_result')
        c=fit['independent_closure'];need(keys(c,('verified','checkpoint_sha256','source_sha256','packet_sha256','no_optimizer','proof_pin')) and c['verified'] is True and c['no_optimizer'] is True and c['checkpoint_sha256']==fit['checkpoint_sha256'] and c['source_sha256']==descriptor['source_pin']['sha256'] and c['packet_sha256']==old['original_packet_sha256'] and c['proof_pin']==ac['whole_result']['pin'],'independent_origin')
        expected=[dict(p,seed=pair[0],arm=pair[1],status='complete') for p in fit_by[pair]['predictions']];need(io.canonical(fit['predictions'])==io.canonical(expected),'all528_exact_original_records')
    return feature,strong,old

# New seven-audit authority is separate from all original fitting-stage permissions.
import copy
import os
import re
import time
import types
from types import SimpleNamespace

STUDY='earthquake-TRAIN115-marked-noise-fitting-v2'
PAIRS=[(s,a) for s in (20261012,20261013) for a in ('S','P','D')]
LIMITS=dict(memory=2147483648,swap=0,tasks=64,cpu_weight=10,threads=1,cuda_hidden=True,kill_mode='control-group',stop_seconds=5)
SCOPE_KEYS={'schema','config_pin','audit_id','study','stage','unit','phase','binding_sha256','bundle_pin','source_manifest_pins','runtime_subject_pin','publication_pin','protocol_pin','whole_begin','lease_deadline'}
AC_KEYS={'schema','funding','resource','publication','boot_id','lease','original_config','original_authority','original_execution','last_return_evidence_directory','source_proof','runtime_proof'}
RAW_CREDIT_KEYS={'schema','account_shared','authorized_credit_only_ceiling_usd','checked_utc','conservative_task_reservation_usd','credit_reserved_by_provider','eligible_services','estimated_amounts_delayed_24_hours','main_credit_estimated_remaining_usd','main_credit_expiry','main_credit_status','same_account_default_cli_credentials_refreshed','screen','settled_incremental_task_spend_unknown','total_estimated_remaining_usd'}
SERVICES=['Amazon Elastic Compute Cloud','AWS Data Transfer','Amazon Virtual Private Cloud']
FKEYS={'schema','credits_only','main_active','services','ceiling_usd','reservation_usd','task_spend_upper_bound_usd','estimated_balance_usd','uncertainty_reserve_usd','other_reservations_usd','unreserved_lower_bound_usd','checked_utc','valid_until_utc','credit_expiry_utc','raw_proof'}


def stage_spec(gate,index):
    need(integer(index,0,13) and type(gate['experiment_id']) is str and re.fullmatch('[a-z0-9-]{1,48}',gate['experiment_id']),'original_stage')
    stages=[('admission',None,None)]+[(kind,s,a) for s,a in PAIRS for kind in ('fit','score')]+[('aggregate',None,None)]
    kind,seed,arm=stages[index];source=900 if kind=='score' else 300
    return dict(index=index,kind=kind,seed=seed,arm=arm,source_seconds=source,manager_seconds=source+60,unit='eew-marked-'+gate['experiment_id']+'-%02d.service'%index,limits=dict(LIMITS))


def original_members(index):
    names={'claim.json','manager_return.json','post.json','child_report.json','result.json','closed.json'}
    if index==0:names|={'initial_%02d.json'%i for i in range(6)}
    elif index<13 and index%2:names|={'begin_fit.json','latest_update.json'}|{'update_%03d.json'%i for i in range(1,301)}
    elif index<13:names|={'forecast_%02d.json'%i for i in range(66)}
    return names


def raw_properties(raw):
    need(type(raw) is str and len(raw)<=65536,'raw_properties');out={}
    for line in raw.splitlines():
        need('=' in line,'property_line');key,value=line.split('=',1);need(key not in out,'duplicate_property');out[key]=value
    return out


def duration(raw):
    # systemctl's duration grammar is observed, not guessed default values.
    need(type(raw) is str and len(raw)<=128,'duration')
    pieces=re.findall(r'([0-9]+(?:\.[0-9]+)?)(h|min|s|ms|us)',raw)
    need(pieces and ''.join(n+u for n,u in pieces)==raw.replace(' ',''),'duration')
    return sum(Decimal(n)*{'h':Decimal(3600),'min':Decimal(60),'s':Decimal(1),'ms':Decimal('.001'),'us':Decimal('.000001')}[u] for n,u in pieces)


def finance(io,spec,wall):
    funding=object_read(io,spec,2*1024*1024)
    need(keys(funding,FKEYS) and funding['schema']=='root-marked-funding-proof-v1' and funding['credits_only'] is True and funding['main_active'] is True and funding['services']==['EC2','VPC','DataTransfer'],'funding')
    raw=object_read(io,funding['raw_proof'],2*1024*1024)
    need(keys(raw,RAW_CREDIT_KEYS) and raw['schema']=='eligible-AWS-main-credit-live-UI-proof-v1','credit_raw_schema')
    need(raw['account_shared'] is True and raw['estimated_amounts_delayed_24_hours'] is True and raw['credit_reserved_by_provider'] is False and raw['settled_incremental_task_spend_unknown'] is True and raw['same_account_default_cli_credentials_refreshed'] is True,'raw_credit_semantics')
    need(raw['main_credit_status']=='Active' and raw['main_credit_expiry']=='2026-10-31' and raw['eligible_services']==SERVICES and integer(raw['authorized_credit_only_ceiling_usd'],2000,2000) and integer(raw['conservative_task_reservation_usd'],335,335) and type(raw['screen']) is str and 1<=len(raw['screen'])<=2048,'raw_eligibility')
    fields=('ceiling_usd','reservation_usd','task_spend_upper_bound_usd','estimated_balance_usd','uncertainty_reserve_usd','other_reservations_usd','unreserved_lower_bound_usd')
    amounts={k:money(funding[k]) for k in fields}
    need(amounts['ceiling_usd']==2000 and amounts['reservation_usd']==335 and amounts['task_spend_upper_bound_usd']<335 and amounts['uncertainty_reserve_usd']>=1500,'conservative_task_budget')
    need(money(raw['main_credit_estimated_remaining_usd'])==amounts['estimated_balance_usd'] and money(raw['total_estimated_remaining_usd'])>=amounts['estimated_balance_usd'] and raw['checked_utc']==funding['checked_utc'],'raw_amount_binding')
    lower=amounts['estimated_balance_usd']-amounts['uncertainty_reserve_usd']-amounts['other_reservations_usd']
    remaining=amounts['ceiling_usd']-amounts['task_spend_upper_bound_usd']
    need(lower==amounts['unreserved_lower_bound_usd'] and lower>=remaining,'remaining_credit_ceiling')
    cutoff=utc('2026-10-13T16:40:00Z');expiry=utc(funding['credit_expiry_utc'])
    need(datetime.fromtimestamp(expiry,timezone.utc).date().isoformat()=='2026-10-31' and utc(funding['checked_utc'])<=wall<utc(funding['valid_until_utc'])<=min(cutoff,expiry),'financial_clock')
    return funding


def closed_history(io,execution,bundle,gate):
    need(keys(execution,('schema','gate_sha256','controller_source_pin','deployment_config_pin','bootstrap_source_pin','source_commit','stages','TEST_opened')) and execution['schema']=='root-marked-original-fourteen-execution-v1' and execution['TEST_opened'] is False and execution['gate_sha256']==io.pin(io.canonical(gate))['sha256'] and type(execution['stages']) is list and len(execution['stages'])==14,'original_execution')
    need(type(execution['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',execution['source_commit']),'original_execution_commit')
    need(type(bundle['stages']) is list and len(bundle['stages'])==14,'fourteen_bundle_stages')
    for index,(held,files) in enumerate(zip(execution['stages'],bundle['stages'])):
        need(keys(held,('index','unit','last_return','directory','files')) and integer(held['index'],index,index) and held['unit']==stage_spec(gate,index)['unit'] and keys(files,original_members(index)) and set(held['files'])==original_members(index)|{'bootstrap.json'} and all(held['files'][n]==s['pin'] for n,s in files.items()),'original_inventory')
        fd=io.directory(held['directory'])
        try:need(set(os.listdir(fd))==original_members(index)|{'bootstrap.json'},'late_or_unknown_member')
        finally:os.close(fd)
        bootstrap=object_read(io,dict(path=held['directory']+'/bootstrap.json',pin=held['files']['bootstrap.json'],mode=0o400))
        need(bootstrap['schema']=='marked-stage-launch-v1' and io.pin(io.canonical(bootstrap['config']))==execution['deployment_config_pin'] and bootstrap['expected_deployment_config_pin']==execution['deployment_config_pin'] and bootstrap['config']['bootstrap']['pin']==execution['bootstrap_source_pin'],'original_bootstrap_positive')
        raw={}
        for name,spec in files.items():
            need(str(Path(spec['path']).parent)==held['directory'] and Path(spec['path']).name==name,'original_member_path')
            raw[name]=io.read_file(spec)
        closed=io.json_read(raw['closed.json']);need(closed==held['last_return'] and closed['schema']=='marked-sixfit-parent-return-v1' and closed['status']=='complete' and integer(closed['index'],index,index) and closed['unit']==held['unit'] and closed['cleanup_verified'] is True and closed['errors']==[] and closed['no_retry'] is True and closed['gate_sha256']==execution['gate_sha256'] and closed['report_pin']==io.pin(raw['child_report.json']) and closed['result_pin']==io.pin(raw['result.json']),'actual_last_parent_return')
        post=io.json_read(raw['post.json']);need(post==dict(unit=held['unit'],result='success',active_state='inactive',control_group=''),'original_raw_cleanup')
        manager=io.json_read(raw['manager_return.json']);need(integer(manager['code'],0,0) and manager['timeout'] is False and manager['streams_complete'] is True and manager['exception'] is None,'original_raw_manager')
        for stream in ('stdout','stderr'):
            clip=manager[stream];need(clip['truncated'] is False and type(clip['retained_hex']) is str and io.pin(bytes.fromhex(clip['retained_hex']))==clip['original_pin'],'original_complete_stream')
        claim=io.json_read(raw['claim.json']);need(claim['gate']==gate and claim['gate_sha256']==execution['gate_sha256'] and claim['stage']==stage_spec(gate,index) and bootstrap['request']==claim,'original_controller_claim')
    return execution


def known_root_return(io,path):
    import stat
    parent=str(Path(path).parent);name=Path(path).name;directory=io.directory(parent)
    try:
        fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory)
        try:
            st=os.fstat(fd);need(stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode)==0o400 and st.st_nlink==1 and st.st_uid==os.getuid() and st.st_size<=262144,'root_return_file')
            raw=b''
            while len(raw)<=262144:
                block=os.read(fd,65536)
                if not block:break
                raw+=block
            end=os.fstat(fd);need((st.st_size,st.st_mtime_ns,st.st_ctime_ns)==(end.st_size,end.st_mtime_ns,end.st_ctime_ns) and len(raw)==st.st_size,'root_return_stable')
        finally:os.close(fd)
    finally:os.close(directory)
    need(io.read_file(dict(path=path,pin=io.pin(raw),mode=0o400),262144)==raw,'root_return_readback')
    return io.json_read(raw)


def make_hooks(config,*,io,sb,clock,expected_config_pin):
    need(type(io) is types.ModuleType and type(sb) is types.ModuleType and callable(clock),'dependencies')
    for module,names in ((io,('read_file','canonical','json_read','pin','pin_check','parts','directory')),(sb,('source','runtime','cross_copies'))):
        need(all(callable(getattr(module,n,None)) and getattr(module,n).__globals__ is module.__dict__ for n in names),'bound_helper_globals')
    io.pin_check(expected_config_pin);need(io.pin(io.canonical(config))==expected_config_pin,'out_of_band_config_pin')
    need(config['schema']=='marked-seven-audit-deployment-v1' and config['study']==STUDY and type(config['audit_id']) is str and re.fullmatch('[a-z0-9-]{1,48}',config['audit_id']) and config['storage_limit_bytes']==7*64*1024*1024 and 'bundle_template' in config,'audit_config')
    for name,module in (('secure_io',io),('source_binding',sb)):
        source=config['sources']['v6'];need(Path(module.__file__)==Path(source['directory'])/(name+'.py'),'helper_origin');io.read_file(dict(path=str(Path(module.__file__)),pin=source['files'][name+'.py'],mode=0o400))
    io.read_file(config['hooks_source']);need(Path(__file__)==Path(config['hooks_source']['path']),'hooks_origin')
    ac=object_read(io,config['hooks_config'],2*1024*1024);need(keys(ac,AC_KEYS) and ac['schema']=='root-marked-seven-audit-hooks-config-v1','hooks_config')
    original=object_read(io,ac['original_config']);oldac=object_read(io,ac['original_authority']);gate=object_read(io,oldac['gate']);need(gate['schema']=='marked-sixfit-parent-gate-v1' and gate['study']==STUDY,'original_gate')
    need(original['authority_config']==ac['original_authority'] and ac['publication']==config['publication'],'original_provenance_config')
    expected_old_sources=dict(processor=original['sources']['processor']['manifest']['pin'],operator=original['sources']['gaussian']['manifest']['pin'],reference=original['sources']['gaussian']['manifest']['pin'],native=original['sources']['native']['manifest']['pin'],parent=original['sources']['parent']['manifest']['pin'],protocol=original['protocol']['pin'])
    need(expected_old_sources==gate['source_pins'] and {k:spec['pin'] for k,spec in original['inputs'].items()}==gate['input_pins'] and original['runtime']['manifest']['pin']==gate['runtime_pin'] and io.canonical(original['runtime'])==io.canonical(config['runtime']),'original_positive_subjects')
    docs={k:io.read_file(original['inputs'][k]) for k in ('feature_authority','strong_authority','strong_results')}
    # Original provenance algorithm copied literally; original fit permissions not reused.
    feature,strong,old=verify(io,oldac,original,gate,docs)
    template=object_read(io,config['bundle_template']);need(template['schema']=='root-marked-audit-input-bundle-v1' and template['previous_audits']==[] and template['binding_sha256']==config['binding_sha256'] and template['wrapper_binding_sha256']==config['wrapper_binding_sha256'],'bundle_template')
    need(template['root_context']==dict(schema='root-marked-seven-audit-context-v1',original_execution_pin=ac['original_execution']['pin']),'template_root_context')
    io.parts(ac['last_return_evidence_directory'],True);need(ac['last_return_evidence_directory']!=config['store_directory'],'separate_root_evidence')
    authorized={}
    config=copy.deepcopy(config);ac=copy.deepcopy(ac);expected_config_pin=copy.deepcopy(expected_config_pin)

    def tick(begin=None):
        now=clock();need(finite(now),'clock')
        if begin is not None:need(finite(begin) and 0<=begin<=now and now-begin<=900,'source_deadline')
        need(finite(config['whole_begin']) and 0<=config['whole_begin']<=now and now<=config['whole_begin']+7200 and finite(config['lease_deadline']) and now<=config['lease_deadline']<=config['whole_begin']+7400,'whole_deadline')
        return now

    def subjects():
        return {k:s['manifest']['pin'] for k,s in config['sources'].items()}

    def runtime_source():
        original_raw={role:sb.source(spec,role,tick) for role,spec in original['sources'].items()};sb.cross_copies(original_raw)
        for role,spec in config['sources'].items():sb.source(spec,{'v6':'adapters','native':'native'}.get(role,role),tick)
        sb.runtime(config['runtime'],tick)
        source=object_read(io,ac['source_proof']);runtime=object_read(io,ac['runtime_proof'])
        need(source['schema']=='root-seven-audit-source-runtime-proof-v1' and source['status']=='pass' and source['source_manifest_pins']==subjects() and source['hooks_source_pin']==config['hooks_source']['pin'] and source['protocol_pin']==config['protocol']['pin'],'source_proof')
        need(runtime['schema']=='root-seven-audit-source-runtime-proof-v1' and runtime['status']=='pass' and runtime['runtime_subject_pin']==io.pin(io.canonical(config['runtime'])) and runtime['source_manifest_pins']==subjects(),'runtime_proof')
        return source,runtime

    def resource_check(now,phase):
        wall=time.time();funding=finance(io,ac['funding'],wall)
        lease=ac['lease'];need(keys(lease,('issued','expires','expires_utc','boot_id_sha256')) and finite(lease['issued']) and finite(lease['expires']) and 0<=lease['issued']<=now<=lease['expires']<=config['lease_deadline'],'lease')
        need(ac['boot_id']['path']=='/proc/sys/kernel/random/boot_id' and ac['boot_id']['mode']==0o444,'boot_path')
        boot=io.read_file(ac['boot_id'],128);need(io.pin(boot)['sha256']==lease['boot_id_sha256'],'same_boot')
        need(wall<utc(lease['expires_utc'])<=utc(funding['valid_until_utc']) and lease['expires']-now<=utc(lease['expires_utc'])-wall,'wall_monotonic_lease')
        if phase=='parent':need(now+960<=min(lease['expires'],config['whole_begin']+7200),'manager_coverage')
        resource=object_read(io,ac['resource']);need(resource['schema']=='root-seven-audit-resource-proof-v1' and resource['source_manifest_pins']==subjects() and resource['runtime_subject_pin']==io.pin(io.canonical(config['runtime'])) and resource['funding_pin']==ac['funding']['pin'] and resource['publication_pin']==config['publication']['pin'] and resource['protocol_pin']==config['protocol']['pin'] and resource['hooks_source_pin']==config['hooks_source']['pin'] and resource['binding_sha256']==config['binding_sha256'] and resource['whole_begin']==config['whole_begin'] and resource['lease_deadline']==config['lease_deadline'] and resource['commands']==config['commands'],'resource_subjects')
        units=['eew-marked-'+config['audit_id']+'-%02d.service'%i for i in range(7)]
        need(resource['approved_units']==units and resource['limits']==LIMITS and integer(resource['whole_seconds'],7200,7200) and integer(resource['closure_seconds'],200,200) and resource['disk_directory']==config['store_directory'] and integer(resource['disk_reservation_bytes'],config['storage_limit_bytes'],2**40) and resource['boot_id_sha256']==lease['boot_id_sha256'],'audit_resources')
        raw=object_read(io,resource['raw_control_proof']);need(raw['schema']=='root-seven-audit-installed-stop-raw-v1' and raw['approved_units']==units and raw['commands']==config['commands'] and raw['boot_id_sha256']==lease['boot_id_sha256'] and finite(raw['installed_begin_monotonic']) and 0<=raw['installed_begin_monotonic']<=config['whole_begin'] and raw['automatic_stop_utc']==resource['automatic_stop_utc'],'installed_control_subjects')
        timer=raw_properties(raw['observedraw_systemctl_timer']);service=raw_properties(raw['observedraw_service'])
        need(timer['ActiveState']=='active' and timer['Unit']==raw['service_unit'] and duration(timer['AccuracyUSec'])<=1 and service['ActiveState']=='inactive','stop_active')
        match=re.search(r'OnActiveSec=([^;]+)',timer['TimersMonotonic']);need(match is not None and duration(match.group(1).strip())==7400,'stop_timer_interval')
        vectors=re.findall(r'argv\[\]=([^;]*)(?:;|$)',service['ExecStart'])
        need(type(raw['exec_argv']) is list and raw['exec_argv']==['/usr/bin/bash',raw['stop_script']['path']] and len(vectors)==1 and vectors[0].split()==raw['exec_argv'],'stop_exec')
        stop=io.read_file(raw['stop_script'],65536);need(stop==raw['expected_stop_script'].encode() and all(('systemctl --user stop '+u+'\n').encode() in stop for u in units),'stop_script_bound')
        deadline=raw['installed_begin_monotonic']+7400
        need(finite(resource['cost_deadline_monotonic']) and lease['expires']<=min(deadline,resource['cost_deadline_monotonic']) and utc(lease['expires_utc'])<=utc(resource['automatic_stop_utc'])<=utc(funding['valid_until_utc']),'stop_lease')
        fd=io.directory(config['store_directory'])
        try:space=os.fstatvfs(fd);available=space.f_bavail*space.f_frsize
        finally:os.close(fd)
        need(available>=resource['disk_reservation_bytes']+64*1024*1024,'disk_reservation')
        end=clock();wall_end=time.time();need(finite(end) and end<=lease['expires'] and (end+960<=min(lease['expires'],config['whole_begin']+7200) if phase=='parent' else end<=config['whole_begin']+7200),'final_resource_deadline')
        need(finite(wall_end) and utc(funding['checked_utc'])<=wall_end<min(utc(lease['expires_utc']),utc(funding['valid_until_utc']),utc(resource['automatic_stop_utc'])) and lease['expires']-end<=utc(lease['expires_utc'])-wall_end,'final_utc_deadline')
        return funding,resource,available

    def publication_check(documents):
        need(keys(documents,('publication','protocol','hooks_config','bundle')) and all(documents[k]==io.read_file(config[k]) for k in ('publication','protocol','hooks_config')),'authorization_documents')
        publication=io.json_read(documents['publication'])
        need(publication['schema']=='root-seven-audit-publication-proof-v1' and publication['source_manifest_pins']==subjects() and publication['runtime_subject_pin']==io.pin(io.canonical(config['runtime'])) and publication['hooks_source_pin']==config['hooks_source']['pin'] and publication['protocol_pin']==config['protocol']['pin'] and type(publication['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',publication['source_commit']),'publication_subjects')
        need(type(publication['linux_proofs']) is list and publication['linux_proofs'],'target_proof')
        for spec in publication['linux_proofs']:
            proof=object_read(io,spec);need(proof['status']=='pass' and integer(proof['skip'],0,0) and integer(proof['fail'],0,0) and integer(proof['error'],0,0) and proof['source_manifest_pins']==subjects() and proof['runtime_subject_pin']==io.pin(io.canonical(config['runtime'])) and proof['hooks_source_pin']==config['hooks_source']['pin'],'target_exact')
        need(bool(io.read_file(publication['published_proof'])),'published_evidence')
        return publication

    def held_bundle(stage,bundle):
        need(keys(bundle,template) and all(bundle[k]==template[k] for k in template if k!='previous_audits'),'held_bundle')
        need(type(bundle['previous_audits']) is list and len(bundle['previous_audits'])==stage,'previous_count')
        for k,spec in bundle['native'].items():need(spec==original['inputs'][k],'native_input_spec')
        for k,spec in bundle['stronger'].items():need(spec==original['inputs'][k],'strong_input_spec')
        execution=object_read(io,ac['original_execution']);need(execution['controller_source_pin']==original['sources']['parent']['files']['controller.py'] and execution['deployment_config_pin']==io.pin(io.canonical(original)) and execution['bootstrap_source_pin']==original['bootstrap']['pin'],'original_controller_source')
        sb.source(original['sources']['parent'],'parent',tick)
        closed_history(io,execution,bundle,gate)
        for i,files in enumerate(bundle['previous_audits']):
            path=ac['last_return_evidence_directory']+'/stage_%02d.private.json'%i
            held=known_root_return(io,path)
            need(keys(held,('schema','stage','config_pin','directory','files','inventory','last_return','root_observation','root_manager')) and held['schema']=='root-seven-audit-last-return-v1' and integer(held['stage'],i,i) and held['config_pin']==expected_config_pin and held['files']=={k:spec['pin'] for k,spec in files.items()},'previous_held_inventory')
            required={'bootstrap.json','dispatch.json','claim.json','return.json','raw_report_000.json','child_report.json','manager_return.json','post.json','closed.json'}
            required|={'record_%03d.json'%j for j in range(66)}
            need(set(held['inventory'])==required,'previous_exact_inventory')
            root=config['store_directory']+'/stage_%02d'%i
            need(held['directory']==root,'previous_own_directory');fd=io.directory(root)
            try:need(set(os.listdir(fd))==set(held['inventory']),'previous_absence')
            finally:os.close(fd)
            for name,pin in held['inventory'].items():io.read_file(dict(path=root+'/'+name,pin=pin,mode=0o400))
            for k,spec in files.items():need(spec['path']==root+'/'+{'claim':'claim.json','return':'return.json','report':'raw_report_000.json','closed':'closed.json'}[k],'previous_bundle_path')
            closed=object_read(io,files['closed']);need(closed==held['last_return'] and closed['schema']=='marked-seven-audit-manager-return-v1' and closed['status']=='complete' and integer(closed['stage'],i,i) and closed['config_pin']==expected_config_pin and closed['unit']=='eew-marked-'+config['audit_id']+'-%02d.service'%i and closed['no_retry'] is True and closed['cleanup_verified'] is True and closed['errors']==[],'previous_actual_return')
            dispatch=object_read(io,dict(path=root+'/dispatch.json',pin=held['inventory']['dispatch.json'],mode=0o400));bootstrap=object_read(io,dict(path=root+'/bootstrap.json',pin=held['inventory']['bootstrap.json'],mode=0o400))
            need(dispatch['schema']=='marked-seven-audit-request-v1' and dispatch['config_pin']==expected_config_pin and integer(dispatch['stage']['index'],i,i) and dispatch['stage']['unit']==closed['unit'] and dispatch['stage']['limits']==LIMITS and integer(dispatch['stage']['source_seconds'],900,900) and integer(dispatch['stage']['manager_seconds'],960,960) and bootstrap==dict(schema='marked-seven-audit-launch-v1',request=dispatch,config=config,expected_config_pin=expected_config_pin),'previous_launch_binding')
            child=object_read(io,dict(path=root+'/child_report.json',pin=held['inventory']['child_report.json'],mode=0o400));need(child['schema']=='marked-seven-audit-child-report-v1' and child['status']=='complete' and integer(child['stage'],i,i) and child['config_pin']==expected_config_pin and child['request_pin']==io.pin(io.canonical(dispatch)) and child['return_pin']==files['return']['pin'] and child['report_pin']==files['report']['pin'] and child['claim_pin']==files['claim']['pin'] and child['within_source'] is True and closed['child_report_pin']==held['inventory']['child_report.json'] and closed['return_pin']==files['return']['pin'] and closed['report_pin']==files['report']['pin'],'previous_child_binding')
            report=object_read(io,files['report']);returned=object_read(io,files['return'])
            need(report['status']=='pass' and integer(report['checked'],66,66) and type(report['records']) is list and len(report['records'])==66 and returned['status']=='complete' and integer(returned['retained_count'],67,67) and integer(returned['attempted_count'],67,67),'previous_record_count')
            original_score=object_read(io,bundle['stages'][2*i+2]['result.json']);need(type(original_score['predictions']) is list and len(original_score['predictions'])==66,'prior_original_score66')
            record_bytes=files['report']['pin']['bytes']
            for j in range(66):
                member='record_%03d.json'%j;record=object_read(io,dict(path=root+'/'+member,pin=held['inventory'][member],mode=0o400));need(record['fresh']==report['records'][j] and integer(record['position'],j,j) and record['status']=='pass' and type(record['source_sha256']) is str and record['source_sha256']==io.pin(io.canonical(original_score['predictions'][j]['source']))['sha256'],'previous_record_order');record_bytes+=held['inventory'][member]['bytes']
            need(integer(returned['retained_bytes'],record_bytes,record_bytes),'previous_retained_bytes')
            rootpost=held['root_observation'];post=object_read(io,dict(path=root+'/post.json',pin=held['inventory']['post.json'],mode=0o400))
            need(rootpost==post and post==dict(unit=closed['unit'],result='success',active_state='inactive',control_group=''),'root_owned_cleanup_agreement')
            manager=object_read(io,dict(path=root+'/manager_return.json',pin=held['inventory']['manager_return.json'],mode=0o400))
            need(manager==held['root_manager'] and integer(manager['code'],0,0) and manager['timeout'] is False and manager['streams_complete'] is True and manager['exception'] is None,'root_raw_manager_agreement')
            for stream in ('stdout','stderr'):
                clip=manager[stream];meta=manager['stream_custody'][stream];rawstream=bytes.fromhex(clip['retained_hex']);actual=io.pin(rawstream)
                need(clip['truncated'] is False and actual==clip['retained_pin'] and integer(meta['original_bytes'],len(rawstream),len(rawstream)) and integer(meta['retained_bytes'],len(rawstream),len(rawstream)) and meta['original_sha256']==actual['sha256'] and meta['truncated'] is False and meta['complete_observation'] is True,'root_raw_complete_stream')
        return bundle,execution

    def proofs(execution):
        return dict(source=dict(known_verified=True,sha256=ac['source_proof']['pin']['sha256']),runtime=dict(known_verified=True,sha256=ac['runtime_proof']['pin']['sha256']),native=dict(known_verified=True,sha256=original['inputs']['feature_authority']['pin']['sha256']),stronger=dict(known_verified=True,sha256=oldac['whole_result']['pin']['sha256']),history_gradient=dict(known_verified=True,sha256=ac['original_execution']['pin']['sha256']),resources=dict(known_verified=True,sha256=ac['resource']['pin']['sha256']))

    def authorize(scope,documents,now):
        need(io.pin(io.canonical(config))==expected_config_pin and keys(scope,SCOPE_KEYS) and scope['schema']=='marked-seven-audit-authorization-scope-v1' and scope['config_pin']==expected_config_pin and integer(scope['stage'],0,6) and scope['phase'] in ('parent','child'),'authorization_scope')
        stage=scope['stage'];current=tick();need(finite(now) and abs(current-now)<=1,'same_clock')
        expected=dict(schema=scope['schema'],config_pin=expected_config_pin,audit_id=config['audit_id'],study=STUDY,stage=stage,unit='eew-marked-'+config['audit_id']+'-%02d.service'%stage,phase=scope['phase'],binding_sha256=config['binding_sha256'],bundle_pin=io.pin(documents['bundle']),source_manifest_pins=subjects(),runtime_subject_pin=io.pin(io.canonical(config['runtime'])),publication_pin=config['publication']['pin'],protocol_pin=config['protocol']['pin'],whole_begin=config['whole_begin'],lease_deadline=config['lease_deadline'])
        need(scope==expected,'scope_subjects');publication_check(documents);runtime_source();bundle=io.json_read(documents['bundle']);need(io.canonical(bundle)==documents['bundle'],'canonical_bundle');bundle,execution=held_bundle(stage,bundle)
        funding,resource,available=resource_check(tick(),scope['phase']);tick();authorized[stage]=copy.deepcopy(bundle)
        return dict(schema='root-marked-seven-audit-authorization-v1',scope=copy.deepcopy(scope),decision='authorized',expires=ac['lease']['expires'],disk_available_bytes=available,disk_reserve_bytes=resource['disk_reservation_bytes'],proofs=proofs(execution))

    def project_stronger(packet,envelope,authority_pin,packet_sha):
        need(io.canonical(envelope)==docs['strong_results'] and authority_pin==original['inputs']['strong_authority']['pin'],'strong_projection_inputs')
        rows=[r for r in packet['rows'] if r['common']]
        expected=[dict(ordinal=r['ordinal'],partition=r['partition'],mw=r['mw'],group=r['group'],horizons=[1,3,5]) for r in rows]
        need(envelope['roster']==expected and len(rows)==87 and sum(r['partition']=='TRAIN' for r in rows)==65 and sum(r['partition']=='DEV' for r in rows)==22 and packet_sha==feature['packet_sha256'],'strong_projection_population')
        fits=[];origins=[]
        for fit,pair in zip(envelope['fits'],STRONG_ORDER):
            closed=fit['independent_closure'];need(closed['proof_pin']==oldac['whole_result']['pin'],'full_original_report_pin')
            fits.append(dict(seed=pair[0],arm=pair[1],predictions=copy.deepcopy(fit['predictions']),closure=dict(verified=True,no_optimizer=True,checkpoint_sha256=fit['checkpoint_sha256'],source_sha256=closed['source_sha256'],packet_sha256=packet_sha,independent_audit_sha256=oldac['whole_result']['pin']['sha256'])))
            origin=dict(schema='old-model-new-comparison-join-v1',packet_sha256_semantics='comparison_population_only',original_packet_sha256=envelope['original_packet_sha256'],original_packet_pins=copy.deepcopy(envelope['original_packet_pins']),original_result_pin=copy.deepcopy(fit['result_pin']),original_checkpoint_sha256=fit['checkpoint_sha256'],original_source_sha256=closed['source_sha256'],original_closure_proof_pin=copy.deepcopy(closed['proof_pin']),comparison_join_proof_pin=copy.deepcopy(authority_pin),old_model_reexecuted=False)
            if 'origin' in fit:origin['original_fit_origin']=copy.deepcopy(fit['origin'])
            if 'original_packet_sha256_semantics' in fit:origin['original_packet_sha256_semantics']=copy.deepcopy(fit['original_packet_sha256_semantics'])
            origins.append(origin)
        return dict(fits=fits,origins=origins)

    def authenticate_input(scope,root_context,*,processing_begin):
        tick(processing_begin);need(scope['schema']=='marked-audit-input-authentication-scope-v1' and integer(scope['stage'],0,6),'input_scope')
        stage=scope['stage'];need(stage in authorized,'prior_positive_authorization');bundle,execution=held_bundle(stage,authorized[stage]);need(root_context==template['root_context'],'root_context')
        need(scope['bundle_sha256']==io.pin(io.canonical(bundle))['sha256'] and scope['binding_sha256']==config['binding_sha256'] and bundle['wrapper_binding_sha256']==config['wrapper_binding_sha256'] and scope['gate_sha256']==io.pin(io.canonical(gate))['sha256'] and scope['packet_sha256']==feature['packet_sha256'],'input_subjects')
        artifacts={}
        for i,files in enumerate(bundle['stages']):artifacts.update({'stage_%02d/%s'%(i,n):s['pin'] for n,s in files.items()})
        for role in ('native','stronger'):
            artifacts.update({role+'/'+n:s['pin'] for n,s in bundle[role].items()})
        for i,files in enumerate(bundle['previous_audits']):artifacts.update({'audit_%02d/%s'%(i,n):s['pin'] for n,s in files.items()})
        need(scope['artifact_pins']==artifacts,'all_artifact_pins')
        admission=object_read(io,bundle['stages'][0]['result.json']);need(scope['admission_sha256']==bundle['stages'][0]['result.json']['pin']['sha256'] and scope['source_pins']==admission['source_pins'],'admission_source_subject')
        projected=project_stronger(dict(rows=[dict(r,common=True) for r in feature['roster']]),old,original['inputs']['strong_authority']['pin'],feature['packet_sha256'])
        need(scope['stronger_closure_sha256']==io.pin(io.canonical(projected['fits']))['sha256'] and scope['stronger_origins_sha256']==io.pin(io.canonical(projected['origins']))['sha256'],'stronger_exact_projection')
        publication_check({k:io.read_file(config[k]) for k in ('publication','protocol','hooks_config')} | {'bundle':io.canonical(bundle)});runtime_source();resource_check(tick(processing_begin),'child');tick(processing_begin)
        return dict(schema='root-marked-audit-input-authentication-v1',scope=copy.deepcopy(scope),decision='authorized',proofs=proofs(execution))
    return SimpleNamespace(authorize=authorize,authenticate_input=authenticate_input,project_stronger=project_stronger,stage_spec=stage_spec)

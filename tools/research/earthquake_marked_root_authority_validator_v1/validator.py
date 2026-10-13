"""ROOT-bound readonly authority; no default proof, finance writes or numerical scoring."""
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
import copy,math,os,re,time,types

SCOPE={'gate_sha256','config_pin','index','unit','source_pins','runtime_pin','input_pins','funding_pin','publication_pin','phase'}
AC_KEYS={'schema','gate','funding','resource','publication','native_returns','whole_result','whole_audit','whole_closure','checkpoints','lease','boot_id','original_packet'}
PER_SEED=('B','F','H','T','C')
OLD_ORDER=[(s,a) for s in (20261012,20261013) for a in PER_SEED]
STRONG_ORDER=[p for p in OLD_ORDER if p[1]!='C']
STAGES=[('admission',None,None)]+[(kind,s,a) for s in (20261012,20261013) for a in ('S','P','D') for kind in ('fit','score')]+[('aggregate',None,None)]
CLOSED_FLAGS={'all660_forward_parameters_previously_agreed','all10_fit_reports_agree_with_final_aggregate','all30_horizon_metrics_independently_recomputed','all24_guards_independently_recomputed','owned_units_stopped_empty'}
RESOURCE_KEYS={'schema','gate_sha256','source_pins','runtime_pin','runtime_subject_pin','input_pins','funding_pin','source_commit','approved_units','limits','whole_seconds','disk_directory','disk_reservation_bytes','cost_deadline_monotonic','automatic_stop_utc','raw_control_proof','commands','storage_limit_bytes','boot_id_sha256'}
LIMITS=dict(memory=2147483648,swap=0,tasks=64,cpu_weight=10,threads=1,cuda_hidden=True,kill_mode='control-group',stop_seconds=5)


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


def make_validator(config,*,io,source_binding,clock,expected_deployment_config_pin):
    """expected pin is ROOT bootstrap's independent preverified runtime argument."""
    need(type(io) is types.ModuleType and type(source_binding) is types.ModuleType and callable(clock),'dependencies')
    for module,names in [(io,('read_file','canonical','json_read','pin','pin_check','parts','directory')),(source_binding,('source','runtime','cross_copies'))]:
        need(all(callable(getattr(module,n,None)) and getattr(module,n).__globals__ is module.__dict__ for n in names),'helper_globals')
    io.pin_check(expected_deployment_config_pin,16*1024*1024);need(io.pin(io.canonical(config))==expected_deployment_config_pin,'independent_config_pin')
    # Caller bootstrap already verified these module bytes; repeat their FS pins.
    need(type(getattr(source_binding,'vi',None)) is types.ModuleType and source_binding.vi.io is io,'vendor_helper_globals')
    for name,module in [('secure_io',io),('source_binding',source_binding),('vendor_inventory',source_binding.vi)]:
        src=config['sources']['adapters'];p=src['files'][name+'.py'];need(Path(module.__file__)==Path(src['directory'])/(name+'.py'),'helper_path');io.read_file(dict(path=str(Path(module.__file__)),pin=p,mode=0o400),16*1024*1024)
    ac=object_read(io,config['authority_config'],2*1024*1024);need(keys(ac,AC_KEYS) and ac['schema']=='root-marked-authority-config-v1','authority_config');gate=object_read(io,ac['gate'],2*1024*1024)
    need(gate['schema']=='marked-sixfit-parent-gate-v1' and gate['study']=='earthquake-TRAIN115-marked-noise-fitting-v2' and gate['feature_schema']=='earthquake-TRAIN115-marked-noise-observations-v1' and gate['feature_study']=='earthquake-TRAIN115-marked-noise-study-v1' and type(gate['experiment_id']) is str and re.fullmatch('[a-z0-9-]{1,48}',gate['experiment_id']) and finite(gate['experiment_begin']) and gate['experiment_begin']>=0,'gate')
    need(keys(gate['source_pins'],('processor','operator','native','reference','parent','protocol')) and keys(gate['input_pins'],('feature_archive','feature_manifest','feature_authority','strong_results','strong_authority')),'gate_pins')
    for p in list(gate['source_pins'].values())+list(gate['input_pins'].values())+[gate['runtime_pin'],gate['funding_pin']]:io.pin_check(p)
    expected_sources=dict(processor=config['sources']['processor']['manifest']['pin'],operator=config['sources']['gaussian']['manifest']['pin'],reference=config['sources']['gaussian']['manifest']['pin'],native=config['sources']['native']['manifest']['pin'],parent=config['sources']['parent']['manifest']['pin'],protocol=config['protocol']['pin'])
    need(expected_sources==gate['source_pins'],'role_manifest_gate_binding')
    need(config['storage_limit_bytes']==gate['storage_limit_bytes'] and config['runtime']['manifest']['pin']==gate['runtime_pin'] and config['protocol']['pin']==gate['source_pins']['protocol'] and keys(config['inputs'],gate['input_pins']) and all(config['inputs'][k]['pin']==p for k,p in gate['input_pins'].items()),'config_subjects')
    ac=copy.deepcopy(ac);gate=copy.deepcopy(gate);expected_deployment_config_pin=copy.deepcopy(expected_deployment_config_pin)

    def verify(scope,documents,now):
        need(io.pin(io.canonical(config))==expected_deployment_config_pin,'config_changed')
        need(keys(scope,SCOPE) and scope['config_pin']==expected_deployment_config_pin and scope['gate_sha256']==io.pin(io.canonical(gate))['sha256'] and integer(scope['index'],0,13) and scope['phase'] in ('parent','child'),'scope')
        index=scope['index'];kind,_,_=STAGES[index];manager=960 if kind=='score' else 360;unit='eew-marked-'+gate['experiment_id']+'-%02d.service'%index
        need(type(scope['unit']) is str and scope['unit']==unit and scope['source_pins']==gate['source_pins'] and scope['runtime_pin']==gate['runtime_pin'] and scope['input_pins']==gate['input_pins'] and scope['funding_pin']==gate['funding_pin'] and scope['publication_pin']==config['publication']['pin'],'scope_subjects')
        current=clock();need(finite(now) and finite(current) and abs(current-now)<=1 and now>=gate['experiment_begin'] and now+manager<=gate['experiment_begin']+7200,'same_host_stage_clock')
        need(keys(documents,('publication','feature_authority','strong_authority','strong_results')),'documents')
        for k,input_name in [('feature_authority','feature_authority'),('strong_authority','strong_authority'),('strong_results','strong_results')]:need(type(documents[k]) is bytes and io.pin(documents[k])==gate['input_pins'][input_name] and documents[k]==io.read_file(config['inputs'][input_name]),'document_binding')
        need(documents['publication']==io.read_file(config['publication']) and ac['publication']==config['publication'],'publication_binding')
        lease=ac['lease'];need(keys(lease,('issued','expires','expires_utc','boot_id_sha256')) and finite(lease['issued']) and finite(lease['expires']) and 0<=lease['issued']<=now<=lease['expires'],'lease')
        need(ac['boot_id']['path']=='/proc/sys/kernel/random/boot_id' and ac['boot_id']['mode']==0o444,'boot_path');boot=io.read_file(ac['boot_id'],128);need(io.pin(boot)['sha256']==lease['boot_id_sha256'],'same_boot')
        wall=time.time();need(finite(wall) and wall<utc(lease['expires_utc']) and lease['expires']-current<=utc(lease['expires_utc'])-wall and (lease['expires']>=current+manager if scope['phase']=='parent' else lease['expires']>=current),'lease_coverage')
        funding=object_read(io,ac['funding'],2*1024*1024);need(ac['funding']['pin']==gate['funding_pin'],'funding_pin')
        fkeys={'schema','credits_only','main_active','services','ceiling_usd','reservation_usd','task_spend_upper_bound_usd','estimated_balance_usd','uncertainty_reserve_usd','other_reservations_usd','unreserved_lower_bound_usd','checked_utc','valid_until_utc','credit_expiry_utc','raw_proof'}
        need(keys(funding,fkeys) and funding['schema']=='root-marked-funding-proof-v1' and funding['credits_only'] is True and funding['main_active'] is True and io.canonical(funding['services'])==io.canonical(['EC2','VPC','DataTransfer']),'credit_eligibility')
        values={k:money(funding[k]) for k in ('ceiling_usd','reservation_usd','task_spend_upper_bound_usd','estimated_balance_usd','uncertainty_reserve_usd','other_reservations_usd','unreserved_lower_bound_usd')}
        need(values['ceiling_usd']==2000 and values['reservation_usd']==335 and values['unreserved_lower_bound_usd']==values['estimated_balance_usd']-values['uncertainty_reserve_usd']-values['other_reservations_usd'] and values['task_spend_upper_bound_usd']+335<=2000 and values['unreserved_lower_bound_usd']>=335,'conservative_credits')
        expiry=utc(funding['credit_expiry_utc']);need(datetime.fromtimestamp(expiry,timezone.utc).date().isoformat()=='2026-10-31' and utc(funding['checked_utc'])<=wall<utc(funding['valid_until_utc'])<=expiry and utc(lease['expires_utc'])<=utc(funding['valid_until_utc']),'funding_validity');file_spec(io,funding['raw_proof']);need(bool(io.read_file(funding['raw_proof'])),'credit_raw_evidence')
        resource=object_read(io,ac['resource'],2*1024*1024);need(keys(resource,RESOURCE_KEYS) and resource['schema']=='root-marked-resource-proof-v1','resource')
        for k in ('gate_sha256','source_pins','runtime_pin','input_pins','funding_pin'):need(resource[k]==scope[k],'resource_subjects')
        need(resource['runtime_subject_pin']==io.pin(io.canonical(config['runtime'])),'whole_runtime_subject')
        need(io.canonical(resource['approved_units'])==io.canonical(['eew-marked-'+gate['experiment_id']+'-%02d.service'%i for i in range(14)]) and io.canonical(resource['limits'])==io.canonical(LIMITS) and integer(resource['whole_seconds'],7200,7200) and resource['commands']==config['commands'] and resource['storage_limit_bytes']==config['storage_limit_bytes'] and resource['disk_directory']==config['store_directory'] and integer(resource['disk_reservation_bytes'],config['storage_limit_bytes'],2**40),'resource_limits')
        need(finite(resource['cost_deadline_monotonic']) and lease['expires']<=resource['cost_deadline_monotonic'] and lease['expires']<=gate['experiment_begin']+7200 and utc(lease['expires_utc'])<=utc(resource['automatic_stop_utc'])<=expiry and resource['boot_id_sha256']==lease['boot_id_sha256'],'stop_deadline');file_spec(io,resource['raw_control_proof']);need(bool(io.read_file(resource['raw_control_proof'])),'control_raw_evidence')
        fd=io.directory(config['store_directory'])
        try:space=os.fstatvfs(fd);need(space.f_bavail*space.f_frsize>=resource['disk_reservation_bytes'],'live_disk')
        finally:os.close(fd)
        publication=io.json_read(documents['publication']);pkeys={'schema','source_commit','source_pins','runtime_pin','adapter_manifest_pin','authority_source_pin','linux_proofs','published_proof'}
        need(keys(publication,pkeys) and publication['schema']=='root-marked-publication-proof-v1' and publication['source_commit']==resource['source_commit'] and type(publication['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',publication['source_commit']) and publication['source_pins']==scope['source_pins'] and publication['runtime_pin']==scope['runtime_pin'] and publication['adapter_manifest_pin']==config['sources']['adapters']['manifest']['pin'] and publication['authority_source_pin']==config['authority_source']['pin'],'publication_subjects')
        file_spec(io,config['authority_source']);io.read_file(config['authority_source'])
        need(type(publication['linux_proofs']) is list and len(publication['linux_proofs'])>=1,'linux_proofs')
        for s in publication['linux_proofs']:
            proof=object_read(io,s);need(proof['status']=='pass' and integer(proof['skip'],0,0) and integer(proof['fail'],0,0) and integer(proof['error'],0,0) and proof['source_pins']==scope['source_pins'] and proof['runtime_pin']==scope['runtime_pin'],'linux_exact')
        file_spec(io,publication['published_proof']);need(bool(io.read_file(publication['published_proof'])),'published_raw_evidence')
        # Supplemental RECORDs bind metadata here. ROOT's required vendor guard
        # hashes executable vendor bytes at import; no eager multi-GB tree claim.
        raw_sources={k:source_binding.source(s,k,lambda:need(clock()<=lease['expires'],'verification_expired')) for k,s in config['sources'].items()};source_binding.cross_copies(raw_sources);source_binding.runtime(config['runtime'],lambda:need(clock()<=lease['expires'],'verification_expired'))
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
        need(io.pin(io.canonical(config))==expected_deployment_config_pin,'config_changed')
        end=clock();need(finite(end) and end<=lease['expires'] and (end+manager<=lease['expires'] if scope['phase']=='parent' else True) and end+manager<=gate['experiment_begin']+7200,'end_deadline')
        wall_end=time.time();need(finite(wall_end) and utc(funding['checked_utc'])<=wall_end<min(utc(lease['expires_utc']),utc(funding['valid_until_utc']),expiry,utc(resource['automatic_stop_utc'])) and lease['expires']-end<=utc(lease['expires_utc'])-wall_end,'end_utc_validity')
        return dict(schema='root-marked-stage-authority-v1',scope=copy.deepcopy(scope),decision='authorized',expires=lease['expires'],evidence_pins=dict(publication=io.pin(documents['publication']),feature=io.pin(documents['feature_authority']),strong=io.pin(documents['strong_authority']),funding=gate['funding_pin']))
    return verify

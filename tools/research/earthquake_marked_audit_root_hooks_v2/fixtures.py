"""Invented authority proofs only. Kernel boot/time is mocked, all FS checks real."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import types

BASE=Path(__file__).parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def corpus(directory):
    load('validator',BASE/'reference/validator.py')
    oldfixtures=load('original_fixture',BASE/'reference/fixtures.py')
    c=oldfixtures.corpus(directory);io=c['io'];sb=c['sb'];original_put=c['put'];fixture_root=c['root']
    def put(raw,name=None,mode=0o400):
        if name is not None and (fixture_root/name).exists():(fixture_root/name).chmod(0o600)
        return original_put(raw,name,mode)
    c['put']=put
    original=c['config'];gate=c['gate'];ac0=c['ac'];root=c['root']
    original['bootstrap']=put(b'# invented positively bound bootstrap')
    original_config=put(original);old_ac=original['authority_config']
    hooksspec=put((BASE/'hooks.py').read_bytes(),'hooks.py');hooks=load('invented_hooks',Path(hooksspec['path']))
    sources=dict(v6=original['sources']['adapters'],native=original['sources']['native'])
    for role in ('auditor','wrapper','input_adapter','harness'):
        path=root/role;path.mkdir();src=put(b'# public invented '+role.encode(),role+'/module.py');manifest=put(dict(files={'module.py':src['pin']}),role+'/MANIFEST.json');sources[role]=dict(directory=str(path),files={'module.py':src['pin'],'MANIFEST.json':manifest['pin']},manifest=manifest,upload_manifest=None)
    controller=original['sources']['parent']['files']['controller.py'];gate_sha=io.pin(io.canonical(gate))['sha256'];stagefiles=[];held=[]
    for index in range(14):
        name='original_stages/stage_%02d'%index;directory=str(root/name)
        spec=hooks.stage_spec(gate,index);unit=spec['unit']
        claim=dict(schema='marked-sixfit-stage-request-v1',gate=gate,gate_sha256=gate_sha,stage=spec,previous={},dispatch_begin=100.)
        files={}
        for member in hooks.original_members(index):files[member]=put(dict(dummy='invented'),name+'/'+member)
        files['claim.json']=put(claim,name+'/claim.json')
        if index==0:
            files['result.json']=put(dict(source_pins={'operator':gate['source_pins']['operator'],'native_validator':gate['source_pins']['native'],'reference':gate['source_pins']['reference'],'processor':gate['source_pins']['processor'],'protocol':gate['source_pins']['protocol']}),name+'/result.json')
        if index>0 and index<13 and not index%2:files['result.json']=put(dict(predictions=[dict(source={}) for _ in range(66)]),name+'/result.json')
        child=dict(schema='marked-sixfit-child-report-v1',status='complete')
        files['child_report.json']=put(child,name+'/child_report.json')
        stream=dict(retained_hex='',original_pin=io.pin(b''),truncated=False)
        manager=dict(code=0,timeout=False,streams_complete=True,stdout=stream,stderr=stream,exception=None)
        files['manager_return.json']=put(manager,name+'/manager_return.json')
        files['post.json']=put(dict(unit=unit,result='success',active_state='inactive',control_group=''),name+'/post.json')
        closed=dict(schema='marked-sixfit-parent-return-v1',status='complete',index=index,unit=unit,gate_sha256=gate_sha,cleanup_verified=True,report_pin=files['child_report.json']['pin'],result_pin=files['result.json']['pin'],errors=[],no_retry=True,scientific_pass=None)
        files['closed.json']=put(closed,name+'/closed.json')
        launch=put(dict(schema='marked-stage-launch-v1',request=claim,config=original,expected_deployment_config_pin=io.pin(io.canonical(original))),name+'/bootstrap.json')
        held.append(dict(index=index,unit=unit,last_return=closed,directory=directory,files=dict({k:s['pin'] for k,s in files.items()},**{'bootstrap.json':launch['pin']})))
        stagefiles.append(files)
    execution=put(dict(schema='root-marked-original-fourteen-execution-v1',gate_sha256=gate_sha,controller_source_pin=controller,deployment_config_pin=io.pin(io.canonical(original)),bootstrap_source_pin=original['bootstrap']['pin'],source_commit='a'*40,stages=held,TEST_opened=False))
    context=dict(schema='root-marked-seven-audit-context-v1',original_execution_pin=execution['pin'])
    bundle=dict(schema='root-marked-audit-input-bundle-v1',binding_sha256='b'*64,wrapper_binding_sha256='d'*64,native={k:original['inputs'][k] for k in ('feature_archive','feature_manifest','feature_authority')},stronger={k:original['inputs'][k] for k in ('strong_results','strong_authority')},stages=stagefiles,previous_audits=[],root_context=context)
    template=put(bundle)
    manifests={k:s['manifest']['pin'] for k,s in sources.items()};runtimepin=io.pin(io.canonical(original['runtime']))
    rawcredit=dict(schema='eligible-AWS-main-credit-live-UI-proof-v1',account_shared=True,authorized_credit_only_ceiling_usd=2000,checked_utc='2026-10-13T11:59:00Z',conservative_task_reservation_usd=335,credit_reserved_by_provider=False,eligible_services=hooks.SERVICES,estimated_amounts_delayed_24_hours=True,main_credit_estimated_remaining_usd=5000.,main_credit_expiry='2026-10-31',main_credit_status='Active',same_account_default_cli_credentials_refreshed=True,screen='invented credit console',settled_incremental_task_spend_unknown=True,total_estimated_remaining_usd=5200.)
    funding=copy.deepcopy(io.json_read(io.read_file(ac0['funding'])));funding.update(uncertainty_reserve_usd=1500,other_reservations_usd=200,unreserved_lower_bound_usd=3300,valid_until_utc='2026-10-13T16:40:00Z',credit_expiry_utc='2026-10-31T00:00:00Z',raw_proof=put(rawcredit));fundingspec=put(funding)
    store=root/'auditstore';store.mkdir(mode=0o700);evidence=root/'root_last_returns';evidence.mkdir(mode=0o700)
    config=dict(schema='marked-seven-audit-deployment-v1',audit_id='invented-audit',study=hooks.STUDY,feature_schema=gate['feature_schema'],feature_study=gate['feature_study'],whole_begin=100.,lease_deadline=6000.,binding_sha256='b'*64,wrapper_binding_sha256='d'*64,sources=sources,runtime=original['runtime'],bundle_template=template,protocol=put(b'public audit protocol'),hooks_source=hooksspec,commands={},store_directory=str(store),storage_limit_bytes=7*64*1024*1024)
    common=dict(schema='root-seven-audit-source-runtime-proof-v1',status='pass',source_manifest_pins=manifests,runtime_subject_pin=runtimepin,hooks_source_pin=hooksspec['pin'],protocol_pin=config['protocol']['pin'])
    sourceproof=put(common);runtimeproof=put(common);linux=put(dict(status='pass',skip=0,fail=0,error=0,source_manifest_pins=manifests,runtime_subject_pin=runtimepin,hooks_source_pin=hooksspec['pin']))
    publication=put(dict(schema='root-seven-audit-publication-proof-v1',source_commit='c'*40,source_manifest_pins=manifests,runtime_subject_pin=runtimepin,hooks_source_pin=hooksspec['pin'],protocol_pin=config['protocol']['pin'],linux_proofs=[linux],published_proof=put(b'invented publication raw')));config['publication']=publication
    units=['eew-marked-invented-audit-%02d.service'%i for i in range(7)]
    script='#!/usr/bin/bash\n'+''.join('systemctl --user stop '+u+'\n' for u in units);script_spec=put(script.encode(),'stop.sh')
    stopraw=dict(schema='root-seven-audit-installed-stop-raw-v1',approved_units=units,commands={},boot_id_sha256=ac0['lease']['boot_id_sha256'],installed_begin_monotonic=100.,automatic_stop_utc='2026-10-13T16:30:00Z',observedraw_systemctl_timer='ActiveState=active\nTimersMonotonic={ OnActiveUSec=2h 3min 20s ; next_elapse=unknown }\nUnit=invented-stop.service\nAccuracyUSec=1s\n',observedraw_service='ActiveState=inactive\nExecStart={ argv[]=/usr/bin/bash '+script_spec['path']+' ; }\n',service_unit='invented-stop.service',exec_argv=['/usr/bin/bash',script_spec['path']],stop_script=script_spec,expected_stop_script=script)
    resource=put(dict(schema='root-seven-audit-resource-proof-v1',source_manifest_pins=manifests,runtime_subject_pin=runtimepin,funding_pin=fundingspec['pin'],publication_pin=publication['pin'],protocol_pin=config['protocol']['pin'],hooks_source_pin=hooksspec['pin'],binding_sha256=config['binding_sha256'],whole_begin=100.,lease_deadline=6000.,commands={},approved_units=units,limits=hooks.LIMITS,whole_seconds=7200,closure_seconds=200,disk_directory=str(store),disk_reservation_bytes=config['storage_limit_bytes'],cost_deadline_monotonic=7500.,automatic_stop_utc='2026-10-13T16:30:00Z',boot_id_sha256=ac0['lease']['boot_id_sha256'],raw_control_proof=put(stopraw)))
    lease=dict(issued=100.,expires=5000.,expires_utc='2026-10-13T15:00:00Z',boot_id_sha256=ac0['lease']['boot_id_sha256'])
    ac=dict(schema='root-marked-seven-audit-hooks-config-v1',funding=fundingspec,resource=resource,publication=publication,boot_id=ac0['boot_id'],lease=lease,original_config=original_config,original_authority=old_ac,original_execution=execution,last_return_evidence_directory=str(evidence),source_proof=sourceproof,runtime_proof=runtimeproof)
    config['hooks_config']=put(ac)
    scope=dict(schema='marked-seven-audit-authorization-scope-v1',config_pin=io.pin(io.canonical(config)),audit_id=config['audit_id'],study=hooks.STUDY,stage=0,unit=units[0],phase='parent',binding_sha256=config['binding_sha256'],bundle_pin=io.pin(io.canonical(bundle)),source_manifest_pins=manifests,runtime_subject_pin=runtimepin,publication_pin=publication['pin'],protocol_pin=config['protocol']['pin'],whole_begin=100.,lease_deadline=6000.)
    documents={k:io.read_file(config[k]) for k in ('publication','protocol','hooks_config')};documents['bundle']=io.canonical(bundle)
    return dict(c,config=config,ac=ac,scope=scope,documents=documents,bundle=bundle,hooks=hooks,execution=held,rawcredit=rawcredit,stopraw=stopraw)


def previous_stage(c):
    io=c['io'];put=c['put'];config=c['config'];root=c['root'];prefix='auditstore/stage_00';directory=root/prefix;directory.mkdir(mode=0o700)
    configpin=io.pin(io.canonical(config));unit='eew-marked-'+config['audit_id']+'-00.service'
    stage=dict(index=0,kind='audit_fit',seed=20261012,arm='S',source_seconds=900,manager_seconds=960,unit=unit,limits=c['hooks'].LIMITS)
    request=dict(schema='marked-seven-audit-request-v1',config_pin=configpin,stage=stage,dispatch_begin=200.,previous=[],bundle_spec=config['bundle_template'])
    files={}
    for name in ('bootstrap.json','dispatch.json','claim.json','return.json','raw_report_000.json','child_report.json','manager_return.json','post.json','closed.json'):
        files[name]=put({},prefix+'/'+name)
    files['dispatch.json']=put(request,prefix+'/dispatch.json')
    files['bootstrap.json']=put(dict(schema='marked-seven-audit-launch-v1',request=request,config=config,expected_config_pin=configpin),prefix+'/bootstrap.json')
    records=[dict(position=i,value=float(i)) for i in range(66)]
    source_sha=io.pin(io.canonical({}))['sha256']
    for i,record in enumerate(records):files['record_%03d.json'%i]=put(dict(position=i,status='pass',errors={},work={},source_sha256=source_sha,fresh=record),prefix+'/record_%03d.json'%i)
    report=dict(status='pass',checked=66,records=records)
    files['raw_report_000.json']=put(report,prefix+'/raw_report_000.json')
    size=sum(s['pin']['bytes'] for n,s in files.items() if n.startswith('record_'))+files['raw_report_000.json']['pin']['bytes']
    returned=dict(status='complete',retained_count=67,attempted_count=67,retained_bytes=size)
    files['return.json']=put(returned,prefix+'/return.json')
    child=dict(schema='marked-seven-audit-child-report-v1',status='complete',stage=0,config_pin=configpin,request_pin=io.pin(io.canonical(request)),return_pin=files['return.json']['pin'],report_pin=files['raw_report_000.json']['pin'],claim_pin=files['claim.json']['pin'],within_source=True)
    files['child_report.json']=put(child,prefix+'/child_report.json')
    stream=dict(retained_hex='',retained_pin=io.pin(b''),truncated=False)
    meta=dict(original_bytes=0,original_sha256=io.pin(b'')['sha256'],retained_bytes=0,truncated=False,complete_observation=True)
    manager=dict(code=0,timeout=False,streams_complete=True,exception=None,stdout=stream,stderr=stream,stream_custody=dict(stdout=meta,stderr=meta))
    files['manager_return.json']=put(manager,prefix+'/manager_return.json')
    post=dict(unit=unit,result='success',active_state='inactive',control_group='')
    files['post.json']=put(post,prefix+'/post.json')
    closed=dict(schema='marked-seven-audit-manager-return-v1',status='complete',stage=0,unit=unit,config_pin=configpin,cleanup_verified=True,child_report_pin=files['child_report.json']['pin'],return_pin=files['return.json']['pin'],report_pin=files['raw_report_000.json']['pin'],errors=[],no_retry=True)
    files['closed.json']=put(closed,prefix+'/closed.json')
    projected={key:files[name] for key,name in dict(claim='claim.json',return_='return.json',report='raw_report_000.json',closed='closed.json').items()};projected['return']=projected.pop('return_')
    held=dict(schema='root-seven-audit-last-return-v1',stage=0,config_pin=configpin,directory=str(directory),files={k:s['pin'] for k,s in projected.items()},inventory={k:s['pin'] for k,s in files.items()},last_return=closed,root_observation=post,root_manager=manager)
    evidence=put(held,'root_last_returns/stage_00.private.json')
    bundle=copy.deepcopy(c['bundle']);bundle['previous_audits']=[projected]
    c['documents']['bundle']=io.canonical(bundle);c['scope'].update(stage=1,unit='eew-marked-'+config['audit_id']+'-01.service',bundle_pin=io.pin(c['documents']['bundle']))
    return dict(held=held,evidence=evidence,files=files,bundle=bundle)

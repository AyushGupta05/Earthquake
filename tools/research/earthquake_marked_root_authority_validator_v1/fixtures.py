"""Invented proof chain only. Kernel boot-id is mocked; live temp FS is real."""
from pathlib import Path
import base64,copy,importlib.util,json,os,sys,time
import validator as v

BASE=Path(__file__).parent


def corpus(directory):
    root=Path(directory).resolve();counter=[0]
    # Positively read real copied stdlib helpers in the synthetic adapter group.
    ad=root/'adapters';ad.mkdir();mods={}
    for name in ('secure_io','vendor_inventory','source_binding'):
        path=ad/(name+'.py');path.write_bytes((BASE/'reference'/(name+'.py')).read_bytes());path.chmod(0o400);s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);mods[name]=m
    io=mods['secure_io'];sb=mods['source_binding'];boot=b'11111111-1111-1111-1111-111111111111\n';io._original_read_file=io.read_file;io._invented_boot=boot
    # Only kernel boundary mocked, explicit pin/mode verification still required.
    exec("def read_file(spec,cap=16*1024*1024):\n if spec['path']=='/proc/sys/kernel/random/boot_id':\n  need(spec['mode']==0o444 and pin(_invented_boot)==spec['pin'] and len(_invented_boot)<=cap,'invented_boot_pin');return _invented_boot\n return _original_read_file(spec,cap)\n",io.__dict__)
    def put(raw,name=None,mode=0o400):
        if name is None:counter[0]+=1;name='doc_%03d.json'%counter[0]
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);b=raw if isinstance(raw,bytes) else io.canonical(raw);p.write_bytes(b);p.chmod(mode);return dict(path=str(p),pin=io.pin(b),mode=mode)
    def group(role,count,names):
        d=ad if role=='adapters' else root/role;d.mkdir(exist_ok=True);files={}
        for name in names:
            p=d/name;p.parent.mkdir(parents=True,exist_ok=True)
            if not p.exists():p.write_bytes(b'# invented scientific source\n');p.chmod(0o400)
            files[name]=io.pin(p.read_bytes())
        while len(files)<count-1:
            name='doc%d.txt'%len(files);p=d/name;p.write_bytes(b'public invented');p.chmod(0o400);files[name]=io.pin(p.read_bytes())
        manifest=put(dict(files=files),role+'/MANIFEST.json');files['MANIFEST.json']=manifest['pin'];return dict(directory=str(d),files=files,manifest=manifest,upload_manifest=None)
    sources=dict(processor=group('processor',32,['reference/gaussian_operator.py','reference/reference_core.py','reference/marked_native.py','reference/native_packet_io.py']),gaussian=group('gaussian',34,['gaussian_operator.py','reference_core.py']),native=group('native',22,['marked_native.py','packet_io.py']),parent=group('parent',32,['controller.py']),adapters=group('adapters',4,['secure_io.py','vendor_inventory.py','source_binding.py']))
    prefix=root/'runtime';lib=prefix/'venv/lib';lib.mkdir(parents=True);members={}
    for i in range(10112):
        p=lib/('x%05d'%i);p.write_bytes(b'x');p.chmod(0o444);members[p.relative_to(prefix).as_posix()]=io.pin(b'x')
    critical={}
    for i in range(10):s=put(b'public critical','critical/x%d'%i,0o775 if i%2 else 0o664);critical[s['path']]=dict(s['pin'],mode=s['mode'])
    (prefix/'venv/bin').mkdir();links={'venv/bin/python':'python3','venv/bin/python3':'../../critical_placeholder','venv/bin/python3.9':'python3','venv/lib64':'lib'};links['venv/bin/python3']='../../../critical/x0'
    for n,target in links.items():os.symlink(target,prefix/n)
    vendor_root=root/'vendor_site';vendor_root.mkdir();vf=put(b'# invented vendor source\n','vendor_site/toy.py',0o664);digest=base64.urlsafe_b64encode(bytes.fromhex(vf['pin']['sha256'])).decode().rstrip('=');record=put(('toy.py,sha256='+digest+','+str(vf['pin']['bytes'])+'\n').encode(),'vendor_site/toy-1.0.dist-info/RECORD',0o664)
    vendor=put(dict(schema='marked-supplemental-vendor-inventory-v1',roots=[str(vendor_root)],records={'toy-1.0.dist-info':record},files={vf['path']:dict(vf['pin'],mode=vf['mode'],record_id='toy-1.0.dist-info',record_path='toy.py')}))
    runtime=dict(directory=str(prefix),manifest=put(dict(files=members)),symlinks=put(dict(symlinks=links)),critical=critical,python=str(prefix/'venv/bin/python'),versions={},regular_mode=0o444,vendor_inventory=vendor)
    source_pins=dict(processor=sources['processor']['manifest']['pin'],operator=sources['gaussian']['manifest']['pin'],reference=sources['gaussian']['manifest']['pin'],native=sources['native']['manifest']['pin'],parent=sources['parent']['manifest']['pin'],protocol=put(b'public frozen protocol')['pin'])
    rows=[dict(ordinal=i if i<65 else i+26,partition='TRAIN' if i<65 else 'DEV',mw=6.0,group=i if i<65 else i+26,horizons=[1,3,5]) for i in range(87)];dev=rows[65:]
    original_specs=dict(archive=put(b'original numeric archive'),manifest=put(b'original numeric manifest'));original_pins={k:s['pin'] for k,s in original_specs.items()};oid=v.original_id(io,original_pins);fits=[]
    for seed,arm in v.OLD_ORDER:
        predictions=[]
        for row in dev:
            for h in (1,3,5):
                p=dict(ordinal=row['ordinal'],horizon=h,target=row['mw'],group=row['group'],mean=5.0,median=5.0,nll=1.0,crps=.5,pit=.5,coverage_50=True,coverage_80=True,coverage_95=True)
                if arm in ('H','T','C'):p['quantiles']={str(x):float(x+5) for x in (.025,.1,.25,.5,.75,.9,.975)}
                predictions.append(p)
        fits.append(dict(seed=seed,arm=arm,status='complete',predictions=predictions,metrics={},strata={},extreme_cases=[]))
    wrapped=dict(schema='receiver-batched-score-stage-report-v1',index=10,stage='aggregate',within_budget=True,outcomes={},binding=dict(packet_pins=original_pins,source_commit='a'*40),report=dict(schema='earthquake-TRAIN115-renewal-score-audit-v3',status='pass',reasons=[],fits=fits,comparisons=[{}]*24,advance=dict(pass_all=False),recomputed_advance=dict(pass_all=False),diagnostics={}))
    whole_result=put(wrapped,'whole/stage_report.private.json');whole_closure=put(dict(schema='root-full-receiver-score-closure-v1',**{k:True for k in v.CLOSED_FLAGS},complete_stages=11,fits=10,independent_probability_records=660,new_optimizer_steps=0,TEST_opened=False,frozen_source_commit='a'*40,aggregate_report_pin=whole_result['pin'],scientific_advance=False))
    def closed(path,schema,files,**extra):
        return put(dict(schema=schema,status='complete',unit_exit=0,owned_unit_inactive=True,owned_cgroup_empty=True,no_retry=True,files=files,total_bytes=sum(p['bytes'] for p in files.values()),**extra),path)
    whole_parent=closed('whole/parent_return.private.json','receiver-batched-score-parent-return-v1',{'stage_report.private.json':whole_result['pin']},stage='aggregate',index=10,audit_status='pass')
    checkpoints=[];origins=[];oldfits=[]
    for pair in v.STRONG_ORDER:
        fit=fits[v.OLD_ORDER.index(pair)];cp=put(b'original final checkpoint');source=put(b'original frozen source manifest');sr=put(dict(schema='receiver-batched-score-stage-report-v1',stage='fit',within_budget=True,report=dict(schema='receiver-fit-score-audit-v1',status='pass',complete=True,reasons=[],fit=fit)))
        d=dict(seed=pair[0],arm=pair[1],checkpoint=cp,fit_report=sr,source_pin=source['pin'],source_spec=source);checkpoints.append(d);origins.append(dict(seed=pair[0],arm=pair[1],checkpoint_pin=cp['pin'],result_pin=sr['pin'],source_pin=source['pin'],closure_pin=whole_result['pin']))
        oldfits.append(dict(seed=pair[0],arm=pair[1],status='complete',no_optimizer=True,packet_sha256=oid,checkpoint_sha256=cp['pin']['sha256'],result_pin=sr['pin'],independent_closure=dict(verified=True,no_optimizer=True,packet_sha256=oid,checkpoint_sha256=cp['pin']['sha256'],source_sha256=source['pin']['sha256'],proof_pin=whole_result['pin']),predictions=[dict(p,seed=pair[0],arm=pair[1],status='complete') for p in fit['predictions']]))
    strong_results=put(dict(schema='root-original-strong-comparison-input-v1',original_packet_pins=original_pins,original_packet_sha256=oid,roster=rows,fits=oldfits));strong=put(dict(schema='root-original-strong-authority-v1',whole_closure_pin=whole_closure['pin'],whole_result_pin=whole_result['pin'],whole_parent_pin=whole_parent['pin'],original_packet_pins=original_pins,original_packet_sha256=oid,roster=rows,origins=origins))
    archive=put(b'invented marked numeric archive','build/features.private.npz');manifest=put(b'invented marked numeric manifest','build/features_manifest.private.json');build_result=put(dict(status='complete',archive_pin=archive['pin'],manifest_pin=manifest['pin'],events=115,horizon_cells=345,fit_authorized=False),'build/result.private.json');audit_result=put(dict(status='complete',fit_authorized=False,audit=dict(schema='marked-native-independent-semantic-audit-v1',semantic_agreed=True,allpositive_pilot_admission=True,fit_authorized=False,events=115,horizon_cells=345,common_train=65,common_dev=22)),'audit/result.private.json');prep_result=put(dict(status='complete'),'prepare/result.private.json')
    native_returns=[closed('prepare/parent_return.private.json','marked-native-root-preparation-return-v1',{'result.private.json':prep_result['pin']}),closed('build/parent_return.private.json','marked-native-parent-return-v1',{'features.private.npz':archive['pin'],'features_manifest.private.json':manifest['pin'],'result.private.json':build_result['pin']},stage='build',input_fingerprint='f'*64),closed('audit/parent_return.private.json','marked-native-parent-return-v1',{'result.private.json':audit_result['pin']},stage='audit',input_fingerprint='f'*64)]
    feature=put(dict(schema='root-marked-native-feature-authority-v1',feature_schema='earthquake-TRAIN115-marked-noise-observations-v1',feature_study='earthquake-TRAIN115-marked-noise-study-v1',events=115,horizon_cells=345,common_train=65,common_dev=22,allpositive=True,archive_pin=archive['pin'],manifest_pin=manifest['pin'],packet_sha256='b'*64,roster=rows,native_return_pins=[s['pin'] for s in native_returns]))
    inputs=dict(feature_archive=archive,feature_manifest=manifest,feature_authority=feature,strong_authority=strong,strong_results=strong_results);wall=v.utc('2026-10-13T12:00:00Z');funding=put(dict(schema='root-marked-funding-proof-v1',credits_only=True,main_active=True,services=['EC2','VPC','DataTransfer'],ceiling_usd=2000,reservation_usd=335,task_spend_upper_bound_usd=200,estimated_balance_usd=5000,uncertainty_reserve_usd=100,other_reservations_usd=200,unreserved_lower_bound_usd=4700,checked_utc='2026-10-13T11:59:00Z',valid_until_utc='2026-10-13T14:00:00Z',credit_expiry_utc='2026-10-31T23:59:59Z',raw_proof=put(b'invented ROOT credit/ledger inspection')))
    gate=dict(schema='marked-sixfit-parent-gate-v1',study='earthquake-TRAIN115-marked-noise-fitting-v2',feature_schema='earthquake-TRAIN115-marked-noise-observations-v1',feature_study='earthquake-TRAIN115-marked-noise-study-v1',experiment_id='invented',experiment_begin=100.,source_pins=source_pins,runtime_pin=runtime['manifest']['pin'],input_pins={k:s['pin'] for k,s in inputs.items()},funding_pin=funding['pin'],storage_limit_bytes=2*1024*1024)
    gate_spec=put(gate);store=root/'store';store.mkdir(mode=0o700);commands={};resource=put(dict(schema='root-marked-resource-proof-v1',gate_sha256=io.pin(io.canonical(gate))['sha256'],source_pins=source_pins,runtime_pin=gate['runtime_pin'],runtime_subject_pin=io.pin(io.canonical(runtime)),input_pins=gate['input_pins'],funding_pin=funding['pin'],source_commit='c'*40,approved_units=['eew-marked-invented-%02d.service'%i for i in range(14)],limits=v.LIMITS,whole_seconds=7200,disk_directory=str(store),disk_reservation_bytes=4*1024*1024,cost_deadline_monotonic=5000.,automatic_stop_utc='2026-10-13T14:00:00Z',raw_control_proof=put(b'invented ROOT installed stop controller'),commands=commands,storage_limit_bytes=gate['storage_limit_bytes'],boot_id_sha256=io.pin(boot)['sha256']))
    linux=put(dict(status='pass',skip=0,fail=0,error=0,source_pins=source_pins,runtime_pin=gate['runtime_pin']));authority_source=put((BASE/'validator.py').read_bytes(),'root_validator.py');publication=put(dict(schema='root-marked-publication-proof-v1',source_commit='c'*40,source_pins=source_pins,runtime_pin=gate['runtime_pin'],adapter_manifest_pin=sources['adapters']['manifest']['pin'],authority_source_pin=authority_source['pin'],linux_proofs=[linux],published_proof=put(b'invented ROOT publication inspection')))
    ac=dict(schema='root-marked-authority-config-v1',original_packet=original_specs,gate=gate_spec,funding=funding,resource=resource,publication=publication,native_returns=native_returns,whole_result=whole_result,whole_audit=whole_parent,whole_closure=whole_closure,checkpoints=checkpoints,lease=dict(issued=100.,expires=4000.,expires_utc='2026-10-13T13:59:00Z',boot_id_sha256=io.pin(boot)['sha256']),boot_id=dict(path='/proc/sys/kernel/random/boot_id',pin=io.pin(boot),mode=0o444));acspec=put(ac)
    config=dict(sources=sources,runtime=runtime,inputs=inputs,protocol=dict(pin=source_pins['protocol']),publication=publication,authority_source=authority_source,authority_config=acspec,commands=commands,store_directory=str(store),storage_limit_bytes=gate['storage_limit_bytes'])
    scope=dict(gate_sha256=io.pin(io.canonical(gate))['sha256'],config_pin=io.pin(io.canonical(config)),index=0,unit='eew-marked-invented-00.service',source_pins=source_pins,runtime_pin=gate['runtime_pin'],input_pins=gate['input_pins'],funding_pin=gate['funding_pin'],publication_pin=publication['pin'],phase='parent');documents={k:io.read_file(inputs[k]) for k in ('feature_authority','strong_authority','strong_results')};documents['publication']=io.read_file(publication)
    return dict(root=root,io=io,sb=sb,config=config,scope=scope,documents=documents,wall=wall,ac=ac,put=put,gate=gate)

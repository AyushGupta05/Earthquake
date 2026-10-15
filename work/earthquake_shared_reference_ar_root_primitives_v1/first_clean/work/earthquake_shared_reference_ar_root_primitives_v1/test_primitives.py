"""Invented stdlib-only fixtures; no cloud, scientific data or financial records."""
import copy
import importlib.util
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest

HERE=Path(__file__).resolve().parent
REF=HERE.parent/'earthquake_shared_reference_ar_runtime_adapter_v1/reference'
EXEC=HERE.parent/'earthquake_shared_reference_ar_execution_v1'
sys.path.insert(0,str(REF))
import secure_io as io
import source_binding as sb
sys.path.insert(0,str(EXEC))
import control as c
import journal
_sd_spec=importlib.util.spec_from_file_location('invented_frozen_systemd',EXEC/'reference/systemd_adapter.py')
sd=importlib.util.module_from_spec(_sd_spec);_sd_spec.loader.exec_module(sd)
import root_primitives as p


def put(path,value,raw=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    body=value if raw else io.canonical(value)
    if path.exists():path.chmod(0o600)  # invented fixture reconfiguration only
    path.write_bytes(body);path.chmod(0o400)
    return dict(path=str(path),pin=io.pin(body),mode=0o400)


def transport(stdout=b'ok',stderr=b''):
    return dict(code=0,timeout=False,stdout=stdout,stderr=stderr,streams_complete=True,exception=None,
                stream_custody={k:dict(original_bytes=len(v),original_sha256=io.pin(v)['sha256'],retained_bytes=len(v),truncated=False,complete_observation=True) for k,v in [('stdout',stdout),('stderr',stderr)]})


def saved(answer):
    out={k:copy.deepcopy(answer[k]) for k in ('code','timeout','streams_complete','exception','stream_custody')}
    out.update({k:dict(retained_hex=answer[k].hex(),retained_pin=io.pin(answer[k]),truncated=False) for k in ('stdout','stderr')})
    return out


def invented_history(root):
    """Actual old wire shapes, invented bytes; unbound helper context only."""
    root=Path(root).resolve();root.mkdir(mode=0o700);pin=io.pin(b'old source');oldpins={k:pin for k in p.OLD}
    parentdir=root/'old_parent';parentdir.mkdir(mode=0o700)
    specs={}
    for n in ['controller.py']+['inert_%02d.py'%i for i in range(30)]:specs[n]=put(parentdir/n,b'# invented inert source\n',True)['pin']
    manifest=put(parentdir/'MANIFEST.json',dict(files=specs))
    profile=dict(directory=str(parentdir),files=dict(specs,**{'MANIFEST.json':manifest['pin']}),manifest=manifest,upload_manifest=None)
    boot_source=put(root/'old_bootstrap.py',b'# invented old bootstrap\n',True)
    config=dict(sources={'parent':profile},bootstrap=boot_source)
    configpin=io.pin(io.canonical(config))
    gate=dict(schema='marked-sixfit-parent-gate-v1',source_pins=dict(processor=pin,operator=pin,native=pin,reference=pin,protocol=pin,parent=manifest['pin']))
    gate_sha=io.pin(io.canonical(gate))['sha256'];stages=[];scorepins=[];adpin=None
    for index in range(14):
        d=root/('old_%02d'%index);d.mkdir(mode=0o700);unit='eew-marked-invented-old-%02d.service'%index
        request=dict(schema='marked-sixfit-stage-request-v1',gate=gate,gate_sha256=gate_sha,stage={'index':index},authority={},dispatch_begin=1.,previous={})
        result=put(d/'result.json',dict(status='admitted' if index==0 else 'complete',ordinal=index));resultpin=result['pin']
        if index==0:adpin=resultpin
        if index in (2,4,6,8,10,12):scorepins.append(resultpin)
        bootstrap=put(d/'bootstrap.json',dict(schema='marked-stage-launch-v1',config=config,expected_deployment_config_pin=configpin,request=request))
        put(d/'claim.json',request)
        child=dict(schema='marked-sixfit-child-report-v1',callbacks=[],exception_evidence_pin=None,failure=None,gate_sha256=gate_sha,index=index,request_pin=io.pin(io.canonical(request)),result_pin=resultpin,status='complete',within_experiment=True,within_source=True)
        childspec=put(d/'child_report.json',child)
        closed=dict(schema='marked-sixfit-parent-return-v1',cleanup_verified=True,errors=[],gate_sha256=gate_sha,index=index,no_retry=True,report_pin=childspec['pin'],result_pin=resultpin,scientific_pass=None,status='complete',unit=unit)
        put(d/'closed.json',closed)
        a=transport();a.pop('stream_custody');a.update({k:dict(original_pin=io.pin(a[k]),retained_hex=a[k].hex(),truncated=False) for k in ('stdout','stderr')})
        put(d/'manager_return.json',a);put(d/'post.json',dict(active_state='inactive',control_group='',result='success',unit=unit))
        stages.append(dict(directory=str(d),files=p.tree(io,str(d)),index=index,last_return=closed,unit=unit))
    oldmeta=put(root/'original14.json',dict(schema='root-marked-original-fourteen-execution-v1',TEST_opened=False,bootstrap_source_pin=boot_source['pin'],controller_source_pin=specs['controller.py'],deployment_config_pin=configpin,gate_sha256=gate_sha,source_commit='0'*40,stages=stages))
    audit_specs=[];fullpin=None
    for index in range(7):
        d=root/('audit_%02d'%index);d.mkdir(mode=0o700);unit='eew-marked-invented-audit-%02d.service'%index
        request=dict(schema='marked-seven-audit-request-v1',stage={'index':index});dispatch=put(d/'dispatch.json',request);claim=put(d/'claim.json',dict(stage=index))
        report=dict(schema='marked-sixfit-independent-audit-v1',status='pass',checked=66,records=[{}]*66,seed=(20261012,20261013)[index//3] if index<6 else None,arm=('S','P','D')[index%3] if index<6 else None)
        if index==6:report=dict(schema='marked-sixfit-independent-aggregate-v1',status='pass',fits=[dict(records=[{}]*66)]*6,stronger=[dict(records=[{}]*66)]*8)
        rspec=put(d/'raw_report_000.json',report);returned=put(d/'return.json',dict(status='complete',stage=index))
        if index==6:fullpin=rspec['pin']
        child=dict(schema='marked-seven-audit-child-report-v1',claim_pin=claim['pin'],config_pin=configpin,report_pin=rspec['pin'],request_pin=dispatch['pin'],return_pin=returned['pin'],stage=index,status='complete',within_source=True)
        chspec=put(d/'child_report.json',child)
        closed=dict(schema='marked-seven-audit-manager-return-v1',child_report_pin=chspec['pin'],cleanup_verified=True,config_pin=configpin,errors=[],no_retry=True,report_pin=rspec['pin'],return_pin=returned['pin'],stage=index,status='complete',unit=unit)
        cspec=put(d/'closed.json',closed);manager=saved(transport());put(d/'manager_return.json',manager);post=dict(active_state='inactive',control_group='',result='success',unit=unit);put(d/'post.json',post)
        audit_specs.append(put(root/('known_audit_%02d.json'%index),dict(schema='root-seven-audit-last-return-v1',config_pin=configpin,directory=str(d),files=dict(claim=claim,closed=cspec,report=rspec,**{'return':returned}),inventory=p.tree(io,str(d)),last_return=closed,root_manager=manager,root_observation=post,stage=index)))
    context=SimpleNamespace(io=io,h=dict(loader=dict(original_source_pins=oldpins),facts=dict(original_execution_closure_sha256=oldmeta['pin']['sha256']),history=dict(reused_scores=[dict(spec={'pin':x}) for x in scorepins])),g=dict(input_pins=dict(original_admission=adpin,closed_comparator_report=fullpin)),modules={'source_binding':sb},c=c,check=lambda:100.,input_paths=set(),input_directories={},input_profiles=[])
    return context,dict(original_execution=oldmeta,independent_returns=audit_specs)


class Fixture:
    def __init__(self,root):
        self.root=Path(root).resolve();self.now=100.;self.boot='12345678-1234-1234-1234-123456789abc'
        self.store=self.root/'journal';self.store.mkdir(mode=0o700)
        self.returns=self.root/'returns';self.returns.mkdir(mode=0o700)
        self.pin=io.pin(b'invented')
        self.old={k:self.pin for k in p.OLD};self.new={k:self.pin for k in p.ROLES}
        g=dict(schema='shared-reference-AR-L-nine-stage-config-v1',study=c.STUDY,
               feature_schema='earthquake-TRAIN115-marked-noise-observations-v1',feature_study='earthquake-TRAIN115-marked-noise-study-v1',
               experiment_id='invented-l-test',whole_begin=0.,lease_deadline=7400.,source_pins={k:self.pin for k in c.SOURCES},runtime_pin=self.pin,
               input_pins={k:self.pin for k in c.INPUTS},funding_pin=self.pin,publication_pin=self.pin,protocol_pin=io.pin(b'protocol'),storage_limit_bytes=9*64*1024*1024)
        static={k:g[k] for k in p.STATIC_SCOPE}
        credit=put(self.root/'raw_credit.json',dict(schema='root-live-eligible-credit-refresh-v1',terms='synthetic only'))
        eligibility=put(self.root/'eligibility.json',dict(schema='root-L-credit-window-v1',scope=static,expires=7400.,eligible_services=['Amazon Elastic Compute Cloud'],raw_credit_readback=credit))
        funding=put(self.root/'funding.json',dict(schema='root-L-funding-reservation-v1',scope=static,expires=7400.,task_ceiling_cents=100000,reservation_cents=20000,spent_upper_cents=1000,future_upper_cents=1000,eligible_credit_cents=50000,other_reserved_cents=1000,eligibility=eligibility))
        publication=put(self.root/'publication.json',dict(schema='root-L-publication-authority-v1',scope=static,expires=7400.))
        g['funding_pin']=funding['pin'];g['publication_pin']=publication['pin'];self.g=g;self.gpin=io.pin(io.canonical(g))
        self.loader=dict(runtime={'python':'/invented/python'},original_source_pins=self.old);loaderpin=io.pin(io.canonical(self.loader))
        provider=put(self.root/'resource_readback.json',dict(schema='root-scoped-aws-readonly-refresh-v1',checked_utc='invented',no_resource_start_or_change=True,
                     raw=dict(account={},instances={},owned_volumes={},quota={'Quota':{'Value':16}},running_G_VT={'Reservations':[{'Instances':[dict(State={'Name':'running'},InstanceType='g5.xlarge',CpuOptions={'CoreCount':2,'ThreadsPerCore':2})]}]})))
        quota=put(self.root/'quota.json',dict(schema='root-L-quota-window-v1',scope=static,expires=7400.,limit_vcpu=16,used_vcpu=4,additional_vcpu=0,resource_readback=provider))
        resources=put(self.root/'resources.json',dict(schema='root-L-resource-reservation-v1',execution_pin=self.gpin,boot_id=self.boot,whole_begin=0.,science_deadline=7200.,closure_deadline=7400.,expires=7400.,limits=c.LIMITS,quota=quota))
        storage=put(self.root/'storage.json',dict(schema='root-L-storage-reservation-v1',execution_pin=self.gpin,directory=str(self.store),reserved_bytes=g['storage_limit_bytes'],minimum_free_bytes=g['storage_limit_bytes']))
        current=put(self.root/'current.json',dict(schema='root-L-current-proof-v1',execution_pin=self.gpin,boot_id=self.boot,expires=7400.,retention_directory=str(self.returns),timer=dict(unit='invented-whole.timer',service='invented-whole.service',exec_start='invented-stop-command',deadline=7400.),resources=resources,storage=storage))
        sr=put(self.root/'source.json',dict(schema='root-L-source-runtime-proof-v1',execution_pin=self.gpin,loader_pin=loaderpin,runtime_spec_pin=io.pin(io.canonical(self.loader['runtime'])),source_pins=g['source_pins'],boot_id=self.boot))
        command=put(self.root/'systemctl',b'invented executable bytes',True)
        self.h=dict(schema='root-held-L-composition-v1',execution=g,execution_pin=self.gpin,loader=self.loader,loader_pin=loaderpin,
                    inputs={},history={},documents=dict(funding=funding,publication=publication,protocol=put(self.root/'protocol',b'protocol',True),root_context=put(self.root/'context.json',{})),
                    evidence=dict(source_runtime=sr,current=current,inputs=put(self.root/'inputs.json',{}),projection=put(self.root/'projection.json',{}),audit=put(self.root/'audit.json',{})),
                    facts=dict(packet_sha256='a'*64,original_execution_closure_sha256='b'*64),launch=dict(store_directory=str(self.store),commands=dict(systemctl=command,systemd_run=command)))
        outer=self
        class ReadSystemd:
            def __init__(self,*args):pass
            def own(self,u):pass
            def available(self,u):outer.available.append(u)
        self.available=[]
        def process(args,timeout):
            unit=args[3];names=[args[i+1] for i,x in enumerate(args) if x=='-p']
            if unit.endswith('.timer'):values=dict(ActiveState='active',Unit='invented-whole.service',NextElapseUSecMonotonic='2h 3min 20s')
            elif unit=='invented-whole.service':values=dict(ExecStart='invented-stop-command',LoadState='loaded')
            else:values=dict(Result='success',ActiveState='inactive',ControlGroup='')
            return transport(('\n'.join(n+'='+values[n] for n in names)+'\n').encode())
        fake_sd=SimpleNamespace(live_read=lambda *_:self.boot.encode(),process=process,properties=sd.properties,Systemd=ReadSystemd)
        self.modules=dict(secure_io=io,control=c,journal=journal,source_binding=sb,systemd_adapter=fake_sd)
        self.rebind()
    def rebind(self):
        spec=put(self.root/'root.json',self.h)
        self.p,self.custody=p.make_primitives(self.h,expected_root_pin=spec['pin'],root_spec=spec,modules=self.modules,clock=lambda:self.now)
    def current(self,index=0,phase='parent'):
        scope=c.scope(self.g,c.spec(self.g,index),phase)
        docs={k:Path(v['path']).read_bytes() for k,v in self.h['documents'].items()}
        return self.p.current(scope,self.h,docs,Path(self.h['evidence']['current']['path']).read_bytes(),self.now)
    def stage(self,index=0,status='complete',payload=None,extra=None,callbacks=None):
        j=journal.Journal(str(self.store));s=c.spec(self.g,index)
        proofs=dict(source=io.pin(io.canonical(self.g['source_pins'])),runtime=self.g['runtime_pin'],native=self.g['input_pins']['feature_authority'],original_initialization=self.g['input_pins']['original_admission_authority'],reused924=self.g['input_pins']['comparator_authority'],resources=self.pin,storage=self.pin)
        def receipt(phase):return dict(schema='root-shared-reference-AR-L-stage-authority-v1',scope=c.scope(self.g,s,phase),decision='authorized',expires=7400.,proofs=proofs)
        request=dict(schema='shared-reference-AR-L-stage-request-v1',config=self.g,config_pin=self.gpin,stage=s,dispatch_begin=100.,previous=[],parent_authority=receipt('parent'))
        j.object(index,'dispatch.json',request)
        claim=dict(schema='shared-reference-AR-L-child-claim-v1',stage=index,request_pin=io.pin(io.canonical(request)),config_pin=self.gpin,authority=receipt('child'));j.object(index,'claim.json',claim)
        result=dict(status='admitted',study=c.STUDY) if payload is None else payload;j.object(index,'result.json',result)
        for name,value in (extra or {}).items():j.object(index,name,value)
        child=dict(schema='shared-reference-AR-L-child-report-v1',stage=index,config_pin=self.gpin,request_pin=io.pin(io.canonical(request)),status=status,result_pin=io.pin(io.canonical(result)),claim_pin=io.pin(io.canonical(claim)),within_source=True,within_experiment=True,callbacks=callbacks or [],failure=None,exception_evidence_pin=None)
        j.object(index,'child_report.json',child);answer=transport();j.object(index,'manager_return.json',saved(answer));j.object(index,'post.json',dict(unit=s['unit'],result='success',active_state='inactive',control_group=''))
        returned=dict(schema='shared-reference-AR-L-parent-return-v1',status=status,stage=index,unit=s['unit'],config_pin=self.gpin,cleanup_verified=True,child_report_pin=io.pin(io.canonical(child)),result_pin=io.pin(io.canonical(result)),claim_pin=io.pin(io.canonical(claim)),errors=[] if status=='complete' else ['invented failure'],no_retry=True)
        j.object(index,'closed.json',returned)
        return j,returned,answer,request

    def audit_fixture(self,bad_final_pin=False):
        """Unit audit context only; synthetic cache stands for checked input tests.

        This does not invoke/claim native authentication or numerical validity.
        It exercises the concrete audit's actual retained-stage/300-step graph.
        """
        array=lambda x:{'__array__':'<f8','shape':[],'hex':struct.pack('<d',x).hex()}
        names=['coefficients','prior.first_bias','prior.second.weight','prior.second.bias','prior.head.weight','prior.head.bias']
        parameters={k:array(0.) for k in names}
        probe=dict(events=65,horizons=3,terms=195,used=6,total=6,masks={k:{'__array__':'|u1','shape':[],'hex':'01'} for k in names})
        order={'__array__':'<i8','shape':[300,8],'hex':struct.pack('<2400q',*(list(range(8))*300)).hex()}
        original=dict(schema={},slots=[{}]*115,denominators={},capacity=dict(S=6,P=6,D=6),models={str(seed)+':'+arm:dict(initial=parameters,order=order) for seed in (20261012,20261013) for arm in ('S','P','D')})
        spec=put(self.root/'invented_original_admission.json',original)
        self.g['input_pins']['original_admission']=spec['pin'];self.gpin=io.pin(io.canonical(self.g));self.h['execution_pin']=self.gpin
        self.h['inputs']['original_admission']=spec
        self.h['history']=dict(reused_scores=[],stronger_envelope={'pin':self.pin})
        for name in ('source_runtime','current'):
            obj=io.json_read(Path(self.h['evidence'][name]['path']).read_bytes());obj['execution_pin']=self.gpin
            self.h['evidence'][name]=put(self.root/(name+'_audit.json'),obj)
        self.h['evidence']['audit']=put(self.root/'audit_proof.json',dict(schema='root-L-audit-proof-v1',execution_pin=self.gpin,input_evidence_pin=self.h['evidence']['inputs']['pin']))
        self.rebind();self.p.inputs_verified=True;self.p.verified_input_pin=self.h['evidence']['inputs']['pin']
        admission=dict(status='admitted',study=c.STUDY,packet_sha256=self.h['facts']['packet_sha256'],original_admission_sha256=spec['pin']['sha256'],schema={},slots=original['slots'],denominators={},capacity=dict(S=6,P=6,D=6,L=6),models={str(seed)+':L':dict(initial=parameters,order=order,probe=probe,original_initial_sha256=io.pin(io.canonical(parameters))['sha256']) for seed in (20261012,20261013)})
        adsha=io.pin(io.canonical(admission))['sha256']
        optimizer={str(i):dict(step=array(300.),exp_avg=array(0.),exp_avg_sq=array(1.)) for i in range(6)}
        history=[dict(update=n,loss=0.,gradient_norm=1.,ordinals=list(range(8))) for n in range(1,301)]
        checkpoint=dict(status='final',study=c.STUDY,seed=20261012,arm='L',update=300,parameters=parameters,optimizer=optimizer,history=history,final_probe=probe,admission_sha256=adsha)
        latest=dict(checkpoint,status='partial');extra={'latest_update.json':latest,'begin_fit.json':dict(update=0,parameters=parameters)};callbacks=[]
        for n in range(1,301):
            pin=io.pin(io.canonical(latest)) if n==300 else io.pin(io.canonical({'synthetic_step':n}))
            if n==300 and bad_final_pin:pin=io.pin(b'unrelated retained checkpoint')
            extra['update_%03d.json'%n]=dict(update=n,checkpoint_pin=pin,history_last=history[n-1]);callbacks.append(dict(kind='step',name='latest_update.json',pin=pin))
        score=dict(status='complete',seed=20261012,arm='L',checkpoint_sha256=io.pin(io.canonical(checkpoint))['sha256'])
        cache={};previous={}
        for index,payload,additional,cb in ((0,admission,None,None),(1,checkpoint,extra,callbacks),(2,score,None,None)):
            j,result,answer,request=self.stage(index,payload=payload,extra=additional,callbacks=cb)
            try:
                self.p.retain_return(index,result,j.inventory(),answer,request);snapshot=self.custody.snapshot(index)
                raw={name:p.owned_read(io,s) for name,s in snapshot['files'].items()};previous[str(index)]=raw['result.json'];cache[index]=({},raw,snapshot)
            finally:j.close()
        stage=c.spec(self.g,6)
        input_scope=dict(schema='L-bridge-input-scope-v1',config_pin=self.gpin,stage=stage,unit=stage['unit'],mode='independent',source_begin=100.,loader_config_pin=self.h['loader_pin'],input_pins=self.g['input_pins'],historical_pins=dict(reused_scores=[],stronger_envelope=self.pin),source_pins={k:self.g['source_pins'][k] for k in p.ROLES},original_source_pins=self.old)
        scope=dict(schema='L-bridge-audit-scope-v1',input_scope=input_scope,stage=stage,previous_pins={k:io.pin(v) for k,v in previous.items()})
        receipt=dict(proof_pin=self.p.verified_input_pin,packet_sha256=self.h['facts']['packet_sha256'],scope=input_scope)
        return scope,previous,receipt,cache,Path(self.h['evidence']['audit']['path']).read_bytes()


class Tests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory(prefix='invented-L-primitives-');self.f=Fixture(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_factory_rejects_unheld_root_pin(self):
        spec=put(self.f.root/'other_root.json',self.f.h)
        with self.assertRaises(ValueError):p.make_primitives(self.f.h,expected_root_pin=io.pin(b'untrusted'),root_spec=spec,modules=self.f.modules)
    def test_factory_no_numerical_imports(self):
        self.assertFalse(any(n=='numpy' or n.startswith('numpy.') or n=='torch' or n.startswith('torch.') for n in sys.modules))
    def test_current_concrete_readbacks_and_all_available(self):
        r=self.f.current();self.assertEqual(r['claims']['expires'],7400.);self.assertEqual(len(self.f.available),9)
    def test_expired_gate(self):
        self.f.now=7401.
        with self.assertRaises(ValueError):self.f.current()
    def test_boot_change(self):
        self.f.boot='87654321-1234-1234-1234-123456789abc'
        with self.assertRaises(ValueError):self.f.current()
    def test_document_bytes_cannot_be_requested_replacements(self):
        scope=c.scope(self.f.g,c.spec(self.f.g,0),'parent');docs={k:Path(v['path']).read_bytes() for k,v in self.f.h['documents'].items()};docs['funding']=b'{}'
        with self.assertRaises(ValueError):self.f.p.current(scope,self.f.h,docs,Path(self.f.h['evidence']['current']['path']).read_bytes(),100.)
    def test_timer_must_be_actual_readback(self):
        self.f.modules['systemd_adapter'].process=lambda *a:transport(b'ActiveState=inactive\nUnit=invented-whole.service\nNextElapseUSecMonotonic=7400s\n')
        with self.assertRaises(ValueError):self.f.current()
    def test_earlier_installed_stop_bounds_stage_expiry(self):
        doc=io.json_read(Path(self.f.h['evidence']['current']['path']).read_bytes());doc['timer']['deadline']=101.
        self.f.h['evidence']['current']=put(self.f.root/'early_current.json',doc);self.f.rebind()
        original=self.f.modules['systemd_adapter'].process
        def process(args,timeout):
            if args[3].endswith('.timer'):return transport(b'ActiveState=active\nUnit=invented-whole.service\nNextElapseUSecMonotonic=101s\n')
            return original(args,timeout)
        self.f.modules['systemd_adapter'].process=process
        with self.assertRaisesRegex(ValueError,'installed_stop_stage_cover'):self.f.current()
        self.assertEqual(self.f.current(phase='child')['claims']['expires'],101.)
    def test_monotonic_weeks_days(self):
        self.assertAlmostEqual(p.monotonic_seconds(io,'1w 3d 18h 2min 25.750278s'),928945.750278)
        for v in ('infinity','NaN','-1s','1w;bad','2days','1e3s'):
            with self.subTest(v=v),self.assertRaises(ValueError):p.monotonic_seconds(io,v)
    def test_full_original_streams_no_truncation(self):
        value=dict(code=0,exception=None,streams_complete=True,timeout=False,**{k:dict(original_pin=io.pin(v),retained_hex=v.hex(),truncated=False) for k,v in [('stdout',b'ok'),('stderr',b'')]})
        p.old_streams(io,value);value['stdout']['original_pin']=io.pin(b'changed')
        with self.assertRaises(ValueError):p.old_streams(io,value)
    def test_raw_external_receipt_keeps_noncanonical_original_bytes(self):
        spec=put(self.f.root/'external.json',b'{\n  "schema": "invented", "a": 1\n}\n',True)
        self.assertEqual(p.raw_receipt(io,spec)['a'],1)
        with self.assertRaises(ValueError):p.read_object(io,spec)
        wrong=copy.deepcopy(spec);wrong['pin']=io.pin(b'changed')
        with self.assertRaises(ValueError):p.raw_receipt(io,wrong)
    def test_duplicate_keys_in_external_receipt_rejected(self):
        spec=put(self.f.root/'external_duplicate.json',b'{"x":1,"x":2}',True)
        with self.assertRaises(ValueError):p.raw_receipt(io,spec)
    def test_manager_stream_eof_and_counts(self):
        value=saved(transport());p.saved_streams(io,c,value);value['stream_custody']['stdout']['complete_observation']=False
        with self.assertRaises(ValueError):p.saved_streams(io,c,value)
    def test_tree_rejects_unknown_temp(self):
        d=self.f.root/'flat';d.mkdir(mode=0o700);put(d/'ok.json',{})
        p.tree(io,str(d));put(d/'.tmp-dangling',{})
        with self.assertRaises(ValueError):p.tree(io,str(d))
    def test_readonly_hardlink_rejected(self):
        spec=put(self.f.root/'hard.json',{});os.link(spec['path'],self.f.root/'alias.json')
        with self.assertRaises(ValueError):p.owned_read(io,spec)
    def test_readonly_symlink_rejected(self):
        spec=put(self.f.root/'real.json',{});alias=self.f.root/'symlink.json';alias.symlink_to(spec['path']);spec['path']=str(alias)
        with self.assertRaises((ValueError,OSError)):p.owned_read(io,spec)
    def test_source_function_memory_replacement_rejected(self):
        raw=b'def f():\n    return 1\n';m=SimpleNamespace(__file__='/invented/source.py',__name__='invented');exec(compile(raw,m.__file__,'exec'),m.__dict__);p.module_code(io,m,raw)
        exec(compile('def f():\n    return 2\n',m.__file__,'exec'),m.__dict__)
        with self.assertRaises(ValueError):p.module_code(io,m,raw)
    def test_source_function_rebound_to_foreign_globals_rejected(self):
        raw=b'def f():\n    return 1\n';m=SimpleNamespace(__file__='/invented/source.py',__name__='invented');exec(compile(raw,m.__file__,'exec'),m.__dict__)
        foreign={};exec(compile(raw,m.__file__,'exec'),foreign);m.f=foreign['f']
        with self.assertRaisesRegex(ValueError,'loaded_function_globals'):p.module_code(io,m,raw)
    def test_deleted_source_validator_is_rejected(self):
        raw=b'def f():\n    return 1\n';m=SimpleNamespace(__file__='/invented/source.py',__name__='invented');exec(compile(raw,m.__file__,'exec'),m.__dict__);del m.f
        with self.assertRaises(ValueError):p.module_code(io,m,raw)
    def test_seal_detects_mutation_even_same_size(self):
        spec=put(self.f.root/'sealed.json',{'x':1});seal=self.f.p.seal({spec['path']});Path(spec['path']).chmod(0o600);Path(spec['path']).write_bytes(b'{"x":2}');Path(spec['path']).chmod(0o400)
        self.assertNotEqual(seal,self.f.p.seal({spec['path']}))
    def test_cached_inventory_detects_added_failure_member(self):
        d=self.f.root/'cached';d.mkdir(mode=0o700);spec=put(d/'ok.json',{})
        self.f.p.input_paths={spec['path']};self.f.p.input_seal=self.f.p.seal(self.f.p.input_paths);self.f.p.input_directories={str(d):p.tree(io,str(d))}
        self.f.p.check_input_seal();put(d/'late_or_failed.json',{})
        with self.assertRaises(ValueError):self.f.p.check_input_seal()
    def test_durable_retention_and_readonly_snapshot(self):
        j,result,answer,request=self.f.stage()
        try:
            retained=self.f.p.retain_return(0,result,j.inventory(),answer,request);self.assertEqual(retained['return_pin'],io.pin(io.canonical(result)))
            before=p.tree(io,str(self.f.store/'stage_00'));snapshot=self.f.custody.snapshot(0)
            self.assertEqual(p.tree(io,str(self.f.store/'stage_00')),before)
            self.assertEqual(snapshot['known_pin'],io.pin(snapshot['known_raw']))
            scope=dict(schema='root-L-prior-scope-v1',stage=0,closed_pin=io.pin(io.canonical(result)),root_scope=dict(schema='root-L-composition-scope-v1',root_pin=io.pin(io.canonical(self.f.h)),execution_pin=self.f.gpin,loader_pin=self.f.h['loader_pin']))
            claims=self.f.p.prior(scope,self.f.h,snapshot,j.inventory(),100.)['claims'];self.assertEqual(claims['result_pin'],result['result_pin'])
        finally:j.close()
    def test_retention_rejects_actual_answer_mismatch(self):
        j,result,answer,request=self.f.stage();answer['stdout']=b'forged'
        try:
            with self.assertRaises(ValueError):self.f.p.retain_return(0,result,j.inventory(),answer,request)
            self.assertTrue((self.f.returns/'stage_00.json').exists())
        finally:j.close()
    def test_failure_is_retained_but_not_advanceable(self):
        j,result,answer,request=self.f.stage(status='incomplete')
        try:
            self.f.p.retain_return(0,result,j.inventory(),answer,request)
            with self.assertRaises(ValueError):self.f.custody.snapshot(0)
        finally:j.close()
    def test_duplicate_return_poison_no_retry(self):
        j,result,answer,request=self.f.stage()
        try:
            self.f.p.retain_return(0,result,j.inventory(),answer,request)
            with self.assertRaises(FileExistsError):self.f.p.retain_return(0,result,j.inventory(),answer,request)
            with self.assertRaises(ValueError):self.f.custody.snapshot(0)
        finally:j.close()
    def test_provisional_closed_is_not_custody(self):
        j,*_=self.f.stage()
        try:
            with self.assertRaises(FileNotFoundError):self.f.custody.snapshot(0)
        finally:j.close()
    def test_actual_root_cleanup_must_be_observed(self):
        j,result,answer,request=self.f.stage()
        self.f.modules['systemd_adapter'].process=lambda *a:transport(b'Result=success\nActiveState=active\nControlGroup=/still-live\n')
        try:
            with self.assertRaises(ValueError):self.f.p.retain_return(0,result,j.inventory(),answer,request)
        finally:j.close()
    def test_probe_mask_and_exact195(self):
        probe=dict(events=65,horizons=3,terms=195,used=2,total=2,masks={'x':{'__array__':'|u1','shape':[2],'hex':'0101'}})
        self.f.p.probe(probe);probe['masks']['x']['hex']='0100'
        with self.assertRaises(ValueError):self.f.p.probe(probe)
    def test_optimizer_requires_all300_steps(self):
        names=['coefficients','prior.first_bias','prior.second.weight','prior.second.bias','prior.head.weight','prior.head.bias']
        a=lambda x:{'__array__':'<f8','shape':[],'hex':struct.pack('<d',x).hex()}
        parameters={k:a(0.) for k in names};optimizer={str(i):dict(step=a(300.),exp_avg=a(0.),exp_avg_sq=a(1.)) for i in range(len(names))}
        self.f.p.optimizer(optimizer,parameters);optimizer['0']['step']=a(299.)
        with self.assertRaises(ValueError):self.f.p.optimizer(optimizer,parameters)
    def test_full21_historical_actual_wire_shapes(self):
        ctx,proof=invented_history(self.f.root/'history');p.Primitives.historical(ctx,proof)
        self.assertGreater(len(ctx.input_paths),150)
        original=io.json_read(Path(proof['original_execution']['path']).read_bytes())
        self.assertNotIn('dispatch.json',original['stages'][0]['files'])
    def test_historical_original_source_file_manifest_not_relabelled(self):
        ctx,proof=invented_history(self.f.root/'history');meta=io.json_read(Path(proof['original_execution']['path']).read_bytes());meta['controller_source_pin']=meta['bootstrap_source_pin'];proof['original_execution']=put(self.f.root/'wrong_original.json',meta);ctx.h['facts']['original_execution_closure_sha256']=proof['original_execution']['pin']['sha256']
        with self.assertRaises(ValueError):p.Primitives.historical(ctx,proof)
    def test_historical_missing_raw_member_rejected(self):
        ctx,proof=invented_history(self.f.root/'history');meta=io.json_read(Path(proof['original_execution']['path']).read_bytes());Path(meta['stages'][5]['directory'],'manager_return.json').unlink()
        with self.assertRaises(ValueError):p.Primitives.historical(ctx,proof)
    def test_concrete_audit_authority_requires_actual300_step_custody(self):
        scope,previous,receipt,cache,evidence=self.f.audit_fixture()
        result=self.f.p.audit(scope,self.f.h,previous,receipt,cache,evidence,100.)
        self.assertTrue(result['claims']['authority']['optimizer_history_verified'])
        self.assertTrue(result['claims']['authority']['gradient_probes_verified'])
        self.assertNotIn('torch',sys.modules)
    def test_audit_cannot_assert_missing_retained_update(self):
        scope,previous,receipt,cache,evidence=self.f.audit_fixture();Path(cache[1][2]['files']['update_042.json']['path']).unlink()
        with self.assertRaises(ValueError):self.f.p.audit(scope,self.f.h,previous,receipt,cache,evidence,100.)
    def test_last_callback_and_update_cannot_agree_on_unrelated_checkpoint(self):
        scope,previous,receipt,cache,evidence=self.f.audit_fixture(bad_final_pin=True)
        with self.assertRaisesRegex(ValueError,'final_step_checkpoint_readback'):self.f.p.audit(scope,self.f.h,previous,receipt,cache,evidence,100.)


if __name__=='__main__':unittest.main()

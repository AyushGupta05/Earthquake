"""Invented custody/control fixtures only. No scientific data or cloud execution."""
import contextlib
import copy
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'reference'),str(ROOT)]
import secure_io as io
import source_binding as sb
import audit_journal as journal
import audit_control as ctl
import audit_deployment as depmod
import audit_bootstrap as boot
import systemd_adapter as sdmod

def config(begin=100):
    return dict(schema='marked-seven-audit-deployment-v1',audit_id='fixture-audit',study=ctl.STUDY,feature_schema='earthquake-TRAIN115-marked-noise-observations-v1',feature_study='earthquake-TRAIN115-marked-noise-study-v1',whole_begin=begin,lease_deadline=begin+7400,binding_sha256='a'*64,wrapper_binding_sha256='b'*64,sources={r:{} for r in depmod.ROLES},runtime={},bundle_template={},publication={},protocol={},hooks_source={},hooks_config={},commands={},store_directory='',storage_limit_bytes=7*64*1024*1024)

class Temp(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=str(Path(self.temp.name).resolve());os.chmod(self.path,0o700);self.j=journal.Journal(self.path)
    def tearDown(self):self.j.close();self.temp.cleanup()

class JournalTests(Temp):
    def test_large_member_roundtrip_old_store_unchanged(self):
        value=b'x'*(3*1024*1024);self.j.write(0,'raw_report_000.json',value);self.assertEqual(self.j.read(0,'raw_report_000.json'),value);self.assertEqual(io.CAP,2*1024*1024)
    def test_no_overwrite_or_retry(self):
        self.j.write(0,'claim.json',b'{}')
        with self.assertRaises(FileExistsError):self.j.write(0,'claim.json',b'{}')
    def test_only_seven_stages(self):
        for i in (-1,7,True):
            with self.assertRaises(ValueError):self.j.write(i,'claim.json',b'{}')
    def test_symlink_member_rejected(self):
        self.j.write(0,'claim.json',b'{}');os.symlink('claim.json',Path(self.path)/'stage_00'/'return.json')
        with self.assertRaises(ValueError):self.j.read(0,'claim.json')
    def test_hardlink_member_rejected(self):
        self.j.write(0,'claim.json',b'{}');os.link(Path(self.path)/'stage_00'/'claim.json',Path(self.path)/'stage_00'/'return.json')
        with self.assertRaises(ValueError):self.j.exists(0,'claim.json')
    def test_writable_member_rejected(self):
        self.j.write(0,'claim.json',b'{}');os.chmod(Path(self.path)/'stage_00'/'claim.json',0o600)
        with self.assertRaises(ValueError):self.j.read(0,'claim.json')
    def test_member_limit(self):
        with patch.object(journal,'MEMBER',5):
            with self.assertRaises(ValueError):self.j.write(0,'raw_report_000.json',b'123456')
    def test_reserve_survives_payload_limit(self):
        with patch.multiple(journal,STAGE=100,RESERVE=30,MEMBER=100,CONTROL=30):
            self.j.write(0,'raw_report_000.json',b'x'*70)
            with self.assertRaises(ValueError):self.j.write(0,'record_000.json',b'x')
            self.j.write(0,'child_failure.json',b'failure');self.assertEqual(self.j.read(0,'child_failure.json'),b'failure')
    def test_return_charged_as_payload(self):
        with patch.multiple(journal,STAGE=100,RESERVE=30,MEMBER=100,CONTROL=30):
            self.j.write(0,'return.json',b'x'*70)
            with self.assertRaises(ValueError):self.j.write(0,'record_000.json',b'x')
    def test_thread_lock_nonblocking(self):
        with self.j.locked():
            with self.assertRaises(ValueError):self.j.write(0,'claim.json',b'{}')
    def test_unfinished_temp_poison(self):
        self.j.write(0,'claim.json',b'{}');(Path(self.path)/'stage_00'/'.tmp-unknown').write_text('x')
        with self.assertRaises(ValueError):self.j.write(1,'claim.json',b'{}')
    def test_owner_mode(self):
        self.j.close();os.chmod(self.path,0o755)
        with self.assertRaises(ValueError):journal.Journal(self.path)
    def test_directory_symlink_not_followed(self):
        target=Path(self.path)/'actual';target.mkdir(mode=0o700);(Path(self.path)/'stage_00').symlink_to(target,target_is_directory=True)
        with self.assertRaises((ValueError,OSError)):self.j.write(0,'claim.json',b'{}')
    def test_persistence_sync_before_receipt(self):
        calls=[];real=io.file_sync
        def sync(fd):calls.append('file_sync');return real(fd)
        with patch.object(io,'file_sync',side_effect=sync):ack=self.j.write(0,'claim.json',b'{}')
        self.assertEqual(calls,['file_sync']);self.assertEqual(ack,{'status':'durable','sha256':io.pin(b'{}')['sha256']});self.assertEqual(stat.S_IMODE(os.stat(Path(self.path)/'stage_00'/'claim.json').st_mode),0o400)

class FakeDep:
    def __init__(self,c,j,clock):self.c=c;self.j=j;self.clock=clock;self.runs=0;self.stops=[];self.fail=None;self.post_bad=False
    def authorize(self,s,phase,bundle):return dict(expires=self.c['lease_deadline'])
    def run(self,request,timeout):
        self.runs+=1;i=request['stage']['index'];claim=io.canonical({'fake':'claim'});raw=io.canonical({'status':'pass','checked':66});result=dict(status='complete',stage=i,binding_sha256=self.c['wrapper_binding_sha256'])
        self.j.write(i,'claim.json',claim);self.j.write(i,'raw_report_000.json',raw);self.j.object(i,'return.json',result)
        self.j.object(i,'child_report.json',dict(status='complete',stage=i,config_pin=ctl.config_pin(self.c),request_pin=io.pin(io.canonical(request)),return_pin=io.pin(io.canonical(result)),report_pin=io.pin(raw),claim_pin=io.pin(claim),within_source=True))
        if self.fail=='child':self.j.object(i,'child_failure.json',{'bad':True})
        if self.fail=='late':self.clock[0]=self.c['whole_begin']+7500
        custody={k:dict(original_bytes=0,original_sha256=io.pin(b'')['sha256'],retained_bytes=0,truncated=False,complete_observation=True) for k in ('stdout','stderr')}
        answer=dict(code=1 if self.fail=='exit' else 0,timeout=self.fail=='timeout',streams_complete=self.fail not in ('streams','truncated'),stdout=b'',stderr=b'',exception=None,stream_custody=custody)
        if self.fail=='truncated':
            answer['stdout']=b'x'*65536;custody['stdout']=dict(original_bytes=70000,original_sha256=io.pin(b'x'*70000)['sha256'],retained_bytes=65536,truncated=True,complete_observation=True)
        return answer
    def stop(self,unit,timeout):self.stops.append(timeout);return dict(requested=True,cleanup_verified=False)
    def inspect(self,unit,timeout):
        if self.post_bad:raise ValueError('unverifiable')
        return dict(unit=unit,result='success',active_state='inactive',control_group='')

class ControllerTests(Temp):
    def setUp(self):super().setUp();self.now=[100];self.c=config();self.d=FakeDep(self.c,self.j,self.now)
    def runone(self,i=0):return ctl.run_stage(self.c,i,{},self.j,self.d,clock=lambda:self.now[0])
    def test_all_seven_fixed_order(self):
        for i in range(7):self.assertEqual(self.runone(i)['status'],'complete')
        self.assertEqual(self.d.runs,7);self.assertEqual([(ctl.spec(self.c,i)['seed'],ctl.spec(self.c,i)['arm']) for i in range(6)],list(ctl.ORDER))
    def test_duplicate_dispatch_no_retry(self):
        self.runone()
        with self.assertRaises(FileExistsError):self.runone()
        self.assertEqual(self.d.runs,1)
    def test_skip_rejected(self):
        with self.assertRaises(FileNotFoundError):self.runone(1)
        self.assertEqual(self.d.runs,0)
    def test_no_transport_zero_exit_promotion(self):
        self.d.fail='streams';r=self.runone();self.assertEqual(r['status'],'incomplete');self.assertTrue(self.j.exists(0,'manager_return.json'))
    def test_truncated_original_stream_preserved(self):
        self.d.fail='truncated';self.assertEqual(self.runone()['status'],'incomplete');v=ctl.parse(self.j.read(0,'manager_return.json'))
        self.assertEqual(v['stream_custody']['stdout']['original_bytes'],70000);self.assertEqual(v['stream_custody']['stdout']['original_sha256'],io.pin(b'x'*70000)['sha256']);self.assertEqual(v['stdout']['retained_pin'],io.pin(b'x'*65536));self.assertTrue(v['stdout']['truncated']);self.assertNotIn('original_pin',v['stdout'])
    def test_full_stream_hash_disagreement_rejected(self):
        answer=dict(stdout=b'x',stderr=b'',stream_custody={k:dict(original_bytes=int(k=='stdout'),retained_bytes=int(k=='stdout'),original_sha256=io.pin(b'')['sha256'],truncated=False,complete_observation=True) for k in ('stdout','stderr')})
        with self.assertRaisesRegex(ValueError,'hash'):ctl.streams_checked(answer)
    def test_nonzero_exit_stopped(self):
        self.d.fail='exit';self.assertEqual(self.runone()['status'],'incomplete');self.assertEqual(len(self.d.stops),1)
    def test_child_failure_terminal(self):
        self.d.fail='child';self.assertEqual(self.runone()['status'],'incomplete')
        with self.assertRaises(ValueError):self.runone(1)
    def test_uncertain_cleanup_stopped_no_complete(self):
        self.d.post_bad=True;r=self.runone();self.assertFalse(r['cleanup_verified']);self.assertEqual(len(self.d.stops),1)
    def test_expiry_nonblocking_stop_preserves_report(self):
        self.d.fail='late';r=self.runone();self.assertEqual(r['status'],'incomplete');self.assertEqual(self.d.stops,[0]);self.assertTrue(self.j.exists(0,'return.json'));self.assertTrue(self.j.exists(0,'manager_return.json'))
    def test_finalization_late_marker(self):
        original=self.j.object
        def save(i,n,v):
            result=original(i,n,v)
            if n=='closed.json':self.now[0]=7600
            return result
        with patch.object(self.j,'object',side_effect=save):r=self.runone()
        self.assertEqual(r['status'],'incomplete');self.assertTrue(self.j.exists(0,'late_or_failed.json'))
    def test_short_parent_authority_caps_finalization(self):
        original=self.j.object
        def save(i,n,v):
            result=original(i,n,v)
            if n=='closed.json':self.now[0]=1101
            return result
        with patch.object(self.d,'authorize',return_value={'expires':1100}),patch.object(self.j,'object',side_effect=save):r=self.runone()
        self.assertEqual(r['status'],'incomplete');self.assertIn('late_finalization',r['errors'])
    def test_failed_closed_persist_not_success(self):
        original=self.j.object
        def save(i,n,v):
            if n=='closed.json':raise OSError('disk')
            return original(i,n,v)
        with patch.object(self.j,'object',side_effect=save):self.assertEqual(self.runone()['status'],'incomplete')
    def test_whole_budget_before_dispatch(self):
        self.now[0]=7000
        with self.assertRaises(ValueError):self.runone()
        self.assertEqual(self.d.runs,0)
    def test_command_exact_caps_and_cold_python(self):
        command=ctl.command(ctl.spec(self.c,0),'/fixture/python','pass')
        for x in ('RuntimeMaxSec=960','MemoryMax=2147483648','TasksMax=64','--setenv=CUDA_VISIBLE_DEVICES=','-I','-B'):self.assertIn(x,command)
    def test_config_feature_and_clock(self):
        for key,value in (('study','bad'),('feature_schema','bad'),('lease_deadline',float('nan')),('storage_limit_bytes',1)):
            c=copy.deepcopy(self.c);c[key]=value
            with self.assertRaises(ValueError):ctl.config_check(c,100)

class BindingTests(unittest.TestCase):
    def source(self,path):
        p=Path(path);p.mkdir();(p/'module.py').write_bytes(b'x=1\n');(p/'CHECKSUMS').write_bytes(b'original checksums');(p/'MANIFEST.json').write_bytes(b'{"files":{}}')
        files={n.name:io.pin(n.read_bytes()) for n in p.iterdir()}
        for n in p.iterdir():n.chmod(0o400)
        return dict(directory=str(p),files=files,manifest=dict(path=str(p/'MANIFEST.json'),pin=files['MANIFEST.json'],mode=0o400),upload_manifest=None)
    def test_closed_all_checksum_members(self):
        with tempfile.TemporaryDirectory() as t:
            s=self.source(Path(t).resolve()/'source');self.assertEqual(depmod.closed_source(s,lambda:None)['module.py'],b'x=1\n')
    def test_closed_unknown_file(self):
        with tempfile.TemporaryDirectory() as t:
            s=self.source(Path(t).resolve()/'source');(Path(s['directory'])/'extra.py').write_text('x')
            with self.assertRaises(ValueError):depmod.closed_source(s,lambda:None)
    def test_closed_replaced_member(self):
        with tempfile.TemporaryDirectory() as t:
            s=self.source(Path(t).resolve()/'source');p=Path(s['directory'])/'module.py';p.chmod(0o600);p.write_text('x=2\n');p.chmod(0o400)
            with self.assertRaises(ValueError):depmod.closed_source(s,lambda:None)
    def test_bootstrap_hash_and_symlink(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t).resolve()/'code.py';p.write_bytes(b'x');p.chmod(0o400);self.assertEqual(boot.read(str(p),10,io.pin(b'x')['sha256']),b'x')
            with self.assertRaises(ValueError):boot.read(str(p),10,'0'*64)
            q=p.with_name('link');q.symlink_to(p)
            with self.assertRaises(OSError):boot.read(str(q),10,io.pin(b'x')['sha256'])
    def test_forbidden_producer_role(self):
        c=config();c['sources']['processor']={};hooks=types.SimpleNamespace(**{n:lambda *a:None for n in ('authorize','authenticate_input','project_stronger','stage_spec')})
        with self.assertRaises(ValueError):depmod.Deployment(c,hooks,object(),clock=lambda:100)
    def test_loader_only_declared_groups_and_alias_restore(self):
        calls=[];np=types.ModuleType('numpy');np.__version__='fixture';scipy=types.ModuleType('scipy');scipy.__version__='fixture'
        c=config();c['runtime']={'versions':dict(python='.'.join(map(str,sys.version_info[:3])),numpy='fixture',scipy='fixture')}
        raws={};specs={}
        programs={
          'native':{'marked_native':'import numpy as np','packet_io':'import numpy as np\nimport marked_native as m'},
          'auditor':{n:'import numpy as np' for n in depmod.AUDITOR},
          'wrapper':{'wrapper':'x=1'},'input_adapter':{'adapter':'x=1'}}
        programs['auditor']['auditor']+='\nimport math_core as core\nimport packet as pkt\nimport transport as tx\nimport packet_digest\nimport metrics'
        for role,progs in programs.items():
            raws[role]={n+'.py':p.encode() for n,p in progs.items()};specs[role]=dict(directory=str(ROOT),files={n:io.pin(p) for n,p in raws[role].items()})
        c['sources']=specs;old=types.ModuleType('math_core');old.ambient=True
        with patch.dict(sys.modules,{'numpy':np,'scipy':scipy,'math_core':old}):
            result=depmod.independent_modules(c,raws,'fixtureload',lambda:None)
            self.assertIs(sys.modules['math_core'],old);self.assertIs(result[1]['auditor'].core,result[1]['math_core']);self.assertNotIn('torch',sys.modules)
        for name in list(sys.modules):
            if name.startswith('fixtureload_'):sys.modules.pop(name)
    def test_no_scientific_modules_shortcut(self):
        text=(ROOT/'audit_deployment.py').read_text();self.assertNotIn('sb.scientific_modules(',text);self.assertNotIn('import torch',text)

class ChildTests(Temp):
    def setUp(self):
        super().setUp()
        import time
        import wrapper
        self.wrapper=wrapper;self.begin=time.monotonic();self.c=config(self.begin);self.c['store_directory']=self.path
        self.s=ctl.spec(self.c,0);self.r=dict(schema='marked-seven-audit-request-v1',config_pin=ctl.config_pin(self.c),stage=self.s,dispatch_begin=self.begin,previous=[],bundle_spec={})
        self.j.object(0,'dispatch.json',self.r);self.events=[];self.late=False;self.bad=False;self.negative=False
        self.bundle=dict(binding_sha256=self.c['binding_sha256'],wrapper_binding_sha256=self.c['wrapper_binding_sha256'],native={'feature_archive':{'pin':io.pin(b'a')},'feature_manifest':{'pin':io.pin(b'm')}})
        self.proofs={k:dict(known_verified=True,sha256='1'*64) for k in ('source','runtime','native','stronger','history_gradient','resources')}
        self.now=[self.begin];self.expiry=self.c['lease_deadline']
        self.deployment=types.SimpleNamespace(config=self.c,raw={},clock=lambda:self.now[0],hooks=types.SimpleNamespace(project_stronger=lambda *a:None,authenticate_input=lambda *a,**kw:None,stage_spec=lambda *a:None),systemd=types.SimpleNamespace(live=lambda s:self.events.append('live')))
        def check():
            if self.late:raise ValueError('late_fixture')
        def authorize(s,phase,b):
            self.assertEqual(self.deployment.source_begin,self.begin);self.events.append('authorize')
            return dict(expires=self.expiry,disk_available_bytes=128*1024*1024,disk_reserve_bytes=0,proofs=self.proofs)
        self.deployment.check=check;self.deployment.authorize=authorize
        def fit(score,packet,admission,checkpoint,authority,*,processing_begin,retain):
            self.events.append('auditor');retain({'invented':'numeric record'})
            return dict(schema='marked-sixfit-independent-audit-v1',status='fail' if self.bad else 'pass',checked=66,seed=20261012,arm='S',advance=dict(pass_all=not self.negative,checks=[]))
        class Bindings:
            def __init__(self,**kwargs):self.__dict__.update(kwargs)
        def prepare(i,b,bindings,*,processing_begin):
            self.events.append('prepare');self.assertEqual(processing_begin,self.begin)
            self.assertEqual(bindings.decode(b'{"x":1}',io.pin(b'{"x":1}')['sha256']),{'x':1})
            value=dict(score={'seed':20261012,'arm':'S'},packet={},admission={},checkpoint={'seed':20261012,'arm':'S'},authority={})
            return dict(inputs=value,inputs_sha256=io.pin(io.canonical(value))['sha256'],previous=[],proofs=self.proofs,evidence={})
        self.mods=({},dict(transport=types.SimpleNamespace(canonical=io.canonical,decode=lambda v,cap:v),packet_digest=types.SimpleNamespace(sha=lambda p:'x'*64),auditor=types.SimpleNamespace(audit_fit=fit,aggregate=lambda *a:None)),wrapper,types.SimpleNamespace(Bindings=Bindings,prepare_inputs=prepare))
        self.mods[0]['packet_io']=types.SimpleNamespace(load=lambda *a,**k:{})
    @contextlib.contextmanager
    def patches(self):
        @contextlib.contextmanager
        def guard(*a,**k):
            self.events.append('guard_enter')
            try:yield
            finally:self.events.append('guard_exit')
        with patch.object(depmod.sb,'vendor_guard',guard),patch.object(depmod,'independent_modules',return_value=self.mods),patch.object(depmod.io,'read_file',return_value=io.canonical(self.bundle)):
            yield
    def runchild(self):
        with self.patches():return depmod.execute(self.r,self.j,self.deployment,source_begin=self.begin)
    def test_full_frozen_wrapper_roundtrip_no_optimizer(self):
        result=self.runchild();self.assertEqual(result['status'],'complete');self.assertTrue(self.j.exists(0,'raw_report_000.json'));self.assertTrue(self.j.exists(0,'record_000.json'))
        self.assertEqual(self.events,['authorize','live','guard_enter','prepare','auditor','guard_exit'])
    def test_negative_scientific_gate_still_complete_audit(self):
        self.negative=True;self.assertEqual(self.runchild()['status'],'complete');self.assertFalse(ctl.parse(self.j.read(0,'return.json'))['advance']['pass_all'])
    def test_late_after_saved_full_return_fails(self):
        original=self.j.write
        def save(i,n,raw):
            result=original(i,n,raw)
            if n=='return.json':self.late=True
            return result
        with patch.object(self.j,'write',side_effect=save):result=self.runchild()
        self.assertEqual(result['status'],'incomplete');self.assertTrue(self.j.exists(0,'return.json'));self.assertTrue(self.j.exists(0,'raw_report_000.json'));self.assertTrue(self.j.exists(0,'child_failure.json'))
    def test_short_child_receipt_expiry_after_return(self):
        self.expiry=self.begin+10;original=self.j.write
        def save(i,n,raw):
            result=original(i,n,raw)
            if n=='return.json':self.now[0]=self.expiry+1
            return result
        with patch.object(self.j,'write',side_effect=save):result=self.runchild()
        self.assertEqual(result['status'],'incomplete');self.assertIn('authorization_expired',result['reason']);self.assertTrue(self.j.exists(0,'return.json'))
    def test_short_child_receipt_expiry_after_child_report(self):
        self.expiry=self.begin+10;original=self.j.write
        def save(i,n,raw):
            result=original(i,n,raw)
            if n=='child_report.json':self.now[0]=self.expiry+1
            return result
        with patch.object(self.j,'write',side_effect=save):result=self.runchild()
        self.assertEqual(result['status'],'incomplete');self.assertTrue(self.j.exists(0,'child_report.json'));self.assertTrue(self.j.exists(0,'child_failure.json'))
    def test_failed_audit_retained_before_failed_status(self):
        self.bad=True;self.assertEqual(self.runchild()['status'],'incomplete');self.assertEqual(ctl.parse(self.j.read(0,'raw_report_000.json'))['status'],'fail')
    def test_missing_dispatch_no_auditor(self):
        os.unlink(Path(self.path)/'stage_00'/'dispatch.json');self.assertEqual(self.runchild()['status'],'incomplete');self.assertNotIn('auditor',self.events)
    def test_bundle_mismatch_no_auditor(self):
        self.bundle['wrapper_binding_sha256']='c'*64;self.assertEqual(self.runchild()['status'],'incomplete');self.assertNotIn('auditor',self.events)
    def test_child_checkpoint_persist_failure_never_promoted(self):
        original=self.j.write
        def save(i,n,raw):
            if n=='return.json':raise OSError('fixture disk fail')
            return original(i,n,raw)
        with patch.object(self.j,'write',side_effect=save):self.assertEqual(self.runchild()['status'],'incomplete')
        self.assertTrue(self.j.exists(0,'raw_report_000.json'))
    def test_source_begin_and_live_precede_guard(self):
        self.runchild();self.assertLess(self.events.index('live'),self.events.index('guard_enter'))

class AuthorityTests(unittest.TestCase):
    def test_no_hook_default(self):
        with self.assertRaises(ValueError):depmod.Deployment(config(),object(),object(),clock=lambda:100)
    def test_expired_hook_receipt_rejected(self):
        c=config();c['runtime']={};c['sources']={k:{'manifest':{'pin':io.pin(b'public')}} for k in depmod.ROLES}
        def authorize(scope,docs,now):return dict(schema='root-marked-seven-audit-authorization-v1',scope=scope,decision='authorized',expires=101,disk_available_bytes=128*1024*1024,disk_reserve_bytes=0,proofs={})
        hooks=types.SimpleNamespace(authorize=authorize,authenticate_input=lambda *a:None,project_stronger=lambda *a:None,stage_spec=lambda *a:None)
        sd=types.SimpleNamespace(own=lambda u:None,available=lambda u,t:None)
        dep=depmod.Deployment(c,hooks,sd,clock=lambda:100)
        with patch.object(dep,'verify',return_value=dict(publication=b'p',protocol=b'p',hooks_config=b'h')),patch.object(io,'read_file',return_value=b'{}'):
            with self.assertRaisesRegex(ValueError,'lease'):dep.authorize(ctl.spec(c,0),'parent',{})

class TransportTests(unittest.TestCase):
    def test_real_bounded_subprocess_complete(self):
        r=sdmod.process([sys.executable,'-I','-B','-c','print("fixture")'],2)
        self.assertEqual(r['code'],0);self.assertTrue(r['streams_complete']);self.assertEqual(r['stdout'],b'fixture\n')
    def test_real_bounded_subprocess_timeout(self):
        r=sdmod.process([sys.executable,'-I','-B','-c','import time;time.sleep(5)'],.15)
        self.assertTrue(r['timeout']);self.assertFalse(r['streams_complete'])
    def test_unowned_unit_never_stopped(self):
        obj=object.__new__(sdmod.Systemd);obj.owned=set()
        with self.assertRaisesRegex(ValueError,'foreign_unit'):obj.stop('unknown.service',0)
    def test_bootstrap_alias_collision(self):
        with patch.dict(sys.modules,{'fixture_collision':types.ModuleType('fixture_collision')}):
            with self.assertRaises(ValueError):boot.load('fixture_collision',b'raise AssertionError',str(ROOT/'fixture.py'))

if __name__=='__main__':unittest.main()

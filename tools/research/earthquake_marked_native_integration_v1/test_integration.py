"""Invented records and isolated temp files only; no AWS/systemd/private data."""
import copy,hashlib,importlib.util,json,math,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import child,controller,custody,semantic

BASE=Path(__file__).parent

def load_candidate():
    names=('marked_native','packet_io','fixtures');previous={n:sys.modules.get(n) for n in names};loaded={}
    try:
        for n in names:
            spec=importlib.util.spec_from_file_location(n,BASE/'candidate'/(n+'.py'));m=importlib.util.module_from_spec(spec);sys.modules[n]=m;spec.loader.exec_module(m);loaded[n]=m
    finally:
        for n,m in previous.items():
            if m is None:sys.modules.pop(n,None)
            else:sys.modules[n]=m
    return loaded


def independent():
    root=BASE/'independent';names=('old_native_scanner','new_native_scanner','decode_contract','old_native','new_native','auditor')
    return child.load_group(dict(directory=str(root),files={n+'.py':custody.pin((root/(n+'.py')).read_bytes()) for n in names}),names,'test_native_independent')['auditor']


class Semantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules=load_candidate();cls.f=cls.modules['fixtures'];cls.m=cls.modules['marked_native'];cls.c=cls.f.corpus();cls.packet=cls.f.build(cls.c);cls.a=independent()
    def audit(self,packet=None,anchor=None,decode=None,begin=None):
        r=self.c['raw'];return semantic.audit(r['old_plan'],r['old_qualified'],self.c['pairs'][0][2],r['new_plan'],r['new_qualified'],self.c['pairs'][1][2],r['metadata'],r['roster'],self.packet if packet is None else packet,r['activity_anchor'] if anchor is None else anchor,self.f.decode if decode is None else decode,self.a,input_pins=self.c['pins'],processing_begin=time.monotonic() if begin is None else begin)
    def test_full115_345_exact_native_semantics_with_C_kept(self):
        result=self.audit();self.assertTrue(result['semantic_agreed']);self.assertEqual(result['events'],115);self.assertEqual(result['horizon_cells'],345);self.assertFalse(result['fit_authorized']);self.assertFalse(result['allpositive_pilot_admission']);self.assertEqual(result['observed_samples'],self.packet['observed_samples'])
    def test_joint_noise_index_and_ctx_activity_drop_corruption_denied(self):
        for field in ('nu','precontext'):
            p=copy.deepcopy(self.packet)
            if field=='nu':p['rows'][4]['noise']['nu'][0,1]+=1e-10
            else:p['rows'][4]['precontext'][6]+=1e-10
            with self.assertRaises(semantic.AuditError):self.audit(p)
    def test_native_ratio_log_censor_state_and_unknown_status_denied(self):
        for field in ('ratios','reported','censor','states','run_ages'):
            p=copy.deepcopy(self.packet);array=p['rows'][4]['horizons'][0][field];array.flat[0]+=1
            with self.assertRaises(semantic.AuditError):self.audit(p)
        p=copy.deepcopy(self.packet);p['rows'][0]['status']='available'
        with self.assertRaises(semantic.AuditError):self.audit(p)
    def test_body_hash_and_current_view_replay_denied(self):
        body=self.c['pairs'][0][2][1];self.c['pairs'][0][2][1]=body[:-1]+bytes([body[-1]^1])
        try:
            with self.assertRaises(semantic.AuditError):self.audit()
        finally:self.c['pairs'][0][2][1]=body
    def test_failed_decode_charged_before_no_promotion(self):
        def failure(raw,d):raise self.a.ObservedDecodeFailure(19)
        with self.assertRaises(semantic.AuditError) as error:self.audit(decode=failure)
        self.assertEqual(error.exception.observed_samples,{'old':19,'new':0});self.assertEqual(error.exception.diagnostics['checked_events'],0)
    def test_anchor_bool_alias_and_denominators_denied(self):
        original=json.loads(self.c['raw']['activity_anchor']);original['rows'][4]['context35'][6]=bool(original['rows'][4]['context35'][6]);raw=self.m.canonical(original);prior=self.c['pins']['activity_anchor'];self.c['pins']['activity_anchor']=self.m.pin(raw)
        # Packet binding adjusts only to make semantic type checks reachable.
        packet=copy.deepcopy(self.packet);packet['input_pins']['activity_anchor']=self.m.pin(raw)
        try:
            with self.assertRaises(semantic.AuditError):self.audit(packet,anchor=raw)
        finally:self.c['pins']['activity_anchor']=prior
    def test_noTEST_missing_roster_deadline_denied(self):
        p=copy.deepcopy(self.packet);p['rows'][4]['partition']='TEST'
        with self.assertRaises(semantic.AuditError):self.audit(p)
        with self.assertRaisesRegex(semantic.AuditError,'audit_deadline'):self.audit(begin=time.monotonic()-301)
    def test_fresh_zero_native_event_keeps_censor_as_mass_token(self):
        row=self.c['pairs'][0][0]['rows'][4];meta=self.c['metadata'][4];first=self.f.START;period=semantic.Fraction(1000000000,64);native=[np.zeros(512,dtype=np.int32) for _ in range(3)]
        ctx,noise,hs=semantic.event(row,meta,native,first,period,time.monotonic(),self.a)
        self.assertEqual(len(ctx),34);self.assertEqual(noise['nu'],[[0.,0.,0.]]*12);self.assertTrue(all(c==1 for h in hs for r in h['censor'] for c in r));self.assertTrue(all(v==-12. for h in hs for r in h['reported'] for v in r))


def put(directory,name,raw):
    path=Path(directory)/name;path.write_bytes(raw);path.chmod(0o400);return {'path':str(path),'pin':custody.pin(raw)}


def gate(directory,stage='build'):
    root=Path(directory);output=root/'output';output.mkdir();inputs={name:put(root,name+'.bin',b'{}') for name in controller.INPUT_CAPS};inputs['old_bodies']={str(i):None for i in range(17)};inputs['new_bodies']={str(i):None for i in range(13)}
    sources={}
    for group,count in [('parent',1),('marked',22),('original',69),('auditor',1),('decoder',1)]:
        d=root/group;d.mkdir();files={}
        for i in range(count):name='s%d.py'%i;files[name]=put(d,name,b'# invented source\n')['pin']
        sources[group]={'directory':str(d),'files':files}
    runtime=dict(prefix_directory=str(root/'runtime'),manifest=put(root,'runtime.json',b'{}'),canonical_sha256='a'*64,symlink_manifest=put(root,'symlinks.json',b'{}'),critical_files={str(root/('critical%d'%i)):{'bytes':0,'sha256':'a'*64,'mode':'0o444'} for i in range(10)})
    g=dict(schema='marked-native-parent-gate-v1',study=controller.STUDY,stage=stage,processing_begin=time.monotonic(),source_commit='a'*40,sources=sources,runtime=runtime,inputs=inputs,prerequisites={'path':str(root/'prerequisites.json'),'pin':{'bytes':0,'sha256':'a'*64}},output_root=str(output),build_return=None)
    names={'schema':'marked-native-prerequisites-v1','source_maps':sources,'input_specs':inputs,'source_commit':'a'*40}
    names.update({k:True for k in ('source_published','linux_zero_skips','original_native_agreement','original_observations_agreement','anchor_independently_projected','group_roster_bound','funding_resource_authorized','owned_units_inactive')});g['prerequisites']=put(root,'prerequisites.json',(json.dumps(names,sort_keys=True)+'\n').encode());return g


class Controls(unittest.TestCase):
    def test_exclusive_claim_no_overwrite_and_schema_bound(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);out=controller.claim(g);self.assertTrue((out/'claim.private.json').exists())
            with self.assertRaises(FileExistsError):controller.claim(g)
            g['inputs']['old_bodies']['17']=None
            with self.assertRaises(ValueError):controller.gate_check(g)
    def test_FS_leaf_symlink_mode_hash_and_partial_fsync(self):
        with tempfile.TemporaryDirectory() as t:
            p=put(t,'x',b'invented');self.assertEqual(custody.read_file(p['path'],p['pin'],100),b'invented');os.symlink(p['path'],Path(t)/'link')
            with self.assertRaises(OSError):custody.read_file(Path(t)/'link',p['pin'],100)
            Path(p['path']).chmod(0o600)
            with self.assertRaises(ValueError):custody.read_file(p['path'],p['pin'],100)
            with patch.object(custody.os,'fsync',wraps=os.fsync) as fs:put(t,'other',b'x');custody.private_put(t,'failure.json',{'observed_samples':19},1000);self.assertGreaterEqual(fs.call_count,2)
    def test_closed_source_pin_and_extra_members_denied(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);s=g['sources']['marked'];controller.verify_sources(s,lambda:None);put(s['directory'],'rogue.py',b'# no\n')
            with self.assertRaisesRegex(ValueError,'source_closed'):controller.verify_sources(s,lambda:None)
    def test_owned_manager_limits_and_persist_before_post_deadline(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);seen=[]
            def runner(args,timeout):
                seen.extend(args);self.assertEqual(timeout,380);out=Path(g['output_root'])/'build';custody.Store(out).put('result.private.json',{'status':'complete'},1000)
                return dict(code=0,timeout=False,raw={'stdout':b'ok','stderr':b''},streams={k:dict(truncated=False,complete_observation=True) for k in ('stdout','stderr')})
            result=controller.run(g,runner=runner,check_output=lambda *a,**k:'Result=success\nActiveState=inactive\nControlGroup=\n')
            self.assertEqual(result['status'],'complete');self.assertIn('MemoryMax=1073741824',seen);self.assertIn('RuntimeMaxSec=360',seen);self.assertIn('TasksMax=32',seen);self.assertIn('KillMode=control-group',seen)
            self.assertEqual(Path(g['output_root'],'build','parent_return.private.json').stat().st_mode&0o777,0o400)
    def test_post_cleanup_failure_retains_manager_return(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t)
            answer=dict(code=1,timeout=False,raw={'stdout':b'partial','stderr':b'failure'},streams={})
            with self.assertRaises(ValueError):controller.run(g,runner=lambda *a:answer,check_output=lambda *a,**k:'ActiveState=active\nControlGroup=/still-owned\n')
            self.assertTrue(Path(g['output_root'],'build','manager_return.private.json').exists())
    def test_before_import_failure_export_and_no_dependencies(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);out=controller.claim(g)
            with patch.object(child,'before_import',side_effect=ValueError('invented gate failure')),patch.object(child,'dependencies') as deps:
                with self.assertRaisesRegex(ValueError,'invented gate failure'):child.main(out)
                deps.assert_not_called()
            value=json.loads((out/'failure.private.json').read_text());self.assertEqual(value['status'],'incomplete');self.assertEqual(value['reason'],'invented gate failure')
    def test_FeatureError_preserved_before_late_return_check(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);out=controller.claim(g);m=type('M',(),{})();m.FeatureError=load_candidate()['marked_native'].FeatureError;m.Bindings=lambda o:None
            def build(*args,**kwargs):raise m.FeatureError('invented_feature_failure',rows=[{'ordinal':4}],observed_samples={'old':7,'new':11},diagnostics={'noise':np.zeros(3,dtype='<f8')})
            m.build_marked=build;raws={k:b'{}' for k in controller.RAW_CAPS};bodies={'old_bodies':{},'new_bodies':{}}
            with patch.object(child,'before_import',return_value=(raws,bodies,{},{})),patch.object(child,'dependencies',return_value=(m,None,None,None,None,np)):
                with self.assertRaises(m.FeatureError):child.main(out)
            failure=json.loads((out/'failure.private.json').read_text());self.assertEqual(failure['observed_samples'],{'old':7,'new':11});self.assertEqual(failure['partial_rows'],[{'ordinal':4}]);self.assertEqual(failure['diagnostics']['noise']['dtype'],'<f8')
    def test_live_own_cgroup_manager_environment_and_membership(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);base=Path(t)/'cgroups';group=base/'user.slice'/'eew-marked-native-integration-v1-build.service';group.mkdir(parents=True)
            for name,text in [('memory.max','1073741824'),('memory.swap.max','0'),('pids.max','32'),('cgroup.procs',str(os.getpid()))]:put(group,name,text.encode())
            proc=put(t,'proc',b'0::/user.slice/eew-marked-native-integration-v1-build.service\n')['path'];env={k:'1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')};env['CUDA_VISIBLE_DEVICES']=''
            props='RuntimeMaxUSec=6min\nTimeoutStopUSec=5s\nKillMode=control-group\nActiveState=active\nCPUWeight=10\n'
            with patch.dict(os.environ,env),patch.object(sys,'dont_write_bytecode',True):
                result=child.live(g,proc=Path(proc),base=base,check_output=lambda *a,**k:props);self.assertEqual(result['limits']['pids.max'],'32')
                (group/'pids.max').chmod(0o600);(group/'pids.max').write_text('64');(group/'pids.max').chmod(0o400)
                with self.assertRaisesRegex(ValueError,'live_limits'):child.live(g,proc=Path(proc),base=base,check_output=lambda *a,**k:props)
    def test_runtime_full10112_closed_prefix_symlink_and_original_modes(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);prefix=root/'prefix';lib=prefix/'venv/lib';lib.mkdir(parents=True);files={}
            for i in range(10112):
                path=lib/('f%05d'%i);path.write_bytes(b'x');path.chmod(0o444);files[path.relative_to(prefix).as_posix()]=custody.pin(b'x')
            (prefix/'venv/bin').mkdir();os.symlink('../../critical0',prefix/'venv/bin/python')
            manifest={'files':files};canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode();critical={}
            for i in range(10):
                path=root/('critical%d'%i);path.write_bytes(b'public synthetic binary');path.chmod(0o555);critical[str(path)]=dict(custody.pin(path.read_bytes()),mode='0o555')
            r=dict(prefix_directory=str(prefix),manifest=put(root,'manifest.json',canonical),canonical_sha256=hashlib.sha256(canonical).hexdigest(),symlink_manifest=put(root,'links.json',json.dumps({'schema':'marked-native-runtime-symlinks-v1','symlinks':{'venv/bin/python':'../../critical0'}}).encode()),critical_files=critical)
            child.runtime_verify(r,lambda:None)
            (prefix/'venv/bin/python').unlink();os.symlink('../../critical1',prefix/'venv/bin/python')
            with self.assertRaisesRegex(ValueError,'runtime_closed'):child.runtime_verify(r,lambda:None)
    def test_import_failure_never_invokes_source_and_retains_generic_failure(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);out=controller.claim(g);raws={k:b'{}' for k in controller.RAW_CAPS};bodies={'old_bodies':{},'new_bodies':{}}
            with patch.object(child,'before_import',return_value=(raws,bodies,{},{})),patch.object(child,'dependencies',side_effect=ImportError('invented missing source')):
                with self.assertRaises(ImportError):child.main(out)
            self.assertEqual(json.loads((out/'failure.private.json').read_text())['exception_type'],'ImportError')
    def test_output_persists_before_late_parent_deadline(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);real_tick=controller.tick
            def tick(begin,limit=300):
                if limit==750:raise ValueError('invented outer deadline')
                return real_tick(begin,limit)
            answer=dict(code=1,timeout=False,raw={'stdout':b'partial','stderr':b'failure'},streams={})
            with patch.object(controller,'tick',side_effect=tick):
                with self.assertRaisesRegex(ValueError,'invented outer deadline'):controller.run(g,runner=lambda *a:answer,check_output=lambda *a,**k:'Result=exit-code\nActiveState=failed\nControlGroup=\n')
            self.assertTrue(Path(g['output_root'],'build','manager_return.private.json').exists());self.assertTrue(Path(g['output_root'],'build','parent_return.private.json').exists())

    def test_zero_exit_outer_expiration_is_incomplete_and_denies_AUDIT(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);real_tick=controller.tick
            def tick(begin,limit=300):
                if limit==750:raise ValueError('invented outer deadline')
                return real_tick(begin,limit)
            def runner(*args):
                custody.Store(Path(g['output_root'])/'build').put('result.private.json',{'status':'complete'},1000)
                return dict(code=0,timeout=False,raw={'stdout':b'ok','stderr':b''},streams={k:dict(truncated=False,complete_observation=True) for k in ('stdout','stderr')})
            with patch.object(controller,'tick',side_effect=tick):
                with self.assertRaisesRegex(ValueError,'invented outer deadline'):controller.run(g,runner=runner,check_output=lambda *a,**k:'Result=success\nActiveState=inactive\nControlGroup=\n')
            closure=Path(g['output_root'])/'build'/'parent_return.private.json';raw=closure.read_bytes();value=json.loads(raw)
            self.assertEqual(value['status'],'incomplete');self.assertEqual(value['unit_exit'],0);self.assertEqual(value['failure']['reason'],'invented outer deadline')
            self.assertTrue((closure.parent/'manager_return.private.json').exists());self.assertTrue((closure.parent/'result.private.json').exists())
            g['stage']='audit';g['build_return']={'path':str(closure),'pin':custody.pin(raw)}
            with self.assertRaisesRegex(ValueError,'build_unverified'):controller.claim(g)
            self.assertFalse((Path(g['output_root'])/'claim_audit.private.json').exists())

    def test_original_critical664_775_admission_and_exact_mode_identity(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);keys=list(g['runtime']['critical_files'])
            for index,mode in enumerate((0o664,0o775)):
                path=Path(keys[index]);path.write_bytes(b'invented original binary');path.chmod(mode)
                pin=dict(custody.pin(path.read_bytes()),mode=oct(mode));g['runtime']['critical_files'][str(path)]=pin
                controller.gate_check(g);custody.hash_file(path,pin,mode)
                path.chmod(0o644)
                with self.assertRaisesRegex(ValueError,'runtime_file'):custody.hash_file(path,pin,mode)
                path.chmod(mode)
            g['runtime']['critical_files'][keys[0]]['mode']='0o666'
            with self.assertRaisesRegex(ValueError,'critical'):controller.gate_check(g)

    def test_clock_and_runtime_before_import_contract(self):
        with tempfile.TemporaryDirectory() as t:
            g=gate(t);g['processing_begin']=time.monotonic()-301
            with self.assertRaisesRegex(ValueError,'deadline'):controller.gate_check(g)
            runtime=g['runtime']
            with self.assertRaises(ValueError):child.runtime_verify(runtime,lambda:None)

if __name__=='__main__':unittest.main()

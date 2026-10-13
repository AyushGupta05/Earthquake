"""Invented original storage, owned tempfiles and simulated managers only."""
from pathlib import Path
import copy,hashlib,importlib.util,io,json,os,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
import numpy as np
import anchor,deployment

BASE=Path(__file__).parent


def reference():
    root=BASE/'reference';source=dict(directory=str(root),files={p.name:anchor.pin(p.read_bytes()) for p in root.iterdir() if p.is_file()})
    return deployment.load_parent(source)


def marked():
    s=importlib.util.spec_from_file_location('root_projection_test_marked',BASE/'reference/marked_native.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m


def invented():
    arrays={};entries={};rows=[];inputs={k:anchor.pin(b'invented '+k.encode()) for k in anchor.RAW_KEYS};payload=0
    for i in range(115):
        part='TRAIN' if i<91 else 'DEV';common=i<65 or 91<=i<113;r=dict(ordinal=i,partition=part,mw=6.0,group=i,common=common,status='available' if common else 'unavailable',initial=None,horizons=[])
        if common:
            ctx=np.arange(35,dtype='<f8');ctx[6]=1
            scopes=[('init',dict(wave=np.zeros((3,16),dtype='<f4'),amplitude=np.zeros(4,dtype='<f4'),context=ctx))]
            for h in (1,3,5):
                rs=([10.,0.,10.,10.]*20)[:h*4];states=[int(x>9) for x in rs];ages=[];age=0;last=None
                for state in states:age=age+1 if state==last else 1;last=state;ages.append(age)
                scopes.append(('h%d'%h,dict(seconds=h,rate=[64,1],wave=np.zeros((3,h*64),dtype='<f4'),amplitude=np.zeros(4,dtype='<f4'),context=np.zeros(36,dtype='<f8'),ratios=rs,states=states,run_ages=ages)))
            for scope,fields in scopes:
                scalar={}
                for k,v in fields.items():
                    if k in ('wave','amplitude','context'):
                        name='r_%03d_%s_%s'%(i,scope,k);arrays[name]=v;raw=v.tobytes();entries[name]=dict(dtype=v.dtype.str,shape=list(v.shape),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());payload+=len(raw);scalar[k]=name
                    else:scalar[k]=v
                if scope=='init':r['initial']=scalar
                else:r['horizons'].append(scalar)
        else:r['horizons']=[dict(seconds=h,status='unavailable') for h in (1,3,5)]
        rows.append(r)
    packet=dict(schema=anchor.SCHEMA,study=anchor.STUDY,rows=rows,denominators=anchor.DEN,input_pins=inputs,observed_samples=dict(old=100,new=100),fit_authorized=False)
    manifest=anchor.canonical(dict(schema='receiver-observation-storage-v2',packet=packet,arrays=entries));buf=io.BytesIO();np.savez_compressed(buf,**arrays);archive=buf.getvalue()
    agreement=anchor.canonical(dict(public=dict(schema='earthquake-TRAIN115-receiver-observation-independent-audit-v1',study=anchor.STUDY,disposition='agreed',reason='exact_native_semantics',events=115,common_train=65,common_dev=22,checked_observations=348,fit_authorized=False),input_pins=inputs,observed_samples=packet['observed_samples'],numeric_payload_bytes=payload,fit_authorized=False))
    return archive,manifest,agreement,dict(archive=anchor.pin(archive),manifest=anchor.pin(manifest),agreement=anchor.pin(agreement)),inputs


class Projection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.values=invented();cls.m=marked()
    def project(self,values=None):
        a,m,r,p,i=self.values if values is None else values;return anchor.project(a,m,r,pins=p,input_pins=i,processing_begin=time.monotonic())
    def test_full115_345_exact_independent_projection_and_frozen_helper(self):
        raw,p=self.project();a=json.loads(raw);self.assertEqual(len(a['rows']),115)
        for r in p['rows']:
            if r['common']:r['initial']['context']=np.ascontiguousarray(r['initial']['context'],dtype='<f8')
        self.assertEqual(raw,self.m.project_anchor(p,source_pins={k:self.values[3][k] for k in ('archive','manifest')}))
    def test_summary_is_not_semantic_agreement(self):
        a,m,_,p,i=self.values;r=anchor.canonical(dict(status='complete',common_train=65,common_dev=22));p=dict(p,agreement=anchor.pin(r))
        with self.assertRaises((ValueError,KeyError)):self.project((a,m,r,p,i))
    def test_archive_pin_and_context_payload_corruption_rejected(self):
        a,m,r,p,i=self.values
        with self.assertRaisesRegex(ValueError,'pin'):self.project((a[:-1]+bytes([a[-1]^1]),m,r,p,i))
        d=json.loads(m);d['arrays']['r_000_init_context']['sha256']='0'*64;m=anchor.canonical(d);p=dict(p,manifest=anchor.pin(m))
        with self.assertRaisesRegex(ValueError,'context_hash'):self.project((a,m,r,p,i))
    def test_TEST_bool_alias_age_reset_future_prefix_rejected(self):
        a,m,r,p,i=self.values
        for mutate in [lambda d:d['packet']['rows'][0].update(partition='TEST'),lambda d:d['packet']['rows'][0].update(ordinal=False),lambda d:d['packet']['rows'][0]['horizons'][0]['run_ages'].__setitem__(1,2),lambda d:d['packet']['rows'][0]['horizons'][1]['ratios'].__setitem__(0,11.)]:
            d=json.loads(m);mutate(d);raw=anchor.canonical(d)
            with self.assertRaises(ValueError):self.project((a,raw,r,dict(p,manifest=anchor.pin(raw)),i))
    def test_deadline_before_values_and_duplicate_json_denied(self):
        a,m,r,p,i=self.values
        with self.assertRaisesRegex(ValueError,'deadline'):anchor.project(a,m,r,pins=p,input_pins=i,processing_begin=time.monotonic()-301)
        with self.assertRaisesRegex(ValueError,'duplicate_key'):anchor.parse(b'{"a":1,"a":2}',100)
    def test_projection_does_not_load_wave_numeric_values(self):
        with patch.object(np,'load',side_effect=AssertionError('wave load forbidden')):raw,p=self.project()
        self.assertIsInstance(p['rows'][0]['initial']['wave'],str);self.assertIsInstance(p['rows'][0]['initial']['context'],list)


def put(root,name,raw):
    path=Path(root)/name;deployment.raw_put(path,raw,4*1024*1024);return dict(path=str(path),pin=anchor.pin(raw))


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.modules=reference()
    def authority(self,t):
        return dict(schema='marked-native-root-authority-v1',processing_begin=time.monotonic(),source_commit='a'*40,sources=dict(parent={},marked={},original={},auditor={},decoder={}),runtime=dict(prefix_directory=str(Path(t)/'runtime')),inputs={},output_root=str(Path(t)/'output'),permissions={k:True for k in deployment.PERMISSIONS},deployment_source=dict(directory=str(BASE),files={}))
    def answer(self):return dict(code=0,timeout=False,raw=dict(stdout=b'ok',stderr=b''),streams={k:dict(truncated=False,complete_observation=True) for k in ('stdout','stderr')})
    def test_readonly_NOFOLLOW_hash_cap_and_fsync(self):
        with tempfile.TemporaryDirectory() as t:
            s=put(t,'x',b'invented');self.assertEqual(deployment.read(s,100),b'invented');os.symlink(s['path'],Path(t)/'link')
            with self.assertRaises(OSError):deployment.raw_read(Path(t)/'link',100)
            with self.assertRaisesRegex(ValueError,'raw_file'):deployment.raw_read(s['path'],1)
    def test_closed_source_extra_member_denied(self):
        with tempfile.TemporaryDirectory() as t:
            s=put(t,'a.py',b'# invented');source=dict(directory=t,files={'a.py':s['pin']});deployment.verify_source(source,time.monotonic());put(t,'extra.py',b'# extra')
            with self.assertRaisesRegex(ValueError,'source_closed'):deployment.verify_source(source,time.monotonic())
    def test_preparation_once_only_manager_caps_and_empty_cleanup(self):
        with tempfile.TemporaryDirectory() as t:
            a=self.authority(t);seen=[]
            def runner(args,timeout):
                seen.extend(args);self.assertEqual(timeout,380);self.modules['custody'].Store(Path(a['output_root'])/'preparation').put('result.private.json',dict(status='complete'),1000);return self.answer()
            with patch.object(deployment,'bootstrap',return_value=self.modules):
                result=deployment.prepare_once(a,runner=runner,check_output=lambda *a,**k:'Result=success\nActiveState=inactive\nControlGroup=\n');self.assertEqual(result['status'],'complete')
                with self.assertRaises(FileExistsError):deployment.prepare_once(a,runner=runner)
            for v in ['MemoryMax=1073741824','TasksMax=32','RuntimeMaxSec=360','TimeoutStopSec=5','KillMode=control-group']:self.assertIn(v,seen)
    def test_zero_exit_expiration_incomplete_closure_preserves_journal(self):
        with tempfile.TemporaryDirectory() as t:
            a=self.authority(t)
            def runner(*args):self.modules['custody'].Store(Path(a['output_root'])/'preparation').put('result.private.json',dict(status='complete'),1000);return self.answer()
            with patch.object(deployment,'bootstrap',return_value=self.modules),patch.object(self.modules['controller'],'tick',side_effect=ValueError('outer750')):
                with self.assertRaisesRegex(ValueError,'outer750'):deployment.prepare_once(a,runner=runner,check_output=lambda *a,**k:'Result=success\nActiveState=inactive\nControlGroup=\n')
            out=Path(a['output_root'])/'preparation';self.assertEqual(json.loads((out/'parent_return.private.json').read_bytes())['status'],'incomplete');self.assertTrue((out/'result.private.json').exists());self.assertTrue((out/'manager.private.json').exists())
    def test_before_import_failure_export_no_science(self):
        with tempfile.TemporaryDirectory() as t:
            put(t,'authority.private.json',anchor.canonical(self.authority(t)))
            with patch.object(deployment,'bootstrap',side_effect=ValueError('source mismatch')),patch.object(anchor,'project') as project:
                with self.assertRaisesRegex(ValueError,'source mismatch'):deployment.prepare_child(t)
                project.assert_not_called()
            self.assertEqual(json.loads((Path(t)/'failure.private.json').read_bytes())['status'],'incomplete')
    def test_separate_build_audit_same_subjects_and_no_auto_chaining(self):
        with tempfile.TemporaryDirectory() as t:
            a=self.authority(t);out=Path(a['output_root'])/'preparation';out.mkdir(parents=True);inputs={k:put(t,k+'.json',b'{}') for k in self.modules['controller'].INPUT_CAPS if k not in ('activity_anchor','anchor_proof')};inputs.update(old_bodies={str(i):None for i in range(17)},new_bodies={str(i):None for i in range(13)});a['inputs']=inputs
            extras={}
            for name in ('activity_anchor','anchor_proof'):extras[name]=put(out,name+'.private.json',b'{}')
            links=put(out,'runtime_symlinks.private.json',b'{}');runtime=dict(a['runtime'],symlink_manifest=links)
            result=dict(schema='marked-native-root-preparation-result-v1',status='complete',input_specs=dict(inputs,**extras),runtime=runtime,source_maps=a['sources'],source_commit=a['source_commit'],permissions=a['permissions'],output_root=a['output_root'],independent_projection_exact=True,fit_authorized=False);rs=put(out,'result.private.json',anchor.canonical(result));files={Path(v['path']).name:v['pin'] for v in list(extras.values())+[links,rs]};closed=dict(schema='marked-native-root-preparation-return-v1',status='complete',fingerprint=deployment.fingerprint(a),files=files,unit_exit=0,owned_unit_inactive=True,owned_cgroup_empty=True,no_retry=True);ret=put(out,'parent_return.private.json',anchor.canonical(closed));seen=[]
            def invoke(g):seen.append(g);return dict(status='complete')
            with patch.object(deployment,'bootstrap',return_value=self.modules):
                deployment.run_stage(a,ret,'build',processing_begin=time.monotonic(),invoke=invoke);self.assertEqual(len(seen),1);self.assertIsNone(seen[-1]['build_return'])
                b=put(t,'build_return.json',b'{}');deployment.run_stage(a,ret,'audit',processing_begin=time.monotonic(),build_return_spec=b,invoke=invoke);self.assertEqual(len(seen),2);self.assertEqual(seen[-1]['build_return'],b)
            self.assertEqual(seen[0]['inputs'],seen[1]['inputs']);self.assertEqual(seen[0]['prerequisites'],seen[1]['prerequisites'])
    def test_four_literal_links_source_capacity_and_critical_original_modes(self):
        with tempfile.TemporaryDirectory() as t:
            a=self.authority(t);a['sources']={name:dict(directory=str(Path(t)/name),files={'f%d.py'%i:dict(bytes=0,sha256='0'*64) for i in range(count)}) for name,count in [('parent',48),('marked',22),('original',69),('auditor',6),('decoder',4)]};a['deployment_source']=dict(directory=t,files={'deployment.py':dict(bytes=0,sha256='0'*64)})
            a['inputs']={k:dict(path=str(Path(t)/k),pin=dict(bytes=0,sha256='0'*64)) for k in self.modules['controller'].INPUT_CAPS if k not in ('activity_anchor','anchor_proof')};a['inputs'].update(old_bodies={str(i):None for i in range(17)},new_bodies={str(i):None for i in range(13)})
            a['runtime'].update(manifest=dict(path=str(Path(t)/'manifest'),pin=dict(bytes=0,sha256='0'*64)),canonical_sha256='0'*64,critical_files={str(Path(t)/('critical%d'%i)):dict(bytes=0,sha256='0'*64,mode='0o664' if i%2 else '0o775') for i in range(10)},original_symlinks={'venv/bin/python':'python3','venv/bin/python3':'/usr/bin/python3','venv/bin/python3.9':'python3','venv/lib64':'lib'})
            deployment.validate(a,self.modules['controller']);a['runtime']['original_symlinks'].pop('venv/lib64')
            with self.assertRaisesRegex(ValueError,'four_links'):deployment.validate(a,self.modules['controller'])

    def test_ordinary_entrypoint_creates_no_bytecode_before_argument_failure(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            for name in ('invoke.py','anchor.py','deployment.py'):(root/name).write_bytes((BASE/name).read_bytes());(root/name).chmod(0o400)
            before={p.name:anchor.pin(p.read_bytes()) for p in root.iterdir()}
            result=subprocess.run([sys.executable,'-W','error',str(root/'invoke.py'),'bad'],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,1);self.assertIn(b'arguments',result.stderr);self.assertEqual(set(p.name for p in root.iterdir()),set(before));self.assertFalse((root/'__pycache__').exists())
            self.assertEqual({p.name:anchor.pin(p.read_bytes()) for p in root.iterdir()},before)

    def test_bad_preparation_never_calls_frozen_stage(self):
        with tempfile.TemporaryDirectory() as t:
            a=self.authority(t);r=put(t,'incomplete.private.json',anchor.canonical(dict(schema='marked-native-root-preparation-return-v1',status='incomplete')))
            with patch.object(deployment,'bootstrap',return_value=self.modules),patch.object(self.modules['controller'],'run') as run:
                with self.assertRaisesRegex(ValueError,'preparation_unverified'):deployment.run_stage(a,r,'build',processing_begin=time.monotonic())
                run.assert_not_called()

if __name__=='__main__':unittest.main()

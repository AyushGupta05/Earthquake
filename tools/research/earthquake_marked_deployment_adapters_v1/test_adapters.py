"""Invented temp filesystem/process fixtures; no cloud, numerical data or weights."""
import copy
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import secure_io as io
import source_binding as sb
import systemd_adapter as sd
import deployment as dep
import comparison_join as cj
import bootstrap
import fixtures as fx


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700)
        sb.sysconfig.get_path('stdlib')  # warm stdlib config before deliberately isolated module fixtures
    def tearDown(self):self.tmp.cleanup()
    def store(self,cap=1048576,members=4096):
        s=io.Store(str(self.root),cap,members);self.addCleanup(s.close);return s


class Storage(Temp):
    def test_durable_exclusive_readback(self):
        s=self.store();raw=b'{"value":1}';r=s.write('stage_00/claim.json',raw,total_cap=s.total_cap)
        self.assertEqual(r,dict(status='durable',pin=io.pin(raw)));self.assertEqual(s.read('stage_00/claim.json'),raw)
        self.assertEqual(stat.S_IMODE((self.root/'stage_00/claim.json').stat().st_mode),0o400)
        with self.assertRaises(FileExistsError):s.write('stage_00/claim.json',raw,total_cap=s.total_cap)
    def test_atomic_latest_only(self):
        s=self.store();s.write('stage_01/latest_update.json',b'a',replace=True,total_cap=s.total_cap)
        s.write('stage_01/latest_update.json',b'new',replace=True,total_cap=s.total_cap)
        self.assertEqual(s.read('stage_01/latest_update.json'),b'new')
        with self.assertRaisesRegex(ValueError,'replacement_role'):s.write('stage_01/result.json',b'x',replace=True,total_cap=s.total_cap)
    def test_cap_checked_before_writing(self):
        s=self.store(5);s.write('stage_00/result.json',b'1234',total_cap=5)
        with self.assertRaisesRegex(ValueError,'temporary_store_cap'):s.write('stage_00/next.json',b'12',total_cap=5)
        self.assertEqual(sorted(p.name for p in (self.root/'stage_00').iterdir()),['result.json'])
        with self.assertRaisesRegex(ValueError,'write_cap'):s.write('stage_00/next.json',b'1',total_cap=6)
    def test_replacement_requires_full_temp_headroom(self):
        s=self.store(5);s.write('stage_00/latest_update.json',b'1234',total_cap=5)
        with self.assertRaisesRegex(ValueError,'temporary_store_cap'):s.write('stage_00/latest_update.json',b'12',replace=True,total_cap=5)
        self.assertEqual(s.read('stage_00/latest_update.json'),b'1234')
    def test_member_cap_and_snapshot_cap(self):
        s=self.store(members=1);s.write('stage_00/result.json',b'x',total_cap=s.total_cap)
        with self.assertRaisesRegex(ValueError,'temporary_store_cap'):s.write('stage_00/other.json',b'x',total_cap=s.total_cap)
        with self.assertRaisesRegex(ValueError,'write_cap'):s.write('stage_00/other.json',b'x'*(io.CAP+1),total_cap=s.total_cap)
    def test_nonblocking_process_and_thread_lock(self):
        s=self.store();second=self.store();start=time.monotonic()
        with s.locked():
            with self.assertRaisesRegex(ValueError,'store_busy'):s.exists('stage_00/x.json')
            with self.assertRaises(BlockingIOError):second.exists('stage_00/x.json')
        self.assertLess(time.monotonic()-start,.5)
    def test_partial_temp_retained_and_blocks_success(self):
        s=self.store()
        with patch.object(io,'file_sync',side_effect=OSError('invented disk sync failure')):
            with self.assertRaises(OSError):s.write('stage_00/claim.json',b'x',total_cap=s.total_cap)
        self.assertTrue(any(p.name.startswith('.tmp-') for p in (self.root/'stage_00').iterdir()))
        with self.assertRaisesRegex(ValueError,'unfinished_or_unknown'):s.exists('stage_00/claim.json')
    def test_symlink_stage_and_member_rejected(self):
        s=self.store();(self.root/'stage_00').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):s.exists('stage_00/x.json')
        (self.root/'stage_00').unlink();(self.root/'stage_00').mkdir(mode=0o700);(self.root/'stage_00/x.json').symlink_to(self.root/'.store.lock')
        with self.assertRaisesRegex(ValueError,'stored_member'):s.exists('stage_00/x.json')
    def test_hardlink_unknown_and_wrong_modes_rejected(self):
        s=self.store();s.write('stage_00/x.json',b'1',total_cap=s.total_cap)
        os.link(self.root/'stage_00/x.json',self.root/'stage_00/y.json')
        with self.assertRaisesRegex(ValueError,'stored_member'):s.read('stage_00/x.json')
        (self.root/'stage_00/y.json').unlink();(self.root/'stage_00/x.json').chmod(0o600)
        with self.assertRaisesRegex(ValueError,'stored_member'):s.read('stage_00/x.json')
    def test_path_and_ancestor_rejected(self):
        s=self.store()
        for name in ('../x.json','stage_00/../x.json','stage_00/nested/x.json','/stage_00/x.json'):
            with self.assertRaises(ValueError):s.exists(name)
        (self.root/'alias').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(OSError):io.directory(str(self.root/'alias'))
    def test_exact_readpin_mode_and_duplicates(self):
        spec=fx.put(self.root/'bound',b'value',0o664);self.assertEqual(io.read_file(spec),b'value')
        with self.assertRaisesRegex(ValueError,'file_mode'):io.read_file(dict(spec,mode=0o400))
        with self.assertRaisesRegex(ValueError,'file_pin'):io.read_file(dict(spec,pin=io.pin(b'other')))
        for raw in (b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":1e999}'):
            with self.assertRaises(ValueError):io.json_read(raw)


class Source(Temp):
    def test_closed_source_and_extra_rejection(self):
        spec=fx.source(self.root/'src');self.assertEqual(sb.source(spec,'processor',lambda:None)['module.py'],b'value=123\n')
        fx.put(self.root/'src/extra.py',b'pass')
        with self.assertRaisesRegex(ValueError,'source_closed'):sb.source(spec,'processor',lambda:None)
    def test_manifest_completeness_and_mutated_code(self):
        spec=fx.source(self.root/'src');name='doc00.txt';raw=b'new code';(self.root/'src'/name).unlink();spec['files'].pop(name)
        spec['files']['unreviewed.py']=io.pin(raw);fx.put(self.root/'src/unreviewed.py',raw)
        # Remove old doc from the positively bound manifest, but omit new code.
        m=io.json_read(Path(spec['manifest']['path']).read_bytes());m['files'].pop(name);r=io.canonical(m)
        spec['manifest']=fx.put(Path(spec['manifest']['path']),r);spec['files']['FIRST_CLEAN_MANIFEST.json']=io.pin(r)
        with self.assertRaisesRegex(ValueError,'unmanifested_source'):sb.source(spec,'processor',lambda:None)
    def test_upload_is_separately_positive(self):
        spec=fx.source(self.root/'src');spec['upload_manifest']=fx.put(self.root/'src/parent_upload_manifest.private.json',io.canonical(spec['files']))
        sb.source(spec,'processor',lambda:None)
        spec['upload_manifest']['pin']=io.pin(b'wrong')
        with self.assertRaisesRegex(ValueError,'file_pin'):sb.source(spec,'processor',lambda:None)
    def test_reference_copy_mismatch(self):
        raw={'processor':{},'gaussian':{'gaussian_operator.py':b'a','reference_core.py':b'b'},'native':{'marked_native.py':b'c','packet_io.py':b'd'}}
        for ref,role,name in [('reference/gaussian_operator.py','gaussian','gaussian_operator.py'),('reference/reference_core.py','gaussian','reference_core.py'),('reference/marked_native.py','native','marked_native.py'),('reference/native_packet_io.py','native','packet_io.py')]:raw['processor'][ref]=raw[role][name]
        sb.cross_copies(raw);raw['processor']['reference/marked_native.py']=b'bad'
        with self.assertRaisesRegex(ValueError,'frozen_reference'):sb.cross_copies(raw)
    def test_verified_import_alias_restore(self):
        raw={'first.py':b'value=71\n','second.py':b'import first\nvalue=first.value+1\n'};spec=dict(directory=str(self.root),files={k:io.pin(v) for k,v in raw.items()})
        ambient=types.ModuleType('first');ambient.value=-100
        with patch.dict(sys.modules,{'first':ambient}):
            loaded=sb.load_group(spec,raw,('first','second'),'invented_verified')
            self.assertEqual(loaded['second'].value,72);self.assertIs(sys.modules['first'],ambient)
        for key in ('invented_verified_first','invented_verified_second'):sys.modules.pop(key,None)
    def test_runtime_mode_and_mutation_stream(self):
        spec=fx.put(self.root/'critical',b'critical',0o775);sb.hashed_file(spec['path'],spec['pin'],0o775,lambda:None)
        with self.assertRaisesRegex(ValueError,'runtime_file'):sb.hashed_file(spec['path'],spec['pin'],0o664,lambda:None)
        with self.assertRaisesRegex(ValueError,'runtime_hash'):sb.hashed_file(spec['path'],io.pin(b'differen'),0o775,lambda:None)
    def test_vendor_origin_and_preloaded_rejection(self):
        root=self.root/'runtime';(root/'venv').mkdir(parents=True)
        module=fx.put(root/'venv/invented_vendor.py',b'value=123\n',0o444)
        manifest=fx.put(self.root/'runtime-manifest',io.canonical(dict(files={'venv/invented_vendor.py':module['pin']})))
        spec=dict(directory=str(root),manifest=manifest,critical={},regular_mode=0o444,python=sys.executable)
        with patch.object(sb,'interpreter_check'),patch.dict(sys.modules,{},clear=True),patch.object(sys,'path',[str(root/'venv')]):
            with sb.vendor_guard(spec,{},(),lambda:None):
                imported=__import__('invented_vendor');self.assertEqual(imported.value,123)
            sys.modules.pop('invented_vendor',None)
        outside=self.root/'outside';fx.put(outside/'invented_vendor.py',b'raise AssertionError("outside code executed")\n')
        with patch.object(sb,'interpreter_check'),patch.dict(sys.modules,{},clear=True),patch.object(sys,'path',[str(outside)]):
            with sb.vendor_guard(spec,{},(),lambda:None):
                with self.assertRaisesRegex(ValueError,'import_outside_verified_runtime'):__import__('invented_vendor')
        with patch.object(sb,'interpreter_check'),patch.dict(sys.modules,{'numpy':types.ModuleType('numpy')},clear=True):
            with self.assertRaisesRegex(ValueError,'preloaded_vendor'):
                with sb.vendor_guard(spec,{},(),lambda:None):pass
    def test_guard_rejects_external_preloaded_dependency(self):
        root=self.root/'runtime';(root/'venv').mkdir(parents=True)
        manifest=fx.put(self.root/'manifest',io.canonical(dict(files={})))
        outside=fx.put(self.root/'outside.py',b'value=1\n');module=types.ModuleType('invented_dependency');module.__file__=outside['path']
        spec=dict(directory=str(root),manifest=manifest,critical={},regular_mode=0o444,python=sys.executable)
        with patch.object(sb,'interpreter_check'),patch.dict(sys.modules,{'invented_dependency':module},clear=True):
            with self.assertRaisesRegex(ValueError,'import_outside_verified_runtime'):
                with sb.vendor_guard(spec,{},(),lambda:None):pass
    def test_interpreter_is_positive_not_version_only(self):
        wrong=fx.put(self.root/'python',b'not the running interpreter',0o775)
        with self.assertRaisesRegex(ValueError,'running_interpreter_binding'):sb.interpreter_check({'python':wrong['path']})
        flags=types.SimpleNamespace(isolated=1)
        with patch.object(sys,'flags',flags),patch.object(sys,'dont_write_bytecode',True):sb.interpreter_check({'python':sys.executable})

    def test_runtime_full_invented_inventory(self):
        root=self.root/'runtime';v=root/'venv';v.mkdir(parents=True)
        members={}
        for i in range(10112):
            name='venv/f%05d'%i;fx.put(root/name,b'x',0o444);members[name]=io.pin(b'x')
        critical={}
        for i in range(10):
            p=fx.put(self.root/('critical%d'%i),b'y',0o775 if i%2 else 0o664);critical[p['path']]=dict(p['pin'],mode=p['mode'])
        links={}
        for i in range(4):
            name='venv/link%d'%i;os.symlink('f00000',root/name);links[name]='f00000'
        spec=dict(directory=str(root),manifest=fx.put(self.root/'runtime-manifest',io.canonical(dict(files=members))),symlinks=fx.put(self.root/'runtime-links',io.canonical(dict(symlinks=links))),critical=critical,python=str(v/'link0'),versions={},regular_mode=0o444)
        sb.runtime(spec,lambda:None)
        (v/'link0').unlink();os.symlink('../../unbound',v/'link0')
        with self.assertRaisesRegex(ValueError,'runtime_closed'):sb.runtime(spec,lambda:None)


class Systemd(Temp):
    def make(self,raw,**kwargs):
        self.calls=[]
        def runner(args,timeout):self.calls.append((args,timeout));return fx.answer(raw)
        s=sd.Systemd(fx.commands(self.root),runner=runner,**kwargs);s.own('eew-marked-fixture-00.service');return s
    def test_available_foreign_and_existing(self):
        s=self.make(b'LoadState=not-found\nActiveState=inactive\nControlGroup=\n');s.available('eew-marked-fixture-00.service')
        with self.assertRaisesRegex(ValueError,'foreign'):s.inspect('unowned.service',1)
        s.runner=lambda *_:fx.answer(b'LoadState=loaded\nActiveState=inactive\nControlGroup=\n')
        with self.assertRaisesRegex(ValueError,'already_exists'):s.available('eew-marked-fixture-00.service')
    def test_not_found_nonzero_is_specific_to_availability(self):
        raw=b'LoadState=not-found\nActiveState=inactive\nControlGroup=\n';s=self.make(raw)
        for code in (1,4):
            s.runner=lambda *_,c=code:fx.answer(raw,c);s.available('eew-marked-fixture-00.service')
            with self.assertRaisesRegex(ValueError,'systemctl_failed'):s.show('eew-marked-fixture-00.service',('LoadState','ActiveState','ControlGroup'),1)
        s.runner=lambda *_:fx.answer(raw,2)
        with self.assertRaisesRegex(ValueError,'systemctl_failed'):s.available('eew-marked-fixture-00.service')
        s.runner=lambda *_:fx.answer(b'LoadState=loaded\nActiveState=inactive\nControlGroup=\n',1)
        with self.assertRaisesRegex(ValueError,'systemctl_failed'):s.available('eew-marked-fixture-00.service')
    def test_inspection_exact_and_duplicate(self):
        s=self.make(b'Result=success\nActiveState=inactive\nControlGroup=\n')
        self.assertEqual(s.inspect('eew-marked-fixture-00.service',1)['result'],'success')
        with self.assertRaisesRegex(ValueError,'property_duplicate'):sd.properties(b'A=1\nA=2\n',('A',))
    def test_nonblocking_expired_stop(self):
        spawned=[]
        def popen(args,**kwargs):spawned.append(args);return types.SimpleNamespace(pid=42)
        s=self.make(b'',popen=popen)
        with patch.object(s,'_command',side_effect=AssertionError('must not rehash after expiry')):
            result=s.stop('eew-marked-fixture-00.service',0)
        self.assertFalse(result['cleanup_verified']);self.assertTrue(result['nonblocking']);self.assertEqual(len(spawned),1);self.assertFalse(self.calls)
    def test_transport_prep_is_subtracted(self):
        clock=[10.];s=self.make(b'',clock=lambda:clock[0]);original=s._command
        def command(k):clock[0]+=3;return original(k)
        s._command=command;s.run(['systemd-run','--unit=eew-marked-fixture-00'],10,'eew-marked-fixture-00.service')
        self.assertEqual(self.calls[0][1],7)
        with self.assertRaisesRegex(ValueError,'launch_unit'):s.run(['systemd-run','--unit=other'],10,'eew-marked-fixture-00.service')
    def test_live_observed_caps_not_requested_only(self):
        unit='eew-marked-fixture-00.service';group='/user.slice/'+unit
        values={'/proc/55/cgroup':('0::'+group+'\n').encode()}
        for k,v in {'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64','cpu.weight':'10','cgroup.procs':'55'}.items():values['/sys/fs/cgroup'+group+'/'+k]=v.encode()
        raw=('RuntimeMaxUSec=6min\nTimeoutStopUSec=5s\nKillMode=control-group\nActiveState=active\nCPUWeight=10\nMainPID=55\nControlGroup='+group+'\n').encode()
        env={k:'1' for k in sd.THREAD_KEYS};env['CUDA_VISIBLE_DEVICES']=''
        s=self.make(raw,read_live=lambda p,cap=16384:values[p],environ=env,pid=55,bytecode=True)
        spec=dict(unit=unit,manager_seconds=360,limits={'fixed':'invented'})
        self.assertTrue(s.live(spec)['active']);values['/sys/fs/cgroup'+group+'/memory.max']=b'max'
        with self.assertRaisesRegex(ValueError,'live_caps'):s.live(spec)
    def test_durations_and_transport_custody(self):
        self.assertEqual(sd.seconds('6min'),360);self.assertEqual(sd.seconds('5000000us'),5)
        with self.assertRaises(ValueError):sd.seconds('infinity')
        r=sd.process([sys.executable,'-c','print("x"*70000)'],3)
        self.assertEqual(r['code'],0);self.assertFalse(r['streams_complete']);self.assertTrue(r['stream_custody']['stdout']['truncated'])
        self.assertEqual(len(r['stdout']),65536)
    def test_transport_timeout_bounded(self):
        start=time.monotonic();r=sd.process([sys.executable,'-c','import time;time.sleep(3)'],.2)
        self.assertTrue(r['timeout']);self.assertFalse(r['streams_complete']);self.assertLess(time.monotonic()-start,1)


class Comparison(unittest.TestCase):
    def test_origin_projection_all528_unchanged(self):
        packet,old,pin,sha=fx.comparison();original=copy.deepcopy(old);new=cj.project(packet,old,pin,sha)
        self.assertEqual(old,original);self.assertEqual(sum(len(v['predictions']) for v in new),528)
        for before,after in zip(old['fits'],new):
            self.assertEqual(before['predictions'],after['predictions']);self.assertEqual(after['packet_sha256'],sha)
            self.assertEqual(after['origin']['original_packet_sha256'],old['original_packet_sha256']);self.assertFalse(after['origin']['old_model_reexecuted'])
            self.assertEqual(after['origin']['packet_sha256_semantics'],'comparison_population_only')
            self.assertNotIn('quantiles',after['predictions'][0]);self.assertEqual(len(after['independent_closure']),5)
    def test_historical_origin_and_hash_semantics_preserved(self):
        packet,old,pin,sha=fx.comparison();history={'archive_custody':'invented independently closed metadata','prior_origin':{'pin':'4'*64}}
        old['fits'][0]['origin']=copy.deepcopy(history);old['fits'][0]['original_packet_sha256_semantics']='canonical_original_storage_pair_pins'
        new=cj.project(packet,old,pin,sha)
        self.assertEqual(new[0]['origin']['original_fit_origin'],history)
        self.assertEqual(new[0]['origin']['original_packet_sha256_semantics'],'canonical_original_storage_pair_pins')
        self.assertEqual(new[0]['original_packet_sha256_semantics'],old['fits'][0]['original_packet_sha256_semantics'])
        self.assertEqual(old['fits'][0]['origin'],history)
    def test_roster_value_role_and_group_mismatch(self):
        for field,value in [('mw',100.),('partition','DEV'),('group','wrong'),('ordinal',1000)]:
            packet,old,pin,sha=fx.comparison();old['roster'][0][field]=value
            with self.assertRaisesRegex(ValueError,'same87'):cj.project(packet,old,pin,sha)
    def test_relabelled_old_input_and_missing_record_rejected(self):
        packet,old,pin,sha=fx.comparison();old['fits'][0]['packet_sha256']=sha
        with self.assertRaisesRegex(ValueError,'original_fit_binding'):cj.project(packet,old,pin,sha)
        packet,old,pin,sha=fx.comparison();old['fits'][0]['predictions'].pop()
        with self.assertRaisesRegex(ValueError,'old66'):cj.project(packet,old,pin,sha)
    def test_wrong_forecast_time_or_target_rejected(self):
        for key,value in [('horizon',4),('target',-100),('ordinal',0)]:
            packet,old,pin,sha=fx.comparison();old['fits'][0]['predictions'][0][key]=value
            with self.assertRaisesRegex(ValueError,'old_record'):cj.project(packet,old,pin,sha)


class Authority(Temp):
    def make(self):
        d=object.__new__(dep.Deployment);d.config={'invented':True};d.inputs=dict(feature_authority=b'native proof fixture',strong_authority=b'old proof fixture',strong_results=b'old numeric fixture');d.authority=fx.root_receipt;d.clock=lambda:20.
        g=dict(source_pins={},runtime_pin=io.pin(b'rt'),input_pins={},funding_pin=io.pin(b'fixture funding is NOT real funding'))
        spec=dict(index=0,unit='eew-marked-fixture-00.service',manager_seconds=360)
        return d,g,spec
    def test_authority_factory_receives_full_config_contract(self):
        source=Path(bootstrap.__file__).read_text()
        self.assertIn('authority.make_validator(config,io=io,source_binding=',source)
        self.assertNotIn('authority.verify',source)
    def test_callback_exact_scope_and_evidence(self):
        d,g,s=self.make();r=d.root_receipt(g,s,b'publication','parent');self.assertEqual(r['scope']['phase'],'parent')
        def bad(scope,raw,now):
            r=fx.root_receipt(scope,raw,now);r['evidence_pins']['feature']=io.pin(b'other');return r
        d.authority=bad
        with self.assertRaisesRegex(ValueError,'authority_evidence'):d.root_receipt(g,s,b'publication','parent')
    def test_callback_booleans_and_expired_lease_rejected(self):
        d,g,s=self.make();d.authority=lambda *_:True
        with self.assertRaisesRegex(ValueError,'root_authority'):d.root_receipt(g,s,b'pub','parent')
        def short(scope,raw,now):
            r=fx.root_receipt(scope,raw,now);r['expires']=now+1;return r
        d.authority=short
        with self.assertRaisesRegex(ValueError,'authority_lease'):d.root_receipt(g,s,b'pub','parent')
    def test_whole_and_source_clock_no_reset(self):
        d,_,_=self.make();d.request=dict(gate=dict(experiment_begin=0),stage=dict(source_seconds=300));d.science_begin=0
        d.clock=lambda:301
        with self.assertRaisesRegex(ValueError,'stage_source'):d.check()
        d.science_begin=None;d.clock=lambda:7201
        with self.assertRaisesRegex(ValueError,'whole_source'):d.check()
    def test_bootstrap_read_refuses_links_hash_mismatch(self):
        p=fx.put(self.root/'source',b'pass\n');self.assertEqual(bootstrap._read(p['path'],100,p['pin']['sha256']),b'pass\n')
        with self.assertRaisesRegex(ValueError,'bootstrap_hash'):bootstrap._read(p['path'],100,'0'*64)
        (self.root/'link').symlink_to(self.root/'source')
        with self.assertRaises(OSError):bootstrap._read(str(self.root/'link'),100)


if __name__=='__main__':unittest.main()

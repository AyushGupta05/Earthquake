import copy
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parent/'reference'))
import secure_io as io
import control
import journal
import systemd_adapter as sd_reference
import root_glue
import stop
sys.modules['parent_stop']=stop
import parent
import entry


def answer(body=b'',code=0):
    return dict(code=code,timeout=False,stdout=body,stderr=b'',streams_complete=True,exception=None,
                stream_custody={k:dict(original_bytes=len(b),original_sha256=io.pin(b)['sha256'],retained_bytes=len(b),truncated=False,complete_observation=True)
                                for k,b in (('stdout',body),('stderr',b''))})


class FakeOS:
    def __init__(self,root):
        self.root=Path(root);self.now=1000000.;self.timer=False;self.stop_service=False
        self.boot='00000000-1111-2222-3333-444444444444';self.commands=[];self.calls=[];self.retain=[]
        self.active=set();self.unclosed=False;self.fail_at=None;self.retain_failure=False;self.current_failure=False
        self.bad_due=False;self.absence_code=0;self.read_redirect={};self.own_units=set()
        def put(name,value):
            b=io.canonical(value);f=self.root/name;f.write_bytes(b);f.chmod(0o400)
            return dict(path=str(f),pin=io.pin(b),mode=0o400)
        self.put=put
        commands={k:put(k,{}) for k in ('systemctl','systemd_run')};bash=put('bash',{})
        for k,s in [*commands.items(),('bash',bash)]:
            original=copy.deepcopy(s);s['path']='/usr/bin/'+{'systemd_run':'systemd-run'}.get(k,k);self.read_redirect[s['path']]=original
        self.io=mock.Mock(wraps=io);self.io.read_file.side_effect=lambda s,*args:io.read_file(self.read_redirect.get(s['path'],s),*args)
        self.install=dict(schema='ROOT-L-stop-install-v1',experiment_id='invented-l9',whole_begin=self.now,lease_deadline=self.now+7400,
                          commands=commands,bash=bash,stop_store_directory=str(self.root/'stopstore'),boot_id=self.boot)
        self.sd=types.SimpleNamespace(process=self.process,live_read=lambda _:self.boot.encode(),Systemd=lambda _:self)

    def clock(self):return self.now
    def own(self,unit):self.own_units.add(unit)
    def available(self,unit):
        if unit in self.active:raise ValueError('busy')
    def process(self,args,timeout):
        self.commands.append(args);self.now+=.01
        if any(x.startswith('--on-active=')for x in args):
            self.timer=True;self.stop_service=True
            self.interval=float(next(x.split('=',1)[1][:-1]for x in args if x.startswith('--on-active=')))
            self.due=self.now+self.interval+(20 if self.bad_due else 0);self.script=args[-1]
            return answer()
        if 'stop'in args:
            unit=args[-1]
            if unit.endswith('.timer'):
                self.timer=False;self.stop_service=False;return answer()
            if unit.endswith('-stop.service'):return answer(code=0 if self.stop_service else 5)
            if self.unclosed:self.active.add(unit);return answer(code=1)
            self.active.discard(unit);return answer(code=5)
        unit=args[args.index('show')+1];fields=args[-1].split('=',1)[1].split(',')
        if 'NextElapseUSecMonotonic'in fields:
            values=dict(LoadState='loaded',ActiveState='active'if self.timer else'inactive',Unit=unit[:-6]+'.service',AccuracyUSec='1s',
                        TimersMonotonic='{ OnActiveUSec=%.6fs ; }'%self.interval,NextElapseUSecMonotonic='%.6fs'%self.due)
        elif 'ExecStart'in fields:
            values=dict(LoadState='loaded',ActiveState='inactive',ExecStart='{ path=/usr/bin/bash ; argv[]=/usr/bin/bash '+self.script+' ; ignore_errors=no ; }')
        else:
            active=unit in self.active
            values=dict(LoadState='loaded'if active else'not-found',ActiveState='active'if active else'inactive')
            if 'ControlGroup'in fields:values['ControlGroup']='/live'if active else''
        return answer(('\n'.join(k+'='+v for k,v in values.items())+'\n').encode(),code=self.absence_code if values.get('LoadState')=='not-found' else 0)

    def install_timer(self):
        return stop.install_stop(self.install,expected_pin=io.pin(io.canonical(self.install)),io=self.io,sd=self.sd,clock=self.clock)

    def prepare_parent(self):
        receipt=self.install_timer();fixedpin=io.pin(b'fixture');g=dict(schema='shared-reference-AR-L-nine-stage-config-v1',study=control.STUDY,
            feature_schema='earthquake-TRAIN115-marked-noise-observations-v1',feature_study='earthquake-TRAIN115-marked-noise-study-v1',
            experiment_id='invented-l9',whole_begin=self.install['whole_begin'],lease_deadline=self.install['lease_deadline'],
            source_pins={k:fixedpin for k in control.SOURCES},runtime_pin=fixedpin,input_pins={k:fixedpin for k in control.INPUTS},
            funding_pin=fixedpin,publication_pin=fixedpin,protocol_pin=fixedpin,storage_limit_bytes=9*64*1024*1024)
        for n in('child','retained'):(self.root/n).mkdir(mode=0o700)
        r=json.loads(io.read_file(receipt));current=self.put('current',dict(timer=r['timer'],boot_id=self.boot,retention_directory=str(self.root/'retained')))
        bootstrap=self.put('bootstrap',{});held=dict(execution=g,execution_pin=io.pin(io.canonical(g)),launch=dict(bootstrap=bootstrap,commands=self.install['commands'],store_directory=str(self.root/'child')),evidence=dict(current=current))
        root=self.put('root',held);req=dict(schema='ROOT-L-parent-entry-v1',root_spec=root,expected_root_pin=root['pin'],bootstrap_spec=bootstrap,
            entry_source_spec=self.put('entry',{}),parent_source_spec=self.put('parent',{}),stop_source_spec=self.put('stop',{}),
            stop_request_spec=self.put('stoprequest',self.install),stop_receipt_spec=receipt,parent_store_directory=str(self.root/'parentstore'))
        fake=self
        class Primitives:
            def retain_return(_,index,result,inventory,observed,request):
                fake.retain.append((index,result,inventory,observed,request))
                if fake.retain_failure:raise OSError('invented retention failure')
                return dict(schema='root-L-last-return-retention-v1',stage=index,return_pin=io.pin(io.canonical(result)),proof_pin=io.pin(b'actual fixture'))
        prim=Primitives()
        def factory(h,**kw):
            assert h==held and kw['expected_root_pin']==root['pin']and kw['source_begin']is None
            return prim,object()
        def run_parent(h,index,**kw):
            assert h==held and kw['expected_pin']==root['pin']and kw['retain_return']==prim.retain_return
            if fake.current_failure:raise ValueError('current authority failure before dispatch')
            fake.calls.append(index);fake.now+=1
            result=dict(status='incomplete'if index==fake.fail_at else'complete',stage=index)
            kw['journal'].object(index,'closed.json',result)
            kw['retain_return'](index,result,kw['journal'].inventory(),answer(),dict(stage=index))
            return result
        modules=dict(secure_io=self.io,control=control,systemd_adapter=self.sd,journal=journal,
                     root_primitives=types.SimpleNamespace(make_primitives=factory),root_glue=types.SimpleNamespace(run_parent=run_parent))
        return req,held,modules


class Tests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.h=FakeOS(str(Path(t.name).resolve()))

    def test_absolute_timer_subtracts_elapsed_and_has_nine_targets(self):
        self.h.now+=137;spec=self.h.install_timer();r=json.loads(io.read_file(spec))
        self.assertLessEqual(r['timer']['deadline'],self.h.install['whole_begin']+7400)
        self.assertGreaterEqual(r['timer']['deadline'],self.h.install['whole_begin']+7390)
        self.assertEqual(io.read_file(r['stop_script']).count(b'/usr/bin/systemctl --user stop'),9)
        self.assertEqual(self.h.install['whole_begin'],1000000.)

    def test_week_day_monotonic_format(self):
        self.assertAlmostEqual(stop.duration('1w 3d 18h 2min 25.750278s'),928945.750278)
        with self.assertRaises(ValueError):stop.duration('1w junk')

    def test_late_timer_install_terminal_and_no_reinstall(self):
        self.h.bad_due=True
        with self.assertRaisesRegex(ValueError,'fixed_stop_due'):self.h.install_timer()
        self.assertEqual(sum(any(x.startswith('--on-active=')for x in a)for a in self.h.commands),1)
        self.assertTrue((self.h.root/'stopstore/stage_00/failure.json').exists())

    def test_wrong_boot_prevents_timer(self):
        self.h.install['boot_id']='different'
        with self.assertRaisesRegex(ValueError,'install_boot'):self.h.install_timer()
        self.assertFalse(self.h.timer)

    def test_existing_namespace_cannot_rearm(self):
        self.h.install_timer()
        with self.assertRaises(FileExistsError):self.h.install_timer()
        self.assertEqual(sum(any(x.startswith('--on-active=')for x in a)for a in self.h.commands),1)

    def test_wrong_expected_install_pin(self):
        with self.assertRaisesRegex(ValueError,'held_install_request'):
            stop.install_stop(self.h.install,expected_pin=io.pin(b'bad'),io=self.h.io,sd=self.h.sd,clock=self.h.clock)

    def test_missing_status_one_four_accepted_only_exact(self):
        for code in(1,4):self.assertEqual(stop.props(answer(b'LoadState=not-found\nActiveState=inactive\n',code),absence=True)['LoadState'],'not-found')
        with self.assertRaises(ValueError):stop.props(answer(b'LoadState=loaded\nActiveState=active\n',4),absence=True)

    def test_loaded_unknown_nonzero_stop_not_benign(self):
        self.h.install_timer();self.h.unclosed=True;records=[]
        r=stop.cleanup(self.h.install,io=self.h.io,sd=self.h.sd,record=records.append,clock=self.h.clock)
        self.assertEqual(r['status'],'incomplete');self.assertTrue(self.h.timer)
        self.assertFalse(any('stop'in a and a[-1].endswith('.timer')for a in self.h.commands))

    def test_timer_stop_and_dormant_service_separate_missing_benign(self):
        self.h.install_timer();r=stop.cleanup(self.h.install,io=self.h.io,sd=self.h.sd,record=lambda _:None,clock=self.h.clock)
        self.assertEqual(r['status'],'complete');self.assertFalse(self.h.timer)
        stops=[a for a in self.h.commands if 'stop'in a]
        self.assertEqual(len(stops),11);self.assertTrue(stops[-2][-1].endswith('.timer'));self.assertTrue(stops[-1][-1].endswith('-stop.service'))

    def test_full_fixed_nine_calls_concrete_retainer(self):
        req,h,mods=self.h.prepare_parent();r=parent.run(req,h,mods,clock=self.h.clock)
        self.assertEqual(r['status'],'complete');self.assertEqual(self.h.calls,list(range(9)))
        self.assertEqual([a[0]for a in self.h.retain],list(range(9)));self.assertFalse(self.h.timer)
        self.assertEqual(h['execution']['whole_begin'],1000000.)

    def test_stage_failure_stops_all_later_attempts(self):
        req,h,mods=self.h.prepare_parent();self.h.fail_at=2;r=parent.run(req,h,mods,clock=self.h.clock)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(self.h.calls,[0,1,2])
        self.assertTrue((self.h.root/'parentstore/stage_02/actual_parent_return.json').exists())
        self.assertFalse((self.h.root/'parentstore/stage_03').exists())

    def test_retainer_failure_never_advances(self):
        req,h,mods=self.h.prepare_parent();self.h.retain_failure=True;r=parent.run(req,h,mods,clock=self.h.clock)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(self.h.calls,[0])
        report=json.loads(io.read_file(r['final_report']));self.assertIn('retention failure',report['failure']['reason'])

    def test_current_authority_failure_before_dispatch(self):
        req,h,mods=self.h.prepare_parent();self.h.current_failure=True;r=parent.run(req,h,mods,clock=self.h.clock)
        self.assertEqual(r['status'],'incomplete');self.assertEqual(self.h.calls,[])

    def test_root_pin_mismatch_no_claim(self):
        req,h,mods=self.h.prepare_parent();req['expected_root_pin']=io.pin(b'wrong')
        with self.assertRaises(ValueError):parent.run(req,h,mods,clock=self.h.clock)
        self.assertEqual(self.h.calls,[])

    def test_duplicate_parent_never_replays(self):
        req,h,mods=self.h.prepare_parent();parent.run(req,h,mods,clock=self.h.clock)
        with self.assertRaises(FileExistsError):parent.run(req,h,mods,clock=self.h.clock)
        self.assertEqual(self.h.calls,list(range(9)))

    def test_whole_cannot_reset_on_expiry(self):
        req,h,mods=self.h.prepare_parent();self.h.now=h['execution']['whole_begin']+7399
        r=parent.run(req,h,mods,clock=self.h.clock);self.assertEqual(r['status'],'incomplete');self.assertEqual(self.h.calls,[])

    def test_final_write_late_never_passes(self):
        req,h,mods=self.h.prepare_parent();original=stop.store_object
        def delayed(store,index,name,value,io):
            p=original(store,index,name,value,io)
            if name=='final_report.json':self.h.now+=7401
            return p
        with mock.patch.object(stop,'store_object',delayed):r=parent.run(req,h,mods,clock=self.h.clock)
        self.assertEqual(r['status'],'incomplete');self.assertTrue((self.h.root/'parentstore/stage_09/late_finalization.json').exists())

    def test_entry_read_hash_mode_symlink(self):
        spec=self.h.put('a',{'x':1});self.assertEqual(entry.read(spec),io.read_file(spec))
        bad=copy.deepcopy(spec);bad['pin']=io.pin(b'wrong')
        with self.assertRaises(ValueError):entry.read(bad)
        alias=self.h.root/'alias';alias.symlink_to(spec['path']);bad=dict(spec,path=str(alias))
        with self.assertRaises(OSError):entry.read(bad)

    def test_real_frozen_glue_calls_actual_return_retainer_abi(self):
        # Exercise unchanged run_parent itself, not a rewritten imitation.
        req,h,mods=self.h.prepare_parent();returned=dict(status='incomplete',errors=[],stage=0)
        mods.update(projection=object(),comparator_population=object(),bridge=object(),runtime_adapter=object())
        retained=[];fake_root=types.SimpleNamespace(g=h['execution'],h=h,io=io,c=types.SimpleNamespace(run_stage=lambda *a,**k:returned),requests={})
        class FakeJournal:
            def inventory(self):return {'invented':(1,1,0,1)}
        def retain(index,result,inventory,observed,request):
            retained.append((index,result,inventory,observed,request))
            return dict(schema='root-L-last-return-retention-v1',stage=index,return_pin=io.pin(io.canonical(result)),proof_pin=io.pin(b'proof'))
        with mock.patch.object(root_glue,'Root',return_value=fake_root),mock.patch.object(root_glue,'compose',return_value=object()):
            r=root_glue.run_parent(h,0,expected_pin=req['expected_root_pin'],root_spec=req['root_spec'],modules=mods,primitives=object(),custody=object(),journal=FakeJournal(),systemd=self.h,retain_return=retain,clock=self.h.clock)
        self.assertIs(r,returned);self.assertEqual(retained[0][0],0);self.assertIs(retained[0][1],returned);self.assertIsNone(retained[0][3])


if __name__=='__main__':unittest.main()

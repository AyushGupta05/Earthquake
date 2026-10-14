"""Focused9stage control/custody/FS tests, entirely invented and stdlib-only."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import fixtures as f
import control as c
import child
import journal
import secure_io as io

class ControlTests(unittest.TestCase):
    def test_exact9_stages_caps_one_clock_resource_limits(self):
        clock,j,d,g=f.setup();specs=[c.spec(g,i)for i in range(9)]
        self.assertEqual([s['kind']for s in specs],['admission','fit','score','fit','score','aggregate','audit_fit','audit_fit','audit_aggregate'])
        self.assertEqual(sum(s['source_seconds']for s in specs),5700);self.assertEqual(sum(s['manager_seconds']for s in specs),6240)
        for s in specs:
            self.assertEqual(s['limits'],c.LIMITS);self.assertIn('RuntimeMaxSec='+str(s['manager_seconds']),c.command(s,'/fake/python','pass'))
        for index in(-1,9,False):
            with self.assertRaises(ValueError):c.spec(g,index)

    def test_unit_namespace_matches_frozen_Systemd_without_weakening_owner_guard(self):
        import importlib.util
        path=Path(__file__).parent/'reference/systemd_adapter.py';spec=importlib.util.spec_from_file_location('frozen_systemd_fixture',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        owner=object.__new__(module.Systemd);owner.owned=set();clock,j,d,g=f.setup()
        for index in range(9):owner.own(c.spec(g,index)['unit'])
        self.assertEqual(len(owner.owned),9)
        with self.assertRaises(ValueError):owner.own('eew-L-invented-only-00.service')

    def test_all9_once_producer300_scores132_and_independent42_negative_complete(self):
        clock,j,d,g=f.setup()
        for index in range(9):
            returned=c.run_stage(g,c.config_pin(g),index,j,d,clock=clock);self.assertEqual(returned['status'],'complete',returned)
        self.assertEqual(d.called,list(range(9)))
        for i in(1,3):self.assertEqual(len([name for n,name in j.files if n==i and name.startswith('update_')]),300)
        for i in(2,4):self.assertEqual(len([name for n,name in j.files if n==i and name.startswith('forecast_')]),66)
        for i in(6,7):self.assertEqual(len([name for n,name in j.files if n==i and name.startswith('record_')]),66)
        value=c.parse(j.read(8,'result.json'));self.assertFalse(value['advance']['pass_all']);self.assertEqual(len(value['advance']['checks'])+len(value['advance']['additional']),42)
        self.assertEqual(value['record_counts']['total'],1056)
        with self.assertRaises(FileExistsError):c.run_stage(g,c.config_pin(g),8,j,d,clock=clock)
        self.assertEqual(len(d.called),9)

    def test_out_of_order_no_held_ROOTreturn_no_import_dispatch(self):
        clock,j,d,g=f.setup()
        with self.assertRaises(KeyError):c.run_stage(g,c.config_pin(g),1,j,d,clock=clock)
        self.assertEqual(d.called,[]);c.run_stage(g,c.config_pin(g),0,j,d,clock=clock);d.noheld=True
        with self.assertRaises(ValueError):c.run_stage(g,c.config_pin(g),1,j,d,clock=clock)
        self.assertEqual(d.called,[0])

    def test_config_source_pin_held_authority_and_remaining_whole_budget(self):
        for bad in('pin','proof','clock','identity','empty'):
            clock,j,d,g=f.setup();expected=c.config_pin(g)
            if bad=='pin':expected=io.pin(b'unknown')
            if bad=='proof':d.proof_bad=True
            if bad=='clock':clock.now=g['whole_begin']+7000
            if bad=='identity':g['schema']='marked-seven-audit-deployment-v1'
            if bad=='empty':g['source_pins']['processor']=io.pin(b'');expected=c.config_pin(g)
            with self.assertRaises(ValueError):c.run_stage(g,expected,0,j,d,clock=clock)
            self.assertEqual(d.called,[])

    def test_before_import_binder_or_live_caps_failure_terminal(self):
        for kind in('caps','bind'):
            clock,j,d,g=f.setup()
            if kind=='caps':d.live_bad=True
            else:d.bind_failure=True
            result=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock);self.assertEqual(result['status'],'incomplete')
            self.assertIn((0,'child_report.json'),j.files);self.assertIn((0,'late_or_failed.json'),j.files)
            self.assertFalse(any(name.startswith('initial_')for _,name in j.files))

    def test_full_EOF_counts_hash_incomplete_transport_and_stop(self):
        for kind in('hash','EOF','timeout','code','truncation'):
            clock,j,d,g=f.setup()
            def change(answer):
                if kind=='hash':answer['stream_custody']['stdout']['original_sha256']='0'*64
                if kind=='EOF':answer['stream_custody']['stdout']['complete_observation']=False
                if kind=='timeout':answer['timeout']=True
                if kind=='code':answer['code']=1
                if kind=='truncation':answer['stream_custody']['stdout']['original_bytes']+=1;answer['stream_custody']['stdout']['truncated']=True
            d.answer_change=change;result=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
            self.assertEqual(result['status'],'incomplete');self.assertIn((0,'manager_return.json'),j.files)
            if kind in('timeout','code'):self.assertEqual(len(d.stopped),1)

    def test_uncertain_cgroup_stops_once_reconciles_never_promotes(self):
        clock,j,d,g=f.setup();d.post_bad=True;result=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(result['status'],'incomplete');self.assertEqual(len(d.stopped),1);self.assertIn((0,'post_after_stop.json'),j.files)

    def test_claim_fsync_failure_prevents_dispatch(self):
        clock,j,d,g=f.setup();j.fail='dispatch.json'
        with self.assertRaises(OSError):c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(d.called,[])

    def test_child_partial_callback_or_source_expiry_retains_evidence(self):
        clock,j,d,g=f.setup();c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        j.fail='update_002.json';result=c.run_stage(g,c.config_pin(g),1,j,d,clock=clock)
        self.assertEqual(result['status'],'incomplete');self.assertEqual(c.parse(j.read(1,'latest_update.json'))['update'],2)
        self.assertIn((1,'update_001.json'),j.files)

    def test_late_parent_final_persistence_marker_blocks_next(self):
        clock,j,d,g=f.setup()
        def after(i,name):
            if name=='closed.json':clock.now=g['whole_begin']+7401
        j.after=after;result=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(result['status'],'incomplete');self.assertIn((0,'late_or_failed.json'),j.files)
        with self.assertRaises(ValueError):c.run_stage(g,c.config_pin(g),1,j,d,clock=clock)

    def test_child_late_source_finalization_persists_full_result_then_failure(self):
        clock,j,d,g=f.setup()
        def after(i,name):
            if name=='result.json':clock.now+=301
        j.after=after;returned=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(returned['status'],'incomplete');self.assertEqual(c.parse(j.read(0,'result.json'))['status'],'admitted')
        self.assertIn((0,'child_report.json'),j.files)

    def test_issued_child_receipt_lease_hard_bound(self):
        clock,j,d,g=f.setup();real=d.authorize
        def shorter(scope,docs,now):
            proof=real(scope,docs,now)
            if scope['phase']=='child':proof['expires']=now+1
            return proof
        d.authorize=shorter
        def after(i,name):
            if name=='result.json':clock.now+=2
        j.after=after;result=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(result['status'],'incomplete');self.assertIn((0,'child_failure.json'),j.files)

    def test_audit_returned_failure_retained_not_advanced_or_retried(self):
        clock,j,d,g=f.setup()
        for i in range(6):self.assertEqual(c.run_stage(g,c.config_pin(g),i,j,d,clock=clock)['status'],'complete')
        def fail(*args,**kw):
            value=dict(schema='shared-reference-AR-L-independent-audit-v1',status='fail',checked=0,records=[],reason='invented');kw['retain'](value);return value
        d.auditor.audit_fit=fail;result=c.run_stage(g,c.config_pin(g),6,j,d,clock=clock)
        self.assertEqual(result['status'],'incomplete');self.assertEqual(c.parse(j.read(6,'result.json'))['status'],'fail')
        self.assertIn((6,'audit_report.json'),j.files)
        with self.assertRaises(ValueError):c.run_stage(g,c.config_pin(g),7,j,d,clock=clock)

    def test_parent_original_stream_fields_not_relabelled_as_prefix_hash(self):
        clock,j,d,g=f.setup()
        def change(a):
            a['stdout']=b'a'*65536
            a['stream_custody']['stdout']=dict(original_bytes=65537,original_sha256=io.pin(b'a'*65537)['sha256'],retained_bytes=65536,truncated=True,complete_observation=True)
        d.answer_change=change;c.run_stage(g,c.config_pin(g),0,j,d,clock=clock);m=c.parse(j.read(0,'manager_return.json'))
        self.assertEqual(m['stdout']['retained_pin'],io.pin(b'a'*65536));self.assertEqual(m['stream_custody']['stdout']['original_sha256'],io.pin(b'a'*65537)['sha256'])
    def test_exact_full_permitted_streams_fit_control_cap(self):
        clock,j,d,g=f.setup()
        def change(a):
            a['stdout']=b'x'*65536;a['stderr']=b'y'*131072
            a['stream_custody']={k:dict(original_bytes=len(a[k]),original_sha256=io.pin(a[k])['sha256'],retained_bytes=len(a[k]),truncated=False,complete_observation=True)for k in('stdout','stderr')}
        d.answer_change=change;returned=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(returned['status'],'complete');self.assertGreater(len(j.read(0,'manager_return.json')),262144);self.assertLess(len(j.read(0,'manager_return.json')),journal.CONTROL)

    def test_audit_aggregate_missing42_guard_report_retained_and_rejected(self):
        clock,j,d,g=f.setup()
        for i in range(8):self.assertEqual(c.run_stage(g,c.config_pin(g),i,j,d,clock=clock)['status'],'complete')
        real=d.auditor.aggregate
        def missing(*a,**kw):
            value=real(*a,**kw);value['advance']['checks'].pop();return value
        d.auditor.aggregate=missing;returned=c.run_stage(g,c.config_pin(g),8,j,d,clock=clock)
        self.assertEqual(returned['status'],'incomplete');self.assertEqual(len(c.parse(j.read(8,'result.json'))['advance']['checks']),23)
        self.assertIn((8,'audit_report.json'),j.files)

    def test_child_separately_held_pin_cannot_derive_from_request(self):
        clock,j,d,g=f.setup();s=c.spec(g,0);receipt=c.authorize(g,s,'parent',d,clock());request=dict(schema='shared-reference-AR-L-stage-request-v1',config=g,config_pin=c.config_pin(g),stage=s,dispatch_begin=clock(),previous=[],parent_authority=receipt)
        j.object(0,'dispatch.json',request)
        returned=child.execute(request,j,d,expected_config_pin=io.pin(b'unknown-ROOT-config'),source_begin=clock(),clock=clock)
        self.assertEqual(returned['status'],'incomplete');self.assertFalse(any(name.startswith('initial_')for _,name in j.files))

    def test_child_lease_crossed_after_complete_report_before_managerEOF_rejects(self):
        clock,j,d,g=f.setup();real=d.authorize
        def shorter(scope,docs,now):
            value=real(scope,docs,now)
            if scope['phase']=='child':value['expires']=now+1
            return value
        d.authorize=shorter
        def afterEOF(answer):clock.now+=2
        d.answer_change=afterEOF;returned=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(c.parse(j.read(0,'child_report.json'))['status'],'complete')
        self.assertEqual(returned['status'],'incomplete');self.assertIn('late_transport',returned['errors'])
        self.assertIn((0,'manager_return.json'),j.files);self.assertIn((0,'result.json'),j.files)

    def test_parent_final_closed_write_crossing_child_lease_is_terminal(self):
        clock,j,d,g=f.setup();real=d.authorize
        def shorter(scope,docs,now):
            value=real(scope,docs,now)
            if scope['phase']=='child':value['expires']=now+1
            return value
        d.authorize=shorter
        def after(i,name):
            if name=='closed.json':clock.now+=2
        j.after=after;returned=c.run_stage(g,c.config_pin(g),0,j,d,clock=clock)
        self.assertEqual(returned['status'],'incomplete');self.assertIn('late_finalization',returned['errors']);self.assertIn((0,'late_or_failed.json'),j.files)
        with self.assertRaises(ValueError):c.run_stage(g,c.config_pin(g),1,j,d,clock=clock)


class JournalTests(unittest.TestCase):
    def make(self):
        temporary=tempfile.TemporaryDirectory();path=Path(temporary.name).resolve();path.chmod(0o700);return temporary,path,journal.Journal(str(path))
    def test_fs_owner_mode_claim_once_latest_only_and_300receipt_names(self):
        temp,path,j=self.make()
        try:
            j.object(0,'dispatch.json',{'fake':True})
            with self.assertRaises(ValueError):j.object(0,'dispatch.json',{'fake':True})
            for i in range(1,301):j.write(1,'latest_update.json',io.canonical({'update':i}),replace=True);j.object(1,'update_%03d.json'%i,{'update':i})
            self.assertEqual(c.parse(j.read(1,'latest_update.json'))['update'],300)
            self.assertEqual(len(list((path/'stage_01').iterdir())),301);self.assertEqual((path/'stage_01/latest_update.json').stat().st_mode&0o777,0o400)
            with self.assertRaises(ValueError):j.write(1,'result.json',b'{}',replace=True)
        finally:j.close();temp.cleanup()
    def test_FS_link_mode_extra_temp_poison_storage_guard(self):
        for change in('mode','link','temp'):
            temp,path,j=self.make()
            try:
                j.object(0,'dispatch.json',{'fake':True});p=path/'stage_00/dispatch.json'
                if change=='mode':p.chmod(0o600)
                if change=='link':(path/'stage_00/claim.json').symlink_to(p)
                if change=='temp':(path/'stage_00/.tmp-failed').write_bytes(b'partial')
                with self.assertRaises(ValueError):j.inventory()
            finally:j.close();temp.cleanup()
    def test_replacement_temporary_bytes_cannot_exceed_stage_or_payload_reserve(self):
        temp,path,j=self.make()
        try:
            with mock.patch.object(journal,'STAGE',1024),mock.patch.object(journal,'RESERVE',128):
                j.write(0,'latest_update.json',b'x'*300,replace=True);j.write(0,'record_000.json',b'y'*500)
                # Final payload700 would fit, but the two simultaneous copies total1000.
                with self.assertRaises(ValueError):j.write(0,'latest_update.json',b'z'*200,replace=True)
                self.assertEqual(j.read(0,'latest_update.json'),b'x'*300)
                self.assertEqual(sorted(p.name for p in (path/'stage_00').iterdir()),['latest_update.json','record_000.json'])
                j.write(0,'latest_update.json',b'a'*90,replace=True)
                self.assertEqual(j.read(0,'latest_update.json'),b'a'*90)
        finally:j.close();temp.cleanup()

    def test_member_caps_and_nine_namespace_no_old_names(self):
        temp,path,j=self.make()
        try:
            with self.assertRaises(ValueError):j.write(9,'result.json',b'{}')
            with self.assertRaises(ValueError):j.write(0,'manager_return.json',b'x'*(journal.CONTROL+1))
            with self.assertRaises(ValueError):j.write(0,'result.json',b'x'*(journal.MEMBER+1))
            j.object(8,'closed.json',{'fake':True});self.assertIn('stage_08',j.inventory())
        finally:j.close();temp.cleanup()

if __name__=='__main__':unittest.main()

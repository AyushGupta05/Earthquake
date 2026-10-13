"""Invented callback tests; no OS calls or actual dataset access."""
import unittest
import controller as c
from fixtures import fixture

class Tests(unittest.TestCase):
    def run_stage(self,fx,i):
        g,t,s,a=fx; return c.run_stage(g,i,s,a,clock=t)
    def test_all_fixed_stages_negative_science_is_complete(self):
        fx=fixture(); g,t,s,a=fx
        for i in range(14):
            r=self.run_stage(fx,i); self.assertEqual(r['status'],'complete',r)
        self.assertIs(r['scientific_pass'],False); self.assertEqual(a.runs,list(range(14)))
        self.assertEqual(a.processor.calls,['admission']+[(k,seed,arm) for seed,arm in c.ORDER for k in ('fit','score')]+['aggregate'])
        self.assertEqual(sum('/update_' in k for k in s.values),1800)
        self.assertEqual(sum('/latest_update' in k for k in s.values),6)
        self.assertEqual(sum('/forecast_' in k for k in s.values),396)
    def test_no_optimizer_before_all_admission_initials(self):
        fx=fixture(); fx[3].processor.skip='initial'; r=self.run_stage(fx,0)
        self.assertEqual(r['status'],'incomplete'); self.assertEqual(fx[3].processor.calls,['admission'])
        with self.assertRaises(Exception): self.run_stage(fx,1)
    def test_duplicate_and_out_of_order_forbidden(self):
        fx=fixture()
        with self.assertRaises(Exception): self.run_stage(fx,1)
        self.run_stage(fx,0)
        with self.assertRaises(FileExistsError): self.run_stage(fx,0)
        self.assertEqual(fx[3].runs,[0])
    def test_funding_not_invented_or_bypassed(self):
        fx=fixture(); fx[3].authorization_bad=True
        with self.assertRaisesRegex(ValueError,'authority'): self.run_stage(fx,0)
        self.assertEqual(fx[3].runs,[])
    def test_authority_lease_late_after_callback(self):
        fx=fixture(); a=fx[3]; old=a.authorize
        def delayed(g,spec,now):
            proof=old(g,spec,now); fx[1].now+=1; return proof
        a.authorize=delayed
        with self.assertRaisesRegex(ValueError,'expired'): self.run_stage(fx,0)
    def test_no_new_stage_with_insufficient_science_budget(self):
        fx=fixture(); fx[1].now+=6841
        with self.assertRaisesRegex(ValueError,'budget'): self.run_stage(fx,0)
        self.assertEqual(fx[3].runs,[])
    def test_input_pin_corruption_stops_before_import(self):
        fx=fixture(); fx[3].inputs['feature_archive']=b'wrong'
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertEqual(fx[3].processor.calls,[])
    def test_live_owned_limits_before_science(self):
        fx=fixture(); fx[3].bad_live=True
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertEqual(fx[3].processor.calls,[])
    def test_feature_identity_not_rewritten(self):
        fx=fixture(); fx[0]['feature_study']=c.STUDY
        with self.assertRaisesRegex(ValueError,'identity'): self.run_stage(fx,0)
    def test_partial_update_checkpoint_and_history_retained(self):
        fx=fixture(); self.run_stage(fx,0); fx[3].processor.failure_step=17
        r=self.run_stage(fx,1); self.assertEqual(r['status'],'incomplete')
        latest=c.parse(fx[2].values['stage_01/latest_update.json']); self.assertEqual(latest['update'],16); self.assertEqual(len(latest['history']),16)
        self.assertFalse(fx[2].exists('stage_01/result.json'))
        with self.assertRaises(Exception): self.run_stage(fx,2)
    def test_final_write_failure_never_starts_score(self):
        fx=fixture(); self.run_stage(fx,0); fx[2].fail='stage_01/result.json'
        r=self.run_stage(fx,1); self.assertEqual(r['status'],'incomplete')
        self.assertEqual(c.parse(fx[2].values['stage_01/latest_update.json'])['update'],300)
        with self.assertRaises(Exception): self.run_stage(fx,2)
    def test_score_only_uses_saved_checkpoint(self):
        fx=fixture(); self.run_stage(fx,0); self.run_stage(fx,1)
        before=fx[3].processor.calls.copy(); self.run_stage(fx,2)
        self.assertEqual(fx[3].processor.calls,before+[('score',20261012,'S')])
    def test_cleanup_unknown_incomplete_and_preserved(self):
        fx=fixture(); fx[3].cleanup_bad=True; r=self.run_stage(fx,0)
        self.assertEqual(r['status'],'incomplete'); self.assertFalse(r['cleanup_verified'])
        self.assertTrue(fx[2].exists('stage_00/manager_return.json')); self.assertTrue(fx[2].exists('stage_00/child_report.json'))
    def test_uncertain_transport_stops_only_own_unit(self):
        for mode in ('exception','malformed'):
            fx=fixture(); fx[3].run_bad=mode; r=self.run_stage(fx,0)
            self.assertEqual(r['status'],'incomplete'); self.assertEqual(fx[3].stops,['eew-marked-fixture-only-00.service'])
            with self.assertRaises(FileExistsError): self.run_stage(fx,0)
    def test_late_report_retained_without_promotion(self):
        fx=fixture(); fx[2].delay=('child_report.json',301)
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete')
        self.assertTrue(fx[2].exists('stage_00/child_report.json')); self.assertTrue(fx[2].exists('stage_00/child_late_or_failed.json'))
    def test_late_parent_close_has_poison_marker(self):
        fx=fixture(); fx[2].delay=('closed.json',7401)
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertTrue(fx[2].exists('stage_00/late_or_failed.json'))
        with self.assertRaises(Exception): self.run_stage(fx,1)
    def test_storage_exhaustion_no_extra_envelope(self):
        fx=fixture(); fx[0]['storage_limit_bytes']=100
        with self.assertRaisesRegex(ValueError,'disk_cap'): self.run_stage(fx,0)
        self.assertEqual(fx[3].runs,[])
    def test_numeric_snapshot_cap_and_readback(self):
        fx=fixture(); journal=c.Journal(fx[2],16*1024*1024)
        with self.assertRaisesRegex(ValueError,'cap'): journal.put('a.json',b'a'*(c.CAP+1))
        fx[2].corrupt=True
        with self.assertRaisesRegex(ValueError,'readback'): journal.put('a.json',b'{}')
    def test_source_clock_includes_binding_time(self):
        fx=fixture(); old=fx[3].bind
        def delayed(*args):
            v=old(*args); fx[1].now+=301; return v
        fx[3].bind=delayed
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertEqual(fx[3].processor.calls,[])
    def test_slow_claim_does_not_launch_after_authority_lease(self):
        fx=fixture(); fx[2].delay=('claim.json',1)
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertEqual(fx[3].runs,[])
    def test_bound_module_receipt_cannot_change_source(self):
        fx=fixture(); old=fx[3].bind
        def bad(*args):
            v=old(*args); v['binding_receipt']['gate_sha256']='0'*64; return v
        fx[3].bind=bad
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertEqual(fx[3].processor.calls,[])
    def test_incomplete_stream_cannot_be_success(self):
        fx=fixture(); old=fx[3].run
        def bad(*args):
            v=old(*args); v['streams_complete']=False; return v
        fx[3].run=bad
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete')
    def test_parent_finalization_failure_returns_incomplete(self):
        fx=fixture(); fx[2].fail='closed.json'
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete')
        self.assertTrue(fx[2].exists('stage_00/child_report.json')); self.assertTrue(fx[2].exists('stage_00/late_or_failed.json'))
        with self.assertRaises(Exception): self.run_stage(fx,1)
    def test_snapshot_journal_records_exact_latest_hash(self):
        fx=fixture(); self.run_stage(fx,0); self.run_stage(fx,1)
        raw=fx[2].values['stage_01/latest_update.json']; receipt=c.parse(fx[2].values['stage_01/update_300.json'])
        self.assertEqual(receipt['checkpoint_pin'],c.pin(raw))
        self.assertEqual(receipt['history_last'],c.parse(raw)['history'][-1])
    def test_parent_closure_uses_reserve_but_cannot_start_more_science(self):
        fx=fixture(); fx[1].now+=6840; fx[2].delay=('manager_return.json',400)
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'complete',r)
        self.assertGreater(fx[1].now,fx[0]['experiment_begin']+7200)
        self.assertLess(fx[1].now,fx[0]['experiment_begin']+7400)
        with self.assertRaisesRegex(ValueError,'budget'): self.run_stage(fx,1)
    def test_cleanup_uncertainty_stops_and_rechecks_owned_unit(self):
        fx=fixture(); a=fx[3]; old=a.inspect; calls=[]
        def live_then_stopped(unit,timeout):
            calls.append(unit)
            if len(calls)==1: return dict(unit=unit,result='success',active_state='active',control_group='/owned/invented')
            return old(unit,timeout)
        a.inspect=live_then_stopped
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertTrue(r['cleanup_verified'])
        self.assertEqual(a.stops,['eew-marked-fixture-only-00.service']); self.assertEqual(calls,a.stops*2)
        self.assertTrue(fx[2].exists('stage_00/post_after_stop.json'))
    def test_parent_transport_cap_not_relaxed_by_closure_reserve(self):
        fx=fixture(); old=fx[3].run
        def late(*args):
            value=old(*args); fx[1].now+=381; return value
        fx[3].run=late
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertIn('late_transport',r['errors'])
    def test_expired_cleanup_still_requests_nonblocking_owned_stop(self):
        fx=fixture(); a=fx[3]; fx[2].delay=('manager_return.json',7401); a.cleanup_bad=True; calls=[]
        def stop(unit,timeout):
            calls.append((unit,timeout)); return dict(requested=True,unit=unit)
        a.stop=stop
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'incomplete'); self.assertFalse(r['cleanup_verified'])
        self.assertEqual(calls,[('eew-marked-fixture-only-00.service',0)])
    def test_slow_claim_consumes_existing_outer_timeout(self):
        fx=fixture(); a=fx[3]; old_authorize=a.authorize; old_run=a.run; timeouts=[]
        def generous(*args):
            v=old_authorize(*args); v['expires']+=100; return v
        def observed(request,timeout):
            timeouts.append(timeout); return old_run(request,timeout)
        a.authorize=generous; a.run=observed; fx[2].delay=('claim.json',10)
        r=self.run_stage(fx,0); self.assertEqual(r['status'],'complete',r)
        self.assertEqual(timeouts,[370])
    def test_systemd_bound_command_no_execution(self):
        fx=fixture(); g=fx[0]; req=dict(gate=g,stage=c.stage_spec(g,2))
        args=c.systemd_command(req,'/invented/bin/python','pass')
        self.assertIn('RuntimeMaxSec=960',args); self.assertIn('MemoryMax=2147483648',args); self.assertIn('KillMode=control-group',args)
        req['stage']['limits']['memory']=1
        with self.assertRaises(ValueError): c.systemd_command(req,'/invented/bin/python','pass')

if __name__=='__main__': unittest.main()

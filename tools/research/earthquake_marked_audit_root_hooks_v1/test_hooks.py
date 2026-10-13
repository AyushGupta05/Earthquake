import ast
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fixtures


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.c=fixtures.corpus(self.temp.name)
        self.h=self.c['hooks'];self.io=self.c['io'];self.clock=lambda:200.
        self.wall=patch.object(self.h.time,'time',return_value=self.c['wall']);self.wall.start()
    def tearDown(self):self.wall.stop();self.temp.cleanup()
    def make(self):return self.h.make_hooks(self.c['config'],io=self.io,sb=self.c['sb'],clock=self.clock,expected_config_pin=self.io.pin(self.io.canonical(self.c['config'])))
    def refresh(self):
        self.c['config']['hooks_config']=self.c['put'](self.c['ac']);self.c['scope']['config_pin']=self.io.pin(self.io.canonical(self.c['config']));self.c['documents']['hooks_config']=self.io.read_file(self.c['config']['hooks_config'])
    def authorize(self,obj=None):return (obj or self.make()).authorize(self.c['scope'],self.c['documents'],200.)
    def funding(self,raw=None,**updates):
        f=self.io.json_read(self.io.read_file(self.c['ac']['funding']));f.update(updates)
        if raw is not None:f['raw_proof']=self.c['put'](raw)
        oldpin=self.c['ac']['funding']['pin'];self.c['ac']['funding']=self.c['put'](f)
        resource=self.io.json_read(self.io.read_file(self.c['ac']['resource']));resource['funding_pin']=self.c['ac']['funding']['pin'];self.c['ac']['resource']=self.c['put'](resource);self.refresh()
    def test_authorize_positive(self):
        v=self.authorize();self.assertEqual(v['decision'],'authorized');self.assertEqual(v['scope'],self.c['scope']);self.assertGreaterEqual(v['disk_available_bytes'],v['disk_reserve_bytes']+64*1024*1024)
    def test_funding_inactive_raw(self):
        raw=copy.deepcopy(self.c['rawcredit']);raw['main_credit_status']='Expired';self.funding(raw)
        with self.assertRaisesRegex(ValueError,'raw_eligibility'):self.authorize()
    def test_main_balance_binds_raw(self):
        self.funding(estimated_balance_usd=4999.,unreserved_lower_bound_usd=3299.)
        with self.assertRaisesRegex(ValueError,'raw_amount_binding'):self.authorize()
    def test_full_remaining_ceiling(self):
        raw=copy.deepcopy(self.c['rawcredit']);raw['main_credit_estimated_remaining_usd']=3300.;raw['total_estimated_remaining_usd']=3500.
        self.funding(raw,estimated_balance_usd=3300.,unreserved_lower_bound_usd=1600.)
        with self.assertRaisesRegex(ValueError,'remaining_credit_ceiling'):self.authorize()
    def test_expired_funding(self):
        self.funding(valid_until_utc='2026-10-13T11:59:59Z')
        with self.assertRaisesRegex(ValueError,'financial_clock'):self.authorize()
    def test_wrong_scope_or_config(self):
        hooks=self.make();self.c['scope']['unit']='eew-unrelated.service'
        with self.assertRaisesRegex(ValueError,'scope_subjects'):self.authorize(hooks)
        bad=copy.deepcopy(self.c['config']);bad['audit_id']='changed'
        with self.assertRaisesRegex(ValueError,'out_of_band_config_pin'):self.h.make_hooks(bad,io=self.io,sb=self.c['sb'],clock=self.clock,expected_config_pin=self.c['scope']['config_pin'])
    def test_raw_stop_inactive(self):
        raw=copy.deepcopy(self.c['stopraw']);raw['observedraw_systemctl_timer']=raw['observedraw_systemctl_timer'].replace('ActiveState=active','ActiveState=inactive')
        resource=self.io.json_read(self.io.read_file(self.c['ac']['resource']));resource['raw_control_proof']=self.c['put'](raw);self.c['ac']['resource']=self.c['put'](resource);self.refresh()
        with self.assertRaisesRegex(ValueError,'stop_active'):self.authorize()
    def test_installed_stop_script_suffix_rejected(self):
        raw=copy.deepcopy(self.c['stopraw']);raw['observedraw_service']=raw['observedraw_service'].replace(raw['stop_script']['path']+' ;',raw['stop_script']['path']+'.disabled ;')
        resource=self.io.json_read(self.io.read_file(self.c['ac']['resource']));resource['raw_control_proof']=self.c['put'](raw);self.c['ac']['resource']=self.c['put'](resource);self.refresh()
        with self.assertRaisesRegex(ValueError,'stop_exec'):self.authorize()
    def test_short_held_bundle_rejected(self):
        bundle=copy.deepcopy(self.c['bundle']);bundle['stages']=bundle['stages'][:1]
        self.c['config']['bundle_template']=self.c['put'](bundle);self.c['documents']['bundle']=self.io.canonical(bundle);self.c['scope']['bundle_pin']=self.io.pin(self.c['documents']['bundle']);self.refresh()
        with self.assertRaisesRegex(ValueError,'fourteen_bundle_stages'):self.authorize()

    def test_original_late_inventory(self):
        self.c['put'](dict(status='late'),str(Path(self.c['execution'][0]['directory']).relative_to(self.c['root']))+'/late_or_failed.json')
        with self.assertRaisesRegex(ValueError,'late_or_unknown_member'):self.authorize()
    def test_original_last_return_not_flag(self):
        execution=self.io.json_read(self.io.read_file(self.c['ac']['original_execution']));execution['stages'][0]['last_return']['status']='incomplete';self.c['ac']['original_execution']=self.c['put'](execution)
        bundle=copy.deepcopy(self.c['bundle']);bundle['root_context']['original_execution_pin']=self.c['ac']['original_execution']['pin'];self.c['config']['bundle_template']=self.c['put'](bundle);self.c['documents']['bundle']=self.io.canonical(bundle);self.c['scope']['bundle_pin']=self.io.pin(self.c['documents']['bundle']);self.refresh()
        with self.assertRaisesRegex(ValueError,'actual_last_parent_return'):self.authorize()
    def test_strong_full_report_projection(self):
        obj=self.make();old=self.io.json_read(self.io.read_file(self.c['config_original_input'] if 'config_original_input' in self.c else self.c['bundle']['stronger']['strong_results']))
        original=self.io.json_read(self.io.read_file(self.c['ac']['original_config']));feature=self.io.json_read(self.io.read_file(original['inputs']['feature_authority']));packet=dict(rows=[dict(r,common=True) for r in old['roster']])
        value=obj.project_stronger(packet,old,original['inputs']['strong_authority']['pin'],feature['packet_sha256'])
        self.assertEqual(len(value['fits']),8);self.assertEqual(value['fits'][0]['predictions'],old['fits'][0]['predictions']);self.assertEqual(value['fits'][0]['closure']['independent_audit_sha256'],old['fits'][0]['independent_closure']['proof_pin']['sha256']);self.assertFalse(value['origins'][0]['old_model_reexecuted'])
    def test_authenticate_requires_authorize(self):
        with self.assertRaisesRegex(ValueError,'prior_positive_authorization'):self.make().authenticate_input(dict(schema='marked-audit-input-authentication-scope-v1',stage=0),self.c['bundle']['root_context'],processing_begin=199.)
    def authentication_scope(self,obj):
        original=self.io.json_read(self.io.read_file(self.c['ac']['original_config']));feature=self.io.json_read(self.io.read_file(original['inputs']['feature_authority']));old=self.io.json_read(self.io.read_file(original['inputs']['strong_results']))
        projected=obj.project_stronger(dict(rows=[dict(r,common=True) for r in feature['roster']]),old,original['inputs']['strong_authority']['pin'],feature['packet_sha256'])
        artifacts={}
        for i,files in enumerate(self.c['bundle']['stages']):artifacts.update({'stage_%02d/%s'%(i,n):spec['pin'] for n,spec in files.items()})
        for role in ('native','stronger'):artifacts.update({role+'/'+n:spec['pin'] for n,spec in self.c['bundle'][role].items()})
        admission=self.io.json_read(self.io.read_file(self.c['bundle']['stages'][0]['result.json']))
        return dict(schema='marked-audit-input-authentication-scope-v1',stage=0,bundle_sha256=self.io.pin(self.io.canonical(self.c['bundle']))['sha256'],binding_sha256=self.c['config']['binding_sha256'],artifact_pins=artifacts,gate_sha256=self.io.pin(self.io.canonical(self.c['gate']))['sha256'],source_pins=admission['source_pins'],packet_sha256=feature['packet_sha256'],admission_sha256=self.c['bundle']['stages'][0]['result.json']['pin']['sha256'],stronger_closure_sha256=self.io.pin(self.io.canonical(projected['fits']))['sha256'],stronger_origins_sha256=self.io.pin(self.io.canonical(projected['origins']))['sha256'])
    def test_authentication_positive_and_pin_reject(self):
        obj=self.make();self.authorize(obj);scope=self.authentication_scope(obj)
        receipt=obj.authenticate_input(scope,self.c['bundle']['root_context'],processing_begin=199.)
        self.assertEqual(receipt['scope'],scope);self.assertEqual(receipt['decision'],'authorized')
        scope['artifact_pins']={}
        with self.assertRaisesRegex(ValueError,'all_artifact_pins'):obj.authenticate_input(scope,self.c['bundle']['root_context'],processing_begin=199.)

    def test_dynamic_previous_root_return_positive(self):
        fixtures.previous_stage(self.c);self.assertEqual(self.authorize()['decision'],'authorized')
    def test_dynamic_previous_no_false_last_return(self):
        previous=fixtures.previous_stage(self.c);previous['held']['last_return']['status']='incomplete'
        self.c['put'](previous['held'],'root_last_returns/stage_00.private.json')
        with self.assertRaisesRegex(ValueError,'previous_actual_return'):self.authorize()
    def test_dynamic_previous_stream_truncation_and_late_member(self):
        fixtures.previous_stage(self.c)
        self.c['put']({},'auditstore/stage_00/late_or_failed.json')
        with self.assertRaisesRegex(ValueError,'previous_absence'):self.authorize()

    def test_dynamic_previous_truncated_original_metadata(self):
        previous=fixtures.previous_stage(self.c);held=previous['held'];manager=copy.deepcopy(held['root_manager']);manager['stream_custody']['stdout']['original_bytes']=1
        spec=self.c['put'](manager,'auditstore/stage_00/manager_return.json');held['inventory']['manager_return.json']=spec['pin'];held['root_manager']=manager
        self.c['put'](held,'root_last_returns/stage_00.private.json')
        with self.assertRaisesRegex(ValueError,'root_raw_complete_stream'):self.authorize()

    def test_clock_precision_and_raw_properties(self):
        self.assertEqual(self.h.duration('2h 3min 20s'),7400)
        with self.assertRaises(ValueError):self.h.raw_properties('ActiveState=active\nActiveState=inactive')
        hooks=self.make()
        with self.assertRaisesRegex(ValueError,'same_clock'):hooks.authorize(self.c['scope'],self.c['documents'],20.)
    def test_python39(self):
        for file in Path('.').glob('*.py'):ast.parse(file.read_text(),feature_version=(3,9))


if __name__=='__main__':unittest.main()

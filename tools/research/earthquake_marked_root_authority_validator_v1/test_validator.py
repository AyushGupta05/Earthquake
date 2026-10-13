import copy,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import validator as v
import fixtures

class Authority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(dir=str(Path(tempfile.gettempdir()).resolve()));cls.c=fixtures.corpus(cls.tmp.name)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def callback(self,config=None):
        c=self.c;config=c['config'] if config is None else config;return v.make_validator(config,io=c['io'],source_binding=c['sb'],clock=lambda:101.,expected_deployment_config_pin=c['io'].pin(c['io'].canonical(config)))
    def invoke(self,callback=None,scope=None,documents=None):
        c=self.c
        with patch.object(v.time,'time',return_value=c['wall']):return (self.callback() if callback is None else callback)(c['scope'] if scope is None else scope,c['documents'] if documents is None else documents,101.)
    def config_ac(self,mutation):
        c=self.c;ac=copy.deepcopy(c['ac']);mutation(ac);config=copy.deepcopy(c['config']);config['authority_config']=c['put'](ac);return config
    def test_positive_chain_preserves_negative_old_scientific_outcome(self):
        result=self.invoke();self.assertEqual(result['decision'],'authorized');self.assertEqual(result['scope'],self.c['scope']);self.assertEqual(set(result),{'schema','scope','decision','expires','evidence_pins'})
    def test_all14_literal_stages_parent_and_child(self):
        callback=self.callback()
        # Full positive chains cover both manager classes and both phases.
        for i,phase in ((0,'parent'),(2,'parent'),(13,'child')):
            scope=dict(self.c['scope'],index=i,unit='eew-marked-invented-%02d.service'%i,phase=phase);self.assertEqual(self.invoke(callback,scope)['decision'],'authorized')
        # Every fixed index rejects a foreign literal before reading evidence.
        for i in range(14):
            scope=dict(self.c['scope'],index=i,unit='eew-marked-invented-%02d.service'%((i+1)%14))
            with self.assertRaisesRegex(ValueError,'scope_subjects'):self.invoke(callback,scope)
    def test_no_fixtureTrue_default_or_scope_derived_config(self):
        c=self.c
        with self.assertRaises(ValueError):v.make_validator(c['config'],io=c['io'],source_binding=c['sb'],clock=lambda:101.,expected_deployment_config_pin=dict(bytes=1,sha256='0'*64))
        with self.assertRaises(TypeError):v.make_validator(c['config'],io=c['io'],source_binding=c['sb'],clock=lambda:101.)
    def test_unknown_POST_TEST_boolindex_and_foreign_scope_denied(self):
        for fields in [dict(index=True),dict(index=14),dict(unit='POST.service'),dict(phase='TEST'),dict(config_pin=dict(bytes=1,sha256='0'*64))]:
            with self.assertRaises(ValueError):self.invoke(scope=dict(self.c['scope'],**fields))
    def test_document_body_pin_and_canonical_original_records_mismatch(self):
        d=dict(self.c['documents']);d['strong_results']+=b' '
        with self.assertRaises(ValueError):self.invoke(documents=d)
    def test_expired_crosshost_lease_or_insufficient_manager_denied(self):
        for mutate in [lambda a:a['lease'].update(expires=102.),lambda a:a['lease'].update(boot_id_sha256='0'*64),lambda a:a['lease'].update(issued=102.)]:
            config=self.config_ac(mutate);scope=dict(self.c['scope'],config_pin=self.c['io'].pin(self.c['io'].canonical(config)))
            with self.assertRaises(ValueError):self.invoke(self.callback(config),scope)
    def test_modified_config_rejected_even_after_factory(self):
        config=copy.deepcopy(self.c['config']);callback=self.callback(config);config['storage_limit_bytes']+=1
        with self.assertRaisesRegex(ValueError,'config_changed'):self.invoke(callback)
    def test_feature_false_or_missing_three_returns_no_receipt(self):
        config=self.config_ac(lambda a:a['native_returns'].pop());scope=dict(self.c['scope'],config_pin=self.c['io'].pin(self.c['io'].canonical(config)))
        with self.assertRaisesRegex(ValueError,'native_closures'):self.invoke(self.callback(config),scope)
    def test_credit_ceiling_eligibility_conservative_arithmetic_denied(self):
        c=self.c
        for field,value in [('credits_only',False),('ceiling_usd',2001),('reservation_usd',334),('unreserved_lower_bound_usd',9999),('task_spend_upper_bound_usd',1800)]:
            old=c['io'].json_read(c['io'].read_file(c['ac']['funding']));old[field]=value;fund=c['put'](old);gate=dict(c['gate'],funding_pin=fund['pin']);gate_spec=c['put'](gate);config=self.config_ac(lambda a:a.update(funding=fund,gate=gate_spec));scope=dict(c['scope'],config_pin=c['io'].pin(c['io'].canonical(config)),funding_pin=fund['pin'],gate_sha256=c['io'].pin(c['io'].canonical(gate))['sha256'])
            with self.assertRaises(ValueError):self.invoke(self.callback(config),scope)
    def test_whole660_and_checkpoint_pins_cannot_be_shape_only(self):
        for mutation in [lambda a:a['checkpoints'].__setitem__(0,dict(a['checkpoints'][0],checkpoint=dict(a['checkpoints'][0]['checkpoint'],pin=dict(bytes=1,sha256='0'*64)))),lambda a:a['checkpoints'].pop()]:
            config=self.config_ac(mutation);scope=dict(self.c['scope'],config_pin=self.c['io'].pin(self.c['io'].canonical(config)))
            with self.assertRaises(ValueError):self.invoke(self.callback(config),scope)
    def test_independent_role_manifest_binding_required_at_factory(self):
        config=copy.deepcopy(self.c['config']);config['sources']['gaussian']['manifest']['pin']=dict(bytes=1,sha256='0'*64)
        with self.assertRaisesRegex(ValueError,'role_manifest_gate_binding'):self.callback(config)
    def test_changed_authority_source_cannot_issue_receipt(self):
        c=self.c;path=Path(c['config']['authority_source']['path']);raw=path.read_bytes();callback=self.callback();path.chmod(0o600);path.write_bytes(b'# changed validator source');path.chmod(0o400)
        try:
            with self.assertRaisesRegex(ValueError,'file_pin'):self.invoke(callback)
        finally:path.chmod(0o600);path.write_bytes(raw);path.chmod(0o400)
    def test_forward_wall_clock_step_expires_before_receipt(self):
        c=self.c;callback=self.callback()
        with patch.object(v.time,'time',side_effect=[c['wall'],v.utc(c['ac']['lease']['expires_utc'])+1]):
            with self.assertRaisesRegex(ValueError,'end_utc_validity'):callback(c['scope'],c['documents'],101.)

    def test_live_source_hash_changed_no_authority(self):
        c=self.c;path=Path(c['config']['sources']['parent']['directory'])/'controller.py';raw=path.read_bytes();path.chmod(0o600);path.write_bytes(b'# changed');path.chmod(0o400)
        try:
            with self.assertRaises(ValueError):self.invoke()
        finally:path.chmod(0o600);path.write_bytes(raw);path.chmod(0o400)

if __name__=='__main__':unittest.main()

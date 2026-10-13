"""Meaningful invented native custody, exact byte and censor/reset checks."""
import copy
from fractions import Fraction
import math
import time
import unittest
from unittest.mock import patch
import numpy as np
import auditor
import invented
from decode_contract import ObservedDecodeFailure

class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.f=invented.fixture()
    def fixture(self):return copy.deepcopy(self.f)
    def reject(self,f,pattern=None):
        if pattern:
            with self.assertRaisesRegex((ValueError,RuntimeError),pattern):invented.run(f)
        else:
            with self.assertRaises((ValueError,RuntimeError,KeyError,TypeError)):invented.run(f)
    def test_full115_exact_oracle_and_separate_namespaces(self):
        called=[]
        def decode(raw,d):called.append(d['ordinal']);return invented.decode(raw,d)
        result=invented.run(self.f,decode)
        self.assertEqual(result['public']['checked_observations'],348);self.assertEqual(result['observed_samples'],dict(old=2700,new=1440))
        self.assertEqual(len(called),(15+8)*5);self.assertFalse(result['fit_authorized']);self.assertFalse(result['public']['physical_authority'])
        self.assertNotIn('input_pins',result['public']);self.assertNotIn('observed_samples',result['public'])
    def test_later_mixed_native_dtype_keeps_prefix_exact(self):
        for early in (3,4):
            f=self.fixture();body=b''.join(invented.record('HH'+ch,invented.VALUES[:16],early,0)+invented.record('HH'+ch,invented.VALUES[16:32],5,4)+invented.record('HH'+ch,invented.VALUES[32:],5,8) for ch in 'EN12Z')
            for idx,core,name in [(0,auditor.old_native,'old'),(1,auditor.new_native,'new')]:
                p=copy.deepcopy(f['plans'][idx]);bodies={i:body for i in range(len(p['batches']))}
                for b in p['batches']:b.update(body_bytes=len(body),body_sha256=auditor.pin(body)['sha256'])
                q=core.qualify(p,bodies,invented.decode);self.assertEqual(q['disposition'],'complete')
                f=invented.changed(f,name+'_plan',p);f=invented.changed(f,name+'_qualified',q);f['bodies'][idx]=bodies
            result=invented.run(f);self.assertEqual(result['public']['checked_observations'],348)

    def test_noise_exact_one_not_floored_threshold9_is_quiet_reactivation(self):
        r=self.f['packet']['rows'][0];h=r['horizons'][2]
        self.assertEqual(h['ratios'][:5],[16.,16.,9.,1.,16.]);self.assertEqual(h['states'][:5],[1,1,0,0,1]);self.assertEqual(h['run_ages'][:5],[1,2,1,2,1])
        np.testing.assert_array_equal(r['initial']['context'][:6],np.zeros(6))
        self.assertEqual([len(c['states']) for c in r['horizons']],[2,10,18]);invented.run(self.f)
    def test_own_initial_normalization_and_immutable_context(self):
        r=self.f['packet']['rows'][0];np.testing.assert_array_equal(r['initial']['wave'],np.ones((3,1),dtype=np.float32))
        for c in r['horizons']:
            self.assertEqual(c['context'][:7].tobytes(),r['initial']['context'][:7].tobytes())
            self.assertEqual(c['context'][8:].tobytes(),r['initial']['context'][7:].tobytes())
        f=self.fixture();f['packet']['rows'][0]['initial']['wave'][0,0]=np.nextafter(np.float32(1),np.float32(0));self.reject(f,'semantic_array')
    def test_array_one_ulp_byte_mismatch_all_types(self):
        for key in ('wave','amplitude','context'):
            f=self.fixture();a=f['packet']['rows'][0]['horizons'][1][key];a.flat[0]=np.nextafter(a.flat[0],a.dtype.type(2));self.reject(f,'semantic_array')
    def test_scalar_ratio_one_ulp_and_negative_zero(self):
        f=self.fixture();f['packet']['rows'][0]['horizons'][2]['ratios'][-1]=math.nextafter(1.,2.);self.reject(f,'semantic_ratio')
        a=self.f['packet']['rows'][0]['initial'];b=copy.deepcopy(a);b['context'][0]=-0.
        with self.assertRaisesRegex(ValueError,'semantic_array'):auditor.same_observation(a,b)
    def test_states_ages_and_terminal_exit_tamper(self):
        for key,value in [('states',[1,0]),('run_ages',[1,1]),('ratios',[16.,16.,1.])]:
            f=self.fixture();f['packet']['rows'][0]['horizons'][0][key]=value;self.reject(f,'activity')
    def test_ratio_prefix_no_reset_on_horizon(self):
        f=self.fixture();c=f['packet']['rows'][0]['horizons'][1];c['ratios'][0]=17.;self.reject(f,'activity_prefix')
        f=self.fixture();f['packet']['rows'][0]['horizons'][2]['run_ages'][-1]=1;self.reject(f,'activity')
    def test_pin_mismatch_before_any_decode(self):
        f=self.fixture();f['pins']['old_plan']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'pin_binding'):invented.run(f,lambda *_:self.fail('decode'))
    def test_metadata_roles_privacy_before_values(self):
        for k,v in [('mw',True),('group',True),('group',-1),('partition','TEST'),('event_id','private'),('origin_latitude',0.)]:
            meta=copy.deepcopy(self.f['meta']);meta[0][k]=v;f=invented.changed(self.f,'metadata',meta)
            with self.assertRaises(ValueError):invented.run(f,lambda *_:self.fail('decode'))
    def test_fixed_roster_cannot_shrink_or_expand(self):
        for i in (0,34):
            roster=copy.deepcopy(self.f['roster']);roster['rows'][i]['common']=not roster['rows'][i]['common'];f=invented.changed(self.f,'roster',roster)
            with self.assertRaisesRegex(ValueError,'fixed_denominator'):invented.run(f,lambda *_:self.fail('decode'))
        r=copy.deepcopy(self.f['roster']);r['schema']='other';self.reject(invented.changed(self.f,'roster',r),'roster_schema')
    def test_mixed_group_all_rows_denied_even_noncommon(self):
        meta=copy.deepcopy(self.f['meta']);meta[65]['group']=41
        with self.assertRaisesRegex(ValueError,'mixed_group'):invented.run(invented.changed(self.f,'metadata',meta),lambda *_:self.fail('decode'))
        meta=copy.deepcopy(self.f['meta']);meta[34].update(group=-1,operational_eligible=False)
        f=invented.changed(self.f,'metadata',meta);f['packet']['rows'][34]['group']=-1;invented.run(f)
    def test_no_arrays_for_noncommon_rows(self):
        f=self.fixture();f['packet']['rows'][34]['initial']=copy.deepcopy(f['packet']['rows'][0]['initial']);self.reject(f,'noncommon')
        f=self.fixture();f['packet']['rows'][34]['horizons'][0]['wave']=np.zeros((3,1),dtype=np.float32);self.reject(f,'noncommon')
    def test_exact_array_type_dtype_contiguity_finiteness(self):
        for value in [np.zeros((3,16),dtype=np.float64),np.zeros((16,3),dtype=np.float32).T,np.full((3,16),np.nan,dtype=np.float32),[[1.]]*3]:
            f=self.fixture();f['packet']['rows'][0]['horizons'][0]['wave']=value;self.reject(f)
    def test_payload_caps_before_decode(self):
        with patch.object(auditor,'MAX_ELEMENTS',3):
            with self.assertRaisesRegex(ValueError,'wave_schema|payload_cap'):invented.run(self.f,lambda *_:self.fail('decode'))
        with patch.object(auditor,'MAX_PAYLOAD',1):
            with self.assertRaisesRegex(ValueError,'payload_cap'):invented.run(self.f,lambda *_:self.fail('decode'))
    def test_raw_body_hash_and_namespace_no_repacking(self):
        f=self.fixture();f['bodies'][0][0]=f['bodies'][0][0][:-1]+b'x';self.reject(f,'input_schema')
        f=self.fixture();f['bodies'][1]=dict(f['bodies'][0]);self.reject(f,'input_schema')
        p=copy.deepcopy(self.f['plans'][1]);p['rows'][0]['global_ordinal']=0;self.reject(invented.changed(self.f,'new_plan',p),'input_schema')
    def test_record_raw_native_routing_bindings(self):
        for key,value in [('raw_sha256','0'*64),('samples_sha256','0'*64),('routed_rows',[0]),('start_ns',0),('observed_samples',35),('dtype','f8')]:
            q=copy.deepcopy(self.f['qs'][0]);q['records'][0][key]=value;self.reject(invented.changed(self.f,'old_qualified',q))
    def test_piece_view_hash_and_exact_grid_no_tolerance_repair(self):
        for namespace,idx in [('old_qualified',0),('new_qualified',1)]:
            q=copy.deepcopy(self.f['qs'][idx]);next(c for c in q['rows'][0]['cells'][0]['components'] if c['channel']=='HHE')['view_sha256']='0'*64;self.reject(invented.changed(self.f,namespace,q),'view_binding')
            q=copy.deepcopy(self.f['qs'][idx]);next(c for c in q['rows'][0]['cells'][0]['components'] if c['channel']=='HHE')['first'][0]+=1;self.reject(invented.changed(self.f,namespace,q),'piece_binding|component_grid')
    def test_rational_halfopen_membership_signed_clock(self):
        self.assertEqual(auditor.indices(Fraction(-7,3),Fraction(2,3),20,-1,1),(2,5))
        self.assertEqual(auditor.indices(Fraction(0),Fraction(250000000),36,3500000000,3750000000),(14,15))
        with self.assertRaisesRegex(ValueError,'empty_window'):auditor.indices(Fraction(0),Fraction(10),2,1,2)
    def test_received_size_charged_before_wrong_clock_or_malformed_schema(self):
        def oversized(*_):return dict(start_ns=-1,rate=1.,dtype='i4',values=np.zeros(8_000_001,dtype=np.int32),extra=1)
        with self.assertRaisesRegex(RuntimeError,'observed_sample_cap'):invented.run(self.f,oversized)
        def multidimensional(*_):return dict(start_ns=-1,rate=1.,dtype='i4',values=np.zeros((2,4_000_001),dtype=np.int32))
        with self.assertRaisesRegex(RuntimeError,'observed_sample_cap'):invented.run(self.f,multidimensional)
    def test_array_subclass_receipt_charged_before_dtype_veto(self):
        class Sub(np.ndarray):pass
        def oversized(*_):return dict(start_ns=-1,rate=1.,dtype='i4',values=np.zeros(8_000_001,dtype=np.int32).view(Sub))
        with self.assertRaisesRegex(RuntimeError,'observed_sample_cap'):invented.run(self.f,oversized)
        def small(*_):return dict(start_ns=0,rate=1.,dtype='i4',values=np.zeros(36,dtype=np.int32).view(Sub))
        with self.assertRaisesRegex(ValueError,'record_replay'):invented.run(self.f,small)

    def test_structured_failure_charges_received_count(self):
        def over(*_):raise ObservedDecodeFailure(8_000_001)
        with self.assertRaisesRegex(RuntimeError,'observed_sample_cap'):invented.run(self.f,over)
        def bounded(*_):raise ObservedDecodeFailure(1)
        with self.assertRaisesRegex(ValueError,'record_decode_failure'):invented.run(self.f,bounded)
        for bad in (True,-1):
            with self.assertRaises(RuntimeError):ObservedDecodeFailure(bad)
    def test_batch_and_packet_observed_counts_exact(self):
        q=copy.deepcopy(self.f['qs'][0]);q['batches'][0]['observed_samples']-=1;self.reject(invented.changed(self.f,'old_qualified',q),'observed_binding')
        f=self.fixture();f['packet']['observed_samples']['old']-=1;self.reject(f,'packet_observed')
    def test_deadline_before_decode_and_after_last_reduction(self):
        with self.assertRaisesRegex(RuntimeError,'audit_deadline'):invented.run(self.f,lambda *_:self.fail('decode'),time.monotonic()-301)
        with self.assertRaisesRegex(ValueError,'processing_begin'):invented.run(self.f,begin=True)
        with patch.object(auditor.time,'monotonic',return_value=1.):
            with self.assertRaises(RuntimeError):invented.run(self.f,begin=2.)
    def test_JSON_duplicates_nonfinite_depth_and_integer_caps(self):
        for raw in [b'{"a":1,"a":2}',b'NaN',b'1e1000',b'['*34+b'0'+b']'*34,b'1'*1025]:
            with self.assertRaises(ValueError):auditor.parse(raw,2048)
    def test_missing_receiver_static_context_and_literal_units(self):
        row=self.f['plans'][0]['rows'][0];m=copy.deepcopy(self.f['meta'][0]);m.update(station_latitude=91.,station_longitude=None,station_elevation=None,sensitivities=[0.,None,10.],units=['m/s','M/S','M/S**2'])
        s=auditor.static(row,m,Fraction(4));self.assertEqual(s[1:7],[0.,0.,0.,1.,1.,1.]);self.assertEqual(s[9:15],[0.,0.,1.,1.,1.,0.]);self.assertEqual(s[15:],[0.,0.,0.,1.,1.,0.,0.,0.,0.,1.,0.,0.])
    def test_scalar_fsum_center_power_floor_and_initial_future_independence(self):
        row=self.f['plans'][0]['rows'][0];m=self.f['meta'][0];native=[np.asarray(invented.VALUES,dtype=np.float64)]*3
        a,h=auditor.semantics(row,native,Fraction(invented.START),Fraction(250000000),m,time.monotonic())
        b=[x.copy() for x in native]
        for x in b:x[20:]=100.
        ai,hi=auditor.semantics(row,b,Fraction(invented.START),Fraction(250000000),m,time.monotonic())
        auditor.same_observation(a,ai);auditor.same_observation(h[0],hi[0]);self.assertNotEqual(h[2]['wave'].tobytes(),hi[2]['wave'].tobytes())
        zero=[np.zeros(36)]*3;z,zh=auditor.semantics(row,zero,Fraction(invented.START),Fraction(250000000),m,time.monotonic())
        np.testing.assert_array_equal(z['context'][:6],[0,0,0,1,1,1]);np.testing.assert_array_equal(z['amplitude'],[0,-12,-12,-12]);self.assertEqual(zh[2]['states'],[0]*18)
    def test_noninteger_grid_and_nonfinite_numerics_abort_not_quiet(self):
        row=dict(self.f['plans'][0]['rows'][0]);row['pick_ns']+=1
        native=[np.asarray(invented.VALUES,dtype=np.float64)]*3
        a,h=auditor.semantics(row,native,Fraction(invented.START),Fraction(250000000),self.f['meta'][0],time.monotonic())
        self.assertEqual([len(v['states']) for v in h],[1,9,17]);self.assertEqual(a['wave'].shape,(3,1))
        with self.assertRaises((ValueError,OverflowError)):auditor.normalized([[math.inf]]*3)
    def test_forbidden_packet_fields_and_builtin_types(self):
        for key in ('station_id','origin_latitude','p_to_t0','absolute_date'):
            f=self.fixture();f['packet']['rows'][0]['initial'][key]=0;self.reject(f,'common_packet')
        f=self.fixture();f['packet']['denominators']['events']=True;self.reject(f,'packet_schema')
        f=self.fixture();f['packet']['rows'][0]['horizons'][0]['states'][0]=True;self.reject(f,'activity')

if __name__=='__main__':unittest.main()

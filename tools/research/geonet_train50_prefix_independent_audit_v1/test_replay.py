"""Invented manual native records and independently composed NEW50 replay."""
import copy
from fractions import Fraction
import struct
import types
import unittest
from unittest.mock import patch
import numpy as np
import obspy
import auditor
from fixtures import plan_and_bodies,reader,input_pins
from invented import int_record
import header_scanner
from geometry import header_grid
from native_decode import decode_record,ObservedDecodeFailure
from plan_validation import validate
import replay as r
from strict import Reject,canonical,sha


class ReplayTests(unittest.TestCase):
    def test_exact50_150_13_global_tail_and_five_literals(self):
        plan,bodies=plan_and_bodies(tuple(range(13)));result=r.replay(plan,reader(bodies))
        self.assertEqual(result['disposition'],'complete');self.assertEqual(len(result['rows']),50);self.assertEqual(sum(len(v['cells']) for v in result['rows']),150)
        self.assertEqual(result['rows'][-1]['global_ordinal'],114);self.assertEqual(plan['batches'][-1]['rows'],[48,49])
        self.assertEqual(result['batches'][0]['observed_samples'],400);self.assertEqual(result['records'][0]['routed_rows'],[0,1,2,3])
        for h in result['aggregate']['horizons']:self.assertEqual(h['complete_joint'],45);self.assertEqual(h['metadata_unknown_complete_components'],25)
        self.assertTrue(all(v is False for v in result['claims'].values()))

    def test_no_target_nullable_clocks_and_empty_batches_no_reads(self):
        plan,bodies=plan_and_bodies(queryable=())
        plan['rows'][0]['t0_ns']=3_000_000_000
        result=r.replay(plan,lambda *a:self.fail('bodyread'),lambda *a:self.fail('decode'))
        self.assertEqual(result['aggregate']['no_target_rows'],50);self.assertEqual(result['aggregate']['batch_statuses']['nonpositive'],13)
        a,b=result['rows'][:2]
        self.assertEqual(a['cells'][0]['cutoff_ns'],4_000_000_000);self.assertIsNone(b['cells'][0]['cutoff_ns'])
        for row in result['rows']:
            for cell in row['cells']:self.assertEqual(cell['joint']['reason'],'selection_unknown');self.assertEqual(cell['components'],[]);self.assertIsNone(cell['pick_before_cutoff'])

    def test_sparse_requested_rows_and_long_station_not_truncated(self):
        plan,bodies=plan_and_bodies(queryable=(0,2));result=r.replay(plan,reader(bodies))
        self.assertEqual(plan['batches'][0]['requested_rows'],[0,2]);self.assertEqual(result['records'][0]['routed_rows'],[0,2])
        for i in (0,2):plan['rows'][i]['station']='ABCDLONG'
        result=r.replay(plan,reader(bodies));self.assertEqual(result['batches'][0]['reason'],'unexpected_identity');self.assertEqual(result['records'][0]['routed_rows'],[])
        self.assertEqual(result['aggregate']['horizons'][0]['complete_joint'],0)

    def test_strict_types_no_test_duplicate_or_old_shape_before_reader(self):
        base,bodies=plan_and_bodies();cases=[]
        for field,value in (('ordinal',False),('global_ordinal',64),('partition','TEST'),('queryable',1),('family','E12')):
            p=copy.deepcopy(base);p['rows'][0][field]=value;cases.append(p)
        p=copy.deepcopy(base);p['batches'][0]['requested_rows']=[True,1,2,3];cases.append(p)
        p=copy.deepcopy(base);p['batches'][12]['rows']=[48];cases.append(p)
        p=copy.deepcopy(base);p['rows'].append(p['rows'][0]);cases.append(p)
        p=copy.deepcopy(base);p['rows'][0]['nominal_rates']['HHE']=[20,2];cases.append(p)
        for p in cases:
            with self.assertRaises(Reject):r.replay(p,lambda *a:self.fail('reader'))

    def test_opaque_reserved_equivalent_clocks_native_samples_hash(self):
        outputs=[]
        for reserved in (0,1,255):
            raw=bytearray(int_record());raw[62]=reserved;raw=bytes(raw)
            p,b=plan_and_bodies(raw=raw);out=r.replay(p,reader(b));outputs.append(out['records'][0])
        self.assertEqual(len({o['raw_sha256'] for o in outputs}),3)
        self.assertEqual(len({o['samples_sha256'] for o in outputs}),1)
        self.assertEqual(len({o['start_ns'] for o in outputs}),1)

    def test_success_callback_count_charged_before_wrong_start_rate_dtype_count(self):
        p,b=plan_and_bodies(raw=int_record())
        for field,value in (('start_ns',1),('rate',5.),('dtype','f8')):
            def callback(raw,d,start,rate):
                out=dict(start_ns=start,rate=float(rate),dtype='i4',values=np.arange(d['npts'],dtype=np.int32));out[field]=value;return out
            out=r.replay(p,reader(b),callback)
            self.assertEqual(out['disposition'],'complete');self.assertEqual(out['batches'][0]['reason'],'decode_unknown');self.assertEqual(out['batches'][0]['observed_samples'],40);self.assertEqual(out['records'],[])
        def excess(raw,d,start,rate):return dict(start_ns=start,rate=float(rate),dtype='i4',values=np.arange(41,dtype=np.int32))
        out=r.replay(p,reader(b),excess);self.assertEqual(out['batches'][0]['observed_samples'],41);self.assertEqual(out['records'],[])

    def test_structured_failure_count_valid_invalid_overbudget_and_prior_evidence(self):
        p,b=plan_and_bodies(raw=int_record()+int_record(sequence=2,start_second=4))
        def fail(raw,d,start,rate):
            if d['ordinal']==1:raise ObservedDecodeFailure(17)
            return decode_record(raw,d,start,rate)
        out=r.replay(p,reader(b),fail);self.assertEqual(out['batches'][0]['observed_samples'],57);self.assertEqual(len(out['records']),1);self.assertEqual(out['batches'][0]['status'],'unknown')
        for count in (True,np.int64(2),-1,2**63):
            def bad(*a):raise ObservedDecodeFailure(count)
            out=r.replay(p,reader(b),bad);self.assertEqual((out['disposition'],out['reason']),('incomplete','runtime_failure'));self.assertEqual(out['batches'][0]['observed_samples'],0)
        def huge(*a):raise ObservedDecodeFailure(8_000_001)
        out=r.replay(p,reader(b),huge);self.assertEqual((out['disposition'],out['reason']),('incomplete','sample_cap'));self.assertEqual(out['batches'][0]['observed_samples'],8_000_001)
        self.assertEqual(out['batches'][0]['status'],'unknown');self.assertTrue(all(h['complete_joint']==0 for h in out['aggregate']['horizons']))

    def test_perbody_and_total_success_overdelivery_guard_before_hash(self):
        p,b=plan_and_bodies(raw=int_record())
        def huge(raw,d,start,rate):return dict(start_ns=1,rate=float(rate),dtype='i4',values=np.broadcast_to(np.zeros(1,dtype=np.int32),(8_000_001,)))
        with patch.object(r,'digest',side_effect=AssertionError('hash')):out=r.replay(p,reader(b),huge)
        self.assertEqual(out['reason'],'sample_cap');self.assertEqual(out['records'],[])
        with patch.object(r,'MAX_TOTAL_SAMPLES',39):out=r.replay(p,reader(b))
        self.assertEqual(out['reason'],'sample_cap');self.assertEqual(out['batches'][0]['advertised_samples'],40)

    def test_final_data_nan_only_local_prefix_finiteness(self):
        raw=bytearray(int_record(channel='HHE',count=40));raw.extend(b'\0'*256);raw[52]=4;raw[54]=9;struct.pack_into('>H',raw,30,80)
        values=np.arange(80,dtype='>f4');values[65]=np.nan;raw[64:384]=values.tobytes()
        p,b=plan_and_bodies(raw=bytes(raw))
        out=r.replay(p,reader(b));self.assertFalse(out['records'][0]['finite'])
        components=out['rows'][0]['cells'][0]['components'];c=next(c for c in components if c['channel']=='HHE');self.assertEqual(c['status'],'complete')
        c=next(c for c in out['rows'][0]['cells'][2]['components'] if c['channel']=='HHE');self.assertEqual(c['reason'],'nonfinite')

    def test_zero_count_no_callback_and_declared_vs_runtime_failures(self):
        p,b=plan_and_bodies(raw=int_record(count=0));out=r.replay(p,reader(b),lambda *a:self.fail('zero'))
        self.assertEqual(out['records'][0]['samples_sha256'],sha(b'empty\0'));self.assertEqual(out['records'][0]['dtype'],'empty')
        p,b=plan_and_bodies(raw=int_record())
        def declared(*a):raise ValueError('invented')
        self.assertEqual(r.replay(p,reader(b),declared)['disposition'],'complete')
        def unexpected(*a):raise RuntimeError('invented')
        self.assertEqual(r.replay(p,reader(b),unexpected)['reason'],'runtime_failure')

    def test_exact_body_and_producer_pins_and_bool_json_difference(self):
        p,b=plan_and_bodies();out=r.replay(p,reader(b));a,z,pins=input_pins(p,out)
        calls=[]
        def bound(name,cap):calls.append((name,cap));return b[int(name[:3])]
        verdict=auditor.audit(a,z,bound,pins);self.assertTrue(verdict['audit_pass']);self.assertEqual(len(calls),1)
        changed=copy.deepcopy(out);changed['rows'][0]['cells'][0]['pick_before_cutoff']=1;a,z,pins=input_pins(p,changed)
        self.assertFalse(auditor.audit(a,z,bound,pins)['audit_pass'])
        with self.assertRaises(Reject):auditor.audit(a+b'x',z,lambda *a:self.fail('reader'),pins)

    def test_deadline_before_first_body_and_bad_later_custody_zero_promotion(self):
        p,b=plan_and_bodies((0,1))
        out=r.replay(p,lambda *a:self.fail('late read'),wall_seconds=-1)
        self.assertEqual((out['disposition'],out['reason']),('incomplete','wall_timeout'))
        out=r.replay(p,lambda ordinal,size:b[ordinal] if ordinal==0 else b'changed')
        self.assertEqual(out['reason'],'runtime_failure');self.assertEqual(out['batches'][0]['status'],'decoded');self.assertTrue(all(h['complete_joint']==0 for h in out['aggregate']['horizons']))

    def test_entry_piece_budget_and_final_output_no_partial_success(self):
        p,b=plan_and_bodies(raw=int_record())
        with patch.object(r,'MAX_PRIVATE',r.HEADROOM+1):out=r.replay(p,reader(b))
        self.assertEqual(out['reason'],'output_cap');self.assertEqual(out['records'],[]);self.assertEqual(out['batches'][0]['status'],'unknown')
        # Private headroom and +64 charge are exact public constants.
        self.assertEqual(r.HEADROOM,8*1024*1024)

    def test_piece_budget_retains_reconciled_entry_but_no_success(self):
        p,b=plan_and_bodies(raw=int_record())
        ordinary=r.replay(p,reader(b))
        entry_charge=len(canonical(ordinary['records'][0]))+64
        with patch.object(r,'MAX_PRIVATE',r.HEADROOM+entry_charge):out=r.replay(p,reader(b))
        self.assertEqual(out['reason'],'output_cap');self.assertEqual(len(out['records']),1)
        self.assertTrue(all(h['complete_joint']==0 for h in out['aggregate']['horizons']))

    def test_producer_preflight_rejects_stale_incomplete_claims_before_body(self):
        p,b=plan_and_bodies();out=r.replay(p,reader(b))
        for field,value in (('schema','geonet-POST-prefix-qualification-v2'),('study','wrong'),('disposition','incomplete'),('reason','sample_cap')):
            changed=copy.deepcopy(out);changed[field]=value;a,z,pins=input_pins(p,changed)
            with self.assertRaises(Reject):auditor.audit(a,z,lambda *a:self.fail('bodyread'),pins)
        changed=copy.deepcopy(out);changed['claims']['raw_clock_truth_verified']=True;a,z,pins=input_pins(p,changed)
        with self.assertRaises(Reject):auditor.audit(a,z,lambda *a:self.fail('bodyread'),pins)

    def test_exact_signed_correction_microseconds_and_rational_crop(self):
        from geometry import crop
        raw=int_record(correction=2,microsecond=-1,rate=-2)
        d=header_scanner.scan(raw)['records'][0];start,rate=header_grid(d)
        self.assertEqual(start,199000);self.assertEqual(rate,Fraction(1,2))
        lo,hi,period=crop(start,rate,4,200000,4_000_199_000)
        self.assertEqual((lo,hi,period),(1,2,Fraction(2_000_000_000)))
        d['flags'][0]=2;self.assertEqual(header_grid(d)[0],-1000)
        d['b100']=[float(np.float32(0.1)),0,0,0,0]
        self.assertEqual(header_grid(d)[1],Fraction.from_float(float(np.float32(0.1))))
        d['flags'][0]=0x10
        with self.assertRaises(Reject):header_grid(d)

    def test_repeated_overlap_gap_and_mixed_rate_never_repaired(self):
        for second,rate,reason in ((3,10,'gap_overlap'),(5,10,'gap_overlap'),(4,20,'mixed_rate')):
            p,b=plan_and_bodies(raw=int_record()+int_record(start_second=second,rate=rate,sequence=2)+int_record(start_second=7,sequence=3))
            out=r.replay(p,reader(b));c=next(c for c in out['rows'][0]['cells'][2]['components'] if c['channel']=='HHE')
            self.assertEqual(c['status'],'incomplete');self.assertEqual(c['reason'],reason)
            self.assertTrue(all(h['complete_joint']==0 for h in out['aggregate']['horizons']))


class DecoderTests(unittest.TestCase):
    def test_manual_steim2_native_without_vendor_encoder(self):
        raw=bytearray(int_record(count=4,rate=1,values=[0,1,2,3]));raw[52]=11
        struct.pack_into('>16I',raw,64,1<<24,0,3,0x00010101,*([0]*12));raw=bytes(raw)
        d=header_scanner.scan(raw)['records'][0];out=decode_record(raw,d,*header_grid(d));self.assertEqual(out['values'].tolist(),[0,1,2,3])

    def test_adapter_all_received_arrays_charged_before_identity_or_shape_reject(self):
        raw=int_record();d=header_scanner.scan(raw)['records'][0];start,rate=header_grid(d)
        def trace(values,station='ABCD'):
            stats=types.SimpleNamespace(network='NZ',station=station,location='',channel='HHE',npts=values.size,starttime=types.SimpleNamespace(ns=start),sampling_rate=float(rate))
            return types.SimpleNamespace(data=values,stats=stats)
        for stream,total in (([trace(np.zeros(3,dtype=np.int32)),trace(np.zeros(5,dtype=np.int32))],8),([trace(np.zeros(7,dtype=np.int32),'BAD')],7),([trace(np.zeros((2,3),dtype=np.int32))],6)):
            with patch('obspy.read',return_value=stream):
                with self.assertRaises(ObservedDecodeFailure) as failure:decode_record(raw,d,start,rate)
            self.assertEqual(failure.exception.observed_samples,total)

    def test_adapter_deferred_start_count_and_no_array_failures(self):
        raw=int_record();d=header_scanner.scan(raw)['records'][0];start,rate=header_grid(d)
        trace=obspy.Trace(np.arange(41,dtype=np.int32),dict(network='NZ',station='ABCD',location='',channel='HHE',starttime=obspy.UTCDateTime(1970,1,1)+1,sampling_rate=10))
        with patch('obspy.read',return_value=obspy.Stream([trace])):out=decode_record(raw,d,start,rate)
        self.assertEqual(len(out['values']),41);self.assertNotEqual(out['start_ns'],start)
        with patch('obspy.read',side_effect=MemoryError('invented')):
            with self.assertRaises(MemoryError):decode_record(raw,d,start,rate)

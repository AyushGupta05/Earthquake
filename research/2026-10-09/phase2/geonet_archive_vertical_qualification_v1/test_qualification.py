"""Invented streams and miniSEED bytes only; no cached earthquake objects."""
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import numpy as np
import obspy
from obspy import Stream, Trace, UTCDateTime

ROOT=Path(__file__).resolve().parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
q=load('qualification');c=load('core');h=load('child_harness');s=load('supervisor')
T0=UTCDateTime('2020-01-02T00:00:00Z')

def slot(index=0):
    return {'slot_index':index,'body_path':'/invented/body'+str(index),'body_sha256':'1'*64,'body_bytes':4096,
        'expected_nslc':{'network':'NZ','station':'AAA','location':'10','channel':'HHZ'},
        't0_ns':T0.ns,'pick_ns':T0.ns,'filename_year':2020,'filename_doy':2}

def trace(start=-5,n=1000,rate=100.,**changes):
    header={'network':'NZ','station':'AAA','location':'10','channel':'HHZ','starttime':T0+start,'sampling_rate':rate}
    header.update(changes)
    return Trace(data=np.arange(n,dtype=np.int32),header=header)

def encoded(traces):
    b=io.BytesIO();Stream(traces).write(b,format='MSEED',encoding='INT32',reclen=512);return b.getvalue()

class GridTests(unittest.TestCase):
    def test_exact_three_half_open_windows(self):
        r=q.analyze(Stream([trace(n=1001)]),slot(),c)
        self.assertEqual([r['windows'][str(d)]['core']['samples'] for d in (1,3,5)],[600,800,1000])
        self.assertTrue(all(w['core']['available'] for w in r['windows'].values()))
        self.assertFalse(r['metadata_rate_verified']);self.assertFalse(r['filename_partition_verified'])

    def test_future_amplitude_poison_never_changes_earlier_prefix(self):
        base=Stream([trace(n=1100)])
        for duration in (1,3,5):
            changed=base.copy();changed[0].data=changed[0].data.astype(np.float64)
            changed[0].data[(5+duration)*100:]=np.nan
            a=q.analyze(base,slot(),c)['windows'][str(duration)]
            b=q.analyze(changed,slot(),c)['windows'][str(duration)]
            self.assertEqual(a,b)

    def test_split_adjacent_gap_overlap_and_misaligned(self):
        for shift,available,gaps,overlaps in ((0,True,0,0),(.01,False,1,0),(-.01,False,0,1),(.005,False,1,0)):
            with self.subTest(shift=shift):
                st=Stream([trace(n=500),trace(start=shift,n=501)])
                result=q.analyze(st,slot(),c)
                core=result['windows']['5']['core']
                self.assertEqual(core['available'],available)
                self.assertEqual((core['gaps'],core['overlaps']),(gaps,overlaps))
                if shift==.005:self.assertFalse(core['sample_grid_consistent'])

    def test_future_gap_does_not_reject_complete_earlier_window(self):
        result=q.analyze(Stream([trace(n=700),trace(start=3,n=201)]),slot(),c)
        self.assertTrue(result['windows']['1']['core']['available'])
        self.assertFalse(result['windows']['3']['core']['available'])
        self.assertEqual(result['decoded_sample_grid']['gaps'],1)

    def test_missing_edge_sample_rejected(self):
        for st in (Stream([trace(start=-4.99,n=999)]),Stream([trace(n=999)])):
            self.assertFalse(q.analyze(st,slot(),c)['windows']['5']['core']['available'])

    def test_multiple_rate_object_and_nonfinite_rate(self):
        row=q.analyze(Stream([trace(n=500),trace(start=0,n=1001,rate=200)]),slot(),c)
        self.assertFalse(row['observed_rate_consistent'])
        self.assertFalse(row['windows']['1']['core']['available'])
        for rate in (0,math.inf,math.nan):
            fake=types.SimpleNamespace(stats=types.SimpleNamespace(sampling_rate=rate))
            with self.assertRaises(ValueError):q.trace_signature(fake)

    def test_literal_nslc_extra_or_alias_never_silently_selected(self):
        for field,value in (('network','XX'),('station','BBB'),('location',''),('channel','HHE')):
            with self.subTest(field=field):
                row=q.analyze(Stream([trace(),trace(**{field:value})]),slot(),c)
                self.assertFalse(row['literal_identity_matches'])
                self.assertEqual(len(row['observed_nslc']),2)
                self.assertFalse(row['windows']['1']['core']['available'])

    def test_day_crossing_descriptive_and_fixed_pick_clock(self):
        p=slot();p['pick_ns']=p['t0_ns']-2*c.NS
        row=q.analyze(Stream([trace()]),p,c)
        self.assertEqual(row['filename_day_boundary_crossing_count'],1)
        self.assertTrue(row['windows']['5']['core']['available'])
        self.assertEqual(row['pick_minus_t0_ns'],-2*c.NS)
        self.assertEqual(row['windows']['1']['left_ns'],p['t0_ns']-5*c.NS)
        p['pick_ns']=p['t0_ns']+c.NS
        row=q.analyze(Stream([trace()]),p,c)
        self.assertFalse(row['windows']['1']['target_pick_strictly_before_deadline'])
        self.assertTrue(row['windows']['3']['target_pick_strictly_before_deadline'])

    def test_rational_noninteger_period_and_fractional_start(self):
        p=slot();p['t0_ns']+=123456000
        tr=trace(n=1200,rate=120.);tr.stats.starttime=UTCDateTime(ns=p['t0_ns']-5*c.NS)
        row=q.analyze(Stream([tr]),p,c)
        self.assertEqual(row['decoded_traces'][0]['sample_rate'],{'numerator':120,'denominator':1})
        self.assertEqual(row['decoded_traces'][0]['last_sample_ns']['denominator'],3)
        self.assertTrue(row['windows']['5']['core']['available'])

    def test_extreme_candidate_is_not_physical_clipping_gate(self):
        tr=trace();tr.data[:]=2
        row=q.analyze(Stream([tr]),slot(),c)
        core=row['windows']['5']['core']
        self.assertTrue(core['available']);self.assertTrue(core['clipping_candidate'])
        self.assertFalse(core['physically_unclipped_verified'])

    def test_aggregate_contains_counts_only_no_private_tokens(self):
        row=q.analyze(Stream([trace()]),slot(),c);row['secret']='PRIVATE_SENTINEL'
        a=q.aggregate([row]+[q.failed(i,'PRIVATE_SENTINEL') for i in (1,2,3)])
        text=json.dumps(a,allow_nan=False)
        for token in ('PRIVATE_SENTINEL','AAA','HHZ','157','body_path','t0_ns'):
            self.assertNotIn(token,text)
        self.assertEqual(a['failed_slots'],3);self.assertEqual(a['complete_decoded_trace_windows']['1'],1)

class DecodeTests(unittest.TestCase):
    def test_public_miniseed_roundtrip(self):
        stream,count,warnings=q.decode(encoded([trace(n=1001)]),obspy.read,q.TOTAL_SAMPLE_CAP)
        self.assertEqual(count,1001);self.assertTrue(np.array_equal(stream[0].data,np.arange(1001,dtype=np.int32)))
        self.assertEqual(q.analyze(stream,slot(),c)['windows']['5']['core']['samples'],1000)

    def test_concatenated_adjacent_gap_overlap_records(self):
        for shift,available in ((0,True),(.01,False),(-.01,False)):
            with self.subTest(shift=shift):
                body=encoded([trace(n=500)])+encoded([trace(start=shift,n=500)])
                stream,count,_=q.decode(body,obspy.read,q.TOTAL_SAMPLE_CAP)
                self.assertEqual(count,1000)
                self.assertEqual(q.analyze(stream,slot(),c)['windows']['5']['core']['available'],available)

    def test_header_caps_stop_before_full_read(self):
        for count in (-1,True,1.0,float('nan'),q.OBJECT_SAMPLE_CAP+1):
            calls=[]
            def read(*args,**kwargs):
                calls.append(kwargs);return [types.SimpleNamespace(stats=types.SimpleNamespace(npts=count))]
            with self.subTest(count=count),self.assertRaises(ValueError):q.decode(b'invented',read,q.TOTAL_SAMPLE_CAP)
            self.assertEqual(len(calls),1)
        with self.assertRaises(ValueError):q.decode(encoded([trace()]),obspy.read,999)

    def test_header_full_disagreement_dtype_and_warning_privacy(self):
        headers=Stream([trace()]);full=headers.copy();full[0].data=full[0].data[:-1]
        with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**k:headers if k.get('headonly') else full,1000)
        full=headers.copy();full[0].data=full[0].data.astype(np.uint32)
        with self.assertRaises(ValueError):q.decode(b'invented',lambda *a,**k:headers if k.get('headonly') else full,1000)
        import warnings
        def warning_read(*a,**k):
            warnings.warn('PRIVATE_SENTINEL');return headers
        decoded,count,n=q.decode(b'invented',warning_read,1000)
        self.assertEqual(n,2)

class GateTests(unittest.TestCase):
    def fixture(self,root):
        root=Path(root).resolve();sources={name:h.digest((ROOT/name).read_bytes()) for name in h.SOURCE_NAMES}
        slots=[]
        for i in range(4):
            body=encoded([trace(n=1001)]);path=root/('invented'+str(i)+'.mseed');path.write_bytes(body)
            item=slot(i);item.update(body_path=str(path),body_sha256=h.digest(body),body_bytes=len(body));slots.append(item)
        plan={'protocol_id':h.PROTOCOL,'limits':h.LIMITS,'source_files':sources,'slots':slots}
        planpath=root/'invented_plan.json';planpath.write_text(json.dumps(plan));ph=h.digest(planpath.read_bytes())
        auth={'protocol_id':h.PROTOCOL,'limits':h.LIMITS,'source_files':sources,'plan_sha256':ph,'offline_decode_authorized':True,
            'focused_tests_passed':True,'code_only_review_clean':True,'pushed_source_commit':'a'*40,
            'source_manifest_sha256':'1'*64,'review_receipt_sha256':'2'*64,'test_receipt_sha256':'3'*64}
        authpath=root/'invented_auth.json';authpath.write_text(json.dumps(auth))
        runtime=str(Path(sys.executable).absolute())
        return types.SimpleNamespace(plan=str(planpath),authorization=str(authpath),plan_sha256=ph,
            authorization_sha256=h.digest(authpath.read_bytes()),adapter_sha256=sources['child_harness.py'],
            supervisor_sha256=sources['supervisor.py'],runtime_path=runtime,
            runtime_sha256=h.digest(Path(runtime).resolve().read_bytes()),deadline=time.monotonic()+120)

    def test_gate_real_sources_and_exact_four_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);plan,auth,buffers=h.validate_gate(args)
            self.assertEqual(len(plan['slots']),4);self.assertEqual(set(buffers),h.SOURCE_NAMES)
            for key,value in (('slot_index',True),('pick_ns',1.0),('t0_ns',None),('filename_doy',0)):
                bad=copy.deepcopy(plan['slots'][0]);bad[key]=value
                with self.subTest(key=key),self.assertRaises(ValueError):h.validate_slot(bad,0)
            bad=copy.deepcopy(plan['slots'][0]);bad.update(filename_year=2021,filename_doy=366)
            with self.assertRaises(ValueError):h.validate_slot(bad,0)
            for field,value in (('location',''),('channel','HHE'),('station','abcdef')):
                bad=copy.deepcopy(plan['slots'][0]);bad['expected_nslc'][field]=value
                with self.assertRaises(ValueError):h.validate_slot(bad,0)

    def test_bad_fourth_path_fails_before_any_body_read(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory)
            plan=json.loads(Path(args.plan).read_bytes());plan['slots'][3]['body_path']='relative_fourth'
            Path(args.plan).write_text(json.dumps(plan));args.plan_sha256=h.digest(Path(args.plan).read_bytes())
            auth=json.loads(Path(args.authorization).read_bytes());auth['plan_sha256']=args.plan_sha256
            Path(args.authorization).write_text(json.dumps(auth));args.authorization_sha256=h.digest(Path(args.authorization).read_bytes())
            with patch.object(h,'verify_runtime',side_effect=AssertionError('must not start runtime/decoder')):
                with self.assertRaises(ValueError):h.run(args)

    def test_trusted_parent_pin_and_authority_fail_before_body_read(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory);args.authorization_sha256='0'*64
            with self.assertRaises(ValueError):h.validate_gate(args)
            args=self.fixture(directory);auth=json.loads(Path(args.authorization).read_bytes());auth['offline_decode_authorized']=False
            Path(args.authorization).write_text(json.dumps(auth));args.authorization_sha256=h.digest(Path(args.authorization).read_bytes())
            with self.assertRaises(ValueError):h.validate_gate(args)

    def test_regular_pinned_reader_symlinks_fifo_cap_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();p=root/'invented';p.write_bytes(b'1234');link=root/'link';link.symlink_to(p)
            for path,cap,deadline in ((str(link),4,time.monotonic()+1),(str(p),3,time.monotonic()+1),(str(p),4,time.monotonic()-1)):
                with self.assertRaises((ValueError,TimeoutError)):h.bounded_read(path,cap,deadline)
            import os
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(ValueError):h.bounded_read(str(fifo),4,time.monotonic()+1)

    def test_json_output_and_duplicate_nonfinite_guards(self):
        for body in (b'{"a":1,"a":2}',b'{"a":NaN}'):
            with self.assertRaises(ValueError):h.strict_json(body)
        with patch.object(h,'OUTPUT_CAP',64),self.assertRaises(ValueError):h.bounded_result({'large':'x'*100})
        with self.assertRaises(ValueError):h.bounded_result({'bad':float('nan')})

    def test_actual_source_only_four_body_invented_supervised_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory)
            receipt=s.supervise(runtime=args.runtime_path,runtime_sha256=args.runtime_sha256,
                child=str(ROOT/'child_harness.py'),child_sha256=args.adapter_sha256,supervisor_sha256=args.supervisor_sha256,
                plan=args.plan,plan_sha256=args.plan_sha256,authorization=args.authorization,
                authorization_sha256=args.authorization_sha256,out_dir=str(Path(directory).resolve()/'exclusive_output'))
            self.assertTrue(receipt['complete'],receipt)
            result=json.loads((Path(directory)/'exclusive_output/private_result.json').read_bytes())
            self.assertEqual(len(result['private']['slots']),4)
            self.assertEqual(result['public_aggregate']['complete_decoded_trace_windows'],{'1':4,'3':4,'5':4})

    def test_failed_object_remains_all_four_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            args=self.fixture(directory)
            plan=json.loads(Path(args.plan).read_bytes());p=Path(plan['slots'][0]['body_path']);p.write_bytes(b'invented not miniseed')
            plan['slots'][0].update(body_bytes=p.stat().st_size,body_sha256=h.digest(p.read_bytes()))
            Path(args.plan).write_text(json.dumps(plan));args.plan_sha256=h.digest(Path(args.plan).read_bytes())
            auth=json.loads(Path(args.authorization).read_bytes());auth['plan_sha256']=args.plan_sha256
            Path(args.authorization).write_text(json.dumps(auth));args.authorization_sha256=h.digest(Path(args.authorization).read_bytes())
            result=h.run(args)
            self.assertEqual(len(result['private']['slots']),4)
            self.assertEqual(result['public_aggregate']['failed_slots'],1)
            self.assertIsNone(result['private']['slots'][0]['windows']['1']['core']['available'])

if __name__=='__main__':unittest.main()

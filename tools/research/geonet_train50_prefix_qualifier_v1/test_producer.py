"""Invented manual records and local adapter tests; no actual inputs or encoder."""

import copy
from fractions import Fraction
import hashlib
import json
import math
import struct
import unittest
from unittest.mock import patch

import producer
import offline_decoder
import scanner
from decode_contract import ObservedDecodeFailure

START = 1704067200000000000


def raw_record(channel="HHZ", values=None, *, start_second=0, factor=1,
               multiplier=1, encoding=3, correction=0, activity=0,
               micros=None, rate100=None, station="ABC", reserved=0):
    values = list(range(9)) if values is None else values
    raw = bytearray(256)
    raw[:20] = b"000001D " + station.ljust(5).encode() + b"  " + channel.encode() + b"NZ"
    kinds = [1000] + ([100] if rate100 is not None else []) + ([1001] if micros is not None else [])
    offsets, cursor = [], 48
    for kind in kinds:
        offsets.append(cursor);cursor += 12 if kind == 100 else 8
    struct.pack_into(">HHBBBBHHhhBBBBiHH",raw,20,2024,1,0,0,start_second,0,0,len(values),
                     factor,multiplier,activity,0,0,len(kinds),correction,cursor,48)
    for i,(kind,offset) in enumerate(zip(kinds,offsets)):
        struct.pack_into(">HH",raw,offset,kind,offsets[i+1] if i+1<len(kinds) else 0)
        if kind == 1000:
            struct.pack_into("BBBB",raw,offset+4,encoding,1,8,reserved)
        elif kind == 100:
            struct.pack_into(">fBBBB",raw,offset+4,rate100,0,0,0,0)
        else:
            struct.pack_into("BbBB",raw,offset+4,90,micros,0,0)
    fmt = {1:"h",3:"i",4:"f",5:"d"}.get(encoding)
    if fmt:
        struct.pack_into(">"+fmt*len(values),raw,cursor,*values)
    return bytes(raw)


def fake_decode(raw,d):
    start,rate,_ = producer.header_grid(d)
    code = {1:"h",3:"i",4:"f",5:"d"}[d["encoding"]]
    values = list(struct.unpack_from(">"+code*d["npts"],raw,d["data_offset"]))
    return dict(start_ns=start,rate=float(rate),dtype={1:"i4",3:"i4",4:"f4",5:"f8"}[d["encoding"]],values=values)


def inputs(body=None):
    body=b''.join(raw_record('HH'+suffix) for suffix in 'EN12Z') if body is None else body
    rows=[]
    for i in range(50):
        family='ENZ' if i<32 else '12Z' if i<44 else None
        suffixes='ENZ' if family=='ENZ' else '12Z' if family=='12Z' else ''
        rows.append(dict(ordinal=i,global_ordinal=65+i,partition='TRAIN',batch=i//4,queryable=True,
                         network='NZ',station='ABC',location='',prefix='HH',t0_ns=START+3_000_000_000,
                         pick_ns=START+3_500_000_000,family=family,nominal_rates={'HH'+code:[1,1] for code in suffixes}))
    bodies={i:body for i in range(13)}
    batches=[dict(ordinal=i,rows=list(range(4*i,min(4*i+4,50))),requested_rows=list(range(4*i,min(4*i+4,50))),
                  transport='http200',body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest()) for i in range(13)]
    return dict(study=producer.STUDY,rows=rows,batches=batches),bodies


def no_selection(plan,bodies,indices):
    for i in indices:
        plan['rows'][i].update(queryable=False,network=None,station=None,location=None,prefix=None,pick_ns=None,family=None,nominal_rates={})
    for batch in plan['batches']:
        batch['requested_rows']=[i for i in batch['rows'] if plan['rows'][i]['queryable']]
        if not batch['requested_rows']:
            batch.update(transport='no_selection',body_bytes=0,body_sha256=None);bodies[batch['ordinal']]=None
    return plan,bodies


class ProducerTests(unittest.TestCase):
    def test_fixed_accounting_unknown_metadata_and_all_horizons(self):
        plan,bodies=inputs();r=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(r["disposition"],"complete")
        self.assertEqual(len(r["rows"]),50)
        self.assertEqual(sum(len(x["cells"]) for x in r["rows"]),150)
        self.assertEqual(len(r["records"]),65)
        for h in r["aggregate"]["horizons"]:
            self.assertEqual(h["complete_joint"],44)
            self.assertEqual(h["metadata_unknown_complete_components"],30)
        self.assertEqual(r["rows"][49]["cells"][0]["joint"]["reason"],"metadata_unknown")
        self.assertTrue(all(v is False for v in r["claims"].values()))

    def test_strict_plan_bool_types_extra_test_and_bad_body_pin_before_callback(self):
        plan,bodies=inputs()
        cases=[]
        for field,value in (("ordinal",False),("batch",False),("t0_ns",True),("partition","TEST"),("location"," ")):
            bad=copy.deepcopy(plan);bad["rows"][0][field]=value;cases.append(bad)
        bad=copy.deepcopy(plan);bad["extra"]=1;cases.append(bad)
        bad=copy.deepcopy(plan);bad["batches"][0]["rows"][0]=False;cases.append(bad)
        bad=copy.deepcopy(plan);bad["rows"][0]["nominal_rates"]["HHE"]=[True,1];cases.append(bad)
        for bad in cases:
            with self.assertRaises(ValueError):producer.qualify(bad,bodies,lambda *a:self.fail("decode invoked"))
        altered=dict(bodies);altered[0]=bodies[0]+b"x"
        with self.assertRaises(ValueError):producer.qualify(plan,altered,lambda *a:self.fail("decode invoked"))

    def test_schema_subclasses_and_no_context_hooks(self):
        class Evil(str):
            def __eq__(self,other):raise AssertionError("hook invoked")
        plan,bodies=inputs();plan["study"]=Evil(producer.STUDY)
        with self.assertRaises(ValueError):producer.qualify(plan,bodies,fake_decode)
        plan,bodies=inputs();bodies[False]=bodies.pop(0)
        with self.assertRaises(ValueError):producer.qualify(plan,bodies,fake_decode)

    def test_transport_nonpositive_retains_denominator(self):
        plan,bodies=inputs();plan["batches"][0].update(transport="no_data",body_bytes=0,body_sha256=None);bodies[0]=None
        r=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(r["batches"][0]["status"],"nonpositive")
        self.assertEqual(r["rows"][0]["cells"][0]["components"][0]["reason"],"transport_nonpositive")
        self.assertEqual(r["aggregate"]["rows"],50)
        self.assertEqual(r["aggregate"]["horizons"][0]["complete_joint"],40)

    def test_exact_global_indices_final_two_dynamic_metadata_and_old_reject(self):
        plan,bodies=inputs();r=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(r['rows'][-1]['global_ordinal'],114)
        self.assertEqual(plan['batches'][-1]['rows'],[48,49])
        self.assertEqual(r['aggregate']['metadata_unknown'],6)
        self.assertEqual(r['aggregate']['dev'],0)
        for field,value in [('global_ordinal',False),('global_ordinal',66),('partition','DEV'),('queryable',1)]:
            bad=copy.deepcopy(plan);bad['rows'][0][field]=value
            with self.assertRaises(ValueError):producer.qualify(bad,bodies,lambda *_:self.fail('invalid profile decode'))
        bad=copy.deepcopy(plan);bad['study']='geonet-original-TRAINDEV65-prefix3-native-POST-v2'
        with self.assertRaises(ValueError):producer.qualify(bad,bodies,fake_decode)

    def test_no_target_all_fifty_preserved_without_decode_or_clock_fabrication(self):
        plan,bodies=no_selection(*inputs(),range(50))
        plan['rows'][0]['t0_ns']=None
        result=producer.qualify(plan,bodies,lambda *_:self.fail('no selection decoded'))
        self.assertEqual(result['disposition'],'complete')
        self.assertEqual(len(result['rows']),50)
        self.assertEqual(sum(len(r['cells']) for r in result['rows']),150)
        self.assertEqual(result['records'],[])
        self.assertEqual(result['aggregate']['no_target_rows'],50)
        self.assertIsNone(result['rows'][0]['cells'][0]['cutoff_ns'])
        self.assertIsNone(result['rows'][1]['cells'][0]['pick_before_cutoff'])
        self.assertEqual(result['rows'][0]['cells'][0]['joint']['reason'],'selection_unknown')
        self.assertEqual(result['aggregate']['batch_statuses']['nonpositive'],13)

    def test_mixed_no_target_cannot_route_and_no_selection_membership_exact(self):
        plan,bodies=no_selection(*inputs(),[0,48,49])
        result=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(result['records'][0]['routed_rows'],[1,2,3])
        self.assertEqual(result['rows'][0]['cells'][0]['components'],[])
        self.assertEqual(result['batches'][-1]['status'],'nonpositive')
        bad=copy.deepcopy(plan);bad['batches'][0]['requested_rows']=[0,1,2,3]
        with self.assertRaises(ValueError):producer.qualify(bad,bodies,lambda *_:self.fail('bad subset decoded'))
        bad=copy.deepcopy(plan);bad['rows'][0]['station']='ABC'
        with self.assertRaises(ValueError):producer.qualify(bad,bodies,fake_decode)

    def test_long_original_station_never_native_truncated_or_replaced(self):
        plan,bodies=inputs();plan['rows'][0]['station']='ABCDEFGH'
        result=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(plan['rows'][0]['station'],'ABCDEFGH')
        self.assertEqual(result['rows'][0]['cells'][0]['components'][0]['reason'],'missing_component')
        self.assertEqual(result['rows'][0]['cells'][0]['joint']['status'],'unknown')
        self.assertNotIn(0,result['records'][0]['routed_rows'])

    def test_header_clock_correction_microseconds_and_exact_rates(self):
        raw=raw_record(correction=-20,micros=-7)
        d=scanner.scan(raw)["records"][0]
        start,rate,period=producer.header_grid(d)
        self.assertEqual(start,START-2_007_000)
        self.assertEqual((rate,period),(Fraction(1),Fraction(1_000_000_000)))
        d=scanner.scan(raw_record(correction=123,activity=2))["records"][0]
        self.assertEqual(producer.header_grid(d)[0],START)
        d=scanner.scan(raw_record(factor=-2,multiplier=3))["records"][0]
        self.assertEqual(producer.header_grid(d)[1],Fraction(3,2))
        d=scanner.scan(raw_record(rate100=0.3))["records"][0]
        self.assertEqual(producer.header_grid(d)[1],Fraction.from_float(d["b100"][0]))

    def test_unsupported_timing_does_not_decode(self):
        for raw in (raw_record(reserved=1),raw_record(activity=0x10),raw_record(factor=0)):
            plan,bodies=inputs(raw)
            r=producer.qualify(plan,bodies,lambda *a:self.fail("decode invoked"))
            self.assertTrue(all(b["reason"]=="timing_unknown" for b in r["batches"]))

    def test_zero_records_retained_without_callback(self):
        plan,bodies=inputs(raw_record(values=[]))
        r=producer.qualify(plan,bodies,lambda *a:self.fail("zero decoded"))
        self.assertEqual(len(r["records"]),13)
        self.assertEqual(r["records"][0]["dtype"],"empty")
        self.assertEqual(r["records"][0]["samples_sha256"],hashlib.sha256(b"empty\0").hexdigest())
        self.assertEqual(r["aggregate"]["horizons"][0]["complete_joint"],0)

    def test_unexpected_identity_batch_veto_no_partial_promotion(self):
        body=raw_record("HHE")+raw_record("HHZ",station="XYZ")
        plan,bodies=inputs(body);r=producer.qualify(plan,bodies,fake_decode)
        self.assertTrue(all(b["reason"]=="unexpected_identity" for b in r["batches"]))
        self.assertEqual(len(r["records"]),26)
        self.assertEqual(r["records"][1]["routed_rows"],[])
        self.assertTrue(all(c["status"]=="unknown" for c in r["rows"][0]["cells"][0]["components"]))

    def test_shared_record_routes_to_every_row_and_cutoff_pick_exclusion(self):
        plan,bodies=inputs();plan["rows"][0]["pick_ns"]=plan["rows"][0]["t0_ns"]+1_000_000_000
        r=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(r["records"][0]["routed_rows"],[0,1,2,3])
        c=r["rows"][0]["cells"][0]["components"][0]
        self.assertEqual((c["pieces"][0]["lo"],c["pieces"][0]["hi"]),(0,4))
        self.assertEqual(c["last"],[START+3_000_000_000,1])
        self.assertFalse(r["rows"][0]["cells"][0]["pick_before_cutoff"])

    def test_exact_missing_edge_gap_overlap_and_phase(self):
        row=inputs()[0]["rows"][0]
        good=producer._piece(0,list(range(9)),"i4",START,Fraction(1_000_000_000),START,START+4_000_000_000)
        batch=dict(status="decoded")
        self.assertEqual(producer._component("HHE",[good],row,1,batch,{"HHE"})["status"],"complete")
        shifted=copy.deepcopy(good);shifted["first"][0]+=1_000_000_000
        self.assertEqual(producer._component("HHE",[shifted],row,1,batch,{"HHE"})["reason"],"edge")
        self.assertEqual(producer._component("HHE",[good,good],row,1,batch,{"HHE"})["reason"],"gap_overlap")
        self.assertGreater(producer._phase(Fraction(5000),Fraction(1_000_000_000)),Fraction(1000))

    def test_later_nan_does_not_veto_earlier_prefix(self):
        values=list(range(9));values[7]=math.nan
        body=b"".join(raw_record("HH"+s,values,encoding=4) for s in "EN12Z")
        plan,bodies=inputs(body);r=producer.qualify(plan,bodies,fake_decode)
        cells=r["rows"][0]["cells"]
        self.assertEqual(cells[0]["joint"]["status"],"complete")
        self.assertEqual(cells[1]["joint"]["status"],"complete")
        self.assertEqual(cells[2]["components"][0]["reason"],"nonfinite")
        self.assertIsNone(cells[2]["components"][0]["minimum"])
        json.dumps(r,allow_nan=False)

    def test_later_rate_change_local_isolation(self):
        body=b"".join(raw_record("HH"+s,values=list(range(4)))+raw_record("HH"+s,values=list(range(8)),start_second=4,factor=2) for s in "EN12Z")
        plan,bodies=inputs(body);r=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(r["rows"][0]["cells"][0]["joint"]["status"],"complete")
        self.assertEqual(r["rows"][0]["cells"][1]["components"][0]["reason"],"mixed_rate")

    def test_metadata_mismatch_separate_and_no_family_switch(self):
        plan,bodies=inputs();plan["rows"][0]["nominal_rates"]["HHE"]=[2,1]
        r=producer.qualify(plan,bodies,fake_decode)
        cell=r["rows"][0]["cells"][0]
        self.assertEqual(cell["joint"]["status"],"complete")
        self.assertIs(next(c for c in cell["components"] if c["channel"]=="HHE")["metadata_rate_match"],False)
        self.assertEqual(cell["joint"]["channels"],["HHE","HHN","HHZ"])

    def test_hash_width_order_and_ordered_view_composition(self):
        self.assertEqual(producer.sample_hash([1,-2],"i4"),hashlib.sha256(b"i4\0"+struct.pack("<ii",1,-2)).hexdigest())
        self.assertNotEqual(producer.sample_hash([1.0],"f4"),producer.sample_hash([1.0],"f8"))
        plan,bodies=inputs();r=producer.qualify(plan,bodies,fake_decode)
        c=r["rows"][0]["cells"][0]["components"][0]
        keys=("record","lo","hi","count","first","last","period","dtype","samples_sha256")
        digest=hashlib.sha256(producer.canonical([{k:p[k] for k in keys} for p in c["pieces"]])).hexdigest()
        self.assertEqual(c["view_sha256"],digest)

    def test_extreme_runs_descriptive_across_record_boundary(self):
        body=b"".join(raw_record("HH"+s,[7]*4)+raw_record("HH"+s,[7]*5,start_second=4) for s in "EN12Z")
        plan,bodies=inputs(body);r=producer.qualify(plan,bodies,fake_decode)
        c=r["rows"][0]["cells"][2]["components"][0]
        self.assertEqual(c["extreme_run"],8)
        self.assertIs(c["flat"],True)
        self.assertIs(r["claims"]["hardware_clipping_verified"],False)

    def test_decode_mismatch_and_controlled_errors_unknown(self):
        plan,bodies=inputs()
        for key,value in (("start_ns",START+1),("rate",1.001),("dtype","f8")):
            def bad(raw,d):
                result=fake_decode(raw,d);result[key]=value;return result
            r=producer.qualify(plan,bodies,bad)
            self.assertTrue(all(b["reason"]=="decode_unknown" for b in r["batches"]))
        def fail(*args):raise ValueError("private vendor details")
        r=producer.qualify(plan,bodies,fail)
        self.assertNotIn("private vendor details",producer.canonical(r).decode())

    def test_runtime_memory_budget_timeout_fatal_zero_promotion(self):
        plan,bodies=inputs()
        for error in (RuntimeError,MemoryError):
            def fail(*args):raise error("private runtime detail")
            r=producer.qualify(plan,bodies,fail)
            self.assertEqual((r["disposition"],r["reason"]),("incomplete","runtime_failure"))
            self.assertEqual(r["aggregate"]["horizons"][0]["complete_joint"],0)
            self.assertEqual(sum(len(x["cells"]) for x in r["rows"]),150)
        with patch.object(producer,"MAX_TOTAL_SAMPLES",40):
            self.assertEqual(producer.qualify(plan,bodies,fake_decode)["reason"],"sample_cap")
        with patch.object(producer.time,"monotonic",side_effect=[0,301]):
            self.assertEqual(producer.qualify(plan,bodies,fake_decode)["reason"],"wall_timeout")

    def test_observed_overdelivery_counted_before_reconciliation_and_budget_fatal(self):
        plan,bodies=inputs()
        def extra(raw,d):
            value=fake_decode(raw,d);value['values'].append(123);return value
        r=producer.qualify(plan,bodies,extra)
        self.assertEqual(r['disposition'],'complete')
        self.assertTrue(all(b['reason']=='decode_unknown' and b['observed_samples']==10 for b in r['batches']))
        class TooMany:
            def __len__(self):return 8_000_001
            def __iter__(self):raise AssertionError('overbudget values visited')
        def too_many(raw,d):
            value=fake_decode(raw,d);value['values']=TooMany();return value
        r=producer.qualify(plan,bodies,too_many)
        self.assertEqual((r['disposition'],r['reason']),('incomplete','sample_cap'))
        self.assertEqual(r['batches'][0]['observed_samples'],8_000_001)
        self.assertTrue(all(h['complete_joint']==0 for h in r['aggregate']['horizons']))
        def fifty(raw,d):
            value=fake_decode(raw,d);value['values']=[0]*50;return value
        with patch.object(producer,'MAX_TOTAL_SAMPLES',140):r=producer.qualify(plan,bodies,fifty)
        self.assertEqual((r['disposition'],r['reason']),('incomplete','sample_cap'))
        self.assertEqual(sum(b['observed_samples'] for b in r['batches']),150)
        self.assertEqual(sum(len(row['cells']) for row in r['rows']),150)

    def test_structured_received_failure_counts_charged_or_whole_fatal(self):
        plan,bodies=inputs()
        def failed(*_):raise ObservedDecodeFailure(10)
        r=producer.qualify(plan,bodies,failed)
        self.assertTrue(all(b['observed_samples']==10 and b['reason']=='decode_unknown' for b in r['batches']))
        def overbudget(*_):raise ObservedDecodeFailure(8_000_001)
        r=producer.qualify(plan,bodies,overbudget)
        self.assertEqual((r['disposition'],r['reason']),('incomplete','sample_cap'))
        self.assertEqual(r['records'],[])
        self.assertTrue(all(h['complete_joint']==0 for h in r['aggregate']['horizons']))
        def malformed(*_):
            error=ObservedDecodeFailure(1);error.observed_samples=True;raise error
        r=producer.qualify(plan,bodies,malformed)
        self.assertEqual((r['disposition'],r['reason']),('incomplete','runtime_failure'))
        for bad in (True,-1,2**63,1.0):
            with self.assertRaises(RuntimeError):ObservedDecodeFailure(bad)

    def test_native_received_arrays_reconciled_failures_are_not_silently_discarded(self):
        try:import obspy,numpy
        except ImportError:self.skipTest('existing pinned native runtime required')
        from types import SimpleNamespace
        with patch.object(offline_decoder,'verify_live_limits',return_value={}):decode=offline_decoder.make_decoder()
        def trace(values,station='ABC',npts=None):
            return SimpleNamespace(data=values,stats=SimpleNamespace(network='NZ',station=station,location='',channel='HHE',
                                   npts=len(values) if npts is None else npts,starttime=SimpleNamespace(ns=START),sampling_rate=1.0))
        raw=raw_record('HHE');descriptor=scanner.scan(raw)['records'][0]
        for traces,count in (([trace(numpy.zeros(10,dtype=numpy.int32))],10),
                             ([trace(numpy.zeros(9,dtype=numpy.int32),station='XYZ')],9),
                             ([trace(numpy.zeros(9,dtype=numpy.complex64))],9),
                             ([trace(numpy.zeros(9,dtype=numpy.int32)),trace(numpy.zeros(9,dtype=numpy.int32))],18)):
            with patch.object(obspy,'read',return_value=traces):
                with self.assertRaises(ObservedDecodeFailure) as ctx:decode(raw,descriptor)
                self.assertEqual(ctx.exception.observed_samples,count)
        plan,bodies=inputs()
        traces=[trace(numpy.zeros(8_000_001,dtype=numpy.int32))]
        with patch.object(obspy,'read',return_value=traces):r=producer.qualify(plan,bodies,decode)
        self.assertEqual((r['disposition'],r['reason']),('incomplete','sample_cap'))
        self.assertEqual(r['batches'][0]['observed_samples'],8_000_001)
        self.assertTrue(all(h['complete_joint']==0 for h in r['aggregate']['horizons']))

    def test_output_cap_bounded_incomplete_or_no_result(self):
        plan,bodies=inputs()
        with patch.object(producer,"MAX_PRIVATE",512*1024),patch.object(producer,"_HEADROOM",511*1024):
            r=producer.qualify(plan,bodies,fake_decode)
            self.assertEqual(r["reason"],"output_cap")
            self.assertLessEqual(len(producer.canonical(r)),512*1024)
            self.assertTrue(all(h["complete_joint"]==0 for h in r["aggregate"]["horizons"]))
        with patch.object(producer,"MAX_PRIVATE",1000),patch.object(producer,"_HEADROOM",0):
            with self.assertRaises(RuntimeError):producer.qualify(plan,bodies,fake_decode)

    def test_scanner_sample_and_output_budget_failures_are_whole_fatal(self):
        plan,bodies=inputs()
        for reason in ("sample_cap","output_cap"):
            with patch.object(producer.scanner,"scan",return_value={"disposition":"unknown","reason":reason}):
                r=producer.qualify(plan,bodies,lambda *a:self.fail("budget decoded"))
            self.assertEqual((r["disposition"],r["reason"]),("incomplete",reason))
            self.assertEqual(sum(len(row["cells"]) for row in r["rows"]),150)
            self.assertTrue(all(h["complete_joint"]==0 for h in r["aggregate"]["horizons"]))

    def test_last_decode_and_final_serialization_deadline_cannot_promote(self):
        plan,bodies=inputs()
        now=[0]
        calls=[0]
        def slow_final(raw,d):
            calls[0]+=1
            value=fake_decode(raw,d)
            if calls[0]==65:now[0]=301
            return value
        with patch.object(producer.time,"monotonic",side_effect=lambda:now[0]):
            r=producer.qualify(plan,bodies,slow_final)
        self.assertEqual(r["reason"],"wall_timeout")
        self.assertTrue(all(h["complete_joint"]==0 for h in r["aggregate"]["horizons"]))
        real_canonical=producer.canonical
        now[0]=0
        def slow_output(value):
            data=real_canonical(value)
            if type(value) is dict and value.get("schema")=="geonet-TRAIN50-prefix-qualification-v1":now[0]=301
            return data
        with patch.object(producer.time,"monotonic",side_effect=lambda:now[0]),patch.object(producer,"canonical",side_effect=slow_output):
            r=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(r["reason"],"wall_timeout")
        self.assertTrue(all(h["complete_joint"]==0 for h in r["aggregate"]["horizons"]))

    def test_strict_json_duplicates_nonfinite_and_linux_guard(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):offline_decoder.load_json(raw)
        with patch.object(offline_decoder.sys,"platform","darwin"):
            with self.assertRaises(RuntimeError):offline_decoder.make_decoder()

    def test_native_adapter_invented_record_only(self):
        try:import obspy
        except ImportError:self.skipTest("native lane requires existing pinned ObsPy1.5.1")
        self.assertEqual(obspy.__version__,"1.5.1")
        with patch.object(offline_decoder,"verify_live_limits",return_value={}):
            decode=offline_decoder.make_decoder()
        for encoding,values in ((1,[1,2,3]),(3,[1,2,3]),(4,[1.25,2.5]),(5,[1.25,2.5])):
            raw=raw_record(values=values,encoding=encoding,correction=-20,micros=-7)
            d=scanner.scan(raw)["records"][0];decoded=decode(raw,d)
            self.assertEqual(decoded["start_ns"],START-2_007_000)
            self.assertEqual(list(decoded["values"]),values)
            self.assertEqual(decoded["rate"],1.0)
        # The patched test guard is invented, and proves no Linux containment.

    def test_b1001_reserved_opaque_uint8_retained_without_timing_or_sample_change(self):
        reference=[]
        raw_cases=[]
        for reserved in (0,1,255):
            b=bytearray(raw_record(correction=-20,micros=-7))
            b[62]=reserved  # Manual invented B1001 +6 reserved byte.
            raw=bytes(b);raw_cases.append(raw)
            d=scanner.scan(raw)["records"][0]
            self.assertEqual(d["b1001"][2],reserved)
            plan,bodies=inputs(raw)
            result=producer.qualify(plan,bodies,fake_decode)
            self.assertEqual(result["schema"],"geonet-TRAIN50-prefix-qualification-v1")
            self.assertTrue(all(batch["status"]=="decoded" for batch in result["batches"]))
            entry=result["records"][0]
            self.assertEqual(entry["raw_sha256"],hashlib.sha256(raw).hexdigest())
            reference.append((producer.header_grid(d),fake_decode(raw,d)["values"],
                              entry["samples_sha256"],result["rows"][0]["cells"]))
        self.assertEqual(len({hashlib.sha256(raw).hexdigest() for raw in raw_cases}),3)
        self.assertEqual(reference[0],reference[1]);self.assertEqual(reference[1],reference[2])
        try:import obspy
        except ImportError:return  # Pure regression above still runs without vendor packages.
        self.assertEqual(obspy.__version__,"1.5.1")
        with patch.object(offline_decoder,"verify_live_limits",return_value={}):
            decode=offline_decoder.make_decoder()
        decoded=[]
        for raw in raw_cases:
            d=scanner.scan(raw)["records"][0];out=decode(raw,d)
            decoded.append((out["start_ns"],out["rate"],list(out["values"]),
                            producer.sample_hash(out["values"],out["dtype"])))
        self.assertEqual(decoded[0],decoded[1]);self.assertEqual(decoded[1],decoded[2])
        self.assertEqual(decoded[0][0],START-2_007_000)
        self.assertEqual(decoded[0][2],list(range(9)))


if __name__ == "__main__":unittest.main()

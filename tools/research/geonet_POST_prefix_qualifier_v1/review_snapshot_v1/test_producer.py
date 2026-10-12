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
    body = b"".join(raw_record("HH"+suffix) for suffix in "EN12Z") if body is None else body
    rows=[]
    for i in range(65):
        family = "ENZ" if i<47 else "12Z" if i<61 else None
        suffixes = "ENZ" if family=="ENZ" else "12Z" if family=="12Z" else ""
        rows.append(dict(ordinal=i,partition="TRAIN" if i<41 else "DEV",batch=i//4,
                         network="NZ",station="ABC",location="",prefix="HH",t0_ns=START+3_000_000_000,
                         pick_ns=START+3_500_000_000,family=family,
                         nominal_rates={"HH"+s:[1,1] for s in suffixes}))
    bodies={i:body for i in range(17)}
    batches=[dict(ordinal=i,rows=list(range(4*i,min(4*i+4,65))),transport="http200",
                  body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest()) for i in range(17)]
    return dict(study=producer.STUDY,rows=rows,batches=batches),bodies


class ProducerTests(unittest.TestCase):
    def test_fixed_accounting_unknown_metadata_and_all_horizons(self):
        plan,bodies=inputs();r=producer.qualify(plan,bodies,fake_decode)
        self.assertEqual(r["disposition"],"complete")
        self.assertEqual(len(r["rows"]),65)
        self.assertEqual(sum(len(x["cells"]) for x in r["rows"]),195)
        self.assertEqual(len(r["records"]),85)
        for h in r["aggregate"]["horizons"]:
            self.assertEqual(h["complete_joint"],61)
            self.assertEqual(h["metadata_unknown_complete_components"],20)
        self.assertEqual(r["rows"][64]["cells"][0]["joint"]["reason"],"metadata_unknown")
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
        self.assertEqual(r["aggregate"]["rows"],65)
        self.assertEqual(r["aggregate"]["horizons"][0]["complete_joint"],57)

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
        self.assertEqual(len(r["records"]),17)
        self.assertEqual(r["records"][0]["dtype"],"empty")
        self.assertEqual(r["records"][0]["samples_sha256"],hashlib.sha256(b"empty\0").hexdigest())
        self.assertEqual(r["aggregate"]["horizons"][0]["complete_joint"],0)

    def test_unexpected_identity_batch_veto_no_partial_promotion(self):
        body=raw_record("HHE")+raw_record("HHZ",station="XYZ")
        plan,bodies=inputs(body);r=producer.qualify(plan,bodies,fake_decode)
        self.assertTrue(all(b["reason"]=="unexpected_identity" for b in r["batches"]))
        self.assertEqual(len(r["records"]),34)
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
            self.assertEqual(sum(len(x["cells"]) for x in r["rows"]),195)
        with patch.object(producer,"MAX_TOTAL_SAMPLES",40):
            self.assertEqual(producer.qualify(plan,bodies,fake_decode)["reason"],"sample_cap")
        with patch.object(producer.time,"monotonic",side_effect=[0,301]):
            self.assertEqual(producer.qualify(plan,bodies,fake_decode)["reason"],"wall_timeout")

    def test_output_cap_bounded_incomplete_or_no_result(self):
        plan,bodies=inputs()
        with patch.object(producer,"MAX_PRIVATE",512*1024),patch.object(producer,"_HEADROOM",511*1024):
            r=producer.qualify(plan,bodies,fake_decode)
            self.assertEqual(r["reason"],"output_cap")
            self.assertLessEqual(len(producer.canonical(r)),512*1024)
            self.assertTrue(all(h["complete_joint"]==0 for h in r["aggregate"]["horizons"]))
        with patch.object(producer,"MAX_PRIVATE",1000),patch.object(producer,"_HEADROOM",0):
            with self.assertRaises(RuntimeError):producer.qualify(plan,bodies,fake_decode)

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


if __name__ == "__main__":unittest.main()

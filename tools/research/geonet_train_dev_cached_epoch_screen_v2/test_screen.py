"""All projection, request, XML, names and clocks are invented synthetic fixtures."""
import copy
import hashlib
import json
import tracemalloc
import unittest
from unittest.mock import patch
import auditor as a
import selector as s
import v1_reference as v1

T0 = v1.parse_ns("2020-01-02T03:04:05.123456789Z")
START = 'startDate="2019-01-01T00:00:00Z"'
END = 'endDate="2021-01-01T00:00:00Z"'


def target(index=0, queryable=True, **changes):
    result=dict(target_index=index,network="NZ",station="SYN1",location="",prefix="HN",pick_ns=T0+10**9,
                queryable=queryable,unqueryable_reason=None if queryable else "invented_unqueryable")
    result.update(changes)
    return result


def projection():
    return dict(protocol=s.PROTOCOL,original_plan_sha256="1"*64,source_run_complete=False,excluded_TEST_count=31,
                rows=[dict(row_index=i,original_event_index=i,partition="TRAIN" if i<41 else "DEV",
                           event_id="invented_event_%03d"%i,t0_ns=T0,targets=[target()]) for i in range(65)])


def evidence(roster):
    return [dict(row_index=i,state="missing_exact_cache" if r["selected_target"] is not None else "no_queryable_target",
                 body_bytes=None,body_sha256=None,individual_http200_complete=False,custody_verified=False,request=None)
            for i,r in enumerate(roster["rows"])]


def request(row):
    t=row["selected_target"]
    return dict(level="channel",network=t["network"],station=t["station"],location=t["location"],channel=t["prefix"]+"?",
                start_ns=row["t0_ns"]-5*10**9,end_ns=row["t0_ns"]+5*10**9)


def channel(suffix="E",rate="100",bounds=None,response='<Response/>',extra=""):
    bounds=START+" "+END if bounds is None else bounds
    return f'<Channel code="HN{suffix}" locationCode="" {bounds}><Azimuth>90</Azimuth><Dip>0</Dip><SampleRate>{rate}</SampleRate>{response}{extra}</Channel>'


def xml(contents=None):
    contents=''.join(channel(x) for x in "ENZ") if contents is None else contents
    return f'<FDSNStationXML xmlns="{v1.NS}" schemaVersion="1.2"><Source>INVENTED</Source><Network code="NZ" {START} {END}><Station code="SYN1" {START} {END}>{contents}</Station></Network></FDSNStationXML>'.encode()


def setup(data=None,index=0,project=None):
    p=projection() if project is None else project;r=s.select(p);e=evidence(r);docs=[None]*65
    if data is not None:
        e[index].update(state="positive_cached_HTTP200",body_bytes=len(data),body_sha256=hashlib.sha256(data).hexdigest(),
                        individual_http200_complete=True,custody_verified=True,request=request(r["rows"][index]));docs[index]=data
    return p,r,e,docs


def run(data=None,index=0,project=None):
    return a.audit(*setup(data,index,project))


class SelectorTests(unittest.TestCase):
    def test_fixed_order_counts(self):
        p=projection();r=s.select(p)
        self.assertEqual(len(r["rows"]),65)
        self.assertEqual([x["original_event_index"] for x in r["rows"]],list(range(65)))
        self.assertEqual(sum(x["partition"]=="TRAIN" for x in r["rows"]),41)
        self.assertFalse(r["source_run_complete"])

    def test_first_true_and_no_fallback(self):
        p=projection();p["rows"][0]["targets"]=[target(0,False,network="bad value"),target(1),target(2,station="LATER")]
        r=s.select(p);self.assertEqual(r["rows"][0]["selected_target_index"],1)
        self.assertEqual(r["rows"][0]["selected_target"],p["rows"][0]["targets"][1])
        e=evidence(r);self.assertEqual(a.audit(p,r,e,[None]*65)["private_rows"][0]["selection"]["selected_target_index"],1)

    def test_empty_and_unqueryable_keep_events(self):
        p=projection();p["rows"][0]["targets"]=[];p["rows"][1]["targets"]=[target(queryable=False)]
        p["rows"][1]["t0_ns"]=None
        result=run(project=p)
        self.assertEqual(result["public_counts"]["overall"]["input_states"]["no_queryable_target"],2)
        self.assertEqual(len(result["private_rows"]),65)
        self.assertIsNone(result["private_rows"][1]["horizons"][0]["catalogue_pick_before_cutoff"])

    def test_nonqueryable_literals_retained_without_normalization(self):
        p=projection();p["rows"][0]["targets"]=[target(queryable=False,network="?private text",location="--",prefix="invalid",unqueryable_reason=None)]
        r=s.select(p);self.assertIsNone(r["rows"][0]["selected_target"])
        self.assertEqual(p["rows"][0]["targets"][0]["location"],"--")

    def test_selected_copy_does_not_mutate_projection(self):
        p=projection();before=copy.deepcopy(p);r=s.select(p);r["rows"][0]["selected_target"]["station"]="CHANGED"
        self.assertEqual(p,before)

    def test_cohort_count_and_TEST_rejected(self):
        for mutate in (lambda p:p["rows"].pop(),lambda p:p["rows"].append(copy.deepcopy(p["rows"][0])),
                       lambda p:p["rows"][0].update(partition="TEST"),lambda p:p["rows"][0].update(partition="DEV")):
            p=projection();mutate(p)
            with self.assertRaises(ValueError):s.select(p)

    def test_original_order_duplicates_indices(self):
        for field,value in (("row_index",1),("original_event_index",95),("original_event_index",True),("event_id","invented_event_001")):
            p=projection();p["rows"][0][field]=value
            with self.assertRaises(ValueError):s.select(p)

    def test_early_TEST_rejection_does_not_touch_documents(self):
        p,r,e,d=setup();p["rows"][0]["partition"]="TEST"
        with patch.object(v1,"_document_row",side_effect=AssertionError("must not parse")):
            with self.assertRaises(ValueError):a.audit(p,r,e,object())

    def test_strict_top_schema(self):
        for key,value in (("protocol",1),("original_plan_sha256","A"*64),("source_run_complete",0),("excluded_TEST_count",31.0)):
            p=projection();p[key]=value
            with self.assertRaises(ValueError):s.select(p)
        p=projection();p["extra"]=None
        with self.assertRaises(ValueError):s.select(p)

    def test_strict_target_schema(self):
        for field,value in (("target_index",True),("pick_ns",1.0),("queryable",1),("network",None),("prefix","HN?"),("location","--"),("unqueryable_reason","reason")):
            p=projection();p["rows"][0]["targets"][0][field]=value
            with self.assertRaises(ValueError):s.select(p)
        p=projection();p["rows"][0]["targets"]=[target(i) for i in range(9)]
        with self.assertRaises(ValueError):s.select(p)

    def test_nullable_t0_requires_nonqueryable_target(self):
        p=projection();p["rows"][0]["t0_ns"]=None
        with self.assertRaises(ValueError):s.select(p)

    def test_signed64_margins_and_printable_identity(self):
        for value in (True,v1.MAX_NS,v1.MIN_NS,1.0):
            p=projection();p["rows"][0]["t0_ns"]=value
            with self.assertRaises(ValueError):s.select(p)
        for value in ("", "line\nbreak", "é", "x"*129):
            p=projection();p["rows"][0]["event_id"]=value
            with self.assertRaises(ValueError):s.select(p)

    def test_hostile_comparisons_never_run(self):
        class Hostile:
            def __eq__(self,x):raise RuntimeError("must not compare")
            def __ne__(self,x):raise RuntimeError("must not compare")
        for key in ("protocol","original_plan_sha256","excluded_TEST_count"):
            p=projection();p[key]=Hostile()
            with self.assertRaises(ValueError):s.select(p)
        for key in ("partition","event_id","row_index"):
            p=projection();p["rows"][0][key]=Hostile()
            with self.assertRaises(ValueError):s.select(p)

    def test_exact_container_key_and_value_types(self):
        class Key(str):pass
        class Rows(list):pass
        p=projection();p[Key("rows")]=p.pop("rows")
        with self.assertRaises(ValueError):s.select(p)
        p=projection();p["rows"]=Rows(p["rows"])
        with self.assertRaises(ValueError):s.select(p)

    def test_projection_json_cap(self):
        p=projection()
        for row in p["rows"]:
            row["targets"]=[target(i,False,network="😀"*128,station="😀"*128,location="😀"*128,prefix="😀"*128) for i in range(8)]
        with self.assertRaisesRegex(ValueError,"json_byte_cap"):s.select(p)


class AuditTests(unittest.TestCase):
    def test_all_unknown_65_195_and_partition_denominators(self):
        r=run();public=r["public_counts"]
        self.assertEqual(len(r["private_rows"]),65)
        self.assertEqual(sum(len(x["horizons"]) for x in r["private_rows"]),195)
        self.assertEqual(public["denominators"],dict(events=65,TRAIN=41,DEV=24,excluded_TEST=31,event_deadlines=195))
        for counter,count in ((public["overall"],65),(public["by_partition"]["TRAIN"],41),(public["by_partition"]["DEV"],24)):
            self.assertEqual(sum(counter["input_states"].values()),count);self.assertEqual(counter["unknown_documents"],count)
            self.assertEqual(counter["horizons"]["5"]["families"]["either"],dict(positive=0,unknown=count))
        self.assertFalse(any(public["claims"].values()))

    def test_exact_roster_replay_before_documents(self):
        p,r,e,d=setup(xml());r["rows"][0]["selected_target"]["station"]="CHANGED"
        with patch.object(v1,"_document_row",side_effect=AssertionError("must not parse")):
            with self.assertRaisesRegex(ValueError,"canonical_original_selection_mismatch"):a.audit(p,r,e,object())

    def test_roster_bool_int_swaps_and_extra_keys(self):
        for mutate in (lambda r:r["rows"][0].update(row_index=False),lambda r:r.update(excluded_TEST_count=31.0),
                       lambda r:r["rows"][0]["selected_target"].update(queryable=1),lambda r:r.update(extra=None)):
            p,r,e,d=setup();mutate(r)
            with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_original_clock_and_plan_roster_changes_rejected(self):
        for mutate in (lambda r:r["rows"][0].update(t0_ns=T0+1),lambda r:r.update(original_plan_sha256="2"*64)):
            p,r,e,d=setup();mutate(r)
            with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_individual_unknown_dispositions_retained(self):
        p,r,e,d=setup()
        for i,state in enumerate(("missing_exact_cache","HTTP204","failed","unattempted","unverified_custody")):e[i]["state"]=state
        out=a.audit(p,r,e,d)
        for i in range(5):self.assertEqual(out["private_rows"][i]["input_state"],e[i]["state"])
        self.assertEqual(out["public_counts"]["overall"]["unknown_documents"],65)

    def test_positive_custody_flags_and_pins_required(self):
        for field,value in (("body_sha256",None),("body_bytes",None),("custody_verified",False),("individual_http200_complete",False),("request",None),("custody_verified",1),("body_bytes",True)):
            p,r,e,d=setup(xml());e[0][field]=value
            with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_bad_body_sha_or_size_retained_unverified_without_parser(self):
        for field,value in (("body_sha256","0"*64),("body_bytes",0)):
            p,r,e,d=setup(xml());e[0][field]=value
            with patch.object(v1,"_document_row",side_effect=AssertionError("must not parse")):
                out=a.audit(p,r,e,d)
            self.assertEqual(out["private_rows"][0]["input_state"],"unverified_custody")
            self.assertEqual(out["public_counts"]["overall"]["unknown_documents"],65)

    def test_request_scope_time_and_types_strict(self):
        for field,value in (("level","response"),("network","XX"),("station","OTHER"),("location","--"),("channel","HN*"),("start_ns",T0-5*10**9+1),("end_ns",float(T0+5*10**9))):
            p,r,e,d=setup(xml());e[0]["request"][field]=value
            with self.assertRaises(ValueError):a.audit(p,r,e,d)
        class Hostile:
            def __ne__(self,other):raise RuntimeError("must not compare")
        p,r,e,d=setup(xml());e[0]["request"]["level"]=Hostile()
        with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_nonpositive_requests_must_still_match_original_scope(self):
        p,r,e,d=setup();e[0]["request"]=request(r["rows"][0]);e[0]["request"]["station"]="CHANGED"
        with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_document_state_pairs_strict(self):
        p,r,e,d=setup(xml());d[0]=None
        with self.assertRaises(ValueError):a.audit(p,r,e,d)
        p,r,e,d=setup();d[0]=xml()
        with self.assertRaises(ValueError):a.audit(p,r,e,d)
        p,r,e,d=setup();d[0]=bytearray(b"x")
        with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_no_target_iff_disposition_and_null_custody(self):
        p=projection();p["rows"][0]["targets"]=[]
        p,r,e,d=setup(project=p);e[0]["state"]="missing_exact_cache"
        with self.assertRaises(ValueError):a.audit(p,r,e,d)
        p,r,e,d=setup(project=p);e[0]["body_bytes"]=0
        with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_enumerated_metadata_and_cardinal_candidate(self):
        out=run(xml());row=out["private_rows"][0]
        self.assertEqual(row["document"]["literal_codes"],["HNE","HNN","HNZ"])
        self.assertTrue(row["horizons"][0]["nominal_family_candidates"]["ENZ"])
        self.assertIsNone(row["horizons"][0]["nominal_family_candidates"]["12Z"])
        self.assertEqual(out["public_counts"]["overall"]["literal_channel_count"],3)
        self.assertEqual(out["public_counts"]["overall"]["response_stage_count"],0)

    def test_numbered_names_and_candidate(self):
        out=run(xml(''.join(channel(x) for x in "12Z")))
        self.assertEqual(out["private_rows"][0]["document"]["literal_codes"],["HN1","HN2","HNZ"])
        self.assertTrue(out["private_rows"][0]["horizons"][2]["nominal_family_candidates"]["12Z"])
        self.assertIsNone(out["private_rows"][0]["horizons"][2]["nominal_family_candidates"]["ENZ"])

    def test_both_families_count_either_once(self):
        out=run(xml(''.join(channel(x) for x in "EN12Z")))
        counts=out["public_counts"]["overall"]["horizons"]["5"]["families"]
        self.assertEqual([counts[k]["positive"] for k in ("ENZ","12Z","either")],[1,1,1])

    def test_exact_decimal_value_equality(self):
        out=run(xml(channel("E","100.0")+channel("N","1e2")+channel("Z","100")))
        self.assertTrue(out["private_rows"][0]["horizons"][2]["nominal_family_candidates"]["ENZ"])

    def test_unequal_missing_and_invalid_rates_unknown(self):
        for value in ("101","0","NaN","bad"):
            out=run(xml(channel("E",value)+channel("N")+channel("Z")))
            self.assertIsNone(out["private_rows"][0]["horizons"][2]["nominal_family_candidates"]["ENZ"])
        out=run(xml(channel("E").replace('<SampleRate>100</SampleRate>','')+channel("N")+channel("Z")))
        self.assertIsNone(out["private_rows"][0]["horizons"][2]["nominal_family_candidates"]["ENZ"])

    def test_catalogue_pick_cutoff_strict_and_intersections(self):
        out=run(xml());row=out["private_rows"][0]
        self.assertEqual([h["catalogue_pick_before_cutoff"] for h in row["horizons"]],[False,True,True])
        self.assertEqual([h["family_pick_intersections"]["ENZ"] for h in row["horizons"]],[False,True,True])
        self.assertEqual(out["public_counts"]["overall"]["horizons"]["1"]["intersections"]["ENZ"]["not_positive"],1)

    def test_catalogue_pick_independent_of_missing_cache(self):
        out=run()
        self.assertTrue(out["private_rows"][0]["horizons"][2]["catalogue_pick_before_cutoff"])
        self.assertIsNone(out["private_rows"][0]["horizons"][2]["family_pick_intersections"]["ENZ"])

    def test_descriptor_only_for_unique_supported_horizon(self):
        end='endDate="2020-01-02T03:04:07.123456789Z"'
        first=channel("E","100",START+" "+end,response='<Response><Stage number="1"/></Response>')
        second=channel("E","200",'startDate="2020-01-02T03:04:07.123456789Z" '+END)
        out=run(xml(first+second+channel("N")+channel("Z")))
        ch=out["private_rows"][0]["document"]["channels"][0]
        self.assertEqual(ch["horizon_descriptors"]["1"]["sample_rate"]["exact_decimal"],"100")
        self.assertEqual(ch["horizon_descriptors"]["1"]["response"]["stage_count"],1)
        self.assertIsNone(ch["horizon_descriptors"]["3"]);self.assertIsNone(ch["horizon_descriptors"]["5"])
        self.assertTrue(out["private_rows"][0]["horizons"][0]["nominal_family_candidates"]["ENZ"])
        self.assertIsNone(out["private_rows"][0]["horizons"][1]["nominal_family_candidates"]["ENZ"])

    def test_duplicate_or_boundary_epoch_unknown_not_absent(self):
        for contents in (channel("E")+channel("E")+channel("N")+channel("Z"),
                         channel("E",bounds='startDate="2020-01-02T03:04:02.123456789Z" '+END)+channel("N")+channel("Z")):
            out=run(xml(contents));self.assertIsNone(out["private_rows"][0]["horizons"][0]["nominal_family_candidates"]["ENZ"])
            self.assertFalse(out["public_counts"]["claims"]["physical_absence"])

    def test_response_orientation_remain_descriptive(self):
        out=run(xml(channel("E",response='')+channel("N",response='<Response/><Response/>')+channel("Z",response='<Response><Stage number="1"/></Response>')))
        self.assertTrue(out["private_rows"][0]["horizons"][2]["nominal_family_candidates"]["ENZ"])
        self.assertEqual(out["public_counts"]["overall"]["response_fragment_epochs"],2)
        self.assertEqual(out["public_counts"]["overall"]["response_stage_count"],1)
        self.assertFalse(out["public_counts"]["claims"]["full_response"])

    def test_byte_pinned_v1_parser_epoch_parity(self):
        data=xml();p,r,e,d=setup(data);out=a.audit(p,r,e,d)
        slot=dict(slot_id="row_000",t0_ns=T0,network="NZ",station="SYN1",location="",prefix="HN",body_sha256=e[0]["body_sha256"],individual_http200_complete=True,custody_verified=True)
        expected=v1._document_row(data,slot);actual=copy.deepcopy(out["private_rows"][0]["document"])
        for ch in actual["channels"]:ch.pop("horizon_descriptors")
        self.assertEqual(actual,expected)

    def test_same_body_not_deduplicated_across_events(self):
        data=xml();p,r,e,d=setup(data)
        e[1]=dict(e[0],row_index=1,request=request(r["rows"][1]));d[1]=data
        out=a.audit(p,r,e,d)
        self.assertEqual(out["public_counts"]["overall"]["valid_scope_documents"],2)
        self.assertEqual(out["public_counts"]["overall"]["horizons"]["5"]["families"]["ENZ"]["positive"],2)

    def test_DEV_partition_counts(self):
        out=run(xml(),index=41)
        self.assertEqual(out["public_counts"]["by_partition"]["DEV"]["valid_scope_documents"],1)
        self.assertEqual(out["public_counts"]["by_partition"]["TRAIN"]["valid_scope_documents"],0)

    def test_per_body_cap_without_parser(self):
        data=b"x"*(a.MAX_BODY+1)
        with patch.object(v1,"_document_row",side_effect=AssertionError("must not parse")):
            out=run(data)
        self.assertEqual(out["private_rows"][0]["document"]["reason"],"document_byte_cap")
        self.assertEqual(len(out["private_rows"]),65)

    def test_total_cap_all_65_unknown_without_parser(self):
        data=b"x"*(3*1024*1024);p,r,e,d=setup(data)
        for i in (1,2):e[i]=dict(e[0],row_index=i,request=request(r["rows"][i]));d[i]=data
        with patch.object(v1,"_document_row",side_effect=AssertionError("must not parse")):
            out=a.audit(p,r,e,d)
        self.assertEqual([x["document"]["reason"] for x in out["private_rows"]],["total_document_byte_cap"]*65)
        self.assertEqual(out["public_counts"]["overall"]["unknown_documents"],65)

    def test_original_evidence_body_and_json_caps(self):
        p,r,e,d=setup();e[0]["body_bytes"]=4*1024*1024+1
        with self.assertRaises(ValueError):a.audit(p,r,e,d)
        p,r,e,d=setup();e=e[:64]
        with self.assertRaises(ValueError):a.audit(p,r,e,d)

    def test_inherited_XML_caps_malformed_scope_unknown(self):
        for data in (b'<bad',xml().replace(b'xmlns="'+v1.NS.encode()+b'"',b'xmlns="urn:bad"'),
                     xml().replace(b'<Source>',b'<Source>'+b'<X/>'*4096),
                     b'<!DOCTYPE FDSNStationXML>'+xml()):
            out=run(data);self.assertEqual(out["public_counts"]["overall"]["unknown_documents"],65)

    def test_public_privacy_and_variable_denominators(self):
        out=run(xml());text=json.dumps(out["public_counts"])
        for forbidden in ("invented_event","SYN1","HNE","2020",str(T0),"1"*64):self.assertNotIn(forbidden,text)
        counter=out["public_counts"]["overall"]
        self.assertEqual(counter["valid_scope_documents"]+counter["unknown_documents"],65)
        self.assertEqual(sum(counter["channel_support_by_horizon"]["1"].values()),3)
        self.assertEqual(counter["epoch_record_count"],3)

    def test_public_private_output_caps_fail_without_truncation(self):
        with patch.object(a,"MAX_PUBLIC_JSON",32):
            with self.assertRaisesRegex(ValueError,"json_byte_cap"):run(xml())
        with patch.object(a,"MAX_PRIVATE_JSON",32):
            with self.assertRaisesRegex(ValueError,"json_byte_cap"):run(xml())

    def test_amplified_JSON_stops_before_large_allocation(self):
        shared="S"*(128*1024);tracemalloc.start()
        try:
            with self.assertRaisesRegex(ValueError,"json_byte_cap"):s.bounded_json({"x":[shared]*128},1024*1024)
            _,peak=tracemalloc.get_traced_memory();self.assertLess(peak,4*1024*1024)
        finally:tracemalloc.stop()


if __name__ == "__main__":unittest.main()

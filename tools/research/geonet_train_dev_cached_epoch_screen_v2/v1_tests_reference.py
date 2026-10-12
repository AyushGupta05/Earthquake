"""All XML, clocks, codes and custody assertions in this file are invented."""
import copy
import hashlib
import json
import unittest
import auditor as a

T0 = a.parse_ns("2020-01-02T03:04:05.123456789Z")
START = 'startDate="2019-01-01T00:00:00Z"'
END = 'endDate="2021-01-01T00:00:00Z"'


def channel(code="HNE", *, bounds=None, location="", content=None):
    if bounds is None:
        bounds = START + " " + END
    if content is None:
        content = '<Azimuth>90.125</Azimuth><Dip>0</Dip><SampleRate>100</SampleRate><Response><InstrumentSensitivity><Value>2.5</Value><InputUnits><Name>M/S**2</Name></InputUnits><OutputUnits><Name>COUNTS</Name></OutputUnits></InstrumentSensitivity><Stage number="1"/></Response>'
    return f'<Channel code="{code}" locationCode="{location}" {bounds}>{content}</Channel>'


def xml(channels=None, *, network="NZ", station="SYN1", nbounds=None, sbounds=None, version="1.2", namespace=a.NS):
    channels = channel() + channel("HNN") if channels is None else channels
    nbounds = START + " " + END if nbounds is None else nbounds
    sbounds = START + " " + END if sbounds is None else sbounds
    return f'<FDSNStationXML xmlns="{namespace}" schemaVersion="{version}"><Source>INVENTED</Source><Created>2020-01-01T00:00:00Z</Created><Network code="{network}" {nbounds}><Station code="{station}" {sbounds}>{channels}</Station></Network></FDSNStationXML>'.encode()


def slots(documents):
    return [dict(slot_id=role, network="NZ", station="SYN1", location="", prefix="HN", t0_ns=T0,
                 body_sha256=hashlib.sha256(d).hexdigest() if d is not None else None,
                 individual_http200_complete=d is not None, custody_verified=d is not None,
                 source_run_complete=False, request_level="channel", request_network="NZ",
                 request_station="SYN1", request_location="", request_channel="HN?",
                 request_start_ns=T0-5*10**9, request_end_ns=T0+5*10**9)
            for role, d in zip(a.ROLES, documents)]


def result(data):
    docs = [data, None, None, None]
    return a.audit(docs, slots(docs))


def states(data):
    return result(data)["private_rows"][0]["channels"][0]["horizon_support"]


class CachedAuditTests(unittest.TestCase):
    def test_cardinal_complete(self):
        r = result(xml())
        self.assertEqual(len(r["private_rows"]), 4)
        self.assertEqual(r["public_counts"]["valid_scope_documents"], 1)
        self.assertEqual(r["public_counts"]["unknown_documents"], 3)
        self.assertEqual(r["public_counts"]["literal_suffix_document_presence"], dict(E=1, N=1, **{"1":0,"2":0,"other":0}))
        self.assertEqual(r["public_counts"]["epoch_support_by_horizon"]["5"]["supported"], 2)
        self.assertEqual(r["public_counts"]["response_stage_count"], 2)
        self.assertFalse(any(r["public_counts"]["claims"].values()))

    def test_numbered_not_renamed(self):
        r = result(xml(channel("HN1") + channel("HN2")))
        self.assertEqual(r["private_rows"][0]["literal_codes"], ["HN1", "HN2"])
        self.assertEqual(r["public_counts"]["literal_suffix_document_presence"]["E"], 0)

    def test_other_suffixes_descriptive(self):
        r = result(xml(channel("HNZ") + channel("HNX") + channel("HNY")))
        self.assertEqual(r["public_counts"]["literal_suffix_document_presence"]["other"], 1)
        self.assertEqual(r["public_counts"]["literal_channel_count"], 3)

    def test_scope_filters_literal_prefix_location(self):
        r = result(xml(channel() + channel("HHE") + channel(location="01") + channel("HNEA")))
        self.assertEqual(r["private_rows"][0]["literal_codes"], ["HNE"])

    def test_missing_four_unknown(self):
        r = result(None)
        self.assertEqual(r["public_counts"]["unknown_documents"], 4)
        self.assertEqual(r["public_counts"]["literal_channel_count"], 0)

    def test_missing_channel_scope_unknown(self):
        for data in (xml(""), xml(channel("HHE")), xml(network="AB"), xml(station="OTHER")):
            with self.subTest(data=data):
                self.assertEqual(result(data)["private_rows"][0]["document_state"], "unknown")

    def test_bad_pin_unknown(self):
        docs=[xml(),None,None,None]; ss=slots(docs); ss[0]["body_sha256"]="0"*64
        self.assertEqual(a.audit(docs,ss)["private_rows"][0]["document_state"],"unknown")

    def test_custody_flags_unknown(self):
        for field in ("custody_verified", "individual_http200_complete"):
            docs=[xml(),None,None,None]; ss=slots(docs); ss[0][field]=False
            self.assertEqual(a.audit(docs,ss)["private_rows"][0]["document_state"],"unknown")

    def test_exact_fractional_utc(self):
        self.assertEqual(a.parse_ns("2020-01-02T03:04:05.123456789Z"),1577934245123456789)
        self.assertEqual(a.parse_ns("2020-01-02T04:04:05.123456789+01:00"),T0)
        self.assertEqual(a.parse_ns("1969-12-31T23:59:59.999999999Z"),-1)

    def test_invalid_dates(self):
        for value in ("2020-01-01", "2020-01-01T00:00:00", "2020-01-01T00:00:60Z", "2020-02-30T00:00:00Z", "2020-01-01T00:00:00.1234567890Z", "2020-01-01T00:00:00+14:01", "2020-01-01T00:00:00+15:00", "9999-01-01T00:00:00Z", 0, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): a.parse_ns(value)

    def test_exact_signed64_limits(self):
        self.assertEqual(a.parse_ns("1677-09-21T00:12:43.145224192Z"),a.MIN_NS)
        self.assertEqual(a.parse_ns("2262-04-11T23:47:16.854775807Z"),a.MAX_NS)
        for value in ("1677-09-21T00:12:43.145224191Z", "2262-04-11T23:47:16.854775808Z"):
            with self.assertRaises(ValueError): a.parse_ns(value)

    def test_declared_left_equality_unknown(self):
        bounds='startDate="2020-01-02T03:04:02.123456789Z" '+END
        self.assertEqual(set(states(xml(channel(bounds=bounds))).values()),{"boundary_unknown"})

    def test_declared_right_equality_unknown(self):
        bounds=START+' endDate="2020-01-02T03:04:08.123456789Z"'
        self.assertEqual(states(xml(channel(bounds=bounds))),{"1":"supported","3":"boundary_unknown","5":"not_supported"})

    def test_one_ns_strict_interior(self):
        bounds='startDate="2020-01-02T03:04:02.123456788Z" endDate="2020-01-02T03:04:10.123456790Z"'
        self.assertEqual(set(states(xml(channel(bounds=bounds))).values()),{"supported"})

    def test_open_end_metadata_only(self):
        self.assertEqual(set(states(xml(channel(bounds=START),nbounds=START,sbounds=START)).values()),{"supported"})

    def test_missing_required_starts_unknown(self):
        for kwargs in (dict(channels=channel(bounds=END)), dict(nbounds=END), dict(sbounds=END)):
            self.assertEqual(set(states(xml(**kwargs)).values()),{"unknown"})

    def test_unparseable_epoch_unknown(self):
        self.assertEqual(set(states(xml(channel(bounds='startDate="bad" '+END))).values()),{"unknown"})

    def test_reversed_epoch_unknown(self):
        self.assertEqual(set(states(xml(channel(bounds='startDate="2021-01-01T00:00:00Z" endDate="2019-01-01T00:00:00Z"'))).values()),{"unknown"})

    def test_duplicate_channel_unknown(self):
        r=result(xml(channel()+channel()))
        self.assertEqual(len(r["private_rows"][0]["channels"][0]["epochs"]),2)
        self.assertEqual(set(states(xml(channel()+channel())).values()),{"unknown"})

    def test_overlapping_channel_unknown(self):
        data=xml(channel()+channel(bounds='startDate="2020-01-01T00:00:00Z" endDate="2022-01-01T00:00:00Z"'))
        self.assertEqual(set(states(data).values()),{"unknown"})

    def test_serial_epochs_unique_enclosure(self):
        earlier=channel(bounds='startDate="2018-01-01T00:00:00Z" endDate="2019-01-01T00:00:00Z"')
        self.assertEqual(set(states(xml(earlier+channel())).values()),{"supported"})

    def test_station_ends_before_window(self):
        self.assertEqual(set(states(xml(sbounds=START+' endDate="2019-12-31T00:00:00Z"')).values()),{"not_supported"})

    def test_duplicate_station_unknown(self):
        text=xml().decode(); start=text.index('<Station '); end=text.index('</Station>')+len('</Station>')
        text=text[:end]+text[start:end]+text[end:]
        self.assertEqual(set(states(text.encode()).values()),{"unknown"})

    def test_duplicate_network_unknown(self):
        text=xml().decode(); start=text.index('<Network '); end=text.index('</Network>')+len('</Network>')
        text=text[:end]+text[start:end]+text[end:]
        self.assertEqual(set(states(text.encode()).values()),{"unknown"})

    def test_numeric_descriptive_and_nonfinite(self):
        for value in ("NaN", "Infinity", "-Infinity", "bad", "-1", "361"):
            r=result(xml(channel(content=f'<Azimuth>{value}</Azimuth><Dip>91</Dip><SampleRate>0</SampleRate>')))
            rec=r["private_rows"][0]["channels"][0]["epochs"][0]
            self.assertFalse(rec["azimuth"]["valid"]); self.assertFalse(rec["dip"]["valid"]); self.assertFalse(rec["sample_rate"]["valid"])
            self.assertEqual(set(rec.get("horizon_support",{}).values()),set())
            self.assertEqual(r["private_rows"][0]["channels"][0]["horizon_support"]["5"],"supported")

    def test_positive_small_rate_no_arbitrary_threshold(self):
        r=result(xml(channel(content='<SampleRate>1e-100</SampleRate>')))
        self.assertEqual(r["public_counts"]["sample_rate_valid"],1)

    def test_duplicate_and_nested_numeric_invalid(self):
        for content in ('<Azimuth>90</Azimuth><Azimuth>90</Azimuth>', '<Azimuth><Value>90</Value></Azimuth>'):
            r=result(xml(channel(content=content)))
            self.assertEqual(r["public_counts"]["orientation_field_valid"]["azimuth"],0)

    def test_empty_response_not_complete(self):
        r=result(xml(channel(content='<Response/>')))
        self.assertEqual(r["public_counts"]["response_fragment_epochs"],1)
        self.assertEqual(r["public_counts"]["response_stage_count"],0)
        self.assertFalse(r["public_counts"]["claims"]["full_response_verified"])

    def test_duplicate_response_descriptive_only(self):
        r=result(xml(channel(content='<Response><Stage number="1"/></Response><Response/>')))
        self.assertEqual(r["public_counts"]["response_stage_count"],1)
        self.assertEqual(r["private_rows"][0]["channels"][0]["epochs"][0]["response"]["response_count"],2)

    def test_public_no_identifiers_or_dates(self):
        text=json.dumps(result(xml())["public_counts"])
        for forbidden in ("SYN1", "HNE", "NZ", "2020", "2019", str(T0), "COUNTS", "M/S"):
            self.assertNotIn(forbidden,text)

    def test_wrong_root_namespace_versions(self):
        for data in (xml(namespace="urn:invented"),xml(version="2.0"),xml().replace(b"FDSNStationXML",b"WrongRoot")):
            self.assertEqual(result(data)["private_rows"][0]["document_state"],"unknown")

    def test_recognized_versions(self):
        for version in ("1.0","1.1","1.2"):
            self.assertEqual(result(xml(version=version))["private_rows"][0]["document_state"],"valid")

    def test_wrong_hierarchy_unknown(self):
        data=xml().replace(b'<Station ',b'<Wrapper><Station ').replace(b'</Station>',b'</Station></Wrapper>')
        self.assertEqual(result(data)["private_rows"][0]["document_state"],"unknown")

    def test_missing_location_unknown(self):
        self.assertEqual(result(xml().replace(b' locationCode=""',b''))["private_rows"][0]["document_state"],"unknown")

    def test_foreign_extension_unknown(self):
        self.assertEqual(result(xml().replace(b'<Source>',b'<Source><f:Other xmlns:f="urn:f"/>'))["private_rows"][0]["document_state"],"unknown")

    def test_dtd_entities_rejected(self):
        for prefix in (b'<!DOCTYPE FDSNStationXML>',b'<!DOCTYPE FDSNStationXML [<!ENTITY evil "bad">]>',b'<!ENTITY evil SYSTEM "file:///tmp/invented">'):
            self.assertEqual(result(prefix+xml())["private_rows"][0]["document_state"],"unknown")

    def test_processing_instruction_rejected(self):
        self.assertEqual(result(b'<?invented test?>'+xml())["private_rows"][0]["document_state"],"unknown")

    def test_comments_do_not_activate_markup(self):
        data=xml().replace(b"<Source>", b"<!-- <?example?> <!DOCTYPE fake> <!ENTITY fake> --><Source>")
        self.assertEqual(result(data)["private_rows"][0]["document_state"],"valid")

    def test_cdata_does_not_activate_markup(self):
        data=xml().replace(b"INVENTED",b"<![CDATA[<?example?> <!DOCTYPE fake> <!ENTITY fake>]]>")
        self.assertEqual(result(data)["private_rows"][0]["document_state"],"valid")

    def test_real_declarations_after_comments_still_rejected(self):
        data=b"<!-- inert --> <!DOCTYPE FDSNStationXML [<!ENTITY example \"text\">]>"+xml()
        self.assertEqual(result(data)["private_rows"][0]["document_state"],"unknown")

    def test_real_pi_after_cdata_still_rejected(self):
        data=xml().replace(b"INVENTED",b"<![CDATA[inert]]><?actual pi?>")
        self.assertEqual(result(data)["private_rows"][0]["document_state"],"unknown")

    def test_malformed_comments_unknown(self):
        self.assertEqual(result(b"<!-- unterminated"+xml())["private_rows"][0]["document_state"],"unknown")

    def test_exact_slot_id_type_before_parsing(self):
        class Role(str): pass
        class EqualRole:
            def __eq__(self, other): return True
        for value in (Role("ordinary"),EqualRole()):
            ss=slots([None]*4); ss[0]["slot_id"]=value
            with self.assertRaises(ValueError): a.audit([None]*4,ss)

    def test_utf8_declaration_and_bom(self):
        self.assertEqual(result(b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?>'+xml())["private_rows"][0]["document_state"],"valid")

    def test_unsupported_encoding_unknown(self):
        for data in (b'<?xml version="1.0" encoding="ISO-8859-1"?>'+xml(),b'\xff'+xml(),b'<bad'):
            self.assertEqual(result(data)["private_rows"][0]["document_state"],"unknown")

    def test_document_cap(self):
        r=result(b" "*(a.MAX_DOCUMENT+1))
        self.assertEqual(r["private_rows"][0]["reason"],"document_byte_cap")

    def test_total_cap_all_retained(self):
        docs=[b" "*(a.MAX_DOCUMENT+1)]*4
        r=a.audit(docs,slots(docs))
        self.assertEqual([x["reason"] for x in r["private_rows"]],["total_document_byte_cap"]*4)

    def test_depth_cap(self):
        data=xml().replace(b'<Source>',b'<Source>'+b'<X>'*32).replace(b'</Source>',b'</X>'*32+b'</Source>')
        self.assertEqual(result(data)["private_rows"][0]["document_state"],"unknown")

    def test_node_cap(self):
        data=xml().replace(b'<Source>',b'<Source>'+b'<X/>'*4096)
        self.assertEqual(result(data)["private_rows"][0]["document_state"],"unknown")

    def test_slot_schema_order_strict(self):
        docs=[None]*4; ss=slots(docs)
        for bad in (ss[:3],tuple(ss),list(reversed(ss))):
            with self.assertRaises(ValueError): a.audit(docs,bad)
        for field,value in (("t0_ns",float(T0)),("t0_ns",True),("t0_ns",a.MAX_NS),("source_run_complete",True),("custody_verified",1),("request_start_ns",float(T0-5*10**9)),("request_level","response"),("request_channel","HN*"),("request_location","--"),("body_sha256","ABC"),("prefix","HN?")):
            changed=copy.deepcopy(ss); changed[0][field]=value
            with self.subTest(field=field,value=value):
                with self.assertRaises(ValueError): a.audit(docs,changed)
        changed=copy.deepcopy(ss); changed[0]["extra"]=None
        with self.assertRaises(ValueError): a.audit(docs,changed)

    def test_request_types_checked_before_custom_comparisons(self):
        class Hostile:
            def __eq__(self, other): raise RuntimeError("comparison must not run")
            def __ne__(self, other): raise RuntimeError("comparison must not run")
        for field in ("request_level","request_network","request_station","request_location","request_channel"):
            ss=slots([None]*4); ss[0][field]=Hostile()
            with self.assertRaises(ValueError): a.audit([None]*4,ss)

    def test_exact_key_string_types(self):
        class Key(str): pass
        ss=slots([None]*4); ss[0][Key("slot_id")]=ss[0].pop("slot_id")
        with self.assertRaises(ValueError): a.audit([None]*4,ss)

    def test_document_api_strict(self):
        for docs in ([None]*3,tuple([None]*4),[bytearray(b"x"),None,None,None],["x",None,None,None]):
            with self.assertRaises(ValueError): a.audit(docs,slots([None]*4))


if __name__ == "__main__":
    unittest.main()

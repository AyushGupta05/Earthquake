"""Invented XML only. No actual IDs, metadata, paths, or producer imports."""
from html import escape
import unittest

import semantic_audit as audit

EVENT = "invented-event"
PID = audit.PREFIX + "pick_A"
OID = audit.PREFIX + "origin_one"
STAMP = "2020-01-01T00:00:00Z"


def pick(pid=PID, stamp=STAMP, network="NZ", station="S0", status=None, extra="", location="", channel="HHZ"):
    status_xml = "" if status is None else "<evaluationStatus>" + escape(status) + "</evaluationStatus>"
    return (f'<pick publicID="{escape(pid, quote=True)}"><time><value>{escape(stamp)}</value></time>'
            f'<waveformID networkCode="{escape(network, quote=True)}" stationCode="{escape(station, quote=True)}" '
            f'locationCode="{escape(location, quote=True)}" channelCode="{escape(channel, quote=True)}"/>'
            + status_xml + extra + '</pick>')


def arrival(pid=PID, phase="P", weight="1", native=False, flags=None, extra=""):
    field = "weight" if native else "timeWeight"
    weight_xml = "" if weight is None else f'<{field}>{escape(weight)}</{field}>'
    flag_xml = "".join(f'<{k}>{escape(v)}</{k}>' for k, v in (flags or {}).items())
    return f'<arrival><pickID>{escape(pid)}</pickID><phase>{escape(phase)}</phase>{weight_xml}{flag_xml}{extra}</arrival>'


def origin(oid=OID, arrivals=None, depth="12000", extra="", creation=""):
    if arrivals is None:
        arrivals = arrival()
    return (f'<origin publicID="{escape(oid, quote=True)}"><time><value>{STAMP}</value></time>'
            f'<latitude><value>-40.0</value></latitude><longitude><value>175</value></longitude>'
            f'<depth><value>{escape(depth)}</value></depth>{arrivals}{extra}{creation}</origin>')


def qml(picks=None, arrivals=None, extra="", event_extra="", origins=None, preferred=OID, creation=""):
    if picks is None:
        picks = pick()
    if origins is None:
        origins = origin(arrivals=arrivals)
    return (f'<q:quakeml xmlns:q="{audit.QROOT}" xmlns="{audit.BED}" xmlns:s13="{audit.SCML["0.13"]}" '
            f'xmlns:s14="{audit.SCML["0.14"]}" xmlns:x="urn:invented:foreign"><eventParameters>'
            f'<event publicID="{audit.PREFIX + EVENT}"><preferredOriginID>{escape(preferred)}</preferredOriginID>'
            f'{picks}{origins}{event_extra}{creation}</event>{extra}</eventParameters></q:quakeml>').encode()


def scml(picks=None, arrivals=None, extra="", event_extra="", origins=None, preferred="origin:one", version="0.14", creation=""):
    if picks is None:
        picks = pick("pick:A")
    if arrivals is None:
        arrivals = arrival("pick:A", native=True)
    if origins is None:
        origins = origin("origin:one", arrivals, depth="12")
    ns = audit.SCML.get(version, audit.SCML["0.14"])
    return (f'<seiscomp xmlns="{ns}" xmlns:x="urn:invented:foreign" version="{version}"><EventParameters>'
            f'<event publicID="{EVENT}"><preferredOriginID>{escape(preferred)}</preferredOriginID>'
            f'<originReference>{escape(preferred)}</originReference>{event_extra}{creation}</event>'
            f'{picks}{origins}{extra}</EventParameters></seiscomp>').encode()


def parse(body=None, native=False):
    return audit.project(scml() if native and body is None else qml() if body is None else body,
                         EVENT, "scml" if native else "qml")


def info(contents):
    return "<creationInfo>" + contents + "</creationInfo>"


class Semantics(unittest.TestCase):
    def assert_ok(self, result):
        self.assertEqual(result["status"], "ok", result.get("reason"))
        return result

    def assert_unknown(self, result, why=None):
        self.assertEqual(result["status"], "unknown_representation")
        self.assertIsNone(result["denominators"])
        self.assertIsNone(result["accepted_picks"])
        if why:
            self.assertIn(why, result["reason"])

    def test_qml_basic(self):
        result = self.assert_ok(parse())
        self.assertEqual(result["denominators"]["accepted_NZ_P_picks"], 1)
        self.assertEqual(result["origin"]["depth_m"], "1.2E+4")

    def test_native_basic_equivalent(self):
        left, right = parse(), self.assert_ok(parse(native=True))
        result = audit.compare(left, right)
        self.assertTrue(result["same_record_content"])
        self.assertEqual(result["revision_evidence"], "missing_or_incomplete")

    def test_qml_only_event_scope(self):
        result = self.assert_ok(parse(qml(picks="", extra=pick())))
        self.assertEqual(result["denominators"]["event_scoped_pick_objects"], 0)
        self.assertEqual(result["reasons"]["missing_or_ambiguous_pick_reference"], 1)

    def test_native_unrelated_global_pick_excluded(self):
        result = self.assert_ok(parse(scml(extra=pick("pick:unrelated")), True))
        self.assertEqual(result["denominators"]["event_scoped_pick_objects"], 1)

    def test_native_amplitude_pick_link(self):
        sm = '<stationMagnitude publicID="invented-sm"><amplitudeID>amp:A</amplitudeID></stationMagnitude>'
        secondary = origin("origin:two", "", "12", extra=sm)
        amp = '<amplitude publicID="amp:A"><pickID>pick:B</pickID></amplitude>'
        result = self.assert_ok(parse(scml(picks=pick("pick:A") + pick("pick:B"),
            origins=origin("origin:one", arrival("pick:A", native=True), "12") + secondary,
            event_extra='<originReference>origin:two</originReference>', extra=amp), True))
        self.assertIn(audit.PREFIX + "pick_B", result["picks"])
        self.assertEqual(result["denominators"]["accepted_P_picks"], 1)
        self.assertEqual(result["denominators"]["event_scoped_amplitude_objects"], 1)

    def test_native_amplitude_unreferenced_excluded(self):
        result = self.assert_ok(parse(scml(picks=pick("pick:A") + pick("pick:B"),
            extra='<amplitude publicID="amp:A"><pickID>pick:B</pickID></amplitude>'), True))
        self.assertNotIn(audit.PREFIX + "pick_B", result["picks"])

    def test_native_secondary_arrival_pick_scope(self):
        result = self.assert_ok(parse(scml(picks=pick("pick:A") + pick("pick:B"),
            origins=origin("origin:one", arrival("pick:A", native=True), "12") + origin("origin:two", arrival("pick:B", native=True), "12"),
            event_extra='<originReference>origin:two</originReference>'), True))
        self.assertEqual(len(result["picks"]), 2)
        self.assertEqual(result["denominators"]["accepted_P_picks"], 1)

    def test_duplicate_pick_resolves_before_weight_rejection(self):
        result = self.assert_ok(parse(qml(picks=pick() + pick(), arrivals=arrival(weight="0"))))
        self.assertEqual(result["reasons"], {"missing_or_ambiguous_pick_reference": 1})
        self.assertEqual(result["denominators"]["unique_resolved_qualifying_P_reference_ids"], 0)

    def test_unique_pick_before_weight_rejection(self):
        result = self.assert_ok(parse(qml(arrivals=arrival(weight="0"))))
        self.assertEqual(result["denominators"]["unique_resolved_qualifying_P_reference_ids"], 1)
        self.assertFalse(result["incomplete_associated_P_structure"])

    def test_dedup_after_acceptance(self):
        result = self.assert_ok(parse(qml(arrivals=arrival(weight="0") + arrival(weight="1") + arrival(weight="1"))))
        self.assertEqual(result["denominators"]["qualifying_P_references"], 3)
        self.assertEqual(result["denominators"]["accepted_P_picks"], 1)
        self.assertEqual(result["reasons"], {"nonpositive_or_invalid_time_weight": 1})

    def test_native_literal_uri_reference_stripped_after_mapping(self):
        uri = "smi:invented/pick "
        result = self.assert_ok(parse(scml(picks=pick(uri), arrivals=arrival(uri, native=True)), True))
        self.assertIn(uri, result["picks"])
        self.assertEqual(result["unresolved_pick_ids"], [uri.strip()])
        self.assertEqual(result["denominators"]["accepted_P_picks"], 0)

    def test_qml_literal_publicid(self):
        result = self.assert_ok(parse(qml(picks=pick(PID + " "), arrivals=arrival(PID + " "))))
        self.assertEqual(result["denominators"]["accepted_P_picks"], 0)

    def test_native_preferred_uri_whitespace_unknown(self):
        uri = "smi:invented/origin "
        self.assert_unknown(parse(scml(preferred=uri, origins=origin(uri, arrival("pick:A", native=True), "12")), True), "projected_preferred")

    def test_native_raw_scope_not_mapped_scope(self):
        result = self.assert_ok(parse(scml(picks=pick("pick_A"), arrivals=arrival("pick:A", native=True)), True))
        self.assertEqual(result["denominators"]["event_scoped_pick_objects"], 0)

    def test_native_pick_mapping_collision(self):
        self.assert_unknown(parse(scml(picks=pick("pick:A") + pick("pick_A"),
            arrivals=arrival("pick:A", native=True) + arrival("pick_A", native=True)), True), "collision")

    def test_native_unresolved_reference_mapping_collision(self):
        self.assert_unknown(parse(scml(arrivals=arrival("pick:A", native=True) + arrival("pick_A", native=True)), True), "collision")

    def test_native_origin_mapping_collision(self):
        self.assert_unknown(parse(scml(origins=origin("origin:one", arrival("pick:A", native=True), "12") + origin("origin_one", "", "12"),
            event_extra='<originReference>origin_one</originReference>'), True), "collision")

    def test_native_amplitude_reference_mapping_collision(self):
        sm = '<stationMagnitude><amplitudeID>amp:A</amplitudeID></stationMagnitude><stationMagnitude><amplitudeID>amp_A</amplitudeID></stationMagnitude>'
        self.assert_unknown(parse(scml(origins=origin("origin:one", arrival("pick:A", native=True), "12", extra=sm)), True), "collision")

    def test_native_empty_reference_na_collision(self):
        body = scml(picks=pick('NA'), arrivals=arrival('', native=True) + arrival('NA', phase='S', native=True))
        self.assert_unknown(parse(body, True), 'collision')

    def test_native_whitespace_reference_na_collision(self):
        body = scml(picks=pick('NA'), arrivals=arrival('   ', native=True) + arrival('NA', phase='S', native=True))
        self.assert_unknown(parse(body, True), 'collision')

    def test_native_empty_amplitude_reference_na_collision(self):
        sm = '<stationMagnitude><amplitudeID/></stationMagnitude><stationMagnitude><amplitudeID>NA</amplitudeID></stationMagnitude>'
        body = scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm))
        self.assert_unknown(parse(body, True), 'collision')

    def test_native_empty_reference_without_scoped_na_unresolved(self):
        body = scml(picks=pick('NA'), arrivals=arrival('', native=True))
        result = self.assert_ok(parse(body, True))
        self.assertEqual(result['denominators']['accepted_P_picks'], 0)
        self.assertEqual(result['denominators']['event_scoped_pick_objects'], 0)
        self.assertEqual(result['unresolved_pick_ids'], [audit.PREFIX + 'NA'])

    def test_native_unrelated_collision_ignored(self):
        result = self.assert_ok(parse(scml(extra=pick("unrelated:X") + pick("unrelated_X")), True))
        self.assertEqual(result["denominators"]["accepted_P_picks"], 1)

    def test_native_duplicate_pick_unresolved(self):
        result = self.assert_ok(parse(scml(picks=pick("pick:A") * 2), True))
        self.assertEqual(result["unresolved_pick_ids"], [PID])

    def test_native_missing_origin_unknown(self):
        self.assert_unknown(parse(scml(origins=""), True), "referenced_origin")

    def test_native_duplicate_origin_unknown(self):
        self.assert_unknown(parse(scml(origins=origin("origin:one", "", "12") * 2), True), "referenced_origin")

    def test_native_preferred_not_referenced_unknown(self):
        body = scml().replace(b'<originReference>origin:one</originReference>', b'')
        self.assert_unknown(parse(body, True), "outside_event_scope")

    def test_qml_wrong_requested_event_unknown(self):
        self.assert_unknown(audit.project(qml(), "invented-other", "qml"), "identity_mismatch")

    def test_qml_root_namespace_unknown(self):
        self.assert_unknown(parse(qml().replace(audit.QROOT.encode(), b'urn:invented:qml')), "qml_root")

    def test_qml_bed_namespace_unknown(self):
        self.assert_unknown(parse(qml().replace(audit.BED.encode(), b'urn:invented:bed')))

    def test_native_version_namespace_mismatch_unknown(self):
        self.assert_unknown(parse(scml().replace(b'version="0.14"', b'version="0.13"'), True), "version")

    def test_native_unsupported_version_unknown(self):
        self.assert_unknown(parse(scml(version="0.12"), True), "version")

    def test_event_cardinality_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<event publicID="invented-nested"/>').replace(b'</eventParameters>', b'<event publicID="invented-other"/></eventParameters>')), "cardinality")

    def test_duplicate_preferred_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<preferredOriginID>invented-other</preferredOriginID>')), "singleton")

    def test_duplicate_timeweight_unknown(self):
        self.assert_unknown(parse(qml(arrivals=arrival(extra='<timeWeight>1</timeWeight>'))), "singleton")

    def test_duplicate_waveform_unknown(self):
        self.assert_unknown(parse(qml(picks=pick(extra='<waveformID networkCode="NZ" stationCode="S1"/>'))), "singleton")

    def test_non_scalar_pick_reference_unknown(self):
        body = qml().replace(b'<pickID>', b'<pickID><x:invented/>')
        self.assert_unknown(parse(body), "non_scalar")

    def test_non_scalar_native_origin_reference_unknown(self):
        body = scml().replace(b'<originReference>', b'<originReference><x:invented/>')
        self.assert_unknown(parse(body, True), "non_scalar")

    def test_foreign_structural_substitution_unknown(self):
        body = qml().replace(b'<timeWeight>1</timeWeight>', b'<x:timeWeight>1</x:timeWeight>')
        self.assert_unknown(parse(body), "foreign_evidence")

    def test_foreign_station_attribute_unknown(self):
        body = qml().replace(b'networkCode="NZ"', b'x:networkCode="NZ"')
        self.assert_unknown(parse(body), "foreign_evidence_attribute")

    def test_native_reported_status_dropped(self):
        result = self.assert_ok(parse(scml(picks=pick("pick:A", status="reported")), True))
        self.assertEqual(result["accepted_picks"][0]["evaluation_status"], "missing")

    def test_native_padded_reported_status_retained(self):
        result = self.assert_ok(parse(scml(picks=pick("pick:A", status=" reported ")), True))
        self.assertEqual(result["accepted_picks"][0]["evaluation_status"], "reported")

    def test_station_only_attrs_strip(self):
        result = self.assert_ok(parse(qml(picks=pick(network=" NZ ", station=" S0 ", location=" 00 ", channel=" HHZ "))))
        p = result["accepted_picks"][0]
        self.assertEqual((p["network"], p["station"], p["location"], p["channel"]), ("NZ", "S0", " 00 ", " HHZ "))

    def test_empty_status_missing(self):
        self.assertEqual(parse(qml(picks=pick(status="  ")))["accepted_picks"][0]["evaluation_status"], "missing")

    def test_zero_subset_unresolved_not_known_coverage(self):
        result = self.assert_ok(parse(qml(picks="")))
        self.assertFalse(result["NZ_coverage_known"])
        self.assertTrue(result["incomplete_associated_P_structure"])

    def test_empty_parsed_subset_known(self):
        result = self.assert_ok(parse(qml(arrivals="", picks="")))
        self.assertTrue(result["NZ_coverage_known"])
        self.assertEqual(result["denominators"]["qualifying_P_references"], 0)

    def test_valid_modification_extension_both_versions(self):
        for prefix in ("s13", "s14"):
            result = self.assert_ok(parse(qml(creation=info(f'<{prefix}:modificationTime>{STAMP}</{prefix}:modificationTime>'))))
            self.assertEqual(result["event_creation"]["modificationTime"], STAMP)

    def test_bed_modification_unsupported(self):
        self.assert_unknown(parse(qml(creation=info(f'<modificationTime>{STAMP}</modificationTime>'))), "modificationTime")

    def test_modification_wrong_parent_unsupported(self):
        self.assert_unknown(parse(qml(event_extra=f'<s14:modificationTime>{STAMP}</s14:modificationTime>')), "modificationTime")

    def test_modification_duplicate_namespaces_unknown(self):
        self.assert_unknown(parse(qml(creation=info(f'<s13:modificationTime>{STAMP}</s13:modificationTime><s14:modificationTime>{STAMP}</s14:modificationTime>'))), "duplicate_creation")

    def test_foreign_creation_field_unknown(self):
        self.assert_unknown(parse(qml(creation=info('<x:author>invented-author</x:author>'))), "foreign_evidence")

    def test_creation_lexical_preserved(self):
        result = self.assert_ok(parse(qml(creation=info('<author> invented-author </author><agencyURI>invented:agency</agencyURI>'))))
        self.assertEqual(result["event_creation"]["author"], " invented-author ")
        self.assertEqual(result["event_creation"]["agencyURI"], "invented:agency")

    def test_recovery_unique_missing_object(self):
        result = audit.compare(parse(qml(picks="")), parse())
        self.assertEqual((result["newly_unique_reference_object_count"], result["newly_accepted_NZ_reference_count"], result["content_matched_resolution_candidate_count"]), (1, 1, 1))

    def test_recovery_existing_invalid_time_object(self):
        result = audit.compare(parse(qml(picks=pick(stamp="invalid"))), parse())
        self.assertEqual(result["newly_unique_reference_object_count"], 0)
        self.assertEqual(result["newly_accepted_NZ_reference_count"], 1)

    def test_recovery_existing_station_repair_object(self):
        result = audit.compare(parse(qml(picks=pick(station=""))), parse())
        self.assertEqual(result["newly_unique_reference_object_count"], 0)
        self.assertEqual(result["newly_accepted_NZ_reference_count"], 1)

    def test_recovery_duplicate_object(self):
        result = audit.compare(parse(qml(picks=pick() * 2)), parse())
        self.assertEqual(result["newly_unique_reference_object_count"], 1)

    def test_recovery_right_only_new_arrival_not_left_reference(self):
        result = audit.compare(parse(qml(picks="", arrivals="")), parse())
        self.assertEqual(result["newly_accepted_NZ_reference_count"], 0)
        self.assertFalse(result["arrival_multiset_match"])

    def test_arrival_signature_is_multiset(self):
        result = audit.compare(parse(qml(arrivals=arrival() * 2)), parse())
        self.assertFalse(result["arrival_multiset_match"])

    def test_arrival_signature_order_ignored(self):
        a, b = arrival(), arrival(phase="S")
        self.assertTrue(audit.compare(parse(qml(arrivals=a + b)), parse(qml(arrivals=b + a)))["arrival_multiset_match"])

    def test_revision_conflict_guards_recovery(self):
        left = parse(qml(picks="", creation=info('<version>invented-1</version>')))
        right = parse(qml(creation=info('<version>invented-2</version>')))
        result = audit.compare(left, right)
        self.assertEqual(result["revision_evidence"], "known_conflict")
        self.assertEqual(result["newly_accepted_NZ_reference_count"], 1)
        self.assertEqual(result["content_matched_resolution_candidate_count"], 0)

    def test_revision_valid_equal_timestamp(self):
        creation = info(f'<creationTime>{STAMP}</creationTime>')
        result = audit.compare(parse(qml(picks="", creation=creation)), parse(qml(creation=creation)))
        self.assertEqual(result["revision_evidence"], "matching_recorded_revision")
        self.assertEqual(result["paired_recorded_revision_resolution_count"], 1)
        self.assertFalse(result["atomic_database_revision_verified"])

    def test_revision_invalid_equal_timestamp_not_match(self):
        creation = info('<creationTime>invalid</creationTime>')
        result = audit.compare(parse(qml(picks="", creation=creation)), parse(qml(creation=creation)))
        self.assertEqual(result["revision_evidence"], "missing_or_incomplete")
        self.assertEqual(result["paired_recorded_revision_resolution_count"], 0)

    def test_revision_mixed_valid_invalid_times_not_match(self):
        creation = info(f'<creationTime>{STAMP}</creationTime><s14:modificationTime>invalid</s14:modificationTime>')
        result = audit.compare(parse(qml(picks="", creation=creation)), parse(qml(creation=creation)))
        self.assertEqual(result["revision_evidence"], "missing_or_incomplete")

    def test_accepted_timestamp_canonical_utc(self):
        result = parse(qml(picks=pick(stamp='2020-01-01T01:00:00+01:00')))
        self.assertEqual(result["accepted_picks"][0]["time"], '2020-01-01T00:00:00+00:00')

    def test_native_013(self):
        result = self.assert_ok(parse(scml(version='0.13'), True))
        self.assertEqual(result["version"], 'SCML0.13')

    def test_origin_incomplete_guards_recovery(self):
        body = qml().replace(b'<depth><value>12000</value></depth>', b'')
        result = audit.compare(parse(qml(picks="")), parse(body))
        self.assertFalse(result["origin_fields_complete"])
        self.assertEqual(result["content_matched_resolution_candidate_count"], 0)

    def test_exact_decimal_subnormal_not_zero(self):
        self.assertEqual(audit.canonical_decimal('1e-1000030', True), '1E-1000027')
        self.assertNotEqual(audit.canonical_decimal('1e-1000030'), audit.canonical_decimal('0'))

    def test_decimal_nonfinite_unknown_field(self):
        result = self.assert_ok(parse(qml(origins=origin(depth="NaN"))))
        self.assertIsNone(result["origin"]["depth_m"])
        self.assertEqual(result["denominators"]["accepted_P_picks"], 1)

    def test_decimal_negative_zero(self):
        self.assertEqual(audit.canonical_decimal('-0.000'), '0')

    def test_decimal_large_precision_exact(self):
        value = '123456789012345678901234567890.12345'
        self.assertEqual(audit.canonical_decimal(value, True), '123456789012345678901234567890123.45')

    def test_unknown_comparison_available_false(self):
        result = audit.compare(parse(b'invented-invalid'), parse())
        self.assertFalse(result["available"])

    def test_doctype_forbidden(self):
        self.assert_unknown(parse(b'<!DOCTYPE x [<!ENTITY a "invented">]>' + qml()), "forbidden")

    def test_body_limit(self):
        self.assert_unknown(parse(b' ' * (audit.MAX_BYTES + 1)), "byte_limit")

    def test_depth_limit(self):
        body = qml(event_extra='<invented>' * 65 + '</invented>' * 65)
        self.assert_unknown(parse(body), "structure_limit")

    def test_element_limit(self):
        body = qml(event_extra='<invented/>' * audit.MAX_ELEMENTS)
        self.assert_unknown(parse(body), "structure_limit")

    def test_non_utf8_forbidden(self):
        self.assert_unknown(parse(b'\xff'))
        self.assert_unknown(parse(b'<?xml version="1.0" encoding="iso-8859-1"?>' + qml()), "encoding")

    def test_interface_errors(self):
        with self.assertRaises(TypeError):
            audit.project("invented", EVENT, "qml")
        with self.assertRaises(ValueError):
            audit.project(qml(), EVENT, "invented-format")

    def test_claims_always_false(self):
        for result in (parse(), parse(native=True), parse(b'invented-invalid'), audit.compare(parse(), parse())):
            for claim in audit.CLAIMS:
                self.assertIs(result[claim], False)


# One test per independently expected weight/use combination, without executing XSLT.
for index, (weight, flags, projected, accepted) in enumerate([
    ("0", {}, "0", False), ("1", {}, "1", True), ("", {}, "", True),
    (None, {}, None, True), ("0", {"timeUsed": "true"}, "0", False),
    ("0", {"timeUsed": "1"}, "0", False), ("0", {"timeUsed": "false"}, None, True),
    ("0", {"timeUsed": "0"}, None, True), ("0", {"timeUsed": " true "}, None, True),
    ("0", {"timeUsed": "TRUE"}, None, True), ("0", {"timeUsed": ""}, None, True),
    ("0", {"horizontalSlownessUsed": "true"}, None, True),
    ("0", {"backazimuthUsed": "true"}, None, True),
    (" 0 ", {"timeUsed": "true"}, "0", False), (" 1 ", {"timeUsed": "true"}, "1", True),
    (None, {"timeUsed": "true"}, "1", True), (None, {"timeUsed": "1"}, "1", True),
    (None, {"timeUsed": "false"}, None, True), ("NaN", {"timeUsed": "true"}, "NaN", False),
    ("1e-9999", {}, "1e-9999", False), ("inf", {}, "inf", False),
    ("-1", {}, "-1", False), ("invented-invalid", {}, "invented-invalid", False),
]):
    def check(self, weight=weight, flags=flags, projected=projected, accepted=accepted):
        result = self.assert_ok(parse(scml(arrivals=arrival("pick:A", weight=weight, native=True, flags=flags)), True))
        self.assertEqual(result["arrivals"][0]["time_weight"], projected)
        self.assertEqual(result["arrivals"][0]["native_flags"]["weight"], weight)
        self.assertEqual(result["denominators"]["accepted_P_picks"], int(accepted))
    setattr(Semantics, f'test_native_weight_matrix_{index:02d}', check)

for index, (phase, count) in enumerate([(p, 1) for p in ('P', 'Pg', 'Pn', 'Pb', ' P ')] + [(p, 0) for p in ('p', 'PG', 'S', '', 'Pdiff')]):
    def check(self, phase=phase, count=count):
        result = self.assert_ok(parse(qml(arrivals=arrival(phase=phase))))
        self.assertEqual(result["denominators"]["qualifying_P_references"], count)
    setattr(Semantics, f'test_phase_matrix_{index:02d}', check)

for index, (status, count) in enumerate([('rejected', 0), (' rejected ', 0), ('Rejected', 1), ('REJECTED', 1), ('confirmed', 1), ('', 1)]):
    def check(self, status=status, count=count):
        result = self.assert_ok(parse(qml(picks=pick(status=status))))
        self.assertEqual(result["denominators"]["accepted_P_picks"], count)
    setattr(Semantics, f'test_status_matrix_{index:02d}', check)

for index, (stamp, count) in enumerate([(STAMP, 1), ('2020-01-01T01:00:00+01:00', 1), ('2020-01-01T00:00:00.123456789Z', 1), ('20200101T000000Z', 1), ('2020-01-01T00:00:00', 0), ('2020-01-01', 0), ('invalid', 0), ('9999-12-31T23:59:59-01:00', 0)]):
    def check(self, stamp=stamp, count=count):
        result = self.assert_ok(parse(qml(picks=pick(stamp=stamp))))
        self.assertEqual(result["denominators"]["accepted_P_picks"], count)
    setattr(Semantics, f'test_time_matrix_{index:02d}', check)

if __name__ == '__main__':
    unittest.main(verbosity=2)

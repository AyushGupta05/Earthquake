"""Invented XML only. No actual IDs, metadata, paths, or producer imports."""
from html import escape
from decimal import localcontext, InvalidOperation
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
    return (f'<q:quakeml xmlns:q="{audit.QROOT}" xmlns="{audit.BED}" xmlns:s10="{audit.SCML["0.10"]}" '
            f'xmlns:s11="{audit.SCML["0.11"]}" xmlns:x="urn:invented:foreign"><eventParameters>'
            f'<event publicID="{audit.PREFIX + EVENT}"><preferredOriginID>{escape(preferred)}</preferredOriginID>'
            f'{picks}{origins}{event_extra}{creation}</event>{extra}</eventParameters></q:quakeml>').encode()


def scml(picks=None, arrivals=None, extra="", event_extra="", origins=None, preferred="origin:one", version="0.11", creation=""):
    if picks is None:
        picks = pick("pick:A")
    if arrivals is None:
        arrivals = arrival("pick:A", native=True)
    if origins is None:
        origins = origin("origin:one", arrivals, depth="12")
    ns = audit.SCML.get(version, audit.SCML["0.11"])
    return (f'<seiscomp xmlns="{ns}" xmlns:x="urn:invented:foreign" version="{version}"><EventParameters>'
            f'<event publicID="{EVENT}"><preferredOriginID>{escape(preferred)}</preferredOriginID>'
            f'<originReference>{escape(preferred)}</originReference>{event_extra}{creation}</event>'
            f'{picks}{origins}{extra}</EventParameters></seiscomp>').encode()


def parse(body=None, native=False, profile="0.11"):
    return audit.project(scml() if native and body is None else qml() if body is None else body,
                         EVENT, "scml" if native else "qml", None if native else profile)


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
        self.assert_unknown(parse(scml(origins=origin("origin:one", arrival("pick:A", native=True), "12", extra=sm)), True))

    def test_native_empty_reference_na_collision(self):
        body = scml(picks='', arrivals=arrival('', native=True) + arrival('NA', phase='S', native=True))
        self.assert_unknown(parse(body, True), 'collision')

    def test_native_whitespace_reference_na_collision(self):
        body = scml(picks='', arrivals=arrival('   ', native=True) + arrival('NA', phase='S', native=True))
        self.assert_unknown(parse(body, True), 'collision')

    def test_native_empty_amplitude_reference_na_collision(self):
        sm = '<stationMagnitude><amplitudeID/></stationMagnitude><stationMagnitude><amplitudeID>NA</amplitudeID></stationMagnitude>'
        body = scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm))
        self.assert_unknown(parse(body, True))

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
        self.assert_unknown(parse(scml().replace(b'version="0.11"', b'version="0.10"'), True), "version")

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
        body = qml().replace(b'<pickID>', b'<pickID><invented/>')
        self.assert_unknown(parse(body), "non_scalar")

    def test_non_scalar_native_origin_reference_unknown(self):
        body = scml().replace(b'<originReference>', b'<originReference><invented/>')
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
        for prefix, profile in (("s10", "0.10"), ("s11", "0.11")):
            result = self.assert_ok(parse(qml(creation=info(f'<{prefix}:modificationTime>{STAMP}</{prefix}:modificationTime>')), profile=profile))
            self.assertEqual(result["event_creation"]["modificationTime"], STAMP)

    def test_bed_modification_unsupported(self):
        self.assert_unknown(parse(qml(creation=info(f'<modificationTime>{STAMP}</modificationTime>'))), "modificationTime")

    def test_modification_wrong_parent_unsupported(self):
        self.assert_unknown(parse(qml(event_extra=f'<s11:modificationTime>{STAMP}</s11:modificationTime>')), "modificationTime")

    def test_modification_duplicate_namespaces_unknown(self):
        self.assert_unknown(parse(qml(creation=info(f'<s10:modificationTime>{STAMP}</s10:modificationTime><s11:modificationTime>{STAMP}</s11:modificationTime>'))), "duplicate_creation")

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
        creation = info(f'<creationTime>{STAMP}</creationTime><s11:modificationTime>invalid</s11:modificationTime>')
        result = audit.compare(parse(qml(picks="", creation=creation)), parse(qml(creation=creation)))
        self.assertEqual(result["revision_evidence"], "missing_or_incomplete")

    def test_accepted_timestamp_canonical_utc(self):
        result = parse(qml(picks=pick(stamp='2020-01-01T01:00:00+01:00')))
        self.assertEqual(result["accepted_picks"][0]["time"], '2020-01-01T00:00:00+00:00')

    def test_native_010(self):
        result = self.assert_ok(parse(scml(version='0.10'), True))
        self.assertEqual(result["version"], 'SCML0.10')

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

class LegacyProfiles(unittest.TestCase):
    # Reuse assertion helpers, never producer logic or actual fixtures.
    assert_ok = Semantics.assert_ok
    assert_unknown = Semantics.assert_unknown
    def test_qml_core_without_profile(self):
        self.assert_ok(parse(qml(), profile=None))

    def test_qml_modification_requires_profile(self):
        self.assert_unknown(parse(qml(creation=info(f'<s11:modificationTime>{STAMP}</s11:modificationTime>')), profile=None), 'requires_explicit_profile')

    def test_qml_passedqc_requires_profile(self):
        self.assert_unknown(parse(qml(event_extra='<stationMagnitude publicID="invented-sm"><passedQC>true</passedQC></stationMagnitude>'), profile=None), 'requires_explicit_profile')

    def test_qml_010_bed_passedqc_schema_source_discrepancy_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<stationMagnitude publicID="invented-sm"><passedQC>true</passedQC></stationMagnitude>'), profile='0.10'), 'not_supported_by_profile_010')

    def test_qml_011_bed_passedqc_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<stationMagnitude><passedQC>true</passedQC></stationMagnitude>'), profile='0.11'), 'placement_or_profile')

    def test_qml_011_extension_passedqc(self):
        result = self.assert_ok(parse(qml(event_extra='<stationMagnitude><s11:passedQC> false </s11:passedQC></stationMagnitude>'), profile='0.11'))
        self.assertEqual(result['legacy_extensions'][0]['text'], ' false ')

    def test_qml_010_extension_passedqc_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<stationMagnitude><s10:passedQC>true</s10:passedQC></stationMagnitude>'), profile='0.10'), 'not_supported_by_profile_010')

    def test_qml_extension_profile_conflict(self):
        self.assert_unknown(parse(qml(creation=info(f'<s11:modificationTime>{STAMP}</s11:modificationTime>')), profile='0.10'), 'placement_or_profile')

    def test_qml_mixed_extensions_unknown(self):
        extra = '<stationMagnitude><s11:passedQC>true</s11:passedQC></stationMagnitude>'
        creation = info(f'<s10:modificationTime>{STAMP}</s10:modificationTime>')
        self.assert_unknown(parse(qml(creation=creation, event_extra=extra), profile='0.10'))

    def test_qml_passedqc_wrong_parent_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<s11:passedQC>true</s11:passedQC>'), profile='0.11'))

    def test_qml_passedqc_under_magnitude_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<magnitude><s11:passedQC>true</s11:passedQC></magnitude>'), profile='0.11'))

    def test_qml_station_magnitude_wrong_parent_unknown(self):
        extra = '<stationMagnitude><s11:passedQC>true</s11:passedQC></stationMagnitude>'
        self.assert_unknown(parse(qml(origins=origin(extra=extra)), profile='0.11'))

    def test_qml_duplicate_passedqc_unknown(self):
        extra = '<stationMagnitude><s11:passedQC>true</s11:passedQC><s11:passedQC>false</s11:passedQC></stationMagnitude>'
        self.assert_unknown(parse(qml(event_extra=extra)), 'duplicate_legacy_extension')

    def test_qml_non_scalar_passedqc_unknown(self):
        extra = '<stationMagnitude><s11:passedQC><invented/></s11:passedQC></stationMagnitude>'
        self.assert_unknown(parse(qml(event_extra=extra)), 'non_scalar')

    def test_native_explicit_mismatch_unknown(self):
        self.assert_unknown(audit.project(scml(version='0.10'), EVENT, 'scml', '0.11'), 'profile_root_mismatch')

    def test_native_newer_version_unknown(self):
        self.assert_unknown(parse(scml().replace(b'/0.11', b'/0.13').replace(b'version="0.11"', b'version="0.13"'), True))

    def test_native_passedqc_retained(self):
        for version in ('0.11',):
            sm = '<stationMagnitude publicID="invented-sm"><passedQC> true </passedQC><amplitudeID>amp:A</amplitudeID></stationMagnitude>'
            amp = '<amplitude publicID="amp:A"><pickID>pick:B</pickID></amplitude>'
            body = scml(version=version, origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm), extra=amp)
            result = self.assert_ok(parse(body, True))
            record = result['native_scope']['station_magnitudes'][0]
            self.assertEqual(record['passed_qc'], ' true ')
            self.assertEqual(record['passed_qc_projected_namespace'], audit.BED if version == '0.10' else audit.SCML[version])
            self.assertTrue(record['origin_id_synthesized'])

    def test_native_010_passedqc_schema_source_discrepancy_unknown(self):
        sm = '<stationMagnitude><passedQC>true</passedQC></stationMagnitude>'
        body = scml(version='0.10', origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm))
        self.assert_unknown(parse(body, True), 'not_supported_by_profile_010')

    def test_native_explicit_originid_not_substituted(self):
        sm = '<stationMagnitude publicID="invented-sm"><originID>origin:foreign</originID></stationMagnitude>'
        result = self.assert_ok(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm)), True))
        record = result['native_scope']['station_magnitudes'][0]
        self.assertFalse(record['origin_id_synthesized'])
        self.assertEqual(record['projected_origin_id'], audit.PREFIX + 'origin_foreign')
        self.assertEqual(record['raw_parent_origin_id'], 'origin:one')

    def test_native_reported_raw_preserved(self):
        result = self.assert_ok(parse(scml(picks=pick('pick:A', status='reported')), True))
        self.assertEqual(result['picks'][PID][0]['raw_evaluation_status'], 'reported')
        self.assertEqual(result['picks'][PID][0]['evaluation_status'], 'missing')

    def test_native_dangling_amplitude_unknown(self):
        sm = '<stationMagnitude><amplitudeID>amp:absent</amplitudeID></stationMagnitude>'
        self.assert_unknown(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm)), True), 'referenced_amplitude')

    def test_native_duplicate_amplitude_unknown(self):
        sm = '<stationMagnitude><amplitudeID>amp:A</amplitudeID></stationMagnitude>'
        amp = '<amplitude publicID="amp:A"><pickID>pick:A</pickID></amplitude>'
        self.assert_unknown(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm), extra=amp * 2), True), 'referenced_amplitude')

    def test_native_amplitude_no_value_pick_scope_retained(self):
        sm = '<stationMagnitude><amplitudeID>amp:A</amplitudeID></stationMagnitude>'
        amp = '<amplitude publicID="amp:A"><pickID>pick:B</pickID></amplitude>'
        result = self.assert_ok(parse(scml(picks=pick('pick:A') + pick('pick:B'), origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm), extra=amp), True))
        self.assertIn(audit.PREFIX + 'pick_B', result['picks'])
        record = result['native_scope']['amplitudes'][0]
        self.assertFalse(record['has_amplitude_value_child'])
        self.assertEqual(record['source_mapping_emission_count'], 0)
        self.assertEqual(result['native_scope']['pick_scope_paths'][1]['route'], 'amplitude')

    def test_native_shared_amplitude_emission_multiplicity(self):
        sm = '<stationMagnitude><amplitudeID>amp:A</amplitudeID></stationMagnitude>'
        amp = '<amplitude publicID="amp:A"><amplitude><value>1</value></amplitude><pickID>pick:A</pickID></amplitude>'
        result = self.assert_ok(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm * 2), extra=amp), True))
        self.assertEqual(result['native_scope']['amplitudes'][0]['source_mapping_emission_count'], 2)
        self.assertEqual(result['denominators']['event_scoped_pick_objects'], 1)
        self.assertEqual(len(result['native_scope']['pick_scope_paths']), 3)

    def test_native_duplicate_sm_identity_unknown(self):
        sm = '<stationMagnitude publicID="invented-sm"/>'
        self.assert_unknown(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm * 2)), True), 'duplicate_station')

    def test_native_sm_mapping_collision_unknown(self):
        sm = '<stationMagnitude publicID="sm:A"/><stationMagnitude publicID="sm_A"/>'
        self.assert_unknown(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm)), True), 'collision')

    def test_native_placeholder_pick_identity_unknown(self):
        self.assert_unknown(parse(scml(picks=pick('NA'), arrivals=arrival('NA', native=True)), True), 'placeholder')

    def test_qml_placeholder_pick_identity_unknown(self):
        self.assert_unknown(parse(qml(picks=pick(audit.PREFIX + 'NA'), arrivals=arrival(audit.PREFIX + 'NA'))), 'placeholder')

    def test_native_outside_scope_records_annotated(self):
        result = self.assert_ok(parse(scml(extra=pick('pick:unrelated') + origin('origin:unrelated', '', '12')), True))
        self.assertEqual(result['native_scope']['outside_scope_pick_ids'], ['pick:unrelated'])
        self.assertEqual(result['native_scope']['outside_scope_origin_ids'], ['origin:unrelated'])

    def test_repaired_pick_increments_resolved_label(self):
        result = audit.compare(parse(qml(picks=pick(station=''))), parse())
        self.assertEqual(result['newly_unique_reference_object_count'], 0)
        self.assertEqual(result['newly_resolved_reference_count'], 1)
        self.assertEqual(result['newly_accepted_NZ_reference_count'], 1)

    def test_non_nz_repair_resolved_label(self):
        left = parse(qml(picks=pick(network='AU', station='')))
        right = parse(qml(picks=pick(network='AU')))
        result = audit.compare(left, right)
        self.assertEqual(result['newly_unique_reference_object_count'], 0)
        self.assertEqual(result['newly_resolved_reference_count'], 1)
        self.assertEqual(result['newly_accepted_NZ_reference_count'], 0)

    def test_weight_lexical_vs_finite_canonical_discrepancy(self):
        result = audit.compare(parse(qml(arrivals=arrival(weight='1'))), parse(qml(arrivals=arrival(weight='1.0'))))
        self.assertFalse(result['arrival_multiset_match'])
        self.assertFalse(result['arrival_multiset_lexical_match'])
        self.assertTrue(result['arrival_multiset_finite_canonical_match'])
        self.assertFalse(result['same_record_content'])

    def test_nonfinite_canonical_signature_unknown(self):
        result = audit.compare(parse(qml(arrivals=arrival(weight='NaN'))), parse(qml(arrivals=arrival(weight='NaN'))))
        self.assertIsNone(result['arrival_multiset_finite_canonical_match'])

    def test_profile_mismatch_guards_recovery(self):
        result = audit.compare(parse(qml(picks=''), profile='0.10'), parse(qml(), profile='0.11'))
        self.assertFalse(result['source_profile_consistency'])
        self.assertEqual(result['content_matched_resolution_candidate_count'], 0)

    def test_core_unknown_foreign_extension_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<x:invented>value</x:invented>'), profile=None), 'foreign')

    def test_qml_cross_type_public_id_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<amplitude publicID="' + PID + '"/>')), 'cross_type')

    def test_native_cross_type_public_id_unknown(self):
        sm = '<stationMagnitude publicID="pick:A"/>'
        self.assert_unknown(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=sm)), True), 'cross_type')

    def test_qml_duplicate_nonpreferred_origin_unknown(self):
        other = origin(audit.PREFIX + 'origin_other', '', '12000')
        self.assert_unknown(parse(qml(origins=origin() + other * 2)), 'duplicate_scoped_identity:origin')

    def test_qml_duplicate_amplitude_unknown(self):
        extra = '<amplitude publicID="invented-amp"/>' * 2
        self.assert_unknown(parse(qml(event_extra=extra)), 'duplicate_scoped_identity:amplitude')

    def test_qml_dangling_station_amplitude_unknown(self):
        extra = '<stationMagnitude><amplitudeID>invented-amp</amplitudeID></stationMagnitude>'
        self.assert_unknown(parse(qml(event_extra=extra)), 'referenced_amplitude')

    def test_qml_unique_station_amplitude_allowed(self):
        extra = '<stationMagnitude><amplitudeID>invented-amp</amplitudeID></stationMagnitude><amplitude publicID="invented-amp"/>'
        self.assert_ok(parse(qml(event_extra=extra)))

    def test_qml_duplicate_picks_remain_unresolved(self):
        result = self.assert_ok(parse(qml(picks=pick() * 2)))
        self.assertEqual(result['denominators']['accepted_P_picks'], 0)
        self.assertEqual(result['denominators']['unique_resolved_qualifying_P_reference_ids'], 0)

    def test_native_creation_uri_candidate_and_raw_separate(self):
        creation = info('<agencyURI>agency:A</agencyURI><authorURI></authorURI><author> </author>')
        result = self.assert_ok(parse(scml(creation=creation), True))
        self.assertEqual(result['raw_event_creation']['agencyURI'], 'agency:A')
        self.assertEqual(result['event_creation']['agencyURI'], audit.PREFIX + 'agency_A')
        self.assertEqual(result['raw_event_creation']['authorURI'], '')
        self.assertEqual(result['event_creation']['authorURI'], audit.PREFIX + 'NA')
        self.assertEqual(result['raw_event_creation']['author'], ' ')
        self.assertEqual(result['event_creation']['author'], '')

    def test_native_creation_uri_mapping_matches_qml_candidate(self):
        native = parse(scml(creation=info('<agencyURI>agency:A</agencyURI>')), True)
        converted = parse(qml(creation=info('<agencyURI>' + audit.PREFIX + 'agency_A</agencyURI>')))
        self.assertTrue(audit.compare(native, converted)['same_record_content'])

    def test_native_requested_raw_id_substitution_mapping_collision(self):
        body = scml().replace(EVENT.encode(), b'invented_event')
        result = audit.project(body, 'invented:event', 'scml')
        self.assert_unknown(result, 'raw_native_event_identity_mismatch')

    def test_native_trimmed_arrival_cannot_alias_amplitude_selected_pick(self):
        sm = '<stationMagnitude><amplitudeID>invented-amp</amplitudeID></stationMagnitude>'
        amp = '<amplitude publicID="invented-amp"><pickID>smi:invented/P</pickID></amplitude>'
        body = scml(picks=pick('smi:invented/P'), origins=origin('origin:one', arrival('smi:invented/P ', native=True), '12', extra=sm), extra=amp)
        result = self.assert_ok(parse(body, True))
        self.assertFalse(result['arrivals'][0]['reference_identity_known'])
        self.assertTrue(result['native_reference_mapping_ambiguity'])
        self.assertEqual(result['denominators']['unique_resolved_qualifying_P_reference_ids'], 0)
        self.assertEqual(result['denominators']['accepted_P_picks'], 0)
        self.assertTrue(result['incomplete_associated_P_structure'])
        converted = parse(qml(picks=pick('smi:invented/P'), arrivals=arrival('smi:invented/P')))
        comparison = audit.compare(result, converted)
        self.assertFalse(comparison['reference_mapping_consistency'])
        self.assertFalse(comparison['same_record_content'])
        self.assertEqual(comparison['content_matched_resolution_candidate_count'], 0)

    def test_native_raw_target_cannot_resolve_different_trimmed_object(self):
        sm = '<stationMagnitude><amplitudeID>invented-amp</amplitudeID></stationMagnitude>'
        amp = '<amplitude publicID="invented-amp"><pickID>smi:invented/P</pickID></amplitude>'
        body = scml(picks=pick('smi:invented/P ') + pick('smi:invented/P'), origins=origin('origin:one', arrival('smi:invented/P ', native=True), '12', extra=sm), extra=amp)
        result = self.assert_ok(parse(body, True))
        self.assertEqual(result['denominators']['accepted_P_picks'], 0)
        self.assertTrue(result['native_reference_mapping_ambiguity'])

    def test_decimal_depth_constructor_exponent_overflow_retains_pick_subset(self):
        result = self.assert_ok(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '1e999999999999999999')), True))
        self.assertIsNone(result['origin']['depth_m'])
        self.assertEqual(result['denominators']['accepted_P_picks'], 1)

    def test_frozen_station_precedes_invalid_time(self):
        result = self.assert_ok(parse(qml(picks=pick(station='', stamp='invalid'))))
        self.assertEqual(result['qualifying_reference_decisions'][0]['disposition'], 'missing_station_identity')

    def test_already_accepted_non_nz_to_nz_is_not_recovery(self):
        result = audit.compare(parse(qml(picks=pick(network='XX'))), parse())
        self.assertEqual(result['newly_resolved_reference_count'], 0)
        self.assertEqual(result['newly_accepted_NZ_reference_count'], 0)
        self.assertEqual(result['content_matched_resolution_candidate_count'], 0)

    def test_duplicate_raw_space_id_does_not_hide_mapping_disagreement(self):
        body = scml(picks=pick('smi:invented/P ') * 2, arrivals=arrival('smi:invented/P ', native=True))
        left = self.assert_ok(parse(body, True))
        self.assertTrue(left['native_reference_mapping_ambiguity'])
        self.assertEqual(left['denominators']['accepted_P_picks'], 0)
        right = parse(qml(picks=pick('smi:invented/P'), arrivals=arrival('smi:invented/P')))
        result = audit.compare(left, right)
        self.assertFalse(result['reference_mapping_consistency'])
        self.assertEqual(result['content_matched_resolution_candidate_count'], 0)

    def test_native_ordinary_duplicate_id_preserves_lower_bound_repair(self):
        left = self.assert_ok(parse(scml(picks=pick('pick:A') * 2), True))
        self.assertFalse(left['native_reference_mapping_ambiguity'])
        self.assertEqual(left['denominators']['accepted_P_picks'], 0)
        comparison = audit.compare(left, parse())
        self.assertTrue(comparison['same_record_content'])
        self.assertEqual(comparison['newly_unique_reference_object_count'], 1)
        self.assertEqual(comparison['content_matched_resolution_candidate_count'], 1)

    def test_native_absent_preserved_uri_with_trim_identity_change_guarded(self):
        left = self.assert_ok(parse(scml(picks='', arrivals=arrival('smi:invented/P ', native=True)), True))
        self.assertTrue(left['native_reference_mapping_ambiguity'])
        right = parse(qml(picks=pick('smi:invented/P'), arrivals=arrival('smi:invented/P')))
        self.assertEqual(audit.compare(left, right)['content_matched_resolution_candidate_count'], 0)

    def test_secondary_qml_origin_mixed_arrival_unknown(self):
        other = origin(audit.PREFIX + 'origin_other', arrival(weight=None, extra='<weight>0</weight>'))
        self.assert_unknown(parse(qml(origins=origin() + other)), 'mixed_arrival_weight')

    def test_secondary_qml_origin_duplicate_phase_unknown(self):
        other = origin(audit.PREFIX + 'origin_other', arrival(extra='<phase>S</phase>'))
        self.assert_unknown(parse(qml(origins=origin() + other)), 'singleton:phase')

    def test_secondary_qml_origin_non_scalar_weight_unknown(self):
        other = origin(audit.PREFIX + 'origin_other', arrival(weight=None, extra='<timeWeight><invented/></timeWeight>'))
        self.assert_unknown(parse(qml(origins=origin() + other)), 'non_scalar_field:timeWeight')

    def test_secondary_qml_origin_valid_arrivals_do_not_change_preferred_count(self):
        other = origin(audit.PREFIX + 'origin_other', arrival(phase='S'))
        result = self.assert_ok(parse(qml(origins=origin() + other)))
        self.assertEqual(result['denominators']['all_preferred_arrivals'], 1)
        self.assertEqual(result['denominators']['accepted_P_picks'], 1)

    def test_native_outside_pick_candidate_collision_unknown(self):
        self.assert_unknown(parse(scml(extra=pick('pick_A')), True), 'outside_scope_native_identity')

    def test_native_outside_origin_candidate_collision_unknown(self):
        self.assert_unknown(parse(scml(extra=origin('origin_one', '', '12')), True), 'outside_scope_native_identity')

    def test_native_outside_wrong_type_raw_identity_unknown(self):
        self.assert_unknown(parse(scml(extra='<amplitude publicID="pick:A"/>'), True), 'outside_scope_native_identity')

    def test_native_outside_wrong_type_magnitude_candidate_identity_unknown(self):
        self.assert_unknown(parse(scml(extra='<magnitude publicID="pick_A"/>'), True), 'outside_scope_native_identity')

    def test_native_scoped_magnitude_wrong_type_identity_unknown(self):
        extra = '<magnitude publicID="pick:A"/>'
        self.assert_unknown(parse(scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=extra)), True), 'cross_type_scoped_identity')

    def test_qml_scoped_magnitude_wrong_type_identity_unknown(self):
        self.assert_unknown(parse(qml(event_extra='<magnitude publicID="' + PID + '"/>')), 'cross_type_scoped_identity')

    def test_qml_outside_wrong_type_identity_unknown(self):
        self.assert_unknown(parse(qml(extra='<amplitude publicID="' + PID + '"/>')), 'outside_scope_qml_identity')

    def test_qml_nested_duplicate_pick_is_not_scoped_duplicate_exemption(self):
        self.assert_unknown(parse(qml(origins=origin(extra=pick()))), 'duplicate_scoped_identity:pick')

    def test_native_nested_duplicate_pick_is_not_scoped_duplicate_exemption(self):
        body = scml(origins=origin('origin:one', arrival('pick:A', native=True), '12', extra=pick('pick:A')))
        self.assert_unknown(parse(body, True), 'duplicate_scoped_identity:pick')

    def test_native_root_sibling_candidate_id_collision_unknown(self):
        body = scml().replace(b'</seiscomp>', pick('pick_A').encode() + b'</seiscomp>')
        self.assert_unknown(parse(body, True), 'outside_scope_native_identity')

    def test_qml_root_sibling_raw_id_collision_unknown(self):
        body = qml().replace(b'</q:quakeml>', pick().encode() + b'</q:quakeml>')
        self.assert_unknown(parse(body), 'outside_scope_qml_identity')

    def test_qml_root_sibling_distinct_id_does_not_expand_scope(self):
        body = qml().replace(b'</q:quakeml>', pick('smi:invented/outside').encode() + b'</q:quakeml>')
        result = self.assert_ok(parse(body))
        self.assertEqual(result['denominators']['event_scoped_pick_objects'], 1)

    def test_native_comment_text_boundary_unknown(self):
        body = scml(arrivals=arrival('pick:A', weight='0', native=True, extra='<timeUsed> <!--invented-->true</timeUsed>'))
        self.assert_unknown(parse(body, True), 'comment_or_processing_instruction')

    def test_native_pi_text_boundary_unknown(self):
        body = scml(arrivals=arrival('pick:A', weight='0', native=True, extra='<timeUsed> <?invented value?>true</timeUsed>'))
        self.assert_unknown(parse(body, True), 'comment_or_processing_instruction')

    def test_native_reference_comment_boundary_unknown(self):
        body = scml().replace(b'<pickID>pick:A</pickID>', b'<pickID> <!--invented-->pick:A</pickID>')
        self.assert_unknown(parse(body, True), 'comment_or_processing_instruction')

    def test_qml_scalar_comment_boundary_unknown(self):
        body = qml().replace(b'<timeWeight>1</timeWeight>', b'<timeWeight> <!--invented-->1</timeWeight>')
        self.assert_unknown(parse(body), 'comment_or_processing_instruction')

    def test_native_comment_under_root_conservative_unknown(self):
        self.assert_unknown(parse(scml().replace(b'<EventParameters>', b'<!--invented--><EventParameters>'), True), 'comment_or_processing_instruction')

    def test_xml_declaration_and_outside_comment_allowed(self):
        self.assert_ok(parse(b'<?xml version="1.0" encoding="UTF-8"?><!--invented outside-->' + qml()))

    def test_decimal_constructor_nonfinite_with_disabled_trap_is_null(self):
        with localcontext() as context:
            context.traps[InvalidOperation] = False
            self.assertIsNone(audit.canonical_decimal('1e999999999999999999', True))

    def test_decimal_disabled_trap_cannot_promote_guarded_recovery(self):
        origins = origin('origin:one', arrival('pick:A', native=True), '1e999999999999999999')
        with localcontext() as context:
            context.traps[InvalidOperation] = False
            left = self.assert_ok(parse(scml(picks='', origins=origins), True))
            right = self.assert_ok(parse(scml(origins=origins), True))
        comparison = audit.compare(left, right)
        self.assertFalse(comparison['origin_fields_complete'])
        self.assertEqual(comparison['newly_accepted_NZ_reference_count'], 1)
        self.assertEqual(comparison['content_matched_resolution_candidate_count'], 0)

    def test_unsupported_profile_interface_error(self):
        with self.assertRaises(ValueError):
            audit.project(qml(), EVENT, 'qml', '0.13')

for index, (version, flag, raw, state) in enumerate((version, flag, raw, state)
        for version in ('0.10', '0.11')
        for flag in ('timeUsed', 'horizontalSlownessUsed', 'backazimuthUsed')
        for raw, state in [('true', 'true'), ('1', 'true'), ('false', 'false'), ('0', 'false'), (' true ', 'unrecognized'), ('invented', 'unrecognized'), ('', 'unrecognized')]):
    def check(self, version=version, flag=flag, raw=raw, state=state):
        body = scml(version=version, arrivals=arrival('pick:A', weight=None, native=True, flags={flag: raw}))
        result = self.assert_ok(parse(body, True))
        a = result['arrivals'][0]
        self.assertEqual(a['native_use_flag_states'][flag], state)
        self.assertEqual(a['native_flags'][flag], raw)
        target = {'timeUsed': 'timeWeight', 'horizontalSlownessUsed': 'horizontalSlownessWeight', 'backazimuthUsed': 'backazimuthWeight'}[flag]
        self.assertEqual(a['projected_weights'][target], '1' if state == 'true' else None)
    setattr(LegacyProfiles, f'test_all_use_flags_{index:02d}', check)

for index, (text, supported) in enumerate([('true', True), ('false', True), ('1', True), ('0', True), (' true ', True), ('\tfalse\n', True), ('TRUE', False), ('', False), ('true false', False), ('\u00a0true\u00a0', False)]):
    def check(self, text=text, supported=supported):
        extension = '<stationMagnitude><s11:passedQC>' + escape(text) + '</s11:passedQC></stationMagnitude>'
        result = parse(qml(event_extra=extension), profile='0.11')
        if supported:
            self.assert_ok(result)
            self.assertEqual(result['legacy_extensions'][0]['text'], text)
        else:
            self.assert_unknown(result, 'invalid_passedQC')
    setattr(LegacyProfiles, f'test_passedqc_boolean_{index:02d}', check)

for index, (native, field) in enumerate([(True, f) for f in ('timeWeight', 'horizontalSlownessWeight', 'backazimuthWeight')] + [(False, f) for f in ('weight', 'timeUsed', 'horizontalSlownessUsed', 'backazimuthUsed')]):
    def check(self, native=native, field=field):
        a = arrival('pick:A' if native else PID, native=native, weight=None, extra=f'<{field}>0</{field}>')
        self.assert_unknown(parse(scml(arrivals=a) if native else qml(arrivals=a), native), 'mixed_arrival_weight')
    setattr(LegacyProfiles, f'test_mixed_arrival_vocabulary_{index:02d}', check)

if __name__ == '__main__':
    unittest.main(verbosity=2)

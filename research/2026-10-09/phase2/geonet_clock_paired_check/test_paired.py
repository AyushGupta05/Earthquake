"""Invented XML, roster, transport and cancellation fixtures; no real data or requests."""
import copy
import io
import http.client
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
import xml.etree.ElementTree as ET
import comparison as c
import dependencies as d
import paired as run
import projection as p
import selection as s

EID = "invented-event"
T = "2020-01-01T00:00:00+00:00"


def node(parent, ns, name, text=None, **attrs):
    result = ET.SubElement(parent, "{" + ns + "}" + name, attrs)
    result.text = text
    return result


def fixture(kind="qml", version="0.14", include_b=True):
    ns = p.B if kind == "qml" else p.SCML[version]
    root = ET.Element("{" + (p.Q if kind == "qml" else ns) + "}" +
                      ("quakeml" if kind == "qml" else "seiscomp"),
                      {} if kind == "qml" else {"version": version})
    params = node(root, ns, "eventParameters" if kind == "qml" else "EventParameters")
    mapped = p.mapped_id if kind == "qml" else lambda value: value
    event = node(params, ns, "event", publicID=mapped(EID))
    node(event, ns, "preferredOriginID", mapped("origin:one"))
    if kind != "qml":
        node(event, ns, "originReference", "origin:one")
    scope = event if kind == "qml" else params
    origin = node(scope, ns, "origin", publicID=mapped("origin:one"))
    for key, value in (("time", T), ("latitude", "-40"), ("longitude", "175"),
                       ("depth", "12000" if kind == "qml" else "12")):
        node(node(origin, ns, key), ns, "value", value)
    for index, identifier in enumerate(("pick:A", "pick:B", "pick:C")):
        arrival = node(origin, ns, "arrival")
        node(arrival, ns, "phase", "P")
        node(arrival, ns, "pickID", mapped(identifier))
        node(arrival, ns, "timeWeight" if kind == "qml" else "weight", "1")
        if index == 1 and not include_b:
            continue
        pick = node(scope, ns, "pick", publicID=mapped(identifier))
        node(node(pick, ns, "time"), ns, "value", T if index == 0 else (
            "2019-12-31T23:59:59+00:00" if index == 1 else "2020-01-01T00:00:00.800+00:00"))
        node(pick, ns, "waveformID", networkCode="NZ", stationCode="S" + str(index), channelCode="HHZ")
    return root, params, event, origin, ns


def body(parts):
    return ET.tostring(parts[0], encoding="utf-8")


def parsed(kind="qml", **kwargs):
    return p.parse(body(fixture(kind, **kwargs)), EID, kind)


def with_creation(parts, scope, value):
    parent = parts[2] if scope == "event" else parts[3]
    node(node(parent, parts[4], "creationInfo"), parts[4], "modificationTime", value)
    return parts


def invented_roster():
    rows, outcomes = [], {}
    for index in range(495):
        identifier = str(10000 + index)
        row = {"event_id": identifier, "source": "reused_tail" if index < 149 else "new_lower_M",
               "candidate_calendar_partition": s.PARTITION, "mw": 6.5 if index < 10 else 7.5}
        rows.append(row)
        reasons = {"missing_or_ambiguous_pick_reference": 1} if index in (0, 1, 2, 10) else {}
        outcomes[identifier] = {"base": {"status": "ok", "reasons": reasons}}
    return rows, outcomes


class ProjectionTests(unittest.TestCase):
    def test_scoped_amplitude_mapping_collision_is_unknown(self):
        parts = fixture("scml")
        ns = parts[4]
        for index, identifier in enumerate(("amp:A", "amp A")):
            magnitude = node(parts[3], ns, "stationMagnitude", publicID="magnitude:" + str(index))
            node(magnitude, ns, "amplitudeID", identifier)
            amplitude = node(parts[1], ns, "amplitude", publicID=identifier)
            node(amplitude, ns, "pickID", "pick:A" if index == 0 else "pick:C")
        result = p.parse(body(parts), EID, "scml")
        self.assertEqual(result["status"], "unknown_representation")
        self.assertEqual(result["reason"], "ID_mapping_collision")

    def test_canonical_geometry_inexact_underflow_is_unknown(self):
        self.assertIsNone(p.canonical_number("1e-1000100"))
        self.assertIsNone(p.canonical_number("1e-1000100", 1000))
        self.assertEqual(p.canonical_number("1e-1000001"), "1E-1000001")
        self.assertEqual(p.canonical_number("12.000", 1000), "1.2E+4")

    def test_preserved_uri_pick_reference_uses_projected_text_predicate(self):
        for prefix in ("smi:", "quakeml:"):
            records = []
            for kind in ("qml", "scml"):
                parts = fixture(kind)
                ns = parts[4]
                scope = parts[2] if kind == "qml" else parts[1]
                pick = p.children(scope, "pick", ns)[0]
                pick.set("publicID", prefix + "invented/pick ")
                p.children(p.children(parts[3], "arrival", ns)[0], "pickID", ns)[0].text = prefix + "invented/pick "
                records.append(p.parse(body(parts), EID, kind))
            for record in records:
                self.assertEqual(record["status"], "ok")
                self.assertEqual(record["reasons"]["missing_or_ambiguous_pick_reference"], 1)
                self.assertEqual(record["denominators"]["accepted_P_picks"], 2)
                self.assertIn(prefix + "invented/pick ", record["picks"])

    def test_preserved_uri_preferred_reference_whitespace_unresolved(self):
        for kind in ("qml", "scml"):
            parts = fixture(kind)
            ns = parts[4]
            identifier = "smi:invented/origin "
            parts[3].set("publicID", identifier)
            p.children(parts[2], "preferredOriginID", ns)[0].text = identifier
            if kind == "scml":
                p.children(parts[2], "originReference", ns)[0].text = identifier
            self.assertEqual(p.parse(body(parts), EID, kind)["status"], "unknown_representation")

    def test_qml_complete(self):
        result = parsed()
        self.assertEqual(result["denominators"]["accepted_NZ_P_picks"], 3)
        self.assertEqual(result["nz"]["strict_horizon_station_counts"], {"1": 1, "3": 3, "5": 3})

    def test_supported_versions_match(self):
        for version in p.SCML:
            with self.subTest(version=version):
                qml, scml = parsed(), parsed("scml", version=version)
                self.assertTrue(c.compare(qml, scml)["same_record_content"])
                self.assertEqual(qml["nz"], scml["nz"])

    def test_reference_denominators_remain_partial(self):
        result = parsed(include_b=False)
        self.assertEqual(result["denominators"]["qualifying_P_references"], 3)
        self.assertEqual(result["denominators"]["unique_resolved_qualifying_P_reference_ids"], 2)
        self.assertTrue(result["incomplete_associated_P_structure"])

    def test_prefix_clock_counterexample(self):
        result = c.event_result(parsed(include_b=False), parsed(include_b=False), parsed("scml"))
        old = result["shadow_clocks"]["original_qml"]["own_clock"]
        new = result["shadow_clocks"]["native_scml"]
        self.assertEqual(old["strict_horizon_station_counts"]["1"], 2)
        self.assertEqual(new["own_clock"]["strict_horizon_station_counts"]["1"], 1)
        self.assertEqual(new["at_preserved_original_T0"]["strict_horizon_station_counts"]["1"], 3)
        self.assertFalse(result["automatic_reclock_applied"])

    def test_unknown_not_zero(self):
        result = p.parse(b"bad XML", EID, "scml")
        self.assertIsNone(result["denominators"])
        self.assertIsNone(result["nz"])

    def test_zero_subset_missing_references_unknown_coverage(self):
        parts = fixture()
        for pick in p.children(parts[2], "pick", parts[4]):
            parts[2].remove(pick)
        result = p.parse(body(parts), EID, "qml")
        self.assertFalse(result["NZ_coverage_known"])
        self.assertIsNone(result["nz"]["t0_us"])
        self.assertIsNone(result["nz"]["strict_horizon_station_counts"]["1"])

    def test_empty_resolved_catalogue_zero_known(self):
        parts = fixture()
        for arrival in p.children(parts[3], "arrival", parts[4]):
            parts[3].remove(arrival)
        result = p.parse(body(parts), EID, "qml")
        self.assertTrue(result["NZ_coverage_known"])
        self.assertEqual(result["denominators"]["accepted_P_picks"], 0)

    def test_duplicate_pick_not_choose_first(self):
        parts = fixture()
        parts[2].append(copy.deepcopy(p.children(parts[2], "pick", parts[4])[0]))
        result = p.parse(body(parts), EID, "qml")
        self.assertEqual(result["reasons"]["missing_or_ambiguous_pick_reference"], 1)
        self.assertEqual(result["denominators"]["accepted_P_picks"], 2)

    def test_duplicate_arrival_deduplicated_after_acceptance(self):
        parts = fixture()
        parts[3].append(copy.deepcopy(p.children(parts[3], "arrival", parts[4])[0]))
        result = p.parse(body(parts), EID, "qml")
        self.assertEqual(result["denominators"]["qualifying_P_references"], 4)
        self.assertEqual(result["reasons"]["duplicate_accepted_arrival_reference"], 1)

    def test_missing_reference_count_before_nonpositive_weight(self):
        parts = fixture(include_b=False)
        arrivals = p.children(parts[3], "arrival", parts[4])
        p.children(arrivals[1], "timeWeight", parts[4])[0].text = "0"
        result = p.parse(body(parts), EID, "qml")
        self.assertEqual(result["reasons"]["missing_or_ambiguous_pick_reference"], 1)
        self.assertNotIn("nonpositive_or_invalid_time_weight", result["reasons"])

    def test_invalid_weights(self):
        for weight in ("0", "-1", "NaN", "Inf", "1e9999", "1e-9999", "wrong"):
            with self.subTest(weight=weight):
                parts = fixture()
                arrival = p.children(parts[3], "arrival", parts[4])[0]
                p.children(arrival, "timeWeight", parts[4])[0].text = weight
                result = p.parse(body(parts), EID, "qml")
                self.assertEqual(result["denominators"]["accepted_P_picks"], 2)

    def test_missing_and_empty_weight_accepted(self):
        for remove in (True, False):
            parts = fixture()
            arrival = p.children(parts[3], "arrival", parts[4])[0]
            weight = p.children(arrival, "timeWeight", parts[4])[0]
            if remove:
                arrival.remove(weight)
            else:
                weight.text = ""
            result = p.parse(body(parts), EID, "qml")
            self.assertEqual(result["denominators"]["accepted_P_picks"], 3)
            self.assertEqual(result["reasons"]["accepted_missing_time_weight"], 1)

    def test_native_weight_truth_table(self):
        cases = [(None, {}, None), ("0.7", {}, "0.7"),
                 (None, {"timeUsed": "true"}, "1"), (None, {"timeUsed": "1"}, "1"),
                 ("0.7", {"timeUsed": "false"}, None),
                 ("0.7", {"horizontalSlownessUsed": "true"}, None),
                 ("0.7", {"timeUsed": "true", "backazimuthUsed": "false"}, "0.7"),
                 (None, {"timeUsed": "false"}, None)]
        for weight, flags, expected in cases:
            with self.subTest(weight=weight, flags=flags):
                arrival = ET.Element("arrival")
                if weight is not None:
                    node(arrival, p.SCML["0.14"], "weight", weight)
                for key, value in flags.items():
                    node(arrival, p.SCML["0.14"], key, value)
                self.assertEqual(p.projected_weight(arrival, p.SCML["0.14"])[0], expected)

    def test_time_used_false_is_projected_missing_weight(self):
        parts = fixture("scml")
        node(p.children(parts[3], "arrival", parts[4])[0], parts[4], "timeUsed", "false")
        result = p.parse(body(parts), EID, "scml")
        self.assertEqual(result["denominators"]["accepted_P_picks"], 3)
        self.assertEqual(result["reasons"]["accepted_missing_time_weight"], 1)

    def test_native_xpath_flag_whitespace_is_literal(self):
        for value in (" true ", " 1 "):
            parts = fixture("scml")
            arrival = p.children(parts[3], "arrival", parts[4])[0]
            p.children(arrival, "weight", parts[4])[0].text = "0"
            node(arrival, parts[4], "timeUsed", value)
            result = p.parse(body(parts), EID, "scml")
            self.assertEqual(result["status"], "ok")
            self.assertIsNone(result["arrivals"][0]["time_weight"])
            self.assertEqual(result["arrivals"][0]["native_flags"]["timeUsed"], value)
            self.assertEqual(result["denominators"]["accepted_P_picks"], 3)

    def test_invalid_native_boolean_unknown(self):
        parts = fixture("scml")
        node(p.children(parts[3], "arrival", parts[4])[0], parts[4], "timeUsed", "yes")
        self.assertEqual(p.parse(body(parts), EID, "scml")["status"], "unknown_representation")

    def test_supported_phase_set(self):
        for phase in ("P", "Pg", "Pn", "Pb", "S", "p", ""):
            parts = fixture()
            p.children(p.children(parts[3], "arrival", parts[4])[0], "phase", parts[4])[0].text = phase
            self.assertEqual(p.parse(body(parts), EID, "qml")["denominators"]["accepted_P_picks"],
                             3 if phase in p.PHASES else 2)

    def test_rejected_and_station_time_failures(self):
        for issue, reason in (("rejected", "rejected_pick"), ("station", "missing_station_identity"),
                              ("time", "invalid_or_naive_pick_time")):
            parts = fixture()
            pick = p.children(parts[2], "pick", parts[4])[0]
            if issue == "rejected":
                node(pick, parts[4], "evaluationStatus", "rejected")
            elif issue == "station":
                p.children(pick, "waveformID", parts[4])[0].set("stationCode", " ")
            else:
                p.children(p.children(pick, "time", parts[4])[0], "value", parts[4])[0].text = "2020-01-01"
            result = p.parse(body(parts), EID, "qml")
            self.assertEqual(result["reasons"][reason], 1)

    def test_namespace_and_version_guard(self):
        for change in ("version", "root_namespace", "foreign_pick"):
            parts = fixture("scml")
            if change == "version":
                parts[0].set("version", "0.13")
            elif change == "root_namespace":
                parts[0].tag = "{wrong}seiscomp"
            else:
                p.children(parts[1], "pick", parts[4])[0].tag = "{wrong}pick"
            self.assertEqual(p.parse(body(parts), EID, "scml")["status"], "unknown_representation")

    def test_foreign_evidence_fields_unknown(self):
        for kind in ("qml", "scml"):
            for field in ("weight", "evaluationStatus", "creationInfo", "creationTime"):
                if kind == "qml" and field == "weight":
                    continue
                parts = fixture(kind)
                if field == "weight":
                    target = p.children(p.children(parts[3], "arrival", parts[4])[0], "weight", parts[4])[0]
                    target.text = "0"
                elif field == "evaluationStatus":
                    target = node(p.children(parts[2] if kind == "qml" else parts[1], "pick", parts[4])[0],
                                  parts[4], field, "rejected")
                elif field == "creationInfo":
                    target = node(parts[3], parts[4], "creationInfo")
                else:
                    target = node(node(parts[3], parts[4], "creationInfo"), parts[4], field, T)
                target.tag = "{foreign}" + field
                self.assertEqual(p.parse(body(parts), EID, kind)["status"], "unknown_representation")

    def test_event_origin_normalization_collision_unknown(self):
        parts = fixture("scml")
        alias = p.mapped_id(EID)
        p.children(parts[2], "preferredOriginID", parts[4])[0].text = alias
        p.children(parts[2], "originReference", parts[4])[0].text = alias
        parts[3].set("publicID", alias)
        self.assertEqual(p.parse(body(parts), EID, "scml")["status"], "unknown_representation")

    def test_event_identity_exact(self):
        for kind in ("qml", "scml"):
            parts = fixture(kind)
            parts[2].set("publicID", "smi:foreign/" + EID)
            self.assertEqual(p.parse(body(parts), EID, kind)["status"], "unknown_representation")

    def test_duplicate_event_or_origin_unknown(self):
        for kind in ("qml", "scml"):
            for target in ("event", "origin"):
                parts = fixture(kind)
                parent = parts[1] if target == "event" or kind == "scml" else parts[2]
                parent.append(copy.deepcopy(parts[2] if target == "event" else parts[3]))
                self.assertEqual(p.parse(body(parts), EID, kind)["status"], "unknown_representation")

    def test_duplicate_singleton_unknown(self):
        for field in ("preferredOriginID", "phase", "pickID", "timeWeight", "waveformID"):
            parts = fixture()
            parent = parts[2] if field == "preferredOriginID" else (
                p.children(parts[2], "pick", parts[4])[0] if field == "waveformID" else
                p.children(parts[3], "arrival", parts[4])[0])
            parent.append(copy.deepcopy(p.children(parent, field, parts[4])[0]))
            self.assertEqual(p.parse(body(parts), EID, "qml")["status"], "unknown_representation")

    def test_native_preferred_origin_requires_reference(self):
        parts = fixture("scml")
        parts[2].remove(p.children(parts[2], "originReference", parts[4])[0])
        self.assertEqual(p.parse(body(parts), EID, "scml")["status"], "unknown_representation")

    def test_mapping_collision_unknown(self):
        parts = fixture("scml")
        node(parts[3], parts[4], "arrival")
        arrival = p.children(parts[3], "arrival", parts[4])[-1]
        node(arrival, parts[4], "phase", "P")
        node(arrival, parts[4], "pickID", "pick A")
        self.assertEqual(p.parse(body(parts), EID, "scml")["status"], "unknown_representation")

    def test_unreferenced_native_pick_excluded(self):
        parts = fixture("scml")
        pick = copy.deepcopy(p.children(parts[1], "pick", parts[4])[0])
        pick.set("publicID", "unrelated")
        parts[1].append(pick)
        self.assertNotIn(p.mapped_id("unrelated"), p.parse(body(parts), EID, "scml")["picks"])

    def test_second_event_origin_and_amplitude_pick_scope(self):
        parts = fixture("scml")
        ns = parts[4]
        node(parts[2], ns, "originReference", "origin:other")
        other = node(parts[1], ns, "origin", publicID="origin:other")
        magnitude = node(other, ns, "stationMagnitude", publicID="station:mag")
        node(magnitude, ns, "amplitudeID", "amplitude:other")
        amplitude = node(parts[1], ns, "amplitude", publicID="amplitude:other")
        node(amplitude, ns, "pickID", "pick:other")
        pick = copy.deepcopy(p.children(parts[1], "pick", ns)[0])
        pick.set("publicID", "pick:other")
        parts[1].append(pick)
        result = p.parse(body(parts), EID, "scml")
        self.assertIn(p.mapped_id("pick:other"), result["picks"])
        self.assertEqual(result["denominators"]["accepted_P_picks"], 3)

    def test_xml_safety(self):
        for invalid in (b"<!DOCTYPE x><x/>", b"<!ENTITY x 'a'><x/>", b"\x00", b"\xff",
                        b"x" * (4 * p.MIB + 1)):
            self.assertEqual(p.parse(invalid, EID, "qml")["status"], "unknown_representation")

    def test_id_mapping(self):
        self.assertEqual(p.mapped_id("a b:c"), p.PREFIX + "a_b_c")
        self.assertEqual(p.mapped_id("smi:x:y"), "smi:x:y")
        self.assertEqual(p.mapped_id("quakeml:x:y"), "quakeml:x:y")
        with self.assertRaises(p.RepresentationError):
            p.mapped_id(" ")

    def test_utc_offset_fraction_and_strict_boundary(self):
        self.assertEqual(p.stamp_us(T), p.stamp_us("2020-01-01T01:00:00+01:00"))
        self.assertEqual(p.stamp_us("2020-01-01T00:00:00.1Z") - p.stamp_us(T), 100000)
        values = [{"network": "NZ", "station": str(i), "time": value}
                  for i, value in enumerate((T, "2020-01-01T00:00:01Z", "2020-01-01T00:00:02.999999Z"))]
        self.assertEqual(p.clock(values)["strict_horizon_station_counts"], {"1": 1, "3": 3, "5": 3})

    def test_station_repeats_earliest(self):
        values = [{"network": "NZ", "station": "A", "time": T},
                  {"network": "NZ", "station": "A", "time": "2020-01-01T00:00:05Z"}]
        self.assertEqual(p.clock(values)["station_count"], 1)


class ComparisonTests(unittest.TestCase):
    def test_uri_revision_conflicts_are_retained(self):
        for field in ("authorURI", "agencyURI"):
            left = with_creation(fixture(include_b=False), "origin", T)
            right = with_creation(fixture("scml"), "origin", T)
            node(p.children(left[3], "creationInfo", left[4])[0], left[4], field, "smi:invented/one")
            node(p.children(right[3], "creationInfo", right[4])[0], right[4], field, "smi:invented/two")
            result = c.compare(p.parse(body(left), EID, "qml"), p.parse(body(right), EID, "scml"))
            self.assertEqual(result["revision_evidence"], "conflict")
            self.assertEqual(result["paired_recorded_revision_resolution_count"], 0)

    def test_empty_malformed_or_naive_revision_times_not_evidence(self):
        for value in ("", "nonsense", "2020-01-01", "2020-01-01T00:00:00"):
            left = with_creation(fixture(include_b=False), "origin", value)
            right = with_creation(fixture("scml"), "origin", value)
            result = c.compare(p.parse(body(left), EID, "qml"), p.parse(body(right), EID, "scml"))
            self.assertEqual(result["revision_evidence"], "missing_or_incomplete")
            self.assertEqual(result["paired_recorded_revision_resolution_count"], 0)

    def test_source_backed_scml_modification_extension(self):
        for native in p.SCML.values():
            left = fixture(include_b=False)
            node(node(left[3], left[4], "creationInfo"), native, "modificationTime", T)
            right = with_creation(fixture("scml"), "origin", T)
            qml = p.parse(body(left), EID, "qml")
            self.assertEqual(qml["status"], "ok")
            self.assertEqual(c.compare(qml, p.parse(body(right), EID, "scml"))["paired_recorded_revision_resolution_count"], 1)

    def test_ambiguous_modification_extensions_unknown(self):
        left = fixture()
        info = node(left[3], left[4], "creationInfo")
        for native in p.SCML.values():
            node(info, native, "modificationTime", T)
        self.assertEqual(p.parse(body(left), EID, "qml")["status"], "unknown_representation")

    def test_foreign_modification_outside_exact_context_unknown(self):
        left = fixture()
        node(left[3], p.SCML["0.14"], "modificationTime", T)
        self.assertEqual(p.parse(body(left), EID, "qml")["status"], "unknown_representation")
    def test_unsupported_original_keeps_frozen_clock(self):
        unknown = p.parse(b"invalid invented original", EID, "qml")
        fresh = parsed()
        result = c.event_result(unknown, fresh, parsed("scml"), p.stamp_us(T))
        self.assertIsNone(result["shadow_clocks"]["original_qml"]["at_preserved_original_T0"])
        self.assertEqual(result["shadow_clocks"]["fresh_qml"]["at_preserved_original_T0"]["anchor_us"], p.stamp_us(T))
        self.assertEqual(result["shadow_clocks"]["native_scml"]["at_preserved_original_T0"]["strict_horizon_station_counts"]["1"], 3)
        self.assertIsNone(result["catalogue_drift"]["same_record_content"])

    def test_lexical_revision_whitespace_conflict(self):
        left = with_creation(fixture(include_b=False), "origin", T)
        right = with_creation(fixture("scml"), "origin", T)
        node(p.children(left[3], "creationInfo", left[4])[0], left[4], "author", "Analyst")
        node(p.children(right[3], "creationInfo", right[4])[0], right[4], "author", " Analyst ")
        result = c.compare(p.parse(body(left), EID, "qml"), p.parse(body(right), EID, "scml"))
        self.assertEqual(result["revision_evidence"], "conflict")
        self.assertEqual(result["paired_recorded_revision_resolution_count"], 0)
    def test_content_recovery_without_revision_not_bug(self):
        result = c.compare(parsed(include_b=False), parsed("scml"))
        self.assertEqual(result["content_matched_resolution_candidate_count"], 1)
        self.assertEqual(result["paired_recorded_revision_resolution_count"], 0)
        self.assertFalse(result["converter_bug_proved"])

    def test_recorded_revision_match(self):
        left = with_creation(fixture(include_b=False), "origin", T)
        right = with_creation(fixture("scml"), "origin", T)
        result = c.compare(p.parse(body(left), EID, "qml"), p.parse(body(right), EID, "scml"))
        self.assertEqual(result["paired_recorded_revision_resolution_count"], 1)
        self.assertFalse(result["atomic_database_revision_verified"])

    def test_revision_conflict_prevents_candidate(self):
        left = with_creation(fixture(include_b=False), "origin", T)
        right = with_creation(fixture("scml"), "origin", "2020-01-02T00:00:00Z")
        result = c.compare(p.parse(body(left), EID, "qml"), p.parse(body(right), EID, "scml"))
        self.assertEqual(result["revision_evidence"], "conflict")
        self.assertEqual(result["content_matched_resolution_candidate_count"], 0)

    def test_origin_or_association_drift(self):
        for field in ("depth", "phase"):
            parts = fixture("scml")
            target = p.children(parts[3], field, parts[4])[0] if field == "depth" else (
                p.children(p.children(parts[3], "arrival", parts[4])[0], field, parts[4])[0])
            if field == "depth":
                target[0].text = "13"
            else:
                target.text = "Pg"
            result = c.compare(parsed(include_b=False), p.parse(body(parts), EID, "scml"))
            self.assertFalse(result["same_record_content"])
            self.assertEqual(result["content_matched_resolution_candidate_count"], 0)

    def test_missing_origin_fields_content_unknown(self):
        parts = fixture("scml")
        parts[3].remove(p.children(parts[3], "depth", parts[4])[0])
        self.assertIsNone(c.compare(parsed(), p.parse(body(parts), EID, "scml"))["same_record_content"])

    def test_inexact_geometry_cannot_support_revision_resolution(self):
        left = with_creation(fixture(include_b=False), "origin", T)
        right = with_creation(fixture("scml"), "origin", T)
        p.children(p.children(left[3], "latitude", left[4])[0], "value", left[4])[0].text = "0"
        p.children(p.children(right[3], "latitude", right[4])[0], "value", right[4])[0].text = "1e-1000100"
        left_record, right_record = p.parse(body(left), EID, "qml"), p.parse(body(right), EID, "scml")
        self.assertEqual(right_record["status"], "ok")
        self.assertIsNone(right_record["origin"]["latitude"])
        result = c.compare(left_record, right_record)
        self.assertIsNone(result["same_record_content"])
        self.assertEqual(result["newly_resolved_reference_count"], 1)
        self.assertEqual(result["content_matched_resolution_candidate_count"], 0)
        self.assertEqual(result["paired_recorded_revision_resolution_count"], 0)

    def test_new_object_rejected_is_not_resolved_accepted(self):
        parts = fixture("scml")
        node(p.children(parts[1], "pick", parts[4])[1], parts[4], "evaluationStatus", "rejected")
        result = c.compare(parsed(include_b=False), p.parse(body(parts), EID, "scml"))
        self.assertEqual(result["newly_unique_reference_object_count"], 1)
        self.assertEqual(result["newly_resolved_reference_count"], 0)

    def test_existing_unique_pick_station_or_time_recovery_is_newly_accepted(self):
        for field in ("station", "time"):
            left = fixture()
            pick = p.children(left[2], "pick", left[4])[1]
            if field == "station":
                p.children(pick, "waveformID", left[4])[0].set("stationCode", "")
            else:
                p.children(p.children(pick, "time", left[4])[0], "value", left[4])[0].text = "2020-01-01T00:00:00"
            result = c.compare(p.parse(body(left), EID, "qml"), parsed("scml"))
            self.assertEqual(result["newly_unique_reference_object_count"], 0)
            self.assertEqual(result["newly_resolved_reference_count"], 1)
            self.assertEqual(result["newly_accepted_NZ_reference_count"], 1)
            self.assertEqual(result["content_matched_resolution_candidate_count"], 1)

    def test_newly_accepted_reference_requires_left_qualifying_arrival(self):
        left = fixture(include_b=False)
        p.children(p.children(left[3], "arrival", left[4])[1], "phase", left[4])[0].text = "S"
        result = c.compare(p.parse(body(left), EID, "qml"), parsed("scml"))
        self.assertEqual(result["newly_resolved_reference_count"], 0)
        self.assertEqual(result["content_matched_resolution_candidate_count"], 0)

    def test_full_denominators_on_unknown(self):
        unknown = run.unavailable(EID, "transport_failed", "invented")
        values = [c.event_result(parsed(), unknown, unknown) for _ in range(6)]
        aggregate = c.aggregate(values)
        self.assertEqual(aggregate["representation_denominator"], 18)
        self.assertEqual(aggregate["representation_status_counts"]["fresh_qml:transport_failed"], 6)
        self.assertEqual(aggregate["comparisons"]["representation_difference"]["unknown"], 6)


class SelectionTests(unittest.TestCase):
    def test_all_four_and_two_controls(self):
        rows, outcomes = invented_roster()
        chosen = s.choose(rows, outcomes)
        self.assertEqual(len(chosen), 6)
        self.assertEqual(sum(row["role"] == "incomplete_probe" for row in chosen), 4)
        self.assertEqual(len(s.requests(chosen)), 12)

    def test_input_reordering_does_not_change_selection(self):
        rows, outcomes = invented_roster()
        self.assertEqual(s.choose(rows, outcomes), s.choose(list(reversed(rows)), outcomes))

    def test_control_exact_rank(self):
        rows, outcomes = invented_roster()
        chosen = s.choose(rows, outcomes)
        for band, indices in (("[6,7)", range(3, 10)), (">=7", range(11, 149))):
            expected = min(indices, key=lambda i: (s.digest("geonet-scml-paired-control-v1|" + s.PARTITION +
                                                           "|" + band + "|" + rows[i]["event_id"]), rows[i]["event_id"]))
            self.assertIn(rows[expected]["event_id"], {row["event_id"] for row in chosen})

    def test_no_replacement_if_prerequisite_changes(self):
        rows, outcomes = invented_roster()
        outcomes[rows[0]["event_id"]]["base"]["status"] = "failed"
        with self.assertRaises(ValueError):
            s.choose(rows, outcomes)

    def test_probe_denominator_change_rejected(self):
        rows, outcomes = invented_roster()
        outcomes[rows[1]["event_id"]]["base"]["reasons"] = {}
        with self.assertRaises(ValueError):
            s.choose(rows, outcomes)

    def test_complete_control_unavailable_rejected(self):
        rows, outcomes = invented_roster()
        for index in range(3, 10):
            rows[index]["candidate_calendar_partition"] = "train2003_2014"
        with self.assertRaises(ValueError):
            s.choose(rows, outcomes)

    def test_duplicate_frame_identity_rejected(self):
        rows, outcomes = invented_roster()
        rows[-1]["event_id"] = rows[0]["event_id"]
        with self.assertRaises(ValueError):
            s.choose(rows, outcomes)

    def test_queries_no_optional_flags(self):
        rows, outcomes = invented_roster()
        requests = s.requests(s.choose(rows, outcomes))
        for index, request in enumerate(requests):
            self.assertEqual(request["method"], "GET")
            self.assertEqual(request["kind"], "qml" if index % 2 == 0 else "scml")
            self.assertEqual(request["url"].split("?")[1], "eventid=" + request["event_id"])


class MockFetcher:
    failure = None
    def __init__(self, root, **kwargs):
        self.root, self.kwargs, self.log, self.bytes = root, kwargs, [], 0
    def check(self):
        if len(self.log) >= self.kwargs["max_requests"]:
            raise RuntimeError("attempt cap")
    def fetch(self, url, name, cap):
        self.check()
        self.log.append({"url": url, "file": name, "status": "ok", "bytes": 0})
        if self.failure is not None:
            raise self.failure
        kind = "scml" if name.startswith("scml") else "qml"
        value = body(fixture(kind))
        self.root.joinpath(name).write_bytes(value)
        self.bytes += len(value)
        self.log[-1].update(bytes=len(value), sha256=d.sha(value), http_status=200)
        return value


class ControlTests(unittest.TestCase):
    def plan(self, root):
        original = body(fixture(include_b=False))
        root.joinpath("original.xml").write_bytes(original)
        events = [{"event_id": EID, "role": "incomplete_probe", "Mw_band": "[6,7)",
                   "preserved_original_T0_us": p.stamp_us(T),
                   "original_qml": {"path": str(root / "original.xml"), "pin": run.pin(root / "original.xml"),
                                    "projection_sha256": p.digest(p.parse(original, EID, "qml"))}}]
        # Six unique fixture slots share only invented XML content; event_id is changed
        # within each body when constructing the final worker test below.
        return {"events": events, "requests": s.requests(events), "processing_files": {},
                "reviewed_dependencies": {}, "runtime": {}, "input_receipt_sha256": "invented",
                "specification": run.specification()}

    def test_source_specification_and_runtime(self):
        self.assertEqual(run.specification()["caps"]["requests"], 12)
        self.assertEqual(d.runtime()["installations"], 0)
        self.assertEqual(set(d.pins()), {"downloader", "transport", "dependency_receipt", "dependency_lock", "wheel_receipt"})

    def test_bounded_read_and_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x"
            path.write_bytes(b"xx")
            with self.assertRaises(ValueError):
                d.read(path, 1)
            link = Path(tmp) / "link"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                d.read(link, 10)

    def test_initial_checksum_change_fails_before_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan(root)
            root.joinpath("original.xml").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                run.initial_results(plan)

    def test_invalid_authorization_fails_before_plan_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("plan").write_text("{}")
            root.joinpath("receipt").write_text("{}")
            with patch.object(run, "local", side_effect=lambda value: Path(value)), patch.object(run, "make_plan") as make:
                with self.assertRaises(ValueError):
                    run.validate(root / "plan", root / "receipt")
                make.assert_not_called()

    def test_authorization_requires_all_boolean_guards(self):
        receipt = {"version": "geonet-paired-parent-receipt-v1", "acquisition_authorized": True,
                   "code_only_review_clean": True, "private_selection_independently_replayed": True,
                   "freeze_pushed": True, "git_freeze_commit": "a" * 40,
                   "private_selection_replay_sha256": "b" * 64}
        for key in ("acquisition_authorized", "code_only_review_clean", "private_selection_independently_replayed", "freeze_pushed"):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                root.joinpath("plan").write_text("{}")
                value = dict(receipt, **{key: False})
                root.joinpath("receipt").write_text(json.dumps(value))
                with patch.object(run, "local", side_effect=lambda item: Path(item)), patch.object(run, "make_plan") as make:
                    with self.assertRaises(ValueError):
                        run.validate(root / "plan", root / "receipt")
                    make.assert_not_called()

    def test_worker_six_denominators_all_twelve_failures(self):
        class Failing(MockFetcher):
            failure = TimeoutError("invented timeout")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan(root)
            plan["events"] = [dict(plan["events"][0], event_id=str(index)) for index in range(6)]
            snapshots = [dict(c.event_result(parsed(), run.unavailable(str(index), "not_attempted", "invented"),
                                                   run.unavailable(str(index), "not_attempted", "invented")),
                              event_id=str(index), role="invented", Mw_band="[6,7)") for index in range(6)]
            plan["requests"] = s.requests(plan["events"])
            with patch.object(run, "initial_results", return_value=snapshots):
                code = run.worker(plan, root, "a", "b", time.monotonic() + 360, Failing)
            self.assertEqual(code, 0)
            summary = run.load(root / "summary.json")
            self.assertEqual(summary["source_event_denominator"], 6)
            self.assertEqual(summary["representation_status_counts"]["fresh_qml:transport_failed"], 6)
            self.assertEqual(len(run.load(root / "requests.json")), 12)

    def test_worker_truncated_http_continues_fixed_attempts(self):
        class Truncated(MockFetcher):
            failure = http.client.IncompleteRead(b"invented partial", 99)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan(root)
            plan["requests"] = [{**request, "file": "invented_" + str(index) + ".xml"}
                                for index, request in enumerate(s.requests(plan["events"]) * 6)]
            self.assertEqual(run.worker(plan, root, "a", "b", time.monotonic() + 360, Truncated), 0)
            self.assertEqual(len(run.load(root / "requests.json")), 12)
            result = run.load(root / "event_outcomes.json")[0]
            self.assertEqual(result["representations"]["native_scml"]["status"], "transport_failed")
            self.assertIsNone(result["representations"]["native_scml"]["denominators"])

    def test_worker_resource_limit_stops_without_replacement(self):
        lib = d.module("downloader")
        transport = d.module("transport")
        class Limited(MockFetcher):
            def fetch(self, url, name, cap):
                self.log.append({"file": name, "url": url, "bytes": 0})
                raise lib.LimitReached("invented bound")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = self.plan(root)
            with patch.object(run.deps, "module", side_effect=lambda name: lib if name == "downloader" else transport):
                code = run.worker(plan, root, "a", "b", time.monotonic() + 360, Limited)
            self.assertEqual(code, 2)
            self.assertFalse(run.load(root / "summary.json")["completed"])
            self.assertEqual(len(run.load(root / "requests.json")), 1)

    def test_worker_memory_error_stops(self):
        class Limited(MockFetcher):
            failure = MemoryError("invented")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = run.worker(self.plan(root), root, "a", "b", time.monotonic() + 360, Limited)
            self.assertEqual(code, 2)
            self.assertFalse(run.load(root / "manifest.json")["completed"])

    def test_worker_cancellation_before_durable_attempt_not_attempted(self):
        lib = d.module("downloader")
        class NoAttempt(MockFetcher):
            def fetch(self, url, name, cap):
                raise lib.LimitReached("invented cancellation during start-spacing sleep")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = run.worker(self.plan(root), root, "a", "b", time.monotonic() + 360, NoAttempt)
            self.assertEqual(code, 2)
            self.assertEqual(run.load(root / "requests.json"), [])
            result = run.load(root / "event_outcomes.json")[0]
            self.assertEqual(result["representations"]["fresh_qml"]["status"], "not_attempted")
            self.assertEqual(result["shadow_clocks"]["fresh_qml"]["status"], "not_attempted")
            self.assertFalse(run.load(root / "summary.json")["completed"])

    def test_worker_local_persistence_failure_stops(self):
        class StorageFailure(MockFetcher):
            failure = PermissionError("invented sidecar permission failure")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = run.worker(self.plan(root), root, "a", "b", time.monotonic() + 360, StorageFailure)
            self.assertEqual(code, 2)
            self.assertFalse(run.load(root / "manifest.json")["completed"])
            self.assertEqual(len(run.load(root / "requests.json")), 1)

    def test_worker_unexpected_transport_contract_stops(self):
        class ContractFailure(MockFetcher):
            failure = ValueError("unexpected pinned HTTPResponse socket adapter")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = run.worker(self.plan(root), root, "a", "b", time.monotonic() + 360, ContractFailure)
            self.assertEqual(code, 2)
            self.assertFalse(run.load(root / "manifest.json")["completed"])

    def test_frozen_plan_recompute_before_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = {"input_receipt_path": "invented"}
            encoded = json.dumps(plan).encode()
            root.joinpath("plan").write_bytes(encoded)
            receipt = {"version": "geonet-paired-parent-receipt-v1", "acquisition_authorized": True,
                       "code_only_review_clean": True, "private_selection_independently_replayed": True,
                       "freeze_pushed": True, "git_freeze_commit": "a" * 40,
                       "private_selection_replay_sha256": "b" * 64, "plan_sha256": d.sha(encoded)}
            root.joinpath("receipt").write_text(json.dumps(receipt))
            with patch.object(run, "local", side_effect=lambda item: Path(item)), patch.object(run, "make_plan", return_value={"changed": True}) as make:
                with self.assertRaises(ValueError):
                    run.validate(root / "plan", root / "receipt")
                make.assert_called_once_with("invented")

    def test_stop_child_only_owned_group_and_escalates(self):
        process = unittest.mock.Mock(pid=123)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("invented", 1), 2]
        with patch.object(run.os, "killpg") as kill:
            run.stop_child(process, time.monotonic() + 10, True)
        self.assertEqual(kill.call_args_list, [unittest.mock.call(123, signal.SIGTERM), unittest.mock.call(123, signal.SIGKILL)])

    def test_soft_stop_is_failure(self):
        with self.assertRaises(run.Deadline):
            run.soft_stop(signal.SIGALRM, None)

    def test_parent_validation_failure_never_spawns(self):
        with patch.object(run, "validate", side_effect=ValueError("invented invalid receipt")), \
                patch.object(run.subprocess, "Popen") as spawn:
            with self.assertRaises(ValueError):
                run.collect("invented", "invented", "invented")
            spawn.assert_not_called()

    def test_parent_stops_child_before_recovery(self):
        process = unittest.mock.Mock(pid=123)
        process.poll.return_value = 2
        process.wait.side_effect = subprocess.TimeoutExpired("invented", .1)
        ordering = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            plan = {"events": [], "requests": [], "event_denominator": 6}
            with patch.object(run, "validate", return_value=(plan, "a", "b")), \
                    patch.object(run, "local", side_effect=lambda item: Path(item)), \
                    patch.object(run, "initial_results", return_value=[]), \
                    patch.object(run.subprocess, "Popen", return_value=process), \
                    patch.object(run.os, "write", return_value=1), \
                    patch.object(run, "stop_child", side_effect=lambda *args: ordering.append("stop")), \
                    patch.object(run, "load", side_effect=lambda *args: ordering.append("read") or (
                        [] if args[0].name == "event_outcomes.json" else {"completed": False})):
                with self.assertRaises(subprocess.TimeoutExpired):
                    run.collect("invented", "invented", root)
            self.assertEqual(ordering, ["stop", "read", "read"])
            self.assertTrue(root.joinpath("outer_interruption.json").exists())

    def test_parent_launch_cancellation_retains_child_before_recovery(self):
        for number in (signal.SIGTERM, signal.SIGALRM, signal.SIGINT):
            process = unittest.mock.Mock(pid=123)
            process.poll.return_value = 2
            handlers, ordering = {}, []

            def install(signum, handler):
                handlers[signum] = handler

            def spawn(*args, **kwargs):
                handlers[number](number, None)
                ordering.append("created")
                return process

            def stop(handle, *args):
                self.assertIs(handle, process)
                ordering.append("stop")

            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "run"
                plan = {"events": [], "requests": [], "event_denominator": 6}
                with patch.object(run, "validate", return_value=(plan, "a", "b")), \
                        patch.object(run, "local", side_effect=lambda item: Path(item)), \
                        patch.object(run, "initial_results", return_value=[]), \
                        patch.object(run.signal, "signal", side_effect=install), \
                        patch.object(run.signal, "setitimer"), \
                        patch.object(run.subprocess, "Popen", side_effect=spawn), \
                        patch.object(run, "stop_child", side_effect=stop), \
                        patch.object(run, "load", side_effect=lambda *args: ordering.append("read") or (
                            [] if args[0].name == "event_outcomes.json" else {"completed": False})):
                    with self.assertRaises(run.Deadline):
                        run.collect("invented", "invented", root)
                self.assertEqual(ordering, ["created", "stop", "read", "read"])
                process.wait.assert_not_called()

    def test_parent_stalled_launch_arms_hard_deadline_and_closes_gate(self):
        handlers, timers, child_gates = {}, [], []
        current = [run.PROCESS_STARTED + 350]

        def install(signum, handler):
            handlers[signum] = handler

        def stalled_spawn(*args, **kwargs):
            child_gates.append(run.os.dup(kwargs["pass_fds"][0]))
            handlers[signal.SIGALRM](signal.SIGALRM, None)
            current[0] += 10
            handlers[signal.SIGALRM](signal.SIGALRM, None)
            self.fail("hard launch deadline did not exit")

        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "run"
                plan = {"events": [], "requests": [], "event_denominator": 6}
                with patch.object(run, "validate", return_value=(plan, "a", "b")), \
                        patch.object(run, "local", side_effect=lambda item: Path(item)), \
                        patch.object(run, "initial_results", return_value=[]), \
                        patch.object(run.signal, "signal", side_effect=install), \
                        patch.object(run.signal, "setitimer", side_effect=lambda kind, seconds: timers.append(seconds)), \
                        patch.object(run.time, "monotonic", side_effect=lambda: current[0]), \
                        patch.object(run.os, "_exit", side_effect=SystemExit(2)) as exit_process, \
                        patch.object(run.subprocess, "Popen", side_effect=stalled_spawn), \
                        patch.object(run, "stop_child") as stop:
                    with self.assertRaises(SystemExit):
                        run.collect("invented", "invented", root)
                self.assertIn(10, timers)
                exit_process.assert_called_once_with(2)
                stop.assert_called_once_with(None, run.PROCESS_STARTED + 360, True)
                self.assertEqual(run.os.read(child_gates[0], 1), b"")
        finally:
            for descriptor in child_gates:
                run.os.close(descriptor)

    def test_worker_gate_eof_and_elapsed_deadline_fail_closed(self):
        for case in ("EOF", "expired", "expired_after_token", "released"):
            read, write = run.os.pipe()
            now = time.monotonic()
            if case != "EOF":
                run.os.write(write, b"1")
            run.os.close(write)
            deadline = now + (5 if case == "expired" else 360)
            ticks = [now, now + 351] if case == "expired_after_token" else [now, now]
            with patch.object(run, "hard_watchdog") as watchdog, \
                    patch.object(run.time, "monotonic", side_effect=ticks):
                if case == "released":
                    run.receive_launch_gate(read, deadline)
                else:
                    with self.assertRaises(run.Deadline):
                        run.receive_launch_gate(read, deadline)
                watchdog.assert_called_once_with(deadline, None)
            with self.assertRaises(OSError):
                run.os.read(read, 1)

    def test_worker_cli_gate_precedes_private_input_validation(self):
        argv = ["paired.py", "_worker", "--plan", "invented", "--receipt", "invented",
                "--output", "invented", "--deadline", "123", "--gate-fd", "3"]
        with patch.object(run.sys, "argv", argv), \
                patch.object(run, "receive_launch_gate", side_effect=run.Deadline("invented gate EOF")) as gate, \
                patch.object(run, "validate") as validate:
            with self.assertRaises(run.Deadline):
                run.main()
            gate.assert_called_once_with(3, 123)
            validate.assert_not_called()

    def test_actual_worker_gate_eof_and_elapsed_never_validate_inputs(self):
        for case in ("EOF", "elapsed"):
            read, write = run.os.pipe()
            process = None
            try:
                if case == "elapsed":
                    run.os.write(write, b"1")
                process = subprocess.Popen(
                    [run.sys.executable, "-B", str(run.BASE / "paired.py"), "_worker",
                     "--plan", "invented-input-that-must-not-be-read", "--receipt", "invented",
                     "--output", "invented", "--deadline", str(time.monotonic() + (5 if case == "elapsed" else 360)),
                     "--gate-fd", str(read)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(read,), start_new_session=True)
                run.os.close(read)
                read = None
                run.os.close(write)
                write = None
                stdout, stderr = process.communicate(timeout=5)
                self.assertNotEqual(process.returncode, 0)
                self.assertEqual(stdout, b"")
                self.assertIn(b"worker launch gate closed" if case == "EOF" else b"worker launch deadline elapsed", stderr)
                self.assertNotIn(b"private nonsymlink", stderr)
            finally:
                for descriptor in (read, write):
                    if descriptor is not None:
                        run.os.close(descriptor)
                if process is not None and process.poll() is None:
                    run.os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)

    def test_forced_stop_reconciles_attempted_slot_and_shadow(self):
        unknown = run.unavailable(EID, "not_attempted", "invented")
        result = dict(c.event_result(parsed(), unknown, unknown), event_id=EID)
        result["representations"]["fresh_qml"] = run.unavailable(EID, "attempting", "invented")
        plan = {"events": [{"event_id": EID}], "requests": s.requests([{"event_id": EID}])}
        attempts = [{"file": plan["requests"][0]["file"], "url": plan["requests"][0]["url"], "status": "interrupted"}]
        recovered = run.reconcile_results(plan, [result], attempts)[0]
        self.assertEqual(recovered["representations"]["fresh_qml"]["status"], "interrupted")
        self.assertEqual(recovered["shadow_clocks"]["fresh_qml"]["status"], "interrupted")
        self.assertIsNone(recovered["shadow_clocks"]["fresh_qml"]["own_clock"])
        self.assertEqual(recovered["representations"]["native_scml"]["status"], "not_attempted")

    def test_forced_stop_before_attempt_remains_not_attempted(self):
        unknown = run.unavailable(EID, "not_attempted", "invented")
        result = dict(c.event_result(parsed(), unknown, unknown), event_id=EID)
        result["representations"]["fresh_qml"] = run.unavailable(EID, "attempting", "invented")
        plan = {"events": [{"event_id": EID}], "requests": s.requests([{"event_id": EID}])}
        recovered = run.reconcile_results(plan, [result], [])[0]
        self.assertEqual(recovered["representations"]["fresh_qml"]["status"], "not_attempted")
        self.assertEqual(recovered["shadow_clocks"]["fresh_qml"]["status"], "not_attempted")

    def test_recovery_does_not_promote_or_replace_unknown_body(self):
        unknown = run.unavailable(EID, "not_attempted", "invented")
        result = dict(c.event_result(parsed(), unknown, unknown), event_id=EID)
        plan = {"events": [{"event_id": EID}], "requests": s.requests([{"event_id": EID}])}
        attempts = [{"file": plan["requests"][0]["file"], "url": plan["requests"][0]["url"], "status": "ok"}]
        recovered = run.reconcile_results(plan, [result], attempts)[0]
        self.assertEqual(recovered["representations"]["fresh_qml"]["status"], "interrupted")
        self.assertIsNone(recovered["representations"]["fresh_qml"]["denominators"])

    def test_recovery_rejects_changed_or_duplicate_queries(self):
        plan = {"events": [{"event_id": EID}], "requests": s.requests([{"event_id": EID}])}
        attempt = {"file": plan["requests"][0]["file"], "url": plan["requests"][0]["url"]}
        for attempts in ([dict(attempt, url="https://invented.invalid/changed")], [attempt, attempt]):
            with self.assertRaises(ValueError):
                run.reconcile_results(plan, [], attempts)

    def test_existing_output_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("keep").write_text("untouched")
            with patch.object(run, "validate", return_value=({}, "a", "b")), \
                    patch.object(run, "local", side_effect=lambda item: Path(item)), \
                    patch.object(run.subprocess, "Popen") as spawn:
                with self.assertRaises(FileExistsError):
                    run.collect("invented", "invented", root)
                spawn.assert_not_called()
            self.assertEqual(root.joinpath("keep").read_text(), "untouched")

    def test_original_body_exact_member_and_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("raw").mkdir()
            value = body(fixture())
            root.joinpath("raw/invented.xml").write_bytes(value)
            expected = {"bytes": len(value), "sha256": d.sha(value)}
            root.joinpath("manifest.json").write_text(json.dumps({"files": {"raw/invented.xml": expected}}))
            entry = {"file": "invented.xml", "status": "ok", "http_status": 200, **expected}
            root.joinpath("requests.json").write_text(json.dumps([entry]))
            with patch.object(run, "CENSUS", root):
                self.assertEqual(run.original_body("invented")[2], value)
                entry["bytes"] += 1
                root.joinpath("requests.json").write_text(json.dumps([entry]))
                with self.assertRaises(ValueError):
                    run.original_body("invented")


class FetcherTests(unittest.TestCase):
    def test_durable_chunk_success_and_partial_timeout(self):
        for timeout in (False, True):
            lib = d.module("downloader")
            transport = d.module("transport")
            class Response:
                status, headers, fp = 200, {}, None
                def __init__(self):
                    self.calls = 0
                def isclosed(self):
                    return True
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def read1(self, cap):
                    self.calls += 1
                    if self.calls == 1:
                        return b"invented partial"
                    if timeout:
                        raise TimeoutError("invented whole-request timeout")
                    return b""
            opener = unittest.mock.Mock()
            opener.open.return_value = Response()
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / "raw"
                root.mkdir()
                with patch.object(transport.urllib.request, "build_opener", return_value=opener):
                    fetch = transport.factory(lib, time.monotonic())(root, max_requests=12, max_bytes=48 * run.MIB)
                    if timeout:
                        with self.assertRaises(TimeoutError):
                            fetch.fetch("https://invented.invalid", "x", 4 * run.MIB)
                    else:
                        self.assertEqual(fetch.fetch("https://invented.invalid", "x", 4 * run.MIB), b"invented partial")
                self.assertEqual(root.joinpath("x").read_bytes(), b"invented partial")
                self.assertFalse(root.joinpath("x.received").exists())
                ledger = json.loads(root.parent.joinpath("requests.json").read_text())
                self.assertEqual(ledger[0]["bytes"], len(b"invented partial"))
                self.assertEqual(ledger[0]["sha256"], d.sha(b"invented partial"))
                self.assertEqual(fetch.bytes, len(b"invented partial"))

    def test_unchanged_fetcher_start_spacing_and_cap(self):
        lib = d.module("downloader")
        now = [0.0]
        starts = []
        class Response:
            status, headers = 200, {"Content-Length": "1"}
            def __init__(self):
                self.values = [b"x", b""]
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read1(self, cap):
                return self.values.pop(0)
        class Opener:
            def open(self, *args, **kwargs):
                starts.append(now[0])
                return Response()
        with tempfile.TemporaryDirectory() as tmp:
            fetch = lib.Fetcher(Path(tmp), clock=lambda: now[0], sleep=lambda seconds: now.__setitem__(0, now[0] + seconds),
                                opener=Opener(), max_requests=2)
            fetch.fetch("https://invented.invalid/a", "a", 10)
            fetch.fetch("https://invented.invalid/b", "b", 10)
            self.assertEqual(starts, [0, 1])
            with self.assertRaises(lib.LimitReached):
                fetch.fetch("https://invented.invalid/c", "c", 10)
            self.assertEqual(len(fetch.log), 2)

    def test_redirect_handler_does_not_follow(self):
        lib = d.module("downloader")
        self.assertIsNone(lib.NoRedirect().redirect_request(None, None, 302, "invented", {}, "https://invented.invalid"))

    def test_body_bound_retains_attempt(self):
        lib = d.module("downloader")
        class Response:
            status, headers = 200, {"Content-Length": "5"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        opener = unittest.mock.Mock()
        opener.open.return_value = Response()
        with tempfile.TemporaryDirectory() as tmp:
            fetch = lib.Fetcher(Path(tmp), opener=opener)
            with self.assertRaises(lib.LimitReached):
                fetch.fetch("https://invented.invalid", "x", 4)
            self.assertEqual(len(fetch.log), 1)
            self.assertEqual(Path(tmp, "x").read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()

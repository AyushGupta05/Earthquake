"""Invented fixtures only. No actual source event, catalog or private artifact."""
import copy
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import independent as m
import audit

T = "2020-01-01T00:00:00Z"


def frame():
    rows, outcomes = [], {}
    for i in range(495):
        row = {"event_id": f"invented-{i:03d}", "source": "reused_tail" if i < 149 else "new_lower_M",
               "candidate_calendar_partition": "test2018_2024" if i < 149 else "train2003_2014",
               "mw": 5.5 if i < 149 else 3.2, "cmt_time": "20200101000000" if i < 149 else "20040101000000",
               "cmt_row_indices": [i + 1]}
        if i < 8:
            row["mw"] = [6.0, 6.2, 6.8, 7.1, 6.4, 6.9, 7.0, 7.3][i]
        base = {"event_id": row["event_id"], "status": "ok", "reasons": {}, "nz": {"t0_utc": T}}
        if i < 4:
            base["reasons"][m.REASONS[i % 3]] = 1
        rows.append(row)
        outcomes[row["event_id"]] = {"event_id": row["event_id"], "base": base}
    return rows, outcomes


def invented_plan():
    rows, outcomes = frame()
    events = m.frame_selection(rows, outcomes)
    for event in events:
        event["original_qml"] = {"path": "/invented-only", "pin": {"bytes": 0, "sha256": "0" * 64},
                                 "projection_sha256": "1" * 64, "projection_status": "ok"}
    plan = {"events": events, "requests": m.request_list(events), "event_denominator": 6,
            "new_request_count": 12, "specification": {"caps": m.CAPS, "horizons_seconds": [1, 3, 5]},
            "event_order_sha256": hashlib.sha256(("\n".join(x["event_id"] for x in events) + "\n").encode()).hexdigest()}
    return rows, outcomes, plan


def records(events, incomplete=False, empty=False):
    result = []
    for event in events:
        picks = [] if empty else [{"pick_id": "invented-p", "network": "NZ", "station": "FAKE", "time": T}]
        own = m.clock(picks)
        d = {"all_preferred_arrivals": 1, "qualifying_P_references": 1,
             "unique_qualifying_P_reference_ids": 1, "unique_resolved_qualifying_P_reference_ids": 1,
             "accepted_P_picks": len(picks), "accepted_NZ_P_picks": len(picks)}
        r = {"event_id": event["event_id"], "status": "ok", "accepted_picks": picks, "nz": own,
             "all_network": own, "denominators": d, "incomplete_associated_P_structure": incomplete,
             "NZ_coverage_known": bool(picks) or not incomplete}
        result.append({"event_id": event["event_id"], "role": event["role"], "Mw_band": event["Mw_band"],
                       "preserved_original_T0_us": event["preserved_original_T0_us"],
                       "representations": {name: copy.deepcopy(r) for name in m.SLOTS},
                       "shadow_clocks": {name: {"status": "ok", "own_clock": copy.deepcopy(own),
                            "at_preserved_original_T0": m.clock(picks, event["preserved_original_T0_us"])} for name in m.SLOTS}})
    return result


def qml(extra="", revision="", preferred="invented-o", event_id="invented-e"):
    return (f'<q:quakeml xmlns:q="{m.Q}" xmlns="{m.B}"><eventParameters><event publicID="{m.mapped(event_id)}">'
            f'<preferredOriginID>{preferred}</preferredOriginID>{revision}<origin publicID="invented-o">'
            f'<time><value>{T}</value></time><latitude><value>0.0</value></latitude>'
            '<longitude><value>1</value></longitude><depth><value>1500</value></depth>'
            f'{extra}</origin></event></eventParameters></q:quakeml>').encode()


def scml(version="0.13", extra="", preferred="invented-o"):
    return (f'<seiscomp xmlns="{m.NATIVE[version]}" version="{version}"><EventParameters><event publicID="invented-e">'
            f'<preferredOriginID>{preferred}</preferredOriginID><originReference>invented-o</originReference>'
            '</event><origin publicID="invented-o"><time><value>' + T + '</value></time>'
            '<latitude><value>0</value></latitude><longitude><value>1.0</value></longitude>'
            f'<depth><value>1.5</value></depth>{extra}</origin></EventParameters></seiscomp>').encode()


class Selection(unittest.TestCase):
    def test_fixed_frame_control_rank_and_query_order(self):
        rows, outcomes, plan = invented_plan()
        selected = m.selected_plan(rows, outcomes, plan)
        expected_controls = []
        for band, pool in (("[6,7)", ("invented-004", "invented-005")), (">=7", ("invented-006", "invented-007"))):
            expected_controls.append(min(pool, key=lambda x: hashlib.sha256(
                ("geonet-scml-paired-control-v1|test2018_2024|" + band + "|" + x).encode()).hexdigest()))
        self.assertEqual({x["event_id"] for x in selected if x["role"] == "complete_control"}, set(expected_controls))
        self.assertEqual([r["kind"] for r in plan["requests"]], ["qml", "scml"] * 6)
        self.assertEqual([r["file"] for r in plan["requests"]],
                         [f'{kind}_{i:02d}.xml' for i, kind in enumerate(["qml", "scml"] * 6)])

    def test_outcome_dependent_replacement_fails(self):
        rows, outcomes, plan = invented_plan()
        plan["events"][0]["role"] = "complete_control"
        with self.assertRaises(m.AuditError): m.selected_plan(rows, outcomes, plan)

    def test_unknown_original_is_not_complete(self):
        rows, outcomes = frame()
        outcomes["invented-004"]["base"]["status"] = "failed"
        with self.assertRaises(m.AuditError): m.frame_selection(rows, outcomes)

    def test_original_probe_fourth_reason_kept(self):
        rows, outcomes = frame()
        outcomes["invented-005"]["base"]["reasons"][m.REASONS[0]] = 1
        with self.assertRaises(m.AuditError): m.frame_selection(rows, outcomes)

    def test_duplicate_frame_identity(self):
        rows, outcomes = frame(); rows[-1]["event_id"] = rows[0]["event_id"]
        with self.assertRaises(m.AuditError): m.frame_selection(rows, outcomes)

    def test_boolean_reason_not_numeric_count(self):
        rows, outcomes = frame(); outcomes["invented-000"]["base"]["reasons"][m.REASONS[0]] = True
        with self.assertRaises(m.AuditError): m.frame_selection(rows, outcomes)

    def test_extra_blank_query_parameter_is_not_exact(self):
        rows, outcomes, plan = invented_plan(); plan["requests"][0]["url"] += "&extra="
        with self.assertRaises(m.AuditError): m.selected_plan(rows, outcomes, plan)

    def test_preserved_clock_cannot_change(self):
        rows, outcomes, plan = invented_plan(); plan["events"][0]["preserved_original_T0_us"] -= 1
        with self.assertRaises(m.AuditError): m.selected_plan(rows, outcomes, plan)

    def census_evidence(self):
        bulk, _ = frame()
        rows = [{"row_index": r["cmt_row_indices"][0], "event_id": r["event_id"], "mw": r["mw"],
                 "date": r["cmt_time"], "reasons": []} for r in bulk[:149]]
        groups = [{"event_id": r["event_id"], "row_indices": r["cmt_row_indices"], "eligible": True,
                   "mw_min": r["mw"], "mw_max": r["mw"], "dates": [r["cmt_time"]]} for r in bulk[:149]]
        return bulk, groups, rows, [r["event_id"] for r in bulk[:149]]

    def test_original_census_eligibility_is_independently_bound(self):
        self.assertEqual(m.original_eligibility(*self.census_evidence()), 149)
        for field, value in (("mw", 5.9), ("candidate_calendar_partition", "train2003_2014"),
                             ("cmt_time", "20100101000000"), ("cmt_row_indices", [999])):
            with self.subTest(field=field):
                bulk, groups, rows, ids = self.census_evidence()
                bulk[4][field] = value
                with self.assertRaisesRegex(m.AuditError, "original_tail_eligibility_changed"):
                    m.original_eligibility(bulk, groups, rows, ids)

    def test_census_group_must_resolve_all_original_rows(self):
        bulk, groups, rows, ids = self.census_evidence()
        rows.append(dict(rows[4], row_index=999))
        with self.assertRaisesRegex(m.AuditError, "original_tail_row_membership"):
            m.original_eligibility(bulk, groups, rows, ids)

    def test_census_query_membership_and_date_window_preserved(self):
        bulk, groups, rows, ids = self.census_evidence(); ids[-1] = "invented-extra"
        with self.assertRaisesRegex(m.AuditError, "original_tail_membership"):
            m.original_eligibility(bulk, groups, rows, ids)
        bulk, groups, rows, ids = self.census_evidence()
        groups[4]["dates"] = ["20250101000000"]; rows[4]["date"] = "20250101000000"
        with self.assertRaisesRegex(m.AuditError, "original_tail_date_window"):
            m.original_eligibility(bulk, groups, rows, ids)


class Clocks(unittest.TestCase):
    def test_fractional_widths_and_timezones_exact(self):
        for digits, expected in (("1", 100000), ("12", 120000), ("1234", 123400), ("12345", 123450), ("123456", 123456)):
            self.assertEqual(m.stamp(T[:-1] + "." + digits + "Z") - m.stamp(T), expected)
        self.assertEqual(m.stamp("2020-01-01T01:00:00+01:00"), m.stamp(T))
        with self.assertRaises(m.AuditError): m.stamp(T[:-1])

    def test_strict_boundaries_and_station_dedup(self):
        picks = [{"network": "NZ", "station": "A", "time": T},
                 {"network": "NZ", "station": "A", "time": "2020-01-01T00:00:00.5Z"},
                 {"network": "NZ", "station": "B", "time": "2020-01-01T00:00:01Z"},
                 {"network": "NZ", "station": "C", "time": "2020-01-01T00:00:03Z"},
                 {"network": "XY", "station": "A", "time": "2020-01-01T00:00:05Z"}]
        self.assertEqual(m.clock(picks)["strict_horizon_station_counts"], {"1": 1, "3": 2, "5": 3})
        self.assertEqual(m.clock(picks)["station_count"], 4)

    def test_earlier_recovered_clock_does_not_replace_shadow(self):
        p = [{"network": "NZ", "station": "A", "time": "2019-12-31T23:59:58Z"},
             {"network": "NZ", "station": "B", "time": "2020-01-01T00:00:00.5Z"}]
        self.assertEqual(m.clock(p)["strict_horizon_station_counts"]["1"], 1)
        self.assertEqual(m.clock(p, m.stamp(T))["strict_horizon_station_counts"]["1"], 2)

    def test_zero_incomplete_remains_unknown(self):
        rows, outcomes, plan = invented_plan(); selected = m.selected_plan(rows, outcomes, plan)
        result = records(selected, incomplete=True, empty=True)
        m.slots_and_clocks(selected, result)
        result[0]["representations"]["fresh_qml"]["NZ_coverage_known"] = True
        with self.assertRaises(m.AuditError): m.slots_and_clocks(selected, result)

    def test_unknown_slot_does_not_become_zero(self):
        rows, outcomes, plan = invented_plan(); selected = m.selected_plan(rows, outcomes, plan)
        result = records(selected)
        result[0]["representations"]["native_scml"]["status"] = "unknown_representation"
        result[0]["shadow_clocks"]["native_scml"]["status"] = "unknown_representation"
        with self.assertRaises(m.AuditError): m.slots_and_clocks(selected, result)

    def test_all_eighteen_slots_retained(self):
        rows, outcomes, plan = invented_plan(); selected = m.selected_plan(rows, outcomes, plan)
        result = records(selected)
        self.assertEqual(sum(m.slots_and_clocks(selected, result).values()), 18)
        del result[0]["representations"]["native_scml"]
        with self.assertRaises(m.AuditError): m.slots_and_clocks(selected, result)


class XML(unittest.TestCase):
    def test_native_depth_and_literal_identity(self):
        for version in m.NATIVE:
            core = m.xml_core(scml(version), "invented-e", "scml")
            self.assertEqual(core["origin"], m.xml_core(qml(), "invented-e", "qml")["origin"])
            self.assertEqual(core["preferred_origin_id"], "smi:nz.org.geonet/invented-o")

    def test_plain_qml_attribute_is_not_mapped_again(self):
        body = qml().replace(b'publicID="smi:nz.org.geonet/invented-e"', b'publicID="invented-e"')
        with self.assertRaises(m.AuditError): m.xml_core(body, "invented-e", "qml")

    def test_native_padded_reference_is_unknown_profile(self):
        with self.assertRaises(m.AuditError): m.xml_core(scml(preferred=" invented-o "), "invented-e", "scml")

    def test_native_origin_reference_child_is_not_discarded(self):
        body = scml().replace(b'<originReference>invented-o</originReference>',
                             b'<originReference>invented-o<x/>different</originReference>')
        with self.assertRaisesRegex(m.AuditError, "xml_scalar_container"):
            m.xml_core(body, "invented-e", "scml")

    def test_duplicate_geometry_does_not_choose_first(self):
        with self.assertRaises(m.AuditError): m.xml_core(qml('<latitude><value>2</value></latitude>'), "invented-e", "qml")

    def test_duplicate_quantity_value(self):
        body = qml().replace(b'<value>1500</value>', b'<value>1500</value><value>1501</value>')
        with self.assertRaises(m.AuditError): m.xml_core(body, "invented-e", "qml")

    def test_missing_geometry_is_null(self):
        body = qml().replace(b'<depth><value>1500</value></depth>', b'')
        self.assertIsNone(m.xml_core(body, "invented-e", "qml")["origin"]["depth_m"])

    def test_dtd_and_foreign_evidence_rejected(self):
        for body in (b'<!DOCTYPE q [<!ENTITY x "x">]>' + qml(),
                     qml('<f:depth xmlns:f="urn:foreign"><f:value>2</f:value></f:depth>')):
            with self.assertRaises(m.AuditError): m.xml_core(body, "invented-e", "qml")

    def test_supported_modification_extension_and_duplicate_unknown(self):
        ext = '<creationInfo><n:modificationTime xmlns:n="' + m.NATIVE["0.13"] + '">' + T + '</n:modificationTime></creationInfo>'
        core = m.xml_core(qml(revision=ext), "invented-e", "qml")
        self.assertEqual(core["revision"]["event"]["modificationTime"], T)
        bad = ext.replace('</creationInfo>', '<modificationTime>' + T + '</modificationTime></creationInfo>')
        with self.assertRaises(m.AuditError): m.xml_core(qml(revision=bad), "invented-e", "qml")

    def test_bed_modification_time_is_not_the_native_extension(self):
        body = qml(revision='<creationInfo><modificationTime>' + T + '</modificationTime></creationInfo>')
        with self.assertRaisesRegex(m.AuditError, "revision_singleton_or_namespace"):
            m.xml_core(body, "invented-e", "qml")

    def test_encoding_declaration_matches_the_supported_bytes(self):
        for encoding in ("ISO-8859-1", "UTF-16", "US-ASCII"):
            body = ('<?xml version="1.0" encoding="' + encoding + '"?>').encode() + qml(
                revision='<creationInfo><author>caf\u00e9</author></creationInfo>')
            with self.assertRaisesRegex(m.AuditError, "xml_encoding_declaration_profile"):
                m.xml_core(body, "invented-e", "qml")
        body = b'<?xml version="1.0" encoding="UTF-8"?>' + qml()
        self.assertEqual(m.xml_core(body, "invented-e", "qml")["mapped_event_id"], m.mapped("invented-e"))

    def test_revision_conflict_overrides_equal_time(self):
        a = m.xml_core(qml(revision='<creationInfo><creationTime>' + T + '</creationTime><version>A</version></creationInfo>'), "invented-e", "qml")
        b = copy.deepcopy(a); b["revision"]["event"]["version"] = "B"
        self.assertEqual(m.revision_relation(a, a), "matching_recorded_time")
        self.assertEqual(m.revision_relation(a, b), "conflict")
        c = m.xml_core(qml(), "invented-e", "qml")
        self.assertEqual(m.revision_relation(c, c), "missing_or_incomplete")

    def test_saved_revision_and_geometry_binding(self):
        core = m.xml_core(qml(), "invented-e", "qml")
        record = {"mapped_event_id": core["mapped_event_id"], "preferred_origin_id": core["preferred_origin_id"],
                  "origin": {k: str(v) if k != "time_us" else v for k, v in core["origin"].items()},
                  "event_creation": core["revision"]["event"]}
        record["origin"]["creation"] = core["revision"]["origin"]
        audit.core_record_check(core, record)
        record["origin"]["depth_m"] = "1501"
        with self.assertRaises(m.AuditError): audit.core_record_check(core, record)

    def test_saved_conservative_null_is_unavailable_not_zero_agreement(self):
        core = m.xml_core(qml(), "invented-e", "qml")
        record = {"mapped_event_id": core["mapped_event_id"], "preferred_origin_id": core["preferred_origin_id"],
                  "origin": {"time_us": core["origin"]["time_us"], "latitude": "0", "longitude": "1",
                             "depth_m": None, "creation": core["revision"]["origin"]},
                  "event_creation": core["revision"]["event"]}
        self.assertEqual(audit.core_record_check(core, record), (3, 1))


class Transport(unittest.TestCase):
    def bundle(self):
        _, _, plan = invented_plan(); bodies, ledger = {}, []
        begin = datetime(2020, 1, 1, tzinfo=timezone.utc)
        for i, request in enumerate(plan["requests"]):
            body = b"" if i == 2 else b"invented bytes"
            bodies[request["file"]] = body
            ledger.append({"file": request["file"], "url": request["url"],
                           "utc": (begin + timedelta(seconds=i)).isoformat(), "elapsed_seconds": .05,
                           "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                           "status": "ok", "http_status": 200})
        manifest = {"completed": True, "worker_exit_code": 0, "event_denominator": 6,
                    "representation_denominator": 18, "caps": m.CAPS, "request_attempts": 12,
                    "response_body_bytes": sum(len(x) for x in bodies.values()), "outer_elapsed_seconds": 15.0}
        return plan, manifest, ledger, bodies

    def test_all_twelve_attempts_including_empty_body(self):
        bundle = self.bundle()
        self.assertEqual(m.transport_replay(*bundle)["attempts"], 12)

    def test_attempt_order_changed(self):
        plan, manifest, ledger, bodies = self.bundle(); ledger[0], ledger[1] = ledger[1], ledger[0]
        with self.assertRaises(m.AuditError): m.transport_replay(plan, manifest, ledger, bodies)

    def test_partial_hash_and_body_total_changed(self):
        for field, value in (("response_body_bytes", 0), ("completed", False), ("outer_elapsed_seconds", 360.1)):
            plan, manifest, ledger, bodies = self.bundle(); manifest[field] = value
            with self.assertRaises(m.AuditError): m.transport_replay(plan, manifest, ledger, bodies)
        plan, manifest, ledger, bodies = self.bundle(); bodies[plan["requests"][0]["file"]] = b"different"
        with self.assertRaises(m.AuditError): m.transport_replay(plan, manifest, ledger, bodies)

    def test_timing_no_tolerance(self):
        plan, manifest, ledger, bodies = self.bundle(); ledger[0]["elapsed_seconds"] = 20.0001
        with self.assertRaises(m.AuditError): m.transport_replay(plan, manifest, ledger, bodies)
        plan, manifest, ledger, bodies = self.bundle(); ledger[1]["utc"] = "2020-01-01T00:00:00.999999Z"
        with self.assertRaises(m.AuditError): m.transport_replay(plan, manifest, ledger, bodies)


class IO(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=audit.BASE)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_json_duplicate_and_nan_rejected(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'not json'):
            with self.assertRaises(m.AuditError): audit.decode(body)

    def test_reader_pin_cap_and_symlink(self):
        path = self.root / "invented.txt"; path.write_bytes(b"123")
        reader = audit.Reader()
        self.assertEqual(reader.read(path, m.size_hash(b"123"), 3), b"123")
        with self.assertRaises(m.AuditError): reader.read(path, cap=2)
        with self.assertRaises(m.AuditError): reader.read(path, m.size_hash(b"124"))
        link = self.root / "link"; link.symlink_to(path)
        with self.assertRaises(m.AuditError): audit.Reader().read(link)

    def test_handoff_flags_gate_before_input_read(self):
        path = self.root / "invented_handoff.json"
        path.write_text(json.dumps({"authorized_private_read": True, "files": {"paired_plan": {"path": "/must/not/read"}}}))
        with self.assertRaisesRegex(m.AuditError, "private_read_disabled"): audit.run(path, "selection")

    def test_path_escape(self):
        with self.assertRaises(m.AuditError): audit.safe_path(audit.WORK / ".." / "outside")

    def test_output_dotdot_escape_is_rejected_before_creation(self):
        path = audit.BASE / "local_runs" / ".." / "invented-report.json"
        self.assertEqual(audit.safe_path(path), audit.BASE / "invented-report.json")
        with patch.object(sys, "argv", ["audit.py", "selection", "--handoff", str(self.root / "unused"),
                                       "--output", str(path)]), \
             patch.object(audit.signal, "signal"), patch.object(audit.signal, "setitimer"):
            with self.assertRaisesRegex(m.AuditError, "output_outside_auditor_local_runs"):
                audit.main()
        self.assertFalse(path.exists())


class Integration(unittest.TestCase):
    """Complete invented receipt chain, with one failed new retrieval retained."""
    def fixture(self):
        temp = tempfile.TemporaryDirectory(dir=audit.BASE)
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        def put(name, value):
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
            body = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
            path.write_bytes(body)
            return {"path": str(path), "pin": m.size_hash(body)}
        rows, outcomes, plan = invented_plan()
        originals, old_requests, old_members = {}, [], {}
        for event in plan["events"]:
            eid = event["event_id"]
            entry = put("census/raw/" + eid + ".xml", qml(event_id=eid))
            originals[eid] = entry; old_members["raw/" + eid + ".xml"] = entry["pin"]
            event["original_qml"].update(path=entry["path"], pin=entry["pin"])
            old_requests.append({"file": eid + ".xml", "status": "ok", "http_status": 200, **entry["pin"]})
        census_rows = [{"row_index": r["cmt_row_indices"][0], "event_id": r["event_id"],
                        "mw": r["mw"], "date": r["cmt_time"], "reasons": []} for r in rows[:149]]
        census_groups = [{"event_id": r["event_id"], "row_indices": r["cmt_row_indices"], "eligible": True,
                          "mw_min": r["mw"], "mw_max": r["mw"], "dates": [r["cmt_time"]]} for r in rows[:149]]
        census_values = {"groups.json": census_groups, "manifest.json": {"completed": True, "files": old_members},
                         "outcomes.json": {x["event_id"]: outcomes[x["event_id"]]["base"] for x in rows[:149]},
                         "query_order.json": [x["event_id"] for x in rows[:149]], "requests.json": old_requests,
                         "rows.json": census_rows, "summary.json": {"invented": True}}
        files = {"census_" + k: put("census/" + k, v) for k, v in census_values.items()}
        bulk_plan = {"rows": rows, "input_pins": {k: files["census_" + k]["pin"]["sha256"] for k in census_values}}
        files["bulk_0"] = put("bulk/planned.json", bulk_plan)
        files["bulk_1"] = put("bulk/parent.json", {"plan_sha256": files["bulk_0"]["pin"]["sha256"]})
        files["bulk_3"] = put("bulk/outcomes.json", list(outcomes.values()))
        files["bulk_4"] = put("bulk/summary.json", {"completed": True, "metadata_missingness_gate_pass": True})
        files["bulk_5"] = put("bulk/requests.json", [{} for _ in range(346)])
        files["bulk_2"] = put("bulk/manifest.json", {"completed": True,
            "plan_sha256": files["bulk_0"]["pin"]["sha256"], "parent_receipt_sha256": files["bulk_1"]["pin"]["sha256"],
            "files": {name: files["bulk_" + str(i)]["pin"] for i, name in ((3, "outcomes.json"), (4, "summary.json"), (5, "requests.json"))}})
        bulk_pins = {name: files["bulk_" + str(i)]["pin"]["sha256"] for i, name in enumerate(audit.BULK_NAMES)}
        files["bulk_replay"] = put("bulk/replay.json", {"all_checks_pass": True})
        files["selection_input"] = put("selection_input.json", {"version": "geonet-paired-selection-inputs-v1",
            "completed_bulk_independently_replayed": True, "bulk_gate_passed": True, "bulk_files": bulk_pins,
            "bulk_independent_replay_path": files["bulk_replay"]["path"],
            "bulk_independent_replay_sha256": files["bulk_replay"]["pin"]["sha256"]})
        source = put("invented_public.txt", b"invented inert producer source\n")
        processing = {"invented_public.txt": source["pin"]["sha256"]}
        plan.update(input_receipt_path=files["selection_input"]["path"],
                    input_receipt_sha256=files["selection_input"]["pin"]["sha256"], bulk_input_pins=bulk_pins,
                    bulk_replay_sha256=files["bulk_replay"]["pin"]["sha256"],
                    processing_files=processing, runtime={"invented_runtime": True}, reviewed_dependencies={"invented": True})
        plan["specification"].update(bulk_plan_sha256=files["bulk_0"]["pin"]["sha256"],
                                      census_groups_sha256=files["census_groups.json"]["pin"]["sha256"])
        files["paired_plan"] = put("paired_plan.json", plan)
        selected = m.selected_plan(rows, outcomes, plan)
        result = records(selected)
        ledger = []
        for i, request in enumerate(plan["requests"]):
            kind = request["kind"]; eid = request["event_id"]
            body = qml(event_id=eid) if kind == "qml" else scml().replace(b'invented-e', eid.encode())
            failed = i == 0
            if failed: body = b""
            entry = put("collection/raw/" + request["file"], body)
            ledger.append({"file": request["file"], "url": request["url"], **entry["pin"],
                           "utc": (datetime(2020, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=i)).isoformat(),
                           "elapsed_seconds": .05, "status": "URLError" if failed else "ok",
                           "http_status": None if failed else 200})
        for event, row in zip(plan["events"], result):
            for slot in m.SLOTS:
                if slot == "fresh_qml" and event["event_id"] == plan["events"][0]["event_id"]:
                    row["representations"][slot] = {"event_id": event["event_id"], "status": "transport_failed",
                        "denominators": None, "nz": None, "all_network": None, "accepted_picks": None}
                    row["shadow_clocks"][slot] = {"status": "transport_failed", "own_clock": None,
                                                 "at_preserved_original_T0": None}
                    continue
                body = qml(event_id=event["event_id"]) if slot != "native_scml" else scml().replace(
                    b'invented-e', event["event_id"].encode())
                core = m.xml_core(body, event["event_id"], "scml" if slot == "native_scml" else "qml")
                saved = row["representations"][slot]
                saved.update(mapped_event_id=core["mapped_event_id"], preferred_origin_id=core["preferred_origin_id"],
                             origin={k: str(v) if k != "time_us" and v is not None else v for k, v in core["origin"].items()},
                             event_creation=core["revision"]["event"])
                saved["origin"]["creation"] = core["revision"]["origin"]
            for name in ("catalogue_drift", "representation_difference"):
                row[name] = {"revision_evidence": "missing_or_incomplete", "atomic_database_revision_verified": False,
                             "converter_bug_proved": False, "content_matched_resolution_candidate_count": 0,
                             "paired_recorded_revision_resolution_count": 0}
        statuses = m.slots_and_clocks(selected, result)
        put("collection/event_outcomes.json", result)
        put("collection/requests.json", ledger)
        put("collection/summary.json", {"completed": True, "source_event_denominator": 6, "representation_denominator": 18,
            "representation_status_counts": statuses, "atomic_database_revision_verified": False, "physical_pick_validated": False})
        put("collection/native_worker.log", b"")
        parent = {"version": "geonet-paired-parent-receipt-v1", "acquisition_authorized": True,
                  "code_only_review_clean": True, "private_selection_independently_replayed": True, "freeze_pushed": True,
                  "git_freeze_commit": "f" * 40, "private_selection_replay_sha256": "e" * 64,
                  "plan_sha256": files["paired_plan"]["pin"]["sha256"], **{k: plan[k] for k in audit.PRODUCER_FIELDS}}
        files["paired_parent"] = put("parent.json", parent)
        collection = root / "collection"
        members = {str(x.relative_to(collection)): m.size_hash(x.read_bytes()) for x in collection.rglob("*") if x.is_file()}
        files["paired_manifest"] = put("collection/manifest.json", {"completed": True, "worker_exit_code": 0,
            "plan_sha256": parent["plan_sha256"], "parent_receipt_sha256": files["paired_parent"]["pin"]["sha256"],
            "event_denominator": 6, "representation_denominator": 18, "caps": m.CAPS,
            "request_attempts": 12, "response_body_bytes": sum(x["bytes"] for x in ledger), "outer_elapsed_seconds": 15,
            "files": members, **{k: plan[k] for k in ("processing_files", "reviewed_dependencies", "runtime", "input_receipt_sha256")}})
        receipt = {"version": "paired-independent-private-handoff-v1", "authorized_private_read": True,
            "producer_review_clean": True, "auditor_review_clean": True, "freeze_pushed": True, "inputs_preserved": True,
            "git_freeze_commit": "f" * 40, "collection_completed_preserved_normal_exit": True,
            "collection_root": str(collection), "files": files, "original_bodies": originals,
            "auditor_processing_files": {name: m.digest((audit.BASE / name).read_bytes()) for name in audit.AUDITOR_FILES},
            "auditor_runtime": {"python_version": sys.version, "cache_tag": sys.implementation.cache_tag,
                                "binary_sha256": m.digest(Path(sys.executable).resolve().read_bytes())},
            "producer_processing_files": processing, "producer_public_files": {"invented_public.txt": source},
            "producer_runtime": plan["runtime"], "producer_reviewed_dependencies": plan["reviewed_dependencies"]}
        handoff = put("handoff.json", receipt)
        return root, handoff["path"]

    def test_full_chain_and_failed_slot_do_not_claim_full_semantics(self):
        root, handoff = self.fixture()
        report = audit.run(handoff, "selection")
        self.assertTrue(report["all_scoped_checks_pass"])
        report = audit.run(handoff, "artifacts")
        self.assertTrue(report["all_scoped_checks_pass"])
        self.assertEqual(report["raw_core_verified_parsed_slots"], 17)
        self.assertEqual(report["raw_core_unverified_slots"], 1)
        self.assertFalse(report["complete_arrival_or_conversion_semantics_verified"])
        self.assertFalse(report["recovery_counts_independently_verified"])

    def test_original_bytes_changed(self):
        root, handoff = self.fixture()
        original = next((root / "census/raw").iterdir()); original.write_bytes(b"changed")
        with self.assertRaisesRegex(m.AuditError, "input_pin_mismatch"): audit.run(handoff, "selection")

    def test_soft_deadline_during_xml_never_becomes_unavailable_evidence(self):
        root, handoff = self.fixture()
        with patch.object(m, "xml_core", side_effect=audit.Deadline("auditor_deadline")):
            with self.assertRaises(audit.Deadline): audit.run(handoff, "artifacts")

    def mutate_original_status(self, root, handoff, status):
        path = root / "collection/event_outcomes.json"
        results = json.loads(path.read_text())
        results[0]["representations"]["original_qml"] = {"event_id": results[0]["event_id"], "status": status,
            "denominators": None, "nz": None, "all_network": None, "accepted_picks": None}
        results[0]["shadow_clocks"]["original_qml"] = {"status": status, "own_clock": None,
                                                     "at_preserved_original_T0": None}
        path.write_text(json.dumps(results))
        summary_path = root / "collection/summary.json"
        summary = json.loads(summary_path.read_text())
        summary["representation_status_counts"] = dict(Counter(
            slot + ":" + record["status"] for row in results
            for slot, record in row["representations"].items()))
        summary_path.write_text(json.dumps(summary))
        manifest_path = root / "collection/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for name in ("event_outcomes.json", "summary.json"):
            manifest["files"][name] = m.size_hash((root / "collection" / name).read_bytes())
        manifest_path.write_text(json.dumps(manifest))
        receipt = json.loads(Path(handoff).read_text())
        receipt["files"]["paired_manifest"]["pin"] = m.size_hash(manifest_path.read_bytes())
        Path(handoff).write_text(json.dumps(receipt))

    def test_completed_original_slot_cannot_remain_unfinished(self):
        for status in ("attempting", "interrupted", "not_attempted"):
            with self.subTest(status=status):
                root, handoff = self.fixture()
                self.mutate_original_status(root, handoff, status)
                with self.assertRaisesRegex(m.AuditError, "completed_slot_not_terminal"):
                    audit.run(handoff, "artifacts")

    def test_successfully_retrieved_original_cannot_be_transport_failed(self):
        root, handoff = self.fixture()
        self.mutate_original_status(root, handoff, "transport_failed")
        with self.assertRaisesRegex(m.AuditError, "original_successful_retrieval_status"):
            audit.run(handoff, "artifacts")

    def test_extra_collection_artifact_and_incomplete_handoff(self):
        root, handoff = self.fixture(); (root / "collection/extra.txt").write_text("invented extra")
        with self.assertRaisesRegex(m.AuditError, "collection_extra_or_missing_members"): audit.run(handoff, "artifacts")
        body = json.loads(Path(handoff).read_text()); body["collection_completed_preserved_normal_exit"] = False
        Path(handoff).write_text(json.dumps(body))
        with self.assertRaisesRegex(m.AuditError, "completed_handoff_required"): audit.run(handoff, "artifacts")


if __name__ == "__main__":
    unittest.main()

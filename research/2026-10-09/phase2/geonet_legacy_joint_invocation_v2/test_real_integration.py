"""Invented cohorts through all120 pinned public members and the real frozen modules."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location("invented_real_" + name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


h, s = load("child_harness"), load("supervisor")
MODULE_NAMES = ("projection", "comparison", "shadow", "independent_legacy_semantic_v3")
PREFIX = "smi:nz.org.geonet/"


def invented_body(index, native=False, version="0.11", kind="known"):
    eid, oid, pid = "invented%d" % index, "origin%d" % index, "pick%d" % index
    def mapped(value):
        return value if native else PREFIX + value
    pick = ('<pick publicID="%s"><time><value>1970-01-01T00:00:00Z</value></time>'
            '<waveformID networkCode="%s" stationCode="FAKE"/></pick>') % (
                mapped(pid), "XX" if kind == "non_nz" else "NZ")
    if kind == "missing_pick":
        pick = ""
    if kind == "duplicate_pick":
        pick += pick
    weight = "<weight>1</weight>" if native else "<timeWeight>1</timeWeight>"
    if native and kind == "bad_flag":
        weight += "<timeUsed>unknown</timeUsed>"
    origin = ('<origin publicID="%s"><time><value>1970-01-01T00:00:00Z</value></time>'
        '<latitude><value>-40</value></latitude><longitude><value>175</value></longitude>'
        '<depth><value>%s</value></depth><arrival><pickID>%s</pickID><phase>P</phase>%s'
        '</arrival></origin>') % (mapped(oid), "10" if native else "10000", mapped(pid), weight)
    if native:
        text = ('<seiscomp xmlns="http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/%s" '
            'version="%s"><EventParameters><event publicID="%s"><preferredOriginID>%s'
            '</preferredOriginID><originReference>%s</originReference></event>%s%s'
            '</EventParameters></seiscomp>') % (version, version, eid, oid, oid, origin, pick)
    else:
        text = ('<q:quakeml xmlns:q="http://quakeml.org/xmlns/quakeml/1.2" '
            'xmlns="http://quakeml.org/xmlns/bed/1.2"><eventParameters><event publicID="%s">'
            '<preferredOriginID>%s</preferredOriginID>%s%s</event></eventParameters>'
            '</q:quakeml>') % (mapped(eid), mapped(oid), origin, pick)
    if kind == "comment":
        text = text.replace("<EventParameters>", "<EventParameters><!--invented-->") if native else (
            text.replace("<eventParameters>", "<eventParameters><!--invented-->"))
    if kind == "malformed_qml" and not native:
        text = "<invalid"
    return text.encode()


class RealFixture:
    def __init__(self, directory, kind="known", anchor=0):
        self.root = Path(directory).resolve()
        bundles = json.loads((ROOT / "public_dependency_bundles.json").read_text())
        for role, bundle in bundles.items():
            # The context copies preserve all exact member bytes/names. Only their
            # canonical source directory changes inside an isolated review snapshot.
            bundle["directory"] = str((ROOT / "public_dependencies" / role).resolve())
        self.plan = {"protocol_id": h.PROTOCOL, "original_plan_sha256": "1" * 64,
            "original_manifest_sha256": "2" * 64, "original_census_clock_source_sha256": "3" * 64,
            "processing_source_mapping_sha256": "a4a62b0ecea3b7cc92b6092729f4fb49c527198421d59ba988393799c42747cd",
            **bundles, "events": []}
        for index in range(6):
            row = {"event_id": "invented%d" % index, "original_t0_us": anchor,
                   "native_profile": None, "bodies": {}}
            for representation in h.REPRESENTATIONS:
                body = invented_body(index, representation == "native_scml",
                                     "0.10" if index == 0 else "0.11", kind)
                path = self.root / ("%d_%s.xml" % (index, representation))
                path.write_bytes(body)
                row["bodies"][representation] = {"path": str(path), "bytes": len(body), "sha256": h.digest(body)}
            self.plan["events"].append(row)
        runtime = str(Path(sys.executable).resolve())
        self.trusted = {"adapter_sha256": h.digest((ROOT / "child_harness.py").read_bytes()),
            "supervisor_sha256": h.digest((ROOT / "supervisor.py").read_bytes()),
            "runtime_path": runtime, "runtime_sha256": h.digest(Path(runtime).read_bytes())}
        self.auth = {"protocol_id": h.PROTOCOL, "authorization": "one_fixed_offline_invocation",
            "adapter_sha256": self.trusted["adapter_sha256"], "supervisor_sha256": self.trusted["supervisor_sha256"],
            "runtime": {"path": runtime, "sha256": self.trusted["runtime_sha256"]},
            "pushed_freeze": "a" * 40, "original_census_clock_source_sha256": "3" * 64,
            "original_census_clocks_independently_verified": True, "source_freeze_tests_review_verified": True,
            "git_pushed_freeze_independently_verified": True, "network_requests_authorized": 0,
            "adapter_review_receipt_sha256": "b" * 64, "adapter_test_receipt_sha256": "c" * 64}
        # These assertions exist only as invented fixtures, not real grants.
        self.plan_path, self.auth_path = self.root / "plan.json", self.root / "authorization.json"
        self.save()

    def save(self):
        for role in ("producer", "auditor"):
            self.auth[role + "_bundle_sha256"] = h.digest(h.encoded(self.plan[role]))
        plan = h.encoded(self.plan)
        self.trusted["plan_sha256"] = self.auth["plan_sha256"] = h.digest(plan)
        auth = h.encoded(self.auth)
        self.trusted["authorization_sha256"] = h.digest(auth)
        self.plan_path.write_bytes(plan)
        self.auth_path.write_bytes(auth)

    def execute(self, progress=None):
        return json.loads(h.execute(str(self.plan_path), str(self.auth_path), self.trusted,
                                    time.monotonic() + 60, progress))

    def supervise(self):
        t = self.trusted
        return s.supervise(t["runtime_path"], t["runtime_sha256"], str(ROOT / "child_harness.py"),
            t["adapter_sha256"], t["supervisor_sha256"], str(self.plan_path), t["plan_sha256"],
            str(self.auth_path), t["authorization_sha256"], str(self.root / "output"), max_seconds=60)


class RealIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.assertFalse(any(name in sys.modules for name in MODULE_NAMES))

    def tearDown(self):
        for name in MODULE_NAMES:
            sys.modules.pop(name, None)

    def test_real_modules_and_full_bundles_serialize_eighteen_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            progress = h.Progress()
            result = RealFixture(directory).execute(progress)
            self.assertEqual(result["public_aggregate"]["independent_status_counts"], {"ok": 18})
            self.assertEqual(result["public_aggregate"]["known_projection_clock_mismatch_slots"], 0)
            self.assertEqual(progress.validated_body_count, 18)
            self.assertEqual(progress.stage, "serialization")

    def test_null_preserved_clock_matches_real_producer_without_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            result = RealFixture(directory, anchor=None).execute()
            self.assertEqual(result["public_aggregate"]["known_projection_clock_mismatch_slots"], 0)
            for event in result["private"]["independent"]:
                for clock in event["shadow_clocks"].values():
                    self.assertIsNone(clock["at_preserved_original_T0"])
                    self.assertEqual(clock["own_clock"]["t0_us"], 0)

    def test_real_supervised_fresh_child(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = RealFixture(directory)
            receipt = fixture.supervise()
            self.assertTrue(receipt["complete"])
            self.assertEqual(receipt["returncode"], 0)
            self.assertTrue(receipt["group_termination_confirmed"])
            output = (fixture.root / "output" / "private_result.json").read_bytes()
            self.assertEqual(h.digest(output), receipt["result_sha256"])
            self.assertEqual(json.loads(output)["public_aggregate"]["representation_slots"], 18)

    def test_real_unknowns_and_incomplete_subsets_preserve_all_slots(self):
        for kind, expected in (("missing_pick", {"ok": 18}), ("duplicate_pick", {"ok": 18}),
                               ("non_nz", {"ok": 18}), ("bad_flag", {"ok": 18}),
                               ("comment", {"unknown_representation": 18}),
                               ("malformed_qml", {"ok": 6, "unknown_representation": 12})):
            for name in MODULE_NAMES:
                sys.modules.pop(name, None)
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                result = RealFixture(directory, kind).execute()
                self.assertEqual(result["public_aggregate"]["independent_status_counts"], expected)
                self.assertEqual(result["public_aggregate"]["representation_slots"], 18)
                self.assertEqual(len(result["private"]["producer"]["events"]), 6)

    def test_real_child_body_pin_failure_is_bounded_and_private(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = RealFixture(directory)
            path = fixture.plan["events"][2]["bodies"]["fresh_qml"]["path"]
            Path(path).write_bytes(b"PRIVATE_ID /PRIVATE/PATH <PRIVATE_XML>")
            receipt = fixture.supervise()
            self.assertFalse(receipt["complete"])
            self.assertEqual(receipt["returncode"], 1)
            self.assertTrue(receipt["group_termination_confirmed"])
            self.assertEqual(receipt["stdout_bytes"], 0)
            diagnostic_bytes = (fixture.root / "output" / "stderr.part").read_bytes()
            self.assertLessEqual(len(diagnostic_bytes), h.DIAGNOSTIC_CAP)
            self.assertNotIn(b"PRIVATE", diagnostic_bytes)
            diagnostic = json.loads(diagnostic_bytes)
            self.assertEqual(diagnostic["stage"], "body_validation")
            self.assertEqual(diagnostic["body_index"], 7)
            self.assertEqual(diagnostic["validated_body_count"], 7)
            self.assertEqual(diagnostic["exception_class"], "ValueError")


if __name__ == "__main__":
    unittest.main()

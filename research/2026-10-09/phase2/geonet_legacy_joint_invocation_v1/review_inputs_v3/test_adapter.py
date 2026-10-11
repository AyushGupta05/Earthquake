"""Invented inputs/stub interfaces only; never import the frozen scientific implementations."""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
h = load("child_harness")
s = load("supervisor")


def native(version="0.11"):
    return (f'<seiscomp xmlns="http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/{version}" version="{version}"><EventParameters/></seiscomp>').encode()


def pick(station, timestamp, network="NZ"):
    return {"station": station, "network": network, "time": timestamp}


class ClockTests(unittest.TestCase):
    def test_strict_deadlines_and_negative_offsets(self):
        picks = [pick("a", "1970-01-01T00:00:09Z"), pick("b", "1970-01-01T00:00:11Z"),
                 pick("c", "1970-01-01T00:00:13Z"), pick("d", "1970-01-01T00:00:15Z"),
                 pick("d", "1970-01-01T00:00:14Z"), pick("x", "1970-01-01T00:00:08Z", "XX")]
        clock = h.independent_clocks({"status": "ok", "accepted_picks": picks}, 10_000_000)
        self.assertEqual(clock["own_clock"]["t0_us"], 9_000_000)
        self.assertEqual(clock["at_preserved_original_T0"]["strict_horizon_station_counts"], {"1": 1, "3": 2, "5": 4})
        self.assertEqual(clock["own_clock"]["station_count"], 4)

    def test_offsets_and_microseconds(self):
        self.assertEqual(h.utc_us("1970-01-01T01:00:00.123456+01:00"), 123456)
        self.assertEqual(h.utc_us("1969-12-31T23:59:59.999999Z"), -1)

    def test_null_anchor_empty_known_and_unknown(self):
        empty = h.independent_clocks({"status": "ok", "accepted_picks": []}, None)
        self.assertEqual(empty["own_clock"]["station_count"], 0)
        self.assertEqual(empty["own_clock"]["strict_horizon_station_counts"], {"1": None, "3": None, "5": None})
        self.assertIsNone(h.independent_clocks({"status": "unknown_representation"}, 0)["own_clock"])

    def test_invalid_accepted_record_and_anchor(self):
        for records in (None, [None], [pick("", "1970-01-01T00:00:00Z")], [pick("a", "1970-01-01T00:00:00")]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                h.independent_clocks({"status": "ok", "accepted_picks": records}, 0)
        for anchor in (True, 1.0, 10**30):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                h.valid_anchor(anchor)

    def test_native_root_exact(self):
        for version in ("0.10", "0.11"):
            self.assertEqual(h.native_root_profile(native(version)), version)
        for body in (native("0.13"), native().replace(b'version="0.11"', b'version="0.10"'), b'<foreign/>',
                     b'<!DOCTYPE seiscomp [<!ENTITY x "a">]>' + native(), b'<?xml version="1.0" encoding="ISO-8859-1"?>' + native(), b'\xff'):
            with self.subTest(body=body):
                self.assertIsNone(h.native_root_profile(body))

    def test_utf16_utf32_ascii_nul_bytes_not_utf8_xml(self):
        text = '<?xml version="1.0" encoding="UTF-16"?>' + native().decode()
        for encoding in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
            with self.subTest(encoding=encoding):
                self.assertIsNone(h.native_root_profile(text.encode(encoding)))

    def test_root_only_no_full_parse_claim(self):
        self.assertEqual(h.native_root_profile(native()[:-15]), "0.11")
        self.assertEqual(h.native_root_profile(b'<!--outside--><?outside yes?>' + native()), "0.11")


def interface_stubs(unknown=False, mismatch=False):
    def project(body, eid, fmt, profile=None):
        if unknown and fmt == "scml":
            return {"status": "unknown_representation", "accepted_picks": None}
        return {"status": "ok", "event_id": eid, "accepted_picks": [pick("A", "1970-01-01T00:00:00Z")], "profile_supplied": profile}
    auditor = types.SimpleNamespace(project=project, compare=lambda left, right: {"available": left["status"] == right["status"] == "ok",
        "content_matched_resolution_candidate_count": 1})
    def run(events, provenance):
        outputs = []
        for event in events:
            reps = {rep: project(event[rep], event["event_id"], "scml" if rep == "native_scml" else "qml") for rep in h.REPRESENTATIONS}
            clocks = {rep: h.independent_clocks(reps[rep], event["original_t0_us"]) for rep in h.REPRESENTATIONS}
            if mismatch:
                clocks["original_qml"]["own_clock"]["station_count"] = 99
            outputs.append({"representations": reps, "shadow_clocks": clocks,
                "preserved_original_T0_us": event["original_t0_us"],
                "native_profile_binding": {"recognized": event["native_profile"], "supplied": event["native_profile"], "bound": not unknown}})
        return {"protocol_id": "geonet_legacy_offline_shadow_v2", "events": outputs, "provenance": provenance}
    return types.SimpleNamespace(run_shadow=run), auditor


class JointTests(unittest.TestCase):
    def events(self):
        return [{"event_id": "invented%d" % i, "original_t0_us": 0, "native_profile": "0.11", "native_scml": native(),
                 "fresh_qml": b"invented", "original_qml": b"invented"} for i in range(6)]

    def test_primary_profile_and_scope_differences(self):
        shadow, auditor = interface_stubs()
        result = h.joint_result(self.events(), {}, shadow, auditor)
        self.assertEqual(result["public_aggregate"]["representation_slots"], 18)
        self.assertFalse(result["public_aggregate"]["universal_semantic_equality_claim_permitted"])
        self.assertFalse(result["public_aggregate"]["shared_clock_claim_permitted"])
        self.assertEqual(result["private"]["independent"][0]["primary_qml_profile"], "0.11")
        self.assertEqual(result["private"]["policy_differences"]["auditor_guarded_recovery_scope"], "NZ")

    def test_unknown_native_removes_qml_profile(self):
        shadow, auditor = interface_stubs(unknown=True)
        result = h.joint_result(self.events(), {}, shadow, auditor)
        event = result["private"]["independent"][0]
        self.assertIsNone(event["primary_qml_profile"])
        self.assertIsNone(event["representations"]["original_qml"]["profile_supplied"])
        self.assertIsNone(event["shadow_clocks"]["native_scml"]["own_clock"])
        self.assertEqual(result["public_aggregate"]["independent_status_counts"], {"ok": 12, "unknown_representation": 6})

    def test_unknown_native_withheld_profile_preserved(self):
        shadow, auditor = interface_stubs(unknown=True)
        original = shadow.run_shadow
        def withheld(events, provenance):
            result = original(events, provenance)
            for event in result["events"]:
                event["native_profile_binding"]["recognized"] = None
            return result
        shadow.run_shadow = withheld
        result = h.joint_result(self.events(), {}, shadow, auditor)
        self.assertIsNone(result["private"]["independent"][0]["primary_qml_profile"])

    def test_clock_mismatch_preserves_both(self):
        result = h.joint_result(self.events(), {}, *interface_stubs(mismatch=True))
        self.assertEqual(result["public_aggregate"]["known_projection_clock_mismatch_slots"], 6)
        self.assertEqual(result["private"]["producer"]["events"][0]["shadow_clocks"]["original_qml"]["own_clock"]["station_count"], 99)
        self.assertEqual(result["private"]["independent"][0]["shadow_clocks"]["original_qml"]["own_clock"]["station_count"], 1)

    def test_signed_own_clock_diagnostic_retains_negative_offset(self):
        events = self.events()
        for event in events:
            event["original_t0_us"] = 1000000
        result = h.joint_result(events, {}, *interface_stubs())
        self.assertEqual(result["public_aggregate"]["independent_own_clock_earlier_than_preserved_slots"], 18)
        self.assertEqual(result["private"]["independent"][0]["signed_clock_diagnostics"]["original_qml"]["independent_own_earliest_minus_original_T0_us"], -1000000)

    def test_root_profile_mismatch_rejected(self):
        events = self.events()
        events[0]["native_profile"] = "0.10"
        with self.assertRaises(ValueError):
            h.joint_result(events, {}, *interface_stubs())


class SyntheticPlan:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.code = {"producer": {key: b"# invented stub source" for key in h.EXPECTED_CODE["producer"]},
                     "auditor": {"semantic_audit.py": b"# independently invented stub source"}}
        self.expected = {role: {name: h.digest(body) for name, body in members.items()} for role, members in self.code.items()}
        self.plan = {"protocol_id": h.PROTOCOL, "original_plan_sha256": "1" * 64, "original_manifest_sha256": "2" * 64,
                     "original_census_clock_source_sha256": "3" * 64, "processing_source_mapping_sha256": "4" * 64, "events": []}
        for role in ("producer", "auditor"):
            directory = self.root / role
            directory.mkdir()
            members = {}
            source = dict(self.code[role])
            for i in range(h.EXPECTED_BUNDLE_MEMBERS[role] - len(source)):
                source["invented_context_%d.txt" % i] = b"source-only invented context"
            for name, body in source.items():
                (directory / name).write_bytes(body)
                members[name] = {"bytes": len(body), "sha256": h.digest(body)}
            self.plan[role] = {"directory": str(directory), "members": members}
        for i in range(6):
            row = {"event_id": "invented%d" % i, "original_t0_us": i, "native_profile": "0.11", "bodies": {}}
            for rep in h.REPRESENTATIONS:
                body = native() if rep == "native_scml" else b"<invented/>"
                path = self.root / (str(i) + "_" + rep + ".xml")
                path.write_bytes(body)
                row["bodies"][rep] = {"path": str(path), "bytes": len(body), "sha256": h.digest(body)}
            self.plan["events"].append(row)
        self.trusted = {"adapter_sha256": "5" * 64, "supervisor_sha256": "6" * 64,
                        "runtime_path": str(Path(sys.executable).resolve()), "runtime_sha256": "7" * 64}
        self.auth = {"protocol_id": h.PROTOCOL, "authorization": "one_fixed_offline_invocation",
                     "adapter_sha256": self.trusted["adapter_sha256"], "supervisor_sha256": self.trusted["supervisor_sha256"],
                     "runtime": {"path": self.trusted["runtime_path"], "sha256": self.trusted["runtime_sha256"]},
                     "pushed_freeze": "a" * 40, "original_census_clock_source_sha256": "3" * 64,
                     "original_census_clocks_independently_verified": True, "source_freeze_tests_review_verified": True,
                     "git_pushed_freeze_independently_verified": True, "network_requests_authorized": 0,
                     "adapter_review_receipt_sha256": "b" * 64, "adapter_test_receipt_sha256": "c" * 64}

    def save(self):
        for role in ("producer", "auditor"):
            self.auth[role + "_bundle_sha256"] = h.digest(h.encoded(self.plan[role]))
        plan = h.encoded(self.plan)
        self.trusted["plan_sha256"] = self.auth["plan_sha256"] = h.digest(plan)
        auth = h.encoded(self.auth)
        self.trusted["authorization_sha256"] = h.digest(auth)
        self.plan_path, self.auth_path = self.root / "plan.json", self.root / "auth.json"
        self.plan_path.write_bytes(plan)
        self.auth_path.write_bytes(auth)

    def execute(self):
        self.save()
        with patch.object(h, "EXPECTED_CODE", self.expected), patch.object(h, "load_frozen", return_value=interface_stubs()):
            return h.execute(str(self.plan_path), str(self.auth_path), self.trusted, time.monotonic() + 30)


class GateTests(unittest.TestCase):
    def test_full_invented_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyntheticPlan(directory)
            result = json.loads(fixture.execute())
            self.assertEqual(result["public_aggregate"]["events"], 6)
            self.assertFalse(result["private"]["invocation_provenance"]["parent_verification_assertions_independently_reperformed_here"])

    def test_null_parent_profile_recognized_in_child(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyntheticPlan(directory)
            for event in fixture.plan["events"]:
                event["native_profile"] = None
            result = json.loads(fixture.execute())
            self.assertTrue(result["private"]["independent"][0]["profile_input_provenance"]["native_profile_supplied_from_child_root_recognition"])
            self.assertEqual(result["private"]["independent"][0]["native_root_profile"], "0.11")

    def test_nested_source_members_and_unsafe_names(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyntheticPlan(directory)
            members = fixture.plan["auditor"]["members"]
            root = Path(fixture.plan["auditor"]["directory"])
            nested = root / "public_context"
            nested.mkdir()
            (root / "invented_context_0.txt").rename(nested / "invented_context_0.txt")
            members["public_context/invented_context_0.txt"] = members.pop("invented_context_0.txt")
            result = json.loads(fixture.execute())
            self.assertEqual(result["public_aggregate"]["events"], 6)
            pin = members.pop("public_context/invented_context_0.txt")
            for bad in ("../outside", "/absolute", "public_context//invented", "public_context/./invented", "public_context/../invented", "public_context\\invented"):
                with self.subTest(bad=bad):
                    members[bad] = pin
                    with self.assertRaises(ValueError):
                        fixture.execute()
                    members.pop(bad)
            (root / "public_context").rename(root / "real_context")
            (root / "public_context").symlink_to(root / "real_context", target_is_directory=True)
            members["public_context/invented_context_0.txt"] = pin
            with self.assertRaises(ValueError):
                fixture.execute()

    def test_bad_plan_fields_authority_and_count(self):
        mutations = [lambda x: x.plan.update(extra=True), lambda x: x.auth.update(git_pushed_freeze_independently_verified=False),
                     lambda x: x.auth.update(network_requests_authorized=1), lambda x: x.plan["events"].pop(),
                     lambda x: x.plan["events"][1].update(event_id="invented0"),
                     lambda x: x.plan["events"][0].update(original_t0_us=True),
                     lambda x: x.auth.update(original_census_clock_source_sha256="8" * 64),
                     lambda x: x.plan["producer"]["members"].pop("invented_context_0.txt")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                fixture = SyntheticPlan(directory)
                mutate(fixture)
                with self.assertRaises(ValueError):
                    fixture.execute()

    def test_body_and_source_pins_paths_profile(self):
        mutations = [lambda x: x.plan["events"][0]["bodies"]["original_qml"].update(sha256="9" * 64),
                     lambda x: x.plan["events"][0]["bodies"]["original_qml"].update(bytes=h.BODY_CAP + 1),
                     lambda x: x.plan["events"][0].update(native_profile="0.10"),
                     lambda x: x.plan["producer"]["members"]["shadow.py"].update(sha256="9" * 64),
                     lambda x: x.plan["events"][0]["bodies"].update(original_qml=x.plan["events"][0]["bodies"]["fresh_qml"])]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                fixture = SyntheticPlan(directory)
                mutate(fixture)
                with self.assertRaises(ValueError):
                    fixture.execute()

    def test_source_not_executed_before_every_input_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyntheticPlan(directory)
            fixture.plan["events"][5]["bodies"]["native_scml"]["sha256"] = "9" * 64
            fixture.save()
            with patch.object(h, "EXPECTED_CODE", fixture.expected), patch.object(h, "load_frozen") as loader:
                with self.assertRaises(ValueError):
                    h.execute(str(fixture.plan_path), str(fixture.auth_path), fixture.trusted, time.monotonic() + 30)
                loader.assert_not_called()

    def test_trusted_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyntheticPlan(directory)
            fixture.save()
            fixture.trusted["plan_sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                h.execute(str(fixture.plan_path), str(fixture.auth_path), fixture.trusted, time.monotonic() + 30)

    def test_body_path_alias_cannot_satisfy_eighteen_paths(self):
        for alias in ("./", "/"):
            with self.subTest(alias=alias), tempfile.TemporaryDirectory() as directory:
                fixture = SyntheticPlan(directory)
                original = fixture.plan["events"][0]["bodies"]["original_qml"]
                substitute = copy.deepcopy(original)
                substitute["path"] = str(fixture.root) + "/" + alias + Path(original["path"]).name
                fixture.plan["events"][0]["bodies"]["fresh_qml"] = substitute
                with self.assertRaises(ValueError):
                    fixture.execute()

    def test_canonical_literal_paths_and_source_roots(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = SyntheticPlan(directory)
            path = fixture.root / "plan.json"
            path.write_bytes(b"{}")
            for suffix in ("/./plan.json", "//plan.json"):
                with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                    h.read_regular(str(fixture.root) + suffix, 10, time.monotonic() + 1)
            fixture.plan["auditor"]["directory"] += "/."
            with self.assertRaises(ValueError):
                fixture.execute()

    def test_duplicate_json_and_nonfinite(self):
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                h.json_body(body)

    def test_file_bounds_symlink_fifo_deadline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            p = root / "file"
            p.write_bytes(b"abc")
            link = root / "link"
            link.symlink_to(p)
            fifo = root / "fifo"
            os.mkfifo(fifo)
            for path, cap, deadline in ((p, 2, time.monotonic() + 1), (link, 4, time.monotonic() + 1),
                                        (fifo, 4, time.monotonic() + 1), (p, 4, time.monotonic() - 1)):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    h.read_regular(str(path), cap, deadline)

    def test_serialized_output_bound(self):
        with patch.object(h, "OUTPUT_CAP", 16):
            with self.assertRaises(ValueError):
                h.bounded_result({"text": "too much output"})

    def test_loader_executes_verified_buffers_without_source_reopen(self):
        names = ("projection", "comparison", "shadow", "independent_legacy_semantic_v3")
        saved = {name: sys.modules.pop(name) for name in names if name in sys.modules}
        try:
            producer = {"projection.py": b"value = 7", "comparison.py": b"from projection import value", "shadow.py": b"from comparison import value"}
            shadow, auditor = h.load_frozen(producer, {"semantic_audit.py": b"value = 9"}, "/invented/producer", "/invented/auditor")
            self.assertEqual((shadow.value, auditor.value), (7, 9))
            with self.assertRaises(ValueError):
                h.load_frozen(producer, {"semantic_audit.py": b"value = 9"}, "/invented/producer", "/invented/auditor")
        finally:
            for name in names:
                sys.modules.pop(name, None)
            sys.modules.update(saved)


class SupervisorTests(unittest.TestCase):
    def run_child(self, root, code, max_seconds=2, **overrides):
        root = Path(root).resolve()
        child = root / "invented_child.py"
        child.write_text("import sys, time, os, subprocess, json\nif sys.stdin.buffer.read(1) != b'G': sys.exit(1)\n" + code)
        runtime = str(Path(sys.executable).resolve())
        kwargs = dict(runtime=runtime, runtime_sha256=s.file_sha(runtime, 128 * 1024 * 1024),
            child=str(child), child_sha256=s.file_sha(str(child), 2 * 1024 * 1024),
            supervisor_sha256=s.file_sha(str(ROOT / "supervisor.py"), 2 * 1024 * 1024),
            plan=str(root / "never_read_plan"), plan_sha256="1" * 64,
            authorization=str(root / "never_read_auth"), authorization_sha256="2" * 64,
            out_dir=str(root / "exclusive_output"), max_seconds=max_seconds)
        kwargs.update(overrides)
        return s.supervise(**kwargs), kwargs

    def test_success_exclusive_and_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt, kwargs = self.run_child(directory, "print(json.dumps({'protocol_id': 'geonet_legacy_joint_invocation_v1', 'private': {'invented': True}, 'public_aggregate': {'events': 6}}))\n")
            self.assertTrue(receipt["complete"])
            root = Path(kwargs["out_dir"])
            self.assertTrue((root / "private_result.json").is_file())
            self.assertEqual(json.loads((root / "public_aggregate.json").read_bytes()), {"events": 6})
            self.assertFalse((root / "stdout.part").exists())
            with self.assertRaises(FileExistsError):
                s.supervise(**kwargs)

    def test_timeout_retains_partial_and_confirms_kill(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt, kwargs = self.run_child(directory, "print('partial', flush=True)\ntime.sleep(10)\n", max_seconds=0.4)
            self.assertFalse(receipt["complete"])
            self.assertTrue(receipt["group_termination_confirmed"])
            self.assertEqual(receipt["returncode"], -signal.SIGKILL)
            self.assertEqual((Path(kwargs["out_dir"]) / "stdout.part").read_bytes(), b"partial\n")

    def test_stdout_and_stderr_overflow(self):
        for stream in ("stdout", "stderr"):
            with self.subTest(stream=stream), tempfile.TemporaryDirectory() as directory:
                with patch.object(s, "OUTPUT_CAP", 100), patch.object(s, "STDERR_CAP", 100):
                    receipt, kwargs = self.run_child(directory, f"sys.{stream}.buffer.write(b'x' * 1000); sys.{stream}.flush(); time.sleep(10)\n")
                self.assertEqual(receipt["reason"], stream + "_overflow")
                self.assertFalse(receipt["complete"])
                self.assertTrue(receipt["group_termination_confirmed"])
                self.assertEqual((Path(kwargs["out_dir"]) / (stream + ".part")).stat().st_size, 100)

    def test_invalid_result_failed_exit_and_pin(self):
        for code in ("print('not json')\n", "sys.exit(3)\n", "print('{\"protocol_id\":\"x\",\"private\":{},\"public_aggregate\":{}}')\n",
                     "print('{\"protocol_id\":\"geonet_legacy_joint_invocation_v1\",\"private\":{},\"public_aggregate\":{},\"private\":{}}')\n"):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                receipt, kwargs = self.run_child(directory, code)
                self.assertFalse(receipt["complete"])
                self.assertFalse((Path(kwargs["out_dir"]) / "private_result.json").exists())
        with tempfile.TemporaryDirectory() as directory:
            receipt, kwargs = self.run_child(directory, "raise Exception('never launched')\n", runtime_sha256="0" * 64)
            self.assertFalse(receipt["start_gate_released"])
            self.assertIsNone(receipt["returncode"])

    def test_launch_stall_does_not_release_gate(self):
        original = subprocess.Popen
        def stalled(*args, **kwargs):
            time.sleep(0.16)
            return original(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, patch.object(s.subprocess, "Popen", side_effect=stalled):
            receipt, kwargs = self.run_child(directory, "raise Exception('gate must remain closed')\n", max_seconds=0.2)
        self.assertFalse(receipt["start_gate_released"])
        self.assertFalse(receipt["complete"])
        self.assertTrue(receipt["group_termination_confirmed"])

    def test_descendant_inherits_pipe_group_killed(self):
        original_killpg = os.killpg
        with tempfile.TemporaryDirectory() as directory, patch.object(s.os, "killpg", wraps=original_killpg) as group_signal:
            # Descendant retains the pipe. Completion must wait/expire and kill the entire session.
            receipt, kwargs = self.run_child(directory, "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'])\nsys.exit(0)\n", max_seconds=0.5)
            self.assertFalse(receipt["complete"])
            self.assertIn(receipt["reason"], ("deadline", "whole_invocation_limit_elapsed"))
            self.assertIsInstance(receipt["group_termination_confirmed"], bool)
            self.assertTrue(any(call.args[1] == signal.SIGKILL for call in group_signal.call_args_list))
            self.assertFalse((Path(kwargs["out_dir"]) / "private_result.json").exists())

    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "target"
            target.mkdir()
            (root / "exclusive_output").symlink_to(target)
            with self.assertRaises(FileExistsError):
                self.run_child(directory, "print('{}')\n")

    def test_unconfirmed_group_never_complete(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(s, "terminate_group", return_value=False):
            receipt, kwargs = self.run_child(directory, "print(json.dumps({'protocol_id':'geonet_legacy_joint_invocation_v1','private':{},'public_aggregate':{}}))\n")
            self.assertFalse(receipt["complete"])
            self.assertEqual(receipt["reason"], "group_termination_unconfirmed")
            self.assertFalse((Path(kwargs["out_dir"]) / "private_result.json").exists())

    def test_slow_final_receipt_is_incomplete_on_disk(self):
        original = s.exclusive
        class SlowReceipt:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self.stream
            def __exit__(self, *args):
                self.stream.close()
                time.sleep(0.5)
        def delayed(path):
            stream = original(path)
            return SlowReceipt(stream) if Path(path).name == "receipt.json" else stream
        with tempfile.TemporaryDirectory() as directory, patch.object(s, "exclusive", side_effect=delayed):
            receipt, kwargs = self.run_child(directory, "print(json.dumps({'protocol_id':'geonet_legacy_joint_invocation_v1','private':{},'public_aggregate':{}}))\n", max_seconds=0.4)
            saved = json.loads((Path(kwargs["out_dir"]) / "receipt.json").read_bytes())
            self.assertFalse(receipt["complete"])
            self.assertFalse(saved["complete"])
            self.assertGreaterEqual(saved["elapsed_seconds"], 0.4)


if __name__ == "__main__":
    unittest.main()

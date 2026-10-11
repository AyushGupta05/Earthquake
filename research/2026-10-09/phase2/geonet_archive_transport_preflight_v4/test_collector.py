"""Invented fake/local HTTP fixtures only. No GeoNet/AWS requests or raw reads."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import collector as c


def key(channel="A0E", day="060", year="2000", location="00", network="ZZ"):
    return f"waveforms/miniseed/{year}/{year}.{day}/TEST.{network}/{year}.{day}.TEST.{location}-{channel}.{network}.D"


def paired_keys(**kwargs):
    return [key("A0E", **kwargs), key("A0N", **kwargs)] * 4


def distinct_keys():
    return [key(f"A{i // 2}{'E' if i % 2 == 0 else 'N'}") for i in range(8)]


def document(keys=None):
    if keys is None:
        keys = paired_keys()
    return {"protocol": c.PROTOCOL, "study_id": "invented-horizontal-transport", "proposal_sha256": c.PROPOSAL_SHA256,
            "template_source_sha256": c.TEMPLATE_SOURCE_SHA256, "mapping_status": c.MAPPING_STATUS,
            "transport_hypothesis": c.TRANSPORT_HYPOTHESIS,
            "uncertainty_evidence_sha256": c.UNCERTAINTY_EVIDENCE_SHA256,
            "preregistration_sha256": "e" * 64,
            "slots": [{"slot_id": s, "key": k, "unavailable_reason": None if k else "mapping_unknown",
                       "uncertainties": list(c.SLOT_UNCERTAINTIES)}
                      for s, k in zip(c.SLOT_IDS, keys)]}


def plan(keys=None):
    return c.validate_plan(json.dumps(document(keys)).encode())


def invented_gate(p):
    root = Path(c.__file__).resolve().parent
    pin = lambda name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    return c.ActualInvocationGate(plan_sha256=p.sha256, reviewed_source_sha256=pin("collector.py"),
                                  reviewed_test_sha256=pin("test_collector.py"),
                                  reviewed_protocol_sha256=pin("PROTOCOL_v4.md"),
                                  source_manifest_sha256="a" * 64, review_receipt_sha256="b" * 64,
                                  pushed_freeze_commit="c" * 40, authorization_reference="invented assertion only",
                                  mapping_status=c.MAPPING_STATUS,
                                  uncertainty_evidence_sha256=c.UNCERTAINTY_EVIDENCE_SHA256,
                                  preregistration_sha256=p.preregistration_sha256,
                                  hypothesis_preregistered=True, uncertainty_acknowledged=True,
                                  actual_acquisition_authorized=True)


FAST = c.Limits(connection_s=0.4, first_body_s=0.65, request_s=1.0,
                start_spacing_s=0.0, no_new_after_s=2.5, transfer_stop_s=3.5,
                run_s=4.5, per_body_bytes=64, total_body_bytes=512)


@contextmanager
def server(*, body=b"invented body", status=200, content_length="auto", headers_delay=0.0,
           body_delay=0.0, slow_chunks=False, chunked=False, truncate_chunk=False, duplicate_length=False):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_GET(self):
            requests.append({"method": "GET", "path": self.path, "headers": dict(self.headers)})
            try:
                time.sleep(headers_delay)
                self.send_response(status)
                if status == 302:
                    self.send_header("Location", "http://127.0.0.1:1/never-follow")
                if chunked:
                    self.send_header("Transfer-Encoding", "chunked")
                elif content_length == "auto":
                    self.send_header("Content-Length", str(len(body)))
                elif content_length is not None:
                    self.send_header("Content-Length", str(content_length))
                if duplicate_length:
                    self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                time.sleep(body_delay)
                if chunked:
                    if truncate_chunk:
                        self.wfile.write(b"10\r\n" + body)
                    else:
                        self.wfile.write(f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n")
                elif slow_chunks:
                    for byte in body:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.2)
                else:
                    self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.close_connection = True

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", requests
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=1)


class PlanTests(unittest.TestCase):
    def test_exact_v4_roles_and_e_n_channels_are_literal(self):
        self.assertEqual(c.SLOT_IDS, ("ordinary_e", "ordinary_n", "higher_e", "higher_n",
                                    "boundary_e", "boundary_n", "final_e", "final_n"))
        self.assertEqual([slot.key.split("-")[1][:3][-1] for slot in plan().slots], list("ENENENEN"))
        for index in range(8):
            obj = document()
            wrong = "A0N" if index % 2 == 0 else "A0E"
            obj["slots"][index]["key"] = key(wrong)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "suffix"):
                c.validate_plan(json.dumps(obj).encode())
        for channel in ("A0Z", "A01", "A0e", "A0n"):
            with self.subTest(channel=channel), self.assertRaises(ValueError):
                plan([key(channel)] + paired_keys()[1:])

    def test_v3_four_slot_plan_is_incompatible_under_either_protocol(self):
        for protocol in (c.PROTOCOL, "geonet-anonymous-archive-transport-v3"):
            obj = document()
            obj["protocol"] = protocol
            obj["slots"] = obj["slots"][:4]
            with self.subTest(protocol=protocol), self.assertRaises(ValueError):
                c.validate_plan(json.dumps(obj).encode())
        obj = document()
        obj["proposal_sha256"] = "574eaf45f17987bc4e78b212481748ec1392ed08493eeeef6d13700bd485c679"
        with self.assertRaises(ValueError):
            c.validate_plan(json.dumps(obj).encode())

    def test_v4_production_study_is_fixed_and_fixture_gate_stays_closed(self):
        obj = document()
        obj["study_id"] = c.STUDY_ID
        p = c.validate_plan(json.dumps(obj).encode())
        invented_gate(p).check(p)  # Pin check only, no production call.
        with self.assertRaisesRegex(ValueError, "production V4 study"):
            invented_gate(plan()).check(plan())
        obj["study_id"] = "geonet-configured-four-transport-v3"
        with self.assertRaisesRegex(ValueError, "study identity"):
            c.validate_plan(json.dumps(obj).encode())

    def test_pair_prefix_correspondence_is_parent_assertion(self):
        # Literal suffixes are checked. No hidden event/station/day mapper exists.
        keys = paired_keys()
        keys[1] = key("B0N", day="061", location="AA", network="YY")
        self.assertEqual(plan(keys).slots[1].key, keys[1])

    def test_default_limits_exact_proposal(self):
        self.assertEqual(c.DEFAULT_LIMITS, c.Limits(10, 20, 120, 1, 660, 780, 900, 67108864, 536870912))

    def test_plan_is_immutable_and_byte_pinned(self):
        p = plan()
        self.assertEqual(p.sha256, hashlib.sha256(p.source_bytes).hexdigest())
        with self.assertRaises(Exception):
            p.study_id = "altered"

    def test_exact_eight_slots_order(self):
        for change in (lambda o: o["slots"].pop(), lambda o: o["slots"].reverse()):
            obj = document()
            change(obj)
            with self.assertRaises(ValueError):
                c.validate_plan(json.dumps(obj).encode())

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            c.validate_plan(b'{"protocol":"x","protocol":"y"}')

    def test_unknown_fields_nonfinite_and_overlong(self):
        obj = document()
        obj["retry"] = 1
        for data in (json.dumps(obj).encode(), b'{"x":NaN}', b" " * (c.MAX_PLAN_BYTES + 1)):
            with self.assertRaises(ValueError):
                c.validate_plan(data)

    def test_key_traversal_wildcard_query_and_blank_location_rejected(self):
        for bad in (key() + "?x=y", key().replace("TEST", "../TEST"), key().replace("A0E", "A*?"),
                    key().replace(".00-", ".-"), key().replace(".ZZ.D", ".YY.D")):
            with self.assertRaises(ValueError):
                plan([bad] + paired_keys()[1:])

    def test_configured_filename_order_distinguishes_network_from_location(self):
        configured = key(location="10", network="ZZ")
        self.assertEqual(plan(paired_keys(location="10", network="ZZ")).slots[0].key, configured)
        old_tutorial_order = configured.replace("TEST.10-A0E.ZZ.D", "TEST.ZZ-A0E.10.D")
        with self.assertRaises(ValueError):
            plan([old_tutorial_order] + paired_keys()[1:])

    def test_final_filename_network_repeats_directory_network_not_location(self):
        for location in ("00", "10", "AA", "ZZ"):
            with self.subTest(location=location):
                configured = key(location=location, network="ZZ")
                self.assertEqual(plan(paired_keys(location=location, network="ZZ")).slots[0].key, configured)
                for bad in (configured.replace("/TEST.ZZ/", "/TEST.YY/"),
                            configured.replace(".ZZ.D", ".YY.D")):
                    with self.assertRaises(ValueError):
                        plan([bad] + paired_keys()[1:])

    def test_configured_fields_are_literal_without_case_blank_or_location_aliases(self):
        for bad in (key(location=""), key(location="--"), key(location="  "),
                    key(location="a0"), key(network="zz"), key(channel="a00"),
                    key().replace("TEST", "test"), key(location="%30%30"),
                    key(location="0"), key(location="000")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                plan([bad] + paired_keys()[1:])

    def test_old_protocol_proposal_template_and_uncertainty_pins_rejected(self):
        old = {"protocol": "geonet-anonymous-archive-transport-v2",
               "proposal_sha256": "ae85f4f2a1431cc4b30c91fcc5caab8cc040d36c51ce744f93ef62ae34290a1a",
               "template_source_sha256": "f6449a1afade401de0e4cc79b9cca081996d6818cfd112468555f91facc9aa56",
               "uncertainty_evidence_sha256": "c4ac22937300dfc9644a0a0b4d5f735b8663234e6839704da3c211d34ce90230",
               "transport_hypothesis": "anonymous_nominal_literal_key_gets"}
        for field, value in old.items():
            obj = document()
            obj[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                c.validate_plan(json.dumps(obj).encode())

    def test_key_date_and_identity_consistency(self):
        for bad in (key(day="000"), key(day="367"), key(day="366", year="2001"), key(year="0000"),
                    key().replace("2000.060.TEST", "2001.060.TEST")):
            with self.assertRaises(ValueError):
                plan([bad] + paired_keys()[1:])
        plan(paired_keys(day="366"))

    def test_unavailable_slots_and_conflicting_reason(self):
        self.assertTrue(all(s.key is None for s in plan([None] * 8).slots))
        obj = document()
        obj["slots"][0]["unavailable_reason"] = "conflict"
        with self.assertRaises(ValueError):
            c.validate_plan(json.dumps(obj).encode())

    def test_only_unverified_literal_key_hypothesis_and_pins_are_accepted(self):
        for field, value in (("mapping_status", "verified"), ("transport_hypothesis", "waveform_coverage"),
                             ("template_source_sha256", "a" * 64), ("uncertainty_evidence_sha256", "b" * 64),
                             ("preregistration_sha256", "")):
            obj = document()
            obj[field] = value
            with self.assertRaises(ValueError):
                c.validate_plan(json.dumps(obj).encode())

    def test_day_basis_verified_mapping_and_alias_fields_are_rejected(self):
        for field, value in (("day_basis", "UTC"), ("mapping_verified", True), ("blank_location_alias", "--")):
            obj = document()
            obj[field] = value
            with self.assertRaises(ValueError):
                c.validate_plan(json.dumps(obj).encode())

    def test_each_slot_must_retain_channel_utc_location_and_endpoint_uncertainty(self):
        for bad in ([], ["channel_inventory_verified"], list(reversed(c.SLOT_UNCERTAINTIES))):
            obj = document()
            obj["slots"][2]["uncertainties"] = bad
            with self.assertRaises(ValueError):
                c.validate_plan(json.dumps(obj).encode())

    def test_actual_network_gate_fails_before_outputs_or_spawn(self):
        with tempfile.TemporaryDirectory() as td, patch.object(c, "_spawn") as spawn:
            with self.assertRaises(ValueError):
                c.collect(plan(), Path(td) / "out", None)
            spawn.assert_not_called()
            self.assertFalse((Path(td) / "out").exists())

    def test_gate_pins_source_and_plan(self):
        obj = document()
        obj["study_id"] = c.STUDY_ID
        p = c.validate_plan(json.dumps(obj).encode())
        gate = invented_gate(p)
        gate.check(p)  # Assertions only; never invoke production collection.
        for altered in (replace(gate, plan_sha256="c" * 64), replace(gate, mapping_status="verified"),
                        replace(gate, uncertainty_acknowledged=False), replace(gate, hypothesis_preregistered=False),
                        replace(gate, actual_acquisition_authorized=False),
                        replace(gate, reviewed_source_sha256="d" * 64), replace(gate, reviewed_test_sha256="d" * 64),
                        replace(gate, reviewed_protocol_sha256="d" * 64), replace(gate, source_manifest_sha256=""),
                        replace(gate, review_receipt_sha256=""), replace(gate, pushed_freeze_commit=""),
                        replace(gate, uncertainty_evidence_sha256="d" * 64),
                        replace(gate, preregistration_sha256="d" * 64)):
            with self.assertRaises(ValueError):
                altered.check(p)

    def test_verified_mapping_gate_alias_is_not_supported(self):
        with self.assertRaises(TypeError):
            replace(invented_gate(plan()), mapping_verified=True)

    def test_fixture_cannot_target_public_auth_proxy_or_other_host(self):
        for bad in (c.ARCHIVE_ENDPOINT, "http://localhost:1", "http://127.0.0.1:1/", "http://u:p@127.0.0.1:1",
                    "http://127.0.0.1:1?list-type=2", "\thttp://127.0.0.1:1", "http://127.0.0.1:0000001"):
            with self.assertRaises(ValueError):
                c.collect_fixture(plan(), "never-created", bad, limits=FAST)

    def test_fixture_requires_invented_study_and_valid_limits(self):
        obj = document()
        obj["study_id"] = "actual-data"
        with self.assertRaises(ValueError):
            c.collect_fixture(c.validate_plan(json.dumps(obj).encode()), "never-created", "http://127.0.0.1:1", limits=FAST)
        for bad in (replace(FAST, connection_s=float("nan")), replace(FAST, total_body_bytes=True),
                    replace(FAST, transfer_stop_s=FAST.run_s)):
            with self.assertRaises(ValueError):
                bad.check_fixture()

    def test_output_path_bound_rejects_before_spawn(self):
        with patch.object(c, "_spawn") as spawn:
            with self.assertRaisesRegex(ValueError, "output path byte limit"):
                c.collect_fixture(plan(), "/" + "x" * c.MAX_OUTPUT_PATH_BYTES,
                                  "http://127.0.0.1:1", limits=FAST)
            spawn.assert_not_called()


class TransportTests(unittest.TestCase):
    def test_eight_full_allowances_fit_new_aggregate_cap(self):
        with server(body=b"x" * 64) as (endpoint, requests):
            root, result = self.run_fixture(endpoint, keys=distinct_keys())
            receipt = self.receipt(root)
            self.assertTrue(result["complete"])
            self.assertTrue(result["all_slots_transport_pass"])
            self.assertEqual(receipt["attempts"], 8)
            self.assertEqual(receipt["consumed_upper"], 512)
            self.assertEqual(receipt["observed_body_bytes"], 512)
            self.assertEqual(len(requests), 8)
            self.assertEqual(len(receipt["slots"]), 8)
            self.assertTrue((root / "007.slot.private.json").is_file())

    def test_nonexact_eight_attempts_charge_full_aggregate_allowance(self):
        def uncertain(*args, **kwargs):
            return {"start": time.monotonic(), "body": None, "consumed": 0,
                    "observed_bytes": 0, "consumed_upper": args[3],
                    "consumption_exact": False, "receipt_verified": False,
                    "transport_pass": False}

        p = plan(distinct_keys())
        with tempfile.TemporaryDirectory() as td, patch.object(c, "_request", side_effect=uncertain), patch.object(c, "_emit"):
            root = Path(td) / "exclusive"
            c._controller({"plan": p.source_bytes.decode(), "fixture": True,
                           "limits": c.asdict(FAST), "endpoint": "http://127.0.0.1:1",
                           "fixture_mode": "", "gate": None, "output": str(root),
                           "begin": time.monotonic()})
            receipt = self.receipt(root)
            self.assertEqual(receipt["attempts"], 8)
            self.assertEqual(receipt["observed_body_bytes"], 0)
            self.assertEqual(receipt["consumed_upper"], 512)
            self.assertFalse(receipt["all_slots_transport_pass"])

    def run_fixture(self, endpoint, *, keys=None, limits=FAST, mode=""):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name) / "exclusive"
        result = c.collect_fixture(plan(keys), root, endpoint, limits=limits, mode=mode)
        return root, result

    def receipt(self, root):
        return c.verify_fixture_manifest(root)

    def test_complete_body_dedup_receipts_and_no_credentials(self):
        with server() as (endpoint, requests), patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "AWS_ACCESS_KEY_ID": "invented"}):
            root, result = self.run_fixture(endpoint)
            receipt = self.receipt(root)
            self.assertTrue(result["all_slots_transport_pass"])
            self.assertEqual(receipt["attempts"], 2)
            self.assertEqual(len(requests), 2)
            self.assertEqual(requests[0]["path"], "/" + key())
            self.assertNotIn("Authorization", requests[0]["headers"])
            self.assertNotIn("x-amz-request-payer", {s.lower() for s in requests[0]["headers"]})
            self.assertEqual(requests[0]["headers"]["Accept-Encoding"], "identity")
            self.assertEqual(receipt["slots"][2]["source_slot_index"], 0)
            self.assertEqual(receipt["slots"][3]["source_slot_index"], 1)
            self.assertEqual(result["manifest_sha256"], hashlib.sha256((root / "manifest.private.json").read_bytes()).hexdigest())
            self.assertEqual(result["mapping_status"], "unverified_hypothesis")
            self.assertTrue(all(value is False for value in result["claims"].values()))
            self.assertEqual(receipt["claims"], result["claims"])
            self.assertEqual(receipt["mapping_status"], "unverified_hypothesis")
            self.assertTrue(receipt["slots"][0]["worker_exit_confirmed"])
            self.assertTrue(all(row["uncertainties"] == list(c.SLOT_UNCERTAINTIES) for row in receipt["slots"]))
            self.assertEqual(result["elapsed_s"], result["returned_at"] - result["begin"])
            self.assertLessEqual(result["elapsed_s"], FAST.run_s)

    def test_maximum_plan_whitespace_survives_both_gate_envelopes(self):
        raw = json.dumps(document(), separators=(",", ":")).encode()
        raw = b"\t" * (c.MAX_PLAN_BYTES - len(raw)) + raw
        p = c.validate_plan(raw)
        self.assertEqual(len(raw), c.MAX_PLAN_BYTES)
        gate = replace(invented_gate(p), authorization_reference="a" * 255)
        with server() as (endpoint, requests), tempfile.TemporaryDirectory() as td:
            root = Path(td) / "exclusive"
            # The maximum legal path exercises envelope overhead only; actual
            # fixture output uses a short exclusive temporary directory.
            envelope = {"plan": p.source_bytes.decode(), "output": "/" + "x" * (c.MAX_OUTPUT_PATH_BYTES - 1), "begin": time.monotonic(),
                        "endpoint": endpoint, "limits": c.asdict(FAST), "fixture": True,
                        "gate": c.asdict(gate), "fixture_mode": ""}
            self.assertGreater(len(c._bytes(envelope)), 32768)
            self.assertLessEqual(len(c._bytes(envelope)), c.MAX_INTERNAL_ARGUMENT_BYTES)
            # Gate fields exercise production-sized envelopes, but fixture=True
            # is rechecked in each child and permits numeric loopback only.
            result = c._collect(p, root, endpoint, FAST, gate, True, "")
            self.assertTrue(result["all_slots_transport_pass"])
            self.assertEqual(self.receipt(root)["plan_sha256"], p.sha256)
            self.assertEqual((root / "roster.private.json").read_bytes(), raw)
            self.assertEqual(len(requests), 2)

    def test_exclusive_output_existing_and_symlink_no_requests(self):
        with server() as (endpoint, requests), tempfile.TemporaryDirectory() as td:
            existing = Path(td) / "existing"
            existing.mkdir()
            marker = existing / "unrelated"
            marker.write_text("preserve")
            for output in (existing, Path(td) / "link"):
                if output != existing:
                    output.symlink_to(existing, target_is_directory=True)
                result = c.collect_fixture(plan(), output, endpoint, limits=FAST)
                self.assertFalse(result["complete"])
            self.assertEqual(marker.read_text(), "preserve")
            self.assertEqual(requests, [])

    def test_unavailable_denominator_no_requests(self):
        with server() as (endpoint, requests):
            root, result = self.run_fixture(endpoint, keys=[None] * 8)
            receipt = self.receipt(root)
            self.assertTrue(result["complete"])
            self.assertFalse(result["all_slots_transport_pass"])
            self.assertEqual(len(receipt["slots"]), 8)
            self.assertEqual(receipt["attempts"], 0)
            self.assertEqual(requests, [])

    def test_eight_distinct_gets_no_more(self):
        with server() as (endpoint, requests):
            root, result = self.run_fixture(endpoint, keys=distinct_keys())
            self.assertTrue(result["all_slots_transport_pass"])
            self.assertEqual(self.receipt(root)["attempts"], 8)
            self.assertEqual(len(requests), 8)

    def test_spacing_uses_recorded_request_start_after_preparation_delay(self):
        starts = []

        def fake_request(*args, **kwargs):
            if not starts:
                time.sleep(0.08)  # Preparation happens before the recorded start.
            starts.append(time.monotonic())
            return {"start": starts[-1], "body": None, "consumed_upper": 0,
                    "observed_bytes": 0, "transport_pass": False}

        limits = replace(FAST, start_spacing_s=0.1)
        p = plan(distinct_keys())
        with tempfile.TemporaryDirectory() as td, patch.object(c, "_request", side_effect=fake_request), patch.object(c, "_emit"):
            c._controller({"plan": p.source_bytes.decode(), "fixture": True, "limits": c.asdict(limits),
                           "endpoint": "http://127.0.0.1:1", "fixture_mode": "", "gate": None,
                           "output": str(Path(td) / "exclusive"), "begin": time.monotonic()})
        self.assertEqual(len(starts), 8)
        self.assertTrue(all(later - earlier >= 0.1 for earlier, later in zip(starts, starts[1:])))

    def test_stale_controller_cutoff_cannot_start_a_worker(self):
        with tempfile.TemporaryDirectory() as td, patch.object(c, "_spawn") as spawn:
            result = c._request("http://127.0.0.1:1", key(), Path(td) / "invented.body", 64, FAST,
                                time.monotonic() + FAST.transfer_stop_s, "", plan(), True, None,
                                new_start_stop_at=time.monotonic() - 0.01)
            self.assertIsNone(result)
            spawn.assert_not_called()
            self.assertFalse((Path(td) / "invented.body").exists())

    def test_partial_body_is_pinned_only_after_delayed_kill_exits(self):
        workers = []
        spawn, pin = c._spawn, c._pin

        def delayed_kill_spawn(mode):
            proc = spawn(mode)
            workers.append(proc)
            kill = proc.kill

            def delayed_kill():
                timer = threading.Timer(0.05, kill)
                timer.daemon = True
                timer.start()

            proc.kill = delayed_kill
            return proc

        def pin_after_exit(path):
            self.assertIsNotNone(workers[0].poll(), "the body writer must exit before its hash is read")
            return pin(path)

        with server(body_delay=1.2) as (endpoint, requests), tempfile.TemporaryDirectory() as td:
            with patch.object(c, "_spawn", side_effect=delayed_kill_spawn), patch.object(c, "_pin", side_effect=pin_after_exit):
                row = c._request(endpoint, key(), Path(td) / "invented.body", FAST.per_body_bytes, FAST,
                                 time.monotonic() + FAST.transfer_stop_s, "", plan(), True, None)
            self.assertEqual(row["outcome"], "first_body_deadline")
            self.assertFalse(row["transport_pass"])
            self.assertEqual(len(requests), 1)

    def test_unconfirmed_worker_exit_never_pins_a_body(self):
        def unconfirmed(proc, deadline):
            c._kill(proc)
            raise RuntimeError("invented unconfirmed termination")

        with server() as (endpoint, requests), tempfile.TemporaryDirectory() as td:
            with patch.object(c, "_terminate_and_confirm", side_effect=unconfirmed), patch.object(c, "_pin") as pin:
                with self.assertRaisesRegex(RuntimeError, "unconfirmed"):
                    c._request(endpoint, key(), Path(td) / "invented.body", FAST.per_body_bytes, FAST,
                               time.monotonic() + FAST.transfer_stop_s, "", plan(), True, None)
                pin.assert_not_called()
            self.assertTrue((Path(td) / "invented.body").exists())

    def test_redirect_not_followed_error_body_counted(self):
        with server(status=302, body=b"redirect error") as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            receipt = self.receipt(root)
            self.assertFalse(result["all_slots_transport_pass"])
            self.assertEqual(len(requests), 2)
            self.assertEqual(receipt["observed_body_bytes"], 28)
            self.assertEqual(receipt["slots"][0]["status"], "attempted")
            self.assertEqual(receipt["slots"][0]["outcome"], "body_complete")

    def test_error_and_partial_declared_body_retained(self):
        with server(status=403, body=b"denied") as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            self.assertFalse(result["all_slots_transport_pass"])
            self.assertEqual(self.receipt(root)["observed_body_bytes"], 12)
            self.assertEqual(len(requests), 2)
        with server(body=b"partial", content_length=20) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            receipt = self.receipt(root)
            self.assertFalse(result["all_slots_transport_pass"])
            self.assertEqual(receipt["slots"][0]["outcome"], "incomplete_body")
            self.assertEqual(receipt["observed_body_bytes"], 14)

    def test_declared_large_rejected_without_body_reads(self):
        with server(body=b"x" * 100, content_length=100) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            row = self.receipt(root)["slots"][0]
            self.assertEqual(row["outcome"], "declared_size_rejected")
            self.assertEqual(row["observed_bytes"], 0)
            self.assertFalse(result["all_slots_transport_pass"])

    def test_missing_length_stream_cap_and_exact_boundary_conservative(self):
        for body in (b"x" * 100, b"x" * 64):
            with server(body=body, content_length=None) as (endpoint, requests):
                root, result = self.run_fixture(endpoint)
                row = self.receipt(root)["slots"][0]
                self.assertEqual(row["observed_bytes"], 64)
                self.assertEqual(row["outcome"], "body_cap_boundary")
                self.assertFalse(result["all_slots_transport_pass"])

    def test_exact_declared_length_at_cap_passes(self):
        with server(body=b"x" * 64) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            self.assertTrue(result["all_slots_transport_pass"])
            self.assertEqual(self.receipt(root)["consumed_upper"], 128)

    def test_false_short_length_never_consumes_extra_wire_bytes(self):
        with server(body=b"x" * 100, content_length=5) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            row = self.receipt(root)["slots"][0]
            self.assertEqual(row["observed_bytes"], 5)
            self.assertEqual(row["consumed_upper"], 5)
            # A transport pass is not a claim about content or server truth.
            self.assertTrue(result["all_slots_transport_pass"])

    def test_duplicate_length_rejected(self):
        with server(duplicate_length=True) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            self.assertEqual(self.receipt(root)["slots"][0]["outcome"], "invalid_content_length")
            self.assertFalse(result["all_slots_transport_pass"])

    def test_chunked_complete_and_truncated_partial(self):
        with server(body=b"chunk body", chunked=True) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            self.assertTrue(result["all_slots_transport_pass"])
        with server(body=b"short", chunked=True, truncate_chunk=True) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            receipt = self.receipt(root)
            self.assertFalse(result["all_slots_transport_pass"])
            self.assertEqual(receipt["observed_body_bytes"], 10)

    def test_first_body_deadline_includes_headers_wait(self):
        with server(headers_delay=1.2) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            row = self.receipt(root)["slots"][0]
            self.assertEqual(row["outcome"], "first_body_deadline")
            self.assertLess(row["end"] - row["start"], 1.0)
            self.assertFalse(row["consumption_exact"])
            self.assertEqual(row["consumed_upper"], FAST.per_body_bytes)

    def test_body_after_headers_also_first_byte_deadline(self):
        with server(body_delay=1.2) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            row = self.receipt(root)["slots"][0]
            self.assertIsNotNone(row["headers_at"])
            self.assertEqual(row["outcome"], "first_body_deadline")

    def test_slow_body_complete_deadline_retains_partial(self):
        with server(body=b"abcdefghijk", slow_chunks=True) as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            row = self.receipt(root)["slots"][0]
            self.assertEqual(row["outcome"], "complete_deadline")
            self.assertGreater(row["observed_bytes"], 0)
            self.assertLess(row["observed_bytes"], 11)
            self.assertFalse(result["all_slots_transport_pass"])

    def test_blocked_connection_parent_process_deadline(self):
        root, result = self.run_fixture("http://127.0.0.1:1", mode="block_connection")
        row = self.receipt(root)["slots"][0]
        self.assertEqual(row["outcome"], "connection_deadline")
        self.assertLess(row["end"] - row["start"], 0.8)

    def test_total_cap_retains_unattempted_slots(self):
        with server(body=b"x" * 100, content_length=None) as (endpoint, requests):
            root, result = self.run_fixture(endpoint, keys=distinct_keys(),
                                            limits=replace(FAST, total_body_bytes=70))
            receipt = self.receipt(root)
            self.assertEqual(receipt["consumed_upper"], 70)
            self.assertEqual(receipt["observed_body_bytes"], 70)
            self.assertEqual(receipt["attempts"], 2)
            self.assertFalse(result["complete"])
            self.assertEqual(receipt["slots"][2]["reason"], "total_body_cap")
            self.assertEqual(len(requests), 2)

    def test_request_start_and_transfer_cutoff(self):
        limits = replace(FAST, connection_s=0.4, first_body_s=0.5, request_s=1.0,
                         no_new_after_s=0.2, transfer_stop_s=0.7, run_s=1.5)
        with server(body=b"abcdefghijk", slow_chunks=True) as (endpoint, requests):
            root, result = self.run_fixture(endpoint, keys=distinct_keys(), limits=limits)
            receipt = self.receipt(root)
            self.assertEqual(receipt["slots"][0]["outcome"], "transfer_deadline")
            self.assertEqual(receipt["slots"][1]["reason"], "new_request_deadline")
            self.assertEqual(len(requests), 1)

    def test_outer_finalization_watchdog_retains_initial_journals(self):
        limits = replace(FAST, no_new_after_s=0.3, transfer_stop_s=0.7, run_s=1.2)
        with server() as (endpoint, requests):
            start = time.monotonic()
            root, result = self.run_fixture(endpoint, limits=limits, mode="block_finalization")
            self.assertEqual(result["result"], "run_deadline")
            self.assertFalse(result["complete"])
            self.assertLess(time.monotonic() - start, 1.7)
            self.assertTrue((root / "roster.private.json").is_file())
            self.assertTrue((root / "initial.private.json").is_file())
            self.assertTrue((root / "007.slot.private.json").is_file())
            self.assertFalse((root / "receipt.private.json").exists())

    def test_tampered_fixture_body_receipt_rejected(self):
        with server() as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            (root / "000.body.private").write_bytes(b"tampered invented bytes")
            with self.assertRaises(ValueError):
                self.receipt(root)

    def test_missing_manifest_member_rejected(self):
        with server() as (endpoint, requests):
            root, result = self.run_fixture(endpoint)
            path = root / "manifest.private.json"
            obj = json.loads(path.read_text())
            obj["members"].pop()
            path.write_text(json.dumps(obj))
            with self.assertRaises(ValueError):
                self.receipt(root)

    def test_forged_plan_object_rejected_before_collection(self):
        with tempfile.TemporaryDirectory() as td:
            p = replace(plan(), slots=plan([None] * 8).slots)
            with self.assertRaises(ValueError):
                c.collect_fixture(p, Path(td) / "out", "http://127.0.0.1:1", limits=FAST)


if __name__ == "__main__":
    unittest.main()

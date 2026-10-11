#!/usr/bin/env python3
"""Read-only private replay, disabled absent a separate hash-bound parent handoff."""
import time
STARTED = time.monotonic()
import argparse
from collections import Counter
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import signal
import sys
import independent as check

BASE = Path(__file__).resolve().parent
WORK = BASE.parent.resolve()
MIB = 1048576
AUDITOR_FILES = ("audit.py", "independent.py", "test_independent.py", "PROTOCOL.md", "specification.json")
CENSUS_NAMES = ("groups.json", "manifest.json", "outcomes.json", "query_order.json",
                "requests.json", "rows.json", "summary.json")
BULK_NAMES = ("local_runs/planned_inputs_final.json", "local_runs/parent_receipt_final.json",
              "local_runs/collection_final/manifest.json", "local_runs/collection_final/outcomes.json",
              "local_runs/collection_final/summary.json", "local_runs/collection_final/requests.json")
PRODUCER_FIELDS = ("processing_files", "reviewed_dependencies", "runtime", "input_receipt_sha256",
                   "bulk_input_pins", "bulk_replay_sha256", "event_order_sha256", "specification")


class Deadline(RuntimeError):
    """Resource interruption must not be caught as unsupported metadata."""


def safe_path(path):
    result = Path(path).absolute()
    check.require(result.is_relative_to(WORK), "path_outside_work")
    current = result
    while current != WORK:
        check.require(not current.is_symlink(), "symlink_input_or_ancestor")
        current = current.parent
    resolved = result.resolve()
    check.require(resolved.is_relative_to(WORK), "resolved_path_outside_work")
    return resolved


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            check.require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def constant(_):
        raise check.AuditError("nonfinite_json")
    try:
        return json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise check.AuditError("json_encoding_or_syntax") from None


class Reader:
    def __init__(self):
        self.total = 0
        self.cache = {}

    def read(self, path, pin=None, cap=32 * MIB):
        path = safe_path(path)
        if path not in self.cache:
            check.require(path.is_file() and path.stat().st_size <= cap, "input_size_or_type")
            with path.open("rb") as stream:
                data = stream.read(cap + 1)
            check.require(len(data) <= cap, "input_grew")
            self.total += len(data)
            check.require(self.total <= 256 * MIB, "aggregate_read_cap")
            self.cache[path] = data
        body = self.cache[path]
        check.require(len(body) <= cap, "cached_input_cap")
        if pin is not None:
            check.require(check.size_hash(body) == pin, "input_pin_mismatch")
        return body

    def object(self, entry, cap=32 * MIB):
        return decode(self.read(entry["path"], entry["pin"], cap))


def verify_bindings(reader, receipt, plan):
    check.require(receipt.get("version") == "paired-independent-private-handoff-v1" and
                  all(receipt.get(k) is True for k in ("authorized_private_read", "producer_review_clean",
                       "auditor_review_clean", "freeze_pushed", "inputs_preserved")), "private_handoff_required")
    check.require(re.fullmatch(r"[0-9a-f]{40}", receipt.get("git_freeze_commit", "")), "freeze_commit_shape")
    expected_files = {}
    for name in AUDITOR_FILES:
        expected_files[name] = check.digest(reader.read(BASE / name, cap=4 * MIB))
    check.require(receipt["auditor_processing_files"] == expected_files, "auditor_source_binding")
    runtime = receipt["auditor_runtime"]
    check.require(runtime["python_version"] == sys.version and
                  runtime["cache_tag"] == sys.implementation.cache_tag, "auditor_runtime_binding")
    binary = Path(sys.executable).resolve()
    # Executable is outside WORK; it is read solely to verify its frozen hash.
    check.require(binary.is_file() and binary.stat().st_size <= 128 * MIB, "runtime_binary_cap")
    with binary.open("rb") as stream:
        body = stream.read(128 * MIB + 1)
    check.require(len(body) <= 128 * MIB and check.digest(body) == runtime["binary_sha256"],
                  "auditor_runtime_binary")
    check.require(plan["processing_files"] == receipt["producer_processing_files"], "producer_source_binding")
    check.require(plan["runtime"] == receipt["producer_runtime"] and
                  plan["reviewed_dependencies"] == receipt["producer_reviewed_dependencies"],
                  "producer_dependency_runtime_binding")
    public = receipt["producer_public_files"]
    check.require(set(public) == set(plan["processing_files"]), "producer_public_member_set")
    for name, entry in public.items():
        check.require(check.digest(reader.read(entry["path"], entry["pin"], 4 * MIB)) ==
                      plan["processing_files"][name], "producer_public_source_pin")


def selection_replay(reader, receipt):
    files = receipt["files"]
    plan = reader.object(files["paired_plan"], 4 * MIB)
    verify_bindings(reader, receipt, plan)
    selection_input = reader.object(files["selection_input"], 2 * MIB)
    check.require(selection_input["version"] == "geonet-paired-selection-inputs-v1" and
                  selection_input["completed_bulk_independently_replayed"] is True and
                  selection_input["bulk_gate_passed"] is True, "selection_input_gate")
    check.require(plan["input_receipt_sha256"] == files["selection_input"]["pin"]["sha256"] and
                  safe_path(plan["input_receipt_path"]) == safe_path(files["selection_input"]["path"]),
                  "selection_input_plan_binding")
    bulk = [reader.object(files["bulk_" + str(i)]) for i in range(6)]
    bulk_plan, bulk_parent, bulk_manifest, bulk_outcomes, bulk_summary, bulk_requests = bulk
    expected_bulk = {name: files["bulk_" + str(i)]["pin"]["sha256"] for i, name in enumerate(BULK_NAMES)}
    check.require(selection_input["bulk_files"] == expected_bulk == plan["bulk_input_pins"], "bulk_input_pins")
    check.require(expected_bulk[BULK_NAMES[0]] == plan["specification"]["bulk_plan_sha256"], "bulk_plan_spec_pin")
    replay = reader.object(files["bulk_replay"], 2 * MIB)
    check.require(replay.get("all_checks_pass") is True and
                  selection_input["bulk_independent_replay_sha256"] == files["bulk_replay"]["pin"]["sha256"] ==
                  plan["bulk_replay_sha256"] and
                  safe_path(selection_input["bulk_independent_replay_path"]) == safe_path(files["bulk_replay"]["path"]),
                  "bulk_replay_binding")
    check.require(bulk_manifest.get("completed") is True and not bulk_manifest.get("artifact_pins_incomplete") and
                  bulk_summary.get("completed") is True and bulk_summary.get("metadata_missingness_gate_pass") is True,
                  "bulk_completion")
    check.require(bulk_manifest["plan_sha256"] == expected_bulk[BULK_NAMES[0]] == bulk_parent["plan_sha256"] and
                  bulk_manifest["parent_receipt_sha256"] == expected_bulk[BULK_NAMES[1]], "bulk_manifest_bindings")
    for i, name in ((3, "outcomes.json"), (4, "summary.json"), (5, "requests.json")):
        check.require(bulk_manifest["files"][name] == files["bulk_" + str(i)]["pin"], "bulk_member_binding")
    check.require(len(bulk_requests) == 346, "bulk_request_denominator")
    check.require(set(bulk_plan["input_pins"]) == set(CENSUS_NAMES), "census_member_set")
    census = {}
    for name in CENSUS_NAMES:
        entry = files["census_" + name]
        census[name] = reader.object(entry)
        check.require(entry["pin"]["sha256"] == bulk_plan["input_pins"][name], "census_input_binding")
    check.require(census["manifest.json"].get("completed") is True and
                  len(census["outcomes.json"]) == 149, "census_completion_denominator")
    check.require(bulk_plan["input_pins"]["groups.json"] == plan["specification"]["census_groups_sha256"],
                  "census_frame_spec_pin")
    check.original_eligibility(bulk_plan["rows"], census["groups.json"], census["rows.json"],
                               census["query_order.json"])
    outcomes = {x["event_id"]: x for x in bulk_outcomes}
    check.require(len(outcomes) == len(bulk_outcomes) == 495, "bulk_unique_outcomes")
    for row in bulk_plan["rows"]:
        if row["source"] == "reused_tail":
            check.require(outcomes[row["event_id"]]["base"] == census["outcomes.json"][row["event_id"]],
                          "original_census_base_changed")
    selected = check.selected_plan(bulk_plan["rows"], outcomes, plan)
    check.require(set(receipt["original_bodies"]) == {x["event_id"] for x in selected},
                  "original_body_member_set")
    originals = {}
    for event in plan["events"]:
        eid, original = event["event_id"], event["original_qml"]
        attempts = [x for x in census["requests.json"] if x["file"] == eid + ".xml"]
        check.require(len(attempts) == 1 and attempts[0]["status"] == "ok" and attempts[0]["http_status"] == 200,
                      "original_request_identity")
        attempt = attempts[0]
        pin = census["manifest.json"]["files"]["raw/" + eid + ".xml"]
        check.require(pin == original["pin"] == {"bytes": attempt["bytes"], "sha256": attempt["sha256"]},
                      "original_request_member_binding")
        supplied = receipt["original_bodies"][eid]
        check.require(supplied["pin"] == pin and safe_path(supplied["path"]) == safe_path(original["path"]),
                      "original_body_path_binding")
        originals[eid] = reader.read(supplied["path"], pin, 4 * MIB)
    return plan, selected, originals


def core_record_check(core, record):
    check.require(record["mapped_event_id"] == core["mapped_event_id"] and
                  record["preferred_origin_id"] == core["preferred_origin_id"], "xml_saved_identity")
    fields_verified, fields_unavailable = 0, 0
    for key, value in core["origin"].items():
        saved = record["origin"][key]
        if saved is None:
            # A conservative producer null (including normalization underflow)
            # is unavailable evidence, never an asserted zero or an agreement.
            fields_unavailable += 1
            continue
        if key != "time_us" and saved is not None:
            try:
                saved = Decimal(saved)
            except (ValueError, TypeError, ArithmeticError):
                raise check.AuditError("saved_geometry_domain") from None
        check.require(saved == value, "xml_saved_origin")
        fields_verified += 1
    check.require(record["event_creation"] == core["revision"]["event"] and
                  record["origin"]["creation"] == core["revision"]["origin"], "xml_saved_revision")
    return fields_verified, fields_unavailable


def artifacts_replay(reader, receipt, plan, selected, originals):
    check.require(receipt.get("collection_completed_preserved_normal_exit") is True, "completed_handoff_required")
    files = receipt["files"]
    parent = reader.object(files["paired_parent"], MIB)
    check.require(parent["version"] == "geonet-paired-parent-receipt-v1" and all(parent.get(k) is True for k in (
        "acquisition_authorized", "code_only_review_clean", "private_selection_independently_replayed", "freeze_pushed")),
        "producer_parent_gate")
    check.require(parent["plan_sha256"] == files["paired_plan"]["pin"]["sha256"] and
                  re.fullmatch(r"[0-9a-f]{40}", parent["git_freeze_commit"]) and
                  re.fullmatch(r"[0-9a-f]{64}", parent["private_selection_replay_sha256"]), "producer_parent_binding")
    check.require(all(parent[k] == plan[k] for k in PRODUCER_FIELDS), "producer_parent_field_binding")
    manifest = reader.object(files["paired_manifest"], 2 * MIB)
    check.require(manifest["plan_sha256"] == parent["plan_sha256"] and
                  manifest["parent_receipt_sha256"] == files["paired_parent"]["pin"]["sha256"], "paired_manifest_binding")
    for key in ("processing_files", "reviewed_dependencies", "runtime", "input_receipt_sha256"):
        check.require(manifest[key] == plan[key], "manifest_processing_binding")
    root = safe_path(receipt["collection_root"])
    expected = {"event_outcomes.json", "summary.json", "requests.json", "native_worker.log"} | {
        "raw/" + x["file"] for x in plan["requests"]}
    check.require(set(manifest["files"]) == expected, "collection_member_set")
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    check.require(actual == expected | {"manifest.json"}, "collection_extra_or_missing_members")
    member_bytes = {}
    for name, pin in manifest["files"].items():
        cap = 4 * MIB if name.startswith("raw/") or name == "native_worker.log" else 32 * MIB
        member_bytes[name] = reader.read(root / name, pin, cap)
    check.require(safe_path(files["paired_manifest"]["path"]) == root / "manifest.json", "collection_manifest_path")
    ledger = decode(member_bytes["requests.json"])
    transport = check.transport_replay(plan, manifest, ledger,
                                      {x["file"]: member_bytes["raw/" + x["file"]] for x in plan["requests"]})
    results = decode(member_bytes["event_outcomes.json"])
    statuses = check.slots_and_clocks(selected, results)
    summary = decode(member_bytes["summary.json"])
    check.require(summary["completed"] is True and summary["source_event_denominator"] == 6 and
                  summary["representation_denominator"] == 18 and
                  summary["representation_status_counts"] == statuses and
                  summary["atomic_database_revision_verified"] is False and summary["physical_pick_validated"] is False,
                  "summary_denominators_or_claims")
    available, unavailable, conflicts, geometry_verified, geometry_unavailable = 0, 0, 0, 0, 0
    by_request = {(x["event_id"], x["kind"]): (x, a) for x, a in zip(plan["requests"], ledger)}
    for event, result in zip(plan["events"], results):
        cores = {}
        for slot in check.SLOTS:
            record = result["representations"][slot]
            check.require(record["status"] not in ("attempting", "interrupted", "not_attempted"),
                          "completed_slot_not_terminal")
            if slot == "original_qml":
                check.require(record["status"] != "transport_failed", "original_successful_retrieval_status")
                body, kind = originals[event["event_id"]], "qml"
            else:
                kind = "qml" if slot == "fresh_qml" else "scml"
                request, attempt = by_request[(event["event_id"], kind)]
                succeeded = attempt["status"] == "ok" and attempt.get("http_status") == 200
                check.require((record["status"] == "transport_failed") == (not succeeded), "slot_transport_status")
                body = member_bytes["raw/" + request["file"]]
                if not succeeded:
                    unavailable += 1
                    continue
            try:
                core = check.xml_core(body, event["event_id"], kind)
            except check.AuditError:
                unavailable += 1
                continue
            cores[slot] = core
            if record["status"] == "ok":
                verified, unknown = core_record_check(core, record)
                geometry_verified += verified
                geometry_unavailable += unknown
                available += 1
            else:
                unavailable += 1
        for name, left, right in (("catalogue_drift", "original_qml", "fresh_qml"),
                                  ("representation_difference", "fresh_qml", "native_scml")):
            comparison = result[name]
            check.require(comparison.get("atomic_database_revision_verified", False) is False and
                          comparison.get("converter_bug_proved", False) is False, "unsupported_scientific_claim")
            parsed_pair = all(result["representations"][s]["status"] == "ok" for s in (left, right))
            if parsed_pair and any(result["representations"][s]["origin"][field] is None
                                   for s in (left, right) for field in ("time_us", "latitude", "longitude", "depth_m")):
                check.require(comparison.get("same_record_content") is None and
                              comparison.get("content_matched_resolution_candidate_count", 0) == 0 and
                              comparison.get("paired_recorded_revision_resolution_count", 0) == 0,
                              "missing_origin_promoted")
            if left in cores and right in cores and all(result["representations"][s]["status"] == "ok"
                                                        for s in (left, right)):
                revision = check.revision_relation(cores[left], cores[right])
                check.require(comparison["revision_evidence"] == revision, "raw_revision_relation")
                if revision == "conflict":
                    conflicts += 1
                    check.require(comparison.get("content_matched_resolution_candidate_count", 0) == 0 and
                                  comparison.get("paired_recorded_revision_resolution_count", 0) == 0,
                                  "revision_conflict_promoted")
    return {**transport, "representation_status_counts": statuses,
            "raw_core_verified_parsed_slots": available, "raw_core_unverified_slots": unavailable,
            "raw_origin_fields_verified": geometry_verified, "raw_origin_fields_unavailable": geometry_unavailable,
            "raw_recorded_revision_conflict_pairs": conflicts,
            "clock_verification_basis": "Saved accepted-pick subsets, eligibility not independently certified",
            "complete_arrival_or_conversion_semantics_verified": False,
            "recovery_counts_independently_verified": False}


def run(receipt_path, mode):
    reader = Reader()
    receipt = decode(reader.read(receipt_path, cap=4 * MIB))
    # Gate before opening any explicitly named private inputs.
    check.require(receipt.get("version") == "paired-independent-private-handoff-v1" and
                  all(receipt.get(k) is True for k in ("authorized_private_read", "producer_review_clean",
                       "auditor_review_clean", "freeze_pushed", "inputs_preserved")), "private_read_disabled")
    plan, selected, originals = selection_replay(reader, receipt)
    report = {"version": "paired-independent-replay-v1", "all_scoped_checks_pass": True,
              "mode": mode, "event_denominator": 6, "request_denominator": 12,
              "representation_denominator": 18, "selection_and_original_hashes_verified": True,
              "original_projection_digest_semantics_verified": False,
              "complete_arrival_or_conversion_semantics_verified": False,
              "operational_or_physical_clock_verified": False,
              "actual_recovery_or_model_improvement_verified": False}
    if mode == "artifacts":
        report.update(artifacts_replay(reader, receipt, plan, selected, originals))
    report["private_handoff_sha256"] = check.digest(reader.read(receipt_path, cap=4 * MIB))
    report["input_bytes_read"] = reader.total
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("selection", "artifacts"))
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    def deadline(_signum, _frame):
        raise Deadline("auditor_deadline")
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, max(.001, STARTED + 300 - time.monotonic()))
    output = safe_path(args.output)
    check.require(output.is_relative_to(BASE / "local_runs"), "output_outside_auditor_local_runs")
    output.parent.mkdir(parents=True, exist_ok=True)
    check.require(not output.exists(), "output_exists")
    try:
        report = run(args.handoff, args.mode)
        code = 0
    except (Deadline, check.AuditError, KeyError, TypeError, ValueError, OSError, MemoryError) as exc:
        report = {"version": "paired-independent-replay-v1", "all_scoped_checks_pass": False,
                  "mode": args.mode, "event_denominator": 6, "representation_denominator": 18,
                  "complete_arrival_or_conversion_semantics_verified": False,
                  "failure": str(exc) if isinstance(exc, (Deadline, check.AuditError)) else type(exc).__name__}
        code = 2
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())

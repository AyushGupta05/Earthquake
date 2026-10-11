#!/usr/bin/env python3
"""Bounded private metadata diagnostic; collect requires the parent's pushed freeze."""
import time
PROCESS_STARTED = time.monotonic()
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import signal
import ssl
import subprocess
import sys
import urllib.error
import comparison
import dependencies as deps
import projection
import selection

BASE = Path(__file__).resolve().parent
BULK = BASE.parent / "geonet_bulk_metadata"
CENSUS = BASE.parent / "geonet_tail_census/local_runs/recovery_20261010"
MIB = 1024 * 1024
OUTER, RESERVE = 360, 10
FILES = ("paired.py", "dependencies.py", "projection.py", "comparison.py",
         "selection.py", "test_paired.py", "PROTOCOL_v1.md", "specification.json",
         "reviewed_dependencies.json", "public_transform_pins.json")
BULK_MEMBERS = ("local_runs/planned_inputs_final.json", "local_runs/parent_receipt_final.json",
                "local_runs/collection_final/manifest.json", "local_runs/collection_final/outcomes.json",
                "local_runs/collection_final/summary.json", "local_runs/collection_final/requests.json")
INPUT_MEMBERS = {"groups.json", "manifest.json", "outcomes.json", "query_order.json",
                 "requests.json", "rows.json", "summary.json"}


def load(path, cap=32 * MIB):
    return json.loads(deps.read(path, cap))


def dump(path, value):
    temporary = path.with_name(path.name + ".temporary." + str(os.getpid()))
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def local(path):
    root, path = BASE / "local_runs", Path(path)
    if root.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(root) or path.resolve() == root:
        raise ValueError("private nonsymlink local_runs required")
    return path.resolve()


def pin(path, cap=32 * MIB):
    body = deps.read(path, cap)
    return {"bytes": len(body), "sha256": deps.sha(body)}


def sources():
    return {name: deps.sha(deps.read(BASE / name, 4 * MIB)) for name in FILES}


def specification():
    spec = load(BASE / "specification.json", MIB)
    expected = {"events": 6, "requests": 12, "body_bytes": 48 * MIB,
                "per_body_bytes": 4 * MIB, "outer_seconds": OUTER,
                "finalization_reserve_seconds": RESERVE, "request_seconds": 20,
                "start_spacing_seconds": 1, "retries": 0, "redirects": 0,
                "replacements": 0, "resume": False, "AWS": 0, "fits": 0}
    if spec["caps"] != expected or spec["horizons_seconds"] != [1, 3, 5]:
        raise ValueError("frozen specification changed")
    return spec


def input_objects(input_path):
    body = deps.read(local(input_path), 2 * MIB)
    receipt = json.loads(body)
    if (receipt.get("version") != "geonet-paired-selection-inputs-v1" or
            receipt.get("completed_bulk_independently_replayed") is not True or
            receipt.get("bulk_gate_passed") is not True):
        raise ValueError("parent verified completed bulk required")
    pins = receipt.get("bulk_files", {})
    if set(pins) != set(BULK_MEMBERS) or pins[BULK_MEMBERS[0]] != specification()["bulk_plan_sha256"]:
        raise ValueError("exact frozen bulk input members required")
    objects = {}
    for name, digest in pins.items():
        data = deps.read(BULK / name, 32 * MIB)
        if deps.sha(data) != digest:
            raise ValueError("bulk input changed")
        objects[name] = json.loads(data)
    replay_path = Path(receipt["bulk_independent_replay_path"])
    if replay_path.is_symlink() or not replay_path.resolve().is_relative_to(BULK.resolve()):
        raise ValueError("bulk replay escaped original directory")
    replay = deps.read(replay_path, 2 * MIB)
    if deps.sha(replay) != receipt["bulk_independent_replay_sha256"] or json.loads(replay).get("all_checks_pass") is not True:
        raise ValueError("completed independent replay required")
    plan, parent, manifest, outcomes, summary, ledger = (objects[name] for name in BULK_MEMBERS)
    root = BULK / "local_runs/collection_final"
    if (manifest.get("completed") is not True or manifest.get("artifact_pins_incomplete") or
            (root / "outer_interruption.json").exists() or summary.get("completed") is not True or
            summary.get("metadata_missingness_gate_pass") is not True or
            manifest.get("plan_sha256") != pins[BULK_MEMBERS[0]] or
            manifest.get("parent_receipt_sha256") != pins[BULK_MEMBERS[1]] or
            parent.get("plan_sha256") != pins[BULK_MEMBERS[0]]):
        raise ValueError("bulk completion/provenance mismatch")
    if set(plan["input_pins"]) != INPUT_MEMBERS:
        raise ValueError("original census member set changed")
    for name, digest in plan["input_pins"].items():
        if deps.sha(deps.read(CENSUS / name, 32 * MIB)) != digest:
            raise ValueError("original census member changed")
    if plan["input_pins"]["groups.json"] != specification()["census_groups_sha256"]:
        raise ValueError("original CMT frame changed")
    for name in ("outcomes.json", "summary.json", "requests.json"):
        if pin(root / name) != manifest["files"][name]:
            raise ValueError("completed bulk member changed")
    if (len(outcomes) != 495 or len({row["event_id"] for row in outcomes}) != 495 or
            {row["event_id"] for row in outcomes} != {row["event_id"] for row in plan["rows"]} or
            len(ledger) != 346):
        raise ValueError("bulk denominator changed")
    return receipt, body, plan, {row["event_id"]: row for row in outcomes}


def original_body(event_id):
    manifest, requests = load(CENSUS / "manifest.json"), load(CENSUS / "requests.json")
    entries = [entry for entry in requests if entry.get("file") == event_id + ".xml"]
    if len(entries) != 1:
        raise ValueError("original body request identity is ambiguous")
    entry = entries[0]
    name = "raw/" + entry["file"]
    if entry.get("status") != "ok" or entry.get("http_status") != 200:
        raise ValueError("original successful body required")
    # The old manifest contains member pins, never infer a body from an event row.
    expected = manifest["files"][name]
    path = CENSUS / name
    body = deps.read(path, 4 * MIB)
    actual = {"bytes": len(body), "sha256": deps.sha(body)}
    if actual != expected or actual != {"bytes": entry["bytes"], "sha256": entry["sha256"]}:
        raise ValueError("original request/member/body mismatch")
    return path, actual, body


def make_plan(input_path):
    spec, runtime = specification(), deps.runtime()
    receipt, input_body, bulk, outcomes = input_objects(input_path)
    events = selection.choose(bulk["rows"], outcomes)
    for event in events:
        frozen_nz = outcomes[event["event_id"]]["base"].get("nz")
        frozen_time = frozen_nz.get("t0_utc") if frozen_nz is not None else None
        event["preserved_original_T0_us"] = projection.stamp_us(frozen_time) if frozen_time else None
        path, expected, body = original_body(event["event_id"])
        original = projection.parse(body, event["event_id"], "qml")
        event["original_qml"] = {"path": str(path), "pin": expected,
                                 "projection_sha256": projection.digest(original),
                                 "projection_status": original["status"]}
    return {"version": "geonet-paired-plan-v1", "input_receipt_path": str(local(input_path)),
            "input_receipt_sha256": deps.sha(input_body), "bulk_input_pins": receipt["bulk_files"],
            "bulk_replay_sha256": receipt["bulk_independent_replay_sha256"], "runtime": runtime,
            "processing_files": sources(), "reviewed_dependencies": deps.pins(), "specification": spec,
            "event_denominator": 6, "event_order_sha256": selection.list_hash(row["event_id"] for row in events),
            "events": events, "requests": selection.requests(events), "new_request_count": 12}


def validate(plan_path, receipt_path):
    body = deps.read(local(plan_path), 4 * MIB)
    plan = json.loads(body)
    receipt_body = deps.read(local(receipt_path), MIB)
    receipt = json.loads(receipt_body)
    if (receipt.get("version") != "geonet-paired-parent-receipt-v1" or
            receipt.get("acquisition_authorized") is not True or receipt.get("code_only_review_clean") is not True or
            receipt.get("private_selection_independently_replayed") is not True or
            receipt.get("freeze_pushed") is not True or
            not re.fullmatch("[0-9a-f]{40}", receipt.get("git_freeze_commit", "")) or
            not re.fullmatch("[0-9a-f]{64}", receipt.get("private_selection_replay_sha256", ""))):
        raise ValueError("parent pushed freeze/independent-selection/review authorization required")
    fields = ("processing_files", "reviewed_dependencies", "runtime", "input_receipt_sha256",
              "bulk_input_pins", "bulk_replay_sha256", "event_order_sha256", "specification")
    if (receipt.get("plan_sha256") != deps.sha(body) or
            any(receipt.get(name) != plan.get(name) for name in fields) or
            plan != make_plan(plan["input_receipt_path"])):
        raise ValueError("frozen plan/source/input/runtime changed")
    return plan, deps.sha(body), deps.sha(receipt_body)


def unavailable(event_id, status, reason):
    return {"event_id": event_id, "status": status, "reason": reason,
            "denominators": None, "nz": None, "all_network": None, "accepted_picks": None}


def initial_results(plan):
    results = []
    for event in plan["events"]:
        expected = event["original_qml"]
        body = deps.read(expected["path"], 4 * MIB)
        if {"bytes": len(body), "sha256": deps.sha(body)} != expected["pin"]:
            raise ValueError("original body changed before initialization")
        original = projection.parse(body, event["event_id"], "qml")
        if projection.digest(original) != expected["projection_sha256"]:
            raise ValueError("original projection changed")
        unknown = unavailable(event["event_id"], "not_attempted", "frozen request not yet attempted")
        result = comparison.event_result(original, unknown, unknown, event["preserved_original_T0_us"])
        result.update(role=event["role"], Mw_band=event["Mw_band"], event_id=event["event_id"])
        results.append(result)
    return results


def checkpoint(out, results, completed=False):
    dump(out / "event_outcomes.json", results)
    dump(out / "summary.json", {**comparison.aggregate(results), "completed": completed})


def worker(plan, out, plan_sha, receipt_sha, deadline, fetch_factory=None):
    lib, transport = deps.module("downloader"), deps.module("transport")
    results = initial_results(plan)
    lookup = {row["event_id"]: row for row in results}
    raw = out / "raw"
    raw.mkdir()
    checkpoint(out, results)
    factory = fetch_factory or transport.factory(lib, deadline - OUTER)
    fetch = factory(raw, max_seconds=max(0, deadline - RESERVE - time.monotonic()),
                    max_bytes=48 * MIB, max_requests=12, request_alarm=True)
    state = {"completed": False, "plan_sha256": plan_sha, "parent_receipt_sha256": receipt_sha,
             "event_denominator": 6, "representation_denominator": 18,
             "processing_files": plan["processing_files"], "reviewed_dependencies": plan["reviewed_dependencies"],
             "runtime": plan["runtime"], "input_receipt_sha256": plan["input_receipt_sha256"],
             "outer_deadline_monotonic": deadline, "caps": plan["specification"]["caps"]}
    code = 2

    def terminate(signum, frame):
        raise lib.LimitReached("parent cancellation")

    previous_term = signal.signal(signal.SIGTERM, terminate)
    try:
        for request in plan["requests"]:
            fetch.check()
            row = lookup[request["event_id"]]
            key = "fresh_qml" if request["kind"] == "qml" else "native_scml"
            row["representations"][key] = unavailable(request["event_id"], "attempting", "request started")
            checkpoint(out, results)
            try:
                body = fetch.fetch(request["url"], request["file"], 4 * MIB)
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, ssl.SSLError) as exc:
                result = unavailable(request["event_id"], "transport_failed", type(exc).__name__)
            except ValueError as exc:
                if str(exc) not in ("HTTP status is not 200", "Content-Length mismatch") and not str(exc).startswith(
                        "invalid literal for int() with base 10:"):
                    raise
                result = unavailable(request["event_id"], "transport_failed", type(exc).__name__)
            else:
                # Local I/O, resource bounds, provenance and unexpected parser
                # errors reach the outer incomplete-stop path, never a retry.
                result = projection.parse(body, request["event_id"], request["kind"])
            snapshots = row["representations"]
            snapshots[key] = result
            updated = comparison.event_result(snapshots["original_qml"], snapshots["fresh_qml"], snapshots["native_scml"],
                                              row["preserved_original_T0_us"])
            row.update(updated)
            checkpoint(out, results)
        if time.monotonic() >= deadline - RESERVE or fetch.bytes > 48 * MIB or len(fetch.log) != 12:
            raise ValueError("twelve frozen attempt denominator changed")
        state["completed"], code = True, 0
    except BaseException as exc:
        state.update(stop_type=type(exc).__name__, stop_reason=str(exc))
        results = reconcile_results(plan, results, fetch.log)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        dump(out / "requests.json", fetch.log)
        checkpoint(out, results, state["completed"])
        state.update(request_attempts=len(fetch.log), response_body_bytes=fetch.bytes,
                     worker_elapsed_seconds=time.monotonic() - PROCESS_STARTED)
        state["files"] = {str(path.relative_to(out)): pin(path)
                          for path in sorted(out.rglob("*")) if path.is_file() and
                          path.name not in ("manifest.json", "native_worker.log")}
        dump(out / "manifest.json", state)
        signal.signal(signal.SIGTERM, previous_term)
    return code


class Deadline(RuntimeError):
    pass


def soft_stop(signum, frame):
    raise Deadline("paired parent deadline/cancellation")


def hard_watchdog(deadline, process):
    def stop(signum, frame):
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        os._exit(2)
    signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))


def stop_child(process, deadline, graceful):
    if process is None or process.poll() is not None:
        return
    if graceful:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=max(.001, min(5, deadline - time.monotonic())))
            return
        except subprocess.TimeoutExpired:
            pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=max(.001, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        os._exit(2)


def reconcile_results(plan, results, attempts):
    """Terminalize unknown slots after child exit; do not parse or retry bodies."""
    requests = {request["file"]: request for request in plan["requests"]}
    if len(requests) != len(plan["requests"]):
        raise ValueError("ambiguous frozen request names")
    by_slot = {}
    for attempt in attempts:
        request = requests.get(attempt["file"])
        if request is None or attempt.get("url") != request["url"]:
            raise ValueError("recovered attempt differs from frozen query")
        slot = (request["event_id"], request["kind"])
        if slot in by_slot:
            raise ValueError("duplicate recovered attempt")
        by_slot[slot] = attempt
    if (len(results) != len(plan["events"]) or len({row["event_id"] for row in results}) != len(results) or
            {row["event_id"] for row in results} != {row["event_id"] for row in plan["events"]}):
        raise ValueError("recovery lost source event denominator")
    for row in results:
        for key, kind in (("fresh_qml", "qml"), ("native_scml", "scml")):
            record = row["representations"][key]
            attempt = by_slot.get((row["event_id"], kind))
            if record["status"] in ("attempting", "interrupted") or (record["status"] == "not_attempted" and attempt is not None):
                status = "interrupted" if attempt is not None else "not_attempted"
                reason = "child stopped after durable attempt" if attempt is not None else "child stopped before durable attempt"
                row["representations"][key] = unavailable(row["event_id"], status, reason)
        snapshots = row["representations"]
        row.update(comparison.event_result(snapshots["original_qml"], snapshots["fresh_qml"], snapshots["native_scml"],
                                           row["preserved_original_T0_us"]))
    return results


def collect(plan_path, receipt_path, out):
    process, plan, reserved, code = None, None, False, None
    gate_read, gate_write = None, None
    deadline = PROCESS_STARTED + OUTER
    previous_term, previous_alarm = signal.getsignal(signal.SIGTERM), signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGTERM, soft_stop)
        signal.signal(signal.SIGALRM, soft_stop)
        signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - RESERVE - time.monotonic()))
        plan, plan_sha, receipt_sha = validate(plan_path, receipt_path)
        out = local(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.mkdir()
        reserved = True
        checkpoint(out, initial_results(plan))
        dump(out / "manifest.json", {"completed": False, "initial_checkpoint": True,
                                    "event_denominator": 6, "representation_denominator": 18,
                                    "plan_sha256": plan_sha, "parent_receipt_sha256": receipt_sha})
        with (out / "native_worker.log").open("xb") as log:
            gate_read, gate_write = os.pipe()
            pending = []
            launch_signals = (signal.SIGTERM, signal.SIGALRM, signal.SIGINT)
            launch_handlers = {number: signal.getsignal(number) for number in launch_signals}

            def defer_launch_cancellation(signum, frame):
                pending.append(signum)
                # The worker waits for the pipe gate. A hard exit closes the
                # parent's write end even if Popen has not returned a handle.
                hard_watchdog(deadline, process)

            # A raising handler inside Popen can lose an already-created child
            # before the returned handle is assigned. Retain that handle first.
            try:
                for number in launch_signals:
                    signal.signal(number, defer_launch_cancellation)
                process = subprocess.Popen([sys.executable, "-B", str(BASE / "paired.py"), "_worker",
                                            "--plan", str(local(plan_path)), "--receipt", str(local(receipt_path)),
                                            "--output", str(out), "--deadline", str(deadline),
                                            "--gate-fd", str(gate_read)],
                                           stdout=log, stderr=log, start_new_session=True, pass_fds=(gate_read,))
            finally:
                for number, handler in launch_handlers.items():
                    signal.signal(number, handler)
            os.close(gate_read)
            gate_read = None
            if pending or time.monotonic() >= deadline - RESERVE:
                soft_stop(pending[0] if pending else signal.SIGALRM, None)
            os.write(gate_write, b"1")
            os.close(gate_write)
            gate_write = None
            code = process.wait(timeout=max(.001, deadline - RESERVE - time.monotonic()))
        state = load(out / "manifest.json", 2 * MIB)
        if state.get("initial_checkpoint") or code != 0 or state.get("completed") is not True:
            raise RuntimeError("worker incomplete: " + str(code))
        state.update(worker_exit_code=code, outer_elapsed_seconds=time.monotonic() - PROCESS_STARTED)
        state["files"]["native_worker.log"] = pin(out / "native_worker.log", 4 * MIB)
        dump(out / "manifest.json", state)
        return 0
    except BaseException as exc:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        hard_watchdog(deadline, process)
        if reserved:
            dump(out / "outer_interruption.json", {"completed": False, "stop_type": type(exc).__name__,
                                                   "event_denominator": 6, "representation_denominator": 18,
                                                   "plan_sha256": plan_sha, "parent_receipt_sha256": receipt_sha})
        stop_child(process, deadline, True)
        if reserved:
            state = load(out / "manifest.json", 2 * MIB)
            state.update(completed=False, files={}, artifact_pins_incomplete=True, worker_exit_code=code)
            dump(out / "manifest.json", state)
            attempts = []
            if (out / "requests.json").exists():
                attempts = load(out / "requests.json", 2 * MIB)
                for entry in attempts:
                    sidecar = out / "raw" / (entry["file"] + ".received")
                    if sidecar.exists():
                        body = deps.read(sidecar, 4 * MIB)
                        entry.update(bytes=len(body), sha256=deps.sha(body), status="interrupted")
                        dump(out / "requests.json", attempts)
                        sidecar.replace(out / "raw" / entry["file"])
                dump(out / "requests.json", attempts)
            if (out / "event_outcomes.json").exists():
                checkpoint(out, reconcile_results(plan, load(out / "event_outcomes.json"), attempts), False)
        raise
    finally:
        for descriptor in (gate_read, gate_write):
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
        if process is not None and process.poll() is None:
            hard_watchdog(deadline, process)
            stop_child(process, deadline, False)
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGTERM, previous_term)
        signal.signal(signal.SIGALRM, previous_alarm)


def receive_launch_gate(descriptor, deadline):
    """Fail closed before reading private inputs or acquiring any metadata."""
    hard_watchdog(deadline, None)
    try:
        if not 0 < deadline - RESERVE - time.monotonic() <= OUTER - RESERVE:
            raise Deadline("worker launch deadline elapsed")
        if os.read(descriptor, 1) != b"1":
            raise Deadline("worker launch gate closed")
        if not 0 < deadline - RESERVE - time.monotonic() <= OUTER - RESERVE:
            raise Deadline("worker launch deadline elapsed")
    finally:
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--plan", type=Path, required=True)
    for name in ("collect", "_worker"):
        p = sub.add_parser(name)
        p.add_argument("--plan", type=Path, required=True)
        p.add_argument("--receipt", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True)
        if name == "_worker":
            p.add_argument("--deadline", type=float, required=True)
            p.add_argument("--gate-fd", type=int, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        plan = make_plan(args.inputs)
        destination = local(args.plan)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x") as target:
            target.write(json.dumps(plan, indent=2, sort_keys=True, allow_nan=False) + "\n")
        return 0
    if args.mode == "collect":
        return collect(args.plan, args.receipt, args.output)
    receive_launch_gate(args.gate_fd, args.deadline)
    plan, plan_sha, receipt_sha = validate(args.plan, args.receipt)
    out = local(args.output)
    if (not 0 < args.deadline - time.monotonic() <= OUTER or
            not (out / "manifest.json").exists() or
            not load(out / "manifest.json").get("initial_checkpoint") or (out / "raw").exists()):
        raise ValueError("fresh parent reservation/shared deadline required")
    return worker(plan, out, plan_sha, receipt_sha, args.deadline)


if __name__ == "__main__":
    sys.exit(main())

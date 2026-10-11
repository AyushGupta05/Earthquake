"""Bounded anonymous daily-object transport; importing never performs I/O.

Production use needs a separately authorized, pinned parent handoff. Fixture
entry points admit only invented plans and loopback HTTP, never public data.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import select
import signal
import ssl
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

PROTOCOL = "geonet-anonymous-archive-transport-v4"
PROPOSAL_SHA256 = "6283180bd493d2846e08b866ade3910afe2896ceea27ad3b309e21460b7d1a0a"
TEMPLATE_SOURCE_SHA256 = "3194fa79e8993b99f0514239d7735dc4461b9d31aefd031b2f43e725612b6412"
UNCERTAINTY_EVIDENCE_SHA256 = "d3f826d1b1e45c59fdd5760dc3b5e9f0a8e954a60c2ec7ee628e80031462ec74"
MAPPING_STATUS = "unverified_hypothesis"
TRANSPORT_HYPOTHESIS = "anonymous_official_configured_literal_key_gets"
SLOT_UNCERTAINTIES = ("utc_filename_partition", "channel_key_identity",
                      "location_key_encoding", "endpoint_key_correspondence")
ARCHIVE_ENDPOINT = "https://geonet-open-data.s3.ap-southeast-2.amazonaws.com"
STUDY_ID = "geonet-configured-eight-horizontal-transport-v4"
SLOT_IDS = ("ordinary_e", "ordinary_n", "higher_e", "higher_n",
            "boundary_e", "boundary_n", "final_e", "final_n")
MAX_PLAN_BYTES = 16384
MAX_INTERNAL_ARGUMENT_BYTES = 65536
MAX_OUTPUT_PATH_BYTES = 4096
CHUNK_BYTES = 16384
MAX_EVENT_BYTES = 512
SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
KEY = re.compile(
    r"waveforms/miniseed/([0-9]{4})/([0-9]{4})\.([0-9]{3})/"
    r"([A-Z0-9]{3,4})\.([A-Z0-9]{2})/"
    r"([0-9]{4})\.([0-9]{3})\.([A-Z0-9]{3,4})\.([A-Z0-9]{2})-"
    r"([A-Z0-9]{3})\.([A-Z0-9]{2})\.D\Z", re.ASCII)


def _json(data: bytes):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out
    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def _text(value, pattern: str, label: str) -> str:
    if type(value) is not str or re.fullmatch(pattern, value, re.ASCII) is None:
        raise ValueError(label)
    return value


def _fields(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("unexpected/missing fields")


@dataclass(frozen=True)
class Slot:
    slot_id: str
    key: str | None
    unavailable_reason: str | None
    uncertainties: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    study_id: str
    slots: tuple[Slot, ...]
    source_bytes: bytes
    sha256: str
    mapping_status: str
    uncertainty_evidence_sha256: str
    preregistration_sha256: str


def validate_plan(data: bytes) -> Plan:
    """Pure validation. No actual inputs are opened or mapped by this module."""
    if type(data) is not bytes or not 0 < len(data) <= MAX_PLAN_BYTES:
        raise ValueError("plan byte limit")
    obj = _json(data)
    _fields(obj, ("protocol", "study_id", "proposal_sha256", "template_source_sha256",
                  "mapping_status", "transport_hypothesis", "uncertainty_evidence_sha256",
                  "preregistration_sha256", "slots"))
    if obj["protocol"] != PROTOCOL or obj["proposal_sha256"] != PROPOSAL_SHA256:
        raise ValueError("protocol/proposal pin")
    study = _text(obj["study_id"], r"[a-z][a-z0-9-]{0,63}", "study id")
    if study != STUDY_ID and not study.startswith("invented-"):
        raise ValueError("fixed V4 study identity or invented fixture required")
    if obj["template_source_sha256"] != TEMPLATE_SOURCE_SHA256:
        raise ValueError("pinned nominal template source required")
    if obj["mapping_status"] != MAPPING_STATUS or obj["transport_hypothesis"] != TRANSPORT_HYPOTHESIS:
        raise ValueError("literal-key unverified transport hypothesis required")
    if obj["uncertainty_evidence_sha256"] != UNCERTAINTY_EVIDENCE_SHA256:
        raise ValueError("pinned mapping uncertainty evidence required")
    _text(obj["preregistration_sha256"], r"[0-9a-f]{64}", "parent preregistration pin")
    if type(obj["slots"]) is not list or len(obj["slots"]) != 8:
        raise ValueError("exact eight-slot roster required")
    slots = []
    for index, item in enumerate(obj["slots"]):
        _fields(item, ("slot_id", "key", "unavailable_reason", "uncertainties"))
        if item["slot_id"] != SLOT_IDS[index]:
            raise ValueError("fixed slot order")
        if item["uncertainties"] != list(SLOT_UNCERTAINTIES):
            raise ValueError("per-slot mapping/channel uncertainties must be retained")
        key, reason = item["key"], item["unavailable_reason"]
        if key is None:
            _text(reason, r"[a-z][a-z0-9_]{0,63}", "unavailable reason")
        else:
            if type(key) is not str or reason is not None:
                raise ValueError("requestable slot fields")
            match = KEY.fullmatch(key)
            if match is None:
                raise ValueError("nominal documented key required")
            # Official GEONET reader config: STATION.LOCATION-CHANNEL.NETWORK.
            # The final filename network repeats the directory network; location
            # is independent and is never inferred or normalized from that field.
            y1, y2, doy1, site1, net1, y3, doy2, site2, _, channel, net2 = match.groups()
            if channel[-1] != ("E" if index % 2 == 0 else "N"):
                raise ValueError("literal horizontal channel suffix must match role")
            if (y1, doy1, site1, net1) != (y2, doy2, site2, net2) or y1 != y3:
                raise ValueError("inconsistent key fields")
            year, day = int(y1), int(doy1)
            if not 1 <= year <= 9999 or not 1 <= day <= (dt.date(year, 12, 31).timetuple().tm_yday):
                raise ValueError("invalid year/day")
        slots.append(Slot(item["slot_id"], key, reason, SLOT_UNCERTAINTIES))
    return Plan(study, tuple(slots), data, hashlib.sha256(data).hexdigest(),
                MAPPING_STATUS, UNCERTAINTY_EVIDENCE_SHA256, obj["preregistration_sha256"])


@dataclass(frozen=True)
class Limits:
    connection_s: float = 10.0
    first_body_s: float = 20.0
    request_s: float = 120.0
    start_spacing_s: float = 1.0
    no_new_after_s: float = 660.0
    transfer_stop_s: float = 780.0
    run_s: float = 900.0
    per_body_bytes: int = 67108864
    total_body_bytes: int = 536870912

    def check_fixture(self):
        nums = (self.connection_s, self.first_body_s, self.request_s,
                self.no_new_after_s, self.transfer_stop_s, self.run_s)
        if any(type(v) not in (int, float) or not 0 < v < float("inf") for v in nums):
            raise ValueError("invalid fixture deadline")
        if not (self.connection_s <= self.first_body_s <= self.request_s <= self.run_s
                and self.no_new_after_s < self.transfer_stop_s < self.run_s):
            raise ValueError("fixture deadline ordering")
        if type(self.start_spacing_s) not in (int, float) or not 0 <= self.start_spacing_s < self.run_s:
            raise ValueError("fixture spacing")
        if any(type(v) is not int or v <= 0 for v in (self.per_body_bytes, self.total_body_bytes)):
            raise ValueError("fixture byte cap")


DEFAULT_LIMITS = Limits()


def _claims():
    return {"semantic_mapping_verified": False, "utc_filename_basis_verified": False,
            "channel_key_identity_verified": False,
            "location_key_encoding_verified": False, "endpoint_mapping_verified": False,
            "waveform_coverage_verified": False, "failed96_repaired": False}


@dataclass(frozen=True)
class ActualInvocationGate:
    """Parent assertions, not verification of human authorization or Git state."""
    plan_sha256: str
    reviewed_source_sha256: str
    reviewed_test_sha256: str
    reviewed_protocol_sha256: str
    source_manifest_sha256: str
    review_receipt_sha256: str
    pushed_freeze_commit: str
    authorization_reference: str
    mapping_status: str
    uncertainty_evidence_sha256: str
    preregistration_sha256: str
    hypothesis_preregistered: bool
    uncertainty_acknowledged: bool
    actual_acquisition_authorized: bool

    def check(self, plan: Plan):
        if plan.study_id != STUDY_ID:
            raise ValueError("production V4 study identity required")
        if self.plan_sha256 != plan.sha256:
            raise ValueError("parent plan pin")
        for value in (self.reviewed_source_sha256, self.reviewed_test_sha256,
                      self.reviewed_protocol_sha256, self.source_manifest_sha256,
                      self.review_receipt_sha256, self.preregistration_sha256):
            if type(value) is not str or SHA.fullmatch(value) is None:
                raise ValueError("parent source/test/protocol/manifest/review/preregistration pin")
        root = Path(__file__).resolve().parent
        for name, expected in (("collector.py", self.reviewed_source_sha256),
                               ("test_collector.py", self.reviewed_test_sha256),
                               ("PROTOCOL_v4.md", self.reviewed_protocol_sha256)):
            if expected != hashlib.sha256((root / name).read_bytes()).hexdigest():
                raise ValueError("source/test/protocol bytes differ from reviewed pin")
        _text(self.pushed_freeze_commit, r"[0-9a-f]{40}", "pushed freeze assertion")
        _text(self.authorization_reference, r"[A-Za-z0-9][A-Za-z0-9 ._:/-]{0,255}", "authorization assertion")
        if self.mapping_status != MAPPING_STATUS or plan.mapping_status != MAPPING_STATUS:
            raise ValueError("mapping must remain an unverified hypothesis")
        if (self.uncertainty_evidence_sha256 != UNCERTAINTY_EVIDENCE_SHA256
                or self.uncertainty_evidence_sha256 != plan.uncertainty_evidence_sha256
                or self.preregistration_sha256 != plan.preregistration_sha256):
            raise ValueError("parent uncertainty/preregistration pins differ from plan")
        if (self.hypothesis_preregistered is not True or self.uncertainty_acknowledged is not True
                or self.actual_acquisition_authorized is not True):
            raise ValueError("separate acknowledged hypothesis and acquisition authority required")


def _write_new(path: Path, data: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(data)
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise OSError("short write")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _pin(path: Path):
    count, digest = 0, hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            count += len(chunk)
            digest.update(chunk)
    return {"name": path.name, "bytes": count, "sha256": digest.hexdigest()}


def _emit(value):
    data = _bytes(value)
    if len(data) > MAX_EVENT_BYTES:
        raise ValueError("internal event limit")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _worker(arg):
    """Private subprocess. Bodies stay in its exclusive private output file."""
    plan = validate_plan(arg["plan"].encode("utf-8"))
    limits = Limits(**arg["limits"])
    if arg["fixture"]:
        _fixture_check(plan, arg["endpoint"], limits, arg["fixture_mode"])
    else:
        ActualInvocationGate(**arg["gate"]).check(plan)
        if limits != DEFAULT_LIMITS or arg["endpoint"] != ARCHIVE_ENDPOINT or arg["fixture_mode"]:
            raise ValueError("production worker gate")
    if arg["key"] not in [s.key for s in plan.slots if s.key is not None]:
        raise ValueError("worker key not in immutable plan")
    if type(arg["allowance"]) is not int or not 0 < arg["allowance"] <= min(limits.per_body_bytes, limits.total_body_bytes):
        raise ValueError("worker allowance")
    endpoint, key, destination, allowance, fixture_mode = (
        arg["endpoint"], arg["key"], arg["destination"], arg["allowance"], arg["fixture_mode"])
    if fixture_mode == "block_connection":
        time.sleep(60)
        return
    parsed = urlsplit(endpoint)
    conn = None
    fd = None
    count, written, digest = 0, 0, hashlib.sha256()
    status, declared, first = None, None, None
    outcome = "worker_error"
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        kwargs = {"timeout": limits.request_s}
        if parsed.scheme == "https":
            kwargs["context"] = ssl.create_default_context()
        conn = cls(parsed.hostname, parsed.port, **kwargs)
        conn.connect()  # DNS/connect/TLS are separately killed by the parent.
        _emit({"event": "connected", "at": time.monotonic()})
        conn.putrequest("GET", "/" + key, skip_accept_encoding=True)
        conn.putheader("Accept-Encoding", "identity")
        conn.putheader("Connection", "close")
        conn.endheaders()
        response = conn.getresponse()
        status = response.status
        lengths = [value for name, value in response.getheaders() if name.lower() == "content-length"]
        if len(lengths) > 1 or (lengths and re.fullmatch(r"[0-9]{1,20}", lengths[0]) is None):
            outcome = "invalid_content_length"
        else:
            declared = int(lengths[0]) if lengths else None
            _emit({"event": "headers", "at": time.monotonic(), "status": status, "declared": declared})
            if declared is not None and declared > allowance:
                outcome = "declared_size_rejected"
            else:
                outcome = "body_cap_boundary"
                while count < allowance:
                    try:
                        chunk = response.read1(min(CHUNK_BYTES, allowance - count))
                    except http.client.IncompleteRead as exc:
                        chunk = exc.partial
                        outcome = "incomplete_body"
                        # read1's supplied bound limits returned/partial bytes.
                        if len(chunk) > allowance - count:
                            raise ValueError("stdlib read bound violated")
                        if not chunk:
                            break
                        terminal_partial = True
                    else:
                        terminal_partial = False
                    if not chunk:
                        outcome = "body_complete"
                        break
                    count += len(chunk)
                    if first is None:
                        first = time.monotonic()
                        _emit({"event": "first_body", "at": first})
                    view = memoryview(chunk)
                    while view:
                        n = os.write(fd, view)
                        if n <= 0:
                            raise OSError("short body write")
                        digest.update(view[:n])
                        written += n
                        view = view[n:]
                    if terminal_partial:
                        break
                    if response.length == 0:
                        outcome = "body_complete"
                        break
                if outcome == "body_complete" and declared is not None and count != declared:
                    outcome = "incomplete_body"
                if outcome == "body_complete" and count == 0:
                    outcome = "empty_body"
        os.fsync(fd)
    except Exception as exc:
        # Do not disclose a URL/key, credential, exception text or raw header.
        outcome = "worker_error_" + type(exc).__name__[:40]
    finally:
        if conn is not None:
            conn.close()
        if fd is not None:
            os.close(fd)
    _emit({"event": "done", "at": time.monotonic(), "outcome": outcome,
           "status": status, "declared": declared, "consumed": count,
           "written": written, "sha256": digest.hexdigest(), "first": first})


def _environment():
    # Bypass proxy, netrc, AWS credentials/config, Python path and user site.
    return {"PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "utf-8"}


def _spawn(mode: str):
    proc = subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), mode],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            env=_environment(), start_new_session=(mode == "--controller"))
    return proc


def _kill(proc, group=False):
    try:
        if group:
            # The controller may have exited while a worker still owns the group.
            os.killpg(proc.pid, signal.SIGKILL)
        elif proc.poll() is None:
            proc.kill()
    except ProcessLookupError:
        pass


def _reap(proc):
    # Reaping is asynchronous after a kill; no cleanup wait extends a hard cap.
    if proc.poll() is None:
        threading.Thread(target=proc.wait, daemon=True).start()


def _terminate_and_confirm(proc, deadline):
    """Do not pin a body until its only writer has stopped.

    Cleanup may consume the remaining finalization budget, but cannot extend the
    outer run watchdog. Unconfirmed termination leaves accounting incomplete.
    """
    _kill(proc)
    try:
        proc.wait(timeout=max(0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        raise RuntimeError("worker termination unconfirmed") from None


def _request(endpoint, key, path, allowance, limits, stop_at, fixture_mode, plan, fixture, gate,
             *, new_start_stop_at=None):
    start = time.monotonic()
    if new_start_stop_at is not None and start >= new_start_stop_at:
        return None  # Preparation delay must not move a launch beyond the cutoff.
    result = {"start": start, "connected_at": None, "headers_at": None, "first_body_at": None,
              "end": None, "http_status": None, "declared": None,
              "outcome": "worker_exit", "consumed": None}
    arg = {"endpoint": endpoint, "key": key, "destination": str(path),
           "allowance": allowance, "fixture_mode": fixture_mode,
           "plan": plan.source_bytes.decode("utf-8"), "fixture": fixture,
           "limits": asdict(limits), "gate": gate}
    payload = _bytes(arg)
    if len(payload) > MAX_INTERNAL_ARGUMENT_BYTES:
        raise ValueError("worker argument limit")
    proc = _spawn("--worker")
    # Nonblocking pipe writes are included in the connection deadline.
    input_fd = proc.stdin.fileno()
    os.set_blocking(input_fd, False)
    fd = proc.stdout.fileno()
    os.set_blocking(fd, False)
    buffer = b""
    connected, first, done = False, False, None
    sent = 0
    try:
        while True:
            now = time.monotonic()
            bound = min(start + limits.request_s, stop_at,
                        start + (limits.first_body_s if connected else limits.connection_s))
            if first:
                bound = min(start + limits.request_s, stop_at)
            if now >= bound:
                result["outcome"] = ("transfer_deadline" if bound == stop_at else
                                     "complete_deadline" if first else
                                     "first_body_deadline" if connected else "connection_deadline")
                break
            readable, writable, _ = select.select([fd], [input_fd] if sent < len(payload) else [], [], min(0.05, bound - now))
            if time.monotonic() >= bound:
                continue
            if writable:
                sent += os.write(input_fd, payload[sent:])
                if sent == len(payload):
                    proc.stdin.close()
                    proc.stdin = None
            if readable:
                part = os.read(fd, 4096)
                if not part:
                    break
                buffer += part
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if len(line) + 1 > MAX_EVENT_BYTES:
                        raise ValueError("event overflow")
                    event = _json(line)
                    kind = event["event"]
                    if kind == "connected":
                        connected = True
                        result["connected_at"] = event["at"]
                    elif kind == "headers":
                        result.update(headers_at=event["at"], http_status=event["status"], declared=event["declared"])
                    elif kind == "first_body":
                        first = True
                        result["first_body_at"] = event["at"]
                    elif kind == "done":
                        done = event
                        result.update(outcome=event["outcome"], consumed=event["consumed"],
                                      http_status=event["status"], declared=event["declared"])
                if len(buffer) > MAX_EVENT_BYTES:
                    raise ValueError("event overflow")
                if done is not None:
                    break
    finally:
        try:
            _terminate_and_confirm(proc, stop_at + limits.run_s - limits.transfer_stop_s)
        finally:
            if proc.stdin is not None:
                proc.stdin.close()
            proc.stdout.close()
            # A pending termination must not block beyond the run watchdog.
            _reap(proc)
    result["end"] = time.monotonic()
    pin = _pin(path) if path.exists() else None
    observed = pin["bytes"] if pin else 0
    if observed > allowance:
        raise ValueError("body cap invariant")
    verified = (done is not None and pin is not None and done["written"] == observed
                and done["sha256"] == pin["sha256"] and observed == done["consumed"])
    if done is not None and not verified:
        result["outcome"] = "body_receipt_mismatch"
    consumed_upper = done["consumed"] if verified else allowance
    if not observed <= consumed_upper <= allowance:
        raise ValueError("consumption cap invariant")
    within = (result["end"] <= start + limits.request_s and result["end"] <= stop_at
              and result["connected_at"] is not None
              and result["connected_at"] <= start + limits.connection_s
              and result["first_body_at"] is not None
              and result["first_body_at"] <= start + limits.first_body_s)
    result.update(body=pin, observed_bytes=observed, consumed_upper=consumed_upper,
                  consumption_exact=verified, receipt_verified=verified,
                  worker_exit_confirmed=True,
                  transport_pass=(verified and result["outcome"] == "body_complete"
                                  and result["http_status"] == 200 and within))
    return result


def _controller(arg):
    plan = validate_plan(arg["plan"].encode("utf-8"))
    fixture = arg["fixture"]
    limits = Limits(**arg["limits"])
    endpoint = arg["endpoint"]
    if fixture:
        _fixture_check(plan, endpoint, limits, arg["fixture_mode"])
    else:
        ActualInvocationGate(**arg["gate"]).check(plan)
        if limits != DEFAULT_LIMITS or endpoint != ARCHIVE_ENDPOINT or arg["fixture_mode"]:
            raise ValueError("production limits/endpoint fixed")
    root = Path(arg["output"])
    root.mkdir(mode=0o700)  # Exclusive: an existing directory is a hard failure.
    begin = arg["begin"]
    if type(begin) not in (int, float) or not time.monotonic() - limits.run_s <= begin <= time.monotonic():
        raise ValueError("supervisor monotonic start")
    _write_new(root / "roster.private.json", plan.source_bytes)
    initial = {"protocol": PROTOCOL, "study_id": plan.study_id, "plan_sha256": plan.sha256,
               "complete": False, "fixture": fixture, "limits": asdict(limits),
               "mapping_status": MAPPING_STATUS, "transport_hypothesis": TRANSPORT_HYPOTHESIS,
               "template_source_sha256": TEMPLATE_SOURCE_SHA256,
               "uncertainty_evidence_sha256": plan.uncertainty_evidence_sha256,
               "preregistration_sha256": plan.preregistration_sha256,
               "claims": _claims(), "run_begin": begin,
               "request_policy": {"method": "GET", "endpoint": endpoint, "redirects": False,
                                  "retries": False, "head": False, "listing": False, "auth": False,
                                  "requester_payer": False, "fallback": False},
               "slots": [{"slot_id": s.slot_id, "status": "unavailable" if s.key is None else "unattempted",
                          "uncertainties": list(s.uncertainties)}
                         for s in plan.slots]}
    _write_new(root / "initial.private.json", _bytes(initial))
    records, seen, charged, attempts, last_start = [], {}, 0, 0, None
    members = [_pin(root / "roster.private.json"), _pin(root / "initial.private.json")]
    for index, slot in enumerate(plan.slots):
        record = {"slot_id": slot.slot_id, "key": slot.key, "uncertainties": list(slot.uncertainties)}
        if slot.key is None:
            record.update(status="unavailable", reason=slot.unavailable_reason)
        elif slot.key in seen:
            record.update(status="shared_object", source_slot_index=seen[slot.key],
                          request_index=records[seen[slot.key]]["request_index"],
                          transport_pass=records[seen[slot.key]].get("transport_pass", False))
        else:
            if last_start is not None:
                remaining = last_start + limits.start_spacing_s - time.monotonic()
                if remaining > 0:
                    time.sleep(min(remaining, max(0, begin + limits.no_new_after_s - time.monotonic())))
            allowance = min(limits.per_body_bytes, limits.total_body_bytes - charged)
            if time.monotonic() >= begin + limits.no_new_after_s:
                record.update(status="unattempted", reason="new_request_deadline")
            elif allowance <= 0:
                record.update(status="unattempted", reason="total_body_cap")
            else:
                path = root / f"{index:03d}.body.private"
                result = _request(endpoint, slot.key, path, allowance, limits,
                                  begin + limits.transfer_stop_s, arg["fixture_mode"], plan, fixture, arg["gate"],
                                  new_start_stop_at=begin + limits.no_new_after_s)
                if result is None:
                    record.update(status="unattempted", reason="new_request_deadline")
                else:
                    last_start = result["start"]
                    record.update(status="attempted", request_index=attempts, **result)
                    attempts += 1
                    charged += result["consumed_upper"]
                    seen[slot.key] = index
                    if result["body"] is not None:
                        members.append(result["body"])
        records.append(record)
        journal = root / f"{index:03d}.slot.private.json"
        _write_new(journal, _bytes(record))
        members.append(_pin(journal))
    complete = not any(r["status"] == "unattempted" for r in records)
    receipt = {**initial, "complete": complete, "slots": records, "attempts": attempts,
               "consumed_upper": charged, "observed_body_bytes": sum(r.get("observed_bytes", 0) for r in records),
               "all_slots_transport_pass": all(r.get("transport_pass", False) for r in records),
               "elapsed_s": time.monotonic() - begin}
    if arg["fixture_mode"] == "block_finalization":
        time.sleep(60)
    _write_new(root / "receipt.private.json", _bytes(receipt))
    members.append(_pin(root / "receipt.private.json"))
    _write_new(root / "manifest.private.json", _bytes({"protocol": PROTOCOL, "members": members}))
    manifest = _pin(root / "manifest.private.json")
    _emit({"result": "finalized", "complete": complete, "all_slots_transport_pass": receipt["all_slots_transport_pass"],
           "manifest_sha256": manifest["sha256"], "mapping_status": MAPPING_STATUS})


def _fixture_check(plan, endpoint, limits, mode):
    if not plan.study_id.startswith("invented-") or mode not in ("", "block_connection", "block_finalization"):
        raise ValueError("invented fixture only")
    _text(endpoint, r"http://127[.]0[.]0[.]1:[0-9]{1,5}", "canonical numeric loopback endpoint required")
    parsed = urlsplit(endpoint)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None
            or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("numeric loopback fixture endpoint required")
    limits.check_fixture()


def _collect(plan, output_dir, endpoint, limits, gate, fixture, mode):
    begin = time.monotonic()
    # Revalidate immutable bytes; do not trust a hand-constructed Plan instance.
    checked = validate_plan(plan.source_bytes)
    if checked != plan:
        raise ValueError("plan object differs from source bytes")
    output = str(Path(output_dir).absolute())
    if len(output.encode("utf-8")) > MAX_OUTPUT_PATH_BYTES:
        raise ValueError("output path byte limit")
    arg = {"plan": plan.source_bytes.decode("utf-8"), "output": output,
           "begin": begin, "endpoint": endpoint, "limits": asdict(limits), "fixture": fixture,
           "gate": asdict(gate) if gate else None, "fixture_mode": mode}
    payload = _bytes(arg)
    if len(payload) > MAX_INTERNAL_ARGUMENT_BYTES:
        raise ValueError("controller argument limit")
    proc = _spawn("--controller")
    try:
        remaining = max(0, begin + limits.run_s - time.monotonic())
        stdout, _ = proc.communicate(input=payload, timeout=remaining)
        if proc.returncode != 0 or len(stdout) > MAX_EVENT_BYTES:
            result = {"result": "controller_failed", "complete": False, "all_slots_transport_pass": False}
        else:
            result = _json(stdout)
    except subprocess.TimeoutExpired:
        _kill(proc, group=True)
        result = {"result": "run_deadline", "complete": False, "all_slots_transport_pass": False}
    finally:
        _kill(proc, group=True)
        proc.stdout.close()
        _reap(proc)
    returned = time.monotonic()
    if returned > begin + limits.run_s:
        result.update(result="run_deadline", complete=False, all_slots_transport_pass=False)
    return {**result, "mapping_status": MAPPING_STATUS, "claims": _claims(),
            "begin": begin, "returned_at": returned, "elapsed_s": returned - begin}


def collect(plan: Plan, output_dir: str | Path, gate: ActualInvocationGate):
    """Callable production interface; no roster file reader or ready-to-run CLI."""
    if type(gate) is not ActualInvocationGate:
        raise ValueError("explicit parent invocation gate required")
    gate.check(plan)
    return _collect(plan, output_dir, ARCHIVE_ENDPOINT, DEFAULT_LIMITS, gate, False, "")


def collect_fixture(plan: Plan, output_dir: str | Path, endpoint: str, *, limits=DEFAULT_LIMITS, mode=""):
    """Invented loopback-only harness; never an archive acquisition fallback."""
    _fixture_check(plan, endpoint, limits, mode)
    return _collect(plan, output_dir, endpoint, limits, None, True, mode)


def verify_fixture_manifest(output_dir: str | Path):
    """Independent hash check for invented outputs only; actual replay is parent-owned."""
    root = Path(output_dir)
    receipt = _json((root / "receipt.private.json").read_bytes())
    if receipt.get("fixture") is not True or not receipt.get("study_id", "").startswith("invented-"):
        raise ValueError("fixture verification only")
    manifest = _json((root / "manifest.private.json").read_bytes())
    _fields(manifest, ("protocol", "members"))
    if manifest["protocol"] != PROTOCOL:
        raise ValueError("fixture manifest protocol")
    roster = validate_plan((root / "roster.private.json").read_bytes())
    if receipt.get("plan_sha256") != roster.sha256:
        raise ValueError("fixture roster pin mismatch")
    expected = {"roster.private.json", "initial.private.json", "receipt.private.json"}
    for index, row in enumerate(receipt["slots"]):
        journal_name = f"{index:03d}.slot.private.json"
        expected.add(journal_name)
        if _json((root / journal_name).read_bytes()) != row:
            raise ValueError("fixture journal mismatch")
        if row.get("body") is not None:
            expected.add(f"{index:03d}.body.private")
    names = [m["name"] for m in manifest["members"]]
    if len(receipt["slots"]) != 8 or len(names) != len(set(names)) or set(names) != expected:
        raise ValueError("fixture manifest membership mismatch")
    for member in manifest["members"]:
        if member["name"] != Path(member["name"]).name or _pin(root / member["name"]) != member:
            raise ValueError("independent fixture hash mismatch")
    return receipt


if __name__ == "__main__":
    # Only private supervised subprocess modes exist; no actual-run CLI.
    if len(sys.argv) != 2 or sys.argv[1] not in ("--worker", "--controller"):
        raise SystemExit("Use the reviewed callable interface and separate parent handoff.")
    arg_bytes = sys.stdin.buffer.read(MAX_INTERNAL_ARGUMENT_BYTES + 1)
    if len(arg_bytes) > MAX_INTERNAL_ARGUMENT_BYTES:
        raise SystemExit("internal argument limit")
    arg = _json(arg_bytes)
    if sys.argv[1] == "--worker":
        _worker(arg)
    else:
        _controller(arg)

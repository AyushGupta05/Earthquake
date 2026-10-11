"""One fixed offline invocation; actual use requires separately pinned parent authority."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time
import types
from xml.etree import ElementTree as ET

PROTOCOL = "geonet_legacy_joint_invocation_v3"
REPRESENTATIONS = ("original_qml", "fresh_qml", "native_scml")
BODY_CAP = 4 * 1024 * 1024
INPUT_CAP = 96 * 1024 * 1024
OUTPUT_CAP = 32 * 1024 * 1024
PLAN_CAP = 1024 * 1024
AUTH_CAP = 64 * 1024
SOURCE_CAP = 2 * 1024 * 1024
SOURCE_TOTAL_CAP = 16 * 1024 * 1024
EXPECTED_CODE = {
    "producer": {
        "projection.py": "ee4a3fe78681ee0fb0928306ae821d5b964765c1a2c414c77b448d2c8bf0d097",
        "comparison.py": "9c0b3c3480a345ecb53ac6e52b18bc47657b4792ce527b6b640d3adc230caab6",
        "shadow.py": "a9d4c5f33ea831cbdbd815f960c641153f350ec267daa706aa8bedaa87999bcf",
    },
    "auditor": {
        "semantic_audit.py": "cc93594acb6c120319d6520b17c7f2e2cdaad86ed4ae5d0de6115dfc58921763",
    },
}
EXPECTED_BUNDLE_MEMBERS = {"producer": 86, "auditor": 34}
FAILURE_STAGES = (
    "startup", "start_gate", "runtime_validation", "plan_authorization",
    "source_bundles", "event_schema", "body_validation", "native_profile",
    "module_loading", "producer_projection", "independent_projection",
    "clock_comparison", "serialization", "stdout_write",
)
DIAGNOSTIC_CAP = 1024


class _OutputCapExceeded(ValueError):
    """Raised only by the internal serialized-byte guard, never from a message."""


class _JSONEncoderRejected(ValueError):
    """Fixed marker for an exact known exception from the JSON encoder boundary."""


class Progress:
    """Only fixed stage names and bounded body positions; no input values."""
    def __init__(self):
        self.stage = "startup"
        self.validated_body_count = 0
        self.body_index = None

    def mark(self, stage, body_index=None):
        if stage not in FAILURE_STAGES or (body_index is not None and
                (type(body_index) is not int or not 0 <= body_index < 18)):
            raise ValueError("invalid internal diagnostic stage")
        self.stage, self.body_index = stage, body_index


def failure_diagnostic(progress, error):
    # An exception's text, attributes and arbitrary class name are never copied.
    known = (ValueError, TypeError, KeyError, IndexError, AttributeError,
             OSError, RuntimeError, OverflowError, UnicodeError, MemoryError,
             RecursionError, ZeroDivisionError)
    exception_class = next((cls.__name__ for cls in known if type(error) is cls), "OtherException")
    serializer_failure = "not_serialization"
    if progress.stage == "serialization":
        serializer_failure = (
            "output_cap_exceeded" if type(error) is _OutputCapExceeded else
            "json_encoder_rejected" if type(error) is _JSONEncoderRejected else
            "other_or_unknown")
    body = encoded({"protocol_id": PROTOCOL, "complete": False,
        "stage": progress.stage, "validated_body_count": progress.validated_body_count,
        "body_index": progress.body_index, "exception_class": exception_class,
        "serializer_failure": serializer_failure}) + b"\n"
    if len(body) > DIAGNOSTIC_CAP:
        raise ValueError("internal diagnostic exceeds bound")
    return body


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default diagnostic can echo private argument values.
        raise ValueError("invalid invocation arguments")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _result_json_parts(value):
    # Only encoder operations are inside this boundary. Buffer/write/deadline
    # failures cannot acquire an encoder-rejection marker from their exception type.
    try:
        yield from json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False).iterencode(value)
    except Exception as error:
        if type(error) in (ValueError, TypeError, OverflowError, RecursionError):
            raise _JSONEncoderRejected() from None
        raise


def bounded_result(value):
    stream = io.BytesIO()
    count = 0
    for part in _result_json_parts(value):
        chunk = part.encode("utf-8")
        count += len(chunk)
        if count + 1 > OUTPUT_CAP:
            raise _OutputCapExceeded()
        stream.write(chunk)
    stream.write(b"\n")
    return stream.getvalue()


def exact_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("unexpected object fields")


def hex_pin(value, width=64):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{%d}" % width, value) is None:
        raise ValueError("invalid digest")
    return value


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise ValueError("whole invocation deadline elapsed")


def canonical_path(path):
    if not isinstance(path, str):
        raise ValueError("input path must be a string")
    p = Path(path)
    if str(p) != path or not p.is_absolute() or p.is_symlink() or p.resolve() != p:
        raise ValueError("noncanonical or symlink input path")
    return p


def read_regular(path, cap, deadline):
    check_deadline(deadline)
    p = canonical_path(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
            raise ValueError("input is not a bounded regular file")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            body = stream.read(cap + 1)
        if len(body) > cap:
            raise ValueError("input grew beyond bound")
    finally:
        if fd is not None:
            os.close(fd)
    check_deadline(deadline)
    return body


def check_pin(body, pin, cap):
    exact_keys(pin, ("sha256", "bytes"))
    hex_pin(pin["sha256"])
    if type(pin["bytes"]) is not int or not 0 <= pin["bytes"] <= cap:
        raise ValueError("invalid pinned length")
    if len(body) != pin["bytes"] or digest(body) != pin["sha256"]:
        raise ValueError("input pin mismatch")


def json_body(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result
    def no_constant(value):
        raise ValueError("nonfinite JSON value")
    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=no_constant)


def source_bundle(bundle, role, deadline):
    exact_keys(bundle, ("directory", "members"))
    root = canonical_path(bundle["directory"])
    if not root.is_dir():
        raise ValueError("source directory must be canonical")
    members = bundle["members"]
    if not isinstance(members, dict) or len(members) != EXPECTED_BUNDLE_MEMBERS[role]:
        raise ValueError("invalid source member mapping")
    if not set(EXPECTED_CODE[role]) <= set(members):
        raise ValueError("missing frozen entry modules")
    saved, total = {}, 0
    for relative, pin in sorted(members.items()):
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise ValueError("invalid relative source member")
        rel = PurePosixPath(relative)
        if rel.is_absolute() or rel.as_posix() != relative or any(part in (".", "..") for part in rel.parts):
            raise ValueError("unsafe relative source member")
        body = read_regular(str(root / relative), SOURCE_CAP, deadline)
        check_pin(body, pin, SOURCE_CAP)
        total += len(body)
        if total > SOURCE_TOTAL_CAP:
            raise ValueError("source bundle exceeds bound")
        if relative in EXPECTED_CODE[role]:
            if digest(body) != EXPECTED_CODE[role][relative]:
                raise ValueError("wrong frozen implementation")
            saved[relative] = body
    return saved


def load_frozen(producer_bytes, auditor_bytes, producer_dir, auditor_dir):
    # Execute only already-verified byte buffers: there is no second source read/import race.
    names = ("projection", "comparison", "shadow", "independent_legacy_semantic_v3")
    if any(name in sys.modules for name in names):
        raise ValueError("generic module namespace is not fresh")
    for name, body, path in (
        ("projection", producer_bytes["projection.py"], Path(producer_dir) / "projection.py"),
        ("comparison", producer_bytes["comparison.py"], Path(producer_dir) / "comparison.py"),
        ("shadow", producer_bytes["shadow.py"], Path(producer_dir) / "shadow.py"),
        ("independent_legacy_semantic_v3", auditor_bytes["semantic_audit.py"], Path(auditor_dir) / "semantic_audit.py"),
    ):
        module = types.ModuleType(name)
        module.__file__ = str(path)
        sys.modules[name] = module
        exec(compile(body, str(path), "exec"), module.__dict__)
    return sys.modules["shadow"], sys.modules["independent_legacy_semantic_v3"]


def utc_us(value):
    if not isinstance(value, str):
        raise ValueError("accepted pick time must be a string")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("accepted pick time must be aware")
    delta = dt.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def valid_anchor(value):
    if value is not None:
        if type(value) is not int:
            raise ValueError("preserved T0 must be integer microseconds or null")
        try:
            from datetime import timedelta
            datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value)
        except (OverflowError, ValueError):
            raise ValueError("preserved T0 outside UTC calendar range") from None


def independent_clocks(projection, preserved):
    valid_anchor(preserved)
    if projection.get("status") != "ok":
        return {"status": "unknown_representation", "own_clock": None, "at_preserved_original_T0": None}
    picks = projection.get("accepted_picks")
    if not isinstance(picks, list):
        raise ValueError("known projection lacks accepted picks")
    stations = {}
    for pick in picks:
        if not isinstance(pick, dict):
            raise ValueError("invalid accepted pick")
        network, station = pick.get("network"), pick.get("station")
        if not isinstance(network, str) or not isinstance(station, str) or not network or not station:
            raise ValueError("accepted station identity missing")
        if network == "NZ":
            timestamp = utc_us(pick.get("time"))
            key = (network, station)
            stations[key] = min(stations.get(key, timestamp), timestamp)
    own = min(stations.values(), default=None)
    def at(anchor):
        return {"station_count": len(stations), "t0_us": own, "anchor_us": anchor,
                "strict_horizon_station_counts": {
                    str(h): None if anchor is None else sum(t < anchor + h * 1000000 for t in stations.values())
                    for h in (1, 3, 5)}}
    return {"status": "ok", "own_clock": at(own),
            "at_preserved_original_T0": None if preserved is None else at(preserved)}


class _RootFound(Exception):
    pass


def native_root_profile(body):
    # Root recognition is independent of the frozen projectors; it is not full XML validation.
    recognized = []
    class RootTarget:
        def start(self, tag, attributes):
            for version in ("0.10", "0.11"):
                if tag == "{http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/" + version + "}seiscomp" and attributes.get("version") == version:
                    recognized.append(version)
            raise _RootFound()
        def end(self, tag):
            pass
        def data(self, text):
            pass
        def close(self):
            pass
        def doctype(self, name, pubid, system):
            raise ValueError("DOCTYPE unsupported")
    try:
        body.decode("utf-8")
        # NUL is forbidden in XML 1.0 and prevents Expat's UTF-16/32 autodetection
        # from accepting ASCII/NUL byte sequences that also decode as UTF-8.
        if b"\x00" in body:
            return None
        declaration = re.match(br"\A(?:\xef\xbb\xbf)?<\?xml\s+.*?\?>", body, re.DOTALL)
        if declaration:
            encoding = re.search(br"\bencoding\s*=\s*(['\"])(.*?)\1", declaration.group())
            if encoding and encoding.group(2).lower() != b"utf-8":
                return None
        parser = ET.XMLParser(target=RootTarget(), encoding="utf-8")
        parser.feed(body)
        parser.close()
    except _RootFound:
        return recognized[0] if len(recognized) == 1 else None
    except (ValueError, ET.ParseError, UnicodeError):
        return None
    return None


def joint_result(events, provenance, shadow_module, auditor_module, progress=None):
    progress = Progress() if progress is None else progress
    progress.mark("producer_projection")
    producer = shadow_module.run_shadow(events, provenance)
    if producer.get("protocol_id") != "geonet_legacy_offline_shadow_v2" or len(producer.get("events", [])) != 6:
        raise ValueError("producer result contract mismatch")
    independent, mismatch_slots, earlier_slots = [], 0, 0
    for event, reported in zip(events, producer["events"]):
        if reported.get("preserved_original_T0_us") != event["original_t0_us"]:
            raise ValueError("producer changed preserved clock")
        binding = reported.get("native_profile_binding", {})
        recognized = native_root_profile(event["native_scml"])
        if recognized != event["native_profile"]:
            raise ValueError("independent native root/profile mismatch")
        native_ok = reported.get("representations", {}).get("native_scml", {}).get("status") == "ok"
        # An unsupported native projection may withhold its recognized profile. Root evidence
        # does not make that projection known and does not bind primary QML extensions.
        if binding.get("recognized") not in (None, recognized) or (native_ok and binding.get("recognized") != recognized):
            raise ValueError("producer recognized profile conflict")
        if binding.get("bound") is not native_ok or binding.get("supplied") != recognized:
            raise ValueError("unexpected producer profile binding")
        profile = recognized if binding["bound"] else None
        projections, clocks, mismatches, offsets = {}, {}, {}, {}
        for representation in REPRESENTATIONS:
            progress.mark("independent_projection")
            fmt = "scml" if representation == "native_scml" else "qml"
            projections[representation] = auditor_module.project(
                event[representation], event["event_id"], fmt,
                recognized if fmt == "scml" else profile)
            progress.mark("clock_comparison")
            clocks[representation] = independent_clocks(projections[representation], event["original_t0_us"])
            other = reported.get("representations", {}).get(representation, {})
            comparable = other.get("status") == projections[representation].get("status") == "ok"
            mismatch = comparable and reported.get("shadow_clocks", {}).get(representation) != clocks[representation]
            mismatches[representation] = {"comparable": comparable, "mismatch": mismatch}
            mismatch_slots += int(mismatch)
            preserved = event["original_t0_us"]
            def offset(clock):
                own = (clock or {}).get("own_clock")
                earliest = own.get("t0_us") if isinstance(own, dict) else None
                return earliest - preserved if type(earliest) is int and preserved is not None else None
            offsets[representation] = {
                "producer_own_earliest_minus_original_T0_us": offset(reported.get("shadow_clocks", {}).get(representation)),
                "independent_own_earliest_minus_original_T0_us": offset(clocks[representation]),
                "meaning": "observed_accepted_subset_revision_diagnostic"}
            signed = offsets[representation]["independent_own_earliest_minus_original_T0_us"]
            earlier_slots += int(signed is not None and signed < 0)
        independent.append({"event_id": event["event_id"], "native_root_profile": recognized,
            "primary_qml_profile": profile, "representations": projections, "shadow_clocks": clocks,
            "catalogue_drift": auditor_module.compare(projections["original_qml"], projections["fresh_qml"]),
            "representation_difference": auditor_module.compare(projections["fresh_qml"], projections["native_scml"]),
            "producer_clock_comparison": mismatches, "signed_clock_diagnostics": offsets})
    status_counts = Counter(p.get("status") for e in independent for p in e["representations"].values())
    aggregate = {"events": 6, "representation_slots": 18, "independent_status_counts": dict(status_counts),
                 "known_projection_clock_mismatch_slots": mismatch_slots,
                 "independent_own_clock_earlier_than_preserved_slots": earlier_slots,
                 "shared_known_subset_clock_mismatch_detected": mismatch_slots > 0,
                 "shared_clock_claim_permitted": False,
                 "universal_semantic_equality_claim_permitted": False,
                 "network_requests": 0, "automatic_reclock_applied": False,
                 "model_improvement_claim": False, "operational_availability_claim": False}
    return {"protocol_id": PROTOCOL, "private": {"producer": producer, "independent": independent,
        "policy_differences": {"producer_guarded_recovery_scope": "all_networks", "auditor_guarded_recovery_scope": "NZ",
            "auditor_revision_policy": "all_present_times_aware_nonempty", "producer_revision_policy": "any_valid_recorded_time",
            "unrecognized_native_boolean_policy": "producer_unknown_vs_auditor_literal_source_predicate",
            "geometry_policy": "producer_binary_float_vs_auditor_exact_decimal",
            "primary_qml_profile": "producer_bound_native_ok_decision"}}, "public_aggregate": aggregate}


def execute(plan_path, auth_path, trusted, deadline, progress=None):
    progress = Progress() if progress is None else progress
    progress.mark("plan_authorization")
    plan_bytes = read_regular(plan_path, PLAN_CAP, deadline)
    auth_bytes = read_regular(auth_path, AUTH_CAP, deadline)
    if digest(plan_bytes) != trusted["plan_sha256"] or digest(auth_bytes) != trusted["authorization_sha256"]:
        raise ValueError("parent plan/authorization binding mismatch")
    plan, auth = json_body(plan_bytes), json_body(auth_bytes)
    exact_keys(plan, ("protocol_id", "original_plan_sha256", "original_manifest_sha256",
        "original_census_clock_source_sha256", "processing_source_mapping_sha256", "producer", "auditor", "events"))
    exact_keys(auth, ("protocol_id", "authorization", "plan_sha256", "adapter_sha256", "supervisor_sha256",
        "runtime", "pushed_freeze", "original_census_clock_source_sha256", "original_census_clocks_independently_verified",
        "source_freeze_tests_review_verified", "git_pushed_freeze_independently_verified", "network_requests_authorized",
        "producer_bundle_sha256", "auditor_bundle_sha256", "adapter_review_receipt_sha256", "adapter_test_receipt_sha256"))
    if plan["protocol_id"] != PROTOCOL or auth["protocol_id"] != PROTOCOL or auth["authorization"] != "one_fixed_offline_invocation":
        raise ValueError("wrong invocation protocol/authorization")
    for flag in ("original_census_clocks_independently_verified", "source_freeze_tests_review_verified", "git_pushed_freeze_independently_verified"):
        if auth[flag] is not True:
            raise ValueError("parent verification flag missing")
    if type(auth["network_requests_authorized"]) is not int or auth["network_requests_authorized"] != 0:
        raise ValueError("offline-only authorization required")
    for key in ("original_plan_sha256", "original_manifest_sha256", "original_census_clock_source_sha256", "processing_source_mapping_sha256"):
        hex_pin(plan[key])
    for key in ("plan_sha256", "adapter_sha256", "supervisor_sha256", "original_census_clock_source_sha256",
                "producer_bundle_sha256", "auditor_bundle_sha256", "adapter_review_receipt_sha256", "adapter_test_receipt_sha256"):
        hex_pin(auth[key])
    hex_pin(auth["pushed_freeze"], 40)
    if any(auth[key] != trusted[key] for key in ("plan_sha256", "adapter_sha256", "supervisor_sha256")):
        raise ValueError("trusted invocation pins differ")
    exact_keys(auth["runtime"], ("path", "sha256"))
    if auth["runtime"] != {"path": trusted["runtime_path"], "sha256": trusted["runtime_sha256"]}:
        raise ValueError("runtime authority differs")
    if auth["original_census_clock_source_sha256"] != plan["original_census_clock_source_sha256"]:
        raise ValueError("preserved census clock provenance differs")
    for role in ("producer", "auditor"):
        if digest(encoded(plan[role])) != auth[role + "_bundle_sha256"]:
            raise ValueError("full source bundle authority differs")
    progress.mark("source_bundles")
    producer_bytes = source_bundle(plan["producer"], "producer", deadline)
    auditor_bytes = source_bundle(plan["auditor"], "auditor", deadline)
    events = plan["events"]
    if not isinstance(events, list) or len(events) != 6:
        raise ValueError("exact six events required")
    seen, paths, total, loaded = set(), set(), 0, []
    for row in events:
        progress.mark("event_schema")
        exact_keys(row, ("event_id", "original_t0_us", "native_profile", "bodies"))
        eid = row["event_id"]
        if not isinstance(eid, str) or not eid or eid in seen or len(eid) > 1024:
            raise ValueError("event identity duplicate/invalid")
        seen.add(eid)
        valid_anchor(row["original_t0_us"])
        if row["native_profile"] not in (None, "0.10", "0.11"):
            raise ValueError("unsupported native profile")
        exact_keys(row["bodies"], REPRESENTATIONS)
        current = {key: row[key] for key in ("event_id", "original_t0_us", "native_profile")}
        current["body_pins"] = {}
        for representation in REPRESENTATIONS:
            progress.mark("body_validation", progress.validated_body_count)
            pin = row["bodies"][representation]
            exact_keys(pin, ("path", "bytes", "sha256"))
            canonical = str(canonical_path(pin["path"]))
            if canonical in paths:
                raise ValueError("representation paths must be distinct")
            paths.add(canonical)
            body = read_regular(pin["path"], BODY_CAP, deadline)
            simple_pin = {key: pin[key] for key in ("bytes", "sha256")}
            check_pin(body, simple_pin, BODY_CAP)
            total += len(body)
            if total > INPUT_CAP:
                raise ValueError("body input budget exceeded")
            current[representation], current["body_pins"][representation] = body, simple_pin
            progress.validated_body_count += 1
        progress.mark("native_profile")
        recognized = native_root_profile(current["native_scml"])
        if recognized is None or (row["native_profile"] is not None and recognized != row["native_profile"]):
            raise ValueError("independent native profile preflight failed")
        current["native_profile"] = recognized
        loaded.append(current)
    check_deadline(deadline)
    progress.mark("module_loading")
    shadow_module, auditor_module = load_frozen(producer_bytes, auditor_bytes, plan["producer"]["directory"], plan["auditor"]["directory"])
    provenance = {key: plan[key] for key in ("original_plan_sha256", "original_manifest_sha256",
        "original_census_clock_source_sha256", "processing_source_mapping_sha256")}
    provenance.update(runtime_sha256=trusted["runtime_sha256"], pushed_freeze=auth["pushed_freeze"],
                      parent_authorization_receipt_sha256=trusted["authorization_sha256"])
    check_deadline(deadline)
    result = joint_result(loaded, provenance, shadow_module, auditor_module, progress)
    for observed, requested in zip(result["private"]["independent"], events):
        observed["profile_input_provenance"] = {
            "parent_explicit_native_profile": requested["native_profile"],
            "native_profile_supplied_from_child_root_recognition": requested["native_profile"] is None,
            "deployed_converter_profile_proved": False}
    result["private"]["invocation_provenance"] = {"plan_sha256": digest(plan_bytes), "authorization_sha256": digest(auth_bytes),
        "adapter_sha256": trusted["adapter_sha256"], "supervisor_sha256": trusted["supervisor_sha256"],
        "producer_bundle_sha256": auth["producer_bundle_sha256"], "auditor_bundle_sha256": auth["auditor_bundle_sha256"],
        "parent_verification_assertions_independently_reperformed_here": False}
    check_deadline(deadline)
    progress.mark("serialization")
    output = bounded_result(result)
    check_deadline(deadline)
    return output


def main(progress):
    parser = PrivateArgumentParser(add_help=False)
    for field in ("plan", "authorization", "plan-sha256", "authorization-sha256", "adapter-sha256",
                  "supervisor-sha256", "runtime-sha256", "runtime-path", "deadline"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError("fresh -I -B interpreter required")
    deadline = float(args.deadline)
    if not time.monotonic() < deadline <= time.monotonic() + 120:
        raise ValueError("invalid invocation deadline")
    # No plan, authorization, dependency source or body reads until parent has a live handle.
    progress.mark("start_gate")
    if sys.stdin.buffer.read(1) != b"G":
        raise ValueError("parent start gate closed")
    check_deadline(deadline)
    progress.mark("runtime_validation")
    trusted = vars(args).copy()
    trusted["authorization_sha256"] = args.authorization_sha256
    for key in ("plan_sha256", "authorization_sha256", "adapter_sha256", "supervisor_sha256", "runtime_sha256"):
        hex_pin(trusted[key])
    if str(Path(sys.executable).resolve()) != args.runtime_path:
        raise ValueError("wrong resolved interpreter")
    if digest(read_regular(args.runtime_path, 128 * 1024 * 1024, deadline)) != args.runtime_sha256:
        raise ValueError("runtime hash mismatch")
    if digest(read_regular(str(Path(__file__).resolve()), SOURCE_CAP, deadline)) != args.adapter_sha256:
        raise ValueError("adapter hash mismatch")
    output = execute(args.plan, args.authorization, trusted, deadline, progress)
    check_deadline(deadline)
    progress.mark("stdout_write")
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    progress = Progress()
    try:
        main(progress)
    except Exception as error:
        sys.stderr.buffer.write(failure_diagnostic(progress, error))
        sys.exit(1)

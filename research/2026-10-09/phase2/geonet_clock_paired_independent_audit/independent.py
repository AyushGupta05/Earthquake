"""Independent stdlib selection, artifact, clock and limited XML evidence checks.

No producer modules or transforms are imported. This is deliberately not a
second full native/QML projector: accepted-pick eligibility and complete
arrival/conversion semantics remain outside its verification claim.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import math
import re
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

MIB = 1048576
Q = "http://quakeml.org/xmlns/quakeml/1.2"
B = "http://quakeml.org/xmlns/bed/1.2"
NATIVE = {
    "0.13": "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.13",
    "0.14": "http://geofon.gfz.de/ns/seiscomp-schema/0.14",
}
SLOTS = ("original_qml", "fresh_qml", "native_scml")
REASONS = ("missing_or_ambiguous_pick_reference", "invalid_or_naive_pick_time",
           "missing_station_identity")
REVISION = ("agencyID", "agencyURI", "author", "authorURI", "creationTime",
            "modificationTime", "version")
CAPS = {"events": 6, "requests": 12, "body_bytes": 48 * MIB,
        "per_body_bytes": 4 * MIB, "outer_seconds": 360,
        "finalization_reserve_seconds": 10, "request_seconds": 20,
        "start_spacing_seconds": 1, "retries": 0, "redirects": 0,
        "replacements": 0, "resume": False, "AWS": 0, "fits": 0}


class AuditError(ValueError):
    """Fixed error labels never include a private identifier or payload."""


def require(condition, label):
    if not condition:
        raise AuditError(label)


def original_eligibility(bulk_rows, groups, rows, ordered_ids):
    """Cross-check copied tail eligibility against pinned original CMT evidence."""
    grouped = {g["event_id"]: g for g in groups}
    indexed = {r["row_index"]: r for r in rows}
    require(len(grouped) == len(groups) and len(indexed) == len(rows), "census_duplicate_group_or_row")
    tail = [r for r in bulk_rows if r["source"] == "reused_tail"]
    require(len(tail) == len(ordered_ids) == 149 and
            len(set(ordered_ids)) == 149 and {r["event_id"] for r in tail} == set(ordered_ids),
            "original_tail_membership")
    for copied in tail:
        eid = copied["event_id"]
        require(eid in grouped, "original_tail_group_missing")
        group = grouped[eid]
        indices = group["row_indices"]
        require(indices and all(type(i) is int and i > 0 for i in indices) and
                len(set(indices)) == len(indices), "original_tail_row_indices")
        require(set(indices) == {r["row_index"] for r in rows if r["event_id"] == eid},
                "original_tail_row_membership")
        linked = [indexed[i] for i in indices]
        require(group["eligible"] is True and all(r["reasons"] == [] for r in linked),
                "original_tail_ineligible")
        magnitudes = [r["mw"] for r in linked]
        require(all(type(x) in (int, float) and math.isfinite(x) for x in magnitudes) and
                len(set(magnitudes)) == 1 and magnitudes[0] >= 5.5,
                "original_tail_magnitude")
        dates = {r["date"] for r in linked}
        require(len(dates) == 1 and group["dates"] == sorted(dates), "original_tail_dates")
        value = next(iter(dates))
        require(isinstance(value, str) and re.fullmatch(r"[0-9]{12}00", value), "original_tail_date_format")
        try:
            date = datetime.strptime(value, "%Y%m%d%H%M%S")
        except ValueError:
            raise AuditError("original_tail_date_format") from None
        require(datetime(2003, 8, 1) <= date < datetime(2025, 1, 1), "original_tail_date_window")
        partition = ("train2003_2014" if date.year <= 2014 else
                     "dev2015_2017" if date.year <= 2017 else "test2018_2024")
        require(group["mw_min"] == group["mw_max"] == magnitudes[0] == copied["mw"] and
                copied["cmt_time"] == value and copied["candidate_calendar_partition"] == partition and
                copied["cmt_row_indices"] == indices, "original_tail_eligibility_changed")
    return len(tail)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def size_hash(body):
    return {"bytes": len(body), "sha256": digest(body)}


def nonnegative_int(value):
    return type(value) is int and value >= 0


def stamp(value):
    require(isinstance(value, str), "timestamp_type")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(parsed.utcoffset() is not None, "timestamp_timezone")
        delta = parsed.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    except (ValueError, OverflowError, TypeError):
        raise AuditError("timestamp_invalid") from None


def frame_selection(rows, outcomes):
    require(isinstance(rows, list) and len(rows) == 495, "frame_denominator")
    ids = [row["event_id"] for row in rows]
    require(all(isinstance(x, str) and x for x in ids) and len(set(ids)) == 495,
            "frame_identity")
    require(set(outcomes) == set(ids), "frame_outcomes")
    require(Counter(row["source"] for row in rows) ==
            Counter({"reused_tail": 149, "new_lower_M": 346}), "frame_sources")
    candidates = []
    for row in rows:
        mw = row["mw"]
        require(type(mw) in (int, float) and math.isfinite(mw), "magnitude_domain")
        if (row["source"] != "reused_tail" or
                row["candidate_calendar_partition"] != "test2018_2024" or mw < 6):
            continue
        base = outcomes[row["event_id"]]["base"]
        require(base.get("status") == "ok", "candidate_original_unknown")
        reasons = base["reasons"]
        counts = [reasons.get(key, 0) for key in REASONS]
        require(all(nonnegative_int(x) for x in counts), "incomplete_reason_domain")
        item = dict(row)
        item["Mw_band"] = "[6,7)" if mw < 7 else ">=7"
        item["incomplete"] = any(counts)
        nz = base.get("nz")
        t0 = nz.get("t0_utc") if nz is not None else None
        item["preserved_original_T0_us"] = stamp(t0) if t0 else None
        candidates.append(item)
    probes = [x for x in candidates if x["incomplete"]]
    require(Counter(x["Mw_band"] for x in probes) == Counter({"[6,7)": 3, ">=7": 1}),
            "fixed_probe_denominator")
    for item in probes:
        item["role"] = "incomplete_probe"
    selected = probes[:]
    for band in ("[6,7)", ">=7"):
        pool = [x for x in candidates if not x["incomplete"] and x["Mw_band"] == band]
        require(bool(pool), "missing_control_band")
        def rank(item):
            text = "geonet-scml-paired-control-v1|test2018_2024|" + band + "|" + item["event_id"]
            return digest(text.encode("utf-8")), item["event_id"]
        winner = min(pool, key=rank)
        winner["role"] = "complete_control"
        selected.append(winner)
    return sorted(selected, key=lambda x: (
        digest(("geonet-scml-paired-query-v1|" + x["event_id"]).encode("utf-8")), x["event_id"]))


def request_list(events):
    result = []
    for event in events:
        for kind, route in (("qml", "/fdsnws/event/1/query"), ("scml", "/sc3ml")):
            i = len(result)
            result.append({"event_id": event["event_id"], "kind": kind, "method": "GET",
                           "file": f"{kind}_{i:02d}.xml", "url": "https://service.geonet.org.nz" +
                           route + "?" + urlencode({"eventid": event["event_id"]})})
    return result


def selected_plan(rows, outcomes, plan):
    selected = frame_selection(rows, outcomes)
    require(len(plan["events"]) == 6, "plan_denominator")
    for expected, actual in zip(selected, plan["events"]):
        reduced = dict(actual)
        original = reduced.pop("original_qml")
        require(reduced == expected, "plan_selection_or_clock")
        require(re.fullmatch(r"[0-9a-f]{64}", original["projection_sha256"]) is not None,
                "projection_digest_shape")
    require(plan["requests"] == request_list(selected), "plan_requests")
    order_hash = digest(("\n".join(x["event_id"] for x in selected) + "\n").encode("utf-8"))
    require(plan["event_order_sha256"] == order_hash, "plan_order_hash")
    require(plan["event_denominator"] == 6 and plan["new_request_count"] == 12,
            "plan_fixed_denominators")
    require(plan["specification"]["caps"] == CAPS and
            plan["specification"]["horizons_seconds"] == [1, 3, 5], "plan_caps")
    return selected


def clock(picks, anchor=None):
    earliest = {}
    for item in picks:
        key = (item["network"], item["station"])
        require(all(isinstance(x, str) and x for x in key), "clock_station_identity")
        value = stamp(item["time"])
        if key not in earliest or value < earliest[key]:
            earliest[key] = value
    first = min(earliest.values()) if earliest else None
    if anchor is not None:
        require(type(anchor) is int, "clock_anchor_domain")
    origin = first if anchor is None else anchor
    return {"station_count": len(earliest), "t0_us": first, "anchor_us": origin,
            "strict_horizon_station_counts": {
                str(h): None if origin is None else sum(t < origin + h * 1000000
                                                      for t in earliest.values())
                for h in (1, 3, 5)}}


def slots_and_clocks(events, results):
    require(len(results) == 6 and len({x["event_id"] for x in results}) == 6,
            "result_denominator")
    require([x["event_id"] for x in results] == [x["event_id"] for x in events], "result_order")
    statuses = Counter()
    for event, result in zip(events, results):
        require(result["role"] == event["role"] and result["Mw_band"] == event["Mw_band"],
                "result_role")
        anchor = event["preserved_original_T0_us"]
        require(result["preserved_original_T0_us"] == anchor, "original_clock_replaced")
        require(set(result["representations"]) == set(SLOTS) and
                set(result["shadow_clocks"]) == set(SLOTS), "representation_slots")
        for name in SLOTS:
            record, shadow = result["representations"][name], result["shadow_clocks"][name]
            require(record["event_id"] == event["event_id"], "representation_identity")
            status = record["status"]
            require(status in ("ok", "unknown_representation", "transport_failed", "not_attempted",
                               "interrupted", "attempting"), "representation_status")
            statuses[name + ":" + status] += 1
            require(shadow["status"] == status, "shadow_status")
            if status != "ok":
                require(all(record.get(k) is None for k in (
                    "denominators", "nz", "all_network", "accepted_picks")), "unknown_became_zero")
                require(shadow["own_clock"] is None and shadow["at_preserved_original_T0"] is None,
                        "unknown_shadow")
                continue
            picks = record["accepted_picks"]
            require(isinstance(picks, list) and len({x["pick_id"] for x in picks}) == len(picks),
                    "saved_accepted_deduplication")
            nz = [x for x in picks if x["network"] == "NZ"]
            own, all_network = clock(nz), clock(picks)
            require(record["nz"] == own and record["all_network"] == all_network,
                    "saved_accepted_clock")
            require(shadow["own_clock"] == own and shadow["at_preserved_original_T0"] ==
                    (clock(nz, anchor) if anchor is not None else None), "shadow_clock")
            d = record["denominators"]
            require(all(nonnegative_int(x) for x in d.values()), "parsed_denominator_domain")
            require(d["accepted_P_picks"] == len(picks) and d["accepted_NZ_P_picks"] == len(nz),
                    "saved_accepted_denominators")
            require(d["accepted_P_picks"] <= d["unique_resolved_qualifying_P_reference_ids"] <=
                    d["unique_qualifying_P_reference_ids"] <= d["qualifying_P_references"] <=
                    d["all_preferred_arrivals"], "parsed_denominator_order")
            incomplete = record["incomplete_associated_P_structure"]
            require(type(incomplete) is bool and record["NZ_coverage_known"] == (bool(nz) or not incomplete),
                    "unresolved_zero_coverage")
    return dict(statuses)


def mapped(identifier):
    require(isinstance(identifier, str) and bool(identifier), "xml_empty_identifier")
    return identifier if identifier.startswith(("smi:", "quakeml:")) else (
        "smi:nz.org.geonet/" + identifier.replace(":", "_").replace(" ", "_"))


def xml_core(body, event_id, kind):
    """Limited XML profile: identity, preferred linkage, geometry and revision.

    No accepted-pick eligibility, arrival signature or full transform replay is
    inferred from these primitives. Unsupported syntax produces unknown evidence.
    """
    require(len(body) <= 4 * MIB, "xml_byte_cap")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AuditError("xml_encoding_profile") from None
    declaration = re.match(r"\A\s*<\?xml\b(.*?)\?>", text, re.DOTALL | re.IGNORECASE)
    if declaration:
        encoding = re.search(r"\bencoding\s*=\s*(['\"])(.*?)\1", declaration.group(1), re.IGNORECASE)
        if encoding:
            require(encoding.group(2).lower() in ("utf-8", "utf8"), "xml_encoding_declaration_profile")
    require("<!DOCTYPE" not in text.upper() and "<!ENTITY" not in text.upper(), "xml_dtd")
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError):
        raise AuditError("xml_syntax") from None
    pending, n = [(root, 0)], 0
    while pending:
        node, depth = pending.pop()
        n += 1
        require(n <= 100000 and depth <= 64, "xml_tree_cap")
        pending.extend((x, depth + 1) for x in node)
    if kind == "qml":
        require(root.tag == "{" + Q + "}quakeml", "qml_root")
        ns, parameter = B, "eventParameters"
    else:
        require(kind == "scml" and root.get("version") in NATIVE, "scml_version")
        ns, parameter = NATIVE[root.get("version")], "EventParameters"
        require(root.tag == "{" + ns + "}seiscomp", "scml_namespace")
    def children(node, field):
        found = [x for x in node if x.tag == "{" + ns + "}" + field]
        # Foreign duplicates of evidence fields cannot support a singleton.
        require(not any(x.tag.split("}")[-1] == field and x not in found for x in node),
                "foreign_evidence_field")
        return found
    def one(node, field, required=False):
        found = children(node, field)
        require(len(found) <= 1 and (not required or len(found) == 1), "xml_singleton")
        return found[0] if found else None
    def scalar(node, field, required=False):
        value = one(node, field, required)
        if value is None:
            return None
        require(len(value) == 0, "xml_scalar_container")
        return value.text or ""
    params = one(root, parameter, True)
    events = children(params, "event")
    require(len(events) == 1, "xml_event")
    expected_identity = mapped(event_id)
    observed_identity = events[0].get("publicID")
    require((observed_identity == expected_identity if kind == "qml" else
             mapped(observed_identity) == expected_identity), "xml_event")
    event = events[0]
    preferred_text = scalar(event, "preferredOriginID", True)
    if kind == "scml":
        require(preferred_text == preferred_text.strip(), "native_reference_whitespace_profile")
    preferred = preferred_text.strip()
    require(preferred, "xml_preferred_origin")
    origin_parent = event if kind == "qml" else params
    origins = children(origin_parent, "origin")
    if kind == "scml":
        reference_nodes = children(event, "originReference")
        require(all(len(x) == 0 for x in reference_nodes), "xml_scalar_container")
        references = [x.text or "" for x in reference_nodes]
        require(preferred in references and len(references) == len(set(references)), "scml_origin_references")
        for reference in references:
            require(sum(x.get("publicID") == reference for x in origins) == 1, "scml_origin_link")
    candidates = [x for x in origins if x.get("publicID") == preferred]
    require(len(candidates) == 1, "xml_origin_link")
    origin = candidates[0]
    if kind == "scml":
        raw_ids = [x.get("publicID") for x in params if x.get("publicID")]
        by_map = {}
        for raw in raw_ids:
            require(mapped(raw) not in by_map or by_map[mapped(raw)] == raw, "scml_id_collision")
            by_map[mapped(raw)] = raw
    def revision(node):
        ci = one(node, "creationInfo")
        result = {x: None for x in REVISION}
        if ci is None:
            return result
        for field in REVISION:
            values = [x for x in ci if (x.tag == "{" + ns + "}" + field and
                      not (kind == "qml" and field == "modificationTime")) or
                      (kind == "qml" and field == "modificationTime" and
                       x.tag in {"{" + value + "}modificationTime" for value in NATIVE.values()})]
            require(len(values) <= 1 and not any(x.tag.split("}")[-1] == field and x not in values
                                               for x in ci), "revision_singleton_or_namespace")
            if values:
                require(len(values[0]) == 0, "revision_container")
                result[field] = values[0].text or ""
        return result
    def quantity(field, factor=1):
        container = one(origin, field)
        if container is None:
            return None
        value = scalar(container, "value")
        if value is None:
            return None
        if field == "time":
            try:
                return stamp(value.strip())
            except AuditError:
                return None
        try:
            number = Decimal(value.strip())
            if not number.is_finite():
                return None
            # Multiplication without Decimal context rounding.
            if factor == 1000:
                parts = number.as_tuple()
                number = Decimal((parts.sign, parts.digits, parts.exponent + 3))
            return number
        except (InvalidOperation, ValueError):
            return None
    return {"mapped_event_id": mapped(event.get("publicID")), "preferred_origin_id": mapped(preferred)
            if kind == "scml" else preferred, "origin": {
                "time_us": quantity("time"), "latitude": quantity("latitude"),
                "longitude": quantity("longitude"), "depth_m": quantity("depth", 1000 if kind == "scml" else 1)},
            "revision": {"event": revision(event), "origin": revision(origin)}}


def revision_relation(left, right):
    """Recorded fields only. Neither equality nor conflict establishes atomicity."""
    for scope in ("event", "origin"):
        for key in REVISION:
            a, b = left["revision"][scope][key], right["revision"][scope][key]
            if a is not None and b is not None and a != b:
                return "conflict"
    if left["revision"] != right["revision"]:
        return "missing_or_incomplete"
    for scope in ("event", "origin"):
        for key in ("creationTime", "modificationTime"):
            try:
                stamp(left["revision"][scope][key])
                return "matching_recorded_time"
            except AuditError:
                pass
    return "missing_or_incomplete"


def transport_replay(plan, manifest, ledger, body_by_name):
    require(manifest.get("completed") is True and manifest.get("worker_exit_code") == 0,
            "collection_not_complete")
    require(manifest["event_denominator"] == 6 and manifest["representation_denominator"] == 18,
            "manifest_denominators")
    require(manifest["caps"] == CAPS and len(ledger) == 12 and manifest["request_attempts"] == 12,
            "attempt_denominator")
    require(len(plan["requests"]) == 12, "query_denominator")
    total, previous = 0, None
    for expected, attempt in zip(plan["requests"], ledger):
        require(attempt["file"] == expected["file"] and attempt["url"] == expected["url"],
                "attempt_order_or_url")
        size = attempt["bytes"]
        require(nonnegative_int(size) and size <= 4 * MIB, "attempt_byte_cap")
        total += size
        started = stamp(attempt["utc"])
        require(previous is None or started - previous >= 1000000, "recorded_start_spacing")
        previous = started
        elapsed = attempt["elapsed_seconds"]
        require(type(elapsed) in (float, int) and math.isfinite(elapsed) and 0 <= elapsed <= 20,
                "recorded_request_duration")
        require(size_hash(body_by_name[expected["file"]]) == {"bytes": size, "sha256": attempt["sha256"]},
                "attempt_body_hash")
    require(total <= 48 * MIB and total == manifest["response_body_bytes"], "total_body_cap")
    outer = manifest["outer_elapsed_seconds"]
    require(type(outer) in (float, int) and math.isfinite(outer) and 0 <= outer <= 360,
            "recorded_outer_cap")
    return {"attempts": 12, "response_body_bytes": total, "recorded_outer_seconds": outer,
            "timing_claim": "Recorded wall-clock spacing and durations; no independent monotonic transport log"}

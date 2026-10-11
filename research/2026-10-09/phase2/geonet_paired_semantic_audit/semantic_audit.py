"""Independent, bounded metadata semantics. No I/O, acquisition, XSLT, or producer imports.

Only caller-supplied bytes enter project(). Results may be private when callers later
supply real metadata; this module does not decide publication or acquisition authority.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import re
import xml.etree.ElementTree as ET

QROOT = "http://quakeml.org/xmlns/quakeml/1.2"
BED = "http://quakeml.org/xmlns/bed/1.2"
SCML = {
    "0.13": "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.13",
    "0.14": "http://geofon.gfz.de/ns/seiscomp-schema/0.14",
}
PREFIX = "smi:nz.org.geonet/"
MAX_BYTES = 4 * 1024 * 1024
MAX_ELEMENTS = 100000
MAX_DEPTH = 64
CREATION_FIELDS = ("agencyID", "agencyURI", "author", "authorURI", "creationTime", "modificationTime", "version")
EVIDENCE_FIELDS = frozenset({
    "quakeml", "seiscomp", "eventParameters", "EventParameters", "event",
    "pick", "origin", "arrival", "amplitude", "stationMagnitude", "originReference",
    "preferredOriginID", "pickID", "amplitudeID", "phase", "timeWeight", "weight",
    "timeUsed", "horizontalSlownessUsed", "backazimuthUsed", "evaluationStatus",
    "evaluationMode", "waveformID", "time", "value", "latitude", "longitude", "depth",
    "creationInfo", *CREATION_FIELDS,
})
CLAIMS = {
    "physical_pick_validity_verified": False,
    "operational_receipt_timing_verified": False,
    "atomic_database_revision_verified": False,
    "converter_bug_proved": False,
    "automatic_reclock_applied": False,
    "model_improvement_verified": False,
}


class Unsupported(ValueError):
    """Structural evidence cannot be interpreted unambiguously."""


def _tag(namespace, local):
    return "{" + namespace + "}" + local


def _name(tag):
    if tag.startswith("{"):
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def map_id(raw):
    """Pinned convertID rule, deliberately without stripping URI attributes."""
    if raw.startswith(("smi:", "quakeml:")):
        return raw
    return PREFIX + raw.replace(":", "_").replace(" ", "_")


def _xslt_scalar(text):
    # xsl:strip-space removes whitespace-only text nodes, not padded nonblank values.
    return "" if not text.strip(" \t\r\n") else text


def _mapped_reference(text):
    # ID nodes use convertOptionalID, unlike @publicID's convertID.
    return map_id(_xslt_scalar(text) or "NA")


def _children(node, ns, local):
    return [c for c in node if c.tag == _tag(ns, local)]


def _one(node, ns, local, required=False):
    children = _children(node, ns, local)
    if len(children) > 1 or (required and not children):
        raise Unsupported("duplicate_or_missing_singleton:" + local)
    return children[0] if children else None


def _scalar(node, ns, local, required=False):
    child = _one(node, ns, local, required)
    if child is None:
        return None
    if len(child):
        raise Unsupported("non_scalar_field:" + local)
    return child.text or ""


def _value(node, ns, local):
    container = _one(node, ns, local)
    return None if container is None else _scalar(container, ns, "value")


def _identity(node, kind):
    raw = node.attrib.get("publicID")
    if raw is None or not raw:
        raise Unsupported("missing_object_identity:" + kind)
    if any(_name(a)[1] == "publicID" and a != "publicID" for a in node.attrib):
        raise Unsupported("foreign_identity_attribute")
    return raw


def time_us(text):
    """Aware ISO time in Python's bounded microsecond domain; invalid -> None."""
    if text is None or not text.strip():
        return None
    try:
        value = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
        if value.tzinfo is None or value.utcoffset() is None:
            return None
        value = value.astimezone(timezone.utc)
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        delta = value - epoch
        return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
    except (ValueError, OverflowError):
        return None


def canonical_decimal(text, depth_km=False):
    """Context-free exact decimal normalization; scaling never rounds/underflows."""
    if text is None or not text.strip():
        return None
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        return None
    if not value.is_finite():
        return None
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return "0"
    # Tuple arithmetic avoids Decimal's context-dependent normalize/multiply.
    exponent += 3 if depth_km else 0
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return str(Decimal((sign, tuple(digits), exponent)))


def _creation(node, ns, native):
    info = _one(node, ns, "creationInfo")
    result = dict.fromkeys(CREATION_FIELDS)
    if info is None:
        return result
    for field in CREATION_FIELDS:
        permitted = set(SCML.values()) if not native and field == "modificationTime" else {ns}
        candidates = [c for c in info if _name(c.tag)[1] == field]
        if len(candidates) > 1:
            raise Unsupported("duplicate_creation_field:" + field)
        if candidates:
            c = candidates[0]
            if _name(c.tag)[0] not in permitted or len(c):
                raise Unsupported("unsupported_creation_field:" + field)
            result[field] = c.text or ""
    return result


def _validate_tree(root, ns, native):
    count = 0
    stack = [(root, None, 1)]
    while stack:
        node, parent, depth = stack.pop()
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise Unsupported("xml_structure_limit")
        node_ns, local = _name(node.tag)
        expected = ns
        if not native and node is root:
            expected = QROOT
        extension = (not native and local == "modificationTime" and
                     node_ns in SCML.values() and parent is not None and
                     parent.tag == _tag(BED, "creationInfo"))
        if not native and local == "modificationTime" and not extension:
            raise Unsupported("unsupported_modificationTime_extension")
        if local in EVIDENCE_FIELDS and node_ns != expected and not extension:
            raise Unsupported("foreign_evidence_namespace:" + local)
        if any(_name(a)[1] in {"publicID", "networkCode", "stationCode", "channelCode", "locationCode"}
               and _name(a)[0] for a in node.attrib):
            raise Unsupported("foreign_evidence_attribute")
        stack.extend((c, node, depth + 1) for c in node)


def _pick(node, ns, native):
    raw_id = _identity(node, "pick")
    waveform = _one(node, ns, "waveformID")
    fields = {"network": "networkCode", "station": "stationCode", "location": "locationCode", "channel": "channelCode"}
    result = {k: (waveform.attrib.get(a, "") if waveform is not None else "") for k, a in fields.items()}
    for field in ("network", "station"):
        result[field] = result[field].strip()
    result.update({
        "pick_id": map_id(raw_id) if native else raw_id,
        "time": (_value(node, ns, "time") or "").strip(),
        "evaluation_mode": (_scalar(node, ns, "evaluationMode") or "").strip() or "missing",
        "evaluation_status": (_scalar(node, ns, "evaluationStatus") or "").strip() or "missing",
    })
    if native and _scalar(node, ns, "evaluationStatus") == "reported":
        result["evaluation_status"] = "missing"
    return result


def _arrival(node, ns, native):
    raw_pick = _scalar(node, ns, "pickID")
    phase = (_scalar(node, ns, "phase") or "").strip()
    flags = None
    if native:
        flags = {field: _scalar(node, ns, field) for field in ("weight", "timeUsed", "horizontalSlownessUsed", "backazimuthUsed")}
        truth = flags["timeUsed"] in {"true", "1"}
        no_flags = all(flags[k] is None for k in flags if k != "weight")
        if flags["weight"] is not None and (truth or no_flags):
            weight = _xslt_scalar(flags["weight"]).strip()
        elif flags["weight"] is None and truth:
            weight = "1"
        else:
            weight = None
        pick_id = _mapped_reference(raw_pick).strip() if raw_pick is not None else ""
    else:
        weight = _scalar(node, ns, "timeWeight")
        weight = None if weight is None else weight.strip()
        pick_id = (raw_pick or "").strip()
    return {"pick_id": pick_id, "phase": phase, "time_weight": weight, "native_flags": flags}


def _valid_weight(text):
    if text is None or not text:
        return True
    try:
        value = float(text)
        return math.isfinite(value) and value > 0
    except (ValueError, OverflowError):
        return False


def _unknown(requested, reason):
    return {"status": "unknown_representation", "event_id": requested,
            "reason": reason, "accepted_picks": None, "denominators": None,
            "picks": None, "arrivals": None, **CLAIMS}


def project(body: bytes, requested_event_id: str, format: str):
    """Project one bounded XML body into independent semantic evidence.

    format is 'qml' or 'scml'. No filenames, URLs, receipts, or clock anchors are
    accepted. Failure is unknown, never a parsed zero denominator.
    """
    if not isinstance(body, bytes) or not isinstance(requested_event_id, str):
        raise TypeError("bytes body and string event identity required")
    if format not in {"qml", "scml"}:
        raise ValueError("format must be qml or scml")
    if not requested_event_id or len(requested_event_id) > 4096:
        raise ValueError("bounded nonempty event identity required")
    try:
        if len(body) > MAX_BYTES:
            raise Unsupported("body_byte_limit")
        text = body.decode("utf-8")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise Unsupported("xml_declaration_forbidden")
        # Explicit non-UTF8 declarations cannot change caller bytes' interpretation.
        declaration = re.match(r"\ufeff?\s*<\?xml\s+[^?]*encoding\s*=\s*['\"]([^'\"]+)", text, re.I)
        if declaration and declaration.group(1).lower() not in {"utf-8", "utf8"}:
            raise Unsupported("unsupported_xml_encoding")
        root = ET.fromstring(text)
        native = format == "scml"
        if native:
            version = root.attrib.get("version")
            if version not in SCML or root.tag != _tag(SCML[version], "seiscomp"):
                raise Unsupported("unsupported_native_root_version")
            ns = SCML[version]
            version_label = "SCML" + version
            ep = _one(root, ns, "EventParameters", required=True)
        else:
            ns = BED
            version_label = "QML1.2"
            if root.tag != _tag(QROOT, "quakeml"):
                raise Unsupported("unsupported_qml_root")
            ep = _one(root, ns, "eventParameters", required=True)
        _validate_tree(root, ns, native)
        events = _children(ep, ns, "event")
        if len(events) != 1:
            raise Unsupported("event_cardinality")
        event = events[0]
        raw_event = _identity(event, "event")
        mapped_event = map_id(raw_event) if native else raw_event
        if mapped_event != map_id(requested_event_id):
            raise Unsupported("requested_event_identity_mismatch")
        raw_preferred = _scalar(event, ns, "preferredOriginID", required=True)
        preferred = (_mapped_reference(raw_preferred) if native else raw_preferred).strip()
        # Literal raw IDs determine native object scope BEFORE reference stripping.
        collisions = defaultdict(set)
        def register(raw, reference=False):
            # Empty ID nodes map to NA; object attributes use convertID directly.
            projected = _mapped_reference(raw) if reference else map_id(raw)
            collisions[projected].add(raw)
        if native:
            register(raw_event)
            references = _children(event, ns, "originReference")
            raw_refs = []
            for ref in references:
                if len(ref):
                    raise Unsupported("non_scalar_field:originReference")
                raw_refs.append(_xslt_scalar(ref.text or ""))
            if _xslt_scalar(raw_preferred) not in raw_refs:
                raise Unsupported("preferred_origin_outside_event_scope")
            origin_index = defaultdict(list)
            for origin in _children(ep, ns, "origin"):
                origin_index[origin.attrib.get("publicID")].append(origin)
            origins = []
            for ref in dict.fromkeys(raw_refs):
                register(ref, reference=True)
                matches = origin_index.get(ref, [])
                if len(matches) != 1:
                    raise Unsupported("missing_or_ambiguous_referenced_origin")
                origins.extend(matches)
            for origin in origins:
                register(_identity(origin, "origin"))
            amplitude_refs = []
            pick_refs = []
            for origin in origins:
                for arrival in _children(origin, ns, "arrival"):
                    # Validate all event-scoped arrivals, even in secondary origins.
                    _arrival(arrival, ns, True)
                    raw = _scalar(arrival, ns, "pickID")
                    if raw is not None:
                        pick_refs.append(_xslt_scalar(raw))
                for sm in _children(origin, ns, "stationMagnitude"):
                    raw = _scalar(sm, ns, "amplitudeID")
                    if raw is not None:
                        amplitude_refs.append(_xslt_scalar(raw))
            amplitudes = [a for a in _children(ep, ns, "amplitude") if a.attrib.get("publicID") in amplitude_refs]
            for raw in amplitude_refs:
                register(raw, reference=True)
            for amplitude in amplitudes:
                register(_identity(amplitude, "amplitude"))
                raw = _scalar(amplitude, ns, "pickID")
                if raw is not None:
                    pick_refs.append(_xslt_scalar(raw))
            for raw in pick_refs:
                register(raw, reference=True)
            picks = [p for p in _children(ep, ns, "pick") if p.attrib.get("publicID") in pick_refs]
            for pick in picks:
                register(_identity(pick, "pick"))
            register(_xslt_scalar(raw_preferred), reference=True)
            if any(len(values) > 1 for values in collisions.values()):
                raise Unsupported("native_id_mapping_collision")
        else:
            origins = _children(event, ns, "origin")
            picks = _children(event, ns, "pick")
            amplitudes = _children(event, ns, "amplitude")
        matching = [o for o in origins if (map_id(_identity(o, "origin")) if native else _identity(o, "origin")) == preferred]
        if len(matching) != 1:
            raise Unsupported("missing_or_ambiguous_projected_preferred_origin")
        origin = matching[0]
        for scoped_origin in origins:
            for field in ("time", "latitude", "longitude", "depth"):
                _value(scoped_origin, ns, field)
            _creation(scoped_origin, ns, native)
        arrivals = [_arrival(a, ns, native) for a in _children(origin, ns, "arrival")]
        pick_table = defaultdict(list)
        for pick in picks:
            record = _pick(pick, ns, native)
            pick_table[record["pick_id"]].append(record)
        qualifying = [a for a in arrivals if a["phase"] in {"P", "Pg", "Pn", "Pb"}]
        qualifying_ids = {a["pick_id"] for a in qualifying}
        resolved_ids = {pid for pid in qualifying_ids if pid and len(pick_table.get(pid, [])) == 1}
        accepted = {}
        reasons = Counter()
        decisions = []
        unresolved = set()
        for arrival in qualifying:
            pid = arrival["pick_id"]
            if pid not in resolved_ids:
                reason = "missing_or_ambiguous_pick_reference"
                unresolved.add(pid)
            elif not _valid_weight(arrival["time_weight"]):
                reason = "nonpositive_or_invalid_time_weight"
            else:
                pick = pick_table[pid][0]
                if pick["evaluation_status"] == "rejected":
                    reason = "rejected_pick_status"
                elif not pick["network"] or not pick["station"]:
                    reason = "missing_station_identity"
                elif time_us(pick["time"]) is None:
                    reason = "invalid_or_naive_pick_time"
                else:
                    reason = "accepted"
                    accepted.setdefault(pid, {**pick, "phase": arrival["phase"],
                                              "time": datetime.fromisoformat(pick["time"].replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()})
            decisions.append({"pick_id": pid, "disposition": reason})
            if reason != "accepted":
                reasons[reason] += 1
        incomplete = any(reasons[k] for k in ("missing_or_ambiguous_pick_reference", "missing_station_identity", "invalid_or_naive_pick_time"))
        return {
            "status": "ok", "event_id": requested_event_id, "version": version_label,
            "mapped_event_id": mapped_event, "preferred_origin_id": preferred,
            "raw_preferred_origin_id": raw_preferred,
            "event_creation": _creation(event, ns, native),
            "origin": {"time_us": time_us(_value(origin, ns, "time")),
                       "latitude": canonical_decimal(_value(origin, ns, "latitude")),
                       "longitude": canonical_decimal(_value(origin, ns, "longitude")),
                       "depth_m": canonical_decimal(_value(origin, ns, "depth"), native),
                       "creation": _creation(origin, ns, native)},
            "picks": dict(sorted(pick_table.items())), "arrivals": arrivals,
            "accepted_picks": [accepted[k] for k in sorted(accepted)],
            "qualifying_reference_decisions": decisions,
            "denominators": {"all_preferred_arrivals": len(arrivals),
                             "qualifying_P_references": len(qualifying),
                             "unique_qualifying_P_reference_ids": len(qualifying_ids),
                             "unique_resolved_qualifying_P_reference_ids": len(resolved_ids),
                             "accepted_P_picks": len(accepted),
                             "accepted_NZ_P_picks": sum(p["network"] == "NZ" for p in accepted.values()),
                             "event_scoped_pick_objects": len(picks),
                             "event_scoped_amplitude_objects": len(amplitudes)},
            "unresolved_pick_ids": sorted(unresolved), "reasons": dict(sorted(reasons.items())),
            "incomplete_associated_P_structure": incomplete,
            "NZ_coverage_known": bool(any(p["network"] == "NZ" for p in accepted.values())) or not incomplete,
            **CLAIMS,
        }
    except (Unsupported, UnicodeError, ET.ParseError, RecursionError) as exc:
        return _unknown(requested_event_id, str(exc))


def _arrival_signature(projection):
    return Counter((a["pick_id"], a["phase"], a["time_weight"]) for a in projection["arrivals"])


def _revision(left, right):
    a = [left["event_creation"], left["origin"]["creation"]]
    b = [right["event_creation"], right["origin"]["creation"]]
    if any(x[k] is not None and y[k] is not None and x[k] != y[k]
           for x, y in zip(a, b) for k in CREATION_FIELDS):
        return "known_conflict"
    recorded_times = [x[k] for x in a for k in ("creationTime", "modificationTime") if x[k] is not None]
    if a == b and recorded_times and all(time_us(value) is not None for value in recorded_times):
        return "matching_recorded_revision"
    return "missing_or_incomplete"


def compare(left: dict, right: dict):
    """Compare only two project() results; clock arithmetic belongs to the parent."""
    if left.get("status") != "ok" or right.get("status") != "ok":
        return {"available": False, "reason": "unknown_representation", **CLAIMS}
    identity = (left["mapped_event_id"], left["preferred_origin_id"]) == (right["mapped_event_id"], right["preferred_origin_id"])
    fields = ("time_us", "latitude", "longitude", "depth_m")
    complete = all(p["origin"][k] is not None for p in (left, right) for k in fields)
    content = complete and all(left["origin"][k] == right["origin"][k] for k in fields)
    arrivals = _arrival_signature(left) == _arrival_signature(right)
    revision = _revision(left, right)
    same = identity and content and arrivals and revision != "known_conflict"
    left_ids = {a["pick_id"] for a in left["arrivals"] if a["phase"] in {"P", "Pg", "Pn", "Pb"}}
    unique_left = {k for k, v in left["picks"].items() if len(v) == 1}
    unique_right = {k for k, v in right["picks"].items() if len(v) == 1}
    resolved = left_ids & (unique_right - unique_left)
    accepted_left = {p["pick_id"] for p in left["accepted_picks"]}
    nz_right = {p["pick_id"] for p in right["accepted_picks"] if p["network"] == "NZ"}
    recovered = left_ids & (nz_right - accepted_left)
    candidates = len(recovered) if same else 0
    return {"available": True, "identity_match": identity,
            "origin_fields_complete": complete, "origin_content_match": content,
            "arrival_multiset_match": arrivals, "revision_evidence": revision,
            "same_record_content": same,
            "newly_unique_reference_object_count": len(resolved),
            "newly_resolved_reference_count": len(resolved),
            "newly_accepted_NZ_reference_count": len(recovered),
            "content_matched_resolution_candidate_count": candidates,
            "paired_recorded_revision_resolution_count": candidates if revision == "matching_recorded_revision" else 0,
            **CLAIMS}

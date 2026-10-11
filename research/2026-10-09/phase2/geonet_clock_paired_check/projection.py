"""Source-derived QML/SCML shadow metadata; no author transform execution."""
import collections
import datetime as dt
import decimal
import hashlib
import json
import math
import xml.etree.ElementTree as ET

Q = "http://quakeml.org/xmlns/quakeml/1.2"
B = "http://quakeml.org/xmlns/bed/1.2"
SCML = {
    "0.13": "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.13",
    "0.14": "http://geofon.gfz.de/ns/seiscomp-schema/0.14",
}
PREFIX = "smi:nz.org.geonet/"
PHASES = {"P", "Pg", "Pn", "Pb"}
UNRESOLVED = {
    "missing_or_ambiguous_pick_reference",
    "invalid_or_naive_pick_time",
    "missing_station_identity",
}
MIB = 1024 * 1024
UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
CRITICAL = {
    "event", "origin", "pick", "arrival", "preferredOriginID",
    "originReference", "pickID", "waveformID", "phase", "timeWeight",
    "timeUsed", "horizontalSlownessUsed", "backazimuthUsed",
    "weight", "evaluationStatus", "evaluationMode", "time", "value",
    "latitude", "longitude", "depth", "creationInfo", "agencyID", "author",
    "creationTime", "modificationTime", "version", "agencyURI", "authorURI", "amplitude", "amplitudeID",
    "stationMagnitude", "EventParameters", "eventParameters",
}


class RepresentationError(ValueError):
    pass


def children(parent, name, namespace):
    return parent.findall("{" + namespace + "}" + name)


def singleton(parent, name, namespace, required=False):
    nodes = children(parent, name, namespace)
    if len(nodes) > 1:
        raise RepresentationError("duplicate_singleton:" + name)
    if required and not nodes:
        raise RepresentationError("missing_singleton:" + name)
    return nodes[0] if nodes else None


def scalar(parent, name, namespace, required=False, strip=True):
    node = singleton(parent, name, namespace, required)
    if node is None:
        return None
    if len(node):
        raise RepresentationError("non_scalar:" + name)
    value = node.text or ""
    return value.strip() if strip else value


def quantity(parent, name, namespace):
    node = singleton(parent, name, namespace)
    return scalar(node, "value", namespace) if node is not None else None


def number(value):
    try:
        if not math.isfinite(float(value)):
            return None
        result = decimal.Decimal(value)
    except (decimal.InvalidOperation, TypeError, ValueError, OverflowError):
        return None
    return result if result.is_finite() else None


def canonical_number(value, scale=1):
    parsed = number(value)
    if parsed is None or not math.isfinite(float(parsed) * scale):
        return None
    with decimal.localcontext() as context:
        context.prec = max(40, len(parsed.as_tuple().digits) + 10)
        context.traps[decimal.Inexact] = True
        try:
            return str((parsed * scale).normalize())
        except decimal.DecimalException:
            # Exponent limits must not collapse nonzero geometry into a
            # matching zero. Unsupported arithmetic remains unknown.
            return None


def utc(value):
    stamp = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("naive time")
    return stamp.astimezone(UTC)


def stamp_us(value):
    delta = utc(value) - EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def iso_us(value):
    return (EPOCH + dt.timedelta(microseconds=value)).isoformat()


def mapped_id(value):
    if not value or not value.strip():
        raise RepresentationError("missing_identity")
    if value.startswith(("smi:", "quakeml:")):
        return value
    return PREFIX + value.translate(str.maketrans({" ": "_", ":": "_"}))


def xml(body):
    if not isinstance(body, bytes) or len(body) > 4 * MIB:
        raise RepresentationError("body_bound")
    try:
        text = body.decode("utf-8-sig")
    except UnicodeError as exc:
        raise RepresentationError("unsupported_encoding") from exc
    if "\x00" in text or "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise RepresentationError("unsafe_XML")
    try:
        return ET.fromstring(text)
    except ET.ParseError as exc:
        raise RepresentationError("invalid_XML") from exc


def reject_foreign(root, namespace):
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter():
        local = node.tag.rsplit("}", 1)[-1]
        if local in CRITICAL and node.tag != "{" + namespace + "}" + local:
            # Both pinned GeoNet transforms intentionally retain native
            # modificationTime under BED creationInfo as a SCML extension.
            parent = parents.get(node)
            if (namespace == B and local == "modificationTime" and parent is not None and
                    parent.tag == "{" + B + "}creationInfo" and
                    node.tag in {"{" + value + "}modificationTime" for value in SCML.values()}):
                continue
            raise RepresentationError("foreign_structural_namespace")


def creation(parent, namespace):
    node = singleton(parent, "creationInfo", namespace)
    fields = ("agencyID", "agencyURI", "author", "authorURI", "creationTime", "modificationTime", "version")
    result = {key: scalar(node, key, namespace, strip=False) if node is not None else None
              for key in fields}
    if node is not None and namespace == B:
        modifications = children(node, "modificationTime", B)
        for native in SCML.values():
            modifications.extend(children(node, "modificationTime", native))
        if len(modifications) > 1:
            raise RepresentationError("duplicate_singleton:modificationTime")
        if modifications:
            if len(modifications[0]):
                raise RepresentationError("non_scalar:modificationTime")
            result["modificationTime"] = modifications[0].text or ""
    return result


def origin_metadata(origin, namespace, native=False):
    stamp = quantity(origin, "time", namespace)
    try:
        time_us = stamp_us(stamp)
    except (ValueError, TypeError, AttributeError, OverflowError):
        time_us = None
    return {
        "time_us": time_us,
        "latitude": canonical_number(quantity(origin, "latitude", namespace)),
        "longitude": canonical_number(quantity(origin, "longitude", namespace)),
        "depth_m": canonical_number(quantity(origin, "depth", namespace),
                                    1000 if native else 1),
        "creation": creation(origin, namespace),
    }


def pick_record(pick, namespace, identifier):
    waveform = singleton(pick, "waveformID", namespace)
    attrs = waveform.attrib if waveform is not None else {}
    return {
        "pick_id": identifier,
        "time": quantity(pick, "time", namespace),
        "network": attrs.get("networkCode", "").strip(),
        "station": attrs.get("stationCode", "").strip(),
        "location": attrs.get("locationCode", ""),
        "channel": attrs.get("channelCode", ""),
        "evaluation_status": scalar(pick, "evaluationStatus", namespace) or "missing",
        "evaluation_mode": scalar(pick, "evaluationMode", namespace) or "missing",
    }


def projected_weight(arrival, namespace):
    weight = scalar(arrival, "weight", namespace, strip=False)
    flags = {key: scalar(arrival, key, namespace, strip=False) for key in (
        "timeUsed", "horizontalSlownessUsed", "backazimuthUsed")}
    for value in flags.values():
        if value is not None and value.strip() not in ("true", "false", "1", "0"):
            raise RepresentationError("invalid_native_use_flag")
    time_used = flags["timeUsed"] in ("true", "1")
    no_flags = all(value is None for value in flags.values())
    if weight is not None and (time_used or no_flags):
        # XPath tests the flag's literal string; schema-valid surrounding
        # whitespace does not make it equal to 'true' in the pinned transform.
        # Only the resulting QML weight is stripped by the frozen predicate.
        result = weight.strip()
    elif weight is None and time_used:
        result = "1"
    else:
        result = None
    return result, {"weight": weight, **flags}


def qml_records(body, event_id):
    root = xml(body)
    if root.tag != "{" + Q + "}quakeml":
        raise RepresentationError("foreign_QML_root")
    reject_foreign(root, B)
    params = singleton(root, "eventParameters", B, True)
    events = children(params, "event", B)
    if len(events) != 1 or events[0].get("publicID") != mapped_id(event_id):
        raise RepresentationError("event_identity_or_cardinality")
    event = events[0]
    preferred = scalar(event, "preferredOriginID", B, True)
    origins = [node for node in children(event, "origin", B)
               if node.get("publicID") == preferred]
    if not preferred or len(origins) != 1:
        raise RepresentationError("preferred_origin_identity_or_cardinality")
    origin = origins[0]
    picks = collections.defaultdict(list)
    for node in children(event, "pick", B):
        identifier = node.get("publicID", "")
        picks[identifier].append(pick_record(node, B, identifier))
    arrivals = []
    for node in children(origin, "arrival", B):
        arrivals.append({
            "phase": scalar(node, "phase", B) or "",
            "pick_id": scalar(node, "pickID", B) or "",
            "time_weight": scalar(node, "timeWeight", B),
            "native_flags": None,
        })
    return {
        "event_id": event_id, "mapped_event_id": event.get("publicID"),
        "preferred_origin_id": preferred, "raw_preferred_origin_id": preferred,
        "origin": origin_metadata(origin, B), "event_creation": creation(event, B),
        "arrivals": arrivals, "picks": dict(picks), "version": "QML1.2",
    }


def scml_records(body, event_id):
    root = xml(body)
    version = root.get("version")
    namespace = SCML.get(version)
    if namespace is None or root.tag != "{" + namespace + "}seiscomp":
        raise RepresentationError("unsupported_or_ambiguous_SCML_version")
    reject_foreign(root, namespace)
    params = singleton(root, "EventParameters", namespace, True)
    events = children(params, "event", namespace)
    if len(events) != 1 or mapped_id(events[0].get("publicID", "")) != mapped_id(event_id):
        raise RepresentationError("event_identity_or_cardinality")
    event = events[0]
    preferred = scalar(event, "preferredOriginID", namespace, True, strip=False)
    references = []
    for node in children(event, "originReference", namespace):
        if len(node):
            raise RepresentationError("non_scalar:originReference")
        references.append(node.text or "")
    if not preferred or preferred not in references:
        raise RepresentationError("preferred_origin_not_event_referenced")
    origins = []
    for reference in set(references):
        matches = [node for node in children(params, "origin", namespace)
                   if node.get("publicID") == reference]
        if len(matches) != 1:
            raise RepresentationError("event_origin_reference_ambiguous")
        origins.append(matches[0])
    origin = next(node for node in origins if node.get("publicID") == preferred)
    # Object selection uses the native literal ID. The projected QML text
    # predicate strips reference text but leaves publicID attributes literal.
    if mapped_id(preferred).strip() != mapped_id(origin.get("publicID")):
        raise RepresentationError("projected_preferred_origin_unresolved")
    selected_pick_ids = set()
    amplitude_ids = set()
    for node in origins:
        for arrival in children(node, "arrival", namespace):
            selected_pick_ids.add(scalar(arrival, "pickID", namespace, strip=False) or "")
        for magnitude in children(node, "stationMagnitude", namespace):
            amplitude_ids.add(scalar(magnitude, "amplitudeID", namespace, strip=False) or "")
    for amplitude in children(params, "amplitude", namespace):
        if amplitude.get("publicID") in amplitude_ids:
            selected_pick_ids.add(scalar(amplitude, "pickID", namespace, strip=False) or "")
    picks = collections.defaultdict(list)
    raw_by_mapped = collections.defaultdict(set)
    raw_by_mapped[mapped_id(event.get("publicID"))].add(event.get("publicID"))
    for node in children(params, "pick", namespace):
        identifier = node.get("publicID")
        if identifier not in selected_pick_ids:
            continue
        converted = mapped_id(identifier)
        raw_by_mapped[converted].add(identifier)
        picks[converted].append(pick_record(node, namespace, converted))
    for reference in selected_pick_ids | set(references) | amplitude_ids:
        if reference:
            raw_by_mapped[mapped_id(reference)].add(reference)
    if any(len(values) > 1 for values in raw_by_mapped.values()):
        raise RepresentationError("ID_mapping_collision")
    arrivals = []
    for node in children(origin, "arrival", namespace):
        identifier = scalar(node, "pickID", namespace, strip=False) or ""
        weight, flags = projected_weight(node, namespace)
        arrivals.append({
            "phase": scalar(node, "phase", namespace) or "",
            "pick_id": mapped_id(identifier).strip() if identifier else "",
            "time_weight": weight, "native_flags": flags,
        })
    return {
        "event_id": event_id, "mapped_event_id": mapped_id(event.get("publicID")),
        "preferred_origin_id": mapped_id(preferred), "raw_preferred_origin_id": preferred,
        "origin": origin_metadata(origin, namespace, native=True),
        "event_creation": creation(event, namespace),
        "arrivals": arrivals, "picks": dict(picks), "version": "SCML" + version,
    }


def clock(picks, fixed_t0_us=None):
    earliest = {}
    for pick in picks:
        key = pick["network"] + "." + pick["station"]
        stamp = stamp_us(pick["time"])
        earliest[key] = min(stamp, earliest.get(key, stamp))
    t0 = min(earliest.values()) if earliest else None
    anchor = fixed_t0_us if fixed_t0_us is not None else t0
    return {
        "station_count": len(earliest), "t0_us": t0, "anchor_us": anchor,
        "strict_horizon_station_counts": {
            str(h): sum(stamp < anchor + h * 1000000 for stamp in earliest.values())
            if anchor is not None else None for h in (1, 3, 5)},
    }


def analyse(records):
    reasons = collections.Counter()
    accepted = []
    unresolved = []
    seen = set()
    qualifying = []
    for arrival in records["arrivals"]:
        phase, identifier = arrival["phase"], arrival["pick_id"]
        if phase not in PHASES:
            reasons["other_phase:" + phase] += 1
            continue
        qualifying.append(identifier)
        matches = records["picks"].get(identifier, [])
        if not identifier or len(matches) != 1:
            reasons["missing_or_ambiguous_pick_reference"] += 1
            unresolved.append(identifier)
            continue
        weight = arrival["time_weight"]
        # The frozen census uses finite binary float and rejects positive values
        # that underflow to zero; Decimal positivity must not widen that rule.
        if weight and (number(weight) is None or float(weight) <= 0):
            reasons["nonpositive_or_invalid_time_weight"] += 1
            continue
        pick = matches[0]
        if pick["evaluation_status"] == "rejected":
            reasons["rejected_pick"] += 1
            continue
        if not pick["network"] or not pick["station"]:
            reasons["missing_station_identity"] += 1
            continue
        try:
            stamp = utc(pick["time"])
        except (ValueError, TypeError, AttributeError, OverflowError):
            reasons["invalid_or_naive_pick_time"] += 1
            continue
        if identifier in seen:
            reasons["duplicate_accepted_arrival_reference"] += 1
            continue
        seen.add(identifier)
        if not weight:
            reasons["accepted_missing_time_weight"] += 1
        accepted.append({**pick, "phase": phase, "time": stamp.isoformat()})
    nz = [pick for pick in accepted if pick["network"] == "NZ"]
    incomplete = any(reasons[key] for key in UNRESOLVED)
    return {
        **records, "status": "ok", "reasons": dict(reasons),
        "accepted_picks": accepted, "unresolved_pick_ids": unresolved,
        "all_network": clock(accepted), "nz": clock(nz),
        "incomplete_associated_P_structure": incomplete,
        "NZ_coverage_known": bool(nz) or not incomplete,
        "denominators": {
            "all_preferred_arrivals": len(records["arrivals"]),
            "qualifying_P_references": len(qualifying),
            "unique_qualifying_P_reference_ids": len(set(qualifying)),
            "unique_resolved_qualifying_P_reference_ids":
                sum(bool(identifier) and len(records["picks"].get(identifier, [])) == 1
                    for identifier in set(qualifying)),
            "accepted_P_picks": len(accepted), "accepted_NZ_P_picks": len(nz),
        },
    }


def parse(body, event_id, representation):
    try:
        records = qml_records(body, event_id) if representation == "qml" else (
            scml_records(body, event_id) if representation == "scml" else None)
        if records is None:
            raise RepresentationError("unsupported_representation")
        return analyse(records)
    except RepresentationError as exc:
        return {"event_id": event_id, "status": "unknown_representation",
                "reason": str(exc), "denominators": None, "nz": None,
                "all_network": None, "accepted_picks": None}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()

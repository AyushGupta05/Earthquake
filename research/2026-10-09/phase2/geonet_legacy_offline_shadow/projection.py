"""Post-collection legacy compatibility hypothesis; pure bounded byte inputs.

No files, requests, schema validation or stylesheet execution. Raw fields and
source-derived candidates are distinct. This is not an operational clock.
"""
import collections
import datetime as dt
import decimal
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET

Q = "http://quakeml.org/xmlns/quakeml/1.2"
B = "http://quakeml.org/xmlns/bed/1.2"
SCML = {
    "0.10": "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.10",
    "0.11": "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.11",
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
    "stationMagnitude", "magnitude", "originID", "passedQC", "EventParameters", "eventParameters",
}


class RepresentationError(ValueError):
    pass


def xml_boolean_lexical(value):
    return re.sub(r"[ \t\r\n]+", " ", value).strip(" \t\r\n")


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


def quantity(parent, name, namespace, strip=True):
    node = singleton(parent, name, namespace)
    return scalar(node, "value", namespace, strip=strip) if node is not None else None


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


def source_id_candidate(value):
    value = value or "NA"
    return value if value.startswith(("smi:", "quakeml:")) else PREFIX + value.translate(str.maketrans({" ": "_", ":": "_"}))


def mapped_id(value):
    if not isinstance(value, str) or not value.strip() or value.strip() in ("NA", PREFIX + "NA"):
        # The optional-ID fallback is a placeholder, never correspondence.
        raise RepresentationError("missing_or_placeholder_identity")
    return source_id_candidate(value)


class BoundedTree(ET.TreeBuilder):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.count = 0

    def start(self, tag, attrs):
        self.depth += 1
        self.count += 1
        if self.depth > 64 or self.count > 100000:
            raise RepresentationError("XML_structure_bound")
        return super().start(tag, attrs)

    def end(self, tag):
        result = super().end(tag)
        self.depth -= 1
        return result


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
        return ET.fromstring(text, parser=ET.XMLParser(target=BoundedTree()))
    except ET.ParseError as exc:
        raise RepresentationError("invalid_XML") from exc


def reject_foreign(root, namespace, profile=None):
    parents = {child: parent for parent in root.iter() for child in parent}
    for node in root.iter():
        local = node.tag.rsplit("}", 1)[-1]
        if namespace == B and local in ("modificationTime", "passedQC"):
            parent = parents.get(node)
            if profile not in SCML:
                raise RepresentationError("version_extension_requires_bound_profile")
            if local == "passedQC" and profile == "0.10":
                raise RepresentationError("unsupported_010_passedQC")
            expected = SCML[profile]
            allowed_parents = ("creationInfo",) if local == "modificationTime" else ("stationMagnitude",)
            if parent is None or parent.tag not in {"{" + B + "}" + key for key in allowed_parents} or node.tag != "{" + expected + "}" + local:
                raise RepresentationError("unsupported_extension_namespace_or_placement")
            if local == "passedQC" and parents.get(parent) is not None and parents[parent].tag != "{" + B + "}event":
                raise RepresentationError("unsupported_extension_namespace_or_placement")
            if len(node) or sum(child.tag.rsplit("}", 1)[-1] == local for child in parent) != 1:
                raise RepresentationError("duplicate_or_non_scalar_extension:" + local)
            continue
        if namespace in SCML.values() and local in ("modificationTime", "passedQC"):
            parent = parents.get(node)
            if local == "passedQC" and namespace == SCML["0.10"]:
                raise RepresentationError("unsupported_010_passedQC")
            allowed_parents = ("creationInfo",) if local == "modificationTime" else ("stationMagnitude",)
            if parent is None or parent.tag not in {"{" + namespace + "}" + key for key in allowed_parents}:
                raise RepresentationError("unsupported_native_extension_placement")
            if local == "passedQC" and parents.get(parent) is not None and parents[parent].tag != "{" + namespace + "}origin":
                raise RepresentationError("unsupported_native_extension_placement")
            if len(node) or sum(child.tag.rsplit("}", 1)[-1] == local for child in parent) != 1:
                raise RepresentationError("duplicate_or_non_scalar_extension:" + local)
        if local in CRITICAL and node.tag != "{" + namespace + "}" + local:
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
    if namespace in SCML.values():
        for key in ("agencyURI", "authorURI"):
            if result[key] is not None:
                result[key] = source_id_candidate(result[key])
    return result


def raw_creation(parent, namespace):
    node = singleton(parent, "creationInfo", namespace)
    if node is None:
        return None
    return {child.tag: child.text or "" for child in node if child.tag.rsplit("}", 1)[-1] in (
        "agencyID", "agencyURI", "author", "authorURI", "creationTime", "modificationTime", "version")}


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
        "raw_creation": raw_creation(origin, namespace),
    }


def pick_record(pick, namespace, identifier):
    waveform = singleton(pick, "waveformID", namespace)
    attrs = waveform.attrib if waveform is not None else {}
    raw_status = scalar(pick, "evaluationStatus", namespace, strip=False)
    raw_mode = scalar(pick, "evaluationMode", namespace, strip=False)
    native = namespace in SCML.values()
    status = None if native and raw_status == "reported" else raw_status
    return {
        "pick_id": identifier,
        "raw_public_id": pick.get("publicID"),
        "time": quantity(pick, "time", namespace),
        "network": attrs.get("networkCode", "").strip(),
        "station": attrs.get("stationCode", "").strip(),
        "location": attrs.get("locationCode", ""),
        "channel": attrs.get("channelCode", ""),
        "evaluation_status": status.strip() if status and status.strip() else "missing",
        "evaluation_mode": raw_mode.strip() if raw_mode and raw_mode.strip() else "missing",
        "raw_evaluation_status": raw_status, "raw_evaluation_mode": raw_mode,
        "raw_time": quantity(pick, "time", namespace, strip=False),
        "reported_suppressed_candidate": native and raw_status == "reported",
    }


def projected_weight(arrival, namespace):
    weight = scalar(arrival, "weight", namespace, strip=False)
    flags = {key: scalar(arrival, key, namespace, strip=False) for key in (
        "timeUsed", "horizontalSlownessUsed", "backazimuthUsed")}
    for value in flags.values():
        if value is not None and xml_boolean_lexical(value) not in ("true", "false", "1", "0"):
            # Unrecognized boolean fields are unsupported, although the XSLT
            # literal comparison would be false. Do not invent schema validity.
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


def guard_registry(objects, native=False, outside_objects=()):
    """Ambiguous duplicate picks remain unresolved; cross-type IDs never match."""
    types = collections.defaultdict(set)
    raw_by_mapped = collections.defaultdict(set)
    for kind, node in objects:
        raw = node.get("publicID", "")
        identifier = mapped_id(raw) if native else checked_qml_id(raw)
        types[identifier].add(kind)
        raw_by_mapped[identifier].add(raw)
    scoped_candidates = set(types)
    outside_duplicate = False
    for kind, node in outside_objects:
        raw = node.get("publicID", "")
        try:
            identifier = mapped_id(raw) if native else checked_qml_id(raw)
        except RepresentationError:
            # Unrelated unsupported identities cannot taint the selected graph.
            continue
        if identifier in scoped_candidates:
            # Validate a colliding outside identity without projecting it.
            outside_duplicate |= kind in types[identifier] and raw in raw_by_mapped[identifier]
            types[identifier].add(kind)
            raw_by_mapped[identifier].add(raw)
    if any(len(value) > 1 for value in types.values()):
        raise RepresentationError("wrong_typed_publicID_collision")
    if any(len(value) > 1 for value in raw_by_mapped.values()):
        raise RepresentationError("ID_mapping_collision")
    if outside_duplicate:
        raise RepresentationError("outside_scope_duplicate_publicID")


def checked_qml_id(value):
    if not isinstance(value, str) or not value.strip() or value.strip() in ("NA", PREFIX + "NA"):
        raise RepresentationError("missing_or_placeholder_identity")
    return value


def magnitude_records(nodes, namespace, parent_origin_id=None):
    result = []
    for node in nodes:
        local = node.tag.rsplit("}", 1)[-1]
        raw_origin = scalar(node, "originID", namespace, strip=False)
        raw_id = node.get("publicID", "")
        qc_nodes = [child for child in node if child.tag.rsplit("}", 1)[-1] == "passedQC"]
        qc = qc_nodes[0] if qc_nodes else None
        if qc is not None and xml_boolean_lexical(qc.text or "") not in ("true", "false", "1", "0"):
            raise RepresentationError("invalid_passedQC_lexical")
        result.append({
            "kind": local, "raw_public_id": raw_id,
            "candidate_public_id": mapped_id(raw_id) if parent_origin_id is not None else checked_qml_id(raw_id),
            "raw_origin_id": raw_origin,
            "candidate_origin_id": source_id_candidate(raw_origin if raw_origin is not None else parent_origin_id)
                if parent_origin_id is not None else raw_origin,
            "origin_id_synthesized_candidate": parent_origin_id is not None and raw_origin is None,
            "passedQC": None if qc is None else {"tag": qc.tag, "raw": qc.text or ""},
        })
    return result


def qml_records(body, event_id, profile=None):
    if profile is not None and profile not in SCML:
        raise RepresentationError("unsupported_profile")
    root = xml(body)
    if root.tag != "{" + Q + "}quakeml":
        raise RepresentationError("foreign_QML_root")
    reject_foreign(root, B, profile)
    params = singleton(root, "eventParameters", B, True)
    events = children(params, "event", B)
    if len(events) != 1 or events[0].get("publicID") != mapped_id(event_id):
        raise RepresentationError("event_identity_or_cardinality")
    event = events[0]
    preferred = scalar(event, "preferredOriginID", B, True)
    checked_qml_id(preferred)
    all_origins = children(event, "origin", B)
    origins = [node for node in all_origins if node.get("publicID") == preferred]
    if len(origins) != 1:
        raise RepresentationError("preferred_origin_identity_or_cardinality")
    if len({node.get("publicID") for node in all_origins}) != len(all_origins):
        raise RepresentationError("duplicate_origin_publicID")
    origin = origins[0]
    all_picks = children(event, "pick", B)
    all_amplitudes = children(event, "amplitude", B)
    if len({node.get("publicID") for node in all_amplitudes}) != len(all_amplitudes):
        raise RepresentationError("ambiguous_amplitude_reference")
    magnitudes = children(event, "magnitude", B) + children(event, "stationMagnitude", B)
    scoped_arrivals = [node for item in all_origins for node in children(item, "arrival", B)
                      if "publicID" in node.attrib]
    scoped_objects = ([("event", event)] + [("origin", node) for node in all_origins] +
                   [("pick", node) for node in all_picks] + [("amplitude", node) for node in all_amplitudes] +
                   [(node.tag.rsplit("}", 1)[-1], node) for node in magnitudes] +
                   [("arrival", node) for node in scoped_arrivals])
    scoped_nodes = {node for _, node in scoped_objects}
    outside_objects = [(node.tag.rsplit("}", 1)[-1], node) for node in params.iter()
                       if node not in scoped_nodes and node.tag.startswith("{" + B + "}")
                       and "publicID" in node.attrib]
    guard_registry(scoped_objects, outside_objects=outside_objects)
    picks = collections.defaultdict(list)
    for node in all_picks:
        identifier = checked_qml_id(node.get("publicID", ""))
        picks[identifier].append(pick_record(node, B, identifier))
    arrivals = []
    for node in children(origin, "arrival", B):
        identifier = scalar(node, "pickID", B) or ""
        # Missing and placeholder references are retained as unresolved.
        if identifier in ("NA", PREFIX + "NA"):
            identifier = ""
        arrivals.append({"phase": scalar(node, "phase", B) or "", "pick_id": identifier,
                         "raw_public_id": node.get("publicID"),
                         "raw_pick_id": scalar(node, "pickID", B, strip=False),
                         "time_weight": scalar(node, "timeWeight", B), "native_flags": None})
    return {
        "event_id": event_id, "mapped_event_id": event.get("publicID"),
        "preferred_origin_id": preferred,
        "raw_preferred_origin_id": scalar(event, "preferredOriginID", B, True, strip=False),
        "origin": origin_metadata(origin, B), "event_creation": creation(event, B),
        "raw_event_creation": raw_creation(event, B),
        "arrivals": arrivals, "picks": dict(picks), "version": "QML1.2",
        "source_profile": profile, "scope": {"qml_event_pick_records": len(all_picks)},
        "magnitude_metadata": magnitude_records(magnitudes, B),
        "schema_validation_performed": False, "deployed_converter_verified": False,
    }


def scml_records(body, event_id, profile=None):
    root = xml(body)
    version = root.get("version")
    namespace = SCML.get(version)
    if namespace is None or root.tag != "{" + namespace + "}seiscomp":
        raise RepresentationError("unsupported_or_ambiguous_SCML_version")
    if profile is not None and profile != version:
        raise RepresentationError("profile_root_conflict")
    reject_foreign(root, namespace)
    params = singleton(root, "EventParameters", namespace, True)
    events = children(params, "event", namespace)
    if len(events) != 1 or events[0].get("publicID") != event_id:
        raise RepresentationError("event_identity_or_cardinality")
    event = events[0]
    preferred = scalar(event, "preferredOriginID", namespace, True, strip=False)
    mapped_id(preferred)
    references = []
    for node in children(event, "originReference", namespace):
        if len(node):
            raise RepresentationError("non_scalar:originReference")
        raw = node.text or ""
        mapped_id(raw)
        references.append(raw)
    if preferred not in references:
        raise RepresentationError("preferred_origin_not_event_referenced")
    origins = []
    origins_by_id = collections.defaultdict(list)
    for node in children(params, "origin", namespace):
        origins_by_id[node.get("publicID")].append(node)
    for reference in sorted(set(references)):
        matches = origins_by_id.get(reference, [])
        if len(matches) != 1:
            raise RepresentationError("event_origin_reference_ambiguous")
        origins.append(matches[0])
    origin = next(node for node in origins if node.get("publicID") == preferred)
    if mapped_id(preferred).strip() != mapped_id(origin.get("publicID")):
        raise RepresentationError("projected_preferred_origin_unresolved")
    arrival_pick_ids, amplitude_ids = set(), set()
    amplitude_multiplicity = collections.Counter()
    mags = []
    magnitude_meta = []
    for node in origins:
        for arrival in children(node, "arrival", namespace):
            arrival_pick_ids.add(scalar(arrival, "pickID", namespace, strip=False) or "")
        own_mags = children(node, "magnitude", namespace) + children(node, "stationMagnitude", namespace)
        mags.extend(own_mags)
        magnitude_meta.extend(magnitude_records(own_mags, namespace, node.get("publicID")))
        for magnitude in children(node, "stationMagnitude", namespace):
            ref = scalar(magnitude, "amplitudeID", namespace, strip=False) or ""
            if ref and ref.strip() not in ("NA", PREFIX + "NA"):
                amplitude_ids.add(ref)
                amplitude_multiplicity[ref] += 1
    selected_amplitudes = [node for node in children(params, "amplitude", namespace) if node.get("publicID") in amplitude_ids]
    if len({node.get("publicID") for node in selected_amplitudes}) != len(selected_amplitudes):
        raise RepresentationError("ambiguous_amplitude_reference")
    amplitude_pick_ids = {scalar(node, "pickID", namespace, strip=False) or "" for node in selected_amplitudes}
    selected_pick_ids = arrival_pick_ids | amplitude_pick_ids
    selected_picks = [node for node in children(params, "pick", namespace) if node.get("publicID") in selected_pick_ids]
    scoped_objects = ([("event", event)] + [("origin", node) for node in origins] +
                   [("pick", node) for node in selected_picks] + [("amplitude", node) for node in selected_amplitudes] +
                   [(node.tag.rsplit("}", 1)[-1], node) for node in mags])
    scoped_nodes = {node for _, node in scoped_objects}
    outside_objects = [(node.tag.rsplit("}", 1)[-1], node) for node in params.iter()
                       if node not in scoped_nodes and node.tag.startswith("{" + namespace + "}")
                       and "publicID" in node.attrib]
    guard_registry(scoped_objects, native=True, outside_objects=outside_objects)
    raw_by_mapped = collections.defaultdict(set)
    for reference in selected_pick_ids | set(references) | amplitude_ids:
        if reference and reference.strip() not in ("NA", PREFIX + "NA"):
            raw_by_mapped[mapped_id(reference)].add(reference)
    if any(len(values) > 1 for values in raw_by_mapped.values()):
        raise RepresentationError("ID_mapping_collision")
    picks = collections.defaultdict(list)
    for node in selected_picks:
        identifier = node.get("publicID", "")
        converted = mapped_id(identifier)
        record = pick_record(node, namespace, converted)
        record["selection_paths"] = [name for name, values in (
            ("arrival", arrival_pick_ids), ("amplitude", amplitude_pick_ids)) if identifier in values]
        picks[converted].append(record)
    arrivals = []
    raw_pick_multiplicity = collections.Counter(node.get("publicID") for node in selected_picks)
    for node in children(origin, "arrival", namespace):
        identifier = scalar(node, "pickID", namespace, strip=False) or ""
        weight, flags = projected_weight(node, namespace)
        placeholder = not identifier.strip() or identifier.strip() in ("NA", PREFIX + "NA")
        arrivals.append({"phase": scalar(node, "phase", namespace) or "",
                         "pick_id": "" if placeholder else mapped_id(identifier).strip(),
                         "raw_public_id": node.get("publicID"),
                         "raw_pick_id": identifier, "time_weight": weight, "native_flags": flags,
                         "native_raw_reference_matches": raw_pick_multiplicity[identifier]})
    scope = {
        "raw_origin_reference_count": len(references), "unique_referenced_origins": len(origins),
        "selected_pick_records": len(selected_picks),
        "outside_scope_pick_records": len(children(params, "pick", namespace)) - len(selected_picks),
        "outside_scope_origin_records": len(children(params, "origin", namespace)) - len(origins),
        "selected_amplitude_records": len(selected_amplitudes),
        "unresolved_amplitude_reference_count": len(amplitude_ids - {node.get("publicID") for node in selected_amplitudes}),
        "candidate_emitted_amplitude_records": sum(amplitude_multiplicity[node.get("publicID")]
            for node in selected_amplitudes if singleton(node, "amplitude", namespace) is not None),
        "selected_amplitude_without_value_count": sum(singleton(node, "amplitude", namespace) is None for node in selected_amplitudes),
    }
    return {
        "event_id": event_id, "mapped_event_id": mapped_id(event.get("publicID")),
        "preferred_origin_id": mapped_id(preferred), "raw_preferred_origin_id": preferred,
        "origin": origin_metadata(origin, namespace, native=True),
        "event_creation": creation(event, namespace), "raw_event_creation": raw_creation(event, namespace),
        "arrivals": arrivals, "picks": dict(picks), "version": "SCML" + version,
        "source_profile": version, "scope": scope, "magnitude_metadata": magnitude_meta,
        "schema_validation_performed": False, "deployed_converter_verified": False,
    }


def clock(picks, fixed_t0_us=None):
    earliest = {}
    for pick in picks:
        key = (pick["network"], pick["station"])
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
    resolved_qualifying = set()
    for arrival in records["arrivals"]:
        phase, identifier = arrival["phase"], arrival["pick_id"]
        if phase not in PHASES:
            reasons["other_phase:" + phase] += 1
            continue
        qualifying.append(identifier)
        matches = records["picks"].get(identifier, [])
        if not identifier or len(matches) != 1 or arrival.get("native_raw_reference_matches", 1) != 1:
            reasons["missing_or_ambiguous_pick_reference"] += 1
            unresolved.append(identifier)
            continue
        resolved_qualifying.add(identifier)
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
                len(resolved_qualifying),
            "accepted_P_picks": len(accepted), "accepted_NZ_P_picks": len(nz),
        },
    }


def project(body, event_id, representation, profile=None):
    try:
        records = qml_records(body, event_id, profile) if representation == "qml" else (
            scml_records(body, event_id, profile) if representation == "scml" else None)
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

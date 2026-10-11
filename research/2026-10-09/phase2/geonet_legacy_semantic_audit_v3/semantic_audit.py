"""Independent, bounded legacy metadata semantics. No I/O, acquisition, XSLT, or producer imports.

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
    "0.10": "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.10",
    "0.11": "http://geofon.gfz-potsdam.de/ns/seiscomp3-schema/0.11",
}
PREFIX = "smi:nz.org.geonet/"
MAX_BYTES = 4 * 1024 * 1024
MAX_ELEMENTS = 100000
MAX_DEPTH = 64
CREATION_FIELDS = ("agencyID", "agencyURI", "author", "authorURI", "creationTime", "modificationTime", "version")
EVIDENCE_FIELDS = frozenset({
    "quakeml", "seiscomp", "eventParameters", "EventParameters", "event",
    "pick", "origin", "arrival", "amplitude", "stationMagnitude", "originReference", "originID", "passedQC",
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
    "original_frozen_result_rewritten": False,
    "original_clocks_changed": False,
    "new_requests_made": False,
    "QML_converter_profile_verified": False,
    "full_XML_schema_validity_verified": False,
    "deployed_converter_verified": False,
}


class Unsupported(ValueError):
    """Structural evidence cannot be interpreted unambiguously."""


class _DeclarationGuard(ET.TreeBuilder):
    """Reject a real DOCTYPE before Expat reads its internal subset."""

    def doctype(self, name, pubid, system):
        raise Unsupported("xml_declaration_forbidden")


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
    if raw in {"NA", PREFIX + "NA"}:
        raise Unsupported("placeholder_object_identity:" + kind)
    if any(_name(a)[1] == "publicID" and a != "publicID" for a in node.attrib):
        raise Unsupported("foreign_identity_attribute")
    return raw


def _scoped_identity_check(event, origins, picks, amplitudes, station_magnitudes, native):
    """Keep duplicate picks unresolved, but never conflate scoped object types."""
    identities = defaultdict(list)
    for kind, nodes in (("event", [event]), ("origin", origins), ("pick", picks),
                        ("amplitude", amplitudes), ("stationMagnitude", station_magnitudes)):
        for node in nodes:
            if kind == "stationMagnitude" and node.attrib.get("publicID") in {None, "", "NA", PREFIX + "NA"}:
                # Missing optional correspondence annotations cannot become identities.
                continue
            raw = _identity(node, kind)
            identities[map_id(raw) if native else raw].append((kind, raw))
    for rows in identities.values():
        if len({kind for kind, _ in rows}) > 1:
            raise Unsupported("cross_type_scoped_identity")
        if len({raw for _, raw in rows}) > 1:
            raise Unsupported("native_id_mapping_collision")
        if len(rows) > 1 and rows[0][0] != "pick":
            raise Unsupported("duplicate_scoped_identity:" + rows[0][0])


def _global_identity_check(root, selected_nodes, native, scoped_picks):
    """Outside objects never expand scope, but cannot conceal ID ambiguity."""
    selected = set(selected_nodes)
    scoped_pick_nodes = set(scoped_picks)
    index = defaultdict(list)
    for node in root.iter():
        raw = node.attrib.get("publicID")
        if raw is not None:
            index[map_id(raw) if native else raw].append((node, raw, _name(node.tag)[1]))
    for rows in index.values():
        if not any(node in selected for node, _, _ in rows):
            continue
        if any(node not in selected for node, _, _ in rows):
            raise Unsupported("outside_scope_" + ("native" if native else "qml") + "_identity_ambiguity")
        if len({raw for _, raw, _ in rows}) > 1:
            raise Unsupported("native_id_mapping_collision")
        if len({kind for _, _, kind in rows}) > 1:
            raise Unsupported("cross_type_scoped_identity")
        if len(rows) > 1 and not (rows[0][2] == "pick" and
                                  all(node in scoped_pick_nodes for node, _, _ in rows)):
            raise Unsupported("duplicate_scoped_identity:" + rows[0][2])


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
    try:
        scaled = Decimal((sign, tuple(digits), exponent))
        return str(scaled) if scaled.is_finite() else None
    except InvalidOperation:
        # Scaling can exceed the constructor's exponent domain without rounding.
        return None


def _creation(node, ns, native, profile, raw=False):
    info = _one(node, ns, "creationInfo")
    result = dict.fromkeys(CREATION_FIELDS)
    if info is None:
        return result
    for field in CREATION_FIELDS:
        permitted = {SCML[profile]} if not native and field == "modificationTime" and profile else {ns}
        candidates = [c for c in info if _name(c.tag)[1] == field]
        if len(candidates) > 1:
            raise Unsupported("duplicate_creation_field:" + field)
        if candidates:
            c = candidates[0]
            if _name(c.tag)[0] not in permitted or len(c):
                raise Unsupported("unsupported_creation_field:" + field)
            value = c.text or ""
            result[field] = (value if raw or not native else
                             _mapped_reference(value) if field in {"agencyURI", "authorURI"} else
                             _xslt_scalar(value))
    return result


def _validate_tree(root, ns, native, profile):
    count = 0
    extensions = []
    stack = [(root, None, None, 1)]
    while stack:
        node, parent, grandparent, depth = stack.pop()
        count += 1
        if count > MAX_ELEMENTS or depth > MAX_DEPTH:
            raise Unsupported("xml_structure_limit")
        if not isinstance(node.tag, str):
            # Discarding these nodes could merge text across XSLT whitespace boundaries.
            raise Unsupported("comment_or_processing_instruction_not_supported")
        if "{http://www.w3.org/XML/1998/namespace}space" in node.attrib:
            # Inherited preservation would invalidate the scalar strip-space model.
            raise Unsupported("xml_space_not_supported")
        node_ns, local = _name(node.tag)
        expected = QROOT if not native and node is root else ns
        modification = (local == "modificationTime" and parent is not None and
                        parent.tag == _tag(ns, "creationInfo"))
        passed_qc = (local == "passedQC" and parent is not None and grandparent is not None and
                     parent.tag == _tag(ns, "stationMagnitude") and
                     grandparent.tag == _tag(ns, "origin" if native else "event"))
        allowed_extension = False
        if local in {"modificationTime", "passedQC"}:
            if local == "passedQC" and profile == "0.10":
                # Generic XSLT fallback exists, but the pinned closed0.10 XSD excludes it.
                raise Unsupported("passedQC_not_supported_by_profile_010")
            if len(node):
                raise Unsupported("non_scalar_legacy_extension:" + local)
            if local == "passedQC" and (node.text or "").strip(" \t\r\n") not in {"true", "false", "1", "0"}:
                raise Unsupported("invalid_passedQC_boolean_lexical_value")
            if native:
                valid = node_ns == ns and (modification if local == "modificationTime" else passed_qc)
            else:
                if profile is None:
                    raise Unsupported("legacy_extension_requires_explicit_profile:" + local)
                valid = ((modification and node_ns == SCML[profile]) if local == "modificationTime" else
                         (passed_qc and node_ns == (BED if profile == "0.10" else SCML[profile])))
                allowed_extension = valid
            if not valid:
                raise Unsupported("unsupported_legacy_extension_placement_or_profile:" + local)
            extensions.append({"field": local, "namespace": node_ns,
                               "parent": _name(parent.tag)[1], "text": node.text or "",
                               "conditional_source_profile": profile,
                               "schema_membership_verified": False,
                               "passed_qc_boolean_candidate_validated": local == "passedQC"})
        if node_ns != expected and not allowed_extension:
            raise Unsupported("foreign_evidence_namespace:" + local)
        if any(_name(a)[1] in {"publicID", "networkCode", "stationCode", "channelCode", "locationCode"}
               and _name(a)[0] for a in node.attrib):
            raise Unsupported("foreign_evidence_attribute")
        if local == "creationInfo":
            for field in CREATION_FIELDS:
                matches = [c for c in node if _name(c.tag)[1] == field]
                if len(matches) > 1:
                    raise Unsupported("duplicate_creation_field:" + field)
        if local == "stationMagnitude":
            matches = [c for c in node if _name(c.tag)[1] == "passedQC"]
            if len(matches) > 1:
                raise Unsupported("duplicate_legacy_extension:passedQC")
        stack.extend((c, node, parent, depth + 1) for c in reversed(list(node)))
    return extensions


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
        "raw_public_id": raw_id,
        "raw_evaluation_status": _scalar(node, ns, "evaluationStatus"),
        "raw_time": _value(node, ns, "time"),
    })
    if native and _scalar(node, ns, "evaluationStatus") == "reported":
        result["evaluation_status"] = "missing"
    return result


def _arrival(node, ns, native):
    opposite_fields = (("timeWeight", "horizontalSlownessWeight", "backazimuthWeight") if native else
                       ("weight", "timeUsed", "horizontalSlownessUsed", "backazimuthUsed"))
    if any(_children(node, ns, field) for field in opposite_fields):
        raise Unsupported("mixed_arrival_weight_vocabulary")
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
    projected_weights = {"timeWeight": weight}
    if native:
        for flag, target in (("horizontalSlownessUsed", "horizontalSlownessWeight"), ("backazimuthUsed", "backazimuthWeight")):
            projected_weights[target] = ((_xslt_scalar(flags["weight"]).strip() if flags["weight"] is not None else "1")
                                         if flags[flag] in {"true", "1"} else None)
    return {"pick_id": pick_id, "phase": phase, "time_weight": weight, "native_flags": flags,
            "raw_pick_id": raw_pick, "raw_phase": _scalar(node, ns, "phase"),
            "reference_identity_known": bool(raw_pick and _xslt_scalar(raw_pick)) and
                                        pick_id != PREFIX + "NA",
            "projected_weights": projected_weights,
            "native_use_flag_states": ({k: ("absent" if flags[k] is None else "true" if flags[k] in {"true", "1"} else
                                                     "false" if flags[k] in {"false", "0"} else "unrecognized")
                                        for k in ("timeUsed", "horizontalSlownessUsed", "backazimuthUsed")} if native else None)}


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


def project(body: bytes, requested_event_id: str, format: str, profile: str | None = None):
    """Project one bounded XML body into independent semantic evidence.

    format is 'qml' or 'scml'. QML legacy fields require explicit0.10/.11 profile.
    No filenames, URLs, receipts, or clock anchors are
    accepted. Failure is unknown, never a parsed zero denominator.
    """
    if not isinstance(body, bytes) or not isinstance(requested_event_id, str):
        raise TypeError("bytes body and string event identity required")
    if format not in {"qml", "scml"}:
        raise ValueError("format must be qml or scml")
    if profile is not None and profile not in SCML:
        raise ValueError("profile must be 0.10, 0.11 or None")
    if not requested_event_id or len(requested_event_id) > 4096:
        raise ValueError("bounded nonempty event identity required")
    try:
        if len(body) > MAX_BYTES:
            raise Unsupported("body_byte_limit")
        text = body.decode("utf-8")
        # Explicit non-UTF8 declarations cannot change caller bytes' interpretation.
        declaration = re.match(r"\ufeff?\s*<\?xml\s+[^?]*encoding\s*=\s*['\"]([^'\"]+)", text, re.I)
        if declaration and declaration.group(1).lower() not in {"utf-8", "utf8"}:
            raise Unsupported("unsupported_xml_encoding")
        root = ET.fromstring(text, parser=ET.XMLParser(
            target=_DeclarationGuard(insert_comments=True, insert_pis=True)))
        native = format == "scml"
        if native:
            version = root.attrib.get("version")
            if version not in SCML or root.tag != _tag(SCML[version], "seiscomp"):
                raise Unsupported("unsupported_native_root_version")
            if profile is not None and profile != version:
                raise Unsupported("native_profile_root_mismatch")
            profile = version
            ns = SCML[version]
            version_label = "SCML" + version
            ep = _one(root, ns, "EventParameters", required=True)
        else:
            ns = BED
            version_label = "QML1.2"
            if root.tag != _tag(QROOT, "quakeml"):
                raise Unsupported("unsupported_qml_root")
            ep = _one(root, ns, "eventParameters", required=True)
        extensions = _validate_tree(root, ns, native, profile)
        events = _children(ep, ns, "event")
        if len(events) != 1:
            raise Unsupported("event_cardinality")
        event = events[0]
        raw_event = _identity(event, "event")
        if native and raw_event != requested_event_id:
            raise Unsupported("requested_raw_native_event_identity_mismatch")
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
            scope_paths = []
            station_magnitudes = []
            amplitude_links = []
            for origin in origins:
                for arrival_ordinal, arrival in enumerate(_children(origin, ns, "arrival")):
                    # Validate all event-scoped arrivals, even in secondary origins.
                    _arrival(arrival, ns, True)
                    raw = _scalar(arrival, ns, "pickID")
                    if raw is not None:
                        pick_refs.append(_xslt_scalar(raw))
                        scope_paths.append({"route": "arrival", "raw_pick_id": raw,
                            "raw_origin_id": origin.attrib.get("publicID"), "arrival_ordinal": arrival_ordinal})
                for sm_ordinal, sm in enumerate(_children(origin, ns, "stationMagnitude")):
                    raw = _scalar(sm, ns, "amplitudeID")
                    raw_origin_id = _scalar(sm, ns, "originID")
                    qc = _scalar(sm, ns, "passedQC")
                    raw_sm_id = sm.attrib.get("publicID")
                    station_magnitudes.append({"raw_public_id": raw_sm_id,
                        "identity_correspondence_known": bool(raw_sm_id and raw_sm_id not in {"NA", PREFIX + "NA"}),
                        "projected_public_id": map_id(raw_sm_id) if raw_sm_id and raw_sm_id not in {"NA", PREFIX + "NA"} else None,
                        "raw_parent_origin_id": origin.attrib.get("publicID"),
                        "raw_origin_id": raw_origin_id,
                        "projected_origin_id": (_mapped_reference(raw_origin_id) if raw_origin_id is not None else
                                                 map_id(_identity(origin, "origin"))),
                        "origin_id_synthesized": raw_origin_id is None,
                        "raw_amplitude_id": raw, "passed_qc": qc,
                        "passed_qc_projected_namespace": BED if profile == "0.10" else ns,
                        "station_magnitude_ordinal": sm_ordinal})
                    if raw_sm_id and raw_sm_id not in {"NA", PREFIX + "NA"}:
                        register(raw_sm_id)
                    if raw is not None:
                        amplitude_refs.append(_xslt_scalar(raw))
                        amplitude_links.append({"raw_amplitude_id": raw,
                            "raw_origin_id": origin.attrib.get("publicID"),
                            "raw_station_magnitude_id": raw_sm_id, "station_magnitude_ordinal": sm_ordinal})
            sm_ids = [s["raw_public_id"] for s in station_magnitudes if s["identity_correspondence_known"]]
            if len(set(sm_ids)) != len(sm_ids):
                raise Unsupported("duplicate_station_magnitude_identity")
            amplitudes = [a for a in _children(ep, ns, "amplitude") if a.attrib.get("publicID") in amplitude_refs]
            for raw in amplitude_refs:
                register(raw, reference=True)
            amplitude_index = defaultdict(list)
            for amplitude in amplitudes:
                amplitude_index[amplitude.attrib.get("publicID")].append(amplitude)
            for amplitude_ref in set(amplitude_refs):
                if len(amplitude_index.get(amplitude_ref, [])) != 1:
                    raise Unsupported("missing_or_ambiguous_referenced_amplitude")
            for amplitude in amplitudes:
                register(_identity(amplitude, "amplitude"))
                raw = _scalar(amplitude, ns, "pickID")
                if raw is not None:
                    pick_refs.append(_xslt_scalar(raw))
                    for link in amplitude_links:
                        if _xslt_scalar(link["raw_amplitude_id"]) == amplitude.attrib.get("publicID"):
                            scope_paths.append({"route": "amplitude", "raw_pick_id": raw, **link})
            for raw in pick_refs:
                register(raw, reference=True)
            picks = [p for p in _children(ep, ns, "pick") if p.attrib.get("publicID") in pick_refs]
            for pick in picks:
                register(_identity(pick, "pick"))
            register(_xslt_scalar(raw_preferred), reference=True)
            if any(len(values) > 1 for values in collisions.values()):
                raise Unsupported("native_id_mapping_collision")
            scope = {"raw_origin_references": raw_refs, "pick_scope_paths": scope_paths,
                     "station_magnitudes": station_magnitudes,
                     "amplitudes": [{"raw_public_id": a.attrib.get("publicID"),
                                     "raw_pick_id": _scalar(a, ns, "pickID"),
                                     "has_amplitude_value_child": _one(a, ns, "amplitude") is not None,
                                     "source_mapping_emission_count": sum(_xslt_scalar(link["raw_amplitude_id"]) == a.attrib.get("publicID") for link in amplitude_links)
                                          if _one(a, ns, "amplitude") is not None else 0}
                                    for a in amplitudes],
                     "outside_scope_pick_ids": [p.attrib.get("publicID") for p in _children(ep, ns, "pick") if p not in picks],
                     "outside_scope_origin_ids": [o.attrib.get("publicID") for o in _children(ep, ns, "origin") if o not in origins]}
        else:
            scope = None
            origins = _children(event, ns, "origin")
            picks = _children(event, ns, "pick")
            amplitudes = _children(event, ns, "amplitude")
        matching = [o for o in origins if (map_id(_identity(o, "origin")) if native else _identity(o, "origin")) == preferred]
        if len(matching) != 1:
            raise Unsupported("missing_or_ambiguous_projected_preferred_origin")
        origin = matching[0]
        scoped_sm = ([sm for o in origins for sm in _children(o, ns, "stationMagnitude")]
                     if native else _children(event, ns, "stationMagnitude"))
        _scoped_identity_check(event, origins, picks, amplitudes, scoped_sm, native)
        if native:
            selected_nodes = [n for container in [event, *origins, *picks, *amplitudes]
                              for n in container.iter() if "publicID" in n.attrib]
            _global_identity_check(root, selected_nodes, True, picks)
        if not native:
            _global_identity_check(root, [n for n in event.iter() if "publicID" in n.attrib], False, picks)
            amplitude_index = defaultdict(list)
            for amplitude in amplitudes:
                amplitude_index[_identity(amplitude, "amplitude")].append(amplitude)
            for sm in scoped_sm:
                ref = _scalar(sm, ns, "amplitudeID")
                if ref is not None and len(amplitude_index.get(ref.strip(), [])) != 1:
                    raise Unsupported("missing_or_ambiguous_referenced_amplitude")
        for scoped_origin in origins:
            for field in ("time", "latitude", "longitude", "depth"):
                _value(scoped_origin, ns, field)
            _creation(scoped_origin, ns, native, profile)
            for scoped_arrival in _children(scoped_origin, ns, "arrival"):
                _arrival(scoped_arrival, ns, native)
        arrivals = [_arrival(a, ns, native) for a in _children(origin, ns, "arrival")]
        pick_table = defaultdict(list)
        for pick in picks:
            record = _pick(pick, ns, native)
            pick_table[record["pick_id"]].append(record)
        raw_pick_table = defaultdict(list)
        for pick in picks:
            raw_pick_table[pick.attrib["publicID"]].append(pick)
        for arrival in arrivals:
            # Trimming a mapped QML reference cannot establish a missing raw link.
            targets = (raw_pick_table.get(_xslt_scalar(arrival["raw_pick_id"] or ""), []) if native else
                       pick_table.get(arrival["pick_id"], []))
            projected_targets = pick_table.get(arrival["pick_id"], [])
            same_target = (len(targets) == len(projected_targets) == 1 and
                           (not native or targets[0].attrib["publicID"] == projected_targets[0]["raw_public_id"]))
            # Compare literal target multisets even if neither side is unique.
            raw_target_ids = Counter(p.attrib["publicID"] for p in targets) if native else Counter()
            projected_target_ids = Counter(p["raw_public_id"] for p in projected_targets)
            mapped_raw_reference = _mapped_reference(arrival["raw_pick_id"] or "") if native else ""
            arrival["native_reference_mapping_ambiguity"] = (native and
                (raw_target_ids != projected_target_ids or mapped_raw_reference != mapped_raw_reference.strip()))
            arrival["reference_identity_known"] = arrival["reference_identity_known"] and same_target
        qualifying = [a for a in arrivals if a["phase"] in {"P", "Pg", "Pn", "Pb"}]
        qualifying_ids = {a["pick_id"] for a in qualifying}
        resolved_ids = {a["pick_id"] for a in qualifying if a["reference_identity_known"] and
                        a["pick_id"] and a["pick_id"] != PREFIX + "NA" and len(pick_table.get(a["pick_id"], [])) == 1}
        accepted = {}
        reasons = Counter()
        decisions = []
        unresolved = set()
        for arrival in qualifying:
            pid = arrival["pick_id"]
            if not arrival["reference_identity_known"] or pid not in resolved_ids:
                reason = "missing_or_ambiguous_pick_reference"
                unresolved.add(pid)
            elif not _valid_weight(arrival["time_weight"]):
                reason = "nonpositive_or_invalid_time_weight"
            else:
                pick = pick_table[pid][0]
                if pick["evaluation_status"] == "rejected":
                    reason = "rejected_pick_status"
                # Frozen public predicate checks station before aware time.
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
            "legacy_profile": profile, "legacy_extensions": extensions,
            "conditional_source_mapping_only": True,
            "native_reference_mapping_ambiguity": any(a["native_reference_mapping_ambiguity"] for a in arrivals),
            "raw_event_id": raw_event, "native_scope": scope,
            "mapped_event_id": mapped_event, "preferred_origin_id": preferred,
            "raw_preferred_origin_id": raw_preferred,
            "event_creation": _creation(event, ns, native, profile),
            "raw_event_creation": _creation(event, ns, native, profile, raw=True),
            "origin": {"time_us": time_us(_value(origin, ns, "time")),
                       "latitude": canonical_decimal(_value(origin, ns, "latitude")),
                       "longitude": canonical_decimal(_value(origin, ns, "longitude")),
                       "depth_m": canonical_decimal(_value(origin, ns, "depth"), native),
                       "creation": _creation(origin, ns, native, profile),
                       "raw_creation": _creation(origin, ns, native, profile, raw=True)},
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


def _finite_arrival_signature(projection):
    rows = []
    for arrival in projection["arrivals"]:
        text = arrival["time_weight"]
        if text is None or not text:
            key = None
        else:
            try:
                value = float(text)
            except (ValueError, OverflowError):
                return None
            if not math.isfinite(value):
                return None
            key = value.hex()
        rows.append((arrival["pick_id"], arrival["phase"], key))
    return Counter(rows)


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
    profile_match = (left["legacy_profile"] is None or right["legacy_profile"] is None or left["legacy_profile"] == right["legacy_profile"])
    reference_mapping_match = not (left["native_reference_mapping_ambiguity"] or right["native_reference_mapping_ambiguity"])
    identity = (left["mapped_event_id"], left["preferred_origin_id"]) == (right["mapped_event_id"], right["preferred_origin_id"])
    fields = ("time_us", "latitude", "longitude", "depth_m")
    complete = all(p["origin"][k] is not None for p in (left, right) for k in fields)
    content = complete and all(left["origin"][k] == right["origin"][k] for k in fields)
    arrivals = _arrival_signature(left) == _arrival_signature(right)
    finite_left, finite_right = _finite_arrival_signature(left), _finite_arrival_signature(right)
    finite_arrivals = None if finite_left is None or finite_right is None else finite_left == finite_right
    revision = _revision(left, right)
    same = profile_match and reference_mapping_match and identity and content and arrivals and revision != "known_conflict"
    left_ids = {a["pick_id"] for a in left["arrivals"] if a["phase"] in {"P", "Pg", "Pn", "Pb"}}
    unique_left = {k for k, v in left["picks"].items() if len(v) == 1}
    unique_right = {k for k, v in right["picks"].items() if len(v) == 1}
    unique_recovery = left_ids & (unique_right - unique_left)
    accepted_left = {p["pick_id"] for p in left["accepted_picks"]}
    accepted_right = {p["pick_id"] for p in right["accepted_picks"]}
    resolved = left_ids & (accepted_right - accepted_left)
    nz_right = {p["pick_id"] for p in right["accepted_picks"] if p["network"] == "NZ"}
    recovered = left_ids & (nz_right - accepted_left)
    candidates = len(recovered) if same else 0
    return {"available": True, "identity_match": identity,
            "source_profile_consistency": profile_match,
            "reference_mapping_consistency": reference_mapping_match,
            "conditional_source_mapping_only": True,
            "origin_fields_complete": complete, "origin_content_match": content,
            "arrival_multiset_match": arrivals, "arrival_multiset_lexical_match": arrivals,
            "arrival_multiset_finite_canonical_match": finite_arrivals,
            "revision_evidence": revision,
            "recorded_revision_guard_policy": "all_present_times_aware_nonempty",
            "same_record_content": same,
            "newly_unique_reference_object_count": len(unique_recovery),
            "newly_resolved_reference_count": len(resolved),
            "newly_accepted_NZ_reference_count": len(recovered),
            "content_matched_resolution_candidate_count": candidates,
            "paired_recorded_revision_resolution_count": candidates if revision == "matching_recorded_revision" else 0,
            **CLAIMS}

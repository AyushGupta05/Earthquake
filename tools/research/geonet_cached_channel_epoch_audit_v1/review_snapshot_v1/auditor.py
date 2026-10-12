"""Pure, bounded cached StationXML metadata census; no acquisition or decoding."""
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import re
import xml.etree.ElementTree as ET

NS = "http://www.fdsn.org/xml/station/1"
TAG = "{" + NS + "}"
ROLES = ("ordinary", "higher", "boundary", "final")
HORIZONS = (1, 3, 5)
MAX_DOCUMENT = 128 * 1024
MAX_TOTAL = 512 * 1024
MAX_NODES = 4096
MAX_DEPTH = 32
MIN_NS, MAX_NS = -(2**63), 2**63 - 1
PROPOSAL_SHA256 = "0705ffa3edd1e31d4e4f802b52598a1f008646775b0771bc3a00e6333292769b"
SLOT_KEYS = frozenset((
    "slot_id", "network", "station", "location", "prefix", "t0_ns",
    "body_sha256", "individual_http200_complete", "custody_verified",
    "source_run_complete", "request_level", "request_network", "request_station",
    "request_location", "request_channel", "request_start_ns", "request_end_ns",
))
CLAIMS = {name: False for name in (
    "full_xsd_validation", "complete_failed96_run", "archive_holdings_verified",
    "physical_absence_verified", "measured_axes_verified", "full_response_verified",
    "response_calibration_verified", "waveform_continuity_verified",
    "online_timing_verified", "model_gain_verified", "novelty_verified",
)}
_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})\Z", re.ASCII)


def parse_ns(value):
    """Parse an explicit-zone dateTime to exact signed-64 UTC nanoseconds."""
    if type(value) is not str:
        raise ValueError("date_type")
    m = _DATE.fullmatch(value)
    if not m:
        raise ValueError("unsupported_date")
    year, month, day, hour, minute, second = map(int, m.group(1, 2, 3, 4, 5, 6))
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("unsupported_clock")
    zone = m.group(8)
    offset = 0
    if zone != "Z":
        zh, zm = int(zone[1:3]), int(zone[4:6])
        if zh > 14 or zm > 59 or (zh == 14 and zm != 0):
            raise ValueError("unsupported_zone")
        offset = (zh * 60 + zm) * 60 * (1 if zone[0] == "+" else -1)
    days = (date(year, month, day) - date(1970, 1, 1)).days
    seconds = days * 86400 + hour * 3600 + minute * 60 + second - offset
    ns = seconds * 10**9 + int((m.group(7) or "").ljust(9, "0") or "0")
    if not MIN_NS <= ns <= MAX_NS:
        raise ValueError("date_outside_signed64")
    return ns


def validate_slots(slots):
    if type(slots) is not list or len(slots) != 4:
        raise ValueError("exactly_four_slots_required")
    for role, s in zip(ROLES, slots):
        if type(s) is not dict or set(s) != SLOT_KEYS or s["slot_id"] != role:
            raise ValueError("slot_schema_or_order")
        for field in ("network", "station"):
            if type(s[field]) is not str or not re.fullmatch(r"[A-Z0-9]{1,8}", s[field], re.ASCII):
                raise ValueError("literal_identity")
        if type(s["location"]) is not str or not re.fullmatch(r"[A-Z0-9]{0,8}", s["location"], re.ASCII):
            raise ValueError("literal_location")
        if type(s["prefix"]) is not str or not re.fullmatch(r"[A-Z0-9]{2}", s["prefix"], re.ASCII):
            raise ValueError("literal_prefix")
        if type(s["t0_ns"]) is not int or not MIN_NS + 5*10**9 <= s["t0_ns"] <= MAX_NS - 5*10**9:
            raise ValueError("t0_signed64_margin")
        for field in ("individual_http200_complete", "custody_verified", "source_run_complete"):
            if type(s[field]) is not bool:
                raise ValueError("custody_boolean")
        if s["source_run_complete"] is not False:
            raise ValueError("incomplete_source_provenance_required")
        pin = s["body_sha256"]
        if pin is not None and (type(pin) is not str or not re.fullmatch(r"[a-f0-9]{64}", pin, re.ASCII)):
            raise ValueError("body_pin")
        if s["request_level"] != "channel" or type(s["request_level"]) is not str:
            raise ValueError("request_level")
        for field in ("network", "station", "location"):
            if s["request_" + field] != s[field] or type(s["request_" + field]) is not str:
                raise ValueError("request_scope")
        if s["request_channel"] != s["prefix"] + "?" or type(s["request_channel"]) is not str:
            raise ValueError("request_prefix_scope")
        for field, delta in (("request_start_ns", -5), ("request_end_ns", 5)):
            if type(s[field]) is not int or s[field] != s["t0_ns"] + delta*10**9:
                raise ValueError("request_time_scope")


def _epoch(node):
    raw_start, raw_end = node.get("startDate"), node.get("endDate")
    result = {"raw_start": raw_start, "raw_end": raw_end, "start_ns": None,
              "end_ns": None, "end_open": raw_end is None, "valid": False, "reason": None}
    try:
        if raw_start is None:
            raise ValueError("missing_start")
        result["start_ns"] = parse_ns(raw_start)
        if raw_end is not None:
            result["end_ns"] = parse_ns(raw_end)
            if result["end_ns"] <= result["start_ns"]:
                raise ValueError("nonpositive_epoch")
        result["valid"] = True
    except ValueError as error:
        result["reason"] = str(error)
    return result


def _ambiguous(epochs):
    if any(not e["valid"] for e in epochs):
        return "invalid_or_missing_epoch"
    ordered = sorted(epochs, key=lambda e: e["start_ns"])
    for previous, current in zip(ordered, ordered[1:]):
        if previous["end_ns"] is None or previous["end_ns"] > current["start_ns"]:
            return "duplicate_or_overlapping_epochs"
    return None


def _contains(epoch, left, right):
    if not epoch["valid"]:
        return "unknown"
    start, end = epoch["start_ns"], epoch["end_ns"]
    # Exact equality to either window edge is retained as boundary ambiguity.
    if start in (left, right) or end in (left, right):
        return "boundary_unknown"
    if start < left and (end is None or end > right):
        return "supported"
    return "not_supported"


def _numeric(node, field, minimum=None, maximum=None, *, positive=False):
    found = node.findall(TAG + field)
    raw = [x.text for x in found]
    result = {"present": bool(found), "raw": raw, "valid": False, "exact_decimal": None}
    if len(found) != 1 or len(found[0]) or found[0].text is None:
        return result
    try:
        value = Decimal(found[0].text.strip())
        if not value.is_finite() or (positive and value <= 0) or (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            return result
        result.update(valid=True, exact_decimal=str(value))
    except InvalidOperation:
        pass
    return result


def _units(node, field):
    groups = node.findall(TAG + field)
    if len(groups) != 1:
        return {"present": bool(groups), "valid": False, "name": None}
    names = groups[0].findall(TAG + "Name")
    valid = len(names) == 1 and not len(names[0]) and names[0].text is not None and bool(names[0].text.strip())
    return {"present": True, "valid": valid, "name": names[0].text if valid else None}


def _response(channel):
    responses = channel.findall(TAG + "Response")
    result = {"present": bool(responses), "response_count": len(responses),
              "stage_count": sum(len(x.findall(TAG + "Stage")) for x in responses),
              "sensitivity_present": False, "sensitivity_count": 0,
              "sensitivity_value": None, "input_units": None, "output_units": None}
    sensitivities = [s for r in responses for s in r.findall(TAG + "InstrumentSensitivity")]
    result["sensitivity_present"] = bool(sensitivities)
    result["sensitivity_count"] = len(sensitivities)
    if len(responses) == 1 and len(sensitivities) == 1:
        s = sensitivities[0]
        result.update(sensitivity_value=_numeric(s, "Value"), input_units=_units(s, "InputUnits"), output_units=_units(s, "OutputUnits"))
    return result


def _parse(data):
    text = data.decode("utf-8-sig", errors="strict")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
        raise ValueError("dtd_or_entity_declaration")
    rest = text
    if re.match(r"<\?xml\s", rest):
        end = rest.find("?>")
        if end < 0:
            raise ValueError("bad_xml_declaration")
        declaration, rest = rest[:end + 2], rest[end + 2:]
        encoding = re.search(r"encoding\s*=\s*(['\"])(.*?)\1", declaration)
        if encoding and encoding.group(2).lower() not in ("utf-8", "utf8"):
            raise ValueError("unsupported_encoding")
    if "<?" in rest:
        raise ValueError("processing_instruction")
    root = ET.fromstring(text)
    count = 0
    pending = [(root, 1, None)]
    while pending:
        node, depth, parent = pending.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ValueError("node_or_depth_cap")
        if type(node.tag) is not str or not node.tag.startswith(TAG):
            raise ValueError("unsupported_namespace")
        local = node.tag[len(TAG):]
        required_parent = {"FDSNStationXML": None, "Network": "FDSNStationXML", "Station": "Network", "Channel": "Station"}
        if local in required_parent and parent != required_parent[local]:
            raise ValueError("unsupported_hierarchy")
        pending.extend((child, depth + 1, local) for child in node)
    if root.tag != TAG + "FDSNStationXML" or root.get("schemaVersion") not in ("1.0", "1.1", "1.2"):
        raise ValueError("root_or_schema_version")
    # Only the inspected hierarchy and descriptive fields are validated, not XSD.
    for node in root.iter():
        local = node.tag[len(TAG):]
        if local in ("Network", "Station", "Channel") and node.get("code") is None:
            raise ValueError("missing_hierarchy_code")
        if local == "Channel" and node.get("locationCode") is None:
            raise ValueError("missing_location_code")
    return root, count


def _document_row(data, slot):
    row = {"slot_id": slot["slot_id"], "t0_ns": slot["t0_ns"],
           "scope": {k: slot[k] for k in ("network", "station", "location", "prefix")},
           "expected_sha256": slot["body_sha256"], "observed_sha256": None,
           "bytes": None, "document_state": "unknown", "reason": None,
           "source_run_complete": False, "schema_version": None, "node_count": None,
           "channels": [], "literal_codes": []}
    if data is None:
        row["reason"] = "missing_cached_document"
        return row
    row["bytes"] = len(data)
    row["observed_sha256"] = hashlib.sha256(data).hexdigest()
    if len(data) > MAX_DOCUMENT:
        row["reason"] = "document_byte_cap"
        return row
    if not slot["individual_http200_complete"] or not slot["custody_verified"] or row["observed_sha256"] != slot["body_sha256"]:
        row["reason"] = "positive_individual_custody_not_verified"
        return row
    try:
        root, nodes = _parse(data)
    except (ValueError, UnicodeError, ET.ParseError, RecursionError) as error:
        row["reason"] = "unsupported_cached_xml:" + str(error)
        return row
    row.update(schema_version=root.get("schemaVersion"), node_count=nodes)
    networks = [n for n in root.findall(TAG + "Network") if n.get("code") == slot["network"]]
    stations = [(n, s) for n in networks for s in n.findall(TAG + "Station") if s.get("code") == slot["station"]]
    matches = [(n, s, c) for n, s in stations for c in s.findall(TAG + "Channel")
               if c.get("locationCode") == slot["location"] and
               re.fullmatch(re.escape(slot["prefix"]) + r"[A-Z0-9]", c.get("code", ""), re.ASCII)]
    if not matches:
        row["reason"] = "literal_scope_not_present_unknown_completeness"
        return row
    row["document_state"] = "valid"
    network_ambiguity = _ambiguous([_epoch(n) for n in networks])
    station_ambiguity = _ambiguous([_epoch(s) for _, s in stations])
    codes = sorted({c.get("code") for _, _, c in matches})
    row["literal_codes"] = codes
    for code in codes:
        records = []
        for n, s, c in matches:
            if c.get("code") == code:
                records.append({"channel_epoch": _epoch(c), "station_epoch": _epoch(s), "network_epoch": _epoch(n),
                                "azimuth": _numeric(c, "Azimuth", Decimal(0), Decimal(360)),
                                "dip": _numeric(c, "Dip", Decimal(-90), Decimal(90)),
                                "sample_rate": _numeric(c, "SampleRate", positive=True),
                                "response": _response(c)})
        ambiguity = network_ambiguity or station_ambiguity or _ambiguous([r["channel_epoch"] for r in records])
        states = {}
        for h in HORIZONS:
            left, right = slot["t0_ns"] - 3*10**9, slot["t0_ns"] + h*10**9
            if ambiguity:
                states[str(h)] = "unknown"
                continue
            record_states = []
            for r in records:
                parts = [_contains(r[field], left, right) for field in ("channel_epoch", "station_epoch", "network_epoch")]
                if "unknown" in parts:
                    record_states.append("unknown")
                elif "not_supported" in parts:
                    record_states.append("not_supported")
                elif "boundary_unknown" in parts:
                    record_states.append("boundary_unknown")
                else:
                    record_states.append("supported")
            if record_states.count("supported") == 1:
                states[str(h)] = "supported"
            elif "unknown" in record_states:
                states[str(h)] = "unknown"
            elif "boundary_unknown" in record_states:
                states[str(h)] = "boundary_unknown"
            else:
                states[str(h)] = "not_supported"
        row["channels"].append({"code": code, "location": slot["location"],
                                "suffix_kind": code[-1] if code[-1] in "EN12" else "other",
                                "ambiguity": ambiguity, "epochs": records, "horizon_support": states})
    return row


def audit(documents, slots):
    """Return four private rows and identifier-free descriptive aggregate counts."""
    validate_slots(slots)
    if type(documents) is not list or len(documents) != 4 or any(d is not None and type(d) is not bytes for d in documents):
        raise ValueError("four_bytes_or_none_documents_required")
    total = sum(len(d) for d in documents if d is not None)
    if total > MAX_TOTAL:
        rows = [_document_row(None, s) for s in slots]
        for row, data in zip(rows, documents):
            row["bytes"] = len(data) if data is not None else None
            row["reason"] = "total_document_byte_cap"
    else:
        rows = [_document_row(d, s) for d, s in zip(documents, slots)]
    public = {"protocol": "geonet-cached-channel-epoch-audit-v1", "proposal_sha256": PROPOSAL_SHA256,
              "fixed_slots": 4, "valid_scope_documents": sum(r["document_state"] == "valid" for r in rows),
              "unknown_documents": sum(r["document_state"] == "unknown" for r in rows),
              "literal_suffix_document_presence": {k: 0 for k in ("E", "N", "1", "2", "other")},
              "literal_channel_count": 0, "epoch_record_count": 0,
              "epoch_support_by_horizon": {str(h): {k: 0 for k in ("supported", "not_supported", "boundary_unknown", "unknown")} for h in HORIZONS},
              "orientation_field_presence": {"azimuth": 0, "dip": 0},
              "orientation_field_valid": {"azimuth": 0, "dip": 0},
              "sample_rate_present": 0, "sample_rate_valid": 0,
              "response_fragment_epochs": 0, "response_stage_count": 0,
              "sensitivity_epochs": 0, "claims": dict(CLAIMS)}
    for row in rows:
        for kind in {c["suffix_kind"] for c in row["channels"]}:
            public["literal_suffix_document_presence"][kind] += 1
        public["literal_channel_count"] += len(row["channels"])
        for channel in row["channels"]:
            for h, state in channel["horizon_support"].items():
                public["epoch_support_by_horizon"][h][state] += 1
            for record in channel["epochs"]:
                public["epoch_record_count"] += 1
                for name in ("azimuth", "dip"):
                    public["orientation_field_presence"][name] += int(record[name]["present"])
                    public["orientation_field_valid"][name] += int(record[name]["valid"])
                public["sample_rate_present"] += int(record["sample_rate"]["present"])
                public["sample_rate_valid"] += int(record["sample_rate"]["valid"])
                public["response_fragment_epochs"] += int(record["response"]["present"])
                public["response_stage_count"] += record["response"]["stage_count"]
                public["sensitivity_epochs"] += int(record["response"]["sensitivity_present"])
    return {"private_rows": rows, "public_counts": public}

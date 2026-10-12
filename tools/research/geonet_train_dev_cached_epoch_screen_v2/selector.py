"""Pure deterministic original-order TRAIN/DEV selector; no cached input."""
import json
import re

PROTOCOL = "geonet-train-dev-cached-channel-epoch-v2"
PROTOCOL_SHA256 = "66b14ad5c594075b0490cec6be166877e22391060f8d0b72c654a66b26ec8a99"
MIN_NS, MAX_NS = -(2**63), 2**63-1
MAX_JSON_INPUT = 262144
TOP_KEYS = frozenset(("protocol", "original_plan_sha256", "source_run_complete", "excluded_TEST_count", "rows"))
ROW_KEYS = frozenset(("row_index", "original_event_index", "partition", "event_id", "t0_ns", "targets"))
ROSTER_ROW_KEYS = frozenset(("row_index", "original_event_index", "partition", "event_id", "t0_ns", "selected_target_index", "selected_target"))
TARGET_KEYS = frozenset(("target_index", "network", "station", "location", "prefix", "pick_ns", "queryable", "unqueryable_reason"))


def keys(value, expected):
    if type(value) is not dict or any(type(k) is not str for k in value) or set(value) != expected:
        raise ValueError("exact_dictionary_schema_required")


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("exact_integer_out_of_bounds")


def digest(value, *, nullable=False):
    if nullable and value is None:
        return
    if type(value) is not str or not re.fullmatch(r"[a-f0-9]{64}", value, re.ASCII):
        raise ValueError("lowercase_sha256_required")


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def bounded_json(value, maximum):
    # Count encoded chunks without materializing an amplified private JSON string.
    encoder = json.JSONEncoder(sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
    total = 0
    for piece in encoder.iterencode(value):
        total += len(piece.encode("utf-8"))
        if total > maximum:
            raise ValueError("json_byte_cap")


def _top(value):
    keys(value, TOP_KEYS)
    if type(value["protocol"]) is not str or value["protocol"] != PROTOCOL:
        raise ValueError("protocol_mismatch")
    digest(value["original_plan_sha256"])
    if value["source_run_complete"] is not False:
        raise ValueError("failed_whole_run_provenance_required")
    integer(value["excluded_TEST_count"], 31, 31)
    if type(value["rows"]) is not list or len(value["rows"]) != 65:
        raise ValueError("exactly_65_rows_required")


def _row_identity(row, index, previous, seen):
    integer(row["row_index"], index, index)
    integer(row["original_event_index"], 0, 95)
    if row["original_event_index"] <= previous:
        raise ValueError("original_event_order_required")
    if type(row["partition"]) is not str or row["partition"] not in ("TRAIN", "DEV"):
        raise ValueError("TRAIN_DEV_only")
    event = row["event_id"]
    if type(event) is not str or not re.fullmatch(r"[\x20-\x7e]{1,128}", event, re.ASCII) or event in seen:
        raise ValueError("unique_printable_event_identity_required")
    seen.add(event)
    if row["t0_ns"] is not None:
        integer(row["t0_ns"], MIN_NS+5*10**9, MAX_NS-5*10**9)
    return row["original_event_index"]


def target(value, index, t0):
    keys(value, TARGET_KEYS)
    integer(value["target_index"], index, index)
    integer(value["pick_ns"], MIN_NS, MAX_NS)
    if type(value["queryable"]) is not bool:
        raise ValueError("exact_queryable_boolean_required")
    for field in ("network", "station", "location", "prefix"):
        if type(value[field]) is not str or len(value[field]) > 128:
            raise ValueError("bounded_literal_identity_required")
    reason = value["unqueryable_reason"]
    if reason is not None and (type(reason) is not str or len(reason) > 128):
        raise ValueError("bounded_unqueryable_reason_required")
    if value["queryable"]:
        if t0 is None or reason is not None:
            raise ValueError("queryable_t0_and_reason_required")
        for field in ("network", "station"):
            if not re.fullmatch(r"[A-Z0-9]{1,8}", value[field], re.ASCII):
                raise ValueError("queryable_literal_identity")
        if not re.fullmatch(r"[A-Z0-9]{0,8}", value["location"], re.ASCII) or not re.fullmatch(r"[A-Z0-9]{2}", value["prefix"], re.ASCII):
            raise ValueError("queryable_literal_scope")


def _counts(rows):
    if sum(r["partition"] == "TRAIN" for r in rows) != 41 or sum(r["partition"] == "DEV" for r in rows) != 24:
        raise ValueError("exact_41_TRAIN_24_DEV_required")


def validate_projection(projection):
    _top(projection)
    seen, previous = set(), -1
    for index, row in enumerate(projection["rows"]):
        keys(row, ROW_KEYS)
        previous = _row_identity(row, index, previous, seen)
        if type(row["targets"]) is not list or len(row["targets"]) > 8:
            raise ValueError("original_target_list_cap")
        for ti, item in enumerate(row["targets"]):
            target(item, ti, row["t0_ns"])
    _counts(projection["rows"])
    bounded_json(projection, MAX_JSON_INPUT)


def validate_roster(roster):
    _top(roster)
    seen, previous = set(), -1
    for index, row in enumerate(roster["rows"]):
        keys(row, ROSTER_ROW_KEYS)
        previous = _row_identity(row, index, previous, seen)
        ti, item = row["selected_target_index"], row["selected_target"]
        if ti is None:
            if item is not None:
                raise ValueError("nullable_selected_target_pair")
        else:
            integer(ti, 0, 7)
            target(item, ti, row["t0_ns"])
            if item["queryable"] is not True:
                raise ValueError("selected_target_must_be_queryable")
    _counts(roster["rows"])
    bounded_json(roster, MAX_JSON_INPUT)


def select(projection):
    """Freeze first original queryable target, with all 65 rows retained."""
    validate_projection(projection)
    rows = []
    for row in projection["rows"]:
        selected = next((t for t in row["targets"] if t["queryable"] is True), None)
        result = {k: row[k] for k in ("row_index", "original_event_index", "partition", "event_id", "t0_ns")}
        result.update(selected_target_index=selected["target_index"] if selected is not None else None,
                      selected_target=dict(selected) if selected is not None else None)
        rows.append(result)
    result = {k: projection[k] for k in ("protocol", "original_plan_sha256", "source_run_complete", "excluded_TEST_count")}
    result["rows"] = rows
    bounded_json(result, MAX_JSON_INPUT)
    return result

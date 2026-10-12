"""Pure fixed-65 cached metadata screen. No acquisition, reads or waveform decode."""
from decimal import Decimal
import hashlib
import selector as s
import v1_reference as v1

select = s.select
PROTOCOL = s.PROTOCOL
MAX_BODY = 131072
MAX_TOTAL = 8519680
MAX_PRIVATE_JSON = 67108864
MAX_PUBLIC_JSON = 65536
STATES = ("no_queryable_target", "missing_exact_cache", "HTTP204", "failed", "unattempted", "unverified_custody", "positive_cached_HTTP200")
EVIDENCE_KEYS = frozenset(("row_index", "state", "body_bytes", "body_sha256", "individual_http200_complete", "custody_verified", "request"))
REQUEST_KEYS = frozenset(("level", "network", "station", "location", "channel", "start_ns", "end_ns"))
CLAIMS = {name: False for name in (
    "failed96_completion", "full_xsd_validation", "actual_axes", "waveform_rate_lattice_continuity",
    "archive_holdings", "physical_absence", "full_response", "calibration", "online_timing",
    "sequence_independence", "usable_training_cohort", "accuracy_improvement", "novelty", "published_benchmark_superiority",
)}


def _request(request, row):
    s.keys(request, REQUEST_KEYS)
    target = row["selected_target"]
    if target is None:
        raise ValueError("request_without_selected_target")
    expected = dict(level="channel", network=target["network"], station=target["station"],
                    location=target["location"], channel=target["prefix"] + "?",
                    start_ns=row["t0_ns"]-5*10**9, end_ns=row["t0_ns"]+5*10**9)
    for field in ("level", "network", "station", "location", "channel"):
        if type(request[field]) is not str or request[field] != expected[field]:
            raise ValueError("original_literal_request_scope_required")
    for field in ("start_ns", "end_ns"):
        s.integer(request[field], expected[field], expected[field])


def validate_evidence(evidence, roster):
    if type(evidence) is not list or len(evidence) != 65:
        raise ValueError("exactly_65_evidence_rows_required")
    for index, (item, row) in enumerate(zip(evidence, roster["rows"])):
        s.keys(item, EVIDENCE_KEYS)
        s.integer(item["row_index"], index, index)
        if type(item["state"]) is not str or item["state"] not in STATES:
            raise ValueError("exact_input_state_required")
        if item["body_bytes"] is not None:
            s.integer(item["body_bytes"], 0, 4*1024*1024)
        s.digest(item["body_sha256"], nullable=True)
        for field in ("individual_http200_complete", "custody_verified"):
            if type(item[field]) is not bool:
                raise ValueError("exact_custody_boolean_required")
        if item["request"] is not None:
            _request(item["request"], row)
        no_target = row["selected_target"] is None
        if (item["state"] == "no_queryable_target") != no_target:
            raise ValueError("no_target_disposition_mismatch")
        if no_target and any(item[k] is not None for k in ("request", "body_bytes", "body_sha256")):
            raise ValueError("no_target_custody_must_be_null")
        if item["state"] == "positive_cached_HTTP200":
            if item["body_bytes"] is None or item["body_sha256"] is None or item["request"] is None or item["individual_http200_complete"] is not True or item["custody_verified"] is not True:
                raise ValueError("positive_individual_custody_required")
        elif item["individual_http200_complete"] is not False or item["custody_verified"] is not False:
            raise ValueError("nonpositive_custody_assertions_must_be_false")
    s.bounded_json(evidence, s.MAX_JSON_INPUT)


def _empty_metadata(row, evidence, reason, data=None, observed=None):
    target = row["selected_target"]
    return dict(slot_id="row_%03d" % row["row_index"], t0_ns=row["t0_ns"],
                scope={k:target[k] for k in ("network", "station", "location", "prefix")} if target is not None else None,
                expected_sha256=evidence["body_sha256"], observed_sha256=observed,
                bytes=len(data) if data is not None else None, document_state="unknown", reason=reason,
                source_run_complete=False, schema_version=None, node_count=None, channels=[], literal_codes=[])


def _metadata(row, evidence, data, total_excess):
    if total_excess:
        return _empty_metadata(row, evidence, "total_document_byte_cap", data), evidence["state"]
    if data is None:
        return _empty_metadata(row, evidence, evidence["state"]), evidence["state"]
    observed = hashlib.sha256(data).hexdigest()
    if len(data) != evidence["body_bytes"] or observed != evidence["body_sha256"]:
        return _empty_metadata(row, evidence, "body_size_or_sha_mismatch", data, observed), "unverified_custody"
    if len(data) > MAX_BODY:
        return _empty_metadata(row, evidence, "document_byte_cap", data, observed), evidence["state"]
    target = row["selected_target"]
    slot = {k:target[k] for k in ("network", "station", "location", "prefix")}
    slot.update(slot_id="row_%03d" % row["row_index"], t0_ns=row["t0_ns"],
                body_sha256=evidence["body_sha256"], individual_http200_complete=True, custody_verified=True)
    return v1._document_row(data, slot), evidence["state"]


def _describe(metadata, t0):
    for channel in metadata["channels"]:
        descriptors = {}
        for h in v1.HORIZONS:
            descriptor = None
            if channel["horizon_support"][str(h)] == "supported":
                left, right = t0-3*10**9, t0+h*10**9
                indices = [i for i,r in enumerate(channel["epochs"])
                           if all(v1._contains(r[f],left,right) == "supported" for f in ("channel_epoch","station_epoch","network_epoch"))]
                if len(indices) != 1:
                    raise ValueError("inconsistent_unique_supported_epoch")
                record = channel["epochs"][indices[0]]
                descriptor = {k:record[k] for k in ("sample_rate", "azimuth", "dip", "response")}
                descriptor["epoch_record_index"] = indices[0]
            descriptors[str(h)] = descriptor
        channel["horizon_descriptors"] = descriptors


def _candidate(metadata, prefix, family, horizon):
    by_code = {c["code"]:c for c in metadata["channels"]}
    descriptors = []
    for suffix in family:
        channel = by_code.get(prefix+suffix)
        if channel is None:
            return None
        description = channel["horizon_descriptors"][str(horizon)]
        if description is None or not description["sample_rate"]["valid"]:
            return None
        descriptors.append(description)
    rates = [Decimal(d["sample_rate"]["exact_decimal"]) for d in descriptors]
    return True if rates[0] == rates[1] == rates[2] else None


def _horizons(row, metadata):
    target, t0 = row["selected_target"], row["t0_ns"]
    results = []
    for h in v1.HORIZONS:
        pick_before = target["pick_ns"] < t0+h*10**9 if target is not None else None
        enz = _candidate(metadata,target["prefix"],"ENZ",h) if target is not None else None
        numbered = _candidate(metadata,target["prefix"],"12Z",h) if target is not None else None
        candidates = {"ENZ":enz,"12Z":numbered,"either":True if enz is True or numbered is True else None}
        intersections = {name:pick_before if flag is True else None for name,flag in candidates.items()}
        results.append(dict(horizon_s=h,left_ns=t0-3*10**9 if t0 is not None else None,
                            right_ns=t0+h*10**9 if t0 is not None else None,
                            catalogue_pick_before_cutoff=pick_before,nominal_family_candidates=candidates,
                            family_pick_intersections=intersections))
    return results


def _counter(events):
    return dict(events=events,input_states={state:0 for state in STATES},valid_scope_documents=0,unknown_documents=0,
                positive_suffix_document_presence={k:0 for k in ("E","N","1","2","other")},literal_channel_count=0,epoch_record_count=0,
                channel_support_by_horizon={str(h):{k:0 for k in ("supported","not_supported","boundary_unknown","unknown")} for h in v1.HORIZONS},
                orientation_field_presence={"azimuth":0,"dip":0},orientation_field_valid={"azimuth":0,"dip":0},
                sample_rate_present=0,sample_rate_valid=0,response_fragment_epochs=0,response_stage_count=0,sensitivity_epochs=0,
                horizons={str(h):dict(families={k:dict(positive=0,unknown=0) for k in ("ENZ","12Z","either")},
                                     catalogue_pick=dict(before=0,not_before=0,unknown=0),
                                     intersections={k:dict(positive=0,not_positive=0,unknown=0) for k in ("ENZ","12Z","either")}) for h in v1.HORIZONS})


def _add(counter, row):
    metadata = row["document"]
    counter["input_states"][row["input_state"]] += 1
    counter["valid_scope_documents"] += int(metadata["document_state"] == "valid")
    counter["unknown_documents"] += int(metadata["document_state"] == "unknown")
    for kind in {c["suffix_kind"] for c in metadata["channels"]}:
        counter["positive_suffix_document_presence"][kind] += 1
    counter["literal_channel_count"] += len(metadata["channels"])
    for channel in metadata["channels"]:
        for h,state in channel["horizon_support"].items():counter["channel_support_by_horizon"][h][state] += 1
        for record in channel["epochs"]:
            counter["epoch_record_count"] += 1
            for field in ("azimuth","dip"):
                counter["orientation_field_presence"][field] += int(record[field]["present"])
                counter["orientation_field_valid"][field] += int(record[field]["valid"])
            counter["sample_rate_present"] += int(record["sample_rate"]["present"])
            counter["sample_rate_valid"] += int(record["sample_rate"]["valid"])
            counter["response_fragment_epochs"] += int(record["response"]["present"])
            counter["response_stage_count"] += record["response"]["stage_count"]
            counter["sensitivity_epochs"] += int(record["response"]["sensitivity_present"])
    for horizon in row["horizons"]:
        counts = counter["horizons"][str(horizon["horizon_s"])]
        for family,flag in horizon["nominal_family_candidates"].items():counts["families"][family]["positive" if flag is True else "unknown"] += 1
        pick = horizon["catalogue_pick_before_cutoff"]
        counts["catalogue_pick"]["unknown" if pick is None else "before" if pick else "not_before"] += 1
        for family,flag in horizon["family_pick_intersections"].items():
            counts["intersections"][family]["unknown" if flag is None else "positive" if flag else "not_positive"] += 1


def audit(projection, roster, evidence, documents):
    """Replay roster first, then retain every selected cached metadata outcome."""
    expected = s.select(projection)
    s.validate_roster(roster)
    if s.wire(roster) != s.wire(expected):
        raise ValueError("canonical_original_selection_mismatch")
    validate_evidence(evidence, expected)
    if type(documents) is not list or len(documents) != 65 or any(d is not None and type(d) is not bytes for d in documents):
        raise ValueError("exactly_65_bytes_or_none_documents_required")
    for item,data in zip(evidence,documents):
        if (item["state"] == "positive_cached_HTTP200") != (data is not None):
            raise ValueError("document_disposition_mismatch")
    total_excess = sum(len(d) for d in documents if d is not None) > MAX_TOTAL
    rows = []
    for selection,item,data in zip(expected["rows"],evidence,documents):
        metadata,state = _metadata(selection,item,data,total_excess)
        _describe(metadata,selection["t0_ns"])
        copied_evidence = dict(item)
        if item["request"] is not None:copied_evidence["request"] = dict(item["request"])
        rows.append(dict(selection=selection,evidence=copied_evidence,input_state=state,
                         document=metadata,horizons=_horizons(selection,metadata)))
    public = dict(protocol=PROTOCOL,public_source_identifiers=dict(parent_protocol_sha256=s.PROTOCOL_SHA256,
                   frozen_v1_source_sha256="71beb6e92e8ebf3ff8bccf4f2f3bc5dad7f36f4cf993a9fc5adea84440afc86b"),
                  denominators=dict(events=65,TRAIN=41,DEV=24,excluded_TEST=31,event_deadlines=195),
                  overall=_counter(65),by_partition={"TRAIN":_counter(41),"DEV":_counter(24)},claims=dict(CLAIMS))
    for row in rows:
        _add(public["overall"],row);_add(public["by_partition"][row["selection"]["partition"]],row)
    s.bounded_json(public,MAX_PUBLIC_JSON)
    result=dict(private_rows=rows,public_counts=public)
    s.bounded_json(result,MAX_PRIVATE_JSON)
    return result

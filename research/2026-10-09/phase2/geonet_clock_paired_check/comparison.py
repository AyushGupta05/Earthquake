"""Private shadow comparisons; uncertainty does not become zero coverage."""
import collections
import projection as p
DERIVE_FROM_SHADOW = object()


def association_signature(record):
    values = []
    for arrival in record["arrivals"]:
        weight = arrival["time_weight"]
        canonical = p.canonical_number(weight)
        values.append((arrival["phase"], arrival["pick_id"], weight is not None,
                       canonical if canonical is not None else weight))
    return sorted(values, key=repr)


def revision(record):
    return {"event": record["event_creation"],
            "origin": record["origin"]["creation"]}


def recorded_time(value):
    try:
        p.stamp_us(value)
        return True
    except (ValueError, TypeError, AttributeError, OverflowError):
        return False


def compare(left, right):
    result = {"available": False, "same_record_content": None,
              "revision_evidence": "unknown", "newly_resolved_reference_count": None}
    if left.get("status") != "ok" or right.get("status") != "ok":
        return result
    result["available"] = True
    identity = (left["mapped_event_id"], left["preferred_origin_id"]) == (
        right["mapped_event_id"], right["preferred_origin_id"])
    required = ("time_us", "latitude", "longitude", "depth_m")
    complete = all(record["origin"][key] is not None
                   for record in (left, right) for key in required)
    geometry = all(left["origin"][key] == right["origin"][key] for key in required)
    associations = association_signature(left) == association_signature(right)
    result.update(identity_match=identity, origin_fields_complete=complete,
                  origin_content_match=geometry, arrival_multiset_match=associations)
    result["same_record_content"] = (
        identity and geometry and associations if complete else None)
    left_rev, right_rev = revision(left), revision(right)
    known_conflicts = any(a is not None and b is not None and a != b
                          for scope in ("event", "origin")
                          for key in left_rev[scope]
                          for a, b in [(left_rev[scope][key], right_rev[scope][key])])
    matching_times = any(
        recorded_time(left_rev[scope][key]) and
        left_rev[scope][key] == right_rev[scope][key]
        for scope in ("event", "origin") for key in ("creationTime", "modificationTime"))
    result["revision_evidence"] = "conflict" if known_conflicts else (
        "matching_recorded_time" if matching_times and left_rev == right_rev else
        "missing_or_incomplete")
    missing = {identifier for identifier in left["unresolved_pick_ids"] if identifier}
    newly_unique = {identifier for identifier in missing
                      if len(right["picks"].get(identifier, [])) == 1}
    left_accepted = {pick["pick_id"] for pick in left["accepted_picks"]}
    accepted = {pick["pick_id"] for pick in right["accepted_picks"]}
    qualifying = {arrival["pick_id"] for arrival in left["arrivals"]
                  if arrival["phase"] in p.PHASES and arrival["pick_id"]}
    # A reference may become accepted through repaired station/time fields
    # even when its pick object was already unique in the left representation.
    newly_resolved = (qualifying & accepted) - left_accepted
    accepted_nz = {pick["pick_id"] for pick in right["accepted_picks"]
                   if pick["network"] == "NZ"}
    result["newly_unique_reference_object_count"] = len(newly_unique)
    result["newly_resolved_reference_count"] = len(newly_resolved)
    result["newly_accepted_NZ_reference_count"] = len(newly_resolved & accepted_nz)
    result["content_matched_resolution_candidate_count"] = (
        len(newly_resolved) if result["same_record_content"] and not known_conflicts else 0)
    result["paired_recorded_revision_resolution_count"] = (
        len(newly_resolved) if result["same_record_content"] and
        result["revision_evidence"] == "matching_recorded_time" else 0)
    result["atomic_database_revision_verified"] = False
    result["converter_bug_proved"] = False
    return result


def event_result(original, fresh_qml, fresh_scml, preserved_original_t0_us=DERIVE_FROM_SHADOW):
    # Production passes the independently checksum-bound census clock. The
    # default derives from invented standalone fixtures for pure parser tests.
    original_t0 = preserved_original_t0_us
    if original_t0 is DERIVE_FROM_SHADOW:
        original_t0 = original["nz"]["t0_us"] if original.get("status") == "ok" else None
    snapshots = {"original_qml": original, "fresh_qml": fresh_qml, "native_scml": fresh_scml}
    shadows = {}
    for name, record in snapshots.items():
        nz = [pick for pick in record["accepted_picks"] if pick["network"] == "NZ"] \
            if record.get("status") == "ok" else None
        shadows[name] = {
            "status": record["status"],
            "own_clock": record.get("nz"),
            "at_preserved_original_T0": p.clock(nz, original_t0)
            if nz is not None and original_t0 is not None else None,
        }
    return {"representations": snapshots, "shadow_clocks": shadows,
            "preserved_original_T0_us": original_t0,
            "catalogue_drift": compare(original, fresh_qml),
            "representation_difference": compare(fresh_qml, fresh_scml),
            "automatic_reclock_applied": False}


def aggregate(results):
    status = collections.Counter()
    comparisons = {}
    for event in results:
        for name, record in event["representations"].items():
            status[name + ":" + record["status"]] += 1
        for name in ("catalogue_drift", "representation_difference"):
            panel = comparisons.setdefault(name, collections.Counter())
            item = event[name]
            panel["available"] += bool(item["available"])
            panel["same_record_content"] += item.get("same_record_content") is True
            panel["content_mismatch"] += item.get("same_record_content") is False
            panel["unknown"] += item.get("same_record_content") is None
            panel["revision_conflict"] += item.get("revision_evidence") == "conflict"
            panel["content_matched_resolution_candidate_count"] += item.get(
                "content_matched_resolution_candidate_count", 0)
            panel["paired_recorded_revision_resolution_count"] += item.get(
                "paired_recorded_revision_resolution_count", 0)
    return {"source_event_denominator": len(results), "representation_denominator": 3 * len(results),
            "representation_status_counts": dict(status),
            "comparisons": {name: dict(panel) for name, panel in comparisons.items()},
            "atomic_database_revision_verified": False, "physical_pick_validated": False,
            "automatic_reclock_applied": False, "converter_bug_proved": False,
            "operational_clock_verified": False, "magnitude_model_improvement": False}

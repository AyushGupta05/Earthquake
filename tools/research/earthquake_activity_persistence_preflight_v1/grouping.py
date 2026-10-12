"""Fixed65 metadata-only grouping; source coordinates never inference features."""

import math
from activity import InvalidInput, _integer, _keys, _number, _text, SECOND

THIRTY_DAYS_NS = 30 * 86400 * SECOND
EARTH_KM = 6371.0


def distance_km(lat1, lon1, lat2, lon2):
    """Binary64 haversine, shortest dateline difference, rounding-only clamp."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    delta_p = p2 - p1
    delta_l = math.radians((lon2 - lon1 + 180.0) % 360.0 - 180.0)
    a = math.sin(delta_p / 2.0)**2 + math.cos(p1) * math.cos(p2) * math.sin(delta_l / 2.0)**2
    a = min(1.0, max(0.0, a))
    return 2.0 * EARTH_KM * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _origin(raw):
    if raw is None:
        return None
    try:
        _keys(raw, ("time_ns", "latitude", "longitude"))
        time = _integer(raw["time_ns"], -(2**63), 2**63 - 1)
        lat, lon = _number(raw["latitude"]), _number(raw["longitude"])
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            return None
        return time, lat, lon
    except InvalidInput:
        # Malformed origin metadata remains unknown, never independent singleton.
        return None


def group_events(rows):
    """Pure operational convention on all65; cannot verify caller provenance."""
    if type(rows) is not list or len(rows) != 65:
        raise InvalidInput("COHORT_SIZE")
    ordinals, partitions, origins = [], [], []
    seen = set()
    counts = {"TRAIN": 0, "DEV": 0}
    for slot, row in enumerate(rows):
        _keys(row, ("ordinal", "partition", "origin_ns", "latitude", "longitude"))
        ordinal = _integer(row["ordinal"], 0, 2**31 - 1)
        if ordinal in seen or (ordinals and ordinal <= ordinals[-1]):
            raise InvalidInput("ORDINAL_ORDER")
        seen.add(ordinal)
        partition = _text(row["partition"], ("TRAIN", "DEV"))
        counts[partition] += 1
        ordinals.append(ordinal)
        partitions.append(partition)
        origins.append(_origin({"time_ns": row["origin_ns"], "latitude": row["latitude"],
                                "longitude": row["longitude"]}))
    if counts != {"TRAIN": 41, "DEV": 24}:
        raise InvalidInput("PARTITION_COUNTS")
    parent = list(range(65))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    edges = []
    for first in range(65):
        if origins[first] is None:
            continue
        t1, lat1, lon1 = origins[first]
        for second in range(first + 1, 65):
            if origins[second] is None:
                continue
            t2, lat2, lon2 = origins[second]
            if (abs(t2 - t1) <= THIRTY_DAYS_NS
                    and distance_km(lat1, lon1, lat2, lon2) <= 200.0):
                edges.append([ordinals[first], ordinals[second]])
                a, b = find(first), find(second)
                parent[max(a, b)] = min(a, b)
    members = {}
    for slot in range(65):
        if origins[slot] is not None:
            members.setdefault(find(slot), []).append(slot)
    groups, mapping = [], {}
    for slots in members.values():
        identifier = min(ordinals[slot] for slot in slots)
        cross = len({partitions[slot] for slot in slots}) > 1
        groups.append({"identifier": identifier, "original_ordinals": [ordinals[s] for s in slots],
                       "cross_partition": cross, "operational_eligible": not cross})
        for slot in slots:
            mapping[slot] = identifier, cross
    groups.sort(key=lambda group: group["identifier"])
    outputs = []
    for slot in range(65):
        known = slot in mapping
        identifier, cross = mapping.get(slot, (None, False))
        outputs.append({"slot": slot, "ordinal": ordinals[slot],
                        "partition": partitions[slot], "group_identifier": identifier,
                        "status": "UNKNOWN_ORIGIN" if not known else "CROSS_PARTITION" if cross else "known",
                        "operational_eligible": known and not cross})
    return {"schema": "operational-grouping-v1", "events": 65, "maximum_pairs": 2080,
            "partition_counts": counts, "edges": edges, "groups": groups, "rows": outputs,
            "physical_sequence_independence_verified": False,
            "external_origin_binding_verified": False, "fit_authorized": False}

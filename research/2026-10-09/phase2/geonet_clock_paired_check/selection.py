"""Fixed diagnostic roster and twelve paired queries, independent of new bodies."""
import hashlib
import math
import re
import urllib.parse
from projection import UNRESOLVED

PARTITION = "test2018_2024"


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def list_hash(values):
    return digest("\n".join(values) + "\n")


def choose(rows, outcomes):
    if len(rows) != 495 or len({row["event_id"] for row in rows}) != 495:
        raise ValueError("frozen source denominator")
    tail = [row for row in rows if row["source"] == "reused_tail"]
    lower = [row for row in rows if row["source"] == "new_lower_M"]
    if len(tail) != 149 or len(lower) != 346:
        raise ValueError("frozen lower/tail denominators")
    candidates = []
    for row in tail:
        if row["candidate_calendar_partition"] != PARTITION or row["mw"] < 6:
            continue
        if not math.isfinite(row["mw"]):
            raise ValueError("invalid magnitude label")
        identifier = row["event_id"]
        if not re.fullmatch(r"(?:[0-9]{5,7}|[0-9]{4}p[0-9]{6})", identifier):
            raise ValueError("invalid source identity")
        base = outcomes[identifier]["base"]
        if base.get("status") != "ok":
            raise ValueError("original tail metadata prerequisite changed")
        partial = any(base.get("reasons", {}).get(key, 0) > 0 for key in UNRESOLVED)
        band = "[6,7)" if row["mw"] < 7 else ">=7"
        candidates.append({**row, "Mw_band": band, "incomplete": partial})
    probes = [row for row in candidates if row["incomplete"]]
    if {band: sum(row["Mw_band"] == band for row in probes)
        for band in ("[6,7)", ">=7")} != {"[6,7)": 3, ">=7": 1}:
        raise ValueError("four fixed incomplete probes changed")
    selected = [dict(row, role="incomplete_probe") for row in probes]
    for band in ("[6,7)", ">=7"):
        cell = [row for row in candidates if not row["incomplete"] and row["Mw_band"] == band]
        if not cell:
            raise ValueError("missing fixed control band")
        cell.sort(key=lambda row: (
            digest("geonet-scml-paired-control-v1|" + PARTITION + "|" + band + "|" + row["event_id"]),
            row["event_id"]))
        selected.append(dict(cell[0], role="complete_control"))
    selected.sort(key=lambda row: (
        digest("geonet-scml-paired-query-v1|" + row["event_id"]), row["event_id"]))
    if len(selected) != 6 or len({row["event_id"] for row in selected}) != 6:
        raise ValueError("fixed six-event selection changed")
    return selected


def requests(events):
    result = []
    for event in events:
        for kind, endpoint in (("qml", "/fdsnws/event/1/query"), ("scml", "/sc3ml")):
            result.append({
                "event_id": event["event_id"], "kind": kind, "method": "GET",
                "file": f"{kind}_{len(result):02d}.xml",
                "url": "https://service.geonet.org.nz" + endpoint + "?" +
                       urllib.parse.urlencode({"eventid": event["event_id"]}),
            })
    return result

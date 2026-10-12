"""Offline per-record prefix accounting. Pure logic supplies no decode authority."""

from datetime import date
from fractions import Fraction
import hashlib
import json
import math
import struct
import time

import scanner

STUDY = "geonet-original-TRAINDEV65-prefix3-native-POST-v2"
MAX_PRIVATE = 64 * 1024 * 1024
MAX_PUBLIC = 64 * 1024
MAX_SAMPLES = 8_000_000
MAX_TOTAL_SAMPLES = 136_000_000
MAX_SECONDS = 300
_HEADROOM = 8 * 1024 * 1024
_CLAIMS = ("physically_calibrated", "full_response_verified", "physical_axes_verified",
           "raw_clock_truth_verified", "online_availability_verified",
           "sequence_independence_verified", "usable_model_support_verified",
           "accuracy_improved", "novelty_verified", "published_superiority_verified",
           "hardware_clipping_verified")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def pair(value):
    return [value.numerator, value.denominator]


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def _keys(value, keys):
    return type(value) is dict and all(type(k) is str for k in value) and set(value) == set(keys)


def _literal(value, low, high):
    return (type(value) is str and low <= len(value) <= high
            and all("A" <= c <= "Z" or "0" <= c <= "9" for c in value))


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _rational(value):
    if (type(value) is not list or len(value) != 2
            or type(value[0]) is not int or value[0] <= 0
            or type(value[1]) is not int or value[1] <= 0
            or math.gcd(*value) != 1):
        raise ValueError("input_schema")
    return Fraction(*value)


def channels(row):
    suffixes = "ENZ" if row["family"] == "ENZ" else "12Z" if row["family"] == "12Z" else ""
    return [row["prefix"] + suffix for suffix in suffixes]


def validate(plan, bodies):
    if (not _keys(plan, ("study", "rows", "batches")) or type(plan["study"]) is not str or plan["study"] != STUDY
            or type(plan["rows"]) is not list or len(plan["rows"]) != 65
            or type(plan["batches"]) is not list or len(plan["batches"]) != 17
            or type(bodies) is not dict or len(bodies) != 17
            or any(type(k) is not int for k in bodies) or set(bodies) != set(range(17))):
        raise ValueError("input_schema")
    partitions = {"TRAIN": 0, "DEV": 0}
    families = {"ENZ": 0, "12Z": 0, None: 0}
    rowkeys = ("ordinal", "partition", "batch", "network", "station", "location",
               "prefix", "t0_ns", "pick_ns", "family", "nominal_rates")
    for i, row in enumerate(plan["rows"]):
        if (not _keys(row, rowkeys) or not _int(row["ordinal"], i, i)
                or not _int(row["batch"], i//4, i//4)
                or type(row["partition"]) is not str or row["partition"] not in partitions
                or not (row["family"] is None or type(row["family"]) is str)
                or row["family"] not in families
                or not _literal(row["network"], 1, 2) or not _literal(row["station"], 1, 5)
                or not _literal(row["location"], 0, 2) or not _literal(row["prefix"], 2, 2)
                or not _int(row["t0_ns"], -(2**63)+3_000_000_000, 2**63-1-5_000_000_000)
                or not _int(row["pick_ns"], -(2**63), 2**63-1)
                or type(row["nominal_rates"]) is not dict
                or any(type(k) is not str for k in row["nominal_rates"])
                or set(row["nominal_rates"]) != set(channels(row))):
            raise ValueError("input_schema")
        for key, value in row["nominal_rates"].items():
            if type(key) is not str:
                raise ValueError("input_schema")
            _rational(value)
        partitions[row["partition"]] += 1
        families[row["family"]] += 1
    if partitions != {"TRAIN": 41, "DEV": 24} or families != {"ENZ": 47, "12Z": 14, None: 4}:
        raise ValueError("input_schema")
    total = 0
    for i, batch in enumerate(plan["batches"]):
        if (not _keys(batch, ("ordinal", "rows", "transport", "body_bytes", "body_sha256"))
                or not _int(batch["ordinal"], i, i) or type(batch["rows"]) is not list
                or any(type(n) is not int for n in batch["rows"])
                or batch["rows"] != list(range(4*i, min(4*i+4, 65)))
                or type(batch["transport"]) is not str
                or batch["transport"] not in ("http200", "no_data", "error", "empty")):
            raise ValueError("input_schema")
        raw = bodies[i]
        if batch["transport"] == "http200":
            if (type(raw) is not bytes or not _int(batch["body_bytes"], 1, 8_388_608)
                    or len(raw) != batch["body_bytes"] or not _sha(batch["body_sha256"])
                    or hashlib.sha256(raw).hexdigest() != batch["body_sha256"]):
                raise ValueError("input_schema")
            total += len(raw)
        elif raw is not None or type(batch["body_bytes"]) is not int or batch["body_bytes"] != 0 or batch["body_sha256"] is not None:
            raise ValueError("input_schema")
    if total > 136 * 1024 * 1024:
        raise ValueError("input_schema")


def header_grid(record):
    b100, b1001 = record["b100"], record["b1001"]
    if (record["date_unused"] or record["b1000_reserved"]
            or record["flags"][0] & 0x30 or (b100 and any(b100[2:]))
            or (b1001 and b1001[2])):
        raise ValueError("timing_unknown")
    y, day, h, m, s, fraction = record["date"]
    days = (date(y, 1, 1) - date(1970, 1, 1)).days + day - 1
    start = (days*86400 + h*3600 + m*60 + s)*1_000_000_000 + fraction*100_000
    if not record["flags"][0] & 0x02:
        start += record["correction"]*100_000
    if b1001:
        start += b1001[1]*1000
    if b100:
        rate = Fraction.from_float(b100[0])
    else:
        factor, multiplier = record["rate"]
        if not factor or not multiplier:
            raise ValueError("timing_unknown")
        rate = (Fraction(factor) if factor > 0 else Fraction(1, -factor)) * (
            Fraction(multiplier) if multiplier > 0 else Fraction(1, -multiplier))
    if rate <= 0 or not _int(start, -(2**63), 2**63-1):
        raise ValueError("timing_unknown")
    return start, rate, Fraction(1_000_000_000)/rate


def _bytes(values, dtype):
    if dtype not in ("i4", "f4", "f8"):
        raise ValueError("decode_unknown")
    if hasattr(values, "dtype"):
        if (getattr(values, "ndim", None) != 1 or values.dtype.kind != dtype[0]
                or values.dtype.itemsize != int(dtype[1])):
            raise ValueError("decode_unknown")
        return values.astype("<" + dtype, copy=False).tobytes(order="C")
    if type(values) is not list or any(type(v) not in (int, float) for v in values):
        raise ValueError("decode_unknown")
    try:
        return struct.pack("<" + {"i4": "i", "f4": "f", "f8": "d"}[dtype]*len(values), *values)
    except (struct.error, OverflowError):
        raise ValueError("decode_unknown")


def sample_hash(values, dtype):
    return hashlib.sha256(dtype.encode("ascii") + b"\0" + _bytes(values, dtype)).hexdigest()


def _scalar(value, dtype):
    return int(value) if dtype == "i4" else float(value)


def _runs(values, dtype):
    finite = all(math.isfinite(float(v)) for v in values)
    keys = ("minimum", "maximum", "first_value", "last_value", "first_run", "last_run", "min_run", "max_run", "flat")
    if not finite:
        return dict(finite=False, **{k: None for k in keys})
    minimum = _scalar(min(values), dtype)
    maximum = _scalar(max(values), dtype)
    first, last = _scalar(values[0], dtype), _scalar(values[-1], dtype)
    first_run = last_run = 0
    for v in values:
        if v != first:
            break
        first_run += 1
    for v in reversed(values):
        if v != last:
            break
        last_run += 1
    min_run = max_run = current = 0
    previous = None
    for v in values:
        current = current + 1 if v == previous else 1
        if v == minimum:
            min_run = max(min_run, current)
        if v == maximum:
            max_run = max(max_run, current)
        previous = v
    return dict(finite=True, minimum=minimum, maximum=maximum, first_value=first,
                last_value=last, first_run=first_run, last_run=last_run,
                min_run=min_run, max_run=max_run, flat=minimum == maximum)


def _ceil(value):
    return -((-value.numerator)//value.denominator)


def _piece(record, values, dtype, start, period, left, right):
    lo = max(0, _ceil((Fraction(left)-start)/period))
    hi = min(len(values), _ceil((Fraction(right)-start)/period))
    if hi <= lo:
        return None
    crop = values[lo:hi]
    piece = dict(record=record, lo=lo, hi=hi, count=hi-lo,
                 first=pair(Fraction(start)+lo*period),
                 last=pair(Fraction(start)+(hi-1)*period), period=pair(period),
                 dtype=dtype, samples_sha256=sample_hash(crop, dtype))
    piece.update(_runs(crop, dtype))
    return piece


def _phase(delta, period):
    residue = delta % period
    return min(residue, period-residue)


def _unknown(channel, reason):
    return dict(channel=channel, status="unknown", reason=reason, count=0,
                rate=None, first=None, last=None, finite=None, metadata_rate_match=None,
                minimum=None, maximum=None, flat=None, extreme_run=None,
                view_sha256=None, pieces=[])


def _component(channel, pieces, row, horizon, batch, seen):
    if batch["status"] != "decoded":
        return _unknown(channel, "transport_nonpositive" if batch["status"] == "nonpositive" else "batch_unknown")
    if not pieces:
        return _unknown(channel, "no_samples_in_window" if channel in seen else "missing_component")
    pieces = sorted(pieces, key=lambda x: (Fraction(*x["first"]), Fraction(*x["last"]), x["record"]))
    periods = {Fraction(*p["period"]) for p in pieces}
    period = next(iter(periods)) if len(periods) == 1 else None
    rate = Fraction(1_000_000_000)/period if period else None
    first = Fraction(*pieces[0]["first"])
    last = max(Fraction(*p["last"]) for p in pieces)
    finite = all(p["finite"] for p in pieces)
    reason = "supported"
    if not finite:
        reason = "nonfinite"
    elif period is None:
        reason = "mixed_rate"
    else:
        left, right = row["t0_ns"]-3_000_000_000, row["t0_ns"]+horizon*1_000_000_000
        tolerance = min(Fraction(1000), period/100)
        if not (0 <= first-left < period and 0 < right-last <= period):
            reason = "edge"
        elif any(abs(Fraction(*b["first"])-Fraction(*a["last"])-period) > tolerance for a, b in zip(pieces, pieces[1:])):
            reason = "gap_overlap"
        elif any(_phase(Fraction(*p["first"])-first, period) > tolerance for p in pieces):
            reason = "phase"
    minimum = min(p["minimum"] for p in pieces) if finite else None
    maximum = max(p["maximum"] for p in pieces) if finite else None
    extreme = 0 if finite else None
    if finite:
        previous_value, tail = None, 0
        for p in pieces:
            if p["minimum"] == minimum:
                extreme = max(extreme, p["min_run"])
            if p["maximum"] == maximum:
                extreme = max(extreme, p["max_run"])
            if p["first_value"] == previous_value and previous_value in (minimum, maximum):
                extreme = max(extreme, tail+p["first_run"])
            tail = tail+p["count"] if p["flat"] and p["first_value"] == previous_value else p["last_run"]
            previous_value = p["last_value"]
    composition = [{k:p[k] for k in ("record", "lo", "hi", "count", "first", "last", "period", "dtype", "samples_sha256")} for p in pieces]
    expected = row["nominal_rates"].get(channel)
    return dict(channel=channel, status="complete" if reason == "supported" else "incomplete",
                reason=reason, count=sum(p["count"] for p in pieces), rate=pair(rate) if rate else None,
                first=pair(first), last=pair(last), finite=finite,
                metadata_rate_match=(rate == Fraction(*expected)) if rate and expected else None,
                minimum=minimum, maximum=maximum, flat=(minimum == maximum) if finite else None,
                extreme_run=extreme, view_sha256=hashlib.sha256(canonical(composition)).hexdigest(), pieces=pieces)


def _joint(row, components):
    required = channels(row)
    if not required:
        return dict(status="unknown", reason="metadata_unknown", rate=None, channels=[])
    by_code = {c["channel"]:c for c in components}
    values = [by_code[c] for c in required]
    if any(c["status"] == "unknown" for c in values):
        return dict(status="unknown", reason="component_unknown", rate=None, channels=required)
    if any(c["status"] != "complete" for c in values):
        return dict(status="incomplete", reason="component_incomplete", rate=None, channels=required)
    rates = {tuple(c["rate"]) for c in values}
    if len(rates) != 1:
        return dict(status="incomplete", reason="joint_rate", rate=None, channels=required)
    rate = Fraction(*values[0]["rate"])
    period = Fraction(1_000_000_000)/rate
    anchor = Fraction(*values[0]["first"])
    if any(_phase(Fraction(*c["first"])-anchor, period) > min(Fraction(1000), period/100) for c in values):
        return dict(status="incomplete", reason="joint_phase", rate=pair(rate), channels=required)
    return dict(status="complete", reason="supported", rate=pair(rate), channels=required)


def _rows(plan, batches, pieces, seen, fatal):
    result = []
    for row in plan["rows"]:
        codes = sorted(set(channels(row)) | seen[row["ordinal"]])
        cells = []
        for h in (1, 3, 5):
            components = [(_unknown(code, "batch_unknown") if fatal else
                           _component(code, pieces.get((row["ordinal"],h,code), []), row, h,
                                      batches[row["batch"]], seen[row["ordinal"]])) for code in codes]
            cells.append(dict(horizon=h, cutoff_ns=row["t0_ns"]+h*1_000_000_000,
                              pick_before_cutoff=row["pick_ns"] < row["t0_ns"]+h*1_000_000_000,
                              components=components, joint=_joint(row, components)))
        result.append(dict(ordinal=row["ordinal"], partition=row["partition"], batch=row["batch"], family=row["family"], cells=cells))
    return result


def _aggregate(rows, batches):
    horizons = []
    for i, h in enumerate((1, 3, 5)):
        complete = [r for r in rows if r["cells"][i]["joint"]["status"] == "complete"]
        horizons.append(dict(horizon=h, complete_joint=len(complete),
                             train_complete_joint=sum(r["partition"] == "TRAIN" for r in complete),
                             dev_complete_joint=sum(r["partition"] == "DEV" for r in complete),
                             complete_joint_pick_before_cutoff=sum(r["cells"][i]["pick_before_cutoff"] for r in complete),
                             complete_components=sum(c["status"] == "complete" for r in rows for c in r["cells"][i]["components"]),
                             metadata_unknown_complete_components=sum(c["status"] == "complete" for r in rows if r["family"] is None for c in r["cells"][i]["components"])))
    return dict(rows=65, train=41, dev=24, test_excluded=31, cells=195, batches=17,
                metadata_known=61, metadata_unknown=4, horizons=horizons,
                batch_statuses={s:sum(b["status"] == s for b in batches) for s in ("decoded","unknown","nonpositive")})


class _Fatal(Exception):
    pass


def qualify(plan, bodies, decode_record):
    validate(plan, bodies)
    started = time.monotonic()
    batches = [dict(ordinal=i, status="unknown", reason="decode_unknown", record_count=0,
                    advertised_samples=0, observed_samples=0) for i in range(17)]
    records, pieces, seen = [], {}, [set() for _ in range(65)]
    advertised_total = observed_total = spent = 0
    fatal = None
    try:
        for batch in plan["batches"]:
            bi, raw = batch["ordinal"], bodies[batch["ordinal"]]
            current = batches[bi]
            if raw is None:
                current.update(status="nonpositive", reason="transport_nonpositive")
                continue
            ledger = scanner.scan(raw)
            if ledger["disposition"] != "supported":
                if ledger["reason"] in ("sample_cap", "output_cap"):
                    raise _Fatal(ledger["reason"])
                current.update(status="unknown", reason="structural_unknown")
                continue
            current.update(record_count=ledger["record_count"], advertised_samples=ledger["advertised_samples"])
            advertised_total += ledger["advertised_samples"]
            if advertised_total > MAX_TOTAL_SAMPLES:
                raise _Fatal("sample_cap")
            current.update(status="decoded", reason="supported")
            for d in ledger["records"]:
                if time.monotonic()-started > MAX_SECONDS:
                    raise _Fatal("wall_timeout")
                try:
                    start, rate, period = header_grid(d)
                except ValueError:
                    current.update(status="unknown", reason="timing_unknown")
                    break
                rbytes = raw[d["offset"]:d["offset"]+d["length"]]
                decoded = values = None
                try:
                    if d["npts"]:
                        decoded = decode_record(rbytes, d)
                        if not _keys(decoded, ("start_ns", "rate", "dtype", "values")):
                            raise ValueError("decode_unknown")
                        observed = decoded["rate"]
                        values, dtype = decoded["values"], decoded["dtype"]
                        if (not _int(decoded["start_ns"], -(2**63), 2**63-1) or decoded["start_ns"] != start
                                or type(observed) is not float or not math.isfinite(observed) or observed <= 0
                                or abs(Fraction.from_float(observed)-rate) > max(Fraction(1,10**12), rate/10**12)
                                or len(values) != d["npts"]):
                            raise ValueError("decode_unknown")
                        expected_dtype = {1:"i4",3:"i4",4:"f4",5:"f8",10:"i4",11:"i4"}[d["encoding"]]
                        if dtype != expected_dtype:
                            raise ValueError("decode_unknown")
                        digest = sample_hash(values, dtype)
                        decoded_start = decoded["start_ns"]
                    else:
                        values, dtype, decoded_start = [], "empty", None
                        digest = hashlib.sha256(b"empty\0").hexdigest()
                    n = len(values)
                    current["observed_samples"] += n
                    observed_total += n
                    if current["observed_samples"] > MAX_SAMPLES or observed_total > MAX_TOTAL_SAMPLES:
                        raise _Fatal("sample_cap")
                    routed = [i for i in batch["rows"] if d["nslc"][:3] == [plan["rows"][i][k] for k in ("network","station","location")]
                              and d["nslc"][3][:2] == plan["rows"][i]["prefix"]]
                    entry = dict(batch=bi, ordinal=d["ordinal"], offset=d["offset"], length=d["length"], nslc=d["nslc"],
                                 encoding=d["encoding"], word_order=d["word_order"], raw_sha256=hashlib.sha256(rbytes).hexdigest(),
                                 start_ns=start, rate=pair(rate), period=pair(period), advertised_samples=d["npts"],
                                 observed_samples=n, decoded_start_ns=decoded_start, dtype=dtype, samples_sha256=digest,
                                 finite=all(math.isfinite(float(v)) for v in values), routed_rows=routed)
                    spent += len(canonical(entry)) + 64
                    if spent > MAX_PRIVATE-_HEADROOM:
                        raise _Fatal("output_cap")
                    records.append(entry)
                    if not routed:
                        current.update(status="unknown", reason="unexpected_identity")
                        break
                    for ri in routed:
                        row, code = plan["rows"][ri], d["nslc"][3]
                        seen[ri].add(code)
                        for h in (1,3,5):
                            piece = _piece(d["ordinal"], values, dtype, start, period,
                                            row["t0_ns"]-3_000_000_000, row["t0_ns"]+h*1_000_000_000)
                            if piece is not None:
                                spent += len(canonical(piece)) + 64
                                if spent > MAX_PRIVATE-_HEADROOM:
                                    raise _Fatal("output_cap")
                                pieces.setdefault((ri,h,code), []).append(piece)
                    # No observed arrays are retained in records/pieces or across iterations.
                except ValueError:
                    current.update(status="unknown", reason="decode_unknown")
                    break
                finally:
                    # Release the callback's owning array as well as any local view.
                    decoded = values = None
                if time.monotonic()-started > MAX_SECONDS:
                    raise _Fatal("wall_timeout")
        if time.monotonic()-started > MAX_SECONDS:
            raise _Fatal("wall_timeout")
    except _Fatal as error:
        fatal = error.args[0]
        current.update(status="unknown", reason="decode_unknown")
    except Exception:
        fatal = "runtime_failure"
        current.update(status="unknown", reason="decode_unknown")
    rows = _rows(plan, batches, pieces, seen, fatal is not None)
    result = dict(schema="geonet-POST-prefix-qualification-v1", study=STUDY,
                  disposition="incomplete" if fatal else "complete", reason=fatal or "supported",
                  batches=batches, records=records, rows=rows, aggregate=_aggregate(rows,batches),
                  claims={k:False for k in _CLAIMS})
    if len(canonical(result)) > MAX_PRIVATE or len(canonical(result["aggregate"])) > MAX_PUBLIC:
        result.update(disposition="incomplete", reason="output_cap")
        result["rows"] = _rows(plan,batches,{},seen,True)
        result["aggregate"] = _aggregate(result["rows"],batches)
        # Only bounded partial evidence can be emitted; original inputs remain retained externally.
        while len(canonical(result)) > MAX_PRIVATE and result["records"]:
            result["records"].pop()
        if len(canonical(result)) > MAX_PRIVATE:
            raise RuntimeError("output_cap")
    if result["disposition"] == "complete" and time.monotonic()-started > MAX_SECONDS:
        result.update(disposition="incomplete", reason="wall_timeout")
        result["rows"] = _rows(plan,batches,{},seen,True)
        result["aggregate"] = _aggregate(result["rows"],batches)
    return result

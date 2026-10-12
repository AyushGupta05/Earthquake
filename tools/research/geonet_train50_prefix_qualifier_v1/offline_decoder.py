"""Standalone Linux entry; actual authority and hard-stop proof remain parent-owned."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import warnings

import producer
from decode_contract import ObservedDecodeFailure


def _bounded(path, cap):
    with Path(path).open("rb") as stream:
        value = stream.read(cap+1)
    if len(value) > cap:
        raise ValueError("input_cap")
    return value


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def load_json(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite_json")))


def verify_live_limits():
    if sys.platform != "linux":
        raise RuntimeError("linux_cgroup_required")
    lines = _bounded("/proc/self/cgroup", 16384).decode("ascii").splitlines()
    entries = [line[3:] for line in lines if line.startswith("0::")]
    if len(entries) != 1 or not entries[0].startswith("/"):
        raise RuntimeError("cgroup_v2_required")
    base = Path("/sys/fs/cgroup").resolve()
    group = (base / entries[0].lstrip("/")).resolve()
    if group == base or base not in group.parents:
        raise RuntimeError("owned_cgroup_required")
    expected = {"memory.max":"1073741824", "memory.swap.max":"0", "pids.max":"32"}
    for name, value in expected.items():
        if _bounded(group/name, 128).decode("ascii").strip() != value:
            raise RuntimeError("cgroup_limit_mismatch")
    pids = _bounded(group/"cgroup.procs", 16384).decode("ascii").split()
    if str(os.getpid()) not in pids:
        raise RuntimeError("cgroup_membership")
    return {"memory_max":1073741824,"memory_swap_max":0,"tasks_max":32}


def make_decoder():
    # Live inspection is necessary but not sufficient: root separately proves
    # OOM/750s systemd stop controls and exact private runtime pins before invocation.
    verify_live_limits()
    for key in ("UNPACK_HEADER_BYTEORDER","UNPACK_DATA_BYTEORDER","UNPACK_DATA_FORMAT",
                "UNPACK_DATA_FORMAT_FALLBACK","DECODE_DEBUG"):
        os.environ.pop(key, None)
    for key in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","NUMEXPR_NUM_THREADS"):
        os.environ[key] = "1"
    import obspy
    import numpy
    from obspy.io.mseed import InternalMSEEDError
    if obspy.__version__ != "1.5.1":
        raise RuntimeError("decoder_version")

    def decode(raw, descriptor):
        received = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                stream = obspy.read(io.BytesIO(raw), format="MSEED", details=True,
                                    reclen=descriptor["length"],
                                    header_byteorder=">" if descriptor["endian"] == "big" else "<")
            # Count every received scalar before any trace/count/dtype/identity veto.
            received = 0
            for trace in stream:
                values = trace.data
                if not isinstance(values, numpy.ndarray):
                    raise RuntimeError("native_observed_accounting_invalid")
                received += int(numpy.ndarray.size.__get__(values))
                if received > 2**63-1:
                    raise RuntimeError("native_observed_accounting_invalid")
            if len(stream) != 1:
                raise ValueError("decode_unknown")
            trace = stream[0]
            literal = [trace.stats.network,trace.stats.station,trace.stats.location,trace.stats.channel]
            if literal != descriptor["nslc"] or trace.stats.npts != descriptor["npts"]:
                raise ValueError("decode_unknown")
            values = trace.data
            if (type(values) is not numpy.ndarray or values.ndim != 1
                    or values.dtype.kind not in ("i","f")
                    or (values.dtype.kind,values.dtype.itemsize) not in (("i",4),("f",4),("f",8))):
                raise ValueError("decode_unknown")
            return dict(start_ns=int(trace.stats.starttime.ns), rate=float(trace.stats.sampling_rate),
                        dtype=values.dtype.kind+str(values.dtype.itemsize), values=values)
        except (InternalMSEEDError, Warning) as error:
            # A vendor call that returns no arrays cannot manufacture a count.
            if received is not None:
                raise ObservedDecodeFailure(received) from None
            raise ValueError("decode_unknown") from error
        except ValueError:
            if received is not None:
                raise ObservedDecodeFailure(received) from None
            raise
    return decode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--bodies-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--aggregate", required=True)
    args = parser.parse_args()
    verify_live_limits()
    if sys.version_info[:3] != (3,9,25):
        raise RuntimeError("production_python_version")
    rawplan = _bounded(args.plan, 1024*1024)
    if not producer._sha(args.plan_sha256) or hashlib.sha256(rawplan).hexdigest() != args.plan_sha256:
        raise ValueError("plan_pin")
    plan = load_json(rawplan)
    # Metadata validation precedes any vendor import; private body names are fixed,
    # and byte membership/pins are rechecked by qualify before callbacks.
    if not producer._keys(plan,("study","rows","batches")) or type(plan["batches"]) is not list or len(plan["batches"]) != 13:
        raise ValueError("input_schema")
    directory = Path(args.bodies_dir).resolve()
    bodies = {}
    for batch in plan["batches"]:
        if not producer._keys(batch,("ordinal","rows","requested_rows","transport","body_bytes","body_sha256")) or not producer._int(batch["ordinal"],0,12):
            raise ValueError("input_schema")
        ordinal = batch["ordinal"]
        if ordinal in bodies:
            raise ValueError("input_schema")
        filename = directory / ("batch_%02d.bin" % ordinal)
        if batch["transport"] == "http200":
            if filename.is_symlink() or not filename.is_file():
                raise ValueError("body_membership")
            bodies[ordinal] = _bounded(filename,8_388_608)
        else:
            bodies[ordinal] = None
    producer.validate(plan,bodies)
    decoder = make_decoder()
    result = producer.qualify(plan,bodies,decoder)
    output, aggregate = producer.canonical(result), producer.canonical(result["aggregate"])
    if len(output) > producer.MAX_PRIVATE or len(aggregate) > producer.MAX_PUBLIC:
        raise RuntimeError("output_cap")
    Path(args.output).write_bytes(output)
    Path(args.aggregate).write_bytes(aggregate)
    return 0 if result["disposition"] == "complete" else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # No identifiers, clocks, paths, vendor exception text or credentials leak.
        sys.stderr.write("qualification_incomplete\n")
        sys.exit(2)

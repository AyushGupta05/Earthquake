"""Pinned native-view reconstruction and declared numeric modeling artifact."""

from fractions import Fraction
import hashlib
import io
import json
import math
import re
import struct
import zipfile

import numpy as np
import old_core as qc

MAX_ELEMENTS=10_000_000
MAX_UNCOMPRESSED=40*1024*1024
MAX_ARCHIVE=64*1024*1024
META_NAMES={"amplitudes","contexts","magnitudes","groups","partitions","cohort"}
WAVE=re.compile(r"wave_(\d{2})_([135])\Z")


def canonical(value):return qc.canonical(value)


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def metadata_validate(metadata,plan):
    keys=("ordinal","partition","mw","group","operational_eligible","station_latitude",
          "station_longitude","station_elevation","sensitivities","units")
    if type(metadata) is not list or len(metadata)!=65:raise ValueError("metadata_schema")
    for i,row in enumerate(metadata):
        if (not qc._keys(row,keys) or not qc._int(row["ordinal"],i,i)
                or type(row["partition"]) is not str or row["partition"]!=plan["rows"][i]["partition"]
                or not _finite(row["mw"]) or not qc._int(row["group"],0,64)
                or type(row["operational_eligible"]) is not bool
                or type(row["sensitivities"]) is not list or len(row["sensitivities"])!=3
                or type(row["units"]) is not list or len(row["units"])!=3):
            raise ValueError("metadata_schema")


def context(row,meta,horizon,rate):
    values=[float(horizon),horizon-(row["pick_ns"]-row["t0_ns"])/1e9,math.log10(float(rate))]
    coords=[];missing=[]
    for key,low,high in (("station_latitude",-90,90),("station_longitude",-180,180),("station_elevation",-10000,10000)):
        value=meta[key];valid=_finite(value) and low<=value<=high
        coords.append(float(value) if valid else 0.0);missing.append(float(not valid))
    values+=coords+missing+[float(row["family"]=="ENZ"),float(row["family"]=="12Z")]
    gains=[];gainmissing=[]
    for value in meta["sensitivities"]:
        valid=_finite(value) and value>0
        gains.append(math.log10(value) if valid else 0.0);gainmissing.append(float(not valid))
    values+=gains+gainmissing
    for unit in meta["units"]:
        category={"M/S":0,"M/S**2":1,"M":2}.get(unit,3) if type(unit) is str else 3
        values += [float(i==category) for i in range(4)]
    if len(values)!=29 or not all(math.isfinite(x) for x in values):raise ValueError("context")
    return np.asarray(values,dtype=np.float64)


def preprocess(native,precontext_count):
    native=np.asarray(native,dtype=np.float64)
    if (native.ndim!=2 or native.shape[0]!=3 or not 0<precontext_count<=native.shape[1]
            or not np.isfinite(native).all()):raise ValueError("preprocess")
    centered=native-native[:,:precontext_count].mean(axis=1,keepdims=True,dtype=np.float64)
    if not np.isfinite(centered).all():raise ValueError("preprocess")
    scale=max(1.0,float(np.max(np.abs(centered))))
    normalized=centered/scale
    rms_unit=np.sqrt(np.mean(normalized*normalized,axis=1,dtype=np.float64))
    logrms=[math.log10(max(float(v)*scale,1e-12)) for v in rms_unit]
    amplitude=np.asarray([math.log10(scale),*logrms],dtype=np.float32)
    wave=np.ascontiguousarray(normalized,dtype=np.float32)
    if not np.isfinite(wave).all() or not np.isfinite(amplitude).all():raise ValueError("preprocess")
    return wave,amplitude


def _empty_cell(h,reason,channels):
    return dict(horizon=h,status="unavailable",reason=reason,array=None,shape=None,
                first=None,period=None,precontext_count=None,channels=channels,view_sha256=None)


def _reconstruct(plan,qualified,bodies,decode_record,only_batch):
    """Replay V2 identity/count/clock/hash before exposing arrays to assembly."""
    qc.validate(plan,bodies)
    if (not qc._keys(qualified,("schema","study","disposition","reason","batches","records","rows","aggregate","claims"))
            or qualified["schema"]!="geonet-POST-prefix-qualification-v2" or qualified["study"]!=qc.STUDY
            or qualified["disposition"]!="complete" or qualified["reason"]!="supported"
            or type(qualified["rows"]) is not list or len(qualified["rows"])!=65
            or type(qualified["batches"]) is not list or len(qualified["batches"])!=17):
        raise ValueError("qualified_schema")
    values={}
    if type(qualified["records"]) is not list:raise ValueError("record_schema")
    ledger=qc.scanner.scan(bodies[only_batch]) if bodies[only_batch] is not None else None
    entries=[e for e in qualified["records"] if type(e) is dict and e.get("batch")==only_batch]
    if qualified["batches"][only_batch]["status"]=="decoded":
        if ledger is None or ledger["disposition"]!="supported" or len(entries)!=ledger["record_count"]:raise ValueError("record_ledger")
        for entry,d in zip(entries,ledger["records"]):
            if any(type(entry.get(k)) is not int or entry[k]!=d[k] for k in ("ordinal","offset","length")):raise ValueError("record_ledger")
    for entry in qualified["records"]:
        if entry["batch"]!=only_batch:continue
        if qualified["batches"][entry["batch"]]["status"]!="decoded":continue
        bi=entry["batch"];raw=bodies[bi]
        if type(raw) is not bytes:raise ValueError("record_binding")
        offset,length=entry["offset"],entry["length"]
        if not qc._int(offset,0,len(raw)) or not qc._int(length,256,1048576) or offset+length>len(raw):raise ValueError("record_binding")
        record=raw[offset:offset+length]
        ledger=qc.scanner.scan(record)
        if ledger["disposition"]!="supported" or ledger["record_count"]!=1:raise ValueError("record_binding")
        d=ledger["records"][0]
        start,rate,period=qc.header_grid(d)
        if (hashlib.sha256(record).hexdigest()!=entry["raw_sha256"] or d["nslc"]!=entry["nslc"]
                or d["npts"]!=entry["advertised_samples"] or start!=entry["start_ns"]
                or qc.pair(rate)!=entry["rate"] or qc.pair(period)!=entry["period"]):raise ValueError("record_binding")
        if d["npts"]:
            out=decode_record(record,d)
            expected_dtype={1:"i4",3:"i4",4:"f4",5:"f8",10:"i4",11:"i4"}[d["encoding"]]
            if (not qc._keys(out,("start_ns","rate","dtype","values")) or type(out["start_ns"]) is not int
                    or type(out["rate"]) is not float or entry["dtype"]!=expected_dtype or entry["observed_samples"]!=d["npts"]
                    or out["start_ns"]!=start or len(out["values"])!=d["npts"] or out["dtype"]!=entry["dtype"]
                    or not math.isfinite(out["rate"]) or abs(Fraction.from_float(float(out["rate"]))-rate)>max(Fraction(1,10**12),rate/10**12)
                    or qc.sample_hash(out["values"],out["dtype"])!=entry["samples_sha256"]):raise ValueError("record_replay")
            array=np.asarray(out["values"])
        else:
            array=np.empty(0,dtype=np.int32)
            if entry["samples_sha256"]!=hashlib.sha256(b"empty\0").hexdigest():raise ValueError("record_replay")
        key=(bi,entry["ordinal"])
        if key in values:raise ValueError("record_duplicate")
        values[key]=(entry,array)
    return values


def build(plan,qualified,bodies,metadata,decode_record):
    metadata_validate(metadata,plan)
    qc.validate(plan,bodies)
    records={};cached_batch=None
    arrays=dict(amplitudes=np.zeros((65,3,4),dtype=np.float32),contexts=np.zeros((65,3,29),dtype=np.float64),
                magnitudes=np.asarray([m["mw"] for m in metadata],dtype=np.float64),
                groups=np.asarray([m["group"] for m in metadata],dtype=np.int32),
                partitions=np.asarray([m["partition"]=="DEV" for m in metadata],dtype=np.uint8),
                cohort=np.zeros(65,dtype=np.uint8))
    shared={g for g in set(m["group"] for m in metadata) if len({m["partition"] for m in metadata if m["group"]==g})>1}
    rows=[];elements=0
    for i,row in enumerate(plan["rows"]):
        if cached_batch!=row["batch"]:
            records.clear()
            records=_reconstruct(plan,qualified,bodies,decode_record,row["batch"])
            cached_batch=row["batch"]
        meta=metadata[i];channels=qc.channels(row);cells=[]
        qrow=qualified["rows"][i]
        if any(qrow[k]!=row[k] for k in ("ordinal","partition","batch","family")):raise ValueError("row_binding")
        if type(qrow["cells"]) is not list or len(qrow["cells"])!=3:raise ValueError("row_binding")
        for j,h in enumerate((1,3,5)):
            reason="supported"
            cell=qrow["cells"][j]
            if cell["horizon"]!=h or cell["cutoff_ns"]!=row["t0_ns"]+h*10**9 or cell["pick_before_cutoff"]!=(row["pick_ns"]<row["t0_ns"]+h*10**9):raise ValueError("cell_binding")
            if not channels:reason="metadata_unknown"
            elif not meta["operational_eligible"] or meta["group"] in shared:reason="operational_ineligible"
            elif cell["joint"]["status"]!="complete" or not cell["pick_before_cutoff"]:reason="qualification_unknown"
            if reason!="supported":cells.append(_empty_cell(h,reason,channels));continue
            components={c["channel"]:c for c in cell["components"]}
            if len(components)!=len(cell["components"]) or any(c not in components for c in channels):raise ValueError("component_binding")
            selected=[components[c] for c in channels]
            grids={(tuple(c["first"]),tuple(c["rate"]),c["count"]) for c in selected}
            if len(grids)!=1 or any(c["status"]!="complete" for c in selected):cells.append(_empty_cell(h,"grid_mismatch",channels));continue
            if elements+3*selected[0]["count"]>MAX_ELEMENTS:raise RuntimeError("artifact_element_cap")
            native=[];hashes=[]
            try:
                for c in selected:
                    chunks=[];composition=[];accumulated=0
                    component_first=Fraction(*c["first"]);component_period=Fraction(10**9)/Fraction(*c["rate"])
                    for piece in c["pieces"]:
                        entry,array=records[(row["batch"],piece["record"])]
                        if entry["nslc"]!=[row["network"],row["station"],row["location"],c["channel"]]:raise ValueError("piece_identity")
                        period=Fraction(*entry["period"]);start=entry["start_ns"]
                        lo=max(0,qc._ceil((Fraction(row["t0_ns"]-3*10**9)-start)/period))
                        hi=min(len(array),qc._ceil((Fraction(row["t0_ns"]+h*10**9)-start)/period))
                        if (lo!=piece["lo"] or hi!=piece["hi"] or hi<=lo or piece["count"]!=hi-lo
                                or piece["first"]!=qc.pair(Fraction(start)+lo*period)
                                or piece["last"]!=qc.pair(Fraction(start)+(hi-1)*period)
                                or piece["period"]!=entry["period"] or piece["dtype"]!=entry["dtype"]
                                or qc.sample_hash(array[lo:hi],entry["dtype"])!=piece["samples_sha256"]):raise ValueError("piece_binding")
                        if period!=component_period or Fraction(*piece["first"])!=component_first+accumulated*component_period:raise ValueError("exact_lattice")
                        accumulated+=hi-lo
                        chunks.append(array[lo:hi])
                        composition.append({k:piece[k] for k in ("record","lo","hi","count","first","last","period","dtype","samples_sha256")})
                    if hashlib.sha256(canonical(composition)).hexdigest()!=c["view_sha256"]:raise ValueError("view_hash")
                    combined=np.concatenate(chunks)
                    if len(combined)!=c["count"] or not np.isfinite(combined).all():raise ValueError("view_values")
                    native.append(combined);hashes.append(c["view_sha256"])
                first=Fraction(*selected[0]["first"]);rate=Fraction(*selected[0]["rate"]);period=Fraction(10**9)/rate
                pre=max(0,min(len(native[0]),qc._ceil((Fraction(row["t0_ns"])-first)/period)))
                if not pre:cells.append(_empty_cell(h,"no_precontext",channels));continue
                wave,amplitude=preprocess(np.stack(native),pre)
                elements+=wave.size
                if elements>MAX_ELEMENTS:raise RuntimeError("artifact_element_cap")
                name="wave_%02d_%d"%(i,h);arrays[name]=wave;arrays["amplitudes"][i,j]=amplitude
                arrays["contexts"][i,j]=context(row,meta,h,rate)
                cells.append(dict(horizon=h,status="available",reason="supported",array=name,shape=list(wave.shape),
                                  first=qc.pair(first),period=qc.pair(period),precontext_count=pre,channels=channels,view_sha256=hashes))
            except (ValueError,KeyError,TypeError,IndexError):
                cells.append(_empty_cell(h,"reconstruction_unknown",channels))
        common=all(c["status"]=="available" for c in cells);arrays["cohort"][i]=common
        rows.append(dict(ordinal=i,partition=row["partition"],group=meta["group"],mw=float(meta["mw"]),cohort=common,cells=cells))
    manifest=dict(schema="earthquake-native-count-artifact-v1",study=qc.STUDY,rows=rows,denominators=dict(rows=65,cells=195,train=41,dev=24,test_excluded=31))
    return arrays,manifest


def save_npz(arrays):
    if type(arrays) is not dict or not META_NAMES.issubset(arrays) or len(arrays)>201:raise ValueError("archive_members")
    total=elements=0
    for name,value in arrays.items():
        match=WAVE.fullmatch(name) if type(name) is str else None
        if name not in META_NAMES and (not match or int(match[1])>64):raise ValueError("archive_member")
        if type(value) is not np.ndarray or value.dtype.hasobject or value.dtype.kind not in "fiu" or not np.isfinite(value).all():raise ValueError("npy_type")
        if match:
            if value.dtype.str!="<f4" or value.ndim!=2 or value.shape[0]!=3 or value.shape[1]<=0:raise ValueError("wave_shape")
            elements+=value.size
        expected={"amplitudes":("<f4",(65,3,4)),"contexts":("<f8",(65,3,29)),"magnitudes":("<f8",(65,)),"groups":("<i4",(65,)),"partitions":("|u1",(65,)),"cohort":("|u1",(65,))}
        if not match and (value.dtype.str,value.shape)!=expected[name]:raise ValueError("metadata_shape")
        # Exact NPY header and payload accounting precedes compression/writer allocation.
        head=io.BytesIO();np.lib.format.write_array_header_1_0(head,np.lib.format.header_data_from_array_1_0(value))
        if len(head.getvalue())>4106:raise ValueError("npy_header_cap")
        total+=len(head.getvalue())+value.nbytes
    if elements>MAX_ELEMENTS or total>MAX_UNCOMPRESSED:raise ValueError("artifact_element_cap")
    stream=io.BytesIO();np.savez_compressed(stream,**arrays);raw=stream.getvalue()
    inspect_npz(raw)
    return raw


def inspect_npz(raw):
    if type(raw) is not bytes or len(raw)>MAX_ARCHIVE:raise ValueError("archive_cap")
    total=elements=0;headers={}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos=archive.infolist()
        if len(infos)>201:raise ValueError("archive_members")
        for info in infos:
            if info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or not info.filename.endswith(".npy"):raise ValueError("archive_member")
            name=info.filename[:-4];match=WAVE.fullmatch(name)
            if name in headers or (name not in META_NAMES and not match) or (match and int(match[1])>64):raise ValueError("archive_member")
            total+=info.file_size
            if total>MAX_UNCOMPRESSED or info.file_size<10:raise ValueError("archive_payload")
            with archive.open(info) as source:
                prefix=source.read(12)
                if prefix[:6]!=b"\x93NUMPY" or prefix[6:8] not in (b"\x01\x00",b"\x02\x00",b"\x03\x00"):raise ValueError("npy_header")
                width=2 if prefix[6]==1 else 4
                size=int.from_bytes(prefix[8:8+width],"little")
                if size>4096:raise ValueError("npy_header_cap")
            # Header reader is bounded to the admitted small prefix, before np.load.
            with archive.open(info) as source:
                headerbytes=source.read(8+width+size)
            import ast
            header=ast.literal_eval(headerbytes[8+width:].decode("latin1"))
            if type(header) is not dict or set(header)!={"descr","fortran_order","shape"} or header["fortran_order"] is not False:raise ValueError("npy_header")
            dtype=np.dtype(header["descr"]);shape=header["shape"]
            if (dtype.hasobject or dtype.kind not in "fiu" or type(shape) is not tuple
                    or any(type(x) is not int or x<0 for x in shape)):raise ValueError("npy_type")
            count=math.prod(shape)
            if 8+width+size+count*dtype.itemsize!=info.file_size:raise ValueError("npy_payload")
            expected={"amplitudes":("<f4",(65,3,4)),"contexts":("<f8",(65,3,29)),"magnitudes":("<f8",(65,)),"groups":("<i4",(65,)),"partitions":("|u1",(65,)),"cohort":("|u1",(65,))}
            if match:
                if dtype.str!="<f4" or len(shape)!=2 or shape[0]!=3 or shape[1]<=0:raise ValueError("wave_shape")
                elements+=count
            elif (dtype.str,shape)!=expected[name]:raise ValueError("metadata_shape")
            if elements>MAX_ELEMENTS:raise ValueError("artifact_element_cap")
            headers[name]=(dtype.str,shape)
    if not META_NAMES.issubset(headers):raise ValueError("archive_members")
    return headers


def load_npz(raw,manifest):
    validate_manifest(manifest)
    headers=inspect_npz(raw)
    expected=META_NAMES|{c["array"] for r in manifest["rows"] for c in r["cells"] if c["status"]=="available"}
    if set(headers)!=expected:raise ValueError("manifest_members")
    with np.load(io.BytesIO(raw),allow_pickle=False) as loaded:
        arrays={name:loaded[name] for name in headers}
    if any(not np.isfinite(v).all() for v in arrays.values()):raise ValueError("artifact_finite")
    for row in manifest["rows"]:
        i=row["ordinal"]
        if (arrays["magnitudes"][i]!=row["mw"] or arrays["groups"][i]!=row["group"]
                or arrays["partitions"][i]!=(row["partition"]=="DEV") or arrays["cohort"][i]!=row["cohort"]):raise ValueError("manifest_metadata")
        for cell in row["cells"]:
            if cell["status"]=="available" and list(arrays[cell["array"]].shape)!=cell["shape"]:raise ValueError("manifest_shape")
    return arrays


def validate_manifest(manifest):
    if (not qc._keys(manifest,("schema","study","rows","denominators")) or manifest["schema"]!="earthquake-native-count-artifact-v1"
            or manifest["study"]!=qc.STUDY or canonical(manifest["denominators"])!=canonical(dict(rows=65,cells=195,train=41,dev=24,test_excluded=31))
            or type(manifest["rows"]) is not list or len(manifest["rows"])!=65):raise ValueError("manifest_schema")
    partitions=[]
    for i,row in enumerate(manifest["rows"]):
        if (not qc._keys(row,("ordinal","partition","group","mw","cohort","cells")) or not qc._int(row["ordinal"],i,i)
                or type(row["partition"]) is not str or row["partition"] not in ("TRAIN","DEV") or not qc._int(row["group"],0,64)
                or not _finite(row["mw"]) or type(row["cohort"]) is not bool or type(row["cells"]) is not list or len(row["cells"])!=3):raise ValueError("manifest_row")
        partitions.append(row["partition"])
        for h,cell in zip((1,3,5),row["cells"]):
            if (not qc._keys(cell,("horizon","status","reason","array","shape","first","period","precontext_count","channels","view_sha256"))
                    or not qc._int(cell["horizon"],h,h) or type(cell["channels"]) is not list):raise ValueError("manifest_cell")
            if cell["status"]=="available":
                if (cell["reason"]!="supported" or cell["array"]!="wave_%02d_%d"%(i,h) or type(cell["shape"]) is not list or len(cell["shape"])!=2
                        or cell["shape"][0]!=3 or not qc._int(cell["shape"][1],1,MAX_ELEMENTS//3)
                        or not qc._int(cell["precontext_count"],1,cell["shape"][1]) or len(cell["channels"])!=3
                        or type(cell["view_sha256"]) is not list or len(cell["view_sha256"])!=3 or not all(qc._sha(v) for v in cell["view_sha256"])):raise ValueError("manifest_cell")
                qc._rational(cell["period"])
                f=cell["first"]
                if type(f) is not list or len(f)!=2 or any(type(v) is not int for v in f) or f[1]<=0 or math.gcd(*f)!=1:raise ValueError("manifest_cell")
            elif cell["status"]!="unavailable" or cell["reason"] not in ("metadata_unknown","operational_ineligible","qualification_unknown","grid_mismatch","no_precontext","reconstruction_unknown") or any(cell[k] is not None for k in ("array","shape","first","period","precontext_count","view_sha256")):raise ValueError("manifest_cell")
        if row["cohort"]!=all(c["status"]=="available" for c in row["cells"]):raise ValueError("manifest_cohort")
    if partitions.count("TRAIN")!=41 or partitions.count("DEV")!=24:raise ValueError("manifest_partition")

"""Authored synthetic headers only; never actual waveforms or vendor encoding."""
import struct
import hashlib
import numpy as np
import qualified_core as qc
START=1704067200000000000

def raw_record(channel="HHZ", values=None, *, start_second=0, factor=1,
               multiplier=1, encoding=3, correction=0, activity=0,
               micros=None, rate100=None, station="ABC", reserved=0):
    values = list(range(9)) if values is None else values
    raw = bytearray(256)
    raw[:20] = b"000001D " + station.ljust(5).encode() + b"  " + channel.encode() + b"NZ"
    kinds = [1000] + ([100] if rate100 is not None else []) + ([1001] if micros is not None else [])
    offsets, cursor = [], 48
    for kind in kinds:
        offsets.append(cursor);cursor += 12 if kind == 100 else 8
    struct.pack_into(">HHBBBBHHhhBBBBiHH",raw,20,2024,1,0,0,start_second,0,0,len(values),
                     factor,multiplier,activity,0,0,len(kinds),correction,cursor,48)
    for i,(kind,offset) in enumerate(zip(kinds,offsets)):
        struct.pack_into(">HH",raw,offset,kind,offsets[i+1] if i+1<len(kinds) else 0)
        if kind == 1000:
            struct.pack_into("BBBB",raw,offset+4,encoding,1,8,reserved)
        elif kind == 100:
            struct.pack_into(">fBBBB",raw,offset+4,rate100,0,0,0,0)
        else:
            struct.pack_into("BbBB",raw,offset+4,90,micros,0,0)
    fmt = {1:"h",3:"i",4:"f",5:"d"}.get(encoding)
    if fmt:
        struct.pack_into(">"+fmt*len(values),raw,cursor,*values)
    return bytes(raw)

def fake_decode(raw,d):
    start,rate,_ = qc.header_grid(d)
    code = {1:"h",3:"i",4:"f",5:"d"}[d["encoding"]]
    values = list(struct.unpack_from(">"+code*d["npts"],raw,d["data_offset"]))
    return dict(start_ns=start,rate=float(rate),dtype={1:"i4",3:"i4",4:"f4",5:"f8"}[d["encoding"]],values=np.asarray(values,dtype={1:"i4",3:"i4",4:"f4",5:"f8"}[d["encoding"]]))

def inputs(body=None):
    body = b"".join(raw_record("HH"+suffix) for suffix in "EN12Z") if body is None else body
    rows=[]
    for i in range(65):
        family = "ENZ" if i<47 else "12Z" if i<61 else None
        suffixes = "ENZ" if family=="ENZ" else "12Z" if family=="12Z" else ""
        rows.append(dict(ordinal=i,partition="TRAIN" if i<41 else "DEV",batch=i//4,
                         network="NZ",station="ABC",location="",prefix="HH",t0_ns=START+3_000_000_000,
                         pick_ns=START+3_500_000_000,family=family,
                         nominal_rates={"HH"+s:[1,1] for s in suffixes}))
    bodies={i:body for i in range(17)}
    batches=[dict(ordinal=i,rows=list(range(4*i,min(4*i+4,65))),transport="http200",
                  body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest()) for i in range(17)]
    return dict(study=qc.STUDY,rows=rows,batches=batches),bodies

def metadata():
    return [dict(ordinal=i,partition="TRAIN" if i<41 else "DEV",mw=6.0 if i%2==0 else 4.0,
                 group=i,operational_eligible=True,station_latitude=-41.,station_longitude=174.,station_elevation=10.,
                 sensitivities=[1.,10.,100.],units=["M/S","M/S**2","M"]) for i in range(65)]


def build_fixture(body=None):
    import artifact
    plan,bodies=inputs(body)
    qualified=qc.qualify(plan,bodies,fake_decode)
    arrays,manifest=artifact.build(plan,qualified,bodies,metadata(),fake_decode)
    return plan,bodies,qualified,arrays,manifest

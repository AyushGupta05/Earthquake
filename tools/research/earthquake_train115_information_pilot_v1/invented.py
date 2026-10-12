"""Authored manual headers and synthetic numeric artifacts; no actual inputs."""
import copy
import hashlib
import time
import numpy as np
import artifact
import invented_old as prior
import new_core as qc


def inputs(missing=(),body=None):
    absent=set(missing);body=b''.join(prior.raw_record('HH'+s) for s in 'EN12Z') if body is None else body
    rows=[]
    for i in range(50):
        queryable=i not in absent;family=('ENZ' if i%2==0 else '12Z') if queryable else None
        codes='ENZ' if family=='ENZ' else '12Z' if family=='12Z' else ''
        rows.append(dict(ordinal=i,global_ordinal=65+i,partition='TRAIN',batch=i//4,queryable=queryable,
                         network='NZ' if queryable else None,station='ABC' if queryable else None,location='' if queryable else None,
                         prefix='HH' if queryable else None,t0_ns=prior.START+3*10**9,pick_ns=prior.START+3500000000 if queryable else None,
                         family=family,nominal_rates={'HH'+s:[1,1] for s in codes}))
    batches=[];bodies={}
    for i in range(13):
        ids=list(range(4*i,min(4*i+4,50)));requested=[j for j in ids if rows[j]['queryable']];raw=body if requested else None;bodies[i]=raw
        batches.append(dict(ordinal=i,rows=ids,requested_rows=requested,transport='http200' if requested else 'no_selection',body_bytes=len(raw) if raw else 0,body_sha256=hashlib.sha256(raw).hexdigest() if raw else None))
    return dict(study=qc.STUDY,rows=rows,batches=batches),bodies


def metadata():
    rows=prior.metadata()
    for i in range(65,115):rows.append(dict(ordinal=i,partition='TRAIN',mw=5.7 if i<79 else 4.,group=i,operational_eligible=True,station_latitude=-41.,station_longitude=174.,station_elevation=10.,sensitivities=[1.,10.,100.],units=['M/S','M/S**2','M']))
    return rows


def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def fixture(missing=(),body=None):
    _,_,_,old_arrays,old_manifest=prior.build_fixture()
    old_npz=artifact.old.save_npz(old_arrays);old_raw=artifact.canonical(old_manifest)
    plan,bodies=inputs(missing,body);qualified=qc.qualify(plan,bodies,prior.fake_decode);meta=metadata()
    raw=dict(old_npz=old_npz,old_manifest=old_raw,new_plan=artifact.canonical(plan),new_qualified=artifact.canonical(qualified),metadata=artifact.canonical(meta))
    return raw,bodies,{k:pin(v) for k,v in raw.items()},old_arrays,old_manifest,plan,qualified,meta


def build(f,decode=prior.fake_decode):
    raw,bodies,pins,*_=f
    return artifact.build_combined(raw['old_npz'],raw['old_manifest'],raw['new_plan'],raw['new_qualified'],bodies,raw['metadata'],decode,pins=pins,processing_begin=time.monotonic())


def changed(f,name,value):
    result=list(f);raw=dict(f[0]);raw[name]=artifact.canonical(value);pins=dict(f[2]);pins[name]=pin(raw[name]);result[0]=raw;result[2]=pins
    return tuple(result)

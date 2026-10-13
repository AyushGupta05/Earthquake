"""Invented miniSEED only. Reference sources load in an isolated module namespace."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time

import numpy as np
import marked_native as marked

START=1704067200000000000


def reference():
    base=Path(__file__).parent/'reference'
    pins=json.loads((base/'SOURCE_PINS.json').read_text())
    for p in pins:
        assert hashlib.sha256((base/p['file']).read_bytes()).hexdigest()==p['sha256']
    names=('old_scanner','new_scanner','decode_contract','old_native','new_native','activity_math','observations')
    prior={name:sys.modules.get(name) for name in names};loaded={}
    try:
        for name in names:
            spec=importlib.util.spec_from_file_location(name,base/(name+'.py'))
            obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj);loaded[name]=obj
    finally:
        for name,obj in prior.items():
            if obj is None:sys.modules.pop(name,None)
            else:sys.modules[name]=obj
    return loaded['observations']


OBS=reference()
BINDINGS=marked.Bindings(OBS)


def record(channel,index,tag,namespace):
    # Namespace alters native values despite identical local record ordinals.
    component='EN12Z'.index(channel[-1]);encoding=(3,4,5)[(component+tag+index)%3]
    dtype={3:'i4',4:'f4',5:'f8'}[encoding]
    values=[];base=20_000_001 if encoding==3 else 1024.125
    for k in range(256):
        cell=(index*256+k)//16
        amplitude=(cell+1)*(component+1) if cell<12 else (0 if (cell-12)%5==2 else 10+7*((cell-12)%5)+namespace)
        v=base+amplitude*(1 if k%2 else -1)
        values.append(int(v) if encoding==3 else float(v))
    raw=bytearray(4096);station='ABC'+str(tag)
    raw[:20]=b'000001D '+station.ljust(5).encode()+b'  '+channel.encode()+b'NZ'
    struct.pack_into('>HHBBBBHHhhBBBBiHH',raw,20,2024,1,0,0,index*4,0,0,len(values),64,1,0,0,0,1,0,56,48)
    struct.pack_into('>HHBBBB',raw,48,1000,0,encoding,1,12,0)
    struct.pack_into('>'+{'i4':'i','f4':'f','f8':'d'}[dtype]*len(values),raw,56,*values)
    return bytes(raw)


def decode(raw,d):
    start,rate,_=OBS.new_native.header_grid(d)
    dtype={3:'i4',4:'f4',5:'f8'}[d['encoding']]
    # Preserve native width before byte-hash validation; endian is in the header.
    values=np.frombuffer(raw,dtype=np.dtype('>'+dtype),count=d['npts'],offset=d['data_offset']).copy()
    return dict(start_ns=start,rate=float(rate),dtype=dtype,values=values)


def corpus():
    pairs=[]
    for n,b,core,namespace in ((65,17,OBS.old_native,1),(50,13,OBS.new_native,2)):
        rows=[];bodies={};batches=[]
        for i in range(n):
            family='ENZ' if n==50 or i>=61 or 4<=i<47 else '12Z' if 47<=i<61 else None
            row=dict(ordinal=i,partition='TRAIN' if n==50 or i<41 else 'DEV',batch=i//4,
                     network='NZ',station='ABC'+str(i%4),location='',prefix='HH',t0_ns=START+3*10**9,
                     pick_ns=START+3*10**9+(0,125_000_000,250_000_000,750_000_000)[i%4],family=family,
                     nominal_rates={'HH'+s:[64,1] for s in ('ENZ' if family=='ENZ' else '12Z' if family=='12Z' else '')})
            if n==50:row.update(global_ordinal=65+i,queryable=True)
            rows.append(row)
        for bi in range(b):
            indices=list(range(4*bi,min(4*bi+4,n)));tags=sorted({i%4 for i in indices})
            body=b''.join(record('HH'+c,j,tag,namespace) for tag in tags for c in 'EN12Z' for j in (0,1))
            bodies[bi]=body
            batch=dict(ordinal=bi,rows=indices,transport='http200',body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
            if n==50:batch['requested_rows']=list(indices)
            batches.append(batch)
        plan=dict(study=core.STUDY,rows=rows,batches=batches)
        qualified=core.qualify(plan,bodies,decode)
        assert qualified['disposition']=='complete'
        pairs.append((plan,qualified,bodies))
    metadata=[];roles=[]
    for i in range(115):
        metadata.append(dict(ordinal=i,partition='TRAIN' if i<41 or i>=65 else 'DEV',mw=6. if i%3==0 else 4.5,
                             group=i,operational_eligible=True,station_latitude=float(i%15),station_longitude=float(i%17),
                             station_elevation=float(i%11),sensitivities=[10.,20.,30.],units=['M/S','M/S**2','M']))
        roles.append(dict(ordinal=i,common=4<=i<63 or 65<=i<93))
    roster=dict(schema='receiver-renewal-roster-v1',study=OBS.STUDY,rows=roles)
    op,oq,ob=pairs[0];np_,nq,nb=pairs[1]
    values=dict(old_plan=op,old_qualified=oq,new_plan=np_,new_qualified=nq,metadata=metadata,roster=roster)
    raw={k:marked.canonical(v) for k,v in values.items()};pins={k:marked.pin(v) for k,v in raw.items()}
    original=OBS.build(raw['old_plan'],raw['old_qualified'],ob,raw['new_plan'],raw['new_qualified'],nb,
                       raw['metadata'],raw['roster'],decode,pins=pins,processing_begin=time.monotonic())
    anchor=marked.project_anchor(original,source_pins=dict(archive=marked.pin(b'invented archive'),manifest=marked.pin(b'invented manifest')))
    raw['activity_anchor']=anchor;pins['activity_anchor']=marked.pin(anchor)
    return dict(raw=raw,pins=pins,pairs=pairs,metadata=metadata,roster=roster,original=original)


def build(c,decode_record=decode):
    r=c['raw']
    return marked.build_marked(r['old_plan'],r['old_qualified'],c['pairs'][0][2],r['new_plan'],r['new_qualified'],c['pairs'][1][2],
                               r['metadata'],r['roster'],r['activity_anchor'],decode_record,
                               bindings=BINDINGS,pins=c['pins'],processing_begin=time.monotonic())


def one_native(c,i=4):
    ns=0 if i<65 else 1;j=i if i<65 else i-65
    plan,q,bodies=c['pairs'][ns];core=OBS.old_native if ns==0 else OBS.new_native
    records=OBS.replay_batch(core,plan,q,bodies,decode,plan['rows'][j]['batch'],dict(old=0,new=0),'old' if ns==0 else 'new',time.monotonic())
    return OBS.components(core,plan['rows'][j],q['rows'][j],records),plan['rows'][j],c['metadata'][i]


def event_anchor(native,row,meta):
    initial,hs=OBS.event_observations(native,row,meta)
    return dict(context35=initial['context'].tolist(),horizons=[dict(seconds=h['seconds'],status='available',**{k:h[k] for k in ('ratios','states','run_ages')}) for h in hs])

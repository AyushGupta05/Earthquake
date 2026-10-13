"""Hand-derived synthetic counts/grid oracle; no candidate imports or actual data."""
import copy
import hashlib
import math
import struct
import time
import numpy as np
import auditor
import old_native
import new_native
START=1704067200000000000
VALUES=[-1,1]*6+[-1,-1,4,4,3,1,4,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1]

def record(channel,values=None,encoding=3,start_second=0):
    values=VALUES if values is None else values
    raw=bytearray(256);raw[:20]=b'000001D ABC    '+channel.encode()+b'NZ'
    struct.pack_into('>HHBBBBHHhhBBBBiHH',raw,20,2024,1,0,0,start_second,0,0,len(values),4,1,0,0,0,1,0,56,48)
    struct.pack_into('>HHBBBB',raw,48,1000,0,encoding,1,8,0)
    code={3:'i',4:'f',5:'d'}[encoding]
    struct.pack_into('>'+code*len(values),raw,56,*values)
    return bytes(raw)

def decode(raw,d):
    start,rate,_=old_native.header_grid(d)
    dtype={3:'i4',4:'f4',5:'f8'}[d['encoding']];code={3:'i',4:'f',5:'d'}[d['encoding']]
    a=np.asarray(struct.unpack_from('>'+code*d['npts'],raw,d['data_offset']),dtype=dtype)
    return dict(start_ns=start,rate=float(rate),dtype=dtype,values=a)

def oracle(row,m):
    # This fixture's arithmetic is known: mean0, all12prequarterpowers1,
    # shared4Hz grid, delta.5, initial scalar4, hence active b1 and scale4.
    shared=[math.log10(4),-41.,174.,10.,0.,0.,0.,float(row['family']=='ENZ'),float(row['family']=='12Z'),0.,1.,2.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.]
    noise=[0.]*6
    def tensors(a):
        x=np.asarray([a]*3,dtype=np.float64)/4.
        rms=np.sqrt(np.mean(x*x,axis=1))
        return np.ascontiguousarray(x,dtype=np.float32),np.asarray([math.log10(4)]+[math.log10(float(v)*4) for v in rms],dtype=np.float32)
    w,amp=tensors([4]);initial=dict(wave=w,amplitude=amp,context=np.asarray(noise+[1.,.5]+shared,dtype=np.float64));hs=[]
    for h in (1,3,5):
        ratios=[float(v*v) for v in VALUES[14:12+4*h]];states=[int(v>9) for v in ratios];ages=[]
        for k,s in enumerate(states):ages.append(ages[-1]+1 if k and s==states[k-1] else 1)
        w,amp=tensors(VALUES[:12+4*h])
        hs.append(dict(seconds=h,rate=[4,1],wave=w,amplitude=amp,context=np.asarray(noise+[1.,float(h),.5]+shared,dtype=np.float64),ratios=ratios,states=states,run_ages=ages))
    return initial,hs

def fixture():
    body=b''.join(record('HH'+s) for s in 'EN12Z');plans=[];qs=[];bodies=[];meta=[];roster=[]
    for n,core,offset in ((65,old_native,0),(50,new_native,65)):
        rows=[];bs={i:body for i in range((n+3)//4)}
        for i in range(n):
            g=offset+i;family=('ENZ' if i<34 or 38<=i<=50 else '12Z' if i>=51 else None) if offset==0 else 'ENZ'
            r=dict(ordinal=i,partition='TRAIN' if g<41 or g>=65 else 'DEV',batch=i//4,network='NZ',station='ABC',location='',prefix='HH',t0_ns=START+3*10**9,pick_ns=START+3500000000,family=family,nominal_rates={'HH'+s:[4,1] for s in ('ENZ' if family=='ENZ' else '12Z' if family=='12Z' else '')})
            if offset:r.update(global_ordinal=g,queryable=True)
            rows.append(r)
            m=dict(ordinal=g,partition=r['partition'],mw=6.0 if g%2 else 4.,group=g,operational_eligible=True,station_latitude=-41.,station_longitude=174.,station_elevation=10.,sensitivities=[1.,10.,100.],units=['M/S','M/S**2','M'])
            meta.append(m);roster.append(dict(ordinal=g,common=(g<34 or 41<=g<=62 or 65<=g<=95)))
        batches=[]
        for bi in bs:
            b=dict(ordinal=bi,rows=list(range(4*bi,min(n,4*bi+4))),transport='http200',body_bytes=len(body),body_sha256=hashlib.sha256(body).hexdigest())
            if offset:b['requested_rows']=list(b['rows'])
            batches.append(b)
        p=dict(study=core.STUDY,rows=rows,batches=batches);q=core.qualify(p,bs,decode)
        assert q['disposition']=='complete',q['reason']
        plans.append(p);qs.append(q);bodies.append(bs)
    roster=dict(schema='receiver-renewal-roster-v1',study=auditor.STUDY,rows=roster)
    raw=dict(old_plan=auditor.canonical(plans[0]),old_qualified=auditor.canonical(qs[0]),new_plan=auditor.canonical(plans[1]),new_qualified=auditor.canonical(qs[1]),metadata=auditor.canonical(meta),roster=auditor.canonical(roster));pins={k:auditor.pin(v) for k,v in raw.items()}
    rows=[]
    for i,m in enumerate(meta):
        yes=roster['rows'][i]['common'];r=dict(ordinal=i,partition=m['partition'],mw=m['mw'],group=i,common=yes,status='available' if yes else 'unavailable',initial=None,horizons=[dict(seconds=h,status='unavailable') for h in (1,3,5)])
        if yes:r['initial'],r['horizons']=oracle(plans[0]['rows'][i] if i<65 else plans[1]['rows'][i-65],m)
        rows.append(r)
    packet=dict(schema=auditor.SCHEMA,study=auditor.STUDY,rows=rows,denominators=dict(events=115,cells=345,train=91,dev=24,test_excluded=31),observed_samples=dict(old=15*5*36,new=8*5*36),input_pins=copy.deepcopy(pins),fit_authorized=False)
    return dict(raw=raw,pins=pins,plans=plans,qs=qs,bodies=bodies,meta=meta,roster=roster,packet=packet)

def run(f,decode_record=decode,begin=None):
    r=f['raw'];return auditor.audit(r['old_plan'],r['old_qualified'],f['bodies'][0],r['new_plan'],r['new_qualified'],f['bodies'][1],r['metadata'],r['roster'],f['packet'],decode_record,input_pins=f['pins'],processing_begin=time.monotonic() if begin is None else begin)

def changed(f,k,v):
    f=copy.deepcopy(f);f['raw'][k]=auditor.canonical(v);f['pins'][k]=auditor.pin(f['raw'][k]);f['packet']['input_pins']=copy.deepcopy(f['pins']);return f

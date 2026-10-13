"""Invented marked packets; no private paths, actual data or model states."""
import importlib.util
import math
import json
import hashlib
from pathlib import Path
import statistics
import sys
import numpy as np
import processor as p
import numeric_state as ns


def load(name):
    base=Path(__file__).parent/'reference'
    pins=json.loads((base/'SOURCE_PINS.json').read_text())
    pin=next(x for x in pins if x['file']==name+'.py')
    path=base/(name+'.py')
    raw=path.read_bytes();assert len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256']
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module); return module


native=load('marked_native'); previous=sys.modules.get('marked_native'); sys.modules['marked_native']=native
try: store=load('native_packet_io')
finally:
    if previous is None:sys.modules.pop('marked_native',None)
    else:sys.modules['marked_native']=previous
op=load('gaussian_operator'); core=load('reference_core')


def bindings():
    pins={k:dict(bytes=1,sha256=ns.digest(k.encode())) for k in ('operator','native_validator','reference','processor','protocol')}
    return p.Bindings(op,store,core,pins)


def packet():
    rows=[]
    for i in range(115):
        common=4<=i<63 or 65<=i<93; role='TRAIN' if i<41 or i>=65 else 'DEV'; magnitude=4.+.045*(i%50)
        row=dict(ordinal=i,partition=role,mw=magnitude,group=i,common=common,status='available' if common else 'unavailable',precontext=None,noise=None,
                 horizons=[dict(seconds=h,status='unavailable') for h in (1,3,5)])
        if common:
            powers=np.asarray([[2.+.02*i+.1*c+.4*math.sin((j+1)*(.3+.01*i)+c)**2 for j in range(12)] for c in range(3)],dtype='<f8')
            rawmed=[statistics.median(q.tolist()) for q in powers]; nhat=np.asarray(rawmed,dtype='<f8')
            eta=[[math.log(statistics.median(q.tolist()[:ell]+q.tolist()[ell+1:])) for q in powers] for ell in range(12)]
            means=[math.fsum(e[c] for e in eta)/12 for c in range(3)]
            nu=np.asarray([[e[c]-means[c] for c in range(3)] for e in eta],dtype='<f8'); offset=(i%4)*250000000
            noise=dict(centers=np.zeros(3,dtype='<f8'),powers=powers,nhat=nhat,floors=np.zeros(3,dtype='u1'),nu=nu,
                       weights=np.asarray([1/12]*12,dtype='<f8'),rate=[100,1],arrival_offset_ns=offset)
            ctx=np.zeros(34,dtype='<f8'); ctx[:3]=[math.log10(x) for x in nhat];ctx[6:11]=[offset/1e9,2.,float(i%17),float(i%13),float(i%11)]
            ctx[14]=1.;ctx[16:19]=[1.,2.,3.];ctx[22]=ctx[27]=ctx[32]=1.
            j5=(5*10**9-offset)//250000000
            ratios=np.asarray([[math.exp(.25*magnitude+.15*c+.025*j+.3*math.sin(i+j+c)) for c in range(3)] for j in range(j5)],dtype='<f8')
            ys=np.asarray([[math.log(x) for x in q] for q in ratios],dtype='<f8'); states=np.asarray([int(max(q)>9.) for q in ratios],dtype='u1');ages=[];old=None;age=0
            for s in states:age=age+1 if s==old else 1;ages.append(age);old=s
            horizons=[]
            for h in (1,3,5):
                n=(h*10**9-offset)//250000000
                horizons.append(dict(seconds=h,status='available',ratios=ratios[:n].copy(),reported=ys[:n].copy(),censor=np.zeros((n,3),dtype='u1'),
                                     max_ratios=np.asarray([max(q) for q in ratios[:n]],dtype='<f8'),states=states[:n].copy(),run_ages=np.asarray(ages[:n],dtype='u1')))
            row.update(noise=noise,precontext=ctx,horizons=horizons)
        rows.append(row)
    return dict(schema=native.SCHEMA,study=native.STUDY,rows=rows,denominators=native.DENOMINATORS.copy(),
                input_pins={k:dict(bytes=1,sha256=ns.digest(k.encode())) for k in native.LIMITS},observed_samples=dict(old=0,new=0),fit_authorized=False)


class Sink:
    def __init__(self,fail_kind=None,fail_update=None):self.records=[];self.fail_kind=fail_kind;self.fail_update=fail_update
    def __call__(self,kind,raw):
        obj=ns.decode(raw,ns.digest(raw));self.records.append((kind,obj,raw))
        if kind==self.fail_kind and (self.fail_update is None or obj.get('update')==self.fail_update):raise RuntimeError('invented durable failure')
        return dict(status='durable',sha256=ns.digest(raw))

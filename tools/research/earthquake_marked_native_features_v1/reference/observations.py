"""Pure pinned-native observations; no paths, inference fields or learning from roles."""
from fractions import Fraction
import hashlib
import json
import math
import time
import numpy as np
import activity_math as am
import old_native
import new_native

STUDY='earthquake-TRAIN115-receiver-renewal-v2'
SCHEMA='earthquake-TRAIN115-receiver-observations-v2'
MAX_SECONDS=300
MAX_ELEMENTS=20_000_000
MAX_BYTES=128*1024*1024
PIECE_KEYS=('record','lo','hi','count','first','last','period','dtype','samples_sha256')


def need(test,code):
    if not test:raise ValueError(code)


def deadline(begin):
    need(type(begin) in (int,float) and math.isfinite(begin) and 0<=begin<=time.monotonic(),'processing_begin')
    need(time.monotonic()-begin<=MAX_SECONDS,'observation_deadline')


def canonical(value):return new_native.canonical(value)


def same(a,b):return canonical(a)==canonical(b)


def json_load(raw,cap):
    need(type(raw) is bytes and len(raw)<=cap,'json_cap')
    def pairs(items):
        out={}
        for k,v in items:
            need(k not in out,'duplicate_key');out[k]=v
        return out
    def integer(text):
        need(len(text.lstrip('-'))<=1024,'json_integer');return int(text)
    value=json.loads(raw.decode('utf8'),object_pairs_hook=pairs,parse_int=integer,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('json_nonfinite')))
    todo=[(value,0)];nodes=0
    while todo:
        v,d=todo.pop();nodes+=1;need(d<=32 and nodes<=2_000_000,'json_structure')
        if type(v) is dict:todo.extend((x,d+1) for x in v.values())
        elif type(v) is list:todo.extend((x,d+1) for x in v)
        elif type(v) is float:need(math.isfinite(v),'json_nonfinite')
        elif type(v) is int:need(v.bit_length()<=4096,'json_integer')
    return value


def context(row,meta,h,rate):
    values=[float(h),(row['pick_ns']-row['t0_ns'])/1e9,math.log10(float(rate))]
    coords=[];missing=[]
    for k,lo,hi in [('station_latitude',-90,90),('station_longitude',-180,180),('station_elevation',-10000,10000)]:
        v=meta[k];valid=type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi
        coords.append(float(v) if valid else 0.);missing.append(float(not valid))
    values+=coords+missing+[float(row['family']=='ENZ'),float(row['family']=='12Z')]
    gains=[];missing=[]
    for v in meta['sensitivities']:
        valid=type(v) in (int,float) and math.isfinite(v) and v>0
        gains.append(math.log10(v) if valid else 0.);missing.append(float(not valid))
    values+=gains+missing
    for unit in meta['units']:
        category={'M/S':0,'M/S**2':1,'M':2}.get(unit,3) if type(unit) is str else 3
        values += [float(k==category) for k in range(4)]
    need(len(values)==29 and all(math.isfinite(x) for x in values),'context')
    return np.asarray(values,dtype=np.float64)


def metadata_validate(metadata,plans,roster):
    need(type(metadata) is list and len(metadata)==115,'metadata')
    need(new_native._keys(roster,('schema','study','rows')) and roster['schema']=='receiver-renewal-roster-v1'
         and roster['study']==STUDY and type(roster['rows']) is list and len(roster['rows'])==115,'roster')
    keys=('ordinal','partition','mw','group','operational_eligible','station_latitude','station_longitude','station_elevation','sensitivities','units')
    counts={'TRAIN':0,'DEV':0}
    for i,(m,r) in enumerate(zip(metadata,roster['rows'])):
        p=plans[0]['rows'][i] if i<65 else plans[1]['rows'][i-65]
        need(new_native._keys(m,keys) and new_native._int(m['ordinal'],i,i) and type(m['partition']) is str
             and m['partition']==p['partition'] and type(m['mw']) in (int,float) and math.isfinite(m['mw']) and -5<=m['mw']<=15
             and new_native._int(m['group'],-1,i) and type(m['operational_eligible']) is bool
             and not (m['group']==-1 and m['operational_eligible']),'metadata')
        need(new_native._keys(r,('ordinal','common')) and new_native._int(r['ordinal'],i,i) and type(r['common']) is bool,'roster')
        need(type(m['sensitivities']) is list and len(m['sensitivities'])==3 and type(m['units']) is list and len(m['units'])==3,'metadata')
        for v in [m[k] for k in ('station_latitude','station_longitude','station_elevation')]+m['sensitivities']:
            need(v is None or type(v) in (int,float) and math.isfinite(v),'metadata_number')
        need(all(v is None or type(v) is str and len(v)<=128 for v in m['units']),'metadata_units')
        if r['common']:
            need(m['group']>=0 and m['operational_eligible'],'roster_eligibility');counts[m['partition']]+=1
    mixed={m['group'] for m in metadata if m['group']>=0 and len({x['partition'] for x in metadata if x['group']==m['group']})>1}
    need(not any(r['common'] and m['group'] in mixed for r,m in zip(roster['rows'],metadata)),'mixed_group')
    need(counts=={'TRAIN':65,'DEV':22},'roster_counts')


def qualified_validate(core,plan,q,bodies,n,b):
    core.validate(plan,bodies)
    need(core._keys(q,('schema','study','disposition','reason','batches','records','rows','aggregate','claims'))
         and q['schema']==('geonet-POST-prefix-qualification-v2' if n==65 else 'geonet-TRAIN50-prefix-qualification-v1')
         and q['study']==plan['study'] and q['disposition']=='complete' and q['reason']=='supported','qualification')
    need(type(q['rows']) is list and len(q['rows'])==n and type(q['batches']) is list and len(q['batches'])==b
         and type(q['records']) is list and len(q['records'])<=b*32768
         and core._keys(q['claims'],core._CLAIMS) and all(v is False for v in q['claims'].values()),'qualification')
    for p,r in zip(plan['rows'],q['rows']):
        fields=('ordinal','partition','batch','family') if n==65 else ('ordinal','global_ordinal','partition','batch','family')
        need(core._keys(r,fields+('cells',)) and all(same(r[k],p[k]) for k in fields) and type(r['cells']) is list and len(r['cells'])==3,'qualified_row')
        for h,c in zip((1,3,5),r['cells']):
            cutoff=None if p['t0_ns'] is None else p['t0_ns']+h*10**9
            before=None if p.get('queryable',True) is False else p['pick_ns']<cutoff
            need(core._keys(c,('horizon','cutoff_ns','pick_before_cutoff','components','joint')) and same(c['horizon'],h)
                 and same(c['cutoff_ns'],cutoff) and same(c['pick_before_cutoff'],before) and type(c['components']) is list
                 and core._keys(c['joint'],('status','reason','rate','channels')),'qualified_cell')
    for i,batch in enumerate(q['batches']):
        need(core._keys(batch,('ordinal','status','reason','record_count','advertised_samples','observed_samples'))
             and core._int(batch['ordinal'],i,i) and type(batch['status']) is str and batch['status'] in ('decoded','unknown','nonpositive')
             and core._int(batch['record_count'],0,32768) and core._int(batch['advertised_samples'],0,8_000_000)
             and core._int(batch['observed_samples'],0,8_000_000),'qualified_batch')
    expected=core._aggregate(q['rows'],q['batches']) if n==65 else core._aggregate(q['rows'],q['batches'],plan)
    need(same(q['aggregate'],expected),'aggregate')
    identifiers=[]
    for e in q['records']:
        need(type(e) is dict and core._int(e.get('batch'),0,b-1) and core._int(e.get('ordinal'),0,32767),'record_schema')
        identifiers.append((e['batch'],e['ordinal']))
    need(len(set(identifiers))==len(identifiers),'record_duplicate')


def replay_batch(core,plan,q,bodies,decode,bi,counts,namespace,begin):
    deadline(begin);need(q['batches'][bi]['status']=='decoded','common_batch')
    raw=bodies[bi];ledger=core.scanner.scan(raw)
    entries=[e for e in q['records'] if e['batch']==bi]
    need(ledger['disposition']=='supported' and len(entries)==ledger['record_count']
         and q['batches'][bi]['record_count']==ledger['record_count'] and q['batches'][bi]['advertised_samples']==ledger['advertised_samples'],'record_ledger')
    charged=0;result={}
    def charge(n):
        nonlocal charged
        need(core._int(n,0,2**63-1),'observed_accounting');charged+=n;counts[namespace]+=n
        need(charged<=8_000_000 and counts[namespace]<=(136_000_000 if namespace=='old' else 104_000_000)
             and counts['old']+counts['new']<=240_000_000,'observed_cap')
    for e,d in zip(entries,ledger['records']):
        deadline(begin);start,rate,period=core.header_grid(d)
        route=[i for i in plan['batches'][bi].get('requested_rows',plan['batches'][bi]['rows'])
               if d['nslc'][:3]==[plan['rows'][i][k] for k in ('network','station','location')] and d['nslc'][3][:2]==plan['rows'][i]['prefix']]
        expected=dict(batch=bi,ordinal=d['ordinal'],offset=d['offset'],length=d['length'],nslc=d['nslc'],encoding=d['encoding'],word_order=d['word_order'],
                      start_ns=start,rate=core.pair(rate),period=core.pair(period),advertised_samples=d['npts'],routed_rows=route)
        need(all(k in e and same(e[k],v) for k,v in expected.items()),'record_binding')
        rbytes=raw[d['offset']:d['offset']+d['length']];need(hashlib.sha256(rbytes).hexdigest()==e['raw_sha256'],'raw_hash')
        if d['npts']:
            try:out=decode(rbytes,d)
            except ValueError as failure:
                if hasattr(failure,'observed_samples'):charge(failure.observed_samples)
                raise ValueError('decode_failure') from None
            need(type(out) is dict and 'values' in out,'decoder_schema')
            values=out['values']
            if type(values) is np.ndarray:charge(int(values.size))
            elif type(values) is list:charge(len(values))
            else:raise ValueError('observed_accounting')
            dtype={1:'i4',3:'i4',4:'f4',5:'f8',10:'i4',11:'i4'}[d['encoding']]
            need(core._keys(out,('start_ns','rate','dtype','values')) and type(out['start_ns']) is int and out['start_ns']==start
                 and type(out['rate']) is float and math.isfinite(out['rate']) and out['rate']>0
                 and abs(Fraction.from_float(out['rate'])-rate)<=max(Fraction(1,10**12),rate/10**12)
                 and out['dtype']==dtype and len(values)==d['npts'] and same(e['observed_samples'],len(values))
                 and same(e['decoded_start_ns'],start) and e['dtype']==dtype,'decoder_binding')
            need(core.sample_hash(values,dtype)==e['samples_sha256'],'sample_hash');values=np.asarray(values,dtype=np.dtype('<'+dtype))
        else:
            dtype='empty';values=np.empty(0,dtype=np.int32)
            need(e['samples_sha256']==hashlib.sha256(b'empty\0').hexdigest() and same(e['observed_samples'],0),'empty_record')
        result[d['ordinal']]=(e,values)
    need(charged==q['batches'][bi]['observed_samples'],'observed_binding')
    return result


def components(core,row,qrow,records):
    codes=core.channels(row);need(len(codes)==3,'common_family')
    result=[]
    for h,cell in zip((1,3,5),qrow['cells']):
        need(cell['joint']['status']=='complete' and cell['pick_before_cutoff'] is True,'common_qualification')
        by={c['channel']:c for c in cell['components']}
        need(len(by)==len(cell['components']) and all(c in by for c in codes),'component_membership')
        chosen=[by[c] for c in codes];grid={(tuple(c['first']),tuple(c['rate']),c['count']) for c in chosen}
        need(len(grid)==1,'exact_joint_grid')
        for c in chosen:
            rebuilt=[]
            for ordinal,(e,values) in records.items():
                if e['nslc']==[row[k] for k in ('network','station','location')]+[c['channel']]:
                    piece=core._piece(ordinal,values,e['dtype'],e['start_ns'],Fraction(*e['period']),row['t0_ns']-3*10**9,row['t0_ns']+h*10**9)
                    if piece is not None:rebuilt.append(piece)
            rebuilt.sort(key=lambda p:(Fraction(*p['first']),Fraction(*p['last']),p['record']))
            need(same(rebuilt,c['pieces']),'piece_replay')
            digest=hashlib.sha256(canonical([{k:p[k] for k in PIECE_KEYS} for p in rebuilt])).hexdigest()
            need(digest==c['view_sha256'],'view_hash')
            need(same(c,core._component(c['channel'],rebuilt,row,h,{'status':'decoded'},set(codes))),'component_replay')
        need(same(cell['joint'],core._joint(row,chosen)),'joint_replay')
    for code in codes:
        pieces=[]
        for _,(e,values) in sorted(records.items(),key=lambda item:(item[1][0]['start_ns'],item[0])):
            if e['nslc']==[row[k] for k in ('network','station','location')]+[code] and len(values):
                start=e['start_ns'];period=Fraction(*e['period']);end=start+len(values)*period
                if end>row['t0_ns']-3*10**9 and start<row['t0_ns']+5*10**9:
                    # Full native record pieces; values inspected only inside current windows.
                    pieces.append({'start_ns':start,'rational_period':e['period'],'values':[int(v) if e['dtype']=='i4' else float(v) for v in values]})
        result.append({'name':code,'pieces':pieces})
    return result


def normalize(centered):
    a=np.asarray(centered,dtype=np.float64)
    need(a.ndim==2 and a.shape[0]==3 and a.shape[1]>0 and np.isfinite(a).all(),'wave')
    scale=max(1.,float(np.max(np.abs(a))));unit=a/scale
    amplitude=np.asarray([math.log10(scale),*[math.log10(max(float(x)*scale,1e-12)) for x in np.sqrt(np.mean(unit*unit,axis=1))]],dtype=np.float32)
    return np.ascontiguousarray(unit,dtype=np.float32),amplitude


def event_observations(native,row,meta):
    prepared=am._piece_geometry(native,row['family']);t0,p=row['t0_ns'],row['pick_ns']
    need(t0<=p and p+am.QUARTER<=t0+am.SECOND,'common_clock')
    centers,powers,floors=am._noise(prepared,t0)
    rate=Fraction(10**9)/Fraction(*native[0]['pieces'][0]['rational_period'])
    noise=np.asarray([*[math.log10(x) for x in powers],*[float(x) for x in floors]],dtype=np.float64)
    initial_values=[[v-center for v in am._window_values(pieces,p,p+am.QUARTER)] for pieces,center in zip(prepared,centers)]
    wave,amp=normalize(initial_values)
    raw_context=context(row,meta,.25,rate)
    first_ratio=max(am._mean(pieces,p,p+am.QUARTER,center,True)/power for pieces,center,power in zip(prepared,centers,powers))
    b1=float(first_ratio>9.)
    initial_ctx=np.concatenate((noise,[b1],raw_context[1:])) # No current horizon/age coordinates.
    initial=dict(wave=wave,amplitude=amp,context=initial_ctx)
    horizons=[]
    for h in (1,3,5):
        current=[[v-center for v in am._window_values(pieces,t0-3*am.SECOND,t0+h*am.SECOND)] for pieces,center in zip(prepared,centers)]
        wave,amp=normalize(current)
        n=(t0+h*am.SECOND-p)//am.QUARTER
        ratios=[max(am._mean(pieces,p+j*am.QUARTER,p+(j+1)*am.QUARTER,center,True)/power
                    for pieces,center,power in zip(prepared,centers,powers)) for j in range(n)]
        states,ages,_,_=am._sequence(ratios)
        horizons.append(dict(seconds=h,rate=[rate.numerator,rate.denominator],wave=wave,amplitude=amp,context=np.concatenate((noise,[b1],context(row,meta,h,rate))),
                             ratios=ratios,states=states,run_ages=ages))
    return initial,horizons


def build(old_plan_bytes,old_qualified_bytes,old_bodies,new_plan_bytes,new_qualified_bytes,new_bodies,metadata_bytes,roster_bytes,decode_record,*,pins,processing_begin):
    deadline(processing_begin)
    inputs=dict(old_plan=old_plan_bytes,old_qualified=old_qualified_bytes,new_plan=new_plan_bytes,new_qualified=new_qualified_bytes,metadata=metadata_bytes,roster=roster_bytes)
    limits=dict(old_plan=131072,new_plan=131072,old_qualified=64*1024*1024,new_qualified=64*1024*1024,metadata=131072,roster=131072)
    need(new_native._keys(pins,inputs),'pins')
    for k,raw in inputs.items():
        pin=pins[k];need(type(raw) is bytes and len(raw)<=limits[k] and new_native._keys(pin,('bytes','sha256'))
                        and new_native._int(pin['bytes'],0,limits[k]) and len(raw)==pin['bytes']
                        and new_native._sha(pin['sha256']) and hashlib.sha256(raw).hexdigest()==pin['sha256'],'input_pin')
    old_plan,old_q,new_plan,new_q,metadata,roster=(json_load(inputs[k],limits[k]) for k in ('old_plan','old_qualified','new_plan','new_qualified','metadata','roster'))
    qualified_validate(old_native,old_plan,old_q,old_bodies,65,17);qualified_validate(new_native,new_plan,new_q,new_bodies,50,13)
    metadata_validate(metadata,(old_plan,new_plan),roster);need(callable(decode_record),'decoder')
    counts={'old':0,'new':0};rows=[];elements=0;array_bytes=0
    for core,plan,q,bodies,offset,namespace in [(old_native,old_plan,old_q,old_bodies,0,'old'),(new_native,new_plan,new_q,new_bodies,65,'new')]:
        cached=None;records={}
        for row,qrow in zip(plan['rows'],q['rows']):
            deadline(processing_begin);ordinal=offset+row['ordinal'];meta=metadata[ordinal];common=roster['rows'][ordinal]['common']
            output=dict(ordinal=ordinal,partition=meta['partition'],mw=float(meta['mw']),group=meta['group'],common=common,
                        status='available' if common else 'unavailable',initial=None,horizons=[dict(seconds=h,status='unavailable') for h in (1,3,5)])
            if common:
                if cached!=row['batch']:
                    records.clear();records=replay_batch(core,plan,q,bodies,decode_record,row['batch'],counts,namespace,processing_begin);cached=row['batch']
                native=components(core,row,qrow,records)
                initial,horizons=event_observations(native,row,meta);del native
                output['initial']=initial;output['horizons']=horizons
                for item in [initial]+horizons:
                    elements+=item['wave'].size;array_bytes+=sum(item[k].nbytes for k in ('wave','amplitude','context'))
                need(elements<=MAX_ELEMENTS and array_bytes<=MAX_BYTES,'observation_output_cap')
            rows.append(output)
        records.clear()
    deadline(processing_begin)
    return dict(schema=SCHEMA,study=STUDY,rows=rows,denominators=dict(events=115,cells=345,train=91,dev=24,test_excluded=31),
                observed_samples=counts,input_pins=pins,fit_authorized=False)

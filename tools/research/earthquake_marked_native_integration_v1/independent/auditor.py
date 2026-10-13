"""Independent native observation semantics. No candidate import or file IO."""
from fractions import Fraction
import hashlib
import json
import math
import statistics
import time
import numpy as np
import old_native
import new_native
from decode_contract import ObservedDecodeFailure

STUDY='earthquake-TRAIN115-receiver-renewal-v2'
SCHEMA='earthquake-TRAIN115-receiver-observations-v2'
MAX_ELEMENTS=20_000_000
MAX_PAYLOAD=128*1024*1024
MAX_SECONDS=300
META_KEYS=('ordinal','partition','mw','group','operational_eligible','station_latitude','station_longitude','station_elevation','sensitivities','units')
PIN_CAPS={'old_plan':131072,'old_qualified':64*1024*1024,'new_plan':131072,'new_qualified':64*1024*1024,'metadata':131072,'roster':131072}

def keys(v,k):return type(v) is dict and all(type(x) is str for x in v) and set(v)==set(k)
def integer(v,a,b):return type(v) is int and a<=v<=b

def finite(v):
    try:return type(v) in (int,float) and math.isfinite(v)
    except OverflowError:return False

def deadline(begin):
    if not finite(begin) or begin<0:raise ValueError('processing_begin')
    now=time.monotonic()
    if now<begin or now-begin>MAX_SECONDS:raise RuntimeError('audit_deadline')

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def parse(raw,cap):
    if type(raw) is not bytes or len(raw)>cap:raise ValueError('json_cap')
    def obj(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('duplicate_key')
            result[k]=v
        return result
    def num(s):
        if len(s.lstrip('-'))>1024:raise ValueError('integer_cap')
        return int(s)
    value=json.loads(raw.decode('utf8'),object_pairs_hook=obj,parse_int=num,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite_json')))
    pending=[(value,0)];nodes=0
    while pending:
        v,d=pending.pop();nodes+=1
        if d>32 or nodes>2_000_000:raise ValueError('json_structure_cap')
        if type(v) is dict:pending.extend((x,d+1) for x in v.values())
        elif type(v) is list:pending.extend((x,d+1) for x in v)
        elif type(v) is float and not math.isfinite(v):raise ValueError('nonfinite_json')
    return value

def custody(raws,pins):
    if not keys(pins,PIN_CAPS):raise ValueError('pin_schema')
    for name,cap in PIN_CAPS.items():
        raw=raws[name];p=pins[name]
        if (type(raw) is not bytes or len(raw)>cap or not keys(p,('bytes','sha256'))
                or not integer(p['bytes'],0,cap) or not new_native._sha(p['sha256']) or pin(raw)!=p):raise ValueError('pin_binding')

def roles(meta,roster,plans):
    if type(meta) is not list or len(meta)!=115:raise ValueError('metadata_schema')
    if (not keys(roster,('schema','study','rows')) or roster['schema']!='receiver-renewal-roster-v1'
            or roster['study']!=STUDY or type(roster['rows']) is not list or len(roster['rows'])!=115):raise ValueError('roster_schema')
    counts={'TRAIN':0,'DEV':0};common={'TRAIN':0,'DEV':0};members={}
    for i,(m,r) in enumerate(zip(meta,roster['rows'])):
        part=plans[0]['rows'][i]['partition'] if i<65 else 'TRAIN'
        if (not keys(m,META_KEYS) or not integer(m['ordinal'],i,i) or type(m['partition']) is not str or m['partition']!=part
                or not finite(m['mw']) or not -5<=m['mw']<=15 or not integer(m['group'],-1,i)
                or type(m['operational_eligible']) is not bool or m['group']==-1 and m['operational_eligible']
                or type(m['sensitivities']) is not list or len(m['sensitivities'])!=3
                or type(m['units']) is not list or len(m['units'])!=3):raise ValueError('metadata_schema')
        if any(v is not None and not finite(v) for v in [m[k] for k in META_KEYS[5:8]]+m['sensitivities']):raise ValueError('metadata_scalar')
        if any(v is not None and (type(v) is not str or len(v)>128) for v in m['units']):raise ValueError('metadata_units')
        if not keys(r,('ordinal','common')) or not integer(r['ordinal'],i,i) or type(r['common']) is not bool:raise ValueError('roster_row')
        if r['common'] and (m['group']<0 or not m['operational_eligible']):raise ValueError('common_ineligible')
        counts[part]+=1;common[part]+=int(r['common'])
        if m['group']>=0:members.setdefault(m['group'],set()).add(part)
    if counts!={'TRAIN':91,'DEV':24} or common!={'TRAIN':65,'DEV':22}:raise ValueError('fixed_denominator')
    mixed={g for g,parts in members.items() if len(parts)>1}
    if any(m['group'] in mixed and m['operational_eligible'] for m in meta):raise ValueError('mixed_group_eligible')
    return [r['common'] for r in roster['rows']]

def array(a,dtype,shape):
    if type(a) is not np.ndarray or a.dtype.str!=dtype or not a.flags.c_contiguous or a.shape!=shape or not np.isfinite(a).all():raise ValueError('array_schema')

def packet_schema(packet,meta,common,pins):
    if (not keys(packet,('schema','study','rows','denominators','observed_samples','input_pins','fit_authorized'))
            or packet['schema']!=SCHEMA or packet['study']!=STUDY or packet['fit_authorized'] is not False
            or not keys(packet['denominators'],('events','cells','train','dev','test_excluded'))
            or any(type(v) is not int for v in packet['denominators'].values())
            or packet['denominators']!=dict(events=115,cells=345,train=91,dev=24,test_excluded=31)
            or not keys(packet['observed_samples'],('old','new'))
            or not integer(packet['observed_samples']['old'],0,136_000_000) or not integer(packet['observed_samples']['new'],0,104_000_000)
            or sum(packet['observed_samples'].values())>240_000_000 or packet['input_pins']!=pins
            or type(packet['rows']) is not list or len(packet['rows'])!=115):raise ValueError('packet_schema')
    # Pin equality alone is insufficient: bool/int aliases must not masquerade as custody.
    if not keys(packet['input_pins'],PIN_CAPS) or any(not keys(p,('bytes','sha256')) or type(p['bytes']) is not int or type(p['sha256']) is not str for p in packet['input_pins'].values()):raise ValueError('packet_pins')
    elements=payload=arrays=0
    for i,r in enumerate(packet['rows']):
        m=meta[i]
        if (not keys(r,('ordinal','partition','mw','group','common','status','initial','horizons')) or not integer(r['ordinal'],i,i)
                or type(r['partition']) is not str or r['partition']!=m['partition'] or not finite(r['mw']) or r['mw']!=m['mw']
                or not integer(r['group'],-1,i) or r['group']!=m['group'] or type(r['common']) is not bool or r['common']!=common[i]
                or type(r['horizons']) is not list or len(r['horizons'])!=3):raise ValueError('packet_row')
        if not common[i]:
            if r['status']!='unavailable' or r['initial'] is not None:raise ValueError('noncommon_packet')
            for h,c in zip((1,3,5),r['horizons']):
                if not keys(c,('seconds','status')) or not integer(c['seconds'],h,h) or c['status']!='unavailable':raise ValueError('noncommon_packet')
            continue
        if r['status']!='available' or not keys(r['initial'],('wave','amplitude','context')):raise ValueError('common_packet')
        observations=[(r['initial'],35)]
        previous=None
        for h,c in zip((1,3,5),r['horizons']):
            if (not keys(c,('seconds','rate','wave','amplitude','context','ratios','states','run_ages'))
                    or not integer(c['seconds'],h,h)):raise ValueError('horizon_schema')
            new_native._rational(c['rate'])
            n=len(c['ratios']) if type(c['ratios']) is list else -1
            if (not 4*h-3<=n<=4*h or type(c['states']) is not list or type(c['run_ages']) is not list
                    or len(c['states'])!=n or len(c['run_ages'])!=n
                    or any(not finite(x) or not 0<=x<=1e25 for x in c['ratios'])):raise ValueError('activity_schema')
            state=None;age=0
            for ratio,s,a in zip(c['ratios'],c['states'],c['run_ages']):
                age=age+1 if s==state else 1
                if not integer(s,0,1) or s!=int(ratio>9) or not integer(a,1,20) or a!=age:raise ValueError('activity_schema')
                state=s
            if previous is not None and (n!=len(previous['ratios'])+8 or any(c[k][:len(previous[k])]!=previous[k] for k in ('ratios','states','run_ages'))):raise ValueError('activity_prefix')
            previous=c;observations.append((c,36))
        for c,ncontext in observations:
            w=c['wave']
            if type(w) is not np.ndarray or w.ndim!=2 or w.shape[0]!=3 or not 1<=w.shape[1]<=MAX_ELEMENTS//3:raise ValueError('wave_schema')
            elements+=w.size;payload+=w.nbytes+4*4+ncontext*8;arrays+=3
            if elements>MAX_ELEMENTS or payload>MAX_PAYLOAD or arrays>1380:raise ValueError('packet_payload_cap')
            array(w,'<f4',w.shape);array(c['amplitude'],'<f4',(4,));array(c['context'],'<f8',(ncontext,))
    return elements,payload

def qualification(plan,q,bodies,core,nrows,nbatches):
    core.validate(plan,bodies)
    schema='geonet-POST-prefix-qualification-v2' if nrows==65 else 'geonet-TRAIN50-prefix-qualification-v1'
    if (not keys(q,('schema','study','disposition','reason','batches','records','rows','aggregate','claims'))
            or q['schema']!=schema or q['study']!=core.STUDY or q['disposition']!='complete' or q['reason']!='supported'
            or type(q['rows']) is not list or len(q['rows'])!=nrows or type(q['batches']) is not list or len(q['batches'])!=nbatches
            or type(q['records']) is not list or len(q['records'])>32768*nbatches
            or not keys(q['claims'],core._CLAIMS) or any(v is not False for v in q['claims'].values())):raise ValueError('qualification_schema')
    for i,r in enumerate(q['rows']):
        fields=('ordinal','partition','batch','family','cells') if nrows==65 else ('ordinal','global_ordinal','partition','batch','family','cells')
        if (not keys(r,fields) or any(type(r[k]) is not type(plan['rows'][i][k]) or r[k]!=plan['rows'][i][k] for k in fields if k!='cells')
                or type(r['cells']) is not list or len(r['cells'])!=3):raise ValueError('qualification_row')
    for i,b in enumerate(q['batches']):
        if (not keys(b,('ordinal','status','reason','record_count','advertised_samples','observed_samples')) or not integer(b['ordinal'],i,i)
                or type(b['status']) is not str or b['status'] not in ('decoded','unknown','nonpositive') or type(b['reason']) is not str
                or not integer(b['record_count'],0,32768) or not integer(b['advertised_samples'],0,8_000_000)
                or not integer(b['observed_samples'],0,8_000_000)):raise ValueError('qualification_batch')
    if any(sum(b[k] for b in q['batches'])>core.MAX_TOTAL_SAMPLES for k in ('advertised_samples','observed_samples')):raise ValueError('qualification_counts')

def decode_batch(plan,q,bodies,core,bi,decode,counts,begin):
    deadline(begin)
    if q['batches'][bi]['status']!='decoded':raise ValueError('needed_batch_not_decoded')
    body=bodies[bi];ledger=core.scanner.scan(body)
    entries=[r for r in q['records'] if type(r) is dict and r.get('batch')==bi]
    if (ledger['disposition']!='supported' or len(entries)!=ledger['record_count']
            or q['batches'][bi]['record_count']!=ledger['record_count']
            or q['batches'][bi]['advertised_samples']!=ledger['advertised_samples']):raise ValueError('record_ledger')
    values={};charged=0
    def charge(n):
        nonlocal charged
        if not integer(n,0,2**63-1):raise ValueError('observed_accounting')
        charged+=n;counts[0]+=n
        if charged>8_000_000 or counts[0]>core.MAX_TOTAL_SAMPLES:raise RuntimeError('observed_sample_cap')
    for e,d in zip(entries,ledger['records']):
        deadline(begin)
        recordkeys=('batch','ordinal','offset','length','nslc','encoding','word_order','raw_sha256','start_ns','rate','period','advertised_samples','observed_samples','decoded_start_ns','dtype','samples_sha256','finite','routed_rows')
        if (not keys(e,recordkeys) or any(not integer(e[k],d[k],d[k]) for k in ('ordinal','offset','length')) or not integer(e['batch'],bi,bi)):raise ValueError('record_schema')
        start,rate,period=core.header_grid(d);raw=body[d['offset']:d['offset']+d['length']]
        core._rational(e['rate']);core._rational(e['period'])
        requested=plan['batches'][bi].get('requested_rows',plan['batches'][bi]['rows'])
        routed=[j for j in requested if d['nslc'][:3]==[plan['rows'][j][k] for k in ('network','station','location')] and d['nslc'][3][:2]==plan['rows'][j]['prefix']]
        if (e['nslc']!=d['nslc'] or not integer(e['encoding'],d['encoding'],d['encoding']) or not integer(e['word_order'],d['word_order'],d['word_order'])
                or not integer(e['start_ns'],start,start) or e['rate']!=core.pair(rate) or e['period']!=core.pair(period)
                or not integer(e['advertised_samples'],d['npts'],d['npts']) or not integer(e['observed_samples'],0,8_000_000)
                or e['raw_sha256']!=hashlib.sha256(raw).hexdigest() or type(e['routed_rows']) is not list
                or any(type(x) is not int for x in e['routed_rows']) or e['routed_rows']!=routed or not routed):raise ValueError('record_binding')
        if d['npts']:
            try:out=decode(raw,d)
            except ObservedDecodeFailure as failure:
                charge(failure.observed_samples);raise ValueError('record_decode_failure') from None
            # Any delivered array/list is charged before schema/clock/rate/shape veto.
            if type(out) is dict and 'values' in out:
                a=out['values']
                if isinstance(a,np.ndarray):charge(int(np.ndarray.size.__get__(a)))
                elif type(a) is list:charge(len(a))
                else:raise ValueError('observed_accounting')
            else:raise ValueError('record_decode_schema')
            dtype={1:'i4',3:'i4',4:'f4',5:'f8',10:'i4',11:'i4'}[d['encoding']]
            if (not keys(out,('start_ns','rate','dtype','values')) or not integer(out['start_ns'],start,start)
                    or not integer(e['decoded_start_ns'],start,start) or type(out['rate']) is not float or not math.isfinite(out['rate']) or out['rate']<=0
                    or abs(Fraction.from_float(out['rate'])-rate)>max(Fraction(1,10**12),rate/10**12)
                    or type(out['dtype']) is not str or out['dtype']!=dtype or e['dtype']!=dtype
                    or e['observed_samples']!=d['npts'] or (type(a) is not list and type(a) is not np.ndarray) or (type(a) is np.ndarray and a.ndim!=1) or len(a)!=d['npts']
                    or core.sample_hash(a,dtype)!=e['samples_sha256']):raise ValueError('record_replay')
            a=np.asarray(a,dtype='<'+dtype)
        else:
            a=np.empty(0,dtype=np.int32)
            if (e['dtype']!='empty' or e['decoded_start_ns'] is not None or e['observed_samples']!=0
                    or e['samples_sha256']!=hashlib.sha256(b'empty\0').hexdigest()):raise ValueError('empty_record')
        if e['finite'] is not True or not np.isfinite(a).all():raise ValueError('record_nonfinite')
        if e['ordinal'] in values:raise ValueError('duplicate_record')
        values[e['ordinal']]=(e,a)
    if charged!=q['batches'][bi]['observed_samples']:raise ValueError('observed_binding')
    deadline(begin);return values

def ceil(v):return -((-v.numerator)//v.denominator)

def native_view(row,cell,h,records,core,begin):
    channels=core.channels(row)
    cutoff=row['t0_ns']+h*10**9
    if (not keys(cell,('horizon','cutoff_ns','pick_before_cutoff','components','joint')) or not integer(cell['horizon'],h,h)
            or not integer(cell['cutoff_ns'],cutoff,cutoff) or cell['pick_before_cutoff'] is not True
            or row['pick_ns']>=cutoff or type(cell['components']) is not list or len(channels)!=3
            or not keys(cell['joint'],('status','reason','rate','channels')) or cell['joint']['status']!='complete'
            or cell['joint']['channels']!=channels):raise ValueError('common_cell')
    comps={c['channel']:c for c in cell['components'] if type(c) is dict and 'channel' in c}
    if len(comps)!=len(cell['components']) or any(c not in comps for c in channels):raise ValueError('component_set')
    assembled=[];grid=None
    for ch in channels:
        c=comps[ch]
        if c['status']!='complete' or c['finite'] is not True or not integer(c['count'],1,MAX_ELEMENTS//3) or type(c['pieces']) is not list or not 1<=len(c['pieces'])<=32768:raise ValueError('component_status')
        rate=core._rational(c['rate'])
        if type(c['first']) is not list or len(c['first'])!=2 or any(type(x) is not int for x in c['first']) or c['first'][1]<=0 or math.gcd(*c['first'])!=1:raise ValueError('component_first')
        first=Fraction(*c['first']);period=Fraction(10**9)/rate
        if grid is None:grid=(first,rate,c['count'])
        elif grid!=(first,rate,c['count']):raise ValueError('component_grid')
        pos=0;chunks=[];composition=[]
        for piece in c['pieces']:
            deadline(begin)
            if type(piece) is not dict or not integer(piece.get('record'),0,32767) or piece['record'] not in records:raise ValueError('piece_record')
            e,a=records[piece['record']];ep=core._rational(e['period']);start=e['start_ns']
            lo=max(0,ceil((Fraction(row['t0_ns']-3*10**9)-start)/ep));hi=min(len(a),ceil((Fraction(cutoff)-start)/ep))
            digest=core.sample_hash(a[lo:hi],e['dtype'])
            if (hi<=lo or e['nslc']!=[row[k] for k in ('network','station','location')]+[ch]
                    or not integer(piece.get('lo'),lo,lo) or not integer(piece.get('hi'),hi,hi) or not integer(piece.get('count'),hi-lo,hi-lo)
                    or piece.get('first')!=core.pair(Fraction(start)+lo*ep) or piece.get('last')!=core.pair(Fraction(start)+(hi-1)*ep)
                    or piece.get('period')!=e['period'] or piece.get('dtype')!=e['dtype'] or piece.get('samples_sha256')!=digest
                    or ep!=period or Fraction(*piece['first'])!=first+pos*period):raise ValueError('piece_binding')
            composition.append({k:piece[k] for k in ('record','lo','hi','count','first','last','period','dtype','samples_sha256')})
            chunks.append(a[lo:hi]);pos+=hi-lo
        if (pos!=c['count'] or c['last']!=core.pair(first+(pos-1)*period)
                or c['view_sha256']!=hashlib.sha256(core.canonical(composition)).hexdigest()
                or not Fraction(row['t0_ns']-3*10**9)<=first<Fraction(row['t0_ns']-3*10**9)+period
                or not cutoff-period<=first+(pos-1)*period<cutoff):raise ValueError('view_binding')
        assembled.append(np.concatenate(chunks))
    if cell['joint']['rate']!=core.pair(grid[1]):raise ValueError('joint_rate')
    return assembled,grid[0],Fraction(10**9)/grid[1]

def indices(first,period,n,left,right):
    lo=max(0,ceil((Fraction(left)-first)/period));hi=min(n,ceil((Fraction(right)-first)/period))
    if hi<=lo:raise ValueError('empty_window')
    return lo,hi

def static(row,m,rate):
    out=[math.log10(float(rate))];coords=[];missing=[]
    for k,lo,hi in (('station_latitude',-90,90),('station_longitude',-180,180),('station_elevation',-10000,10000)):
        v=m[k];ok=finite(v) and lo<=v<=hi;coords.append(float(v) if ok else 0.);missing.append(float(not ok))
    out+=coords+missing+[float(row['family']=='ENZ'),float(row['family']=='12Z')]
    gains=[];missing=[]
    for v in m['sensitivities']:
        ok=finite(v) and v>0;gains.append(math.log10(v) if ok else 0.);missing.append(float(not ok))
    out+=gains+missing
    for unit in m['units']:
        category={'M/S':0,'M/S**2':1,'M':2}.get(unit,3) if type(unit) is str else 3
        out.extend(float(k==category) for k in range(4))
    if len(out)!=27 or not all(math.isfinite(v) for v in out):raise ValueError('static_context')
    return out

def normalized(centered):
    a=np.asarray(centered,dtype=np.float64)
    if a.ndim!=2 or a.shape[0]!=3 or a.shape[1]<1 or not np.isfinite(a).all():raise ValueError('centered_values')
    scale=max(1.,float(np.max(np.abs(a))));unit=a/scale
    rms=np.sqrt(np.mean(unit*unit,axis=1))
    amp=np.asarray([math.log10(scale)]+[math.log10(max(float(x)*scale,1e-12)) for x in rms],dtype=np.float32)
    wave=np.ascontiguousarray(unit,dtype=np.float32)
    if not np.isfinite(amp).all() or not np.isfinite(wave).all():raise ValueError('normalized_nonfinite')
    return wave,amp

def semantics(row,native,first,period,meta,begin):
    """New independent feature mathematics, scalar fsum and exact integer clocks."""
    n=len(native[0]);t0=row['t0_ns'];p=row['pick_ns'];delta=(p-t0)/1e9
    if not 0<=delta<=.75:raise ValueError('local_age')
    noise=[];flags=[];centers=[]
    def samples(c,left,right):
        lo,hi=indices(first,period,n,left,right)
        return (float(native[c][k]) for k in range(lo,hi))
    def power(c,left,right):
        lo,hi=indices(first,period,n,left,right)
        residuals=(float(native[c][k])-centers[c] for k in range(lo,hi))
        result=math.fsum(v*v for v in residuals)/(hi-lo)
        if not math.isfinite(result):raise ValueError('power_nonfinite')
        return result
    for c in range(3):
        lo,hi=indices(first,period,n,t0-3*10**9,t0)
        center=math.fsum(samples(c,t0-3*10**9,t0))/(hi-lo)
        if not math.isfinite(center):raise ValueError('center_nonfinite')
        centers.append(center)
        raw=statistics.median(power(c,t0-3*10**9+k*250_000_000,t0-3*10**9+(k+1)*250_000_000) for k in range(12))
        noise.append(max(1.,raw));flags.append(float(raw<1.))
    rates=Fraction(10**9)/period;shared=static(row,meta,rates)
    noise_ctx=[math.log10(x) for x in noise]+flags
    def observation(left,right):
        lo,hi=indices(first,period,n,left,right)
        return normalized([[float(native[c][k])-centers[c] for k in range(lo,hi)] for c in range(3)])
    initial_wave,initial_amp=observation(p,p+250_000_000)
    ratios=[];states=[];ages=[];horizons=[]
    for h in (1,3,5):
        deadline(begin)
        j=(t0+h*10**9-p)//250_000_000
        if not 4*h-3<=j<=4*h:raise ValueError('cell_count')
        for k in range(len(ratios),j):
            ratio=max(power(c,p+k*250_000_000,p+(k+1)*250_000_000)/noise[c] for c in range(3))
            if not math.isfinite(ratio) or not 0<=ratio<=1e25:raise ValueError('ratio_nonfinite')
            s=int(ratio>9);ages.append(ages[-1]+1 if states and states[-1]==s else 1);states.append(s);ratios.append(ratio)
        wave,amp=observation(t0-3*10**9,t0+h*10**9)
        ctx=np.asarray(noise_ctx+[float(states[0]),float(h),delta]+shared,dtype=np.float64)
        horizons.append(dict(seconds=h,rate=new_native.pair(rates),wave=wave,amplitude=amp,context=ctx,ratios=list(ratios),states=list(states),run_ages=list(ages)))
    initial=dict(wave=initial_wave,amplitude=initial_amp,context=np.asarray(noise_ctx+[float(states[0]),delta]+shared,dtype=np.float64))
    return initial,horizons

def same_observation(actual,expected):
    for k in ('wave','amplitude','context'):
        a,b=actual[k],expected[k]
        if a.dtype.str!=b.dtype.str or a.shape!=b.shape or a.tobytes(order='C')!=b.tobytes(order='C'):raise ValueError('semantic_array_mismatch')
    for k in ('seconds','rate','states','run_ages'):
        if k in expected and actual[k]!=expected[k]:raise ValueError('semantic_scalar_mismatch')
    if 'ratios' in expected:
        # binary64 byte equality, including signed zero, survives ordinary int/float values.
        if np.asarray(actual['ratios'],dtype='<f8').tobytes()!=np.asarray(expected['ratios'],dtype='<f8').tobytes():raise ValueError('semantic_ratio_mismatch')

def audit(old_plan_bytes,old_qualified_bytes,old_bodies,new_plan_bytes,new_qualified_bytes,new_bodies,metadata_bytes,roster_bytes,packet,decode_record,*,input_pins,processing_begin):
    deadline(processing_begin)
    raws=dict(old_plan=old_plan_bytes,old_qualified=old_qualified_bytes,new_plan=new_plan_bytes,new_qualified=new_qualified_bytes,metadata=metadata_bytes,roster=roster_bytes)
    custody(raws,input_pins);deadline(processing_begin)
    data={k:parse(v,PIN_CAPS[k]) for k,v in raws.items()};plans=[data['old_plan'],data['new_plan']];qs=[data['old_qualified'],data['new_qualified']]
    qualification(plans[0],qs[0],old_bodies,old_native,65,17);qualification(plans[1],qs[1],new_bodies,new_native,50,13)
    meta=data['metadata'];common=roles(meta,data['roster'],plans);elements,payload=packet_schema(packet,meta,common,input_pins);deadline(processing_begin)
    observed={};checked=0
    for offset,plan,q,bodies,core,namespace in ((0,plans[0],qs[0],old_bodies,old_native,'old'),(65,plans[1],qs[1],new_bodies,new_native,'new')):
        counts=[0]
        for bi in range(len(plan['batches'])):
            rows=[i for i,r in enumerate(plan['rows']) if r['batch']==bi and common[offset+i]]
            if not rows:continue
            records=decode_batch(plan,q,bodies,core,bi,decode_record,counts,processing_begin)
            for i in rows:
                row=plan['rows'][i];views=[]
                for h,c in zip((1,3,5),q['rows'][i]['cells']):views.append(native_view(row,c,h,records,core,processing_begin))
                native,first,period=views[2]
                # Each original dtype hash was already authenticated. Float64 represents
                # every supported i4/f4/f8 scalar losslessly; longer-horizon dtype
                # promotion cannot alter the comparison of the native prefix.
                for short,shortfirst,shortperiod in views[:2]:
                    if shortfirst!=first or shortperiod!=period or any(np.asarray(a,dtype='<f8').tobytes()!=np.asarray(b[:len(a)],dtype='<f8').tobytes() for a,b in zip(short,native)):raise ValueError('native_prefix_mismatch')
                initial,horizons=semantics(row,native,first,period,meta[offset+i],processing_begin)
                actual=packet['rows'][offset+i];same_observation(actual['initial'],initial)
                for a,b in zip(actual['horizons'],horizons):same_observation(a,b)
                checked+=1
            records.clear();deadline(processing_begin)
        observed[namespace]=counts[0]
    if observed!=packet['observed_samples']:raise ValueError('packet_observed_mismatch')
    deadline(processing_begin)
    public=dict(schema='earthquake-TRAIN115-receiver-observation-independent-audit-v1',study=STUDY,disposition='agreed',reason='exact_native_semantics',events=115,common_train=65,common_dev=22,checked_observations=checked*4,physical_authority=False,fit_authorized=False)
    return dict(public=public,input_pins={k:dict(v) for k,v in input_pins.items()},observed_samples=observed,wave_elements=elements,numeric_payload_bytes=payload,fit_authorized=False)

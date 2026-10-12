"""Bounded old65 numeric custody plus NEW50 exact native reconstruction."""
from fractions import Fraction
import copy
import hashlib
import io
import json
import math
import re
import time
import zipfile
import numpy as np
import old_artifact as old
import new_core as qc
from new_decode_contract import ObservedDecodeFailure

STUDY='earthquake-fixed-TRAIN115-native-count-information-v1'
SCHEMA='earthquake-TRAIN115-native-count-artifact-v1'
PROPOSAL_SHA='525b803e5c66da5284faad5e431eb152d04458f78d2ab5d783c27ba6a2dc6ed9'
MAX_ELEMENTS=20_000_000
MAX_UNCOMPRESSED=80*1024*1024
MAX_ARCHIVE=128*1024*1024
META_NAMES={'amplitudes','contexts','magnitudes','groups','partitions','cohort'}
WAVE=re.compile(r'wave_(\d{3})_([135])\Z')
canonical=qc.canonical
preprocess=old.preprocess
context=old.context


def deadline(begin):
    if type(begin) not in (int,float) or not math.isfinite(begin) or begin<0:raise ValueError('processing_begin')
    now=time.monotonic()
    if now<begin or now-begin>300:raise RuntimeError('artifact_deadline')


def _finite(v):
    try:return type(v) in (int,float) and math.isfinite(v)
    except OverflowError:return False


def _json(raw,cap):
    if type(raw) is not bytes or len(raw)>cap:raise ValueError('json_cap')
    def obj(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('duplicate_key')
            out[k]=v
        return out
    def integer(s):
        if len(s.lstrip('-'))>1024:raise ValueError('integer_cap')
        return int(s)
    v=json.loads(raw.decode('utf-8'),object_pairs_hook=obj,parse_int=integer,parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite_json')))
    todo=[(v,0)];count=0
    while todo:
        item,depth=todo.pop();count+=1
        if depth>32 or count>2_000_000:raise ValueError('json_structure_cap')
        if type(item) is dict:todo.extend((x,depth+1) for x in item.values())
        elif type(item) is list:todo.extend((x,depth+1) for x in item)
        elif type(item) is float and not math.isfinite(item):raise ValueError('nonfinite_json')
    return v


def _pins(inputs,pins):
    if not qc._keys(pins,inputs):raise ValueError('custody_schema')
    limits={'old_npz':old.MAX_ARCHIVE,'old_manifest':1048576,'new_plan':131072,'new_qualified':qc.MAX_PRIVATE,'metadata':131072}
    for name,raw in inputs.items():
        p=pins[name]
        if (type(raw) is not bytes or len(raw)>limits[name] or not qc._keys(p,('bytes','sha256'))
                or not qc._int(p['bytes'],0,limits[name]) or len(raw)!=p['bytes'] or not qc._sha(p['sha256'])
                or hashlib.sha256(raw).hexdigest()!=p['sha256']):raise ValueError('custody_pin')


def metadata_validate(metadata,old_manifest,new_plan):
    keys=('ordinal','partition','mw','group','operational_eligible','station_latitude','station_longitude','station_elevation','sensitivities','units')
    if type(metadata) is not list or len(metadata)!=115:raise ValueError('metadata_schema')
    for i,m in enumerate(metadata):
        part=old_manifest['rows'][i]['partition'] if i<65 else 'TRAIN'
        if (not qc._keys(m,keys) or not qc._int(m['ordinal'],i,i) or type(m['partition']) is not str or m['partition']!=part
                or not _finite(m['mw']) or not qc._int(m['group'],-1,i) or type(m['operational_eligible']) is not bool
                or m['group']==-1 and m['operational_eligible'] or type(m['sensitivities']) is not list or len(m['sensitivities'])!=3
                or type(m['units']) is not list or len(m['units'])!=3):raise ValueError('metadata_schema')
        if i<65 and m['mw']!=old_manifest['rows'][i]['mw']:raise ValueError('old_mw_binding')
        for v in [m[k] for k in ('station_latitude','station_longitude','station_elevation')]+m['sensitivities']:
            if v is not None and not _finite(v):raise ValueError('metadata_scalar')
        if any(v is not None and (type(v) is not str or len(v)>128) for v in m['units']):raise ValueError('metadata_unit')
    shared={m['group'] for m in metadata if m['group']>=0 and len({r['partition'] for r in metadata if r['group']==m['group']})>1}
    return [m['group']>=0 and m['operational_eligible'] and m['group'] not in shared for m in metadata]


def _qualified(plan,q,bodies):
    qc.validate(plan,bodies)
    if (not qc._keys(q,('schema','study','disposition','reason','batches','records','rows','aggregate','claims'))
            or q['schema']!='geonet-TRAIN50-prefix-qualification-v1' or q['study']!=qc.STUDY
            or q['disposition']!='complete' or q['reason']!='supported'
            or type(q['rows']) is not list or len(q['rows'])!=50 or type(q['batches']) is not list or len(q['batches'])!=13
            or type(q['records']) is not list or not qc._keys(q['claims'],qc._CLAIMS) or any(v is not False for v in q['claims'].values())):raise ValueError('qualified_schema')
    for i,row in enumerate(q['rows']):
        p=plan['rows'][i]
        if (not qc._keys(row,('ordinal','global_ordinal','partition','batch','family','cells'))
                or any(type(row[k]) is not type(p[k]) or row[k]!=p[k] for k in ('ordinal','global_ordinal','partition','batch','family'))
                or type(row['cells']) is not list or len(row['cells'])!=3):raise ValueError('qualified_row')
    for i,b in enumerate(q['batches']):
        if (not qc._keys(b,('ordinal','status','reason','record_count','advertised_samples','observed_samples'))
                or not qc._int(b['ordinal'],i,i) or type(b['status']) is not str or b['status'] not in ('decoded','unknown','nonpositive')
                or type(b['reason']) is not str or not qc._int(b['record_count'],0,32768)
                or not qc._int(b['advertised_samples'],0,qc.MAX_SAMPLES) or not qc._int(b['observed_samples'],0,qc.MAX_SAMPLES)):raise ValueError('qualified_batch')
    if sum(b['advertised_samples'] for b in q['batches'])>qc.MAX_TOTAL_SAMPLES or sum(b['observed_samples'] for b in q['batches'])>qc.MAX_TOTAL_SAMPLES:raise ValueError('qualified_sample_cap')


def _reconstruct(plan,q,bodies,decode,bi,counts,begin):
    deadline(begin)
    raw=bodies[bi];entries=[e for e in q['records'] if type(e) is dict and e.get('batch')==bi]
    if q['batches'][bi]['status']!='decoded':return {}
    ledger=qc.scanner.scan(raw)
    if ledger['disposition']!='supported' or len(entries)!=ledger['record_count']:raise ValueError('record_ledger')
    if q['batches'][bi]['record_count']!=ledger['record_count'] or q['batches'][bi]['advertised_samples']!=ledger['advertised_samples']:raise ValueError('batch_ledger')
    values={};charged=0
    def charge(n):
        nonlocal charged
        if not qc._int(n,0,2**63-1):raise ValueError('observed_accounting')
        charged+=n;counts[0]+=n
        if charged>qc.MAX_SAMPLES or counts[0]>qc.MAX_TOTAL_SAMPLES:raise RuntimeError('artifact_observed_cap')
    for e,d in zip(entries,ledger['records']):
        deadline(begin)
        if (not qc._int(e.get('batch'),bi,bi) or any(type(e.get(k)) is not int or e[k]!=d[k] for k in ('ordinal','offset','length'))):raise ValueError('record_ledger')
        record=raw[d['offset']:d['offset']+d['length']];start,rate,period=qc.header_grid(d)
        if (type(e['start_ns']) is not int or type(e['advertised_samples']) is not int or type(e['observed_samples']) is not int
                or hashlib.sha256(record).hexdigest()!=e['raw_sha256'] or d['nslc']!=e['nslc'] or d['npts']!=e['advertised_samples']
                or start!=e['start_ns'] or qc.pair(rate)!=e['rate'] or qc.pair(period)!=e['period']):raise ValueError('record_binding')
        if d['npts']:
            try:out=decode(record,d)
            except ObservedDecodeFailure as failure:charge(failure.observed_samples);raise ValueError('record_decode_failure') from None
            if not qc._keys(out,('start_ns','rate','dtype','values')):raise ValueError('record_decode_schema')
            a=out['values']
            if type(a) is np.ndarray:charge(int(a.size))
            elif type(a) is list:charge(len(a))
            else:raise ValueError('observed_accounting')
            expected={1:'i4',3:'i4',4:'f4',5:'f8',10:'i4',11:'i4'}[d['encoding']]
            if (type(out['start_ns']) is not int or out['start_ns']!=start or e['decoded_start_ns']!=start
                    or type(out['rate']) is not float or not math.isfinite(out['rate']) or out['rate']<=0
                    or type(out['dtype']) is not str or out['dtype']!=expected or e['dtype']!=expected
                    or e['observed_samples']!=d['npts'] or len(a)!=d['npts']
                    or abs(Fraction.from_float(out['rate'])-rate)>max(Fraction(1,10**12),rate/10**12)
                    or qc.sample_hash(a,expected)!=e['samples_sha256']):raise ValueError('record_replay')
            a=np.asarray(a)
        else:
            a=np.empty(0,dtype=np.int32)
            if e['samples_sha256']!=hashlib.sha256(b'empty\0').hexdigest() or e['observed_samples']!=0:raise ValueError('record_replay')
        key=(bi,e['ordinal'])
        if key in values:raise ValueError('record_duplicate')
        values[key]=(e,a)
        deadline(begin)
    if charged!=q['batches'][bi]['observed_samples']:raise ValueError('batch_observed_binding')
    return values


def _cell(row,cell,h,records,meta,eligible,elements,begin):
    channels=qc.channels(row)
    cutoff=None if row['t0_ns'] is None else row['t0_ns']+h*10**9
    pick=None if not row['queryable'] else row['pick_ns']<cutoff
    if (not qc._keys(cell,('horizon','cutoff_ns','pick_before_cutoff','components','joint')) or type(cell['horizon']) is not int
            or cell['horizon']!=h or type(cell['cutoff_ns']) is not type(cutoff) or cell['cutoff_ns']!=cutoff
            or type(cell['pick_before_cutoff']) is not type(pick) or cell['pick_before_cutoff']!=pick):raise ValueError('cell_binding')
    reason='supported'
    if not row['queryable']:reason='selection_unknown'
    elif not channels:reason='metadata_unknown'
    elif not eligible:reason='operational_ineligible'
    elif cell['joint']['status']!='complete' or pick is not True:reason='qualification_unknown'
    elif h-(row['pick_ns']-row['t0_ns'])/1e9<.25:reason='local_age'
    if reason!='supported':return old._empty_cell(h,reason,channels),None,None,None
    components={c['channel']:c for c in cell['components']}
    if len(components)!=len(cell['components']) or any(c not in components for c in channels):raise ValueError('component_binding')
    selected=[components[c] for c in channels]
    for c in selected:
        if not qc._int(c['count'],1,MAX_ELEMENTS//3):raise ValueError('component_count')
        qc._rational(c['rate'])
        v=c['first']
        if type(v) is not list or len(v)!=2 or any(type(x) is not int for x in v) or v[1]<=0 or math.gcd(*v)!=1:raise ValueError('component_first')
    if len({(tuple(c['first']),tuple(c['rate']),c['count']) for c in selected})!=1 or any(c['status']!='complete' for c in selected):return old._empty_cell(h,'grid_mismatch',channels),None,None,None
    if not qc._int(selected[0]['count'],1,MAX_ELEMENTS//3) or elements+3*selected[0]['count']>MAX_ELEMENTS:raise RuntimeError('artifact_element_cap')
    try:
        native=[];hashes=[]
        for c in selected:
            chunks=[];composition=[];accumulated=0;first=Fraction(*c['first']);period=Fraction(10**9)/Fraction(*c['rate'])
            for piece in c['pieces']:
                deadline(begin)
                e,a=records[(row['batch'],piece['record'])];ep=Fraction(*e['period']);start=e['start_ns']
                if e['nslc']!=[row[k] for k in ('network','station','location')]+[c['channel']]:raise ValueError('piece_identity')
                lo=max(0,qc._ceil((Fraction(row['t0_ns']-3*10**9)-start)/ep));hi=min(len(a),qc._ceil((Fraction(row['t0_ns']+h*10**9)-start)/ep))
                if (type(piece['lo']) is not int or type(piece['hi']) is not int or lo!=piece['lo'] or hi!=piece['hi'] or hi<=lo
                        or piece['count']!=hi-lo or piece['first']!=qc.pair(Fraction(start)+lo*ep)
                        or piece['last']!=qc.pair(Fraction(start)+(hi-1)*ep) or piece['period']!=e['period'] or piece['dtype']!=e['dtype']
                        or qc.sample_hash(a[lo:hi],e['dtype'])!=piece['samples_sha256'] or ep!=period
                        or Fraction(*piece['first'])!=first+accumulated*period):raise ValueError('piece_binding')
                accumulated+=hi-lo;chunks.append(a[lo:hi]);composition.append({k:piece[k] for k in ('record','lo','hi','count','first','last','period','dtype','samples_sha256')})
            if hashlib.sha256(canonical(composition)).hexdigest()!=c['view_sha256']:raise ValueError('view_hash')
            combined=np.concatenate(chunks)
            if len(combined)!=c['count'] or not np.isfinite(combined).all():raise ValueError('view_values')
            native.append(combined);hashes.append(c['view_sha256'])
        first=Fraction(*selected[0]['first']);rate=Fraction(*selected[0]['rate']);period=Fraction(10**9)/rate
        pre=max(0,min(len(native[0]),qc._ceil((Fraction(row['t0_ns'])-first)/period)))
        if not pre:return old._empty_cell(h,'no_precontext',channels),None,None,None
        wave,amp=preprocess(np.stack(native),pre);ctx=context(row,meta,h,rate)
        c=dict(horizon=h,status='available',reason='supported',array='wave_%03d_%d'%(row['global_ordinal'],h),shape=list(wave.shape),first=qc.pair(first),period=qc.pair(period),precontext_count=pre,channels=channels,view_sha256=hashes)
        return c,wave,amp,ctx
    except (ValueError,KeyError,TypeError,IndexError):return old._empty_cell(h,'reconstruction_unknown',channels),None,None,None


def build_combined(old_npz_bytes,old_manifest_bytes,new_plan_bytes,new_qualified_bytes,new_bodies,metadata_bytes,decode_record,*,pins,processing_begin):
    deadline(processing_begin)
    inputs=dict(old_npz=old_npz_bytes,old_manifest=old_manifest_bytes,new_plan=new_plan_bytes,new_qualified=new_qualified_bytes,metadata=metadata_bytes)
    _pins(inputs,pins);deadline(processing_begin)
    old_manifest=_json(old_manifest_bytes,1048576);plan=_json(new_plan_bytes,131072);q=_json(new_qualified_bytes,qc.MAX_PRIVATE);metadata=_json(metadata_bytes,131072)
    old.validate_manifest(old_manifest);eligible=metadata_validate(metadata,old_manifest,plan);_qualified(plan,q,new_bodies);deadline(processing_begin)
    prior=old.load_npz(old_npz_bytes,old_manifest);deadline(processing_begin)
    arrays={name:np.zeros((115,)+prior[name].shape[1:],dtype=prior[name].dtype) for name in META_NAMES}
    for name in ('amplitudes','contexts','magnitudes','partitions'):arrays[name][:65]=prior[name]
    arrays['magnitudes'][65:]=[m['mw'] for m in metadata[65:]];arrays['groups'][:]=[m['group'] for m in metadata]
    arrays['partitions'][65:]=0;rows=[];elements=0
    for i,r in enumerate(old_manifest['rows']):
        cells=copy.deepcopy(r['cells'])
        for j,c in enumerate(cells):
            if c['status']=='available':
                original=c['array'];name='wave_%03d_%d'%(i,c['horizon']);a=prior[original];arrays[name]=a;c['array']=name;elements+=a.size
                family='ENZ' if [x[-1] for x in c['channels']]==list('ENZ') else '12Z' if [x[-1] for x in c['channels']]==list('12Z') else None
                ctx=context({'family':family,'t0_ns':0,'pick_ns':0},metadata[i],c['horizon'],Fraction(10**9)/Fraction(*c['period']))
                if not np.array_equal(ctx[3:],prior['contexts'][i,j,3:]):raise ValueError('old_static_metadata_binding')
        common=r['cohort'] and eligible[i] and all(prior['contexts'][i,j,1]>=.25 for j in range(3))
        arrays['cohort'][i]=common
        rows.append(dict(ordinal=i,partition=r['partition'],group=metadata[i]['group'],mw=r['mw'],operational_eligible=eligible[i],cohort=bool(common),source='original65',original_group=r['group'],original_cohort=r['cohort'],cells=cells))
    if elements>MAX_ELEMENTS:raise RuntimeError('artifact_element_cap')
    counts=[0];records={};cached=None
    for i,row in enumerate(plan['rows']):
        deadline(processing_begin)
        if cached!=row['batch']:
            records.clear();records=_reconstruct(plan,q,new_bodies,decode_record,row['batch'],counts,processing_begin);cached=row['batch']
        g=65+i;cells=[]
        for j,h in enumerate((1,3,5)):
            c,wave,amp,ctx=_cell(row,q['rows'][i]['cells'][j],h,records,metadata[g],eligible[g],elements,processing_begin);cells.append(c)
            if wave is not None:arrays[c['array']]=wave;arrays['amplitudes'][g,j]=amp;arrays['contexts'][g,j]=ctx;elements+=wave.size
        common=eligible[g] and all(c['status']=='available' for c in cells);arrays['cohort'][g]=common
        rows.append(dict(ordinal=g,partition='TRAIN',group=metadata[g]['group'],mw=float(metadata[g]['mw']),operational_eligible=eligible[g],cohort=bool(common),source='new50',original_group=None,original_cohort=None,cells=cells))
    manifest=dict(schema=SCHEMA,study=STUDY,proposal_sha256=PROPOSAL_SHA,custody=copy.deepcopy(pins),native_namespaces=dict(original_rows=65,original_bodies=17,new_rows=50,new_bodies=13),rows=rows,denominators=dict(rows=115,cells=345,train=91,dev=24,test_excluded=31),observed_new_samples=counts[0])
    validate_manifest(manifest);validate_arrays(arrays,manifest);deadline(processing_begin)
    return arrays,manifest


def save_npz(arrays,*,processing_begin):
    deadline(processing_begin)
    if type(arrays) is not dict or not META_NAMES.issubset(arrays) or len(arrays)>351:raise ValueError("archive_members")
    total=elements=0
    for name,value in arrays.items():
        match=WAVE.fullmatch(name) if type(name) is str else None
        if name not in META_NAMES and (not match or int(match[1])>114):raise ValueError("archive_member")
        if type(value) is not np.ndarray or value.dtype.hasobject or value.dtype.kind not in "fiu" or not np.isfinite(value).all():raise ValueError("npy_type")
        if match:
            if value.dtype.str!="<f4" or value.ndim!=2 or value.shape[0]!=3 or value.shape[1]<=0:raise ValueError("wave_shape")
            elements+=value.size
        expected={"amplitudes":("<f4",(115,3,4)),"contexts":("<f8",(115,3,29)),"magnitudes":("<f8",(115,)),"groups":("<i4",(115,)),"partitions":("|u1",(115,)),"cohort":("|u1",(115,))}
        if not match and (value.dtype.str,value.shape)!=expected[name]:raise ValueError("metadata_shape")
        # Exact NPY header and payload accounting precedes compression/writer allocation.
        head=io.BytesIO();np.lib.format.write_array_header_1_0(head,np.lib.format.header_data_from_array_1_0(value))
        if len(head.getvalue())>4106:raise ValueError("npy_header_cap")
        total+=len(head.getvalue())+value.nbytes
    if elements>MAX_ELEMENTS or total>MAX_UNCOMPRESSED:raise ValueError("artifact_element_cap")
    stream=io.BytesIO();np.savez_compressed(stream,**arrays);raw=stream.getvalue()
    inspect_npz(raw,processing_begin=processing_begin)
    deadline(processing_begin)
    return raw


def inspect_npz(raw,*,processing_begin):
    deadline(processing_begin)
    if type(raw) is not bytes or len(raw)>MAX_ARCHIVE:raise ValueError("archive_cap")
    total=elements=0;headers={}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos=archive.infolist()
        if len(infos)>351:raise ValueError("archive_members")
        for info in infos:
            if info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or not info.filename.endswith(".npy"):raise ValueError("archive_member")
            name=info.filename[:-4];match=WAVE.fullmatch(name)
            if name in headers or (name not in META_NAMES and not match) or (match and int(match[1])>114):raise ValueError("archive_member")
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
            expected={"amplitudes":("<f4",(115,3,4)),"contexts":("<f8",(115,3,29)),"magnitudes":("<f8",(115,)),"groups":("<i4",(115,)),"partitions":("|u1",(115,)),"cohort":("|u1",(115,))}
            if match:
                if dtype.str!="<f4" or len(shape)!=2 or shape[0]!=3 or shape[1]<=0:raise ValueError("wave_shape")
                elements+=count
            elif (dtype.str,shape)!=expected[name]:raise ValueError("metadata_shape")
            if elements>MAX_ELEMENTS:raise ValueError("artifact_element_cap")
            headers[name]=(dtype.str,shape)
    if not META_NAMES.issubset(headers):raise ValueError("archive_members")
    deadline(processing_begin)
    return headers




def validate_manifest(m):
    keys=('schema','study','proposal_sha256','custody','native_namespaces','rows','denominators','observed_new_samples')
    if (not qc._keys(m,keys) or m['schema']!=SCHEMA or m['study']!=STUDY or m['proposal_sha256']!=PROPOSAL_SHA
            or canonical(m['denominators'])!=canonical(dict(rows=115,cells=345,train=91,dev=24,test_excluded=31))
            or canonical(m['native_namespaces'])!=canonical(dict(original_rows=65,original_bodies=17,new_rows=50,new_bodies=13))
            or not qc._int(m['observed_new_samples'],0,qc.MAX_TOTAL_SAMPLES) or type(m['rows']) is not list or len(m['rows'])!=115
            or not qc._keys(m['custody'],('old_npz','old_manifest','new_plan','new_qualified','metadata'))):raise ValueError('manifest_schema')
    for p in m['custody'].values():
        if not qc._keys(p,('bytes','sha256')) or not qc._int(p['bytes'],0,MAX_ARCHIVE) or not qc._sha(p['sha256']):raise ValueError('manifest_custody')
    parts=[]
    for i,r in enumerate(m['rows']):
        if (not qc._keys(r,('ordinal','partition','group','mw','operational_eligible','cohort','source','original_group','original_cohort','cells'))
                or not qc._int(r['ordinal'],i,i) or type(r['partition']) is not str or r['partition'] not in ('TRAIN','DEV') or i>=65 and r['partition']!='TRAIN'
                or not qc._int(r['group'],-1,i) or not _finite(r['mw']) or type(r['operational_eligible']) is not bool or type(r['cohort']) is not bool
                or r['group']==-1 and r['operational_eligible'] or r['source']!=('original65' if i<65 else 'new50')
                or type(r['cells']) is not list or len(r['cells'])!=3):raise ValueError('manifest_row')
        if i<65:
            if not qc._int(r['original_group'],0,64) or type(r['original_cohort']) is not bool:raise ValueError('original_role_provenance')
        elif r['original_group'] is not None or r['original_cohort'] is not None:raise ValueError('new_role_provenance')
        parts.append(r['partition'])
        for h,c in zip((1,3,5),r['cells']):
            if (not qc._keys(c,('horizon','status','reason','array','shape','first','period','precontext_count','channels','view_sha256'))
                    or not qc._int(c['horizon'],h,h) or type(c['channels']) is not list or any(type(x) is not str for x in c['channels'])):raise ValueError('manifest_cell')
            if c['status']=='available':
                if (c['reason']!='supported' or c['array']!='wave_%03d_%d'%(i,h) or type(c['shape']) is not list or len(c['shape'])!=2
                        or type(c['shape'][0]) is not int or c['shape'][0]!=3 or not qc._int(c['shape'][1],1,MAX_ELEMENTS//3)
                        or not qc._int(c['precontext_count'],1,c['shape'][1]) or len(c['channels'])!=3 or len(set(c['channels']))!=3
                        or type(c['view_sha256']) is not list or len(c['view_sha256'])!=3 or not all(qc._sha(v) for v in c['view_sha256'])):raise ValueError('manifest_cell')
                qc._rational(c['period']);v=c['first']
                if type(v) is not list or len(v)!=2 or any(type(x) is not int for x in v) or v[1]<=0 or math.gcd(*v)!=1:raise ValueError('manifest_cell')
            elif c['status']!='unavailable' or c['reason'] not in ('selection_unknown','metadata_unknown','operational_ineligible','qualification_unknown','grid_mismatch','no_precontext','reconstruction_unknown','local_age') or any(c[k] is not None for k in ('array','shape','first','period','precontext_count','view_sha256')):raise ValueError('manifest_cell')
        available=all(c['status']=='available' for c in r['cells'])
        if r['cohort'] and (not available or not r['operational_eligible'] or r['group']<0):raise ValueError('manifest_cohort')
        if i<65 and r['original_cohort']!=available:raise ValueError('original_cohort_provenance')
    if parts[:65].count('TRAIN')!=41 or parts[:65].count('DEV')!=24:raise ValueError('manifest_partition')
    shared={r['group'] for r in m['rows'] if r['group']>=0 and len({v['partition'] for v in m['rows'] if v['group']==r['group']})>1}
    if any(r['operational_eligible'] or r['cohort'] for r in m['rows'] if r['group'] in shared):raise ValueError('manifest_cross_group')


def validate_arrays(arrays,m):
    validate_manifest(m)
    expected=META_NAMES|{c['array'] for r in m['rows'] for c in r['cells'] if c['status']=='available'}
    if type(arrays) is not dict or set(arrays)!=expected or len(arrays)>351:raise ValueError('manifest_members')
    shapes={'amplitudes':('<f4',(115,3,4)),'contexts':('<f8',(115,3,29)),'magnitudes':('<f8',(115,)),'groups':('<i4',(115,)),'partitions':('|u1',(115,)),'cohort':('|u1',(115,))}
    elements=0
    for name,a in arrays.items():
        if type(a) is not np.ndarray or not a.flags.c_contiguous or not np.isfinite(a).all():raise ValueError('artifact_numeric')
        if name in META_NAMES:
            if (a.dtype.str,a.shape)!=shapes[name]:raise ValueError('metadata_shape')
        else:
            if a.dtype.str!='<f4' or a.ndim!=2 or a.shape[0]!=3 or a.shape[1]<1:raise ValueError('wave_shape')
            elements+=a.size
    if elements>MAX_ELEMENTS:raise ValueError('artifact_element_cap')
    for r in m['rows']:
        i=r['ordinal']
        if (arrays['magnitudes'][i]!=r['mw'] or arrays['groups'][i]!=r['group'] or arrays['partitions'][i]!=(r['partition']=='DEV')
                or arrays['cohort'][i]!=r['cohort']):raise ValueError('manifest_metadata')
        for j,c in enumerate(r['cells']):
            if c['status']=='available':
                if list(arrays[c['array']].shape)!=c['shape']:raise ValueError('manifest_shape')
            elif np.any(arrays['amplitudes'][i,j]) or np.any(arrays['contexts'][i,j]):raise ValueError('unavailable_context')
        common=r['operational_eligible'] and all(c['status']=='available' for c in r['cells']) and all(arrays['contexts'][i,j,1]>=.25 for j in range(3))
        if r['cohort']!=common:raise ValueError('cohort_role_binding')


def load_npz(raw,manifest,*,processing_begin):
    deadline(processing_begin);validate_manifest(manifest)
    headers=inspect_npz(raw,processing_begin=processing_begin)
    expected=META_NAMES|{c['array'] for r in manifest['rows'] for c in r['cells'] if c['status']=='available'}
    if set(headers)!=expected:raise ValueError('manifest_members')
    with np.load(io.BytesIO(raw),allow_pickle=False) as loaded:arrays={name:loaded[name] for name in headers}
    validate_arrays(arrays,manifest);deadline(processing_begin)
    return arrays

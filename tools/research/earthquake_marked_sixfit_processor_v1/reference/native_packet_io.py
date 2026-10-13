"""Strict in-memory numeric custody for marked packets; no paths or pickle."""
import ast
import copy
import hashlib
import io
import json
import math
import re
import statistics
import struct
import zipfile
import numpy as np
import marked_native as m

STORAGE_SCHEMA='marked-native-numeric-storage-v1'
MAX_MANIFEST=4*1024*1024
MAX_PAYLOAD=1024*1024
MAX_ARCHIVE=8*1024*1024
MAX_MEMBERS=2875
NOISE_ARRAYS=('centers','powers','nhat','floors','nu','weights')
H_ARRAYS=('ratios','reported','censor','max_ratios','states','run_ages')
MEMBER=re.compile(r'r_\d{3}_(?:precontext|noise_(?:centers|powers|nhat|floors|nu|weights)|h[135]_(?:ratios|reported|censor|max_ratios|states|run_ages))\Z')


def json_load(raw,cap):
    m.need(type(raw) is bytes and len(raw)<=cap,'storage_json_cap')
    def pairs(items):
        d={}
        for k,v in items:
            m.need(k not in d,'storage_duplicate');d[k]=v
        return d
    def bad(_):raise m.FeatureError('storage_nonfinite')
    value=json.loads(raw.decode('utf8'),object_pairs_hook=pairs,parse_constant=bad)
    todo=[(value,0)];nodes=0
    while todo:
        x,d=todo.pop();nodes+=1;m.need(d<=32 and nodes<=2_000_000,'storage_structure')
        if type(x) is dict:todo.extend((v,d+1) for v in x.values())
        elif type(x) is list:todo.extend((v,d+1) for v in x)
        elif type(x) is float:m.need(math.isfinite(x),'storage_nonfinite')
        elif type(x) is int:m.need(x.bit_length()<=4096,'storage_integer')
    return value


def require_array(a,dtype,shape,lo=-math.inf,hi=math.inf):
    m.need(type(a) is np.ndarray and a.dtype.str==np.dtype(dtype).str and a.shape==shape
           and a.flags.c_contiguous and np.isfinite(a).all() and (a>=lo).all() and (a<=hi).all(),'storage_array')


def arrays_of(row):
    if not row['common']:return []
    base='r_%03d_'%row['ordinal']
    out=[(base+'precontext',row,'precontext')]
    out.extend((base+'noise_'+key,row['noise'],key) for key in NOISE_ARRAYS)
    out.extend((base+'h%d_'%h['seconds']+key,h,key) for h in row['horizons'] for key in H_ARRAYS)
    return out


def validate(packet,*,processing_begin):
    m.deadline(processing_begin)
    m.need(m.keys(packet,('schema','study','rows','denominators','input_pins','observed_samples','fit_authorized'))
           and packet['schema']==m.SCHEMA and packet['study']==m.STUDY and packet['fit_authorized'] is False,'storage_packet')
    m.need(m.canonical(packet['denominators'])==m.canonical(m.DENOMINATORS),'storage_denominators')
    m.need(m.keys(packet['input_pins'],m.LIMITS) and all(m.valid_pin(v,m.LIMITS[k]) for k,v in packet['input_pins'].items()),'storage_pins')
    counts=packet['observed_samples']
    m.need(m.keys(counts,('old','new')) and m.integer(counts['old'],0,136_000_000)
           and m.integer(counts['new'],0,104_000_000) and counts['old']+counts['new']<=240_000_000,'storage_counts')
    m.need(type(packet['rows']) is list and len(packet['rows'])==115,'storage_rows')
    totals=dict(TRAIN=0,DEV=0);common=dict(TRAIN=0,DEV=0);payload=0;members=0
    for i,row in enumerate(packet['rows']):
        m.deadline(processing_begin)
        m.need(m.keys(row,('ordinal','partition','mw','group','common','status','precontext','noise','horizons'))
               and m.integer(row['ordinal'],i,i) and type(row['partition']) is str and row['partition'] in totals
               and m.number(row['mw'],-5,15) and m.integer(row['group'],-1,i) and type(row['common']) is bool,'storage_row')
        totals[row['partition']]+=1
        m.need(type(row['horizons']) is list and len(row['horizons'])==3,'storage_horizons')
        if not row['common']:
            m.need(row['status']=='unavailable' and row['precontext'] is None and row['noise'] is None
                   and m.canonical(row['horizons'])==m.canonical([dict(seconds=h,status='unavailable') for h in m.HORIZONS]),'storage_unavailable')
            continue
        common[row['partition']]+=1;m.need(row['status']=='available' and row['group']>=0,'storage_common')
        n=row['noise'];m.need(m.keys(n,NOISE_ARRAYS+('rate','arrival_offset_ns')),'storage_noise')
        require_array(n['centers'],'<f8',(3,),-1e12,1e12);require_array(n['powers'],'<f8',(3,12),0,1e24)
        require_array(n['nhat'],'<f8',(3,),1,1e24);require_array(n['floors'],'u1',(3,),0,1)
        require_array(n['nu'],'<f8',(12,3));require_array(n['weights'],'<f8',(12,))
        m.need(type(n['rate']) is list and len(n['rate'])==2 and all(m.integer(x,1,2**63-1) for x in n['rate'])
               and math.gcd(*n['rate'])==1 and m.integer(n['arrival_offset_ns'],0,750_000_000),'storage_clock')
        rawmed=[statistics.median(q.tolist()) for q in n['powers']]
        m.need(m.bit_equal(n['nhat'],m.array([max(1.,v) for v in rawmed],'<f8'))
               and n['floors'].tolist()==[int(v<1.) for v in rawmed],'storage_floor')
        eta=[[math.log(max(1.,statistics.median(q.tolist()[:ell]+q.tolist()[ell+1:]))) for q in n['powers']] for ell in range(12)]
        mu=[math.fsum(e[c] for e in eta)/12 for c in range(3)]
        m.need(m.bit_equal(n['nu'],m.array([[e[c]-mu[c] for c in range(3)] for e in eta],'<f8'))
               and m.bit_equal(n['weights'],m.array([1/12]*12,'<f8')),'storage_noise_support')
        ctx=row['precontext'];require_array(ctx,'<f8',(34,))
        expected=[*[math.log10(v) for v in n['nhat']],*[float(v) for v in n['floors']],n['arrival_offset_ns']/1e9,
                  math.log10(n['rate'][0]/n['rate'][1])]
        m.need(m.bit_equal(ctx[:8],m.array(expected,'<f8')),'storage_precontext')
        for inds in ((14,15),(22,23,24,25),(26,27,28,29),(30,31,32,33)):
            m.need(all(ctx[k] in (0.,1.) for k in inds) and sum(ctx[k] for k in inds)==1.,'storage_categories')
        m.need(all(ctx[k] in (0.,1.) for k in (11,12,13,19,20,21)),'storage_missing')
        previous=None
        for h,item in zip(m.HORIZONS,row['horizons']):
            j=(h*m.SECOND-n['arrival_offset_ns'])//m.Q
            m.need(m.keys(item,('seconds','status')+H_ARRAYS) and m.integer(item['seconds'],h,h)
                   and item['status']=='available' and 1<=j<=20,'storage_horizon')
            require_array(item['ratios'],'<f8',(j,3),0,1e25);require_array(item['reported'],'<f8',(j,3))
            require_array(item['censor'],'u1',(j,3),0,1);require_array(item['max_ratios'],'<f8',(j,),0,1e25)
            require_array(item['states'],'u1',(j,),0,1);require_array(item['run_ages'],'u1',(j,),1,20)
            ratios=item['ratios'].tolist();marks=[[m.report_ratio(v) for v in r] for r in ratios]
            cs=[[x[1] for x in r] for r in marks];ys=[[x[0] for x in r] for r in marks]
            maxima=[max(r) for r in ratios];states=[int(v>9.) for v in maxima];ages=[];age=0;last=None
            for s in states:age=age+1 if s==last else 1;ages.append(age);last=s
            for key,value,dtype in (('censor',cs,'u1'),('reported',ys,'<f8'),('max_ratios',maxima,'<f8'),('states',states,'u1'),('run_ages',ages,'u1')):
                m.need(m.bit_equal(item[key],m.array(value,dtype)),'storage_mark_semantics')
            if previous is not None:
                k=len(previous['ratios']);m.need(j==k+8 and all(m.bit_equal(previous[key],item[key][:k]) for key in H_ARRAYS),'storage_prefix')
            previous=item
        for _,obj,key in arrays_of(row):payload+=obj[key].nbytes;members+=1
    m.need(totals==dict(TRAIN=91,DEV=24) and common==dict(TRAIN=65,DEV=22),'storage_population')
    group_roles={}
    for row in packet['rows']:
        if row['group']>=0:group_roles.setdefault(row['group'],set()).add(row['partition'])
    m.need(not any(row['common'] and len(group_roles[row['group']])>1 for row in packet['rows']),'storage_group_overlap')
    m.need(payload<=MAX_PAYLOAD and members<=MAX_MEMBERS,'storage_payload_cap')
    m.deadline(processing_begin)


def save(packet,*,processing_begin):
    validate(packet,processing_begin=processing_begin)
    scalar=copy.deepcopy(packet);entries={};archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED) as z:
        for row in scalar['rows']:
            for name,obj,key in arrays_of(row):
                m.deadline(processing_begin);a=obj[key];payload=a.tobytes(order='C')
                entries[name]=dict(dtype=a.dtype.str,shape=list(a.shape),bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
                b=io.BytesIO();np.save(b,a,allow_pickle=False);z.writestr(name+'.npy',b.getvalue());obj[key]=name
    raw=archive.getvalue();manifest=m.canonical(dict(schema=STORAGE_SCHEMA,packet=scalar,arrays=entries))
    m.need(len(raw)<=MAX_ARCHIVE and len(manifest)<=MAX_MANIFEST and len(raw)+len(manifest)<=MAX_ARCHIVE,'storage_output_cap')
    m.deadline(processing_begin)
    return raw,manifest


def load(archive,manifest,*,pins,processing_begin):
    m.deadline(processing_begin)
    m.need(m.keys(pins,('archive','manifest')),'storage_input_pins')
    for raw,key,cap in ((archive,'archive',MAX_ARCHIVE),(manifest,'manifest',MAX_MANIFEST)):
        m.need(type(raw) is bytes and len(raw)<=cap and m.valid_pin(pins[key],cap) and m.pin(raw)==pins[key],'storage_input_pin')
    m.need(len(archive)+len(manifest)<=MAX_ARCHIVE,'storage_combined_cap')
    top=json_load(manifest,MAX_MANIFEST)
    m.need(m.keys(top,('schema','packet','arrays')) and top['schema']==STORAGE_SCHEMA
           and type(top['arrays']) is dict and 0<len(top['arrays'])<=MAX_MEMBERS,'storage_manifest')
    entries=top['arrays'];payload_total=0;expected=set()
    for name,e in entries.items():
        m.need(type(name) is str and MEMBER.fullmatch(name) and int(name[2:5])<115
               and m.keys(e,('dtype','shape','bytes','sha256')),'storage_entry')
        m.need(type(e['shape']) is list and 1<=len(e['shape'])<=2 and all(m.integer(x,1,34) for x in e['shape'])
               and e['dtype'] in ('<f8','|u1') and m.valid_pin(dict(bytes=e['bytes'],sha256=e['sha256']),MAX_PAYLOAD),'storage_shape')
        n=math.prod(e['shape'])*np.dtype(e['dtype']).itemsize;m.need(n==e['bytes'],'storage_size')
        payload_total+=n;expected.add(name+'.npy')
    m.need(payload_total<=MAX_PAYLOAD,'storage_payload_cap')
    arrays={}
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        members=z.infolist();m.need(len(members)==len(expected) and {x.filename for x in members}==expected,'storage_member_set')
        m.need(sum(x.file_size for x in members)<=MAX_ARCHIVE,'storage_uncompressed_cap')
        for member in members:
            m.deadline(processing_begin);name=member.filename[:-4];e=entries[name]
            m.need(member.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) and not member.flag_bits&1
                   and e['bytes']<member.file_size<=e['bytes']+4112,'storage_framing')
            with z.open(member) as f:
                magic=f.read(8);m.need(magic[:6]==b'\x93NUMPY' and magic[6:] in (b'\x01\x00',b'\x02\x00'),'storage_npy')
                width=2 if magic[6]==1 else 4;length=f.read(width);m.need(len(length)==width,'storage_npy')
                n=struct.unpack('<H' if width==2 else '<I',length)[0];m.need(n<=4096,'storage_header_cap')
                raw_header=f.read(n);m.need(len(raw_header)==n,'storage_npy')
                header=ast.literal_eval(raw_header.decode('latin1'))
                m.need(m.keys(header,('descr','fortran_order','shape')) and header['descr']==e['dtype']
                       and header['fortran_order'] is False and type(header['shape']) is tuple
                       and all(type(x) is int for x in header['shape']) and list(header['shape'])==e['shape']
                       and 8+width+n+e['bytes']==member.file_size,'storage_npy_shape')
                payload=f.read(e['bytes']);m.need(len(payload)==e['bytes'] and f.read(1)==b''
                       and hashlib.sha256(payload).hexdigest()==e['sha256'],'storage_payload_hash')
                arrays[name]=np.frombuffer(payload,dtype=e['dtype']).reshape(e['shape']).copy(order='C')
    packet=top['packet'];m.need(type(packet) is dict and type(packet.get('rows')) is list and len(packet['rows'])==115,'storage_rows')
    refs=[]
    for i,row in enumerate(packet['rows']):
        m.need(type(row) is dict and m.integer(row.get('ordinal'),i,i) and type(row.get('common')) is bool,'storage_row')
        if row['common']:
            m.need(type(row.get('noise')) is dict and type(row.get('horizons')) is list and len(row['horizons'])==3,'storage_refs')
            for h,item in zip(m.HORIZONS,row['horizons']):
                m.need(type(item) is dict and m.integer(item.get('seconds'),h,h),'storage_refs')
            for name,obj,key in arrays_of(row):
                m.need(obj.get(key)==name and name in arrays,'storage_reference');obj[key]=arrays[name];refs.append(name)
    m.need(len(refs)==len(set(refs)) and set(refs)==set(arrays),'storage_reference_closure')
    validate(packet,processing_begin=processing_begin)
    return packet

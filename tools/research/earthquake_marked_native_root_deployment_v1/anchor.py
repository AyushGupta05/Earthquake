"""Independent original-activity projection; pure bytes and stdlib, no file IO."""
import ast,copy,hashlib,io,json,math,re,struct,time,zipfile

RAW_KEYS={'old_plan','old_qualified','new_plan','new_qualified','metadata','roster'}
DEN=dict(events=115,cells=345,train=91,dev=24,test_excluded=31)
SCHEMA='earthquake-TRAIN115-receiver-observations-v2'
STUDY='earthquake-TRAIN115-receiver-renewal-v2'
MEMBER=re.compile(r'r_\d{3}_(?:init|h[135])_(?:wave|amplitude|context)\Z')


def need(v,reason):
    if not v:raise ValueError(reason)


def tick(begin):
    now=time.monotonic();need(type(begin) in (int,float) and math.isfinite(begin) and 0<=begin<=now and now-begin<=300,'deadline')


def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
def pin(b):return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def keys(v,k):return type(v) is dict and set(v)==set(k) and all(type(x) is str for x in v)
def integer(v,lo,hi):return type(v) is int and lo<=v<=hi

def number(v,lo=-math.inf,hi=math.inf):
    try:return type(v) in (int,float) and math.isfinite(v) and lo<=v<=hi
    except OverflowError:return False


def parse(b,cap):
    need(type(b) is bytes and len(b)<=cap,'json_cap')
    def pairs(items):
        d={}
        for k,v in items:need(k not in d,'duplicate_key');d[k]=v
        return d
    value=json.loads(b,object_pairs_hook=pairs,parse_constant=lambda x:need(False,'nonfinite'))
    stack=[(value,0)];count=0
    while stack:
        v,depth=stack.pop();count+=1;need(depth<=32 and count<=2_000_000,'json_structure')
        if type(v) is dict:stack.extend((x,depth+1) for x in v.values())
        elif type(v) is list:stack.extend((x,depth+1) for x in v)
        elif type(v) is float:need(math.isfinite(v),'nonfinite')
    return value


def checked_pin(raw,p,cap):
    need(type(raw) is bytes and len(raw)<=cap and keys(p,('bytes','sha256')) and integer(p['bytes'],0,cap) and type(p['sha256']) is str and re.fullmatch('[0-9a-f]{64}',p['sha256']) and pin(raw)==p,'pin')


def context(raw,entry):
    need(keys(entry,('dtype','shape','bytes','sha256')) and entry['dtype']=='<f8' and type(entry['shape']) is list and len(entry['shape'])==1 and integer(entry['shape'][0],35,35) and integer(entry['bytes'],280,280),'context_entry')
    need(type(raw) is bytes and 280<len(raw)<=280+4112 and raw[:6]==b'\x93NUMPY' and raw[6:8] in (b'\x01\x00',b'\x02\x00'),'npy')
    width=2 if raw[6]==1 else 4;n=struct.unpack('<H' if width==2 else '<I',raw[8:8+width])[0];need(n<=4096 and len(raw)==8+width+n+280,'npy_size')
    header=ast.literal_eval(raw[8+width:8+width+n].decode('latin1'));need(keys(header,('descr','fortran_order','shape')) and header['descr']=='<f8' and header['fortran_order'] is False and type(header['shape']) is tuple and len(header['shape'])==1 and integer(header['shape'][0],35,35),'npy_header')
    data=raw[8+width+n:];need(hashlib.sha256(data).hexdigest()==entry['sha256'],'context_hash');values=list(struct.unpack('<35d',data));need(all(number(x) for x in values),'context_finite');return values


def project(archive_bytes,manifest_bytes,agreement_bytes,*,pins,input_pins,processing_begin):
    tick(processing_begin);need(keys(pins,('archive','manifest','agreement')) and keys(input_pins,RAW_KEYS),'authority')
    for name,raw,cap in [('archive',archive_bytes,128*1024*1024),('manifest',manifest_bytes,4*1024*1024),('agreement',agreement_bytes,16*1024*1024)]:checked_pin(raw,pins[name],cap)
    agreement=parse(agreement_bytes,16*1024*1024);pub=agreement['public']
    need(pub['schema']=='earthquake-TRAIN115-receiver-observation-independent-audit-v1' and pub['study']==STUDY and pub['disposition']=='agreed' and pub['reason']=='exact_native_semantics' and integer(pub['events'],115,115) and integer(pub['common_train'],65,65) and integer(pub['common_dev'],22,22) and integer(pub['checked_observations'],348,348) and pub['fit_authorized'] is False and agreement['fit_authorized'] is False and canonical(agreement['input_pins'])==canonical(input_pins),'original_agreement')
    m=parse(manifest_bytes,4*1024*1024);need(keys(m,('schema','packet','arrays')) and m['schema']=='receiver-observation-storage-v2' and type(m['arrays']) is dict and len(m['arrays'])==1044,'storage_manifest')
    p=copy.deepcopy(m['packet']);need(keys(p,('schema','study','rows','denominators','input_pins','observed_samples','fit_authorized')) and p['schema']==SCHEMA and p['study']==STUDY and p['fit_authorized'] is False and canonical(p['denominators'])==canonical(DEN) and canonical(p['input_pins'])==canonical(input_pins) and type(p['rows']) is list and len(p['rows'])==115,'packet')
    need(keys(p['observed_samples'],('old','new')) and integer(p['observed_samples']['old'],0,136_000_000) and integer(p['observed_samples']['new'],0,104_000_000) and canonical(p['observed_samples'])==canonical(agreement['observed_samples']),'observed')
    expected=set();payload=0
    for name,e in m['arrays'].items():
        need(type(name) is str and MEMBER.fullmatch(name) and int(name[2:5])<=114 and keys(e,('dtype','shape','bytes','sha256')) and type(e['shape']) is list and all(integer(v,1,20_000_000) for v in e['shape']) and type(e['sha256']) is str and re.fullmatch('[0-9a-f]{64}',e['sha256']),'array_entry')
        kind=name.rsplit('_',1)[-1];need(e['dtype']==('<f8' if kind=='context' else '<f4'),'array_dtype');count=math.prod(e['shape']);need(count<=20_000_000 and integer(e['bytes'],count*(8 if kind=='context' else 4),count*(8 if kind=='context' else 4)),'array_bytes');payload+=e['bytes'];expected.add(name+'.npy')
    need(payload<=128*1024*1024 and integer(agreement['numeric_payload_bytes'],payload,payload),'payload')
    counts={'TRAIN':0,'DEV':0};common={'TRAIN':0,'DEV':0};rows=[];used=set()
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        infos=z.infolist();need(len(infos)==1044 and {x.filename for x in infos}==expected and sum(x.file_size for x in infos)<=128*1024*1024,'archive_closed')
        for x in infos:
            e=m['arrays'][x.filename[:-4]];need(x.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) and not x.flag_bits&1 and e['bytes']<x.file_size<=e['bytes']+4112,'archive_member')
        for i,r in enumerate(p['rows']):
            tick(processing_begin);need(keys(r,('ordinal','partition','mw','group','common','status','initial','horizons')) and integer(r['ordinal'],i,i) and type(r['partition']) is str and r['partition'] in counts and number(r['mw'],-5,15) and integer(r['group'],-1,i) and type(r['common']) is bool and type(r['horizons']) is list and len(r['horizons'])==3,'row')
            counts[r['partition']]+=1;common[r['partition']]+=int(r['common']);a={k:r[k] for k in ('ordinal','partition','mw','group','common','status')}
            if r['common']:
                need(r['status']=='available' and r['group']>=0 and keys(r['initial'],('wave','amplitude','context')),'initial');name='r_%03d_init_context'%i;need(r['initial']['context']==name,'context_reference');r['initial']['context']=context(z.read(name+'.npy'),m['arrays'][name]);a['context35']=list(r['initial']['context']);a['horizons']=[];previous=None
                for h,x in zip((1,3,5),r['horizons']):
                    need(keys(x,('seconds','rate','wave','amplitude','context','ratios','states','run_ages')) and integer(x['seconds'],h,h) and type(x['ratios']) is list and 1<=len(x['ratios'])<=min(20,4*h) and type(x['states']) is list and type(x['run_ages']) is list and len(x['states'])==len(x['run_ages'])==len(x['ratios']),'history')
                    for k in ('wave','amplitude','context'):need(x[k]=='r_%03d_h%d_%s'%(i,h,k),'array_reference');used.add(x[k])
                    age=0;last=None
                    for ratio,state,run in zip(x['ratios'],x['states'],x['run_ages']):
                        need(number(ratio,0,1e25),'ratio');want=int(ratio>9);age=age+1 if want==last else 1;last=want;need(integer(state,want,want) and integer(run,age,age),'state_age')
                    need(number(a['context35'][6],0,1) and a['context35'][6]==x['states'][0],'initial_activity')
                    if previous is not None:
                        n=len(previous['ratios']);need(len(x['ratios'])==n+8 and all(canonical(x[k][:n])==canonical(previous[k]) for k in ('ratios','states','run_ages')),'future_prefix')
                    previous=x;a['horizons'].append(dict(seconds=h,status='available',ratios=list(x['ratios']),states=list(x['states']),run_ages=list(x['run_ages'])))
                for k in ('wave','amplitude'):need(r['initial'][k]=='r_%03d_init_%s'%(i,k),'initial_reference');used.add(r['initial'][k])
                used.add(name)
            else:
                need(r['status']=='unavailable' and r['initial'] is None and canonical(r['horizons'])==canonical([dict(seconds=h,status='unavailable') for h in (1,3,5)]),'unavailable');a['context35']=None;a['horizons']=copy.deepcopy(r['horizons'])
            rows.append(a)
    need(counts==dict(TRAIN=91,DEV=24) and common==dict(TRAIN=65,DEV=22) and used==set(m['arrays']),'denominator')
    a=dict(schema='marked-native-original-activity-anchor-v1',original_schema=SCHEMA,original_study=STUDY,source_pins={k:pins[k] for k in ('archive','manifest')},input_pins=copy.deepcopy(input_pins),denominators=copy.deepcopy(DEN),rows=rows)
    out=canonical(a);need(len(out)<=4*1024*1024,'anchor_cap');tick(processing_begin);return out,p

"""Source-only bounded fixed65 native POST transport. Importing performs no I/O."""
from dataclasses import dataclass,asdict
import datetime as dt,hashlib,http.client,json,math,os,re,select,signal,ssl,stat,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit
PROTOCOL='geonet-train-dev-prefix-POST-transport-v1'
STUDY='geonet-original-TRAINDEV65-prefix3-native-POST-v2'
PROPOSAL_SHA='d1fde0107ec473d0452d6354100052a1f7ce716f06bf22af047055cbd87e8f45'
ENDPOINT='https://service.geonet.org.nz/fdsnws/dataselect/1/query'
SOURCE_NAMES=('collector.py','PROTOCOL.md','SCHEMA.md','CONTROL_PARITY_PROOF.json','ACTUAL_GATE.md','PUBLIC_PROPOSAL.md')
PREREQUISITES=('original_projection_sha256','frozen_roster_sha256','metadata_custody_sha256','first_queryable_selection_proof_sha256','no_exact_complete_success_cache_proof_sha256')
ASSERTIONS=('original_selection_verified','no_exact_success_cache_verified','review_and_tests_verified','publication_verified','actual_POST_authorized')
CLAIMS=('waveform_rows_qualified','scientific_coverage_verified','metadata_http204_repaired','full_response_verified','physical_axes_verified','calibration_verified','operational_availability_verified','sequence_independence_verified','model_input_verified','magnitude_improvement_verified','novelty_verified','published_benchmark_superiority_verified')
ROOT=Path(__file__).resolve().parent
PLAN_CAP=131072;ARG_CAP=1048576;EVENT_CAP=4096

def encode(obj):return (json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf8')
def sha(body):return hashlib.sha256(body).hexdigest()
def fields(obj,names):
    if type(obj) is not dict or any(type(k) is not str for k in obj) or set(obj)!=set(names):raise ValueError('field schema')
def text(value,pattern):
    if type(value) is not str or re.fullmatch(pattern,value,re.ASCII) is None:raise ValueError('literal string schema')
    return value
def integer(value,lo,hi):
    if type(value) is not int or not lo<=value<=hi:raise ValueError('integer schema')
    return value
def hashtext(value):return text(value,r'[0-9a-f]{64}')
def strict_json(body):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate JSON')
            result[k]=v
        return result
    return json.loads(body.decode('utf8'),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
def utc_ns(value):
    integer(value,-2**63,2**63-1);seconds,nanos=divmod(value,10**9)
    stamp=dt.datetime(1970,1,1,tzinfo=dt.timezone.utc)+dt.timedelta(seconds=seconds)
    return stamp.strftime('%Y-%m-%dT%H:%M:%S')+'.%09dZ'%nanos

def entity(rows):
    lines=['format=miniseed']
    for row in rows:
        lines.append(' '.join((row['network'],row['station'],row['location'] or '--',row['prefix']+'?',utc_ns(row['t0_ns']-3*10**9),utc_ns(row['t0_ns']+5*10**9))))
    return ('\n'.join(lines)+'\n').encode('ascii')

@dataclass(frozen=True)
class Plan:
    source_bytes:bytes
    sha256:str
    study_id:str

def validate_plan(body):
    if type(body) is not bytes or not 0<len(body)<=PLAN_CAP:raise ValueError('plan bytes')
    p=strict_json(body);fields(p,('protocol','study_id','proposal_sha256','rows','batches','prerequisites'))
    if p['protocol']!=PROTOCOL or p['proposal_sha256']!=PROPOSAL_SHA:raise ValueError('plan identity')
    study=text(p['study_id'],r'geonet-original-TRAINDEV65-prefix3-native-POST-v2|invented-[a-z0-9-]{1,64}')
    fields(p['prerequisites'],PREREQUISITES)
    for v in p['prerequisites'].values():hashtext(v)
    rows=p['rows']
    if type(rows) is not list or len(rows)!=65:raise ValueError('fixed65 rows')
    previous=-1;ids=set();counts={'TRAIN':0,'DEV':0,'ENZ':0,'12Z':0,'unknown':0}
    for i,r in enumerate(rows):
        fields(r,('row_index','original_event_index','original_target_index','event_id','partition','network','station','location','prefix','t0_ns','pick_ns','metadata_status','nominal_family'))
        if integer(r['row_index'],0,64)!=i:raise ValueError('row order')
        event=integer(r['original_event_index'],0,95)
        if event<=previous:raise ValueError('original event order')
        previous=event;integer(r['original_target_index'],0,1000000)
        identifier=text(r['event_id'],r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
        if identifier in ids:raise ValueError('unique original event binding')
        ids.add(identifier);split=text(r['partition'],r'TRAIN|DEV');counts[split]+=1
        for k in ('network','station'):text(r[k],r'[A-Z0-9]{1,8}')
        text(r['location'],r'[A-Z0-9]{0,2}');text(r['prefix'],r'[A-Z0-9]{2}')
        integer(r['t0_ns'],-2**63+3*10**9,2**63-1-5*10**9);integer(r['pick_ns'],-2**63,2**63-1)
        if r['metadata_status']=='http204_unknown' and r['nominal_family'] is None:counts['unknown']+=1
        elif type(r['metadata_status']) is str and r['metadata_status']=='positive':counts[text(r['nominal_family'],r'ENZ|12Z')]+=1
        else:raise ValueError('fixed metadata annotation')
    if counts!={'TRAIN':41,'DEV':24,'ENZ':47,'12Z':14,'unknown':4}:raise ValueError('fixed41/24/47/14/4')
    if type(p['batches']) is not list or len(p['batches'])!=17:raise ValueError('fixed17 batches')
    for i,b in enumerate(p['batches']):
        fields(b,('batch_index','row_indices','request_body','request_sha256'))
        expected=list(range(4*i,min(4*i+4,65)))
        if integer(b['batch_index'],0,16)!=i or type(b['row_indices']) is not list or any(type(v) is not int for v in b['row_indices']) or b['row_indices']!=expected:raise ValueError('batch order/membership')
        raw=entity([rows[j] for j in expected])
        if type(b['request_body']) is not str or b['request_body'].encode('ascii')!=raw or len(raw)>16384 or hashtext(b['request_sha256'])!=sha(raw):raise ValueError('canonical entity')
    return Plan(body,sha(body),study)

@dataclass(frozen=True)
class Limits:
    connection_s:float=10.;first_body_s:float=60.;request_s:float=120.;start_spacing_s:float=1.
    processing_s:float=2160.;whole_s:float=2400.;term_s:float=5.;kill_s:float=5.
    body_bytes:int=8388608;total_retained_bytes:int=142606336;probe_bytes:int=1;total_consumption_upper:int=142606353
    request_bytes:int=16384;header_diagnostic_bytes:int=131072
DEFAULT=Limits()
def checked_limits(value,fixture):
    fields(value,asdict(DEFAULT));result=Limits(**value)
    for k,v in value.items():
        expected=getattr(DEFAULT,k)
        if type(expected) is int:
            integer(v,1,expected)
        elif type(v) not in (int,float) or not math.isfinite(v) or v<0 or v>expected:raise ValueError('finite bounded deadline')
    if not fixture and value!=asdict(DEFAULT):raise ValueError('production limits')
    if not (0<result.connection_s<=result.first_body_s<=result.request_s<=result.processing_s<result.whole_s and result.term_s>0 and result.kill_s>0 and result.term_s+result.kill_s<=result.whole_s-result.processing_s):raise ValueError('deadline ordering/reserve')
    if result.probe_bytes!=1 or result.total_retained_bytes!=17*result.body_bytes or result.total_consumption_upper!=17*(result.body_bytes+1):raise ValueError('exact byte totals/probe')
    return result

def read_regular(path,cap):
    if type(path) is not str:raise ValueError('path')
    p=Path(path)
    if not p.is_absolute() or str(p)!=path or p.resolve()!=p:raise ValueError('canonical regular path')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        st=os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size>cap:raise ValueError('regular file cap')
        body=f.read(cap+1)
    if len(body)>cap:raise ValueError('growing file cap')
    return body

def source_pins():return {n:sha(read_regular(str(ROOT/n),2097152)) for n in SOURCE_NAMES}
@dataclass(frozen=True)
class Authority:
    plan_sha256:str;source_files:dict;source_manifest_sha256:str;review_receipt_sha256:str;test_proof_sha256:str
    pushed_source_commit:str;authorization_reference:str;runtime_path:str;runtime_sha256:str;python_version:str
    prerequisites:dict;original_selection_verified:bool;no_exact_success_cache_verified:bool;review_and_tests_verified:bool;publication_verified:bool;actual_POST_authorized:bool
    def check(self,plan):
        if type(plan) is not Plan or type(plan.source_bytes) is not bytes or type(plan.sha256) is not str or type(plan.study_id) is not str or validate_plan(plan.source_bytes)!=plan or plan.study_id!=STUDY:raise ValueError('production immutable plan')
        hashtext(self.plan_sha256)
        if self.plan_sha256!=plan.sha256:raise ValueError('trusted plan pin')
        fields(self.source_files,SOURCE_NAMES)
        for v in self.source_files.values():hashtext(v)
        if self.source_files!=source_pins() or self.source_files['PUBLIC_PROPOSAL.md']!=PROPOSAL_SHA:raise ValueError('local source pin')
        for v in (self.source_manifest_sha256,self.review_receipt_sha256,self.test_proof_sha256,self.runtime_sha256):hashtext(v)
        text(self.pushed_source_commit,r'[0-9a-f]{40}');text(self.authorization_reference,r'[A-Za-z0-9][A-Za-z0-9 ._:/-]{0,255}')
        fields(self.prerequisites,PREREQUISITES)
        for v in self.prerequisites.values():hashtext(v)
        if self.prerequisites!=strict_json(plan.source_bytes)['prerequisites'] or any(getattr(self,k) is not True for k in ASSERTIONS):raise ValueError('fresh parent prerequisites')
        if type(self.runtime_path) is not str or str(Path(sys.executable).resolve())!=self.runtime_path or sha(read_regular(self.runtime_path,134217728))!=self.runtime_sha256 or type(self.python_version) is not str or self.python_version!=sys.version:raise ValueError('pinned runtime')

def claims():return {k:False for k in CLAIMS}
def write_new(path,body):
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:
        owned=os.fstat(f.fileno());f.write(body);f.flush();os.fsync(f.fileno())
    return owned
def finalize_receipt(path,owned,value):
    fd=os.open(path,os.O_WRONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'wb') as f:
        current=os.fstat(f.fileno())
        if (current.st_dev,current.st_ino)!=(owned.st_dev,owned.st_ino):raise ValueError('exclusive receipt replaced')
        f.truncate(0);f.write(encode(value));f.flush();os.fsync(f.fileno())

def member(path,cap):
    body=read_regular(str(path),cap);return {'name':path.name,'bytes':len(body),'sha256':sha(body)}
def emit(value):
    raw=encode(value)
    if len(raw)>EVENT_CAP:raise ValueError('event cap')
    sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
def spawn(mode):
    raw=read_regular(str(ROOT/'collector.py'),2097152)
    entry='__file__ = '+repr(str(ROOT/'collector.py'))+'\n'+raw.decode('utf8')
    return subprocess.Popen([sys.executable,'-I','-B','-S','-c',entry,mode],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True,env={'PATH':'/usr/bin:/bin','PYTHONIOENCODING':'utf8'})
def group_exists(pid):
    try:os.killpg(pid,0);return True
    except ProcessLookupError:return False
    except PermissionError:return True

def stop_group(pid,proc,limits,deadline):
    if not group_exists(pid):
        if proc is not None:
            try:proc.wait(timeout=max(0.001,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:return False
        return True
    for sig,seconds in ((signal.SIGTERM,limits.term_s),(signal.SIGKILL,limits.kill_s)):
        try:os.killpg(pid,sig)
        except ProcessLookupError:pass
        until=min(deadline,time.monotonic()+seconds)
        while time.monotonic()<until:
            if proc is not None:proc.poll()
            if not group_exists(pid):return True
            time.sleep(min(.01,max(0,until-time.monotonic())))
    return not group_exists(pid)

def check_context(arg):
    fixture=arg['fixture']
    if type(fixture) is not bool:raise ValueError('fixture flag')
    plan=validate_plan(arg['plan'].encode('utf8'));limits=checked_limits(arg['limits'],fixture)
    if fixture:
        if not plan.study_id.startswith('invented-'):raise ValueError('invented only')
        text(arg['endpoint'],r'http://127[.]0[.]0[.]1:[0-9]{1,5}')
        if not 1<=urlsplit(arg['endpoint']).port<=65535:raise ValueError('fixture port')
    else:
        if arg['endpoint']!=ENDPOINT:raise ValueError('fixed production endpoint')
        Authority(**arg['authority']).check(plan)
    return plan,limits

def header_framing(status,items):
    if not 200<=status<=999:raise ValueError('unsupported informational response')
    cls=[v for k,v in items if k.lower()=='content-length'];tes=[v for k,v in items if k.lower()=='transfer-encoding']
    if len(cls)>1 or len(tes)>1 or (cls and tes):raise ValueError('ambiguous framing')
    declared=None
    if cls:
        text(cls[0],r'[0-9]{1,20}');declared=int(cls[0])
    if tes and (type(tes[0]) is not str or tes[0].lower()!='chunked'):raise ValueError('unsupported transfer coding')
    if status in (204,304):return 'no_body',declared
    return ('chunked' if tes else 'fixed' if cls else 'eof'),declared

class ChunkReader:
    """Bounded raw syntax evidence; payload goes only to the separate body writer."""
    def __init__(self,fp,path,cap):
        self.fp=fp;self.fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        self.cap=cap;self.bytes=0;self.digest=hashlib.sha256();self.left=0;self.delimiter=False;self.complete=False
    def token(self,raw):
        if self.bytes+len(raw)>self.cap:raise ValueError('combined framing evidence cap')
        view=memoryview(raw)
        while view:
            written=os.write(self.fd,view)
            if written<=0:raise OSError('short framing write')
            self.digest.update(view[:written]);self.bytes+=written;view=view[written:]
    def line(self):
        raw=self.fp.readline(65537);self.token(raw)
        if not raw.endswith(b'\r\n') or len(raw)>65536:raise ValueError('chunk line framing')
        return raw
    def read1(self,maximum):
        if self.complete:return b''
        if self.left==0:
            if self.delimiter:
                raw=self.fp.read(2);self.token(raw)
                if raw!=b'\r\n':raise ValueError('chunk data delimiter')
                self.delimiter=False
            raw=self.line()
            if re.fullmatch(rb'[0-9A-Fa-f]{1,16}(?:;[\x20-\x7e]*)?\r\n',raw) is None:raise ValueError('chunk size syntax')
            self.left=int(raw[:-2].split(b';',1)[0],16)
            if self.left==0:
                for _ in range(100):
                    trailer=self.line()
                    if trailer==b'\r\n':self.complete=True;return b''
                    if re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+:[\x09\x20-\x7e]*\r\n",trailer) is None:raise ValueError('chunk trailer syntax')
                raise ValueError('chunk trailer count')
        raw=self.fp.read1(min(maximum,self.left))
        if not raw:raise ValueError('truncated chunk payload')
        if len(raw)>min(maximum,self.left):raise ValueError('chunk reader bound')
        self.left-=len(raw)
        if self.left==0:self.delimiter=True
        return raw
    def close(self):
        os.fsync(self.fd);os.close(self.fd)

def worker(arg):
    plan,limits=check_context(arg);index=integer(arg['batch_index'],0,16);batch=strict_json(plan.source_bytes)['batches'][index]
    request=batch['request_body'].encode('ascii');root=Path(arg['root']);path=root/('%03d.body.private'%index);header_path=root/('%03d.headers.private.json'%index)
    if http.client._MAXLINE!=65536 or http.client._MAXHEADERS!=100:raise ValueError('stdlib parser constants')
    parsed=urlsplit(arg['endpoint']);conn=None;fd=None;chunk_reader=None;observed=probe=0;framing='unknown';declared=status=None;outcome='worker_error';body_digest=hashlib.sha256();headers_sha=None
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        if arg['fixture']:conn=http.client.HTTPConnection(parsed.hostname,parsed.port,timeout=limits.request_s)
        else:
            context=ssl.create_default_context()
            if not context.check_hostname or context.verify_mode!=ssl.CERT_REQUIRED:raise ValueError('TLS validation required')
            conn=http.client.HTTPSConnection(parsed.hostname,parsed.port,timeout=limits.request_s,context=context)
        conn.connect();emit({'event':'connected','at':time.monotonic()})
        conn.putrequest('POST',parsed.path or '/',skip_accept_encoding=True);conn.putheader('Content-Type','text/plain');conn.putheader('Content-Length',str(len(request)));conn.putheader('Accept-Encoding','identity');conn.putheader('Connection','close');conn.endheaders(request)
        response=conn.getresponse();status=response.status;items=response.getheaders()
        try:framing,declared=header_framing(status,items)
        except ValueError:outcome='framing_error'
        diagnostics=encode({'status':status,'framing':framing,'declared':declared,'fields':[[k,v] for k,v in items],'parser_limits':{'line_bytes':65536,'header_count':100,'chunk_trailer_count':100}})
        if len(diagnostics)>limits.header_diagnostic_bytes:raise ValueError('retained diagnostic cap')
        write_new(header_path,diagnostics);headers_sha=sha(diagnostics);emit({'event':'headers','at':time.monotonic(),'status':status,'framing':framing,'declared':declared})
        if outcome=='framing_error':pass
        elif declared is not None and declared>limits.body_bytes and framing!='no_body':outcome='overflow'
        else:
            if framing=='chunked':chunk_reader=ChunkReader(response.fp,root/('%03d.framing.private'%index),limits.header_diagnostic_bytes-len(diagnostics))
            outcome='framed_complete' if framing=='no_body' else 'partial'
            first=False
            while framing!='no_body':
                requested=min(16384,limits.body_bytes-observed) if observed<limits.body_bytes else 1
                try:chunk=chunk_reader.read1(requested) if chunk_reader else response.read1(requested)
                except http.client.IncompleteRead as error:
                    chunk=error.partial
                    if len(chunk)>requested:raise ValueError('reader bound')
                    terminal=True
                else:terminal=False
                if len(chunk)>requested:raise ValueError('reader bound')
                if not chunk:
                    outcome='partial' if terminal else 'framed_complete';break
                if not first:emit({'event':'first','at':time.monotonic()});first=True
                if observed==limits.body_bytes:probe=len(chunk);outcome='overflow';break
                observed+=len(chunk);view=memoryview(chunk)
                while view:
                    written=os.write(fd,view)
                    if written<=0:raise OSError('short body write')
                    body_digest.update(view[:written]);view=view[written:]
                if terminal:outcome='partial';break
                if framing=='fixed' and response.length==0:outcome='framed_complete';break
            if framing=='fixed' and outcome=='framed_complete' and observed!=declared:outcome='partial'
        os.fsync(fd)
    except Exception:outcome='worker_error'
    finally:
        if conn is not None:conn.close()
        if fd is not None:os.close(fd)
        if chunk_reader is not None:chunk_reader.close()
    emit({'event':'done','at':time.monotonic(),'status':status,'framing':framing,'declared':declared,'outcome':outcome,'observed':observed,'probe':probe,'consumed':observed+probe,'body_sha256':body_digest.hexdigest(),'headers_sha256':headers_sha,'framing_sha256':chunk_reader.digest.hexdigest() if chunk_reader else None,'framing_evidence_complete':chunk_reader.complete if chunk_reader else False})

def request(arg,index,begin,limits):
    start=time.monotonic();proc=spawn('--worker');emit({'event':'worker_group','batch_index':index,'pid':proc.pid})
    if sys.stdin.buffer.read(1)!=b'G':raise ValueError('outer group registration acknowledgement')
    payload=encode({**arg,'batch_index':index});integer(len(payload),1,ARG_CAP)
    os.set_blocking(proc.stdin.fileno(),False);os.set_blocking(proc.stdout.fileno(),False)
    sent=0;buffer=b'';done=None;connected=headers=first=None;reason='worker_exit'
    deadline=min(start+limits.request_s,begin+limits.processing_s);whole=begin+limits.whole_s
    try:
        while True:
            bound=min(deadline,start+(limits.connection_s if connected is None else limits.first_body_s)) if first is None else deadline
            now=time.monotonic()
            if now>=bound:
                reason='processing_deadline' if bound==begin+limits.processing_s else 'request_deadline' if bound==deadline else 'connection_deadline' if connected is None else 'first_body_deadline';break
            readable,writable,_=select.select([proc.stdout],[proc.stdin] if sent<len(payload) else [],[],min(.05,bound-now))
            if time.monotonic()>=bound:continue
            if writable:
                sent+=os.write(proc.stdin.fileno(),payload[sent:])
                if sent==len(payload):proc.stdin.close()
            if readable:
                chunk=os.read(proc.stdout.fileno(),8192)
                if not chunk:break
                buffer+=chunk
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1)
                    if len(line)>EVENT_CAP:raise ValueError('event bound')
                    event=strict_json(line);kind=event['event']
                    if kind=='connected':connected=event['at']
                    elif kind=='headers':headers=event['at']
                    elif kind=='first':first=event['at']
                    elif kind=='done':done=event
                    else:raise ValueError('worker event')
                if len(buffer)>EVENT_CAP:raise ValueError('event bound')
                if done is not None:
                    try:proc.wait(timeout=max(.001,deadline-time.monotonic()))
                    except subprocess.TimeoutExpired:reason='request_deadline';done=None
                    break
    finally:
        stopped=stop_group(proc.pid,proc,limits,whole)
        if not proc.stdin.closed:proc.stdin.close()
        proc.stdout.close()
    if not stopped or proc.returncode is None:raise RuntimeError('writer stop unconfirmed')
    root=Path(arg['root']);bodypath=root/('%03d.body.private'%index);hp=root/('%03d.headers.private.json'%index);fp=root/('%03d.framing.private'%index)
    body=member(bodypath,limits.body_bytes) if bodypath.exists() else None;header=member(hp,limits.header_diagnostic_bytes) if hp.exists() else None;framing_evidence=member(fp,limits.header_diagnostic_bytes) if fp.exists() else None
    observed=body['bytes'] if body else 0;exact=bool(done is not None and done['observed']==observed and 0<=done['probe']<=1 and done['consumed']==observed+done['probe'] and body is not None and done['body_sha256']==body['sha256'] and (header is None and done['headers_sha256'] is None or header is not None and done['headers_sha256']==header['sha256']) and (framing_evidence is None and done['framing_sha256'] is None or framing_evidence is not None and done['framing_sha256']==framing_evidence['sha256']))
    evidence_complete=bool(exact and framing_evidence is not None and done['framing_evidence_complete'] is True)
    diagnostics=strict_json(read_regular(str(hp),limits.header_diagnostic_bytes)) if header else None
    status=diagnostics['status'] if diagnostics else None;framing=diagnostics['framing'] if diagnostics else 'unknown';declared=diagnostics['declared'] if diagnostics else None;outcome=done['outcome'] if done else reason;probe=done['probe'] if exact else 0
    end=time.monotonic()
    complete=bool(exact and outcome=='framed_complete' and probe==0 and stopped and proc.returncode==0 and body is not None and header is not None and (framing!='chunked' or evidence_complete) and sum(p['bytes'] for p in (header,framing_evidence) if p is not None)<=limits.header_diagnostic_bytes and connected is not None and headers is not None and connected<=start+limits.connection_s and headers<=start+limits.first_body_s and (observed==0 or first is not None and first<=start+limits.first_body_s) and end<=deadline)
    return {'start':start,'end':end,'connected_at':connected,'headers_at':headers,'first_body_at':first,'http_status':status,'framing':framing,'declared':declared,'outcome':outcome,'body':body,'headers':header,'framing_evidence':framing_evidence,'framing_evidence_complete':evidence_complete,'observed_bytes':observed,'overflow_probe_bytes':probe,'consumed_upper':observed+probe if exact else limits.body_bytes+1,'consumption_exact':exact,'worker_group':proc.pid,'worker_exit_code':proc.returncode,'worker_exit_confirmed':proc.returncode is not None,'worker_group_stop_confirmed':stopped,'attempt_accounting_complete':complete,'HTTP200_candidate':bool(complete and status==200 and observed>0)}

def controller(arg):
    plan,limits=check_context(arg);p=strict_json(plan.source_bytes);root=Path(arg['root']);begin=arg['begin'];integer(len(encode(arg)),1,ARG_CAP)
    write_new(root/'roster.private.json',plan.source_bytes);batches=[]
    for b in p['batches']:
        i=b['batch_index'];path=root/('%03d.request.private'%i);write_new(path,b['request_body'].encode('ascii'))
        batches.append({'batch_index':i,'row_indices':b['row_indices'],'request':member(path,limits.request_bytes),'status':'unattempted'})
    initial={'protocol':PROTOCOL,'study_id':plan.study_id,'plan_sha256':plan.sha256,'fixture':arg['fixture'],'limits':asdict(limits),'begin':begin,'claims':claims(),'batches':batches}
    write_new(root/'initial.private.json',encode(initial));records=[];halt=None;last=None;groups=[]
    for i,b in enumerate(batches):
        row=dict(b)
        if halt:row['reason']=halt
        else:
            if last is not None:time.sleep(max(0,min(last+limits.start_spacing_s-time.monotonic(),begin+limits.processing_s-time.monotonic())))
            if time.monotonic()>=begin+limits.processing_s:row['reason']='launch_cutoff';halt='launch_cutoff'
            else:
                result=request(arg,i,begin,limits);last=result['start'];groups.append(result['worker_group']);row.update(status='attempted',request_index=len(groups)-1,**result)
                halt=None if result['attempt_accounting_complete'] else 'halted_after_incomplete'
        records.append(row);write_new(root/('%03d.batch.private.json'%i),encode(row))
    attempted=[r for r in records if r['status']=='attempted']
    summary={**initial,'batches':records,'processing_elapsed':time.monotonic()-begin,'attempts':len(attempted),'retained_bytes':sum(r['observed_bytes'] for r in attempted),'overflow_probe_bytes':sum(r['overflow_probe_bytes'] for r in attempted),'consumption_upper':sum(r['consumed_upper'] for r in attempted),'HTTP200_candidates':sum(r['HTTP200_candidate'] for r in attempted),'candidate_complete':len(attempted)==17 and all(r['attempt_accounting_complete'] for r in attempted),'worker_groups':groups}
    write_new(root/'controller_summary.private.json',encode(summary));emit({'event':'finished','summary_sha256':sha(encode(summary))})

def public(summary,complete,registered=(),limits=DEFAULT):
    known=bool(summary);attempted=summary['attempts'] if known else len(registered)
    return {'rows':65,'TRAIN_rows':41,'DEV_rows':24,'metadata_unknown_rows':4,'nominal_ENZ_rows':47,'nominal_12Z_rows':14,'batches':17,'attempted_batches':attempted,'unattempted_batches':17-attempted,'accounting_known':known,'accounting_complete_batches':sum(r.get('attempt_accounting_complete',False) for r in summary.get('batches',[])),'HTTP200_candidate_batches':summary.get('HTTP200_candidates',0),'qualified_batches':summary.get('HTTP200_candidates',0) if complete else 0,'retained_response_bytes':summary['retained_bytes'] if known else None,'overflow_probe_bytes':summary['overflow_probe_bytes'] if known else None,'consumption_upper':summary['consumption_upper'] if known else attempted*(limits.body_bytes+1),'whole_complete':complete,'claims':claims()}

def member_cap(name,limits):
    fixed={'roster.private.json':PLAN_CAP,'initial.private.json':65536,'controller_summary.private.json':ARG_CAP,'receipt.private.json':16384,'public_aggregate.json':16384,'manifest.private.json':65536}
    if name in fixed:return fixed[name]
    if re.fullmatch(r'00[0-9]|01[0-6]',name.split('.')[0]):
        for suffix,cap in (('.request.private',limits.request_bytes),('.batch.private.json',16384),('.body.private',limits.body_bytes),('.headers.private.json',limits.header_diagnostic_bytes),('.framing.private',limits.header_diagnostic_bytes)):
            if name.endswith(suffix):return cap
    raise ValueError('closed member name')

def collect_internal(plan,out_dir,authority,endpoint,limits,fixture):
    begin=time.monotonic()
    if type(plan) is not Plan or type(plan.sha256) is not str or type(plan.study_id) is not str:raise ValueError('strict plan object')
    validate_plan(plan.source_bytes)
    if validate_plan(plan.source_bytes)!=plan:raise ValueError('immutable plan')
    checked_limits(asdict(limits),fixture)
    if not fixture:authority.check(plan)
    elif not plan.study_id.startswith('invented-'):raise ValueError('invented only')
    root=Path(out_dir)
    if type(out_dir) is not str or not root.is_absolute() or str(root)!=out_dir or root.parent.resolve()!=root.parent:raise ValueError('canonical output')
    root.mkdir(mode=0o700);proc=None;groups=[];registered=[];summary={};finish=None;reason='incomplete';controller_stopped=request_stopped=False;manifest_sha=receipt_sha=None
    arg={'plan':plan.source_bytes.decode('utf8'),'root':str(root),'begin':begin,'fixture':fixture,'limits':asdict(limits),'endpoint':endpoint,'authority':asdict(authority) if authority else None}
    payload=encode(arg);integer(len(payload),1,ARG_CAP)
    try:
        proc=spawn('--controller');os.set_blocking(proc.stdin.fileno(),False);os.set_blocking(proc.stdout.fileno(),False);pending=payload;buffer=b''
        while time.monotonic()<begin+limits.processing_s:
            readable,writable,_=select.select([proc.stdout],[proc.stdin] if pending else [],[],.05)
            if writable:pending=pending[os.write(proc.stdin.fileno(),pending):]
            if readable:
                chunk=os.read(proc.stdout.fileno(),8192)
                if not chunk:break
                buffer+=chunk
                while b'\n' in buffer:
                    line,buffer=buffer.split(b'\n',1)
                    if len(line)>EVENT_CAP:raise ValueError('outer event cap')
                    event=strict_json(line)
                    if event['event']=='worker_group':
                        fields(event,('event','batch_index','pid'));pid=integer(event['pid'],1,2**31-1);index=integer(event['batch_index'],0,16)
                        if pid in groups or index!=len(groups) or len(groups)>=17:raise ValueError('distinct ordered fixed worker groups')
                        groups.append(pid);registered.append({'batch_index':index,'worker_group':pid});pending+=b'G'
                    elif event['event']=='finished':fields(event,('event','summary_sha256'));finish=hashtext(event['summary_sha256'])
                    else:raise ValueError('outer event')
                if len(buffer)>EVENT_CAP:raise ValueError('outer event cap')
            if finish is not None:
                try:proc.wait(timeout=max(.001,begin+limits.processing_s-time.monotonic()))
                except subprocess.TimeoutExpired:reason='deadline'
                break
        if finish is not None and proc.returncode==0 and time.monotonic()<begin+limits.processing_s:
            raw=read_regular(str(root/'controller_summary.private.json'),ARG_CAP)
            if sha(raw)!=finish:raise ValueError('controller summary pin')
            summary=strict_json(raw)
            if summary['worker_groups']!=groups or summary['plan_sha256']!=plan.sha256 or summary['processing_elapsed']>limits.processing_s:raise ValueError('registered group/source timing summary')
        else:reason='deadline' if time.monotonic()>=begin+limits.processing_s else 'controller_failed'
    except Exception:summary={};reason='controller_failed'
    finally:
        if proc is not None:
            request_stopped=all([stop_group(pid,None,limits,begin+limits.whole_s) for pid in groups])
            controller_stopped=stop_group(proc.pid,proc,limits,begin+limits.whole_s)
            if not proc.stdin.closed:proc.stdin.close()
            proc.stdout.close()
    complete=bool(summary.get('candidate_complete') is True and controller_stopped and request_stopped and time.monotonic()<begin+limits.whole_s)
    reason='complete' if complete else 'group_stop_unconfirmed' if not controller_stopped or not request_stopped else reason
    receipt={'protocol':PROTOCOL,'study_id':plan.study_id,'plan_sha256':plan.sha256,'complete':False,'reason':'finalization_failed','fixture':fixture,'limits':asdict(limits),'begin':begin,'elapsed_s':time.monotonic()-begin,'controller_exit_code':proc.returncode if proc else None,'controller_group_stop_confirmed':controller_stopped,'request_groups_stop_confirmed':request_stopped,'registered_attempts':registered,'controller_summary_sha256':finish if summary else None,'result_manifest_sha256':None,'claims':claims()}
    try:
        # Saved aggregate remains provisional; only a normal returned result can promote it.
        owned=write_new(root/'receipt.private.json',encode(receipt));write_new(root/'public_aggregate.json',encode(public(summary,False,registered,limits)))
        receipt.update(complete=complete,reason=reason,elapsed_s=time.monotonic()-begin)
        if receipt['elapsed_s']>=limits.whole_s:receipt.update(complete=False,reason='deadline');complete=False
        # Own exclusive inode only; never replace unrelated output.
        finalize_receipt(root/'receipt.private.json',owned,receipt)
        if summary:
            expected={'roster.private.json','initial.private.json','controller_summary.private.json','receipt.private.json','public_aggregate.json'}|{f'{i:03d}.{s}' for i in range(17) for s in ('request.private','batch.private.json')}
            for row in summary['batches']:
                if row['status']=='attempted':
                    for k in ('body','headers','framing_evidence'):
                        if row[k] is not None:expected.add(row[k]['name'])
            actual={p.name for p in root.iterdir()}
            if actual!=expected:raise ValueError('exact output membership')
            pins=[member(root/n,member_cap(n,limits)) for n in sorted(expected)]
            write_new(root/'manifest.private.json',encode({'protocol':PROTOCOL,'members':pins}));manifest_sha=sha(read_regular(str(root/'manifest.private.json'),65536));receipt_sha=sha(read_regular(str(root/'receipt.private.json'),16384))
        if time.monotonic()>=begin+limits.whole_s:complete=False;reason='deadline'
    except Exception:
        complete=False;reason='finalization_failed'
        if 'owned' in locals():
            try:finalize_receipt(root/'receipt.private.json',owned,dict(receipt,complete=False,reason=reason,elapsed_s=time.monotonic()-begin))
            except Exception:pass
    returned=time.monotonic()
    return {'protocol':PROTOCOL,'complete':complete,'reason':reason,'begin':begin,'returned_at':returned,'elapsed_s':returned-begin,'manifest_sha256':manifest_sha,'receipt_sha256':receipt_sha,'controller_group_stop_confirmed':controller_stopped,'request_groups_stop_confirmed':request_stopped,'registered_attempts':registered,'public_aggregate':public(summary,complete,registered,limits)}

def collect(plan,out_dir,authority):
    if type(authority) is not Authority:raise ValueError('separate production authority')
    return collect_internal(plan,out_dir,authority,ENDPOINT,DEFAULT,False)
def collect_fixture(plan,out_dir,endpoint,limits):
    check_context({'plan':plan.source_bytes.decode('utf8'),'fixture':True,'limits':asdict(limits),'endpoint':endpoint,'authority':None})
    return collect_internal(plan,out_dir,None,endpoint,limits,True)

if __name__=='__main__':
    try:
        raw=sys.stdin.buffer.readline(ARG_CAP+1)
        if not raw.endswith(b'\n') or len(raw)>ARG_CAP:raise ValueError('argument bound')
        arg=strict_json(raw)
        if sys.argv[-1]=='--controller':controller(arg)
        elif sys.argv[-1]=='--worker':worker(arg)
        else:raise ValueError('private mode only')
    except BaseException:sys.exit(1)

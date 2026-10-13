"""ROOT execution driver: authored only, not invoked during source preparation."""
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import shlex
import stat
import subprocess
import sys
import time

CAP=1024*1024

def need(v,why):
    if not v:raise ValueError(why)
def pin(b):return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def object_read(raw):
    def pairs(items):
        out={}
        for k,v in items:need(k not in out,'duplicate_key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in()).throw(ValueError('nonfinite')))
def directory(path):
    need(type(path)is str and path.startswith('/') and all(p not in('','.','..')for p in path.split('/')[1:]),'absolute_path');fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.split('/')[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
        return fd
    except BaseException:os.close(fd);raise

def read_private(path,cap=CAP):
    p=Path(path);fd=directory(str(p.parent))
    try:
        f=os.open(p.name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            s=os.fstat(f);need(stat.S_ISREG(s.st_mode)and stat.S_IMODE(s.st_mode)==0o400 and s.st_nlink==1 and s.st_uid==os.geteuid()and s.st_size<=cap,'private_file');raw=b''
            while len(raw)<=cap:
                part=os.read(f,min(65536,cap+1-len(raw)))
                if not part:break
                raw+=part
            e=os.fstat(f);need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(e.st_dev,e.st_ino,e.st_size,e.st_mtime_ns,e.st_ctime_ns)and len(raw)==s.st_size,'private_changed');return raw
        finally:os.close(f)
    finally:os.close(fd)

def exclusive(path,raw):
    need(type(raw)is bytes and len(raw)<=5*CAP,'private_cap');p=Path(path);fd=directory(str(p.parent))
    try:
        f=os.open(p.name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=fd)
        try:
            view=memoryview(raw)
            while view:
                n=os.write(f,view);need(n>0,'short_write');view=view[n:]
            os.fchmod(f,0o400);os.fsync(f)
        finally:os.close(f)
        os.fsync(fd)
    finally:os.close(fd)
    need(read_private(str(p),5*CAP)==raw,'private_readback')

def transport(argv,payload,timeout=1130):
    """Bounded observed-stream custody; uncertainty never retries or authorizes."""
    need(type(payload)is bytes and len(payload)<=8192 and type(timeout)in(int,float)and math.isfinite(timeout)and timeout>0,'transport_args');begin=time.monotonic();p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);sel=selectors.DefaultSelector();state={k:dict(data=bytearray(),hash=hashlib.sha256(),count=0,eof=False)for k in('stdout','stderr')};timed=False;error=None
    try:
        for name in state:sel.register(getattr(p,name),selectors.EVENT_READ,name)
        try:p.stdin.write(payload);p.stdin.flush()
        except Exception as e:error=type(e).__name__
        finally:
            try:p.stdin.close()
            except Exception as e:error=error or type(e).__name__
        deadline=begin+timeout;drain_end=None
        while sel.get_map():
            now=time.monotonic()
            if now>=deadline and not timed:
                timed=True;p.kill();drain_end=now+5
            if timed and now>=drain_end:break
            for key,_ in sel.select(min(1,max(0,(drain_end if timed else deadline)-now))):
                block=os.read(key.fileobj.fileno(),65536);s=state[key.data]
                if not block:s['eof']=True;sel.unregister(key.fileobj);continue
                s['count']+=len(block);s['hash'].update(block);s['data'].extend(block[:max(0,CAP-len(s['data']))])
        try:code=p.wait(timeout=5 if timed else max(0,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            p.kill();timed=True
            try:code=p.wait(timeout=5)
            except subprocess.TimeoutExpired:code=None
    except Exception as e:
        error=type(e).__name__
        try:p.kill()
        except OSError:pass
        try:code=p.wait(timeout=5)
        except subprocess.TimeoutExpired:code=None
    finally:
        sel.close()
        for name in state:getattr(p,name).close()
    streams={k:dict(retained_hex=bytes(s['data']).hex(),retained_pin=pin(bytes(s['data'])),original_bytes=s['count'],original_sha256=s['hash'].hexdigest(),truncated=s['count']>len(s['data']),complete_observation=s['eof'])for k,s in state.items()}
    return dict(code=code,timeout=timed,exception=error,streams=streams,elapsed_s=time.monotonic()-begin,no_retry=True)

REMOTE=r'''import time
REMOTE_BEGIN=time.monotonic()
import sys,json,os,hashlib,types,stat
r=json.loads(sys.stdin.buffer.read(8193));assert set(r)=={'index','config_spec','config_pin','custody_source','control_directory','preparation_return','remote_python'} and type(r['index'])is int and 0<=r['index']<7
pin=lambda b:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def read(s):
 assert type(s)is dict and set(s)=={'path','pin','mode'} and s['mode']==256
 names=s['path'].split('/');assert names[0]=='' and all(x not in('','.','..')for x in names[1:]);d=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for n in names[1:-1]:q=os.open(n,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);os.close(d);d=q
  f=os.open(names[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d)
  try:
   a=os.fstat(f);assert stat.S_ISREG(a.st_mode)and stat.S_IMODE(a.st_mode)==256 and a.st_nlink==1 and a.st_uid==os.geteuid() and a.st_size<=1048576
   b=b''
   while len(b)<=1048576:
    part=os.read(f,min(65536,1048577-len(b)))
    if not part:break
    b+=part
   e=os.fstat(f);assert(a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns,a.st_ctime_ns)==(e.st_dev,e.st_ino,e.st_size,e.st_mtime_ns,e.st_ctime_ns)and len(b)==a.st_size and pin(b)==s['pin'];return b
  finally:os.close(f)
 finally:os.close(d)
def load(n,b,p):
 assert n not in sys.modules;m=types.ModuleType(n);m.__file__=p;m.__package__='';sys.modules[n]=m;exec(compile(b,p,'exec'),m.__dict__);return m
rawconfig=read(r['config_spec']);config=json.loads(rawconfig);assert json.dumps(config,sort_keys=True,separators=(',',':'),allow_nan=False).encode()==rawconfig and pin(rawconfig)==r['config_pin'];assert r['remote_python']==config['runtime']['python'];assert time.monotonic()+960<=min(config['whole_begin']+7200,config['lease_deadline']);assert r['control_directory']!=config['store_directory']
raw=[]
for role,names in(('v6',('secure_io','vendor_inventory','generated_source','metadata_finder','source_binding','systemd_adapter')),('harness',('audit_journal','audit_control','audit_deployment'))):
 source=config['sources'][role]
 for n in names:raw.append((n,read(dict(path=source['directory']+'/'+n+'.py',pin=source['files'][n+'.py'],mode=256)),source['directory']+'/'+n+'.py'))
mods={n:load(n,b,p)for n,b,p in raw};io=mods['secure_io'];controlfd=io.directory(r['control_directory'])
try:
 try:os.stat('setup_failure.private.json',dir_fd=controlfd,follow_symlinks=False)
 except FileNotFoundError:pass
 else:raise ValueError('setup_failure_terminal')
finally:os.close(controlfd)
prepared_raw=io.canonical(r['preparation_return']);assert io.read_file(dict(path=r['control_directory']+'/preparation_receipt.private.json',pin=pin(prepared_raw),mode=256))==prepared_raw
sb=mods['source_binding'];ctl=mods['audit_control'];helper=load('root_audit_run_custody',read(r['custody_source']),r['custody_source']['path']);hooks_module=load('root_seven_audit_hooks',io.read_file(config['hooks_source']),config['hooks_source']['path']);hooks=hooks_module.make_hooks(config,io=io,sb=sb,clock=time.monotonic,expected_config_pin=r['config_pin']);sd=mods['systemd_adapter'].Systemd(config['commands']);dep=mods['audit_deployment'].Deployment(config,hooks,sd);dep.verify()
ac=helper.schema(io.read_file(config['hooks_config']));assert ac['last_return_evidence_directory']!=r['control_directory'] and ac['last_return_evidence_directory']!=config['store_directory'];bundle=helper.dynamic_bundle(config,r['index'],io,hooks_module.known_root_return);bundle_spec=helper.durable(io,r['control_directory'],'stage_%02d_bundle.private.json'%r['index'],bundle,cap=1048576);journal=mods['audit_journal'].Journal(config['store_directory']);actual=None;metadata=None
try:
 actual=ctl.run_stage(config,r['index'],bundle_spec,journal,dep,clock=time.monotonic)
 if actual['status']!='complete':raise ValueError('audit_stage_incomplete')
 metadata=helper.complete_closure(config,r['index'],actual,journal,io,sd.inspect,bundle_spec=bundle_spec)
 assert time.monotonic()<=min(config['whole_begin']+7400,config['lease_deadline']);root_spec=helper.durable(io,ac['last_return_evidence_directory'],'stage_%02d.private.json'%r['index'],metadata)
 assert time.monotonic()<=min(config['whole_begin']+7400,config['lease_deadline']);print(json.dumps(dict(schema='root-marked-seven-audit-run-return-v2',status='complete',index=r['index'],actual_return=actual,root_evidence_spec=root_spec,bundle_spec=bundle_spec,inventory=metadata['inventory'],elapsed_s=time.monotonic()-REMOTE_BEGIN,no_retry=True),sort_keys=True))
except Exception as e:
 failure=dict(schema='root-marked-seven-audit-run-return-v2',status='incomplete',index=r['index'],actual_return=actual,metadata=metadata,reason=str(e)[:256],exception=type(e).__name__,elapsed_s=time.monotonic()-REMOTE_BEGIN,no_retry=True)
 try:helper.durable(io,r['control_directory'],'stage_%02d_root_failure.private.json'%r['index'],failure,cap=1048576)
 except Exception:failure['failure_retention_unverified']=True
 print(json.dumps(failure,sort_keys=True));sys.exit(1)
finally:journal.close()
'''

def main(argv=None):
    args=sys.argv[1:]if argv is None else argv;need(len(args)==4,'arguments_index_preparation_runner_output');index=int(args[0]);need(0<=index<7,'index');prepraw=read_private(args[1]);runnerraw=read_private(args[2]);outer=object_read(prepraw);runner=object_read(runnerraw);need(type(outer)is dict and type(outer.get('exit'))is int and outer['exit']==0 and type(outer.get('stdout'))is str,'preparation_transport');prep=object_read(outer['stdout'].encode())
    need(prep['schema']=='root-marked-seven-audit-control-preparation-v2' and prep['status']=='prepared' and prep['no_audit_invoked']is True,'preparation')
    need(set(runner)=={'schema','ssh_host','remote_python','custody_source'}and runner['schema']=='root-seven-audit-runner-authority-v2' and type(runner['ssh_host'])is str and runner['ssh_host']=='instancebaseline' and type(runner['remote_python'])is str and runner['remote_python'].startswith('/'),'runner_authority')
    request=dict(index=index,config_spec=prep['config_spec'],config_pin=prep['config_canonical_pin'],custody_source=runner['custody_source'],control_directory=prep['control_directory'],preparation_return=prep,remote_python=runner['remote_python']);payload=canonical(request);need(len(payload)<=8192,'request_cap');output=Path(args[3]);intent=str(output)+'.intent.private.json';need(not output.exists(),'existing_output');exclusive(intent,canonical(dict(schema='root-seven-audit-run-intent-v2',index=index,request=request,preparation_pin=pin(prepraw),runner_authority_pin=pin(runnerraw),driver_source_pin=pin(Path(__file__).read_bytes()),no_retry=True)))
    try:answer=transport(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',runner['ssh_host'],shlex.quote(runner['remote_python'])+' -I -B -c '+shlex.quote(REMOTE)],payload)
    except Exception as e:answer=dict(code=None,timeout=False,exception=type(e).__name__,streams={},elapsed_s=None,no_retry=True)
    exclusive(str(output),canonical(dict(schema='root-seven-audit-run-transport-v2',index=index,**answer)))
    need(answer['code']==0 and answer['timeout']is False and answer['exception']is None and all(s['complete_observation']is True and s['truncated']is False for s in answer['streams'].values()),'transport_uncertain_no_retry')
    returned=object_read(bytes.fromhex(answer['streams']['stdout']['retained_hex']));need(returned['status']=='complete' and returned['index']==index and returned['no_retry']is True,'remote_incomplete_no_retry');print(json.dumps(returned,sort_keys=True));return 0

if __name__=='__main__':raise SystemExit(main())

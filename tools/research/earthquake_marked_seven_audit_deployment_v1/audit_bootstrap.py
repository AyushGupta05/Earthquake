"""One independent audit child. Inline positively pinned launcher starts clock."""
import time
if 'SOURCE_BEGIN' not in globals():SOURCE_BEGIN=time.monotonic()
import hashlib
import json
import os
import stat
import sys
import types

def need(ok,reason):
    if not ok:raise ValueError(reason)
def read(path,cap,sha):
    need(type(path)is str and path.startswith('/') and all(x not in ('','.','..') for x in path.split('/')[1:]),'bootstrap_path')
    names=path.split('/')[1:];d=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for name in names[:-1]:
            n=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);os.close(d);d=n
        f=os.open(names[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d)
        try:
            s=os.fstat(f);need(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode)==0o400 and s.st_nlink==1 and s.st_size<=cap,'bootstrap_file')
            out=[];count=0
            while True:
                b=os.read(f,min(1048576,cap+1-count))
                if not b:break
                count+=len(b);need(count<=cap,'bootstrap_cap');out.append(b)
            e=os.fstat(f);need((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(e.st_dev,e.st_ino,e.st_size,e.st_mtime_ns,e.st_ctime_ns),'bootstrap_changed');raw=b''.join(out)
        finally:os.close(f)
    finally:os.close(d)
    need(hashlib.sha256(raw).hexdigest()==sha,'bootstrap_hash');return raw
def load(name,raw,path):
    need(name not in sys.modules,'bootstrap_alias_collision');m=types.ModuleType(name);m.__file__=path;m.__package__='';sys.modules[name]=m;exec(compile(raw,path,'exec'),m.__dict__);return m
def main():
    need(len(sys.argv)==3,'bootstrap_arguments');frame_raw=read(sys.argv[1],256*1024,sys.argv[2]);frame=json.loads(frame_raw)
    need(frame['schema']=='marked-seven-audit-launch-v1','launch_schema');c=frame['config'];request=frame['request'];modules={}
    groups=(('v6',('secure_io','vendor_inventory','generated_source','metadata_finder','source_binding','systemd_adapter')),('harness',('audit_journal','audit_control','audit_deployment')))
    all_raw=[]
    for role,names in groups:
        source=c['sources'][role]
        for name in names:
            p=source['files'][name+'.py'];path=source['directory']+'/'+name+'.py';raw=read(path,16*1024*1024,p['sha256']);need(len(raw)==p['bytes'],'bootstrap_source_size');all_raw.append((name,raw,path))
    for name,raw,path in all_raw:modules[name]=load(name,raw,path)
    io=modules['secure_io'];need(io.json_read(frame_raw)==frame and io.canonical(frame)==frame_raw,'bootstrap_canonical')
    expected=frame['expected_config_pin'];need(io.pin(io.canonical(c))==expected and request['config_pin']==expected,'bootstrap_config_pin')
    j=modules['audit_journal'].Journal(c['store_directory'])
    try:
        try:
            # Hash and execute ROOT hooks only from its independently bound source.
            raw=io.read_file(c['hooks_source']);hooks_module=load('root_seven_audit_hooks',raw,c['hooks_source']['path'])
            hooks=hooks_module.make_hooks(c,io=io,sb=modules['source_binding'],clock=time.monotonic,expected_config_pin=expected)
            systemd=modules['systemd_adapter'].Systemd(c['commands'])
            dep=modules['audit_deployment'].Deployment(c,hooks,systemd)
            result=modules['audit_deployment'].execute(request,j,dep,source_begin=SOURCE_BEGIN)
        except Exception as exc:
            result=dict(schema='marked-seven-audit-child-failure-v1',status='incomplete',stage=request['stage']['index'],config_pin=expected,reason=str(exc)[:256],exception=type(exc).__name__,no_retry=True)
            try:j.object(request['stage']['index'],'child_failure.json',result)
            except Exception:result['retention_unverified']=True
        print(json.dumps(dict(status=result['status'],stage=request['stage']['index'],no_retry=True)))
        return 0 if result['status']=='complete' else 1
    finally:j.close()
if __name__=='__main__':raise SystemExit(main())

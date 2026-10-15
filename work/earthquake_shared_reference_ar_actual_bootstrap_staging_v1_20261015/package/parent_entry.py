"""Positively held ROOT parent CLI; never captures a new scientific clock."""
import hashlib
import json
import os
import stat
import sys
import types


def read(spec,cap=2*1024*1024):
    path=spec['path'];p=spec['pin']
    if not(path.startswith('/') and all(x not in ('','.','..') for x in path.split('/')[1:])):raise ValueError('path')
    if type(p['bytes'])is not int or not 0<p['bytes']<=cap or spec['mode']!=0o400:raise ValueError('spec')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.split('/')[1:-1]:
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=child
        f=os.open(path.split('/')[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            before=os.fstat(f)
            if not(stat.S_ISREG(before.st_mode) and stat.S_IMODE(before.st_mode)==0o400 and before.st_nlink==1 and before.st_uid==os.geteuid() and before.st_size==p['bytes']):raise ValueError('readonly_member')
            with os.fdopen(f,'rb',closefd=False) as stream:raw=stream.read(cap+1)
            after=os.fstat(f)
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):raise ValueError('changed_read')
        finally:os.close(f)
    finally:os.close(fd)
    if len(raw)!=p['bytes'] or hashlib.sha256(raw).hexdigest()!=p['sha256']:raise ValueError('pin')
    return raw


def main(args):
    path,sha,size=args;request_raw=read(dict(path=path,pin=dict(bytes=int(size),sha256=sha),mode=0o400));request=json.loads(request_raw)
    if os.path.abspath(__file__)!=request['entry_source_spec']['path']:raise ValueError('entry_identity')
    read(request['entry_source_spec'])
    root_raw=read(request['root_spec']);held=json.loads(root_raw)
    if request['expected_root_pin']!=request['root_spec']['pin'] or request['bootstrap_spec']!=held['launch']['bootstrap']:raise ValueError('held_subject')
    boot_raw=read(request['bootstrap_spec'],16*1024*1024)
    bootstrap=types.ModuleType('parent_bootstrap_reader');bootstrap.__file__=request['bootstrap_spec']['path']
    exec(compile(boot_raw,bootstrap.__file__,'exec'),bootstrap.__dict__)
    specs=held['launch']['modules']
    if set(specs)!=set(bootstrap.MODULES):raise ValueError('module_inventory')
    # ALL support bytes are positively held before ANY support import.
    raw={n:bootstrap.read(specs[n],16*1024*1024)for n in bootstrap.MODULES}
    primitive_spec=held['launch']['primitive_source'];primitive_raw=bootstrap.read(primitive_spec,16*1024*1024)
    stop_raw=read(request['stop_source_spec']);parent_raw=read(request['parent_source_spec'])
    modules={n:bootstrap.load(n,raw[n],specs[n]['path'])for n in bootstrap.MODULES}
    modules['root_primitives']=bootstrap.load('root_primitives',primitive_raw,primitive_spec['path'])
    modules['parent_stop']=bootstrap.load('parent_stop',stop_raw,request['stop_source_spec']['path'])
    modules['parent_orchestrator']=bootstrap.load('parent_orchestrator',parent_raw,request['parent_source_spec']['path'])
    modules['parent_entry']=sys.modules[__name__]
    io=modules['secure_io'];io.need(io.canonical(io.json_read(root_raw))==root_raw and io.canonical(io.json_read(request_raw))==request_raw,'canonical_entry')
    result=modules['parent_orchestrator'].run(request,held,modules)
    print(json.dumps(result,sort_keys=True,separators=(',',':')),flush=True)
    return 0 if result['status']=='complete'else 2


if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))

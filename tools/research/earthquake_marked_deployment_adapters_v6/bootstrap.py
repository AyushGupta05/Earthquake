"""Sole-stage bootstrap. Source clock is captured by the positively bound inline launcher."""
import time
if 'SOURCE_BEGIN' not in globals(): SOURCE_BEGIN=time.monotonic()
import hashlib
import json
import os
import stat
import sys
import types


def _need(ok,why):
    if not ok:raise ValueError(why)


def _read(path,cap,sha=None):
    _need(type(path) is str and path.startswith('/') and all(x not in ('','.','..') for x in path.split('/')[1:]),'bootstrap_path')
    names=path.split('/')[1:];d=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for name in names[:-1]:
            n=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);os.close(d);d=n
        f=os.open(names[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d)
        try:
            s=os.fstat(f);_need(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode)==0o400 and s.st_size<=cap,'bootstrap_file')
            chunks=[];size=0
            while True:
                b=os.read(f,min(1048576,cap+1-size))
                if not b:break
                chunks.append(b);size+=len(b);_need(size<=cap,'bootstrap_cap')
            raw=b''.join(chunks)
        finally:os.close(f)
    finally:os.close(d)
    _need(sha is None or hashlib.sha256(raw).hexdigest()==sha,'bootstrap_hash');return raw


def _load(name,raw,path):
    _need(name not in sys.modules,'bootstrap_alias_collision')
    m=types.ModuleType(name);m.__file__=path;m.__package__='';sys.modules[name]=m;exec(compile(raw,path,'exec'),m.__dict__);return m


def main():
    _need(len(sys.argv)==3 and len(sys.argv[2])==64,'sole_stage_arguments')
    launch_raw=_read(sys.argv[1],2*1024*1024,sys.argv[2]);launch=json.loads(launch_raw)
    _need(launch['schema']=='marked-stage-launch-v1','launch_schema');config=launch['config'];request=launch['request']
    own=config['sources']['adapters'];root=own['directory']
    # Pin every module before importing even the adapter helpers. Full closed
    # inventory and manifest checks are repeated by source_binding before science.
    names=('secure_io','vendor_inventory','generated_source','metadata_finder','source_binding','comparison_join','systemd_adapter','deployment')
    raws={}
    for n in names:
        p=own['files'][n+'.py'];raws[n]=_read(root+'/'+n+'.py',16*1024*1024,p['sha256']);_need(len(raws[n])==p['bytes'],'adapter_size')
    modules={}
    for n in names:modules[n]=_load(n,raws[n],root+'/'+n+'.py')
    io=modules['secure_io'];io.need(io.json_read(launch_raw)==launch,'launch_json')
    expected_config_pin=launch['expected_deployment_config_pin']
    io.need(io.pin(io.canonical(config))==expected_config_pin,'deployment_config_pin')
    systemd=modules['systemd_adapter'].Systemd(config['commands'])
    def no_authority(*_):raise ValueError('ROOT authority not loaded')
    dep=modules['deployment'].Deployment(config,no_authority,systemd);dep.request=request;dep.stage=request['stage'];dep.science_begin=SOURCE_BEGIN
    dep.verify(request['gate'])
    authority_raw=io.read_file(config['authority_source']);authority=_load('root_marked_authority',authority_raw,config['authority_source']['path'])
    io.need(callable(authority.make_validator),'root_validator_factory')
    dep.authority=authority.make_validator(config,io=io,source_binding=modules['source_binding'],clock=time.monotonic,expected_deployment_config_pin=expected_config_pin)
    io.need(callable(dep.authority),'root_verify_callback')
    parent=modules['source_binding'].load_group(config['sources']['parent'],dep.raw['parent'],('controller','child'),'marked_child_'+str(os.getpid()))
    store=io.Store(config['store_directory'],config['storage_limit_bytes'])
    try:
        result=parent['child'].execute(request,store,dep,source_begin=SOURCE_BEGIN)
        print(json.dumps(dict(status=result['status'],index=request['stage']['index'],no_retry=True)))
        return 0 if result['status']=='complete' else 1
    finally:store.close()

if __name__=='__main__':raise SystemExit(main())

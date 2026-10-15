"""Positively pinned sole-stage bootstrap; captures source clock before imports."""
import time
if 'SOURCE_BEGIN'not in globals():SOURCE_BEGIN=time.monotonic()
import hashlib
import json
import os
import stat
import sys
import types

MODULES=('secure_io','vendor_inventory','generated_source','metadata_finder',
         'source_binding','systemd_adapter','codec','bridge','runtime_adapter',
         'control','child','journal','projection','comparator_population','root_glue')

def need(ok,why):
    if not ok:raise ValueError(why)

def read(spec,cap):
    need(type(spec)is dict and set(spec)=={'path','pin','mode'}and type(spec['mode'])is int and spec['mode']==0o400,'bootstrap_spec')
    path=spec['path'];pin=spec['pin']
    need(type(path)is str and path.startswith('/')and all(n not in('','.','..')for n in path.split('/')[1:]),'bootstrap_path')
    need(type(pin)is dict and set(pin)=={'bytes','sha256'}and type(pin['bytes'])is int and 0<pin['bytes']<=cap and type(pin['sha256'])is str and len(pin['sha256'])==64 and all(c in'0123456789abcdef'for c in pin['sha256']),'bootstrap_pin')
    d=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for n in path.split('/')[1:-1]:
            q=os.open(n,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);os.close(d);d=q
        f=os.open(path.split('/')[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d)
        try:
            s=os.fstat(f);need(stat.S_ISREG(s.st_mode)and stat.S_IMODE(s.st_mode)==0o400 and s.st_nlink==1 and s.st_uid==os.geteuid()and s.st_size==pin['bytes'],'bootstrap_member')
            out=[];size=0
            while True:
                b=os.read(f,min(1024*1024,cap+1-size))
                if not b:break
                out.append(b);size+=len(b);need(size<=cap,'bootstrap_cap')
            raw=b''.join(out)
        finally:os.close(f)
    finally:os.close(d)
    need(len(raw)==pin['bytes']and hashlib.sha256(raw).hexdigest()==pin['sha256'],'bootstrap_hash');return raw

def load(name,raw,path):
    need(name not in sys.modules,'bootstrap_alias_collision')
    module=types.ModuleType(name);module.__file__=path;module.__package__='';sys.modules[name]=module
    exec(compile(raw,path,'exec'),module.__dict__);return module

def main():
    need('LAUNCH_PATH'in globals()and'LAUNCH_PIN'in globals(),'independent_inline_launch_subject')
    launch_raw=read(dict(path=LAUNCH_PATH,pin=LAUNCH_PIN,mode=0o400),512*1024);launch=json.loads(launch_raw)
    need(type(launch)is dict and set(launch)=={'schema','request','root_spec'}and launch['schema']=='root-L-stage-bootstrap-v1','bootstrap_launch_schema')
    root_spec=launch['root_spec'];root_raw=read(root_spec,2*1024*1024);held=json.loads(root_raw)
    need(held['schema']=='root-held-L-composition-v1','root_schema')
    specs=held['launch']['modules'];need(type(specs)is dict and set(specs)==set(MODULES),'module_inventory')
    # Read/hash ALL bootstrap support bytes before executing ANY helper.
    raw={name:read(specs[name],16*1024*1024)for name in MODULES}
    primitive_spec=held['launch']['primitive_source'];primitive_raw=read(primitive_spec,16*1024*1024)
    modules={name:load(name,raw[name],specs[name]['path'])for name in MODULES}
    io=modules['secure_io'];io.need(io.canonical(io.json_read(launch_raw))==launch_raw and io.canonical(io.json_read(root_raw))==root_raw,'canonical_bootstrap')
    primitive_module=load('root_primitives',primitive_raw,primitive_spec['path']);modules['root_primitives']=primitive_module
    io.need(callable(getattr(primitive_module,'make_primitives',None)),'mandatory_root_primitive_factory')
    primitives,custody=primitive_module.make_primitives(held,expected_root_pin=root_spec['pin'],root_spec=root_spec,modules=modules,source_begin=SOURCE_BEGIN,clock=time.monotonic)
    journal=modules['journal'].Journal(held['launch']['store_directory'])
    try:
        systemd=modules['systemd_adapter'].Systemd(held['launch']['commands'])
        result=modules['root_glue'].execute_child(held,launch['request'],expected_pin=root_spec['pin'],root_spec=root_spec,modules=modules,primitives=primitives,custody=custody,journal=journal,systemd=systemd,source_begin=SOURCE_BEGIN)
        print(json.dumps(dict(schema='root-L-bootstrap-summary-v1',stage=launch['request']['stage']['index'],status=result['status'],no_retry=True),sort_keys=True,separators=(',',':')))
        return 0 if result['status']=='complete'else 1
    finally:journal.close()

if __name__=='__main__':raise SystemExit(main())

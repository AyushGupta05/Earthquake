"""Closed source/runtime verification and imports from positively hashed bytes."""
import hashlib
import importlib
import importlib.machinery
import sysconfig
from contextlib import contextmanager
import os
import stat
import sys
import types
from pathlib import Path
import secure_io as io
import vendor_inventory as vi

COUNTS={'processor':32,'gaussian':34,'native':22,'parent':32}


def inventory(root,allow_links=False):
    """Do not traverse links. ROOT directory and every actual subdirectory are opened nofollow."""
    fd=io.directory(root);files={};links={};dirs=set()
    def visit(d,prefix):
        for n in os.listdir(d):
            io.parts(n);name=prefix+n;s=os.stat(n,dir_fd=d,follow_symlinks=False)
            if stat.S_ISREG(s.st_mode):files[name]=(s.st_size,stat.S_IMODE(s.st_mode))
            elif stat.S_ISDIR(s.st_mode):
                dirs.add(name);sub=os.open(n,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d)
                try:visit(sub,name+'/')
                finally:os.close(sub)
            elif stat.S_ISLNK(s.st_mode) and allow_links:links[name]=os.readlink(n,dir_fd=d)
            else:raise ValueError('unexpected_tree_node')
    try:visit(fd,'')
    finally:os.close(fd)
    return files,links,dirs


def source(spec,role,check):
    io.need(type(spec) is dict and set(spec)=={'directory','files','manifest','upload_manifest'},'source_spec')
    io.need(type(spec['files']) is dict and len(spec['files'])==(COUNTS[role] if role in COUNTS else len(spec['files'])) and 1<=len(spec['files'])<=128,'source_count')
    files,links,dirs=inventory(spec['directory']);expected=set(spec['files'])
    for n in expected:io.parts(n)
    if spec['upload_manifest'] is not None:
        upload=spec['upload_manifest'];io.need(upload['path']==spec['directory']+'/parent_upload_manifest.private.json' and upload['mode']==0o400,'upload_role')
        value=io.json_read(io.read_file(upload,4*1024*1024));io.need(value==spec['files'],'upload_binding');expected.add('parent_upload_manifest.private.json')
    expected_dirs={str(p) for n in expected for p in Path(n).parents if str(p)!='.'}
    io.need(set(files)==expected and not links and dirs==expected_dirs,'source_closed')
    raw_py={}
    for name,p in spec['files'].items():
        check();raw=io.read_file(dict(path=spec['directory']+'/'+name,pin=p,mode=0o400),16*1024*1024)
        if name.endswith('.py'):raw_py[name]=raw
    check();manifest=spec['manifest'];io.need(manifest['path'].startswith(spec['directory']+'/') and manifest['mode']==0o400,'manifest_role')
    relative=manifest['path'][len(spec['directory'])+1:];io.need(relative in spec['files'] and manifest['pin']==spec['files'][relative],'manifest_binding')
    raw_manifest=io.read_file(manifest);m=io.json_read(raw_manifest)
    entries=m.get('files',m.get('members'))
    if type(entries) is list:
        io.need(len({x['path'] for x in entries})==len(entries),'duplicate_manifest_path')
        entries={x['path']:{k:x[k] for k in ('bytes','sha256')} for x in entries}
    io.need(type(entries) is dict and entries and all(k in spec['files'] and v==spec['files'][k] for k,v in entries.items()),'first_clean_members')
    omissions={relative}
    if role in ('parent','adapters'):omissions.add('ALLOWED_PUBLIC_FILES.txt')
    if role=='gaussian':omissions.add('SHA256SUMS')
    io.need(set(spec['files'])-set(entries)<=omissions,'unmanifested_source')
    return raw_py


def hashed_file(path,pin,mode,check):
    """Stream runtime members without putting a large library into memory."""
    io.pin_check(pin,2**34);names=io.parts(path,True);d=io.directory('/'+'/'.join(names[:-1]));f=None
    try:
        f=os.open(names[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d);s=os.fstat(f)
        io.need(stat.S_ISREG(s.st_mode) and stat.S_IMODE(s.st_mode)==mode and s.st_size==pin['bytes'],'runtime_file')
        h=hashlib.sha256();count=0
        while True:
            check();b=os.read(f,1024*1024)
            if not b:break
            h.update(b);count+=len(b);io.need(count<=pin['bytes'],'runtime_growth')
        end=os.fstat(f)
        io.need((s.st_size,s.st_mtime_ns,s.st_ctime_ns)==(end.st_size,end.st_mtime_ns,end.st_ctime_ns) and count==pin['bytes'] and h.hexdigest()==pin['sha256'],'runtime_hash')
    finally:
        if f is not None:os.close(f)
        os.close(d)


def runtime(spec,check):
    keys={'directory','manifest','symlinks','critical','python','versions','regular_mode','vendor_inventory'}
    io.need(type(spec) is dict and set(spec)==keys and spec['regular_mode']==0o444,'runtime_spec')
    manifest=io.json_read(io.read_file(spec['manifest'],4*1024*1024));members=manifest['files']
    io.need(type(members) is dict and len(members)==10112 and type(spec['critical']) is dict and len(spec['critical'])==10,'runtime_counts')
    linkdoc=io.json_read(io.read_file(spec['symlinks'],1024*1024));links=linkdoc['symlinks']
    io.need(type(links) is dict and len(links)==4,'symlink_count')
    venv=spec['directory']+'/venv';actual,actual_links,dirs=inventory(venv,True)
    actual={'venv/'+k:v for k,v in actual.items()};actual_links={'venv/'+k:v for k,v in actual_links.items()}
    io.need(set(actual)==set(members) and actual_links==links,'runtime_closed')
    allowed_files=set();allowed_dirs={str(Path(venv).resolve())}
    for name,p in members.items():
        io.need(io.parts(name)[0]=='venv','runtime_path');check();path=spec['directory']+'/'+name
        hashed_file(path,p,spec['regular_mode'],check);allowed_files.add(str(Path(path).resolve()))
        allowed_dirs.update(str(q.resolve()) for q in Path(path).parents if q==Path(venv) or Path(venv) in q.parents)
    for path,p in spec['critical'].items():
        io.need(type(p) is dict and set(p)=={'bytes','sha256','mode'} and type(p['mode']) is int and 0<=p['mode']<=0o777,'critical_spec')
        hashed_file(path,{k:p[k] for k in ('bytes','sha256')},p['mode'],check);allowed_files.add(str(Path(path).resolve()))
    for name in links:
        io.need(io.parts(name)[0]=='venv','link_name');resolved=str(Path(spec['directory']+'/'+name).resolve(strict=True))
        io.need(resolved in allowed_files or resolved in allowed_dirs,'link_destination')
    io.need(spec['python'].startswith(venv+'/') and str(Path(spec['python']).resolve(strict=True)) in allowed_files,'python_binding');check()
    vi.load(spec['vendor_inventory'],check)


def load_group(spec,raw_py,names,prefix):
    """Execute only the bytes just hashed; temporary aliases cannot bind ambient code."""
    previous={n:sys.modules.get(n) for n in names};loaded={}
    try:
        for n in names:
            key=n+'.py';io.need(key in raw_py and io.pin(raw_py[key])==spec['files'][key],'module_pin')
            unique=prefix+'_'+n;io.need(unique not in sys.modules,'module_once')
            path=spec['directory']+'/'+key;module=types.ModuleType(unique);module.__file__=path;module.__package__=''
            sys.modules[unique]=module;sys.modules[n]=module;exec(compile(raw_py[key],path,'exec'),module.__dict__);loaded[n]=module
    finally:
        for name,old in previous.items():
            if old is None:sys.modules.pop(name,None)
            else:sys.modules[name]=old
    return loaded


def cross_copies(raw):
    for ref,role,name in [('reference/gaussian_operator.py','gaussian','gaussian_operator.py'),('reference/reference_core.py','gaussian','reference_core.py'),('reference/marked_native.py','native','marked_native.py'),('reference/native_packet_io.py','native','packet_io.py')]:
        io.need(raw['processor'][ref]==raw[role][name],'frozen_reference_mismatch')


def interpreter_check(spec):
    io.need(Path(sys.executable).resolve(strict=True)==Path(spec['python']).resolve(strict=True)
            and sys.flags.isolated==1 and sys.dont_write_bytecode is True,'running_interpreter_binding')


@contextmanager
def vendor_guard(spec,source_specs,extra_sources,check):
    """Permit vendor/dependency execution only from the hashed runtime tree.

    Python's own stdlib/builtin/frozen modules remain interpreter authority. The
    allowed stdlib excludes site/dist-packages. Custom meta-path/path loaders do
    not acquire execution authority from a matching version string.
    """
    interpreter_check(spec)
    members=io.json_read(io.read_file(spec['manifest'],4*1024*1024))['files']
    allowed={str(Path(spec['directory']+'/'+n).resolve(strict=True)):dict(pin=p,mode=spec['regular_mode']) for n,p in members.items()}
    for n,p in spec['critical'].items():allowed[str(Path(n).resolve(strict=True))]=dict(pin={k:p[k] for k in ('bytes','sha256')},mode=p['mode'])
    supplemental=vi.load(spec['vendor_inventory'],check)
    for path,binding in supplemental.items():
        io.need(path not in allowed or allowed[path]==binding,'ambiguous_vendor_binding')
        allowed[path]=binding
    source_files={str(Path(s['directory']+'/'+n).resolve(strict=True)) for s in source_specs.values() for n in s['files'] if n.endswith('.py')}
    for s in extra_sources:
        io.read_file(s);source_files.add(str(Path(s['path']).resolve(strict=True)))
    stdlib=Path(sysconfig.get_path('stdlib')).resolve(strict=True)
    allowed_dirs={str(p) for n in allowed for p in Path(n).parents}
    def standard(path):
        p=Path(path)
        return (p==stdlib or stdlib in p.parents) and not any(x in ('site-packages','dist-packages') for x in p.parts)
    def origin_ok(origin,rehash=False):
        if origin in ('built-in','frozen',None):return
        real=str(Path(origin).resolve(strict=True))
        io.need(real in allowed or standard(real),'import_outside_verified_runtime')
        if rehash and real in allowed:hashed_file(real,allowed[real]['pin'],allowed[real]['mode'],check)
        return (real,allowed[real]) if real in allowed else None
    for name,module in list(sys.modules.items()):
        io.need(not any(name==v or name.startswith(v+'.') for v in ('numpy','scipy','torch')),'preloaded_vendor')
        file=vars(module).get('__file__') if isinstance(module,types.ModuleType) else None
        if file and str(Path(file).resolve()) not in source_files:
            real=str(Path(file).resolve(strict=True))
            # A current path/hash cannot prove what a preinstalled loader already
            # executed (including timestamp-valid pyc). No scientific vendor may
            # acquire authority by being preloaded before this guard.
            io.need(standard(real),'preloaded_unverified_dependency')
    class Guard:
        def find_spec(self,fullname,path=None,target=None):
            check()
            spec=importlib.machinery.BuiltinImporter.find_spec(fullname)
            if spec is None:spec=importlib.machinery.FrozenImporter.find_spec(fullname)
            if spec is None:spec=importlib.machinery.PathFinder.find_spec(fullname,path,target)
            if spec is None:raise ModuleNotFoundError(fullname)
            binding=origin_ok(spec.origin,True)
            if spec.origin not in ('built-in','frozen',None):
                io.need(type(spec.loader) in (importlib.machinery.SourceFileLoader,importlib.machinery.SourcelessFileLoader,importlib.machinery.ExtensionFileLoader),'unbound_import_loader')
                if binding and type(spec.loader) is importlib.machinery.SourceFileLoader:
                    spec.loader=vi.VerifiedSourceLoader(fullname,spec.origin,binding[0],binding[1],check)
                elif binding and type(spec.loader) is importlib.machinery.SourcelessFileLoader:
                    spec.loader=vi.VerifiedBytecodeLoader(fullname,spec.origin,binding[0],binding[1],check)
            if spec.submodule_search_locations:
                for p in spec.submodule_search_locations:
                    real=str(Path(p).resolve(strict=True));io.need(real in allowed_dirs or standard(real),'import_namespace_outside_runtime')
            return spec
    guard=Guard();sys.meta_path.insert(0,guard)
    try:yield
    finally:
        # The persistent child guard lives until interpreter teardown, when the
        # import machinery itself may already be cleared. No scientific work
        # can resume during that teardown. Ordinary context exit stays strict.
        if not sys.is_finalizing():
            io.need(sys.meta_path and sys.meta_path[0] is guard,'import_guard_changed')
            sys.meta_path.pop(0)


def scientific_modules(specs,raw,runtime_spec,prefix,*,extra_sources,check):
    cross_copies(raw)
    # Keep the guard alive for lazy imports during later optimizer/scoring calls.
    # Each fresh contained child binds scientific modules exactly once.
    global _ACTIVE_VENDOR_GUARD
    io.need('_ACTIVE_VENDOR_GUARD' not in globals(),'scientific_bind_once')
    _ACTIVE_VENDOR_GUARD=vendor_guard(runtime_spec,specs,extra_sources,check)
    _ACTIVE_VENDOR_GUARD.__enter__()
    import numpy as np
    import scipy
    import torch
    expected=runtime_spec['versions']
    actual=dict(python='.'.join(map(str,sys.version_info[:3])),numpy=np.__version__,scipy=scipy.__version__,torch=str(torch.__version__))
    io.need(actual==expected,'vendor_versions');torch.set_num_threads(1)
    io.need(torch.get_num_threads()==1 and not torch.cuda.is_initialized(),'cpu_only')
    native=load_group(specs['native'],raw['native'],('marked_native','packet_io'),prefix+'_native')
    gaussian=load_group(specs['gaussian'],raw['gaussian'],('gaussian_operator','reference_core'),prefix+'_gaussian')
    proc=load_group(specs['processor'],raw['processor'],('numeric_state','processor'),prefix+'_processor')
    io.need(native['packet_io'].m is native['marked_native'] and proc['processor'].ns is proc['numeric_state'],'transitive_alias')
    io.need(all(x.np is np for x in (native['marked_native'],native['packet_io'],gaussian['gaussian_operator'],gaussian['reference_core'],proc['processor'],proc['numeric_state'])),'numpy_identity')
    io.need(gaussian['gaussian_operator'].torch is torch and proc['processor'].torch is torch,'torch_identity')
    return native,gaussian,proc

"""One ROOT-pinned PyTorch helper; never a general dynamic-source allowlist."""
import importlib.machinery
import os
from pathlib import Path
import re
import stat
import sys
import types
import tempfile
import secure_io as io
import vendor_inventory as vi

MODULE='_remote_module_non_scriptable'
BASENAME=MODULE+'.py'
SOURCES={'instantiator':'torch.distributed.nn.jit.instantiator','template':'torch.distributed.nn.jit.templates.remote_module_template'}
MAX_BODY=65536


def validate(spec,allowed,check):
    keys={'schema','module','basename','body_pin','generator_sources','temp_parent','owner_uid','directory_mode','file_mode','max_depth'}
    io.need(type(spec) is dict and set(spec)==keys and spec['schema']=='torch-nonscriptable-remote-helper-v1','generated_schema')
    io.need(spec['module']==MODULE and spec['basename']==BASENAME and spec['max_depth']==1 and type(spec['max_depth']) is int,'generated_identity')
    io.pin_check(spec['body_pin'],MAX_BODY);io.need(spec['body_pin']['bytes']>0,'generated_empty')
    io.need(type(spec['owner_uid']) is int and spec['owner_uid']==os.geteuid() and spec['directory_mode']==0o700 and type(spec['directory_mode']) is int
            and type(spec['file_mode']) is int and spec['file_mode'] in (0o600,0o640,0o644,0o660,0o664),'generated_modes')
    parent=spec['temp_parent'];io.need(type(parent) is dict and set(parent)=={'path','uid','mode'} and type(parent['uid']) is int and parent['uid']>=0
            and type(parent['mode']) is int and parent['mode'] in (0o700,0o1700,0o1777),'generated_parent_spec')
    fd=io.directory(parent['path'])
    try:
        s=os.fstat(fd);io.need(s.st_uid==parent['uid'] and stat.S_IMODE(s.st_mode)==parent['mode'],'generated_parent')
    finally:os.close(fd)
    sources=spec['generator_sources'];io.need(type(sources) is dict and set(sources)==set(SOURCES),'generated_sources')
    for name,file in sources.items():
        check();real=str(Path(file['path']).resolve(strict=True));io.need(real==file['path'] and real in allowed and allowed[real]==dict(pin=file['pin'],mode=file['mode']),'generated_source_inventory')
        io.read_file(file,MAX_BODY)
    check()


def _loaded_generator(spec):
    loaded={}
    for role,name in SOURCES.items():
        module=sys.modules.get(name);io.need(isinstance(module,types.ModuleType),'generated_generator_not_loaded')
        meta=vars(module);file=spec['generator_sources'][role];loader=meta.get('__loader__');ms=meta.get('__spec__')
        io.need(type(loader) is vi.VerifiedSourceLoader and ms is not None and ms.loader is loader and ms.name==name
                and meta.get('__file__')==file['path'] and loader.verified_path==file['path'] and loader.binding==dict(pin=file['pin'],mode=file['mode']),'generated_generator_execution')
        loaded[role]=module
    module=loaded['instantiator'];path=vars(module).get('INSTANTIATED_TEMPLATE_DIR_PATH');temporary=vars(module).get('_TEMP_DIR')
    io.need(type(path) is str and type(temporary) is tempfile.TemporaryDirectory and temporary.name==path,'generated_temp_identity')
    return path


def read_bound(spec,fullname,origin,check):
    """Verify opened private ancestry and exact bytes; compile does not reopen paths."""
    check();io.need(fullname==MODULE and type(origin) is str,'generated_import_name')
    io.parts(origin,True);parent=spec['temp_parent'];directory=_loaded_generator(spec)
    io.need(os.path.dirname(origin)==directory and os.path.basename(origin)==BASENAME and os.path.dirname(directory)==parent['path'],'generated_path')
    leaf=os.path.basename(directory);io.need(re.fullmatch('tmp[a-z0-9_]{8}',leaf),'generated_temp_basename')
    parentfd=io.directory(parent['path']);directoryfd=filefd=None
    try:
        ps=os.fstat(parentfd);io.need(ps.st_uid==parent['uid'] and stat.S_IMODE(ps.st_mode)==parent['mode'],'generated_parent')
        directoryfd=os.open(leaf,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parentfd);ds=os.fstat(directoryfd)
        io.need(ds.st_uid==spec['owner_uid'] and stat.S_IMODE(ds.st_mode)==spec['directory_mode'],'generated_private_directory')
        filefd=os.open(BASENAME,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directoryfd);before=os.fstat(filefd)
        io.need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==spec['owner_uid'] and stat.S_IMODE(before.st_mode)==spec['file_mode']
                and before.st_size==spec['body_pin']['bytes'],'generated_regular_file')
        chunks=[];size=0
        while True:
            check();block=os.read(filefd,min(8192,MAX_BODY+1-size))
            if not block:break
            size+=len(block);io.need(size<=MAX_BODY,'generated_body_cap');chunks.append(block)
        after=os.fstat(filefd);ds_after=os.fstat(directoryfd)
        io.need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
                and ds_after.st_uid==spec['owner_uid'] and stat.S_IMODE(ds_after.st_mode)==spec['directory_mode'],'generated_changed')
        raw=b''.join(chunks);io.need(io.pin(raw)==spec['body_pin'],'generated_body_pin');check();return raw
    finally:
        if filefd is not None:os.close(filefd)
        if directoryfd is not None:os.close(directoryfd)
        os.close(parentfd)


class PinnedGeneratedLoader(importlib.machinery.SourceFileLoader):
    def __init__(self,name,path,spec,check):super().__init__(name,path);self.binding=spec;self.check=check
    def get_code(self,fullname):
        raw=read_bound(self.binding,fullname,self.path,self.check)
        return self.source_to_code(raw,self.path)


def bind(module_spec,fullname,spec,check):
    io.need(fullname==MODULE and module_spec.name==MODULE and type(module_spec.loader) is importlib.machinery.SourceFileLoader
            and module_spec.submodule_search_locations is None,'generated_module_spec')
    # Validate now and again when get_code obtains the exact bytes to compile.
    read_bound(spec,fullname,module_spec.origin,check)
    module_spec.loader=PinnedGeneratedLoader(fullname,module_spec.origin,spec,check)
    return module_spec

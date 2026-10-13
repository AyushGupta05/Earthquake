"""Copied reviewed public custody/import/resource helpers; no scientific imports."""
from pathlib import Path
import hashlib
import json
import math
import os
import selectors
import stat
import subprocess
import sys
import time
import importlib
import custody as c

def file_spec(v,cap):
 c.need(type(v)is dict and set(v)=={'path','pin'}and type(v['path'])is str and len(v['path'])<=4096 and Path(v['path']).is_absolute(),'file_spec');c.pin_checked(v['pin'],cap)
 return v

def source_spec(v,count=None):
 c.need(type(v)is dict and set(v)=={'directory','files'}and type(v['directory'])is str and Path(v['directory']).is_absolute()and type(v['files'])is dict and 1<=len(v['files'])<=128,'source_spec')
 if count is not None:c.need(len(v['files'])==count,'source_members')
 for n,pin in v['files'].items():c.name_checked(n);c.pin_checked(pin,c.MAX_MEMBER)

def managed_process(args,timeout,popen=subprocess.Popen,clock=time.monotonic):
 buffers={k:bytearray()for k in('stdout','stderr')};hashes={k:hashlib.sha256()for k in buffers};counts={k:0 for k in buffers};caps={'stdout':65536,'stderr':131072};proc=None;selector=None;code=None;interrupted=False;failure=None
 try:
  start=clock();proc=popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE);selector=selectors.DefaultSelector()
  for k,pipe in(('stdout',proc.stdout),('stderr',proc.stderr)):os.set_blocking(pipe.fileno(),False);selector.register(pipe,selectors.EVENT_READ,k)
  while selector.get_map():
   if clock()-start>timeout:interrupted=True;proc.terminate();break
   for key,_ in selector.select(.1):
    b=os.read(key.fileobj.fileno(),65536)
    if not b:selector.unregister(key.fileobj);continue
    k=key.data;hashes[k].update(b);counts[k]+=len(b);buffers[k].extend(b[:max(0,caps[k]-len(buffers[k]))])
  try:code=proc.wait(timeout=5)
  except subprocess.TimeoutExpired:interrupted=True;proc.kill();code=proc.wait(timeout=5)
 except Exception as error:
  interrupted=True;failure=type(error).__name__
  if proc is not None:
   try:proc.terminate()
   except Exception:pass
   try:code=proc.wait(timeout=5)
   except Exception:
    try:proc.kill();code=proc.wait(timeout=5)
    except Exception:pass
 finally:
  if selector is not None:
   try:selector.close()
   except Exception:interrupted=True
  if proc is not None:
   for pipe in(proc.stdout,proc.stderr):
    try:pipe.close()
    except Exception:interrupted=True
 streams={k:dict(original_bytes=counts[k],original_sha256=hashes[k].hexdigest(),retained_bytes=len(buffers[k]),truncated=counts[k]>len(buffers[k]),complete_observation=not interrupted)for k in buffers}
 answer=dict(code=code,timeout=interrupted,raw={k:bytes(v)for k,v in buffers.items()},streams=streams)
 if failure is not None:answer['exception_type']=failure
 return answer

def post_checked(text):
 c.need(type(text)is str and len(text.encode())<=16384,'post_cap');props={}
 for line in text.splitlines():
  if '='in line:k,v=line.split('=',1);c.need(k not in props,'post_duplicate');props[k]=v
 c.need(props.get('ActiveState')in('inactive','failed')and props.get('ControlGroup')=='','owned_cleanup_unverified');return props
def read_raw(path,cap):
 path=Path(path);c.need(path.is_file()and not path.is_symlink(),'raw_file')
 with path.open('rb')as f:raw=f.read(cap+1)
 c.need(len(raw)<=cap,'raw_cap');return raw

def source_verify(spec,check):
 directory=Path(spec['directory']);c.need(directory.is_dir()and not directory.is_symlink(),'source_directory');actual={p.name for p in directory.iterdir()if p.is_file()};extra='parent_upload_manifest.private.json';allowed=set(spec['files'])
 if extra in actual:
  metadata=directory/extra;c.need(metadata.stat().st_mode&0o777==0o400 and c.strict_json(read_raw(metadata,1048576),1048576)==spec['files'],'source_upload_manifest');allowed=allowed|{extra}
 c.need(actual==allowed and all(p.is_file()and not p.is_symlink()for p in directory.iterdir()),'source_membership')
 for n,pin in spec['files'].items():check();c.read_file(directory/n,pin,c.MAX_MEMBER)

def load_spec(spec,cap):return c.read_file(spec['path'],spec['pin'],cap)

def runtime_verify(runtime,check):
 root=Path(runtime['prefix_directory']);c.need(root.is_dir()and not root.is_symlink()and(root/'venv').is_dir()and not(root/'venv').is_symlink(),'runtime_directory');raw=load_spec(runtime['manifest'],4194304);m=c.strict_json(raw,4194304);c.need(hashlib_sha(canonical(m))==runtime['canonical_sha256']and type(m.get('files'))is dict and len(m['files'])==10112,'runtime_manifest')
 links=c.strict_json(load_spec(runtime['symlinks'],65536),65536);c.need(type(links)is dict and set(links)=={'schema','prefix_directory','links'}and links['schema']=='root-prefix-runtime-symlink-manifest-v1'and links['prefix_directory']==runtime['prefix_directory']and type(links['links'])is dict and len(links['links'])<=128,'runtime_link_manifest')
 for n,target in links['links'].items():c.need(type(n)is str and 0<len(n)<=4096 and Path(n).parts[0]=='venv'and len(Path(n).parts)>1 and not Path(n).is_absolute()and '..'not in Path(n).parts and type(target)is str and 0<len(target)<=4096,'runtime_link_path')
 actual=set();seen_links={}
 for path in(root/'venv').rglob('*'):
  check();name=str(path.relative_to(root));mode=path.lstat().st_mode
  if stat.S_ISLNK(mode):seen_links[name]=os.readlink(path)
  elif stat.S_ISREG(mode):actual.add(name)
  else:c.need(stat.S_ISDIR(mode),'runtime_unexpected_entry')
 c.need(actual==set(m['files'])and seen_links==links['links'],'runtime_membership');allowed_files=set();derived_dirs={(root/'venv').resolve(strict=True)}
 for n,pin in m['files'].items():
  c.need(type(n)is str and Path(n).parts[0]=='venv'and not Path(n).is_absolute()and '..'not in Path(n).parts,'runtime_path');check();c.hash_file(root/n,pin,0o444);allowed_files.add((root/n).resolve(strict=True))
  directory=(root/n).parent
  while directory!=root:derived_dirs.add(directory.resolve(strict=True));directory=directory.parent
 critical=set()
 for n,pin in runtime['critical_files'].items():check();c.hash_file(n,pin,int(pin['mode'],8));critical.add(Path(n).resolve(strict=True))
 for n in seen_links:
  check();resolved=(root/n).resolve(strict=True);c.need(resolved in allowed_files or resolved in derived_dirs or resolved in critical,'runtime_link_target')

def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode('utf8')

def hashlib_sha(v):return __import__('hashlib').sha256(v).hexdigest()

def import_bound(module,directory):
 expected=Path(directory)/ (module+'.py')
 if module in sys.modules:c.need(Path(sys.modules[module].__file__).resolve()==expected.resolve(),'ambient_module_collision')
 loaded=importlib.import_module(module);c.need(Path(loaded.__file__).resolve()==expected.resolve(),'import_identity');return loaded

def tick(begin):
 now=time.monotonic();c.need(type(begin)in(int,float)and math.isfinite(begin)and 0<=begin<=now and now-begin<=900,'replay_deadline')

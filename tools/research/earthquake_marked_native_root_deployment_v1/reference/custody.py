"""Stdlib private durable custody; no model, network or scientific authority."""
from pathlib import Path
import hashlib
import io
import json
import math
import os
import stat
import zipfile

MAX_MEMBER=16*1024*1024
MAX_TOTAL=64*1024*1024
MAX_MEMBERS=64

def need(ok,reason):
 if not ok:raise ValueError(reason)

def name_checked(name):
 need(type(name)is str and 0<len(name)<=128 and name not in('.','..')and '/'not in name and '\\'not in name,'member_name')
 return name

def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def pin_checked(value,cap):
 need(type(value)is dict and set(value)=={'bytes','sha256'}and type(value['bytes'])is int and 0<=value['bytes']<=cap and type(value['sha256'])is str and len(value['sha256'])==64 and all(c in'0123456789abcdef'for c in value['sha256']),'pin')

def strict_json(raw,cap=MAX_MEMBER):
 need(type(raw)is bytes and len(raw)<=cap,'json_cap')
 def obj(pairs):
  out={}
  for k,v in pairs:need(k not in out,'duplicate_key');out[k]=v
  return out
 def integer(s):
  need(len(s.lstrip('-'))<=1024,'integer_cap');return int(s)
 value=json.loads(raw.decode('utf8'),object_pairs_hook=obj,parse_int=integer,parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite_json')))
 pending=[(value,0)];n=0
 while pending:
  v,d=pending.pop();n+=1;need(n<=2_000_000 and d<=32,'json_structure_cap')
  if type(v)is dict:pending.extend((x,d+1)for x in v.values())
  elif type(v)is list:pending.extend((x,d+1)for x in v)
  elif type(v)is float:need(math.isfinite(v),'nonfinite_json')
 return value

def private_put(directory,name,value,cap=16777216):
 if type(cap) is not int or not 0<cap<=16777216:raise ValueError('private_payload_cap')
 if type(name) is not str or not name or name in ('.','..') or '/' in name or '\\' in name:raise ValueError('private_name')
 b=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode('utf8')
 if len(b)>cap:raise ValueError('private_payload_cap')
 directory_fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=directory_fd)
  with os.fdopen(fd,'wb')as f:os.fchmod(f.fileno(),0o400);f.write(b);f.flush();os.fsync(f.fileno())
  os.fsync(directory_fd)
 finally:os.close(directory_fd)

def make_output_directory(out):
 out.mkdir(mode=0o700)
 directory_fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(directory_fd)
 finally:os.close(directory_fd)

def bounded_stream(value):
 if value is None:value=b''
 if isinstance(value,str):value=value.encode('utf8',errors='replace')
 assert isinstance(value,bytes);original_bytes=len(value);digest=hashlib.sha256(value).hexdigest();text=value.decode('utf8',errors='replace');lo=0;hi=len(text)
 while lo<hi:
  middle=(lo+hi+1)//2
  if len(json.dumps(text[:middle],ensure_ascii=True).encode())<=61440:lo=middle
  else:hi=middle-1
 retained=text[:lo];return retained,{'original_bytes':original_bytes,'original_sha256':digest,'retained_serialized_bytes':len(json.dumps(retained,ensure_ascii=True).encode()),'truncated':lo<len(text),'decoding':'UTF8 replacement'}

def read_file(path,expected,cap,mode=0o400):
 pin_checked(expected,cap);path=Path(path)
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode)and st.st_mode&0o777==mode and st.st_size==expected['bytes'],'input_file')
  with os.fdopen(fd,'rb',closefd=False)as f:raw=f.read(cap+1)
  need(len(raw)<=cap and pin(raw)==expected,'input_pin');return raw
 finally:os.close(fd)

def hash_file(path,expected,mode,cap=2**34):
 pin_checked({k:expected[k]for k in('bytes','sha256')},cap);path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);need(stat.S_ISREG(st.st_mode)and st.st_mode&0o777==mode and st.st_size==expected['bytes'],'runtime_file');h=hashlib.sha256();count=0
  with os.fdopen(fd,'rb',closefd=False)as f:
   for b in iter(lambda:f.read(1048576),b''):h.update(b);count+=len(b);need(count<=cap,'runtime_cap')
  need(count==expected['bytes']and h.hexdigest()==expected['sha256'],'runtime_pin')
 finally:os.close(fd)

class Store:
 def __init__(self,directory,reserve_bytes=0,reserve_members=0):
  self.reserve_bytes=reserve_bytes;self.reserve_members=reserve_members
  self.directory=Path(directory);self.members=0;self.total=0
  for path in self.directory.iterdir():
   need(path.is_file()and not path.is_symlink()and path.stat().st_mode&0o777==0o400,'existing_output');self.members+=1;self.total+=path.stat().st_size
  need(self.members<=MAX_MEMBERS and self.total<=MAX_TOTAL,'existing_output_cap')
 def put(self,name,value,cap=MAX_MEMBER):
  name_checked(name);need(type(cap)is int and 0<cap<=MAX_MEMBER,'output_cap')
  raw=value if type(value)is bytes else(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode('utf8')
  need(len(raw)<=cap and self.members+1<=MAX_MEMBERS-self.reserve_members and self.total+len(raw)<=MAX_TOTAL-self.reserve_bytes,'output_cap')
  fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
  try:
   dest=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=fd)
   self.members+=1;self.total+=len(raw)
   with os.fdopen(dest,'wb')as f:os.fchmod(f.fileno(),0o400);f.write(raw);f.flush();os.fsync(f.fileno())
   os.fsync(fd)
  finally:os.close(fd)
  return pin(raw)
 def inventory(self,reserve=0):
  files={};total=0
  for p in self.directory.iterdir():
   name_checked(p.name);need(p.is_file()and not p.is_symlink()and p.stat().st_mode&0o777==0o400,'output_file')
   cap=8*1024*1024 if p.name.endswith('.npz')else MAX_MEMBER;need(p.stat().st_size<=cap,'output_member_cap')
   with p.open('rb')as f:raw=f.read(cap+1)
   need(len(raw)<=cap,'output_member_cap');total+=len(raw);files[p.name]=pin(raw)
  need(total+reserve<=MAX_TOTAL and len(files)+1<=MAX_MEMBERS,'output_closed_cap');return files,total


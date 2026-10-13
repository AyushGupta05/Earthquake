"""Bounded fd-relative storage; stdlib only, no scientific or resource authority."""
import fcntl
import hashlib
import json
import math
import os
import re
import stat
import uuid
import threading
from contextlib import contextmanager

CAP=2*1024*1024


def need(ok,why):
    if not ok: raise ValueError(why)


def pin(raw): return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def pin_check(p,cap=16*1024*1024):
    need(type(p) is dict and set(p)=={'bytes','sha256'} and type(p['bytes']) is int and 0<=p['bytes']<=cap
         and type(p['sha256']) is str and re.fullmatch('[0-9a-f]{64}',p['sha256']),'pin')


def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def json_read(raw,cap=16*1024*1024):
    need(type(raw) is bytes and len(raw)<=cap,'json_cap')
    def pairs(items):
        out={}
        for k,v in items: need(k not in out,'duplicate');out[k]=v
        return out
    def bad(_): raise ValueError('nonfinite')
    v=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad);pending=[(v,0)];n=0
    while pending:
        x,d=pending.pop();n+=1;need(d<=40 and n<=1000000,'json_structure')
        if type(x) is dict: pending.extend((a,d+1) for a in x.values())
        elif type(x) is list: pending.extend((a,d+1) for a in x)
        elif type(x) is float: need(math.isfinite(x),'nonfinite')
    return v


def parts(path,absolute=False):
    need(type(path) is str and 0<len(path)<=4096 and '\\' not in path and '\0' not in path,'path')
    need(path.startswith('/')==absolute,'absolute_path')
    v=path.split('/')[1:] if absolute else path.split('/')
    need(all(x not in ('','.','..') for x in v),'path_component');return v


def directory(path):
    """Open all absolute path components without following any symlink."""
    items=parts(path,True);fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for name in items:
            nxt=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=nxt
        return fd
    except BaseException: os.close(fd);raise


def read_at(fd,name,cap,mode=None,expected=None):
    need('/' not in name and name not in ('','.','..'),'file_name')
    f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
    try:
        before=os.fstat(f);need(stat.S_ISREG(before.st_mode) and before.st_size<=cap,'regular_file')
        if mode is not None: need(stat.S_IMODE(before.st_mode)==mode,'file_mode')
        data=[];total=0
        while True:
            b=os.read(f,min(1024*1024,cap+1-total))
            if not b: break
            data.append(b);total+=len(b);need(total<=cap,'file_cap')
        after=os.fstat(f);need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'file_changed')
        raw=b''.join(data)
        if expected is not None: pin_check(expected,cap);need(pin(raw)==expected,'file_pin')
        return raw
    finally: os.close(f)


def read_file(spec,cap=16*1024*1024):
    need(type(spec) is dict and set(spec)=={'path','pin','mode'},'file_spec');pin_check(spec['pin'],cap)
    names=parts(spec['path'],True);need(type(spec['mode']) is int and 0<=spec['mode']<=0o777,'mode')
    fd=directory('/'+'/'.join(names[:-1])) if len(names)>1 else os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try: return read_at(fd,names[-1],cap,spec['mode'],spec['pin'])
    finally: os.close(fd)


def file_sync(fd):
    getattr(os,'fdatasync',os.fsync)(fd)
    os.fsync(fd)  # include final readonly mode metadata, not only payload


class Store:
    """Fresh ROOT-owned private directory; real atomic process-shared storage."""
    def __init__(self,path,total_cap,member_cap=4096):
        need(type(total_cap) is int and 0<total_cap<=2**34 and type(member_cap) is int and 1<=member_cap<=4096,'store_caps')
        self.fd=directory(path);self.total_cap=total_cap;self.member_cap=member_cap;self.mutex=threading.Lock()
        self.lock=None
        try:
            need(stat.S_IMODE(os.fstat(self.fd).st_mode)==0o700,'store_directory_mode')
            self.lock=os.open('.store.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=self.fd)
            s=os.fstat(self.lock);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o600,'store_lock')
            file_sync(self.lock);os.fsync(self.fd)
        except BaseException:
            if self.lock is not None:os.close(self.lock)
            os.close(self.fd);self.fd=None;raise
    def close(self):
        if self.fd is not None:os.close(self.lock);os.close(self.fd);self.fd=None
    @contextmanager
    def locked(self):
        need(self.mutex.acquire(blocking=False),'store_busy')
        acquired=False
        try:
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True;yield
        finally:
            if acquired:fcntl.flock(self.lock,fcntl.LOCK_UN)
            self.mutex.release()
    def _names(self,name):
        names=parts(name);need(len(names)==2 and re.fullmatch('stage_[0-9]{2}',names[0]) and re.fullmatch('[a-z0-9_]+\\.json',names[1]),'store_name');return names
    def _stage(self,name,create=False):
        if create:
            try:os.mkdir(name,0o700,dir_fd=self.fd);os.fsync(self.fd)
            except FileExistsError:pass
        d=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.fd)
        if stat.S_IMODE(os.fstat(d).st_mode)!=0o700:
            os.close(d);raise ValueError('stage_mode')
        return d
    def _inventory(self):
        total=count=0
        for name in os.listdir(self.fd):
            if name=='.store.lock':continue
            need(re.fullmatch('stage_[0-9]{2}',name),'unexpected_store_member');d=self._stage(name)
            try:
                for member in os.listdir(d):
                    need(re.fullmatch('[a-z0-9_]+\\.json',member),'unfinished_or_unknown_member')
                    s=os.stat(member,dir_fd=d,follow_symlinks=False)
                    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o400 and s.st_size<=CAP,'stored_member')
                    total+=s.st_size;count+=1
            finally:os.close(d)
        need(total<=self.total_cap and count<=self.member_cap,'current_store_cap');return total,count
    def write(self,name,raw,replace=False,total_cap=None):
        names=self._names(name);need(type(raw) is bytes and len(raw)<=CAP and total_cap==self.total_cap,'write_cap')
        need(type(replace) is bool and (not replace or names[1]=='latest_update.json'),'replacement_role')
        with self.locked():
            total,count=self._inventory();d=self._stage(names[0],True)
            try:
                try:
                    old=os.stat(names[1],dir_fd=d,follow_symlinks=False)
                    need(stat.S_ISREG(old.st_mode) and old.st_nlink==1 and stat.S_IMODE(old.st_mode)==0o400,'existing_dest')
                    if not replace:raise FileExistsError(name)
                    exists=True
                except FileNotFoundError:exists=False
                # Charge the new temporary bytes too; replacement requires headroom.
                need(total+len(raw)<=self.total_cap and count+1<=self.member_cap,'temporary_store_cap')
                temp='.tmp-'+uuid.uuid4().hex
                f=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=d)
                try:
                    view=memoryview(raw)
                    while view:
                        n=os.write(f,view);need(n>0,'short_write');view=view[n:]
                    os.fchmod(f,0o400);file_sync(f)
                finally:os.close(f)
                if replace:os.replace(temp,names[1],src_dir_fd=d,dst_dir_fd=d)
                else:os.link(temp,names[1],src_dir_fd=d,dst_dir_fd=d,follow_symlinks=False);os.unlink(temp,dir_fd=d)
                os.fsync(d);os.fsync(self.fd)
                need(read_at(d,names[1],CAP,0o400)==raw,'write_readback');self._inventory()
                return dict(status='durable',pin=pin(raw))
            finally:os.close(d)
    def read(self,name):
        names=self._names(name)
        with self.locked():
            self._inventory();d=self._stage(names[0])
            try:return read_at(d,names[1],CAP,0o400)
            finally:os.close(d)
    def exists(self,name):
        names=self._names(name)
        with self.locked():
            self._inventory()
            try:d=self._stage(names[0])
            except FileNotFoundError:return False
            try:
                try:
                    s=os.stat(names[1],dir_fd=d,follow_symlinks=False);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o400,'stored_member');return True
                except FileNotFoundError:return False
            finally:os.close(d)

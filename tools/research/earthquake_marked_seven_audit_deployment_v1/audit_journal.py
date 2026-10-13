"""Separate immutable audit journal. The frozen 2 MiB Store is unchanged."""
import fcntl
import os
import re
import stat
import threading
import uuid
from contextlib import contextmanager
import secure_io as io

MEMBER=16*1024*1024
STAGE=64*1024*1024
RESERVE=1024*1024
CONTROL=512*1024
PAYLOAD=re.compile(r'(?:record|raw_report|wrapper_failure)_[0-9]{3}\.json\Z')
CONTROLS={'dispatch.json','bootstrap.json','claim.json','return.json','child_report.json','child_failure.json','manager_return.json','stop.json','post.json','post_after_stop.json','closed.json','late_or_failed.json'}

class Journal:
    def __init__(self,path):
        self.fd=io.directory(path);self.lock=None;self.mutex=threading.Lock()
        try:
            s=os.fstat(self.fd);io.need(s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700,'journal_owner_mode')
            self.lock=os.open('.audit.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=self.fd)
            s=os.fstat(self.lock);io.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o600,'journal_lock')
            io.file_sync(self.lock);os.fsync(self.fd)
        except BaseException:self.close();raise
    def close(self):
        if self.lock is not None:os.close(self.lock);self.lock=None
        if self.fd is not None:os.close(self.fd);self.fd=None
    @contextmanager
    def locked(self):
        io.need(self.mutex.acquire(blocking=False),'journal_busy');acquired=False
        try:
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB);acquired=True;yield
        finally:
            if acquired:fcntl.flock(self.lock,fcntl.LOCK_UN)
            self.mutex.release()
    def name(self,stage,name):
        io.need(type(stage)is int and 0<=stage<7 and type(name)is str and (name in CONTROLS or PAYLOAD.fullmatch(name)),'journal_name')
        return 'stage_%02d'%stage
    def stage(self,name,create=False):
        if create:
            try:os.mkdir(name,0o700,dir_fd=self.fd);os.fsync(self.fd)
            except FileExistsError:pass
        d=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.fd);s=os.fstat(d)
        if s.st_uid!=os.geteuid() or stat.S_IMODE(s.st_mode)!=0o700:os.close(d);raise ValueError('stage_owner_mode')
        return d
    def inventory(self):
        out={}
        for directory in os.listdir(self.fd):
            if directory=='.audit.lock':continue
            io.need(re.fullmatch('stage_0[0-6]',directory),'unexpected_stage');d=self.stage(directory)
            total=payload=controls=count=0
            try:
                for name in os.listdir(d):
                    self.name(int(directory[-2:]),name);s=os.stat(name,dir_fd=d,follow_symlinks=False)
                    ispayload=bool(PAYLOAD.fullmatch(name));cap=MEMBER if ispayload or name=='return.json' else CONTROL
                    io.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o400 and s.st_size<=cap,'stored_member')
                    total+=s.st_size;count+=1
                    # A large failed wrapper return is payload, not closure reserve.
                    if ispayload or name=='return.json':payload+=s.st_size
                    else:controls+=s.st_size
            finally:os.close(d)
            io.need(total<=STAGE and payload<=STAGE-RESERVE and controls<=RESERVE and count<=84,'stage_storage_cap')
            out[directory]=(total,payload,controls,count)
        return out
    def write(self,stage,name,raw):
        directory=self.name(stage,name);ispayload=bool(PAYLOAD.fullmatch(name)) or name=='return.json'
        io.need(type(raw)is bytes and len(raw)<=(MEMBER if ispayload else CONTROL),'artifact_cap')
        with self.locked():
            total,payload,controls,count=self.inventory().get(directory,(0,0,0,0))
            io.need(total+len(raw)<=STAGE and count<84 and (payload+len(raw)<=STAGE-RESERVE if ispayload else controls+len(raw)<=RESERVE),'storage_reserve')
            d=self.stage(directory,True);temp='.tmp-'+uuid.uuid4().hex
            try:
                # Exclusive final link makes claims atomic across processes. Any
                # unfinished temp poisons future inventory instead of permitting retry.
                try:os.stat(name,dir_fd=d,follow_symlinks=False)
                except FileNotFoundError:pass
                else:raise FileExistsError(name)
                f=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=d)
                try:
                    view=memoryview(raw)
                    while view:
                        n=os.write(f,view);io.need(n>0,'short_write');view=view[n:]
                    os.fchmod(f,0o400);io.file_sync(f)
                finally:os.close(f)
                os.link(temp,name,src_dir_fd=d,dst_dir_fd=d,follow_symlinks=False);os.unlink(temp,dir_fd=d)
                os.fsync(d);os.fsync(self.fd)
                io.need(io.read_at(d,name,MEMBER,0o400)==raw,'readback');self.inventory()
                return dict(status='durable',sha256=io.pin(raw)['sha256'])
            finally:os.close(d)
    def object(self,stage,name,value):return self.write(stage,name,io.canonical(value))
    def read(self,stage,name,expected=None):
        directory=self.name(stage,name)
        with self.locked():
            self.inventory();d=self.stage(directory)
            try:return io.read_at(d,name,MEMBER,0o400,expected)
            finally:os.close(d)
    def exists(self,stage,name):
        directory=self.name(stage,name)
        with self.locked():
            self.inventory()
            try:d=self.stage(directory)
            except FileNotFoundError:return False
            try:
                try:os.stat(name,dir_fd=d,follow_symlinks=False);return True
                except FileNotFoundError:return False
            finally:os.close(d)

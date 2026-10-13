"""Supplemental installed-distribution metadata binding; no acquisition or authority."""
import base64
import csv
import hashlib
import importlib.machinery
from io import StringIO
import os
from pathlib import Path
import re
import secure_io as io

MAX_INVENTORY=16*1024*1024
MAX_RECORD_TOTAL=64*1024*1024
MAX_FILES=200000


def _beneath(path,root):return path.startswith(root+'/')


def _digest(value):
    io.need(type(value) is str and value.startswith('sha256='),'record_hash_algorithm')
    text=value[7:];io.need(re.fullmatch('[A-Za-z0-9_-]{43}',text),'record_hash_encoding')
    raw=base64.b64decode(text+'=',altchars=b'-_',validate=True)
    io.need(len(raw)==32 and base64.urlsafe_b64encode(raw).decode().rstrip('=')==text,'record_hash_canonical')
    return raw.hex()


def load(spec,check):
    """Verify pinned RECORD documents and their exact admitted-file correspondence.

    Hashes inside RECORD are integrity metadata pinned by ROOT, not publisher
    signatures. File bytes are checked when actually imported, not eagerly here.
    """
    check();doc=io.json_read(io.read_file(spec,MAX_INVENTORY),MAX_INVENTORY)
    io.need(type(doc) is dict and set(doc)=={'schema','roots','records','files'} and doc['schema']=='marked-supplemental-vendor-inventory-v1','vendor_schema')
    roots=doc['roots'];records=doc['records'];files=doc['files']
    io.need(type(roots) is list and 1<=len(roots)<=8 and len(set(roots))==len(roots),'vendor_roots')
    for root in roots:
        io.parts(root,True);d=io.directory(root);os.close(d)
        io.need(str(Path(root).resolve(strict=True))==root,'canonical_vendor_root')
    io.need(type(records) is dict and 1<=len(records)<=4096 and type(files) is dict and 1<=len(files)<=MAX_FILES,'vendor_counts')
    wanted={};out={}
    for path,entry in files.items():
        check();io.parts(path,True)
        io.need(type(entry) is dict and set(entry)=={'bytes','sha256','mode','record_id','record_path'} and type(entry['mode']) is int and 0<=entry['mode']<=0o777,'vendor_file')
        io.pin_check({k:entry[k] for k in ('bytes','sha256')},2**34)
        io.need(any(_beneath(path,r) for r in roots) and type(entry['record_id']) is str and entry['record_id'] in records,'vendor_file_root')
        literal=entry['record_path'];io.need(type(literal) is str and 0<len(literal)<=4096 and not literal.startswith('/') and '\\' not in literal and '\0' not in literal,'record_relative_path')
        rid=entry['record_id'];r=records[rid];base=str(Path(r['path']).parent.parent)
        io.need(base in roots and os.path.normpath(base+'/'+literal)==path,'record_path_resolution')
        key=(rid,literal);io.need(key not in wanted,'duplicate_vendor_record_path');wanted[key]=entry
        out[path]=dict(pin={k:entry[k] for k in ('bytes','sha256')},mode=entry['mode'])
    seen=set();total=0;rows=0
    for rid,r in records.items():
        check();io.need(type(rid) is str and '/' not in rid and rid.endswith('.dist-info'),'record_id')
        io.need(type(r) is dict and set(r)=={'path','pin','mode'} and str(Path(r['path']).parent.name)==rid and Path(r['path']).name=='RECORD' and str(Path(r['path']).parent.parent) in roots,'record_spec')
        raw=io.read_file(r,MAX_INVENTORY);total+=len(raw);io.need(total<=MAX_RECORD_TOTAL,'record_total_cap')
        local={}
        for row in csv.reader(StringIO(raw.decode('utf8')),strict=True):
            rows+=1;io.need(rows<=400000 and len(row)==3,'record_row')
            if rows%256==0:check()
            literal,hash_value,size=row
            key=(rid,literal)
            if key not in wanted:continue  # unadmitted rows, including duplicates, convey no execution permission
            if literal in local:
                io.need(local[literal]==tuple(row),'conflicting_record_literal');continue
            local[literal]=tuple(row)
            io.need(re.fullmatch('[0-9]+',size) and len(size)<=20,'record_size')
            entry=wanted[key];io.need(_digest(hash_value)==entry['sha256'] and int(size)==entry['bytes'],'record_file_binding');seen.add(key)
    io.need(seen==set(wanted),'unproven_vendor_member');check();return out


class VerifiedSourceLoader(importlib.machinery.SourceFileLoader):
    """Compile pinned source bytes directly; -B alone does not bypass stale pyc."""
    def __init__(self,name,path,verified_path,binding,check):
        super().__init__(name,path);self.verified_path=verified_path;self.binding=binding;self.check=check
    def get_code(self,fullname):
        self.check();io.need(fullname==self.name,'verified_loader_name')
        raw=io.read_file(dict(path=self.verified_path,pin=self.binding['pin'],mode=self.binding['mode']),64*1024*1024)
        code=self.source_to_code(raw,self.path);self.check();return code


class VerifiedBytecodeLoader(importlib.machinery.SourcelessFileLoader):
    """Sourceless execution is allowed only for independently pinned pyc bytes."""
    def __init__(self,name,path,verified_path,binding,check):
        super().__init__(name,path);self.verified_path=verified_path;self.binding=binding;self.check=check
    def get_data(self,path):
        self.check();io.need(path==self.path,'verified_bytecode_path')
        raw=io.read_file(dict(path=self.verified_path,pin=self.binding['pin'],mode=self.binding['mode']),64*1024*1024)
        self.check();return raw

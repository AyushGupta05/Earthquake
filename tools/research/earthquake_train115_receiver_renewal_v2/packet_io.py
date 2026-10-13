"""Bounded numeric in-memory packet custody; no filesystem paths or pickle."""
import ast
import copy
import hashlib
import io
import json
import re
import struct
import zipfile
import numpy as np
import observations as obs
import pilot

MAX_ARCHIVE=128*1024*1024
MAX_MANIFEST=4*1024*1024
MAX_MEMBERS=1380
STORAGE_SCHEMA='receiver-observation-storage-v2'
MEMBER=re.compile(r'r_\d{3}_(?:init|h[135])_(?:wave|amplitude|context)\Z')


def need(value,code):obs.need(value,code)


def pin(raw,expected,cap):
    need(type(raw) is bytes and len(raw)<=cap and obs.new_native._keys(expected,('bytes','sha256'))
         and obs.new_native._int(expected['bytes'],0,cap) and len(raw)==expected['bytes']
         and obs.new_native._sha(expected['sha256']) and hashlib.sha256(raw).hexdigest()==expected['sha256'],'storage_pin')


def save(packet,*,processing_begin):
    obs.deadline(processing_begin);pilot.validate(packet)
    arrays={};entries={};scalar={k:copy.deepcopy(v) for k,v in packet.items() if k!='rows'};scalar['rows']=[]
    for row in packet['rows']:
        projected={k:copy.deepcopy(v) for k,v in row.items() if k not in ('initial','horizons')}
        projected['initial']=None;projected['horizons']=[copy.deepcopy(x) for x in row['horizons']] if not row['common'] else []
        if row['common']:
            for scope,item in [('init',row['initial'])]+[('h'+str(x['seconds']),x) for x in row['horizons']]:
                obj={}
                for key,value in item.items():
                    if key in ('wave','amplitude','context'):
                        name='r_%03d_%s_%s'%(row['ordinal'],scope,key);arrays[name]=value
                        raw=value.tobytes(order='C');entries[name]=dict(dtype=value.dtype.str,shape=list(value.shape),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());obj[key]=name
                    else:obj[key]=copy.deepcopy(value)
                if scope=='init':projected['initial']=obj
                else:projected['horizons'].append(obj)
        scalar['rows'].append(projected);obs.deadline(processing_begin)
    need(len(arrays)<=MAX_MEMBERS,'storage_members')
    manifest=obs.canonical(dict(schema=STORAGE_SCHEMA,packet=scalar,arrays=entries));need(len(manifest)<=MAX_MANIFEST,'storage_manifest_cap')
    archive=io.BytesIO();np.savez_compressed(archive,**arrays);raw=archive.getvalue();need(len(raw)<=MAX_ARCHIVE,'storage_archive_cap')
    inspect(raw,entries,processing_begin);obs.deadline(processing_begin)
    return raw,manifest


def inspect(raw,entries,begin):
    obs.deadline(begin)
    need(type(raw) is bytes and len(raw)<=MAX_ARCHIVE and type(entries) is dict and 0<len(entries)<=MAX_MEMBERS,'storage_archive')
    expected=set();payload=0;wave_elements=0
    for name,entry in entries.items():
        need(type(name) is str and MEMBER.fullmatch(name) and int(name[2:5])<=114
             and obs.new_native._keys(entry,('dtype','shape','bytes','sha256')),'storage_entry')
        shape=entry['shape'];dtype=entry['dtype'];kind=name.rsplit('_',1)[-1]
        need(type(shape) is list and all(type(x) is int and x>0 for x in shape)
             and dtype==('<f8' if kind=='context' else '<f4') and obs.new_native._sha(entry['sha256']),'storage_entry')
        elements=math_product(shape);size=elements*(8 if dtype=='<f8' else 4)
        if kind=='wave':need(len(shape)==2 and shape[0]==3,'storage_shape');wave_elements+=elements
        elif kind=='amplitude':need(shape==[4],'storage_shape')
        else:need(shape==([35] if '_init_' in name else [36]),'storage_shape')
        need(type(entry['bytes']) is int and entry['bytes']==size,'storage_bytes');payload+=size;expected.add(name+'.npy')
    need(payload<=MAX_ARCHIVE and wave_elements<=20_000_000,'storage_payload_cap')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members=z.infolist();need(len(members)==len(expected) and {x.filename for x in members}==expected,'storage_member_set')
        need(sum(x.file_size for x in members)<=MAX_ARCHIVE,'storage_uncompressed_cap')
        for member in members:
            obs.deadline(begin);entry=entries[member.filename[:-4]]
            need(member.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) and not member.flag_bits&1
                 and entry['bytes']<member.file_size<=entry['bytes']+4112,'storage_framing')
            with z.open(member) as f:
                magic=f.read(8);need(magic[:6]==b'\x93NUMPY' and magic[6:] in (b'\x01\x00',b'\x02\x00'),'storage_npy')
                width=2 if magic[6]==1 else 4;length=f.read(width);need(len(length)==width,'storage_npy')
                n=struct.unpack('<H' if width==2 else '<I',length)[0];need(n<=4096,'storage_header_cap')
                header=f.read(n);need(len(header)==n,'storage_npy')
                h=ast.literal_eval(header.decode('latin1'))
                need(type(h) is dict and set(h)=={'descr','fortran_order','shape'} and h['descr']==entry['dtype']
                     and h['fortran_order'] is False and type(h['shape']) is tuple and all(type(x) is int for x in h['shape'])
                     and list(h['shape'])==entry['shape'] and 8+width+n+entry['bytes']==member.file_size,'storage_npy_shape')


def math_product(shape):
    value=1
    for x in shape:
        value*=x;need(value<=20_000_000,'storage_element_cap')
    return value


def load(archive_bytes,manifest_bytes,*,pins,processing_begin):
    obs.deadline(processing_begin);need(obs.new_native._keys(pins,('archive','manifest')),'storage_pins')
    pin(archive_bytes,pins['archive'],MAX_ARCHIVE);pin(manifest_bytes,pins['manifest'],MAX_MANIFEST)
    manifest=obs.json_load(manifest_bytes,MAX_MANIFEST)
    need(obs.new_native._keys(manifest,('schema','packet','arrays')) and manifest['schema']==STORAGE_SCHEMA,'storage_manifest')
    inspect(archive_bytes,manifest['arrays'],processing_begin);scalar=manifest['packet'];need(type(scalar) is dict,'storage_packet')
    arrays={}
    with np.load(io.BytesIO(archive_bytes),allow_pickle=False) as z:
        need(set(z.files)==set(manifest['arrays']),'storage_member_set')
        for name,entry in manifest['arrays'].items():
            obs.deadline(processing_begin);a=np.ascontiguousarray(z[name])
            need(a.dtype.str==entry['dtype'] and list(a.shape)==entry['shape'] and np.isfinite(a).all()
                 and hashlib.sha256(a.tobytes(order='C')).hexdigest()==entry['sha256'],'storage_payload_hash')
            arrays[name]=a
    expected_refs=[]
    need(type(scalar.get('rows')) is list and len(scalar['rows'])==115,'storage_packet')
    for i,row in enumerate(scalar['rows']):
        need(type(row) is dict and type(row.get('common')) is bool,'storage_packet')
        if row['common']:
            need(type(row.get('initial')) is dict and type(row.get('horizons')) is list and len(row['horizons'])==3,'storage_packet')
            for scope,item in [('init',row['initial'])]+[('h'+str(h),x) for h,x in zip((1,3,5),row['horizons'])]:
                need(type(item) is dict,'storage_packet')
                for key in ('wave','amplitude','context'):
                    name='r_%03d_%s_%s'%(i,scope,key);need(type(item.get(key)) is str and item[key]==name and name in arrays,'storage_reference')
                    item[key]=arrays[name];expected_refs.append(name)
    need(len(expected_refs)==len(set(expected_refs)) and set(expected_refs)==set(arrays),'storage_reference_closure')
    pilot.validate(scalar);obs.deadline(processing_begin)
    return scalar

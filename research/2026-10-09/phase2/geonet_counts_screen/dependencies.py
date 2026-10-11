"""Checksum-pinned local source and existing runtime; no installs or requests."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import types
import warnings

BASE=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(BASE/'.runtime-cache/matplotlib')

def read(path,cap):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('bounded nonsymlink file required')
    with path.open('rb') as f:body=f.read(cap+1)
    if len(body)>cap:raise ValueError('bounded file grew')
    return body

def sha(body):return hashlib.sha256(body).hexdigest()
def pins():return json.loads(read(BASE/'reviewed_dependencies.json',1024*1024))

def body(name):
    p=pins()[name];data=read(BASE.parent/p['relative_path'],32*1024*1024)
    if sha(data)!=p['sha256']:raise ValueError('reviewed dependency changed: '+name)
    return data

def module(name):
    source=body(name);m=types.ModuleType('counts_pinned_'+name)
    m.__file__=str(BASE.parent/pins()[name]['relative_path'])
    if name=='adapter':
        # Reuse only reviewed public-API adapters, never its acquisition entry point
        # or top-level imports/cache side effects. Selected definitions are pinned
        # by the complete original source hash, with explicit standard-library globals.
        names={'ResponseEvidenceError','inventory_records','stream_pieces','response_evidence'}
        nodes=[n for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
        if {n.name for n in nodes}!=names:raise ValueError('pinned adapter definitions missing')
        m.__dict__.update(math=math,warnings=warnings)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),m.__file__,'exec'),m.__dict__)
    else:exec(compile(source,m.__file__,'exec'),m.__dict__)
    return m

def runtime():
    import importlib.metadata
    for name in pins():body(name)
    d=json.loads(body('dependency_receipt'))
    expected=BASE.parent/'geonet_waveform_feasibility/.venv'
    if Path(sys.executable).absolute()!=Path(d['python_executable']) or sys.version!=d['python_version']:raise ValueError('exact existing workspace runtime required')
    if not d['synthetic_adapter_smoke_passed']:raise ValueError('runtime smoke prerequisite absent')
    for name,version in d['installed_resolved_packages'].items():
        dist=importlib.metadata.distribution(name)
        if dist.version!=version or not Path(dist.locate_file('')).absolute().is_relative_to(expected):raise ValueError('workspace package changed')
    if sha(body('dependency_lock'))!=d['dependency_lock_sha256'] or sha(body('wheel_receipt'))!=d['published_wheels_receipt_sha256']:raise ValueError('runtime lock/receipt mismatch')
    binary=Path(sys.executable).resolve()
    result={'executable':str(Path(sys.executable).absolute()),'resolved_binary':str(binary),'binary_sha256':sha(read(binary,128*1024*1024)),
            'python_version':sys.version,'cache_tag':sys.implementation.cache_tag,'machine':os.uname().machine,'package_versions':d['installed_resolved_packages'],
            'dependency_receipt_sha256':pins()['dependency_receipt']['sha256'],'installations':0}
    if result['binary_sha256']!='2477b47fa3ae65b9574eb18a15edb364e96948eaa1875ad3f1c80d780efc9c12':raise ValueError('original Python binary mismatch')
    return result

"""L's positively bound cold runtime contexts. Source reads only; no data/IO writes."""
from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import re
import sys
import types

COUNTS = dict(processor=33,gaussian=34,native=22,reference=13,kernel=20,auditor=35,original_auditor=31)
SUPPORT = {'adapter','executor','v6','protocol','bootstrap'}
REQUIRED_SUPPORT = {'adapter','executor','v6'}
SOURCE_ROLES = {'operator','native_validator','reference','kernel','processor','protocol','numeric_state'}
OLD_ROLES = {'operator','native_validator','reference','processor','protocol'}
THREADS = ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')
AUDIT_NAMES = ('math_core','transport','packet_digest','packet','metrics','auditor','proper_core','ar_core','l_auditor')
_USED = False


def _keys(io, value, keys, reason):
    io.need(type(value) is dict and set(value)==set(keys),reason)


def _source(spec, role, io, sb, check):
    _keys(io,spec,('directory','files','manifest','upload_manifest'),'source_spec')
    directory=spec['directory'];io.parts(directory,True)
    io.need(os.path.realpath(directory)==directory,'canonical_source_directory')
    files=spec['files'];io.need(type(files) is dict and 1<=len(files)<=128,'source_count')
    if role in COUNTS:io.need(len(files)==COUNTS[role],'frozen_source_count')
    actual,links,dirs=sb.inventory(directory);expected=set(files)
    for name,pin in files.items():io.parts(name);io.pin_check(pin)
    if spec['upload_manifest'] is not None:
        up=spec['upload_manifest']
        io.need(up['path']==directory+'/parent_upload_manifest.private.json' and up['mode']==0o400,'upload_role')
        io.need(io.json_read(io.read_file(up,4*1024*1024))==files,'upload_binding')
        expected.add('parent_upload_manifest.private.json')
    expected_dirs={str(q) for name in expected for q in Path(name).parents if str(q)!='.'}
    io.need(set(actual)==expected and not links and dirs==expected_dirs,'source_closed')
    raw={}
    for name,pin in files.items():
        check();raw[name]=io.read_file(dict(path=directory+'/'+name,pin=pin,mode=0o400),16*1024*1024)
    m=spec['manifest'];_keys(io,m,('path','pin','mode'),'manifest_spec')
    io.need(m['mode']==0o400 and m['path'].startswith(directory+'/'),'manifest_role')
    relative=m['path'][len(directory)+1:]
    io.need(relative in files and m['pin']==files[relative],'manifest_binding')
    doc=io.json_read(raw[relative]);io.need(type(doc) is dict,'manifest_object')
    entries=doc.get('files',doc.get('members',doc))
    if type(entries) is list:
        io.need(all(type(x) is dict and {'path','bytes','sha256'}<=set(x) for x in entries),'manifest_entries')
        io.need(len({x['path'] for x in entries})==len(entries),'duplicate_manifest_path')
        entries={x['path']:{k:x[k] for k in ('bytes','sha256')} for x in entries}
    io.need(type(entries) is dict and entries and all(k in files and v==files[k] for k,v in entries.items()),'manifest_members')
    # Self/checksum/allowlist metadata cannot mutually hash themselves. Every
    # one is nevertheless explicitly pinned by ROOT's whole closed profile.
    omitted=set(files)-set(entries)
    io.need(omitted<={relative,'ALLOWED_PUBLIC_FILES.txt','PUBLIC_FILES.json','SHA256SUMS','CHECKSUMS.sha256'},'unmanifested_source')
    check();return raw


def _member(specs,file_spec,io):
    _keys(io,file_spec,('path','pin','mode'),'subject_spec');io.need(file_spec['mode']==0o400,'subject_mode')
    matches=[]
    for group,s in specs.items():
        prefix=s['directory']+'/'
        if file_spec['path'].startswith(prefix):
            name=file_spec['path'][len(prefix):]
            if name in s['files'] and file_spec['pin']==s['files'][name]:matches.append((group,name))
    io.need(len(matches)==1,'subject_outside_or_ambiguous_profile');return matches[0]


def _roles(config, raw, io):
    specs=config['sources'];subjects=config['role_subjects'];_keys(io,subjects,SOURCE_ROLES,'role_subjects')
    pins={}
    for role,value in subjects.items():
        group,name=_member(specs,value,io);pins[role]=dict(value['pin']);io.need(value['pin']['bytes']>0,'role_pin')
        if role in ('operator','native_validator','reference','kernel','processor'):
            expected={'operator':'gaussian','native_validator':'native'}.get(role,role)
            io.need(group==expected and value==specs[expected]['manifest'],'role_manifest_subject')
        elif role=='numeric_state':io.need(group=='processor' and name=='numeric_state.py','numeric_state_subject')
    pg,pn=_member(specs,subjects['protocol'],io);protocol=raw[pg][pn]
    io.need(protocol==raw['processor']['reference/PROTOCOL.md']==raw['reference']['L_PROTOCOL.md']==raw['auditor']['L_PROTOCOL.md'],'protocol_bytes')
    old=config['original_source_pins'];_keys(io,old,OLD_ROLES,'original_source_roles')
    for value in old.values():io.pin_check(value);io.need(value['bytes']>0,'original_source_pin')
    for role in ('operator','native_validator'):io.need(old[role]==pins[role],'unchanged_original_role')
    return pins


def _copies(raw,io):
    pairs=[('processor','reference/gaussian_operator.py','gaussian','gaussian_operator.py'),
           ('processor','reference/reference_core.py','gaussian','reference_core.py'),
           ('processor','reference/marked_native.py','native','marked_native.py'),
           ('processor','reference/native_packet_io.py','native','packet_io.py'),
           ('processor','reference/level_kernel.py','kernel','kernel.py')]
    for name in ('proper_core.py','ar_core.py'):
        pairs.extend([('processor','reference/'+name,'reference',name),('auditor',name,'reference',name)])
    for name in ('math_core.py','transport.py','packet_digest.py','packet.py','metrics.py','auditor.py','fixtures.py'):
        pairs.append(('auditor',name,'original_auditor',name))
    pairs.append(('reference','proper_core.py','original_auditor','math_core.py'))
    for left,ln,right,rn in pairs:io.need(raw[left][ln]==raw[right][rn],'frozen_copy_mismatch')


def _injected(config, io, sb):
    s=config['sources']['v6']
    modules={'secure_io':io,'source_binding':sb,'vendor_inventory':sb.vi,'generated_source':sb.gs,'metadata_finder':sb.mf}
    for name,module in modules.items():
        io.need(type(module) is types.ModuleType and module.__file__==s['directory']+'/'+name+'.py'
                and name+'.py' in s['files'],'injected_source_identity')
    io.need(sb.io is io and sb.vi.io is io and sb.gs.io is io and sb.mf.io is io and sb.gs.vi is sb.vi and sb.mf.vi is sb.vi,'injected_dependency_identity')
    own=config['sources']['adapter'];io.need(__file__==own['directory']+'/runtime_adapter.py' and 'runtime_adapter.py' in own['files'],'adapter_source_identity')


def _group(role,names,prefix,specs,raw,io,sb,check):
    before={name:sys.modules.get(name) for name in names};check()
    modules=sb.load_group(specs[role],raw[role],names,prefix+'_'+role)
    for name,module in modules.items():
        io.need(sys.modules.get(name) is before[name],'canonical_alias_restoration')
        io.need(module.__file__==specs[role]['directory']+'/'+name+'.py'
                and sys.modules.get(prefix+'_'+role+'_'+name) is module,'loaded_module_identity')
    check();return modules


def _independent_clean(specs,io):
    forbidden=[specs[k]['directory']+'/' for k in ('processor','gaussian','kernel')]
    for name,module in list(sys.modules.items()):
        io.need(not (name=='torch' or name.startswith('torch.')), 'independent_torch_import')
        path=vars(module).get('__file__') if isinstance(module,types.ModuleType) else None
        if path:io.need(not any(os.path.realpath(path).startswith(root) for root in forbidden),'independent_producer_import')


def _environment(io):
    io.need(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='1' for k in THREADS),'cpu_environment')


def _identities(mode,g,np,torch,io):
    native=g['native'];io.need(native['packet_io'].m is native['marked_native'],'native_alias')
    for group in g.values():
        for module in group.values():io.need(module.np is np,'numpy_identity')
    if mode=='producer':
        p=g['processor'];io.need(p['processor'].ns is p['numeric_state'] and p['processor'].lm is p['l_math']
                                  and p['processor'].desc is p['descriptive'],'processor_alias')
        io.need(g['reference']['ar_core'].p is g['reference']['proper_core'],'reference_alias')
        for module in (p['processor'],p['l_math'],g['kernel']['kernel'],g['gaussian']['gaussian_operator']):
            io.need(module.torch is torch,'torch_identity')
        io.need(torch.get_num_threads()==1 and not torch.cuda.is_initialized(),'cpu_only')
    else:
        a=g['auditor'];m=a['math_core']
        for name in ('transport','packet_digest','packet','metrics'):io.need(a[name].need is m.need,'core_function_alias')
        io.need(a['packet'].array is m.array and a['packet'].summaries is m.summaries,'packet_core_alias')
        for name,targets in {'auditor':dict(core='math_core',pkt='packet',tx='transport',packet_digest='packet_digest',metrics='metrics'),
                             'ar_core':dict(p='proper_core'),
                             'l_auditor':dict(old='auditor',core='math_core',ar='ar_core',pkt='packet',packet_digest='packet_digest',tx='transport',metrics='metrics')}.items():
            for attr,target in targets.items():io.need(getattr(a[name],attr) is a[target],'auditor_alias')
        io.need(not any(n=='torch' or n.startswith('torch.') for n in sys.modules),'independent_torch_import')


@contextmanager
def load(mode, config, *, expected_config_pin, io, sb, check, prefix):
    """ROOT owns the context through the entire scientific call and its return."""
    global _USED
    io.need(not _USED,'runtime_adapter_once');_USED=True
    io.need(type(mode) is str and mode in ('producer','independent') and type(prefix) is str
            and re.fullmatch(r'eew_l_[a-z0-9_]{1,64}',prefix),'mode_prefix')
    check();_keys(io,config,('sources','runtime','role_subjects','original_source_pins'),'adapter_config')
    io.need(io.pin(io.canonical(config))==expected_config_pin,'adapter_config_pin')
    specs=config['sources'];io.need(type(specs) is dict and (set(COUNTS)|REQUIRED_SUPPORT)<=set(specs)
                                  and set(specs)<=(set(COUNTS)|SUPPORT),'source_groups')
    roots=[s['directory'] for s in specs.values()]
    io.need(len(set(roots))==len(roots) and not any(a.startswith(b+'/') for a in roots for b in roots if a!=b),'source_root_overlap')
    raw={role:_source(spec,role,io,sb,check) for role,spec in specs.items()}
    _injected(config,io,sb);_copies(raw,io);pins=_roles(config,raw,io);_environment(io)
    sb.runtime(config['runtime'],check);check()
    if mode=='independent':_independent_clean(specs,io)
    with sb.vendor_guard(config['runtime'],specs,(),check):
        np=importlib.import_module('numpy');scipy=importlib.import_module('scipy');torch=None
        actual=dict(python='.'.join(map(str,sys.version_info[:3])),numpy=np.__version__,scipy=scipy.__version__)
        versions=config['runtime']['versions']
        _keys(io,versions,('python','numpy','scipy','torch'),'runtime_versions')
        if mode=='producer':
            torch=importlib.import_module('torch');actual['torch']=str(torch.__version__);torch.set_num_threads(1)
        io.need(all(versions[k]==v for k,v in actual.items()),'vendor_versions')
        g={'native':_group('native',('marked_native','packet_io'),prefix,specs,raw,io,sb,check)}
        if mode=='producer':
            for role,names in [('gaussian',('gaussian_operator','reference_core')),('reference',('proper_core','ar_core')),
                               ('kernel',('kernel',)),('processor',('numeric_state','l_math','descriptive','processor'))]:
                g[role]=_group(role,names,prefix,specs,raw,io,sb,check)
        else:g['auditor']=_group('auditor',AUDIT_NAMES,prefix,specs,raw,io,sb,check)
        _identities(mode,g,np,torch,io);check()
        value=dict(mode=mode,groups=g,source_pins=pins,original_source_pins={k:dict(v) for k,v in config['original_source_pins'].items()},
                   observed_versions=actual,adapter_config_pin=dict(expected_config_pin))
        try:yield value
        finally:
            check();_environment(io);_identities(mode,g,np,torch,io)
            if mode=='independent':_independent_clean(specs,io)

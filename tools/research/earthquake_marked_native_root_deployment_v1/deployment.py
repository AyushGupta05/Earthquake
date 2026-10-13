"""ROOT-only once-only preparation and separate frozen BUILD/AUDIT wrappers."""
from pathlib import Path,PurePosixPath
import hashlib,importlib.util,json,math,os,stat,subprocess,sys,time
import anchor

UNIT='eew-marked-native-root-preparation-v1.service'
AUTH_KEYS={'schema','processing_begin','source_commit','sources','runtime','inputs','output_root','permissions','deployment_source'}
PERMISSIONS={'source_published','linux_zero_skips','original_native_agreement','original_observations_agreement','anchor_projection_authorized','group_roster_bound','funding_resource_authorized','owned_units_inactive'}


def read(spec,cap):
    anchor.need(anchor.keys(spec,('path','pin')) and type(spec['path']) is str and Path(spec['path']).is_absolute(),'spec')
    fd=os.open(spec['path'],os.O_RDONLY|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd);anchor.need(stat.S_ISREG(s.st_mode) and s.st_mode&0o777==0o400 and s.st_size<=cap,'file')
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(cap+1)
    finally:os.close(fd)
    anchor.checked_pin(raw,spec['pin'],cap);return raw


def raw_read(path,cap):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd);anchor.need(stat.S_ISREG(s.st_mode) and s.st_mode&0o777==0o400 and s.st_size<=cap,'raw_file')
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(cap+1)
        anchor.need(len(raw)<=cap,'raw_cap');return raw
    finally:os.close(fd)


def raw_put(path,raw,cap):
    anchor.need(type(raw) is bytes and len(raw)<=cap,'output_cap');fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    with os.fdopen(fd,'wb') as f:os.fchmod(f.fileno(),0o400);f.write(raw);f.flush();os.fsync(f.fileno())
    directory=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


def verify_source(source,begin):
    anchor.need(anchor.keys(source,('directory','files')) and Path(source['directory']).is_absolute() and type(source['files']) is dict and 1<=len(source['files'])<=128,'source')
    root=Path(source['directory']);anchor.need(root.is_dir() and not root.is_symlink(),'source_directory');actual=set();dirs=set()
    for p in root.rglob('*'):
        anchor.need(not p.is_symlink(),'source_symlink')
        if p.is_file():actual.add(p.relative_to(root).as_posix())
        elif p.is_dir():dirs.add(p.relative_to(root).as_posix())
        else:anchor.need(False,'source_node')
    names=set(source['files']);expected_dirs=set()
    for n,pin in source['files'].items():
        anchor.need(type(n) is str and 0<len(n)<=256 and '\\' not in n and not PurePosixPath(n).is_absolute() and all(x not in ('','.','..') for x in n.split('/')),'source_member');expected_dirs.update(str(p) for p in PurePosixPath(n).parents if str(p)!='.');anchor.tick(begin);read(dict(path=str(root/n),pin=pin),16*1024*1024)
    extra='parent_upload_manifest.private.json'
    if extra in actual:
        p=root/extra;fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            s=os.fstat(fd);anchor.need(stat.S_ISREG(s.st_mode) and s.st_mode&0o777==0o400 and s.st_size<=1048576,'upload_file')
            with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(1048577)
        finally:os.close(fd)
        anchor.need(anchor.parse(raw,1048576)==source['files'],'upload_map');names.add(extra)
    anchor.need(actual==names and dirs==expected_dirs,'source_closed');anchor.tick(begin)


def load_parent(source):
    previous={n:sys.modules.get(n) for n in ('custody','supervision','controller','child')};loaded={}
    try:
        for n in previous:
            p=Path(source['directory'])/(n+'.py');spec=importlib.util.spec_from_file_location('marked_root_integration_'+n,p);m=importlib.util.module_from_spec(spec);sys.modules[n]=m;sys.modules[spec.name]=m;spec.loader.exec_module(m);loaded[n]=m
    finally:
        for n,m in previous.items():
            if m is None:sys.modules.pop(n,None)
            else:sys.modules[n]=m
    anchor.need(loaded['controller'].c is loaded['custody'] and loaded['child'].c is loaded['custody'] and loaded['child'].parent is loaded['controller'] and loaded['controller'].managed_process is loaded['supervision'].managed_process,'parent_globals');return loaded


def validate(a,p):
    anchor.need(anchor.keys(a,AUTH_KEYS) and a['schema']=='marked-native-root-authority-v1','authority');anchor.tick(a['processing_begin'])
    anchor.need(type(a['source_commit']) is str and len(a['source_commit'])==40 and all(x in '0123456789abcdef' for x in a['source_commit']),'commit')
    anchor.need(anchor.keys(a['sources'],('parent','marked','original','auditor','decoder')),'source_groups')
    for name,count in [('parent',48),('marked',22),('original',69),('auditor',None),('decoder',None)]:p.source_spec(a['sources'][name],count)
    p.source_spec(a['deployment_source']);anchor.need(anchor.keys(a['runtime'],('prefix_directory','manifest','canonical_sha256','critical_files','original_symlinks')),'runtime')
    links=a['runtime']['original_symlinks'];anchor.need(type(links) is dict and len(links)==4,'four_links')
    for name,target in links.items():p.member_name(name);anchor.need(name.startswith('venv/') and type(target) is str and 0<len(target)<=4096,'link')
    anchor.need(anchor.keys(a['inputs'],(set(p.INPUT_CAPS)-{'activity_anchor','anchor_proof'})|{'old_bodies','new_bodies'}),'inputs')
    for k,cap in p.INPUT_CAPS.items():
        if k in a['inputs']:p.spec(a['inputs'][k],cap)
    for key,n in [('old_bodies',17),('new_bodies',13)]:
        anchor.need(type(a['inputs'][key]) is dict and set(a['inputs'][key])=={str(i) for i in range(n)},'bodies')
        for spec in a['inputs'][key].values():
            if spec is not None:p.spec(spec,8388608)
    anchor.need(anchor.keys(a['permissions'],PERMISSIONS) and all(x is True for x in a['permissions'].values()),'permissions')
    anchor.need(type(a['output_root']) is str and Path(a['output_root']).is_absolute(),'output_root')
    placeholder=dict(path=str(Path(a['output_root'])/'not_read.private.json'),pin=dict(bytes=0,sha256='0'*64))
    runtime={k:v for k,v in a['runtime'].items() if k!='original_symlinks'};runtime['symlink_manifest']=placeholder
    inputs=dict(a['inputs'],activity_anchor=placeholder,anchor_proof=placeholder)
    p.gate_check(dict(schema='marked-native-parent-gate-v1',study=p.STUDY,stage='build',processing_begin=a['processing_begin'],source_commit=a['source_commit'],sources=a['sources'],runtime=runtime,inputs=inputs,prerequisites=placeholder,output_root=a['output_root'],build_return=None))


def fingerprint(a):return hashlib.sha256(anchor.canonical({k:v for k,v in a.items() if k!='processing_begin'})).hexdigest()


def bootstrap(a):
    begin=a['processing_begin'];verify_source(a['deployment_source'],begin);anchor.need(Path(__file__).parent==Path(a['deployment_source']['directory']) and Path(anchor.__file__).parent==Path(a['deployment_source']['directory']),'deployment_identity');verify_source(a['sources']['parent'],begin);modules=load_parent(a['sources']['parent']);validate(a,modules['controller']);return modules


def prepare_once(a,*,runner=None,run=subprocess.run,check_output=subprocess.check_output):
    modules=bootstrap(a);c=modules['custody'];p=modules['controller'];root=Path(a['output_root']);c.make_output_directory(root);c.private_put(root,'claim_prepare.private.json',dict(schema='marked-native-root-prepare-claim-v1',fingerprint=fingerprint(a),no_retry=True),262144);out=root/'preparation';c.make_output_directory(out);store=c.Store(out);store.put('authority.private.json',a,4194304)
    d=a['deployment_source']['directory'];code="import sys;sys.path.insert(0,%r);import deployment;deployment.prepare_child(%r)"%(d,str(out));python=str(Path(a['runtime']['prefix_directory'])/'venv/bin/python')
    args=['systemd-run','--user','--unit='+UNIT[:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']+['--setenv='+k+'=1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]+['-p','MemoryMax=1073741824','-p','MemorySwapMax=0','-p','TasksMax=32','-p','CPUWeight=10','-p','RuntimeMaxSec=360','-p','TimeoutStopSec=5','-p','KillMode=control-group',python,'-I','-B','-c',code]
    if runner is None:runner=modules['supervision'].managed_process
    try:answer=runner(args,380)
    except Exception as error:answer=dict(code=None,timeout=True,raw=dict(stdout=b'',stderr=b''),streams={},exception_type=type(error).__name__)
    store.put('stdout.private.bin',answer['raw']['stdout'],65536);store.put('stderr.private.bin',answer['raw']['stderr'],131072);store.put('manager.private.json',{k:v for k,v in answer.items() if k!='raw'},262144)
    if answer['timeout']:
        try:r=run(['systemctl','--user','stop',UNIT],capture_output=True,timeout=10);store.put('stop.private.json',dict(code=r.returncode),262144)
        except Exception as e:store.put('stop.private.json',dict(exception_type=type(e).__name__),262144)
    text=check_output(['systemctl','--user','show',UNIT,'-p','Result','-p','ActiveState','-p','ControlGroup'],text=True,timeout=5);anchor.need(type(text) is str and len(text.encode())<=16384,'post_cap');props={}
    for line in text.splitlines():
        if '=' in line:k,v=line.split('=',1);anchor.need(k not in props,'post_duplicate');props[k]=v
    store.put('post.private.json',dict(raw=text),262144);anchor.need(props.get('ActiveState') in ('inactive','failed') and props.get('ControlGroup')=='','cleanup')
    files,total=store.inventory(reserve=262144);result=None
    if 'result.private.json' in files:result=c.strict_json(c.read_file(out/'result.private.json',files['result.private.json'],4194304),4194304)
    normal=type(answer['code']) is int and answer['code']==0 and not answer['timeout'] and props.get('Result')=='success' and result is not None and result.get('status')=='complete' and answer['streams'] and all(not x['truncated'] and x['complete_observation'] for x in answer['streams'].values());late=None
    try:p.tick(a['processing_begin'],750)
    except Exception as e:normal=False;late=e
    returned=dict(schema='marked-native-root-preparation-return-v1',status='complete' if normal else 'incomplete',fingerprint=fingerprint(a),files=files,total_bytes=total,unit_exit=answer['code'],owned_unit_inactive=True,owned_cgroup_empty=True,no_retry=True)
    if late is not None:returned['failure']=dict(exception_type=type(late).__name__,reason=str(late))
    store.put('parent_return.private.json',returned,262144)
    if late is not None:raise late
    return returned


def live(check_output=subprocess.check_output):
    path=Path('/proc/self/cgroup').read_text();lines=[x[3:] for x in path.splitlines() if x.startswith('0::')];anchor.need(len(lines)==1 and Path(lines[0]).name==UNIT,'own_cgroup');g=Path('/sys/fs/cgroup')/lines[0].lstrip('/')
    anchor.need({n:(g/n).read_text().strip() for n in ('memory.max','memory.swap.max','pids.max')}==dict(zip(('memory.max','memory.swap.max','pids.max'),('1073741824','0','32'))) and str(os.getpid()) in (g/'cgroup.procs').read_text().split(),'live_limits')
    text=check_output(['systemctl','--user','show',UNIT,'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode','-p','ActiveState'],text=True,timeout=5);props=dict(x.split('=',1) for x in text.splitlines() if '=' in x)
    anchor.need(props.get('RuntimeMaxUSec') in ('6min','6min 0s','360s','360000000us') and props.get('TimeoutStopUSec') in ('5s','5000000us') and props.get('KillMode')=='control-group' and props.get('ActiveState')=='active','live_manager');anchor.need(sys.dont_write_bytecode and os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')),'live_environment')


def prepare_child(out):
    out=Path(out);store=None
    try:
        a=anchor.parse(raw_read(out/'authority.private.json',4194304),4194304);modules=bootstrap(a);c=modules['custody'];p=modules['controller'];store=c.Store(out)
        live();anchor.tick(a['processing_begin']);claim=anchor.parse(raw_read(Path(a['output_root'])/'claim_prepare.private.json',262144),262144);anchor.need(claim==dict(schema='marked-native-root-prepare-claim-v1',fingerprint=fingerprint(a),no_retry=True),'claim')
        for source in a['sources'].values():p.verify_sources(source,lambda:anchor.tick(a['processing_begin']))
        linkraw=anchor.canonical(dict(schema='marked-native-runtime-symlinks-v1',symlinks=a['runtime']['original_symlinks']));store.put('runtime_symlinks.private.json',linkraw,1048576);runtime={k:v for k,v in a['runtime'].items() if k!='original_symlinks'};runtime['symlink_manifest']=dict(path=str(out/'runtime_symlinks.private.json'),pin=anchor.pin(linkraw));modules['child'].runtime_verify(runtime,lambda:anchor.tick(a['processing_begin']))
        for name,spec in a['inputs'].items():
            if name.endswith('_bodies'):
                for spec in spec.values():
                    if spec is not None:anchor.tick(a['processing_begin']);c.hash_file(spec['path'],spec['pin'],0o400,8388608)
            else:anchor.tick(a['processing_begin']);c.hash_file(spec['path'],spec['pin'],0o400,p.INPUT_CAPS[name])
        raws={k:read(a['inputs'][k],p.INPUT_CAPS[k]) for k in ('original_archive','original_manifest','original_agreement')};pins=dict(archive=a['inputs']['original_archive']['pin'],manifest=a['inputs']['original_manifest']['pin'],agreement=a['inputs']['original_agreement']['pin']);input_pins={k:a['inputs'][k]['pin'] for k in anchor.RAW_KEYS}
        raw,packet=anchor.project(raws['original_archive'],raws['original_manifest'],raws['original_agreement'],pins=pins,input_pins=input_pins,processing_begin=a['processing_begin'])
        import numpy as np
        anchor.need(sys.version_info[:3]==(3,9,25) and np.__version__=='2.0.2' and 'torch' not in sys.modules,'versions')
        marked=modules['child'].load_group(a['sources']['marked'],('marked_native',),'root_anchor_marked')['marked_native'];anchor.need(marked.np is np,'marked_numpy')
        for r in packet['rows']:
            if r['common']:r['initial']['context']=np.ascontiguousarray(r['initial']['context'],dtype='<f8')
        compared=marked.project_anchor(packet,source_pins={k:pins[k] for k in ('archive','manifest')});anchor.need(type(compared) is bytes and compared==raw,'independent_projection_mismatch');store.put('activity_anchor.private.json',raw,4194304)
        proof=dict(schema='marked-native-original-anchor-proof-v1',passed=True,original_packet_verified=True,source_archive_pin=pins['archive'],source_manifest_pin=pins['manifest'],anchor_pin=anchor.pin(raw),input_pins=input_pins,original_agreement_pin=pins['agreement']);proofraw=anchor.canonical(proof);store.put('anchor_proof.private.json',proofraw,4194304)
        inputs=dict(a['inputs'],activity_anchor=dict(path=str(out/'activity_anchor.private.json'),pin=anchor.pin(raw)),anchor_proof=dict(path=str(out/'anchor_proof.private.json'),pin=anchor.pin(proofraw)))
        store.put('result.private.json',dict(schema='marked-native-root-preparation-result-v1',status='complete',input_specs=inputs,runtime=runtime,source_maps=a['sources'],source_commit=a['source_commit'],permissions=a['permissions'],output_root=a['output_root'],independent_projection_exact=True,fit_authorized=False),4194304);anchor.tick(a['processing_begin'])
    except Exception as error:
        failure=dict(status='incomplete',exception_type=type(error).__name__,reason=str(error),fit_authorized=False)
        if store is not None:store.put('failure.private.json',failure,262144)
        else:raw_put(out/'failure.private.json',anchor.canonical(failure),262144)
        raise


def run_stage(a,preparation_return_spec,stage,*,processing_begin,build_return_spec=None,invoke=None):
    current=dict(a,processing_begin=processing_begin);modules=bootstrap(current);c=modules['custody'];p=modules['controller'];anchor.need(stage in ('build','audit'),'stage');closed=anchor.parse(read(preparation_return_spec,262144),262144)
    anchor.need(closed['schema']=='marked-native-root-preparation-return-v1' and closed['status']=='complete' and closed['fingerprint']==fingerprint(a) and type(closed['unit_exit']) is int and closed['unit_exit']==0 and closed['owned_unit_inactive'] is True and closed['owned_cgroup_empty'] is True and closed['no_retry'] is True,'preparation_unverified')
    out=Path(a['output_root'])/'preparation';anchor.need(Path(preparation_return_spec['path'])==out/'parent_return.private.json','preparation_path')
    for name,pin in closed['files'].items():c.name_checked(name);p.tick(processing_begin);c.read_file(out/name,pin,64*1024*1024)
    result=anchor.parse(c.read_file(out/'result.private.json',closed['files']['result.private.json'],4194304),4194304);anchor.need(result['schema']=='marked-native-root-preparation-result-v1' and result['status']=='complete' and result['source_maps']==a['sources'] and result['source_commit']==a['source_commit'] and result['permissions']==a['permissions'] and result['output_root']==a['output_root'] and result['independent_projection_exact'] is True and result['fit_authorized'] is False,'preparation_result')
    anchor.need(anchor.keys(result['input_specs'],set(a['inputs'])|{'activity_anchor','anchor_proof'}) and all(result['input_specs'][k]==v for k,v in a['inputs'].items()),'prepared_inputs')
    for name,leaf in [('activity_anchor','activity_anchor.private.json'),('anchor_proof','anchor_proof.private.json')]:anchor.need(Path(result['input_specs'][name]['path'])==out/leaf and result['input_specs'][name]['pin']==closed['files'][leaf],'prepared_anchor')
    anchor.need(anchor.keys(result['runtime'],(set(a['runtime'])-{'original_symlinks'})|{'symlink_manifest'}) and all(result['runtime'][k]==v for k,v in a['runtime'].items() if k!='original_symlinks') and result['runtime']['symlink_manifest']==dict(path=str(out/'runtime_symlinks.private.json'),pin=closed['files']['runtime_symlinks.private.json']),'prepared_runtime')
    prereq=dict(schema='marked-native-prerequisites-v1',source_maps=a['sources'],input_specs=result['input_specs'],source_commit=a['source_commit']);prereq.update({k:a['permissions'][k] for k in PERMISSIONS-{'anchor_projection_authorized'}});prereq['anchor_independently_projected']=True;raw=anchor.canonical(prereq);path=Path(a['output_root'])/'prerequisites.private.json'
    if stage=='build':raw_put(path,raw,4194304);anchor.need(build_return_spec is None,'unexpected_build')
    else:anchor.need(read(dict(path=str(path),pin=anchor.pin(raw)),4194304)==raw and build_return_spec is not None,'audit_prerequisites')
    gate=dict(schema='marked-native-parent-gate-v1',study=p.STUDY,stage=stage,processing_begin=processing_begin,source_commit=a['source_commit'],sources=a['sources'],runtime=result['runtime'],inputs=result['input_specs'],prerequisites=dict(path=str(path),pin=anchor.pin(raw)),output_root=a['output_root'],build_return=build_return_spec)
    return (p.run if invoke is None else invoke)(gate)

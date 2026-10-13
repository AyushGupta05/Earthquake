"""Owned build/audit stage controller; stdlib only until positive child gates."""
from pathlib import Path,PurePosixPath
import hashlib,json,math,os,subprocess,time
import custody as c
from supervision import managed_process

STUDY='marked-native-integration-v1'
RAW_CAPS=dict(old_plan=131072,old_qualified=64*1024*1024,new_plan=131072,new_qualified=64*1024*1024,metadata=131072,roster=131072,activity_anchor=4*1024*1024)
INPUT_CAPS=dict(RAW_CAPS,original_archive=128*1024*1024,original_manifest=4*1024*1024,original_agreement=16*1024*1024,anchor_proof=4*1024*1024)
GATE_KEYS={'schema','study','stage','processing_begin','source_commit','sources','runtime','inputs','prerequisites','output_root','build_return'}


def tick(begin,limit=300):
    now=time.monotonic();c.need(type(begin) in (int,float) and math.isfinite(begin) and 0<=begin<=now and now-begin<=limit,'deadline')


def spec(value,cap):
    c.need(type(value) is dict and set(value)=={'path','pin'} and type(value['path']) is str and len(value['path'])<=4096 and Path(value['path']).is_absolute(),'file_spec');c.pin_checked(value['pin'],cap)


def member_name(name):
    c.need(type(name) is str and len(name)<=256 and '\\' not in name and not PurePosixPath(name).is_absolute() and all(p not in ('','.','..') for p in name.split('/')),'source_name')


def source_spec(value,count=None):
    c.need(type(value) is dict and set(value)=={'directory','files'} and type(value['directory']) is str and Path(value['directory']).is_absolute() and type(value['files']) is dict and 1<=len(value['files'])<=128,'source_spec')
    if count is not None:c.need(len(value['files'])==count,'source_count')
    for name,pin in value['files'].items():member_name(name);c.pin_checked(pin,16*1024*1024)


def gate_check(g):
    c.need(type(g) is dict and set(g)==GATE_KEYS and g['schema']=='marked-native-parent-gate-v1' and g['study']==STUDY and g['stage'] in ('build','audit'),'gate');tick(g['processing_begin'])
    c.need(type(g['source_commit']) is str and len(g['source_commit'])==40 and all(v in '0123456789abcdef' for v in g['source_commit']),'commit')
    c.need(type(g['sources']) is dict and set(g['sources'])=={'parent','marked','original','auditor','decoder'},'source_groups')
    for group,count in [('marked',22),('original',69),('parent',None),('auditor',None),('decoder',None)]:source_spec(g['sources'][group],count)
    runtime=g['runtime'];c.need(type(runtime) is dict and set(runtime)=={'prefix_directory','manifest','canonical_sha256','symlink_manifest','critical_files'} and type(runtime['prefix_directory']) is str and Path(runtime['prefix_directory']).is_absolute(),'runtime')
    spec(runtime['manifest'],4194304);spec(runtime['symlink_manifest'],1048576);c.pin_checked(dict(bytes=0,sha256=runtime['canonical_sha256']),0)
    c.need(type(runtime['critical_files']) is dict and len(runtime['critical_files'])==10,'critical')
    for path,p in runtime['critical_files'].items():
        c.need(type(path) is str and Path(path).is_absolute() and type(p) is dict and set(p)=={'bytes','sha256','mode'} and p['mode'] in ('0o400','0o444','0o555','0o644','0o664','0o755','0o775'),'critical');c.pin_checked({k:p[k] for k in ('bytes','sha256')},2**34)
    inputs=g['inputs'];c.need(type(inputs) is dict and set(inputs)==set(INPUT_CAPS)|{'old_bodies','new_bodies'},'inputs')
    for k,cap in INPUT_CAPS.items():spec(inputs[k],cap)
    for group,n in [('old_bodies',17),('new_bodies',13)]:
        c.need(type(inputs[group]) is dict and set(inputs[group])==set(str(i) for i in range(n)),'body_namespaces')
        total=0
        for value in inputs[group].values():
            if value is not None:spec(value,8388608);total+=value['pin']['bytes']
        c.need(total<=n*8388608,'body_cap')
    spec(g['prerequisites'],4194304)
    c.need(type(g['output_root']) is str and Path(g['output_root']).is_absolute(),'output_root')
    if g['stage']=='build':c.need(g['build_return'] is None,'unexpected_build')
    else:spec(g['build_return'],262144)


def input_fingerprint(g):
    return hashlib.sha256(json.dumps({k:g[k] for k in ('study','source_commit','sources','runtime','inputs','prerequisites','output_root')},sort_keys=True,allow_nan=False).encode()).hexdigest()


def verify_sources(value,check):
    root=Path(value['directory']);c.need(root.is_dir() and not root.is_symlink(),'source_directory');actual=set();directories=set()
    for path in root.rglob('*'):
        c.need(not path.is_symlink(),'source_symlink')
        if path.is_file():actual.add(path.relative_to(root).as_posix())
        elif path.is_dir():directories.add(path.relative_to(root).as_posix())
        else:raise ValueError('source_node')
    expected=set(value['files']);extra='parent_upload_manifest.private.json'
    if extra in actual:
        c.need(c.strict_json(upload_raw(root/extra),1048576)==value['files'],'source_upload');expected.add(extra)
    expected_dirs={str(parent) for name in value['files'] for parent in PurePosixPath(name).parents if str(parent)!='.'}
    c.need(actual==expected and directories==expected_dirs,'source_closed')
    for name,pin in value['files'].items():check();c.read_file(root/name,pin,16*1024*1024)


def upload_raw(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        import stat
        st=os.fstat(fd);c.need(stat.S_ISREG(st.st_mode) and st.st_mode&0o777==0o400 and st.st_size<=1048576,'upload_file')
        with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(1048577)
        c.need(len(raw)<=1048576,'upload_cap');return raw
    finally:os.close(fd)


def prerequisites(g):
    v=c.strict_json(c.read_file(g['prerequisites']['path'],g['prerequisites']['pin'],4194304),4194304)
    names={'schema','source_published','linux_zero_skips','original_native_agreement','original_observations_agreement','anchor_independently_projected','group_roster_bound','funding_resource_authorized','owned_units_inactive','source_maps','input_specs','source_commit'}
    c.need(type(v) is dict and set(v)==names and v['schema']=='marked-native-prerequisites-v1' and all(v[k] is True for k in names-{'schema','source_maps','input_specs','source_commit'}) and v['source_maps']==g['sources'] and v['input_specs']==g['inputs'] and v['source_commit']==g['source_commit'],'prerequisites')
    return v


def claim(g):
    gate_check(g);prerequisites(g);root=Path(g['output_root']);c.need(root.is_dir() and not root.is_symlink(),'output_directory')
    if g['stage']=='audit':
        closed=c.strict_json(c.read_file(g['build_return']['path'],g['build_return']['pin'],262144),262144)
        c.need(closed['schema']=='marked-native-parent-return-v1' and closed['stage']=='build' and closed['status']=='complete' and type(closed['unit_exit']) is int and closed['unit_exit']==0 and closed['owned_unit_inactive'] is True and closed['owned_cgroup_empty'] is True and closed['input_fingerprint']==input_fingerprint(g),'build_unverified')
    value=dict(schema='marked-native-exclusive-claim-v1',study=STUDY,stage=g['stage'],processing_begin=g['processing_begin'],input_fingerprint=input_fingerprint(g),gate_pin=c.pin((json.dumps(g,sort_keys=True,allow_nan=False)+'\n').encode()),no_retry=True)
    c.private_put(root,'claim_'+g['stage']+'.private.json',value,262144)
    out=root/g['stage'];c.make_output_directory(out);store=c.Store(out);store.put('claim.private.json',value,262144);store.put('gate.private.json',g,4194304);return out


def run(g,*,runner=managed_process,run=subprocess.run,check_output=subprocess.check_output):
    out=claim(g);stage=g['stage'];unit='eew-marked-native-integration-v1-'+stage+'.service';parent=g['sources']['parent']['directory'];python=str(Path(g['runtime']['prefix_directory'])/'venv/bin/python')
    code="import sys;sys.path.insert(0,%r);import child;child.main(%r)"%(parent,str(out))
    args=['systemd-run','--user','--unit='+unit[:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']+['--setenv='+k+'=1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]+['-p','MemoryMax=1073741824','-p','MemorySwapMax=0','-p','TasksMax=32','-p','CPUWeight=10','-p','RuntimeMaxSec=360','-p','TimeoutStopSec=5','-p','KillMode=control-group',python,'-I','-B','-c',code]
    tick(g['processing_begin']);store=c.Store(out)
    try:answer=runner(args,380)
    except Exception as error:answer=dict(code=None,timeout=True,raw=dict(stdout=b'',stderr=b''),streams={},exception_type=type(error).__name__)
    # Durable output journal precedes every return-time budget/control assertion.
    store.put('manager_stdout.private.bin',answer['raw']['stdout'],65536);store.put('manager_stderr.private.bin',answer['raw']['stderr'],131072);store.put('manager_return.private.json',{k:v for k,v in answer.items() if k!='raw'},262144)
    if answer['timeout']:
        try:r=run(['systemctl','--user','stop',unit],capture_output=True,timeout=10);store.put('stop.private.json',dict(code=r.returncode),262144)
        except Exception as e:store.put('stop.private.json',dict(exception_type=type(e).__name__),262144)
    text=check_output(['systemctl','--user','show',unit,'-p','Result','-p','ActiveState','-p','ControlGroup'],text=True,timeout=5);c.need(type(text) is str and len(text.encode())<=16384,'post_cap');props={}
    for line in text.splitlines():
        if '=' in line:k,v=line.split('=',1);c.need(k not in props,'post_duplicate');props[k]=v
    c.need(props.get('ActiveState') in ('inactive','failed') and props.get('ControlGroup')=='','owned_cleanup_unverified');store.put('post.private.json',dict(raw=text,owned_unit_inactive=True,owned_cgroup_empty=True),262144)
    files,total=store.inventory(reserve=262144);result=None
    if 'result.private.json' in files:result=c.strict_json(c.read_file(out/'result.private.json',files['result.private.json'],16*1024*1024))
    normal=type(answer['code']) is int and answer['code']==0 and not answer['timeout'] and props.get('Result')=='success' and result is not None and result.get('status')=='complete' and answer['streams'] and all(not s['truncated'] and s['complete_observation'] for s in answer['streams'].values())
    # A closure is AUDIT-eligible only if the final eligibility check passed.
    # Journals above survive expiration, but expiration must never leave complete.
    deadline_error=None
    try:tick(g['processing_begin'],750)
    except Exception as error:deadline_error=error;normal=False
    returned=dict(schema='marked-native-parent-return-v1',study=STUDY,stage=stage,status='complete' if normal else 'incomplete',files=files,total_bytes=total,input_fingerprint=input_fingerprint(g),unit_exit=answer['code'],owned_unit_inactive=True,owned_cgroup_empty=True,no_retry=True)
    if deadline_error is not None:returned['failure']=dict(exception_type=type(deadline_error).__name__,reason=str(deadline_error))
    store.put('parent_return.private.json',returned,262144)
    if deadline_error is not None:raise deadline_error
    return returned

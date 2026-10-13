"""Owned marked build/audit child. Stdlib until all source/runtime/input gates."""
from pathlib import Path
import importlib.util,json,math,os,stat,subprocess,sys,time
import custody as c
import controller as parent


def raw_file(path,cap):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        s=os.fstat(fd);c.need(stat.S_ISREG(s.st_mode) and s.st_size<=cap,'raw_file')
        with os.fdopen(fd,'rb',closefd=False) as f:b=f.read(cap+1)
        c.need(len(b)<=cap,'raw_cap');return b
    finally:os.close(fd)


def live(g,check_output=subprocess.check_output,proc=Path('/proc/self/cgroup'),base=Path('/sys/fs/cgroup')):
    unit='eew-marked-native-integration-v1-'+g['stage']+'.service';paths=[line[3:] for line in raw_file(proc,16384).decode().splitlines() if line.startswith('0::')]
    c.need(len(paths)==1 and paths[0].startswith('/') and Path(paths[0]).name==unit,'owned_cgroup');group=base/paths[0].lstrip('/')
    limits={k:raw_file(group/k,128).decode().strip() for k in ('memory.max','memory.swap.max','pids.max')}
    c.need(limits=={'memory.max':'1073741824','memory.swap.max':'0','pids.max':'32'} and str(os.getpid()) in raw_file(group/'cgroup.procs',16384).decode().split(),'live_limits')
    text=check_output(['systemctl','--user','show',unit,'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode','-p','ActiveState','-p','CPUWeight'],text=True,timeout=5)
    c.need(type(text) is str and len(text.encode())<=16384,'live_properties');props={}
    for line in text.splitlines():
        if '=' in line:k,v=line.split('=',1);c.need(k not in props,'live_duplicate');props[k]=v
    c.need(props.get('RuntimeMaxUSec') in {'6min','6min 0s','360s','360000000us'} and props.get('TimeoutStopUSec') in {'5s','5000000us'} and props.get('KillMode')=='control-group' and props.get('ActiveState')=='active' and props.get('CPUWeight')=='10','live_manager')
    c.need(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')) and sys.dont_write_bytecode,'live_environment');return dict(limits=limits,manager=text)


def runtime_verify(r,check):
    root=Path(r['prefix_directory']);manifest=c.strict_json(c.read_file(r['manifest']['path'],r['manifest']['pin'],4194304),4194304)
    canonical=json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode()
    c.need(__import__('hashlib').sha256(canonical).hexdigest()==r['canonical_sha256'] and type(manifest.get('files')) is dict and len(manifest['files'])==10112,'runtime_manifest')
    links=c.strict_json(c.read_file(r['symlink_manifest']['path'],r['symlink_manifest']['pin'],1048576),1048576)
    c.need(type(links) is dict and set(links)=={'schema','symlinks'} and links['schema']=='marked-native-runtime-symlinks-v1' and type(links['symlinks']) is dict,'symlinks_manifest')
    actual_files=set();actual_links={}
    for path in (root/'venv').rglob('*'):
        name=path.relative_to(root).as_posix()
        if path.is_symlink():actual_links[name]=os.readlink(path)
        elif path.is_file():actual_files.add(name)
    c.need(actual_files==set(manifest['files']) and actual_links==links['symlinks'],'runtime_closed')
    for name,pin in manifest['files'].items():
        parent.member_name(name);c.need(name.startswith('venv/'),'runtime_name');check();c.hash_file(root/name,pin,0o444)
    for path,pin in r['critical_files'].items():check();c.hash_file(path,pin,int(pin['mode'],8))
    check()


def load_group(source,names,prefix):
    # Temporary plain aliases resolve ONLY this group's verified transitive imports.
    previous={n:sys.modules.get(n) for n in names};loaded={}
    try:
        for name in names:
            relative=name+'.py';c.need(relative in source['files'],'module_unregistered');path=Path(source['directory'])/relative
            unique=prefix+'_'+name;c.need(unique not in sys.modules,'module_once')
            spec=importlib.util.spec_from_file_location(unique,path);obj=importlib.util.module_from_spec(spec);sys.modules[unique]=obj;sys.modules[name]=obj;spec.loader.exec_module(obj);loaded[name]=obj
            c.need(Path(obj.__file__)==path,'module_path')
    finally:
        for name,value in previous.items():
            if value is None:sys.modules.pop(name,None)
            else:sys.modules[name]=value
    return loaded


def dependencies(g):
    import numpy as np
    import scipy
    import obspy
    c.need(sys.version_info[:3]==(3,9,25) and np.__version__=='2.0.2' and scipy.__version__=='1.13.1' and obspy.__version__=='1.5.1' and 'torch' not in sys.modules,'runtime_versions')
    orig=load_group(g['sources']['original'],('old_scanner','new_scanner','decode_contract','old_native','new_native','activity_math','observations'),'marked_original')
    o=orig['observations'];c.need(o.old_native is orig['old_native'] and o.new_native is orig['new_native'] and o.am is orig['activity_math'] and orig['old_native'].scanner is orig['old_scanner'] and orig['new_native'].scanner is orig['new_scanner'] and orig['new_native'].ObservedDecodeFailure is orig['decode_contract'].ObservedDecodeFailure,'original_transitive')
    marked=load_group(g['sources']['marked'],('marked_native','packet_io'),'marked_bound')
    c.need(marked['packet_io'].m is marked['marked_native'] and o.np is np and marked['marked_native'].np is np and marked['packet_io'].np is np,'marked_transitive')
    decoder=load_group(g['sources']['decoder'],('scanner','decode_contract','producer','offline_decoder'),'marked_decoder')
    d=decoder['offline_decoder'];c.need(d.producer is decoder['producer'] and decoder['producer'].scanner is decoder['scanner'] and d.ObservedDecodeFailure is decoder['decode_contract'].ObservedDecodeFailure,'decoder_transitive')
    callback=d.make_decoder();c.need(callable(callback) and callback.__globals__['ObservedDecodeFailure'] is d.ObservedDecodeFailure,'decoder_callback')
    closure=dict(zip(callback.__code__.co_freevars,(x.cell_contents for x in callback.__closure__ or ())))
    c.need(closure.get('numpy') is np and closure.get('obspy') is obspy,'decoder_vendor_binding')
    independent=None
    if g['stage']=='audit':
        modules=load_group(g['sources']['auditor'],('old_native_scanner','new_native_scanner','decode_contract','old_native','new_native','auditor'),'marked_independent')
        independent=modules['auditor'];c.need(independent.old_native is modules['old_native'] and independent.new_native is modules['new_native'] and independent.ObservedDecodeFailure is modules['decode_contract'].ObservedDecodeFailure and modules['old_native'].scanner is modules['old_native_scanner'] and modules['new_native'].scanner is modules['new_native_scanner'] and independent.np is np,'auditor_transitive')
        base=callback
        def translate(raw,descriptor):
            try:return base(raw,descriptor)
            except d.ObservedDecodeFailure as failure:raise independent.ObservedDecodeFailure(failure.observed_samples) from None
        callback=translate
    return marked['marked_native'],marked['packet_io'],o,independent,callback,np


def before_import(g,out,claim,live_check=live):
    parent.gate_check(g);parent.prerequisites(g);check=lambda:parent.tick(g['processing_begin']);check()
    c.need(claim['schema']=='marked-native-exclusive-claim-v1' and claim['stage']==g['stage'] and claim['processing_begin']==g['processing_begin'] and claim['input_fingerprint']==parent.input_fingerprint(g) and claim['no_retry'] is True and claim['gate_pin']==c.pin(raw_file(out/'gate.private.json',4194304)),'claim_binding')
    global_claim=Path(g['output_root'])/('claim_'+g['stage']+'.private.json');c.need(c.strict_json(c.read_file(global_claim,c.pin(raw_file(global_claim,262144)),262144),262144)==claim,'global_claim')
    if g['stage']=='audit':
        previous=c.strict_json(c.read_file(g['build_return']['path'],g['build_return']['pin'],262144),262144)
        c.need(previous['schema']=='marked-native-parent-return-v1' and previous['stage']=='build' and previous['status']=='complete' and type(previous['unit_exit']) is int and previous['unit_exit']==0 and previous['owned_unit_inactive'] is True and previous['owned_cgroup_empty'] is True and previous['input_fingerprint']==parent.input_fingerprint(g),'build_unverified')
    controls=live_check(g)
    for value in g['sources'].values():parent.verify_sources(value,check)
    c.need(Path(__file__).parent==Path(g['sources']['parent']['directory']) and Path(c.__file__).parent==Path(g['sources']['parent']['directory']) and Path(parent.__file__).parent==Path(g['sources']['parent']['directory']),'parent_identity')
    runtime_verify(g['runtime'],check)
    raws={k:c.read_file(v['path'],v['pin'],parent.INPUT_CAPS[k]) for k,v in g['inputs'].items() if k in parent.RAW_CAPS}
    for k in ('original_archive','original_manifest','original_agreement','anchor_proof'):check();c.hash_file(g['inputs'][k]['path'],g['inputs'][k]['pin'],0o400,parent.INPUT_CAPS[k])
    proof=c.strict_json(c.read_file(g['inputs']['anchor_proof']['path'],g['inputs']['anchor_proof']['pin'],4194304),4194304)
    keys={'schema','passed','original_packet_verified','source_archive_pin','source_manifest_pin','anchor_pin','input_pins','original_agreement_pin'}
    pins={k:g['inputs'][k]['pin'] for k in parent.RAW_CAPS}
    c.need(type(proof) is dict and set(proof)==keys and proof['schema']=='marked-native-original-anchor-proof-v1' and proof['passed'] is True and proof['original_packet_verified'] is True and proof['source_archive_pin']==g['inputs']['original_archive']['pin'] and proof['source_manifest_pin']==g['inputs']['original_manifest']['pin'] and proof['anchor_pin']==pins['activity_anchor'] and proof['input_pins']=={k:p for k,p in pins.items() if k!='activity_anchor'} and proof['original_agreement_pin']==g['inputs']['original_agreement']['pin'],'anchor_proof')
    anchor=c.strict_json(raws['activity_anchor'],4194304);c.need(anchor['source_pins']=={'archive':proof['source_archive_pin'],'manifest':proof['source_manifest_pin']},'anchor_archive_binding')
    agreement=c.strict_json(c.read_file(g['inputs']['original_agreement']['path'],g['inputs']['original_agreement']['pin'],16*1024*1024));pub=agreement['public']
    c.need(pub['disposition']=='agreed' and pub['events']==115 and type(pub['events']) is int and pub['common_train']==65 and pub['common_dev']==22 and agreement['input_pins']==proof['input_pins'] and agreement['fit_authorized'] is False,'original_agreement')
    bodies={}
    for group in ('old_bodies','new_bodies'):bodies[group]={int(k):None if v is None else c.read_file(v['path'],v['pin'],8388608) for k,v in g['inputs'][group].items()}
    check();return raws,bodies,pins,controls


def diagnostic(value,np,depth=0):
    c.need(depth<=32,'diagnostic_depth')
    if type(value) is np.ndarray:
        c.need(value.dtype.str in ('<f8','|u1') and value.size<=1048576 and value.nbytes<=1048576,'diagnostic_array')
        return dict(dtype=value.dtype.str,shape=list(value.shape),values=diagnostic(value.tolist(),np,depth+1))
    if type(value) is dict:return {str(k):diagnostic(v,np,depth+1) for k,v in value.items()}
    if type(value) in (list,tuple):return [diagnostic(v,np,depth+1) for v in value]
    if type(value) is float and not math.isfinite(value):return dict(nonfinite_float=str(value))
    c.need(value is None or type(value) in (bool,int,float,str),'diagnostic_type');return value


def main(directory):
    out=Path(directory);store=c.Store(out,reserve_bytes=16*1024*1024,reserve_members=2);packet=None;np=None;m=None;semantic=None
    try:
        g=c.strict_json(raw_file(out/'gate.private.json',4194304),4194304);claim=c.strict_json(raw_file(out/'claim.private.json',262144),262144)
        raws,bodies,pins,controls=before_import(g,out,claim);store.put('live.private.json',controls,262144);parent.tick(g['processing_begin'])
        m,io,o,a,decode,np=dependencies(g);parent.tick(g['processing_begin'])
        args=(raws['old_plan'],raws['old_qualified'],bodies['old_bodies'],raws['new_plan'],raws['new_qualified'],bodies['new_bodies'],raws['metadata'],raws['roster'])
        if g['stage']=='build':
            packet=m.build_marked(*args,raws['activity_anchor'],decode,bindings=m.Bindings(o),pins=pins,processing_begin=g['processing_begin'])
            archive,manifest=io.save(packet,processing_begin=g['processing_begin']);archive_pin=store.put('features.private.npz',archive,8388608);manifest_pin=store.put('features_manifest.private.json',manifest,4194304)
            result=dict(status='complete',archive_pin=archive_pin,manifest_pin=manifest_pin,events=115,horizon_cells=345,fit_authorized=False)
        else:
            closed=c.strict_json(c.read_file(g['build_return']['path'],g['build_return']['pin'],262144),262144);build=Path(g['output_root'])/'build';files=closed['files']
            packet=io.load(c.read_file(build/'features.private.npz',files['features.private.npz'],8388608),c.read_file(build/'features_manifest.private.json',files['features_manifest.private.json'],4194304),pins={'archive':files['features.private.npz'],'manifest':files['features_manifest.private.json']},processing_begin=g['processing_begin'])
            # Semantic module belongs to this already verified parent source package.
            semantic=load_group(g['sources']['parent'],('semantic',),'marked_semantic')['semantic']
            audited=semantic.audit(*args,packet,raws['activity_anchor'],decode,a,input_pins=pins,processing_begin=g['processing_begin']);result=dict(status='complete',audit=audited,fit_authorized=False)
        store.put('result.private.json',result,16*1024*1024);parent.tick(g['processing_begin']);return result
    except BaseException as error:
        # Use fresh Store so reserved failure headroom is available. Evidence is
        # durable BEFORE a post-deadline check, never an accepted partial packet.
        failure=dict(status='incomplete',exception_type=type(error).__name__,reason=str(error)[:128],no_retry=True)
        if np is not None:
            if m is not None and isinstance(error,m.FeatureError):failure.update(partial_rows=diagnostic(error.partial_rows,np),observed_samples=error.observed_samples,diagnostics=diagnostic(error.diagnostics,np))
            if semantic is not None and isinstance(error,semantic.AuditError):failure.update(observed_samples=error.observed_samples,diagnostics=diagnostic(error.diagnostics,np))
            if packet is not None:failure['produced_packet']=diagnostic(packet,np)
        c.Store(out).put('failure.private.json',failure,16*1024*1024);raise

"""Independent hash/barrier/trace verification; no production imports or forwards."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import zipfile
import numpy as np

PROTOCOL='8d4e2e3ed43c072356d539bb822316ed8f8d2cee3213ff8a02ef419a6f33777b'
SOURCE_MANIFEST='af88e1269ef1678c5434a0c5d483adebc24fac7374baded4579ea83fdc8df60f'
PLAN='8bb46ac1ae4296a5aa20ab4724491052ec729c96dba04cf2dd7d3656afe5323d'
BASELINE_STATE='4acb798e74e7263b3a570c01008f66271440e9d951bb012448ddc359f567143e'
FIT_IDS='1b9ad34f6e7c976311a8edd07e24cd9ef075f579754306b4092bb6af312d7c14'
FITS=tuple(f'{arm}_{seed}' for seed in (20261011,20261012) for arm in ('source_uniform','discrete_1_3_5'))
PAIRED=('event_order','station_order','station_count_draw','station_rank_draw','label_draw','model_rng')
OPTIMIZER={'amsgrad':False,'betas':[.9,.999],'eps':1e-8,'gradient_clip_global_norm':1,'learning_rate':9e-6,'name':'torch.optim.Adam','schedule':'none','source_relation':'1e-4 * 0.3**2; not inferred actual epoch97 LR','weight_decay':0}
MIB=1024**2

def contained(root,name):
    root=Path(root).resolve();p=Path(name)
    if p.is_absolute() or '..' in p.parts or not p.parts:raise ValueError('relative nonsymlink artifact required')
    f=root/p
    if any((root/Path(*p.parts[:i])).is_symlink() for i in range(1,len(p.parts)+1)) or not f.resolve().is_relative_to(root):raise ValueError('artifact escaped root')
    return f

def file_pin(path,cap=1024*MIB):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('bounded nonsymlink file required')
    h=hashlib.sha256();size=0
    with path.open('rb') as f:
        while b:=f.read(1024*MIB//16):
            size+=len(b)
            if size>cap:raise ValueError('artifact grew beyond bound')
            h.update(b)
    return {'bytes':size,'sha256':h.hexdigest()}

def json_file(path,cap=16*MIB):
    file_pin(path,cap)
    with Path(path).open('rb') as f:body=f.read(cap+1)
    if len(body)>cap:raise ValueError('JSON grew')
    return json.loads(body)

def ids_digest(ids):return hashlib.sha256('\n'.join(ids).encode()).hexdigest()

def grid(root,complete_pin,execution):
    root=Path(root)
    if root.is_symlink() or execution!={'worker_exit_code':0,'supervisor_exit_code':0,'preservation_complete':True}:raise ValueError('normal worker/supervisor exit and preserved handoff required')
    complete=contained(root,'COMPLETE.json')
    if file_pin(complete,16*MIB)!=complete_pin:raise ValueError('independently supplied COMPLETE pin mismatch')
    m=json_file(complete)
    expected={'schema':'chile-clock-grid-complete-v1','protocol_sha256':PROTOCOL,'source_manifest_sha256':SOURCE_MANIFEST,'plan_sha256':PLAN,'test_reads':0,'selection':'fixed_final6','fits':4}
    if any(m.get(k)!=v for k,v in expected.items()):raise ValueError('completion barrier mismatch')
    names={'STARTED.json','grid_identity.json','TRAINING_COMPLETE.json','report.json'}|{f'{fit}/{n}' for fit in FITS for n in ('FIT_COMPLETE.json','INIT.json','history.json','model.pth','latest.pth')}|{f'{split}_{fit}_predictions.npz' for split in ('calibration','dev') for fit in (*FITS,'starting_epoch97')}
    if set(m.get('artifacts_sha256',{}))!=names:raise ValueError('exact completed34 artifact set required')
    pins={}
    for name,digest in m['artifacts_sha256'].items():
        p=contained(root,name);pins[name]=file_pin(p)
        if not re.fullmatch('[0-9a-f]{64}',digest) or pins[name]['sha256']!=digest:raise ValueError('completed member checksum mismatch')
    started=json_file(root/'STARTED.json')
    if started!={k:expected[k] for k in ('protocol_sha256','source_manifest_sha256','plan_sha256')}:raise ValueError('started identity differs')
    training=json_file(root/'TRAINING_COMPLETE.json')
    if training.get('keys')!=list(FITS) or training.get('fit_completion_sha256')!={k:pins[k+'/FIT_COMPLETE.json']['sha256'] for k in FITS}:raise ValueError('all-four fit barrier differs')
    identity=json_file(root/'grid_identity.json')
    if identity.get('protocol_sha256')!=PROTOCOL or identity.get('source_manifest_sha256')!=SOURCE_MANIFEST or identity.get('epochs')!=6 or identity.get('batch_size')!=64 or identity.get('optimizer')!=OPTIMIZER or identity.get('baseline_initial_state_sha256')!=BASELINE_STATE or identity.get('fit_ids_sha256')!=FIT_IDS:raise ValueError('fixed fit identity changed')
    receipts={};histories={};initial={}
    for fit in FITS:
        arm,seed=fit.rsplit('_',1);wanted=identity|{'arm':arm,'seed':int(seed)}
        r=json_file(root/fit/'FIT_COMPLETE.json');h=json_file(root/fit/'history.json');i=json_file(root/fit/'INIT.json')
        if r.get('identity')!=wanted or r.get('completed_epochs')!=6 or r.get('files_sha256')!={n:pins[fit+'/'+n]['sha256'] for n in ('model.pth','history.json','INIT.json','latest.pth')}:raise ValueError('fit receipt/identity differs')
        if i.get('identity')!=wanted or i.get('model_state_sha256')!=BASELINE_STATE or i.get('optimizer_state_entries')!=0:raise ValueError('initial-state/fresh optimizer changed')
        receipts[fit]=r;histories[fit]=h;initial[fit]=i
    for seed in (20261011,20261012):
        a=initial[f'source_uniform_{seed}'];b=initial[f'discrete_1_3_5_{seed}']
        for k in ('model_rng_sha256','generator_state_sha256'):
            if a.get(k)!=b.get(k) or not re.fullmatch('[0-9a-f]{64}',a.get(k,'')):raise ValueError('within-seed initial RNG differs')
    return {'pins':pins,'complete':m,'identity':identity,'histories':histories,'fit_receipts':receipts}

def split_and_targets(split,run,manifest,metadata_path,expected_metadata_pin):
    if file_pin(metadata_path,64*MIB)!=expected_metadata_pin:raise ValueError('original metadata checksum mismatch')
    if set(split)!={'fit','calibration','dev'}:raise ValueError('original3 splits required')
    train_end,dev_end=manifest['author_split_boundaries'];ids=[];rows=[];lookup={}
    for name in ('fit','calibration','dev'):
        b=split[name];ix=b['source_rows'];event_ids=b['event_ids']
        if not event_ids or len(event_ids)!=len(ix) or ix!=sorted(ix) or any(type(x)!=int for x in ix) or ids_digest(event_ids)!=b['ids_sha256'] or b['ids_sha256']!=run[name+'_ids_sha256'] or len(ix)!=run[name+'_events']:raise ValueError('original split order/digest/count changed')
        if any(not (0<=r<train_end if name!='dev' else train_end<=r<dev_end) for r in ix):raise ValueError('original split boundary changed')
        ids+=event_ids;rows+=ix;lookup.update(zip(ix,event_ids))
    if len(set(ids))!=len(ids) or len(set(rows))!=len(rows) or sorted(rows)!=list(range(dev_end)):raise ValueError('overlap/missing source row')
    values={};observed=[]
    with Path(metadata_path).open(newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=['EVENT','MA','TIME','source_row_index','benchmark_split']:raise ValueError('metadata schema differs')
        for ix,row in enumerate(reader):
            if ix>=dev_end or row['EVENT']!=lookup[ix] or int(row['source_row_index'])!=ix or row['benchmark_split']!=('train' if ix<train_end else 'dev'):raise ValueError('metadata identity/order changed')
            y,t=float(row['MA']),float(row['TIME'])
            if not math.isfinite(y) or not math.isfinite(t):raise ValueError('nonfinite preserved label/time')
            values[row['EVENT']]=y;observed.append(row['EVENT'])
    if len(observed)!=dev_end or manifest['cache_rows']!=dev_end:raise ValueError('metadata denominator changed')
    for name,event_ids in (('train',observed[:train_end]),('dev',observed[train_end:])):
        if ids_digest(event_ids)!=manifest['splits'][name]['ids_sha256']:raise ValueError('author TRAIN/DEV source identity changed')
    if ids_digest([e for e in split['fit']['event_ids']])!=FIT_IDS:raise ValueError('frozen TRAIN-fit identity changed')
    repeat=0
    for e in split['fit']['event_ids']:
        repeat+=next((2**(k-1) for k in range(4,9) if k<values[e]<=k+1),1)
    return {'targets':{name:np.asarray([values[e] for e in split[name]['event_ids']],dtype=np.float64) for name in split},'ids':{name:split[name]['event_ids'] for name in split},'training_examples_per_epoch':repeat}

def traces(histories,expected_examples):
    required=set(PAIRED)|{'clock','final_mask'};comparisons={}
    sizes=[64]*(expected_examples//64)+([expected_examples%64] if expected_examples%64 else [])
    for fit,h in histories.items():
        if not isinstance(h,list) or len(h)!=6:raise ValueError('six completed histories required')
        for epoch,r in enumerate(h,1):
            t=r['trace'];counts=t['clock_counts']
            if r.get('epoch')!=epoch or r.get('learning_rate')!=9e-6 or any(not math.isfinite(r[k]) for k in ('train_loss','seconds','last_gradient_norm')) or r['seconds']<0 or r['last_gradient_norm']<0:raise ValueError('epoch/LR/finite history changed')
            if t['examples']!=expected_examples or t['batches']!=len(sizes) or t['batch_sizes']!=sizes or len(counts)!=3000 or any(type(n)!=int or n<0 for n in counts) or sum(counts)!=expected_examples:raise ValueError('recorded draw budget/remainder changed')
            if set(t['sha256'])!=required or any(not re.fullmatch('[0-9a-f]{64}',s) for s in t['sha256'].values()):raise ValueError('invalid trace hash set')
            allowed=set(range(100,3000)) if fit.startswith('source_uniform_') else {600,800,1000}
            if any(n and ix not in allowed for ix,n in enumerate(counts)):raise ValueError('clock outside frozen support')
    for seed in (20261011,20261012):
        pair=[]
        for a,b in zip(histories[f'source_uniform_{seed}'],histories[f'discrete_1_3_5_{seed}']):
            if any(a['trace']['sha256'][k]!=b['trace']['sha256'][k] for k in PAIRED):raise ValueError('recorded nonclock pairing differs')
            pair.append({'epoch':a['epoch'],'paired_fields':6,'equal_recorded_digests':True})
        comparisons[str(seed)]=pair
    return {'passed':True,'recorded_pairing_only':True,'examples_per_epoch':expected_examples,'seeds':comparisons}

def prediction_archive(path,expected_pin):
    if file_pin(path,32*MIB)!=expected_pin:raise ValueError('prediction archive pin mismatch')
    with zipfile.ZipFile(path) as z:
        members=z.infolist()
        if len(members)!=26 or len({m.filename for m in members})!=26 or sum(m.file_size for m in members)>64*MIB or any(m.file_size>64*MIB or not m.filename.endswith('.npy') or '/' in m.filename for m in members):raise ValueError('bounded26-array archive required')
    with np.load(path,allow_pickle=False) as arrays:return {k:arrays[k] for k in arrays.files}

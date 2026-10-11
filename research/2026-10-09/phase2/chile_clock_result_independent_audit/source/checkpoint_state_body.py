"""Self-contained exact-runtime CPU-only restricted artifact checks; no forwards."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import signal

MAX_BYTES=1024**3
FITS=tuple(f'{arm}_{seed}' for seed in (20261011,20261012) for arm in ('source_uniform','discrete_1_3_5'))

def pin(path,cap=MAX_BYTES):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('bounded nonsymlink checkpoint required')
    h=hashlib.sha256();size=0
    with path.open('rb') as f:
        while b:=f.read(8*1024**2):
            size+=len(b)
            if size>cap:raise ValueError('checkpoint grew')
            h.update(b)
    return {'bytes':size,'sha256':h.hexdigest()}

def digest(state):
    h=hashlib.sha256()
    for name in sorted(state):
        value=state[name].detach().cpu().contiguous()
        h.update(name.encode()+b'\0')
        h.update(json.dumps([str(value.dtype),list(value.shape)],separators=(',',':')).encode()+b'\0')
        h.update(value.numpy().tobytes(order='C'))
    return h.hexdigest()

def load_checkpoint(path,expected,torch):
    if pin(path)!=expected:raise ValueError('checkpoint pin mismatch before deserialization')
    return torch.load(path,map_location='cpu',weights_only=True)

def inspect(request,torch,numpy):
    runtime={'python':sys.version,'torch':str(torch.__version__),'numpy':numpy.__version__,'byteorder':sys.byteorder}
    if runtime!=request['expected_runtime']:raise ValueError('exact recorded restricted-load runtime required')
    if set(request['fits'])!=set(FITS):raise ValueError('all4 final6 fits required')
    if request.get('execution')!={'worker_exit_code':0,'supervisor_exit_code':0,'preservation_complete':True}:raise ValueError('completed preserved execution required')
    c=request['complete']
    if pin(c['path'],16*1024**2)!=c['pin']:raise ValueError('completed barrier pin mismatch')
    completed=json.loads(Path(c['path']).read_bytes())
    if any(completed.get(k)!=v for k,v in {'schema':'chile-clock-grid-complete-v1','fits':4,'test_reads':0,'selection':'fixed_final6','protocol_sha256':'8d4e2e3ed43c072356d539bb822316ed8f8d2cee3213ff8a02ef419a6f33777b','source_manifest_sha256':'af88e1269ef1678c5434a0c5d483adebc24fac7374baded4579ea83fdc8df60f','plan_sha256':'8bb46ac1ae4296a5aa20ab4724491052ec729c96dba04cf2dd7d3656afe5323d'}.items()):raise ValueError('all4 final completion barrier required')
    baseline=request['baseline']
    original=load_checkpoint(baseline['path'],baseline['pin'],torch)
    if set(original)!={'model','config','selected_epoch'} or original['selected_epoch']!=97:raise ValueError('original selected97 checkpoint schema differs')
    initial_digest=digest(original['model'])
    if initial_digest!=baseline['expected_state_sha256']:raise ValueError('original initial tensor state differs')
    del original
    states={};checks={}
    for fit,member in request['fits'].items():
        if any(completed['artifacts_sha256'].get(fit+'/'+name+'.pth')!=member[name]['pin']['sha256'] for name in ('model','latest')):raise ValueError('requested checkpoint differs from completed member')
        final=load_checkpoint(member['model']['path'],member['model']['pin'],torch)
        latest=load_checkpoint(member['latest']['path'],member['latest']['pin'],torch)
        if set(final)!={'schema','model','identity','completed_epochs'} or final['schema']!='chile-clock-final-v1' or final['completed_epochs']!=6 or final['identity']!=member['identity']:raise ValueError('final6 schema/identity mismatch')
        required={'schema','completed_epoch','model','optimizer','streams','model_rng','python_rng','numpy_rng','identity','history','resume_supported'}
        if set(latest)!=required or latest['schema']!='chile-clock-completed-epoch-v1' or latest['completed_epoch']!=6 or latest['identity']!=final['identity'] or latest['history']!=member['history'] or latest['resume_supported'] is not False:raise ValueError('latest6 schema/identity/history mismatch')
        for model in (final['model'],latest['model']):
            if not model or not all(isinstance(v,torch.Tensor) and torch.isfinite(v).all().item() for v in model.values()):raise ValueError('nonfinite/non-tensor model state')
        final_digest=digest(final['model']);latest_digest=digest(latest['model'])
        if final_digest!=latest_digest:raise ValueError('final/latest tensor state differs')
        optimizer=latest['optimizer'];groups=optimizer['param_groups'];expected_steps=sum(r['trace']['batches'] for r in member['history'])
        if len(groups)!=1:raise ValueError('single fresh Adam group required')
        g=groups[0]
        if any(g.get(k)!=v for k,v in {'lr':9e-6,'betas':(.9,.999),'eps':1e-8,'weight_decay':0,'amsgrad':False}.items()):raise ValueError('saved Adam configuration differs')
        if not g['params'] or len(set(g['params']))!=len(g['params']) or set(g['params'])!=set(optimizer['state']):raise ValueError('optimizer parameter coverage differs')
        for s in optimizer['state'].values():
            if set(s)!={'step','exp_avg','exp_avg_sq'} or float(s['step'])!=expected_steps or not all(torch.isfinite(s[k]).all().item() for k in s):raise ValueError('saved Adam steps/state invalid')
        if set(latest['streams'])!={'clock','station_count','station_rank','label'} or set(latest['model_rng'])!={'cpu','cuda'}:raise ValueError('saved RNG fields differ')
        states[fit]={'augmentation':digest({k:latest['streams'][k] for k in ('station_count','station_rank','label')}),'global_model':digest(latest['model_rng']),'python':hashlib.sha256(json.dumps(latest['python_rng'],separators=(',',':'),allow_nan=False).encode()).hexdigest(),'numpy':hashlib.sha256(json.dumps(latest['numpy_rng'],sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()}
        checks[fit]={'completed_epochs':6,'final_model_state_sha256':final_digest,'latest_model_state_sha256':latest_digest,'identical_final_latest_state':True,'all_model_and_optimizer_values_finite':True,'optimizer_steps':expected_steps,'optimizer_configuration_matches':True}
        del final,latest,optimizer
    paired={}
    for seed in (20261011,20261012):
        left=states[f'source_uniform_{seed}'];right=states[f'discrete_1_3_5_{seed}']
        if left!=right:raise ValueError('persisted nonclock RNG states differ within seed')
        paired[str(seed)]={'augmentation_global_model_python_numpy_equal':True,'clock_state_exempt':True,'state_sha256':left}
    return {'schema':'chile-clock-independent-checkpoint-state-v1','all_checks_pass':True,'runtime':runtime,'baseline_initial_state_sha256':initial_digest,'baseline_pin':baseline['pin'],'fits':checks,'paired_rng':paired,'production_imports':0,'forwards':0,'optimizer_steps_executed':0,'TEST_reads':0}

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True);p.add_argument('--request-sha256',required=True);a=p.parse_args()
    if pin(a.request,16*1024**2)['sha256']!=a.request_sha256:raise ValueError('caller-pinned private request required')
    request=json.loads(a.request.read_bytes())
    def deadline(signum,frame):raise TimeoutError('restricted state replay1200s ceiling; incomplete')
    previous=signal.signal(signal.SIGALRM,deadline);signal.setitimer(signal.ITIMER_REAL,1200)
    try:
        import torch
        import numpy
        torch.set_num_threads(2)
        result=inspect(request,torch,numpy);result.update(source_sha256=pin(Path(__file__),4*1024**2)['sha256'],request_sha256=a.request_sha256)
        print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)

if __name__=='__main__':main()

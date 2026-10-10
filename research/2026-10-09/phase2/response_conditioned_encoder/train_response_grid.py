"""Fixed eight-run response-encoder grid. Dry-run by default; no VAL/TEST input.

The production CLI accepts one completed shared TRAIN export, exact source-bundle
hash and a new output directory. Children have600s caps and the grid4800s of
training wall time. Metrics are a separate bounded CPU stage, never fit feedback.
"""
import os
os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG',':4096:8')
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ.setdefault(_key,'2')
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import torch
from torch.nn import functional as F
from response_model import ResponseConditionedModel
from response_data import (CompletedExport,file_sha,fit_export_normalizers,fitting_population_digest,gain_reexpression)
from response_metrics import (CENTERS,SEEDS,DEADLINES,SUBSETS,checked_p,scores,mean_action,point,deltas,paired_bootstrap,primary_gate)

ARMS=('A','B','C','D')
PROTOCOL_SHA='403fe4bafabc11dad71b8a02d16e98a6b8d8c3a5c95ca89a812a5193a284f1b8'
PARENT_SHA='0993d321e4e21a0e612c05b01189d54b2577f5ebb238ee52ebd50300109250bb'
SOURCE_NAMES=('train_response_grid.py','response_metrics.py','response_model.py','response_data.py','frozen_protocol_v1.md')
EPOCHS=10;BATCH=512;RUN_SECONDS=600;GRID_SECONDS=4800


def atomic_json(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.partial')
    tmp.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n');tmp.replace(path)


def array_sha(value):
    a=np.asarray(value);h=hashlib.sha256();h.update(str(a.dtype).encode());h.update(str(a.shape).encode());h.update(a.tobytes());return h.hexdigest()


def state_sha(state):
    h=hashlib.sha256()
    for name,value in sorted(state.items()):h.update(name.encode()+b'\0');h.update(array_sha(value.detach().cpu().numpy()).encode())
    return h.hexdigest()


def verify_bundle(path,expected):
    if file_sha(path)!=expected:raise ValueError('Source-bundle manifest not pinned')
    manifest=json.loads(Path(path).read_text())
    if set(manifest['files'])!=set(SOURCE_NAMES):raise ValueError('Wrong source-bundle allowlist')
    for name,digest in manifest['files'].items():
        if file_sha(Path(__file__).with_name(name))!=digest:raise ValueError('Source changed: '+name)
    if manifest['files']['frozen_protocol_v1.md']!=PROTOCOL_SHA:raise ValueError('Protocol changed')
    return manifest


def runtime():
    if os.environ.get('CUBLAS_WORKSPACE_CONFIG')!=':4096:8':raise ValueError('Wrong deterministic CUBLAS setting')
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    return {'torch':torch.__version__,'numpy':np.__version__,'cuda':torch.version.cuda,
        'cudnn':torch.backends.cudnn.version(),'deterministic':torch.are_deterministic_algorithms_enabled(),
        'tf32_matmul':torch.backends.cuda.matmul.allow_tf32,'tf32_cudnn':torch.backends.cudnn.allow_tf32,
        'cublas_workspace_config':os.environ['CUBLAS_WORKSPACE_CONFIG'],'threads':torch.get_num_threads()}


def schedules(populations,seed,epoch):
    """Target-free independent permutation/cycles; sameD draws at each horizon."""
    if set(populations)!=set(DEADLINES) or any(len(v)==0 for v in populations.values()):raise ValueError('Three nonempty fit populations required')
    d=max(len(v) for v in populations.values());result={}
    for t in DEADLINES:
        rows=np.asarray(populations[t],dtype=np.int64);rng=np.random.default_rng(np.random.SeedSequence([seed,epoch,t]))
        pieces=[];remaining=d
        while remaining:
            p=rng.permutation(rows);pieces.append(p[:remaining]);remaining-=min(remaining,len(rows))
        result[t]=np.concatenate(pieces)
    return result


def supervised_loss(logits,target,normalized_weight):
    if logits.ndim!=2 or logits.shape[1]!=66 or target.shape!=(len(logits),) or normalized_weight.shape!=target.shape:raise ValueError('Loss shape mismatch')
    bins=torch.arange(66,device=logits.device,dtype=logits.dtype)*.1
    prediction=(logits.softmax(1)*bins).sum(1)
    labels=torch.floor(target/.1+1e-5).long().clamp(0,65)
    per=(1+5*(target-3.5).clamp_min(0))*F.huber_loss(prediction,target,reduction='none',delta=1.)+.075*F.cross_entropy(logits,labels,reduction='none')
    return (per*normalized_weight).mean()


def batch(dataset,rows,t,device,arm,seed,epoch,augment=False):
    value=dataset.inference_batch(rows,t)
    if augment:
        value['counts'],value['sensitivity'],value['static']=gain_reexpression(value['counts'],value['sensitivity'],value['static'],dataset.metadata['source_row_index'][rows],seed,epoch)
    return {k:torch.as_tensor(v,device=device) for k,v in value.items()}


def prepare(dataset,path):
    path=Path(path);path.mkdir(parents=True,exist_ok=False)
    normals,provenance=fit_export_normalizers(dataset)
    np.savez(path/'normalizers.npz',**normals)
    provenance['artifact_sha256']=file_sha(path/'normalizers.npz')
    atomic_json(path/'normalizers.json',provenance)
    return provenance


def read_prepared(dataset,path):
    path=Path(path);prov=json.loads((path/'normalizers.json').read_text())
    if prov['export_manifest_sha256']!=file_sha(dataset.path/'manifest.json') or prov['normalizer_source_sha256']!=file_sha(Path(__file__).with_name('response_data.py')):
        raise ValueError('Wrong normalization source/export')
    if prov['metadata_fit_population']!=fitting_population_digest(dataset.metadata):raise ValueError('Wrong metadata fitting population')
    if prov['per_deadline_fit_population']!={str(t):fitting_population_digest(dataset.metadata,t) for t in DEADLINES}:raise ValueError('Wrong prefix fitting population')
    if prov['labels_used'] or prov['held_rows_used'] or file_sha(path/'normalizers.npz')!=prov['artifact_sha256']:raise ValueError('Invalid normalization artifact')
    with np.load(path/'normalizers.npz',allow_pickle=False) as f:normals={k:f[k] for k in f.files}
    if {k:hashlib.sha256(np.asarray(v,dtype='<f4').tobytes()).hexdigest() for k,v in normals.items()}!=prov['arrays_sha256']:raise ValueError('Normalizer arrays changed')
    return normals,prov


def fit_model(dataset,normals,arm,seed,device,epochs=EPOCHS,batch_size=BATCH):
    """Testable invented-data core. Production caller fixes10epochs/batch512."""
    if arm not in ARMS or seed not in SEEDS:raise ValueError('Unknown fixed arm/seed')
    torch.manual_seed(seed)
    if device.startswith('cuda'):torch.cuda.manual_seed_all(seed)
    model=ResponseConditionedModel(arm,normals).to(device);initial=state_sha(model.state_dict())
    optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=epochs,eta_min=3e-5)
    populations={t:dataset.valid_rows('fit',t) for t in DEADLINES}
    m=dataset.metadata;weight_mean={t:float(m['sampling_weight'][rows].mean()) for t,rows in populations.items()}
    history=[];orders=[];steps=0
    for epoch in range(epochs):
        model.train();order=schedules(populations,seed,epoch);orders.append({str(t):array_sha(order[t]) for t in DEADLINES})
        epoch_loss=0.;draws=0;d=len(order[1])
        for start in range(0,d,batch_size):
            optimizer.zero_grad(set_to_none=True);total=0.
            for t in DEADLINES:
                ix=order[t][start:start+batch_size];x=batch(dataset,ix,t,device,arm,seed,epoch,augment=arm=='D')
                y=torch.as_tensor(m['targets'][ix],dtype=torch.float32,device=device)
                w=torch.as_tensor(m['sampling_weight'][ix]/weight_mean[t],dtype=torch.float32,device=device)
                loss=supervised_loss(model.forward_prefix(x,t),y,w)/3
                if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
                loss.backward();total+=float(loss.detach())
            norm=torch.nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True)
            optimizer.step();steps+=1;n=min(batch_size,d-start);epoch_loss+=total*n;draws+=n
        history.append({'epoch':epoch+1,'training_loss':epoch_loss/draws,'lr':optimizer.param_groups[0]['lr'],'draws_per_horizon':draws})
        scheduler.step()
    return model,{'initial_state_sha256':initial,'final_state_sha256':state_sha(model.state_dict()),'order_sha256':orders,
        'steps':steps,'history':history,'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),
        'fit_rows':{str(t):len(v) for t,v in populations.items()},'fit_weight_mean':weight_mean}


def predict(model,dataset,device,batch_size=BATCH):
    model.eval();result={};diagnostics={}
    with torch.no_grad():
        for t in DEADLINES:
            for subset in SUBSETS:
                rows=dataset.valid_rows(subset,t)
                if not len(rows):raise ValueError('Empty held evaluation panel')
                probabilities=[];shift=[];l1=[]
                for start in range(0,len(rows),batch_size):
                    ix=rows[start:start+batch_size]
                    p=model.forward_prefix(batch(dataset,ix,t,device,model.arm,0,0),t).double().softmax(1).cpu().numpy()
                    re=model.forward_prefix(batch(dataset,ix,t,device,model.arm,20261012,0,augment=True),t).double().softmax(1).cpu().numpy()
                    probabilities.append(p);shift.extend(abs(mean_action(p)-mean_action(re)).tolist());l1.extend(abs(p-re).sum(1).tolist())
                key=f'{t}_{subset}';result['rows_'+key]=rows;result['p_'+key]=np.concatenate(probabilities)
                w=dataset.metadata['sampling_weight'][rows]
                diagnostics[key]={'fixed_reexpression_seed':20261012,'weighted_mean_abs_point_shift':float(np.average(shift,weights=w)),
                    'weighted_pmf_l1':float(np.average(l1,weights=w)),'interpretation':'Sensitivity diagnostic, not structural invariance'}
    return result,diagnostics


def run_one(args):
    started=time.monotonic();source=verify_bundle(args.bundle,args.bundle_sha256);env=runtime()
    if args.device!='cuda' or not torch.cuda.is_available():raise ValueError('Production pilot requires authorized existing CUDA worker')
    dataset=CompletedExport(args.export)
    if dataset.manifest.get('polarization_manifest_sha256')!=PARENT_SHA or dataset.manifest.get('protocol_sha256')!=PROTOCOL_SHA:raise ValueError('Wrong frozen shared population/protocol')
    normals,prov=read_prepared(dataset,args.prepared)
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    info={'status':'started','arm':args.arm,'seed':args.seed,'epochs':EPOCHS,'batch_size':BATCH,'protocol_sha256':PROTOCOL_SHA,
        'bundle_sha256':args.bundle_sha256,'export_manifest_sha256':file_sha(dataset.path/'manifest.json'),
        'normalizers_sha256':file_sha(args.prepared/'normalizers.json'),'runtime':env,'device':torch.cuda.get_device_name(0),
        'objective':'weighted Huber(delta1,beta5,threshold3.5)+.075CE; restoration weights normalized over each valid fitting population',
        'source_files':source['files']}
    atomic_json(output/'manifest.json',info)
    model,fit=fit_model(dataset,normals,args.arm,args.seed,args.device)
    checkpoint={'model':model.state_dict(),'optimizer':fit.pop('optimizer'),'scheduler':fit.pop('scheduler'),
        'arm':args.arm,'seed':args.seed,'normalizers':normals,'normalizer_provenance':prov,'fit':fit,'identity':info}
    torch.save(checkpoint,output/'checkpoint.pt.partial');(output/'checkpoint.pt.partial').replace(output/'checkpoint.pt')
    predictions,diagnostic=predict(model,dataset,args.device)
    np.savez(output/'predictions.npz',**predictions);atomic_json(output/'gain_diagnostic.json',diagnostic)
    verify_bundle(args.bundle,args.bundle_sha256)
    if file_sha(dataset.path/'manifest.json')!=info['export_manifest_sha256'] or file_sha(args.prepared/'normalizers.json')!=info['normalizers_sha256']:raise ValueError('Input changed during run')
    for name,digest in dataset.manifest['outputs_sha256'].items():
        if file_sha(dataset.path/name)!=digest:raise ValueError('Export array changed during run')
    info.update(status='complete',fit=fit,seconds=time.monotonic()-started,
        outputs_sha256={n:file_sha(output/n) for n in ('checkpoint.pt','predictions.npz','gain_diagnostic.json')})
    if info['seconds']>RUN_SECONDS:raise TimeoutError('Run exceeded fixed budget')
    atomic_json(output/'manifest.json',info);atomic_json(output/'COMPLETE.json',{'manifest_sha256':file_sha(output/'manifest.json')})


def verify_fit_protocol(fit,dataset,seed):
    populations={t:dataset.valid_rows('fit',t) for t in DEADLINES};d=max(map(len,populations.values()))
    expected_orders=[{str(t):array_sha(v) for t,v in schedules(populations,seed,epoch).items()} for epoch in range(EPOCHS)]
    means={str(t):float(dataset.metadata['sampling_weight'][rows].mean()) for t,rows in populations.items()}
    if (fit['fit_rows']!={str(t):len(v) for t,v in populations.items()} or fit['fit_weight_mean']!=means or
        fit['steps']!=EPOCHS*math.ceil(d/BATCH) or fit['order_sha256']!=expected_orders or len(fit['history'])!=EPOCHS):
        raise ValueError('Run did not complete the fixed schedule/budget')
    for i,row in enumerate(fit['history']):
        if row['epoch']!=i+1 or row['draws_per_horizon']!=d or not math.isfinite(row['training_loss']):
            raise ValueError('Incomplete/invalid epoch history')


def completed_runs(root,dataset,bundle_sha):
    # One prepared artifact is shared by every arm AND both seeds.
    read_prepared(dataset,Path(root)/'prepared')
    normalizer_sha=file_sha(Path(root)/'prepared'/'normalizers.json')
    records={};predictions={}
    for arm in ARMS:
        for seed in SEEDS:
            path=Path(root)/f'{arm}_{seed}';complete=json.loads((path/'COMPLETE.json').read_text())
            if complete['manifest_sha256']!=file_sha(path/'manifest.json'):raise ValueError('Run completion mismatch')
            m=json.loads((path/'manifest.json').read_text())
            if m['status']!='complete' or m['arm']!=arm or m['seed']!=seed or m['epochs']!=EPOCHS or m['batch_size']!=BATCH or m['bundle_sha256']!=bundle_sha or m['protocol_sha256']!=PROTOCOL_SHA or m['export_manifest_sha256']!=file_sha(dataset.path/'manifest.json'):raise ValueError('Run protocol/source/identity mismatch')
            if m['normalizers_sha256']!=normalizer_sha:raise ValueError('Run does not use shared grid normalizers')
            verify_fit_protocol(m['fit'],dataset,seed)
            if set(m['outputs_sha256'])!={'checkpoint.pt','predictions.npz','gain_diagnostic.json'}:raise ValueError('Missing run artifact')
            if not math.isfinite(m['seconds']) or m['seconds']>RUN_SECONDS:raise ValueError('Run exceeded prespecified budget')
            for name,digest in m['outputs_sha256'].items():
                if file_sha(path/name)!=digest:raise ValueError('Run artifact changed')
            with np.load(path/'predictions.npz',allow_pickle=False) as f:
                for t in DEADLINES:
                    for subset in SUBSETS:
                        key=f'{t}_{subset}';rows=dataset.valid_rows(subset,t)
                        if not np.array_equal(f['rows_'+key],rows):raise ValueError('Prediction row order mismatch')
                        predictions[(arm,seed,t,subset)]=checked_p(f['p_'+key],len(rows))
            records[(arm,seed)]=m
    for seed in SEEDS:
        reference=records[('A',seed)]['fit']
        for arm in ARMS:
            fit=records[(arm,seed)]['fit']
            for key in ('initial_state_sha256','order_sha256','steps','fit_rows','fit_weight_mean'):
                if fit[key]!=reference[key]:raise ValueError('Unmatched training control: '+key)
    return records,predictions


def report_grid(root,dataset,bundle_sha):
    records,predictions=completed_runs(root,dataset,bundle_sha);m=dataset.metadata;report={'scores':[],'comparisons':[],'matched_event_panels':[],'population_audit':[],
        'protocol_sha256':PROTOCOL_SHA,'bundle_sha256':bundle_sha,'primary':'C minus B, PMF mean','runs':{f'{a}_{s}':{'manifest_sha256':file_sha(Path(root)/f'{a}_{s}'/'manifest.json')} for a,s in records}}
    ensemble={}
    for t in DEADLINES:
        for subset in SUBSETS:
            rows=dataset.valid_rows(subset,t);y=m['targets'][rows];w=m['sampling_weight'][rows];event=m['source_id'][rows]
            selected=np.flatnonzero(m['subset']==subset);lost=set(m['source_id'][selected])-set(event)
            codes,counts=np.unique(m['invalid_codes'][selected,DEADLINES.index(t)],return_counts=True)
            report['population_audit'].append({'seconds':t,'subset':subset,'selected_records':len(selected),'valid_records':len(rows),
                'selected_events':len(np.unique(m['source_id'][selected])),'valid_events':len(np.unique(event)),
                'lost_event_ids':sorted(lost),'invalid_code_counts':{str(int(k)):int(v) for k,v in zip(codes,counts)}})
            family_hot=m['static'][rows,:6]
            if not np.isin(family_hot,[0,1]).all() or not (family_hot.sum(1)==1).all():raise ValueError('Invalid reporting family one-hot')
            strata={'unit':m['native_units'][rows],'family':np.array(['HH','EH','HN','HL','EN','unknown'])[family_hot.argmax(1)],'station_group':m['station_group'][rows]}
            by_arm={}
            for arm in ARMS:
                by_arm[arm]={};ps={s:predictions[(arm,s,t,subset)] for s in SEEDS};ensemble[(arm,t,subset)]=np.mean(list(ps.values()),axis=0)
                for name,p in [(str(s),ps[s]) for s in SEEDS]+[('ensemble',ensemble[(arm,t,subset)])]:
                    value=scores(p,y,w,event);by_arm[arm][name]=value
                    row={'arm':arm,'seed':name,'seconds':t,'subset':subset,'metrics':value,'strata':{}}
                    for field,values in strata.items():
                        row['strata'][field]={str(group):scores(p[values==group],y[values==group],w[values==group],event[values==group]) for group in np.unique(values)}
                    report['scores'].append(row)
            a=ensemble[('C',t,subset)];b=ensemble[('B',t,subset)]
            report['comparisons'].append({'seconds':t,'subset':subset,'m4_events':len(np.unique(event[y>=4])),
                'valid_fraction':len(rows)/int((m['subset']==subset).sum()),
                'seed_deltas':{str(s):deltas(by_arm['C'][str(s)]['mean'],by_arm['B'][str(s)]['mean']) for s in SEEDS},
                'ensemble_deltas':deltas(by_arm['C']['ensemble']['mean'],by_arm['B']['ensemble']['mean']),
                'bootstrap':paired_bootstrap(a,b,y,w,event),
                'individual_event_mae_deltas':{e:v['mae']-by_arm['B']['ensemble']['mean']['individual_events'][e]['mae'] for e,v in by_arm['C']['ensemble']['mean']['individual_events'].items()}})
    for t in DEADLINES:
        panels={s:dataset.valid_rows(s,t) for s in SUBSETS};common=set(m['source_id'][panels['eval_seen']])&set(m['source_id'][panels['eval_held']])
        for subset,rows in panels.items():
            keep=np.isin(m['source_id'][rows],list(common))
            for arm in ARMS:
                report['matched_event_panels'].append({'seconds':t,'subset':subset,'arm':arm,'common_events':len(common),
                    'mean_metrics':point(mean_action(ensemble[(arm,t,subset)])[keep],m['targets'][rows][keep],m['sampling_weight'][rows][keep],m['source_id'][rows][keep]) if keep.any() else None})
    report['gate']=primary_gate(report['comparisons']);return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('export','bundle','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--bundle-sha256',required=True);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--device',default='cuda',choices=['cuda']);parser.add_argument('--arm',choices=ARMS)
    parser.add_argument('--seed',type=int,choices=SEEDS);parser.add_argument('--prepared',type=Path);parser.add_argument('--report-only',action='store_true')
    args=parser.parse_args()
    if not args.execute:
        print(json.dumps({'execute':False,'arms':ARMS,'seeds':SEEDS,'epochs':EPOCHS,'batch':BATCH,'run_seconds':RUN_SECONDS,'grid_seconds':GRID_SECONDS,'scope':'No reads, fits or output writes'}));return
    verify_bundle(args.bundle,args.bundle_sha256)
    if args.arm:
        if args.seed is None or args.prepared is None or args.report_only:raise ValueError('Complete fixed child configuration required')
        run_one(args);return
    dataset=CompletedExport(args.export)
    if dataset.manifest.get('polarization_manifest_sha256')!=PARENT_SHA or dataset.manifest.get('protocol_sha256')!=PROTOCOL_SHA:raise ValueError('Wrong frozen shared export')
    if args.report_only:
        atomic_json(args.output/'report.json',report_grid(args.output,dataset,args.bundle_sha256));return
    args.output.mkdir(parents=True,exist_ok=False);prepared=args.output/'prepared';prepare(dataset,prepared)
    grid={'status':'started','bundle_sha256':args.bundle_sha256,'protocol_sha256':PROTOCOL_SHA,'export_manifest_sha256':file_sha(args.export/'manifest.json'),'arms':ARMS,'seeds':SEEDS}
    atomic_json(args.output/'grid_manifest.json',grid);started=time.monotonic()
    try:
        for seed in SEEDS:
            for arm in ARMS:
                remaining=GRID_SECONDS-(time.monotonic()-started)
                if remaining<=0:raise TimeoutError('Grid budget exhausted')
                command=[sys.executable,str(Path(__file__).resolve()),'--export',str(args.export.resolve()),'--bundle',str(args.bundle.resolve()),'--bundle-sha256',args.bundle_sha256,'--output',str((args.output/f'{arm}_{seed}').resolve()),'--prepared',str(prepared.resolve()),'--arm',arm,'--seed',str(seed),'--execute']
                with (args.output/f'{arm}_{seed}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=min(RUN_SECONDS,remaining))
        grid.update(status='training_complete',training_seconds=time.monotonic()-started);atomic_json(args.output/'grid_manifest.json',grid)
        command=[sys.executable,str(Path(__file__).resolve()),'--export',str(args.export.resolve()),'--bundle',str(args.bundle.resolve()),'--bundle-sha256',args.bundle_sha256,'--output',str(args.output.resolve()),'--report-only','--execute']
        with (args.output/'report.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''))
        grid.update(status='complete',report_sha256=file_sha(args.output/'report.json'));atomic_json(args.output/'grid_manifest.json',grid)
        atomic_json(args.output/'COMPLETE.json',{'grid_manifest_sha256':file_sha(args.output/'grid_manifest.json')})
    except Exception as exc:
        grid.update(status='incomplete',error=type(exc).__name__+': '+str(exc));atomic_json(args.output/'grid_manifest.json',grid);raise


if __name__=='__main__':main()

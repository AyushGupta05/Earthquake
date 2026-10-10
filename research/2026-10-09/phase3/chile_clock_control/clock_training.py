"""Fixed four-fit lifecycle. Imported only inside an explicitly executed worker."""
import hashlib
import json
import os
from pathlib import Path
import random
import time

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Subset

from baseline_guards import verify, sha, read_json, validate_splits, epoch_sequence
from clock_contract import (atomic_json, import_sources, validate_baseline, metadata_rows,
                            verify_cache_headers, verify_dataset_contract, PROTOCOL_SHA, preflight)
from clock_rng import Streams, Trace, assert_paired, apply_augmentation, stream_seed, state_digest, tensor_bytes
from clock_metrics import add_proper_scores, scores, paired_comparison, frozen_gate


class Budget:
    def __init__(self, seconds):self.deadline=time.monotonic()+seconds
    def check(self):
        if time.monotonic()>=self.deadline:raise TimeoutError('Fixed budget expired; experiment is incomplete')


def configure_runtime():
    if os.environ.get('CUBLAS_WORKSPACE_CONFIG')!=':4096:8':raise ValueError('Set CUBLAS_WORKSPACE_CONFIG before Torch/CUDA imports')
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic=True;torch.backends.cudnn.benchmark=False
    return {'torch':str(torch.__version__),'cuda':torch.version.cuda,'cudnn':torch.backends.cudnn.version(),
            'deterministic_algorithms':torch.are_deterministic_algorithms_enabled(),
            'cudnn_deterministic':torch.backends.cudnn.deterministic,'cudnn_benchmark':torch.backends.cudnn.benchmark,
            'cuda_matmul_allow_tf32':torch.backends.cuda.matmul.allow_tf32,'cudnn_allow_tf32':torch.backends.cudnn.allow_tf32,
            'float32_matmul_precision':torch.get_float32_matmul_precision(), 'threads':torch.get_num_threads(),
            'cublas_workspace_config':os.environ['CUBLAS_WORKSPACE_CONFIG']}


def require_runtime(runtime, run, device):
    original=run['runtime']
    # The sole accepted run.json SHA is the completed flat-backend migration.
    # Its wrapper adds this extension to the plain trainer runtime metadata;
    # the event loader itself remained HDF-based. Never accept a flat-schema
    # fallback or infer unrecorded TF32 settings from the selected epoch.
    backend=original.get('station_backend',{})
    if backend.get('schema')!='team-flat-station-runtime-v1' or backend.get('scope')!='station_pretraining_and_train_calibration_only':
        raise ValueError('Pinned migrated baseline runtime extension is required')
    strict=backend.get('strict_runtime',{})
    if not {'cuda_matmul_allow_tf32','cudnn_allow_tf32','float32_matmul_precision'}.issubset(strict):
        raise ValueError('Pinned baseline precision record is incomplete')
    if runtime['torch']!=run['torch_version'] or runtime['cuda']!=original['torch_cuda'] or runtime['cudnn']!=original['cudnn']:
        raise ValueError('Original baseline Torch/CUDA/cuDNN runtime must be preserved')
    for key in ('cuda_matmul_allow_tf32','cudnn_allow_tf32','float32_matmul_precision'):
        if runtime[key]!=strict[key]:raise ValueError('Original precision default changed: '+key)
    if device.type!='cuda' or not torch.cuda.is_available() or torch.cuda.get_device_name(device)!=original['gpu']:
        raise ValueError('Parent must supply the pinned A10G runtime; no silent CPU/hardware fallback')


def atomic_npz(path, arrays):
    temp=Path(str(path)+'.tmp')
    with temp.open('wb') as stream:
        np.savez_compressed(stream,**arrays);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def model_random_state(device):
    values={'cpu':torch.get_rng_state()}
    if device.type=='cuda':values['cuda']=torch.cuda.get_rng_state(device)
    return values


def fresh_model(team, initial, seed, device):
    torch.manual_seed(stream_seed(seed,'construction'))
    model=team.TeamLM('transformer');model.load_state_dict(initial,strict=True)
    for name,p in model.named_parameters():p.requires_grad_(not name.startswith('single_station_head.'))
    if any(isinstance(m,torch.nn.Dropout) and m.p!=0 for m in model.modules()):raise ValueError('Frozen model dropout configuration changed')
    model.to(device)
    torch.manual_seed(stream_seed(seed,'model'));random.seed(stream_seed(seed,'python'))
    np.random.seed(stream_seed(seed,'numpy')%(2**32))
    return model


def train_epoch(model, loader, optimizer, parameters, streams, arm, team, trainer,
                device, *, seed, epoch, station_counts, check_budget=lambda:None):
    model.train();trace=Trace();total=0.;started=time.monotonic()
    for batch_index,(x,coords,mask,y,ids) in enumerate(loader,1):
        check_budget()
        trace.records('event_order',ids)
        # The pinned EventDataset uses this exact per-event permutation. With
        # <=25 stations none are truncated; header counts bind its domain.
        selections=[]
        for event in ids:
            rng=np.random.default_rng(trainer._event_seed(seed,epoch,event))
            selections.append([event,rng.permutation(station_counts[event]).tolist()])
        trace.records('station_order',selections)
        x,coords,mask,y=x.to(device),coords.to(device),mask.to(device),y.float().to(device)
        cutoff,samples=streams.cutoffs(len(y),device,arm)
        draws=streams.augmentation(mask,y)
        for field,value in zip(('station_count_draw','station_rank_draw','label_draw'),draws):trace.tensor(field,value)
        for name,value in model_random_state(device).items():trace.records('model_rng',name);trace.tensor('model_rng',value)
        trace.tensor('clock',samples)
        mask,noisy=apply_augmentation(x,coords,mask,y,cutoff,draws,team.prepare_prefix)
        trace.tensor('final_mask',mask)
        loss=team.mixture_nll(model(x,coords,mask,cutoff),noisy,1e-6)
        if not torch.isfinite(loss):raise FloatingPointError('Nonfinite fixed floored-NLL loss')
        optimizer.zero_grad(set_to_none=True);loss.backward()
        norm=torch.nn.utils.clip_grad_norm_(parameters,1.,error_if_nonfinite=True)
        optimizer.step()
        total+=float(loss.detach())*len(y);trace.examples+=len(y);trace.batches+=1;trace.batch_sizes.append(len(y))
        for n,count in zip(*np.unique(samples.cpu().numpy(),return_counts=True)):trace.clock_counts[int(n)]+=int(count)
        if batch_index==100:print(json.dumps({'stage':'fit_first100','arm':arm,'seed':seed,'epoch':epoch+1,'seconds':time.monotonic()-started}),flush=True)
    check_budget()
    if not trace.examples:raise ValueError('Empty training epoch')
    return {'epoch':epoch+1,'train_loss':total/trace.examples,'seconds':time.monotonic()-started,
            'trace':trace.result(),'learning_rate':optimizer.param_groups[0]['lr'],'last_gradient_norm':float(norm)}


def _save_epoch(path,trainer,model,optimizer,streams,epoch,history,identity,device):
    trainer.atomic_save({'schema':'chile-clock-completed-epoch-v1','completed_epoch':epoch,'model':model.state_dict(),
                         'optimizer':optimizer.state_dict(),'streams':streams.state_dict(),'model_rng':model_random_state(device),
                         'python_rng':random.getstate(),'numpy_rng':{'algorithm':np.random.get_state()[0],
                          'keys':np.random.get_state()[1].tolist(),'position':np.random.get_state()[2],
                          'has_gauss':np.random.get_state()[3],'cached_gaussian':np.random.get_state()[4]},
                         'identity':identity,'history':history,'resume_supported':False},path)


def completed_fits(output, identities):
    """Fail closed before held-out reads if even one final fit is incomplete."""
    expected={f'{arm}_{seed}' for arm in ('source_uniform','discrete_1_3_5') for seed in (20261011,20261012)}
    if set(identities)!=expected:raise ValueError('All four frozen fit identities required')
    paths={}
    for key,identity in identities.items():
        directory=output/key;receipt=read_json(directory/'FIT_COMPLETE.json')
        if receipt.get('completed_epochs')!=6 or receipt.get('identity')!=identity:raise ValueError('Wrong/incomplete fit')
        for filename,digest in receipt['files_sha256'].items():verify(directory/filename,digest)
        if set(receipt['files_sha256'])!={'model.pth','history.json','INIT.json','latest.pth'}:raise ValueError('Unexpected fit artifact set')
        paths[key]=directory/'model.pth'
    if len(paths)!=4:raise ValueError('All four frozen fits must complete before evaluation')
    return paths


def execute(args,plan,protocol,sources):
    global_budget=Budget(args.max_seconds);started=time.monotonic()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    atomic_json(output/'STARTED.json',{'protocol_sha256':PROTOCOL_SHA,'plan_sha256':args.plan_sha256,'source_manifest_sha256':args.source_manifest_sha256})
    for item in plan['artifacts'].values():global_budget.check();verify(item['path'],item['sha256'])
    paths={k:Path(v['path']) for k,v in plan['artifacts'].items()}
    manifest,sidecar=read_json(paths['dataset_manifest']),read_json(paths['metadata_manifest']);verify_dataset_contract(plan,manifest,sidecar)
    epoch_sequence(paths['history'],100);epoch_sequence(paths['pretrain_history'],25)
    run=read_json(paths['run']);split=read_json(paths['split_manifest'])
    validate_splits(split,*manifest['author_split_boundaries'],run)
    runtime=configure_runtime();device=torch.device('cuda');require_runtime(runtime,run,device)
    checkpoint=torch.load(paths['checkpoint'],map_location='cpu',weights_only=True)
    validate_baseline(run,checkpoint,plan,manifest)
    initial=checkpoint['model']
    if any(not torch.isfinite(value).all() for value in initial.values()):raise ValueError('Nonfinite original checkpoint')
    initial_digest=state_digest(initial)
    fit_rows,ids=metadata_rows(paths['metadata'],split,manifest,sidecar,requested='fit')
    counts=verify_cache_headers(paths['cache'],manifest,ids,fit_rows)
    team,trainer=import_sources(args.source_dir)
    repetitions=trainer.resampling_indices(np.asarray([r['MA'] for r in fit_rows]),2)
    fit_config={'protocol_sha256':PROTOCOL_SHA,'source_manifest_sha256':args.source_manifest_sha256,
                'baseline_artifact_sha256':protocol['artifact_sha256'],'baseline_initial_state_sha256':initial_digest,
                'fit_ids_sha256':run['fit_ids_sha256'],'runtime':runtime,'epochs':6,'batch_size':64,'optimizer':protocol['optimizer']}
    atomic_json(output/'grid_identity.json',fit_config)
    identities={}; histories={};fit_spent=0.
    for seed in protocol['seeds']:
        for arm in protocol['arms']:
            global_budget.check();key=f'{arm}_{seed}';directory=output/key;directory.mkdir()
            identity={**fit_config,'arm':arm,'seed':seed};identities[key]=identity
            model=fresh_model(team,initial,seed,device)
            if state_digest(model.state_dict())!=initial_digest:raise ValueError('Initial weights changed')
            parameters=[p for name,p in model.named_parameters() if not name.startswith('single_station_head.')]
            optimizer=torch.optim.Adam(parameters,lr=9e-6,betas=(.9,.999),eps=1e-8,weight_decay=0,amsgrad=False)
            if optimizer.state:raise ValueError('Fresh optimizer must have empty moments')
            streams=Streams(seed,device)
            atomic_json(directory/'INIT.json',{'identity':identity,'model_state_sha256':initial_digest,'optimizer_state_entries':len(optimizer.state),
                                               'model_rng_sha256':state_digest(model_random_state(device)),'generator_state_sha256':state_digest(streams.state_dict())})
            dataset=trainer.EventDataset(paths['cache'],pd.DataFrame(fit_rows),training=True,max_stations=25,station_drop=0.,seed=seed,stored_samples=3000)
            repeated=Subset(dataset,repetitions.tolist());history=[];fit_start=time.monotonic();fit_budget=Budget(min(9000.,36000.-fit_spent))
            def check_budget():global_budget.check();fit_budget.check()
            try:
                for epoch in range(6):
                    dataset.epoch=epoch
                    loader=DataLoader(repeated,batch_size=64,shuffle=True,generator=torch.Generator().manual_seed(seed+1000+epoch),
                                      num_workers=0,collate_fn=trainer.collate_events,drop_last=False)
                    record=train_epoch(model,loader,optimizer,parameters,streams,arm,team,trainer,device,
                                       seed=seed,epoch=epoch,station_counts=counts,check_budget=check_budget)
                    if record['trace']['examples']!=len(repetitions):raise ValueError('Incomplete draw budget/remainder')
                    if arm=='discrete_1_3_5':assert_paired(histories[f'source_uniform_{seed}'][epoch]['trace'],record['trace'])
                    history.append(record)
                    _save_epoch(directory/'latest.pth',trainer,model,optimizer,streams,epoch+1,history,identity,device)
                    atomic_json(directory/'history.json',history)
                    print(json.dumps({'stage':'fit_epoch','key':key,'epoch':epoch+1,'seconds':record['seconds'],'loss':record['train_loss']}),flush=True)
                check_budget()
                trainer.atomic_save({'schema':'chile-clock-final-v1','model':model.state_dict(),'identity':identity,'completed_epochs':6},directory/'model.pth')
                receipt={'identity':identity,'completed_epochs':6,'files_sha256':{name:sha(directory/name) for name in ('model.pth','history.json','INIT.json','latest.pth')}}
                atomic_json(directory/'FIT_COMPLETE.json',receipt);histories[key]=history
            finally:dataset.close()
            fit_spent+=time.monotonic()-fit_start
            del model,optimizer,parameters,streams
            torch.cuda.empty_cache()
    model_paths=completed_fits(output,identities)
    atomic_json(output/'TRAINING_COMPLETE.json',{'keys':list(model_paths),'fit_seconds':fit_spent,'fit_completion_sha256':{k:sha(output/k/'FIT_COMPLETE.json') for k in model_paths}})
    # Neither calibration nor DEV target values were parsed or forwarded before
    # this barrier. The starting checkpoint is contextual, never the comparator.
    predictions={};report={'scope':protocol['interpretation'],'runtime':runtime,'protocol_sha256':PROTOCOL_SHA,'scores':{},'comparisons':{},'fit_seconds':fit_spent}
    for split_name in ('calibration','dev'):
        rows,all_ids=metadata_rows(paths['metadata'],split,manifest,sidecar,requested=split_name,all_fits_complete=True)
        verify_cache_headers(paths['cache'],manifest,all_ids,rows)
        dataset=trainer.EventDataset(paths['cache'],pd.DataFrame(rows),training=False,max_stations=25,station_drop=0.,stored_samples=3000)
        loader=DataLoader(dataset,batch_size=64,shuffle=False,num_workers=0,collate_fn=trainer.collate_events)
        predictions[split_name]={};report['scores'][split_name]={}
        try:
            for key in [*model_paths,'starting_epoch97']:
                global_budget.check();model=team.TeamLM('transformer')
                if key=='starting_epoch97':weights=initial
                else:
                    receipt=read_json(output/key/'FIT_COMPLETE.json');verify(model_paths[key],receipt['files_sha256']['model.pth'])
                    payload=torch.load(model_paths[key],map_location='cpu',weights_only=True)
                    if payload['identity']!=identities[key] or payload['completed_epochs']!=6:raise ValueError('Final comparison checkpoint changed')
                    weights=payload['model']
                model.load_state_dict(weights,strict=True);model.to(device)
                _,p=trainer.evaluate(model,loader,device);p=add_proper_scores(p,team,trainer)
                if p['event_ids'].tolist()!=split[split_name]['event_ids'] or not np.array_equal(p['targets'],[row['MA'] for row in rows]):raise ValueError('Evaluation alignment changed')
                predictions[split_name][key]=p;report['scores'][split_name][key]=scores(p)
                atomic_npz(output/f'{split_name}_{key}_predictions.npz',p)
                del model
            report['comparisons'][split_name]={}
            for seed in protocol['seeds']:
                global_budget.check()
                report['comparisons'][split_name][str(seed)]=paired_comparison(predictions[split_name][f'discrete_1_3_5_{seed}'],predictions[split_name][f'source_uniform_{seed}'])
        finally:dataset.close()
    report['gate']=frozen_gate(report['comparisons']['dev']);report['calibration_tail_warning']='Only2 calibration and1 DEV MA>=5.5 event; do not infer high-magnitude generalization.'
    report['elapsed_seconds']=time.monotonic()-started
    global_budget.check();atomic_json(output/'report.json',report)
    # Revalidate all final fit bytes after reporting; no evaluation modifies them.
    completed_fits(output,identities)
    preflight(args)  # Same reviewed code and protocol through completion.
    artifacts={str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file() and p.name!='COMPLETE.json'}
    atomic_json(output/'COMPLETE.json',{'schema':'chile-clock-grid-complete-v1','protocol_sha256':PROTOCOL_SHA,
                                      'plan_sha256':args.plan_sha256,'source_manifest_sha256':args.source_manifest_sha256,
                                      'artifacts_sha256':artifacts,'test_reads':0,'selection':'fixed_final6','fits':4})

"""Parent-only, unaugmented first16-fit replay; no optimizer or held-out reads."""
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from baseline_guards import verify, read_json, validate_splits, epoch_sequence, ids_sha
from clock_contract import (atomic_json, import_sources, validate_baseline, metadata_rows,
                            verify_cache_headers, verify_dataset_contract, PROTOCOL_SHA)
from clock_training import configure_runtime, require_runtime, fresh_model, Budget
from clock_rng import state_digest


def compare_parameters(actual, reference, event_ids, expected_ids, *, atol=1e-6, rtol=1e-6):
    """Reference stores native float32 outputs as float64, without recomputation."""
    if list(event_ids)!=list(expected_ids) or len(event_ids)!=16 or len(set(event_ids))!=16:
        raise ValueError('Replay requires exactly the same first16 unique fit events')
    report={}
    for seconds in (1,3,5):
        report[str(seconds)]={}
        for name in ('logits','means','scales'):
            got=np.asarray(actual[f'{seconds}_{name}']);want=np.asarray(reference[f'{seconds}_{name}'])
            if got.dtype!=np.float32 or got.shape!=(16,5) or want.shape!=got.shape:
                raise ValueError('Replay requires native float32 five-Gaussian parameters')
            if not np.isfinite(got).all() or not np.isfinite(want).all():raise ValueError('Nonfinite replay parameter')
            if not np.allclose(got,want,atol=atol,rtol=rtol):raise ValueError(f'Initial parameter replay failed: {seconds}/{name}')
            report[str(seconds)][name]={'max_abs_error':float(np.abs(got.astype(np.float64)-want).max()),'atol':atol,'rtol':rtol}
    return report


def execute_replay(args,plan,protocol,sources):
    budget=Budget(args.max_seconds);output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    for item in plan['artifacts'].values():budget.check();verify(item['path'],item['sha256'])
    paths={k:Path(v['path']) for k,v in plan['artifacts'].items()}
    diagnostic=args.initial_replay.resolve();pins=protocol['initial_replay']
    verify(diagnostic/'COMPLETE.json',pins['complete_sha256']);receipt=read_json(diagnostic/'COMPLETE.json')
    if receipt.get('schema')!='chile_floor_diagnostic_complete_v1' or receipt['inputs']!=plan:
        raise ValueError('Replay diagnostic must belong to the exact frozen baseline plan')
    if receipt['artifacts'].get('diagnostics.npz')!=pins['arrays_sha256']:raise ValueError('Unrecognized reference predictions')
    for name in ('diagnostics.npz','selection.json'):verify(diagnostic/name,receipt['artifacts'][name])
    manifest,sidecar=read_json(paths['dataset_manifest']),read_json(paths['metadata_manifest']);verify_dataset_contract(plan,manifest,sidecar)
    epoch_sequence(paths['history'],100);epoch_sequence(paths['pretrain_history'],25)
    run,split=read_json(paths['run']),read_json(paths['split_manifest']);validate_splits(split,*manifest['author_split_boundaries'],run)
    runtime=configure_runtime();device=torch.device('cuda');require_runtime(runtime,run,device)
    checkpoint=torch.load(paths['checkpoint'],map_location='cpu',weights_only=True);validate_baseline(run,checkpoint,plan,manifest)
    fit_rows,ids=metadata_rows(paths['metadata'],split,manifest,sidecar,requested='fit')
    lookup={r['EVENT']:r for r in fit_rows};selection=read_json(diagnostic/'selection.json')['events'][:16]
    selected=[]
    for row in selection:
        if row['EVENT'] not in lookup or any(row[k]!=lookup[row['EVENT']][k] for k in lookup[row['EVENT']]):
            raise ValueError('Reference event does not exactly match original TRAIN fit membership/metadata')
        selected.append(lookup[row['EVENT']])
    expected_ids=[r['EVENT'] for r in selected]
    with np.load(diagnostic/'diagnostics.npz',allow_pickle=False) as reference:
        if reference['event_ids'][:16].tolist()!=expected_ids or not np.array_equal(reference['targets'][:16],[r['MA'] for r in selected]):
            raise ValueError('Reference first16 identity/target mismatch')
        expected={f'{t}_{k}':reference[f'{t}_source_{k}'][:16].copy() for t in (1,3,5) for k in ('logits','means','scales')}
    verify_cache_headers(paths['cache'],manifest,ids,selected)
    team,trainer=import_sources(args.source_dir);model=fresh_model(team,checkpoint['model'],20261011,device);model.eval()
    dataset=trainer.EventDataset(paths['cache'],pd.DataFrame(selected),training=False,max_stations=25,station_drop=0.,seed=20261009,stored_samples=3000)
    loader=DataLoader(dataset,batch_size=16,shuffle=False,num_workers=0,collate_fn=trainer.collate_events)
    actual={};events=[]
    try:
        with torch.no_grad():
            for x,coords,mask,y,events in loader:
                budget.check();x,coords,mask=x.to(device),coords.to(device),mask.to(device)
                for t in (1,3,5):
                    mixture=model(x,coords,mask,cutoff_seconds=t)
                    for k in ('logits','means','scales'):actual[f'{t}_{k}']=mixture[k].cpu().numpy()
    finally:dataset.close()
    comparison=compare_parameters(actual,expected,events,expected_ids)
    budget.check()
    atomic_json(output/'COMPLETE.json',{'schema':'chile-clock-initial-replay-v1','protocol_sha256':PROTOCOL_SHA,
      'plan_sha256':args.plan_sha256,'source_manifest_sha256':args.source_manifest_sha256,'baseline_checkpoint_sha256':pins['checkpoint_sha256'],
      'initial_model_state_sha256':state_digest(checkpoint['model']),'reference_complete_sha256':pins['complete_sha256'],
      'reference_arrays_sha256':pins['arrays_sha256'],'event_ids_sha256':ids_sha(expected_ids),'events':16,
      'parameters':comparison,'runtime':runtime,'optimizer_steps':0,'calibration_dev_test_forwards':0,
      'scope':'First16-fit input-behavior check only; not full replay or TensorFlow equivalence'})

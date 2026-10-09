"""Bounded 1-second pilot: change only the last distribution layer.

Three fixed objectives, identical initial weights, frozen waveform features,
identical event-balanced examples, five epochs, no test evaluation or selection.
This pilot is cheaper than a new waveform backbone and cannot establish the
performance of end-to-end training with any of these losses.
"""
import argparse
import copy
import json
from pathlib import Path
import time

import h5py
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F

from audit_and_export import EarthquakeCNN, sha256, require_checkpoint_preprocessing
from distribution_experiment import event_weights, metrics, median


def ordinal_score(logits, labels, tail_weight=0.):
    """Proper positive-weight CDF score for 66 ordered magnitude bins."""
    cdf = logits.softmax(1).cumsum(1)[:, :-1]
    cut = torch.arange(logits.shape[1]-1, device=logits.device)
    target = (labels[:, None] <= cut).to(logits.dtype)
    # CDF boundary after bin 39 is M4.0.
    weights = 1. + tail_weight * ((cut + 1) * .1 >= 4.)
    return .1 * (((cdf-target)**2) * weights).sum(1)


def choose_rows(metadata, max_per_event=4):
    rng = np.random.default_rng(20261009)
    # Keep index labels matching cache rows; no shuffle/drop of metadata itself.
    rows = []
    for index in metadata.groupby('source_id', sort=True).indices.values():
        rows.extend(rng.choice(index, min(max_per_event,len(index)), replace=False).tolist())
    return np.sort(np.asarray(rows))


def encode(model, path, split, rows, device):
    features = []
    with h5py.File(path,'r') as h:
        waves = h[f'{split}/waveforms']
        if waves.shape[1:] != (3,100):
            raise ValueError('This pilot requires exactly one-second prefixes')
        with torch.inference_mode():
            for i in range(0,len(rows),256):
                x = torch.from_numpy(waves[rows[i:i+256]]).to(device)
                hidden = model.classifier[:-1](model.global_pool(model.features(x)))
                features.append(hidden.cpu())
    return torch.cat(features)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,default=Path('results/2026-10-09/head_pilot_1s'))
    args = ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[2]
    audited = json.loads((root/'results/2026-10-09/audit.json').read_text())
    require_checkpoint_preprocessing({audited['windows']['1']['preprocessing']})
    meta = pd.read_csv(root/'train_full_metadata.csv',usecols=['source_id','source_magnitude'])
    if sha256(root/'train_full_metadata.csv') != audited['train']['metadata_sha256']:
        raise ValueError('Training metadata changed after cache audit')
    rows=choose_rows(meta)
    torch.manual_seed(20261009)
    torch.set_num_threads(2)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint_path=root/'bayesianprior/data/best_model_huberandcross1s075fixed.pth'
    if sha256(checkpoint_path) != audited['windows']['1']['checkpoint_sha256']:
        raise ValueError('Checkpoint changed after export')
    model=EarthquakeCNN().to(device)
    checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=True)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    data=np.load(root/'results/2026-10-09/validation_1s.npz',allow_pickle=False)
    val_ids,y,c=data['event_ids'],data['targets'],data['centers']
    if set(meta.source_id.astype(str)) & set(val_ids):
        raise ValueError('Training/validation event overlap')
    started=time.monotonic()
    cache=Path('/data/Instance_windows_1s.hdf5')
    train_x=encode(model,cache,'train',rows,device).to(device)
    val_x=encode(model,cache,'val',np.arange(len(y)),device).to(device)
    with torch.inference_mode():
        reproduced=torch.cat([model.classifier[-1](x).cpu() for x in val_x.split(256)]).numpy()
    if not np.allclose(reproduced,data['logits'],atol=2e-3,rtol=2e-4):
        raise ValueError(f'Frozen features differ from audited logits: max_abs={np.max(np.abs(reproduced-data["logits"]))}')
    labels=torch.tensor(np.clip(np.floor(meta.source_magnitude.to_numpy()[rows]/.1+1e-5),0,65),dtype=torch.long,device=device)
    w=event_weights(meta.source_id.to_numpy()[rows])*len(rows)
    weights=torch.tensor(w,dtype=torch.float32,device=device)
    initial=copy.deepcopy(model.classifier[-1].state_dict())
    history=[]
    result={}
    raw_prob=torch.from_numpy(data['logits']).double().softmax(1).numpy()
    result['frozen_original_mean']=metrics(y,raw_prob@c,val_ids,raw_prob,c)
    result['frozen_original_median']=metrics(y,median(raw_prob,c),val_ids,raw_prob,c)
    for objective in ['cross_entropy','ordinal_crps','ordinal_crps_tail10']:
        torch.manual_seed(20261009)
        head=nn.Linear(128,66).to(device)
        head.load_state_dict(initial)
        optimizer=torch.optim.AdamW(head.parameters(),lr=1e-3,weight_decay=0.)
        for epoch in range(5):
            order=torch.randperm(len(rows),device=device)
            total=0.
            for start in range(0,len(rows),1024):
                ix=order[start:start+1024]
                logits=head(train_x[ix])
                losses=(F.cross_entropy(logits,labels[ix],reduction='none') if objective=='cross_entropy'
                        else ordinal_score(logits,labels[ix],10. if objective.endswith('tail10') else 0.))
                loss=(losses*weights[ix]).mean()
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
                total+=loss.item()*len(ix)
            with torch.inference_mode():
                prob=head(val_x).double().softmax(1).cpu().numpy()
            m=metrics(y,prob@c,val_ids,prob,c)
            history.append({'objective':objective,'epoch':epoch+1,'train_loss':total/len(rows),**m})
            print(objective,epoch+1,{k:m[k] for k in ['mae','m4_mae','crps','tail_crps4']},flush=True)
        result[objective+'_mean']=m
        result[objective+'_median']=metrics(y,median(prob,c),val_ids,prob,c)
        torch.save(head.state_dict(),args.output/f'{objective}.pth')
    info={'train_records':len(rows),'train_events':meta.source_id.iloc[rows].nunique(),
          'max_stations_per_event':4,'epochs':5,'seed':20261009,
          'wall_seconds':time.monotonic()-started,'device':str(device),
          'checkpoint_sha256':sha256(checkpoint_path),
          'selection':'Fixed final epoch for each objective; no validation selection',
          'scope':'Frozen-head pilot, reused validation set; not independent confirmation'}
    (args.output/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (args.output/'history.json').write_text(json.dumps(history,indent=2,allow_nan=False)+'\n')
    (args.output/'run.json').write_text(json.dumps(info,indent=2)+'\n')
    print(info,flush=True)


if __name__=='__main__':
    main()

"""Ablation: combine rare-magnitude emphasis with worst-error CVaR training.

This is established risk minimization, included as a strong loss-only control.
All fits use training events, with population weights correcting station sampling.
Reused validation is exploratory, not an untouched test or novelty certificate.
"""
import argparse
import json
from pathlib import Path
import time

import numpy as np
import torch
from torch.nn import functional as F

from feature_residual import (extract, inputs, ResidualDistribution, OUT,
                              select_crossfit, metrics, ROOT)
from run_artifacts import create_run


def cvar_surrogate(errors, weights, eta, alpha=.95):
    """Rockafellar-Uryasev expected shortfall objective with learned VaR.

    Population weights have global mean one; do not self-normalize minibatches.
    For a fixed model the minimum over eta equals empirical weighted CVaR.
    """
    if not 0 <= alpha < 1:
        raise ValueError('alpha must lie in [0,1)')
    return eta + (weights * (errors - eta).clamp_min(0)).mean() / (1-alpha)


def fit(data, beta, gamma, device, epochs, seed):
    torch.manual_seed(seed)
    arrays, mean, std = inputs(data, 'evidence')
    x, vx = [torch.as_tensor(a, device=device) for a in arrays]
    z, vz = [torch.as_tensor(data[s+'_logits'],device=device) for s in ['train','val']]
    y=torch.as_tensor(data['train_y'],device=device)
    w=torch.as_tensor(data['weights'],device=device)
    c=torch.as_tensor(data['centers'],dtype=torch.float32,device=device)
    labels=(y/.1+1e-5).floor().long().clamp(0,65)
    model=ResidualDistribution(x.shape[1]).to(device)
    eta=torch.nn.Parameter(torch.tensor(1.,device=device))
    optimizer=torch.optim.AdamW(model.parameters(),lr=5e-4,weight_decay=1e-4)
    eta_optimizer=torch.optim.Adam([eta],lr=.01)
    history=[]
    for epoch in range(epochs):
        model.train()
        total=0.
        for ix in torch.randperm(len(y),device=device).split(2048):
            logits=model(x[ix],z[ix])
            pred=logits.softmax(1)@c
            loss=(w[ix]*(F.huber_loss(pred,y[ix],reduction='none',delta=.5)
                  *(1+beta*(y[ix]-3.5).clamp_min(0))
                  +.075*F.cross_entropy(logits,labels[ix],reduction='none'))).mean()
            loss=loss+gamma*cvar_surrogate((pred-y[ix]).abs(),w[ix],eta)
            optimizer.zero_grad(set_to_none=True)
            eta_optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),5.)
            optimizer.step()
            if gamma:
                eta_optimizer.step()
                with torch.no_grad():
                    eta.clamp_(0,6.6)
            total+=loss.item()*len(ix)
        history.append({'epoch':epoch+1,'loss':total/len(y),'eta':eta.item()})
    model.eval()
    with torch.inference_mode():
        p=torch.cat([model(a,b).double().softmax(1).cpu()
                     for a,b in zip(vx.split(2048),vz.split(2048))]).numpy()
    state={'model':model.state_dict(),'feature_mean':torch.tensor(mean),
           'feature_std':torch.tensor(std),'eta':eta.detach().cpu(),
           'beta':beta,'gamma':gamma,'epochs':epochs,'seed':seed}
    return p,state,history


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--seconds',type=int,choices=[1,3,5],required=True)
    ap.add_argument('--epochs',type=int,default=15)
    ap.add_argument('--seed',type=int,default=20261009)
    args=ap.parse_args()
    if args.epochs<1:
        raise ValueError('epochs must be positive')
    torch.set_num_threads(2)
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    here=Path(__file__).resolve().parent
    out=create_run(OUT,f'robust_residual_{args.seconds}s',vars(args),
                   list(here.glob('*.py')) + list(here.parent.glob('*.py')) +
                   [ROOT/'results/2026-10-09/audit.json'])
    print('RUN_DIRECTORY',out,flush=True)
    started=time.monotonic()
    data=extract(args.seconds,device)
    y,ids,c=data['val_y'],data['val_ids'],data['centers']
    raw=torch.from_numpy(data['val_logits']).double().softmax(1).numpy()@c
    result={'raw_mean':metrics(y,raw,ids)}
    predictions={'raw_mean':raw}
    histories,candidates={},{}
    # Registered grid: magnitude emphasis x expected-shortfall coefficient.
    for beta in [5.,15.]:
        for gamma in [0.,.025,.1,.3]:
            name=f'beta{beta:g}_cvar{gamma:g}'
            p,state,history=fit(data,beta,gamma,device,args.epochs,args.seed)
            pred=p@c
            result[name]=metrics(y,pred,ids,p,c)
            predictions[name]=pred
            histories[name]=history
            torch.save(state,out/f'{name}.pth')
            for blend in [.25,.5,1.]:
                candidates[f'{name}_blend{blend:g}']=raw+blend*(pred-raw)
            print(args.seconds,name,{k:result[name][k] for k in ['mae','medae','m4_mae','cvar95','fp4']},flush=True)
    selected,choices,folds=select_crossfit(y,ids,raw,candidates)
    predictions['selected']=selected
    result['selected']=metrics(y,selected,ids)
    run={**vars(args),'wall_seconds':time.monotonic()-started,
         'status':'Reused exploratory validation; fixed final epoch',
         'method':'Established weighted Huber+CE with CVaR loss-only control'}
    for filename,obj in [('metrics.json',result),('choices.json',choices),
                         ('history.json',histories),('run.json',run)]:
        (out/filename).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(out/'predictions.npz',targets=y,event_ids=ids,fold=folds,**predictions)
    print('FINISHED',run,result['selected'],flush=True)


if __name__=='__main__':
    main()

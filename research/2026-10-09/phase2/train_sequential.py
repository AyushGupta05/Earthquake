"""End-to-end, matched-capacity tests of sequential magnitude distributions.

No test-set evaluation. All 1/3/5s predictions use the same examples and seed.
Final epoch is fixed; intermediate reused-validation metrics are monitoring only.
"""
import argparse
import json
from pathlib import Path
import sys
import time

import h5py
import numpy as np
import pandas as pd
import torch
from torch.nn import functional as F

from sequential_models import MagnitudeDistributionModel, MODES
from run_artifacts import create_run
from feature_residual import population_weights, ROOT
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from frozen_head_pilot import choose_rows, ordinal_score
from audit_and_export import sha256, require_checkpoint_preprocessing
from distribution_experiment import metrics, median


def conditional_drift(outputs, weights):
    """Weak conditional-moment penalty, not pathwise monotonicity.

    An ideal posterior CDF is a martingale under accumulating observations.
    We penalize finite-batch moments conditioned on a bounded early-CDF basis.
    This is a biased finite-batch surrogate, not a calibration certificate.
    Jointly train both times: a frozen incorrect early forecast can anchor bias.
    """
    scores=[]
    for early, late in [(1,3),(3,5)]:
        ps=outputs[early].float().softmax(1)
        pt=outputs[late].float().softmax(1)
        fs,ft=ps.cumsum(1)[:,:-1],pt.cumsum(1)[:,:-1]
        entropy=-(ps*ps.clamp_min(1e-12).log()).sum(1,keepdim=True)/np.log(66)
        basis=torch.cat([torch.ones_like(entropy),fs[:,[19,29,39,49]],entropy],1).detach()
        moment=torch.einsum('n,ni,nj->ij',weights/weights.sum(),ft-fs,basis)
        tail_weight=torch.where(torch.arange(65,device=ps.device)>=39,11.,1.)
        scores.append((moment.square()*tail_weight[:,None]).mean())
    return torch.stack(scores).mean()


def supervised_loss(outputs,y,w,centers,objective):
    labels=(y/.1+1e-5).floor().long().clamp(0,65)
    terms=[]
    for logits in outputs.values():
        logits=logits.float()
        ce=F.cross_entropy(logits,labels,reduction='none')
        if objective=='weighted':
            pred=logits.softmax(1)@centers
            l=F.huber_loss(pred,y,reduction='none',delta=1.)*(1+5*(y-3.5).clamp_min(0))+.075*ce
        else:
            l=ce+.2*ordinal_score(logits,labels,tail_weight=10.)
        terms.append((w*l).mean())
    return torch.stack(terms).mean()


def load_examples(device,max_per_event):
    audit=json.loads((ROOT/'results/2026-10-09/audit.json').read_text())
    require_checkpoint_preprocessing({audit['windows']['5']['preprocessing']})
    for split,file in [('train','train_full_metadata.csv'),('val','val_metadata.csv')]:
        if sha256(ROOT/file)!=audit[split]['metadata_sha256']:
            raise ValueError(f'{split} metadata changed')
    meta=pd.read_csv(ROOT/'train_full_metadata.csv',usecols=['source_id','source_magnitude'])
    rows=np.union1d(choose_rows(meta,max_per_event),np.flatnonzero(meta.source_magnitude.to_numpy()>=4))
    baseline=np.load(ROOT/'results/2026-10-09/validation_5s.npz',allow_pickle=False)
    if set(meta.source_id.astype(str))&set(baseline['event_ids']):
        raise ValueError('Train/validation event overlap')
    weights=population_weights(meta,rows)
    waves={}
    with h5py.File('/data/Instance_windows_5s.hdf5','r') as h:
        for split,ix in [('train',rows),('val',np.arange(len(baseline['targets'])))]:
            ds=h[f'{split}/waveforms']
            if ds.shape[1:]!=(3,500):
                raise ValueError('Expected 5s cache before causal slicing')
            target=h[f'{split}/targets'][:][ix]
            expected=meta.source_magnitude.to_numpy()[ix] if split=='train' else baseline['targets']
            if not np.allclose(target,expected,rtol=0,atol=1e-6):
                raise ValueError('Cache target ordering mismatch')
            # Chunking avoids an enormous fancy-index request into HDF5.
            a=np.empty((len(ix),3,500),dtype='float32')
            for start in range(0,len(ix),4096):
                a[start:start+4096]=ds[ix[start:start+4096]]
            if not np.isfinite(a).all():
                raise ValueError('Nonfinite waveforms')
            waves[split]=torch.from_numpy(a).to(device)
            print('LOADED',split,a.shape,flush=True)
    return waves,torch.tensor(meta.source_magnitude.to_numpy()[rows],dtype=torch.float32,device=device),torch.tensor(weights,dtype=torch.float32,device=device),baseline,rows


def evaluate(model,x,y,ids,c):
    model.eval()
    probs={t:[] for t in [1,3,5]}
    gates={3:[],5:[]}
    with torch.inference_mode():
        for batch in x.split(512):
            outputs,info=model.forward_with_diagnostics(batch)
            for t in probs:
                probs[t].append(outputs[t].double().softmax(1).cpu().numpy())
            for t in gates:
                if t in info['gate']:
                    gates[t].append(info['gate'][t].float().cpu().numpy().ravel())
    probs={t:np.concatenate(p) for t,p in probs.items()}
    result={str(t):metrics(y,p@c,ids,p,c) for t,p in probs.items()}
    predictions={f'mean_{t}s':p@c for t,p in probs.items()}
    predictions.update({f'median_{t}s':median(p,c) for t,p in probs.items()})
    for t,a in gates.items():
        if a:
            predictions[f'gate_{t}s']=np.concatenate(a)
    return result,predictions


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--mode',choices=MODES,required=True)
    ap.add_argument('--objective',choices=['weighted','proper'],default='weighted')
    ap.add_argument('--martingale-weight',type=float,default=0.)
    ap.add_argument('--epochs',type=int,default=20)
    ap.add_argument('--seed',type=int,default=20261009)
    ap.add_argument('--batch-size',type=int,default=512)
    ap.add_argument('--max-per-event',type=int,default=4)
    args=ap.parse_args()
    if args.epochs<1 or args.batch_size<1 or args.max_per_event<1 or args.martingale_weight<0:
        raise ValueError('Invalid training bounds')
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    torch.backends.cudnn.benchmark=False
    device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    name=f'{args.mode}_{args.objective}_drift{args.martingale_weight:g}_seed{args.seed}'
    here=Path(__file__).resolve().parent
    out=create_run(ROOT/'results/2026-10-09/phase2', name, vars(args),
                   list(here.glob('*.py')) + list(here.parent.glob('*.py')) +
                   [ROOT/'results/2026-10-09/audit.json'])
    print('RUN_DIRECTORY',out,flush=True)
    started=time.monotonic()
    waves,y,w,baseline,rows=load_examples(device,args.max_per_event)
    c=torch.tensor(baseline['centers'],dtype=torch.float32,device=device)
    model=MagnitudeDistributionModel(args.mode).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=3e-4,weight_decay=1e-4)
    scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=args.epochs,eta_min=3e-5)
    history=[]
    for epoch in range(args.epochs):
        model.train()
        order=torch.randperm(len(y),device=device)
        total=0.
        epoch_start=time.monotonic()
        for ix in order.split(args.batch_size):
            outputs=model(waves['train'][ix])
            loss=supervised_loss(outputs,y[ix],w[ix],c,args.objective)
            if args.martingale_weight:
                loss=loss+args.martingale_weight*conditional_drift(outputs,w[ix])
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),5.)
            optimizer.step()
            total+=loss.item()*len(ix)
        scheduler.step()
        log={'epoch':epoch+1,'train_loss':total/len(y),'epoch_seconds':time.monotonic()-epoch_start}
        if epoch==0 or (epoch+1)%5==0 or epoch+1==args.epochs:
            result,predictions=evaluate(model,waves['val'],baseline['targets'],baseline['event_ids'],baseline['centers'])
            log['validation']=result
        history.append(log)
        (out/'history.json').write_text(json.dumps(history,indent=2,allow_nan=False)+'\n')
        brief={t:{k:m[k] for k in ['mae','m4_mae','cvar95']} for t,m in log.get('validation',{}).items()}
        print(name,epoch+1,'loss',log['train_loss'],'seconds',log['epoch_seconds'],brief,flush=True)
    torch.save({'model':model.state_dict(),'config':vars(args)},out/'model.pth')
    (out/'metrics.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    run={**vars(args),'parameters':model.parameter_counts(),'train_records':len(rows),
         'wall_seconds':time.monotonic()-started,'selection':'Fixed final epoch; monitoring does not select weights',
         'data_status':'Reused INSTANCE validation, no test predictions'}
    (out/'run.json').write_text(json.dumps(run,indent=2)+'\n')
    np.savez_compressed(out/'predictions.npz',targets=baseline['targets'],event_ids=baseline['event_ids'],**predictions)
    print('FINISHED',run,flush=True)


if __name__=='__main__':
    main()

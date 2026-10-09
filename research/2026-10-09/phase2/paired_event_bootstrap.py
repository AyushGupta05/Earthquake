"""Descriptive paired-event bootstrap for reused exploratory validation.

Intervals do not undo adaptive model selection or earthquake-sequence dependence.
Whole event clusters, including every recording, are resampled together.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from feature_residual import ROOT, metrics
from run_artifacts import create_run
from audit_and_export import sha256


def ordered_metrics(sorted_errors, sorted_counts):
    """Exact median and ceil(5%)-tail mean for integer replication counts."""
    cumulative=np.cumsum(sorted_counts)
    total=int(cumulative[-1])
    if total<1:
        raise ValueError('At least one replicated observation is required')
    left=np.searchsorted(cumulative,(total-1)//2+1)
    right=np.searchsorted(cumulative,total//2+1)
    median=(sorted_errors[left]+sorted_errors[right])/2
    tail_size=int(np.ceil(total*.05))
    before=np.r_[0,cumulative[:-1]]
    in_tail=np.maximum(0,cumulative-np.maximum(before,total-tail_size))
    return float(median),float(sorted_errors@in_tail/tail_size)


def bootstrap(y,ids,raw,pred,replicates=2000,seed=20261009):
    events,groups=np.unique(ids,return_inverse=True)
    n=len(events)
    count=np.bincount(groups,minlength=n)
    high=y>=4
    highcount=np.bincount(groups,weights=high,minlength=n)
    errors=np.stack([np.abs(raw-y),np.abs(pred-y)])
    sumloss=np.stack([np.bincount(groups,weights=e,minlength=n) for e in errors])
    highloss=np.stack([np.bincount(groups,weights=e*high,minlength=n) for e in errors])
    order=np.argsort(errors,axis=1)
    sorted_errors=np.take_along_axis(errors,order,axis=1)
    rng=np.random.default_rng(seed)
    keys=['mae','medae','cvar95','event_macro_mae','m4_mae','m4_event_macro_mae']
    draws={k:[] for k in keys}
    for _ in range(replicates):
        mult=rng.multinomial(n,np.full(n,1/n))
        record_mult=mult[groups]
        mae=sumloss@mult/(count@mult)
        macro=(sumloss/count)@mult/n
        medcvar=np.array([ordered_metrics(sorted_errors[j],record_mult[order[j]]) for j in [0,1]])
        draws['mae'].append(mae[1]-mae[0])
        draws['event_macro_mae'].append(macro[1]-macro[0])
        draws['medae'].append(medcvar[1,0]-medcvar[0,0])
        draws['cvar95'].append(medcvar[1,1]-medcvar[0,1])
        if highcount@mult>0:
            tail=highloss@mult/(highcount@mult)
            present=highcount>0
            tailmacro=(highloss[:,present]/highcount[present])@mult[present]/mult[present].sum()
            draws['m4_mae'].append(tail[1]-tail[0])
            draws['m4_event_macro_mae'].append(tailmacro[1]-tailmacro[0])
    interval={k: {'lower_95':float(np.quantile(v,.025)),
                  'upper_95':float(np.quantile(v,.975)), 'draws':len(v)} if v else None
              for k,v in draws.items()}
    return {'raw':metrics(y,raw,ids),'candidate':metrics(y,pred,ids),
            'paired_delta_intervals':interval,'events':n,'replicates':replicates,
            'interpretation':'Descriptive post-selection intervals; not independent confirmation'}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--predictions',type=Path,required=True)
    ap.add_argument('--candidate',default='beta15_cvar0.1')
    ap.add_argument('--replicates',type=int,default=2000)
    ap.add_argument('--seed',type=int,default=20261009)
    args=ap.parse_args()
    if args.replicates<1:
        raise ValueError('replicates must be positive')
    data=np.load(args.predictions,allow_pickle=False)
    result=bootstrap(data['targets'],data['event_ids'],data['raw_mean'],data[args.candidate],args.replicates,args.seed)
    here=Path(__file__).resolve().parent
    config={**vars(args),'predictions':str(args.predictions),
            'predictions_sha256':sha256(args.predictions)}
    out=create_run(ROOT/'results/2026-10-09/phase2','paired_event_bootstrap',config,
                   list(here.glob('*.py'))+list(here.parent.glob('*.py')))
    (out/'intervals.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print('FINISHED',out,result['paired_delta_intervals'],flush=True)


if __name__=='__main__':
    main()

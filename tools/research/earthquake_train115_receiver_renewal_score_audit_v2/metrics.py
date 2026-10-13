"""Independent descriptive metrics, paired groups and strict24 guards."""
import math
import numpy as np

SEEDS=(20261012,20261013)
ARMS=('B','F','H','T','C')
HORIZONS=(1,3,5)


def metrics(predictions):
    y,mean,median,nll,crps=(np.asarray([p[k]for p in predictions],dtype=np.float64)for k in('target','mean','median','nll','crps'))
    absolute=np.abs(mean-y);high=y>=5.5;higher=y>=6;lower=y<5.5
    def subset(mask,median=False):
        return float((np.median if median else np.mean)(absolute[mask]))if mask.any()else None
    out=dict(n=len(y),nll=float(nll.mean()),crps=float(crps.mean()),mae=float(absolute.mean()),medae=float(np.median(absolute)),
             tail_mae_5_5=subset(high),tail_mae_6=subset(higher),lower_mae=subset(lower),lower_medae=subset(lower,True),
             tail_bias=float((mean-y)[high].mean())if high.any()else None,cvar95=float(np.sort(absolute)[-max(1,math.ceil(.05*len(y))):].mean()),
             maximum=float(absolute.max()),p95=float(np.quantile(absolute,.95,method='linear')),median_mae=float(np.abs(median-y).mean()))
    for level in(50,80,95):out['coverage_%d'%level]=float(np.mean([p['coverage_%d'%level]for p in predictions]))
    return out


def strata(predictions):
    result={}
    for h in HORIZONS:
        p=[v for v in predictions if v['horizon']==h];panel={}
        for kind,key in(('families','family'),('receivers','receiver'),('groups','group'),('rates','rate')):
            values=sorted({tuple(v[key])if type(v[key])is list else v[key]for v in p});entries=[]
            for value in values:
                selected=[v for v in p if (tuple(v[key])if type(v[key])is list else v[key])==value]
                entries.append({key:list(value)if type(value)is tuple else value,'metrics':metrics(selected)})
            panel[kind]=entries
        result[str(h)]=panel
    return result


def paired(left,right):
    if [(p['ordinal'],p['target'],p['group'])for p in left]!=[(p['ordinal'],p['target'],p['group'])for p in right]:raise ValueError('pair_binding')
    lm,rm=metrics(left),metrics(right);groups=sorted({p['group']for p in left})
    category={}
    for key in lm:
        if key=='n':continue
        ids={p['group']for p in left if (p['target']>=5.5 if key in('tail_mae_5_5','tail_bias')else p['target']>=6 if key=='tail_mae_6'else p['target']<5.5 if key in('lower_mae','lower_medae')else True)}
        category[key]=len(ids)
    draws={k:[]for k,n in category.items()if n>=3};rng=np.random.default_rng(9919)
    if draws:
        indices={g:[i for i,p in enumerate(left)if p['group']==g]for g in groups}
        for _ in range(1000):
            selected=[i for g in rng.choice(groups,len(groups),replace=True)for i in indices[g]]
            a,b=metrics([left[i]for i in selected]),metrics([right[i]for i in selected])
            for k in draws:
                if a[k]is not None and b[k]is not None:draws[k].append(a[k]-b[k])
    out={}
    for k,n in category.items():
        delta=lm[k]-rm[k]if lm[k]is not None and rm[k]is not None else None
        supported=n>=3 and len(draws[k])==1000
        out[k]=dict(status='descriptive'if supported else'unsupported',groups=n,delta=delta,interval=[float(v)for v in np.quantile(draws[k],[.025,.975])]if supported else None)
    return out


def advance(fits):
    if len(fits)!=10 or any(f['status']!='complete'for f in fits):return dict(pass_all=False,checks=[])
    checks=[]
    for seed in SEEDS:
        by={f['arm']:f for f in fits if f['seed']==seed}
        if set(by)!=set(ARMS):return dict(pass_all=False,checks=[])
        for h in HORIZONS:
            c=by['C']['metrics'][str(h)]
            for comparator in ARMS[:-1]:
                b=by[comparator]['metrics'][str(h)]
                tail=c['tail_mae_5_5']is not None and b['tail_mae_5_5']is not None and b['tail_mae_5_5']-c['tail_mae_5_5']>=.02
                proper=c['nll']<b['nll']and c['crps']<b['crps']if comparator in('B','F')else True
                bulk={k:c[k]is not None and b[k]is not None and c[k]<=b[k]for k in('mae','medae','lower_mae','lower_medae','cvar95','maximum')}
                checks.append(dict(seed=seed,horizon=h,comparator=comparator,tail=tail,proper=proper,bulk_worst=bulk,passed=tail and proper and all(bulk.values())))
    return dict(pass_all=all(v['passed']for v in checks),checks=checks)

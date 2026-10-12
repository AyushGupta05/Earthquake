"""Exact group-weighted risk and fixed paired-group descriptive bootstrap."""
import math
from collections import Counter
import numpy as np


def weights(rows, multiplicities=None):
    counts = Counter(r['group'] for r in rows)
    mult = dict.fromkeys(counts,1) if multiplicities is None else multiplicities
    w = np.array([mult.get(r['group'],0)/counts[r['group']] for r in rows],dtype=float)
    total = float(w.sum())
    if total <= 0:
        return None
    return w/total


def weighted_median(values, w):
    ordered = np.argsort(values,kind='stable')
    cumulative = 0.
    for i in ordered:
        cumulative += float(w[i])
        if cumulative >= .5:
            return float(values[i])
    raise ArithmeticError('median_weights_not_normalized')


def cvar95(errors,w):
    remain = .05
    value = 0.
    for i in np.argsort(-errors,kind='stable'):
        take = min(remain,float(w[i]))
        value += take*float(errors[i])
        remain -= take
        if remain <= 1e-15:
            return value/.05
    raise ArithmeticError('cvar_mass_unknown')


def summarize(rows, arm, multiplicities=None):
    w=weights(rows,multiplicities)
    if w is None:return None
    selected=np.array([w[i]>0 for i in range(len(w))])
    pred=np.array([r[arm]['mean'] for r in rows]);truth=np.array([r['mw'] for r in rows])
    errors=np.abs(pred-truth)
    out={'events':int(selected.sum()),'groups':len({r['group'] for i,r in enumerate(rows) if selected[i]}),
         'nll':float(w@np.array([r[arm]['nll'] for r in rows])),
         'crps':float(w@np.array([r[arm]['crps'] for r in rows])),
         'mae':float(w@errors),'medae':weighted_median(errors,w),
         'cvar95':cvar95(errors,w),'maximum':float(errors[selected].max()),
         'bias':float(w@(pred-truth))}
    for name,predicate in [('high5_5',lambda m:m>=5.5),('high6',lambda m:m>=6),('lower',lambda m:m<5.5)]:
        idx=[i for i,r in enumerate(rows) if predicate(r['mw']) and selected[i]]
        if not idx:out[name]=None;continue
        # Keep original all-event group weights, then renormalize the subset.
        sw=w[idx]/w[idx].sum();e=errors[idx]
        out[name]={'events':len(idx),'groups':len({rows[i]['group'] for i in idx}),
                   'mae':float(sw@e),'medae':weighted_median(e,sw),'cvar95':cvar95(e,sw),
                   'maximum':float(e.max()),'bias':float(sw@(pred[idx]-truth[idx]))}
    if not all(math.isfinite(out[k]) for k in ('nll','crps','mae','medae','cvar95','maximum','bias')):
        raise ArithmeticError('nonfinite_metrics')
    return out


def observed_gate(metrics):
    checks=[]
    for h in (1,3,5):
        m,p=metrics[str(h)]['model'],metrics[str(h)]['prior']
        valid=m['high5_5'] is not None and p['high5_5'] is not None
        checks.append(bool(valid and m['nll']<p['nll'] and m['crps']<p['crps']
                           and p['high5_5']['mae']-m['high5_5']['mae']>=.02
                           and all(m[k]<=p[k] for k in ('mae','medae','cvar95','maximum'))))
    return {'per_horizon':dict(zip(('1','3','5'),checks)),'passed':all(checks)}


def bootstrap(predictions, deadline, check_deadline):
    groups=sorted({r['group'] for r in predictions['1']})
    rng=np.random.default_rng(9919)
    differences={str(h):{k:[] for k in ('nll','crps','mae','high5_5_mae','medae','cvar95','maximum')}
                 for h in (1,3,5)}
    for _ in range(1000):
        check_deadline(deadline)
        mult=Counter(rng.choice(groups,len(groups),replace=True).tolist())
        for h in ('1','3','5'):
            m=summarize(predictions[h],'model',mult);p=summarize(predictions[h],'prior',mult)
            for k in differences[h]:
                if k=='high5_5_mae':
                    if m['high5_5'] is None or p['high5_5'] is None:continue
                    delta=m['high5_5']['mae']-p['high5_5']['mae']
                else:delta=m[k]-p[k]
                differences[h][k].append(delta)
    return {'seed':9919,'replicates':1000,'descriptive_only':True,
            'physical_sequence_independence':False,'delta_model_minus_prior':{
                h:{k:{'usable':len(v),'quantiles_2_5_50_97_5':np.quantile(v,[.025,.5,.975]).tolist() if v else None}
                   for k,v in panels.items()} for h,panels in differences.items()}}

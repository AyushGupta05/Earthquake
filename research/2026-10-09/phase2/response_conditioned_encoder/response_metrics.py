"""Prespecified response-encoder metrics and C-minus-B paired event gate.

Pure NumPy. Mean/median actions and all thresholds are fixed before fitting.
Weighted record metrics restore sampling; within-event averages are unweighted.
"""
from types import SimpleNamespace
import numpy as np

CENTERS=np.arange(66,dtype=np.float64)*.1
SEEDS=(20261009,20261010)
DEADLINES=(1,3,5)
SUBSETS=('eval_seen','eval_held')


def checked_p(p,n):
    p=np.asarray(p,dtype=np.float64)
    if p.shape!=(n,66) or not np.isfinite(p).all() or (p<0).any() or not np.allclose(p.sum(1),1,rtol=0,atol=1e-8):
        raise ValueError('Finite normalized aligned N x66 PMFs required')
    return p


def wquantile(v,w,q):
    order=np.argsort(v,kind='stable');index=np.searchsorted(np.cumsum(w[order]),q*w.sum(),side='left')
    return float(v[order[min(index,len(order)-1)]])


def point(pred,y,w,event):
    pred=np.asarray(pred);y=np.asarray(y);w=np.asarray(w);event=np.asarray(event)
    if not len(y) or pred.shape!=y.shape or w.shape!=y.shape or event.shape!=y.shape or not np.isfinite(pred).all() or not np.isfinite(y).all() or not np.isfinite(w).all() or (w<=0).any():
        raise ValueError('Nonempty finite aligned point population required')
    error=pred-y;ae=np.abs(error);ids,inv=np.unique(event,return_inverse=True)
    em=np.bincount(inv,weights=ae)/np.bincount(inv);eb=np.bincount(inv,weights=error)/np.bincount(inv)
    order=np.argsort(-ae,kind='stable');mass=.05*w.sum();before=np.r_[0.,np.cumsum(w[order])[:-1]]
    amount=np.minimum(w[order],np.maximum(mass-before,0))
    result={'records':len(y),'events':len(ids),'weighted_mae':float(np.average(ae,weights=w)),
        'medae':wquantile(ae,w,.5),'weighted_bias':float(np.average(error,weights=w)),
        'cvar95':float((ae[order]*amount).sum()/mass),'event_macro_mae':float(em.mean()),
        'individual_events':{str(e):{'mae':float(a),'bias':float(b)} for e,a,b in zip(ids,em,eb)},'tail':{}}
    for threshold in (4,5):
        ix=y>=threshold;tid,tinv=np.unique(event[ix],return_inverse=True)
        row={'records':int(ix.sum()),'events':len(tid)}
        if ix.any():row.update(weighted_mae=float(np.average(ae[ix],weights=w[ix])),weighted_bias=float(np.average(error[ix],weights=w[ix])),
            event_macro_mae=float((np.bincount(tinv,weights=ae[ix])/np.bincount(tinv)).mean()))
        result['tail'][str(threshold)]=row
    return result


def mean_action(p):return (p*CENTERS[None]).sum(1)
def median_action(p):return CENTERS[(p.cumsum(1)<.5).sum(1).clip(max=65)]


def scores(p,y,w,event):
    p=checked_p(p,len(y));y=np.asarray(y);w=np.asarray(w)
    cdf=p.cumsum(1);previous=np.c_[np.zeros(len(p)),cdf[:,:-1]]
    moment=np.c_[np.zeros(len(p)),(p*CENTERS).cumsum(1)[:,:-1]]
    crps=(p*np.abs(CENTERS-y[:,None])).sum(1)-(p*(CENTERS*previous-moment)).sum(1)
    labels=np.floor(y/.1+1e-5).astype(np.int64).clip(0,65)
    truep=p[np.arange(len(p)),labels]
    lo=(cdf<.05).sum(1).clip(max=65);hi=(cdf<.95).sum(1).clip(max=65)
    dist={'continuous_label_crps':float(np.average(crps,weights=w)),
          'clipped_category_nll':float(np.average(-np.log(truep),weights=w)) if (truep>0).all() else None,
          'nll_infinite':bool((truep==0).any()),'outside_center_support_records':int(((y<0)|(y>6.5)).sum()),
          'center_interval90_coverage':float(np.average((y>=CENTERS[lo])&(y<=CENTERS[hi]),weights=w)),
          'tail_calibration':{}}
    for threshold in (4,5):
        prob=p[:,CENTERS>=threshold].sum(1);observed=y>=threshold;bins=np.minimum((prob*10).astype(int),9);rows=[]
        for b in range(10):
            ix=bins==b;r={'bin':b,'records':int(ix.sum())}
            if ix.any():r.update(predicted=float(np.average(prob[ix],weights=w[ix])),observed=float(np.average(observed[ix],weights=w[ix])))
            rows.append(r)
        dist['tail_calibration'][str(threshold)]={'weighted_brier':float(np.average((prob-observed)**2,weights=w)),'bins':rows}
    return {'mean':point(mean_action(p),y,w,event),'median':point(median_action(p),y,w,event),'distribution':dist}


def deltas(a,b):
    return {'weighted_mae':a['weighted_mae']-b['weighted_mae'],'medae':a['medae']-b['medae'],
            'm4_weighted_mae':a['tail']['4']['weighted_mae']-b['tail']['4']['weighted_mae'] if a['tail']['4']['records'] else None,
            'm4_event_macro_mae':a['tail']['4']['event_macro_mae']-b['tail']['4']['event_macro_mae'] if a['tail']['4']['records'] else None}


def paired_bootstrap(a,b,y,w,event,replicates=1000):
    """Paired cluster draws for bulk; independent tail-only event draws for tail.

    Fixed sorting makes weighted MedAE exact without sorting every replicate.
    Tail resampling is conditional on the observed M>=4 event population.
    """
    if replicates!=1000:raise ValueError('Exactly1000 fixed replicates required')
    ae=np.abs(mean_action(checked_p(a,len(y)))-y);be=np.abs(mean_action(checked_p(b,len(y)))-y)
    ids,inv=np.unique(event,return_inverse=True);rng=np.random.default_rng(20261011)
    ad=np.argsort(ae,kind='stable');bd=np.argsort(be,kind='stable');bulk=[];med=[]
    for _ in range(replicates):
        multiplicity=np.bincount(rng.integers(len(ids),size=len(ids)),minlength=len(ids));rw=w*multiplicity[inv]
        bulk.append(float(np.average(ae-be,weights=rw)))
        def mq(v,order):
            j=np.searchsorted(np.cumsum(rw[order]),.5*rw.sum(),side='left');return v[order[min(j,len(order)-1)]]
        med.append(float(mq(ae,ad)-mq(be,bd)))
    out={'replicates':replicates,'seed':20261011,'weighted_mae':np.quantile(bulk,[.025,.975]).tolist(),
         'medae':np.quantile(med,[.025,.975]).tolist()}
    tail=y>=4;tid,ti=np.unique(event[tail],return_inverse=True)
    if len(tid):
        d=(ae-be)[tail];tw=w[tail];s=np.bincount(ti,weights=tw*d);mass=np.bincount(ti,weights=tw)
        em=np.bincount(ti,weights=d)/np.bincount(ti);record=[];macro=[]
        for _ in range(replicates):
            ix=rng.integers(len(tid),size=len(tid));record.append(float(s[ix].sum()/mass[ix].sum()));macro.append(float(em[ix].mean()))
        out.update(m4_weighted_mae=np.quantile(record,[.025,.975]).tolist(),m4_event_macro_mae=np.quantile(macro,[.025,.975]).tolist())
    return out


def primary_gate(comparisons):
    expected={(t,s) for t in DEADLINES for s in SUBSETS}
    if len(comparisons)!=6 or {(r['seconds'],r['subset']) for r in comparisons}!=expected:
        return {'status':'incomplete','pass':False}
    checks=[];enough=True
    def pass_delta(d):return all(d[k] is not None and np.isfinite(d[k]) and d[k]<=.002 for k in ('weighted_mae','medae')) and all(d[k] is not None and np.isfinite(d[k]) and d[k]<0 for k in ('m4_weighted_mae','m4_event_macro_mae'))
    for r in comparisons:
        support=r['m4_events']>=20 and r['valid_fraction']>=.9;enough &=support
        exact_seeds=set(r['seed_deltas'])=={str(s) for s in SEEDS}
        seed_pass=exact_seeds and all(pass_delta(d) for d in r['seed_deltas'].values())
        b=r['bootstrap'];bounds={k:v[1] for k,v in b.items() if isinstance(v,list)}
        uncertainty=set(bounds)=={'weighted_mae','medae','m4_weighted_mae','m4_event_macro_mae'} and pass_delta(bounds)
        checks.append({'seconds':r['seconds'],'subset':r['subset'],'support':support,'both_seed_effects':seed_pass,'ensemble_uncertainty':uncertainty})
    # Missing precision is not evidence that the observed effect failed.
    if not enough:status='inconclusive_support'
    elif not all(c['both_seed_effects'] for c in checks):status='failed'
    elif not all(c['ensemble_uncertainty'] for c in checks):status='inconclusive_precision'
    else:status='pass'
    return {'status':status,'pass':status=='pass','checks':checks,'scope':'Exploratory all-panel C-minus-B gate, not familywise confirmation'}

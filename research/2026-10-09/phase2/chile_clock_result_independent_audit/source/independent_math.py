"""Independent saved-parameter math; no model, training or production imports."""
import hashlib
import math
import numpy as np

TIMES=(1,3,5)
ACTIONS=('mean','median')
ATOL=RTOL=1e-9
KEYS={'event_ids','targets'}|{f'{name}_{t}s' for t in TIMES for name in ('logits','weights','means','scales','mean','median','nll','crps')}

def validate(p):
    if set(p)!=KEYS:raise ValueError('exact26 prediction keys required')
    ids=np.asarray(p['event_ids']);y=np.asarray(p['targets'])
    if ids.ndim!=1 or ids.dtype.kind!='U' or len(ids)==0 or len(set(ids.tolist()))!=len(ids) or y.shape!=ids.shape or y.dtype!=np.float64 or not np.isfinite(y).all():raise ValueError('invalid unique aligned identities/targets')
    for t in TIMES:
        for name in ('logits','weights','means','scales','mean','median','nll','crps'):
            a=np.asarray(p[f'{name}_{t}s']);shape=(len(y),5) if name in ('logits','weights','means','scales') else (len(y),)
            if a.dtype!=np.float64 or a.shape!=shape or not np.isfinite(a).all():raise ValueError('invalid saved array shape/dtype/finite values')
            if name in ('logits','weights','means','scales') and not np.array_equal(a,a.astype(np.float32).astype(np.float64)):raise ValueError('parameters not native float32 copies')
        w=p[f'weights_{t}s'];s=p[f'scales_{t}s'];logits=p[f'logits_{t}s']
        if (w<0).any() or (s<=0).any() or (np.abs(w.sum(axis=1)-1)>1e-6).any():raise ValueError('invalid stored mass/scales')
        shifted=logits-logits.max(axis=1,keepdims=True);soft=np.exp(shifted);soft/=soft.sum(axis=1,keepdims=True)
        if (np.abs(soft-w)>1e-6).any():raise ValueError('stored weights differ from logit softmax')
    return y

def erf(a):
    a=np.asarray(a,dtype=np.float64)
    return np.fromiter((math.erf(float(x)) for x in a.flat),dtype=np.float64,count=a.size).reshape(a.shape)

def parameter_scores(logits,w,mu,s,y):
    mean=np.sum(w*mu,axis=1)
    lo=np.min(mu-12*s,axis=1);hi=np.max(mu+12*s,axis=1)
    for _ in range(48):
        mid=(lo+hi)/2;cdf=np.sum(w*.5*(1+erf((mid[:,None]-mu)/(s*math.sqrt(2)))),axis=1)
        lo=np.where(cdf<.5,mid,lo);hi=np.where(cdf>=.5,mid,hi)
    shifted=logits-logits.max(axis=1,keepdims=True);logw=shifted-np.log(np.exp(shifted).sum(axis=1,keepdims=True))
    terms=logw-.5*((y[:,None]-mu)/s)**2-np.log(s)-.5*math.log(2*math.pi)
    largest=np.max(terms,axis=1);nll=-largest-np.log(np.exp(terms-largest[:,None]).sum(axis=1))
    def absolute(d,scale):return scale*math.sqrt(2/math.pi)*np.exp(-.5*(d/scale)**2)+d*erf(d/(scale*math.sqrt(2)))
    first=np.sum(w*absolute(y[:,None]-mu,s),axis=1)
    second=np.sum(w[:,:,None]*w[:,None,:]*absolute(mu[:,:,None]-mu[:,None,:],np.sqrt(s[:,:,None]**2+s[:,None,:]**2)),axis=(1,2))
    result={'mean':mean,'median':(lo+hi)/2,'nll':nll,'crps':first-.5*second}
    if not all(np.isfinite(v).all() for v in result.values()):raise ValueError('nonfinite independent scores')
    return result

def compare_arrays(actual,expected):
    a=np.asarray(actual,dtype=np.float64);e=np.asarray(expected,dtype=np.float64)
    if a.shape!=e.shape or not np.isfinite(a).all() or not np.isfinite(e).all():return {'passed':False,'shape_or_finite_failure':True}
    difference=np.abs(a-e)
    return {'passed':bool(np.all(difference<=ATOL+RTOL*np.abs(e))),'mismatched_values':int(np.count_nonzero(difference>ATOL+RTOL*np.abs(e))),'maximum_absolute_difference':float(difference.max()) if difference.size else 0.0}

def replay_arrays(p):
    y=validate(p);checks={}
    for t in TIMES:
        r=parameter_scores(p[f'logits_{t}s'],p[f'weights_{t}s'],p[f'means_{t}s'],p[f'scales_{t}s'],y)
        checks[str(t)]={k:compare_arrays(v,p[f'{k}_{t}s']) for k,v in r.items()}
    return {'passed':all(v['passed'] for h in checks.values() for v in h.values()),'checks':checks,'events':len(y),'atol':ATOL,'rtol':RTOL}

def percentile(a,q):
    values=np.sort(np.asarray(a,dtype=np.float64))
    if not len(values):return None
    h=(len(values)-1)*q;i=math.floor(h);j=math.ceil(h)
    return float(values[i]+(values[j]-values[i])*(h-i))

def errors(pred,target):
    signed=np.asarray(pred)-target;a=np.abs(signed);sorted_a=np.sort(a);tail=target>=5.5;n=len(a)
    if not n:raise ValueError('empty event cohort')
    return {'events':n,'mae':float(a.sum()/n),'medae':percentile(a,.5),'bias':float(signed.sum()/n),'cvar95':float(sorted_a[-max(1,math.ceil(.05*n)):].mean()),'p95':percentile(a,.95),'maximum':float(sorted_a[-1]),'tail_events':int(tail.sum()),'tail_mae':float(a[tail].mean()) if tail.any() else None,'tail_medae':percentile(a[tail],.5) if tail.any() else None}

def scores(p):
    y=validate(p);result={}
    for t in TIMES:
        result[str(t)]={action:errors(p[f'{action}_{t}s'],y) for action in ACTIONS}
        result[str(t)].update(proper_nll=float(p[f'nll_{t}s'].mean()),crps=float(p[f'crps_{t}s'].mean()))
    return {'deadlines':result,'mean_mae_equal_deadline_average':float(sum(result[str(t)]['mean']['mae'] for t in TIMES)/3),'tail_events':int((y>=5.5).sum())}

def statistics(p,ix):
    y=p['targets'][ix];answer={}
    for t in TIMES:
        for action in ACTIONS:
            r=errors(p[f'{action}_{t}s'][ix],y)
            for k in ('mae','medae','bias','cvar95','p95','maximum','tail_mae','tail_medae'):answer[f'{t}.{action}.{k}']=r[k]
        for k in ('nll','crps'):answer[f'{t}.{k}']=float(p[f'{k}_{t}s'][ix].mean())
    answer['equal_deadline_mean_mae']=float(sum(answer[f'{t}.mean.mae'] for t in TIMES)/3)
    return answer

def index_digest(indices):return hashlib.sha256(np.asarray(indices,dtype='<i8').tobytes(order='C')).hexdigest()

def validate_indices(indices,n,expected_sha):
    if indices.dtype!=np.int64 or indices.shape!=(2000,n) or (indices<0).any() or (indices>=n).any() or index_digest(indices)!=expected_sha:raise ValueError('fixed2000 index shape/range/checksum mismatch')

def paired(candidate,reference,indices,expected_sha):
    y=validate(candidate);validate(reference)
    if not np.array_equal(candidate['event_ids'],reference['event_ids']) or not np.array_equal(y,reference['targets']):raise ValueError('paired event/target alignment mismatch')
    validate_indices(indices,len(y),expected_sha)
    c=statistics(candidate,np.arange(len(y)));r=statistics(reference,np.arange(len(y)))
    delta={k:c[k]-r[k] if c[k] is not None else None for k in c};samples={k:[] for k in c}
    for ix in indices:
        ca=statistics(candidate,ix);re=statistics(reference,ix)
        for k in samples:
            if ca[k] is not None:samples[k].append(ca[k]-re[k])
    ci={k:{'low':percentile(v,.025),'high':percentile(v,.975),'valid_draws':len(v),'requested_draws':2000} for k,v in samples.items()}
    return {'delta_discrete_minus_source':delta,'paired_event_ci95':ci,'events':len(y),'tail_events':int((y>=5.5).sum()),'bootstrap_seed':20261013,'bootstrap_draws':2000,'bootstrap_indices_sha256':expected_sha}

def gate(comparisons):
    if set(comparisons)!={'20261011','20261012'}:raise ValueError('both frozen seeds required')
    checks={}
    for seed,row in comparisons.items():
        d=row['delta_discrete_minus_source'];ci=row['paired_event_ci95']
        checks[seed]={'point_and_margin':d['equal_deadline_mean_mae']<0 and all(d[f'{t}.mean.{k}']<=.002 for t in TIMES for k in ('mae','medae')),'bulk_ci_excludes_no_benefit':ci['equal_deadline_mean_mae']['high'] is not None and ci['equal_deadline_mean_mae']['high']<0,'proper_nll_tradeoff':any(d[f'{t}.nll']>0 for t in TIMES),'mean_worst_error_regression':{str(t):[k for k in ('cvar95','p95','maximum') if d[f'{t}.mean.{k}']>0] for t in TIMES}}
    points=all(r['point_and_margin'] for r in checks.values());certain=all(r['bulk_ci_excludes_no_benefit'] for r in checks.values())
    return {'status':'failed' if not points else 'pass' if certain else 'inconclusive','point_criteria_pass':points,'checks':checks}

def compare_tree(actual,expected):
    """Numeric outputs only. Exact discrete values, fixed tolerance for floats."""
    failures=[]
    def visit(a,e,path):
        if isinstance(a,dict):
            if not isinstance(e,dict):failures.append(path+':type');return
            for k in a:
                if k not in e:failures.append(path+'.'+k+':missing')
                else:visit(a[k],e[k],path+'.'+k)
        elif isinstance(a,float):
            if type(e) not in (float,int) or not math.isfinite(e) or abs(a-e)>ATOL+RTOL*abs(e):failures.append(path+':value')
        elif a!=e:failures.append(path+':exact')
    visit(actual,expected,'root')
    return {'passed':not failures,'mismatches':failures}

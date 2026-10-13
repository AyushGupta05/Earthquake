"""Fixed cohort gate, TRAIN-only preprocessing and six bounded CPU fits."""

import math
from fractions import Fraction
import time
import numpy as np
import mixture_density as density

SEEDS=(20261012,20261013)
ARMS=("W","M","P")
HORIZONS=(1,3,5)
CONTINUOUS=(0,1,2,3,4,5,11,12,13)
UPDATES=300


def gate(manifest):
    from artifact import validate_manifest
    validate_manifest(manifest)
    rows=manifest["rows"]
    if len(rows)!=115 or [r["ordinal"] for r in rows]!=list(range(115)) or sum(len(r["cells"]) for r in rows)!=345:raise ValueError("manifest_denominator")
    common=[r for r in rows if r["cohort"]]
    train=[r for r in common if r["partition"]=="TRAIN"];dev=[r for r in common if r["partition"]=="DEV"]
    counts=dict(train=len(train),dev=len(dev),train_high=sum(r["mw"]>=5.5 for r in train),
                dev_high=sum(r["mw"]>=5.5 for r in dev),train_lower=sum(r["mw"]<5.5 for r in train),
                dev_lower=sum(r["mw"]<5.5 for r in dev),dev_high_groups=len({r["group"] for r in dev if r["mw"]>=5.5}))
    shared={r["group"] for r in train}&{r["group"] for r in dev}
    passed=not shared and all(counts[k]>=v for k,v in dict(train=20,dev=12,train_high=8,dev_high=5,train_lower=5,dev_lower=5,dev_high_groups=3).items())
    counts['old_train']=sum(r['ordinal']<65 for r in train)
    counts['new_train']=sum(r['ordinal']>=65 for r in train)
    counts['old_train_high']=sum(r['ordinal']<65 and r['mw']>=5.5 for r in train)
    counts['new_train_high']=sum(r['ordinal']>=65 and r['mw']>=5.5 for r in train)
    counts['old_train_lower']=counts['old_train']-counts['old_train_high']
    counts['new_train_lower']=counts['new_train']-counts['new_train_high']
    counts['unknown_groups']=sum(r['group']<0 for r in rows)
    panels={source:{str(h):sum(r['cells'][j]['status']=='available' for r in rows if r['source']==source) for j,h in enumerate(HORIZONS)} for source in ('original65','new50')}
    return dict(status="pass" if passed else "fail",counts=counts,train=[r["ordinal"] for r in train],dev=[r["ordinal"] for r in dev],status_panels=panels,DEV_reused_exploratory=True)


def standardize(context,train):
    out=np.array(context,dtype=np.float64,copy=True)
    mean=np.zeros(29);std=np.ones(29)
    for column in CONTINUOUS:
        values=out[train,:,column]
        mean[column]=values.mean();std[column]=values.std(ddof=0)
        out[:,:,column]=(out[:,:,column]-mean[column])/std[column] if std[column]>0 else 0
    return out,mean,std


def permutation(train):
    return np.random.default_rng(7919).permutation(np.asarray(train,dtype=np.int64))


def event_order(train,seed):
    rng=np.random.default_rng(seed+1009)
    for _ in range(UPDATES):yield rng.choice(train,size=8,replace=False)


def _vectors(predictions):
    result={k:np.asarray([p[k] for p in predictions],dtype=np.float64) for k in ("target","mean","median","nll","crps")}
    for coverage in (.5,.9,.95):
        tail=(1-coverage)/2
        result["coverage_%d"%round(coverage*100)]=np.asarray([density.quantile(tail,p["pi"],p["mu"],p["sigma"])<=p["target"]<=density.quantile(1-tail,p["pi"],p["mu"],p["sigma"]) for p in predictions],dtype=np.float64)
    return result


def _summary(v):
    y=v["target"];error=v["mean"]-y;absolute=np.abs(error);high=y>=5.5;higher=y>=6;lower=y<5.5
    result=dict(n=len(y),nll=float(v["nll"].mean()),crps=float(v["crps"].mean()),mae=float(absolute.mean()),medae=float(np.median(absolute)),
                tail_mae_5_5=float(absolute[high].mean()) if high.any() else None,tail_mae_6=float(absolute[higher].mean()) if higher.any() else None,
                tail_bias=float(error[high].mean()) if high.any() else None,lower_mae=float(absolute[lower].mean()) if lower.any() else None,
                lower_medae=float(np.median(absolute[lower])) if lower.any() else None,cvar95=float(np.sort(absolute)[-max(1,math.ceil(.05*len(y))):].mean()),
                p95=float(np.quantile(absolute,.95,method="linear")),maximum=float(absolute.max()),median_mae=float(np.abs(v["median"]-y).mean()))
    for k in ("coverage_50","coverage_90","coverage_95"):result[k]=float(v[k].mean())
    return result


def metrics(predictions):return _summary(_vectors(predictions))


def original_advance(results):
    if len(results)!=6 or any(r["status"]!="complete" for r in results):return False
    for seed in SEEDS:
        by={r["arm"]:r for r in results if r["seed"]==seed}
        if set(by)!=set(ARMS):return False
        for h in HORIZONS:
            w,m,p=(by[a]["metrics"][str(h)] for a in ARMS)
            if not (w["nll"]<m["nll"] and w["crps"]<m["crps"] and w["nll"]<p["nll"] and w["crps"]<p["crps"]
                    and w["tail_mae_5_5"] is not None and m["tail_mae_5_5"] is not None and m["tail_mae_5_5"]-w["tail_mae_5_5"]>=.02
                    and all(w[k] is not None and m[k] is not None and w[k]<=m[k] for k in ("lower_mae","lower_medae","cvar95","maximum"))):return False
    return True



def bulk_guard(results):
    checks=[]
    if len(results)!=6 or any(r['status']!='complete' for r in results):return dict(pass_all=False,checks=checks)
    for seed in SEEDS:
        by={r['arm']:r for r in results if r['seed']==seed}
        if set(by)!=set(ARMS):return dict(pass_all=False,checks=checks)
        for h in HORIZONS:
            w,m=(by[a]['metrics'][str(h)] for a in ('W','M'))
            checks.append(dict(seed=seed,horizon=h,mae_not_worse=w['mae']<=m['mae'],medae_not_worse=w['medae']<=m['medae']))
    return dict(pass_all=all(v['mae_not_worse'] and v['medae_not_worse'] for v in checks),checks=checks)


def advance(results):return original_advance(results) and bulk_guard(results)['pass_all']


def _deadline(begin,fit_begin=None):
    if type(begin) not in (int,float) or not math.isfinite(begin) or begin<0:raise ValueError('processing_begin')
    now=time.monotonic()
    if now<begin or now-begin>1800 or fit_begin is not None and now-fit_begin>300:raise RuntimeError('fit_deadline')

def paired_intervals(left,right,groups):
    if ([p["ordinal"] for p in left]!=[p["ordinal"] for p in right]
            or [p["target"] for p in left]!=[p["target"] for p in right]):raise ValueError("paired_order")
    a,b=_vectors(left),_vectors(right);pointa,pointb=_summary(a),_summary(b)
    gid=np.asarray([groups[p["ordinal"]] for p in left]);y=a["target"];unique=np.unique(gid)
    supported={}
    for name in pointa:
        if name=="n":continue
        mask=y>=5.5 if name in ("tail_mae_5_5","tail_bias") else y>=6 if name=="tail_mae_6" else y<5.5 if name in ("lower_mae","lower_medae") else np.ones(len(y),dtype=bool)
        contributors=len(np.unique(gid[mask]));supported[name]=contributors
    draws={k:[] for k,n in supported.items() if n>=3}
    rng=np.random.default_rng(9919)
    for _ in range(1000):
        selected=rng.choice(unique,size=len(unique),replace=True)
        indices=np.concatenate([np.flatnonzero(gid==g) for g in selected])
        sa=_summary({k:v[indices] for k,v in a.items()});sb=_summary({k:v[indices] for k,v in b.items()})
        for k in draws:
            if sa[k] is not None and sb[k] is not None:draws[k].append(sa[k]-sb[k])
    result={}
    for k,n in supported.items():
        delta=pointa[k]-pointb[k] if pointa[k] is not None and pointb[k] is not None else None
        if n<3 or len(draws[k])!=1000:result[k]=dict(status="unsupported",groups=n,mean=delta)
        else:result[k]=dict(status="descriptive",groups=n,mean=delta,interval=[float(x) for x in np.quantile(draws[k],[.025,.975])])
    return result


def rate_strata(predictions,groups):
    result=[]
    for rate in sorted({tuple(p["rate"]) for p in predictions}):
        selected=[p for p in predictions if tuple(p["rate"])==rate]
        n_groups=len({int(groups[p["ordinal"]]) for p in selected})
        result.append(dict(rate=list(rate),n=len(selected),groups=n_groups,status="descriptive" if n_groups>=3 else "unsupported",metrics=metrics(selected)))
    return result


def run(arrays,manifest,checkpoint,history=None,*,processing_begin):
    """Actual execution only after external/live controls; never called by source tests."""
    _deadline(processing_begin)
    from artifact import validate_arrays
    validate_arrays(arrays,manifest)
    support=gate(manifest)
    if support["status"]!="pass":return dict(status="gate_failed",support=support,fits=[],original_advance=False,bulk_guard=dict(pass_all=False,checks=[]),advance=False)
    _deadline(processing_begin)
    import torch
    from model import PilotNet,mixture_nll
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    train,dev=support["train"],support["dev"]
    contexts,mean,std=standardize(arrays["contexts"],train)
    label_perm=dict(zip(train,permutation(train)))
    started=processing_begin;fits=[]
    for seed in SEEDS:
        for arm in ARMS:
            fit=dict(seed=seed,arm=arm,status="incomplete",history=[],predictions=[],metrics={})
            fits.append(fit);fit_start=time.monotonic()
            try:
                torch.manual_seed(seed);net=PilotNet();net.initialize(float(arrays["magnitudes"][train].mean()),float(arrays["magnitudes"][train].std(ddof=0)))
                optimizer=torch.optim.Adam(net.parameters(),lr=1e-3,weight_decay=0)
                for step,event_ids in enumerate(event_order(train,seed)):
                    _deadline(started,fit_start)
                    batch=[(int(i),j,h) for i in event_ids for j,h in enumerate(HORIZONS)]
                    lengths=[arrays["wave_%03d_%d"%(i,h)].shape[1] for i,j,h in batch]
                    wave=torch.zeros((24,3,max(lengths)),dtype=torch.float32);mask=torch.zeros((24,max(lengths)),dtype=torch.bool)
                    for k,(i,j,h) in enumerate(batch):
                        wave[k,:,:lengths[k]]=torch.from_numpy(arrays["wave_%03d_%d"%(i,h)]);mask[k,:lengths[k]]=True
                    amplitude=torch.from_numpy(np.asarray([arrays["amplitudes"][i,j] for i,j,h in batch],dtype=np.float32))
                    ctx=torch.from_numpy(np.asarray([contexts[i,j] for i,j,h in batch],dtype=np.float32))
                    labels=torch.from_numpy(np.asarray([arrays["magnitudes"][label_perm[i] if arm=="P" else i] for i,j,h in batch],dtype=np.float32))
                    optimizer.zero_grad();logpi,mu,sigma=net(wave,amplitude,ctx,mask,metadata_only=arm=="M",return_log=True)
                    loss=mixture_nll(labels,logpi,mu,sigma,log_input=True).reshape(8,3).mean(1).mean()
                    if not torch.isfinite(loss):raise RuntimeError("fit_nonfinite")
                    loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5)
                    if not torch.isfinite(norm):raise RuntimeError("fit_nonfinite")
                    optimizer.step();fit["history"].append(dict(update=step+1,nll=float(loss.detach()),seconds=time.monotonic()-fit_start))
                    if history is not None:history(seed,arm,fit["history"][-1])
                    _deadline(started,fit_start)
                _deadline(started,fit_start)
                checkpoint(seed,arm,{k:v.detach().cpu().numpy() for k,v in net.state_dict().items()},mean,std)
                net.eval()
                with torch.no_grad():
                    for i in dev:
                        for j,h in enumerate(HORIZONS):
                            _deadline(started,fit_start)
                            wave=torch.from_numpy(arrays["wave_%03d_%d"%(i,h)])[None,:,:]
                            mask=torch.ones((1,wave.shape[-1]),dtype=torch.bool)
                            pi,mu,sigma=net(wave,torch.from_numpy(arrays["amplitudes"][i,j])[None,:],torch.from_numpy(contexts[i,j].astype(np.float32))[None,:],mask,metadata_only=arm=="M")
                            p,m,s=([float(x) for x in v[0]] for v in (pi,mu,sigma));target=float(arrays["magnitudes"][i])
                            rate=Fraction(10**9)/Fraction(*manifest["rows"][i]["cells"][j]["period"])
                            fit["predictions"].append(dict(ordinal=i,horizon=h,rate=[rate.numerator,rate.denominator],target=target,pi=p,mu=m,sigma=s,mean=density.mean_action(p,m),median=density.quantile(.5,p,m,s),nll=density.nll(target,p,m,s),crps=density.crps(target,p,m,s)))
                fit["metrics"]={str(h):metrics([p for p in fit["predictions"] if p["horizon"]==h]) for h in HORIZONS}
                fit["rate_strata"]={str(h):rate_strata([p for p in fit["predictions"] if p["horizon"]==h],arrays["groups"]) for h in HORIZONS}
                _deadline(started,fit_start)
                fit["status"]="complete"
                del net,optimizer,wave,mask,amplitude,ctx,labels,logpi,mu,sigma,loss
            except Exception:
                fit["reason"]="fit_incomplete"
                return dict(status="incomplete",support=support,fits=fits,original_advance=False,bulk_guard=dict(pass_all=False,checks=[]),advance=False)
    comparisons=[]
    try:
        for seed in SEEDS:
            by={f["arm"]:f for f in fits if f["seed"]==seed}
            for other in ("M","P"):
                for h in HORIZONS:
                    _deadline(started)
                    left=[p for p in by["W"]["predictions"] if p["horizon"]==h];right=[p for p in by[other]["predictions"] if p["horizon"]==h]
                    strata=[]
                    for rate in sorted({tuple(p["rate"]) for p in left}):
                        _deadline(started)
                        a=[p for p in left if tuple(p["rate"])==rate];b=[p for p in right if tuple(p["rate"])==rate]
                        strata.append(dict(rate=list(rate),n=len(a),intervals=paired_intervals(a,b,arrays["groups"])))
                    comparisons.append(dict(seed=seed,horizon=h,pair="W-"+other,intervals=paired_intervals(left,right,arrays["groups"]),rate_strata=strata))
        _deadline(started)
    except Exception:
        return dict(status='incomplete',reason='comparison_incomplete',support=support,fits=fits,original_advance=False,bulk_guard=dict(pass_all=False,checks=[]),advance=False,comparisons=comparisons)
    return dict(status="complete",support=support,fits=fits,original_advance=original_advance(fits),bulk_guard=bulk_guard(fits),advance=advance(fits),comparisons=comparisons)

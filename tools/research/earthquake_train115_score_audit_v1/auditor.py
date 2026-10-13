"""Independent saved-prediction replay; no producer imports, training or input IO."""
from fractions import Fraction
import json
import math
import re
import numpy as np
from scipy.special import logsumexp, ndtr

SEEDS=(20261012,20261013)
ARMS=("W","M","P")
HORIZONS=(1,3,5)
STUDY="earthquake-fixed-TRAIN115-native-count-information-v1"
PROPOSAL_SHA="525b803e5c66da5284faad5e431eb152d04458f78d2ab5d783c27ba6a2dc6ed9"
MAX_OUTPUT=64*1024*1024
SQRT2PI=math.sqrt(2*math.pi)


def _keys(value,names):return type(value) is dict and set(value)==set(names) and all(type(k) is str for k in value)
def _int(value,lo,hi):return type(value) is int and lo<=value<=hi
def _number(value):return type(value) in (int,float) and math.isfinite(value)
def _canonical(value):return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode("ascii")


def _ratio(value,positive=False):
    if (type(value) is not list or len(value)!=2 or any(type(v) is not int for v in value)
            or value[1]<=0 or math.gcd(*value)!=1 or (positive and value[0]<=0)):raise ValueError("schema")
    return Fraction(*value)


def _close(stored,expected):
    """Discrete membership is exact; only numerical score fields admit tolerance."""
    if type(expected) is float:
        return _number(stored) and abs(stored-expected)<=1e-7+1e-6*abs(expected)
    if type(expected) is dict:
        return type(stored) is dict and set(stored)==set(expected) and all(_close(stored[k],v) for k,v in expected.items())
    if type(expected) is list:
        return type(stored) is list and len(stored)==len(expected) and all(_close(a,b) for a,b in zip(stored,expected))
    return type(stored) is type(expected) and stored==expected


def _manifest(manifest):
    if (not _keys(manifest,("schema","study","proposal_sha256","custody","native_namespaces","rows","denominators","observed_new_samples"))
            or manifest["schema"]!="earthquake-TRAIN115-native-count-artifact-v1" or manifest["study"]!=STUDY
            or manifest["proposal_sha256"]!=PROPOSAL_SHA
            or not _close(manifest["denominators"],dict(rows=115,cells=345,train=91,dev=24,test_excluded=31))
            or not _close(manifest["native_namespaces"],dict(original_rows=65,original_bodies=17,new_rows=50,new_bodies=13))
            or not _int(manifest["observed_new_samples"],0,104_000_000)
            or not _keys(manifest["custody"],("old_npz","old_manifest","new_plan","new_qualified","metadata"))
            or type(manifest["rows"]) is not list or len(manifest["rows"])!=115):raise ValueError("schema")
    for pin in manifest["custody"].values():
        if (not _keys(pin,("bytes","sha256")) or not _int(pin["bytes"],0,134_217_728)
                or type(pin["sha256"]) is not str or not re.fullmatch(r"[0-9a-f]{64}",pin["sha256"])):raise ValueError("custody_schema")
    rows=manifest["rows"];partitions=[];elements=0
    for i,row in enumerate(rows):
        if (not _keys(row,("ordinal","partition","group","mw","operational_eligible","cohort","source","original_group","original_cohort","cells"))
                or not _int(row["ordinal"],i,i) or type(row["partition"]) is not str or row["partition"] not in ("TRAIN","DEV")
                or type(row["source"]) is not str
                or not _int(row["group"],-1,i) or not _number(row["mw"]) or type(row["cohort"]) is not bool
                or type(row["operational_eligible"]) is not bool or type(row["cells"]) is not list or len(row["cells"])!=3):raise ValueError("schema")
        if i<65:
            if (row["source"]!="original65" or not _int(row["original_group"],0,64)
                    or type(row["original_cohort"]) is not bool):raise ValueError("provenance")
        elif (row["partition"]!="TRAIN" or row["source"]!="new50"
                or row["original_group"] is not None or row["original_cohort"] is not None):raise ValueError("provenance")
        if row["group"]<0 and row["operational_eligible"]:raise ValueError("unknown_group")
        partitions.append(row["partition"])
        for h,cell in zip(HORIZONS,row["cells"]):
            if (not _keys(cell,("horizon","status","reason","array","shape","first","period","precontext_count","channels","view_sha256"))
                    or not _int(cell["horizon"],h,h) or type(cell["channels"]) is not list
                    or any(type(c) is not str or not re.fullmatch(r"[A-Z0-9]{3}",c) for c in cell["channels"])):raise ValueError("schema")
            if cell["status"]=="available":
                if (cell["reason"]!="supported" or cell["array"]!="wave_%03d_%d"%(i,h) or type(cell["shape"]) is not list or len(cell["shape"])!=2
                        or not _int(cell["shape"][0],3,3) or not _int(cell["shape"][1],1,20_000_000//3)
                        or not _int(cell["precontext_count"],1,cell["shape"][1]) or len(cell["channels"])!=3 or len(set(cell["channels"]))!=3
                        or len({c[:2] for c in cell["channels"]})!=1 or "".join(c[2] for c in cell["channels"]) not in ("ENZ","12Z")
                        or type(cell["view_sha256"]) is not list or len(cell["view_sha256"])!=3
                        or any(type(v) is not str or not re.fullmatch(r"[0-9a-f]{64}",v) for v in cell["view_sha256"])):raise ValueError("schema")
                _ratio(cell["first"]);_ratio(cell["period"],True);elements+=math.prod(cell["shape"])
            elif (cell["status"]!="unavailable" or cell["reason"] not in ("selection_unknown","metadata_unknown","operational_ineligible","qualification_unknown","grid_mismatch","no_precontext","reconstruction_unknown","local_age")
                    or any(cell[k] is not None for k in ("array","shape","first","period","precontext_count","view_sha256"))):raise ValueError("schema")
        available=all(c["status"]=="available" for c in row["cells"])
        eligible=row["operational_eligible"] and row["group"]>=0
        if row["cohort"] and not (available and eligible):raise ValueError("cohort")
        if i<65:
            # Original tensors remain descriptive; local-age truth is external.
            if row["original_cohort"]!=available:raise ValueError("provenance")
        elif row["cohort"]!=(available and eligible):raise ValueError("cohort")
    if (partitions[:65].count("TRAIN")!=41 or partitions[:65].count("DEV")!=24
            or partitions.count("TRAIN")!=91 or partitions.count("DEV")!=24 or elements>20_000_000):raise ValueError("schema")
    mixed={g for g in {r["group"] for r in rows if r["group"]>=0}
           if len({r["partition"] for r in rows if r["group"]==g})>1}
    if any((r["cohort"] or r["operational_eligible"]) and r["group"] in mixed for r in rows):raise ValueError("binding")
    train=[r for r in rows if r["cohort"] and r["partition"]=="TRAIN"];dev=[r for r in rows if r["cohort"] and r["partition"]=="DEV"]
    counts=dict(train=len(train),dev=len(dev),train_high=sum(r["mw"]>=5.5 for r in train),dev_high=sum(r["mw"]>=5.5 for r in dev),
                train_lower=sum(r["mw"]<5.5 for r in train),dev_lower=sum(r["mw"]<5.5 for r in dev),dev_high_groups=len({r["group"] for r in dev if r["mw"]>=5.5}),
                old_train=sum(r["ordinal"]<65 for r in train),new_train=sum(r["ordinal"]>=65 for r in train),
                old_train_high=sum(r["ordinal"]<65 and r["mw"]>=5.5 for r in train),new_train_high=sum(r["ordinal"]>=65 and r["mw"]>=5.5 for r in train),
                old_train_lower=sum(r["ordinal"]<65 and r["mw"]<5.5 for r in train),new_train_lower=sum(r["ordinal"]>=65 and r["mw"]<5.5 for r in train),
                unknown_groups=sum(r["group"]<0 for r in rows))
    disjoint=not({r["group"] for r in train}&{r["group"] for r in dev})
    passed=disjoint and all(counts[k]>=n for k,n in dict(train=20,dev=12,train_high=8,dev_high=5,train_lower=5,dev_lower=5,dev_high_groups=3).items())
    panels={source:{str(h):sum(r["cells"][index]["status"]=="available" for r in rows if r["source"]==source)
                    for index,h in enumerate(HORIZONS)} for source in ("original65","new50")}
    support=dict(status="pass" if passed else "fail",counts=counts,train=[r["ordinal"] for r in train],dev=[r["ordinal"] for r in dev],
                 status_panels=panels,DEV_reused_exploratory=True)
    return rows,support


def score(target,pi,mu,sigma):
    if (not _number(target) or any(type(v) is not list or len(v)!=5 for v in (pi,mu,sigma))
            or any(not _number(v) for values in (pi,mu,sigma) for v in values)
            or any(v<0 for v in pi) or abs(sum(pi)-1)>1e-6 or any(v<.05 for v in sigma)):raise ValueError("density")
    p,m,s=(np.asarray(v,dtype=np.float64) for v in (pi,mu,sigma))
    with np.errstate(over="ignore",invalid="ignore",divide="ignore"):
        logdensity=np.where(p>0,np.log(p),-np.inf)-np.log(s)-math.log(SQRT2PI)-.5*((target-m)/s)**2
        nll=float(-logsumexp(logdensity))
        def absolute_moment(delta,sd):
            z=delta/sd
            return sd*math.sqrt(2/math.pi)*np.exp(-.5*z*z)+delta*(2*ndtr(z)-1)
        crps=float(np.dot(p,absolute_moment(target-m,s))-.5*np.sum(p[:,None]*p[None,:]*absolute_moment(m[:,None]-m[None,:],np.hypot(s[:,None],s[None,:]))))
        mean=float(np.dot(p,m))
        def quantile(q):
            lo,hi=(float(m.min()),float(m.max())) if q==.5 else (float(np.min(m-40*s)),float(np.max(m+40*s)))
            for _ in range(64):
                middle=lo/2+hi/2
                if float(np.dot(p,ndtr((middle-m)/s)))<q:lo=middle
                else:hi=middle
            return lo/2+hi/2
        median=quantile(.5)
        coverage={"coverage_%d"%round(c*100):float(quantile((1-c)/2)<=target<=quantile(1-(1-c)/2)) for c in (.5,.9,.95)}
    if any(not math.isfinite(v) for v in (nll,crps,mean,median)):raise ValueError("density")
    return dict(target=float(target),mean=mean,median=median,nll=nll,crps=crps,**coverage)


def _vectors(predictions):
    return {k:np.asarray([p[k] for p in predictions],dtype=np.float64) for k in ("target","mean","median","nll","crps","coverage_50","coverage_90","coverage_95")}


def _metrics(v):
    target=v["target"];signed=v["mean"]-target;absolute=np.abs(signed);high=target>=5.5;higher=target>=6;lower=target<5.5
    out=dict(n=len(target),nll=float(np.mean(v["nll"])),crps=float(np.mean(v["crps"])),mae=float(np.mean(absolute)),medae=float(np.median(absolute)),
             tail_mae_5_5=float(np.mean(absolute[high])) if high.any() else None,tail_mae_6=float(np.mean(absolute[higher])) if higher.any() else None,
             tail_bias=float(np.mean(signed[high])) if high.any() else None,lower_mae=float(np.mean(absolute[lower])) if lower.any() else None,
             lower_medae=float(np.median(absolute[lower])) if lower.any() else None,cvar95=float(np.mean(np.sort(absolute)[-math.ceil(.05*len(target)):])),
             p95=float(np.quantile(absolute,.95,method="linear")),maximum=float(np.max(absolute)),median_mae=float(np.mean(np.abs(v["median"]-target))))
    out.update({k:float(np.mean(v[k])) for k in ("coverage_50","coverage_90","coverage_95")})
    return out


def paired(left,right,groups):
    if [(p["ordinal"],p["target"]) for p in left]!=[(p["ordinal"],p["target"]) for p in right]:raise ValueError("binding")
    a,b=_vectors(left),_vectors(right);pa,pb=_metrics(a),_metrics(b)
    gid=np.asarray([groups[p["ordinal"]] for p in left]);unique=np.unique(gid);target=a["target"]
    support={}
    for name in pa:
        if name=="n":continue
        mask=target>=5.5 if name in ("tail_mae_5_5","tail_bias") else target>=6 if name=="tail_mae_6" else target<5.5 if name in ("lower_mae","lower_medae") else np.ones(len(target),dtype=bool)
        support[name]=len(np.unique(gid[mask]))
    draws={name:[] for name,n in support.items() if n>=3}
    if draws:
        rng=np.random.default_rng(9919)
        for _ in range(1000):
            indices=np.concatenate([np.flatnonzero(gid==g) for g in rng.choice(unique,len(unique),replace=True)])
            ma,mb=_metrics({k:v[indices] for k,v in a.items()}),_metrics({k:v[indices] for k,v in b.items()})
            for name in draws:
                if ma[name] is not None and mb[name] is not None:draws[name].append(ma[name]-mb[name])
    result={}
    for name,n in support.items():
        delta=pa[name]-pb[name] if pa[name] is not None and pb[name] is not None else None
        if n<3 or len(draws[name])!=1000:result[name]=dict(status="unsupported",groups=n,mean=delta)
        else:result[name]=dict(status="descriptive",groups=n,mean=delta,interval=[float(v) for v in np.quantile(draws[name],[.025,.975])])
    return result


def rate_strata(predictions,groups):
    out=[]
    for rate in sorted({tuple(p["rate"]) for p in predictions}):
        selected=[p for p in predictions if tuple(p["rate"])==rate];ng=len({groups[p["ordinal"]] for p in selected})
        out.append(dict(rate=list(rate),n=len(selected),groups=ng,status="descriptive" if ng>=3 else "unsupported",metrics=_metrics(_vectors(selected))))
    return out


def original_advance(fits):
    if len(fits)!=6 or any(f.get("status")!="complete" for f in fits):return False
    for seed in SEEDS:
        by={f["arm"]:f for f in fits if f["seed"]==seed}
        if set(by)!=set(ARMS):return False
        for h in HORIZONS:
            w,m,p=(by[a]["metrics"][str(h)] for a in ARMS)
            if not (w["nll"]<m["nll"] and w["crps"]<m["crps"] and w["nll"]<p["nll"] and w["crps"]<p["crps"]
                    and w["tail_mae_5_5"] is not None and m["tail_mae_5_5"] is not None and m["tail_mae_5_5"]-w["tail_mae_5_5"]>=.02
                    and all(w[k] is not None and m[k] is not None and w[k]<=m[k] for k in ("lower_mae","lower_medae","cvar95","maximum"))):return False
    return True


def bulk_guard(fits):
    checks=[]
    for seed in SEEDS:
        by={f["arm"]:f for f in fits if f["seed"]==seed}
        for h in HORIZONS:
            w,m=(by[a]["metrics"][str(h)] for a in ("W","M"))
            checks.append(dict(seed=seed,horizon=h,mae_not_worse=w["mae"]<=m["mae"],medae_not_worse=w["medae"]<=m["medae"]))
    return dict(pass_all=all(c["mae_not_worse"] and c["medae_not_worse"] for c in checks),checks=checks)


def _guard_shape(value):
    if (not _keys(value,("pass_all","checks")) or type(value["pass_all"]) is not bool
            or type(value["checks"]) is not list or len(value["checks"])!=6):return False
    for entry,(seed,h) in zip(value["checks"],((seed,h)for seed in SEEDS for h in HORIZONS)):
        if (not _keys(entry,("seed","horizon","mae_not_worse","medae_not_worse"))
                or not _int(entry["seed"],seed,seed) or not _int(entry["horizon"],h,h)
                or any(type(entry[k]) is not bool for k in ("mae_not_worse","medae_not_worse"))):return False
    return True


def _history(value):
    if type(value) is not list or len(value)!=300:raise ValueError("history")
    previous=0.
    for update,entry in enumerate(value,1):
        if (not _keys(entry,("update","nll","seconds")) or not _int(entry["update"],update,update) or not _number(entry["nll"])
                or not _number(entry["seconds"]) or not previous<=entry["seconds"]<=300):raise ValueError("history")
        previous=entry["seconds"]


def audit(result,manifest,histories=None):
    """No IO/fits; actual custody/runtime limits remain independent parent gates."""
    errors=[];recomputed=[];comparisons=[]
    try:
        rows,support=_manifest(manifest)
        if (not _keys(result,("status","support","fits","original_advance","bulk_guard","advance","comparisons")) or result["status"]!="complete" or support["status"]!="pass"
                or not _close(result["support"],support) or type(result["fits"]) is not list or len(result["fits"])!=6 or type(result["advance"]) is not bool or type(result["original_advance"]) is not bool
                or not _guard_shape(result["bulk_guard"])):raise ValueError("binding")
        expected_pairs=[(seed,arm) for seed in SEEDS for arm in ARMS]
        if histories is not None and (type(histories) is not dict or set(histories)!=set(expected_pairs)
                or any(type(k) is not tuple or len(k)!=2 or type(k[0]) is not int or type(k[1]) is not str for k in histories)):raise ValueError("history")
        groups=[r["group"] for r in rows];expected_predictions=[(i,h) for i in support["dev"] for h in HORIZONS]
        for fit,pair in zip(result["fits"],expected_pairs):
            if (not _keys(fit,("seed","arm","status","history","predictions","metrics","rate_strata")) or not _int(fit["seed"],pair[0],pair[0])
                    or type(fit["arm"]) is not str or fit["arm"]!=pair[1] or fit["status"]!="complete" or type(fit["predictions"]) is not list or len(fit["predictions"])!=len(expected_predictions)):raise ValueError("binding")
            _history(fit["history"])
            if histories is not None and _canonical(histories[pair])!=_canonical(fit["history"]):raise ValueError("history")
            predictions=[]
            for stored,(i,h) in zip(fit["predictions"],expected_predictions):
                rate=Fraction(10**9)/_ratio(rows[i]["cells"][HORIZONS.index(h)]["period"],True);rate_pair=[rate.numerator,rate.denominator]
                if (not _keys(stored,("ordinal","horizon","rate","target","pi","mu","sigma","mean","median","nll","crps"))
                        or not _int(stored["ordinal"],i,i) or not _int(stored["horizon"],h,h) or not _number(stored["target"]) or stored["target"]!=rows[i]["mw"]
                        or _ratio(stored["rate"],True)!=rate):raise ValueError("binding")
                values=score(stored["target"],stored["pi"],stored["mu"],stored["sigma"])
                if any(not _close(stored[k],values[k]) for k in ("mean","median","nll","crps")):errors.append("stored_prediction")
                predictions.append(dict(ordinal=i,horizon=h,rate=rate_pair,**values))
            metrics={str(h):_metrics(_vectors([p for p in predictions if p["horizon"]==h])) for h in HORIZONS}
            strata={str(h):rate_strata([p for p in predictions if p["horizon"]==h],groups) for h in HORIZONS}
            if not _close(fit["metrics"],metrics):errors.append("stored_metrics")
            if not _close(fit["rate_strata"],strata):errors.append("stored_rate_strata")
            recomputed.append(dict(seed=pair[0],arm=pair[1],status="complete",predictions=predictions,metrics=metrics,rate_strata=strata))
        for seed in SEEDS:
            by={f["arm"]:f for f in recomputed if f["seed"]==seed}
            for other in ("M","P"):
                for h in HORIZONS:
                    a=[p for p in by["W"]["predictions"] if p["horizon"]==h];b=[p for p in by[other]["predictions"] if p["horizon"]==h]
                    strata=[]
                    for rate in sorted({tuple(p["rate"]) for p in a}):
                        x=[p for p in a if tuple(p["rate"])==rate];y=[p for p in b if tuple(p["rate"])==rate]
                        strata.append(dict(rate=list(rate),n=len(x),intervals=paired(x,y,groups)))
                    comparisons.append(dict(seed=seed,horizon=h,pair="W-"+other,intervals=paired(a,b,groups),rate_strata=strata))
        if not _close(result["comparisons"],comparisons):errors.append("stored_comparisons")
        original=original_advance(recomputed);guard=bulk_guard(recomputed);passed=original and guard["pass_all"]
        if result["original_advance"]!=original:errors.append("stored_original_advance")
        if not _close(result["bulk_guard"],guard):errors.append("stored_bulk_guard")
        if result["advance"]!=passed:errors.append("stored_advance")
        report=dict(schema="earthquake-TRAIN115-score-audit-v1",status="fail" if errors else "pass",reasons=sorted(set(errors)),support=support,fits=recomputed,comparisons=comparisons,original_advance=original,bulk_guard=guard,advance=passed)
        if len(_canonical(report))>MAX_OUTPUT:raise ValueError("output_cap")
        return report
    except (ValueError,TypeError,KeyError,IndexError,OverflowError):
        return dict(schema="earthquake-TRAIN115-score-audit-v1",status="fail",reasons=["input_or_computation_invalid"],fits=[],comparisons=[],original_advance=False,bulk_guard=dict(pass_all=False,checks=[]),advance=False)

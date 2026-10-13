"""Invented constant-normal complete fixture; no provider/model inputs."""
import copy
import math
import numpy as np
from scipy.stats import norm
from metrics import SEEDS,ARMS,HORIZONS


def reference_metric(predictions):
    n=len(predictions);high=any(p['target']>=5.5 for p in predictions);higher=any(p['target']>=6 for p in predictions);lower=any(p['target']<5.5 for p in predictions)
    out=dict(n=n,nll=predictions[0]['nll'],crps=predictions[0]['crps'],mae=1.,medae=1.,tail_mae_5_5=1. if high else None,tail_mae_6=1. if higher else None,
             lower_mae=1. if lower else None,lower_medae=1. if lower else None,tail_bias=-1. if high else None,cvar95=1.,maximum=1.,p95=1.,median_mae=1.,coverage_50=0.,coverage_80=0.,coverage_95=1.)
    return out


def fixture():
    rows=[];common=set(range(41))|set(range(41,63))|set(range(65,89))
    for i in range(115):
        partition='TRAIN'if i<41 or i>=65 else'DEV';base=dict(ordinal=i,partition=partition,mw=6. if i%2==0 else 4.,group=i,common=i in common)
        if i not in common:
            rows.append(dict(**base,status='unavailable',initial=None,horizons=[dict(seconds=h,status='unavailable')for h in HORIZONS]));continue
        c=np.zeros(35,dtype=np.float64);c[3:7]=1;c[8]=2;c[15]=1
        initial=dict(wave=np.zeros((3,25),dtype=np.float32),amplitude=np.zeros(4,dtype=np.float32),context=c)
        horizons=[]
        for h in HORIZONS:
            states=([1]*3+[0]*(4*h-3))if i<5 else[1]*(4*h);run=[]
            for j,b in enumerate(states):run.append(run[-1]+1 if j and b==states[j-1]else 1)
            context=np.r_[c[:7],float(h),c[7:]].astype(np.float64)
            horizons.append(dict(seconds=h,rate=[100,1],wave=np.zeros((3,100*(h+3)),dtype=np.float32),amplitude=np.zeros(4,dtype=np.float32),context=context,
                                 ratios=[10. if b else 0. for b in states],states=states,run_ages=run))
        rows.append(dict(**base,status='available',initial=initial,horizons=horizons))
    packet=dict(schema='earthquake-TRAIN115-receiver-observations-v2',study='earthquake-TRAIN115-receiver-renewal-v2',rows=rows,
                denominators=dict(events=115,cells=345,train=91,dev=24,test_excluded=31),observed_samples=dict(old=1000,new=1000),
                input_pins={k:dict(bytes=1,sha256='0'*64)for k in('old_plan','old_qualified','new_plan','new_qualified','metadata','roster')},fit_authorized=False)
    train=[r for r in rows if r['common']and r['partition']=='TRAIN'];dev=[r for r in rows if r['common']and r['partition']=='DEV']
    mref=float(np.mean([r['mw']for r in train]));std=float(np.std([r['mw']for r in train]));sigma=.05+math.log(2);z=1/sigma
    nll=math.log(sigma)+.5*math.log(2*math.pi)+.5*z*z
    crps=float(sigma*(z*(2*norm.cdf(z)-1)+2*norm.pdf(z)-1/math.sqrt(math.pi)))
    hazard=dict(alpha=[0.]*2,beta=[0.]*2,z_weights=[[0.]*36 for _ in range(2)],c_weights=[[0.]*35 for _ in range(2)],gamma=[0.]*2,extra=[0.]*2)
    context=[0.]*35;context[3:7]=[1.]*4;context[15]=1.
    raw=[0.]*5+[5.]*5+[0.]*5;quantiles={str(q):float(5+sigma*norm.ppf(q))for q in(.025,.1,.25,.5,.75,.9,.975)}
    fits=[]
    for seed in SEEDS:
        for arm in ARMS:
            predictions=[]
            for row in dev:
                for h in HORIZONS:
                    target=row['mw'];score=dict(mean=5.,median=5.,nll=nll,crps=crps,pit=float(norm.cdf((target-5)/sigma)),coverage_50=False,coverage_80=False,coverage_95=True)
                    if arm in('B','F'):numeric=dict(pi=[.2]*5,mu=[5.]*5,sigma=[sigma]*5)
                    else:
                        logz=-(4*h-1)*math.log(2)
                        numeric=dict(accepted=True,errors=dict(log_normalizer=0.,mean=0.,nll=0.),torch_errors={'64':0.,'128':0.},base_raw=raw,z=[0.]*36,c=context,states=[1]*(4*h),hazard=hazard,mref=mref,
                                     integrals={key:dict(method=method,log_normalizer=logz,mean=5.,nll=nll)for key,method in(('gh64','GH64'),('gh128','GH128'),('adaptive','adaptive'))})
                        score['quantiles']=quantiles
                    predictions.append(dict(ordinal=row['ordinal'],horizon=h,target=target,group=row['group'],family='ENZ',receiver=[0.,0.,0.],rate=[100,1],numerical=copy.deepcopy(numeric),**copy.deepcopy(score)))
            panel={str(h):reference_metric([p for p in predictions if p['horizon']==h])for h in HORIZONS};strata={}
            for h in HORIZONS:
                ps=[p for p in predictions if p['horizon']==h]
                strata[str(h)]=dict(families=[dict(family='ENZ',metrics=reference_metric(ps))],receivers=[dict(receiver=[0.,0.,0.],metrics=reference_metric(ps))],rates=[dict(rate=[100,1],metrics=reference_metric(ps))],groups=[dict(group=p['group'],metrics=reference_metric([p]))for p in ps])
            entries=[dict(update=u,base_nll=1.,sequence_nll=0. if arm in('B','F')else 2.,joint_or_conditional_nll=1. if arm in('B','F')else 3.,gradient_norm=1.,base_gradient_norm=1.,sequence_gradient_norm=0. if arm in('B','F')else 1.,seconds=u/100)for u in range(1,301)]
            fits.append(dict(seed=seed,arm=arm,mref=mref,train_population_std=std,status='complete',history=entries,predictions=predictions,numerical_failures=[],metrics=panel,strata=strata,extreme_cases=[]))
    checks=[];comparisons=[]
    metric=reference_metric(fits[0]['predictions'])
    for seed in SEEDS:
        for h in HORIZONS:
            for comparator in ARMS[:-1]:
                proper=comparator in('H','T')
                checks.append(dict(seed=seed,horizon=h,comparator=comparator,tail=False,proper=proper,bulk_worst={k:True for k in('mae','medae','lower_mae','lower_medae','cvar95','maximum')},passed=False))
                intervals={k:dict(status='descriptive',groups=11 if k in('tail_mae_5_5','tail_mae_6','tail_bias','lower_mae','lower_medae')else 22,delta=0.,interval=[0.,0.])for k in metric if k!='n'}
                comparisons.append(dict(seed=seed,horizon=h,comparator=comparator,intervals=intervals))
    diagnostics=dict(denominators=packet['denominators'],unavailable_events=28,old_events=65,new_events=50)
    diagnostics['TRAIN']=dict(common=65,noise_floor_counts=[65]*3,horizons={str(h):dict(off=5,on=0,active_censored=60)for h in HORIZONS})
    diagnostics['DEV']=dict(common=22,noise_floor_counts=[22]*3,horizons={str(h):dict(off=0,on=0,active_censored=22)for h in HORIZONS})
    counts=dict(B=5007,F=5147,H=5125,T=5125,C=5125)
    result=dict(status='complete',fits=fits,capacity=dict(counts=counts,nonzero_TRAIN_probe_gradient_degrees=dict(counts)),advance=dict(pass_all=False,checks=checks),comparisons=comparisons,diagnostics=diagnostics,fit_authorized=False)
    return result,packet

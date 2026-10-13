"""Independently derived mean-action errors, group bootstrap and fixed36 guards."""
import math
import numpy as np
from math_core import need

H=(1,3,5)
def panel(p):
 y=np.asarray([v['target']for v in p],dtype=np.float64);mean=np.asarray([v['mean']for v in p]);err=mean-y;a=np.abs(err);hi=y>=5.5;higher=y>=6;lo=y<5.5
 def sub(mask,median=False):return float((np.median if median else np.mean)(a[mask]))if mask.any()else None
 result=dict(n=len(y),nll=float(np.mean([v['nll']for v in p])),crps=float(np.mean([v['crps']for v in p])),mae=float(a.mean()),medae=float(np.median(a)),tail_mae_5_5=sub(hi),tail_mae_6=sub(higher),lower_mae=sub(lo),lower_medae=sub(lo,True),tail_bias=float(err[hi].mean())if hi.any()else None,cvar95=float(np.sort(a)[-max(1,math.ceil(.05*len(a))):].mean()),maximum=float(a.max()),p95=float(np.quantile(a,.95,method='linear')),median_mae=float(np.mean([abs(v['median']-v['target'])for v in p])))
 for level in(50,80,95):result['coverage_'+str(level)]=float(np.mean([v['coverage_'+str(level)]for v in p]))
 return result

def paired(a,b,tick=lambda:None,evidence=None):
 need([(v['ordinal'],v['target'],v['group'])for v in a]==[(v['ordinal'],v['target'],v['group'])for v in b],'paired_roles');pa,pb=panel(a),panel(b);groups=sorted({v['group']for v in a});support={};draws={};need(evidence is None or type(evidence)is dict,'bootstrap_evidence');evidence={}if evidence is None else evidence;evidence.update(support=support,draws=draws,completed=0)
 for key in pa:
  if key=='n':continue
  members={v['group']for v in a if(v['target']>=5.5 if key in('tail_mae_5_5','tail_bias')else v['target']>=6 if key=='tail_mae_6'else v['target']<5.5 if key in('lower_mae','lower_medae')else True)};support[key]=len(members)
  if len(members)>=3:draws[key]=[]
 evidence.update(primary_a=pa,primary_b=pb);rng=np.random.default_rng(9919)
 for _ in range(1000):
  tick();ids=[i for g in rng.choice(groups,len(groups),replace=True)for i,v in enumerate(a)if v['group']==g];x,y=panel([a[i]for i in ids]),panel([b[i]for i in ids])
  for key in draws:
   if x[key]is not None and y[key]is not None:draws[key].append(x[key]-y[key])
  evidence['completed']+=1
 return {key:dict(status='descriptive'if support[key]>=3 and len(draws.get(key,[]))==1000 else'unsupported',groups=support[key],delta=pa[key]-pb[key]if pa[key]is not None and pb[key]is not None else None,interval=[float(v)for v in np.quantile(draws[key],[.025,.975])]if support[key]>=3 and len(draws.get(key,[]))==1000 else None)for key in support}

def strata(p):
 result={}
 for h in H:
  rows=[v for v in p if v['horizon']==h];out={}
  for name,key in(('families','family'),('receivers','receiver'),('groups','group'),('rates','rate')):
   values=sorted({tuple(v[key])if type(v[key])is list else v[key]for v in rows});out[name]=[{key:list(x)if type(x)is tuple else x,'metrics':panel([v for v in rows if(tuple(v[key])if type(v[key])is list else v[key])==x])}for x in values]
  result[str(h)]=out
 return result

def guards(fits,stronger):
 checks=[];extra=[]
 for seed in(20261012,20261013):
  current={v['arm']:v for v in fits if v['seed']==seed};old={v['arm']:v for v in stronger if v['seed']==seed};need(set(current)=={'S','P','D'}and set(old)=={'B','F','H','T'},'all_comparators')
  for h in H:
   s=current['S']['metrics'][str(h)]
   for arm in('B','F','H','T','P','D'):
    b=(current if arm in('P','D')else old)[arm]['metrics'][str(h)];tail=s['tail_mae_5_5']is not None and b['tail_mae_5_5']is not None and b['tail_mae_5_5']-s['tail_mae_5_5']>=.02;proper=s['nll']<b['nll']and s['crps']<b['crps']if arm in('B','F','P','D')else True;bulk={k:s[k]is not None and b[k]is not None and s[k]<=b[k]for k in('mae','medae','lower_mae','lower_medae','cvar95','maximum')};item=dict(seed=seed,horizon=h,comparator=arm,tail=tail,proper=proper,bulk_worst=bulk,passed=tail and proper and all(bulk.values()));(extra if arm in('P','D')else checks).append(item)
 return dict(pass_all=all(v['passed']for v in checks+extra),checks=checks,additional=extra)

"""Invented scalar fake auditor and fixed score fixtures; no external imports/data."""
import copy
import json
import math
from types import SimpleNamespace
import numpy as np
import reference_metrics as m

class Fake:
 def __init__(self,dev):self.dev=dev;self.calls=[]
 def canonical(self,v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 def close(self,a,b,tolerance=1e-4):
  if type(b)is float:return type(a)in(int,float)and math.isfinite(a)and abs(a-b)<=tolerance+1e-6*abs(b)
  if type(b)is dict:return type(a)is dict and set(a)==set(b)and all(self.close(a[k],v,tolerance)for k,v in b.items())
  if type(b)is list:return type(a)is list and len(a)==len(b)and all(self.close(x,y,tolerance)for x,y in zip(a,b))
  return type(a)is type(b)and a==b
 def keys(self,v,names):
  if type(v)is not dict or set(v)!=set(names):raise ValueError('keys')
 def finite(self,v):return type(v)in(int,float)and math.isfinite(v)
 def integer(self,v,lo,hi):
  if type(v)is not int or not lo<=v<=hi:raise ValueError('integer')
 def validate(self,p):return {'TRAIN':list(range(65)),'DEV':self.dev}
 def scaler(self,p,r):return stats()
 def capacity(self,c):pass
 def history(self,h,a):
  if type(h)is not list or len(h)!=300:raise ValueError('history')
 def model_context(self,*a):return [0.]*35
 def diagnostics(self,*a):return {'invented':True}
 def numerical_record(self,record,arm,row,obs,st,target,mean,cache):
  self.calls.append((arm,target));value=score(target,arm);return value,None if arm in('B','F')else record
 metrics=staticmethod(m.metrics);strata=staticmethod(m.strata);paired=staticmethod(m.paired);advance=staticmethod(m.advance)

def stats():return {k:np.ones(35 if k.startswith('initial')else 36,dtype=np.float64)for k in('initial_mean','initial_std','current_mean','current_std')}
def score(target,arm):
 v=dict(mean=4.,median=4.,nll=1.,crps=.1,pit=.5,coverage_50=True,coverage_80=True,coverage_95=True)
 if arm in('C','H','T'):v['quantiles']={str(x):4. for x in(.025,.1,.25,.5,.75,.9,.975)}
 return v

def complete(result,g):
 result=copy.deepcopy(result);rows=[dict(ordinal=i,mw=4. if i<102 else 6.,group=i if i<91 else 91,initial={'context':np.zeros(35),'amplitude':np.zeros(4,dtype=np.float32)},horizons=[{'rate':[100,1],'states':[1,1]}for _ in(1,3,5)])for i in range(115)];packet={'rows':rows};ad=Fake(g['dev_ordinals']);st={pair:stats()for pair in[(s,a)for s in(20261012,20261013)for a in('B','F','H','T','C')]};histories={}
 for fit in result['fits']:
  fit['train_population_std']=0.;histories[(fit['seed'],fit['arm'])]=fit['history']
  for item in fit['predictions']:
   row=rows[item['ordinal']];item.update(target=row['mw'],group=row['group'],receiver=[0.,0.,0.],family='12Z',rate=[100,1],**score(row['mw'],fit['arm']))
  fit['metrics']={str(h):m.metrics([p for p in fit['predictions']if p['horizon']==h])for h in(1,3,5)};fit['strata']=m.strata(fit['predictions']);fit['extreme_cases']=[]
 fits=[{k:fit[k]for k in('seed','arm','status','predictions','metrics','strata','extreme_cases')}for fit in result['fits']];result['advance']=m.advance(fits);result['comparisons']=[]
 for seed in(20261012,20261013):
  by={f['arm']:f for f in fits if f['seed']==seed}
  for h in(1,3,5):
   for arm in('B','F','H','T'):result['comparisons'].append(dict(seed=seed,horizon=h,comparator=arm,intervals=m.paired([p for p in by['C']['predictions']if p['horizon']==h],[p for p in by[arm]['predictions']if p['horizon']==h])))
 return result,packet,st,histories,ad

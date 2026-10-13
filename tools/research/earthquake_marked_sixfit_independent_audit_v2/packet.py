"""Independent marked packet semantics and TRAIN-only statistical schema."""
import math
import statistics
import numpy as np
from math_core import array,need,summaries

KEEP=[i for i in range(34)if i not in(15,25,29,33)]
NAMES=[f'c{c}_{s}'for c in range(3)for s in('latest','mean','max','time_slope','censor_fraction')]+['log_duration','cells','nu_sd_0','nu_sd_1','nu_sd_2']

def keys(v,names):need(type(v)is dict and set(v)==set(names),'keys')
def integer(v,lo,hi):need(type(v)is int and lo<=v<=hi,'integer')
def byteeq(a,b):return type(a)is np.ndarray and type(b)is np.ndarray and a.dtype==b.dtype and a.shape==b.shape and a.tobytes()==b.tobytes()

def validate(p):
 keys(p,('schema','study','rows','denominators','input_pins','observed_samples','fit_authorized'));need(p['schema']=='earthquake-TRAIN115-marked-noise-observations-v1'and p['study']=='earthquake-TRAIN115-marked-noise-study-v1'and p['fit_authorized']is False,'packet_identity');need(p['denominators']==dict(events=115,horizon_cells=345,train=91,dev=24,common_train=65,common_dev=22,test_excluded=31),'denominators');keys(p['input_pins'],('old_plan','old_qualified','new_plan','new_qualified','metadata','roster','activity_anchor'));keys(p['observed_samples'],('old','new'))
 for name,pin in p['input_pins'].items():
  keys(pin,('bytes','sha256'));need(type(pin['bytes'])is int and pin['bytes']>0 and type(pin['sha256'])is str and len(pin['sha256'])==64 and all(c in'0123456789abcdef'for c in pin['sha256']),'native_input_pin')
 integer(p['observed_samples']['old'],0,136_000_000);integer(p['observed_samples']['new'],0,104_000_000);need(sum(p['observed_samples'].values())<=240_000_000,'native_sample_cap');need(type(p['rows'])is list and len(p['rows'])==115,'rows');roles={'TRAIN':[],'DEV':[]};part={'TRAIN':0,'DEV':0};groups={'TRAIN':set(),'DEV':set()}
 for i,row in enumerate(p['rows']):
  keys(row,('ordinal','partition','mw','group','common','status','precontext','noise','horizons'));integer(row['ordinal'],i,i);need(row['partition']in roles and type(row['common'])is bool and type(row['mw'])in(int,float)and math.isfinite(row['mw'])and -5<=row['mw']<=15,'row');part[row['partition']]+=1;integer(row['group'],-1,2**63-1);need(type(row['horizons'])is list and len(row['horizons'])==3,'horizons')
  if not row['common']:need(row['status']=='unavailable'and row['precontext']is None and row['noise']is None and row['horizons']==[dict(seconds=h,status='unavailable')for h in(1,3,5)],'unavailable');continue
  need(row['status']=='available'and row['group']>=0,'common');roles[row['partition']].append(i);groups[row['partition']].add(row['group']);ctx=array(row['precontext'],(34,));n=row['noise'];keys(n,('centers','powers','nhat','floors','nu','weights','rate','arrival_offset_ns'));array(n['centers'],(3,));powers=array(n['powers'],(3,12));nhat=array(n['nhat'],(3,));nu=array(n['nu'],(12,3));weights=array(n['weights'],(12,));need((powers>=0).all()and(powers<=1e24).all()and byteeq(weights,np.full(12,1/12,dtype=np.float64)),'noise');need(type(n['floors'])is np.ndarray and n['floors'].dtype==np.uint8 and n['floors'].shape==(3,),'floor_flags');integer(n['arrival_offset_ns'],0,750_000_000);rate=n['rate'];need(type(rate)is list and len(rate)==2 and all(type(v)is int and v>0 for v in rate)and math.gcd(*rate)==1,'rate')
  expectednu=np.empty((12,3));expectedn=[];floor=[]
  for c in range(3):
   med=statistics.median(float(x)for x in powers[c]);expectedn.append(max(1.,med));floor.append(int(med<1.));eta=[math.log(max(1.,statistics.median(float(v)for j,v in enumerate(powers[c])if j!=ell)))for ell in range(12)];mean=math.fsum(eta)/12
   for ell,v in enumerate(eta):expectednu[ell,c]=v-mean
  need(byteeq(nhat,np.asarray(expectedn,dtype=np.float64))and byteeq(n['floors'],np.asarray(floor,dtype=np.uint8))and byteeq(nu,expectednu),'noise_reduction');need(bool(np.all(np.abs(ctx[:3]-np.asarray([math.log10(float(v))for v in nhat]))<=1e-12))and np.array_equal(ctx[3:6],n['floors'])and abs(float(ctx[7])-math.log10(rate[0]/rate[1]))<=1e-12,'precontext_noise_rate');need(ctx[6]==n['arrival_offset_ns']/1e9 and all(v in(0.,1.)for v in ctx[[11,12,13,14,15,19,20,21]])and ctx[14]+ctx[15]==1. and all(all(v in(0.,1.)for v in ctx[a:a+4])and float(ctx[a:a+4].sum())==1. for a in(22,26,30)),'static_flags_clock');prior=None
  for h,item in zip((1,3,5),row['horizons']):
   keys(item,('seconds','status','ratios','reported','censor','max_ratios','states','run_ages'));integer(item['seconds'],h,h);need(item['status']=='available','horizon_status');J=(h*1_000_000_000-n['arrival_offset_ns'])//250_000_000;R=array(item['ratios'],(J,3));y=array(item['reported'],(J,3));need((R>math.exp(-12)).all()and(R<=1e25).all()and(y>-12).all(),'allpositive');logged=np.asarray([[math.log(float(v))for v in line]for line in R],dtype=np.float64);need(byteeq(y,logged),'reported_log');need(type(item['censor'])is np.ndarray and item['censor'].dtype==np.uint8 and item['censor'].shape==(J,3)and not item['censor'].any(),'censor');maximum=array(item['max_ratios'],(J,));need(byteeq(maximum,np.max(R,axis=1)),'maximum');b=np.asarray(maximum>9,dtype=np.uint8);ages=[];count=0;last=None
   for v in b:count=count+1 if int(v)==last else 1;ages.append(count);last=int(v)
   need(byteeq(item['states'],b)and byteeq(item['run_ages'],np.asarray(ages,dtype=np.uint8)),'activity')
   if prior is not None:
    need(J-len(prior['reported'])==8 and all(byteeq(item[k][:len(prior[k])],prior[k])for k in('ratios','reported','censor','max_ratios','states','run_ages')),'prefix')
   prior=item
 need(part=={'TRAIN':91,'DEV':24}and len(roles['TRAIN'])==65 and len(roles['DEV'])==22 and not(groups['TRAIN']&groups['DEV']),'roles');return roles

def schema(p,roles):
 X=np.asarray([p['rows'][i]['precontext'][KEEP]for i in roles['TRAIN']],dtype=np.float64);mean=X.mean(0);constant=np.all(X==X[0],axis=0);std=X.std(0,ddof=0);std[constant]=0.;Z=np.divide(X-mean,std,out=np.zeros_like(X),where=std>0);basis=[];kept=[];norms=[]
 for k in range(30):
  v=Z[:,k].copy();original=float(np.linalg.norm(v))
  for _ in range(2):
   for b in basis:v-=b*float(np.dot(b,v))
  residual=float(np.linalg.norm(v));norms.append(residual)
  if original>0 and residual>1e-12*original:basis.append(v/residual);kept.append(k)
 coef=np.linalg.lstsq(Z[:,kept],Z,rcond=None)[0]if kept else np.empty((0,30));err=float(np.max(np.abs(Z[:,kept]@coef-Z)))if kept else float(np.max(np.abs(Z)));need(err<=1e-10,'static_reconstruction');S=np.asarray([summaries(p['rows'][i]['horizons'][h]['reported'],p['rows'][i]['noise']['nu'])for i in roles['TRAIN']for h in range(3)]);sm=S.mean(0);constantS=np.all(S==S[0],axis=0);ss=S.std(0,ddof=0);ss[constantS]=0.;active=[i for i in range(20)if i not in(4,9,14)and not constantS[i]];labels=np.asarray([p['rows'][i]['mw']for i in roles['TRAIN']],dtype=np.float64)
 return dict(static=dict(reference_keep=KEEP,mean=mean,std=std,constant=np.asarray(constant,dtype=np.uint8),kept=kept,residual_norms=np.asarray(norms),reconstruction=coef,reconstruction_max_abs=err),summary=dict(names=NAMES,mean=sm,std=ss,active=active),mref=float(labels.mean()),train_std=float(labels.std(ddof=0)),train=roles['TRAIN'],dev=roles['DEV'])

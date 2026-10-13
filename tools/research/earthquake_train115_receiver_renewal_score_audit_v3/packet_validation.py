"""Independent public packet/role/activity/scaler arithmetic; no input IO."""
import math
from fractions import Fraction
import re
import numpy as np
from numerical import ages, finite, NumericalFailure

HORIZONS=(1,3,5)
DENOMINATORS=dict(events=115,cells=345,train=91,dev=24,test_excluded=31)
CONTINUOUS=(0,1,2,7,8,9,10,11,17,18,19)


def keys(v,names):
    if type(v)is not dict or set(v)!=set(names)or any(type(k)is not str for k in v):raise NumericalFailure('keys')


def integer(v,lo,hi):
    if type(v)is not int or not lo<=v<=hi:raise NumericalFailure('integer')
    return v


def ratio(v):
    if type(v)is not list or len(v)!=2:raise NumericalFailure('rate')
    n=integer(v[0],1,10**1024-1);d=integer(v[1],1,10**1024-1)
    if math.gcd(n,d)!=1:raise NumericalFailure('rate')
    return Fraction(n,d)


def array(v,shape,dtype):
    if type(v)is not np.ndarray or v.dtype!=np.dtype(dtype)or not v.flags.c_contiguous or v.shape!=shape or not np.isfinite(v).all():raise NumericalFailure('array')


def observation(v,width):
    keys(v,('wave','amplitude','context'))
    wave=v['wave']
    if type(wave)is not np.ndarray or wave.ndim!=2 or wave.shape[0]!=3 or wave.shape[1]<1:raise NumericalFailure('wave')
    array(wave,wave.shape,'float32');array(v['amplitude'],(4,),'float32');array(v['context'],(width,),'float64')
    return wave.size


def validate(packet):
    keys(packet,('schema','study','rows','denominators','observed_samples','input_pins','fit_authorized'))
    if packet['schema']!='earthquake-TRAIN115-receiver-observations-v2'or packet['study']!='earthquake-TRAIN115-receiver-renewal-v2'or packet['fit_authorized']is not False:raise NumericalFailure('identity')
    keys(packet['denominators'],DENOMINATORS)
    for k,n in DENOMINATORS.items():integer(packet['denominators'][k],n,n)
    keys(packet['observed_samples'],('old','new'));old=integer(packet['observed_samples']['old'],0,136_000_000);new=integer(packet['observed_samples']['new'],0,104_000_000)
    if old+new>240_000_000:raise NumericalFailure('samples')
    keys(packet['input_pins'],('old_plan','old_qualified','new_plan','new_qualified','metadata','roster'))
    for p in packet['input_pins'].values():
        keys(p,('bytes','sha256'));integer(p['bytes'],0,134_217_728)
        if type(p['sha256'])is not str or not re.fullmatch('[0-9a-f]{64}',p['sha256']):raise NumericalFailure('pin')
    rows=packet['rows']
    if type(rows)is not list or len(rows)!=115:raise NumericalFailure('rows')
    partitions=[];roles=dict(TRAIN=[],DEV=[]);elements=bytes_total=0
    for i,row in enumerate(rows):
        keys(row,('ordinal','partition','mw','group','common','status','initial','horizons'));integer(row['ordinal'],i,i);integer(row['group'],-1,i)
        if row['partition']not in('TRAIN','DEV')or type(row['partition'])is not str or(i>=65 and row['partition']!='TRAIN')or not finite(row['mw'])or not -5<=row['mw']<=15 or type(row['common'])is not bool:raise NumericalFailure('role')
        partitions.append(row['partition'])
        if type(row['horizons'])is not list or len(row['horizons'])!=3:raise NumericalFailure('horizons')
        if not row['common']:
            if row['status']!='unavailable'or row['initial']is not None:raise NumericalFailure('unavailable')
            for h,v in zip(HORIZONS,row['horizons']):
                keys(v,('seconds','status'));integer(v['seconds'],h,h)
                if v['status']!='unavailable':raise NumericalFailure('unavailable')
            continue
        if row['status']!='available'or row['group']<0:raise NumericalFailure('common')
        roles[row['partition']].append(i);initial=row['initial'];elements+=observation(initial,35)
        bytes_total+=sum(v.nbytes for v in initial.values());c=initial['context']
        if any(v not in(0,1)for v in c[3:7])or not 0<=c[7]<=.75 or tuple(c[15:17])not in((1.,0.),(0.,1.)):raise NumericalFailure('context')
        previous=None
        for h,v in zip(HORIZONS,row['horizons']):
            keys(v,('seconds','rate','wave','amplitude','context','ratios','states','run_ages'));integer(v['seconds'],h,h)
            elements+=observation({k:v[k]for k in('wave','amplitude','context')},36);bytes_total+=sum(v[k].nbytes for k in('wave','amplitude','context'))
            if not np.array_equal(c[:7],v['context'][:7])or not np.array_equal(c[7:],v['context'][8:])or v['context'][7]!=h:raise NumericalFailure('static_prefix')
            rate=ratio(v['rate'])
            if abs(c[8]-math.log10(float(rate)))>1e-10:raise NumericalFailure('rate_context')
            states=v['states'];run=ages(states)
            if states[0]!=c[6]or type(v['ratios'])is not list or len(v['ratios'])!=len(states)or type(v['run_ages'])is not list or v['run_ages']!=run or any(type(a)is not int for a in v['run_ages']):raise NumericalFailure('activity')
            if not 4*h-3<=len(states)<=4*h or len(states)!=math.floor(4*(h-float(c[7]))):raise NumericalFailure('cell_clock')
            for r,b in zip(v['ratios'],states):
                if not finite(r)or not 0<=r<=1e25 or b!=int(r>9):raise NumericalFailure('ratio_state')
            if previous is not None:
                n=len(previous['states'])
                if len(states)!=n+8 or any(v[k][:n]!=previous[k]for k in('states','ratios','run_ages'))or v['rate']!=previous['rate']:raise NumericalFailure('prefix')
            previous=v
    if partitions[:65].count('TRAIN')!=41 or partitions[:65].count('DEV')!=24 or len(roles['TRAIN'])!=65 or len(roles['DEV'])!=22 or elements>20_000_000 or bytes_total>134_217_728:raise NumericalFailure('denominator')
    mixed={g for g in {r['group']for r in rows if r['group']>=0}if len({r['partition']for r in rows if r['group']==g})>1}
    if any(r['common']and r['group']in mixed for r in rows):raise NumericalFailure('group')
    return roles


def scaler(packet,roles):
    c=np.stack([packet['rows'][i]['initial']['context']for i in roles['TRAIN']])
    mean=np.zeros(35);std=np.ones(35)
    mean[list(CONTINUOUS)]=np.mean(c[:,CONTINUOUS],axis=0);std[list(CONTINUOUS)]=np.std(c[:,CONTINUOUS],axis=0)
    cm=np.r_[mean[:7],np.mean(HORIZONS),mean[7:]];cs=np.r_[std[:7],np.std(HORIZONS),std[7:]]
    return dict(initial_mean=mean,initial_std=std,current_mean=cm,current_std=cs)


def model_context(raw,scalers):
    mean,std=scalers['initial_mean'],scalers['initial_std'];value=np.zeros(35)
    np.divide(raw-mean,std,out=value,where=std!=0)
    return value.astype(np.float32).astype(np.float64).tolist()


def diagnostics(packet,roles):
    out=dict(denominators=dict(DENOMINATORS),unavailable_events=28,old_events=65,new_events=50)
    for partition in('TRAIN','DEV'):
        rows=[packet['rows'][i]for i in roles[partition]]
        horizons={}
        for index,h in enumerate(HORIZONS):
            states=[r['horizons'][index]['states']for r in rows]
            horizons[str(h)]=dict(off=sum(a==1 and b==0 for s in states for a,b in zip(s,s[1:])),on=sum(a==0 and b==1 for s in states for a,b in zip(s,s[1:])),active_censored=sum(s[-1]==1 for s in states))
        out[partition]=dict(common=len(rows),noise_floor_counts=[int(sum(r['initial']['context'][j]==1 for r in rows))for j in(3,4,5)],horizons=horizons)
    return out

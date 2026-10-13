"""Independent native marked semantics; no builder reference, paths or fit IO."""
from fractions import Fraction
import math
import statistics
import time
import numpy as np

H=(1,3,5);Q=250000000;SECOND=1000000000
SCHEMA='earthquake-TRAIN115-marked-noise-observations-v1'
STUDY='earthquake-TRAIN115-marked-noise-study-v1'
DENOMINATORS=dict(events=115,horizon_cells=345,train=91,dev=24,common_train=65,common_dev=22,test_excluded=31)


def need(ok,why):
    if not ok:raise ValueError(why)


def tick(begin):
    now=time.monotonic();need(type(begin) in (int,float) and math.isfinite(begin) and 0<=begin<=now and now-begin<=300,'audit_deadline')


def equal_array(actual,values,dtype,shape):
    expected=np.ascontiguousarray(values,dtype=dtype)
    need(type(actual) is np.ndarray and actual.dtype.str==np.dtype(dtype).str and actual.shape==shape and actual.flags.c_contiguous and np.isfinite(actual).all() and actual.tobytes()==expected.tobytes(),'semantic_array')


def event(row,meta,native,first,period,begin,a):
    tick(begin);n=len(native[0]);need(len(native)==3 and all(len(v)==n for v in native),'native_shape')
    t0,p=row['t0_ns'],row['pick_ns'];delta=p-t0;need(type(delta) is int and 0<=delta<=750000000,'clock')
    centers=[];powers=[];nhat=[];floors=[]
    def bounds(lo,hi):return a.indices(first,period,n,lo,hi)
    def values(c,lo,hi):
        left,right=bounds(lo,hi)
        for k in range(left,right):
            v=float(native[c][k]);need(math.isfinite(v) and abs(v)<=1e12,'native_scalar');yield v
    def power(c,lo,hi):
        left,right=bounds(lo,hi)
        def terms():
            for v in values(c,lo,hi):
                r=v-centers[c];need(abs(r)<=1e12,'centered_bound');yield r*r
        out=math.fsum(terms())/(right-left);need(math.isfinite(out) and 0<=out<=1e24,'power');return out
    for c in range(3):
        tick(begin);left,right=bounds(t0-3*SECOND,t0);center=math.fsum(values(c,t0-3*SECOND,t0))/(right-left)
        need(math.isfinite(center),'center');centers.append(center)
        quarters=[power(c,t0-3*SECOND+k*Q,t0-3*SECOND+(k+1)*Q) for k in range(12)];raw=statistics.median(quarters)
        powers.append(quarters);nhat.append(max(1.,raw));floors.append(int(raw<1.))
    eta=[[math.log(max(1.,statistics.median(powers[c][:k]+powers[c][k+1:]))) for c in range(3)] for k in range(12)]
    center=[math.fsum(e[c] for e in eta)/12 for c in range(3)];nu=[[e[c]-center[c] for c in range(3)] for e in eta]
    rate=Fraction(SECOND)/period
    context=[*[math.log10(v) for v in nhat],*[float(v) for v in floors],delta/1e9]+a.static(row,meta,rate)
    noise=dict(centers=centers,powers=powers,nhat=nhat,floors=floors,nu=nu,weights=[1/12]*12,rate=[rate.numerator,rate.denominator],arrival_offset_ns=delta)
    horizons=[];ratios=[];reported=[];censors=[];maxima=[];states=[];ages=[];last=None;age=0
    for h in H:
        tick(begin);j=(h*SECOND-delta)//Q;need(1<=j<=20,'quarter_count')
        for k in range(len(ratios),j):
            ratios_row=[power(c,p+k*Q,p+(k+1)*Q)/nhat[c] for c in range(3)]
            need(all(math.isfinite(v) and 0<=v<=1e25 for v in ratios_row),'ratio')
            ys=[];cs=[]
            for value in ratios_row:
                censored=value<=math.exp(-12.);logged=-12. if censored else math.log(value)
                need(censored or logged>-12.,'censor_log_roundoff');ys.append(logged);cs.append(int(censored))
            maximum=max(ratios_row);state=int(maximum>9);age=age+1 if state==last else 1;last=state
            ratios.append(ratios_row);reported.append(ys);censors.append(cs);maxima.append(maximum);states.append(state);ages.append(age)
        horizons.append(dict(seconds=h,status='available',ratios=[r[:] for r in ratios],reported=[r[:] for r in reported],censor=[r[:] for r in censors],max_ratios=list(maxima),states=list(states),run_ages=list(ages)))
    return context,noise,horizons


def check_event(actual,anchor,expected,a):
    context,noise,horizons=expected
    need(a.keys(actual,('ordinal','partition','mw','group','common','status','precontext','noise','horizons')) and actual['status']=='available','row_schema')
    equal_array(actual['precontext'],context,'<f8',(34,));need(a.keys(noise,actual['noise']) and len(actual['horizons'])==3,'noise_schema')
    for k,shape,dtype in [('centers',(3,),'<f8'),('powers',(3,12),'<f8'),('nhat',(3,),'<f8'),('floors',(3,),'u1'),('nu',(12,3),'<f8'),('weights',(12,),'<f8')]:equal_array(actual['noise'][k],noise[k],dtype,shape)
    need(actual['noise']['rate']==noise['rate'] and all(type(x) is int for x in actual['noise']['rate']) and type(actual['noise']['arrival_offset_ns']) is int and actual['noise']['arrival_offset_ns']==noise['arrival_offset_ns'],'noise_clock')
    need(a.keys(anchor,('ordinal','partition','mw','group','common','status','context35','horizons')) and type(anchor['context35']) is list and len(anchor['context35'])==35 and all(a.finite(v) for v in anchor['context35']),'anchor_row')
    expected35=context[:6]+[float(horizons[0]['states'][0])]+context[6:]
    need(np.asarray(anchor['context35'],dtype='<f8').tobytes()==np.asarray(expected35,dtype='<f8').tobytes(),'anchor_context')
    need(type(anchor['horizons']) is list and len(anchor['horizons'])==3,'anchor_horizons')
    allpositive=True
    for found,old,expected_h in zip(actual['horizons'],anchor['horizons'],horizons):
        j=len(expected_h['ratios']);need(a.keys(found,expected_h) and type(found['seconds']) is int and found['seconds']==expected_h['seconds'] and found['status']=='available','horizon_schema')
        for key in ('ratios','reported','censor','max_ratios','states','run_ages'):
            dtype='u1' if key in ('censor','states','run_ages') else '<f8';shape=(j,3) if key in ('ratios','reported','censor') else (j,)
            equal_array(found[key],expected_h[key],dtype,shape)
        need(a.keys(old,('seconds','status','ratios','states','run_ages')) and type(old['seconds']) is int and old['seconds']==expected_h['seconds'] and old['status']=='available','anchor_horizon')
        need(type(old['ratios']) is list and len(old['ratios'])==j and all(a.finite(v) and 0<=v<=1e25 for v in old['ratios']) and type(old['states']) is list and len(old['states'])==j and all(type(v) is int and v in (0,1) for v in old['states']) and type(old['run_ages']) is list and len(old['run_ages'])==j and all(type(v) is int and 1<=v<=20 for v in old['run_ages']),'anchor_types')
        for key,dtype in [('ratios','<f8'),('states','u1'),('run_ages','u1')]:
            need(np.asarray(old[key],dtype=dtype).tobytes()==np.asarray(expected_h['max_ratios' if key=='ratios' else key],dtype=dtype).tobytes(),'anchor_activity')
        allpositive=allpositive and not any(c for cell in expected_h['censor'] for c in cell)
    return allpositive


def _audit(old_plan_bytes,old_qualified_bytes,old_bodies,new_plan_bytes,new_qualified_bytes,new_bodies,metadata_bytes,roster_bytes,packet,anchor_bytes,decode_record,native_auditor,*,input_pins,processing_begin,diagnostics):
    tick(processing_begin);a=native_auditor
    raws=dict(old_plan=old_plan_bytes,old_qualified=old_qualified_bytes,new_plan=new_plan_bytes,new_qualified=new_qualified_bytes,metadata=metadata_bytes,roster=roster_bytes)
    need(a.keys(input_pins,tuple(raws)+('activity_anchor',)),'input_pins');a.custody(raws,{k:input_pins[k] for k in raws})
    anchor_pin=input_pins['activity_anchor'];need(type(anchor_bytes) is bytes and len(anchor_bytes)<=4*1024*1024 and a.pin(anchor_bytes)==anchor_pin,'anchor_pin')
    data={k:a.parse(raw,a.PIN_CAPS[k]) for k,raw in raws.items()};anchor=a.parse(anchor_bytes,4*1024*1024)
    plans=[data['old_plan'],data['new_plan']];qs=[data['old_qualified'],data['new_qualified']];meta=data['metadata']
    a.qualification(plans[0],qs[0],old_bodies,a.old_native,65,17);a.qualification(plans[1],qs[1],new_bodies,a.new_native,50,13)
    common=a.roles(meta,data['roster'],plans)
    need(a.keys(packet,('schema','study','rows','denominators','input_pins','observed_samples','fit_authorized')) and packet['schema']==SCHEMA and packet['study']==STUDY and packet['fit_authorized'] is False and a.canonical(packet['denominators'])==a.canonical(DENOMINATORS) and packet['input_pins']==input_pins and type(packet['rows']) is list and len(packet['rows'])==115,'packet_schema')
    need(a.keys(anchor,('schema','original_schema','original_study','source_pins','input_pins','denominators','rows')) and anchor['schema']=='marked-native-original-activity-anchor-v1' and anchor['original_schema']==a.SCHEMA and anchor['original_study']==a.STUDY and anchor['input_pins']=={k:input_pins[k] for k in raws} and type(anchor['rows']) is list and len(anchor['rows'])==115 and a.canonical(anchor['denominators'])==a.canonical(dict(events=115,cells=345,train=91,dev=24,test_excluded=31)),'anchor_schema')
    for i,(r,old,m) in enumerate(zip(packet['rows'],anchor['rows'],meta)):
        need(a.keys(r,('ordinal','partition','mw','group','common','status','precontext','noise','horizons')),'packet_row')
        for row in (r,old):
            need(type(row['ordinal']) is int and row['ordinal']==i and type(row['partition']) is str and row['partition']==m['partition'] and a.finite(row['mw']) and float(row['mw'])==float(m['mw']) and type(row['group']) is int and row['group']==m['group'] and type(row['common']) is bool and row['common']==common[i],'roles')
        if not common[i]:
            expected=[dict(seconds=h,status='unavailable') for h in H]
            need(r['status']=='unavailable' and r['precontext'] is None and r['noise'] is None and a.canonical(r['horizons'])==a.canonical(expected) and old['status']=='unavailable' and old['context35'] is None and a.canonical(old['horizons'])==a.canonical(expected),'noncommon')
    observed={};checked=0;allpositive=True
    for offset,plan,q,bodies,core,namespace in [(0,plans[0],qs[0],old_bodies,a.old_native,'old'),(65,plans[1],qs[1],new_bodies,a.new_native,'new')]:
        counts=diagnostics['counters'][namespace]
        for bi in range(len(plan['batches'])):
            rows=[i for i,row in enumerate(plan['rows']) if row['batch']==bi and common[offset+i]]
            if not rows:continue
            records=a.decode_batch(plan,q,bodies,core,bi,decode_record,counts,processing_begin)
            for i in rows:
                row=plan['rows'][i];views=[a.native_view(row,cell,h,records,core,processing_begin) for h,cell in zip(H,q['rows'][i]['cells'])]
                native,first,period=views[-1]
                for short,first_short,period_short in views[:-1]:need(first_short==first and period_short==period and all(np.asarray(x,dtype='<f8').tobytes()==np.asarray(y[:len(x)],dtype='<f8').tobytes() for x,y in zip(short,native)),'native_prefix')
                expected=event(row,meta[offset+i],native,first,period,processing_begin,a);diagnostics['current_event']={'ordinal':offset+i,'expected':expected}
                positive=check_event(packet['rows'][offset+i],anchor['rows'][offset+i],expected,a)
                allpositive=allpositive and positive;checked+=1;diagnostics['checked_events']=checked;tick(processing_begin)
            records.clear()
        observed[namespace]=counts[0]
    need(packet['observed_samples']==observed and a.keys(packet['observed_samples'],('old','new')) and all(type(v) is int for v in packet['observed_samples'].values()) and checked==87,'observed_counts');tick(processing_begin)
    return dict(schema='marked-native-independent-semantic-audit-v1',semantic_agreed=True,events=115,horizon_cells=345,common_train=65,common_dev=22,allpositive_pilot_admission=allpositive,observed_samples=observed,fit_authorized=False)


class AuditError(ValueError):
    def __init__(self,error,diagnostics):
        super().__init__(str(error)[:128]);self.observed_samples={k:v[0] for k,v in diagnostics['counters'].items()};self.diagnostics=diagnostics


def audit(*args,input_pins,processing_begin):
    diagnostics=dict(counters={'old':[0],'new':[0]},checked_events=0,current_event=None)
    try:return _audit(*args,input_pins=input_pins,processing_begin=processing_begin,diagnostics=diagnostics)
    except Exception as error:raise AuditError(error,diagnostics) from error

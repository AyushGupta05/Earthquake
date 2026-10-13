"""Invented public fixtures only; no real earthquake record or result."""
import math,time
import numpy as np
import packet,transport as tx,math_core as core,auditor,metrics,packet_digest

def packet_fixture():
 rows=[]
 for i in range(115):
  part='TRAIN'if i<91 else'DEV';common=i<65 or 91<=i<113;row=dict(ordinal=i,partition=part,mw=4.8+.1*(i%12),group=i,common=common,status='available'if common else'unavailable',precontext=None,noise=None,horizons=[dict(seconds=h,status='unavailable')for h in(1,3,5)])
  if common:
   n=dict(centers=np.zeros(3),powers=np.full((3,12),2.),nhat=np.full(3,2.),floors=np.zeros(3,dtype=np.uint8),nu=np.zeros((12,3)),weights=np.full(12,1/12),rate=[100,1],arrival_offset_ns=0);ctx=np.zeros(34);ctx[:3]=math.log10(2.);ctx[7]=2.;ctx[8]=i/10.;ctx[14]=1.;ctx[[22,26,30]]=1.;hs=[]
   for h in(1,3,5):
    J=4*h;R=np.asarray([[2.+.1*j+.01*i,3.+.1*j,4.+.2*j]for j in range(J)]);reported=np.asarray([[math.log(float(v))for v in line]for line in R]);maxima=R.max(1);b=np.asarray(maxima>9,dtype=np.uint8);age=[];last=None;count=0
    for v in b:count=count+1 if int(v)==last else 1;last=int(v);age.append(count)
    hs.append(dict(seconds=h,status='available',ratios=R,reported=reported,censor=np.zeros((J,3),dtype=np.uint8),max_ratios=maxima,states=b,run_ages=np.asarray(age,dtype=np.uint8)))
   row.update(precontext=ctx,noise=n,horizons=hs)
  rows.append(row)
 return dict(schema='earthquake-TRAIN115-marked-noise-observations-v1',study='earthquake-TRAIN115-marked-noise-study-v1',rows=rows,denominators=dict(events=115,horizon_cells=345,train=91,dev=24,common_train=65,common_dev=22,test_excluded=31),input_pins={k:dict(bytes=1,sha256='a'*64)for k in('old_plan','old_qualified','new_plan','new_qualified','metadata','roster','activity_anchor')},observed_samples=dict(old=100,new=100),fit_authorized=False)

def state(K,q,arm):
 p={'prior.second.weight':np.zeros((16,16)),'prior.second.bias':np.zeros(16),'prior.head.weight':np.zeros((14,16)),'prior.head.bias':np.r_[np.zeros(4),np.linspace(4.8,5.2,5),np.full(5,-.5)]}
 if K:p.update({'prior.first.weight':np.zeros((16,K)),'prior.first.bias':np.zeros(16)})
 else:p['prior.first_bias']=np.zeros(16)
 if arm in('S','P'):p['coefficients']=np.c_[np.ones(3),np.full(3,.1),np.zeros((3,3)),np.zeros(3)]
 else:p.update(theta=np.zeros(q),tau=np.asarray(0.))
 return p

def probe(parameters):
 n=sum(a.size for a in parameters.values());return dict(events=65,horizons=3,terms=195,used=n,total=n,masks={k:np.ones(v.shape,dtype=np.uint8)for k,v in parameters.items()},maximum_event_gradient_norm={k:1. for k in parameters})

def source_pins():return {k:dict(bytes=1,sha256='a'*64)for k in auditor.SOURCES}

def admission_fixture(packet):
 roles=packet_module_validate(packet);s=packet_module_schema(packet,roles);K=len(s['static']['kept']);q=len(s['summary']['active']);models={};runtime=dict(torch='invented',numpy=np.__version__,threads=1,dtype='float64',device='cpu')
 for seed,arm in auditor.IDS:
  p=state(K,q,arm);prior=tx.sha({k[6:]:v for k,v in p.items()if k.startswith('prior.')});initial=dict(status='initial',study=auditor.STUDY,seed=seed,arm=arm,update=0,parameters=p,schema_sha256=tx.sha(s),packet_sha256=packet_digest.sha(packet),source_pins=source_pins(),prior_sha256=prior);rng=np.random.default_rng(seed+1009);models[str(seed)+':'+arm]=dict(initial=p,initial_receipt=dict(status='durable',sha256=tx.sha(initial)),prior_sha256=prior,probe=probe(p),order=np.asarray([rng.choice(roles['TRAIN'],8,replace=False)for _ in range(300)],dtype=np.int64))
 return dict(status='admitted',study=auditor.STUDY,packet_sha256=packet_digest.sha(packet),source_pins=source_pins(),schema=s,capacity={'S':16*K+544,'P':16*K+544,'D':16*K+527+q},models=models,runtime=runtime,order=[[s,a]for s,a in auditor.IDS],denominators=packet['denominators'],slots=[dict(ordinal=r['ordinal'],partition=r['partition'],common=r['common'],status=r['status'],horizons=[dict(seconds=h['seconds'],status=h['status'])for h in r['horizons']])for r in packet['rows']])
packet_module_validate=packet.validate
packet_module_schema=packet.schema

def checkpoint_fixture(admission,seed=20261012,arm='P'):
 m=admission['models'][str(seed)+':'+arm];p=m['initial'];prior=['prior.first.weight','prior.first.bias']if 'prior.first.weight'in p else['prior.first_bias'];prior+=['prior.second.weight','prior.second.bias','prior.head.weight','prior.head.bias'];order=(['coefficients']if arm in('S','P')else['theta','tau'])+prior
 optimizer={str(i):dict(step=np.asarray(300.,dtype=np.float32),exp_avg=np.zeros(p[k].shape),exp_avg_sq=np.zeros(p[k].shape))for i,k in enumerate(order)}
 return dict(status='final',study=auditor.STUDY,seed=seed,arm=arm,update=300,history=[dict(update=i+1,loss=1.,gradient_norm=1.,ordinals=rows.tolist())for i,rows in enumerate(m['order'])],admission_sha256=tx.sha(admission),packet_sha256=admission['packet_sha256'],source_pins=admission['source_pins'],prior_sha256=m['prior_sha256'],initial_sha256=tx.sha(p),order_sha256=tx.sha(m['order']),runtime=admission['runtime'],parameters=p,optimizer=optimizer,current=dict(update=300,ordinal=int(m['order'][-1,-1]),horizon=5,loss=1.),final_probe=probe(p))

def authority_fixture(packet,admission,cp,score):
 return dict(schema='root-marked-sixfit-independent-authority-v1',verified=True,native_verified=True,optimizer_history_verified=True,gradient_probes_verified=True,stronger_verified=True,packet_sha256=packet_digest.sha(packet),admission_sha256=tx.sha(admission),checkpoint_sha256=tx.sha(cp),score_sha256=tx.sha(score),source_pins=admission['source_pins'],stronger_closure_sha256='b'*64)

def score_fixture(packet,admission,cp):
 s=admission['schema'];rows=[]
 for i in s['dev']:
  for h in(1,3,5):
   row=packet['rows'][i];budget=core.Budget();mix,reference,_=auditor.reconstruct(row,h,s,cp['parameters'],cp['arm'],budget);fresh=mix.scores(row['mw'],crosscheck=False);source=dict(reference=reference,log_weights=mix.logw,means=mix.mu,scales=mix.sd,log_normalizer=float(mix.logz),noise_probabilities=mix.noise);diagnostic=dict(errors=dict(mean=0.,nll=0.,log_normalizer=0.,crps=0.,pit=0.),work=dict(density_points=budget.points,scalar_terms=budget.terms,seconds=0.),allpositive_only=True,reference_reserved_points=240,reference_actual_points=0);rows.append(dict(seed=cp['seed'],arm=cp['arm'],ordinal=i,horizon=h,target=row['mw'],group=row['group'],status='complete',diagnostics=diagnostic,source=source,**fresh))
 return dict(status='complete',study=auditor.STUDY,predictions=rows,seed=cp['seed'],arm=cp['arm'],admission_sha256=tx.sha(admission),packet_sha256=packet_digest.sha(packet),checkpoint_sha256=tx.sha(cp),source_pins=admission['source_pins'],no_optimizer=True,metrics={str(h):metrics.panel([v for v in rows if v['horizon']==h])for h in(1,3,5)})

def aggregate_fixture():
 p=packet_fixture();ad=admission_fixture(p);audits=[];scores=[];pins=[]
 for seed,arm in auditor.IDS:
  cp=checkpoint_fixture(ad,seed,arm);score=score_fixture(p,ad,cp);auth=authority_fixture(p,ad,cp,score);records=[]
  for v in score['predictions']:
   row=p['rows'][v['ordinal']];fresh={k:v[k]for k in('mean','median','nll','crps','pit','quantiles','coverage_50','coverage_80','coverage_95')};records.append(dict(seed=seed,arm=arm,ordinal=v['ordinal'],horizon=v['horizon'],target=v['target'],group=v['group'],family='ENZ',receiver=row['precontext'][8:11].tolist(),rate=row['noise']['rate'],**fresh))
  report=dict(schema='marked-sixfit-independent-audit-v1',status='pass',seed=seed,arm=arm,records=records,metrics={},strata={},checked=66,authority_sha256=tx.sha(auth),score_sha256=tx.sha(score),advance=dict(pass_all=False,checks=[]));audits.append(report);scores.append(score);pins.append(dict(seed=seed,arm=arm,audit_sha256=tx.sha(report),authority_sha256=tx.sha(auth),score_sha256=tx.sha(score),checkpoint_sha256=tx.sha(cp)))
 stronger=[]
 for seed in(20261012,20261013):
  original=next(v for v in scores if v['seed']==seed and v['arm']=='P')
  for arm in('B','F','H','T'):
   records=[]
   for v in original['predictions']:
    keys=['ordinal','horizon','target','group','mean','median','nll','crps','pit','coverage_50','coverage_80','coverage_95']+(['quantiles']if arm in('H','T')else[]);records.append({k:v[k]for k in keys})
   closure=dict(verified=True,no_optimizer=True,checkpoint_sha256='a'*64,source_sha256='b'*64,packet_sha256='c'*64,independent_audit_sha256='d'*64);stronger.append(dict(seed=seed,arm=arm,predictions=records,closure=closure))
 authority=dict(schema='root-marked-sixfit-aggregate-authority-v1',verified=True,native_verified=True,stronger_verified=True,packet_sha256=packet_digest.sha(p),admission_sha256=tx.sha(ad),source_pins=ad['source_pins'],stronger_closure_sha256=tx.sha(stronger),fits=pins)
 return p,ad,audits,scores,stronger,authority

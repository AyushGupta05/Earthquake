"""Invented source-only fixtures, never execution authority."""
import copy
import numpy as np
import fixtures as f
import l_auditor as a
import transport as tx
import metrics
import math_core as core
import packet_digest

def admission(p,o):
 ad=copy.deepcopy(o);ad.update(study=a.STUDY,source_pins={k:dict(bytes=1,sha256='c'*64)for k in a.SOURCES},capacity=dict(o['capacity'],L=o['capacity']['S']),models={},order=[list(x)for x in a.IDS],original_admission_sha256=tx.sha(o),original_source_pins=o['source_pins'])
 for role in ('operator','native_validator'):ad['source_pins'][role]=copy.deepcopy(o['source_pins'][role])
 for seed,arm in a.IDS:
  old=o['models'][str(seed)+':S'];m=copy.deepcopy(old);m['original_initial_sha256']=tx.sha(old['initial'])
  initial=dict(status='initial',study=a.STUDY,seed=seed,arm=arm,update=0,parameters=m['initial'],schema_sha256=tx.sha(ad['schema']),packet_sha256=ad['packet_sha256'],source_pins=ad['source_pins'],prior_sha256=m['prior_sha256'],original_admission_sha256=tx.sha(o),original_initial_sha256=tx.sha(old['initial']))
  m['initial_receipt']=dict(status='durable',sha256=tx.sha(initial));ad['models'][str(seed)+':L']=m
 return ad

def checkpoint(ad,o,seed):
 cp=copy.deepcopy(f.checkpoint_fixture(o,seed,'S'));cp.update(study=a.STUDY,arm='L',admission_sha256=tx.sha(ad),source_pins=ad['source_pins']);cp['parameters']['coefficients'][:,4]=[.3,-.2,1.];return cp

def score(p,ad,cp):
 rows=[]
 for i in ad['schema']['dev']:
  row=p['rows'][i]
  for h in(1,3,5):
   b=core.Budget();mix,reference,_=a.reconstruct(row,h,ad['schema'],cp['parameters'],b);fresh=mix.scores(row['mw'],crosscheck=False)
   source=dict(reference=reference,log_weights=mix.logw,means=mix.mu,scales=mix.sd,log_normalizer=float(mix.logz),noise_probabilities=mix.noise)
   d=dict(errors=dict(mean=0.,nll=0.,log_normalizer=0.,crps=0.,pit=0.,median=0.,quantiles={str(q):0. for q in core.Q}),work=dict(density_points=b.points,scalar_terms=b.terms,seconds=0.),allpositive_only=True,law='shared-level-reference-AR-L-v1')
   rows.append(dict(seed=cp['seed'],arm='L',ordinal=i,horizon=h,target=row['mw'],group=row['group'],status='complete',source=source,diagnostics=d,**fresh))
 return dict(status='complete',study=a.STUDY,predictions=rows,seed=cp['seed'],arm='L',admission_sha256=tx.sha(ad),packet_sha256=packet_digest.sha(p),checkpoint_sha256=tx.sha(cp),source_pins=ad['source_pins'],no_optimizer=True,metrics={str(h):metrics.panel([v for v in rows if v['horizon']==h])for h in(1,3,5)})

def authority(p,ad,o,cp,s):
 return dict(schema='root-shared-reference-AR-L-audit-authority-v1',verified=True,native_verified=True,original_initialization_verified=True,optimizer_history_verified=True,gradient_probes_verified=True,packet_sha256=packet_digest.sha(p),admission_sha256=tx.sha(ad),original_admission_sha256=tx.sha(o),original_execution_closure_sha256='e'*64,checkpoint_sha256=tx.sha(cp),score_sha256=tx.sha(s),source_pins=ad['source_pins'],original_source_pins=o['source_pins'])

def records(s,p):
 out=[]
 for v in s['predictions']:
  row=p['rows'][v['ordinal']];keys=('seed','arm','ordinal','horizon','target','group','mean','median','nll','crps','pit','quantiles','coverage_50','coverage_80','coverage_95')
  out.append(dict({k:v[k]for k in keys},family='ENZ',receiver=row['precontext'][8:11].tolist(),rate=row['noise']['rate']))
 return out

def closed(p,ad,scores):
 fits=[];older=[];origins=[]
 for seed,arm in list(a.old.IDS)+[(s,x)for s in(20261012,20261013)for x in('B','F','H','T')]:
  rows=copy.deepcopy(records(next(s for s in scores if s['seed']==seed),p))
  for v in rows:
   v['arm']=arm
   if arm in('B','F'):v.pop('quantiles')
  item=a.record_set(rows,(seed,arm),p,ad['schema'],quantiles=arm not in('B','F'));(fits if arm in('S','P','D')else older).append(item)
  origins.append(dict(seed=seed,arm=arm,checkpoint_sha256='1'*64,source_sha256='2'*64,packet_sha256='3'*64,independent_audit_sha256='4'*64,origin_sha256='5'*64,records_sha256=tx.sha(rows),original_packet_sha256_semantics='invented historical storage-pair pins, not new marks'))
 return dict(schema='marked-sixfit-independent-aggregate-v1',status='pass',checked=396,fits=fits,stronger=older,paired=[],advance=metrics.guards(fits,older),authority_sha256='6'*64),origins

def agg_authority(p,ad,o,audits,scores,closed,origins):
 pins=[dict(seed=r['seed'],arm='L',audit_sha256=tx.sha(r),authority_sha256=r['authority_sha256'],score_sha256=tx.sha(s),checkpoint_sha256=s['checkpoint_sha256'])for r,s in zip(audits,scores)]
 return dict(schema='root-shared-reference-AR-L-aggregate-authority-v1',verified=True,native_verified=True,original_initialization_verified=True,comparators_verified=True,packet_sha256=packet_digest.sha(p),admission_sha256=tx.sha(ad),original_admission_sha256=tx.sha(o),original_execution_closure_sha256='e'*64,source_pins=ad['source_pins'],original_source_pins=o['source_pins'],fits=pins,closed_comparator_report_sha256=tx.sha(closed),origins_sha256=tx.sha(origins))

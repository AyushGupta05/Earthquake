"""Small independently staged replay of unchanged frozen V3 audit functions."""
import math
import time

IDS=tuple((s,a)for s in(20261012,20261013)for a in('B','F','H','T','C'))
HORIZONS=(1,3,5)

def need(value,reason):
 if not value:raise ValueError(reason)

def prepare(result,packet,scalers,histories,ad,np,check):
 check();roles=ad.validate(packet);st=ad.scaler(packet,roles);labels=np.asarray([packet['rows'][i]['mw']for i in roles['TRAIN']],dtype=np.float64);mean=float(labels.mean());std=float(labels.std());ad.keys(result,('status','fits','capacity','advance','comparisons','diagnostics','fit_authorized'));need(result['status']=='complete'and result['fit_authorized']is False and len(result['fits'])==10,'complete_result');ad.capacity(result['capacity']);need(set(scalers)==set(IDS)and set(histories)==set(IDS),'ten_callbacks')
 for pair in IDS:
  ad.keys(scalers[pair],st);need(all(type(scalers[pair][k])is np.ndarray and scalers[pair][k].dtype==np.float64 and scalers[pair][k].shape==v.shape and scalers[pair][k].tobytes()==v.tobytes()for k,v in st.items()),'checkpoint_scaler')
 for fit,pair in zip(result['fits'],IDS):
  ad.keys(fit,('seed','arm','mref','train_population_std','status','history','predictions','numerical_failures','metrics','strata','extreme_cases'));ad.integer(fit['seed'],pair[0],pair[0]);need(fit['arm']==pair[1]and fit['status']=='complete'and ad.finite(fit['mref'])and fit['mref']==mean and ad.close(fit['train_population_std'],std,1e-8)and type(fit['numerical_failures'])is list and not fit['numerical_failures']and type(fit['predictions'])is list and len(fit['predictions'])==66,'fit_binding');ad.history(fit['history'],pair[1]);need(ad.canonical(histories[pair])==ad.canonical(fit['history']),'history_callback')
 check();return roles,st,mean

def scored_item(stored,pair,row,observation,ordinal,h,st,mean,ad,cache):
 fields=('ordinal','horizon','target','group','family','receiver','rate','numerical','mean','median','nll','crps','pit','coverage_50','coverage_80','coverage_95');ad.keys(stored,fields+('quantiles',)if pair[1]in('H','T','C')else fields);ad.integer(stored['ordinal'],ordinal,ordinal);ad.integer(stored['horizon'],h,h);raw=row['initial']['context'];family='ENZ'if raw[15]==1 else'12Z'
 need(ad.finite(stored['target'])and stored['target']==row['mw']and type(stored['group'])is int and stored['group']==row['group']and stored['family']==family and ad.canonical(stored['receiver'])==ad.canonical(raw[9:12].tolist())and ad.canonical(stored['rate'])==ad.canonical(observation['rate']),'prediction_binding');score,record=ad.numerical_record(stored['numerical'],pair[1],row,observation,st,row['mw'],mean,cache);fresh={k:stored[k]for k in('ordinal','horizon','target','group','family','receiver','rate')};fresh.update(score);return fresh,record,any(not ad.close(stored[k],v)for k,v in score.items())

def fit_audit(result,packet,index,scalers,histories,ad,np,check,retain):
 roles,st,mean=prepare(result,packet,scalers,histories,ad,np,check);need(type(index)is int and 0<=index<10,'fit_index');pair=IDS[index];fit=result['fits'][index];predictions=[];errors=[];initial={};hazard_reference=None;cache={};failure=None
 for position,(stored,(ordinal,h,k))in enumerate(zip(fit['predictions'],((i,h,k)for i in roles['DEV']for k,h in enumerate(HORIZONS)))):
  check();fresh=None;record=None
  try:
   fresh,record,mismatch=scored_item(stored,pair,packet['rows'][ordinal],packet['rows'][ordinal]['horizons'][k],ordinal,h,st,mean,ad,cache)
   if record is not None:
    invariant={n:record[n]for n in('base_raw','z','c','hazard','mref')};value=ad.canonical(invariant);need(ordinal not in initial or value==initial[ordinal],'initial_invariance');initial[ordinal]=value;hb=ad.canonical(record['hazard']);need(hazard_reference is None or hb==hazard_reference,'checkpoint_hazard');hazard_reference=hb
   outcome=dict(schema='receiver-numerical-record-outcome-v1',position=position,seed=pair[0],arm=pair[1],ordinal=ordinal,horizon=h,status='fail'if mismatch else'pass',fresh=fresh,reason='stored_score'if mismatch else None)
  except Exception as error:
   outcome=dict(schema='receiver-numerical-record-outcome-v1',position=position,seed=pair[0],arm=pair[1],ordinal=ordinal,horizon=h,status='fail',fresh=fresh,returned_record=record,reason=str(error)[:128],exception_type=type(error).__name__,numeric_evidence=getattr(error,'evidence',None));retain(outcome);failure=type(error).__name__;break
  retain(outcome);predictions.append(fresh)
  if mismatch:errors.append('stored_score')
  check()
 if failure is not None:return dict(schema='receiver-fit-score-audit-v1',status='fail',complete=False,seed=pair[0],arm=pair[1],predictions=predictions,reasons=[failure],advance=dict(pass_all=False,checks=[]))
 need(len(predictions)==66,'complete66');panel={str(h):ad.metrics([v for v in predictions if v['horizon']==h])for h in HORIZONS};strata=ad.strata(predictions)
 if not ad.close(fit['metrics'],panel):errors.append('stored_metrics')
 if not ad.close(fit['strata'],strata):errors.append('stored_strata')
 if ad.canonical(fit['extreme_cases'])!=ad.canonical([v for v in fit['predictions']if v['target']>=7]):errors.append('stored_extreme_cases')
 fresh=dict(seed=pair[0],arm=pair[1],status='complete',predictions=predictions,metrics=panel,strata=strata,extreme_cases=[v for v in predictions if v['target']>=7]);return dict(schema='receiver-fit-score-audit-v1',status='fail'if errors else'pass',complete=True,seed=pair[0],arm=pair[1],fit=fresh,reasons=sorted(set(errors)),advance=dict(pass_all=False,checks=[]))

def aggregate(result,packet,reports,scalers,histories,ad,np,check):
 roles,st,mean=prepare(result,packet,scalers,histories,ad,np,check);need(type(reports)is list and len(reports)==10,'ten_reports');fresh=[];errors=[]
 for fit_index,(report,pair)in enumerate(zip(reports,IDS)):
  check();need(report['schema']=='receiver-fit-score-audit-v1'and report['complete']is True and(report['seed'],report['arm'])==pair and report['status']in('pass','fail')and type(report['reasons'])is list and((report['status']=='pass')==(not report['reasons'])),'fit_report_binding');v=report['fit'];need(v['status']=='complete'and(v['seed'],v['arm'])==pair and type(v['predictions'])is list and len(v['predictions'])==66,'report66');pred=v['predictions']
  for item,(ordinal,h,k)in zip(pred,((i,h,k)for i in roles['DEV']for k,h in enumerate(HORIZONS))):
   row=packet['rows'][ordinal];ad.integer(item['ordinal'],ordinal,ordinal);ad.integer(item['horizon'],h,h);need(item['target']==row['mw']and type(item['group'])is int and item['group']==row['group']and ad.canonical(item['receiver'])==ad.canonical(row['initial']['context'][9:12].tolist())and ad.canonical(item['rate'])==ad.canonical(row['horizons'][k]['rate'])and item['family']==('ENZ'if row['initial']['context'][15]==1 else'12Z'),'aggregate_record_binding')
  panel={str(h):ad.metrics([p for p in pred if p['horizon']==h])for h in HORIZONS};strata=ad.strata(pred)
  if not ad.close(result['fits'][fit_index]['metrics'],panel):errors.append('stored_metrics')
  if not ad.close(result['fits'][fit_index]['strata'],strata):errors.append('stored_strata')
  if ad.canonical(v['extreme_cases'])!=ad.canonical([p for p in pred if p['target']>=7]):errors.append('report_extreme_cases')
  fresh.append(dict(seed=pair[0],arm=pair[1],status='complete',predictions=pred,metrics=panel,strata=strata,extreme_cases=[p for p in pred if p['target']>=7]));errors.extend(report['reasons'])
 comparisons=[]
 for seed in(20261012,20261013):
  by={f['arm']:f for f in fresh if f['seed']==seed}
  for h in HORIZONS:
   for arm in('B','F','H','T'):check();comparisons.append(dict(seed=seed,horizon=h,comparator=arm,intervals=ad.paired([p for p in by['C']['predictions']if p['horizon']==h],[p for p in by[arm]['predictions']if p['horizon']==h])))
 guard=ad.advance(fresh);diag=ad.diagnostics(packet,roles)
 if not ad.close(result['comparisons'],comparisons):errors.append('stored_comparisons')
 if not ad.close(result['advance'],guard,0):errors.append('stored_advance')
 if not ad.close(result['diagnostics'],diag,0):errors.append('stored_diagnostics')
 return dict(schema='earthquake-TRAIN115-renewal-score-audit-v3',status='fail'if errors else'pass',reasons=sorted(set(errors)),fits=fresh,comparisons=comparisons,advance=guard if not errors else dict(pass_all=False,checks=[]),recomputed_advance=guard,diagnostics=diag)

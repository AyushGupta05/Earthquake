"""Independent saved-result audit; no producer/checkpoint imports or IO."""
import json
import math
import time
import numpy as np
from numerical import Posterior, factors, mixture_from_raw, hermite, gaussian_score, finite, NumericalFailure
from packet_validation import validate, scaler, model_context, diagnostics, keys, integer
from metrics import SEEDS, ARMS, HORIZONS, metrics, strata, paired, advance

MAX_OUTPUT=16*1024*1024
QUANTILES=(.025,.1,.25,.5,.75,.9,.975)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')


def close(stored,expected,tolerance=1e-4):
    if type(expected)is float:return finite(stored)and abs(stored-expected)<=tolerance+1e-6*abs(expected)
    if type(expected)is dict:return type(stored)is dict and set(stored)==set(expected)and all(close(stored[k],v,tolerance)for k,v in expected.items())
    if type(expected)is list:return type(stored)is list and len(stored)==len(expected)and all(close(a,b,tolerance)for a,b in zip(stored,expected))
    return type(stored)is type(expected)and stored==expected


def promoted(value):
    if type(value)is list:return all(promoted(v)for v in value)
    if type(value)is dict:return all(promoted(v)for v in value.values())
    if not finite(value):return False
    with np.errstate(over='ignore',invalid='ignore'):
        return float(np.float32(value))==value


def capacity(value):
    keys(value,('counts','nonzero_TRAIN_probe_gradient_degrees'));expected=dict(B=5007,F=5147,H=5125,T=5125,C=5125)
    for field in value:
        keys(value[field],ARMS)
        for arm in ARMS:integer(value[field][arm],1,expected[arm])
        numbers=list(value[field].values())
        if max(numbers)>1.05*min(numbers):raise NumericalFailure('capacity_spread')
    if value['counts']!=expected:raise NumericalFailure('capacity_counts')


def history(entries,arm):
    fields=('update','base_nll','sequence_nll','joint_or_conditional_nll','gradient_norm','base_gradient_norm','sequence_gradient_norm','seconds')
    if type(entries)is not list or len(entries)!=300:raise NumericalFailure('history')
    previous=0.
    for update,v in enumerate(entries,1):
        keys(v,fields);integer(v['update'],update,update)
        if any(not finite(v[k])for k in fields[1:])or not previous<=v['seconds']<=300 or any(v[k]<0 for k in('gradient_norm','base_gradient_norm','sequence_gradient_norm')):raise NumericalFailure('history')
        if not close(float(v['joint_or_conditional_nll']),float(v['base_nll']+v['sequence_nll'])):raise NumericalFailure('loss_decomposition')
        if arm in('B','F')and(v['sequence_nll']!=0 or v['sequence_gradient_norm']!=0):raise NumericalFailure('conditional_history')
        previous=v['seconds']


def numerical_record(record,arm,row,observation,scalers,target,mref,cache):
    if arm in('B','F'):
        keys(record,('pi','mu','sigma'));key=('base',canonical(record),target)
        if key not in cache:cache[key]=gaussian_score(target,record['pi'],record['mu'],record['sigma'])
        return dict(cache[key]),None
    keys(record,('accepted','errors','torch_errors','base_raw','z','c','states','hazard','mref','integrals'))
    if record['accepted']is not True or not finite(record['mref'])or record['mref']!=mref or type(record['z'])is not list or len(record['z'])!=36 or type(record['c'])is not list or len(record['c'])!=35:raise NumericalFailure('numeric_binding')
    if not promoted([record['base_raw'],record['z'],record['c']])or not close(record['c'],model_context(row['initial']['context'],scalers),1e-7)or record['z'][-4:]!=row['initial']['amplitude'].astype(np.float64).tolist():raise NumericalFailure('numeric_context')
    if canonical(record['states'])!=canonical(observation['states']):raise NumericalFailure('numeric_states')
    hazard=record['hazard'];keys(hazard,('alpha','beta','z_weights','c_weights','gamma','extra'))
    if not promoted(hazard):raise NumericalFailure('numeric_precision')
    h=dict(alpha=hazard['alpha'],beta=hazard['beta'],v=hazard['z_weights'],w=hazard['c_weights'],gamma=hazard['gamma'],eta=hazard['extra'])
    affine=factors(arm,record['states'],record['z'],record['c'],h,mref);pi,mu,sigma=mixture_from_raw(record['base_raw'])
    key=('posterior',canonical([pi,mu,sigma,affine]),target)
    if key not in cache:
        posterior=Posterior(pi,mu,sigma,affine)
        try:
            score=posterior.score(target);score['quantiles']={str(q):posterior.quantile(q)for q in QUANTILES}
            adaptive=dict(method='adaptive',log_normalizer=posterior.log_normalizer,mean=posterior.mean,nll=-posterior.log_pdf(target))
            gh64=hermite(pi,mu,sigma,affine,target,64);gh128=hermite(pi,mu,sigma,affine,target,128)
            integrals=dict(gh64=gh64,gh128=gh128,adaptive=adaptive)
            errors={field:max(v[field]for v in integrals.values())-min(v[field]for v in integrals.values())for field in('log_normalizer','mean','nll')}
            if any(v>1e-4 or not math.isfinite(v)for v in errors.values()):raise NumericalFailure('independent_parity',dict(integrals=integrals,errors=errors))
            score.update(mean=gh64['mean'],nll=gh64['nll']);score.pop('log_normalizer')
            cache[key]=(score,integrals,errors)
        finally:
            posterior._cdf_cache.clear();posterior.components.clear()
    score,integrals,errors=cache[key]
    if not close(record['integrals'],integrals)or not close(record['errors'],errors,1e-8):raise NumericalFailure('stored_integrals',dict(integrals=integrals,errors=errors))
    keys(record['torch_errors'],('64','128'))
    if any(not finite(v)or not 0<=v<=1e-4 for v in record['torch_errors'].values()):raise NumericalFailure('torch_parity')
    return dict(score),record


def audit(result,packet,checkpoint_scalers=None,histories=None,*,processing_begin,wall_seconds=900):
    """Pure saved replay; parent authenticates inputs/runtime/live limits first."""
    fresh=[];comparisons=[];errors=[];cache={};recomputed_guard=dict(pass_all=False,checks=[])
    try:
        if not finite(processing_begin)or not 0<=processing_begin<=time.monotonic()or not finite(wall_seconds)or not 0<wall_seconds<=900:raise NumericalFailure('deadline')
        def deadline():
            if time.monotonic()-processing_begin>wall_seconds:raise NumericalFailure('deadline')
        deadline();roles=validate(packet);scalers=scaler(packet,roles);train_labels=np.asarray([packet['rows'][i]['mw']for i in roles['TRAIN']],dtype=np.float64)
        mref=float(train_labels.mean());std=float(train_labels.std());expected_pairs=[(s,a)for s in SEEDS for a in ARMS]
        for supplied in(checkpoint_scalers,histories):
            if supplied is not None and(type(supplied)is not dict or set(supplied)!=set(expected_pairs)or any(type(k)is not tuple or len(k)!=2 or type(k[0])is not int or type(k[1])is not str for k in supplied)):raise NumericalFailure('callback_binding')
        if checkpoint_scalers is not None:
            for supplied in checkpoint_scalers.values():
                keys(supplied,scalers)
                if any(type(supplied[k])is not np.ndarray or supplied[k].shape!=v.shape or not np.isfinite(supplied[k]).all()or not np.allclose(supplied[k],v,rtol=1e-6,atol=1e-8)for k,v in scalers.items()):raise NumericalFailure('checkpoint_scaler')
        keys(result,('status','fits','capacity','advance','comparisons','diagnostics','fit_authorized'))
        if result['status']!='complete'or result['fit_authorized']is not False or type(result['fits'])is not list or len(result['fits'])!=10:raise NumericalFailure('complete_result')
        capacity(result['capacity']);expected_predictions=[(i,h,index)for i in roles['DEV']for index,h in enumerate(HORIZONS)]
        for fit,pair in zip(result['fits'],expected_pairs):
            deadline();keys(fit,('seed','arm','mref','train_population_std','status','history','predictions','numerical_failures','metrics','strata','extreme_cases'))
            integer(fit['seed'],pair[0],pair[0])
            if fit['arm']!=pair[1]or fit['status']!='complete'or not finite(fit['mref'])or fit['mref']!=mref or not close(fit['train_population_std'],std,1e-8)or type(fit['numerical_failures'])is not list or fit['numerical_failures']or type(fit['predictions'])is not list or len(fit['predictions'])!=66:raise NumericalFailure('fit_binding')
            history(fit['history'],pair[1])
            if histories is not None and canonical(histories[pair])!=canonical(fit['history']):raise NumericalFailure('history_callback')
            predictions=[];initial_records={};hazard_reference=None
            for stored,(ordinal,h,index)in zip(fit['predictions'],expected_predictions):
                deadline();fields=('ordinal','horizon','target','group','family','receiver','rate','numerical','mean','median','nll','crps','pit','coverage_50','coverage_80','coverage_95')
                keys(stored,fields+('quantiles',)if pair[1]in('H','T','C')else fields);integer(stored['ordinal'],ordinal,ordinal);integer(stored['horizon'],h,h)
                row=packet['rows'][ordinal];observation=row['horizons'][index];raw=row['initial']['context'];family='ENZ'if raw[15]==1 else'12Z'
                if not finite(stored['target'])or stored['target']!=row['mw']or type(stored['group'])is not int or stored['group']!=row['group']or stored['family']!=family or canonical(stored['receiver'])!=canonical(raw[9:12].tolist())or canonical(stored['rate'])!=canonical(observation['rate']):raise NumericalFailure('prediction_binding')
                scored,record=numerical_record(stored['numerical'],pair[1],row,observation,scalers,row['mw'],mref,cache)
                if record is not None:
                    invariant={k:record[k]for k in('base_raw','z','c','hazard','mref')}
                    if ordinal in initial_records and canonical(invariant)!=initial_records[ordinal]:raise NumericalFailure('initial_invariance')
                    initial_records[ordinal]=canonical(invariant)
                    hazard_bytes=canonical(record['hazard'])
                    if hazard_reference is not None and hazard_bytes!=hazard_reference:raise NumericalFailure('checkpoint_hazard')
                    hazard_reference=hazard_bytes
                if any(not close(stored[k],v)for k,v in scored.items()):errors.append('stored_score')
                predictions.append({k:stored[k]for k in('ordinal','horizon','target','group','family','receiver','rate')}|scored)
            panel={str(h):metrics([p for p in predictions if p['horizon']==h])for h in HORIZONS};strata_panel=strata(predictions)
            if not close(fit['metrics'],panel):errors.append('stored_metrics')
            if not close(fit['strata'],strata_panel):errors.append('stored_strata')
            stored_extreme=[p for p in fit['predictions']if p['target']>=7]
            if canonical(fit['extreme_cases'])!=canonical(stored_extreme):errors.append('stored_extreme_cases')
            fresh.append(dict(seed=pair[0],arm=pair[1],status='complete',predictions=predictions,metrics=panel,strata=strata_panel,extreme_cases=[p for p in predictions if p['target']>=7]))
        for seed in SEEDS:
            by={f['arm']:f for f in fresh if f['seed']==seed}
            for h in HORIZONS:
                for comparator in ARMS[:-1]:
                    deadline();left=[p for p in by['C']['predictions']if p['horizon']==h];right=[p for p in by[comparator]['predictions']if p['horizon']==h]
                    comparisons.append(dict(seed=seed,horizon=h,comparator=comparator,intervals=paired(left,right)))
        guard=advance(fresh);recomputed_guard=guard;diag=diagnostics(packet,roles)
        if not close(result['comparisons'],comparisons):errors.append('stored_comparisons')
        if not close(result['advance'],guard,0):errors.append('stored_advance')
        if not close(result['diagnostics'],diag,0):errors.append('stored_diagnostics')
        report=dict(schema='earthquake-TRAIN115-renewal-score-audit-v3',status='fail'if errors else'pass',reasons=sorted(set(errors)),fits=fresh,comparisons=comparisons,advance=guard if not errors else dict(pass_all=False,checks=[]),recomputed_advance=guard,diagnostics=diag)
        if len(canonical(report))>MAX_OUTPUT:raise NumericalFailure('output_cap')
        deadline();return report
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,FloatingPointError)as exc:
        report=dict(schema='earthquake-TRAIN115-renewal-score-audit-v3',status='fail',reasons=['input_or_numerical_invalid'],fits=fresh,comparisons=comparisons,advance=dict(pass_all=False,checks=[]),recomputed_advance=recomputed_guard,failure=dict(reason=type(exc).__name__,numeric_evidence=getattr(exc,'evidence',None)))
        while len(canonical(report))>MAX_OUTPUT and report['comparisons']:report['comparisons'].pop()
        while len(canonical(report))>MAX_OUTPUT and report['fits']:report['fits'].pop()
        if len(canonical(report))>MAX_OUTPUT:raise NumericalFailure('bounded_failure_unavailable')
        return report

"""TRAIN-only nested adequacy; pure numeric inputs, no CLI/IO/native reader."""
import hashlib
import json
import math
import re
import time
from collections import Counter
import numpy as np
import fit as estimator
import metrics as risk
from numerics import NormalPosterior, check_deadline, posterior

SCHEMA='earthquake-train-amplitude-adequacy-input-v1'
RESULT='earthquake-train-amplitude-adequacy-result-v1'
PROPOSAL='cfe9971b0819beda5ebdfec665aa7e2c99e2dc2a11f0bde7aeda45859a2a8a16'
DENIED={'UNSUPPORTED','BAD_NOISE','BAD_WINDOW'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('ascii')


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def fields(value,expected):
    if type(value) is not dict or set(value)!=set(expected):raise ValueError('exact_object_keys')


def number(value,low=-math.inf,high=math.inf):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError('finite_builtin_scalar')
    return float(value)


def integer(value,low,high):
    if type(value) is not int or not low<=value<=high:raise ValueError('strict_integer')


def validate_input(value):
    fields(value,('schema','coverage','events'))
    if type(value['schema']) is not str or value['schema']!=SCHEMA:raise ValueError('input_schema')
    cv=value['coverage']
    if type(cv) is not list or len(cv)!=65:raise ValueError('coverage65')
    expected=[];partitions=Counter()
    for i,row in enumerate(cv):
        fields(row,('slot','partition','common','horizon_statuses'))
        integer(row['slot'],0,64)
        if row['slot']!=i or type(row['common']) is not bool:raise ValueError('coverage_order_common')
        p=row['partition']
        if type(p) is not str or p not in ('TRAIN','DEV'):raise ValueError('TRAIN_DEV_only')
        partitions[p]+=1
        hs=row['horizon_statuses']
        if type(hs) is not list or len(hs)!=3 or any(type(s) is not str for s in hs):raise ValueError('three_statuses')
        if p=='DEV':
            if hs!=['DEFERRED_DEV']*3:raise ValueError('DEV_denied')
        elif not row['common']:
            if hs!=['NON_COMMON']*3:raise ValueError('non_common_denied')
        else:
            if any(s not in DENIED|{'available'} for s in hs):raise ValueError('common_status')
            expected.append(i)
    if partitions!={'TRAIN':41,'DEV':24}:raise ValueError('original41_24')
    events=value['events']
    if type(events) is not list or len(events)!=len(expected):raise ValueError('fixed_common_TRAIN_set')
    for e,slot in zip(events,expected):
        fields(e,('slot','mw','group','horizons'))
        integer(e['slot'],0,64)
        if e['slot']!=slot:raise ValueError('no_drop_or_replacement')
        number(e['mw'],2.8,8.)
        if type(e['group']) is not str or not re.fullmatch('[A-Za-z0-9._-]{1,64}',e['group']):raise ValueError('group_identifier')
        hs=e['horizons']
        if type(hs) is not list or len(hs)!=3:raise ValueError('three_horizons')
        last_ratio=None;by_component={};age0=None
        for j,(h,seconds) in enumerate(zip(hs,(1,3,5))):
            fields(h,('seconds','status','features'));integer(h['seconds'],1,5)
            if h['seconds']!=seconds or h['status']!=cv[slot]['horizon_statuses'][j]:raise ValueError('horizon_parity')
            f=h['features']
            if h['status']!='available':
                if f is not None:raise ValueError('denied_features')
                continue
            fields(f,('y','L','censored','u','selected_component','noise_floor','peak','noise'))
            number(f['y'],-12,12);number(f['L'],-12,0);number(f['u'],.25,seconds)
            number(f['peak'],0,1e12);number(f['noise'],1,1e12);integer(f['selected_component'],0,2)
            if type(f['censored']) is not bool or type(f['noise_floor']) is not bool:raise ValueError('feature_boolean')
            if f['noise_floor'] and f['noise']!=1:raise ValueError('noise_floor_parity')
            if f['censored']!=(f['peak']<=1):raise ValueError('censor_parity')
            if abs(f['L']+math.log10(f['noise']))>1e-12 or abs(f['y']-math.log10(max(f['peak'],1)/f['noise']))>1e-12:
                raise ValueError('feature_identity')
            age=f['u']-seconds
            if age0 is not None and abs(age-age0)>1e-9:raise ValueError('fixed_P_age')
            age0=age
            ratio=f['peak']/f['noise']
            if last_ratio is not None and ratio+1e-12<last_ratio:raise ValueError('cumulative_peak_ratio')
            last_ratio=ratio
            c=f['selected_component']
            if c in by_component:
                old=by_component[c]
                if f['noise']!=old['noise'] or f['noise_floor']!=old['noise_floor'] or f['peak']<old['peak']:
                    raise ValueError('same_component_noise_peak')
            by_component[c]=f
    raw=canonical(value)
    if len(raw)>16*1024*1024:raise ValueError('numeric_input_cap')
    return json.loads(raw)


def folds(events,count):
    groups={e['group'] for e in events}
    if len(groups)<count:raise ValueError('nonempty_group_folds')
    order=sorted(groups,key=lambda g:(hashlib.sha256(('amplitude-age-adequacy-v1|'+g).encode('utf8')).hexdigest(),g))
    return {g:i%count for i,g in enumerate(order)}


def source_deadline(deadline):
    now=time.monotonic()
    if deadline is None:return now+900.
    number(deadline,0,math.inf)
    check_deadline(deadline)
    return min(deadline,now+900.)


def support(events):
    known=all(h['status']=='available' for e in events for h in e['horizons'])
    return {'complete_common_TRAIN':known,'TRAIN_events':len(events),'groups':len({e['group'] for e in events}),
            'high5_5':sum(e['mw']>=5.5 for e in events),'lower':sum(e['mw']<5.5 for e in events),
            'passed':bool(known and len(events)>=20 and len({e['group'] for e in events})>=5
                          and sum(e['mw']>=5.5 for e in events)>=8 and sum(e['mw']<5.5 for e in events)>=5)}


class Tracker:
    def __init__(self,deadline,maximum):self.deadline=deadline;self.maximum=maximum;self.records=[]
    def fit(self,events,penalty,role):
        check_deadline(self.deadline)
        if len(self.records)>=self.maximum:raise ArithmeticError('fit_count_cap')
        record={'index':len(self.records),'role':role,'lambda':float(penalty),'status':'started',
                'training_slots':[e['slot'] for e in events],'training_groups':sorted({e['group'] for e in events})}
        self.records.append(record)
        try:
            result=estimator.fit(events,penalty,self.deadline)
            record.update(status='complete',fit=result)
            return result
        except (ArithmeticError,ValueError,TimeoutError,RuntimeError,OverflowError,MemoryError) as exc:
            record.update(status='failed',reason=type(exc).__name__+':'+str(exc)[:128])
            raise


def evaluate(events,model,deadline,score=True):
    out={str(h):[] for h in (1,3,5)}
    prior=model['prior']
    for e in events:
        for h in e['horizons']:
            check_deadline(deadline)
            p=posterior(model['parameters'],prior,model['scaler'],h['features'],deadline)
            if score:
                result=p.score(e['mw']);control=NormalPosterior(prior['mean'],prior['sd'],deadline).score(e['mw'])
            else:
                result={'nll':float(-p.logpdf(e['mw']))};control=None
            out[str(h['seconds'])].append({'slot':e['slot'],'group':e['group'],'mw':e['mw'],
                                           'model':result,'prior':control})
    return out


def merge(destination,source):
    for h in ('1','3','5'):destination[h].extend(source[h])


def choose(events,count,tracker,role):
    assignment=folds(events,count)
    scores={}
    for penalty in estimator.LAMBDAS:
        predictions={str(h):[] for h in (1,3,5)}
        for index in range(count):
            training=[e for e in events if assignment[e['group']]!=index]
            held=[e for e in events if assignment[e['group']]==index]
            model=tracker.fit(training,penalty,role+'-lambda'+str(penalty)+'-fold'+str(index))
            merge(predictions,evaluate(held,model,tracker.deadline,score=False))
        vals=[]
        for h in ('1','3','5'):
            w=risk.weights(predictions[h]);vals.append(float(w@np.array([r['model']['nll'] for r in predictions[h]])))
        scores[penalty]=sum(vals)/3
    minimum=min(scores.values())
    selected=max(p for p,s in scores.items() if s<=minimum+1e-12)
    return selected,{'folds':assignment,'scores':[{'lambda':p,'nll':scores[p]} for p in estimator.LAMBDAS]}


def seal(result):
    result['result_hash']=digest(result)
    if len(canonical(result))>16*1024*1024:raise ArithmeticError('private_result_cap')
    return result


def run_outer(value,*,deadline=None):
    deadline=source_deadline(deadline)
    data=validate_input(value);events=data['events'];s=support(events);tracker=Tracker(deadline,105)
    result={'schema':RESULT,'proposal_sha256':PROPOSAL,'phase':'outer','input_hash':digest(data),
            'coverage':data['coverage'],'support':s,'status':'incomplete','reason':None,
            'source_deadline':deadline,
            'fits':tracker.records,'predictions':{str(h):[] for h in (1,3,5)},'choices':[],
            'metrics':None,'bootstrap':None,'gate':{'passed':False},'full_TRAIN_fits':0}
    if not s['passed']:
        result['reason']='support_or_missing_common_TRAIN';return seal(result)
    try:
        outer=folds(events,5);result['outer_folds']=outer
        for index in range(5):
            training=[e for e in events if outer[e['group']]!=index]
            held=[e for e in events if outer[e['group']]==index]
            penalty,choice=choose(training,4,tracker,'outer'+str(index)+'-inner')
            model=tracker.fit(training,penalty,'outer'+str(index)+'-final')
            result['choices'].append({'outer_index':index,'lambda':penalty,'inner':choice})
            merge(result['predictions'],evaluate(held,model,deadline))
        for rows in result['predictions'].values():rows.sort(key=lambda r:r['slot'])
        check_deadline(deadline)
        result['metrics']={h:{arm:risk.summarize(rows,arm) for arm in ('model','prior')}
                           for h,rows in result['predictions'].items()}
        result['bootstrap']=risk.bootstrap(result['predictions'],deadline,check_deadline)
        result['gate']=risk.observed_gate(result['metrics'])
        result['status']='complete'
    except (ArithmeticError,ValueError,TimeoutError,RuntimeError,OverflowError,MemoryError) as exc:
        result['reason']=type(exc).__name__+':'+str(exc)[:128];result['gate']={'passed':False}
    return seal(result)


def continue_train(value,outer_result,*,deadline=None):
    deadline=source_deadline(deadline);data=validate_input(value)
    if type(outer_result) is not dict or 'result_hash' not in outer_result:raise ValueError('outer_receipt_required')
    original={k:v for k,v in outer_result.items() if k!='result_hash'}
    if (digest(original)!=outer_result['result_hash'] or original.get('schema')!=RESULT
            or original.get('proposal_sha256')!=PROPOSAL or original.get('phase')!='outer'
            or original.get('input_hash')!=digest(data) or original.get('coverage')!=data['coverage']
            or original.get('support')!=support(data['events']) or original.get('status')!='complete'
            or original.get('full_TRAIN_fits')!=0 or len(original.get('fits',[]))!=105
            or any(r.get('status')!='complete' or r.get('index')!=i for i,r in enumerate(original['fits']))
            or risk.observed_gate(original.get('metrics',{}))!=original.get('gate')
            or original['gate']['passed'] is not True):raise ValueError('verified_passed_outer_required')
    # Parent authenticates persisted original bytes. Recompute all row/metric parities
    # here as an additional accidental-tamper guard, never as external authority.
    for h in ('1','3','5'):
        rows=original['predictions'][h]
        if [(r['slot'],r['group'],r['mw']) for r in rows]!=[(e['slot'],e['group'],e['mw']) for e in data['events']]:
            raise ValueError('outer_prediction_membership')
        for arm in ('model','prior'):
            if risk.summarize(rows,arm)!=original['metrics'][h][arm]:raise ValueError('outer_metric_tamper')
    number(original.get('source_deadline'),0,math.inf)
    deadline=min(deadline,original['source_deadline'])
    check_deadline(deadline)
    tracker=Tracker(deadline,26)
    result={'schema':RESULT,'proposal_sha256':PROPOSAL,'phase':'full_TRAIN','input_hash':digest(data),
            'outer_result_hash':outer_result['result_hash'],'status':'incomplete','reason':None,
            'fits':tracker.records,'model':None,'choice':None,'gate':{'passed':False},'DEV_predictions':0}
    try:
        penalty,choice=choose(data['events'],5,tracker,'fullTRAIN-choice')
        result['choice']=choice
        result['model']=tracker.fit(data['events'],penalty,'fullTRAIN-final')
        check_deadline(deadline);result['status']='complete'
    except (ArithmeticError,ValueError,TimeoutError,RuntimeError,OverflowError,MemoryError) as exc:
        result['reason']=type(exc).__name__+':'+str(exc)[:128]
    return seal(result)


def public_summary(result):
    if type(result) is not dict or result.get('schema')!=RESULT:raise ValueError('result_schema')
    return {'schema':'earthquake-train-amplitude-adequacy-public-v1','phase':result['phase'],
            'status':result['status'],'fit_attempts':len(result['fits']),
            'successful_fits':sum(r['status']=='complete' for r in result['fits']),
            'observed_gate_passed':bool(result.get('gate',{}).get('passed',False)),
            'original_slots':65,'original_horizon_cells':195,'DEV_predictions':0,
            'actual_authority':False,'independent_population_proof':False,'physical_sequence_independence':False,
            'novelty':False,'published_superiority':False,'acquisition_authorized':False}

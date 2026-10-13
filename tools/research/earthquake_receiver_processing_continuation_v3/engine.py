"""Pure one-attempt processing stages; external parent authority is required."""
import math
import time
import numpy as np

SEEDS=(20261012,20261013)
ARMS=('B','F','H','T','C')
HORIZONS=(1,3,5)
IDENTITIES=tuple((seed,arm) for seed in SEEDS for arm in ARMS)
ORIGINAL=IDENTITIES[:3]
FRESH=IDENTITIES[3:]
HISTORY_KEYS={'update','base_nll','sequence_nll','joint_or_conditional_nll','gradient_norm','base_gradient_norm','sequence_gradient_norm','seconds'}
ADMISSION_KEYS={'schema','original_replay_verified','source_runtime_verified','resource_verified','capacity','scorer_mode','scorer_binding','optional_scorer_verified'}


def need(ok,reason):
    if not ok:raise ValueError(reason)


def tick(processing_begin,experiment_begin,limit):
    now=time.monotonic()
    for begin in (processing_begin,experiment_begin):
        need(type(begin) in (int,float) and math.isfinite(begin) and 0<=begin<=now,'clock')
    need(experiment_begin<=processing_begin,'clock_order')
    if now-processing_begin>limit or now-experiment_begin>7200:raise RuntimeError('renewal_deadline')


def identity(seed,arm,fresh=False):
    need(type(seed) is int and type(arm) is str and (seed,arm) in (FRESH if fresh else IDENTITIES),'identity')


def admission_checked(admission):
    need(type(admission) is dict and set(admission)==ADMISSION_KEYS and admission['schema']=='receiver-continuation-admission-v3','admission')
    need(all(admission[k] is True for k in ('original_replay_verified','source_runtime_verified','resource_verified')),'parent_gate')
    need(admission['scorer_mode'] in ('original','reviewed_optional') and type(admission['scorer_binding']) is str and 1<=len(admission['scorer_binding'])<=128 and type(admission['optional_scorer_verified']) is bool,'scorer_binding')
    if admission['scorer_mode']=='reviewed_optional':need(admission['optional_scorer_verified'],'optional_scorer_gate')
    capacity=admission['capacity'];need(type(capacity) is dict and set(capacity)=={'counts','nonzero_TRAIN_probe_gradient_degrees'},'capacity')
    for counts in capacity.values():
        need(type(counts) is dict and set(counts)==set(ARMS) and all(type(v) is int and v>0 for v in counts.values()) and max(counts.values())/min(counts.values())<=1.05,'capacity')
    need(capacity['counts']=={'B':5007,'F':5147,'H':5125,'T':5125,'C':5125},'capacity')
    return capacity


def begin_stage(seed,arm,stage,claim,admission,processing_begin,experiment_begin):
    identity(seed,arm,stage=='training');capacity=admission_checked(admission)
    tick(processing_begin,experiment_begin,300 if stage=='training' else 900)
    need(claim(seed,arm,stage) is True,'claim_denied')
    return capacity


def prepare(packet,deps):
    p,t=deps.pilot,deps.torch
    need(tuple(p.SEEDS)==SEEDS and tuple(p.ARMS)==ARMS and tuple(p.HORIZONS)==HORIZONS and p.UPDATES==300,'candidate_contract')
    roles=p.validate(packet);stats=p.scaler(packet,roles['TRAIN'])
    t.set_num_threads(1);t.use_deterministic_algorithms(True)
    need(not t.cuda.is_initialized(),'CUDA_initialized')
    labels_train=np.asarray([packet['rows'][i]['mw'] for i in roles['TRAIN']])
    return roles,stats,float(labels_train.mean()),float(labels_train.std(ddof=0))


def fit_record(seed,arm,mean,std,history=None):
    return dict(seed=seed,arm=arm,mref=mean,train_population_std=std,status='incomplete',history=[] if history is None else history,predictions=[],numerical_failures=[],metrics={})


def failure(fit,error,stage):
    fit.update(status='incomplete',reason=stage+'_incomplete',exception_type=type(error).__name__,exception_reason=str(error)[:128])


def state_arrays(net):
    return {k:v.detach().cpu().numpy() for k,v in net.state_dict().items()}


def retained_checkpoint(checkpoint,seed,arm,net,stats,attempted,saved):
    if saved:return dict(status='already_saved_final')
    if net is None:return dict(status='unavailable_before_model')
    if attempted:return dict(status='checkpoint_callback_failed')
    try:
        checkpoint(seed,arm,state_arrays(net),stats)
        return dict(status='saved_failed_fit')
    except Exception as error:return dict(status='checkpoint_callback_failed',exception_type=type(error).__name__)


def train_stage(packet,seed,arm,deps,claim,checkpoint,history=None,*,admission,processing_begin,experiment_begin):
    result=dict(status='incomplete',stage='training',seed=seed,arm=arm,fit_authorized=False)
    net=None;stats=None;attempted=saved=False;fit=None
    try:
        result['capacity']=begin_stage(seed,arm,'training',claim,admission,processing_begin,experiment_begin)
        result['scorer_binding']=admission['scorer_binding']
        roles,stats,mean,std=prepare(packet,deps);fit=fit_record(seed,arm,mean,std);result['fit']=fit
        torch=deps.torch;p=deps.pilot;Net=deps.models.Net;nll=deps.models.nll
        check=lambda:tick(processing_begin,experiment_begin,300)
        begin=time.monotonic();check();torch.manual_seed(seed);net=Net(arm,mean);net.initialize(mean,std);optimizer=torch.optim.Adam(net.parameters(),lr=1e-3,weight_decay=0)
        # The update block below is the original V2 loop, only tick/batch aliases change.
        for update,ids in enumerate(p.event_order(roles['TRAIN'],seed),1):
            check();optimizer.zero_grad();labels=torch.tensor([packet['rows'][int(i)]['mw'] for i in ids],dtype=torch.float32)
            sequence=torch.zeros(8)
            if arm in ('C','H','T'):
                w,a,c,m=p.batch(packet,ids,stats,True);raw,z=net.initial(w,a,c,m);states,mask=p.state_batch(packet,ids,5)
                base=nll(labels,raw);sequence=-net.hazards.likelihood(labels,z,c,states,mask);loss=(base+sequence).mean()
            else:
                base=torch.stack([nll(labels,net.current(*p.batch(packet,ids,stats,False,h,arm=='F'))) for h in HORIZONS],1).mean(1);loss=base.mean()
            if not torch.isfinite(loss):raise RuntimeError('loss_nonfinite')
            base_grad=torch.autograd.grad(base.mean(),tuple(net.parameters()),retain_graph=True,allow_unused=True)
            base_norm=math.sqrt(sum(float((g*g).sum()) for g in base_grad if g is not None))
            if arm in ('C','H','T'):
                sequence_grad=torch.autograd.grad(sequence.mean(),tuple(net.parameters()),retain_graph=True,allow_unused=True)
                sequence_norm=math.sqrt(sum(float((g*g).sum()) for g in sequence_grad if g is not None))
            else:sequence_norm=0.
            loss.backward();norm=torch.nn.utils.clip_grad_norm_(net.parameters(),5)
            if not torch.isfinite(norm):raise RuntimeError('gradient_nonfinite')
            optimizer.step();item=dict(update=update,base_nll=float(base.mean().detach()),sequence_nll=float(sequence.mean().detach()),joint_or_conditional_nll=float(loss.detach()),gradient_norm=float(norm),base_gradient_norm=base_norm,sequence_gradient_norm=sequence_norm,seconds=time.monotonic()-begin)
            fit['history'].append(item)
            if history is not None:history(seed,arm,item)
            check()
        need(len(fit['history'])==300,'update_count')
        attempted=True;checkpoint(seed,arm,state_arrays(net),stats);saved=True
        check();fit['status']='trained';result['status']='trained'
    except Exception as error:
        if fit is not None:
            fit['failure_checkpoint']=retained_checkpoint(checkpoint,seed,arm,net,stats,attempted,saved);failure(fit,error,'training')
        result.update(reason='training_incomplete',exception_type=type(error).__name__,exception_reason=str(error)[:128])
    return result


def history_checked(items):
    need(type(items) is list and len(items)==300,'history')
    for i,item in enumerate(items,1):
        need(type(item) is dict and set(item)==HISTORY_KEYS and type(item['update']) is int and item['update']==i,'history')
        need(all(type(v) in (int,float) and math.isfinite(v) for k,v in item.items() if k!='update'),'history')
        need(item['seconds']>=0,'history')


def anchor_checked(anchor,seed,arm,net,stats,mean,std,torch):
    keys={'schema','seed','arm','kind','state','scalers','history','mref','train_population_std','retained_predictions'}
    need(type(anchor) is dict and set(anchor)==keys and anchor['schema']=='receiver-final-anchor-v3' and type(anchor['seed']) is int and anchor['seed']==seed and anchor['arm']==arm,'anchor')
    need(anchor['kind']==('original_final' if (seed,arm) in ORIGINAL else 'v3_final'),'anchor_kind')
    need(type(anchor['mref']) in (int,float) and anchor['mref']==mean and type(anchor['train_population_std']) in (int,float) and anchor['train_population_std']==std,'anchor_labels')
    history_checked(anchor['history'])
    expected_predictions=(66 if arm in ('B','F') else 46) if (seed,arm) in ORIGINAL else 0
    need(type(anchor['retained_predictions']) is list and len(anchor['retained_predictions'])==expected_predictions,'anchor_predictions')
    scalers=anchor['scalers'];need(type(scalers) is dict and set(scalers)==set(stats),'anchor_scalers')
    for k,v in stats.items():
        a=scalers[k];need(type(a) is np.ndarray and a.dtype==np.float64 and a.shape==v.shape and np.isfinite(a).all() and np.array_equal(a,v),'anchor_scalers')
    state=anchor['state'];expected=net.state_dict();need(type(state) is dict and set(state)==set(expected) and len(state)<=256,'anchor_state')
    count=size=0
    for k,value in state.items():
        need(type(value) is np.ndarray and value.dtype==np.float32 and value.shape==tuple(expected[k].shape) and np.isfinite(value).all(),'anchor_state')
        count+=value.size;size+=value.nbytes
    need(count<=100000 and size<=1024*1024,'anchor_state_cap')
    net.load_state_dict({k:torch.from_numpy(v.copy()) for k,v in state.items()},strict=True)


def finite_record(value):
    remaining=4096
    def visit(item,depth):
        nonlocal remaining
        remaining-=1;need(remaining>=0 and depth<=16,'numerical_cap')
        if type(item) in (int,float):need(math.isfinite(item),'numerical_nonfinite')
        elif type(item) is str:need(len(item)<=128,'numerical_text')
        elif type(item) is bool or item is None:return
        elif type(item) is list:
            for child in item:visit(child,depth+1)
        elif type(item) is dict:
            need(all(type(k) is str and len(k)<=128 for k in item),'numerical_schema')
            for child in item.values():visit(child,depth+1)
        else:raise ValueError('numerical_schema')
    visit(value,0)


def score_checked(score,numerics,initial):
    need(type(score) is dict and set(score)==({'mean','median','nll','crps','pit','coverage_50','coverage_80','coverage_95'}|({'quantiles'} if initial else set())),'score_schema')
    need(all(type(score[k]) in (int,float) and math.isfinite(score[k]) for k in ('mean','median','nll','crps','pit')) and score['crps']>=-1e-8 and 0<=score['pit']<=1,'score_nonfinite')
    need(all(type(score['coverage_'+str(k)]) is bool for k in (50,80,95)),'score_coverage')
    finite_record(numerics)
    if initial:
        need(type(numerics) is dict and set(numerics)=={'accepted','errors','torch_errors','base_raw','z','c','states','hazard','mref','integrals'} and numerics.get('accepted') is True,'numerical_rejected')
        for key,expected in (('errors',{'log_normalizer','mean','nll'}),('torch_errors',{'64','128'})):
            values=numerics.get(key);need(type(values) is dict and set(values)==expected and all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1e-4 for v in values.values()),'numerical_parity')
        def vector(value,n):
            need(type(value) is list and len(value)==n and all(type(v) in (int,float) and math.isfinite(v) for v in value),'numerical_shape')
        for key,n in (('base_raw',15),('z',36),('c',35)):vector(numerics[key],n)
        states=numerics['states'];need(type(states) is list and 1<=len(states)<=20 and all(type(v) is int and v in (0,1) for v in states),'numerical_states')
        hazard=numerics['hazard'];need(type(hazard) is dict and set(hazard)=={'alpha','beta','z_weights','c_weights','gamma','extra'},'numerical_hazard')
        for key in ('alpha','beta','gamma','extra'):vector(hazard[key],2)
        for key,n in (('z_weights',36),('c_weights',35)):
            need(type(hazard[key]) is list and len(hazard[key])==2,'numerical_hazard')
            for row in hazard[key]:vector(row,n)
        integrals=numerics['integrals'];need(type(integrals) is dict and set(integrals)=={'gh64','gh128','adaptive'},'numerical_integrals')
        for key,method in (('gh64','GH64'),('gh128','GH128'),('adaptive','adaptive')):
            item=integrals[key];need(type(item) is dict and set(item)=={'method','log_normalizer','mean','nll'} and item['method']==method and all(type(item[k]) in (int,float) and math.isfinite(item[k]) for k in ('log_normalizer','mean','nll')),'numerical_integrals')
        need(type(numerics['mref']) in (int,float) and math.isfinite(numerics['mref']),'numerical_mref')
        q=score['quantiles'];need(type(q) is dict and list(q)==['0.025','0.1','0.25','0.5','0.75','0.9','0.975'] and all(type(v) in (int,float) and math.isfinite(v) for v in q.values()) and list(q.values())==sorted(q.values()),'score_quantiles')


def diagnostic_raw(raw):
    values=raw[0].detach().cpu().double().tolist()
    return [v if math.isfinite(v) else 'NaN' if math.isnan(v) else '+Infinity' if v>0 else '-Infinity' for v in values]


def score_stage(packet,seed,arm,deps,claim,read_anchor,prediction=None,scorer=None,*,admission,processing_begin,experiment_begin):
    result=dict(status='incomplete',stage='scoring',seed=seed,arm=arm,fit_authorized=False);fit=None
    try:
        result['capacity']=begin_stage(seed,arm,'scoring',claim,admission,processing_begin,experiment_begin);result['scorer_binding']=admission['scorer_binding']
        need((scorer is None)==(admission['scorer_mode']=='original'),'scorer_authority')
        roles,stats,mean,std=prepare(packet,deps);p=deps.pilot;torch=deps.torch;check=lambda:tick(processing_begin,experiment_begin,900)
        check();anchor=read_anchor(seed,arm);torch.manual_seed(seed);net=deps.models.Net(arm,mean)
        anchor_checked(anchor,seed,arm,net,stats,mean,std,torch)
        fit=fit_record(seed,arm,mean,std,anchor['history']);result['fit']=fit;result['retained_anchor_predictions']=anchor['retained_predictions'];net.eval()
        evaluate=p.numerical if scorer is None else scorer
        with torch.no_grad():
            for ordinal in roles['DEV']:
                target=float(packet['rows'][ordinal]['mw'])
                for h in HORIZONS:
                    check();initial=arm in ('C','H','T');args=p.batch(packet,[ordinal],stats,initial,None if initial else h,arm=='F')
                    if initial:
                        raw,z=net.initial(*args);states,mask=p.state_batch(packet,[ordinal],h)
                        try:score,numerics=evaluate(net,raw,z,args[2],states,mask,target,check)
                        except Exception as error:
                            fit['numerical_failures'].append(dict(ordinal=ordinal,horizon=h,accepted=False,reason=str(error)[:128],exception_type=type(error).__name__,base_raw=diagnostic_raw(raw),states=states[0,mask[0]].cpu().tolist()));raise
                        if score is None:
                            fit['numerical_failures'].append(dict(ordinal=ordinal,horizon=h,**numerics));raise p.core.NumericalFailure('quadrature_parity')
                    else:
                        raw=net.current(*args)
                        try:
                            mix=p.core.Mixture.from_raw(raw[0].cpu().double().numpy());weights,means,sigmas=(x.tolist() for x in (mix.weights,mix.means,mix.sigmas));numerics={'pi':weights,'mu':means,'sigma':sigmas};density=p.density
                            score=dict(mean=density.mean_action(weights,means),median=density.quantile(.5,weights,means,sigmas),nll=density.nll(target,weights,means,sigmas),crps=density.crps(target,weights,means,sigmas),pit=density.cdf(target,weights,means,sigmas))
                            for level in (.5,.8,.95):
                                tail=(1-level)/2;score['coverage_'+str(round(level*100))]=density.quantile(tail,weights,means,sigmas)<=target<=density.quantile(1-tail,weights,means,sigmas)
                        except Exception as error:
                            fit['numerical_failures'].append(dict(ordinal=ordinal,horizon=h,accepted=False,reason=str(error)[:128],exception_type=type(error).__name__,base_raw=diagnostic_raw(raw)));raise
                    try:score_checked(score,numerics,initial)
                    except Exception:
                        fit['numerical_failures'].append(dict(ordinal=ordinal,horizon=h,accepted=False,reason='score_contract',numerical=numerics));raise
                    item=dict(ordinal=ordinal,horizon=h,target=target,group=packet['rows'][ordinal]['group'],family='ENZ' if packet['rows'][ordinal]['initial']['context'][15]==1 else '12Z',receiver=packet['rows'][ordinal]['initial']['context'][9:12].tolist(),rate=packet['rows'][ordinal]['horizons'][HORIZONS.index(h)]['rate'],numerical=numerics,**score)
                    fit['predictions'].append(item)
                    if prediction is not None:prediction(seed,arm,item)
                    check()
        need(len(fit['predictions'])==66,'prediction_count')
        fit['metrics']={str(h):p.metrics([v for v in fit['predictions'] if v['horizon']==h]) for h in HORIZONS};fit['strata']={str(h):p.strata([v for v in fit['predictions'] if v['horizon']==h]) for h in HORIZONS};fit['extreme_cases']=[v for v in fit['predictions'] if v['target']>=7]
        check();fit['status']='complete';result['status']='complete'
    except Exception as error:
        if fit is not None:failure(fit,error,'scoring')
        result.update(reason='scoring_incomplete',exception_type=type(error).__name__,exception_reason=str(error)[:128])
    return result


def aggregate(packet,stage_results,deps,*,admission,processing_begin,experiment_begin):
    result=dict(status='incomplete',fits=[],comparisons=[],retained_stage_results=stage_results,advance=dict(pass_all=False,checks=[]),fit_authorized=False)
    try:
        capacity=admission_checked(admission);result['capacity']=capacity;result['scorer_binding']=admission['scorer_binding']
        check=lambda:tick(processing_begin,experiment_begin,900);check();roles,stats,mean,std=prepare(packet,deps);p=deps.pilot
        need(type(stage_results) is list and len(stage_results)==10,'aggregate_count')
        for stage,wanted in zip(stage_results,IDENTITIES):
            check();need(type(stage) is dict and stage.get('status')=='complete' and stage.get('stage')=='scoring' and (stage.get('seed'),stage.get('arm'))==wanted and stage.get('capacity')==capacity and stage.get('scorer_binding')==admission['scorer_binding'],'aggregate_stage')
            fit=stage['fit'];need(fit['status']=='complete' and (fit['seed'],fit['arm'])==wanted and fit['mref']==mean and fit['train_population_std']==std and not fit['numerical_failures'],'aggregate_fit');history_checked(fit['history'])
            predictions=fit['predictions'];need(type(predictions) is list and len(predictions)==66,'aggregate_predictions')
            for item,(ordinal,h) in zip(predictions,((i,h) for i in roles['DEV'] for h in HORIZONS)):
                row=packet['rows'][ordinal];need(item['ordinal']==ordinal and item['horizon']==h and item['target']==row['mw'] and item['group']==row['group'] and item['rate']==row['horizons'][HORIZONS.index(h)]['rate'] and item['receiver']==row['initial']['context'][9:12].tolist() and item['family']==('ENZ' if row['initial']['context'][15]==1 else '12Z'),'aggregate_binding');score={k:v for k,v in item.items() if k not in ('ordinal','horizon','target','group','family','receiver','rate','numerical')};score_checked(score,item['numerical'],wanted[1] in ('C','H','T'))
            retained=dict(fit);retained['metrics']={str(h):p.metrics([v for v in predictions if v['horizon']==h]) for h in HORIZONS};retained['strata']={str(h):p.strata([v for v in predictions if v['horizon']==h]) for h in HORIZONS};retained['extreme_cases']=[v for v in predictions if v['target']>=7];result['fits'].append(retained)
        for seed in SEEDS:
            by={f['arm']:f for f in result['fits'] if f['seed']==seed}
            for h in HORIZONS:
                for other in ('B','F','H','T'):
                    check();result['comparisons'].append(dict(seed=seed,horizon=h,comparator=other,intervals=p.paired_intervals([v for v in by['C']['predictions'] if v['horizon']==h],[v for v in by[other]['predictions'] if v['horizon']==h],check)))
        result['diagnostics']=p.diagnostics(packet);result['advance']=p.advance(result['fits']);result['status']='complete'
        if len(p.observations.canonical(result))>16*1024*1024:raise RuntimeError('private_result_cap')
        public={'status':result['status'],'capacity':capacity,'advance':result['advance'],'metrics':[dict(seed=f['seed'],arm=f['arm'],metrics=f['metrics']) for f in result['fits']],'diagnostics':result['diagnostics']}
        if len(p.observations.canonical(public))>64*1024:raise RuntimeError('public_result_cap')
        check()
    except Exception as error:
        result.update(status='incomplete',reason='aggregation_incomplete',exception_type=type(error).__name__,exception_reason=str(error)[:128],advance=dict(pass_all=False,checks=[]),bounded_export=False)
    return result

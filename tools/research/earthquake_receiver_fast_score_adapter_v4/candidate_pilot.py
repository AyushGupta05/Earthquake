"""One prospective ten-fit comparison; pure callback API, never invoked by tests."""
import math
import time
import numpy as np
import observations
import numerical_core as core
import mixture_density as density
import posterior_scores

SEEDS=(20261012,20261013)
ARMS=('B','F','H','T','C')
HORIZONS=(1,3,5)
UPDATES=300
INITIAL_CONTINUOUS=(0,1,2,7,8,9,10,11,17,18,19)


def deadline(begin,fit_begin=None):
    now=time.monotonic()
    if type(begin) not in (int,float) or not math.isfinite(begin) or not 0<=begin<=now or now-begin>3300 or fit_begin is not None and now-fit_begin>300:raise RuntimeError('renewal_deadline')


def validate(packet):
    need=observations.need
    need(type(packet) is dict and set(packet)=={'schema','study','rows','denominators','observed_samples','input_pins','fit_authorized'}
         and packet['schema']==observations.SCHEMA and packet['study']==observations.STUDY and packet['fit_authorized'] is False,'packet')
    need(type(packet['rows']) is list and len(packet['rows'])==115 and packet['denominators']==dict(events=115,cells=345,train=91,dev=24,test_excluded=31),'packet_denominator')
    need(observations.new_native._keys(packet['observed_samples'],('old','new')) and all(type(v) is int and v>=0 for v in packet['observed_samples'].values())
         and packet['observed_samples']['old']<=136_000_000 and packet['observed_samples']['new']<=104_000_000,'packet_observation_budget')
    need(observations.new_native._keys(packet['input_pins'],('old_plan','old_qualified','new_plan','new_qualified','metadata','roster')),'packet_input_pins')
    for key,pin in packet['input_pins'].items():
        need(observations.new_native._keys(pin,('bytes','sha256')) and type(pin['bytes']) is int and 0<=pin['bytes']<=64*1024*1024 and observations.new_native._sha(pin['sha256']),'packet_input_pins')
    roles={'TRAIN':[],'DEV':[]};total=0
    for i,row in enumerate(packet['rows']):
        need(type(row) is dict and set(row)=={'ordinal','partition','mw','group','common','status','initial','horizons'}
             and type(row['ordinal']) is int and row['ordinal']==i and type(row['partition']) is str and row['partition'] in roles
             and type(row['mw']) in (int,float) and math.isfinite(row['mw']) and -5<=row['mw']<=15
             and type(row['group']) is int and -1<=row['group']<=i and type(row['common']) is bool,'packet_row')
        need(type(row['horizons']) is list and len(row['horizons'])==3,'packet_horizons')
        if not row['common']:
            need(row['status']=='unavailable' and row['initial'] is None and row['horizons']==[dict(seconds=h,status='unavailable') for h in HORIZONS],'packet_unavailable');continue
        need(row['status']=='available' and row['group']>=0,'packet_eligible');roles[row['partition']].append(i)
        for j,item in enumerate([row['initial']]+row['horizons']):
            names={'wave','amplitude','context'} if j==0 else {'seconds','rate','wave','amplitude','context','ratios','states','run_ages'}
            need(type(item) is dict and set(item)==names,'observation_fields')
            wave,amp,ctx=(item[k] for k in ('wave','amplitude','context'))
            need(type(wave) is np.ndarray and wave.dtype==np.float32 and wave.ndim==2 and wave.shape[0]==3 and wave.shape[1]>0 and wave.flags.c_contiguous,'wave_shape')
            need(type(amp) is np.ndarray and amp.dtype==np.float32 and amp.shape==(4,) and type(ctx) is np.ndarray and ctx.dtype==np.float64 and ctx.shape==((35,) if j==0 else (36,)),'feature_shape')
            need(np.isfinite(wave).all() and np.max(np.abs(wave))<=1.0000001 and np.isfinite(amp).all() and np.isfinite(ctx).all(),'observation_nonfinite');total+=wave.size
            if j:
                h=HORIZONS[j-1];need(type(item['seconds']) is int and item['seconds']==h,'horizon_order');newrate=observations.new_native._rational(item['rate']);need(abs(float(ctx[9])-math.log10(float(newrate)))<=1e-12,'rate_binding')
                ratios=item['ratios'];states=item['states'];ages=item['run_ages']
                need(type(ratios) is list and 4*h-3<=len(ratios)<=4*h and all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1e25 for x in ratios),'activity_ratios')
                expected=core.transitions(states)
                calculated=observations.am._sequence(ratios)
                need(type(states) is list and all(type(x) is int for x in states) and states==calculated[0] and ages==calculated[1] and row['initial']['context'][6]==float(states[0]),'activity_sequence')
                need(np.array_equal(ctx[:7],row['initial']['context'][:7]) and np.array_equal(ctx[8:],row['initial']['context'][7:]),'static_context_invariance')
        for a,b in zip(row['horizons'],row['horizons'][1:]):
            need(b['ratios'][:len(a['ratios'])]==a['ratios'] and len(b['ratios'])-len(a['ratios'])==8,'activity_prefix')
    need(total<=observations.MAX_ELEMENTS and len(roles['TRAIN'])==65 and len(roles['DEV'])==22,'packet_common')
    need(sum(r['partition']=='TRAIN' for r in packet['rows'])==91 and sum(r['partition']=='DEV' for r in packet['rows'])==24,'packet_partition')
    need(not ({packet['rows'][i]['group'] for i in roles['TRAIN']}&{packet['rows'][i]['group'] for i in roles['DEV']}),'packet_mixed')
    return roles


def scaler(packet,train):
    initial=np.asarray([packet['rows'][i]['initial']['context'] for i in train]);current=np.asarray([packet['rows'][i]['horizons'][j]['context'] for i in train for j in range(3)])
    mean=np.zeros(35);std=np.ones(35);current_mean=np.zeros(36);current_std=np.ones(36)
    for k in INITIAL_CONTINUOUS:
        mean[k]=initial[:,k].mean();std[k]=initial[:,k].std(ddof=0)
    for k in range(35):
        j=k if k<7 else k+1;current_mean[j]=mean[k];current_std[j]=std[k]
    for k in (7,):current_mean[k]=current[:,k].mean();current_std[k]=current[:,k].std(ddof=0)
    return {'initial_mean':mean,'initial_std':std,'current_mean':current_mean,'current_std':current_std}


def standardized(ctx,stats,initial):
    key='initial' if initial else 'current';mean=stats[key+'_mean'];std=stats[key+'_std']
    return np.asarray(np.divide(ctx-mean,std,out=np.zeros_like(ctx),where=std>0),dtype=np.float32)


def batch(packet,ids,stats,initial,horizon=None,features=False):
    import torch
    items=[packet['rows'][int(i)]['initial'] if initial else packet['rows'][int(i)]['horizons'][HORIZONS.index(horizon)] for i in ids]
    lengths=[x['wave'].shape[1] for x in items]
    if len(ids)*3*max(lengths)>20_000_000:raise RuntimeError('padded_batch_cap')
    wave=torch.zeros(len(ids),3,max(lengths));mask=torch.zeros(len(ids),max(lengths),dtype=torch.bool)
    for k,(item,n) in enumerate(zip(items,lengths)):wave[k,:,:n]=torch.from_numpy(item['wave']);mask[k,:n]=True
    amp=torch.from_numpy(np.asarray([x['amplitude'] for x in items],dtype=np.float32));ctx=torch.from_numpy(np.asarray([standardized(x['context'],stats,initial) for x in items],dtype=np.float32))
    if not features:return wave,amp,ctx,mask
    activity=torch.zeros(len(ids),5,20);valid=torch.zeros(len(ids),20,dtype=torch.bool)
    for k,item in enumerate(items):
        n=len(item['states']);r=np.log1p(item['run_ages']);b=np.asarray(item['states'])
        activity[k,:,:n]=torch.from_numpy(np.asarray([np.log1p(item['ratios']),b,r,.25*np.arange(n),b*r],dtype=np.float32));valid[k,:n]=True
    return wave,amp,ctx,mask,activity,valid


def state_batch(packet,ids,horizon):
    import torch
    items=[packet['rows'][int(i)]['horizons'][HORIZONS.index(horizon)]['states'] for i in ids]
    states=torch.zeros(len(ids),20,dtype=torch.int64);mask=torch.zeros(len(ids),20,dtype=torch.bool)
    for k,s in enumerate(items):states[k,:len(s)]=torch.tensor(s);mask[k,:len(s)]=True
    return states,mask


def event_order(train,seed):
    rng=np.random.default_rng(seed+1009)
    for _ in range(UPDATES):yield rng.choice(train,8,replace=False)


def metrics(predictions):
    y=np.asarray([p['target'] for p in predictions]);e=np.asarray([p['mean'] for p in predictions])-y;a=np.abs(e);hi=y>=5.5;higher=y>=6;lo=y<5.5
    out=dict(n=len(y),nll=float(np.mean([p['nll'] for p in predictions])),crps=float(np.mean([p['crps'] for p in predictions])),mae=float(a.mean()),medae=float(np.median(a)),
             tail_mae_5_5=float(a[hi].mean()) if hi.any() else None,tail_mae_6=float(a[higher].mean()) if higher.any() else None,
             lower_mae=float(a[lo].mean()) if lo.any() else None,lower_medae=float(np.median(a[lo])) if lo.any() else None,
             tail_bias=float(e[hi].mean()) if hi.any() else None,cvar95=float(np.sort(a)[-max(1,math.ceil(.05*len(y))):].mean()),
             maximum=float(a.max()),p95=float(np.quantile(a,.95,method='linear')),median_mae=float(np.mean([abs(p['median']-p['target']) for p in predictions])))
    for level in (50,80,95):out['coverage_'+str(level)]=float(np.mean([p['coverage_'+str(level)] for p in predictions]))
    return out


def advance(fits):
    checks=[]
    if len(fits)!=10 or any(f['status']!='complete' for f in fits):return dict(pass_all=False,checks=checks)
    for seed in SEEDS:
        selected=[f for f in fits if f['seed']==seed]
        if len(selected)!=5 or {f['arm'] for f in selected}!=set(ARMS):return dict(pass_all=False,checks=checks)
        by={f['arm']:f for f in selected}
        for h in HORIZONS:
            candidate=by['C']['metrics'][str(h)]
            for other in ('B','F','H','T'):
                baseline=by[other]['metrics'][str(h)]
                tail=candidate['tail_mae_5_5'] is not None and baseline['tail_mae_5_5'] is not None and baseline['tail_mae_5_5']-candidate['tail_mae_5_5']>=.02
                guard={k:candidate[k] is not None and baseline[k] is not None and candidate[k]<=baseline[k] for k in ('mae','medae','lower_mae','lower_medae','cvar95','maximum')}
                proper=other in ('H','T') or candidate['nll']<baseline['nll'] and candidate['crps']<baseline['crps']
                checks.append(dict(seed=seed,horizon=h,comparator=other,tail=tail,proper=proper,bulk_worst=guard,passed=tail and proper and all(guard.values())))
    return dict(pass_all=all(c['passed'] for c in checks),checks=checks)


def strata(predictions):
    return {'families':[{ 'family':g,'metrics':metrics([p for p in predictions if p['family']==g]) } for g in sorted({p['family'] for p in predictions})],
            'receivers':[{ 'receiver':list(g),'metrics':metrics([p for p in predictions if tuple(p['receiver'])==g]) } for g in sorted({tuple(p['receiver']) for p in predictions})],
            'groups':[{ 'group':g,'metrics':metrics([p for p in predictions if p['group']==g]) } for g in sorted({p['group'] for p in predictions})],
            'rates':[{ 'rate':list(r),'metrics':metrics([p for p in predictions if tuple(p['rate'])==r]) } for r in sorted({tuple(p['rate']) for p in predictions})]}


def diagnostics(packet):
    out={}
    for partition in ('TRAIN','DEV'):
        rows=[r for r in packet['rows'] if r['common'] and r['partition']==partition]
        out[partition]={'common':len(rows),'noise_floor_counts':[sum(bool(r['initial']['context'][j]) for r in rows) for j in (3,4,5)],
                        'horizons':{str(h):{'off':sum(sum(a==1 and b==0 for a,b in zip(r['horizons'][k]['states'],r['horizons'][k]['states'][1:])) for r in rows),
                                            'on':sum(sum(a==0 and b==1 for a,b in zip(r['horizons'][k]['states'],r['horizons'][k]['states'][1:])) for r in rows),
                                            'active_censored':sum(r['horizons'][k]['states'][-1]==1 for r in rows)} for k,h in enumerate(HORIZONS)}}
    out['denominators']=packet['denominators'];out['unavailable_events']=sum(not r['common'] for r in packet['rows']);out['old_events']=65;out['new_events']=50
    return out


def paired_intervals(left,right,tick):
    if [(p['ordinal'],p['target'],p['group']) for p in left]!=[(p['ordinal'],p['target'],p['group']) for p in right]:raise ValueError('comparison_pairing')
    a,b=metrics(left),metrics(right);groups=sorted({p['group'] for p in left});support={};draws={}
    for k in a:
        if k=='n':continue
        subset=[p for p in left if (p['target']>=5.5 if k in ('tail_mae_5_5','tail_bias') else p['target']>=6 if k=='tail_mae_6' else p['target']<5.5 if k in ('lower_mae','lower_medae') else True)]
        support[k]=len({p['group'] for p in subset})
        if support[k]>=3:draws[k]=[]
    rng=np.random.default_rng(9919)
    for _ in range(1000):
        tick();selected=rng.choice(groups,len(groups),replace=True);indices=[i for g in selected for i,p in enumerate(left) if p['group']==g]
        sa,sb=metrics([left[i] for i in indices]),metrics([right[i] for i in indices])
        for k in draws:
            if sa[k] is not None and sb[k] is not None:draws[k].append(sa[k]-sb[k])
    return {k:dict(status='descriptive' if support[k]>=3 and len(draws[k])==1000 else 'unsupported',groups=support[k],delta=a[k]-b[k] if a[k] is not None and b[k] is not None else None,
                   interval=[float(x) for x in np.quantile(draws[k],[.025,.975])] if support[k]>=3 and len(draws[k])==1000 else None) for k in support}


def numerical(net,raw,z,ctx,states,mask,target,tick):
    import torch
    from models import torch_gh
    mixture=core.Mixture.from_raw(raw[0].detach().cpu().double().numpy());h=net.hazards
    hazard=core.Hazard(net.arm,*[getattr(h,k).detach().cpu().double().numpy() for k in ('alpha','beta','z_weights','c_weights','gamma','extra')],h.mref)
    zv=z[0].detach().cpu().double().numpy();cv=ctx[0].detach().cpu().double().numpy();sv=states[0,mask[0]].cpu().tolist()
    tick()
    try:checked=core.checked_inference(mixture,hazard,zv,cv,sv,target)
    except Exception as error:raise core.NumericalFailure('core_'+type(error).__name__) from None
    tick()
    torch_errors={}
    for order in (64,128):
        logz,mean=torch_gh(raw,h,z,ctx,states,mask,order);reference=checked['gh'+str(order)]
        torch_errors[str(order)]=max(abs(float(logz[0])-reference.log_normalizer),abs(float(mean[0])-reference.mean))
    accepted=checked['accepted'] and all(x<=1e-4 for x in torch_errors.values())
    record=dict(accepted=accepted,errors=checked['errors'],torch_errors=torch_errors,base_raw=raw[0].detach().cpu().double().tolist(),z=zv.tolist(),c=cv.tolist(),states=sv,
                hazard={k:getattr(hazard,k).tolist() for k in ('alpha','beta','z_weights','c_weights','gamma','extra')},mref=hazard.mref,
                integrals={k:vars(checked[k]) for k in ('gh64','gh128','adaptive')})
    if not accepted:return None,record
    try:score=posterior_scores.scores(mixture,hazard,zv,cv,sv,target,checked,tick)
    except Exception as error:
        if isinstance(error,RuntimeError) and str(error)=='renewal_deadline':raise
        raise core.NumericalFailure('proper_score_'+type(error).__name__) from None
    return score,record


def capacity_probe(packet,roles,stats):
    """TRAIN-only structural/effective checks; no optimizer, label tuning or selection."""
    import torch
    from models import Net,parameter_counts,nll
    counts=parameter_counts();mean=float(np.mean([packet['rows'][i]['mw'] for i in roles['TRAIN']]))
    ids=roles['TRAIN'] # Fixed full TRAIN set, never search for favorable gradient examples.
    degrees={}
    for arm in ARMS:
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(8173);net=Net(arm,mean)
            labels=torch.tensor([packet['rows'][i]['mw'] for i in ids],dtype=torch.float32)
            if arm in ('C','H','T'):
                w,a,c,m=batch(packet,ids,stats,True);raw,z=net.initial(w,a,c,m);states,mask=state_batch(packet,ids,5)
                if arm=='H' and (not torch.any(z[:,0]*z[:,1]!=0) or not torch.any(z[:,0]*c[:,0]!=0)):raise ValueError('H_replacement_ineffective')
                loss=(nll(labels,raw)-net.hazards.likelihood(labels,z,c,states,mask)).mean()
            else:
                args=batch(packet,ids,stats,False,5,arm=='F');raw=net.current(*args);loss=nll(labels,raw).mean()
            loss.backward()
            used=sum(int(torch.count_nonzero(p.grad)) for p in net.parameters() if p.grad is not None)
            if any(p.grad is None for p in net.parameters()):raise ValueError('unused_parameter_tensor')
            degrees[arm]=used
    if max(degrees.values())/min(degrees.values())>1.05:raise ValueError('capacity_mismatch')
    return dict(counts=counts,nonzero_TRAIN_probe_gradient_degrees=degrees)


def retain_failure_checkpoint(checkpoint,seed,arm,net,stats,attempted,saved):
    # Diagnostic finalization only: no optimizer, inference, retry or replacement.
    if saved:return dict(status='already_saved_final')
    if net is None:return dict(status='unavailable_before_model')
    if attempted:return dict(status='checkpoint_callback_failed')
    try:
        state={k:v.detach().cpu().numpy() for k,v in net.state_dict().items()}
        checkpoint(seed,arm,state,stats)
        return dict(status='saved_failed_fit')
    except Exception as error:
        return dict(status='checkpoint_callback_failed',exception_type=type(error).__name__)


def run(packet,checkpoint,history=None,*,processing_begin):
    """Root actual source/runtime/scientific authority required; tests never call this."""
    deadline(processing_begin);roles=validate(packet);stats=scaler(packet,roles['TRAIN'])
    import torch
    from models import Net,nll
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    if torch.cuda.is_initialized():raise RuntimeError('CUDA_initialized')
    capacity=capacity_probe(packet,roles,stats);deadline(processing_begin)
    labels_train=np.asarray([packet['rows'][i]['mw'] for i in roles['TRAIN']]);mean=float(labels_train.mean());std=float(labels_train.std(ddof=0));fits=[]
    for seed in SEEDS:
        for arm in ARMS:
            net=None;checkpoint_attempted=False;checkpoint_saved=False
            begin=time.monotonic();fit=dict(seed=seed,arm=arm,mref=mean,train_population_std=std,status='incomplete',history=[],predictions=[],numerical_failures=[],metrics={});fits.append(fit)
            tick=lambda:deadline(processing_begin,begin)
            try:
                tick();torch.manual_seed(seed);net=Net(arm,mean);net.initialize(mean,std);optimizer=torch.optim.Adam(net.parameters(),lr=1e-3,weight_decay=0)
                for update,ids in enumerate(event_order(roles['TRAIN'],seed),1):
                    tick();optimizer.zero_grad();labels=torch.tensor([packet['rows'][int(i)]['mw'] for i in ids],dtype=torch.float32)
                    sequence=torch.zeros(8)
                    if arm in ('C','H','T'):
                        w,a,c,m=batch(packet,ids,stats,True);raw,z=net.initial(w,a,c,m);states,mask=state_batch(packet,ids,5)
                        base=nll(labels,raw);sequence=-net.hazards.likelihood(labels,z,c,states,mask);loss=(base+sequence).mean()
                    else:
                        base=torch.stack([nll(labels,net.current(*batch(packet,ids,stats,False,h,arm=='F'))) for h in HORIZONS],1).mean(1);loss=base.mean()
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
                    tick()
                checkpoint_attempted=True
                checkpoint(seed,arm,{k:v.detach().cpu().numpy() for k,v in net.state_dict().items()},stats);checkpoint_saved=True;net.eval()
                with torch.no_grad():
                    for ordinal in roles['DEV']:
                        target=float(packet['rows'][ordinal]['mw'])
                        for h in HORIZONS:
                            tick();initial=arm in ('C','H','T');args=batch(packet,[ordinal],stats,initial,None if initial else h,arm=='F')
                            if initial:
                                raw,z=net.initial(*args);states,mask=state_batch(packet,[ordinal],h)
                                try:score,numerics=numerical(net,raw,z,args[2],states,mask,target,tick)
                                except core.NumericalFailure as error:
                                    fit['numerical_failures'].append(dict(ordinal=ordinal,horizon=h,accepted=False,reason=str(error),base_raw=raw[0].cpu().double().tolist(),states=states[0,mask[0]].cpu().tolist()))
                                    raise
                                if score is None:
                                    fit['numerical_failures'].append(dict(ordinal=ordinal,horizon=h,**numerics));raise core.NumericalFailure('quadrature_parity')
                            else:
                                raw=net.current(*args);mix=core.Mixture.from_raw(raw[0].cpu().double().numpy());p,m,s=(x.tolist() for x in (mix.weights,mix.means,mix.sigmas));numerics={'pi':p,'mu':m,'sigma':s}
                                score=dict(mean=density.mean_action(p,m),median=density.quantile(.5,p,m,s),nll=density.nll(target,p,m,s),crps=density.crps(target,p,m,s),pit=density.cdf(target,p,m,s))
                                for level in (.5,.8,.95):
                                    tail=(1-level)/2;score['coverage_'+str(round(level*100))]=density.quantile(tail,p,m,s)<=target<=density.quantile(1-tail,p,m,s)
                            fit['predictions'].append(dict(ordinal=ordinal,horizon=h,target=target,group=packet['rows'][ordinal]['group'],family='ENZ' if packet['rows'][ordinal]['initial']['context'][15]==1 else '12Z',receiver=packet['rows'][ordinal]['initial']['context'][9:12].tolist(),rate=packet['rows'][ordinal]['horizons'][HORIZONS.index(h)]['rate'],numerical=numerics,**score))
                fit['metrics']={str(h):metrics([p for p in fit['predictions'] if p['horizon']==h]) for h in HORIZONS}
                fit['strata']={str(h):strata([p for p in fit['predictions'] if p['horizon']==h]) for h in HORIZONS}
                fit['extreme_cases']=[p for p in fit['predictions'] if p['target']>=7];tick();fit['status']='complete'
                del net,optimizer
            except Exception as failure:
                fit['failure_checkpoint']=retain_failure_checkpoint(checkpoint,seed,arm,net,stats,checkpoint_attempted,checkpoint_saved)
                fit['reason']='numerical_failure' if isinstance(failure,core.NumericalFailure) else 'fit_incomplete';fit['exception_type']=type(failure).__name__;fit['exception_reason']=str(failure)[:128]
                return dict(status='incomplete',fits=fits,capacity=capacity,advance=advance(fits),fit_authorized=False)
    comparisons=[]
    try:
        deadline(processing_begin)
        for seed in SEEDS:
            by={f['arm']:f for f in fits if f['seed']==seed}
            for h in HORIZONS:
                for other in ('B','F','H','T'):
                    deadline(processing_begin)
                    comparisons.append(dict(seed=seed,horizon=h,comparator=other,intervals=paired_intervals([p for p in by['C']['predictions'] if p['horizon']==h],[p for p in by[other]['predictions'] if p['horizon']==h],lambda:deadline(processing_begin))))
    except Exception as failure:
        return dict(status='incomplete',reason='comparison_incomplete',exception_type=type(failure).__name__,fits=fits,capacity=capacity,comparisons=comparisons,advance=dict(pass_all=False,checks=[]),fit_authorized=False)
    return finalize_result(packet,fits,capacity,comparisons,processing_begin)


def finalize_result(packet,fits,capacity,comparisons,processing_begin):
    # Preserve accumulated evidence even if bounded export or finalization fails.
    result=dict(status='incomplete',fits=fits,capacity=capacity,comparisons=comparisons,advance=dict(pass_all=False,checks=[]),fit_authorized=False)
    try:
        result['diagnostics']=diagnostics(packet)
        result['advance']=advance(fits);result['status']='complete'
        if len(observations.canonical(result))>16*1024*1024:raise RuntimeError('private_result_cap')
        public={'status':result['status'],'capacity':capacity,'advance':result['advance'],'metrics':[dict(seed=f['seed'],arm=f['arm'],metrics=f['metrics']) for f in fits],'diagnostics':result['diagnostics']}
        if len(observations.canonical(public))>64*1024:raise RuntimeError('public_result_cap')
        deadline(processing_begin)
    except Exception as failure:
        result.update(status='incomplete',reason='finalization_incomplete',exception_type=type(failure).__name__,exception_reason=str(failure)[:128],advance=dict(pass_all=False,checks=[]),bounded_export=False)
    return result

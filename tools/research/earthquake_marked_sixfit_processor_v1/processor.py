"""Fixed prospective S/P/D processor; injected source/data/custody, no IO."""
import copy
from dataclasses import dataclass
import hashlib
import math
import time
import numpy as np
import torch
import numeric_state as ns

SEEDS = (20261012, 20261013)
ARMS = ('S', 'P', 'D')
HORIZONS = (1, 3, 5)
ORDER = tuple((s, a) for s in SEEDS for a in ARMS)
UPDATES = 300
STUDY = 'earthquake-TRAIN115-marked-noise-fitting-v2'
KEEP = tuple(i for i in range(34) if i not in (15,25,29,33))
SUMMARY_NAMES = tuple(f'c{c}_{v}' for c in range(3) for v in ('latest','mean','max','time_slope','censor_fraction')) + ('log_duration','cells','nu_sd_0','nu_sd_1','nu_sd_2')


class Failure(ValueError):
    def __init__(self, reason, evidence=None):
        super().__init__(reason)
        self.evidence = evidence


def need(ok, why):
    if not ok:
        raise Failure(why)


def deadline(begin, seconds):
    need(type(begin) in (int,float) and math.isfinite(begin) and 0 <= begin <= time.monotonic(), 'processing_begin')
    need(time.monotonic()-begin <= seconds, 'source_deadline')


def runtime():
    need(torch.get_num_threads() == 1, 'one_cpu_thread_required')
    return dict(torch=str(torch.__version__), numpy=np.__version__, threads=torch.get_num_threads(), dtype='float64', device='cpu')


@dataclass(frozen=True)
class Bindings:
    operator: object
    native_validator: object
    reference: object
    source_pins: dict

    def validate(self):
        need(type(self.source_pins) is dict and set(self.source_pins) == {'operator','native_validator','reference','processor','protocol'}, 'source_pin_names')
        for p in self.source_pins.values():
            need(type(p) is dict and set(p) == {'bytes','sha256'} and type(p['bytes']) is int and p['bytes'] > 0
                 and type(p['sha256']) is str and len(p['sha256']) == 64 and all(c in '0123456789abcdef' for c in p['sha256']), 'source_pin')
        need(callable(self.native_validator.validate) and callable(self.operator.checked_scores), 'source_api')


def publish(callback, kind, value):
    raw = ns.encode(value)
    receipt = callback(kind, raw)
    need(type(receipt) is dict and set(receipt) == {'status','sha256'} and receipt['status'] == 'durable'
         and receipt['sha256'] == ns.digest(raw), 'durable_callback')
    return raw, receipt


def failure_numeric(value):
    """Preserve rejected IEEE bits explicitly without accepting them as numbers."""
    if type(value) is np.ndarray and not np.isfinite(value).all():
        raw=value.tobytes().hex()
        return dict(nonfinite_array_bits=dict(dtype=value.dtype.str,shape=list(value.shape),hex_chunks=[raw[i:i+4096] for i in range(0,len(raw),4096)]))
    if type(value) is float and not math.isfinite(value):
        return dict(nonfinite_scalar_bits=np.asarray(value,dtype='<f8').tobytes().hex())
    if type(value) is dict:return {k:failure_numeric(v) for k,v in value.items()}
    if type(value) in (tuple,list):return [failure_numeric(v) for v in value]
    return value


def tensor(value):
    return torch.from_numpy(np.array(value, dtype=np.float64, copy=True, order='C'))


def packet_hash(packet):
    # Streaming numeric-tree hashing avoids expanding native arrays into JSON.
    h = hashlib.sha256()
    def walk(x):
        if type(x) is np.ndarray:
            h.update(b'A'); h.update(ns.encode(dict(dtype=x.dtype.str, shape=list(x.shape)))); h.update(x.tobytes())
        elif type(x) is dict:
            h.update(b'D')
            for k in sorted(x):
                h.update(ns.encode(k)); walk(x[k])
            h.update(b'E')
        elif type(x) in (tuple,list):
            h.update(b'L')
            for v in x: walk(v)
            h.update(b'E')
        else:
            h.update(b'V'); h.update(ns.encode(x))
    walk(packet)
    return h.hexdigest()


def validate_packet(packet, bindings, begin, stage_limit=300):
    bindings.validate(); runtime(); deadline(begin,stage_limit)
    bindings.native_validator.validate(packet, processing_begin=begin if stage_limit==300 else time.monotonic())
    common = [r for r in packet['rows'] if r['common']]
    for r in common:
        for h in r['horizons']:
            need(not h['censor'].any() and bool((h['ratios'] > math.exp(-12)).all()), 'allpositive_admission')
    bindings.operator.admit_allpositive([[tensor(h['reported']) for h in r['horizons']] for r in common])
    need([len([r for r in common if r['partition']==p]) for p in ('TRAIN','DEV')] == [65,22], 'common_roles')
    deadline(begin,stage_limit)
    return copy.deepcopy(packet)


def static_scaler(train):
    x = np.stack([r['precontext'][list(KEEP)] for r in train])
    need(x.shape == (65,30) and np.isfinite(x).all(), 'static_train')
    varying = np.any(x != x[0], axis=0)
    mean = x.mean(0); std = np.where(varying, x.std(0,ddof=0), 0.)
    need(np.isfinite(mean).all() and np.isfinite(std).all() and np.all(std[varying] > 0), 'static_scaler')
    z = (x-mean)/np.where(std > 0,std,1.); z[:,~varying]=0.
    basis=[]; kept=[]; residuals=[]
    for j in range(30):
        col=z[:,j]; norm=float(np.linalg.norm(col)); v=col.copy()
        for _ in range(2):
            for b in basis: v -= np.dot(b,v)*b
        rem=float(np.linalg.norm(v)); residuals.append(rem)
        if rem > 1e-12*norm:
            basis.append(v/rem); kept.append(j)
    w = np.linalg.lstsq(z[:,kept],z,rcond=None)[0] if kept else np.zeros((0,30))
    error=float(np.max(np.abs(np.einsum('ik,kj->ij',z[:,kept],w)-z)))
    need(math.isfinite(error) and error <= 1e-10, 'rank_reconstruction')
    return dict(reference_keep=list(KEEP),mean=mean,std=std,constant=(~varying).astype('u1'),kept=kept,
                residual_norms=np.asarray(residuals,dtype='<f8'),reconstruction=w,reconstruction_max_abs=error)


def context(row, scaler):
    x=row['precontext'][scaler['reference_keep']]; std=scaler['std']
    z=np.where(std>0,(x-scaler['mean'])/np.where(std>0,std,1.),0.)
    return tensor(z[scaler['kept']])


def state(model):
    return {k:v.detach().cpu().numpy().copy() for k,v in model.state_dict().items()}


def load_state(model, value):
    expected=model.state_dict()
    need(set(value)==set(expected), 'parameter_names')
    for k,v in value.items():
        need(type(v) is np.ndarray and v.dtype.str=='<f8' and v.shape==tuple(expected[k].shape) and np.isfinite(v).all(), 'parameter_array')
    model.load_state_dict({k:tensor(v) for k,v in value.items()},strict=True)


def model_for(bindings, schema, seed, arm):
    need((seed,arm) in ORDER, 'fit_identity')
    op=bindings.operator; k=len(schema['static']['kept'])
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        prior=op.Prior(k); prior.initialize(schema['mref'],schema['train_std'])
        model=op.DirectNet(k,tuple(schema['summary']['active'])) if arm=='D' else op.MarkedNet(k,arm,schema['mref'])
        model.prior.load_state_dict(prior.state_dict())
    need(all(p.dtype==torch.float64 and p.device.type=='cpu' for p in model.parameters()), 'model_runtime')
    return model


def posterior(model, row, hi, schema, bindings, begin):
    op=bindings.operator; marks=tensor(row['horizons'][hi]['reported']); nu=tensor(row['noise']['nu'])
    prior=model.prior(context(row,schema['static']))
    if hasattr(model,'theta'):
        raw=op.summaries(marks,nu)
        z=op.standardized_summary(raw,tensor(schema['summary']['mean']),tensor(schema['summary']['std']))
        return op.direct(prior,z,model.theta,model.tau,tuple(schema['summary']['active']),processing_begin=begin)
    return op.forecast(prior,marks,model.coefficients,nu,model.arm,schema['mref'],HORIZONS[hi],row['noise']['arrival_offset_ns'],processing_begin=begin)


def gradient_probe(model, train, schema, bindings, begin):
    params=list(model.named_parameters()); masks={k:np.zeros(tuple(p.shape),dtype='u1') for k,p in params}; norms={k:0. for k,_ in params}
    progress=dict(terms_completed=0,masks=masks,maximum_event_gradient_norm=norms,current=None)
    try:
        for row in train:
            for hi in range(3):
                progress['current']=dict(ordinal=row['ordinal'],horizon=HORIZONS[hi])
                deadline(begin,300); start=time.monotonic()
                loss=posterior(model,row,hi,schema,bindings,start).nll(torch.tensor(row['mw'],dtype=torch.float64))
                progress['current']['loss']=float(loss.detach())
                gradients=torch.autograd.grad(loss,[p for _,p in params],allow_unused=False)
                progress['current']['gradients']={k:g.detach().cpu().numpy().copy() for (k,_),g in zip(params,gradients)}
                for (k,_),g in zip(params,gradients):
                    need(bool(torch.isfinite(g).all()), 'probe_nonfinite')
                    a=g.detach().numpy(); masks[k] |= (a!=0).astype('u1'); norms[k]=max(norms[k],float(np.linalg.norm(a)))
                progress['terms_completed']+=1
                deadline(start,10); deadline(begin,300)
        used=sum(int(v.sum()) for v in masks.values()); total=sum(v.size for v in masks.values())
        need(used==total, 'unused_coefficient')
        return dict(events=65,horizons=3,terms=195,used=used,total=total,masks=masks,maximum_event_gradient_norm=norms)
    except Exception as exc:
        progress['reason']=type(exc).__name__+':'+str(exc)[:256]
        progress['exception_evidence']=export_numeric(getattr(exc,'evidence',None))
        raise Failure('gradient_probe_failed',progress) from exc


def event_order(train_ids,seed):
    need(seed in SEEDS and len(train_ids)==65 and len(set(train_ids))==65, 'event_order_input')
    rng=np.random.default_rng(seed+1009)
    return np.stack([rng.choice(train_ids,8,replace=False) for _ in range(UPDATES)]).astype('<i8')


def prepare(packet, bindings, callback, *, processing_begin):
    """Stage0: all six initialized probes complete before any optimizer exists."""
    evidence=dict(status='admission_incomplete',study=STUDY,completed=[])
    try:
        packet=validate_packet(packet,bindings,processing_begin)
        train=[r for r in packet['rows'] if r['common'] and r['partition']=='TRAIN']
        dev=[r for r in packet['rows'] if r['common'] and r['partition']=='DEV']
        op=bindings.operator
        raw=torch.stack([op.summaries(tensor(h['reported']),tensor(r['noise']['nu'])) for r in train for h in r['horizons']])
        mean,std,active=op.summary_scaler(raw)
        y=np.asarray([r['mw'] for r in train],dtype='<f8')
        schema=dict(static=static_scaler(train),summary=dict(names=list(SUMMARY_NAMES),mean=mean.numpy().copy(),std=std.numpy().copy(),active=list(active)),
                    mref=float(y.mean()),train_std=float(y.std(ddof=0)),train=[r['ordinal'] for r in train],dev=[r['ordinal'] for r in dev])
        counts=op.capacity(len(schema['static']['kept']),active)
        result=dict(status='admitted',study=STUDY,packet_sha256=packet_hash(packet),source_pins=copy.deepcopy(bindings.source_pins),
                    schema=schema,capacity=counts,models={},runtime=runtime(),order=[list(x) for x in ORDER],
                    denominators=copy.deepcopy(packet['denominators']),slots=[dict(ordinal=r['ordinal'],partition=r['partition'],common=r['common'],status=r['status'],horizons=[dict(seconds=h['seconds'],status=h['status']) for h in r['horizons']]) for r in packet['rows']])
        prior_pins={}
        for seed,arm in ORDER:
            deadline(processing_begin,300); model=model_for(bindings,schema,seed,arm)
            initial=state(model); prior_pin=ns.digest(ns.encode(state(model.prior)))
            need(prior_pin==prior_pins.setdefault(seed,prior_pin), 'initial_prior_mismatch')
            initial_record=dict(status='initial',study=STUDY,seed=seed,arm=arm,update=0,parameters=initial,
                                schema_sha256=ns.digest(ns.encode(schema)),packet_sha256=result['packet_sha256'],source_pins=result['source_pins'],prior_sha256=prior_pin)
            _,receipt=publish(callback,'initial',initial_record)
            evidence['current']=dict(seed=seed,arm=arm,initial_receipt=receipt,prior_sha256=prior_pin,probe=None)
            try: probe=gradient_probe(model,train,schema,bindings,processing_begin)
            except Failure as error:
                evidence['current']['probe']=error.evidence
                raise
            evidence['current']['probe']=probe
            need(probe['total']==counts[arm], 'capacity_count')
            key=f'{seed}:{arm}'; result['models'][key]=dict(initial=initial,initial_receipt=receipt,prior_sha256=prior_pin,probe=probe,
                                                        order=event_order(schema['train'],seed))
            evidence['completed'].append(dict(seed=seed,arm=arm,initial_receipt=receipt,probe=probe))
        deadline(processing_begin,300)
        raw,_=publish(callback,'admission',result)
        deadline(processing_begin,300)
        return raw
    except Exception as exc:
        evidence['reason']=type(exc).__name__+':'+str(exc)[:256]
        try: publish(callback,'admission_failure',failure_numeric(evidence))
        except Exception: pass
        raise Failure('admission_incomplete',evidence) from exc


def bind_admission(packet, raw, pin, bindings, begin, stage_limit=300):
    packet=validate_packet(packet,bindings,begin,stage_limit); admission=ns.decode(raw,pin)
    need(admission['study']==STUDY and admission['status']=='admitted' and admission['packet_sha256']==packet_hash(packet)
         and admission['source_pins']==bindings.source_pins and admission['order']==[list(x) for x in ORDER], 'admission_binding')
    need(set(admission['models'])=={f'{s}:{a}' for s,a in ORDER}, 'admission_models')
    schema=admission['schema']; train=[packet['rows'][i] for i in schema['train']]
    need(len(train)==65 and all(r['common'] and r['partition']=='TRAIN' for r in train) and schema['dev']==[r['ordinal'] for r in packet['rows'] if r['common'] and r['partition']=='DEV'], 'admission_roles')
    for seed,arm in ORDER:
        item=admission['models'][f'{seed}:{arm}']; p=item['probe']
        need(p['used']==p['total']==admission['capacity'][arm] and p['terms']==195 and all(v.all() for v in p['masks'].values()), 'admission_probe')
        need(np.array_equal(item['order'],event_order(schema['train'],seed)), 'admission_order')
    return packet,admission


def optimizer_state(optimizer):
    out={}
    for i,(parameter,value) in enumerate(optimizer.state.items()):
        need(set(value)=={'step','exp_avg','exp_avg_sq'}, 'adam_state')
        out[str(i)]={k:v.detach().cpu().numpy().copy() for k,v in value.items()}
    return out


def fit_one(packet, admission_raw, admission_pin, bindings, callback, *, seed, arm, processing_begin):
    evidence=dict(status='failure',study=STUDY,seed=seed,arm=arm,update=0,history=[])
    model=None; optimizer=None
    try:
        deadline(processing_begin,300); packet,admission=bind_admission(packet,admission_raw,admission_pin,bindings,processing_begin)
        schema=admission['schema']; item=admission['models'][f'{seed}:{arm}']
        model=model_for(bindings,schema,seed,arm); load_state(model,item['initial'])
        evidence.update(admission_sha256=admission_pin,packet_sha256=admission['packet_sha256'],source_pins=copy.deepcopy(bindings.source_pins),
                        prior_sha256=item['prior_sha256'],initial_sha256=ns.digest(ns.encode(item['initial'])),
                        order_sha256=ns.digest(ns.encode(item['order'])),runtime=runtime(),parameters=state(model),optimizer={})
        publish(callback,'begin_fit',dict(evidence,status='initial'))
        deadline(processing_begin,300)
        optimizer=torch.optim.Adam(model.parameters(),lr=1e-3,weight_decay=0.)
        for update,ids in enumerate(item['order'],1):
            deadline(processing_begin,300); optimizer.zero_grad(set_to_none=True); loss_value=0.
            for ordinal in ids:
                row=packet['rows'][int(ordinal)]
                for hi in range(3):
                    evidence['current']=dict(update=update,ordinal=int(ordinal),horizon=HORIZONS[hi])
                    deadline(processing_begin,300); start=time.monotonic()
                    loss=posterior(model,row,hi,schema,bindings,start).nll(torch.tensor(row['mw'],dtype=torch.float64))
                    evidence['current']['loss']=float(loss.detach())
                    need(bool(torch.isfinite(loss)), 'loss_nonfinite')
                    (loss/24.).backward(); loss_value += float(loss.detach())/24.
                    deadline(start,10)
            need(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters()), 'gradient_nonfinite')
            norm=float(torch.nn.utils.clip_grad_norm_(model.parameters(),5.,error_if_nonfinite=True))
            deadline(processing_begin,300); optimizer.step(); evidence['update']=update
            evidence['parameters']=state(model); evidence['optimizer']=optimizer_state(optimizer)
            need(all(np.isfinite(v).all() for v in evidence['parameters'].values()), 'parameter_nonfinite')
            evidence['history'].append(dict(update=update,loss=loss_value,gradient_norm=norm,ordinals=[int(i) for i in ids]))
            publish(callback,'step',dict(evidence,status='partial'))
            deadline(processing_begin,300)
        train=[packet['rows'][i] for i in schema['train']]
        evidence['final_probe']=gradient_probe(model,train,schema,bindings,processing_begin)
        need(evidence['final_probe']['total']==admission['capacity'][arm], 'final_capacity')
        evidence['status']='final'; deadline(processing_begin,300)
        raw,receipt=publish(callback,'final',evidence)
        deadline(processing_begin,300)
        return dict(status='complete',checkpoint=raw,receipt=receipt)
    except Exception as exc:
        evidence['status']='failure'; evidence['reason']=type(exc).__name__+':'+str(exc)[:256]
        evidence['exception_evidence']=export_numeric(getattr(exc,'evidence',None))
        if model is not None:
            evidence['parameters']=state(model)
            evidence['partial_gradients']={k:(v.grad.detach().cpu().numpy().copy() if v.grad is not None else None) for k,v in model.named_parameters()}
        if optimizer is not None:
            try: evidence['optimizer']=optimizer_state(optimizer)
            except Exception: pass
        try: publish(callback,'failure',failure_numeric(evidence))
        except Exception: pass
        raise Failure('fit_incomplete',evidence) from exc


def export_numeric(value):
    if isinstance(value,np.generic):return value.item()
    if type(value) is torch.Tensor:
        return value.detach().cpu().numpy().copy()
    if type(value) in (tuple,list):
        return [export_numeric(v) for v in value]
    if type(value) is dict:
        return {k:export_numeric(v) for k,v in value.items()}
    return value


def validate_final(checkpoint, admission, admission_pin, seed, arm):
    item=admission['models'][f'{seed}:{arm}']
    need(checkpoint['status']=='final' and checkpoint['study']==STUDY and checkpoint['seed']==seed and checkpoint['arm']==arm
         and checkpoint['update']==300 and len(checkpoint['history'])==300 and checkpoint['admission_sha256']==admission_pin
         and checkpoint['packet_sha256']==admission['packet_sha256'] and checkpoint['source_pins']==admission['source_pins']
         and checkpoint['initial_sha256']==ns.digest(ns.encode(item['initial'])) and checkpoint['prior_sha256']==item['prior_sha256']
         and checkpoint['order_sha256']==ns.digest(ns.encode(item['order'])), 'final_checkpoint')
    for i,(h,ids) in enumerate(zip(checkpoint['history'],item['order']),1):
        need(set(h)=={'update','loss','gradient_norm','ordinals'} and h['update']==i and h['ordinals']==ids.tolist()
             and type(h['loss']) is float and math.isfinite(h['loss']) and type(h['gradient_norm']) is float
             and math.isfinite(h['gradient_norm']) and h['gradient_norm']>=0, 'final_history')
    p=checkpoint['final_probe']
    need(p['used']==p['total']==admission['capacity'][arm] and p['terms']==195 and all(v.all() for v in p['masks'].values()), 'final_probe')


def score_final(packet, admission_raw, admission_pin, checkpoint_raw, checkpoint_pin, bindings, callback, *, processing_begin):
    """Fresh score-only stage. Never constructs an optimizer or updates weights."""
    evidence=dict(status='incomplete',study=STUDY,predictions=[])
    current=None; post=None
    try:
        deadline(processing_begin,900)
        packet,admission=bind_admission(packet,admission_raw,admission_pin,bindings,processing_begin,stage_limit=900)
        checkpoint=ns.decode(checkpoint_raw,checkpoint_pin); seed=checkpoint['seed']; arm=checkpoint['arm']
        need((seed,arm) in ORDER,'fit_identity'); validate_final(checkpoint,admission,admission_pin,seed,arm)
        schema=admission['schema']; model=model_for(bindings,schema,seed,arm); load_state(model,checkpoint['parameters']); model.eval()
        model_pin=ns.digest(ns.encode(state(model)))
        evidence.update(seed=seed,arm=arm,admission_sha256=admission_pin,packet_sha256=admission['packet_sha256'],
                        checkpoint_sha256=checkpoint_pin,source_pins=copy.deepcopy(bindings.source_pins),no_optimizer=True)
        with torch.no_grad():
            for ordinal in schema['dev']:
                row=packet['rows'][ordinal]
                for hi,h in enumerate(HORIZONS):
                    post=None
                    current=dict(seed=seed,arm=arm,ordinal=ordinal,horizon=h,target=float(row['mw']),group=row['group'],
                                 precontext=row['precontext'].copy(),marks=row['horizons'][hi]['reported'].copy(),nu=row['noise']['nu'].copy(),arrival_offset_ns=row['noise']['arrival_offset_ns'])
                    deadline(processing_begin,900); start=time.monotonic()
                    post=posterior(model,row,hi,schema,bindings,start)
                    source=dict(reference=export_numeric(post.reference),log_weights=export_numeric(post.logw),
                                means=export_numeric(post.mu),scales=export_numeric(post.sigma),log_normalizer=float(post.logz))
                    source['noise_probabilities']=post.logw.exp().reshape(12,5).sum(1).numpy().copy() if arm=='S' else None
                    current['source']=source
                    score=bindings.operator.checked_scores(post,float(row['mw']),bindings.reference)
                    current['score']=score
                    record=dict(seed=seed,arm=arm,ordinal=ordinal,horizon=h,target=float(row['mw']),group=row['group'],
                                status='complete',**score,source=source)
                    validate_forecast(record)
                    deadline(start,10); evidence['predictions'].append(record)
                    publish(callback,'forecast',record); deadline(start,10); deadline(processing_begin,900)
        need(ns.digest(ns.encode(state(model)))==model_pin, 'scoring_changed_parameters')
        validate_population(evidence['predictions'],packet,seed,arm)
        evidence['metrics']={str(h):metrics([p for p in evidence['predictions'] if p['horizon']==h]) for h in HORIZONS}
        evidence['status']='complete'; deadline(processing_begin,900)
        raw,receipt=publish(callback,'score_final',evidence); deadline(processing_begin,900)
        return dict(status='complete',result=raw,receipt=receipt)
    except Exception as exc:
        evidence['status']='incomplete'; evidence['reason']=type(exc).__name__+':'+str(exc)[:256]
        evidence['current_record']=current
        evidence['exception_evidence']=export_numeric(getattr(exc,'evidence',None))
        if post is not None:
            evidence['current_work']=post.budget.record()
        try: publish(callback,'score_failure',failure_numeric(evidence))
        except Exception: pass
        raise Failure('score_incomplete',evidence) from exc


def numeric_evidence(p, row=None):
    """Validate mandatory evidence; independent ROOT replay still proves truth."""
    def array(value,shape,positive=False):
        need(type(value) is np.ndarray and value.dtype.str=='<f8' and value.shape==shape and value.flags.c_contiguous
             and np.isfinite(value).all() and (not positive or bool((value>0).all())), 'forecast_source_array')
    source=p['source']; diag=p['diagnostics']; arm=p['arm']; length=60 if arm=='S' else 5
    need(type(source) is dict and set(source)=={'reference','log_weights','means','scales','log_normalizer','noise_probabilities'}, 'forecast_source')
    for key in ('log_weights','means','scales'):array(source[key],(length,),key=='scales')
    need(type(source['log_normalizer']) is float and math.isfinite(source['log_normalizer']), 'forecast_log_normalizer')
    weights=np.exp(source['log_weights']);need(np.isfinite(weights).all() and abs(math.fsum(weights.tolist())-1.)<=1e-6, 'forecast_normalization')
    ref=source['reference'];need(type(ref) is dict and set(ref)=={'prior','facts','nu','arm'}, 'forecast_reference')
    need(type(ref['prior']) is list and len(ref['prior'])==3 and type(ref['facts']) is list, 'forecast_reference')
    for i,v in enumerate(ref['prior']):array(v,(5,),i==2)
    need(bool((ref['prior'][2]>=.05).all()) and abs(float(np.logaddexp.reduce(ref['prior'][0])))<=1e-12, 'forecast_prior')
    array(ref['nu'],(12,3))
    if arm=='D':
        need(ref['arm']=='P' and not ref['facts'] and bool((ref['nu']==0).all()) and source['noise_probabilities'] is None
             and source['log_normalizer']==0. and all(a.tobytes()==source[k].tobytes() for a,k in zip(ref['prior'],('log_weights','means','scales'))), 'forecast_direct_source')
    else:
        need(ref['arm']==arm and 1<=len(ref['facts'])<=20, 'forecast_facts')
        for fact in ref['facts']:
            need(type(fact) is list and len(fact)==4, 'forecast_fact')
            for i,v in enumerate(fact):array(v,(3,),i==2)
            need(bool((fact[2]>=.05).all()) and bool((fact[3]>-12).all()), 'forecast_positive_fact')
        if row is not None:
            h=row['horizons'][HORIZONS.index(p['horizon'])]
            need(ref['nu'].tobytes()==row['noise']['nu'].tobytes() and len(ref['facts'])==len(h['reported'])
                 and np.stack([v[3] for v in ref['facts']]).tobytes()==h['reported'].tobytes(), 'forecast_source_prefix')
        if arm=='S':
            noise=source['noise_probabilities'];array(noise,(12,))
            need(bool((noise>=0).all()) and abs(math.fsum(noise.tolist())-1.)<=1e-6
                 and bool((np.abs(noise-weights.reshape(12,5).sum(1))<=1e-6).all()), 'forecast_noise_mass')
        else:need(source['noise_probabilities'] is None, 'forecast_plugin_noise')
    need(type(diag) is dict and set(diag)=={'errors','work','allpositive_only','reference_reserved_points','reference_actual_points'}
         and diag['allpositive_only'] is True and type(diag['reference_reserved_points']) is int and diag['reference_reserved_points']==240
         and type(diag['reference_actual_points']) is int and 0<=diag['reference_actual_points']<=240, 'forecast_diagnostics')
    errors=diag['errors'];need(type(errors) is dict and set(errors)=={'mean','nll','log_normalizer','crps','pit'}, 'forecast_errors')
    for k,v in errors.items():need(type(v) is float and math.isfinite(v) and 0<=v<=(1e-6 if k in ('crps','pit') else 1e-4), 'forecast_parity')
    work=diag['work'];need(type(work) is dict and set(work)=={'density_points','scalar_terms','seconds'}, 'forecast_work')
    need(type(work['density_points']) is int and 0<=work['density_points']<=1000000 and type(work['scalar_terms']) is int
         and 0<=work['scalar_terms']<2**63 and type(work['seconds']) is float and math.isfinite(work['seconds']) and 0<=work['seconds']<=10, 'forecast_work_cap')


def validate_forecast(p, require_quantiles=True):
    if p['arm'] in ARMS:numeric_evidence(p)
    required=('mean','median','nll','crps','pit')
    need(p['status']=='complete' and all(type(p[k]) is float and math.isfinite(p[k]) for k in required)
         and p['crps']>=0 and 0<=p['pit']<=1, 'forecast_fields')
    if not require_quantiles and 'quantiles' not in p:
        need(all(type(p['coverage_'+str(level)]) is bool for level in (50,80,95)), 'forecast_coverage')
        return
    q=p['quantiles']; keys=[str(x) for x in (.025,.1,.25,.5,.75,.9,.975)]
    need(type(q) is dict and set(q)==set(keys) and all(type(q[k]) is float and math.isfinite(q[k]) for k in keys)
         and all(q[a]<=q[b] for a,b in zip(keys[:-1],keys[1:])) and p['median']==q['0.5'], 'forecast_quantiles')
    for level,lo,hi in ((50,'0.25','0.75'),(80,'0.1','0.9'),(95,'0.025','0.975')):
        value=p['coverage_'+str(level)]
        need(type(value) is bool and value==bool(q[lo]<=p['target']<=q[hi]), 'forecast_coverage')


def validate_population(predictions, packet, seed, arm):
    expected=[(r['ordinal'],h) for r in packet['rows'] if r['common'] and r['partition']=='DEV' for h in HORIZONS]
    need(len(predictions)==66 and [(p['ordinal'],p['horizon']) for p in predictions]==expected, 'forecast_population')
    for p in predictions:
        row=packet['rows'][p['ordinal']]
        need(p['seed']==seed and p['arm']==arm and type(p['target']) is float and p['target']==row['mw'] and p['group']==row['group'], 'forecast_identity')
        validate_forecast(p,require_quantiles=arm not in ('B','F'))
        if arm in ARMS:numeric_evidence(p,row)


def metrics(predictions):
    y=np.asarray([p['target'] for p in predictions]); e=np.asarray([p['mean'] for p in predictions])-y; a=np.abs(e)
    hi=y>=5.5; higher=y>=6; lo=y<5.5
    out=dict(n=len(y),nll=float(np.mean([p['nll'] for p in predictions])),crps=float(np.mean([p['crps'] for p in predictions])),
             mae=float(a.mean()),medae=float(np.median(a)),tail_mae_5_5=float(a[hi].mean()) if hi.any() else None,
             tail_mae_6=float(a[higher].mean()) if higher.any() else None,lower_mae=float(a[lo].mean()) if lo.any() else None,
             lower_medae=float(np.median(a[lo])) if lo.any() else None,tail_bias=float(e[hi].mean()) if hi.any() else None,
             cvar95=float(np.sort(a)[-max(1,math.ceil(.05*len(y))):].mean()),maximum=float(a.max()),
             p95=float(np.quantile(a,.95,method='linear')),median_mae=float(np.mean([abs(p['median']-p['target']) for p in predictions])))
    for level in (50,80,95):out['coverage_'+str(level)]=float(np.mean([p['coverage_'+str(level)] for p in predictions]))
    return out


def aggregate(packet, admission_raw, admission_pin, new_results, strong_results, bindings, *, processing_begin):
    """Closed forecasts only; ROOT independently establishes external closure truth."""
    result=dict(status='incomplete',pass_all=False,original24=[],additional12=[])
    try:
        packet,admission=bind_admission(packet,admission_raw,admission_pin,bindings,processing_begin)
        need(type(new_results) is list and len(new_results)==6 and [(x['seed'],x['arm']) for x in new_results]==list(ORDER), 'six_fit_order')
        need(type(strong_results) is list and len(strong_results)==8 and [(x['seed'],x['arm']) for x in strong_results]==[(s,a) for s in SEEDS for a in ('B','F','H','T')], 'strong_comparators')
        by={}
        for record in new_results+strong_results:
            s,a=record['seed'],record['arm']
            need(record['status']=='complete' and record['packet_sha256']==admission['packet_sha256'] and record['no_optimizer'] is True, 'score_closure')
            need(type(record['checkpoint_sha256']) is str and len(record['checkpoint_sha256'])==64, 'checkpoint_closure')
            if a in ARMS:
                need(record['admission_sha256']==admission_pin and record['source_pins']==bindings.source_pins, 'new_result_binding')
            else:
                closed=record['independent_closure']
                need(set(closed)=={'verified','checkpoint_sha256','source_sha256','packet_sha256','no_optimizer'}
                     and closed['verified'] is True and closed['no_optimizer'] is True
                     and closed['checkpoint_sha256']==record['checkpoint_sha256'] and closed['packet_sha256']==admission['packet_sha256']
                     and type(closed['source_sha256']) is str and len(closed['source_sha256'])==64, 'strong_independent_closure')
            validate_population(record['predictions'],packet,s,a)
            by[s,a]={str(h):metrics([p for p in record['predictions'] if p['horizon']==h]) for h in HORIZONS}
        for s in SEEDS:
            for h in HORIZONS:
                candidate=by[s,'S'][str(h)]
                for other in ('B','F','H','T','P','D'):
                    baseline=by[s,other][str(h)]
                    tail=candidate['tail_mae_5_5'] is not None and baseline['tail_mae_5_5'] is not None and baseline['tail_mae_5_5']-candidate['tail_mae_5_5']>=.02
                    guard={k:candidate[k] is not None and baseline[k] is not None and candidate[k]<=baseline[k] for k in ('mae','medae','lower_mae','lower_medae','cvar95','maximum')}
                    proper=other in ('H','T') or candidate['nll']<baseline['nll'] and candidate['crps']<baseline['crps']
                    check=dict(seed=s,horizon=h,comparator=other,tail=tail,proper=proper,bulk_worst=guard,passed=tail and proper and all(guard.values()))
                    result['original24' if other in ('B','F','H','T') else 'additional12'].append(check)
        need(len(result['original24'])==24 and len(result['additional12'])==12, 'guard_count')
        deadline(processing_begin,300)
        result.update(status='complete',pass_all=all(x['passed'] for x in result['original24']+result['additional12']),
                      metrics={f'{s}:{a}':m for (s,a),m in by.items()},scientific_claim='exploratory Stage1 only; Stage2 and independent validation absent')
    except Exception as exc:
        result.update(status='incomplete',pass_all=False,reason=type(exc).__name__+':'+str(exc)[:256])
    return result

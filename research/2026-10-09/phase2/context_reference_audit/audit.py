"""Independent CPU-only audit; no imports from the training implementation.

Requires COMPLETE, source pins and every manifested artifact. Reads saved
probabilities/points/checkpoints only. Never fits a model or uses CUDA. Float32
probability rounding is bounded explicitly when validating saved float64 points.
"""
import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np

CONTROLS = ('crps_ce','context_ce','shuffled_ce','average_ce','ranked_bce_ce','properized_ad_ce')
CENTERS = (np.arange(66,dtype=np.float64)+.5)*.1


@dataclass(frozen=True)
class Protocol:
    records: int = 197676
    epochs: int = 15
    reference_epochs: int = 15
    batch_size: int = 2048
    tail_events: int = 13
    folds: int = 5
    seeds: tuple = (20261009,20261010)
    fold_seed: int = 20261009
    reference_seed: int = 20261011
    permutation_seed: int = 20261012


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def array_digest(value):
    a=np.ascontiguousarray(value);h=hashlib.sha256()
    h.update(str(a.dtype).encode());h.update(json.dumps(list(a.shape)).encode());h.update(a.tobytes())
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def load_npz(path):
    with np.load(path,allow_pickle=False) as data:return {k:data[k] for k in data.files}


def verify_artifacts(run,pins,protocol=Protocol()):
    run=Path(run);complete=read_json(run/'COMPLETE.json')
    require(complete.get('status')=='complete','Missing valid completion status')
    require(complete['artifacts_sha256']==file_digest(run/'artifacts.json'),'Artifact-manifest hash mismatch')
    manifest=read_json(run/'artifacts.json')
    required={'identity.json','run.json','metrics.json','history.json','training_traces.json',
              'reference_oof.npz','reference_report.json','predictions.npz','feature_schema.json',
              'input_identities.json','alignment.json'}
    required.update(f'{c}_probabilities.npz' for c in CONTROLS)
    required.update(f'{c}_seed{s}.pth' for c in CONTROLS for s in protocol.seeds)
    required.update(f'reference_fold{k}.pth' for k in range(protocol.folds))
    require(required<=set(manifest),'Required audit artifacts missing from manifest')
    for name,identity in manifest.items():
        require(Path(name).name==name and name not in ('.','..'),'Manifest entry must be a local basename')
        path=run/name
        require(path.is_file() and not path.is_symlink(),f'Missing/linked artifact: {name}')
        require(path.stat().st_size==identity['bytes'] and file_digest(path)==identity['sha256'],f'Artifact mismatch: {name}')
    identity=read_json(run/'identity.json')
    require(identity['source_sha256']==pins['source_sha256'],'Run sources differ from reviewed pinned commit')
    return complete,identity,manifest


def normalized_probability(value):
    p=np.asarray(value,dtype=np.float64)
    require(p.ndim==2 and p.shape[1]==66 and len(p)>0,'Expected nonempty N x 66 probabilities')
    require(np.isfinite(p).all() and (p>=0).all(),'Invalid probability values')
    sums=p.sum(1)
    require(np.max(np.abs(sums-1))<2e-6,'Probability rows fail mass check')
    return p/sums[:,None]


def continuous_crps(p,y,centers=CENTERS):
    """Integrate squared CDF error across center intervals and exterior tails."""
    cdf=p.cumsum(1)[:,:-1]
    widths=np.diff(centers)
    left=np.clip(y[:,None]-centers[None,:-1],0,widths)
    result=(cdf*cdf*left+(1-cdf)**2*(widths-left)).sum(1)
    return result+np.maximum(centers[0]-y,0)+np.maximum(y-centers[-1],0)


def event_average(value,ids):
    _,inverse,counts=np.unique(ids,return_inverse=True,return_counts=True)
    return float(np.mean(np.bincount(inverse,weights=value)/counts))


def recompute_metrics(y,point,ids,p):
    error=np.abs(point-y);tail=y>=4
    result={'records':len(y),'events':len(np.unique(ids)),'mae':float(error.mean()),
        'medae':float(np.median(error)),'rmse':float(np.sqrt(np.mean(error**2))),
        'event_macro_mae':event_average(error,ids),
        'cvar95':float(np.sort(error)[-max(1,int(np.ceil(.05*len(y)))):].mean()),
        'fp4':int(np.sum((point>=4)&~tail)),'tp4':int(np.sum((point>=4)&tail)),
        'fpr4':float(np.mean(point[~tail]>=4)) if (~tail).any() else None}
    for threshold in (4.,4.5,5.,6.):
        mask=y>=threshold;prefix=f'm{threshold:g}'
        result[prefix+'_events']=len(np.unique(ids[mask]))
        result[prefix+'_records']=int(mask.sum())
        result[prefix+'_mae']=float(error[mask].mean()) if mask.any() else None
        result[prefix+'_event_macro_mae']=event_average(error[mask],ids[mask]) if mask.any() else None
        result[prefix+'_bias']=float((point[mask]-y[mask]).mean()) if mask.any() else None
    crps=continuous_crps(p,y)
    labels=np.clip(np.floor(y/.1+1e-5),0,65).astype(int)
    correct=p[np.arange(len(p)),labels];positive=correct>0
    nll=np.full(len(p),np.inf);nll[positive]=-np.log(correct[positive])
    result.update(crps=float(crps.mean()),event_macro_crps=event_average(crps,ids),
        nll=float(nll.mean()) if positive.all() else None,nll_zero_target_probabilities=int(np.sum(~positive)),
        nll_status='finite' if positive.all() else 'infinite from saved zero probability; no floor applied',
        nll_finite_part_mean=float(nll[positive].mean()) if positive.any() else None)
    return result


def validate_points(stored_probability,mean,median):
    p=np.asarray(stored_probability);p64=p.astype(np.float64)
    require(p.dtype==np.float32,'Expected archived float32 probabilities')
    require(mean.shape==median.shape==(len(p),),'Point rows misaligned')
    entry_lower,entry_upper=probability_rounding_intervals(p)
    mean_lower=(entry_lower*CENTERS).sum(1)-2e-14
    mean_upper=(entry_upper*CENTERS).sum(1)+2e-14
    reconstructed_mean=(p64*CENTERS).sum(1)
    require(np.all((mean>=mean_lower)&(mean<=mean_upper)),
            'Saved mean exceeds float32 probability-rounding bound')
    # The original double probabilities can put a median on either side of a
    # rounded CDF=0.5. Require the stored center to be feasible within IEEE bounds.
    j=np.searchsorted(CENTERS,median)
    require((j<66).all() and np.array_equal(CENTERS[j],median),'Saved median is not a grid center')
    cdf=p64.cumsum(1)
    cdf_lower=entry_lower.cumsum(1)-2e-14
    cdf_upper=entry_upper.cumsum(1)+2e-14
    rows=np.arange(len(p));before=np.maximum(j-1,0)
    lower=np.where(j==0,0,cdf_lower[rows,before])
    upper=cdf_upper[rows,j]
    require(np.all((lower<.5)&(upper>=.5)),'Saved median inconsistent with probability-rounding bounds')
    # The runner uses float64 sequential cumsum. An increment smaller than
    # half the representable gap immediately below 0.5 cannot produce its first
    # crossing, even if independent cumulative error intervals overlap 0.5.
    # This rules out a corrupted median placed in a float32-zero probability gap.
    crossing_increment=(.5-np.nextafter(.5,-np.inf))/2
    require(np.all((j==0)|(entry_upper[rows,j]>=crossing_increment)),
            'Saved median crosses a probability gap that cannot advance float64 CDF')
    naive=np.minimum((cdf<.5).sum(1),65)
    return {'mean_max_difference':float(np.max(np.abs(mean-reconstructed_mean))),
            'median_rounding_ambiguous_rows':int(np.sum(j!=naive))}


def probability_rounding_intervals(p):
    p=np.asarray(p)
    require(p.dtype==np.float32 and np.isfinite(p).all() and (p>=0).all(),'Invalid archived float32 PMF')
    previous=np.nextafter(p,np.float32(-np.inf)).astype(np.float64)
    following=np.nextafter(p,np.float32(np.inf)).astype(np.float64)
    value=p.astype(np.float64)
    return np.maximum(0,(previous+value)/2),(following+value)/2


def verify_ensemble(ensemble,seeds):
    require(all(s.shape==ensemble.shape for s in seeds),'Ensemble/seed probability shapes differ')
    intervals=[probability_rounding_intervals(s) for s in seeds]
    lower=np.nextafter(np.mean([v[0] for v in intervals],axis=0),-np.inf)
    upper=np.nextafter(np.mean([v[1] for v in intervals],axis=0),np.inf)
    actual_lower,actual_upper=probability_rounding_intervals(ensemble)
    require(np.all((actual_upper>=lower)&(actual_lower<=upper)),
            'Ensemble probability outside seed float32-rounding intervals')
    # A convex mean of inputs in the same rounding cell rounds to that cell.
    # Enforce this exactly so closed intervals cannot admit adjacent tie cells,
    # especially a nonzero ensemble probability when every seed rounds to zero.
    identical=np.logical_and.reduce([s==seeds[0] for s in seeds])
    require(np.all(ensemble[identical]==seeds[0][identical]),
            'Ensemble differs from identical archived seed rounding cells')


def aligned(data,targets,ids,traces):
    for key,expected in [('targets',targets),('event_ids',ids),('trace_names',traces)]:
        require(np.array_equal(data[key],expected),f'{key} row identities differ')


def hash_folds(ids,protocol):
    mapping={s:int.from_bytes(hashlib.sha256(f'{protocol.fold_seed}:{s}'.encode()).digest()[:8],'big')%protocol.folds
             for s in np.unique(ids).tolist()}
    return np.array([mapping[s] for s in ids],dtype=np.int64)


def verify_reference(ref,report,protocol):
    y,ids,pop=ref['targets'],ref['event_ids'],ref['population_weights']
    n=len(y);require(n==protocol.records,'Reference TRAIN count changed')
    require(report['n_folds']==protocol.folds and report['fold_seed']==protocol.fold_seed
            and report['reference_seed']==protocol.reference_seed,'Reference report seed/fold settings differ')
    require(all(ref[k].shape==(n,) for k in ('targets','event_ids','trace_names','row_index','population_weights','folds','donor')),
            'Reference identity/weight arrays not aligned')
    require(len(np.unique(ref['trace_names']))==n and len(np.unique(ref['row_index']))==n,'Duplicate reference row/trace')
    require(np.isfinite(y).all() and np.isfinite(pop).all() and (pop>0).all(),'Invalid reference targets/weights')
    for field,key in [('targets_sha256','targets'),('population_weights_sha256','population_weights'),
                      ('row_index_sha256','row_index'),('event_ids_sha256','event_ids'),('trace_names_sha256','trace_names'),
                      ('fold_sha256','folds'),('probability_sha256','probability'),('weight_sha256','weights')]:
        require(report[field]==array_digest(ref[key]),f'Reference digest mismatch: {field}')
    folds=hash_folds(ids,protocol)
    require(np.array_equal(ref['folds'],folds) and set(folds)==set(range(protocol.folds)),'Event hash folds mismatch/empty')
    require(np.array_equal(np.sort(ref['donor']),np.arange(n)),'Donor indices not a bijection')
    require(np.array_equal(folds[ref['donor']],folds),'Weight permutation crosses teacher exclusion fold')
    p=normalized_probability(ref['probability']);cdf=np.clip(ref['probability'].cumsum(1)[:,:-1],0,1)
    require(np.array_equal(cdf,ref['cdf']),'OOF CDF differs from saved probability')
    raw=np.minimum(25.,1/(.01+cdf*(1-cdf)));w=(raw/raw.mean(1,keepdims=True)).astype(np.float32)
    require(np.array_equal(w,ref['weights']),'Frozen weights differ from prespecified capped/normalized equation')
    require(np.max(np.abs(w.mean(1)-1))<2e-6 and (w>0).all(),'Invalid per-record threshold normalization')
    average=np.average(w.astype(np.float64),weights=pop,axis=0).astype(np.float32)
    require(np.array_equal(average,ref['average']),'Average control is not population-weighted TRAIN vector')
    rng=np.random.default_rng(protocol.permutation_seed);donor=np.arange(n)
    for k in range(protocol.folds):
        rows=np.flatnonzero(folds==k);donor[rows]=rng.permutation(rows)
    require(np.array_equal(donor,ref['donor']),'Permutation seed/order differs')
    require(array_digest(donor)==report['permutation']['donor_sha256'],'Donor report digest mismatch')
    require(array_digest(average)==report['permutation']['average_sha256'],'Average report digest mismatch')
    labels=np.clip(np.floor(y.astype(np.float64)/.1+1e-5),0,65).astype(int)
    target=p[np.arange(n),labels]
    require((target>0).all(),'OOF probability underflow prevents logp report verification')
    nll=-np.log(target)
    require(abs(np.average(nll,weights=pop)-report['population_weighted_oof_nll'])<2e-9,'OOF NLL report mismatch')
    fold_proofs=[]
    for k in range(protocol.folds):
        held=np.flatnonzero(folds==k);train=np.flatnonzero(folds!=k);proof=report['folds'][k]
        require(proof['held_fold']==k and proof['seed']==protocol.reference_seed+k,'Reference fold/seed mismatch')
        require(proof['train_indices_sha256']==array_digest(train) and proof['held_indices_sha256']==array_digest(held),
                'Fold retained/held row-index provenance mismatch')
        require(not set(ids[train])&set(ids[held]),'Whole-event exclusion violation')
        require(proof['train_records']==len(train) and proof['held_records']==len(held),'Fold record counts mismatch')
        require(proof['train_events']==len(np.unique(ids[train])) and proof['held_events']==len(np.unique(ids[held])),
                'Fold event counts mismatch')
        fold_proofs.append({'fold':k,'held_records':len(held),'held_events':len(np.unique(ids[held])),
            'train_records':len(train),'train_events':len(np.unique(ids[train]))})
    weighted_mean=np.average(w,weights=pop,axis=0)
    variation=np.sqrt(np.average((w-weighted_mean)**2,weights=pop,axis=0))
    return {'event_fold_exclusion':'verified from all saved aligned event IDs and indices',
        'folds':fold_proofs,'population_weighted_oof_nll':float(np.average(nll,weights=pop)),
        'cap_fraction':float(np.mean(raw==25.)), 'row_mean_max_error':float(np.max(np.abs(w.mean(1)-1))),
        'weight_min':float(w.min()),'weight_max':float(w.max()),
        'weighted_per_threshold_std':variation.tolist(),'weighted_threshold_std_mean':float(variation.mean()),
        'context_minus_average_weight_rms':float(np.sqrt(np.average(np.mean((w-average)**2,axis=1),weights=pop))),
        'same_event_donor_fraction':float(np.mean(ids[donor]==ids)),
        'fixed_donor_fraction':float(np.mean(donor==np.arange(n))),
        'shuffled_weighted_mean_max_change':float(np.max(np.abs(np.average(w[donor],weights=pop,axis=0)-average))),
        'normalizer_boundary':'Checkpoint values and hashes verified; raw85 inputs absent, numerical recomputation unavailable',
        'teacher_input_source_sha256':report['input_sha256']}


def torch_tools():
    # No GPU discovery or CUDA calls. Explicit visibility also protects future
    # checkpoint/helper changes; source state loading is always map_location=cpu.
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(2)
    return torch


def state_digest(state):
    h=hashlib.sha256()
    for key,tensor in state.items():
        a=tensor.detach().cpu().numpy()
        h.update(key.encode());h.update(array_digest(a).encode())
    return h.hexdigest()


def expected_model_hash(torch,seed,input_dim,zero_last):
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        net=torch.nn.Sequential(torch.nn.Linear(input_dim,128),torch.nn.SiLU(),torch.nn.Dropout(.1),
                                torch.nn.Linear(128,64),torch.nn.SiLU(),torch.nn.Linear(64,66))
        if zero_last:
            torch.nn.init.zeros_(net[-1].weight);torch.nn.init.zeros_(net[-1].bias)
    return state_digest({'net.'+k:v for k,v in net.state_dict().items()})


def expected_orders(torch,seed,count,epochs):
    g=torch.Generator(device='cpu').manual_seed(seed)
    return [array_digest(torch.randperm(count,generator=g).numpy()) for _ in range(epochs)]


def verify_checkpoints(run,ref,report,traces,history,config,protocol):
    torch=torch_tools();run=Path(run);normalizer=None
    for seed in protocol.seeds:
        initial=expected_model_hash(torch,seed,291,True)
        orders=expected_orders(torch,seed,protocol.records,protocol.epochs)
        for control in CONTROLS:
            name=f'{control}_seed{seed}';trace=traces[name]
            require(trace['initial_model_sha256']==initial,'Student initialization does not replay on CPU')
            require(trace['epoch_order_sha256']==orders,'Student order does not replay from seed')
            require(len(history[name])==protocol.epochs and np.isfinite(history[name]).all(),'Incomplete student epochs')
            ck=torch.load(run/f'{name}.pth',map_location='cpu',weights_only=True)
            require(ck['seed']==seed and ck['control']==control and ck['config']==config,'Student checkpoint config mismatch')
            require(state_digest(ck['model'])==trace['final_model_sha256'],'Final student model hash mismatch')
            mean,std,mask=[ck[k].numpy() for k in ('feature_mean','feature_std','feature_mask')]
            require(mean.shape==std.shape==mask.shape==(291,) and np.isfinite(mean).all() and np.isfinite(std).all() and (std>0).all(),
                    'Invalid student normalizer')
            require(np.array_equal(mask,np.r_[np.ones(279),np.zeros(12)]),'Instrument/native student mask changed')
            signature=(array_digest(mean),array_digest(std),array_digest(mask))
            if normalizer is None:normalizer=signature
            require(signature==normalizer,'Student feature normalization differs across arms')
    for k,proof in enumerate(report['folds']):
        ck=torch.load(run/f'reference_fold{k}.pth',map_location='cpu',weights_only=True)
        require(ck['held_fold']==k and ck['seed']==protocol.reference_seed+k and ck['feature_dimension']==85,'Teacher checkpoint identity mismatch')
        require(state_digest(ck['model'])==proof['final_model_sha256'],'Teacher model hash mismatch')
        require(expected_model_hash(torch,protocol.reference_seed+k,85,False)==proof['initial_model_sha256'],'Teacher initialization mismatch')
        count=int(np.sum(ref['folds']!=k))
        require(expected_orders(torch,protocol.reference_seed+k,count,protocol.reference_epochs)==proof['epoch_order_sha256'],'Teacher epoch order mismatch')
        require(len(proof['history'])==protocol.reference_epochs and np.isfinite(proof['history']).all(),'Incomplete teacher training history')
        for field in ('mean','std'):
            value=ck['feature_'+field].numpy()
            require(value.shape==(85,) and np.isfinite(value).all(),'Invalid teacher normalizer')
            if field=='std':require((value>0).all(),'Teacher std must be positive')
            require(array_digest(value)==proof[f'normalizer_{field}_sha256'],'Teacher normalizer hash mismatch')
    return {'checkpoint_models':'all final hashes verified','student_initialization_and_orders':'reconstructed independently on CPU',
        'teacher_initialization_and_orders':'reconstructed independently on CPU','student_normalizer_sha256':normalizer,
        'teacher_normalization':'per-fold85 values checked against source report; raw input numeric reconstruction unavailable',
        'torch_audit_version':str(torch.__version__),'cuda_used':False}


def verify_protocol(config,run,complete,protocol):
    expected={'controls':list(CONTROLS),'seeds':list(protocol.seeds),'epochs':protocol.epochs,
        'reference_epochs':protocol.reference_epochs,
        'reference_folds':protocol.folds,'reference_seed':protocol.reference_seed,
        'fold_seed':protocol.fold_seed,'permutation_seed':protocol.permutation_seed,
        'expected_train_records':protocol.records,'batch_size':protocol.batch_size,
        'max_per_event':4,'reference_features':85,'weight_epsilon':.01,'weight_cap':25.,'ce_weight':.075,'bin_width':.1,
        'learning_rate':5e-4,'reference_learning_rate':5e-4,'sampling_seed':20261009,
        'ad_exponent_safety_bound':60.,'family':'instrument'}
    for key,value in expected.items():require(config.get(key)==value,f'Prespecified protocol mismatch: {key}')
    require(config['seconds'] in (1,3,5),'Unexpected input duration')
    require(complete['controls']==list(CONTROLS) and complete['seeds']==list(protocol.seeds),'Completion controls/seeds mismatch')
    require(run['train_records']==protocol.records,'Run TRAIN count mismatch')
    for key,value in config.items():require(run.get(key)==value,f'Run/identity config mismatch: {key}')
    runtime=config['runtime']
    require(runtime['deterministic_algorithms'] and runtime['cudnn_deterministic'] and not runtime['cudnn_benchmark'],
            'Deterministic training flags missing')
    require(runtime['CUBLAS_WORKSPACE_CONFIG'] in (':4096:8',':16:8'),'Missing deterministic cuBLAS configuration')


def audit_run(run_dir,pins,validation_reference,huber_run=None,protocol=Protocol()):
    run_dir=Path(run_dir);started=time.monotonic()
    complete,identity,manifest=verify_artifacts(run_dir,pins,protocol)
    config=identity['config'];run=read_json(run_dir/'run.json');verify_protocol(config,run,complete,protocol)
    inputs=read_json(run_dir/'input_identities.json')
    require(file_digest(validation_reference)==inputs['validation_reference_sha256'],'Original validation reference hash mismatch')
    original=load_npz(validation_reference);points=load_npz(run_dir/'predictions.npz')
    y,ids,names=original['targets'],original['event_ids'],original['trace_names']
    aligned(points,y,ids,names);require(np.array_equal(original['centers'],CENTERS),'Original magnitude grid differs')
    require(len(np.unique(names))==len(y),'Duplicate validation traces')
    require(len(np.unique(ids[y>=4]))==protocol.tail_events,'Expected fixed tail-event population differs')
    _,first,inverse=np.unique(ids,return_index=True,return_inverse=True)
    require(np.array_equal(y[first][inverse],y),'Inconsistent magnitude within validation event')
    ref=load_npz(run_dir/'reference_oof.npz');ref_report=read_json(run_dir/'reference_report.json')
    require(not set(ref['event_ids'])&set(ids),'TRAIN/validation event overlap')
    require(not set(ref['trace_names'])&set(names),'TRAIN/validation trace overlap')
    require(ref_report['input_identities']==inputs,'Reference input provenance differs')
    reference=verify_reference(ref,ref_report,protocol)
    traces=read_json(run_dir/'training_traces.json');history=read_json(run_dir/'history.json')
    expected_keys={f'{c}_seed{s}' for c in CONTROLS for s in protocol.seeds}
    require(set(traces)==set(history)==expected_keys,'Missing or extra arm/seed training evidence')
    checkpoints=verify_checkpoints(run_dir,ref,ref_report,traces,history,config,protocol)
    reported=read_json(run_dir/'metrics.json');metrics={};point_checks={};tail_rows=[]
    raw=original['logits'].astype(float);raw=np.exp(raw-raw.max(1,keepdims=True));raw/=raw.sum(1,keepdims=True)
    # Deliberately stricter than the loader's allowed re-extraction logit drift:
    # this is an additional empirical raw-output identity check, not a claim
    # that every loader-valid run must pass. Any failure needs separate analysis;
    # never loosen the check silently or label the training output invalid.
    require(np.max(np.abs(points['raw_mean']-(raw*CENTERS).sum(1)))<2e-12,'Raw mean differs from original reference')
    raw_median=CENTERS[np.minimum((raw.cumsum(1)<.5).sum(1),65)]
    require(np.array_equal(points['raw_median'],raw_median),'Raw median differs from original reference')
    for control in CONTROLS:
        data=load_npz(run_dir/f'{control}_probabilities.npz');aligned(data,y,ids,names)
        require(np.array_equal(data['centers'],CENTERS),'Control magnitude grid differs')
        values=[data[f'seed{s}'] for s in protocol.seeds]
        verify_ensemble(data['mean_probability'],values)
        for suffix,p32 in [(f'seed{s}',data[f'seed{s}']) for s in protocol.seeds]+[('ensemble',data['mean_probability'])]:
            key=control+'_'+suffix;p=normalized_probability(p32)
            mean,med=points[key+'_mean'],points[key+'_median']
            point_checks[key]=validate_points(p32,mean,med)
            for decision,prediction in [('mean',mean),('median',med)]:
                name=key+'_'+decision
                metrics[name]=recompute_metrics(y,prediction,ids,p)
                for field,expected in reported[name].items():
                    if field not in metrics[name]:continue
                    actual=metrics[name][field]
                    if expected is None:require(actual is None,f'Metric null mismatch: {name}/{field}')
                    elif isinstance(expected,str):require(actual==expected,f'Metric status mismatch: {name}/{field}')
                    else:require(actual is not None and abs(actual-expected)<2e-6,f'Reported metric mismatch: {name}/{field}')
                for event in sorted(np.unique(ids[y>=4]).tolist()):
                    mask=ids==event
                    tail_rows.append({'arm':control,'seed_or_ensemble':suffix,'decision':decision,'event_id':event,
                        'magnitude':float(y[mask][0]),'records':int(mask.sum()),
                        'mae':float(np.abs(prediction[mask]-y[mask]).mean()),'bias':float((prediction[mask]-y[mask]).mean()),
                        'crps':float(continuous_crps(p[mask],y[mask]).mean())})
    deltas={}
    for suffix in [f'seed{s}' for s in protocol.seeds]+['ensemble']:
        for decision in ('mean','median'):
            candidate=metrics[f'context_ce_{suffix}_{decision}']
            for comparator in ('crps_ce','shuffled_ce','average_ce','ranked_bce_ce','properized_ad_ce'):
                base=metrics[f'{comparator}_{suffix}_{decision}']
                deltas[f'context_minus_{comparator}_{suffix}_{decision}']={k:candidate[k]-base[k]
                    for k in ('mae','medae','m4_mae','m4_event_macro_mae','m5_mae','cvar95','crps','nll')
                    if candidate[k] is not None and base[k] is not None}
    indexed={(v['arm'],v['seed_or_ensemble'],v['decision'],v['event_id']):v for v in tail_rows}
    for row in tail_rows:
        if row['arm']=='context_ce':
            row['mae_delta_vs']={c:row['mae']-indexed[(c,row['seed_or_ensemble'],row['decision'],row['event_id'])]['mae']
                                 for c in CONTROLS if c!='context_ce'}
    baseline=None
    if huber_run is not None:
        huber_run=Path(huber_run);hr=read_json(huber_run/'run.json')
        require(hr['train_records']==979487 and hr['seconds']==config['seconds'],'Full-data Huber comparison budget/duration differs')
        hp=load_npz(huber_run/'instrument_probabilities.npz');aligned(hp,y,ids,names)
        require(np.array_equal(hp['centers'],CENTERS),'Huber grid differs')
        hd=load_npz(huber_run/'predictions.npz');aligned(hd,y,ids,names)
        baseline={'status':'Descriptive different-data-budget reference; no causal score attribution',
            'train_records':979487,'pilot_train_records':protocol.records,
            'baseline_run_sha256':file_digest(huber_run/'run.json'),
            'baseline_provenance_boundary':'Older runner has no COMPLETE or artifact manifest; comparison files hashed and identities aligned only',
            'baseline_probability_sha256':file_digest(huber_run/'instrument_probabilities.npz'),
            'baseline_predictions_sha256':file_digest(huber_run/'predictions.npz'),'metrics':{},'context_minus_huber':{}}
        for suffix,p32 in [(f'seed{s}',hp[f'seed{s}']) for s in protocol.seeds]+[('ensemble',hp['mean_probability'])]:
            p=normalized_probability(p32)
            validate_points(p32,hd[f'instrument_{suffix}_mean'],hd[f'instrument_{suffix}_median'])
            for decision in ('mean','median'):
                key=suffix+'_'+decision;m=recompute_metrics(y,hd[f'instrument_{key}'],ids,p);baseline['metrics'][key]=m
                candidate=metrics[f'context_ce_{key}']
                baseline['context_minus_huber'][key]={k:candidate[k]-m[k] for k in ('mae','medae','m4_mae','m4_event_macro_mae','m5_mae','cvar95','crps','nll')
                                                     if candidate[k] is not None and m[k] is not None}
    return {'status':'complete CPU artifact/metric audit with stated normalization boundary',
        'run_directory':str(run_dir),'seconds':config['seconds'],'source_commit':pins['commit'],
        'audit_source_sha256':file_digest(__file__),
        'manifest_sha256':file_digest(run_dir/'artifacts.json'),'source_pins_sha256':hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest(),
        'artifacts_verified':len(manifest),'protocol':config,'reference':reference,'checkpoints':checkpoints,
        'validation_records':len(y),'validation_events':len(np.unique(ids)),'m4_events':protocol.tail_events,
        'm5_events':len(np.unique(ids[y>=5])),'metrics':metrics,'context_deltas':deltas,'tail_events':tail_rows,
        'point_rounding_checks':point_checks,'full_data_huber':baseline,
        'gradient_diagnostics':{k:{f:v[f] for f in ('preclip_gradient_norm_mean','preclip_gradient_norm_max','gradient_clipped_fraction')} for k,v in traces.items()},
        'limits':['Reused exploratory validation;13 tail events in the real protocol, no independent SOTA claim',
                  'No raw85 archive: normalizer values hash-verified but not numerically reconstructed',
                  'NLL uses saved float32 PMF; zero target probabilities are infinite, never floored',
                  'No training/inference performed; CPU parameter initialization and shuffle reconstruction only'],
        'elapsed_seconds':time.monotonic()-started}


def write_report(result,destination):
    """Write final JSON atomically plus directly inspectable parallel tables."""
    destination=Path(destination)
    require(not destination.exists(),'Audit output must be fresh')
    destination.mkdir(parents=True)
    metrics=[dict(name=k,**v) for k,v in result['metrics'].items()]
    with (destination/'metrics.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(metrics[0]));writer.writeheader();writer.writerows(metrics)
    tail=[]
    for row in result['tail_events']:
        value={k:v for k,v in row.items() if k!='mae_delta_vs'}
        value.update({'delta_vs_'+k:v for k,v in row.get('mae_delta_vs',{}).items()});tail.append(value)
    fields=list(dict.fromkeys(k for row in tail for k in row))
    with (destination/'tail_events.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(tail)
    lines=[f"# Independent {result['seconds']} s contextual-score audit",'',result['status'],
        '',f"Validated {result['artifacts_verified']} manifested files; {result['validation_records']} validation recordings, "
           f"{result['validation_events']} events, {result['m4_events']} M≥4 events and {result['m5_events']} M≥5 events.",
        '', 'Each row below uses the ensemble mean decision. All seed/median results and individual tail-event comparisons are in the CSV/JSON files.',
        '', '| Arm | MAE | MedAE | M≥4 MAE | M≥4 event MAE | M≥5 MAE | CVaR95 | CRPS | NLL |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm in CONTROLS:
        m=result['metrics'][arm+'_ensemble_mean']
        values=[m[k] for k in ('mae','medae','m4_mae','m4_event_macro_mae','m5_mae','cvar95','crps','nll')]
        lines.append('| '+arm+' | '+' | '.join('NA' if v is None else f'{v:.6f}' for v in values)+' |')
    lines.extend(['','Context-only benefit requires improvement over both shuffled and average weights, '
        'with comparison to ranked BCE and properized AD. Improvement over ordinary CRPS alone cannot establish a context-specific effect.',
        '', 'Normalizer provenance: '+result['reference']['normalizer_boundary']+'.','',*['- '+v for v in result['limits']]])
    (destination/'report.md').write_text('\n'.join(lines)+'\n')
    temp=destination/'audit.tmp';temp.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    temp.replace(destination/'audit.json')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--validation-reference',type=Path,required=True)
    parser.add_argument('--pins',type=Path,default=Path(__file__).with_name('source_pins.json'))
    parser.add_argument('--huber-run',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'Audit output must be fresh')
    result=audit_run(args.run,read_json(args.pins),args.validation_reference,args.huber_run)
    write_report(result,args.output)
    print(json.dumps({'status':result['status'],'seconds':result['seconds'],'output':str(args.output/'audit.json')},indent=2))


if __name__=='__main__':main()

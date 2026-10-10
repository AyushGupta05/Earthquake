"""Fixed random-feature ridge and paired event summaries; NumPy CPU only."""
import numpy as np

SEEDS = (20261009, 20261010)
BOOTSTRAP_SEED = 20261011
TARGETS = ('magnitude', 'distance_km', 'depth_km')


def checked_weights(weight, n):
    weight = np.asarray(weight, dtype=np.float64)
    if weight.shape != (n,) or not np.isfinite(weight).all() or (weight <= 0).any():
        raise ValueError('Weights must be positive finite and aligned')
    return weight


def normalization(x, weight):
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 2 or not np.isfinite(x).all() or not len(x):
        raise ValueError('Finite nonempty 2D fitting array required')
    w = checked_weights(weight, len(x))
    w = w/w.sum()
    mean = np.einsum('i,ij->j', w, x)
    variance = np.einsum('i,ij->j', w, (x-mean)**2)
    return mean, np.maximum(np.sqrt(np.maximum(variance, 0)), 1e-12)


def transform_target(raw):
    raw = np.asarray(raw, dtype=np.float64)
    if raw.ndim != 2 or raw.shape[1] != 3 or not np.isfinite(raw).all() or (raw[:,1:] < 0).any():
        raise ValueError('Targets must be finite M, nonnegative distance and depth')
    return np.column_stack((raw[:,0],np.log10(np.maximum(raw[:,1],1)),np.log1p(raw[:,2])))


def inverse_target(value):
    # No physical clipping: negative predicted depth is retained for reporting.
    with np.errstate(over='raise', invalid='raise'):
        result = np.column_stack((value[:,0],10.**value[:,1],np.expm1(value[:,2])))
    if not np.isfinite(result).all():
        raise ValueError('Nonfinite inverse-transformed predictions')
    return result


def random_map(seed):
    rng = np.random.default_rng(seed)
    return rng.normal(0,1/np.sqrt(127),size=(127,128)),rng.normal(size=128)


def basis(x, state):
    normalized = np.clip((x-state['input_mean'])/state['input_scale'],-8,8)
    normalized = normalized*state['mask']
    return np.concatenate((normalized,np.maximum(normalized@state['random_weight']+state['random_bias'],0)),axis=1)


def fit(x, target_raw, weight, mask, seed):
    x = np.asarray(x,dtype=np.float64)
    mask = np.asarray(mask,dtype=bool)
    if x.ndim != 2 or x.shape[1] != 127 or mask.shape != (127,):
        raise ValueError('The common127-slot design is required')
    weight = checked_weights(weight,len(x))
    target = transform_target(target_raw)
    if len(target) != len(x):
        raise ValueError('Target alignment mismatch')
    state = dict(mask=mask.copy(),seed=np.array(seed),ridge=np.array(.01),
                 fitted_coefficient_count=np.array(256*3))
    state['input_mean'],state['input_scale'] = normalization(x,weight)
    state['target_mean'],state['target_scale'] = normalization(target,weight)
    state['random_weight'],state['random_bias'] = random_map(seed)
    z = basis(x,state)
    state['basis_mean'],state['basis_scale'] = normalization(z,weight)
    z = (z-state['basis_mean'])/state['basis_scale']
    y = (target-state['target_mean'])/state['target_scale']
    w = weight/weight.sum()
    gram = z.T@(w[:,None]*z)
    gram.flat[::len(gram)+1] += .01
    state['coefficients'] = np.linalg.solve(gram,z.T@(w[:,None]*y))
    # Weighted basis and targets are centered, so the unpenalized standardized
    # intercept is zero analytically. target_mean supplies the fitted intercept.
    state['intercept_standardized'] = np.zeros(3)
    return state


def predict(x,state):
    x = np.asarray(x,dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 127 or not np.isfinite(x).all():
        raise ValueError('Finite127-slot prediction inputs required')
    z = (basis(x,state)-state['basis_mean'])/state['basis_scale']
    transformed = (z@state['coefficients']+state['intercept_standardized'])*state['target_scale']+state['target_mean']
    return inverse_target(transformed),transformed


def ensemble_predictions(predictions,transformed_predictions,valid):
    """Mean original-unit points; stable transforms retain underflowed depths.

    log1p(mean(expm1(z))) = log(mean(exp(z))). The log-sum-exp form
    remains finite if float64 expm1(z) has rounded a negative depth to -1.
    This is an exact mathematical identity, not clipping or calibration.
    """
    if len(predictions) != 2 or len(transformed_predictions) != 2:
        raise ValueError('Exactly the two preregistered seeds are required')
    mean = np.mean(predictions,axis=0)
    transformed = np.full_like(mean,np.nan)
    first,second = (x[valid] for x in transformed_predictions)
    transformed[valid,0] = mean[valid,0]
    transformed[valid,1] = (np.logaddexp(first[:,1]*np.log(10),second[:,1]*np.log(10))-np.log(2))/np.log(10)
    transformed[valid,2] = np.logaddexp(first[:,2],second[:,2])-np.log(2)
    return mean,transformed


def event_means(value,event):
    event_ids,inverse = np.unique(np.asarray(event),return_inverse=True)
    total = np.bincount(inverse,weights=np.asarray(value,dtype=float))
    count = np.bincount(inverse)
    return event_ids,total/count


def weighted_quantile(value,weight,q):
    order = np.argsort(value,kind='stable')
    index = np.searchsorted(np.cumsum(weight[order]),q*weight.sum(),side='left')
    return float(value[order[min(index,len(order)-1)]])


def weighted_cvar(value,weight,tail=.05):
    order = np.argsort(-value,kind='stable')
    w = weight[order]
    amount = tail*w.sum()
    included = np.minimum(w,np.maximum(amount-np.concatenate(([0.],np.cumsum(w)[:-1])),0))
    return float(np.dot(value[order],included)/amount)


def score(prediction,target,weight,event,transformed_prediction=None):
    if len(prediction) == 0:
        return {'records':0,'events':0}
    if prediction.shape != target.shape or prediction.shape[1] != 3 or not np.isfinite(prediction).all():
        raise ValueError('Finite aligned predictions required')
    weight = checked_weights(weight,len(target))
    result = {'records':len(target),'events':len(set(event)), 'targets':{}, 'tail':{},
              'physical_invalid_predictions':{'negative_depth':int((prediction[:,2]<0).sum()),
                                              'nonpositive_distance':int((prediction[:,1]<=0).sum()),
                                              'hypocentral_distance_below_depth':int((prediction[:,1]<prediction[:,2]).sum())}}
    for j,name in enumerate(TARGETS):
        error = prediction[:,j]-target[:,j]
        absolute = np.abs(error)
        _,event_mae = event_means(absolute,event)
        _,event_mse = event_means(error**2,event)
        result['targets'][name] = {'weighted_mae':float(np.average(absolute,weights=weight)),
                                   'weighted_rmse':float(np.sqrt(np.average(error**2,weights=weight))),
                                   'event_macro_mae':float(event_mae.mean()),
                                   'event_macro_rmse':float(np.sqrt(event_mse).mean())}
    absolute = np.abs(prediction[:,0]-target[:,0])
    result['magnitude_medae'] = weighted_quantile(absolute,weight,.5)
    result['magnitude_cvar95'] = weighted_cvar(absolute,weight)
    for threshold in (4,5):
        selected = target[:,0] >= threshold
        if not selected.any():
            result['tail'][str(threshold)] = {'records':0,'events':0}
            continue
        error = prediction[selected,0]-target[selected,0]
        _,event_mae = event_means(np.abs(error),np.asarray(event)[selected])
        _,event_bias = event_means(error,np.asarray(event)[selected])
        result['tail'][str(threshold)] = {'records':int(selected.sum()),'events':len(event_mae),
            'weighted_mae':float(np.average(np.abs(error),weights=weight[selected])),
            'weighted_bias':float(np.average(error,weights=weight[selected])),
            'event_macro_mae':float(event_mae.mean()),'event_macro_bias':float(event_bias.mean())}
    if transformed_prediction is not None:
        truth = transform_target(target)
        result['transformed_space'] = {}
        for j,name in enumerate(('magnitude','log10_distance','log1p_depth')):
            error = transformed_prediction[:,j]-truth[:,j]
            _,event_mae = event_means(np.abs(error),event)
            result['transformed_space'][name] = {'weighted_mae':float(np.average(np.abs(error),weights=weight)),
                'weighted_rmse':float(np.sqrt(np.average(error**2,weights=weight))),
                'event_macro_mae':float(event_mae.mean())}
    return result


def paired_bootstrap(full,diagonal,target,weight,event,repetitions=1000):
    """Resample events, retain all their rows, pair F and D in every replicate."""
    weight = checked_weights(weight,len(target))
    event = np.asarray(event)
    delta = np.abs(full[:,0]-target[:,0])-np.abs(diagonal[:,0]-target[:,0])
    ids,inverse = np.unique(event,return_inverse=True)
    if not len(ids):
        return {'events':0}
    total = np.bincount(inverse,weights=weight*delta)
    mass = np.bincount(inverse,weights=weight)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = []
    for start in range(0,repetitions,32):
        sample = rng.integers(0,len(ids),size=(min(32,repetitions-start),len(ids)))
        draws.extend((total[sample].sum(1)/mass[sample].sum(1)).tolist())
    result = {'events':len(ids),'replicates':repetitions,'seed':BOOTSTRAP_SEED,
              'weighted_magnitude_mae_delta':float(total.sum()/mass.sum()),
              'weighted_magnitude_mae_ci95':np.quantile(draws,[.025,.975]).tolist()}
    tail = target[:,0] >= 4
    _,tail_delta = event_means(delta[tail],event[tail])
    result['tail_events'] = len(tail_delta)
    if len(tail_delta):
        draws = []
        for start in range(0,repetitions,32):
            sample = rng.integers(0,len(tail_delta),size=(min(32,repetitions-start),len(tail_delta)))
            draws.extend(tail_delta[sample].mean(1).tolist())
        result['m4_event_macro_mae_delta'] = float(tail_delta.mean())
        result['m4_event_macro_mae_ci95'] = np.quantile(draws,[.025,.975]).tolist()
    return result


def gate(comparisons):
    """All6 horizon/subset comparisons required; no best-horizon selection."""
    expected = {(t,s) for t in (1,3,5) for s in ('eval_seen','eval_held')}
    if {(r['seconds'],r['subset']) for r in comparisons} != expected or len(comparisons) != 6:
        return {'pass':False,'status':'incomplete','reason':'All six horizon/subset comparisons required'}
    checks,geometry = [],{name:True for name in ('distance_km','depth_km')}
    enough = all(r['F']['tail'].get('4',{}).get('events',0) >= 20 for r in comparisons)
    for row in comparisons:
        full,diagonal,boot = row['F'],row['D'],row['bootstrap']
        tail_f,tail_d = full['tail'].get('4',{}),diagonal['tail'].get('4',{})
        passed = (full['targets']['magnitude']['weighted_mae']-diagonal['targets']['magnitude']['weighted_mae'] <= .002
                  and full['magnitude_medae']-diagonal['magnitude_medae'] <= .002
                  and tail_f.get('event_macro_mae',np.inf)-tail_d.get('event_macro_mae',0) <= -.02
                  and all(v <= 0 for v in row['seed_m4_event_macro_deltas'])
                  and len(row['seed_m4_event_macro_deltas']) == 2
                  and boot.get('weighted_magnitude_mae_ci95',[0,np.inf])[1] <= .005
                  and boot.get('m4_event_macro_mae_ci95',[0,np.inf])[1] < 0
                  and row['valid_fraction'] >= .9)
        checks.append({'seconds':row['seconds'],'subset':row['subset'],'non_geometry_pass':bool(passed)})
        for name in geometry:
            geometry[name] &= (diagonal['targets'][name]['event_macro_mae'] > 0 and
                               full['targets'][name]['event_macro_mae'] <= .95*diagonal['targets'][name]['event_macro_mae'])
    status = 'inconclusive_tail_sample' if not enough else ('pass' if all(c['non_geometry_pass'] for c in checks) and any(geometry.values()) else 'failed')
    return {'pass':status=='pass','status':status,'geometry_all_six':geometry,'checks':checks,
            'scope':'Exploratory information gate only; no distribution, novelty or EEW superiority claim'}

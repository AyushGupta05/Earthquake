"""Fixed event-level reporting; no checkpoint/optimizer selection consumes this."""
import math
import numpy as np

TIMES = (1, 3, 5)
ACTIONS = ('mean', 'median')


def error_metrics(error, signed, target):
    if not len(error):raise ValueError('Empty evaluation cohort')
    tail = target >= 5.5
    worst = max(1, int(np.ceil(.05 * len(error))))
    return {'events':len(error), 'mae':float(error.mean()), 'medae':float(np.median(error)),
            'bias':float(signed.mean()), 'cvar95':float(np.sort(error)[-worst:].mean()),
            'p95':float(np.quantile(error,.95)), 'maximum':float(error.max()),
            'tail_events':int(tail.sum()), 'tail_mae':float(error[tail].mean()) if tail.any() else None,
            'tail_medae':float(np.median(error[tail])) if tail.any() else None}


def validate_predictions(p):
    ids, target = np.asarray(p['event_ids']), np.asarray(p['targets'])
    if ids.ndim!=1 or target.shape!=ids.shape or not len(ids) or len(set(ids.tolist()))!=len(ids) or not np.isfinite(target).all():
        raise ValueError('Invalid aligned event identities/targets')
    for t in TIMES:
        for name in (*ACTIONS, 'nll', 'crps'):
            v=np.asarray(p[f'{name}_{t}s'])
            if v.shape!=target.shape or not np.isfinite(v).all():raise ValueError('Nonfinite/misaligned prediction score')
    return target


def add_proper_scores(predictions, team, trainer):
    import torch
    result=dict(predictions); y=torch.from_numpy(result['targets']).double()
    for t in TIMES:
        mixture={k:torch.from_numpy(result[f'{k}_{t}s']).double() for k in ('logits','weights','means','scales')}
        if any(v.shape!=(len(y),5) or not torch.isfinite(v).all() for v in mixture.values()):raise ValueError('Invalid five-component mixture')
        if (mixture['scales']<=0).any() or (mixture['weights']<0).any() or not torch.allclose(mixture['weights'].sum(-1),torch.ones_like(y),atol=1e-6,rtol=0):raise ValueError('Invalid mixture mass/scales')
        result[f'nll_{t}s']=(-team.mixture_log_prob(mixture,y)).numpy()
        result[f'crps_{t}s']=trainer.gaussian_mixture_crps(mixture,y).numpy()
    validate_predictions(result)
    return result


def scores(predictions):
    y=validate_predictions(predictions); result={}
    for t in TIMES:
        result[str(t)]={}
        for action in ACTIONS:
            signed=predictions[f'{action}_{t}s']-y
            result[str(t)][action]=error_metrics(np.abs(signed),signed,y)
        result[str(t)].update(proper_nll=float(predictions[f'nll_{t}s'].mean()),crps=float(predictions[f'crps_{t}s'].mean()))
    tail=np.flatnonzero(y>=5.5)
    return {'deadlines':result,'mean_mae_equal_deadline_average':float(np.mean([result[str(t)]['mean']['mae'] for t in TIMES])),
            'tail_cases':[{'event_id':str(predictions['event_ids'][i]),'magnitude':float(y[i]),
                           'mean_error':{str(t):float(predictions[f'mean_{t}s'][i]-y[i]) for t in TIMES},
                           'median_error':{str(t):float(predictions[f'median_{t}s'][i]-y[i]) for t in TIMES}} for i in tail]}


def _statistics(p, indices):
    y=p['targets'][indices]; result={}
    for t in TIMES:
        for action in ACTIONS:
            signed=p[f'{action}_{t}s'][indices]-y
            m=error_metrics(np.abs(signed),signed,y)
            for key in ('mae','medae','bias','cvar95','p95','maximum','tail_mae','tail_medae'):
                result[f'{t}.{action}.{key}']=m[key]
        for key in ('nll','crps'):result[f'{t}.{key}']=float(p[f'{key}_{t}s'][indices].mean())
    result['equal_deadline_mean_mae']=float(np.mean([result[f'{t}.mean.mae'] for t in TIMES]))
    return result


def paired_comparison(candidate, reference, *, draws=2000, seed=20261013):
    """Same event bootstrap indices across both models AND all three deadlines."""
    y=validate_predictions(candidate); validate_predictions(reference)
    if not np.array_equal(candidate['event_ids'],reference['event_ids']) or not np.array_equal(y,reference['targets']):
        raise ValueError('Paired event/target identity mismatch')
    if type(draws) is not int or draws<1:raise ValueError('Positive integer bootstrap draws required')
    index=np.arange(len(y)); c=_statistics(candidate,index); r=_statistics(reference,index)
    delta={k:c[k]-r[k] if c[k] is not None else None for k in c}
    samples={k:[] for k in delta}; rng=np.random.default_rng(seed)
    for _ in range(draws):
        ix=rng.integers(0,len(y),len(y)); c=_statistics(candidate,ix); r=_statistics(reference,ix)
        for key in samples:
            if c[key] is not None:samples[key].append(c[key]-r[key])
    intervals={k:{'low':float(np.quantile(v,.025)) if v else None,'high':float(np.quantile(v,.975)) if v else None,
                   'valid_draws':len(v),'requested_draws':draws} for k,v in samples.items()}
    return {'delta_discrete_minus_source':delta,'paired_event_ci95':intervals,'events':len(y),'tail_events':int((y>=5.5).sum()),
            'bootstrap_seed':seed,'bootstrap_draws':draws,'tail_interval_warning':'Descriptive only; only2 calibration and1 DEV tail event. Undefined zero-tail resamples omitted with counts retained; no tail gate.',
            'event_dependence_warning':'Events are not independent earthquake sequences; two fitted seeds do not establish population replication.'}


def frozen_gate(comparisons):
    if set(comparisons)!={'20261011','20261012'}:raise ValueError('Both prespecified seeds required')
    checks={}
    for seed,row in comparisons.items():
        delta=row['delta_discrete_minus_source']; ci=row['paired_event_ci95']
        point=delta['equal_deadline_mean_mae']<0 and all(delta[f'{t}.mean.{k}']<=.002 for t in TIMES for k in ('mae','medae'))
        uncertainty=ci['equal_deadline_mean_mae']['high']<0
        checks[seed]={'point_and_margin':point,'bulk_ci_excludes_no_benefit':uncertainty,
                      'proper_nll_tradeoff':any(delta[f'{t}.nll']>0 for t in TIMES),
                      'mean_worst_error_regression':{str(t):[k for k in ('cvar95','p95','maximum') if delta[f'{t}.mean.{k}']>0] for t in TIMES}}
    points=all(x['point_and_margin'] for x in checks.values()); precision=all(x['bulk_ci_excludes_no_benefit'] for x in checks.values())
    return {'status':'failed' if not points else 'pass' if precision else 'inconclusive', 'point_criteria_pass':points,
            'checks':checks,'scope':'DEV primary known-method clock-allocation criterion; not a rare-magnitude or universal distributional improvement claim. Calibration is supporting only.'}

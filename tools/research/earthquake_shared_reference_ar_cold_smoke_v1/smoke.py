"""Bound cold-runtime synthetic smoke only; no real inputs, claims or file writes."""
import math
import struct
import time

SEED = 20261013
HORIZONS = (1, 3, 5)
Q = (.025, .1, .25, .5, .75, .9, .975)


class SmokeFailure(ValueError):
    def __init__(self, reason, evidence):
        super().__init__(reason)
        self.evidence = evidence


def need(value, reason):
    if not value:
        raise ValueError(reason)


def invented():
    """The complete fixed synthetic population: three mathematical rows, no metadata."""
    coefficients = [[.1, .3, .01, .015, .3, math.log(math.expm1(.95))],
                    [-.1, .25, -.01, .02, -.2, math.log(math.expm1(.85))],
                    [.05, .2, .02, .01, .8, math.log(math.expm1(1.05))]]
    nuisance = [[(i-5.5)*.01, (i-5.5)*-.015, (i-5.5)*.02] for i in range(12)]
    rows = [dict(horizon=h, offset=0, target=3.3+.1*h,
                 marks=[[.2+.03*j+.05*c+.01*j*c for c in range(3)] for j in range(4*h)])
            for h in HORIZONS]
    return coefficients, nuisance, rows


def producer(groups, progress, tick, clock):
    operator = groups['gaussian']['gaussian_operator']
    kernel = groups['kernel']['kernel']
    torch = operator.torch
    need(kernel.torch is torch, 'kernel_torch_identity')
    torch.manual_seed(SEED)
    prior = operator.Prior(2)
    prior.initialize(3.5, .7)  # Fixed invented location/scale, never target estimation.
    coeff, noise, rows = invented()
    coefficients = torch.nn.Parameter(torch.tensor(coeff, dtype=torch.float64))
    parameters = list(prior.parameters()) + [coefficients]
    progress['current_work'] = dict(kind='adam', phase='optimizer_construction', step=0)
    optimizer = torch.optim.Adam(parameters, lr=1e-3)
    context = torch.tensor([[.2, -.1], [.1, .3], [-.15, .25]], dtype=torch.float64)
    marks = tuple(torch.tensor(r['marks'], dtype=torch.float64) for r in rows)
    nu = torch.tensor([noise]*3, dtype=torch.float64)
    targets = torch.tensor([r['target'] for r in rows], dtype=torch.float64)
    need(all(p.dtype == torch.float64 and p.device.type == 'cpu' for p in parameters), 'cpu_float64')
    for update in range(1, 4):
        progress['current_work'] = dict(kind='adam', phase='forward', step=update)
        tick(); optimizer.zero_grad(set_to_none=True)
        predictions = [prior(v) for v in context]
        batch = tuple(torch.stack([v[k] for v in predictions]) for k in range(3))
        result = kernel.marked_nll(batch, marks, coefficients, nu, targets, 'L', 3.5,
                                   HORIZONS, (0, 0, 0), processing_begin=clock())
        need(tuple(result['mu'].shape) == (3, 60)
             and bool((torch.logsumexp(result['logw'], 1).detach().abs() <= 1e-12).all()), 'kernel_components')
        loss = result['nll'].mean()
        need(bool(torch.isfinite(loss)), 'loss_finite')
        progress['current_work']['phase'] = 'backward'
        loss.backward()
        need(all(p.grad is not None and bool(torch.isfinite(p.grad).all())
                 and bool((p.grad != 0).any()) for p in parameters), 'genuine_gradients')
        need(bool((coefficients.grad != 0).all()), 'all18_coefficient_gradients')
        gradient_l1 = math.fsum(float(p.grad.detach().abs().sum()) for p in parameters)
        before = [p.detach().clone() for p in parameters]
        progress['current_work']['phase'] = 'step'
        tick(); progress['optimizer_step_calls'] = update
        optimizer.step()
        need(all(bool(torch.isfinite(p).all()) for p in parameters), 'parameter_finite')
        need(all(int(optimizer.state[p]['step']) == update for p in parameters), 'adam_step')
        delta = max(float((p.detach()-b).abs().max()) for p, b in zip(parameters, before))
        need(math.isfinite(delta) and delta > 0, 'parameter_change')
        progress['updates'].append(dict(step=update, preupdate_loss=float(loss.detach()),
                                        gradient_l1=gradient_l1, max_parameter_change=delta,
                                        density_points=list(result['density_points'])))
        progress['synthetic_steps'] = update
        tick()
    progress.pop('current_work', None)
    return dict(parameters=sum(p.numel() for p in parameters), rows=3, components=60,
                device='cpu', dtype='float64', seed=SEED)


def independent(groups, progress, tick, clock):
    core = groups['auditor']['ar_core']; np = core.np
    coefficients, nuisance, rows = invented()
    prior = [np.asarray([math.log(.2)]*5, dtype=np.float64),
             np.asarray([3.1, 3.3, 3.5, 3.7, 3.9], dtype=np.float64),
             np.asarray([.6, .65, .7, .75, .8], dtype=np.float64)]
    for row in rows:
        current = dict(kind='proper', horizon=row['horizon'], phase='completion', scores={})
        progress['current_work'] = current
        tick(); budget = core.Budget(clock())
        reference = core.build_reference(prior, np.asarray(row['marks'], dtype=np.float64),
                    np.asarray(coefficients, dtype=np.float64), np.asarray(nuisance, dtype=np.float64),
                    3.5, row['horizon'], row['offset'], budget=budget)
        mix = core.complete(reference, budget)
        need(len(mix.mu) == 60 and mix.noise.shape == (12,), 'independent_components')
        current['phase'] = 'scores'
        score = mix.scores(row['target'], crosscheck=True, evidence=current['scores'])
        need(all(math.isfinite(float(score[k])) for k in ('mean','median','nll','crps','pit'))
             and score['crps'] >= 0 and 0 <= score['pit'] <= 1, 'proper_finite')
        need(set(score['quantiles']) == {str(q) for q in Q}
             and all(math.isfinite(float(v)) for v in score['quantiles'].values()), 'quantiles_finite')
        values = [float(score['quantiles'][str(q)]) for q in Q]
        need(values == sorted(values), 'quantiles_order')
        probabilities = [float(mix.cdf(v)) for v in values]
        need(all(abs(p-q) <= 1e-6 for p,q in zip(probabilities,Q)), 'quantile_cdf')
        noise_mass = math.fsum(float(v) for v in mix.noise)
        need(abs(noise_mass-1.) <= 1e-12 and bool((mix.noise >= 0).all()), 'noise_normalization')
        budget.tick(); tick()
        progress['records'].append(dict(horizon=row['horizon'], components=60, noise_mass=noise_mass,
              log_normalizer=float(mix.logz), scores=score,
              work=dict(density_points=budget.points, scalar_terms=budget.terms)))
    progress.pop('current_work', None)
    return dict(rows=3, components=60, device='cpu', dtype='float64', crosscheck='cdf-integral-crps')


def failure_numeric(value):
    if type(value) is float and not math.isfinite(value):
        return dict(rejected_float64_hex=struct.pack('<d', value).hex())
    if type(value) is dict:
        return {k:failure_numeric(v) for k,v in value.items()}
    if type(value) in (tuple,list):
        return [failure_numeric(v) for v in value]
    return value


def run(mode, config_raw, *, raw_pin, expected_config_pin, io, sb, adapter,
        processing_begin, check, prefix, clock=time.monotonic):
    """ROOT supplies positive raw/canonical pins, before-import clock and live checks."""
    progress = dict(mode=mode, synthetic_steps=0, scienceactual=0, updates=[], records=[], phase='entry')
    def tick():
        check(); now = clock()
        need(type(processing_begin) in (int,float) and math.isfinite(processing_begin)
             and type(now) in (int,float) and math.isfinite(now)
             and 0 <= processing_begin <= now and now-processing_begin <= 300, 'source_deadline')
    def record_begin():
        # Frozen math uses a 10s record clock. Cap it by the inherited source
        # deadline too, without incorrectly making the entire import lane 10s.
        tick(); return min(clock(), processing_begin+290.)
    try:
        tick(); need(type(mode) is str and mode in ('producer','independent'), 'mode')
        need(type(config_raw) is bytes and len(config_raw) <= 16*1024*1024
             and io.pin(config_raw) == raw_pin, 'config_raw_pin')
        config = io.json_read(config_raw)
        need(io.pin(io.canonical(config)) == expected_config_pin, 'config_canonical_pin')
        progress['phase'] = 'cold_load'
        with adapter.load(mode, config, expected_config_pin=expected_config_pin,
                          io=io, sb=sb, check=tick, prefix=prefix) as bound:
            need(bound['mode'] == mode and bound['adapter_config_pin'] == expected_config_pin, 'bound_identity')
            progress['versions'] = dict(bound['observed_versions'])
            progress['module_identities'] = {role:{name:dict(name=m.__name__, source=m.__file__)
                 for name,m in members.items()} for role,members in bound['groups'].items()}
            progress['phase'] = 'synthetic_work'; tick()
            detail = (producer if mode == 'producer' else independent)(bound['groups'], progress, tick, record_begin)
            progress['detail'] = detail; progress['phase'] = 'context_final_check'; tick()
        tick(); progress['phase'] = 'complete'; progress['status'] = 'complete'; progress['seconds'] = clock()-processing_begin
        need(math.isfinite(progress['seconds']) and progress['seconds'] <= 300, 'source_deadline')
        return progress
    except Exception as error:
        progress['status'] = 'incomplete'
        progress['reason'] = type(error).__name__+':'+str(error)[:256]
        raise SmokeFailure('synthetic_cold_smoke_incomplete', failure_numeric(progress)) from error

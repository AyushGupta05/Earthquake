"""Independent L all-factor Gaussian audit; NumPy/SciPy only, no model imports."""
import math
import numpy as np
from scipy.special import logsumexp
import proper_core as p

Budget = p.Budget
AuditFailure = p.AuditFailure
Mixture = p.Mixture
Q = p.Q
REFERENCE_KEYS = {'arm', 'prior', 'coefficients', 'rho', 'nu', 'mref', 'horizon',
                  'arrival_offset_ns', 'count', 'last_observed', 'facts'}
FACT_KEYS = {'cell', 'intercept', 'slope', 'sigma', 'value', 'previous', 'loading'}
SOURCE_KEYS = {'reference', 'log_weights', 'means', 'scales', 'log_normalizer',
               'noise_probabilities'}


def keys(value, expected):
    p.need(type(value) is dict and set(value) == set(expected), 'keys')


def same_array(actual, expected):
    p.array(actual, expected.shape)
    p.need(actual.tobytes() == expected.tobytes(), 'source_exact_array')


def bounded(value, shape):
    p.array(value, shape)
    p.need(bool((np.abs(value) <= 1e6).all()), 'input_representation')
    return value


def build_reference(prior, marks, coefficients, nu, mref, horizon,
                    arrival_offset_ns, *, budget):
    """Derive L facts from immutable prefix inputs; the caller owns their authority."""
    budget.tick()
    p.need(type(prior) in (list, tuple) and len(prior) == 3, 'prior')
    for value in prior:
        bounded(value, (5,))
    p.need(abs(float(logsumexp(prior[0]))) <= 1e-12
           and bool((prior[2] >= .05).all()), 'proper_prior')
    p.need(type(horizon) is int and horizon in (1, 3, 5)
           and type(arrival_offset_ns) is int and 0 <= arrival_offset_ns <= 750000000, 'clock')
    count = (horizon * 1000000000 - arrival_offset_ns) // 250000000
    bounded(marks, (count, 3)); bounded(coefficients, (3, 6)); bounded(nu, (12, 3))
    p.need(1 <= count <= 20 and bool((marks > -12).all()), 'allpositive_admission')
    p.need(type(mref) in (int, float) and math.isfinite(mref) and abs(mref) <= 1e6, 'mref')
    sigma = .05 + p.softplus(coefficients[:, 5])
    rho = coefficients[:, 4].copy(); facts = []
    for j, y in enumerate(marks):
        budget.charge(0, 3)
        t = math.log1p(.25 * j)
        beta = coefficients[:, 1] + coefficients[:, 3] * t
        previous = np.zeros(3) if j == 0 else marks[j - 1]
        intercept = coefficients[:, 0] + coefficients[:, 2] * t + rho * previous - beta * mref
        loading = np.ones(3) if j == 0 else 1. - rho
        for value in (intercept, beta, sigma):
            bounded(value, (3,))
        facts.append(dict(cell=j, intercept=intercept.copy(), slope=beta.copy(),
                          sigma=sigma.copy(), value=y.copy(), previous=previous.copy(),
                          loading=loading.copy()))
    result = dict(arm='L', prior=[v.copy() for v in prior], coefficients=coefficients.copy(),
                  rho=rho, nu=nu.copy(), mref=float(mref), horizon=horizon,
                  arrival_offset_ns=arrival_offset_ns, count=count,
                  last_observed=marks[-1].copy(), facts=facts)
    budget.tick()
    return result


def factor_bounds(reference):
    """Inherited affine bounds plus explicit subtraction error for 1-rho."""
    c = reference['coefficients']; mref = reference['mref']; out = []
    for f in reference['facts']:
        t = math.log1p(.25 * f['cell']); beta = f['slope']; a = f['intercept']
        eb = 32 * p.EPS * (1 + np.abs(c[:, 1]) + np.abs(c[:, 3] * t))
        ea = abs(mref) * eb + 32 * p.EPS * (1 + np.abs(c[:, 0]) + np.abs(c[:, 2] * t)
             + np.abs(c[:, 4] * f['previous']) + np.abs(beta * mref))
        es = 32 * p.EPS * (1 + np.abs(f['sigma']))
        ed = np.zeros(3) if f['cell'] == 0 else 4 * p.EPS * (1 + np.abs(c[:, 4]) + np.abs(f['loading']))
        bounds = dict(intercept=ea, slope=eb, sigma=es, loading=ed)
        for key, error in bounds.items():
            p.bound_ok(f[key], error)
        out.append(bounds)
    return out


def check_reference(reference, expected, prior_bounds):
    keys(reference, REFERENCE_KEYS)
    for key in ('arm', 'mref', 'horizon', 'arrival_offset_ns', 'count'):
        p.need(type(reference[key]) is type(expected[key]) and reference[key] == expected[key], 'source_metadata')
    for key in ('coefficients', 'rho', 'nu', 'last_observed'):
        same_array(reference[key], expected[key])
    p.need(type(reference['prior']) is list and len(reference['prior']) == 3
           and type(prior_bounds) in (list, tuple) and len(prior_bounds) == 3, 'source_prior')
    for actual, value, error in zip(reference['prior'], expected['prior'], prior_bounds):
        p.array(actual, (5,)); p.array(error, (5,)); p.compare(actual, value, error)
    p.need(type(reference['facts']) is list and len(reference['facts']) == expected['count'], 'source_count')
    for actual, value, bounds in zip(reference['facts'], expected['facts'], factor_bounds(expected)):
        keys(actual, FACT_KEYS)
        p.need(type(actual['cell']) is int and actual['cell'] == value['cell'], 'source_chronology')
        for key in ('value', 'previous'):
            same_array(actual[key], value[key])
        for key, error in bounds.items():
            p.array(actual[key], (3,)); p.compare(actual[key], value[key], error)


def complete(reference, budget):
    """Complete all L factors once, retaining the shared nuisance outside the product."""
    budget.tick(); keys(reference, REFERENCE_KEYS)
    p.need(type(reference['facts']) is list and 1 <= len(reference['facts']) <= 20, 'factor_count')
    # Re-derive before using any supplied loadings, clock, lag or nuisance declaration.
    for f in reference['facts']:
        keys(f, FACT_KEYS); p.array(f['value'], (3,))
    marks = np.ascontiguousarray([f['value'] for f in reference['facts']], dtype=np.float64)
    expected = build_reference(reference['prior'], marks, reference['coefficients'], reference['nu'],
                               reference['mref'], reference['horizon'], reference['arrival_offset_ns'], budget=budget)
    check_reference(reference, expected, [np.zeros(5) for _ in range(3)])
    logw, mu, sd = expected['prior']; nu = expected['nu']; facts = expected['facts']
    outw = []; outmu = []; outsd = []
    for noise in nu:
        for k in range(5):
            budget.charge(0, 9 * len(facts) + 1)
            v = []; b = []; s = []; ev = []
            for f in facts:
                for c in range(3):
                    y, a, bb, ss = (float(f[key][c]) for key in ('value', 'intercept', 'slope', 'sigma'))
                    d = float(f['loading'][c]); nn = float(noise[c]); product = d * nn
                    # Bound the new subtraction and product before inherited information/mean arithmetic.
                    ed = 0. if f['cell'] == 0 else 4 * p.EPS * (1 + abs(float(expected['rho'][c])) + abs(d))
                    en = abs(nn) * ed + 2 * p.EPS * abs(product)
                    vv = y - a - product - bb * float(mu[k])
                    ee = en + 8 * p.EPS * (abs(y) + abs(a) + abs(product) + abs(bb * float(mu[k])))
                    p.need(math.isfinite(vv) and math.isfinite(ee), 'residual_representation')
                    v.append(vv); ev.append(ee); b.append(bb); s.append(ss)
            precision = math.fsum((bb / ss) ** 2 for bb, ss in zip(b, s))
            A = 1 + sd[k] ** 2 * precision
            delta = sd[k] ** 2 * math.fsum(bb * vv / (ss * ss) for bb, vv, ss in zip(b, v, s)) / A
            mean = float(mu[k] + delta); sigma = float(sd[k] / math.sqrt(A))
            mean_error = p.completion_mean_error(float(mu[k]), float(sd[k]), v, ev, b, s, precision, A, delta, mean, sigma)
            residual = math.fsum(((vv - bb * delta) / ss) ** 2 for vv, bb, ss in zip(v, b, s))
            mass = float(logw[k] - math.log(12) - .5 * (residual + (delta / sd[k]) ** 2)
                         - math.fsum(math.log(ss) for ss in s) - len(s) * .5 * math.log(2 * math.pi) - .5 * math.log(A))
            p.need(all(math.isfinite(x) for x in (mean, sigma, mass)) and math.ulp(mass) <= 1e-10
                   and math.ulp(mean) <= 1e-10 * sigma and mean_error <= 1e-10 * sigma, 'completion_representation')
            outw.append(mass); outmu.append(mean); outsd.append(sigma)
    logz = float(logsumexp(outw)); p.need(math.ulp(logz) <= 1e-10, 'evidence_representation')
    mix = Mixture(np.asarray(outw) - logz, np.asarray(outmu), np.asarray(outsd), logz, budget)
    mix.noise = np.exp(mix.logw).reshape(12, 5).sum(1)
    budget.tick(); return mix


def verify_source(source, prior, marks, coefficients, nu, mref, horizon,
                  arrival_offset_ns, prior_bounds, *, budget):
    """Source evidence is checked against independently supplied inputs, not its own claims."""
    budget.tick(); keys(source, SOURCE_KEYS)
    expected = build_reference(prior, marks, coefficients, nu, mref, horizon, arrival_offset_ns, budget=budget)
    check_reference(source['reference'], expected, prior_bounds)
    mix = complete(expected, budget)
    for key, actual in (('log_weights', mix.logw), ('means', mix.mu), ('scales', mix.sd), ('noise_probabilities', mix.noise)):
        p.array(source[key], actual.shape)
        p.need(bool((np.abs(source[key] - actual) <= 1e-10 * (1 + np.abs(actual))).all()), 'completed_gaussian')
    value = source['log_normalizer']
    p.need(type(value) is float and math.isfinite(value) and abs(value - mix.logz) <= 1e-4, 'log_normalizer')
    budget.tick(); return mix

"""Four-parameter constrained likelihood with fitting-group-only statistics."""
import math
import time
from collections import Counter
import numpy as np
from scipy.optimize import minimize, nnls
from scipy.special import log_ndtr
from numerics import check_deadline, finite

LAMBDAS = (0., .1, 1., 10., 100.)


def event_weights(events):
    counts = Counter(e['group'] for e in events)
    if not counts:
        raise ValueError('empty_fitting_groups')
    return np.array([1/len(counts)/counts[e['group']] for e in events], dtype=np.float64)


def statistics(events):
    weights = event_weights(events)
    labels = np.array([e['mw'] for e in events], dtype=np.float64)
    mean = float(weights@labels)
    sd = max(float(math.sqrt(float(weights@((labels-mean)**2)))), .5)
    ages = np.array([math.log10(h['features']['u']) for e in events for h in e['horizons']])
    hw = np.repeat(weights/3, 3)
    age_mean = float(hw@ages)
    age_sd = math.sqrt(float(hw@((ages-age_mean)**2)))
    if np.all(ages == ages[0]):
        age_mean, age_sd = float(ages[0]), 0.0
    prior = {'mean': finite(mean), 'sd': finite(sd)}
    scaler = {'age_mean': finite(age_mean), 'age_sd': finite(age_sd)}
    return prior, scaler


def matrix(events, prior, scaler):
    weights = np.repeat(event_weights(events)/3, 3)
    x = np.array([[1., (e['mw']-prior['mean'])/prior['sd'],
                   0. if scaler['age_sd'] == 0 else
                   (math.log10(h['features']['u'])-scaler['age_mean'])/scaler['age_sd']]
                  for e in events for h in e['horizons']], dtype=np.float64)
    y = np.array([h['features']['y'] for e in events for h in e['horizons']])
    limits = np.array([h['features']['L'] for e in events for h in e['horizons']])
    censored = np.array([h['features']['censored'] for e in events for h in e['horizons']], dtype=bool)
    return x, y, limits, censored, weights


def objective(theta, x, y, limits, censored, weights, penalty, deadline):
    check_deadline(deadline)
    a, b, c, ls = theta
    sigma = math.exp(float(ls))
    mu = x@np.array([a,b,c])
    residual = (y-mu)/sigma
    z = (limits-mu)/sigma
    nll = np.log(sigma)+.5*math.log(2*math.pi)+.5*residual**2
    dmu = -residual/sigma
    dls = 1-residual**2
    if np.any(censored):
        zi = z[censored]
        lp = log_ndtr(zi)
        mills = np.exp(-.5*zi**2-.5*math.log(2*math.pi)-lp)
        nll[censored] = -lp
        dmu[censored] = mills/sigma
        dls[censored] = zi*mills
    loss = float(weights@nll+penalty*(b*b+c*c))
    grad = np.r_[x.T@(weights*dmu), weights@dls]
    grad[1] += 2*penalty*b
    grad[2] += 2*penalty*c
    if not math.isfinite(loss) or not np.all(np.isfinite(grad)):
        raise ArithmeticError('nonfinite_objective')
    return loss, grad


def fit(events, penalty, deadline):
    if type(penalty) not in (float,int) or penalty not in LAMBDAS:
        raise ValueError('fixed_penalties')
    begin = time.monotonic()
    fit_deadline = min(deadline, begin+10.)
    check_deadline(fit_deadline)
    prior, scaler = statistics(events)
    x, y, limits, censored, weights = matrix(events, prior, scaler)
    center_x = x[:,1:]-weights@x[:,1:]
    center_y = y-float(weights@y)
    slopes, _ = nnls(center_x*np.sqrt(weights)[:,None], center_y*np.sqrt(weights), maxiter=500)
    intercept = float(weights@y-(weights@x[:,1:])@slopes)
    residual = y-x@np.r_[intercept,slopes]
    sigma = max(math.sqrt(float(weights@(residual**2))), .1)
    initial = np.r_[intercept,slopes,math.log(sigma)]
    initial_sigma = sigma
    result = minimize(objective, initial, args=(x,y,limits,censored,weights,float(penalty),fit_deadline),
                      method='L-BFGS-B', jac=True,
                      bounds=((None,None),(0,None),(0,None),(math.log(.1),None)),
                      options={'maxiter':500,'maxfun':5000,'ftol':1e-10,'gtol':1e-6})
    check_deadline(fit_deadline)
    if not result.success or not np.all(np.isfinite(result.x)) or not math.isfinite(float(result.fun)):
        raise ArithmeticError('optimizer_nonconvergence')
    a,b,c,ls = map(float,result.x)
    sigma = math.exp(ls)
    if b < 0 or c < 0 or sigma < .1:
        raise ArithmeticError('optimizer_constraint_unknown')
    return {'parameters':[a,b,c,sigma], 'prior':prior,'scaler':scaler,'lambda':float(penalty),
            'training_groups':sorted({e['group'] for e in events}),
            'training_slots':[e['slot'] for e in events], 'objective':float(result.fun),
            'iterations':int(result.nit),'function_evaluations':int(result.nfev),
            'success':True,'elapsed_seconds':time.monotonic()-begin,
            'initial_parameters':[float(initial[0]),float(initial[1]),float(initial[2]),initial_sigma],
            'bound_hits':{'b':b==0.,'c':c==0.,'sigma':ls==math.log(.1)},
            'residual_sd_initial':float(math.sqrt(float(weights@(residual**2)))),
            'optimizer':'SciPy-L-BFGS-B-fixed-one-start'}

"""Source-only exact-form S/P/D batching; no optimizer, IO or inference scorer."""
import math
import time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


def need(ok, why):
    if not ok:
        raise ValueError(why)


def tensor(x, shape, bounded=True):
    need(type(x) in (torch.Tensor, nn.Parameter) and x.dtype == torch.float64
         and x.device.type == 'cpu' and tuple(x.shape) == shape
         and bool(torch.isfinite(x).all()), 'tensor')
    if bounded:
        need(bool((x.detach().abs() <= 1e6).all()), 'input_representation')


def ulp(x):
    """math.ulp for finite IEEE doubles; positive spacing even for negative powers."""
    x = np.asarray(x, dtype=np.float64)
    need(bool(np.isfinite(x).all()), 'nonfinite_ulp')
    _, exponent = np.frexp(np.abs(x))
    return np.ldexp(np.ones_like(x), np.where(x == 0, -1074, np.maximum(exponent - 53, -1074)))


def array(x):
    return x.detach().numpy()


def precision(x, label):
    need(bool(np.isfinite(array(x)).all()) and bool((ulp(array(x)) <= 1e-10).all()), label)


class Budget:
    def __init__(self, begin, batch):
        need(type(begin) in (int, float) and math.isfinite(begin)
             and 0 <= begin <= time.monotonic(), 'processing_begin')
        self.begin = begin
        self.points = np.zeros(batch, dtype=np.int64)
        self.check()

    def check(self, rows=None, components=0):
        if rows is not None:
            self.points[rows] += components
        need(bool((self.points <= 1000000).all()), 'evaluation_cap')
        need(time.monotonic() - self.begin <= 10, 'deadline')


def inputs(prior, targets):
    need(type(prior) in (tuple, list) and len(prior) == 3, 'prior')
    need(type(targets) is torch.Tensor and targets.ndim == 1, 'target')
    batch = len(targets)
    need(1 <= batch <= 24, 'batch')
    tensor(targets, (batch,), bounded=False)
    for x in prior:
        tensor(x, (batch, 5))
    logw, mu, sigma = prior
    need(bool((torch.logsumexp(logw, 1).detach().abs() <= 1e-12).all())
         and bool((sigma >= .05).all()), 'proper_prior')
    return batch


def finish(mass, mean, variance, targets, budget, direct=False):
    logz = targets.new_zeros(len(targets)) if direct else torch.logsumexp(mass, 1)
    precision(logz, 'evidence_precision')
    weights = mass if direct else mass - logz[:, None]
    scales = variance if direct else variance.sqrt()
    need(bool(torch.isfinite(weights).all()) and bool(torch.isfinite(mean).all())
         and bool(torch.isfinite(scales).all()) and bool((scales > 0).all()), 'posterior_nonfinite')
    rows = np.arange(len(targets))
    budget.check(rows, mean.shape[1])
    terms = weights - torch.log(scales) - .5 * math.log(2 * math.pi) \
        - .5 * ((targets[:, None] - mean) / scales).square()
    nll = -torch.logsumexp(terms, 1)
    precision(nll, 'target_precision')
    budget.check()
    return dict(nll=nll, logz=logz, logw=weights, mu=mean, sigma=scales,
                density_points=tuple(int(x) for x in budget.points))


def marked_nll(prior, marks, coeff, nu, targets, arm, mref, horizons, offsets,
               *, processing_begin):
    batch = inputs(prior, targets)
    budget = Budget(processing_begin, batch)
    tensor(coeff, (3, 6))
    tensor(nu, (batch, 12, 3))
    need(arm in ('S', 'P'), 'arm')
    need(type(mref) in (int, float) and math.isfinite(mref) and abs(mref) <= 1e6, 'mref')
    need(type(marks) is tuple and len(marks) == batch and type(horizons) is tuple
         and type(offsets) is tuple and len(horizons) == len(offsets) == batch, 'roster')
    lengths = []
    for x, h, offset in zip(marks, horizons, offsets):
        need(type(h) is int and h in (1, 3, 5) and type(offset) is int
             and 0 <= offset <= 750000000, 'clock')
        need(type(x) is torch.Tensor, 'marks')
        count = (h * 1000000000 - offset) // 250000000
        tensor(x, (count, 3))
        need(1 <= count <= 20 and bool((x > -12).all()), 'allpositive_admission')
        lengths.append(count)
    # Pad only transport: inactive rows never enter a recurrence or precision check.
    padded = torch.stack([F.pad(x.clone(), (0, 0, 0, max(lengths)-len(x))) for x in marks])
    support = nu.clone() if arm == 'S' else nu.new_zeros(batch, 1, 3)
    width = support.shape[1]
    logw, mu, sigma = (x.clone() for x in prior)
    mass = (logw[:, None, :] - math.log(width)).expand(batch, width, 5).reshape(batch, -1).clone()
    mean = mu[:, None, :].expand(batch, width, 5).reshape(batch, -1).clone()
    variance = sigma.square()[:, None, :].expand(batch, width, 5).reshape(batch, -1).clone()
    a, b, d, e, rho, rawsigma = coeff.unbind(1)
    scale = .05 + F.softplus(rawsigma)
    for j in range(max(lengths)):
        rows_np = np.flatnonzero(np.asarray(lengths) > j)
        rows = torch.from_numpy(rows_np)
        previous = padded[rows, j-1] if j else padded.new_zeros(len(rows), 3)
        t = math.log1p(.25 * j)
        beta = b + e * t
        intercept = a + d * t + rho * previous - beta * mref
        tensor(beta, (3,)); tensor(scale, (3,)); tensor(intercept, (len(rows), 3))
        local_mass = mass[rows]; local_mean = mean[rows]; local_var = variance[rows]
        for c in range(3):
            budget.check(rows_np, width * 5)
            center = (intercept[:, c, None, None] + support[rows, :, c, None]).expand(-1, width, 5).reshape(len(rows), -1)
            total = scale[c].square() + beta[c].square() * local_var
            innovation = padded[rows, j, c, None] - center - beta[c] * local_mean
            local_mass = local_mass - .5 * (torch.log(2 * math.pi * total) + innovation.square() / total)
            precision(local_mass, 'evidence_precision')
            first = local_mean * scale[c].square()
            second = local_var * beta[c] * (padded[rows, j, c, None] - center)
            newmean = (first + second) / total
            newvar = local_var * (scale[c].square() / total)
            f, g, n, denominator, sd = (array(x) for x in (first, second, newmean, total, newvar.sqrt()))
            bound = (4*ulp(f) + 6*ulp(g) + ulp(f+g))/denominator + 3*ulp(n)
            need(bool(np.isfinite(bound).all()) and bool((bound <= 1e-10*sd).all()), 'gaussian_mean_precision')
            local_mean, local_var = newmean, newvar
        mass = mass.index_copy(0, rows, local_mass)
        mean = mean.index_copy(0, rows, local_mean)
        variance = variance.index_copy(0, rows, local_var)
    return finish(mass, mean, variance, targets, budget)


def direct_nll(prior, summary, theta, tau, active, targets, *, processing_begin):
    batch = inputs(prior, targets)
    budget = Budget(processing_begin, batch)
    tensor(summary, (batch, 20))
    need(type(active) is tuple and len(set(active)) == len(active)
         and all(type(i) is int and 0 <= i < 20 and i not in (4, 9, 14) for i in active), 'capacity_schema')
    counts = (526+18, 526+len(active)+1)
    need(max(counts)/min(counts) <= 1.05, 'capacity_spread')
    tensor(theta, (len(active),)); tensor(tau, ())
    logw, mu, sigma = prior
    shift = (summary.clone()[:, list(active)] * theta).sum(1)
    mean = mu + shift[:, None]
    scales = .05 + torch.exp(tau) * (sigma-.05)
    inputs((logw, mean, scales), targets)
    return finish(logw, mean, scales, targets, budget, direct=True)


def loss24(nll):
    tensor(nll, (24,), bounded=False)
    return nll.sum()/24

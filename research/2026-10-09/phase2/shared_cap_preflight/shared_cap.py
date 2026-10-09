"""TRAIN-only amplitude-contrast density preflight; no deployed magnitude model.

The empirical cap index is not an identified physical rupture state. All scores
condition on the known magnitude. No source waveform or validation file is read.
"""
import hashlib
import math

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

PROTOCOL_SHA = '92b54f5f57cec682956ce5a0e2d584292cd85a83c8d7980ce9336bdc0e282c21'
FLOOR = .03 ** 2
ARMS = ('linear_gaussian', 'moment_matched', 'shared_cap')
COUNTERFACTUAL = 'moment_match_from_shared_cap'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def event_folds(ids, salt):
    return np.asarray([hashlib.sha256((salt + '\x1f' + str(x)).encode('utf8')).digest()[0] & 1
                       for x in ids], dtype=np.int8)


def contrasts(z, seconds):
    """At 3s, deliberately do not inspect the future coordinate, even for NaN."""
    if z.ndim != 2 or z.shape[1] != 2 or seconds not in (1, 3, 5):
        raise ValueError('Expected signed innovations N x 2 and deadline 1/3/5')
    if seconds == 1:
        return z[:, :0]
    first = z[:, 0]
    if seconds == 3:
        return first[:, None]
    return torch.stack((first, z[:, 1] + first.clamp_min(0)), dim=1)


def validate_arrays(data, protocol):
    n = protocol['expected_rows']
    for key in protocol['required_columns']:
        if key not in data or len(data[key]) != n:
            raise ValueError('Missing/wrong row count: ' + key)
    for key, shape in [('z', (n, 2)), ('valid', (n, 2)), ('above_floor', (n, 3)),
                       ('invalid_reason_code', (n, 2))]:
        if data[key].shape != shape:
            raise ValueError('Wrong shape: ' + key)
    if data['valid'].dtype != np.bool_ or data['above_floor'].dtype != np.bool_:
        raise ValueError('Masks must be boolean')
    for key in ('targets', 'row_index', 'physical_unit_z', 'event_ids', 'trace_names'):
        if data[key].shape != (n,):
            raise ValueError('Expected vector: ' + key)
    if not np.issubdtype(data['row_index'].dtype, np.integer) or np.any(np.diff(data['row_index']) <= 0):
        raise ValueError('Source rows must be unique and strictly increasing')
    for key in ('event_ids', 'trace_names'):
        if data[key].dtype.kind not in 'US' or np.any(data[key].astype(str) == ''):
            raise ValueError('Expected exact nonempty string identities')
        data[key] = data[key].astype(str)
    if len(np.unique(data['trace_names'])) != n:
        raise ValueError('Duplicate trace identity')
    if not np.isfinite(data['targets']).all() or not np.isfinite(data['z'][data['valid']]).all():
        raise ValueError('Nonfinite observed value/target')
    if not np.isin(data['physical_unit_z'], [0, 1, 2]).all():
        raise ValueError('Unknown physical unit')
    valid = data['valid']
    if np.any(valid[:, 1] & ~valid[:, 0]) or not np.array_equal(valid, data['invalid_reason_code'] == 0):
        raise ValueError('Cumulative masks and reason codes disagree')
    above = data['above_floor']
    if np.any(valid[:, 0] & ~(above[:, 0] & above[:, 1])) or np.any(valid[:, 1] & ~above[:, 2]):
        raise ValueError('A valid row is below the native floor')
    if np.any(valid.any(1) & (data['physical_unit_z'] == 0)):
        raise ValueError('Valid row has unknown physical units')
    _, inv = np.unique(data['event_ids'], return_inverse=True)
    lo = np.full(inv.max() + 1, np.inf)
    hi = np.full_like(lo, -np.inf)
    np.minimum.at(lo, inv, data['targets'])
    np.maximum.at(hi, inv, data['targets'])
    if np.max(hi - lo) > 1e-5:
        raise ValueError('Inconsistent per-event magnitude')
    return data


def equal_event_weights(ids):
    _, inv, counts = np.unique(ids, return_inverse=True, return_counts=True)
    w = 1. / counts[inv]
    return w / w.sum()


def covariance(raw):
    a, b, c = F.softplus(raw[0]), raw[1], F.softplus(raw[2])
    return torch.stack((torch.stack((a * a + FLOOR, a * b)),
                        torch.stack((a * b, b * b + c * c + FLOOR))))


def gaussian_logpdf(x, mean, cov):
    """Full normalized 1/2-dimensional density, including covariance determinant."""
    d = x.shape[-1]
    if d not in (1, 2) or mean.shape[-1] != d or cov.shape[-2:] != (d, d):
        raise ValueError('Expected matching 1D or 2D density')
    delta = x - mean
    if d == 1:
        var = cov[..., 0, 0]
        return -.5 * (math.log(2 * math.pi) + var.log() + delta[..., 0].square() / var)
    a, b, c = cov[..., 0, 0], cov[..., 0, 1], cov[..., 1, 1]
    det = a * c - b.square()
    q = (c * delta[..., 0].square() - 2 * b * delta[..., 0] * delta[..., 1]
         + a * delta[..., 1].square()) / det
    return -.5 * (2 * math.log(2 * math.pi) + det.log() + q)


def moment_match(weights, means, noise):
    mean = (weights[None, :, None] * means).sum(1)
    residual = means - mean[:, None]
    cov = noise + torch.einsum('k,nki,nkj->nij', weights, residual, residual)
    return mean, cov


def normal_cdf(x):
    return .5 * (1 + torch.erf(x / math.sqrt(2)))


class Density(nn.Module):
    def __init__(self, arm, initial):
        super().__init__()
        if arm not in ARMS + (COUNTERFACTUAL,):
            raise ValueError('Unknown arm')
        expected = 7 if arm == 'linear_gaussian' else 11
        if initial.shape != (expected,) or initial.dtype != torch.float64 or initial.device.type != 'cpu':
            raise ValueError('Expected CPU float64 raw parameters')
        self.arm = arm
        self.raw = nn.Parameter(initial.clone())

    def components(self, magnitude):
        p = self.raw
        if self.arm == 'linear_gaussian':
            mean = p[:2] + (magnitude[:, None] - 3) * p[2:4]
            return torch.ones(1, dtype=p.dtype), mean[:, None], covariance(p[4:])
        caps = torch.cumsum(torch.tensor([8., 4., 4.], dtype=p.dtype) * p[:3].sigmoid(), 0)
        kappa = .05 + 2.95 * p[3].sigmoid()
        weights = torch.softmax(torch.cat((p[4:6], p.new_zeros(1))), 0)
        bounds = caps[None] + p.new_tensor([-.5, 0, .5])[:, None]
        clipped = torch.minimum(magnitude[:, None, None], bounds[None])
        means = p[6:8] + kappa * (clipped[:, :, 1:] - clipped[:, :, :1])
        return weights, means, covariance(p[8:])

    def log_likelihood(self, z, magnitude, seconds):
        if magnitude.ndim != 1 or len(magnitude) != len(z):
            raise ValueError('Magnitude/observations must align')
        x = contrasts(z, seconds)
        if seconds == 1:
            return z.new_zeros(len(z))
        dim = x.shape[1]
        w, means, noise = self.components(magnitude)
        means, noise = means[..., :dim], noise[:dim, :dim]
        if self.arm == 'shared_cap':
            return torch.logsumexp(w.log()[None] + gaussian_logpdf(x[:, None], means, noise), 1)
        mean, cov = moment_match(w, means, noise)
        return gaussian_logpdf(x, mean, cov)

    def marginal_pit(self, z, magnitude, seconds):
        x = contrasts(z, seconds)
        if seconds == 1:
            return x
        dim = x.shape[1]
        w, means, noise = self.components(magnitude)
        means, noise = means[..., :dim], noise[:dim, :dim]
        if self.arm == 'shared_cap':
            standardized = (x[:, None] - means) / noise.diagonal().sqrt()
            return (w[None, :, None] * normal_cdf(standardized)).sum(1)
        mean, cov = moment_match(w, means, noise)
        return normal_cdf((x - mean) / cov.diagonal(dim1=-2, dim2=-1).sqrt())


def inverse_softplus(x):
    return x + torch.log(-torch.expm1(-x))


def initial_parameters(magnitude, observed, weights, seed, linear=False):
    """Only fit-fold observations enter this initializer; starts shared by both cap arms."""
    p = torch.zeros(7 if linear else 11, dtype=torch.float64)
    if linear:
        # Coarse reference: weighted mean intercept, zero slope, residual covariance.
        p[:2] = (weights[:, None] * observed).sum(0)
        residual = observed - p[:2]
        offset = 4
    else:
        p[:3] = torch.logit(p.new_tensor([3.5 / 8, .7 / 4, .6 / 4]))
        p[3] = torch.logit(p.new_tensor((1 - .05) / 2.95))
        model = Density('shared_cap', p)
        w, means, _ = model.components(magnitude)
        mean = (w[None, :, None] * means).sum(1).detach()
        residual = observed - mean
        p[6:8] = (weights[:, None] * residual).sum(0)
        residual = residual - p[6:8]
        offset = 8
    cov = torch.einsum('n,ni,nj->ij', weights, residual, residual)
    vals, vecs = torch.linalg.eigh(cov)
    cov = (vecs * vals.clamp_min(FLOOR + 1e-6)) @ vecs.T
    lower = torch.linalg.cholesky(cov - FLOOR * torch.eye(2, dtype=p.dtype))
    p[offset:] = torch.stack((inverse_softplus(lower[0, 0]), lower[1, 0], inverse_softplus(lower[1, 1])))
    gen = torch.Generator(device='cpu').manual_seed(seed)
    return p + .01 * torch.randn(p.shape, generator=gen, dtype=p.dtype)

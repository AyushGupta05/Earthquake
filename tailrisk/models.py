"""Encoders and predictive-distribution heads.

Every arm shares the same waveform encoder and trunk; arms differ only in the
head and in whether the log amplitude A enters as a free input (unconstrained)
or only through an exact shift (scale-equivariant).

Scale equivariance: if every physical sample is multiplied by c > 0, the
shape input and amplitude-ratio features are unchanged and A -> A + log10 c.
The equivariant head's location is kappa(s) * (A - A0) + g_k(s), so the whole
predictive distribution translates by kappa(s) * log10 c. With a
Gutenberg-Richter (exponential) magnitude prior and a Gaussian amplitude
likelihood the exact Bayes posterior has this form (the GR shrinkage is a
constant shift), so the constraint removes data-driven saturation in the
sparse upper tail without forbidding Bayesian shrinkage.
"""
import math

import torch
from torch import nn
from torch.nn import functional as F

A0 = -6.0        # centring constant for log10 RMS in m/s or m/s^2
NUM_CAT = 71     # categorical centres 0.0 .. 7.0 (labels lie on a 0.1 grid)
CAT_CENTERS = torch.arange(NUM_CAT, dtype=torch.float32) * 0.1


class ResBlock(nn.Module):
    def __init__(self, cin, cout, stride=2):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv1d(cin, cout, 5, stride=stride, padding=2, bias=False), nn.GroupNorm(8, cout), nn.SiLU(),
            nn.Conv1d(cout, cout, 3, padding=1, bias=False), nn.GroupNorm(8, cout))
        self.skip = nn.Conv1d(cin, cout, 1, stride=stride, bias=False)

    def forward(self, x):
        return F.silu(self.body(x) + self.skip(x))


class Encoder(nn.Module):
    def __init__(self, width=(48, 64, 96, 128, 192)):
        super().__init__()
        layers = [nn.Conv1d(3, width[0], 7, padding=3, bias=False), nn.GroupNorm(8, width[0]), nn.SiLU()]
        for cin, cout in zip(width[:-1], width[1:]):
            layers.append(ResBlock(cin, cout))
        self.net = nn.Sequential(*layers)
        self.out_dim = 2 * width[-1]

    def forward(self, shape):
        h = self.net(shape)
        return torch.cat([h.mean(-1), h.amax(-1)], 1)


class Trunk(nn.Module):
    """Encoder + MLP over [pooled shape, invariants, static, duration, (A)]."""

    def __init__(self, n_static, free_amplitude, hidden=256, dropout=0.1):
        super().__init__()
        self.encoder = Encoder()
        self.free_amplitude = free_amplitude
        n_in = self.encoder.out_dim + 8 + n_static + 3 + (1 if free_amplitude else 0)
        self.mlp = nn.Sequential(
            nn.Linear(n_in, hidden), nn.LayerNorm(hidden), nn.SiLU(), nn.Dropout(dropout),
            nn.Linear(hidden, hidden), nn.LayerNorm(hidden), nn.SiLU(), nn.Dropout(dropout))
        self.out_dim = hidden

    def forward(self, shape, A, invariant, static, dur_idx):
        dur = F.one_hot(dur_idx, 3).float()
        parts = [self.encoder(shape), invariant, static, dur]
        if self.free_amplitude:
            parts.append(((A - A0) / 2.0)[:, None])
        return self.mlp(torch.cat(parts, 1))


# ------------------------------------------------------------ distributions
class Categorical:
    def __init__(self, logits):
        self.logits = logits.float()
        self.p = self.logits.softmax(-1)

    def log_prob_label(self, y):
        idx = torch.round(y * 10).long().clamp(0, NUM_CAT - 1)
        return self.logits.log_softmax(-1).gather(1, idx[:, None])[:, 0]

    def mean(self):
        return self.p @ CAT_CENTERS.to(self.p.device)

    def sd(self):
        c = CAT_CENTERS.to(self.p.device)
        m = self.mean()
        return ((self.p * (c[None] - m[:, None]) ** 2).sum(1) + 0.1 ** 2 / 12).sqrt()

    def cdf(self, grid):
        # each bin uniform on [c - .05, c + .05)
        c = CAT_CENTERS.to(self.p.device)
        frac = ((grid[None, :] - (c[:, None] - 0.05)) / 0.1).clamp(0, 1)   # (K, G)
        return self.p @ frac


def log_interval(mu, sigma, lo, hi):
    """Stable log(Phi((hi-mu)/s) - Phi((lo-mu)/s)) for each mixture component."""
    a = (lo[:, None] - mu) / sigma
    b = (hi[:, None] - mu) / sigma
    # use the upper tail when the interval is above the mean
    flip = a > 0
    a2 = torch.where(flip, -b, a)
    b2 = torch.where(flip, -a, b)
    lb = torch.special.log_ndtr(b2)
    la = torch.special.log_ndtr(a2)
    return lb + torch.log1p(-torch.exp((la - lb).clamp(max=-1e-7)))


class Mixture:
    def __init__(self, logit_w, mu, sigma):
        self.logit_w = logit_w.float()
        self.mu = mu.float()
        self.sigma = sigma.float()

    def log_prob_label(self, y):
        """Interval-censored likelihood of the 0.1-rounded label."""
        lw = self.logit_w.log_softmax(-1)
        return torch.logsumexp(lw + log_interval(self.mu, self.sigma, y - 0.05, y + 0.05), -1)

    def mean(self):
        return (self.logit_w.softmax(-1) * self.mu).sum(-1)

    def sd(self):
        w = self.logit_w.softmax(-1)
        m = self.mean()
        return ((w * (self.sigma ** 2 + (self.mu - m[:, None]) ** 2)).sum(-1)).sqrt()

    def cdf(self, grid):
        w = self.logit_w.softmax(-1)                                 # (B,K)
        z = (grid[None, None, :] - self.mu[..., None]) / self.sigma[..., None]
        return (w[..., None] * torch.special.ndtr(z)).sum(1)


class CategoricalHead(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.lin = nn.Linear(dim, NUM_CAT)

    def forward(self, h, A):
        return Categorical(self.lin(h))


class MixtureHead(nn.Module):
    """Free Gaussian mixture; A may enter only through the trunk input."""

    def __init__(self, dim, k=6, min_sigma=0.03):
        super().__init__()
        self.k, self.min_sigma = k, min_sigma
        self.lin = nn.Linear(dim, 3 * k)
        with torch.no_grad():
            self.lin.bias[k:2 * k] = torch.linspace(1.0, 4.5, k)
            self.lin.bias[2 * k:] = math.log(math.expm1(0.3))

    def forward(self, h, A):
        w, mu, s = self.lin(h).float().split(self.k, -1)
        return Mixture(w, mu, F.softplus(s) + self.min_sigma)


class EquivariantMixtureHead(nn.Module):
    """mu_k = kappa(s) (A - A0) + g_k(s); kappa in [0.3, 1.5]."""

    def __init__(self, dim, k=6, min_sigma=0.03):
        super().__init__()
        self.k, self.min_sigma = k, min_sigma
        self.lin = nn.Linear(dim, 3 * k)
        self.kappa = nn.Linear(dim, 1)
        with torch.no_grad():
            self.lin.bias[k:2 * k] = torch.linspace(-1.0, 1.0, k) + 3.0
            self.lin.bias[2 * k:] = math.log(math.expm1(0.3))
            self.kappa.weight.zero_()
            self.kappa.bias.fill_(math.log(0.7 / 0.5))     # kappa = 1.0 at init

    def forward(self, h, A):
        w, g, s = self.lin(h).float().split(self.k, -1)
        kappa = 0.3 + 1.2 * torch.sigmoid(self.kappa(h).float())
        mu = kappa * (A.float() - A0)[:, None] + g
        return Mixture(w, mu, F.softplus(s) + self.min_sigma)


class Binned:
    """Discrete posterior on 0.1-wide bins with arbitrary centres (uniform within bin)."""

    def __init__(self, logp, centers):
        self.logp = logp.float()                 # normalized log probabilities (B, K)
        self.p = self.logp.exp()
        self.centers = centers

    def log_prob_label(self, y):
        idx = torch.round((y - float(self.centers[0])) * 10).long().clamp(0, len(self.centers) - 1)
        return self.logp.gather(1, idx[:, None])[:, 0]

    def mean(self):
        return self.p @ self.centers

    def sd(self):
        m = self.mean()
        return ((self.p * (self.centers[None] - m[:, None]) ** 2).sum(1) + 0.1 ** 2 / 12).sqrt()

    def cdf(self, grid):
        frac = ((grid[None, :] - (self.centers[:, None] - 0.05)) / 0.1).clamp(0, 1)
        return self.p @ frac


class EquivariantGRHead(nn.Module):
    """Equivariant mixture likelihood x learned global magnitude prior factor.

    p(bin b | x) oc P_mix(b | x) exp(phi_b). phi is free below M_C (catalogue
    incompleteness / detection roll-off) and Gutenberg-Richter-linear above:
    phi_b = phi(M_C) + beta (c_b - M_C). An exponential factor times a Gaussian
    mixture is again a shifted mixture, so the head remains exactly
    scale-equivariant wherever the tail prior is linear.
    """

    M_C = 3.5

    def __init__(self, dim, k=6, min_sigma=0.03, base_cls=None):
        super().__init__()
        # base_cls=MixtureHead gives the matched free-mixture ablation ('mixgr')
        self.mix = (base_cls or EquivariantMixtureHead)(dim, k, min_sigma)
        centers = torch.round(torch.arange(-1.0, 8.5 + 1e-6, 0.1) * 10) / 10
        self.register_buffer('centers', centers)
        self.n_free = int((centers < self.M_C - 1e-6).sum())
        self.phi_free = nn.Parameter(torch.zeros(self.n_free))
        self.beta = nn.Parameter(torch.zeros(()))

    def log_prior(self):
        c = self.centers
        tail = self.phi_free[-1] + self.beta * (c[self.n_free:] - c[self.n_free - 1])
        return torch.cat([self.phi_free, tail])

    def forward(self, h, A):
        mix = self.mix(h, A)
        edges = torch.cat([self.centers - 0.05, self.centers[-1:] + 0.05])
        Fe = mix.cdf(edges)                                   # (B, K+1)
        mass = (Fe[:, 1:] - Fe[:, :-1]).clamp_min(1e-30)
        logp = mass.log() + self.log_prior()[None]
        return Binned(logp.log_softmax(-1), self.centers)


class EquivariantHybridHead(nn.Module):
    """Equivariant mixture plus a bounded (+-0.5) free amplitude correction."""

    def __init__(self, dim, k=6, min_sigma=0.03, bound=0.5):
        super().__init__()
        self.mix = EquivariantMixtureHead(dim, k, min_sigma)
        self.bound = bound
        self.corr = nn.Sequential(nn.Linear(dim + 1, 64), nn.SiLU(), nn.Linear(64, k))
        nn.init.zeros_(self.corr[-1].weight)
        nn.init.zeros_(self.corr[-1].bias)

    def forward(self, h, A):
        m = self.mix(h, A)
        c = self.bound * torch.tanh(self.corr(torch.cat([h, ((A - A0) / 2.0)[:, None]], 1)).float())
        return Mixture(m.logit_w, m.mu + c, m.sigma)


R_CENTERS = torch.arange(0.5, 3.01, 0.1)      # log10 hypocentral distance (3 km .. 1000 km)


def distance_bin(hyp_km):
    r = torch.log10(hyp_km.clamp_min(1.0))
    return torch.round((r - 0.5) * 10).long().clamp(0, len(R_CENTERS) - 1)


class DistanceMixture(Mixture):
    """Marginal over distance bins; joint likelihood available for training."""

    def log_prob_joint(self, y, rbin):
        lw = self.logit_w.log_softmax(-1).gather(1, rbin[:, None])[:, 0]
        mu = self.mu.gather(1, rbin[:, None])
        sig = self.sigma.gather(1, rbin[:, None])
        return lw + log_interval(mu, sig, y - 0.05, y + 0.05)[:, 0]


class EquivariantDistanceHead(nn.Module):
    """p(m|x) = sum_r p(r|s) N(m; kappa(s)(A-A0) + G_r(s), sigma_r(s)^2).

    Distance r (log10 hypocentral km) is a TRAINING label only: the joint
    likelihood p(r|s) p(m|r,x) supervises how the scale-free shape constrains
    geometry; inference marginalizes r. Scale-equivariant in A exactly.
    """

    def __init__(self, dim, k=None, min_sigma=0.03):
        super().__init__()
        n = len(R_CENTERS)
        self.n, self.min_sigma = n, min_sigma
        self.lin = nn.Linear(dim, 3 * n)
        self.kappa = nn.Linear(dim, 1)
        with torch.no_grad():
            # start near M ~ log A + 1.5 log R (local-magnitude-like distance correction)
            self.lin.bias[n:2 * n] = 3.0 + 1.5 * (R_CENTERS - 1.7)
            self.lin.bias[2 * n:] = math.log(math.expm1(0.3))
            self.kappa.weight.zero_()
            self.kappa.bias.fill_(math.log(0.7 / 0.5))

    def forward(self, h, A):
        w, g, s = self.lin(h).float().split(self.n, -1)
        kappa = 0.3 + 1.2 * torch.sigmoid(self.kappa(h).float())
        mu = kappa * (A.float() - A0)[:, None] + g
        return DistanceMixture(w, mu, F.softplus(s) + self.min_sigma)


class JointBinned(Binned):
    """Marginal magnitude posterior plus the joint (distance, magnitude) likelihood."""

    def __init__(self, logp_marginal, centers, logjoint):
        super().__init__(logp_marginal, centers)
        self.logjoint = logjoint                         # (B, R, K) normalized

    def log_prob_joint(self, y, rbin):
        idx = torch.round((y - float(self.centers[0])) * 10).long().clamp(0, len(self.centers) - 1)
        lj = self.logjoint.gather(1, rbin[:, None, None].expand(-1, 1, self.logjoint.shape[2]))[:, 0]
        return lj.gather(1, idx[:, None])[:, 0]


class EquivariantDistanceGRHead(nn.Module):
    """Distance-aware equivariant likelihood x learned bulk prior x GR-linear tail.

    p(r, b | x) oc p(r|s) P(b | r, x) exp(phi_b), normalized jointly over (r, b);
    inference marginalizes r. Exactly equivariant in A where phi is linear.
    """

    def __init__(self, dim, k=None, min_sigma=0.03):
        super().__init__()
        self.base = EquivariantDistanceHead(dim, min_sigma=min_sigma)
        self.prior = EquivariantGRHead(dim, 1)     # reuse its prior parametrization only
        del self.prior.mix

    def forward(self, h, A):
        d = self.base(h, A)
        centers = self.prior.centers
        edges = torch.cat([centers - 0.05, centers[-1:] + 0.05])
        z = (edges[None, None, :] - d.mu[..., None]) / d.sigma[..., None]           # (B, R, K+1)
        Fe = torch.special.ndtr(z)
        mass = (Fe[..., 1:] - Fe[..., :-1]).clamp_min(1e-30)
        logj = d.logit_w.log_softmax(-1)[..., None] + mass.log() + self.prior.log_prior()[None, None]
        logz = torch.logsumexp(logj.flatten(1), 1)[:, None, None]
        logj = logj - logz
        return JointBinned(torch.logsumexp(logj, 1), centers, logj)


HEADS = {'cat': (CategoricalHead, True), 'mix': (MixtureHead, True), 'eq': (EquivariantMixtureHead, False),
         'eqgr': (EquivariantGRHead, False), 'eqh': (EquivariantHybridHead, False),
         'eqd': (EquivariantDistanceHead, False),
         'mixgr': (lambda dim, k=6: EquivariantGRHead(dim, k, base_cls=MixtureHead), True),
         'eqdgr': (EquivariantDistanceGRHead, False)}


class MagnitudeModel(nn.Module):
    def __init__(self, head, n_static, k=6, aux_dist=False):
        super().__init__()
        head_cls, free_amplitude = HEADS[head]
        self.trunk = Trunk(n_static, free_amplitude)
        self.head = head_cls(self.trunk.out_dim) if head == 'cat' else head_cls(self.trunk.out_dim, k)
        # optional auxiliary distance classifier (training-only multi-task control)
        self.aux = nn.Linear(self.trunk.out_dim, len(R_CENTERS)) if aux_dist else None

    def forward(self, shape, A, invariant, static, dur_idx):
        return self.head(self.trunk(shape, A, invariant, static, dur_idx), A)

    def forward_train(self, shape, A, invariant, static, dur_idx):
        h = self.trunk(shape, A, invariant, static, dur_idx)
        aux = self.aux(h).float() if self.aux is not None else None
        return self.head(h, A), aux

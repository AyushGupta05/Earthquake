"""Numerical check of the GR-equivariance proposition in THEORY.md (CPU, numpy only).

Model: M ~ prior; nuisance z (log10 distance) ~ p(z) independent of M;
A = kappa*M + h(z) + eps, eps ~ N(0, s^2); shape s carries no information about M.
Claim: with a Gutenberg-Richter prior the posterior p(M | A) satisfies
p(M | A + kappa*delta) = p(M - delta | A) exactly, for any h, p(z), kappa, s.
Also shown: with a non-exponential prior (a selection cliff) the property fails,
which is why the bulk prior is left free and only the tail is GR-linear.
"""
import numpy as np

kappa, s = 0.7, 0.35
M = np.arange(-6.0, 15.0001, 0.01)                 # wide grid: no truncation inside the posterior support
z = np.linspace(0.5, 3.0, 400)                       # log10 km
pz = np.exp(-0.5 * ((z - 1.8) / 0.5) ** 2); pz /= pz.sum()
h = -1.5 * z + 0.3 * np.sin(3 * z)                    # arbitrary attenuation/site term


def posterior(A, log_prior):
    ll = -0.5 * ((A - kappa * M[:, None] - h[None, :]) / s) ** 2 + np.log(pz)[None, :]
    m = ll.max()
    log_like = m + np.log(np.exp(ll - m).sum(1))                    # marginal over z
    lp = log_prior + log_like
    p = np.exp(lp - lp.max())
    return p / (p.sum() * 0.01)


def shift(p, delta):
    """p(M - delta) on the same grid (linear interpolation, zero outside)."""
    return np.interp(M - delta, M, p, left=0.0, right=0.0)


gr = -2.3 * M                                        # b = 1 in log10 units
cliff = gr + np.where(M < 2.0, -2.2, 0.0)           # 9x fewer records below M2 (selection)
for A0 in (0.0, 2.0, 4.0):                             # inside the simulated support of A
    for delta in (0.5, 1.0):
        pA = posterior(A0 + kappa * delta, gr)
        pS = shift(posterior(A0, gr), delta)
        inside = (M > -4.0) & (M < 13.0)               # away from the truncated grid edges
        err_gr = np.abs(pA - pS)[inside].max() / pA.max()
        pA2 = posterior(A0 + kappa * delta, cliff)
        pS2 = shift(posterior(A0, cliff), delta)
        err_cliff = np.abs(pA2 - pS2)[inside].max() / pA2.max()
        print(f'A0={A0:+.1f} delta={delta}: GR prior max rel. deviation {err_gr:.1e} | cliff prior {err_cliff:.2f}')
        assert err_gr < 1e-6
print('GR equivariance holds exactly with unknown distance; a prior cliff breaks it (as expected).')

# Proposition 2: an exponential tilt of a Gaussian mixture is a shifted, re-weighted mixture,
# so (likelihood, beta) and (tilted likelihood, 0) give the same posterior.
rng = np.random.default_rng(0)
for beta in (-2.3, -1.2, 0.7):
    w = rng.dirichlet(np.ones(4)); mu = rng.uniform(1, 6, 4); sig = rng.uniform(0.1, 0.8, 4)
    comp = np.exp(-0.5 * ((M[:, None] - mu) / sig) ** 2) / sig
    tilted = (comp @ w) * np.exp(beta * M)
    w2 = w * np.exp(beta * mu + 0.5 * beta ** 2 * sig ** 2)
    comp2 = np.exp(-0.5 * ((M[:, None] - (mu + beta * sig ** 2)) / sig) ** 2) / sig
    direct = comp2 @ w2
    tilted /= tilted.sum(); direct /= direct.sum()
    err = np.abs(tilted - direct).max() / tilted.max()
    print(f'beta={beta:+.1f}: tilt-vs-shift max rel. deviation {err:.1e}')
    assert err < 1e-10
print('The prior tail slope is absorbed by a component shift: not identified from single-station data.')

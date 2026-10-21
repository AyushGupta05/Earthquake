"""Checks of the multi-station fusion rules on synthetic posteriors (no data needed).

  python tailrisk/test_fusion.py
"""
import numpy as np

import multistation as ms
from common import PMF_CENTERS

K = len(PMF_CENTERS)
c = PMF_CENTERS.astype(np.float32)
rng = np.random.default_rng(0)


def gauss_logpmf(mu, sd):
    lp = -0.5 * ((c - mu) / sd) ** 2
    return (lp - np.log(np.exp(lp).sum())).astype(np.float32)


# 1. with one station every rule returns the station posterior
phi = (-2.3 * c).astype(np.float32)[None, :]
pih = (-1.5 * c).astype(np.float32)[None, :]
lp = gauss_logpmf(4.0, 0.4)[None, None, :]
for rule in ('post_prod', 'post_mean', 'hist_adj', 'lik_prior'):
    p = ms.combine(lp, rule, 1, phi, pih)
    assert np.allclose(p[0], np.exp(lp[0, 0]), atol=1e-6), rule
print('k = 1: every rule returns the single-station posterior')

# 2. Bayes: posteriors p_i = L_i pi / Z_i; the true k-station posterior is prod L_i pi.
#    'lik_prior' with the true prior recovers it exactly; the naive product carries pi^k.
L = [gauss_logpmf(5.0, 0.5), gauss_logpmf(4.6, 0.7), gauss_logpmf(5.3, 0.6)]
prior = phi[0]
posts = np.stack([ms.normalize((l + prior)[None, :])[0] for l in L])
truth = ms.normalize((np.sum(L, 0) + prior)[None, :])[0]
lp3 = np.log(np.maximum(posts, 1e-30)).astype(np.float32)[None]
p_lik = ms.combine(lp3, 'lik_prior', 3, phi, pih)[0]
p_naive = ms.combine(lp3, 'post_prod', 3, phi, pih)[0]
naive_truth = ms.normalize((np.sum(L, 0) + 3 * prior)[None, :])[0]
assert np.abs(p_lik - truth).max() < 1e-5
assert np.abs(p_naive - naive_truth).max() < 1e-5
m_true = (truth * c).sum(); m_naive = (p_naive * c).sum()
print(f'Bayes with the prior counted once: exact (max dev {np.abs(p_lik - truth).max():.1e}); '
      f'naive product carries the prior 3 times: mean {m_naive:.3f} vs {m_true:.3f}')

# 3. 'hist_adj' with pi_hat = the true prior equals 'lik_prior'
p_hist = ms.combine(lp3, 'hist_adj', 3, phi, phi)[0]
assert np.abs(p_hist - p_lik).max() < 1e-5
print('histogram rule with the true prior equals the factor rule')

# 4. the posterior mean of identical stations is the station posterior; the product sharpens it
same = np.repeat(lp[:, :1], 4, axis=1)
p_mean = ms.combine(same, 'post_mean', 4, phi, pih)[0]
assert np.allclose(p_mean, np.exp(lp[0, 0]), atol=1e-6)
sd_prod = np.sqrt((ms.combine(same, 'post_prod', 4, phi, pih)[0] * c ** 2).sum() - (ms.combine(same, 'post_prod', 4, phi, pih)[0] * c).sum() ** 2)
assert sd_prod < 0.3
print('mean of identical posteriors is unchanged; their product is sharper (sd %.2f vs 0.40)' % sd_prod)

# 5. Proposition 2 consequence: a factor with the wrong slope leaves a residual tilt exp((k-1) gamma m)
gamma = 1.0
phi_wrong = phi - gamma * c[None, :]
p_wrong = ms.combine(lp3, 'lik_prior', 3, phi_wrong, pih)[0]
resid = ms.normalize((np.log(np.maximum(truth, 1e-30)) + 2 * gamma * c)[None, :])[0]
assert np.abs(p_wrong - resid).max() < 1e-5
print('a mis-sloped factor leaves exactly the predicted residual tilt exp((k-1) gamma m)')
print('all fusion checks passed')

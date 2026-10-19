"""Numerical checks of the decision rules (run on CPU: python tailrisk/test_decisions.py)."""
import numpy as np
import torch

from common import GRID, TAIL_T, tail_weighted_median
from evaluate import EDGES, wmed_from_pmf
from models import Categorical, Mixture

torch.manual_seed(0)
B = 64


def brute_force(cdf_fn, ratios, grid=np.arange(-1, 8, 0.002)):
    """argmin_a E[w(M)|a-M|] by direct numerical integration on a fine grid."""
    F = cdf_fn(torch.tensor(grid, dtype=torch.float32)).double().numpy()     # (B, G)
    p = np.diff(np.concatenate([np.zeros((len(F), 1)), F], 1), axis=1)
    out = np.zeros((len(F), len(ratios)))
    for j, r in enumerate(ratios):
        w = np.where(grid >= TAIL_T, r, 1.0)
        for i in range(len(F)):
            pw = p[i] * w
            c = np.cumsum(pw)
            out[i, j] = grid[np.searchsorted(c, 0.5 * c[-1])]   # weighted median minimizes weighted L1
    return out


def expected_loss(cdf_fn, actions, ratios, grid=np.arange(-1, 8, 0.002)):
    """E[w_r(M)|a - M|] for each row/ratio (numerical integration)."""
    F = cdf_fn(torch.tensor(grid, dtype=torch.float32)).double().numpy()
    p = np.diff(np.concatenate([np.zeros((len(F), 1)), F], 1), axis=1)
    out = np.zeros(actions.shape)
    for j, r in enumerate(ratios):
        w = np.where(grid >= TAIL_T, r, 1.0)
        out[:, j] = (p * w * np.abs(actions[:, j:j + 1] - grid[None, :])).sum(1)
    return out


def check(name, cdf_fn, closed, ratios):
    bf = brute_force(cdf_fn, ratios)
    lc, lb = expected_loss(cdf_fn, closed, ratios), expected_loss(cdf_fn, bf, ratios)
    rel = ((lc - lb) / np.maximum(lb, 1e-9)).max()
    print(f'{name}: max argmin gap {np.abs(closed - bf).max():.4f}, max relative excess loss {rel:.2e}')
    assert rel < 1e-3, name


ratios = [0.5, 1, 3, 11, 50]
mix = Mixture(torch.randn(B, 4), torch.rand(B, 4) * 5 + 0.5, torch.rand(B, 4) * 0.5 + 0.1)
wm = tail_weighted_median(mix.cdf(GRID).float(), GRID, ratios).numpy()
check('mixture', mix.cdf, wm, ratios)

cat = Categorical(torch.randn(B, 71) * 2)
wm_c = tail_weighted_median(cat.cdf(GRID).float(), GRID, ratios).numpy()
check('categorical', cat.cdf, wm_c, ratios)

# PMF-based evaluator path on the categorical (exactly representable on the 0.1 grid)
centers = (EDGES[:-1] + 0.05)
Fe = cat.cdf(torch.tensor(EDGES, dtype=torch.float32)).numpy()
pmf = np.diff(Fe, axis=1)
wm_p = wmed_from_pmf(pmf, np.array(ratios, float))
check('pmf path', cat.cdf, wm_p.astype(np.float64), ratios)
# monotone in r
assert (np.diff(wm, axis=1) >= -1e-4).all()
print('all decision checks passed')

"""Shared data, feature, distribution and decision utilities for tail-risk work.

All model inputs are causal functions of the observed P-relative prefix
(1/3/5 s) plus static station metadata known before the event (instrument
gains/units/families, elevation, Vs30, station coordinates). Catalogue source
fields in meta.npz are used only for fold construction and analysis.
"""
import math
from pathlib import Path

import numpy as np
import torch

WORK = Path('/mnt/eew-research/runs/tailwork')
REPO = Path(__file__).resolve().parents[1]
DURATIONS = (1, 3, 5)
SAMPLES = {1: 100, 3: 300, 5: 500}
# Global standardization constants of the cache: x = (counts - mean) / std.
CACHE_STD = np.load(REPO / 'train_std_full.npy').astype(np.float64)
TAIL_T = 3.95                     # continuous threshold equivalent to label >= 4.0
GRID = torch.arange(-1.0, 8.0 + 1e-9, 0.01)          # fine CDF grid for decisions
PMF_CENTERS = np.round(np.arange(-0.5, 7.5 + 1e-9, 0.1), 2)  # saved coarse PMF
RATIOS = (1, 1.5, 2, 3, 4, 6, 8, 11, 16, 24, 35, 50, 75, 100)
QUANTILES = (0.05, 0.1, 0.25, 0.75, 0.9, 0.95)
DECISION_NAMES = (['mean'] + [f'wmed_r{r:g}' for r in RATIOS] + [f'q{q:g}' for q in QUANTILES]
                  + ['p_ge4', 'p_ge45', 'p_ge5', 'nll_bin', 'crps', 'sd'])


def load_meta():
    m = np.load(WORK / 'meta.npz', allow_pickle=True)
    return {k: m[k] for k in m.files}


def fallback_gains(meta):
    """Replace unmatched component gains by the family/component median gain."""
    gains = meta['gains'].copy()
    usable = meta['usable']
    fam = meta['family']
    for f in np.unique(fam):
        for c in range(3):
            rows = fam == f
            ok = rows & usable[:, c]
            med = np.nanmedian(gains[ok, c]) if ok.any() else np.nanmedian(gains[usable[:, c], c])
            gains[rows & ~usable[:, c], c] = med
    return gains


class GPUData:
    """Waveforms (float16, per-record scaled) and per-record static inputs on GPU."""

    def __init__(self, device, meta=None, rows=None):
        self.meta = load_meta() if meta is None else meta
        wave = np.load(WORK / 'wave16.npy', mmap_mode='r')
        scale = np.load(WORK / 'scale.npy')
        n = len(scale)
        self.rows = np.arange(n) if rows is None else np.asarray(rows)
        self.device = device
        chunks = []
        for start in range(0, len(self.rows), 100000):
            sel = self.rows[start:start + 100000]
            chunks.append(torch.from_numpy(np.ascontiguousarray(wave[sel])).to(device))
        self.wave = torch.cat(chunks)
        self.scale = torch.from_numpy(scale[self.rows]).to(device)
        gains = fallback_gains(self.meta)[self.rows]
        # physical = (x - prefix mean) * std / gain
        self.phys_factor = torch.from_numpy((CACHE_STD[None, :] / gains).astype(np.float32)).to(device)
        static = np.concatenate([self.meta['static'],
                                 self.meta['sta_lat'][:, None], self.meta['sta_lon'][:, None]], 1)
        static = static[self.rows].astype(np.float32)
        static = np.nan_to_num(static, nan=0.0)
        self.static_raw = torch.from_numpy(static).to(device)
        self.mag = torch.from_numpy(self.meta['mag'][self.rows].astype(np.float32)).to(device)
        self.static_mean = None
        self.static_std = None

    def fit_static_norm(self, local_idx):
        s = self.static_raw[local_idx]
        self.static_mean = s.mean(0)
        self.static_std = s.std(0).clamp_min(1e-3)

    def static(self, local_idx):
        return ((self.static_raw[local_idx] - self.static_mean) / self.static_std).clamp(-10, 10)

    def prefix(self, local_idx, seconds):
        """Physical-unit, prefix-demeaned waveform and amplitude summaries."""
        L = SAMPLES[seconds]
        x = self.wave[local_idx, :, :L].float() * self.scale[local_idx, None, None]
        x = x - x.mean(-1, keepdim=True)
        phys = x * self.phys_factor[local_idx, :, None]
        return amplitude_features(phys)


def amplitude_features(phys):
    """Split a physical prefix into a scale-free shape and its log amplitude.

    Returns shape (B,3,L), A (B,) = log10 RMS over all components, and
    invariant (B,8) log-amplitude ratios. Scaling phys by c > 0 leaves shape and
    invariant unchanged and adds log10(c) to A exactly.
    """
    tiny = 1e-15
    rms_c = phys.square().mean(-1).clamp_min(tiny ** 2).sqrt()
    peak_c = phys.abs().amax(-1).clamp_min(tiny)
    rms_all = phys.square().mean((1, 2)).clamp_min(tiny ** 2).sqrt()
    A = rms_all.log10()
    L = phys.shape[-1]
    head = phys[..., : max(L // 5, 10)].square().mean((1, 2)).clamp_min(tiny ** 2).sqrt()
    tail = phys[..., -max(L // 5, 10):].square().mean((1, 2)).clamp_min(tiny ** 2).sqrt()
    invariant = torch.cat([rms_c.log10() - A[:, None], peak_c.log10() - A[:, None],
                           (head.log10() - A)[:, None], (tail.log10() - A)[:, None]], 1)
    shape = (phys / rms_all[:, None, None]).clamp(-60, 60)
    return shape, A, invariant


# ----------------------------------------------------------------- decisions
def interp_cdf(F, grid, at):
    """Linear interpolation of per-row CDF F (B,G) on grid at points at (B,K)."""
    step = float(grid[1] - grid[0])
    pos = ((at - float(grid[0])) / step).clamp(0, F.shape[1] - 1 - 1e-6)
    i0 = pos.floor().long()
    w = pos - i0
    return F.gather(1, i0) * (1 - w) + F.gather(1, i0 + 1) * w


def inverse_cdf(F, grid, q):
    """Quantiles of per-row CDF F at levels q (B,K) by linear interpolation."""
    Fc = torch.cummax(F, 1).values.contiguous()
    idx = torch.searchsorted(Fc, q.contiguous(), right=False).clamp(1, F.shape[1] - 1)
    f0, f1 = Fc.gather(1, idx - 1), Fc.gather(1, idx)
    g = grid.to(F.device)
    g0, g1 = g[idx - 1], g[idx]
    w = ((q - f0) / (f1 - f0).clamp_min(1e-12)).clamp(0, 1)
    return g0 + w * (g1 - g0)


def tail_weighted_median(F, grid, ratios, threshold=TAIL_T):
    """argmin_a E[w(M)|a-M|] with w = r above threshold, 1 below (per ratio)."""
    FT = interp_cdf(F, grid, torch.full((F.shape[0], 1), threshold, device=F.device))
    r = torch.as_tensor(ratios, dtype=F.dtype, device=F.device)[None, :]
    half = 0.5 * (FT + r * (1 - FT))
    q = torch.where(half <= FT, half, FT + 0.5 * (1 - FT) - 0.5 * FT / r)
    return inverse_cdf(F, grid, q.clamp(1e-6, 1 - 1e-6))


def decisions(dist, y):
    """Fixed decision/score summary of a predictive distribution (B, D)."""
    grid = GRID.to(y.device)
    F = dist.cdf(grid).float().clamp(0, 1)
    mean = dist.mean().float()
    wmed = tail_weighted_median(F, grid, RATIOS)
    q = inverse_cdf(F, grid, torch.tensor(QUANTILES, device=y.device).expand(len(y), -1))
    tail = 1 - interp_cdf(F, grid, torch.tensor([3.95, 4.45, 4.95], device=y.device).expand(len(y), -1))
    lo = interp_cdf(F, grid, (y - 0.05)[:, None])
    hi = interp_cdf(F, grid, (y + 0.05)[:, None])
    nll = -(hi - lo).clamp_min(1e-12).log()
    step = float(grid[1] - grid[0])
    crps = ((F - (grid[None, :] >= y[:, None]).float()) ** 2).sum(1, keepdim=True) * step
    sd = dist.sd().float()[:, None]
    out = torch.cat([mean[:, None], wmed, q, tail, nll, crps, sd], 1)
    centers = torch.tensor(PMF_CENTERS, dtype=torch.float32, device=y.device)
    edges = torch.cat([centers - 0.05, centers[-1:] + 0.05])
    Fe = interp_cdf(F, grid, edges[None, :].expand(len(y), -1))
    pmf = (Fe[:, 1:] - Fe[:, :-1]).clamp_min(0)
    return out, pmf


# ------------------------------------------------------------------ metrics
def cvar(err, frac):
    k = max(1, int(math.ceil(frac * len(err))))
    return float(np.sort(err)[-k:].mean())


def metric_table(pred, y, event, thresholds=(4.0, 4.5, 5.0)):
    """Record and event-macro metrics for point predictions."""
    err = np.abs(pred - y)
    out = {'MAE': float(err.mean()), 'MedAE': float(np.median(err)),
           'RMSE': float(np.sqrt(np.mean((pred - y) ** 2))),
           'CVaR95': cvar(err, .05), 'CVaR99': cvar(err, .01), 'P95': float(np.quantile(err, .95)),
           'max': float(err.max())}
    ev_err = np.bincount(event, err) / np.maximum(np.bincount(event), 1)
    ev_mag = np.zeros(event.max() + 1)
    ev_mag[event] = y
    present = np.bincount(event) > 0
    out['event_MAE'] = float(ev_err[present].mean())
    for t in thresholds:
        sel = y >= t - 1e-6
        e_sel = present & (ev_mag >= t - 1e-6)
        out[f'M>={t:g}_MAE'] = float(err[sel].mean())
        out[f'M>={t:g}_bias'] = float((pred[sel] - y[sel]).mean())
        out[f'M>={t:g}_eventMAE'] = float(ev_err[e_sel].mean())
        out[f'M>={t:g}_n_events'] = int(e_sel.sum())
    low = y < 4 - 1e-6
    out['M<4_MAE'] = float(err[low].mean())
    out['M<4_MedAE'] = float(np.median(err[low]))
    out['FP4_rate'] = float(np.mean(pred[y < 3.5] >= 3.95))
    return out

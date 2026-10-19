"""Classical feature + gradient-boosting baseline (E3WS-style), same CV folds.

Causal per-deadline features from the physical-unit prefix (no catalogue
information): per component log peak / RMS of the native signal and of its
first and second running integrals (Pd/Pv/Pa analogues), a tau_c-like period
ratio, vertical band-energy fractions, early/late growth, H/V ratio; plus the
same 36 static station fields the networks see. Point predictions only
(absolute-error loss -> conditional median).

  python tailrisk/gbm_baseline.py
"""
import json
import math
import os
import time

import numpy as np
import torch

from common import DURATIONS, SAMPLES, WORK, GPUData, load_meta, metric_table


def features(data, idx, seconds):
    L = SAMPLES[seconds]
    x = data.wave[idx, :, :L].float() * data.scale[idx, None, None]
    x = x - x.mean(-1, keepdim=True)
    x = x * data.phys_factor[idx, :, None]
    i1 = torch.cumsum(x, -1) / 100.0
    i1 = i1 - torch.linspace(0, 1, L, device=x.device) * i1[..., -1:]        # remove linear drift
    i2 = torch.cumsum(i1, -1) / 100.0
    i2 = i2 - torch.linspace(0, 1, L, device=x.device) * i2[..., -1:]
    lg = lambda v: v.clamp_min(1e-15).log10()
    f = []
    for s in (x, i1, i2):
        f += [lg(s.abs().amax(-1)), lg(s.square().mean(-1).sqrt())]          # 3 comps each
    tau = 2 * math.pi * (i1[:, 2].square().sum(-1) / x[:, 2].square().sum(-1).clamp_min(1e-30)).sqrt()
    f.append(lg(tau)[:, None])
    spec = torch.fft.rfft(x[:, 2] * torch.hann_window(L, device=x.device), dim=-1).abs().square()
    freqs = torch.fft.rfftfreq(L, 0.01).to(x.device)
    tot = spec.sum(-1).clamp_min(1e-30)
    for lo, hi in ((0.5, 1), (1, 2), (2, 4), (4, 8), (8, 16), (16, 50)):
        band = spec[:, (freqs >= lo) & (freqs < hi)].sum(-1)
        f.append(lg(band / tot + 1e-12)[:, None])
    half = L // 2
    f.append((lg(x[..., :half].square().mean((1, 2)).sqrt()) - lg(x[..., half:].square().mean((1, 2)).sqrt()))[:, None])
    f.append((lg(x[:, :2].square().mean((1, 2)).sqrt()) - lg(x[:, 2].square().mean(-1).sqrt()))[:, None])
    f.append(data.static_raw[idx])
    return torch.cat(f, 1).cpu().numpy().astype(np.float32)


def main():
    from sklearn.ensemble import HistGradientBoostingRegressor
    meta = load_meta()
    device = torch.device('cuda')
    data = GPUData(device, meta)
    n = len(meta['mag'])
    X = {}
    with torch.no_grad():
        for d in DURATIONS:
            parts = [features(data, torch.arange(s, min(s + 20000, n), device=device), d) for s in range(0, n, 20000)]
            X[d] = np.concatenate(parts)
            print('features', d, X[d].shape, flush=True)
    del data
    torch.cuda.empty_cache()
    y = meta['mag'].astype(np.float32)
    fold = meta['fold']
    out_dir = WORK / 'arms' / 'gbm_e3ws'
    out_dir.mkdir(parents=True, exist_ok=True)
    pred = np.full((n, 3), np.nan, np.float32)
    t0 = time.time()
    for f in range(5):
        tr, te = fold != f, fold == f
        for d_i, d in enumerate(DURATIONS):
            model = HistGradientBoostingRegressor(loss='absolute_error', max_iter=600, learning_rate=0.08,
                                                  max_leaf_nodes=127, min_samples_leaf=40, l2_regularization=1.0,
                                                  early_stopping=False, random_state=0)
            model.fit(X[d][tr], y[tr])
            pred[te, d_i] = model.predict(X[d][te])
            m = metric_table(pred[te, d_i], y[te], meta['event'][te])
            print(f'fold{f} {d}s MAE {m["MAE"]:.4f} M>=4 {m["M>=4_MAE"]:.4f} {time.time() - t0:.0f}s', flush=True)
        np.save(out_dir / 'pred.npy', pred)
    summary = {f'{d}s': metric_table(pred[:, i], y, meta['event']) for i, d in enumerate(DURATIONS)}
    (out_dir / 'summary.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: {m: v[m] for m in ('MAE', 'MedAE', 'CVaR95', 'M>=4_MAE', 'M>=4_eventMAE', 'M>=5_MAE')}
                      for k, v in summary.items()}, indent=1))


if __name__ == '__main__':
    os.environ.setdefault('OMP_NUM_THREADS', '3')
    main()

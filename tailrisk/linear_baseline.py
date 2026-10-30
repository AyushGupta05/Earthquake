"""Classical linear log-amplitude baselines under the same cap and folds (written by the 30 Oct
audit of the capped-training result; CPU only).

Features per record and deadline, computed exactly as the networks see them (common.amplitude_features
on wave16 * scale * phys_factor, prefix-demeaned): A = log10 RMS and the 8 scale-free invariants.
Fits, on training rows only (fold != k and common.cap_keep(label, cap, 'bin')):
  lin_A      M ~ 1 + A
  lin_Ainv   M ~ 1 + A + invariants(8)
  lin_AR     M ~ 1 + A + log10(hyp_km)   (ORACLE catalogue distance; not available to the networks)
  inv_Minv   inverse law A ~ 1 + M + invariants, solved for M (no distance)
  inv_MR     inverse law A ~ 1 + M + log10(hyp_km), solved for M (ORACLE distance)
Forward regressions of M on A are biased by the truncation on M; the inverse (generative)
direction A | M is not, which is the classical counterpart of Proposition 3.
Usage: python linear_baseline.py <work_dir> <cap> <out_json>
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import amplitude_features, CACHE_STD, cap_keep, fallback_gains  # noqa: E402

W = Path(sys.argv[1])
CAP = float(sys.argv[2])
OUT = Path(sys.argv[3])
torch.set_num_threads(2)
m = np.load(W / 'meta.npz', allow_pickle=True)
meta = {k: m[k] for k in m.files}
mag = meta['mag'].astype(np.float64)
fold = meta['fold'].astype(int)
event = meta['event']
cluster = meta['cluster']
hyp = meta['hyp_km'].astype(np.float64)
N = len(mag)
wave = np.load(W / 'wave16.npy', mmap_mode='r')
scale = np.load(W / 'scale.npy')
if 'phys_factor' in meta:
    pf_all = meta['phys_factor'].astype(np.float32)
else:
    pf_all = (CACHE_STD[None, :] / fallback_gains(meta)).astype(np.float32)
feat = np.zeros((N, 3, 9), np.float32)
CH = 20000
for s in range(0, N, CH):
    x = torch.from_numpy(np.asarray(wave[s:s + CH])).float() * torch.from_numpy(scale[s:s + CH])[:, None, None]
    pf = torch.from_numpy(pf_all[s:s + CH])
    for d_i, L in enumerate((100, 300, 500)):
        xx = x[:, :, :L]
        xx = xx - xx.mean(-1, keepdim=True)
        _, A, inv = amplitude_features(xx * pf[:, :, None])
        feat[s:s + CH, d_i, 0] = A.numpy()
        feat[s:s + CH, d_i, 1:] = inv.numpy()
    if s % 200000 == 0:
        print('features', s, flush=True)
logR = np.log10(np.clip(np.nan_to_num(hyp, nan=50.0), 1.0, None))
pred = {k: np.full((N, 3), np.nan) for k in ('lin_A', 'lin_Ainv', 'lin_AR', 'inv_Minv', 'inv_MR')}
coef = {}
for k in range(5):
    tr = (fold != k) & cap_keep(mag, CAP, 'bin')
    te = fold == k
    for d_i in range(3):
        F = feat[:, d_i].astype(np.float64)
        ok = np.isfinite(F).all(1)
        designs = {'lin_A': np.c_[np.ones(N), F[:, 0]],
                   'lin_Ainv': np.c_[np.ones(N), F],
                   'lin_AR': np.c_[np.ones(N), F[:, 0], logR]}
        for name, X in designs.items():
            sel = tr & ok
            b, *_ = np.linalg.lstsq(X[sel], mag[sel], rcond=None)
            p = X[te] @ b
            pred[name][te, d_i] = p
            coef.setdefault(name, {})[f'fold{k}_d{d_i}'] = [round(float(v), 4) for v in b[:3]]
        # classical inverse regression (selection on the regressor M does not bias it):
        #   A = a + b M + c . z  ->  M = (A - a - c . z) / b
        for name, Z in (('inv_Minv', F[:, 1:]), ('inv_MR', logR[:, None])):
            sel = tr & ok
            X = np.c_[np.ones(N), mag, Z]
            b, *_ = np.linalg.lstsq(X[sel], F[sel, 0], rcond=None)
            Zt = np.c_[np.ones(te.sum()), Z[te]]
            bz = np.r_[b[0], b[2:]]
            pred[name][te, d_i] = (F[te, 0] - Zt @ bz) / b[1]
            coef.setdefault(name, {})[f'fold{k}_d{d_i}'] = [round(float(v), 4) for v in b[:3]]
res = {'coef_first3': coef}
for name, P in pred.items():
    out = {}
    for d_i, d in enumerate((1, 3, 5)):
        e = P[:, d_i] - mag
        ok = np.isfinite(e)
        row = {'bulk_MAE': float(np.abs(e[ok]).mean()), 'n_nonfinite': int((~ok).sum())}
        for t in (CAP, CAP + 1):
            s = ok & (mag >= t - 1e-6)
            ev = event[s]
            u, inv = np.unique(ev, return_inverse=True)
            row[f'M>={t:g}'] = {'rec_MAE': float(np.abs(e[s]).mean()), 'bias': float(e[s].mean()),
                                'event_MAE': float((np.bincount(inv, np.abs(e[s])) / np.bincount(inv)).mean()),
                                'n_rec': int(s.sum()), 'n_ev': int(len(u))}
        out[f'{d}s'] = row
    res[name] = out
OUT.write_text(json.dumps(res, indent=1))
print(json.dumps({n: {d: {'bulk': round(res[n][d]['bulk_MAE'], 3),
                          f'M>={CAP:g}': round(res[n][d][f'M>={CAP:g}']['rec_MAE'], 3),
                          f'M>={CAP + 1:g}': round(res[n][d][f'M>={CAP + 1:g}']['rec_MAE'], 3),
                          f'bias{CAP + 1:g}': round(res[n][d][f'M>={CAP + 1:g}']['bias'], 3)}
                      for d in ('1s', '3s', '5s')} for n in pred}, indent=1))

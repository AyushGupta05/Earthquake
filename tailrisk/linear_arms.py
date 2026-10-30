"""Classical log-amplitude magnitude laws as ordinary arms (CPU only).

Writes <WORK>/arms/<name>/fold<k>.npz in the same format as train.py (rows, dec, pmf), so the
evaluation and robust-statistics scripts treat these baselines exactly like the networks.
Features are computed as the networks see them (common.amplitude_features on the physical,
prefix-demeaned waveform; code from the 30 Oct audit's linear_baseline.py) and cached in
<WORK>/linfeat.npz. Laws, fitted per fold on training rows only (optionally under a cap):

  fwd    M ~ 1 + A + invariants(8)                  forward regression, no distance
  fwdR   M ~ 1 + A + log10(R_hyp)                   forward, ORACLE catalogue distance
  inv    A ~ 1 + M + invariants(8), solved for M    inverse (generative) law, no distance
  invR   A ~ 1 + M + log10(R_hyp), solved for M     inverse law, ORACLE catalogue distance

(invR is the form of the classical P-amplitude magnitude relations, e.g. log PGV = aM + b log R
+ c.) The predictive distribution is Gaussian with the training residual SD in magnitude units.
The networks get no distance input; fwdR and invR are oracles.

  TAILWORK_DIR=... python linear_arms.py --laws fwd,fwdR,inv,invR [--cap 5.0] [--suffix _cap50b]
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from common import (CACHE_STD, DECISION_NAMES, PMF_CENTERS, WORK, amplitude_features, cap_keep,
                    decisions, fallback_gains)
from models import Mixture

torch.set_num_threads(3)


def features(meta):
    path = WORK / 'linfeat.npz'
    if path.exists():
        return np.load(path)['feat']
    n = len(meta['mag'])
    wave = np.load(WORK / 'wave16.npy', mmap_mode='r')
    scale = np.load(WORK / 'scale.npy')
    pf_all = (meta['phys_factor'].astype(np.float32) if 'phys_factor' in meta
              else (CACHE_STD[None, :] / fallback_gains(meta)).astype(np.float32))
    feat = np.zeros((n, 3, 9), np.float32)
    ch = 20000
    for s in range(0, n, ch):
        x = torch.from_numpy(np.asarray(wave[s:s + ch])).float() * torch.from_numpy(scale[s:s + ch])[:, None, None]
        pf = torch.from_numpy(pf_all[s:s + ch])
        for d_i, length in enumerate((100, 300, 500)):
            xx = x[:, :, :length]
            xx = xx - xx.mean(-1, keepdim=True)
            _, A, inv = amplitude_features(xx * pf[:, :, None])
            feat[s:s + ch, d_i, 0] = A.numpy()
            feat[s:s + ch, d_i, 1:] = inv.numpy()
        if s % 200000 == 0:
            print('features', s, flush=True)
    np.savez(path, feat=feat)
    return feat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--laws', default='fwd,fwdR,inv,invR')
    ap.add_argument('--cap', type=float, default=None)
    ap.add_argument('--suffix', default='')
    args = ap.parse_args()
    m = np.load(WORK / 'meta.npz', allow_pickle=True)
    meta = {k: m[k] for k in m.files}
    mag = meta['mag'].astype(np.float64)
    fold = meta['fold'].astype(int)
    n = len(mag)
    feat = features(meta).astype(np.float64)
    hyp = meta['hyp_km'].astype(np.float64)
    logR = np.log10(np.clip(np.nan_to_num(hyp, nan=np.nanmedian(hyp)), 1.0, None))
    laws = args.laws.split(',')
    out = {law: WORK / 'arms' / f'lin_{law}{args.suffix}' for law in laws}
    for law, d in out.items():
        d.mkdir(parents=True, exist_ok=True)
        (d / 'record.json').write_text(json.dumps({'args': {'arm': d.name, 'head': f'linear_{law}', 'train_mag_cap': args.cap,
                                                             'cap_filter': 'bin', 'note': 'classical law; see linear_arms.py'},
                                                    'folds': {}}, indent=1))
    for k in sorted(set(fold.tolist())):
        tr = fold != k
        if args.cap is not None:
            tr &= cap_keep(mag, args.cap, 'bin')
        te = np.flatnonzero(fold == k)
        res = {law: (np.zeros((len(te), 3, len(DECISION_NAMES)), np.float32),
                     np.zeros((len(te), 3, len(PMF_CENTERS)), np.float16)) for law in laws}
        for d_i in range(3):
            F = feat[:, d_i]
            ok = np.isfinite(F).all(1) & np.isfinite(logR)
            sel = tr & ok
            A = F[:, 0]
            for law in laws:
                if law in ('fwd', 'fwdR'):
                    X = np.c_[np.ones(n), A, F[:, 1:]] if law == 'fwd' else np.c_[np.ones(n), A, logR]
                    b, *_ = np.linalg.lstsq(X[sel], mag[sel], rcond=None)
                    mu = X[te] @ b
                    sd = float(np.std(mag[sel] - X[sel] @ b))
                else:
                    Z = F[:, 1:] if law == 'inv' else logR[:, None]
                    X = np.c_[np.ones(n), mag, Z]
                    b, *_ = np.linalg.lstsq(X[sel], A[sel], rcond=None)
                    bz = np.r_[b[0], b[2:]]
                    mu = (A[te] - np.c_[np.ones(len(te)), Z[te]] @ bz) / b[1]
                    sd = float(np.std(A[sel] - X[sel] @ b) / abs(b[1]))
                mu = np.nan_to_num(mu, nan=float(np.median(mag[sel])))
                y = torch.from_numpy(mag[te]).float()
                for s in range(0, len(te), 8192):
                    sl = slice(s, s + 8192)
                    m_t = torch.from_numpy(mu[sl]).float()[:, None]
                    dist = Mixture(torch.zeros_like(m_t), m_t, torch.full_like(m_t, sd))
                    o, p = decisions(dist, y[sl])
                    res[law][0][sl, d_i] = o.numpy()
                    res[law][1][sl, d_i] = p.numpy().astype(np.float16)
                print(f'fold{k} {d_i} {law}: sd {sd:.3f} coef {np.round(b[:3], 3).tolist()}', flush=True)
        for law in laws:
            np.savez(out[law] / f'fold{k}.npz', rows=te, dec=res[law][0], pmf=res[law][1])


if __name__ == '__main__':
    main()

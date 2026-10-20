"""Build a single-station cache from the Northern-Chile TEAM-LM data in the tailwork layout.

The source cache (chile_train_dev_full3000.hdf5) holds, per event, all station traces as
30 s windows at 100 Hz in m/s, from 5 s before the network-first P to 25 s after, on a common
clock. Per-station P picks are not provided, so each trace is picked here:

  1. causal band-pass 1-20 Hz on the vertical component;
  2. STA/LTA (0.5 s / 5 s), first trigger >= --trigger after the network P;
  3. AIC refinement in +-1 s around the trigger;
  4. accept if RMS(1 s after pick) / RMS(1 s before pick) >= --snr and pick + 5 s fits.

The 5 s after the pick (E, N, Z) is stored like the other caches (wave16/scale/meta.npz,
phys_factor = 1). Event folds: Gardner-Knopoff sequences balanced on M>=5 / M>=6.

  TAILWORK_DIR=/mnt/eew-research/runs/tailwork/chile python tailrisk/chile_prep.py --order ZNE
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy.signal import butter, lfilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prep_data import sequence_clusters, assign_folds, haversine_km  # noqa: E402

SRC = Path('/mnt/eew-research/chile/chile_train_dev_full3000.hdf5')
OUT = Path(os.environ.get('TAILWORK_DIR', '/mnt/eew-research/runs/tailwork/chile'))
SR = 100
PRE = 5 * SR            # network-first P at sample 500
STA, LTA = int(0.5 * SR), 5 * SR
B, A = butter(4, [1.0 / (SR / 2), 20.0 / (SR / 2)], btype='band')


def load_event_meta(h):
    """Read the PyTables event table with h5py (pandas' reader is unavailable here)."""
    t = h['metadata/event_metadata/table'][:]
    cols0 = ['LAT', 'LON', 'DEPTH', 'TIME', 'ML', 'MW_SIPPL', 'M_EXT', 'MA', 'std_MA']
    df = pd.DataFrame(t['values_block_0'], columns=cols0)
    df['source_row_index'] = t['values_block_1'][:, 0]
    ev = [v[0].decode() if isinstance(v[0], bytes) else str(v[0]) for v in t['values_block_2']]
    df['benchmark_split'] = [v[3].decode() if isinstance(v[3], bytes) else str(v[3]) for v in t['values_block_2']]
    df.index = pd.Index(ev, name='EVENT')
    return df


def pick(z, trigger, snr_min):
    """Return the P sample on one vertical trace, or -1."""
    f = lfilter(B, A, z - z[:PRE].mean())
    e = f * f
    cs = np.concatenate([[0.0], np.cumsum(e)])
    n = len(f)
    i = np.arange(LTA, n)
    sta = (cs[i + 1] - cs[i + 1 - STA]) / STA
    lta = (cs[i + 1 - STA] - cs[i + 1 - STA - (LTA - STA)]) / (LTA - STA) + 1e-30
    ratio = sta / lta
    cand = np.flatnonzero((ratio >= trigger) & (i >= PRE))
    if not len(cand):
        return -1
    t = int(i[cand[0]])
    lo, hi = max(PRE - SR, t - SR), min(n - 1, t + SR)
    seg = f[lo:hi]
    k = np.arange(1, len(seg) - 1)
    c1 = np.cumsum(seg * seg)
    v1 = c1[k - 1] / k
    v2 = (c1[-1] - c1[k - 1]) / (len(seg) - k)
    aic = k * np.log(v1 + 1e-30) + (len(seg) - k) * np.log(v2 + 1e-30)
    p = lo + int(k[np.argmin(aic)])
    if p < SR or p + 5 * SR > n:
        return -1
    post = np.sqrt((f[p:p + SR] ** 2).mean())
    pre = np.sqrt((f[p - SR:p] ** 2).mean()) + 1e-30
    return p if post / pre >= snr_min else -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--order', default='ZNE', help='component order in the source arrays')
    ap.add_argument('--trigger', type=float, default=4.0)
    ap.add_argument('--snr', type=float, default=3.0)
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--limit', type=int, default=0, help='debug: first N events only')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    order = [args.order.index(c) for c in 'ENZ']
    zi = args.order.index('Z')
    h = h5py.File(SRC, 'r')
    em = load_event_meta(h)
    keys = [k for k in h['data'].keys() if k in set(em.index)]
    if args.limit:
        keys = keys[:args.limit]
    waves, rows = [], []
    t0 = time.time()
    n_tr = n_ok = 0
    for j, k in enumerate(keys):
        g = h['data'][k]
        w = g['waveforms'][:]                       # (n, 3000, 3)
        coords = g['coords'][:]
        stations = [s.decode() if isinstance(s, bytes) else str(s) for s in g['stations'][:]]
        for s in range(w.shape[0]):
            n_tr += 1
            z = w[s, :, zi].astype(np.float64)
            if not np.isfinite(z).all() or np.abs(z).max() == 0:
                continue
            p = pick(z, args.trigger, args.snr)
            if p < 0:
                continue
            seg = w[s, p:p + 5 * SR, :].T[order].astype(np.float32)        # (3, 500) E, N, Z
            waves.append(seg)
            rows.append({'event': k, 'station': stations[s], 'sta_lat': coords[s, 0], 'sta_lon': coords[s, 1],
                         'sta_elev': coords[s, 2] if coords.shape[1] > 2 else 0.0, 'p_sample': p,
                         'p_after_network_s': (p - PRE) / SR})
            n_ok += 1
        if j % 2000 == 0:
            print(f'{j}/{len(keys)} events, {n_ok}/{n_tr} traces picked, {time.time() - t0:.0f}s', flush=True)
    frame = pd.DataFrame(rows)
    n = len(frame)
    print('picked traces', n, 'of', n_tr, 'events with traces', frame.event.nunique(), flush=True)
    wave = np.stack(waves)
    scale = np.abs(wave).reshape(n, -1).max(1)
    scale = np.where(scale > 0, scale, 1.0).astype(np.float32)
    np.save(OUT / 'wave16.npy', (wave / scale[:, None, None]).astype(np.float16))
    np.save(OUT / 'scale.npy', scale)

    ev_meta = em.loc[frame.event.unique()]
    ev = pd.DataFrame({'source_id': ev_meta.index, 'lat': ev_meta['LAT'].to_numpy(float),
                       'lon': ev_meta['LON'].to_numpy(float), 'depth': ev_meta['DEPTH'].to_numpy(float),
                       'mag': ev_meta['MA'].to_numpy(float), 't': ev_meta['TIME'].to_numpy(float)})
    ev['mag_type'] = 'MA'
    ev['records'] = frame.groupby('event').size().reindex(ev.source_id).to_numpy()
    ev['m4'] = (ev.mag >= 5).astype(int)
    ev['m5'] = (ev.mag >= 6).astype(int)
    ev['cluster'] = sequence_clusters(ev, 0.25)
    ev['fold'] = assign_folds(ev, args.folds)
    ev['split'] = 'train'
    ev.to_csv(OUT / 'events.csv', index=False)
    eidx = frame.event.map({s: i for i, s in enumerate(ev.source_id)}).to_numpy(np.int64)
    stations, sidx = np.unique(frame.station.to_numpy(), return_inverse=True)
    epi = haversine_km(ev.lat.to_numpy()[eidx], ev.lon.to_numpy()[eidx], frame.sta_lat.to_numpy(), frame.sta_lon.to_numpy())
    static = np.stack([frame.sta_elev.to_numpy(float) / 1000.0, frame.p_after_network_s.to_numpy(float) * 0.0], 1).astype(np.float32)
    np.savez(OUT / 'meta.npz',
             split=np.zeros(n, np.int8), event=eidx, station=sidx.astype(np.int32), stations=stations,
             family=np.zeros(n, np.int8), families=np.array(['HH']),
             mag=ev.mag.to_numpy()[eidx].astype(np.float32), mag_type=np.array(['MA'] * n),
             fold=ev.fold.to_numpy()[eidx].astype(np.int8), cluster=ev.cluster.to_numpy()[eidx].astype(np.int64),
             static=static, static_names=np.array(['elevation_km', 'zero']), gains=np.ones((n, 3)), usable=np.ones((n, 3), bool),
             phys_factor=np.ones((n, 3), np.float32),
             sta_lat=frame.sta_lat.to_numpy(np.float32), sta_lon=frame.sta_lon.to_numpy(np.float32),
             hyp_km=np.sqrt(epi ** 2 + np.nan_to_num(ev.depth.to_numpy()[eidx], nan=30.0) ** 2).astype(np.float32),
             epi_km=epi.astype(np.float32), depth_km=ev.depth.to_numpy()[eidx].astype(np.float32),
             baz=np.full(n, np.nan, np.float32), p_sample=frame.p_sample.to_numpy(np.float32),
             s_sample=np.full(n, np.nan, np.float32), origin_t=ev.t.to_numpy()[eidx].astype(np.float64),
             trace_name=(frame.event + '/' + frame.station).to_numpy(), rate=np.full(n, 100.0, np.float32),
             p_after_network_s=frame.p_after_network_s.to_numpy(np.float32))
    summary = {'records': int(n), 'traces_seen': int(n_tr), 'events': int(len(ev)), 'clusters': int(ev.cluster.nunique()),
               'component_order_in_source': args.order, 'trigger': args.trigger, 'snr': args.snr, 'folds': {}}
    for f in range(args.folds):
        e = ev[ev.fold == f]
        summary['folds'][f] = {'events': int(len(e)), 'records': int(e.records.sum()),
                               'M>=5 events': int((e.mag >= 5).sum()), 'M>=6 events': int((e.mag >= 6).sum()),
                               'max_mag': float(e.mag.max())}
    summary['epi_km_pct'] = [float(x) for x in np.nanpercentile(epi, [5, 50, 95])]
    (OUT / 'folds.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()

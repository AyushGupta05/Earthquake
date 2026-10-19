"""Build a second-dataset cache from GEOFON (SeisBench mirror) in the tailwork layout.

Reads only the needed rows of each HDF5 bucket over HTTP (no 26 GB download), takes
the 5 s window after the catalogue P pick at the native rate, converts counts to m/s
with the station sensitivity, resamples to 100 Hz (500 samples) and stores it like the
INSTANCE cache: wave16.npy (N, 3, 500) float16 scaled per record, scale.npy, meta.npz
(with phys_factor = 1, so GPUData treats the cache as physical units), events.csv,
folds.json. Component order is E, N, Z as in the INSTANCE cache.

  TAILWORK_DIR=/mnt/eew-research/runs/tailwork/geofon python tailrisk/geofon_prep.py --max-km 2000 --workers 4
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path

import fsspec
import h5py
import numpy as np
import pandas as pd
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prep_data import sequence_clusters, assign_folds, haversine_km  # noqa: E402

URL = 'https://seisbench.gfz-potsdam.de/mirror/datasets/geofon/waveforms.hdf5'
OUT = Path(os.environ.get('TAILWORK_DIR', '/mnt/eew-research/runs/tailwork/geofon'))
FAMILIES = ['BH', 'HH', 'SH', 'EH', 'CH']
SEC = 5.0


def select(meta, max_km):
    m = meta.copy()
    m['epi_km'] = haversine_km(m.source_latitude_deg.to_numpy(), m.source_longitude_deg.to_numpy(),
                               m.station_latitude_deg.to_numpy(), m.station_longitude_deg.to_numpy())
    ok = (m.epi_km < max_km) & m.trace_P_arrival_sample.notna() & (m.trace_P_arrival_sample >= 0)
    ok &= np.isfinite(m.station_sensitivity_counts_spm) & (m.station_sensitivity_counts_spm > 0)
    ok &= m.trace_completeness >= 0.99
    ok &= m.source_magnitude.notna()
    m = m[ok].copy()
    parts = m.trace_name.str.extract(r'^(bucket\d+)\$(\d+),:(\d+),:(\d+)$')
    m['bucket'], m['row'], m['ncomp'], m['nsamp'] = parts[0], parts[1].astype(int), parts[2].astype(int), parts[3].astype(int)
    need = np.round(m.trace_sampling_rate_hz * SEC).astype(int)
    m = m[(m.trace_P_arrival_sample + need <= m.nsamp) & (m.ncomp == 3)].copy()
    return m.reset_index(drop=True)


def to_100hz(x, rate):
    """x: (3, n) native-rate window of SEC seconds -> (3, 500) at 100 Hz."""
    fr = Fraction(100 / rate).limit_denominator(200)
    y = resample_poly(x, fr.numerator, fr.denominator, axis=-1)
    if y.shape[-1] >= 500:
        return y[:, :500]
    return np.pad(y, ((0, 0), (0, 500 - y.shape[-1])), mode='edge')


def worker(args):
    buckets, frame, order, wid = args
    f = fsspec.open(URL, 'rb', block_size=16 * 2 ** 20).open()
    h = h5py.File(f, 'r')
    out = {}
    t0 = time.time()
    for b in buckets:
        sub = frame[frame.bucket == b].sort_values('row')
        rows = sub.row.to_numpy()
        data = h['data'][b][rows]                        # (k, 3, L) float64, only needed rows
        for i, r in enumerate(sub.itertuples(index=False)):
            rate = float(r.trace_sampling_rate_hz)
            n = int(round(rate * SEC))
            p = int(round(r.trace_P_arrival_sample))
            w = data[i][:, p:p + n].astype(np.float64)
            w = w[order] / float(r.station_sensitivity_counts_spm)     # E, N, Z in m/s
            if not np.isfinite(w).all():
                continue
            out[r.trace_name] = to_100hz(w, rate).astype(np.float32)
        print(f'worker {wid}: {b} ({len(rows)} rows) done, {len(out)} traces, {time.time() - t0:.0f}s', flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-km', type=float, default=2000.0)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--folds', type=int, default=5)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    meta = pd.read_csv(OUT / 'metadata.csv', low_memory=False)
    frame = select(meta, args.max_km)
    print('selected traces', len(frame), 'events', frame.source_id.nunique(), flush=True)
    f = fsspec.open(URL, 'rb', block_size=2 ** 20).open()
    h = h5py.File(f, 'r')
    comp = h['data_format'].attrs.get('component_order', 'ZNE')
    comp = comp.decode() if isinstance(comp, bytes) else str(comp)
    order = [comp.index(c) for c in 'ENZ']
    print('component order in file', comp, '-> ENZ indices', order, flush=True)
    buckets = sorted(frame.bucket.unique(), key=lambda s: int(s[6:]))
    groups = [buckets[i::args.workers] for i in range(args.workers)]
    waves = {}
    with ThreadPoolExecutor(args.workers) as ex:
        for part in ex.map(worker, [(g, frame, order, i) for i, g in enumerate(groups)]):
            waves.update(part)
    frame = frame[frame.trace_name.isin(waves)].reset_index(drop=True)
    n = len(frame)
    print('traces with waveforms', n, flush=True)
    wave = np.stack([waves[t] for t in frame.trace_name])
    scale = np.abs(wave).reshape(n, -1).max(1)
    scale = np.where(scale > 0, scale, 1.0).astype(np.float32)
    np.save(OUT / 'wave16.npy', (wave / scale[:, None, None]).astype(np.float16))
    np.save(OUT / 'scale.npy', scale)

    origin = pd.to_datetime(frame.source_origin_time, utc=True, format='ISO8601')
    frame['t'] = (origin - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds()
    ev = frame.groupby('source_id', sort=False).agg(
        t=('t', 'first'), lat=('source_latitude_deg', 'first'), lon=('source_longitude_deg', 'first'),
        depth=('source_depth_km', 'first'), mag=('source_magnitude', 'first'),
        mag_type=('source_magnitude_type', 'first'), records=('trace_name', 'size')).reset_index()
    ev['m4'] = (ev.mag >= 6).astype(int)      # balancing targets: M>=6 and M>=7 events
    ev['m5'] = (ev.mag >= 7).astype(int)
    ev['cluster'] = sequence_clusters(ev, 0.25)
    ev['fold'] = assign_folds(ev, args.folds)
    ev['split'] = 'train'
    ev.to_csv(OUT / 'events.csv', index=False)
    eidx = frame.source_id.map({s: i for i, s in enumerate(ev.source_id)}).to_numpy(np.int64)
    station_key = (frame.station_network_code.astype(str) + '.' + frame.station_code.astype(str)).to_numpy()
    stations, sidx = np.unique(station_key, return_inverse=True)
    fam = frame.trace_channel.astype(str).to_numpy()
    families, fidx = np.unique(fam, return_inverse=True)
    static = np.stack([np.log10(frame.station_sensitivity_counts_spm.to_numpy(float))]
                      + [(fam == f).astype(float) for f in FAMILIES]
                      + [np.log10(frame.trace_sampling_rate_hz.to_numpy(float)),
                         np.nan_to_num(frame.station_elevation_m.to_numpy(float), nan=0.0) / 1000.0], 1).astype(np.float32)
    names = ['log10_sensitivity'] + [f'family_{f}' for f in FAMILIES] + ['log10_rate', 'elevation_km']
    np.savez(OUT / 'meta.npz',
             split=np.zeros(n, np.int8), event=eidx, station=sidx.astype(np.int32), stations=stations,
             family=fidx.astype(np.int8), families=families,
             mag=frame.source_magnitude.to_numpy(np.float32), mag_type=frame.source_magnitude_type.astype(str).to_numpy(),
             fold=ev.fold.to_numpy()[eidx].astype(np.int8), cluster=ev.cluster.to_numpy()[eidx].astype(np.int64),
             static=static, static_names=np.array(names), gains=np.ones((n, 3)), usable=np.ones((n, 3), bool),
             phys_factor=np.ones((n, 3), np.float32),
             sta_lat=frame.station_latitude_deg.to_numpy(np.float32), sta_lon=frame.station_longitude_deg.to_numpy(np.float32),
             hyp_km=np.sqrt(frame.epi_km.to_numpy(float) ** 2 + np.nan_to_num(frame.source_depth_km.to_numpy(float), nan=10.0) ** 2).astype(np.float32),
             epi_km=frame.epi_km.to_numpy(np.float32), depth_km=frame.source_depth_km.to_numpy(np.float32),
             baz=frame.path_back_azimuth_deg.to_numpy(np.float32), p_sample=np.zeros(n, np.float32),
             s_sample=np.full(n, np.nan, np.float32), origin_t=frame.t.to_numpy(np.float64),
             trace_name=frame.trace_name.to_numpy(), rate=frame.trace_sampling_rate_hz.to_numpy(np.float32))
    summary = {'records': int(n), 'events': int(len(ev)), 'clusters': int(ev.cluster.nunique()), 'max_km': args.max_km,
               'component_order_in_file': comp, 'folds': {}}
    for f in range(args.folds):
        e = ev[ev.fold == f]
        summary['folds'][f] = {'events': int(len(e)), 'records': int(e.records.sum()),
                               'M>=6 events': int((e.mag >= 6).sum()), 'M>=7 events': int((e.mag >= 7).sum()),
                               'max_mag': float(e.mag.max())}
    summary['mag_types'] = {k: int(v) for k, v in frame.source_magnitude_type.value_counts().items()}
    summary['rates'] = {str(k): int(v) for k, v in frame.trace_sampling_rate_hz.round().value_counts().items()}
    (OUT / 'folds.json').write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()

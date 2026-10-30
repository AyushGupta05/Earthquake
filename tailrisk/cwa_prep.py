"""Build a fifth-catalogue cache from CWA (Taiwan Central Weather Administration; SeisBench mirror).

CWA holds 1.33 M three-component earthquake traces (2011-2021, 17,051 events, local magnitude
ML for every event, manual P picks) from the CWASN and TSMIP networks, one contiguous float64
HDF5 dataset per trace (component order Z, N, E), split into one file per year (2-83 GB).
Range-reading 1.3 M separate datasets over HTTP is too slow, so each year file is downloaded
with parallel range requests, the 5 s windows are cut locally, and the file is deleted.

Units (checked against the metadata's PGA / PGV, 30 Oct): HL accelerometers are stored in
cm/s^2 (sensitivity field 1); EH and HH velocity sensors are counts, and counts times the
'station_sensitivity_counts_spm' field is cm/s. phys_factor converts to SI (m/s^2 for HL, m/s
for EH / HH), as for INSTANCE's mix of HN accelerometers and velocity sensors.

Selection (fixed in PREREGISTRATION_CWA.md before any model sees CWA): 100 Hz traces (drops the
7% TSMIP traces at 200 / 500 Hz), P pick with 500 samples after it, finite non-zero vertical.
Labels: the catalogue ML of each event (no conversion). Folds: Gardner-Knopoff sequences,
largest first, five folds balanced on M>=5 / M>=4 events and records (prep_data.py).

  TAILWORK_DIR=/mnt/cwa/cache python cwa_prep.py --raw /mnt/cwa/raw --workers 16
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prep_data import assign_folds, haversine_km, sequence_clusters  # noqa: E402

BASE = 'https://seisbench.gfz-potsdam.de/mirror/datasets/cwa/'
YEARS = list(range(2011, 2022))
FAMILIES = ['HH', 'EH', 'HL']
SR, NWIN = 100, 500
OUT = Path(os.environ.get('TAILWORK_DIR', '/mnt/cwa/cache'))
ZNE_TO_ENZ = [2, 1, 0]


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def utc_seconds(s):
    t = pd.to_datetime(s, utc=True, format='mixed', errors='coerce')
    return (t - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds().to_numpy()


def parse_sens(s):
    return np.array([float(v) for v in str(s).strip('[]').replace(',', ' ').split()][:3], float)


# ------------------------------------------------------------------ download
def head_size(url):
    req = urllib.request.Request(url, method='HEAD')
    with urllib.request.urlopen(req, timeout=120) as r:
        return int(r.headers['Content-Length'])


def fetch_range(url, lo, hi, tries=6):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'Range': f'bytes={lo}-{hi}'})
            with urllib.request.urlopen(req, timeout=600) as r:
                body = r.read()
            if len(body) == hi - lo + 1:
                return body
            err = RuntimeError(f'short read {len(body)}')
        except Exception as e:  # noqa: BLE001 - network errors are retried
            err = e
        time.sleep(5 * (k + 1))
    raise RuntimeError(f'{url} {lo}-{hi}: {err}')


def download(year, raw, workers, chunk=128 << 20):
    url = f'{BASE}waveforms_{year}.hdf5'
    path = raw / f'waveforms_{year}.hdf5'
    size = head_size(url)
    if path.exists() and path.stat().st_size == size and (raw / f'waveforms_{year}.ok').exists():
        return path
    t0 = time.time()
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    os.ftruncate(fd, size)

    def job(lo):
        hi = min(lo + chunk, size) - 1
        os.pwrite(fd, fetch_range(url, lo, hi), lo)
        return hi - lo + 1
    with ThreadPoolExecutor(workers) as ex:
        got = sum(ex.map(job, range(0, size, chunk)))
    os.close(fd)
    assert got == size, (got, size)
    (raw / f'waveforms_{year}.ok').write_text(str(size))
    dt = time.time() - t0
    log(f'downloaded {year}: {size / 1e9:.1f} GB in {dt / 60:.1f} min ({size / dt / 1e6:.0f} MB/s)')
    return path


# ------------------------------------------------------------------ selection
def select(raw):
    cols = ['source_origin_time', 'source_depth_km', 'source_latitude_deg', 'source_longitude_deg',
            'source_magnitude', 'source_magnitude_type', 'source_event_id', 'station_code',
            'station_network_code', 'station_location_code', 'trace_channel', 'trace_start_time',
            'station_sensitivity_counts_spm', 'station_longitude_deg', 'station_latitude_deg',
            'station_elevation_m', 'trace_name', 'trace_sampling_rate_hz', 'trace_npts',
            'trace_p_arrival_sample', 'trace_p_arrival_time', 'trace_s_arrival_sample', 'path_ep_distance_km',
            'path_back_azimuth_deg', 'trace_seismographic_network', 'split']
    frames = []
    for y in YEARS:
        m = pd.read_csv(raw / f'metadata_{y}.csv', usecols=cols, low_memory=False)
        m['year'] = y
        frames.append(m)
    meta = pd.concat(frames, ignore_index=True)
    counts = {'cwa_traces': int(len(meta))}
    meta = meta[meta.trace_sampling_rate_hz == SR]
    counts['at_100Hz'] = int(len(meta))
    p = meta.trace_p_arrival_sample.to_numpy(float)
    meta = meta[np.isfinite(p) & (p >= 0) & (p + NWIN <= meta.trace_npts.to_numpy()) & meta.source_magnitude.notna()
                & meta.trace_channel.isin(FAMILIES)].copy()
    counts['with_P_window_and_mag'] = int(len(meta))
    sens = np.stack(meta.station_sensitivity_counts_spm.map(parse_sens).to_numpy())
    meta['sens_Z'], meta['sens_N'], meta['sens_E'] = sens[:, 0], sens[:, 1], sens[:, 2]
    ok = np.isfinite(sens).all(1) & (sens > 0).all(1)
    meta = meta[ok].copy()
    counts['with_sensitivity'] = int(len(meta))
    meta['t_origin'] = utc_seconds(meta.source_origin_time)
    meta['t_p'] = utc_seconds(meta.trace_p_arrival_time)
    meta = meta.sort_values(['year', 'trace_name']).reset_index(drop=True)
    ev = meta.groupby('source_event_id').source_magnitude.first()
    counts['events'] = int(len(ev))
    for t in (4, 5, 6, 7):
        counts[f'events_M>={t}'] = int((ev >= t).sum())
    counts['families'] = {k: int(v) for k, v in meta.trace_channel.value_counts().items()}
    log(json.dumps(counts, indent=1))
    return meta, counts


# ------------------------------------------------------------------ waveforms
def extract_year(frame, idx, h5path, wave, scale, live):
    h = h5py.File(h5path, 'r')
    d = h['data']
    p_all = np.round(frame.trace_p_arrival_sample.to_numpy()).astype(int)
    names = frame.trace_name.to_numpy()
    bad = 0
    for k, i in enumerate(idx):
        p = p_all[i]
        try:
            w = d[names[i]][:, p:p + NWIN][ZNE_TO_ENZ].astype(np.float32)
        except KeyError:
            scale[i] = -1.0
            bad += 1
            continue
        if w.shape != (3, NWIN) or not np.isfinite(w).all():
            scale[i] = -1.0
            bad += 1
            continue
        live[i] = (np.abs(w).max(1) > 0).astype(np.int8)
        s = float(np.abs(w).max())
        scale[i] = s if s > 0 else -1.0
        wave[i] = (w / (s if s > 0 else 1.0)).astype(np.float16)
        if k % 50000 == 0:
            log(f'  {k}/{len(idx)}')
    h.close()
    return bad


def stream_waves(frame, raw, workers, keep_raw):
    n = len(frame)
    mode = 'r+' if (OUT / 'wave16.npy').exists() else 'w+'
    wave = np.lib.format.open_memmap(OUT / 'wave16.npy', mode, np.float16, (n, 3, NWIN))
    scale = np.lib.format.open_memmap(OUT / 'scale_partial.npy', mode, np.float32, (n,))
    live = np.lib.format.open_memmap(OUT / 'live_partial.npy', mode, np.int8, (n, 3))
    done_path = OUT / 'done_years.txt'
    done = set(done_path.read_text().split()) if done_path.exists() and mode == 'r+' else set()
    groups = frame.groupby('year').indices
    for y in YEARS:
        if str(y) in done or y not in groups:
            continue
        path = download(y, raw, workers)
        t0 = time.time()
        bad = extract_year(frame, groups[y], path, wave, scale, live)
        wave.flush(); scale.flush(); live.flush()
        with open(done_path, 'a') as f:
            f.write(f'{y}\n')
        log(f'extracted {y}: {len(groups[y])} traces, {bad} bad, {(time.time() - t0) / 60:.1f} min')
        if not keep_raw:
            path.unlink()
            (raw / f'waveforms_{y}.ok').unlink(missing_ok=True)
    return np.asarray(scale), np.asarray(live).astype(bool)


def compact(keep):
    src = np.load(OUT / 'wave16.npy', mmap_mode='r')
    dst = np.lib.format.open_memmap(OUT / 'wave16.tmp.npy', 'w+', np.float16, (int(keep.sum()), 3, NWIN))
    pos = 0
    for a in range(0, len(src), 100000):
        blk = src[a:a + 100000][keep[a:a + 100000]]
        dst[pos:pos + len(blk)] = blk
        pos += len(blk)
    dst.flush()
    del src, dst
    os.replace(OUT / 'wave16.tmp.npy', OUT / 'wave16.npy')


# ------------------------------------------------------------------ meta
def write_meta(frame, scale, live, counts, n_folds):
    n = len(frame)
    np.save(OUT / 'scale.npy', scale.astype(np.float32))
    ev = frame.groupby('source_event_id', sort=False).agg(
        t=('t_origin', 'first'), lat=('source_latitude_deg', 'first'), lon=('source_longitude_deg', 'first'),
        depth=('source_depth_km', 'first'), mag=('source_magnitude', 'first'), records=('trace_name', 'size')).reset_index()
    ev['m4'] = (ev.mag >= 4).astype(int)
    ev['m5'] = (ev.mag >= 5).astype(int)
    ev['cluster'] = sequence_clusters(ev, 0.25)
    ev['fold'] = assign_folds(ev, n_folds)
    ev['split'] = 'train'
    ev.to_csv(OUT / 'events.csv', index=False)
    eidx = frame.source_event_id.map({e: i for i, e in enumerate(ev.source_event_id)}).to_numpy(np.int64)
    station_key = (frame.station_network_code.astype(str) + '.' + frame.station_code.astype(str)).to_numpy()
    stations, sidx = np.unique(station_key, return_inverse=True)
    fam = frame.trace_channel.astype(str).to_numpy()
    families, fidx = np.unique(fam, return_inverse=True)
    sens_cm = frame[['sens_E', 'sens_N', 'sens_Z']].to_numpy(float)          # cm/s per count; 1 for HL (cm/s^2)
    phys_factor = (sens_cm / 100.0).astype(np.float32)                     # -> m/s or m/s^2
    gains = 1.0 / phys_factor                                               # counts per SI unit
    usable = live.copy()
    static = np.stack([np.log10(gains[:, 2])] + [(fam == f).astype(float) for f in FAMILIES]
                      + [np.nan_to_num(frame.station_elevation_m.to_numpy(float), nan=0.0) / 1000.0,
                         (frame.trace_seismographic_network == 'TSMIP').to_numpy(float)], 1).astype(np.float32)
    names = ['log10_gain'] + [f'family_{f}' for f in FAMILIES] + ['elevation_km', 'network_TSMIP']
    epi = frame.path_ep_distance_km.to_numpy(float)
    miss = ~np.isfinite(epi)
    epi[miss] = haversine_km(frame.source_latitude_deg.to_numpy()[miss], frame.source_longitude_deg.to_numpy()[miss],
                             frame.station_latitude_deg.to_numpy()[miss], frame.station_longitude_deg.to_numpy()[miss])
    depth = frame.source_depth_km.to_numpy(float)
    hyp = np.sqrt(epi ** 2 + np.clip(np.nan_to_num(depth, nan=10.0), 0, None) ** 2)
    first = pd.Series(frame.t_p.to_numpy()).groupby(eidx).transform('min').to_numpy()
    p_src = frame.trace_p_arrival_sample.to_numpy(float)
    s_rel = frame.trace_s_arrival_sample.to_numpy(float) - np.round(p_src)
    sb_split = frame.split.map({'train': 0, 'dev': 1, 'test': 2}).fillna(-1).to_numpy(np.int8)
    np.savez(OUT / 'meta.npz',
             split=np.zeros(n, np.int8), event=eidx, station=sidx.astype(np.int32), stations=stations,
             family=fidx.astype(np.int8), families=families,
             mag=frame.source_magnitude.to_numpy(np.float32), mag_type=np.full(n, 'ML'),
             fold=ev.fold.to_numpy()[eidx].astype(np.int8), cluster=ev.cluster.to_numpy()[eidx].astype(np.int64),
             static=static, static_names=np.array(names), gains=gains, usable=usable, phys_factor=phys_factor,
             sta_lat=frame.station_latitude_deg.to_numpy(np.float32), sta_lon=frame.station_longitude_deg.to_numpy(np.float32),
             hyp_km=hyp.astype(np.float32), epi_km=epi.astype(np.float32), depth_km=depth.astype(np.float32),
             baz=frame.path_back_azimuth_deg.to_numpy(np.float32), p_sample=np.zeros(n, np.float32),
             p_sample_source=p_src.astype(np.float32), s_sample=s_rel.astype(np.float32),
             origin_t=frame.t_origin.to_numpy(np.float64), trace_name=frame.trace_name.to_numpy(),
             rate=np.full(n, float(SR), np.float32), p_after_network_s=(frame.t_p.to_numpy() - first).astype(np.float32),
             source_id=frame.source_event_id.astype(str).to_numpy(), split_seisbench=sb_split)
    summary = {'records': int(n), 'events': int(len(ev)), 'clusters': int(ev.cluster.nunique()),
               'window': 'samples p..p+500 at 100 Hz, E N Z; phys_factor -> m/s (EH, HH) or m/s^2 (HL)',
               'counts': counts, 'folds': {}}
    for f in range(n_folds):
        e = ev[ev.fold == f]
        summary['folds'][f] = {'events': int(len(e)), 'records': int(e.records.sum()), 'M>=4 events': int(e.m4.sum()),
                               'M>=5 events': int(e.m5.sum()), 'M>=6 events': int((e.mag >= 6).sum()),
                               'max_mag': float(e.mag.max())}
    big = ev.groupby('cluster').agg(events=('mag', 'size'), records=('records', 'sum'), max_mag=('mag', 'max'),
                                    m5=('m5', 'sum')).sort_values('records', ascending=False).head(12)
    summary['largest_clusters'] = big.reset_index().to_dict('records')
    summary['M>=5 clusters'] = int(ev[ev.m5 == 1].cluster.nunique())
    summary['M>=6 clusters'] = int(ev[ev.mag >= 6].cluster.nunique())
    summary['families'] = {k: int(v) for k, v in frame.trace_channel.value_counts().items()}
    summary['epi_km_pct'] = [float(x) for x in np.nanpercentile(epi, [5, 50, 95, 100])]
    (OUT / 'folds.json').write_text(json.dumps(summary, indent=1, default=str))
    log(json.dumps(summary, indent=1, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default='/mnt/cwa/raw')
    ap.add_argument('--workers', type=int, default=16)
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--keep-raw', action='store_true')
    ap.add_argument('--stop-after', choices=['select'], default=None)
    args = ap.parse_args()
    raw = Path(args.raw)
    OUT.mkdir(parents=True, exist_ok=True)
    sel = OUT / 'selected.pkl'
    if sel.exists():
        frame, counts = pd.read_pickle(sel)
        log('loaded selection', len(frame))
    else:
        frame, counts = select(raw)
        pd.to_pickle((frame, counts), sel)
    if args.stop_after == 'select':
        return
    scale, live = stream_waves(frame, raw, args.workers, args.keep_raw)
    keep = (scale > 0) & live[:, 2]
    counts['dropped_bad_waveform'] = int((~keep).sum())
    if not keep.all():
        compact(keep)
    frame, scale, live = frame[keep].reset_index(drop=True), scale[keep], live[keep]
    write_meta(frame, scale, live, counts, args.folds)
    for tmp in ('scale_partial.npy', 'live_partial.npy'):
        (OUT / tmp).unlink(missing_ok=True)
    log('done')


if __name__ == '__main__':
    main()

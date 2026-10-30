"""Build a local-distance cache from STEAD (SeisBench mirror) in the tailwork layout.

STEAD (Mousavi et al. 2019) holds 1.03 M three-component earthquake traces within
~350 km epicentral distance, 60 s at 100 Hz, ZNE, in counts (no response removal),
already detrended and band-passed 1-45 Hz by the STEAD authors. Steps:

  1. inventory: per network, FDSN channel-level station metadata (IRIS fedcatalog,
     which routes to the holding data centre) as text, cached in inventory/<NET>.txt;
     the 'Scale' column is the channel's InstrumentSensitivity (counts per m/s).
  2. select: velocity families HH/BH/EH/SH; each trace is matched to the channel
     epochs of its station and family that contain its start time; the location
     code is not in STEAD, so a station with several locations is kept only if their
     vertical sensitivities agree within 5 %. Duplicate catalogue entries of one
     earthquake (origin within 5 s, epicentres within 50 km) are merged and duplicate
     recordings dropped; one magnitude per event by type preference (Mw > ML > Md >
     mbLg > mb > other).
  3. waves: buckets are streamed with HTTP range reads (contiguous float32 rows, no
     91 GB download); the 5 s after the catalogue P pick (samples p..p+500, E, N, Z)
     is stored as counts in wave16/scale, and phys_factor = 1 / sensitivity per
     component, so wave16 * scale * phys_factor is ground velocity in m/s. p_sample = 0
     and s_sample (S - P) index the cached window; p_sample_source indexes the STEAD trace.
  4. meta: meta.npz, events.csv, folds.json (Gardner-Knopoff sequences visited
     largest-first, 5 folds balanced on M>=5 / M>=4 events / records). SeisBench's
     own split is trace-level (events cross it), so split = 0 for all rows (CV only).
  5. gain_qc.npz: station-gain epochs whose amplitudes sit > 1 dex off a global
     log-amplitude/magnitude/distance fit are flagged (analysis only; rows unchanged).

  TAILWORK_DIR=/mnt/scratch/stead python tailrisk/stead_prep.py --workers 6
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import fsspec
import h5py
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prep_data import sequence_clusters, assign_folds, haversine_km  # noqa: E402

BASE = 'https://seisbench.gfz-potsdam.de/mirror/datasets/stead/'
FEDCAT = 'https://service.iris.edu/irisws/fedcatalog/1/query'
OUT = Path(os.environ.get('TAILWORK_DIR', '/mnt/scratch/stead'))
DEST = OUT                      # stage 3-4 outputs (OUT/debug for --limit-buckets runs)
FAMILIES = ['HH', 'BH', 'EH', 'SH']
SR, NWIN, NTRACE = 100, 500, 6000
COMP_OF = {'E': 'E', '2': 'E', 'N': 'N', '1': 'N', 'Z': 'Z', '3': 'Z'}
INV_COLS = ['net', 'sta', 'loc', 'cha', 'lat', 'lon', 'elev', 'depth', 'az', 'dip', 'sensor',
            'scale', 'scale_freq', 'units', 'rate', 'start', 'end']
META_COLS = ['station_network_code', 'station_code', 'trace_channel', 'station_latitude_deg',
             'station_longitude_deg', 'station_elevation_m', 'trace_p_arrival_sample', 'trace_p_status',
             'source_id', 'source_origin_time', 'source_latitude_deg', 'source_longitude_deg',
             'source_depth_km', 'source_magnitude', 'source_magnitude_type', 'source_distance_km',
             'path_back_azimuth_deg', 'trace_snr_db', 'trace_start_time', 'trace_category', 'trace_name',
             'split', 'trace_s_arrival_sample']


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def http_get(url, headers=None, tries=5, timeout=300):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (204, 404):
                return e.code, b''
            err = e
        except Exception as e:  # noqa: BLE001 - network errors are retried
            err = e
        time.sleep(5 * (k + 1))
    raise RuntimeError(f'{url[:120]}: {err}')


def utc_seconds(s):
    t = pd.to_datetime(s, utc=True, format='ISO8601', errors='coerce')
    return (t - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds().to_numpy()


# ------------------------------------------------------------------ magnitude labels
def norm_mag_type(t):
    """STEAD lower-case types -> conventional spelling (train.py tests startswith('Mw'))."""
    t = str(t).strip().lower()
    if t.startswith('mw'):
        return 'Mw' + t[2:]
    return {'ml': 'ML', 'mlv': 'MLv', 'md': 'Md', 'mdl': 'Mdl', 'mb': 'mb', 'mb_lg': 'mbLg', 'mblg': 'mbLg',
            'mlg': 'mbLg', 'ms': 'Ms', 'mh': 'Mh', 'h': 'Mh'}.get(t, t)


def type_rank(t):
    if t.startswith('Mw'):
        return 0
    return {'ML': 1, 'MLv': 1, 'Md': 2, 'Mdl': 2, 'mbLg': 3, 'mb': 4}.get(t, 5)


# ------------------------------------------------------------------ stage 1: inventory
def fetch_inventory(meta, inv_dir):
    inv_dir.mkdir(parents=True, exist_ok=True)
    sta = meta.groupby('station_network_code').station_code.unique()
    for net, stations in sta.items():
        path = inv_dir / f'{net}.txt'
        if path.exists():
            continue
        stations = sorted(stations)
        parts = []
        for i in range(0, len(stations), 150):
            q = urllib.parse.urlencode({'net': net, 'sta': ','.join(stations[i:i + 150]),
                                        'cha': ','.join(f + '?' for f in FAMILIES),
                                        'level': 'channel', 'format': 'text'})
            try:
                code, body = http_get(f'{FEDCAT}?{q}', tries=3)
            except RuntimeError as e:
                log(f'inventory {net}: {e}; skipped (rerun to retry)')
                break
            parts.append(body.decode('utf-8', 'replace'))
        else:
            path.write_text('\n'.join(parts))
        if not path.exists():
            continue
        n = sum(1 for line in path.read_text().splitlines() if line and not line.startswith('#'))
        log(f'inventory {net}: {len(stations)} stations requested, {n} channel epochs')


def load_inventory(inv_dir):
    rows = []
    for path in sorted(inv_dir.glob('*.txt')):
        for line in path.read_text().splitlines():
            if not line or line.startswith('#'):
                continue
            f = line.split('|')
            if len(f) >= 17:
                rows.append(f[:17])
    inv = pd.DataFrame(rows, columns=INV_COLS).drop_duplicates(['net', 'sta', 'loc', 'cha', 'start'])
    for c in ('lat', 'lon', 'elev', 'depth', 'scale', 'scale_freq', 'rate'):
        inv[c] = pd.to_numeric(inv[c], errors='coerce')
    inv['t0'] = utc_seconds(inv.start)
    end = utc_seconds(inv.end.replace('', np.nan))
    inv['t1'] = np.where(np.isfinite(end), end, np.inf)
    inv['loc'] = inv['loc'].str.strip()
    inv['fam'] = inv.cha.str[:2]
    inv['comp'] = inv.cha.str[2].map(COMP_OF)
    u = inv.units.str.strip().str.lower()
    inv['to_mps'] = np.select([u.isin(['m/s', 'm/sec']), u.isin(['nm/s', 'nm/sec'])], [1.0, 1e9], np.nan)
    inv['sens'] = (inv.scale.abs() * inv.to_mps).where(inv.scale.abs() > 0)   # counts per (m/s)
    return inv[inv.comp.notna()].reset_index(drop=True)


# ------------------------------------------------------------------ stage 2: selection
def resolve_channels(c):
    """Active channel epochs of one station/family -> (status, [E, N, Z] sens, Z row)."""
    if not np.isfinite(c.sens).any():
        return 'not_velocity', None, None
    per_loc = {}
    for loc, cl in c.groupby('loc', sort=True):
        z = cl[(cl.comp == 'Z') & np.isfinite(cl.sens)]
        if len(z):
            per_loc[loc] = (cl, z.iloc[0])
    if not per_loc:
        return 'no_vertical', None, None
    zs = np.array([z.sens for _, z in per_loc.values()])
    if zs.max() / zs.min() > 1.05:
        return 'ambiguous_location', None, None
    cl, z = per_loc[sorted(per_loc, key=lambda s: (s not in ('', '00'), s))[0]]
    sens = []
    for comp in 'ENZ':
        v = cl[(cl.comp == comp) & np.isfinite(cl.sens)].sens
        sens.append(v.iloc[0] if len(v) else np.nan)
    return 'ok', sens, z


def match_sensitivity(frame, inv):
    """Per trace: E/N/Z sensitivity, native rate, sensor depth and a status string.

    Traces of one station and family whose start times fall in the same set of channel
    epochs share one resolution, so each distinct epoch set is resolved once.
    """
    n = len(frame)
    sens = np.full((n, 3), np.nan)
    rate = np.full(n, np.nan)
    depth = np.full(n, np.nan)
    dist = np.full(n, np.nan)
    status = np.full(n, 'no_inventory', dtype=object)
    t = frame.t_start.to_numpy()
    slat, slon = frame.station_latitude_deg.to_numpy(float), frame.station_longitude_deg.to_numpy(float)
    groups = inv.groupby(['net', 'sta', 'fam']).indices
    for key, idx in frame.groupby(['station_network_code', 'station_code', 'trace_channel']).indices.items():
        if key not in groups:
            continue
        g = inv.iloc[groups[key]]
        act = (g.t0.to_numpy()[None, :] <= t[idx, None]) & (t[idx, None] < g.t1.to_numpy()[None, :])
        sig, which = np.unique(act, axis=0, return_inverse=True)
        which = which.reshape(-1)
        for k, s in enumerate(sig):
            rows = idx[which == k]
            if not s.any():
                status[rows] = 'no_epoch'
                continue
            st, sv, z = resolve_channels(g[s])
            if st != 'ok':
                status[rows] = st
                continue
            sens[rows] = sv
            rate[rows], depth[rows] = z.rate, z.depth
            dist[rows] = haversine_km(slat[rows], slon[rows], z.lat, z.lon)
            status[rows] = np.where(dist[rows] <= 5.0, 'ok', 'station_moved')
    return sens, rate, depth, dist, status


def merge_duplicate_events(ev, max_dt=5.0, max_km=50.0):
    """Union catalogue entries of one earthquake (different source_id, same origin)."""
    order = np.argsort(ev.t.to_numpy())
    t, lat, lon = ev.t.to_numpy()[order], ev.lat.to_numpy()[order], ev.lon.to_numpy()[order]
    parent = np.arange(len(ev))

    def root(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i in range(len(t)):
        j = i + 1
        while j < len(t) and t[j] - t[i] < max_dt:
            if haversine_km(lat[i], lon[i], lat[j], lon[j]) < max_km:
                parent[root(j)] = root(i)
            j += 1
    group = np.array([root(i) for i in range(len(t))])
    out = np.empty(len(ev), np.int64)
    out[order] = group
    return out


def select(args):
    meta = pd.read_csv(OUT / 'raw' / 'metadata.csv', usecols=META_COLS, low_memory=False)
    counts = {'stead_traces': int(len(meta))}
    meta = meta[meta.trace_category == 'earthquake_local']
    counts['earthquake_traces'] = int(len(meta))
    meta = meta[meta.trace_p_arrival_sample.notna() & meta.source_magnitude.notna()]
    p = np.round(meta.trace_p_arrival_sample.to_numpy()).astype(int)
    meta = meta[(p >= 0) & (p + NWIN <= NTRACE)]
    counts['with_P_and_mag'] = int(len(meta))
    meta = meta[meta.trace_channel.isin(FAMILIES)].copy()
    counts['velocity_families'] = int(len(meta))
    fetch_inventory(meta, OUT / 'inventory')
    inv = load_inventory(OUT / 'inventory')
    log('inventory channel epochs', len(inv), 'networks', inv.net.nunique())
    meta['t_start'] = utc_seconds(meta.trace_start_time)
    meta = meta.reset_index(drop=True)
    sens, rate, depth, dist, status = match_sensitivity(meta, inv)
    meta['sens_E'], meta['sens_N'], meta['sens_Z'] = sens.T
    meta['native_rate'], meta['sensor_depth_m'], meta['inv_offset_km'] = rate, depth, dist
    meta['inv_status'] = status
    counts['sensitivity_status'] = {k: int(v) for k, v in meta.inv_status.value_counts().items()}
    big = meta.source_magnitude >= 5
    counts['sensitivity_status_M>=5'] = {k: int(v) for k, v in meta[big].inv_status.value_counts().items()}
    by_net = meta.groupby('station_network_code').inv_status.apply(lambda s: float((s == 'ok').mean()))
    counts['ok_fraction_by_network_top'] = {k: round(v, 3) for k, v in
                                            by_net[meta.station_network_code.value_counts().index[:30]].items()}
    meta = meta[meta.inv_status == 'ok'].copy()
    counts['horizontal_sensitivity_missing'] = int((~np.isfinite(meta[['sens_E', 'sens_N']].to_numpy())).any(1).sum())

    # events: one row per source_id, merge duplicate catalogue entries, one label per event
    meta['t_origin'] = utc_seconds(meta.source_origin_time)
    meta['mag_type_norm'] = meta.source_magnitude_type.map(norm_mag_type)
    meta['mag_rank'] = meta.mag_type_norm.map(type_rank)
    # source_id alone is not unique in STEAD (a few ids are reused for different origins)
    meta['src_key'] = meta.source_id.astype(str) + '@' + meta.t_origin.round(1).astype(str)
    src = meta.groupby('src_key').agg(t=('t_origin', 'first'), lat=('source_latitude_deg', 'first'),
                                      lon=('source_longitude_deg', 'first')).reset_index()
    src['group'] = merge_duplicate_events(src)
    meta['evg'] = meta.src_key.map(dict(zip(src.src_key, src.group)))
    counts['source_ids'] = int(len(src))
    counts['merged_events'] = int(src.group.nunique())
    best = meta.groupby('evg').mag_rank.min()
    lab = meta[meta.mag_rank.to_numpy() == best.reindex(meta.evg).to_numpy()]
    lab = lab.groupby('evg').agg(mag=('source_magnitude', 'median'), mag_type=('mag_type_norm', 'first'))
    meta['mag'] = meta.evg.map(lab.mag).round(2)
    meta['mag_type'] = meta.evg.map(lab.mag_type)
    # duplicate recordings: STEAD holds time-shifted copies of one recording (same station,
    # family and absolute P time, window start shifted 1-5 s) and one copy per catalogue entry
    meta['manual'] = (meta.trace_p_status == 'manual').astype(int)
    meta['t_p'] = meta.t_start + meta.trace_p_arrival_sample / SR
    key = ['evg', 'station_network_code', 'station_code', 'trace_channel']
    meta = meta.sort_values(key + ['t_p'])
    same = (meta[key] == meta[key].shift()).all(1).to_numpy()
    dup = pd.Series(same & (np.diff(meta.t_p.to_numpy(), prepend=-np.inf) < 1.0), index=meta.index)
    counts['duplicate_recordings_dropped'] = int(dup.sum())
    meta = meta[~dup].copy()
    parts = meta.trace_name.str.extract(r'^(bucket\d+)\$(\d+),:(\d+),:(\d+)$')
    meta['bucket'], meta['row'] = parts[0], parts[1].astype(int)
    meta['bnum'] = meta.bucket.str[6:].astype(int)
    meta = meta.sort_values(['bnum', 'row']).reset_index(drop=True)
    counts['selected_records'] = int(len(meta))
    counts['selected_events'] = int(meta.evg.nunique())
    ev = meta.groupby('evg').mag.first()
    for m in (4, 5, 6, 7):
        counts[f'selected_events_M>={m}'] = int((ev >= m).sum())
    log(json.dumps(counts, indent=1))
    return meta, counts


# ------------------------------------------------------------------ stage 3: waveforms
def bucket_layout(buckets):
    """Byte offset of each contiguous float32 bucket dataset in the HDF5 file."""
    path = OUT / 'bucket_offsets.json'
    lay = json.loads(path.read_text()) if path.exists() else {}
    need = [b for b in buckets if b not in lay]
    if need:
        f = fsspec.open(BASE + 'waveforms.hdf5', 'rb', block_size=2 ** 18).open()
        h = h5py.File(f, 'r')
        comp = h['data_format/component_order'][()]
        assert (comp.decode() if isinstance(comp, bytes) else str(comp)) == 'ZNE', comp
        for j, b in enumerate(need):
            d = h['data'][b]
            assert d.dtype == np.dtype('<f4') and d.chunks is None and d.compression is None, (b, d.dtype, d.chunks)
            assert d.shape[1:] == (3, NTRACE), (b, d.shape)
            lay[b] = [int(d.id.get_offset()), int(d.shape[0])]
            if j % 100 == 0:
                log(f'offsets {j}/{len(need)}')
                path.write_text(json.dumps(lay))
        path.write_text(json.dumps(lay))
    return lay


def fetch_rows(offset, rows):
    """Download the listed rows of one bucket, merging nearby rows into one range read."""
    rowbytes = 3 * NTRACE * 4
    out = {}
    runs, start = [], 0
    for k in range(1, len(rows) + 1):
        if k == len(rows) or rows[k] - rows[k - 1] > 8:
            runs.append((rows[start], rows[k - 1]))
            start = k
    for a, b in runs:
        lo = offset + a * rowbytes
        hi = offset + (b + 1) * rowbytes - 1
        code, body = http_get(BASE + 'waveforms.hdf5', {'Range': f'bytes={lo}-{hi}'})
        if len(body) != hi - lo + 1:
            raise RuntimeError(f'short read {len(body)} != {hi - lo + 1}')
        block = np.frombuffer(body, '<f4').reshape(b - a + 1, 3, NTRACE)
        for r in rows[(rows >= a) & (rows <= b)]:
            out[int(r)] = block[r - a]
    return out


def stream_waves(frame, workers):
    n = len(frame)
    mode = 'r+' if (DEST / 'wave16.npy').exists() else 'w+'
    if mode == 'w+':
        (DEST / 'done_buckets.txt').unlink(missing_ok=True)
    wave = np.lib.format.open_memmap(DEST / 'wave16.npy', mode, np.float16, (n, 3, NWIN))
    if wave.shape != (n, 3, NWIN):
        raise SystemExit(f'{DEST}/wave16.npy has shape {wave.shape}, selection needs {(n, 3, NWIN)}: remove it to restart')
    scale = np.lib.format.open_memmap(DEST / 'scale_partial.npy', mode, np.float32, (n,))
    live = np.lib.format.open_memmap(DEST / 'live_partial.npy', mode, np.int8, (n, 3))
    done_path = DEST / 'done_buckets.txt'
    done = set(done_path.read_text().split()) if done_path.exists() and mode == 'r+' else set()
    buckets = [b for b in frame.bucket.unique() if b not in done]
    lay = bucket_layout(list(frame.bucket.unique()))
    groups = frame.groupby('bucket').indices
    p_all = np.round(frame.trace_p_arrival_sample.to_numpy()).astype(int)
    row_all = frame.row.to_numpy()
    enz = [2, 1, 0]                                   # file order Z, N, E -> E, N, Z

    def job(b):
        idx = groups[b]
        offset, nrows = lay[b]
        assert row_all[idx].max() < nrows
        data = fetch_rows(offset, np.sort(row_all[idx]))
        for i in idx:
            p = p_all[i]
            w = data[int(row_all[i])][enz, p:p + NWIN].astype(np.float32)
            if not np.isfinite(w).all():
                scale[i] = -1.0
                continue
            live[i] = (np.abs(w).max(1) > 0).astype(np.int8)
            s = float(np.abs(w).max())
            scale[i] = s if s > 0 else -1.0
            wave[i] = (w / (s if s > 0 else 1.0)).astype(np.float16)
        return b, len(idx)

    t0 = time.time()
    nb = 0
    with ThreadPoolExecutor(workers) as ex, open(done_path, 'a') as fdone:
        futs = [ex.submit(job, b) for b in buckets]
        for fut in as_completed(futs):
            b, k = fut.result()
            nb += 1
            if nb % 25 == 0 or nb == len(buckets):
                wave.flush(); scale.flush(); live.flush()
            fdone.write(b + '\n'); fdone.flush()
            if nb % 25 == 0:
                rate = nb / (time.time() - t0)
                log(f'waves {nb}/{len(buckets)} buckets, {rate * 60:.1f} buckets/min, eta {(len(buckets) - nb) / rate / 60:.0f} min')
    wave.flush(); scale.flush(); live.flush()
    return np.asarray(scale), np.asarray(live).astype(bool)


def compact(keep):
    """Drop rows from wave16.npy in place (chunked copy, no full load)."""
    src = np.load(DEST / 'wave16.npy', mmap_mode='r')
    dst = np.lib.format.open_memmap(DEST / 'wave16.tmp.npy', 'w+', np.float16, (int(keep.sum()), 3, NWIN))
    pos = 0
    for a in range(0, len(src), 100000):
        blk = src[a:a + 100000][keep[a:a + 100000]]
        dst[pos:pos + len(blk)] = blk
        pos += len(blk)
    dst.flush()
    del src, dst
    os.replace(DEST / 'wave16.tmp.npy', DEST / 'wave16.npy')


# ------------------------------------------------------------------ stage 4: meta
def write_meta(frame, scale, live, counts, n_folds):
    n = len(frame)
    np.save(DEST / 'scale.npy', scale.astype(np.float32))
    ev = frame.groupby('evg', sort=False).agg(
        source_id=('source_id', 'first'), t=('t_origin', 'first'), lat=('source_latitude_deg', 'first'),
        lon=('source_longitude_deg', 'first'), depth=('source_depth_km', 'first'), mag=('mag', 'first'),
        mag_type=('mag_type', 'first'), records=('trace_name', 'size')).reset_index()
    ev['m4'] = (ev.mag >= 4).astype(int)
    ev['m5'] = (ev.mag >= 5).astype(int)
    ev['cluster'] = sequence_clusters(ev, 0.25)
    ev['fold'] = assign_folds(ev, n_folds)
    ev['split'] = 'train'
    ev.to_csv(DEST / 'events.csv', index=False)
    eidx = frame.evg.map({e: i for i, e in enumerate(ev.evg)}).to_numpy(np.int64)
    station_key = (frame.station_network_code.astype(str) + '.' + frame.station_code.astype(str)).to_numpy()
    stations, sidx = np.unique(station_key, return_inverse=True)
    fam = frame.trace_channel.astype(str).to_numpy()
    families, fidx = np.unique(fam, return_inverse=True)

    sens = frame[['sens_E', 'sens_N', 'sens_Z']].to_numpy(float)
    usable = np.isfinite(sens) & live
    sens = np.where(np.isfinite(sens), sens, sens[:, 2:3])       # horizontals without metadata: vertical gain
    phys_factor = (1.0 / sens).astype(np.float32)
    static = np.stack([np.log10(sens[:, 2])] + [(fam == f).astype(float) for f in FAMILIES]
                      + [np.log10(frame.native_rate.to_numpy(float)),
                         np.nan_to_num(frame.station_elevation_m.to_numpy(float), nan=0.0) / 1000.0,
                         np.nan_to_num(frame.sensor_depth_m.to_numpy(float), nan=0.0) / 1000.0], 1).astype(np.float32)
    names = ['log10_sensitivity'] + [f'family_{f}' for f in FAMILIES] + ['log10_native_rate', 'elevation_km', 'sensor_depth_km']
    epi = frame.source_distance_km.to_numpy(float)
    miss = ~np.isfinite(epi)
    epi[miss] = haversine_km(frame.source_latitude_deg.to_numpy()[miss], frame.source_longitude_deg.to_numpy()[miss],
                             frame.station_latitude_deg.to_numpy()[miss], frame.station_longitude_deg.to_numpy()[miss])
    depth = frame.source_depth_km.to_numpy(float)
    hyp = np.sqrt(epi ** 2 + np.clip(np.nan_to_num(depth, nan=10.0), 0, None) ** 2)
    p_src = frame.trace_p_arrival_sample.to_numpy(float)
    t_p = frame.t_start.to_numpy() + p_src / SR                 # absolute P time
    first = pd.Series(t_p).groupby(eidx).transform('min').to_numpy()
    s_rel = frame.trace_s_arrival_sample.to_numpy(float) - np.round(p_src)
    sb_split = frame.split.map({'train': 0, 'dev': 1, 'test': 2}).fillna(-1).to_numpy(np.int8)
    np.savez(DEST / 'meta.npz',
             split=np.zeros(n, np.int8), event=eidx, station=sidx.astype(np.int32), stations=stations,
             family=fidx.astype(np.int8), families=families,
             mag=frame.mag.to_numpy(np.float32), mag_type=frame.mag_type.astype(str).to_numpy(),
             fold=ev.fold.to_numpy()[eidx].astype(np.int8), cluster=ev.cluster.to_numpy()[eidx].astype(np.int64),
             static=static, static_names=np.array(names), gains=sens, usable=usable, phys_factor=phys_factor,
             sta_lat=frame.station_latitude_deg.to_numpy(np.float32), sta_lon=frame.station_longitude_deg.to_numpy(np.float32),
             hyp_km=hyp.astype(np.float32), epi_km=epi.astype(np.float32), depth_km=depth.astype(np.float32),
             baz=frame.path_back_azimuth_deg.to_numpy(np.float32), p_sample=np.zeros(n, np.float32),
             p_sample_source=p_src.astype(np.float32), s_sample=s_rel.astype(np.float32),
             origin_t=frame.t_origin.to_numpy(np.float64), trace_name=frame.trace_name.to_numpy(),
             rate=np.full(n, float(SR), np.float32), native_rate=frame.native_rate.to_numpy(np.float32),
             p_after_network_s=(t_p - first).astype(np.float32), p_manual=frame.manual.to_numpy(np.int8),
             source_id=frame.source_id.astype(str).to_numpy(), source_mag=frame.source_magnitude.to_numpy(np.float32),
             source_mag_type=frame.source_magnitude_type.astype(str).to_numpy(), split_seisbench=sb_split)
    summary = {'records': int(n), 'events': int(len(ev)), 'clusters': int(ev.cluster.nunique()),
               'window': 'samples p..p+500 at 100 Hz, E N Z, counts; phys_factor = 1/sensitivity (m/s)',
               'counts': counts, 'folds': {}}
    for f in range(n_folds):
        e = ev[ev.fold == f]
        summary['folds'][f] = {'events': int(len(e)), 'records': int(e.records.sum()),
                               'M>=4 events': int(e.m4.sum()), 'M>=5 events': int(e.m5.sum()),
                               'M>=6 events': int((e.mag >= 6).sum()), 'M>=4 records': int(e.records[e.m4 == 1].sum()),
                               'max_mag': float(e.mag.max())}
    big = ev.groupby('cluster').agg(events=('mag', 'size'), records=('records', 'sum'), max_mag=('mag', 'max'),
                                    m5=('m5', 'sum')).sort_values('records', ascending=False).head(12)
    summary['largest_clusters'] = big.reset_index().to_dict('records')
    summary['mag_types_records'] = {k: int(v) for k, v in frame.mag_type.value_counts().items()}
    summary['mag_types_M>=5_events'] = {k: int(v) for k, v in ev[ev.mag >= 5].mag_type.value_counts().items()}
    summary['families'] = {k: int(v) for k, v in frame.trace_channel.value_counts().items()}
    summary['usable_components'] = [int(x) for x in usable.sum(0)]
    summary['epi_km_pct'] = [float(x) for x in np.nanpercentile(epi, [5, 50, 95, 100])]
    (DEST / 'folds.json').write_text(json.dumps(summary, indent=1, default=str))
    log(json.dumps(summary, indent=1, default=str))


def gain_qc(min_records=10, max_dex=1.0):
    """Station-gain check, for analysis only (never a model input, nothing is dropped).

    log10 RMS of the 3 s physical prefix is fitted globally as a*M + b*log10(R) + c; a
    station/family/sensitivity epoch whose median residual exceeds max_dex (a factor 10)
    over >= min_records records most likely has wrong metadata. Written to gain_qc.npz
    (row-aligned) and summarized in folds.json.
    """
    m = np.load(DEST / 'meta.npz', allow_pickle=True)
    wave = np.load(DEST / 'wave16.npy', mmap_mode='r')
    scale = np.load(DEST / 'scale.npy')
    pf, n = m['phys_factor'], len(scale)
    A = np.empty(n)
    for a in range(0, n, 50000):
        x = wave[a:a + 50000, :, :3 * SR].astype(np.float32) * scale[a:a + 50000, None, None]
        x -= x.mean(-1, keepdims=True)
        x *= pf[a:a + 50000, :, None]
        A[a:a + 50000] = np.log10(np.sqrt((x ** 2).mean((1, 2))) + 1e-30)
    X = np.stack([m['mag'].astype(float), np.log10(np.maximum(m['hyp_km'].astype(float), 1.0)), np.ones(n)], 1)
    coef, *_ = np.linalg.lstsq(X, A, rcond=None)
    resid = A - X @ coef
    key = pd.Series(m['station'].astype(str)) + '|' + m['family'].astype(str) + '|' + \
        np.round(np.log10(m['gains'][:, 2]), 3).astype(str)
    g = pd.Series(resid).groupby(key.to_numpy())
    med, cnt = g.transform('median').to_numpy(), g.transform('size').to_numpy()
    suspect = (cnt >= min_records) & (np.abs(med) > max_dex)
    np.savez(DEST / 'gain_qc.npz', log_rms3=A.astype(np.float32), resid=resid.astype(np.float32),
             epoch_median=med.astype(np.float32), epoch_records=cnt.astype(np.int32), suspect=suspect, coef=coef)
    mag = m['mag']
    out = {'fit_a_b_c': [round(float(c), 4) for c in coef], 'resid_sd': round(float(resid.std()), 3),
           'epochs_tested': int((g.size() >= min_records).sum()),
           'suspect_epochs': int(key[suspect].nunique()), 'suspect_records': int(suspect.sum()),
           'suspect_records_M>=5': int((suspect & (mag >= 5)).sum()),
           'suspect_events_M>=5': int(len(np.unique(m['event'][suspect & (mag >= 5)])))}
    fj = json.loads((DEST / 'folds.json').read_text())
    fj['gain_qc'] = out
    (DEST / 'folds.json').write_text(json.dumps(fj, indent=1, default=str))
    log('gain qc', json.dumps(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--folds', type=int, default=5)
    ap.add_argument('--stop-after', choices=['select', 'waves'], default=None)
    ap.add_argument('--limit-buckets', type=int, default=0, help='debug: first N buckets only')
    ap.add_argument('--qc-only', action='store_true', help='rerun the station-gain check on an existing cache')
    args = ap.parse_args()
    if args.qc_only:
        gain_qc()
        return
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    if not (OUT / 'raw' / 'metadata.csv').exists():
        code, body = http_get(BASE + 'metadata.csv', timeout=1800)
        (OUT / 'raw' / 'metadata.csv').write_bytes(body)
    sel = OUT / 'selected.pkl'
    if sel.exists():
        frame, counts = pd.read_pickle(sel)
        log('loaded selection', len(frame))
    else:
        frame, counts = select(args)
        pd.to_pickle((frame, counts), sel)
    global DEST
    if args.limit_buckets:
        keep_b = sorted(frame.bnum.unique())[:args.limit_buckets]
        frame = frame[frame.bnum.isin(keep_b)].reset_index(drop=True)
        DEST = OUT / 'debug'
        DEST.mkdir(exist_ok=True)
    if args.stop_after == 'select':
        return
    scale, live = stream_waves(frame, args.workers)
    if args.stop_after == 'waves':
        return
    keep = (scale > 0) & live[:, 2]                       # finite, non-zero, vertical present
    counts['dropped_bad_waveform'] = int((~keep).sum())
    if not keep.all():
        compact(keep)
    frame, scale, live = frame[keep].reset_index(drop=True), scale[keep], live[keep]
    write_meta(frame, scale, live, counts, args.folds)
    gain_qc()
    for tmp in ('scale_partial.npy', 'live_partial.npy', 'done_buckets.txt'):
        (DEST / tmp).unlink(missing_ok=True)
    log('done')


if __name__ == '__main__':
    main()

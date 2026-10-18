"""Build the metadata package and leave-sequence-out folds for tail-risk work.

Outputs (under --out):
  meta.npz      per-record arrays aligned with the cache row order
                (train rows, then val rows, then test rows)
  events.csv    one row per event with its sequence cluster and CV fold
  folds.json    fold summary

Waveforms are NOT copied: training reads /data/Instance_windows_5s.hdf5
directly (1 s and 3 s inputs are exact prefixes of the 5 s cache; verified).

Catalogue source fields (origin time, epicentre, depth, distance) are stored
only for clustering and post-hoc analysis. They are never model inputs.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'research/2026-10-09/phase2'))
from instrument_inventory import Inventory, model_features  # noqa: E402

CACHE = '/data/Instance_windows_5s.hdf5'
CSV = {'train': REPO / 'train_full_metadata.csv', 'val': REPO / 'val_metadata.csv',
       'test': REPO / 'test_metadata.csv'}
STRING = ['source_id', 'trace_name', 'trace_start_time', 'station_network_code',
          'station_code', 'station_location_code', 'station_channels',
          'station_vs_30_detail', 'source_magnitude_type', 'source_origin_time']
NUMERIC = ['source_magnitude', 'trace_P_arrival_sample', 'trace_S_arrival_sample',
           'station_latitude_deg', 'station_longitude_deg', 'station_elevation_m',
           'station_vs_30_mps', 'source_latitude_deg', 'source_longitude_deg',
           'source_depth_km', 'path_hyp_distance_km', 'path_ep_distance_km',
           'path_backazimuth_deg']


def load_split(split):
    frame = pd.read_csv(CSV[split], usecols=STRING + NUMERIC,
                        dtype={c: str for c in STRING}, keep_default_na=False,
                        na_values={c: [''] for c in NUMERIC})
    with h5py.File(CACHE, 'r') as h5:
        targets = h5[split + '/targets'][:]
    if not np.array_equal(frame.source_magnitude.to_numpy(np.float32), targets):
        raise ValueError(f'{split}: metadata order differs from cache targets')
    frame['split'] = split
    return frame


def static_features(frame, inventory):
    feats, gains, usable, names = [], [], [], None
    for row in frame[['trace_name', 'trace_start_time', 'station_network_code', 'station_code',
                      'station_location_code', 'station_channels', 'station_vs_30_detail',
                      'station_latitude_deg', 'station_longitude_deg', 'station_elevation_m',
                      'station_vs_30_mps']].to_dict('records'):
        joined = inventory.join(row)
        allowed = model_features(joined)
        if names is None:
            names = list(allowed)
        feats.append(list(allowed.values()))
        ok = [joined['channels'][c]['status'] == 'matched' for c in 'ENZ']
        gains.append([joined['channels'][c]['sensitivity'] if o else np.nan
                      for c, o in zip('ENZ', ok)])
        usable.append(ok)
    return (np.asarray(feats, np.float32), np.asarray(gains, np.float64),
            np.asarray(usable, bool), names)


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def gk_window(mag):
    """Gardner & Knopoff (1974) aftershock windows: (km, days)."""
    km = 10 ** (0.1238 * mag + 0.983)
    days = np.where(mag >= 6.5, 10 ** (0.032 * mag + 2.7389), 10 ** (0.5409 * mag - 0.547))
    return km, days


def sequence_clusters(events, foreshock_fraction):
    """Mainshock-window declustering (no chaining between small events).

    Events are visited in descending magnitude. An unassigned event becomes a
    sequence root and claims every unassigned event inside its GK window
    (forward window T, backward window foreshock_fraction*T). Remaining
    background events are singletons. This keeps every aftershock sequence of a
    large event inside one CV fold without chaining 14 years of background
    seismicity into a single group.
    """
    t = events.t.to_numpy()
    lat, lon, mag = (events[c].to_numpy() for c in ('lat', 'lon', 'mag'))
    by_time = np.argsort(t)
    t_sorted = t[by_time]
    km, days = gk_window(mag)
    cluster = np.full(len(t), -1, np.int64)
    next_id = 0
    for root in np.lexsort((t, -mag)):
        if cluster[root] >= 0:
            continue
        lo = np.searchsorted(t_sorted, t[root] - foreshock_fraction * days[root] * 86400.0, 'left')
        hi = np.searchsorted(t_sorted, t[root] + days[root] * 86400.0, 'right')
        cand = by_time[lo:hi]
        cand = cand[cluster[cand] < 0]
        near = cand[haversine_km(lat[root], lon[root], lat[cand], lon[cand]) <= km[root]]
        cluster[near] = next_id
        cluster[root] = next_id
        next_id += 1
    return cluster


def assign_folds(events, n_folds):
    """Greedy balance of M>=4 events, M>=5 events and record counts per fold."""
    g = events.groupby('cluster').agg(n4=('m4', 'sum'), n5=('m5', 'sum'),
                                      records=('records', 'sum')).reset_index()
    g = g.sort_values(['n5', 'n4', 'records'], ascending=False)
    load = np.zeros((n_folds, 3))
    total = g[['n5', 'n4', 'records']].sum().to_numpy(float) + 1e-9
    fold_of = {}
    for row in g.itertuples(index=False):
        vec = np.array([row.n5, row.n4, row.records], float) / total
        cost = [(load[f] + vec).max() + 1e-3 * (load[f] + vec).sum() for f in range(n_folds)]
        f = int(np.argmin(cost))
        load[f] += vec
        fold_of[row.cluster] = f
    return events.cluster.map(fold_of).to_numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/mnt/eew-research/runs/tailwork')
    ap.add_argument('--foreshock-fraction', type=float, default=0.25)
    ap.add_argument('--folds', type=int, default=5)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    frame = pd.concat([load_split(s) for s in ('train', 'val', 'test')], ignore_index=True)
    print('metadata', len(frame), f'{time.time()-t0:.0f}s', flush=True)
    inventory = Inventory.from_archive('/mnt/eew-research/instance/responses.tgz')
    feats, gains, usable, names = static_features(frame, inventory)
    print('static features', feats.shape, 'complete', usable.all(1).mean(), f'{time.time()-t0:.0f}s', flush=True)

    origin = pd.to_datetime(frame.source_origin_time, utc=True, format='ISO8601')
    frame['t'] = (origin - pd.Timestamp('1970-01-01', tz='UTC')).dt.total_seconds()
    ev = frame.groupby('source_id', sort=False).agg(
        t=('t', 'first'), lat=('source_latitude_deg', 'first'), lon=('source_longitude_deg', 'first'),
        depth=('source_depth_km', 'first'), mag=('source_magnitude', 'first'),
        mag_type=('source_magnitude_type', 'first'), split=('split', 'first'),
        records=('trace_name', 'size')).reset_index()
    if frame.groupby('source_id').source_magnitude.nunique().max() != 1:
        raise ValueError('conflicting event magnitudes')
    ev['m4'] = (ev.mag >= 4).astype(int)
    ev['m5'] = (ev.mag >= 5).astype(int)
    ev['cluster'] = sequence_clusters(ev, args.foreshock_fraction)
    ev['fold'] = assign_folds(ev, args.folds)
    ev.to_csv(out / 'events.csv', index=False)

    event_index = {sid: i for i, sid in enumerate(ev.source_id)}
    eidx = frame.source_id.map(event_index).to_numpy(np.int64)
    station_key = (frame.station_network_code + '.' + frame.station_code).to_numpy()
    stations, sidx = np.unique(station_key, return_inverse=True)
    fam = frame.station_channels.to_numpy()
    families, fidx = np.unique(fam, return_inverse=True)
    split_code = frame.split.map({'train': 0, 'val': 1, 'test': 2}).to_numpy(np.int8)
    np.savez(out / 'meta.npz',
             split=split_code, event=eidx, station=sidx.astype(np.int32),
             stations=stations, family=fidx.astype(np.int8), families=families,
             mag=frame.source_magnitude.to_numpy(np.float32),
             mag_type=frame.source_magnitude_type.to_numpy(),
             fold=ev.fold.to_numpy()[eidx].astype(np.int8),
             cluster=ev.cluster.to_numpy()[eidx].astype(np.int64),
             static=feats, static_names=np.array(names), gains=gains, usable=usable,
             sta_lat=frame.station_latitude_deg.to_numpy(np.float32),
             sta_lon=frame.station_longitude_deg.to_numpy(np.float32),
             hyp_km=frame.path_hyp_distance_km.to_numpy(np.float32),
             epi_km=frame.path_ep_distance_km.to_numpy(np.float32),
             depth_km=frame.source_depth_km.to_numpy(np.float32),
             baz=frame.path_backazimuth_deg.to_numpy(np.float32),
             p_sample=frame.trace_P_arrival_sample.to_numpy(np.float32),
             s_sample=frame.trace_S_arrival_sample.to_numpy(np.float32),
             origin_t=frame.t.to_numpy(np.float64),
             trace_name=frame.trace_name.to_numpy())

    summary = {'records': int(len(frame)), 'events': int(len(ev)), 'clusters': int(ev.cluster.nunique()),
               'clustering': 'Gardner-Knopoff mainshock windows',
               'foreshock_fraction': args.foreshock_fraction, 'folds': {}}
    big = ev.groupby('cluster').agg(events=('mag', 'size'), records=('records', 'sum'),
                                    max_mag=('mag', 'max'), m4=('m4', 'sum'))
    big = big.sort_values('records', ascending=False).head(12)
    summary['largest_clusters'] = big.reset_index().to_dict('records')
    for f in range(args.folds):
        e = ev[ev.fold == f]
        summary['folds'][f] = {'events': int(len(e)), 'records': int(e.records.sum()),
                               'M>=4 events': int(e.m4.sum()), 'M>=5 events': int(e.m5.sum()),
                               'M>=4 records': int(e.records[e.m4 == 1].sum()),
                               'max_mag': float(e.mag.max())}
    (out / 'folds.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f'done {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()

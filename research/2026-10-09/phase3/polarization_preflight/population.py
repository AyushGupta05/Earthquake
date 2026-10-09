"""Fixed identity-only partitions and metadata sampling; no waveform/target use."""
import hashlib
import math
from collections import defaultdict


def digest(salt, identifier):
    return hashlib.sha256((salt + '\0' + str(identifier)).encode('utf-8')).digest()


def bucket(salt, identifier):
    return int.from_bytes(digest(salt, identifier)[:8], 'big') % 10


def station_groups(stations, epochs):
    """Union all aliases within100m horizontal/50m vertical in any known epoch.

    Epoch coordinates are used only for splitting. This conservative connected
    component rule also groups stations that moved through the same site.
    """
    stations = sorted(set(stations))
    parent = {s: s for s in stations}

    def root(s):
        while parent[s] != s:
            parent[s] = parent[parent[s]]
            s = parent[s]
        return s

    locations = defaultdict(set)
    for epoch in epochs:
        s = epoch.network + '.' + epoch.station
        values = (epoch.latitude_deg, epoch.longitude_deg, epoch.elevation_m)
        if s not in parent or any(v is None or not math.isfinite(v) for v in values):
            continue
        lat, lon, elevation = values
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            locations[s].add((lat, lon, elevation))
    grid = defaultdict(list)
    earth_radius = 6371000.
    for s in stations:
        for lat, lon, elevation in sorted(locations[s]):
            lat, lon = math.radians(lat), math.radians(lon)
            xyz = (earth_radius*math.cos(lat)*math.cos(lon),
                   earth_radius*math.cos(lat)*math.sin(lon), earth_radius*math.sin(lat))
            cell = tuple(math.floor(v/100) for v in xyz)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for other, a, b, h in grid[(cell[0]+dx, cell[1]+dy, cell[2]+dz)]:
                            if abs(elevation-h) > 50:
                                continue
                            hav = math.sin((lat-a)/2)**2 + math.cos(lat)*math.cos(a)*math.sin((lon-b)/2)**2
                            distance = 2*earth_radius*math.asin(min(1., math.sqrt(hav)))
                            if distance <= 100:
                                first, second = sorted((root(s), root(other)))
                                parent[second] = first
            grid[cell].append((s, lat, lon, elevation))
    return ({s: root(s) for s in stations}, [s for s in stations if not locations[s]])


def select(records, groups, fit_event_cap=15000, eval_event_cap=10000, record_cap=4):
    """records already passed metadata eligibility; none have waveform checks.

    Returns sampled records with original source indices and unmodified sampling
    weights. Never replace an invalid waveform after this operation.
    """
    if min(fit_event_cap, eval_event_cap, record_cap) <= 0:
        raise ValueError('Sample caps must be positive')
    per_subset = {name: defaultdict(list) for name in ('fit', 'eval_seen', 'eval_held')}
    traces, indices = set(), set()
    excluded = 0
    for row in records:
        trace, index = row['trace_name'], row['source_row_index']
        if trace in traces or index in indices:
            raise ValueError('Duplicate TRAIN trace identity or row index')
        traces.add(trace)
        indices.add(index)
        group = groups[row['station_id']]
        event_fold = bucket('polarization-event-v1', row['source_id'])
        station_fold = bucket('polarization-station-v1', group)
        if event_fold >= 2 and station_fold < 2:
            excluded += 1
            continue
        subset = 'fit' if event_fold >= 2 else ('eval_seen' if station_fold >= 2 else 'eval_held')
        copy = dict(row, station_group=group, event_bucket=event_fold, station_bucket=station_fold,
                    subset=subset)
        per_subset[subset][row['source_id']].append(copy)
    selected, audit = [], {'fitting_events_at_held_stations_excluded': excluded, 'subsets': {}}
    for subset, events in per_subset.items():
        salt = 'polarization-fit-sample-v1' + ('' if subset == 'fit' else 'eval')
        cap = fit_event_cap if subset == 'fit' else eval_event_cap
        event_ids = sorted(events, key=lambda s: (digest(salt, s), s))[:cap]
        count = 0
        for event in event_ids:
            rows = sorted(events[event], key=lambda r: (digest('polarization-record-v1', r['trace_name']), r['trace_name']))
            sample = rows[:record_cap]
            for row in sample:
                selected.append(dict(row, n_metadata_eligible=len(rows), n_sampled=len(sample),
                                     sampling_weight=len(rows)/len(sample)))
            count += len(sample)
        audit['subsets'][subset] = {'metadata_events': len(events), 'selected_events': len(event_ids),
                                    'dropped_events': len(events)-len(event_ids),
                                    'metadata_records': sum(map(len, events.values())), 'sampled_records': count}
    selected.sort(key=lambda r: r['source_row_index'])
    fit = [r for r in selected if r['subset'] == 'fit']
    evaluation = [r for r in selected if r['subset'] != 'fit']
    assert not ({r['source_id'] for r in fit} & {r['source_id'] for r in evaluation})
    assert not ({r['station_group'] for r in fit} &
                {r['station_group'] for r in selected if r['subset'] == 'eval_held'})
    return selected, audit

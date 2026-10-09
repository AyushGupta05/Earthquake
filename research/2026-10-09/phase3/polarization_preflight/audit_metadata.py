"""Read-only TRAIN metadata/response/shape feasibility audit; no waveform values."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
from collections import Counter

ROOT = Path('/home/ec2-user/Earthquake')
METADATA = ROOT / 'train_full_metadata.csv'
INVENTORY = Path('/mnt/eew-research/instance/responses.tgz')
SOURCE = ROOT / 'research/2026-10-09/phase2/instrument_inventory.py'
EXPECTED_METADATA = '168b5d861804e9707f68125dc8bc9453c8e0a47a48ef4055a7920c6526f1535d'
EXPECTED_INVENTORY = '71eccc6304afad15e9c45534ca374b4b4f974c9f93ccfc0f2683616ee6421ef2'
EXPECTED_SOURCE = '9a942c4773e5c18264aa2db432ba4669f965004aeb9a1f67f25a67d6c812c227'
PROTOCOL_SHA256 = '686e427bce3e587e17985346a93cf59a5e685517b1c810e83c20d3bae2edda29'
COLUMNS = ['trace_name', 'trace_start_time', 'trace_P_arrival_sample', 'trace_dt_s', 'trace_npts',
           'station_network_code', 'station_code', 'station_location_code', 'station_channels',
           'source_depth_km', 'path_ep_distance_km', 'path_hyp_distance_km']


def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def canonical_orientation(component, channel):
    dip = finite(channel.get('dip_deg'))
    azimuth = finite(channel.get('azimuth_deg'))
    if dip is None:
        return False
    if component == 'Z':
        return abs(dip + 90) <= 1
    expected = 90 if component == 'E' else 0
    return (azimuth is not None and abs(dip) <= 1
            and abs((azimuth - expected + 180) % 360 - 180) <= 1)


def metadata_window(row):
    p, dt, n = [finite(row[k]) for k in ('trace_P_arrival_sample', 'trace_dt_s', 'trace_npts')]
    return (p is not None and p.is_integer() and p >= 200 and dt is not None
            and abs(dt - .01) <= 1e-10 and n is not None and n.is_integer()
            and n >= p + 500)


def unique_epoch_cover(epochs, start, end):
    """Inclusive boundaries: even a touching/invalid competing epoch is ambiguous."""
    matches = [e for e in epochs if e.end >= e.start and e.start <= end and e.end >= start]
    return len(matches) == 1 and matches[0].start <= start and matches[0].end >= end


def window_responses(row, inventory, module):
    """Use properties of the uniquely covering epoch, never another trace-start epoch."""
    result = {}
    try:
        timestamp = module.utc_seconds(row['trace_start_time'])
    except (ValueError, TypeError, OverflowError):
        timestamp = None
    window = metadata_window(row) and timestamp is not None
    location, _ = module.location_code(row)
    for component in 'ENZ':
        key = (row['station_network_code'], row['station_code'], location,
               row['station_channels'] + component)
        epochs = inventory.index.get(key, [])
        epoch = None
        if window:
            p = float(row['trace_P_arrival_sample'])
            start, end = timestamp + (p - 200)*.01, timestamp + (p + 500)*.01
            if unique_epoch_cover(epochs, start, end):
                epoch = next(e for e in epochs if e.end >= e.start and e.start <= start and e.end >= end)
        item = {'status': 'no_unique_cover', 'has_key': bool(epochs)}
        if epoch is not None:
            item.update(status='matched' if epoch.usable else 'invalid_response',
                        input_units=module.normalize_units(epoch.input_units),
                        sensitivity=epoch.sensitivity, azimuth_deg=epoch.azimuth_deg,
                        dip_deg=epoch.dip_deg)
        result[component] = item
    return result


def main():
    # Imports stay inside main so helper tests never load real metadata or HDF5.
    import pandas as pd
    import h5py
    started = time.monotonic()
    hashes = {str(p): sha(p) for p in (METADATA, INVENTORY, SOURCE)}
    if list(hashes.values()) != [EXPECTED_METADATA, EXPECTED_INVENTORY, EXPECTED_SOURCE]:
        raise ValueError('Pinned metadata, inventory or source changed')
    spec = importlib.util.spec_from_file_location('polarization_inventory', SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    inventory = module.Inventory.from_archive(INVENTORY)
    counts, units, orientations, reasons = Counter(), Counter(), Counter(), Counter()
    examples = []
    for chunk in pd.read_csv(METADATA, usecols=COLUMNS, dtype=str, keep_default_na=False, chunksize=20000):
        for row in chunk.to_dict('records'):
            counts['train_rows'] += 1
            if len(examples) < 8:
                examples.append(row['trace_name'])
            window = metadata_window(row)
            counts['metadata_window_2s_pre_5s_post'] += int(window)
            for target in ('source_depth_km', 'path_ep_distance_km', 'path_hyp_distance_km'):
                value = finite(row[target])
                counts[target + '_finite_nonnegative'] += int(value is not None and value >= 0)
            response = window_responses(row, inventory, module)
            channels = [response[c] for c in 'ENZ']
            usable = all(c['status'] == 'matched' for c in channels)
            counts['response_all_matched'] += int(usable)
            unit_set = {c.get('input_units') for c in channels}
            common_unit = usable and len(unit_set) == 1 and next(iter(unit_set)) in ('m/s', 'm/s^2')
            units['/'.join(str(c.get('input_units', 'missing')) for c in channels)] += 1
            orientation = all(canonical_orientation(c, response[c]) for c in 'ENZ')
            orientations[str(orientation)] += 1
            boundary = window and any(c['has_key'] and c['status'] == 'no_unique_cover' for c in channels)
            valid = window and common_unit and orientation and not boundary
            counts['metadata_response_orientation_eligible'] += int(valid)
            for name, fail in [('window', not window), ('response', not usable),
                               ('units', not common_unit), ('orientation', not orientation), ('epoch_boundary', boundary)]:
                reasons[name] += int(fail)
    shapes = {}
    with h5py.File('/data/Instance_events_counts.hdf5', 'r') as raw:
        format_fields = {key: str(raw['data_format'][key][()]) for key in raw['data_format']}
        for name in examples:
            ds = raw['data'][name]
            shapes[name] = {'shape': list(ds.shape), 'dtype': str(ds.dtype)}
    cache_shapes = {}
    # Existing audit.json names the historical 3s file "full", not "3s".
    cache_files = {1: 'Instance_windows_1s.hdf5', 3: 'Instance_windows_full.hdf5',
                   5: 'Instance_windows_5s.hdf5'}
    for seconds, filename in cache_files.items():
        with h5py.File(Path('/data') / filename, 'r') as cache:
            ds = cache['train/waveforms']
            cache_shapes[str(seconds)] = {'path': str(Path('/data') / filename),
                                         'shape': list(ds.shape), 'dtype': str(ds.dtype)}
    print(json.dumps({'scope': 'TRAIN metadata and TRAIN shapes only; no waveform values, no magnitude column, no VAL/TEST',
                      'protocol_sha256': PROTOCOL_SHA256, 'hashes': hashes, 'counts': counts,
                      'unit_patterns': units, 'orientation_validity': orientations, 'failure_reasons_nonexclusive': reasons,
                      'train_shape_examples': shapes, 'train_cache_shapes': cache_shapes, 'data_format': format_fields,
                      'limits': 'Eligibility counts are metadata-only; waveform finiteness/variance and exhaustive HDF presence are untested',
                      'seconds': time.monotonic() - started}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()

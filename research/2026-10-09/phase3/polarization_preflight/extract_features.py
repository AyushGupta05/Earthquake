"""TRAIN-only CPU extraction for protocol v2. Does nothing without --execute.

This command produces descriptors/identities, never fits a model or reads a VAL
or TEST cache. Importable helpers operate on supplied synthetic fixtures.
"""
import argparse
from collections import Counter
import csv
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time

for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_key, '2')
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import numpy as np
from audit_metadata import (METADATA, INVENTORY, SOURCE, EXPECTED_METADATA,
                            EXPECTED_INVENTORY, EXPECTED_SOURCE, sha, finite,
                            metadata_window, canonical_orientation, window_responses)
from features import describe, InvalidObservation, INVALID_CODES, FEATURE_NAMES, STATIC_NAMES, masks
from population import station_groups, select

PROTOCOL_SHA256 = 'a9b12a88be3a46e96d0f3f208f64b7728d1a17bb132e146887694e40288a448b'
RAW = Path('/data/Instance_events_counts.hdf5')
TARGET_NAMES = ['source_magnitude', 'path_hyp_distance_km', 'source_depth_km']
COLUMNS = ['source_id', 'trace_name', 'trace_start_time', 'trace_P_arrival_sample',
           'trace_dt_s', 'trace_npts', 'station_network_code', 'station_code',
           'station_location_code', 'station_channels', 'station_elevation_m',
           'station_vs_30_mps'] + TARGET_NAMES
ALL_INVALID_CODES = dict(INVALID_CODES, missing_trace=128, trace_shape_mismatch=256)
CACHE_BYTES = 128*1024*1024


def metadata_rows(path):
    with open(path, newline='') as stream:
        reader = csv.DictReader(stream)
        if not set(COLUMNS).issubset(reader.fieldnames or []):
            raise ValueError('Required TRAIN columns missing')
        for index, raw in enumerate(reader):
            # A strict allowlist excludes all full-record SNR, peaks, S picks,
            # source location/type and other catalog metadata from this code.
            row = {key: raw[key] for key in COLUMNS}
            row['source_row_index'] = index
            yield row


def metadata_reason(row, inventory, module):
    if not row['source_id'].strip() or not row['trace_name'].strip():
        return 'identity', None
    if any(not row[k].strip() for k in ('station_network_code', 'station_code', 'station_channels')):
        return 'identity', None
    if not metadata_window(row):
        return 'window', None
    target = [finite(row[k]) for k in TARGET_NAMES]
    if any(v is None for v in target) or any(v < 0 for v in target[1:]):
        return 'target', None
    response = window_responses(row, inventory, module)
    if not all(c['status'] == 'matched' for c in response.values()):
        return 'response', None
    units = {c['input_units'] for c in response.values()}
    if len(units) != 1 or next(iter(units)) not in ('m/s', 'm/s^2'):
        return 'units', None
    if not all(canonical_orientation(c, response[c]) for c in 'ENZ'):
        return 'orientation', None
    return None, response


def static_and_response(row, inventory, module):
    reason, response = metadata_reason(row, inventory, module)
    if reason:
        raise ValueError('Previously eligible metadata changed: '+reason)
    p = int(float(row['trace_P_arrival_sample']))
    start = module.utc_seconds(row['trace_start_time']) + (p-200)*.01
    # Inventory.join intentionally restricts families in its original workflow.
    # This protocol admits any valid ENZ family and has a family_unknown slot,
    # so use the already validated covering epochs with the same numeric schema.
    joined = {'channel_family':row['station_channels'].strip(), 'channels':{},
              'station_elevation_m':module.numeric(row.get('station_elevation_m')),
              'station_vs_30_mps':module.numeric(row.get('station_vs_30_mps'))}
    if joined['station_vs_30_mps'] is not None and joined['station_vs_30_mps'] <= 0:
        joined['station_vs_30_mps'] = None
    location, _ = module.location_code(row)
    for c in 'ENZ':
        key = (row['station_network_code'], row['station_code'], location, row['station_channels']+c)
        status, epoch, _ = inventory.lookup(key, start)
        expected = response[c]
        if (status != 'matched' or epoch.sensitivity != expected['sensitivity']
                or module.normalize_units(epoch.input_units) != expected['input_units']):
            raise ValueError('Static features do not use the covering response epoch')
        joined['channels'][c] = {'status':status, 'log10_sensitivity':math.log10(epoch.sensitivity),
                                 'input_units':module.normalize_units(epoch.input_units),
                                 'sensitivity_frequency_hz':epoch.sensitivity_frequency_hz,
                                 'native_sample_rate_hz':epoch.sample_rate_hz}
    static = module.model_features(joined)
    if list(static) != STATIC_NAMES:
        raise ValueError('Static feature schema changed')
    return (np.array(list(static.values()), dtype=np.float64),
            np.array([response[c]['sensitivity'] for c in 'ENZ']),
            [response[c]['input_units'] for c in 'ENZ'])


def configure_cache(raw):
    config = raw.id.get_mdc_config()
    config.initial_size = CACHE_BYTES
    config.max_size = CACHE_BYTES
    config.min_size = CACHE_BYTES
    config.set_initial_size = 1
    raw.id.set_mdc_config(config)


def verify_format(raw):
    expected = {'component_order': 'ENZ', 'dimension_order': 'CW', 'unit': 'counts',
                'instrument_response': 'not restituted'}
    actual = {}
    for key, value in expected.items():
        field = raw['data_format'][key][()]
        actual[key] = field.decode() if isinstance(field, bytes) else str(field)
        if actual[key] != value:
            raise ValueError('Unexpected raw format: '+key)
    return actual


def extract_record(raw, row, gain, units, static):
    """No other HDF key is touched. All horizons share sampled identity, not validity."""
    features = np.full((3, 127), np.nan, dtype=np.float64)
    invalid = np.zeros(3, dtype=np.uint16)
    degenerate = np.zeros(3, dtype=bool)
    name = row['trace_name']
    # An INSTANCE trace is one literal dataset name, never an HDF path.
    if '/' in name or name in ('.', '..'):
        raise ValueError('Invalid trace identity')
    try:
        dataset = raw['data'][name]
    except KeyError:
        invalid[:] = ALL_INVALID_CODES['missing_trace']
        return features, invalid, degenerate
    npts = int(float(row['trace_npts']))
    if (len(dataset.shape) != 2 or dataset.shape[0] != 3 or dataset.shape[1] != npts
            or dataset.dtype.kind not in 'ifu'):
        invalid[:] = ALL_INVALID_CODES['trace_shape_mismatch']
        return features, invalid, degenerate
    p = int(float(row['trace_P_arrival_sample']))
    segment = dataset[:, p-200:p+500]
    for index, seconds in enumerate((1, 3, 5)):
        try:
            features[index], degenerate[index] = describe(segment, gain, units, static, seconds)
        except InvalidObservation as error:
            invalid[index] = error.code
    return features, invalid, degenerate


def raw_stat(path):
    stat = path.stat()
    return {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'inode': stat.st_ino}


def load_inventory(source, archive):
    spec = importlib.util.spec_from_file_location('polarization_inventory', source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module, module.Inventory.from_archive(archive)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Read real TRAIN metadata/waveforms; parent authorization required')
    args = parser.parse_args()
    plan = {'scope': 'TRAIN only; extraction only; no fitting', 'protocol_sha256': PROTOCOL_SHA256,
            'metadata': str(METADATA), 'inventory': str(INVENTORY), 'raw': str(RAW),
            'output': str(args.output), 'execute': args.execute}
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return
    # No configurable data-path override or skip-verification flag in production.
    here = Path(__file__).resolve().parent
    pinned = {METADATA: EXPECTED_METADATA, INVENTORY: EXPECTED_INVENTORY,
              SOURCE: EXPECTED_SOURCE, here/'protocol.md': PROTOCOL_SHA256}
    for path, expected in pinned.items():
        if sha(path) != expected:
            raise ValueError('Pinned input changed: '+str(path))
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    code = {name: sha(here/name) for name in ('extract_features.py', 'features.py', 'population.py', 'audit_metadata.py')}
    manifest = dict(plan, status='started', code_sha256=code, pinned_sha256={str(k):v for k,v in pinned.items()},
                    raw_stat_before=raw_stat(RAW), raw_full_file_hash=None,
                    raw_hash_limitation='Huge raw source is identified by path/stat/format; extracted descriptor outputs are hashed, raw waveform bytes are not',
                    metadata_cache_bytes=CACHE_BYTES, target_names=TARGET_NAMES, feature_names=FEATURE_NAMES,
                    invalid_codes=ALL_INVALID_CODES)
    manifest_path = args.output/'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    module, inventory = load_inventory(SOURCE, INVENTORY)
    eligible, reasons, stations = [], Counter(), set()
    total = 0
    for row in metadata_rows(METADATA):
        total += 1
        station = row['station_network_code']+'.'+row['station_code']
        stations.add(station)
        reason, _ = metadata_reason(row, inventory, module)
        if reason:
            reasons[reason] += 1
            continue
        eligible.append({key: row[key] for key in ('source_row_index', 'source_id', 'trace_name')})
        eligible[-1]['station_id'] = station
    groups, missing_coords = station_groups(stations, inventory.epochs)
    selected, sampling = select(eligible, groups)
    del eligible
    if not selected:
        raise ValueError('No metadata-eligible sampled rows')
    selection = {row['source_row_index']: row for row in selected}
    materialized = []
    for row in metadata_rows(METADATA):
        if row['source_row_index'] in selection:
            original = selection[row['source_row_index']]
            if any(original[key] != row[key] for key in ('trace_name', 'source_id')):
                raise ValueError('Metadata identity changed during sampling')
            materialized.append(dict(row, **{k:v for k,v in original.items() if k not in row}))
    if len(materialized) != len(selected):
        raise ValueError('Selected metadata rows disappeared')
    with (args.output/'selected_metadata.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)
    (args.output/'station_groups.json').write_text(json.dumps({'groups': groups, 'missing_coordinates': missing_coords}, indent=2)+'\n')
    n = len(materialized)
    values = np.full((n, 3, 127), np.nan, dtype=np.float64)
    invalid = np.zeros((n, 3), dtype=np.uint16)
    degenerate = np.zeros((n, 3), dtype=bool)
    sensitivities = np.zeros((n, 3))
    units = []
    # h5py is intentionally absent from all import-time and dry-run paths.
    import h5py
    with h5py.File(RAW, 'r') as raw:
        configure_cache(raw)
        manifest['data_format'] = verify_format(raw)
        for i, row in enumerate(materialized):
            static, gain, unit = static_and_response(row, inventory, module)
            values[i], invalid[i], degenerate[i] = extract_record(raw, row, gain, unit, static)
            sensitivities[i] = gain
            units.append(unit[0])
            if (i+1) % 2000 == 0:
                print(json.dumps({'extracted':i+1, 'sampled':n, 'seconds':time.monotonic()-started}), flush=True)
    arrays = {'features': values, 'valid': invalid == 0, 'invalid_codes': invalid,
              'principal_degenerate': degenerate, 'sensitivities':sensitivities, 'native_units':np.array(units),
              'targets':np.array([[float(row[k]) for k in TARGET_NAMES] for row in materialized]),
              'sampling_weight':np.array([row['sampling_weight'] for row in materialized]),
              'source_row_index':np.array([row['source_row_index'] for row in materialized], dtype=np.int64),
              'feature_names':np.array(FEATURE_NAMES), 'target_names':np.array(TARGET_NAMES), 'deadlines':np.array([1,3,5])}
    for key in ('trace_name','source_id','station_id','station_group','subset','station_channels'):
        arrays[key] = np.array([row[key] for row in materialized])
    for key in ('event_bucket','station_bucket','n_metadata_eligible','n_sampled'):
        arrays[key] = np.array([row[key] for row in materialized], dtype=np.int64)
    arrays.update({'mask_'+k:v for k,v in masks().items()})
    np.savez(args.output/'features.npz', **arrays)
    if raw_stat(RAW) != manifest['raw_stat_before']:
        raise ValueError('Raw source stat changed during extraction')
    for path, expected in pinned.items():
        if sha(path) != expected:
            raise ValueError('Pinned input changed during extraction: '+str(path))
    for name, expected in code.items():
        if sha(here/name) != expected:
            raise ValueError('Extraction code changed during execution')
    quality = {}
    for subset in ('fit','eval_seen','eval_held'):
        indices = np.array([r['subset'] == subset for r in materialized])
        quality[subset] = {}
        for j, seconds in enumerate((1,3,5)):
            valid = indices & (invalid[:,j] == 0)
            events = set(arrays['source_id'][indices])
            quality[subset][str(seconds)] = {'sampled':int(indices.sum()), 'valid':int(valid.sum()),
                'valid_fraction':float(valid.sum()/indices.sum()) if indices.any() else None,
                'valid_events':len(set(arrays['source_id'][valid])), 'lost_events':len(events-set(arrays['source_id'][valid])),
                'invalid_reason_counts':{name:int((indices & (invalid[:,j] == code)).sum()) for name,code in ALL_INVALID_CODES.items()}}
    manifest.update(status='complete', seconds=time.monotonic()-started, metadata_rows=total,
                    metadata_ineligible_reasons=dict(reasons), sampling=sampling, quality=quality,
                    outputs_sha256={name:sha(args.output/name) for name in ('features.npz','selected_metadata.csv','station_groups.json')},
                    limitations=['Sampling weights do not correct waveform-quality nonresponse',
                                 'Metadata coverage is fixed; waveform validity differs by horizon',
                                 'Manual picks and released full-record preprocessing are not raw-stream causal',
                                 'No model, fitted normalization, likelihood or benchmark result produced'])
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'status':'complete','seconds':manifest['seconds'],'quality':quality}), flush=True)


if __name__ == '__main__':
    main()

"""Frozen source/data identity and split guards; dry checks never open artifacts."""
import csv
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import sys

from baseline_guards import (SOURCES, verify, sha, read_json, validate_plan, validate_completion,
                             validate_splits, epoch_sequence, ids_sha)

PROTOCOL_SHA = '8d4e2e3ed43c072356d539bb822316ed8f8d2cee3213ff8a02ef419a6f33777b'
OWN_FILES = ('baseline_guards.py', 'clock_contract.py', 'clock_rng.py', 'clock_training.py',
             'clock_metrics.py', 'clock_replay.py', 'clock_synthetic.py', 'run_clock_control.py', 'protocol.json')
CONFIG_EXTRA = {'batch_size': 64, 'workers': 0, 'max_stations': 25, 'station_drop': 0.,
                'station_blinding': 'author', 'event_label_smoothing': True,
                'magnitude_resampling': 2, 'seed': 20261009}


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def preflight(args):
    if not 1 <= args.max_seconds <= 39600:
        raise ValueError('Grid timeout must be1..39600 seconds')
    if getattr(args, 'initial_replay', None) and args.max_seconds > 600:
        raise ValueError('Initial replay must be bounded to at most600 seconds')
    if getattr(args, 'synthetic_runtime', False) and args.max_seconds > 120:
        raise ValueError('Synthetic CUDA proof must be bounded to at most120 seconds')
    if getattr(args, 'synthetic_runtime', False) and getattr(args, 'initial_replay', None):
        raise ValueError('Choose one prefit proof mode')
    verify(args.plan, args.plan_sha256)
    plan = read_json(args.plan); validate_plan(plan)
    verify(Path(__file__).with_name('protocol.json'), PROTOCOL_SHA)
    protocol = read_json(Path(__file__).with_name('protocol.json'))
    if {k: v['sha256'] for k, v in plan['artifacts'].items()} != protocol['artifact_sha256']:
        raise ValueError('Only the frozen selected97 baseline/data identities are accepted')
    verify(args.source_manifest, args.source_manifest_sha256)
    sources = read_json(args.source_manifest)
    if set(sources) != {'schema', 'own', 'dependencies', 'protocol_sha256'} or sources['schema'] != 'chile-clock-sources-v1':
        raise ValueError('Wrong reviewed-source manifest schema')
    if set(sources['own']) != set(OWN_FILES) or sources['dependencies'] != SOURCES or sources['protocol_sha256'] != PROTOCOL_SHA:
        raise ValueError('Reviewed source allowlist changed')
    for name, digest in sources['own'].items():verify(Path(__file__).with_name(name), digest)
    for name, digest in SOURCES.items():verify(args.source_dir / name, digest)
    return plan, protocol, sources


def import_sources(directory):
    directory = Path(directory).resolve()
    sys.path.insert(0, str(directory))
    imported = {}
    for name in ('team_lm', 'training_artifacts', 'train_team_lm'):
        module = importlib.import_module(name)
        if Path(module.__file__).resolve() != directory / (name + '.py'):
            raise ValueError('Dependency import escaped pinned source directory')
        imported[name] = module
    return imported['team_lm'], imported['train_team_lm']


def validate_baseline(run, checkpoint, plan, dataset_manifest):
    if set(checkpoint) != {'model', 'config', 'selected_epoch'}:
        raise ValueError('Only final selected model.pth schema accepted')
    validate_completion(run, checkpoint['config'], checkpoint['selected_epoch'], plan, dataset_manifest)
    if checkpoint['selected_epoch'] != 97:
        raise ValueError('Frozen selected97 starting point changed')
    for field, value in CONFIG_EXTRA.items():
        if run.get(field) != value or checkpoint['config'].get(field) != value:
            raise ValueError('Original event config changed: ' + field)
    return run


def metadata_rows(path, splits, dataset_manifest, sidecar, *, requested, all_fits_complete=False):
    """Identity-check all rows, parse outcomes only for the currently allowed split."""
    if requested not in ('fit', 'calibration', 'dev') or (requested != 'fit' and not all_fits_complete):
        raise ValueError('Held-out outcomes require all four completed fits')
    train_end, dev_end = dataset_manifest['author_split_boundaries']
    lookup = {row: event for block in splits.values() for row, event in zip(block['source_rows'], block['event_ids'])}
    allowed = set(splits[requested]['source_rows']); rows = []; ids = {'train': [], 'dev': []}
    with Path(path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ['EVENT', 'MA', 'TIME', 'source_row_index', 'benchmark_split']:
            raise ValueError('Metadata schema changed')
        count = 0
        for index, row in enumerate(reader):
            count += 1; split = 'train' if index < train_end else 'dev'
            if int(row['source_row_index']) != index or row['benchmark_split'] != split or lookup.get(index) != row['EVENT']:
                raise ValueError('Metadata identity/split order mismatch')
            ids[split].append(row['EVENT'])
            if index in allowed:
                y, timestamp = float(row['MA']), float(row['TIME'])
                if not math.isfinite(y) or not math.isfinite(timestamp):raise ValueError('Nonfinite allowed target/time')
                rows.append({'EVENT': row['EVENT'], 'MA': y, 'TIME': timestamp, 'source_row_index': index, 'benchmark_split': split})
    if count != dev_end or count != dataset_manifest['cache_rows'] or count != sidecar['rows']:
        raise ValueError('Metadata count mismatch')
    for split in ids:
        if ids_sha(ids[split]) != dataset_manifest['splits'][split]['ids_sha256']:raise ValueError('Author split identity changed')
    if [row['EVENT'] for row in rows] != splits[requested]['event_ids']:
        raise ValueError('Requested split not exactly preserved')
    return rows, ids


def verify_cache_headers(path, dataset_manifest, ids, selected, station_cap=25):
    import h5py
    import numpy as np
    counts = {}
    with h5py.File(path, 'r') as h:
        if h.attrs.get('schema') != 'chile-team-prefix-v1' or int(h.attrs.get('stored_samples', 0)) != 3000:
            raise ValueError('Wrong no-TEST full cache schema')
        for name, value in [('sampling_rate',100),('time_before',5),('time_after',25)]:
            if h['metadata/'+name][()] != value:raise ValueError('Cache clock changed')
        if set(h['data']) != set(ids['train'] + ids['dev']):raise ValueError('Unexpected data groups, possibly TEST')
        train_end, dev_end = dataset_manifest['author_split_boundaries']
        for split, start, stop in [('train',0,train_end),('dev',train_end,dev_end)]:
            if h['splits/'+split+'_event_ids'].asstr()[:].tolist() != ids[split] or not np.array_equal(h['splits/'+split+'_source_rows'][:], np.arange(start,stop)):
                raise ValueError('HDF/sidecar membership mismatch')
        for row in selected:
            g=h['data'][row['EVENT']]; shape=g['waveforms'].shape
            if len(shape)!=3 or shape[1:]!=(3000,3) or not 1<=shape[0]<=station_cap or g['coords'].shape!=(shape[0],3):
                raise ValueError('Malformed event shape or source cap truncation')
            counts[row['EVENT']]=shape[0]
    return counts


def verify_dataset_contract(plan, manifest, sidecar):
    if (manifest.get('schema') != 'chile-team-prefix-v1' or manifest.get('stored_samples') != 3000
        or manifest.get('source_test_waveforms_read') is not False or manifest.get('all_event_readback_verified') is not True
        or manifest.get('sha256') != plan['artifacts']['cache']['sha256']):raise ValueError('Wrong completed full TRAIN+DEV cache')
    if (sidecar.get('cache_sha256') != manifest['sha256'] or sidecar.get('origin') != 'metadata/event_metadata'
        or sidecar.get('columns') != ['EVENT','MA','TIME','source_row_index','benchmark_split']
        or sidecar.get('sha256') != plan['artifacts']['metadata']['sha256']):raise ValueError('Wrong metadata sidecar')

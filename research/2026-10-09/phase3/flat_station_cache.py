"""Verified, read-only station cache for a FUTURE TEAM training backend.

This module does not modify or integrate with the live runner. Export includes
all canonical original-TRAIN stations, in event-row then station-index order.
It excludes DEV/TEST waveform arrays. Export publication requires full bitwise
readback against the frozen float32 HDF cache and unchanged source checksums.
A reader requires externally pinned manifest and source-cache hashes.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path

import h5py
import numpy as np

SCHEMA = 'chile-flat-station-v1'
SOURCE_SCHEMA = 'chile-team-prefix-v1'
COLUMNS = ['EVENT', 'MA', 'TIME', 'source_row_index', 'benchmark_split']


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def ids_digest(values):
    return hashlib.sha256('\n'.join(values).encode()).hexdigest()


def membership_digest(events):
    digest = hashlib.sha256()
    for event in events:
        record = [event['event_id'], event['source_row_index'], event['station_ids']]
        digest.update(json.dumps(record, ensure_ascii=True, separators=(',', ':')).encode() + b'\n')
    return digest.hexdigest()


def _strings(dataset):
    return [x.decode('utf-8') if isinstance(x, bytes) else str(x) for x in dataset[:]]


def _source_info(source, expected_cache_sha256, expected_metadata_sha256):
    source = Path(source)
    manifest_path = Path(str(source) + '.manifest.json')
    metadata_path = Path(str(source) + '.metadata.csv')
    sidecar_path = Path(str(metadata_path) + '.manifest.json')
    manifest, sidecar = (json.loads(path.read_text()) for path in (manifest_path, sidecar_path))
    if (manifest.get('schema') != SOURCE_SCHEMA or manifest.get('source_test_waveforms_read') is not False
            or manifest.get('all_event_readback_verified') is not True
            or manifest.get('sha256') != expected_cache_sha256 or file_sha256(source) != expected_cache_sha256):
        raise ValueError('A verified, pinned, completed no-TEST source cache is required')
    if (sidecar.get('cache_sha256') != expected_cache_sha256 or sidecar.get('columns') != COLUMNS
            or sidecar.get('origin') != 'metadata/event_metadata'
            or sidecar.get('sha256') != expected_metadata_sha256
            or file_sha256(metadata_path) != expected_metadata_sha256):
        raise ValueError('Source metadata identity does not match the cache')
    with metadata_path.open(newline='') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError('Unexpected metadata columns')
        rows = list(reader)
    train_end, dev_end = manifest['author_split_boundaries']
    if (not 0 < train_end < dev_end or len(rows) != dev_end
            or len(rows) != manifest['cache_rows'] or len(rows) != sidecar['rows']):
        raise ValueError('Source chronological split boundaries are inconsistent')
    ids, previous_time = [], -math.inf
    for i, row in enumerate(rows):
        magnitude, timestamp = float(row['MA']), float(row['TIME'])
        if (int(row['source_row_index']) != i or row['benchmark_split'] != ('train' if i < train_end else 'dev')
                or not math.isfinite(magnitude) or not math.isfinite(timestamp) or timestamp < previous_time):
            raise ValueError('Invalid chronological source metadata or label')
        previous_time = timestamp
        ids.append(row['EVENT'])
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate source event IDs')
    samples = manifest.get('stored_samples')
    events, offset = [], 0
    with h5py.File(source, 'r') as handle:
        if (handle.attrs.get('schema') != SOURCE_SCHEMA or samples not in (1000, 3000)
                or handle.attrs.get('stored_samples') != samples
                or handle['metadata/sampling_rate'][()] != 100
                or handle['metadata/time_before'][()] != 5
                or handle['metadata/time_after'][()] != samples // 100 - 5
                or set(handle['data']) != set(ids)):
            raise ValueError('Source waveform timing, schema or event membership is invalid')
        for split, start, stop in [('train', 0, train_end), ('dev', train_end, dev_end)]:
            if (_strings(handle[f'splits/{split}_event_ids']) != ids[start:stop]
                    or not np.array_equal(handle[f'splits/{split}_source_rows'][:], np.arange(start, stop))
                    or ids_digest(ids[start:stop]) != manifest['splits'][split]['ids_sha256']):
                raise ValueError('Explicit HDF source split does not match metadata')
        for row in rows[:train_end]:
            group = handle['data'][row['EVENT']]
            waveform = group['waveforms']
            if (waveform.ndim != 3 or waveform.shape[1:] != (samples, 3)
                    or waveform.shape[0] < 1 or waveform.dtype != np.dtype('float32')):
                raise ValueError('Station export requires nonempty raw float32 source arrays')
            station_ids = _strings(group['stations'])
            if len(station_ids) != waveform.shape[0]:
                raise ValueError('Station identities do not cover every source station')
            events.append({'event_id': row['EVENT'], 'source_row_index': int(row['source_row_index']),
                           'magnitude': float(row['MA']), 'time': float(row['TIME']),
                           'station_ids': station_ids, 'offset': offset, 'count': len(station_ids)})
            offset += len(station_ids)
    identity = {'source_cache_sha256': expected_cache_sha256,
                'source_cache_manifest_sha256': file_sha256(manifest_path),
                'source_metadata_sha256': sidecar['sha256'],
                'source_metadata_manifest_sha256': file_sha256(sidecar_path),
                'original_source_sha256': manifest['source_sha256'],
                'canonical_train_ids_sha256': ids_digest(ids[:train_end]),
                'canonical_train_membership_sha256': membership_digest(events),
                'stored_samples': samples, 'events': train_end, 'stations': offset}
    return events, identity


def _atomic_json(value, path):
    path = Path(path)
    temporary = path.with_name(path.name + '.partial')
    with temporary.open('x') as handle:
        json.dump(value, handle, sort_keys=True, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_waveforms(handle, event, samples):
    value = handle['data'][event['event_id']]['waveforms'][:]
    if (value.shape != (event['count'], samples, 3) or value.dtype != np.dtype('float32')
            or not np.isfinite(value).all()):
        raise ValueError('Source waveform shape, dtype or finite-value contract changed')
    return value


def export_flat_station_cache(source, destination, *, expected_source_cache_sha256, expected_source_metadata_sha256):
    """Create a new cache; any failure leaves an unpublished partial directory."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError('Destination must be new; existing artifacts are never overwritten')
    events, identity = _source_info(source, expected_source_cache_sha256, expected_source_metadata_sha256)
    destination.mkdir(parents=True, exist_ok=False)
    samples = identity['stored_samples']
    partial = destination / 'waveforms.npy.partial'
    shape = (identity['stations'], samples, 3)
    output = np.lib.format.open_memmap(partial, mode='w+', dtype=np.float32, shape=shape)
    with h5py.File(source, 'r') as handle:
        for event in events:
            start, stop = event['offset'], event['offset'] + event['count']
            output[start:stop] = _read_waveforms(handle, event, samples)
    output.flush()
    del output
    with partial.open('rb') as handle:
        os.fsync(handle.fileno())
    # Fresh read-only mapping and fresh HDF reads verify every tensor, including
    # signed-zero bits, after the written file has been flushed.
    output = np.load(partial, mmap_mode='r', allow_pickle=False)
    with h5py.File(source, 'r') as handle:
        for event in events:
            actual = output[event['offset']:event['offset'] + event['count']]
            expected = _read_waveforms(handle, event, samples)
            if actual.tobytes(order='C') != expected.tobytes(order='C'):
                raise ValueError('Derived station tensor failed bitwise readback')
    del output
    # Revalidate source content/sidecars after writing. No partial output is a
    # completed artifact even if a process stops between any of these steps.
    final_events, final_identity = _source_info(source, expected_source_cache_sha256, expected_source_metadata_sha256)
    if final_identity != identity or final_events != events:
        raise ValueError('Source identity changed during export')
    os.replace(partial, destination / 'waveforms.npy')
    _atomic_json(events, destination / 'events.json')
    files = {name: {'sha256': file_sha256(destination / name), 'bytes': (destination / name).stat().st_size}
             for name in ('waveforms.npy', 'events.json')}
    manifest = {'schema': SCHEMA, 'complete': True, 'source_identity': identity,
                'created_utc': datetime.now(timezone.utc).isoformat(),
                'exporter_sha256': file_sha256(__file__), 'files': files,
                'shape': list(shape), 'dtype': 'float32', 'partition': 'original_train_only',
                'ordering': 'original_event_row_then_station_index',
                'all_tensor_bits_verified': True, 'dev_waveform_arrays_read': False,
                'test_waveform_arrays_read': False, 'transformations': 'none',
                'numpy_version': np.__version__, 'h5py_version': h5py.__version__}
    _atomic_json(manifest, destination / 'manifest.json')
    descriptor = os.open(destination, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return {'manifest': manifest, 'manifest_sha256': file_sha256(destination / 'manifest.json')}


class FlatStationCache:
    """Verified read-only map; requires pins from the experiment's provenance."""
    def __init__(self, directory, *, expected_manifest_sha256, expected_source_cache_sha256):
        self.directory = Path(directory)
        self.expected_manifest_sha256 = expected_manifest_sha256
        self.expected_source_cache_sha256 = expected_source_cache_sha256
        path = self.directory / 'manifest.json'
        if file_sha256(path) != expected_manifest_sha256:
            raise ValueError('Derived completion manifest is not the pinned artifact')
        manifest = json.loads(path.read_text())
        identity = manifest.get('source_identity', {})
        if (manifest.get('schema') != SCHEMA or manifest.get('complete') is not True
                or manifest.get('partition') != 'original_train_only'
                or manifest.get('all_tensor_bits_verified') is not True
                or manifest.get('dev_waveform_arrays_read') is not False
                or manifest.get('test_waveform_arrays_read') is not False
                or manifest.get('transformations') != 'none'
                or manifest.get('dtype') != 'float32'
                or identity.get('source_cache_sha256') != expected_source_cache_sha256
                or identity.get('stored_samples') not in (1000, 3000)
                or set(manifest.get('files', {})) != {'waveforms.npy', 'events.json'}):
            raise ValueError('Derived manifest does not satisfy the TRAIN-only raw-cache contract')
        for name, record in manifest['files'].items():
            file = self.directory / name
            if file.stat().st_size != record['bytes'] or file_sha256(file) != record['sha256']:
                raise ValueError('Derived file content differs from its completion identity')
        self.events = json.loads((self.directory / 'events.json').read_text())
        offset = 0
        for position, event in enumerate(self.events):
            if (event['source_row_index'] != position or event['offset'] != offset
                    or type(event['count']) is not int or event['count'] < 1
                    or len(event['station_ids']) != event['count']
                    or not math.isfinite(event['magnitude']) or not math.isfinite(event['time'])):
                raise ValueError('Derived event index is not canonical contiguous TRAIN')
            offset += event['count']
        ids = [event['event_id'] for event in self.events]
        if (len(set(ids)) != len(ids) or len(ids) != identity['events'] or offset != identity['stations']
                or ids_digest(ids) != identity['canonical_train_ids_sha256']
                or membership_digest(self.events) != identity['canonical_train_membership_sha256']):
            raise ValueError('Derived station membership does not match its identity')
        self._array = np.load(self.directory / 'waveforms.npy', mmap_mode='r', allow_pickle=False)
        if (self._array.dtype != np.dtype('float32') or self._array.shape != tuple(manifest['shape'])
                or self._array.shape != (offset, identity['stored_samples'], 3) or self._array.flags.writeable):
            raise ValueError('Derived array layout/read-only contract is invalid')
        self.manifest = manifest
        self._by_event = {event['event_id']: event for event in self.events}

    def subset(self, event_ids, *, expected_membership_sha256):
        """Keep the caller's exact event order; unknown/DEV/duplicate IDs fail."""
        ids = list(event_ids)
        if not ids or len(ids) != len(set(ids)) or any(x not in self._by_event for x in ids):
            raise ValueError('Subset must contain unique original-TRAIN event IDs')
        events = [self._by_event[x] for x in ids]
        if membership_digest(events) != expected_membership_sha256:
            raise ValueError('Subset station/event order does not match the required source membership')
        return FlatStationSubset(self, events)

    def close(self):
        # Existing returned views retain ownership of their map; do not forcibly
        # close its mmap while a caller may still hold a NumPy/Torch view.
        self._array = None

    def __getstate__(self):
        return {'directory': self.directory, 'expected_manifest_sha256': self.expected_manifest_sha256,
                'expected_source_cache_sha256': self.expected_source_cache_sha256}

    def __setstate__(self, state):
        self.__init__(**state)


class FlatStationSubset:
    """NumPy Dataset-compatible (waveform, float64-label) reader; no Torch import."""
    def __init__(self, cache, events):
        self.cache, self.events = cache, events
        self.ends = np.cumsum([event['count'] for event in events])
        self.membership_sha256 = membership_digest(events)

    def __len__(self):
        return int(self.ends[-1])

    def __getitem__(self, index):
        if not isinstance(index, (int, np.integer)):
            raise TypeError('A scalar station index is required')
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        if self.cache._array is None:
            raise RuntimeError('Station cache has been closed')
        event_index = int(np.searchsorted(self.ends, index, side='right'))
        event = self.events[event_index]
        station = index - (int(self.ends[event_index - 1]) if event_index else 0)
        value = np.asarray(self.cache._array[event['offset'] + station])
        return value, event['magnitude']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--expected-source-cache-sha256', required=True)
    parser.add_argument('--expected-source-metadata-sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(export_flat_station_cache(args.source, args.destination,
          expected_source_cache_sha256=args.expected_source_cache_sha256,
          expected_source_metadata_sha256=args.expected_source_metadata_sha256), indent=2), flush=True)


if __name__ == '__main__':
    main()

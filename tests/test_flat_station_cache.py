"""Small HDF/CSV fixtures test the future flat backend without Torch or DEV reads."""
import csv
import json
from pathlib import Path
import pickle
import sys
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1] / 'research/2026-10-09/phase3'))
import flat_station_cache as cache


def fixture(root, samples=1000):
    root = Path(root)
    path = root / 'source.hdf5'
    ids = [f'event_{i}' for i in range(7)]
    with h5py.File(path, 'w') as handle:
        handle.attrs['schema'] = cache.SOURCE_SCHEMA
        handle.attrs['stored_samples'] = samples
        for key, value in [('sampling_rate', 100), ('time_before', 5), ('time_after', samples // 100 - 5)]:
            handle.create_dataset('metadata/' + key, data=value)
        for split, start, stop in [('train', 0, 6), ('dev', 6, 7)]:
            handle.create_dataset('splits/' + split + '_event_ids', data=ids[start:stop], dtype=h5py.string_dtype())
            handle.create_dataset('splits/' + split + '_source_rows', data=np.arange(start, stop))
        for i, event_id in enumerate(ids):
            count = i % 3 + 1
            waveform = (np.arange(count * samples * 3, dtype=np.float32).reshape(count, samples, 3) + i) * 1e-6
            waveform[0, 0, 0] = np.float32(-0.)
            if i == 6:
                # Deliberately poison DEV: export must never inspect these values.
                # This is a synthetic fixture, not a claimed verified real cache.
                waveform[:] = np.nan
            handle.create_dataset('data/' + event_id + '/waveforms', data=waveform)
            handle.create_dataset('data/' + event_id + '/stations', data=[f'S{j}' for j in range(count)], dtype=h5py.string_dtype())
    manifest = {'schema': cache.SOURCE_SCHEMA, 'source_test_waveforms_read': False,
                'all_event_readback_verified': True, 'sha256': cache.file_sha256(path),
                'source_sha256': 'original-source-fixture', 'source_rows': 10, 'cache_rows': 7,
                'stored_samples': samples, 'author_split_boundaries': [6, 7],
                'splits': {name: {'ids_sha256': cache.ids_digest(ids[start:stop])}
                           for name, start, stop in [('train', 0, 6), ('dev', 6, 7)]}}
    Path(str(path) + '.manifest.json').write_text(json.dumps(manifest))
    csv_path = Path(str(path) + '.metadata.csv')
    with csv_path.open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(cache.COLUMNS)
        writer.writerows([[name, 2.123456789012345 + i / 10, i * 10., i, 'train' if i < 6 else 'dev'] for i, name in enumerate(ids)])
    Path(str(csv_path) + '.manifest.json').write_text(json.dumps({
        'cache_sha256': manifest['sha256'], 'sha256': cache.file_sha256(csv_path),
        'rows': 7, 'columns': cache.COLUMNS, 'origin': 'metadata/event_metadata'}))
    return path, manifest['sha256']


def repin_source(path):
    sha = cache.file_sha256(path)
    for suffix, field in [('.manifest.json', 'sha256'), ('.metadata.csv.manifest.json', 'cache_sha256')]:
        file = Path(str(path) + suffix)
        data = json.loads(file.read_text())
        data[field] = sha
        file.write_text(json.dumps(data))
    return sha


def export(root, samples=1000):
    source, source_sha = fixture(root, samples)
    output = Path(root) / 'flat'
    result = cache.export_flat_station_cache(source, output, expected_source_cache_sha256=source_sha,
                    expected_source_metadata_sha256=cache.file_sha256(Path(str(source) + '.metadata.csv')))
    pins = {'expected_manifest_sha256': result['manifest_sha256'], 'expected_source_cache_sha256': source_sha}
    return source, output, result, pins


class FlatStationCacheTests(unittest.TestCase):
    def test_export_verifies_all_train_bits_and_preserves_signed_zero(self):
        for samples in (1000, 3000):
            with self.subTest(samples=samples), tempfile.TemporaryDirectory() as root:
                source, output, result, pins = export(root, samples)
                reader = cache.FlatStationCache(output, **pins)
                self.assertEqual(len(reader.events), 6)
                self.assertEqual(result['manifest']['shape'], [12, samples, 3])
                self.assertFalse(result['manifest']['dev_waveform_arrays_read'])
                self.assertTrue(result['manifest']['all_tensor_bits_verified'])
                with h5py.File(source, 'r') as handle:
                    for event in reader.events:
                        expected = handle['data'][event['event_id']]['waveforms'][:]
                        actual = reader._array[event['offset']:event['offset'] + event['count']]
                        self.assertEqual(actual.tobytes(), expected.tobytes())
                        self.assertTrue(np.signbit(actual[0, 0, 0]))
                self.assertFalse((output / 'waveforms.npy.partial').exists())

    def test_subset_retains_requested_order_labels_and_readonly_views(self):
        with tempfile.TemporaryDirectory() as root:
            source, output, _, pins = export(root)
            reader = cache.FlatStationCache(output, **pins)
            events = [reader.events[4], reader.events[0], reader.events[2]]
            subset = reader.subset([x['event_id'] for x in events], expected_membership_sha256=cache.membership_digest(events))
            self.assertEqual(len(subset), 6)
            expected = []
            with h5py.File(source, 'r') as handle:
                for event in events:
                    expected.extend((x, event['magnitude']) for x in handle['data'][event['event_id']]['waveforms'][:])
            for i, (x, label) in enumerate(expected):
                value, actual_label = subset[i]
                self.assertEqual(value.tobytes(), x.tobytes())
                self.assertEqual(actual_label, label)
                self.assertFalse(value.flags.writeable)
                with self.assertRaises(ValueError):
                    value[0, 0] = 10
            self.assertEqual(subset[-1][0].tobytes(), expected[-1][0].tobytes())
            for i in (-7, 6):
                with self.assertRaises(IndexError):
                    subset[i]
            with self.assertRaises(TypeError):
                subset[1.5]
            previous_view = subset[0][0]
            reader.close()
            self.assertEqual(previous_view.tobytes(), expected[0][0].tobytes())
            with self.assertRaises(RuntimeError):
                subset[0]

    def test_subset_rejects_dev_unknown_duplicates_and_wrong_order(self):
        with tempfile.TemporaryDirectory() as root:
            _, output, _, pins = export(root)
            reader = cache.FlatStationCache(output, **pins)
            for ids in ([], ['event_6'], ['unknown'], ['event_0', 'event_0']):
                with self.assertRaises(ValueError):
                    reader.subset(ids, expected_membership_sha256='irrelevant')
            with self.assertRaises(ValueError):
                reader.subset(['event_1', 'event_0'], expected_membership_sha256=cache.membership_digest(reader.events[:2]))

    def test_changed_source_pin_metadata_and_hdf_split_fail_closed(self):
        for change in ('pin', 'metadata', 'split'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as root:
                source, source_sha = fixture(root)
                if change == 'pin':
                    source_sha = 'wrong-pin'
                elif change == 'metadata':
                    with Path(str(source) + '.metadata.csv').open('a') as handle:
                        handle.write('\n')
                else:
                    with h5py.File(source, 'r+') as handle:
                        handle['splits/train_source_rows'][0] = 99
                    source_sha = repin_source(source)
                output = Path(root) / 'flat'
                with self.assertRaises(ValueError):
                    cache.export_flat_station_cache(source, output, expected_source_cache_sha256=source_sha,
                    expected_source_metadata_sha256=cache.file_sha256(Path(str(source) + '.metadata.csv')))
                self.assertFalse((output / 'manifest.json').exists())

    def test_self_consistent_changed_metadata_cannot_bypass_external_pin(self):
        with tempfile.TemporaryDirectory() as root:
            source, source_sha = fixture(root)
            metadata = Path(str(source) + '.metadata.csv')
            original_sha = cache.file_sha256(metadata)
            with metadata.open(newline='') as handle:
                rows = list(csv.DictReader(handle))
            rows[0]['MA'] = '8.5'
            with metadata.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=cache.COLUMNS)
                writer.writeheader()
                writer.writerows(rows)
            sidecar = Path(str(metadata) + '.manifest.json')
            record = json.loads(sidecar.read_text())
            record['sha256'] = cache.file_sha256(metadata)
            sidecar.write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                cache.export_flat_station_cache(source, Path(root) / 'flat',
                    expected_source_cache_sha256=source_sha, expected_source_metadata_sha256=original_sha)

    def test_fractional_timing_and_sample_metadata_are_rejected(self):
        for key in ('sampling_rate', 'time_before', 'time_after', 'stored_samples'):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                source, _ = fixture(root)
                with h5py.File(source, 'r+') as handle:
                    if key == 'stored_samples':
                        handle.attrs[key] = 1000.5
                    else:
                        name = 'metadata/' + key
                        value = float(handle[name][()]) + .5
                        del handle[name]
                        handle.create_dataset(name, data=value)
                source_sha = repin_source(source)
                output = Path(root) / 'flat'
                with self.assertRaises(ValueError):
                    cache.export_flat_station_cache(source, output,
                        expected_source_cache_sha256=source_sha,
                        expected_source_metadata_sha256=cache.file_sha256(Path(str(source) + '.metadata.csv')))
                self.assertFalse((output / 'manifest.json').exists())

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            source, output, _, pins = export(root)
            before = cache.file_sha256(output / 'manifest.json')
            with self.assertRaises(FileExistsError):
                cache.export_flat_station_cache(source, output, expected_source_cache_sha256=pins['expected_source_cache_sha256'],
                    expected_source_metadata_sha256=cache.file_sha256(Path(str(source) + '.metadata.csv')))
            self.assertEqual(before, cache.file_sha256(output / 'manifest.json'))

    def test_interrupted_export_never_publishes_completion(self):
        with tempfile.TemporaryDirectory() as root:
            source, source_sha = fixture(root)
            output = Path(root) / 'flat'
            original = cache._read_waveforms
            calls = 0
            def failing(handle, event, samples):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('simulated interruption')
                return original(handle, event, samples)
            with patch.object(cache, '_read_waveforms', side_effect=failing), self.assertRaises(OSError):
                cache.export_flat_station_cache(source, output, expected_source_cache_sha256=source_sha,
                    expected_source_metadata_sha256=cache.file_sha256(Path(str(source) + '.metadata.csv')))
            self.assertFalse((output / 'manifest.json').exists())
            with self.assertRaises(FileNotFoundError):
                cache.FlatStationCache(output, expected_manifest_sha256='missing', expected_source_cache_sha256=source_sha)

    def test_corrupt_derived_file_or_wrong_pins_are_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            _, output, _, pins = export(root)
            for field in pins:
                changed = dict(pins, **{field: 'wrong-pin'})
                with self.assertRaises(ValueError):
                    cache.FlatStationCache(output, **changed)
            with (output / 'waveforms.npy').open('r+b') as handle:
                handle.seek(-1, 2)
                old = handle.read(1)
                handle.seek(-1, 2)
                handle.write(bytes([old[0] ^ 1]))
            with self.assertRaises(ValueError):
                cache.FlatStationCache(output, **pins)

    def test_noncanonical_index_fails_even_when_its_checksum_is_repinned(self):
        with tempfile.TemporaryDirectory() as root:
            _, output, _, pins = export(root)
            events_path = output / 'events.json'
            events = json.loads(events_path.read_text())
            events[1]['offset'] += 1
            events_path.write_text(json.dumps(events))
            manifest_path = output / 'manifest.json'
            manifest = json.loads(manifest_path.read_text())
            manifest['files']['events.json'] = {'sha256': cache.file_sha256(events_path), 'bytes': events_path.stat().st_size}
            manifest_path.write_text(json.dumps(manifest))
            pins['expected_manifest_sha256'] = cache.file_sha256(manifest_path)
            with self.assertRaises(ValueError):
                cache.FlatStationCache(output, **pins)

    def test_pickle_reopens_verified_readonly_map_and_subset(self):
        with tempfile.TemporaryDirectory() as root:
            _, output, _, pins = export(root)
            reader = cache.FlatStationCache(output, **pins)
            subset = reader.subset(['event_1'], expected_membership_sha256=cache.membership_digest([reader.events[1]]))
            loaded = pickle.loads(pickle.dumps(subset))
            self.assertEqual(loaded[1][0].tobytes(), subset[1][0].tobytes())
            self.assertFalse(loaded[0][0].flags.writeable)
            self.assertEqual(loaded.membership_sha256, subset.membership_sha256)

    def test_invalid_train_values_or_dtype_never_publish(self):
        for invalid in ('nan', 'float64'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as root:
                source, _ = fixture(root)
                with h5py.File(source, 'r+') as handle:
                    group = handle['data/event_0']
                    if invalid == 'nan':
                        group['waveforms'][0, 0, 0] = np.nan
                    else:
                        value = group['waveforms'][:].astype(np.float64)
                        del group['waveforms']
                        group.create_dataset('waveforms', data=value)
                source_sha = repin_source(source)
                output = Path(root) / 'flat'
                with self.assertRaises(ValueError):
                    cache.export_flat_station_cache(source, output, expected_source_cache_sha256=source_sha,
                    expected_source_metadata_sha256=cache.file_sha256(Path(str(source) + '.metadata.csv')))
                self.assertFalse((output / 'manifest.json').exists())


if __name__ == '__main__':
    unittest.main()

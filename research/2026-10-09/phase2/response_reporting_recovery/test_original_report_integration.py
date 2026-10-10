"""Frozen reporter integration using invented arrays and stub checkpoints only."""
import contextlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ['CUDA_VISIBLE_DEVICES'] = ''
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '2'
sys.dont_write_bytecode = True
SOURCE = Path(os.environ.get('RESPONSE_SOURCE_DIR', Path(__file__).resolve().parent.parent / 'response_conditioned_encoder')).resolve()
sys.path.insert(0, str(SOURCE))
import numpy as np
import train_response_grid as original
from response_data import CompletedExport
import recover_report as recovery


def synthetic_grid(directory):
    directory = Path(directory)
    export = directory / 'export'; export.mkdir()
    root = directory / 'grid'; root.mkdir()
    rng = np.random.default_rng(20261010)
    n = 12
    counts = rng.normal(size=(n, 3, 500)).astype(np.float64) * 100
    static = np.zeros((n, 34)); static[:, 0] = 1
    response = np.zeros((n, 3, 6, 4)); response[..., 1] = 1; response[..., 3] = 1
    valid = np.ones((n, 3), dtype=bool); valid[0, 2] = False; valid[-1, 0] = False
    metadata = dict(valid=valid, invalid_codes=np.where(valid, 0, 64).astype(np.uint16),
                    sensitivity=np.ones((n, 3)) * 1e6, static=static, response=response.reshape(n, 72),
                    source_row_index=np.arange(n) * 7, trace_name=np.array([f'invented-trace-{i}' for i in range(n)]),
                    source_id=np.array([f'fit-{i}' for i in range(6)] + ['held-0', 'held-1', 'held-2'] * 2),
                    station_group=np.array(['seen'] * 9 + ['held'] * 3),
                    subset=np.array(['fit'] * 6 + ['eval_seen'] * 3 + ['eval_held'] * 3),
                    sampling_weight=1 + np.arange(n) % 3,
                    targets=np.array([.5, 1., 1.5, 2., 3., 4., 2., 4.2, 5.1, 2., 4.2, 5.1]),
                    native_units=np.array(['m/s'] * n), deadlines=np.array([1, 3, 5]))
    np.save(export / 'counts.npy', counts)
    np.savez(export / 'metadata.npz', **metadata)
    manifest = dict(status='complete', protocol_sha256=original.PROTOCOL_SHA,
                    polarization_manifest_sha256=original.PARENT_SHA,
                    outputs_sha256={name: recovery.sha(export / name) for name in ('counts.npy', 'metadata.npz')})
    recovery.atomic_json(export / 'manifest.json', manifest)
    export_sha = recovery.sha(export / 'manifest.json')
    recovery.atomic_json(export / 'COMPLETE.json', {'manifest_sha256': export_sha})
    dataset = CompletedExport(export)
    # Tiny synthetic fit-only normalization; no network fit or forward pass.
    original.prepare(dataset, root / 'prepared')
    pop = {t: dataset.valid_rows('fit', t) for t in original.DEADLINES}
    draws = max(map(len, pop.values()))
    for arm in recovery.ARMS:
        for seed in recovery.SEEDS:
            path = root / f'{arm}_{seed}'; path.mkdir()
            predictions = {}
            for t in original.DEADLINES:
                for subset in original.SUBSETS:
                    rows = dataset.valid_rows(subset, t); key = f'{t}_{subset}'
                    predictions['rows_' + key] = rows
                    p = rng.random((len(rows), 66)); p /= p.sum(1, keepdims=True)
                    predictions['p_' + key] = p
            np.savez(path / 'predictions.npz', **predictions)
            (path / 'checkpoint.pt').write_bytes(b'Invented stub; must never torch.load this file')
            recovery.atomic_json(path / 'gain_diagnostic.json', {})
            fit = {'initial_state_sha256': 'invented-matched-state',
                   'fit_rows': {str(t): len(v) for t, v in pop.items()},
                   'fit_weight_mean': {str(t): float(metadata['sampling_weight'][v].mean()) for t, v in pop.items()},
                   'steps': 10 * math.ceil(draws / 512),
                   'order_sha256': [{str(t): original.array_sha(v) for t, v in original.schedules(pop, seed, e).items()} for e in range(10)],
                   'history': [{'epoch': e + 1, 'draws_per_horizon': draws, 'training_loss': 1.0} for e in range(10)]}
            m = dict(status='complete', arm=arm, seed=seed, epochs=10, batch_size=512,
                     protocol_sha256=original.PROTOCOL_SHA, bundle_sha256=recovery.BUNDLE_SHA,
                     export_manifest_sha256=export_sha, normalizers_sha256=recovery.sha(root / 'prepared/normalizers.json'),
                     fit=fit, seconds=1., outputs_sha256={name: recovery.sha(path / name) for name in recovery.FIT_FILES[2:]})
            recovery.atomic_json(path / 'manifest.json', m)
            recovery.atomic_json(path / 'COMPLETE.json', {'manifest_sha256': recovery.sha(path / 'manifest.json')})
    grid = dict(status='training_complete', bundle_sha256=recovery.BUNDLE_SHA,
                protocol_sha256=original.PROTOCOL_SHA, export_manifest_sha256=export_sha,
                arms=list(recovery.ARMS), seeds=list(recovery.SEEDS), training_seconds=659.24)
    recovery.atomic_json(root / 'grid_manifest.json', grid)
    return dataset, root, recovery.sha(root / 'grid_manifest.json'), export_sha


class OriginalIntegrationTests(unittest.TestCase):
    def test_original_source_pinned(self):
        original.verify_bundle(SOURCE / 'training_source_manifest.json', recovery.BUNDLE_SHA)
        self.assertEqual(Path(original.__file__).resolve(), SOURCE / 'train_response_grid.py')
        self.assertFalse(original.torch.cuda.is_initialized())

    def test_full_original_report_bytes_and_completion(self):
        with tempfile.TemporaryDirectory() as d:
            ds, root, grid_sha, export_sha = synthetic_grid(d)
            before = recovery.fit_snapshot(root, recovery.BUNDLE_SHA, export_sha, original.PROTOCOL_SHA)
            report = original.report_grid(root, ds, recovery.BUNDLE_SHA)
            expected = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
            self.assertEqual(len(report['scores']), 72)
            self.assertEqual(len(report['comparisons']), 6)
            self.assertEqual(len(report['matched_event_panels']), 24)
            with contextlib.redirect_stdout(io.StringIO()):
                recovery.recover_locked(root, Path(d) / 'receipt', grid_sha, recovery.BUNDLE_SHA,
                                        export_sha, original.PROTOCOL_SHA,
                                        lambda: original.report_grid(root, ds, recovery.BUNDLE_SHA),
                                        lambda: recovery.verify_export_manifest(ds.path, export_sha),
                                        {'synthetic': True})
            self.assertEqual((root / 'report.json').read_bytes(), expected)
            self.assertEqual(json.loads(expected), recovery.read_json(root / 'report.json'))
            self.assertEqual(before, recovery.fit_snapshot(root, recovery.BUNDLE_SHA, export_sha, original.PROTOCOL_SHA))
            self.assertEqual(recovery.read_json(root / 'COMPLETE.json'), {'grid_manifest_sha256': recovery.sha(root / 'grid_manifest.json')})

    def test_original_alignment_guard_still_controls_completion(self):
        with tempfile.TemporaryDirectory() as d:
            ds, root, grid_sha, export_sha = synthetic_grid(d)
            path = root / 'A_20261009'
            with np.load(path / 'predictions.npz', allow_pickle=False) as f:
                p = {key: f[key] for key in f.files}
            p['rows_1_eval_seen'] = p['rows_1_eval_seen'][::-1]
            np.savez(path / 'predictions.npz', **p)
            manifest = recovery.read_json(path / 'manifest.json')
            manifest['outputs_sha256']['predictions.npz'] = recovery.sha(path / 'predictions.npz')
            recovery.atomic_json(path / 'manifest.json', manifest)
            recovery.atomic_json(path / 'COMPLETE.json', {'manifest_sha256': recovery.sha(path / 'manifest.json')})
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, 'row order mismatch'):
                recovery.recover_locked(root, Path(d) / 'receipt', grid_sha, recovery.BUNDLE_SHA,
                                        export_sha, original.PROTOCOL_SHA,
                                        lambda: original.report_grid(root, ds, recovery.BUNDLE_SHA), lambda: None,
                                        {'synthetic': True})
            self.assertFalse((root / 'COMPLETE.json').exists())
            self.assertFalse((root / 'report.json').exists())


if __name__ == '__main__':
    unittest.main()

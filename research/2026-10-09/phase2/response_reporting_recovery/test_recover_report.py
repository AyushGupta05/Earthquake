"""Only invented JSON/files; no original datasets/checkpoints are accessed."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import recover_report as recovery


def old_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def fake_grid(root):
    root.mkdir()
    (root / 'prepared').mkdir()
    for name in ('normalizers.json', 'normalizers.npz'):
        (root / 'prepared' / name).write_bytes(b'synthetic, never decoded')
    normalizer = recovery.sha(root / 'prepared/normalizers.json')
    for arm in recovery.ARMS:
        for seed in recovery.SEEDS:
            path = root / f'{arm}_{seed}'
            path.mkdir()
            for name in recovery.FIT_FILES[2:]:
                (path / name).write_bytes(b'synthetic, never decoded')
            manifest = dict(status='complete', arm=arm, seed=seed, epochs=10, batch_size=512,
                            bundle_sha256='bundle', export_manifest_sha256='export',
                            protocol_sha256='protocol', normalizers_sha256=normalizer, seconds=1,
                            outputs_sha256={n: recovery.sha(path / n) for n in recovery.FIT_FILES[2:]})
            recovery.atomic_json(path / 'manifest.json', manifest)
            recovery.atomic_json(path / 'COMPLETE.json', {'manifest_sha256': recovery.sha(path / 'manifest.json')})
    grid = dict(status='training_complete', bundle_sha256='bundle', protocol_sha256='protocol',
                export_manifest_sha256='export', arms=list(recovery.ARMS), seeds=list(recovery.SEEDS),
                training_seconds=659.24)
    recovery.atomic_json(root / 'grid_manifest.json', grid)
    return recovery.sha(root / 'grid_manifest.json')


class RecoveryTests(unittest.TestCase):
    def recover(self, root, receipt, grid_sha, report=lambda: {'synthetic': True}, verify=lambda: None):
        with contextlib.redirect_stdout(io.StringIO()):
            recovery.recover_locked(root, receipt, grid_sha, 'bundle', 'export', 'protocol',
                                    report, verify, {'synthetic': True})

    def test_stream_matches_old_bytes_and_semantics(self):
        values = [{}, [None, True, False, -0.0, 1e-200, 1e200],
                  {'z': 'π\n😀', 'a': {'null': None, 'tuple': (1, 2), 'float': .12345678901234568}},
                  {'events': [{'id': str(i), 'error': i / 9, 'p': [.01] * 66} for i in range(2000)]}]
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'report.json'
            for value in values:
                recovery.atomic_json(path, value)
                self.assertEqual(path.read_bytes(), old_bytes(value))
                self.assertEqual(json.loads(path.read_bytes()), json.loads(old_bytes(value)))
                self.assertFalse(path.with_suffix('.json.partial').exists())

    def test_no_full_string_serializer_used(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(recovery.json, 'dumps', side_effect=AssertionError('full string')):
            recovery.atomic_json(Path(d) / 'report.json', {'large': list(range(1000))})

    def test_nan_failure_removes_partial_preserves_destination(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'report.json'
            path.write_bytes(b'previous')
            with self.assertRaises(ValueError):
                recovery.atomic_json(path, {'a': [0.0, float('nan')]})
            self.assertEqual(path.read_bytes(), b'previous')
            self.assertFalse(path.with_suffix('.json.partial').exists())

    def test_existing_partial_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'report.json'
            path.with_suffix('.json.partial').write_bytes(b'interrupted')
            with self.assertRaises(FileExistsError):
                recovery.atomic_json(path, {})
            self.assertEqual(path.with_suffix('.json.partial').read_bytes(), b'interrupted')

    def test_success_original_schema_bytes_and_fit_immutability(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'grid'; receipt = Path(d) / 'receipt'; digest = fake_grid(root)
            original = (root / 'grid_manifest.json').read_bytes()
            before = recovery.fit_snapshot(root, 'bundle', 'export', 'protocol')
            report = {'z': {'π': [1.0, None]}, 'a': []}
            callback = mock.Mock(return_value=report)
            self.recover(root, receipt, digest, callback)
            callback.assert_called_once_with()
            self.assertEqual((receipt / 'pre_recovery_grid_manifest.json').read_bytes(), original)
            self.assertEqual((root / 'report.json').read_bytes(), old_bytes(report))
            grid = json.loads(original); grid.update(status='complete', report_sha256=recovery.sha(root / 'report.json'))
            self.assertEqual((root / 'grid_manifest.json').read_bytes(), old_bytes(grid))
            self.assertEqual((root / 'COMPLETE.json').read_bytes(), old_bytes({'grid_manifest_sha256': recovery.sha(root / 'grid_manifest.json')}))
            self.assertEqual(before, recovery.fit_snapshot(root, 'bundle', 'export', 'protocol'))
            r = recovery.read_json(receipt / 'recovery_receipt.json')
            self.assertEqual(r['fit_files_before_sha256'], r['fit_files_after_sha256'])
            self.assertEqual(r['pre_recovery_grid_manifest_sha256'], digest)
            stages = [json.loads(x) for x in (receipt / 'progress.jsonl').read_text().splitlines()]
            self.assertEqual(len(stages), 5)
            self.assertTrue(all(set(x) == {'stage', 'elapsed_seconds', 'peak_rss_bytes'} for x in stages))

    def test_missing_fit_never_reports_or_completes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'grid'; digest = fake_grid(root)
            (root / 'D_20261010/COMPLETE.json').unlink()
            report = mock.Mock()
            with self.assertRaises(ValueError):
                self.recover(root, Path(d) / 'receipt', digest, report)
            report.assert_not_called()
            self.assertFalse((root / 'COMPLETE.json').exists())
            self.assertEqual(recovery.sha(root / 'grid_manifest.json'), digest)

    def test_corrupt_artifact_rejected_before_reporting(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'grid'; digest = fake_grid(root)
            (root / 'A_20261009/predictions.npz').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'artifact changed'):
                self.recover(root, Path(d) / 'receipt', digest)
            self.assertFalse((root / 'COMPLETE.json').exists())

    def test_report_failure_or_nan_never_completes(self):
        for report in (mock.Mock(side_effect=RuntimeError('synthetic')), lambda: {'bad': float('nan')}):
            with self.subTest(report=report), tempfile.TemporaryDirectory() as d:
                root = Path(d) / 'grid'; digest = fake_grid(root)
                with self.assertRaises((RuntimeError, ValueError)):
                    self.recover(root, Path(d) / 'receipt', digest, report)
                self.assertFalse((root / 'COMPLETE.json').exists())
                self.assertFalse((root / 'report.json.partial').exists())
                self.assertEqual(recovery.sha(root / 'grid_manifest.json'), digest)

    def test_changed_input_after_report_never_completes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'grid'; digest = fake_grid(root)
            verify = mock.Mock(side_effect=[None, ValueError('changed source')])
            with self.assertRaises(ValueError):
                self.recover(root, Path(d) / 'receipt', digest, verify=verify)
            self.assertTrue((root / 'report.json').exists())
            self.assertFalse((root / 'COMPLETE.json').exists())
            self.assertEqual(recovery.sha(root / 'grid_manifest.json'), digest)

    def test_marker_failure_rolls_back_original_grid(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'grid'; digest = fake_grid(root)
            write = recovery.atomic_json
            def fail_marker(path, value):
                if Path(path) == root / 'COMPLETE.json':
                    raise OSError('synthetic failed marker write')
                write(path, value)
            with mock.patch.object(recovery, 'atomic_json', side_effect=fail_marker), self.assertRaises(OSError):
                self.recover(root, Path(d) / 'receipt', digest)
            self.assertFalse((root / 'COMPLETE.json').exists())
            self.assertEqual(recovery.sha(root / 'grid_manifest.json'), digest)

    def test_wrong_grid_pin_state_budget_and_preexisting_report(self):
        for change in ('pin', 'state', 'budget', 'report'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as d:
                root = Path(d) / 'grid'; digest = fake_grid(root)
                if change == 'pin': digest = 'wrong'
                if change in ('state', 'budget'):
                    grid = recovery.read_json(root / 'grid_manifest.json')
                    grid['status' if change == 'state' else 'training_seconds'] = 'started' if change == 'state' else 4801
                    recovery.atomic_json(root / 'grid_manifest.json', grid); digest = recovery.sha(root / 'grid_manifest.json')
                if change == 'report': (root / 'report.json').write_bytes(b'existing')
                with self.assertRaises(ValueError): self.recover(root, Path(d) / 'receipt', digest)
                self.assertFalse((root / 'COMPLETE.json').exists())

    def test_dry_run_no_paths_imports_or_writes(self):
        script = Path(recovery.__file__).resolve()
        result = subprocess.run([sys.executable, str(script), '--deployment-root', '/nonexistent/deploy',
                                 '--export', '/nonexistent/export', '--grid', '/nonexistent/grid',
                                 '--receipt-dir', '/nonexistent/receipt', '--wrapper-sha256', 'unused',
                                 '--grid-manifest-sha256', 'unused'], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(result.stdout)['execute'])
        self.assertNotIn('torch', result.stderr)

    def test_unsafe_manifest_paths_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for value in ('../outside', '/outside'):
                with self.assertRaises(ValueError): recovery.checked_file(d, value)
            path = Path(d) / 'file'; path.write_bytes(b'x')
            (Path(d) / 'link').symlink_to(path)
            with self.assertRaises(ValueError): recovery.checked_file(d, 'link')


if __name__ == '__main__':
    unittest.main()

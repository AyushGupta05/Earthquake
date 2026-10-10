"""CPU reporting recovery for one immutable response grid; dry by default.

No trainer, forward pass, sampling, scores or decision rules are modified.
The parent must supply an outer 1800-second process-group/cgroup timeout.
"""
import argparse
import fcntl
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import resource
import sys
import time

DEPLOYMENT_SHA = '7204ab1d6502599565478a641a824cd92a1028bf81b6410360845d79c682362f'
BUNDLE_SHA = 'f745a18b194490b2f018845ddeeb5a3282aa9a0307a4795cfebe465382b669d3'
EXPORT_SHA = '55ba19f81f59c106964ae92302258aba7780d5bc1a48cd3ec20617c8f2ba2a46'
PROTOCOL_SHA = '403fe4bafabc11dad71b8a02d16e98a6b8d8c3a5c95ca89a812a5193a284f1b8'
ARMS = ('A', 'B', 'C', 'D')
SEEDS = (20261009, 20261010)
SOURCE_RELATIVE = Path('work/response_conditioned_encoder')
FIT_FILES = ('COMPLETE.json', 'manifest.json', 'checkpoint.pt', 'predictions.npz', 'gain_diagnostic.json')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def atomic_json(path, value):
    """Byte-equivalent to original dumps(...)+LF without its full string copy."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.partial')
    # Exclusive creation rejects an interrupted earlier serialization.
    with temporary.open('x', encoding='utf-8', newline='\n', buffering=1 << 20) as f:
        try:
            json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    os.replace(temporary, path)


def checked_file(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe manifest path')
    path = root / rel
    if not path.is_file() or path.resolve() != path:
        raise ValueError('Missing file or symlink: ' + str(rel))
    return path


def verify_deployment(root):
    root = Path(root).resolve()
    manifest = checked_file(root, 'bundle_manifest.json')
    if sha(manifest) != DEPLOYMENT_SHA:
        raise ValueError('Deployment manifest changed')
    value = read_json(manifest)
    if value['schema'] != 'distribution-grids-deployment-v1' or len(value['files']) != 41:
        raise ValueError('Wrong deployment schema/allowlist')
    for name, entry in value['files'].items():
        path = checked_file(root, name)
        if path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise ValueError('Deployment file changed: ' + name)
    bundle = checked_file(root, SOURCE_RELATIVE / 'training_source_manifest.json')
    if sha(bundle) != BUNDLE_SHA:
        raise ValueError('Original training bundle changed')
    return root / SOURCE_RELATIVE, bundle


def import_original(source, bundle):
    """Only the hash-verified original modules can supply the report function."""
    modules = ('train_response_grid', 'response_model', 'response_data', 'response_metrics')
    if any(name in sys.modules for name in modules):
        raise ValueError('Start a fresh reporting process; original modules already imported')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '2'
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source))
    original = importlib.import_module('train_response_grid')
    for name in modules:
        if Path(sys.modules[name].__file__).resolve() != source / (name + '.py'):
            raise ValueError('Imported source outside verified deployment')
    original.verify_bundle(bundle, BUNDLE_SHA)
    original.torch.set_num_threads(2)
    if original.torch.cuda.is_initialized():
        raise ValueError('Recovery must not initialize CUDA')
    return original


def verify_export_manifest(path, expected):
    path = Path(path)
    if sha(checked_file(path, 'manifest.json')) != expected:
        raise ValueError('Export manifest changed')
    if read_json(checked_file(path, 'COMPLETE.json')) != {'manifest_sha256': expected}:
        raise ValueError('Export completion mismatch')
    manifest = read_json(path / 'manifest.json')
    if manifest['status'] != 'complete' or set(manifest['outputs_sha256']) != {'counts.npy', 'metadata.npz'}:
        raise ValueError('Incomplete export schema')
    # Bounded streaming hashes; no waveform sample/container decoding here.
    for name, digest in manifest['outputs_sha256'].items():
        if sha(checked_file(path, name)) != digest:
            raise ValueError('Export artifact changed: ' + name)
    return manifest


def fit_snapshot(root, bundle_sha, export_sha, protocol_sha):
    """Preflight all eight completions without loading any prediction arrays.

    Full schedule, normalizer and row/PMF validation remains in report_grid.
    """
    root = Path(root)
    snapshot = {str(Path('prepared') / name): sha(checked_file(root, Path('prepared') / name))
                for name in ('normalizers.json', 'normalizers.npz')}
    for arm in ARMS:
        for seed in SEEDS:
            relative = Path(f'{arm}_{seed}')
            hashes = {name: sha(checked_file(root, relative / name)) for name in FIT_FILES}
            m = read_json(root / relative / 'manifest.json')
            c = read_json(root / relative / 'COMPLETE.json')
            if c != {'manifest_sha256': hashes['manifest.json']}:
                raise ValueError('Fit completion changed')
            required = {'status': 'complete', 'arm': arm, 'seed': seed, 'epochs': 10,
                        'batch_size': 512, 'bundle_sha256': bundle_sha,
                        'export_manifest_sha256': export_sha, 'protocol_sha256': protocol_sha,
                        'normalizers_sha256': snapshot['prepared/normalizers.json']}
            if any(m.get(k) != v for k, v in required.items()):
                raise ValueError('Incomplete or wrong fixed fit')
            if not math.isfinite(m['seconds']) or not 0 <= m['seconds'] <= 600:
                raise ValueError('Fit exceeded original budget')
            if m['outputs_sha256'] != {name: hashes[name] for name in FIT_FILES[2:]}:
                raise ValueError('Fit artifact changed')
            snapshot.update({str(relative / name): digest for name, digest in hashes.items()})
    return snapshot


def stage(receipt_dir, name, started, max_seconds):
    elapsed = time.monotonic() - started
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    value = {'stage': name, 'elapsed_seconds': elapsed,
             'peak_rss_bytes': int(rss if sys.platform == 'darwin' else rss * 1024)}
    with (receipt_dir / 'progress.jsonl').open('a') as f:
        f.write(json.dumps(value, sort_keys=True) + '\n')
        f.flush()
    print(json.dumps(value, sort_keys=True), flush=True)
    if elapsed > max_seconds:
        raise TimeoutError('Recovery stage exceeded budget; outer cgroup enforces hard timeout')


def recover_locked(root, receipt_dir, grid_sha, bundle_sha, export_sha, protocol_sha,
                   make_report, verify_inputs, provenance, max_seconds=1800):
    """Transaction core. Production callbacks only invoke the unchanged reporter.

    Caller holds the exclusive grid lock. All fit paths are read-only. COMPLETE
    is the last operation; a receipt alone never asserts root completion.
    """
    started = time.monotonic()
    root, receipt_dir = Path(root), Path(receipt_dir)
    if not 0 < max_seconds <= 1800:
        raise ValueError('Recovery budget must be at most 1800 seconds')
    for name in ('report.json', 'report.json.partial', 'COMPLETE.json', 'COMPLETE.json.partial', 'grid_manifest.json.partial'):
        if (root / name).exists():
            raise ValueError('Existing reporting/completion artifact requires inspection: ' + name)
    manifest_path = checked_file(root, 'grid_manifest.json')
    original_bytes = manifest_path.read_bytes()
    if hashlib.sha256(original_bytes).hexdigest() != grid_sha:
        raise ValueError('Pre-recovery grid manifest changed')
    grid = json.loads(original_bytes)
    expected = {'status': 'training_complete', 'bundle_sha256': bundle_sha,
                'protocol_sha256': protocol_sha, 'export_manifest_sha256': export_sha,
                'arms': list(ARMS), 'seeds': list(SEEDS)}
    if set(grid) != set(expected) | {'training_seconds'} or any(grid.get(k) != v for k, v in expected.items()):
        raise ValueError('Wrong pre-recovery grid schema/state')
    if not math.isfinite(grid['training_seconds']) or not 0 <= grid['training_seconds'] <= 4800:
        raise ValueError('Original training budget exceeded')
    receipt_dir.mkdir(parents=True, exist_ok=False)
    (receipt_dir / 'pre_recovery_grid_manifest.json').write_bytes(original_bytes)
    receipt = {'schema': 'response-reporting-recovery-v1', 'provenance': provenance,
               'pre_recovery_grid_manifest_sha256': grid_sha,
               'serializer': {'api': 'json.dump', 'sort_keys': True, 'indent': 2,
                              'allow_nan': False, 'ensure_ascii': True, 'suffix': 'LF'},
               'max_seconds': max_seconds, 'hard_timeout_owner': 'parent systemd cgroup',
               'completion_rule': 'Receipt is valid only with matching root COMPLETE.json'}
    promoted_sha = None
    try:
        stage(receipt_dir, 'verify_inputs', started, max_seconds)
        verify_inputs()
        before = fit_snapshot(root, bundle_sha, export_sha, protocol_sha)
        receipt['fit_files_before_sha256'] = before
        atomic_json(receipt_dir / 'recovery_started.json', receipt)
        stage(receipt_dir, 'report_grid_start', started, max_seconds)
        report = make_report()
        stage(receipt_dir, 'report_grid_returned', started, max_seconds)
        atomic_json(root / 'report.json', report)
        del report
        stage(receipt_dir, 'report_json_written', started, max_seconds)
        verify_inputs()
        after = fit_snapshot(root, bundle_sha, export_sha, protocol_sha)
        if before != after or sha(manifest_path) != grid_sha:
            raise ValueError('Immutable inputs changed during report recovery')
        report_sha = sha(root / 'report.json')
        grid.update(status='complete', report_sha256=report_sha)
        # Same schema and bytes as the original runner's successful promotion.
        atomic_json(manifest_path, grid)
        promoted_sha = sha(manifest_path)
        receipt.update(status='prepared_for_root_completion', report_sha256=report_sha,
                       grid_manifest_sha256=promoted_sha, fit_files_after_sha256=after)
        atomic_json(receipt_dir / 'recovery_receipt.json', receipt)
        stage(receipt_dir, 'ready_for_root_complete', started, max_seconds)
        # No fallible reporting/provenance work after the completion marker.
        atomic_json(root / 'COMPLETE.json', {'grid_manifest_sha256': promoted_sha})
    except BaseException as exc:
        # A failure after manifest promotion must not advertise a complete grid.
        # Restore exact original bytes only when this transaction still owns it.
        if promoted_sha is not None and sha(manifest_path) == promoted_sha:
            temporary = manifest_path.with_suffix('.json.rollback')
            temporary.write_bytes(original_bytes)
            os.replace(temporary, manifest_path)
        receipt.update(status='failed', error_type=type(exc).__name__)
        atomic_json(receipt_dir / 'failure_receipt.json', receipt)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('deployment-root', 'export', 'grid', 'receipt-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--grid-manifest-sha256', required=True)
    parser.add_argument('--wrapper-sha256', required=True)
    parser.add_argument('--max-seconds', type=int, default=1800, choices=range(1, 1801))
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'execute': False, 'scope': 'No input reads, imports, fits, or writes',
                          'deployment_sha256': DEPLOYMENT_SHA, 'bundle_sha256': BUNDLE_SHA,
                          'export_manifest_sha256': EXPORT_SHA, 'max_seconds': args.max_seconds}))
        return
    if sha(__file__) != args.wrapper_sha256:
        raise ValueError('Recovery wrapper not pinned')
    paths = [p.resolve() for p in (args.deployment_root, args.export, args.grid, args.receipt_dir)]
    for i, a in enumerate(paths):
        if any(a == b or a in b.parents or b in a.parents for b in paths[i + 1:]):
            raise ValueError('Input/output directories must be disjoint')
    deployment, export, grid, receipts = paths
    source, bundle = verify_deployment(deployment)
    original = import_original(source, bundle)

    def verify_inputs():
        verify_deployment(deployment)
        manifest = verify_export_manifest(export, EXPORT_SHA)
        if manifest.get('protocol_sha256') != PROTOCOL_SHA or manifest.get('polarization_manifest_sha256') != original.PARENT_SHA:
            raise ValueError('Wrong frozen export population/protocol')

    def make_report():
        dataset = original.CompletedExport(export)
        return original.report_grid(grid, dataset, BUNDLE_SHA)

    # flock is released even on OOM/kill; do not use a stale PID sentinel.
    with (grid / '.reporting_recovery.lock').open('a') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        recover_locked(grid, receipts, args.grid_manifest_sha256, BUNDLE_SHA, EXPORT_SHA,
                       PROTOCOL_SHA, make_report, verify_inputs,
                       {'wrapper_sha256': args.wrapper_sha256, 'deployment_manifest_sha256': DEPLOYMENT_SHA,
                        'training_bundle_sha256': BUNDLE_SHA, 'export_manifest_sha256': EXPORT_SHA,
                        'original_source_sha256': read_json(bundle)['files'],
                        'python': sys.version, 'cpu_only': True, 'torch': original.torch.__version__,
                        'numpy': original.np.__version__}, args.max_seconds)


if __name__ == '__main__':
    main()

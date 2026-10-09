"""Parent-scheduled, same-runtime GPU correspondence replay; never trains.

Use an external timeout of 600s. It reads only validation waveform rows, preserves
saved CNN/head batch sizes and runtime flags, and does not loosen CPU replay
tolerances. This module is deliberately independent of the CPU-only auditor,
whose import disables CUDA. No GPU action occurs on import.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time


CONTROLS = ('huber_ce', 'crps_ce', 'tail_crps_ce', 'marginal_crps_ce', 'ranked_bce_ce')
SEEDS = (20261009, 20261010)
LOGIT_ATOL, LOGIT_RTOL = 2e-3, 2e-4
PMF_ATOL, MEAN_ATOL = 2e-4, 2e-3


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def batches(n, batch_size):
    require(n > 0 and batch_size > 0, 'Invalid batch dimensions')
    return [(start, min(start + batch_size, n)) for start in range(0, n, batch_size)]


def difference_metrics(probability, expected, centers):
    import numpy as np
    require(probability.shape == expected.shape and probability.ndim == 2 and
            probability.shape[1] == len(centers), 'Replay PMF shape mismatch')
    # Python max(0., NaN) can keep zero; reject nonfinite batches before
    # reductions so a failed inference can never disappear from the report.
    require(np.isfinite(probability).all() and np.isfinite(expected).all() and np.isfinite(centers).all(),
            'Nonfinite replay or archived PMF')
    require(np.all(probability >= 0) and np.all(expected >= 0) and
            np.allclose(probability.sum(1), 1, atol=2e-6, rtol=0) and
            np.allclose(expected.sum(1), 1, atol=2e-6, rtol=0), 'Invalid replay or archived PMF mass')
    difference = probability - expected
    return float(np.max(np.abs(difference))), float(np.max(np.abs(difference @ centers)))


def identity_checks(run, root):
    manifest = read_json(run / 'artifacts.json')
    require(set(manifest) == {p.name for p in run.iterdir() if p.is_file() and p.name != 'artifacts.json'},
            'Incomplete/unlisted run artifact')
    for name, item in manifest.items():
        require(Path(name).name == name and not (run / name).is_symlink(), 'Unsafe artifact path')
        require((run / name).stat().st_size == item['bytes'] and sha256(run / name) == item['sha256'],
                f'Artifact mismatch: {name}')
    identity = read_json(run / 'identity.json')
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()[:12]
    require(f'_{digest}_' in run.name, 'Run identity digest differs')
    for name, expected in identity['source_sha256'].items():
        require(Path(name).name == name, 'Unsafe source path')
        candidates = [root / 'research/2026-10-09/phase2' / name, root / 'research/2026-10-09' / name]
        found = [p for p in candidates if p.is_file()]
        require(len(found) == 1 and sha256(found[0]) == expected, f'Source mismatch: {name}')
    config = identity['config']
    require(tuple(config['controls']) == CONTROLS and tuple(config['seeds']) == SEEDS and config['epochs'] == 15,
            'Replay only supports the prespecified five-control/two-seed grid')
    require(config['seconds'] in (1, 3, 5), 'Unknown validation horizon')
    return identity, manifest


def configure_runtime(expected):
    # This assignment occurs before importing Torch, creating a CUDA context,
    # or importing the source-pinned feature extraction modules.
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', expected['CUBLAS_WORKSPACE_CONFIG'])
    require(os.environ['CUBLAS_WORKSPACE_CONFIG'] == expected['CUBLAS_WORKSPACE_CONFIG'], 'cuBLAS workspace changed')
    require(os.environ.get('NVIDIA_TF32_OVERRIDE') == expected['NVIDIA_TF32_OVERRIDE'], 'TF32 environment override changed')
    import torch
    require(not torch.cuda.is_initialized(), 'Use a fresh replay process')
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)
    require(torch.cuda.is_available(), 'A parent-scheduled CUDA device is required')
    actual = {'python': platform.python_version(), 'torch': str(torch.__version__),
        'cuda_build': torch.version.cuda, 'cudnn': torch.backends.cudnn.version(),
        'device': 'cuda', 'device_name': torch.cuda.get_device_name(0),
        'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
        'cudnn_deterministic': torch.backends.cudnn.deterministic,
        'cudnn_benchmark': torch.backends.cudnn.benchmark,
        'cudnn_allow_tf32': torch.backends.cudnn.allow_tf32,
        'matmul_allow_tf32': torch.backends.cuda.matmul.allow_tf32,
        'CUBLAS_WORKSPACE_CONFIG': os.environ['CUBLAS_WORKSPACE_CONFIG'],
        'NVIDIA_TF32_OVERRIDE': os.environ.get('NVIDIA_TF32_OVERRIDE')}
    require(actual == expected, f'Runtime differs from training: actual={actual}, expected={expected}')
    return actual


def make_head():
    import torch
    from torch import nn

    class Head(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(nn.Linear(291, 128), nn.SiLU(), nn.Dropout(.1),
                nn.Linear(128, 64), nn.SiLU(), nn.Linear(64, 66))

        def forward(self, x, original):
            return original + 5 * torch.tanh(self.net(x) / 5)

    return Head()


def replay_run(run, root, data_root, inventory_path, identity, manifest):
    import numpy as np
    import torch
    import h5py
    import pandas as pd
    sys.path.insert(0, str(root / 'research/2026-10-09/phase2'))
    sys.path.insert(0, str(root / 'research/2026-10-09'))
    import instrument_residual as feature_source
    started = time.monotonic()
    config, inputs = identity['config'], read_json(run / 'input_identities.json')
    seconds = config['seconds']
    reference_path = root / f'results/2026-10-09/validation_{seconds}s.npz'
    require(sha256(reference_path) == inputs['validation_reference_sha256'], 'Reference hash mismatch')
    require(sha256(root / 'val_metadata.csv') == inputs['metadata_sha256']['val'], 'Validation metadata changed')
    require(sha256(inventory_path) == inputs['inventory_sha256'], 'Inventory changed')
    with np.load(reference_path, allow_pickle=False) as loaded:
        ref = {key: loaded[key] for key in ('targets', 'event_ids', 'trace_names', 'centers', 'logits')}
    frame = pd.read_csv(root / 'val_metadata.csv', usecols=feature_source.METADATA_COLUMNS,
        dtype={c: str for c in feature_source.STRING_COLUMNS}, keep_default_na=False)
    feature_source.assert_reference_alignment(frame, ref)
    n = len(frame)
    cache_names = {1: 'Instance_windows_1s.hdf5', 3: 'Instance_windows_full.hdf5', 5: 'Instance_windows_5s.hdf5'}
    checkpoint_names = {1: 'best_model_huberandcross1s075fixed.pth',
        3: 'best_model_huberandcross3sfixed.pth', 5: 'best_model_huberandcross5s075fixed.pth'}
    cache_path = data_root / cache_names[seconds]
    require(cache_path.name == Path(inputs['cache']['path']).name and cache_path.stat().st_size == inputs['cache']['bytes'],
            'Validation cache identity differs')
    checkpoint_path = root / 'bayesianprior/data' / checkpoint_names[seconds]
    require(sha256(checkpoint_path) == inputs['checkpoint_sha256'], 'Backbone changed')
    backbone = feature_source.EarthquakeCNN().cuda()
    backbone.load_state_dict(torch.load(checkpoint_path, map_location='cpu', weights_only=True)['model_state_dict'])
    backbone.eval()
    instrument, _, _, instrument_names, _ = feature_source.instrument_arrays(frame, feature_source.Inventory.from_archive(inventory_path))
    feature_parts, logit_parts = [], []
    torch.cuda.reset_peak_memory_stats()
    with h5py.File(cache_path, 'r') as cache, torch.inference_mode():
        require(cache['val/waveforms'].shape == (n, 3, seconds * 100), 'Wrong validation waveform dimensions')
        require(np.array_equal(cache['val/targets'][:].astype(np.float32), frame.source_magnitude.to_numpy(np.float32)),
                'Validation target alignment differs')
        for start, end in batches(n, config['extract_batch_size']):
            # Fancy row indexing matches producer extraction, including final
            # batch length; no padded CNN batches and no sample-only batching.
            x = torch.from_numpy(cache['val/waveforms'][np.arange(start, end)]).cuda()
            hidden = backbone.classifier[:-1](backbone.global_pool(backbone.features(x)))
            logits = backbone.classifier[-1](hidden)
            prefix = feature_source.prefix_features(x)
            z = logits.cpu().numpy()
            feature_parts.append(np.concatenate([z - z.mean(1, keepdims=True), hidden.cpu().numpy(),
                prefix.cpu().numpy(), instrument[start:end], np.zeros((end - start, 12), np.float32)], axis=1).astype(np.float32))
            logit_parts.append(z)
    original_np, feature_np = np.concatenate(logit_parts), np.concatenate(feature_parts)
    del feature_parts, logit_parts, backbone
    raw_difference = float(np.max(np.abs(original_np - ref['logits'])))
    raw_pass = bool(np.allclose(original_np, ref['logits'], atol=LOGIT_ATOL, rtol=LOGIT_RTOL))
    results, failures = {}, []
    if not raw_pass:
        failures.append('frozen_backbone_reference_tolerance')
    original = torch.from_numpy(original_np).cuda()
    for control in CONTROLS:
        with np.load(run / f'{control}_probabilities.npz', allow_pickle=False) as pfile:
            for field in ('targets', 'event_ids', 'trace_names', 'centers'):
                require(np.array_equal(pfile[field], ref[field]), 'Saved probability alignment mismatch')
            for seed in SEEDS:
                key = f'{control}_seed{seed}'
                checkpoint = torch.load(run / f'{key}.pth', map_location='cpu', weights_only=True)
                require(checkpoint['config'] == config and checkpoint['instrument_names'] == instrument_names,
                        'Checkpoint configuration/schema mismatch')
                require(np.array_equal(checkpoint['feature_mask'].numpy(), np.r_[np.ones(279), np.zeros(12)]),
                        'Native-mask assumption differs')
                require(np.isfinite(checkpoint['feature_mean'].numpy()).all() and
                        np.isfinite(checkpoint['feature_std'].numpy()).all() and (checkpoint['feature_std'].numpy() > 0).all(),
                        'Invalid checkpoint normalizer')
                # Identical NumPy float32 centering, clipping and post-normalizer
                # zero mask. Unused finite native features cannot affect output.
                normalized = np.clip((feature_np - checkpoint['feature_mean'].numpy()) /
                                     checkpoint['feature_std'].numpy(), -15, 15) * checkpoint['feature_mask'].numpy()
                features = torch.from_numpy(normalized).cuda()
                model = make_head().cuda(); model.load_state_dict(checkpoint['model'], strict=True); model.eval()
                expected = pfile[f'seed{seed}']
                max_p, max_mean = 0., 0.
                with torch.inference_mode():
                    for start, end in batches(n, config['batch_size']):
                        p = model(features[start:end], original[start:end]).double().softmax(1).cpu().numpy()
                        batch_p, batch_mean = difference_metrics(p, expected[start:end], ref['centers'])
                        max_p = max(max_p, batch_p)
                        max_mean = max(max_mean, batch_mean)
                passed = max_p <= PMF_ATOL and max_mean <= MEAN_ATOL
                if not passed:
                    failures.append(key)
                results[key] = dict(pass_tolerance=passed, max_abs_probability=max_p, max_abs_mean=max_mean,
                    checkpoint_sha256=manifest[f'{key}.pth']['sha256'])
                del model, features
    torch.cuda.synchronize()
    return {'status': 'PASS' if not failures else 'FAIL', 'run': str(run.resolve()), 'seconds': seconds,
        'validation_records': n, 'models': results, 'failed_checks': failures,
        'raw_backbone_max_abs_logit': raw_difference, 'raw_backbone_pass': raw_pass,
        'artifact_manifest_sha256': sha256(run / 'artifacts.json'),
        'cnn_batch_size': config['extract_batch_size'], 'head_batch_size': config['batch_size'],
        'peak_gpu_bytes': torch.cuda.max_memory_allocated(), 'wall_seconds': time.monotonic() - started,
        'limits': 'Full validation correspondence replay reuses pinned feature functions; no TEST or training waveforms read.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, nargs='+', required=True)
    for name in ('source-root', 'data-root', 'inventory', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(len(args.runs) <= 3 and len(set(args.runs)) == len(args.runs), 'At most three distinct horizons')
    require(not args.output.exists(), 'Refuse to overwrite replay evidence')
    require(all(run.resolve() not in args.output.resolve().parents for run in args.runs), 'Output must be outside original run')
    identities = [identity_checks(run, args.source_root) for run in args.runs]
    require(len({identity['config']['seconds'] for identity, _ in identities}) == len(identities), 'Duplicate horizon')
    require(all(identity['config']['runtime'] == identities[0][0]['config']['runtime'] for identity, _ in identities),
            'Horizons do not share runtime identity')
    runtime = configure_runtime(identities[0][0]['config']['runtime'])
    results = []
    # Normal numeric tolerance failures are retained for all requested horizons;
    # provenance/alignment failures abort immediately instead of replaying data.
    for run, (identity, manifest) in zip(args.runs, identities):
        result = replay_run(run, args.source_root, args.data_root, args.inventory, identity, manifest)
        results.append(result)
        print(json.dumps({key: result[key] for key in ('status', 'seconds', 'validation_records', 'wall_seconds')}), flush=True)
    report = {'status': 'PASS' if all(x['status'] == 'PASS' for x in results) else 'FAIL',
        'runtime': runtime, 'source_sha256': sha256(Path(__file__)), 'horizons': results,
        'tolerances': {'logit_atol': LOGIT_ATOL, 'logit_rtol': LOGIT_RTOL, 'probability_atol': PMF_ATOL, 'mean_atol': MEAN_ATOL}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False); stream.write('\n')
    if report['status'] != 'PASS':
        raise SystemExit(2)


if __name__ == '__main__':
    main()

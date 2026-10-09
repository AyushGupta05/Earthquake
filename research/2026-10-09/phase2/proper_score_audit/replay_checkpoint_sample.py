"""Bounded CPU correspondence check: frozen validation inputs -> saved head PMFs.

This supplements independent audit_scores metrics. It deliberately reuses the
source-pinned feature extraction functions, so it is a replay check, not a second
independent implementation of the feature pipeline. No TRAIN/TEST waveforms read.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch
from torch import nn

import audit_scores as audit


def sample_rows(targets, budget):
    audit.require(2 <= budget <= 128, 'Replay requires 2..128 validation samples')
    count = min(budget, len(targets))
    uniform = np.linspace(0, len(targets) - 1, (count + 1) // 2, dtype=int)
    tail = np.argsort(-targets, kind='stable')[:count // 2]
    return np.unique(np.r_[uniform, tail])


class SavedHead(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(291, 128), nn.SiLU(), nn.Dropout(.1),
                                 nn.Linear(128, 64), nn.SiLU(), nn.Linear(64, 66))

    def forward(self, features, original):
        return original + 5 * torch.tanh(self.net(features) / 5)


def replay(run, root, data_root, inventory_path, samples):
    started = time.monotonic()
    torch.set_num_threads(1)
    _, identity = audit.verify_manifest(run)
    audit.verify_sources(identity, root)
    config = identity['config']
    seconds = config['seconds']
    audit.require(seconds in (1, 3, 5), 'Unknown horizon')
    inputs = audit.load_json(run / 'input_identities.json')
    audit.require(audit.sha256(inventory_path) == inputs['inventory_sha256'], 'Inventory hash mismatch')
    metadata_path = root / 'val_metadata.csv'
    audit.require(audit.sha256(metadata_path) == inputs['metadata_sha256']['val'], 'Validation metadata hash mismatch')
    reference_path = root / f'results/2026-10-09/validation_{seconds}s.npz'
    audit.require(audit.sha256(reference_path) == inputs['validation_reference_sha256'], 'Reference hash mismatch')
    reference = audit.load_npz(reference_path)
    indices = sample_rows(reference['targets'], samples)
    sys.path.insert(0, str(root / 'research/2026-10-09/phase2'))
    sys.path.insert(0, str(root / 'research/2026-10-09'))
    import instrument_residual as feature_source
    import h5py
    import pandas as pd
    frame = pd.read_csv(metadata_path, usecols=feature_source.METADATA_COLUMNS,
                       dtype={c: str for c in feature_source.STRING_COLUMNS}, keep_default_na=False)
    feature_source.assert_reference_alignment(frame, reference)
    cache_names = {1: 'Instance_windows_1s.hdf5', 3: 'Instance_windows_full.hdf5', 5: 'Instance_windows_5s.hdf5'}
    checkpoint_names = {1: 'best_model_huberandcross1s075fixed.pth',
        3: 'best_model_huberandcross3sfixed.pth', 5: 'best_model_huberandcross5s075fixed.pth'}
    cache_path = data_root / cache_names[seconds]
    audit.require(cache_path.name == Path(inputs['cache']['path']).name, 'Cache identity name mismatch')
    audit.require(cache_path.stat().st_size == inputs['cache']['bytes'], 'Cache byte count mismatch')
    checkpoint_path = root / 'bayesianprior/data' / checkpoint_names[seconds]
    audit.require(audit.sha256(checkpoint_path) == inputs['checkpoint_sha256'], 'Backbone hash mismatch')
    backbone = feature_source.EarthquakeCNN()
    backbone.load_state_dict(torch.load(checkpoint_path, map_location='cpu', weights_only=True)['model_state_dict'])
    backbone.eval()
    with h5py.File(cache_path, 'r') as cache:
        audit.require(cache['val/waveforms'].shape == (len(frame), 3, seconds * 100), 'Validation cache shape mismatch')
        audit.require(np.array_equal(cache['val/targets'][indices].astype(np.float32),
                                     frame.iloc[indices].source_magnitude.to_numpy(np.float32)), 'Cached target alignment mismatch')
        x = torch.from_numpy(cache['val/waveforms'][indices])
    inventory = feature_source.Inventory.from_archive(inventory_path)
    instrument, _, _, names, _ = feature_source.instrument_arrays(frame.iloc[indices], inventory)
    with torch.inference_mode():
        hidden = backbone.classifier[:-1](backbone.global_pool(backbone.features(x)))
        original = backbone.classifier[-1](hidden)
        prefix = feature_source.prefix_features(x)
    # Native slots are inactive after normalization. Finite zeros are sufficient
    # here and avoid computing unused native-amplitude features for the replay.
    features = np.concatenate([original.numpy() - original.numpy().mean(1, keepdims=True),
        hidden.numpy(), prefix.numpy(), instrument, np.zeros((len(indices), 12), dtype=np.float32)], axis=1).astype(np.float32)
    raw_difference = float(np.max(np.abs(original.numpy() - reference['logits'][indices])))
    audit.require(np.allclose(original.numpy(), reference['logits'][indices], atol=2e-3, rtol=2e-4),
                  'CPU backbone differs beyond existing reference tolerance')
    result = {}
    for control in audit.CONTROLS:
        saved = audit.load_npz(run / f'{control}_probabilities.npz')
        for seed in audit.SEEDS:
            key = f'{control}_seed{seed}'
            checkpoint = torch.load(run / f'{key}.pth', map_location='cpu', weights_only=True)
            audit.require(checkpoint['instrument_names'] == names, 'Instrument feature names differ')
            audit.require(np.array_equal(checkpoint['feature_mask'].numpy(), np.r_[np.ones(279), np.zeros(12)]), 'Replay mask changed')
            normalized = np.clip((features - checkpoint['feature_mean'].numpy()) /
                                 checkpoint['feature_std'].numpy(), -15, 15) * checkpoint['feature_mask'].numpy()
            model = SavedHead(); model.load_state_dict(checkpoint['model'], strict=True); model.eval()
            with torch.inference_mode():
                p = model(torch.from_numpy(normalized), original).double().softmax(1).numpy()
            expected = saved[f'seed{seed}'][indices]
            probability_difference = float(np.max(np.abs(p - expected)))
            mean_difference = float(np.max(np.abs((p - expected) @ reference['centers'])))
            # CPU versus CUDA extraction/matmul is not a bitwise replay. These
            # prespecified diagnostic tolerances are not tuned to a run outcome.
            audit.require(probability_difference <= 2e-4 and mean_difference <= 2e-3,
                          f'Saved checkpoint/PMF sample disagreement: {key}')
            result[key] = {'max_abs_probability': probability_difference, 'max_abs_mean': mean_difference}
    return {'status': 'PASS', 'run': str(run), 'seconds': seconds, 'samples': len(indices),
        'validation_row_indices': indices.tolist(), 'validation_trace_names': reference['trace_names'][indices].tolist(),
        'raw_backbone_max_abs_logit': raw_difference, 'models': result,
        'replay_source_sha256': audit.sha256(Path(__file__)), 'wall_seconds': time.monotonic() - started,
        'scope': 'CPU sample inference, pinned feature functions reused; no exhaustive model inference or raw-data reprocessing.',
        'tolerances': {'probability': 2e-4, 'mean': 2e-3, 'raw_logits_atol': 2e-3, 'raw_logits_rtol': 2e-4}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('run', 'source-root', 'data-root', 'inventory', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--samples', type=int, default=32)
    args = parser.parse_args()
    audit.require(not args.output.exists(), 'Refuse to replace replay report')
    audit.require(args.run.resolve() not in args.output.resolve().parents, 'Output cannot modify immutable run')
    result = replay(args.run, args.source_root, args.data_root, args.inventory, args.samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'seconds', 'samples', 'wall_seconds')}))


if __name__ == '__main__':
    main()

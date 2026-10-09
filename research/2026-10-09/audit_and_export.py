"""Audit INSTANCE identities and export duration-correct validation logits.

Run from the repository root on the existing host. Never accesses test waveforms.
Cached waveform identity is sampled against the original traces; targets are checked
exhaustively. Metadata statistics include test support, not test predictions.
"""
import argparse
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import torch
from torch import nn


class EarthquakeCNN(nn.Module):
    """Exact existing checkpoint architecture, without data-loader import effects."""
    def __init__(self):
        super().__init__()
        channels = [3, 16, 32, 64, 128, 256, 512]
        self.features = nn.Sequential(*[
            nn.Sequential(nn.Conv1d(a, b, 5, padding=2), nn.ReLU(), nn.MaxPool1d(2))
            for a, b in zip(channels[:-1], channels[1:])
        ])
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.classifier = nn.Sequential(
            nn.Flatten(), nn.Dropout(.5), nn.Linear(512, 512), nn.ReLU(),
            nn.Dropout(.5), nn.Linear(512, 128), nn.ReLU(), nn.Dropout(.5),
            nn.Linear(128, 66),
        )

    def forward(self, x):
        return self.classifier(self.global_pool(self.features(x)))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audit_metadata(root):
    frames, summary = {}, {}
    columns = ['source_id', 'source_origin_time', 'source_magnitude',
               'source_magnitude_type', 'trace_name', 'trace_P_arrival_sample']
    for split, filename in [('train', 'train_full_metadata.csv'),
                            ('val', 'val_metadata.csv'), ('test', 'test_metadata.csv')]:
        d = pd.read_csv(root / filename, usecols=columns)
        if d[columns].isna().any().any() or d.trace_name.duplicated().any():
            raise ValueError(f'Invalid metadata identity: {split}')
        if d.groupby('source_id').source_magnitude.nunique().max() != 1:
            raise ValueError(f'Conflicting event magnitudes: {split}')
        e = d.drop_duplicates('source_id')
        frames[split] = d
        summary[split] = {
            'records': len(d), 'events': len(e),
            'magnitude_min': float(d.source_magnitude.min()),
            'magnitude_max': float(d.source_magnitude.max()),
            'event_counts_above': {str(t): int((e.source_magnitude >= t).sum()) for t in [4, 5, 6]},
            'record_counts_above': {str(t): int((d.source_magnitude >= t).sum()) for t in [4, 5, 6]},
            'magnitude_scales': d.source_magnitude_type.value_counts().to_dict(),
            'time_min': d.source_origin_time.min(), 'time_max': d.source_origin_time.max(),
            'metadata_sha256': sha256(root / filename),
        }
    summary['overlap'] = {}
    for a, b in [('train', 'val'), ('train', 'test'), ('val', 'test')]:
        counts = {k: len(set(frames[a][k]) & set(frames[b][k])) for k in ['source_id', 'trace_name']}
        summary['overlap'][f'{a}_{b}'] = counts
        if any(counts.values()):
            raise ValueError(f'Split leakage: {a}, {b}')
    return frames, summary


def require_checkpoint_preprocessing(transforms):
    """The three named checkpoints were trained with global standardization.

    Raw-count caches can exist in this repository, but are incompatible with
    these weights. Identity alone is insufficient to permit inference.
    """
    expected = {'training_global_standardization'}
    if transforms != expected:
        raise ValueError(f'Checkpoint requires {expected}; cache uses {transforms}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path('/data'))
    parser.add_argument('--output', type=Path, default=Path('results/2026-10-09'))
    parser.add_argument('--batch-size', type=int, default=256)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    frames, audit = audit_metadata(root)
    val = frames['val']
    centers = (np.arange(66, dtype=np.float64) + .5) * .1
    train_bins = np.clip(np.floor(frames['train'].source_magnitude.to_numpy() / .1 + 1e-5).astype(int), 0, 65)
    counts = np.bincount(train_bins, minlength=66)
    # Explicit small pseudocount; does not imply observed high-magnitude evidence.
    prior = (counts + .5) / (counts.sum() + 33)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    mean = torch.tensor(np.load(root / 'train_mean_full.npy'), dtype=torch.float32).reshape(3, 1)
    std = torch.tensor(np.load(root / 'train_std_full.npy'), dtype=torch.float32).reshape(3, 1)
    audit['device'] = str(device)
    audit['normalization_sha256'] = {name: sha256(root / name) for name in ['train_mean_full.npy', 'train_std_full.npy']}
    audit['windows'] = {}
    paths = {1: ('Instance_windows_1s.hdf5', 'best_model_huberandcross1s075fixed.pth'),
             3: ('Instance_windows_full.hdf5', 'best_model_huberandcross3sfixed.pth'),
             5: ('Instance_windows_5s.hdf5', 'best_model_huberandcross5s075fixed.pth')}
    with h5py.File(args.data / 'Instance_events_counts.hdf5', 'r') as raw:
        for seconds, (cache_name, ckpt_name) in paths.items():
            transforms = set()
            with h5py.File(args.data / cache_name, 'r') as cache:
                for split, frame in frames.items():
                    y = cache[f'{split}/targets'][:]
                    if not np.allclose(y, frame.source_magnitude.to_numpy(), atol=1e-6, rtol=0):
                        raise ValueError(f'Cached target ordering mismatch: {seconds}s {split}')
                    waves = cache[f'{split}/waveforms']
                    if waves.shape != (len(frame), 3, seconds * 100):
                        raise ValueError(f'Wrong window: {seconds}s {split}: {waves.shape}')
                    # Deterministic coverage of both common and largest events.
                    idx = np.unique(np.r_[np.linspace(0, len(frame)-1, 12, dtype=int),
                                           frame.source_magnitude.nlargest(12).index.to_numpy()])
                    for i in idx:
                        row = frame.iloc[i]
                        p = int(row.trace_P_arrival_sample)
                        expected = np.asarray(raw['data'][row.trace_name][:, p:p + seconds * 100], dtype=np.float32)
                        normalized = ((torch.from_numpy(expected) - mean) / (std + 1e-8)).numpy()
                        if np.array_equal(waves[i], normalized):
                            transforms.add('training_global_standardization')
                        elif np.array_equal(waves[i], expected):
                            transforms.add('raw_counts')
                        else:
                            raise ValueError(f'Cached waveform identity mismatch: {seconds}s {split} row {i}')
                require_checkpoint_preprocessing(transforms)
                checkpoint_path = root / 'bayesianprior/data' / ckpt_name
                checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
                model = EarthquakeCNN().to(device)
                model.load_state_dict(checkpoint['model_state_dict'], strict=True)
                model.eval()
                logits = []
                with torch.inference_mode():
                    waves = cache['val/waveforms']
                    for start in range(0, len(val), args.batch_size):
                        x = torch.from_numpy(waves[start:start+args.batch_size]).to(device)
                        logits.append(model(x).cpu().numpy())
                logits = np.concatenate(logits)
                if not np.isfinite(logits).all():
                    raise ValueError('Non-finite logits')
                target = val.source_magnitude.to_numpy()
                p = torch.softmax(torch.from_numpy(logits).double(), 1).numpy()
                prediction = p @ centers
                error = np.abs(prediction - target)
                np.savez_compressed(args.output / f'validation_{seconds}s.npz', logits=logits,
                    targets=target, event_ids=val.source_id.to_numpy(dtype=str),
                    trace_names=val.trace_name.to_numpy(dtype=str), centers=centers, train_prior=prior)
                audit['windows'][str(seconds)] = {
                    'cache': cache_name, 'checkpoint': ckpt_name,
                    'preprocessing': next(iter(transforms)),
                    'checkpoint_sha256': sha256(checkpoint_path),
                    'sampled_raw_identity_checks_per_split': 'up to 24',
                    'mae': float(error.mean()), 'm4_mae': float(error[target >= 4].mean()),
                    'checkpoint_val_mae': checkpoint.get('val_mae'),
                    'checkpoint_val_m4_mae': checkpoint.get('val_4.0_mae'),
                }
                print(seconds, 'seconds', audit['windows'][str(seconds)], flush=True)
    (args.output / 'audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    print('Audit and validation exports complete.', flush=True)


if __name__ == '__main__':
    main()

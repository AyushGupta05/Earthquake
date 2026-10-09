"""Matched instrument-feature controls for frozen INSTANCE magnitude residuals.

Only training and exploratory validation are read. Each control has identical
parameter count, initial weights, samples, minibatch order and fixed epochs.
Validation never selects a model, epoch, blend, threshold or hyperparameter.
Sensitivity-normalized counts are an approximation, not response deconvolution.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import platform
import sys
import time

import h5py
import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from instrument_inventory import Inventory, model_features
from feature_residual import prefix_features, population_weights, ResidualDistribution
from audit_and_export import EarthquakeCNN, sha256, require_checkpoint_preprocessing
from distribution_experiment import metrics, median
from frozen_head_pilot import choose_rows
from run_artifacts import create_run

ROOT = Path(__file__).resolve().parents[3]
INVENTORY_SHA256 = '71eccc6304afad15e9c45534ca374b4b4f974c9f93ccfc0f2683616ee6421ef2'
FAMILIES = ('base', 'instrument', 'instrument_native')
METADATA_COLUMNS = [
    'source_id', 'source_magnitude', 'trace_name', 'trace_P_arrival_sample',
    'trace_start_time', 'station_network_code', 'station_code',
    'station_location_code', 'station_channels', 'station_latitude_deg',
    'station_longitude_deg', 'station_elevation_m', 'station_vs_30_mps',
    'station_vs_30_detail',
]
STRING_COLUMNS = [c for c in METADATA_COLUMNS if c not in (
    'source_magnitude', 'trace_P_arrival_sample', 'station_latitude_deg',
    'station_longitude_deg', 'station_elevation_m', 'station_vs_30_mps')]
NATIVE_FEATURE_NAMES = [f'native_log10_{summary}_{component}'
                        for summary in ('rms', 'peak', 'mean_abs', 'energy_seconds')
                        for component in 'ENZ']


def validate_metadata(frame, split):
    for column in ('source_id', 'trace_name', 'trace_start_time'):
        if frame[column].isna().any() or frame[column].astype(str).eq('').any():
            raise ValueError(f'{split}: missing {column}')
    if frame.trace_name.duplicated().any():
        raise ValueError(f'{split}: duplicate trace identities')
    if not np.isfinite(frame.source_magnitude.to_numpy(float)).all():
        raise ValueError(f'{split}: nonfinite labels')
    if frame.groupby('source_id').source_magnitude.nunique().max() != 1:
        raise ValueError(f'{split}: conflicting event labels')
    picks = frame.trace_P_arrival_sample.to_numpy(float)
    if not np.isfinite(picks).all() or (picks < 0).any() or not np.equal(picks, np.floor(picks)).all():
        raise ValueError(f'{split}: invalid benchmark P sample')


def assert_reference_alignment(frame, reference):
    """Reject reordered rows even when their event labels happen to agree."""
    for key, column in [('trace_names', 'trace_name'), ('event_ids', 'source_id')]:
        expected = frame[column].to_numpy(dtype=str)
        if key not in reference or not np.array_equal(reference[key].astype(str), expected):
            raise ValueError(f'Validation {key} order differs from audited reference')
    if not np.array_equal(reference['targets'], frame.source_magnitude.to_numpy(float)):
        raise ValueError('Validation target order differs from audited reference')
    centers = (np.arange(66, dtype=np.float64) + .5) * .1
    if not np.array_equal(reference['centers'], centers):
        raise ValueError('Magnitude-bin centers differ from audited reference')
    if reference['logits'].shape != (len(frame), 66) or not np.isfinite(reference['logits']).all():
        raise ValueError('Invalid audited reference logits')


def assert_cache_alignment(group, frame, seconds):
    expected = frame.source_magnitude.to_numpy(dtype=np.float32)
    actual = np.asarray(group['targets'][:])
    if actual.shape != expected.shape or not np.array_equal(actual.astype(np.float32), expected):
        raise ValueError('Cache target order differs from metadata')
    if group['waveforms'].shape != (len(frame), 3, seconds * 100):
        raise ValueError('Cache does not contain the exact requested duration/row count')


def sample_rows(frame, max_per_event):
    if max_per_event < 0:
        raise ValueError('max_per_event must be nonnegative')
    if max_per_event == 0:
        return np.arange(len(frame), dtype=np.int64)
    selected = choose_rows(frame, max_per_event=max_per_event)
    # Retain all rare-event recordings; the inverse weights undo this imbalance.
    return np.union1d(selected, np.flatnonzero(frame.source_magnitude.to_numpy() >= 4))


def instrument_arrays(frame, inventory):
    """Order is exactly the supplied frame order; no merge or sorting occurs."""
    columns = list(frame.columns)
    features, gain, usable, names = [], [], [], None
    statuses, repaired = Counter(), 0
    for values in frame.itertuples(index=False, name=None):
        row = dict(zip(columns, values))
        joined = inventory.join(row)
        allowed = model_features(joined)
        current_names = list(allowed)
        if names is None:
            names = current_names
        if names != current_names:
            raise ValueError('Instrument feature schema changed between rows')
        features.append(list(allowed.values()))
        response = [joined['channels'][component] for component in 'ENZ']
        valid = [r['status'] == 'matched' for r in response]
        gain.append([r['sensitivity'] if ok else 1. for r, ok in zip(response, valid)])
        usable.append(valid)
        statuses.update(r['status'] for r in response)
        repaired += int(joined['location_numeric_encoding_repaired'])
    if not len(frame):
        raise ValueError('Cannot build features for an empty split')
    array = np.asarray(features, dtype=np.float32)
    if array.shape[1] != 34 or not np.isfinite(array).all():
        raise ValueError('Expected 34 finite allowed instrument/site features')
    report = {'records': len(frame), 'channel_status': dict(statuses),
              'complete_records': int(np.asarray(usable).all(1).sum()),
              'location_numeric_encoding_repaired': repaired}
    return array, np.asarray(gain, dtype=np.float64), np.asarray(usable, dtype=bool), names, report


def native_prefix_features(standardized, mean, std, gains, usable):
    """12 summaries from the observed prefix in approximate native units.

    Invert the exact audited affine scaling, then subtract this prefix's mean.
    Per-component units and response masks live in the 34 instrument features.
    Missing components produce zero summaries; raw counts remain in every model.
    """
    if standardized.ndim != 3 or standardized.shape[1] != 3 or standardized.shape[-1] not in (100, 300, 500):
        raise ValueError('Expected B x 3 x exact 1/3/5-second prefix at 100 Hz')
    if gains.shape != standardized.shape[:2] or usable.shape != gains.shape:
        raise ValueError('Gain/mask rows or components do not align with waveforms')
    if not torch.isfinite(standardized).all() or not torch.isfinite(gains).all() or (gains <= 0).any():
        raise ValueError('Invalid waveform values or instrument gains')
    mean = torch.as_tensor(mean, dtype=torch.float32, device=standardized.device).reshape(1, 3, 1)
    std = torch.as_tensor(std, dtype=torch.float32, device=standardized.device).reshape(1, 3, 1)
    if not torch.isfinite(mean).all() or not torch.isfinite(std).all() or (std <= 0).any():
        raise ValueError('Invalid count-normalization constants')
    counts = standardized.double() * (std + 1e-8).double() + mean.double()
    native = counts / gains.double()[..., None]
    native = native - native.mean(-1, keepdim=True)
    amplitude = native.abs()
    summaries = [native.square().mean(-1).sqrt(), amplitude.amax(-1),
                 amplitude.mean(-1), .01 * native.square().sum(-1)]
    mask = usable.to(dtype=torch.bool)
    # float64 avoids overflow during squared-energy computation on bad counts.
    logs = [torch.where(mask, v.clamp_min(1e-30).log10(), torch.zeros_like(v)) for v in summaries]
    result = torch.cat(logs, 1).float()
    if not torch.isfinite(result).all():
        raise ValueError('Nonfinite native-prefix summaries')
    return result


def weighted_normalizer(train, weights):
    weights = np.asarray(weights, dtype=np.float64)
    if train.ndim != 2 or weights.shape != (len(train),) or not np.isfinite(train).all():
        raise ValueError('Invalid normalization input')
    if not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('Normalization requires finite positive population weights')
    w = weights / weights.sum()
    mean = np.sum(train.astype(np.float64) * w[:, None], axis=0)
    variance = np.sum((train.astype(np.float64) - mean)**2 * w[:, None], axis=0)
    return mean.astype(np.float32), np.maximum(np.sqrt(variance), 1e-5).astype(np.float32)


def design_inputs(data):
    arrays = []
    for split in ('train', 'val'):
        logits = data[split + '_logits']
        base = np.concatenate([logits - logits.mean(1, keepdims=True),
                               data[split + '_hidden'], data[split + '_prefix']], axis=1)
        arrays.append(np.concatenate([base, data[split + '_instrument'], data[split + '_native']], axis=1).astype(np.float32))
    base_dim = arrays[0].shape[1] - 34 - len(NATIVE_FEATURE_NAMES)
    mean, std = weighted_normalizer(arrays[0], data['weights'])
    if any(not np.isfinite(a).all() or a.shape[1] != len(mean) for a in arrays):
        raise ValueError('Nonfinite/misaligned feature arrays')
    normalized = [np.clip((a - mean) / std, -15, 15) for a in arrays]
    masks = {family: np.zeros(len(mean), dtype=np.float32) for family in FAMILIES}
    for mask in masks.values():
        mask[:base_dim] = 1
    masks['instrument'][base_dim:base_dim + 34] = 1
    masks['instrument_native'][base_dim:] = 1
    return normalized, mean, std, masks, base_dim


def verify_raw_samples(group, raw, frame, seconds, mean, std):
    indices = np.unique(np.r_[np.linspace(0, len(frame)-1, min(64, len(frame)), dtype=int),
                              frame.source_magnitude.nlargest(min(16, len(frame))).index.to_numpy()])
    for index in indices:
        row = frame.iloc[index]
        start = int(row.trace_P_arrival_sample)
        prefix = np.asarray(raw['data'][row.trace_name][:, start:start + seconds*100], dtype=np.float32)
        expected = ((torch.from_numpy(prefix) - mean) / (std + 1e-8)).numpy()
        if not np.array_equal(group['waveforms'][index], expected):
            raise ValueError(f'Raw prefix identity mismatch: row {index}, {row.trace_name}')
    return indices.tolist()


def extract(args, device):
    root, data_path = Path(args.root), Path(args.data)
    audit_path = root / 'results/2026-10-09/audit.json'
    audit = json.loads(audit_path.read_text())
    info = audit['windows'][str(args.seconds)]
    require_checkpoint_preprocessing({info['preprocessing']})
    identities = {'audit_sha256': sha256(audit_path), 'inventory_sha256': sha256(args.inventory),
                  'metadata_sha256': {}, 'normalization_sha256': {}}
    if identities['inventory_sha256'] != args.inventory_sha256:
        raise ValueError('Instrument inventory differs from explicitly pinned archive')
    frames = {}
    for split, name in [('train', 'train_full_metadata.csv'), ('val', 'val_metadata.csv')]:
        path = root / name
        digest = sha256(path)
        if digest != audit[split]['metadata_sha256']:
            raise ValueError(f'{split}: metadata changed since duration audit')
        identities['metadata_sha256'][split] = digest
        frame = pd.read_csv(path, usecols=METADATA_COLUMNS,
                            dtype={c: str for c in STRING_COLUMNS}, keep_default_na=False)
        validate_metadata(frame, split)
        frames[split] = frame
    if set(frames['train'].source_id) & set(frames['val'].source_id):
        raise ValueError('Training/validation event overlap')
    if set(frames['train'].trace_name) & set(frames['val'].trace_name):
        raise ValueError('Training/validation trace overlap')
    reference_path = root / f'results/2026-10-09/validation_{args.seconds}s.npz'
    with np.load(reference_path, allow_pickle=False) as loaded:
        reference = {key: loaded[key] for key in ('logits', 'targets', 'event_ids', 'trace_names', 'centers')}
    assert_reference_alignment(frames['val'], reference)
    identities['validation_reference_sha256'] = sha256(reference_path)
    normalization = []
    for name in ('train_mean_full.npy', 'train_std_full.npy'):
        digest = sha256(root / name)
        if digest != audit['normalization_sha256'][name]:
            raise ValueError('Count normalization changed since audit')
        identities['normalization_sha256'][name] = digest
        normalization.append(torch.tensor(np.load(root / name), dtype=torch.float32).reshape(3, 1))
    mean, std = normalization
    checkpoint_path = root / 'bayesianprior/data' / info['checkpoint']
    identities['checkpoint_sha256'] = sha256(checkpoint_path)
    if identities['checkpoint_sha256'] != info['checkpoint_sha256']:
        raise ValueError('Checkpoint changed since audit')
    model = EarthquakeCNN().to(device)
    model.load_state_dict(torch.load(checkpoint_path, map_location='cpu', weights_only=True)['model_state_dict'], strict=True)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    inventory = Inventory.from_archive(args.inventory)
    selected = sample_rows(frames['train'], args.max_per_event)
    data, alignment, schema = {}, {}, None
    cache_path = data_path / info['cache']
    stat = cache_path.stat()
    identities['cache'] = {'path': str(cache_path), 'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
                           'waveform_identity_scope': 'sampled raw checks; exhaustive targets and validation reference'}
    with h5py.File(cache_path, 'r') as cache, h5py.File(data_path / 'Instance_events_counts.hdf5', 'r') as raw:
        for split, rows in [('train', selected), ('val', np.arange(len(frames['val'])))]:
            frame = frames[split]
            assert_cache_alignment(cache[split], frame, args.seconds)
            raw_rows = verify_raw_samples(cache[split], raw, frame, args.seconds, mean, std)
            inst, gains, valid, names, report = instrument_arrays(frame.iloc[rows], inventory)
            if schema is not None and schema != names:
                raise ValueError('Training/validation instrument schemas differ')
            schema = names
            hidden, prefixes, native, logits = [], [], [], []
            with torch.inference_mode():
                for start in range(0, len(rows), args.extract_batch_size):
                    stop = start + args.extract_batch_size
                    indices = rows[start:stop]
                    x = torch.from_numpy(cache[f'{split}/waveforms'][indices]).to(device)
                    z = model.classifier[:-1](model.global_pool(model.features(x)))
                    hidden.append(z.cpu().numpy())
                    prefixes.append(prefix_features(x).cpu().numpy())
                    native.append(native_prefix_features(x, mean, std,
                        torch.as_tensor(gains[start:stop], device=device),
                        torch.as_tensor(valid[start:stop], device=device)).cpu().numpy())
                    logits.append(model.classifier[-1](z).cpu().numpy())
            data.update({split + '_hidden': np.concatenate(hidden), split + '_prefix': np.concatenate(prefixes),
                         split + '_native': np.concatenate(native), split + '_instrument': inst,
                         split + '_logits': np.concatenate(logits),
                         split + '_y': frame.source_magnitude.to_numpy(dtype=np.float32)[rows],
                         split + '_ids': frame.source_id.to_numpy(dtype=str)[rows],
                         split + '_trace_names': frame.trace_name.to_numpy(dtype=str)[rows]})
            alignment[split] = dict(report, exact_target_rows=len(frame), selected_rows=len(rows), raw_identity_rows=raw_rows)
    if not np.allclose(data['val_logits'], reference['logits'], atol=2e-3, rtol=2e-4):
        raise ValueError('Validation logits disagree with audited reference')
    data.update(weights=population_weights(frames['train'], selected).astype(np.float32),
                train_rows=selected, centers=reference['centers'], val_y=reference['targets'])
    identities['preprocessing'] = info['preprocessing']
    return data, identities, alignment, schema


def fit_one(data, arrays, mask, args, seed, device):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    train_x, val_x = [torch.as_tensor(a * mask, device=device) for a in arrays]
    original = torch.as_tensor(data['train_logits'], device=device)
    val_original = torch.as_tensor(data['val_logits'], device=device)
    y = torch.as_tensor(data['train_y'], device=device)
    weights = torch.as_tensor(data['weights'], device=device)
    centers = torch.as_tensor(data['centers'], dtype=torch.float32, device=device)
    labels = (y / .1 + 1e-5).floor().long().clamp(0, 65)
    original_mean = original.softmax(1) @ centers
    model = ResidualDistribution(train_x.shape[1]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    shuffle = torch.Generator(device='cpu').manual_seed(seed)
    losses = []
    for _ in range(args.epochs):
        model.train()
        order = torch.randperm(len(y), generator=shuffle)
        total = 0.
        for cpu_indices in order.split(args.batch_size):
            indices = cpu_indices.to(device)
            logits = model(train_x[indices], original[indices])
            pred = logits.softmax(1) @ centers
            magnitude = F.huber_loss(pred, y[indices], reduction='none', delta=.5)
            emphasis = 1 + args.beta * (y[indices] - 3.5).clamp_min(0)
            ce = F.cross_entropy(logits, labels[indices], reduction='none')
            anchor = (pred - original_mean[indices]).square()
            loss = (weights[indices] * (emphasis*magnitude + .075*ce + args.anchor*anchor)).mean()
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite training objective')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 5.)
            optimizer.step()
            total += loss.item() * len(indices)
        losses.append(total / len(y))
    model.eval()
    with torch.inference_mode():
        probability = torch.cat([model(val_x[start:start+args.batch_size], val_original[start:start+args.batch_size])
                                  .double().softmax(1).cpu() for start in range(0, len(val_x), args.batch_size)]).numpy()
    return probability, model.cpu().state_dict(), losses


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, choices=(1, 3, 5), required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', default=INVENTORY_SHA256)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--data', type=Path, default=Path('/data'))
    parser.add_argument('--output', type=Path, default=ROOT / 'results/2026-10-09/phase2')
    parser.add_argument('--seeds', type=int, nargs='+', default=[20261009, 20261010])
    parser.add_argument('--epochs', type=int, default=15)
    parser.add_argument('--max-per-event', type=int, default=4)
    parser.add_argument('--batch-size', type=int, default=2048)
    parser.add_argument('--extract-batch-size', type=int, default=256)
    parser.add_argument('--learning-rate', type=float, default=5e-4)
    parser.add_argument('--beta', type=float, default=0.)
    parser.add_argument('--anchor', type=float, default=0.)
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.extract_batch_size) < 1 or args.max_per_event < 0:
        parser.error('epochs and batches must be positive; max-per-event must be nonnegative')
    if len(set(args.seeds)) != len(args.seeds):
        parser.error('Duplicate seeds are not independent replicates')
    if not all(np.isfinite(x) and x >= 0 for x in (args.beta, args.anchor)) or not np.isfinite(args.learning_rate) or args.learning_rate <= 0:
        parser.error('Invalid loss weights or learning rate')
    return args


def main():
    args = parse_args()
    torch.set_num_threads(2)
    device = torch.device(('cuda' if torch.cuda.is_available() else 'cpu') if args.device == 'auto' else args.device)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    config.update(controls=FAMILIES, sampling_seed=20261009,
                  selection='Fixed final epoch; report every control/seed; no validation selection')
    sources = [HERE / name for name in ('instrument_residual.py', 'instrument_inventory.py',
                                       'feature_residual.py', 'run_artifacts.py')]
    sources += [HERE.parent / name for name in ('audit_and_export.py', 'distribution_experiment.py', 'frozen_head_pilot.py')]
    destination = create_run(args.output, f'instrument_residual_{args.seconds}s', config, sources)
    print('RUN_DIRECTORY', destination, flush=True)
    started = time.monotonic()
    data, identities, alignment, instrument_names = extract(args, device)
    arrays, feature_mean, feature_std, masks, base_dim = design_inputs(data)
    centers, y, ids = data['centers'], data['val_y'], data['val_ids']
    raw_probability = torch.from_numpy(data['val_logits']).double().softmax(1).numpy()
    results = {'raw_mean': metrics(y, raw_probability @ centers, ids, raw_probability, centers),
               'raw_median': metrics(y, median(raw_probability, centers), ids, raw_probability, centers)}
    predictions = {'raw_mean': raw_probability @ centers, 'raw_median': median(raw_probability, centers)}
    histories, probabilities = {}, {family: [] for family in FAMILIES}
    for seed in args.seeds:
        for family in FAMILIES:
            name = f'{family}_seed{seed}'
            p, model_state, losses = fit_one(data, arrays, masks[family], args, seed, device)
            probabilities[family].append(p)
            histories[name] = losses
            torch.save({'model': model_state, 'feature_mean': torch.tensor(feature_mean),
                        'feature_std': torch.tensor(feature_std), 'feature_mask': torch.tensor(masks[family]),
                        'config': config, 'seed': seed, 'family': family,
                        'base_dim': base_dim, 'instrument_names': instrument_names,
                        'native_names': NATIVE_FEATURE_NAMES}, destination / f'{name}.pth')
            for decision, prediction in [('mean', p @ centers), ('median', median(p, centers))]:
                key = name + '_' + decision
                predictions[key] = prediction
                results[key] = metrics(y, prediction, ids, p, centers)
            print(name, {k: results[name + '_mean'][k] for k in ('mae', 'medae', 'm4_mae', 'cvar95', 'fp4')}, flush=True)
    for family, values in probabilities.items():
        p = np.mean(values, axis=0)
        np.savez_compressed(destination / f'{family}_probabilities.npz', targets=y, event_ids=ids,
                            trace_names=data['val_trace_names'], centers=centers, mean_probability=p.astype(np.float32),
                            **{f'seed{seed}': value.astype(np.float32) for seed, value in zip(args.seeds, values)})
        for decision, prediction in [('mean', p @ centers), ('median', median(p, centers))]:
            key = family + '_ensemble_' + decision
            predictions[key] = prediction
            results[key] = metrics(y, prediction, ids, p, centers)
    run = dict(config, wall_seconds=time.monotonic()-started, device=str(device),
               torch_version=torch.__version__, python_version=platform.python_version(),
               train_records=len(data['train_y']), train_events=len(np.unique(data['train_ids'])),
               input_dimension=len(feature_mean), validation_status='Reused exploratory validation',
               objective_status='Inverse-sampling-weighted Huber + CE; optional fixed beta/anchor; no calibration guarantee',
               causality_limit='Input-only prefix operations; original INSTANCE whole-record preprocessing remains')
    schema = {'base_dimension': base_dim, 'instrument_names': instrument_names, 'native_names': NATIVE_FEATURE_NAMES,
              'masks': {key: value.tolist() for key, value in masks.items()}}
    for name, value in [('metrics.json', results), ('history.json', histories), ('run.json', run),
                        ('input_identities.json', identities), ('alignment.json', alignment), ('feature_schema.json', schema)]:
        (destination / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    np.savez_compressed(destination / 'predictions.npz', targets=y, event_ids=ids,
                        trace_names=data['val_trace_names'], **predictions)
    np.savez_compressed(destination / 'training_rows.npz', row_index=data['train_rows'], event_ids=data['train_ids'],
                        trace_names=data['train_trace_names'], weights=data['weights'])
    print('COMPLETE', destination, flush=True)


if __name__ == '__main__':
    main()

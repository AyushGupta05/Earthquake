"""TRAIN-only future-growth auxiliaries on the matched full-static residual head.

Each duration is independent. Inference receives the same prefix-derived
features and frozen logits as instrument_residual, never Y or future growth.
This is an established multitask/conditional-density experiment, not a novelty
claim. See INSTRUMENT_GROWTH.md for the fixed protocol and limitations.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instrument_residual as baseline
from feature_residual import ResidualDistribution
from future_growth import SIGMA_CEILING, SIGMA_FLOOR, hurdle_log_prob
from train_future_growth import META_COLUMNS, array_digest, file_stat, load_targets
from run_artifacts import create_run
from audit_and_export import sha256
from distribution_experiment import metrics, median

CONTROLS = ('supervised', 'growth_mse', 'unconditional_nll', 'conditional_nll', 'conditional_detached')
INPUT_DIM = 291


class InstrumentGrowthModel(nn.Module):
    def __init__(self, n_features=INPUT_DIM):
        super().__init__()
        if n_features != INPUT_DIM:
            raise ValueError('Require the exact 291-column instrument residual design')
        self.magnitude = ResidualDistribution(n_features)
        # Construction is on CPU. Do not consume the baseline's post-init RNG:
        # its next use is dropout, which must match instrument_residual.fit_one.
        with torch.random.fork_rng(devices=[]):
            self.growth_head = nn.Sequential(nn.Linear(65, 64), nn.SiLU(), nn.Linear(64, 4))

    def forward(self, features, original_logits):
        return self.magnitude(features, original_logits)

    def forward_with_state(self, features, original_logits):
        state = self.magnitude.net[:-1](features)
        logits = original_logits + 5 * torch.tanh(self.magnitude.net[-1](state) / 5)
        return logits, state

    def growth_parameters(self, state, labels=None):
        if labels is None:
            condition = state.new_zeros((len(state), 1))
        else:
            if labels.shape != (len(state),):
                raise ValueError('One magnitude-bin auxiliary label is required per state')
            condition = ((labels.to(state.dtype) + .5) / 66 - .5)[:, None]
        raw = self.growth_head(torch.cat([state, condition], -1)).float()
        return {'mean': F.softplus(raw[:, 0]), 'zero_logit': raw[:, 1],
                'mu': raw[:, 2].clamp(-20., 10.),
                'sigma': (F.softplus(raw[:, 3]) + SIGMA_FLOOR).clamp_max(SIGMA_CEILING)}


def growth_loss(model, state, labels, weights, growth, valid, control):
    """Unscaled auxiliary mean over ALL sampled rows, missing rows contributing 0."""
    if control not in CONTROLS:
        raise ValueError('Unknown instrument growth control')
    if growth.shape != labels.shape or valid.shape != labels.shape or valid.dtype != torch.bool:
        raise ValueError('Require aligned one-dimensional growth and boolean validity')
    if weights.shape != labels.shape or not torch.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('Require finite positive population weights')
    if not torch.isfinite(growth[valid]).all() or (growth[valid] < 0).any():
        raise ValueError('Observed growth targets must be finite and nonnegative')
    if control == 'supervised':
        return state.new_zeros(())
    h = state.detach() if control == 'conditional_detached' else state
    params = model.growth_parameters(h, labels if control.startswith('conditional') else None)
    target = torch.where(valid, growth, torch.zeros_like(growth))
    loss = (params['mean'] - target).square() if control == 'growth_mse' else -hurdle_log_prob(params, target)
    return (weights * torch.where(valid, loss, torch.zeros_like(loss))).mean()


def instrument_design(data):
    arrays, mean, std, masks, base_dim = baseline.design_inputs(data)
    if base_dim != 245 or any(a.shape[1] != INPUT_DIM for a in arrays):
        raise ValueError('Instrument feature dimensions changed')
    mask = masks['instrument']
    if not np.array_equal(mask, np.r_[np.ones(279), np.zeros(12)].astype(np.float32)):
        raise ValueError('Require all 34 static features and inactive native-amplitude slots')
    return arrays, mean, std, mask, base_dim


def load_aligned_growth(args, data, identities):
    """Reuse the reviewed loader, then verify the exact instrument-selected rows.

    Instrument sampling uses STRING event IDs. Do not resample using the
    independent-backbone runner's inferred/numeric group ordering.
    """
    root = Path(args.root)
    path = root / 'train_full_metadata.csv'
    digest = sha256(path)
    if digest != identities['metadata_sha256']['train']:
        raise ValueError('Training metadata changed after instrument extraction')
    frame = pd.read_csv(path, usecols=META_COLUMNS,
                        dtype={'source_id': str, 'trace_name': str}, keep_default_na=False)
    rows = np.asarray(data['train_rows'])
    if (rows.ndim != 1 or rows.dtype.kind not in 'iu' or not len(rows)
            or rows[0] < 0 or rows[-1] >= len(frame) or np.any(np.diff(rows) <= 0)):
        raise ValueError('Instrument training rows must be ordered unique metadata indices')
    selected = frame.iloc[rows]
    for key, expected in [('train_ids', selected.source_id.to_numpy(dtype=str)),
                          ('train_trace_names', selected.trace_name.to_numpy(dtype=str)),
                          ('train_y', selected.source_magnitude.to_numpy(dtype=np.float32))]:
        if not np.array_equal(data[key], expected):
            raise ValueError(f'Instrument feature/target identity mismatch: {key}')
    target_stat = file_stat(args.targets)
    target_sha = sha256(args.targets)
    growth, valid, manifest = load_targets(args.targets, frame, rows, digest)
    if target_stat != file_stat(args.targets):
        raise ValueError('Growth target archive changed during loading')
    if manifest['audit_sha256'] != identities['audit_sha256']:
        raise ValueError('Growth archive was exported under a different duration audit')
    if manifest['normalization_sha256'] != identities['normalization_sha256']:
        raise ValueError('Growth archive count normalization differs from instrument extraction')
    audit = json.loads((root / 'results/2026-10-09/audit.json').read_text())
    if sha256(root / 'results/2026-10-09/audit.json') != identities['audit_sha256']:
        raise ValueError('Duration audit changed after instrument extraction')
    raw_path = Path(args.data) / 'Instance_events_counts.hdf5'
    cache_path = Path(args.data) / audit['windows']['5']['cache']
    if file_stat(raw_path) != manifest['raw_source'] or file_stat(cache_path) != manifest['cache_source']:
        raise ValueError('Growth source or exact-alignment 5s cache changed since export')
    j = (1, 3, 5).index(args.seconds)
    report = {'archive_sha256': target_sha, 'archive_stat': target_stat, 'manifest': manifest,
              'selected_row_sha256': array_digest(rows), 'selected_growth_sha256': array_digest(growth),
              'selected_mask_sha256': array_digest(valid), 'selected_records': len(rows),
              'valid_per_time': valid.sum(0).tolist(),
              'zero_growth_per_time': ((growth == 0) & valid).sum(0).tolist(),
              'seconds': args.seconds, 'target_seconds': 10,
              'coverage_policy': 'Every instrument-selected TRAIN row required; no dropping or resampling'}
    return growth[:, j].astype(np.float32), valid[:, j], report


def fit_one(data, arrays, mask, growth, valid, args, seed, device, control):
    if control not in CONTROLS or not np.isfinite(args.auxiliary_weight) or args.auxiliary_weight < 0:
        raise ValueError('Invalid growth control or auxiliary weight')
    if np.asarray(growth).shape != data['train_y'].shape or np.asarray(valid).shape != data['train_y'].shape:
        raise ValueError('Growth rows do not align with instrument training features')
    if np.asarray(valid).dtype != np.bool_:
        raise ValueError('Growth validity must be boolean')
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
    g = torch.as_tensor(growth, device=device)
    available = torch.as_tensor(valid, device=device)
    model = InstrumentGrowthModel(train_x.shape[1]).to(device)
    # Separate optimizers and clipping preserve the exact baseline AdamW path,
    # including foreach group shapes, even when the detached head has gradients.
    optimizer = torch.optim.AdamW(model.magnitude.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    aux_optimizer = torch.optim.AdamW(model.growth_head.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    shuffle = torch.Generator(device='cpu').manual_seed(seed)
    histories = {key: [] for key in ('supervised', 'auxiliary', 'total')}
    for _ in range(args.epochs):
        model.train()
        order = torch.randperm(len(y), generator=shuffle)
        totals = dict.fromkeys(histories, 0.)
        for cpu_indices in order.split(args.batch_size):
            indices = cpu_indices.to(device)
            logits, state = model.forward_with_state(train_x[indices], original[indices])
            pred = logits.softmax(1) @ centers
            magnitude = F.huber_loss(pred, y[indices], reduction='none', delta=.5)
            emphasis = 1 + args.beta * (y[indices] - 3.5).clamp_min(0)
            ce = F.cross_entropy(logits, labels[indices], reduction='none')
            anchor = (pred - original_mean[indices]).square()
            supervised = (weights[indices] * (emphasis*magnitude + .075*ce + args.anchor*anchor)).mean()
            aux = growth_loss(model, state, labels[indices], weights[indices], g[indices], available[indices], control)
            loss = supervised if control == 'supervised' else supervised + args.auxiliary_weight * aux
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite training objective')
            optimizer.zero_grad(set_to_none=True)
            aux_optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.magnitude.parameters(), 5.)
            nn.utils.clip_grad_norm_(model.growth_head.parameters(), 5.)
            optimizer.step()
            aux_optimizer.step()
            for key, value in [('supervised', supervised), ('auxiliary', aux), ('total', loss)]:
                totals[key] += value.item() * len(indices)
        for key in histories:
            histories[key].append(totals[key] / len(y))
    model.eval()
    with torch.inference_mode():
        probability = torch.cat([model(val_x[start:start+args.batch_size], val_original[start:start+args.batch_size])
                                  .double().softmax(1).cpu() for start in range(0, len(val_x), args.batch_size)]).numpy()
    state = {'magnitude': model.magnitude.cpu().state_dict(), 'growth_head': model.growth_head.cpu().state_dict()}
    return probability, state, histories


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, choices=(1, 3, 5), required=True)
    parser.add_argument('--targets', type=Path, required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', default=baseline.INVENTORY_SHA256)
    parser.add_argument('--root', type=Path, default=baseline.ROOT)
    parser.add_argument('--data', type=Path, default=Path('/data'))
    parser.add_argument('--output', type=Path, default=baseline.ROOT / 'results/2026-10-09/phase2')
    parser.add_argument('--controls', nargs='+', choices=CONTROLS, default=list(CONTROLS))
    parser.add_argument('--seeds', type=int, nargs='+', default=[20261009, 20261010])
    parser.add_argument('--epochs', type=int, default=15)
    parser.add_argument('--max-per-event', type=int, default=4)
    parser.add_argument('--expected-train-records', type=int, default=197676)
    parser.add_argument('--batch-size', type=int, default=2048)
    parser.add_argument('--extract-batch-size', type=int, default=256)
    parser.add_argument('--learning-rate', type=float, default=5e-4)
    parser.add_argument('--beta', type=float, default=5.)
    parser.add_argument('--anchor', type=float, default=0.)
    parser.add_argument('--auxiliary-weight', type=float, default=.05)
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.extract_batch_size, args.expected_train_records) < 1 or args.max_per_event < 0:
        parser.error('Positive epochs/batches/expected records and nonnegative max-per-event required')
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.controls)) != len(args.controls):
        parser.error('Duplicate seeds/controls are not independent comparisons')
    if not all(np.isfinite(v) and v >= 0 for v in (args.beta, args.anchor, args.auxiliary_weight)):
        parser.error('Loss weights must be finite and nonnegative')
    if not np.isfinite(args.learning_rate) or args.learning_rate <= 0:
        parser.error('Learning rate must be finite and positive')
    return args


def run(args):
    torch.set_num_threads(2)
    device = torch.device(('cuda' if torch.cuda.is_available() else 'cpu') if args.device == 'auto' else args.device)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    config.update(sampling_seed=20261009, selection='Fixed final epoch; every requested seed/control; no validation selection',
                  family='instrument', native_slots='all zero after shared TRAIN normalization')
    sources = [HERE / name for name in ('instrument_growth.py', 'instrument_residual.py', 'instrument_inventory.py',
               'feature_residual.py', 'future_growth.py', 'train_future_growth.py', 'train_sequential.py',
               'sequential_models.py', 'run_artifacts.py', 'INSTRUMENT_GROWTH.md')]
    sources += [HERE.parent / name for name in ('audit_and_export.py', 'distribution_experiment.py', 'frozen_head_pilot.py')]
    destination = create_run(args.output, f'instrument_growth_{args.seconds}s', config, sources)
    print('RUN_DIRECTORY', destination, flush=True)
    started = time.monotonic()
    data, identities, alignment, instrument_names = baseline.extract(args, device)
    if len(data['train_y']) != args.expected_train_records:
        raise ValueError('Training record count differs from the explicitly fixed protocol')
    arrays, mean, std, mask, base_dim = instrument_design(data)
    growth, valid, target_report = load_aligned_growth(args, data, identities)
    centers, y, ids = data['centers'], data['val_y'], data['val_ids']
    raw_probability = torch.from_numpy(data['val_logits']).double().softmax(1).numpy()
    results, predictions, histories = {}, {}, {}
    probabilities = {control: [] for control in args.controls}
    for decision, prediction in [('mean', raw_probability @ centers), ('median', median(raw_probability, centers))]:
        results['raw_' + decision] = metrics(y, prediction, ids, raw_probability, centers)
        predictions['raw_' + decision] = prediction
    np.savez_compressed(destination / 'raw_probabilities.npz', targets=y, event_ids=ids,
                        trace_names=data['val_trace_names'], centers=centers, mean_probability=raw_probability.astype(np.float32))
    for seed in args.seeds:
        for control in args.controls:
            name = f'{control}_seed{seed}'
            p, state, history = fit_one(data, arrays, mask, growth, valid, args, seed, device, control)
            probabilities[control].append(p)
            histories[name] = history
            torch.save(dict(state, feature_mean=torch.tensor(mean), feature_std=torch.tensor(std),
                       feature_mask=torch.tensor(mask), config=config, seed=seed, control=control,
                       base_dim=base_dim, instrument_names=instrument_names, native_names=baseline.NATIVE_FEATURE_NAMES),
                       destination / f'{name}.pth')
            for decision, prediction in [('mean', p @ centers), ('median', median(p, centers))]:
                key = name + '_' + decision
                predictions[key] = prediction
                results[key] = metrics(y, prediction, ids, p, centers)
            print(name, {k: results[name + '_mean'][k] for k in ('mae', 'medae', 'm4_mae', 'cvar95', 'fp4')}, flush=True)
    for control, values in probabilities.items():
        p = np.mean(values, axis=0)
        np.savez_compressed(destination / f'{control}_probabilities.npz', targets=y, event_ids=ids,
            trace_names=data['val_trace_names'], centers=centers, mean_probability=p.astype(np.float32),
            **{f'seed{seed}': value.astype(np.float32) for seed, value in zip(args.seeds, values)})
        for decision, prediction in [('mean', p @ centers), ('median', median(p, centers))]:
            key = control + '_ensemble_' + decision
            predictions[key] = prediction
            results[key] = metrics(y, prediction, ids, p, centers)
    run_info = dict(config, wall_seconds=time.monotonic()-started, device=str(device),
        torch_version=torch.__version__, python_version=platform.python_version(),
        train_records=len(data['train_y']), train_events=len(np.unique(data['train_ids'])),
        validation_status='Reused exploratory validation; no confirmatory claim',
        objective_status='Exact instrument residual weighted Huber(delta=.5)+.075CE plus fixed auxiliary; not a proper magnitude score',
        future_scope='TRAIN loss only; no future values, magnitude labels or growth outputs in inference',
        causality_limit='Original INSTANCE whole-record detrending/resampling and manual P alignment remain')
    schema = {'base_dimension': base_dim, 'instrument_names': instrument_names,
              'native_names': baseline.NATIVE_FEATURE_NAMES, 'mask': mask.tolist()}
    for name, value in [('metrics.json', results), ('history.json', histories), ('run.json', run_info),
                        ('input_identities.json', identities), ('alignment.json', alignment),
                        ('growth_targets.json', target_report), ('feature_schema.json', schema)]:
        (destination / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    np.savez_compressed(destination / 'predictions.npz', targets=y, event_ids=ids,
                        trace_names=data['val_trace_names'], **predictions)
    np.savez_compressed(destination / 'training_rows.npz', row_index=data['train_rows'], event_ids=data['train_ids'],
                        trace_names=data['train_trace_names'], targets=data['train_y'], weights=data['weights'])
    artifacts = {p.name: {'bytes': p.stat().st_size, 'sha256': sha256(p)}
                 for p in sorted(destination.iterdir()) if p.is_file()}
    (destination / 'artifacts.json').write_text(json.dumps(artifacts, indent=2) + '\n')
    print('COMPLETE', destination, flush=True)
    return destination


if __name__ == '__main__':
    run(parse_args())

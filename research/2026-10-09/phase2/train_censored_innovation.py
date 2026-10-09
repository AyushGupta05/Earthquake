"""Fixed TRAIN/VAL sequential likelihood pilot. Never opens TEST waveforms.

Every selected five-second cache row is checked against its named raw trace.
Only the one-second network is extracted. Starting static checkpoints are pinned
and replayed before any fit. See CENSORED_INNOVATION_METHOD.md for limitations.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import sys
import time

import h5py
import numpy as np
import pandas as pd
import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import censored_innovation as pilot
import instrument_residual as source
from instrument_factor_ablation import EXPECTED_INSTRUMENT_NAMES, write_json, write_artifact_manifest

EXPECTED_TRAIN_RECORDS = 197676
STARTING_CHECKPOINT_SHA256 = {
    20261009: 'd53f7ecfdf24cefb02382d29cac4c9d79a6ba17c683933d14757a8df66249c70',
    20261010: '78b6b6f86344dc7acb1383e77fe234f8994dfb46230fcd1c7f2727c995db1d8e',
}
CONTROLS = ('frozen',) + pilot.ARMS
INVALID_REASONS = {1: 'response_not_usable', 2: 'invalid_sensitivity', 4: 'unknown_unit',
                   8: 'first_peak_floor_or_nonfinite', 16: '13_block_floor_or_nonfinite',
                   32: '35_block_floor_or_nonfinite', 64: 'earlier_update_unavailable'}


def configure_determinism():
    """Set the verified cuBLAS contract before initializing any CUDA context.

    Preserve TF32 flags when replaying an existing backbone; changing precision
    silently would change its inputs. All effective flags are recorded.
    """
    workspace = ':4096:8'
    if torch.cuda.is_initialized() and os.environ.get('CUBLAS_WORKSPACE_CONFIG') != workspace:
        raise RuntimeError('CUDA was initialized before the deterministic cuBLAS contract')
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = workspace
    torch.use_deterministic_algorithms(True, warn_only=False)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    return {'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
            'deterministic_warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
            'cublas_workspace_config': os.environ['CUBLAS_WORKSPACE_CONFIG'],
            'cudnn_benchmark': torch.backends.cudnn.benchmark,
            'cudnn_deterministic': torch.backends.cudnn.deterministic,
            'cuda_matmul_allow_tf32': torch.backends.cuda.matmul.allow_tf32,
            'cudnn_allow_tf32': torch.backends.cudnn.allow_tf32}


def verify_prefix_batch(short, five, raw_group, frame, mean, std):
    """Exhaustive identity, not just matching labels or a sampled cache check."""
    if short.shape != (len(frame), 3, 100) or five.shape != (len(frame), 3, 500):
        raise ValueError('Wrong prefix batch dimensions')
    if not np.array_equal(short, five[:, :, :100]):
        raise ValueError('Selected one-second and five-second prefixes differ')
    mean = torch.as_tensor(mean, dtype=torch.float32).reshape(3, 1)
    std = torch.as_tensor(std, dtype=torch.float32).reshape(3, 1)
    for index, row in enumerate(frame.itertuples(index=False)):
        start = int(row.trace_P_arrival_sample)
        counts = np.asarray(raw_group[row.trace_name][:, start:start + 500], dtype=np.float32)
        if counts.shape != (3, 500):
            raise ValueError(f'Short named raw prefix: {row.trace_name}')
        expected = ((torch.from_numpy(counts) - mean) / (std + 1e-8)).numpy()
        if not np.array_equal(five[index], expected):
            raise ValueError(f'Named raw prefix differs: {row.trace_name}')


def invalid_codes(observations, sensitivity, usable, unit):
    common = (~usable).to(torch.int16)
    common |= ((~torch.isfinite(sensitivity)) | (sensitivity <= 0)).to(torch.int16) * 2
    common |= (unit == 0).to(torch.int16) * 4
    codes = common[:, None].expand(-1, 2).clone()
    codes[:, 0] |= (~observations.above_floor[:, 0]).to(torch.int16) * 8
    codes[:, 0] |= (~observations.above_floor[:, 1]).to(torch.int16) * 16
    codes[:, 1] |= (~observations.above_floor[:, 2]).to(torch.int16) * 32
    codes[:, 1] |= (~observations.valid[:, 0]).to(torch.int16) * 64
    if not torch.equal(codes == 0, observations.valid):
        raise ValueError('Invalid-reason codes disagree with validity masks')
    return codes


def extract_observations(args, data, identities, names):
    if tuple(names) != EXPECTED_INSTRUMENT_NAMES:
        raise ValueError('Expected the pinned 34-column instrument schema')
    audit_path = Path(args.root) / 'results/2026-10-09/audit.json'
    if source.sha256(audit_path) != identities['audit_sha256']:
        raise ValueError('Audit changed after one-second extraction')
    audit = json.loads(audit_path.read_text())
    if source.sha256(args.inventory) != identities['inventory_sha256']:
        raise ValueError('Inventory changed after one-second extraction')
    inventory = source.Inventory.from_archive(args.inventory)
    normalizers = []
    for name in ('train_mean_full.npy', 'train_std_full.npy'):
        path = Path(args.root) / name
        if source.sha256(path) != identities['normalization_sha256'][name]:
            raise ValueError('Normalization changed after one-second extraction')
        normalizers.append(np.load(path, allow_pickle=False))
    mean, std = normalizers
    paths = [Path(args.data) / audit['windows'][str(t)]['cache'] for t in (1, 5)]
    paths.append(Path(args.data) / 'Instance_events_counts.hdf5')
    observed, reporting, provenance = {}, {}, {'files': {}, 'raw_identity_checks': {}}
    for path in paths:
        stat = path.stat()
        provenance['files'][str(path)] = {'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}
    with h5py.File(paths[0], 'r') as one, h5py.File(paths[1], 'r') as five, h5py.File(paths[2], 'r') as raw:
        for split, filename in [('train', 'train_full_metadata.csv'), ('val', 'val_metadata.csv')]:
            path = Path(args.root) / filename
            if source.sha256(path) != identities['metadata_sha256'][split]:
                raise ValueError('Metadata changed after one-second extraction')
            frame = pd.read_csv(path, usecols=source.METADATA_COLUMNS,
                                dtype={name: str for name in source.STRING_COLUMNS}, keep_default_na=False)
            source.validate_metadata(frame, split)
            source.assert_cache_alignment(one[split], frame, 1)
            source.assert_cache_alignment(five[split], frame, 5)
            rows = data['train_rows'] if split == 'train' else np.arange(len(frame))
            if len(rows) == 0 or (np.diff(rows) <= 0).any() or rows[0] < 0 or rows[-1] >= len(frame):
                raise ValueError('Selected source rows must be nonempty, increasing and in range')
            selected = frame.iloc[rows].reset_index(drop=True)
            for key, column in [('ids', 'source_id'), ('trace_names', 'trace_name')]:
                if not np.array_equal(data[f'{split}_{key}'].astype(str), selected[column].to_numpy(str)):
                    raise ValueError(f'{split} identity order differs from one-second extraction')
            if not np.array_equal(data[f'{split}_y'].astype(np.float32), selected.source_magnitude.to_numpy(np.float32)):
                raise ValueError('Observation labels differ from one-second extraction')
            inst, gains, usable, actual_names, _ = source.instrument_arrays(selected, inventory)
            if list(names) != actual_names or not np.array_equal(inst, data[f'{split}_instrument']):
                raise ValueError('Response epoch/features differ from one-second extraction')
            velocity = inst[:, names.index('Z_velocity')]
            acceleration = inst[:, names.index('Z_acceleration')]
            if not np.isin(velocity, [0, 1]).all() or not np.isin(acceleration, [0, 1]).all() or (velocity + acceleration > 1).any():
                raise ValueError('Ambiguous Z physical-unit flags')
            units = (velocity + 2 * acceleration).astype(np.int64)
            chunks = {key: [] for key in ('z', 'g', 'valid', 'above_floor', 'invalid_reason_code')}
            for start in range(0, len(rows), args.extract_batch_size):
                stop = min(len(rows), start + args.extract_batch_size)
                ix = rows[start:stop]
                short = one[f'{split}/waveforms'][ix]
                values = five[f'{split}/waveforms'][ix]
                verify_prefix_batch(short, values, raw['data'], selected.iloc[start:stop], mean, std)
                counts = pilot.undo_count_standardization(torch.from_numpy(values), mean, std)[:, 2]
                gain = torch.from_numpy(gains[start:stop, 2])
                mask = torch.from_numpy(usable[start:stop, 2])
                unit = torch.from_numpy(units[start:stop])
                result = pilot.vertical_innovations(counts, gain, mask, unit)
                code = invalid_codes(result, gain, mask, unit)
                for key in chunks:
                    chunks[key].append((code if key == 'invalid_reason_code' else getattr(result, key)).numpy())
                if stop == len(rows) or (start // 16384 != stop // 16384):
                    print('OBSERVATIONS_PROGRESS', split, stop, len(rows), flush=True)
            observed[split] = {key: np.concatenate(value) for key, value in chunks.items()}
            observed[split].update(sensitivity_z=gains[:, 2], response_usable_z=usable[:, 2], physical_unit_z=units)
            reporting[split] = {'families': selected.station_channels.to_numpy(str),
                                'station_ids': (selected.station_network_code + '.' + selected.station_code).to_numpy(str)}
            provenance['raw_identity_checks'][split] = len(rows)
            print('OBSERVATIONS_VERIFIED', split, len(rows), flush=True)
    for path in paths:
        before = provenance['files'][str(path)]
        stat = path.stat()
        if before != {'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns}:
            raise ValueError('A source HDF5 changed during exhaustive prefix verification')
    provenance.update(identity_scope='Every selected TRAIN and all VAL 500-sample ENZ cache rows checked against named raw trace; every corresponding100-sample prefix identical',
                      invalid_reasons=INVALID_REASONS, native_floor=1e-12, baseline_samples=10, unit_codes={0: 'unknown', 1: 'velocity', 2: 'acceleration'})
    return observed, reporting, provenance


def evaluate(model, context, log_prior, observed, centers, y, batch_size, device):
    """Return float64 probabilities and held-out mechanism diagnostics."""
    probabilities, diagnostics = [], {k: [] for k in ('conditional_nll', 'forecast_nll', 'zero_probability', 'positive_pit')}
    centers_t = torch.as_tensor(centers, dtype=torch.float32, device=device)
    for start in range(0, len(context), batch_size):
        stop = start + batch_size
        x = torch.as_tensor(context[start:stop], device=device)
        prior = torch.as_tensor(log_prior[start:stop], device=device)
        z = torch.as_tensor(observed['z'][start:stop], device=device)
        valid = torch.as_tensor(observed['valid'][start:stop], device=device)
        labels = torch.as_tensor(np.floor(np.asarray(y[start:stop]) / .1 + 1e-5).clip(0, 65), dtype=torch.long, device=device)
        with torch.inference_mode():
            log_p = pilot.frozen_predictions(prior) if model is None else model(x, prior, z, valid, centers_t)
            p = log_p.exp().cpu().numpy()
            if not np.isfinite(p).all() or not np.allclose(p.sum(2), 1., rtol=0, atol=1e-12):
                raise ValueError('Non-normalized prediction artifact')
            probabilities.append(p)
            if model is None or model.arm == 'discriminative':
                continue
            marks = z if model.arm == 'uncensored' else z.clamp_min(0)
            conditional = pilot.conditional_nll(model, x, z, valid, centers_t[labels])
            diagnostics['conditional_nll'].append(conditional.cpu().numpy())
            forecast, zero, pit = [], [], []
            for step in range(2):
                params = model.parameters_for(x, centers_t[None].expand(len(x), -1), marks[:, 0], marks[:, step], step).double()
                mu, sigma = params[..., 0], F.softplus(params[..., 1]) + model.sigma_floor
                if model.arm in ('hurdle', 'hurdle_truncated'):
                    log_atom, log_positive = F.logsigmoid(params[..., 2]), F.logsigmoid(-params[..., 2])
                else:
                    log_atom, log_positive = torch.special.log_ndtr(-mu / sigma), torch.special.log_ndtr(mu / sigma)
                zero.append(torch.logsumexp(log_p[:, step] + log_atom, 1).exp())
                g = z[:, step].clamp_min(0)[:, None]
                if model.arm == 'hurdle':
                    cdf_positive = torch.special.ndtr((g.clamp_min(1e-300).log() - mu) / sigma)
                else:
                    # Stable conditional positive-Gaussian CDF, avoiding 1-1 cancellation.
                    log_ratio = torch.special.log_ndtr((mu - g) / sigma) - torch.special.log_ndtr(mu / sigma)
                    cdf_positive = -torch.expm1(log_ratio.clamp_max(0))
                mixture = (log_p[:, step] + log_positive).softmax(1)
                pit.append((mixture * cdf_positive).sum(1))
                log_q = pilot.observation_log_likelihood(model.arm, marks[:, step, None], params, model.sigma_floor)
                forecast.append(-torch.logsumexp(log_p[:, step] + log_q, 1))
            for key, parts in [('forecast_nll', forecast), ('zero_probability', zero), ('positive_pit', pit)]:
                values = torch.stack(parts, 1)
                mask = valid & (z > 0) if key == 'positive_pit' else valid
                values = torch.where(mask, values, torch.zeros_like(values))
                if not torch.isfinite(values).all():
                    raise ValueError('Nonfinite held-out likelihood diagnostics')
                diagnostics[key].append(values.cpu().numpy())
    return np.concatenate(probabilities), {key: np.concatenate(value) for key, value in diagnostics.items() if value}


def mechanism_summary(diagnostic, observation):
    result = {}
    for step, seconds in enumerate((3, 5)):
        keep = observation['valid'][:, step]
        positive = keep & (observation['z'][:, step] > 0)
        summary = {'valid_records': int(keep.sum()), 'positive_records': int(positive.sum())}
        if keep.any():
            zero = observation['z'][keep, step] <= 0
            forecast = diagnostic['zero_probability'][keep, step]
            summary.update(observed_zero_fraction=float(zero.mean()), predicted_zero_fraction=float(forecast.mean()),
                           zero_brier=float(np.square(forecast - zero).mean()),
                           conditional_nll=float(diagnostic['conditional_nll'][keep, step].mean()),
                           forecast_nll=float(diagnostic['forecast_nll'][keep, step].mean()))
        if positive.any():
            pit = diagnostic['positive_pit'][positive, step]
            summary.update(positive_pit_mean=float(pit.mean()), positive_pit_histogram=np.histogram(pit, bins=np.linspace(0, 1, 11))[0].tolist())
        result[str(seconds)] = summary
    return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', default=source.INVENTORY_SHA256)
    parser.add_argument('--root', type=Path, default=source.ROOT)
    parser.add_argument('--data', type=Path, default=Path('/data'))
    parser.add_argument('--output', type=Path, default=Path('/mnt/eew-research/runs'))
    parser.add_argument('--initial-run', type=Path, default=Path('/mnt/eew-research/runs/instrument_residual_1s_1bbf4f4d67e5_2b94eb7e7f00'))
    parser.add_argument('--batch-size', type=int, default=2048)
    parser.add_argument('--extract-batch-size', type=int, default=256)
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    parser.add_argument('--prepare-only', action='store_true', help='Verify and persist observations and replayed p1, then exit without fitting')
    args = parser.parse_args(argv)
    if min(args.batch_size, args.extract_batch_size) < 1:
        parser.error('Batch sizes must be positive')
    args.seconds, args.max_per_event, args.epochs, args.seeds = 1, 4, 15, list(pilot.SEEDS)
    return args


def main():
    args = parse_args()
    torch.set_num_threads(1)
    runtime_flags = configure_determinism()
    device = torch.device(('cuda' if torch.cuda.is_available() else 'cpu') if args.device == 'auto' else args.device)
    if device.type == 'cuda':
        runtime_flags['cuda_device_name'] = torch.cuda.get_device_name(device)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    fit_config = pilot.FitConfig(epochs=args.epochs, batch_size=args.batch_size)
    config.update(controls=list(CONTROLS), fit=asdict(fit_config), runtime_flags=runtime_flags, selection='Fixed final epoch; every arm/seed reported; no validation selection',
                  update_status='Normalized likelihood heuristic from frozen cost-sensitive p1; not true Bayes guarantee',
                  gain_invariance_scope='Innovation statistic only; H1 includes count-dependent and station/site features')
    sources = [HERE / name for name in ('train_censored_innovation.py', 'censored_innovation.py', 'instrument_residual.py', 'instrument_inventory.py',
                                       'instrument_factor_ablation.py', 'feature_residual.py', 'run_artifacts.py', 'CENSORED_INNOVATION_METHOD.md')]
    sources += [HERE.parent / name for name in ('audit_and_export.py', 'distribution_experiment.py', 'frozen_head_pilot.py')]
    destination = source.create_run(args.output, 'censored_innovation', config, sources)
    print('RUN_DIRECTORY', destination, flush=True)
    start_time = time.monotonic()
    data, identities, alignment, names = source.extract(args, device)
    if len(data['train_y']) != EXPECTED_TRAIN_RECORDS:
        raise ValueError('The prespecified197676-row starting population was not reproduced')
    observed, reporting, observation_identity = extract_observations(args, data, identities, names)
    write_json(destination / 'input_identities.json', identities)
    write_json(destination / 'alignment.json', alignment)
    write_json(destination / 'observation_provenance.json', observation_identity)
    for split in ('train', 'val'):
        selected_rows = data['train_rows'] if split == 'train' else np.arange(len(data['val_y']))
        np.savez_compressed(destination / f'{split}_observations.npz', **observed[split], **reporting[split], row_index=selected_rows,
                            event_ids=data[f'{split}_ids'], trace_names=data[f'{split}_trace_names'], targets=data[f'{split}_y'])
    np.savez_compressed(destination / 'training_rows.npz', row_index=data['train_rows'], event_ids=data['train_ids'],
                        trace_names=data['train_trace_names'], weights=data['weights'])
    centers, y, ids = data['centers'], data['val_y'], data['val_ids']
    metrics, histories, predictions, mechanism, counts, frozen_identity, ensembles = {}, {}, {}, {}, {}, {}, {}
    reference_context, starts = None, {}

    def record(label, probability):
        for index, seconds in enumerate((1, 3, 5)):
            p = probability[:, index]
            for decision, prediction in [('mean', p @ centers), ('median', source.median(p, centers))]:
                key = f'{label}_{seconds}s_{decision}'
                predictions[key] = prediction
                metrics[key] = source.metrics(y, prediction, ids, p, centers)

    for seed in args.seeds:
        checkpoint = args.initial_run / f'instrument_seed{seed}.pth'
        if source.sha256(checkpoint) != STARTING_CHECKPOINT_SHA256[seed]:
            raise ValueError('Pinned starting checkpoint changed')
        contexts, priors, provenance = pilot.load_frozen_start(data, identities, names, args.initial_run, seed, device, args.batch_size)
        frozen_identity[str(seed)] = provenance
        if reference_context is None:
            reference_context = contexts
            np.savez_compressed(destination / 'frozen_context.npz', train=contexts[0], val=contexts[1])
        elif any(not np.array_equal(a, b) for a, b in zip(reference_context, contexts)):
            raise ValueError('Starting H1 contexts differ between seeds')
        np.savez_compressed(destination / f'frozen_p1_seed{seed}.npz', train_log_probability=priors[0], val_log_probability=priors[1], centers=centers)
        write_json(destination / 'frozen_start_provenance.json', frozen_identity)
        starts[seed] = (priors, provenance)
    # Verify BOTH starting artifacts before fitting any arm. They share H1 but
    # preserve their separately fitted p1; no averaging before the updates.
    for seed in ([] if args.prepare_only else args.seeds):
        contexts, (priors, provenance) = reference_context, starts[seed]
        tensors = [torch.as_tensor(value, device=device) for value in (contexts[0], priors[0], observed['train']['z'], observed['train']['valid'])]
        labels = torch.as_tensor(np.floor(data['train_y'] / .1 + 1e-5).clip(0, 65), dtype=torch.long, device=device)
        weights = torch.as_tensor(data['weights'], device=device)
        centers_t = torch.as_tensor(centers, dtype=torch.float32, device=device)
        for arm in CONTROLS:
            label = f'{arm}_seed{seed}'
            if arm == 'frozen':
                model, history = None, []
            else:
                model, history = pilot.fit_arm(*tensors, labels, weights, centers_t, arm, seed, fit_config)
                torch.save({'model': {k: v.detach().cpu() for k, v in model.state_dict().items()}, 'seed': seed, 'arm': arm,
                            'context_dimension': contexts[0].shape[1], 'fit_config': asdict(fit_config), 'starting_provenance': provenance}, destination / f'{label}.pth')
            histories[label] = history
            counts[label] = 0 if model is None else sum(p.numel() for p in model.parameters())
            p, diagnostic = evaluate(model, contexts[1], priors[1], observed['val'], centers, y, args.batch_size, device)
            if not np.array_equal(p[:, 0], np.exp(priors[1])):
                # NumPy and torch exp can differ by an ulp, but p1 itself is unchanged.
                if not np.allclose(p[:, 0], np.exp(priors[1]), atol=1e-15, rtol=1e-14):
                    raise ValueError('An arm changed the frozen one-second start')
            np.savez_compressed(destination / f'{label}_probabilities.npz', probability=p, targets=y, event_ids=ids,
                                trace_names=data['val_trace_names'], centers=centers, deadlines=np.array([1, 3, 5]))
            if diagnostic:
                np.savez_compressed(destination / f'{label}_mechanism.npz', **diagnostic, valid=observed['val']['valid'],
                                    positive_valid=observed['val']['valid'] & (observed['val']['z'] > 0), event_ids=ids, trace_names=data['val_trace_names'])
                mechanism[label] = mechanism_summary(diagnostic, observed['val'])
            record(label, p)
            ensembles[arm] = ensembles.get(arm, 0.) + p / len(args.seeds)
            print(label, {t: metrics[f'{label}_{t}s_mean']['mae'] for t in (1, 3, 5)}, flush=True)
        del tensors, model
    if not args.prepare_only:
        if len(set(value for value in counts.values() if value)) != 1:
            raise ValueError('Learned-arm parameter allocations differ')
        for arm, p in ensembles.items():
            record(arm + '_ensemble', p)
            np.savez_compressed(destination / f'{arm}_ensemble_probabilities.npz', probability=p, targets=y, event_ids=ids,
                                trace_names=data['val_trace_names'], centers=centers, deadlines=np.array([1, 3, 5]))
        np.savez_compressed(destination / 'predictions.npz', targets=y, event_ids=ids, trace_names=data['val_trace_names'], **predictions)
    run = dict(config, train_records=len(data['train_y']), train_events=len(np.unique(data['train_ids'])),
               parameter_counts=counts, device=str(device), torch_version=torch.__version__, python_version=platform.python_version(),
               wall_seconds=time.monotonic() - start_time, status='prepared_only' if args.prepare_only else 'complete',
               validation_status='Reused exploratory event-disjoint VAL; mostly seen stations,13M>=4events, noM>=6',
               causality_limit='Released INSTANCE full-record processing and catalogue P pick remain; no TEST read',
               nll_comparison='Uncensored Z has a different sample space; compare its NLL only to same-space controls')
    for name, value in [('run.json', run), ('metrics.json', metrics), ('history.json', histories), ('mechanism.json', mechanism)]:
        write_json(destination / name, value)
    write_artifact_manifest(destination)
    print('COMPLETE', destination, flush=True)


if __name__ == '__main__':
    main()

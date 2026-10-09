"""Matched static-feature ablations of the existing INSTANCE residual runner.

All five arms retain its 291-column architecture, initialization, normalization,
sampling, minibatch order and objective. Only explicit input masks differ. The
12 native-prefix slots are disabled in every arm. TRAIN/VAL only; reused VAL is
exploratory and never chooses an epoch, arm, seed or decision threshold.
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import instrument_residual as source

FAMILY_NAMES = tuple(f'family_{x}' for x in ('HH', 'EH', 'HN', 'HL', 'EN', 'unknown'))
SITE_NAMES = ('station_elevation_m', 'station_elevation_m_missing',
              'station_vs_30_mps', 'station_vs_30_mps_missing')
RESPONSE_SUFFIXES = ('response_missing', 'log10_sensitivity', 'velocity', 'acceleration',
                     'log1p_sensitivity_frequency_hz', 'sensitivity_frequency_hz_missing',
                     'log1p_native_sample_rate_hz', 'native_sample_rate_hz_missing')
RESPONSE_NAMES = tuple(f'{c}_{suffix}' for c in 'ENZ' for suffix in RESPONSE_SUFFIXES)
EXPECTED_INSTRUMENT_NAMES = FAMILY_NAMES + SITE_NAMES + RESPONSE_NAMES
GAIN_NAMES = tuple(f'{c}_{suffix}' for c in 'ENZ'
                   for suffix in ('response_missing', 'log10_sensitivity', 'velocity', 'acceleration'))
CONTROL_NAMES = {
    'base': (),
    'gain_units': GAIN_NAMES,
    'family_site': FAMILY_NAMES + SITE_NAMES,
    'response_all': RESPONSE_NAMES,
    'full_static': EXPECTED_INSTRUMENT_NAMES,
}


def factor_design(data, instrument_names):
    """Use the source's exact normalization; select columns by explicit names."""
    if tuple(instrument_names) != EXPECTED_INSTRUMENT_NAMES:
        raise ValueError('Instrument feature schema differs from the pinned 34-name order')
    arrays, mean, std, _, base_dim = source.design_inputs(data)
    if base_dim != 245 or len(mean) != 291:
        raise ValueError('Expected unchanged 245 base + 34 static + 12 inactive native columns')
    positions = {name: base_dim + i for i, name in enumerate(instrument_names)}
    masks = {}
    for control, selected in CONTROL_NAMES.items():
        mask = np.zeros(291, dtype=np.float32)
        mask[:base_dim] = 1
        for name in selected:
            mask[positions[name]] = 1
        masks[control] = mask
    return arrays, mean, std, masks, base_dim


def reporting_metadata(args, data, identities):
    """Read identity fields for reporting only; never append them to features."""
    frames = {}
    columns = ['source_id', 'trace_name', 'station_network_code', 'station_code', 'station_channels']
    for split, filename in [('train', 'train_full_metadata.csv'), ('val', 'val_metadata.csv')]:
        path = Path(args.root) / filename
        if source.sha256(path) != identities['metadata_sha256'][split]:
            raise ValueError(f'{split}: reporting metadata changed after extraction')
        frame = pd.read_csv(path, usecols=columns, dtype=str, keep_default_na=False)
        if frame[columns].eq('').any().any() or frame.trace_name.duplicated().any():
            raise ValueError(f'{split}: invalid reporting identities')
        frame['station_id'] = frame.station_network_code + '.' + frame.station_code
        frames[split] = frame
        selected = frame.iloc[data['train_rows']] if split == 'train' else frame
        for key, column in [('ids', 'source_id'), ('trace_names', 'trace_name')]:
            if not np.array_equal(data[f'{split}_{key}'].astype(str), selected[column].to_numpy(str)):
                raise ValueError(f'{split}: reporting metadata identity order differs')
    val = frames['val']
    overlap = {}
    for scope, train in [('full_train', frames['train']),
                         ('sampled_train', frames['train'].iloc[data['train_rows']])]:
        seen = val.station_id.isin(set(train.station_id)).to_numpy()
        tail = data['val_y'] >= 4
        overlap[scope] = {
            'train_stations': int(train.station_id.nunique()),
            'validation_stations': int(val.station_id.nunique()),
            'overlapping_stations': len(set(train.station_id) & set(val.station_id)),
            'seen_validation_records': int(seen.sum()),
            'seen_validation_fraction': float(seen.mean()),
            'seen_tail_records': int((seen & tail).sum()),
            'tail_records': int(tail.sum()),
            'unseen_validation_station_ids': sorted(set(val.station_id) - set(train.station_id)),
        }
    return val, overlap


def subgroup_diagnostics(targets, event_ids, families, baseline, alternative, threshold=4.):
    """Paired descriptive errors, with same-event family support explicit."""
    y = np.asarray(targets)
    ids, families = np.asarray(event_ids).astype(str), np.asarray(families).astype(str)
    baseline, alternative = np.asarray(baseline), np.asarray(alternative)
    if any(x.shape != y.shape for x in (ids, families, baseline, alternative)):
        raise ValueError('Subgroup vectors differ in shape')
    if not all(np.isfinite(x).all() for x in (y, baseline, alternative)):
        raise ValueError('Nonfinite subgroup values')
    errors = np.abs(baseline - y), np.abs(alternative - y)
    required = ('EH', 'HH', 'HN')
    common = set.intersection(*(set(ids[families == family]) for family in required))
    shared = np.isin(ids, sorted(common))
    result = {'interpretation': 'Descriptive paired subgroups; different stations/distances remain confounded',
              'same_event_families': list(required), 'same_event_count': len(common),
              'same_event_tail_count': len(set(ids[shared & (y >= threshold)])), 'groups': {}}
    for scope, selection in [('all', np.ones(len(y), dtype=bool)), ('tail', y >= threshold),
                             ('same_events', shared), ('same_events_tail', shared & (y >= threshold))]:
        groups = []
        for family in sorted(set(families)):
            keep = selection & (families == family)
            if not keep.any():
                continue
            before, after = [e[keep] for e in errors]
            frame = pd.DataFrame({'event': ids[keep], 'before': before, 'after': after})
            event_means = frame.groupby('event', sort=True)[['before', 'after']].mean()
            groups.append({'family': family, 'records': int(keep.sum()), 'events': len(event_means),
                           'base_mae': float(before.mean()), 'alternative_mae': float(after.mean()),
                           'paired_mae_difference': float((after - before).mean()),
                           'base_event_macro_mae': float(event_means.before.mean()),
                           'alternative_event_macro_mae': float(event_means.after.mean()),
                           'events_improved': int((event_means.after < event_means.before).sum())})
        result['groups'][scope] = groups
    return result


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def write_artifact_manifest(destination):
    """Hashes cover every completed output except this self-referential manifest."""
    files = {p.name: {'bytes': p.stat().st_size, 'sha256': source.sha256(p)}
             for p in sorted(destination.iterdir()) if p.is_file() and p.name != 'artifacts.json'}
    write_json(destination / 'artifacts.json', {'algorithm': 'sha256', 'files': files})


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, choices=(1, 3, 5), required=True)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--inventory-sha256', default=source.INVENTORY_SHA256)
    parser.add_argument('--root', type=Path, default=source.ROOT)
    parser.add_argument('--data', type=Path, default=Path('/data'))
    parser.add_argument('--output', type=Path, default=source.ROOT / 'results/2026-10-09/phase2')
    parser.add_argument('--seeds', type=int, nargs='+', default=[20261009, 20261010])
    parser.add_argument('--epochs', type=int, default=15)
    parser.add_argument('--max-per-event', type=int, default=4,
                        help='0 retains all training records; otherwise source event sampling plus all M>=4')
    parser.add_argument('--batch-size', type=int, default=2048)
    parser.add_argument('--extract-batch-size', type=int, default=256)
    parser.add_argument('--learning-rate', type=float, default=5e-4)
    parser.add_argument('--beta', type=float, default=5.)
    parser.add_argument('--anchor', type=float, default=0.)
    parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
    args = parser.parse_args(argv)
    if min(args.epochs, args.batch_size, args.extract_batch_size) < 1 or args.max_per_event < 0:
        parser.error('epochs/batches must be positive; max-per-event must be nonnegative')
    if len(set(args.seeds)) != len(args.seeds):
        parser.error('Duplicate seeds are not independent replicates')
    if not all(np.isfinite(x) and x >= 0 for x in (args.beta, args.anchor)) or not np.isfinite(args.learning_rate) or args.learning_rate <= 0:
        parser.error('Invalid objective weights or learning rate')
    return args


def main():
    args = parse_args()
    torch.set_num_threads(2)
    device = torch.device(('cuda' if torch.cuda.is_available() else 'cpu') if args.device == 'auto' else args.device)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    config.update(controls=list(CONTROL_NAMES), sampling_seed=20261009,
                  selection='Fixed final epoch; every arm/seed reported; no validation selection',
                  native_policy='All 12 native-prefix inputs permanently masked to zero')
    sources = [HERE / name for name in ('instrument_factor_ablation.py', 'instrument_residual.py',
                                       'instrument_inventory.py', 'feature_residual.py', 'run_artifacts.py')]
    sources += [HERE.parent / name for name in ('audit_and_export.py', 'distribution_experiment.py', 'frozen_head_pilot.py')]
    destination = source.create_run(args.output, f'instrument_factors_{args.seconds}s', config, sources)
    print('RUN_DIRECTORY', destination, flush=True)
    started = time.monotonic()
    data, identities, alignment, names = source.extract(args, device)
    arrays, mean, std, masks, base_dim = factor_design(data, names)
    reporting, overlap = reporting_metadata(args, data, identities)
    centers, y, ids = data['centers'], data['val_y'], data['val_ids']
    schema = {'base_dimension': base_dim, 'input_dimension': len(mean), 'instrument_names': names,
              'inactive_native_names': source.NATIVE_FEATURE_NAMES,
              'selected_static_names': {k: list(v) for k, v in CONTROL_NAMES.items()},
              'masks': {k: v.tolist() for k, v in masks.items()}}
    write_json(destination / 'feature_schema.json', schema)
    write_json(destination / 'input_identities.json', identities)
    write_json(destination / 'alignment.json', alignment)
    write_json(destination / 'station_overlap.json', overlap)
    np.savez_compressed(destination / 'feature_normalization.npz', mean=mean, std=std)
    np.savez_compressed(destination / 'training_rows.npz', row_index=data['train_rows'], event_ids=data['train_ids'],
                        trace_names=data['train_trace_names'], weights=data['weights'])
    np.savez_compressed(destination / 'validation_reporting_metadata.npz', event_ids=ids,
                        trace_names=data['val_trace_names'], station_ids=reporting.station_id.to_numpy(str),
                        families=reporting.station_channels.to_numpy(str))
    raw = torch.from_numpy(data['val_logits']).double().softmax(1).numpy()
    np.savez_compressed(destination / 'raw_probabilities.npz', targets=y, event_ids=ids,
                        trace_names=data['val_trace_names'], centers=centers, probability=raw)
    results, predictions, histories, probabilities, parameter_counts = {}, {}, {}, {}, {}

    def record(name, probability):
        for decision, prediction in [('mean', probability @ centers), ('median', source.median(probability, centers))]:
            key = name + '_' + decision
            predictions[key] = prediction
            results[key] = source.metrics(y, prediction, ids, probability, centers)

    record('raw', raw)
    for control in CONTROL_NAMES:
        probabilities[control] = []
    for seed in args.seeds:
        for control in CONTROL_NAMES:
            label = f'{control}_seed{seed}'
            p, state, losses = source.fit_one(data, arrays, masks[control], args, seed, device)
            probabilities[control].append(p)
            histories[label] = losses
            parameter_counts[label] = sum(t.numel() for t in state.values())
            torch.save({'model': state, 'feature_mean': torch.tensor(mean), 'feature_std': torch.tensor(std),
                        'feature_mask': torch.tensor(masks[control]), 'config': config, 'seed': seed,
                        'control': control, 'base_dim': base_dim, 'instrument_names': names,
                        'native_names': source.NATIVE_FEATURE_NAMES}, destination / f'{label}.pth')
            record(label, p)
            print(label, {key: results[label + '_mean'][key] for key in ('mae', 'medae', 'm4_mae', 'cvar95', 'fp4')}, flush=True)
    if len(set(parameter_counts.values())) != 1:
        raise ValueError('Model parameter counts differ between controls')
    ensembles = {}
    for control, values in probabilities.items():
        p = np.mean(values, axis=0)
        ensembles[control] = p
        # Preserve float64 used for metrics, so saved probabilities reproduce decisions.
        np.savez_compressed(destination / f'{control}_probabilities.npz', targets=y, event_ids=ids,
                            trace_names=data['val_trace_names'], centers=centers, mean_probability=p,
                            **{f'seed{seed}': value for seed, value in zip(args.seeds, values)})
        record(control + '_ensemble', p)
    diagnostics = {control: subgroup_diagnostics(y, ids, reporting.station_channels.to_numpy(str),
                   ensembles['base'] @ centers, p @ centers) for control, p in ensembles.items() if control != 'base'}
    run = dict(config, wall_seconds=time.monotonic()-started, device=str(device),
               torch_version=torch.__version__, python_version=platform.python_version(),
               train_records=len(data['train_y']), train_events=len(np.unique(data['train_ids'])),
               input_dimension=len(mean), parameter_counts=parameter_counts,
               validation_status='Reused exploratory validation; event-disjoint but mostly seen stations',
               objective_status='Inverse-sampling-weighted beta-Huber + CE; no calibration guarantee',
               causality_limit='INSTANCE whole-record preprocessing and catalog P alignment remain')
    for filename, value in [('metrics.json', results), ('history.json', histories), ('run.json', run),
                            ('family_diagnostics.json', diagnostics)]:
        write_json(destination / filename, value)
    np.savez_compressed(destination / 'predictions.npz', targets=y, event_ids=ids,
                        trace_names=data['val_trace_names'], **predictions)
    write_artifact_manifest(destination)
    print('COMPLETE', destination, flush=True)


if __name__ == '__main__':
    main()

"""Independent point-prediction and provenance audit of six affine controls.

Does not verify unsaved distributions, CRPS or model replay. Ensemble means
are valid mixture means; per-seed medians are never averaged into a median.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


CONTROLS = ('raw', 'affine', 'affine_guard1')
SEEDS = (20261009, 20261010)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def array_sha(value):
    a = np.ascontiguousarray(value)
    h = hashlib.sha256(str(a.dtype).encode())
    h.update(json.dumps(list(a.shape)).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def point_metrics(y, pred, ids):
    y, pred, ids = map(np.asarray, (y, pred, ids))
    if y.ndim != 1 or not len(y) or pred.shape != y.shape or ids.shape != y.shape:
        raise ValueError('Aligned nonempty vectors required')
    if not np.isfinite(y).all() or not np.isfinite(pred).all():
        raise ValueError('Finite targets and predictions required')
    error = np.abs(pred-y)
    events, inverse = np.unique(ids, return_inverse=True)
    counts = np.bincount(inverse)
    per_event = np.bincount(inverse, weights=error) / counts
    lower = np.full(len(events), np.inf)
    upper = np.full(len(events), -np.inf)
    np.minimum.at(lower, inverse, y)
    np.maximum.at(upper, inverse, y)
    if np.any(upper-lower > 1e-6):
        raise ValueError('An event must have one magnitude')
    tail = y >= 4
    result = dict(mae=float(error.mean()), medae=float(np.median(error)),
                  rmse=float(np.sqrt(np.mean(error**2))),
                  event_macro_mae=float(per_event.mean()),
                  cvar95=float(np.sort(error)[-max(1, int(np.ceil(.05*len(y)))):].mean()),
                  records=len(y), events=len(events),
                  fp4=int(np.sum((pred >= 4) & ~tail)),
                  tp4=int(np.sum((pred >= 4) & tail)),
                  fpr4=float(np.mean(pred[~tail] >= 4)) if (~tail).any() else None)
    for threshold in (4., 4.5, 5., 6.):
        mask = y >= threshold
        key = f'm{threshold:g}'
        selected = np.unique(inverse[mask])
        result[key+'_events'] = len(selected)
        result[key+'_mae'] = float(error[mask].mean()) if mask.any() else None
        result[key+'_event_macro_mae'] = float(per_event[selected].mean()) if mask.any() else None
        result[key+'_bias'] = float((pred-y)[mask].mean()) if mask.any() else None
    return result


def close_metrics(actual, saved):
    maximum = 0.
    for key, value in actual.items():
        other = saved[key]
        if value is None:
            if other is not None:
                raise ValueError(f'Unexpected finite metric {key}')
        else:
            if other is None or not np.isfinite(other):
                raise ValueError(f'Nonfinite or absent metric {key}')
            delta = abs(value-other)
            maximum = max(maximum, delta)
            if delta > 1e-10:
                raise ValueError(f'Metric mismatch {key}: {value} != {other}')
    return maximum


def audit(directory, manifest_path, require_complete=True):
    root = Path(directory)
    manifest = json.loads(Path(manifest_path).read_text())
    for name, item in manifest.items():
        path = root / name
        if path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError(f'Transfer artifact mismatch: {name}')
    runs = {}
    reference = None
    common_config = None
    max_delta = 0.
    for directory in sorted(root.glob('affine_prefix_*')):
        if not directory.is_dir():
            continue
        required = ('identity.json', 'run.json', 'history.json', 'metrics.json',
                    'model.pth', 'predictions.npz', 'train_rows.npz')
        if any(str((directory/f).relative_to(root)) not in manifest for f in required):
            raise ValueError('Every evaluated artifact must be transfer-hash pinned')
        identity = json.loads((directory/'identity.json').read_text())
        config = identity['config']
        final = json.loads((directory/'run.json').read_text())
        if any(final.get(k) != v for k, v in config.items()):
            raise ValueError('Final config differs from initial identity')
        key = (config['control'], config['seed'])
        if key in runs or key[0] not in CONTROLS or key[1] not in SEEDS:
            raise ValueError('Duplicate or unknown control/seed')
        if config['epochs'] != 10 or config['train_records'] != 979487:
            raise ValueError('Unexpected fixed training budget')
        runtime = config['runtime']
        if not (config['deterministic'] and runtime['deterministic_algorithms']
                and runtime['cudnn_deterministic'] and not runtime['cudnn_benchmark']):
            raise ValueError('Expected strict deterministic run')
        shared = {k:v for k,v in config.items() if k not in ('control','seed','initial_model_sha256')}
        shared['sources'] = identity['source_sha256']
        if common_config is None:
            common_config = shared
        if common_config != shared:
            raise ValueError('Matched controls differ beyond control and seed')
        history = json.loads((directory/'history.json').read_text())
        if [x['epoch'] for x in history] != list(range(1,11)):
            raise ValueError('Incomplete epoch history')
        with np.load(directory/'train_rows.npz', allow_pickle=False) as data:
            rows = data['rows']
            if len(rows) != 979487 or array_sha(rows) != config['train_rows_sha256']:
                raise ValueError('TRAIN row hash mismatch')
        with np.load(directory/'predictions.npz', allow_pickle=False) as data:
            arrays = {k:data[k] for k in data.files}
        for k, h in config['validation_identity_sha256'].items():
            if array_sha(arrays[k]) != h:
                raise ValueError(f'Validation identity mismatch {k}')
        current = {k:arrays[k] for k in ('targets','event_ids','trace_names','centers')}
        if reference is None:
            reference = current
        if any(not np.array_equal(current[k], reference[k]) for k in current):
            raise ValueError('Validation alignment mismatch')
        saved = json.loads((directory/'metrics.json').read_text())
        measured = {}
        for t in (1,3,5):
            measured[str(t)] = point_metrics(arrays['targets'], arrays[f'mean_{t}s'], arrays['event_ids'])
            max_delta = max(max_delta, close_metrics(measured[str(t)], saved[str(t)]))
            if not np.isfinite(arrays[f'median_{t}s']).all():
                raise ValueError('Nonfinite saved median')
        runs[key] = dict(directory=directory.name, config=config, history=history,
                         measured=measured, predictions=arrays)
    expected = {(c,s) for c in CONTROLS for s in SEEDS}
    if require_complete and set(runs) != expected:
        raise ValueError(f'Incomplete grid: {sorted(expected-set(runs))}')
    if not runs:
        raise ValueError('No runs found')
    for seed in SEEDS:
        group = [v for k,v in runs.items() if k[1] == seed]
        if not group:
            continue
        first = group[0]
        for run in group[1:]:
            if run['config']['initial_model_sha256'] != first['config']['initial_model_sha256']:
                raise ValueError('Initial model differs within seed')
            if [x['order_sha256'] for x in run['history']] != [x['order_sha256'] for x in first['history']]:
                raise ValueError('TRAIN batch order differs within seed')
    result = {'schema':'affine-point-audit-v1','verified_transfer_files':len(manifest),
              'complete_grid':set(runs)==expected,'maximum_metric_absolute_difference':max_delta,
              'not_verified':['model replay','unsaved probability distributions','CRPS','mixture median'],
              'runs':{f'{c}_seed{s}':{'directory':r['directory'],'metrics':r['measured']} for (c,s),r in runs.items()},
              'ensemble_mean':{}}
    for control in CONTROLS:
        if not all((control,s) in runs for s in SEEDS):
            continue
        result['ensemble_mean'][control] = {}
        for t in (1,3,5):
            prediction = np.mean([runs[control,s]['predictions'][f'mean_{t}s'] for s in SEEDS],axis=0)
            result['ensemble_mean'][control][str(t)] = point_metrics(reference['targets'],prediction,reference['event_ids'])
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.directory,args.manifest)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')

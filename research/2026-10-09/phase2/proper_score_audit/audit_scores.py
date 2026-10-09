"""Independent, CPU-only audit of completed validation proper-score grids.

No training/evaluator modules are imported. Only explicitly named TRAIN and
validation artifacts are read; no TEST discovery, model fitting, or selection.
Saved float32 PMFs are checked before a documented sum-to-one roundoff repair.
"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse
import hashlib
import json
from pathlib import Path
import platform
import time

import numpy as np

CONTROLS = ('huber_ce', 'crps_ce', 'tail_crps_ce', 'marginal_crps_ce', 'ranked_bce_ce')
SEEDS = (20261009, 20261010)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def array_digest(value):
    value = np.ascontiguousarray(value)
    h = hashlib.sha256()
    h.update(str(value.dtype).encode())
    h.update(json.dumps(list(value.shape)).encode())
    h.update(value.tobytes())
    return h.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text())


def load_npz(path):
    with np.load(path, allow_pickle=False) as source:
        return {key: source[key] for key in source.files}


def validate_probability(value, rows, columns):
    p = np.asarray(value, dtype=np.float64)
    require(p.shape == (rows, columns), 'PMF shape mismatch')
    require(np.isfinite(p).all() and np.all(p >= 0), 'Nonfinite or negative PMF')
    sums = p.sum(axis=1)
    drift = float(np.max(np.abs(sums - 1)))
    require(drift <= 2e-6, 'PMF does not sum to one')
    return p / sums[:, None], drift


def mean_and_median(p, centers):
    cdf = np.cumsum(p, axis=1)
    index = np.minimum((cdf < .5).sum(axis=1), len(centers) - 1)
    return p @ centers, centers[index]


def continuous_crps(p, centers, y):
    """Integrate (F(z)-1[y<=z])² exactly over discrete-support CDF segments.

    Different derivation from the training evaluator's energy-distance formula.
    Nondecreasing repeated support points are valid for the tail-clamped score.
    """
    centers, y = np.asarray(centers), np.asarray(y)
    require(np.all(np.diff(centers) >= 0), 'Support must be sorted')
    width = np.diff(centers)
    left_of_y = np.clip(y[:, None] - centers[:-1], 0, width)
    cdf = np.cumsum(p, axis=1)[:, :-1]
    value = (cdf ** 2 * left_of_y + (1 - cdf) ** 2 * (width - left_of_y)).sum(axis=1)
    return value + np.maximum(centers[0] - y, 0) + np.maximum(y - centers[-1], 0)


def event_weights(ids):
    _, inverse, counts = np.unique(ids, return_inverse=True, return_counts=True)
    return (1 / counts[inverse]) / len(counts)


def cvar(values):
    return float(np.sort(values)[-max(1, int(np.ceil(.05 * len(values)))):].mean())


def point_metrics(y, pred, ids):
    error = np.abs(pred - y)
    macro = event_weights(ids)
    _, inverse, counts = np.unique(ids, return_inverse=True, return_counts=True)
    event_error = np.bincount(inverse, weights=error) / counts
    negative = y < 4
    result = dict(mae=float(error.mean()), medae=float(np.median(error)),
        rmse=float(np.sqrt(np.mean(error ** 2))), event_macro_mae=float(macro @ error),
        cvar95=cvar(error), event_macro_cvar95=cvar(event_error),
        fp4=int(np.sum((pred >= 4) & negative)), tp4=int(np.sum((pred >= 4) & ~negative)),
        fpr4=float(np.mean(pred[negative] >= 4)) if negative.any() else None,
        records=len(y), events=len(counts))
    for threshold in (4., 4.5, 5., 6.):
        use = y >= threshold
        key = f'm{threshold:g}'
        result.update({key + '_events': len(np.unique(ids[use])),
            key + '_records': int(use.sum()),
            key + '_mae': float(error[use].mean()) if use.any() else None,
            key + '_event_macro_mae': float(event_weights(ids[use]) @ error[use]) if use.any() else None,
            key + '_bias': float((pred[use] - y[use]).mean()) if use.any() else None,
            key + '_cvar95': cvar(error[use]) if use.any() else None})
    return result


def mean_score(value):
    finite = np.isfinite(value)
    return {'mean': float(value.mean()) if finite.all() else None,
            'infinite_records': int((~finite).sum())}


def distribution_metrics(p, centers, y, ids, marginal_weights):
    label = np.clip(np.floor(y.astype(np.float64) / .1 + 1e-5), 0, 65).astype(int)
    observed = label[:, None] <= np.arange(65)
    cdf = np.cumsum(p, axis=1)[:, :-1]
    square = (cdf - observed) ** 2
    survival = np.cumsum(p[:, ::-1], axis=1)[:, -2::-1]
    with np.errstate(divide='ignore'):
        ce = -np.log(p[np.arange(len(y)), label])
        rank = -.1 * np.log(np.where(observed, cdf, survival)).sum(axis=1)
    exact = continuous_crps(p, centers, y)
    tail_exact = continuous_crps(p, np.maximum(centers, 4), np.maximum(y, 4))
    grid = .1 * square.sum(axis=1)
    tail = y >= 4
    probability = p[:, centers >= 4].sum(axis=1)
    brier = (probability - tail) ** 2
    weight = event_weights(ids)
    result = {'crps': float(exact.mean()), 'event_macro_crps': float(weight @ exact),
        'tail_crps4': float(tail_exact.mean()), 'event_macro_tail_crps4': float(weight @ tail_exact),
        'brier4': float(brier.mean()), 'event_macro_brier4': float(weight @ brier),
        'quantized_grid_crps': float(grid.mean()),
        'quantized_tail_grid_crps': float((.1 * square @ (1 + 4 * (np.arange(1, 66) >= 40))).mean()),
        'quantized_marginal_grid_crps': float((.1 * square @ marginal_weights).mean()),
        'quantized_ranked_log_score': mean_score(rank), 'categorical_nll': mean_score(ce),
        'continuous_minus_quantized_crps': float((exact - grid).mean()),
        'max_abs_continuous_minus_quantized_crps': float(np.max(np.abs(exact - grid))),
        'target_outside_center_support': int(((y < centers[0]) | (y > centers[-1])).sum())}
    # Fixed reliability bins, never chosen from performance. Macro weighting
    # gives each earthquake total weight one, including repeated station rows.
    bins = np.minimum((probability * 10).astype(int), 9)
    rows, ece, macro_ece = [], 0., 0.
    for index in range(10):
        use = bins == index
        if not use.any():
            rows.append({'bin': index, 'records': 0, 'events': 0})
            continue
        forecast, actual = float(probability[use].mean()), float(tail[use].mean())
        w = weight[use]
        mf, ma = float(w @ probability[use] / w.sum()), float(w @ tail[use] / w.sum())
        ece += use.mean() * abs(forecast - actual)
        macro_ece += w.sum() * abs(mf - ma)
        rows.append({'bin': index, 'records': int(use.sum()), 'events': len(np.unique(ids[use])),
            'predicted': forecast, 'observed': actual, 'event_macro_predicted': mf,
            'event_macro_observed': ma, 'event_macro_mass': float(w.sum())})
    result['tail_calibration'] = dict(predicted=float(probability.mean()), observed=float(tail.mean()),
        event_macro_predicted=float(weight @ probability), event_macro_observed=float(weight @ tail),
        ece10=float(ece), event_macro_ece10=float(macro_ece), bins=rows)
    result['intervals'] = {}
    cumulative = np.cumsum(p, axis=1)
    for coverage in (.5, .8, .9):
        alpha = 1 - coverage
        lo_index = np.minimum((cumulative < alpha / 2).sum(axis=1), 65)
        hi_index = np.minimum((cumulative < 1 - alpha / 2).sum(axis=1), 65)
        lo, hi = centers[lo_index], centers[hi_index]
        hit = (y >= lo) & (y <= hi)
        grid_hit = (label >= lo_index) & (label <= hi_index)
        result['intervals'][str(coverage)] = dict(coverage=float(hit.mean()),
            event_macro_coverage=float(weight @ hit), mean_width=float((hi - lo).mean()),
            m4_coverage=float(hit[tail].mean()) if tail.any() else None,
            quantized_bin_set_coverage=float(grid_hit.mean()),
            event_macro_quantized_bin_set_coverage=float(weight @ grid_hit),
            m4_quantized_bin_set_coverage=float(grid_hit[tail].mean()) if tail.any() else None,
            interpretation='coverage uses continuous y within center endpoints; bin-set coverage uses the scored clipped category')
    return result


def compare_metrics(actual, reported, probability=False):
    max_difference = 0.
    for key, expected in reported.items():
        if not probability and key in ('crps', 'tail_crps4', 'brier4'):
            continue
        require(key in actual, f'Missing independently computed metric {key}')
        value = actual[key]
        if expected is None:
            require(value is None, f'None disagreement: {key}')
        else:
            require(value is not None and np.isfinite(value), f'Nonfinite metric: {key}')
            difference = abs(value - expected)
            require(difference <= (3e-6 if key in ('crps', 'tail_crps4', 'brier4') else 2e-10),
                    f'Metric mismatch {key}: {value} != {expected}')
            max_difference = max(max_difference, difference)
    return max_difference


def validate_prediction(p, centers, stored_mean, stored_median):
    mean, med = mean_and_median(p, centers)
    require(np.allclose(mean, stored_mean, atol=2e-6, rtol=0), 'Saved PMF mean differs from saved prediction')
    mismatched = med != stored_median
    # Saving float64 probabilities as float32 can cross a .5 CDF tie. Accept
    # only bracketing quantiles whose pre/post CDF encloses .5 within roundoff.
    for row in np.flatnonzero(mismatched):
        matches = np.flatnonzero(centers == stored_median[row])
        require(len(matches) == 1, 'Saved median outside support')
        index = matches[0]
        before, after = p[row, :index].sum(), p[row, :index + 1].sum()
        require(before <= .5 + 2e-7 and after >= .5 - 2e-7, 'Saved median is not a valid PMF quantile')
    return {'mean_max_abs': float(np.max(np.abs(mean - stored_mean))),
            'float32_boundary_median_ambiguities': int(mismatched.sum())}


def verify_manifest(run):
    manifest = load_json(run / 'artifacts.json')
    require('identity.json' in manifest, 'Incomplete artifact manifest')
    require(set(manifest) == {p.name for p in run.iterdir() if p.is_file() and p.name != 'artifacts.json'},
            'Unlisted or missing artifact')
    for name, item in manifest.items():
        require(Path(name).name == name and not (run / name).is_symlink(), 'Unsafe artifact path')
        require((run / name).stat().st_size == item['bytes'], f'Byte count mismatch: {name}')
        require(sha256(run / name) == item['sha256'], f'Artifact hash mismatch: {name}')
    identity = load_json(run / 'identity.json')
    canonical = json.dumps(identity, sort_keys=True, allow_nan=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:12]
    require(f'_{digest}_' in run.name, 'Run directory does not match configuration/source digest')
    return manifest, identity


def verify_sources(identity, source_root):
    found = {}
    for name, expected in identity['source_sha256'].items():
        require(Path(name).name == name, 'Unsafe source basename')
        candidates = [source_root / 'research/2026-10-09/phase2' / name,
                      source_root / 'research/2026-10-09' / name]
        matches = [p for p in candidates if p.is_file()]
        require(len(matches) == 1, f'Source missing/ambiguous: {name}')
        found[name] = sha256(matches[0])
        require(found[name] == expected, f'Live source differs from archived identity: {name}')
    return found


def verify_training(run, prior, train, config):
    require(len(train['targets']) == config['expected_train_records'], 'Unexpected TRAIN record count')
    require(config['max_per_event'] == 0, 'This audit requires the full TRAIN protocol')
    require(np.array_equal(train['row_index'], np.arange(len(train['targets']))), 'TRAIN row order is not exhaustive')
    require(np.isfinite(train['targets']).all(), 'Nonfinite TRAIN target')
    require(np.array_equal(train['weights'], np.ones(len(train['targets']))), 'Unexpected full-TRAIN inclusion weight')
    mapping = {'targets': 'targets_sha256', 'weights': 'weights_sha256', 'row_index': 'row_index_sha256',
               'event_ids': 'event_ids_sha256', 'trace_names': 'trace_names_sha256'}
    for name, digest in mapping.items():
        require(array_digest(train[name]) == prior[digest], f'TRAIN array digest mismatch: {name}')
    labels = np.clip(np.floor(train['targets'].astype(float) / .1 + 1e-5), 0, 65).astype(int)
    mass = np.bincount(labels, weights=train['weights'].astype(float), minlength=66)
    cdf = np.cumsum(mass)[:-1] / mass.sum()
    u = np.minimum(25, 1 / (.01 + cdf * (1 - cdf)))
    weight = (u / u.mean()).astype(np.float32)
    require(prior['source_split'] == 'train', 'Prior is not TRAIN-only')
    require(np.array_equal(mass, prior['weighted_bin_mass']), 'TRAIN prior histogram mismatch')
    require(np.allclose(cdf, prior['cdf'], atol=1e-15, rtol=0), 'TRAIN CDF mismatch')
    require(np.array_equal(weight, np.asarray(prior['weights'], dtype=np.float32)), 'Prior weight mismatch')
    return weight


def model_digest(state):
    h = hashlib.sha256()
    for key, tensor in state.items():
        h.update(key.encode())
        h.update(array_digest(tensor.detach().cpu().numpy()).encode())
    return h.hexdigest()


def audit_run(run, source_root, reference):
    started = time.monotonic()
    manifest, identity = verify_manifest(run)
    config = identity['config']
    require(tuple(config['controls']) == CONTROLS and tuple(config['seeds']) == SEEDS, 'Grid differs from prespecified controls/seeds')
    require(config['epochs'] == 15, 'Final epoch differs from prespecified 15')
    source_hashes = verify_sources(identity, source_root)
    require(reference.name == f"validation_{config['seconds']}s.npz", 'Only a named validation reference may be read')
    inputs = load_json(run / 'input_identities.json')
    require(sha256(reference) == inputs['validation_reference_sha256'], 'Validation reference hash mismatch')
    ref, saved = load_npz(reference), load_npz(run / 'predictions.npz')
    for key in ('targets', 'event_ids', 'trace_names'):
        require(np.array_equal(ref[key], saved[key]), f'Prediction/reference alignment mismatch: {key}')
    y, ids, centers = saved['targets'].astype(float), saved['event_ids'], ref['centers'].astype(float)
    require(len(y) and np.isfinite(y).all(), 'Invalid validation targets')
    require(centers.shape == (66,) and np.allclose(centers, np.arange(66) * .1 + .05, atol=1e-6), 'Magnitude support changed')
    require(len(np.unique(saved['trace_names'])) == len(y), 'Duplicate validation trace')
    train = load_npz(run / 'training_rows.npz')
    prior = load_json(run / 'train_marginal_prior.json')
    require(prior['input_identities'] == inputs, 'Prior/source identities disagree')
    weight = verify_training(run, prior, train, config)
    require(not np.intersect1d(train['event_ids'], ids).size, 'TRAIN/validation event overlap')
    require(not np.intersect1d(train['trace_names'], saved['trace_names']).size, 'TRAIN/validation trace overlap')
    require(len(np.unique(train['trace_names'])) == len(train['trace_names']), 'Duplicate TRAIN trace')
    reported, traces, history = (load_json(run / name) for name in ('metrics.json', 'training_traces.json', 'history.json'))
    import torch
    torch.set_num_threads(1)
    replayed_orders = str(torch.__version__) == config['runtime']['torch']
    expected_keys = {f'{control}_seed{seed}' for control in CONTROLS for seed in SEEDS}
    require(set(traces) == expected_keys and set(history) == expected_keys, 'Missing or extra model/training history')
    checkpoints, normalizer = {}, None
    for seed in SEEDS:
        seed_traces = [traces[f'{control}_seed{seed}'] for control in CONTROLS]
        require(all(t['initial_model_sha256'] == seed_traces[0]['initial_model_sha256'] and
                    t['epoch_order_sha256'] == seed_traces[0]['epoch_order_sha256'] for t in seed_traces),
                'Unmatched initialization/order across controls')
        require(len(seed_traces[0]['epoch_order_sha256']) == 15, 'Missing epoch orders')
        if replayed_orders:
            generator = torch.Generator(device='cpu').manual_seed(seed)
            expected_orders = [array_digest(torch.randperm(len(train['targets']), generator=generator).numpy())
                               for _ in range(15)]
            require(expected_orders == seed_traces[0]['epoch_order_sha256'], 'Realized order differs from seeded CPU replay')
        for control in CONTROLS:
            key = f'{control}_seed{seed}'
            require(len(history[key]) == 15 and np.isfinite(history[key]).all(), 'Invalid fixed-epoch loss history')
            checkpoint = torch.load(run / f'{key}.pth', map_location='cpu', weights_only=True)
            require(checkpoint['config'] == config and checkpoint['seed'] == seed and checkpoint['control'] == control,
                    'Checkpoint protocol identity mismatch')
            state = checkpoint['model']
            shapes = {'net.0.weight': (128, 291), 'net.0.bias': (128,),
                      'net.3.weight': (64, 128), 'net.3.bias': (64,),
                      'net.5.weight': (66, 64), 'net.5.bias': (66,)}
            require(set(state) == set(shapes) and all(tuple(state[k].shape) == v for k, v in shapes.items()),
                    'Saved residual-head architecture differs')
            require(all(torch.isfinite(t).all().item() for t in state.values()), 'Nonfinite model parameters')
            require(model_digest(state) == traces[key]['final_model_sha256'], 'Final model hash mismatch')
            require(sum(t.numel() for t in state.values()) == traces[key]['parameters'], 'Model parameter count mismatch')
            require(np.array_equal(checkpoint['feature_mask'].numpy(), np.r_[np.ones(279), np.zeros(12)]), 'Feature mask changed')
            require(np.array_equal(checkpoint['training_prior_weights'].numpy(), weight), 'Model prior differs from audited TRAIN prior')
            statistics = {k: checkpoint[k].numpy() for k in ('feature_mean', 'feature_std', 'feature_mask')}
            require(all(a.shape == (291,) and np.isfinite(a).all() for a in statistics.values()), 'Invalid saved feature normalization')
            require(np.all(statistics['feature_std'] > 0), 'Nonpositive feature standard deviation')
            if normalizer is None:
                normalizer = statistics
            else:
                require(all(np.array_equal(statistics[k], normalizer[k]) for k in statistics), 'Unmatched feature normalization')
            checkpoints[key] = {'sha256': manifest[f'{key}.pth']['sha256'], 'model_sha256': model_digest(state)}
    all_metrics, checks = {}, {}
    for decision in ('mean', 'median'):
        key = 'raw_' + decision
        actual = point_metrics(y, saved[key], ids)
        compare_metrics(actual, reported[key])
        all_metrics[key] = {'point': actual, 'distribution': None,
            'limitation': 'Raw recomputed CNN PMF was not saved; only point metrics independently verified.'}
    for control in CONTROLS:
        data = load_npz(run / f'{control}_probabilities.npz')
        require(set(data) == {'targets', 'event_ids', 'trace_names', 'centers', 'mean_probability',
                             *[f'seed{seed}' for seed in SEEDS]}, 'Unexpected PMF artifact schema')
        for key in ('targets', 'event_ids', 'trace_names', 'centers'):
            require(np.array_equal(data[key], ref[key]), f'PMF identity alignment mismatch: {key}')
        seed_values = [data[f'seed{seed}'].astype(float) for seed in SEEDS]
        ensemble_diff = float(np.max(np.abs(data['mean_probability'] - np.mean(seed_values, axis=0))))
        require(ensemble_diff <= 9e-8, 'Ensemble PMF is not the equal seed average')
        for name, value in [(f'seed{seed}', data[f'seed{seed}']) for seed in SEEDS] + [('ensemble', data['mean_probability'])]:
            key = f'{control}_{name}'
            p, drift = validate_probability(value, len(y), 66)
            check = validate_prediction(p, centers, saved[key + '_mean'], saved[key + '_median'])
            score = distribution_metrics(p, centers, y, ids, weight)
            for decision in ('mean', 'median'):
                actual = point_metrics(y, saved[key + '_' + decision], ids)
                delta = compare_metrics(dict(actual, **score), reported[key + '_' + decision], probability=True)
                all_metrics[key + '_' + decision] = {'point': actual, 'distribution': score}
            checks[key] = dict(check, pmf_sum_max_drift=drift, ensemble_pmf_max_abs=ensemble_diff,
                               reported_metric_max_abs=delta)
    require(set(all_metrics) == set(reported), 'Missing or extra reported comparison')
    result = {'status': 'PASS', 'seconds': config['seconds'], 'run': str(run.resolve()),
        'artifact_manifest_sha256': sha256(run / 'artifacts.json'), 'identity_sha256': manifest['identity.json']['sha256'],
        'source_sha256': source_hashes, 'reference_sha256': sha256(reference),
        'audit_source_sha256': sha256(Path(__file__)),
        'runtime': {'python': platform.python_version(), 'numpy': np.__version__, 'torch': str(torch.__version__),
                    'torch_threads': torch.get_num_threads(), 'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES']},
        'checkpoints': checkpoints, 'probability_checks': checks, 'metrics': all_metrics,
        'seeded_epoch_orders_replayed': replayed_orders,
        'train_records': len(train['targets']), 'train_events': len(np.unique(train['event_ids'])),
        'validation_records': len(y), 'validation_events': len(np.unique(ids)),
        'validation_status': 'Repeatedly reused exploratory validation, no model or threshold selection in this audit.',
        'limits': ['Saved model tensor digests verified; full input-to-model inference is a separate bounded replay.',
                  'Float32 saved PMFs are normalized by row only after a 2e-6 sum tolerance check.',
                  'PMF scores recomputed to 3e-6 tolerance; point metrics recomputed from saved float64 decisions.',
                  'Training objectives target clipped bin labels; continuous-target CRPS is separately integrated.',
                  'Artifact hashes establish internal consistency, not external authentication.',
                  'Cached waveform bytes and original metadata membership are not re-extracted in this audit.'],
        'wall_seconds': time.monotonic() - started}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refuse to overwrite an audit report')
    require(args.run.resolve() not in args.output.resolve().parents, 'Audit output must be outside immutable run')
    result = audit_run(args.run, args.source_root, args.reference)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('status', 'seconds', 'validation_records', 'wall_seconds')}))


if __name__ == '__main__':
    main()

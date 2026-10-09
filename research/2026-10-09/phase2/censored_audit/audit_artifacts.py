"""Read completed censored-pilot artifacts on CPU; emit a small JSON audit.

Never imports training code, Torch, waveforms, or TEST data. Writes only stdout.
"""
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ARMS = ('frozen', 'censored', 'hurdle', 'hurdle_truncated', 'uncensored', 'discriminative')
SEEDS = (20261009, 20261010)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for b in iter(lambda: handle.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def check_probability(p, n, k):
    if p.shape != (n, 3, k) or not np.isfinite(p).all() or (p < 0).any():
        raise ValueError('Invalid probability shape/value')
    error = float(np.max(np.abs(p.sum(-1) - 1)))
    if error > 1e-12:
        raise ValueError('Probability normalization failed')
    return error


def discrete_crps(p, centers, y):
    """Independent exact CDF integral, including observations off support."""
    c = np.asarray(centers)
    widths = np.diff(c)
    if (widths < 0).any():
        raise ValueError('Centers not ordered')
    f = np.cumsum(p, axis=1)[:, :-1]
    left = np.clip(y[:, None] - c[None, :-1], 0, widths)
    return (f*f*left + (f-1)**2*(widths-left)).sum(1) + np.maximum(c[0]-y, 0) + np.maximum(y-c[-1], 0)


def event_mean(values, ids):
    _, ix, counts = np.unique(ids, return_inverse=True, return_counts=True)
    return float((np.bincount(ix, weights=values) / counts).mean())


def decisions_and_scores(p, centers, y, ids):
    cdf = np.cumsum(p, 1)
    decisions = {'mean': p @ centers, 'median': centers[np.minimum((cdf < .5).sum(1), len(centers)-1)]}
    tail = y >= 4
    p4 = p[:, centers >= 4].sum(1)
    labels = np.clip(np.floor(y/.1 + 1e-5).astype(int), 0, len(centers)-1)
    nll = -np.log(np.maximum(p[np.arange(len(y)), labels], np.finfo(float).tiny))
    scores = {'crps': float(discrete_crps(p, centers, y).mean()),
              'tail_crps4': float(discrete_crps(p, np.maximum(centers, 4), np.maximum(y, 4)).mean()),
              'brier4': float(((p4-tail)**2).mean()), 'categorical_nll': float(nll.mean()),
              'event_macro_categorical_nll': event_mean(nll, ids),
              'mean_p4': float(p4.mean()), 'observed_p4': float(tail.mean()),
              'zero_label_probabilities': int((p[np.arange(len(y)), labels] == 0).sum())}
    result = {}
    for name, pred in decisions.items():
        e = np.abs(pred-y)
        nworst = max(1, math.ceil(.05*len(y)))
        m = {'mae': float(e.mean()), 'medae': float(np.median(e)), 'rmse': float(np.sqrt(np.mean(e*e))),
             'cvar95': float(np.partition(e, len(e)-nworst)[-nworst:].mean()),
             'event_macro_mae': event_mean(e, ids), 'fp4': int(((pred >= 4) & ~tail).sum()),
             'tp4': int(((pred >= 4) & tail).sum()), 'fpr4': float((pred[~tail] >= 4).mean()), **scores}
        for threshold in (4, 4.5, 5, 6):
            keep = y >= threshold
            key = f'm{threshold:g}'
            m[key+'_mae'] = float(e[keep].mean()) if keep.any() else None
            m[key+'_event_macro_mae'] = event_mean(e[keep], ids[keep]) if keep.any() else None
            m[key+'_bias'] = float((pred[keep]-y[keep]).mean()) if keep.any() else None
        result[name] = m
    return decisions, result


def reliability(forecast, observed):
    if not len(forecast):
        return {'records': 0}
    bins, error = [], 0.
    for i in range(10):
        keep = (forecast >= i/10) & (forecast < (i+1)/10 if i < 9 else forecast <= 1)
        if keep.any():
            p, q = float(forecast[keep].mean()), float(observed[keep].mean())
            bins.append({'bin': i, 'records': int(keep.sum()), 'predicted': p, 'observed': q})
            error += keep.sum()*abs(p-q)/len(forecast)
    rate = float(observed.mean())
    return {'records': len(forecast), 'predicted': float(forecast.mean()), 'observed': rate,
            'brier': float(np.mean((forecast-observed)**2)), 'constant_prevalence_brier': rate*(1-rate),
            'ece10_descriptive': error, 'bins': bins}


def bounded_calibration(numbers):
    """Record and clip only float64 endpoint roundoff in saved diagnostics."""
    if not np.isfinite(numbers).all() or ((numbers < -1e-12) | (numbers > 1+1e-12)).any():
        raise ValueError('Invalid probability calibration diagnostic')
    info = {'endpoint_roundoff_count': int(((numbers < 0) | (numbers > 1)).sum()),
            'raw_minimum': float(numbers.min()) if len(numbers) else None,
            'raw_maximum': float(numbers.max()) if len(numbers) else None}
    return np.clip(numbers, 0, 1), info


def compared_metric_difference(actual, reported):
    if not np.isfinite(actual) or not np.isfinite(reported):
        raise ValueError('Nonfinite metric cannot certify agreement')
    return abs(actual-reported)


def audit(directory):
    root = Path(directory)
    run = json.loads((root/'run.json').read_text())
    if run.get('status') != 'complete':
        raise ValueError('Only a completed run can be audited')
    manifest = json.loads((root/'artifacts.json').read_text())['files']
    checked = {}
    def verify(name):
        path = root/name
        actual = {'bytes': path.stat().st_size, 'sha256': sha(path)}
        if actual != manifest[name]:
            raise ValueError(f'Artifact identity mismatch: {name}')
        checked[name] = actual
        return path
    for name in ('run.json', 'metrics.json', 'history.json', 'mechanism.json', 'frozen_start_provenance.json', 'observation_provenance.json'):
        verify(name)
    reported = json.loads((root/'metrics.json').read_text())
    history = json.loads((root/'history.json').read_text())
    if run['seeds'] != list(SEEDS) or run['controls'] != list(ARMS) or run['epochs'] != 15:
        raise ValueError('Unexpected seeds, controls or fixed epoch budget')
    for seed in SEEDS:
        reference_order = None
        for arm in ARMS[1:]:
            h = history[f'{arm}_seed{seed}']
            order = [row['row_order_sha256'] for row in h]
            if len(h) != 15 or [row['epoch'] for row in h] != list(range(1,16)) or not np.isfinite([row['loss'] for row in h]).all():
                raise ValueError('Incomplete/nonfinite training history')
            if reference_order is None:
                reference_order = order
            elif order != reference_order:
                raise ValueError('Training row order differs across controls')
    obs = {}
    for split in ('train', 'val'):
        with np.load(verify(split+'_observations.npz'), allow_pickle=False) as f:
            obs[split] = {k: f[k] for k in f.files}
    v = obs['val']; y, ids, traces = v['targets'], v['event_ids'], v['trace_names']
    if len(y) != 96993 or len(obs['train']['targets']) != 197676:
        raise ValueError('Unexpected pilot population')
    if set(obs['train']['event_ids']) & set(ids):
        raise ValueError('TRAIN/VAL event overlap')
    mask_summary = {}
    for split, o in obs.items():
        if not np.array_equal(o['valid'], o['invalid_reason_code'] == 0):
            raise ValueError('Invalid reasons disagree with masks')
        if not np.array_equal(o['g'], np.maximum(o['z'], 0)):
            raise ValueError('G and Z disagree')
        entries = {}
        for j, deadline in enumerate((3, 5)):
            entries[str(deadline)] = {'valid': int(o['valid'][:,j].sum()), 'total': len(o['targets']),
                'invalid_tail': int(((~o['valid'][:,j]) & (o['targets'] >= 4)).sum()),
                'codes': {str(int(c)): int((o['invalid_reason_code'][:,j] == c).sum()) for c in np.unique(o['invalid_reason_code'][:,j])}}
        mask_summary[split] = entries
    anchor = {}
    for seed in SEEDS:
        with np.load(verify(f'frozen_p1_seed{seed}.npz'), allow_pickle=False) as f:
            anchor[seed] = np.exp(f['val_log_probability'])
            centers = f['centers']
    output = {'run': run, 'observation_masks': mask_summary, 'metrics': {}, 'integrity': {}, 'calibration': {}, 'tail_events': {}}
    max_metric_difference = 0.
    saved_frozen_p1 = {}
    for arm in ARMS:
        expected_ensemble = None
        for tag in [f'seed{s}' for s in SEEDS] + ['ensemble']:
            name = f'{arm}_{tag}'
            with np.load(verify(name+'_probabilities.npz'), allow_pickle=False) as f:
                for key, expected in [('targets', y), ('event_ids', ids), ('trace_names', traces), ('centers', centers), ('deadlines', np.array([1,3,5]))]:
                    if not np.array_equal(f[key], expected):
                        raise ValueError(f'Probability identity mismatch {name}/{key}')
                p = f['probability']
            integrity = {'normalization_max_error': check_probability(p, len(y), len(centers))}
            if tag == 'ensemble':
                integrity['ensemble_max_error'] = float(np.max(np.abs(p-expected_ensemble)))
                if not np.array_equal(p, expected_ensemble):
                    raise ValueError('Ensemble differs from exact saved-seed arithmetic')
                a = sum(anchor.values())/2
            else:
                seed = int(tag[4:]); a = anchor[seed]
                if expected_ensemble is None:
                    expected_ensemble = p/2
                else:
                    expected_ensemble += p/2
            integrity['p1_max_error'] = float(np.max(np.abs(p[:,0]-a)))
            if not np.allclose(p[:,0], a, atol=1e-15, rtol=1e-14):
                raise ValueError('Starting prior drift')
            if arm == 'frozen':
                saved_frozen_p1[tag] = p[:,0].copy()
                if not np.array_equal(p[:,0],p[:,1]) or not np.array_equal(p[:,0],p[:,2]):
                    raise ValueError('Frozen control changed over deadlines')
            integrity['p1_bit_identical_to_frozen'] = bool(np.array_equal(p[:,0],saved_frozen_p1[tag]))
            if not integrity['p1_bit_identical_to_frozen']:
                raise ValueError('Arm changed saved one-second probabilities')
            for j in range(2):
                keep = ~v['valid'][:,j]
                integrity[f'invalid_step{j}_unchanged'] = bool(np.array_equal(p[keep,j+1], p[keep,j]))
                if not integrity[f'invalid_step{j}_unchanged']:
                    raise ValueError('Invalid update changed predictions')
            output['integrity'][name] = integrity
            for j, deadline in enumerate((1,3,5)):
                decisions, scores = decisions_and_scores(p[:,j], centers, y, ids)
                for decision, values in scores.items():
                    key = f'{name}_{deadline}s_{decision}'
                    output['metrics'][key] = values
                    for metric, value in values.items():
                        if metric in reported[key] and value is not None:
                            max_metric_difference = max(max_metric_difference, compared_metric_difference(value,reported[key][metric]))
                    event_rows = []
                    for event in np.unique(ids[y >= 4]):
                        keep = ids == event
                        event_rows.append({'event_id': str(event), 'magnitude': float(y[keep][0]), 'records': int(keep.sum()),
                                           'mae': float(np.abs(decisions[decision][keep]-y[keep]).mean()),
                                           'bias': float((decisions[decision][keep]-y[keep]).mean())})
                    output['tail_events'][key] = event_rows
            if tag != 'ensemble' and arm not in ('frozen','discriminative'):
                with np.load(verify(name+'_mechanism.npz'), allow_pickle=False) as f:
                    if not np.array_equal(f['valid'],v['valid']) or not np.array_equal(f['event_ids'],ids) or not np.array_equal(f['trace_names'],traces):
                        raise ValueError('Mechanism identity mismatch')
                    details = {}
                    for j, deadline in enumerate((3,5)):
                        keep = v['valid'][:,j]
                        positive = keep & (v['z'][:,j] > 0)
                        zero, zero_roundoff = bounded_calibration(f['zero_probability'][keep,j])
                        pit, pit_roundoff = bounded_calibration(f['positive_pit'][positive,j])
                        tail_zero, _ = bounded_calibration(f['zero_probability'][keep & (y >= 4),j])
                        if not np.array_equal(f['positive_valid'][:,j],positive):
                            raise ValueError('Positive PIT mask mismatch')
                        step = {'zero': reliability(zero,v['z'][keep,j] <= 0),
                                'tail_zero': reliability(tail_zero,v['z'][keep & (y >= 4),j] <= 0),
                                'roundoff': {'zero_probability': zero_roundoff, 'positive_pit': pit_roundoff},
                                'conditional_nll': float(f['conditional_nll'][keep,j].mean()),
                                'forecast_nll': float(f['forecast_nll'][keep,j].mean()),
                                'positive_pit_mean': float(pit.mean()),
                                'positive_pit_histogram': np.histogram(pit,np.linspace(0,1,11))[0].tolist()}
                        details[str(deadline)] = step
                    output['calibration'][name] = details
    output['max_reported_metric_difference'] = max_metric_difference
    if max_metric_difference > 1e-10:
        raise ValueError('Independent metrics disagree with runner')
    output['checked_artifacts'] = checked
    output['scope'] = 'CPU-only completed TRAIN/VAL artifacts; no waveforms, TEST or Torch. Calibration descriptive, records clustered within events.'
    return output


if __name__ == '__main__':
    print(json.dumps(audit(sys.argv[1]), allow_nan=False, indent=2))

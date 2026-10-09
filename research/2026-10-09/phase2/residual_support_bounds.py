"""Optimistic per-record bounds for bounded residual logits, not a predictor.

For q_k proportional to p_k exp(delta_k), |delta_k| <= bound, extrema
of the mean occur at threshold vertices: emphasize a low or high suffix.
These closed-box bounds are infima/suprema for a tanh parameterization.
They ignore shared network capacity and do not imply achievable test error.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def mean_bounds(probability, centers, bound=5.):
    p = np.asarray(probability, dtype=np.float64)
    c = np.asarray(centers, dtype=np.float64)
    if p.ndim != 2 or not len(p) or p.shape[1] < 2 or c.shape != (p.shape[1],):
        raise ValueError('Require nonempty rows of probabilities and matching centers')
    if (not np.isfinite(p).all() or (p < 0).any() or not np.isfinite(c).all()
            or not (np.diff(c) > 0).all()
            or not np.allclose(p.sum(1), 1., rtol=0, atol=1e-12)):
        raise ValueError('Require normalized nonnegative probabilities and ordered finite centers')
    if not np.isfinite(bound) or not 0 <= bound <= 25:
        raise ValueError('Bound must be finite and between 0 and 25')
    # Normalize roundoff only; never invent probability mass at zero-support bins.
    p = p / p.sum(1, keepdims=True)
    mass = p * c
    total = mass.sum(1, keepdims=True)
    zero = np.zeros((len(p), 1))
    low_p = np.concatenate([zero, p.cumsum(1)], axis=1)
    low_m = np.concatenate([zero, mass.cumsum(1)], axis=1)
    high_p = np.concatenate([p[:, ::-1].cumsum(1)[:, ::-1], zero], axis=1)
    high_m = np.concatenate([mass[:, ::-1].cumsum(1)[:, ::-1], zero], axis=1)
    ratio_minus_one = np.expm1(2 * bound)
    lower = ((total + ratio_minus_one * low_m) / (1 + ratio_minus_one * low_p)).min(1)
    upper = ((total + ratio_minus_one * high_m) / (1 + ratio_minus_one * high_p)).max(1)
    return lower, upper


def summarize(probability, centers, targets, event_ids, bound=5.):
    p = np.asarray(probability, dtype=np.float64)
    y = np.asarray(targets, dtype=np.float64)
    ids = np.asarray(event_ids)
    lower, upper = mean_bounds(p, centers, bound)
    if y.shape != lower.shape or ids.shape != y.shape or not np.isfinite(y).all():
        raise ValueError('Targets and event identities must align with finite probability rows')
    p = p / p.sum(1, keepdims=True)
    floor = np.maximum.reduce([lower - y, y - upper, np.zeros(len(y))])
    high = p[:, np.asarray(centers) >= 4].sum(1)
    ratio = np.exp(2 * bound)
    max_high = ratio * high / (1 + (ratio - 1) * high)
    result = {'records': len(y), 'events': len(np.unique(ids)), 'bound': bound,
              'all_mean_error_floor': float(floor.mean())}
    for threshold in [4., 5.]:
        selected = y >= threshold
        n = int(selected.sum())
        key = f'm{threshold:g}'
        result[key] = {'records': n, 'events': len(np.unique(ids[selected])),
                      'mean_error_floor': float(floor[selected].mean()) if n else None,
                      'fraction_target_above_max': float((y[selected] > upper[selected] + 1e-10).mean()) if n else None,
                      'upper_mean_quantiles': np.quantile(upper[selected], [0, .1, .5, .9, 1]).tolist() if n else None}
    tail = y >= 4
    result['m4']['fraction_provably_unable_to_reach_m4_median'] = float((max_high[tail] < .5 - 1e-12).mean()) if tail.any() else None
    result['interpretation'] = ('Optimistic hindsight per-record closure lower bound; not learned or attainable-network error. '
                                'Small floor rejects the correction range as the sole explanation, not as a possible local constraint.')
    return result


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Do not overwrite an earlier audit')
    report = {'schema': 'residual-logit-closure-bound-v1', 'source_sha256': file_sha256(__file__), 'windows': {}}
    for seconds in (1, 3, 5):
        path = args.input_root / f'validation_{seconds}s.npz'
        before = file_sha256(path)
        with np.load(path, allow_pickle=False) as data:
            logits = data['logits'].astype(np.float64)
            if logits.ndim != 2 or not np.isfinite(logits).all():
                raise ValueError('Invalid logits')
            exp = np.exp(logits - logits.max(1, keepdims=True))
            probability = exp / exp.sum(1, keepdims=True)
            result = summarize(probability, data['centers'], data['targets'], data['event_ids'])
        if file_sha256(path) != before:
            raise ValueError('Input changed during audit')
        result['input_sha256'] = before
        report['windows'][str(seconds)] = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()

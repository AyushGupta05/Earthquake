"""Run the locked conditional-density protocol. CPU only; TRAIN artifact only."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

import argparse
import hashlib
import json
import platform
import signal
import time
from pathlib import Path

import numpy as np
import torch

from shared_cap import (ARMS, COUNTERFACTUAL, PROTOCOL_SHA, Density, contrasts,
                        equal_event_weights, event_folds, initial_parameters,
                        sha256, validate_arrays)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def array_hash(array):
    a = np.ascontiguousarray(array)
    return hashlib.sha256(str((a.dtype.str, a.shape)).encode() + a.tobytes()).hexdigest()


def event_values(values, ids):
    unique, inv, counts = np.unique(ids, return_inverse=True, return_counts=True)
    return unique, np.bincount(inv, weights=values) / counts


def summarize(values, ids, targets, pit=None):
    result = {}
    for threshold in (None, 4., 4.5, 5.):
        mask = np.ones(len(ids), dtype=bool) if threshold is None else targets >= threshold
        key = 'all' if threshold is None else 'M_ge_' + str(threshold)
        if not mask.any():
            result[key] = {'records': 0, 'events': 0, 'nll': None}
            continue
        events, nll = event_values(values[mask], ids[mask])
        item = {'records': int(mask.sum()), 'events': len(events), 'nll': float(nll.mean())}
        if pit is not None and threshold in (None, 4.):
            # PIT bins use event weights as well, not an unlabelled row-micro count.
            weights = equal_event_weights(ids[mask])
            item['marginal_pit_event_weighted_bins'] = [
                np.histogram(pit[mask, j], bins=np.linspace(0, 1, 11), weights=weights)[0].tolist()
                for j in range(pit.shape[1])]
            item['marginal_pit_row_counts'] = [
                np.histogram(pit[mask, j], bins=np.linspace(0, 1, 11))[0].tolist()
                for j in range(pit.shape[1])]
        result[key] = item
    return result


def bootstrap(values, seed=20261019):
    if not len(values):
        return None
    rng = np.random.default_rng(seed)
    means = np.asarray([values[rng.integers(0, len(values), len(values))].mean() for _ in range(500)])
    return {'events': len(values), 'mean_delta': float(np.mean(values)),
            'ci95': np.quantile(means, [.025, .975]).tolist(), 'resamples': 500, 'seed': seed}


def fit(arm, initial, z, m, weights, options):
    model = Density(arm, initial)
    optimizer = torch.optim.LBFGS(model.parameters(), lr=1., max_iter=options['max_iter'],
                                 max_eval=options['max_eval'], history_size=options['history_size'],
                                 line_search_fn=options['line_search'], tolerance_grad=options['tolerance_grad'],
                                 tolerance_change=options['tolerance_change'])
    history = []
    started = time.monotonic()

    def closure():
        optimizer.zero_grad(set_to_none=True)
        value = -(weights * model.log_likelihood(z, m, 5)).sum()
        if not torch.isfinite(value):
            raise ValueError('Nonfinite objective')
        value.backward()
        if not torch.isfinite(model.raw.grad).all():
            raise ValueError('Nonfinite gradient')
        history.append(float(value.detach()))
        return value

    optimizer.step(closure)
    closure()
    if not torch.isfinite(model.raw).all():
        raise ValueError('Nonfinite fitted parameters')
    with torch.no_grad():
        _, _, cov = model.components(m[:1])
        if not (torch.linalg.eigvalsh(cov) > 0).all():
            raise ValueError('Nonpositive residual covariance')
    state = optimizer.state[model.raw]
    gradient_max = float(model.raw.grad.abs().max())
    return model, {'arm': arm, 'initial_raw': initial.tolist(), 'raw': model.raw.detach().tolist(),
                   'initial_sha256': array_hash(initial.numpy()), 'parameters': len(initial),
                   'closure_nll': history, 'iterations': int(state.get('n_iter', 0)),
                   'optimizer_function_evaluations': int(state.get('func_evals', 0)),
                   'final_gradient_max_abs': gradient_max,
                   'gradient_tolerance_met': gradient_max <= options['tolerance_grad'],
                   'iteration_limit_reached': state.get('n_iter', 0) >= options['max_iter'],
                   'evaluation_limit_reached': state.get('func_evals', 0) >= options['max_eval'],
                   'wall_seconds': time.monotonic() - started,
                   'residual_covariance': cov.tolist()}


def decide(scores, row_outputs, data, seeds):
    checks, pooled, support = [], {}, []
    for unit in (1, 2):
        for seed in seeds:
            key = f'unit{unit}_seed{seed}'
            entries = [scores.get(f'{key}_held{fold}') for fold in (0, 1)]
            if any(e is None for e in entries):
                support.append(key + ': missing supported fold')
                continue
            for fold, e in enumerate(entries):
                delta = e['shared_cap']['5']['all']['nll'] - e['moment_matched']['5']['all']['nll']
                checks.append({'test': key + f'_held{fold}_5s', 'delta': delta, 'pass': delta < 0})
            for deadline, group in [('3', 'all'), ('3', 'M_ge_4.0'), ('5', 'M_ge_4.0')]:
                count = sum(e['shared_cap'][deadline][group]['events'] for e in entries)
                if group != 'all' and count < 10:
                    support.append(key + f': insufficient tail events at {deadline}s ({count})')
                    continue
                if any(e['shared_cap'][deadline][group]['nll'] is None for e in entries):
                    support.append(key + f': empty fold tail at {deadline}s')
                    continue
                delta = np.mean([e['shared_cap'][deadline][group]['nll'] - e['moment_matched'][deadline][group]['nll']
                                 for e in entries])
                checks.append({'test': key + f'_{deadline}s_{group}_fold_mean',
                               'delta': float(delta), 'pass': bool(delta <= 0)})
            selected = []
            differences = []
            for fold in (0, 1):
                cap = row_outputs[f'{key}_held{fold}_shared_cap_5']
                mm = row_outputs[f'{key}_held{fold}_moment_matched_5']
                if not np.array_equal(cap[0], mm[0]):
                    raise ValueError('Unmatched evaluated rows')
                selected.append(cap[0])
                differences.append(mm[1] - cap[1])  # NLL_cap - NLL_mm = LL_mm - LL_cap.
            rows, diff = np.concatenate(selected), np.concatenate(differences)
            _, event_diff = event_values(diff, data['event_ids'][rows])
            pooled[key] = bootstrap(event_diff)
            checks.append({'test': key + '_5s_pooled_bootstrap', 'delta': pooled[key]['mean_delta'],
                           'pass': pooled[key]['ci95'][1] < 0})
    return {'checks': checks, 'paired_event_bootstrap_5s': pooled, 'support_notes': support,
            'all_numeric_gates_pass': bool(checks and all(c['pass'] for c in checks)),
            'general_two_unit_followup_gate': bool(checks and all(c['pass'] for c in checks) and not support),
            'interpretation': 'Likelihood diagnostic only. True M is given; no magnitude prediction or 1s improvement tested.'}


def run(args):
    root = Path(__file__).resolve().parent
    protocol_path = root / 'protocol.json'
    if sha256(protocol_path) != PROTOCOL_SHA:
        raise ValueError('Protocol changed after locking')
    protocol = json.loads(protocol_path.read_text())
    source = Path(args.source)
    if source.name != protocol['source_file'] or sha256(source) != protocol['source_sha256']:
        raise ValueError('Source artifact mismatch; only the pinned TRAIN file is allowed')
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    if torch.cuda.is_initialized():
        raise RuntimeError('CPU-only diagnostic found initialized CUDA')
    provenance = {'protocol_sha256': PROTOCOL_SHA, 'source_sha256': sha256(source),
                  'source_path': str(source), 'source_bytes': source.stat().st_size,
                  'code_sha256': {name: sha256(root / name) for name in ('shared_cap.py', 'run_preflight.py', 'test_shared_cap.py')},
                  'python': platform.python_version(), 'numpy': np.__version__, 'torch': torch.__version__,
                  'torch_threads': torch.get_num_threads(), 'CUDA_VISIBLE_DEVICES': os.environ['CUDA_VISIBLE_DEVICES'],
                  'start_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'status': 'running'}
    write_json(destination / 'provenance.json', provenance)
    started = time.monotonic()
    try:
        with np.load(source, allow_pickle=False) as f:
            data = validate_arrays({key: f[key] for key in protocol['required_columns']}, protocol)
        folds = event_folds(data['event_ids'], protocol['split_salt'])
        data['event_fold'] = folds
        np.savez_compressed(destination / 'identities_masks_observations.npz', **data)
        provenance['array_sha256'] = {key: array_hash(value) for key, value in data.items()}
        summary = {'total_rows': len(folds), 'total_events': len(np.unique(data['event_ids'])), 'strata': {}}
        for unit in (0, 1, 2):
            for fold in (0, 1):
                mask = (data['physical_unit_z'] == unit) & (folds == fold)
                summary['strata'][f'unit{unit}_fold{fold}'] = {
                    'records': int(mask.sum()), 'events': len(np.unique(data['event_ids'][mask])),
                    'valid3': int((mask & data['valid'][:, 0]).sum()), 'valid5': int((mask & data['valid'][:, 1]).sum()),
                    'invalid_reason_counts': {str(code): int((data['invalid_reason_code'][mask] == code).sum())
                                              for code in np.unique(data['invalid_reason_code'][mask])},
                    'target_range': [float(np.min(data['targets'][mask])), float(np.max(data['targets'][mask]))] if mask.any() else None}
        write_json(destination / 'source_audit.json', summary)
        write_json(destination / 'provenance.json', provenance)
        scores, fit_logs, outputs, skips = {}, {}, {}, []
        for unit in (1, 2):
            for held in (0, 1):
                fit_rows = np.flatnonzero((data['physical_unit_z'] == unit) & (folds != held) & data['valid'][:, 1])
                held_rows = np.flatnonzero((data['physical_unit_z'] == unit) & (folds == held) & data['valid'][:, 1])
                fit_ids, held_ids = data['event_ids'][fit_rows], data['event_ids'][held_rows]
                if np.intersect1d(fit_ids, held_ids).size:
                    raise ValueError('Events shared between fit and held folds')
                if len(np.unique(fit_ids)) < 100 or len(np.unique(held_ids)) < 30:
                    skips.append({'unit': unit, 'held': held, 'fit_events': len(np.unique(fit_ids)),
                                  'held_events': len(np.unique(held_ids))})
                    continue
                z = torch.from_numpy(data['z'][fit_rows]).double()
                m = torch.from_numpy(data['targets'][fit_rows]).double()
                weights = torch.from_numpy(equal_event_weights(fit_ids))
                observed = contrasts(z, 5)
                for seed in protocol['initializations']:
                    key = f'unit{unit}_seed{seed}_held{held}'
                    scores[key] = {}
                    initial = initial_parameters(m, observed, weights, seed)
                    for arm in ARMS:
                        start = initial_parameters(m, observed, weights, seed, linear=True) if arm == 'linear_gaussian' else initial
                        model, log = fit(arm, start, z, m, weights, protocol['optimizer'])
                        fit_logs[key + '_' + arm] = log
                        scored = [(arm, model)]
                        if arm == 'shared_cap':
                            scored.append((COUNTERFACTUAL, Density(COUNTERFACTUAL, model.raw.detach())))
                        for label, fitted in scored:
                            scores[key][label] = {}
                            for seconds, mask_index in ((3, 0), (5, 1)):
                                rows = np.flatnonzero((data['physical_unit_z'] == unit) & (folds == held) & data['valid'][:, mask_index])
                                # Pass no future coordinate at 3s: sentinel is a causality assertion.
                                evaluation_z = data['z'][rows].copy()
                                if seconds == 3:
                                    evaluation_z[:, 1] = np.nan
                                with torch.no_grad():
                                    values = torch.from_numpy(evaluation_z).double()
                                    magnitude = torch.from_numpy(data['targets'][rows]).double()
                                    ll = fitted.log_likelihood(values, magnitude, seconds).numpy()
                                    pit = fitted.marginal_pit(values, magnitude, seconds).numpy()
                                if not np.isfinite(ll).all() or not np.isfinite(pit).all() or (pit < 0).any() or (pit > 1).any():
                                    raise ValueError('Invalid held likelihood or PIT')
                                scores[key][label][str(seconds)] = summarize(-ll, data['event_ids'][rows], data['targets'][rows], pit)
                                outputs[key + '_' + label + '_' + str(seconds)] = (rows, ll)
                                np.savez_compressed(destination / f'{key}_{label}_{seconds}s.npz',
                                                    array_row=rows, source_row=data['row_index'][rows],
                                                    event_ids=data['event_ids'][rows], trace_names=data['trace_names'][rows],
                                                    targets=data['targets'][rows], log_likelihood=ll, marginal_pit=pit)
                        write_json(destination / 'fit_logs.json', fit_logs)
                        write_json(destination / 'scores.json', scores)
                        print('FIT', key, arm, 'seconds', round(log['wall_seconds'], 3),
                              'held5_nll', scores[key][arm]['5']['all']['nll'], flush=True)
        decision = decide(scores, outputs, data, protocol['initializations'])
        decision['skipped'] = skips
        write_json(destination / 'decision.json', decision)
        if sha256(protocol_path) != PROTOCOL_SHA or sha256(source) != protocol['source_sha256']:
            raise ValueError('Pinned inputs changed during run')
        provenance.update(status='complete', wall_seconds=time.monotonic() - started,
                          cuda_initialized=torch.cuda.is_initialized())
        write_json(destination / 'provenance.json', provenance)
        paths = sorted(destination.iterdir())
        manifest = {p.name: {'sha256': sha256(p), 'bytes': p.stat().st_size} for p in paths if p.is_file()}
        if sum(item['bytes'] for item in manifest.values()) > 1024 ** 3:
            raise RuntimeError('Artifact size cap exceeded')
        write_json(destination / 'manifest.json', manifest)
        print('COMPLETE', destination, json.dumps(decision), flush=True)
    except BaseException as error:
        provenance.update(status='failed', error=repr(error), wall_seconds=time.monotonic() - started)
        write_json(destination / 'provenance.json', provenance)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    def timeout_handler(_signum, _frame):
        raise TimeoutError('Locked 30-minute CPU runtime cap reached')
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(1800)
    run(arguments)

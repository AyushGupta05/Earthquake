"""197676-record event-cross-fitted reference-metric pilot on instrument head.

Fixed 15 epochs, two student seeds, 1/3/5 seconds independently. Same 291-input
student as instrument_residual, 12 native slots zero. Each reference is fitted
once per horizon and reused by all students; validation never fits/selects it.
"""
import argparse
import json
import os
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn

import instrument_residual as baseline
from feature_residual import ResidualDistribution
from context_reference import CONTROLS, fit_references, score_vector
from train_instrument_scores import (instrument_design, configure_runtime, runtime_identity,
                                     array_digest, model_digest)
from audit_and_export import sha256
from distribution_experiment import metrics, median
from run_artifacts import create_run

HERE = Path(__file__).resolve().parent


def fit_one(data, arrays, mask, args, seed, device, control, references):
    if control not in CONTROLS or len(arrays) != 2 or mask.shape != (291,):
        raise ValueError('Invalid control or exact instrument design')
    if any(a.ndim != 2 or a.shape[1] != 291 for a in arrays):
        raise ValueError('Require exact 291-column student input')
    if len(arrays[0]) != len(data['train_y']) or len(arrays[1]) != len(data['val_logits']):
        raise ValueError('Student rows not aligned')
    if min(args.epochs, args.batch_size) < 1 or not np.isfinite(args.learning_rate) or args.learning_rate <= 0:
        raise ValueError('Invalid student optimization bounds')
    n = len(arrays[0])
    # Explicit per-control materialization happens before the seed reset and
    # consumes no torch RNG; all student initializations/dropout/orders match.
    threshold_weights = None
    if control in ('context_ce', 'shuffled_ce', 'average_ce'):
        if references['weights'].shape != (n, 65):
            raise ValueError('Misaligned frozen reference weights')
        w = references['weights']
        if control == 'shuffled_ce':
            donor = references['donor']
            if donor.shape != (n,) or not np.array_equal(np.sort(donor), np.arange(n)):
                raise ValueError('Invalid weight-vector permutation')
            if not np.array_equal(references['folds'], references['folds'][donor]):
                raise ValueError('Reference permutation crossed held-out event folds')
            w = w[donor]
        elif control == 'average_ce':
            w = references['average']
        threshold_weights = torch.as_tensor(w, dtype=torch.float32, device=device)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    train_x, val_x = [torch.as_tensor(a * mask, device=device) for a in arrays]
    original = torch.as_tensor(data['train_logits'], device=device)
    val_original = torch.as_tensor(data['val_logits'], device=device)
    y = torch.as_tensor(data['train_y'], device=device)
    weights = torch.as_tensor(data['weights'], device=device)
    labels = (y / .1 + 1e-5).floor().long().clamp(0, 65)
    model = ResidualDistribution(291).to(device)
    initial_hash = model_digest(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    shuffle = torch.Generator(device='cpu').manual_seed(seed)
    losses, orders = [], []
    gradient_sum, gradient_max, clipped, steps = 0., 0., 0, 0
    for _ in range(args.epochs):
        model.train()
        order = torch.randperm(len(y), generator=shuffle)
        orders.append(array_digest(order.numpy()))
        total = 0.
        for cpu_indices in order.split(args.batch_size):
            indices = cpu_indices.to(device)
            logits = model(train_x[indices], original[indices])
            w = threshold_weights
            if w is not None and w.ndim == 2:
                w = w[indices]
            loss = (weights[indices] * score_vector(logits, labels[indices], control, w)).mean()
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite contextual-score objective')
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            norm = nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True).item()
            gradient_sum += norm; gradient_max = max(gradient_max, norm)
            clipped += int(norm > 5.); steps += 1
            optimizer.step()
            total += loss.item() * len(indices)
        losses.append(total / len(y))
    model.eval()
    with torch.inference_mode():
        probability = torch.cat([model(val_x[start:start+args.batch_size], val_original[start:start+args.batch_size])
            .double().softmax(1).cpu() for start in range(0, len(val_x), args.batch_size)]).numpy()
    trace = {'initial_model_sha256': initial_hash, 'epoch_order_sha256': orders,
        'final_model_sha256': model_digest(model), 'parameters': sum(p.numel() for p in model.parameters()),
        'preclip_gradient_norm_mean': gradient_sum/steps, 'preclip_gradient_norm_max': gradient_max,
        'gradient_clipped_fraction': clipped/steps}
    return probability, model.cpu().state_dict(), losses, trace


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seconds', type=int, choices=(1, 3, 5), required=True)
    p.add_argument('--inventory', type=Path, required=True)
    p.add_argument('--inventory-sha256', default=baseline.INVENTORY_SHA256)
    p.add_argument('--root', type=Path, default=baseline.ROOT)
    p.add_argument('--data', type=Path, default=Path('/data'))
    p.add_argument('--output', type=Path, default=baseline.ROOT/'results/2026-10-09/phase2')
    p.add_argument('--controls', nargs='+', choices=CONTROLS, default=list(CONTROLS))
    p.add_argument('--seeds', nargs='+', type=int, default=[20261009, 20261010])
    p.add_argument('--epochs', type=int, default=15)
    p.add_argument('--reference-epochs', type=int, default=15)
    p.add_argument('--reference-folds', type=int, choices=(5,), default=5)
    p.add_argument('--reference-seed', type=int, default=20261011)
    p.add_argument('--fold-seed', type=int, default=20261009)
    p.add_argument('--permutation-seed', type=int, default=20261012)
    p.add_argument('--max-per-event', type=int, default=4)
    p.add_argument('--expected-train-records', type=int, default=197676)
    p.add_argument('--batch-size', type=int, default=2048)
    p.add_argument('--extract-batch-size', type=int, default=256)
    p.add_argument('--learning-rate', type=float, default=5e-4)
    p.add_argument('--reference-learning-rate', type=float, default=5e-4)
    p.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = p.parse_args(argv)
    if min(args.epochs, args.reference_epochs, args.expected_train_records, args.batch_size, args.extract_batch_size) < 1 or args.max_per_event < 0:
        p.error('Positive training bounds and nonnegative sampling cap required')
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.controls)) != len(args.controls):
        p.error('Duplicate seeds/controls are not independent comparisons')
    if any(not np.isfinite(v) or v <= 0 for v in (args.learning_rate, args.reference_learning_rate)):
        p.error('Learning rates must be finite positive')
    return args


def run(args):
    configure_runtime()
    device = torch.device(args.device)
    config = {k: str(v) if isinstance(v, Path) else v for k,v in vars(args).items()}
    config.update(sampling_seed=20261009, family='instrument', reference_features=85,
        reference_normalization='Population-weighted fold-TRAIN only; zero held-fold labels used',
        reference_objective='Population-weighted categorical CE only; fixed final epoch',
        reference_upstream_limit='Existing global count scaling is target-free but uses full TRAIN covariates; released preprocessing/manual P limitations remain',
        native_slots='12 zeros after TRAIN student normalization', ce_weight=.075, bin_width=.1,
        weight_epsilon=.01, weight_cap=25., weight_normalization='Per-record arithmetic mean over 65 thresholds',
        ad_exponent_safety_bound=60., runtime=runtime_identity(device),
        selection='All fixed final epochs/controls/seeds; no validation selection or tuning')
    sources = [HERE/n for n in ('context_reference.py', 'context_reference_train.py',
        'train_instrument_scores.py', 'instrument_proper_scores.py', 'instrument_residual.py',
        'instrument_inventory.py', 'feature_residual.py', 'run_artifacts.py')]
    sources += [HERE.parent/n for n in ('audit_and_export.py', 'distribution_experiment.py', 'frozen_head_pilot.py')]
    out = create_run(args.output, f'context_reference_{args.seconds}s', config, sources)
    print('RUN_DIRECTORY', out, flush=True)
    started = time.monotonic()
    data, identities, alignment, instrument_names = baseline.extract(args, device)
    if len(data['train_y']) != args.expected_train_records:
        raise ValueError('TRAIN count differs from the explicitly requested protocol')
    arrays, feature_mean, feature_std, mask, base_dim = instrument_design(data)
    references, report = fit_references(data, args, device, out)
    report.update(input_identities=identities, targets_sha256=array_digest(data['train_y']),
        population_weights_sha256=array_digest(data['weights']), row_index_sha256=array_digest(data['train_rows']),
        event_ids_sha256=array_digest(data['train_ids']), trace_names_sha256=array_digest(data['train_trace_names']))
    # Save before students: exact rows/folds/CDFs enable separately prespecified
    # earlier-reference/later-student work without fitting a new teacher.
    np.savez_compressed(out/'reference_oof.npz', targets=data['train_y'], event_ids=data['train_ids'],
        trace_names=data['train_trace_names'], row_index=data['train_rows'], population_weights=data['weights'],
        cdf=np.clip(references['probability'].cumsum(1)[:, :-1], 0., 1.), **references)
    (out/'reference_report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    y, ids, centers = data['val_y'], data['val_ids'], data['centers']
    raw = torch.from_numpy(data['val_logits']).double().softmax(1).numpy()
    results, predictions, histories, traces = {}, {}, {}, {}
    probabilities = {control: [] for control in args.controls}
    for decision,prediction in [('mean',raw@centers), ('median',median(raw,centers))]:
        results['raw_'+decision] = metrics(y,prediction,ids,raw,centers)
        predictions['raw_'+decision] = prediction
    for seed in args.seeds:
        for control in args.controls:
            name = f'{control}_seed{seed}'
            probability, state, losses, trace = fit_one(data, arrays, mask, args, seed, device, control, references)
            probabilities[control].append(probability); histories[name] = losses; traces[name] = trace
            torch.save({'model': state, 'feature_mean': torch.tensor(feature_mean),
                'feature_std': torch.tensor(feature_std), 'feature_mask': torch.tensor(mask),
                'config': config, 'seed': seed, 'control': control, 'base_dim': base_dim,
                'instrument_names': instrument_names, 'native_names': baseline.NATIVE_FEATURE_NAMES}, out/f'{name}.pth')
            for decision,prediction in [('mean',probability@centers), ('median',median(probability,centers))]:
                key = name+'_'+decision
                predictions[key] = prediction; results[key] = metrics(y,prediction,ids,probability,centers)
            print(name, {k:results[name+'_mean'][k] for k in ('mae','medae','m4_mae','cvar95','fp4')}, flush=True)
        compared = [traces[f'{control}_seed{seed}'] for control in args.controls]
        if any(t['initial_model_sha256'] != compared[0]['initial_model_sha256'] or
               t['epoch_order_sha256'] != compared[0]['epoch_order_sha256'] for t in compared):
            raise ValueError('Student initialization or minibatch order differs across controls')
    for control,values in probabilities.items():
        probability = np.mean(values, axis=0)
        np.savez_compressed(out/f'{control}_probabilities.npz', targets=y,event_ids=ids,
            trace_names=data['val_trace_names'], centers=centers, mean_probability=probability.astype(np.float32),
            **{f'seed{seed}':v.astype(np.float32) for seed,v in zip(args.seeds,values)})
        for decision,prediction in [('mean',probability@centers), ('median',median(probability,centers))]:
            key = control+'_ensemble_'+decision
            predictions[key] = prediction; results[key] = metrics(y,prediction,ids,probability,centers)
    info = dict(config, wall_seconds=time.monotonic()-started, train_records=len(data['train_y']),
        train_events=len(np.unique(data['train_ids'])), validation_status='Reused exploratory validation only',
        score_status='Known conditional positive-weight CRPS construction; no new propriety theorem or calibration guarantee',
        causality_limit='Student all-TRAIN frozen CNN, original released counts and manual P limitations unchanged')
    schema = {'base_dimension':base_dim,'instrument_names':instrument_names,
        'native_names':baseline.NATIVE_FEATURE_NAMES,'mask':mask.tolist(),
        'reference_fields':'51 prefix descriptors then 34 instrument fields; no CNN logits/embedding/native'}
    for name,value in [('run.json',info),('metrics.json',results),('history.json',histories),
                      ('training_traces.json',traces),('input_identities.json',identities),
                      ('alignment.json',alignment),('feature_schema.json',schema)]:
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(out/'predictions.npz',targets=y,event_ids=ids,trace_names=data['val_trace_names'],**predictions)
    manifest = {p.name:{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(out.iterdir()) if p.is_file()}
    (out/'artifacts.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Downstream analysis must require this marker, written atomically LAST.
    pending = out/'COMPLETE.tmp'
    pending.write_text(json.dumps({'status':'complete','artifacts_sha256':sha256(out/'artifacts.json'),
        'controls':args.controls,'seeds':args.seeds},indent=2)+'\n')
    os.replace(pending,out/'COMPLETE.json')
    print('COMPLETE',out,flush=True)
    return out


if __name__ == '__main__':
    run(parse_args())

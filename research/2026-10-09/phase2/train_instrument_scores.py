"""Known proper-score grid on the matched 291-input static instrument head.

Defaults: all 979487 TRAIN records, fixed 15 epochs, two prespecified seeds.
All controls share extraction, TRAIN normalizer, mask, initialization and order.
No validation selection, contextual reference model, new architecture or novelty
claim. Original release preprocessing/frozen-CNN limitations remain unchanged.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import torch
from torch import nn

import instrument_residual as baseline
from feature_residual import ResidualDistribution
from instrument_proper_scores import CONTROLS, objective_vector, train_marginal_weights
from audit_and_export import sha256
from distribution_experiment import metrics, median
from run_artifacts import create_run

HERE = Path(__file__).resolve().parent
INPUT_DIM = 291


def array_digest(value):
    a = np.ascontiguousarray(value)
    h = hashlib.sha256()
    h.update(str(a.dtype).encode()); h.update(json.dumps(list(a.shape)).encode()); h.update(a.tobytes())
    return h.hexdigest()


def model_digest(model):
    h = hashlib.sha256()
    for key, tensor in model.state_dict().items():
        h.update(key.encode()); h.update(array_digest(tensor.detach().cpu().numpy()).encode())
    return h.hexdigest()


def configure_runtime():
    if torch.cuda.is_initialized():
        raise RuntimeError('Use a fresh process to set cuBLAS determinism before CUDA initialization')
    os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
    if os.environ['CUBLAS_WORKSPACE_CONFIG'] not in (':4096:8', ':16:8'):
        raise ValueError('Unsupported deterministic cuBLAS workspace setting')
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


def runtime_identity(device):
    return {'python': platform.python_version(), 'torch': str(torch.__version__),
        'cuda_build': torch.version.cuda, 'cudnn': torch.backends.cudnn.version(),
        'device': str(device), 'device_name': torch.cuda.get_device_name(device) if device.type == 'cuda' else platform.processor(),
        'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
        'cudnn_deterministic': torch.backends.cudnn.deterministic,
        'cudnn_benchmark': torch.backends.cudnn.benchmark,
        'cudnn_allow_tf32': torch.backends.cudnn.allow_tf32,
        'matmul_allow_tf32': torch.backends.cuda.matmul.allow_tf32,
        'CUBLAS_WORKSPACE_CONFIG': os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
        'NVIDIA_TF32_OVERRIDE': os.environ.get('NVIDIA_TF32_OVERRIDE')}


def instrument_design(data):
    arrays, mean, std, masks, base_dim = baseline.design_inputs(data)
    if base_dim != 245 or any(a.shape[1] != INPUT_DIM for a in arrays):
        raise ValueError('Require the exact 291-column instrument residual design')
    mask = masks['instrument']
    if not np.array_equal(mask, np.r_[np.ones(279), np.zeros(12)].astype(np.float32)):
        raise ValueError('Require all 34 static fields active and 12 native slots inactive')
    return arrays, mean, std, mask, base_dim


def fit_one(data, arrays, mask, args, seed, device, control, marginal_weights):
    if control not in CONTROLS or len(arrays) != 2 or mask.shape != (INPUT_DIM,):
        raise ValueError('Invalid control or design mask')
    if min(args.epochs, args.batch_size) < 1 or not np.isfinite(args.learning_rate) or args.learning_rate <= 0:
        raise ValueError('Invalid training bounds')
    if any(a.shape[1] != INPUT_DIM for a in arrays):
        raise ValueError('Feature dimension changed')
    if arrays[0].shape[0] != len(data['train_y']) or arrays[1].shape[0] != len(data['val_logits']):
        raise ValueError('Feature rows do not match magnitude rows')
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
    threshold_weights = torch.as_tensor(marginal_weights, dtype=torch.float32, device=device)
    model = ResidualDistribution(train_x.shape[1]).to(device)
    initial_hash = model_digest(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    shuffle = torch.Generator(device='cpu').manual_seed(seed)
    losses, orders = [], []
    for _ in range(args.epochs):
        model.train()
        order = torch.randperm(len(y), generator=shuffle)
        orders.append(array_digest(order.numpy()))
        total = 0.
        for cpu_indices in order.split(args.batch_size):
            indices = cpu_indices.to(device)
            logits = model(train_x[indices], original[indices])
            loss_vector = objective_vector(logits, y[indices], labels[indices], centers,
                                           original_mean[indices], control, threshold_weights)
            loss = (weights[indices] * loss_vector).mean()
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite instrument-score objective')
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
    trace = {'initial_model_sha256': initial_hash, 'epoch_order_sha256': orders,
             'final_model_sha256': model_digest(model), 'parameters': sum(p.numel() for p in model.parameters())}
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
    p.add_argument('--max-per-event', type=int, default=0)
    p.add_argument('--expected-train-records', type=int, default=979487)
    p.add_argument('--batch-size', type=int, default=2048)
    p.add_argument('--extract-batch-size', type=int, default=256)
    p.add_argument('--learning-rate', type=float, default=5e-4)
    p.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = p.parse_args(argv)
    if min(args.epochs, args.expected_train_records, args.batch_size, args.extract_batch_size) < 1 or args.max_per_event < 0:
        p.error('Positive training bounds and nonnegative sampling cap required')
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.controls)) != len(args.controls):
        p.error('Duplicate seeds/controls are not independent comparisons')
    if not np.isfinite(args.learning_rate) or args.learning_rate <= 0:
        p.error('Learning rate must be finite positive')
    return args


def run(args):
    configure_runtime()
    device = torch.device(args.device)
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    config.update(sampling_seed=20261009, family='instrument', native_slots='12 zeros after TRAIN normalization',
        huber_beta=5., huber_delta=.5, anchor=0., ce_weight=.075, bin_width=.1,
        tail_weight='1+4*I[z>=4] (not rescaled)', prior_epsilon=.01, prior_cap=25.,
        prior_normalization='Fixed arithmetic mean over 65 thresholds', runtime=runtime_identity(device),
        selection='Fixed final epoch; report all prespecified seeds/controls; no validation selection')
    sources = [HERE/n for n in ('train_instrument_scores.py', 'instrument_proper_scores.py',
        'INSTRUMENT_PROPER_SCORES.md', 'instrument_residual.py', 'instrument_inventory.py', 'feature_residual.py', 'run_artifacts.py')]
    sources += [HERE.parent/n for n in ('audit_and_export.py', 'distribution_experiment.py', 'frozen_head_pilot.py')]
    out = create_run(args.output, f'instrument_scores_{args.seconds}s', config, sources)
    print('RUN_DIRECTORY', out, flush=True)
    started = time.monotonic()
    data, identities, alignment, instrument_names = baseline.extract(args, device)
    if len(data['train_y']) != args.expected_train_records:
        raise ValueError('TRAIN count differs from the explicitly requested protocol')
    arrays, feature_mean, feature_std, mask, base_dim = instrument_design(data)
    marginal_weights, prior = train_marginal_weights(data['train_y'], data['weights'])
    prior.update(targets_sha256=array_digest(data['train_y']), weights_sha256=array_digest(data['weights']),
        row_index_sha256=array_digest(data['train_rows']), event_ids_sha256=array_digest(data['train_ids']),
        trace_names_sha256=array_digest(data['train_trace_names']), input_identities=identities)
    y, ids, centers = data['val_y'], data['val_ids'], data['centers']
    raw = torch.from_numpy(data['val_logits']).double().softmax(1).numpy()
    results, predictions, histories, traces = {}, {}, {}, {}
    probabilities = {control: [] for control in args.controls}
    for decision, prediction in [('mean', raw @ centers), ('median', median(raw, centers))]:
        results['raw_' + decision] = metrics(y, prediction, ids, raw, centers)
        predictions['raw_' + decision] = prediction
    for seed in args.seeds:
        for control in args.controls:
            name = f'{control}_seed{seed}'
            p, state, losses, trace = fit_one(data, arrays, mask, args, seed, device, control, marginal_weights)
            probabilities[control].append(p); histories[name] = losses; traces[name] = trace
            torch.save({'model': state, 'feature_mean': torch.tensor(feature_mean),
                'feature_std': torch.tensor(feature_std), 'feature_mask': torch.tensor(mask),
                'config': config, 'seed': seed, 'control': control, 'base_dim': base_dim,
                'instrument_names': instrument_names, 'native_names': baseline.NATIVE_FEATURE_NAMES,
                'training_prior_weights': torch.tensor(marginal_weights)}, out/f'{name}.pth')
            for decision, prediction in [('mean', p @ centers), ('median', median(p, centers))]:
                key = name + '_' + decision
                predictions[key] = prediction; results[key] = metrics(y, prediction, ids, p, centers)
            print(name, {k: results[name+'_mean'][k] for k in ('mae','medae','m4_mae','cvar95','fp4')}, flush=True)
        matched = [traces[f'{control}_seed{seed}'] for control in args.controls]
        if any(t['initial_model_sha256'] != matched[0]['initial_model_sha256'] or
               t['epoch_order_sha256'] != matched[0]['epoch_order_sha256'] for t in matched):
            raise ValueError('Compared controls did not share initialization and realized minibatch order')
    for control, values in probabilities.items():
        p = np.mean(values, axis=0)
        np.savez_compressed(out/f'{control}_probabilities.npz', targets=y, event_ids=ids,
            trace_names=data['val_trace_names'], centers=centers, mean_probability=p.astype(np.float32),
            **{f'seed{seed}': v.astype(np.float32) for seed,v in zip(args.seeds, values)})
        for decision, prediction in [('mean', p @ centers), ('median', median(p, centers))]:
            key = control + '_ensemble_' + decision
            predictions[key] = prediction; results[key] = metrics(y, prediction, ids, p, centers)
    info = dict(config, wall_seconds=time.monotonic()-started, train_records=len(data['train_y']),
        train_events=len(np.unique(data['train_ids'])), validation_status='Reused exploratory validation only',
        score_status='Four known proper finite-bin distribution objectives; existing Huber arm is not proper',
        causality_limit='Existing frozen CNN and released counts retain whole-record processing/manual P limitations')
    schema = {'base_dimension': base_dim, 'instrument_names': instrument_names,
              'native_names': baseline.NATIVE_FEATURE_NAMES, 'mask': mask.tolist()}
    for name,value in [('run.json',info),('metrics.json',results),('history.json',histories),
                      ('training_traces.json',traces),('train_marginal_prior.json',prior),
                      ('input_identities.json',identities),('alignment.json',alignment),('feature_schema.json',schema)]:
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    np.savez_compressed(out/'predictions.npz', targets=y,event_ids=ids,trace_names=data['val_trace_names'],**predictions)
    np.savez_compressed(out/'training_rows.npz',row_index=data['train_rows'],event_ids=data['train_ids'],
        trace_names=data['train_trace_names'],targets=data['train_y'],weights=data['weights'])
    manifest = {p.name:{'bytes':p.stat().st_size,'sha256':sha256(p)} for p in sorted(out.iterdir()) if p.is_file()}
    (out/'artifacts.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('COMPLETE',out,flush=True)
    return out


if __name__ == '__main__':
    run(parse_args())

"""Bounded loader/update equivalence probe; execution requires explicit scheduling.

A passing probe concerns its recorded checkpoint, runtime, subset and two short
epochs. It is not a universal numerical equivalence theorem or a model score.
"""
import copy
import hashlib
import json
import struct
import time

import torch
from torch.utils.data import DataLoader, Subset, default_collate

from training_artifacts import capture_random_state, restore_random_state


def state_digest(value):
    digest = hashlib.sha256()
    def add(item):
        if isinstance(item, torch.Tensor):
            tensor = item.detach().cpu().contiguous()
            digest.update(b'tensor' + str(tensor.dtype).encode() + str(tuple(tensor.shape)).encode())
            digest.update(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
        elif isinstance(item, dict):
            digest.update(b'dict')
            for key in sorted(item, key=lambda key: (type(key).__name__, repr(key))):
                add(key)
                add(item[key])
        elif isinstance(item, (list, tuple)):
            digest.update(type(item).__name__.encode() + str(len(item)).encode())
            for child in item:
                add(child)
        elif isinstance(item, float):
            # Scheduler sentinels legitimately contain +/-infinity. Preserve
            # IEEE bits here; model losses/gradients are checked separately.
            digest.update(b'float' + struct.pack('!d', item))
        else:
            digest.update(type(item).__name__.encode() + json.dumps(item, allow_nan=False).encode() + b'\n')
    add(value)
    return digest.hexdigest()


def _build(trainer, origin, device):
    config = origin['config']
    model = trainer.TeamLM(config['aggregation'])
    model.single_station_head = trainer.GaussianMixtureHead()
    model.load_state_dict(origin['model'], strict=True)
    model.to(device)
    parameters = list(model.station_encoder.parameters()) + list(model.single_station_head.parameters())
    optimizer = torch.optim.Adam(parameters, lr=1e-4)
    scheduler = trainer.make_plateau_scheduler(optimizer, config['lr_schedule'], 'pretrain')
    # Optimizer.load_state_dict may reuse CPU tensor storage. The two proof
    # paths must never mutate their shared starting checkpoint.
    recovery = dict(origin, optimizer=copy.deepcopy(origin['optimizer']), scheduler=copy.deepcopy(origin['scheduler']))
    trainer.restore_optimizer_and_random(optimizer, scheduler, recovery)
    return model, parameters, optimizer, scheduler


def _probe_one(trainer, origin, fit, calibration, fit_indices, calibration_indices, device, *, restore_boundary, deadline):
    config = origin['config']
    model, parameters, optimizer, scheduler = _build(trainer, origin, device)
    traces = {'batch_and_noise_trace': [], 'loss_gradient_update_trace': [],
              'model_optimizer_scheduler_rng': [], 'calibration': []}
    original_noise, original_cutoffs, original_loss = trainer.smooth_training_magnitudes, trainer.training_cutoffs, trainer.mixture_nll
    def deadline_check():
        if time.monotonic() > deadline:
            raise TimeoutError('Bounded training-equivalence probe exceeded its deadline')
    def collate(examples):
        deadline_check()
        batch = default_collate(examples)
        traces['batch_and_noise_trace'].append({'batch': state_digest(batch)})
        return batch
    def noise(targets, **kwargs):
        result = original_noise(targets, **kwargs)
        traces['batch_and_noise_trace'].append({'raw_targets': state_digest(targets), 'noised_targets': state_digest(result)})
        return result
    def cutoffs(*args, **kwargs):
        result = original_cutoffs(*args, **kwargs)
        traces['batch_and_noise_trace'].append({'cutoffs': state_digest(result)})
        return result
    def loss(*args, **kwargs):
        result = original_loss(*args, **kwargs)
        traces['loss_gradient_update_trace'].append({'loss': state_digest(result)})
        return result
    trainer.smooth_training_magnitudes, trainer.training_cutoffs, trainer.mixture_nll = noise, cutoffs, loss
    def attach_step_audit(current_optimizer, current_model, current_parameters):
        original_step = current_optimizer.step
        def step(*args, **kwargs):
            deadline_check()
            gradients = [parameter.grad for parameter in current_parameters]
            if any(value is None or not torch.isfinite(value).all() for value in gradients):
                raise FloatingPointError('Probe requires finite gradients on all trained station/head parameters')
            traces['loss_gradient_update_trace'].append({'gradients': state_digest(gradients)})
            result = original_step(*args, **kwargs)
            traces['loss_gradient_update_trace'].append({'model': state_digest(current_model.state_dict()),
                                                          'optimizer': state_digest(current_optimizer.state_dict())})
            return result
        current_optimizer.step = step
    try:
        attach_step_audit(optimizer, model, parameters)
        for offset in range(2):
            epoch = origin['completed_epoch'] + offset
            generator = torch.Generator().manual_seed(config['seed'] + epoch)
            loader = DataLoader(Subset(fit, fit_indices), batch_size=config['pretrain_batch_size'], shuffle=True,
                                generator=generator, num_workers=0, collate_fn=collate)
            result = trainer.train_station_epoch(model, loader, optimizer, parameters, device, config, epoch)
            deadline_check()
            calibration_loader = DataLoader(Subset(calibration, calibration_indices), batch_size=config['pretrain_batch_size'],
                                            shuffle=False, num_workers=0)
            metrics = trainer.evaluate_pretraining(model, calibration_loader, device)
            trainer.step_calibration_scheduler(scheduler, metrics, split='calibration')
            traces['calibration'].append(metrics)
            snapshot = trainer.checkpoint(model, optimizer, 'pretrain', epoch + 1, config, {}, scheduler,
                out=__import__('pathlib').Path(origin['run_directory']),
                run_state=copy.deepcopy(origin['run_state']))
            traces['model_optimizer_scheduler_rng'].append(state_digest({
                key: snapshot[key] for key in ('model', 'optimizer', 'scheduler', 'torch_rng', 'cuda_rng', 'python_rng', 'numpy_rng')}))
            traces['model_optimizer_scheduler_rng'].append({'loss': result[0], 'count': result[1],
                                                            'loader_generator': state_digest(generator.get_state())})
            if restore_boundary and offset == 0:
                # Use a fully independent tensor snapshot: continuing mutation
                # must not alias the checkpoint used to prove epoch recovery.
                snapshot = copy.deepcopy(snapshot)
                model, parameters, optimizer, scheduler = _build(trainer, snapshot, device)
                attach_step_audit(optimizer, model, parameters)
        deadline_check()
    finally:
        trainer.smooth_training_magnitudes, trainer.training_cutoffs, trainer.mixture_nll = original_noise, original_cutoffs, original_loss
    return {key: state_digest(value) for key, value in traces.items()}


def prove_updates(trainer, origin, original_fit, original_calibration, flat_fit, flat_calibration, *, device, max_seconds=120):
    """Two short epochs, including a final partial batch and one restored boundary."""
    batch_size = origin['config']['pretrain_batch_size']
    needed = 2 * batch_size + 1
    if batch_size < 2 or min(len(original_fit), len(flat_fit)) < needed:
        raise ValueError('Proof needs batch_size>=2 and at least 2*batch_size+1 fitting stations')
    if len(original_fit) != len(flat_fit) or len(original_calibration) != len(flat_calibration):
        raise ValueError('Original and flat station memberships have different lengths')
    # Deterministically cover early and late station indices. Selection uses no
    # runtime RNG and is recorded; this is a bounded subset, not a full epoch.
    fit_indices = [int(index) for index in __import__('numpy').linspace(0, len(original_fit) - 1, needed, dtype=int)]
    calibration_indices = list(range(min(batch_size + 1, len(original_calibration))))
    if not calibration_indices:
        raise ValueError('Proof requires held-out TRAIN calibration stations')
    original_rng = capture_random_state()
    deadline = time.monotonic() + max_seconds
    try:
        original = _probe_one(trainer, origin, original_fit, original_calibration, fit_indices, calibration_indices,
                              device, restore_boundary=False, deadline=deadline)
        flat = _probe_one(trainer, origin, flat_fit, flat_calibration, fit_indices, calibration_indices,
                          device, restore_boundary=True, deadline=deadline)
    finally:
        restore_random_state(original_rng)
    if original != flat:
        raise AssertionError('Original/flat traces differ: ' + ', '.join(key for key in original if original[key] != flat[key]))
    return {'checks': {key: {'original': original[key], 'flat': flat[key]} for key in original},
            'epochs': 2, 'steps_per_epoch': 3, 'epoch_boundary_restore_tested': True,
            'partial_batch_tested': True, 'cutoff_and_label_noise_traced': True,
            'selected_fit_station_indices': fit_indices, 'selected_calibration_station_indices': calibration_indices,
            'batch_size': batch_size, 'probe_seconds': max_seconds - max(0, deadline - time.monotonic()),
            'scope': 'bounded recorded subsets; not universal training equivalence'}

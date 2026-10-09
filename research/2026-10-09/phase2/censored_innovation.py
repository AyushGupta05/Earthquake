"""Small sequential likelihood pilot; see CENSORED_INNOVATION_METHOD.md.

This module does not read waveforms, launch jobs, or select on validation. The
caller supplies identity-checked TRAIN/VAL prefixes. The starting posterior is
the frozen, cost-sensitive one-second instrument residual, not a calibrated
Bayesian prior. Classical censoring and posterior recursion are not new methods.
"""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

ARMS = ('censored', 'hurdle', 'hurdle_truncated', 'uncensored', 'discriminative')
GENERATIVE_ARMS = ARMS[:-1]
SEEDS = (20261009, 20261010)
LOG_2PI = math.log(2 * math.pi)


def _finite(name, tensor):
    if not torch.isfinite(tensor).all():
        raise ValueError(f'{name} must be finite')


@dataclass
class Innovations:
    z: torch.Tensor                 # B x 2, signed log10 block/previous-peak ratio
    g: torch.Tensor                 # B x 2, exactly max(0,z), no tolerance bin
    valid: torch.Tensor             # B x 2, cumulative shared mask for every arm
    above_floor: torch.Tensor       # B x 3, A1, B13, B35 diagnostic only


def vertical_innovations(counts, sensitivity, usable, unit, native_floor=1e-12):
    """Map raw vertical counts B x T, T>=100, to strict 1/3/5 s innovations.

    Sampling is 100 Hz and index zero is the benchmark P pick. Subtract the mean
    of the first TEN POST-P samples, fixed for every deadline; no pre-P samples
    are required. unit=1 means velocity, 2 means acceleration, 0 means unknown.
    Positive scalar sensitivity removes gain only, not full frequency response.

    All arms use a conservative common floor mask: both compared peaks must be
    above the numerical native-unit floor. If 13 is invalid, 35 is also skipped.
    Incomplete new blocks are unavailable (T<300 skips 13, T<500 skips 35).
    Values/masks from after sample 499 are never inspected. Floor/availability
    selection is ignored evidence, not an extra learned likelihood term.
    """
    if counts.ndim != 2 or counts.shape[1] < 100 or not counts.is_floating_point():
        raise ValueError('Expected floating raw vertical counts B x T with T>=100')
    n = counts.shape[0]
    if any(v.shape != (n,) for v in (sensitivity, usable, unit)) or usable.dtype != torch.bool:
        raise ValueError('Sensitivity, bool usability and unit rows must align')
    if any(v.device != counts.device for v in (sensitivity, usable, unit)):
        raise ValueError('Observation tensors must share a device')
    if not math.isfinite(native_floor) or native_floor <= 0:
        raise ValueError('Native numerical floor must be finite and positive')
    if not torch.isin(unit, torch.tensor([0, 1, 2], device=unit.device)).all():
        raise ValueError('Unknown physical-unit encoding')
    gain_ok = torch.isfinite(sensitivity) & (sensitivity > 0)
    sensor_ok = usable & gain_ok & (unit != 0)
    # Safe placeholders are never used as valid observations.
    gain = torch.where(gain_ok, sensitivity, torch.ones_like(sensitivity)).double()
    available_samples = min(counts.shape[1], 500)
    x = counts[:, :500].double()
    if available_samples < 500:
        x = F.pad(x, (0, 500 - available_samples))
    finite_blocks = torch.stack([torch.isfinite(x[:, lo:hi]).all(1)
                                 for lo, hi in ((0, 100), (100, 300), (300, 500))], 1)
    x = torch.where(torch.isfinite(x), x, torch.zeros_like(x))
    native = (x - x[:, :10].mean(1, keepdim=True)) / gain[:, None]
    peaks = torch.stack([native[:, lo:hi].abs().amax(1)
                         for lo, hi in ((0, 100), (100, 300), (300, 500))], 1)
    above = (peaks > native_floor) & torch.isfinite(peaks) & finite_blocks
    above &= torch.tensor([True, available_samples >= 300, available_samples >= 500], device=counts.device)[None]
    safe = torch.where(torch.isfinite(peaks), peaks, torch.zeros_like(peaks)).clamp_min(native_floor)
    # Compute log differences to avoid overflow/underflow in extreme ratios.
    log_peaks = safe.log10()
    z = torch.stack([log_peaks[:, 1] - log_peaks[:, 0],
                     log_peaks[:, 2] - torch.maximum(log_peaks[:, 0], log_peaks[:, 1])], 1)
    valid13 = sensor_ok & above[:, 0] & above[:, 1] & (available_samples >= 300)
    valid = torch.stack([valid13, valid13 & above[:, 2] & (available_samples >= 500)], 1)
    z = torch.where(valid, z, torch.zeros_like(z))
    return Innovations(z=z, g=z.clamp_min(0), valid=valid, above_floor=above)


def undo_count_standardization(standardized, mean, std):
    """Invert this repository's audited float32 affine cache transform.

    This is not recovery of pre-INSTANCE preprocessing or exact integer counts:
    float32 cache rounding remains. Inputs must be ENZ B x 3 x T.
    """
    if standardized.ndim != 3 or standardized.shape[1] != 3:
        raise ValueError('Expected B x 3 x T ENZ cache')
    mean = torch.as_tensor(mean, dtype=torch.float32, device=standardized.device).reshape(1, 3, 1)
    std = torch.as_tensor(std, dtype=torch.float32, device=standardized.device).reshape(1, 3, 1)
    _finite('Standardized counts', standardized)
    _finite('Mean', mean)
    _finite('Standard deviation', std)
    if (std <= 0).any():
        raise ValueError('Nonpositive count standard deviation')
    return standardized.double() * (std + 1e-8).double() + mean.double()


def gaussian_log_density(value, mu, sigma):
    return -.5 * ((value - mu) / sigma).square() - sigma.log() - .5 * LOG_2PI


def observation_log_likelihood(arm, observation, parameters, sigma_floor=.03):
    """Normalized mixed/continuous likelihood, evaluated in float64.

    Gaussian arms use (mu, softplus(scale)+floor); the third output is inactive.
    Hurdle uses the same first two outputs for log(G), plus a free atom logit.
    Positive densities may exceed one. Zero is an atom, never a density value.
    """
    if arm not in GENERATIVE_ARMS or parameters.shape[-1] != 3:
        raise ValueError('Expected a generative arm and three head outputs')
    if not math.isfinite(sigma_floor) or sigma_floor <= 0:
        raise ValueError('Sigma floor must be positive')
    _finite('Observation', observation)
    _finite('Parameters', parameters)
    if arm != 'uncensored' and (observation < 0).any():
        raise ValueError('Observed censored growth cannot be negative')
    value, parameters = observation.double(), parameters.double()
    mu = parameters[..., 0]
    sigma = F.softplus(parameters[..., 1]) + sigma_floor
    density = gaussian_log_density(value, mu, sigma)
    if arm == 'uncensored':
        return density
    if arm == 'censored':
        atom = torch.special.log_ndtr(-mu / sigma)
        return torch.where(value == 0, atom, density)
    if arm == 'hurdle_truncated':
        # Same positive truncated Gaussian as the censored arm; only its atom
        # is freed. This isolates the CDF tie from the lognormal shape choice.
        atom_logit = parameters[..., 2]
        positive_density = F.logsigmoid(-atom_logit) + density - torch.special.log_ndtr(mu / sigma)
        return torch.where(value == 0, F.logsigmoid(atom_logit), positive_density)
    # Avoid evaluating log(0), including its unused autograd branch.
    positive = torch.where(value > 0, value, torch.ones_like(value))
    log_value = positive.log()
    atom_logit = parameters[..., 2]
    atom = F.logsigmoid(atom_logit)
    positive_density = F.logsigmoid(-atom_logit) + gaussian_log_density(log_value, mu, sigma) - log_value
    return torch.where(value == 0, atom, positive_density)


def normalized_update(log_prior, log_likelihood, valid):
    """A masked update preserves the input log posterior exactly."""
    if log_prior.ndim != 2 or log_likelihood.shape != log_prior.shape or valid.shape != log_prior.shape[:1]:
        raise ValueError('Posterior, likelihood and validity shapes differ')
    if valid.dtype != torch.bool:
        raise ValueError('Update mask must be bool')
    _finite('Log prior', log_prior)
    _finite('Log likelihood', log_likelihood)
    if not torch.allclose(torch.logsumexp(log_prior.double(), 1), torch.zeros_like(log_prior[:, 0]).double(), atol=1e-6, rtol=0):
        raise ValueError('Initial log probabilities must already normalize')
    # Remove a potentially enormous common log-density offset BEFORE adding
    # log p. Otherwise equal best likelihoods near -1e20 erase the prior odds.
    centered = log_likelihood.double() - log_likelihood.double().amax(1, keepdim=True)
    updated = log_prior.double() + centered
    updated = updated - torch.logsumexp(updated, 1, keepdim=True)
    # Exact identity for uninformative equal likelihoods, including frozen arm.
    equal = (log_likelihood == log_likelihood[:, :1]).all(1)
    # Preserve the correct derivative at an initially uninformative head. A
    # hard switch to the prior here would freeze a zero-initialized direct head.
    exact_identity = log_prior.detach().double() + (updated - updated.detach())
    updated = torch.where(equal[:, None], exact_identity, updated)
    return torch.where(valid[:, None], updated, log_prior.double())


class InnovationHead(nn.Module):
    """Same parameters/init across arms; inactive slots are explicitly masked.

    Inputs: fixed H1, candidate magnitude, earlier innovation, current innovation,
    and two step indicators. Generative parameters NEVER see current innovation;
    only the discriminative residual can use that slot. At 35 the history slot
    contains observed G13 (Z13 for uncensored), never a full three-second state.
    """
    def __init__(self, context_dimension, arm, width=64, sigma_floor=.03):
        super().__init__()
        if arm not in ARMS or context_dimension < 1 or width < 2 or sigma_floor <= 0 or not math.isfinite(sigma_floor):
            raise ValueError('Invalid head configuration')
        self.arm, self.context_dimension, self.sigma_floor = arm, context_dimension, sigma_floor
        self.net = nn.Sequential(nn.Linear(context_dimension + 5, width), nn.SiLU(),
                                 nn.Linear(width, width // 2), nn.SiLU(), nn.Linear(width // 2, 3))
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def parameters_for(self, context, magnitudes, earlier, current, step):
        if step not in (0, 1) or context.ndim != 2 or context.shape[1] != self.context_dimension:
            raise ValueError('Invalid retained context or step')
        n = len(context)
        if magnitudes.ndim != 2 or magnitudes.shape[0] != n or earlier.shape != (n,) or current.shape != (n,):
            raise ValueError('Magnitude/history rows differ from H1')
        for name, value in [('Context', context), ('Magnitude', magnitudes), ('Earlier', earlier), ('Current', current)]:
            _finite(name, value)
        k = magnitudes.shape[1]
        context = context.detach()
        earlier = (earlier.detach() if step else torch.zeros_like(earlier)).to(context.dtype)
        current = (current.detach() if self.arm == 'discriminative' else torch.zeros_like(current)).to(context.dtype)
        indicators = context.new_zeros(n, 2)
        indicators[:, step] = 1
        shared = torch.cat([context, earlier[:, None], current[:, None], indicators], 1)
        shared = shared[:, None, :].expand(n, k, -1)
        return self.net(torch.cat([shared, magnitudes[..., None].to(context.dtype)], 2))

    def forward(self, context, log_prior, z, valid, centers):
        _validate_history(context, log_prior, z, valid, centers)
        log_p = log_prior.detach().double()
        outputs = [log_p]
        observed = torch.where(valid, z.detach(), torch.zeros_like(z))
        observed = observed if self.arm == 'uncensored' else observed.clamp_min(0)
        for step in range(2):
            parameters = self.parameters_for(context, centers[None].expand(len(context), -1),
                                             observed[:, 0], observed[:, step], step)
            if self.arm == 'discriminative':
                log_q = 5 * torch.tanh(parameters[..., 0].double() / 5)
            else:
                log_q = observation_log_likelihood(self.arm, observed[:, step, None], parameters, self.sigma_floor)
            log_p = normalized_update(log_p, log_q, valid[:, step])
            outputs.append(log_p)
        return torch.stack(outputs, 1)


def _validate_history(context, log_prior, z, valid, centers):
    n = len(context)
    if context.ndim != 2 or z.shape != (n, 2) or valid.shape != (n, 2) or valid.dtype != torch.bool:
        raise ValueError('Expected H1 matrix, two innovations and bool masks')
    if centers.ndim != 1 or log_prior.shape != (n, len(centers)) or len(centers) < 2:
        raise ValueError('Incorrect magnitude grid/prior shape')
    if any(value.device != context.device for value in (log_prior, z, valid, centers)):
        raise ValueError('Prepared tensors must share a device')
    if (centers[1:] <= centers[:-1]).any() or (valid[:, 1] & ~valid[:, 0]).any():
        raise ValueError('Grid must increase; valid 35 requires valid 13')
    for name, value in [('H1', context), ('Log prior', log_prior), ('Innovation', z), ('Centers', centers)]:
        _finite(name, value)
    if not torch.allclose(torch.logsumexp(log_prior.double(), 1), torch.zeros(n, device=log_prior.device).double(), atol=1e-6, rtol=0):
        raise ValueError('Prior must be normalized log probabilities')


def conditional_nll(model, context, z, valid, label_centers):
    """B x 2 labelled conditional NLL; skipped updates contribute exactly zero."""
    if model.arm == 'discriminative':
        raise ValueError('Discriminative residual has no observation density')
    observed = torch.where(valid, z.detach(), torch.zeros_like(z))
    observed = observed if model.arm == 'uncensored' else observed.clamp_min(0)
    losses = []
    for step in range(2):
        parameters = model.parameters_for(context, label_centers[:, None], observed[:, 0], observed[:, step], step)
        log_q = observation_log_likelihood(model.arm, observed[:, step, None], parameters, model.sigma_floor)[:, 0]
        losses.append(torch.where(valid[:, step], -log_q, torch.zeros_like(log_q)))
    return torch.stack(losses, 1)


@dataclass(frozen=True)
class FitConfig:
    epochs: int = 15
    batch_size: int = 2048
    learning_rate: float = 5e-4
    weight_decay: float = 1e-4
    width: int = 64
    sigma_floor: float = .03


def fit_arm(context, log_prior, z, valid, labels, weights, centers, arm, seed, config=FitConfig()):
    """TRAIN-only fit on prepared frozen tensors; no validation argument exists.

    Generative arms minimize conditional NLL at the target magnitude-bin center.
    Direct control minimizes mean categorical NLL at 3/5 s. Both use identical
    inverse-sampling weights and all-record denominators, not tail weighting.
    The initial p1 was fitted with beta=5; it is frozen for every arm.
    """
    _validate_history(context, log_prior, z, valid, centers)
    n = len(context)
    if n < 1 or labels.shape != (n,) or labels.dtype != torch.long or weights.shape != (n,):
        raise ValueError('Invalid labels or population weights')
    if (labels < 0).any() or (labels >= len(centers)).any() or (weights <= 0).any():
        raise ValueError('Invalid labels or population weights')
    _finite('Weights', weights)
    if config.epochs < 1 or config.batch_size < 1 or not math.isfinite(config.learning_rate) or config.learning_rate <= 0 or not math.isfinite(config.weight_decay) or config.weight_decay < 0:
        raise ValueError('Invalid optimizer configuration')
    if not valid.any():
        raise ValueError('No usable TRAIN innovations')
    torch.manual_seed(seed)
    model = InnovationHead(context.shape[1], arm, config.width, config.sigma_floor).to(device=context.device, dtype=context.dtype)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay)
    generator = torch.Generator(device='cpu').manual_seed(seed)
    histories = []
    context, log_prior, z, weights = [v.detach() for v in (context, log_prior, z, weights)]
    weights = weights / weights.mean()
    for epoch in range(config.epochs):
        model.train()
        order = torch.randperm(n, generator=generator)
        total = 0.
        for cpu_indices in order.split(config.batch_size):
            ix = cpu_indices.to(context.device)
            if arm == 'discriminative':
                log_p = model(context[ix], log_prior[ix], z[ix], valid[ix], centers)
                row = torch.arange(len(ix), device=context.device)
                losses = -log_p[row[:, None], torch.tensor([1, 2], device=context.device)[None], labels[ix, None]]
                # Invalid updates are a fixed prediction, not evidence to fit.
                losses = torch.where(valid[ix], losses, torch.zeros_like(losses))
            else:
                losses = conditional_nll(model, context[ix], z[ix], valid[ix], centers[labels[ix]])
            loss = (losses.mean(1) * weights[ix]).mean()
            _finite('Training loss', loss)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            gradient = nn.utils.clip_grad_norm_(model.parameters(), 5.)
            _finite('Gradient norm', gradient)
            optimizer.step()
            total += float(loss.detach()) * len(ix)
        histories.append({'epoch': epoch + 1, 'loss': total / n,
                          'row_order_sha256': hashlib.sha256(order.numpy().tobytes()).hexdigest()})
    return model.eval(), histories


def frozen_predictions(log_prior):
    """No-update control, including identical 1 s probabilities for all arms."""
    _finite('Log prior', log_prior)
    return log_prior.detach().double()[:, None, :].expand(-1, 3, -1).clone()


def load_frozen_start(data, input_identities, instrument_names, run_directory, seed, device='cpu', batch_size=2048):
    """Load an existing 1 s static artifact after schema/identity reproduction.

    `data`/identities must be the return of instrument_residual.extract(seconds=1).
    This function reads only small run artifacts, never waveforms or TEST data.
    It reuses the exact saved normalizer/mask and verifies the saved VAL outputs.
    Returns lists [TRAIN, VAL] of H1 and normalized log p1, plus provenance.
    """
    import instrument_residual as source
    run_directory = Path(run_directory)
    if batch_size < 1:
        raise ValueError('Positive inference batch size required')
    checkpoint_path = run_directory / f'instrument_seed{seed}.pth'
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=True)
    cfg = checkpoint['config']
    if checkpoint['family'] != 'instrument' or checkpoint['seed'] != seed or any(cfg.get(k) != v for k, v in {'seconds': 1, 'epochs': 15, 'beta': 5., 'anchor': 0., 'max_per_event': 4}.items()):
        raise ValueError('Expected the fixed 1 s, beta5, 15-epoch static starting artifact')
    prior_identities = json.loads((run_directory / 'input_identities.json').read_text())
    for key in ('metadata_sha256', 'normalization_sha256', 'inventory_sha256', 'checkpoint_sha256', 'preprocessing'):
        if prior_identities[key] != input_identities[key]:
            raise ValueError(f'Frozen starting input identity differs: {key}')
    with np.load(run_directory / 'training_rows.npz', allow_pickle=False) as saved:
        for key, data_key in [('row_index', 'train_rows'), ('event_ids', 'train_ids'), ('trace_names', 'train_trace_names'), ('weights', 'weights')]:
            if not np.array_equal(saved[key], data[data_key]):
                raise ValueError(f'Frozen starting TRAIN selection differs: {key}')
    arrays, mean, std, masks, base_dim = source.design_inputs(data)
    if base_dim != 245 or checkpoint['base_dim'] != base_dim or checkpoint['instrument_names'] != list(instrument_names) or checkpoint['native_names'] != source.NATIVE_FEATURE_NAMES:
        raise ValueError('Frozen starting feature schema differs')
    for name, actual in [('feature_mean', mean), ('feature_std', std), ('feature_mask', masks['instrument'])]:
        if not np.array_equal(checkpoint[name].numpy(), actual):
            raise ValueError(f'Frozen starting normalization/mask differs: {name}')
    model = source.ResidualDistribution(291).to(device)
    model.load_state_dict(checkpoint['model'], strict=True)
    model.eval().requires_grad_(False)
    contexts = [np.asarray(a * masks['instrument'], dtype=np.float32) for a in arrays]
    log_priors = []
    with torch.inference_mode():
        for split, context in zip(('train', 'val'), contexts):
            values = []
            for start in range(0, len(context), batch_size):
                stop = start + batch_size
                x = torch.as_tensor(context[start:stop], device=device)
                logits = torch.as_tensor(data[split + '_logits'][start:stop], device=device)
                values.append(model(x, logits).double().log_softmax(1).cpu().numpy())
            log_priors.append(np.concatenate(values))
    with np.load(run_directory / 'instrument_probabilities.npz', allow_pickle=False) as reference:
        for key, data_key in [('targets', 'val_y'), ('event_ids', 'val_ids'), ('trace_names', 'val_trace_names'), ('centers', 'centers')]:
            if not np.array_equal(reference[key], data[data_key]):
                raise ValueError(f'Frozen starting VAL identity differs: {key}')
        if not np.allclose(reference[f'seed{seed}'], np.exp(log_priors[1]), atol=2e-7, rtol=2e-6):
            raise ValueError('Frozen starting validation probabilities do not reproduce')
    paths = [checkpoint_path] + [run_directory / name for name in ('input_identities.json', 'training_rows.npz', 'instrument_probabilities.npz')]
    return contexts, log_priors, {'files_sha256': {str(p): source.sha256(p) for p in paths},
                                'seed': seed, 'starting_prior': 'Frozen cost-sensitive beta5 Huber+.075CE; not calibrated true Bayes'}

"""Training-only future-growth auxiliaries for an unchanged magnitude marginal.

The deployed forward takes only a supplied 1/3/5-second prefix. Auxiliary
labels never enter the magnitude decoder. Counts-derived running-peak growth
is a privileged training target, not a rupture-completion or physical-magnitude
measurement. Mixture responsibilities/composite likelihood are established
methods; see FUTURE_GROWTH.md for prior art and negative synthetic results.
"""
import math

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from sequential_models import DURATION_SAMPLES, MagnitudeDistributionModel


CONTROLS = ("supervised", "growth_mse", "unconditional_nll", "conditional_nll",
            "conditional_detached", "conditional_marginal_stopq")
TARGET_SECONDS = 10
SAMPLE_RATE = 100
PEAK_FLOOR_COUNTS = 1e-8
SIGMA_FLOOR = 0.1
SIGMA_CEILING = 5.0


def observed_growth(vertical, p_sample, peak_floor=PEAK_FLOOR_COUNTS):
    """Use the SAME pre-P one-second mean for all nested running peaks.

    vertical must contain the complete supplied trace in counts, sampled at
    100 Hz in INSTANCE's documented ENZ order. The caller slices only the
    required [P-100:P+1000] window from HDF5 before calling this function.
    Missing pre-P/future coverage is an error here, masked by the exporter.
    """
    a = np.asarray(vertical, dtype=np.float64)
    if a.ndim != 1 or not np.isfinite(a).all() or not np.isfinite(p_sample):
        raise ValueError("Require finite one-dimensional vertical counts and P sample")
    p = int(p_sample)
    if p != p_sample or p < SAMPLE_RATE or p + TARGET_SECONDS * SAMPLE_RATE > len(a):
        raise ValueError("P must be integral with one second before and ten after")
    if not np.isfinite(peak_floor) or peak_floor <= 0:
        raise ValueError("Peak floor must be finite and positive")
    baseline = float(a[p - SAMPLE_RATE:p].mean())
    signal = a[p:p + TARGET_SECONDS * SAMPLE_RATE] - baseline
    peaks = np.array([max(float(np.abs(signal[:t * SAMPLE_RATE]).max()), peak_floor)
                      for t in (1, 3, 5, TARGET_SECONDS)])
    # The difference of logarithms avoids overflow of a very large peak ratio.
    logs = np.log10(peaks)
    growth = logs[-1] - logs[:3]
    if not np.isfinite(growth).all() or np.any(growth < 0):
        raise ValueError("Nested peaks must produce finite nonnegative growth")
    return growth, peaks, baseline


class FutureGrowthModel(nn.Module):
    """All controls allocate identical parameters and magnitude-path RNG.

    forward(x) delegates to the exact independent baseline. The auxiliary
    method returns hidden states from exactly the same computation, with
    no future values or labels. Only the training loss conditions q on Y.
    """
    def __init__(self, channels=3, num_bins=66, hidden_dim=128):
        super().__init__()
        self.backbone = MagnitudeDistributionModel("independent", channels, num_bins, hidden_dim)
        # Output0 is a nonnegative regression mean; outputs1:4 parameterize
        # hurdle mass, positive-log-growth mean, and positive-log-growth scale.
        # Unused outputs remain allocated in every control.
        self.growth_head = nn.Sequential(nn.Linear(hidden_dim + 1, 64), nn.SiLU(), nn.Linear(64, 4))

    def forward(self, x):
        return self.backbone(x)

    def forward_with_states(self, x):
        if x.ndim != 3 or x.shape[1] != self.backbone.channels or x.shape[0] == 0:
            raise ValueError("Require a nonempty B x channels x L tensor")
        if x.shape[-1] not in DURATION_SAMPLES.values() or not x.is_floating_point():
            raise ValueError("Require floating 100/300/500-sample prefixes")
        outputs, states = {}, {}
        for t, stop in DURATION_SAMPLES.items():
            if stop > x.shape[-1]:
                break
            h = self.backbone.encoder(x[:, :, :stop])
            state = self.backbone.state_update(h, torch.zeros_like(h))
            outputs[t], states[t] = self.backbone.decoder(state), state
        return outputs, states

    def growth_parameters(self, state, labels=None):
        if labels is None:
            condition = state.new_zeros((len(state), 1))
        else:
            if labels.shape != (len(state),):
                raise ValueError("Require one auxiliary magnitude bin per hidden state")
            condition = ((labels.to(state.dtype) + .5) / self.backbone.num_bins - .5)[:, None]
        raw = self.growth_head(torch.cat([state, condition], -1)).float()
        return {"mean": F.softplus(raw[:, 0]), "zero_logit": raw[:, 1],
                "mu": raw[:, 2].clamp(-20., 10.),
                "sigma": (F.softplus(raw[:, 3]) + SIGMA_FLOOR).clamp_max(SIGMA_CEILING)}


def hurdle_log_prob(params, growth):
    """Density with respect to delta_0 plus Lebesgue measure on (0,infinity)."""
    if growth.shape != params["mu"].shape or not torch.isfinite(growth).all() or (growth < 0).any():
        raise ValueError("Growth targets must be finite, nonnegative and shape-aligned")
    positive = growth > 0
    log_g = torch.where(positive, growth, torch.ones_like(growth)).log()
    zero = F.logsigmoid(params["zero_logit"])
    log_density = (-log_g - params["sigma"].log() - .5 * math.log(2 * math.pi)
                   - .5 * ((log_g - params["mu"]) / params["sigma"]).square())
    return torch.where(positive, F.logsigmoid(-params["zero_logit"]) + log_density, zero)


def auxiliary_loss(model, outputs, states, labels, weights, growth, valid, control,
                   auxiliary_weight=.05, marginal_weight=.01):
    """Weighted mean over ALL records and available times; missing targets mask out.

    The supervised term is added separately by the runner without any change.
    stopq prevents the optional marginal term from training q through that
    term; the labeled conditional NLL still trains q. It does not make q true.
    """
    if control not in CONTROLS or auxiliary_weight < 0 or marginal_weight < 0:
        raise ValueError("Invalid control/auxiliary weights")
    if growth.shape != (len(labels), 3) or valid.shape != growth.shape or valid.dtype != torch.bool:
        raise ValueError("Growth and boolean masks must have shape B x 3")
    if weights.shape != labels.shape or not torch.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("Require one finite positive population weight per record")
    zero = next(iter(outputs.values())).new_zeros(())
    if control == "supervised":
        return zero, {"auxiliary": zero, "marginal": zero}
    auxiliary, marginal = [], []
    for j, t in enumerate(DURATION_SAMPLES):
        if t not in outputs:
            continue
        h = states[t].detach() if control == "conditional_detached" else states[t]
        conditional = control.startswith("conditional")
        params = model.growth_parameters(h, labels if conditional else None)
        g = torch.where(valid[:, j], growth[:, j], torch.zeros_like(growth[:, j]))
        loss = (params["mean"] - g).square() if control == "growth_mse" else -hurdle_log_prob(params, g)
        auxiliary.append((weights * torch.where(valid[:, j], loss, torch.zeros_like(loss))).mean())
        if control == "conditional_marginal_stopq":
            bins = model.backbone.num_bins
            expanded = h[:, None, :].expand(-1, bins, -1).reshape(-1, h.shape[1])
            bin_ids = torch.arange(bins, device=h.device).repeat(len(h))
            all_params = model.growth_parameters(expanded, bin_ids)
            log_q = hurdle_log_prob(all_params, g[:, None].expand(-1, bins).reshape(-1)).reshape(-1, bins)
            score = -torch.logsumexp(outputs[t].float().log_softmax(-1) + log_q.detach(), -1)
            marginal.append((weights * torch.where(valid[:, j], score, torch.zeros_like(score))).mean())
    aux = torch.stack(auxiliary).mean()
    mix = torch.stack(marginal).mean() if marginal else zero
    return auxiliary_weight * aux + marginal_weight * mix, {"auxiliary": aux.detach(), "marginal": mix.detach()}


def clip_gradients(model, max_norm=5.):
    """Separate clipping preserves magnitude updates in the detached control."""
    torch.nn.utils.clip_grad_norm_(model.backbone.parameters(), max_norm)
    torch.nn.utils.clip_grad_norm_(model.growth_head.parameters(), max_norm)

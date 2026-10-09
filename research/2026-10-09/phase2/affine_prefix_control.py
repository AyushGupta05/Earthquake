"""Matched independent-prefix controls for removing affine nuisance components.

This is ordinary least-squares projection, not a new magnitude method. At each
forecast deadline it acts BEFORE both normalized waveform and log-amplitude
branches. Exact invariance applies to ideal real-valued affine subtraction;
it does not certify causality of a quantized/resampled public release.
"""

import torch
from torch.nn import functional as F

from sequential_models import DURATION_SAMPLES, MagnitudeDistributionModel


CONTROLS = ("raw", "affine", "affine_guard1")


def project_affine_prefix(x, guard_samples=0):
    """Remove per-channel constant and time trend from the available prefix.

    With guard=1, discard the last sample BEFORE fitting, then append one zero
    to retain the model's original input length. No discarded value enters the
    projection, RMS, peak, or waveform branch. A one-sample guard is sufficient
    only for a separately established one-lookahead processing operator away
    from record edges; it is not a generic anti-filtering guarantee.

    Accumulate in float64 and return the input dtype. This reduces numerical
    cancellation but cannot undo rounding already present in the supplied x.
    The operation is differentiable and has no parameters, buffers, or RNG.
    """
    if x.ndim != 3 or x.shape[0] == 0 or x.shape[1] == 0:
        raise ValueError("Expected a nonempty B x C x L prefix")
    if not x.is_floating_point():
        raise TypeError("Prefix projection requires floating-point samples")
    if guard_samples not in (0, 1):
        raise ValueError("Only zero or one trailing guard sample is supported")
    length = x.shape[-1] - guard_samples
    if length < 2:
        raise ValueError("At least two retained samples are required")
    kept = x[..., :length].double()
    time = torch.arange(length, dtype=torch.float64, device=x.device)
    time = time - (length - 1) / 2
    centered = kept - kept.mean(-1, keepdim=True)
    slope = (centered * time).sum(-1, keepdim=True) / time.square().sum()
    projected = (centered - slope * time).to(x.dtype)
    return F.pad(projected, (0, guard_samples)) if guard_samples else projected


class AffinePrefixModel(MagnitudeDistributionModel):
    """The existing independent model, changing only its supplied prefixes.

    No frozen CNN, original logits, auxiliary branch, or station features are
    used. State-dict keys, parameter counts, constructor RNG, and raw forward
    behavior are identical to MagnitudeDistributionModel(mode='independent').
    """

    def __init__(self, control="affine", channels=3, num_bins=66, hidden_dim=128):
        if control not in CONTROLS:
            raise ValueError(f"Unknown control {control!r}; expected {CONTROLS}")
        super().__init__(mode="independent", channels=channels,
                         num_bins=num_bins, hidden_dim=hidden_dim)
        self.control = control

    def _forward(self, x, diagnostics):
        if self.control == "raw":
            return super()._forward(x, diagnostics)
        if (x.ndim != 3 or x.shape[1] != self.channels or x.shape[0] == 0
                or x.shape[-1] not in DURATION_SAMPLES.values()):
            raise ValueError("Require nonempty B x channels x L, L in {100,300,500}")
        if not x.is_floating_point():
            raise TypeError("Waveforms must be floating point")
        outputs, info = {}, {"entropy": {}, "gate": {}}
        state = x.new_zeros((x.shape[0], self.hidden_dim))
        for duration, stop in DURATION_SAMPLES.items():
            if stop > x.shape[-1]:
                break
            observed = project_affine_prefix(
                x[..., :stop], guard_samples=int(self.control == "affine_guard1"))
            state = torch.zeros_like(state)
            state = self.state_update(self.encoder(observed), state)
            logits = self.decoder(state)
            outputs[duration] = logits
            if diagnostics:
                info["entropy"][duration] = self.normalized_entropy(logits).detach()
        return outputs, info

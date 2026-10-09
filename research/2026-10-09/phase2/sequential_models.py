"""Controlled compact waveform models for 1-, 3-, and 5-second distributions.

All modes use the same residual-convolution encoder, GRUCell, and 66-bin
decoder. The independent baseline re-encodes each observed prefix and resets
the GRU state. Sequential modes encode disjoint [0,1], [1,3], [3,5] second
segments and retain a latent state. Their update is

    logits_t = log_softmax(logits_previous) + gate_t * innovation_t.

This is a learned discriminative logit correction, NOT an independently
calibrated Bayes likelihood. It does not multiply posteriors fitted to
overlapping prefixes. An entropy gate also sees the new segment embedding,
so low previous entropy does not force it to ignore surprising new evidence.
There is no monotonicity restriction on entropy or predicted magnitude.

Residual convolutions, recurrent state, and softmax distribution heads are
established components; this module alone establishes no novelty claim.
Inputs are float B x 3 x L globally standardized counts at 100 Hz, with
L in {100, 300, 500}. Dataset/channel calibration remains the caller's job.
No global/batch waveform statistic is fitted here. Prefix/segment-local RMS
normalization is accompanied by retained log RMS and log peak amplitudes.
"""

import math

import torch
from torch import nn
from torch.nn import functional as F


MODES = ("independent", "sequential", "entropy_gate")
DURATION_SAMPLES = {1: 100, 3: 300, 5: 500}


class ResidualBlock(nn.Module):
    """A small strided 1-D residual block; normalization is example-local."""

    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv1d(in_channels, out_channels, 5, stride=2, padding=2, bias=False),
            nn.GroupNorm(8, out_channels),
            nn.SiLU(),
            nn.Conv1d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.GroupNorm(8, out_channels),
        )
        self.skip = nn.Conv1d(in_channels, out_channels, 1, stride=2, bias=False)

    def forward(self, x):
        return F.silu(self.body(x) + self.skip(x))


class PrefixAmplitudeEncoder(nn.Module):
    """Encode only supplied samples, retaining scale removed from waveforms.

    Log amplitudes refer to the supplied globally standardized counts, not
    instrument-corrected displacement or velocity. They are not a substitute
    for the station response and distance controls needed in a final study.
    """

    def __init__(self, channels=3, hidden_dim=128, amplitude_floor=1e-8):
        super().__init__()
        if amplitude_floor <= 0:
            raise ValueError("amplitude_floor must be positive")
        self.amplitude_floor = amplitude_floor
        self.features = nn.Sequential(
            nn.Conv1d(channels, 32, 9, stride=2, padding=4, bias=False),
            nn.GroupNorm(8, 32),
            nn.SiLU(),
            ResidualBlock(32, 64),
            ResidualBlock(64, 96),
            ResidualBlock(96, 128),
        )
        self.project = nn.Sequential(
            nn.Linear(256 + 2 * channels + 1, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.SiLU(),
        )

    def forward(self, x):
        # Clamp before sqrt: zero waveforms must have finite input gradients.
        rms = x.square().mean(-1).clamp_min(self.amplitude_floor**2).sqrt()
        peak = x.abs().amax(-1).clamp_min(self.amplitude_floor)
        normalized = x / rms.unsqueeze(-1)
        wave = self.features(normalized)
        duration = x.new_full((len(x), 1), math.log(x.shape[-1] / 100.0))
        features = torch.cat(
            [wave.mean(-1), wave.amax(-1), rms.log(), peak.log(), duration], dim=1
        )
        return self.project(features)


class MagnitudeDistributionModel(nn.Module):
    """Return magnitude logits keyed by every complete observed duration.

    ``model(x500)`` returns ``{1: Bx66, 3: Bx66, 5: Bx66}``; x100 or x300
    returns only the available earlier outputs. ``forward_with_diagnostics``
    additionally returns detached normalized entropies and update gates,
    without changing inference. There is no gate at the first observation.

    Independent and ungated sequential modes have exactly equal parameter
    counts. Entropy gating adds only hidden_dim + 2 trainable parameters.
    Computational cost is intentionally different: the baseline recomputes
    overlapping prefixes; streaming sequential variants process each sample
    once. Shared modules allow supervision at all three observation times.
    """

    def __init__(self, mode="entropy_gate", channels=3, num_bins=66, hidden_dim=128):
        super().__init__()
        if mode not in MODES:
            raise ValueError(f"Unknown mode {mode!r}; choose from {MODES}")
        if channels < 1 or num_bins < 2 or hidden_dim < 1:
            raise ValueError("channels/hidden_dim must be positive and num_bins >= 2")
        self.mode = mode
        self.channels = channels
        self.num_bins = num_bins
        self.hidden_dim = hidden_dim
        self.encoder = PrefixAmplitudeEncoder(channels, hidden_dim)
        self.state_update = nn.GRUCell(hidden_dim, hidden_dim)
        self.decoder = nn.Linear(hidden_dim, num_bins)
        if mode == "entropy_gate":
            self.innovation_gate = nn.Linear(hidden_dim + 1, 1)
            # A neutral initial gate; neither high nor low entropy is assumed
            # to imply correctness. New evidence can override confident error.
            nn.init.zeros_(self.innovation_gate.weight)
            nn.init.zeros_(self.innovation_gate.bias)
        else:
            self.innovation_gate = None

    def parameter_counts(self):
        return {
            "total": sum(p.numel() for p in self.parameters()),
            "trainable": sum(p.numel() for p in self.parameters() if p.requires_grad),
            "encoder": sum(p.numel() for p in self.encoder.parameters()),
            "state_update": sum(p.numel() for p in self.state_update.parameters()),
            "decoder": sum(p.numel() for p in self.decoder.parameters()),
            "gate": (
                sum(p.numel() for p in self.innovation_gate.parameters())
                if self.innovation_gate is not None else 0
            ),
        }

    @staticmethod
    def normalized_entropy(logits):
        log_prob = F.log_softmax(logits, dim=-1)
        return -(log_prob.exp() * log_prob).sum(-1, keepdim=True) / math.log(logits.shape[-1])

    def _forward(self, x, diagnostics):
        if x.ndim != 3 or x.shape[1] != self.channels:
            raise ValueError(f"Expected B x {self.channels} x L waveform tensor")
        if x.shape[-1] not in DURATION_SAMPLES.values():
            raise ValueError("L must be 100, 300, or 500 samples at 100 Hz")
        if not x.is_floating_point():
            raise TypeError("Waveforms must be floating point, globally standardized counts")
        if x.shape[0] == 0:
            raise ValueError("Waveform batch cannot be empty")
        state = x.new_zeros((x.shape[0], self.hidden_dim))
        outputs, info = {}, {"entropy": {}, "gate": {}}
        previous_logits = None
        start = 0
        for duration, stop in DURATION_SAMPLES.items():
            if stop > x.shape[-1]:
                break
            if self.mode == "independent":
                observed = x[:, :, :stop]
                state = torch.zeros_like(state)
            else:
                observed = x[:, :, start:stop]
            features = self.encoder(observed)
            state = self.state_update(features, state)
            innovation = self.decoder(state)
            if previous_logits is None or self.mode == "independent":
                logits = innovation
            else:
                if self.innovation_gate is None:
                    gate = x.new_ones((x.shape[0], 1))
                else:
                    gate_input = torch.cat(
                        [features, self.normalized_entropy(previous_logits)], dim=1
                    )
                    gate = self.innovation_gate(gate_input).sigmoid()
                logits = F.log_softmax(previous_logits, dim=-1) + gate * innovation
                if diagnostics:
                    info["gate"][duration] = gate.detach()
            outputs[duration] = logits
            if diagnostics:
                info["entropy"][duration] = self.normalized_entropy(logits).detach()
            previous_logits = logits
            start = stop
        return outputs, info

    def forward(self, x):
        return self._forward(x, diagnostics=False)[0]

    def forward_with_diagnostics(self, x):
        return self._forward(x, diagnostics=True)

"""Research prototype: nested future-CDF distillation and revision energy.

Let Z_k = 1[Y <= k], X_t be the observed waveform prefix, F_t,k a current
CDF, and T_s,k a frozen teacher CDF using the FULL longer prefix X_s, s > t.
For ideal conditional forecasts and nested information,

    E[T_s,k | X_t] = F_t,k,
    R_t,s,k = E[(T_s,k - F_t,k)^2 | X_t]
            = Var(T_s,k | X_t) <= F_t,k * (1 - F_t,k).

Under ideal calibration, r = F(1-F) sigmoid(a) bounds 65 boundary-specific
outputs. With imperfect forecasts that envelope can exclude large corrections
to confidently wrong predictions. The "unit" option uses r = sigmoid(a) to
estimate empirical squared CDF revision, which is always in [0,1] per boundary
without a calibration assumption. Neither output is magnitude error or a
guaranteed confidence interval.
The five-second forecast has no resolution output because no later data is
available here. Default resolution horizons are 1->3 and 3->5 seconds.

Per-record training components, with bin spacing d=0.1, are:

    CE(logits, Y)
    d * sum_k (F_k - 1[Y <= k])^2
    d * sum_k (F_k - stopgrad(T_k))^2
    d * sum_k (r_k - stopgrad((T_k - stopgrad(F_k))^2))^2.

CE and the ordinal CDF score are proper supervised scores. The additional
terms are an EMPIRICAL hypothesis: a trained teacher is imperfect and the
tower identity is not guaranteed. Teacher miscalibration can bias the student.
Even for an ideal teacher, a single squared innovation can exceed F(1-F);
the envelope bounds its conditional mean, so observed targets are not clipped.
By default the envelope F(1-F) is detached in the auxiliary resolution path
to prevent directly moving the probability decoder to improve that loss.
The shared representation can still trade objectives off. Compare against
supervised-only and distillation-only controls on held-out earthquakes.

Teacher inputs are sliced from the same example tensor and always include
the current prefix. Train/fold/event identity and teacher training provenance
must still be enforced by the runner: freezing alone does not prevent leakage.
This module makes no novelty or calibration guarantee. DIME (ICLR 2024,
arXiv:2306.03301) is relevant prior art for conditional-variance/value heads.
"""

import math

import torch
from torch import nn
from torch.nn import functional as F

from sequential_models import DURATION_SAMPLES, MagnitudeDistributionModel


def _horizon_mapping(future_horizons):
    horizons = {1: 3, 3: 5} if future_horizons is None else dict(future_horizons)
    for current, future in horizons.items():
        if current not in DURATION_SAMPLES or future not in DURATION_SAMPLES or future <= current:
            raise ValueError("Resolution horizons must be nested available durations with future > current")
    return horizons


def cdf_from_logits(logits):
    """CDF at interior boundaries; the certain final boundary is omitted."""
    if logits.ndim != 2 or logits.shape[1] < 2:
        raise ValueError("Expected B x K logits with K >= 2")
    # Roundoff when the final-bin probability is tiny must not make the
    # Bernoulli variance envelope slightly negative.
    return logits.softmax(-1).cumsum(-1)[:, :-1].clamp(0.0, 1.0)


def bounded_resolution(cdf, head_logits, detach_envelope=True, envelope="bernoulli"):
    """Unit revision energy, or an ideal-calibrated Bernoulli-envelope ablation."""
    if cdf.shape != head_logits.shape:
        raise ValueError("CDF and resolution head must have matching shapes")
    if envelope == "unit":
        return head_logits.sigmoid()
    if envelope != "bernoulli":
        raise ValueError("Resolution envelope must be 'unit' or 'bernoulli'")
    envelope_cdf = cdf.detach() if detach_envelope else cdf
    return envelope_cdf * (1 - envelope_cdf) * head_logits.sigmoid()


class ResolutionDistillationModel(nn.Module):
    """Independent-prefix student plus a shared 65-value resolution head.

    ``forward(x)`` preserves the baseline runner API: {duration: logits}.
    ``forward_with_resolution(x)`` returns {duration: forecast_dict}, where
    each dictionary has duration, future_duration, logits, cdf, resolution.
    The last two fields have B x 65 shape, except resolution is None when no
    later horizon is configured. A checkpoint from the existing independent
    baseline can initialize ``model.backbone.load_state_dict(state_dict)``.
    """

    def __init__(self, channels=3, num_bins=66, hidden_dim=128,
                 future_horizons=None, detach_resolution_envelope=True,
                 resolution_envelope="bernoulli", detach_resolution_features=False):
        super().__init__()
        if resolution_envelope not in ("unit", "bernoulli"):
            raise ValueError("Resolution envelope must be 'unit' or 'bernoulli'")
        self.future_horizons = _horizon_mapping(future_horizons)
        self.detach_resolution_envelope = detach_resolution_envelope
        self.resolution_envelope = resolution_envelope
        self.detach_resolution_features = detach_resolution_features
        self.backbone = MagnitudeDistributionModel(
            mode="independent", channels=channels, num_bins=num_bins, hidden_dim=hidden_dim
        )
        self.resolution_head = nn.Linear(hidden_dim, num_bins - 1)
        # Midpoint of the selected envelope is initialization, not evidence
        # about how much revision/uncertainty resolves in two seconds.
        nn.init.zeros_(self.resolution_head.weight)
        nn.init.zeros_(self.resolution_head.bias)

    def forward_with_resolution(self, x):
        if x.ndim != 3 or x.shape[1] != self.backbone.channels:
            raise ValueError(f"Expected B x {self.backbone.channels} x L waveform tensor")
        if x.shape[-1] not in DURATION_SAMPLES.values() or x.shape[0] == 0:
            raise ValueError("Require a nonempty batch with L in {100, 300, 500}")
        if not x.is_floating_point():
            raise TypeError("Waveforms must be floating point")
        forecasts = {}
        for duration, samples in DURATION_SAMPLES.items():
            if samples > x.shape[-1]:
                break
            # This is exactly the independent baseline's current-prefix path.
            features = self.backbone.encoder(x[:, :, :samples])
            state = self.backbone.state_update(features, torch.zeros_like(features))
            logits = self.backbone.decoder(state)
            cdf = cdf_from_logits(logits)
            future = self.future_horizons.get(duration)
            auxiliary_state = state.detach() if self.detach_resolution_features else state
            resolution = (
                bounded_resolution(cdf, self.resolution_head(auxiliary_state),
                                   self.detach_resolution_envelope, self.resolution_envelope)
                if future is not None else None
            )
            forecasts[duration] = {
                "duration": duration, "future_duration": future,
                "logits": logits, "cdf": cdf, "resolution": resolution,
            }
        return forecasts

    def forward(self, x):
        return {t: forecast["logits"] for t, forecast in self.forward_with_resolution(x).items()}

    def parameter_counts(self):
        result = self.backbone.parameter_counts()
        result["resolution_head"] = sum(p.numel() for p in self.resolution_head.parameters())
        result["total"] = sum(p.numel() for p in self.parameters())
        result["trainable"] = sum(p.numel() for p in self.parameters() if p.requires_grad)
        return result


class FrozenNestedTeacher(nn.Module):
    """Freeze an owned teacher and generate targets from complete later prefixes.

    The supplied model must map B x C x L input to {duration: B x K logits}.
    This wrapper freezes that model in place and keeps it in eval mode even
    when a containing module calls train(). Do not share it with a model that
    is still being optimized. Only available later horizons produce targets.
    """

    def __init__(self, teacher, future_horizons=None):
        super().__init__()
        self.teacher = teacher
        self.future_horizons = _horizon_mapping(future_horizons)
        self.teacher.requires_grad_(False)
        self.train(False)

    def train(self, mode=True):
        super().train(False)
        return self

    @torch.no_grad()
    def forward(self, x):
        if x.ndim != 3 or x.shape[-1] not in DURATION_SAMPLES.values() or x.shape[0] == 0:
            raise ValueError("Require nonempty B x C x L input with L in {100, 300, 500}")
        if not x.is_floating_point():
            raise TypeError("Waveforms must be floating point")
        # Defend against a caller changing the owned child's mode directly.
        self.teacher.eval()
        cached, targets = {}, {}
        for current, future in self.future_horizons.items():
            samples = DURATION_SAMPLES[future]
            if samples > x.shape[-1]:
                continue
            if future not in cached:
                # The future observation explicitly contains the earlier data.
                predictions = self.teacher(x[:, :, :samples])
                if future not in predictions:
                    raise ValueError(f"Teacher did not return a {future}-second prediction")
                cached[future] = cdf_from_logits(predictions[future]).detach()
            targets[current] = {
                "current_duration": current, "teacher_duration": future,
                "cdf": cached[future],
            }
        return targets


def forecast_losses(forecast, labels, teacher_target=None, *, ce_weight=1.0,
                    ordinal_weight=1.0, distillation_weight=1.0,
                    resolution_weight=1.0, bin_width=0.1):
    """Return unreduced B-vectors; the runner applies event/sample weights.

    Set both auxiliary weights to zero for a supervised-only control. An
    available future forecast requires a target when either auxiliary weight
    is nonzero; a terminal forecast needs no target and uses supervised loss.
    Current and teacher forecasts must refer to the same rows and bin grid.
    Cross-record/partition identity is the runner's responsibility.
    """
    weights = (ce_weight, ordinal_weight, distillation_weight, resolution_weight)
    if any(not math.isfinite(w) or w < 0 for w in weights):
        raise ValueError("Loss weights must be finite and nonnegative")
    if not math.isfinite(bin_width) or bin_width <= 0:
        raise ValueError("bin_width must be positive and finite")
    logits, cdf = forecast["logits"], forecast["cdf"]
    if cdf.shape != (logits.shape[0], logits.shape[1] - 1):
        raise ValueError("Forecast CDF and logits shapes disagree")
    if labels.shape != (logits.shape[0],):
        raise ValueError("Labels must contain one bin index per record")
    cuts = torch.arange(cdf.shape[1], device=cdf.device)
    observed = (labels[:, None] <= cuts).to(cdf.dtype)
    ce = F.cross_entropy(logits, labels, reduction="none")
    ordinal = bin_width * (cdf - observed).square().sum(-1)
    distillation = torch.zeros_like(ce)
    resolution = torch.zeros_like(ce)
    future = forecast["future_duration"]
    if future is None:
        if teacher_target is not None:
            raise ValueError("Terminal forecast has no configured future-resolution horizon")
    elif teacher_target is None:
        if distillation_weight > 0 or resolution_weight > 0:
            raise ValueError("Auxiliary losses require a matching frozen nested teacher target")
    else:
        if (teacher_target["current_duration"] != forecast["duration"]
                or teacher_target["teacher_duration"] != future
                or future <= forecast["duration"]):
            raise ValueError("Teacher target does not match the forecast's nested horizon")
        teacher_cdf = teacher_target["cdf"].detach()
        if teacher_cdf.shape != cdf.shape:
            raise ValueError("Teacher and student CDF shapes disagree")
        predicted_resolution = forecast["resolution"]
        if predicted_resolution is None or predicted_resolution.shape != cdf.shape:
            raise ValueError("A nonterminal forecast requires matching resolution predictions")
        distillation = bin_width * (cdf - teacher_cdf).square().sum(-1)
        # Do not clip this sample target to the conditional-mean envelope.
        resolution_target = (teacher_cdf - cdf.detach()).square()
        resolution = bin_width * (predicted_resolution - resolution_target).square().sum(-1)
    total = (ce_weight * ce + ordinal_weight * ordinal
             + distillation_weight * distillation + resolution_weight * resolution)
    return {"ce": ce, "ordinal": ordinal, "distillation": distillation,
            "resolution": resolution, "total": total}

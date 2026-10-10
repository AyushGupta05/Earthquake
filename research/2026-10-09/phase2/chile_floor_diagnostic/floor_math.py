"""Output-space diagnostic only. No trainable head or optimizer is defined."""
import math
import numpy as np

EPSILON = 1e-6
DELTA = 2.0


def logsumexp(x, axis=-1, keepdims=False):
    maximum = np.max(x, axis=axis, keepdims=True)
    value = maximum + np.log(np.exp(x - maximum).sum(axis=axis, keepdims=True))
    return value if keepdims else np.squeeze(value, axis=axis)


def logsoftmax(x):
    shifted = x - np.max(x, axis=-1, keepdims=True)
    return shifted - logsumexp(shifted, keepdims=True)


def huber_constants(delta=DELTA):
    if not math.isfinite(delta) or delta <= 0:
        raise ValueError("Positive finite Huber delta required")
    core = math.sqrt(2 * math.pi) * math.erf(delta / math.sqrt(2))
    tail = math.exp(-delta * delta / 2)
    z = core + 2 * tail / delta
    variance = (core + 4 * tail * (1 / delta + 1 / delta**3)) / z
    return z, variance


def diagnose(logits, means, scales, targets):
    """B x 5 outputs; derivatives are of each event's NLL (no batch mean).

    Logit derivatives are pre-softmax; mean and scale derivatives are after
    ReLU/scale floor. They do not include the neural Jacobian or clipping.
    The hypothetical Huber diagnostic preserves each mean and variance.
    """
    logits, means, scales, targets = [np.asarray(x, dtype=np.float64)
                                     for x in (logits, means, scales, targets)]
    if logits.ndim != 2 or logits.shape[1] != 5 or len(logits) == 0:
        raise ValueError("Nonempty B x 5 mixture required")
    if means.shape != logits.shape or scales.shape != logits.shape or targets.shape != (len(logits),):
        raise ValueError("Mixture/target alignment mismatch")
    if not all(np.isfinite(x).all() for x in (logits, means, scales, targets)) or (scales <= 0).any():
        raise ValueError("Finite outputs and positive scales required")
    logw = logsoftmax(logits)
    weights = np.exp(logw)
    residual = (targets[:, None] - means) / scales
    gaussian = -.5 * residual**2 - np.log(scales) - .5 * math.log(2 * math.pi)
    z, variance = huber_constants()
    u = math.sqrt(variance) * residual
    absolute = np.abs(u)
    # minimum avoids evaluating an unnecessarily large quadratic tail.
    huber_penalty = .5 * np.minimum(absolute, DELTA)**2 + DELTA * np.maximum(absolute - DELTA, 0)
    huber = .5 * math.log(variance) - np.log(scales) - math.log(z) - huber_penalty
    result = {"normalized_weights": weights}
    for family, logcomponent in (("gaussian", gaussian), ("huber", huber)):
        # Center the component density before adding log weights: a huge
        # common negative log-density must not erase their relative weights.
        offset = np.max(logcomponent, axis=-1, keepdims=True)
        centered_joint = logw + (logcomponent - offset)
        logdensity = offset[:, 0] + logsumexp(centered_joint)
        logr = logsoftmax(centered_joint)
        responsibility = np.exp(logr)
        entropy = -np.sum(responsibility * logr, axis=1)
        result.update({family + "_" + name: value for name, value in {
            "component_log_density": logcomponent,
            "log_density": logdensity,
            "log_responsibility": logr,
            "responsibility": responsibility,
            "responsibility_entropy": entropy,
            "effective_components": np.exp(entropy),
            "nll": -logdensity,
            "grad_logits": weights - responsibility,
        }.items()})
        if family == "gaussian":
            component_mu = -residual / scales
            component_logscale = 1 - residual**2
        else:
            psi = np.clip(u, -DELTA, DELTA)
            component_mu = -math.sqrt(variance) * psi / scales
            component_logscale = 1 - psi * u
        result[family + "_component_nll_score_means"] = component_mu
        result[family + "_component_nll_score_logscales"] = component_logscale
        grad_mu = responsibility * component_mu
        grad_logscale = responsibility * component_logscale
        result[family + "_grad_means"] = grad_mu
        result[family + "_grad_logscales"] = grad_logscale
        result[family + "_grad_scales"] = grad_logscale / scales
    logdensity = result["gaussian_log_density"]
    logfloored = np.logaddexp(logdensity, math.log(EPSILON))
    logattenuation = logdensity - logfloored
    attenuation = np.exp(logattenuation)
    result.update(log_attenuation=logattenuation, attenuation=attenuation,
                  floored_gaussian_nll=-logfloored,
                  gaussian_density=np.exp(logdensity))
    for name in ("logits", "means", "logscales", "scales"):
        result["floored_gaussian_grad_" + name] = attenuation[:, None] * result["gaussian_grad_" + name]
    mean = np.sum(weights * means, axis=1)
    result["normalized_mixture_mean"] = mean
    result["mixture_standard_deviation"] = np.sqrt(np.sum(weights * (scales**2 + (means - mean[:, None])**2), axis=1))
    if not all(np.isfinite(value).all() for value in result.values()):
        raise FloatingPointError("Nonfinite diagnostic; no partial gate is valid")
    return result


def event_gate(event_ids, targets, source_means, attenuation):
    """Columns must be exactly the fixed 1,3,5 s order, one row per event."""
    ids = list(map(str, event_ids))
    y = np.asarray(targets, dtype=np.float64)
    means, factors = np.asarray(source_means), np.asarray(attenuation)
    if not ids or len(set(ids)) != len(ids) or y.shape != (len(ids),):
        raise ValueError("Unique aligned events required")
    if means.shape != (len(ids), 3) or factors.shape != means.shape:
        raise ValueError("Exactly three aligned deadlines required")
    if not all(np.isfinite(a).all() for a in (y, means, factors)) or ((factors < 0) | (factors > 1)).any():
        raise ValueError("Invalid gate inputs")
    joint = (factors < .1) & ((y[:, None] - means) > .5)
    qualifying = (y >= 5.5) & (joint.sum(axis=1) >= 2)
    return {"passed": bool(qualifying.sum() >= 4), "qualifying_count": int(qualifying.sum()),
            "qualifying_event_ids": [ids[i] for i in np.flatnonzero(qualifying)],
            "joint_deadline_count": joint.sum(axis=1).tolist(),
            "interpretation": "Current TRAIN suppression only; no historical causal or held-out benefit claim",
            "next_action": "Eligible for separately authorized pilot" if qualifying.sum() >= 4 else "Stop proposed floor mechanism pilot"}

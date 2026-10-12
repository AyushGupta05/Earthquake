"""Numerical C/H operator only; inputs are already deadline-qualified activity.

No waveform extraction, clocks, training, files, network, or automatic experiment.
"""
from dataclasses import dataclass
import math
import warnings
import numpy as np


class NumericalFailure(RuntimeError):
    """A computation cannot support an accepted inference; never clips a model."""


def _array(value, shape=None):
    a = np.array(value, dtype=np.float64, copy=True)
    if (shape is not None and a.shape != shape) or not np.all(np.isfinite(a)):
        raise ValueError("finite array with required shape expected")
    a.setflags(write=False)
    return a


def _lse(a, axis=None):
    a = np.asarray(a, dtype=np.float64)
    hi = np.max(a, axis=axis, keepdims=True)
    if not np.all(np.isfinite(hi)):
        raise NumericalFailure("logsumexp has no finite dominant term")
    out = hi + np.log(np.sum(np.exp(a - hi), axis=axis, keepdims=True))
    return np.squeeze(out, axis=axis)


def _sigmoid(a):
    return np.exp(-np.logaddexp(0., -np.asarray(a)))


@dataclass(frozen=True)
class Mixture:
    weights: np.ndarray
    means: np.ndarray
    sigmas: np.ndarray

    def __post_init__(self):
        for key in ("weights", "means", "sigmas"):
            object.__setattr__(self, key, _array(getattr(self, key), (5,)))
        if (np.any(self.weights < 0) or
                abs(float(self.weights.sum()) - 1.) > 1e-12 or
                np.any(self.sigmas < .05)):
            raise ValueError("five normalized nonnegative weights and sigma >= .05 required")

    @classmethod
    def from_raw(cls, raw):
        """Layout: five logits, five uncapped means, five rho values."""
        raw = _array(raw, (15,))
        w = np.exp(raw[:5] - _lse(raw[:5]))
        return cls(w, raw[5:10], .05 + np.logaddexp(0., raw[10:]))

    def logpdf(self, m):
        m = _array(m)
        with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            x = (m[..., None] - self.means) / self.sigmas
            terms = (np.log(self.weights) - np.log(self.sigmas)
                     - .5 * math.log(2 * math.pi) - .5 * x * x)
        return _lse(terms, axis=-1)


@dataclass(frozen=True)
class Hazard:
    """Index 0 = on (quiet to active); 1 = off (active to quiet).

    C extra coefficients are eta_on/off times log(1+run_age).
    H replaces them by z[0]*z[1] and z[0]*c[0], respectively.
    These are measured initial features, never magnitude/run-age interactions.
    """
    arm: str
    alpha: np.ndarray
    beta: np.ndarray
    z_weights: np.ndarray
    c_weights: np.ndarray
    gamma: np.ndarray
    extra: np.ndarray
    mref: float

    def __post_init__(self):
        if self.arm not in ("C", "H"):
            raise ValueError("arm must be C or H")
        for key in ("alpha", "beta", "gamma", "extra"):
            object.__setattr__(self, key, _array(getattr(self, key), (2,)))
        for key in ("z_weights", "c_weights"):
            a = _array(getattr(self, key))
            if a.ndim != 2 or a.shape[0] != 2:
                raise ValueError("feature weights must be 2 by dimension")
            object.__setattr__(self, key, a)
        if not isinstance(self.mref, (int, float)) or not math.isfinite(self.mref):
            raise ValueError("finite mref required")
        if self.arm == "H" and (self.z_weights.shape[1] < 2 or self.c_weights.shape[1] < 1):
            raise ValueError("H requires two initial z coordinates and one c coordinate")

    @property
    def parameter_count(self):
        return 8 + self.z_weights.size + self.c_weights.size

    def logits(self, m, z, c, hazard_indices, local_times, previous_ages):
        z = _array(z, (self.z_weights.shape[1],))
        c = _array(c, (self.c_weights.shape[1],))
        m = _array(m)
        idx = np.asarray(hazard_indices)
        u = _array(local_times, idx.shape)
        r = _array(previous_ages, idx.shape)
        if idx.ndim != 1 or idx.dtype.kind not in "iu" or np.any((idx < 0) | (idx > 1)):
            raise ValueError("one-dimensional on/off indices required")
        if np.any(u < 0) or np.any(r < 1) or np.any(r > 20) or np.any(r != np.floor(r)):
            raise ValueError("nonnegative local times and integer ages 1..20 required")
        try:
            with np.errstate(over="raise", invalid="raise"):
                common = self.alpha + self.z_weights @ z + self.c_weights @ c
                if self.arm == "C":
                    extra = self.extra[idx] * np.log1p(r)
                else:
                    extra = (self.extra * np.array([z[0] * z[1], z[0] * c[0]]))[idx]
                ell = (common[idx] + self.gamma[idx] * np.log1p(u) + extra
                       + (m[..., None] - self.mref) * self.beta[idx])
        except FloatingPointError as exc:
            raise NumericalFailure("hazard arithmetic overflow") from exc
        if not np.all(np.isfinite(ell)):
            raise NumericalFailure("nonfinite logits")
        return ell


def transitions(states, prefix_cells=None):
    """Only observed edges after b1; no fictitious exit at the deadline."""
    raw = np.asarray(states)
    if raw.ndim != 1 or raw.dtype.kind not in "biu" or not 1 <= len(raw) <= 20:
        raise ValueError("one to twenty observed binary cells required")
    if np.any((raw != 0) & (raw != 1)):
        raise ValueError("binary cells required")
    if prefix_cells is None:
        prefix_cells = len(raw)
    if type(prefix_cells) is not int or not 1 <= prefix_cells <= len(raw):
        raise ValueError("valid integer prefix length required")
    b = raw[:prefix_cells].astype(np.int64)
    age = 1
    ages = []
    for j in range(1, len(b)):
        ages.append(age)
        age = age + 1 if b[j] == b[j - 1] else 1
    # Active -> quiet uses off; quiet -> active uses on. A stay is y=0.
    return (b[:-1], (b[1:] != b[:-1]).astype(np.float64),
            .25 * np.arange(1, len(b), dtype=np.float64), np.array(ages, dtype=np.float64))


def log_likelihood(m, hazard, z, c, states, prefix_cells=None):
    idx, y, u, r = transitions(states, prefix_cells)
    ell = hazard.logits(m, z, c, idx, u, r)
    # Signed softplus avoids y*ell cancellation for very large positive logits.
    signed = np.where(y == 1, -ell, ell)
    out = -np.sum(np.logaddexp(0., signed), axis=-1)
    if not np.all(np.isfinite(out)):
        raise NumericalFailure("nonfinite likelihood")
    return out


def joint_loss(mw, mixture, hazard, z, c, states):
    """Displayed generative J, not posterior-normalized conditional NLL."""
    mw = float(mw)
    base = -float(mixture.logpdf(mw))
    sequence = -float(log_likelihood(mw, hazard, z, c, states))
    return {"base_nll": base, "sequence_nll": sequence, "joint_nll": base + sequence}


@dataclass(frozen=True)
class Integral:
    method: str
    log_normalizer: float
    mean: float
    nll: float


def gauss_hermite(mixture, hazard, z, c, states, mw, order):
    if order not in (64, 128):
        raise ValueError("only prospectively fixed orders 64 and 128 supported")
    x, w = np.polynomial.hermite.hermgauss(order)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        nodes = mixture.means[:, None] + math.sqrt(2.) * mixture.sigmas[:, None] * x
        log_mass = np.log(mixture.weights[:, None]) + np.log(w[None, :]) - .5 * math.log(math.pi)
    if not np.all(np.isfinite(nodes)):
        raise NumericalFailure("nonfinite quadrature nodes")
    a = log_mass + log_likelihood(nodes, hazard, z, c, states)
    log_z = float(_lse(a.ravel()))
    mean = float(np.sum(np.exp(a - log_z) * nodes))
    nll = float(-mixture.logpdf(mw) - log_likelihood(mw, hazard, z, c, states) + log_z)
    if not all(math.isfinite(t) for t in (log_z, mean, nll)):
        raise NumericalFailure("nonfinite GH integral")
    return Integral("GH%d" % order, log_z, mean, nll)


def adaptive(mixture, hazard, z, c, states, mw):
    """Independent all-real-line SciPy integration, with mode/curvature scaling.

    Each component's Gaussian times affine-logistic sequence is log-concave.
    Its analytic derivative has a unique root, bracketed by sum(abs(beta*sigma)).
    Scaling is numerical only: no magnitude support or hazard coefficient clipping.
    """
    from scipy.integrate import quad, IntegrationWarning
    from scipy.optimize import brentq
    idx, y, u, r = transitions(states)
    terms = []
    means = []
    for weight, mu, sigma in zip(mixture.weights, mixture.means, mixture.sigmas):
        if weight == 0:
            continue
        slopes = hazard.beta[idx] * sigma
        bound = float(np.sum(np.abs(slopes)))
        if not math.isfinite(bound):
            raise NumericalFailure("nonfinite adaptive mode bracket")

        def logits_at(x):
            return hazard.logits(mu + sigma * x, z, c, idx, u, r)

        def deriv(x):
            return float(-x + np.sum(slopes * (y - _sigmoid(logits_at(x)))))

        mode = 0. if bound == 0 else brentq(deriv, -bound, bound, xtol=1e-12, maxiter=500)
        p = _sigmoid(logits_at(mode))
        with np.errstate(over="ignore", invalid="ignore"):
            curvature = float(1. + np.sum(slopes * slopes * p * (1. - p)))
        if not math.isfinite(curvature):
            raise NumericalFailure("nonfinite adaptive curvature")
        scale = 1. / math.sqrt(curvature)
        if mode + scale == mode:
            raise NumericalFailure("adaptive mode resolution insufficient")

        def log_f(x):
            return float(-.5 * x * x - .5 * math.log(2. * math.pi)
                         + log_likelihood(mu + sigma * x, hazard, z, c, states))

        peak = log_f(mode)

        def integrand(t):
            x = mode + scale * t
            if not math.isfinite(x) or not math.isfinite(mu + sigma * x):
                raise NumericalFailure("nonfinite adaptive point")
            exponent = log_f(x) - peak
            if exponent > 1e-7:
                raise NumericalFailure("adaptive root is not the component maximum")
            return math.exp(exponent)

        def integrate(fun):
            with warnings.catch_warnings():
                warnings.simplefilter("error", IntegrationWarning)
                answer = quad(fun, -np.inf, np.inf, epsabs=1e-10, epsrel=1e-10,
                              limit=300, full_output=1)
            if len(answer) != 3:
                raise NumericalFailure("adaptive integration did not converge")
            value, error, _ = answer
            if not math.isfinite(value) or not math.isfinite(error) or error > max(1e-9, abs(value) * 1e-9):
                raise NumericalFailure("adaptive error bound too large")
            return value

        mass = integrate(integrand)
        moment = integrate(lambda t: t * integrand(t))
        if mass <= 0:
            raise NumericalFailure("adaptive component mass unavailable")
        terms.append(math.log(weight) + peak + math.log(scale) + math.log(mass))
        means.append(mu + sigma * (mode + scale * moment / mass))
    log_z = float(_lse(terms))
    mean = float(np.sum(np.exp(np.asarray(terms) - log_z) * np.asarray(means)))
    nll = float(-mixture.logpdf(mw) - log_likelihood(mw, hazard, z, c, states) + log_z)
    if not all(math.isfinite(t) for t in (log_z, mean, nll)):
        raise NumericalFailure("nonfinite adaptive result")
    return Integral("adaptive", log_z, mean, nll)


def checked_inference(mixture, hazard, z, c, states, mw):
    """Never reports accepted=True without 64/128 and independent adaptive parity."""
    a = gauss_hermite(mixture, hazard, z, c, states, mw, 64)
    b = gauss_hermite(mixture, hazard, z, c, states, mw, 128)
    d = adaptive(mixture, hazard, z, c, states, mw)
    keys = ("log_normalizer", "mean", "nll")
    errors = {key: max(abs(getattr(a, key) - getattr(b, key)),
                       abs(getattr(a, key) - getattr(d, key)),
                       abs(getattr(b, key) - getattr(d, key))) for key in keys}
    return {"accepted": all(e <= 1e-4 for e in errors.values()),
            "errors": errors, "gh64": a, "gh128": b, "adaptive": d}

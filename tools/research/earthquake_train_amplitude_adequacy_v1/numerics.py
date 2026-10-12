"""Deterministic all-real Gaussian/selection-normal posteriors; no data IO."""
import math
import time
from dataclasses import dataclass
import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq
from scipy.special import log_ndtr, ndtr

TOL = 1e-4
LOG2PI = math.log(2 * math.pi)


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('source_deadline')


def finite(value):
    if not math.isfinite(float(value)):
        raise ArithmeticError('nonfinite_numeric')
    return float(value)


def normal_logpdf(x, mean, sd):
    if not math.isfinite(sd) or sd <= 0:
        raise ArithmeticError('invalid_scale')
    z = (x - mean) / sd
    return finite(-.5 * z * z - math.log(sd) - .5 * LOG2PI)


def normal_crps(x, mean, sd):
    z = (x - mean) / sd
    phi = math.exp(-.5 * z * z) / math.sqrt(2 * math.pi)
    result = sd * (z * (2 * float(ndtr(z)) - 1) + 2 * phi - 1 / math.sqrt(math.pi))
    if result < 0:
        raise ArithmeticError('negative_crps')
    return finite(result)


def integrate(f, low, high, deadline, eps=2e-9):
    check_deadline(deadline)
    def checked(x):
        check_deadline(deadline)
        return finite(f(x))
    value, error = quad(checked, low, high, epsabs=eps, epsrel=eps, limit=200)
    if not math.isfinite(value) or not math.isfinite(error) or error > 1e-6:
        raise ArithmeticError('quadrature_not_certified')
    return value, error


@dataclass(frozen=True)
class NormalPosterior:
    mean: float
    sd: float
    deadline: float

    def logpdf(self, x):
        check_deadline(self.deadline)
        return normal_logpdf(x, self.mean, self.sd)

    def cdf(self, x):
        check_deadline(self.deadline)
        return float(ndtr((x - self.mean) / self.sd))

    def median(self):
        return self.mean

    def score(self, x):
        result = normal_crps(x, self.mean, self.sd)
        z = (x - self.mean) / self.sd
        left, le = integrate(lambda u: float(ndtr(u)) ** 2, -np.inf, z, self.deadline)
        right, re = integrate(lambda u: float(ndtr(-u)) ** 2, z, np.inf, self.deadline)
        error = abs(self.sd * (left + right) - result) + self.sd*(le+re)
        if error > TOL:
            raise ArithmeticError('normal_crps_reference_disagreement')
        return {'mean': finite(self.mean), 'median': finite(self.mean),
                'nll': finite(-self.logpdf(x)), 'crps': result, 'numerical_error': finite(error)}


@dataclass(frozen=True)
class CensoredPosterior:
    """Z~N(0,1), conditioned on b Z + noise <= limit-offset."""
    prior_mean: float
    prior_sd: float
    offset: float
    slope: float
    sigma: float
    limit: float
    deadline: float

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.prior_mean, self.prior_sd, self.offset,
                                             self.slope, self.sigma, self.limit)):
            raise ArithmeticError('selection_parameters_nonfinite')
        if self.prior_sd <= 0 or self.slope < 0 or self.sigma < .1:
            raise ArithmeticError('selection_parameters_invalid')
        total = math.hypot(self.slope, self.sigma)
        t = (self.limit - self.offset) / total
        rho = self.slope / total
        lognorm = float(log_ndtr(t))
        mills = math.exp(-.5 * t * t - .5 * LOG2PI - lognorm)
        ez = -rho * mills
        vz = 1 - rho * rho * mills * (mills + t)
        if not math.isfinite(vz) or vz <= 0:
            raise ArithmeticError('selection_variance_unknown')
        object.__setattr__(self, 'log_normalizer', finite(lognorm))
        object.__setattr__(self, 'mean', finite(self.prior_mean + self.prior_sd * ez))
        object.__setattr__(self, 'sd', finite(self.prior_sd * math.sqrt(vz)))
        object.__setattr__(self, '_mass_error', self._certify_moments())

    def logpdf(self, m):
        z = (m - self.prior_mean) / self.prior_sd
        q = (self.limit - self.offset - self.slope * z) / self.sigma
        return finite(normal_logpdf(m, self.prior_mean, self.prior_sd)
                      + float(log_ndtr(q)) - self.log_normalizer)

    def _pdf_standard(self, u):
        return math.exp(self.logpdf(self.mean + self.sd * u) + math.log(self.sd))

    def _certify_moments(self):
        mass, e0 = integrate(self._pdf_standard, -np.inf, np.inf, self.deadline)
        first, e1 = integrate(lambda u: u * self._pdf_standard(u), -np.inf, np.inf, self.deadline)
        second, e2 = integrate(lambda u: u * u * self._pdf_standard(u), -np.inf, np.inf, self.deadline)
        error = max(abs(mass - 1), abs(self.sd * first), abs(second - 1), e0, e1, e2)
        if error > TOL:
            raise ArithmeticError('selection_moment_reference_disagreement')
        return error

    def _tails(self, u):
        if u <= 0:
            f, error = integrate(self._pdf_standard, -np.inf, u, self.deadline)
            s = 1 - f
        else:
            s, error = integrate(self._pdf_standard, u, np.inf, self.deadline)
            f = 1 - s
        if not 0 <= f <= 1 or not 0 <= s <= 1 or error > TOL:
            raise ArithmeticError('selection_cdf_unknown')
        return f, s

    def cdf(self, m):
        return self._tails((m - self.mean) / self.sd)[0]

    def median(self):
        step = self.sd
        for _ in range(64):
            low, high = self.mean - step, self.mean + step
            if self.cdf(low) <= .5 <= self.cdf(high):
                return finite(brentq(lambda m: self.cdf(m) - .5, low, high, xtol=1e-10))
            step *= 2
        raise ArithmeticError('selection_quantile_not_bracketed')

    def score(self, truth):
        q = (truth - self.mean) / self.sd
        left, le = integrate(lambda u: self._tails(u)[0] ** 2, -np.inf, q, self.deadline)
        right, re = integrate(lambda u: self._tails(u)[1] ** 2, q, np.inf, self.deadline)
        crps = finite(self.sd * (left + right))
        # Independent expectation identity: E|X-y| - E[X(2F(X)-1)].
        abs_left, ae0 = integrate(lambda u: (q-u) * self._pdf_standard(u), -np.inf, q, self.deadline)
        abs_right, ae1 = integrate(lambda u: (u-q) * self._pdf_standard(u), q, np.inf, self.deadline)
        half_pair, pe = integrate(lambda u: u * (2*self._tails(u)[0]-1) * self._pdf_standard(u),
                                  -np.inf, np.inf, self.deadline)
        reference = self.sd * (abs_left + abs_right - half_pair)
        error = max(self._mass_error, abs(crps-reference), self.sd*(le+re+ae0+ae1+pe))
        if crps < 0 or error > TOL:
            raise ArithmeticError('selection_crps_reference_disagreement')
        return {'mean': self.mean, 'median': self.median(), 'nll': finite(-self.logpdf(truth)),
                'crps': crps, 'numerical_error': finite(error)}


def posterior(parameters, prior, scaler, feature, deadline):
    a, b, c, sigma = parameters
    xu = 0.0 if scaler['age_sd'] == 0 else (math.log10(feature['u'])-scaler['age_mean'])/scaler['age_sd']
    offset = a + c*xu
    if feature['censored']:
        return CensoredPosterior(prior['mean'], prior['sd'], offset, b, sigma, feature['L'], deadline)
    v = sigma*sigma+b*b
    mz = b*(feature['y']-offset)/v
    mean = prior['mean']+prior['sd']*mz
    sd = prior['sd']*sigma/math.sqrt(v)
    result = NormalPosterior(finite(mean), finite(sd), deadline)
    marginal = normal_logpdf(feature['y'], offset, math.sqrt(v))
    # A separate Bayes-density algebra verifies the analytic posterior before acceptance.
    lp = normal_logpdf(prior['mean'], prior['mean'], prior['sd'])
    ll = normal_logpdf(feature['y'], offset, sigma)
    if abs(result.logpdf(prior['mean'])-(lp+ll-marginal)) > TOL:
        raise ArithmeticError('normal_posterior_identity_disagreement')
    return result

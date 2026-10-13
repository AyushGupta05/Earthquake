"""Test-only independent direct normal-equation oracle; no production imports."""
from decimal import Decimal, localcontext
import math
import numpy as np


def D(x):
    return Decimal.from_float(float(x))


def posterior(prior, marks, coeff, nu, mref):
    # Direct precision/information/square completion (not recursive Kalman updates).
    with localcontext() as ctx:
        ctx.prec = 80
        factors = []
        for j, row in enumerate(marks):
            t = D(math.log1p(.25 * j))
            for c in range(3):
                a, b, d, e, rho, raw = (D(v) for v in coeff[c])
                previous = D(0) if j == 0 else D(marks[j - 1, c])
                beta = b + e * t
                intercept = a + d * t + rho * previous - beta * D(mref)
                sigma = D(.05) + (raw if raw > 20 else (1 + raw.exp()).ln())
                loading = D(1) if j == 0 else 1 - rho
                factors.append((c, D(row[c]), intercept, beta, sigma, loading))
        masses = []; means = []; scales = []
        for noise in nu:
            for k in range(5):
                mu, sd = D(prior[1][k]), D(prior[2][k])
                precision = 1 / (sd * sd)
                information = mu / (sd * sd)
                square = mu * mu / (sd * sd)
                logscale = sd.ln()
                for c, y, intercept, beta, sigma, loading in factors:
                    residual = y - intercept - loading * D(noise[c])
                    precision += (beta / sigma) ** 2
                    information += beta * residual / (sigma * sigma)
                    square += (residual / sigma) ** 2
                    logscale += sigma.ln()
                means.append(information / precision); scales.append((1 / precision).sqrt())
                masses.append(D(prior[0][k]) - Decimal(12).ln() - logscale
                              - Decimal(len(factors)) / 2 * D(2 * math.pi).ln()
                              - precision.ln() / 2 - (square - information * information / precision) / 2)
        maximum = max(masses); logz = maximum + sum((m - maximum).exp() for m in masses).ln()
        return tuple(np.asarray([float(v) for v in values]) for values in (masses, means, scales)), float(logz)


def nll(components, logz, target):
    masses, means, scales = components
    with localcontext() as ctx:
        ctx.prec = 80
        terms = [D(w) - D(logz) - D(s).ln() - D(2 * math.pi).ln() / 2
                 - ((D(target) - D(m)) / D(s)) ** 2 / 2 for w, m, s in zip(masses, means, scales)]
        maximum = max(terms)
        return float(-maximum - sum((v - maximum).exp() for v in terms).ln())

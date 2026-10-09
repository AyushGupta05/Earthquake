"""Stdlib equation checks, not an earthquake experiment or learned-model result."""
import json
import math
import random
import statistics
import unittest
from pathlib import Path


def normal_pdf(x, mean, scale):
    return math.exp(-0.5 * ((x - mean) / scale) ** 2) / (scale * math.sqrt(2 * math.pi))


def normal_cdf(x, mean, scale):
    return 0.5 * math.erfc(-(x - mean) / (scale * math.sqrt(2)))


def censored_likelihood(growth, mean, scale):
    if growth < 0:
        return 0.0
    return normal_cdf(0, mean, scale) if growth == 0 else normal_pdf(growth, mean, scale)


def update(prior, low_likelihood, high_likelihood):
    return prior * high_likelihood / ((1 - prior) * low_likelihood + prior * high_likelihood)


def risk_summary(rows):
    errors = [abs(2 + 3 * p - (2 + 3 * y)) for y, p in rows]
    tail = [e for e, (y, _) in zip(errors, rows) if y]
    return {
        "mean_decision_mae": statistics.mean(errors),
        "tail_mean_decision_mae": statistics.mean(tail),
        "median_absolute_error_of_mean_decision": statistics.median(errors),
        "brier": statistics.mean((p - y) ** 2 for y, p in rows),
        "nll": statistics.mean(-math.log(max(1e-15, p if y else 1 - p)) for y, p in rows),
    }


def checks_and_demo():
    # Fixed, deliberately favorable oracle toy. No parameters fitted and no data selected.
    seed, count, prior = 20261009, 100000, 0.05
    rng = random.Random(seed)
    rows = {"prior_only": [], "correct_censoring": [], "density_at_zero_wrong": []}
    zeros = 0
    for _ in range(count):
        y = int(rng.random() < prior)
        g = max(0.0, rng.gauss((-0.7, 0.8)[y], 0.6))
        zeros += int(g == 0)
        correct = update(prior, censored_likelihood(g, -0.7, 0.6), censored_likelihood(g, 0.8, 0.6))
        wrong = update(prior, normal_pdf(g, -0.7, 0.6), normal_pdf(g, 0.8, 0.6))
        for arm, p in (("prior_only", prior), ("correct_censoring", correct), ("density_at_zero_wrong", wrong)):
            rows[arm].append((y, p))
    prior_variance, shared_variance, independent_variance, n = 4.0, 1.0, 0.04, 3
    return {
        "scope": "Oracle synthetic equation check only; no training, no earthquake data, no empirical novelty claim.",
        "design": {"seed": seed, "n": count, "tail_prevalence": prior, "class_growth_normal_means": [-0.7, 0.8], "scale": 0.6},
        "observed_zero_fraction": zeros / count,
        "zero_growth_posterior": {
            "correct": update(prior, normal_cdf(0, -0.7, 0.6), normal_cdf(0, 0.8, 0.6)),
            "incorrect_density_at_zero": update(prior, normal_pdf(0, -0.7, 0.6), normal_pdf(0, 0.8, 0.6)),
        },
        "same_observation_reused": {"prior": prior, "first_posterior": 0.2, "correct_unchanged": 0.2, "wrong_reused_likelihood": update(0.2, 1, 4.75)},
        "shared_nuisance_posterior_variance": {
            "exact": 1 / (1 / prior_variance + n / (independent_variance + n * shared_variance)),
            "wrong_independent_marginals": 1 / (1 / prior_variance + n / (independent_variance + shared_variance)),
        },
        "arms": {arm: risk_summary(values) for arm, values in rows.items()},
    }


class EquationTests(unittest.TestCase):
    def test_atom_plus_continuous_mass(self):
        # Numerical midpoint integral is independent of the CDF expression for the atom.
        for mean in (-1.5, -0.2, 0.0, 0.8, 2.0):
            scale, step = 0.6, 0.0001
            mass = normal_cdf(0, mean, scale) + step * sum(normal_pdf((i + 0.5) * step, mean, scale) for i in range(100000))
            self.assertAlmostEqual(mass, 1, places=7)

    def test_digital_gain_symmetry(self):
        prefix, new_block, baseline, sensitivity = [2, -5, 3], [8, -2], 1.5, 27.0
        def observed(c):
            a = max(abs(c * v - c * baseline) / (c * sensitivity) for v in prefix)
            b = max(abs(c * v - c * baseline) / (c * sensitivity) for v in new_block)
            return a, max(0.0, math.log10(b / a))
        for c in (0.001, 1, 10, 1000):
            for expected, actual in zip(observed(1), observed(c)):
                self.assertAlmostEqual(expected, actual, places=13)

    def test_zero_increment_is_not_zero_information(self):
        self.assertLess(update(0.05, normal_cdf(0, -0.7, 0.6), normal_cdf(0, 0.8, 0.6)), 0.01)

    def test_equal_likelihood_leaves_posterior(self):
        for prior in (0.01, 0.2, 0.9):
            self.assertAlmostEqual(update(prior, 0.4, 0.4), prior)

    def test_persistent_latent_must_not_reset(self):
        # Y,U independent priors; P(B=1|Y,U). Two observed successes share U.
        q = ((0.1, 0.4), (0.4, 0.8))
        prior = 0.05
        joint = {(y, u): (prior if y else 1 - prior) * 0.5 for y in (0, 1) for u in (0, 1)}
        for _ in range(2):
            joint = {(y, u): w * q[y][u] for (y, u), w in joint.items()}
            z = sum(joint.values())
            joint = {key: value / z for key, value in joint.items()}
        exact = sum(w for (y, _), w in joint.items() if y)
        batch = update(prior, sum(v * v for v in q[0]) / 2, sum(v * v for v in q[1]) / 2)
        reset = update(prior, (sum(q[0]) / 2) ** 2, (sum(q[1]) / 2) ** 2)
        self.assertAlmostEqual(exact, batch)
        self.assertGreater(abs(exact - reset), 0.02)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EquationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    output = Path(__file__).with_name("record_innovation_checks.json")
    output.write_text(json.dumps(checks_and_demo(), indent=2) + "\n")
    print(output)

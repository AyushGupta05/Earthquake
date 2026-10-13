"""Invented arrays only; no files containing scientific inputs, Torch or models."""
import ast
import copy
import math
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from scipy.special import logsumexp
import ar_core as a
import proper_core as p
import decimal_fixture as decimal


def fixture(h=1, offset=0):
    logits = np.array([.1, -.3, .2, .4, 0.])
    prior = [logits - logsumexp(logits), np.array([2., 2.5, 3., 3.5, 4.]), np.array([.6, .8, .9, 1., 1.2])]
    coeff = np.array([[.3, .4, .06, .02, -.3, .4], [.4, .5, -.03, .01, 1., .5], [.2, .6, .04, -.01, .6, .2]])
    count = (h * 1000000000 - offset) // 250000000
    marks = np.array([[.7 + .02*j, .6 + .03*j, 1. + .01*j] for j in range(count)])
    z = np.linspace(-.3, .3, 12)
    nu = np.column_stack((z, -.4*z, .8*z))
    return prior, marks, coeff, nu, 3., h, offset


def reconstructed(args):
    budget = a.Budget()
    ref = a.build_reference(*args, budget=budget)
    return ref, a.complete(ref, budget)


def source(ref, mix):
    return dict(reference=copy.deepcopy(ref), log_weights=mix.logw.copy(), means=mix.mu.copy(),
                scales=mix.sd.copy(), log_normalizer=mix.logz, noise_probabilities=mix.noise.copy())


class Math(unittest.TestCase):
    def test_decimal_direct_completion_at_all_deadlines(self):
        for h in (1, 3, 5):
            with self.subTest(h=h):
                args = fixture(h); ref, mix = reconstructed(args)
                (mass, mean, scale), logz = decimal.posterior(*args[:5])
                np.testing.assert_allclose(mix.logw, mass-logz, rtol=0, atol=3e-12)
                np.testing.assert_allclose(mix.mu, mean, rtol=0, atol=2e-13)
                np.testing.assert_allclose(mix.sd, scale, rtol=0, atol=2e-13)
                self.assertAlmostEqual(mix.logz, logz, places=11)
                self.assertEqual(ref['count'], 4*h)

    def test_rho_zero_fixed_parameter_S_identity(self):
        args = list(fixture(3)); args[2][:, 4] = 0
        _, mix = reconstructed(args)
        old = p.complete(args[0], p.factors(args[1], args[2], args[4]), args[3], 'S', p.Budget())
        for x, y in ((mix.logw, old.logw), (mix.mu, old.mu), (mix.sd, old.sd)):
            np.testing.assert_array_equal(x, y)
        self.assertEqual(mix.logz, old.logz)

    def test_zero_nuisance_P_marginal_identity(self):
        args = list(fixture()); args[3][:] = 0
        _, mix = reconstructed(args)
        old = p.complete(args[0], p.factors(args[1], args[2], args[4]), args[3], 'P', p.Budget())
        np.testing.assert_allclose(mix.mu.reshape(12, 5), np.tile(old.mu, (12, 1)), rtol=0, atol=1e-13)
        for x in (0., 2., 4., 7.): self.assertAlmostEqual(mix.cdf(x), old.cdf(x), places=13)
        self.assertAlmostEqual(mix.nll(2.5), old.nll(2.5), places=12)

    def test_first_cell_S_identity(self):
        args = fixture(1, 750000000); ref, mix = reconstructed(args)
        self.assertEqual(ref['count'], 1)
        old = p.complete(args[0], p.factors(args[1], args[2], args[4]), args[3], 'S', p.Budget())
        np.testing.assert_array_equal(mix.logw, old.logw)
        np.testing.assert_array_equal(mix.mu, old.mu)

    def test_rho_one_and_negative_loading(self):
        args = list(fixture()); args[2][:, 4] = [1., -2., 1.5]
        ref, _ = reconstructed(args)
        np.testing.assert_array_equal(ref['facts'][0]['loading'], np.ones(3))
        for f in ref['facts'][1:]: np.testing.assert_array_equal(f['loading'], [0., 3., -.5])

    def test_level_translation_with_joint_reference_translation(self):
        args = list(fixture(3)); _, old = reconstructed(args)
        shift = np.array([.2, -.1, .3]); args[1] += shift; args[3] += shift
        _, new = reconstructed(args)
        np.testing.assert_allclose(old.logw, new.logw, rtol=0, atol=2e-13)
        np.testing.assert_allclose(old.mu, new.mu, rtol=0, atol=2e-13)
        self.assertAlmostEqual(old.logz, new.logz, places=12)

    def test_later_rho_derivative_is_previous_minus_support(self):
        args = fixture(); eps = 1e-6
        for component in range(3):
            plus = copy.deepcopy(args); minus = copy.deepcopy(args)
            plus[2][component, 4] += eps; minus[2][component, 4] -= eps
            rp, _ = reconstructed(plus); rm, _ = reconstructed(minus)
            for j in range(4):
                fp, fm = rp['facts'][j], rm['facts'][j]; noise = args[3][7, component]
                derivative = ((fp['intercept'][component] + fp['loading'][component]*noise)
                              - (fm['intercept'][component] + fm['loading'][component]*noise))/(2*eps)
                expected = 0. if j == 0 else args[1][j-1, component] - noise
                self.assertAlmostEqual(derivative, expected, places=8)

    def test_conditional_NLL_rho_derivative_matches_decimal(self):
        args = fixture(); eps = 2e-5
        plus, minus = copy.deepcopy(args), copy.deepcopy(args)
        plus[2][0, 4] += eps; minus[2][0, 4] -= eps
        _, mp = reconstructed(plus); _, mm = reconstructed(minus)
        pp, zp = decimal.posterior(*plus[:5]); pm, zm = decimal.posterior(*minus[:5])
        derivative = (mp.nll(2.7)-mm.nll(2.7))/(2*eps)
        expected = (decimal.nll(pp, zp, 2.7)-decimal.nll(pm, zm, 2.7))/(2*eps)
        self.assertAlmostEqual(derivative, expected, places=7)

    def test_uninformative_amplitude_leaves_marginal_prior(self):
        args = list(fixture()); args[2][:, [1, 3]] = 0
        _, mix = reconstructed(args); old = p.Mixture(*args[0])
        for x in (0., 2., 4., 7.): self.assertAlmostEqual(mix.cdf(x), old.cdf(x), places=13)
        self.assertAlmostEqual(mix.nll(3.), old.nll(3.), places=12)

    def test_noise_major_joint_order_and_posterior_noise(self):
        ref, mix = reconstructed(fixture())
        self.assertEqual(len(mix.mu), 60)
        np.testing.assert_array_equal(mix.noise, np.exp(mix.logw).reshape(12, 5).sum(1))
        self.assertAlmostEqual(float(mix.noise.sum()), 1., places=13)
        self.assertLess(abs(float(logsumexp(mix.logw))), 1e-12)

    def test_future_suffix_does_not_change_copied_reference(self):
        args = list(fixture(5)); short = list(args); short[1] = args[1][:4]; short[5] = 1
        ref, old = reconstructed(short); args[1][4:] = 99.
        new = a.complete(ref, a.Budget())
        np.testing.assert_array_equal(old.logw, new.logw)
        # Immutable copied prefix evidence does not alias caller arrays.
        short[1][:] = 22.
        np.testing.assert_array_equal(ref['facts'][0]['value'], [.7, .6, 1.])

    def test_proper_scores_quantiles_integral_and_coverage(self):
        _, mix = reconstructed(fixture()); score = mix.scores(2.7)
        self.assertGreaterEqual(score['crps'], 0.)
        self.assertLessEqual(abs(score['crps']-mix.integral_crps(2.7)), 1e-6)
        for q in p.Q:
            self.assertLessEqual(abs(mix.cdf(score['quantiles'][str(q)])-q), 1e-6)
        self.assertEqual(score['median'], score['quantiles']['0.5'])
        for level, low, high in [(50, '.25', '.75'), (80, '.1', '.9'), (95, '.025', '.975')]:
            self.assertIs(type(score['coverage_'+str(level)]), bool)
            self.assertEqual(score['coverage_'+str(level)], score['quantiles'][str(float(low))] <= 2.7 <= score['quantiles'][str(float(high))])

    def test_valid_source_and_nonzero_prior_bounds(self):
        args = fixture(); ref, mix = reconstructed(args); value = source(ref, mix)
        result = a.verify_source(value, *args, [np.zeros(5) for _ in range(3)], budget=a.Budget())
        np.testing.assert_array_equal(result.logw, mix.logw)
        value['reference']['prior'][1][0] += 1e-14
        a.verify_source(value, *args, [np.full(5, 1e-13) for _ in range(3)], budget=a.Budget())

    def test_explicit_source_metadata_and_clock_mismatches(self):
        args = fixture(); ref, mix = reconstructed(args)
        for key, changed in [('arm', 'S'), ('count', 3), ('horizon', 3), ('arrival_offset_ns', 1), ('mref', 3.1)]:
            with self.subTest(key=key):
                value = source(ref, mix); value['reference'][key] = changed
                with self.assertRaises(a.AuditFailure):
                    a.verify_source(value, *args, [np.zeros(5) for _ in range(3)], budget=a.Budget())

    def test_source_coefficient_nuisance_rho_last_and_prior_mismatches(self):
        args = fixture(); ref, mix = reconstructed(args)
        for key in ('coefficients', 'rho', 'nu', 'last_observed', 'prior'):
            with self.subTest(key=key):
                value = source(ref, mix)
                target = value['reference']['prior'][1] if key == 'prior' else value['reference'][key]
                target.flat[0] += .1
                with self.assertRaises(a.AuditFailure):
                    a.verify_source(value, *args, [np.zeros(5) for _ in range(3)], budget=a.Budget())

    def test_fact_chronology_loading_previous_and_value_mismatches(self):
        args = fixture(); ref, mix = reconstructed(args)
        for key in a.FACT_KEYS:
            with self.subTest(key=key):
                value = source(ref, mix); f = value['reference']['facts'][1]
                if key == 'cell': f[key] = 2
                else: f[key][0] += .1
                with self.assertRaises(a.AuditFailure):
                    a.verify_source(value, *args, [np.zeros(5) for _ in range(3)], budget=a.Budget())

    def test_mixture_outputs_cannot_be_swapped_or_omitted(self):
        args = fixture(); ref, mix = reconstructed(args)
        for key in a.SOURCE_KEYS - {'reference'}:
            with self.subTest(key=key):
                value = source(ref, mix)
                if key == 'log_normalizer': value[key] += .01
                else: value[key].flat[0] += .01
                with self.assertRaises(a.AuditFailure):
                    a.verify_source(value, *args, [np.zeros(5) for _ in range(3)], budget=a.Budget())
        value = source(ref, mix); del value['noise_probabilities']
        with self.assertRaises(a.AuditFailure): a.verify_source(value, *args, [np.zeros(5) for _ in range(3)], budget=a.Budget())

    def test_standalone_completion_rederives_loading(self):
        ref, _ = reconstructed(fixture()); ref['facts'][1]['loading'][0] = 1.
        with self.assertRaises(a.AuditFailure): a.complete(ref, a.Budget())

    def test_invalid_dtype_floor_shape_clock_and_domains(self):
        for which in ('dtype', 'floor', 'count', 'rho', 'nu', 'prior', 'clock', 'mref'):
            with self.subTest(which=which):
                args = list(fixture())
                if which == 'dtype': args[1] = args[1].astype(np.float32)
                elif which == 'floor': args[1][0, 0] = -12.
                elif which == 'count': args[1] = args[1][:-1].copy()
                elif which == 'rho': args[2][0, 4] = 1000001.
                elif which == 'nu': args[3][0, 0] = math.inf
                elif which == 'prior': args[0][0][0] += .1
                elif which == 'clock': args[5] = True
                elif which == 'mref': args[4] = math.nan
                with self.assertRaises(a.AuditFailure): reconstructed(args)

    def test_loading_near_zero_bounds_and_source_rejection(self):
        args = list(fixture()); args[2][0, 4] = np.nextafter(1., 2.)
        ref, mix = reconstructed(args); self.assertLess(ref['facts'][1]['loading'][0], 0)
        bounds = a.factor_bounds(ref); self.assertGreater(bounds[1]['loading'][0], 0)
        value = source(ref, mix); value['reference']['facts'][1]['loading'][0] = .0001
        with self.assertRaises(a.AuditFailure): a.verify_source(value, *args, [np.zeros(5) for _ in range(3)], budget=a.Budget())

    def test_bad_representation_rejected_not_rounded(self):
        args = list(fixture()); args[1][:] = 100000.
        with self.assertRaisesRegex(a.AuditFailure, 'representation'): reconstructed(args)

    def test_unresolved_prior_bound_rejected(self):
        args = fixture(); ref, mix = reconstructed(args)
        with self.assertRaisesRegex(a.AuditFailure, 'bound_unresolved'):
            a.verify_source(source(ref, mix), *args, [np.ones(5) for _ in range(3)], budget=a.Budget())

    def test_clock_and_point_budget_preserved(self):
        with patch.object(p.time, 'monotonic', return_value=11.):
            with self.assertRaisesRegex(a.AuditFailure, 'deadline'): a.Budget(0.)
        ref, _ = reconstructed(fixture()); budget = a.Budget(); budget.points = 1000000
        mix = a.complete(ref, budget)
        with self.assertRaisesRegex(a.AuditFailure, 'work_cap'): mix.cdf(2.)

    def test_duck_budget_shared_without_restarting_clock(self):
        class Shared:
            def __init__(self): self.inner = p.Budget()
            def tick(self): self.inner.tick()
            def charge(self, points, terms): self.inner.charge(points, terms)
        budget = Shared(); args = fixture()
        ref = a.build_reference(*args, budget=budget); mix = a.complete(ref, budget)
        self.assertIs(mix.budget, budget)
        mix.cdf(2.); self.assertEqual(budget.inner.points, 1)
        self.assertGreater(budget.inner.terms, 0)
        with patch.object(p.time, 'monotonic', return_value=budget.inner.begin + 10.01):
            with self.assertRaisesRegex(a.AuditFailure, 'deadline'): mix.scores(2.)

    def test_nll_representation_failure_preserves_numeric_evidence(self):
        _, mix = reconstructed(fixture()); evidence = {}
        with self.assertRaisesRegex(a.AuditFailure, 'nll_representation'):
            mix.scores(100000., evidence=evidence)
        self.assertIn('rejected_nll', evidence)
        self.assertEqual(set(evidence['rejected_nll']), {'candidate_float64_hex', 'bound_float64_hex', 'ulp_float64_hex'})

    def test_no_normalization_rescue(self):
        prior = fixture()[0]
        with self.assertRaisesRegex(a.AuditFailure, 'normalization'):
            a.Mixture(prior[0] + .001, prior[1], prior[2])

    def test_softplus_threshold_and_bound_branch(self):
        raw = np.array([19., 20., 21.]); result = p.softplus(raw)
        self.assertEqual(result[-1], 21.)
        with self.assertRaisesRegex(a.AuditFailure, 'branch_ambiguous'):
            p.softplus(np.array([20.]), np.array([1e-13]))

    def test_no_producer_kernel_or_torch_imports(self):
        for name in ('ar_core.py', 'proper_core.py', 'decimal_fixture.py'):
            tree = ast.parse(Path(__file__).with_name(name).read_text())
            imported = []
            for n in ast.walk(tree):
                if isinstance(n, ast.Import): imported.extend(v.name for v in n.names)
                elif isinstance(n, ast.ImportFrom): imported.append(n.module or '')
            self.assertFalse(any(any(part in name for part in ('torch', 'kernel', 'operator', 'processor')) for name in imported))


if __name__ == '__main__': unittest.main()

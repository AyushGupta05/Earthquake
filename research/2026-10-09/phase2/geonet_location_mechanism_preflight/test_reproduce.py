"""Focused scientific identities and safe reproduction ownership, invented data only."""

import ast
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from scipy.integrate import quad
from scipy.stats import multivariate_normal

import reproduce


class MathematicalIdentities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.math = reproduce.load_math()

    def test_linear_mean_equals_matched_ElogR_with_correlated_noise(self):
        conditional = self.math["conditional"]
        a = np.array([[2.8, 2.7, 2.6], [3.0, 2.9, 2.8]])
        lr = np.broadcast_to(self.math["LR"][None, :, :], (2, 2, 3))
        weights = np.array([[0.2, 0.8], [0.9, 0.1]])
        cov = 0.25**2 * np.eye(3) + 0.15**2 * np.ones((3, 3))
        kwargs = {"mu": np.array([4.5]), "v": np.array([0.8**2]), "pw": np.array([1.0])}
        mixture = conditional(a, lr, cov, np.log(weights), arrival_only=True, **kwargs)
        expected_lr = np.sum(lr * weights[:, :, None], axis=1)
        point = conditional(a, expected_lr[:, None, :], cov, np.zeros((2, 1)), **kwargs)
        np.testing.assert_allclose(np.sum(mixture[0] * mixture[2], axis=1), point[0][:, 0], atol=1e-14, rtol=0)

    def test_shared_source_covariance_has_rank_one_and_no_fake_states(self):
        logs = self.math["LR"]
        centered = logs - np.mean(logs, axis=0)
        covariance = np.einsum("gi,gj->ij", centered, centered) / 2
        expected = np.outer(logs[1] - logs[0], logs[1] - logs[0]) / 4
        np.testing.assert_allclose(covariance, expected, atol=1e-15, rtol=0)
        self.assertEqual(np.linalg.matrix_rank(covariance, tol=1e-12), 1)
        self.assertGreater(covariance.sum() / 9, np.trace(covariance) / 9)
        combinations = [logs[[(bits >> i) & 1 for i in range(3)], np.arange(3)] for bits in range(8)]
        coherent = sum(any(np.array_equal(row, source) for source in logs) for row in combinations)
        self.assertEqual(coherent, 2)

    def test_one_report_timing_returns_prior_without_using_time(self):
        fn = self.math["timing_logweights"]
        a = fn(np.array([[1000.0, -999.0]]), 1, 0.02, 0.04)
        b = fn(np.array([[-1000.0, 999.0]]), 1, 0.02, 0.04)
        np.testing.assert_array_equal(a, b)
        np.testing.assert_allclose(np.exp(a), [[0.98, 0.02]], atol=1e-16, rtol=0)

    def test_joint_amplitude_weights_match_independent_scalar_quadrature(self):
        conditional = self.math["conditional"]
        a = np.array([[2.8]])
        logs = self.math["LR"][:, :1]
        cov = np.array([[0.35**2 + 0.15**2]])
        q = np.array([0.5, 0.5])
        joint = conditional(a, logs[None, :, :], cov, np.log(q)[None, :])
        arrival = conditional(a, logs[None, :, :], cov, np.log(q)[None, :], arrival_only=True)
        self.assertAlmostEqual(joint[2].sum(), 1.0, places=13)
        self.assertTrue(np.all(joint[1] > 0))
        self.assertGreater(abs(np.sum(joint[0] * joint[2]) - np.sum(arrival[0] * arrival[2])), 0.5)
        mu, v, pw = self.math["MU"], self.math["V"], self.math["PW"]

        def raw(m):
            prior = np.sum(pw * np.exp(-(m - mu)**2 / (2 * v)) / np.sqrt(2 * np.pi * v))
            likelihood = sum(q[g] * multivariate_normal.pdf(a[0], mean=[m - 2 * logs[g, 0]], cov=cov) for g in range(2))
            return prior * likelihood

        evidence = quad(raw, -10, 20, points=[3.7, 6.8], epsabs=1e-12, epsrel=1e-11)[0]
        mean = quad(lambda m: m * raw(m), -10, 20, points=[3.7, 6.8], epsabs=1e-12, epsrel=1e-11)[0] / evidence
        self.assertAlmostEqual(mean, np.sum(joint[0] * joint[2]), places=11)

    def test_CRPS_single_normal_known_value_and_split_component_identity(self):
        summarize = self.math["summarize"]
        truth = np.array([6.5])
        one = (np.array([[6.5]]), np.array([[0.09]]), np.ones((1, 1)), np.zeros((1, 1)))
        split = (np.array([[6.5, 6.5]]), np.array([[0.09, 0.09]]), np.array([[0.5, 0.5]]), np.log([[0.5, 0.5]]))
        result, _ = summarize(one, truth)
        second, _ = summarize(split, truth)
        self.assertAlmostEqual(result["CRPS"], 0.3 * (np.sqrt(2 / np.pi) - 1 / np.sqrt(np.pi)), places=14)
        self.assertAlmostEqual(result["CRPS"], second["CRPS"], places=14)
        self.assertAlmostEqual(result["NLL"], second["NLL"], places=14)

    def test_moment_matching_preserves_mean_decisions_not_density(self):
        summarize = self.math["summarize"]
        mixture = (np.array([[5.0, 7.0], [6.0, 8.0]]), np.full((2, 2), 0.09), np.full((2, 2), 0.5), np.log(np.full((2, 2), 0.5)))
        mean = np.sum(mixture[0] * mixture[2], axis=1)
        variance = np.sum((mixture[1] + mixture[0]**2) * mixture[2], axis=1) - mean**2
        gaussian = (mean[:, None], variance[:, None], np.ones((2, 1)), np.zeros((2, 1)))
        a, pred_a = summarize(mixture, np.array([6.0, 7.0]))
        b, pred_b = summarize(gaussian, np.array([6.0, 7.0]))
        np.testing.assert_array_equal(pred_a, pred_b)
        self.assertEqual(a["mean_decision"], b["mean_decision"])
        self.assertNotAlmostEqual(a["NLL"], b["NLL"], places=3)


class ReproductionOwnership(unittest.TestCase):
    def fixture(self, tmp):
        base = Path(tmp) / "fixture"
        base.mkdir()
        for name in reproduce.PINNED_NAMES | {"reproduction_input_pins.json"}:
            shutil.copyfile(reproduce.BASE / name, base / name)
        return base

    def test_root_redirection_changes_only_one_AST_value(self):
        text = (reproduce.BASE / reproduce.CELLS[0][0]).read_text()
        original = ast.parse(text)
        modified = reproduce.redirected_tree(text, "ROOT", Path("/private/tmp/invented-output"))
        roots = [i for i, node in enumerate(original.body) if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "ROOT"]
        self.assertEqual(len(roots), 1)
        original.body[roots[0]].value = modified.body[roots[0]].value
        self.assertEqual(ast.dump(original), ast.dump(modified))
        with self.assertRaises(ValueError):
            reproduce.redirected_tree("ROOT=1\nROOT=2\n", "ROOT", Path("ignored"))

    def test_path_names_cannot_escape_or_reuse_original_directory(self):
        for name in ("../original", "/private/tmp/escape", "x/y", "", "."):
            with self.assertRaises(ValueError):
                reproduce.run_reproduction(reproduce.BASE, name)

    def test_changed_inert_source_rejected_before_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.fixture(tmp)
            with (base / reproduce.CELLS[0][0]).open("a") as stream:
                stream.write("\n# changed\n")
            with self.assertRaises(ValueError):
                reproduce.run_reproduction(base, "attempt")
            self.assertFalse((base / "local_runs").exists())

    def test_existing_output_or_symlink_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.fixture(tmp)
            runs = base / "local_runs"
            runs.mkdir()
            (runs / "existing").mkdir()
            sentinel = runs / "existing" / "sentinel"
            sentinel.write_text("unchanged")
            with self.assertRaises(FileExistsError):
                reproduce.run_reproduction(base, "existing")
            self.assertEqual(sentinel.read_text(), "unchanged")
            (runs / "symlink").symlink_to(base, target_is_directory=True)
            with self.assertRaises(FileExistsError):
                reproduce.run_reproduction(base, "symlink")

    def test_symlinked_run_root_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.fixture(tmp)
            (base / "local_runs").symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaises(ValueError):
                reproduce.run_reproduction(base, "attempt")

    def test_only_declared_metadata_can_be_excluded_from_comparison(self):
        original = {"runtime": {"python": "old"}, "results": [{"error": 1.0}]}
        replay = copy.deepcopy(original)
        replay["runtime"]["python"] = "new"
        self.assertIsNone(reproduce.first_difference(reproduce.semantic_value("CALCULATIONS.json", original), reproduce.semantic_value("CALCULATIONS.json", replay)))
        replay["results"][0]["error"] += 1e-14
        self.assertIsNotNone(reproduce.first_difference(reproduce.semantic_value("CALCULATIONS.json", original), reproduce.semantic_value("CALCULATIONS.json", replay)))
        a = {"checked_calculations_sha256": "a", "warnings": ["x"]}
        b = {"checked_calculations_sha256": "b", "warnings": ["y"]}
        self.assertIsNotNone(reproduce.first_difference(reproduce.semantic_value("WARNING_CHECK.json", a), reproduce.semantic_value("WARNING_CHECK.json", b)))


if __name__ == "__main__":
    unittest.main()

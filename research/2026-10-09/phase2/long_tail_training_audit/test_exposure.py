"""Synthetic tests only. No data files, AWS calls, downloads or GPU execution."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch
from torch import nn

import exposure_training as training
import exposure_metrics as metrics

torch.set_num_threads(1)


def identifier(salt, held, index):
    for j in range(index * 100, index * 100 + 100):
        value = f"fixture-{j}"
        if (training.bucket(salt, value) < 2) == held:
            return value
    raise AssertionError("Fixture ID search exhausted")


def population(seconds=1, n=30, subset="fit", row_start=0):
    held = subset != "fit"
    events = [identifier("polarization-event-v1", held, i % 6) for i in range(n)]
    station = identifier("polarization-station-v1", subset == "eval_held", 0)
    return training.PrefixPopulation(seconds, subset, np.arange(row_start, row_start + n), events,
                                     [station] * n, np.arange(n) % 6 + .5, 1 + np.arange(n) % 4)


def plans(sizes=(18, 24, 30)):
    return {t: training.make_plan(population(t, n)) for t, n in zip(training.HORIZONS, sizes)}


class ToyEncoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Linear(3, 7)
        self.head = nn.Linear(8, 66)

    def forward_prefix(self, inputs, seconds):
        hidden = torch.tanh(self.encoder(inputs["counts"].mean(-1)))
        duration = torch.full((len(hidden), 1), seconds / 5., device=hidden.device)
        return self.head(torch.cat([hidden, duration], 1))


def loader(seconds, rows):
    values = torch.tensor(rows % 6, dtype=torch.float32)[:, None, None]
    counts = values.expand(len(rows), 3, 100 * seconds).clone() / 5
    return training.LoadedPrefix(rows.copy(), {"counts": counts, "sensitivity": torch.ones(len(rows), 3),
        "static": torch.zeros(len(rows), 34), "response": torch.zeros(len(rows), 72)})


def identity(p):
    digest = training.population_digest(p)
    return {"export_sha256": "a" * 64, "backbone_sha256": "b" * 64,
            "normalizers_sha256": "c" * 64, "population_sha256": digest,
            "normalizer_fit_population_sha256": digest, "scope": "synthetic fixture only"}


class ExposureMathTest(unittest.TestCase):
    def test_exact_label_and_band_boundaries(self):
        labels, support = training.labels_and_support([0, .999, 1, 3.999, 4, 4.999, 5, 6.55, 6.6, -.1])
        np.testing.assert_array_equal(labels, [0, 9, 10, 39, 40, 49, 50, 65, -1, -1])
        np.testing.assert_array_equal(np.minimum(labels[:8] // 10, 5), [0, 0, 1, 3, 4, 4, 5, 5])
        self.assertEqual(support.sum(), 8)
        with self.assertRaises(ValueError):
            training.labels_and_support([np.nan])

    def test_population_checks_fresh_splits_and_unique_ids(self):
        p = population()
        with self.assertRaises(ValueError):
            training.PrefixPopulation(1, "fit", p.source_rows, p.events,
                [identifier("polarization-station-v1", True, 0)] * len(p.targets), p.targets, p.weights)
        with self.assertRaises(ValueError):
            training.PrefixPopulation(1, "fit", np.zeros(len(p.targets), dtype=int), p.events, p.stations, p.targets, p.weights)
        with self.assertRaises(ValueError):
            training.PrefixPopulation(1, "fit", p.source_rows, p.events, p.stations, p.targets, np.zeros(len(p.targets)))
        with self.assertRaises(ValueError):
            p.weights[0] = 999

    def test_six_band_weighted_sampler_and_empty_fine_bins(self):
        p = population()
        plan = training.make_plan(p)
        expected = np.array([p.weights[(np.arange(len(p.targets)) % 6) == i].sum() for i in range(6)])
        np.testing.assert_array_equal(plan.band_counts, expected)
        np.testing.assert_allclose(plan.natural_probability, p.weights / p.weights.sum())
        expected_q = p.weights / np.sqrt(expected[np.arange(len(p.targets)) % 6])
        np.testing.assert_allclose(plan.exposure_probability, expected_q / expected_q.sum())
        group_mass = np.bincount(np.minimum(plan.labels // 10, 5), weights=plan.exposure_probability, minlength=6)
        np.testing.assert_allclose(group_mass, np.sqrt(expected) / np.sqrt(expected).sum())
        self.assertEqual((plan.fine_counts == 0).sum(), 60)
        self.assertTrue(np.isfinite(plan.log_adjustment).all())
        self.assertEqual(len(plan.log_adjustment), 66)

    def test_missing_band_fails_without_regrouping(self):
        with self.assertRaises(ValueError):
            training.make_plan(population(n=5))
        with self.assertRaises(ValueError):
            training.make_plan(population(subset="eval_seen"))

    def test_analytic_conditional_optimum_and_empty_bin_recovery(self):
        adjustment = training.make_plan(population()).log_adjustment
        natural = np.arange(1., 67.)
        natural[[0, 15, 62]] = 0
        natural /= natural.sum()
        q = natural * np.exp(adjustment)
        q /= q.sum()
        recovered = q * np.exp(-adjustment)
        recovered /= recovered.sum()
        np.testing.assert_allclose(recovered, natural, atol=1e-16)
        self.assertTrue((q[[0, 15, 62]] == 0).all())
        # The exact optimum is on the boundary for empty categories. Finite logits
        # approach that boundary; their omitted mass is less than1e-25 here.
        z = torch.tensor(np.log(np.maximum(natural, 1e-30)), requires_grad=True)
        labels = torch.arange(66)
        target = torch.tensor(training.CENTERS)
        correction = torch.tensor(adjustment)
        risk = (torch.tensor(q) * training.loss_vector(z.expand(66, -1), target, labels,
                                                       "band_exposure_ce", correction)).sum()
        risk.backward()
        self.assertLess(z.grad.abs().max().item(), 1e-15)
        wrong = z.detach().clone().requires_grad_(True)
        wrong_risk = (torch.tensor(q) * torch.nn.functional.cross_entropy(
            wrong.expand(66, -1) - correction, labels, reduction="none")).sum()
        wrong_risk.backward()
        self.assertGreater(wrong.grad.abs().max().item(), 1e-4)

    def test_weighted_huber_exact_existing_equation(self):
        logits = torch.arange(132, dtype=torch.float64).reshape(2, 66) / 100
        y = torch.tensor([2.2, 5.1], dtype=torch.float64)
        labels = torch.tensor([22, 51])
        pred = logits.softmax(1) @ torch.tensor(training.CENTERS)
        expected = torch.nn.functional.huber_loss(pred, y, delta=1., reduction="none") * (1 + 5 * (y - 3.5).clamp_min(0))
        expected += .075 * torch.nn.functional.cross_entropy(logits, labels, reduction="none")
        actual = training.loss_vector(logits, y, labels, "huber_ce", torch.zeros(66))
        torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    def test_plan_rejects_cross_deadline_identity_change(self):
        p = plans()
        original = p[3].population
        changed = training.PrefixPopulation(3, "fit", original.source_rows, original.events,
            original.stations, original.targets, original.weights * 2)
        p[3] = training.make_plan(changed)
        with self.assertRaises(ValueError):
            training.checked_plans(p)

    def test_paired_orders_schedule_and_actual_remainder(self):
        p = plans((513, 509, 501))
        self.assertEqual(training.checked_plans(p), 513)
        g1, g2, g3 = [torch.Generator().manual_seed(20261009) for _ in range(3)]
        a = training.epoch_orders(p, "huber_ce", g1)
        b = training.epoch_orders(p, "natural_ce", g2)
        c = training.epoch_orders(p, "band_exposure_ce", g3)
        for t in training.HORIZONS:
            np.testing.assert_array_equal(a[t], b[t])
            self.assertEqual(len(c[t]), 513)
            self.assertLess(c[t].max(), len(p[t].labels))
        self.assertEqual([[len(x[t]) for t in training.HORIZONS] for x in training.joint_batches(a)], [[512]*3, [1]*3])

    def test_empirical_sampler_law(self):
        p = plans()
        generator = torch.Generator().manual_seed(7)
        draws = np.concatenate([training.epoch_orders(p, "band_exposure_ce", generator)[1] for _ in range(2000)])
        observed = np.bincount(draws, minlength=len(p[1].labels)) / len(draws)
        np.testing.assert_allclose(observed, p[1].exposure_probability, atol=.006, rtol=0)

    def test_forward_input_whitelist_alignment_and_future_cutoff(self):
        def extra(t, ids):
            item = loader(t, ids)
            item.inputs["targets"] = torch.zeros(len(ids))
            return item
        with self.assertRaises(ValueError):
            training.load_prefix(extra, 1, np.array([1, 2]), "cpu")
        def wrong(t, ids):
            item = loader(t, ids)
            item.source_rows = ids[::-1]
            return item
        with self.assertRaises(ValueError):
            training.load_prefix(wrong, 1, np.array([1, 2]), "cpu")
        full = torch.randn(2, 3, 500)
        def prefix(t, ids):
            item = loader(t, ids)
            item.inputs["counts"] = full[..., :100*t].clone()
            return item
        model = ToyEncoder().eval()
        before = model.forward_prefix(training.load_prefix(prefix, 1, np.array([1, 2]), "cpu"), 1)
        full[..., 100:] = float("nan")
        after = model.forward_prefix(training.load_prefix(prefix, 1, np.array([1, 2]), "cpu"), 1)
        torch.testing.assert_close(before, after, rtol=0, atol=0)
        with self.assertRaises(ValueError):
            training.load_prefix(prefix, 5, np.array([1, 2]), "cpu")


class CompletedGridTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.plans = plans()
        cls.directories = {}
        for control in training.CONTROLS:
            for seed in training.SEEDS:
                path = cls.root / f"{control}_{seed}"
                training.fit_control(ToyEncoder, loader, cls.plans, control, seed, path, identity(cls.plans))
                cls.directories[(control, seed)] = path

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_grid_provenance_fixed_epochs_and_full_checkpoint(self):
        records = training.require_completed_grid(self.directories)
        self.assertEqual(len(records), 6)
        path = self.directories[("huber_ce", 20261009)]
        state = torch.load(path / "latest.pth", weights_only=True)
        self.assertEqual(state["completed_epoch"], 10)
        self.assertEqual(state["scheduler"]["last_epoch"], 10)
        self.assertEqual(len(state["history"]), 10)
        self.assertIn("sampler_rng", state)
        self.assertIn("numpy_rng", state)
        self.assertIn("cuda_rng", state)
        self.assertNotEqual(records[("huber_ce", 20261009)]["initial_model_sha256"], records[("huber_ce", 20261009)]["final_model_sha256"])
        sampler = torch.Generator().manual_seed(20261009)
        for _ in range(10):
            training.epoch_orders(self.plans, "huber_ce", sampler)
        torch.testing.assert_close(sampler.get_state(), state["sampler_rng"], rtol=0, atol=0)

    def test_same_runtime_repeatability(self):
        out = self.root / "repeat"
        result = training.fit_control(ToyEncoder, loader, self.plans, "natural_ce", 20261009, out, identity(self.plans))
        reference = json.loads((self.directories[("natural_ce", 20261009)] / "completed.json").read_text())
        self.assertEqual(result["final_model_sha256"], reference["final_model_sha256"])

    def test_partial_grid_and_tampered_history_rejected(self):
        with self.assertRaises(ValueError):
            training.require_completed_grid(dict(list(self.directories.items())[:-1]))
        path = self.directories[("natural_ce", 20261009)] / "history.json"
        original = path.read_bytes()
        try:
            path.write_text("[]\n")
            with self.assertRaises(ValueError):
                training.require_completed_grid(self.directories)
        finally:
            path.write_bytes(original)

    def test_held_normalizer_binding_and_failed_fit_do_not_publish(self):
        bad = identity(self.plans)
        bad["normalizer_fit_population_sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            training.fit_control(ToyEncoder, loader, self.plans, "natural_ce", 20261009, self.root / "badnorm", bad)
        self.assertFalse((self.root / "badnorm").exists())
        def failed(t, rows):
            raise RuntimeError("Synthetic unavailable prefix")
        with self.assertRaises(RuntimeError):
            training.fit_control(ToyEncoder, failed, self.plans, "natural_ce", 20261009, self.root / "failed", identity(self.plans))
        self.assertFalse((self.root / "failed/completed.json").exists())

    def test_actual_training_remainder_and_encoder_updates(self):
        p = plans((513, 509, 501))
        sizes = []
        def recording_loader(t, rows):
            sizes.append((t, len(rows)))
            return loader(t, rows)
        output = self.root / "remainder"
        training.fit_control(ToyEncoder, recording_loader, p, "band_exposure_ce", 20261009, output, identity(p))
        self.assertEqual(sizes, [(1, 512), (3, 512), (5, 512), (1, 1), (3, 1), (5, 1)] * 10)
        state = torch.load(output / "latest.pth", weights_only=True)
        self.assertTrue(all(int(s["step"]) == 20 for s in state["optimizer"]["state"].values()))
        torch.manual_seed(20261009)
        initial = ToyEncoder().state_dict()
        self.assertFalse(torch.equal(initial["encoder.weight"], state["model"]["encoder.weight"]))

    def test_completed_predictions_are_natural_normalized_all_panels(self):
        held = {(t, subset): population(t, 12, subset, 1000 + 100 * j)
                for t in training.HORIZONS for j, subset in enumerate(("eval_seen", "eval_held"))}
        prediction = training.predict_completed_grid(self.directories, ToyEncoder, loader, held,
            identity=identity(self.plans),
            population_validator=lambda p: self.assertEqual(p.identity(), held[(p.seconds, p.subset)].identity()))
        self.assertEqual(len(prediction), 36)
        for p in prediction.values():
            np.testing.assert_allclose(p.sum(1), 1, atol=1e-14)
            self.assertTrue(np.isfinite(p).all())
        key = ("band_exposure_ce", 20261009)
        state = torch.load(self.directories[key] / "latest.pth", weights_only=True)
        model = ToyEncoder()
        model.load_state_dict(state["model"])
        p = held[(1, "eval_seen")]
        with torch.no_grad():
            direct = model.forward_prefix(loader(1, p.source_rows).inputs, 1).double().softmax(1).numpy()
        np.testing.assert_array_equal(prediction[(*key, 1, "eval_seen")], direct)

    def test_evaluation_rejects_different_binding_before_any_callback(self):
        held = {(t, subset): population(t, 12, subset, 1000 + 100 * j)
                for t in training.HORIZONS for j, subset in enumerate(("eval_seen", "eval_held"))}
        def forbidden(*args):
            self.fail("A mismatched evaluation binding reached an inference callback")
        for field in ("export_sha256", "backbone_sha256", "normalizers_sha256",
                      "normalizer_fit_population_sha256", "population_sha256"):
            changed = identity(self.plans)
            changed[field] = "d" * 64
            with self.assertRaisesRegex(ValueError, "Evaluation binding"):
                training.predict_completed_grid(self.directories, forbidden, forbidden, held,
                                                 identity=changed, population_validator=forbidden)

    def test_completion_initialization_must_match_verified_configuration(self):
        path = self.directories[("natural_ce", 20261009)] / "completed.json"
        original = path.read_bytes()
        try:
            record = json.loads(original)
            record["initial_model_sha256"] = "d" * 64
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "Completion initialization"):
                training.require_completed_grid(self.directories)
        finally:
            path.write_bytes(original)

    def test_held_validator_runs_before_any_inference_callback(self):
        held = {(t, subset): population(t, 12, subset, 1000 + 100 * j)
                for t in training.HORIZONS for j, subset in enumerate(("eval_seen", "eval_held"))}
        def forbidden(*args):
            self.fail("Rejected held identities reached inference")
        def rejected(p):
            raise ValueError("Synthetic held identity mismatch")
        with self.assertRaisesRegex(ValueError, "Synthetic held identity"):
            training.predict_completed_grid(self.directories, forbidden, forbidden, held,
                identity=identity(self.plans), population_validator=rejected)


class MetricsTest(unittest.TestCase):
    def test_continuous_crps_quantization_and_zero_likelihood(self):
        p = population(n=6, subset="eval_seen")
        prob = np.zeros((6, 66))
        labels, _ = training.labels_and_support(p.targets)
        prob[np.arange(6), labels] = 1
        scores = metrics.distribution_scores(prob, p)
        self.assertAlmostEqual(scores["continuous_crps"], .05)
        self.assertEqual(scores["quantized_crps"], 0)
        self.assertEqual(scores["categorical_nll"], 0)
        self.assertEqual(scores["categorical_interval90_coverage"], 1)
        self.assertEqual(scores["continuous_center_interval90_coverage"], 0)
        prob = np.roll(prob, 1, axis=1)
        scores = metrics.distribution_scores(prob, p)
        self.assertIsNone(scores["categorical_nll"])
        self.assertTrue(scores["categorical_nll_infinite"])

    def test_continuous_crps_matches_pairwise_definition(self):
        p = population(n=6, subset="eval_seen")
        prob = np.random.default_rng(2).dirichlet(np.ones(66), size=6)
        term1 = (prob * np.abs(training.CENTERS - p.targets[:, None])).sum(1)
        pair = np.abs(training.CENTERS[:, None] - training.CENTERS[None])
        brute = term1 - .5 * np.einsum("bi,ij,bj->b", prob, pair, prob)
        self.assertAlmostEqual(metrics.distribution_scores(prob, p)["continuous_crps"], np.average(brute, weights=p.weights))

    def test_weighted_cvar_and_event_macro_match_shared_probe(self):
        self.assertAlmostEqual(metrics.weighted_cvar(np.array([10., 0.]), np.array([1., 99.])), 2.)
        p = population(n=24, subset="eval_seen")
        prediction = p.targets + np.arange(24) / 24
        score = metrics.point_metrics(prediction, p)
        expected_event = [np.abs(prediction[p.events == e] - p.targets[p.events == e]).mean() for e in np.unique(p.events)]
        self.assertAlmostEqual(score["event_macro_mae"], np.mean(expected_event))

    def test_support_failure_keeps_continuous_errors_and_invalid_pmf_rejected(self):
        p = population(n=6, subset="eval_seen")
        y = p.targets.copy(); y[-1] = 7.1
        p = training.PrefixPopulation(1, "eval_seen", p.source_rows, p.events, p.stations, y, p.weights)
        prob = np.full((6, 66), 1 / 66)
        scores = metrics.score_pmf(prob, p)
        self.assertEqual(scores["mean"]["records"], 6)
        self.assertEqual(scores["distribution"]["unsupported_category_records"], 1)
        self.assertIsNone(scores["distribution"]["categorical_nll"])
        with self.assertRaises(ValueError):
            metrics.score_pmf(prob * .99, p)

    def test_bootstrap_identity_and_shared_rng_parity(self):
        p = population(n=24, subset="eval_seen")
        prob = np.full((24, 66), 1 / 66)
        result = metrics.paired_bootstrap(prob, prob, p)
        self.assertEqual(result["weighted_mae_ci95"], [0., 0.])
        self.assertEqual(result["m4_event_macro_mae_ci95"], [0., 0.])
        # Independent local reference only; synthetic targets, never real arrays.
        reference_path = Path(__file__).parents[1] / "polarization_preflight/ridge_probe.py"
        if reference_path.exists():
            spec = importlib.util.spec_from_file_location("shared_ridge_probe", reference_path)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            candidate = np.random.default_rng(1).dirichlet(np.ones(66), size=24)
            a = np.c_[metrics.pmf_mean(candidate), np.ones((24, 2))]
            b = np.c_[metrics.pmf_mean(prob), np.ones((24, 2))]
            y = np.c_[p.targets, np.ones((24, 2))]
            expected = module.paired_bootstrap(a, b, y, p.weights, p.events)
            actual = metrics.paired_bootstrap(candidate, prob, p)
            self.assertEqual(actual["weighted_mae_ci95"], expected["weighted_magnitude_mae_ci95"])
            self.assertEqual(actual["m4_event_macro_mae_ci95"], expected["m4_event_macro_mae_ci95"])

    def test_comparison_has_both_seeds_ensemble_and_no_optional_action_gate(self):
        p = population(n=24, subset="eval_seen")
        prob = np.full((24, 66), 1 / 66)
        candidates = {s: prob.copy() for s in training.SEEDS}
        row = metrics.comparison(candidates, candidates, p, valid_fraction=.99)
        self.assertEqual(row["seed_m4_event_macro_deltas"], [0., 0.])
        self.assertEqual(set(row["candidate"]), {"mean", "median", "distribution", "strata"})
        self.assertFalse(metrics.investment_gate([])["pass"])
        rows = []
        for reference in ("natural_ce", "huber_ce"):
            for t in training.HORIZONS:
                for subset in ("eval_seen", "eval_held"):
                    copied = copy.deepcopy(row)
                    copied.update(reference_control=reference, seconds=t, subset=subset)
                    rows.append(copied)
        self.assertEqual(metrics.investment_gate(rows)["status"], "inconclusive_tail_sample")
        for item in rows:
            item["candidate"]["mean"]["tail"]["4"]["events"] = 20
        self.assertEqual(metrics.investment_gate(rows)["status"], "failed")

    def test_full_fixed_report_and_empty_tail_are_json_safe(self):
        panels = {(t, s): population(t, n=24, subset=s) for t in training.HORIZONS for s in ("eval_seen", "eval_held")}
        prediction = {(c, seed, t, s): np.full((24, 66), 1 / 66)
                      for c in training.CONTROLS for seed in training.SEEDS for t, s in panels}
        strata = {key: {"unit": np.repeat("velocity", 24), "family": np.repeat("HH", 24)} for key in panels}
        report = metrics.summarize_predictions(prediction, panels, strata, {key: .99 for key in panels})
        self.assertEqual(len(report["scores"]), 54)
        self.assertEqual(len(report["comparisons"]), 12)
        self.assertEqual(len(report["matched_event_panels"]), 18)
        json.dumps(report, allow_nan=False)
        p = population(n=3, subset="eval_seen")  # Only bands0/1/2, no M>=4.
        prob = {seed: np.full((3, 66), 1 / 66) for seed in training.SEEDS}
        empty = metrics.comparison(prob, prob, p, valid_fraction=1.)
        self.assertEqual(empty["seed_m4_event_macro_deltas"], [None, None])
        json.dumps(empty, allow_nan=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)

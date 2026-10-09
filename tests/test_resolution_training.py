"""Independent mathematics and provenance checks for revision training."""

from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parents[1] / "research/2026-10-09/phase2"))
from resolution_distillation import ResolutionDistillationModel
from train_resolution import (
    array_sha256, precompute_teacher_cdfs, revision_diagnostics,
    revision_targets, training_loss, save_latest_checkpoint, clip_student_gradients,
    evaluate_resolution,
)
from train_sequential import supervised_loss


class RecordingCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.observed = []

    def forward(self, x):
        self.observed.append(x.detach().clone())
        return torch.zeros(len(x), 66, device=x.device) + x.mean((1, 2))[:, None]


class ResolutionTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(20261009)

    def test_squared_revision_is_conditional_mean_of_ideal_brier_gain(self):
        current = torch.full((2, 1), .1, requires_grad=True)
        teacher = torch.full((2, 1), .9, requires_grad=True)
        # First row has B=0, second row B=1; later conditional P(B=1)=.9.
        targets = revision_targets(current, teacher, torch.tensor([1, 0]))
        torch.testing.assert_close(targets["realized_brier_gain"].flatten(), torch.tensor([-.8, .8]))
        torch.testing.assert_close(targets["squared_revision"].flatten(), torch.tensor([.64, .64]))
        probabilities = torch.tensor([.1, .9])
        conditional_mean = probabilities @ targets["realized_brier_gain"].flatten()
        torch.testing.assert_close(conditional_mean, targets["squared_revision"][0, 0])
        gain_variance = probabilities @ (targets["realized_brier_gain"].flatten() - conditional_mean).square()
        self.assertGreater(gain_variance.item(), .2)
        self.assertFalse(targets["realized_brier_gain"].requires_grad)
        self.assertFalse(targets["squared_revision"].requires_grad)

    def test_imperfect_teacher_can_have_negative_expected_gain(self):
        targets = revision_targets(torch.full((2, 1), .1), torch.full((2, 1), .9), torch.tensor([1, 0]))
        true_outcome_probabilities = torch.tensor([.9, .1])
        expected_gain = true_outcome_probabilities @ targets["realized_brier_gain"].flatten()
        self.assertLess(expected_gain.item(), 0)
        self.assertGreater(targets["squared_revision"].mean().item(), 0)

    def test_supervised_control_is_independent_of_teacher_predictions(self):
        model = ResolutionDistillationModel()
        forecasts = model.forward_with_resolution(torch.randn(2, 3, 500))
        labels, weights = torch.tensor([10, 45]), torch.tensor([.5, 1.5])
        a = {3: torch.zeros(2, 65), 5: torch.zeros(2, 65)}
        b = {3: torch.ones(2, 65), 5: torch.ones(2, 65)}
        first, _ = training_loss(forecasts, labels, weights, a, "supervised")
        second, _ = training_loss(forecasts, labels, weights, b, "supervised")
        torch.testing.assert_close(first, second, atol=0, rtol=0)
        first.backward()
        self.assertIsNone(model.resolution_head.weight.grad)

    def test_gain_and_revision_controls_receive_distinct_unclipped_targets(self):
        logits = torch.tensor([[.1, .9]]).log().requires_grad_()
        cdf = logits.softmax(-1).cumsum(-1)[:, :-1]
        head = torch.tensor([[.5]], requires_grad=True)
        forecast = {1: {"duration": 1, "future_duration": 3, "logits": logits,
                        "cdf": cdf, "resolution": head}}
        targets = {3: torch.tensor([[.9]])}
        revision_loss, _ = training_loss(forecast, torch.tensor([1]), torch.ones(1), targets, "cdf_resolution")
        revision_loss.backward(retain_graph=True)
        self.assertLess(head.grad.item(), 0)
        head.grad.zero_()
        gain_loss, _ = training_loss(forecast, torch.tensor([1]), torch.ones(1), targets, "cdf_brier_gain")
        gain_loss.backward()
        self.assertGreater(head.grad.item(), 0)

    def test_weighted_supervised_control_matches_existing_baseline_objective(self):
        model = ResolutionDistillationModel(resolution_envelope="unit")
        forecasts = model.forward_with_resolution(torch.randn(2, 3, 500))
        magnitudes, weights = torch.tensor([1.3, 4.7]), torch.tensor([.5, 1.5])
        labels = (magnitudes / .1 + 1e-5).floor().long()
        centers = (torch.arange(66) + .5) * .1
        actual, _ = training_loss(forecasts, labels, weights, {}, "supervised",
                                  objective="weighted", magnitudes=magnitudes, centers=centers)
        expected = supervised_loss({t: f["logits"] for t, f in forecasts.items()}, magnitudes,
                                   weights, centers, "weighted")
        torch.testing.assert_close(actual, expected)

    def test_teacher_precomputation_preserves_full_nested_prefix(self):
        teachers = {3: RecordingCNN(), 5: RecordingCNN()}
        x = torch.randn(4, 3, 500, requires_grad=True)
        targets, checks = precompute_teacher_cdfs(teachers, x, batch_size=2)
        self.assertEqual(checks, {})
        for duration in (3, 5):
            torch.testing.assert_close(torch.cat(teachers[duration].observed), x[:, :, :100 * duration])
            self.assertEqual(targets[duration].shape, (4, 65))
            self.assertFalse(targets[duration].requires_grad)
        with self.assertRaises(ValueError):
            precompute_teacher_cdfs(teachers, x, reference_logits={3: np.ones((4, 66)), 5: np.ones((4, 66))})

    def test_revision_diagnostics_report_negative_gain_without_clipping(self):
        current = np.full((4, 65), .1)
        teacher = np.full((4, 65), .9)
        predicted = np.full((4, 65), .64)
        y = np.array([.05, 6.55, .05, 6.55])
        ids = np.array(["a", "b", "a", "b"])
        centers = (np.arange(66) + .5) * .1
        result = revision_diagnostics(current, predicted, teacher, y, ids, centers)
        self.assertAlmostEqual(result["revision_boundary_mse"], 0)
        self.assertAlmostEqual(result["negative_gain_boundary_fraction"], .5)
        self.assertAlmostEqual(result["realized_brier_gain_integrated_mean"], 0)
        self.assertEqual(result["revision_target_exceeds_bernoulli_envelope_fraction"], 1)
        self.assertEqual(result["events"], 2)

    def test_row_identity_changes_with_order_shape_or_dtype(self):
        rows = np.array([1, 3, 8], dtype=np.int64)
        self.assertEqual(array_sha256(rows), array_sha256(rows.copy()))
        for different in (rows[::-1], rows.reshape(1, -1), rows.astype(np.int32)):
            self.assertNotEqual(array_sha256(rows), array_sha256(different))

    def test_atomic_checkpoint_retains_optimizer_schedule_and_rng_identity(self):
        model = nn.Linear(2, 1)
        optimizer = torch.optim.AdamW(model.parameters())
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=2)
        model(torch.ones(1, 2)).sum().backward()
        optimizer.step()
        scheduler.step()
        config = {"train_rows_sha256": "recorded-row-identity", "epochs": 2}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.pth"
            save_latest_checkpoint(path, model, optimizer, scheduler, 1, config, {"source_sha256": {"runner.py": "digest"}})
            checkpoint = torch.load(path, weights_only=True)
            self.assertEqual(checkpoint["completed_epoch"], 1)
            self.assertEqual(checkpoint["train_rows_sha256"], config["train_rows_sha256"])
            self.assertEqual(checkpoint["scheduler"]["last_epoch"], 1)
            self.assertTrue(checkpoint["optimizer"]["state"])
            torch.testing.assert_close(checkpoint["torch_rng_state"], torch.get_rng_state())
            self.assertFalse(path.with_name("latest.pth.tmp").exists())
            save_latest_checkpoint(path, model, optimizer, scheduler, 2, config, {})
            self.assertEqual(torch.load(path, weights_only=True)["completed_epoch"], 2)

    def test_detached_head_gradient_cannot_rescale_predictor_gradient(self):
        model = nn.Module()
        model.backbone = nn.Linear(1, 1, bias=False)
        model.resolution_head = nn.Linear(1, 1, bias=False)
        model.backbone.weight.grad = torch.ones_like(model.backbone.weight)
        model.resolution_head.weight.grad = torch.full_like(model.resolution_head.weight, 1000.)
        clip_student_gradients(model)
        torch.testing.assert_close(model.backbone.weight.grad, torch.ones_like(model.backbone.weight))
        self.assertAlmostEqual(model.resolution_head.weight.grad.norm().item(), 5., places=5)

    def test_export_names_distinguish_revision_gain_and_untrained_heads(self):
        model = ResolutionDistillationModel(resolution_envelope="unit")
        x = torch.randn(4, 3, 500)
        y = np.array([1., 2., 4., 5.])
        ids = np.array(["a", "b", "c", "d"])
        centers = (np.arange(66) + .5) * .1
        targets = {t: torch.full((4, 65), .5) for t in (3, 5)}
        for control in ("supervised", "cdf_distill", "cdf_resolution", "cdf_brier_gain"):
            _, predictions, diagnostics = evaluate_resolution(model, x, y, ids, centers, targets, control)
            names = {key for key in predictions if not key.startswith(("mean_", "median_", "observed_"))}
            if control in ("supervised", "cdf_distill"):
                self.assertEqual(names, set())
                self.assertFalse(diagnostics["1_to_3"]["head"]["trained"])
            else:
                prefix = "revision_energy" if control == "cdf_resolution" else "brier_gain"
                self.assertEqual(names, {f"{prefix}_1_to_3", f"{prefix}_3_to_5"})
                self.assertTrue(diagnostics["1_to_3"]["head"]["trained"])
        for control in ("cdf_resolution", "cdf_brier_gain"):
            _, predictions, diagnostics = evaluate_resolution(model, x, y, ids, centers, targets,
                                                               control, resolution_weight=0.)
            self.assertFalse(diagnostics["1_to_3"]["head"]["trained"])
            self.assertFalse(any(key.startswith(("revision_energy_", "brier_gain_")) for key in predictions))


if __name__ == "__main__":
    unittest.main()

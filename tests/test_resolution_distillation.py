"""Mathematical and information-flow tests for future-resolution hypotheses."""

from pathlib import Path
import sys
import unittest

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).parents[1] / "research/2026-10-09/phase2"))
from resolution_distillation import (
    FrozenNestedTeacher, ResolutionDistillationModel, bounded_resolution,
    cdf_from_logits, forecast_losses,
)


class RecordingTeacher(nn.Module):
    def __init__(self):
        super().__init__()
        self.weight = nn.Parameter(torch.zeros(66))
        self.observed = []

    def forward(self, x):
        self.observed.append(x.detach().clone())
        duration = {100: 1, 300: 3, 500: 5}[x.shape[-1]]
        return {duration: self.weight.expand(x.shape[0], -1)}


class ResolutionDistillationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(20261009)

    def test_student_matches_independent_baseline_and_has_no_future_access(self):
        model = ResolutionDistillationModel()
        x = torch.randn(2, 3, 500)
        changed = x.clone()
        changed[:, :, 100:] = 20 * torch.randn_like(changed[:, :, 100:])
        with torch.no_grad():
            forecasts = model.forward_with_resolution(x)
            early = model.forward_with_resolution(changed)[1]
            baseline = model.backbone(x)
        for duration, forecast in forecasts.items():
            torch.testing.assert_close(forecast["logits"], baseline[duration], rtol=0, atol=0)
            self.assertEqual(forecast["cdf"].shape, (2, 65))
            self.assertTrue((forecast["cdf"][:, 1:] >= forecast["cdf"][:, :-1]).all())
        torch.testing.assert_close(forecasts[1]["cdf"], early["cdf"], rtol=0, atol=0)
        torch.testing.assert_close(forecasts[1]["resolution"], early["resolution"], rtol=0, atol=0)
        self.assertIsNone(forecasts[5]["resolution"])
        self.assertEqual(model.parameter_counts()["resolution_head"], 65 * 129)

    def test_resolution_envelope_and_detached_probability_gradient(self):
        cdf = torch.tensor([[0., .1, .5, .9, 1.]], requires_grad=True)
        head = torch.tensor([[-10., -2., 0., 2., 10.]], requires_grad=True)
        resolution = bounded_resolution(cdf, head)
        self.assertTrue((resolution >= 0).all())
        self.assertTrue((resolution <= cdf * (1 - cdf)).all())
        resolution.sum().backward()
        self.assertIsNone(cdf.grad)
        self.assertTrue(torch.isfinite(head.grad).all())
        self.assertGreater(head.grad.abs().sum().item(), 0)

    def test_nested_teacher_uses_full_prefix_and_remains_frozen(self):
        teacher = RecordingTeacher()
        frozen = FrozenNestedTeacher(teacher)
        frozen.train(True)
        x = torch.randn(2, 3, 500, requires_grad=True)
        targets = frozen(x)
        self.assertFalse(frozen.training)
        self.assertFalse(teacher.training)
        self.assertFalse(teacher.weight.requires_grad)
        self.assertEqual(set(targets), {1, 3})
        torch.testing.assert_close(teacher.observed[0], x[:, :, :300])
        torch.testing.assert_close(teacher.observed[1], x[:, :, :500])
        self.assertFalse(targets[1]["cdf"].requires_grad)
        self.assertFalse(targets[3]["cdf"].requires_grad)
        self.assertEqual(frozen(x[:, :, :100]), {})

    def test_ideal_nested_forecast_obeys_resolution_decomposition(self):
        # X_t reveals a coarse group; a later feature yields two conditional
        # Bernoulli probabilities. Their weighted average is the current CDF.
        probabilities = torch.tensor([.25, .75], dtype=torch.float64)
        teacher = torch.tensor([.1, .7], dtype=torch.float64)
        current = (probabilities * teacher).sum()
        resolution = (probabilities * (teacher - current).square()).sum()
        residual = (probabilities * teacher * (1 - teacher)).sum()
        torch.testing.assert_close(current * (1 - current), resolution + residual)
        self.assertLessEqual(resolution.item(), (current * (1 - current)).item())
        # Current prediction is the minimizer of expected squared CDF
        # distillation; a biased alternative increases its population loss.
        distorted = current + .2
        loss = (probabilities * (current - teacher).square()).sum()
        worse = (probabilities * (distorted - teacher).square()).sum()
        self.assertLess(loss.item(), worse.item())

    def test_proper_supervised_losses_favor_true_bin_distribution(self):
        population = torch.tensor([.7, .2, .1], dtype=torch.float64)
        labels = torch.arange(3)
        def score(distribution):
            logits = distribution.log().expand(3, -1)
            forecast = {"duration": 5, "future_duration": None, "logits": logits,
                        "cdf": cdf_from_logits(logits), "resolution": None}
            return (population * forecast_losses(forecast, labels)["total"]).sum()
        self.assertLess(score(population).item(), score(torch.tensor([.2, .3, .5], dtype=torch.float64)).item())

    def test_imperfect_teacher_need_not_obey_tower_identity(self):
        truth = torch.tensor(.2)
        biased_future_predictions = torch.tensor([.6, .8])
        self.assertGreater((biased_future_predictions.mean() - truth).abs().item(), .4)
        # This is why supervised controls and teacher calibration matter;
        # merely observing more samples does not prove the tower condition.

    def test_resolution_target_is_unclipped_and_both_targets_are_detached(self):
        logits = torch.tensor([[.1, .9]], dtype=torch.float64).log().requires_grad_()
        cdf = cdf_from_logits(logits)
        predicted = torch.tensor([[.045]], dtype=torch.float64, requires_grad=True)
        teacher_cdf = torch.tensor([[1.]], dtype=torch.float64, requires_grad=True)
        forecast = {"duration": 1, "future_duration": 3, "logits": logits,
                    "cdf": cdf, "resolution": predicted}
        target = {"current_duration": 1, "teacher_duration": 3, "cdf": teacher_cdf}
        losses = forecast_losses(forecast, torch.tensor([0]), target,
                                 ce_weight=0., ordinal_weight=0., distillation_weight=0.)
        expected = .1 * (.045 - .81)**2
        self.assertAlmostEqual(losses["resolution"].item(), expected)
        losses["resolution"].sum().backward()
        self.assertIsNone(logits.grad)
        self.assertIsNone(teacher_cdf.grad)
        self.assertLess(predicted.grad.item(), 0)

    def test_combined_loss_has_finite_student_gradients_and_no_teacher_gradients(self):
        student = ResolutionDistillationModel()
        teacher_model = RecordingTeacher()
        teacher = FrozenNestedTeacher(teacher_model)
        x = torch.randn(2, 3, 500)
        forecasts, targets = student.forward_with_resolution(x), teacher(x)
        loss = sum(forecast_losses(v, torch.tensor([10, 45]), targets.get(t))["total"].mean()
                   for t, v in forecasts.items())
        loss.backward()
        for name, parameter in student.named_parameters():
            self.assertIsNotNone(parameter.grad, name)
            self.assertTrue(torch.isfinite(parameter.grad).all(), name)
        self.assertIsNone(teacher_model.weight.grad)

    def test_rejects_non_nested_or_mismatched_teacher_horizons(self):
        with self.assertRaises(ValueError):
            ResolutionDistillationModel(future_horizons={3: 1})
        model = ResolutionDistillationModel()
        forecast = model.forward_with_resolution(torch.randn(1, 3, 100))[1]
        with self.assertRaises(ValueError):
            forecast_losses(forecast, torch.tensor([10]))
        target = {"current_duration": 1, "teacher_duration": 5,
                  "cdf": torch.full((1, 65), .5)}
        with self.assertRaises(ValueError):
            forecast_losses(forecast, torch.tensor([10]), target)
        # Supervised-only ablation does not require later observations.
        loss = forecast_losses(forecast, torch.tensor([10]), distillation_weight=0., resolution_weight=0.)
        self.assertTrue(torch.isfinite(loss["total"]).all())


if __name__ == "__main__":
    unittest.main()

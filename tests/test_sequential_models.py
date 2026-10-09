"""Structural checks for causal sequential distribution experiments."""

import importlib.util
from pathlib import Path
import unittest

import torch


MODULE_PATH = (Path(__file__).parents[1] / "research/2026-10-09/phase2/sequential_models.py")
SPEC = importlib.util.spec_from_file_location("sequential_models", MODULE_PATH)
MODELS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODELS)


class SequentialModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(20261009)

    def test_shapes_normalization_and_duration_handling(self):
        for mode in MODELS.MODES:
            model = MODELS.MagnitudeDistributionModel(mode)
            for length, durations in [(100, {1}), (300, {1, 3}), (500, {1, 3, 5})]:
                with self.subTest(mode=mode, length=length), torch.no_grad():
                    outputs = model(torch.randn(2, 3, length))
                    self.assertEqual(set(outputs), durations)
                    for logits in outputs.values():
                        self.assertEqual(logits.shape, (2, 66))
                        self.assertTrue(torch.isfinite(logits).all())
                        torch.testing.assert_close(logits.softmax(-1).sum(-1), torch.ones(2))

    def test_later_samples_cannot_change_earlier_outputs_in_train_or_eval(self):
        x = torch.randn(2, 3, 500)
        after_one = x.clone()
        after_one[:, :, 100:] = 50 * torch.randn_like(after_one[:, :, 100:])
        after_three = x.clone()
        after_three[:, :, 300:] = 50 * torch.randn_like(after_three[:, :, 300:])
        for mode in MODELS.MODES:
            model = MODELS.MagnitudeDistributionModel(mode)
            for training in (True, False):
                model.train(training)
                with self.subTest(mode=mode, training=training), torch.no_grad():
                    reference = model(x)
                    torch.testing.assert_close(reference[1], model(after_one)[1], rtol=0, atol=0)
                    torch.testing.assert_close(reference[3], model(after_three)[3], rtol=0, atol=0)
                    torch.testing.assert_close(reference[1], model(x[:, :, :100])[1], rtol=0, atol=0)
                    torch.testing.assert_close(reference[3], model(x[:, :, :300])[3], rtol=0, atol=0)

    def test_early_outputs_have_no_gradient_to_future_samples(self):
        for mode in MODELS.MODES:
            with self.subTest(mode=mode):
                x = torch.randn(2, 3, 500, requires_grad=True)
                model = MODELS.MagnitudeDistributionModel(mode)
                outputs = model(x)
                outputs[1][:, 0].sum().backward(retain_graph=True)
                self.assertEqual(torch.count_nonzero(x.grad[:, :, 100:]).item(), 0)
                self.assertGreater(torch.count_nonzero(x.grad[:, :, :100]).item(), 0)
                x.grad.zero_()
                outputs[3][:, 0].sum().backward()
                self.assertEqual(torch.count_nonzero(x.grad[:, :, 300:]).item(), 0)

    def test_zero_and_regular_waveforms_have_finite_gradients(self):
        for mode in MODELS.MODES:
            for zero in (True, False):
                with self.subTest(mode=mode, zero=zero):
                    model = MODELS.MagnitudeDistributionModel(mode)
                    x = (torch.zeros(2, 3, 500) if zero else torch.randn(2, 3, 500)).requires_grad_()
                    outputs = model(x)
                    loss = sum(torch.nn.functional.cross_entropy(v, torch.tensor([10, 45])) for v in outputs.values())
                    loss.backward()
                    self.assertTrue(torch.isfinite(x.grad).all())
                    for name, parameter in model.named_parameters():
                        self.assertIsNotNone(parameter.grad, name)
                        self.assertTrue(torch.isfinite(parameter.grad).all(), name)

    def test_sequential_update_accumulates_logit_innovations(self):
        innovation = torch.linspace(-1, 1, 66)
        x = torch.randn(2, 3, 500)
        for mode, multipliers in [
            ("independent", [1, 1, 1]),
            ("sequential", [1, 2, 3]),
            ("entropy_gate", [1, 1.5, 2]),
        ]:
            model = MODELS.MagnitudeDistributionModel(mode)
            with torch.no_grad():
                model.decoder.weight.zero_()
                model.decoder.bias.copy_(innovation)
                outputs, diagnostics = model.forward_with_diagnostics(x)
            for duration, multiplier in zip((1, 3, 5), multipliers):
                expected = (innovation * multiplier).softmax(-1).expand(2, -1)
                torch.testing.assert_close(outputs[duration].softmax(-1), expected)
            self.assertEqual(set(diagnostics["entropy"]), {1, 3, 5})
            self.assertEqual(set(diagnostics["gate"]), set() if mode == "independent" else {3, 5})

    def test_gate_can_use_new_evidence_despite_confident_previous_distribution(self):
        model = MODELS.MagnitudeDistributionModel("entropy_gate")
        with torch.no_grad():
            model.innovation_gate.weight.zero_()
            model.innovation_gate.weight[0, 0] = 4.0
            model.innovation_gate.weight[0, -1] = 1.0
            model.innovation_gate.bias.zero_()
        low_entropy = model.normalized_entropy(torch.tensor([[100.0] + [-100.0] * 65]))
        features = torch.zeros(1, 128)
        low_input = torch.cat([features, low_entropy], dim=1)
        high_input = low_input.clone()
        high_input[:, 0] = 2.0
        self.assertGreater(model.innovation_gate(high_input).sigmoid().item(), .99)
        self.assertAlmostEqual(model.innovation_gate(low_input).sigmoid().item(), .5)

    def test_parameter_budget_is_controlled(self):
        counts = {mode: MODELS.MagnitudeDistributionModel(mode).parameter_counts() for mode in MODELS.MODES}
        self.assertEqual(counts["independent"], counts["sequential"])
        self.assertEqual(counts["entropy_gate"]["total"] - counts["sequential"]["total"], 130)
        self.assertEqual(counts["entropy_gate"]["gate"], 130)
        self.assertLess(counts["entropy_gate"]["total"], 1_000_000)

    def test_rejects_ambiguous_or_malformed_windows(self):
        model = MODELS.MagnitudeDistributionModel()
        for x in [torch.randn(2, 3, 200), torch.randn(2, 2, 500), torch.randn(3, 500), torch.randn(0, 3, 500)]:
            with self.assertRaises(ValueError):
                model(x)
        with self.assertRaises(TypeError):
            model(torch.zeros(2, 3, 500, dtype=torch.int64))
        with self.assertRaises(ValueError):
            MODELS.MagnitudeDistributionModel("unknown")


if __name__ == "__main__":
    unittest.main()

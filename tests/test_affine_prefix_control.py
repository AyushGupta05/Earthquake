"""Ideal invariance, counterexamples, and exact matched raw-baseline replay."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import torch

PHASE2 = Path(__file__).parents[1] / "research/2026-10-09/phase2"
sys.path[:0] = [str(PHASE2), str(PHASE2.parent)]
from affine_prefix_control import AffinePrefixModel, CONTROLS, project_affine_prefix
from sequential_models import MagnitudeDistributionModel
import train_affine_prefix as runner
from train_sequential import supervised_loss


def independently_detrend(x):
    """Full-record least squares, independently using a two-column design."""
    n = x.shape[-1]
    design = torch.stack([torch.ones(n, dtype=x.dtype), torch.linspace(-1, 1, n, dtype=x.dtype)], 1)
    values = x.reshape(-1, n).T
    coefficients = torch.linalg.lstsq(design, values).solution
    return (values - design @ coefficients).T.reshape_as(x)


class AffinePrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(707)

    def test_projection_annihilates_affine_terms_and_is_orthogonal(self):
        x = torch.randn(2, 3, 500, dtype=torch.float64)
        t = torch.arange(500, dtype=torch.float64)
        affine = torch.randn(2, 3, 1, dtype=torch.float64) + .2 * torch.randn(2, 3, 1, dtype=torch.float64) * t
        actual = project_affine_prefix(x)
        torch.testing.assert_close(project_affine_prefix(x + affine), actual, rtol=0, atol=1e-13)
        torch.testing.assert_close(actual.mean(-1), torch.zeros(2, 3, dtype=torch.float64), rtol=0, atol=1e-15)
        torch.testing.assert_close((actual * (t - t.mean())).sum(-1), torch.zeros(2, 3, dtype=torch.float64), rtol=0, atol=3e-12)

    def test_full_record_detrending_and_changed_future_ideal_fixture(self):
        x = torch.randn(2, 3, 1600, dtype=torch.float64)
        start = 137
        model = AffinePrefixModel("affine").double().eval()
        for seconds, stop in [(1, 100), (3, 300), (5, 500)]:
            changed = x.clone()
            changed[..., start + stop:] += 100 * torch.randn_like(changed[..., start + stop:])
            base = independently_detrend(x)[..., start:start + stop]
            alternative = independently_detrend(changed)[..., start:start + stop]
            expected = project_affine_prefix(x[..., start:start + stop])
            torch.testing.assert_close(project_affine_prefix(base), expected, rtol=0, atol=2e-13)
            torch.testing.assert_close(project_affine_prefix(alternative), expected, rtol=0, atol=2e-13)
            with torch.no_grad():
                torch.testing.assert_close(model(base)[seconds], model(alternative)[seconds], rtol=0, atol=2e-12)

    def test_each_deadline_transforms_before_every_encoder_path(self):
        x = torch.randn(2, 3, 500)
        x[..., 100:] += 100
        for control in ("affine", "affine_guard1"):
            model = AffinePrefixModel(control)
            supplied = []
            hook = model.encoder.register_forward_pre_hook(lambda module, args: supplied.append(args[0].detach().clone()))
            model(x)
            hook.remove()
            self.assertEqual([a.shape[-1] for a in supplied], [100, 300, 500])
            for prefix, length in zip(supplied, (100, 300, 500)):
                torch.testing.assert_close(prefix, project_affine_prefix(x[..., :length], int(control == "affine_guard1")), rtol=0, atol=0)
            # A single 5-second fit must not be reused at the 1-second deadline.
            self.assertGreater((supplied[0] - project_affine_prefix(x)[..., :100]).abs().max().item(), 1.)

    def test_prefix_only_forward_and_guard_gradient(self):
        for control in CONTROLS:
            model = AffinePrefixModel(control)
            for training in (True, False):
                model.train(training)
                x = torch.randn(2, 3, 500, requires_grad=True)
                output = model(x)
                changed = x.detach().clone()
                changed[..., 100:] += 300
                torch.testing.assert_close(output[1], model(changed)[1], rtol=0, atol=0)
                torch.testing.assert_close(output[3], model(x[..., :300])[3], rtol=0, atol=0)
                output[1][:, 0].sum().backward()
                cutoff = 99 if control == "affine_guard1" else 100
                self.assertEqual(x.grad[..., cutoff:].count_nonzero().item(), 0)
                self.assertTrue(torch.isfinite(x.grad).all())
                self.assertGreater(x.grad[..., :cutoff].count_nonzero().item(), 0)

    def test_one_sample_guard_precedes_projection_for_known_three_tap_operator(self):
        x = torch.randn(1, 3, 1200, dtype=torch.float64)
        start, stop = 137, 300
        changed = x.clone()
        changed[..., start + stop] += 100
        def release(raw):
            detrended = independently_detrend(raw)
            return .25 * detrended.roll(1, -1) + .5 * detrended + .25 * detrended.roll(-1, -1)
        a = release(x)[..., start:start + stop]
        b = release(changed)[..., start:start + stop]
        torch.testing.assert_close(project_affine_prefix(a, 1), project_affine_prefix(b, 1), rtol=0, atol=2e-13)
        self.assertEqual(project_affine_prefix(a, 1)[..., -1].count_nonzero().item(), 0)
        self.assertGreater((project_affine_prefix(a) - project_affine_prefix(b)).abs().max().item(), 1.)

    def test_quantization_is_a_counterexample_to_exact_release_invariance(self):
        raw = 10 * torch.randn(2, 3, 1200, dtype=torch.float64)
        changed = raw.clone()
        changed[..., 237:] += 1000
        a = independently_detrend(raw).round()[..., 137:237]
        b = independently_detrend(changed).round()[..., 137:237]
        discrepancy = project_affine_prefix(a) - project_affine_prefix(b)
        self.assertGreater(discrepancy.square().mean().sqrt().item(), .05)

    def test_initialization_parameter_count_and_rng_are_matched(self):
        torch.manual_seed(20261009)
        original = MagnitudeDistributionModel("independent")
        reference_rng = torch.get_rng_state().clone()
        for control in CONTROLS:
            torch.manual_seed(20261009)
            actual = AffinePrefixModel(control)
            self.assertEqual(actual.parameter_counts(), original.parameter_counts())
            self.assertTrue(torch.equal(reference_rng, torch.get_rng_state()))
            for k, value in actual.state_dict().items():
                torch.testing.assert_close(value, original.state_dict()[k], rtol=0, atol=0)

    def test_raw_replays_original_optimizer_loop_and_orders_exactly(self):
        x = torch.randn(11, 3, 500)
        y = torch.linspace(.3, 5.2, len(x))
        weights = torch.linspace(.5, 1.5, len(x))
        centers = torch.arange(66).float() * .1 + .05
        for seed in (20261009, 20261010):
            torch.manual_seed(seed)
            original = MagnitudeDistributionModel("independent")
            opt = torch.optim.AdamW(original.parameters(), lr=3e-4, weight_decay=1e-4)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=2, eta_min=3e-5)
            expected = []
            for epoch in range(2):
                original.train()
                order = torch.randperm(len(y), device=y.device)
                total = 0.
                for ix in order.split(4):
                    loss = supervised_loss(original(x[ix]), y[ix], weights[ix], centers, "weighted")
                    opt.zero_grad(set_to_none=True)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(original.parameters(), 5.)
                    opt.step()
                    total += loss.item() * len(ix)
                scheduler.step()
                expected.append((total / len(y), runner.array_sha256(order.numpy())))
            final_rng = torch.get_rng_state().clone()
            torch.manual_seed(seed)
            replay = AffinePrefixModel("raw")
            actual = runner.fit_one(replay, x, y, weights, centers, epochs=2, batch_size=4)
            self.assertTrue(torch.equal(final_rng, torch.get_rng_state()))
            for log, (loss, order_hash) in zip(actual, expected):
                self.assertEqual(log["train_loss"], loss)
                self.assertEqual(log["order_sha256"], order_hash)
            for k, value in replay.state_dict().items():
                torch.testing.assert_close(value, original.state_dict()[k], rtol=0, atol=0)

    def test_zero_prefix_finite_and_bad_input_rejected(self):
        for control in CONTROLS:
            model = AffinePrefixModel(control)
            x = torch.zeros(2, 3, 500, requires_grad=True)
            sum(v.square().sum() for v in model(x).values()).backward()
            self.assertTrue(torch.isfinite(x.grad).all())
            self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
        for x in (torch.zeros(0, 3, 100), torch.zeros(2, 0, 100), torch.zeros(2, 3, 1)):
            with self.assertRaises(ValueError): project_affine_prefix(x)
        with self.assertRaises(TypeError): project_affine_prefix(torch.zeros(2, 3, 100, dtype=torch.int64))
        with self.assertRaises(ValueError): project_affine_prefix(torch.zeros(2, 3, 100), 2)
        with self.assertRaises(ValueError): AffinePrefixModel("unknown")

    def test_runner_cpu_fixture_writes_complete_identities(self):
        n = 8
        x = torch.randn(n, 3, 500)
        y = torch.linspace(.5, 5.1, n)
        reference = {"targets": y.numpy(), "event_ids": np.array([f"event_{i}" for i in range(n)]),
                     "trace_names": np.array([f"trace_{i}" for i in range(n)]), "centers": np.arange(66) * .1 + .05}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "results/2026-10-09/audit.json"
            audit.parent.mkdir(parents=True)
            audit.write_text(json.dumps({s: {"metadata_sha256": f"fixture_{s}"} for s in ("train", "val")}))
            cache = root / "fixture_cache"; cache.write_bytes(b"fixture")
            with mock.patch.object(runner, "ROOT", root), mock.patch.object(runner, "CACHE_PATH", cache), mock.patch.object(runner, "load_examples", return_value=({"train": x, "val": x}, y, torch.ones(n), reference, np.arange(n))):
                runner.main(["--control", "affine", "--device", "cpu", "--epochs", "1", "--batch-size", "4", "--output", str(root / "runs")])
            out, = (root / "runs").iterdir()
            config = json.loads((out / "run.json").read_text())
            identity = json.loads((out / "identity.json").read_text())
            history = json.loads((out / "history.json").read_text())
            checkpoint = torch.load(out / "model.pth", map_location="cpu", weights_only=True)
            restored = AffinePrefixModel("affine")
            restored.load_state_dict(checkpoint["model"], strict=True)
            self.assertEqual(type(checkpoint["config"]["runtime"]["torch"]), str)
            self.assertEqual(runner.model_sha256(restored), config["final_model_sha256"])
            self.assertEqual(config["train_records"], n)
            self.assertEqual(config["train_rows_sha256"], runner.array_sha256(np.arange(n)))
            self.assertEqual(identity["config"]["initial_model_sha256"], config["initial_model_sha256"])
            self.assertEqual(len(history[0]["order_sha256"]), 64)
            self.assertEqual(set(config["validation_identity_sha256"]), {"targets", "event_ids", "trace_names", "centers"})
            with np.load(out / "predictions.npz", allow_pickle=False) as pred:
                for key in reference: np.testing.assert_array_equal(pred[key], reference[key])
                for seconds in (1, 3, 5): self.assertTrue(np.isfinite(pred[f"mean_{seconds}s"]).all())


if __name__ == "__main__":
    unittest.main()

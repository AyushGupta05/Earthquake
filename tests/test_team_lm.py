"""TEAM-LM architecture/masking tests; not a TensorFlow equivalence certificate."""

import math
from pathlib import Path
import sys
import unittest

import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "research/2026-10-09/phase3"))
from team_lm import (
    CoordinateEmbedding, GaussianMixtureHead, InterleavedSelfAttention,
    StationEncoder, TeamLM, mixture_cdf, mixture_log_prob, mixture_nll, prepare_prefix,
)


class TeamLMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(42)

    @staticmethod
    def inputs(stations=3):
        x = torch.randn(1, stations, 1000, 3) * 1e-4
        coords = torch.randn(1, stations, 3)
        coords[..., 0] -= 21
        coords[..., 1] -= 69
        return x, coords, torch.ones(1, stations, dtype=torch.bool)

    def test_prefix_demeaning_scaling_and_exact_future_boundary(self):
        x = torch.arange(1000.).reshape(1, 1, 1000, 1).expand(1, 1, 1000, 3).clone()
        x[:, :, 600:] = float("nan")
        prepared, mask = prepare_prefix(x, None, 1.)
        self.assertEqual(prepared.shape, (1, 1, 3000, 3))
        self.assertTrue(mask.all())
        torch.testing.assert_close(prepared[0, 0, :600, 0], torch.arange(600.) - 299.5)
        self.assertEqual(torch.count_nonzero(prepared[:, :, 600:]).item(), 0)
        normalized, scale = StationEncoder.normalize_and_scale(prepared[:, 0])
        self.assertAlmostEqual(normalized.abs().max().item(), 1., places=6)
        self.assertAlmostEqual(scale.item(), math.log(299.5 + 1e-8) / 100., places=6)

    def test_station_encoder_shape_and_source_initial_head_parameters(self):
        encoder = StationEncoder()
        output = encoder(torch.randn(2, 3000, 3))
        self.assertEqual(output.shape, (2, 500))
        mixture = GaussianMixtureHead()(torch.zeros(2, 500))
        torch.testing.assert_close(mixture["weights"], torch.full((2, 5), .2))
        torch.testing.assert_close(mixture["means"], torch.full((2, 5), 1.8))
        torch.testing.assert_close(mixture["scales"], torch.full((2, 5), .2001))

    def test_coordinate_interleaving_matches_independent_scalar_formula(self):
        module = CoordinateEmbedding()
        coordinates = torch.tensor([[[.03, .02, .005]]])
        embedded = module(coordinates)[0, 0]
        for frequency_index in (0, 1, 49, 99):
            lat_frequency = 2 * math.pi / .01 * (.01 / 15.)**(frequency_index / 100)
            lon_frequency = lat_frequency
            self.assertAlmostEqual(embedded[5 * frequency_index].item(), math.sin(.03 * lat_frequency), places=5)
            self.assertAlmostEqual(embedded[5 * frequency_index + 3].item(), math.cos(.02 * lon_frequency), places=5)
        for frequency_index in (0, 1, 49):
            frequency = 2 * math.pi / .01 * (.01 / 10.)**(frequency_index / 50)
            self.assertAlmostEqual(embedded[10 * frequency_index + 4].item(), math.sin(.005 * frequency), places=5)
            self.assertAlmostEqual(embedded[10 * frequency_index + 9].item(), math.cos(.005 * frequency), places=5)

    def test_attention_uses_interleaved_projection_and_absolute_output(self):
        module = InterleavedSelfAttention(dimension=4, heads=2)
        with torch.no_grad():
            module.query.weight.zero_()
            module.key.weight.zero_()
            module.value.weight.copy_(torch.eye(4))
            module.output.weight.copy_(torch.eye(4))
        x = torch.tensor([[[-1., -2., -3., -4.], [-5., -6., -7., -8.], [100., 200., 300., 400.]]])
        mask = torch.tensor([[True, True, False]])
        actual = module(x, mask)
        # Value heads are [x0,x2] and [x1,x3], then merged head-major.
        expected = torch.tensor([[[3., 5., 4., 6.], [3., 5., 4., 6.], [0., 0., 0., 0.]]])
        torch.testing.assert_close(actual, expected)

    def test_event_prediction_is_station_permutation_invariant(self):
        x, coords, mask = self.inputs()
        permutation = torch.tensor([2, 0, 1])
        for aggregation in ("transformer", "pool"):
            with self.subTest(aggregation=aggregation), torch.no_grad():
                model = TeamLM(aggregation).eval()
                reference = model(x, coords, mask, 3.)
                permuted = model(x[:, permutation], coords[:, permutation], mask[:, permutation], 3.)
                for key in reference:
                    torch.testing.assert_close(reference[key], permuted[key], rtol=1e-4, atol=1e-5)

    def test_unavailable_station_values_and_coordinates_are_irrelevant(self):
        x, coords, mask = self.inputs()
        mask[:, -1] = False
        changed_x, changed_coords = x.clone(), coords.clone()
        changed_x[:, -1] = float("nan")
        changed_coords[:, -1] = float("nan")
        for aggregation in ("transformer", "pool"):
            with self.subTest(aggregation=aggregation), torch.no_grad():
                model = TeamLM(aggregation).eval()
                reference = model(x, coords, mask, 1.)
                changed = model(changed_x, changed_coords, mask, 1.)
                for key in reference:
                    torch.testing.assert_close(reference[key], changed[key], rtol=0, atol=0)

    def test_future_suffix_cannot_change_predictions_or_prefix_gradients(self):
        x, coords, mask = self.inputs(stations=2)
        x = torch.nn.functional.pad(x, (0, 0, 0, 2000))
        for seconds in (1., 3., 5.):
            with self.subTest(seconds=seconds):
                model = TeamLM().eval()
                stop = int(100 * (5 + seconds))
                changed = x.clone()
                changed[:, :, stop:] = 1e8
                with torch.no_grad():
                    reference = model(x, coords, mask, seconds)
                    alternate = model(changed, coords, mask, seconds)
                for key in reference:
                    torch.testing.assert_close(reference[key], alternate[key], rtol=0, atol=0)
                variable = x.clone().requires_grad_()
                mixture_nll(model(variable, coords, mask, seconds), torch.tensor([2.]), density_epsilon=0).backward()
                self.assertTrue(torch.isfinite(variable.grad).all())
                self.assertEqual(torch.count_nonzero(variable.grad[:, :, stop:]).item(), 0)

    def test_missing_stations_leave_valid_finite_event_distribution(self):
        x, coords, mask = self.inputs(stations=2)
        mask.zero_()
        for aggregation in ("transformer", "pool"):
            with torch.no_grad():
                mixture = TeamLM(aggregation)(x, coords, mask, 5.)
                torch.testing.assert_close(mixture["weights"].sum(-1), torch.ones(1))
                self.assertTrue(all(torch.isfinite(v).all() for v in mixture.values()))

    def test_normalized_mixture_density_and_source_floored_score(self):
        logits = torch.tensor([[1., -1., .5, 2., -.5]], dtype=torch.float64, requires_grad=True)
        means = torch.tensor([[1., 2., 3., 4., 5.]], dtype=torch.float64, requires_grad=True)
        scales = torch.tensor([[.2, .4, .6, .8, 1.]], dtype=torch.float64, requires_grad=True)
        mixture = {"logits": logits, "weights": logits.softmax(-1), "means": means, "scales": scales}
        cdf = mixture_cdf(mixture, torch.tensor([-30., 30.], dtype=torch.float64))
        torch.testing.assert_close(cdf, torch.tensor([[0., 1.]], dtype=torch.float64))
        y = torch.tensor([3.5], dtype=torch.float64)
        reference = torch.distributions.MixtureSameFamily(torch.distributions.Categorical(logits=logits),
                    torch.distributions.Normal(means, scales)).log_prob(y)
        torch.testing.assert_close(mixture_log_prob(mixture, y), reference)
        floored = mixture_nll(mixture, y, density_epsilon=1e-6, reduction="none")
        torch.testing.assert_close(floored, -(reference.exp() + 1e-6).log())
        far_tail = mixture_nll(mixture, torch.tensor([100.], dtype=torch.float64), density_epsilon=0)
        self.assertTrue(torch.isfinite(far_tail))
        (far_tail + floored.sum()).backward()
        self.assertTrue(all(torch.isfinite(v.grad).all() for v in (logits, means, scales)))

    def test_rejects_future_cutoff_beyond_compact_cache(self):
        x, _, mask = self.inputs()
        with self.assertRaises(ValueError):
            prepare_prefix(x, mask, 6.)
        with self.assertRaises(ValueError):
            prepare_prefix(x, mask, -6.)
        with self.assertRaises(ValueError):
            prepare_prefix(x, mask.float(), 1.)


if __name__ == "__main__":
    unittest.main()

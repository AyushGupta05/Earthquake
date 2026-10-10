"""Synthetic integration with separately owned response code; no audit payload.

In the isolated code-only review bundle these optional dependencies are absent.
The complete local verification receipt pins the exact dependency sources used.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

import numpy as np
import torch

import exposure_training as training
from shared_response_adapter import bind_shared_response
from test_exposure import population


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SharedResponseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).parents[1] / "response_conditioned_encoder"
        if not (source / "response_model.py").exists() or not (source / "response_data.py").exists():
            raise unittest.SkipTest("Shared code deliberately absent from isolated review bundle")
        cls.data = load_source("shared_response_data", source / "response_data.py")
        cls.model = load_source("shared_response_model", source / "response_model.py")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        path = Path(self.temporary.name)
        parts = [population(n=30), population(n=6, subset="eval_seen", row_start=30),
                 population(n=6, subset="eval_held", row_start=36)]
        source = np.concatenate([p.source_rows for p in parts]) * 7 + 100
        n = len(source)
        valid = np.ones((n, 3), dtype=bool)
        valid[0, 2] = False
        valid[1, 1:] = False
        magnitude = np.concatenate([p.targets for p in parts])
        metadata = dict(source_row_index=source, trace_name=np.array([f"synthetic-trace-{i}" for i in source]),
            source_id=np.concatenate([p.events for p in parts]),
            station_group=np.concatenate([p.stations for p in parts]),
            subset=np.concatenate([np.repeat(p.subset, len(p.targets)) for p in parts]),
            sampling_weight=np.concatenate([p.weights for p in parts]), valid=valid,
            invalid_codes=(~valid).astype(np.uint8), deadlines=np.array(training.HORIZONS),
            sensitivity=np.ones((n, 3), dtype=np.float32), static=np.zeros((n, 34), dtype=np.float32),
            response=np.zeros((n, 72), dtype=np.float32),
            targets=magnitude)
        counts = np.random.default_rng(7).normal(size=(n, 3, 500)).astype(np.float64)
        np.save(path / "counts.npy", counts)
        np.savez(path / "metadata.npz", **metadata)
        outputs = {name: hashlib.sha256((path / name).read_bytes()).hexdigest() for name in ("counts.npy", "metadata.npz")}
        (path / "manifest.json").write_text(json.dumps({"status": "complete", "outputs_sha256": outputs,
                                                       "scope": "synthetic fixture only"}))
        (path / "COMPLETE.json").write_text(json.dumps({"manifest_sha256": hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest()}))
        self.dataset = self.data.CompletedExport(path)
        self.normalizers, self.provenance = self.data.fit_export_normalizers(self.dataset)

    def tearDown(self):
        self.temporary.cleanup()

    def binding(self, provenance=None, normalizers=None):
        return bind_shared_response(self.dataset, normalizers or self.normalizers,
            provenance or self.provenance, self.model.ResponseConditionedModel, self.data.fitting_population_digest)

    def test_shared_B_exact_interface_capacity_and_gradient(self):
        binding = self.binding()
        self.assertEqual([len(binding.plans[t].labels) for t in training.HORIZONS], [30, 29, 28])
        self.assertEqual(binding.identity["population_sha256"], training.population_digest(binding.plans))
        initial = []
        for control in training.CONTROLS:
            torch.manual_seed(20261009)
            model = binding.model_factory()
            self.assertEqual(sum(p.numel() for p in model.parameters()), 380706)
            self.assertEqual(model.arm, "B")
            initial.append(training.model_digest(model))
            for t in training.HORIZONS:
                plan = binding.plans[t]
                ix = np.arange(4)
                batch = training.load_prefix(binding.loader, t, plan.population.source_rows[ix], "cpu")
                self.assertEqual(batch["counts"].shape, (4, 3, 100*t))
                logits = model.forward_prefix(batch, t)
                loss = training.loss_vector(logits, torch.tensor(plan.population.targets[ix]),
                    torch.tensor(plan.labels[ix]), control, torch.tensor(plan.log_adjustment)).mean()
                loss.backward()
            self.assertTrue(all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
            self.assertGreater(model.stem[0].weight.grad.abs().sum().item(), 0)
        self.assertEqual(len(set(initial)), 1)

    def test_normalizer_provenance_and_arrays_must_match(self):
        for field, value in [("held_rows_used", True), ("labels_used", True),
                             ("export_manifest_sha256", "d" * 64)]:
            p = copy.deepcopy(self.provenance); p[field] = value
            with self.assertRaises(ValueError):
                self.binding(p)
        p = copy.deepcopy(self.provenance)
        p["per_deadline_fit_population"]["1"]["sha256"] = "d" * 64
        with self.assertRaises(ValueError):
            self.binding(p)
        altered = {k: v.copy() for k, v in self.normalizers.items()}
        altered["static_mean"][0] += 1
        with self.assertRaises(ValueError):
            self.binding(normalizers=altered)

    def test_source_row_lookup_and_deadline_masks(self):
        binding = self.binding()
        rows = binding.plans[1].population.source_rows[[4, 0, 4]]
        loaded = binding.loader(1, rows)
        np.testing.assert_array_equal(loaded.source_rows, rows)
        np.testing.assert_array_equal(loaded.inputs["counts"].numpy(), self.dataset.counts[[4, 0, 4], :, :100])
        with self.assertRaises(ValueError):
            binding.loader(5, rows)  # Source row0 is invalid only at5seconds.
        with self.assertRaises(ValueError):
            binding.loader(1, np.array([999999]))

    def test_shared_normalizers_ignore_all_held_values(self):
        original = self.dataset.metadata["static"].copy()
        held = self.dataset.metadata["subset"] != "fit"
        self.dataset.metadata["static"][held] += 1000
        changed, _ = self.data.fit_export_normalizers(self.dataset)
        for key in self.normalizers:
            np.testing.assert_array_equal(changed[key], self.normalizers[key])
        self.dataset.metadata["static"] = original

    def test_bound_held_panels_reject_fit_ids_targets_weights_and_subselection(self):
        binding = self.binding()
        m = self.dataset.metadata
        ix = self.dataset.valid_rows("eval_seen", 1)
        def make(**changes):
            values = dict(seconds=1, subset="eval_seen", source_rows=m["source_row_index"][ix],
                events=m["source_id"][ix], stations=m["station_group"][ix],
                targets=m["targets"][ix], weights=m["sampling_weight"][ix])
            values.update(changes)
            return training.PrefixPopulation(**values)
        binding.validate_population(make())
        for changes in ({"source_rows": m["source_row_index"][:len(ix)]},
                        {"targets": m["targets"][ix] + .1},
                        {"weights": m["sampling_weight"][ix] * 2}):
            with self.assertRaisesRegex(ValueError, "Held panel"):
                binding.validate_population(make(**changes))
        p = make()
        sub = training.PrefixPopulation(1, "eval_seen", p.source_rows[:-1], p.events[:-1],
            p.stations[:-1], p.targets[:-1], p.weights[:-1])
        with self.assertRaisesRegex(ValueError, "Held panel"):
            binding.validate_population(sub)


if __name__ == "__main__":
    unittest.main(verbosity=2)

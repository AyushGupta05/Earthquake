import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import h5py
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "research/2026-10-09/phase2"))
from future_growth import (CONTROLS, FutureGrowthModel, auxiliary_loss, clip_gradients,
                           hurdle_log_prob, observed_growth)
from train_future_growth import (array_digest, export_targets, load_targets, load_training_data,
                                 read_metadata, selected_rows, train)
from train_sequential import supervised_loss
from audit_and_export import sha256
from frozen_head_pilot import choose_rows


class FutureGrowthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def setUp(self):
        torch.manual_seed(20261009)

    def test_fixed_baseline_nested_peaks_and_true_zero_atom(self):
        x = np.full(1100, 7.)
        x[100:200] += 2
        x[200:400] += 4
        x[400:600] += 8
        x[600:] += 8
        g, peaks, baseline = observed_growth(x, 100)
        np.testing.assert_allclose(peaks, [2, 4, 8, 8])
        np.testing.assert_allclose(g, np.log10([4, 2, 1]))
        self.assertEqual(baseline, 7.)
        self.assertEqual(g[2], 0)
        # Additive offsets and positive constant instrument gain cancel here.
        np.testing.assert_allclose(observed_growth(3 * x + 20, 100)[0], g)
        np.testing.assert_array_equal(observed_growth(np.zeros(1100), 100)[0], [0, 0, 0])
        for bad_p in (99, 100.5, 101):
            with self.assertRaises(ValueError):
                observed_growth(x, bad_p)

    def test_hurdle_density_has_correct_zero_mass_and_positive_jacobian(self):
        params = {"zero_logit": torch.tensor([0., 0.]), "mu": torch.tensor([0., 0.]),
                  "sigma": torch.tensor([1., 1.])}
        actual = hurdle_log_prob(params, torch.tensor([0., 2.]))
        distribution = torch.distributions.LogNormal(torch.tensor(0.), torch.tensor(1.))
        expected = torch.stack([torch.tensor(.5).log(), torch.tensor(.5).log() + distribution.log_prob(torch.tensor(2.))])
        torch.testing.assert_close(actual, expected)
        with self.assertRaises(ValueError):
            hurdle_log_prob(params, torch.tensor([0., -1.]))

    def test_training_magnitude_path_exactly_matches_prefix_only_forward(self):
        model = FutureGrowthModel()
        x = torch.randn(3, 3, 500)
        full, states = model.forward_with_states(x)
        for t in (1, 3, 5):
            exact = model(x[:, :, :100 * t])[t]
            torch.testing.assert_close(full[t], exact, atol=0, rtol=0)
            self.assertEqual(states[t].shape, (3, 128))
        modified = x.clone()
        modified[:, :, 100:] = 1e4
        torch.testing.assert_close(model(x)[1], model(modified)[1], atol=0, rtol=0)
        self.assertEqual(set(model(x[:, :, :100])), {1})

    def test_all_controls_allocate_same_parameters_and_magnitude_initialization(self):
        states, sizes = [], []
        for _ in CONTROLS:
            torch.manual_seed(11)
            model = FutureGrowthModel()
            states.append(model.backbone.state_dict())
            sizes.append(sum(p.numel() for p in model.parameters()))
        self.assertEqual(len(set(sizes)), 1)
        for state in states[1:]:
            for k in state:
                torch.testing.assert_close(state[k], states[0][k], atol=0, rtol=0)

    def test_supervised_and_detached_have_identical_two_step_backbone_updates(self):
        a = FutureGrowthModel()
        b = copy.deepcopy(a)
        optimizers = [torch.optim.AdamW(m.parameters(), lr=3e-4, weight_decay=1e-4) for m in (a, b)]
        x, y, weights = torch.randn(3, 3, 100), torch.tensor([1.2, 2.3, 4.5]), torch.tensor([.4, .8, 1.8])
        labels, centers = (y / .1 + 1e-5).floor().long(), (torch.arange(66) + .5) * .1
        growth = torch.tensor([[0., .2, .1], [10., 1., 0.], [.03, .02, .01]])
        valid = torch.ones(3, 3, dtype=torch.bool)
        for _ in range(2):
            for model, optimizer, control in zip((a, b), optimizers, ("supervised", "conditional_detached")):
                logits, states = model.forward_with_states(x)
                base = supervised_loss(logits, y, weights, centers, "weighted")
                extra, _ = auxiliary_loss(model, logits, states, labels, weights, growth, valid, control,
                                          auxiliary_weight=100.)
                optimizer.zero_grad(set_to_none=True)
                (base + extra).backward()
                clip_gradients(model)
                optimizer.step()
            for pa, pb in zip(a.backbone.parameters(), b.backbone.parameters()):
                torch.testing.assert_close(pa, pb, atol=0, rtol=0)

    def test_missing_growth_masks_and_inverse_weights_are_applied_once(self):
        model = FutureGrowthModel()
        x = torch.randn(2, 3, 100)
        outputs, states = model.forward_with_states(x)
        labels, weights = torch.tensor([3, 45]), torch.tensor([.5, 1.5])
        g = torch.tensor([[.4, 0., 0.], [float("nan"), 0., 0.]])
        mask = torch.tensor([[True, False, False], [False, False, False]])
        actual, _ = auxiliary_loss(model, outputs, states, labels, weights, g, mask, "conditional_nll",
                                    auxiliary_weight=1.)
        expected = -hurdle_log_prob(model.growth_parameters(states[1][:1], labels[:1]), g[:1, 0])[0] * .5 / 2
        torch.testing.assert_close(actual, expected)
        actual.backward()
        self.assertTrue(all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters()))

    def test_stopq_marginal_updates_logits_without_direct_auxiliary_gradient(self):
        model = FutureGrowthModel()
        logits = torch.randn(2, 66, requires_grad=True)
        states = {1: torch.randn(2, 128, requires_grad=True)}
        loss, _ = auxiliary_loss(model, {1: logits}, states, torch.tensor([1, 44]), torch.ones(2),
                                  torch.ones(2, 3), torch.ones(2, 3, dtype=torch.bool),
                                  "conditional_marginal_stopq", auxiliary_weight=0., marginal_weight=1.)
        loss.backward()
        self.assertGreater(logits.grad.abs().sum().item(), 0)
        self.assertEqual(states[1].grad.abs().sum().item(), 0)
        for parameter in model.growth_head.parameters():
            self.assertEqual(parameter.grad.abs().sum().item(), 0)


class GrowthExportTests(unittest.TestCase):
    def test_numeric_event_sampling_matches_original_baseline_group_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            frame = pd.DataFrame({"source_id": np.repeat([2, 10, 100], 9),
                                  "source_magnitude": np.repeat([1., 2., 3.], 9),
                                  "trace_name": [f"t{i}" for i in range(27)],
                                  "trace_P_arrival_sample": np.full(27, 100)})
            path = root / "train_full_metadata.csv"
            frame.to_csv(path, index=False)
            audit = {"train": {"metadata_sha256": sha256(path)}}
            read = read_metadata(root, "train", audit)
            baseline = pd.read_csv(path, usecols=["source_id", "source_magnitude"])
            np.testing.assert_array_equal(selected_rows(read, 2), choose_rows(baseline, 2))
            as_strings = baseline.copy()
            as_strings["source_id"] = as_strings.source_id.astype(str)
            self.assertFalse(np.array_equal(choose_rows(as_strings, 2), choose_rows(baseline, 2)))

    def fixture(self, directory):
        root = Path(directory)
        (root / "results/2026-10-09").mkdir(parents=True)
        data = root / "data"
        data.mkdir()
        train = pd.DataFrame({"source_id": ["a", "a", "b"], "source_magnitude": [2., 2., 4.2],
                              "trace_name": ["t0", "t1", "t2"], "trace_P_arrival_sample": [100, 50, 100]})
        val = pd.DataFrame({"source_id": ["c"], "source_magnitude": [3.],
                            "trace_name": ["v0"], "trace_P_arrival_sample": [100]})
        train.to_csv(root / "train_full_metadata.csv", index=False)
        val.to_csv(root / "val_metadata.csv", index=False)
        np.save(root / "train_mean_full.npy", np.zeros(3, dtype=np.float32))
        np.save(root / "train_std_full.npy", np.ones(3, dtype=np.float32))
        waves = []
        with h5py.File(data / "Instance_events_counts.hdf5", "w") as raw:
            for i, row in train.iterrows():
                n = 1100 if i < 2 else 700  # Last row lacks the full future horizon.
                a = np.zeros((3, n), dtype=np.float32)
                p = int(row.trace_P_arrival_sample)
                a[2, p:] = np.linspace(1, 5, n - p)
                raw.create_dataset("data/" + row.trace_name, data=a)
                waves.append(a[:, p:p + 500])
            # No validation raw trace exists: the exporter must never request it.
        with h5py.File(data / "Instance_windows_5s.hdf5", "w") as cache:
            cache.create_dataset("train/waveforms", data=np.stack(waves))
            cache.create_dataset("train/targets", data=train.source_magnitude.to_numpy())
            cache.create_dataset("val/waveforms", data=np.zeros((1, 3, 500), dtype=np.float32))
            cache.create_dataset("val/targets", data=val.source_magnitude.to_numpy())
        audit = {split: {"metadata_sha256": sha256(root / name)} for split, name in
                 (("train", "train_full_metadata.csv"), ("val", "val_metadata.csv"))}
        audit["windows"] = {"5": {"cache": "Instance_windows_5s.hdf5", "preprocessing": "training_global_standardization"}}
        audit["normalization_sha256"] = {name: sha256(root / name) for name in ("train_mean_full.npy", "train_std_full.npy")}
        (root / "results/2026-10-09/audit.json").write_text(json.dumps(audit))
        np.savez(root / "results/2026-10-09/validation_5s.npz", targets=np.array([3.]),
                 event_ids=np.array(["c"]), trace_names=np.array(["v0"]), centers=(np.arange(66) + .5) * .1)
        return root, data, train, audit

    def test_export_alignment_missing_masks_and_train_only_loader(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as d:
            root, data, frame, audit = self.fixture(d)
            output = root / "targets.npz"
            manifest = export_targets(root, data, output)
            self.assertEqual(manifest["reasons"], {"ok": 1, "missing_pre_p": 1, "missing_future": 1})
            self.assertEqual(manifest["aligned_raw_cache_records"], 3)
            growth, valid, _ = load_targets(output, frame, np.arange(3), audit["train"]["metadata_sha256"])
            self.assertTrue(valid[0].all())
            self.assertFalse(valid[1:].any())
            self.assertTrue((growth >= 0).all())
            args = Namespace(root=str(root), data=str(data), targets=str(output), max_per_event=0,
                             allow_smoke_targets=False)
            result = load_training_data(args, torch.device("cpu"))
            self.assertEqual(result[0]["train"].shape, (3, 3, 500))
            self.assertEqual(result[0]["val"].shape, (1, 3, 500))
            with self.assertRaises(FileExistsError):
                export_targets(root, data, output)

    def test_same_magnitude_trace_swap_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root, data, frame, audit = self.fixture(d)
            with h5py.File(data / "Instance_windows_5s.hdf5", "r+") as cache:
                a, b = cache["train/waveforms"][0], cache["train/waveforms"][1]
                cache["train/waveforms"][0], cache["train/waveforms"][1] = b, a
            with self.assertRaisesRegex(ValueError, "Exact raw/cache"):
                export_targets(root, data, root / "targets.npz")

    def test_split_overlap_is_caught_when_csv_event_id_types_differ(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as d:
            root, data, frame, audit = self.fixture(d)
            frame["source_id"] = [2, 2, 10]
            frame.to_csv(root / "train_full_metadata.csv", index=False)
            val = pd.DataFrame({"source_id": ["2", "x"], "source_magnitude": [2., 3.],
                                "trace_name": ["v0", "v1"], "trace_P_arrival_sample": [100, 100]})
            val.to_csv(root / "val_metadata.csv", index=False)
            for split, name in (("train", "train_full_metadata.csv"), ("val", "val_metadata.csv")):
                audit[split]["metadata_sha256"] = sha256(root / name)
            (root / "results/2026-10-09/audit.json").write_text(json.dumps(audit))
            args = Namespace(root=str(root), data=str(data), targets=str(root / "unused.npz"),
                             max_per_event=0, allow_smoke_targets=False)
            # Must fail the overlap guard before trying to open a target file.
            with self.assertRaisesRegex(ValueError, "overlap in source_id"):
                load_training_data(args, torch.device("cpu"))

    def test_archive_digest_and_identity_detect_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root, data, frame, audit = self.fixture(d)
            path = root / "targets.npz"
            export_targets(root, data, path)
            with np.load(path, allow_pickle=False) as a:
                values = {k: a[k] for k in a.files}
            values["growth"][0, 0] += 1
            np.savez(root / "changed.npz", **values)
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                load_targets(root / "changed.npz", frame, np.arange(3), audit["train"]["metadata_sha256"])
            # Even a refreshed digest cannot bypass exact metadata row identities.
            manifest = json.loads(str(values["manifest_json"]))
            values["trace_names"] = values["trace_names"][::-1]
            manifest["arrays_sha256"] = {k: array_digest(v) for k, v in values.items() if k != "manifest_json"}
            values["manifest_json"] = np.array(json.dumps(manifest))
            np.savez(root / "swapped.npz", **values)
            with self.assertRaisesRegex(ValueError, "trace_names.*order"):
                load_targets(root / "swapped.npz", frame, np.arange(3), audit["train"]["metadata_sha256"])

    def test_sample_limited_exports_require_explicit_smoke_scope(self):
        with tempfile.TemporaryDirectory() as d:
            root, data, frame, audit = self.fixture(d)
            path = root / "small.npz"
            export_targets(root, data, path, sample_limit=1)
            with self.assertRaisesRegex(ValueError, "allow-smoke"):
                load_targets(path, frame, np.array([0]), audit["train"]["metadata_sha256"])
            load_targets(path, frame, np.array([0]), audit["train"]["metadata_sha256"], allow_smoke=True)
            with self.assertRaisesRegex(ValueError, "cover every"):
                load_targets(path, frame, np.arange(3), audit["train"]["metadata_sha256"], allow_smoke=True)

    def test_full_cpu_runner_uses_fixture_prefixes_and_writes_fixed_final_artifacts(self):
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as d:
            root, data, _, _ = self.fixture(d)
            path = root / "targets.npz"
            export_targets(root, data, path)
            args = Namespace(command="train", root=str(root), data=str(data), targets=str(path),
                             control="conditional_nll", epochs=1, seed=20261009, batch_size=2,
                             max_per_event=0, auxiliary_weight=.05, marginal_weight=.01,
                             device="cpu", allow_smoke_targets=False)
            train(args)
            runs = list((root / "results/2026-10-09/phase2").glob("growth_conditional_nll_*"))
            self.assertEqual(len(runs), 1)
            report = json.loads((runs[0] / "run.json").read_text())
            self.assertEqual(report["train_records"], 3)
            self.assertEqual(report["valid_growth_records"], [1, 1, 1])
            self.assertEqual(report["epochs"], 1)
            self.assertTrue((runs[0] / "model.pth").exists())
            with np.load(runs[0] / "predictions.npz", allow_pickle=False) as predictions:
                self.assertEqual(set(k for k in predictions.files if k.startswith("mean_")),
                                 {"mean_1s", "mean_3s", "mean_5s"})
                self.assertFalse(any("growth" in k for k in predictions.files))


if __name__ == "__main__":
    unittest.main()

"""Focused split, data-isolation, proper-score and recovery tests."""

import json
import copy
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import h5py
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "research/2026-10-09/phase3"))
from train_team_lm import (
    EventDataset, StationDataset, atomic_save, collate_events, file_sha256,
    gaussian_mixture_crps, id_digest, load_verified_metadata, mixture_quantile,
    point_metrics, resampling_indices, split_original_train, training_cutoffs,
    author_station_blinding, main, make_plateau_scheduler, smooth_training_magnitudes,
    step_calibration_scheduler,
)
import train_team_lm
from training_artifacts import EPOCH_SCHEMA, atomic_json_save, load_encoder_artifact, load_epoch_recovery, station_membership
from team_lm import StationEncoder


def fixture(directory, samples=1000):
    path = Path(directory) / "fixture.hdf5"
    ids = [f"event_{i:02}" for i in range(14)]
    frame = pd.DataFrame({"EVENT": ids, "MA": [2.] * 6 + [4.2, 4.3, 5.1, 5.2, 5.8, 5.9, 3., 6.],
        "TIME": np.arange(14, dtype=float),
        "source_row_index": np.arange(14), "benchmark_split": ["train"] * 12 + ["dev"] * 2})
    with h5py.File(path, "w") as handle:
        handle.create_group("metadata")
        handle["metadata"].create_dataset("native_SPLIT_descriptive_only", data=["TEST"] * 14, dtype=h5py.string_dtype())
        handle.attrs["schema"] = "chile-team-prefix-v1"
        handle.attrs["stored_samples"] = samples
        handle["metadata"].create_dataset("sampling_rate", data=100)
        handle["metadata"].create_dataset("time_before", data=5)
        handle["metadata"].create_dataset("time_after", data=samples // 100 - 5)
        split_group = handle.create_group("splits")
        for split in ("train", "dev"):
            selected = frame[frame.benchmark_split == split]
            split_group.create_dataset(split + "_event_ids", data=selected.EVENT.to_list(), dtype=h5py.string_dtype())
            split_group.create_dataset(split + "_source_rows", data=selected.source_row_index)
        groups = handle.create_group("data")
        for index, event in enumerate(ids):
            group = groups.create_group(event)
            count = index % 3 + 1
            values = np.arange(count * samples * 3, dtype=np.float32).reshape(count, samples, 3) * 1e-6
            group.create_dataset("waveforms", data=values)
            group.create_dataset("coords", data=np.tile([-21., -69., -.2], (count, 1)))
            group.create_dataset("stations", data=[f"station_{j}" for j in range(count)], dtype=h5py.string_dtype())
    manifest = {"schema": "chile-team-prefix-v1", "source_test_waveforms_read": False,
                "all_event_readback_verified": True, "sha256": file_sha256(path),
                "source_sha256": "source-identity", "source_rows": 20, "cache_rows": 14,
                "stored_samples": samples, "author_split_boundaries": [12, 14],
                "splits": {split: {"ids_sha256": id_digest(frame[frame.benchmark_split == split].EVENT)}
                           for split in ("train", "dev")}}
    path.with_suffix(".hdf5.manifest.json").write_text(json.dumps(manifest))
    metadata_path = Path(str(path) + ".metadata.csv")
    frame.to_csv(metadata_path, index=False)
    Path(str(metadata_path) + ".manifest.json").write_text(json.dumps({
        "sha256": file_sha256(metadata_path), "cache_sha256": manifest["sha256"],
        "rows": len(frame), "columns": frame.columns.tolist(), "origin": "metadata/event_metadata"}))
    return path, frame, manifest


class TeamTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2)

    def test_verifies_export_and_ignores_unrelated_native_split_column(self):
        for samples in (1000, 3000):
            with tempfile.TemporaryDirectory() as directory:
                path, expected, _ = fixture(directory, samples)
                actual, manifest = load_verified_metadata(path)
                pd.testing.assert_frame_equal(actual, expected)
                self.assertEqual(manifest["stored_samples"], samples)
                with path.open("ab") as handle:
                    handle.write(b"changed")
                with self.assertRaises(ValueError):
                    load_verified_metadata(path)

    def test_rejects_changed_or_cross_cache_metadata_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = fixture(directory)
            side_manifest = Path(str(path) + ".metadata.csv.manifest.json")
            payload = json.loads(side_manifest.read_text())
            payload["cache_sha256"] = "different-cache"
            side_manifest.write_text(json.dumps(payload))
            with self.assertRaises(ValueError):
                load_verified_metadata(path)

    def test_calibration_is_event_heldout_within_original_train_and_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            _, frame, _ = fixture(directory)
            first = split_original_train(frame, .1, 42)
            second = split_original_train(frame, .1, 42)
            for key in first:
                np.testing.assert_array_equal(first[key], second[key])
            self.assertFalse(set(first["fit"]) & set(first["calibration"]))
            self.assertEqual(set(first["fit"]) | set(first["calibration"]), set(range(12)))
            self.assertEqual(set(first["dev"]), {12, 13})
            self.assertTrue((frame.MA.iloc[first["calibration"]] >= 5.5).any())
            # DEV magnitudes cannot change the training/calibration split.
            frame.loc[frame.benchmark_split == "dev", "MA"] = 9.
            changed = split_original_train(frame, .1, 42)
            np.testing.assert_array_equal(first["calibration"], changed["calibration"])

    def test_dataset_augmentation_is_deterministic_train_only_and_shape_aware(self):
        with tempfile.TemporaryDirectory() as directory:
            path, frame, _ = fixture(directory, 3000)
            training = EventDataset(path, frame.iloc[:12], training=True, stored_samples=3000, station_drop=.9)
            first, second = training[2], training[2]
            torch.testing.assert_close(first["waveforms"], second["waveforms"])
            self.assertGreaterEqual(len(first["waveforms"]), 1)
            evaluation = EventDataset(path, frame.iloc[12:], stored_samples=3000)
            batch = collate_events([evaluation[0], evaluation[1]])
            self.assertEqual(batch[0].shape, (2, 2, 3000, 3))
            self.assertEqual(batch[2].sum().item(), 3)
            stations = StationDataset(training)
            self.assertEqual(len(stations), 24)
            self.assertEqual(stations[0][0].shape, (3000, 3))
            with self.assertRaises(ValueError):
                EventDataset(path, frame.iloc[12:], training=True)
            with self.assertRaises(ValueError):
                EventDataset(path, frame.iloc[12:], station_drop=.2)
            training.close()
            evaluation.close()

    def test_author_magnitude_resampling_boundaries_are_exact(self):
        magnitudes = np.array([4., 4.1, 5., 5.1, 6., 8.1])
        counts = np.bincount(resampling_indices(magnitudes, 2), minlength=len(magnitudes))
        np.testing.assert_array_equal(counts, [1, 8, 8, 16, 16, 128])
        np.testing.assert_array_equal(resampling_indices(magnitudes, 1), np.arange(6))

    def test_author_blinding_draws_uniform_retained_count_and_masks_unavailable(self):
        torch.manual_seed(17)
        # Four active stations plus one unavailable station; count must be 1..4.
        x = torch.randn(2000, 5, 1000, 3)
        coords = torch.ones(2000, 5, 3)
        mask = torch.ones(2000, 5, dtype=torch.bool)
        mask[:, -1] = False
        retained = author_station_blinding(x, coords, mask, 1.)
        self.assertFalse(retained[:, -1].any())
        counts = torch.bincount(retained.sum(-1), minlength=5)
        self.assertEqual(counts[0], 0)
        self.assertTrue(((counts[1:] - 500).abs() < 100).all())
        torch.testing.assert_close(author_station_blinding(x, coords, mask, 1., training=False), mask)
        self.assertFalse(author_station_blinding(x[:2], coords[:2], torch.zeros_like(mask[:2]), 1.).any())

    def test_author_blinding_ignores_future_and_preserves_inputs(self):
        x = torch.randn(8, 4, 1000, 3)
        coords, mask = torch.ones(8, 4, 3), torch.ones(8, 4, dtype=torch.bool)
        altered = x.clone()
        altered[:, :, 600:] = float("nan")
        torch.manual_seed(9)
        first = author_station_blinding(x, coords, mask, 1.)
        torch.manual_seed(9)
        second = author_station_blinding(altered, coords, mask, 1.)
        torch.testing.assert_close(first, second)
        self.assertTrue(mask.all())

    def test_magnitude_smoothing_has_source_scale_and_never_changes_eval_labels(self):
        targets = torch.tensor([3., 4., 5., 6.]).repeat(4000)
        original = targets.clone()
        torch.manual_seed(3)
        smoothed = smooth_training_magnitudes(targets, enabled=True)
        torch.testing.assert_close(targets, original)
        torch.testing.assert_close(smoothed[targets <= 4], targets[targets <= 4])
        for magnitude, sigma in ((5, .05), (6, .1)):
            noise = smoothed[targets == magnitude] - magnitude
            self.assertAlmostEqual(float(noise.std()), sigma, delta=.004)
            self.assertAlmostEqual(float(noise.mean()), 0., delta=.004)
        torch.testing.assert_close(smooth_training_magnitudes(targets, enabled=True, training=False), original)
        torch.testing.assert_close(smooth_training_magnitudes(targets, enabled=False), original)

    def test_scheduler_uses_only_calibration_and_source_plateau_patience(self):
        for stage, patience in (("pretrain", 4), ("event", 6)):
            optimizer = torch.optim.Adam([torch.nn.Parameter(torch.ones(1))], lr=1e-4)
            scheduler = make_plateau_scheduler(optimizer, "author-plateau", stage)
            metrics = {str(t): {"proper_nll": 2.} for t in (1, 3, 5)}
            with self.assertRaises(ValueError):
                step_calibration_scheduler(scheduler, metrics, split="dev")
            step_calibration_scheduler(scheduler, metrics, split="calibration")
            for _ in range(patience - 1):
                step_calibration_scheduler(scheduler, metrics, split="calibration")
                self.assertAlmostEqual(optimizer.param_groups[0]["lr"], 1e-4)
            step_calibration_scheduler(scheduler, metrics, split="calibration")
            self.assertAlmostEqual(optimizer.param_groups[0]["lr"], 3e-5)

    def test_station_calibration_cannot_read_dev_or_use_fitting_augmentation(self):
        with tempfile.TemporaryDirectory() as directory:
            path, frame, _ = fixture(directory)
            calibration = EventDataset(path, frame.iloc[6:8])
            self.assertGreater(len(StationDataset(calibration, calibration=True)), 0)
            with self.assertRaises(ValueError):
                StationDataset(calibration)
            with self.assertRaises(ValueError):
                StationDataset(EventDataset(path, frame.iloc[12:]), calibration=True)
            with self.assertRaises(ValueError):
                StationDataset(EventDataset(path, frame.iloc[:2], training=True), calibration=True)
            calibration.close()

    def test_train_only_pilot_never_fetches_dev_and_preserves_scheduler_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = fixture(directory)
            original_get = EventDataset.__getitem__
            def guarded_get(dataset, index):
                if dataset.frame.iloc[index].benchmark_split == "dev":
                    raise AssertionError("A TRAIN-only pilot fetched DEV waveforms")
                return original_get(dataset, index)
            args = ["train_team_lm", "--cache", str(path), "--aggregation", "pool", "--epochs", "1",
                    "--pretrain-epochs", "1", "--batch-size", "2", "--pretrain-batch-size", "2",
                    "--limit-fit-events", "2", "--magnitude-resampling", "1", "--skip-dev",
                    "--station-blinding", "author", "--event-label-smoothing",
                    "--lr-schedule", "author-plateau", "--selection", "calibration-nll", "--output", directory]
            with patch.object(sys, "argv", args), patch.object(EventDataset, "__getitem__", guarded_get), patch("torch.cuda.is_available", return_value=False):
                main()
            output, = Path(directory).glob("team_pool_*")
            run = json.loads((output / "run.json").read_text())
            self.assertFalse(run["dev_evaluated"])
            self.assertFalse((output / "dev_metrics.json").exists())
            self.assertFalse((output / "dev_predictions.npz").exists())
            saved = torch.load(output / "latest.pth", weights_only=True)
            self.assertIsNotNone(saved["scheduler"])
            self.assertEqual(saved["completed_epoch"], 1)
            encoder_path = output / "pretrained_encoder.pth"
            identity = run["pretraining_identity"]
            weights, provenance = load_encoder_artifact(encoder_path, identity, file_sha256=file_sha256)
            self.assertEqual(provenance["sha256"], file_sha256(encoder_path))
            expected = torch.load(encoder_path, weights_only=True)["encoder"]
            for key, tensor in weights.items():
                torch.testing.assert_close(tensor, expected[key], rtol=0, atol=0)
            imported_args = args.copy()
            imported_args[imported_args.index("--aggregation") + 1] = "transformer"
            imported_args.extend(["--pretrained-encoder", str(encoder_path)])
            with patch.object(sys, "argv", imported_args), patch.object(EventDataset, "__getitem__", guarded_get), patch("torch.cuda.is_available", return_value=False):
                main()
            imported_dir, = Path(directory).glob("team_transformer_*")
            imported = json.loads((imported_dir / "run.json").read_text())
            self.assertEqual(imported["imported_encoder"]["sha256"], provenance["sha256"])
            self.assertFalse((imported_dir / "pretrain_history.json").exists())
            for field, replacement in (("training_cutoff", "author"), ("epochs", 25),
                                       ("source_sha256", "other"), ("fit_ids_sha256", "other"),
                                       ("label_noise", "none"), ("implementation_sha256", "other"),
                                       ("partition", "dev"), ("test_used", True)):
                changed = copy.deepcopy(identity)
                changed[field] = replacement
                with self.assertRaises(ValueError):
                    load_encoder_artifact(encoder_path, changed, file_sha256=file_sha256)
            changed = copy.deepcopy(identity)
            changed["fit_stations"]["ordered_membership_sha256"] = "different-station-order"
            with self.assertRaises(ValueError):
                load_encoder_artifact(encoder_path, changed, file_sha256=file_sha256)

    def test_encoder_rejects_legacy_file_missing_manifest_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.pth"
            atomic_save({"encoder": StationEncoder().state_dict()}, path)
            with self.assertRaises(ValueError):
                load_encoder_artifact(path, {}, file_sha256=file_sha256)
            Path(str(path) + ".manifest.json").write_text(json.dumps({"schema": "team-station-encoder-v1", "sha256": "changed"}))
            with self.assertRaises(ValueError):
                load_encoder_artifact(path, {}, file_sha256=file_sha256)

    def test_station_membership_binds_ids_order_and_excludes_dev(self):
        with tempfile.TemporaryDirectory() as directory:
            path, frame, _ = fixture(directory)
            fit = EventDataset(path, frame.iloc[:4], training=True)
            original = station_membership(fit)
            self.assertEqual(original["records"], 7)
            with h5py.File(path, "r+") as handle:
                handle["data/event_01/stations"][0] = "different_station"
            changed = station_membership(fit)
            self.assertNotEqual(changed["ordered_membership_sha256"], original["ordered_membership_sha256"])
            with self.assertRaises(ValueError):
                station_membership(EventDataset(path, frame.iloc[12:]))

    def assert_nested_exact(self, actual, expected):
        if isinstance(expected, torch.Tensor):
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
        elif isinstance(expected, dict):
            self.assertEqual(set(actual), set(expected))
            for key in expected:
                self.assert_nested_exact(actual[key], expected[key])
        elif isinstance(expected, (tuple, list)):
            self.assertEqual(len(actual), len(expected))
            for left, right in zip(actual, expected):
                self.assert_nested_exact(left, right)
        else:
            self.assertEqual(actual, expected)

    def test_completed_epoch_resume_matches_uninterrupted_cpu_tensors_and_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = fixture(directory)
            root = Path(directory)
            args = ["train_team_lm", "--cache", str(path), "--aggregation", "pool", "--epochs", "2",
                    "--pretrain-epochs", "2", "--batch-size", "2", "--pretrain-batch-size", "2",
                    "--limit-fit-events", "4", "--magnitude-resampling", "1", "--skip-dev",
                    "--station-blinding", "author", "--event-label-smoothing",
                    "--lr-schedule", "author-plateau", "--selection", "calibration-nll"]
            with patch.object(sys, "argv", args + ["--output", str(root / "continuous")]), patch("torch.cuda.is_available", return_value=False):
                main()
            continuous, = (root / "continuous").glob("team_pool_*")
            expected = torch.load(continuous / "latest.pth", weights_only=True)
            selected = torch.load(continuous / "model.pth", weights_only=True)["model"]
            real_save = atomic_save
            for stage, epoch in (("pretrain", 1), ("pretrain", 2), ("event", 1), ("event", 2)):
                with self.subTest(stage=stage, epoch=epoch):
                    def interrupted_save(value, destination):
                        real_save(value, destination)
                        if value.get("schema") == EPOCH_SCHEMA and value.get("stage") == stage and value.get("completed_epoch") == epoch:
                            raise InterruptedError("Simulated interruption after complete atomic epoch save")
                    output = root / f"resume_{stage}_{epoch}"
                    argv = args + ["--output", str(output)]
                    with patch.object(sys, "argv", argv), patch.object(train_team_lm, "atomic_save", interrupted_save), patch("torch.cuda.is_available", return_value=False):
                        with self.assertRaises(InterruptedError):
                            main()
                    run, = output.glob("team_pool_*")
                    # A failed control-metadata write may leave a partial temp
                    # file, but must not publish a broken completion marker or
                    # audit JSON that prevents recovery from the intact epoch.
                    for control in ("resume_history.json", "run.json"):
                        with self.assertRaises(TypeError):
                            atomic_json_save({"incomplete": object()}, run / control)
                        self.assertFalse((run / control).exists())
                    saved = torch.load(run / "latest.pth", weights_only=True)
                    config = saved["config"]
                    memberships = json.loads((run / "split_manifest.json").read_text())
                    changed = copy.deepcopy(config)
                    changed["epochs"] += 1
                    with self.assertRaises(ValueError):
                        load_epoch_recovery(run / "latest.pth", changed, memberships)
                    with patch.object(sys, "argv", argv + ["--resume", str(run / "latest.pth")]), patch("torch.cuda.is_available", return_value=False):
                        main()
                    actual = torch.load(run / "latest.pth", weights_only=True)
                    for key in ("model", "optimizer", "scheduler", "torch_rng", "cuda_rng", "numpy_rng", "python_rng", "selection"):
                        self.assert_nested_exact(actual[key], expected[key])
                    self.assert_nested_exact(torch.load(run / "model.pth", weights_only=True)["model"], selected)
                    self.assert_nested_exact(actual["run_state"]["best_model"], expected["run_state"]["best_model"])
                    self.assertEqual(len(json.loads((run / "history.json").read_text())), 2)
                    self.assertEqual(len(json.loads((run / "pretrain_history.json").read_text())), 2)
                    self.assertEqual(len(json.loads((run / "resume_history.json").read_text())), 1)
                    with self.assertRaises(ValueError):
                        load_epoch_recovery(run / "latest.pth", config, memberships)

    def test_epoch_recovery_rejects_legacy_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.pth"
            atomic_save({"model": {}, "completed_epoch": 1}, path)
            with self.assertRaises(ValueError):
                load_epoch_recovery(path, {}, {})

    def test_atomic_control_metadata_failure_preserves_previous_complete_json(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("run.json", "resume_history.json"):
                path = Path(directory) / name
                atomic_json_save({"complete": 1}, path)
                with self.assertRaises(TypeError):
                    atomic_json_save({"incomplete": object()}, path)
                self.assertEqual(json.loads(path.read_text()), {"complete": 1})
                with patch("training_artifacts.os.replace", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        atomic_json_save({"complete": 2}, path)
                self.assertEqual(json.loads(path.read_text()), {"complete": 1})
                atomic_json_save({"complete": 3}, path)
                self.assertEqual(json.loads(path.read_text()), {"complete": 3})

    def test_gaussian_crps_and_quantiles_match_closed_form_standard_normal(self):
        mixture = {"means": torch.zeros(3, 1, dtype=torch.float64),
                   "scales": torch.ones(3, 1, dtype=torch.float64),
                   "weights": torch.ones(3, 1, dtype=torch.float64)}
        targets = torch.tensor([0., 1., -1.], dtype=torch.float64)
        actual = gaussian_mixture_crps(mixture, targets)
        z = targets
        expected = z * torch.erf(z / math.sqrt(2)) + math.sqrt(2 / math.pi) * torch.exp(-.5 * z*z) - 1 / math.sqrt(math.pi)
        torch.testing.assert_close(actual, expected)
        torch.testing.assert_close(mixture_quantile(mixture, .5), torch.zeros(3, dtype=torch.float64), atol=1e-10, rtol=0)
        torch.testing.assert_close(mixture_quantile(mixture, .95), torch.full((3,), 1.6448536269514722, dtype=torch.float64), atol=1e-9, rtol=0)

    def test_cvar_and_rare_event_metrics_have_correct_support(self):
        actual = point_metrics(np.array([2., 3., 6.]), np.array([2.1, 2.9, 4.]))
        self.assertAlmostEqual(actual["cvar95"], 2.)
        self.assertEqual(actual["m5.5_events"], 1)
        self.assertAlmostEqual(actual["m5.5_mae"], 2.)
        self.assertIsNone(actual["m7_mae"])

    def test_training_cutoffs_stay_within_each_cache_protocol(self):
        for schedule, upper in (("uniform-early", 1000), ("author", 3000)):
            cutoffs = training_cutoffs(10000, "cpu", schedule)
            samples = ((cutoffs + 5) * 100).floor()
            self.assertGreaterEqual(samples.min().item(), 100)
            self.assertLess(samples.max().item(), upper)
        self.assertTrue(set(training_cutoffs(100, "cpu", "discrete").tolist()).issubset({1., 3., 5.}))

    def test_atomic_checkpoint_replaces_complete_file_without_leftover_temp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.pth"
            atomic_save({"epoch": 1, "state": torch.ones(2)}, path)
            atomic_save({"epoch": 2, "state": torch.zeros(2)}, path)
            actual = torch.load(path, weights_only=True)
            self.assertEqual(actual["epoch"], 2)
            self.assertFalse(path.with_name("latest.pth.tmp").exists())


if __name__ == "__main__":
    unittest.main()

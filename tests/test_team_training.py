"""Focused split, data-isolation, proper-score and recovery tests."""

import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

import h5py
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / "research/2026-10-09/phase3"))
from train_team_lm import (
    EventDataset, StationDataset, atomic_save, collate_events, file_sha256,
    gaussian_mixture_crps, id_digest, load_verified_metadata, mixture_quantile,
    point_metrics, resampling_indices, split_original_train, training_cutoffs,
)


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

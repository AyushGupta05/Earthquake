"""Focused export tests: benchmark membership, sealed suffix/test, data fidelity."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import h5py
import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "research/2026-10-09/phase3"))
from export_chile_prefix import chronological_boundaries, export_prefix_cache, sha256_file


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.hdf5"
        self.output = self.root / "prefix.hdf5"
        self.metadata = pd.DataFrame({
            "EVENT": [f"event_{i}" for i in range(10)], "MA": np.arange(10) / 2 + 1,
            "TIME": np.arange(10), "SPLIT": ["TEST"] * 7 + ["TRAIN"] * 3,
        }, index=[0] * 10)  # Official source also has a non-unique pandas index.
        self.metadata.to_hdf(self.source, key="metadata/event_metadata", format="table")
        with h5py.File(self.source, "a") as f:
            for key, value in {"sampling_rate": 100, "time_before": 5, "time_after": 25}.items():
                f["metadata"].create_dataset(key, data=value)
            data = f.create_group("data")
            for i in range(10):
                g = data.create_group(f"event_{i}")
                wave = np.arange(2 * 3000 * 3, dtype=np.float64).reshape(2, 3000, 3) * 1e-11 + i * 1e-8
                wave[:, 1000:] = np.nan  # Must never be inspected or exported.
                if i >= 7:
                    wave[:] = np.nan  # TEST waveforms must never be inspected either.
                g.create_dataset("waveforms", data=wave)
                g.create_dataset("coords", data=[[-20, -70, -1.2], [-21, -69, -0.3]])
                g.create_dataset("stations", data=np.asarray([b"ABC", b"DEF"]))
                g.attrs["retained"] = "event attribute"

    def tearDown(self):
        self.temp.cleanup()

    def test_author_boundaries(self):
        self.assertEqual(chronological_boundaries(96133), (57679, 67293))
        self.assertEqual(chronological_boundaries(10), (6, 7))

    def test_train_dev_exact_copy_with_no_future_or_test_values(self):
        result = export_prefix_cache(self.source, self.output, "fixture-sha")
        self.assertEqual(result["records"], 14)
        self.assertEqual(result["splits"]["train"]["events"], 6)
        self.assertEqual(result["splits"]["dev"]["events"], 1)
        self.assertTrue(result["all_event_readback_verified"])
        self.assertFalse(result["source_test_waveforms_read"])
        self.assertEqual(result["sha256"], sha256_file(self.output))
        metadata = pd.read_hdf(self.output, "metadata/event_metadata")
        self.assertEqual(metadata.benchmark_split.tolist(), ["train"] * 6 + ["dev"])
        self.assertEqual(metadata.SPLIT.tolist(), ["TEST"] * 7)  # Retained, but intentionally ignored.
        self.assertEqual(metadata.source_row_index.tolist(), list(range(7)))
        with h5py.File(self.source) as src, h5py.File(self.output) as dst:
            self.assertEqual(set(dst["data"]), {f"event_{i}" for i in range(7)})
            self.assertEqual(dst["metadata/time_after"][()], 5)
            self.assertEqual(dst.attrs["source_time_after_seconds"], 25)
            self.assertEqual(dst["splits/train_event_ids"].asstr()[()].tolist(), [f"event_{i}" for i in range(6)])
            for i in range(7):
                original, copy = src[f"data/event_{i}"], dst[f"data/event_{i}"]
                self.assertEqual(copy["waveforms"].shape, (2, 1000, 3))
                self.assertEqual(copy["waveforms"].dtype, np.dtype("float32"))
                np.testing.assert_array_equal(copy["waveforms"][()], original["waveforms"][:, :1000, :].astype(np.float32))
                for key in ["stations", "coords"]:
                    np.testing.assert_array_equal(copy[key][()], original[key][()])
                self.assertEqual(copy.attrs["retained"], "event attribute")
                self.assertNotIn("p_picks", copy)

    def test_existing_output_and_partial_are_never_overwritten(self):
        self.output.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            export_prefix_cache(self.source, self.output, "fixture-sha")
        self.assertEqual(self.output.read_bytes(), b"keep")
        self.output.unlink()
        partial = self.output.with_name(self.output.name + ".partial")
        partial.write_bytes(b"also keep")
        with self.assertRaises(FileExistsError):
            export_prefix_cache(self.source, self.output, "fixture-sha")
        self.assertEqual(partial.read_bytes(), b"also keep")

    def test_full_train_dev_cache_keeps_25_second_training_data_but_no_test(self):
        with h5py.File(self.source, "a") as f:
            for i in range(7):
                f[f"data/event_{i}/waveforms"][:, 1000:] = 42 + i
        result = export_prefix_cache(self.source, self.output, "fixture-sha", samples=3000)
        self.assertEqual(result["stored_samples"], 3000)
        self.assertEqual(result["time_after_first_p_seconds"], 25)
        self.assertFalse(result["source_test_waveforms_read"])
        with h5py.File(self.source) as src, h5py.File(self.output) as dst:
            self.assertEqual(dst["metadata/time_after"][()], 25)
            self.assertEqual(set(dst["data"]), {f"event_{i}" for i in range(7)})
            for i in range(7):
                cached = dst[f"data/event_{i}/waveforms"]
                self.assertEqual(cached.shape, (2, 3000, 3))
                np.testing.assert_array_equal(cached[()], src[f"data/event_{i}/waveforms"][()].astype(np.float32))

    def test_unsupported_sample_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "1000 or 3000"):
            export_prefix_cache(self.source, self.output, "fixture-sha", samples=1200)
        self.assertFalse(self.output.exists())

    def test_size_limit_removes_only_new_partial(self):
        with self.assertRaisesRegex(RuntimeError, "byte cap"):
            export_prefix_cache(self.source, self.output, "fixture-sha", max_bytes=100)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".partial").exists())
        self.assertTrue(self.source.exists())

    def test_nonfinite_available_data_is_rejected(self):
        with h5py.File(self.source, "a") as f:
            f["data/event_0/waveforms"][0, 100, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "Non-finite"):
            export_prefix_cache(self.source, self.output, "fixture-sha")
        self.assertFalse(self.output.exists())

    def test_late_output_collision_preserves_other_writer(self):
        def concurrent_writer(path):
            digest = sha256_file(path)
            self.output.write_bytes(b"concurrent output")
            return digest
        with mock.patch("export_chile_prefix.sha256_file", side_effect=concurrent_writer):
            with self.assertRaises(FileExistsError):
                export_prefix_cache(self.source, self.output, "fixture-sha")
        self.assertEqual(self.output.read_bytes(), b"concurrent output")
        self.assertFalse(self.output.with_suffix(".hdf5.manifest.json").exists())

    def test_late_manifest_collision_rolls_back_only_our_output(self):
        manifest = self.output.with_suffix(".hdf5.manifest.json")
        def concurrent_writer(path):
            digest = sha256_file(path)
            manifest.write_bytes(b"concurrent manifest")
            return digest
        with mock.patch("export_chile_prefix.sha256_file", side_effect=concurrent_writer):
            with self.assertRaises(FileExistsError):
                export_prefix_cache(self.source, self.output, "fixture-sha")
        self.assertEqual(manifest.read_bytes(), b"concurrent manifest")
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".partial").exists())

    def test_manifest_staging_failure_leaves_no_published_output(self):
        original_open = Path.open
        def fail_manifest(path, *args, **kwargs):
            if path.name.endswith(".manifest.json.partial"):
                raise OSError("simulated full filesystem")
            return original_open(path, *args, **kwargs)
        with mock.patch.object(Path, "open", fail_manifest):
            with self.assertRaisesRegex(OSError, "full filesystem"):
                export_prefix_cache(self.source, self.output, "fixture-sha")
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".partial").exists())

    def test_duplicate_event_ids_are_rejected(self):
        self.metadata.iloc[1, self.metadata.columns.get_loc("EVENT")] = "event_0"
        self.metadata.to_hdf(self.source, key="metadata/event_metadata", format="table", mode="a")
        with self.assertRaisesRegex(ValueError, "unique"):
            export_prefix_cache(self.source, self.output, "fixture-sha")

    def test_non_chronological_metadata_is_rejected(self):
        self.metadata.iloc[0, self.metadata.columns.get_loc("TIME")] = 20
        self.metadata.to_hdf(self.source, key="metadata/event_metadata", format="table", mode="a")
        with self.assertRaisesRegex(ValueError, "chronological"):
            export_prefix_cache(self.source, self.output, "fixture-sha")


if __name__ == "__main__":
    unittest.main()

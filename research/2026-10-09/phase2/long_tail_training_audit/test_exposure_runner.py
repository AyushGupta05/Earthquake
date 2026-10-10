"""Synthetic-only production runner checks; no real source paths or data."""
import contextlib
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

import run_exposure_grid as runner
import exposure_training as training
from test_exposure import population, plans


def sleeper():
    time.sleep(20)


def marker(path):
    Path(path).write_text("finished")


def pid_sleeper(path):
    Path(path).write_text(str(os.getpid()))
    time.sleep(20)


def supervisor_for_signal_test(path):
    runner.run_guarded(pid_sleeper, (path,), 20, grace=.1)


def synthetic_metadata():
    parts = [population(n=12), population(n=6, subset="eval_seen", row_start=12),
             population(n=6, subset="eval_held", row_start=18)]
    n = sum(len(p.targets) for p in parts)
    source = np.concatenate([p.source_rows for p in parts]) * 7 + 100
    valid = np.ones((n, 3), dtype=bool)
    valid[0, 2] = False
    static = np.zeros((n, 34)); static[:, 0] = 1
    return dict(source_row_index=source,
        trace_name=np.array([f"synthetic-{i}" for i in source]),
        source_id=np.concatenate([p.events for p in parts]),
        station_group=np.concatenate([p.stations for p in parts]),
        subset=np.concatenate([np.repeat(p.subset, len(p.targets)) for p in parts]),
        sampling_weight=np.concatenate([p.weights for p in parts]),
        targets=np.concatenate([p.targets for p in parts]),
        valid=valid, invalid_codes=(~valid).astype(np.uint8), deadlines=np.array([1, 3, 5]),
        sensitivity=np.ones((n, 3)), static=static, response=np.zeros((n, 72)),
        native_units=np.repeat("m/s", n))


class RunnerTest(unittest.TestCase):
    def test_default_dry_run_does_not_open_sources_or_launch(self):
        args = ["--export-dir", "/missing/synthetic-export", "--response-source", "/missing/code",
                "--output", "/missing/output", "--max-seconds", "3600"]
        for name in ("export", "model", "data"):
            args += ["--" + name + "-sha256", "a" * 64]
        with patch.object(runner, "run_guarded", side_effect=AssertionError("Dispatched")), \
             patch.object(runner, "file_sha", side_effect=AssertionError("Read source")), \
             contextlib.redirect_stdout(io.StringIO()) as text:
            self.assertEqual(runner.main(args), 0)
        self.assertFalse(json.loads(text.getvalue())["execute"])

    def test_guard_finishes_or_terminates_the_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "marker"
            result = runner.run_guarded(marker, (str(path),), 5, grace=.1)
            self.assertFalse(result["timed_out"])
            self.assertEqual(result["exitcode"], 0)
            self.assertEqual(path.read_text(), "finished")
        result = runner.run_guarded(sleeper, (), 1, grace=.1)
        self.assertTrue(result["timed_out"])
        self.assertNotEqual(result["exitcode"], 0)
        self.assertLess(result["elapsed_seconds"], 5)
        for seconds in (0, -1, 43201):
            with self.assertRaises(ValueError):
                runner.run_guarded(sleeper, (), seconds)

    def test_panel_masks_fractions_units_and_family(self):
        m = synthetic_metadata()
        panels, strata, fractions, audit = runner.held_panels(SimpleNamespace(metadata=m))
        self.assertEqual(len(panels), 6)
        self.assertEqual(fractions[(1, "eval_seen")], 1.)
        self.assertAlmostEqual(fractions[(5, "eval_seen")], 11 / 12)
        np.testing.assert_array_equal(strata[(1, "eval_held")]["family"], ["HH"] * 6)
        np.testing.assert_array_equal(strata[(1, "eval_held")]["unit"], ["m/s"] * 6)
        self.assertEqual(len(audit), 6)
        m["static"][0, 1] = 1
        with self.assertRaisesRegex(ValueError, "one-hot"):
            runner.held_panels(SimpleNamespace(metadata=m))

    def test_supervisor_SIGTERM_reaps_training_child(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "child_pid"
            process = multiprocessing.get_context("spawn").Process(
                target=supervisor_for_signal_test, args=(str(path),))
            process.start()
            child = None
            try:
                deadline = time.monotonic() + 8
                while not path.is_file() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(path.is_file())
                child = int(path.read_text())
                process.terminate()
                process.join(5)
                self.assertFalse(process.is_alive())
                self.assertEqual(process.exitcode, 143)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child, 0)
            finally:
                if process.is_alive():
                    process.kill(); process.join()
                process.close()
                if child is not None:
                    try:
                        os.kill(child, 9)
                    except ProcessLookupError:
                        pass

    def test_fit_empty_bins_and_unsupported_held_targets_are_reported(self):
        m = synthetic_metadata()
        m["targets"][12] = .15  # Supported fine bin absent from fitting rows.
        m["targets"][13] = 7.2  # Retained continuous target outside the grid.
        panels, _, _, _ = runner.held_panels(SimpleNamespace(metadata=m))
        report = runner.fine_bin_support(plans((12, 12, 12)), panels)
        row = next(r for r in report if r["seconds"] == 1 and r["subset"] == "eval_seen")
        self.assertEqual(row["unsupported_held_records"], 1)
        self.assertEqual(row["held_occupied_fit_empty"][0]["label"], 1)

    def test_source_pins_precede_import_and_reject_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            for name in ("response_model.py", "response_data.py", "manifest.json"):
                (p / name).write_text("synthetic")
            digest = hashlib.sha256(b"synthetic").hexdigest()
            config = dict(response_source=str(p), export_dir=str(p), model_sha256=digest,
                          data_sha256=digest, export_sha256=digest)
            runner.verify_pins(config)
            (p / "response_model.py").write_text("changed")
            with self.assertRaisesRegex(ValueError, "Pinned"):
                runner.verify_pins(config)

    def test_atomic_artifacts_reject_object_arrays(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "arrays.npz"
            with self.assertRaisesRegex(ValueError, "Object arrays"):
                runner.atomic_npz(path, {"bad": np.array([{}], dtype=object)})
            self.assertFalse(path.exists())
            runner.atomic_npz(path, {"good": np.arange(3)})
            with np.load(path, allow_pickle=False) as data:
                np.testing.assert_array_equal(data["good"], np.arange(3))


class SharedProductionRunnerTest(unittest.TestCase):
    def test_complete_synthetic_grid_with_actual_B_and_archived_predictions(self):
        source = Path(__file__).resolve().parents[1] / "response_conditioned_encoder"
        if not (source / "response_model.py").is_file() or not (source / "response_data.py").is_file():
            self.skipTest("Shared code excluded from the isolated runner review")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); export = root / "export"; export.mkdir()
            output = root / "output"; output.mkdir()
            m = synthetic_metadata()
            np.save(export / "counts.npy", np.random.default_rng(19).normal(size=(len(m["targets"]), 3, 500)))
            np.savez(export / "metadata.npz", **m)
            runner.atomic_json(export / "manifest.json", {"status": "complete", "scope": "synthetic only",
                "outputs_sha256": {n: runner.file_sha(export / n) for n in ("counts.npy", "metadata.npz")}})
            runner.atomic_json(export / "COMPLETE.json", {"manifest_sha256": runner.file_sha(export / "manifest.json")})
            config = dict(export_dir=str(export), response_source=str(source), output=str(output),
                export_sha256=runner.file_sha(export / "manifest.json"),
                model_sha256=runner.file_sha(source / "response_model.py"),
                data_sha256=runner.file_sha(source / "response_data.py"), device="cpu", threads=1, max_seconds=120)
            with contextlib.redirect_stdout(io.StringIO()):
                runner.worker(config)
            completed = json.loads((output / "COMPLETE.json").read_text())
            self.assertEqual(completed["manifest_sha256"], runner.file_sha(output / "manifest.json"))
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "complete")
            for name, digest in manifest["outputs_sha256"].items():
                self.assertEqual(runner.file_sha(output / name), digest)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(len(report["scores"]), 54)
            self.assertEqual(len(report["comparisons"]), 12)
            self.assertEqual(report["gate"]["status"], "inconclusive_tail_sample")
            with np.load(output / "predictions.npz", allow_pickle=False) as data:
                predictions = [key for key in data.files if not key.startswith("panel__")]
                self.assertEqual(len(predictions), 36)
                for key in predictions:
                    np.testing.assert_allclose(data[key].sum(1), 1, atol=1e-14)
            for c in training.CONTROLS:
                for seed in training.SEEDS:
                    cfg = json.loads((output / f"{c}_seed{seed}" / "identity.json").read_text())
                    self.assertEqual(cfg["parameters"], 380706)
                    self.assertEqual(cfg["epochs"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)

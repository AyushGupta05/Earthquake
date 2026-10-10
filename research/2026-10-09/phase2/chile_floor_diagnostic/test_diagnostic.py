"""Invented fixtures only. Torch integration tests run in the existing CPU env."""
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import floor_math as fm
import guards as g
import run_diagnostic as runner


class MathTests(unittest.TestCase):
    def setUp(self):
        self.logits = np.array([[1., -2., 0., .2, 2.], [0., .5, 1., -1., 0.]])
        self.means = np.array([[1., 2., 3., 4., 5.], [2., 3., 4., 5., 6.]])
        self.scales = np.array([[.7, 1., 1.2, 2., .8], [1., .8, 1.4, .7, 1.1]])
        self.targets = np.array([2.4, 6.3])

    def calculate(self, logits=None, means=None, scales=None):
        return fm.diagnose(self.logits if logits is None else logits,
                           self.means if means is None else means,
                           self.scales if scales is None else scales, self.targets)

    def test_analytic_derivatives_all_three_scores(self):
        base = self.calculate()
        for parameter, source in (("logits", self.logits), ("means", self.means), ("logscales", np.log(self.scales))):
            for index in np.ndindex(source.shape):
                left, right = source.copy(), source.copy()
                left[index] -= 1e-6
                right[index] += 1e-6
                keyword = "scales" if parameter == "logscales" else parameter
                if parameter == "logscales":
                    left, right = np.exp(left), np.exp(right)
                a, b = self.calculate(**{keyword: left}), self.calculate(**{keyword: right})
                for family in ("gaussian", "floored_gaussian", "huber"):
                    numeric = (b[family + "_nll"][index[0]] - a[family + "_nll"][index[0]]) / 2e-6
                    self.assertAlmostEqual(numeric, base[family + "_grad_" + parameter][index], places=7)

    def test_huber_normalization_and_moments(self):
        x = np.linspace(-25., 25., 250001)
        z, v = fm.huber_constants()
        u = np.sqrt(v) * x
        penalty = .5 * np.minimum(abs(u), 2)**2 + 2 * np.maximum(abs(u) - 2, 0)
        pdf = np.sqrt(v) / z * np.exp(-penalty)
        self.assertAlmostEqual(float(np.trapezoid(pdf, x)), 1., places=8)
        self.assertAlmostEqual(float(np.trapezoid(x * pdf, x)), 0., places=8)
        self.assertAlmostEqual(float(np.trapezoid(x*x*pdf, x)), 1., places=8)

    def test_extreme_logits_narrow_scales_and_floor_suppression(self):
        result = fm.diagnose([[10000., -10000., 0., -5000., 1.]], [[0.]*5], [[1e-4]*5], [8.])
        self.assertEqual(result["attenuation"][0], 0.)
        self.assertTrue(all(np.isfinite(value).all() for value in result.values()))
        self.assertAlmostEqual(result["gaussian_responsibility"].sum(), 1.)
        self.assertGreater(result["gaussian_grad_means"][0, 0]**2, 0)
        self.assertTrue((result["floored_gaussian_grad_means"] == 0).all())

    def test_huge_common_offsets_preserve_normalization(self):
        means = np.full((1, 5), 1.)
        scales = np.ones((1, 5))
        base = fm.diagnose(np.zeros((1, 5)), means, scales, [3.])
        offset = fm.diagnose(np.full((1, 5), 1e20), means, scales, [3.])
        for key in base:
            np.testing.assert_allclose(offset[key], base[key], rtol=0, atol=0)
        # Component log densities also have a huge common offset here; preserve
        # their nonuniform mixture weights before constructing responsibilities.
        logits = np.array([[0., 1., 2., 3., 4.]])
        far = fm.diagnose(logits, np.zeros((1, 5)), np.full((1, 5), 1e-4), [1e8])
        np.testing.assert_allclose(far["gaussian_responsibility"], far["normalized_weights"], rtol=1e-14)
        np.testing.assert_allclose(far["gaussian_grad_logits"].sum(1), 0., atol=1e-14)

    def test_responsibility_collapse_is_not_floor_suppression(self):
        result = fm.diagnose([[10000., -10000., 0., -5000., 1.]], [[1.]*5], [[1.]*5], [1.])
        self.assertLess(result["gaussian_responsibility_entropy"][0], 1e-10)
        self.assertGreater(result["attenuation"][0], .999)

    def test_floor_identity(self):
        result = self.calculate()
        np.testing.assert_allclose(result["attenuation"], result["gaussian_density"] / (result["gaussian_density"] + 1e-6), rtol=1e-14)
        for key in ("logits", "means", "scales", "logscales"):
            np.testing.assert_allclose(result["floored_gaussian_grad_" + key], result["attenuation"][:, None] * result["gaussian_grad_" + key])
        np.testing.assert_allclose(result["gaussian_grad_logits"].sum(1), 0., atol=1e-14)
        for family in ("gaussian", "huber"):
            for parameter in ("means", "logscales"):
                np.testing.assert_allclose(result[family + "_grad_" + parameter], result[family + "_responsibility"] * result[family + "_component_nll_score_" + parameter])

    def test_invalid_outputs_fail(self):
        for change in ({"scales": np.zeros((2, 5))}, {"logits": np.ones((2, 4))}, {"means": np.full((2, 5), np.nan)}):
            with self.assertRaises(ValueError):
                self.calculate(**change)

    def test_gate_distinct_events_and_strict_thresholds(self):
        ids, y = ["a", "b", "c", "d"], np.full(4, 6.)
        means, factors = np.full((4, 3), 5.4), np.full((4, 3), .09)
        self.assertTrue(fm.event_gate(ids, y, means, factors)["passed"])
        factors[0, :2] = .1
        self.assertFalse(fm.event_gate(ids, y, means, factors)["passed"])
        factors[:] = .09
        means[0, :2] = 5.5
        self.assertFalse(fm.event_gate(ids, y, means, factors)["passed"])
        with self.assertRaises(ValueError):
            fm.event_gate(["a"]*4, y, means, factors)


def fake_run():
    run = {k: None for k in g.CONFIG_FIELDS}
    run.update(aggregation="transformer", epochs=100, pretrain_epochs=25, selection="calibration-nll",
               density_epsilon=1e-6, pretrain_density_epsilon=1e-6, stored_samples=3000,
               training_cutoff="author", pretrain_cutoff="author", limit_fit_events=0,
               limit_dev_events=0, skip_dev=False, schema="chile-team-prefix-v1", source_sha256_files=g.SOURCES,
               selected_epoch=37, dev_evaluated=True, test_reads=0, selection_used_dev=False,
               max_stations=25, seed=20261009, cache_sha256="a"*64, source_sha256="b"*64,
               metadata_sidecar_sha256="c"*64, metadata_sidecar_manifest_sha256="d"*64,
               fit_events=2, calibration_events=1, dev_events=1)
    splits = {}
    for name, ids, rows in (("fit", ["f0", "f2"], [0, 2]), ("calibration", ["c1"], [1]), ("dev", ["d3"], [3])):
        splits[name] = dict(event_ids=ids, source_rows=rows, ids_sha256=g.ids_sha(ids))
        run[name + "_ids_sha256"] = splits[name]["ids_sha256"]
    return run, splits


class GuardTests(unittest.TestCase):
    def test_selected_checkpoint_not_forced_final(self):
        run, _ = fake_run()
        run["dev_metrics"] = {"metric": "DO_NOT_CONSULT"}
        self.assertNotIn("dev_metrics", g.project_run(run))
        plan = {"artifacts": {"cache": {"sha256": "a"*64}, "metadata": {"sha256": "c"*64}, "metadata_manifest": {"sha256": "d"*64}}}
        self.assertEqual(g.validate_completion(run, run, 37, plan, {"source_sha256": "b"*64})["selected_epoch"], 37)
        for change in ({"selection": "final"}, {"epochs": 99}, {"source_sha256_files": {}}, {"skip_dev": True}, {"dev_evaluated": False}, {"selection_used_dev": True}, {"test_reads": 1}):
            other = {**run, **change}
            with self.assertRaises(ValueError):
                g.validate_completion(other, other, 37, plan, {"source_sha256": "b"*64})
        with self.assertRaises(ValueError):
            g.validate_completion(run, run, 100, plan, {"source_sha256": "b"*64})

    def test_epoch_history_only_reads_epochs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_text(json.dumps([{"epoch": i, "calibration": {"proper_nll": "DO_NOT_USE"}} for i in range(1, 101)]))
            self.assertEqual(g.epoch_sequence(path, 100), list(range(1, 101)))
            with self.assertRaises(ValueError):
                g.epoch_sequence(path, 25)

    def test_split_guards(self):
        run, splits = fake_run()
        g.validate_splits(splits, 3, 4, run)
        for name, field, value in (("fit", "source_rows", [0, 3]), ("fit", "source_rows", [0, 0]), ("calibration", "event_ids", ["f0"])):
            changed = copy.deepcopy(splits)
            changed[name][field] = value
            with self.assertRaises(ValueError):
                g.validate_splits(changed, 3, 4, run)

    def test_nonfit_labels_not_parsed(self):
        _, splits = fake_run()
        manifest = {"author_split_boundaries": [3, 4], "cache_rows": 4, "splits": {"train": {"ids_sha256": g.ids_sha(["f0", "c1", "f2"])}, "dev": {"ids_sha256": g.ids_sha(["d3"])}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.csv"
            path.write_text("EVENT,MA,TIME,source_row_index,benchmark_split\nf0,3.1,1,0,train\nc1,DO_NOT_PARSE,DO_NOT_PARSE,1,train\nf2,6.0,3,2,train\nd3,DO_NOT_PARSE,DO_NOT_PARSE,3,dev\n")
            rows, identities = g.fit_rows_only(path, splits, manifest, {"rows": 4})
            self.assertEqual([r["EVENT"] for r in rows], ["f0", "f2"])
            self.assertEqual(identities["dev"], ["d3"])

    def test_selection_fixed_hash_and_all_tail(self):
        rows = [{"EVENT": f"event{i}", "MA": (3. if i < 1100 else 4.5 if i < 2200 else 6.), "source_row_index": i, "benchmark_split": "train"} for i in range(2210)]
        chosen, fractions = g.select_population(rows)
        chosen_reverse, _ = g.select_population(list(reversed(rows)))
        self.assertEqual(chosen, chosen_reverse)
        self.assertEqual(len(chosen), 2058)
        self.assertEqual(fractions["MA_ge_5p5"]["selected"], 10)
        self.assertEqual(fractions["MA_lt_4"]["fraction"], 1024/1100)

    def test_sha_and_schema_guards(self):
        for value in ("", "A"*64, "a"*63):
            with self.assertRaises(ValueError):
                g.check_sha(value)
        with self.assertRaises(ValueError):
            g.validate_plan({"schema": "other", "artifacts": {}})


class SupervisorTests(unittest.TestCase):
    def test_timeout_removes_completion(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as directory:
            complete = Path(directory) / "COMPLETE.json"
            complete.write_text("{}")
            with self.assertRaises(subprocess.TimeoutExpired):
                runner.supervise([sys.executable, "-c", "import time; time.sleep(20)"], .05, directory)
            self.assertFalse(complete.exists())

    def test_failed_worker_invalidates_completion(self):
        import sys
        with tempfile.TemporaryDirectory() as directory:
            complete = Path(directory) / "COMPLETE.json"
            complete.write_text("{}")
            self.assertEqual(runner.supervise([sys.executable, "-c", "raise SystemExit(7)"], 5, directory), 7)
            self.assertFalse(complete.exists())

    def test_cancellation_during_spawn_reaps_child(self):
        import os
        import signal
        import subprocess
        import sys
        from unittest.mock import patch
        original = subprocess.Popen
        children = []
        def interrupted_spawn(*args, **kwargs):
            child = original(*args, **kwargs)
            children.append(child)
            os.kill(os.getpid(), signal.SIGTERM)
            return child
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(runner.subprocess, "Popen", side_effect=interrupted_spawn):
                with self.assertRaises(SystemExit) as raised:
                    runner.supervise([sys.executable, "-c", "import time; time.sleep(20)"], 5, directory)
            self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
            self.assertIsNotNone(children[0].poll())
            with self.assertRaises(ProcessLookupError):
                os.kill(children[0].pid, 0)

    def test_cancellation_during_successful_cleanup_is_nonzero(self):
        import os
        import signal
        import subprocess
        import sys
        from unittest.mock import patch
        original = subprocess.Popen
        def spawn(*args, **kwargs):
            child = original(*args, **kwargs)
            poll = child.poll
            def interrupted_poll():
                os.kill(os.getpid(), signal.SIGTERM)
                return poll()
            child.poll = interrupted_poll
            return child
        with tempfile.TemporaryDirectory() as directory:
            complete = Path(directory) / "COMPLETE.json"
            complete.write_text("{}")
            self.assertEqual(runner.supervise([sys.executable, "-c", "pass"], 5, directory), 0)
            self.assertTrue(complete.exists())
            with patch.object(runner.subprocess, "Popen", side_effect=spawn):
                with self.assertRaises(SystemExit) as raised:
                    runner.supervise([sys.executable, "-c", "pass"], 5, directory)
            self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
            self.assertFalse(complete.exists())

    def test_repeated_cancellation_does_not_skip_cleanup(self):
        import os
        import signal
        import subprocess
        import sys
        from unittest.mock import patch
        original_popen = subprocess.Popen
        old_handler = signal.getsignal(signal.SIGTERM)
        received, children = [], []
        # Observe delivery after cleanup without terminating this test process.
        signal.signal(signal.SIGTERM, lambda signum, frame: received.append(signum))
        def interrupted_spawn(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            children.append(child)
            original_poll = child.poll
            repeated = False
            def interrupted_poll():
                nonlocal repeated
                if not repeated:
                    repeated = True
                    os.kill(os.getpid(), signal.SIGTERM)
                return original_poll()
            child.poll = interrupted_poll
            os.kill(os.getpid(), signal.SIGTERM)
            return child
        try:
            with tempfile.TemporaryDirectory() as directory:
                complete = Path(directory) / "COMPLETE.json"
                complete.write_text("{}")
                with patch.object(runner.subprocess, "Popen", side_effect=interrupted_spawn):
                    with self.assertRaises(SystemExit):
                        runner.supervise([sys.executable, "-c", "import time; time.sleep(20)"], 5, directory)
                self.assertIsNotNone(children[0].poll())
                self.assertFalse(complete.exists())
                self.assertEqual(received, [])
        finally:
            signal.signal(signal.SIGTERM, old_handler)
            for child in children:
                if child.returncode is None:
                    child.kill()
                    child.wait()

    def test_cancellation_reaps_child(self):
        import os
        import signal
        import subprocess
        import sys
        import time
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pidfile = root / "child.pid"
            child_code = "import os,time,pathlib; pathlib.Path(" + repr(str(pidfile)) + ").write_text(str(os.getpid())); time.sleep(20)"
            launcher_code = "import sys; sys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + "); import run_diagnostic as r; r.supervise(" + repr([sys.executable, "-c", child_code]) + ",10," + repr(directory) + ")"
            launcher = subprocess.Popen([sys.executable, "-c", launcher_code], start_new_session=True)
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(pidfile.exists())
                child_pid = int(pidfile.read_text())
                launcher.terminate()
                self.assertEqual(launcher.wait(timeout=5), 128 + signal.SIGTERM)
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if launcher.poll() is None:
                    os.killpg(launcher.pid, signal.SIGKILL)
                    launcher.wait()


try:
    import torch
    TORCH = True
except ImportError:
    TORCH = False


@unittest.skipUnless(TORCH, "Torch-only tests run in authorized AWS synthetic scratch")
class SourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        cls.source_dir = Path(os.environ["CHILE_SOURCE_DIR"])
        for name, digest in g.SOURCES.items():
            g.verify(cls.source_dir / name, digest)
        cls.team, cls.trainer = runner.import_sources(cls.source_dir)
        torch.set_num_threads(2)

    def test_baseline_runtime_flags_preserve_precision(self):
        before = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32,
                  torch.get_float32_matmul_precision())
        deterministic = torch.are_deterministic_algorithms_enabled()
        warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
        cudnn_deterministic = torch.backends.cudnn.deterministic
        benchmark = torch.backends.cudnn.benchmark
        try:
            torch.use_deterministic_algorithms(False)
            torch.backends.cudnn.deterministic = False
            torch.backends.cudnn.benchmark = True
            runner.configure_runtime(torch)
            self.assertTrue(torch.are_deterministic_algorithms_enabled())
            self.assertFalse(torch.is_deterministic_algorithms_warn_only_enabled())
            self.assertTrue(torch.backends.cudnn.deterministic)
            self.assertFalse(torch.backends.cudnn.benchmark)
            self.assertEqual(torch.get_num_threads(), 2)
            self.assertEqual(before, (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32,
                                      torch.get_float32_matmul_precision()))
        finally:
            torch.use_deterministic_algorithms(deterministic, warn_only=warn_only)
            torch.backends.cudnn.deterministic = cudnn_deterministic
            torch.backends.cudnn.benchmark = benchmark

    def test_prefix_exact_clock_and_future_boundary(self):
        x = torch.randn(1, 2, 3000, 3)
        mask = torch.tensor([[True, False]])
        for seconds, count in ((1, 600), (3, 800), (5, 1000)):
            altered = x.clone()
            altered[:, :, count:] = 12345
            altered[:, 1] = -1000
            a, ma = self.team.prepare_prefix(x, mask, seconds)
            b, mb = self.team.prepare_prefix(altered, mask, seconds)
            torch.testing.assert_close(a, b, rtol=0, atol=0)
            self.assertTrue(torch.equal(ma, mb))
            self.assertTrue((a[:, :, count:] == 0).all())
            torch.testing.assert_close(a[:, 0, :count], x[:, 0, :count] - x[:, 0, :count].mean(1, keepdim=True), rtol=0, atol=3e-7)

    def test_complete_worker_only_on_synthetic_fixture(self):
        import argparse
        import h5py
        import os
        source = Path(__file__).resolve().parent
        protocol = Path(os.environ["CHILE_PROTOCOL_PATH"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "synthetic.hdf5"
            metadata = Path(str(cache) + ".metadata.csv")
            metadata.write_text("EVENT,MA,TIME,source_row_index,benchmark_split\nf0,3.1,1,0,train\nc1,DO_NOT_PARSE,DO_NOT_PARSE,1,train\nf2,6.0,3,2,train\nd3,DO_NOT_PARSE,DO_NOT_PARSE,3,dev\n")
            run, splits = fake_run()
            with h5py.File(cache, "w") as handle:
                handle.attrs.update(schema="chile-team-prefix-v1", stored_samples=3000)
                for key, value in (("sampling_rate", 100), ("time_before", 5), ("time_after", 25)):
                    handle.create_dataset("metadata/" + key, data=value)
                for name, ids, rows in (("train", ["f0", "c1", "f2"], [0, 1, 2]), ("dev", ["d3"], [3])):
                    handle.create_dataset("splits/" + name + "_event_ids", data=np.asarray(ids, dtype=h5py.string_dtype()))
                    handle.create_dataset("splits/" + name + "_source_rows", data=rows)
                for event in ("f0", "c1", "f2", "d3"):
                    group = handle.create_group("data/" + event)
                    # Nonfit waveform bodies must never be consulted: malformed
                    # shapes/nonfinite payload deliberately fail EventDataset.
                    values = np.full((1, 3000, 3), np.nan, dtype=np.float32)
                    if event.startswith("f"):
                        values = np.random.default_rng(41).normal(size=(1, 3000, 3)).astype(np.float32) * 1e-4
                    group.create_dataset("waveforms", data=values)
                    group.create_dataset("coords", data=[[-33., -71., 0.]])
            manifest = {"schema": "chile-team-prefix-v1", "stored_samples": 3000, "source_test_waveforms_read": False,
                        "all_event_readback_verified": True, "sha256": g.sha(cache), "source_sha256": "b"*64,
                        "author_split_boundaries": [3, 4], "cache_rows": 4,
                        "splits": {"train": {"ids_sha256": g.ids_sha(["f0", "c1", "f2"])}, "dev": {"ids_sha256": g.ids_sha(["d3"])}}}
            metadata_manifest = {"cache_sha256": g.sha(cache), "origin": "metadata/event_metadata",
                                 "columns": ["EVENT", "MA", "TIME", "source_row_index", "benchmark_split"], "rows": 4, "sha256": g.sha(metadata)}
            baseline = root / "baseline"
            baseline.mkdir()
            paths = {"cache": cache, "metadata": metadata, "dataset_manifest": Path(str(cache) + ".manifest.json"),
                     "metadata_manifest": Path(str(metadata) + ".manifest.json")}
            for key, name in (("checkpoint", "model.pth"), ("run", "run.json"), ("split_manifest", "split_manifest.json"),
                              ("history", "history.json"), ("pretrain_history", "pretrain_history.json")):
                paths[key] = baseline / name
            runner.atomic_json(paths["dataset_manifest"], manifest)
            runner.atomic_json(paths["metadata_manifest"], metadata_manifest)
            run.update(cache_sha256=g.sha(cache), metadata_sidecar_sha256=g.sha(metadata), metadata_sidecar_manifest_sha256=g.sha(paths["metadata_manifest"]))
            config = {k: run[k] for k in g.CONFIG_FIELDS}
            torch.manual_seed(41)
            torch.save({"model": self.team.TeamLM("transformer").state_dict(), "config": config, "selected_epoch": 37}, paths["checkpoint"])
            runner.atomic_json(paths["run"], run)
            runner.atomic_json(paths["split_manifest"], splits)
            for key, count in (("history", 100), ("pretrain_history", 25)):
                runner.atomic_json(paths[key], [{"epoch": i, "calibration": "DO_NOT_USE"} for i in range(1, count+1)])
            plan = {"schema": "chile_floor_artifact_plan_v1", "artifacts": {key: {"path": str(path), "sha256": g.sha(path)} for key, path in paths.items()}}
            plan_path = root / "plan.json"
            runner.atomic_json(plan_path, plan)
            source_path = root / "sources.json"
            runner.atomic_json(source_path, {"schema": "chile_floor_sources_v1", "own": {name: g.sha(source / name) for name in runner.OWN_FILES},
                                             "dependencies": g.SOURCES, "protocol_sha256": g.PROTOCOL_SHA})
            args = argparse.Namespace(plan=plan_path, plan_sha256=g.sha(plan_path), protocol=protocol, protocol_sha256=g.PROTOCOL_SHA,
                                      source_dir=self.source_dir, source_manifest=source_path, source_manifest_sha256=g.sha(source_path),
                                      output=root / "out", max_seconds=600, batch_size=2, device="cpu")
            runner.worker(args)
            complete = g.read_json(args.output / "COMPLETE.json")
            for name, digest in complete["artifacts"].items():
                g.verify(args.output / name, digest)
            with np.load(args.output / "diagnostics.npz", allow_pickle=False) as arrays:
                self.assertEqual(arrays["event_ids"].tolist(), ["f0", "f2"])
                self.assertEqual(arrays["source_rows"].tolist(), [0, 2])
            summary = g.read_json(args.output / "summary.json")
            self.assertEqual(summary["selection_epoch"], 37)
            self.assertTrue(summary["runtime"]["deterministic_algorithms"])
            self.assertTrue(summary["runtime"]["cudnn_deterministic"])
            self.assertFalse(summary["runtime"]["cudnn_benchmark"])
            with self.assertRaises(FileExistsError):
                runner.worker(args)
            # Dry preflight must not even require production artifact existence.
            for path in paths.values():
                path.rename(path.with_name(path.name + ".absent"))
            runner.preflight(args)
            for path in paths.values():
                path.with_name(path.name + ".absent").rename(path)
            args.max_seconds = 601
            with self.assertRaises(ValueError):
                runner.preflight(args)
            args.max_seconds = 600
            with h5py.File(cache, "r+") as handle:
                handle["metadata/time_before"][()] = 4
            with self.assertRaises(ValueError):
                runner.verify_hdf_headers(cache, manifest, {"train": ["f0", "c1", "f2"], "dev": ["d3"]}, [{"EVENT": "f0"}], 25)
            with h5py.File(cache, "r+") as handle:
                handle["metadata/time_before"][()] = 5
            with self.assertRaises(ValueError):
                runner.verify_hdf_headers(cache, manifest, {"train": ["f0", "c1", "f2"], "dev": ["d3"]}, [{"EVENT": "f0"}], 0)
            wrong = {**manifest, "stored_samples": 1000}
            with self.assertRaises(ValueError):
                runner.verify_metadata_contract(plan, wrong, metadata_manifest)

    def test_source_forward_matches_evaluate_on_invented_arrays(self):
        torch.manual_seed(7)
        model = self.team.TeamLM("transformer").eval().requires_grad_(False)
        x = torch.randn(1, 1, 3000, 3) * 1e-4
        coords = torch.tensor([[[-33., -71., 0.]]])
        mask = torch.ones(1, 1, dtype=torch.bool)
        y = torch.tensor([6.1], dtype=torch.float64)
        loader = [(x, coords, mask, y, ["synthetic"])]
        actual = runner.source_forward(model, loader, torch.device("cpu"), self.team, self.trainer)
        # Existing evaluate only on this invented fixture, never production heldout data.
        _, expected = self.trainer.evaluate(model, loader, torch.device("cpu"))
        for t in (1, 3, 5):
            np.testing.assert_array_equal(actual[f"{t}_source_mean"], expected[f"mean_{t}s"])
            np.testing.assert_array_equal(actual[f"{t}_source_median"], expected[f"median_{t}s"])
        self.assertEqual(actual["event_ids"].tolist(), ["synthetic"])


if __name__ == "__main__":
    unittest.main()

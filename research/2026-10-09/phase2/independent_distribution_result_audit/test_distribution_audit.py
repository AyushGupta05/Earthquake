"""Invented-array tests only; no imports from production trainers or metrics."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import artifact_audit as aa
import metric_audit as ma


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def synthetic_metadata():
    roles = np.array(["fit"] * 8 + ["eval_seen"] * 3 + ["eval_held"] * 3)
    n = len(roles)
    valid = np.ones((n, 3), dtype=bool)
    valid[6, 0] = False; valid[7, 2] = False; valid[9, 0] = False
    return dict(source_row_index=np.arange(n, dtype=np.int64) * 7,
        trace_name=np.array(["trace" + str(i) for i in range(n)]),
        source_id=np.array(["fit" + str(i) for i in range(8)] + ["low", "four", "five"] * 2),
        station_group=np.array(["station" + str(i) for i in range(n)]),
        subset=roles, sampling_weight=(np.arange(n) % 3 + 1).astype(float), valid=valid,
        invalid_codes=(~valid).astype(np.uint16), deadlines=np.array([1, 3, 5]),
        targets=np.array([.2, 1.2, 2.2, 3.2, 4.2, 5.2, .4, 2.3, .2, 4.4, 5.3, .2, 4.4, 5.3]),
        native_units=np.array(["m/s"] * n), static=np.tile(np.r_[1., np.zeros(33)], (n, 1)))


def fixture_root(directory, kind):
    """Hand-build immutable artifact schemas; checkpoint bytes are opaque text."""
    root, export = directory / "grid", directory / "export"
    root.mkdir(); export.mkdir()
    m = synthetic_metadata(); np.savez(export / "metadata.npz", **m)
    manifest = {"status": "complete", "rows": len(m["targets"]),
                "outputs_sha256": {"metadata.npz": aa.file_sha(export / "metadata.npz"), "counts.npy": "0" * 64}}
    write_json(export / "manifest.json", manifest)
    export_sha = aa.file_sha(export / "manifest.json")
    write_json(export / "COMPLETE.json", {"manifest_sha256": export_sha})
    contract = {"response_bundle_sha256": "b" * 64, "files": {
        "response": {k: str(i) * 64 for i, k in enumerate(("response_data.py", "response_model.py", "response_metrics.py", "train_response_grid.py", "frozen_protocol_v1.md"), 1)},
        "exposure": {k: str(i) * 64 for i, k in enumerate(("exposure_training.py", "exposure_metrics.py", "shared_response_adapter.py", "run_exposure_grid.py", "AUDIT_AND_FIXED_PROTOCOL.md"), 1)}}}
    contract_path = directory / "contract.json"; write_json(contract_path, contract)
    nd = root / "prepared" if kind == "response" else root
    nd.mkdir(exist_ok=True)
    normals = {"test_mean": np.zeros(3, np.float32), "test_std": np.ones(3, np.float32)}
    np.savez(nd / "normalizers.npz", **normals)
    provenance = {"export_manifest_sha256": export_sha, "normalizer_source_sha256": contract["files"]["response"]["response_data.py"],
        "metadata_fit_population": aa.fit_digest(m), "per_deadline_fit_population": {str(t): aa.fit_digest(m, t) for t in ma.TIMES},
        "labels_used": False, "held_rows_used": False,
        "arrays_sha256": {k: aa.hashlib.sha256(v.tobytes()).hexdigest() for k, v in normals.items()}}
    if kind == "response": provenance["artifact_sha256"] = aa.file_sha(nd / "normalizers.npz")
    normal_name = "normalizers.json" if kind == "response" else "normalizers_provenance.json"
    write_json(nd / normal_name, provenance)
    all_p = {}
    for t, subset in ma.PANELS:
        pop = aa.population(m, subset, t); n = len(pop["targets"])
        p = np.full((n, 66), .001)
        label = np.floor(pop["targets"] / .1 + 1e-5).astype(int)
        p[np.arange(n), label] += 1 - .066
        for c in aa.CONTROLS[kind]:
            for seed in ma.SEEDS:
                all_p[(c, seed, t, subset)] = p.copy()
    records = {}; config = {}
    if kind == "response":
        rt = dict(deterministic=True, tf32_matmul=False, tf32_cudnn=False, cublas_workspace_config=":4096:8", threads=2)
        for c in aa.CONTROLS[kind]:
            for seed in ma.SEEDS:
                path = root / f"{c}_{seed}"; path.mkdir()
                (path / "checkpoint.pt").write_bytes(b"Synthetic opaque checkpoint, never unpickled")
                write_json(path / "gain_diagnostic.json", {})
                values = {}
                for t, subset in ma.PANELS:
                    values[f"rows_{t}_{subset}"] = aa.rows(m, subset, t)
                    values[f"p_{t}_{subset}"] = all_p[(c, seed, t, subset)]
                np.savez(path / "predictions.npz", **values)
                d = max(len(aa.rows(m, "fit", t)) for t in ma.TIMES)
                fit = {"initial_state_sha256": str(seed), "final_state_sha256": c + str(seed),
                    "fit_rows": {str(t): len(aa.rows(m, "fit", t)) for t in ma.TIMES},
                    "fit_weight_mean": {str(t): float(m["sampling_weight"][aa.rows(m, "fit", t)].mean()) for t in ma.TIMES},
                    "steps": 10 * aa.math.ceil(d / 512), "order_sha256": [aa.response_schedule(m, seed, e) for e in range(10)],
                    "history": [{"epoch": e + 1, "draws_per_horizon": d, "training_loss": 1., "lr": 3e-5 + (3e-4 - 3e-5) * (1 + aa.math.cos(aa.math.pi * e / 10)) / 2} for e in range(10)]}
                info = dict(status="complete", arm=c, seed=seed, epochs=10, batch_size=512,
                    bundle_sha256=contract["response_bundle_sha256"], protocol_sha256=contract["files"]["response"]["frozen_protocol_v1.md"],
                    source_files=contract["files"]["response"], export_manifest_sha256=export_sha,
                    normalizers_sha256=aa.file_sha(nd / normal_name), runtime=rt, device="synthetic", objective="frozen synthetic fixture",
                    seconds=1., fit=fit, outputs_sha256={name: aa.file_sha(path / name) for name in ("checkpoint.pt", "predictions.npz", "gain_diagnostic.json")})
                write_json(path / "manifest.json", info); write_json(path / "COMPLETE.json", {"manifest_sha256": aa.file_sha(path / "manifest.json")})
                records[(c, seed)] = info
        grid = dict(status="complete", arms=list(aa.CONTROLS[kind]), seeds=list(ma.SEEDS), bundle_sha256=contract["response_bundle_sha256"],
            protocol_sha256=contract["files"]["response"]["frozen_protocol_v1.md"], export_manifest_sha256=export_sha)
    else:
        plans = aa.exposure_plan(m)
        population = {str(t): aa.population_identity(plans[t]["pop"], t, "fit") for t in ma.TIMES}
        identity = dict(export_sha256=export_sha, backbone_sha256=contract["files"]["response"]["response_model.py"],
            normalizers_sha256=aa.compact_sha(provenance), normalizer_provenance=provenance,
            population_sha256=aa.compact_sha(population), normalizer_fit_population_sha256=aa.compact_sha(population),
            architecture="B-native-late", expected_parameters=380706,
            adapter_sha256=contract["files"]["exposure"]["shared_response_adapter.py"], runner_sha256=contract["files"]["exposure"]["run_exposure_grid.py"])
        import torch
        rt = dict(torch=str(torch.__version__), deterministic=True, CUBLAS_WORKSPACE_CONFIG=":4096:8", torch_num_threads=2)
        config = dict(export_sha256=export_sha, model_sha256=identity["backbone_sha256"], data_sha256=contract["files"]["response"]["response_data.py"], threads=2)
        for c in aa.CONTROLS[kind]:
            for seed in ma.SEEDS:
                path = root / f"{c}_seed{seed}"; path.mkdir()
                (path / "latest.pth").write_bytes(b"Synthetic opaque checkpoint, never unpickled")
                orders, _ = aa.exposure_orders(plans, c, seed)
                history = [{"completed_epoch": e + 1, "orders": order, "loss": {str(t): 1. for t in ma.TIMES}} for e, order in enumerate(orders)]
                write_json(path / "history.json", history)
                cconfig = dict(control=c, seed=seed, epochs=10, batch_size=512,
                    protocol_sha256=contract["files"]["exposure"]["AUDIT_AND_FIXED_PROTOCOL.md"],
                    implementation_sha256=contract["files"]["exposure"]["exposure_training.py"], identity=identity,
                    population=population, sampling={str(t): p["sampling"] for t, p in plans.items()},
                    parameters=380706, optimizer=dict(name="AdamW", lr=3e-4, weight_decay=1e-4, cosine_eta_min=3e-5, gradient_clip=5.),
                    draws_per_horizon_per_epoch=max(len(p["labels"]) for p in plans.values()), runtime=rt, initial_model_sha256=str(seed))
                write_json(path / "identity.json", cconfig)
                done = dict(control=c, seed=seed, completed_epoch=10, checkpoint_sha256=aa.file_sha(path / "latest.pth"),
                    identity_sha256=aa.file_sha(path / "identity.json"), history_sha256=aa.file_sha(path / "history.json"),
                    initial_model_sha256=str(seed), final_model_sha256=c + str(seed), fit_population_sha256=aa.compact_sha(population))
                write_json(path / "completed.json", done); records[(c, seed)] = done
        grid = dict(status="complete", configuration=config, runtime=rt, binding_identity=identity,
                    source_sha256={k: v for k, v in contract["files"]["exposure"].items() if k.endswith(".py")})
        write_json(root / "job_status.json", dict(status="complete", exitcode=0, timed_out=False, configuration=config))
        values = {f"{c}__{seed}__{t}__{s}": value for (c, seed, t, s), value in all_p.items()}
        for t, subset in ma.PANELS:
            pop = aa.population(m, subset, t)
            for k, v in pop.items(): values[f"panel__{t}__{subset}__{k}"] = v
            values[f"panel__{t}__{subset}__unit"] = np.array(["m/s"] * len(pop["targets"]))
            values[f"panel__{t}__{subset}__family"] = np.array(["HH"] * len(pop["targets"]))
        np.savez(root / "predictions.npz", **values)
    report = dict(scores=[], comparisons=[])
    if kind == "response":
        report.update(protocol_sha256=grid["protocol_sha256"], bundle_sha256=grid["bundle_sha256"],
            runs={f"{c}_{s}": {"manifest_sha256": aa.file_sha(root / f"{c}_{s}" / "manifest.json")} for c, s in records})
    else:
        report.update(protocol_sha256=contract["files"]["exposure"]["AUDIT_AND_FIXED_PROTOCOL.md"],
            metrics_source_sha256=contract["files"]["exposure"]["exposure_metrics.py"], checkpoints=[records[(c, s)] for c in aa.CONTROLS[kind] for s in ma.SEEDS])
    for t, subset in sorted(ma.PANELS):
        pop = aa.population(m, subset, t); y, w, event = pop["targets"], pop["weights"], pop["events"]
        computed = {}
        for c in aa.CONTROLS[kind]:
            for label in [*map(str, ma.SEEDS), "ensemble"]:
                p = all_p[(c, ma.SEEDS[0] if label == "ensemble" else int(label), t, subset)]
                result = ma.reported_scores(ma.scores(p, y, w, event, kind), kind)
                if kind == "exposure": result["strata"] = {}
                computed[(c, label)] = result
                common = dict(seconds=t, subset=subset, metrics=result)
                if kind == "response": common.update(arm=c, seed=label)
                else: common.update(control=c, seed_or_ensemble="equal_pmf_ensemble" if label == "ensemble" else label, pmf_sha256=aa.array_sha(p, "exposure"))
                report["scores"].append(common)
        candidate = "C" if kind == "response" else "band_exposure_ce"
        for ref in (("B",) if kind == "response" else ("huber_ce", "natural_ce")):
            p = all_p[(candidate, ma.SEEDS[0], t, subset)]
            fraction = len(y) / (m["subset"] == subset).sum()
            row = dict(seconds=t, subset=subset, bootstrap=ma.bootstrap(p, p, y, w, event, kind),
                       individual_event_mae_deltas={str(e): 0. for e in np.unique(event)})
            if kind == "response":
                zero = dict(weighted_mae=0., medae=0., m4_weighted_mae=0., m4_event_macro_mae=0.)
                row.update(valid_fraction=fraction, m4_events=len(np.unique(event[y >= 4])),
                    seed_deltas={str(s): zero.copy() for s in ma.SEEDS}, ensemble_deltas=zero.copy())
            else:
                row.update(valid_fraction=min(fraction, m["valid"][m["subset"] == "fit", ma.TIMES.index(t)].mean()),
                    reference_control=ref, candidate=computed[(candidate, "ensemble")], reference=computed[(ref, "ensemble")], seed_m4_event_macro_deltas=[0., 0.])
            report["comparisons"].append(row)
    report["gate"] = ma.gate(report["comparisons"], kind)
    write_json(root / "report.json", report)
    if kind == "response":
        grid["report_sha256"] = aa.file_sha(root / "report.json")
        grid_name, complete_key = "grid_manifest.json", "grid_manifest_sha256"
    else:
        grid["outputs_sha256"] = {name: aa.file_sha(root / name) for name in ("normalizers.npz", "normalizers_provenance.json", "report.json", "predictions.npz")}
        grid_name, complete_key = "manifest.json", "manifest_sha256"
    write_json(root / grid_name, grid)
    write_json(root / "COMPLETE.json", {complete_key: aa.file_sha(root / grid_name)})
    return root, export, kind, aa.file_sha(root / grid_name), export_sha, contract_path, aa.file_sha(contract_path)


class MetricTests(unittest.TestCase):
    def test_weighted_points_event_average_and_partial_cvar(self):
        out = ma.point(np.array([0., 2., 4.]), np.zeros(3), np.array([94., 4., 2.]), np.array(["a", "b", "b"]))
        self.assertAlmostEqual(out["weighted_mae"], .16)
        self.assertEqual(out["medae"], 0.)
        self.assertAlmostEqual(out["event_macro_mae"], 1.5)
        self.assertAlmostEqual(out["cvar95"], 2.8)
        self.assertEqual(out["supplementary"], {"weighted_p95_abs_error": 2., "maximum_abs_error": 4.})

    def test_support_and_continuous_vs_quantized_crps(self):
        p = np.zeros((1, 66)); p[0, 0] = 1
        response = ma.scores(p, np.array([.075]), np.ones(1), np.array(["a"]), "response")
        exposure = ma.scores(p, np.array([.075]), np.ones(1), np.array(["a"]), "exposure")
        self.assertAlmostEqual(response["distribution"]["continuous_label_crps"], .075)
        self.assertAlmostEqual(exposure["distribution"]["continuous_crps"], .025)
        self.assertEqual(exposure["distribution"]["quantized_crps"], 0.)
        self.assertAlmostEqual(ma.support("exposure")[0] - ma.support("response")[0], .05)

    def test_two_mass_crps_matches_pairwise_definition(self):
        p = np.zeros((3, 66)); p[:, 10] = .3; p[:, 50] = .7
        y = np.array([-.1, 3.123, 7.])
        x = ma.support("exposure"); w = np.array([1., 2., 3.])
        first = .3 * abs(y - x[10]) + .7 * abs(y - x[50])
        expected = np.average(first - .3 * .7 * (x[50] - x[10]), weights=w)
        out = ma.scores(p, y, w, np.array(["a", "b", "c"]), "exposure")
        self.assertAlmostEqual(out["distribution"]["continuous_crps"], expected)
        self.assertEqual(out["distribution"]["unsupported_category_records"], 2)
        self.assertIsNone(out["distribution"]["categorical_nll"])

    def test_pmf_and_report_corruption_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unnormalized"):
            ma.probability(np.ones((1, 66)), 1)
        with self.assertRaisesRegex(ValueError, "fields"):
            ma.compare_values({}, {"weighted_mae": .2})
        with self.assertRaisesRegex(ValueError, "mismatch"):
            ma.compare_values({"weighted_mae": .201}, {"weighted_mae": .2})

    def test_fixed_response_gate_fail_precision_and_support(self):
        delta = dict(weighted_mae=.001, medae=.001, m4_weighted_mae=-.03, m4_event_macro_mae=-.03)
        rows = [dict(seconds=t, subset=s, m4_events=20, valid_fraction=.95, seed_deltas={str(seed): delta.copy() for seed in ma.SEEDS},
            bootstrap=dict(replicates=1000, seed=20261011, **{k: [-.1, v] for k, v in delta.items()})) for t, s in sorted(ma.PANELS)]
        self.assertEqual(ma.gate(rows, "response")["status"], "pass")
        rows[0]["bootstrap"]["weighted_mae"][1] = .003
        self.assertEqual(ma.gate(rows, "response")["status"], "inconclusive_precision")
        rows[0]["seed_deltas"][str(ma.SEEDS[0])]["m4_event_macro_mae"] = 0
        self.assertEqual(ma.gate(rows, "response")["status"], "failed")
        rows[0]["m4_events"] = 19
        self.assertEqual(ma.gate(rows, "response")["status"], "inconclusive_support")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            ma.gate(rows[:-1], "response")

    def test_bootstrap_is_paired_and_fixed(self):
        p = np.zeros((4, 66)); p[:, 40] = 1
        b = p.copy(); b[:, 40] = 0; b[:, 41] = 1
        y = np.repeat(4., 4); w = np.array([1., 2., 3., 1.]); events = np.array(["a", "a", "b", "c"])
        result = ma.bootstrap(p, b, y, w, events, "response")
        np.testing.assert_allclose(result["weighted_mae"], [-.1, -.1], atol=1e-14)
        np.testing.assert_allclose(result["m4_event_macro_mae"], [-.1, -.1], atol=1e-14)
        zero = ma.bootstrap(p, p, y, w, events, "exposure")
        self.assertEqual(zero["weighted_mae_ci95"], [0., 0.])

    def test_exposure_gate_requires_both_references_and_fixed_margin(self):
        c = dict(weighted_mae=.3, medae=.2, tail={"4": dict(events=20, event_macro_mae=.7)})
        r = dict(weighted_mae=.3, medae=.2, tail={"4": dict(events=20, event_macro_mae=.73)})
        rows = [dict(seconds=t, subset=s, reference_control=ref, candidate={"mean": copy.deepcopy(c)},
            reference={"mean": copy.deepcopy(r)}, seed_m4_event_macro_deltas=[-.01, -.04], valid_fraction=.99,
            bootstrap=dict(replicates=1000, seed=20261011, weighted_mae_ci95=[-.01, .003], m4_event_macro_mae_ci95=[-.1, -.001]))
            for ref in ("huber_ce", "natural_ce") for t, s in sorted(ma.PANELS)]
        self.assertEqual(ma.gate(rows, "exposure")["status"], "pass")
        rows[0]["candidate"]["mean"]["tail"]["4"]["event_macro_mae"] = .715
        self.assertEqual(ma.gate(rows, "exposure")["status"], "failed")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            ma.gate(rows[6:], "exposure")


class ArtifactTests(unittest.TestCase):
    def test_full_response_fixture_all_eight_and_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "response")
            result = aa.audit(*args)
            self.assertEqual(result["runs_verified"], 8)
            self.assertEqual(result["score_rows_checked"], 72)
            self.assertFalse((args[1] / "counts.npy").exists())
            self.assertEqual(result["gate"]["status"], "inconclusive_support")
            self.assertEqual(len(result["worst_error_contrasts"]), 36)

    def test_full_exposure_fixture_all_six_and_sampler(self):
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "exposure")
            result = aa.audit(*args)
            self.assertEqual(result["runs_verified"], 6)
            self.assertEqual(result["score_rows_checked"], 54)
            self.assertEqual(result["comparisons_checked"], 12)
            self.assertEqual(result["gate"]["status"], "inconclusive_tail_sample")
            self.assertEqual(len(result["worst_error_contrasts"]), 72)

    def test_numeric_report_corruption_and_missing_field_are_detected(self):
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "response")
            report = aa.json_value(args[0] / "report.json")
            report["scores"][0]["metrics"]["mean"]["weighted_mae"] += .001
            with self.assertRaisesRegex(ValueError, "numeric mismatch"):
                aa.replay_report(args[0], "response", synthetic_metadata(), report)
            del report["scores"][0]["metrics"]["mean"]["weighted_mae"]
            with self.assertRaisesRegex(ValueError, "fields"):
                aa.replay_report(args[0], "response", synthetic_metadata(), report)

    def test_gate_uses_replayed_values_without_metric_tolerance(self):
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "response")
            report = aa.json_value(args[0] / "report.json")
            # These changes fit inside numeric replay tolerance, but cannot
            # convert exact ties into strict negative improvement for the gate.
            for row in report["comparisons"]:
                for delta in row["seed_deltas"].values():
                    delta["m4_weighted_mae"] = delta["m4_event_macro_mae"] = -1e-10
                for key in ("m4_weighted_mae", "m4_event_macro_mae"):
                    row["bootstrap"][key] = [-1e-10, -1e-10]
            report["gate"] = ma.gate(report["comparisons"], "response")
            with self.assertRaisesRegex(ValueError, "fixed gate.*differs"):
                aa.replay_report(args[0], "response", synthetic_metadata(), report)

    def test_empty_fit_prefix_fails_promptly(self):
        m = synthetic_metadata(); m["valid"][m["subset"] == "fit", 0] = False
        with self.assertRaisesRegex(ValueError, "Empty fitting"):
            aa.response_schedule(m, ma.SEEDS[0], 0)

    def test_metadata_static_rows_must_align(self):
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "response")
            m = synthetic_metadata(); m["static"] = np.empty((0, 34))
            np.savez(args[1] / "metadata.npz", **m)
            manifest = aa.json_value(args[1] / "manifest.json")
            manifest["outputs_sha256"]["metadata.npz"] = aa.file_sha(args[1] / "metadata.npz")
            write_json(args[1] / "manifest.json", manifest)
            sha = aa.file_sha(args[1] / "manifest.json")
            write_json(args[1] / "COMPLETE.json", {"manifest_sha256": sha})
            with self.assertRaisesRegex(ValueError, "Static metadata"):
                aa.metadata_export(args[1], sha)

    def test_incomplete_grid_stops_before_probability_decode(self):
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "response")
            (args[0] / "D_20261010" / "COMPLETE.json").unlink()
            with patch.object(aa, "panel_predictions", side_effect=AssertionError("must not score")):
                with self.assertRaises(FileNotFoundError): aa.audit(*args)

    def test_checkpoint_bytes_and_prediction_order_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "response")
            (args[0] / "A_20261009" / "checkpoint.pt").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Changed artifact"): aa.audit(*args)
        with tempfile.TemporaryDirectory() as d:
            args = fixture_root(Path(d), "response")
            path = args[0] / "A_20261009" / "predictions.npz"
            with np.load(path, allow_pickle=False) as f: values = {k: f[k] for k in f.files}
            values["rows_3_eval_seen"] = values["rows_3_eval_seen"][::-1]
            np.savez(path, **values)
            # Direct row check isolates alignment from the already tested byte hash.
            with self.assertRaisesRegex(ValueError, "row order"):
                aa.panel_predictions(args[0], "response", synthetic_metadata(), 3, "eval_seen")

    def test_deadline_schedule_and_exposure_arms_match(self):
        m = synthetic_metadata()
        self.assertNotEqual(aa.response_schedule(m, ma.SEEDS[0], 0)["1"], aa.response_schedule(m, ma.SEEDS[0], 0)["3"])
        plans = aa.exposure_plan(m)
        a, _ = aa.exposure_orders(plans, "huber_ce", ma.SEEDS[0])
        b, _ = aa.exposure_orders(plans, "natural_ce", ma.SEEDS[0])
        c, _ = aa.exposure_orders(plans, "band_exposure_ce", ma.SEEDS[0])
        self.assertEqual(a, b); self.assertNotEqual(a, c)
        self.assertTrue(all(row[str(t)]["draws"] == 8 for row in c for t in ma.TIMES))

    def test_default_cli_does_not_read_any_paths(self):
        with patch.object(aa, "audit", side_effect=AssertionError("no reads")):
            self.assertEqual(aa.main(["--kind", "response", "--root", "/missing", "--export", "/missing", "--contract", "/missing", "--output", "/missing", "--grid-sha256", "x", "--export-sha256", "x", "--contract-sha256", "x"]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

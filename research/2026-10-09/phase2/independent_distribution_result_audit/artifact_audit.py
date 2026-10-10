"""Read-only, independent completed-grid audit. Dry-run until --execute.

Only metadata and saved PMFs are decoded. Checkpoints are byte-hashed, never
deserialized. No producer score/validation functions, models or waveform arrays
are imported/opened. Torch is used on CPU only to replay exposure sampler RNG.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time

import numpy as np

from metric_audit import (TIMES, SUBSETS, SEEDS, PANELS, need, probability, scores,
                          point, support, reported_scores, compare_values, deltas,
                          bootstrap, gate)

CONTROLS = {"response": ("A", "B", "C", "D"),
            "exposure": ("huber_ce", "natural_ce", "band_exposure_ce")}
METADATA = ("source_row_index", "trace_name", "source_id", "station_group", "subset",
            "sampling_weight", "valid", "invalid_codes", "deadlines", "targets", "native_units", "static")


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_value(path):
    def reject(value):
        raise ValueError("Nonfinite JSON constant " + value)
    return json.loads(Path(path).read_text(), parse_constant=reject)


def hashed_json(path, digest):
    need(file_sha(path) == digest, "Changed JSON artifact: " + str(path))
    return json_value(path)


def compact_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def array_sha(value, kind):
    a = np.ascontiguousarray(value)
    shape = str(a.shape) if kind == "response" else json.dumps(a.shape)
    return hashlib.sha256(str(a.dtype).encode() + shape.encode() + a.tobytes()).hexdigest()


def artifacts(path, declared, expected):
    need(set(declared) == set(expected), "Wrong artifact allowlist: " + str(path))
    for name in expected:
        need(Path(name).name == name, "Nonlocal artifact name")
        need(file_sha(path / name) == declared[name], "Changed artifact: " + str(path / name))


def rows(metadata, subset, t):
    return np.flatnonzero((metadata["subset"] == subset) & metadata["valid"][:, TIMES.index(t)])


def population(metadata, subset, t):
    ix = rows(metadata, subset, t)
    need(len(ix) > 0, "Empty frozen population")
    return {"source_rows": metadata["source_row_index"][ix].astype(np.int64),
            "events": metadata["source_id"][ix].astype(str), "stations": metadata["station_group"][ix].astype(str),
            "targets": metadata["targets"][ix].astype(np.float64), "weights": metadata["sampling_weight"][ix].astype(np.float64)}


def population_identity(pop, t, subset):
    return {"seconds": t, "subset": subset, "records": len(pop["targets"]),
            "arrays": {k: array_sha(v, "exposure") for k, v in pop.items()}}


def fit_digest(m, t=None):
    keep = m["subset"] == "fit"
    if t is not None:
        keep &= m["valid"][:, TIMES.index(t)]
    h = hashlib.sha256()
    indices = np.flatnonzero(keep)
    for i in indices:
        record = {"source_row_index": int(m["source_row_index"][i]), "trace_name": str(m["trace_name"][i]),
                  "source_id": str(m["source_id"][i]), "sampling_weight": float(m["sampling_weight"][i])}
        h.update(json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n")
    return {"rows": len(indices), "sha256": h.hexdigest()}


def metadata_export(path, expected_sha):
    manifest = hashed_json(path / "manifest.json", expected_sha)
    need(json_value(path / "COMPLETE.json")["manifest_sha256"] == expected_sha and manifest["status"] == "complete", "Export incomplete")
    need(file_sha(path / "metadata.npz") == manifest["outputs_sha256"]["metadata.npz"], "Export metadata bytes changed")
    with np.load(path / "metadata.npz", allow_pickle=False) as f:
        m = {k: f[k] for k in METADATA}
    n = len(m["targets"])
    need(n == manifest["rows"] and m["valid"].shape == (n, 3) and m["valid"].dtype == np.bool_, "Export dimensions")
    need(np.array_equal(m["deadlines"], TIMES) and np.array_equal(m["valid"], m["invalid_codes"] == 0), "Export deadline masks")
    need(all(m[k].shape == (n,) for k in METADATA if k not in ("static", "valid", "invalid_codes", "deadlines")), "Metadata row alignment")
    need(len(np.unique(m["source_row_index"])) == n and np.isfinite(m["targets"]).all() and np.isfinite(m["sampling_weight"]).all() and (m["sampling_weight"] > 0).all(), "Invalid metadata IDs/labels/weights")
    need(set(m["subset"]) <= {"fit", *SUBSETS}, "Unexpected population role")
    need(m["static"].shape == (n, 34) and np.isfinite(m["static"]).all(), "Static metadata row/column alignment")
    need(all(len(rows(m, "fit", t)) > 0 for t in TIMES), "Empty fitting deadline")
    family = m["static"][:, :6]
    need(np.isin(family, [0, 1]).all() and (family.sum(1) == 1).all(), "Family one-hot mismatch")
    fit_events = set(m["source_id"][m["subset"] == "fit"])
    need(not fit_events.intersection(m["source_id"][m["subset"] != "fit"]), "Fit/held event overlap")
    return m, manifest


def normalizers(root, m, export_sha, contract, kind):
    directory = root / "prepared" if kind == "response" else root
    name = "normalizers.json" if kind == "response" else "normalizers_provenance.json"
    provenance = json_value(directory / name)
    need(provenance["export_manifest_sha256"] == export_sha and provenance["normalizer_source_sha256"] == contract["files"]["response"]["response_data.py"], "Wrong normalizer source/export")
    need(provenance["labels_used"] is False and provenance["held_rows_used"] is False, "Held/label normalizer leakage")
    need(provenance["metadata_fit_population"] == fit_digest(m) and provenance["per_deadline_fit_population"] == {str(t): fit_digest(m, t) for t in TIMES}, "Normalizer population mismatch")
    if kind == "response":
        need(file_sha(directory / "normalizers.npz") == provenance["artifact_sha256"], "Changed normalizer file")
    with np.load(directory / "normalizers.npz", allow_pickle=False) as f:
        arrays = {k: f[k] for k in f.files}
    need(set(arrays) == set(provenance["arrays_sha256"]), "Normalizer array schema")
    for key, value in arrays.items():
        need(np.isfinite(value).all(), "Nonfinite normalizer")
        need(hashlib.sha256(np.asarray(value, dtype="<f4").tobytes()).hexdigest() == provenance["arrays_sha256"][key], "Changed normalizer array")
        if key.endswith("_std"):
            need((value > 0).all(), "Nonpositive normalizer scale")
    return provenance, file_sha(directory / name)


def response_schedule(m, seed, epoch):
    populations = {t: rows(m, "fit", t) for t in TIMES}
    need(all(len(v) > 0 for v in populations.values()), "Empty fitting deadline")
    d = max(map(len, populations.values()))
    result = {}
    for t in TIMES:
        rng = np.random.default_rng(np.random.SeedSequence([seed, epoch, t]))
        pieces, remaining = [], d
        while remaining:
            piece = rng.permutation(populations[t])[:remaining]
            pieces.append(piece)
            remaining -= len(piece)
        result[str(t)] = array_sha(np.concatenate(pieces), "response")
    return result


def verify_response(root, m, export_sha, contract, grid_sha):
    grid = hashed_json(root / "grid_manifest.json", grid_sha)
    need(json_value(root / "COMPLETE.json")["grid_manifest_sha256"] == grid_sha and grid["status"] == "complete", "Response grid incomplete")
    expected_source = contract["files"]["response"]
    need(grid["bundle_sha256"] == contract["response_bundle_sha256"] and grid["protocol_sha256"] == expected_source["frozen_protocol_v1.md"] and grid["export_manifest_sha256"] == export_sha, "Response grid pins")
    need(grid["arms"] == list(CONTROLS["response"]) and grid["seeds"] == list(SEEDS), "Wrong response grid")
    report = hashed_json(root / "report.json", grid["report_sha256"])
    need(report["protocol_sha256"] == grid["protocol_sha256"] and report["bundle_sha256"] == grid["bundle_sha256"], "Report protocol/source mismatch")
    _, normal_sha = normalizers(root, m, export_sha, contract, "response")
    records = {}
    fitrows = {str(t): len(rows(m, "fit", t)) for t in TIMES}
    weightmeans = {str(t): float(m["sampling_weight"][rows(m, "fit", t)].mean()) for t in TIMES}
    d = max(fitrows.values())
    for seed in SEEDS:
        orders = [response_schedule(m, seed, epoch) for epoch in range(10)]
        for arm in CONTROLS["response"]:
            key = f"{arm}_{seed}"; path = root / key
            digest = json_value(path / "COMPLETE.json")["manifest_sha256"]
            info = hashed_json(path / "manifest.json", digest)
            need(report["runs"][key]["manifest_sha256"] == digest, "Report references wrong run")
            need(info["status"] == "complete" and info["arm"] == arm and info["seed"] == seed and info["epochs"] == 10 and info["batch_size"] == 512, "Wrong response run identity/budget")
            need(info["bundle_sha256"] == grid["bundle_sha256"] and info["protocol_sha256"] == grid["protocol_sha256"] and info["source_files"] == expected_source and info["export_manifest_sha256"] == export_sha and info["normalizers_sha256"] == normal_sha, "Unmatched response run provenance")
            need(math.isfinite(info["seconds"]) and 0 <= info["seconds"] <= 600, "Response run duration")
            artifacts(path, info["outputs_sha256"], ("checkpoint.pt", "predictions.npz", "gain_diagnostic.json"))
            fit = info["fit"]
            need(fit["fit_rows"] == fitrows and fit["fit_weight_mean"] == weightmeans and fit["steps"] == 10 * math.ceil(d / 512) and fit["order_sha256"] == orders and len(fit["history"]) == 10, "Response schedule/population mismatch")
            for epoch, row in enumerate(fit["history"]):
                need(row["epoch"] == epoch + 1 and row["draws_per_horizon"] == d and math.isfinite(row["training_loss"]), "Incomplete response history")
                lr = 3e-5 + (3e-4 - 3e-5) * (1 + math.cos(math.pi * epoch / 10)) / 2
                need(abs(row["lr"] - lr) < 1e-15, "Response LR schedule")
            records[(arm, seed)] = info
    for seed in SEEDS:
        first = records[("A", seed)]
        for arm in CONTROLS["response"]:
            info = records[(arm, seed)]
            need(info["fit"]["initial_state_sha256"] == first["fit"]["initial_state_sha256"], "Response initial models differ")
            for field in ("runtime", "device", "objective"):
                need(info[field] == first[field], "Response controls differ in " + field)
    runtimes = [r["runtime"] for r in records.values()]
    need(all(r == runtimes[0] for r in runtimes), "Response runtime differs across seeds")
    r = runtimes[0]
    need(r["deterministic"] is True and r["tf32_matmul"] is False and r["tf32_cudnn"] is False and r["cublas_workspace_config"] == ":4096:8" and r["threads"] == 2, "Response runtime flags")
    return report, records


def exposure_plan(m):
    plans = {}
    for t in TIMES:
        p = population(m, "fit", t)
        labels = np.floor(p["targets"] / .1 + 1e-5).astype(np.int64)
        need((p["targets"] >= 0).all() and (labels < 66).all(), "Unsupported exposure fitting target")
        band = np.minimum(labels // 10, 5)
        mass = np.bincount(band, weights=p["weights"], minlength=6)
        need((mass > 0).all(), "Empty fixed exposure band")
        correction = -.5 * np.log(mass)[np.minimum(np.arange(66) // 10, 5)]
        q = p["weights"] * np.exp(correction[labels]); q /= q.sum()
        plans[t] = {"pop": p, "labels": labels, "P": p["weights"] / p["weights"].sum(), "Q": q,
                    "sampling": {"weighted_band_counts": mass.tolist(), "fine_counts": np.bincount(labels, weights=p["weights"], minlength=66).tolist(), "log_adjustment": correction.tolist()}}
    return plans


def exposure_orders(plans, control, seed):
    # CPU Generator only. No model, CUDA initialization, or checkpoint load.
    import torch
    generator = torch.Generator(device="cpu").manual_seed(seed)
    d = max(len(plan["labels"]) for plan in plans.values())
    result = []
    for _ in range(10):
        epoch = {}
        for t in TIMES:
            plan = plans[t]
            weights = plan["Q"] if control == "band_exposure_ce" else plan["P"]
            chosen = torch.multinomial(torch.tensor(weights, dtype=torch.float64), d, replacement=True, generator=generator).numpy()
            epoch[str(t)] = {"position_order_sha256": array_sha(chosen, "exposure"),
                "source_order_sha256": array_sha(plan["pop"]["source_rows"][chosen], "exposure"),
                "draws": d, "unique_rows": len(np.unique(chosen)),
                "unique_events": len(np.unique(plan["pop"]["events"][chosen])),
                "band_draw_counts": np.bincount(np.minimum(plan["labels"][chosen] // 10, 5), minlength=6).tolist()}
        result.append(epoch)
    return result, str(torch.__version__)


def verify_exposure(root, m, export_sha, contract, grid_sha):
    grid = hashed_json(root / "manifest.json", grid_sha)
    need(json_value(root / "COMPLETE.json")["manifest_sha256"] == grid_sha and grid["status"] == "complete", "Exposure grid incomplete")
    status = json_value(root / "job_status.json")
    need(status["status"] == "complete" and status["exitcode"] == 0 and status["timed_out"] is False, "Exposure supervisor incomplete")
    need(status["configuration"] == grid["configuration"], "Supervisor/grid config mismatch")
    expected_source = {k: v for k, v in contract["files"]["exposure"].items() if k.endswith(".py")}
    need(grid["source_sha256"] == expected_source, "Exposure source changed")
    config = grid["configuration"]
    need(config["export_sha256"] == export_sha and config["model_sha256"] == contract["files"]["response"]["response_model.py"] and config["data_sha256"] == contract["files"]["response"]["response_data.py"], "Exposure shared source/export pins")
    artifacts(root, grid["outputs_sha256"], ("normalizers.npz", "normalizers_provenance.json", "report.json", "predictions.npz"))
    report = json_value(root / "report.json")
    protocol = contract["files"]["exposure"]["AUDIT_AND_FIXED_PROTOCOL.md"]
    need(report["protocol_sha256"] == protocol and report["metrics_source_sha256"] == expected_source["exposure_metrics.py"], "Exposure report source/protocol")
    provenance, _ = normalizers(root, m, export_sha, contract, "exposure")
    plans = exposure_plan(m)
    expected_population = {str(t): population_identity(plans[t]["pop"], t, "fit") for t in TIMES}
    population_sha = compact_sha(expected_population)
    identity = grid["binding_identity"]
    need(identity["export_sha256"] == export_sha and identity["backbone_sha256"] == config["model_sha256"] and identity["normalizers_sha256"] == compact_sha(provenance) and identity["normalizer_provenance"] == provenance, "Exposure binding provenance")
    need(identity["population_sha256"] == population_sha and identity["normalizer_fit_population_sha256"] == population_sha and identity["architecture"] == "B-native-late" and identity["expected_parameters"] == 380706, "Exposure fitting identity")
    need(identity["adapter_sha256"] == expected_source["shared_response_adapter.py"] and identity["runner_sha256"] == expected_source["run_exposure_grid.py"], "Exposure binding code")
    d = max(len(p["labels"]) for p in plans.values())
    records, configs = {}, {}
    expected_optimizer = {"name": "AdamW", "lr": 3e-4, "weight_decay": 1e-4, "cosine_eta_min": 3e-5, "gradient_clip": 5.}
    for seed in SEEDS:
        orders = {}
        for control in CONTROLS["exposure"]:
            path = root / f"{control}_seed{seed}"
            done = json_value(path / "completed.json")
            c = hashed_json(path / "identity.json", done["identity_sha256"])
            history = hashed_json(path / "history.json", done["history_sha256"])
            need(file_sha(path / "latest.pth") == done["checkpoint_sha256"], "Exposure checkpoint changed")
            need(done["control"] == c["control"] == control and done["seed"] == c["seed"] == seed and done["completed_epoch"] == c["epochs"] == 10 and c["batch_size"] == 512, "Exposure run identity/budget")
            need(c["protocol_sha256"] == protocol and c["implementation_sha256"] == expected_source["exposure_training.py"] and c["identity"] == identity and c["population"] == expected_population and c["sampling"] == {str(t): p["sampling"] for t, p in plans.items()}, "Exposure training source/population/sampler")
            need(c["parameters"] == 380706 and c["optimizer"] == expected_optimizer and c["draws_per_horizon_per_epoch"] == d and c["runtime"] == grid["runtime"], "Exposure matched training config")
            need(done["initial_model_sha256"] == c["initial_model_sha256"] and done["fit_population_sha256"] == population_sha, "Exposure completion identity")
            law = "Q" if control == "band_exposure_ce" else "P"
            if law not in orders:
                orders[law], torch_version = exposure_orders(plans, control, seed)
                need(c["runtime"]["torch"] == torch_version, "Sampler replay requires original Torch version")
            need(len(history) == 10, "Exposure incomplete history")
            for epoch, entry in enumerate(history):
                need(entry["completed_epoch"] == epoch + 1 and entry["orders"] == orders[law][epoch], "Exposure sampler order/remainder mismatch")
                need(set(entry["loss"]) == {str(t) for t in TIMES} and all(math.isfinite(v) for v in entry["loss"].values()), "Exposure invalid losses")
            records[(control, seed)], configs[(control, seed)] = done, c
    for seed in SEEDS:
        need(len({configs[(c, seed)]["initial_model_sha256"] for c in CONTROLS["exposure"]}) == 1, "Exposure initial models differ")
    need(report["checkpoints"] == [records[(c, s)] for c in CONTROLS["exposure"] for s in SEEDS], "Report checkpoint binding")
    runtime = grid["runtime"]
    need(runtime["deterministic"] is True and runtime["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8" and runtime["torch_num_threads"] == config["threads"], "Exposure deterministic flags")
    return report, records


def panel_predictions(root, kind, metadata, t, subset):
    ix = rows(metadata, subset, t)
    result = {}
    if kind == "response":
        expected_keys = {prefix + f"{time}_{s}" for time, s in PANELS for prefix in ("rows_", "p_")}
        for control in CONTROLS[kind]:
            for seed in SEEDS:
                with np.load(root / f"{control}_{seed}" / "predictions.npz", allow_pickle=False) as f:
                    need(set(f.files) == expected_keys, "Response PMF archive fields")
                    need(np.array_equal(f[f"rows_{t}_{subset}"], ix), "Response prediction row order")
                    result[(control, str(seed))] = probability(f[f"p_{t}_{subset}"], len(ix))
    else:
        with np.load(root / "predictions.npz", allow_pickle=False) as f:
            expected_keys = {f"{c}__{seed}__{time}__{s}" for c in CONTROLS[kind] for seed in SEEDS for time, s in PANELS}
            expected_keys |= {f"panel__{time}__{s}__{key}" for time, s in PANELS for key in ("source_rows", "events", "stations", "targets", "weights", "unit", "family")}
            need(set(f.files) == expected_keys, "Exposure PMF archive fields")
            p = population(metadata, subset, t)
            for key, value in p.items():
                need(np.array_equal(f[f"panel__{t}__{subset}__{key}"], value), "Exposure PMF metadata mismatch: " + key)
            family = np.array(["HH", "EH", "HN", "HL", "EN", "unknown"])[metadata["static"][ix, :6].argmax(1)]
            for key, value in (("unit", metadata["native_units"][ix]), ("family", family)):
                need(np.array_equal(f[f"panel__{t}__{subset}__{key}"], value), "Exposure reporting strata mismatch")
            for control in CONTROLS[kind]:
                for seed in SEEDS:
                    result[(control, str(seed))] = probability(f[f"{control}__{seed}__{t}__{subset}"], len(ix))
    for control in CONTROLS[kind]:
        result[(control, "ensemble")] = (result[(control, str(SEEDS[0]))] + result[(control, str(SEEDS[1]))]) / 2
    return result


def replay_report(root, kind, metadata, report):
    expected_keys = {(c, seed, t, s) for c in CONTROLS[kind] for seed in [*map(str, SEEDS), "ensemble"] for t, s in PANELS}
    score_rows = {}
    for row in report["scores"]:
        control = row["arm"] if kind == "response" else row["control"]
        name = row["seed"] if kind == "response" else row["seed_or_ensemble"]
        if name == "equal_pmf_ensemble": name = "ensemble"
        key = (control, name, row["seconds"], row["subset"])
        need(key not in score_rows, "Duplicate reported score")
        score_rows[key] = row
    need(set(score_rows) == expected_keys, "Report omits a fixed seed/control/panel")
    comparisons = report["comparisons"]
    # Validate all comparison membership before calculating anything interpretive.
    gate(comparisons, kind)
    replayed = []; supplementary = []; worst_comparisons = []; max_point = 0.
    for t, subset in sorted(PANELS):
        p = population(metadata, subset, t); y, w, event = p["targets"], p["weights"], p["events"]
        predictions = panel_predictions(root, kind, metadata, t, subset)
        computed = {}; full_scores = {}
        for (control, seed), pmf in predictions.items():
            full = scores(pmf, y, w, event, kind)
            expected = reported_scores(full, kind)
            row = score_rows[(control, seed, t, subset)]
            actual = row["metrics"]
            if kind == "exposure":
                actual = {k: v for k, v in actual.items() if k != "strata"}
                need(row["pmf_sha256"] == array_sha(pmf, "exposure"), "Reported PMF digest mismatch")
            compare_values(actual, expected, f"{kind}.{control}.{seed}.{t}.{subset}")
            computed[(control, seed)] = expected
            full_scores[(control, seed)] = full
            supplementary.append({"control": control, "seed_or_ensemble": seed, "seconds": t, "subset": subset,
                                  **{action: {"cvar95": full[action]["cvar95"], **full[action]["supplementary"]}
                                     for action in ("mean", "median")}})
            max_point = max(max_point, abs(actual["mean"]["weighted_mae"] - expected["mean"]["weighted_mae"]))
        candidate = "C" if kind == "response" else "band_exposure_ce"
        references = ("B",) if kind == "response" else ("huber_ce", "natural_ce")
        for reference in references:
            for name in [*map(str, SEEDS), "ensemble"]:
                for action in ("mean", "median"):
                    a = full_scores[(candidate, name)][action]
                    b = full_scores[(reference, name)][action]
                    delta = {"cvar95": a["cvar95"] - b["cvar95"],
                        **{key: a["supplementary"][key] - b["supplementary"][key]
                           for key in ("weighted_p95_abs_error", "maximum_abs_error")}}
                    worst_comparisons.append({"seconds": t, "subset": subset, "candidate": candidate,
                        "reference": reference, "seed_or_ensemble": name, "action": action,
                        "candidate_minus_reference": delta, "any_observed_regression": any(v > 0 for v in delta.values()),
                        "interpretation": "Descriptive observed errors, no added gate or uncertainty guarantee"})
            matches = [r for r in comparisons if r["seconds"] == t and r["subset"] == subset and (kind == "response" or r["reference_control"] == reference)]
            need(len(matches) == 1, "Ambiguous comparison")
            row = matches[0]
            boot = bootstrap(predictions[(candidate, "ensemble")], predictions[(reference, "ensemble")], y, w, event, kind)
            compare_values(row["bootstrap"], boot, "bootstrap")
            cm, rm = computed[(candidate, "ensemble")], computed[(reference, "ensemble")]
            individual = {e: value["mae"] - rm["mean"]["individual_events"][e]["mae"] for e, value in cm["mean"]["individual_events"].items()}
            compare_values(row["individual_event_mae_deltas"], individual, "event deltas")
            sampled = int((metadata["subset"] == subset).sum())
            valid_fraction = len(y) / sampled
            if kind == "response":
                expected_delta = {str(seed): deltas(computed[(candidate, str(seed))]["mean"], computed[(reference, str(seed))]["mean"]) for seed in SEEDS}
                compare_values(row["seed_deltas"], expected_delta, "seed deltas")
                compare_values(row["ensemble_deltas"], deltas(cm["mean"], rm["mean"]), "ensemble deltas")
                need(row["m4_events"] == len(np.unique(event[y >= 4])), "Gate tail support changed")
            else:
                for field, expected in (("candidate", cm), ("reference", rm)):
                    need(set(row[field]) == {"mean", "median", "distribution", "strata"} and row[field]["strata"] == {}, "Exposure comparison metric schema")
                    compare_values({k: v for k, v in row[field].items() if k != "strata"}, expected, field)
                seed_delta = [deltas(computed[(candidate, str(seed))]["mean"], computed[(reference, str(seed))]["mean"])["m4_event_macro_mae"] for seed in SEEDS]
                compare_values(row["seed_m4_event_macro_deltas"], seed_delta, "seed tail deltas")
                fit_mask = metadata["subset"] == "fit"
                valid_fraction = min(valid_fraction, float(metadata["valid"][fit_mask, TIMES.index(t)].mean()))
            compare_values(row["valid_fraction"], valid_fraction, "Gate valid fraction")
            independent_row = {"seconds": t, "subset": subset, "bootstrap": boot,
                               "valid_fraction": valid_fraction, "individual_event_mae_deltas": individual}
            if kind == "response":
                independent_row.update(m4_events=len(np.unique(event[y >= 4])), seed_deltas=expected_delta,
                                       ensemble_deltas=deltas(cm["mean"], rm["mean"]))
            else:
                independent_row.update(reference_control=reference, candidate=cm, reference=rm,
                                       seed_m4_event_macro_deltas=seed_delta)
            replayed.append(independent_row)
    # Metric comparison has a numeric tolerance; gate thresholds have none.
    # Evaluate the independently computed values to prevent a tiny reported
    # perturbation from changing strict tail-improvement/uncertainty decisions.
    def comparison_key(row):
        return (row.get("reference_control"), row["seconds"], row["subset"])
    independent_by_key = {comparison_key(row): row for row in replayed}
    independent_gate = gate([independent_by_key[comparison_key(row)] for row in comparisons], kind)
    compare_values(report["gate"], independent_gate, "fixed gate")
    return {"score_rows_checked": len(score_rows), "comparisons_checked": len(replayed), "gate": independent_gate,
            "maximum_weighted_mae_replay_difference": max_point, "supplementary": supplementary,
            "worst_error_contrasts": worst_comparisons,
            "task_success_caution": "A primary gate pass does not establish the broader objective if worst-error performance regresses"}


def audit(root, export, kind, grid_sha, export_sha, contract_path, contract_sha):
    started = time.monotonic()
    contract = hashed_json(contract_path, contract_sha)
    m, _ = metadata_export(export, export_sha)
    verify = verify_response if kind == "response" else verify_exposure
    report, records = verify(root, m, export_sha, contract, grid_sha)
    output = replay_report(root, kind, m, report)
    output.update(status="pass", kind=kind, seconds=time.monotonic() - started, runs_verified=len(records),
                  grid_manifest_sha256=grid_sha, export_manifest_sha256=export_sha,
                  source_contract_sha256=contract_sha, point_support=support(kind).tolist(),
                  scope="Saved TRAIN-derived held-panel PMF and metadata audit; no waveform/model inference",
                  limitations=["Checkpoint bytes verified, contents not deserialized and forward predictions not replayed",
                               "Normalizer provenance/arrays verified; statistics not refitted from waveforms",
                               "Unit/family/station stratum scores and matched-event subpanels not replayed in this audit",
                               "No cross-grid pooling; no original DEV/TEST reads; P95/worst are supplementary"])
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=list(CONTROLS), required=True)
    for name in ("root", "export", "contract", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("grid-sha256", "export-sha256", "contract-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({"execute": False, "kind": args.kind, "scope": "No artifact reads or output writes"}))
        return 0
    for value in (args.grid_sha256, args.export_sha256, args.contract_sha256):
        need(len(value) == 64 and set(value) <= set("0123456789abcdef"), "Require exact SHA256 pins")
    need(not args.output.exists(), "Audit output must be new")
    result = audit(args.root, args.export, args.kind, args.grid_sha256, args.export_sha256, args.contract, args.contract_sha256)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({k: result[k] for k in ("status", "kind", "seconds", "runs_verified", "score_rows_checked")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

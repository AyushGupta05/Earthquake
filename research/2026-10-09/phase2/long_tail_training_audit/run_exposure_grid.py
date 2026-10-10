"""Bounded fixed six-run exposure comparison; dry-run is the default.

Only the guarded worker imports Torch or opens the explicitly pinned export.
There is no test dataset argument, calibration selection or epoch override.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import signal
import sys
import tempfile
import time


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name, delete=False) as f:
        temporary = Path(f.name)
        try:
            f.write((json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())
            f.flush(); os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def atomic_npz(path, arrays):
    import numpy as np
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name, delete=False) as f:
        temporary = Path(f.name)
        try:
            if any(np.asarray(v).dtype.hasobject for v in arrays.values()):
                raise ValueError("Object arrays are forbidden in prediction artifacts")
            np.savez_compressed(f, **arrays)
            f.flush(); os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _child_entry(target, args):
    os.setsid()
    target(*args)


def run_guarded(target, args, seconds, *, grace=30.):
    """Fresh spawned process, then TERM and KILL if the whole-job budget expires.

    This bounds hashing, normalization, all fits and assessment together. The
    worker has no subprocess/data-loader workers. Its own process group is still
    killed defensively, leaving already atomically completed epochs intact.
    """
    if not 0 < seconds <= 43200 or not 0 <= grace <= 30:
        raise ValueError("Require a positive budget up to12hours and grace up to30seconds")
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=_child_entry, args=(target, args))
    start = time.monotonic()

    def terminated(signum, frame):
        raise SystemExit(128 + signum)

    previous_term = signal.signal(signal.SIGTERM, terminated)

    def stop():
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            if process.is_alive():
                process.terminate()
        process.join(grace)
        if process.is_alive():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                if process.is_alive():
                    process.kill()
            process.join()
    try:
        process.start()
        process.join(max(0., seconds - (time.monotonic() - start)))
        timed_out = process.is_alive()
        if timed_out:
            stop()
        return {"timed_out": timed_out, "exitcode": process.exitcode,
                "elapsed_seconds": time.monotonic() - start,
                "maximum_seconds": float(seconds), "termination_grace_seconds": float(grace)}
    finally:
        # An interrupted supervisor must not leave its training child running.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        try:
            if process.is_alive():
                stop()
            process.close()
        finally:
            signal.signal(signal.SIGTERM, previous_term)


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify_pins(config):
    paths = {"model_sha256": Path(config["response_source"]) / "response_model.py",
             "data_sha256": Path(config["response_source"]) / "response_data.py",
             "export_sha256": Path(config["export_dir"]) / "manifest.json"}
    for key, path in paths.items():
        if file_sha(path) != config[key]:
            raise ValueError("Pinned source/export changed: " + key)


def verify_export_bytes(dataset):
    for name, expected in dataset.manifest["outputs_sha256"].items():
        if name not in ("counts.npy", "metadata.npz") or file_sha(dataset.path / name) != expected:
            raise ValueError("Immutable export bytes changed during the experiment")


def held_panels(dataset):
    """Construct assessment identities after all runs finish; no row replacement."""
    import numpy as np
    from exposure_training import HORIZONS, PrefixPopulation
    m = dataset.metadata
    family_names = np.array(["HH", "EH", "HN", "HL", "EN", "unknown"])
    family_bits = np.asarray(m["static"])[:, :6]
    if not np.isin(family_bits, [0, 1]).all() or not (family_bits.sum(1) == 1).all():
        raise ValueError("Require exact released family one-hot metadata")
    units = np.asarray(m["native_units"], dtype=str)
    if units.shape != m["targets"].shape or not np.isin(units, ["m/s", "m/s^2"]).all():
        raise ValueError("Native unit reporting metadata is missing or invalid")
    families = family_names[family_bits.argmax(1)]
    populations, strata, fractions, audit = {}, {}, {}, []
    fit = m["subset"] == "fit"
    for j, t in enumerate(HORIZONS):
        fit_fraction = float(m["valid"][fit, j].mean())
        for subset in ("eval_seen", "eval_held"):
            sampled = m["subset"] == subset
            ix = np.flatnonzero(sampled & m["valid"][:, j])
            if not sampled.any() or not len(ix):
                raise ValueError("Frozen held panel is empty; do not substitute another population")
            p = PrefixPopulation(t, subset, m["source_row_index"][ix], m["source_id"][ix],
                                 m["station_group"][ix], m["targets"][ix], m["sampling_weight"][ix])
            populations[(t, subset)] = p
            strata[(t, subset)] = {"unit": units[ix], "family": families[ix]}
            fraction = float(len(ix) / sampled.sum())
            # Same unweighted sampled-record validity law as the frozen probe;
            # a held panel cannot hide low fitting-prefix validity.
            fractions[(t, subset)] = min(fit_fraction, fraction)
            audit.append({"seconds": t, "subset": subset, "sampled_records": int(sampled.sum()),
                          "valid_records": len(ix), "valid_fraction": fraction,
                          "fit_valid_fraction": fit_fraction,
                          "gate_valid_fraction": fractions[(t, subset)]})
    return populations, strata, fractions, audit


def fine_bin_support(plans, populations):
    import numpy as np
    from exposure_training import labels_and_support
    result = []
    for (t, subset), population in sorted(populations.items()):
        labels, support = labels_and_support(population.targets)
        empty = np.flatnonzero(plans[t].fine_counts == 0)
        occupied = np.unique(labels[support])
        rows = []
        for label in np.intersect1d(empty, occupied):
            ix = labels == label
            rows.append({"label": int(label), "records": int(ix.sum()),
                         "events": len(np.unique(population.events[ix])),
                         "restoration_mass": float(population.weights[ix].sum())})
        result.append({"seconds": t, "subset": subset, "fit_empty_labels": empty.tolist(),
                       "held_occupied_fit_empty": rows,
                       "unsupported_held_records": int((~support).sum()),
                       "unsupported_held_events": len(np.unique(population.events[~support]))})
    return result


def worker(config):
    # Set before importing Torch or the shared model on this fresh process.
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    import numpy as np
    import torch
    from exposure_training import CONTROLS, SEEDS, fit_control, require_completed_grid, configure_runtime
    from exposure_metrics import evaluate_completed_grid
    from shared_response_adapter import bind_shared_response
    output = Path(config["output"])
    torch.set_num_threads(config["threads"])
    runtime = configure_runtime()
    if config["device"] == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but unavailable; do not silently change runtime")
    verify_pins(config)
    source = Path(config["response_source"])
    model_module = _load_module("exposure_shared_response_model", source / "response_model.py")
    data_module = _load_module("exposure_shared_response_data", source / "response_data.py")
    dataset = data_module.CompletedExport(config["export_dir"])
    normalizers, provenance = data_module.fit_export_normalizers(dataset)
    binding = bind_shared_response(dataset, normalizers, provenance,
        model_module.ResponseConditionedModel, data_module.fitting_population_digest)
    binding.identity["runner_sha256"] = file_sha(__file__)
    source_names = ("exposure_training.py", "exposure_metrics.py", "shared_response_adapter.py", "run_exposure_grid.py")
    manifest = {"schema": "eew-exposure-grid-v1", "status": "started", "configuration": config,
                "runtime": runtime, "binding_identity": binding.identity,
                "source_sha256": {name: file_sha(Path(__file__).with_name(name)) for name in source_names}}
    atomic_npz(output / "normalizers.npz", normalizers)
    atomic_json(output / "normalizers_provenance.json", provenance)
    atomic_json(output / "manifest.json", manifest)
    directories = {}
    for control in CONTROLS:
        for seed in SEEDS:
            path = output / f"{control}_seed{seed}"
            print(json.dumps({"stage": "fit", "control": control, "seed": seed}), flush=True)
            fit_control(binding.model_factory, binding.loader, binding.plans, control, seed, path,
                        binding.identity, device=config["device"])
            directories[(control, seed)] = path
    require_completed_grid(directories)
    verify_pins(config); verify_export_bytes(dataset)
    print(json.dumps({"stage": "all6_complete_fixed_assessment"}), flush=True)
    populations, strata, fractions, validity = held_panels(dataset)
    report, predictions = evaluate_completed_grid(directories, binding.model_factory, binding.loader,
        populations, strata, fractions, identity=binding.identity,
        population_validator=binding.validate_population, device=config["device"])
    report["validity"] = validity
    report["fine_bin_support"] = fine_bin_support(binding.plans, populations)
    report["evaluation_runtime"] = dict(runtime, device=config["device"], batch_size=512)
    atomic_json(output / "report.json", report)
    arrays = {f"{c}__{s}__{t}__{subset}": pmf for (c, s, t, subset), pmf in predictions.items()}
    for (t, subset), p in populations.items():
        for key in ("source_rows", "events", "stations", "targets", "weights"):
            arrays[f"panel__{t}__{subset}__{key}"] = getattr(p, key)
        for key, value in strata[(t, subset)].items():
            arrays[f"panel__{t}__{subset}__{key}"] = np.asarray(value, dtype=str)
    atomic_npz(output / "predictions.npz", arrays)
    verify_pins(config); verify_export_bytes(dataset)
    if any(file_sha(Path(__file__).with_name(name)) != digest for name, digest in manifest["source_sha256"].items()):
        raise ValueError("Exposure implementation changed during the experiment")
    manifest.update(status="complete", outputs_sha256={name: file_sha(output / name) for name in
        ("normalizers.npz", "normalizers_provenance.json", "report.json", "predictions.npz")})
    atomic_json(output / "manifest.json", manifest)
    atomic_json(output / "COMPLETE.json", {"manifest_sha256": file_sha(output / "manifest.json")})
    print(json.dumps({"stage": "complete", "gate": report["gate"]}), flush=True)


def sha_argument(value):
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise argparse.ArgumentTypeError("Require an exact lowercase SHA256")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("export-dir", "response-source", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("export-sha256", "model-sha256", "data-sha256"):
        parser.add_argument("--" + name, type=sha_argument, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--max-seconds", type=int, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not 0 < args.max_seconds <= 43200 or not 1 <= args.threads <= 16:
        parser.error("Budget must be1–43200seconds and threads1–16")
    config = {k: str(v.resolve()) if isinstance(v, Path) else v for k, v in vars(args).items() if k != "execute"}
    if not args.execute:
        print(json.dumps({"execute": False, "scope": "Fixed3controls x2seeds x10epochs; no data reads", "configuration": config}))
        return 0
    output = Path(config["output"])
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "job_status.json", {"status": "started", "configuration": config})
    try:
        result = run_guarded(worker, (config,), args.max_seconds)
    except BaseException as error:
        atomic_json(output / "job_status.json", {"status": "interrupted", "error_type": type(error).__name__,
                                               "configuration": config})
        raise
    success = not result["timed_out"] and result["exitcode"] == 0 and (output / "COMPLETE.json").is_file()
    atomic_json(output / "job_status.json", dict(result, status="complete" if success else "incomplete", configuration=config))
    return 0 if success else 124 if result["timed_out"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

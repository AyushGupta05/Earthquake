"""Dry by default; execute only against a parent-authorized completed baseline.

The parent must wrap the CLI in a 600-second process-group timeout as an outer
resource safeguard. The CLI also supervises its single worker with a <=600 s
wall timeout. No training, checkpoint choice, held-out metrics or new head.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from guards import (SOURCES, PROTOCOL_SHA, CONFIG_FIELDS, check_sha, epoch_sequence,
                    fit_rows_only, project_run, read_json, select_population, sha,
                    validate_completion, validate_plan, validate_splits, verify)

OWN_FILES = ("run_diagnostic.py", "guards.py", "floor_math.py", "protocol_amendment.json")


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    os.replace(temporary, path)


def preflight(args):
    """Reads only pinned source/protocol/plan; no artifact existence/data reads."""
    if not 1 <= args.max_seconds <= 600 or not 1 <= args.batch_size <= 64:
        raise ValueError("Runtime must be <=600 seconds, batch size 1..64")
    verify(args.plan, args.plan_sha256)
    plan = read_json(args.plan)
    validate_plan(plan)
    if args.protocol_sha256 != PROTOCOL_SHA:
        raise ValueError("Only the frozen preregistration is supported")
    verify(args.protocol, PROTOCOL_SHA)
    verify(args.source_manifest, args.source_manifest_sha256)
    bundle = read_json(args.source_manifest)
    if set(bundle) != {"schema", "own", "dependencies", "protocol_sha256"} or bundle["schema"] != "chile_floor_sources_v1":
        raise ValueError("Invalid reviewed-source allowlist")
    if set(bundle["own"]) != set(OWN_FILES) or bundle["dependencies"] != SOURCES or bundle["protocol_sha256"] != PROTOCOL_SHA:
        raise ValueError("Reviewed-source allowlist changed")
    for name, digest in bundle["own"].items():
        verify(Path(__file__).with_name(name), digest)
    for name, digest in SOURCES.items():
        verify(args.source_dir / name, digest)
    amendment = read_json(Path(__file__).with_name("protocol_amendment.json"))
    if amendment["parent_protocol_sha256"] != PROTOCOL_SHA or amendment["maximum_runtime_seconds"] != 600:
        raise ValueError("Execution amendment changed")
    return plan, bundle


def import_sources(source_dir):
    source_dir = source_dir.resolve()
    sys.path.insert(0, str(source_dir))
    loaded = {}
    for module in ("team_lm", "training_artifacts", "train_team_lm"):
        loaded[module] = importlib.import_module(module)
        if Path(loaded[module].__file__).resolve() != source_dir / (module + ".py"):
            raise ValueError("Source import resolved outside the pinned directory")
    return loaded["team_lm"], loaded["train_team_lm"]


def verify_metadata_contract(plan, manifest, metadata_manifest):
    if (manifest.get("schema") != "chile-team-prefix-v1" or manifest.get("stored_samples") != 3000
            or manifest.get("source_test_waveforms_read") is not False
            or manifest.get("all_event_readback_verified") is not True
            or manifest.get("sha256") != plan["artifacts"]["cache"]["sha256"]):
        raise ValueError("A completed full-length no-TEST export is required")
    if (metadata_manifest.get("cache_sha256") != manifest["sha256"]
            or metadata_manifest.get("origin") != "metadata/event_metadata"
            or metadata_manifest.get("columns") != ["EVENT", "MA", "TIME", "source_row_index", "benchmark_split"]
            or metadata_manifest.get("sha256") != plan["artifacts"]["metadata"]["sha256"]):
        raise ValueError("Invalid pinned metadata sidecar contract")


def verify_hdf_headers(path, manifest, split_ids, selected, station_cap):
    import h5py
    import numpy as np
    with h5py.File(path, "r") as handle:
        if handle.attrs.get("schema") != "chile-team-prefix-v1" or int(handle.attrs.get("stored_samples", 0)) != 3000:
            raise ValueError("Cache header schema mismatch")
        for key, value in (("sampling_rate", 100), ("time_before", 5), ("time_after", 25)):
            if handle["metadata/" + key][()] != value:
                raise ValueError("Wrong exact source timing contract")
        if set(handle["data"]) != set(split_ids["train"] + split_ids["dev"]):
            raise ValueError("Missing/extra waveform groups; TEST must be absent")
        train_end, dev_end = manifest["author_split_boundaries"]
        for split, rows in (("train", range(train_end)), ("dev", range(train_end, dev_end))):
            if (not np.array_equal(handle[f"splits/{split}_event_ids"].asstr()[:], split_ids[split])
                    or not np.array_equal(handle[f"splits/{split}_source_rows"][:], np.asarray(list(rows)))):
                raise ValueError("HDF identity arrays mismatch")
        # Header shapes only; no non-selected waveform dataset is read.
        for row in selected:
            group = handle["data"][row["EVENT"]]
            shape = group["waveforms"].shape
            if len(shape) != 3 or shape[1:] != (3000, 3) or not 1 <= shape[0] <= station_cap or group["coords"].shape != (shape[0], 3):
                raise ValueError("Malformed selected event or source station cap would truncate")


def source_forward(model, loader, device, team, trainer):
    """Exactly trainer.evaluate's no-grad forward/casting path, no its metrics."""
    import numpy as np
    import torch
    outputs = {seconds: {k: [] for k in ("logits", "weights", "means", "scales")} for seconds in (1., 3., 5.)}
    targets, events = [], []
    available = {seconds: [] for seconds in outputs}
    model.eval()
    with torch.no_grad():
        for x, coords, mask, y, ids in loader:
            x, coords, mask = x.to(device), coords.to(device), mask.to(device)
            targets.append(y.double())
            events.extend(ids)
            for seconds in outputs:
                mixture = model(x, coords, mask, cutoff_seconds=seconds)
                for name, values in mixture.items():
                    outputs[seconds][name].append(values.double().cpu())
                # Same availability as TeamLM.forward; diagnostic count only.
                _, active = team.prepare_prefix(x, mask, seconds)
                available[seconds].append((active & coords.ne(0).any(-1)).sum(-1).cpu())
    y = torch.cat(targets)
    if len(set(events)) != len(events):
        raise ValueError("Repeated diagnostic event")
    from floor_math import diagnose
    arrays = {"event_ids": np.asarray(events, dtype=str), "targets": y.numpy(), "horizons_seconds": np.asarray([1, 3, 5])}
    for seconds, parts in outputs.items():
        mixture = {key: torch.cat(value) for key, value in parts.items()}
        t = str(int(seconds))
        for key, value in mixture.items():
            arrays[t + "_source_" + key] = value.numpy()
        mean, median = team.mixture_mean(mixture), trainer.mixture_quantile(mixture, .5)
        for key, value in (("mean", mean), ("median", median)):
            arrays[t + "_source_" + key] = value.numpy()
            arrays[t + "_" + key + "_error"] = (value - y).numpy()
        arrays[t + "_available_stations"] = torch.cat(available[seconds]).numpy()
        diagnostics = diagnose(mixture["logits"].numpy(), mixture["means"].numpy(), mixture["scales"].numpy(), y.numpy())
        arrays.update({t + "_" + key: value for key, value in diagnostics.items()})
        arrays[t + "_source_weight_mass_error"] = mixture["weights"].sum(-1).numpy() - 1.
        arrays[t + "_mean_underestimation"] = (y - mean).numpy()
    return arrays


def worker(args):
    started = time.monotonic()
    plan, bundle = preflight(args)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "STARTED.json", {"plan_sha256": args.plan_sha256, "protocol_sha256": PROTOCOL_SHA,
                                        "source_manifest_sha256": args.source_manifest_sha256, "optimizer_steps": 0})
    # Explicit execution gate precedes all actual artifact reads, even hashes.
    for item in plan["artifacts"].values():
        verify(item["path"], item["sha256"])
    paths = {k: Path(v["path"]) for k, v in plan["artifacts"].items()}
    manifest, metadata_manifest = read_json(paths["dataset_manifest"]), read_json(paths["metadata_manifest"])
    verify_metadata_contract(plan, manifest, metadata_manifest)
    event_epochs = epoch_sequence(paths["history"], 100)
    pretrain_epochs = epoch_sequence(paths["pretrain_history"], 25)
    run = project_run(read_json(paths["run"]))
    splits = read_json(paths["split_manifest"])
    validate_splits(splits, *manifest["author_split_boundaries"], run)
    import numpy as np
    import pandas as pd
    import h5py
    import torch
    from torch.utils.data import DataLoader
    from floor_math import event_gate
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    checkpoint = torch.load(paths["checkpoint"], map_location="cpu", weights_only=True)
    if set(checkpoint) != {"model", "config", "selected_epoch"}:
        raise ValueError("Only completed model.pth schema is accepted")
    run = validate_completion(run, checkpoint["config"], checkpoint["selected_epoch"], plan, manifest)
    fit_rows, split_ids = fit_rows_only(paths["metadata"], splits, manifest, metadata_manifest)
    selected, fractions = select_population(fit_rows)
    verify_hdf_headers(paths["cache"], manifest, split_ids, selected, run["max_stations"])
    team, trainer = import_sources(args.source_dir)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("Requested GPU unavailable; no silent fallback")
    model = team.TeamLM(run["aggregation"])
    model.load_state_dict(checkpoint["model"], strict=True)
    del checkpoint
    if any(not torch.isfinite(p).all() for p in model.parameters()):
        raise ValueError("Nonfinite checkpoint parameters")
    model.requires_grad_(False).to(device)
    dataset = trainer.EventDataset(paths["cache"], pd.DataFrame(selected), training=False,
                                   max_stations=run["max_stations"], station_drop=0., seed=run["seed"], stored_samples=3000)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False, num_workers=0, collate_fn=trainer.collate_events)
    try:
        arrays = source_forward(model, loader, device, team, trainer)
    finally:
        dataset.close()
    if arrays["event_ids"].tolist() != [r["EVENT"] for r in selected] or not np.array_equal(arrays["targets"], [r["MA"] for r in selected]):
        raise ValueError("Exact forward identity/target order mismatch")
    arrays["source_rows"] = np.asarray([r["source_row_index"] for r in selected], dtype=np.int64)
    arrays["stratum"] = np.asarray([r["stratum"] for r in selected], dtype=str)
    means = np.stack([arrays[f"{t}_source_mean"] for t in (1, 3, 5)], axis=1)
    factors = np.stack([arrays[f"{t}_attenuation"] for t in (1, 3, 5)], axis=1)
    gate = event_gate(arrays["event_ids"], arrays["targets"], means, factors)
    summaries = {}
    for stratum in fractions:
        mask = arrays["stratum"] == stratum
        summaries[stratum] = {}
        for t in (1, 3, 5):
            summaries[stratum][str(t)] = {key: (np.quantile(arrays[f"{t}_{key}"][mask], [0, .25, .5, .75, 1]).tolist() if mask.any() else None)
                                         for key in ("gaussian_log_density", "attenuation", "mean_underestimation", "gaussian_responsibility_entropy")}
    temporary = output / "diagnostics.tmp.npz"
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, output / "diagnostics.npz")
    atomic_json(output / "selection.json", {"events": selected, "inclusion_fractions": fractions})
    atomic_json(output / "summary.json", {"gate": gate, "stratum_quantiles_min_q25_median_q75_max": summaries,
                                        "selection_epoch": run["selected_epoch"], "event_epochs_complete": event_epochs,
                                        "pretrain_epochs_complete": pretrain_epochs, "run_provenance": run,
                                        "runtime": trainer.runtime_identity(device), "device": str(device),
                                        "software": {"python": sys.version, "torch": str(torch.__version__), "numpy": np.__version__,
                                                     "pandas": pd.__version__, "h5py": h5py.__version__},
                                        "elapsed_seconds": time.monotonic() - started, "optimizer_steps": 0,
                                        "calibration_DEV_TEST_forwards": 0, "calibration_DEV_TEST_metrics_consulted": 0,
                                        "note": "Source dataset loads selected fit containers in full; only strict-prefix samples affect the forward. Full-file hashing is integrity verification, not a claim of no non-fit bytes read."})
    # Guard source immutability once more before the completion marker.
    preflight(args)
    files = {name: sha(output / name) for name in ("diagnostics.npz", "selection.json", "summary.json", "STARTED.json")}
    atomic_json(output / "COMPLETE.json", {"schema": "chile_floor_diagnostic_complete_v1", "artifacts": files,
                                          "inputs": plan, "sources": bundle, "plan_sha256": args.plan_sha256,
                                          "source_manifest_sha256": args.source_manifest_sha256, "protocol_sha256": PROTOCOL_SHA})
    print(json.dumps({"output": str(output), "gate": gate}), flush=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--plan-sha256", required=True)
    p.add_argument("--protocol", type=Path, required=True)
    p.add_argument("--protocol-sha256", required=True)
    p.add_argument("--source-dir", type=Path, required=True)
    p.add_argument("--source-manifest", type=Path, required=True)
    p.add_argument("--source-manifest-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--max-seconds", type=int, default=600)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return p


def main():
    args = parser().parse_args()
    if args.worker:
        if not args.execute:
            raise ValueError("Worker requires explicit execution")
        worker(args)
        return
    plan, bundle = preflight(args)
    if not args.execute:
        print(json.dumps({"dry_run": True, "actual_artifacts_opened": 0, "plan_sha256": args.plan_sha256,
                          "sources_verified": bundle, "maximum_runtime_seconds": args.max_seconds,
                          "next_step": "Parent must authorize the completed checkpoint and add --execute"}, indent=2))
        return
    if args.output.exists():
        raise FileExistsError("New output directory required")
    code = supervise([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"], args.max_seconds, args.output)
    if code:
        raise SystemExit(code)


def supervise(command, max_seconds, output):
    """One child in the outer process group; cancellation is synchronous.

    Handlers only record requests, including during Popen and cleanup. Raising
    from a handler can interrupt child ownership/reaping; thread-local signal
    masks do not prevent Python delivery through other native threads.
    """
    cancellation = []
    def cancelled(signum, frame):
        cancellation.append(signum)

    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    process, code = None, None
    deadline = time.monotonic() + max_seconds
    try:
        for sig in previous:
            signal.signal(sig, cancelled)
        process = subprocess.Popen(command)
        while True:
            if cancellation:
                raise SystemExit(128 + cancellation[0])
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, max_seconds)
            try:
                code = process.wait(timeout=min(.1, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        if cancellation:
            raise SystemExit(128 + cancellation[0])
    finally:
        # Our handlers never raise, so further cancellation cannot skip this
        # cleanup even when native threads have unblocked signal delivery.
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
        successful = code == 0 and not cancellation and sys.exc_info()[0] is None
        complete = Path(output) / "COMPLETE.json"
        if not successful and complete.exists():
            complete.unlink()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if cancellation:
        raise SystemExit(128 + cancellation[0])
    return code


if __name__ == "__main__":
    main()

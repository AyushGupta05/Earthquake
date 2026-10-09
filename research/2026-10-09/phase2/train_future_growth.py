"""Bounded future-growth pilot. Explicit export/train subcommands; no auto-launch.

Export opens TRAIN raw traces only. Train reads TRAIN growth and prefix-only
TRAIN/VAL caches; it never constructs VAL/test growth. Defaults are fixed ten
epochs and the exact existing weighted-Huber + .075 CE objective.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import h5py
import numpy as np
import pandas as pd
import torch

from future_growth import (CONTROLS, FutureGrowthModel, PEAK_FLOOR_COUNTS, SAMPLE_RATE,
                           SIGMA_CEILING, SIGMA_FLOOR, auxiliary_loss, clip_gradients, observed_growth)
from feature_residual import ROOT, population_weights
from train_sequential import evaluate, supervised_loss
from frozen_head_pilot import choose_rows
from audit_and_export import require_checkpoint_preprocessing, sha256
from run_artifacts import create_run


META_COLUMNS = ["source_id", "source_magnitude", "trace_name", "trace_P_arrival_sample"]
ARRAY_KEYS = ("rows", "event_ids", "trace_names", "magnitudes", "p_samples", "growth", "valid",
              "reason", "peaks", "baseline", "source_window_sha256")


def array_digest(array):
    a = np.ascontiguousarray(array)
    digest = hashlib.sha256(str(a.dtype).encode() + json.dumps(list(a.shape)).encode())
    digest.update(a.tobytes())
    return digest.hexdigest()


def file_stat(path):
    s = Path(path).stat()
    return {"path": str(Path(path).resolve()), "bytes": s.st_size, "mtime_ns": s.st_mtime_ns}


def read_metadata(root, split, audit):
    path = root / ("train_full_metadata.csv" if split == "train" else "val_metadata.csv")
    if sha256(path) != audit[split]["metadata_sha256"]:
        raise ValueError(f"{split} metadata changed since audit")
    # Preserve pandas' inferred source_id dtype, as load_examples() does.
    # choose_rows sorts groups and consumes one RNG across them: sorting
    # numeric IDs as strings (10 before 2) changes the sampled recordings.
    frame = pd.read_csv(path, usecols=META_COLUMNS, dtype={"trace_name": str})
    if len(frame) == 0 or frame.isna().any().any() or frame.trace_name.duplicated().any():
        raise ValueError(f"Invalid {split} metadata identities")
    if (frame.source_id.astype(str).str.len() == 0).any() or (frame.trace_name.str.len() == 0).any():
        raise ValueError("Empty event/trace identity")
    if not np.isfinite(frame[["source_magnitude", "trace_P_arrival_sample"]].to_numpy()).all():
        raise ValueError("Nonfinite magnitude or P sample")
    p = frame.trace_P_arrival_sample.to_numpy()
    if np.any(p != np.floor(p)) or np.any(p < 0):
        raise ValueError("P samples must be nonnegative integers")
    if frame.groupby("source_id").source_magnitude.nunique().max() != 1:
        raise ValueError("Conflicting event magnitudes")
    return frame


def selected_rows(frame, max_per_event):
    if max_per_event < 0:
        raise ValueError("max_per_event must be nonnegative; zero selects all")
    if max_per_event == 0:
        return np.arange(len(frame), dtype=np.int64)
    return np.union1d(choose_rows(frame, max_per_event),
                     np.flatnonzero(frame.source_magnitude.to_numpy() >= 4)).astype(np.int64)


def validate_cache(group, frame):
    if group["waveforms"].shape != (len(frame), 3, 500):
        raise ValueError("Expected complete 5s cache aligned to metadata")
    if not np.allclose(group["targets"][:], frame.source_magnitude.to_numpy(), atol=1e-6, rtol=0):
        raise ValueError("Cache magnitude target order disagrees with metadata")
    for name, expected in (("trace_names", frame.trace_name), ("event_ids", frame.source_id)):
        if name in group and not np.array_equal(group[name].asstr()[:], expected.to_numpy(dtype=str)):
            raise ValueError(f"Cache {name} order disagrees with metadata")


def export_targets(root, data_dir, output, max_per_event=0, sample_limit=0):
    """Read-only CPU export, returning a manifest; existing output is never replaced."""
    root, data_dir, output = Path(root), Path(data_dir), Path(output)
    if output.exists():
        raise FileExistsError(output)
    if sample_limit < 0:
        raise ValueError("sample_limit must be nonnegative")
    audit_path = root / "results/2026-10-09/audit.json"
    audit = json.loads(audit_path.read_text())
    require_checkpoint_preprocessing({audit["windows"]["5"]["preprocessing"]})
    frame = read_metadata(root, "train", audit)
    rows = selected_rows(frame, max_per_event)
    if sample_limit:
        rows = rows[:sample_limit]
    picked = frame.iloc[rows]
    normal = []
    for name in ("train_mean_full.npy", "train_std_full.npy"):
        if sha256(root / name) != audit["normalization_sha256"][name]:
            raise ValueError("Normalization changed since audit")
        normal.append(np.asarray(np.load(root / name), dtype=np.float32).reshape(3, 1))
    mean, std = normal
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or np.any(std <= 0):
        raise ValueError("Invalid count standardization")
    raw_path = data_dir / "Instance_events_counts.hdf5"
    cache_path = data_dir / audit["windows"]["5"]["cache"]
    raw_identity, cache_identity = file_stat(raw_path), file_stat(cache_path)
    n = len(rows)
    arrays = {
        "rows": rows, "event_ids": picked.source_id.to_numpy(dtype=str),
        "trace_names": picked.trace_name.to_numpy(dtype=str),
        "magnitudes": picked.source_magnitude.to_numpy(dtype=np.float64),
        "p_samples": picked.trace_P_arrival_sample.to_numpy(dtype=np.int64),
        "growth": np.zeros((n, 3), dtype=np.float64), "valid": np.zeros((n, 3), dtype=bool),
        "reason": np.full(n, "missing_trace", dtype="U32"),
        "peaks": np.zeros((n, 4), dtype=np.float64), "baseline": np.zeros(n, dtype=np.float64),
        "source_window_sha256": np.full(n, "", dtype="U64"),
    }
    aligned = 0
    with h5py.File(raw_path, "r") as raw, h5py.File(cache_path, "r") as cache:
        # The released counts file has a roughly 46 MiB group lookup heap.
        # Its default 32 MiB metadata cache rereads that heap for each lookup.
        # This changes I/O caching only; source arrays and target math are identical.
        metadata_cache = raw.id.get_mdc_config()
        metadata_cache.max_size = 128 * 1024**2
        metadata_cache.min_size = 32 * 1024**2
        metadata_cache.initial_size = 128 * 1024**2
        metadata_cache.set_initial_size = 1
        raw.id.set_mdc_config(metadata_cache)
        raw_traces = raw["data"]
        validate_cache(cache["train"], frame)
        cached_waveforms = cache["train/waveforms"]
        for j, i in enumerate(rows):
            name, p = arrays["trace_names"][j], int(arrays["p_samples"][j])
            if name not in raw_traces:
                continue
            ds = raw_traces[name]
            if ds.ndim != 2 or ds.shape[0] != 3:
                raise ValueError(f"Expected INSTANCE ENZ trace for {name}")
            if p + 500 > ds.shape[1]:
                raise ValueError(f"P/5s window is inconsistent with cached input: {name}")
            # Validate every selected available trace, not only matching labels.
            early = np.asarray(ds[:, p:p + 500], dtype=np.float32)
            expected = (early - mean) / (std + np.float32(1e-8))
            if not np.array_equal(cached_waveforms[i], expected):
                raise ValueError(f"Exact raw/cache prefix identity mismatch at TRAIN row {i}")
            aligned += 1
            if p < SAMPLE_RATE:
                arrays["reason"][j] = "missing_pre_p"
                continue
            if p + 1000 > ds.shape[1]:
                arrays["reason"][j] = "missing_future"
                continue
            window = np.asarray(ds[:, p - 100:p + 1000])
            if not np.isfinite(window).all():
                arrays["reason"][j] = "nonfinite_window"
                continue
            g, peaks, baseline = observed_growth(window[2], 100)
            arrays["growth"][j], arrays["peaks"][j], arrays["baseline"][j] = g, peaks, baseline
            arrays["valid"][j], arrays["reason"][j] = True, "ok"
            arrays["source_window_sha256"][j] = array_digest(window)
            if (j + 1) % 10000 == 0:
                print("EXPORTED", j + 1, "TRAIN records", flush=True)
    if raw_identity != file_stat(raw_path) or cache_identity != file_stat(cache_path):
        raise ValueError("Source/cache changed during target export")
    valid = arrays["valid"]
    manifest = {
        "schema": "instance_future_growth_v1", "split": "train", "records": n,
        "metadata_sha256": audit["train"]["metadata_sha256"], "audit_sha256": sha256(audit_path),
        "raw_source": raw_identity, "cache_source": cache_identity,
        "normalization_sha256": audit["normalization_sha256"],
        "arrays_sha256": {k: array_digest(v) for k, v in arrays.items()},
        "selected_max_per_event": max_per_event, "sample_limit": sample_limit,
        "smoke_only": bool(sample_limit), "sampling_seed": 20261009,
        "input_seconds": [1, 3, 5], "target_seconds": 10, "sample_rate_hz": 100,
        "component": "Z, index 2 in documented INSTANCE ENZ order",
        "baseline": "Mean of exactly the preceding 100 samples; same baseline for all peaks",
        "peak_floor_counts": PEAK_FLOOR_COUNTS, "aligned_raw_cache_records": aligned,
        "valid_per_time": valid.sum(0).tolist(),
        "zero_growth_per_time": ((arrays["growth"] == 0) & valid).sum(0).tolist(),
        "reasons": {str(k): int(v) for k, v in zip(*np.unique(arrays["reason"], return_counts=True))},
        "source_limit": "Released counts may already include whole-trace detrending/resampling; not instrument-deconvolved.",
        "source_code_sha256": {p.name: sha256(p) for p in
                               (Path(__file__), Path(__file__).with_name("future_growth.py"))},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents overwriting a concurrently created export.
    with output.open("xb") as handle:
        np.savez_compressed(handle, manifest_json=np.array(json.dumps(manifest, sort_keys=True)), **arrays)
    return manifest


def load_targets(path, frame, rows, metadata_sha, allow_smoke=False):
    with np.load(path, allow_pickle=False) as archive:
        manifest = json.loads(str(archive["manifest_json"]))
        arrays = {key: archive[key] for key in ARRAY_KEYS}
    if manifest["schema"] != "instance_future_growth_v1" or manifest["split"] != "train":
        raise ValueError("Only the TRAIN future-growth schema is accepted")
    if (manifest["input_seconds"] != [1, 3, 5] or manifest["target_seconds"] != 10
            or manifest["sample_rate_hz"] != 100 or manifest["peak_floor_counts"] != PEAK_FLOOR_COUNTS):
        raise ValueError("Future-target horizon, sample rate or floor differs from this pilot")
    if manifest["metadata_sha256"] != metadata_sha:
        raise ValueError("Future targets belong to different metadata")
    if manifest["smoke_only"] and not allow_smoke:
        raise ValueError("Sample-limited targets require --allow-smoke-targets")
    for key, value in arrays.items():
        if array_digest(value) != manifest["arrays_sha256"][key]:
            raise ValueError(f"Future-target digest mismatch: {key}")
    stored = arrays["rows"]
    if stored.ndim != 1 or stored.dtype.kind not in "iu" or np.any(np.diff(stored) <= 0):
        raise ValueError("Future-target rows must be unique and increasing integers")
    if len(stored) == 0 or stored[0] < 0 or stored[-1] >= len(frame):
        raise ValueError("Future-target row outside training metadata")
    sub = frame.iloc[stored]
    for key, expected in (("trace_names", sub.trace_name.to_numpy(dtype=str)),
                          ("event_ids", sub.source_id.to_numpy(dtype=str)),
                          ("magnitudes", sub.source_magnitude.to_numpy(dtype=np.float64)),
                          ("p_samples", sub.trace_P_arrival_sample.to_numpy(dtype=np.int64))):
        if not np.array_equal(arrays[key], expected):
            raise ValueError(f"Exact future-target {key} order mismatch")
    if arrays["growth"].shape != (len(stored), 3) or arrays["valid"].shape != arrays["growth"].shape:
        raise ValueError("Invalid target/mask dimensions")
    if arrays["valid"].dtype != np.bool_ or not np.isfinite(arrays["growth"]).all() or np.any(arrays["growth"] < 0):
        raise ValueError("Invalid nonnegative targets or boolean masks")
    if arrays["peaks"].shape != (len(stored), 4) or arrays["baseline"].shape != (len(stored),):
        raise ValueError("Invalid peak/baseline dimensions")
    complete = arrays["valid"].all(1)
    if not np.array_equal(arrays["valid"], np.repeat(complete[:, None], 3, axis=1)):
        raise ValueError("All horizons must share the same fixed-baseline/10s validity")
    if not np.array_equal(complete, arrays["reason"] == "ok"):
        raise ValueError("Target masks disagree with missing-reason codes")
    peaks = arrays["peaks"][complete]
    if not np.isfinite(peaks).all() or np.any(peaks < PEAK_FLOOR_COUNTS) or np.any(np.diff(peaks, axis=1) < 0):
        raise ValueError("Valid target peaks must be finite, positive and nested")
    derived = np.log10(peaks[:, -1:]) - np.log10(peaks[:, :3])
    if not np.array_equal(arrays["growth"][complete], derived):
        raise ValueError("Growth targets disagree with their recorded nested peaks")
    positions = np.searchsorted(stored, rows)
    if np.any(positions >= len(stored)) or not np.array_equal(stored[positions], rows):
        raise ValueError("Growth archive does not cover every selected training row")
    return arrays["growth"][positions], arrays["valid"][positions], manifest


def load_training_data(args, device):
    root, data_dir = Path(args.root), Path(args.data)
    audit = json.loads((root / "results/2026-10-09/audit.json").read_text())
    require_checkpoint_preprocessing({audit["windows"]["5"]["preprocessing"]})
    frames = {split: read_metadata(root, split, audit) for split in ("train", "val")}
    for column in ("source_id", "trace_name"):
        # Keep inferred types for sampling, but compare the same canonical
        # string identities used by the stored reference across split types.
        if set(frames["train"][column].astype(str)) & set(frames["val"][column].astype(str)):
            raise ValueError(f"Training/validation overlap in {column}")
    rows = selected_rows(frames["train"], args.max_per_event)
    if args.allow_smoke_targets:
        with np.load(args.targets, allow_pickle=False) as a:
            if not json.loads(str(a["manifest_json"]))["smoke_only"]:
                raise ValueError("--allow-smoke-targets is only for sample-limited fixture/pilot exports")
            rows = a["rows"]
    g, valid, manifest = load_targets(args.targets, frames["train"], rows,
                                     audit["train"]["metadata_sha256"], args.allow_smoke_targets)
    cache_path = data_dir / audit["windows"]["5"]["cache"]
    if file_stat(cache_path) != manifest["cache_source"]:
        raise ValueError("Input cache changed since exact growth-source alignment")
    for name, digest in manifest["normalization_sha256"].items():
        if sha256(root / name) != digest or audit["normalization_sha256"][name] != digest:
            raise ValueError("Input normalization changed since target alignment")
    ref_path = root / "results/2026-10-09/validation_5s.npz"
    with np.load(ref_path, allow_pickle=False) as ref:
        baseline = {k: ref[k] for k in ("targets", "event_ids", "trace_names", "centers")}
    for key, expected in (("event_ids", frames["val"].source_id.to_numpy(dtype=str)),
                          ("trace_names", frames["val"].trace_name.to_numpy(dtype=str))):
        if not np.array_equal(baseline[key], expected):
            raise ValueError(f"Validation reference {key} order mismatch")
    if not np.allclose(baseline["targets"], frames["val"].source_magnitude, atol=1e-6, rtol=0):
        raise ValueError("Validation reference magnitude order mismatch")
    if not np.allclose(baseline["centers"], (np.arange(66) + .5) * .1, atol=1e-7, rtol=0):
        raise ValueError("Magnitude bin grid changed")
    waves = {}
    with h5py.File(cache_path, "r") as cache:
        for split, indices in (("train", rows), ("val", np.arange(len(frames["val"])))):
            validate_cache(cache[split], frames[split])
            x = np.empty((len(indices), 3, 500), dtype=np.float32)
            for start in range(0, len(indices), 4096):
                x[start:start + 4096] = cache[f"{split}/waveforms"][indices[start:start + 4096]]
            if not np.isfinite(x).all():
                raise ValueError("Nonfinite cached input")
            waves[split] = torch.from_numpy(x).to(device)
    y = torch.as_tensor(frames["train"].source_magnitude.to_numpy()[rows], dtype=torch.float32, device=device)
    w = torch.as_tensor(population_weights(frames["train"], rows), dtype=torch.float32, device=device)
    return waves, y, w, baseline, rows, torch.tensor(g, dtype=torch.float32, device=device), torch.tensor(valid, device=device), manifest


def train(args):
    if min(args.epochs, args.batch_size) < 1 or args.max_per_event < 0:
        raise ValueError("Invalid training bounds")
    if any(not np.isfinite(x) or x < 0 for x in (args.auxiliary_weight, args.marginal_weight)):
        raise ValueError("Loss weights must be finite and nonnegative")
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    device = torch.device(args.device)
    started = time.monotonic()
    waves, y, w, baseline, rows, growth, valid, manifest = load_training_data(args, device)
    if args.control != "supervised" and not valid.any(0).all():
        raise ValueError("Every auxiliary horizon requires at least one valid TRAIN target")
    config = {**vars(args), "objective": "weighted Huber(delta=1,beta=5,threshold=3.5)+.075 CE",
              "train_rows_sha256": array_digest(rows), "target_archive_sha256": sha256(args.targets),
              "selection": "Fixed final epoch; no validation selection",
              "learning_rate": 3e-4, "weight_decay": 1e-4, "cosine_eta_min": 3e-5,
              "sigma_floor": SIGMA_FLOOR, "sigma_ceiling": SIGMA_CEILING,
              "sampling_seed": 20261009, "smoke_only": manifest["smoke_only"]}
    here = Path(__file__).resolve().parent
    sources = [here / name for name in ("future_growth.py", "train_future_growth.py", "sequential_models.py",
                                        "train_sequential.py", "feature_residual.py", "run_artifacts.py")]
    sources += [here.parent / name for name in ("frozen_head_pilot.py", "audit_and_export.py", "distribution_experiment.py")]
    out = create_run(Path(args.root) / "results/2026-10-09/phase2", f"growth_{args.control}_seed{args.seed}", config, sources)
    print("RUN_DIRECTORY", out, flush=True)
    (out / "target_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    np.savez_compressed(out / "train_rows.npz", rows=rows)
    torch.manual_seed(args.seed)
    model = FutureGrowthModel().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=3e-5)
    # A dedicated CPU generator gives identical row order for every control.
    shuffle = torch.Generator(device="cpu").manual_seed(args.seed)
    labels = (y / .1 + 1e-5).floor().long().clamp(0, 65)
    centers = torch.tensor(baseline["centers"], dtype=torch.float32, device=device)
    history = []
    for epoch in range(args.epochs):
        model.train()
        total = {key: 0. for key in ("supervised", "auxiliary", "marginal", "total")}
        epoch_start = time.monotonic()
        for cpu_ix in torch.randperm(len(y), generator=shuffle).split(args.batch_size):
            ix = cpu_ix.to(device)
            outputs, states = model.forward_with_states(waves["train"][ix])
            base = supervised_loss(outputs, y[ix], w[ix], centers, "weighted")
            extra, parts = auxiliary_loss(model, outputs, states, labels[ix], w[ix], growth[ix], valid[ix],
                                           args.control, args.auxiliary_weight, args.marginal_weight)
            loss = base + extra
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite future-growth training loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            clip_gradients(model)
            optimizer.step()
            for key, value in {"supervised": base, "total": loss, **parts}.items():
                total[key] += value.item() * len(ix)
        scheduler.step()
        log = {"epoch": epoch + 1, "loss": {k: v / len(y) for k, v in total.items()},
               "epoch_seconds": time.monotonic() - epoch_start}
        history.append(log)
        (out / "history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
        print(args.control, log, flush=True)
        # Recovery artifact, not an early-stopping checkpoint.
        temporary = out / "latest.pth.tmp"
        torch.save({"model": model.state_dict(), "optimizer": optimizer.state_dict(),
                    "scheduler": scheduler.state_dict(), "completed_epoch": epoch + 1,
                    "shuffle_rng": shuffle.get_state(), "torch_rng": torch.get_rng_state(),
                    "config": config}, temporary)
        os.replace(temporary, out / "latest.pth")
    result, predictions = evaluate(model.backbone, waves["val"], baseline["targets"], baseline["event_ids"], baseline["centers"])
    torch.save({"model": model.state_dict(), "config": config}, out / "model.pth")
    (out / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    np.savez_compressed(out / "predictions.npz", **baseline, **predictions)
    run = {**config, "parameters": sum(p.numel() for p in model.parameters()), "train_records": len(rows),
           "wall_seconds": time.monotonic() - started, "valid_growth_records": valid.sum(0).cpu().tolist(),
           "data_status": "Reused INSTANCE validation; no validation/test future targets or test predictions",
           "comparison_limit": "Exploratory counts-only backbone; no superiority over instrument-conditioned baseline established"}
    (out / "run.json").write_text(json.dumps(run, indent=2, allow_nan=False) + "\n")
    print("FINISHED", out, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="CPU only, TRAIN target preparation")
    export.add_argument("--root", default=str(ROOT))
    export.add_argument("--data", default="/data")
    export.add_argument("--output", required=True)
    export.add_argument("--max-per-event", type=int, default=0)
    export.add_argument("--sample-limit", type=int, default=0)
    fit = sub.add_parser("train", help="Explicit training invocation; never launched by export")
    fit.add_argument("--root", default=str(ROOT))
    fit.add_argument("--data", default="/data")
    fit.add_argument("--targets", required=True)
    fit.add_argument("--control", choices=CONTROLS, required=True)
    fit.add_argument("--epochs", type=int, default=10)
    fit.add_argument("--seed", type=int, default=20261009)
    fit.add_argument("--batch-size", type=int, default=512)
    fit.add_argument("--max-per-event", type=int, default=4)
    fit.add_argument("--auxiliary-weight", type=float, default=.05)
    fit.add_argument("--marginal-weight", type=float, default=.01)
    fit.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    fit.add_argument("--allow-smoke-targets", action="store_true")
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps(export_targets(args.root, args.data, args.output, args.max_per_event, args.sample_limit), indent=2))
    else:
        train(args)


if __name__ == "__main__":
    main()

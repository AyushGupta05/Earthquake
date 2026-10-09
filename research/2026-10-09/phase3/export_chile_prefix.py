"""Export the author's chronological TRAIN+DEV Chile split without TEST waveforms.

Cache waveforms contain raw float32 samples [0:1000] or [0:3000], i.e. network
first-P -5 through +5 or +25 seconds (exclusive endpoint). No filtering, centering, normalization,
station selection or invented P picks is performed. Use benchmark_split, never
the source's unrelated SPLIT column, and zero-pad to 3000 for the TEAM encoder.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

import h5py
import numpy as np
import pandas as pd


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def chronological_boundaries(n: int) -> tuple[int, int]:
    """Exact default TrainDevTestSplitter.run_method math from author code."""
    train_dev_end = int(0.7 * n)
    return int(0.6 / 0.7 * train_dev_end), train_dev_end


def id_digest(ids) -> str:
    return hashlib.sha256("\n".join(map(str, ids)).encode()).hexdigest()


def publish_cache(partial: Path, output: Path, manifest_path: Path, report: dict) -> None:
    """Publish complete files with no-replace links and roll back our own links."""
    manifest_partial = manifest_path.with_name(manifest_path.name + ".partial")
    staged = False
    cache_linked = False
    try:
        with manifest_partial.open("x") as stream:
            staged = True
            stream.write(json.dumps(report, indent=2) + "\n")
        # Both paths live beside their temporary files, hence on the same filesystem.
        # os.link fails if another writer has created the destination in the meantime.
        os.link(partial, output)
        cache_linked = True
        os.link(manifest_partial, manifest_path)
    except BaseException:
        if cache_linked and output.exists() and os.path.samefile(partial, output):
            output.unlink()
        raise
    finally:
        if staged:
            manifest_partial.unlink(missing_ok=True)
    partial.unlink()


def export_prefix_cache(source: Path, output: Path, source_sha256: str,
                        max_bytes: int = 15_000_000_000, samples: int = 1000) -> dict:
    source, output = Path(source), Path(output)
    partial = output.with_name(output.name + ".partial")
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or partial.exists() or manifest_path.exists():
        raise FileExistsError("Refusing to overwrite a cache, partial cache or manifest")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if samples not in (1000, 3000):
        raise ValueError("samples must be 1000 or 3000")
    time_after = samples // 100 - 5
    original = pd.read_hdf(source, "metadata/event_metadata")
    if "EVENT" not in original or "MA" not in original:
        raise ValueError("Expected official Chile EVENT and MA metadata")
    ids = original.EVENT.astype(str)
    if ids.duplicated().any() or not np.isfinite(original.MA.to_numpy(float)).all():
        raise ValueError("Event IDs must be unique and all magnitudes finite")
    if not original.TIME.is_monotonic_increasing:
        raise ValueError("Official Chile chronological metadata order is required")
    train_end, train_dev_end = chronological_boundaries(len(original))
    if not 0 < train_end < train_dev_end < len(original):
        raise ValueError("Dataset must have nonempty train, dev and test splits")
    reserved = {"source_row_index", "benchmark_split"}
    if reserved.intersection(original.columns):
        raise ValueError("Source already has reserved cache metadata columns")
    selected = original.iloc[:train_dev_end].copy().reset_index(drop=True)
    selected["source_row_index"] = np.arange(train_dev_end, dtype=np.int64)
    selected["benchmark_split"] = np.where(np.arange(train_dev_end) < train_end, "train", "dev")
    selected_ids = ids.iloc[:train_dev_end].tolist()
    test_ids = set(ids.iloc[train_dev_end:])
    report = {
        "schema": "chile-team-prefix-v1", "source_sha256": source_sha256,
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "doi": "10.5880/GFZ.2.4.2021.002", "license": "CC-BY-4.0",
        "source_rows": len(original), "cache_rows": train_dev_end,
        "author_split_boundaries": [train_end, train_dev_end],
        "split_policy": "chronological row positions; original SPLIT is descriptive only",
        "source_test_ids_sha256": id_digest(ids.iloc[train_dev_end:]),
        "source_test_waveforms_read": False,
        "waveform_dtype": "float32", "sampling_rate_hz": 100,
        "stored_samples": samples, "time_before_first_p_seconds": 5,
        "time_after_first_p_seconds": time_after, "component_order": "ZNE",
        "waveform_units": "m/s", "coordinate_order": "latitude, longitude, depth",
        "coordinate_units": "degrees, degrees, km (positive below sea level)",
        "centering": "none", "normalization": "none", "filtering": "none",
        "duration_exclusive_cutoffs": {"1": 600, "3": 800, "5": 1000},
        "station_availability": "all recorded stations; source Chile has no per-station P picks",
        "compression": "lzf with shuffle; lossless after float32 conversion",
        "all_event_readback_verified": False,
        "splits": {}, "records": 0, "maximum_float32_absolute_roundoff": 0.0,
        "nonzero_values_rounded_to_zero": 0,
    }
    for split, frame in selected.groupby("benchmark_split", sort=False):
        y = frame.MA.to_numpy(float)
        report["splits"][split] = {
            "events": len(frame), "ids_sha256": id_digest(frame.EVENT),
            "magnitude_min": float(y.min()), "magnitude_max": float(y.max()),
            "threshold_counts": {str(t): int((y >= t).sum()) for t in (4, 5, 5.5, 6, 7, 8)},
        }
    # Metadata is small. mode='w' is safe only after the explicit existence guard.
    created = False
    try:
        with partial.open("xb"):
            created = True
        selected.to_hdf(partial, key="metadata/event_metadata", mode="w", format="table", index=False)
        with h5py.File(source, "r") as src, h5py.File(partial, "a") as dst:
            if int(src["metadata/sampling_rate"][()]) != 100 or int(src["metadata/time_before"][()]) != 5:
                raise ValueError("Unsupported sampling rate or first-P alignment")
            for key, value in src.attrs.items():
                dst.attrs[key] = value
            for key in src["metadata"]:
                if key != "event_metadata":
                    src.copy(src["metadata"][key], dst["metadata"], name=key)
            dst["metadata/time_after"][()] = time_after
            dst.attrs["source_time_after_seconds"] = int(src["metadata/time_after"][()])
            dst.attrs["schema"] = report["schema"]
            dst.attrs["source_sha256"] = source_sha256
            dst.attrs["native_SPLIT_column_is_not_benchmark_split"] = 1
            dst.attrs["waveforms_are_raw_uncentered_prefixes"] = 1
            dst.attrs["stored_samples"] = samples
            split_group = dst.create_group("splits")
            for split, frame in selected.groupby("benchmark_split", sort=False):
                split_group.create_dataset(split + "_event_ids", data=frame.EVENT.astype(str).tolist(),
                                           dtype=h5py.string_dtype("utf-8"))
                split_group.create_dataset(split + "_source_rows", data=frame.source_row_index.to_numpy())
            data = dst.create_group("data")
            for number, event_id in enumerate(selected_ids, 1):
                group = src["data"][event_id]
                if set(group) != {"coords", "stations", "waveforms"}:
                    raise ValueError(f"Unexpected Chile event schema for {event_id}: {list(group)}")
                wave = group["waveforms"]
                station_count = wave.shape[0]
                if wave.shape != (station_count, 3000, 3) or station_count == 0:
                    raise ValueError(f"Unexpected waveform shape for {event_id}: {wave.shape}")
                if group["coords"].shape != (station_count, 3) or group["stations"].shape != (station_count,):
                    raise ValueError(f"Station metadata mismatch for {event_id}")
                raw = wave[:, :samples, :]
                if not np.isfinite(raw).all() or not np.isfinite(group["coords"][()]).all():
                    raise ValueError(f"Non-finite waveform/coordinate in {event_id}")
                prefix = raw.astype(np.float32)
                if not np.isfinite(prefix).all():
                    raise ValueError(f"Float32 overflow in {event_id}")
                error = float(np.max(np.abs(raw - prefix)))
                report["maximum_float32_absolute_roundoff"] = max(report["maximum_float32_absolute_roundoff"], error)
                report["nonzero_values_rounded_to_zero"] += int(np.count_nonzero((raw != 0) & (prefix == 0)))
                exported = data.create_group(event_id)
                for key, value in group.attrs.items():
                    exported.attrs[key] = value
                for key in ("coords", "stations"):
                    src.copy(group[key], exported, name=key)
                    np.testing.assert_array_equal(exported[key][()], group[key][()])
                cached = exported.create_dataset("waveforms", data=prefix, dtype="float32",
                                                 compression="lzf", shuffle=True,
                                                 chunks=(min(station_count, 8), samples, 3))
                for key, value in wave.attrs.items():
                    cached.attrs[key] = value
                np.testing.assert_array_equal(cached[()], prefix)
                report["records"] += station_count
                if number % 1000 == 0 or number == len(selected_ids):
                    dst.flush()
                    if partial.stat().st_size > max_bytes:
                        raise RuntimeError("Cache exceeds requested byte cap")
                    print(json.dumps({"events_exported": number, "events_total": train_dev_end,
                                      "bytes": partial.stat().st_size}), flush=True)
            if set(data) != set(selected_ids) or set(data).intersection(test_ids):
                raise AssertionError("Export membership does not match TRAIN+DEV")
            report["all_event_readback_verified"] = True
        # Verify the pandas table survived HDF5 additions, including exact source row mapping.
        pd.testing.assert_frame_equal(pd.read_hdf(partial, "metadata/event_metadata"), selected)
        report["bytes"] = partial.stat().st_size
        if report["bytes"] > max_bytes:
            raise RuntimeError("Cache exceeds requested byte cap")
        report["sha256"] = sha256_file(partial)
        publish_cache(partial, output, manifest_path, report)
        return report
    except BaseException:
        if created and partial.exists():
            partial.unlink()  # Only this invocation's incomplete, task-created output.
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=15_000_000_000)
    parser.add_argument("--samples", type=int, choices=(1000, 3000), default=1000)
    args = parser.parse_args()
    manifest = json.loads(args.source_manifest.read_text())
    if manifest.get("state") != "extracted" or not manifest.get("gzip_crc_verified"):
        raise ValueError("Source extraction and gzip verification must complete first")
    if args.source.stat().st_size != manifest["first_member_uncompressed_bytes"]:
        raise ValueError("Source size does not match verified extraction manifest")
    report = export_prefix_cache(args.source, args.output, manifest["sha256_hdf5"], args.max_bytes, args.samples)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

"""Identity, population and completion guards; no model/data import at module load."""
import csv
import hashlib
import json
import math
from pathlib import Path

PROTOCOL_SHA = "f36836e562b07baa740b8d8219d2063f369f92fb27be3f4d95efab1ac5757b48"
SOURCES = {
    "team_lm.py": "01a8fa1e143feb317815af9a3c35cdbcbcbd5c7b22b318dbd326b5c8a32c1cca",
    "train_team_lm.py": "25b664f752db8df7fc2127801841c400a0c8086d59ff6e6471f48191f065c92b",
    "training_artifacts.py": "816546a0c79d9dd604171ef6d5c8d053d4cb4302884acbbb079bc28b9e8d1754",
}
ARTIFACTS = {"cache", "dataset_manifest", "metadata", "metadata_manifest", "checkpoint", "run", "split_manifest", "history", "pretrain_history"}
CONFIG_FIELDS = ("aggregation", "epochs", "pretrain_epochs", "selection", "density_epsilon", "pretrain_density_epsilon",
                 "stored_samples", "cache_sha256", "source_sha256", "metadata_sidecar_sha256",
                 "metadata_sidecar_manifest_sha256", "source_sha256_files", "fit_ids_sha256", "calibration_ids_sha256",
                 "dev_ids_sha256", "seed", "max_stations", "training_cutoff", "pretrain_cutoff", "limit_fit_events",
                 "limit_dev_events", "skip_dev", "pretrained_encoder", "schema")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("An explicit lowercase SHA256 is required")
    return value


def verify(path, expected):
    if sha(path) != check_sha(expected):
        raise ValueError("SHA256 mismatch: " + str(path))


def ids_sha(ids):
    return hashlib.sha256("\n".join(map(str, ids)).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def validate_plan(plan):
    if set(plan) != {"schema", "artifacts"} or plan["schema"] != "chile_floor_artifact_plan_v1":
        raise ValueError("Invalid plan schema")
    if set(plan["artifacts"]) != ARTIFACTS:
        raise ValueError("Pin exactly the nine required completed artifacts")
    paths = []
    for item in plan["artifacts"].values():
        if set(item) != {"path", "sha256"} or not isinstance(item["path"], str) or not Path(item["path"]).is_absolute():
            raise ValueError("Absolute explicit artifact paths required")
        check_sha(item["sha256"])
        paths.append(item["path"])
    if len(set(paths)) != len(paths):
        raise ValueError("Artifact paths must be distinct")
    for key, name in (("checkpoint", "model.pth"), ("run", "run.json"), ("split_manifest", "split_manifest.json"),
                      ("history", "history.json"), ("pretrain_history", "pretrain_history.json")):
        if Path(plan["artifacts"][key]["path"]).name != name:
            raise ValueError("Completed baseline artifact name mismatch")
    parents = {str(Path(plan["artifacts"][k]["path"]).parent) for k in ("checkpoint", "run", "split_manifest", "history", "pretrain_history")}
    if len(parents) != 1:
        raise ValueError("Completion artifacts must come from the same baseline directory")
    cache = plan["artifacts"]["cache"]["path"]
    for key, suffix in (("dataset_manifest", ".manifest.json"), ("metadata", ".metadata.csv"), ("metadata_manifest", ".metadata.csv.manifest.json")):
        if plan["artifacts"][key]["path"] != cache + suffix:
            raise ValueError("Cache sidecar path mismatch")


def epoch_sequence(path, count):
    # Discard all dictionary fields except epoch while parsing. No loss,
    # calibration score, scheduler metric or DEV result is consulted/output.
    values = json.loads(Path(path).read_text(), object_hook=lambda obj: {"epoch": obj["epoch"]} if "epoch" in obj else {})
    if not isinstance(values, list) or [item.get("epoch") for item in values] != list(range(1, count + 1)):
        raise ValueError("Incomplete or inconsistent fixed epoch budget")
    if any(type(item["epoch"]) is not int for item in values):
        raise ValueError("Epochs must be integers")
    return list(range(1, count + 1))


def project_run(run):
    # Allowlist only provenance/completion fields. Metrics are never returned.
    fields = CONFIG_FIELDS + ("selected_epoch", "dev_evaluated", "test_reads", "selection_used_dev", "fit_events", "calibration_events", "dev_events")
    if any(k not in run for k in fields):
        raise ValueError("Incomplete run provenance")
    return {k: run[k] for k in fields}


def validate_completion(run, checkpoint_config, selected_epoch, plan, manifest):
    run = project_run(run)
    if any(checkpoint_config.get(k) != run[k] for k in CONFIG_FIELDS):
        raise ValueError("Checkpoint config differs from completed run")
    expected = {"aggregation": "transformer", "epochs": 100, "pretrain_epochs": 25,
                "selection": "calibration-nll", "density_epsilon": 1e-6, "pretrain_density_epsilon": 1e-6,
                "stored_samples": 3000, "training_cutoff": "author", "pretrain_cutoff": "author",
                "limit_fit_events": 0, "limit_dev_events": 0, "skip_dev": False, "pretrained_encoder": None,
                "schema": "chile-team-prefix-v1", "source_sha256_files": SOURCES,
                "dev_evaluated": True, "test_reads": 0, "selection_used_dev": False}
    if any(run[k] != value for k, value in expected.items()):
        raise ValueError("Not the prespecified completed source-faithful TRAIN-selected baseline")
    if type(selected_epoch) is not int or selected_epoch != run["selected_epoch"] or not 1 <= selected_epoch <= 100:
        raise ValueError("Checkpoint/run selected epoch mismatch")
    if type(run["max_stations"]) is not int or run["max_stations"] < 1:
        raise ValueError("Invalid checkpoint station limit")
    for key, field in (("cache", "cache_sha256"), ("metadata", "metadata_sidecar_sha256"), ("metadata_manifest", "metadata_sidecar_manifest_sha256")):
        if run[field] != plan["artifacts"][key]["sha256"]:
            raise ValueError("Baseline dataset provenance mismatch")
    if run["source_sha256"] != manifest["source_sha256"]:
        raise ValueError("Original dataset identity mismatch")
    return run


def validate_splits(splits, train_end, dev_end, run):
    if set(splits) != {"fit", "calibration", "dev"} or not 0 < train_end < dev_end:
        raise ValueError("Invalid original split boundaries")
    all_ids, all_rows = [], []
    for name in ("fit", "calibration", "dev"):
        block = splits[name]
        ids, rows = block["event_ids"], block["source_rows"]
        if not ids or len(ids) != len(rows) or any(not isinstance(x, str) or not x or "\n" in x for x in ids):
            raise ValueError("Malformed event identities")
        if any(type(x) is not int for x in rows) or rows != sorted(rows):
            raise ValueError("Source rows must be ordered integers")
        if ids_sha(ids) != block["ids_sha256"] or block["ids_sha256"] != run[name + "_ids_sha256"]:
            raise ValueError("Split identity digest mismatch")
        if len(ids) != run[name + "_events"]:
            raise ValueError("Split count differs from completed provenance")
        if any(not (0 <= row < train_end if name != "dev" else train_end <= row < dev_end) for row in rows):
            raise ValueError("Fit/calibration/DEV boundary violation")
        all_ids.extend(ids)
        all_rows.extend(rows)
    if len(set(all_ids)) != len(all_ids) or len(set(all_rows)) != len(all_rows) or sorted(all_rows) != list(range(dev_end)):
        raise ValueError("Overlapping, missing or repeated split membership")


def fit_rows_only(metadata_path, splits, manifest, metadata_manifest):
    """Parse magnitudes/times only for exact fit rows; other rows identity-only."""
    columns = ["EVENT", "MA", "TIME", "source_row_index", "benchmark_split"]
    fit_lookup = dict(zip(splits["fit"]["source_rows"], splits["fit"]["event_ids"]))
    all_lookup = {}
    for name in ("fit", "calibration", "dev"):
        all_lookup.update(zip(splits[name]["source_rows"], splits[name]["event_ids"]))
    train_end, dev_end = manifest["author_split_boundaries"]
    frames, train_ids, dev_ids = [], [], []
    count = 0
    with Path(metadata_path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != columns:
            raise ValueError("Metadata column schema mismatch")
        for index, row in enumerate(reader):
            count += 1
            expected_split = "train" if index < train_end else "dev"
            if int(row["source_row_index"]) != index or row["benchmark_split"] != expected_split or row["EVENT"] != all_lookup.get(index):
                raise ValueError("Exact sidecar/split row alignment mismatch")
            (train_ids if index < train_end else dev_ids).append(row["EVENT"])
            if index in fit_lookup:
                magnitude, timestamp = float(row["MA"]), float(row["TIME"])
                if not math.isfinite(magnitude) or not math.isfinite(timestamp):
                    raise ValueError("Nonfinite fit metadata")
                frames.append({"EVENT": row["EVENT"], "MA": magnitude, "TIME": timestamp,
                               "source_row_index": index, "benchmark_split": "train"})
    if count != dev_end or count != metadata_manifest["rows"] or count != manifest["cache_rows"]:
        raise ValueError("Metadata row count mismatch")
    for name, ids in (("train", train_ids), ("dev", dev_ids)):
        if ids_sha(ids) != manifest["splits"][name]["ids_sha256"]:
            raise ValueError("Author split identity mismatch")
    return frames, {"train": train_ids, "dev": dev_ids}


def select_population(rows):
    groups = {"MA_lt_4": [], "MA_4_to_5p5": [], "MA_ge_5p5": []}
    for row in rows:
        magnitude = row["MA"]
        if not math.isfinite(magnitude) or row["benchmark_split"] != "train":
            raise ValueError("Finite TRAIN-fit selection required")
        group = "MA_lt_4" if magnitude < 4 else "MA_4_to_5p5" if magnitude < 5.5 else "MA_ge_5p5"
        groups[group].append(row)
    selected, fractions = [], {}
    for name, population in groups.items():
        ordered = sorted(population, key=lambda row: (hashlib.sha256(("chile_floor_audit_v1|" + row["EVENT"]).encode()).hexdigest(), row["EVENT"]))
        chosen = ordered if name == "MA_ge_5p5" else ordered[:1024]
        fractions[name] = {"eligible": len(population), "selected": len(chosen),
                           "fraction": len(chosen) / len(population) if population else None}
        selected.extend({**row, "stratum": name} for row in chosen)
    selected.sort(key=lambda row: row["source_row_index"])
    if not selected or len({row["EVENT"] for row in selected}) != len(selected):
        raise ValueError("Empty/repeated diagnostic selection")
    return selected, fractions

"""Versioned, auditable station-encoder transfer between matched experiments.

These checks bind recorded provenance and reject incomplete/legacy checkpoints.
They are not an attestation of an untrusted artifact author's training history.
Only tensors and primitive containers are deserialized with weights_only=True.
"""

import hashlib
import json
import os
from pathlib import Path
import random

import h5py
import numpy as np
import torch


ENCODER_SCHEMA = "team-station-encoder-v1"
EPOCH_SCHEMA = "team-epoch-recovery-v1"


def json_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def atomic_json_save(value, destination):
    """Publish complete control metadata; a failed write leaves the old file."""
    destination = Path(destination)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("w") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)


def station_membership(dataset):
    """Bind ordered event/station identities without reading waveform values."""
    if not (dataset.frame.benchmark_split == "train").all():
        raise ValueError("Station encoder membership must be entirely original TRAIN")
    digest, records = hashlib.sha256(), 0
    with h5py.File(dataset.cache, "r") as handle:
        for row in dataset.frame.itertuples(index=False):
            group = handle["data"][str(row.EVENT)]
            count = group["waveforms"].shape[0]
            identifiers = group["stations"][:]
            if len(identifiers) != count or count < 1:
                raise ValueError("Station identifiers must cover every nonempty waveform group")
            # Indices disambiguate repeated station identifiers within an event.
            names = [value.decode("utf-8") if isinstance(value, bytes) else str(value) for value in identifiers]
            record = [str(row.EVENT), int(row.source_row_index), names]
            digest.update(json.dumps(record, ensure_ascii=True, separators=(",", ":")).encode() + b"\n")
            records += count
    return {"events": len(dataset), "records": records, "ordered_membership_sha256": digest.hexdigest()}


def pretraining_identity(config, fit_stations, calibration_stations, implementation_sha256):
    """Only station-training semantics; event aggregator/options may differ."""
    return {
        "schema": ENCODER_SCHEMA,
        "partition": "original_train_fit_only", "test_used": False, "dev_used_for_training_or_selection": False,
        "source_sha256": config["source_sha256"], "cache_sha256": config["cache_sha256"],
        "metadata_sidecar_sha256": config["metadata_sidecar_sha256"], "stored_samples": config["stored_samples"],
        "fit_ids_sha256": config["fit_ids_sha256"], "fit_stations": fit_stations,
        "calibration_ids_sha256": config["calibration_ids_sha256"], "calibration_stations": calibration_stations,
        "implementation_sha256": implementation_sha256,
        "preprocessing": "raw_ZNE_mps_100Hz_firstPminus5s_prefix_mask_no_demean_pad3000_peak_scale_logpeak",
        "station_sampling": "all_stations_once_per_epoch_no_magnitude_resampling_keep_partial_batch",
        "training_cutoff": config["pretrain_cutoff"], "cutoff_sampling": "independent_per_station",
        "label_noise": "Gaussian_sigma_0.05_max(M-4,0)_fit_only",
        "density_epsilon": config["pretrain_density_epsilon"],
        "optimizer": {"name": "Adam", "lr": 1e-4, "betas": [0.9, 0.999], "eps": 1e-8, "clip_global_norm": 1.},
        "schedule": config["lr_schedule"], "calibration_times": [1, 3, 5],
        "selection": "fixed_final_pretraining_epoch", "epochs": config["pretrain_epochs"],
        "batch_size": config["pretrain_batch_size"], "seed": config["seed"],
        "torch_version": config["torch_version"],
    }


def encoder_payload(encoder, identity, config, origin_run):
    if identity["epochs"] < 1 or identity["fit_stations"]["records"] < 1:
        raise ValueError("A completed positive pretraining budget is required")
    if identity["partition"] != "original_train_fit_only" or identity["test_used"] or identity["dev_used_for_training_or_selection"]:
        raise ValueError("Encoder provenance permits only original TRAIN fitting")
    return {"schema": ENCODER_SCHEMA,
            "encoder": {key: value.detach().cpu().clone() for key, value in encoder.state_dict().items()},
            "completed_epochs": identity["epochs"], "pretraining_identity": identity,
            "origin": {"run_directory": str(origin_run), "config": config, "config_sha256": json_sha256(config)}}


def save_encoder_artifact(path, encoder, identity, config, origin_run, *, atomic_save, file_sha256):
    """The manifest is written only after the complete tensor artifact exists."""
    path = Path(path)
    payload = encoder_payload(encoder, identity, config, origin_run)
    atomic_save(payload, path)
    manifest = {"schema": ENCODER_SCHEMA, "sha256": file_sha256(path),
                "pretraining_identity_sha256": json_sha256(identity),
                "origin_config_sha256": payload["origin"]["config_sha256"]}
    atomic_json_save(manifest, Path(str(path) + ".manifest.json"))


def load_encoder_artifact(path, expected_identity, *, file_sha256):
    path = Path(path)
    sidecar = Path(str(path) + ".manifest.json")
    if not sidecar.is_file():
        raise ValueError("Unverified/legacy encoder: a versioned provenance manifest is required")
    manifest = json.loads(sidecar.read_text())
    if manifest.get("schema") != ENCODER_SCHEMA or file_sha256(path) != manifest.get("sha256"):
        raise ValueError("Encoder file does not match its versioned provenance manifest")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload.get("schema") != ENCODER_SCHEMA or payload.get("pretraining_identity") != expected_identity:
        raise ValueError("Incompatible encoder pretraining protocol, implementation, or station membership")
    if payload.get("completed_epochs") != expected_identity["epochs"] or expected_identity["epochs"] < 1:
        raise ValueError("Encoder did not complete the required pretraining budget")
    origin = payload.get("origin", {})
    config = origin.get("config", {})
    if (json_sha256(expected_identity) != manifest.get("pretraining_identity_sha256")
            or json_sha256(config) != origin.get("config_sha256")
            or origin.get("config_sha256") != manifest.get("origin_config_sha256")):
        raise ValueError("Encoder provenance is inconsistent")
    if (expected_identity["partition"] != "original_train_fit_only" or expected_identity["test_used"]
            or expected_identity["dev_used_for_training_or_selection"]
            or any(config.get(key) != expected_identity[key] for key in
                   ("source_sha256", "cache_sha256", "fit_ids_sha256", "calibration_ids_sha256"))):
        raise ValueError("Encoder origin is not the required original TRAIN partition")
    state = payload.get("encoder")
    if not isinstance(state, dict) or not state or any(not isinstance(value, torch.Tensor) or not torch.isfinite(value).all() for value in state.values()):
        raise ValueError("Encoder weights must be a finite tensor state dictionary")
    provenance = {"path": str(path.resolve()), "sha256": manifest["sha256"],
                  "manifest_sha256": file_sha256(sidecar), "origin_run_directory": origin.get("run_directory"),
                  "origin_config_sha256": origin["config_sha256"], "pretraining_identity": expected_identity}
    return state, provenance


def capture_random_state():
    numpy_state = np.random.get_state()
    return {"torch_rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
            "python_rng": random.getstate(),
            "numpy_rng": [numpy_state[0], numpy_state[1].tolist(), *numpy_state[2:]]}


def restore_random_state(payload):
    """Call after model/optimizer/loader setup, immediately before continuation."""
    torch.set_rng_state(payload["torch_rng"].cpu())
    cuda_state = payload["cuda_rng"]
    if len(cuda_state) != (torch.cuda.device_count() if torch.cuda.is_available() else 0):
        raise ValueError("Resume requires the same visible CUDA device count")
    if cuda_state:
        torch.cuda.set_rng_state_all([value.cpu() for value in cuda_state])
    random.setstate(payload["python_rng"])
    numpy_state = payload["numpy_rng"]
    np.random.set_state((numpy_state[0], np.asarray(numpy_state[1], dtype=np.uint32), *numpy_state[2:]))


def load_epoch_recovery(path, config, split_manifest):
    """Fail closed on changed budgets/code/data and incomplete legacy state."""
    path = Path(path).resolve()
    out = path.parent
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload.get("schema") != EPOCH_SCHEMA:
        raise ValueError("Legacy checkpoint cannot provide exact epoch recovery")
    if (payload.get("config") != config or json.loads((out / "identity.json").read_text()) != config
            or json.loads((out / "split_manifest.json").read_text()) != split_manifest
            or payload.get("run_directory") != str(out)):
        raise ValueError("Resume requires unchanged run identity, code, data, options and original run directory")
    if (out / "run.json").exists():
        raise ValueError("This run is already complete; recovery cannot silently repeat its assessment")
    stage, epoch = payload.get("stage"), payload.get("completed_epoch")
    budget = config.get("pretrain_epochs" if stage == "pretrain" else "epochs", 0)
    if stage not in ("pretrain", "event") or not isinstance(epoch, int) or not 1 <= epoch <= budget:
        raise ValueError("Checkpoint has invalid stage/epoch budget")
    if stage == "pretrain" and config.get("pretrained_encoder") is not None:
        raise ValueError("Imported-encoder runs cannot resume an executed pretraining stage")
    state = payload.get("run_state", {})
    for key in ("pretrain_history", "history"):
        if not isinstance(state.get(key), list):
            raise ValueError("Recovery requires complete epoch histories")
    history = state["pretrain_history" if stage == "pretrain" else "history"]
    if [item.get("epoch") for item in history] != list(range(1, epoch + 1)):
        raise ValueError("Recovery history does not cover exactly the completed epochs")
    if stage == "pretrain" and state["history"]:
        raise ValueError("Pretraining checkpoint cannot contain event-training history")
    selection = payload.get("selection", {})
    if stage == "event":
        if selection.get("policy") != config["selection"]:
            raise ValueError("Recovery must preserve the checkpoint-selection policy")
        selected = selection.get("selected_epoch")
        if not isinstance(selected, int) or not 1 <= selected <= epoch:
            raise ValueError("Recovery has invalid selected epoch")
        if config["selection"] == "calibration-nll" and not isinstance(state.get("best_model"), dict):
            raise ValueError("Recovery is missing the selected calibration checkpoint weights")
    for key in ("optimizer", "scheduler", "torch_rng", "cuda_rng", "numpy_rng", "python_rng"):
        if key not in payload:
            raise ValueError("Recovery is missing optimizer/scheduler/random state")
    return payload, out

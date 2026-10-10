"""Chronological Chile TRAIN/DEV early-window TEAM-LM benchmark adaptation.

Only reviewed 1000/3000-sample TRAIN+DEV exports are accepted; TEST is not opened.
Fixed training budgets and optional checkpoint selection use an event-heldout
partition of original TRAIN. DEV is evaluated after selection, never consulted
by optimization, stopping, schedules, or checkpoint selection. The original
paper's [-4,+25] second schedule requires the full 3000-sample cache.
"""

import argparse
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import random
import time
import uuid

import h5py
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset, Subset

from team_lm import GaussianMixtureHead, TeamLM, mixture_log_prob, mixture_mean, mixture_nll, prepare_prefix
import team_lm
from training_artifacts import (EPOCH_SCHEMA, atomic_json_save, capture_random_state, json_sha256,
                                load_encoder_artifact, load_epoch_recovery, pretraining_identity,
                                restore_random_state, save_encoder_artifact, station_membership)


ROOT = Path(__file__).resolve().parents[3]
TIMES = (1., 3., 5.)


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def id_digest(ids):
    return hashlib.sha256("\n".join(map(str, ids)).encode()).hexdigest()


def load_verified_metadata(cache_path, manifest_path=None):
    """Verify exact cache content and original split membership before fitting."""
    cache_path = Path(cache_path)
    manifest_path = Path(manifest_path) if manifest_path else cache_path.with_suffix(cache_path.suffix + ".manifest.json")
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get("schema") != "chile-team-prefix-v1"
            or manifest.get("source_test_waveforms_read") is not False
            or manifest.get("all_event_readback_verified") is not True):
        raise ValueError("A completed no-TEST Chile prefix export is required")
    if file_sha256(cache_path) != manifest["sha256"]:
        raise ValueError("Cache SHA256 disagrees with exporter manifest")
    # The exact table is exported once in the verified-cache environment. This
    # avoids loading incompatible PyTables wheels into the active ML runtime.
    metadata_path = Path(str(cache_path) + ".metadata.csv")
    metadata_manifest_path = Path(str(metadata_path) + ".manifest.json")
    metadata_manifest = json.loads(metadata_manifest_path.read_text())
    columns = ["EVENT", "MA", "TIME", "source_row_index", "benchmark_split"]
    if (metadata_manifest.get("cache_sha256") != manifest["sha256"]
            or metadata_manifest.get("origin") != "metadata/event_metadata"
            or metadata_manifest.get("columns") != columns
            or file_sha256(metadata_path) != metadata_manifest["sha256"]):
        raise ValueError("Metadata sidecar does not match the verified cache/export identity")
    metadata = pd.read_csv(metadata_path, float_precision="round_trip", dtype={
        "EVENT": str, "MA": "float64", "TIME": "float64",
        "source_row_index": "int64", "benchmark_split": str})
    if metadata.columns.tolist() != columns or len(metadata) != metadata_manifest["rows"]:
        raise ValueError("Metadata sidecar has unexpected columns or row count")
    required = {"EVENT", "MA", "TIME", "source_row_index", "benchmark_split"}
    if not required.issubset(metadata.columns) or metadata.EVENT.astype(str).duplicated().any():
        raise ValueError("Invalid or duplicate benchmark event metadata")
    if (not np.isfinite(metadata.MA.to_numpy(float)).all()
            or not np.isfinite(metadata.TIME.to_numpy(float)).all()
            or not metadata.TIME.is_monotonic_increasing):
        raise ValueError("Finite magnitudes and chronological metadata are required")
    train_end, dev_end = manifest["author_split_boundaries"]
    expected = np.where(np.arange(dev_end) < train_end, "train", "dev")
    if (len(metadata) != dev_end or len(metadata) != manifest["cache_rows"]
            or not np.array_equal(metadata.source_row_index, np.arange(dev_end))
            or not np.array_equal(metadata.benchmark_split, expected)):
        raise ValueError("Cache redefines the author's original chronological TRAIN/DEV split")
    with h5py.File(cache_path, "r") as handle:
        samples = int(manifest.get("stored_samples", 0))
        if handle.attrs.get("schema") != "chile-team-prefix-v1" or samples not in (1000, 3000) or int(handle.attrs.get("stored_samples", 0)) != samples:
            raise ValueError("Unsupported cache schema/window")
        if int(handle["metadata/sampling_rate"][()]) != 100 or int(handle["metadata/time_before"][()]) != 5:
            raise ValueError("Unsupported sample rate or first-P alignment")
        if int(handle["metadata/time_after"][()]) != samples // 100 - 5:
            raise ValueError("Cache timing metadata disagrees with stored waveform length")
        if set(handle["data"]) != set(metadata.EVENT.astype(str)):
            raise ValueError("Cache contains missing/extra event groups, possibly TEST")
        for split in ("train", "dev"):
            frame = metadata[metadata.benchmark_split == split]
            ids = frame.EVENT.astype(str).to_numpy()
            if id_digest(ids) != manifest["splits"][split]["ids_sha256"]:
                raise ValueError("Exporter split-ID digest changed")
            stored = handle[f"splits/{split}_event_ids"].asstr()[:]
            if not np.array_equal(ids, stored) or not np.array_equal(frame.source_row_index, handle[f"splits/{split}_source_rows"][:]):
                raise ValueError("HDF split membership differs from metadata")
    manifest = {**manifest, "metadata_sidecar_sha256": metadata_manifest["sha256"],
                "metadata_sidecar_manifest_sha256": file_sha256(metadata_manifest_path)}
    return metadata, manifest


def split_original_train(metadata, fraction=.1, seed=20261009):
    """TRAIN-only random event split stratified by prespecified magnitude bands.

    Bands: <4, [4,5), [5,5.5), [5.5,6), >=6. Each band with >=2 events
    contributes at least one calibration event and retains at least one fit
    event. Singleton bands remain in fit. This can slightly exceed the nominal
    calibration fraction; it is recorded and never uses DEV to choose rows.
    """
    if not 0 < fraction < .5:
        raise ValueError("Calibration fraction must lie strictly between 0 and .5")
    train_rows = np.flatnonzero(metadata.benchmark_split.to_numpy() == "train")
    bands = np.searchsorted([4., 5., 5.5, 6.], metadata.MA.to_numpy(float)[train_rows], side="right")
    rng, calibration = np.random.default_rng(seed), []
    for band in np.unique(bands):
        rows = train_rows[bands == band].copy()
        rng.shuffle(rows)
        if len(rows) >= 2:
            count = min(len(rows) - 1, max(1, int(round(fraction * len(rows)))))
            calibration.extend(rows[:count].tolist())
    calibration = np.sort(np.asarray(calibration, dtype=np.int64))
    fit = np.setdiff1d(train_rows, calibration)
    if not len(fit) or not len(calibration):
        raise ValueError("Need nonempty TRAIN fitting and event-heldout calibration partitions")
    dev = np.flatnonzero(metadata.benchmark_split.to_numpy() == "dev")
    return {"fit": fit, "calibration": calibration, "dev": dev}


def _event_seed(seed, epoch, event):
    return int.from_bytes(hashlib.sha256(f"{seed}/{epoch}/{event}".encode()).digest()[:8], "little")


class EventDataset(Dataset):
    """Lazy TRAIN/DEV-only reads; stochastic station changes are TRAIN-fit only."""

    def __init__(self, cache, frame, *, training=False, max_stations=25, station_drop=0., seed=20261009, stored_samples=1000):
        if max_stations < 1 or not 0 <= station_drop < 1:
            raise ValueError("Invalid station cap/drop probability")
        if not set(frame.benchmark_split).issubset({"train", "dev"}):
            raise ValueError("Dataset cannot contain TEST or undefined benchmark membership")
        if training and not (frame.benchmark_split == "train").all():
            raise ValueError("Only original TRAIN events may receive training augmentation")
        if not training and station_drop:
            raise ValueError("Evaluation cannot use station dropout")
        self.cache, self.frame = str(cache), frame.reset_index(drop=True).copy()
        self.training, self.max_stations, self.station_drop = training, max_stations, station_drop
        if stored_samples not in (1000, 3000):
            raise ValueError("Only verified 1000/3000 sample caches are supported")
        self.stored_samples = stored_samples
        self.seed, self.epoch, self._handle, self._pid = seed, 0, None, None

    def __len__(self):
        return len(self.frame)

    def _file(self):
        if self._handle is None or self._pid != os.getpid():
            self.close()
            self._handle = h5py.File(self.cache, "r")
            self._pid = os.getpid()
        return self._handle

    def close(self):
        if self._handle is not None:
            self._handle.close()
        self._handle = None

    def __getstate__(self):
        state = self.__dict__.copy()
        state["_handle"], state["_pid"] = None, None
        return state

    def __getitem__(self, index):
        row = self.frame.iloc[index]
        group = self._file()["data"][str(row.EVENT)]
        count = group["waveforms"].shape[0]
        if count < 1 or group["waveforms"].shape[1:] != (self.stored_samples, 3) or group["coords"].shape != (count, 3):
            raise ValueError("Malformed compact event waveform/coordinate shape")
        if self.training:
            rng = np.random.default_rng(_event_seed(self.seed, self.epoch, row.EVENT))
            selected = rng.permutation(count)[:self.max_stations]
            if self.station_drop:
                retained = rng.random(len(selected)) >= self.station_drop
                if not retained.any():
                    retained[rng.integers(len(selected))] = True
                selected = selected[retained]
        else:
            selected = np.arange(min(count, self.max_stations))
        # Read all <=21 Chile stations, then reorder in memory: h5py's fancy
        # indices must be sorted, while training station order is randomized.
        x = np.asarray(group["waveforms"][:], dtype=np.float32)[selected]
        coords = np.asarray(group["coords"][:], dtype=np.float32)[selected]
        if not np.isfinite(x).all() or not np.isfinite(coords).all():
            raise ValueError("Nonfinite observed cache values")
        return {"waveforms": torch.from_numpy(x), "coordinates": torch.from_numpy(coords),
                "magnitude": float(row.MA), "event": str(row.EVENT)}


class StationDataset(Dataset):
    """All stations of fitting events, or explicitly held-out TRAIN calibration."""

    def __init__(self, events, *, calibration=False):
        if (not (events.frame.benchmark_split == "train").all()
                or events.training == calibration):
            raise ValueError("Station fitting/calibration must use its matching TRAIN-only event partition")
        self.events = events
        with h5py.File(events.cache, "r") as handle:
            counts = [handle["data"][str(event)]["waveforms"].shape[0] for event in events.frame.EVENT]
        self.ends = np.cumsum(counts)

    def __len__(self):
        return int(self.ends[-1])

    def __getitem__(self, index):
        event_index = int(np.searchsorted(self.ends, index, side="right"))
        station = index - (self.ends[event_index - 1] if event_index else 0)
        row = self.events.frame.iloc[event_index]
        x = self.events._file()["data"][str(row.EVENT)]["waveforms"][int(station)]
        return torch.from_numpy(np.asarray(x, dtype=np.float32)), float(row.MA)


def collate_events(examples):
    maximum = max(len(item["waveforms"]) for item in examples)
    samples = examples[0]["waveforms"].shape[1]
    x = torch.zeros(len(examples), maximum, samples, 3)
    coords = torch.zeros(len(examples), maximum, 3)
    mask = torch.zeros(len(examples), maximum, dtype=torch.bool)
    for index, item in enumerate(examples):
        count = len(item["waveforms"])
        x[index, :count], coords[index, :count], mask[index, :count] = item["waveforms"], item["coordinates"], True
    # Preserve original target precision for reporting; fitting casts explicitly.
    return x, coords, mask, torch.tensor([item["magnitude"] for item in examples], dtype=torch.float64), [item["event"] for item in examples]


def resampling_indices(magnitudes, factor=2):
    """Author's exact TRAIN event repetition factors, without DEV resampling."""
    if factor not in (1, 2):
        raise ValueError("Use factor 2 for the source rule or 1 for its no-resampling ablation")
    repetitions = np.ones(len(magnitudes), dtype=np.int64)
    magnitudes = np.asarray(magnitudes)
    for lower in range(4, 9):
        repetitions[(lower < magnitudes) & (magnitudes <= lower + 1)] = factor**(lower - 1)
    return np.repeat(np.arange(len(magnitudes)), repetitions)


def mixture_quantile(mixture, probability, steps=48):
    if not 0 < probability < 1:
        raise ValueError("Quantile probability must be strictly between zero and one")
    means, scales, weights = mixture["means"], mixture["scales"], mixture["weights"]
    lower = (means - 12 * scales).amin(-1)
    upper = (means + 12 * scales).amax(-1)
    for _ in range(steps):
        middle = (lower + upper) / 2
        cdf = (.5 * (1 + torch.erf((middle[:, None] - means) / (scales * math.sqrt(2)))) * weights).sum(-1)
        lower = torch.where(cdf < probability, middle, lower)
        upper = torch.where(cdf >= probability, middle, upper)
    return (lower + upper) / 2


def gaussian_mixture_crps(mixture, targets):
    """Exact analytic CRPS: E|X-y| - .5 E|X-X'| for Gaussian mixtures."""
    means, scales, weights = mixture["means"], mixture["scales"], mixture["weights"]
    def absolute_normal(offset, sigma):
        z = offset / sigma
        return sigma * math.sqrt(2 / math.pi) * torch.exp(-.5 * z.square()) + offset * torch.erf(z / math.sqrt(2))
    first = (weights * absolute_normal(targets[:, None] - means, scales)).sum(-1)
    distance = means[:, :, None] - means[:, None, :]
    pair_scale = (scales[:, :, None].square() + scales[:, None, :].square()).sqrt()
    second = (weights[:, :, None] * weights[:, None, :] * absolute_normal(distance, pair_scale)).sum((1, 2))
    return first - .5 * second


def point_metrics(target, prediction):
    target, prediction = np.asarray(target), np.asarray(prediction)
    error = np.abs(prediction - target)
    count = max(1, int(np.ceil(.05 * len(error))))
    result = {"events": len(error), "mae": float(error.mean()), "medae": float(np.median(error)),
              "rmse": float(np.sqrt(np.mean(error**2))), "bias": float(np.mean(prediction - target)),
              "cvar95": float(np.sort(error)[-count:].mean())}
    for threshold in (4., 5., 5.5, 6., 7.):
        selected = target >= threshold
        result[f"m{threshold:g}_events"] = int(selected.sum())
        result[f"m{threshold:g}_mae"] = float(error[selected].mean()) if selected.any() else None
        result[f"m{threshold:g}_bias"] = float((prediction - target)[selected].mean()) if selected.any() else None
    return result


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    outputs = {t: {key: [] for key in ("logits", "weights", "means", "scales")} for t in TIMES}
    targets, events = [], []
    for x, coords, mask, y, ids in loader:
        x, coords, mask = x.to(device), coords.to(device), mask.to(device)
        targets.append(y.double())
        events.extend(ids)
        for seconds in TIMES:
            mixture = model(x, coords, mask, cutoff_seconds=seconds)
            for name, values in mixture.items():
                outputs[seconds][name].append(values.double().cpu())
    y = torch.cat(targets)
    if len(set(events)) != len(events):
        raise ValueError("Evaluation contains duplicate event IDs")
    metrics, predictions = {}, {"targets": y.numpy(), "event_ids": np.asarray(events, dtype=str)}
    for seconds, pieces in outputs.items():
        mixture = {key: torch.cat(values) for key, values in pieces.items()}
        mean, median = mixture_mean(mixture), mixture_quantile(mixture, .5)
        nll, crps = -mixture_log_prob(mixture, y), gaussian_mixture_crps(mixture, y)
        lower, upper = mixture_quantile(mixture, .05), mixture_quantile(mixture, .95)
        tail_probability = 1 - ((.5 * (1 + torch.erf((5.5 - mixture["means"]) / (mixture["scales"] * math.sqrt(2))))) * mixture["weights"]).sum(-1)
        metrics[str(int(seconds))] = {
            "mean": point_metrics(y.numpy(), mean.numpy()), "median": point_metrics(y.numpy(), median.numpy()),
            "proper_nll": float(nll.mean()), "crps": float(crps.mean()),
            "brier_m5.5": float((tail_probability - (y >= 5.5).to(tail_probability.dtype)).square().mean()),
            "coverage_90": float(((lower <= y) & (y <= upper)).double().mean()),
            "interval_width_90": float((upper - lower).mean()),
        }
        predictions[f"mean_{int(seconds)}s"], predictions[f"median_{int(seconds)}s"] = mean.numpy(), median.numpy()
        for name, values in mixture.items():
            predictions[f"{name}_{int(seconds)}s"] = values.numpy()
    return metrics, predictions


def atomic_save(value, destination):
    destination = Path(destination)
    temporary = destination.with_name(destination.name + ".tmp")
    with temporary.open("wb") as handle:
        torch.save(value, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)


def checkpoint(model, optimizer, stage, epoch, config, selection, scheduler=None, *, out, run_state):
    return {"schema": EPOCH_SCHEMA, "run_directory": str(out.resolve()),
            "model": model.state_dict(), "optimizer": optimizer.state_dict(), "stage": stage,
            "completed_epoch": epoch, "config": config, "selection": selection,
            "scheduler": None if scheduler is None else scheduler.state_dict(),
            "run_state": run_state, **capture_random_state()}


def restore_optimizer_and_random(optimizer, scheduler, recovery):
    optimizer.load_state_dict(recovery["optimizer"])
    if (scheduler is None) != (recovery["scheduler"] is None):
        raise ValueError("Resume cannot change the learning-rate schedule")
    if scheduler is not None:
        scheduler.load_state_dict(recovery["scheduler"])
    restore_random_state(recovery)


def runtime_identity(device):
    return {"device": device.type, "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
            "visible_cuda_devices": torch.cuda.device_count() if device.type == "cuda" else 0,
            "torch_cuda": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
            "threads": torch.get_num_threads(), "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "float32_matmul_precision": torch.get_float32_matmul_precision()}


def smooth_training_magnitudes(targets, *, enabled, training=True):
    """Source M>4 Gaussian label noise; never mutate targets or evaluation labels."""
    if not enabled or not training:
        return targets
    return targets + torch.randn_like(targets) * (targets - 4).clamp_min(0) * .05


def author_station_blinding(waveforms, coordinates, mask, cutoffs, *, training=True):
    """Hide a uniform number 0..S-1 of currently active stations per event.

    This is the source's count-uniform law, not independent Bernoulli dropout.
    Activation is determined only from the strictly observed, centered prefix;
    each repeated training presentation draws fresh randomness. Returning a mask
    lets the model zero both waveform and coordinate evidence before encoding.
    """
    if not training:
        return mask
    with torch.no_grad():
        _, active = prepare_prefix(waveforms, mask, cutoffs)
        active = active & coordinates.ne(0).any(-1)
        count = active.sum(-1)
        hidden_count = (torch.rand(len(mask), device=mask.device) * count).long()
        scores = torch.rand(mask.shape, device=mask.device).masked_fill(~active, float("inf"))
        ranks = scores.argsort(-1).argsort(-1)
        hidden = active & (ranks < hidden_count[:, None])
        return mask & ~hidden


def make_plateau_scheduler(optimizer, schedule, stage):
    if schedule == "none":
        return None
    if schedule != "author-plateau" or stage not in ("pretrain", "event"):
        raise ValueError("Unknown scheduler/stage")
    # Keras reduces at wait >= patience; PyTorch uses bad_epochs > patience.
    # Both therefore decay after 4/6 consecutive non-improving observations.
    return torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=.3, patience=3 if stage == "pretrain" else 5,
        threshold=1e-4, threshold_mode="abs", eps=0.)


def step_calibration_scheduler(scheduler, metrics, *, split):
    """Explicit boundary: schedules may consume only TRAIN calibration scores."""
    if split != "calibration":
        raise ValueError("Learning-rate schedules must not consume DEV or TEST metrics")
    score = float(np.mean([metrics[str(int(t))]["proper_nll"] for t in TIMES]))
    if not math.isfinite(score):
        raise FloatingPointError("Nonfinite calibration score")
    if scheduler is not None:
        scheduler.step(score)
    return score


@torch.no_grad()
def evaluate_pretraining(model, loader, device):
    """Fixed 1/3/5s station loss on held-out TRAIN; no label noise or blinding."""
    model.eval()
    total, count = {str(int(t)): 0. for t in TIMES}, 0
    for x, targets in loader:
        x, targets = x.to(device), targets.double().to(device)
        for seconds in TIMES:
            mixture = {key: value.double() for key, value in model.forward_single_station(x, seconds).items()}
            total[str(int(seconds))] += float(-mixture_log_prob(mixture, targets).sum())
        count += len(targets)
    if not count:
        raise ValueError("Pretraining calibration must contain stations")
    return {key: {"proper_nll": value / count} for key, value in total.items()}


def peak_cuda_memory(device):
    if device.type != "cuda":
        return {"peak_cuda_allocated_bytes": None, "peak_cuda_reserved_bytes": None}
    return {"peak_cuda_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "peak_cuda_reserved_bytes": torch.cuda.max_memory_reserved(device)}


def train_station_epoch(model, loader, optimizer, parameters, device, config, epoch):
    """One complete pretraining epoch; fingerprinted for encoder compatibility."""
    model.train()
    total, count, epoch_start = 0., 0, time.monotonic()
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    for step, (x, y) in enumerate(loader, 1):
        x, y = x.to(device), y.float().to(device)
        y = smooth_training_magnitudes(y, enabled=True)
        mixture = model.forward_single_station(x, training_cutoffs(len(y), device, config["pretrain_cutoff"]))
        loss = mixture_nll(mixture, y, config["pretrain_density_epsilon"])
        if not torch.isfinite(loss):
            raise FloatingPointError("Nonfinite pretraining loss")
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(parameters, 1.)
        optimizer.step()
        total, count = total + float(loss.detach()) * len(y), count + len(y)
        if step == 100:
            print("TIMING", {"stage": "pretrain", "epoch": epoch + 1,
                             "first_100_batches_seconds": time.monotonic() - epoch_start,
                             "total_batches": len(loader), **peak_cuda_memory(device)}, flush=True)
    return total / count, count, time.monotonic() - epoch_start


def pretraining_implementation_sha256():
    """Fingerprint station-only behavior, permitting independent event variants."""
    components = (team_lm.StationEncoder, GaussianMixtureHead, team_lm._glorot,
                  team_lm._relu_mlp, prepare_prefix, TeamLM.forward_single_station,
                  mixture_nll, mixture_log_prob, StationDataset, training_cutoffs,
                  smooth_training_magnitudes, train_station_epoch, evaluate_pretraining,
                  make_plateau_scheduler, step_calibration_scheduler)
    sources = {item.__qualname__: inspect.getsource(item) for item in components}
    sources["constants"] = [team_lm.TRACE_SAMPLES, team_lm.SAMPLE_RATE, team_lm.PRE_P_SECONDS, list(TIMES)]
    return json_sha256(sources)


def training_cutoffs(count, device, schedule):
    if schedule == "discrete":
        return torch.tensor(TIMES, device=device)[torch.randint(3, (count,), device=device)]
    width = 29. if schedule == "author" else 9.
    # Integer samples match the author's randint cutout convention exactly.
    samples = torch.randint(100, int(100 * (width + 1)), (count,), device=device)
    # A half-sample interior offset avoids floating-point division placing an
    # intended integer cut infinitesimally below its boundary before floor().
    return (samples.double() + .5) / 100. - 5.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--aggregation", choices=("transformer", "pool"), required=True)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--pretrain-epochs", type=int, default=0)
    parser.add_argument("--pretrained-encoder", type=Path, help="Verified station artifact; --pretrain-epochs specifies its required completed budget")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--pretrain-batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-stations", type=int, default=25)
    parser.add_argument("--station-drop", type=float, default=0.)
    parser.add_argument("--station-blinding", choices=("none", "author"), default="none")
    parser.add_argument("--event-label-smoothing", action="store_true")
    parser.add_argument("--lr-schedule", choices=("none", "author-plateau"), default="none")
    parser.add_argument("--magnitude-resampling", type=int, choices=(1, 2), default=2)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--calibration-fraction", type=float, default=.1)
    parser.add_argument("--selection", choices=("final", "calibration-nll"), default="final")
    parser.add_argument("--training-cutoff", choices=("discrete", "uniform-early", "author"), default="discrete")
    parser.add_argument("--pretrain-cutoff", choices=("discrete", "uniform-early", "author"), help="Defaults to --training-cutoff")
    parser.add_argument("--density-epsilon", type=float, default=1e-6)
    parser.add_argument("--pretrain-density-epsilon", type=float, help="Defaults to --density-epsilon")
    parser.add_argument("--limit-fit-events", type=int, default=0, help="Pilot only; zero uses all fitting events")
    parser.add_argument("--limit-dev-events", type=int, default=0, help="Pilot only; zero evaluates all DEV events")
    parser.add_argument("--skip-dev", action="store_true", help="TRAIN-only development: never load DEV waveforms or evaluate DEV")
    parser.add_argument("--resume", type=Path, help="Continue a versioned completed-epoch checkpoint with unchanged original arguments")
    parser.add_argument("--output", type=Path, default=ROOT / "results/2026-10-09/phase3")
    args = parser.parse_args()
    args.pretrain_cutoff = args.pretrain_cutoff or args.training_cutoff
    args.pretrain_density_epsilon = args.density_epsilon if args.pretrain_density_epsilon is None else args.pretrain_density_epsilon
    if min(args.epochs, args.batch_size, args.pretrain_batch_size, args.max_stations) < 1 or min(args.pretrain_epochs, args.workers, args.limit_fit_events, args.limit_dev_events) < 0:
        raise ValueError("Invalid epoch/batch/worker/pilot limits")
    if not 0 <= args.station_drop < 1 or args.density_epsilon < 0 or not math.isfinite(args.density_epsilon):
        raise ValueError("Invalid station dropout or density floor")
    if args.station_blinding == "author" and args.station_drop:
        raise ValueError("Choose author station blinding or Bernoulli station dropout, not both")
    if (args.pretrained_encoder is not None and args.pretrain_epochs < 1
            or args.pretrain_density_epsilon < 0 or not math.isfinite(args.pretrain_density_epsilon)):
        raise ValueError("Encoder import needs a positive required budget and a valid pretraining density floor")
    started = time.monotonic()
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    random.seed(args.seed)
    np.random.seed(args.seed)
    metadata, manifest = load_verified_metadata(args.cache)
    if (args.training_cutoff == "author" or args.pretrain_epochs and args.pretrain_cutoff == "author") and manifest["stored_samples"] != 3000:
        raise ValueError("The author's -4 to +25s training schedule requires a full 3000-sample cache")
    rows = split_original_train(metadata, args.calibration_fraction, args.seed)
    for split, limit in (("fit", args.limit_fit_events), ("dev", args.limit_dev_events)):
        if limit and limit < len(rows[split]):
            # Fixed pilot subset, selected before model creation and all scores.
            rng = np.random.default_rng(args.seed)
            rows[split] = np.sort(rng.choice(rows[split], limit, replace=False))
    split_manifest = {split: {"event_ids": metadata.EVENT.astype(str).iloc[ix].tolist(),
                            "source_rows": metadata.source_row_index.iloc[ix].tolist(),
                            "ids_sha256": id_digest(metadata.EVENT.iloc[ix])} for split, ix in rows.items()}
    datasets = {split: EventDataset(args.cache, metadata.iloc[ix], training=split == "fit", max_stations=args.max_stations,
                                    station_drop=args.station_drop if split == "fit" else 0., seed=args.seed,
                                    stored_samples=manifest["stored_samples"]) for split, ix in rows.items()}
    config = {**{k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items() if k != "resume"},
              "cache_sha256": manifest["sha256"], "source_sha256": manifest["source_sha256"],
              "metadata_sidecar_sha256": manifest["metadata_sidecar_sha256"],
              "metadata_sidecar_manifest_sha256": manifest["metadata_sidecar_manifest_sha256"],
              "fit_ids_sha256": split_manifest["fit"]["ids_sha256"],
              "calibration_ids_sha256": split_manifest["calibration"]["ids_sha256"],
              "dev_ids_sha256": split_manifest["dev"]["ids_sha256"],
              "learning_rate": 1e-4, "optimizer": "Adam", "gradient_clip_norm": 1.,
              "schema": manifest["schema"], "torch_version": str(torch.__version__),
              "runtime": runtime_identity(device),
              "stored_samples": manifest["stored_samples"],
              "protocol": "Magnitude-only PyTorch port with TRAIN-heldout selection; no numerical TF-equivalence claim",
              "source_sha256_files": {name: file_sha256(Path(__file__).with_name(name)) for name in ("train_team_lm.py", "team_lm.py", "training_artifacts.py")}}
    encoder_state = None
    if args.pretrain_epochs:
        config["pretraining_identity"] = pretraining_identity(
            config, station_membership(datasets["fit"]), station_membership(datasets["calibration"]),
            pretraining_implementation_sha256())
        if args.pretrained_encoder is not None:
            encoder_state, config["imported_encoder"] = load_encoder_artifact(
                args.pretrained_encoder, config["pretraining_identity"], file_sha256=file_sha256)
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    recovery = None
    if args.resume is not None:
        recovery, out = load_epoch_recovery(args.resume, config, split_manifest)
        audit_path = out / "resume_history.json"
        audit = json.loads(audit_path.read_text()) if audit_path.exists() else []
        audit.append({"checkpoint_sha256": file_sha256(args.resume), "stage": recovery["stage"],
                      "completed_epoch": recovery["completed_epoch"], "unix_time": time.time()})
        atomic_json_save(audit, audit_path)
    else:
        out = (args.output / f"team_{args.aggregation}_{digest}_{uuid.uuid4().hex[:12]}").resolve()
        out.mkdir(parents=True, exist_ok=False)
        (out / "identity.json").write_text(json.dumps(config, indent=2, allow_nan=False) + "\n")
        (out / "split_manifest.json").write_text(json.dumps(split_manifest, indent=2) + "\n")
    print("RUN_DIRECTORY", out, flush=True)
    evaluation_loaders = {split: DataLoader(datasets[split], batch_size=args.batch_size, shuffle=False, num_workers=args.workers,
                                          collate_fn=collate_events)
                          for split in (("calibration",) if args.skip_dev else ("calibration", "dev"))}
    torch.manual_seed(args.seed)
    model = TeamLM(args.aggregation)
    # Keep shared density-head initializations independent of aggregator size.
    torch.manual_seed(args.seed + 1)
    model.magnitude_head = GaussianMixtureHead()
    torch.manual_seed(args.seed + 2)
    model.single_station_head = GaussianMixtureHead()
    if encoder_state is not None:
        model.station_encoder.load_state_dict(encoder_state, strict=True)
    model.to(device)
    if recovery is not None:
        model.load_state_dict(recovery["model"], strict=True)
    torch.manual_seed(args.seed + 3)
    pretrain_history = [] if recovery is None else recovery["run_state"]["pretrain_history"]
    if args.pretrain_epochs and encoder_state is None and (recovery is None or recovery["stage"] == "pretrain"):
        station_data = StationDataset(datasets["fit"])
        parameters = list(model.station_encoder.parameters()) + list(model.single_station_head.parameters())
        optimizer = torch.optim.Adam(parameters, lr=1e-4)
        scheduler = make_plateau_scheduler(optimizer, args.lr_schedule, "pretrain")
        station_calibration = (DataLoader(StationDataset(datasets["calibration"], calibration=True),
                                         batch_size=args.pretrain_batch_size, shuffle=False, num_workers=args.workers)
                               if scheduler is not None else None)
        pretrain_start = 0
        if recovery is not None:
            restore_optimizer_and_random(optimizer, scheduler, recovery)
            pretrain_start = recovery["completed_epoch"]
        for epoch in range(pretrain_start, args.pretrain_epochs):
            generator = torch.Generator().manual_seed(args.seed + epoch)
            loader = DataLoader(station_data, batch_size=args.pretrain_batch_size, shuffle=True,
                                generator=generator, num_workers=args.workers)
            epoch_start = time.monotonic()
            loss, count, training_seconds = train_station_epoch(model, loader, optimizer, parameters, device, config, epoch)
            calibration = None
            if station_calibration is not None:
                calibration = evaluate_pretraining(model, station_calibration, device)
                step_calibration_scheduler(scheduler, calibration, split="calibration")
            pretrain_history.append({"epoch": epoch + 1, "loss": loss, "stations": count,
                                     "training_seconds": training_seconds,
                                     "epoch_seconds": time.monotonic() - epoch_start,
                                     "calibration": calibration, "learning_rate_next": optimizer.param_groups[0]["lr"],
                                     **peak_cuda_memory(device)})
            state = {"pretrain_history": pretrain_history, "history": [], "best_model": None}
            atomic_save(checkpoint(model, optimizer, "pretrain", epoch + 1, config, {}, scheduler,
                                   out=out, run_state=state), out / "latest.pth")
            (out / "pretrain_history.json").write_text(json.dumps(pretrain_history, indent=2) + "\n")
            print("PRETRAIN", pretrain_history[-1], flush=True)
        save_encoder_artifact(out / "pretrained_encoder.pth", model.station_encoder,
                              config["pretraining_identity"], config, out,
                              atomic_save=atomic_save, file_sha256=file_sha256)
    # Pretraining has a separate head and optimizer; event-model fitting starts
    # its own Adam moments exactly as in the original two-stage procedure.
    parameters = [p for name, p in model.named_parameters() if not name.startswith("single_station_head.")]
    optimizer = torch.optim.Adam(parameters, lr=1e-4)
    scheduler = make_plateau_scheduler(optimizer, args.lr_schedule, "event")
    torch.manual_seed(args.seed + 4)
    history, best_score, selected_epoch, best_model, event_start = [], math.inf, None, None, 0
    if recovery is not None and recovery["stage"] == "event":
        history = recovery["run_state"]["history"]
        best_model = recovery["run_state"]["best_model"]
        selected_epoch = recovery["selection"]["selected_epoch"]
        selected_score = recovery["selection"]["best_calibration_nll"]
        best_score = math.inf if selected_score is None else selected_score
        event_start = recovery["completed_epoch"]
        restore_optimizer_and_random(optimizer, scheduler, recovery)
    train_indices = resampling_indices(datasets["fit"].frame.MA.to_numpy(), args.magnitude_resampling)
    repeated_fit = Subset(datasets["fit"], train_indices.tolist())
    for epoch in range(event_start, args.epochs):
        datasets["fit"].epoch = epoch
        generator = torch.Generator().manual_seed(args.seed + 1000 + epoch)
        loader = DataLoader(repeated_fit, batch_size=args.batch_size, shuffle=True, generator=generator,
                            num_workers=args.workers, collate_fn=collate_events)
        model.train()
        total, count, epoch_start = 0., 0, time.monotonic()
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)
        for step, (x, coords, mask, y, _) in enumerate(loader, 1):
            x, coords, mask, y = x.to(device), coords.to(device), mask.to(device), y.float().to(device)
            cutoff = training_cutoffs(len(y), device, args.training_cutoff)
            if args.station_blinding == "author":
                mask = author_station_blinding(x, coords, mask, cutoff)
            y = smooth_training_magnitudes(y, enabled=args.event_label_smoothing)
            loss = mixture_nll(model(x, coords, mask, cutoff), y, args.density_epsilon)
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite event-model loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 1.)
            optimizer.step()
            total, count = total + float(loss.detach()) * len(y), count + len(y)
            if step == 100:
                print("TIMING", {"stage": "event", "epoch": epoch + 1,
                                 "first_100_batches_seconds": time.monotonic() - epoch_start,
                                 "total_batches": len(loader), **peak_cuda_memory(device)}, flush=True)
        training_seconds = time.monotonic() - epoch_start
        calibration, _ = evaluate(model, evaluation_loaders["calibration"], device)
        score = step_calibration_scheduler(scheduler, calibration, split="calibration")
        if args.selection == "calibration-nll" and score < best_score:
            best_score, selected_epoch = score, epoch + 1
            best_model = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            atomic_save({"model": best_model, "epoch": selected_epoch, "calibration_score": score}, out / "selected.pth")
        if args.selection == "final":
            selected_epoch = epoch + 1
        selection = {"policy": args.selection, "selected_epoch": selected_epoch,
                     "best_calibration_nll": best_score if math.isfinite(best_score) else None}
        log = {"epoch": epoch + 1, "train_loss": total / count, "events": count,
               "training_seconds": training_seconds,
               "epoch_seconds": time.monotonic() - epoch_start, "calibration": calibration,
               "learning_rate_next": optimizer.param_groups[0]["lr"], **peak_cuda_memory(device)}
        history.append(log)
        state = {"pretrain_history": pretrain_history, "history": history, "best_model": best_model}
        atomic_save(checkpoint(model, optimizer, "event", epoch + 1, config, selection, scheduler,
                               out=out, run_state=state), out / "latest.pth")
        (out / "history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
        print("EPOCH", epoch + 1, "loss", log["train_loss"], "seconds", log["epoch_seconds"], "calibration_nll", score, flush=True)
    if args.selection == "calibration-nll":
        # The recovery checkpoint embeds selected weights; a crash between the
        # two artifact writes cannot silently replace the selection with last.
        model.load_state_dict(best_model, strict=True)
        atomic_save({"model": best_model, "epoch": selected_epoch, "calibration_score": best_score}, out / "selected.pth")
    # Epoch histories are embedded in latest.pth, so repair text outputs even
    # when a crash happened just after an atomic checkpoint replacement.
    if pretrain_history:
        (out / "pretrain_history.json").write_text(json.dumps(pretrain_history, indent=2, allow_nan=False) + "\n")
    (out / "history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
    # First DEV evaluation happens after the complete fixed budget and selection.
    dev_metrics = None
    if not args.skip_dev:
        dev_metrics, predictions = evaluate(model, evaluation_loaders["dev"], device)
        (out / "dev_metrics.json").write_text(json.dumps(dev_metrics, indent=2, allow_nan=False) + "\n")
        np.savez_compressed(out / "dev_predictions.npz", **predictions)
    atomic_save({"model": model.state_dict(), "config": config, "selected_epoch": selected_epoch}, out / "model.pth")
    run = {**config, "selected_epoch": selected_epoch, "parameters": model.parameter_counts(),
           "wall_seconds": time.monotonic() - started, "wall_seconds_scope": "current_invocation",
           "recorded_training_seconds": sum(item["training_seconds"] for item in pretrain_history + history),
           "resumed": recovery is not None, "device": str(device),
           "fit_events": len(datasets["fit"]), "calibration_events": len(datasets["calibration"]), "dev_events": len(datasets["dev"]),
           "dev_evaluated": not args.skip_dev, "test_reads": 0, "selection_used_dev": False}
    atomic_json_save(run, out / "run.json")
    for dataset in datasets.values():
        dataset.close()
    print("FINISHED", out, dev_metrics, flush=True)


if __name__ == "__main__":
    main()

"""Chronological Chile TRAIN/DEV early-window TEAM-LM benchmark adaptation.

Only reviewed 1000/3000-sample TRAIN+DEV exports are accepted; TEST is not opened.
Fixed training budgets and optional checkpoint selection use an event-heldout
partition of original TRAIN. DEV is evaluated after selection, never consulted
by optimization, stopping, schedules, or checkpoint selection. The original
paper's [-4,+25] second schedule requires the full 3000-sample cache.
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import time
import uuid

import h5py
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset, Subset

from team_lm import GaussianMixtureHead, TeamLM, mixture_log_prob, mixture_mean, mixture_nll


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
    """Every station from fitting events, matching the source pretraining unit."""

    def __init__(self, events):
        if not events.training:
            raise ValueError("Pretraining can only use fitting TRAIN events")
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


def checkpoint(model, optimizer, stage, epoch, config, selection):
    return {"model": model.state_dict(), "optimizer": optimizer.state_dict(), "stage": stage,
            "completed_epoch": epoch, "config": config, "selection": selection,
            "torch_rng": torch.get_rng_state(),
            "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}


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
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--pretrain-batch-size", type=int, default=64)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--max-stations", type=int, default=25)
    parser.add_argument("--station-drop", type=float, default=0.)
    parser.add_argument("--magnitude-resampling", type=int, choices=(1, 2), default=2)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--calibration-fraction", type=float, default=.1)
    parser.add_argument("--selection", choices=("final", "calibration-nll"), default="final")
    parser.add_argument("--training-cutoff", choices=("discrete", "uniform-early", "author"), default="discrete")
    parser.add_argument("--density-epsilon", type=float, default=1e-6)
    parser.add_argument("--limit-fit-events", type=int, default=0, help="Pilot only; zero uses all fitting events")
    parser.add_argument("--limit-dev-events", type=int, default=0, help="Pilot only; zero evaluates all DEV events")
    parser.add_argument("--output", type=Path, default=ROOT / "results/2026-10-09/phase3")
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.pretrain_batch_size, args.max_stations) < 1 or min(args.pretrain_epochs, args.workers, args.limit_fit_events, args.limit_dev_events) < 0:
        raise ValueError("Invalid epoch/batch/worker/pilot limits")
    if not 0 <= args.station_drop < 1 or args.density_epsilon < 0 or not math.isfinite(args.density_epsilon):
        raise ValueError("Invalid station dropout or density floor")
    started = time.monotonic()
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    metadata, manifest = load_verified_metadata(args.cache)
    if args.training_cutoff == "author" and manifest["stored_samples"] != 3000:
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
    config = {**{k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              "cache_sha256": manifest["sha256"], "source_sha256": manifest["source_sha256"],
              "metadata_sidecar_sha256": manifest["metadata_sidecar_sha256"],
              "metadata_sidecar_manifest_sha256": manifest["metadata_sidecar_manifest_sha256"],
              "fit_ids_sha256": split_manifest["fit"]["ids_sha256"],
              "calibration_ids_sha256": split_manifest["calibration"]["ids_sha256"],
              "dev_ids_sha256": split_manifest["dev"]["ids_sha256"],
              "learning_rate": 1e-4, "optimizer": "Adam", "gradient_clip_norm": 1.,
              "schema": manifest["schema"], "torch_version": str(torch.__version__),
              "stored_samples": manifest["stored_samples"],
              "protocol": "Magnitude-only PyTorch port with TRAIN-heldout selection; no numerical TF-equivalence claim",
              "source_sha256_files": {name: file_sha256(Path(__file__).with_name(name)) for name in ("train_team_lm.py", "team_lm.py")}}
    digest = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:12]
    out = args.output / f"team_{args.aggregation}_{digest}_{uuid.uuid4().hex[:12]}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "identity.json").write_text(json.dumps(config, indent=2, allow_nan=False) + "\n")
    (out / "split_manifest.json").write_text(json.dumps(split_manifest, indent=2) + "\n")
    print("RUN_DIRECTORY", out, flush=True)
    datasets = {split: EventDataset(args.cache, metadata.iloc[ix], training=split == "fit", max_stations=args.max_stations,
                                    station_drop=args.station_drop if split == "fit" else 0., seed=args.seed,
                                    stored_samples=manifest["stored_samples"]) for split, ix in rows.items()}
    evaluation_loaders = {split: DataLoader(datasets[split], batch_size=args.batch_size, shuffle=False, num_workers=args.workers,
                                          collate_fn=collate_events) for split in ("calibration", "dev")}
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(args.seed)
    model = TeamLM(args.aggregation)
    # Keep shared density-head initializations independent of aggregator size.
    torch.manual_seed(args.seed + 1)
    model.magnitude_head = GaussianMixtureHead()
    torch.manual_seed(args.seed + 2)
    model.single_station_head = GaussianMixtureHead()
    model.to(device)
    torch.manual_seed(args.seed + 3)
    pretrain_history = []
    if args.pretrain_epochs:
        station_data = StationDataset(datasets["fit"])
        parameters = list(model.station_encoder.parameters()) + list(model.single_station_head.parameters())
        optimizer = torch.optim.Adam(parameters, lr=1e-4)
        for epoch in range(args.pretrain_epochs):
            generator = torch.Generator().manual_seed(args.seed + epoch)
            loader = DataLoader(station_data, batch_size=args.pretrain_batch_size, shuffle=True,
                                generator=generator, num_workers=args.workers)
            model.train()
            total, count = 0., 0
            for x, y in loader:
                x, y = x.to(device), y.float().to(device)
                # Source label perturbation is TRAIN-only and only above M4.
                y = y + torch.randn_like(y) * (y - 4).clamp_min(0) * .05
                mixture = model.forward_single_station(x, training_cutoffs(len(y), device, args.training_cutoff))
                loss = mixture_nll(mixture, y, args.density_epsilon)
                if not torch.isfinite(loss):
                    raise FloatingPointError("Nonfinite pretraining loss")
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(parameters, 1.)
                optimizer.step()
                total, count = total + float(loss) * len(y), count + len(y)
            pretrain_history.append({"epoch": epoch + 1, "loss": total / count, "stations": count})
            atomic_save(checkpoint(model, optimizer, "pretrain", epoch + 1, config, {}), out / "latest.pth")
            (out / "pretrain_history.json").write_text(json.dumps(pretrain_history, indent=2) + "\n")
            print("PRETRAIN", pretrain_history[-1], flush=True)
        atomic_save({"encoder": model.station_encoder.state_dict(), "fit_ids_sha256": config["fit_ids_sha256"], "config": config}, out / "pretrained_encoder.pth")
    # Pretraining has a separate head and optimizer; event-model fitting starts
    # its own Adam moments exactly as in the original two-stage procedure.
    parameters = [p for name, p in model.named_parameters() if not name.startswith("single_station_head.")]
    optimizer = torch.optim.Adam(parameters, lr=1e-4)
    torch.manual_seed(args.seed + 4)
    history, best_score, selected_epoch = [], math.inf, None
    train_indices = resampling_indices(datasets["fit"].frame.MA.to_numpy(), args.magnitude_resampling)
    repeated_fit = Subset(datasets["fit"], train_indices.tolist())
    for epoch in range(args.epochs):
        datasets["fit"].epoch = epoch
        generator = torch.Generator().manual_seed(args.seed + 1000 + epoch)
        loader = DataLoader(repeated_fit, batch_size=args.batch_size, shuffle=True, generator=generator,
                            num_workers=args.workers, collate_fn=collate_events)
        model.train()
        total, count, epoch_start = 0., 0, time.monotonic()
        for step, (x, coords, mask, y, _) in enumerate(loader, 1):
            x, coords, mask, y = x.to(device), coords.to(device), mask.to(device), y.float().to(device)
            cutoff = training_cutoffs(len(y), device, args.training_cutoff)
            loss = mixture_nll(model(x, coords, mask, cutoff), y, args.density_epsilon)
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite event-model loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 1.)
            optimizer.step()
            total, count = total + float(loss) * len(y), count + len(y)
            if step == 100:
                print("TIMING", {"epoch": epoch + 1, "first_100_batches_seconds": time.monotonic() - epoch_start,
                                 "total_batches": len(loader)}, flush=True)
        calibration, _ = evaluate(model, evaluation_loaders["calibration"], device)
        score = float(np.mean([calibration[str(int(t))]["proper_nll"] for t in TIMES]))
        if args.selection == "calibration-nll" and score < best_score:
            best_score, selected_epoch = score, epoch + 1
            atomic_save({"model": model.state_dict(), "epoch": selected_epoch, "calibration_score": score}, out / "selected.pth")
        if args.selection == "final":
            selected_epoch = epoch + 1
        selection = {"policy": args.selection, "selected_epoch": selected_epoch,
                     "best_calibration_nll": best_score if math.isfinite(best_score) else None}
        atomic_save(checkpoint(model, optimizer, "event", epoch + 1, config, selection), out / "latest.pth")
        log = {"epoch": epoch + 1, "train_loss": total / count, "events": count,
               "epoch_seconds": time.monotonic() - epoch_start, "calibration": calibration}
        history.append(log)
        (out / "history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
        print("EPOCH", epoch + 1, "loss", log["train_loss"], "seconds", log["epoch_seconds"], "calibration_nll", score, flush=True)
    if args.selection == "calibration-nll":
        chosen = torch.load(out / "selected.pth", map_location=device, weights_only=True)
        model.load_state_dict(chosen["model"])
    # First DEV evaluation happens after the complete fixed budget and selection.
    dev_metrics, predictions = evaluate(model, evaluation_loaders["dev"], device)
    atomic_save({"model": model.state_dict(), "config": config, "selected_epoch": selected_epoch}, out / "model.pth")
    (out / "dev_metrics.json").write_text(json.dumps(dev_metrics, indent=2, allow_nan=False) + "\n")
    np.savez_compressed(out / "dev_predictions.npz", **predictions)
    run = {**config, "selected_epoch": selected_epoch, "parameters": model.parameter_counts(),
           "wall_seconds": time.monotonic() - started, "device": str(device),
           "fit_events": len(datasets["fit"]), "calibration_events": len(datasets["calibration"]), "dev_events": len(datasets["dev"]),
           "test_reads": 0, "selection_used_dev": False}
    (out / "run.json").write_text(json.dumps(run, indent=2, allow_nan=False) + "\n")
    for dataset in datasets.values():
        dataset.close()
    print("FINISHED", out, dev_metrics, flush=True)


if __name__ == "__main__":
    main()

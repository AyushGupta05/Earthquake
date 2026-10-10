"""Frozen six-band exposure control; no dataset loader or automatic experiment.

Known sampling/prior correction, not a new EEW principle. A caller supplies the
audited native-late B encoder and shared export. This module never discovers or
opens waveform files, and the fitting API has no evaluation-data argument.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import tempfile
import time
from typing import Callable, Mapping

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

HORIZONS = (1, 3, 5)
SEEDS = (20261009, 20261010)
CONTROLS = ("huber_ce", "natural_ce", "band_exposure_ce")
INPUT_SHAPES = {"sensitivity": (3,), "static": (34,), "response": (72,)}
PROTOCOL_SHA256 = "51af1b54c4e0fdc0320e0d9d3d7a26fe9bdeaa77aa387ba4764f9770c88c69c6"
EPOCHS, BATCH_SIZE = 10, 512
CENTERS = (np.arange(66, dtype=np.float64) + .5) * .1


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def digest_array(value):
    a = np.ascontiguousarray(value)
    h = hashlib.sha256(str(a.dtype).encode() + json.dumps(a.shape).encode())
    h.update(a.tobytes())
    return h.hexdigest()


def bucket(salt, identifier):
    """Same fixed hash as polarization v2; caller supplies canonical station group."""
    value = hashlib.sha256((salt + "\0" + str(identifier)).encode()).digest()
    return int.from_bytes(value[:8], "big") % 10


def labels_and_support(targets):
    y = np.asarray(targets, dtype=np.float64)
    if y.ndim != 1 or not np.isfinite(y).all():
        raise ValueError("Require finite one-dimensional magnitudes")
    raw = np.floor(y / .1 + 1e-5)
    support = (y >= 0) & (raw >= 0) & (raw < 66)
    # Unsupported rows retain a sentinel; never silently clamp the truth.
    return np.where(support, raw, -1).astype(np.int64), support


def _frozen_array(value, dtype):
    a = np.array(value, dtype=dtype, copy=True)
    a.setflags(write=False)
    return a


@dataclass(frozen=True)
class PrefixPopulation:
    seconds: int
    subset: str
    source_rows: np.ndarray
    events: np.ndarray
    stations: np.ndarray
    targets: np.ndarray
    weights: np.ndarray

    def __post_init__(self):
        if self.seconds not in HORIZONS or self.subset not in ("fit", "eval_seen", "eval_held"):
            raise ValueError("Unknown deadline or subset")
        original_rows = np.asarray(self.source_rows)
        if original_rows.ndim != 1 or original_rows.dtype.kind not in "iu":
            raise ValueError("Source rows must be one-dimensional integer identities")
        for name, dtype in (("source_rows", np.int64), ("events", str), ("stations", str),
                            ("targets", np.float64), ("weights", np.float64)):
            object.__setattr__(self, name, _frozen_array(getattr(self, name), dtype))
        n = len(self.source_rows)
        if not n or any(getattr(self, k).shape != (n,) for k in ("events", "stations", "targets", "weights")):
            raise ValueError("Require aligned nonempty population vectors")
        if (self.source_rows < 0).any() or len(np.unique(self.source_rows)) != n:
            raise ValueError("Repeated or negative source row")
        if any(not x for x in self.events) or any(not x for x in self.stations):
            raise ValueError("Event and canonical station IDs are required")
        _, supported = labels_and_support(self.targets)
        if self.subset == "fit" and not supported.all():
            raise ValueError("Out-of-support fitting labels; no clipping allowed")
        if not np.isfinite(self.weights).all() or (self.weights <= 0).any():
            raise ValueError("Restoration weights must be finite positive")
        for event, station in zip(self.events, self.stations):
            event_held = bucket("polarization-event-v1", event) < 2
            station_held = bucket("polarization-station-v1", station) < 2
            expected = "eval_held" if event_held and station_held else (
                "eval_seen" if event_held else "fit" if not station_held else "excluded")
            if self.subset != expected:
                raise ValueError("Population violates the frozen event/station partition")

    def identity(self):
        return {"seconds": self.seconds, "subset": self.subset, "records": len(self.targets),
                "arrays": {k: digest_array(getattr(self, k)) for k in
                           ("source_rows", "events", "stations", "targets", "weights")}}


@dataclass(frozen=True)
class ExposurePlan:
    population: PrefixPopulation
    labels: np.ndarray
    band_counts: np.ndarray
    natural_probability: np.ndarray
    exposure_probability: np.ndarray
    log_adjustment: np.ndarray
    fine_counts: np.ndarray


def make_plan(population):
    if population.subset != "fit":
        raise ValueError("Sampler counts may only use fitting events at seen stations")
    labels, _ = labels_and_support(population.targets)
    groups = np.minimum(labels // 10, 5)
    counts = np.bincount(groups, weights=population.weights, minlength=6)
    if (counts <= 0).any() or not np.isfinite(counts).all():
        raise ValueError("All six fixed bands must have finite positive fit mass; do not regroup")
    log_a = -.5 * np.log(counts)[np.minimum(np.arange(66) // 10, 5)]
    p = population.weights / population.weights.sum()
    q = population.weights * np.exp(log_a[labels])
    q = q / q.sum()
    if not np.isfinite(p).all() or not np.isfinite(q).all() or (p <= 0).any() or (q <= 0).any():
        raise ValueError("Invalid sampler mass")
    return ExposurePlan(population, *[_frozen_array(a, dtype) for a, dtype in (
        (labels, np.int64), (counts, np.float64), (p, np.float64), (q, np.float64),
        (log_a, np.float64), (np.bincount(labels, weights=population.weights, minlength=66), np.float64))])


def checked_plans(plans):
    if set(plans) != set(HORIZONS):
        raise ValueError("Exactly the three deadlines are required")
    rows = {}
    for t in HORIZONS:
        plan = plans[t]
        if plan.population.seconds != t:
            raise ValueError("Deadline mismatch")
        # Recompute to reject mutated/hand-built inconsistent plan objects.
        rebuilt = make_plan(plan.population)
        for field in ("labels", "band_counts", "natural_probability", "exposure_probability",
                      "log_adjustment", "fine_counts"):
            if not np.array_equal(getattr(plan, field), getattr(rebuilt, field)):
                raise ValueError("Sampler plan no longer matches fitting population")
        p = plan.population
        for i, event, station, y, w in zip(p.source_rows, p.events, p.stations, p.targets, p.weights):
            identity = (str(event), str(station), float(y), float(w))
            if int(i) in rows and rows[int(i)] != identity:
                raise ValueError("Cross-deadline source row identity changed")
            rows[int(i)] = identity
    return max(len(plans[t].labels) for t in HORIZONS)


def population_digest(plans):
    checked_plans(plans)
    return digest_json({str(t): plans[t].population.identity() for t in HORIZONS})


def epoch_orders(plans, control, generator):
    """D replacement draws per horizon; A/B consume exactly the same RNG law."""
    if control not in CONTROLS or generator.device.type != "cpu":
        raise ValueError("Require a known control and explicit CPU sampling generator")
    draws = max(len(plans[t].labels) for t in HORIZONS)
    result = {}
    for t in HORIZONS:
        p = plans[t].exposure_probability if control == "band_exposure_ce" else plans[t].natural_probability
        result[t] = torch.multinomial(torch.from_numpy(p.copy()), draws, replacement=True,
                                      generator=generator).numpy()
    return result


def joint_batches(orders):
    if set(orders) != set(HORIZONS) or len({len(a) for a in orders.values()}) != 1:
        raise ValueError("Three equal-length order vectors required")
    n = len(orders[1])
    if not n:
        raise ValueError("An epoch cannot be empty")
    for start in range(0, n, BATCH_SIZE):
        yield {t: orders[t][start:start + BATCH_SIZE] for t in HORIZONS}


def loss_vector(logits, targets, labels, control, log_adjustment):
    if control not in CONTROLS or logits.ndim != 2 or logits.shape[1] != 66:
        raise ValueError("Require known control and B x 66 logits")
    if not logits.is_floating_point() or not torch.isfinite(logits).all():
        raise ValueError("Logits must be finite floating point")
    if targets.shape != logits.shape[:1] or labels.shape != targets.shape or labels.dtype != torch.int64:
        raise ValueError("Aligned targets/int64 category labels required")
    raw = torch.floor(targets.double() / .1 + 1e-5).long()
    if not torch.isfinite(targets).all() or (targets < 0).any() or not torch.equal(raw, labels):
        raise ValueError("Loss labels do not match the exact CE mapping")
    if (labels < 0).any() or (labels >= 66).any():
        raise ValueError("Unsupported fitting category")
    if log_adjustment.shape != (66,) or not torch.isfinite(log_adjustment).all():
        raise ValueError("Require finite full-grid sampler correction")
    if control == "band_exposure_ce":
        return F.cross_entropy(logits + log_adjustment.to(logits), labels, reduction="none")
    ce = F.cross_entropy(logits, labels, reduction="none")
    if control == "natural_ce":
        return ce
    centers = torch.as_tensor(CENTERS, dtype=logits.dtype, device=logits.device)
    mean = logits.softmax(-1) @ centers
    y = targets.to(logits)
    return F.huber_loss(mean, y, reduction="none", delta=1.) * (1 + 5 * (y - 3.5).clamp_min(0)) + .075 * ce


@dataclass
class LoadedPrefix:
    source_rows: np.ndarray
    inputs: Mapping[str, torch.Tensor]


def load_prefix(loader, seconds, requested_rows, device):
    """Loader must return exactly requested IDs; only four fields reach encoder."""
    expected = np.array(requested_rows, dtype=np.int64, copy=True)
    loaded = loader(seconds, expected.copy())
    if not isinstance(loaded, LoadedPrefix) or not np.array_equal(loaded.source_rows, expected):
        raise ValueError("Loader returned unaligned source identities")
    if set(loaded.inputs) != {"counts", *INPUT_SHAPES}:
        raise ValueError("Only counts/sensitivity/static/response may reach forward_prefix")
    b = len(expected)
    result = {}
    for name, value in loaded.inputs.items():
        shape = (b, 3, 100 * seconds) if name == "counts" else (b, *INPUT_SHAPES[name])
        if not isinstance(value, torch.Tensor) or tuple(value.shape) != shape or not value.is_floating_point():
            raise ValueError(f"Invalid {name} prefix input")
        if not torch.isfinite(value).all():
            raise ValueError(f"Nonfinite {name}: explicit masks/fallback must be packed before forward")
        if name == "sensitivity" and (value <= 0).any():
            raise ValueError("Sensitivity must be positive")
        result[name] = value.to(device)
    return result


def configure_runtime():
    setting = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    if torch.cuda.is_initialized() and setting != ":4096:8":
        raise RuntimeError("CUDA initialized before the frozen cuBLAS setting")
    if setting not in (None, ":4096:8"):
        raise ValueError("Frozen cuBLAS workspace is :4096:8")
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    return {"python": platform.python_version(), "torch": str(torch.__version__),
            "numpy": np.__version__, "cuda": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(), "deterministic": True,
            "CUBLAS_WORKSPACE_CONFIG": os.environ["CUBLAS_WORKSPACE_CONFIG"],
            "torch_num_threads": torch.get_num_threads(),
            "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
            "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32}


def _atomic_save(path, payload, *, torch_format=False):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix="." + path.name, delete=False) as f:
        temporary = Path(f.name)
        try:
            if torch_format:
                torch.save(payload, f)
            else:
                f.write((json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())
            f.flush()
            os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def model_digest(model):
    return digest_json({k: digest_array(v.detach().cpu().numpy()) for k, v in model.state_dict().items()})


def _validate_identity(identity, plans):
    required = {"export_sha256", "backbone_sha256", "normalizers_sha256", "population_sha256",
                "normalizer_fit_population_sha256"}
    if not required <= set(identity):
        raise ValueError("Missing shared-export/backbone/normalizer provenance")
    for key in required:
        value = identity[key]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("Require exact SHA256 provenance values")
    expected = population_digest(plans)
    if identity["population_sha256"] != expected or identity["normalizer_fit_population_sha256"] != expected:
        raise ValueError("Normalization and sampler must refer to exactly these fit-only populations")


def fit_control(model_factory: Callable[[], nn.Module], loader, plans, control, seed,
                output, identity, *, device="cpu"):
    """Ten fixed epochs. No validation callback, early stopping, or resume shortcut.

    Factory must create the reviewed B native-late model with the already fitted
    shared normalizer buffers. The caller verifies architecture/source hashes;
    this transport API does not implement or certify an unavailable backbone.
    """
    if seed not in SEEDS or control not in CONTROLS:
        raise ValueError("Only frozen seeds/controls are accepted")
    draws = checked_plans(plans)
    _validate_identity(identity, plans)
    runtime = configure_runtime()
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = torch.device(device)
    model = model_factory().to(device)
    if not callable(getattr(model, "forward_prefix", None)):
        raise TypeError("Shared backbone must implement forward_prefix(inputs, seconds)")
    initial = model_digest(model)
    configuration = {"control": control, "seed": seed, "epochs": EPOCHS, "batch_size": BATCH_SIZE,
                     "draws_per_horizon_per_epoch": draws, "protocol_sha256": PROTOCOL_SHA256,
                     "optimizer": {"name": "AdamW", "lr": 3e-4, "weight_decay": 1e-4,
                                   "cosine_eta_min": 3e-5, "gradient_clip": 5.},
                     "population": {str(t): plans[t].population.identity() for t in HORIZONS},
                     "sampling": {str(t): {"weighted_band_counts": plans[t].band_counts.tolist(),
                         "fine_counts": plans[t].fine_counts.tolist(),
                         "log_adjustment": plans[t].log_adjustment.tolist()} for t in HORIZONS},
                     "identity": dict(identity), "runtime": runtime, "device": str(device),
                     "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "initial_model_sha256": initial,
                     "parameters": sum(p.numel() for p in model.parameters()),
                     "selection": "Fixed epoch10; no held-event input during fitting"}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    _atomic_save(output / "identity.json", configuration)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS, eta_min=3e-5)
    sampler = torch.Generator(device="cpu").manual_seed(seed)
    history = []
    for epoch in range(EPOCHS):
        started = time.monotonic()
        model.train()
        orders = epoch_orders(plans, control, sampler)
        loss_sums = {t: 0. for t in HORIZONS}
        for positions in joint_batches(orders):
            optimizer.zero_grad(set_to_none=True)
            losses = []
            for t in HORIZONS:
                ix, plan = positions[t], plans[t]
                inputs = load_prefix(loader, t, plan.population.source_rows[ix], device)
                logits = model.forward_prefix(inputs, t)
                y = torch.tensor(plan.population.targets[ix], dtype=torch.float64, device=device)
                labels = torch.tensor(plan.labels[ix], dtype=torch.int64, device=device)
                adjustment = torch.tensor(plan.log_adjustment, dtype=logits.dtype, device=device)
                loss = loss_vector(logits, y, labels, control, adjustment).mean()
                losses.append(loss)
                loss_sums[t] += float(loss.detach()) * len(ix)
            combined = torch.stack(losses).mean()
            combined.backward()
            if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
                raise ValueError("Nonfinite encoder/head gradient")
            nn.utils.clip_grad_norm_(model.parameters(), 5., error_if_nonfinite=True)
            optimizer.step()
        scheduler.step()
        trace = {str(t): {"position_order_sha256": digest_array(orders[t]),
                  "source_order_sha256": digest_array(plans[t].population.source_rows[orders[t]]),
                  "draws": len(orders[t]), "unique_rows": len(np.unique(orders[t])),
                  "unique_events": len(np.unique(plans[t].population.events[orders[t]])),
                  "band_draw_counts": np.bincount(np.minimum(plans[t].labels[orders[t]] // 10, 5), minlength=6).tolist()}
                 for t in HORIZONS}
        history.append({"completed_epoch": epoch + 1, "seconds": time.monotonic() - started,
                        "loss": {str(t): loss_sums[t] / draws for t in HORIZONS}, "orders": trace})
        numpy_rng = np.random.get_state()
        state = {"schema": "eew-exposure-completed-epoch-v1", "completed_epoch": epoch + 1,
                 "model": model.state_dict(), "optimizer": optimizer.state_dict(),
                 "scheduler": scheduler.state_dict(), "sampler_rng": sampler.get_state(),
                 "torch_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state_all() if device.type == "cuda" else [],
                 "numpy_rng": {"kind": numpy_rng[0], "keys": numpy_rng[1].tolist(),
                               "position": numpy_rng[2], "has_gauss": numpy_rng[3], "cached_gauss": numpy_rng[4]},
                 "python_rng": random.getstate(),
                 "configuration": configuration, "history": history}
        _atomic_save(output / "latest.pth", state, torch_format=True)
        _atomic_save(output / "history.json", history)
    # latest.pth is the exact fixed final checkpoint; marker publishes completion last.
    result = {"control": control, "seed": seed, "completed_epoch": EPOCHS,
              "checkpoint_sha256": hashlib.sha256((output / "latest.pth").read_bytes()).hexdigest(),
              "identity_sha256": hashlib.sha256((output / "identity.json").read_bytes()).hexdigest(),
              "history_sha256": hashlib.sha256((output / "history.json").read_bytes()).hexdigest(),
              "final_model_sha256": model_digest(model), "initial_model_sha256": initial,
              "fit_population_sha256": population_digest(plans)}
    _atomic_save(output / "completed.json", result)
    return result


def require_completed_grid(directories):
    """Verify all6 immutable completion artifacts before accepting evaluation."""
    if set(directories) != {(c, s) for c in CONTROLS for s in SEEDS}:
        raise ValueError("All three controls and both seeds must finish before held-event scoring")
    records, configurations = {}, {}
    for key, directory in directories.items():
        path = Path(directory)
        record = json.loads((path / "completed.json").read_text())
        config = json.loads((path / "identity.json").read_text())
        if (record["control"], record["seed"]) != key or (config["control"], config["seed"]) != key:
            raise ValueError("Completion identity mismatch")
        if record["completed_epoch"] != EPOCHS or config["epochs"] != EPOCHS or config["protocol_sha256"] != PROTOCOL_SHA256:
            raise ValueError("Only fixed final checkpoints are eligible")
        for name, field in (("latest.pth", "checkpoint_sha256"), ("identity.json", "identity_sha256"),
                            ("history.json", "history_sha256")):
            if hashlib.sha256((path / name).read_bytes()).hexdigest() != record[field]:
                raise ValueError("Completed artifact hash changed")
        if record["initial_model_sha256"] != config["initial_model_sha256"]:
            raise ValueError("Completion initialization differs from the verified configuration")
        records[key], configurations[key] = record, config
    reference = configurations[(CONTROLS[0], SEEDS[0])]
    common = ("protocol_sha256", "population", "sampling", "identity", "runtime", "device", "parameters",
              "implementation_sha256", "draws_per_horizon_per_epoch", "batch_size", "optimizer")
    if any(any(c[field] != reference[field] for field in common) for c in configurations.values()):
        raise ValueError("Grid contains incompatible data/code/runtime/training configurations")
    for seed in SEEDS:
        if len({configurations[(c, seed)]["initial_model_sha256"] for c in CONTROLS}) != 1:
            raise ValueError("Controls did not start from identical models")
        first, second = [json.loads((Path(directories[(c, seed)]) / "history.json").read_text())
                         for c in CONTROLS[:2]]
        if [x["orders"] for x in first] != [x["orders"] for x in second]:
            raise ValueError("Natural-sampler controls did not share exact exposure")
    return records


def predict_completed_grid(directories, model_factory, loader, populations, *, identity,
                           population_validator, device="cpu"):
    """Publish predictions only after verifying the entire fixed grid completed.

    Caller archives returned natural PMFs/identities and evaluates all controls,
    seeds and their fixed equal-PMF ensembles; no sampler adjustment at inference.
    Supply identity and population_validator from the same shared binding as
    model_factory and loader. The validator must match complete held panels to
    export metadata, including source IDs, targets, weights and deadline masks.
    It must exactly match training, including export/backbone/normalizers. The
    generic callback API cannot authenticate independently supplied callbacks;
    the shared adapter owns their binding rather than arbitrary filesystem paths.
    Weights-only loading rejects pickle globals, and all checkpoint hashes and
    binding identities are checked before any model creation or waveform load.
    """
    records = require_completed_grid(directories)
    for directory in directories.values():
        config = json.loads((Path(directory) / "identity.json").read_text())
        if config["identity"] != identity:
            raise ValueError("Evaluation binding does not match the completed training provenance")
    expected = {(t, s) for t in HORIZONS for s in ("eval_seen", "eval_held")}
    if set(populations) != expected:
        raise ValueError("Both held-event panels at all three deadlines required")
    if not callable(population_validator):
        raise ValueError("A bound export metadata validator is required")
    for (t, subset), p in populations.items():
        if p.seconds != t or p.subset != subset:
            raise ValueError("Held population identity mismatch")
        population_validator(p)
    configure_runtime()
    device = torch.device(device)
    predictions = {}
    for key in ((c, s) for c in CONTROLS for s in SEEDS):
        path = Path(directories[key])
        checkpoint = torch.load(path / "latest.pth", map_location="cpu", weights_only=True)
        config = json.loads((path / "identity.json").read_text())
        if checkpoint["completed_epoch"] != EPOCHS or checkpoint["configuration"] != config:
            raise ValueError("Checkpoint is not the matching completed configuration")
        model = model_factory().to(device)
        model.load_state_dict(checkpoint["model"], strict=True)
        if model_digest(model) != records[key]["final_model_sha256"]:
            raise ValueError("Restored model differs from completed state")
        model.eval()
        with torch.inference_mode():
            for t, subset in sorted(populations):
                p = populations[(t, subset)]
                parts = []
                for start in range(0, len(p.targets), BATCH_SIZE):
                    inputs = load_prefix(loader, t, p.source_rows[start:start + BATCH_SIZE], device)
                    logits = model.forward_prefix(inputs, t)
                    if logits.shape != (len(inputs["counts"]), 66) or not torch.isfinite(logits).all():
                        raise ValueError("Invalid held-prefix predictions")
                    parts.append(logits.double().softmax(-1).cpu().numpy())
                predictions[(*key, t, subset)] = np.concatenate(parts)
    return predictions

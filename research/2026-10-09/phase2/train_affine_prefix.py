"""Fixed-epoch raw versus fully affine-projected independent-prefix benchmark.

Default: all 979487 TRAIN rows, seed 20261009, 10 epochs, batch 512; repeat with
seed 20261010. All three deadlines share the original independent backbone.
Reused validation is monitoring only; no test data or frozen-model logits.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import time

import numpy as np
import torch

from affine_prefix_control import AffinePrefixModel, CONTROLS
from feature_residual import ROOT
from run_artifacts import create_run
from train_sequential import evaluate, load_examples, supervised_loss


CACHE_PATH = Path("/data/Instance_windows_5s.hdf5")


def array_sha256(value):
    value = np.ascontiguousarray(value)
    h = hashlib.sha256()
    h.update(str(value.dtype).encode())
    h.update(json.dumps(list(value.shape)).encode())
    h.update(value.tobytes())
    return h.hexdigest()


def model_sha256(model):
    h = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        h.update(name.encode())
        h.update(array_sha256(tensor.detach().cpu().numpy()).encode())
    return h.hexdigest()


def fit_one(model, x, y, weights, centers, epochs=10, batch_size=512, on_epoch=None):
    """Preserve the original independent weighted training loop and RNG draws.

    Caller seeds immediately before model construction. No random operation is
    added here beyond the original device-local randperm per epoch. Order
    hashing records the realized permutation without changing it. Callback
    evaluation must not consume random numbers or alter model parameters.
    """
    if epochs < 1 or batch_size < 1 or len(x) == 0:
        raise ValueError("Positive epoch/batch bounds and nonempty TRAIN data required")
    if x.shape != (len(y), 3, 500) or weights.shape != y.shape or centers.shape != (66,):
        raise ValueError("Mismatched TRAIN waveforms, targets, weights, or bin centers")
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=3e-5)
    history = []
    for epoch in range(epochs):
        model.train()
        order = torch.randperm(len(y), device=y.device)
        order_hash = array_sha256(order.cpu().numpy())
        total, started = 0., time.monotonic()
        for ix in order.split(batch_size):
            outputs = model(x[ix])
            loss = supervised_loss(outputs, y[ix], weights[ix], centers, "weighted")
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite affine-control training loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.)
            optimizer.step()
            total += loss.item() * len(ix)
        scheduler.step()
        log = {"epoch": epoch + 1, "train_loss": total / len(y),
               "epoch_seconds": time.monotonic() - started, "order_sha256": order_hash}
        if on_epoch is not None:
            on_epoch(log, model)
        history.append(log)
    return history


def runtime_identity(device):
    return {"python": platform.python_version(), "torch": str(torch.__version__),
            "cuda_build": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
            "device": str(device), "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else platform.processor(),
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "cudnn_deterministic": torch.backends.cudnn.deterministic,
            "cudnn_benchmark": torch.backends.cudnn.benchmark,
            "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
            "matmul_allow_tf32": torch.backends.cuda.matmul.allow_tf32,
            "CUBLAS_WORKSPACE_CONFIG": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            "NVIDIA_TF32_OVERRIDE": os.environ.get("NVIDIA_TF32_OVERRIDE")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control", choices=CONTROLS, required=True)
    ap.add_argument("--seed", type=int, choices=(20261009, 20261010), default=20261009)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=512)
    ap.add_argument("--max-per-event", type=int, default=10000000)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    ap.add_argument("--deterministic", action=argparse.BooleanOptionalAction, default=True,
                    help="Default deterministic matched controls; opt-out changes the recorded protocol")
    ap.add_argument("--output", type=Path, default=ROOT / "results/2026-10-09/phase2")
    args = ap.parse_args(argv)
    if min(args.epochs, args.batch_size, args.max_per_event) < 1:
        ap.error("Epoch, batch, and sampling bounds must be positive")
    if args.deterministic:
        if torch.cuda.is_initialized():
            raise RuntimeError("Start a fresh process so cuBLAS determinism is configured before CUDA initialization")
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        if os.environ["CUBLAS_WORKSPACE_CONFIG"] not in (":4096:8", ":16:8"):
            raise ValueError("Deterministic CUDA requires CUBLAS_WORKSPACE_CONFIG=:4096:8 or :16:8")
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = args.deterministic
    torch.use_deterministic_algorithms(args.deterministic)
    device = torch.device(args.device)
    # Loader uses only exported validation identities, labels and bin centers;
    # it neither materializes nor passes historical CNN logits to this model.
    waves, y, weights, reference, rows = load_examples(device, args.max_per_event)
    centers = torch.tensor(reference["centers"], dtype=torch.float32, device=device)
    torch.manual_seed(args.seed)
    model = AffinePrefixModel(args.control).to(device)
    audit_path = ROOT / "results/2026-10-09/audit.json"
    audit = json.loads(audit_path.read_text())
    cache = CACHE_PATH
    stat = cache.stat()
    config = {**vars(args), "output": str(args.output), "mode": "independent",
              "objective": "weighted Huber(delta=1,beta=5,threshold=3.5)+.075CE",
              "learning_rate": 3e-4, "weight_decay": 1e-4, "cosine_eta_min": 3e-5,
              "train_records": len(rows), "train_rows_sha256": array_sha256(rows),
              "train_targets_sha256": array_sha256(y.cpu().numpy()),
              "train_weights_sha256": array_sha256(weights.cpu().numpy()),
              "metadata_sha256": {s: audit[s]["metadata_sha256"] for s in ("train", "val")},
              "validation_identity_sha256": {k: array_sha256(reference[k]) for k in ("targets", "event_ids", "trace_names", "centers")},
              "cache_stat_not_content_hash": {"path": str(cache), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns},
              "initial_model_sha256": model_sha256(model), "runtime": runtime_identity(device),
              "selection": "Fixed final epoch; reused VAL monitoring only; no TEST inference",
              "limitation": "Ideal affine-subtraction invariance only; release quantization/resampling causality remains unverified"}
    here = Path(__file__).resolve().parent
    sources = [here / n for n in ("train_affine_prefix.py", "affine_prefix_control.py", "sequential_models.py", "train_sequential.py", "feature_residual.py", "run_artifacts.py")]
    sources += [here.parent / n for n in ("frozen_head_pilot.py", "audit_and_export.py", "distribution_experiment.py")]
    out = create_run(args.output, f"affine_prefix_{args.control}_seed{args.seed}", config, sources + [audit_path])
    print("RUN_DIRECTORY", out, flush=True)
    np.savez_compressed(out / "train_rows.npz", rows=rows)
    started, saved_history = time.monotonic(), []

    def on_epoch(log, fitted):
        if log["epoch"] == 1 or log["epoch"] % 5 == 0 or log["epoch"] == args.epochs:
            result, _ = evaluate(fitted, waves["val"], reference["targets"], reference["event_ids"], reference["centers"])
            log["validation"] = result
        saved_history.append(log)
        (out / "history.json").write_text(json.dumps(saved_history, indent=2, allow_nan=False) + "\n")
        print(args.control, log["epoch"], "loss", log["train_loss"], "seconds", log["epoch_seconds"], flush=True)

    fit_one(model, waves["train"], y, weights, centers, args.epochs, args.batch_size, on_epoch)
    result, predictions = evaluate(model, waves["val"], reference["targets"], reference["event_ids"], reference["centers"])
    torch.save({"model": model.state_dict(), "config": config}, out / "model.pth")
    (out / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    np.savez_compressed(out / "predictions.npz", targets=reference["targets"], event_ids=reference["event_ids"],
                        trace_names=reference["trace_names"], centers=reference["centers"], **predictions)
    (out / "run.json").write_text(json.dumps({**config, "parameters": model.parameter_counts(),
        "wall_seconds": time.monotonic() - started, "final_model_sha256": model_sha256(model)}, indent=2, allow_nan=False) + "\n")
    print("FINISHED", out, flush=True)


if __name__ == "__main__":
    main()

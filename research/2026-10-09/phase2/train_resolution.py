"""Matched controls for frozen future-CDF supervision and revision energy.

All four controls train from scratch on the exact train_sequential row sample,
with inverse inclusion weights, the same initialization/order, and fixed final
epoch. CE + uniform ordinal scoring supervises each 1/3/5-second prediction.
The teacher is the audited existing CNN at 3/5 seconds, frozen, applied to
complete longer prefixes of the SAME training waveform. Validation teacher
inference occurs only after training and is used only for diagnostic scoring.

Controls: supervised; cdf_distill; cdf_resolution (squared CDF revision);
cdf_brier_gain (realized threshold-Brier improvement). The last two have the
same head and loss weights. Their targets are detached and NEVER clipped.
For ideal later conditional CDF T and current f, E[(f-B)^2-(T-B)^2 | X_later]
= (T-f)^2: squared revision removes outcome noise from an ideal gain target.
That identity need not hold for this imperfect trained teacher. A nonnegative
head cannot express negative expected Brier gain; diagnostics report this
limitation rather than hiding negative examples. With imperfect teachers the
unit envelope predicts empirical revision energy, not guaranteed information
gain or irreducible uncertainty. DIME (arXiv:2306.03301, ICLR 2024) is relevant
prior art for conditional-variance/value prediction; no novelty is asserted.

Example: python research/2026-10-09/phase2/train_resolution.py \
    --control cdf_resolution --epochs 20 --resolution-envelope unit
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np
import torch

from resolution_distillation import ResolutionDistillationModel, cdf_from_logits, forecast_losses
from train_sequential import load_examples, supervised_loss
from run_artifacts import create_run
from feature_residual import ROOT
from audit_and_export import EarthquakeCNN, require_checkpoint_preprocessing, sha256
from distribution_experiment import event_weights, median, metrics


CONTROLS = ("supervised", "cdf_distill", "cdf_resolution", "cdf_brier_gain")
FUTURE_HORIZONS = {1: 3, 3: 5}


def revision_targets(current_cdf, teacher_cdf, labels):
    """Two detached empirical targets; gain may be negative and stays so."""
    if current_cdf.shape != teacher_cdf.shape or labels.shape != (len(current_cdf),):
        raise ValueError("CDF targets and labels must have matching rows/boundaries")
    current, teacher = current_cdf.detach(), teacher_cdf.detach()
    boundaries = torch.arange(current.shape[1], device=current.device)
    observed = (labels[:, None] <= boundaries).to(current.dtype)
    return {
        "squared_revision": (teacher - current).square(),
        "realized_brier_gain": (current - observed).square() - (teacher - observed).square(),
    }


def training_loss(forecasts, labels, weights, teacher_cdfs, control,
                  ordinal_weight=.2, distillation_weight=1., resolution_weight=1.,
                  objective="proper", magnitudes=None, centers=None):
    """Average horizons and weighted records, matching train_sequential."""
    if control not in CONTROLS:
        raise ValueError(f"Unknown control {control!r}")
    if weights.shape != labels.shape:
        raise ValueError("One training population weight is required per record")
    if objective not in ("proper", "weighted"):
        raise ValueError("Objective must be proper or weighted")
    if objective == "weighted" and (magnitudes is None or centers is None):
        raise ValueError("Weighted objective requires actual magnitudes and bin centers")
    terms, component_values = [], {k: [] for k in ("ce", "ordinal", "distillation", "resolution")}
    uses_teacher = control != "supervised"
    uses_head = control in ("cdf_resolution", "cdf_brier_gain")
    for duration, forecast in forecasts.items():
        future = forecast["future_duration"]
        target = None
        if uses_teacher and future is not None:
            target = {"current_duration": duration, "teacher_duration": future,
                      "cdf": teacher_cdfs[future]}
        parts = forecast_losses(
            forecast, labels, target, ce_weight=1. if objective == "proper" else 0.,
            ordinal_weight=ordinal_weight if objective == "proper" else 0.,
            distillation_weight=distillation_weight if uses_teacher else 0., resolution_weight=0.,
        )
        if uses_head and future is not None:
            targets = revision_targets(forecast["cdf"], teacher_cdfs[future], labels)
            key = "squared_revision" if control == "cdf_resolution" else "realized_brier_gain"
            parts["resolution"] = .1 * (forecast["resolution"] - targets[key]).square().sum(-1)
            parts["total"] = parts["total"] + resolution_weight * parts["resolution"]
        else:
            parts["resolution"] = torch.zeros_like(parts["ce"])
        term = (weights * parts["total"]).mean()
        if objective == "weighted":
            # Exactly the existing weighted-Huber + .075 CE baseline.
            term = term + supervised_loss({duration: forecast["logits"]}, magnitudes,
                                          weights, centers, "weighted")
        terms.append(term)
        for name in component_values:
            component_values[name].append((weights * parts[name].detach()).mean())
    return torch.stack(terms).mean(), {k: torch.stack(v).mean() for k, v in component_values.items()}


def audited_teacher_paths(root, audit):
    """Resolve actual audited weights; a changed checkpoint aborts the run."""
    paths, identity = {}, {}
    for duration in (3, 5):
        info = audit["windows"][str(duration)]
        require_checkpoint_preprocessing({info["preprocessing"]})
        path = root / "bayesianprior/data" / info["checkpoint"]
        digest = sha256(path)
        if digest != info["checkpoint_sha256"]:
            raise ValueError(f"Audited {duration}s teacher checkpoint changed")
        paths[duration] = path
        identity[str(duration)] = {"path": str(path.relative_to(root)), "sha256": digest}
    return paths, identity


def load_teachers(paths, device):
    models = {}
    for duration, path in paths.items():
        model = EarthquakeCNN().to(device)
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        model.requires_grad_(False)
        model.eval()
        models[duration] = model
    return models


@torch.no_grad()
def precompute_teacher_cdfs(models, x500, batch_size=512, reference_logits=None):
    """Infer frozen teacher targets only from complete same-record prefixes.

    Optional references validate the complete validation export after training.
    No target or weight is selected based on validation agreement/performance.
    """
    if x500.ndim != 3 or x500.shape[1:] != (3, 500) or batch_size < 1:
        raise ValueError("Teacher input must be B x 3 x 500 with positive batch size")
    targets, verification = {}, {}
    for duration, model in models.items():
        if duration not in (3, 5):
            raise ValueError("Only audited 3s/5s teacher models are supported")
        model.eval()
        result = torch.empty((len(x500), 65), device=x500.device, dtype=torch.float32)
        max_error = 0.
        reference = None if reference_logits is None else reference_logits[duration]
        if reference is not None and reference.shape != (len(x500), 66):
            raise ValueError("Audited teacher logit shape disagrees with supplied examples")
        for start in range(0, len(x500), batch_size):
            end = min(start + batch_size, len(x500))
            # Never pass only the new segment: the later information contains
            # every sample available to the current student prediction.
            logits = model(x500[start:end, :, :duration * 100]).float()
            if logits.shape != (end - start, 66) or not torch.isfinite(logits).all():
                raise ValueError("Teacher returned malformed/nonfinite logits")
            result[start:end] = cdf_from_logits(logits)
            if reference is not None:
                actual = logits.cpu().numpy()
                expected = reference[start:end]
                max_error = max(max_error, float(np.max(np.abs(actual - expected))))
                if not np.allclose(actual, expected, atol=2e-3, rtol=2e-4):
                    raise ValueError(f"{duration}s teacher from 5s prefix disagrees with audited export")
        targets[duration] = result.detach()
        if reference is not None:
            verification[str(duration)] = {"max_abs_logit_error": max_error, "records": len(x500)}
    return targets, verification


def array_sha256(array):
    """Identity includes dtype/shape and exact row-ordered array bytes."""
    array = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode())
    digest.update(json.dumps(list(array.shape)).encode())
    digest.update(array.tobytes())
    return digest.hexdigest()


def save_latest_checkpoint(path, model, optimizer, scheduler, epoch, config, source_identity):
    """Atomically retain the last completed epoch; final-epoch selection is unchanged."""
    path = Path(path)
    checkpoint = {
        "model": model.state_dict(), "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(), "completed_epoch": epoch,
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_states": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        "config": config, "train_rows_sha256": config["train_rows_sha256"],
        "source_identity": source_identity,
        "selection": "Recovery checkpoint only; reported model remains the fixed final epoch",
    }
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        torch.save(checkpoint, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def clip_student_gradients(model, max_norm=5.):
    """Keep head-only gradients from rescaling the predictor in detach control."""
    torch.nn.utils.clip_grad_norm_(model.backbone.parameters(), max_norm)
    torch.nn.utils.clip_grad_norm_(model.resolution_head.parameters(), max_norm)


def _safe_correlation(a, b):
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def revision_diagnostics(current_cdf, predicted, teacher_cdf, y, event_ids, centers):
    """Descriptive validation calibration; not a certificate or a fit step."""
    if current_cdf.shape != teacher_cdf.shape or predicted.shape != current_cdf.shape:
        raise ValueError("Revision diagnostic arrays must have matching shapes")
    labels = np.floor(y / .1 + 1e-5).astype(int).clip(0, 65)
    observed = labels[:, None] <= np.arange(current_cdf.shape[1])
    revision = (teacher_cdf - current_cdf)**2
    gain = (current_cdf - observed)**2 - (teacher_cdf - observed)**2
    integrated_pred = .1 * predicted.sum(1)
    integrated_revision = .1 * revision.sum(1)
    integrated_gain = .1 * gain.sum(1)
    weights = event_weights(event_ids)
    # E[M] for arbitrary ordered centers is last center minus CDF increments.
    current_mean = centers[-1] - current_cdf @ np.diff(centers)
    teacher_mean = centers[-1] - teacher_cdf @ np.diff(centers)
    point_gain = np.abs(current_mean - y) - np.abs(teacher_mean - y)
    result = {
        "records": len(y), "events": len(np.unique(event_ids)),
        "predicted_integrated_mean": float(integrated_pred.mean()),
        "observed_revision_integrated_mean": float(integrated_revision.mean()),
        "realized_brier_gain_integrated_mean": float(integrated_gain.mean()),
        "event_macro_predicted_integrated_mean": float(weights @ integrated_pred),
        "event_macro_revision_integrated_mean": float(weights @ integrated_revision),
        "event_macro_brier_gain_integrated_mean": float(weights @ integrated_gain),
        "revision_boundary_mse": float(np.mean((predicted - revision)**2)),
        "gain_boundary_mse": float(np.mean((predicted - gain)**2)),
        "negative_gain_boundary_fraction": float(np.mean(gain < 0)),
        "negative_integrated_gain_record_fraction": float(np.mean(integrated_gain < 0)),
        "revision_target_exceeds_bernoulli_envelope_fraction": float(
            np.mean(revision > current_cdf * (1 - current_cdf) + 1e-7)),
        "predicted_revision_correlation": _safe_correlation(integrated_pred, integrated_revision),
        "predicted_actual_point_error_gain_correlation": _safe_correlation(integrated_pred, point_gain),
        "teacher_point_mae_improvement_over_current": float(point_gain.mean()),
        "head_limitation": "Nonnegative head cannot express negative expected teacher Brier gain",
        "calibration_bins": [],
    }
    # Equal-count descriptive groups; ties are retained in deterministic row
    # order. No coefficient or decision threshold is selected from these bins.
    order = np.argsort(integrated_pred, kind="stable")
    for ix in np.array_split(order, min(10, len(order))):
        result["calibration_bins"].append({
            "records": len(ix), "events": len(np.unique(event_ids[ix])),
            "predicted": float(integrated_pred[ix].mean()),
            "revision": float(integrated_revision[ix].mean()),
            "brier_gain": float(integrated_gain[ix].mean()),
            "point_error_gain": float(point_gain[ix].mean()),
        })
    return result


def head_interpretation(control, resolution_weight=1.):
    if control not in CONTROLS:
        raise ValueError(f"Unknown control {control!r}")
    if resolution_weight == 0:
        return {"trained": False, "prediction_name": None,
                "interpretation": "Auxiliary loss weight is zero; untrained head predictions are omitted"}
    if control == "cdf_resolution":
        return {"trained": True, "prediction_name": "revision_energy",
                "interpretation": "Empirical squared CDF revision; imperfect-teacher tower identity not assumed"}
    if control == "cdf_brier_gain":
        return {"trained": True, "prediction_name": "brier_gain",
                "interpretation": "Realized Brier improvement target with a nonnegative predictor; negative expectations cannot be represented"}
    return {"trained": False, "prediction_name": None,
            "interpretation": "Auxiliary head is untrained and its predictions are omitted"}


def evaluate_resolution(model, x, y, ids, centers, teacher_cdfs=None, control="supervised", resolution_weight=1.):
    """Same point/proper metrics as train_sequential, plus median and diagnostics."""
    model.eval()
    head_info = head_interpretation(control, resolution_weight)
    probabilities = {t: [] for t in (1, 3, 5)}
    cdfs, revisions = {t: [] for t in FUTURE_HORIZONS}, {t: [] for t in FUTURE_HORIZONS}
    with torch.inference_mode():
        for batch in x.split(512):
            forecasts = model.forward_with_resolution(batch)
            for duration, forecast in forecasts.items():
                probabilities[duration].append(forecast["logits"].double().softmax(1).cpu().numpy())
                if teacher_cdfs is not None and duration in FUTURE_HORIZONS:
                    cdfs[duration].append(forecast["cdf"].cpu().numpy())
                    revisions[duration].append(forecast["resolution"].cpu().numpy())
    probabilities = {t: np.concatenate(p) for t, p in probabilities.items()}
    result, predictions, diagnostics = {}, {}, {}
    for duration, p in probabilities.items():
        mean_prediction, median_prediction = p @ centers, median(p, centers)
        result[str(duration)] = metrics(y, mean_prediction, ids, p, centers)
        result[str(duration)]["median_decision"] = metrics(y, median_prediction, ids, p, centers)
        predictions[f"mean_{duration}s"] = mean_prediction
        predictions[f"median_{duration}s"] = median_prediction
    if teacher_cdfs is not None:
        for current, future in FUTURE_HORIZONS.items():
            current_cdf, predicted = np.concatenate(cdfs[current]), np.concatenate(revisions[current])
            target = teacher_cdfs[future].cpu().numpy()
            diagnostic = {"head": head_info}
            if head_info["trained"]:
                diagnostic.update(revision_diagnostics(current_cdf, predicted, target, y, ids, centers))
                predictions[f"{head_info['prediction_name']}_{current}_to_{future}"] = .1 * predicted.sum(1)
            diagnostics[f"{current}_to_{future}"] = diagnostic
            predictions[f"observed_revision_energy_{current}_to_{future}"] = .1 * ((target - current_cdf)**2).sum(1)
    return result, predictions, diagnostics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", choices=CONTROLS, required=True)
    parser.add_argument("--objective", choices=("proper", "weighted"), default="weighted")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--max-per-event", type=int, default=4)
    parser.add_argument("--ordinal-weight", type=float, default=.2)
    parser.add_argument("--distillation-weight", type=float, default=1.)
    parser.add_argument("--resolution-weight", type=float, default=1.)
    parser.add_argument("--resolution-envelope", choices=("unit", "bernoulli"), default="unit")
    parser.add_argument("--detach-aux-encoder", action="store_true",
                        help="Stop revision-head feature gradients; CDF distillation still trains the encoder")
    args = parser.parse_args()
    if min(args.epochs, args.batch_size, args.max_per_event) < 1:
        raise ValueError("Epochs, batch size, and per-event sample cap must be positive")
    if any(not np.isfinite(w) or w < 0 for w in
           (args.ordinal_weight, args.distillation_weight, args.resolution_weight)):
        raise ValueError("Loss weights must be finite and nonnegative")
    torch.set_num_threads(2)
    torch.backends.cudnn.benchmark = False
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    started = time.monotonic()
    audit_path = ROOT / "results/2026-10-09/audit.json"
    audit = json.loads(audit_path.read_text())
    teacher_paths, teacher_identity = audited_teacher_paths(ROOT, audit)
    waves, y, weights, baseline, rows = load_examples(device, args.max_per_event)
    config = {
        **vars(args), "teacher_checkpoints": teacher_identity,
        "train_rows_sha256": array_sha256(rows),
        "metadata_sha256": {split: audit[split]["metadata_sha256"] for split in ("train", "val")},
        "sampling_seed": 20261009, "future_horizons": FUTURE_HORIZONS,
        "learning_rate": 3e-4, "weight_decay": 1e-4, "cosine_eta_min": 3e-5,
        "bin_width": .1, "supervision": (
            "CE + ordinal_weight * uniform ordinal CDF score" if args.objective == "proper"
            else "Original beta=5, threshold=3.5 weighted Huber(delta=1) + .075 CE"),
        "selection": "Fixed final epoch, no validation-based hyperparameter or weight selection",
        "teacher_limit": "Audited teachers used validation in their historical training selection",
        "auxiliary_head": head_interpretation(args.control, args.resolution_weight),
    }
    here = Path(__file__).resolve().parent
    out = create_run(ROOT / "results/2026-10-09/phase2", f"resolution_{args.control}_seed{args.seed}",
                     config, list(here.glob("*.py")) + list(here.parent.glob("*.py")) + [audit_path])
    print("RUN_DIRECTORY", out, flush=True)
    np.savez_compressed(out / "train_rows.npz", rows=rows)
    teachers = load_teachers(teacher_paths, device)
    train_teacher_cdfs, _ = precompute_teacher_cdfs(teachers, waves["train"], args.batch_size)
    teacher_target_identity = {str(t): array_sha256(cdf.cpu().numpy()) for t, cdf in train_teacher_cdfs.items()}
    (out / "teacher_targets.json").write_text(json.dumps({
        "split": "train", "records": len(rows), "row_sha256": config["train_rows_sha256"],
        "cdf_sha256": teacher_target_identity, "checkpoint_identity": teacher_identity,
    }, indent=2) + "\n")
    # Teacher construction consumes RNG. Reset immediately before each matched
    # student's initialization and sample order, independent of control choice.
    torch.manual_seed(args.seed)
    model = ResolutionDistillationModel(resolution_envelope=args.resolution_envelope,
        detach_resolution_features=args.detach_aux_encoder).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=3e-5)
    labels = (y / .1 + 1e-5).floor().long().clamp(0, 65)
    centers = torch.tensor(baseline["centers"], dtype=torch.float32, device=device)
    source_identity = json.loads((out / "identity.json").read_text())
    history = []
    for epoch in range(args.epochs):
        model.train()
        order = torch.randperm(len(y), device=device)
        total, component_total = 0., {k: 0. for k in ("ce", "ordinal", "distillation", "resolution")}
        epoch_start = time.monotonic()
        for ix in order.split(args.batch_size):
            forecasts = model.forward_with_resolution(waves["train"][ix])
            batch_targets = {t: cdf[ix] for t, cdf in train_teacher_cdfs.items()}
            loss, components = training_loss(
                forecasts, labels[ix], weights[ix], batch_targets, args.control,
                args.ordinal_weight, args.distillation_weight, args.resolution_weight,
                objective=args.objective, magnitudes=y[ix], centers=centers,
            )
            if not torch.isfinite(loss):
                raise FloatingPointError("Nonfinite student training loss")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            clip_student_gradients(model)
            optimizer.step()
            total += loss.item() * len(ix)
            for name, value in components.items():
                component_total[name] += value.item() * len(ix)
        scheduler.step()
        save_latest_checkpoint(out / "latest.pth", model, optimizer, scheduler, epoch + 1, config, source_identity)
        log = {"epoch": epoch + 1, "train_loss": total / len(y),
               "components": {k: v / len(y) for k, v in component_total.items()},
               "epoch_seconds": time.monotonic() - epoch_start}
        if epoch == 0 or (epoch + 1) % 5 == 0 or epoch + 1 == args.epochs:
            result, predictions, _ = evaluate_resolution(
                model, waves["val"], baseline["targets"], baseline["event_ids"], baseline["centers"])
            log["validation"] = result
        history.append(log)
        (out / "history.json").write_text(json.dumps(history, indent=2, allow_nan=False) + "\n")
        brief = {t: {k: m[k] for k in ("mae", "m4_mae", "cvar95")}
                 for t, m in log.get("validation", {}).items()}
        print(args.control, epoch + 1, "loss", log["train_loss"], "seconds", log["epoch_seconds"], brief, flush=True)
    # Validation teacher computations begin only now, after all optimization.
    references = {}
    for duration in (3, 5):
        with np.load(ROOT / f"results/2026-10-09/validation_{duration}s.npz", allow_pickle=False) as exported:
            for key in ("targets", "event_ids", "trace_names", "centers"):
                if not np.array_equal(exported[key], baseline[key]):
                    raise ValueError("Teacher export does not match validation row/grid identity")
            references[duration] = exported["logits"]
    val_teacher_cdfs, verification = precompute_teacher_cdfs(
        teachers, waves["val"], 256, reference_logits=references)
    result, predictions, diagnostics = evaluate_resolution(
        model, waves["val"], baseline["targets"], baseline["event_ids"], baseline["centers"], val_teacher_cdfs,
        control=args.control, resolution_weight=args.resolution_weight)
    torch.save({"model": model.state_dict(), "config": config}, out / "model.pth")
    (out / "metrics.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    (out / "revision_diagnostics.json").write_text(json.dumps(diagnostics, indent=2, allow_nan=False) + "\n")
    (out / "teacher_validation_verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    np.savez_compressed(out / "predictions.npz", targets=baseline["targets"], event_ids=baseline["event_ids"],
                        trace_names=baseline["trace_names"], centers=baseline["centers"], **predictions)
    run = {**config, "parameters": model.parameter_counts(), "train_records": len(rows),
           "device": str(device), "wall_seconds": time.monotonic() - started,
           "data_status": "Reused INSTANCE validation, no test predictions",
           "head_limitation": "Nonnegative head cannot represent negative expected Brier gain"}
    (out / "run.json").write_text(json.dumps(run, indent=2, allow_nan=False) + "\n")
    print("FINISHED", run, flush=True)


if __name__ == "__main__":
    main()

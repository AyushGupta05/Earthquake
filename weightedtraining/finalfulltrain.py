from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"

try:
    from .instancepipeline import get_data_loaders, TARGET_MEAN
except ImportError:
    from instancepipeline import get_data_loaders, TARGET_MEAN

import torch
import torch.nn as nn
import torchmetrics
import optuna


class EarthquakeCNN(nn.Module):

    def __init__(self):
        super(EarthquakeCNN, self).__init__()

        blocks = []
        in_channels = 3

        n_filters = [16,32,64,128,256,512]

        for i in range(6):
            out_channels = n_filters[i]

            padding = (5 - 1) // 2

            layers = [
                nn.Conv1d(
                    in_channels,
                    out_channels,
                    kernel_size=5,
                    padding=padding
                )
            ]

            layers.append(nn.ReLU())
            layers.append(nn.MaxPool1d(2))

            block = nn.Sequential(*layers)

            blocks.append(block)
            in_channels = out_channels

        self.features = nn.Sequential(*blocks)
        self.global_pool = nn.AdaptiveAvgPool1d(1)

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.5),
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(128, 1)
        )

    def forward(self, x):
        x = self.features(x)
        x = self.global_pool(x)
        x = self.classifier(x)

        return x


class WeightedHuberLoss(nn.Module):

    def __init__(self, threshold, beta, target_mean = TARGET_MEAN, delta = 1.0):
        super().__init__()

        self.threshold = threshold
        self.beta = beta
        self.target_mean = target_mean
        self.delta = delta

        self.huber = nn.HuberLoss(
            delta=delta,
            reduction="none"
        )

    def forward(self, predictions, targets):

        individual_losses = self.huber(
            predictions,
            targets
        )

        actual_magnitudes = targets + self.target_mean

        weights = 1.0 + self.beta * torch.clamp(
            actual_magnitudes - self.threshold,
            min=0.0
        )

        weighted_loss = (
            weights * individual_losses
        ).mean()

        return weighted_loss


def train_epoch(model, train_loader, loss_function, optimizer, device):
    model.train()

    running_loss = 0.0
    running_mae = 0.0
    correct = 0
    total = 0
    tolerance = 0.2
    log_interval = 200

    for batch_idx, (data, target) in enumerate(train_loader):
        data = data.to(device, non_blocking=True)
        target = target.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        output = model(data).squeeze(-1)
        loss = loss_function(output, target)

        loss.backward()
        optimizer.step()

        batch_size = data.size(0)

        running_loss += loss.item() * batch_size
        running_mae += torch.abs(output - target).sum().item()
        correct += (torch.abs(output - target) <= tolerance).sum().item()
        total += batch_size

        if (batch_idx + 1) % log_interval == 0:
            avg_mae = running_mae / total
            avg_loss = running_loss / total
            accuracy = correct / total * 100

            print(
                f"Batch {batch_idx + 1} | "
                f"Loss: {avg_loss:.4f} | "
                f"MAE: {avg_mae:.4f} | "
                f"Accuracy ±0.2: {accuracy:.2f}%"
            )

    epoch_loss = running_loss / total
    epoch_mae = running_mae / total
    epoch_accuracy = correct / total * 100

    return epoch_loss, epoch_mae, epoch_accuracy


def evaluate_metrics(model, dataloader, device):
    model.eval()

    correct = 0
    total = 0

    mae = torchmetrics.MeanAbsoluteError().to(device)
    mse = torchmetrics.MeanSquaredError().to(device)

    tolerance = 0.2

    with torch.no_grad():
        for waveforms, magnitudes in dataloader:
            waveforms = waveforms.to(device, non_blocking=True)
            magnitudes = magnitudes.to(device, non_blocking=True)

            predictions = model(waveforms).squeeze(-1)

            correct += (torch.abs(predictions - magnitudes) <= tolerance).sum().item()
            total += magnitudes.size(0)

            mae.update(predictions, magnitudes)
            mse.update(predictions, magnitudes)

    mse_value = mse.compute().item()

    return mse_value, mae.compute().item(), mse_value ** 0.5, correct / total * 100


def evaluate_by_magnitude(model, dataloader, device, magnitude_threshold):
    model.eval()

    all_predictions = []
    all_targets = []

    with torch.no_grad():
        for waveforms, magnitudes in dataloader:
            waveforms = waveforms.to(device, non_blocking=True)
            magnitudes = magnitudes.to(device, non_blocking=True)

            predictions = model(waveforms).squeeze(-1)

            actual_predictions = predictions + TARGET_MEAN
            actual_magnitudes = magnitudes + TARGET_MEAN

            mask = actual_magnitudes >= magnitude_threshold

            if mask.any():
                all_predictions.append(
                    actual_predictions[mask].cpu()
                )

                all_targets.append(
                    actual_magnitudes[mask].cpu()
                )

    if len(all_predictions) == 0:
        return float("nan"), float("nan"), float("nan"), 0

    all_predictions = torch.cat(all_predictions)
    all_targets = torch.cat(all_targets)

    errors = all_predictions - all_targets

    mae = torch.abs(errors).mean().item()

    mse = torch.mean(
        errors ** 2
    ).item()

    rmse = mse ** 0.5

    bias = errors.mean().item()

    count = all_targets.size(0)

    return mae, rmse, bias, count


def run_experiment(model,train_loader,val_loader,device,threshold,beta,num_epochs=40,lr=0.000494,weight_decay=1.511446e-07,
    checkpoint_path=None
):
    model = model.to(device)

    if checkpoint_path is None:
        checkpoint_path = DATA_DIR / (
            f"weighted_threshold_{threshold:.4f}_beta_{beta}.pth"
        )

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print(f"Trainable parameters: {trainable_params:,}")
    print(f"Threshold: {threshold:.4f}")
    print(f"Beta: {beta}")

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=weight_decay
    )

    loss_function = WeightedHuberLoss(
        threshold=threshold,
        beta=beta,
        target_mean=TARGET_MEAN,
        delta=1.0
    )

    best_rmse = float("inf")
    best_epoch = 0

    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")

        train_loss, train_mae, train_accuracy = train_epoch(
            model,
            train_loader,
            loss_function,
            optimizer,
            device
        )

        val_mse, val_mae, val_rmse, val_accuracy = evaluate_metrics(
            model,
            val_loader,
            device
        )

        print(
            f"Train | "
            f"Loss: {train_loss:.4f} | "
            f"MAE: {train_mae:.4f} | "
            f"Accuracy ±0.2: {train_accuracy:.2f}%"
        )

        print(
            f"Val   | "
            f"MSE: {val_mse:.4f} | "
            f"MAE: {val_mae:.4f} | "
            f"RMSE: {val_rmse:.4f} | "
            f"Accuracy ±0.2: {val_accuracy:.2f}%"
        )

        if val_rmse < best_rmse:
            best_rmse = val_rmse
            best_epoch = epoch + 1

            checkpoint = {
                "epoch": best_epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "threshold": threshold,
                "beta": beta,
                "val_rmse": val_rmse,
                "val_mae": val_mae,
                "val_mse": val_mse,
                "val_accuracy_0.2": val_accuracy,
                "trainable_params": trainable_params
            }

            torch.save(checkpoint, checkpoint_path)

            print(
                f"New best model saved | "
                f"Epoch {best_epoch} | "
                f"Val RMSE: {val_rmse:.4f}"
            )

    checkpoint = torch.load(
        checkpoint_path,
        map_location=device
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    print(f"\nLoaded best model from epoch {checkpoint['epoch']}")

    val_35_mae, val_35_rmse, val_35_bias, val_35_count = evaluate_by_magnitude(
        model,
        val_loader,
        device,
        magnitude_threshold=3.5
    )

    val_40_mae, val_40_rmse, val_40_bias, val_40_count = evaluate_by_magnitude(
        model,
        val_loader,
        device,
        magnitude_threshold=4.0
    )

    checkpoint["val_3.5_mae"] = val_35_mae
    checkpoint["val_3.5_rmse"] = val_35_rmse
    checkpoint["val_3.5_bias"] = val_35_bias
    checkpoint["val_3.5_count"] = val_35_count

    checkpoint["val_4.0_mae"] = val_40_mae
    checkpoint["val_4.0_rmse"] = val_40_rmse
    checkpoint["val_4.0_bias"] = val_40_bias
    checkpoint["val_4.0_count"] = val_40_count

    torch.save(
        checkpoint,
        checkpoint_path
    )

    print(
        f"Val M >= 3.5 | "
        f"MAE: {val_35_mae:.4f} | "
        f"RMSE: {val_35_rmse:.4f} | "
        f"Bias: {val_35_bias:.4f} | "
        f"N: {val_35_count}"
    )

    print(
        f"Val M >= 4.0 | "
        f"MAE: {val_40_mae:.4f} | "
        f"RMSE: {val_40_rmse:.4f} | "
        f"Bias: {val_40_bias:.4f} | "
        f"N: {val_40_count}"
    )

    return model, checkpoint


if __name__ == "__main__":

    DATA_DIR.mkdir(exist_ok=True)

    train_loader, val_loader, test_loader = get_data_loaders()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"Using {device}")

    def objective(trial):

        threshold = trial.suggest_float(
            "threshold",
            3.5,
            4.0
        )

        beta = trial.suggest_categorical(
            "beta",
            [1,2,3,4,5]
        )

        print("\n" + "=" * 70)

        print(
            f"Trial {trial.number} | "
            f"Threshold: {threshold:.4f} | "
            f"Beta: {beta}"
        )

        print("=" * 70)

        model = EarthquakeCNN().to(device)

        checkpoint_path = DATA_DIR / (
            f"trial_{trial.number}_"
            f"threshold_{threshold:.4f}_"
            f"beta_{beta}.pth"
        )

        model, checkpoint = run_experiment(
            model,
            train_loader,
            val_loader,
            device,
            threshold=threshold,
            beta=beta,
            checkpoint_path=checkpoint_path
        )

        trial.set_user_attr(
            "checkpoint_path",
            str(checkpoint_path)
        )

        trial.set_user_attr(
            "best_epoch",
            checkpoint["epoch"]
        )

        trial.set_user_attr(
            "val_mae",
            checkpoint["val_mae"]
        )

        trial.set_user_attr(
            "val_rmse",
            checkpoint["val_rmse"]
        )

        trial.set_user_attr(
            "val_accuracy",
            checkpoint["val_accuracy_0.2"]
        )

        trial.set_user_attr(
            "val_3.5_mae",
            checkpoint["val_3.5_mae"]
        )

        trial.set_user_attr(
            "val_3.5_rmse",
            checkpoint["val_3.5_rmse"]
        )

        trial.set_user_attr(
            "val_3.5_bias",
            checkpoint["val_3.5_bias"]
        )

        trial.set_user_attr(
            "val_3.5_count",
            checkpoint["val_3.5_count"]
        )

        trial.set_user_attr(
            "val_4.0_mae",
            checkpoint["val_4.0_mae"]
        )

        trial.set_user_attr(
            "val_4.0_rmse",
            checkpoint["val_4.0_rmse"]
        )

        trial.set_user_attr(
            "val_4.0_bias",
            checkpoint["val_4.0_bias"]
        )
        lambda_bias = 1.0
        bias_penalty = abs(checkpoint["val_4.0_bias"])

        objective_value = (
            checkpoint["val_rmse"]
            + lambda_bias * bias_penalty
        )

        return objective_value


    study = optuna.create_study(
        direction="minimize"
    )

    study.optimize(
        objective,
        n_trials=20
    )
    study.trials_dataframe().to_csv(
    DATA_DIR / "weighted_loss_optuna_results.csv",
    index=False
)

    print("\nBest trial:")

    print(
        f"Trial: {study.best_trial.number}"
    )

    print(
        f"Threshold: "
        f"{study.best_params['threshold']:.4f}"
    )

    print(
        f"Beta: "
        f"{study.best_params['beta']}"
    )

    print(
        f"Validation RMSE: "
        f"{study.best_value:.4f}"
    )

    print(
        f"Validation M >= 3.5 RMSE: "
        f"{study.best_trial.user_attrs['val_3.5_rmse']:.4f}"
    )

    print(
        f"Validation M >= 3.5 Bias: "
        f"{study.best_trial.user_attrs['val_3.5_bias']:.4f}"
    )

    print(
        f"Validation M >= 4.0 RMSE: "
        f"{study.best_trial.user_attrs['val_4.0_rmse']:.4f}"
    )

    print(
        f"Validation M >= 4.0 Bias: "
        f"{study.best_trial.user_attrs['val_4.0_bias']:.4f}"
    )

    best_checkpoint_path = Path(
        study.best_trial.user_attrs["checkpoint_path"]
    )

    checkpoint = torch.load(
        best_checkpoint_path,
        map_location=device
    )

    model = EarthquakeCNN().to(device)

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    test_mse, test_mae, test_rmse, test_accuracy = evaluate_metrics(
        model,
        test_loader,
        device
    )

    test_35_mae, test_35_rmse, test_35_bias, test_35_count = evaluate_by_magnitude(
        model,
        test_loader,
        device,
        magnitude_threshold=3.5
    )

    test_40_mae, test_40_rmse, test_40_bias, test_40_count = evaluate_by_magnitude(
        model,
        test_loader,
        device,
        magnitude_threshold=4.0
    )

    print(
        f"\nTest   | "
        f"MSE: {test_mse:.4f} | "
        f"MAE: {test_mae:.4f} | "
        f"RMSE: {test_rmse:.4f} | "
        f"Accuracy ±0.2: {test_accuracy:.2f}%"
    )

    print(
        f"Test M >= 3.5 | "
        f"MAE: {test_35_mae:.4f} | "
        f"RMSE: {test_35_rmse:.4f} | "
        f"Bias: {test_35_bias:.4f} | "
        f"N: {test_35_count}"
    )

    print(
        f"Test M >= 4.0 | "
        f"MAE: {test_40_mae:.4f} | "
        f"RMSE: {test_40_rmse:.4f} | "
        f"Bias: {test_40_bias:.4f} | "
        f"N: {test_40_count}"
    )
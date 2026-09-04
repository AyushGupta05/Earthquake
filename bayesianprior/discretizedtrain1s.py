from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"

try:
    from .instancepipelineprior import get_data_loaders
except ImportError:
    from instancepipeline import get_data_loaders

import torch
import torch.nn as nn
import torchmetrics
import optuna
MIN_MAGNITUDE = 0.0
MAX_MAGNITUDE = 6.6
BIN_WIDTH = 0.1



BIN_CENTERS = torch.arange(
    MIN_MAGNITUDE + BIN_WIDTH / 2,
    MAX_MAGNITUDE,
    BIN_WIDTH,
    dtype=torch.float32
)
NUM_BINS = len(BIN_CENTERS)
def magnitude_to_bin(targets):
    target_bins = ((targets - MIN_MAGNITUDE) / BIN_WIDTH).long()
    target_bins = torch.clamp(target_bins, 0, NUM_BINS - 1)
    return target_bins

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
            nn.Linear(128, NUM_BINS)
        )

    def forward(self, x):
        x = self.features(x)
        x = self.global_pool(x)
        x = self.classifier(x)

        return x
def logits_to_magnitude(logits,bin_centers):
    probabilities = torch.softmax(logits,dim=1)

    predictions = torch.sum(probabilities* bin_centers.unsqueeze(0),dim=1)
    return predictions

class WeightedHuberLoss(nn.Module):

    def __init__(self, threshold = 3.6, beta = 5,  delta = 1.0):
        super().__init__()

        self.threshold = threshold
        self.beta = beta


        self.huber = nn.HuberLoss(
            delta=delta,
            reduction="none"
        )

    def forward(self, predictions, targets):

        individual_losses = self.huber(predictions,targets)

        
        weights = (1.0+ self.beta* torch.clamp(targets - self.threshold,min=0.0)
        )
        weighted_loss = (
            weights * individual_losses
        ).mean()

        return weighted_loss

def train_epoch(model, train_loader, huber_loss_function, cross_entropy_loss_function, gamma, optimizer, device):
    model.train()

    running_loss = 0.0
    running_mae = 0.0
    correct = 0
    total = 0
    tolerance = 0.2
    log_interval = 200
    bin_centers = BIN_CENTERS.to(device)

    for batch_idx, (data, target) in enumerate(train_loader):
        data = data.to(device, non_blocking=True)
        target = target.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        logits = model(data)
        predictions = logits_to_magnitude(logits, bin_centers)

        target_bins = magnitude_to_bin(target)

        huber_loss = huber_loss_function(predictions, target)
        cross_loss = cross_entropy_loss_function(logits, target_bins)

        loss = huber_loss + gamma * cross_loss

        loss.backward()
        optimizer.step()

        batch_size = data.size(0)

        running_loss += loss.item() * batch_size
        running_mae += torch.abs(predictions - target).sum().item()
        correct += (torch.abs(predictions - target) <= tolerance).sum().item()
        total += batch_size

        if (batch_idx + 1) % log_interval == 0:
            avg_mae = running_mae / total
            avg_loss = running_loss / total
            accuracy = correct / total * 100

            print(
                f"Batch {batch_idx + 1} | "
                f"Loss: {avg_loss:.4f} | "
                f"MAE: {avg_mae:.4f} | "
                f"Accuracy ±0.2: {accuracy:.2f}% | "
                f"Huber: {huber_loss.item():.4f} | "
                f"CE: {cross_loss.item():.4f}"
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
    bin_centers = BIN_CENTERS.to(device)

    with torch.no_grad():
        for waveforms, magnitudes in dataloader:

            waveforms = waveforms.to(device,non_blocking=True)

            magnitudes = magnitudes.to(device,non_blocking=True)

            logits = model(waveforms)

            predictions = logits_to_magnitude(logits,bin_centers)

            correct += (torch.abs(predictions - magnitudes)<= tolerance).sum().item()

            total += magnitudes.size(0)

            mae.update(predictions, magnitudes)
            mse.update(predictions, magnitudes)

    mse_value = mse.compute().item()

    return (mse_value, mae.compute().item(),mse_value ** 0.5,correct / total * 100)

def evaluate_by_magnitude(model, dataloader, device, magnitude_threshold):
    model.eval()

    all_predictions = []
    all_targets = []

    bin_centers = BIN_CENTERS.to(device)

    with torch.no_grad():
        for waveforms, magnitudes in dataloader:
            waveforms = waveforms.to(device, non_blocking=True)
            magnitudes = magnitudes.to(device, non_blocking=True)

            logits = model(waveforms)
            predictions = logits_to_magnitude(logits, bin_centers)

            mask = magnitudes >= magnitude_threshold

            if mask.any():
                all_predictions.append(predictions[mask].cpu())
                all_targets.append(magnitudes[mask].cpu())

    if len(all_predictions) == 0:
        return float("nan"), float("nan"), float("nan"), 0

    all_predictions = torch.cat(all_predictions)
    all_targets = torch.cat(all_targets)

    errors = all_predictions - all_targets

    mae = torch.abs(errors).mean().item()
    mse = torch.mean(errors ** 2).item()
    rmse = mse ** 0.5
    bias = errors.mean().item()
    count = all_targets.size(0)

    return mae, rmse, bias, count


def run_experiment(model,train_loader,val_loader,device,threshold,beta,num_epochs=40,lr=0.000494,weight_decay=1.511446e-07,
    checkpoint_path=None
):
    model = model.to(device)



    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print(f"Trainable parameters: {trainable_params:,}")


    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=weight_decay
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer,
    mode="min",
    factor=0.1,
    patience=3
)

    huber_loss_function = WeightedHuberLoss(
        threshold=threshold,
        beta=beta,
        
        delta=1.0
    )
    cross_entropy_loss_function = nn.CrossEntropyLoss()
    gamma = 0.075

    best_rmse = float("inf")
    best_epoch = 0

    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")

        train_loss, train_mae, train_accuracy = train_epoch(
            model,
            train_loader,
            huber_loss_function,
            cross_entropy_loss_function,
            gamma,
            optimizer,
            device
        )

        val_mse, val_mae, val_rmse, val_accuracy = evaluate_metrics(
            model,
            val_loader,
            device
        )
        scheduler.step(val_rmse)

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
                "gamma" :gamma,
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

    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )


    print(f"Using {device}")

    checkpoint_path = DATA_DIR / "best_model_huberandcross1s075.pth"

    # Create fresh model
    model = EarthquakeCNN().to(device)

    # Train model and automatically reload best validation checkpoint
    model, checkpoint = run_experiment(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        threshold=3.5,
        beta=5,
        num_epochs=50,
        lr=0.000494,
        weight_decay=1.511446e-07,
        checkpoint_path=checkpoint_path
    )

    # At this point `model` is already the best validation model

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
        f"\nTest | "
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

    # Add test metrics to checkpoint
    checkpoint["test_mse"] = test_mse
    checkpoint["test_mae"] = test_mae
    checkpoint["test_rmse"] = test_rmse
    checkpoint["test_accuracy_0.2"] = test_accuracy

    checkpoint["test_3.5_mae"] = test_35_mae
    checkpoint["test_3.5_rmse"] = test_35_rmse
    checkpoint["test_3.5_bias"] = test_35_bias
    checkpoint["test_3.5_count"] = test_35_count

    checkpoint["test_4.0_mae"] = test_40_mae
    checkpoint["test_4.0_rmse"] = test_40_rmse
    checkpoint["test_4.0_bias"] = test_40_bias
    checkpoint["test_4.0_count"] = test_40_count

    torch.save(
        checkpoint,
        checkpoint_path
    )

    print(f"\nFinal checkpoint saved to: {checkpoint_path}")
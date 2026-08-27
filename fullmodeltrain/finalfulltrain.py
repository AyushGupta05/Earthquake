from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"

try:
    from .instancepipeline import get_data_loaders
except ImportError:
    from instancepipeline import get_data_loaders

import torch
import torch.nn as nn
import torchmetrics


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


def run_experiment(model,train_loader,val_loader,device,num_epochs=200,lr=0.000494,weight_decay=1.511446e-07,
    checkpoint_path=DATA_DIR / "best_model_full.pth"
):
    model = model.to(device)

    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print(f"Trainable parameters: {trainable_params:,}")

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=weight_decay
    )

    loss_function = nn.HuberLoss(delta=1.0)

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

    checkpoint = torch.load(checkpoint_path, map_location=device)

    model.load_state_dict(checkpoint["model_state_dict"])

    print(f"\nLoaded best model from epoch {checkpoint['epoch']}")

    return model, checkpoint


if __name__ == "__main__":

    DATA_DIR.mkdir(exist_ok=True)

    train_loader, val_loader, test_loader = get_data_loaders()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print(f"Using {device}")

    model = EarthquakeCNN().to(device)

    model, checkpoint = run_experiment(
        model,
        train_loader,
        val_loader,
        device
    )

    test_mse, test_mae, test_rmse, test_accuracy = evaluate_metrics(
        model,
        test_loader,
        device
    )

    print(
        f"Test   | "
        f"MSE: {test_mse:.4f} | "
        f"MAE: {test_mae:.4f} | "
        f"RMSE: {test_rmse:.4f} | "
        f"Accuracy ±0.2: {test_accuracy:.2f}%"
    )

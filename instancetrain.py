from instancepipeline import get_data_loaders
import torch
import torch.nn as nn
import torch.optim as optim 
import torchvision 
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from torchvision import datasets
import torchmetrics 


if __name__ == "__main__":
    train_loader, val_loader, test_loader = get_data_loaders()

    class EarthquakeCNN(nn.Module):

        def __init__(self):
            super().__init__()

            self.features = nn.Sequential(
                nn.Conv1d(3, 32, kernel_size=5, padding=2),
                nn.ReLU(),
                nn.MaxPool1d(2),

                nn.Conv1d(32, 64, kernel_size=5, padding=2),
                nn.ReLU(),
                nn.MaxPool1d(2),

                nn.Conv1d(64, 128, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.MaxPool1d(2),
                nn.Conv1d(128, 256, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AvgPool1d(2),
            )


            self.regressor = nn.Sequential(
                nn.Flatten(),
                nn.Linear(256 * 18, 128),
                nn.ReLU(),
                nn.Linear(128, 1)
            )
        def forward(self, x):

            # Block 1
            x = self.features(x)
            x = self.regressor(x)
        
            return x
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print (f"Using {device}")

    model = EarthquakeCNN().to(device)

    def train_epoch(model, train_loader, loss_function,optimizer,device):
        model.train()
        running_loss = 0.0 
        accuracy_sum = 0.0
        tolerance = 0.2

        for batch_idx, (data,target) in enumerate(train_loader):
            data = data.to(device, non_blocking=True)
            target = target.to(device, non_blocking=True)
            optimizer.zero_grad()
            output = model(data).squeeze(-1)
            loss = loss_function(output,target)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            
            iaccuracy = (torch.abs(output - target) <= tolerance).float().mean().item()
            accuracy_sum += iaccuracy

        

            
            if (batch_idx + 1)%200 == 0:
                
                
                avg_accuracy = accuracy_sum/200 * 100
                avg_loss = running_loss/200
                
                print( f"Loss: {avg_loss:.3f} | "f" Train Accuracy within +- 0.2: {avg_accuracy}%")
                running_loss = 0.0 
                accuracy_sum = 0.0


    def evaluate_metrics(model, val_dataloader, device):
        model.eval()
        correct = 0
        total = 0
        mae = torchmetrics.MeanAbsoluteError().to(device)
        rmse = torchmetrics.MeanSquaredError(squared=False).to(device)

        with torch.no_grad():
            for waveforms, magnitudes in val_dataloader:
                waveforms = waveforms.to(device, non_blocking = True)
                magnitudes = magnitudes.to(device, non_blocking = True)
                tolerance = 0.2
                predictions = model(waveforms).squeeze(-1)
                correct += (torch.abs(predictions - magnitudes) <= tolerance).sum().item()
                total += magnitudes.size(0)
                mae.update(predictions, magnitudes)
                rmse.update(predictions, magnitudes)

        return mae.compute().item(), rmse.compute().item(), correct / total * 100


    optimizer = torch.optim.AdamW(model.parameters(),lr = 0.001,weight_decay=1e-4)
    loss_function = nn.MSELoss()


    num_epochs =40
    best_rmse = float("inf")
    for epoch in range (num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")
        train_epoch(model, train_loader, loss_function,optimizer,device)
        mae,rmse,accuracy = evaluate_metrics(model,val_loader,device)
        print(f"RMSE: {rmse:.3f} | Val accuracy: {accuracy:.2f}%")
        if rmse < best_rmse:
            best_rmse = rmse

            torch.save(
            model.state_dict(),
            "Baseline_Instance_params1.pth"
            )


    model.load_state_dict(
        torch.load(
            "Baseline_Instance_params1.pth",
            map_location=device
        )
    )
    print("Test metrics:")
    mae, rmse,accuracy  = evaluate_metrics(model, test_loader, device)
    print(f"the rmse of test set is {rmse} and accuracy is {accuracy}")
    

    print(f"the best rmse is {best_rmse}")
    print("\nModel saved as Baseline_Instance_params1.pth")
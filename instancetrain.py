from instancepipeline import get_data_loaders 
import torch 
import torch.nn as nn 
import torchmetrics 
import optuna 
 
class FlexibleEarthquakeCNN(nn.Module): 
 
    def __init__(self, n_layers, n_filters, kernel_size, dropout_rate, fc_size,use_batchnorm): 
        super(FlexibleEarthquakeCNN, self).__init__() 
        blocks = [] 
        in_channels = 3 
 
        for i in range(n_layers): 
            out_channels = n_filters[i] 
            
            padding = (kernel_size - 1) // 2 
 
 
            layers = [ 
                nn.Conv1d( 
                    in_channels, 
                    out_channels, 
                    kernel_size=kernel_size, 
                    padding=padding 
                ) 
            ] 
 
            if use_batchnorm: 
                layers.append( 
                    nn.BatchNorm1d(out_channels) 
                ) 
 
            layers.append(nn.ReLU()) 
            layers.append(nn.MaxPool1d(2)) 
 
            block = nn.Sequential(*layers) 
 
            blocks.append(block) 
            in_channels = out_channels 
                     
        self.features = nn.Sequential(*blocks) 
        self.global_pool = nn.AdaptiveAvgPool1d(1) 
        self.classifier = nn.Sequential( 
            nn.Flatten(), 
            nn.Dropout(dropout_rate), 
            nn.Linear(n_filters[-1], fc_size), 
            nn.ReLU(), 
            nn.Dropout(dropout_rate), 
            nn.Linear(fc_size, 1) 
        ) 
 
 
 
    def forward(self, x): 
        x = self.features(x) 
        x = self.global_pool(x) 
        x = self.classifier(x) 
 
        return x 
 
def train_epoch(model, train_loader, loss_function,optimizer,device): 
    model.train() 
    running_loss = 0.0  
    running_mae = 0.0 
    correct = 0 
    total = 0 
    tolerance = 0.2 
    log_interval = 200 
 
    for batch_idx, (data,target) in enumerate(train_loader): 
        data = data.to(device, non_blocking=True) 
        target = target.to(device, non_blocking=True) 
        optimizer.zero_grad(set_to_none = True) 
        output = model(data).squeeze(-1) 
        loss = loss_function(output,target) 
        loss.backward() 
        optimizer.step() 
        batch_size = data.size(0) 
        running_loss += loss.item() * batch_size 
         
        running_mae += torch.abs(output - target).sum().item() 
        correct += (torch.abs(output - target) <= tolerance).sum().item() 
        total += batch_size 
     
        if (batch_idx + 1)%log_interval == 0: 
             
            avg_mae = running_mae /total 
            avg_loss = running_loss/total 
            accuracy = correct/total* 100 
            print( 
            f"Batch {batch_idx + 1} | " 
            f"MSE: {avg_loss:.4f} | " 
            f"MAE: {avg_mae:.4f} | " 
            f"Accuracy ±0.2: {accuracy:.2f}%" 
        ) 
    epoch_mse = running_loss / total 
    epoch_mae = running_mae / total 
    epoch_accuracy = correct / total * 100 
 
    return epoch_mse, epoch_mae, epoch_accuracy 
 
def evaluate_metrics(model, dataloader, device): 
    model.eval() 
    correct = 0 
    total = 0 
    mae = torchmetrics.MeanAbsoluteError().to(device) 
     
    mse = torchmetrics.MeanSquaredError().to(device) 
    tolerance = 0.2 
    with torch.no_grad(): 
        for waveforms, magnitudes in dataloader: 
            waveforms = waveforms.to(device, non_blocking = True) 
            magnitudes = magnitudes.to(device, non_blocking = True) 
             
            predictions = model(waveforms).squeeze(-1) 
            correct += (torch.abs(predictions - magnitudes) <= tolerance).sum().item() 
            total += magnitudes.size(0) 
            mae.update(predictions, magnitudes) 
             
            mse.update(predictions,magnitudes) 
    mse_value = mse.compute().item() 
     
    return mse_value, mae.compute().item(),mse_value ** 0.5, correct / total * 100 
 
def run_experiment(model, train_loader, val_loader, device, num_epochs = 40, lr = 0.001, weight_decay = 1e-4, checkpoint_path = "Baseline_Instance_params1.pth"): 
    model = model.to(device) 
    trainable_params = sum(p.numel()for p in model.parameters()if p.requires_grad) 
 
    print(f"Trainable parameters: {trainable_params:,}") 
 
    optimizer = torch.optim.AdamW(model.parameters(),lr = lr,weight_decay=weight_decay) 
    loss_function = nn.MSELoss() 
 
    best_rmse = float("inf") 
    best_epoch = 0 
 
    for epoch in range (num_epochs): 
        print(f"\nEpoch {epoch + 1}/{num_epochs}") 
        train_mse, train_mae, train_accuracy = train_epoch(model,train_loader,loss_function,optimizer,device) 
 
        val_mse, val_mae, val_rmse, val_accuracy = evaluate_metrics(model,val_loader,device) 
        print( 
            f"Train | " 
            f"MSE: {train_mse:.4f} | " 
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
 
    checkpoint = torch.load( 
        checkpoint_path, 
        map_location=device 
    ) 
 
    model.load_state_dict( 
        checkpoint["model_state_dict"] 
    ) 
 
    print( 
        f"\nLoaded best model from epoch " 
        f"{checkpoint['epoch']}" 
    ) 
 
    return model, checkpoint 

def objective (trial): 
    n_layers = trial.suggest_int("n_layers",2,6) 
    initial_filters = trial.suggest_categorical(
        "initial_filters",
        [16,32,64]
    )
    dropout_rate =0.2
    n_filters = []
    kernel_size = trial.suggest_categorical("kernel_size",[3,5,7])
     
    for i in range(n_layers): 
 
        n_filters.append(min(initial_filters * (2 ** i),256))
 
        

    use_batchnorm = trial.suggest_categorical("use_batchnorm",[True, False]) 
     
    fc_size = trial.suggest_categorical("fc_size",[32,64,128, 256]) 

    print(f"\n{'='*60}") 
    print(f"Trial {trial.number}") 
    print(f"{'='*60}") 
    print(f"Number of layers: {n_layers}") 
    print(f"Filters: {n_filters}") 
    print(f"Kernel sizes: {kernel_size}") 
    print(f"BatchNorm: {use_batchnorm}") 
    print(f"Dropout: {dropout_rate}") 
    print(f"FC size: {fc_size}") 
    print(f"Pooling: MaxPool1d") 
    print(f"{'='*60}") 

    model = FlexibleEarthquakeCNN( 
        n_layers=n_layers, 
        n_filters=n_filters, 
        kernel_size=kernel_size, 
        dropout_rate=dropout_rate, 
        fc_size=fc_size, 
        use_batchnorm=use_batchnorm 
    ).to(device) 

    trainable_params = sum(p.numel()for p in model.parameters()if p.requires_grad) 

    print(f"Trainable parameters: {trainable_params:,}") 

    trial.set_user_attr("trainable_params",trainable_params) 

    optimizer = torch.optim.AdamW( 
        model.parameters(), 
        lr=0.001, 
        weight_decay=1e-4 
    ) 
    loss_function = nn.MSELoss() 
 
    best_rmse = float("inf") 
    best_mse = None 
    best_mae = None 
    best_accuracy = None 
    best_epoch = None 
 
    for epoch in range(10): 
 
        train_epoch(model, 
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
            f"Trial {trial.number} | " 
            f"Epoch {epoch + 1} | " 
            f"Val MSE: {val_mse:.4f} | " 
            f"Val MAE: {val_mae:.4f} | " 
            f"Val RMSE: {val_rmse:.4f} | " 
            f"Accuracy ±0.2: {val_accuracy:.2f}%" 
        ) 
 
        if val_rmse < best_rmse: 
            best_rmse = val_rmse 
            best_mse = val_mse 
            best_mae = val_mae 
            best_accuracy = val_accuracy 
            best_epoch = epoch + 1 

            trial.set_user_attr("best_epoch",best_epoch) 
            trial.set_user_attr("best_val_mse",best_mse) 
            trial.set_user_attr("best_val_mae",best_mae) 
            trial.set_user_attr("best_val_rmse",best_rmse) 
            trial.set_user_attr("best_val_accuracy_0.2",best_accuracy) 
 
        trial.report( 
            val_rmse, 
            epoch 
        ) 
 
        if trial.should_prune(): 
            raise optuna.TrialPruned() 
 
    return best_rmse 
 
 
if __name__ == "__main__": 
    train_loader, val_loader, test_loader = get_data_loaders() 
 
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu") 
    print (f"Using {device}") 

    study = optuna.create_study(
        study_name="earthquake_architecture_search",
        storage="sqlite:///architecture_search.db",
        direction="minimize",
        load_if_exists=True,
        pruner=optuna.pruners.MedianPruner(
            n_startup_trials=5,
            n_warmup_steps=3
        )
    )

    study.optimize(objective,n_trials=1) 
 
    results_df = study.trials_dataframe() 
 
    results_df.to_csv("architecture_search_results.csv",index=False)    

    print("Best RMSE:") 
    print(study.best_value) 
     
    print("Best architecture:") 
    print(study.best_params) 

    print("Best trial data:") 
    print(study.best_trial.user_attrs) 
import torch

try:
    from .instancepipeline import get_data_loaders
except ImportError:
    from instancepipeline import get_data_loaders


train_loader, val_loader, test_loader = get_data_loaders()

# Get one batch
waveforms, magnitudes = next(iter(train_loader))

print("Batch waveform shape:", waveforms.shape)
print("Batch magnitude shape:", magnitudes.shape)

print("Waveform dtype:", waveforms.dtype)
print("Magnitude dtype:", magnitudes.dtype)

print("\nBatch statistics")
print("Min:", waveforms.min().item())
print("Max:", waveforms.max().item())
print("Mean:", waveforms.mean().item())
print("Std:", waveforms.std().item())

# Inspect first sample
x = waveforms[0]
y = magnitudes[0]

print("\nFirst sample")
print("Magnitude:", y.item())
print("Shape:", x.shape)

for channel in range(3):
    print(f"\nChannel {channel}")
    print("Min:", x[channel].min().item())
    print("Max:", x[channel].max().item())
    print("Mean:", x[channel].mean().item())
    print("Std:", x[channel].std().item())

print("\nFirst 20 values of channel 0:")
print(x[0, :20])
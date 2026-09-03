import h5py
from pathlib import Path
import sys
import torch
from torch.utils.data import DataLoader
import pandas as pd
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ARCHITECTURE_DIR = PROJECT_ROOT / "architechturesearch"
if str(ARCHITECTURE_DIR) not in sys.path:
    sys.path.insert(0, str(ARCHITECTURE_DIR))

from fullmodeltrain.instancepipeline import InstanceEarthquakeDataset



train_df = pd.read_csv(PROJECT_ROOT / "train_full_metadata.csv" ,low_memory=False)

val_df = pd.read_csv(PROJECT_ROOT / "val_metadata.csv",low_memory=False)

test_df = pd.read_csv(
    PROJECT_ROOT / "test_metadata.csv",
    low_memory=False
)


SOURCE = "/data/Instance_events_counts.hdf5"
OUTPUT = "/data/Instance_windows_5s.hdf5"



def convert_split(output_file, split_name, dataframe):
    dataset = InstanceEarthquakeDataset(
        dataframe,
        hdf5_path=SOURCE,
        timelength=500,
    )

    # Workers only read the source file. The main process alone writes OUTPUT.
    loader = DataLoader(
        dataset,
        batch_size=512,
        shuffle=False,
        num_workers=4,
        persistent_workers=True,
        prefetch_factor=4,
        pin_memory=False,
    )

    count = len(dataset)

    waveforms = output_file.create_dataset(
        f"{split_name}/waveforms",
        shape=(count, 3, 500),
        dtype="float32",
    )

    targets = output_file.create_dataset(
        f"{split_name}/targets",
        shape=(count,),
        dtype="float32",
    )

    position = 0

    for batch_number, (x, y) in enumerate(
        tqdm(
            loader,
            desc=f"Converting {split_name}",
            unit="batch"
        )
    ):
        batch_size = x.shape[0]
        end = position + batch_size

        waveforms[position:end] = x.numpy()
        targets[position:end] = y.numpy()

        position = end


def main():
    with h5py.File(OUTPUT, "w") as output_file:
        convert_split(output_file, "train", train_df)
        convert_split(output_file, "val", val_df)
        convert_split(output_file, "test", test_df)

    print(f"Created {OUTPUT}")

if __name__ == "__main__":
    main()
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent

from torch.utils.data import Dataset
from torch.utils.data import DataLoader
# acess problems
import os 
import urllib.request
import scipy.io
from PIL import Image
from torchvision import transforms
from torch.utils.data import random_split
import time
from torch.utils.data import Subset
import torch
import pandas as pd

import numpy as np 

import h5py as h5
from sklearn.model_selection import train_test_split



mean = torch.tensor(
    np.load(MODULE_DIR / "train_mean_architecture.npy"),
    dtype=torch.float32
).reshape(3, 1)

std = torch.tensor(
    np.load(MODULE_DIR / "train_std_architecture.npy"),
    dtype=torch.float32
).reshape(3, 1)
class InstanceEarthquakeDataset(Dataset):

    def __init__(self, metadata_df, hdf5_path, timelength, transform = None):
        
        self.hdf5_path = hdf5_path 
        self.transform = transform 
        self.timelength = timelength
        self.trace_names = metadata_df["trace_name"].to_numpy()
        self.p_arrivals = metadata_df["trace_P_arrival_sample"].to_numpy()
        self.magnitudes = metadata_df["source_magnitude"].to_numpy()
        self.h5_file = None
    def __len__(self):
        return len(self.trace_names)
    def __getitem__(self,idx):
        if self.h5_file is None:
            self.h5_file = h5.File(self.hdf5_path, "r")
        
        
        
        trace_name = self.trace_names[idx]
        p_arrival = int(self.p_arrivals[idx])
        magnitude = self.magnitudes[idx]
        waveform = self.h5_file["data"][trace_name]
        waveform_window = waveform[:, p_arrival:p_arrival + self.timelength]
        waveform_window = torch.from_numpy(np.asarray(waveform_window, dtype=np.float32))
        if self.transform:
            waveform_window = self.transform(waveform_window)
        waveform_window = (waveform_window - mean) / (std + 1e-8)
        magnitude = torch.tensor(magnitude, dtype=torch.float32)

        return waveform_window, magnitude

    def __getstate__(self):
        state = self.__dict__.copy()
        state["h5_file"] = None
        return state

class cacheEarthquakeDataset(Dataset):
    def __init__(self, path, split):
        self.path = path
        self.split = split
        self.h5_file = None
        self.waveforms = None
        self.targets = None
    
        with h5.File(path, "r") as file:
            self.length = file[f"{split}/targets"].shape[0]

    def _open(self):
        if self.h5_file is None:
            self.h5_file = h5.File(self.path, "r")
            self.waveforms = self.h5_file[
                f"{self.split}/waveforms"
            ]
            self.targets = self.h5_file[
                f"{self.split}/targets"
            ]

    def __len__(self):
        return self.length

    def __getitem__(self, index):
        self._open()

        waveform = torch.from_numpy(self.waveforms[index])
        target = torch.tensor(
            self.targets[index],
            dtype=torch.float32,
        )

        return waveform, target

    def __getstate__(self):
        state = self.__dict__.copy()
        state["h5_file"] = None
        state["waveforms"] = None
        state["targets"] = None
        return state

def get_data_loaders ():
    

    train_dataset = cacheEarthquakeDataset("/data/Instance_windows.hdf5","train",)

    val_dataset = cacheEarthquakeDataset("/data/Instance_windows.hdf5","val",)

    test_dataset = cacheEarthquakeDataset("/data/Instance_windows.hdf5","test")
    
    train_loader = DataLoader(
    train_dataset,
    batch_size=128,
    shuffle=True,
    num_workers=4,
    pin_memory=torch.cuda.is_available(),
    persistent_workers=True,
    prefetch_factor=4
)
    val_loader = DataLoader(
        val_dataset,
        batch_size=128,
        shuffle=False,
        num_workers=4,
        pin_memory=torch.cuda.is_available(),
        persistent_workers=True,
        prefetch_factor=4
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=128,
        shuffle=False,
        num_workers=4,
        pin_memory=torch.cuda.is_available(),
        persistent_workers=False,
        prefetch_factor=4
    )

    return train_loader, val_loader, test_loader




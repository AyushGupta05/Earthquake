import pandas as pd
import h5py as h5
import numpy as np

train_ids = pd.read_csv("train_full_metadata.csv")

train_optimize_architecture = pd.read_csv("train_architecture_data.csv")

train_optimize_hyperparams = pd.read_csv("train_hyperparams_metadata.csv")

waveforms = h5.File(
    "/data/Instance_events_counts.hdf5",
    "r"
)

architecture_traces = set(train_optimize_architecture["trace_name"])

hyperparam_traces = set(train_optimize_hyperparams["trace_name"])

channel_sum_full = np.zeros(3, dtype=np.float64)

channel_sqsum_full = np.zeros(3, dtype=np.float64)

channel_sum_architecture = np.zeros(3, dtype=np.float64)

channel_sqsum_architecture = np.zeros(3, dtype=np.float64)

channel_sum_hyperparams = np.zeros(3, dtype=np.float64)

channel_sqsum_hyperparams = np.zeros(3, dtype=np.float64)

countfull = 0

countarchitecture = 0

counthyperparams = 0

time = 300

for row in train_ids.itertuples():

    trace_name = row.trace_name

    p_arrival = int(row.trace_P_arrival_sample)

    waveform_time = waveforms["data"][trace_name][
        :, p_arrival:p_arrival + time
    ].astype(np.float64)

    if waveform_time.shape[1] != time:

        continue

    channel_sum = waveform_time.sum(axis=1)

    channel_sqsum = np.square(waveform_time).sum(axis=1)

    channel_sum_full += channel_sum

    channel_sqsum_full += channel_sqsum

    countfull += time

    if trace_name in architecture_traces:

        channel_sum_architecture += channel_sum

        channel_sqsum_architecture += channel_sqsum

        countarchitecture += time

    if trace_name in hyperparam_traces:

        channel_sum_hyperparams += channel_sum

        channel_sqsum_hyperparams += channel_sqsum

        counthyperparams += time


meanfull = channel_sum_full / countfull

stdfull = np.sqrt(
    channel_sqsum_full / countfull
    - meanfull ** 2
)

meanarchitecture = (
    channel_sum_architecture / countarchitecture
)

stdarchitecture = np.sqrt(
    channel_sqsum_architecture / countarchitecture
    - meanarchitecture ** 2
)

meanhyperparams = (
    channel_sum_hyperparams / counthyperparams
)

stdhyperparams = np.sqrt(
    channel_sqsum_hyperparams / counthyperparams
    - meanhyperparams ** 2
)

print("Full mean:", meanfull)

print("Full std:", stdfull)

print("Architecture mean:", meanarchitecture)

print("Architecture std:", stdarchitecture)

print("Hyperparameter mean:", meanhyperparams)

print("Hyperparameter std:", stdhyperparams)

np.save("train_mean_full.npy", meanfull)

np.save("train_std_full.npy", stdfull)

np.save("train_mean_architecture.npy", meanarchitecture)

np.save("train_std_architecture.npy", stdarchitecture)

np.save("train_mean_hyperparams.npy", meanhyperparams)

np.save("train_std_hyperparams.npy", stdhyperparams)

waveforms.close()
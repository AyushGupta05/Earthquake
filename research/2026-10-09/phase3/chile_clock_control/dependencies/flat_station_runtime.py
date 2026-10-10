"""Explicit station-only backend installation for an audited future launcher.

The original trainer source is unchanged. Its StationDataset fingerprint changes
honestly, and its runtime identity additionally binds this entire adapter module.
"""
from contextlib import contextmanager
import copy
import os
from pathlib import Path

import numpy as np
import torch

from flat_station_cache import FlatStationCache, file_sha256
from training_artifacts import json_sha256, station_membership

BACKEND_SCHEMA = 'team-flat-station-runtime-v1'
_ACTIVE = None


def strict_runtime():
    """Additional deterministic execution flags missing from old trainer config."""
    return {'cublas_workspace_config': os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
            'deterministic_algorithms': torch.are_deterministic_algorithms_enabled(),
            'deterministic_warn_only': torch.is_deterministic_algorithms_warn_only_enabled(),
            'cudnn_deterministic': torch.backends.cudnn.deterministic,
            'cudnn_benchmark': torch.backends.cudnn.benchmark,
            'cuda_matmul_allow_tf32': torch.backends.cuda.matmul.allow_tf32,
            'cudnn_allow_tf32': torch.backends.cudnn.allow_tf32,
            'float32_matmul_precision': torch.get_float32_matmul_precision()}


def backend_identity(flat, launcher_sha256):
    return {'schema': BACKEND_SCHEMA, 'scope': 'station_pretraining_and_train_calibration_only',
            'flat_directory': str(flat.directory.resolve()),
            'flat_manifest_sha256': flat.expected_manifest_sha256,
            'source_identity': copy.deepcopy(flat.manifest['source_identity']),
            'adapter_sha256': file_sha256(__file__),
            'flat_module_sha256': file_sha256(Path(__file__).with_name('flat_station_cache.py')),
            'launcher_sha256': launcher_sha256,
            'integration_sources_sha256': {name: file_sha256(Path(__file__).with_name(name)) for name in
                ('run_team_flat.py', 'flat_station_migration.py', 'flat_station_proof.py')},
            'numpy_version': np.__version__,
            'copy_policy': 'owned_float32_array_before_torch_from_numpy',
            'workers': 0, 'strict_runtime': strict_runtime()}


class FlatStationDataset(torch.utils.data.Dataset):
    """Same station order/labels as StationDataset, backed by owned map copies."""
    def __init__(self, events, *, calibration=False):
        if _ACTIVE is None:
            raise RuntimeError('Flat dataset requires the explicit audited runtime context')
        if (not (events.frame.benchmark_split == 'train').all()
                or events.training == calibration):
            raise ValueError('Station fitting/calibration must use its matching TRAIN-only partition')
        flat, source_path = _ACTIVE
        if Path(events.cache).resolve() != source_path or events.stored_samples != flat.manifest['source_identity']['stored_samples']:
            raise ValueError('Flat dataset is not bound to this event cache/timing')
        membership = station_membership(events)
        self.events = events
        self.subset = flat.subset(events.frame.EVENT.astype(str).tolist(),
                                 expected_membership_sha256=membership['ordered_membership_sha256'])
        expected_rows = [event['source_row_index'] for event in self.subset.events]
        expected_labels = np.asarray([event['magnitude'] for event in self.subset.events], dtype=np.float64)
        if (expected_rows != events.frame.source_row_index.tolist()
                or not np.array_equal(expected_labels, events.frame.MA.to_numpy(dtype=np.float64))):
            raise ValueError('Flat labels or source rows differ from authoritative event metadata')
        if len(self.subset) != membership['records']:
            raise ValueError('Flat station count differs from the authoritative station membership')
        self.ends = self.subset.ends.copy()

    def __len__(self):
        return len(self.subset)

    def __getitem__(self, index):
        value, magnitude = self.subset[index]
        # Torch tensors do not enforce NumPy's readonly flag. Own the storage
        # before handing it to training/collation, matching HDF-owned reads.
        return torch.from_numpy(value.copy(order='C')), magnitude


@contextmanager
def install_flat_backend(trainer, flat, source_path, *, identity, lineage):
    """Temporarily install only the station reader and recorded runtime wrapper."""
    global _ACTIVE
    if _ACTIVE is not None or trainer.StationDataset is FlatStationDataset:
        raise RuntimeError('A flat backend is already installed')
    original_dataset, original_runtime = trainer.StationDataset, trainer.runtime_identity
    original_fingerprint = trainer.pretraining_implementation_sha256
    _ACTIVE = (flat, Path(source_path).resolve())
    recorded = {**copy.deepcopy(identity), 'lineage': copy.deepcopy(lineage)}
    def runtime(device):
        return {**original_runtime(device), 'station_backend': copy.deepcopy(recorded)}
    def fingerprint():
        return json_sha256({'station_components_sha256': original_fingerprint(),
                            'adapter_sha256': identity['adapter_sha256'],
                            'flat_module_sha256': identity['flat_module_sha256']})
    trainer.StationDataset, trainer.runtime_identity = FlatStationDataset, runtime
    trainer.pretraining_implementation_sha256 = fingerprint
    try:
        yield
    finally:
        trainer.StationDataset, trainer.runtime_identity = original_dataset, original_runtime
        trainer.pretraining_implementation_sha256 = original_fingerprint
        _ACTIVE = None

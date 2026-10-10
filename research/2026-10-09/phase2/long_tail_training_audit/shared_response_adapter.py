"""Bind an already-open shared export to the frozen B exposure comparison.

No paths to datasets, discovery, waveform export or fitting are provided here.
The response owner supplies the reviewed dataset/model/digest implementations.
All provenance checks precede the first requested waveform batch.
"""
from dataclasses import dataclass
import hashlib
import inspect
from pathlib import Path

import numpy as np
import torch

from exposure_training import (HORIZONS, LoadedPrefix, PrefixPopulation, digest_json,
                               make_plan, population_digest)


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class SharedBinding:
    plans: dict
    loader: object
    model_factory: object
    identity: dict
    validate_population: object


def bind_shared_response(dataset, normalizers, provenance, model_class, fitting_digest):
    """Validate the shared normalizer provenance, then expose the agreed callbacks.

    fitting_digest is the shared metadata-only source-row/event/trace/weight
    digest function. Its source hash must match the function that fitted the
    normalizers. The additional exposure digest also binds targets and canonical
    station groups; copying a digest string cannot substitute for these checks.
    """
    m = dataset.metadata
    required = {"source_row_index", "trace_name", "source_id", "station_group", "subset",
                "sampling_weight", "valid", "targets"}
    if not required <= set(m):
        raise ValueError("Incomplete shared-export identity schema")
    n = len(m["source_row_index"])
    rows = np.asarray(m["source_row_index"])
    if rows.shape != (n,) or rows.dtype.kind not in "iu" or len(np.unique(rows)) != n:
        raise ValueError("Shared source rows must be unique integer identities")
    for key in ("trace_name", "source_id", "station_group", "subset", "sampling_weight"):
        if np.asarray(m[key]).shape != (n,):
            raise ValueError("Shared metadata does not align with source rows")
    valid = np.asarray(m["valid"])
    targets = np.asarray(m["targets"])
    if valid.shape != (n, 3) or valid.dtype != np.bool_ or targets.shape != (n,):
        raise ValueError("Require per-deadline masks and scalar magnitude target schema")
    if not np.isin(m["subset"], ["fit", "eval_seen", "eval_held"]).all():
        raise ValueError("Unknown shared population role")
    manifest_sha = file_sha(Path(dataset.path) / "manifest.json")
    if provenance.get("export_manifest_sha256") != manifest_sha:
        raise ValueError("Normalizers belong to another immutable export")
    if provenance.get("labels_used") is not False or provenance.get("held_rows_used") is not False:
        raise ValueError("Normalization must exclude held rows and all labels")
    normalizer_source = inspect.getsourcefile(fitting_digest)
    if normalizer_source is None or provenance.get("normalizer_source_sha256") != file_sha(normalizer_source):
        raise ValueError("Shared normalizer implementation identity changed")
    if provenance.get("metadata_fit_population") != fitting_digest(m):
        raise ValueError("Metadata normalizers used different fitting identities/weights")
    expected = {str(t): fitting_digest(m, t) for t in HORIZONS}
    if provenance.get("per_deadline_fit_population") != expected:
        raise ValueError("Amplitude normalizers used different deadline-specific fitting populations")
    arrays = {k: np.asarray(v, dtype="<f4").copy() for k, v in normalizers.items()}
    hashes = {k: hashlib.sha256(v.tobytes()).hexdigest() for k, v in arrays.items()}
    if provenance.get("arrays_sha256") != hashes or not all(np.isfinite(v).all() for v in arrays.values()):
        raise ValueError("Normalizer arrays differ from their provenance")
    if any((v <= 0).any() for k, v in arrays.items() if k.endswith("_std")):
        raise ValueError("Normalizer scales must be positive")
    for a in arrays.values():
        a.setflags(write=False)
    plans = {}
    for j, t in enumerate(HORIZONS):
        ix = np.flatnonzero((m["subset"] == "fit") & valid[:, j])
        plans[t] = make_plan(PrefixPopulation(t, "fit", rows[ix], m["source_id"][ix],
            m["station_group"][ix], targets[ix], m["sampling_weight"][ix]))
    exposure_digest = population_digest(plans)
    model_source = inspect.getsourcefile(model_class)
    if model_source is None:
        raise ValueError("Backbone source must be inspectable and pinned")
    identity = {"export_sha256": manifest_sha, "backbone_sha256": file_sha(model_source),
                "normalizers_sha256": digest_json(provenance), "population_sha256": exposure_digest,
                "normalizer_fit_population_sha256": exposure_digest,
                "normalizer_provenance": provenance, "architecture": "B-native-late",
                "adapter_sha256": file_sha(__file__), "expected_parameters": 380706}
    row_map = {int(row): i for i, row in enumerate(rows)}

    def loader(seconds, source_rows):
        try:
            ix = np.array([row_map[int(row)] for row in source_rows], dtype=np.int64)
        except KeyError as error:
            raise ValueError("Requested row is absent from the shared export") from error
        if not np.array_equal(np.asarray(m["source_row_index"])[ix], source_rows):
            raise ValueError("Shared source order changed after binding")
        batch = dataset.inference_batch(ix, seconds)
        return LoadedPrefix(np.asarray(m["source_row_index"])[ix].copy(),
                            {k: torch.from_numpy(np.array(v, copy=True)) for k, v in batch.items()})

    def model_factory():
        # Copy immutable fit statistics into each independent, identical factory
        # invocation; architecture and objective may not change together.
        model = model_class("B", {k: v.copy() for k, v in arrays.items()})
        if sum(p.numel() for p in model.parameters()) != 380706:
            raise ValueError("Shared B capacity changed from the frozen protocol")
        return model

    def validate_population(population):
        # Bind the complete held panel, including labels and weights, to the same
        # export rows that the loader will read. A caller cannot substitute fit
        # waveform IDs or silently select an easier held subset.
        if population.seconds not in HORIZONS or population.subset not in ("eval_seen", "eval_held"):
            raise ValueError("Expected a frozen held evaluation panel")
        j = HORIZONS.index(population.seconds)
        ix = np.flatnonzero((m["subset"] == population.subset) & valid[:, j])
        expected = PrefixPopulation(population.seconds, population.subset, rows[ix],
            m["source_id"][ix], m["station_group"][ix], targets[ix], m["sampling_weight"][ix])
        if population.identity() != expected.identity():
            raise ValueError("Held panel does not match the bound export identities/targets/weights/mask")

    return SharedBinding(plans, loader, model_factory, identity, validate_population)

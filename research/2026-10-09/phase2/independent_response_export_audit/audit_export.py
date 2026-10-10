"""Independent metadata audit. Never opens counts.npy or loads features.npy.

Archive files may be byte-hashed, but only an explicit allowlist of metadata
members is decoded. Saved response evaluations are checked; evalresp, waveform
decoding, fitting and GPU libraries are not invoked.
"""
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import time

import numpy as np

ROOT = Path("/mnt/eew-research/runs/response_prefix_export_v1")
POLAR = Path("/mnt/eew-research/runs/polarization_preflight_v2")
AUDIT = Path("/home/ec2-user/response_export_a338babb/work/response_conditioned_encoder/full_response_audit_v3")
# The large saved join is a separately transferred audit input, never source code.
JOIN_CSV = Path("/home/ec2-user/response_export_audit_inputs_v3/train_response_join.csv.gz")
EXPORT_SHA = "55ba19f81f59c106964ae92302258aba7780d5bc1a48cd3ec20617c8f2ba2a46"
METADATA_SHA = "ff2b58263066f3cd47020960db008297346945a70e39999cd508add90967faaf"
COUNTS_SHA = "6732ecbec94ee5bfe40788a84a13d4de1b11b6bc64bfd9aef887c0946c9e3b0c"
JOIN_SHA = "d65966518a3ec62e022351c6fc6be91e5003c20a916cf5640b8aaba8f59d8ab2"
IDENTITIES = ("source_row_index", "trace_name", "source_id", "station_id", "station_group",
              "subset", "sampling_weight", "valid", "invalid_codes", "deadlines", "event_bucket",
              "station_bucket", "n_metadata_eligible", "n_sampled")
META_KEYS = (*IDENTITIES, "targets", "sensitivity", "static", "response", "native_units", "response_epoch_ids")
POLAR_KEYS = (*IDENTITIES, "targets", "sensitivities", "native_units", "station_channels", "target_names")
FREQUENCIES = np.array([.5, 1., 2., 4., 8., 16.])
FAMILIES = ("HH", "EH", "HN", "HL", "EN")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_json(path, expected):
    require(sha(path) == expected, "Hash mismatch: " + str(path))
    return json.loads(Path(path).read_text())


def load_metadata(path, keys):
    require("features" not in keys and "counts" not in keys, "Waveform/feature member forbidden")
    with np.load(path, allow_pickle=False) as archive:
        require(set(keys) <= set(archive.files), "Required metadata member missing")
        return {key: archive[key] for key in keys}


def unit(value):
    value = (value or "").upper().replace(" ", "")
    return "m/s" if value == "M/S" else "m/s^2" if value in ("M/S**2", "M/S^2", "M/S/S") else "unknown"


def number(value):
    try:
        parsed = float(value)
    except (ValueError, TypeError):
        return None
    return parsed if math.isfinite(parsed) else None


def timestamp(value):
    normalized = value.strip().replace("Z", "+00:00")
    # Python3.9 accepts only selected fractional widths. Match the source clock's
    # explicit microsecond precision while preserving shorter fractions exactly.
    normalized = re.sub(r"\.(\d+)(?=[+-]|$)",
                        lambda m: "." + m.group(1).ljust(6, "0")[:6], normalized)
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def bucket(salt, identifier):
    return int.from_bytes(hashlib.sha256((salt + "\0" + str(identifier)).encode()).digest()[:8], "big") % 10


def reconstructed_descriptor(epoch, evaluation):
    """Independently rebuild the published validity mask and zero fallback."""
    result = np.zeros((6, 4), dtype=np.float64)
    rate = number(epoch.get("sample_rate_hz"))
    if not evaluation.get("valid_response") or rate is None or rate <= 0:
        return result
    final_rate = evaluation.get("final_stage_output_rate")
    if final_rate is not None and not math.isclose(final_rate, rate, rel_tol=1e-8, abs_tol=1e-6):
        return result
    finite = np.asarray(evaluation["frequency_finite_nonzero"])
    require(finite.shape == (6,) and finite.dtype == np.bool_, "Bad stored frequency-validity schema")
    values = np.asarray(evaluation["descriptor_unmasked"], dtype=np.float64)
    require(values.shape == (6, 3), "Bad unmasked response schema")
    mask = (FREQUENCIES < .4 * rate) & finite
    require(np.isfinite(values[mask]).all(), "Valid stored response is nonfinite")
    result[mask, :3] = values[mask]
    result[:, 3] = mask
    return result


def epoch_static(epoch):
    gain = epoch["sensitivity"]
    require(number(gain) is not None and gain > 0, "Selected epoch has invalid scalar gain")
    native = unit(epoch.get("input_units"))
    require(native in ("m/s", "m/s^2"), "Selected epoch has unknown native unit")
    fields = [0., math.log10(gain), float(native == "m/s"), float(native == "m/s^2")]
    for key in ("sensitivity_frequency_hz", "sample_rate_hz"):
        value = number(epoch.get(key))
        valid = value is not None and value >= 0
        fields.extend([math.log1p(value) if valid else 0., float(not valid)])
    return fields


def check_arrays(m, p):
    n = len(m["source_row_index"])
    for key in IDENTITIES:
        require(np.array_equal(m[key], p[key]), "Authoritative metadata mismatch: " + key)
    require(np.array_equal(p["target_names"], ["source_magnitude", "path_hyp_distance_km", "source_depth_km"]), "Target column identity changed")
    require(p["targets"].shape == (n, 3) and m["targets"].shape == (n,), "Wrong target shape")
    require(np.array_equal(m["targets"], p["targets"][:, 0]), "Magnitude target mismatch")
    require(np.array_equal(m["sensitivity"], p["sensitivities"]), "Scalar gains differ from population")
    require(np.array_equal(m["native_units"], p["native_units"]), "Native units differ from population")
    require(m["valid"].dtype == np.bool_ and m["valid"].shape == (n, 3), "Wrong validity shape/dtype")
    require(np.array_equal(m["valid"], m["invalid_codes"] == 0), "Validity/reason disagreement")
    require(np.array_equal(m["deadlines"], [1, 3, 5]), "Deadline order changed")
    require(len(np.unique(m["source_row_index"])) == n and len(np.unique(m["trace_name"])) == n, "Duplicate source identity")
    require(np.isfinite(m["targets"]).all(), "Nonfinite magnitude")
    require(np.isfinite(m["sampling_weight"]).all() and (m["sampling_weight"] > 0).all(), "Invalid restoration weights")
    require((m["n_sampled"] > 0).all() and (m["n_metadata_eligible"] >= m["n_sampled"]).all(), "Invalid sampling denominators")
    require(np.array_equal(m["sampling_weight"], m["n_metadata_eligible"] / m["n_sampled"]), "Restoration ratio changed")
    for key, salt in (("event_bucket", "polarization-event-v1"), ("station_bucket", "polarization-station-v1")):
        identity = m["source_id"] if key == "event_bucket" else m["station_group"]
        expected = np.array([bucket(salt, value) for value in identity])
        require(np.array_equal(m[key], expected), "Canonical hash partition disagreement: " + key)
    e, s = m["event_bucket"] < 2, m["station_bucket"] < 2
    expected = np.where(e, np.where(s, "eval_held", "eval_seen"), np.where(s, "excluded", "fit"))
    require(np.array_equal(m["subset"], expected), "Export includes wrong partition")
    require(m["static"].shape == (n, 34) and m["response"].shape == (n, 72), "Static/response dimensions")
    require(m["sensitivity"].shape == (n, 3) and m["response_epoch_ids"].shape == (n, 3), "Gain/epoch dimensions")
    require(np.isfinite(m["static"]).all() and np.isfinite(m["response"]).all(), "Nonfinite model metadata")
    return n


def check_descriptors(m, epochs, evaluations):
    by_id = {r["epoch_id"]: r for r in epochs}
    require(len(by_id) == len(epochs), "Duplicate epoch IDs")
    for epoch in epochs:
        response = reconstructed_descriptor(epoch, evaluations[epoch["response_id"]])
        require(np.array_equal(np.asarray(epoch["descriptor"]), response), "Stored epoch response disagrees with corrected evaluation/mask")
    ids, inverse = np.unique(m["response_epoch_ids"], return_inverse=True)
    records = [by_id[str(i)] for i in ids]
    lut = np.array([r["descriptor"] for r in records])
    expected = lut[inverse].reshape(m["response"].shape)
    require(np.array_equal(expected, m["response"]), "Export descriptor differs from corrected v3 epoch")
    gains = np.array([r["sensitivity"] for r in records])[inverse].reshape(-1, 3)
    units = np.array([unit(r["input_units"]) for r in records])[inverse].reshape(-1, 3)
    require(np.array_equal(gains, m["sensitivity"]), "Export gain differs from selected response epoch")
    require(np.array_equal(units, np.repeat(m["native_units"][:, None], 3, axis=1)), "Component/epoch units differ")
    static = np.array([epoch_static(r) for r in records])[inverse].reshape(-1, 24)
    require(np.array_equal(static, m["static"][:, 10:]), "Response/gain/unit static metadata differs")
    response = m["response"].reshape(-1, 3, 6, 4)
    mask = response[..., 3]
    require(np.isin(mask, [0, 1]).all(), "Nonbinary response masks")
    require((response[..., :3][mask == 0] == 0).all(), "Invalid response is not exact zero fallback")
    valid = mask == 1
    phase_error = np.abs((response[..., 1] ** 2 + response[..., 2] ** 2)[valid] - 1)
    require(not len(phase_error) or phase_error.max() < 1e-12, "Valid phase is not on unit circle")
    return by_id, {"audited_epochs_reconstructed": len(epochs), "selected_unique_epochs": len(ids),
        "valid_component_frequencies": int(valid.sum()), "masked_component_frequencies": int((~valid).sum()),
        "all18_valid_records": int(valid.all(axis=(1, 2)).sum()),
        "no_valid_frequency_records": int((~valid).all(axis=(1, 2)).sum()),
        "phase_norm_max_abs_error": float(phase_error.max()) if len(phase_error) else 0.}


def check_selected_rows(m, p, epochs_by_id, rows):
    """Compare ordered selected CSV and reconstruct all ten nonresponse fields."""
    n = len(m["targets"])
    seen = 0
    for i, row in enumerate(rows):
        require(i < n, "Extra selected metadata row")
        require(int(row["source_row_index"]) == m["source_row_index"][i], "Selected row order changed")
        require(row["trace_name"] == m["trace_name"][i] and row["source_id"] == m["source_id"][i], "Selected trace/event mismatch")
        family = row["station_channels"].strip()
        require(family == p["station_channels"][i], "Selected channel family changed")
        header = [float(family == f) for f in FAMILIES] + [float(family not in FAMILIES)]
        for key in ("station_elevation_m", "station_vs_30_mps"):
            value = number(row.get(key))
            if key == "station_vs_30_mps" and value is not None and value <= 0:
                value = None
            header.extend([0. if value is None else value, float(value is None)])
        require(np.array_equal(m["static"][i, :10], header), "Family/elevation/vs30 static mismatch")
        network, station, location, trace_family = row["trace_name"].rsplit(".", 4)[1:]
        require(trace_family == family, "Trace/family identity changed")
        pick = float(row["trace_P_arrival_sample"])
        begin = timestamp(row["trace_start_time"]) + (pick - 200) * .01
        end = timestamp(row["trace_start_time"]) + (pick + 500) * .01
        for component, epoch_id in zip("ENZ", m["response_epoch_ids"][i]):
            epoch = epochs_by_id[str(epoch_id)]
            require((epoch["network"], epoch["station"], epoch["location"], epoch["channel"]) ==
                    (network, station, location, family + component), "Selected epoch SCNL mismatch")
            require((epoch["start"] is None or epoch["start"] <= begin) and
                    (epoch["end"] is None or epoch["end"] >= end), "Selected epoch does not cover complete7second window")
        seen += 1
    require(seen == n, "Missing selected metadata rows")
    return seen


def check_join_rows(m, rows):
    positions = {int(row): i for i, row in enumerate(m["source_row_index"])}
    seen = set()
    total = 0
    for row in rows:
        total += 1
        source = int(row["source_row_index"])
        if source not in positions:
            continue
        require(source not in seen, "Repeated selected identity in v3 join")
        seen.add(source); i = positions[source]
        require(row["trace_name"] == m["trace_name"][i] and row["source_id"] == m["source_id"][i], "v3 join identity mismatch")
        # The saved join CSV writes boolean metadata as integer 0/1, not bool repr.
        require(row["metadata_eligible"] == "1", "Selected row is ineligible in corrected v3 audit")
        for component, epoch in zip("ENZ", m["response_epoch_ids"][i]):
            require(row[component + "_status"] == "matched" and row[component + "_epoch_id"] == epoch,
                    "Export did not use the corrected v3 response join")
    require(len(seen) == len(positions), "Selected records missing from corrected v3 join")
    return {"existing_v3_join_rows_scanned": total, "selected_rows_matched": len(seen)}


def main():
    start = time.monotonic()
    manifest = checked_json(ROOT / "manifest.json", EXPORT_SHA)
    complete = json.loads((ROOT / "COMPLETE.json").read_text())
    require(complete["manifest_sha256"] == EXPORT_SHA and manifest["status"] == "complete", "Export incomplete")
    require(manifest["outputs_sha256"] == {"counts.npy": COUNTS_SHA, "metadata.npz": METADATA_SHA}, "Export pins differ from authorized artifact")
    require(manifest["response_join_audit_sha256"] == JOIN_SHA, "Export uses old response audit")
    polar = checked_json(POLAR / "manifest.json", manifest["polarization_manifest_sha256"])
    join = checked_json(AUDIT / "train_join_audit.json", JOIN_SHA)
    require(polar["status"] == "complete" and polar["scope"].startswith("TRAIN only"), "Wrong authoritative scope/status")
    files = {ROOT / "metadata.npz": METADATA_SHA,
        POLAR / "features.npz": polar["outputs_sha256"]["features.npz"],
        POLAR / "selected_metadata.csv": polar["outputs_sha256"]["selected_metadata.csv"],
        AUDIT / "channel_epochs.json": join["audited_epochs_sha256"],
        AUDIT / "response_evaluations.json": join["evaluated_responses_sha256"],
        JOIN_CSV: join["artifacts"]["join_sha256"]}
    for path, expected in files.items():
        require(sha(path) == expected, "Artifact bytes changed: " + str(path))
    m = load_metadata(ROOT / "metadata.npz", META_KEYS)
    p = load_metadata(POLAR / "features.npz", POLAR_KEYS)
    require(check_arrays(m, p) == manifest["rows"] == 112660, "Wrong completed population size")
    epochs = json.loads((AUDIT / "channel_epochs.json").read_text())
    evaluations = json.loads((AUDIT / "response_evaluations.json").read_text())
    by_id, response = check_descriptors(m, epochs, evaluations)
    with (POLAR / "selected_metadata.csv").open() as stream:
        selected = check_selected_rows(m, p, by_id, csv.DictReader(stream))
    with gzip.open(JOIN_CSV, "rt") as stream:
        joined = check_join_rows(m, csv.DictReader(stream))
    require(joined["existing_v3_join_rows_scanned"] == 979487, "Wrong existing TRAIN join row count")
    panels = []
    for subset in ("fit", "eval_seen", "eval_held"):
        selection = m["subset"] == subset
        panels.append({"subset": subset, "sampled_records": int(selection.sum()),
            "sampled_events": len(np.unique(m["source_id"][selection])),
            "valid_records_1_3_5": m["valid"][selection].sum(0).tolist()})
    print(json.dumps({"status": "pass", "seconds": time.monotonic() - start, "rows": selected,
        "python": platform.python_version(), "numpy": np.__version__, "scope": "TRAIN metadata only",
        "export_manifest_sha256": EXPORT_SHA, "polarization_manifest_sha256": manifest["polarization_manifest_sha256"],
        "response_join_audit_sha256": JOIN_SHA, "verified_artifact_sha256": {str(k): v for k, v in files.items()},
        "identity_arrays_exact": list(IDENTITIES), "targets_gains_units_exact": True,
        "static_columns_exact": 34, "response_columns_exact": 72, "response": response,
        "join": joined, "panels": panels,
        "counts_blob": {"declared_sha256_matches_parent": COUNTS_SHA, "opened_by_this_audit": False},
        "decoded_polarization_members": list(POLAR_KEYS), "features_matrix_decoded": False,
        "limitations": ["No waveform contents or causal preprocessing re-audit", "No response evalresp recomputation; checked saved corrected evaluations and masks", "No fits, models, GPU, DEV or TEST", "Source raw HDF remains stat-identified as declared by export"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

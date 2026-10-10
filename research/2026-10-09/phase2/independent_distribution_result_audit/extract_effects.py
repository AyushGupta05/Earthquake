"""Compact extraction from a report already accepted by the independent auditor.

No rescoring, refitting, threshold changes or point-action selection. Hashes bind
the report to the exact audited completed grid. Gate truth comes from the audit
receipt, not a fresh decision based on rounded/extracted report values.
"""
import argparse
import hashlib
import json
from pathlib import Path


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def checked_json(path, expected):
    # Parse the same immutable in-memory snapshot that passed authentication.
    # The 12GiB bounded extraction job accommodates the largest saved report.
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, "Authenticated JSON changed: " + str(path))
    return json.loads(raw)


def point_fields(metric):
    return {"weighted_mae": metric["weighted_mae"], "medae": metric["medae"], "cvar95": metric["cvar95"],
            "m4_weighted_mae": metric["tail"]["4"].get("weighted_mae"),
            "m4_event_macro_mae": metric["tail"]["4"].get("event_macro_mae"),
            "m4_events": metric["tail"]["4"]["events"]}


def compact(report, receipt, kind):
    require(kind in ("response", "exposure") and receipt["kind"] == kind and receipt["status"] == "pass", "Passing matching audit required")
    index = {}
    for row in report["scores"]:
        control = row["arm"] if kind == "response" else row["control"]
        seed = row["seed"] if kind == "response" else row["seed_or_ensemble"]
        if seed == "equal_pmf_ensemble": seed = "ensemble"
        key = (control, seed, row["seconds"], row["subset"])
        require(key not in index, "Duplicate score identity")
        index[key] = row["metrics"]
    candidate = "C" if kind == "response" else "band_exposure_ce"
    cases = []
    for comparison in report["comparisons"]:
        reference = "B" if kind == "response" else comparison["reference_control"]
        t, subset = comparison["seconds"], comparison["subset"]
        actions = []
        for seed in ("20261009", "20261010", "ensemble"):
            for action in ("mean", "median"):
                c = point_fields(index[(candidate, seed, t, subset)][action])
                r = point_fields(index[(reference, seed, t, subset)][action])
                delta = {key: c[key] - r[key] if c[key] is not None and r[key] is not None else None for key in c if key != "m4_events"}
                actions.append({"seed_or_ensemble": seed, "action": action,
                                "candidate": c, "reference": r, "candidate_minus_reference": delta})
        matching_gate = [row for row in receipt["gate"]["checks"] if row["seconds"] == t and row["subset"] == subset and (kind == "response" or row["reference_control"] == reference)]
        require(len(matching_gate) == 1, "Ambiguous independent gate panel")
        cases.append({"seconds": t, "subset": subset, "candidate": candidate, "reference": reference,
                      "valid_fraction": comparison["valid_fraction"], "mean_ensemble_bootstrap": comparison["bootstrap"],
                      "independent_gate_check": matching_gate[0], "decisions": actions})
    require(len(cases) == (6 if kind == "response" else 12), "Incomplete fixed comparisons")
    return {"kind": kind, "status": "extracted_from_independently_verified_report", "gate": receipt["gate"],
            "primary_action": "PMF mean", "median_action": "Preserved secondary action; no action selection",
            "point_support": receipt["point_support"], "cases": cases,
            "note": "Values extracted at full precision from hash-verified report. Gate result is the independent replay; no thresholds recomputed here."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=("response", "exposure"), required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--receipt", type=Path, required=True)
    p.add_argument("--receipt-sha256", required=True)
    a = p.parse_args(argv)
    receipt = checked_json(a.receipt, a.receipt_sha256)
    filename, key = ("grid_manifest.json", "grid_manifest_sha256") if a.kind == "response" else ("manifest.json", "manifest_sha256")
    manifest = checked_json(a.root / filename, receipt["grid_manifest_sha256"])
    completion = json.loads((a.root / "COMPLETE.json").read_text())
    # The producer's completion contract is a pointer to the final manifest,
    # not a separately authenticated document. The audit pins that manifest
    # and its report bytes; harmless marker whitespace/extra fields are not
    # scientific inputs. Do not invent a COMPLETE byte digest absent upstream.
    require(manifest["status"] == "complete" and completion[key] == receipt["grid_manifest_sha256"], "Grid not complete")
    expected = manifest["report_sha256"] if a.kind == "response" else manifest["outputs_sha256"]["report.json"]
    report = checked_json(a.root / "report.json", expected)
    out = compact(report, receipt, a.kind)
    out.update(report_sha256=expected, audit_receipt_sha256=a.receipt_sha256,
               grid_manifest_sha256=receipt["grid_manifest_sha256"], extractor_sha256=file_sha(__file__))
    print(json.dumps(out, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

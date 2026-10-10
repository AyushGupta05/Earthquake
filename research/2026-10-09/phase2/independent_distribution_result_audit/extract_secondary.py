"""Extract only the pre-specified exploratory response B-A and D-A effects.

Uses existing independently audited report metrics and receipt worst-error
metrics. No prediction scoring, new confidence intervals, gates, or selection.
"""
import argparse
import json
import math
from pathlib import Path

from extract_effects import checked_json, file_sha, point_fields, require

SEEDS = ("20261009", "20261010", "ensemble")
PANELS = tuple((t, s) for t in (1, 3, 5) for s in ("eval_seen", "eval_held"))


def compact_secondary(report, receipt):
    require(receipt["kind"] == "response" and receipt["status"] == "pass", "Passing response audit required")
    expected = {(arm, seed, t, subset) for arm in "ABCD" for seed in SEEDS for t, subset in PANELS}
    scores, worst = {}, {}
    for row in report["scores"]:
        key = (row["arm"], row["seed"], row["seconds"], row["subset"])
        require(key not in scores, "Duplicate report score")
        scores[key] = row["metrics"]
    for row in receipt["supplementary"]:
        key = (row["control"], row["seed_or_ensemble"], row["seconds"], row["subset"])
        require(key not in worst, "Duplicate receipt score")
        worst[key] = row
    require(set(scores) == expected and set(worst) == expected, "Incomplete or unexpected fixed score identities")
    cases = []
    for arm in ("B", "D"):
        for t, subset in PANELS:
            for seed in SEEDS:
                for action in ("mean", "median"):
                    pair = []
                    for selected in (arm, "A"):
                        key = (selected, seed, t, subset)
                        values = point_fields(scores[key][action])
                        # Already independently replayed. Preserve that receipt's
                        # CVaR/P95/max, checking its overlap against report CVaR.
                        require(math.isclose(values["cvar95"], worst[key][action]["cvar95"], rel_tol=2e-10, abs_tol=2e-10), "Report/receipt CVaR disagreement")
                        values.update(worst[key][action])
                        require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in values.values()), "Missing or nonfinite requested metric")
                        pair.append(values)
                    candidate, reference = pair
                    require(candidate["m4_events"] == reference["m4_events"], "M4 event support mismatch")
                    cases.append({"candidate": arm, "reference": "A", "seconds": t, "subset": subset,
                                  "seed_or_ensemble": seed, "action": action,
                                  "candidate_metrics": candidate, "reference_metrics": reference,
                                  "candidate_minus_reference": {k: candidate[k] - reference[k] for k in candidate if k != "m4_events"}})
    return {"kind": "response_secondary", "status": "extracted_from_independently_verified_report",
            "point_support": receipt["point_support"], "primary_C_minus_B_gate_unchanged": receipt["gate"],
            "interpretation": "Exploratory pre-specified B-A and D-A only; negative differences lower error. No new success criterion, confidence interval, gate, fit, or action selection.",
            "cases": cases}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--receipt-sha256", required=True)
    args = parser.parse_args(argv)
    receipt = checked_json(args.receipt, args.receipt_sha256)
    manifest = checked_json(args.root / "grid_manifest.json", receipt["grid_manifest_sha256"])
    completion = json.loads((args.root / "COMPLETE.json").read_text())
    # Same producer completion-pointer contract as the reviewed main extractor.
    require(manifest["status"] == "complete" and completion["grid_manifest_sha256"] == receipt["grid_manifest_sha256"], "Response grid not complete")
    report = checked_json(args.root / "report.json", manifest["report_sha256"])
    result = compact_secondary(report, receipt)
    result.update(report_sha256=manifest["report_sha256"], grid_manifest_sha256=receipt["grid_manifest_sha256"],
                  audit_receipt_sha256=args.receipt_sha256, extractor_sha256=file_sha(__file__),
                  extractor_dependency_sha256=file_sha(Path(__file__).with_name("extract_effects.py")))
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()

import copy
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from extract_effects import compact, checked_json


def fixture(kind):
    controls = ("B", "C") if kind == "response" else ("huber_ce", "natural_ce", "band_exposure_ce")
    report = {"scores": [], "comparisons": []}
    receipt = {"status": "pass", "kind": kind, "point_support": [0., 6.5] if kind == "response" else [.05, 6.55], "gate": {"status": "failed", "checks": []}}
    for t in (1, 3, 5):
        for subset in ("eval_seen", "eval_held"):
            for c in controls:
                for s in ("20261009", "20261010", "ensemble"):
                    value = 1. if c == controls[-1] else 2.
                    primary = dict(weighted_mae=value, medae=value / 2, cvar95=value * 3, tail={"4": dict(weighted_mae=value, event_macro_mae=value, events=20)})
                    row = dict(seconds=t, subset=subset, metrics={"mean": primary, "median": copy.deepcopy(primary)})
                    row["metrics"]["median"]["weighted_mae"] += .25
                    if kind == "response": row.update(arm=c, seed=s)
                    else: row.update(control=c, seed_or_ensemble="equal_pmf_ensemble" if s == "ensemble" else s)
                    report["scores"].append(row)
            for ref in controls[:-1]:
                row = dict(seconds=t, subset=subset, valid_fraction=1., bootstrap={"preserved": [1, 2]})
                check = dict(seconds=t, subset=subset, support=True) if kind == "response" else dict(seconds=t, subset=subset, reference_control=ref, pass_=False)
                if kind == "exposure": row["reference_control"] = ref
                report["comparisons"].append(row); receipt["gate"]["checks"].append(check)
    return report, receipt


class ExtractTests(unittest.TestCase):
    def test_hash_and_parse_use_one_byte_snapshot(self):
        raw = b'{"verified": true}'
        with patch.object(Path, "read_bytes", return_value=raw) as read, patch.object(Path, "read_text", side_effect=AssertionError("Must not reopen")):
            self.assertEqual(checked_json(Path("synthetic.json"), hashlib.sha256(raw).hexdigest()), {"verified": True})
            read.assert_called_once()
        with patch.object(Path, "read_bytes", return_value=raw):
            with self.assertRaisesRegex(ValueError, "Authenticated"):
                checked_json(Path("synthetic.json"), "0" * 64)

    def test_preserves_all_seeds_actions_comparisons_and_independent_gate(self):
        for kind, count in (("response", 6), ("exposure", 12)):
            report, receipt = fixture(kind); result = compact(report, receipt, kind)
            self.assertEqual(len(result["cases"]), count)
            self.assertEqual(result["gate"], receipt["gate"])
            self.assertEqual(result["point_support"], receipt["point_support"])
            for case in result["cases"]:
                self.assertEqual(len(case["decisions"]), 6)
                self.assertEqual(case["mean_ensemble_bootstrap"], {"preserved": [1, 2]})
                self.assertEqual(case["decisions"][0]["candidate_minus_reference"]["weighted_mae"], -1.)
                self.assertEqual(case["decisions"][1]["candidate"]["weighted_mae"], 1.25)

    def test_rejects_incomplete_audit_duplicate_and_missing_score(self):
        report, receipt = fixture("response")
        with self.assertRaisesRegex(ValueError, "Passing"):
            compact(report, dict(receipt, status="failed"), "response")
        report["scores"].append(report["scores"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            compact(report, receipt, "response")
        report, receipt = fixture("exposure"); report["scores"].pop()
        with self.assertRaises(KeyError): compact(report, receipt, "exposure")


if __name__ == "__main__": unittest.main(verbosity=2)

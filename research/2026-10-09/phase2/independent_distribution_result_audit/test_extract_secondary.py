"""Synthetic only: fixed identity coverage and arithmetic, no model/data inputs."""
import copy
import unittest

from extract_secondary import PANELS, SEEDS, compact_secondary


def fixture():
    report = {"scores": []}
    receipt = {"kind": "response", "status": "pass", "point_support": [i / 10 for i in range(66)],
               "gate": {"pass": False}, "supplementary": []}
    for arm in "ABCD":
        for seed in SEEDS:
            for t, subset in PANELS:
                metric = {"weighted_mae": ord(arm) / 100, "medae": t / 10,
                          "cvar95": 1.5, "tail": {"4": {"weighted_mae": 1.1, "event_macro_mae": 1.2, "events": 22}}}
                report["scores"].append({"arm": arm, "seed": seed, "seconds": t, "subset": subset,
                                          "metrics": {"mean": copy.deepcopy(metric), "median": copy.deepcopy(metric)}})
                tail = {"cvar95": 1.5, "weighted_p95_abs_error": 1.3, "maximum_abs_error": ord(arm) / 10}
                receipt["supplementary"].append({"control": arm, "seed_or_ensemble": seed, "seconds": t,
                                                  "subset": subset, "mean": tail.copy(), "median": tail.copy()})
    return report, receipt


class SecondaryTests(unittest.TestCase):
    def test_exact_fixed_coverage_and_existing_metric_subtraction(self):
        report, receipt = fixture()
        before = copy.deepcopy((report, receipt))
        result = compact_secondary(report, receipt)
        self.assertEqual(len(result["cases"]), 72)
        self.assertEqual(result["primary_C_minus_B_gate_unchanged"], {"pass": False})
        self.assertEqual(result["point_support"], receipt["point_support"])
        self.assertEqual((report, receipt), before)
        self.assertEqual({x["candidate"] for x in result["cases"]}, {"B", "D"})
        for row in result["cases"]:
            self.assertEqual(row["reference"], "A")
            for name, delta in row["candidate_minus_reference"].items():
                self.assertEqual(delta, row["candidate_metrics"][name] - row["reference_metrics"][name])
            self.assertNotIn("m4_events", row["candidate_minus_reference"])
            self.assertAlmostEqual(row["candidate_minus_reference"]["weighted_mae"], 0.01 if row["candidate"] == "B" else 0.03)

    def test_reject_missing_duplicate_unexpected_and_nonpassing(self):
        for modify in (lambda r, a: r["scores"].pop(),
                       lambda r, a: r["scores"].append(r["scores"][0]),
                       lambda r, a: r["scores"][0].update(arm="X"),
                       lambda r, a: a["supplementary"].pop(),
                       lambda r, a: a["supplementary"].append(a["supplementary"][0]),
                       lambda r, a: a.update(status="fail")):
            report, receipt = fixture()
            modify(report, receipt)
            with self.assertRaises(ValueError):
                compact_secondary(report, receipt)

    def test_reject_mismatched_receipt_tail_support_and_nonfinite(self):
        for modify in (lambda r, a: a["supplementary"][0]["mean"].update(cvar95=2.0),
                       lambda r, a: r["scores"][0]["metrics"]["mean"]["tail"]["4"].update(events=23),
                       lambda r, a: r["scores"][0]["metrics"]["mean"].update(medae=float("nan"))):
            report, receipt = fixture()
            modify(report, receipt)
            with self.assertRaises(ValueError):
                compact_secondary(report, receipt)


if __name__ == "__main__":
    unittest.main()

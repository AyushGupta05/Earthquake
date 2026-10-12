import copy
import math
import unittest
from activity import extract_event, summarize, InvalidInput, _window_values, _piece_geometry
from grouping import group_events, distance_km, THIRTY_DAYS_NS


def fixture(slot=0, partition="TRAIN", amplitudes=None, noise=1, delay=0, family="ENZ"):
    amplitudes = [4] * 20 if amplitudes is None else amplitudes
    values = [-noise, noise] * 12
    values += [value for amplitude in amplitudes for value in (-amplitude, amplitude)]
    names = ("HNE", "HNN", "HNZ") if family == "ENZ" else ("HN1", "HN2", "HNZ")
    event = {"slot": slot, "partition": partition, "t0_ns": 0, "p_ns": delay,
             "family": family, "mw": 6.0, "group": "g" + str(slot),
             "components": [{"name": name, "pieces": [{"start_ns": -3_000_000_000,
                              "rational_period": [125_000_000, 1], "values": list(values)}]}
                            for name in names]}
    if partition == "DEV":
        event["components"] = None
    return event


def qualified():
    return {"horizon_support": [True, True, True], "group_eligible": True}


def result(event):
    return extract_event(event, qualified())


def cohort():
    rows = []
    for slot in range(65):
        event = fixture(slot, "TRAIN" if slot < 41 else "DEV",
                        [4, 4] + [1] * 18 if slot < 5 else [4] * 20)
        event["mw"] = 4.0 if slot < 5 else 6.0
        rows.append(result(event))
    return rows


def metadata():
    return [{"ordinal": 2 * slot,
             "partition": "TRAIN" if slot < 41 else "DEV",
             "origin_ns": None, "latitude": None, "longitude": None} for slot in range(65)]


def origin(time=0, lat=0, lon=0):
    return {"origin_ns": time, "latitude": lat, "longitude": lon}


class ActivityTests(unittest.TestCase):
    def test_all_deadlines_right_censored(self):
        out = result(fixture())
        self.assertTrue(out["all_horizon_eligible"])
        for cell, expected in zip(out["horizons"], (4, 12, 20)):
            self.assertEqual(cell["states"], [1] * expected)
            self.assertEqual(cell["run_ages"], list(range(1, expected + 1)))
            self.assertEqual(cell["transitions"], [])
            self.assertTrue(cell["episodes"][-1]["right_censored"])

    def test_quiet_reactivates_and_prior_run_age(self):
        out = result(fixture(amplitudes=[4, 4, 1, 1, 4] + [4] * 15))
        cell = out["horizons"][1]
        self.assertEqual(cell["transitions"], [{"cell": 3, "kind": "off", "prior_run_age": 2},
                                               {"cell": 5, "kind": "on", "prior_run_age": 2}])
        self.assertEqual(cell["run_ages"][:6], [1, 2, 1, 2, 1, 2])
        self.assertEqual([e["right_censored"] for e in cell["episodes"]], [False, False, True])

    def test_subpeak_excitation_differs_from_quiet_without_peak_growth(self):
        active = result(fixture(amplitudes=[8] + [4] * 19))
        quiet = result(fixture(amplitudes=[8] + [1] * 19))
        self.assertEqual(active["horizons"][0]["states"], [1] * 4)
        self.assertEqual(quiet["horizons"][0]["states"], [1, 0, 0, 0])
        self.assertEqual(max(abs(v) for v in fixture(amplitudes=[8] + [4] * 19)["components"][0]["pieces"][0]["values"]), 8)

    def test_strict_threshold_and_floor(self):
        self.assertEqual(result(fixture(amplitudes=[3] * 20))["horizons"][0]["states"], [0] * 4)
        cell = result(fixture(noise=0))["horizons"][0]
        self.assertEqual(cell["noise_floor"], [True] * 3)
        self.assertEqual(cell["noise_power"], [1.0] * 3)
        self.assertEqual(result(fixture())["horizons"][0]["noise_floor"], [False] * 3)

    def test_future_nonfinite_never_poison_earlier_horizon(self):
        event = fixture()
        before = result(event)["horizons"][0]
        event["components"][0]["pieces"][0]["values"][40] = float("nan")
        out = result(event)
        self.assertEqual(out["horizons"][0], before)
        self.assertEqual(out["horizons"][1]["status"], "BAD_WINDOW_NUMBER")

    def test_deadline_sample_excluded_half_open(self):
        event = fixture()
        before = result(event)["horizons"][0]
        event["components"][0]["pieces"][0]["values"][32] = float("inf")
        self.assertEqual(result(event)["horizons"][0], before)

    def test_global_delay_complete_cells(self):
        event = fixture(delay=375_000_000)
        cells = result(event)["horizons"]
        self.assertEqual([len(c["states"]) for c in cells], [2, 10, 18])

    def test_late_base_denies_without_any_values(self):
        event = fixture(delay=750_000_001)
        event["components"] = None
        self.assertEqual([h["status"] for h in result(event)["horizons"]], ["LATE_BASE"] * 3)
        event = fixture(delay=750_000_000)
        self.assertEqual(len(result(event)["horizons"][0]["states"]), 1)
        event = fixture(delay=10_000_000_000)
        event["components"] = None
        self.assertEqual([h["status"] for h in result(event)["horizons"]], ["LATE_BASE"] * 3)

    def test_fragmented_piece_parity(self):
        event = fixture()
        expected = result(event)
        for component in event["components"]:
            values = component["pieces"][0]["values"]
            component["pieces"] = [{"start_ns": -3_000_000_000 + index * 125_000_000,
                                    "rational_period": [125_000_000, 1], "values": values[index:end]}
                                   for index, end in ((0, 12), (12, 25), (25, 64))]
        self.assertEqual(result(event), expected)

    def test_gap_and_overlap_not_repaired(self):
        for shift in (-1, 1):
            event = fixture()
            values = event["components"][0]["pieces"][0]["values"]
            event["components"][0]["pieces"] = [
                {"start_ns": -3_000_000_000, "rational_period": [125_000_000, 1], "values": values[:28]},
                {"start_ns": 500_000_000 + shift, "rational_period": [125_000_000, 1], "values": values[28:]}]
            self.assertEqual(result(event)["horizons"][0]["status"], "BAD_WINDOW_COVERAGE")

    def test_fractional_period_exact_quarters(self):
        event = fixture()
        for component in event["components"]:
            component["pieces"] = [{"start_ns": -3_000_000_000,
                                    "rational_period": [250_000_000, 3],
                                    "values": [-1, 0, 1] * 12 + [-4, 0, 4] * 20}]
        out = result(event)
        self.assertEqual([len(h["states"]) for h in out["horizons"]], [4, 12, 20])
        prepared = _piece_geometry(event["components"], "ENZ")
        self.assertEqual(list(_window_values(prepared[0], 0, 250_000_000)), [-4.0, 0.0, 4.0])

    def test_dev_and_unsupported_are_deferred(self):
        self.assertEqual(result(fixture(partition="DEV"))["horizons"][0]["status"], "DEFERRED_DEV")
        event = fixture()
        event["components"] = None
        self.assertEqual(extract_event(event, {"horizon_support": [True, False, True], "group_eligible": True})["horizons"][0]["status"], "UNSUPPORTED")
        self.assertEqual(extract_event(event, {"horizon_support": [True] * 3, "group_eligible": False})["horizons"][0]["status"], "GROUP_INELIGIBLE")

    def test_dev_denied_value_smuggling_rejected(self):
        event = fixture(partition="DEV")
        event["components"] = []
        with self.assertRaises(InvalidInput):
            result(event)

    def test_literal_numbered_family(self):
        self.assertTrue(result(fixture(family="12Z"))["all_horizon_eligible"])
        event = fixture()
        event["components"][0]["name"] = "HN1"
        with self.assertRaises(InvalidInput):
            result(event)

    def test_nonfinite_noise_all_unknown(self):
        event = fixture()
        event["components"][0]["pieces"][0]["values"][0] = float("nan")
        self.assertEqual([h["status"] for h in result(event)["horizons"]], ["BAD_NOISE_NUMBER"] * 3)

    def test_strict_types_and_extra_fields(self):
        for field, value in (("slot", True), ("t0_ns", 0.0), ("p_ns", -1), ("mw", True), ("partition", "TEST")):
            event = fixture()
            event[field] = value
            with self.assertRaises(InvalidInput):
                result(event)
        event = fixture()
        event["extra"] = 0
        with self.assertRaises(InvalidInput):
            result(event)
        with self.assertRaises(InvalidInput):
            extract_event(fixture(), {"horizon_support": [1, True, True], "group_eligible": True})

    def test_invalid_samples_and_periods(self):
        for value in (True, "4", 1e13, float("inf"), object()):
            event = fixture()
            event["components"][0]["pieces"][0]["values"][24] = value
            self.assertEqual(result(event)["horizons"][0]["status"], "BAD_WINDOW_NUMBER")
        for period in ([0, 1], [1, 0], [2, 2], [True, 1], [1.0, 1]):
            event = fixture()
            event["components"][0]["pieces"][0]["rational_period"] = period
            with self.assertRaises(InvalidInput):
                result(event)

    def test_caps_container_subclasses_and_hostile_value_not_called(self):
        class Hostile:
            def __float__(self):
                raise AssertionError("must not call")
            def __eq__(self, other):
                raise AssertionError("must not call")
        class CustomList(list):
            pass
        event = fixture()
        event["components"][0]["pieces"][0]["values"] = CustomList([1])
        with self.assertRaises(InvalidInput):
            result(event)
        event = fixture()
        event["components"][0]["pieces"][0]["values"][24] = Hostile()
        self.assertEqual(result(event)["horizons"][0]["status"], "BAD_WINDOW_NUMBER")
        event = fixture()
        event["components"][0]["pieces"] *= 32769
        with self.assertRaises(InvalidInput):
            result(event)

    def test_summary_train_only_group_gate(self):
        rows = cohort()
        summary = summarize(rows, {"grouping_frozen": True, "prior_support_floor_pass": True})
        self.assertTrue(summary["combined_prospective_gate"])
        self.assertEqual(summary["events"], 65)
        self.assertEqual(summary["horizon_cells"], 195)
        self.assertFalse(summary["fit_authorized"])
        changed = copy.deepcopy(rows)
        for row in changed[41:]:
            row["mw"] = 14.0
            row["group"] = "irrelevant_dev"
        self.assertEqual(summarize(changed, {"grouping_frozen": True, "prior_support_floor_pass": True}), summary)

    def test_five_events_in_one_group_not_five_groups(self):
        rows = cohort()
        for row in rows[:5]:
            row["group"] = "same"
        summary = summarize(rows, {"grouping_frozen": True, "prior_support_floor_pass": True})
        self.assertFalse(summary["observational_variation_pass"])
        self.assertEqual(summary["off_train_operational_groups"], 1)

    def test_external_flags_never_fit_authority(self):
        summary = summarize(cohort(), {"grouping_frozen": False, "prior_support_floor_pass": True})
        self.assertTrue(summary["observational_variation_pass"])
        self.assertFalse(summary["combined_prospective_gate"])
        self.assertFalse(summary["fit_authorized"])

    def test_summary_rejects_fake_censor_and_bool_age(self):
        for change in ("censor", "age", "future_status"):
            rows = cohort()
            if change == "censor":
                rows[10]["horizons"][2]["episodes"][-1]["right_censored"] = False
            elif change == "age":
                rows[10]["horizons"][0]["run_ages"][0] = True
            else:
                rows[41]["horizons"][0]["status"] = "available"
            with self.assertRaises(InvalidInput):
                summarize(rows, {"grouping_frozen": True, "prior_support_floor_pass": True})

    def test_summary_denominator_order_and_partition_guards(self):
        for change in ("count", "order", "partition"):
            rows = cohort()
            if change == "count":
                rows.pop()
            elif change == "order":
                rows[0], rows[1] = rows[1], rows[0]
            else:
                rows[-1]["partition"] = "TRAIN"
            with self.assertRaises(InvalidInput):
                summarize(rows, {"grouping_frozen": True, "prior_support_floor_pass": True})

    def test_impossible_horizon_lengths_and_increments_rejected(self):
        from activity import _sequence
        for index, count in ((0, 20), (2, 2), (1, 11)):
            rows = cohort()
            cell = rows[10]["horizons"][index]
            cell["ratios"] = [16.0] * count
            cell["states"], cell["run_ages"], cell["transitions"], cell["episodes"] = _sequence(cell["ratios"])
            with self.assertRaises(InvalidInput):
                summarize(rows, {"grouping_frozen": True, "prior_support_floor_pass": True})

    def test_inconsistent_ratio_noise_prefixes_rejected(self):
        for change in ("ratio", "noise", "floor"):
            rows = cohort()
            cell = rows[10]["horizons"][1]
            if change == "ratio":
                cell["ratios"][0] = 17.0  # Same state, but inconsistent observed value.
            elif change == "noise":
                cell["noise_power"][0] = 2.0
            else:
                cell["noise_floor"][0] = True
            with self.assertRaises(InvalidInput):
                summarize(rows, {"grouping_frozen": True, "prior_support_floor_pass": True})


class GroupingTests(unittest.TestCase):
    def test_transitive_chain_minimum_original_ordinal(self):
        rows = metadata()
        rows[0].update(origin(lon=0))
        rows[1].update(origin(lon=1.5))
        rows[2].update(origin(lon=3))
        out = group_events(rows)
        self.assertEqual(out["edges"], [[0, 2], [2, 4]])
        self.assertEqual(out["groups"][0]["original_ordinals"], [0, 2, 4])
        self.assertEqual(out["groups"][0]["identifier"], 0)

    def test_thirty_day_inclusive_and_one_ns_outside(self):
        for delta, connected in ((THIRTY_DAYS_NS, True), (THIRTY_DAYS_NS + 1, False)):
            rows = metadata()
            rows[0].update(origin())
            rows[1].update(origin(time=delta))
            self.assertEqual(bool(group_events(rows)["edges"]), connected)

    def test_200km_boundary_and_outside(self):
        rows = metadata()
        rows[0].update(origin())
        rows[1].update(origin(lon=math.degrees(200 / 6371)))
        self.assertEqual(group_events(rows)["edges"], [[0, 2]])
        rows[1].update(origin(lon=math.degrees(200.000001 / 6371)))
        self.assertEqual(group_events(rows)["edges"], [])

    def test_dateline_and_poles(self):
        self.assertLess(distance_km(0, 179.9, 0, -179.9), 23)
        self.assertLess(distance_km(90, 0, 90, 180), 1e-9)
        self.assertLessEqual(distance_km(0, 0, 0, 180), math.pi * 6371)

    def test_unknown_origins_not_independent_singletons(self):
        rows = metadata()
        for slot, value in enumerate(({}, origin(lat=91), origin(lon=float("nan")), origin(time=True), origin(lat=None))):
            rows[slot].update(value)
        out = group_events(rows)
        self.assertEqual(out["groups"], [])
        self.assertTrue(all(row["group_identifier"] is None and not row["operational_eligible"] for row in out["rows"]))

    def test_cross_partition_excludes_both(self):
        rows = metadata()
        rows[0].update(origin())
        rows[41].update(origin())
        out = group_events(rows)
        self.assertEqual(out["rows"][0]["status"], "CROSS_PARTITION")
        self.assertEqual(out["rows"][41]["status"], "CROSS_PARTITION")
        self.assertFalse(out["groups"][0]["operational_eligible"])
        self.assertFalse(out["physical_sequence_independence_verified"])

    def test_order_duplicate_test_and_labels_rejected(self):
        for field, value in (("ordinal", True), ("partition", "TEST"), ("mw", 6.0)):
            rows = metadata()
            rows[0][field] = value
            with self.assertRaises(InvalidInput):
                group_events(rows)
        rows = metadata()
        rows[1]["ordinal"] = 0
        with self.assertRaises(InvalidInput):
            group_events(rows)


if __name__ == "__main__":
    unittest.main()

import copy
import tempfile
from pathlib import Path
import unittest

import numpy as np

import audit_export as audit


def fixture():
    event = next(str(i) for i in range(100) if audit.bucket("polarization-event-v1", str(i)) >= 2)
    station = next(str(i) for i in range(100) if audit.bucket("polarization-station-v1", str(i)) >= 2)
    m = dict(source_row_index=np.array([7]), trace_name=np.array(["event.IV.AAA..HH"]),
        source_id=np.array([event]), station_id=np.array(["IV.AAA"]), station_group=np.array([station]),
        subset=np.array(["fit"]), sampling_weight=np.array([2.]), valid=np.ones((1, 3), bool),
        invalid_codes=np.zeros((1, 3), np.uint16), deadlines=np.array([1, 3, 5]),
        event_bucket=np.array([audit.bucket("polarization-event-v1", event)]),
        station_bucket=np.array([audit.bucket("polarization-station-v1", station)]),
        n_metadata_eligible=np.array([4]), n_sampled=np.array([2]), targets=np.array([3.2]),
        sensitivity=np.ones((1, 3)), static=np.zeros((1, 34)), response=np.zeros((1, 72)),
        native_units=np.array(["m/s"]), response_epoch_ids=np.array([["E", "N", "Z"]]))
    p = {k: v.copy() for k, v in m.items() if k in audit.IDENTITIES}
    p.update(targets=np.array([[3.2, 10., 2.]]), sensitivities=m["sensitivity"].copy(),
        native_units=m["native_units"].copy(), station_channels=np.array(["HH"]),
        target_names=np.array(["source_magnitude", "path_hyp_distance_km", "source_depth_km"]))
    return m, p


def epochs_and_response():
    evaluation = {"valid_response": True, "final_stage_output_rate": 20.,
        "frequency_finite_nonzero": [True] * 6, "descriptor_unmasked": [[0., 1., 0.]] * 6}
    epochs = []
    for c in "ENZ":
        e = dict(epoch_id=c, response_id="response", sensitivity=1., input_units="M/S",
            sensitivity_frequency_hz=1., sample_rate_hz=20., network="IV", station="AAA",
            location="", channel="HH" + c, start=0., end=None)
        e["descriptor"] = audit.reconstructed_descriptor(e, evaluation).tolist()
        epochs.append(e)
    return epochs, {"response": evaluation}


class AuditTest(unittest.TestCase):
    def test_variable_fraction_timestamp_matches_source_microsecond_clock(self):
        expected = audit.timestamp("2012-06-22T15:30:35.440000+00:00")
        for value in ("2012-06-22T15:30:35.44Z", "2012-06-22T15:30:35.44",
                      " 2012-06-22T15:30:35.44000+00:00 "):
            self.assertEqual(audit.timestamp(value), expected)
        self.assertEqual(audit.timestamp("2012-06-22T15:30:35.1234567Z"),
                         audit.timestamp("2012-06-22T15:30:35.123456Z"))

    def test_exact_metadata_and_target_alignment(self):
        m, p = fixture()
        self.assertEqual(audit.check_arrays(m, p), 1)
        for key in ("targets", "sampling_weight", "valid", "sensitivity"):
            bad = copy.deepcopy(m)
            bad[key].flat[0] += 1 if bad[key].dtype != bool else False
            if key == "valid":
                bad[key].flat[0] = False
            with self.assertRaises(ValueError):
                audit.check_arrays(bad, p)

    def test_member_allowlist_does_not_decode_feature_payload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "metadata.npz"
            np.savez(path, source_row_index=np.arange(3), features=np.array([{}], dtype=object))
            out = audit.load_metadata(path, ["source_row_index"])
            np.testing.assert_array_equal(out["source_row_index"], np.arange(3))
            with self.assertRaisesRegex(ValueError, "forbidden"):
                audit.load_metadata(path, ["features"])

    def test_masks_and_static_gain_reconstruction(self):
        m, _ = fixture(); epochs, responses = epochs_and_response()
        m["response"][:] = np.array([e["descriptor"] for e in epochs]).reshape(1, 72)
        m["static"][:, 10:] = np.array([audit.epoch_static(e) for e in epochs]).reshape(1, 24)
        _, summary = audit.check_descriptors(m, epochs, responses)
        self.assertEqual(summary["valid_component_frequencies"], 12)
        self.assertEqual(summary["masked_component_frequencies"], 6)
        m["response"][0, 0] = .1
        with self.assertRaisesRegex(ValueError, "Export descriptor"):
            audit.check_descriptors(m, epochs, responses)

    def test_invalid_response_and_rate_mismatch_fail_closed(self):
        epochs, responses = epochs_and_response()
        self.assertEqual(audit.reconstructed_descriptor(epochs[0], responses["response"])[:, 3].tolist(), [1, 1, 1, 1, 0, 0])
        bad = dict(responses["response"], valid_response=False)
        self.assertTrue((audit.reconstructed_descriptor(epochs[0], bad) == 0).all())
        bad = dict(responses["response"], final_stage_output_rate=100.)
        self.assertTrue((audit.reconstructed_descriptor(epochs[0], bad) == 0).all())

    def test_selected_csv_static_and_epoch_window(self):
        m, p = fixture(); epochs, _ = epochs_and_response()
        m["static"][0, :10] = [1, 0, 0, 0, 0, 0, 123., 0, 0, 1]
        row = dict(source_row_index="7", trace_name=m["trace_name"][0], source_id=m["source_id"][0],
            station_channels="HH", station_elevation_m="123", station_vs_30_mps="nan",
            trace_start_time="1970-01-01T00:00:00Z", trace_P_arrival_sample="200")
        by_id = {e["epoch_id"]: e for e in epochs}
        self.assertEqual(audit.check_selected_rows(m, p, by_id, [row]), 1)
        by_id["E"]["end"] = 6.
        with self.assertRaisesRegex(ValueError, "cover"):
            audit.check_selected_rows(m, p, by_id, [row])

    def test_corrected_join_complete_membership_and_epochs(self):
        m, _ = fixture()
        row = dict(source_row_index="7", trace_name=m["trace_name"][0], source_id=m["source_id"][0], metadata_eligible="1")
        for c in "ENZ":
            row[c + "_status"] = "matched"; row[c + "_epoch_id"] = c
        self.assertEqual(audit.check_join_rows(m, [row])["selected_rows_matched"], 1)
        with self.assertRaisesRegex(ValueError, "Repeated"):
            audit.check_join_rows(m, [row, row])
        with self.assertRaisesRegex(ValueError, "missing"):
            audit.check_join_rows(m, [])
        for ineligible in ("0", "True", "", "2"):
            with self.assertRaisesRegex(ValueError, "ineligible"):
                audit.check_join_rows(m, [dict(row, metadata_eligible=ineligible)])
        row["E_epoch_id"] = "old"
        with self.assertRaisesRegex(ValueError, "corrected"):
            audit.check_join_rows(m, [row])


if __name__ == "__main__":
    unittest.main(verbosity=2)

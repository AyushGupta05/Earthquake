import unittest
from types import SimpleNamespace
from audit_metadata import canonical_orientation, metadata_window, finite, COLUMNS, unique_epoch_cover, window_responses


class MetadataAuditTest(unittest.TestCase):
    def test_targets_not_model_inputs(self):
        self.assertNotIn('source_magnitude', COLUMNS)
        self.assertNotIn('trace_S_arrival_sample', COLUMNS)

    def test_orientation(self):
        self.assertTrue(canonical_orientation('E', {'azimuth_deg': 90, 'dip_deg': 0}))
        self.assertTrue(canonical_orientation('N', {'azimuth_deg': 360, 'dip_deg': -1}))
        self.assertTrue(canonical_orientation('Z', {'azimuth_deg': None, 'dip_deg': -90}))
        self.assertFalse(canonical_orientation('Z', {'dip_deg': 90}))
        self.assertFalse(canonical_orientation('E', {'azimuth_deg': 0, 'dip_deg': 0}))
        self.assertFalse(canonical_orientation('N', {'azimuth_deg': None, 'dip_deg': 0}))

    def test_window_boundaries(self):
        row = {'trace_P_arrival_sample': '200', 'trace_dt_s': '.01', 'trace_npts': '700'}
        self.assertTrue(metadata_window(row))
        for key, value in [('trace_P_arrival_sample', '199'), ('trace_P_arrival_sample', '200.5'),
                           ('trace_npts', '699'), ('trace_dt_s', '.02'), ('trace_dt_s', 'nan')]:
            bad = dict(row, **{key: value})
            self.assertFalse(metadata_window(bad))

    def test_nonfinite(self):
        for value in ['nan', 'inf', '', None, 'missing']:
            self.assertIsNone(finite(value))
        self.assertEqual(finite('1.2'), 1.2)

    def test_later_epoch_overlap(self):
        e = lambda a, b: SimpleNamespace(start=a, end=b)
        self.assertTrue(unique_epoch_cover([e(0, 100)], 28, 35))
        self.assertFalse(unique_epoch_cover([e(0, 100), e(30, 40)], 28, 35))
        self.assertFalse(unique_epoch_cover([e(0, 35), e(35, 40)], 28, 35))
        self.assertFalse(unique_epoch_cover([e(0, 34)], 28, 35))
        self.assertFalse(unique_epoch_cover([], 28, 35))
        self.assertTrue(unique_epoch_cover([e(0, 100), e(40, 30)], 28, 35))

    def test_properties_from_window_epoch(self):
        def epoch(start, end, usable=True, azimuth=90):
            return SimpleNamespace(start=start, end=end, usable=usable, sensitivity=2,
                                   input_units='m/s', azimuth_deg=azimuth, dip_deg=0)
        row = dict(trace_start_time='0', trace_P_arrival_sample='1000', trace_npts='2000',
                   trace_dt_s='.01', station_network_code='X', station_code='A',
                   station_channels='HH')
        module = SimpleNamespace(utc_seconds=float, location_code=lambda r: ('', False),
                                 normalize_units=lambda v: v)
        inv = SimpleNamespace(index={('X', 'A', '', 'HHE'): [epoch(0, 5), epoch(6, 100, False, 13)]})
        actual = window_responses(row, inv, module)['E']
        self.assertEqual(actual['status'], 'invalid_response')
        self.assertEqual(actual['azimuth_deg'], 13)
        inv.index[('X', 'A', '', 'HHE')] = [epoch(6, 100)]
        self.assertEqual(window_responses(row, inv, module)['E']['status'], 'matched')
        inv.index[('X', 'A', '', 'HHE')].append(epoch(10, 30))
        self.assertEqual(window_responses(row, inv, module)['E']['status'], 'no_unique_cover')


if __name__ == '__main__':
    unittest.main()

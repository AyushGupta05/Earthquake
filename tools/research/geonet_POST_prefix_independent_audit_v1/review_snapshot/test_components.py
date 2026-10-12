import unittest
import numpy as np
from fractions import Fraction
from replay import component, joint
from geometry import pair
from sample_proofs import stats, digest


def row():
    return {'t0_ns': 3_000_000_000, 'family': 'ENZ', 'prefix': 'HH', 'nominal_rates': {'HHE': [10, 1], 'HHN': [10, 1], 'HHZ': [10, 1]}}


def piece(ordinal, start, rate=10, values=None):
    values = np.arange(10, dtype=np.int32) if values is None else np.array(values, dtype=np.float32)
    period = Fraction(1_000_000_000, rate)
    return {'record': ordinal, 'lo': 0, 'hi': len(values), 'count': len(values),
            'first': pair(Fraction(start)), 'last': pair(Fraction(start) + (len(values) - 1) * period),
            'period': pair(period), 'dtype': 'i4' if values.dtype.kind == 'i' else 'f4',
            'samples_sha256': digest(values, 'i4' if values.dtype.kind == 'i' else 'f4'), **stats(values)}


class ComponentTests(unittest.TestCase):
    def test_phase_accumulation_and_failure_priority(self):
        pieces = [piece(i, i * 1_000_000_000 + i * 900) for i in range(4)]
        self.assertEqual(component('HHE', pieces, row(), 1, True)['reason'], 'phase')
        pieces[0]['finite'] = False
        self.assertEqual(component('HHE', pieces, row(), 1, True)['reason'], 'nonfinite')

    def test_gap_overlap_and_no_dedup(self):
        pieces = [piece(i, i * 1_000_000_000) for i in range(4)]
        duplicate = piece(9, 1_000_000_000)
        value = component('HHE', pieces + [duplicate], row(), 1, True)
        self.assertEqual(value['reason'], 'gap_overlap')
        self.assertEqual(value['count'], 50)
        self.assertEqual(len(value['pieces']), 5)

    def test_metadata_mismatch_does_not_change_complete(self):
        r = row(); r['nominal_rates']['HHE'] = [20, 1]
        value = component('HHE', [piece(i, i * 1_000_000_000) for i in range(4)], r, 1, True)
        self.assertEqual(value['status'], 'complete'); self.assertIs(value['metadata_rate_match'], False)
        missing = component('HHE', [], r, 1, False)
        observed = component('HHE', [], r, 1, True)
        self.assertEqual((missing['reason'], observed['reason']), ('missing_component', 'no_samples_in_window'))
        self.assertIsNone(missing['finite'])

    def test_joint_unknown_before_incomplete_and_grid(self):
        components = [component('HH' + suffix, [piece(i, i * 1_000_000_000) for i in range(4)], row(), 1, True) for suffix in 'ENZ']
        self.assertEqual(joint(row(), components)['status'], 'complete')
        components[0]['status'] = 'incomplete'; components[1]['status'] = 'unknown'
        self.assertEqual(joint(row(), components)['reason'], 'component_unknown')
        components[0]['status'] = components[1]['status'] = 'complete'
        components[1]['rate'] = [20, 1]
        self.assertEqual(joint(row(), components)['reason'], 'joint_rate')
        components[1]['rate'] = [10, 1]; components[1]['first'] = [2000, 1]
        value = joint(row(), components)
        self.assertEqual((value['reason'], value['rate']), ('joint_phase', [10, 1]))


if __name__ == '__main__': unittest.main()

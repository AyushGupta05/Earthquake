import hashlib
import unittest
import numpy as np
from sample_proofs import digest, stats, aggregate_stats


class SampleProofTests(unittest.TestCase):
    def test_local_nonfinite_and_dtype_prefixed_hash(self):
        data = np.array([1, 2, 3, 4, np.nan], dtype=np.float32)
        self.assertTrue(stats(data[:4])['finite'])
        self.assertFalse(stats(data)['finite'])
        self.assertIsNone(stats(data)['minimum'])
        data = np.array([-2, 3], dtype='>i4')
        expected = b'i4\0' + np.array([-2, 3], dtype='<i4').tobytes()
        self.assertEqual(digest(data, 'i4'), hashlib.sha256(expected).hexdigest())

    def test_extreme_runs_join_descriptively(self):
        pieces = []
        for values in ([1, 9, 9, 9], [9, 9, 9], [9, 9, 2]):
            data = np.array(values, dtype=np.int32)
            pieces.append({'count': len(data), **stats(data)})
        result = aggregate_stats(pieces)
        self.assertEqual((result['minimum'], result['maximum'], result['extreme_run'], result['flat']), (1, 9, 8, False))

    def test_flat_all_samples_and_nonfinite_statistics(self):
        data = np.array([0.0] * 9, dtype=np.float64)
        value = stats(data)
        self.assertEqual((value['first_run'], value['last_run'], value['min_run'], value['max_run']), (9, 9, 9, 9))
        self.assertEqual(aggregate_stats([{'count': 9, **value}])['extreme_run'], 9)
        nan = stats(np.array([float('inf')], dtype=np.float64))
        result = aggregate_stats([{'count': 1, **nan}])
        self.assertFalse(result['finite']); self.assertIsNone(result['extreme_run'])


if __name__ == '__main__': unittest.main()

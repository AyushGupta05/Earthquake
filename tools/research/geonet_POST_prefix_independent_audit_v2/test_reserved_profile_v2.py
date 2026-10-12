"""Only invented records; B1001 reserved byte has no inferred meaning."""
import copy
import unittest
import numpy as np
from header_scanner import scan
from geometry import header_grid
from native_decode import decode_record
from replay import replay
from fixtures import plan_and_bodies, reader
from strict import sha, Reject
from invented import int_record


def invented_variant(reserved):
    raw = bytearray(int_record(correction=-5, microsecond=-50))
    raw[62] = reserved  # Invented B1001 offset56 + field5 offset6.
    return bytes(raw)


class ReservedProfileV2Tests(unittest.TestCase):
    def test_zero_one_255_preserve_raw_descriptor_clock_rate_samples(self):
        grids = []; values = []; hashes = []
        for reserved in (0, 1, 255):
            raw = invented_variant(reserved)
            ledger = scan(raw)
            self.assertEqual(ledger['disposition'], 'supported')
            descriptor = ledger['records'][0]
            self.assertEqual(descriptor['b1001'][2], reserved)
            self.assertEqual(descriptor['b1001'][1], -50)
            self.assertEqual(descriptor['b1001'][0], 100)
            grids.append(header_grid(descriptor))
            values.append(decode_record(raw, descriptor, *grids[-1]))
            hashes.append(sha(raw))
        self.assertEqual(grids[0], grids[1]); self.assertEqual(grids[1], grids[2])
        self.assertEqual(grids[0][0], -550_000)
        self.assertTrue(np.array_equal(values[0], values[1]))
        self.assertTrue(np.array_equal(values[1], values[2]))
        self.assertEqual(len(set(hashes)), 3)

    def test_source_classification_and_sample_digest_unaffected(self):
        results = []
        for reserved in (0, 1, 255):
            raw = invented_variant(reserved)
            plan, bodies = plan_and_bodies(raw=raw)
            value = replay(plan, reader(bodies))
            self.assertEqual(value['schema'], 'geonet-POST-prefix-qualification-v2')
            self.assertEqual(value['batches'][0]['status'], 'decoded')
            self.assertEqual((value['aggregate']['rows'], value['aggregate']['cells']), (65, 195))
            results.append(value)
        self.assertEqual(len({v['records'][0]['raw_sha256'] for v in results}), 3)
        self.assertEqual(len({v['records'][0]['samples_sha256'] for v in results}), 1)
        self.assertEqual(results[0]['rows'], results[1]['rows'])
        self.assertEqual(results[1]['rows'], results[2]['rows'])
        self.assertEqual(results[0]['aggregate'], results[2]['aggregate'])

    def test_other_reserved_and_leap_rejections_remain(self):
        descriptor = scan(invented_variant(255))['records'][0]
        for field, value in (('date_unused', 1), ('b1000_reserved', 1),
                             ('b100', [10, 0, 1, 0, 0]), ('flags', [0x10, 0, 0]), ('flags', [0x20, 0, 0])):
            changed = copy.deepcopy(descriptor); changed[field] = value
            with self.assertRaises(Reject): header_grid(changed)


if __name__ == '__main__': unittest.main()

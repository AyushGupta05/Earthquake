import unittest
from header_scanner import scan
from geometry import header_grid
from native_decode import decode_record
from invented import int_record
from strict import Reject


class DecodeTests(unittest.TestCase):
    def test_fresh_individual_records(self):
        for raw in (int_record(), int_record(channel='HHN', sequence=2)):
            ledger = scan(raw)
            self.assertEqual(ledger['disposition'], 'supported')
            record = ledger['records'][0]
            data = decode_record(raw, record, *header_grid(record))
            self.assertEqual(data.tolist(), list(range(40)))
        raw = int_record() + int_record(sequence=2)
        record = scan(raw)['records'][0]
        with self.assertRaises(Reject): decode_record(raw, record, *header_grid(record))

    def test_signed_microsecond_and_unapplied_correction(self):
        for correction, activity, micros in ((-10, 0, -50), (10, 2, 50)):
            raw = int_record(correction=correction, activity=activity, microsecond=micros)
            record = scan(raw)['records'][0]
            self.assertEqual(decode_record(raw, record, *header_grid(record)).size, 40)

    def test_zero_advertised_without_invented_trace(self):
        raw = int_record(count=0)
        record = scan(raw)['records'][0]
        self.assertIsNone(decode_record(raw, record, *header_grid(record)))

    def test_wrong_header_expectation(self):
        raw = int_record()
        record = scan(raw)['records'][0]
        start, rate = header_grid(record)
        with self.assertRaises(Reject): decode_record(raw, record, start + 1, rate)
        with self.assertRaises(Reject): decode_record(raw, record, start, rate * 2)
        record['nslc'][1] = 'OTHER'
        with self.assertRaises(Reject): decode_record(raw, record, start, rate)


if __name__ == '__main__': unittest.main()

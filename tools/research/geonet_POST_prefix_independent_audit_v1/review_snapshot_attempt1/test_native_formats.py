import io
import struct
import unittest
from unittest.mock import patch
import numpy as np
import obspy
from header_scanner import scan
from geometry import header_grid
from native_decode import decode_record
from invented import int_record
from strict import Reject


class NativeFormatTests(unittest.TestCase):
    def test_invented_steim2_individual_records(self):
        values = np.arange(1000, dtype=np.int32)
        trace = obspy.Trace(values, {'network': 'NZ', 'station': 'ABCD', 'location': '', 'channel': 'HHE',
                                    'starttime': obspy.UTCDateTime(1970, 1, 1), 'sampling_rate': 100})
        buffer = io.BytesIO(); trace.write(buffer, format='MSEED', encoding='STEIM2', reclen=256)
        raw = buffer.getvalue(); ledger = scan(raw)
        self.assertEqual(ledger['disposition'], 'supported')
        self.assertGreater(ledger['record_count'], 1)
        observed = []
        for d in ledger['records']:
            piece = raw[d['offset']:d['offset'] + d['length']]
            self.assertEqual(d['encoding'], 11)
            observed.extend(decode_record(piece, d, *header_grid(d)).tolist())
        self.assertEqual(observed, values.tolist())

    def test_float_payload_bits_and_nonfinite_overdelivery(self):
        for encoding, dtype, count in ((4, '>f4', 40), (5, '>f8', 20)):
            raw = bytearray(int_record(count=count)); raw[52] = encoding
            values = np.arange(count, dtype=dtype); values[-1] = np.nan
            raw[64:64 + values.nbytes] = values.tobytes()
            raw = bytes(raw); d = scan(raw)['records'][0]
            actual = decode_record(raw, d, *header_grid(d))
            self.assertEqual(actual.dtype.itemsize, values.dtype.itemsize)
            self.assertTrue(np.array_equal(actual[:-1], values[:-1]))
            self.assertTrue(np.isnan(actual[-1]))

    def test_explicit_b100_rate_uses_exact_header_float(self):
        raw = bytearray(int_record(count=40)); raw[39] = 3
        struct.pack_into('>H', raw, 44, 80)
        struct.pack_into('>HHBBBB', raw, 48, 1000, 56, 3, 1, 8, 0)
        struct.pack_into('>HHfBBBB', raw, 56, 100, 68, 0.1, 1, 0, 0, 0)
        struct.pack_into('>HHBbBB', raw, 68, 1001, 0, 100, -10, 0, 0)
        struct.pack_into('>' + 'i' * 40, raw, 80, *range(40))
        raw = bytes(raw); d = scan(raw)['records'][0]
        start, rate = header_grid(d)
        self.assertEqual(rate.numerator, 13421773)
        self.assertEqual(rate.denominator, 134217728)
        self.assertEqual(start, -10_000)
        self.assertEqual(decode_record(raw, d, start, rate).tolist(), list(range(40)))

    def test_memory_error_is_fatal_not_declared_decode_unknown(self):
        raw = int_record(); d = scan(raw)['records'][0]
        with patch('obspy.read', side_effect=MemoryError('invented')):
            with self.assertRaises(MemoryError): decode_record(raw, d, *header_grid(d))


if __name__ == '__main__': unittest.main()

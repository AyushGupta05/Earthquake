import io
import struct
import unittest
from unittest.mock import patch
import warnings
import zipfile
import numpy as np
from obspy import Stream, Trace, UTCDateTime
import obspy
from obspy.io.mseed import InternalMSEEDWarning
from header_audit import inspect_headers, inspect_member, parse_metadata, select_members, ROOT


class HeaderAuditTests(unittest.TestCase):
    def metadata(self, rate=100):
        return parse_metadata(f'AK TEST -- BHZ 60 -150 10 {rate} 1000 DU/M/S\n')

    def segment(self, start, n=100, rate=100):
        trace = Trace(np.arange(n, dtype=np.int32))
        trace.stats.update(dict(network='AK', station='TEST', location='', channel='BHZ',
                                starttime=UTCDateTime(start), sampling_rate=rate))
        return trace

    def inspect(self, traces, metadata=None):
        output = io.BytesIO()
        Stream(traces).write(output, format='MSEED')
        return inspect_headers(output.getvalue(), metadata if metadata is not None else self.metadata())

    def test_headonly_preserves_count_without_samples(self):
        result = self.inspect([self.segment(0)])
        self.assertEqual(result['header_declared_samples'], 100)
        self.assertEqual(result['header_rate_segments'], {'100.0': 1})
        self.assertEqual(result['matched_channel_units'], {'DU/M/S': 1})
        self.assertFalse(result['missing_metadata'])

    def test_blank_location_and_duplicate_metadata(self):
        rows = self.metadata()
        rows['AK.TEST..BHZ'] *= 2
        result = self.inspect([self.segment(0)], rows)
        self.assertEqual(result['duplicate_metadata_ids'], ['AK.TEST..BHZ'])

    def test_gap_uses_exclusive_endpoint(self):
        result = self.inspect([self.segment(0), self.segment(2)])
        self.assertEqual(result['gaps'], [{'id': 'AK.TEST..BHZ', 'seconds': 1.0}])

    def test_overlap_union_and_nested_segment(self):
        result = self.inspect([self.segment(0, 1000), self.segment(2), self.segment(11)])
        self.assertEqual(result['gaps'], [{'id': 'AK.TEST..BHZ', 'seconds': 1.0}])
        self.assertEqual(result['overlaps'], [{'id': 'AK.TEST..BHZ', 'seconds': 1.0}])

    def test_rate_mismatch_and_unmatched(self):
        result = self.inspect([self.segment(0)], self.metadata(50))
        self.assertEqual(len(result['rate_mismatches']), 1)
        result = self.inspect([self.segment(0)], {})
        self.assertEqual(result['missing_metadata'], ['AK.TEST..BHZ'])

    def test_reject_invalid_metadata(self):
        for rate in ('nan', '0', '-1'):
            with self.assertRaises(ValueError): self.metadata(rate)
        with self.assertRaises(ValueError): parse_metadata('bad row')

    def test_release_name_pairing_and_rejection(self):
        dat = ROOT+'channel_files/ak_test.dat'
        seed = ROOT+'miniseed/ak_test_replay.seed'
        metadata, seeds = select_members([ROOT, dat, seed], expected_events=1)
        self.assertEqual(metadata, {'ak_test': dat})
        self.assertEqual(seeds, {'ak_test': seed})
        for names in [[dat,seed,seed], [dat], [dat,seed.replace('_replay.seed','.seed')],
                      [dat,seed.replace('ak_test','other')],
                      [dat.replace('ak_test','nested/ak_test'),seed]]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                select_members(names, expected_events=1)

    def test_reader_contract_and_reject_unexpected_decoding(self):
        reader = obspy.read
        with patch('header_audit.obspy.read', wraps=reader) as mocked:
            self.inspect([self.segment(0)])
        self.assertEqual(mocked.call_args.kwargs, {'format':'MSEED','headonly':True})
        with patch('header_audit.obspy.read', return_value=Stream([self.segment(0)])):
            with self.assertRaisesRegex(ValueError, 'decoded samples'):
                inspect_headers(b'synthetic mocked input', self.metadata())

    def test_partial_headers_with_reader_warning_are_rejected(self):
        reader = obspy.read
        def partial_reader(*args, **kwargs):
            warnings.warn('Last reclen exceeds buflen, skipping', InternalMSEEDWarning)
            return reader(*args, **kwargs)
        with patch('header_audit.obspy.read', side_effect=partial_reader):
            with self.assertRaisesRegex(ValueError, 'header audit incomplete.*skipping'):
                self.inspect([self.segment(0)])

    def test_complete_zip_member_crc_checked_before_header_read(self):
        wave = io.BytesIO()
        Stream([self.segment(0)]).write(wave, format='MSEED')
        output = io.BytesIO()
        dat = ROOT+'channel_files/fixture.dat'
        seed = ROOT+'miniseed/fixture_replay.seed'
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as archive:
            archive.writestr(dat,'AK TEST -- BHZ 60 -150 10 100 1000 DU/M/S\n')
            archive.writestr(seed,wave.getvalue())
        original = output.getvalue()
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            result = inspect_member(archive,seed,dat)
            self.assertEqual(result['header_declared_samples'],100)
            info = archive.getinfo(seed)
            self.assertEqual(result['seed_crc32'],info.CRC)
            self.assertEqual(result['metadata_crc32'],archive.getinfo(dat).CRC)
            offset = info.header_offset
        # Corrupt only stored member bytes, leave its central CRC unchanged.
        name_bytes,extra_bytes = struct.unpack_from('<HH',original,offset+26)
        payload = offset+30+name_bytes+extra_bytes
        damaged = bytearray(original);damaged[payload+100] ^= 1
        with zipfile.ZipFile(io.BytesIO(damaged)) as archive:
            with patch('header_audit.inspect_headers') as headers:
                with self.assertRaises(zipfile.BadZipFile): inspect_member(archive,seed,dat)
                headers.assert_not_called()


if __name__ == '__main__':
    unittest.main()

"""Invented headers and finite padding only; no vendor encoder/decoder."""

import ast
import hashlib
import json
import math
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import scanner


def record(*, endian=">", exponent=8, encoding=10, word_order=1, npts=0,
           date=(2024, 60, 1, 2, 3, 4567), station=b"ABC  ", location=b"  ",
           channel=b"HHZ", network=b"NZ", sequence=b"000001", quality=b"D",
           reserved=b" ", factor=1, multiplier=-2, flags=(1, 2, 4),
           correction=-123, unused=0, optional=(), data_offset=None):
    length = 1 << exponent
    raw = bytearray(length)
    raw[:20] = sequence + quality + reserved + station + location + channel + network
    kinds = (1000,) + tuple(optional)
    offsets = []
    cursor = 48
    for kind in kinds:
        offsets.append(cursor)
        cursor += {100: 12, 1000: 8, 1001: 8}[kind]
    if data_offset is None:
        data_offset = cursor
    year, day, hour, minute, second, fraction = date
    struct.pack_into(endian + "HHBBBBHHhhBBBBiHH", raw, 20,
                     year, day, hour, minute, second, unused, fraction, npts,
                     factor, multiplier, *flags, len(kinds), correction,
                     data_offset, 48)
    for i, (kind, offset) in enumerate(zip(kinds, offsets)):
        next_offset = offsets[i + 1] if i + 1 < len(offsets) else 0
        struct.pack_into(endian + "HH", raw, offset, kind, next_offset)
        if kind == 1000:
            struct.pack_into("BBBB", raw, offset + 4, encoding, word_order, exponent, 9)
        elif kind == 100:
            struct.pack_into(endian + "fBBBB", raw, offset + 4, 100.5, 128, 1, 2, 3)
        else:
            struct.pack_into("BbBB", raw, offset + 4, 99, -17, 4, 5)
    return bytes(raw)


def changed(raw, offset, fmt, *values):
    b = bytearray(raw)
    struct.pack_into(fmt, b, offset, *values)
    return bytes(b)


class ScannerTests(unittest.TestCase):
    def unknown(self, raw, reason=None, ordinal=0):
        result = scanner.scan(raw)
        self.assertEqual(result["disposition"], "unknown")
        if reason:
            self.assertEqual(result["reason"], reason)
        self.assertEqual(result["record_count"], 0)
        self.assertEqual(result["advertised_samples"], 0)
        self.assertEqual(result["records"], [])
        self.assertFalse(result["header_layout_count_ledger_supported"])
        self.assertEqual(result["failure_ordinal"], ordinal)
        self.false_claims(result)
        self.assertLess(len(json.dumps(result)), 1100)
        return result

    def false_claims(self, result):
        for name in scanner._FALSE_CLAIMS:
            self.assertIs(result[name], False)

    def test_basic_literal_private_descriptor(self):
        raw = record(npts=7)
        result = scanner.scan(raw)
        self.assertEqual(result["disposition"], "supported")
        self.assertEqual(result["record_count"], 1)
        self.assertEqual(result["advertised_samples"], 7)
        self.assertEqual(result["body_bytes"], 256)
        self.assertEqual(result["body_sha256"], hashlib.sha256(raw).hexdigest())
        row = result["records"][0]
        self.assertEqual(row["nslc"], ["NZ", "ABC", "", "HHZ"])
        self.assertEqual(row["date"], [2024, 60, 1, 2, 3, 4567])
        self.assertEqual(row["rate"], [1, -2])
        self.assertEqual(row["flags"], [1, 2, 4])
        self.assertEqual(row["correction"], -123)
        self.assertEqual(row["b1000_reserved"], 9)
        self.false_claims(result)

    def test_input_builtin_no_hooks(self):
        class EvilBytes(bytes):
            def __len__(self):
                raise AssertionError("subclass hook used")
        class EvilObject:
            def __len__(self):
                raise AssertionError("object hook used")
        for raw in (None, True, 1, "text", bytearray(256), memoryview(b"x"),
                    EvilBytes(b"x"), EvilObject(), [], {}):
            with self.subTest(type=type(raw).__name__):
                self.unknown(raw, "input_type", None)

    def test_empty_and_raw_body_caps(self):
        self.unknown(b"", "empty", None)
        self.unknown(b"x" * (scanner.MAX_BODY_BYTES + 1), "body_byte_cap", None)
        result = self.unknown(b"x" * scanner.MAX_BODY_BYTES, "literal_header")
        self.assertEqual(result["body_bytes"], scanner.MAX_BODY_BYTES)

    def test_truncated_and_trailing_bytes_no_partial(self):
        for raw in (b"x", b"x" * 47, record()[:48], record()[:-1]):
            with self.subTest(length=len(raw)):
                self.unknown(raw)
        self.unknown(record() + b"x", "truncated_header", 1)
        self.unknown(record() + b"x" * 256, "literal_header", 1)

    def test_min_max_record_lengths(self):
        for exponent in (8, 20):
            with self.subTest(exponent=exponent):
                row = scanner.scan(record(exponent=exponent))["records"][0]
                self.assertEqual(row["length"], 1 << exponent)
        for exponent in (0, 7, 21, 255):
            self.unknown(changed(record(), 54, "B", exponent))

    def test_individual_counts_encodings_word_orders(self):
        body = b"".join(record(encoding=e, word_order=i % 2, npts=i + 1)
                        for i, e in enumerate((1, 3, 4, 5, 10, 11)))
        result = scanner.scan(body)
        self.assertEqual(result["advertised_samples"], 21)
        self.assertEqual([r["offset"] for r in result["records"]], [256*i for i in range(6)])
        self.assertEqual([r["npts"] for r in result["records"]], list(range(1, 7)))
        self.assertEqual([r["encoding"] for r in result["records"]], [1, 3, 4, 5, 10, 11])
        self.assertEqual([r["word_order"] for r in result["records"]], [0, 1, 0, 1, 0, 1])
        self.false_claims(result)

    def test_zero_counts_and_zero_payload_steim_no_claim(self):
        for encoding in (1, 10, 11):
            result = scanner.scan(record(encoding=encoding, npts=0, data_offset=256))
            self.assertEqual(result["record_count"], 1)
            self.assertEqual(result["advertised_samples"], 0)
        result = scanner.scan(record(encoding=11, npts=65535, data_offset=256))
        self.assertEqual(result["disposition"], "supported")
        self.assertIs(result["payload_admission_verified"], False)

    def test_fixed_width_capacity_exact_one_over(self):
        for encoding, width in ((1, 2), (3, 4), (4, 4), (5, 8)):
            count = 200 // width
            with self.subTest(encoding=encoding):
                self.assertEqual(scanner.scan(record(encoding=encoding, npts=count))["disposition"], "supported")
                self.unknown(record(encoding=encoding, npts=count + 1))

    def test_encoding_and_payload_word_order_rejected_per_record(self):
        for value in (0, 2, 12, 255):
            self.unknown(record() + record(encoding=value), ordinal=1)
        for value in (2, 255):
            self.unknown(record() + record(word_order=value), ordinal=1)

    def test_little_endian_and_independent_payload_order(self):
        for endian, payload_order in (("<", 1), (">", 0)):
            result = scanner.scan(record(endian=endian, word_order=payload_order))
            self.assertEqual(result["disposition"], "supported")
            self.assertEqual(result["records"][0]["endian"], "little" if endian == "<" else "big")
            self.assertEqual(result["records"][0]["word_order"], payload_order)

    def test_optional_layouts_and_arbitrary_order(self):
        for endian in (">", "<"):
            for optional in ((100,), (1001,), (100, 1001), (1001, 100)):
                row = scanner.scan(record(endian=endian, optional=optional))["records"][0]
                if 100 in optional:
                    self.assertEqual(row["b100"], [100.5, 128, 1, 2, 3])
                if 1001 in optional:
                    self.assertEqual(row["b1001"], [99, -17, 4, 5])
        # Explicit 1000 can come last: rotate the small blockette layouts.
        b = bytearray(record(optional=(100,)))
        struct.pack_into(">HHfBBBB", b, 48, 100, 60, 12.5, 3, 0, 0, 0)
        struct.pack_into(">HHBBBB", b, 60, 1000, 0, 10, 1, 8, 0)
        row = scanner.scan(bytes(b))["records"][0]
        self.assertEqual(row["b100"][0], 12.5)

    def test_rate_and_timing_quality_profile(self):
        for value in (0.0, -1.0, math.inf, -math.inf, math.nan):
            self.unknown(changed(record(optional=(100,)), 60, ">f", value))
        self.assertEqual(scanner.scan(changed(record(optional=(1001,)), 60, "B", 100))["disposition"], "supported")
        for quality in (101, 255):
            self.unknown(changed(record(optional=(1001,)), 60, "B", quality))

    def test_sequence_quality_reserved(self):
        for kwargs in ({"sequence": b"00000A"}, {"sequence": b"      "},
                       {"quality": b"V"}, {"quality": b" "}, {"reserved": b"0"}):
            self.unknown(record(**kwargs), "literal_header")
        for quality in (b"D", b"R", b"Q", b"M"):
            self.assertEqual(scanner.scan(record(quality=quality))["disposition"], "supported")

    def test_literal_padding_and_characters(self):
        for kwargs in ({"station": b" ABC "}, {"station": b"A B  "},
                       {"station": b"abc  "}, {"station": b"     "},
                       {"station": b"AB\xff  "}, {"location": b" A"},
                       {"channel": b"HH "}, {"channel": b"H-Z"},
                       {"network": b"  "}, {"network": b"N "}):
            if kwargs == {"network": b"N "}:
                self.assertEqual(scanner.scan(record(**kwargs))["records"][0]["nslc"][0], "N")
            else:
                self.unknown(record(**kwargs), "literal_header")
        result = scanner.scan(record(station=b"A1B2C", location=b"02", channel=b"HN1"))
        self.assertEqual(result["records"][0]["nslc"], ["NZ", "A1B2C", "02", "HN1"])

    def test_dates_calendar_endpoints_and_leap_seconds(self):
        valid = ((1900, 365, 23, 59, 59, 9999), (2000, 366, 0, 0, 0, 0),
                 (2100, 365, 0, 0, 0, 0))
        invalid = ((1899, 1, 0, 0, 0, 0), (2101, 1, 0, 0, 0, 0),
                   (1900, 366, 0, 0, 0, 0), (2100, 366, 0, 0, 0, 0),
                   (2024, 0, 0, 0, 0, 0), (2024, 367, 0, 0, 0, 0),
                   (2024, 1, 24, 0, 0, 0), (2024, 1, 0, 60, 0, 0),
                   (2024, 1, 0, 0, 60, 0), (2024, 1, 0, 0, 0, 10000))
        for date in valid:
            self.assertEqual(scanner.scan(record(date=date))["disposition"], "supported")
        for date in invalid:
            self.unknown(record(date=date))

    def test_raw_fields_no_timestamp_conversion(self):
        row = scanner.scan(record(factor=-32768, multiplier=32767,
                                  flags=(255, 255, 255), correction=-2147483648,
                                  unused=255))["records"][0]
        self.assertEqual(row["rate"], [-32768, 32767])
        self.assertEqual(row["flags"], [255, 255, 255])
        self.assertEqual(row["correction"], -2147483648)
        self.assertEqual(row["date_unused"], 255)
        self.assertFalse(any("timestamp" in key or "time_ns" in key for key in row))

    def test_missing_duplicate_unknown_and_declared_count(self):
        self.unknown(changed(record(), 48, ">H", 1001))
        self.unknown(record(optional=(100, 100)))
        self.unknown(record(optional=(1001, 1001)))
        self.unknown(changed(record(optional=(1001,)), 56, ">H", 1000))
        self.unknown(changed(record(), 48, ">H", 2000))
        for count in (0, 2, 16, 17, 255):
            self.unknown(changed(record(), 39, "B", count))

    def test_chain_self_backward_overlap_outside_data_record_and_body(self):
        for next_offset in (48, 49, 55, 255, 256, 65535):
            self.unknown(changed(record(optional=(1001,)), 50, ">H", next_offset))
        for data_offset in (0, 47, 48, 55, 257, 65535):
            self.unknown(changed(record(), 44, ">H", data_offset))
        for first in (0, 47, 253, 256, 65535):
            self.unknown(changed(record(), 46, ">H", first))
        # A 1000 reached only across the first record must not certify it.
        body = changed(record(), 46, ">H", 304) + record()
        body = changed(body, 44, ">H", 312)
        self.unknown(body)

    def test_record_extent_revalidation_when_1000_last(self):
        b = bytearray(record(exponent=9, optional=(100,)))
        struct.pack_into(">HHfBBBB", b, 48, 100, 300, 12.5, 0, 0, 0, 0)
        struct.pack_into(">HHBBBB", b, 300, 1000, 0, 10, 1, 8, 0)
        struct.pack_into(">H", b, 44, 400)
        self.unknown(bytes(b))

    def test_ambiguous_endian_complete_candidates(self):
        b = bytearray(record(exponent=11, date=(2056, 257, 0, 0, 0, 0), data_offset=1028))
        b[46:48] = b"\x01\x02"  # 258 big, 513 little.
        struct.pack_into(">HHBBBB", b, 258, 1000, 0, 10, 1, 11, 0)
        struct.pack_into("<HHBBBB", b, 513, 1000, 0, 10, 0, 11, 0)
        self.unknown(bytes(b), "ambiguous_endian")

    def test_uniform_length_and_header_endian(self):
        self.unknown(record() + record(exponent=9), "mixed_layout", 1)
        self.unknown(record() + record(endian="<"), "mixed_layout", 1)

    def test_sample_cap_exact_and_over(self):
        whole, remainder = divmod(scanner.MAX_SAMPLES, 65535)
        body = record(npts=65535) * whole + record(npts=remainder)
        result = scanner.scan(body)
        self.assertEqual(result["advertised_samples"], scanner.MAX_SAMPLES)
        self.unknown(body + record(npts=1), "sample_cap", whole + 1)

    def test_record_cap_and_body_geometry(self):
        body = record() * scanner.MAX_RECORDS
        self.assertEqual(len(body), scanner.MAX_BODY_BYTES)
        result = scanner.scan(body)
        self.assertEqual(result["record_count"], scanner.MAX_RECORDS)
        self.assertLessEqual(len(scanner._canonical(result)), scanner.MAX_OUTPUT_BYTES)
        self.unknown(body + record(), "body_byte_cap", None)
        with patch.object(scanner, "MAX_RECORDS", 2):
            self.unknown(record() * 3, "record_cap", 2)

    def test_output_cap_whole_result_boundary(self):
        raw = record()
        needed = len(scanner._canonical(scanner.scan(raw)))
        with patch.object(scanner, "MAX_OUTPUT_BYTES", needed):
            self.assertEqual(scanner.scan(raw)["disposition"], "supported")
        with patch.object(scanner, "MAX_OUTPUT_BYTES", needed - 1):
            self.unknown(raw, "output_cap")
        with patch.object(scanner, "MAX_OUTPUT_BYTES", 100):
            self.unknown(raw, "output_cap")

    def test_privacy_scalar_types_and_no_mutable_alias(self):
        raw = record(optional=(100, 1001)) * 2
        first = scanner.scan(raw)
        def walk(value):
            self.assertIn(type(value), (dict, list, str, int, float, bool, type(None)))
            if type(value) is dict:
                for key, item in value.items():
                    self.assertIs(type(key), str)
                    walk(item)
            elif type(value) is list:
                for item in value:
                    walk(item)
            elif type(value) is float:
                self.assertTrue(math.isfinite(value))
        walk(first)
        first["records"][0]["nslc"][0] = "XX"
        first["records"][0]["b100"][0] = 0
        self.assertEqual(first["records"][1]["nslc"][0], "NZ")
        self.assertEqual(scanner.scan(raw)["records"][0]["b100"][0], 100.5)

    def test_no_io_vendor_or_dynamic_imports(self):
        tree = ast.parse(Path(scanner.__file__).read_text())
        names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                 for alias in node.names}
        self.assertEqual(names, {"hashlib", "json", "math", "struct"})
        self.assertFalse(any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree)))
        banned = {"open", "exec", "eval", "__import__", "read", "read_bytes", "write", "seek"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
                self.assertNotIn(name, banned)


if __name__ == "__main__":
    unittest.main()

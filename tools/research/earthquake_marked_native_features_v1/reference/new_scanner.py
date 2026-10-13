"""Pure, narrow MiniSEEDv2 header ledger; never a payload admission gate."""

import hashlib
import json
import math
import struct

MAX_BODY_BYTES = 8_388_608
MAX_RECORDS = 32_768
MAX_SAMPLES = 8_000_000
MAX_OUTPUT_BYTES = 16_777_216
MAX_RECORD_LENGTH = 1_048_576
_BLOCK_LENGTHS = {100: 12, 1000: 8, 1001: 8}
_FIXED_WIDTHS = {1: 2, 3: 4, 4: 4, 5: 8}
_ENCODINGS = frozenset((1, 3, 4, 5, 10, 11))
_FALSE_CLAIMS = (
    "payload_admission_verified", "raw_record_timing_verified",
    "decompression_admission_verified", "hard_RSS_verified",
    "physical_calibration_verified", "waveform_coverage_verified",
    "model_input_verified", "novelty_verified",
)


class _InvalidHeader(Exception):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _result(reason, size, digest, ordinal=None, records=None, samples=0):
    supported = reason == "supported"
    result = {
        "disposition": "supported" if supported else "unknown",
        "reason": reason,
        "header_layout_count_ledger_supported": supported,
        "body_bytes": size,
        "body_sha256": digest,
        "failure_ordinal": ordinal,
        "record_count": len(records) if supported else 0,
        "advertised_samples": samples if supported else 0,
        "records": records if supported else [],
    }
    result.update({key: False for key in _FALSE_CLAIMS})
    return result


def _literal(field, minimum, maximum):
    trimmed = field.rstrip(b" ")
    if not minimum <= len(trimmed) <= maximum:
        raise _InvalidHeader
    if any(not (48 <= c <= 57 or 65 <= c <= 90) for c in trimmed):
        raise _InvalidHeader
    return trimmed.decode("ascii")


def _identity(raw, start):
    if (any(not 48 <= c <= 57 for c in raw[start:start + 6])
            or raw[start + 6] not in b"DRQM" or raw[start + 7] != 32):
        raise _InvalidHeader
    return [
        _literal(raw[start + 18:start + 20], 1, 2),
        _literal(raw[start + 8:start + 13], 1, 5),
        _literal(raw[start + 13:start + 15], 0, 2),
        _literal(raw[start + 15:start + 18], 3, 3),
    ]


def _candidate(raw, start, prefix):
    (year, day, hour, minute, second, unused, fraction, npts,
     factor, multiplier, activity, io, quality_flags, count,
     correction, data_offset, first_block) = struct.unpack_from(
        prefix + "HHBBBBHHhhBBBBiHH", raw, start + 20)
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    if not (1900 <= year <= 2100 and 1 <= day <= (366 if leap else 365)
            and hour <= 23 and minute <= 59 and second <= 59
            and fraction <= 9999 and 1 <= count <= 16
            and 48 <= first_block and data_offset >= 48):
        raise _InvalidHeader

    limit = min(len(raw) - start, MAX_RECORD_LENGTH)
    cursor = first_block
    previous_end = 48
    blocks = {}
    extents = []
    length = None
    encoding = word_order = reserved1000 = None
    while cursor:
        if (len(extents) >= 16 or cursor < previous_end
                or cursor + 4 > limit or cursor + 4 > data_offset):
            raise _InvalidHeader
        kind, next_block = struct.unpack_from(prefix + "HH", raw, start + cursor)
        block_length = _BLOCK_LENGTHS.get(kind)
        if block_length is None or kind in blocks:
            raise _InvalidHeader
        end = cursor + block_length
        if end > limit or end > data_offset:
            raise _InvalidHeader
        if kind == 1000:
            encoding, word_order, exponent, reserved1000 = struct.unpack_from(
                "BBBB", raw, start + cursor + 4)
            if (encoding not in _ENCODINGS or word_order not in (0, 1)
                    or not 8 <= exponent <= 20):
                raise _InvalidHeader
            length = 1 << exponent
            if length > len(raw) - start or data_offset > length:
                raise _InvalidHeader
            limit = length
            blocks[kind] = True
        elif kind == 100:
            rate = struct.unpack_from(prefix + "f", raw, start + cursor + 4)[0]
            if not math.isfinite(rate) or rate <= 0:
                raise _InvalidHeader
            blocks[kind] = [rate, *raw[start + cursor + 8:start + end]]
        else:
            timing, microsecond, reserved, frames = struct.unpack_from(
                "BbBB", raw, start + cursor + 4)
            if timing > 100:
                raise _InvalidHeader
            blocks[kind] = [timing, microsecond, reserved, frames]
        extents.append((cursor, end))
        if next_block and next_block < end:
            raise _InvalidHeader
        previous_end = end
        cursor = next_block

    if (length is None or len(extents) != count
            or any(end > length or end > data_offset for _, end in extents)):
        raise _InvalidHeader
    if encoding in _FIXED_WIDTHS and npts * _FIXED_WIDTHS[encoding] > length - data_offset:
        raise _InvalidHeader
    # STEIM recognition deliberately adds no packing or payload-capacity claim.
    return {
        "offset": start, "length": length,
        "endian": "big" if prefix == ">" else "little",
        "sequence": raw[start:start + 6].decode("ascii"),
        "quality": chr(raw[start + 6]),
        "date": [year, day, hour, minute, second, fraction],
        "date_unused": unused, "npts": npts,
        "rate": [factor, multiplier],
        "flags": [activity, io, quality_flags], "correction": correction,
        "data_offset": data_offset, "blockette_offset": first_block,
        "blockette_count": count, "encoding": encoding,
        "word_order": word_order, "b1000_reserved": reserved1000,
        "b100": blocks.get(100), "b1001": blocks.get(1001),
    }


def scan(raw):
    """Return a whole-body header ledger or a bounded unknown; builtin bytes only."""
    if type(raw) is not bytes:
        return _result("input_type", None, None)
    size = len(raw)
    if not size:
        return _result("empty", 0, hashlib.sha256(raw).hexdigest())
    if size > MAX_BODY_BYTES:
        return _result("body_byte_cap", size, None)
    digest = hashlib.sha256(raw).hexdigest()
    records = []
    start = samples = 0
    ledger_bytes = 2
    uniform = None
    while start < size:
        ordinal = len(records)
        if ordinal >= MAX_RECORDS:
            return _result("record_cap", size, digest, ordinal)
        if size - start < 48:
            return _result("truncated_header", size, digest, ordinal)
        try:
            nslc = _identity(raw, start)
        except _InvalidHeader:
            return _result("literal_header", size, digest, ordinal)
        candidates = []
        for prefix in (">", "<"):
            try:
                candidates.append(_candidate(raw, start, prefix))
            except _InvalidHeader:
                pass
        if not candidates:
            return _result("header_structure_unknown", size, digest, ordinal)
        if len(candidates) != 1:
            return _result("ambiguous_endian", size, digest, ordinal)
        record = candidates[0]
        layout = (record["length"], record["endian"])
        if uniform is not None and layout != uniform:
            return _result("mixed_layout", size, digest, ordinal)
        uniform = layout
        samples += record["npts"]
        if samples > MAX_SAMPLES:
            return _result("sample_cap", size, digest, ordinal)
        record["ordinal"] = ordinal
        record["nslc"] = nslc
        ledger_bytes += len(_canonical(record)) + (1 if records else 0)
        if ledger_bytes > MAX_OUTPUT_BYTES:
            return _result("output_cap", size, digest, ordinal)
        records.append(record)
        start += record["length"]
    result = _result("supported", size, digest, records=records, samples=samples)
    # The full result is bounded too; its claim/header overhead is not free.
    if len(_canonical(result)) > MAX_OUTPUT_BYTES:
        return _result("output_cap", size, digest, len(records) - 1)
    return result

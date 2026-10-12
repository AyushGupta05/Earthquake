"""Invented miniSEED2 bytes only; never reads provider data."""
import struct


def int_record(channel='HHE', start_second=0, count=40, rate=10, sequence=1, values=None, correction=0, activity=0, microsecond=0):
    raw = bytearray(256)
    raw[:20] = ('%06dD ABCD   %sNZ' % (sequence, channel)).encode('ascii')
    struct.pack_into('>HHBBBBHHhhBBBBiHH', raw, 20, 1970, 1, 0, 0, start_second, 0, 0, count, rate, 1, activity, 0, 0, 2, correction, 64, 48)
    struct.pack_into('>HHBBBB', raw, 48, 1000, 56, 3, 1, 8, 0)
    struct.pack_into('>HHBbBB', raw, 56, 1001, 0, 100, microsecond, 0, 0)
    if values is None: values = list(range(count))
    struct.pack_into('>' + 'i' * count, raw, 64, *values)
    return bytes(raw)

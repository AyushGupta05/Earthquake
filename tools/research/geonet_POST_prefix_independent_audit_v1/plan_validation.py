"""Exact frozen public projection; external original-selection proof is separate."""
import math
import re
from fractions import Fraction
from strict import Reject, integer, keys, pin

STUDY = 'geonet-original-TRAINDEV65-prefix3-native-POST-v2'
MIN_NS, MAX_NS = -(1 << 63), (1 << 63) - 1
LITERAL = re.compile(r'[A-Z0-9]*\Z')


def literal(value, minimum, maximum):
    if type(value) is not str or not minimum <= len(value) <= maximum or not LITERAL.fullmatch(value):
        raise Reject('literal')


def rational(value):
    if type(value) is not list or len(value) != 2:
        raise Reject('rational')
    numerator = integer(value[0], 1); denominator = integer(value[1], 1)
    if math.gcd(numerator, denominator) != 1:
        raise Reject('unreduced')
    return Fraction(numerator, denominator)


def validate(plan):
    keys(plan, ('study', 'rows', 'batches'))
    if type(plan['study']) is not str or plan['study'] != STUDY:
        raise Reject('study')
    if type(plan['rows']) is not list or len(plan['rows']) != 65 or type(plan['batches']) is not list or len(plan['batches']) != 17:
        raise Reject('denominator')
    partitions = {'TRAIN': 0, 'DEV': 0}; families = {'ENZ': 0, '12Z': 0, None: 0}
    for ordinal, row in enumerate(plan['rows']):
        keys(row, ('ordinal', 'partition', 'batch', 'network', 'station', 'location', 'prefix', 't0_ns', 'pick_ns', 'family', 'nominal_rates'))
        if integer(row['ordinal'], 0, 64) != ordinal or integer(row['batch'], 0, 16) != ordinal // 4:
            raise Reject('row_order')
        if type(row['partition']) is not str or row['partition'] not in partitions:
            raise Reject('partition')
        partitions[row['partition']] += 1
        for field, low, high in (('network', 1, 2), ('station', 1, 5), ('location', 0, 2), ('prefix', 2, 2)):
            literal(row[field], low, high)
        t0 = integer(row['t0_ns'], MIN_NS, MAX_NS)
        integer(t0 - 3_000_000_000, MIN_NS, MAX_NS); integer(t0 + 5_000_000_000, MIN_NS, MAX_NS)
        integer(row['pick_ns'], MIN_NS, MAX_NS)
        family = row['family']
        if family is not None and (type(family) is not str or family not in ('ENZ', '12Z')):
            raise Reject('family')
        families[family] += 1
        rates = row['nominal_rates']
        expected = {row['prefix'] + x for x in family} if family is not None else set()
        keys(rates, expected)
        for value in rates.values(): rational(value)
    if partitions != {'TRAIN': 41, 'DEV': 24} or families != {'ENZ': 47, '12Z': 14, None: 4}:
        raise Reject('fixed_counts')
    total = 0
    for ordinal, batch in enumerate(plan['batches']):
        keys(batch, ('ordinal', 'rows', 'transport', 'body_bytes', 'body_sha256'))
        if integer(batch['ordinal'], 0, 16) != ordinal:
            raise Reject('batch_order')
        if type(batch['rows']) is not list or any(type(v) is not int for v in batch['rows']) or batch['rows'] != list(range(ordinal * 4, min(65, ordinal * 4 + 4))):
            raise Reject('membership')
        if type(batch['transport']) is not str or batch['transport'] not in ('http200', 'no_data', 'error', 'empty'):
            raise Reject('transport')
        if batch['transport'] == 'http200':
            pin({'bytes': batch['body_bytes'], 'sha256': batch['body_sha256']}, 8_388_608)
            integer(batch['body_bytes'], 1, 8_388_608); total += batch['body_bytes']
        elif integer(batch['body_bytes'], 0, 0) != 0 or batch['body_sha256'] is not None:
            raise Reject('nonpositive_pin')
    if total > 142_606_336:
        raise Reject('body_total')
    return plan

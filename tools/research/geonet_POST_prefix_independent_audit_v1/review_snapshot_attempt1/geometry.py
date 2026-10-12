"""Independent integer UTC/rational prefix arithmetic; no producer imports."""
import datetime
import math
from fractions import Fraction
from strict import Reject

NS = 1_000_000_000
EPOCH = datetime.datetime(1970, 1, 1)


def pair(value):
    return [value.numerator, value.denominator]


def ceil(value):
    return -((-value.numerator) // value.denominator)


def header_grid(record):
    """Return interpreted start_ns and exact rational samples/second."""
    if (record['date_unused'] or record['b1000_reserved']
            or (record['b100'] and any(record['b100'][2:]))
            or record['flags'][0] & 0x30
            or (record['b1001'] and record['b1001'][2])):
        raise Reject('reserved_timing')
    year, day, hour, minute, second, fraction = record['date']
    date = datetime.datetime(year, 1, 1) + datetime.timedelta(days=day - 1, hours=hour, minutes=minute, seconds=second)
    delta = date - EPOCH
    start = (delta.days * 86400 + delta.seconds) * NS + fraction * 100_000
    if record['b1001'] is not None:
        start += record['b1001'][1] * 1000
    if not record['flags'][0] & 2:
        start += record['correction'] * 100_000
    if record['b100'] is not None:
        rate = Fraction.from_float(record['b100'][0])
    else:
        factor, multiplier = record['rate']
        if not factor or not multiplier:
            raise Reject('zero_rate')
        rate = (Fraction(factor, 1) if factor > 0 else Fraction(1, -factor)) * (Fraction(multiplier, 1) if multiplier > 0 else Fraction(1, -multiplier))
    if rate <= 0:
        raise Reject('rate')
    return start, rate


def rate_agrees(reported, rate):
    if type(reported) not in (int, float) or not math.isfinite(reported) or reported <= 0:
        return False
    return abs(Fraction.from_float(float(reported)) - rate) <= max(Fraction(1, 10**12), rate / 10**12)


def crop(start, rate, count, left, right):
    period = Fraction(NS, 1) / rate
    low = max(0, ceil(Fraction(left - start, 1) / period))
    high = min(count, ceil(Fraction(right - start, 1) / period))
    low = min(count, low)
    high = max(0, high)
    return low, max(low, high), period


def component_geometry(pieces, left, right):
    """Pieces are local nonempty (start_ns, rate, lo, hi) tuples."""
    if not pieces:
        return 'unknown', 'no_samples', None
    rates = {p[1] for p in pieces}
    if len(rates) != 1:
        return 'incomplete', 'mixed_rate', None
    rate = next(iter(rates))
    period = Fraction(NS, 1) / rate
    tolerance = min(Fraction(1000, 1), period / 100)
    bounds = sorted((Fraction(s) + lo * period, Fraction(s) + (hi - 1) * period) for s, _, lo, hi in pieces)
    first, last = bounds[0][0], bounds[-1][1]
    if not (0 <= first - left < period and 0 < right - last <= period):
        return 'incomplete', 'edge', None
    for (_, previous), (current, _) in zip(bounds, bounds[1:]):
        difference = current - previous - period
        if difference < -tolerance:
            return 'incomplete', 'overlap', None
        if difference > tolerance:
            return 'incomplete', 'gap', None
    origin = bounds[0][0]
    for current, _ in bounds:
        phase = (current - origin) % period
        if min(phase, period - phase) > tolerance:
            return 'incomplete', 'phase', None
    return 'complete', 'complete', (rate, first, last)


def compatible(grids):
    if not grids or any(x is None for x in grids) or len({x[0] for x in grids}) != 1:
        return False
    period = Fraction(NS, 1) / grids[0][0]
    tolerance = min(Fraction(1000), period / 100)
    origin = grids[0][1]
    return all(min((g[1] - origin) % period, period - ((g[1] - origin) % period)) <= tolerance for g in grids)

"""Invented 65-row public-shape projection; no actual events or clocks."""
import copy
from invented import int_record
from strict import sha, canonical


def plan_and_bodies(positive=(0,), raw=None):
    if raw is None:
        raw = b''.join(int_record(channel='HH' + suffix, start_second=start, sequence=i * 2 + j + 1)
                       for i, suffix in enumerate('ENZ12') for j, start in enumerate((0, 4)))
    rows = []
    for ordinal in range(65):
        family = 'ENZ' if ordinal < 47 else '12Z' if ordinal < 61 else None
        rows.append({'ordinal': ordinal, 'partition': 'TRAIN' if ordinal < 41 else 'DEV', 'batch': ordinal // 4,
                     'network': 'NZ', 'station': 'ABCD', 'location': '', 'prefix': 'HH', 't0_ns': 3_000_000_000,
                     'pick_ns': 3_500_000_000, 'family': family,
                     'nominal_rates': {'HH' + suffix: [10, 1] for suffix in family} if family else {}})
    batches = [{'ordinal': n, 'rows': list(range(n * 4, min(65, n * 4 + 4))),
                'transport': 'http200' if n in positive else 'no_data',
                'body_bytes': len(raw) if n in positive else 0, 'body_sha256': sha(raw) if n in positive else None} for n in range(17)]
    return {'study': 'geonet-original-TRAINDEV65-prefix3-native-POST-v2', 'rows': rows, 'batches': batches}, {n: raw for n in positive}


def reader(bodies):
    return lambda ordinal, size: bodies[ordinal]


def input_pins(plan, result):
    a, b = canonical(plan), canonical(result)
    return a, b, {'plan': {'bytes': len(a), 'sha256': sha(a)}, 'producer': {'bytes': len(b), 'sha256': sha(b)}}

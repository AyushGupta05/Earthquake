"""Pure selection and absolute-prefix checks; no network, filtering or filling."""
import collections
import datetime as dt
from fractions import Fraction
import hashlib
import math
import re

VERSION = 'geonet-small-waveform-v1'
NS = 10**9


def stamp_ns(text):
    t = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('timezone required')
    delta = t.astimezone(dt.timezone.utc)-dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    return (delta.days*86400+delta.seconds)*NS+delta.microseconds*1000


def iso(ns):
    if ns % 1000:
        raise ValueError('request time must be exactly representable in microseconds')
    seconds, remainder = divmod(ns, NS)
    t = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)+dt.timedelta(seconds=seconds, microseconds=remainder//1000)
    return t.isoformat().replace('+00:00', 'Z')


def choose(groups, outcomes):
    selected = []
    for lo, hi in ((5.5, 6), (6, 7), (7, math.inf)):
        candidates = [g for g in groups if g['eligible'] and g['mw_min'] >= lo
                      and g['mw_max'] < hi and outcomes.get(g['event_id'], {}).get('status') == 'ok']
        def key(g):
            return (hashlib.sha256((VERSION+'|'+g['event_id']).encode()).hexdigest(), g['event_id'])
        if not candidates:
            continue
        years = [min(g['dates'])[:4] for g in candidates]
        early, late = min(years), max(years)
        first = sorted((g for g in candidates if min(g['dates'])[:4] == early), key=key)
        last = sorted((g for g in candidates if min(g['dates'])[:4] == late), key=key)
        pairs = first[:2] if early == late else [first[0], last[0]]
        for g in pairs:
            eid = g['event_id']; stations = collections.defaultdict(list)
            for p in outcomes[eid]['accepted_picks']:
                if p['network'] == 'NZ':
                    stations[p['station']].append(p)
            earliest = [min(ps, key=lambda p: (stamp_ns(p['time']), p['location'], p['channel'], p['pick_id']))
                        for ps in stations.values()]
            earliest.sort(key=lambda p: (stamp_ns(p['time']), p['station']))
            if not earliest:
                raise ValueError('selected census event has no NZ pick')
            t0 = stamp_ns(earliest[0]['time'])
            targets = []
            for p in earliest[:3]:
                good = bool(re.fullmatch('[A-Z0-9]{1,8}', p['station'])
                            and re.fullmatch('[A-Z0-9]{0,2}', p['location'])
                            and re.fullmatch('[A-Z0-9]{3}', p['channel']))
                targets.append({'network': 'NZ', 'station': p['station'], 'location': p['location'],
                                'prefix': p['channel'][:2], 'pick_ns': stamp_ns(p['time']),
                                'queryable': good, 'unqueryable_reason': None if good else 'invalid_seed_identity'})
            selected.append({'event_id': eid, 'band_lower': lo, 'year': min(g['dates'])[:4],
                             'mw_min': g['mw_min'], 'mw_max': g['mw_max'], 't0_ns': t0, 'stations': targets})
    if len(selected) > 6 or len({e['event_id'] for e in selected}) != len(selected):
        raise ValueError('invalid selected event count')
    return selected


def ceil_fraction(v):
    return -(-v.numerator//v.denominator)


def crop(piece, left, deadline):
    start = piece['start_ns']
    if start >= deadline:
        return None
    rate = piece['sample_rate']
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError('invalid sample rate')
    period = Fraction(NS, 1)/Fraction(str(rate))
    data = piece['data']
    lo = max(0, ceil_fraction(Fraction(left-start, 1)/period))
    hi = min(len(data), ceil_fraction(Fraction(deadline-start, 1)/period))
    if hi <= lo:
        return None
    return {'first': Fraction(start)+lo*period, 'last': Fraction(start)+(hi-1)*period,
            'period': period, 'rate': rate, 'data': data[lo:hi], 'timing_quality': piece.get('timing_quality'),
            'calibration_type': piece.get('calibration_type')}


def component(pieces, left, deadline, expected_rate):
    fragments = [x for p in pieces if (x := crop(p, left, deadline)) is not None]
    fragments.sort(key=lambda p: p['first'])
    if not fragments:
        return {'available': False, 'reason': 'no_prefix_samples', 'samples': 0}
    period = Fraction(NS, 1)/Fraction(str(expected_rate)); tolerance = min(Fraction(1000), period/100)
    gaps = overlaps = 0
    for a, b in zip(fragments, fragments[1:]):
        difference = b['first']-(a['last']+a['period'])
        gaps += difference > tolerance; overlaps += difference < -tolerance
    first, last = fragments[0]['first'], max(p['last'] for p in fragments)
    lattice = all(min((p['first']-first) % period, period-((p['first']-first) % period)) <= tolerance for p in fragments)
    values = [v for p in fragments for v in p['data']]
    finite = all(math.isfinite(v) for v in values)
    rates = all(p['rate'] == expected_rate for p in fragments)
    # Interior rounding tolerance must not admit an entire missing edge sample.
    edges = (0 <= first-left < period and 0 < deadline-last <= period)
    flat = bool(finite and min(values) == max(values))
    longest = 0
    finite_values = [v for v in values if math.isfinite(v)]
    if finite_values:
        extremes = {min(finite_values), max(finite_values)}
        run = 0; prior = None; previous_fragment = None
        for p in fragments:
            # Record boundaries do not break a physical run on a continuous grid.
            if (previous_fragment is None or p['rate'] != previous_fragment['rate']
                    or abs(p['first']-(previous_fragment['last']+previous_fragment['period'])) > tolerance):
                run = 0; prior = None
            for value in p['data']:
                if not math.isfinite(value):
                    run = 0; prior = None; continue
                run = run+1 if value == prior and value in extremes else (1 if value in extremes else 0)
                longest = max(longest, run); prior = value
            previous_fragment = p
    candidate = flat or longest >= 8
    good = finite and rates and edges and lattice and not gaps and not overlaps
    return {'available': good, 'samples': len(values), 'finite': finite, 'sample_rate_matches': rates,
            'edge_coverage': edges, 'gaps': gaps, 'overlaps': overlaps, 'flatline': flat,
            'sample_grid_consistent': lattice, 'first_sample_ns_numerator': first.numerator,
            'first_sample_ns_denominator': first.denominator,
            'longest_prefix_extreme_run': longest, 'clipping_candidate': candidate,
            'clipping_screen_passed': good and not candidate, 'physically_unclipped_verified': False,
            'timing_quality_values': sorted({str(p['timing_quality']) for p in fragments}),
            'calibration_type_values': sorted({str(p['calibration_type']) for p in fragments})}


def compatible_lattices(components, sample_rate):
    if not all(c['available'] for c in components.values()):
        return False
    first = [Fraction(c['first_sample_ns_numerator'], c['first_sample_ns_denominator']) for c in components.values()]
    period = Fraction(NS, 1)/Fraction(str(sample_rate)); tolerance = min(Fraction(1000), period/100)
    return all(min((t-first[0]) % period, period-((t-first[0]) % period)) <= tolerance for t in first)


def triplet(channels, target, left, deadline):
    matching = [c for c in channels if c['network'] == target['network'] and c['station'] == target['station']
                and c['location'] == target['location'] and c['code'].startswith(target['prefix'])
                and (c['start_ns'] is None or c['start_ns'] < deadline)
                and (c['end_ns'] is None or c['end_ns'] > left)]
    chosen = None
    for suffixes in ('ENZ', '12Z'):
        codes = [target['prefix']+s for s in suffixes]
        if all(any(c['code'] == code for c in matching) for code in codes):
            chosen = codes; break
    if chosen is None:
        raise ValueError('missing coherent ENZ or 12Z triplet')
    selected = []
    for code in chosen:
        cc = [c for c in matching if c['code'] == code]
        if len(cc) != 1:
            raise ValueError('ambiguous response epoch')
        c = cc[0]
        if (c.get('channel_start_known', True) is not True
                or c['start_ns'] is None or c['start_ns'] > left
                or (c['end_ns'] is not None and c['end_ns'] < deadline)):
            raise ValueError('response epoch does not span prefix')
        if not all(math.isfinite(c[k]) for k in ('sample_rate', 'dip', 'azimuth')) or c['sample_rate'] <= 0:
            raise ValueError('invalid rate/orientation')
        selected.append(c)
    if len({c['sample_rate'] for c in selected}) != 1:
        raise ValueError('component sample rates differ')
    h1, h2, z = selected
    delta = abs((h1['azimuth']-h2['azimuth']+180) % 360-180)
    if abs(h1['dip']) > 10 or abs(h2['dip']) > 10 or abs(abs(z['dip'])-90) > 10 or abs(delta-90) > 10:
        raise ValueError('triplet orientation invalid')
    return selected

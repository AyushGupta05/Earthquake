"""Offline decoded-trace qualification. No acquisition, merge, response or re-clock."""
from collections import Counter
import datetime as dt
from fractions import Fraction
import io
import math
import warnings

PROTOCOL = 'geonet-archive-precontext-sensitivity-v2'
NS = 10**9
OBJECT_SAMPLE_CAP = 16_000_000
TOTAL_SAMPLE_CAP = 64_000_000
PRECONTEXTS = (0, 1, 3, 5)
HORIZONS = (1, 3, 5)


def availability_mask(available):
    return 'available' if available is True else 'incomplete' if available is False else 'unknown'


def sample_count(stream):
    total = 0
    for trace in stream:
        n = trace.stats.npts
        if type(n) is not int or n < 0:
            raise ValueError('invalid advertised count')
        total += n
        if total > OBJECT_SAMPLE_CAP:
            raise ValueError('advertised sample cap')
    return total


def trace_signature(trace):
    st = trace.stats
    rate = float(st.sampling_rate)
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError('unsupported sample rate')
    n = st.npts
    if type(n) is not int or n < 0 or type(st.starttime.ns) is not int:
        raise ValueError('invalid sample grid')
    return (st.network, st.station, st.location, st.channel, st.starttime.ns, str(rate), n)


def decode(body, read, remaining_samples):
    # Suppress warning text: native/library warnings may embed private identifiers.
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        headers = read(io.BytesIO(body), format='MSEED', headonly=True, details=True)
        count = sample_count(headers)
        if count > remaining_samples:
            raise ValueError('total advertised sample cap')
        header_signatures = Counter(trace_signature(t) for t in headers)
        stream = read(io.BytesIO(body), format='MSEED', details=True)
        if sample_count(stream) != count or Counter(trace_signature(t) for t in stream) != header_signatures:
            raise ValueError('header/full grid disagreement')
        for trace in stream:
            data = trace.data
            if data.ndim != 1 or len(data) != trace.stats.npts or data.dtype.kind not in ('i', 'f') or data.dtype.itemsize > 8:
                raise ValueError('unsupported decoded dtype/count')
        warning_count = len(caught)
    return stream, count, warning_count


def rational(value):
    return {'numerator': value.numerator, 'denominator': value.denominator}


def utc_day(year, doy):
    start = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(days=doy-1)
    if start.year != year:
        raise ValueError('invalid filename day')
    delta = start - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    return (delta.days*86400 + delta.seconds)*NS


def analyze(stream, slot, core):
    expected = tuple(slot['expected_nslc'][k] for k in ('network', 'station', 'location', 'channel'))
    pieces = []
    summaries = []
    observed = Counter()
    rates = set()
    day_start = utc_day(slot['filename_year'], slot['filename_doy'])
    day_end = day_start + 86400*NS
    crossing_count = 0
    for trace in stream:
        signature = trace_signature(trace)
        nslc = signature[:4]
        observed[nslc] += 1
        rate = float(trace.stats.sampling_rate)
        period = Fraction(NS)/Fraction(str(rate))
        first = Fraction(trace.stats.starttime.ns)
        last = first+(trace.stats.npts-1)*period if trace.stats.npts else None
        crossing = bool(last is not None and (first < day_start or last >= day_end))
        crossing_count += crossing
        metadata = getattr(trace.stats, 'mseed', {})
        blkt = metadata.get('blkt1001', {})
        pieces.append({'start_ns': trace.stats.starttime.ns, 'sample_rate': rate, 'data': trace.data,
                       'timing_quality': blkt.get('timing_quality') if hasattr(blkt, 'get') else None,
                       'calibration_type': metadata.get('calibration_type')})
        rates.add(rate)
        summaries.append({'nslc': list(nslc), 'start_ns': trace.stats.starttime.ns,
                          'last_sample_ns': None if last is None else rational(last),
                          'sample_rate': rational(Fraction(str(rate))), 'npts': trace.stats.npts,
                          'filename_day_boundary_crossing': crossing})
    ordered = sorted((p for p in pieces if len(p['data'])), key=lambda p: p['start_ns'])
    gaps = overlaps = 0
    aligned = None
    if len(rates) == 1 and ordered:
        period = Fraction(NS)/Fraction(str(next(iter(rates))))
        tolerance = min(Fraction(1000), period/100)
        aligned = all(min((p['start_ns']-ordered[0]['start_ns']) % period,
                          period-((p['start_ns']-ordered[0]['start_ns']) % period)) <= tolerance for p in ordered)
        for a, b in zip(ordered, ordered[1:]):
            separation = Fraction(b['start_ns'])-(Fraction(a['start_ns'])+len(a['data'])*period)
            gaps += separation > tolerance
            overlaps += separation < -tolerance
    identity_ok = bool(observed) and set(observed) == {expected}
    rate_ok = len(rates) == 1
    # Whole-object NSLC/rate evidence is descriptive and separate from prefix core output.
    # Each horizon receives only its half-open crop; unseen-tail amplitudes cannot enter it.
    precontext_windows = {}
    for context in PRECONTEXTS:
        windows = {}
        left = slot['t0_ns'] - context*NS
        for horizon in HORIZONS:
            deadline = slot['t0_ns'] + horizon*NS
            if not identity_ok:
                result = {'available': False, 'reason': 'literal_nslc_mismatch', 'samples': None}
            elif not rate_ok:
                result = {'available': False, 'reason': 'multiple_observed_rates', 'samples': None}
            else:
                result = core.component(pieces, left, deadline, next(iter(rates)))
            windows[str(horizon)] = {'left_ns': left, 'deadline_ns': deadline,
                                     'target_pick_strictly_before_deadline': slot['pick_ns'] < deadline,
                                     'core': result}
        precontext_windows[str(context)] = windows
    masks = {p: {h: availability_mask(w['core']['available']) for h, w in windows.items()}
             for p, windows in precontext_windows.items()}
    return {'slot_index': slot['slot_index'], 'status': 'decoded', 'literal_identity_matches': identity_ok,
            'observed_rate_consistent': rate_ok, 'metadata_rate_verified': False,
            'observed_nslc': [{'nslc': list(k), 'decoded_trace_count': v} for k, v in sorted(observed.items())],
            'decoded_traces': summaries, 'decoded_sample_grid': {
                'gaps': gaps if aligned is not None else None,
                'overlaps': overlaps if aligned is not None else None,
                'start_lattice_consistent': aligned,
                'empty_trace_count': len(pieces)-len(ordered)},
            'filename_day_boundary_crossing_count': crossing_count,
            'filename_partition_verified': False, 'preserved_t0_ns': slot['t0_ns'],
            'metadata_pick_ns': slot['pick_ns'], 'pick_minus_t0_ns': slot['pick_ns']-slot['t0_ns'],
            # The legacy-shaped view is exactly the five-second V1 contract.
            'windows': precontext_windows['5'], 'precontext_windows': precontext_windows,
            'precontext_masks': masks}


def failed(slot_index, reason):
    windows = {str(p): {str(h): {'core': {'available': None}} for h in HORIZONS} for p in PRECONTEXTS}
    return {'slot_index': slot_index, 'status': 'failed', 'reason': reason,
            'windows': windows['5'], 'precontext_windows': windows,
            'precontext_masks': {str(p): {str(h): 'unknown' for h in HORIZONS} for p in PRECONTEXTS}}


def aggregate(rows):
    return {'slots': 4, 'decoded_slots': sum(r['status'] == 'decoded' for r in rows),
            'failed_slots': sum(r['status'] == 'failed' for r in rows),
            'literal_identity_matching_slots': sum(r.get('literal_identity_matches', False) for r in rows),
            'consistent_observed_rate_slots': sum(r.get('observed_rate_consistent', False) for r in rows),
            'complete_decoded_trace_windows': {str(h): sum(r['windows'][str(h)]['core'].get('available') is True for r in rows) for h in (1, 3, 5)},
            'precontext_window_states': {str(p): {str(h): {
                'denominator': 4,
                **{state: sum(r['precontext_masks'][str(p)][str(h)] == state for r in rows)
                   for state in ('available', 'incomplete', 'unknown')},
                'complete_and_catalogue_pick_before_deadline': sum(
                    r['precontext_windows'][str(p)][str(h)]['core']['available'] is True
                    and r['precontext_windows'][str(p)][str(h)].get('target_pick_strictly_before_deadline') is True
                    for r in rows)} for h in HORIZONS} for p in PRECONTEXTS},
            'filename_boundary_crossing_trace_count': sum(r.get('filename_day_boundary_crossing_count', 0) for r in rows),
            'metadata_rate_verified': False, 'filename_partition_verified': False,
            'response_calibration_verified': False, 'physical_clipping_verified': False,
            'three_component_available_verified': False, 'operational_availability_verified': False,
            'model_improvement_verified': False}

"""Independent, offline native-count replay primitives; no acquisition or fits.

No producer/old-audit imports. Actual-run orchestration remains parent-gated.
Times are integer ns; sample bounds and alignment use exact rational arithmetic.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import hashlib
import io
import math
import os
import errno
from pathlib import Path
import re
import sys
import struct
import tempfile
import urllib.parse
import warnings
import xml.etree.ElementTree as ET

NS = 1_000_000_000
MIB = 1024 * 1024
DECODE_CAP = 64 * MIB
HORIZONS = (1, 3, 5)
PARTITIONS = ('train2003_2014', 'dev2015_2017', 'test2018_2024')
LOWER_BANDS = ('<3.5', '[3.5,4)', '[4,4.5)', '[4.5,5)', '[5,5.5)')
ALL_BANDS = LOWER_BANDS + ('[5.5,6)', '[6,7)', '>=7')
LOWER_SET_SHA = '6ed849d32a6ab180b7ddb4ddbf85d085d6819011fcebe7c093384c0806452d7c'
TERMINAL_ATTEMPT_STATUSES = frozenset(('ok', 'HTTPError', 'URLError', 'ValueError', 'OSError',
                                      'ConnectionResetError', 'ConnectionAbortedError', 'ConnectionRefusedError',
                                      'RemoteDisconnected', 'BrokenPipeError', 'SSLError', 'IncompleteRead', 'BadStatusLine', 'EOFError'))
RESOURCE_ERRNOS = frozenset((errno.ENOMEM, errno.EMFILE, errno.ENFILE, errno.ENOSPC,
                           errno.EFBIG, getattr(errno, 'EDQUOT', errno.ENOSPC), errno.ENOBUFS))
RESPONSE_JOIN_KEYS = ('network', 'station', 'location', 'code', 'start_ns', 'end_ns',
                      'network_start_ns', 'network_end_ns', 'station_start_ns', 'station_end_ns',
                      'channel_start_ns', 'channel_end_ns', 'sample_rate', 'dip', 'azimuth')


class AuditError(ValueError):
    """Contract/provenance error; must not turn into engineering absence."""


class ResourceStop(RuntimeError):
    """Resource interruption: replay incomplete, never scientific absence."""


def raise_if_resource_failure(exc):
    """Do not reinterpret native, wrapped or OS exhaustion as missing data."""
    if isinstance(exc, OSError) and exc.errno in RESOURCE_ERRNOS:
        raise ResourceStop('OS resource interruption') from exc
    if resource_failure_diagnostic(str(exc)):
        raise ResourceStop('wrapped resource diagnostic') from exc


def resource_failure_diagnostic(text):
    """Recognize logged native/wrapped POSIX resource failures, not network errno."""
    diagnostic = str(text).lower()
    codes = {int(value) for value in re.findall(r'\berrno\s+(\d+)\b', diagnostic)}
    phrases = ('timed out', 'timeout', 'memory', 'cap_exceeded', 'limit reached',
               'too many open files', 'no space left on device', 'disk quota exceeded',
               'file too large', 'no buffer space available', 'cannot allocate',
               'malloc failed', 'calloc failed', 'allocation failed', 'failed to allocate', 'unable to allocate')
    return bool(codes & RESOURCE_ERRNOS) or any(phrase in diagnostic for phrase in phrases)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def bounded_body(path, cap, expected=None):
    p = Path(path)
    try:
        if p.is_symlink() or not p.is_file() or p.stat().st_size > cap:
            raise AuditError('file bound or symlink')
        with p.open('rb') as handle:
            data = handle.read(cap + 1)
    except OSError as exc:
        raise_if_resource_failure(exc)
        raise AuditError('artifact access prevents pin reverification') from exc
    if len(data) > cap:
        raise AuditError('file grew beyond bound')
    if expected is not None and expected != {'bytes': len(data), 'sha256': sha(data)}:
        raise AuditError('artifact pin changed')
    return data


def utc_ns(text):
    # Preserve up to9 fractional digits: datetime alone truncates below microseconds.
    match = re.fullmatch(r'(\d{4}-\d\d-\d\d[Tt ]\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?(Z|[+-]\d\d:\d\d)', text)
    if not match:
        raise AuditError('strict timezone-aware timestamp required')
    if match[3] != 'Z' and (int(match[3][1:3]) > 23 or int(match[3][4:6]) > 59):
        raise AuditError('invalid timezone offset components')
    instant = datetime.fromisoformat(match[1] + ('+00:00' if match[3] == 'Z' else match[3]))
    delta = instant.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * NS + int((match[2] or '').ljust(9, '0') or 0)


def request_iso(ns):
    if ns % 1000:
        raise AuditError('request time not representable in microseconds')
    sec, nano = divmod(ns, NS)
    t = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=sec, microseconds=nano // 1000)
    return t.isoformat().replace('+00:00', 'Z')


def list_digest(values):
    return sha(('\n'.join(values) + '\n').encode())


def current_event(source, outcome):
    base = outcome.get('base', {})
    station_picks = defaultdict(list)
    if base.get('status') == 'ok':
        for p in base.get('accepted_picks', []):
            if p['network'] == 'NZ':
                station_picks[p['station']].append(p)
    early = [min(ps, key=lambda p: (utc_ns(p['time']), p['location'], p['channel'], p['pick_id']))
             for ps in station_picks.values()]
    early.sort(key=lambda p: (utc_ns(p['time']), p['station']))
    t0 = utc_ns(early[0]['time']) if early else None
    if t0 is not None and utc_ns(base['nz']['t0_utc']) != t0:
        raise AuditError('original accepted-subset clock changed')
    masks = {str(h): [p['station'] for p in early if utc_ns(p['time']) < t0 + h * NS][:8]
             if t0 is not None else [] for h in HORIZONS}
    targets = []
    for p in early:
        if p['station'] not in masks['5']:
            continue
        queryable = bool(re.fullmatch(r'[A-Z0-9]{1,8}', p['station'])
                         and re.fullmatch(r'[A-Z0-9]{0,2}', p['location'])
                         and re.fullmatch(r'[A-Z0-9]{3}', p['channel']))
        targets.append(dict(network='NZ', station=p['station'], location=p['location'],
                            prefix=p['channel'][:2], pick_ns=utc_ns(p['time']), queryable=queryable,
                            unqueryable_reason=None if queryable else 'invalid_seed_identity'))
    reasons = base.get('reasons', {})
    incomplete = any(reasons.get(k, 0) > 0 for k in
                     ('missing_or_ambiguous_pick_reference', 'invalid_or_naive_pick_time', 'missing_station_identity'))
    return dict(event_id=source['event_id'], candidate_calendar_partition=source['candidate_calendar_partition'],
                Mw_band=source.get('Mw_band', '[5.5,6)' if source['mw'] < 6 else '[6,7)' if source['mw'] < 7 else '>=7'),
                mw=source['mw'], t0_ns=t0, P_status=base.get('status', 'unknown'),
                incomplete_associated_P_structure=incomplete, current_station_masks=masks, targets=targets)


def select96(rows, outcomes, expected_lower_sha=LOWER_SET_SHA):
    if len(rows) != 495 or len({r['event_id'] for r in rows}) != 495:
        raise AuditError('495 distinct source denominator required')
    lower = [r for r in rows if r['source'] == 'new_lower_M']
    tail = [r for r in rows if r['source'] == 'reused_tail']
    if (len(lower), len(tail)) != (346, 149) or list_digest(sorted(r['event_id'] for r in lower)) != expected_lower_sha:
        raise AuditError('frozen source frame changed')
    if set(outcomes) != {r['event_id'] for r in rows}:
        raise AuditError('metadata outcomes lost denominator')
    chosen = [r for r in tail if r['mw'] >= 6]
    if len(chosen) != 60:
        raise AuditError('tail allocation changed')
    for partition in PARTITIONS:
        for band in LOWER_BANDS + ('[5.5,6)',):
            population = lower if band in LOWER_BANDS else tail
            candidates = [r for r in population if r['candidate_calendar_partition'] == partition
                          and (r['Mw_band'] == band if band in LOWER_BANDS else 5.5 <= r['mw'] < 6)]
            if len(candidates) < 2:
                raise AuditError('missing source cell')
            chosen.extend(sorted(candidates, key=lambda r: (
                sha(('geonet-counts-screen-v1|' + partition + '|' + band + '|' + r['event_id']).encode()),
                r['event_id']))[:2])
    if len(chosen) != 96 or len({r['event_id'] for r in chosen}) != 96:
        raise AuditError('96 allocation changed')
    chosen.sort(key=lambda r: (sha(('geonet-counts-query-v1|' + r['event_id']).encode()), r['event_id']))
    return [current_event(r, outcomes[r['event_id']]) for r in chosen]


def envelope(event, target):
    return dict(network=target['network'], station=target['station'], location=target['location'] or '--',
                channel=target['prefix'] + '?', starttime=request_iso(event['t0_ns'] - 5 * NS),
                endtime=request_iso(event['t0_ns'] + 5 * NS))


def query_contract(events, cache):
    """Reconstruct literal frozen GETs/POSTs; cached samples never gate GETs."""
    metadata, batches = [], []
    for event in events:
        for t in event['targets']:
            if t['queryable']:
                env = envelope(event, t)
                metadata.append(dict(slot=event['event_id'] + '|' + t['station'], kind='channel', method='GET',
                                     file=f'channel_{len(metadata):03d}.xml', envelope=env,
                                     url='https://service.geonet.org.nz/fdsnws/station/1/query?' +
                                     urllib.parse.urlencode(dict(env, level='channel', format='xml'))))
    for first in range(0, len(events), 16):
        lines, slots = [], []
        for e in events[first:first + 16]:
            for t in e['targets']:
                slot = e['event_id'] + '|' + t['station']
                if not t['queryable'] or cache.get(slot, {}).get('waveform'):
                    continue
                env = envelope(e, t)
                lines.append(' '.join(env[k] for k in ('network', 'station', 'location', 'channel', 'starttime', 'endtime')))
                slots.append(slot)
        body = '\n'.join(lines) + '\n' if lines else ''
        batches.append(dict(kind='waveform', method='POST', file=f'waveform_{len(batches):02d}.mseed',
                            url='https://service.geonet.org.nz/fdsnws/dataselect/1/query',
                            post_body=body, post_body_sha256=sha(body.encode('ascii')), slots=slots,
                            source_event_count=len(events[first:first + 16])))
    if len(events) != 96 or len(metadata) > 768 or len(batches) != 6:
        raise AuditError('frozen query allocation changed')
    return metadata, batches


def exact_cache_match(query, entry, manifest, event, target, kind):
    """Check original successful GET selection versus later canonical envelope.

    Caller separately verifies original completed source/runtime/receipt pins
    and raw member bytes. A response GET cannot replace a channel GET.
    """
    if kind not in ('waveform', 'response') or manifest.get('completed') is not True:
        raise AuditError('completed original cache evidence required')
    if entry.get('status') != 'ok' or entry.get('http_status') != 200 or not entry.get('bytes'):
        return False
    if entry.get('url') != query.get('url') or entry.get('file') != query.get('file'):
        raise AuditError('original request/cache ledger mismatch')
    expected_kind = 'dataselect' if kind == 'waveform' else 'station'
    if query.get('kind') != expected_kind or (query.get('event_id'), query.get('station')) != (event['event_id'], target['station']):
        return False
    parsed = urllib.parse.urlsplit(query['url'])
    if parsed.scheme != 'https' or parsed.netloc != 'service.geonet.org.nz' or parsed.path != '/fdsnws/' + expected_kind + '/1/query' or parsed.fragment:
        return False
    expected = dict(envelope(event, target), **({'format':'miniseed'} if kind == 'waveform' else {'level':'response','format':'xml'}))
    actual = urllib.parse.parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True)
    if actual != {k:[v] for k,v in expected.items()}:
        return False
    name = entry['file']
    if Path(name).name != name or manifest['files'].get('raw/' + name) != {'bytes':entry['bytes'],'sha256':entry['sha256']}:
        raise AuditError('original body/member/request pins mismatch')
    return True


def verify_completed_files(root, manifest):
    """Verify named completed members only; never follow arbitrary paths."""
    base = Path(root).resolve()
    if manifest.get('completed') is not True or manifest.get('worker_exit_code') != 0 or manifest.get('artifact_pins_incomplete'):
        raise AuditError('completed parent exit0 required')
    if any((base / name).exists() for name in ('outer_interruption.json', 'OUTER_INCOMPLETE.json', 'PROCESS_INCOMPLETE.json')):
        raise AuditError('interruption marker present')
    for name, pin in manifest['files'].items():
        candidate = base / name
        if Path(name).is_absolute() or '..' in Path(name).parts or not candidate.resolve().is_relative_to(base):
            raise AuditError('manifest member escaped')
        if any(parent.is_symlink() for parent in (candidate, *candidate.parents) if parent.is_relative_to(base)):
            raise AuditError('manifest member symlink')
        limit = 4 * MIB if name.startswith('raw/channel_') or name == 'native_worker.log' else 16 * MIB if name.startswith('raw/waveform_') else 32 * MIB
        bounded_body(candidate, limit, pin)
    for name in ('requests.json', 'target_outcomes.json', 'event_outcomes.json', 'summary.json'):
        if name not in manifest['files']:
            raise AuditError('required completed member missing')
    if any(p.name.endswith('.received') for p in (base / 'raw').glob('*')):
        raise AuditError('unreconciled partial sidecar')


def verify_attempts(entries, metadata, batches, manifest):
    expected = metadata + [b for b in batches if b['slots']]
    if len(entries) != len(expected) or len(entries) > 800:
        raise AuditError('request count/order changed')
    outer = manifest.get('outer_elapsed_seconds')
    if type(outer) not in (int, float) or not math.isfinite(outer) or not 0 <= outer <= 7200:
        raise AuditError('whole launch deadline violation')
    total = 0
    prior = None
    for entry, request in zip(entries, expected):
        if any(entry.get(k) != request[k] for k in ('url', 'file', 'method')):
            raise AuditError('request plan mismatch')
        start, elapsed = entry['start_from_outer_seconds'], entry['elapsed_seconds']
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (start, elapsed)):
            raise AuditError('invalid request clocks')
        if start < 0 or elapsed < 0 or elapsed > 20 or start + elapsed > 7190 or (prior is not None and start - prior < 1):
            raise AuditError('recorded request deadline/spacing violation')
        if start + elapsed > outer:
            raise AuditError('request extends beyond completed launch')
        prior = start
        n = entry['bytes']
        if type(n) is not int or n < 0 or n > (4 * MIB if request['method'] == 'GET' else 16 * MIB):
            raise AuditError('returned body cap')
        if entry.get('status') not in TERMINAL_ATTEMPT_STATUSES:
            raise AuditError('interrupted or unknown attempt status')
        if resource_failure_diagnostic(entry.get('error', '')):
            raise AuditError('resource/timeout diagnostic is incomplete')
        if entry.get('status') == 'ok' and entry.get('http_status') != 200:
            raise AuditError('success without HTTP200')
        if request['method'] == 'POST' and (entry.get('post_body_sha256') != request['post_body_sha256'] or
                                            entry.get('post_body_bytes') != len(request['post_body'].encode('ascii'))):
            raise AuditError('literal ASCII POST body differs')
        member = manifest['files'].get('raw/' + request['file'])
        if member != {'bytes': n, 'sha256': entry.get('sha256')}:
            raise AuditError('returned body/member pin mismatch')
        total += n
    if total > 512 * MIB or manifest['response_body_bytes'] != total or manifest['request_attempts'] != len(entries):
        raise AuditError('new returned-body accounting mismatch')
    return dict(attempts=len(entries), returned_new_bytes=total)


def _local_name(element):
    return element.tag.rsplit('}', 1)[-1]


def _single_text(element, name):
    nodes = [c for c in element if _local_name(c) == name]
    if len(nodes) != 1 or nodes[0].text is None:
        return None
    return nodes[0].text.strip()


def _number(element, name):
    try:
        return float(_single_text(element, name))
    except (TypeError, ValueError):
        return math.nan


def stationxml(body):
    if len(body) > 4 * MIB:
        raise AuditError('metadata body cap')
    text = body.decode('utf-8-sig')
    if '\0' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise AuditError('unsafe XML')
    root = ET.fromstring(text)
    if _local_name(root) != 'FDSNStationXML':
        raise ValueError('StationXML root required')
    result = []
    for net in root:
        if _local_name(net) != 'Network':
            continue
        for sta in net:
            if _local_name(sta) != 'Station':
                continue
            for ch in sta:
                if _local_name(ch) != 'Channel':
                    continue
                # Known parent/channel bounds remain useful even if another
                # bound is invalid. Errors matter only for a relevant epoch.
                starts, ends, timestamp_errors = [], [], []
                own_bounds = {label + '_' + field + '_ns': None for label in ('network','station','channel')
                              for field in ('start','end')}
                valid_channel_start = False
                for label, element in (('network',net),('station',sta),('channel',ch)):
                    for field, values in (('startDate',starts),('endDate',ends)):
                        if field not in element.attrib:
                            continue
                        try:
                            parsed = utc_ns(element.attrib[field])
                            values.append(parsed)
                            own_bounds[label + '_' + ('start' if field == 'startDate' else 'end') + '_ns'] = parsed
                            if label == 'channel' and field == 'startDate':
                                valid_channel_start = True
                        except (ValueError, TypeError, OverflowError):
                            timestamp_errors.append(label + '.' + field)
                result.append(dict(network=net.get('code'), station=sta.get('code'), location=ch.get('locationCode', ''),
                                   code=ch.get('code'), start_ns=max(starts) if starts else None,
                                   end_ns=min(ends) if ends else None, channel_start_known=valid_channel_start,
                                   timestamp_errors=timestamp_errors,
                                   sample_rate=_number(ch, 'SampleRate'), dip=_number(ch, 'Dip'), azimuth=_number(ch, 'Azimuth'),
                                   latitude=_number(ch, 'Latitude'), longitude=_number(ch, 'Longitude'),
                                   elevation_m=_number(ch, 'Elevation'), **own_bounds))
    return result


def epoch_triplet(rows, target, left, deadline):
    relevant = [r for r in rows if (r['network'], r['station'], r['location']) ==
                (target['network'], target['station'], target['location']) and isinstance(r['code'], str)
                and r['code'].startswith(target['prefix']) and (r['start_ns'] is None or r['start_ns'] < deadline)
                and (r['end_ns'] is None or r['end_ns'] > left)]
    codes = None
    for suffix in ('ENZ', '12Z'):
        family = [target['prefix'] + c for c in suffix]
        if all(any(r['code'] == c for r in relevant) for c in family):
            codes = family
            break
    if codes is None:
        raise ValueError('missing coherent ENZ or 12Z triplet')
    chosen = []
    for code in codes:
        candidates = [r for r in relevant if r['code'] == code]
        if len(candidates) != 1:
            raise ValueError('ambiguous response epoch')
        row = candidates[0]
        if row.get('timestamp_errors'):
            raise ValueError('invalid relevant epoch timestamp')
        if not row['channel_start_known'] or row['start_ns'] is None or row['start_ns'] > left or (
                row['end_ns'] is not None and row['end_ns'] < deadline):
            raise ValueError('response epoch does not span prefix')
        if not all(math.isfinite(row[k]) for k in ('sample_rate', 'dip', 'azimuth')) or row['sample_rate'] <= 0:
            raise ValueError('invalid rate/orientation')
        if not -90 <= row['dip'] <= 90 or not 0 <= row['azimuth'] <= 360:
            raise ValueError('orientation outside StationXML range')
        chosen.append(row)
    if len({r['sample_rate'] for r in chosen}) != 1:
        raise ValueError('component sample rates differ')
    a, b, z = chosen
    angle = abs((a['azimuth'] - b['azimuth'] + 180) % 360 - 180)
    if max(abs(a['dip']), abs(b['dip']), abs(abs(z['dip']) - 90), abs(angle - 90)) > 10:
        raise ValueError('triplet orientation invalid')
    return chosen


def _ceil(value):
    return -(value.numerator // -value.denominator)


def float_rate_agrees(observed, expected):
    """Only floating evaluation rounding; this never defines a sample clock."""
    observed, expected = float(observed), float(expected)
    return (math.isfinite(observed) and math.isfinite(expected) and observed > 0 and expected > 0
            and abs(observed - expected) <= 2 * max(math.ulp(observed), math.ulp(expected)))


def _cropped(piece, left, deadline):
    start = piece['start_ns']
    if start >= deadline:
        return None
    rate = piece['sample_rate']
    if not math.isfinite(rate) or rate <= 0:
        raise ValueError('invalid sample rate')
    native_rate = piece.get('sample_rate_fraction', Fraction(str(rate)))
    if not isinstance(native_rate, Fraction) or native_rate <= 0 or not float_rate_agrees(rate, native_rate):
        raise ValueError('invalid/inconsistent native sample rate')
    rate = float(native_rate)
    step = Fraction(NS) / native_rate
    first = max(0, _ceil(Fraction(left - start) / step))
    stop = min(len(piece['data']), _ceil(Fraction(deadline - start) / step))
    if first >= stop:
        return None
    return dict(piece=piece, lo=first, hi=stop, first=Fraction(start) + first * step,
                last=Fraction(start) + (stop - 1) * step, step=step, rate=rate)


def prefix_component(pieces, left, deadline, expected_rate):
    segments = [s for p in pieces if (s := _cropped(p, left, deadline)) is not None]
    segments.sort(key=lambda s: s['first'])
    if not segments:
        return dict(available=False, reason='no_prefix_samples', samples=0)
    step = segments[0]['step']
    tol = min(Fraction(1000), step / 100)
    gaps = overlaps = 0
    for a, b in zip(segments, segments[1:]):
        delta = b['first'] - a['last'] - a['step']
        gaps += delta > tol
        overlaps += delta < -tol
    first = segments[0]['first']
    last = max(s['last'] for s in segments)
    lattice = all(min((s['first'] - first) % step, (first - s['first']) % step) <= tol for s in segments)
    finite = True
    minimum = maximum = None
    count = 0
    for seg in segments:
        data = seg['piece']['data']
        for i in range(seg['lo'], seg['hi']):
            x = data[i]
            count += 1
            if math.isfinite(x):
                minimum = x if minimum is None else min(minimum, x)
                maximum = x if maximum is None else max(maximum, x)
            else:
                finite = False
    longest = run = 0
    prior = previous = None
    for seg in segments:
        if previous is None or seg['rate'] != previous['rate'] or abs(seg['first'] - previous['last'] - previous['step']) > tol:
            run = 0
            prior = None
        for i in range(seg['lo'], seg['hi']):
            x = seg['piece']['data'][i]
            if not math.isfinite(x):
                run = 0
                prior = None
                continue
            extreme = x == minimum or x == maximum
            run = run + 1 if extreme and prior == x else (1 if extreme else 0)
            longest = max(longest, run)
            prior = x
        previous = seg
    rates = all(float_rate_agrees(s['rate'], expected_rate) and s['step'] == step for s in segments)
    edge = 0 <= first - left < step and 0 < deadline - last <= step
    flat = finite and minimum == maximum
    # The frozen prose requires >=8 contiguous samples even for a flat prefix;
    # old producer core's unconditional flatness is a retained discrepancy.
    candidate = bool(longest >= 8)
    valid = bool(finite and rates and edge and lattice and gaps == 0 and overlaps == 0)
    return dict(available=valid, samples=count, finite=finite, sample_rate_matches=rates, edge_coverage=edge,
                gaps=gaps, overlaps=overlaps, flatline=bool(flat), sample_grid_consistent=lattice,
                first_sample_ns_numerator=first.numerator, first_sample_ns_denominator=first.denominator,
                sample_period_ns_numerator=step.numerator, sample_period_ns_denominator=step.denominator,
                longest_prefix_extreme_run=longest, clipping_candidate=candidate,
                clipping_screen_passed=valid and not candidate, physically_unclipped_verified=False,
                timing_quality_values=sorted({str(s['piece'].get('timing_quality')) for s in segments}),
                calibration_type_values=sorted({str(s['piece'].get('calibration_type')) for s in segments}))


def aligned(components, rate):
    if len(components) != 3 or not all(v['available'] for v in components.values()):
        return False
    origins = [Fraction(v['first_sample_ns_numerator'], v['first_sample_ns_denominator']) for v in components.values()]
    periods = [Fraction(v['sample_period_ns_numerator'], v['sample_period_ns_denominator']) for v in components.values()]
    if len(set(periods)) != 1:
        return False
    step = periods[0]
    if not float_rate_agrees(Fraction(NS) / step, rate):
        return False
    tol = min(Fraction(1000), step / 100)
    return all(min((o - origins[0]) % step, (origins[0] - o) % step) <= tol for o in origins)


def native_mseed2_rate(record, byteorder):
    """SEED2 FSDH factor/multiplier, overridden by Blockette100's binary float.

    This reads only the native clock fields; samples are decoded by public
    ObsPy. No rational approximation of the rounded decoder rate is permitted.
    """
    if byteorder not in ('<','>') or len(record) < 48:
        raise ValueError('invalid native record header')
    factor, multiplier = struct.unpack_from(byteorder + 'hh', record, 32)
    offset = struct.unpack_from(byteorder + 'H', record, 46)[0]
    rate = None
    seen = set()
    while offset:
        if offset in seen or not 48 <= offset <= len(record) - 4:
            raise ValueError('invalid native blockette chain')
        seen.add(offset)
        kind, following = struct.unpack_from(byteorder + 'HH', record, offset)
        if following and following <= offset:
            raise ValueError('nonincreasing native blockette chain')
        if kind == 100:
            if rate is not None or offset > len(record) - 8:
                raise ValueError('duplicate/truncated sample-rate blockette')
            actual = struct.unpack_from(byteorder + 'f', record, offset + 4)[0]
            if not math.isfinite(actual) or actual <= 0:
                raise ValueError('invalid native sample-rate blockette')
            rate = Fraction.from_float(actual)
        offset = following
    if rate is None:
        if factor == 0 or multiplier == 0:
            raise ValueError('zero native sample rate')
        a = Fraction(factor) if factor > 0 else Fraction(1, -factor)
        b = Fraction(multiplier) if multiplier > 0 else Fraction(1, -multiplier)
        rate = a * b
    return rate


def native_mseed2_records(body):
    """Public record information plus direct clock fields; no recovery/merge."""
    from obspy.io.mseed.util import get_record_information
    cursor = 0
    buffer = io.BytesIO(body)
    while cursor < len(body):
        if len(body) - cursor < 48 or body[cursor + 6:cursor + 7] not in (b'D',b'R',b'Q',b'M'):
            raise ValueError('unsupported/truncated native miniSEED2 record')
        info = get_record_information(buffer, offset=cursor)
        length = info['record_length']
        if type(length) is not int or length < 48 or cursor + length > len(body):
            raise ValueError('invalid native record length')
        record = memoryview(body)[cursor:cursor + length]
        yield record, native_mseed2_rate(record, info['byteorder'])
        cursor += length


class PublicObsPy:
    """Only public decoding/evalresp primitives, never producer Python modules."""
    def headers(self, body):
        from obspy import read
        return read(io.BytesIO(body), format='MSEED', headonly=True, details=True)

    def decode(self, body):
        from obspy import read, Stream
        stream = Stream()
        for record, rate in native_mseed2_records(body):
            fragment = read(io.BytesIO(record), format='MSEED', details=True)
            if len(fragment) != 1 or not float_rate_agrees(fragment[0].stats.sampling_rate, rate):
                raise ValueError('public/native record rate or trace accounting mismatch')
            fragment[0].stats.native_rate_numerator = rate.numerator
            fragment[0].stats.native_rate_denominator = rate.denominator
            stream.extend(fragment)
        return stream

    @staticmethod
    def declared(stream):
        numbers = [int(t.stats.npts) for t in stream]
        if any(n < 0 for n in numbers):
            raise ValueError('negative header count')
        return sum(numbers)

    @staticmethod
    def actual(stream):
        return sum(t.data.nbytes for t in stream)

    @staticmethod
    def pieces(stream, target, code, deadline):
        out = []
        for tr in stream:
            s = tr.stats
            if (s.network, s.station, s.location, s.channel) != (target['network'], target['station'], target['location'], code):
                continue
            if s.starttime.ns >= deadline:
                continue
            meta = getattr(s, 'mseed', {})
            timing = meta.get('blkt1001', {})
            native_rate = Fraction(s.native_rate_numerator, s.native_rate_denominator)
            out.append(dict(start_ns=s.starttime.ns, sample_rate=float(native_rate), data=tr.data,
                            sample_rate_fraction=native_rate,
                            timing_quality=timing.get('timing_quality'), calibration_type=meta.get('calibration_type')))
        return out


class BlockDecoder:
    """Header-first combined new+cache declarations and actual decoded bytes.

    Pass at most one fresh batch plus up to9 frozen cache candidates. Header
    bodies are released before full reads; decoded streams are caller-owned and
    must be released before the next block. Read pins are checked on every pass.
    """
    def __init__(self, entries, backend=None, cap=DECODE_CAP):
        if len(entries) > 10 or len([e for e in entries if e['source'] == 'new_batch']) > 1:
            raise AuditError('one fresh body and at most9 cached candidates required')
        if any(e['source'] not in ('new_batch', 'exact_cache') for e in entries):
            raise AuditError('unknown body source')
        if len([e for e in entries if e['source'] == 'exact_cache']) > 9:
            raise AuditError('cache candidate cap')
        if len({e['key'] for e in entries}) != len(entries) or not 0 < cap <= DECODE_CAP:
            raise AuditError('unique bounded block inputs required')
        self.entries = {e['key']: e for e in entries}
        self.backend = backend or PublicObsPy()
        self.cap = cap
        self.declarations = {}
        self.header_errors = {}
        total = 0
        for e in entries:
            body = bounded_body(e['path'], 16 * MIB, e['pin'])
            try:
                headers = self.backend.headers(body)
                n = self.backend.declared(headers)
                self.declarations[e['key']] = n
                total += n * 8
                del headers
            except ResourceStop:
                raise
            except MemoryError as exc:
                raise ResourceStop('header allocation failed') from exc
            except Exception as exc:
                raise_if_resource_failure(exc)
                self.header_errors[e['key']] = type(exc).__name__ + ': ' + str(exc)
            finally:
                del body
            if total > cap:
                raise ResourceStop('combined declared sample cap exceeded')
        self.actual_total = 0
        self.decoded = set()

    def decode(self, key):
        if key in self.decoded:
            raise AuditError('duplicate decoding would evade accounting')
        if key in self.header_errors:
            raise ValueError(self.header_errors[key])
        e = self.entries[key]
        body = bounded_body(e['path'], 16 * MIB, e['pin'])
        try:
            stream = self.backend.decode(body)
        except MemoryError as exc:
            raise ResourceStop('sample allocation failed') from exc
        finally:
            del body
        actual = self.backend.actual(stream)
        self.actual_total += actual
        self.decoded.add(key)
        if actual < 0 or self.actual_total > self.cap:
            del stream
            raise ResourceStop('combined actual sample cap exceeded')
        if self.backend.declared(stream) != self.declarations[key]:
            del stream
            raise ValueError('decoded count differs from header')
        return stream


@contextmanager
def captured_native_stderr():
    """Single-threaded POSIX evalresp call; retain bounded native warnings privately."""
    sys.stderr.flush()
    saved = os.dup(2)
    try:
        with tempfile.TemporaryFile() as sink:
            os.dup2(sink.fileno(), 2)
            try:
                yield sink
            finally:
                sys.stderr.flush()
                os.dup2(saved, 2)
    finally:
        os.close(saved)


def selected_response_xml(xml_body, selected):
    """Prune unselected epochs before public parsing; original bytes stay intact.

    Network/station/channel containers and complete response stages of the
    uniquely joined selected epochs are retained without changing their values.
    The caller's original body pin remains the provenance check.
    """
    rows = stationxml(xml_body)
    keys = RESPONSE_JOIN_KEYS
    root = ET.fromstring(xml_body.decode('utf-8-sig'))
    paths = [(net, sta, ch) for net in root if _local_name(net) == 'Network'
             for sta in net if _local_name(sta) == 'Station'
             for ch in sta if _local_name(ch) == 'Channel']
    if len(paths) != len(rows):
        raise AuditError('direct XML channel accounting mismatch')
    chosen = []
    keep = set()
    for wanted in selected:
        matches = [(row, path) for row, path in zip(rows, paths)
                   if all(row[k] == wanted[k] for k in keys)]
        if len(matches) != 1 or id(matches[0][1][2]) in keep:
            raise ValueError('cached response epoch/rate/orientation differs')
        row, (_, _, ch) = matches[0]
        if row.get('timestamp_errors'):
            raise ValueError('selected response timestamp error')
        chosen.append(row)
        keep.add(id(ch))
    for net in list(root):
        if _local_name(net) != 'Network':
            continue
        for sta in list(net):
            if _local_name(sta) != 'Station':
                continue
            for ch in list(sta):
                if _local_name(ch) == 'Channel' and id(ch) not in keep:
                    sta.remove(ch)
            if not any(_local_name(ch) == 'Channel' for ch in sta):
                net.remove(sta)
        if not any(_local_name(sta) == 'Station' for sta in net):
            root.remove(net)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True), chosen


def response_panel(xml_body, selected):
    """Exact metadata match, public evalresp; not physical calibration proof."""
    from obspy import read_inventory
    isolated, chosen = selected_response_xml(xml_body, selected)
    keys = RESPONSE_JOIN_KEYS
    inventory = read_inventory(io.BytesIO(isolated), format='STATIONXML')
    evidence = {}
    for row in chosen:
        matches = []
        for net in inventory:
            for sta in net:
                for ch in sta:
                    starts = [v.ns for v in (net.start_date, sta.start_date, ch.start_date) if v is not None]
                    ends = [v.ns for v in (net.end_date, sta.end_date, ch.end_date) if v is not None]
                    own = tuple(v.ns if v is not None else None for v in
                                (net.start_date, net.end_date, sta.start_date, sta.end_date, ch.start_date, ch.end_date))
                    identity = (net.code, sta.code, ch.location_code, ch.code, max(starts) if starts else None,
                                min(ends) if ends else None, *own, ch.sample_rate, ch.dip, ch.azimuth)
                    if identity == tuple(row[k] for k in keys):
                        matches.append(ch.response)
        if len(matches) != 1:
            raise ValueError('public response decoder epoch mismatch')
        response = matches[0]
        item = dict(warnings=[], native_stderr='', full_transfer_response_available=False,
                    physically_calibrated_prefix_verified=False)
        failure_category = 'missing_response_or_sensitivity'
        try:
            if response is None or not response.response_stages or response.instrument_sensitivity is None:
                raise ValueError('missing full transfer response/sensitivity')
            sensitivity = response.instrument_sensitivity
            failure_category = 'invalid_response_sensitivity'
            gain, freq = float(sensitivity.value), float(sensitivity.frequency)
            units = str(sensitivity.input_units).upper().replace(' ', '').replace('**', '^')
            output = str(sensitivity.output_units).upper().replace(' ', '')
            if not math.isfinite(gain) or gain <= 0 or not math.isfinite(freq) or not 0 < freq < row['sample_rate'] / 2 or units not in ('M', 'M/S', 'M/S^2') or output not in ('COUNT', 'COUNTS'):
                raise ValueError('invalid sensitivity/frequency/units')
            item.update(input_units=units, output_units=output, sensitivity=gain, reference_frequency=freq,
                        response_stages=len(response.response_stages))
            failure_category = 'evalresp_failure'
            with captured_native_stderr() as sink, warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                try:
                    transfer = complex(response.get_evalresp_response_for_frequencies([freq], output='DEF')[0])
                finally:
                    item['warnings'] = [str(w.message) for w in caught]
                    sink.seek(0)
                    native = sink.read(65537)
                    if len(native) > 65536:
                        raise ResourceStop('native warning body cap')
                    item['native_stderr'] = native.decode('utf-8', errors='replace')
                    if resource_failure_diagnostic(item['native_stderr']):
                        raise ResourceStop('native evalresp resource diagnostic')
            size = abs(transfer)
            ratio = size / gain
            failure_category = 'nonfinite_or_zero_transfer'
            if not all(math.isfinite(v) for v in (transfer.real, transfer.imag, size, ratio)) or size == 0:
                raise ValueError('nonfinite/zero transfer')
            item.update(transfer_magnitude_at_reference=size, reference_to_sensitivity_ratio=ratio,
                        full_transfer_response_available=True)
        except (MemoryError, ResourceStop):
            raise
        except Exception as exc:
            raise_if_resource_failure(exc)
            if resource_failure_diagnostic(str(exc)) or resource_failure_diagnostic(item['native_stderr']):
                raise ResourceStop('wrapped response resource diagnostic') from exc
            item['error'] = type(exc).__name__ + ': ' + str(exc)
            item['failure_category'] = failure_category
        evidence[row['code']] = item
    return evidence


def qualify(event, target, xml_body, stream, backend=None, response_body=None):
    backend = backend or PublicObsPy()
    rows = stationxml(xml_body)
    answer = {}
    for horizon in HORIZONS:
        h = str(horizon)
        if target['station'] not in event['current_station_masks'][h]:
            answer[h] = dict(status='not_in_current_arrival_subset', count_valid=False)
            continue
        result = dict(status='unresolved', count_valid=False, clipping_screen_passed=False,
                      full_transfer_response_available=False, physically_calibrated_prefix_verified=False,
                      operational_picker_replayed=False)
        left, end = event['t0_ns'] - 5 * NS, event['t0_ns'] + horizon * NS
        try:
            channels = epoch_triplet(rows, target, left, end)
            components = {c['code']: prefix_component(backend.pieces(stream, target, c['code'], end), left, end, c['sample_rate']) for c in channels}
            result.update(status='audited', count_valid=aligned(components, channels[0]['sample_rate']),
                          components=components, clipping_screen_passed=all(c.get('clipping_screen_passed', False) for c in components.values()),
                          sensor_codes=[c['code'] for c in channels])
            result['channel_geometry'] = {c['code']: {
                'latitude': c['latitude'] if math.isfinite(c['latitude']) and -90 <= c['latitude'] <= 90 else None,
                'longitude': c['longitude'] if math.isfinite(c['longitude']) and -180 <= c['longitude'] <= 180 else None,
                'elevation_m': c['elevation_m'] if math.isfinite(c['elevation_m']) else None} for c in channels}
            result['response_evidence'] = {}
            if response_body is not None:
                response_failure = 'cached_response_metadata'
                try:
                    selected_codes = {c['code'] for c in channels}
                    # Sensor-family choice belongs to current channel metadata;
                    # cached response evidence joins that already-selected set.
                    response_rows = [r for r in stationxml(response_body) if r['code'] in selected_codes]
                    stronger = epoch_triplet(response_rows, target, left, end)
                    keys = RESPONSE_JOIN_KEYS
                    response_failure = 'cached_response_metadata_join'
                    if any(any(a[k] != b[k] for k in keys) for a, b in zip(channels, stronger)):
                        raise ValueError('cached response epoch/rate/orientation differs')
                    response_failure = 'cached_response_public_parser'
                    result['response_evidence'] = response_panel(response_body, channels)
                    result['full_transfer_response_available'] = all(v['full_transfer_response_available'] for v in result['response_evidence'].values())
                except (AuditError, MemoryError, ResourceStop):
                    raise
                except Exception as exc:
                    raise_if_resource_failure(exc)
                    result['response_panel_error'] = type(exc).__name__ + ': ' + str(exc)
                    result['response_panel_failure_category'] = response_failure
        except (AuditError, MemoryError, ResourceStop):
            raise
        except Exception as exc:
            raise_if_resource_failure(exc)
            result['reason'] = type(exc).__name__ + ': ' + str(exc)
        result['failure_categories'] = prefix_failure_categories(result)
        answer[h] = result
    return answer


def prefix_failure_categories(result):
    """Multiple stable failure categories per target; never success-only counts."""
    if result.get('count_valid') is True or result.get('status') == 'not_in_current_arrival_subset':
        return []
    components = result.get('components', {})
    if not components:
        return [result.get('status', 'unresolved')]
    reasons = set()
    checks = {'finite':'nonfinite_samples', 'sample_rate_matches':'sample_rate_mismatch',
              'edge_coverage':'edge_coverage', 'sample_grid_consistent':'within_component_lattice'}
    for component in components.values():
        if component.get('reason') == 'no_prefix_samples':
            reasons.add('no_prefix_samples')
        for flag, label in checks.items():
            if component.get(flag) is False:
                reasons.add(label)
        if component.get('gaps',0):reasons.add('fragment_gap')
        if component.get('overlaps',0):reasons.add('fragment_overlap')
    if all(v.get('available') is True for v in components.values()):
        reasons.add('cross_component_lattice')
    return sorted(reasons) or ['unclassified_count_failure']


def response_failure_categories(result):
    """Nonexclusive target counts; error/warning text remains private."""
    allowed = {'cached_response_metadata', 'cached_response_metadata_join',
               'cached_response_public_parser', 'missing_response_or_sensitivity',
               'invalid_response_sensitivity', 'evalresp_failure', 'nonfinite_or_zero_transfer'}
    categories = set()
    if 'response_panel_error' in result:
        value = result.get('response_panel_failure_category')
        categories.add(value if value in allowed else 'cached_response_panel_error')
    for item in result.get('response_evidence', {}).values():
        if 'error' in item:
            value = item.get('failure_category')
            categories.add(value if value in allowed else 'response_evaluation_error')
    return sorted(categories)


def initial_rows(events):
    return [dict(slot=e['event_id'] + '|' + t['station'], event_id=e['event_id'], station=t['station'],
                 status='unattempted' if t['queryable'] else 'unqueryable',
                 horizons={str(h): dict(status=(('unattempted' if t['queryable'] else 'unqueryable')
                                                if t['station'] in e['current_station_masks'][str(h)] else 'not_in_current_arrival_subset'),
                                       count_valid=False) for h in HORIZONS}) for e in events for t in e['targets']]


def qualification_batch(events, body_entries, channel_bodies, cached_responses, backend=None):
    """Replay one <=16-event block. Ordinary bad new bytes do not erase caches.

    Entries identify 'new_batch' or the exact cached slot. The caller must
    independently verify provenance and retrieval successes before supplying
    entries. No alternate entry is chosen on a decoder/epoch failure.
    """
    if len(events) > 16:
        raise AuditError('block event cap')
    backend = backend or PublicObsPy()
    decoder = BlockDecoder(body_entries, backend)
    rows = initial_rows(events)
    lookup = {r['slot']: r for r in rows}
    fresh_entries = [e for e in body_entries if e['source'] == 'new_batch']
    fresh, fresh_error = None, 'waveform_unavailable'
    if fresh_entries:
        try:
            fresh = decoder.decode(fresh_entries[0]['key'])
        except (AuditError, ResourceStop, MemoryError):
            raise
        except Exception as exc:
            raise_if_resource_failure(exc)
            fresh_error = type(exc).__name__ + ': ' + str(exc)
    cache_entries = {e['key']: e for e in body_entries if e['source'] == 'exact_cache'}
    for event in events:
        for target in event['targets']:
            slot = event['event_id'] + '|' + target['station']
            row = lookup[slot]
            if not target['queryable']:
                continue
            stream = None
            row['waveform_source'] = 'exact_cache' if slot in cache_entries else 'new_batch'
            body_key = slot if slot in cache_entries else fresh_entries[0]['key'] if fresh_entries else None
            row['waveform_retrieval_status'] = ('cached_verified_success' if slot in cache_entries else
                                                'new_success' if fresh_entries else 'unavailable')
            row['waveform_header_status'] = ('header_failed' if body_key in decoder.header_errors else
                                             'header_ok' if body_key in decoder.declarations else 'unavailable')
            row['waveform_decoder_status'] = 'not_decoded'
            row['channel_retrieval_status'] = 'ok' if slot in channel_bodies else 'unavailable'
            row['channel_parser_status'] = 'not_parsed'
            row['cached_response_status'] = 'supplied_exact_cache' if slot in cached_responses else 'not_cached'
            try:
                if slot in cache_entries:
                    row['waveform_decoder_status'] = 'not_attempted_header_failed' if slot in decoder.header_errors else 'decode_failed'
                    stream = decoder.decode(slot)
                elif fresh is not None:
                    stream = fresh
                else:
                    row['waveform_decoder_status'] = ('not_attempted_header_failed' if body_key in decoder.header_errors else
                                                       'decode_failed' if fresh_entries else 'unavailable')
                    raise ValueError(fresh_error)
                row['waveform_decoder_status'] = 'decoded'
                if slot not in channel_bodies:
                    row['channel_parser_status'] = 'unavailable'
                    raise ValueError('channel_metadata_unresolved')
                row['channel_parser_status'] = 'parse_failed'
                stationxml(channel_bodies[slot])
                row['channel_parser_status'] = 'parsed'
                row.update(status='audited', horizons=qualify(event, target, channel_bodies[slot], stream, backend,
                                                            cached_responses.get(slot)))
            except (AuditError, ResourceStop, MemoryError):
                raise
            except Exception as exc:
                raise_if_resource_failure(exc)
                if row['channel_parser_status'] == 'not_parsed':
                    row['channel_parser_status'] = 'not_attempted_waveform_failure'
                row['status'] = 'unresolved_engineering'
                for h in HORIZONS:
                    if row['horizons'][str(h)]['status'] != 'not_in_current_arrival_subset':
                        row['horizons'][str(h)] = dict(status='unresolved_engineering', reason=type(exc).__name__ + ': ' + str(exc), count_valid=False)
            finally:
                stream = None
    fresh = None
    return rows


def aggregate(events, targets, completed):
    """Rebuild event×3 current views and denominator-preserving aggregate panels."""
    if len(events) != 96 or len({e['event_id'] for e in events}) != 96:
        raise AuditError('96 source events required')
    pairs = {(e['event_id'], t['station']) for e in events for t in e['targets']}
    if len(targets) != len(pairs) or {(r['event_id'], r['station']) for r in targets} != pairs:
        raise AuditError('target denominator changed')
    lookup = {(r['event_id'], r['station']): r for r in targets}
    rows = []
    for e in events:
        horizons = {}
        for h in HORIZONS:
            current = []
            for t in e['targets']:
                if t['station'] not in e['current_station_masks'][str(h)]:
                    continue
                v = lookup[(e['event_id'], t['station'])]['horizons'][str(h)]
                current.append(dict(network=t['network'], station=t['station'], location=t['location'], prefix=t['prefix'], pick_ns=t['pick_ns'], engineering=v))
            horizons[str(h)] = dict(current_view=current, count_available=any(v['engineering'].get('count_valid') is True for v in current),
                                   clean_screen_available=any(v['engineering'].get('count_valid') is True and v['engineering'].get('clipping_screen_passed') is True for v in current),
                                   full_response_consistent_count_available=any(v['engineering'].get('count_valid') is True and v['engineering'].get('full_transfer_response_available') is True for v in current))
        rows.append(dict(event_id=e['event_id'], Mw_band=e['Mw_band'], candidate_calendar_partition=e['candidate_calendar_partition'],
                         P_status=e['P_status'], incomplete_associated_P_structure=e['incomplete_associated_P_structure'], horizons=horizons,
                         common_count_available=all(v['count_available'] for v in horizons.values()),
                         common_clean_screen_available=all(v['clean_screen_available'] for v in horizons.values())))
    def panel(group):
        return dict(event_denominator=len(group), common_count_available=sum(r['common_count_available'] for r in group),
                    common_clean_screen_available=sum(r['common_clean_screen_available'] for r in group),
                    horizons={str(h): {k: sum(r['horizons'][str(h)][k] for r in group) for k in ('count_available', 'clean_screen_available', 'full_response_consistent_count_available')} for h in HORIZONS})
    summary = dict(completed=completed, scientific_interpretation_allowed=completed, events=panel(rows), target_denominator=len(targets),
                   band_calendar=[dict(Mw_band=b, candidate_calendar_partition=p, **panel([r for r in rows if (r['Mw_band'], r['candidate_calendar_partition']) == (b, p)])) for p in PARTITIONS for b in ALL_BANDS])
    for key, default in (('status', None), ('channel_retrieval_status', 'unattempted'), ('waveform_source', 'unattempted'),
                         ('waveform_retrieval_status', 'unattempted'), ('cached_response_status', 'not_evaluated'),
                         ('waveform_header_status', 'unattempted'), ('waveform_decoder_status', 'unattempted'),
                         ('channel_parser_status', 'unattempted')):
        summary['target_status' if key == 'status' else key] = dict(sorted(Counter(r.get(key, default) for r in targets).items()))
    summary['P_event_status'] = dict(sorted(Counter(e['P_status'] for e in events).items()))
    summary['target_horizon_status'] = {str(h): dict(sorted(Counter(r['horizons'][str(h)]['status'] for r in targets).items())) for h in HORIZONS}
    summary['target_horizon_clipping_candidates'] = {str(h): sum(any(c.get('clipping_candidate') is True for c in r['horizons'][str(h)].get('components', {}).values()) for r in targets) for h in HORIZONS}
    summary['target_horizon_failure_categories'] = {str(h): dict(sorted(Counter(category for r in targets for category in
                                                                               prefix_failure_categories(r['horizons'][str(h)])).items())) for h in HORIZONS}
    summary['target_horizon_response_failure_categories'] = {str(h): dict(sorted(Counter(category for r in targets for category in
                                                                                        response_failure_categories(r['horizons'][str(h)])).items())) for h in HORIZONS}
    return rows, summary


def private_reason_counters(targets):
    """Private evidence only; must never be embedded in a public summary."""
    return {str(h): dict(sorted(Counter(r['horizons'][str(h)].get('reason', 'no_reason')
                                       for r in targets).items())) for h in HORIZONS}


def compare_prefix_facts(independent, produced):
    """Semantic comparison of every target×3 qualification fact, not array data.

    Returns private mismatches. Additional independent parser/retrieval stages
    stay separate from producer statuses; no unobserved fact is inferred from
    a producer result. Source/attempt/receipt checks precede this comparison.
    """
    left = {(r['event_id'],r['station']):r for r in independent}
    right = {(r['event_id'],r['station']):r for r in produced}
    if len(left)!=len(independent) or len(right)!=len(produced) or set(left)!=set(right):
        raise AuditError('prefix comparison denominator mismatch')
    discrepancies=[]
    scalar=('status','count_valid','clipping_screen_passed','full_transfer_response_available','sensor_codes','channel_geometry',
            'physically_calibrated_prefix_verified','operational_picker_replayed')
    component_keys=('available','reason','samples','finite','sample_rate_matches','edge_coverage','gaps','overlaps','flatline',
                    'sample_grid_consistent','first_sample_ns_numerator','first_sample_ns_denominator','longest_prefix_extreme_run',
                    'sample_period_ns_numerator','sample_period_ns_denominator',
                    'clipping_candidate','clipping_screen_passed','physically_unclipped_verified','timing_quality_values','calibration_type_values')
    for pair in sorted(left):
        for h in map(str,HORIZONS):
            x,y=left[pair]['horizons'][h],right[pair]['horizons'][h]
            for k in scalar:
                if (k in x,x.get(k))!=(k in y,y.get(k)):
                    discrepancies.append(dict(pair=pair,horizon=h,field=k,independent=x.get(k),producer=y.get(k),
                                              independent_present=k in x,producer_present=k in y))
            xc,yc=x.get('components',{}),y.get('components',{})
            if set(xc)!=set(yc):discrepancies.append(dict(pair=pair,horizon=h,field='component_codes'))
            for code in sorted(set(xc)&set(yc)):
                for k in component_keys:
                    if (k in xc[code],xc[code].get(k))!=(k in yc[code],yc[code].get(k)):
                        discrepancies.append(dict(pair=pair,horizon=h,field=code+'.'+k,independent=xc[code].get(k),producer=yc[code].get(k),
                                                  independent_present=k in xc[code],producer_present=k in yc[code]))
            # Errors are compared explicitly; independent wording is retained
            # rather than reverse-engineered to force an apparently clean replay.
            for k in ('reason','response_panel_error'):
                if x.get(k)!=y.get(k):discrepancies.append(dict(pair=pair,horizon=h,field=k,independent=x.get(k),producer=y.get(k)))
            xe,ye=x.get('response_evidence',{}),y.get('response_evidence',{})
            if set(xe)!=set(ye):discrepancies.append(dict(pair=pair,horizon=h,field='response_codes'))
            for code in sorted(set(xe)&set(ye)):
                for k in ('input_units','output_units','sensitivity','reference_frequency','response_stages','transfer_magnitude_at_reference',
                          'reference_to_sensitivity_ratio','full_transfer_response_available','warnings','native_stderr','error',
                          'physically_calibrated_prefix_verified'):
                    if (k in xe[code],xe[code].get(k))!=(k in ye[code],ye[code].get(k)):
                        discrepancies.append(dict(pair=pair,horizon=h,field=code+'.response.'+k,independent=xe[code].get(k),
                                                  producer=ye[code].get(k),independent_present=k in xe[code],producer_present=k in ye[code]))
    return discrepancies

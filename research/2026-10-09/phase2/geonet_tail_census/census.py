#!/usr/bin/env python3
"""Bounded metadata-only GeoNet census; real outputs must remain local/ignored."""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

VERSION = 'geonet-tail-census-v1'
MIB = 1024 * 1024
START, END = dt.datetime(2003, 8, 1), dt.datetime(2025, 1, 1)
PHASES = {'P', 'Pg', 'Pn', 'Pb'}
WPHASE = {'20090715092200', '20161113110200'}
ID_RE = re.compile(r'(?:[0-9]{5,7}|[0-9]{4}p[0-9]{6})\Z')
COMMIT_URL = 'https://api.github.com/repos/GeoNet/data/commits/main'
QML_NS = 'http://quakeml.org/xmlns/quakeml/1.2'
BED_NS = 'http://quakeml.org/xmlns/bed/1.2'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')


def number(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def parse_cmt(body):
    reader = csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
    headers = reader.fieldnames or []
    norm = [h.strip().lower() for h in headers]
    norm = ['event_id' if h == 'publicid' else h for h in norm]
    if len(set(norm)) != len(norm) or not {'event_id', 'date', 'mw', 'method'} <= set(norm):
        raise ValueError('missing/duplicate CMT required columns')
    rows, buckets = [], collections.defaultdict(list)
    for idx, raw in enumerate(reader, 1):
        if None in raw:
            raise ValueError('CMT row has excess columns')
        r = {('event_id' if k.strip().lower() == 'publicid' else k.strip().lower()): (v or '').strip() for k, v in raw.items()}
        eid, date = r['event_id'], r['date']
        reasons = []
        try:
            if not re.fullmatch(r'[0-9]{12}00', date):
                raise ValueError('date format')
            date_obj = dt.datetime.strptime(date, '%Y%m%d%H%M%S')
            if not START <= date_obj < END:
                reasons.append('date_outside_window')
        except ValueError:
            reasons.append('invalid_date')
        mw = number(r['mw'])
        if mw is None:
            reasons.append('invalid_mw')
        if eid == '9999999':
            reasons.append('unknown_9999999')
        elif not ID_RE.fullmatch(eid):
            reasons.append('unresolvable_id_syntax')
        item = {'row_index': idx, 'event_id': eid, 'date': date, 'mw': mw,
                'method': r['method'] or 'missing', 'external_wphase': date in WPHASE,
                'reasons': reasons, 'original': raw}
        rows.append(item)
        if ID_RE.fullmatch(eid) and eid != '9999999':
            buckets[eid].append(item)
    groups = []
    for eid, rr in sorted(buckets.items()):
        valid = all(not r['reasons'] for r in rr)
        mags = [r['mw'] for r in rr if r['mw'] is not None]
        groups.append({'event_id': eid, 'row_indices': [r['row_index'] for r in rr],
                       'eligible': valid, 'mw_min': min(mags) if mags else None,
                       'mw_max': max(mags) if mags else None,
                       'dates': sorted({r['date'] for r in rr}),
                       'methods': sorted({r['method'] for r in rr}),
                       'external_wphase': any(r['external_wphase'] for r in rr),
                       'conflicting_mw': len(set(mags)) > 1,
                       'reasons': sorted({s for r in rr for s in r['reasons']})})
    return rows, groups


def query_order(groups):
    return sorted((g['event_id'] for g in groups if g['eligible'] and g['mw_max'] >= 5.5),
                  key=lambda eid: (sha((VERSION + '|' + eid).encode()), eid))


def utc(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('pick time lacks timezone')
    return parsed.astimezone(dt.timezone.utc)


def text_at(el, path):
    current = el
    for name in path.split('/'):
        found = current.findall(bed(name))
        if len(found) > 1:
            raise ValueError('duplicate singleton XML field: '+path+' at '+name)
        if not found:
            return ''
        current = found[0]
    return (current.text or '').strip()


def bed(name):
    return '{'+BED_NS+'}'+name


def coverage(picks):
    station_times = {}
    for p in picks:
        key = p['network'] + '.' + p['station']
        stamp = utc(p['time'])
        station_times[key] = min(station_times.get(key, stamp), stamp)
    t0 = min(station_times.values()) if station_times else None
    return {'stations': len(station_times), 't0_utc': t0.isoformat() if t0 else None,
            'before_seconds': {str(t): sum((v-t0).total_seconds() < t for v in station_times.values())
                               if t0 else 0 for t in (1, 3, 5)}}


def parse_quakeml(body, eid):
    decoded = body.decode('utf-8-sig')
    if '\x00' in decoded:
        raise ValueError('only UTF-8 XML supported; embedded NUL rejected')
    if '<!DOCTYPE' in decoded.upper() or '<!ENTITY' in decoded.upper():
        raise ValueError('DTD/entity not permitted')
    root = ET.fromstring(decoded)
    if root.tag != '{'+QML_NS+'}quakeml':
        raise ValueError('expected QuakeML 1.2 root namespace')
    parameters = root.findall(bed('eventParameters'))
    if len(parameters) != 1:
        raise ValueError('expected unique BED 1.2 eventParameters')
    # Foreign extension fields cannot substitute for required BED evidence.
    events = [e for e in parameters[0].findall(bed('event'))
              if e.get('publicID', '').rstrip('/').rsplit('/', 1)[-1] == eid]
    if len(events) != 1:
        raise ValueError('event identity not uniquely matched')
    event = events[0]
    out = {'event_id': eid, 'status': 'ok', 'reasons': {}, 'accepted_picks': [],
           'catalog_magnitude_types': sorted({text_at(m, 'type') or 'missing' for m in event.findall(bed('magnitude'))}),
           'event_type': text_at(event, 'type'), 'preferred_origin_id': text_at(event, 'preferredOriginID')}
    origins = [o for o in event.findall(bed('origin')) if o.get('publicID') == out['preferred_origin_id']]
    if not out['preferred_origin_id'] or len(origins) != 1:
        out.update(status='missing_or_ambiguous_preferred_origin', all_network=None, nz=None)
        return out
    pickmap = collections.defaultdict(list)
    for p in event.findall(bed('pick')):
        pickmap[p.get('publicID', '')].append(p)
    counts, seen = collections.Counter(), set()
    for arrival in origins[0].findall(bed('arrival')):
        phase = text_at(arrival, 'phase')
        if phase not in PHASES:
            counts['other_phase:' + phase] += 1
            continue
        pid = text_at(arrival, 'pickID')
        if not pid or len(pickmap.get(pid, [])) != 1:
            counts['missing_or_ambiguous_pick_reference'] += 1
            continue
        weight = text_at(arrival, 'timeWeight')
        if weight and (number(weight) is None or number(weight) <= 0):
            counts['nonpositive_or_invalid_time_weight'] += 1
            continue
        pick = pickmap[pid][0]
        status = text_at(pick, 'evaluationStatus')
        if status == 'rejected':
            counts['rejected_pick'] += 1
            continue
        waveforms = pick.findall(bed('waveformID'))
        if len(waveforms) > 1:
            raise ValueError('duplicate singleton XML field: waveformID')
        wf = waveforms[0] if waveforms else None
        net, sta = (wf.get('networkCode', '').strip(), wf.get('stationCode', '').strip()) if wf is not None else ('', '')
        if not net or not sta:
            counts['missing_station_identity'] += 1
            continue
        observed_time = text_at(pick, 'time/value')
        try:
            stamp = utc(observed_time)
        except ValueError:
            counts['invalid_or_naive_pick_time'] += 1
            continue
        if pid in seen:
            counts['duplicate_accepted_arrival_reference'] += 1
            continue
        seen.add(pid)
        if not weight:
            counts['accepted_missing_time_weight'] += 1
        out['accepted_picks'].append({'pick_id': pid, 'phase': phase, 'time': stamp.isoformat(),
                                     'network': net, 'station': sta,
                                     'location': wf.get('locationCode', ''), 'channel': wf.get('channelCode', ''),
                                     'evaluation_status': status or 'missing',
                                     'evaluation_mode': text_at(pick, 'evaluationMode') or 'missing'})
    out['reasons'] = dict(counts)
    out['all_network'] = coverage(out['accepted_picks'])
    out['nz'] = coverage([p for p in out['accepted_picks'] if p['network'] == 'NZ'])
    return out


def summarize(rows, groups, outcomes):
    eligible = [g for g in groups if g['eligible']]
    table = {}
    for threshold in (5.5, 6.0, 7.0):
        lower = [g for g in eligible if g['mw_min'] >= threshold]
        upper = [g for g in eligible if g['mw_max'] >= threshold]
        panels = {}
        for scope in ('all_network', 'nz'):
            values = [outcomes.get(g['event_id'], {}) for g in lower]
            valid = [r[scope] for r in values if r.get('status') == 'ok']
            panels[scope] = {'known_coverage_events': len(valid),
                'unknown_coverage_events': len(lower)-len(valid),
                'events_at_least_stations': {str(k): sum(v['stations'] >= k for v in valid) for k in (1, 3, 5)},
                'horizon_station_histograms': {str(t): dict(sorted(collections.Counter(str(v['before_seconds'][str(t)]) for v in valid).items())) for t in (1, 3, 5)}}
        table[str(threshold)] = {'unique_id_lower': len(lower), 'unique_id_upper': len(upper),
            'external_wphase_lower': sum(g['external_wphase'] for g in lower),
            'year_membership_lower': dict(collections.Counter(d[:4] for g in lower for d in sorted({x[:4] for x in g['dates']}))),
            'month_membership_lower': dict(collections.Counter(d[:6] for g in lower for d in sorted({x[:6] for x in g['dates']}))),
            'method_combination_lower': dict(collections.Counter('|'.join(g['methods']) for g in lower)),
            'coverage': panels}
    return {'version': VERSION, 'data_rows': len(rows), 'resolvable_unique_ids': len(groups),
            'eligible_unique_ids': len(eligible), 'excluded_groups': len(groups)-len(eligible),
            'duplicate_id_groups': sum(len(g['row_indices']) > 1 for g in groups),
            'duplicate_extra_rows': sum(len(g['row_indices'])-1 for g in groups),
            'conflicting_mw_groups': sum(g['conflicting_mw'] for g in groups),
            'row_exclusion_reasons': dict(collections.Counter(s for r in rows for s in r['reasons'])),
            'query_candidates': len(query_order(groups)), 'query_outcome_status': dict(collections.Counter(r['status'] for r in outcomes.values())),
            'not_queried': len(query_order(groups))-len(outcomes), 'thresholds': table,
            'practical_gate_observed_support': table['5.5']['coverage']['nz']['events_at_least_stations']['1'] >= 60 and table['6.0']['coverage']['nz']['events_at_least_stations']['1'] >= 20,
            'claim_limit': 'Catalogued P picks are retrospective metadata, not waveform-prefix availability or independent sequences.'}


class LimitReached(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Fetcher:
    def __init__(self, root, clock=time.monotonic, sleep=time.sleep, opener=None,
                 max_seconds=1800, max_bytes=100*MIB, max_requests=500, request_alarm=False):
        self.root, self.clock, self.sleep = root, clock, sleep
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.request_alarm = request_alarm
        self.started = clock()
        self.deadline = self.started + max_seconds
        self.max_bytes, self.max_requests = max_bytes, max_requests
        self.bytes, self.log, self.last_start = 0, [], -math.inf

    def check(self):
        if self.clock() >= self.deadline:
            raise LimitReached('time limit')
        if self.bytes >= self.max_bytes:
            raise LimitReached('body byte limit')
        if len(self.log) >= self.max_requests:
            raise LimitReached('request limit')

    def fetch(self, url, name, per_file):
        self.check()
        self.sleep(max(0, 1-(self.clock()-self.last_start)))
        self.check()
        self.last_start = self.clock()
        entry = {'url': url, 'file': name, 'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'bytes': 0, 'status': 'started'}
        self.log.append(entry)
        content = bytearray()
        request_deadline = min(self.last_start+20, self.deadline)
        def request_alarm_handler(signum, frame):
            if self.clock() >= self.deadline:
                raise LimitReached('time limit')
            raise TimeoutError('20-second whole-request deadline')
        if self.request_alarm:
            signal.signal(signal.SIGALRM, request_alarm_handler)
            signal.setitimer(signal.ITIMER_REAL, max(0.001, request_deadline-self.clock()))
        try:
            req = urllib.request.Request(url, headers={'User-Agent': VERSION + ' metadata-only-research', 'Accept-Encoding': 'identity'})
            with self.opener.open(req, timeout=max(0.001, request_deadline-self.clock())) as response:
                entry['http_status'] = response.status
                if response.status != 200:
                    raise ValueError('HTTP status is not 200')
                length = response.headers.get('Content-Length')
                expected = int(length) if length is not None else None
                room = min(per_file, self.max_bytes-self.bytes)
                if expected is not None and (expected < 0 or expected > room):
                    raise LimitReached('declared response size exceeds limit')
                while True:
                    if self.clock() >= self.deadline:
                        raise LimitReached('time limit')
                    if self.clock() >= request_deadline:
                        raise TimeoutError('20-second whole-request deadline')
                    remain = min(per_file-len(content), self.max_bytes-self.bytes)
                    if remain <= 0:
                        if expected == len(content):
                            break
                        raise LimitReached('response/body byte limit without verified EOF')
                    chunk = response.read1(min(65536, remain))
                    if not chunk:
                        break
                    self.bytes += len(chunk)
                    content.extend(chunk)
                if expected is not None and len(content) != expected:
                    raise ValueError('Content-Length mismatch')
            entry['status'] = 'ok'
            return bytes(content)
        except Exception as exc:
            entry['status'] = type(exc).__name__
            entry['error'] = str(exc)[:200]
            raise
        finally:
            if self.request_alarm:
                signal.setitimer(signal.ITIMER_REAL, 0)
            # Persist received bytes/attempt ledger without deadline interruption.
            # Network access remains off; finalization is bounded by the byte cap.
            try:
                entry['bytes'] = len(content)
                entry['sha256'] = sha(content)
                entry['elapsed_seconds'] = self.clock()-self.last_start
                (self.root / name).write_bytes(content)
                dump(self.root.parent / 'requests.json', self.log)
            finally:
                if self.request_alarm:
                    signal.signal(signal.SIGALRM, alarm_handler)
                    remaining = self.deadline-self.clock()
                    if remaining > 0:
                        signal.setitimer(signal.ITIMER_REAL, remaining)
            if self.clock() >= self.deadline:
                raise LimitReached('time limit after response persistence')


def alarm_handler(signum, frame):
    raise LimitReached('1800-second process deadline')


def validate_recovery_plan(plan_path):
    plan = json.loads(plan_path.read_text())
    if (plan.get('version') != 'geonet-source-header-recovery-v1'
            or plan.get('window_seconds') != 1800
            or plan.get('combined_request_limit') != 500
            or plan.get('combined_body_byte_limit') != 100*MIB):
        raise ValueError('invalid frozen recovery limits')
    base = Path(__file__).resolve().parent
    required = ('census.py', 'test_census.py', 'PROTOCOL_v1.md',
                'AMENDMENT_20261010_PUBLICID.md', 'RECOVERY_WINDOW_v1.md')
    if set(plan.get('processing_files', {})) != set(required):
        raise ValueError('missing recovery processing bindings')
    for name in required:
        if sha((base/name).read_bytes()) != plan['processing_files'][name]:
            raise ValueError('recovery processing checksum mismatch: '+name)
    if not re.fullmatch('[0-9a-f]{64}', plan.get('prior_manifest_sha256', '')):
        raise ValueError('missing prior manifest checksum')
    return plan


def bootstrap_sources(prior, raw, fetch, plan):
    prior = validate_output(prior)
    manifest_body = (prior/'manifest.json').read_bytes()
    if sha(manifest_body) != plan['prior_manifest_sha256']:
        raise ValueError('bootstrap manifest checksum mismatch')
    manifest = json.loads(manifest_body)
    requests_body = (prior/'requests.json').read_bytes()
    if sha(requests_body) != manifest['files']['requests.json']['sha256']:
        raise ValueError('bootstrap request ledger checksum mismatch')
    log = json.loads(requests_body)
    names = ['commit.json', 'README.md', 'GeoNet_CMT_solutions.csv']
    if (manifest.get('completed') or manifest.get('stop_reason') != 'ValueError: missing/duplicate CMT required columns'
            or len(log) != 3 or [x['file'] for x in log] != names
            or any(x['status'] != 'ok' for x in log)):
        raise ValueError('bootstrap supports only the three-request source-header failure')
    commit = manifest['geonet_commit']
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('invalid bootstrap commit')
    expected_urls = [COMMIT_URL] + [f'https://raw.githubusercontent.com/GeoNet/data/{commit}/moment-tensor/'+n for n in names[1:]]
    if [x['url'] for x in log] != expected_urls:
        raise ValueError('bootstrap source URLs mismatch')
    total = sum(x['bytes'] for x in log)
    if total != manifest['response_body_bytes'] or total > fetch.max_bytes:
        raise ValueError('bootstrap byte accounting mismatch')
    # An explicit pre-execution amendment grants this one new process window.
    # Preserve request/byte totals; never reset or extend the new monotonic clock.
    if utc(log[0]['utc']) > dt.datetime.now(dt.timezone.utc):
        raise ValueError('bootstrap acquisition time is in the future')
    fetch.log, fetch.bytes = log, total
    fetch.check()
    for entry in log:
        body = (prior/'raw'/entry['file']).read_bytes()
        pinned = manifest['files']['raw/'+entry['file']]
        if (len(body) != entry['bytes'] or len(body) != pinned['bytes']
                or sha(body) != entry['sha256'] or sha(body) != pinned['sha256']):
            raise ValueError('bootstrap source checksum mismatch')
        (raw/entry['file']).write_bytes(body)
    dump(raw.parent/'requests.json', fetch.log)
    return commit, (raw/'GeoNet_CMT_solutions.csv').read_bytes(), sha(manifest_body)


def run(out, bootstrap=None, recovery_plan=None):
    if (bootstrap is None) != (recovery_plan is None):
        raise ValueError('bootstrap and recovery plan must be supplied together')
    plan = validate_recovery_plan(recovery_plan) if recovery_plan is not None else None
    out.mkdir(parents=True, exist_ok=False)
    raw = out / 'raw'
    raw.mkdir()
    fetch = Fetcher(raw, request_alarm=True)
    rows, groups, outcomes = [], [], {}
    state = {'version': VERSION, 'completed': False, 'source_sha256': sha(Path(__file__).read_bytes()),
             'protocol_sha256': sha(Path(__file__).with_name('PROTOCOL_v1.md').read_bytes()),
             'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
             'python': sys.version, 'limits': {'seconds': 1800, 'body_bytes': 100*MIB, 'requests': 500}}
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.setitimer(signal.ITIMER_REAL, 1800)
    code = 0
    try:
        if bootstrap is not None:
            state['recovery_plan_sha256'] = sha(recovery_plan.read_bytes())
            state['recovery_window_sha256'] = sha(Path(__file__).with_name('RECOVERY_WINDOW_v1.md').read_bytes())
            commit, body, prior_hash = bootstrap_sources(bootstrap, raw, fetch, plan)
            state['bootstrap_manifest_sha256'] = prior_hash
            state['carried_request_attempts'] = len(fetch.log)
            state['carried_response_body_bytes'] = fetch.bytes
            state['amendment_sha256'] = sha(Path(__file__).with_name('AMENDMENT_20261010_PUBLICID.md').read_bytes())
        else:
            commit = json.loads(fetch.fetch(COMMIT_URL, 'commit.json', MIB))['sha']
            if not re.fullmatch('[0-9a-f]{40}', commit):
                raise ValueError('invalid commit SHA')
            base = f'https://raw.githubusercontent.com/GeoNet/data/{commit}/moment-tensor/'
            fetch.fetch(base+'README.md', 'README.md', MIB)
            body = fetch.fetch(base+'GeoNet_CMT_solutions.csv', 'GeoNet_CMT_solutions.csv', 10*MIB)
        state['geonet_commit'] = commit
        rows, groups = parse_cmt(body)
        dump(out / 'rows.json', rows)
        dump(out / 'groups.json', groups)
        ordered = query_order(groups)
        state['query_order_sha256'] = sha(('\n'.join(ordered)+'\n').encode())
        dump(out / 'query_order.json', ordered)
        for eid in ordered:
            fetch.check()
            attempts_before = len(fetch.log)
            try:
                url = 'https://service.geonet.org.nz/fdsnws/event/1/query?' + urllib.parse.urlencode({'eventid': eid})
                xml = fetch.fetch(url, eid+'.xml', 4*MIB)
                outcomes[eid] = parse_quakeml(xml, eid)
            except LimitReached as exc:
                if len(fetch.log) > attempts_before:
                    outcomes[eid] = {'event_id': eid, 'status': 'incomplete', 'error': str(exc)}
                raise
            except Exception as exc:
                outcomes[eid] = {'event_id': eid, 'status': 'failed', 'error': type(exc).__name__+': '+str(exc)[:200]}
            dump(out / 'outcomes.json', outcomes)
        state['completed'] = True
    except Exception as exc:
        state['stop_reason'] = type(exc).__name__+': '+str(exc)[:200]
        code = 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        dump(out / 'requests.json', fetch.log)
        state.update(elapsed_seconds=fetch.clock()-fetch.started, response_body_bytes=fetch.bytes, request_attempts=len(fetch.log))
        dump(out / 'outcomes.json', outcomes)
        dump(out / 'summary.json', summarize(rows, groups, outcomes))
        state['files'] = {str(p.relative_to(out)): {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                          for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'manifest.json'}
        dump(out / 'manifest.json', state)
    print(json.dumps({'completed': state['completed'], 'request_attempts': len(fetch.log), 'response_body_bytes': fetch.bytes, 'elapsed_seconds': state['elapsed_seconds']}))
    return code


def validate_output(path):
    allowed = Path(__file__).resolve().parent / 'local_runs'
    if allowed.is_symlink():
        raise ValueError('local_runs must not be a symlink')
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed) or resolved == allowed:
        raise ValueError('output must resolve beneath this helper local_runs directory')
    return resolved


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bootstrap', type=Path, help='verified source-only header-failure run; preserves original caps')
    parser.add_argument('--recovery-plan', type=Path, help='frozen, reviewed one-window recovery execution manifest')
    args = parser.parse_args()
    # Prevent putting real data inside a reviewer or a broadly committed code directory.
    try:
        destination = validate_output(args.output)
    except ValueError as exc:
        parser.error(str(exc))
    sys.exit(run(destination, args.bootstrap, args.recovery_plan))

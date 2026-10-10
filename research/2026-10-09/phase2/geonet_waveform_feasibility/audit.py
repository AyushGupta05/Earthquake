#!/usr/bin/env python3
"""Prepare or execute the small frozen audit. Acquisition requires parent receipt."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import warnings
import core

BASE = Path(__file__).resolve().parent
# ObsPy may import Matplotlib while evaluating responses; keep its cache local.
os.environ['MPLCONFIGDIR'] = str(BASE/'.runtime-cache/matplotlib')
CENSUS_SHA = '076c9fcb419b801c91fa95a01cec21f708284887f6dfae8e7878b513ba1780b8'
BINDINGS = ('audit.py', 'core.py', 'PROTOCOL_v1.md', 'census_input_pins.json')


class AuditDeadline(Exception):
    pass


class ResponseEvidenceError(ValueError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence=evidence


def outer_alarm(signum, frame):
    raise AuditDeadline('complete collect invocation reached 1800-second limit')


def bounded_bytes(path, limit=32*1024*1024):
    with path.open('rb') as handle:
        body = handle.read(limit+1)
    if len(body) > limit:
        raise ValueError('local validation input exceeds size bound')
    return body


def sha(body):
    return hashlib.sha256(body).hexdigest()


def dump(path, obj, exclusive=False):
    with path.open('x' if exclusive else 'w') as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False); f.write('\n')


def local_path(path):
    allowed = BASE/'local_runs'
    if allowed.is_symlink():
        raise ValueError('local_runs symlink forbidden')
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed) or resolved == allowed:
        raise ValueError('real output must remain under this local_runs')
    return resolved


def census_inputs(root):
    expected = json.loads((BASE/'census_input_pins.json').read_text())
    objects = {}
    for name, pin in expected.items():
        body = bounded_bytes(root/name)
        if sha(body) != pin:
            raise ValueError('census input checksum mismatch: '+name)
        objects[name] = json.loads(body)
    if not objects['manifest.json']['completed'] or not objects['summary.json']['practical_gate_observed_support']:
        raise ValueError('census prerequisites failed')
    return objects, expected


def requests_for(events):
    result = []
    for event in events:
        for station in event['stations']:
            if not station['queryable']:
                continue
            common = {'network': station['network'], 'station': station['station'],
                      'location': station['location'] or '--', 'channel': station['prefix']+'?',
                      'starttime': core.iso(event['t0_ns']-5*core.NS), 'endtime': core.iso(event['t0_ns']+5*core.NS)}
            for kind, extra in (('station', {'level': 'response', 'format': 'xml'}),
                                ('dataselect', {'format': 'miniseed'})):
                result.append({'event_id': event['event_id'], 'station': station['station'], 'kind': kind,
                               'file': f'{len(result):03d}.'+('xml' if kind == 'station' else 'mseed'),
                               'url': 'https://service.geonet.org.nz/fdsnws/'+kind+'/1/query?'+urllib.parse.urlencode(common|extra)})
    if len(result) > 36:
        raise ValueError('too many planned queries')
    return result


def prepare(census_root, output):
    inputs, pins = census_inputs(census_root)
    events = core.choose(inputs['groups.json'], inputs['outcomes.json'])
    plan = {'version': core.VERSION, 'input_root': str(census_root.resolve()), 'input_pins': pins,
            'events': events, 'requests': requests_for(events),
            'source_files': {n: sha((BASE/n).read_bytes()) for n in BINDINGS},
            'limits': {'seconds': 1800, 'requests': 100, 'body_bytes': 128*1024*1024},
            'created_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    output = local_path(output); output.parent.mkdir(parents=True, exist_ok=True)
    dump(output, plan, exclusive=True)
    return {'plan_sha256': sha(output.read_bytes()), 'events': len(events),
            'stations': sum(len(e['stations']) for e in events), 'planned_queries': len(plan['requests']),
            'band_years': {str(b): [e['year'] for e in events if e['band_lower'] == b] for b in (5.5, 6, 7)}}


def validate_execution(plan_path, receipt_path):
    plan_path = local_path(plan_path)
    plan_body = bounded_bytes(plan_path, 1024*1024); plan = json.loads(plan_body)
    receipt = json.loads(bounded_bytes(receipt_path, 1024*1024))
    if (receipt.get('acquisition_authorized') is not True
            or not re.fullmatch('[0-9a-f]{40}', receipt.get('parent_pre_acquisition_commit', ''))
            or receipt.get('plan_sha256') != sha(plan_body)
            or receipt.get('code_only_review_clean') is not True):
        raise ValueError('parent reviewed Git-freeze receipt missing or mismatched')
    files = {n: sha((BASE/n).read_bytes()) for n in BINDINGS}
    if receipt.get('source_files') != files or plan.get('source_files') != files:
        raise ValueError('source/protocol binding changed')
    if plan.get('version') != core.VERSION or plan.get('limits') != {'seconds': 1800, 'requests': 100, 'body_bytes': 128*1024*1024}:
        raise ValueError('frozen limits/version changed')
    inputs, pins = census_inputs(Path(plan['input_root']))
    events = core.choose(inputs['groups.json'], inputs['outcomes.json'])
    if plan.get('input_pins') != pins or plan.get('events') != events or plan.get('requests') != requests_for(events):
        raise ValueError('metadata selection/query list changed')
    dependency_body = (BASE/'dependency_receipt.json').read_bytes()
    dependency = json.loads(dependency_body)
    if (receipt.get('dependency_receipt_sha256') != sha(dependency_body)
            or dependency.get('synthetic_adapter_smoke_passed') is not True
            or dependency.get('obsPy_version') != '1.5.1'
            or dependency.get('python_executable') != str(Path(sys.executable).absolute())):
        raise ValueError('dependency/synthetic adapter prerequisite missing')
    import obspy
    import numpy
    if obspy.__version__ != dependency['obsPy_version'] or numpy.__version__ != dependency['numpy_version']:
        raise ValueError('runtime versions changed')
    if (sha((BASE/'requirements.lock').read_bytes()) != dependency['dependency_lock_sha256']
            or sha((BASE/'dependency_wheels_receipt.json').read_bytes()) != dependency['published_wheels_receipt_sha256']):
        raise ValueError('frozen dependency lock/wheel receipt changed')
    for name, version in dependency['installed_resolved_packages'].items():
        dist=importlib.metadata.distribution(name)
        if (dist.version != version
                or not Path(dist.locate_file('')).absolute().is_relative_to(BASE/'.venv')):
            raise ValueError('resolved workspace-local dependency changed: '+name)
    return plan


def downloader():
    path = BASE.parent/'geonet_tail_census/census.py'
    if sha(path.read_bytes()) != CENSUS_SHA:
        raise ValueError('reviewed downloader dependency changed')
    spec = importlib.util.spec_from_file_location('bounded_census_downloader', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def inventory_records(inventory):
    def numeric(value):
        # Missing metadata is validated after identity/epoch selection. An unrelated
        # or entirely future channel must not invalidate the observed prefix.
        try: return float(value)
        except (TypeError, ValueError): return float('nan')
    result = []
    for network in inventory:
        for station in network:
            for channel in station:
                starts = [x.ns for x in (network.start_date, station.start_date, channel.start_date) if x is not None]
                ends = [x.ns for x in (network.end_date, station.end_date, channel.end_date) if x is not None]
                result.append({'network': network.code, 'station': station.code, 'location': channel.location_code,
                               'code': channel.code, 'start_ns': max(starts) if starts else None,
                               'channel_start_known':channel.start_date is not None,
                               'end_ns': min(ends) if ends else None, 'sample_rate': numeric(channel.sample_rate),
                               'dip': numeric(channel.dip), 'azimuth': numeric(channel.azimuth), 'response': channel.response})
    return result


def response_evidence(channel, budget_exception=None):
    evidence={'warnings':[], 'full_transfer_response_available':False,'physically_calibrated_prefix_verified':False}
    try:
        response = channel['response']
        if response is None or not response.response_stages or response.instrument_sensitivity is None:
            raise ValueError('missing full transfer response/sensitivity')
        sensitivity = response.instrument_sensitivity
        gain, freq = float(sensitivity.value), float(sensitivity.frequency)
        units = str(sensitivity.input_units).upper().replace(' ', '').replace('**', '^')
        output = str(sensitivity.output_units).upper().replace(' ', '')
        if (not math.isfinite(gain) or gain <= 0 or not math.isfinite(freq) or not 0 < freq < channel['sample_rate']/2
                or units not in ('M', 'M/S', 'M/S^2') or output not in ('COUNT', 'COUNTS')):
            raise ValueError('invalid sensitivity/frequency/physical or count units')
        evidence.update(input_units=units,output_units=output,sensitivity=gain,reference_frequency=freq,response_stages=len(response.response_stages))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            try:
                transfer = complex(response.get_evalresp_response_for_frequencies([freq], output='DEF')[0])
            finally:
                evidence['warnings']=[str(w.message) for w in caught]
        magnitude=abs(transfer); ratio=magnitude/gain
        if (not math.isfinite(transfer.real) or not math.isfinite(transfer.imag)
                or not math.isfinite(magnitude) or magnitude == 0 or not math.isfinite(ratio)):
            raise ValueError('nonfinite/zero transfer response or nonfinite sensitivity ratio')
        evidence.update(transfer_magnitude_at_reference=magnitude,reference_to_sensitivity_ratio=ratio,full_transfer_response_available=True)
        return evidence
    except Exception as exc:
        if budget_exception is not None and isinstance(exc,budget_exception):raise
        evidence['error']=type(exc).__name__+': '+str(exc)[:300]
        raise ResponseEvidenceError(evidence['error'],evidence) from exc


def stream_pieces(stream, target, code):
    pieces = []
    for trace in stream:
        st = trace.stats
        if (st.network, st.station, st.location, st.channel) != (target['network'], target['station'], target['location'], code):
            continue
        metadata = getattr(st, 'mseed', {})
        blockette = metadata.get('blkt1001', {})
        pieces.append({'start_ns': st.starttime.ns, 'sample_rate': float(st.sampling_rate), 'data': trace.data,
                       'timing_quality': blockette.get('timing_quality') if hasattr(blockette, 'get') else None,
                       'calibration_type': metadata.get('calibration_type')})
    return pieces


def analyze(inventory, stream, event, target, budget_exception=None):
    records = inventory_records(inventory); result = {}
    for horizon in (1, 3, 5):
        left = event['t0_ns']-5*core.NS; deadline = event['t0_ns']+horizon*core.NS
        responses={}
        try:
            channels = core.triplet(records, target, left, deadline)
            for c in channels:
                try: responses[c['code']]=response_evidence(c,budget_exception)
                except ResponseEvidenceError as exc:
                    responses[c['code']]=exc.evidence;raise
            components = {c['code']: core.component(stream_pieces(stream, target, c['code']), left, deadline, c['sample_rate']) for c in channels}
            aligned = core.compatible_lattices(components, channels[0]['sample_rate'])
            result[str(horizon)] = {'status': 'audited', 'components': components, 'responses': responses,
                'three_component_prefix_available': aligned, 'component_sample_lattices_compatible': aligned,
                'clipping_screen_passed': all(c.get('clipping_screen_passed', False) for c in components.values()),
                'retrospective_station_pick_before_deadline': target['pick_ns'] < deadline,
                'physically_calibrated_prefix_verified': False, 'operational_picker_replayed': False}
        except Exception as exc:
            if budget_exception is not None and isinstance(exc, budget_exception):
                raise
            result[str(horizon)] = {'status': 'failed', 'error': type(exc).__name__+': '+str(exc)[:300], 'responses':responses}
    return result


def worker(plan_path, receipt_path, out):
    plan = validate_execution(plan_path, receipt_path)
    from obspy import read, read_inventory
    module = downloader(); out = local_path(out); out.mkdir(parents=True, exist_ok=False); raw = out/'raw'; raw.mkdir()
    fetch = module.Fetcher(raw, max_seconds=1800, max_requests=100, max_bytes=128*1024*1024, request_alarm=True)
    signal.signal(signal.SIGALRM, module.alarm_handler); signal.setitimer(signal.ITIMER_REAL, 1800)
    state = {'completed': False, 'plan_sha256': sha(plan_path.read_bytes()), 'parent_receipt_sha256': sha(receipt_path.read_bytes())}
    outcomes=[{'event_id':event['event_id'], 'station':target['station'], 'status':'unattempted'} for event in plan['events'] for target in event['stations']]; code=2
    dump(out/'outcomes.json', outcomes)
    request_index = 0
    target_index = 0
    try:
        for event in plan['events']:
            for target in event['stations']:
                row = outcomes[target_index]; target_index += 1
                if not target['queryable']:
                    row.update(status='unqueryable', error=target['unqueryable_reason']); continue
                rq_xml, rq_wave = plan['requests'][request_index:request_index+2]; request_index += 2
                row['status']='stationxml_attempting'; dump(out/'outcomes.json',outcomes)
                try:
                    xml_body = fetch.fetch(rq_xml['url'], rq_xml['file'], 4*1024*1024)
                except module.LimitReached:
                    row.update(status='incomplete_stationxml',waveform_unattempted=True); raise
                except Exception as exc:
                    row.update(status='stationxml_retrieval_failed', waveform_unattempted=True, error=type(exc).__name__+': '+str(exc)[:300]); dump(out/'outcomes.json', outcomes); continue
                try:
                    row['status']='waveform_attempting'; dump(out/'outcomes.json',outcomes)
                    body = fetch.fetch(rq_wave['url'], rq_wave['file'], 8*1024*1024)
                    # Public APIs only. Crop summaries independently after decoding.
                    xml_text = xml_body.decode('utf-8-sig')
                    if '\x00' in xml_text or '<!DOCTYPE' in xml_text.upper() or '<!ENTITY' in xml_text.upper():
                        raise ValueError('unsupported encoding or DTD/entity in StationXML')
                    inventory = read_inventory(io.BytesIO(xml_body), format='STATIONXML')
                    headers = read(io.BytesIO(body), format='MSEED', headonly=True, details=True)
                    if sum(int(tr.stats.npts)*8 for tr in headers) > 64*1024*1024:
                        raise ValueError('declared miniSEED decoded sample memory exceeds 64MiB')
                    stream = read(io.BytesIO(body), format='MSEED', details=True)
                    row.update(status='decoded', horizons=analyze(inventory, stream, event, target, module.LimitReached))
                except module.LimitReached:
                    row['status']='incomplete_waveform_or_audit'; raise
                except Exception as exc:
                    row.update(status='waveform_or_decode_failed', error=type(exc).__name__+': '+str(exc)[:300])
                dump(out/'outcomes.json', outcomes)
        state['completed']=True; code=0
    except Exception as exc:
        state['stop_reason']=type(exc).__name__+': '+str(exc)[:300]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        dump(out/'requests.json', fetch.log); dump(out/'outcomes.json', outcomes)
        state.update(elapsed_seconds=fetch.clock()-fetch.started, request_attempts=len(fetch.log), response_body_bytes=fetch.bytes,
                     files={str(p.relative_to(out)):{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(out.rglob('*')) if p.is_file()})
        dump(out/'manifest.json', state)
    return code


def collect(plan_path, receipt_path, out):
    started=time.monotonic(); process=None; plan=None; valid_output=None
    old_handler=signal.signal(signal.SIGALRM, outer_alarm)
    signal.setitimer(signal.ITIMER_REAL, 1800)
    try:
        out = local_path(out)
        if out.exists(): raise ValueError('output already exists; no resume/overwrite')
        valid_output=out
        plan = validate_execution(plan_path, receipt_path)
        remaining=1800-(time.monotonic()-started)
        if remaining <= 0: raise AuditDeadline('validation exhausted outer deadline')
        args=[sys.executable, '-B', str(BASE/'audit.py'), 'worker', '--plan', str(plan_path), '--receipt', str(receipt_path), '--output', str(out)]
        # Capture evalresp's native stderr as well as Python warnings retained per response.
        log_path=local_path(out.parent/(out.name+'.worker.log'))
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('xb') as log:
            process=subprocess.Popen(args, start_new_session=True, stdout=log, stderr=subprocess.STDOUT)
            code=process.wait(timeout=remaining)
        if code:
            out.mkdir(parents=True, exist_ok=True)
            dump(out/'PROCESS_INCOMPLETE.json', {'completed':False,'exit_code':code,
                'frozen_station_denominator':sum(len(e['stations']) for e in plan['events']),
                'horizons':[1,3,5], 'feasibility_result':'incomplete; retained rows are partial'})
        return code
    except (subprocess.TimeoutExpired, AuditDeadline, KeyboardInterrupt):
        signal.setitimer(signal.ITIMER_REAL, 0)
        if process is not None:
            os.killpg(process.pid, signal.SIGKILL); process.wait()
        if valid_output is not None:
            valid_output.mkdir(parents=True, exist_ok=True)
            dump(valid_output/'OUTER_INCOMPLETE.json', {'completed':False,'reason':'outer deadline/cancellation',
                'elapsed_seconds':time.monotonic()-started,
                'frozen_station_denominator':sum(len(e['stations']) for e in plan['events']) if plan else None,
                'horizons':[1,3,5], 'feasibility_result':'incomplete; retained rows are partial, never a completed rate'})
        return 2
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='mode', required=True)
    p=sub.add_parser('prepare'); p.add_argument('--census-root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    for name in ('collect', 'worker'):
        p=sub.add_parser(name); p.add_argument('--plan',type=Path,required=True); p.add_argument('--receipt',type=Path,required=True); p.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.mode=='prepare': print(json.dumps(prepare(args.census_root, args.output)))
    else: sys.exit((collect if args.mode=='collect' else worker)(args.plan,args.receipt,args.output))

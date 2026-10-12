"""Independent fresh decoder/routing/view replay of the frozen public contract."""
import hashlib
import time
from fractions import Fraction
import header_scanner
from geometry import header_grid, crop, pair
from native_decode import decode_record,ObservedDecodeFailure
from plan_validation import validate, STUDY
from routing import route, nominal_suffixes
from sample_proofs import dtype_code, digest, stats, aggregate_stats
from strict import Reject,canonical,sha,keys,integer

CLAIMS = ('physically_calibrated', 'full_response_verified', 'physical_axes_verified',
          'raw_clock_truth_verified', 'online_availability_verified', 'sequence_independence_verified',
          'usable_model_support_verified', 'accuracy_improved', 'novelty_verified',
          'published_superiority_verified', 'hardware_clipping_verified')
VIEW_KEYS = ('record', 'lo', 'hi', 'count', 'first', 'last', 'period', 'dtype', 'samples_sha256')
MAX_PRIVATE = 67_108_864
MAX_SAMPLES=8_000_000
MAX_TOTAL_SAMPLES=104_000_000
HEADROOM=8*1024*1024


class Fatal(Exception):
    pass


def fraction(value):
    return Fraction(value[0], value[1])


def unknown_component(channel, reason):
    return {'channel': channel, 'status': 'unknown', 'reason': reason, 'count': 0,
            'rate': None, 'first': None, 'last': None, 'finite': None,
            'metadata_rate_match': None, 'minimum': None, 'maximum': None,
            'flat': None, 'extreme_run': None, 'view_sha256': None, 'pieces': []}


def component(channel, pieces, row, horizon, observed):
    if not pieces:
        return unknown_component(channel, 'no_samples_in_window' if observed else 'missing_component')
    pieces.sort(key=lambda p: (fraction(p['first']), fraction(p['last']), p['record']))
    rates = {Fraction(1_000_000_000) / fraction(p['period']) for p in pieces}
    rate = next(iter(rates)) if len(rates) == 1 else None
    first = fraction(pieces[0]['first']); last = fraction(pieces[-1]['last'])
    amplitude = aggregate_stats(pieces)
    reason = 'supported'
    if not amplitude['finite']:
        reason = 'nonfinite'
    elif rate is None:
        reason = 'mixed_rate'
    else:
        period = Fraction(1_000_000_000) / rate
        tolerance = min(Fraction(1000), period / 100)
        left = row['t0_ns'] - 3_000_000_000; right = row['t0_ns'] + horizon * 1_000_000_000
        if not (0 <= first - left < period and 0 < right - last <= period):
            reason = 'edge'
        elif any(abs(fraction(b['first']) - fraction(a['last']) - period) > tolerance for a, b in zip(pieces, pieces[1:])):
            reason = 'gap_overlap'
        elif any(min((fraction(p['first']) - first) % period,
                     period - ((fraction(p['first']) - first) % period)) > tolerance for p in pieces):
            reason = 'phase'
    expected = row['nominal_rates'].get(channel)
    metadata = rate == fraction(expected) if rate is not None and expected is not None else None
    view = [{k: p[k] for k in VIEW_KEYS} for p in pieces]
    return {'channel': channel, 'status': 'complete' if reason == 'supported' else 'incomplete',
            'reason': reason, 'count': sum(p['count'] for p in pieces), 'rate': pair(rate) if rate is not None else None,
            'first': pair(first), 'last': pair(last), 'metadata_rate_match': metadata,
            'view_sha256': sha(canonical(view)), 'pieces': pieces, **amplitude}


def joint(row, components):
    if not row['queryable']:return {'status':'unknown','reason':'selection_unknown','rate':None,'channels':[]}
    suffixes = nominal_suffixes(row['family'])
    if suffixes is None:
        return {'status': 'unknown', 'reason': 'metadata_unknown', 'rate': None, 'channels': []}
    channels = [row['prefix'] + s for s in suffixes]
    required = [next(c for c in components if c['channel'] == channel) for channel in channels]
    status, reason, rate = 'complete', 'supported', None
    if any(c['status'] == 'unknown' for c in required):
        status, reason = 'unknown', 'component_unknown'
    elif any(c['status'] == 'incomplete' for c in required):
        status, reason = 'incomplete', 'component_incomplete'
    elif len({tuple(c['rate']) for c in required}) != 1:
        status, reason = 'incomplete', 'joint_rate'
    else:
        rate = required[0]['rate']
        period = Fraction(1_000_000_000) / fraction(rate)
        tolerance = min(Fraction(1000), period / 100)
        origin = fraction(required[0]['first'])
        if any(min((fraction(c['first']) - origin) % period,
                   period - ((fraction(c['first']) - origin) % period)) > tolerance for c in required):
            status, reason = 'incomplete', 'joint_phase'
    return {'status': status, 'reason': reason, 'rate': rate, 'channels': channels}


def build_rows(plan, batches, observed, views, fatal=False):
    rows = []
    for row in plan['rows']:
        batch = batches[row['batch']]
        channels = set(observed[row['ordinal']])
        suffixes = nominal_suffixes(row['family'])
        if suffixes: channels.update(row['prefix'] + s for s in suffixes)
        cells = []
        for horizon in (1, 3, 5):
            if not row['queryable']:components=[]
            elif fatal or batch['status'] != 'decoded':
                reason = 'transport_nonpositive' if not fatal and batch['status'] == 'nonpositive' else 'batch_unknown'
                components = [unknown_component(channel, reason) for channel in sorted(channels)]
            else:
                components = [component(channel, views.get((row['ordinal'], horizon, channel), []), row, horizon,
                                        channel in observed[row['ordinal']]) for channel in sorted(channels)]
            cells.append({'horizon': horizon, 'cutoff_ns': row['t0_ns']+horizon*1_000_000_000 if row['t0_ns'] is not None else None,
                          'pick_before_cutoff': row['pick_ns']<row['t0_ns']+horizon*1_000_000_000 if row['queryable'] else None,
                          'components': components, 'joint': joint(row, components)})
        rows.append({'ordinal':row['ordinal'],'global_ordinal':row['global_ordinal'],'partition': row['partition'], 'batch': row['batch'],
                     'family': row['family'], 'cells': cells})
    return rows


def aggregate(rows, batches):
    horizons = []
    for index, horizon in enumerate((1, 3, 5)):
        complete = [row for row in rows if row['cells'][index]['joint']['status'] == 'complete']
        horizons.append({'horizon': horizon, 'complete_joint': len(complete),
                         'train_complete_joint': sum(row['partition'] == 'TRAIN' for row in complete),
                         'dev_complete_joint': sum(row['partition'] == 'DEV' for row in complete),
                         'complete_joint_pick_before_cutoff': sum(row['cells'][index]['pick_before_cutoff'] for row in complete),
                         'complete_components': sum(c['status'] == 'complete' for row in rows for c in row['cells'][index]['components']),
                         'metadata_unknown_complete_components': sum(c['status'] == 'complete' for row in rows if row['family'] is None for c in row['cells'][index]['components'])})
    queryable=sum(r['cells'][0]['joint']['reason']!='selection_unknown' for r in rows)
    known=sum(r['family'] is not None for r in rows)
    return {'rows':50,'train':50,'dev':0,'cells':150,'batches':13,'queryable_rows':queryable,'no_target_rows':50-queryable,
            'metadata_known':known,'metadata_unknown':50-known, 'horizons': horizons,
            'batch_statuses': {status: sum(b['status'] == status for b in batches) for status in ('decoded', 'unknown', 'nonpositive')}}


def replay(plan, body_reader, decoder=decode_record, wall_seconds=300):
    """Fresh replay. External custody/runtime/cgroup checks are prerequisites.

    body_reader(ordinal, expected_bytes) returns bounded bytes; zero/nonpositive
    entries are never read. The injected decoder is only for invented tests.
    """
    validate(plan)
    began = time.monotonic()
    batches = [{'ordinal': n, 'status': 'unknown', 'reason': 'decode_unknown', 'record_count': 0,
                'advertised_samples': 0, 'observed_samples': 0} for n in range(13)]
    records = []; observed = {n: set() for n in range(50)}; views = {}
    advertised_total = observed_total = 0
    evidence_bytes = 0
    disposition,reason='complete','supported';batch=None
    try:
        for batch_plan in plan['batches']:
            if time.monotonic() - began > wall_seconds: raise Fatal('wall_timeout')
            n = batch_plan['ordinal']; batch = batches[n]
            if batch_plan['transport'] != 'http200':
                batch.update(status='nonpositive', reason='transport_nonpositive'); continue
            raw = body_reader(n, batch_plan['body_bytes'])
            if type(raw) is not bytes or len(raw) != batch_plan['body_bytes'] or sha(raw) != batch_plan['body_sha256']:
                raise Fatal('runtime_failure')
            ledger = header_scanner.scan(raw)
            if ledger['disposition'] != 'supported':
                if ledger['reason'] == 'sample_cap': raise Fatal('sample_cap')
                if ledger['reason'] == 'output_cap': raise Fatal('output_cap')
                batch.update(reason='structural_unknown'); continue
            batch['record_count'] = ledger['record_count']; batch['advertised_samples'] = ledger['advertised_samples']
            advertised_total += ledger['advertised_samples']
            if advertised_total > MAX_TOTAL_SAMPLES: raise Fatal('sample_cap')
            batch_rows = [plan['rows'][i] for i in batch_plan['rows']]
            batch.update(status='decoded', reason='supported')
            for descriptor in ledger['records']:
                if time.monotonic() - began > wall_seconds: raise Fatal('wall_timeout')
                try: start, rate = header_grid(descriptor)
                except (Reject, ValueError, OverflowError):
                    batch.update(status='unknown', reason='timing_unknown'); break
                record_raw = raw[descriptor['offset']:descriptor['offset'] + descriptor['length']]
                data=None
                def charge(amount):
                    nonlocal observed_total
                    if type(amount) is not int or not 0<=amount<=2**63-1:raise Fatal('runtime_failure')
                    batch['observed_samples']+=amount;observed_total+=amount
                    if batch['observed_samples']>MAX_SAMPLES or observed_total>MAX_TOTAL_SAMPLES:raise Fatal('sample_cap')
                try:
                    if descriptor['npts']:
                        response=decoder(record_raw,descriptor,start,rate)
                        # A returned scalar sequence is counted before field/type/time reconciliation.
                        data=response['values']
                        charge(len(data))
                        keys(response,('start_ns','rate','dtype','values'))
                        integer(response['start_ns'],-2**63,2**63-1)
                        from geometry import rate_agrees
                        if response['start_ns']!=start or type(response['rate']) is not float or not rate_agrees(response['rate'],rate):raise Reject('observed_clock_rate')
                        if type(data) is list:
                            import numpy as np
                            if type(response['dtype']) is not str or response['dtype'] not in ('i4','f4','f8'):raise Reject('observed_dtype')
                            data=np.asarray(data,dtype=response['dtype'])
                        code=dtype_code(data)
                        expected_code={1:'i4',3:'i4',4:'f4',5:'f8',10:'i4',11:'i4'}[descriptor['encoding']]
                        if response['dtype']!=expected_code or code!=expected_code or len(data)!=descriptor['npts']:raise Reject('observed_dtype_count')
                    else:code='empty'
                except ObservedDecodeFailure as failure:
                    charge(failure.observed_samples)
                    batch.update(status='unknown',reason='decode_unknown');data=None;break
                except ValueError:
                    batch.update(status='unknown',reason='decode_unknown');data=None;break
                count=descriptor['npts']
                routes = route(descriptor['nslc'], batch_rows)
                record = {'batch': n, 'ordinal': descriptor['ordinal'], 'offset': descriptor['offset'],
                          'length': descriptor['length'], 'nslc': list(descriptor['nslc']), 'encoding': descriptor['encoding'],
                          'word_order': descriptor['word_order'], 'raw_sha256': sha(record_raw),
                          'start_ns': start, 'rate': pair(rate), 'period': pair(Fraction(1_000_000_000) / rate),
                          'advertised_samples': count, 'observed_samples': count,
                          'decoded_start_ns': start if count else None, 'dtype': code,
                          'samples_sha256': digest(data, code) if count else sha(b'empty\0'),
                          'finite': bool(__import__('numpy').isfinite(data).all()) if count else True,
                          'routed_rows': routes}
                addition=len(canonical(record))+64
                if evidence_bytes + addition > MAX_PRIVATE-HEADROOM: raise Fatal('output_cap')
                records.append(record); evidence_bytes += addition
                if not routes:
                    batch.update(status='unknown', reason='unexpected_identity'); break
                for row_ordinal in routes:
                    row = plan['rows'][row_ordinal]; channel = descriptor['nslc'][3]
                    observed[row_ordinal].add(channel)
                    if not count: continue
                    for horizon in (1, 3, 5):
                        lo, hi, period = crop(start, rate, count, row['t0_ns'] - 3_000_000_000, row['t0_ns'] + horizon * 1_000_000_000)
                        if hi <= lo: continue
                        piece = {'record': descriptor['ordinal'], 'lo': lo, 'hi': hi, 'count': hi - lo,
                                 'first': pair(Fraction(start) + lo * period), 'last': pair(Fraction(start) + (hi - 1) * period),
                                 'period': pair(period), 'dtype': code, 'samples_sha256': digest(data[lo:hi], code),
                                 **stats(data[lo:hi])}
                        addition=len(canonical(piece))+64
                        if evidence_bytes + addition > MAX_PRIVATE-HEADROOM: raise Fatal('output_cap')
                        evidence_bytes += addition
                        views.setdefault((row_ordinal, horizon, channel), []).append(piece)
                del data, record_raw
            del raw, ledger
    except Fatal as failure:
        disposition,reason='incomplete',str(failure)
        if batch is not None:batch.update(status='unknown',reason='decode_unknown')
    except Exception:
        disposition,reason='incomplete','runtime_failure'
        if batch is not None:batch.update(status='unknown',reason='decode_unknown')
    rows = build_rows(plan, batches, observed, views, disposition == 'incomplete')
    if time.monotonic() - began > wall_seconds:
        disposition, reason = 'incomplete', 'wall_timeout'
        rows = build_rows(plan, batches, observed, {}, True)
    result = {'schema':'geonet-TRAIN50-prefix-qualification-v1', 'study': STUDY, 'disposition': disposition,
              'reason': reason, 'batches': batches, 'records': records, 'rows': rows,
              'aggregate': aggregate(rows, batches), 'claims': {key: False for key in CLAIMS}}
    if len(canonical(result)) > MAX_PRIVATE:
        # A cap failure cannot leak a success-shaped oversized document.
        rows = build_rows(plan, batches, observed, {}, True)
        result.update(disposition='incomplete', reason='output_cap', rows=rows, aggregate=aggregate(rows, batches))
        while len(canonical(result))>MAX_PRIVATE and result['records']:result['records'].pop()
        if len(canonical(result))>MAX_PRIVATE:raise Reject('bounded_result_unavailable')
    if len(canonical(result['aggregate'])) > 65_536: raise Reject('aggregate_cap')
    if result['disposition']=='complete' and time.monotonic()-began>wall_seconds:
        rows=build_rows(plan,batches,observed,{},True);result.update(disposition='incomplete',reason='wall_timeout',rows=rows,aggregate=aggregate(rows,batches))
    return result

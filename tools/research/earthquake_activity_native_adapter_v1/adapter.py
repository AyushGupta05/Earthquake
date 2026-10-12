"""Verify selected native TRAIN record/views before receiver-activity extraction."""
from fractions import Fraction
import hashlib
import math
import time

import activity
import producer

SCHEMA = 'earthquake-activity-native-adapter-v1'
MAX_SECONDS = 300
MAX_PRIVATE = 16 * 1024 * 1024
PIECE_KEYS = ('record', 'lo', 'hi', 'count', 'first', 'last', 'period', 'dtype', 'samples_sha256')


class InvalidInput(ValueError):
    pass


class UnsupportedNativeGrid(Exception):
    pass


def need(condition, code):
    if not condition:
        raise InvalidInput(code)


def same(left, right):
    return producer.canonical(left) == producer.canonical(right)


def keys(value, fields):
    return type(value) is dict and set(value) == set(fields) and all(type(k) is str for k in value)


def deadline(started):
    need(time.monotonic() - started <= MAX_SECONDS, 'wall_timeout')


def inputs(plan, qualified, bodies, metadata, external):
    producer.validate(plan, bodies)
    need(keys(qualified, ('schema', 'study', 'disposition', 'reason', 'batches', 'records', 'rows', 'aggregate', 'claims')), 'qualified_schema')
    need(qualified['schema'] == 'geonet-POST-prefix-qualification-v2' and qualified['study'] == plan['study']
         and qualified['disposition'] == 'complete' and qualified['reason'] == 'supported', 'qualified_identity')
    need(type(qualified['claims']) is dict and set(qualified['claims']) == set(producer._CLAIMS)
         and all(v is False for v in qualified['claims'].values()), 'claim')
    need(type(qualified['rows']) is list and len(qualified['rows']) == 65
         and type(qualified['records']) is list and len(qualified['records']) <= 17 * 32768
         and type(qualified['batches']) is list and len(qualified['batches']) == 17, 'qualified_accounting')
    need(type(metadata) is list and len(metadata) == 65, 'metadata')
    need(keys(external, ('grouping_frozen', 'prior_support_floor_pass'))
         and all(type(v) is bool for v in external.values()), 'external')
    for slot, (row, qrow, meta) in enumerate(zip(plan['rows'], qualified['rows'], metadata)):
        need(keys(meta, ('slot', 'mw', 'group', 'group_eligible')) and type(meta['slot']) is int
             and meta['slot'] == slot and type(meta['mw']) in (int, float)
             and math.isfinite(meta['mw']) and -5 <= meta['mw'] <= 15
             and (meta['group'] is None or type(meta['group']) is str and 1 <= len(meta['group']) <= 128)
             and type(meta['group_eligible']) is bool, 'metadata')
        need(keys(qrow, ('ordinal', 'partition', 'batch', 'family', 'cells'))
             and all(same(qrow[k], row[k]) for k in ('ordinal', 'partition', 'batch', 'family'))
             and type(qrow['cells']) is list and len(qrow['cells']) == 3, 'row_binding')
        for horizon, cell in zip((1, 3, 5), qrow['cells']):
            need(keys(cell, ('horizon', 'cutoff_ns', 'pick_before_cutoff', 'components', 'joint'))
                 and same(cell['horizon'], horizon) and same(cell['cutoff_ns'], row['t0_ns'] + horizon * 10**9)
                 and same(cell['pick_before_cutoff'], row['pick_ns'] < cell['cutoff_ns'])
                 and type(cell['components']) is list and type(cell['joint']) is dict
                 and cell['joint'].get('status') in ('complete', 'incomplete', 'unknown'), 'cell_binding')
    indexes = {}
    for record in qualified['records']:
        need(type(record) is dict and type(record.get('batch')) is int and 0 <= record['batch'] < 17
             and type(record.get('ordinal')) is int and 0 <= record['ordinal'] < 32768, 'record_schema')
        key = (record['batch'], record['ordinal'])
        need(key not in indexes, 'duplicate_record')
        indexes[key] = record
    return indexes


def reconstruct(plan, row, qrow, records, bodies, decoder, started):
    required = producer.channels(row)
    views = []
    record_ids = set()
    for cell in qrow['cells']:
        codes = [c.get('channel') for c in cell['components'] if type(c) is dict]
        need(len(codes) == len(cell['components']) and len(set(codes)) == len(codes), 'component_schema')
        by_code = {c['channel']: c for c in cell['components']}
        selected = []
        for code in required:
            need(code in by_code, 'missing_component')
            component = by_code[code]
            need(component.get('status') == 'complete' and type(component.get('pieces')) is list
                 and 1 <= len(component['pieces']) <= 32768, 'component_support')
            for piece in component['pieces']:
                need(type(piece) is dict and type(piece.get('record')) is int and 0 <= piece['record'] < 32768, 'piece_schema')
                record_ids.add(piece['record'])
            selected.append(component)
        views.append(selected)
    raw = bodies[row['batch']]
    need(type(raw) is bytes, 'body')
    ledger = producer.scanner.scan(raw)
    need(ledger['disposition'] == 'supported', 'header_scan')
    descriptors = {d['ordinal']: d for d in ledger['records']}
    expected_ids = set()
    for d in ledger['records']:
        if d['nslc'][:3] == [row[k] for k in ('network', 'station', 'location')] and d['nslc'][3] in required:
            start, rate, period = producer.header_grid(d)
            lo = max(0, producer._ceil((Fraction(row['t0_ns'] - 3 * 10**9) - start) / period))
            hi = min(d['npts'], producer._ceil((Fraction(row['t0_ns'] + 5 * 10**9) - start) / period))
            if hi > lo:
                # Do not widen or approximate the frozen activity representation.
                if period.numerator > 10**12 or period.denominator > 10**9:
                    raise UnsupportedNativeGrid()
                expected_ids.add(d['ordinal'])
    need(record_ids == expected_ids, 'record_coverage')
    decoded = {}
    total = 0
    for ordinal in sorted(record_ids):
        deadline(started)
        key = (row['batch'], ordinal)
        need(key in records and ordinal in descriptors, 'missing_record')
        record, descriptor = records[key], descriptors[ordinal]
        start, rate, period = producer.header_grid(descriptor)
        expected_route = [i for i in plan['batches'][row['batch']]['rows']
                          if descriptor['nslc'][:3] == [plan['rows'][i][k] for k in ('network', 'station', 'location')]
                          and descriptor['nslc'][3][:2] == plan['rows'][i]['prefix']]
        for field, value in (('offset', descriptor['offset']), ('length', descriptor['length']),
                             ('nslc', descriptor['nslc']), ('encoding', descriptor['encoding']),
                             ('word_order', descriptor['word_order']), ('start_ns', start),
                             ('rate', producer.pair(rate)), ('period', producer.pair(period)),
                             ('advertised_samples', descriptor['npts']), ('routed_rows', expected_route)):
            need(field in record and same(record[field], value), 'record_binding')
        need(row['ordinal'] in expected_route and descriptor['nslc'][3] in required, 'record_route')
        rbytes = raw[descriptor['offset']:descriptor['offset'] + descriptor['length']]
        need(record.get('raw_sha256') == hashlib.sha256(rbytes).hexdigest(), 'raw_hash')
        value = decoder(rbytes, descriptor)
        need(keys(value, ('start_ns', 'rate', 'dtype', 'values')), 'decoder_schema')
        need(type(value['start_ns']) is int and value['start_ns'] == start
             and type(value['rate']) is float and math.isfinite(value['rate']) and value['rate'] > 0
             and abs(Fraction.from_float(value['rate']) - rate) <= max(Fraction(1, 10**12), rate / 10**12), 'decoder_grid')
        dtype = {1: 'i4', 3: 'i4', 4: 'f4', 5: 'f8', 10: 'i4', 11: 'i4'}[descriptor['encoding']]
        values = value['values']
        need(value['dtype'] == dtype and len(values) == descriptor['npts']
             and same(record.get('observed_samples'), len(values))
             and same(record.get('decoded_start_ns'), start) and record.get('dtype') == dtype, 'decoder_samples')
        total += len(values)
        need(total <= 8_000_000 and len(decoded) < 32768, 'sample_cap')
        need(producer.sample_hash(values, dtype) == record.get('samples_sha256'), 'sample_hash')
        decoded[ordinal] = (descriptor['nslc'][3], start, period, dtype, values)
    for horizon, components in zip((1, 3, 5), views):
        for component in components:
            rebuilt = []
            for ordinal, (code, start, period, dtype, values) in decoded.items():
                if code == component['channel']:
                    piece = producer._piece(ordinal, values, dtype, start, period,
                                            row['t0_ns'] - 3 * 10**9, row['t0_ns'] + horizon * 10**9)
                    if piece is not None:
                        rebuilt.append(piece)
            rebuilt.sort(key=lambda p: (Fraction(*p['first']), Fraction(*p['last']), p['record']))
            need(same(rebuilt, component['pieces']), 'piece_replay')
            composition = [{k: p[k] for k in PIECE_KEYS} for p in rebuilt]
            need(hashlib.sha256(producer.canonical(composition)).hexdigest() == component.get('view_sha256'), 'view_hash')
            expected = producer._component(component['channel'], rebuilt, row, horizon,
                                           {'status': 'decoded'}, set(required))
            need(same(component, expected), 'component_replay')
        need(same(qrow['cells'][(1, 3, 5).index(horizon)]['joint'], producer._joint(row, components)), 'joint_replay')
    components = []
    for code in required:
        pieces = []
        for ordinal, (name, start, period, dtype, values) in sorted(decoded.items(), key=lambda item: (item[1][1], item[0])):
            if name == code:
                scalars = [int(v) if dtype == 'i4' else float(v) for v in values]
                pieces.append({'start_ns': start, 'rational_period': producer.pair(period), 'values': scalars})
        components.append({'name': code, 'pieces': pieces})
    deadline(started)
    return components, len(decoded)


def denied_result(row, meta, support):
    # No clocks are substituted to make an unsupported event fit another API.
    return {'schema': 'activity-event-v1', 'slot': row['ordinal'],
            'partition': row['partition'], 'family': row['family'],
            'mw': float(meta['mw']), 'group': meta['group'],
            'external_support_asserted': list(support),
            'external_group_eligible_asserted': meta['group_eligible'],
            'all_horizon_eligible': False,
            'horizons': [activity._unknown(h, 'DEFERRED_DEV' if row['partition'] == 'DEV' else 'UNSUPPORTED')
                         for h in (1, 3, 5)]}


def run(plan, qualified_v2, bodies, decode_record, metadata, external):
    """Pure source invocation; parent owns actual execution and audit authority."""
    started = time.monotonic()
    records = inputs(plan, qualified_v2, bodies, metadata, external)
    need(callable(decode_record), 'decoder')
    results, decoded_count, denials = [], 0, []
    for row, qrow, meta in zip(plan['rows'], qualified_v2['rows'], metadata):
        deadline(started)
        support = [cell['joint']['status'] == 'complete' for cell in qrow['cells']]
        eligible = (row['partition'] == 'TRAIN' and all(support) and row['family'] is not None
                    and meta['group'] is not None and meta['group_eligible']
                    and row['pick_ns'] >= row['t0_ns']
                    and row['pick_ns'] + 250_000_000 <= row['t0_ns'] + 10**9)
        components = None
        native_grid_unsupported = False
        if eligible:
            try:
                components, count = reconstruct(plan, row, qrow, records, bodies, decode_record, started)
                decoded_count += count
            except UnsupportedNativeGrid:
                native_grid_unsupported = True
        event = {'slot': row['ordinal'], 'partition': row['partition'], 't0_ns': row['t0_ns'],
                 'p_ns': row['pick_ns'], 'family': row['family'], 'mw': meta['mw'],
                 'group': meta['group'], 'components': components}
        if row['pick_ns'] < row['t0_ns'] or native_grid_unsupported:
            result = denied_result(row, meta, support)
            denials.append({'slot': row['ordinal'], 'reason': 'pre_t0_pick' if row['pick_ns'] < row['t0_ns'] else 'activity_period_bound'})
        else:
            result = activity.extract_event(event, {'horizon_support': support, 'group_eligible': meta['group_eligible']})
        results.append(result)
        del event
        components = None
    summary = activity.summarize(results, external)
    output = {'schema': SCHEMA, 'results': results, 'summary': summary, 'decoded_train_records': decoded_count, 'adapter_denials': denials,
              'claims': {'fit_authorized': False, 'physical_interpretation_verified': False,
                         'accuracy_improved': False, 'novelty_verified': False, 'published_superiority_verified': False}}
    need(len(producer.canonical(output)) <= MAX_PRIVATE, 'output_cap')
    deadline(started)
    return output

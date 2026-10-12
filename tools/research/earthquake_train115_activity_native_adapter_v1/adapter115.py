"""NEW115 pure integration; immutable old scalars, fresh TRAIN50 native replay."""
from fractions import Fraction
import hashlib
import math
import time

import activity115
import old_activity
import native_core

SCHEMA = 'earthquake-train115-activity-native-adapter-v1'
MAX_SECONDS = 300
MAX_PRIVATE = 16 * 1024 * 1024
MAX_PUBLIC = 64 * 1024
MAX_OBSERVED_TOTAL = 400_000_000
PIECE_KEYS = ('record', 'lo', 'hi', 'count', 'first', 'last', 'period', 'dtype', 'samples_sha256')
CLAIMS = ('fit_authorized', 'physical_interpretation_verified', 'accuracy_improved',
          'novelty_verified', 'published_superiority_verified')


class InvalidInput(ValueError):
    pass


class UnsupportedNativeGrid(Exception):
    pass


def need(condition, code):
    if not condition:
        raise InvalidInput(code)


def same(left, right):
    return native_core.canonical(left) == native_core.canonical(right)


def keys(value, fields):
    return type(value) is dict and set(value) == set(fields) and all(type(k) is str for k in value)


def deadline(started):
    need(time.monotonic() - started <= MAX_SECONDS, 'wall_timeout')


def charge(count, current, budget):
    need(type(count) is int and 0 <= count <= 2**63-1, 'observed_accounting_invalid')
    current += count
    budget['observed_samples'] += count
    need(current <= 8_000_000 and budget['observed_samples'] <= MAX_OBSERVED_TOTAL, 'sample_cap')
    return current


def inputs(old, plan, qualified, bodies, metadata, external, bindings):
    need(keys(bindings, ('old_packet_sha256', 'new_plan_sha256', 'new_qualified_sha256', 'metadata115_sha256')), 'bindings')
    for name, value in (('old_packet', old), ('new_plan', plan), ('new_qualified', qualified), ('metadata115', metadata)):
        encoded = native_core.canonical(value)
        need(len(encoded) <= (64 * 1024 * 1024 if name == 'new_qualified' else MAX_PRIVATE), 'input_cap')
        need(native_core._sha(bindings[name + '_sha256']) and hashlib.sha256(encoded).hexdigest() == bindings[name + '_sha256'], 'input_pin')
    need(keys(external, ('grouping_frozen', 'prior_support_floor_pass')) and all(type(v) is bool for v in external.values()), 'external')
    need(type(metadata) is list and len(metadata) == 115, 'metadata')
    for slot, meta in enumerate(metadata):
        need(keys(meta, ('slot', 'mw', 'group', 'group_eligible')) and type(meta['slot']) is int and meta['slot'] == slot
             and type(meta['mw']) in (int, float) and math.isfinite(meta['mw']) and -5 <= meta['mw'] <= 15
             and (meta['group'] is None or type(meta['group']) is str and 1 <= len(meta['group']) <= 128)
             and type(meta['group_eligible']) is bool, 'metadata')
    need(keys(old, ('schema', 'results', 'summary', 'decoded_train_records', 'adapter_denials', 'claims'))
         and type(old['schema']) is str and old['schema'] == 'earthquake-activity-native-adapter-v1', 'old_packet')
    need(keys(old['claims'], CLAIMS) and all(v is False for v in old['claims'].values()), 'old_claim')
    old_external = {'grouping_frozen': old['summary'].get('external_grouping_frozen_asserted'),
                    'prior_support_floor_pass': old['summary'].get('external_prior_support_floor_asserted')}
    need(same(old_activity.summarize(old['results'], old_external), old['summary']), 'old_summary')
    need(type(old['decoded_train_records']) is int and 0 <= old['decoded_train_records'] <= 41 * 32768, 'old_count')
    need(type(old['adapter_denials']) is list and len(old['adapter_denials']) <= 65, 'old_denials')
    seen = set()
    for denial in old['adapter_denials']:
        need(keys(denial, ('slot', 'reason')) and type(denial['slot']) is int and 0 <= denial['slot'] < 65
             and denial['slot'] not in seen and type(denial['reason']) is str
             and denial['reason'] in ('pre_t0_pick', 'activity_period_bound')
             and not old['results'][denial['slot']]['all_horizon_eligible'], 'old_denials')
        seen.add(denial['slot'])
    for result, meta in zip(old['results'], metadata[:65]):
        need(same(result['mw'], float(meta['mw'])) and same(result['group'], meta['group'])
             and same(result['external_group_eligible_asserted'], meta['group_eligible']), 'old_metadata_binding')
        if result['partition'] == 'DEV':
            need(all(c['status'] == 'DEFERRED_DEV' for c in result['horizons']), 'dev_deferred')
    native_core.validate(plan, bodies)
    need(keys(qualified, ('schema', 'study', 'disposition', 'reason', 'batches', 'records', 'rows', 'aggregate', 'claims')), 'qualified_schema')
    need(qualified['schema'] == 'geonet-TRAIN50-prefix-qualification-v1' and qualified['study'] == plan['study']
         and qualified['disposition'] == 'complete' and qualified['reason'] == 'supported', 'qualified_identity')
    need(keys(qualified['claims'], native_core._CLAIMS) and all(v is False for v in qualified['claims'].values()), 'claim')
    need(type(qualified['rows']) is list and len(qualified['rows']) == 50
         and type(qualified['records']) is list and len(qualified['records']) <= 13 * 32768
         and type(qualified['batches']) is list and len(qualified['batches']) == 13, 'qualified_accounting')
    for row, qrow in zip(plan['rows'], qualified['rows']):
        need(keys(qrow, ('ordinal', 'global_ordinal', 'partition', 'batch', 'family', 'cells'))
             and all(same(qrow[k], row[k]) for k in ('ordinal', 'global_ordinal', 'partition', 'batch', 'family'))
             and type(qrow['cells']) is list and len(qrow['cells']) == 3, 'row_binding')
        for horizon, cell in zip((1, 3, 5), qrow['cells']):
            cutoff = None if row['t0_ns'] is None else row['t0_ns'] + horizon * 10**9
            before = None if not row['queryable'] else row['pick_ns'] < cutoff
            need(keys(cell, ('horizon', 'cutoff_ns', 'pick_before_cutoff', 'components', 'joint'))
                 and same(cell['horizon'], horizon) and same(cell['cutoff_ns'], cutoff)
                 and same(cell['pick_before_cutoff'], before) and type(cell['components']) is list
                 and keys(cell['joint'], ('status', 'reason', 'rate', 'channels'))
                 and type(cell['joint']['status']) is str and cell['joint']['status'] in ('complete', 'incomplete', 'unknown'), 'cell_binding')
            if not row['queryable']:
                need(cell['components'] == [] and same(cell['joint'], {'status':'unknown','reason':'selection_unknown','rate':None,'channels':[]}), 'no_selection_binding')
    need(same(qualified['aggregate'], native_core._aggregate(qualified['rows'], qualified['batches'], plan)), 'aggregate')
    indexes = {}
    for record in qualified['records']:
        need(type(record) is dict and type(record.get('batch')) is int and 0 <= record['batch'] < 13
             and type(record.get('ordinal')) is int and 0 <= record['ordinal'] < 32768, 'record_schema')
        key = (record['batch'], record['ordinal'])
        need(key not in indexes, 'duplicate_record')
        indexes[key] = record
    return indexes


def reconstruct(plan, row, qrow, records, bodies, decoder, started, budget):
    required = native_core.channels(row)
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
    ledger = native_core.scanner.scan(raw)
    need(ledger['disposition'] == 'supported', 'header_scan')
    descriptors = {d['ordinal']: d for d in ledger['records']}
    expected_ids = set()
    for d in ledger['records']:
        if d['nslc'][:3] == [row[k] for k in ('network', 'station', 'location')] and d['nslc'][3] in required:
            start, rate, period = native_core.header_grid(d)
            lo = max(0, native_core._ceil((Fraction(row['t0_ns'] - 3 * 10**9) - start) / period))
            hi = min(d['npts'], native_core._ceil((Fraction(row['t0_ns'] + 5 * 10**9) - start) / period))
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
        start, rate, period = native_core.header_grid(descriptor)
        expected_route = [i for i in plan['batches'][row['batch']]['rows']
                          if plan['rows'][i]['queryable'] and descriptor['nslc'][:3] == [plan['rows'][i][k] for k in ('network', 'station', 'location')]
                          and descriptor['nslc'][3][:2] == plan['rows'][i]['prefix']]
        for field, value in (('offset', descriptor['offset']), ('length', descriptor['length']),
                             ('nslc', descriptor['nslc']), ('encoding', descriptor['encoding']),
                             ('word_order', descriptor['word_order']), ('start_ns', start),
                             ('rate', native_core.pair(rate)), ('period', native_core.pair(period)),
                             ('advertised_samples', descriptor['npts']), ('routed_rows', expected_route)):
            need(field in record and same(record[field], value), 'record_binding')
        need(row['ordinal'] in expected_route and descriptor['nslc'][3] in required, 'record_route')
        rbytes = raw[descriptor['offset']:descriptor['offset'] + descriptor['length']]
        need(record.get('raw_sha256') == hashlib.sha256(rbytes).hexdigest(), 'raw_hash')
        try:
            value = decoder(rbytes, descriptor)
        except ValueError as failure:
            if hasattr(failure, 'observed_samples'):
                total = charge(failure.observed_samples, total, budget)
            raise InvalidInput('decode_failure') from None
        # Charge received lengths before schema/grid/dtype/hash reconciliation.
        if type(value) is dict and 'values' in value:
            total = charge(len(value['values']), total, budget)
        else:
            raise InvalidInput('decoder_schema')
        need(keys(value, ('start_ns', 'rate', 'dtype', 'values')), 'decoder_schema')
        need(type(value['start_ns']) is int and value['start_ns'] == start
             and type(value['rate']) is float and math.isfinite(value['rate']) and value['rate'] > 0
             and abs(Fraction.from_float(value['rate']) - rate) <= max(Fraction(1, 10**12), rate / 10**12), 'decoder_grid')
        dtype = {1: 'i4', 3: 'i4', 4: 'f4', 5: 'f8', 10: 'i4', 11: 'i4'}[descriptor['encoding']]
        values = value['values']
        need(value['dtype'] == dtype and len(values) == descriptor['npts']
             and same(record.get('observed_samples'), len(values))
             and same(record.get('decoded_start_ns'), start) and record.get('dtype') == dtype, 'decoder_samples')
        need(len(decoded) < 32768, 'piece_cap')
        need(native_core.sample_hash(values, dtype) == record.get('samples_sha256'), 'sample_hash')
        decoded[ordinal] = (descriptor['nslc'][3], start, period, dtype, values)
    for horizon, components in zip((1, 3, 5), views):
        for component in components:
            rebuilt = []
            for ordinal, (code, start, period, dtype, values) in decoded.items():
                if code == component['channel']:
                    piece = native_core._piece(ordinal, values, dtype, start, period,
                                            row['t0_ns'] - 3 * 10**9, row['t0_ns'] + horizon * 10**9)
                    if piece is not None:
                        rebuilt.append(piece)
            rebuilt.sort(key=lambda p: (Fraction(*p['first']), Fraction(*p['last']), p['record']))
            need(same(rebuilt, component['pieces']), 'piece_replay')
            composition = [{k: p[k] for k in PIECE_KEYS} for p in rebuilt]
            need(hashlib.sha256(native_core.canonical(composition)).hexdigest() == component.get('view_sha256'), 'view_hash')
            expected = native_core._component(component['channel'], rebuilt, row, horizon,
                                           {'status': 'decoded'}, set(required))
            need(same(component, expected), 'component_replay')
        need(same(qrow['cells'][(1, 3, 5).index(horizon)]['joint'], native_core._joint(row, components)), 'joint_replay')
    components = []
    for code in required:
        pieces = []
        for ordinal, (name, start, period, dtype, values) in sorted(decoded.items(), key=lambda item: (item[1][1], item[0])):
            if name == code:
                scalars = [int(v) if dtype == 'i4' else float(v) for v in values]
                pieces.append({'start_ns': start, 'rational_period': native_core.pair(period), 'values': scalars})
        components.append({'name': code, 'pieces': pieces})
    deadline(started)
    return components, len(decoded)


def denied_result(row, meta, support):
    return {'schema':'activity-event-v1', 'slot':row['global_ordinal'], 'partition':'TRAIN', 'family':row['family'],
            'mw':float(meta['mw']), 'group':meta['group'], 'external_support_asserted':list(support),
            'external_group_eligible_asserted':meta['group_eligible'], 'all_horizon_eligible':False,
            'horizons':[activity115._unknown(h, 'UNSUPPORTED') for h in (1,3,5)]}


def panel(results):
    return {'events':len(results), 'horizon_cells':3*len(results),
            'all_horizon_train':sum(r['partition']=='TRAIN' and r['all_horizon_eligible'] for r in results),
            'status_counts':{key:sum(r['partition']+':'+str(c['seconds'])+':'+c['status']==key for r in results for c in r['horizons'])
                             for key in sorted({r['partition']+':'+str(c['seconds'])+':'+c['status'] for r in results for c in r['horizons']})}}


def run(old_packet, new_plan, new_qualified, new_bodies, decode_record, metadata115, external, bindings):
    """Pure invocation after parent's positively bound private custody/resource gate."""
    started = time.monotonic()
    records = inputs(old_packet, new_plan, new_qualified, new_bodies, metadata115, external, bindings)
    need(callable(decode_record), 'decoder')
    results = list(old_packet['results'])
    decoded_count, denials = 0, []
    budget = {'observed_samples':0}
    for row, qrow, meta in zip(new_plan['rows'], new_qualified['rows'], metadata115[65:]):
        deadline(started)
        support = [c['joint']['status']=='complete' for c in qrow['cells']]
        selection_unknown = not row['queryable']
        pre_t0 = not selection_unknown and row['pick_ns'] < row['t0_ns']
        eligible = (not selection_unknown and all(support) and row['family'] is not None
                    and meta['group'] is not None and meta['group_eligible'] and not pre_t0
                    and row['pick_ns'] + 250_000_000 <= row['t0_ns'] + 10**9)
        components, native_grid_unsupported = None, False
        if eligible:
            try:
                components, count = reconstruct(new_plan, row, qrow, records, new_bodies, decode_record, started, budget)
                decoded_count += count
            except UnsupportedNativeGrid:
                native_grid_unsupported = True
        if selection_unknown or pre_t0 or native_grid_unsupported:
            result = denied_result(row, meta, support)
            denials.append({'slot':row['global_ordinal'], 'reason':'selection_unknown' if selection_unknown else
                            'pre_t0_pick' if pre_t0 else 'activity_period_bound'})
        else:
            event = {'slot':row['global_ordinal'], 'partition':'TRAIN', 't0_ns':row['t0_ns'], 'p_ns':row['pick_ns'],
                     'family':row['family'], 'mw':meta['mw'], 'group':meta['group'], 'components':components}
            result = activity115.extract_event(event, {'horizon_support':support, 'group_eligible':meta['group_eligible']})
            del event
        results.append(result)
        components = None
    summary = activity115.summarize(results, external)
    output = {'schema':SCHEMA, 'results':results, 'summary':summary, 'old_summary':old_packet['summary'],
              'support_panels':{'original65':panel(results[:65]), 'new50':panel(results[65:])},
              'decoded_new_train_records':decoded_count, 'observed_new_train_samples':budget['observed_samples'],
              'new_adapter_denials':denials, 'claims':{k:False for k in CLAIMS}}
    need(len(native_core.canonical(output)) <= MAX_PRIVATE, 'output_cap')
    need(len(native_core.canonical({'summary':summary, 'support_panels':output['support_panels']})) <= MAX_PUBLIC, 'public_cap')
    deadline(started)
    return output

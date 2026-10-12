"""Pure fixed65/17 POST receipt replay bound to the final authored public contract.

Only caller-supplied exact bytes and a named bounded callback are processed.
No filesystem, network, acquisition, waveforms, vendor code, or actual authority.
"""
from datetime import datetime, timedelta, timezone
import re

from strict_inputs import Invalid, boolean, decode, digest, fields, integer, need, number, same, sha, text

PROTOCOL = 'geonet-train-dev-prefix-POST-transport-v1'
STUDY = 'geonet-original-TRAINDEV65-prefix3-native-POST-v2'
AUDIT_PROTOCOL = 'geonet-train-dev-prefix-POST-independent-audit-v1'
PROPOSAL_SHA = 'd1fde0107ec473d0452d6354100052a1f7ce716f06bf22af047055cbd87e8f45'
ROW_COUNT = 65
BATCH_COUNT = 17
MAX_PLAN = 131072
MAX_JSON = 1048576
MAX_MANIFEST = 65536
MAX_SUMMARY = 65536
MIN_NS = -(1 << 63)
MAX_NS = (1 << 63) - 1
LIMITS = dict(connection_s=10.0, first_body_s=60.0, request_s=120.0, start_spacing_s=1.0,
              processing_s=2160.0, whole_s=2400.0, term_s=5.0, kill_s=5.0,
              body_bytes=8388608, total_retained_bytes=142606336, probe_bytes=1,
              total_consumption_upper=142606353, request_bytes=16384,
              header_diagnostic_bytes=131072)
CLAIMS = dict.fromkeys(('waveform_rows_qualified', 'scientific_coverage_verified',
                       'metadata_http204_repaired', 'full_response_verified', 'physical_axes_verified',
                       'calibration_verified', 'operational_availability_verified',
                       'sequence_independence_verified', 'model_input_verified',
                       'magnitude_improvement_verified', 'novelty_verified',
                       'published_benchmark_superiority_verified'), False)
PREREQUISITES = ('original_projection_sha256', 'frozen_roster_sha256', 'metadata_custody_sha256',
                 'first_queryable_selection_proof_sha256', 'no_exact_complete_success_cache_proof_sha256')
ROW_FIELDS = {'row_index', 'original_event_index', 'original_target_index', 'event_id', 'partition',
              'network', 'station', 'location', 'prefix', 't0_ns', 'pick_ns',
              'metadata_status', 'nominal_family'}
BATCH_BASE = {'batch_index', 'row_indices', 'request', 'status'}
ATTEMPT_FIELDS = {'request_index', 'start', 'end', 'connected_at', 'headers_at', 'first_body_at',
                  'http_status', 'framing', 'declared', 'outcome', 'body', 'headers',
                  'framing_evidence', 'framing_evidence_complete',
                  'observed_bytes', 'overflow_probe_bytes', 'consumed_upper', 'consumption_exact',
                  'worker_group', 'worker_exit_code', 'worker_exit_confirmed',
                  'worker_group_stop_confirmed', 'attempt_accounting_complete', 'HTTP200_candidate'}
INITIAL_FIELDS = {'protocol', 'study_id', 'plan_sha256', 'fixture', 'limits', 'begin', 'claims', 'batches'}
CONTROLLER_FIELDS = INITIAL_FIELDS | {'processing_elapsed', 'attempts', 'retained_bytes',
                                     'overflow_probe_bytes', 'consumption_upper',
                                     'HTTP200_candidates', 'candidate_complete', 'worker_groups'}
RECEIPT_FIELDS = {'protocol', 'study_id', 'plan_sha256', 'complete', 'reason', 'fixture', 'limits',
                  'begin', 'elapsed_s', 'controller_exit_code', 'controller_group_stop_confirmed',
                  'request_groups_stop_confirmed', 'registered_attempts', 'controller_summary_sha256',
                  'result_manifest_sha256', 'claims'}
SUMMARY_FIELDS = {'protocol', 'complete', 'reason', 'begin', 'returned_at', 'elapsed_s',
                  'manifest_sha256', 'receipt_sha256', 'controller_group_stop_confirmed',
                  'request_groups_stop_confirmed', 'registered_attempts', 'public_aggregate'}
AGGREGATE_FIELDS = {'rows', 'TRAIN_rows', 'DEV_rows', 'metadata_unknown_rows', 'nominal_ENZ_rows',
                    'nominal_12Z_rows', 'batches', 'attempted_batches', 'unattempted_batches',
                    'accounting_complete_batches', 'HTTP200_candidate_batches', 'qualified_batches',
                    'retained_response_bytes', 'overflow_probe_bytes', 'consumption_upper',
                    'accounting_known', 'whole_complete', 'claims'}
OUTCOMES = {'framed_complete', 'overflow', 'partial', 'framing_error', 'connection_deadline',
            'first_body_deadline', 'request_deadline', 'processing_deadline', 'worker_error', 'worker_exit'}
REASONS = {'complete', 'incomplete', 'deadline', 'controller_failed', 'group_stop_unconfirmed',
           'finalization_failed'}
FIXED = {'roster.private.json', 'initial.private.json', 'controller_summary.private.json',
         'receipt.private.json', 'public_aggregate.json'}
REQUESTS = tuple(f'{i:03d}.request.private' for i in range(BATCH_COUNT))
JOURNALS = tuple(f'{i:03d}.batch.private.json' for i in range(BATCH_COUNT))
BODIES = tuple(f'{i:03d}.body.private' for i in range(BATCH_COUNT))
FRAMINGS = tuple(f'{i:03d}.framing.private' for i in range(BATCH_COUNT))
HEADERS = tuple(f'{i:03d}.headers.private.json' for i in range(BATCH_COUNT))
REQUIRED = FIXED | set(REQUESTS) | set(JOURNALS)
ALLOWED = REQUIRED | set(BODIES) | set(HEADERS) | set(FRAMINGS)


def utc_ns(ns):
    integer(ns, 'utc_ns', MIN_NS, MAX_NS)
    seconds, nanos = divmod(ns, 1000000000)
    dt = datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    return dt.strftime('%Y-%m-%dT%H:%M:%S') + f'.{nanos:09d}Z'


def canonical_entity(rows):
    lines = ['format=miniseed']
    for row in rows:
        lines.append(' '.join((row['network'], row['station'], row['location'] or '--',
                               row['prefix'] + '?', utc_ns(row['t0_ns'] - 3000000000),
                               utc_ns(row['t0_ns'] + 5000000000))))
    return ('\n'.join(lines) + '\n').encode('ascii')


def _ascii(value, pattern, label):
    need(type(value) is str and re.fullmatch(pattern, value) is not None, label)
    return value


def _plan(raw):
    plan = decode(raw, MAX_PLAN, 'plan')
    fields(plan, {'protocol', 'study_id', 'proposal_sha256', 'rows', 'batches', 'prerequisites'}, 'plan_fields')
    text(plan['protocol'], PROTOCOL, 'plan_protocol')
    text(plan['study_id'], STUDY, 'plan_study')
    text(plan['proposal_sha256'], PROPOSAL_SHA, 'plan_proposal')
    fields(plan['prerequisites'], PREREQUISITES, 'prerequisite_fields')
    for field in PREREQUISITES:
        sha(plan['prerequisites'][field], 'prerequisite_pin')
    rows = plan['rows']
    need(type(rows) is list and len(rows) == ROW_COUNT, 'plan_row_count')
    partitions = {'TRAIN': 0, 'DEV': 0}
    families = {'ENZ': 0, '12Z': 0}
    unknown = 0
    previous = -1
    events = set()
    for i, row in enumerate(rows):
        fields(row, ROW_FIELDS, 'plan_row_fields')
        need(integer(row['row_index'], 'row_index', 0, 64) == i, 'row_order')
        event_index = integer(row['original_event_index'], 'original_event_index', 0, 95)
        need(event_index > previous, 'original_event_order')
        previous = event_index
        integer(row['original_target_index'], 'original_target_index', 0, 1000000)
        event = _ascii(row['event_id'], r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', 'event_id')
        need(event not in events, 'duplicate_event_id')
        events.add(event)
        partition = row['partition']
        need(type(partition) is str and partition in partitions, 'partition')
        partitions[partition] += 1
        _ascii(row['network'], r'[A-Z0-9]{1,8}', 'network')
        _ascii(row['station'], r'[A-Z0-9]{1,8}', 'station')
        _ascii(row['location'], r'[A-Z0-9]{0,2}', 'location')
        _ascii(row['prefix'], r'[A-Z0-9]{2}', 'prefix')
        t0 = integer(row['t0_ns'], 't0_ns', MIN_NS + 3000000000, MAX_NS - 5000000000)
        integer(row['pick_ns'], 'pick_ns', MIN_NS, MAX_NS)
        need(type(row['metadata_status']) is str, 'metadata_status')
        if row['metadata_status'] == 'http204_unknown':
            need(row['nominal_family'] is None, 'unknown_family')
            unknown += 1
        else:
            text(row['metadata_status'], 'positive', 'metadata_status')
            family = row['nominal_family']
            need(type(family) is str and family in families, 'positive_family')
            families[family] += 1
    need(partitions == {'TRAIN': 41, 'DEV': 24} and families == {'ENZ': 47, '12Z': 14}
         and unknown == 4, 'plan_fixed_denominator')
    batches = plan['batches']
    need(type(batches) is list and len(batches) == BATCH_COUNT, 'plan_batch_count')
    for i, batch in enumerate(batches):
        fields(batch, {'batch_index', 'row_indices', 'request_body', 'request_sha256'}, 'plan_batch_fields')
        need(integer(batch['batch_index'], 'batch_index', 0, 16) == i, 'batch_order')
        indices = list(range(4 * i, min(4 * i + 4, ROW_COUNT)))
        need(same(batch['row_indices'], indices), 'batch_membership')
        body = canonical_entity([rows[n] for n in indices])
        need(type(batch['request_body']) is str and batch['request_body'] == body.decode('ascii'), 'request_entity')
        sha(batch['request_sha256'], 'request_sha')
        need(len(body) <= LIMITS['request_bytes'] and batch['request_sha256'] == digest(body), 'request_entity_pin')
    return plan


def _cap(name):
    if name in BODIES:
        return LIMITS['body_bytes']
    if name in HEADERS or name in FRAMINGS:
        return LIMITS['header_diagnostic_bytes']
    if name in REQUESTS:
        return LIMITS['request_bytes']
    if name == 'roster.private.json':
        return MAX_PLAN
    if name == 'initial.private.json':
        return 65536
    if name in JOURNALS or name in ('receipt.private.json', 'public_aggregate.json'):
        return 16384
    return MAX_JSON


def _pin(pin, label, *, named=True):
    fields(pin, {'name', 'bytes', 'sha256'} if named else {'bytes', 'sha256'}, label)
    if named:
        need(type(pin['name']) is str and pin['name'] in ALLOWED, label + '_name')
    integer(pin['bytes'], label + '_bytes')
    sha(pin['sha256'], label + '_sha')
    return pin


def _claims(claims):
    fields(claims, CLAIMS, 'claims_fields')
    need(all(claims[field] is False for field in CLAIMS), 'claim_not_false')


def _limits(limits):
    fields(limits, LIMITS, 'limits_fields')
    for field, expected in LIMITS.items():
        if type(expected) is int:
            integer(limits[field], 'limit_integer')
        else:
            number(limits[field], 'limit_number')
        need(limits[field] == expected, 'limit_changed')


def _common(value, plan, plan_sha):
    text(value['protocol'], PROTOCOL, 'receipt_protocol')
    text(value['study_id'], STUDY, 'receipt_study')
    text(value['plan_sha256'], plan_sha, 'receipt_plan_sha')
    need(value['fixture'] is False, 'fixture_not_production')
    _limits(value['limits'])
    _claims(value['claims'])
    number(value['begin'], 'begin')


def _aggregate(actual, *, attempts, accounting, candidates, retained, probes, upper, complete):
    fields(actual, AGGREGATE_FIELDS, 'aggregate_fields')
    fixed = {'rows': 65, 'TRAIN_rows': 41, 'DEV_rows': 24, 'metadata_unknown_rows': 4,
             'nominal_ENZ_rows': 47, 'nominal_12Z_rows': 14, 'batches': 17}
    expected = {**fixed, 'attempted_batches': attempts, 'unattempted_batches': 17 - attempts,
                'accounting_complete_batches': accounting, 'HTTP200_candidate_batches': candidates,
                'qualified_batches': candidates if complete else 0,
                'retained_response_bytes': retained, 'overflow_probe_bytes': probes,
                'consumption_upper': upper}
    for field, value in expected.items():
        need(integer(actual[field], 'aggregate_integer') == value, 'aggregate_disagreement')
    need(actual['accounting_known'] is True, 'aggregate_accounting_not_known')
    need(actual['whole_complete'] is complete, 'aggregate_complete')
    _claims(actual['claims'])


def _header(header, row):
    fields(header, {'status', 'framing', 'declared', 'fields', 'parser_limits'}, 'header_fields')
    integer(header['status'], 'header_http_status', 100, 999)
    integer(row['http_status'], 'retained_row_http_status', 100, 999)
    fields(header['parser_limits'], {'line_bytes', 'header_count', 'chunk_trailer_count'}, 'parser_limits_fields')
    need(integer(header['parser_limits']['line_bytes'], 'parser_line') == 65536 and
         integer(header['parser_limits']['header_count'], 'parser_count') == 100 and
         integer(header['parser_limits']['chunk_trailer_count'], 'parser_trailer_count') == 100, 'parser_limits_changed')
    pairs = header['fields']
    need(type(pairs) is list and len(pairs) <= 100, 'header_pair_bound')
    lengths, encodings = [], []
    for pair in pairs:
        need(type(pair) is list and len(pair) == 2 and all(type(v) is str for v in pair), 'header_pair_type')
        if pair[0].casefold() == 'content-length':
            lengths.append(pair[1])
        if pair[0].casefold() == 'transfer-encoding':
            encodings.append(pair[1])
    declared, framing = None, 'unknown'
    invalid = row['http_status'] < 200 or len(lengths) > 1 or len(encodings) > 1 or bool(lengths and encodings)
    if lengths:
        invalid = invalid or re.fullmatch(r'[0-9]{1,20}', lengths[0]) is None
    if encodings:
        invalid = invalid or encodings[0].casefold() != 'chunked'
    if not invalid and row['http_status'] is not None:
        declared = int(lengths[0]) if lengths else None
        if row['http_status'] in (204, 304):
            framing = 'no_body'
        else:
            framing = 'fixed' if lengths else 'chunked' if encodings else 'eof'
    need(same(header['status'], row['http_status']) and same(header['framing'], row['framing']) and
         same(header['declared'], row['declared']), 'header_row_disagreement')
    need(header['framing'] == framing and same(header['declared'], declared), 'header_framing_disagreement')


def _closed_chunks(raw, observed):
    """Replay payload-free syntax and associate sizes with ordered body offsets.

    False preserves malformed/partial bounded evidence without qualification.
    No advertised size allocates memory or controls a read of payload bytes.
    """
    need(type(raw) is bytes and len(raw) <= LIMITS['header_diagnostic_bytes'], 'chunk_evidence_bound')
    position = 0
    body_position = 0
    def line():
        nonlocal position
        ending = raw.find(b'\r\n', position)
        if ending < 0 or ending + 2 - position > 65536:
            return None
        token = raw[position:ending]
        position = ending + 2
        return token
    while True:
        token = line()
        if token is None or re.fullmatch(rb'[0-9A-Fa-f]{1,16}(?:;[\x20-\x7e]*)?', token) is None:
            return False
        size = int(token.split(b';', 1)[0], 16)
        if size:
            body_position += size
            if body_position > observed or raw[position:position + 2] != b'\r\n':
                return False
            position += 2
            continue
        for _ in range(100):
            trailer = line()
            if trailer is None:
                return False
            if trailer == b'':
                return position == len(raw) and body_position == observed
            if re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+:[\x09\x20-\x7e]*", trailer) is None:
                return False
        return False


def _registered(value):
    need(type(value) is list and len(value) <= 17, 'registered_attempts')
    groups = []
    for i, row in enumerate(value):
        fields(row, {'batch_index', 'worker_group'}, 'registered_fields')
        need(integer(row['batch_index'], 'registered_index', 0, 16) == i, 'registered_order')
        group = integer(row['worker_group'], 'registered_group', 1)
        need(group not in groups, 'registered_group_duplicate')
        groups.append(group)
    return groups


def _unknown_aggregate(value, attempts):
    fields(value, AGGREGATE_FIELDS, 'aggregate_fields')
    fixed = {'rows': 65, 'TRAIN_rows': 41, 'DEV_rows': 24, 'metadata_unknown_rows': 4,
             'nominal_ENZ_rows': 47, 'nominal_12Z_rows': 14, 'batches': 17,
             'attempted_batches': attempts, 'unattempted_batches': 17 - attempts,
             'accounting_complete_batches': 0, 'HTTP200_candidate_batches': 0, 'qualified_batches': 0,
             'consumption_upper': attempts * (LIMITS['body_bytes'] + 1)}
    for field, expected in fixed.items():
        need(integer(value[field], 'unknown_aggregate_integer') == expected, 'unknown_aggregate_disagreement')
    need(value['accounting_known'] is False and value['whole_complete'] is False and
         value['retained_response_bytes'] is None and value['overflow_probe_bytes'] is None,
         'unknown_accounting_not_conservative')
    _claims(value['claims'])


def _attempt(row, i, begin, processing, previous_start, previous_end):
    fields(row, BATCH_BASE | ATTEMPT_FIELDS, 'attempt_fields')
    start = number(row['start'], 'attempt_start')
    end = number(row['end'], 'attempt_end')
    need(begin <= start < begin + LIMITS['processing_s'] and start <= end <= begin + processing,
         'attempt_clock_range')
    if previous_start is not None:
        need(start - previous_start >= LIMITS['start_spacing_s'], 'attempt_start_spacing')
        need(start >= previous_end, 'attempt_overlap')
    previous_phase = start
    for field in ('connected_at', 'headers_at', 'first_body_at'):
        if row[field] is not None:
            phase = number(row[field], 'attempt_phase')
            need(previous_phase <= phase <= end, 'attempt_phase_order')
            previous_phase = phase
    if row['http_status'] is not None:
        need(type(row['http_status']) is int, 'http_status_type')
    if row['declared'] is not None:
        integer(row['declared'], 'declared')
    need(type(row['framing']) is str and row['framing'] in ('fixed', 'chunked', 'eof', 'no_body', 'unknown'), 'framing')
    need(type(row['outcome']) is str and row['outcome'] in OUTCOMES, 'outcome')
    observed = integer(row['observed_bytes'], 'observed', 0, LIMITS['body_bytes'])
    probes = integer(row['overflow_probe_bytes'], 'probe', 0, 1)
    upper = integer(row['consumed_upper'], 'upper', observed + probes, LIMITS['body_bytes'] + 1)
    exact = boolean(row['consumption_exact'], 'exact')
    if exact:
        need(upper == observed + probes, 'exact_consumption')
        if probes:
            need(observed == LIMITS['body_bytes'] and row['outcome'] == 'overflow', 'probe_at_cap')
    else:
        need(upper == LIMITS['body_bytes'] + 1, 'unknown_consumption_charge')
    integer(row['worker_group'], 'worker_group', 1)
    if row['worker_exit_code'] is not None:
        need(type(row['worker_exit_code']) is int, 'worker_exit_code_type')
    for field in ('worker_exit_confirmed', 'worker_group_stop_confirmed', 'attempt_accounting_complete',
                  'HTTP200_candidate', 'framing_evidence_complete'):
        boolean(row[field], 'attempt_boolean')
    expected_members = set()
    body, header = row['body'], row['headers']
    if body is None:
        need(observed == 0, 'missing_body_observed')
    else:
        _pin(body, 'body_pin')
        need(body['name'] == BODIES[i] and body['bytes'] == observed, 'body_binding')
        expected_members.add(body['name'])
    if header is not None:
        _pin(header, 'header_pin')
        need(header['name'] == HEADERS[i] and header['bytes'] <= LIMITS['header_diagnostic_bytes'], 'header_binding')
        expected_members.add(header['name'])
    evidence = row['framing_evidence']
    if row['framing'] == 'chunked':
        if evidence is not None:
            _pin(evidence, 'framing_pin')
            need(evidence['name'] == FRAMINGS[i] and evidence['bytes'] <= LIMITS['header_diagnostic_bytes'], 'framing_binding')
            expected_members.add(evidence['name'])
        need(not row['framing_evidence_complete'] or evidence is not None, 'framing_flag_without_evidence')
    else:
        need(evidence is None and row['framing_evidence_complete'] is False, 'nonchunked_evidence')
    need((header['bytes'] if header is not None else 0) +
         (evidence['bytes'] if evidence is not None else 0) <= LIMITS['header_diagnostic_bytes'], 'combined_diagnostic_cap')
    framed = row['framing'] in ('fixed', 'chunked', 'eof', 'no_body')
    if row['outcome'] == 'framed_complete':
        need(framed and body is not None and header is not None and exact and probes == 0,
             'framed_complete_evidence')
        if row['framing'] == 'chunked':
            need(evidence is not None and row['framing_evidence_complete'] is True, 'closed_chunk_evidence_missing')
        if row['framing'] == 'fixed':
            need(row['declared'] is not None and observed == row['declared'], 'fixed_length_mismatch')
        elif row['framing'] == 'no_body':
            need(row['http_status'] in (204, 304) and observed == 0, 'no_body_identity')
        else:
            need(row['declared'] is None, 'nonfixed_declared')
    complete = (row['outcome'] == 'framed_complete' and exact and probes == 0 and
                (row['framing'] != 'chunked' or row['framing_evidence_complete'] is True) and body is not None and
                header is not None and row['worker_exit_confirmed'] is True and
                row['worker_group_stop_confirmed'] is True and row['worker_exit_code'] == 0 and
                row['connected_at'] is not None and row['headers_at'] is not None and
                row['connected_at'] - start <= LIMITS['connection_s'] and
                row['headers_at'] - start <= LIMITS['first_body_s'] and
                (observed == 0 or row['first_body_at'] is not None and
                 row['first_body_at'] - start <= LIMITS['first_body_s']) and
                end - start <= LIMITS['request_s'] and end - begin <= LIMITS['processing_s'])
    candidate = complete and row['http_status'] == 200 and observed > 0
    need(row['attempt_accounting_complete'] is complete and row['HTTP200_candidate'] is candidate,
         'attempt_computed_flags')
    return complete, candidate, observed, probes, upper, start, end, expected_members


def _result():
    return {'audit_protocol': AUDIT_PROTOCOL, 'valid': False, 'finalization_verified': False,
            'whole_complete': False, 'fixed_rows': 65, 'fixed_batches': 17, 'qualified_batches': 0,
            'aggregate': None, 'claims': dict(CLAIMS), 'filesystem_inventory_verified': False,
            'original_selection_authenticated': False, 'source_runtime_authenticated': False,
            'physical_process_stop_verified': False, 'physical_clock_verified': False,
            'registered_setup_accounting_verified': False, 'preserve_parent_artifacts': True, 'issues': []}


def audit(plan_bytes, manifest_bytes, bounded_member_reader, *,
          execution_summary_bytes=None, execution_summary_pin=None):
    """Pure production replay; missing/invalid/incomplete evidence qualifies zero.

    Parent separately authorizes exact private reads, full inventory/source/runtime,
    original selection/cache documentary truth, normal return and read-only custody.
    The callback must enforce provided caps before returning exact bytes.
    """
    result = _result()
    try:
        plan = _plan(plan_bytes)
        plan_sha = digest(plan_bytes)
        _pin(execution_summary_pin, 'execution_pin', named=False)
        need(execution_summary_pin['bytes'] <= MAX_SUMMARY, 'execution_pin_bound')
        summary = decode(execution_summary_bytes, MAX_SUMMARY, 'execution_summary')
        need(len(execution_summary_bytes) == execution_summary_pin['bytes'] and
             digest(execution_summary_bytes) == execution_summary_pin['sha256'], 'execution_pin_mismatch')
        fields(summary, SUMMARY_FIELDS, 'execution_fields')
        text(summary['protocol'], PROTOCOL, 'execution_protocol')
        boolean(summary['complete'], 'execution_complete')
        need(type(summary['reason']) is str and summary['reason'] in REASONS, 'execution_reason')
        begin = number(summary['begin'], 'execution_begin')
        returned = number(summary['returned_at'], 'execution_return')
        elapsed = number(summary['elapsed_s'], 'execution_elapsed')
        need(returned >= begin and elapsed == returned - begin, 'execution_clock')
        for field in ('controller_group_stop_confirmed', 'request_groups_stop_confirmed'):
            boolean(summary[field], 'execution_stop_flag')
        groups_registered = _registered(summary['registered_attempts'])
        fields(summary['public_aggregate'], AGGREGATE_FIELDS, 'aggregate_fields')
        boolean(summary['public_aggregate']['accounting_known'], 'aggregate_accounting_known')
        if summary['public_aggregate']['accounting_known'] is False:
            need(summary['complete'] is False and summary['reason'] != 'complete' and
                 summary['manifest_sha256'] is None and summary['receipt_sha256'] is None and
                 manifest_bytes is None, 'sparse_finalization_disagreement')
            _unknown_aggregate(summary['public_aggregate'], len(groups_registered))
            result.update(aggregate=summary['public_aggregate'], registered_setup_accounting_verified=True,
                          issues=['sparse_incomplete_accounting'])
            return result
        need(elapsed <= LIMITS['whole_s'], 'execution_clock')
        sha(summary['manifest_sha256'], 'execution_manifest_sha')
        sha(summary['receipt_sha256'], 'execution_receipt_sha')
        need(type(manifest_bytes) is bytes and 0 < len(manifest_bytes) <= MAX_MANIFEST, 'manifest_bytes')
        need(digest(manifest_bytes) == summary['manifest_sha256'], 'execution_manifest_binding')
        manifest = decode(manifest_bytes, MAX_MANIFEST, 'manifest')
        fields(manifest, {'protocol', 'members'}, 'manifest_fields')
        text(manifest['protocol'], PROTOCOL, 'manifest_protocol')
        need(type(manifest['members']) is list and 39 <= len(manifest['members']) <= 90, 'manifest_member_count')
        pins = {}
        for pin in manifest['members']:
            _pin(pin, 'member_pin')
            name = pin['name']
            need(name not in pins and pin['bytes'] <= _cap(name), 'member_duplicate_or_bound')
            pins[name] = pin
        need(REQUIRED <= pins.keys(), 'manifest_required_members')
        need(callable(bounded_member_reader), 'reader_not_callable')
        seen = set()
        cache = {}
        def read(name, *, keep=True):
            if name in cache:
                return cache[name]
            need(name in pins and name not in seen, 'member_missing_or_repeated')
            try:
                raw = bounded_member_reader(name, _cap(name))
            except Exception:
                raise Invalid('member_reader_failure') from None
            need(type(raw) is bytes and len(raw) <= _cap(name), 'member_reader_bound')
            pin = pins[name]
            need(len(raw) == pin['bytes'] and digest(raw) == pin['sha256'], 'member_pin_mismatch')
            seen.add(name)
            if keep:
                cache[name] = raw
            return raw
        need(read('roster.private.json') == plan_bytes, 'roster_original_bytes')
        initial = decode(read('initial.private.json'), MAX_JSON, 'initial')
        controller_raw = read('controller_summary.private.json')
        controller = decode(controller_raw, MAX_JSON, 'controller')
        receipt_raw = read('receipt.private.json')
        receipt = decode(receipt_raw, MAX_JSON, 'receipt')
        aggregate = decode(read('public_aggregate.json'), MAX_JSON, 'aggregate')
        fields(initial, INITIAL_FIELDS, 'initial_fields')
        fields(controller, CONTROLLER_FIELDS, 'controller_fields')
        fields(receipt, RECEIPT_FIELDS, 'receipt_fields')
        for value in (initial, controller, receipt):
            _common(value, plan, plan_sha)
            need(value['begin'] == begin, 'common_begin')
        need(type(initial['batches']) is list and len(initial['batches']) == 17 and
             type(controller['batches']) is list and len(controller['batches']) == 17, 'receipt_batch_count')
        processing = number(controller['processing_elapsed'], 'processing_elapsed')
        final_elapsed = number(receipt['elapsed_s'], 'receipt_elapsed')
        need(0 <= processing <= LIMITS['processing_s'] and processing <= final_elapsed <= elapsed, 'saved_elapsed_order')
        need(receipt['result_manifest_sha256'] is None, 'saved_manifest_cycle')
        sha(receipt['controller_summary_sha256'], 'controller_summary_sha')
        need(receipt['controller_summary_sha256'] == digest(controller_raw), 'controller_summary_pin')
        need(summary['receipt_sha256'] == digest(receipt_raw), 'returned_receipt_pin')
        requests = {}
        for i, batch in enumerate(plan['batches']):
            expected = canonical_entity([plan['rows'][j] for j in batch['row_indices']])
            need(read(REQUESTS[i]) == expected, 'saved_request_entity')
            requests[i] = pins[REQUESTS[i]]
            entry = initial['batches'][i]
            fields(entry, BATCH_BASE, 'initial_batch_fields')
            need(same(entry, {'batch_index': i, 'row_indices': batch['row_indices'],
                              'request': requests[i], 'status': 'unattempted'}), 'initial_batch_binding')
        attempts, accounting, candidates, retained, probes, upper = 0, 0, 0, 0, 0, 0
        worker_groups, expected_payloads = [], set()
        previous_start = previous_end = None
        halted = False
        incomplete_attempt_seen = False
        for i, row in enumerate(controller['batches']):
            need(type(row) is dict, 'batch_object')
            need(BATCH_BASE <= row.keys(), 'batch_base_fields')
            need(same(row['batch_index'], i) and same(row['row_indices'], plan['batches'][i]['row_indices']) and
                 same(row['request'], requests[i]), 'final_batch_binding')
            journal = decode(read(JOURNALS[i]), _cap(JOURNALS[i]), 'journal')
            need(same(journal, row), 'journal_controller_disagreement')
            if row['status'] == 'unattempted':
                fields(row, BATCH_BASE | {'reason'}, 'unattempted_fields')
                need(type(row['reason']) is str and row['reason'] in
                     ('halted_after_incomplete', 'launch_cutoff', 'total_cap'), 'unattempted_reason')
                if row['reason'] == 'halted_after_incomplete':
                    need(incomplete_attempt_seen, 'halt_without_incomplete_evidence')
                elif row['reason'] == 'launch_cutoff':
                    need(processing >= LIMITS['processing_s'], 'launch_cutoff_evidence')
                else:
                    need(retained == LIMITS['total_retained_bytes'] or
                         upper == LIMITS['total_consumption_upper'], 'total_cap_evidence')
                halted = True
            elif row['status'] == 'attempted':
                need(not halted, 'attempt_after_halt')
                need(integer(row.get('request_index'), 'request_index', 0, 16) == attempts, 'request_index_order')
                comp, cand, obs, probe, consumed, previous_start, previous_end, payloads = _attempt(
                    row, i, begin, processing, previous_start, previous_end)
                if row['headers'] is not None:
                    name = row['headers']['name']
                    need(name in pins and same(pins[name], row['headers']), 'header_manifest_binding')
                    _header(decode(read(name), _cap(name), 'headers'), row)
                if row['framing_evidence'] is not None:
                    name = row['framing_evidence']['name']
                    need(name in pins and same(pins[name], row['framing_evidence']), 'framing_manifest_binding')
                    closed = _closed_chunks(read(name), obs)
                    need(not row['framing_evidence_complete'] or closed, 'chunk_evidence_not_closed')
                if row['body'] is not None:
                    name = row['body']['name']
                    need(name in pins and same(pins[name], row['body']), 'body_manifest_binding')
                expected_payloads |= payloads
                group = row['worker_group']
                need(group not in worker_groups, 'duplicate_worker_group')
                worker_groups.append(group)
                attempts += 1
                accounting += comp
                candidates += cand
                retained += obs
                probes += probe
                upper += consumed
                need(retained <= LIMITS['total_retained_bytes'] and
                     probes <= 17 and upper <= LIMITS['total_consumption_upper'], 'aggregate_cap')
                halted = not comp
                incomplete_attempt_seen = incomplete_attempt_seen or not comp
            else:
                raise Invalid('batch_status')
        need(set(pins) == REQUIRED | expected_payloads, 'closed_manifest_membership')
        for field, expected in (('attempts', attempts), ('retained_bytes', retained),
                                ('overflow_probe_bytes', probes), ('consumption_upper', upper),
                                ('HTTP200_candidates', candidates)):
            need(integer(controller[field], 'controller_total') == expected, 'controller_totals')
        need(same(controller['worker_groups'], worker_groups), 'controller_groups')
        need(groups_registered == worker_groups and same(receipt['registered_attempts'], summary['registered_attempts']), 'registered_controller_disagreement')
        candidate_complete = attempts == 17 and accounting == 17
        need(controller['candidate_complete'] is candidate_complete, 'controller_complete')
        boolean(receipt['complete'], 'receipt_complete')
        need(type(receipt['reason']) is str and receipt['reason'] in REASONS, 'receipt_reason')
        if receipt['controller_exit_code'] is not None:
            need(type(receipt['controller_exit_code']) is int, 'controller_exit_type')
        need(receipt['controller_exit_code'] == 0, 'known_controller_not_normal')
        for field in ('controller_group_stop_confirmed', 'request_groups_stop_confirmed'):
            boolean(receipt[field], 'receipt_stop_flag')
            need(receipt[field] is summary[field], 'outer_stop_disagreement')
        need(receipt['complete'] is summary['complete'] and receipt['reason'] == summary['reason'],
             'outer_receipt_disagreement')
        complete = receipt['complete']
        need((receipt['reason'] == 'complete') is complete, 'completion_reason')
        if complete:
            need(candidate_complete and processing <= LIMITS['processing_s'] and
                 receipt['controller_exit_code'] == 0 and receipt['controller_group_stop_confirmed'] is True and
                 receipt['request_groups_stop_confirmed'] is True, 'whole_complete_evidence')
        _aggregate(aggregate, attempts=attempts, accounting=accounting, candidates=candidates,
                   retained=retained, probes=probes, upper=upper, complete=False)
        _aggregate(summary['public_aggregate'], attempts=attempts, accounting=accounting, candidates=candidates,
                   retained=retained, probes=probes, upper=upper, complete=complete)
        need(all(same(aggregate[field], summary['public_aggregate'][field]) for field in AGGREGATE_FIELDS
                 if field not in ('qualified_batches', 'whole_complete')), 'returned_aggregate_disagreement')
        # All receipt metadata/header framing/bindings are checked before bodies.
        for name in sorted(expected_payloads & set(BODIES)):
            read(name, keep=False)
        need(seen == set(pins), 'member_not_replayed')
        result.update(valid=True, finalization_verified=complete, whole_complete=complete,
                      qualified_batches=candidates if complete else 0, aggregate=summary['public_aggregate'],
                      registered_setup_accounting_verified=True)
    except Invalid as error:
        result['issues'] = [str(error)]
    except Exception:
        result['issues'] = ['audit_input_failure']
    return result

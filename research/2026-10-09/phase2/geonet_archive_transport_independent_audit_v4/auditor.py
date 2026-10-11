"""Pure, bounded replay of the eight-slot literal-key transport contract.

No filesystem, network, transport, decoding, inventory, or acquisition interface.
The caller supplies exact bytes and a privately authorized bounded member reader.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date

PROTOCOL = 'geonet-anonymous-archive-transport-v5'
STUDY = 'geonet-configured-eight-horizontal-precontext3-transport-v5'
MAPPING = 'unverified_hypothesis'
HYPOTHESIS = 'anonymous_official_configured_literal_key_gets'
ENDPOINT = 'https://geonet-open-data.s3.ap-southeast-2.amazonaws.com'
PROPOSAL_SHA = '9db9d9a06d0ae5c01740b5e5c7befd96a1c34e8b7eef9527639f70b4d4538bb4'
TEMPLATE_SHA = '3194fa79e8993b99f0514239d7735dc4461b9d31aefd031b2f43e725612b6412'
UNCERTAINTY_SHA = 'd3f826d1b1e45c59fdd5760dc3b5e9f0a8e954a60c2ec7ee628e80031462ec74'
SLOTS = ('ordinary_e', 'ordinary_n', 'higher_e', 'higher_n',
         'boundary_e', 'boundary_n', 'final_e', 'final_n')
UNCERTAINTIES = ['utc_filename_partition', 'channel_key_identity',
                 'location_key_encoding', 'endpoint_key_correspondence']
LIMITS = {'connection_s': 10.0, 'first_body_s': 20.0, 'request_s': 120.0,
          'start_spacing_s': 1.0, 'no_new_after_s': 660.0,
          'transfer_stop_s': 780.0, 'run_s': 900.0,
          'per_body_bytes': 67108864, 'total_body_bytes': 536870912}
CLAIMS = dict.fromkeys(('semantic_mapping_verified', 'utc_filename_basis_verified',
                       'channel_key_identity_verified', 'location_key_encoding_verified',
                       'endpoint_mapping_verified', 'waveform_coverage_verified',
                       'failed96_repaired'), False)
POLICY = {'method': 'GET', 'endpoint': ENDPOINT, **dict.fromkeys(
          ('redirects', 'retries', 'head', 'listing', 'auth', 'requester_payer', 'fallback'), False)}
MAX_PLAN = 16384
MAX_JSON = 65536
MAX_MANIFEST = 65536
MAX_SUMMARY = 16384
SHA = re.compile(r'[0-9a-f]{64}\Z')
KEY = re.compile(r'waveforms/miniseed/(?P<year>[0-9]{4})/(?P=year)\.(?P<doy>[0-9]{3})/'
                 r'(?P<site>[A-Z0-9]{3,4})\.(?P<network>[A-Z0-9]{2})/'
                 r'(?P=year)\.(?P=doy)\.(?P=site)\.(?P<location>[A-Z0-9]{2})-'
                 r'(?P<channel>[A-Z0-9]{3})\.(?P=network)\.D\Z')
OUTCOMES = {'body_complete', 'empty_body', 'incomplete_body', 'body_cap_boundary',
            'declared_size_rejected', 'invalid_content_length', 'worker_exit',
            'body_receipt_mismatch', 'connection_deadline', 'first_body_deadline',
            'complete_deadline', 'transfer_deadline'}
INITIAL_FIELDS = {'protocol', 'study_id', 'plan_sha256', 'complete', 'fixture', 'limits',
                  'mapping_status', 'transport_hypothesis', 'template_source_sha256',
                  'uncertainty_evidence_sha256', 'preregistration_sha256', 'claims',
                  'run_begin', 'request_policy', 'slots'}
FINAL_FIELDS = INITIAL_FIELDS | {'attempts', 'consumed_upper', 'observed_body_bytes',
                                  'all_slots_transport_pass', 'elapsed_s'}
REQUEST_FIELDS = {'start', 'connected_at', 'headers_at', 'first_body_at', 'end',
                  'http_status', 'declared', 'outcome', 'consumed', 'body',
                  'observed_bytes', 'consumed_upper', 'consumption_exact',
                  'receipt_verified', 'worker_exit_confirmed', 'transport_pass'}
FIXED_NAMES = {'roster.private.json', 'initial.private.json', 'receipt.private.json'}
JOURNALS = tuple(f'{n:03d}.slot.private.json' for n in range(len(SLOTS)))
BODIES = tuple(f'{n:03d}.body.private' for n in range(len(SLOTS)))


class _Invalid(ValueError):
    pass


def _need(condition, label):
    if not condition:
        raise _Invalid(label)


def _fields(value, fields, label):
    _need(type(value) is dict and set(value) == set(fields), label)


def _integer(value, label, minimum=0):
    _need(type(value) is int and value >= minimum, label)
    return value


def _number(value, label):
    _need(type(value) in (int, float), label)
    try:
        finite = math.isfinite(value)
    except (OverflowError, ValueError):
        finite = False
    _need(finite, label)
    return value


def _boolean(value, label):
    _need(type(value) is bool, label)
    return value


def _sha(value, label):
    _need(type(value) is str and SHA.fullmatch(value) is not None, label)
    return value


def _pairs(pairs):
    answer = {}
    for key, value in pairs:
        if key in answer:
            raise _Invalid('json_duplicate_key')
        answer[key] = value
    return answer


def _json(raw, cap, label):
    _need(type(raw) is bytes and len(raw) <= cap, label + '_bytes')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(_Invalid('json_nonfinite')))
    except _Invalid:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise _Invalid(label + '_json') from None
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        _need(nodes <= 16384 and depth <= 32, label + '_structure_bound')
        if type(item) is float:
            _need(math.isfinite(item), 'json_nonfinite')
        if type(item) is dict:
            pending.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            pending.extend((v, depth + 1) for v in item)
    return value


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _same_json(left, right):
    # Plain Python equality aliases JSON booleans with 0/1. Agreement must
    # preserve decoded types too, including integer-only receipt fields.
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same_json(left[key], right[key]) for key in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same_json(x, y) for x, y in zip(left, right))
    return left == right


def _pin(value, label, *, named=True):
    _fields(value, {'name', 'bytes', 'sha256'} if named else {'bytes', 'sha256'}, label)
    if named:
        _need(type(value['name']) is str and value['name'] in FIXED_NAMES | set(JOURNALS) | set(BODIES),
              label + '_name')
    _integer(value['bytes'], label + '_count')
    _sha(value['sha256'], label + '_sha')
    return value


def _matches(raw, pin, label):
    _need(len(raw) == pin['bytes'] and _digest(raw) == pin['sha256'], label)


def _plan(raw):
    plan = _json(raw, MAX_PLAN, 'plan')
    _fields(plan, {'protocol', 'study_id', 'proposal_sha256', 'template_source_sha256',
                   'mapping_status', 'transport_hypothesis', 'uncertainty_evidence_sha256',
                   'preregistration_sha256', 'precontext_s', 'slots'}, 'plan_fields')
    # This is a declared observation requirement, not verified prefix support.
    _need(type(plan['precontext_s']) is int and plan['precontext_s'] == 3, 'plan_precontext_s')
    for field, expected in (('protocol', PROTOCOL), ('proposal_sha256', PROPOSAL_SHA),
                            ('template_source_sha256', TEMPLATE_SHA), ('mapping_status', MAPPING),
                            ('transport_hypothesis', HYPOTHESIS), ('uncertainty_evidence_sha256', UNCERTAINTY_SHA)):
        _need(plan[field] == expected, 'plan_' + field)
    # Production replay binds the exact public study; synthetic fixtures use
    # invented bytes carrying that identity, never a fixture-gate bypass.
    _need(plan['study_id'] == STUDY, 'study_id')
    _sha(plan['preregistration_sha256'], 'preregistration_sha')
    _need(type(plan['slots']) is list and len(plan['slots']) == len(SLOTS), 'plan_slots')
    for index, slot in enumerate(plan['slots']):
        _fields(slot, {'slot_id', 'key', 'unavailable_reason', 'uncertainties'}, 'plan_slot_fields')
        _need(slot['slot_id'] == SLOTS[index], 'plan_slot_order')
        _need(slot['uncertainties'] == UNCERTAINTIES, 'plan_uncertainties')
        if slot['key'] is None:
            reason = slot['unavailable_reason']
            _need(type(reason) is str and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', reason) is not None,
                  'plan_unavailable_reason')
        else:
            _need(type(slot['key']) is str and slot['unavailable_reason'] is None, 'plan_literal_key')
            match = KEY.fullmatch(slot['key'])
            _need(match is not None, 'plan_key_shape')
            _need(match['channel'][-1] == SLOTS[index][-1].upper(), 'plan_role_channel')
            year, doy = int(match['year']), int(match['doy'])
            _need(year >= 1 and 1 <= doy <= date(year, 12, 31).timetuple().tm_yday, 'plan_year_doy')
    return plan


def _false_claims(value, label):
    _fields(value, CLAIMS, label)
    _need(all(value[key] is False for key in CLAIMS), label)


def _common(receipt, plan, plan_sha, label):
    for field in ('protocol', 'study_id', 'template_source_sha256', 'mapping_status',
                  'transport_hypothesis', 'uncertainty_evidence_sha256', 'preregistration_sha256'):
        _need(receipt[field] == plan[field], label + '_' + field)
    _need(receipt['plan_sha256'] == plan_sha, label + '_plan_sha')
    _need(receipt['fixture'] is False, label + '_fixture_not_production')
    _fields(receipt['limits'], LIMITS, label + '_limits')
    for field, expected in LIMITS.items():
        actual = receipt['limits'][field]
        if field.endswith('_bytes'):
            _integer(actual, label + '_limit_integer')
        else:
            _number(actual, label + '_limit_number')
        _need(actual == expected, label + '_limits')
    _fields(receipt['request_policy'], POLICY, label + '_request_policy')
    for field, expected in POLICY.items():
        _need(receipt['request_policy'][field] == expected and
              (type(expected) is not bool or receipt['request_policy'][field] is expected),
              label + '_request_policy')
    _false_claims(receipt['claims'], label + '_claims')
    _number(receipt['run_begin'], label + '_begin')
    _boolean(receipt['complete'], label + '_complete')
    _need(type(receipt['slots']) is list and len(receipt['slots']) == len(SLOTS), label + '_slots')


def _summary(raw, pin, manifest_raw):
    _pin(pin, 'execution_pin', named=False)
    _need(pin['bytes'] <= MAX_SUMMARY, 'execution_pin_bound')
    _need(type(raw) is bytes and len(raw) <= MAX_SUMMARY, 'execution_bytes')
    _matches(raw, pin, 'execution_pin_mismatch')
    summary = _json(raw, MAX_SUMMARY, 'execution')
    fields = {'result', 'complete', 'all_slots_transport_pass', 'mapping_status', 'claims',
              'begin', 'returned_at', 'elapsed_s', 'manifest_sha256'}
    _fields(summary, fields, 'execution_fields')
    _need(summary['result'] == 'finalized', 'execution_not_finalized')
    _need(summary['mapping_status'] == MAPPING, 'execution_mapping')
    _false_claims(summary['claims'], 'execution_claims')
    _boolean(summary['complete'], 'execution_complete')
    _boolean(summary['all_slots_transport_pass'], 'execution_pass')
    begin = _number(summary['begin'], 'execution_begin')
    returned = _number(summary['returned_at'], 'execution_return')
    elapsed = _number(summary['elapsed_s'], 'execution_elapsed')
    _need(returned >= begin and elapsed == returned - begin and 0 <= elapsed <= LIMITS['run_s'],
          'execution_deadline')
    _sha(summary['manifest_sha256'], 'execution_manifest_sha')
    _need(summary['manifest_sha256'] == _digest(manifest_raw), 'execution_manifest_mismatch')
    return summary


def _request(row, index, begin, summary, allowance, previous_start):
    _fields(row, {'slot_id', 'key', 'uncertainties', 'status', 'request_index'} | REQUEST_FIELDS,
            'attempted_fields')
    start = _number(row['start'], 'request_start')
    end = _number(row['end'], 'request_end')
    _need(begin <= start < begin + LIMITS['no_new_after_s'] and start <= end <= summary['returned_at'],
          'request_clock_range')
    if previous_start is not None:
        _need(start - previous_start >= LIMITS['start_spacing_s'], 'request_spacing')
    previous = start
    missing = False
    for field in ('connected_at', 'headers_at', 'first_body_at'):
        value = row[field]
        if value is None:
            missing = True
        else:
            _number(value, 'request_' + field)
            _need(not missing and previous <= value <= end, 'request_clock_order')
            previous = value
    if row['http_status'] is not None:
        _need(type(row['http_status']) is int, 'request_http_status')
        _need(row['headers_at'] is not None, 'status_without_headers')
    if row['declared'] is not None:
        _integer(row['declared'], 'request_declared')
        _need(row['headers_at'] is not None, 'declared_without_headers')
    outcome = row['outcome']
    _need(type(outcome) is str and (outcome in OUTCOMES or
          re.fullmatch(r'worker_error_[A-Za-z_][A-Za-z0-9_]*', outcome) is not None), 'request_outcome')
    observed = _integer(row['observed_bytes'], 'request_observed')
    upper = _integer(row['consumed_upper'], 'request_upper')
    consumed = row['consumed']
    if consumed is not None:
        _integer(consumed, 'request_consumed')
        _need(consumed <= allowance, 'request_consumed_bound')
    exact = _boolean(row['consumption_exact'], 'request_exact')
    verified = _boolean(row['receipt_verified'], 'request_receipt_verified')
    _need(row['worker_exit_confirmed'] is True, 'worker_exit_unconfirmed')
    _boolean(row['transport_pass'], 'request_pass')
    _need(observed <= upper <= allowance, 'request_body_allowance')
    _need(exact is verified, 'request_verification_disagreement')
    if exact:
        _need(verified and consumed == observed == upper, 'request_exact_count')
    else:
        _need(upper == allowance, 'request_nonexact_charge')
    body = row['body']
    if body is None:
        _need(observed == 0, 'request_missing_body')
    else:
        _pin(body, 'body_pin')
        _need(body['name'] == BODIES[index] and body['bytes'] == observed, 'body_slot_binding')
    if outcome == 'empty_body':
        _need(observed == 0, 'empty_body_count')
    if outcome == 'body_complete':
        _need(observed > 0 and body is not None, 'complete_body_count')
        _need(row['declared'] is not None or observed < allowance, 'complete_body_unknown_cap_framing')
    if outcome in ('body_complete', 'empty_body'):
        _need(exact, 'complete_body_unverified_count')
        if row['declared'] is not None:
            _need(row['declared'] == observed == consumed, 'complete_body_declared_mismatch')
    passing = (outcome == 'body_complete' and row['http_status'] == 200 and body is not None and
               observed > 0 and exact and verified and row['connected_at'] is not None and
               row['first_body_at'] is not None and row['connected_at'] - start <= LIMITS['connection_s'] and
               row['first_body_at'] - start <= LIMITS['first_body_s'] and
               end - start <= LIMITS['request_s'] and end - begin <= LIMITS['transfer_stop_s'])
    _need(row['transport_pass'] is passing, 'request_pass_disagreement')
    return passing, observed, upper, start


def _result():
    return {'audit_protocol': 'geonet-independent-archive-transport-audit-v4',
            'valid': False, 'finalization_verified': False, 'complete_accounting': False,
            'all_slots_transport_pass': False, 'qualified_slot_count': 0,
            'attempt_count': None, 'observed_body_bytes': None, 'consumed_upper': None,
            'mapping_status': MAPPING, 'claims': dict(CLAIMS),
            'filesystem_inventory_verified': False, 'physical_timing_verified': False,
            'slots': [{'slot_id': name, 'status': 'unqualified', 'transport_pass': False} for name in SLOTS],
            'issues': [], 'preserve_parent_artifacts': True}


def audit(plan_bytes, manifest_bytes, bounded_member_reader, *,
          execution_summary_bytes=None, execution_summary_pin=None):
    """Replay production receipts; return only transport-scoped, conservative assertions.

    ``bounded_member_reader(name, maximum_bytes)`` must return exact ``bytes`` or
    raise. It is called only for validated fixed manifest members, once each.
    Parent custody must separately authorize reads and establish full inventory.
    Missing/failed final evidence qualifies zero slots without reading members.
    The execution pin has exactly ``bytes`` and ``sha256`` (no member name).
    """
    result = _result()
    try:
        plan = _plan(plan_bytes)
        _need(type(manifest_bytes) is bytes and len(manifest_bytes) <= MAX_MANIFEST, 'final_manifest_missing_or_bound')
        _need(execution_summary_bytes is not None and execution_summary_pin is not None, 'execution_evidence_missing')
        summary = _summary(execution_summary_bytes, execution_summary_pin, manifest_bytes)
        manifest = _json(manifest_bytes, MAX_MANIFEST, 'manifest')
        _fields(manifest, {'protocol', 'members'}, 'manifest_fields')
        _need(manifest['protocol'] == PROTOCOL, 'manifest_protocol')
        _need(type(manifest['members']) is list and 11 <= len(manifest['members']) <= 19, 'manifest_member_count')
        pins = {}
        for pin in manifest['members']:
            _pin(pin, 'member_pin')
            name = pin['name']
            _need(name not in pins, 'manifest_duplicate_member')
            cap = LIMITS['per_body_bytes'] if name in BODIES else MAX_JSON
            _need(pin['bytes'] <= cap, 'member_pin_bound')
            pins[name] = pin
        _need(FIXED_NAMES | set(JOURNALS) <= pins.keys(), 'manifest_missing_required_member')
        _need(callable(bounded_member_reader), 'member_reader_not_callable')
        cache = {}
        def read(name):
            if name not in cache:
                pin = pins[name]
                cap = LIMITS['per_body_bytes'] if name in BODIES else MAX_JSON
                try:
                    raw = bounded_member_reader(name, cap)
                except Exception:
                    raise _Invalid('member_reader_failure') from None
                _need(type(raw) is bytes and len(raw) <= cap, 'member_reader_bound')
                _matches(raw, pin, 'member_pin_mismatch')
                cache[name] = raw
            return cache[name]
        _need(read('roster.private.json') == plan_bytes, 'roster_original_bytes_mismatch')
        initial = _json(read('initial.private.json'), MAX_JSON, 'initial')
        final = _json(read('receipt.private.json'), MAX_JSON, 'final')
        _fields(initial, INITIAL_FIELDS, 'initial_fields')
        _fields(final, FINAL_FIELDS, 'final_fields')
        plan_sha = _digest(plan_bytes)
        _common(initial, plan, plan_sha, 'initial')
        _common(final, plan, plan_sha, 'final')
        _need(initial['complete'] is False and initial['run_begin'] == final['run_begin'] == summary['begin'],
              'initial_final_begin_or_complete')
        elapsed = _number(final['elapsed_s'], 'final_elapsed')
        _need(0 <= elapsed <= summary['elapsed_s'], 'final_elapsed_range')
        for index, slot in enumerate(initial['slots']):
            _fields(slot, {'slot_id', 'status', 'uncertainties'}, 'initial_slot_fields')
            _need(slot['slot_id'] == SLOTS[index] and slot['uncertainties'] == UNCERTAINTIES and
                  slot['status'] == ('unavailable' if plan['slots'][index]['key'] is None else 'unattempted'),
                  'initial_slot_binding')
        attempts, total_observed, total_upper = 0, 0, 0
        sources, expected_bodies, slot_results = {}, set(), []
        previous_start = None
        previous_end = None
        new_attempts_stopped = False
        for index, row in enumerate(final['slots']):
            _need(type(row) is dict, 'final_slot_object')
            base = {'slot_id', 'key', 'uncertainties', 'status'}
            _need(base <= row.keys(), 'final_slot_missing_fields')
            planned = plan['slots'][index]
            _need(row['slot_id'] == SLOTS[index] and row['key'] == planned['key'] and
                  row['uncertainties'] == UNCERTAINTIES, 'final_slot_binding')
            _need(_same_json(_json(read(JOURNALS[index]), MAX_JSON, 'journal'), row), 'journal_final_mismatch')
            status, key, passing = row['status'], row['key'], False
            if key is None:
                _fields(row, base | {'reason'}, 'unavailable_fields')
                _need(status == 'unavailable' and row['reason'] == planned['unavailable_reason'], 'unavailable_binding')
            elif status == 'unattempted':
                _fields(row, base | {'reason'}, 'unattempted_fields')
                _need(key not in sources, 'unattempted_duplicate_source')
                _need(row['reason'] in ('new_request_deadline', 'total_body_cap'), 'unattempted_reason')
                if row['reason'] == 'new_request_deadline':
                    _need(elapsed >= LIMITS['no_new_after_s'], 'unattempted_deadline_evidence')
                else:
                    _need(total_upper == LIMITS['total_body_bytes'], 'unattempted_cap_evidence')
                new_attempts_stopped = True
            elif status == 'shared_object':
                _fields(row, base | {'source_slot_index', 'request_index', 'transport_pass'}, 'shared_fields')
                source = _integer(row['source_slot_index'], 'shared_index')
                _need(source < index and key in sources and sources[key] == source, 'shared_source_binding')
                original = final['slots'][source]
                _need(type(row['request_index']) is int and row['request_index'] == original['request_index'] and
                      row['transport_pass'] is original['transport_pass'], 'shared_result_binding')
                passing = original['transport_pass']
            elif status == 'attempted':
                _need(not new_attempts_stopped, 'attempt_after_unattempted_cutoff')
                _need(key not in sources, 'duplicate_attempt')
                _need(type(row.get('request_index')) is int and row['request_index'] == attempts, 'request_index_order')
                allowance = min(LIMITS['per_body_bytes'], LIMITS['total_body_bytes'] - total_upper)
                _need(allowance > 0, 'attempt_after_total_cap')
                passing, observed, upper, previous_start = _request(
                    row, index, final['run_begin'], summary, allowance, previous_start)
                _need(previous_end is None or row['start'] >= previous_end, 'request_overlap')
                previous_end = row['end']
                _need(row['end'] <= final['run_begin'] + elapsed, 'request_after_final_receipt')
                total_observed += observed
                total_upper += upper
                attempts += 1
                sources[key] = index
                if row['body'] is not None:
                    name = row['body']['name']
                    _need(name in pins and pins[name] == row['body'], 'body_manifest_binding')
                    expected_bodies.add(name)
            else:
                raise _Invalid('final_slot_status')
            slot_results.append({'slot_id': SLOTS[index], 'status': status, 'transport_pass': passing})
        expected = FIXED_NAMES | set(JOURNALS) | expected_bodies
        _need(set(pins) == expected, 'manifest_membership_disagreement')
        # Only bodies proven to belong to attempted rows may be consumed.
        for name in sorted(expected_bodies):
            read(name)
        _need(set(cache) == set(pins), 'manifest_member_not_replayed')
        _integer(final['attempts'], 'final_attempts')
        _integer(final['observed_body_bytes'], 'final_observed')
        _integer(final['consumed_upper'], 'final_upper')
        _need(final['attempts'] == attempts <= len(SLOTS) and final['observed_body_bytes'] == total_observed and
              final['consumed_upper'] == total_upper <= LIMITS['total_body_bytes'], 'final_totals')
        complete = not any(row['status'] == 'unattempted' for row in slot_results)
        all_pass = all(row['transport_pass'] for row in slot_results)
        _need(final['complete'] is complete and summary['complete'] is complete, 'completion_disagreement')
        _need(final['all_slots_transport_pass'] is all_pass and summary['all_slots_transport_pass'] is all_pass,
              'all_slots_pass_disagreement')
        result.update(valid=True, finalization_verified=True, complete_accounting=complete,
                      all_slots_transport_pass=all_pass,
                      qualified_slot_count=sum(row['transport_pass'] for row in slot_results) if complete else 0,
                      attempt_count=attempts, observed_body_bytes=total_observed, consumed_upper=total_upper,
                      slots=slot_results)
        if not complete:
            # No slot qualification is promoted from an incomplete final run.
            result['slots'] = [{**row, 'transport_pass': False} for row in slot_results]
    except _Invalid as error:
        result['issues'] = [str(error)]
    except Exception:
        # Malformed bounded caller values may not escape into a partial assertion.
        result['issues'] = ['audit_input_failure']
    return result

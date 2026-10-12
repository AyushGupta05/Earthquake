"""Invented in-memory65/17 fixtures only; no actual input, acquisition or filesystem reader."""
import copy
import hashlib
import json
import unittest

import auditor as a


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(name, raw):
    return {'name': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


class Fixture:
    def __init__(self):
        rows = []
        for i in range(65):
            rows.append({'row_index': i, 'original_event_index': i, 'original_target_index': 0,
                         'event_id': f'invented-{i:03d}', 'partition': 'TRAIN' if i < 41 else 'DEV',
                         'network': 'NX', 'station': 'AX0', 'location': '' if i % 2 else 'Z3',
                         'prefix': 'BH', 't0_ns': i * 86400000000000, 'pick_ns': i * 86400000000000 + 1000000001,
                         'metadata_status': 'positive' if i < 61 else 'http204_unknown',
                         'nominal_family': 'ENZ' if i < 47 else '12Z' if i < 61 else None})
        self.plan = {'protocol': a.PROTOCOL, 'study_id': a.STUDY, 'proposal_sha256': a.PROPOSAL_SHA,
                     'rows': rows, 'batches': [], 'prerequisites': dict.fromkeys(a.PREREQUISITES, 'a' * 64)}
        self.rebuild_requests()
        self.rows = []
        self.payloads = {}
        for i in range(17):
            start = 1000.0 + i * 2
            raw = f'invented response entity{i}'.encode()
            header = {'status': 200, 'framing': 'fixed', 'declared': len(raw),
                      'fields': [['Content-Length', str(len(raw))]],
                      'parser_limits': {'line_bytes': 65536, 'header_count': 100, 'chunk_trailer_count': 100}}
            self.payloads[a.BODIES[i]] = raw
            self.payloads[a.HEADERS[i]] = encode(header)
            self.rows.append({'batch_index': i, 'row_indices': self.plan['batches'][i]['row_indices'],
                              'request': pin(a.REQUESTS[i], self.plan['batches'][i]['request_body'].encode('ascii')),
                              'status': 'attempted', 'request_index': i, 'start': start, 'end': start + .5,
                              'connected_at': start + .1, 'headers_at': start + .2, 'first_body_at': start + .3,
                              'http_status': 200, 'framing': 'fixed', 'declared': len(raw), 'outcome': 'framed_complete',
                              'body': pin(a.BODIES[i], raw), 'headers': pin(a.HEADERS[i], encode(header)),
                              'observed_bytes': len(raw), 'overflow_probe_bytes': 0, 'consumed_upper': len(raw),
                              'consumption_exact': True, 'worker_group': 2000 + i, 'worker_exit_code': 0,
                              'worker_exit_confirmed': True, 'worker_group_stop_confirmed': True,
                              'framing_evidence': None, 'framing_evidence_complete': False,
                              'attempt_accounting_complete': True, 'HTTP200_candidate': True})
        self.initial_overrides = {}
        self.controller_overrides = {}
        self.receipt_overrides = {}
        self.summary_overrides = {}
        self.aggregate_overrides = {}
        self.begin = 1000.0
        self.final_elapsed = 35.0
        self.outer_elapsed = 36.0

    def rebuild_requests(self):
        self.plan['batches'] = []
        for i in range(17):
            indices = list(range(i * 4, min(i * 4 + 4, 65)))
            raw = a.canonical_entity([self.plan['rows'][n] for n in indices])
            self.plan['batches'].append({'batch_index': i, 'row_indices': indices,
                                         'request_body': raw.decode('ascii'), 'request_sha256': a.digest(raw)})

    def body(self, i, raw, *, status=200, framing='fixed', outcome='framed_complete', complete=True):
        row = self.rows[i]
        declared = len(raw) if framing == 'fixed' else None
        fields = [['Content-Length', str(declared)]] if framing == 'fixed' else (
            [['Transfer-Encoding', 'chunked']] if framing == 'chunked' else [])
        header = {'status': status, 'framing': framing, 'declared': declared, 'fields': fields,
                  'parser_limits': {'line_bytes': 65536, 'header_count': 100, 'chunk_trailer_count': 100}}
        self.payloads[a.BODIES[i]] = raw
        self.payloads[a.HEADERS[i]] = encode(header)
        row.update(body=pin(a.BODIES[i], raw), headers=pin(a.HEADERS[i], encode(header)), http_status=status,
                   framing=framing, declared=declared, observed_bytes=len(raw), consumed_upper=len(raw),
                   outcome=outcome, attempt_accounting_complete=complete, HTTP200_candidate=complete and status == 200 and bool(raw))
        if framing == 'chunked':
            evidence = (f'{len(raw):x}\r\n\r\n0\r\n\r\n'.encode() if raw else b'0\r\n\r\n')
            self.payloads[a.FRAMINGS[i]] = evidence
            row.update(framing_evidence=pin(a.FRAMINGS[i], evidence), framing_evidence_complete=True)
        else:
            self.payloads.pop(a.FRAMINGS[i], None)
            row.update(framing_evidence=None, framing_evidence_complete=False)
        if not raw:
            row['first_body_at'] = None

    def halt(self, i, *, outcome='partial'):
        self.rows[i].update(outcome=outcome, attempt_accounting_complete=False, HTTP200_candidate=False)
        for n in range(i + 1, 17):
            self.rows[n] = {'batch_index': n, 'row_indices': self.plan['batches'][n]['row_indices'],
                            'request': pin(a.REQUESTS[n], self.plan['batches'][n]['request_body'].encode()),
                            'status': 'unattempted', 'reason': 'halted_after_incomplete'}
            self.payloads.pop(a.BODIES[n], None)
            self.payloads.pop(a.HEADERS[n], None)
            self.payloads.pop(a.FRAMINGS[n], None)

    def header(self, i, pairs, framing, declared):
        row = self.rows[i]
        header = {'status': row['http_status'], 'framing': framing, 'declared': declared, 'fields': pairs,
                  'parser_limits': {'line_bytes': 65536, 'header_count': 100, 'chunk_trailer_count': 100}}
        self.payloads[a.HEADERS[i]] = encode(header)
        row.update(headers=pin(a.HEADERS[i], encode(header)), framing=framing, declared=declared)

    def bundle(self):
        plan = encode(self.plan)
        common = {'protocol': a.PROTOCOL, 'study_id': self.plan['study_id'], 'plan_sha256': a.digest(plan),
                  'fixture': False, 'limits': dict(a.LIMITS), 'begin': self.begin, 'claims': dict(a.CLAIMS)}
        initial = {**copy.deepcopy(common), 'batches': [
            {'batch_index': i, 'row_indices': batch['row_indices'],
             'request': pin(a.REQUESTS[i], batch['request_body'].encode('ascii')), 'status': 'unattempted'}
            for i, batch in enumerate(self.plan['batches'])]}
        initial.update(self.initial_overrides)
        attempted = [row for row in self.rows if row['status'] == 'attempted']
        accounting = sum(row['attempt_accounting_complete'] for row in attempted)
        candidates = sum(row['HTTP200_candidate'] for row in attempted)
        retained = sum(row['observed_bytes'] for row in attempted)
        probes = sum(row['overflow_probe_bytes'] for row in attempted)
        upper = sum(row['consumed_upper'] for row in attempted)
        candidate_complete = len(attempted) == 17 and accounting == 17
        processing = max((row['end'] - self.begin for row in attempted), default=0) + 1
        controller = {**copy.deepcopy(common), 'processing_elapsed': processing, 'batches': copy.deepcopy(self.rows),
                      'attempts': len(attempted), 'retained_bytes': retained, 'overflow_probe_bytes': probes,
                      'consumption_upper': upper, 'HTTP200_candidates': candidates,
                      'candidate_complete': candidate_complete, 'worker_groups': [row['worker_group'] for row in attempted]}
        controller.update(self.controller_overrides)
        controller_raw = encode(controller)
        receipt = {**copy.deepcopy(common), 'complete': candidate_complete,
                   'reason': 'complete' if candidate_complete else 'incomplete', 'elapsed_s': self.final_elapsed,
                   'controller_exit_code': 0, 'controller_group_stop_confirmed': True,
                   'request_groups_stop_confirmed': True,
                   'registered_attempts': [{'batch_index': row['batch_index'], 'worker_group': row['worker_group']} for row in attempted],
                   'controller_summary_sha256': a.digest(controller_raw),
                   'result_manifest_sha256': None}
        receipt.update(self.receipt_overrides)
        complete = receipt['complete']
        aggregate = {'rows': 65, 'TRAIN_rows': 41, 'DEV_rows': 24, 'metadata_unknown_rows': 4,
                     'nominal_ENZ_rows': 47, 'nominal_12Z_rows': 14, 'batches': 17,
                     'attempted_batches': len(attempted), 'unattempted_batches': 17 - len(attempted),
                     'accounting_complete_batches': accounting, 'HTTP200_candidate_batches': candidates,
                     'qualified_batches': candidates if complete else 0, 'retained_response_bytes': retained,
                     'overflow_probe_bytes': probes, 'consumption_upper': upper, 'accounting_known': True, 'whole_complete': complete,
                     'claims': dict(a.CLAIMS)}
        aggregate.update(self.aggregate_overrides)
        members = {'roster.private.json': plan, 'initial.private.json': encode(initial),
                   'controller_summary.private.json': controller_raw, 'receipt.private.json': encode(receipt),
                   'public_aggregate.json': encode({**aggregate, 'whole_complete': False, 'qualified_batches': 0}), **self.payloads}
        for i, batch in enumerate(self.plan['batches']):
            members[a.REQUESTS[i]] = batch['request_body'].encode('ascii')
        for i, row in enumerate(self.rows):
            members[a.JOURNALS[i]] = encode(row)
        manifest = encode({'protocol': a.PROTOCOL, 'members': [pin(n, raw) for n, raw in sorted(members.items())]})
        summary = {'protocol': a.PROTOCOL, 'complete': complete, 'reason': receipt['reason'],
                   'begin': self.begin, 'returned_at': self.begin + self.outer_elapsed,
                   'elapsed_s': self.outer_elapsed, 'manifest_sha256': a.digest(manifest),
                   'receipt_sha256': a.digest(members['receipt.private.json']),
                   'controller_group_stop_confirmed': receipt['controller_group_stop_confirmed'],
                   'request_groups_stop_confirmed': receipt['request_groups_stop_confirmed'],
                   'registered_attempts': receipt['registered_attempts'],
                   'public_aggregate': aggregate}
        summary.update(self.summary_overrides)
        return Bundle(plan, manifest, members, encode(summary))


class Bundle:
    def __init__(self, plan, manifest, members, summary):
        self.plan, self.manifest, self.members, self.summary = plan, manifest, members, summary
        self.calls = []

    def read(self, name, cap):
        self.calls.append((name, cap))
        return self.members[name]

    def audit(self, reader=None, summary_pin=None):
        return a.audit(self.plan, self.manifest, reader or self.read, execution_summary_bytes=self.summary,
                       execution_summary_pin=summary_pin if summary_pin is not None else
                       {'bytes': len(self.summary), 'sha256': a.digest(self.summary)})

    def repin(self):
        self.manifest = encode({'protocol': a.PROTOCOL, 'members': [pin(n, raw) for n, raw in sorted(self.members.items())]})
        summary = json.loads(self.summary)
        summary['manifest_sha256'] = a.digest(self.manifest)
        summary['receipt_sha256'] = a.digest(self.members['receipt.private.json'])
        self.summary = encode(summary)


def sparse_bundle(count=3, *, elapsed=36.0):
    f = Fixture()
    registered = [{'batch_index': i, 'worker_group': 9000 + i} for i in range(count)]
    aggregate = {'rows': 65, 'TRAIN_rows': 41, 'DEV_rows': 24, 'metadata_unknown_rows': 4,
                 'nominal_ENZ_rows': 47, 'nominal_12Z_rows': 14, 'batches': 17,
                 'attempted_batches': count, 'unattempted_batches': 17 - count,
                 'accounting_known': False, 'accounting_complete_batches': 0,
                 'HTTP200_candidate_batches': 0, 'qualified_batches': 0,
                 'retained_response_bytes': None, 'overflow_probe_bytes': None,
                 'consumption_upper': count * 8388609, 'whole_complete': False, 'claims': dict(a.CLAIMS)}
    summary = {'protocol': a.PROTOCOL, 'complete': False, 'reason': 'controller_failed',
               'begin': 1000.0, 'returned_at': 1000.0 + elapsed, 'elapsed_s': elapsed,
               'manifest_sha256': None, 'receipt_sha256': None,
               'controller_group_stop_confirmed': False, 'request_groups_stop_confirmed': False,
               'registered_attempts': registered, 'public_aggregate': aggregate}
    return Bundle(encode(f.plan), None, {}, encode(summary))


class AuditTests(unittest.TestCase):
    def reject(self, b, issue=None):
        result = b.audit()
        self.assertFalse(result['valid'], result)
        self.assertEqual(result['qualified_batches'], 0)
        self.assertEqual(result['fixed_rows'], 65)
        self.assertEqual(result['fixed_batches'], 17)
        self.assertTrue(result['preserve_parent_artifacts'])
        self.assertTrue(all(v is False for v in result['claims'].values()))
        if issue:
            self.assertEqual(result['issues'], [issue])
        return result

    def test_all_fixed_batches_transport_only_and_one_bounded_read_per_member(self):
        b = Fixture().bundle()
        result = b.audit()
        self.assertTrue(result['valid'], result)
        self.assertTrue(result['whole_complete'])
        self.assertEqual(result['qualified_batches'], 17)
        self.assertEqual(len(b.members), 73)
        self.assertEqual(len(b.calls), 73)
        self.assertEqual(len(set(n for n, _ in b.calls)), 73)
        for field in ('filesystem_inventory_verified', 'original_selection_authenticated',
                      'source_runtime_authenticated', 'physical_process_stop_verified', 'physical_clock_verified'):
            self.assertFalse(result[field])
        for private in ('invented-', 'AX0', '1970-', 'worker_group', 'request_sha256', 'Content-Length'):
            self.assertNotIn(private, json.dumps(result))

    def test_canonical_blank_location_exact_nanosecond_utc_and_no_deduplication(self):
        self.assertEqual(a.utc_ns(-1), '1969-12-31T23:59:59.999999999Z')
        self.assertEqual(a.utc_ns(1), '1970-01-01T00:00:00.000000001Z')
        f = Fixture()
        f.plan['rows'][1]['t0_ns'] = f.plan['rows'][0]['t0_ns']
        f.plan['rows'][1]['location'] = f.plan['rows'][0]['location']
        f.rebuild_requests()
        self.assertEqual(len(f.plan['batches'][0]['request_body'].splitlines()), 5)
        self.assertEqual(f.plan['batches'][0]['request_body'].splitlines()[1],
                         f.plan['batches'][0]['request_body'].splitlines()[2])
        # This is a plan-only assertion; saved output must separately bind new entities.
        a._plan(encode(f.plan))
        self.assertIn(' -- BH? ', Fixture().plan['batches'][0]['request_body'])

    def test_plan_strict_types_fields_identity_TEST_and_fixed_denominator(self):
        changes = [('partition', 'TEST'), ('network', 'nx'), ('station', 'AX0 '),
                   ('location', '--'), ('prefix', 'BHZ'), ('t0_ns', True), ('t0_ns', 0.0),
                   ('pick_ns', None), ('original_event_index', True), ('original_target_index', -1),
                   ('event_id', '../bad'), ('metadata_status', 'http200'), ('nominal_family', None)]
        for field, value in changes:
            f = Fixture()
            f.plan['rows'][0][field] = value
            b = f.bundle()
            self.reject(b)
            self.assertEqual(b.calls, [])
        for field, value in (('protocol', 'old'), ('study_id', 'invented-post'), ('proposal_sha256', 'a' * 64)):
            f = Fixture()
            f.plan[field] = value
            b = f.bundle()
            self.reject(b)
            self.assertEqual(b.calls, [])
        f = Fixture()
        f.plan['rows'][0]['partition'] = 'DEV'
        self.reject(f.bundle(), 'plan_fixed_denominator')
        f = Fixture()
        f.plan['rows'][64]['nominal_family'] = 'ENZ'
        self.reject(f.bundle(), 'unknown_family')

    def test_original_event_order_uniqueness_and_row_count_cannot_change(self):
        for field, value in (('original_event_index', 0), ('event_id', 'invented-000'), ('row_index', 0)):
            f = Fixture()
            f.plan['rows'][1][field] = value
            b = f.bundle()
            self.reject(b)
            self.assertEqual(b.calls, [])
        for rows in ([], Fixture().plan['rows'][:-1], Fixture().plan['rows'] + Fixture().plan['rows'][:1]):
            f = Fixture()
            f.plan['rows'] = rows
            b = Fixture().bundle()
            b.plan = encode(f.plan)
            self.reject(b, 'plan_row_count')
            self.assertEqual(b.calls, [])

    def test_batch_order_membership_body_hash_and_canonical_entity_no_alias(self):
        for field, value in (('batch_index', True), ('row_indices', [0, 1, 2]),
                             ('row_indices', [False, 1, 2, 3]), ('request_body', 'format=miniseed\r\n'),
                             ('request_sha256', 'a' * 64)):
            f = Fixture()
            f.plan['batches'][0][field] = value
            b = f.bundle()
            self.reject(b)
            self.assertEqual(b.calls, [])
        for extra in ('endpoint', 'quality', 'fallback', 'reader', 'auth'):
            f = Fixture()
            f.plan[extra] = False
            self.reject(f.bundle(), 'plan_fields')

    def test_each_prerequisite_pin_type_and_exact_field_set_before_reads(self):
        for field in a.PREREQUISITES:
            for value in (None, True, 1, 'A' * 64, 'a' * 63, [], {}):
                f = Fixture()
                f.plan['prerequisites'][field] = value
                b = f.bundle()
                self.reject(b, 'prerequisite_pin')
                self.assertEqual(b.calls, [])
            f = Fixture()
            f.plan['prerequisites'].pop(field)
            self.reject(f.bundle(), 'prerequisite_fields')

    def test_complete_errors_empty_chunked_eof_and_no_body_retain_65_rows(self):
        for status, framing, raw in ((404, 'fixed', b'invented error'), (204, 'no_body', b''),
                                    (304, 'no_body', b''), (200, 'fixed', b''),
                                    (200, 'chunked', b'\x00\xffbinary'), (200, 'eof', b'binary')):
            f = Fixture()
            f.body(0, raw, status=status, framing=framing)
            result = f.bundle().audit()
            self.assertTrue(result['valid'], result)
            self.assertTrue(result['whole_complete'])
            self.assertEqual(result['qualified_batches'], 17 if status == 200 and raw else 16)
            self.assertEqual(result['fixed_rows'], 65)
            self.assertEqual(result['aggregate']['metadata_unknown_rows'], 4)

    def test_each_incomplete_outcome_halts_and_promotes_no_previous_candidate(self):
        for i in (0, 8, 16):
            for outcome in a.OUTCOMES - {'framed_complete'}:
                f = Fixture()
                f.halt(i, outcome=outcome)
                result = f.bundle().audit()
                self.assertTrue(result['valid'], result)
                self.assertFalse(result['whole_complete'])
                self.assertEqual(result['qualified_batches'], 0)
                self.assertEqual(result['aggregate']['attempted_batches'], i + 1)
                self.assertEqual(result['aggregate']['unattempted_batches'], 16 - i)
                self.assertEqual(result['aggregate']['qualified_batches'], 0)

    def test_attempt_after_incomplete_or_unattempted_is_never_accepted(self):
        f = Fixture()
        f.rows[0].update(outcome='partial', attempt_accounting_complete=False, HTTP200_candidate=False)
        b = f.bundle()
        self.reject(b, 'attempt_after_halt')
        self.assertTrue(all(n not in a.BODIES for n, _ in b.calls))

    def test_header_ambiguities_unknown_framing_are_preserved_without_qualification(self):
        fields = ([['Content-Length', '1'], ['Content-Length', '1']],
                  [['Transfer-Encoding', 'chunked'], ['Transfer-Encoding', 'chunked']],
                  [['Content-Length', '1'], ['Transfer-Encoding', 'chunked']],
                  [['Content-Length', ' 1']], [['Content-Length', '+1']],
                  [['Content-Length', '1' * 21]], [['Transfer-Encoding', 'gzip']],
                  [['Transfer-Encoding', ' chunked']], [['Transfer-Encoding', 'chunked,gzip']])
        for pairs in fields:
            f = Fixture()
            f.halt(0, outcome='framing_error')
            f.header(0, pairs, 'unknown', None)
            result = f.bundle().audit()
            self.assertTrue(result['valid'], result)
            self.assertFalse(result['whole_complete'])
            self.assertEqual(result['qualified_batches'], 0)
        f = Fixture()
        f.header(0, [['Content-Length', ' 1']], 'fixed', 1)
        self.reject(f.bundle(), 'fixed_length_mismatch')

    def test_framing_headers_status_pin_parser_limits_and_missing_empty_pin(self):
        for field, value in (('status', 404), ('framing', 'eof'), ('declared', 1)):
            b = Fixture().bundle()
            h = json.loads(b.members[a.HEADERS[0]])
            h[field] = value
            b.members[a.HEADERS[0]] = encode(h)
            b.repin()
            self.reject(b, 'header_manifest_binding')
        f = Fixture()
        f.body(0, b'')
        f.rows[0]['body'] = None
        f.payloads.pop(a.BODIES[0])
        self.reject(f.bundle(), 'framed_complete_evidence')

    def test_metadata_membership_extra_missing_traversal_and_wrong_original_index(self):
        for name in ('../bad', '017.body.private', 'manifest.private.json'):
            b = Fixture().bundle()
            b.members[name] = b'invented'
            b.repin()
            self.reject(b)
            self.assertEqual(b.calls, [])
        for name in ('initial.private.json', a.REQUESTS[16], a.JOURNALS[16]):
            b = Fixture().bundle()
            b.members.pop(name)
            b.repin()
            self.reject(b)
        f = Fixture()
        f.rows[0]['body']['name'] = a.BODIES[1]
        self.reject(f.bundle(), 'body_binding')

    def test_original_roster_and_exact_request_entities_cannot_be_repaired(self):
        b = Fixture().bundle()
        b.members['roster.private.json'] += b' '
        b.repin()
        self.reject(b, 'roster_original_bytes')
        b = Fixture().bundle()
        b.members[a.REQUESTS[0]] += b' '
        b.repin()
        self.reject(b, 'saved_request_entity')

    def test_json_layers_duplicate_nonfinite_invalid_utf8_and_bounds(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'\xff', b' ' * (a.MAX_PLAN + 1)):
            b = Fixture().bundle()
            b.plan = raw
            self.reject(b)
            self.assertEqual(b.calls, [])
        for name in ('initial.private.json', 'controller_summary.private.json', a.JOURNALS[0]):
            b = Fixture().bundle()
            b.members[name] = b'{"a":1,"a":2}'
            b.repin()
            self.reject(b)
            self.assertTrue(all(n not in a.BODIES for n, _ in b.calls))

    def test_bad_reader_body_hash_size_type_and_private_exceptions_fail_closed(self):
        b = Fixture().bundle()
        b.members[a.BODIES[0]] = b'tampered'
        self.reject(b, 'member_pin_mismatch')
        for reader in (lambda n, c: bytearray(b'{}'), lambda n, c: '{}'):
            self.assertFalse(Fixture().bundle().audit(reader=reader)['valid'])
        def reader(name, cap):
            raise OSError('private detail')
        result = Fixture().bundle().audit(reader=reader)
        self.assertEqual(result['issues'], ['member_reader_failure'])
        self.assertNotIn('private detail', json.dumps(result))

    def test_claims_fixture_limit_changed_controls_and_public_integer_aliases(self):
        for mutate in ({'fixture': True}, {'fixture': 0}, {'claims': {**a.CLAIMS, 'novelty_verified': True}},
                       {'limits': {**a.LIMITS, 'body_bytes': 8388608.0}}, {'limits': {**a.LIMITS, 'whole_s': 1}}):
            f = Fixture()
            f.controller_overrides.update(mutate)
            self.reject(f.bundle())
        for field in ('rows', 'qualified_batches', 'retained_response_bytes'):
            f = Fixture()
            f.aggregate_overrides[field] = True
            self.reject(f.bundle(), 'aggregate_integer')

    def test_outer_pins_wrong_flags_stop_exit_and_whole_return_deadline(self):
        for receipt in ({'controller_exit_code': 1}, {'controller_group_stop_confirmed': False},
                        {'request_groups_stop_confirmed': False}, {'elapsed_s': 37}):
            f = Fixture()
            f.receipt_overrides.update(receipt)
            self.reject(f.bundle())
        for summary in ({'elapsed_s': 2401, 'returned_at': 3401}, {'returned_at': 1037},
                        {'manifest_sha256': 'a' * 64}, {'receipt_sha256': 'a' * 64}, {'complete': False}):
            f = Fixture()
            f.summary_overrides.update(summary)
            b = f.bundle()
            self.reject(b)
        b = Fixture().bundle()
        self.assertFalse(b.audit(summary_pin={'bytes': len(b.summary), 'sha256': 'a' * 64})['valid'])
        self.assertEqual(b.calls, [])


    def test_full_known_caps_and_one_probe_overflow_are_distinct(self):
        raw = b'x' * a.LIMITS['body_bytes']
        f = Fixture()
        for i in range(17):
            f.body(i, raw)
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertTrue(result['whole_complete'])
        self.assertEqual(result['aggregate']['retained_response_bytes'], 142606336)
        self.assertEqual(result['aggregate']['consumption_upper'], 142606336)
        self.assertEqual(result['qualified_batches'], 17)
        f = Fixture()
        f.body(8, raw)
        f.halt(8, outcome='overflow')
        f.rows[8].update(overflow_probe_bytes=1, consumed_upper=a.LIMITS['body_bytes'] + 1)
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertFalse(result['whole_complete'])
        self.assertEqual(result['aggregate']['overflow_probe_bytes'], 1)
        self.assertEqual(result['qualified_batches'], 0)

    def test_unknown_consumption_charges_full_cap_plus_probe_and_cannot_complete(self):
        f = Fixture()
        f.halt(3, outcome='worker_exit')
        f.rows[3].update(consumption_exact=False, consumed_upper=a.LIMITS['body_bytes'] + 1,
                         worker_exit_code=-9, worker_exit_confirmed=False, worker_group_stop_confirmed=False)
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['qualified_batches'], 0)
        for value in (0, a.LIMITS['body_bytes'], a.LIMITS['body_bytes'] + 2):
            broken = copy.deepcopy(f)
            broken.rows[3]['consumed_upper'] = value
            self.reject(broken.bundle())

    def test_probe_counts_and_exact_consumption_cannot_hide_overflow(self):
        for change in ({'overflow_probe_bytes': True}, {'overflow_probe_bytes': 2},
                       {'consumed_upper': a.LIMITS['body_bytes'] + 2}, {'consumed_upper': 0},
                       {'overflow_probe_bytes': 1, 'consumed_upper': 27}):
            f = Fixture()
            f.rows[0].update(change)
            self.reject(f.bundle())
        f = Fixture()
        f.halt(0, outcome='overflow')
        f.rows[0].update(overflow_probe_bytes=1, consumed_upper=f.rows[0]['observed_bytes'] + 1)
        self.reject(f.bundle(), 'probe_at_cap')

    def test_declared_oversize_preserves_incomplete_zero_entity_and_no_body_legal_CL(self):
        f = Fixture()
        f.body(0, b'', complete=False, outcome='overflow')
        f.halt(0, outcome='overflow')
        f.header(0, [['Content-Length', str(a.LIMITS['body_bytes'] + 1)]], 'fixed', a.LIMITS['body_bytes'] + 1)
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertFalse(result['whole_complete'])
        self.assertEqual(result['qualified_batches'], 0)
        for status in (204, 304):
            f = Fixture()
            f.body(0, b'', status=status, framing='no_body')
            f.header(0, [['Content-Length', str(a.LIMITS['body_bytes'] + 1)]], 'no_body', a.LIMITS['body_bytes'] + 1)
            result = f.bundle().audit()
            self.assertTrue(result['valid'], result)
            self.assertTrue(result['whole_complete'])
            self.assertEqual(result['qualified_batches'], 16)

    def test_header_framing_derivation_not_just_saved_field_agreement(self):
        raw = Fixture().payloads[a.BODIES[0]]
        for pairs, framing, declared in (([['Content-Length', ' ' + str(len(raw))]], 'fixed', len(raw)),
                                         ([['Transfer-Encoding', 'CHUNKED ']], 'chunked', None),
                                         ([['Content-Length', str(len(raw))], ['Transfer-Encoding', 'chunked']], 'fixed', len(raw))):
            f = Fixture()
            if framing == 'chunked':
                f.body(0, raw, framing='chunked')
            f.header(0, pairs, framing, declared)
            self.reject(f.bundle(), 'header_framing_disagreement')
        f = Fixture()
        f.body(0, b'binary', framing='chunked')
        f.header(0, [['tRaNsFeR-EnCoDiNg', 'CHUNKED']], 'chunked', None)
        self.assertTrue(f.bundle().audit()['valid'])
        f = Fixture()
        f.body(0, b'', status=204, framing='no_body')
        f.header(0, [['Content-Length', '0'], ['Transfer-Encoding', 'chunked']], 'no_body', 0)
        self.reject(f.bundle(), 'header_framing_disagreement')

    def test_header_parser_and_diagnostic_caps_are_separate_from_wire_claims(self):
        for key, value in (('line_bytes', 1), ('header_count', 101), ('header_count', True),
                           ('chunk_trailer_count', True), ('chunk_trailer_count', 0)):
            f = Fixture()
            h = json.loads(f.payloads[a.HEADERS[0]])
            h['parser_limits'][key] = value
            f.payloads[a.HEADERS[0]] = encode(h)
            f.rows[0]['headers'] = pin(a.HEADERS[0], encode(h))
            self.reject(f.bundle())
        f = Fixture()
        f.header(0, [['x', 'value']] * 101, 'fixed', f.rows[0]['declared'])
        self.reject(f.bundle(), 'header_pair_bound')
        b = Fixture().bundle()
        m = json.loads(b.manifest)
        for p in m['members']:
            if p['name'] == a.HEADERS[0]:
                p['bytes'] = 131073
        b.manifest = encode(m)
        summary = json.loads(b.summary)
        summary['manifest_sha256'] = a.digest(b.manifest)
        b.summary = encode(summary)
        self.reject(b, 'member_duplicate_or_bound')
        self.assertEqual(b.calls, [])

    def test_late_connection_first_entity_request_and_processing_are_whole_incomplete(self):
        for mode in ('connection', 'first', 'request', 'processing'):
            f = Fixture()
            f.halt(0, outcome='framed_complete')
            row = f.rows[0]
            if mode == 'connection':
                row.update(connected_at=1011, headers_at=1011.1, first_body_at=1011.2, end=1012)
            elif mode == 'first':
                row.update(first_body_at=1061, end=1062)
            elif mode == 'request':
                row['end'] = 1121
            else:
                row.update(start=3159, connected_at=3159.1, headers_at=3159.2, first_body_at=3159.3, end=3161)
            f.final_elapsed = 2399
            f.outer_elapsed = 2400
            result = f.bundle().audit()
            if mode == 'processing':
                self.assertFalse(result['valid'], result)
            else:
                self.assertTrue(result['valid'], result)
            self.assertFalse(result['whole_complete'])
            self.assertEqual(result['qualified_batches'], 0)

    def test_start_cutoff_spacing_overlap_phase_order_and_clock_types(self):
        for change in ({'start': 999}, {'start': 3160}, {'start': True}, {'connected_at': True},
                       {'headers_at': 1000.05}, {'first_body_at': 999}, {'end': 999}):
            f = Fixture()
            f.rows[0].update(change)
            self.reject(f.bundle())
        f = Fixture()
        row = f.rows[1]
        row.update(start=1000.5, connected_at=1000.6, headers_at=1000.7, first_body_at=1000.8, end=1001)
        self.reject(f.bundle(), 'attempt_start_spacing')
        f = Fixture()
        f.rows[0]['end'] = 1003
        self.reject(f.bundle(), 'attempt_overlap')

    def test_failed_missing_telemetry_retained_but_completed_requires_connection_headers(self):
        f = Fixture()
        f.halt(0, outcome='worker_error')
        f.rows[0].update(connected_at=None, headers_at=None, first_body_at=None)
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertFalse(result['whole_complete'])
        for field in ('connected_at', 'headers_at', 'first_body_at'):
            f = Fixture()
            f.rows[0][field] = None
            self.reject(f.bundle(), 'attempt_computed_flags')

    def test_stop_flags_exit_codes_and_group_identity_replayed_without_physical_authentication(self):
        for change in ({'worker_exit_confirmed': False}, {'worker_group_stop_confirmed': False},
                       {'worker_exit_code': 1}, {'worker_exit_code': None}):
            f = Fixture()
            f.halt(0, outcome='framed_complete')
            f.rows[0].update(change)
            result = f.bundle().audit()
            self.assertTrue(result['valid'], result)
            self.assertFalse(result['whole_complete'])
            self.assertFalse(result['physical_process_stop_verified'])
        for change in ({'worker_group': True}, {'worker_group': 0}, {'worker_exit_code': False},
                       {'worker_group_stop_confirmed': 1}):
            f = Fixture()
            f.rows[0].update(change)
            self.reject(f.bundle())
        f = Fixture()
        f.rows[1]['worker_group'] = f.rows[0]['worker_group']
        self.reject(f.bundle(), 'registered_group_duplicate')
        f = Fixture()
        f.controller_overrides['worker_groups'] = list(reversed([row['worker_group'] for row in f.rows]))
        self.reject(f.bundle(), 'controller_groups')

    def test_all_unattempted_cutoff_fixed39_members_and_reason_evidence(self):
        f = Fixture()
        for i in range(17):
            f.rows[i] = {'batch_index': i, 'row_indices': f.plan['batches'][i]['row_indices'],
                         'request': pin(a.REQUESTS[i], f.plan['batches'][i]['request_body'].encode()),
                         'status': 'unattempted', 'reason': 'launch_cutoff'}
        f.payloads = {}
        f.controller_overrides['processing_elapsed'] = 2160
        f.final_elapsed = 2161
        f.outer_elapsed = 2162
        b = f.bundle()
        result = b.audit()
        self.assertTrue(result['valid'], result)
        self.assertEqual(len(b.members), 39)
        self.assertEqual(result['aggregate']['unattempted_batches'], 17)
        self.assertEqual(result['qualified_batches'], 0)
        for reason in ('total_cap', 'halted_after_incomplete'):
            broken = copy.deepcopy(f)
            broken.rows[0]['reason'] = reason
            self.reject(broken.bundle())
        broken = copy.deepcopy(f)
        broken.rows[1]['reason'] = 'halted_after_incomplete'
        self.reject(broken.bundle(), 'halt_without_incomplete_evidence')

    def test_saved_candidates_cannot_bypass_failed_outer_finalization(self):
        for reason in ('controller_failed', 'group_stop_unconfirmed', 'finalization_failed', 'deadline'):
            f = Fixture()
            f.receipt_overrides.update(complete=False, reason=reason)
            result = f.bundle().audit()
            self.assertTrue(result['valid'], result)
            self.assertEqual(result['aggregate']['HTTP200_candidate_batches'], 17)
            self.assertEqual(result['aggregate']['qualified_batches'], 0)
            self.assertFalse(result['finalization_verified'])
            self.assertEqual(result['qualified_batches'], 0)

    def test_journal_decoded_types_counts_and_fixed_roles_cannot_alias(self):
        for field, value in (('batch_index', False), ('request_index', False), ('consumption_exact', 1),
                             ('observed_bytes', 25.0), ('start', 1000)):
            b = Fixture().bundle()
            j = json.loads(b.members[a.JOURNALS[0]])
            if field == 'observed_bytes':
                value = float(j[field])
            j[field] = value
            b.members[a.JOURNALS[0]] = encode(j)
            b.repin()
            self.reject(b, 'journal_controller_disagreement')
        b = Fixture().bundle()
        j = json.loads(b.members[a.JOURNALS[0]])
        b.members[a.JOURNALS[0]] = json.dumps(dict(reversed(list(j.items()))), indent=2).encode()
        b.repin()
        self.assertTrue(b.audit()['valid'])

    def test_metadata_total_mask_initial_request_and_extra_payload_cannot_be_hidden(self):
        for field, value in (('attempts', True), ('retained_bytes', 0), ('HTTP200_candidates', 0),
                             ('candidate_complete', 1)):
            f = Fixture()
            f.controller_overrides[field] = value
            self.reject(f.bundle())
        f = Fixture()
        f.halt(0)
        f.payloads[a.BODIES[16]] = b'unattempted extra'
        b = f.bundle()
        self.reject(b, 'closed_manifest_membership')
        self.assertTrue(all(n not in a.BODIES for n, _ in b.calls))

    def test_no_body_no_headers_failed_attempt_and_unlisted_members_cannot_authenticate_fs(self):
        f = Fixture()
        f.halt(0, outcome='worker_error')
        f.rows[0].update(body=None, headers=None, observed_bytes=0, consumed_upper=8388609,
                         consumption_exact=False, http_status=None, framing='unknown', declared=None,
                         connected_at=None, headers_at=None, first_body_at=None)
        f.payloads = {}
        b = f.bundle()
        result = b.audit()
        self.assertTrue(result['valid'], result)
        self.assertEqual(len(b.members), 39)
        self.assertFalse(result['filesystem_inventory_verified'])
        self.assertEqual(result['qualified_batches'], 0)

    def test_hostile_summary_pin_objects_and_byte_subclasses_do_not_execute_comparisons(self):
        from test_strict_inputs import Hostile, StringSubclass, IntSubclass
        b = Fixture().bundle()
        for pin_value in ({'bytes': Hostile(), 'sha256': 'a' * 64},
                          {'bytes': IntSubclass(len(b.summary)), 'sha256': 'a' * 64},
                          {'bytes': len(b.summary), 'sha256': StringSubclass('a' * 64)},
                          {Hostile(): 1}):
            result = b.audit(summary_pin=pin_value)
            self.assertFalse(result['valid'])
            self.assertEqual(result['qualified_batches'], 0)
            self.assertEqual(b.calls, [])


    def test_new_V2_study_proposal_and_miniseed_wire_value_reject_unverified_alias(self):
        for field, value in (('study_id', 'geonet-original-TRAINDEV65-prefix3-native-POST-v1'),
                             ('proposal_sha256', 'c184d7f728013411883b960d7bfa714c8a3c642addab116c85a3df063256cfd9')):
            f = Fixture()
            f.plan[field] = value
            b = f.bundle()
            self.reject(b)
            self.assertEqual(b.calls, [])
        f = Fixture()
        batch = f.plan['batches'][0]
        batch['request_body'] = batch['request_body'].replace('format=miniseed', 'format=mseed', 1)
        batch['request_sha256'] = a.digest(batch['request_body'].encode())
        b = f.bundle()
        self.reject(b, 'request_entity')
        self.assertEqual(b.calls, [])

    def test_manifest_byte_bound_precedes_manifest_hash_or_any_member_read(self):
        from unittest.mock import patch
        b = Fixture().bundle()
        b.manifest = b' ' * (a.MAX_MANIFEST + 1)
        original = a.digest
        def bounded_digest(raw):
            if raw is b.manifest:
                raise AssertionError('over-bound manifest was hashed before validation')
            return original(raw)
        with patch.object(a, 'digest', bounded_digest):
            self.reject(b, 'manifest_bytes')
        self.assertEqual(b.calls, [])

    def test_retained_header_diagnostics_require_nonnull_HTTP_response_status(self):
        f = Fixture()
        f.halt(0, outcome='worker_error')
        f.rows[0].update(http_status=None, framing='unknown', declared=None,
                         connected_at=None, headers_at=None, first_body_at=None)
        f.header(0, [], 'unknown', None)
        self.reject(f.bundle(), 'header_http_status')

    def test_empty_entity_late_headers_cannot_bypass_first_entity_watchdog(self):
        f = Fixture()
        f.body(0, b'', status=204, framing='no_body')
        f.halt(0, outcome='framed_complete')
        f.rows[0].update(headers_at=1061, end=1062)
        f.final_elapsed = 119
        f.outer_elapsed = 120
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertFalse(result['whole_complete'])
        self.assertEqual(result['qualified_batches'], 0)


    def test_multichunk_binary_extensions_trailers_body_association_and_closed90_members(self):
        f = Fixture()
        for i in range(17):
            f.body(i, b'abc\x00\xffx', framing='chunked')
            raw = b'3;extension=ok\r\n\r\n3\r\n\r\n0\r\nTag: value\r\n\r\n'
            f.payloads[a.FRAMINGS[i]] = raw
            f.rows[i]['framing_evidence'] = pin(a.FRAMINGS[i], raw)
        b = f.bundle()
        result = b.audit()
        self.assertTrue(result['valid'], result)
        self.assertTrue(result['whole_complete'])
        self.assertEqual(result['qualified_batches'], 17)
        self.assertEqual(len(b.members), 90)
        self.assertEqual(len(b.calls), 90)
        self.assertEqual(len(set(n for n, _ in b.calls)), 90)

    def test_malformed_closed_chunk_claims_delimiters_terminal_trailers_sizes_and_excess(self):
        malformed = (b'6\r\nXX0\r\n\r\n', b'6\r\n\r\n0\r\n',
                     b'6\r\n\r\n0\r\nbadtrailer\r\n\r\n',
                     b'6\r\n\r\n0\r\n Fold: value\r\n\r\n',
                     b'6\r\n\r\n0\r\nX:value\n\r\n',
                     b'6\r\n\r\n0\r\n\r\nextra', b'7\r\n\r\n0\r\n\r\n',
                     b'5\r\n\r\n0\r\n\r\n', b' 6\r\n\r\n0\r\n\r\n',
                     b'+6\r\n\r\n0\r\n\r\n', b'f' * 17 + b'\r\n\r\n0\r\n\r\n',
                     b'6;\x00\r\n\r\n0\r\n\r\n', b'6\n\r\n0\r\n\r\n')
        for raw in malformed:
            with self.subTest(raw=raw[:30]):
                f = Fixture()
                f.body(0, b'abcdef', framing='chunked')
                f.payloads[a.FRAMINGS[0]] = raw
                f.rows[0]['framing_evidence'] = pin(a.FRAMINGS[0], raw)
                b = f.bundle()
                self.reject(b, 'chunk_evidence_not_closed')
                self.assertTrue(all(n not in a.BODIES for n, _ in b.calls))
                f.halt(0, outcome='framing_error')
                f.rows[0]['framing_evidence_complete'] = False
                result = f.bundle().audit()
                self.assertTrue(result['valid'], result)
                self.assertFalse(result['whole_complete'])
                self.assertEqual(result['qualified_batches'], 0)

    def test_chunk_missing_evidence_flag_nonchunked_injection_and_original_binding(self):
        f = Fixture()
        f.body(0, b'abcdef', framing='chunked')
        f.rows[0].update(framing_evidence=None, framing_evidence_complete=False)
        f.payloads.pop(a.FRAMINGS[0])
        self.reject(f.bundle(), 'closed_chunk_evidence_missing')
        f = Fixture()
        raw = b'0\r\n\r\n'
        f.payloads[a.FRAMINGS[0]] = raw
        f.rows[0].update(framing_evidence=pin(a.FRAMINGS[0], raw), framing_evidence_complete=True)
        self.reject(f.bundle(), 'nonchunked_evidence')
        f = Fixture()
        f.body(0, b'abcdef', framing='chunked')
        f.rows[0]['framing_evidence']['name'] = a.FRAMINGS[1]
        self.reject(f.bundle(), 'framing_binding')
        f.rows[0]['framing_evidence_complete'] = 1
        self.reject(f.bundle())

    def test_chunk_trailer_count_line_and_combined_diagnostic_bounds(self):
        prefix = b'6\r\n\r\n0\r\n'
        f = Fixture()
        f.body(0, b'abcdef', framing='chunked')
        for count in (99, 100):
            raw = prefix + b'X:v\r\n' * count + b'\r\n'
            f.payloads[a.FRAMINGS[0]] = raw
            f.rows[0]['framing_evidence'] = pin(a.FRAMINGS[0], raw)
            if count == 99:
                self.assertTrue(f.bundle().audit()['valid'])
            else:
                self.reject(f.bundle(), 'chunk_evidence_not_closed')
        raw = b'6;' + b'x' * 65532 + b'\r\n\r\n0\r\n\r\n'
        f.payloads[a.FRAMINGS[0]] = raw
        f.rows[0]['framing_evidence'] = pin(a.FRAMINGS[0], raw)
        self.assertTrue(f.bundle().audit()['valid'])
        raw = b'6;' + b'x' * 65533 + b'\r\n\r\n0\r\n\r\n'
        f.payloads[a.FRAMINGS[0]] = raw
        f.rows[0]['framing_evidence'] = pin(a.FRAMINGS[0], raw)
        self.reject(f.bundle(), 'chunk_evidence_not_closed')
        raw = b'x' * 131072
        f.payloads[a.FRAMINGS[0]] = raw
        f.rows[0]['framing_evidence'] = pin(a.FRAMINGS[0], raw)
        self.reject(f.bundle(), 'combined_diagnostic_cap')

    def test_informational_status_never_becomes_final_EOF_transport(self):
        for status in (100, 101, 103, 199):
            f = Fixture()
            f.body(0, b'upgrade', status=status, framing='eof')
            self.reject(f.bundle(), 'header_framing_disagreement')
            f.halt(0, outcome='framing_error')
            f.header(0, [], 'unknown', None)
            result = f.bundle().audit()
            self.assertTrue(result['valid'], result)
            self.assertFalse(result['whole_complete'])
            self.assertEqual(result['qualified_batches'], 0)

    def test_sparse_registered_groups_replay_conservative_unknown_accounting_without_reads(self):
        for count in (0, 1, 3, 17):
            for elapsed in (36.0, 2401.0):
                b = sparse_bundle(count, elapsed=elapsed)
                result = b.audit()
                self.assertFalse(result['valid'])
                self.assertFalse(result['whole_complete'])
                self.assertFalse(result['finalization_verified'])
                self.assertTrue(result['registered_setup_accounting_verified'])
                self.assertEqual(result['aggregate']['attempted_batches'], count)
                self.assertEqual(result['aggregate']['unattempted_batches'], 17 - count)
                self.assertEqual(result['aggregate']['consumption_upper'], count * 8388609)
                self.assertIsNone(result['aggregate']['retained_response_bytes'])
                self.assertIsNone(result['aggregate']['overflow_probe_bytes'])
                self.assertEqual(result['qualified_batches'], 0)
                self.assertEqual(b.calls, [])

    def test_sparse_counts_nulls_flags_extra_manifest_and_duplicate_groups_reject_laundering(self):
        changes = (('consumption_upper', 0), ('retained_response_bytes', 0), ('overflow_probe_bytes', 0),
                   ('HTTP200_candidate_batches', 1), ('accounting_complete_batches', 1),
                   ('qualified_batches', 1), ('whole_complete', True), ('attempted_batches', True))
        for field, value in changes:
            b = sparse_bundle()
            summary = json.loads(b.summary)
            summary['public_aggregate'][field] = value
            b.summary = encode(summary)
            self.reject(b)
            self.assertEqual(b.calls, [])
        for field, value in (('complete', True), ('reason', 'complete'), ('manifest_sha256', 'a' * 64),
                             ('receipt_sha256', 'a' * 64)):
            b = sparse_bundle()
            summary = json.loads(b.summary)
            summary[field] = value
            b.summary = encode(summary)
            self.reject(b, 'sparse_finalization_disagreement')
        b = sparse_bundle()
        b.manifest = b'{}'
        self.reject(b, 'sparse_finalization_disagreement')
        for change in ({'batch_index': True}, {'batch_index': 2}, {'worker_group': True},
                       {'worker_group': 9000}, {'extra': 1}):
            b = sparse_bundle()
            summary = json.loads(b.summary)
            summary['registered_attempts'][1].update(change)
            b.summary = encode(summary)
            self.reject(b)
            self.assertEqual(b.calls, [])

    def test_known_registered_setup_proof_matches_journals_groups_and_receipt(self):
        b = Fixture().bundle()
        summary = json.loads(b.summary)
        summary['registered_attempts'][16]['worker_group'] = 9999
        b.summary = encode(summary)
        self.reject(b, 'registered_controller_disagreement')
        b = Fixture().bundle()
        receipt = json.loads(b.members['receipt.private.json'])
        receipt['registered_attempts'][0]['batch_index'] = False
        b.members['receipt.private.json'] = encode(receipt)
        b.repin()
        self.reject(b, 'registered_controller_disagreement')

    def test_saved_aggregate_permanently_provisional_and_only_returned_promotion_qualifies(self):
        b = Fixture().bundle()
        saved = json.loads(b.members['public_aggregate.json'])
        self.assertFalse(saved['whole_complete'])
        self.assertEqual(saved['qualified_batches'], 0)
        result = b.audit()
        self.assertTrue(result['valid'], result)
        self.assertTrue(result['aggregate']['whole_complete'])
        self.assertEqual(result['qualified_batches'], 17)
        saved.update(whole_complete=True, qualified_batches=17)
        b.members['public_aggregate.json'] = encode(saved)
        b.repin()
        self.reject(b, 'aggregate_disagreement')
        b = Fixture().bundle()
        summary = json.loads(b.summary)
        summary['public_aggregate'].update(whole_complete=False, qualified_batches=0)
        b.summary = encode(summary)
        self.reject(b, 'aggregate_disagreement')

    def test_failed_controller_cannot_assert_known_accounting_from_a_saved_summary(self):
        f = Fixture()
        f.receipt_overrides.update(complete=False, reason='controller_failed', controller_exit_code=1)
        b = f.bundle()
        self.reject(b, 'known_controller_not_normal')
        self.assertTrue(all(n not in a.BODIES for n, _ in b.calls))


if __name__ == '__main__':
    unittest.main()

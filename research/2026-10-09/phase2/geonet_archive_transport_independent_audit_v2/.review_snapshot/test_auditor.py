"""Invented-only fixtures; no transport, actual metadata, or file reader."""
import copy
import hashlib
import json
import unittest

import auditor as a


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def pin(name, raw):
    return {'name': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def literal(n=0, year='2025', doy='123'):
    return f'waveforms/miniseed/{year}/{year}.{doy}/AX{n}.NX/{year}.{doy}.AX{n}.Z3-Y12.NX.D'


class Fixture:
    def __init__(self):
        self.plan = {'protocol': a.PROTOCOL, 'study_id': 'invented-transport',
                     'proposal_sha256': a.PROPOSAL_SHA, 'template_source_sha256': a.TEMPLATE_SHA,
                     'mapping_status': a.MAPPING, 'transport_hypothesis': a.HYPOTHESIS,
                     'uncertainty_evidence_sha256': a.UNCERTAINTY_SHA, 'preregistration_sha256': 'a' * 64,
                     'slots': [{'slot_id': name, 'key': literal(i), 'unavailable_reason': None,
                                'uncertainties': list(a.UNCERTAINTIES)} for i, name in enumerate(a.SLOTS)]}
        self.rows = []
        self.bodies = {}
        self.final_elapsed = 20.0
        self.return_elapsed = 21.0
        self.summary_overrides = {}
        self.initial_overrides = {}
        self.final_overrides = {}
        for i, name in enumerate(a.SLOTS):
            start = 100.0 + i * 2
            body = f'invented retained transport body {i}'.encode()
            self.bodies[a.BODIES[i]] = body
            self.rows.append({'slot_id': name, 'key': literal(i), 'uncertainties': list(a.UNCERTAINTIES),
                              'status': 'attempted', 'request_index': i, 'start': start,
                              'connected_at': start + .125, 'headers_at': start + .25,
                              'first_body_at': start + .375, 'end': start + .5,
                              'http_status': 200, 'declared': len(body), 'outcome': 'body_complete',
                              'consumed': len(body), 'body': pin(a.BODIES[i], body),
                              'observed_bytes': len(body), 'consumed_upper': len(body),
                              'consumption_exact': True, 'receipt_verified': True,
                              'worker_exit_confirmed': True, 'transport_pass': True})

    def unavailable(self, i):
        self.plan['slots'][i]['key'] = None
        self.plan['slots'][i]['unavailable_reason'] = 'invented_missing_channel'
        self.bodies.pop(a.BODIES[i], None)
        self.rows[i] = {'slot_id': a.SLOTS[i], 'key': None, 'uncertainties': list(a.UNCERTAINTIES),
                        'status': 'unavailable', 'reason': 'invented_missing_channel'}
        self.reindex()

    def shared(self, i, source=0):
        self.plan['slots'][i]['key'] = self.plan['slots'][source]['key']
        self.bodies.pop(a.BODIES[i], None)
        original = self.rows[source]
        self.rows[i] = {'slot_id': a.SLOTS[i], 'key': original['key'],
                        'uncertainties': list(a.UNCERTAINTIES), 'status': 'shared_object',
                        'source_slot_index': source, 'request_index': original['request_index'],
                        'transport_pass': original['transport_pass']}
        self.reindex()

    def unattempted(self, i, reason='new_request_deadline'):
        self.bodies.pop(a.BODIES[i], None)
        self.rows[i] = {'slot_id': a.SLOTS[i], 'key': self.plan['slots'][i]['key'],
                        'uncertainties': list(a.UNCERTAINTIES), 'status': 'unattempted', 'reason': reason}
        self.final_elapsed = 700.0
        self.return_elapsed = 701.0
        self.reindex()

    def reindex(self):
        index = 0
        for row in self.rows:
            if row['status'] == 'attempted':
                row['request_index'] = index
                index += 1
            elif row['status'] == 'shared_object':
                row['request_index'] = self.rows[row['source_slot_index']]['request_index']
                row['transport_pass'] = self.rows[row['source_slot_index']]['transport_pass']

    def body(self, i, raw, outcome='body_complete', passing=True):
        self.bodies[a.BODIES[i]] = raw
        self.rows[i].update(body=pin(a.BODIES[i], raw), consumed=len(raw), observed_bytes=len(raw),
                            consumed_upper=len(raw), declared=len(raw), outcome=outcome, transport_pass=passing)

    def bundle(self):
        plan_bytes = encode(self.plan)
        common = {'protocol': a.PROTOCOL, 'study_id': self.plan['study_id'],
                  'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(), 'complete': False,
                  'fixture': False, 'limits': dict(a.LIMITS), 'mapping_status': a.MAPPING,
                  'transport_hypothesis': a.HYPOTHESIS, 'template_source_sha256': a.TEMPLATE_SHA,
                  'uncertainty_evidence_sha256': a.UNCERTAINTY_SHA,
                  'preregistration_sha256': self.plan['preregistration_sha256'],
                  'claims': dict(a.CLAIMS), 'run_begin': 100.0, 'request_policy': dict(a.POLICY),
                  'slots': [{'slot_id': name, 'status': 'unavailable' if self.plan['slots'][i]['key'] is None else 'unattempted',
                             'uncertainties': list(a.UNCERTAINTIES)} for i, name in enumerate(a.SLOTS)]}
        initial = copy.deepcopy(common)
        initial.update(self.initial_overrides)
        attempted = [row for row in self.rows if row['status'] == 'attempted']
        complete = all(row['status'] != 'unattempted' for row in self.rows)
        all_pass = all(row.get('transport_pass', False) for row in self.rows)
        final = copy.deepcopy(common)
        final.update(complete=complete, slots=copy.deepcopy(self.rows), attempts=len(attempted),
                     consumed_upper=sum(row['consumed_upper'] for row in attempted),
                     observed_body_bytes=sum(row['observed_bytes'] for row in attempted),
                     all_slots_transport_pass=all_pass, elapsed_s=self.final_elapsed)
        final.update(self.final_overrides)
        members = {'roster.private.json': plan_bytes, 'initial.private.json': encode(initial),
                   'receipt.private.json': encode(final), **self.bodies}
        members.update({a.JOURNALS[i]: encode(row) for i, row in enumerate(self.rows)})
        manifest = {'protocol': a.PROTOCOL, 'members': [pin(name, members[name]) for name in sorted(members)]}
        manifest_bytes = encode(manifest)
        summary = {'result': 'finalized', 'complete': complete, 'all_slots_transport_pass': all_pass,
                   'mapping_status': a.MAPPING, 'claims': dict(a.CLAIMS), 'begin': 100.0,
                   'returned_at': 100.0 + self.return_elapsed, 'elapsed_s': self.return_elapsed,
                   'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest()}
        summary.update(self.summary_overrides)
        return Bundle(plan_bytes, manifest_bytes, members, encode(summary))


class Bundle:
    def __init__(self, plan, manifest, members, summary):
        self.plan, self.manifest, self.members, self.summary = plan, manifest, members, summary
        self.calls = []

    def reader(self, name, bound):
        self.calls.append((name, bound))
        return self.members[name]

    def audit(self, reader=None, summary_pin=None):
        summary_pin = summary_pin if summary_pin is not None else {
            'bytes': len(self.summary), 'sha256': hashlib.sha256(self.summary).hexdigest()}
        return a.audit(self.plan, self.manifest, reader or self.reader,
                       execution_summary_bytes=self.summary, execution_summary_pin=summary_pin)

    def repin_manifest(self):
        manifest = {'protocol': a.PROTOCOL, 'members': [pin(name, raw) for name, raw in sorted(self.members.items())]}
        self.manifest = encode(manifest)
        summary = json.loads(self.summary)
        summary['manifest_sha256'] = hashlib.sha256(self.manifest).hexdigest()
        self.summary = encode(summary)


class AuditTests(unittest.TestCase):
    def rejected(self, bundle, issue=None):
        result = bundle.audit()
        self.assertFalse(result['valid'])
        self.assertEqual(result['qualified_slot_count'], 0)
        self.assertTrue(result['preserve_parent_artifacts'])
        self.assertTrue(all(value is False for value in result['claims'].values()))
        if issue:
            self.assertEqual(result['issues'], [issue])
        return result

    def test_four_exact_bodies_and_single_read_per_member(self):
        b = Fixture().bundle()
        result = b.audit()
        self.assertTrue(result['valid'])
        self.assertEqual(result['audit_protocol'], 'geonet-independent-archive-transport-audit-v2')
        self.assertTrue(result['complete_accounting'])
        self.assertTrue(result['finalization_verified'])
        self.assertTrue(result['all_slots_transport_pass'])
        self.assertEqual(result['qualified_slot_count'], 4)
        self.assertEqual(result['attempt_count'], 4)
        self.assertEqual(len(b.calls), len(b.members))
        self.assertEqual(len({name for name, _ in b.calls}), len(b.calls))
        self.assertFalse(result['filesystem_inventory_verified'])
        self.assertFalse(result['physical_timing_verified'])
        self.assertNotIn('waveforms/miniseed/', json.dumps(result))

    def test_shared_denominator_counts_slots_but_bytes_once(self):
        f = Fixture()
        for i in range(1, 4):
            f.shared(i)
        result = f.bundle().audit()
        self.assertTrue(result['valid'])
        self.assertEqual(result['attempt_count'], 1)
        self.assertEqual(result['qualified_slot_count'], 4)
        self.assertEqual(result['observed_body_bytes'], len(f.bodies[a.BODIES[0]]))

    def test_failed_source_is_shared_without_retry(self):
        f = Fixture()
        f.rows[0].update(http_status=503, transport_pass=False)
        f.shared(1)
        result = f.bundle().audit()
        self.assertTrue(result['valid'])
        self.assertEqual(result['attempt_count'], 3)
        self.assertEqual(result['qualified_slot_count'], 2)
        self.assertFalse(result['all_slots_transport_pass'])

    def test_unavailable_remains_in_denominator(self):
        f = Fixture()
        f.unavailable(1)
        result = f.bundle().audit()
        self.assertTrue(result['valid'])
        self.assertTrue(result['complete_accounting'])
        self.assertEqual(result['qualified_slot_count'], 3)
        self.assertEqual(result['slots'][1]['status'], 'unavailable')

    def test_all_unavailable_has_complete_accounting_zero_pass(self):
        f = Fixture()
        for i in range(4):
            f.unavailable(i)
        result = f.bundle().audit()
        self.assertTrue(result['valid'])
        self.assertTrue(result['complete_accounting'])
        self.assertEqual(result['attempt_count'], 0)
        self.assertEqual(result['qualified_slot_count'], 0)

    def test_unattempted_final_run_qualifies_nothing(self):
        f = Fixture()
        f.unattempted(3)
        b = f.bundle()
        result = b.audit()
        self.assertTrue(result['valid'])
        self.assertFalse(result['complete_accounting'])
        self.assertEqual(result['qualified_slot_count'], 0)
        self.assertTrue(all(row['transport_pass'] is False for row in result['slots']))
        self.assertNotIn(a.BODIES[3], {name for name, _ in b.calls})

    def test_missing_final_manifest_or_execution_never_reads_members(self):
        b = Fixture().bundle()
        cases = [(None, b.summary, {'bytes': len(b.summary), 'sha256': a._digest(b.summary)}),
                 (b.manifest, None, None)]
        for manifest, summary, summary_pin in cases:
            with self.subTest(manifest_missing=manifest is None):
                result = a.audit(b.plan, manifest, b.reader, execution_summary_bytes=summary,
                                 execution_summary_pin=summary_pin)
                self.assertEqual(result['qualified_slot_count'], 0)
                self.assertFalse(result['valid'])
        self.assertEqual(b.calls, [])

    def test_failed_or_over_budget_summary_never_reads(self):
        for override in ({'result': 'controller_failed'}, {'result': 'run_deadline'},
                         {'elapsed_s': 901, 'returned_at': 1001}, {'elapsed_s': -1},
                         {'returned_at': 122}, {'manifest_sha256': 'b' * 64}):
            with self.subTest(override=override):
                f = Fixture()
                f.summary_overrides.update(override)
                b = f.bundle()
                self.rejected(b)
                self.assertEqual(b.calls, [])

    def test_summary_external_pin_mismatch(self):
        b = Fixture().bundle()
        result = b.audit(summary_pin={'bytes': len(b.summary), 'sha256': '0' * 64})
        self.assertEqual(result['issues'], ['execution_pin_mismatch'])
        self.assertEqual(b.calls, [])

    def test_plan_exclusions(self):
        for field, value in [('day_basis', 'UTC'), ('mapping_verified', True), ('alternate_keys', []),
                             ('auth', False), ('inventory_verified', True)]:
            with self.subTest(field=field):
                f = Fixture()
                f.plan[field] = value
                self.rejected(f.bundle(), 'plan_fields')

    def test_plan_pins_status_and_hypothesis_are_exact(self):
        for field, value in [('protocol', 'other'), ('proposal_sha256', '0' * 64),
                             ('template_source_sha256', '0' * 64), ('mapping_status', 'verified'),
                             ('transport_hypothesis', 'other'), ('uncertainty_evidence_sha256', '0' * 64),
                             ('preregistration_sha256', 'A' * 64), ('study_id', 'A')]:
            with self.subTest(field=field):
                f = Fixture()
                f.plan[field] = value
                self.rejected(f.bundle())

    def test_slot_order_count_uncertainty_and_reason(self):
        mutations = [lambda f: f.plan['slots'].reverse(), lambda f: f.plan['slots'].pop(),
                     lambda f: f.plan['slots'][0]['uncertainties'].reverse(),
                     lambda f: f.plan['slots'][0].update(unavailable_reason='no_channel'),
                     lambda f: f.plan['slots'][0].update(key=None, unavailable_reason=None),
                     lambda f: f.plan['slots'][0].update(key=None, unavailable_reason='bad reason')]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                f = Fixture()
                mutate(f)
                b = Fixture().bundle()
                b.plan = encode(f.plan)
                self.rejected(b)

    def test_literal_key_shapes_no_normalization_alias_or_blank(self):
        key = literal()
        candidates = [key.lower(), key + '?x=1', key + '/', key.replace('.Z3-Y12.', '.-Y12.'),
                      key.replace('.Z3-Y12.', '.  -Y12.'), key.replace('AX0.Z3-Y', 'AX1.Z3-Y'),
                      key.replace('/2025.123/', '/2025.124/'), literal(year='0000'),
                      literal(doy='000'), literal(doy='366'), key.replace('Y12', 'Y1'),
                      key.replace('NX', 'N'), key.replace('AX0', 'AX')]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                f = Fixture()
                f.plan['slots'][0]['key'] = candidate
                self.rejected(f.bundle())
        f = Fixture()
        f.plan['slots'][0]['key'] = literal(year='2024', doy='366')
        f.rows[0]['key'] = f.plan['slots'][0]['key']
        self.assertTrue(f.bundle().audit()['valid'])

    def test_configured_network_and_location_order_is_distinguished(self):
        configured = literal()
        self.assertIn('/AX0.NX/2025.123.AX0.Z3-Y12.NX.D', configured)
        match = a.KEY.fullmatch(configured)
        self.assertIsNotNone(match)
        self.assertEqual(match['network'], 'NX')
        self.assertEqual(match['location'], 'Z3')
        previous_tutorial = configured.replace('AX0.Z3-Y12.NX.D', 'AX0.NX-Y12.Z3.D')
        f = Fixture()
        f.plan['slots'][0]['key'] = previous_tutorial
        self.rejected(f.bundle(), 'plan_key_shape')

    def test_configured_filename_repeats_directory_network_and_other_fields(self):
        valid = literal()
        variants = [valid.replace('Y12.NX.D', 'Y12.Z3.D'),
                    valid.replace('/AX0.NX/', '/AX0.Z3/'),
                    valid.replace('2025.123.AX0.Z3-', '2025.124.AX0.Z3-'),
                    valid.replace('2025.123.AX0.Z3-', '2024.123.AX0.Z3-'),
                    valid.replace('2025.123.AX0.Z3-', '2025.123.AX1.Z3-'),
                    valid.replace('AX0.Z3-Y12.NX.D', 'AX0.Z3-NX.Y12.D')]
        for candidate in variants:
            with self.subTest(candidate=candidate):
                f = Fixture()
                f.plan['slots'][0]['key'] = candidate
                self.rejected(f.bundle(), 'plan_key_shape')

    def test_equal_network_location_strings_do_not_prove_semantic_mapping(self):
        f = Fixture()
        f.plan['slots'][0]['key'] = literal().replace('AX0.Z3-', 'AX0.NX-')
        f.rows[0]['key'] = f.plan['slots'][0]['key']
        result = f.bundle().audit()
        self.assertTrue(result['valid'])
        self.assertEqual(result['mapping_status'], 'unverified_hypothesis')
        self.assertTrue(all(value is False for value in result['claims'].values()))

    def test_prior_protocol_and_evidence_pins_cannot_alias_new_contract(self):
        legacy = [('protocol', 'geonet-anonymous-archive-transport-v2'),
                  ('proposal_sha256', 'ae85f4f2a1431cc4b30c91fcc5caab8cc040d36c51ce744f93ef62ae34290a1a'),
                  ('template_source_sha256', 'f6449a1afade401de0e4cc79b9cca081996d6818cfd112468555f91facc9aa56'),
                  ('uncertainty_evidence_sha256', 'c4ac22937300dfc9644a0a0b4d5f735b8663234e6839704da3c211d34ce90230'),
                  ('transport_hypothesis', 'anonymous_nominal_literal_key_gets')]
        for field, value in legacy:
            with self.subTest(field=field):
                f = Fixture()
                f.plan[field] = value
                self.rejected(f.bundle(), 'plan_' + field)

    def test_raw_config_pin_is_distinct_from_authored_profile(self):
        authored = '7031bb9cdb97d1c1463bd0b2f8527bf4fbbec279d81e37d836003a687e98e5da'
        f = Fixture()
        f.plan['template_source_sha256'] = authored
        self.rejected(f.bundle(), 'plan_template_source_sha256')
        for field in ('configured_template_sha256', 'source_profile_sha256'):
            with self.subTest(field=field):
                f = Fixture()
                f.plan[field] = authored
                self.rejected(f.bundle(), 'plan_fields')

    def test_legacy_manifest_or_receipt_identity_is_not_promoted(self):
        for receipt in ('initial.private.json', 'receipt.private.json'):
            with self.subTest(receipt=receipt):
                b = Fixture().bundle()
                row = json.loads(b.members[receipt])
                row['protocol'] = 'geonet-anonymous-archive-transport-v2'
                b.members[receipt] = encode(row)
                b.repin_manifest()
                self.rejected(b)
        b = Fixture().bundle()
        manifest = json.loads(b.manifest)
        manifest['protocol'] = 'geonet-anonymous-archive-transport-v2'
        b.manifest = encode(manifest)
        summary = json.loads(b.summary)
        summary['manifest_sha256'] = a._digest(b.manifest)
        b.summary = encode(summary)
        self.rejected(b, 'manifest_protocol')

    def test_duplicate_attempt_and_bad_shared_binding(self):
        f = Fixture()
        f.plan['slots'][1]['key'] = f.plan['slots'][0]['key']
        f.rows[1]['key'] = f.rows[0]['key']
        self.rejected(f.bundle(), 'duplicate_attempt')
        for field, value in [('source_slot_index', 1), ('source_slot_index', True),
                             ('request_index', 9), ('transport_pass', False)]:
            with self.subTest(field=field):
                f = Fixture()
                f.shared(1)
                f.rows[1][field] = value
                self.rejected(f.bundle())

    def test_replacement_and_no_unattempted_after_source(self):
        f = Fixture()
        f.rows[0]['key'] = literal(9)
        self.rejected(f.bundle(), 'final_slot_binding')
        f = Fixture()
        f.shared(1)
        f.unattempted(1)
        self.rejected(f.bundle(), 'unattempted_duplicate_source')

    def test_journal_and_roster_original_bytes(self):
        b = Fixture().bundle()
        row = json.loads(b.members[a.JOURNALS[0]])
        row['transport_pass'] = False
        b.members[a.JOURNALS[0]] = encode(row)
        b.repin_manifest()
        self.rejected(b, 'journal_final_mismatch')
        b = Fixture().bundle()
        b.members['roster.private.json'] += b'\n'
        b.repin_manifest()
        self.rejected(b, 'roster_original_bytes_mismatch')

    def test_missing_added_traversal_and_duplicate_members(self):
        for name in ('receipt.private.json', a.JOURNALS[3]):
            b = Fixture().bundle()
            b.members.pop(name)
            b.repin_manifest()
            self.rejected(b)
        for name in ('../bad', 'manifest.private.json', '004.body.private'):
            b = Fixture().bundle()
            b.members[name] = b'invented'
            b.repin_manifest()
            self.rejected(b)
        b = Fixture().bundle()
        m = json.loads(b.manifest)
        m['members'].append(m['members'][0])
        b.manifest = encode(m)
        summary = json.loads(b.summary)
        summary['manifest_sha256'] = a._digest(b.manifest)
        b.summary = encode(summary)
        self.rejected(b)

    def test_unattempted_extra_body_rejected_without_body_read(self):
        f = Fixture()
        f.unattempted(3)
        b = f.bundle()
        b.members[a.BODIES[3]] = b'invented unattempted file'
        b.repin_manifest()
        self.rejected(b, 'manifest_membership_disagreement')
        self.assertTrue(all(name not in a.BODIES for name, _ in b.calls))

    def test_hash_count_reader_bounds_errors_and_types(self):
        b = Fixture().bundle()
        b.members[a.BODIES[0]] = b'tampered'
        self.rejected(b, 'member_pin_mismatch')
        for callback in (lambda n, c: 'not bytes', lambda n, c: bytearray(b'bytes')):
            b = Fixture().bundle()
            self.assertFalse(b.audit(reader=callback)['valid'])
        def failing(name, cap):
            raise OSError('private details must never appear')
        result = Fixture().bundle().audit(reader=failing)
        self.assertEqual(result['issues'], ['member_reader_failure'])
        self.assertNotIn('private details', json.dumps(result))

    def test_body_bound_is_checked_before_read(self):
        b = Fixture().bundle()
        m = json.loads(b.manifest)
        for p in m['members']:
            if p['name'] == a.BODIES[0]:
                p['bytes'] = a.LIMITS['per_body_bytes'] + 1
        b.manifest = encode(m)
        s = json.loads(b.summary)
        s['manifest_sha256'] = a._digest(b.manifest)
        b.summary = encode(s)
        self.rejected(b, 'member_pin_bound')
        self.assertEqual(b.calls, [])

    def test_json_duplicate_nonfinite_utf8_depth_and_size(self):
        b = Fixture().bundle()
        invalid = [b'{"protocol":1,"protocol":2}', b'{"n":NaN}', b'{"n":1e999}', b'\xff',
                   b'[' * 40 + b'0' + b']' * 40, b' ' * (a.MAX_PLAN + 1)]
        for raw in invalid:
            with self.subTest(raw=raw[:30]):
                b.plan = raw
                self.rejected(b)
                self.assertEqual(b.calls, [])

    def test_policy_false_claims_fixture_and_limits(self):
        mutations = []
        for field in ('redirects', 'retries', 'head', 'listing', 'auth', 'requester_payer', 'fallback'):
            mutations.append(('request_policy', field, True))
            mutations.append(('request_policy', field, 0))
        mutations += [('request_policy', 'method', 'HEAD'), ('request_policy', 'endpoint', 'http://127.0.0.1'),
                      ('claims', 'waveform_coverage_verified', True), ('claims', 'semantic_mapping_verified', 0),
                      ('limits', 'run_s', 901), ('limits', 'per_body_bytes', True)]
        for container, field, value in mutations:
            with self.subTest(container=container, field=field, value=value):
                f = Fixture()
                replacement = copy.deepcopy(a.POLICY if container == 'request_policy' else
                                             a.CLAIMS if container == 'claims' else a.LIMITS)
                replacement[field] = value
                f.final_overrides[container] = replacement
                self.rejected(f.bundle())
        f = Fixture()
        f.final_overrides['fixture'] = True
        self.rejected(f.bundle(), 'final_fixture_not_production')

    def test_recorded_clock_ranges_order_spacing_and_bool(self):
        overrides = [{'start': 99}, {'start': 760}, {'end': 99}, {'end': 122},
                     {'connected_at': None}, {'headers_at': None}, {'first_body_at': 100.2},
                     {'connected_at': True}, {'start': True}, {'end': 119.9}]
        for override in overrides:
            with self.subTest(override=override):
                f = Fixture()
                f.rows[0].update(override)
                if override == {'end': 119.9}:
                    f.final_elapsed = 10
                self.rejected(f.bundle())
        f = Fixture()
        f.rows[1].update(start=100.5, connected_at=100.625, headers_at=100.75, first_body_at=100.875, end=101)
        self.rejected(f.bundle(), 'request_spacing')

    def test_deadline_failures_remain_nonpassing(self):
        for mode in ('connection', 'first_body', 'request', 'transfer'):
            with self.subTest(mode=mode):
                f = Fixture()
                row = f.rows[3]
                if mode == 'connection':
                    row.update(connected_at=117, headers_at=117.1, first_body_at=117.2, end=117.3)
                elif mode == 'first_body':
                    row.update(first_body_at=127, end=127.5)
                elif mode == 'request':
                    row.update(end=227)
                else:
                    row.update(start=759, connected_at=759.1, headers_at=759.2, first_body_at=759.3, end=881)
                row['transport_pass'] = False
                f.final_elapsed = 890
                f.return_elapsed = 891
                result = f.bundle().audit()
                self.assertTrue(result['valid'], result)
                self.assertEqual(result['qualified_slot_count'], 3)

    def test_exact_and_unverified_partial_accounting(self):
        f = Fixture()
        f.body(0, b'invented partial', outcome='incomplete_body', passing=False)
        f.rows[0].update(consumption_exact=False, receipt_verified=False,
                         consumed_upper=a.LIMITS['per_body_bytes'], consumed=7)
        result = f.bundle().audit()
        self.assertTrue(result['valid'])
        self.assertEqual(result['qualified_slot_count'], 3)
        self.assertGreater(result['consumed_upper'], result['observed_body_bytes'])
        for override in ({'consumption_exact': True}, {'receipt_verified': True}, {'consumed_upper': 100},
                         {'consumed': a.LIMITS['per_body_bytes'] + 1}):
            with self.subTest(override=override):
                broken = copy.deepcopy(f)
                broken.rows[0].update(override)
                self.rejected(broken.bundle())

    def test_empty_and_exact_error_bodies_retained(self):
        for outcome in ('empty_body', 'declared_size_rejected', 'invalid_content_length', 'worker_error_ValueError'):
            with self.subTest(outcome=outcome):
                f = Fixture()
                f.body(0, b'', outcome=outcome, passing=False)
                result = f.bundle().audit()
                self.assertTrue(result['valid'], result)
                self.assertEqual(result['qualified_slot_count'], 3)

    def test_body_slot_count_hash_and_worker_confirmation(self):
        overrides = [{'worker_exit_confirmed': False}, {'request_index': True},
                     {'request_index': 8}, {'consumed': 1}, {'observed_bytes': -1},
                     {'consumed_upper': a.LIMITS['per_body_bytes'] + 1},
                     {'http_status': True}, {'declared': True}, {'outcome': 'unknown'},
                     {'transport_pass': False}, {'receipt_verified': False}]
        for override in overrides:
            with self.subTest(override=override):
                f = Fixture()
                f.rows[0].update(override)
                self.rejected(f.bundle())
        f = Fixture()
        f.rows[0]['body']['name'] = a.BODIES[1]
        self.rejected(f.bundle(), 'body_slot_binding')
        f = Fixture()
        f.rows[0]['body'] = None
        self.rejected(f.bundle(), 'request_missing_body')

    def test_totals_flags_initial_summary_and_final_disagreements(self):
        overrides = [{'attempts': 3}, {'attempts': True}, {'observed_body_bytes': 1},
                     {'consumed_upper': 1}, {'complete': False}, {'all_slots_transport_pass': False},
                     {'elapsed_s': -1}, {'elapsed_s': 22}, {'run_begin': 99}, {'plan_sha256': '0' * 64}]
        for override in overrides:
            with self.subTest(override=override):
                f = Fixture()
                f.final_overrides.update(override)
                self.rejected(f.bundle())
        for override in ({'complete': False}, {'all_slots_transport_pass': False}, {'begin': 99, 'returned_at': 120}):
            f = Fixture()
            f.summary_overrides.update(override)
            self.rejected(f.bundle())
        f = Fixture()
        f.initial_overrides['complete'] = True
        self.rejected(f.bundle())

    def test_exact_cap_known_framed_body_and_recorded_return_limit(self):
        f = Fixture()
        f.body(0, b'x' * a.LIMITS['per_body_bytes'])
        for i in range(1, 4):
            f.shared(i)
        f.return_elapsed = 900.0
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['observed_body_bytes'], a.LIMITS['per_body_bytes'])
        self.assertEqual(result['qualified_slot_count'], 4)

    def test_complete_declared_length_mismatch_is_not_framed_completion(self):
        for raw, outcome in ((b'invented retained body', 'body_complete'), (b'', 'empty_body')):
            with self.subTest(outcome=outcome):
                f = Fixture()
                f.body(0, raw, outcome=outcome, passing=bool(raw))
                f.rows[0]['declared'] = len(raw) + 1
                self.rejected(f.bundle(), 'complete_body_declared_mismatch')

    def test_unknown_length_exact_cap_is_conservatively_unsupported(self):
        f = Fixture()
        f.body(0, b'x' * a.LIMITS['per_body_bytes'])
        f.rows[0]['declared'] = None
        for i in range(1, 4):
            f.shared(i)
        b = f.bundle()
        self.rejected(b, 'complete_body_unknown_cap_framing')
        self.assertTrue(all(name not in a.BODIES for name, _ in b.calls))

    def test_unknown_length_below_cap_and_boundary_failure_remain_distinct(self):
        f = Fixture()
        f.rows[0]['declared'] = None
        self.assertTrue(f.bundle().audit()['valid'])
        f.body(0, b'x' * a.LIMITS['per_body_bytes'], outcome='body_cap_boundary', passing=False)
        f.rows[0]['declared'] = None
        result = f.bundle().audit()
        self.assertTrue(result['valid'])
        self.assertEqual(result['qualified_slot_count'], 3)

    def test_all_four_unverified_counts_charge_exact_aggregate_cap(self):
        f = Fixture()
        for row in f.rows:
            row.update(outcome='body_receipt_mismatch', transport_pass=False, consumed=None,
                       consumption_exact=False, receipt_verified=False,
                       consumed_upper=a.LIMITS['per_body_bytes'])
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['consumed_upper'], a.LIMITS['total_body_bytes'])
        self.assertEqual(result['qualified_slot_count'], 0)

    def test_no_file_exact_zero_error_and_missing_reader_member(self):
        f = Fixture()
        f.bodies.pop(a.BODIES[0])
        f.rows[0].update(body=None, observed_bytes=0, consumed=0, consumed_upper=0,
                         declared=None, outcome='worker_error_OSError', transport_pass=False)
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['qualified_slot_count'], 3)
        b = Fixture().bundle()
        b.members.pop(a.BODIES[0])
        self.rejected(b, 'member_reader_failure')

    def test_cutoff_prevents_later_new_attempt_but_preserves_prior_sharing(self):
        f = Fixture()
        f.unattempted(1)
        self.rejected(f.bundle(), 'attempt_after_unattempted_cutoff')
        f = Fixture()
        f.unattempted(1)
        f.shared(2)
        f.shared(3)
        result = f.bundle().audit()
        self.assertTrue(result['valid'], result)
        self.assertFalse(result['complete_accounting'])
        self.assertEqual(result['attempt_count'], 1)
        self.assertEqual(result['qualified_slot_count'], 0)

    def test_sequential_attempts_may_not_overlap(self):
        f = Fixture()
        f.rows[0]['end'] = 104.0
        self.rejected(f.bundle(), 'request_overlap')
        f.rows[0]['end'] = f.rows[1]['start']
        self.assertTrue(f.bundle().audit()['valid'])

    def test_journal_boolean_number_aliases_and_integer_field_floats(self):
        mutations = [('transport_pass', 1), ('consumption_exact', 1), ('receipt_verified', 1),
                     ('worker_exit_confirmed', 1), ('request_index', False), ('observed_bytes', 33.0)]
        for field, value in mutations:
            with self.subTest(field=field):
                b = Fixture().bundle()
                row = json.loads(b.members[a.JOURNALS[0]])
                if field == 'observed_bytes':
                    value = float(row[field])
                row[field] = value
                b.members[a.JOURNALS[0]] = encode(row)
                b.repin_manifest()
                self.rejected(b, 'journal_final_mismatch')

    def test_nested_journal_pin_type_and_numeric_clock_representation(self):
        for nested in (True, False):
            with self.subTest(nested=nested):
                b = Fixture().bundle()
                row = json.loads(b.members[a.JOURNALS[0]])
                if nested:
                    row['body']['bytes'] = float(row['body']['bytes'])
                else:
                    row['start'] = int(row['start'])
                b.members[a.JOURNALS[0]] = encode(row)
                b.repin_manifest()
                self.rejected(b, 'journal_final_mismatch')

    def test_journal_whitespace_and_key_order_do_not_change_agreement(self):
        b = Fixture().bundle()
        row = json.loads(b.members[a.JOURNALS[0]])
        row = dict(reversed(list(row.items())))
        b.members[a.JOURNALS[0]] = json.dumps(row, indent=2).encode()
        b.repin_manifest()
        self.assertTrue(b.audit()['valid'])


if __name__ == '__main__':
    unittest.main()

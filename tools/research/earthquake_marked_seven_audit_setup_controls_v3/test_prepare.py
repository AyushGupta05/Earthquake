"""Invented metadata only. NEVER invokes prepare() or systemd."""
import importlib.util
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).with_name('prepare.py')
s = importlib.util.spec_from_file_location('setup_only', SOURCE)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def reference(name):
    path = SOURCE.parent / 'reference' / (name + '.py')
    pins = json.loads((SOURCE.parent / 'REFERENCE_PINS.json').read_text())
    raw = path.read_bytes()
    assert pins[path.name] == dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    spec = importlib.util.spec_from_file_location('fixture_' + name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


hooks = reference('hooks_v3')
io = reference('secure_io')
old = reference('prepare_v2')
MONEY_FIELDS = ('ceiling_usd', 'reservation_usd', 'task_spend_upper_bound_usd',
                'estimated_balance_usd', 'uncertainty_reserve_usd',
                'other_reservations_usd', 'unreserved_lower_bound_usd')
WALL = m.utc('2026-10-13T16:00:00Z')


class Setup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def file(self, name, raw=b'invented', mode=0o400):
        p = self.root / name
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(raw); p.chmod(mode)
        return dict(path=str(p), pin=m.pin(raw), mode=mode)

    def credit(self):
        return dict(schema='eligible-AWS-main-credit-live-UI-proof-v1',
                    main_credit_status='Active', main_credit_expiry='2026-10-31',
                    eligible_services=m.SERVICES, account_shared=True,
                    estimated_amounts_delayed_24_hours=True,
                    settled_incremental_task_spend_unknown=True,
                    same_account_default_cli_credentials_refreshed=True,
                    credit_reserved_by_provider=False, authorized_credit_only_ceiling_usd=2000,
                    conservative_task_reservation_usd=335,
                    main_credit_estimated_remaining_usd=3800.25,
                    total_estimated_remaining_usd=4000.25, screen='INVENTED fixture; no actual account',
                    checked_utc='2026-10-13T15:00:00Z')

    def request(self):
        return dict(task_spend_upper_bound_usd='100.00', uncertainty_reserve_usd='1500.00',
                    other_reservations_usd='0.00', task_bound_until_utc=m.VALID_UNTIL,
                    credit_proof=self.file('credit.json', m.canonical(self.credit())))

    def test_money_exact_and_nonfinite(self):
        self.assertEqual(str(m.amount('1.23')), '1.23')
        for x in ('1.234', 'NaN', '-1', True):
            with self.assertRaises(ValueError): m.amount(x)

    def test_funding_binds_raw_and_fixed_validity(self):
        q = m.funding(self.request(), self.credit(), m.utc('2026-10-13T16:00:00Z'))
        self.assertEqual(q['unreserved_lower_bound_usd'], 2300.25)
        self.assertEqual(q['valid_until_utc'], '2026-10-14T04:00:00Z')
        self.assertEqual(q['ceiling_usd'], 2000)
        self.assertEqual(q['reservation_usd'], 335)

    def test_funding_rejects_delayed_semantics_mutation(self):
        c = self.credit(); c['estimated_amounts_delayed_24_hours'] = False
        with self.assertRaises(ValueError): m.funding(self.request(), c, m.utc('2026-10-13T16:00:00Z'))

    def test_funding_insufficient_or_expired(self):
        r = self.request(); r['other_reservations_usd'] = '1000.00'
        with self.assertRaises(ValueError): m.funding(r, self.credit(), m.utc('2026-10-13T16:00:00Z'))
        r['other_reservations_usd'] = '0.00'
        with self.assertRaises(ValueError): m.funding(r, self.credit(), m.utc(m.VALID_UNTIL))

    def test_cost_bound_must_cover_whole_validity(self):
        r = self.request(); r['task_bound_until_utc'] = '2026-10-13T17:00:00Z'
        with self.assertRaises(ValueError): m.funding(r, self.credit(), m.utc('2026-10-13T16:00:00Z'))

    def test_pinned_regular_read(self):
        s = self.file('regular'); self.assertEqual(m.read(s), b'invented')
        s['pin']['sha256'] = '0' * 64
        with self.assertRaises(ValueError): m.read(s)

    def test_symlink_and_hardlink_rejected(self):
        s = self.file('regular'); p = self.root / 'link'; p.symlink_to(s['path'])
        with self.assertRaises((ValueError, OSError)): m.read(dict(s, path=str(p)))
        p.unlink(); os.link(s['path'], p)
        with self.assertRaises(ValueError): m.read(s)

    def test_ancestor_symlink_rejected(self):
        (self.root / 'real').mkdir(); (self.root / 'alias').symlink_to(self.root / 'real')
        with self.assertRaises((ValueError, OSError)): m.directory(str(self.root / 'alias'))

    def test_new_directory_exclusive_and_metadata_durable(self):
        base = str(self.root / 'fresh'); fd = m.make_new(base)
        try:
            spec = m.put(fd, base, 'a.json', {'x': 1})
            self.assertEqual(m.obj(spec), {'x': 1})
            self.assertEqual(Path(spec['path']).stat().st_mode & 0o777, 0o400)
            with self.assertRaises(FileExistsError): m.put(fd, base, 'a.json', {'x': 2})
            self.assertEqual(m.obj(spec), {'x': 1})
        finally: os.close(fd)
        with self.assertRaises(FileExistsError): m.make_new(base)

    def test_control_cap_before_write(self):
        base = str(self.root / 'fresh'); fd = m.make_new(base)
        try:
            with self.assertRaises(ValueError): m.put(fd, base, 'big', b'x' * (2 * 1024 * 1024 + 1), raw=True)
            self.assertEqual(os.listdir(fd), [])
        finally: os.close(fd)

    def timer(self, interval='2h 3min 20s', active='active', argv='/usr/bin/bash /owned/whole-stop.sh'):
        return ('ActiveState=' + active + '\nUnit=owned.service\nAccuracyUSec=1s\n'
                'TimersMonotonic={ OnActiveUSec=' + interval + '; next_elapse=whatever; }\n'
                'ActiveEnterTimestampMonotonic=100000000\n'), ('ActiveState=inactive\nExecStart={ path=/usr/bin/bash ; argv[]=' + argv + '; }\n')

    def test_timer_exact_and_activation_clock(self):
        t, s = self.timer()
        self.assertEqual(m.check_timer(t, s, 'owned.service', '/owned/whole-stop.sh', 99., 101.), 100.)
        with self.assertRaises(ValueError): m.check_timer(t, s, 'owned.service', '/owned/whole-stop.sh', 101., 102.)

    def test_timer_wrong_interval_and_exec_rejected(self):
        for t, s in (self.timer(interval='7401s'), self.timer(active='inactive'), self.timer(argv='/bin/true')):
            with self.assertRaises(ValueError): m.check_timer(t, s, 'owned.service', '/owned/whole-stop.sh', 99., 101.)

    def test_duplicate_property_rejected(self):
        with self.assertRaises(ValueError): m.properties('ActiveState=active\nActiveState=inactive\n')

    def test_exact_seven_stop_lines(self):
        units = ['eew-marked-' + m.AUDIT_ID + '-%02d.service' % i for i in range(7)]
        body = m.stop_body(units)
        self.assertEqual(body.count(b'systemctl --user stop '), 7)
        self.assertNotIn(b'set -e', body)
        for unit in units: self.assertIn(('systemctl --user stop ' + unit + '\n').encode(), body)
        with self.assertRaises(ValueError): m.stop_body(units[:-1])

    def source_profile(self):
        profile = {}
        for role in sorted(m.ROLES):
            p = self.file(role + '/MANIFEST.json', b'{}')
            profile[role] = dict(directory=str(self.root / role), files={'MANIFEST.json': p['pin']}, manifest=p, upload_manifest=None)
        return profile

    def test_closed_positive_source_then_extra_file_rejected(self):
        p = self.source_profile(); m.closed_sources(p)
        self.file('auditor/unbound.py', b'print(1)')
        with self.assertRaises(ValueError): m.closed_sources(p)

    def test_source_manifest_cannot_point_elsewhere(self):
        p = self.source_profile(); p['auditor']['manifest'] = p['wrapper']['manifest']
        with self.assertRaises(ValueError): m.closed_sources(p)

    def test_loading_never_installs_or_dispatches(self):
        with patch('subprocess.run', side_effect=AssertionError('must never execute')):
            s2 = importlib.util.spec_from_file_location('setup_again', SOURCE)
            n = importlib.util.module_from_spec(s2); s2.loader.exec_module(n)
            self.assertTrue(callable(n.prepare))

    def consume(self, funding):
        self.consumed = getattr(self, 'consumed', 0) + 1
        spec = self.file('funding_%02d.json' % self.consumed, m.canonical(funding))
        with patch('subprocess.run', side_effect=AssertionError('no operational calls')):
            return hooks.finance(io, spec, WALL)

    def test_exact_consumer_raw_and_funding_keys(self):
        self.assertEqual(set(self.credit()), hooks.RAW_CREDIT_KEYS)
        q = m.funding(self.request(), self.credit(), WALL)
        self.assertEqual(set(q), hooks.FKEYS)

    def test_real_consumer_roundtrip_all_seven_amounts(self):
        r = self.request(); r['task_spend_upper_bound_usd'] = '250.00'
        q = m.funding(r, self.credit(), WALL)
        saved = self.consume(q)
        self.assertEqual(saved, q)
        expected = (2000, 335, 250, 3800.25, 1500, 0, 2300.25)
        for key, value in zip(MONEY_FIELDS, expected):
            self.assertIn(type(saved[key]), (int, float))
            self.assertTrue(math.isfinite(saved[key]))
            self.assertEqual(hooks.money(saved[key]), m.amount(value))
        self.assertEqual(saved['raw_proof'], r['credit_proof'])

    def test_frozen_v2_reproduces_actual_consumer_money_rejection(self):
        q = old.funding(self.request(), self.credit(), WALL)
        self.assertTrue(all(type(q[k]) is str for k in MONEY_FIELDS))
        with self.assertRaisesRegex(ValueError, '^money$'): self.consume(q)

    def test_each_string_amount_rejected_by_unchanged_consumer(self):
        q = m.funding(self.request(), self.credit(), WALL)
        for key in MONEY_FIELDS:
            with self.subTest(key=key):
                bad = dict(q); bad[key] = str(bad[key])
                with self.assertRaisesRegex(ValueError, '^money$'): self.consume(bad)

    def test_fractional_cents_preserved_without_binary_subtraction(self):
        raw = self.credit(); raw['main_credit_estimated_remaining_usd'] = 3800.23
        r = self.request(); r['credit_proof'] = self.file('raw_fraction.json', m.canonical(raw))
        r['other_reservations_usd'] = '0.10'
        q = self.consume(m.funding(r, raw, WALL))
        self.assertEqual(hooks.money(q['unreserved_lower_bound_usd']), m.amount('2300.13'))
        self.assertEqual(hooks.money(q['estimated_balance_usd']), m.amount(raw['main_credit_estimated_remaining_usd']))

    def test_consumer_raw_balance_binding_and_lower_bound(self):
        q = m.funding(self.request(), self.credit(), WALL)
        for key, reason in [('estimated_balance_usd', 'raw_amount_binding'),
                            ('unreserved_lower_bound_usd', 'remaining_credit_ceiling')]:
            with self.subTest(key=key):
                bad = dict(q); bad[key] = m.numeric_amount(m.amount(q[key]) + m.amount('.01'))
                with self.assertRaisesRegex(ValueError, reason): self.consume(bad)

    def test_missing_screen_or_extra_raw_field_still_rejected(self):
        original_request = self.request()
        for change in ('missing', 'extra'):
            with self.subTest(change=change):
                raw = self.credit()
                if change == 'missing': del raw['screen']
                else: raw['unapproved'] = True
                r = dict(original_request); r['credit_proof'] = self.file('malformed_' + change + '.json', m.canonical(raw))
                q = m.funding(r, raw, WALL)
                with self.assertRaisesRegex(ValueError, 'credit_raw_schema'): self.consume(q)

    def test_raw_file_hash_is_checked_by_actual_secure_io(self):
        r = self.request(); q = m.funding(r, self.credit(), WALL)
        path = Path(r['credit_proof']['path']); path.chmod(0o600)
        path.write_bytes(m.canonical(dict(self.credit(), screen='changed after pin'))); path.chmod(0o400)
        with self.assertRaises(ValueError): self.consume(q)

    def test_numeric_conversion_rejects_overflow_and_loss(self):
        for value in ('NaN', 'Infinity', '1e10000', '9007199254740993.01', '1.234'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.numeric_amount(m.Decimal(value))

    def test_v3_namespace_and_only_intended_production_changes(self):
        self.assertEqual(m.AUDIT_ID, 'shared-noise-audit-v3-20261013')
        self.assertEqual(m.BASE, '/home/ec2-user/eew-marked-seven-audit-v3-20261013')
        self.assertNotEqual(m.AUDIT_ID, old.AUDIT_ID); self.assertNotEqual(m.BASE, old.BASE)
        def unchanged(path):
            tree = ast.parse(path.read_text())
            return [ast.dump(n) for n in tree.body
                    if not (isinstance(n, ast.FunctionDef) and n.name in ('funding', 'numeric_amount'))
                    and not (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('AUDIT_ID', 'BASE') for t in n.targets))]
        self.assertEqual(unchanged(SOURCE), unchanged(SOURCE.parent / 'reference' / 'prepare_v2.py'))


if __name__ == '__main__': unittest.main()

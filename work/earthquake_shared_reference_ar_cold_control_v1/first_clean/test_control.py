import copy
import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import control as c
import entry
import secure_io as io
import systemd_adapter as systemd


def answer(raw=b'', code=0, complete=True):
    return dict(code=code, timeout=False, stdout=raw, stderr=b'', streams_complete=complete,
                stream_custody={}, exception=None)


class Harness:
    def __init__(self, root):
        self.root = Path(root); self.now = 100.; self.launched = []; self.commands = []
        self.timed = False; self.timer_active = False; self.fail_mode = None
        self.truncated = False; self.slow = False; self.bad_report = False; self.unknown_group = False
        self.owned = set(); self.files = {}; self.absence_code = 0
        def put(name, value):
            raw = c.canonical(value); p = self.root/name; p.write_bytes(raw); p.chmod(0o400)
            return dict(path=str(p), pin=c.pin(raw), mode=0o400)
        self.put = put
        gate = dict(schema='root-L-readiness-fresh-funding-resource-gate-v1', no_actual_L_fit_authority=True,
                    checked_utc='1970-01-01T00:00:00+00:00', bound_until_utc='2100-01-01T00:00:00+00:00', publication_commit='invented')
        config = dict(runtime=dict(python='/invented/python'))
        self.req = dict(schema='root-L-cold-control-request-v1', id='fixture-test', namespace=str(self.root/'new'),
                        gate=put('gate', gate), config=put('config', config), caller=put('caller', {}),
                        bash=put('bash', {}), commands={k:put(k, {}) for k in ('systemctl', 'systemd_run')})
        self.req['preflight'] = put('preflight', dict(status='complete', config_pin=self.req['config']['pin'], publication_ancestor='invented'))
        self.command_files = {self.req['bash']['path']: '/usr/bin/bash', self.req['commands']['systemctl']['path']: '/usr/bin/systemctl'}
        self.read_specs = {}
        for spec in (self.req['bash'], self.req['commands']['systemctl']):
            original = copy.deepcopy(spec); spec['path'] = self.command_files[spec['path']]; self.read_specs[spec['path']] = original
        self.io = mock.Mock(wraps=io)
        self.io.read_file.side_effect = lambda spec, *args: io.read_file(self.read_specs.get(spec['path'], spec), *args)

    def clock(self): return self.now
    def own(self, unit): self.owned.add(unit)
    def available(self, unit):
        if unit in self.launched: raise ValueError('existing_unit')

    def process(self, args, timeout):
        self.commands.append(args); self.now += .01
        if '--on-active=1000s' in args:
            self.timed = True; self.timer_active = True; self.start = self.now
            self.stop_path = args[-1]; return answer()
        if 'stop' in args:
            if any(x.endswith('.timer') for x in args): self.timer_active = False
            return answer()
        unit = args[args.index('show')+1]
        fields = args[-1].split('=',1)[1].split(',')
        if 'TimersMonotonic' in fields:
            values = dict(ActiveState='active', Unit=unit[:-6]+'.service', AccuracyUSec='1s',
                          TimersMonotonic='{ OnActiveUSec=16min 40s ; next_elapse=unknown }',
                          ActiveEnterTimestampMonotonic=str(int(self.start*1e6)))
        elif 'ExecStart' in fields:
            values = dict(ActiveState='inactive', ExecStart='{ path=/usr/bin/bash ; argv[]=/usr/bin/bash '+self.stop_path+' ; ignore_errors=no ; }')
        else:
            values = dict(LoadState='not-found', ActiveState='inactive')
            if 'ControlGroup' in fields:
                values['ControlGroup'] = '/not-empty' if self.unknown_group and unit in self.launched else ''
        return answer(('\n'.join(k+'='+v for k,v in values.items())+'\n').encode(),
                      code=self.absence_code if values.get('LoadState') == 'not-found' else 0)

    def run(self, args, timeout, unit):
        self.launched.append(unit); mode = args[-1]
        self.now += 121 if self.slow else 1
        if mode == self.fail_mode: return answer(b'', code=2)
        report = dict(schema='L-cold-source-readiness-v1', mode=mode, scienceactual=0, status='complete', seconds=.5)
        if mode == 'fixtures': report['tests'] = dict(run=19, failures=0, errors=0, skipped=0)
        else: report['synthetic'] = dict(status='complete', scienceactual=0, mode=mode, synthetic_steps=3 if mode=='producer' else 0)
        if self.bad_report: report['status'] = 'incomplete'
        spec = self.put('new/'+mode+'_report.private.json', report)
        return answer(c.canonical(dict(report_path=spec['path'], report_pin=spec['pin'])), complete=not self.truncated)

    def execute(self):
        return c.run(self.req, io=self.io, sd=self, process=self.process, seconds=systemd.seconds, clock=self.clock, wall=lambda:1000.)


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.h = Harness(str(Path(self.tmp.name).resolve()))

    def test_three_once_order_timer_and_caps(self):
        result = self.h.execute(); self.assertEqual(result['status'], 'complete')
        self.assertEqual([x[-10:-8] for x in self.h.launched], ['00','01','02'])
        self.assertFalse(self.h.timer_active)
        self.assertEqual(len(list((self.h.root/'new').glob('*_claim.json'))), 3)
        self.assertEqual(json.loads((self.h.root/'new/control.private.json').read_bytes())['limits'], c.LIMITS)

    def test_failure_terminal_no_retry_or_next_stage(self):
        self.h.fail_mode = 'independent'; result = self.h.execute()
        self.assertEqual(result['status'], 'incomplete'); self.assertEqual(len(self.h.launched), 2)
        self.assertTrue((self.h.root/'new/independent_manager.json').exists())
        self.assertFalse(self.h.timer_active)

    def test_truncated_stream_is_terminal(self):
        self.h.truncated = True; self.assertEqual(self.h.execute()['status'], 'incomplete')
        self.assertEqual(len(self.h.launched), 1)

    def test_late_child_source_return_is_terminal(self):
        self.h.slow = True; self.assertEqual(self.h.execute()['status'], 'incomplete')
        self.assertEqual(len(self.h.launched), 1)

    def test_child_incomplete_rejected(self):
        self.h.bad_report = True; self.assertEqual(self.h.execute()['status'], 'incomplete')

    def test_nonempty_group_never_closes(self):
        self.h.unknown_group = True; result = self.h.execute()
        self.assertEqual(result['status'], 'incomplete'); self.assertEqual(len(self.h.launched), 1)
        self.assertTrue(self.h.timer_active)
        self.assertTrue(json.loads((self.h.root/'new/final_report.json').read_bytes())['timer_retained_for_unverified_cleanup'])

    def test_systemctl_absence_code_one(self):
        self.h.absence_code = 1
        self.assertEqual(self.h.execute()['status'], 'complete')

    def test_systemctl_absence_code_four(self):
        self.h.absence_code = 4
        self.assertEqual(self.h.execute()['status'], 'complete')

    def test_nonzero_active_cannot_claim_absence(self):
        with self.assertRaisesRegex(ValueError, 'command_return'):
            c.props(answer(b'LoadState=loaded\nActiveState=active\nControlGroup=/x\n', code=4), allow_absence=True)

    def test_second_execution_cannot_overwrite(self):
        self.h.execute()
        with self.assertRaises((ValueError, FileExistsError)): self.h.execute()
        self.assertEqual(len(self.h.launched), 3)

    def test_expired_gate_cannot_create_namespace(self):
        with self.assertRaisesRegex(ValueError, 'gate_expired'):
            c.run(self.h.req, io=io, sd=self.h, process=self.h.process, seconds=systemd.seconds,
                  clock=self.h.clock, wall=lambda: 9999999999.)
        self.assertFalse((self.h.root/'new').exists())

    def test_gate_tamper_rejected(self):
        self.h.req['gate']['pin']['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.h.execute()

    def test_preflight_config_mismatch_no_timer(self):
        self.h.req['preflight'] = self.h.put('bad_preflight', dict(status='complete', config_pin={}, publication_ancestor='invented'))
        with self.assertRaisesRegex(ValueError, 'preflight'): self.h.execute()
        self.assertFalse(self.h.timed)

    def test_timer_wrong_interval_rejected(self):
        timer = answer(b'ActiveState=active\nUnit=x.service\nAccuracyUSec=1s\nTimersMonotonic={ OnActiveUSec=1001s ; }\nActiveEnterTimestampMonotonic=100000000\n')
        service = answer(b'ActiveState=inactive\nExecStart={ argv[]=/usr/bin/bash /fixed ; }\n')
        with self.assertRaisesRegex(ValueError, 'timer_interval'):
            c.timer_start(timer, service, 'x.service', '/fixed', 99, 101, systemd.seconds)

    def test_stop_script_exact_three_names(self):
        self.h.execute(); body = (self.h.root/'new/stop.sh').read_text()
        self.assertEqual(body.count('systemctl --user stop'), 3)
        self.assertNotIn('set -e', body)
        self.assertEqual(body.count('/usr/bin/systemctl --user stop'), 3)

    def test_mismatched_stop_executable_rejected_before_timer(self):
        self.h.req['bash']['path'] = '/different/bash'
        with self.assertRaisesRegex(ValueError, 'stop_executable_paths'): self.h.execute()
        self.assertFalse(self.h.timed)

    def test_source_caps_and_hidden_cuda_command(self):
        args = c.argv(self.h.req, dict(runtime=dict(python='/fixed')), dict(path='/c', pin=c.pin(b'x')), 'producer', 'eew-marked-fixture-test-02.service', 360)
        self.assertIn('MemoryMax=2147483648', args); self.assertIn('CPUQuota=100%', args)
        self.assertIn('--setenv=CUDA_VISIBLE_DEVICES=', args); self.assertIn('RuntimeMaxSec=360', args)
        self.assertEqual(args[-1], 'producer')

    def test_full_stdout_failure_retained(self):
        self.h.truncated = True; self.h.execute()
        result = json.loads((self.h.root/'new/fixtures_manager.json').read_bytes())
        self.assertEqual(c.pin(bytes.fromhex(result['stdout']['hex'])), result['stdout']['pin'])

    def test_finalization_lateness_no_passing_return(self):
        original = c.Journal.write
        def late(journal, name, *args, **kwargs):
            spec = original(journal, name, *args, **kwargs)
            if name == 'final_report.json': self.h.now += 1001
            return spec
        with mock.patch.object(c.Journal, 'write', late): result = self.h.execute()
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue((self.h.root/'new/late_after_finalization.json').exists())

    def test_retention_failure_still_requests_cleanup(self):
        original = c.Journal.write
        def fail(journal, name, *args, **kwargs):
            if name == 'outcome_before_cleanup.json': raise OSError('invented disk error')
            return original(journal, name, *args, **kwargs)
        with mock.patch.object(c.Journal, 'write', fail): result = self.h.execute()
        self.assertEqual(result['status'], 'incomplete'); self.assertFalse(self.h.timer_active)

    def test_journal_no_symlink_or_overwrite(self):
        j = c.Journal(str(self.h.root/'j'), io); self.addCleanup(j.close)
        p = j.write('x.json', {'a':1})
        with self.assertRaises(FileExistsError): j.write('x.json', {'a':2})
        self.assertEqual(json.loads(io.read_file(p)), {'a':1})
        os.symlink(self.h.root/'gate', self.h.root/'j/link')
        with self.assertRaisesRegex(ValueError, 'journal_member'): j.write('y.json', {})

    def test_journal_member_cap(self):
        j = c.Journal(str(self.h.root/'j'), io); self.addCleanup(j.close)
        with self.assertRaisesRegex(ValueError, 'member_cap'): j.write('x', b'x'*(2*1024*1024+1), raw=True)

    def test_entry_positive_read_rejects_mode_hash_symlink(self):
        spec = self.h.req['gate']; self.assertEqual(entry.read(spec), io.read_file(spec))
        bad = copy.deepcopy(spec); bad['pin']['sha256']='0'*64
        with self.assertRaises(AssertionError): entry.read(bad)
        alias = self.h.root/'alias'; alias.symlink_to(spec['path']); bad = dict(spec, path=str(alias))
        with self.assertRaises(OSError): entry.read(bad)
        os.chmod(spec['path'],0o600)
        with self.assertRaises(AssertionError): entry.read(spec)


if __name__ == '__main__': unittest.main()

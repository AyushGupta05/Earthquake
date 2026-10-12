import copy
import unittest
import numpy as np
from auditor import audit
from fixtures import plan_and_bodies, reader, input_pins
from invented import int_record
from replay import replay, joint, component
from plan_validation import validate
from strict import Reject, canonical, sha


class FullReplayTests(unittest.TestCase):
    def test_fixed_denominator_five_literals_and_shared_rows(self):
        plan, bodies = plan_and_bodies()
        result = replay(plan, reader(bodies))
        self.assertEqual((result['disposition'], len(result['rows']), sum(len(r['cells']) for r in result['rows'])), ('complete', 65, 195))
        self.assertEqual(result['batches'][0]['observed_samples'], 400)
        self.assertEqual(result['records'][0]['routed_rows'], [0, 1, 2, 3])
        for horizon in result['aggregate']['horizons']:
            self.assertEqual(horizon['complete_joint'], 4)
            self.assertEqual(horizon['complete_components'], 20)
        self.assertEqual(result['rows'][0]['cells'][2]['components'][0]['count'], 80)
        self.assertEqual(result['rows'][0]['cells'][0]['components'][0]['count'], 40)
        self.assertTrue(all(v is False for v in result['claims'].values()))

    def test_all_positive_unknown_family_never_inferred(self):
        plan, bodies = plan_and_bodies(tuple(range(17)))
        result = replay(plan, reader(bodies))
        for h in result['aggregate']['horizons']:
            self.assertEqual(h['complete_joint'], 61)
            self.assertEqual(h['metadata_unknown_complete_components'], 20)
        for row in result['rows'][61:]:
            self.assertIsNone(row['family'])
            self.assertEqual(row['cells'][0]['joint']['reason'], 'metadata_unknown')

    def test_unexpected_identity_veto_retains_reached_records(self):
        raw = int_record() + int_record(channel='BHE', sequence=2)
        plan, bodies = plan_and_bodies(raw=raw)
        result = replay(plan, reader(bodies))
        self.assertEqual(result['disposition'], 'complete')
        self.assertEqual(result['batches'][0]['reason'], 'unexpected_identity')
        self.assertEqual(result['records'][-1]['routed_rows'], [])
        self.assertEqual(result['batches'][0]['observed_samples'], 80)
        self.assertEqual(result['aggregate']['horizons'][0]['complete_joint'], 0)
        self.assertTrue(all(c['status'] == 'unknown' for c in result['rows'][0]['cells'][0]['components']))

    def test_timing_unknown_and_zero_skip(self):
        raw = bytearray(int_record()); raw[36] = 0x10
        plan, bodies = plan_and_bodies(raw=bytes(raw))
        result = replay(plan, reader(bodies))
        self.assertEqual(result['batches'][0]['reason'], 'timing_unknown')
        self.assertEqual(result['batches'][0]['record_count'], 1)
        plan, bodies = plan_and_bodies(raw=int_record(count=0))
        def forbidden(*args): raise AssertionError('zero callback')
        result = replay(plan, reader(bodies), forbidden)
        self.assertEqual(result['disposition'], 'complete')
        self.assertEqual(result['records'][0]['dtype'], 'empty')
        self.assertIsNone(result['records'][0]['decoded_start_ns'])
        self.assertEqual(result['records'][0]['samples_sha256'], sha(b'empty\0'))

    def test_declared_decode_failure_vs_unexpected_runtime(self):
        plan, bodies = plan_and_bodies()
        def declared(*args): raise ValueError('invented')
        result = replay(plan, reader(bodies), declared)
        self.assertEqual((result['disposition'], result['batches'][0]['reason']), ('complete', 'decode_unknown'))
        def crashed(*args): raise RuntimeError('invented')
        result = replay(plan, reader(bodies), crashed)
        self.assertEqual((result['disposition'], result['reason']), ('incomplete', 'runtime_failure'))
        self.assertEqual(result['aggregate']['horizons'][0]['complete_joint'], 0)

    def test_later_local_nan_and_rate_do_not_veto_first_second(self):
        raw = int_record(channel='HHE') + int_record(channel='HHE', start_second=4, rate=20, sequence=2)
        plan, bodies = plan_and_bodies(raw=raw)
        def invented_decode(raw, d, start, rate):
            values = np.arange(d['npts'], dtype=np.float32)
            if d['ordinal'] == 1: values[1] = np.nan
            return values
        result = replay(plan, reader(bodies), invented_decode)
        cells = result['rows'][0]['cells']
        self.assertEqual(cells[0]['components'][0]['status'], 'complete')
        self.assertEqual(cells[1]['components'][0]['reason'], 'nonfinite')
        self.assertFalse(result['records'][1]['finite'])

    def test_body_custody_and_wall_failure_zero_all_promotions(self):
        plan, bodies = plan_and_bodies((0, 1))
        result = replay(plan, lambda ordinal, size: bodies[ordinal] if ordinal == 0 else b'changed')
        self.assertEqual(result['disposition'], 'incomplete')
        self.assertEqual(result['batches'][0]['status'], 'decoded')
        self.assertEqual(result['aggregate']['horizons'][0]['complete_components'], 0)
        result = replay(plan, reader(bodies), wall_seconds=-1)
        self.assertEqual((result['disposition'], result['reason']), ('incomplete', 'wall_timeout'))

    def test_independent_audit_exact_comparison_and_types(self):
        plan, bodies = plan_and_bodies()
        result = replay(plan, reader(bodies))
        a, b, pins = input_pins(plan, result)
        calls = []
        def bounded(name, bound):
            calls.append((name, bound)); value = bodies[int(name[:3])]
            self.assertEqual(bound, len(value) + 1); return value
        verdict = audit(a, b, bounded, pins)
        self.assertTrue(verdict['audit_pass'])
        self.assertEqual(calls, [('000.body.private', len(bodies[0]) + 1)])
        result['rows'][0]['cells'][0]['pick_before_cutoff'] = 1
        a, b, pins = input_pins(plan, result)
        self.assertFalse(audit(a, b, bounded, pins)['audit_pass'])

    def test_invalid_input_before_callbacks(self):
        plan, bodies = plan_and_bodies()
        invalids = []
        for mutation in (lambda p: p['rows'][0].update(ordinal=False), lambda p: p['rows'].reverse(),
                         lambda p: p['rows'][0].update(partition='TEST'), lambda p: p['batches'][0].update(rows=[0, 1, 2, True]),
                         lambda p: p['rows'][61].update(family='ENZ'), lambda p: p['rows'][0]['nominal_rates'].update(HHE=[20, 2]),
                         lambda p: p.update(extra=1)):
            value = copy.deepcopy(plan); mutation(value); invalids.append(value)
        for value in invalids:
            with self.assertRaises(Reject): replay(value, lambda *args: self.fail('reader'))
        result = replay(plan, reader(bodies)); a, b, pins = input_pins(plan, result)
        result['claims']['novelty_verified'] = 0
        a, b, pins = input_pins(plan, result)
        with self.assertRaises(Reject): audit(a, b, lambda *args: self.fail('reader'), pins)


if __name__ == '__main__': unittest.main()

import copy
import unittest
from unittest.mock import patch
from auditor import audit
from fixtures import plan_and_bodies, reader, input_pins
from replay import replay
from strict import Reject


class BoundTests(unittest.TestCase):
    def test_output_cap_rebuilds_every_cell_unknown(self):
        plan, bodies = plan_and_bodies((0, 1))
        # Lower invented admission budget triggers the real evidence-cap lane.
        with patch('replay.MAX_PRIVATE', 4_195_000):
            value = replay(plan, reader(bodies))
        self.assertEqual((value['disposition'], value['reason']), ('incomplete', 'output_cap'))
        self.assertEqual(len(value['rows']), 65)
        self.assertTrue(all(h['complete_components'] == h['complete_joint'] == 0 for h in value['aggregate']['horizons']))

    def test_structural_unknown_does_not_remove_rows(self):
        plan, bodies = plan_and_bodies(raw=b'invented unsupported record')
        value = replay(plan, reader(bodies))
        self.assertEqual(value['batches'][0]['reason'], 'structural_unknown')
        self.assertEqual(value['disposition'], 'complete')
        self.assertEqual((value['aggregate']['rows'], value['aggregate']['cells']), (65, 195))

    def test_pin_duplicate_and_noncomplete_before_reader(self):
        plan, bodies = plan_and_bodies()
        value = replay(plan, reader(bodies)); a, b, pins = input_pins(plan, value)
        changed = copy.deepcopy(pins); changed['plan']['sha256'] = '0' * 64
        with self.assertRaises(Reject): audit(a, b, lambda *args: self.fail('reader'), changed)
        # A correctly bound but duplicate-key plan still fails strict JSON.
        malformed = a[:-1] + b',"study":"duplicate"}'
        from strict import sha
        changed = copy.deepcopy(pins); changed['plan'] = {'bytes': len(malformed), 'sha256': sha(malformed)}
        with self.assertRaises(Reject): audit(malformed, b, lambda *args: self.fail('reader'), changed)
        value['disposition'] = 'incomplete'; a, b, pins = input_pins(plan, value)
        with self.assertRaises(Reject): audit(a, b, lambda *args: self.fail('reader'), pins)

    def test_cutoff_pick_is_strict_and_nonpositive_never_read(self):
        plan, bodies = plan_and_bodies(())
        plan['rows'][0]['pick_ns'] = 4_000_000_000
        value = replay(plan, lambda *args: self.fail('reader'))
        self.assertIs(value['rows'][0]['cells'][0]['pick_before_cutoff'], False)
        self.assertIs(value['rows'][0]['cells'][1]['pick_before_cutoff'], True)
        self.assertEqual(value['aggregate']['batch_statuses']['nonpositive'], 17)

    def test_unknown_component_null_default_and_final_body_single_row(self):
        plan, bodies = plan_and_bodies((16,))
        value = replay(plan, reader(bodies))
        self.assertEqual(value['records'][0]['routed_rows'], [64])
        c = value['rows'][0]['cells'][0]['components'][0]
        self.assertEqual(c['pieces'], []); self.assertIsNone(c['view_sha256']); self.assertIsNone(c['flat'])

    def test_producer_top_level_identity_rejected_before_reader(self):
        plan, bodies = plan_and_bodies()
        value = replay(plan, reader(bodies))
        for field, replacement in (('schema', None), ('schema', 'geonet-POST-prefix-qualification-v1'), ('study', 'old-study'), ('reason', {}),
                                   ('rows', []), ('batches', []), ('records', {}), ('aggregate', [])):
            changed = copy.deepcopy(value); changed[field] = replacement
            a, b, pins = input_pins(plan, changed)
            with self.assertRaises(Reject): audit(a, b, lambda *args: self.fail('reader'), pins)


if __name__ == '__main__': unittest.main()

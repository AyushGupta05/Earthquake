"""Invented-only adapter tests; no provider payload, requests or actual metadata."""
import copy
from fractions import Fraction
import hashlib
import struct
import sys
import unittest
from unittest.mock import patch

import adapter
import producer

START = 1704067200000000000


def record(channel, index, values):
    raw = bytearray(256)
    raw[:20] = b'000001D ABC    ' + channel.encode() + b'NZ'
    # Eight native samples per second, four-second fragments.
    struct.pack_into('>HHBBBBHHhhBBBBiHH', raw, 20, 2024, 1, 0, 0, index * 4,
                     0, 0, len(values), 8, 1, 0, 0, 0, 1, 0, 56, 48)
    struct.pack_into('>HHBBBB', raw, 48, 1000, 0, 3, 1, 8, 0)
    struct.pack_into('>' + 'i' * len(values), raw, 56, *values)
    return bytes(raw)


def decode(raw, descriptor):
    start, rate, _ = producer.header_grid(descriptor)
    values = list(struct.unpack_from('>' + 'i' * descriptor['npts'], raw, descriptor['data_offset']))
    return {'start_ns': start, 'rate': float(rate), 'dtype': 'i4', 'values': values}


def fixture():
    body = b''.join(record('HH' + s, i, [0] * 24 + [20] * 8 if i == 0 else [20, 20, 0, 0] * 8)
                    for s in 'EN12Z' for i in (0, 1))
    rows = []
    for i in range(65):
        family = 'ENZ' if i < 47 else '12Z' if i < 61 else None
        suffixes = 'ENZ' if family == 'ENZ' else '12Z' if family == '12Z' else ''
        rows.append({'ordinal': i, 'partition': 'TRAIN' if i < 41 else 'DEV', 'batch': i // 4,
                     'network': 'NZ', 'station': 'ABC', 'location': '', 'prefix': 'HH',
                     't0_ns': START + 3 * 10**9, 'pick_ns': START + 3 * 10**9,
                     'family': family, 'nominal_rates': {'HH' + s: [8, 1] for s in suffixes}})
    bodies = {i: body for i in range(17)}
    batches = [{'ordinal': i, 'rows': list(range(i * 4, min(i * 4 + 4, 65))),
                'transport': 'http200', 'body_bytes': len(body),
                'body_sha256': hashlib.sha256(body).hexdigest()} for i in range(17)]
    plan = {'study': producer.STUDY, 'rows': rows, 'batches': batches}
    qualified = producer.qualify(plan, bodies, decode)
    metadata = [{'slot': i, 'mw': 6.0 if i < 20 else 4.0, 'group': 'g' + str(i),
                 'group_eligible': True} for i in range(65)]
    external = {'grouping_frozen': True, 'prior_support_floor_pass': True}
    return plan, qualified, bodies, metadata, external


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.q, self.bodies, self.meta, self.external = fixture()

    def run_adapter(self, decoder=decode):
        return adapter.run(self.plan, self.q, self.bodies, decoder, self.meta, self.external)

    def test_fixed_denominator_train_only_decode_and_fragmented_activity(self):
        called = []
        def counting(raw, descriptor):
            called.append(descriptor['ordinal'])
            return decode(raw, descriptor)
        out = self.run_adapter(counting)
        self.assertEqual(len(out['results']), 65)
        self.assertEqual(out['decoded_train_records'], 41 * 6)
        self.assertEqual(len(called), 41 * 6)
        self.assertTrue(all(v is False for v in out['claims'].values()))
        self.assertTrue(all(out['results'][i]['partition'] == 'DEV' for i in range(41, 65)))
        self.assertEqual(len(out['results'][0]['horizons']), 3)

    def test_all_denied_never_calls_decoder(self):
        for m in self.meta:
            m['group_eligible'] = False
        self.assertEqual(self.run_adapter(lambda *_: self.fail('denied decode'))['decoded_train_records'], 0)

    def test_unknown_groups_preserve_rows(self):
        for m in self.meta:
            m['group'] = None
        self.assertEqual(len(self.run_adapter(lambda *_: self.fail('unknown decode'))['results']), 65)

    def test_dev_only_bodies_never_decode(self):
        # Identical invented bodies can occur across slots; callback is traced by active row instead.
        original = adapter.reconstruct
        rows = []
        def trace(plan, row, *args):
            rows.append(row['ordinal'])
            return original(plan, row, *args)
        with patch.object(adapter, 'reconstruct', trace):
            self.run_adapter()
        self.assertEqual(rows, list(range(41)))

    def test_raw_record_pin_rejects(self):
        self.q['records'][0]['raw_sha256'] = '0' * 64
        with self.assertRaisesRegex(adapter.InvalidInput, 'raw_hash'):
            self.run_adapter()

    def test_sample_pin_rejects(self):
        self.q['records'][0]['samples_sha256'] = '0' * 64
        with self.assertRaisesRegex(adapter.InvalidInput, 'sample_hash'):
            self.run_adapter()

    def test_view_pin_rejects(self):
        next(c for c in self.q['rows'][0]['cells'][0]['components'] if c['channel'] == 'HHE')['view_sha256'] = '0' * 64
        with self.assertRaisesRegex(adapter.InvalidInput, 'view_hash'):
            self.run_adapter()

    def test_crop_hash_and_half_open_binding_rejects(self):
        piece = next(c for c in self.q['rows'][0]['cells'][0]['components'] if c['channel'] == 'HHE')['pieces'][0]
        piece['hi'] += 1
        with self.assertRaisesRegex(adapter.InvalidInput, 'piece_replay'):
            self.run_adapter()

    def test_dropped_record_view_rejects(self):
        for cell in self.q['rows'][0]['cells']:
            component = next(c for c in cell['components'] if c['channel'] == 'HHE')
            component['pieces'] = component['pieces'][:1]
        with self.assertRaises(adapter.InvalidInput):
            self.run_adapter()

    def test_grid_mismatch_rejects_without_clock_repair(self):
        def shifted(raw, descriptor):
            value = decode(raw, descriptor)
            value['start_ns'] += 1
            return value
        with self.assertRaisesRegex(adapter.InvalidInput, 'decoder_grid'):
            self.run_adapter(shifted)

    def test_dtype_and_numeric_mutation_rejects(self):
        def mutated(raw, descriptor):
            value = decode(raw, descriptor)
            value['values'][0] += 1
            return value
        with self.assertRaisesRegex(adapter.InvalidInput, 'sample_hash'):
            self.run_adapter(mutated)

    def test_body_pin_rejects_before_decode(self):
        self.bodies[0] = self.bodies[0][:-1] + b'x'
        with self.assertRaises(ValueError):
            self.run_adapter(lambda *_: self.fail('bad body decode'))

    def test_exact_metadata_and_slot_types(self):
        self.meta[0]['slot'] = False
        with self.assertRaisesRegex(adapter.InvalidInput, 'metadata'):
            self.run_adapter(lambda *_: self.fail('bad metadata decode'))

    def test_false_external_gate_retains_no_fit_authority(self):
        self.external['prior_support_floor_pass'] = False
        out = self.run_adapter()
        self.assertFalse(out['summary']['combined_prospective_gate'])
        self.assertFalse(out['summary']['fit_authorized'])

    def test_deadline_before_decode(self):
        with patch.object(adapter.time, 'monotonic', side_effect=[0, 301]):
            with self.assertRaisesRegex(adapter.InvalidInput, 'wall_timeout'):
                self.run_adapter(lambda *_: self.fail('late decode'))

    def test_output_cap_no_partial_result(self):
        with patch.object(adapter, 'MAX_PRIVATE', 1):
            with self.assertRaisesRegex(adapter.InvalidInput, 'output_cap'):
                self.run_adapter()

    def test_incomplete_identity_rejects(self):
        self.q['disposition'] = 'incomplete'
        with self.assertRaisesRegex(adapter.InvalidInput, 'qualified_identity'):
            self.run_adapter(lambda *_: self.fail('incomplete decode'))

    def test_pre_t0_train_and_dev_picks_retained_without_decoding(self):
        for slot in (0, 41):
            row = self.plan['rows'][slot]
            row['pick_ns'] = row['t0_ns'] - 1
            # Qualification cutoffs are unchanged and pick-before remains True.
        original = adapter.reconstruct
        visited = []
        def traced(plan, row, *args):
            visited.append(row['ordinal'])
            return original(plan, row, *args)
        with patch.object(adapter, 'reconstruct', traced):
            out = self.run_adapter()
        self.assertNotIn(0, visited)
        self.assertNotIn(41, visited)
        self.assertEqual(out['results'][0]['horizons'][0]['status'], 'UNSUPPORTED')
        self.assertEqual(out['results'][41]['horizons'][0]['status'], 'DEFERRED_DEV')
        self.assertEqual(self.plan['rows'][0]['pick_ns'], self.plan['rows'][0]['t0_ns'] - 1)

    def test_previous_components_released_before_next_reconstruction(self):
        original = adapter.reconstruct
        state = {}
        def traced(*args):
            if 'last' in state:
                # One reference in this test-owned dict, plus getrefcount's argument.
                self.assertEqual(sys.getrefcount(state['last']), 2)
            components, count = original(*args)
            state['last'] = components
            return components, count
        with patch.object(adapter, 'reconstruct', traced):
            self.run_adapter()

    def test_supported_b100_rate_outside_activity_period_bound_retained(self):
        rate = Fraction.from_float(struct.unpack('>f', struct.pack('>f', 40.1))[0])
        period = Fraction(10**9) / rate
        body = bytearray()
        for suffix in 'EN12Z':
            for ordinal in range(11):
                micros = round(ordinal * 32 * period / 1000)
                raw = bytearray(256)
                raw[:20] = b'000001D ABC    HH' + suffix.encode() + b'NZ'
                second, remainder = divmod(micros, 10**6)
                fraction, correction = divmod(remainder, 100)
                struct.pack_into('>HHBBBBHHhhBBBBiHH', raw, 20, 2024, 1, 0, 0, second,
                                 0, fraction, 32, 8, 1, 0, 0, 0, 3, 0, 84, 48)
                struct.pack_into('>HHBBBB', raw, 48, 1000, 56, 3, 1, 8, 0)
                struct.pack_into('>HHfBBBB', raw, 56, 100, 68, float(rate), 0, 0, 0, 0)
                struct.pack_into('>HHBbBB', raw, 68, 1001, 0, 90, correction, 0, 0)
                struct.pack_into('>' + 'i' * 32, raw, 84, *([0] * 32))
                body.extend(raw)
        body = bytes(body)
        self.bodies = {i: body for i in range(17)}
        for batch in self.plan['batches']:
            batch['body_bytes'] = len(body)
            batch['body_sha256'] = hashlib.sha256(body).hexdigest()
        for row in self.plan['rows']:
            row['nominal_rates'] = {code: [rate.numerator, rate.denominator] for code in row['nominal_rates']}
        self.q = producer.qualify(self.plan, self.bodies, decode)
        self.assertEqual(self.q['rows'][0]['cells'][2]['joint']['status'], 'complete')
        out = self.run_adapter(lambda *_: self.fail('unsupported grid decoded'))
        self.assertEqual(len(out['results']), 65)
        self.assertEqual(len(out['adapter_denials']), 41)
        self.assertEqual(out['results'][0]['horizons'][0]['status'], 'UNSUPPORTED')
        self.assertEqual(out['adapter_denials'][0]['reason'], 'activity_period_bound')
        self.assertEqual(self.q['rows'][0]['cells'][2]['joint']['status'], 'complete')

    def test_duplicate_record_rejects(self):
        self.q['records'].append(copy.deepcopy(self.q['records'][0]))
        with self.assertRaisesRegex(adapter.InvalidInput, 'duplicate_record'):
            self.run_adapter(lambda *_: self.fail('duplicate decode'))


if __name__ == '__main__':
    unittest.main()

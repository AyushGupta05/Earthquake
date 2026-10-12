import unittest
from fractions import Fraction
from geometry import crop, component_geometry, compatible, header_grid, rate_agrees
from strict import Reject, load


def record():
    return {'date_unused': 0, 'b1000_reserved': 0, 'b100': None, 'b1001': None,
            'date': [1970, 1, 0, 0, 0, 0], 'flags': [0, 0, 0], 'correction': 0, 'rate': [100, 1]}


class ArithmeticTests(unittest.TestCase):
    def test_left_included_cutoff_excluded(self):
        self.assertEqual(crop(0, Fraction(10), 100, 100_000_000, 500_000_000), (1, 5, Fraction(100_000_000)))

    def test_fractional_grid(self):
        self.assertEqual(crop(0, Fraction(3), 100, 1, 1_000_000_000)[:2], (1, 3))

    def test_empty_outside(self):
        self.assertEqual(crop(0, Fraction(1), 2, 3_000_000_000, 4_000_000_000)[:2], (2, 2))
        self.assertEqual(crop(0, Fraction(1), 2, -3_000_000_000, -2_000_000_000)[:2], (0, 0))

    def test_signed_rates(self):
        for f, m, expected in ((2, 3, 6), (-2, 3, Fraction(3, 2)), (2, -3, Fraction(2, 3)), (-2, -3, Fraction(1, 6))):
            r = record(); r['rate'] = [f, m]
            self.assertEqual(header_grid(r), (0, expected))
        r = record(); r['rate'][0] = 0
        with self.assertRaises(Reject): header_grid(r)

    def test_correction_mask_and_signed_microseconds(self):
        r = record(); r['correction'] = -5; r['b1001'] = [100, -50, 0, 0]
        self.assertEqual(header_grid(r)[0], -550_000)
        r['flags'][0] = 2
        self.assertEqual(header_grid(r)[0], -50_000)

    def test_explicit_float32_exact(self):
        r = record(); r['rate'] = [0, 0]; r['b100'] = [0.10000000149011612, 0, 0, 0, 0]
        rate = header_grid(r)[1]
        self.assertEqual(rate, Fraction.from_float(r['b100'][0]))
        self.assertTrue(rate_agrees(r['b100'][0], rate))
        self.assertFalse(rate_agrees(float(rate) * 1.000001, rate))
        self.assertFalse(rate_agrees(float('nan'), rate))

    def test_reserved_unsupported(self):
        for field, value in (('date_unused', 1), ('b1000_reserved', 1), ('b100', [100, 0, 1, 0, 0]), ('b1001', [100, 0, 1, 0])):
            r = record(); r[field] = value
            with self.assertRaises(Reject): header_grid(r)

    def test_piece_boundaries_gap_overlap(self):
        left, right, rate = 0, 1_000_000_000, Fraction(10)
        a = (0, rate, 0, 5); b = (500_000_000, rate, 0, 5)
        self.assertEqual(component_geometry([b, a], left, right)[:2], ('complete', 'complete'))
        self.assertEqual(component_geometry([a, (600_000_000, rate, 0, 4)], left, right)[:2], ('incomplete', 'gap'))
        self.assertEqual(component_geometry([a, (400_000_000, rate, 0, 6)], left, right)[:2], ('incomplete', 'overlap'))

    def test_edge_and_local_rate(self):
        rate = Fraction(10)
        self.assertEqual(component_geometry([(100_000_000, rate, 0, 9)], 0, 1_000_000_000)[:2], ('incomplete', 'edge'))
        self.assertEqual(component_geometry([(0, rate, 0, 10), (900_000_000, Fraction(20), 0, 2)], 0, 1_000_000_000)[:2], ('incomplete', 'mixed_rate'))
        self.assertEqual(component_geometry([(0, rate, 0, 10)], 0, 1_000_000_000)[:2], ('complete', 'complete'))

    def test_grid_phase_and_rate(self):
        self.assertTrue(compatible([(Fraction(10), Fraction(0), Fraction(9)), (Fraction(10), Fraction(500), Fraction(9))]))
        self.assertFalse(compatible([(Fraction(10), Fraction(0), Fraction(9)), (Fraction(10), Fraction(2000), Fraction(9))]))
        self.assertFalse(compatible([(Fraction(10), Fraction(0), Fraction(9)), (Fraction(20), Fraction(0), Fraction(9))]))

    def test_strict_json(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e10000}', b'[]junk', b'\xff'):
            with self.assertRaises(Reject): load(raw, 1024)
        self.assertEqual(load(b'{"x":1}', 1024), {'x': 1})


if __name__ == '__main__': unittest.main()

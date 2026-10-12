import unittest
from routing import route, nominal_suffixes


def row(index, station='ABCD', location='', prefix='HH'):
    return {'ordinal': index, 'network': 'NZ', 'station': station, 'location': location, 'prefix': prefix}


class RoutingTests(unittest.TestCase):
    def test_shared_record_routes_every_original_row(self):
        self.assertEqual(route(['NZ', 'ABCD', '', 'HHE'], [row(1), row(2), row(3, station='EFGH')]), [1, 2])

    def test_exact_internal_location_prefix_identity(self):
        rows = [row(1)]
        for nslc in (['NZ', 'ABCD', '00', 'HHE'], ['NZ', 'ABCD', '', 'BHE'], ['NZ', 'EFGH', '', 'HHE'], ['XX', 'ABCD', '', 'HHE']):
            self.assertEqual(route(nslc, rows), [])
        self.assertEqual(route(['NZ', 'ABCD', '', 'HHX'], rows), [1])

    def test_unknown_and_literal_family(self):
        self.assertIsNone(nominal_suffixes(None))
        self.assertIsNone(nominal_suffixes('123'))
        self.assertEqual(nominal_suffixes('ENZ'), ('E', 'N', 'Z'))
        self.assertEqual(nominal_suffixes('12Z'), ('1', '2', 'Z'))


if __name__ == '__main__': unittest.main()

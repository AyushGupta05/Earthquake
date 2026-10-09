import unittest
from types import SimpleNamespace
from population import bucket, station_groups, select


def identity(salt, held):
    return next(str(i) for i in range(1000) if (bucket(salt, str(i)) < 2) == held)


class PopulationTests(unittest.TestCase):
    def records(self):
        out = []
        for event in (identity('polarization-event-v1', False), identity('polarization-event-v1', True)):
            for station in (identity('polarization-station-v1', False), identity('polarization-station-v1', True)):
                for n in range(7):
                    out.append(dict(source_row_index=len(out), source_id=event, station_id=station,
                                    trace_name=f'{event}.{station}.{n}', arbitrary_target=float(n)))
        return out

    def test_split_weights_identity_and_no_replacement(self):
        rows = self.records()
        selected, audit = select(rows, {r['station_id']: r['station_id'] for r in rows})
        self.assertEqual(len(selected), 12)
        self.assertEqual({r['subset'] for r in selected}, {'fit', 'eval_seen', 'eval_held'})
        self.assertTrue(all(r['sampling_weight'] == 7/4 for r in selected))
        self.assertEqual(audit['fitting_events_at_held_stations_excluded'], 7)
        valid = [r for r in selected if r['source_row_index'] != selected[0]['source_row_index']]
        self.assertEqual(len(valid), 11)
        self.assertTrue(all(r['n_sampled'] == 4 for r in valid))

    def test_label_and_order_independent(self):
        rows = self.records()
        groups = {r['station_id']: r['station_id'] for r in rows}
        first, _ = select(rows, groups)
        for row in rows:
            row['arbitrary_target'] = 999
        second, _ = select(rows[::-1], groups)
        self.assertEqual([r['source_row_index'] for r in first], [r['source_row_index'] for r in second])

    def test_event_caps_and_duplicate_rejection(self):
        rows = self.records()
        groups = {r['station_id']: r['station_id'] for r in rows}
        result, _ = select(rows, groups, record_cap=1)
        self.assertEqual(len(result), 3)
        with self.assertRaises(ValueError):
            select(rows+[rows[0]], groups)

    def test_alias_transitive_union_and_missing(self):
        def epoch(name, lat, elevation=0):
            return SimpleNamespace(network='N', station=name, latitude_deg=lat,
                                   longitude_deg=0., elevation_m=elevation)
        epochs = [epoch('a', 0), epoch('b', .0008), epoch('c', .0016), epoch('d', 0, 51)]
        groups, missing = station_groups(['N.a','N.b','N.c','N.d','N.e'], epochs)
        self.assertEqual(groups, {'N.a':'N.a','N.b':'N.a','N.c':'N.a','N.d':'N.d','N.e':'N.e'})
        self.assertEqual(missing, ['N.e'])


if __name__ == '__main__':
    unittest.main()

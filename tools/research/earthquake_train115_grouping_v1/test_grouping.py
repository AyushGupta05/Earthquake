"""Invented115-origin graph boundaries, bridges and independent parity."""
import copy
import math
import unittest
from unittest.mock import patch
import grouping
import graph_audit


def fixture():
    return [{'ordinal':i,'partition':'TRAIN' if i<41 or i>=65 else 'DEV',
             'origin_ns':i*31*86400*10**9,'latitude':0.,'longitude':0.} for i in range(115)]


class GroupTests(unittest.TestCase):
    def test_fixed_denominators_singletons(self):
        rows=fixture();r=grouping.group_events(rows)
        self.assertEqual(r['events'],115);self.assertEqual(r['maximum_pairs'],6555)
        self.assertEqual(r['partition_counts'],{'TRAIN':91,'DEV':24});self.assertEqual(len(r['groups']),115)
        self.assertEqual(r['edges'],[]);self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_newTRAIN_bridges_oldTRAIN_components(self):
        rows=fixture()
        for i in (0,1,65):rows[i]['origin_ns']=0
        rows[0]['longitude']=0.;rows[1]['longitude']=3.;rows[65]['longitude']=1.5
        r=grouping.group_events(rows)
        self.assertIn([0,65],r['edges']);self.assertIn([1,65],r['edges']);self.assertNotIn([0,1],r['edges'])
        g=next(g for g in r['groups'] if g['identifier']==0)
        self.assertEqual(g['original_ordinals'],[0,1,65]);self.assertTrue(g['operational_eligible'])
        self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_newTRAIN_bridge_into_DEV_excludes_all(self):
        rows=fixture()
        for i in (0,41,65):rows[i]['origin_ns']=0
        rows[0]['longitude']=0.;rows[41]['longitude']=3.;rows[65]['longitude']=1.5
        r=grouping.group_events(rows);g=next(g for g in r['groups'] if g['identifier']==0)
        self.assertTrue(g['cross_partition']);self.assertFalse(g['operational_eligible'])
        for i in (0,41,65):self.assertEqual(r['rows'][i]['status'],'CROSS_PARTITION');self.assertFalse(r['rows'][i]['operational_eligible'])
        self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_time_boundary_inclusive_and_one_ns_outside(self):
        rows=fixture();rows[0]['origin_ns']=0;rows[65]['origin_ns']=grouping.WINDOW_NS
        r=grouping.group_events(rows);self.assertIn([0,65],r['edges'])
        rows[65]['origin_ns']+=1;r=grouping.group_events(rows);self.assertNotIn([0,65],r['edges'])
    def test_distance_boundary_comparison_inclusive(self):
        rows=fixture();rows[65]['origin_ns']=0
        with patch('grouping.distance_km',return_value=200.):self.assertIn([0,65],grouping.group_events(rows)['edges'])
        with patch('grouping.distance_km',return_value=math.nextafter(200.,math.inf)):
            self.assertNotIn([0,65],grouping.group_events(rows)['edges'])
    def test_actual_near_distance_boundary_no_epsilon(self):
        delta=math.degrees(200./6371.)
        self.assertAlmostEqual(grouping.distance_km(0.,0.,0.,delta),200.,places=10)
        self.assertLess(grouping.distance_km(0.,0.,0.,delta-1e-6),200.)
        self.assertGreater(grouping.distance_km(0.,0.,0.,delta+1e-6),200.)
    def test_dateline_shortest_arc(self):
        rows=fixture();rows[65]['origin_ns']=0;rows[0]['longitude']=179.8;rows[65]['longitude']=-179.8
        r=grouping.group_events(rows);self.assertIn([0,65],r['edges']);self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_antipodes_finite_and_no_edge(self):
        self.assertAlmostEqual(grouping.distance_km(0.,0.,0.,180.),math.pi*6371.,places=8)
        rows=fixture();rows[65]['origin_ns']=0;rows[65]['longitude']=180.
        r=grouping.group_events(rows);self.assertNotIn([0,65],r['edges']);self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_unknown_never_known_singleton(self):
        for key,value in [('origin_ns',None),('origin_ns',True),('origin_ns',2**63),('latitude',float('nan')),
                          ('longitude',float('inf')),('latitude',91.),('longitude',-181.),('latitude',10**1000),('latitude',False)]:
            rows=fixture();rows[65][key]=value;r=grouping.group_events(rows)
            self.assertEqual(r['rows'][65]['status'],'UNKNOWN_ORIGIN');self.assertIsNone(r['rows'][65]['group_identifier'])
            self.assertFalse(r['rows'][65]['operational_eligible']);self.assertFalse(any(65 in g['original_ordinals'] for g in r['groups']))
            self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_partial_origin_unknown(self):
        rows=fixture();rows[65]['latitude']=None;r=grouping.group_events(rows)
        self.assertEqual(r['rows'][65]['status'],'UNKNOWN_ORIGIN');self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_negative_utc_integer_exact(self):
        rows=fixture();rows[0]['origin_ns']=-2**63;rows[65]['origin_ns']=-2**63+grouping.WINDOW_NS
        r=grouping.group_events(rows);self.assertIn([0,65],r['edges']);self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_float_timestamp_unknown(self):
        rows=fixture();rows[0]['origin_ns']=0.;r=grouping.group_events(rows)
        self.assertEqual(r['rows'][0]['status'],'UNKNOWN_ORIGIN');self.assertTrue(graph_audit.audit(rows,r)['agreement'])
    def test_no_metadata_mutation(self):
        rows=fixture();old=copy.deepcopy(rows);grouping.group_events(rows);self.assertEqual(rows,old)
    def test_wrong_counts_and_TEST_rejected(self):
        for slot,partition in [(65,'DEV'),(0,'TEST'),(0,'DEV')]:
            rows=fixture();rows[slot]['partition']=partition
            with self.assertRaises(ValueError):grouping.group_events(rows)
            with self.assertRaises(ValueError):graph_audit.audit(rows,{})
    def test_old_prefix_partition_counts_enforced(self):
        rows=fixture();rows[0]['partition']='DEV';rows[41]['partition']='TRAIN'
        # Counts stay correct, legal original ordering need not put all TRAIN first.
        r=grouping.group_events(rows);self.assertTrue(graph_audit.audit(rows,r)['agreement'])
        rows=fixture();rows[0]['partition']='DEV';rows[65]['partition']='TRAIN'
        with self.assertRaises(ValueError):grouping.group_events(rows)
    def test_reorder_duplicate_bool_ordinal_rejected(self):
        for change in (lambda r:r.reverse(),lambda r:r[65].update(ordinal=64),lambda r:r[0].update(ordinal=False)):
            rows=fixture();change(rows)
            with self.assertRaises(ValueError):grouping.group_events(rows)
    def test_labels_availability_extra_fields_rejected(self):
        for key in ('mw','waveform','available','prediction'):
            rows=fixture();rows[0][key]=1
            with self.assertRaises(ValueError):grouping.group_events(rows)
    def test_fixed_115_not_padded_65(self):
        for rows in (fixture()[:65],fixture()+[fixture()[0]],tuple(fixture())):
            with self.assertRaises(ValueError):grouping.group_events(rows)
    def test_all_close_max_pairs_and_cross_partition(self):
        rows=fixture()
        for r in rows:r['origin_ns']=0
        result=grouping.group_events(rows);self.assertEqual(len(result['edges']),6555)
        self.assertEqual(len(result['groups']),1);self.assertEqual(result['groups'][0]['identifier'],0)
        self.assertTrue(result['groups'][0]['cross_partition']);self.assertTrue(graph_audit.audit(rows,result)['agreement'])
    def test_audit_membership_edge_boolean_flag_tamper(self):
        rows=fixture();r=grouping.group_events(rows)
        for change in (lambda x:x['rows'][0].update(group_identifier=True),lambda x:x['edges'].append([0,65]),
                       lambda x:x.update(events=114),lambda x:x['groups'][0].update(operational_eligible=1),
                       lambda x:x.update(fit_authorized=True)):
            x=copy.deepcopy(r);change(x);self.assertFalse(graph_audit.audit(rows,x)['agreement'])
    def test_public_no_origin_slot_or_group_identity(self):
        p=grouping.public_summary(grouping.group_events(fixture()));self.assertEqual(p['events'],115)
        self.assertFalse(any(k in p for k in ('rows','coordinates','latitude','longitude','origin_ns','ordinal','identifier')))
        self.assertFalse(p['physical_sequence_independence_verified']);self.assertFalse(p['fit_authorized'])


if __name__=='__main__':unittest.main()

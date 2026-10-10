"""Invented fixtures only. No network or actual census reads."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import core
import audit


def piece(start=0, rate=10, data=None):
    return {'start_ns': start, 'sample_rate': rate, 'data': list(range(10)) if data is None else data}


def channels():
    return [{'network':'NZ','station':'AAA','location':'10','code':'HH'+s,'start_ns':-10*core.NS,
             'end_ns':None,'sample_rate':10.,'dip':dip,'azimuth':az}
            for s,dip,az in (('E',0.,90.),('N',0.,0.),('Z',-90.,0.))]


TARGET={'network':'NZ','station':'AAA','location':'10','prefix':'HH','pick_ns':0,'queryable':True}


def metadata():
    groups=[]; outcomes={}
    for index,(mag,year) in enumerate(((5.6,2004),(5.7,2024),(6.1,2005),(6.2,2023),(7.1,2006),(7.2,2022))):
        eid=str(12345+index)
        groups.append({'event_id':eid,'eligible':True,'mw_min':mag,'mw_max':mag,'dates':[f'{year}0101000000']})
        outcomes[eid]={'status':'ok','accepted_picks':[{'network':'NZ','station':s,'location':'10','channel':'HHZ','pick_id':s,
                           'time':f'{year}-01-01T00:00:0{n}Z'} for n,s in enumerate(('AAA','BBB','CCC','DDD'))]}
    return groups,outcomes


class PrefixTests(unittest.TestCase):
    def test_strict_deadline_and_future_poison_invariance(self):
        good=piece(data=list(range(10))+[100])
        poisoned=piece(data=list(range(10))+[float('nan'),1e100])
        a=core.component([good],0,core.NS,10)
        self.assertTrue(a['available']); self.assertEqual(a['samples'],10)
        self.assertEqual(a,core.component([poisoned],0,core.NS,10))

    def test_fractional_rate_absolute_index(self):
        p=core.crop(piece(rate=3,data=[1,2,3,999]),0,core.NS)
        self.assertEqual(list(p['data']),[1,2,3]); self.assertEqual(p['last'],core.Fraction(2*core.NS,3))

    def test_left_inclusion_and_prebuffer(self):
        p=core.crop(piece(start=-core.NS,data=list(range(21))),0,core.NS)
        self.assertEqual(list(p['data']),list(range(10,20)))

    def test_gap_and_overlap_fail_without_fill(self):
        for start,key in ((600_000_000,'gaps'),(400_000_000,'overlaps')):
            r=core.component([piece(data=[0,1,2,3,4]),piece(start=start,data=[5,6,7,8,9])],0,core.NS,10)
            self.assertFalse(r['available']); self.assertGreater(r[key],0)

    def test_rounding_tolerance_and_wrong_rate(self):
        a=core.component([piece(data=[0,1,2,3,4]),piece(start=500_000_500,data=[5,6,7,8,9])],0,core.NS,10)
        self.assertTrue(a['available'])
        r=core.component([piece()],0,core.NS,20)
        self.assertFalse(r['available']); self.assertFalse(r['sample_rate_matches'])

    def test_nan_inside_prefix_and_missing_edges_fail(self):
        p=piece(data=[0,1,float('nan'),3,4,5,6,7,8,9])
        self.assertFalse(core.component([p],0,core.NS,10)['available'])
        self.assertFalse(core.component([piece(start=200_000_000)],0,core.NS,10)['edge_coverage'])

    def test_one_entire_missing_left_sample_is_not_rounding(self):
        present=core.component([piece()],0,core.NS,10)
        missing=core.component([piece(start=100_000_000,data=list(range(1,10)))],0,core.NS,10)
        self.assertFalse(missing['available']);self.assertFalse(missing['edge_coverage'])
        self.assertFalse(core.compatible_lattices({'E':present,'N':missing,'Z':present},10))

    def test_no_samples_and_future_invalid_rate_ignored(self):
        self.assertEqual(core.component([],0,core.NS,10)['reason'],'no_prefix_samples')
        self.assertEqual(core.component([piece(),piece(start=core.NS,rate=float('nan'))],0,core.NS,10),core.component([piece()],0,core.NS,10))

    def test_flatline_and_extreme_run_are_screens_only(self):
        for data in ([2]*10,[0]+[10]*8+[1]):
            r=core.component([piece(data=data)],0,core.NS,10)
            self.assertTrue(r['available']); self.assertTrue(r['clipping_candidate']); self.assertFalse(r['clipping_screen_passed']); self.assertFalse(r['physically_unclipped_verified'])

    def test_equal_rates_shifted_component_lattices_fail(self):
        a=core.component([piece()],0,core.NS,10)
        shifted=core.component([piece(start=50_000_000)],0,core.NS,10)
        self.assertTrue(a['available']); self.assertTrue(shifted['available'])
        self.assertFalse(core.compatible_lattices({'E':a,'N':shifted,'Z':a},10))
        rounded=core.component([piece(start=500)],0,core.NS,10)
        self.assertTrue(core.compatible_lattices({'E':a,'N':rounded,'Z':a},10))

    def test_extreme_run_invariant_to_contiguous_fragment_split(self):
        data=[0]+[10]*8+[1]
        whole=core.component([piece(data=data)],0,core.NS,10)
        split=core.component([piece(data=data[:5]),piece(start=500_000_000,data=data[5:])],0,core.NS,10)
        self.assertEqual(whole,split); self.assertEqual(split['longest_prefix_extreme_run'],8)
        for start in (600_000_000,400_000_000):
            interrupted=core.component([piece(data=data[:5]),piece(start=start,data=data[5:])],0,core.NS,10)
            self.assertLess(interrupted['longest_prefix_extreme_run'],8)

    def test_epoch_boundaries_ambiguity_and_future_metadata(self):
        records=channels(); result=core.triplet(records,TARGET,-5*core.NS,core.NS)
        future=copy.deepcopy(records[0]); future['start_ns']=3*core.NS
        self.assertEqual(result,core.triplet(records+[future],TARGET,-5*core.NS,core.NS))
        with self.assertRaisesRegex(ValueError,'ambiguous'): core.triplet(records+[future],TARGET,-5*core.NS,5*core.NS)
        records[0]['end_ns']=core.NS
        self.assertEqual(len(core.triplet(records,TARGET,-5*core.NS,core.NS)),3)
        with self.assertRaises(ValueError): core.triplet(records,TARGET,-5*core.NS,3*core.NS)

    def test_missing_epoch_start_orientation_rate_or_axis_fail(self):
        for key,value in (('start_ns',None),('azimuth',0.),('sample_rate',20.),('dip',20.)):
            cc=channels(); cc[0][key]=value
            with self.assertRaises(ValueError): core.triplet(cc,TARGET,-5*core.NS,core.NS)
        with self.assertRaises(ValueError): core.triplet(channels()[:2],TARGET,-5*core.NS,core.NS)


class SelectionTests(unittest.TestCase):
    def test_three_bands_historical_years_and_order_invariance(self):
        groups,outcomes=metadata(); chosen=core.choose(groups,outcomes)
        self.assertEqual(len(chosen),6); self.assertEqual(sum(len(e['stations']) for e in chosen),18)
        self.assertEqual(chosen,core.choose(list(reversed(groups)),dict(reversed(list(outcomes.items())))))
        self.assertEqual([e['year'] for e in chosen],['2004','2024','2005','2023','2006','2022'])
        self.assertTrue(all([s['station'] for s in e['stations']]==['AAA','BBB','CCC'] for e in chosen))

    def test_ambiguous_band_and_failed_event_excluded_without_replacement(self):
        groups,outcomes=metadata(); groups[0]['mw_max']=6.1; outcomes[groups[1]['event_id']]['status']='failed'
        self.assertEqual(len(core.choose(groups,outcomes)),4)

    def test_invalid_station_is_retained_unqueryable(self):
        groups,outcomes=metadata(); outcomes[groups[0]['event_id']]['accepted_picks'][0]['location']='malformed'
        chosen=core.choose(groups,outcomes); self.assertFalse(chosen[0]['stations'][0]['queryable']); self.assertEqual(len(chosen[0]['stations']),3)
        self.assertEqual(len(audit.requests_for(chosen)),34)

    def test_query_list_bounds_and_archive_only(self):
        groups,outcomes=metadata(); events=core.choose(groups,outcomes); requests=audit.requests_for(events)
        self.assertEqual(len(requests),36)
        for request in requests:
            u=audit.urllib.parse.urlparse(request['url']); q=audit.urllib.parse.parse_qs(u.query)
            self.assertEqual(u.scheme,'https'); self.assertEqual(u.netloc,'service.geonet.org.nz'); self.assertEqual(q['channel'],['HH?']); self.assertEqual(q['location'],['10'])
            self.assertEqual(core.stamp_ns(q['endtime'][0])-core.stamp_ns(q['starttime'][0]),10*core.NS)

    def test_same_year_two_distinct_ids(self):
        groups,outcomes=metadata()
        for g in groups: g['dates']=['20100101000000']
        chosen=core.choose(groups,outcomes); self.assertEqual(len(chosen),6); self.assertEqual(len({e['event_id'] for e in chosen}),6)


class GateTests(unittest.TestCase):
    def test_timezone_and_request_precision(self):
        with self.assertRaises(ValueError): core.stamp_ns('2020-01-01T00:00:00')
        with self.assertRaises(ValueError): core.iso(1)
        n=core.stamp_ns('2020-01-01T00:00:00.123456Z'); self.assertEqual(core.stamp_ns(core.iso(n)),n)

    def test_no_parent_receipt_means_no_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit,'local_path',lambda p:p), patch.object(audit.subprocess,'Popen') as launch:
            root=Path(tmp); (root/'plan.json').write_text('{}'); (root/'receipt.json').write_text('{}')
            with self.assertRaises(ValueError): audit.collect(root/'plan.json',root/'receipt.json',root/'out')
            launch.assert_not_called(); self.assertFalse((root/'out').exists())

    def test_real_output_containment(self):
        with self.assertRaises(ValueError): audit.local_path(Path('/tmp/waves'))
        with self.assertRaises(ValueError): audit.local_path(audit.BASE/'local_runs')
        self.assertEqual(audit.local_path(audit.BASE/'local_runs/fixture'),audit.BASE/'local_runs/fixture')

    def test_census_hash_mismatch_fails_before_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'census_input_pins.json').write_text(json.dumps({'groups.json':'0'*64})); (root/'groups.json').write_text('[]')
            with patch.object(audit,'BASE',root), self.assertRaisesRegex(ValueError,'checksum'): audit.census_inputs(root)

    def test_outer_deadline_includes_validation_and_preserves_missingness(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit,'local_path',lambda p:p), patch.object(audit,'validate_execution',side_effect=audit.AuditDeadline('invented timeout')), patch.object(audit.subprocess,'Popen') as launch:
            out=Path(tmp)/'out'
            self.assertEqual(audit.collect(Path(tmp)/'plan',Path(tmp)/'receipt',out),2)
            launch.assert_not_called()
            receipt=json.loads((out/'OUTER_INCOMPLETE.json').read_text())
            self.assertFalse(receipt['completed']); self.assertIsNone(receipt['frozen_station_denominator'])

    def test_bounded_local_validation_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'body'; path.write_bytes(b'x'*11)
            with self.assertRaises(ValueError): audit.bounded_bytes(path,10)

    def test_outer_timeout_after_plan_retains_station_denominator(self):
        events=core.choose(*metadata()); plan={'events':events}
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit,'local_path',lambda p:p), patch.object(audit,'validate_execution',return_value=plan), patch.object(audit.subprocess,'Popen') as launch, patch.object(audit.os,'killpg') as kill:
            process=launch.return_value; process.pid=12345
            process.wait.side_effect=[audit.subprocess.TimeoutExpired('invented child',1),0]
            out=Path(tmp)/'out'
            self.assertEqual(audit.collect(Path(tmp)/'plan',Path(tmp)/'receipt',out),2)
            kill.assert_called_once_with(12345,audit.signal.SIGKILL)
            receipt=json.loads((out/'OUTER_INCOMPLETE.json').read_text())
            self.assertEqual(receipt['frozen_station_denominator'],18)
            self.assertFalse(receipt['completed']); self.assertEqual(receipt['horizons'],[1,3,5])

    def test_child_failure_retains_station_denominator(self):
        plan={'events':core.choose(*metadata())}
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit,'local_path',lambda p:p), patch.object(audit,'validate_execution',return_value=plan), patch.object(audit.subprocess,'Popen') as launch:
            launch.return_value.wait.return_value=2; out=Path(tmp)/'out'
            self.assertEqual(audit.collect(Path(tmp)/'plan',Path(tmp)/'receipt',out),2)
            receipt=json.loads((out/'PROCESS_INCOMPLETE.json').read_text())
            self.assertEqual(receipt['frozen_station_denominator'],18); self.assertFalse(receipt['completed'])


if __name__=='__main__': unittest.main()

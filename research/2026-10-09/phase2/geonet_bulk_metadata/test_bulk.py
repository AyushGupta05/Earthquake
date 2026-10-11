"""Invented fixtures only; no acquisition commands or external data requests."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import io
import types

import aggregate
import bulk
import origin
import sampling


def group(eid='12345',mw=4.0,date='20200101000000'):
    return {'event_id':eid,'eligible':True,'mw_min':mw,'mw_max':mw,'dates':[date],
            'methods':['invented'],'row_indices':[1],'external_wphase':False}


def synthetic_frame():
    groups=[];i=10000
    for year in (2004,2016,2020):
        for mw in (3.0,3.5,4.0,4.5,5.0):
            for _ in range(26 if mw==4.0 else 2):
                groups.append(group(str(i),mw,f'{year}0101000000'));i+=1
    groups.append(group('99998',6.0));return groups


def invented_spec(groups):
    strata,tail,_=sampling.frame(groups);selected=[];ss=[]
    for p in sampling.PARTITIONS:
        for b in sampling.BANDS:
            items=strata[p,b];N=len(items);n=min(N,24)
            rank=lambda g:(hashlib.sha256(f'{sampling.SELECTION_SALT}|{p}|{b}|{g["event_id"]}'.encode()).hexdigest(),g['event_id'])
            selected.extend(sorted(items,key=rank)[:n])
            ss.append({'candidate_calendar_partition':p,'Mw_band':b,'frame_N':N,'sample_n':n,
                       'inclusion_probability_n_over_N':n/N if N else None,'inverse_probability_N_over_n':N/n if n else None})
    ordered=sorted(selected,key=lambda g:(hashlib.sha256(f'{sampling.QUERY_SALT}|{g["event_id"]}'.encode()).hexdigest(),g['event_id']))
    dh=lambda ids:hashlib.sha256(('\n'.join(ids)+'\n').encode()).hexdigest()
    return {'selection_salt':sampling.SELECTION_SALT,'query_order_salt':sampling.QUERY_SALT,'strata_order':list(sampling.PARTITIONS),
            'Mw_band_order':list(sampling.BANDS),'strata':ss,'new_lower_M_unique_events':len(selected),'reused_existing_tail_events':len(tail),
            'selected_set_sha256':dh(sorted(g['event_id'] for g in selected)),'query_order_sha256':dh(g['event_id'] for g in ordered),
            'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}


def xml(eid='12345',origin_fields=None,pick_fields=None,arrivals=None):
    if origin_fields is None:origin_fields='<time><value>2020-01-01T00:00:00Z</value></time><latitude><value>-40</value></latitude><longitude><value>175</value></longitude><depth><value>12000</value></depth>'
    if pick_fields is None:pick_fields='<time><value>2020-01-01T00:00:01Z</value></time><waveformID networkCode="NZ" stationCode="SYN" channelCode="HHZ" />'
    if arrivals is None:arrivals='<arrival><pickID>smi:invented/p1</pickID><phase>P</phase><timeWeight>1</timeWeight></arrival>'
    return (f'<q:quakeml xmlns:q="http://quakeml.org/xmlns/quakeml/1.2" xmlns="http://quakeml.org/xmlns/bed/1.2"><eventParameters><event publicID="smi:invented/{eid}"><preferredOriginID>smi:invented/o1</preferredOriginID><origin publicID="smi:invented/o1">{origin_fields}{arrivals}</origin><pick publicID="smi:invented/p1">{pick_fields}</pick></event></eventParameters></q:quakeml>').encode()


def record(eid='12345',source='new_lower_M',weight=1.0):
    return {'event_id':eid,'source':source,'mw':6.0 if source=='reused_tail' else 4.0,'cmt_time':'20200101000000',
            'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','inverse_probability':weight,
            'query_url':'https://invented.invalid/'+eid}


class SamplingTests(unittest.TestCase):
    def test_selection_and_query_order_are_input_permutation_invariant(self):
        groups=synthetic_frame();spec=invented_spec(groups)
        first=sampling.select(groups,spec);second=sampling.select(list(reversed(groups)),spec)
        self.assertEqual(first,second);self.assertEqual(len(first[0]),96);self.assertEqual(len(first[1]),1)
        self.assertEqual(sum(d['not_selected_N_minus_n'] for d in first[2]),6)
        self.assertAlmostEqual(sum(g['inverse_probability'] for g in first[0]),102)

    def test_exact_boundaries_go_to_upper_bands_and_tail(self):
        groups=[group(str(10000+i),mw) for i,mw in enumerate((3.499,3.5,4,4.5,5,5.5,6,7))]
        strata,tail,_=sampling.frame(groups)
        self.assertEqual([len(strata['test2018_2024',b]) for b in sampling.BANDS],[1]*5)
        self.assertEqual([g['mw'] for g in tail],[5.5,6,7])

    def test_dates_obey_source_window_and_partition_boundaries(self):
        dates=['20030731000000','20030801000000','20141231000000','20150101000000','20171231000000','20180101000000','20241231000000','20250101000000']
        strata,_,rejected=sampling.frame([group(str(10000+i),4,d) for i,d in enumerate(dates)])
        self.assertEqual([len(strata[p,'[4,4.5)']) for p in sampling.PARTITIONS],[2,2,2]);self.assertEqual(len(rejected),2)

    def test_rejection_denominators_and_no_replacements(self):
        bad=[dict(group('20001'),eligible=False),dict(group('20002'),mw_min=3.0,mw_max=4.0),dict(group('20003'),dates=[]),group('9999999'),group('20004',float('nan')),group('20005','bad')]
        self.assertEqual(len(sampling.frame(bad)[2]),6)
        groups=synthetic_frame();spec=invented_spec(groups);groups[0]['eligible']=False
        with self.assertRaisesRegex(ValueError,'denominator'):sampling.select(groups,spec)

    def test_duplicate_groups_and_frozen_hash_change_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):sampling.frame([group(),group()])
        groups=synthetic_frame();spec=invented_spec(groups);spec['query_order_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'digest'):sampling.select(groups,spec)


class OriginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lib=bulk.library()
    def parse(self,body):return bulk.parse_row(self.lib,body,record())

    def test_valid_origin_geometry_and_P(self):
        row=self.parse(xml());o=row['origin']
        self.assertTrue(o['unique_preferred_origin_linkage']);self.assertTrue(o['valid_origin_time_in_window']);self.assertTrue(o['geometry_complete'])
        self.assertEqual(o['earliest_NZ_P_minus_origin_seconds'],1);self.assertFalse(o['earliest_NZ_P_before_origin'])
        self.assertEqual(row['base']['nz']['before_seconds'],{'1':1,'3':1,'5':1})

    def test_geometry_failure_does_not_erase_P_or_origin_time(self):
        fields='<time><value>2020-01-01T00:00:00Z</value></time><latitude><value>999</value></latitude><longitude><value>NaN</value></longitude>'
        row=self.parse(xml(origin_fields=fields));o=row['origin']
        self.assertTrue(o['valid_origin_time_in_window']);self.assertFalse(o['geometry_complete']);self.assertEqual(row['base']['nz']['stations'],1)
        self.assertEqual(set(o['reasons']),{'latitude_outside_range','longitude_nonfinite_or_invalid','depth_missing'})

    def test_duplicate_geometry_container_and_value_are_ambiguous(self):
        fields='<time><value>2020-01-01T00:00:00Z</value></time><latitude><value>1</value></latitude><latitude><value>2</value></latitude><longitude><value>1</value><value>2</value></longitude><depth><value>-3</value></depth>'
        o=self.parse(xml(origin_fields=fields))['origin']
        self.assertIsNone(o['latitude_degrees']);self.assertIsNone(o['longitude_degrees']);self.assertTrue(o['negative_depth']);self.assertEqual(o['depth_m'],-3)
        self.assertTrue(o['valid_origin_time_in_window']);self.assertIn('latitude_ambiguous',o['reasons']);self.assertIn('longitude_ambiguous',o['reasons'])

    def test_duplicate_time_and_naive_time_do_not_erase_P(self):
        for value in ('<time><value>2020-01-01T00:00:00Z</value><value>2020-01-01T00:00:00Z</value></time>','<time><value>2020-01-01T00:00:00</value></time>'):
            r=self.parse(xml(origin_fields=value));self.assertFalse(r['origin']['valid_origin_time_in_window']);self.assertEqual(r['base']['nz']['stations'],1)

    def test_P_singleton_failure_retains_independent_valid_origin_gate(self):
        row=self.parse(xml(pick_fields='<time><value>2020-01-01T00:00:01Z</value><value>2020-01-01T00:00:02Z</value></time><waveformID networkCode="NZ" stationCode="SYN" />'))
        self.assertEqual(row['outcome_status'],'parse_failed');self.assertEqual(row['base']['status'],'parse_failed')
        self.assertTrue(row['origin']['valid_origin_time_in_window']);self.assertIsNone(row['origin']['earliest_NZ_P_minus_origin_seconds'])
        p=aggregate.panel([row]);self.assertEqual(p['unknown_NZ_P_coverage_events'],1);self.assertEqual(p['valid_origin_time_in_window_events'],1)

    def test_wrong_namespace_DTD_and_identity_fail_both_diagnostics(self):
        for body in (xml(eid='54321'),xml().replace(b'quakeml/1.2',b'quakeml/9.9'),b'<!DOCTYPE foo>'+xml(),xml().replace(b'<eventParameters>',b'<eventParameters><eventParameters>')):
            r=self.parse(body);self.assertEqual(r['outcome_status'],'parse_failed');self.assertFalse(r['origin']['unique_preferred_origin_linkage'])

    def test_missing_duplicate_preferred_linkage_is_unknown(self):
        for body in (xml().replace(b'<preferredOriginID>smi:invented/o1</preferredOriginID>',b''),xml().replace(b'<preferredOriginID>smi:invented/o1</preferredOriginID>',b'<preferredOriginID>smi:invented/o1</preferredOriginID>'*2)):
            r=self.parse(body);self.assertFalse(r['origin']['unique_preferred_origin_linkage']);self.assertEqual(aggregate.panel([r])['unknown_NZ_P_coverage_events'],1)

    def test_origin_window_exact_edges(self):
        for stamp,valid in [('2003-08-01T00:00:00Z',True),('2003-07-31T23:59:59Z',False),('2025-01-01T00:00:00Z',False)]:
            r=self.parse(xml(origin_fields=f'<time><value>{stamp}</value></time>'));self.assertEqual(r['origin']['valid_origin_time_in_window'],valid)

    def test_descriptive_offsets_300_and_600_boundaries_and_negative(self):
        for origin_stamp,pick_stamp,offset,late,early in [('2020-01-01T00:05:00Z','2020-01-01T00:15:00Z',300,False,False),('2020-01-01T00:04:59Z','2020-01-01T00:15:00Z',299,True,False),('2019-12-31T23:59:00Z','2019-12-31T23:58:59Z',-60,False,True)]:
            r=self.parse(xml(origin_fields=f'<time><value>{origin_stamp}</value></time>',pick_fields=f'<time><value>{pick_stamp}</value></time><waveformID networkCode="NZ" stationCode="SYN" />'));o=r['origin']
            self.assertEqual(o['signed_origin_minus_cmt_minute_seconds'],offset);self.assertEqual(o['abs_origin_cmt_offset_ge_300s'],abs(offset)>=300)
            self.assertEqual(o['earliest_NZ_P_later_than_600s'],late);self.assertEqual(o['earliest_NZ_P_before_origin'],early)
            self.assertEqual(r['base']['nz']['stations'],1)
        self.assertFalse(o['origin_cmt_utc_day_match']);self.assertFalse(o['origin_cmt_utc_year_match']);self.assertTrue(o['origin_cmt_candidate_partition_match'])

    def test_off_window_pick_and_optional_origin_provenance(self):
        r=self.parse(xml(origin_fields='<time><value>2020-01-01T00:00:00Z</value></time><type>centroid</type><referenceSystemID>smi:invented/coordinate</referenceSystemID>',pick_fields='<time><value>2025-01-01T00:00:00Z</value></time><waveformID networkCode="NZ" stationCode="SYN" />'))
        self.assertTrue(r['origin']['earliest_NZ_pick_outside_source_window']);self.assertEqual(r['origin']['origin_type'],'centroid');self.assertEqual(r['base']['nz']['stations'],1)

    def test_pick_window_flag_does_not_need_valid_origin_time(self):
        for fields in ('','<time><value>naive</value></time>','<time><value>2020-01-01T00:00:00Z</value><value>2020-01-01T00:00:00Z</value></time>'):
            r=self.parse(xml(origin_fields=fields,pick_fields='<time><value>2025-01-01T00:00:00Z</value></time><waveformID networkCode="NZ" stationCode="SYN" />'))
            self.assertTrue(r['origin']['earliest_NZ_pick_outside_source_window']);self.assertIsNone(r['origin']['earliest_NZ_P_minus_origin_seconds']);self.assertFalse(r['origin']['valid_origin_time_in_window'])

    def test_UTC_overflow_does_not_erase_the_other_evidence_channel(self):
        r=self.parse(xml(origin_fields='<time><value>0001-01-01T00:00:00+01:00</value></time>'))
        self.assertFalse(r['origin']['valid_timezone_aware_origin_time']);self.assertEqual(r['base']['nz']['stations'],1)
        r=self.parse(xml(pick_fields='<time><value>0001-01-01T00:00:00+01:00</value></time><waveformID networkCode="NZ" stationCode="SYN"/>'))
        self.assertEqual(r['base']['status'],'parse_failed');self.assertTrue(r['origin']['valid_origin_time_in_window'])

    def test_reviewed_fractional_widths_match_compatible_runtime(self):
        bulk.utc_compatibility(self.lib)
        for fraction in ('1','12','123','1234','12345','123456'):
            r=self.parse(xml(pick_fields=f'<time><value>2020-01-01T00:00:01.{fraction}Z</value></time><waveformID networkCode="NZ" stationCode="SYN"/>'))
            self.assertEqual(r['base']['nz']['stations'],1)
        with mock.patch.object(self.lib,'utc',side_effect=ValueError('invented incompatible fractional width')):
            with self.assertRaisesRegex(ValueError,'runtime incompatible'):bulk.utc_compatibility(self.lib)

    def test_pick_clock_strict_boundaries_and_station_collapse(self):
        picks=[{'network':'NZ','station':s,'time':f'2020-01-01T00:00:{t:02d}+00:00'} for s,t in [('A',0),('A',2),('B',1),('C',3),('D',5)]]
        self.assertEqual(self.lib.coverage(picks)['before_seconds'],{'1':1,'3':2,'5':3})


class AccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.lib=bulk.library()
    def test_known_zero_and_unknown_weights_are_distinct(self):
        a=bulk.parse_row(self.lib,xml(),record(weight=2))
        b=bulk.parse_row(self.lib,xml(eid='54321',arrivals=''),record('54321',weight=3));c=dict(record('54322',weight=5),outcome_status='unattempted')
        p=aggregate.panel([a,b,c]);self.assertEqual((p['known_zero_NZ_P_events'],p['unknown_NZ_P_coverage_events']),(1,1))
        self.assertEqual(p['weighted_positive_fraction_lower_bound'],.2);self.assertEqual(p['weighted_positive_fraction_upper_bound'],.7)
        self.assertEqual(p['strict_horizon_NZ_station_histograms']['1'],{'0':1,'1':1})

    def test_gate_uses_positive_not_empty_coverage_and_is_incomplete_safe(self):
        r=bulk.parse_row(self.lib,xml(arrivals=''),record());tail=dict(record('54321',source='reused_tail'),outcome_status='reuse_pending')
        d=[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':1,'frame_N':1}]
        s={'new_lower_M_unique_events':1,'reused_existing_tail_events':1,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}
        self.assertFalse(aggregate.summarize([r,tail],d,s,True)['metadata_missingness_gate_pass'])
        r=bulk.parse_row(self.lib,xml(),record());self.assertTrue(aggregate.summarize([r,tail],d,s,True)['metadata_missingness_gate_pass'])
        self.assertFalse(aggregate.summarize([r,tail],d,s,False)['metadata_missingness_gate_pass'])
        with self.assertRaisesRegex(ValueError,'denominator'):aggregate.summarize([tail],d,s,True)

    def test_aggregate_contains_no_invented_ID_URL_or_pick_rows(self):
        r=bulk.parse_row(self.lib,xml(),record());body=json.dumps(aggregate.panel([r]))
        for forbidden in ('12345','smi:invented','invented.invalid','accepted_picks','2020-01-01'):self.assertNotIn(forbidden,body)

    def test_unresolved_zero_positive_and_deliberate_rejections_are_distinct(self):
        missing='<arrival><pickID>smi:invented/absent</pickID><phase>P</phase></arrival>'
        zero=bulk.parse_row(self.lib,xml(arrivals=missing),record(weight=2))
        positive=bulk.parse_row(self.lib,xml(arrivals=missing+'<arrival><pickID>smi:invented/p1</pickID><phase>P</phase></arrival>'),record(weight=3))
        rejected=bulk.parse_row(self.lib,xml(arrivals='<arrival><pickID>smi:invented/p1</pickID><phase>P</phase><timeWeight>0</timeWeight></arrival>'),record(weight=5))
        p=aggregate.panel([zero,positive,rejected]);self.assertEqual((p['unknown_NZ_P_coverage_events'],p['events_with_at_least_one_NZ_P'],p['known_zero_NZ_P_events']),(1,1,1))
        self.assertEqual(p['incomplete_associated_P_structure_events'],2);self.assertEqual(p['positive_NZ_P_with_incomplete_structure_events'],1)
        self.assertEqual(p['weighted_positive_fraction_lower_bound'],.3);self.assertEqual(p['weighted_positive_fraction_upper_bound'],.5)
        self.assertEqual(zero['base']['status'],'ok');self.assertEqual(zero['base']['nz']['stations'],0)

    def test_invalid_time_or_station_identity_zero_is_unknown(self):
        for fields in ('<time><value>2020-01-01T00:00:01</value></time><waveformID networkCode="NZ" stationCode="SYN"/>','<time><value>2020-01-01T00:00:01Z</value></time><waveformID networkCode="NZ"/>'):
            r=bulk.parse_row(self.lib,xml(pick_fields=fields),record());self.assertEqual(aggregate.panel([r])['unknown_NZ_P_coverage_events'],1)

    def test_cap_interruption_retains_all_new_and_reused_denominators(self):
        rows=[dict(record(str(10000+i)),query_url='https://invented.invalid/'+str(i)) for i in range(3)]
        plan={'rows':rows,'processing_files':{},'input_pins':{},'runtime':{},'new_denominator':3,'reused_denominator':0,'combined_denominator':3,
              'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':3,'frame_N':3}]}
        spec={'new_lower_M_unique_events':3,'reused_existing_tail_events':0,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}
        lib=self.lib
        class FakeFetcher:
            def __init__(self,*a,**kw):self.log=[];self.bytes=0
            def check(self):pass
            def fetch(self,url,name,cap):
                self.log.append({'status':'LimitReached','bytes':0});raise lib.LimitReached('invented cap')
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            with mock.patch.object(bulk,'library',return_value=lib),mock.patch.object(bulk,'load',side_effect=lambda p,*a:spec if p.name=='sample_specification.json' else {}):
                self.assertEqual(bulk.execute(plan,out,'0'*64,'1'*64,FakeFetcher),2)
            result=json.loads((out/'outcomes.json').read_text());m=json.loads((out/'manifest.json').read_text())
            self.assertEqual(len(result),3);self.assertEqual([r['outcome_status'] for r in result],['incomplete','unattempted','unattempted'])
            self.assertFalse(m['completed']);self.assertEqual(m['combined_denominator'],3);self.assertEqual(m['request_attempts'],1)

    def test_initial_reuse_failure_keeps_exact_346_plus_149_denominators_without_requests(self):
        rows=[record(str(10000+i)) for i in range(346)]+[record(str(20000+i),source='reused_tail') for i in range(149)]
        plan={'rows':rows,'processing_files':{},'input_pins':{},'runtime':{},'new_denominator':346,'reused_denominator':149,'combined_denominator':495,
              'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':346,'frame_N':346}]}
        spec={'new_lower_M_unique_events':346,'reused_existing_tail_events':149,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':312,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':277}}
        class FakeFetcher:
            def __init__(self,*a,**kw):self.log=[];self.bytes=0
            def check(self):raise ValueError('invented reuse provenance failure')
            def fetch(self,*a):raise AssertionError('no request allowed after reuse failure')
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            with mock.patch.object(bulk,'load',side_effect=lambda p,*a:spec if p.name=='sample_specification.json' else {}):
                self.assertEqual(bulk.execute(plan,out,'0'*64,'1'*64,FakeFetcher),2)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['combined_frozen_denominator'],495);self.assertEqual(summary['new_lower_M']['frozen_event_denominator'],346)
            self.assertEqual(summary['reused_tail']['frozen_event_denominator'],149);self.assertFalse(summary['metadata_missingness_gate_pass'])
            self.assertEqual(json.loads((out/'manifest.json').read_text())['request_attempts'],0)

    def test_reused_bytes_and_base_outcomes_match_before_new_fetch(self):
        body=xml(eid='54321');old=self.lib.parse_quakeml(body,'54321')
        tail=dict(record('54321',source='reused_tail'),reused_artifact={'relative_file':'raw/invented.xml','bytes':len(body),'sha256':bulk.sha(body)})
        new=record();plan={'rows':[new,tail],'processing_files':{},'input_pins':{},'runtime':{},'new_denominator':1,'reused_denominator':1,'combined_denominator':2,
          'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':1,'frame_N':1}]}
        spec={'new_lower_M_unique_events':1,'reused_existing_tail_events':1,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}
        fetched=[]
        class FakeFetcher:
            def __init__(self,*a,**kw):self.log=[];self.bytes=0
            def check(self):pass
            def fetch(self,url,name,cap):fetched.append(name);self.log.append({'status':'ok','bytes':len(xml())});self.bytes+=len(xml());return xml()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'raw').mkdir();(root/'raw'/'invented.xml').write_bytes(body)
            with mock.patch.object(bulk,'INPUT',root),mock.patch.object(bulk,'load',side_effect=lambda p,*a:spec if p.name=='sample_specification.json' else {'54321':old}):
                out=root/'out';out.mkdir();self.assertEqual(bulk.execute(plan,out,'0'*64,'1'*64,FakeFetcher),0)
                rows=json.loads((out/'outcomes.json').read_text());self.assertEqual(rows[1]['outcome_status'],'reused_verified');self.assertEqual(fetched,['12345.xml'])
                old['nz']['stations']=2;out=root/'out2';out.mkdir();self.assertEqual(bulk.execute(plan,out,'0'*64,'1'*64,FakeFetcher),2)
                self.assertEqual(fetched,['12345.xml']);self.assertFalse(json.loads((out/'manifest.json').read_text())['completed'])

    def test_whole_request_timeout_stops_and_never_passes_gate(self):
        rows=[record(str(10000+i)) for i in range(2)]
        plan={'rows':rows,'processing_files':{},'input_pins':{},'runtime':{},'new_denominator':2,'reused_denominator':0,'combined_denominator':2,
              'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':2,'frame_N':2}]}
        spec={'new_lower_M_unique_events':2,'reused_existing_tail_events':0,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':0,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':0}}
        class FakeFetcher:
            def __init__(self,*a,**kw):self.log=[];self.bytes=0
            def check(self):pass
            def fetch(self,*args):self.log.append({'status':'TimeoutError','bytes':0});raise TimeoutError('invented 20s whole-request deadline')
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            with mock.patch.object(bulk,'load',side_effect=lambda p,*a:spec if p.name=='sample_specification.json' else {}):self.assertEqual(bulk.execute(plan,out,'0'*64,'1'*64,FakeFetcher),2)
            result=json.loads((out/'outcomes.json').read_text());self.assertEqual([r['outcome_status'] for r in result],['incomplete','unattempted'])
            self.assertFalse(json.loads((out/'summary.json').read_text())['metadata_missingness_gate_pass'])


class TransportTests(unittest.TestCase):
    def test_chunk_checkpoint_precedes_native_accounting_and_survives_alarm(self):
        import transport
        lib=bulk.library()
        class Response(io.BytesIO):
            status=200;headers={}
            fp=types.SimpleNamespace(raw=types.SimpleNamespace(_sock=mock.Mock()))
            def read1(self,n):return super().read1(3)
        class Opener:
            def open(self,*a,**kw):return Response(b'abcdef')
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/'raw';raw.mkdir();f=transport.factory(lib,0)(raw,clock=lambda:0,sleep=lambda n:None,max_seconds=100,max_bytes=10,max_requests=1,request_alarm=False)
            f.opener.opener=Opener()
            with mock.patch.object(transport.signal,'pthread_sigmask',side_effect=[set(),lib.LimitReached('invented delivered pending alarm')]):
                with self.assertRaises(lib.LimitReached):f.fetch('https://invented.invalid/data','invented.xml',10)
            self.assertEqual((raw/'invented.xml').read_bytes(),b'abc');self.assertEqual(f.bytes,3)
            ledger=json.loads((raw.parent/'requests.json').read_text());self.assertEqual(ledger[0]['bytes'],3);self.assertEqual(ledger[0]['sha256'],bulk.sha(b'abc'));self.assertEqual(ledger[0]['status'],'LimitReached')
            self.assertEqual(ledger[0]['start_from_outer_seconds'],0);self.assertFalse((raw/'invented.xml.received').exists())

    def test_durable_wrapper_retains_native_caps_and_no_redirect(self):
        import transport
        lib=bulk.library()
        class Response(io.BytesIO):
            status=200;headers={'Content-Length':'5'}
            fp=types.SimpleNamespace(raw=types.SimpleNamespace(_sock=mock.Mock()))
        class Opener:
            def open(self,*a,**kw):return Response(b'abcde')
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/'raw';raw.mkdir();f=transport.factory(lib,0)(raw,clock=lambda:0,sleep=lambda n:None,max_seconds=100,max_bytes=4,max_requests=1,request_alarm=False);f.opener.opener=Opener()
            with self.assertRaises(lib.LimitReached):f.fetch('https://invented.invalid/data','invented.xml',4)
            self.assertEqual(f.bytes,0);self.assertEqual(len(f.log),1);self.assertEqual((raw/'invented.xml').read_bytes(),b'')
            with self.assertRaises(lib.LimitReached):f.fetch('https://invented.invalid/data','replacement.xml',4)
            self.assertEqual(len(f.log),1)

    def test_reconciliation_uses_pre_request_total_after_native_increment(self):
        import transport
        lib=bulk.library()
        def interrupted_native(owner,url,name,cap):
            owner.log.append({'file':name,'status':'LimitReached','bytes':0});owner.last_start=0
            owner.received_file.write_bytes(b'abc');owner.active_bytes=3;owner.active_hash.update(b'abc')
            owner.bytes+=3
            raise lib.LimitReached('invented alarm after native increment before extend')
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/'raw';raw.mkdir();f=transport.factory(lib,0)(raw,max_seconds=100,max_bytes=10,max_requests=1,request_alarm=False);f.bytes=2
            with mock.patch.object(lib.Fetcher,'fetch',interrupted_native):
                with self.assertRaises(lib.LimitReached):f.fetch('https://invented.invalid/data','invented.xml',10)
            self.assertEqual(f.bytes,5);self.assertEqual(f.log[0]['bytes'],3);self.assertEqual((raw/'invented.xml').read_bytes(),b'abc')

    def test_native_finalization_uses_atomic_persistence_hook(self):
        import transport
        lib=bulk.library();transport.factory(lib,0)
        self.assertIs(lib.dump,transport.checkpoint)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'requests.json';p.write_text('previous')
            with mock.patch.object(Path,'replace',side_effect=RuntimeError('invented kill before atomic rename')):
                with self.assertRaises(RuntimeError):lib.dump(p,[{'status':'started'}])
            self.assertEqual(p.read_text(),'previous');self.assertTrue(p.with_name('requests.json.temporary.'+str(transport.os.getpid())).exists())

    def test_corrected_ledger_is_durable_before_sidecar_retirement(self):
        import transport
        lib=bulk.library()
        def interrupted_native(owner,url,name,cap):
            owner.log.append({'file':name,'status':'LimitReached','bytes':0});owner.last_start=0
            owner.received_file.write_bytes(b'abc');owner.active_bytes=3;owner.active_hash.update(b'abc');owner.bytes+=3
            raise lib.LimitReached('invented native counter-before-content alarm')
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/'raw';raw.mkdir();f=transport.factory(lib,0)(raw,max_seconds=100,max_bytes=10,max_requests=1,request_alarm=False)
            def kill_at_rename(source,target):
                if source.suffix=='.received':
                    ledger=json.loads((raw.parent/'requests.json').read_text());self.assertEqual(ledger[0]['bytes'],3);self.assertEqual(ledger[0]['sha256'],bulk.sha(b'abc'))
                    raise RuntimeError('invented hard kill before sidecar rename')
                return original_replace(source,target)
            original_replace=Path.replace
            with mock.patch.object(lib.Fetcher,'fetch',interrupted_native),mock.patch.object(Path,'replace',kill_at_rename):
                with self.assertRaisesRegex(RuntimeError,'hard kill'):f.fetch('https://invented.invalid/data','invented.xml',10)
            self.assertEqual((raw/'invented.xml.received').read_bytes(),b'abc')

    def test_read_handoff_is_masked_and_repeated_recvs_use_absolute_timeout(self):
        import transport
        lib=bulk.library();now=[0];timeouts=[];mask_seen=[]
        class Socket:
            def settimeout(self,value):self.timeout=value;timeouts.append(value)
            def recv_into(self,*args):
                now[0]+=min(12,self.timeout)
                if self.timeout<12:raise TimeoutError('invented socket absolute timeout')
                return 1
        class Response(io.BytesIO):
            status=200;headers={}
            fp=types.SimpleNamespace(raw=types.SimpleNamespace(_sock=Socket()))
            def read1(self,n):
                mask_seen.append(transport.signal.pthread_sigmask(transport.signal.SIG_BLOCK,set()))
                self.fp.raw._sock.recv_into(bytearray(1));self.fp.raw._sock.recv_into(bytearray(1))
                return b'body'
        class Opener:
            def open(self,*a,**kw):return Response()
        with tempfile.TemporaryDirectory() as temp:
            raw=Path(temp)/'raw';raw.mkdir();f=transport.factory(lib,0)(raw,clock=lambda:now[0],sleep=lambda n:None,max_seconds=100,max_bytes=10,max_requests=1,request_alarm=False);f.opener.opener=Opener()
            with self.assertRaises(TimeoutError):f.fetch('https://invented.invalid/data','invented.xml',10)
            self.assertEqual(timeouts,[20,8]);self.assertEqual(now[0],20);self.assertTrue({transport.signal.SIGALRM,transport.signal.SIGTERM}<=mask_seen[0]);self.assertEqual(f.bytes,0)


class GateTests(unittest.TestCase):
    def test_generated_artifact_stream_hash_uses_separate_ceiling(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'outcomes.json';p.write_bytes(b'12345')
            self.assertEqual(bulk.artifact_pin(p,5),{'bytes':5,'sha256':bulk.sha(b'12345')})
            with self.assertRaisesRegex(ValueError,'ceiling'):bulk.artifact_pin(p,4)

    def test_hard_cleanup_watchdog_kills_group_and_exits_without_wait_extension(self):
        process=mock.Mock(pid=987654);process.poll.return_value=None;handlers=[]
        with mock.patch.object(bulk.signal,'signal',side_effect=lambda sig,fn:handlers.append(fn)),mock.patch.object(bulk.signal,'setitimer') as timer,mock.patch.object(bulk.os,'killpg') as kill,mock.patch.object(bulk.os,'_exit') as stop:
            bulk.hard_watchdog(bulk.time.monotonic()+.01,process);handlers[0](None,None)
            kill.assert_called_once_with(process.pid,bulk.signal.SIGKILL);stop.assert_called_once_with(2);timer.assert_called_once();process.wait.assert_not_called()
    def test_output_escape_symlink_and_oversize_input_rejected(self):
        with self.assertRaisesRegex(ValueError,'inside'):bulk.local('/tmp/outside-bulk-fixture')
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'f';p.write_bytes(b'123');q=Path(temp)/'l';q.symlink_to(p)
            with self.assertRaisesRegex(ValueError,'size'):bulk.read(p,2)
            with self.assertRaisesRegex(ValueError,'nonsymlink'):bulk.read(q,4)

    def test_missing_receipt_is_rejected_before_output_reservation(self):
        with tempfile.TemporaryDirectory(dir=bulk.BASE) as temp:
            p=Path(temp)/'plan.json';p.write_text('{}');out=Path(temp)/'never-created'
            with mock.patch.object(bulk,'validate',side_effect=ValueError('invented missing receipt')):
                with self.assertRaisesRegex(ValueError,'receipt'):bulk.collect(p,p,out)
            self.assertFalse(out.exists())

    def test_receipt_exact_binding_and_plan_replay(self):
        plan={'processing_files':{'bulk.py':'2'*64},'input_pins':{},'runtime':{}}
        receipt={'version':'geonet-bulk-parent-receipt-v1','acquisition_authorized':True,'code_only_review_clean':True,'git_freeze_commit':'a'*40,
                 'processing_files':plan['processing_files'],'library_sha256':bulk.LIBRARY_SHA,'input_pins':{},'runtime':{}}
        with tempfile.TemporaryDirectory(dir=bulk.BASE) as temp:
            p=Path(temp)/'p';r=Path(temp)/'r';bulk.dump(p,plan);receipt['plan_sha256']=bulk.sha(p.read_bytes());bulk.dump(r,receipt)
            with mock.patch.object(bulk,'local',side_effect=lambda x:Path(x)),mock.patch.object(bulk,'make_plan',return_value=plan):
                self.assertEqual(bulk.validate(p,r)[0],plan)
                receipt['acquisition_authorized']=False;bulk.dump(r,receipt)
                with self.assertRaisesRegex(ValueError,'receipt'):bulk.validate(p,r)
                receipt['acquisition_authorized']=True;receipt['runtime']={'tampered':True};bulk.dump(r,receipt)
                with self.assertRaisesRegex(ValueError,'runtime'):bulk.validate(p,r)

    def test_outer_timeout_recomputes_incomplete_checkpoint_with_denominators(self):
        rows=[record()];plan={'rows':rows,'new_denominator':1,'reused_denominator':0,'combined_denominator':1,
                            'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':1,'frame_N':1}]}
        spec={'new_lower_M_unique_events':1,'reused_existing_tail_events':0,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}
        process=mock.Mock(pid=987654);process.wait.side_effect=[subprocess_timeout(),0];process.poll.side_effect=[None,0]
        cleanup_timer=[]
        def fake_load(p,*a):
            if p.name=='outcomes.json':cleanup_timer.append(bulk.signal.getitimer(bulk.signal.ITIMER_REAL)[0])
            return spec if p.name=='sample_specification.json' else json.loads(p.read_text())
        with tempfile.TemporaryDirectory(dir=bulk.BASE) as temp:
            out=Path(temp)/'new'
            with mock.patch.object(bulk,'local',side_effect=lambda p:Path(p)),mock.patch.object(bulk,'validate',return_value=(plan,'0'*64,'1'*64)),mock.patch.object(bulk,'load',side_effect=fake_load),mock.patch.object(bulk.subprocess,'Popen',return_value=process),mock.patch.object(bulk.os,'killpg') as kill:
                with self.assertRaises(bulk.subprocess.TimeoutExpired):bulk.collect(Path(temp)/'p',Path(temp)/'r',out)
                kill.assert_called_once();self.assertEqual(len(json.loads((out/'outcomes.json').read_text())),1)
                self.assertFalse(json.loads((out/'summary.json').read_text())['completed']);self.assertEqual(json.loads((out/'outer_interruption.json').read_text())['combined_denominator'],1)
                self.assertTrue(cleanup_timer and all(t>0 for t in cleanup_timer))
                recovered=json.loads((out/'manifest.json').read_text());self.assertTrue(recovered['artifact_pins_incomplete']);self.assertEqual(recovered['files'],{})

    def test_recovery_write_failure_still_terminates_live_child_before_timer_cancel(self):
        rows=[record()];plan={'rows':rows,'new_denominator':1,'reused_denominator':0,'combined_denominator':1,
                            'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':1,'frame_N':1}]}
        spec={'new_lower_M_unique_events':1,'reused_existing_tail_events':0,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}
        process=mock.Mock(pid=987654);process.wait.side_effect=[subprocess_timeout(),0];process.poll.return_value=None
        original_dump=bulk.dump;timer_seen=[]
        def fail_recovery(p,obj):
            if p.name=='outer_interruption.json':raise FileNotFoundError('invented failed recovery rename')
            return original_dump(p,obj)
        def kill_with_active_timer(*args):timer_seen.append(bulk.signal.getitimer(bulk.signal.ITIMER_REAL)[0])
        with tempfile.TemporaryDirectory(dir=bulk.BASE) as temp:
            out=Path(temp)/'new'
            with mock.patch.object(bulk,'local',side_effect=lambda p:Path(p)),mock.patch.object(bulk,'validate',return_value=(plan,'0'*64,'1'*64)),mock.patch.object(bulk,'load',return_value=spec),mock.patch.object(bulk,'dump',side_effect=fail_recovery),mock.patch.object(bulk.subprocess,'Popen',return_value=process),mock.patch.object(bulk.os,'killpg',side_effect=kill_with_active_timer) as kill:
                with self.assertRaisesRegex(FileNotFoundError,'recovery'):bulk.collect(Path(temp)/'p',Path(temp)/'r',out)
                kill.assert_called_once_with(process.pid,bulk.signal.SIGKILL);self.assertEqual(process.wait.call_count,2);self.assertTrue(timer_seen[0]>0)
            self.assertEqual(bulk.signal.getitimer(bulk.signal.ITIMER_REAL)[0],0)

    def test_parent_sigterm_enters_bounded_cleanup_and_restores_handlers_after_child_exit(self):
        rows=[record()];plan={'rows':rows,'new_denominator':1,'reused_denominator':0,'combined_denominator':1,
                            'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':1,'frame_N':1}]}
        spec={'new_lower_M_unique_events':1,'reused_existing_tail_events':0,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}
        process=mock.Mock(pid=987654);process.poll.side_effect=[None,0]
        prior_term=bulk.signal.getsignal(bulk.signal.SIGTERM);prior_alarm=bulk.signal.getsignal(bulk.signal.SIGALRM)
        def wait(*args,**kwargs):
            if process.wait.call_count==1:
                self.assertIs(bulk.signal.getsignal(bulk.signal.SIGTERM),bulk.parent_terminate)
                bulk.os.kill(bulk.os.getpid(),bulk.signal.SIGTERM)
                self.fail('SIGTERM must enter cleanup')
            self.assertIs(bulk.signal.getsignal(bulk.signal.SIGTERM),bulk.signal.SIG_IGN)
            self.assertGreater(bulk.signal.getitimer(bulk.signal.ITIMER_REAL)[0],0)
            return 0
        process.wait.side_effect=wait
        with tempfile.TemporaryDirectory(dir=bulk.BASE) as temp:
            out=Path(temp)/'new'
            with mock.patch.object(bulk,'local',side_effect=lambda p:Path(p)),mock.patch.object(bulk,'validate',return_value=(plan,'0'*64,'1'*64)),mock.patch.object(bulk.subprocess,'Popen',return_value=process),mock.patch.object(bulk.os,'killpg') as kill,mock.patch.object(bulk,'load',side_effect=lambda p,*a:spec if p.name=='sample_specification.json' else json.loads(p.read_text())):
                with self.assertRaisesRegex(bulk.Deadline,'SIGTERM'):bulk.collect(Path(temp)/'p',Path(temp)/'r',out)
                kill.assert_called_once_with(process.pid,bulk.signal.SIGTERM)
                self.assertFalse(json.loads((out/'summary.json').read_text())['completed'])
                self.assertEqual(json.loads((out/'outer_interruption.json').read_text())['combined_denominator'],1)
            self.assertIs(bulk.signal.getsignal(bulk.signal.SIGTERM),prior_term)
            self.assertIs(bulk.signal.getsignal(bulk.signal.SIGALRM),prior_alarm)

    def test_forced_kill_is_awaited_before_worker_checkpoint_reconciliation(self):
        rows=[record()];plan={'rows':rows,'new_denominator':1,'reused_denominator':0,'combined_denominator':1,
                            'denominators':[{'candidate_calendar_partition':'test2018_2024','Mw_band':'[4,4.5)','sample_n':1,'frame_N':1}]}
        spec={'new_lower_M_unique_events':1,'reused_existing_tail_events':0,'missingness_gate':{'minimum_successfully_resolved_preferred_origin_events':1,'minimum_events_with_at_least_one_accepted_NZ_associated_P_pick':1}}
        process=mock.Mock(pid=987654);process.wait.side_effect=[subprocess_timeout(),subprocess_timeout(),0];process.poll.side_effect=[None,0]
        def checked_load(p,*args):
            if p.name in ('manifest.json','outcomes.json','requests.json'):
                self.assertEqual(process.wait.call_count,3)
                self.assertGreater(bulk.signal.getitimer(bulk.signal.ITIMER_REAL)[0],0)
            return spec if p.name=='sample_specification.json' else json.loads(p.read_text())
        with tempfile.TemporaryDirectory(dir=bulk.BASE) as temp:
            out=Path(temp)/'new'
            with mock.patch.object(bulk,'local',side_effect=lambda p:Path(p)),mock.patch.object(bulk,'validate',return_value=(plan,'0'*64,'1'*64)),mock.patch.object(bulk,'load',side_effect=checked_load),mock.patch.object(bulk.subprocess,'Popen',return_value=process),mock.patch.object(bulk.os,'killpg') as kill:
                with self.assertRaises(bulk.subprocess.TimeoutExpired):bulk.collect(Path(temp)/'p',Path(temp)/'r',out)
                self.assertEqual(kill.call_args_list,[mock.call(process.pid,bulk.signal.SIGTERM),mock.call(process.pid,bulk.signal.SIGKILL)])
                self.assertTrue(json.loads((out/'manifest.json').read_text())['artifact_pins_incomplete'])


def subprocess_timeout():return bulk.subprocess.TimeoutExpired('invented worker',1800)


if __name__=='__main__':unittest.main(verbosity=2)

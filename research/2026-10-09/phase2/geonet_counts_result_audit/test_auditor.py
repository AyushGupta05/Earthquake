"""Invented-only contract tests; no task-owned run output or raw data reads."""
import copy
import io
import json
import math
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import auditor as a


TARGET = dict(network='NZ', station='SYNTH', location='', prefix='HH', pick_ns=5*a.NS,
              queryable=True, unqueryable_reason=None)


def xml(codes=('HHE', 'HHN', 'HHZ'), end=None, extra=''):
    parts = []
    for i, code in enumerate(codes):
        attrs = 'code="'+code+'" locationCode="" startDate="1969-01-01T00:00:00Z"'
        if end is not None:
            attrs += ' endDate="'+a.request_iso(end)+'"'
        parts.append('<Channel '+attrs+'><SampleRate>2</SampleRate><Azimuth>'+str(90 if i==0 else 0)+
                     '</Azimuth><Dip>'+str(-90 if code.endswith('Z') else 0)+
                     '</Dip><Latitude>-40</Latitude><Longitude>175</Longitude><Elevation>10</Elevation></Channel>')
    return ('<FDSNStationXML xmlns="http://www.fdsn.org/xml/station/1"><Network code="NZ"><Station code="SYNTH">'+
            ''.join(parts)+extra+'</Station></Network></FDSNStationXML>').encode()


def event(eid='invented0', targets=None):
    targets = [dict(TARGET)] if targets is None else targets
    return dict(event_id=eid, Mw_band='<3.5', candidate_calendar_partition=a.PARTITIONS[0],
                P_status='ok', incomplete_associated_P_structure=False, t0_ns=5*a.NS,
                targets=targets, current_station_masks={str(h):[t['station'] for t in targets] for h in a.HORIZONS})


def piece(values, start=0, rate=2):
    return dict(data=values, start_ns=start, sample_rate=rate)


def invented_response_body(rate=100, frequency=1, stages=True, codes=('HHE','HHN','HHZ')):
    from obspy import UTCDateTime
    from obspy.core.inventory import Inventory, Network, Station, Channel, Site
    from obspy.core.inventory.response import Response, InstrumentSensitivity, PolesZerosResponseStage
    channels=[]
    for i,code in enumerate(codes):
        response=Response(instrument_sensitivity=InstrumentSensitivity(10,frequency,'M/S','COUNTS'),
                          response_stages=[PolesZerosResponseStage(1,10,frequency,'M/S','COUNTS',
                              'LAPLACE (RADIANS/SECOND)',1,[],[],1)] if stages else [])
        channels.append(Channel(code,'',-40,175,10,0,azimuth=90 if i==0 else 0,dip=-90 if i==2 else 0,
                                sample_rate=rate,start_date=UTCDateTime(-86400),response=response))
    inv=Inventory([Network('NZ',stations=[Station('SYNTH',-40,175,10,channels=channels,site=Site('invented'))])],'invented')
    buffer=io.BytesIO();inv.write(buffer,format='STATIONXML')
    return buffer.getvalue()


class ToyBackend:
    def __init__(self, declarations=None, actual=None, header_bad=(), decode_bad=()):
        self.declarations = declarations or {}
        self.actual_sizes = actual or {}
        self.header_bad, self.decode_bad = set(header_bad), set(decode_bad)

    def headers(self, body):
        if body in self.header_bad:
            raise RuntimeError('invented bad header')
        return body

    def declared(self, stream):
        return self.declarations.get(stream, 10)

    def decode(self, body):
        if body in self.decode_bad:
            raise RuntimeError('invented decoder failure')
        return body

    def actual(self, stream):
        return self.actual_sizes.get(stream, 40)

    def pieces(self, stream, target, code, deadline):
        return [piece(list(range(20)))]


class PrefixTests(unittest.TestCase):
    def test_exact_timestamp_fraction_and_offset(self):
        self.assertEqual(a.utc_ns('1970-01-01T01:00:00.123456789+01:00'),123456789)
        self.assertEqual(a.utc_ns('1969-12-31T23:59:59.9Z'),-100000000)
        with self.assertRaises(a.AuditError):
            a.utc_ns('1970-01-01T00:00:00')

    def test_timezone_offset_component_ranges(self):
        for offset in ('+00:60','-00:99','+24:00'):
            with self.subTest(offset=offset),self.assertRaises(a.AuditError):
                a.utc_ns('1970-01-01T00:00:00'+offset)
        body=xml().replace(b'1969-01-01T00:00:00Z',b'1969-01-01T00:00:00+00:60')
        rows=a.stationxml(body)
        self.assertTrue(all('channel.startDate' in r['timestamp_errors'] for r in rows))
        with self.assertRaises(ValueError):a.epoch_triplet(rows,TARGET,0,6*a.NS)

    def test_strict_right_edge_and_nonfinite_future(self):
        result=a.prefix_component([piece([0,1,2,3,math.nan])],0,2*a.NS,2)
        self.assertTrue(result['available'])
        self.assertEqual(result['samples'],4)
        self.assertTrue(result['finite'])

    def test_noninteger_rate_rational_crop(self):
        result=a.prefix_component([piece([1,2,3,4,math.nan],rate=2.5)],0,1600000000,2.5)
        self.assertEqual(result['samples'],4)
        self.assertTrue(result['available'])

    def test_one_missing_edge_sample_cannot_pass(self):
        result=a.prefix_component([piece([1,2,3],start=500000000)],0,2*a.NS,2)
        self.assertFalse(result['edge_coverage'])
        self.assertFalse(result['available'])

    def test_fragment_invariant_extreme_run(self):
        values=[0,1]+[9]*8+[2,3]
        whole=a.prefix_component([piece(values)],0,6*a.NS,2)
        split=a.prefix_component([piece(values[:7]),piece(values[7:],start=3500000000)],0,6*a.NS,2)
        self.assertEqual(whole,split)
        self.assertEqual(whole['longest_prefix_extreme_run'],8)
        self.assertTrue(whole['available'])
        self.assertFalse(whole['clipping_screen_passed'])

    def test_gap_breaks_run_and_overlap_detected(self):
        gap=a.prefix_component([piece([0,9,9,9,9]),piece([9,9,9,9,1],start=3*a.NS)],0,5500000000,2)
        self.assertEqual(gap['gaps'],1)
        self.assertEqual(gap['longest_prefix_extreme_run'],4)
        overlap=a.prefix_component([piece([0,1,2,3]),piece([1,2,3],start=a.NS)],0,2500000000,2)
        self.assertGreater(overlap['overlaps'],0)
        self.assertFalse(overlap['available'])

    def test_cross_component_lattice_and_rate(self):
        good=a.prefix_component([piece(list(range(12)))],0,6*a.NS,2)
        shifted=a.prefix_component([piece(list(range(12)),start=1000000)],0,6*a.NS,2)
        self.assertFalse(a.aligned({'E':good,'N':good,'Z':shifted},2))
        bad=a.prefix_component([piece(list(range(24)),rate=4)],0,6*a.NS,2)
        self.assertFalse(bad['sample_rate_matches'])

    def test_nonfinite_and_flat_are_distinct(self):
        flat=a.prefix_component([piece([5]*12)],0,6*a.NS,2)
        self.assertTrue(flat['available']);self.assertTrue(flat['flatline'])
        bad=a.prefix_component([piece([1,2,math.inf]+list(range(9)))],0,6*a.NS,2)
        self.assertFalse(bad['available']);self.assertFalse(bad['finite'])

    def test_short_flat_diagnostic_requires_eight_sample_run(self):
        short=a.prefix_component([piece([5]*6,rate=1)],0,6*a.NS,1)
        self.assertTrue(short['available']);self.assertTrue(short['flatline'])
        self.assertEqual(short['longest_prefix_extreme_run'],6)
        self.assertFalse(short['clipping_candidate']);self.assertTrue(short['clipping_screen_passed'])

    def test_wholly_future_invalid_rate_ignored(self):
        rows=[piece(list(range(12))),piece([math.nan],start=6*a.NS,rate=math.nan)]
        self.assertTrue(a.prefix_component(rows,0,6*a.NS,2)['available'])


class EpochTests(unittest.TestCase):
    def test_enz_precedence_even_if_12z_also_present(self):
        rows=a.stationxml(xml()+b'')
        other=a.stationxml(xml(('HH1','HH2','HHZ')))
        rows+=other[:2]
        self.assertEqual([r['code'] for r in a.epoch_triplet(rows,TARGET,0,6*a.NS)],['HHE','HHN','HHZ'])

    def test_future_epoch_not_earlier_failure(self):
        future='<Channel code="HHE" locationCode="" startDate="1970-01-01T00:00:07Z"><SampleRate>NaN</SampleRate></Channel>'
        rows=a.stationxml(xml(end=7*a.NS,extra=future))
        self.assertEqual(len(a.epoch_triplet(rows,TARGET,0,6*a.NS)),3)
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            a.epoch_triplet(rows,TARGET,0,8*a.NS)

    def test_future_invalid_end_isolated_until_relevant(self):
        future='<Channel code="HHE" locationCode="" startDate="1970-01-01T00:00:07Z" endDate="invalid"><SampleRate>2</SampleRate></Channel>'
        rows=a.stationxml(xml(end=7*a.NS,extra=future))
        self.assertEqual(len(a.epoch_triplet(rows,TARGET,0,6*a.NS)),3)
        with self.assertRaises(ValueError):a.epoch_triplet(rows,TARGET,0,8*a.NS)
        invalid=xml().replace(b'startDate="1969-01-01T00:00:00Z"',b'startDate="invalid"')
        with self.assertRaisesRegex(ValueError,'timestamp'):
            a.epoch_triplet(a.stationxml(invalid),TARGET,0,6*a.NS)

    def test_future_timestamp_overflow_isolated_until_relevant(self):
        future='<Channel code="HHE" locationCode="" startDate="1970-01-01T00:00:07Z" endDate="9999-12-31T23:59:59-01:00"><SampleRate>2</SampleRate></Channel>'
        rows=a.stationxml(xml(end=7*a.NS,extra=future))
        self.assertEqual(len(a.epoch_triplet(rows,TARGET,0,6*a.NS)),3)
        self.assertEqual(rows[-1]['timestamp_errors'],['channel.endDate'])
        with self.assertRaises(ValueError):a.epoch_triplet(rows,TARGET,0,8*a.NS)

    def test_network_station_epoch_intersection(self):
        body=xml().replace(b'<Network code="NZ">',b'<Network code="NZ" startDate="1970-01-01T00:00:01Z">')
        with self.assertRaisesRegex(ValueError,'span prefix'):
            a.epoch_triplet(a.stationxml(body),TARGET,0,6*a.NS)

    def test_cached_response_join_preserves_own_channel_dates(self):
        body=xml().replace(b'<Station code="SYNTH">',b'<Station code="SYNTH" startDate="1970-01-01T00:00:00Z">')
        different=body.replace(b'1969-01-01T00:00:00Z',b'1968-01-01T00:00:00Z')
        original=a.epoch_triplet(a.stationxml(body),TARGET,0,6*a.NS)
        changed=a.epoch_triplet(a.stationxml(different),TARGET,0,6*a.NS)
        self.assertEqual(original[0]['start_ns'],changed[0]['start_ns'])
        self.assertNotEqual(original[0]['channel_start_ns'],changed[0]['channel_start_ns'])
        with self.assertRaisesRegex(ValueError,'differs'):a.selected_response_xml(different,original)
        answer=a.qualify(event(),TARGET,body,b'good',ToyBackend(),different)
        self.assertTrue(answer['1']['count_valid'])
        self.assertEqual(a.response_failure_categories(answer['1']),['cached_response_metadata_join'])

    def test_missing_start_and_orientation(self):
        rows=a.stationxml(xml().replace(b' startDate="1969-01-01T00:00:00Z"',b''))
        with self.assertRaises(ValueError):a.epoch_triplet(rows,TARGET,0,6*a.NS)
        rows=a.stationxml(xml());rows[1]['azimuth']=80
        with self.assertRaisesRegex(ValueError,'orientation'):
            a.epoch_triplet(rows,TARGET,0,6*a.NS)

    def test_selected_orientation_ranges_before_tolerance(self):
        for index,field,value in ((2,'dip',100),(2,'dip',-100),(0,'azimuth',450),(1,'azimuth',-360)):
            rows=a.stationxml(xml());rows[index][field]=value
            with self.subTest(field=field,value=value),self.assertRaisesRegex(ValueError,'StationXML range'):
                a.epoch_triplet(rows,TARGET,0,6*a.NS)
        rows=a.stationxml(xml());rows[1]['azimuth']=360
        self.assertEqual(len(a.epoch_triplet(rows,TARGET,0,6*a.NS)),3)

    def test_xml_unsafe_and_duplicate_numeric(self):
        with self.assertRaises(a.AuditError):a.stationxml(b'<!DOCTYPE x>'+xml())
        with self.assertRaises(a.AuditError):a.stationxml(xml()+b'\0')
        rows=a.stationxml(xml().replace(b'<SampleRate>2</SampleRate>',b'<SampleRate>2</SampleRate><SampleRate>2</SampleRate>'))
        with self.assertRaisesRegex(ValueError,'invalid rate'):
            a.epoch_triplet(rows,TARGET,0,6*a.NS)


class MemoryTests(unittest.TestCase):
    def entries(self, root, names, source='exact_cache'):
        answer=[]
        for i,name in enumerate(names):
            p=Path(root)/str(i);p.write_bytes(name)
            answer.append(dict(key=str(i),source=source,path=str(p),pin={'bytes':len(name),'sha256':a.sha(name)}))
        return answer

    def test_combined_declarations_including_nine_caches(self):
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'x']*10);entries[0]['source']='new_batch'
            a.BlockDecoder(entries,ToyBackend(),cap=800)
            with self.assertRaises(a.ResourceStop):a.BlockDecoder(entries,ToyBackend(),cap=799)

    def test_actual_sum_not_only_each_array(self):
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'a',b'b'])
            d=a.BlockDecoder(entries,ToyBackend(declarations={b'a':1,b'b':1},actual={b'a':40,b'b':40}),cap=79)
            d.decode('0')
            with self.assertRaises(a.ResourceStop):d.decode('1')

    def test_pin_changed_and_duplicate_decode_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'x']);d=a.BlockDecoder(entries,ToyBackend())
            d.decode('0')
            with self.assertRaises(a.AuditError):d.decode('0')
            d=a.BlockDecoder(entries,ToyBackend());Path(entries[0]['path']).write_bytes(b'y')
            with self.assertRaises(a.AuditError):d.decode('0')

    def test_artifact_access_race_stops_fresh_and_cached_replay(self):
        original=Path.open
        with tempfile.TemporaryDirectory() as root:
            for source in ('new_batch','exact_cache'):
                entries=self.entries(root,[b'good'],source=source)
                if source=='exact_cache':entries[0]['key']='invented0|SYNTH'
                reads=0
                def changing_open(path,*args,**kwargs):
                    nonlocal reads
                    if str(path)==entries[0]['path']:
                        reads+=1
                        if reads==2:raise PermissionError(a.errno.EACCES,'invented access change')
                    return original(path,*args,**kwargs)
                with self.subTest(source=source),mock.patch.object(Path,'open',changing_open):
                    with self.assertRaises(a.AuditError):
                        a.qualification_batch([event()],entries,{'invented0|SYNTH':xml()},{},ToyBackend())
                self.assertEqual(reads,2)
            p=Path(root)/'ordinary';p.write_bytes(b'x')
            with mock.patch.object(Path,'open',side_effect=OSError(a.errno.ENOMEM,'invented exhaustion')):
                with self.assertRaises(a.ResourceStop):a.bounded_body(p,1)

    def test_bad_new_headers_do_not_erase_valid_cache(self):
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'bad',b'good']);entries[0]['source']='new_batch';entries[1]['key']='invented0|SYNTH'
            rows=a.qualification_batch([event()],entries,{'invented0|SYNTH':xml()},{},ToyBackend(header_bad={b'bad'}))
            self.assertEqual(rows[0]['status'],'audited')
            self.assertTrue(rows[0]['horizons']['1']['count_valid'])

    def test_header_resource_stop_is_never_engineering_absence(self):
        class HeaderStop(ToyBackend):
            def headers(self,body):raise a.ResourceStop('invented header stop')
        class DeclarationStop(ToyBackend):
            def declared(self,stream):raise a.ResourceStop('invented declaration stop')
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'good'])
            for backend in (HeaderStop(),DeclarationStop()):
                with self.subTest(backend=type(backend).__name__),self.assertRaises(a.ResourceStop):
                    a.BlockDecoder(entries,backend)

    def test_wrapped_header_declaration_and_decode_allocation_stop(self):
        class HeaderFailure(ToyBackend):
            def headers(self,body):raise RuntimeError('Cannot allocate memory')
        class DeclarationFailure(ToyBackend):
            def declared(self,stream):raise ValueError('unable to allocate native header')
        class DecodeFailure(ToyBackend):
            def decode(self,body):
                if body==b'badnative':raise RuntimeError('malloc failed')
                return super().decode(body)
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'good'])
            for backend in (HeaderFailure(),DeclarationFailure()):
                with self.subTest(backend=type(backend).__name__),self.assertRaises(a.ResourceStop):
                    a.BlockDecoder(entries,backend)
            for fresh,cache in ((b'badnative',b'good'),(b'good',b'badnative')):
                entries=self.entries(root,[fresh,cache]);entries[0]['source']='new_batch';entries[1]['key']='invented0|SYNTH'
                with self.subTest(fresh=fresh,cache=cache),self.assertRaises(a.ResourceStop):
                    a.qualification_batch([event()],entries,{'invented0|SYNTH':xml()},{},DecodeFailure())

    def test_no_alternate_new_body_on_cached_decode_failure(self):
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'good',b'bad']);entries[0]['source']='new_batch';entries[1]['key']='invented0|SYNTH'
            rows=a.qualification_batch([event()],entries,{'invented0|SYNTH':xml()},{},ToyBackend(decode_bad={b'bad'}))
            self.assertEqual(rows[0]['status'],'unresolved_engineering')
            self.assertFalse(rows[0]['horizons']['1']['count_valid'])

    def test_wrong_root_metadata_is_target_local_failure(self):
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'good'],source='new_batch')
            rows=a.qualification_batch([event(),event('invented1')],entries,
                                       {'invented0|SYNTH':b'<html/>','invented1|SYNTH':xml()},
                                       {},ToyBackend())
            self.assertEqual(rows[0]['status'],'unresolved_engineering')
            self.assertEqual(rows[0]['channel_parser_status'],'parse_failed')
            self.assertFalse(rows[0]['horizons']['1']['count_valid'])
            self.assertTrue(rows[1]['horizons']['1']['count_valid'])

    def test_public_stage_counters_distinguish_header_decode_and_parser(self):
        with tempfile.TemporaryDirectory() as root:
            entries=self.entries(root,[b'badheader',b'baddecode',b'good',b'good'])
            entries[0].update(source='new_batch',key='new')
            for i in range(1,4):entries[i]['key']=f'invented{i}|SYNTH'
            events=[event('invented'+str(i)) for i in range(4)]
            channels={f'invented{i}|SYNTH':b'<html/>' if i==2 else xml() for i in range(4)}
            rows=a.qualification_batch(events,entries,channels,{},ToyBackend(header_bad={b'badheader'},decode_bad={b'baddecode'}))
            events += [event('invented'+str(i),targets=[]) for i in range(4,96)]
            _,summary=a.aggregate(events,rows,False)
            self.assertEqual(summary['target_denominator'],4)
            self.assertEqual(summary['waveform_header_status'],{'header_failed':1,'header_ok':3})
            self.assertEqual(summary['waveform_decoder_status'],{'decode_failed':1,'decoded':2,'not_attempted_header_failed':1})
            self.assertEqual(summary['channel_parser_status'],{'not_attempted_waveform_failure':2,'parse_failed':1,'parsed':1})
            self.assertEqual(summary['events']['horizons']['1']['count_available'],1)


class SelectionTests(unittest.TestCase):
    def test_hash_selection_retains_missing_metadata(self):
        rows=[]
        for pi,p in enumerate(a.PARTITIONS):
            for bi,b in enumerate(a.LOWER_BANDS):
                n=24 if (pi,bi)==(0,0) else 23
                for i in range(n):rows.append(dict(event_id=f'inventedlower{pi}_{bi}_{i}',source='new_lower_M',candidate_calendar_partition=p,Mw_band=b,mw=3.0))
            for i in range(20):rows.append(dict(event_id=f'inventedlarge{pi}_{i}',source='reused_tail',candidate_calendar_partition=p,mw=6.1))
            for i in range(29 if pi==2 else 30):rows.append(dict(event_id=f'inventedtail{pi}_{i}',source='reused_tail',candidate_calendar_partition=p,mw=5.7))
        frozen=a.list_digest(sorted(r['event_id'] for r in rows if r['source']=='new_lower_M'))
        outcomes={r['event_id']:{'base':{'status':'missing_or_ambiguous_preferred_origin'}} for r in rows}
        selected=a.select96(rows,outcomes,frozen)
        self.assertEqual(selected,a.select96(list(reversed(rows)),outcomes,frozen))
        self.assertEqual(len(selected),96)
        self.assertEqual(sum(e['mw']>=6 for e in selected),60)
        self.assertTrue(all(e['targets']==[] for e in selected))
        self.assertEqual(sum(e['P_status']=='missing_or_ambiguous_preferred_origin' for e in selected),96)
        with self.assertRaises(a.AuditError):a.select96(rows,outcomes)

    def test_current_cap_tie_strict_boundary(self):
        picks=[dict(network='NZ',station=f'S{i}',location='',channel='HHZ',pick_id=f'p{i}',time=a.request_iso(5*a.NS+i*100000000)) for i in range(10)]
        picks.append(dict(picks[0],location='01',channel='HNZ',pick_id='earlier_lex'))
        picks.append(dict(network='NZ',station='LATE',location='',channel='HHZ',pick_id='boundary',time=a.request_iso(6*a.NS)))
        source=dict(event_id='invented0',candidate_calendar_partition=a.PARTITIONS[0],Mw_band='<3.5',mw=3.0)
        outcome={'base':{'status':'ok','accepted_picks':picks,'nz':{'t0_utc':a.request_iso(5*a.NS)}}}
        result=a.current_event(source,outcome)
        self.assertEqual(len(result['targets']),8)
        self.assertNotIn('LATE',result['current_station_masks']['1'])
        self.assertEqual(result['targets'][0]['prefix'],'HH')

    def test_all96_retained_and_future_view_hidden(self):
        early=dict(TARGET);late=dict(TARGET,station='LATE',pick_ns=7*a.NS)
        e=event(targets=[early,late]);e['current_station_masks']['1']=['SYNTH']
        events=[e]+[event('invented'+str(i),targets=[]) for i in range(1,96)]
        targets=a.initial_rows(events);targets[0]['horizons']['1'].update(count_valid=True,clipping_screen_passed=False)
        rows,summary=a.aggregate(events,targets,False)
        self.assertEqual(summary['events']['event_denominator'],96)
        self.assertEqual(len(rows)*3,288)
        self.assertEqual(len(rows[0]['horizons']['1']['current_view']),1)
        self.assertNotIn('Mw_band',rows[0]['horizons']['1']['current_view'][0])
        self.assertEqual(summary['events']['horizons']['1']['count_available'],1)
        self.assertFalse(summary['scientific_interpretation_allowed'])
        with self.assertRaises(a.AuditError):a.aggregate(events,targets[:-1],False)

    def test_query_bytes_empty_blocks_and_cache_difference(self):
        events=[event()]+[event('invented'+str(i),targets=[]) for i in range(1,96)]
        get,post=a.query_contract(events,{})
        self.assertEqual(len(post),6);self.assertEqual(get[0]['envelope']['location'],'--')
        self.assertTrue(post[0]['post_body'].endswith('\n'))
        self.assertIn(' HH? ',post[0]['post_body'])
        get2,post2=a.query_contract(events,{'invented0|SYNTH':{'waveform':{'pin':'invented'}}})
        self.assertEqual(get,get2);self.assertEqual(post2[0]['slots'],[])

    def test_exact_cache_rejects_broader_window_and_partial(self):
        import urllib.parse
        e=event();env=dict(a.envelope(e,TARGET),format='miniseed')
        q=dict(event_id='invented0',station='SYNTH',file='invented.mseed',kind='dataselect',
               url='https://service.geonet.org.nz/fdsnws/dataselect/1/query?'+urllib.parse.urlencode(env))
        entry=dict(q,status='ok',http_status=200,bytes=1,sha256=a.sha(b'x'))
        m={'completed':True,'files':{'raw/invented.mseed':{'bytes':1,'sha256':a.sha(b'x')}}}
        self.assertTrue(a.exact_cache_match(q,entry,m,e,TARGET,'waveform'))
        self.assertFalse(a.exact_cache_match(q,dict(entry,status='partial'),m,e,TARGET,'waveform'))
        q2=dict(q,url=q['url'].replace('00%3A00%3A00','00%3A00%3A01'))
        self.assertFalse(a.exact_cache_match(q2,dict(entry,url=q2['url']),m,e,TARGET,'waveform'))

    def test_attempt_accounting_and_order(self):
        events=[event()]+[event('invented'+str(i),targets=[]) for i in range(1,96)]
        get,post=a.query_contract(events,{})
        planned=get+[p for p in post if p['slots']]
        entries=[];files={}
        for i,p in enumerate(planned):
            entry=dict(url=p['url'],file=p['file'],method=p['method'],start_from_outer_seconds=2*i,
                       elapsed_seconds=.25,bytes=1,sha256=a.sha(b'x'),status='ok',http_status=200)
            if p['method']=='POST':entry.update(post_body_sha256=p['post_body_sha256'],post_body_bytes=len(p['post_body'].encode('ascii')))
            entries.append(entry);files['raw/'+p['file']]={'bytes':1,'sha256':a.sha(b'x')}
        m=dict(files=files,response_body_bytes=2,request_attempts=2,outer_elapsed_seconds=5)
        self.assertEqual(a.verify_attempts(entries,get,post,m)['attempts'],2)
        bad=copy.deepcopy(entries);bad[1]['start_from_outer_seconds']=.5
        with self.assertRaises(a.AuditError):a.verify_attempts(bad,get,post,m)
        for status in ('TimeoutError','timeout','cap_exceeded',None,'invented_unknown'):
            bad=copy.deepcopy(entries);bad[0]['status']=status
            with self.assertRaises(a.AuditError):a.verify_attempts(bad,get,post,m)
        bad=copy.deepcopy(entries);bad[0].update(status='URLError',error='The read operation timed out')
        with self.assertRaises(a.AuditError):a.verify_attempts(bad,get,post,m)

    def test_incomplete_result_rejected_before_any_member_read(self):
        with tempfile.TemporaryDirectory() as root:
            for manifest in ({'completed':False,'worker_exit_code':2,'artifact_pins_incomplete':True},
                             {'completed':True,'worker_exit_code':2},
                             {'completed':True,'worker_exit_code':0,'artifact_pins_incomplete':True}):
                with self.assertRaises(a.AuditError):a.verify_completed_files(root,manifest)
            Path(root,'outer_interruption.json').write_text('{}')
            with self.assertRaises(a.AuditError):a.verify_completed_files(root,{'completed':True,'worker_exit_code':0})

    def test_attempt_resource_errno_messages_and_wrapped_failures(self):
        events=[event()]+[event('invented'+str(i),targets=[]) for i in range(1,96)]
        get,post=a.query_contract(events,{})
        planned=get+[p for p in post if p['slots']]
        entries=[];files={}
        for i,p in enumerate(planned):
            e=dict(url=p['url'],file=p['file'],method=p['method'],start_from_outer_seconds=2*i,
                   elapsed_seconds=.25,bytes=0,sha256=a.sha(b''),status='OSError',error='[Errno 61] Connection refused')
            if p['method']=='POST':e.update(post_body_sha256=p['post_body_sha256'],post_body_bytes=len(p['post_body'].encode('ascii')))
            entries.append(e);files['raw/'+p['file']]={'bytes':0,'sha256':a.sha(b'')}
        manifest=dict(files=files,response_body_bytes=0,request_attempts=2,outer_elapsed_seconds=5)
        self.assertEqual(a.verify_attempts(entries,get,post,manifest)['attempts'],2)
        for error in ('[Errno 24] Too many open files','[Errno 28] No space left on device',
                      '<urlopen error [Errno 23] exhausted>', 'Disk quota exceeded'):
            with self.subTest(error=error):
                bad=copy.deepcopy(entries);bad[0].update(status='URLError',error=error)
                with self.assertRaises(a.AuditError):a.verify_attempts(bad,get,post,manifest)

    def test_completed_launch_must_encompass_every_attempt(self):
        request={'url':'https://invented.invalid/metadata','file':'invented.xml','method':'GET'}
        entry=dict(request,start_from_outer_seconds=100,elapsed_seconds=1,bytes=0,
                   sha256=a.sha(b''),status='HTTPError',http_status=404)
        manifest={'files':{'raw/invented.xml':{'bytes':0,'sha256':a.sha(b'')}},
                  'response_body_bytes':0,'request_attempts':1,'outer_elapsed_seconds':101}
        self.assertEqual(a.verify_attempts([entry],[request],[],manifest)['attempts'],1)
        for outer in (5,100.5,math.nan,math.inf,True):
            with self.subTest(outer=outer),self.assertRaises(a.AuditError):
                a.verify_attempts([entry],[request],[],dict(manifest,outer_elapsed_seconds=outer))

    def test_semantic_comparison_preserves_every_horizon(self):
        rows=a.initial_rows([event()]);same=copy.deepcopy(rows)
        self.assertEqual(a.compare_prefix_facts(rows,same),[])
        same[0]['horizons']['3']['count_valid']=True
        findings=a.compare_prefix_facts(rows,same)
        self.assertEqual([(v['horizon'],v['field']) for v in findings],[('3','count_valid')])
        with self.assertRaises(a.AuditError):a.compare_prefix_facts(rows,[])

    def test_scientific_claim_flags_and_presence_are_compared(self):
        rows=a.initial_rows([event()])
        value=rows[0]['horizons']['1']
        value.update(physically_calibrated_prefix_verified=False,operational_picker_replayed=False,
                     response_evidence={'HHE':{'physically_calibrated_prefix_verified':False}})
        produced=copy.deepcopy(rows)
        altered=produced[0]['horizons']['1']
        altered.update(physically_calibrated_prefix_verified=True,operational_picker_replayed=True)
        altered['response_evidence']['HHE']['physically_calibrated_prefix_verified']=True
        self.assertEqual({v['field'] for v in a.compare_prefix_facts(rows,produced)},
                         {'physically_calibrated_prefix_verified','operational_picker_replayed',
                          'HHE.response.physically_calibrated_prefix_verified'})
        produced=copy.deepcopy(rows)
        del produced[0]['horizons']['1']['physically_calibrated_prefix_verified']
        differences=a.compare_prefix_facts(rows,produced)
        self.assertEqual(len(differences),1)
        self.assertTrue(differences[0]['independent_present']);self.assertFalse(differences[0]['producer_present'])
        rows[0]['horizons']['1']['physically_calibrated_prefix_verified']=None
        self.assertEqual(len(a.compare_prefix_facts(rows,produced)),1)

    def test_exact_period_and_period_presence_are_compared(self):
        rows=a.initial_rows([event()])
        good=a.prefix_component([piece(list(range(12)))],0,6*a.NS,2)
        rows[0]['horizons']['1']['components']={'HHE':good}
        produced=copy.deepcopy(rows)
        produced[0]['horizons']['1']['components']['HHE']['sample_period_ns_numerator']+=1
        differences=a.compare_prefix_facts(rows,produced)
        self.assertEqual([v['field'] for v in differences],['HHE.sample_period_ns_numerator'])
        produced=copy.deepcopy(rows)
        del produced[0]['horizons']['1']['components']['HHE']['sample_period_ns_denominator']
        differences=a.compare_prefix_facts(rows,produced)
        self.assertEqual([v['field'] for v in differences],['HHE.sample_period_ns_denominator'])
        self.assertTrue(differences[0]['independent_present']);self.assertFalse(differences[0]['producer_present'])

    def test_failure_categories_and_native_warning_discrepancy(self):
        good=a.prefix_component([piece(list(range(12)))],0,6*a.NS,2)
        bad=dict(good,available=False,finite=False,gaps=1)
        result={'status':'audited','count_valid':False,'components':{'E':good,'N':good,'Z':bad}}
        self.assertEqual(a.prefix_failure_categories(result),['fragment_gap','nonfinite_samples'])
        result['components']['Z']=good
        self.assertEqual(a.prefix_failure_categories(result),['cross_component_lattice'])
        rows=a.initial_rows([event()]);same=copy.deepcopy(rows)
        rows[0]['horizons']['1']['response_evidence']={'HHE':{'native_stderr':'invented warning'}}
        same[0]['horizons']['1']['response_evidence']={'HHE':{'native_stderr':''}}
        differences=a.compare_prefix_facts(rows,same)
        self.assertEqual([v['field'] for v in differences],['HHE.response.native_stderr'])

    def test_optional_response_failure_counts_keep_count_denominators(self):
        events=[event()]+[event('invented'+str(i),targets=[]) for i in range(1,96)]
        rows=a.initial_rows(events)
        value=rows[0]['horizons']['1']
        value.update(status='audited',count_valid=True,clipping_screen_passed=True,
                     response_panel_error='ValueError: private invented path',
                     response_panel_failure_category='cached_response_public_parser',
                     response_evidence={'HHE':{'error':'private sensitivity text','failure_category':'invalid_response_sensitivity'},
                                        'HHN':{'error':'private evalresp text','failure_category':'evalresp_failure'},
                                        'HHZ':{'error':'other private evalresp text','failure_category':'evalresp_failure'}})
        _,summary=a.aggregate(events,rows,False)
        self.assertEqual(summary['events']['event_denominator'],96)
        self.assertEqual(summary['target_denominator'],1)
        self.assertEqual(summary['events']['horizons']['1']['count_available'],1)
        self.assertEqual(summary['target_horizon_response_failure_categories']['1'],
                         {'cached_response_public_parser':1,'evalresp_failure':1,'invalid_response_sensitivity':1})
        self.assertEqual(summary['target_horizon_response_failure_categories']['3'],{})
        self.assertNotIn('private',json.dumps(summary['target_horizon_response_failure_categories']))

    def test_public_summary_excludes_private_reason_text(self):
        events=[event()]+[event('invented'+str(i),targets=[]) for i in range(1,96)]
        rows=a.initial_rows(events)
        reason='ValueError: private invented station and /private/secret/path'
        rows[0]['horizons']['1'].update(status='unresolved_engineering',reason=reason)
        _,summary=a.aggregate(events,rows,False)
        self.assertNotIn('target_horizon_reasons',summary)
        self.assertNotIn('/private/secret/path',json.dumps(summary))
        self.assertEqual(a.private_reason_counters(rows)['1'],{reason:1})
        self.assertEqual(summary['target_horizon_failure_categories']['1'],{'unresolved_engineering':1})


class PublicDecoderTests(unittest.TestCase):
    def test_native_rate_float_tolerance_is_only_rounding(self):
        from fractions import Fraction
        expected=Fraction(100,3)
        sequential=(1.0/3)*100
        self.assertTrue(a.float_rate_agrees(sequential,expected))
        self.assertFalse(a.float_rate_agrees(float(expected)+1e-6,expected))
        self.assertFalse(a.float_rate_agrees(math.nan,expected))
        p=piece(list(range(200))+[math.nan],rate=sequential)
        p['sample_rate_fraction']=expected
        result=a.prefix_component([p],0,6*a.NS,100/3)
        self.assertTrue(result['available']);self.assertEqual(result['samples'],200)
        p['sample_rate']=float(expected)+1e-6
        with self.assertRaises(ValueError):a.prefix_component([p],0,6*a.NS,100/3)
    def test_native_factor_multiplier_and_blockette_rate(self):
        from fractions import Fraction
        for order in ('>','<'):
            for factor,multiplier,expected in ((100,-3,Fraction(100,3)),(-3,100,Fraction(100,3)),
                                              (-3,-5,Fraction(1,15)),(5,20,Fraction(100))):
                record=bytearray(128);a.struct.pack_into(order+'hh',record,32,factor,multiplier)
                self.assertEqual(a.native_mseed2_rate(record,order),expected)
            a.struct.pack_into(order+'H',record,46,48)
            a.struct.pack_into(order+'HHf',record,48,100,0,2.3)
            exact=Fraction.from_float(a.struct.unpack_from(order+'f',record,52)[0])
            self.assertEqual(a.native_mseed2_rate(record,order),exact)
            a.struct.pack_into(order+'f',record,52,math.nan)
            with self.assertRaises(ValueError):a.native_mseed2_rate(record,order)

    def test_native_100_over_3_clock_excludes_exact_deadline_sample(self):
        import numpy as np
        from fractions import Fraction
        from obspy import Stream,Trace,UTCDateTime
        tr=Trace(np.append(np.arange(200,dtype=np.float64),np.nan))
        tr.stats.network='NZ';tr.stats.station='SYNTH';tr.stats.location='';tr.stats.channel='HHE'
        tr.stats.starttime=UTCDateTime(0);tr.stats.sampling_rate=33
        encoded=io.BytesIO();Stream([tr]).write(encoded,format='MSEED',encoding='FLOAT64',reclen=4096,byteorder='>')
        for factor,multiplier in ((100,-3),(-3,100)):
            with self.subTest(factor=factor,multiplier=multiplier):
                body=bytearray(encoded.getvalue());a.struct.pack_into('>hh',body,32,factor,multiplier)
                backend=a.PublicObsPy();stream=backend.decode(bytes(body))
                pieces=backend.pieces(stream,TARGET,'HHE',6*a.NS)
                self.assertEqual(pieces[0]['sample_rate_fraction'],Fraction(100,3))
                result=a.prefix_component(pieces,0,6*a.NS,100/3)
                self.assertEqual(result['samples'],200);self.assertTrue(result['finite']);self.assertTrue(result['available'])
                self.assertEqual(Fraction(result['sample_period_ns_numerator'],result['sample_period_ns_denominator']),30000000)
                self.assertTrue(a.aligned({'E':result,'N':result,'Z':result},100/3))
                self.assertFalse(a.aligned({'E':result,'N':result,'Z':result},33))

    def test_invented_mseed_public_header_decode_and_prefix(self):
        import numpy as np
        from obspy import Stream, Trace, UTCDateTime
        traces=[]
        for code in ('HHE','HHN','HHZ'):
            tr=Trace(np.arange(20,dtype=np.int32));tr.stats.network='NZ';tr.stats.station='SYNTH'
            tr.stats.location='';tr.stats.channel=code;tr.stats.starttime=UTCDateTime(0);tr.stats.sampling_rate=2
            traces.append(tr)
        encoded=io.BytesIO();Stream(traces).write(encoded,format='MSEED',encoding='STEIM2')
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'invented.mseed';p.write_bytes(encoded.getvalue())
            e=dict(key='new',source='new_batch',path=str(p),pin={'bytes':p.stat().st_size,'sha256':a.sha(p.read_bytes())})
            d=a.BlockDecoder([e]);stream=d.decode('new')
            answer=a.qualify(event(),TARGET,xml(),stream)
            self.assertEqual(d.declarations['new'],60)
            self.assertEqual(d.actual_total,240)
            self.assertTrue(all(v['count_valid'] for v in answer.values()))
            self.assertEqual(answer['1']['components']['HHE']['samples'],12)

    def test_invented_response_public_evalresp_and_native_warning_capture(self):
        body=invented_response_body()
        selected=a.epoch_triplet(a.stationxml(body),TARGET,0,6*a.NS)
        panel=a.response_panel(body,selected)
        self.assertTrue(all(v['full_transfer_response_available'] for v in panel.values()))
        self.assertTrue(all(not v['physically_calibrated_prefix_verified'] for v in panel.values()))
        with a.captured_native_stderr() as sink:
            os.write(2,b'invented native warning\n');sink.seek(0)
            self.assertEqual(sink.read(),b'invented native warning\n')

    def test_public_response_parser_excludes_future_invalid_end(self):
        body=invented_response_body()
        selected=a.epoch_triplet(a.stationxml(body),TARGET,0,6*a.NS)
        expected=a.response_panel(body,selected)
        root=a.ET.fromstring(body)
        station=next(e for e in root.iter() if a._local_name(e)=='Station')
        future=copy.deepcopy(next(e for e in station if a._local_name(e)=='Channel'))
        future.set('startDate','1970-01-01T00:00:07Z');future.set('endDate','invalid')
        station.append(future)
        changed=a.ET.tostring(root,encoding='utf-8')
        pin=a.sha(changed)
        selected2=a.epoch_triplet(a.stationxml(changed),TARGET,0,6*a.NS)
        self.assertEqual(a.response_panel(changed,selected2),expected)
        self.assertEqual(a.sha(changed),pin)
        isolated,chosen=a.selected_response_xml(changed,selected2)
        self.assertEqual(len(a.stationxml(isolated)),3);self.assertEqual(chosen,selected2)
        self.assertNotIn(b'invalid',isolated)
        with self.assertRaises(ValueError):a.selected_response_xml(changed,selected2+selected2[:1])

    def test_response_os_resource_failures_interrupt(self):
        body=invented_response_body()
        selected=a.epoch_triplet(a.stationxml(body),TARGET,0,6*a.NS)
        for target,code in (('auditor.os.dup',a.errno.EMFILE),
                            ('auditor.tempfile.TemporaryFile',a.errno.ENOSPC),
                            ('obspy.core.inventory.response.Response.get_evalresp_response_for_frequencies',a.errno.ENOMEM)):
            with self.subTest(target=target),mock.patch(target,side_effect=OSError(code,'invented resource exhaustion')):
                with self.assertRaises(a.ResourceStop):a.response_panel(body,selected)
        body=invented_response_body(rate=2,frequency=.25)
        with mock.patch('obspy.read_inventory',side_effect=OSError(a.errno.ENFILE,'invented resource exhaustion')):
            with self.assertRaises(a.ResourceStop):a.qualify(event(),TARGET,body,b'good',ToyBackend(),body)

    def test_native_and_wrapped_evalresp_allocation_diagnostics_stop(self):
        body=invented_response_body()
        selected=a.epoch_triplet(a.stationxml(body),TARGET,0,6*a.NS)
        method='obspy.core.inventory.response.Response.get_evalresp_response_for_frequencies'
        def native_success(*args,**kwargs):
            os.write(2,b'evalresp: malloc failed\n');return [10+0j]
        def native_failure(*args,**kwargs):
            os.write(2,b'evalresp: memory allocation failed\n');raise ValueError('generic wrapper failure')
        for effect in (native_success,native_failure,ValueError('unable to allocate response filter')):
            with self.subTest(effect=str(effect)),mock.patch(method,side_effect=effect):
                with self.assertRaises(a.ResourceStop):a.response_panel(body,selected)

    def test_response_ordinary_failure_does_not_erase_counts(self):
        body=invented_response_body(rate=2,frequency=.25,stages=False)
        answer=a.qualify(event(),TARGET,body,b'good',ToyBackend(),body)
        self.assertTrue(answer['1']['count_valid'])
        self.assertFalse(answer['1']['full_transfer_response_available'])
        self.assertEqual(a.response_failure_categories(answer['1']),['missing_response_or_sensitivity'])
        with mock.patch('obspy.read_inventory',side_effect=ValueError('invented parse failure')):
            answer=a.qualify(event(),TARGET,body,b'good',ToyBackend(),body)
        self.assertTrue(answer['1']['count_valid'])
        self.assertEqual(a.response_failure_categories(answer['1']),['cached_response_public_parser'])

    def test_optional_response_cap_is_not_ordinary_absence(self):
        with self.assertRaises(a.AuditError):
            a.qualify(event(),TARGET,xml(),b'good',ToyBackend(),b' '*(4*a.MIB+1))

    def test_cached_response_joins_selected_12z_without_reselecting_enz(self):
        body=invented_response_body(rate=2,frequency=.25,codes=('HH1','HH2','HHZ'))
        root=a.ET.fromstring(body)
        station=next(e for e in root.iter() if a._local_name(e)=='Station')
        other=a.ET.fromstring(invented_response_body(rate=2,frequency=.25))
        for ch in other.iter():
            if a._local_name(ch)=='Channel' and ch.get('code') in ('HHE','HHN'):
                station.append(copy.deepcopy(ch))
        cached=a.ET.tostring(root,encoding='utf-8')
        self.assertEqual([r['code'] for r in a.epoch_triplet(a.stationxml(cached),TARGET,0,6*a.NS)],['HHE','HHN','HHZ'])
        answer=a.qualify(event(),TARGET,body,b'good',ToyBackend(),cached)
        self.assertEqual(answer['1']['sensor_codes'],['HH1','HH2','HHZ'])
        self.assertTrue(answer['1']['count_valid'])
        self.assertTrue(answer['1']['full_transfer_response_available'])
        self.assertEqual(a.response_failure_categories(answer['1']),[])


if __name__=='__main__':
    unittest.main()

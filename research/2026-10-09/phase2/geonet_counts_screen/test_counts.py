"""Invented identities, inventories, arrays and fake transport only; zero requests."""
import copy
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import types
import unittest
from unittest import mock
import urllib.error
import numpy as np
from obspy import Inventory,Stream,Trace,UTCDateTime
from obspy.core.inventory import Channel,Network,Station
from obspy.core.inventory.response import Response,InstrumentSensitivity,ResponseStage
import counts
import dependencies as deps
import screen
import selection
import transport

CORE=deps.module('core');ADAPTER=deps.module('adapter')

def event(index=0,with_target=True):
    target={'network':'NZ','station':'ST01','location':'','prefix':'HH','pick_ns':5*CORE.NS,'queryable':True,'unqueryable_reason':None}
    return {'event_id':'invented'+str(index),'Mw_band':'[4,4.5)','candidate_calendar_partition':'test2018_2024','mw':4.2,'t0_ns':5*CORE.NS if with_target else None,
            'P_status':'ok' if with_target else 'unknown','incomplete_associated_P_structure':False,
            'current_station_masks':{str(h):['ST01'] if with_target else [] for h in (1,3,5)},'targets':[target] if with_target else []}

def inventory(response=None,family='ENZ',start=-1,end=20):
    channels=[Channel(code='HH'+s,location_code='',latitude=-40,longitude=175,elevation=0,depth=0,azimuth=az,dip=dip,sample_rate=100,
                      start_date=UTCDateTime(start),end_date=UTCDateTime(end) if end is not None else None,response=response) for s,az,dip in zip(family,(0,90,0),(0,0,-90))]
    return Inventory([Network(code='NZ',stations=[Station(code='ST01',latitude=-40,longitude=175,elevation=0,channels=channels)])],source='invented')

def stream(family='ENZ',samples=1000,start=0):
    return Stream([Trace(data=np.arange(samples,dtype=np.int32)%11,header={'network':'NZ','station':'ST01','location':'','channel':'HH'+s,'sampling_rate':100,'starttime':UTCDateTime(start)}) for s in family])

def miniseed(st=None):
    output=io.BytesIO();(st or stream()).write(output,format='MSEED');return output.getvalue()

def synthetic_frame():
    rows=[];i=0
    for p in selection.PARTITIONS:
        for b in selection.BANDS:
            n=10 if (p,b)==('dev2015_2017','<3.5') else 24
            for k in range(n):
                rows.append({'event_id':f'fake{i:04d}','source':'new_lower_M','candidate_calendar_partition':p,'Mw_band':b,'mw':3.0});i+=1
    for k in range(149):
        rows.append({'event_id':f'fake{i:04d}','source':'reused_tail','candidate_calendar_partition':selection.PARTITIONS[k%3],'mw':6.5 if k<60 else 5.7});i+=1
    outcomes={r['event_id']:{'base':{'status':'unknown'}} for r in rows}
    return rows,outcomes

def accepted(picks):
    t0=min(CORE.stamp_ns(p['time']) for p in picks)
    return {'base':{'status':'ok','accepted_picks':picks,'nz':{'t0_utc':CORE.iso(t0)},'reasons':{}}}

def pick(station,time_ns,location='',channel='HHZ',pid='invented'):
    return {'network':'NZ','station':station,'location':location,'channel':channel,'pick_id':pid,'time':CORE.iso(time_ns)}

class SelectionTests(unittest.TestCase):
    def choose(self,rows,outcomes):
        # Actual hardcoded lower-set hash cannot belong to an invented frame.
        # Bypass only this identity guard; rank/allocations/clock rules stay real.
        with mock.patch.object(selection,'list_hash',return_value='6ed849d32a6ab180b7ddb4ddbf85d085d6819011fcebe7c093384c0806452d7c'):
            return selection.choose(rows,outcomes,CORE,{'events':96})
    def test_all96_selected_before_metadata_conditioning(self):
        rows,out=synthetic_frame();a=self.choose(rows,out)
        self.assertEqual(len(a),96);self.assertEqual(sum(e['mw']>=6 for e in a),60);self.assertEqual(sum(bool(e['targets']) for e in a),0)
        selected=a[0]['event_id'];out[selected]=accepted([pick('ST01',0)])
        b=self.choose(rows,out);self.assertEqual([e['event_id'] for e in a],[e['event_id'] for e in b]);self.assertEqual(sum(bool(e['targets']) for e in b),1)
    def test_hash_rank_selection_and_query_order_ignore_row_order(self):
        rows,out=synthetic_frame();a=self.choose(rows,out);b=self.choose(list(reversed(rows)),out)
        self.assertEqual(a,b)
        for p in selection.PARTITIONS:
            for band in selection.BANDS:
                actual={e['event_id'] for e in a if e['candidate_calendar_partition']==p and e['mw']<5.5 and e['Mw_band']==band}
                eligible=[r for r in rows if r.get('Mw_band')==band and r['candidate_calendar_partition']==p]
                expected={r['event_id'] for r in sorted(eligible,key=lambda r:(selection.digest('geonet-counts-screen-v1|'+p+'|'+band+'|'+r['event_id']),r['event_id']))[:2]}
                self.assertEqual(actual,expected)
    def test_actual_frame_hash_guard_is_not_bypassed_in_production(self):
        rows,out=synthetic_frame()
        with self.assertRaisesRegex(ValueError,'selected-set'):selection.choose(rows,out,CORE,{'events':96})
    def test_strict_boundary_stationcollapse_cap8_and_no_station9(self):
        rows,out=synthetic_frame();eid=self.choose(rows,out)[0]['event_id'];ps=[pick('ST'+str(k),k*CORE.NS//10,pid=str(k)) for k in range(9)]
        ps.extend([pick('EDGE1',CORE.NS),pick('EDGE3',3*CORE.NS),pick('EDGE5',5*CORE.NS),pick('ST0',0,location='01',pid='tie'),pick('ST0',CORE.NS,pid='later')]);out[eid]=accepted(ps)
        e=next(e for e in self.choose(rows,out) if e['event_id']==eid)
        self.assertEqual(e['current_station_masks']['1'],['ST'+str(k) for k in range(8)]);self.assertNotIn('ST8',[t['station'] for t in e['targets']]);self.assertEqual(e['targets'][0]['location'],'')
    def test_invalid_seed_slot_remains_without_replacement(self):
        rows,out=synthetic_frame();eid=self.choose(rows,out)[0]['event_id'];out[eid]=accepted([pick('bad_station!',0),pick('ST02',4*CORE.NS)])
        e=next(e for e in self.choose(rows,out) if e['event_id']==eid)
        self.assertFalse(e['targets'][0]['queryable']);self.assertEqual(len(e['targets']),2)
    def test_envelopes_and_post_body_precede_metadata_response(self):
        e=event();meta,batches=selection.queries([e],CORE,{})
        self.assertEqual(meta[0]['method'],'GET');self.assertIn('level=channel',meta[0]['url']);self.assertIn('channel=HH%3F',meta[0]['url'])
        self.assertEqual(batches[0]['method'],'POST');self.assertEqual(batches[0]['post_body'],'NZ ST01 -- HH? 1970-01-01T00:00:00Z 1970-01-01T00:00:10Z\n')
        self.assertEqual(batches[0]['post_body_sha256'],selection.digest(batches[0]['post_body']))
    def test_exact_cache_excludes_only_frozen_waveform_selection(self):
        e=event();meta,batches=selection.queries([e],CORE,{e['event_id']+'|ST01':{'waveform':{'pin':'invented'}}})
        self.assertEqual(len(meta),1);self.assertEqual(batches[0]['slots'],[])
    def test_six_blocks_include_source_events_without_queryable_targets(self):
        events=[event(k,k%16==0) for k in range(96)];meta,batches=selection.queries(events,CORE,{})
        self.assertEqual(len(batches),6);self.assertTrue(all(b['source_event_count']==16 for b in batches));self.assertEqual(len(meta),6)

class PrefixTests(unittest.TestCase):
    def test_nativecounts_work_without_transfer_response(self):
        e=event();result=screen.analyze(inventory(),stream(),e,e['targets'][0],CORE,ADAPTER)
        self.assertTrue(all(v['count_valid'] for v in result.values()));self.assertTrue(all(not v['full_transfer_response_available'] for v in result.values()))
        self.assertEqual(result['1']['components']['HHE']['samples'],600);self.assertFalse(result['1']['physically_calibrated_prefix_verified'])
    def test_future_suffix_mutation_cannot_change_absolute_earlier_decision(self):
        e=event();original=stream();a=screen.analyze(inventory(),original,e,e['targets'][0],CORE,ADAPTER)
        altered=original.copy()
        for tr in altered:tr.data[600:]=777
        b=screen.analyze(inventory(),altered,e,e['targets'][0],CORE,ADAPTER);self.assertEqual(a['1'],b['1'])
        altered.append(Trace(np.zeros(100,dtype=np.int32),header={'network':'NZ','station':'ST01','channel':'HHE','sampling_rate':100,'starttime':UTCDateTime(8)}))
        self.assertEqual(a['1'],screen.analyze(inventory(),altered,e,e['targets'][0],CORE,ADAPTER)['1'])
    def test_missing_channel_metadata_is_unresolved_even_with_samples(self):
        e=event();inv=inventory();inv[0][0].channels=[]
        result=screen.analyze(inv,stream(),e,e['targets'][0],CORE,ADAPTER)
        self.assertFalse(result['1']['count_valid']);self.assertIn('missing coherent',result['1']['reason'])
    def test_later_epoch_change_does_not_disqualify_earlier_prefix(self):
        e=event();inv=inventory(end=7);result=screen.analyze(inv,stream(),e,e['targets'][0],CORE,ADAPTER)
        self.assertTrue(result['1']['count_valid']);self.assertFalse(result['3']['count_valid'])
    def test_equal_rates_with_shifted_component_lattices_are_not_aligned(self):
        e=event();st=stream();st[1].stats.starttime=UTCDateTime(.005)
        self.assertFalse(screen.analyze(inventory(),st,e,e['targets'][0],CORE,ADAPTER)['1']['count_valid'])
    def test_fragment_splitting_does_not_hide_extreme_run_candidate(self):
        e=event();st=stream();st[0].data[300:308]=999
        a=screen.analyze(inventory(),st,e,e['targets'][0],CORE,ADAPTER)['1']
        split=Stream([st[0].copy(),st[0].copy(),st[1],st[2]]);split[0].data=st[0].data[:304];split[1].data=st[0].data[304:];split[1].stats.starttime=UTCDateTime(3.04)
        b=screen.analyze(inventory(),split,e,e['targets'][0],CORE,ADAPTER)['1']
        self.assertEqual(a,b);self.assertTrue(a['count_valid']);self.assertFalse(a['clipping_screen_passed'])
    def test_future_station_identity_and_metadata_do_not_reach_early_view(self):
        a=event();first=screen.initial_targets([a]);left=screen.event_outcomes([a],first)[0]['horizons']['1']
        b=copy.deepcopy(a);future=dict(b['targets'][0],station='FUTURE',pick_ns=7*CORE.NS);b['targets'].append(future);b['current_station_masks']['3'].append('FUTURE');b['current_station_masks']['5'].append('FUTURE')
        rows=screen.initial_targets([b]);rows[-1]['horizons']['3']['invented_future_geometry']={'latitude':99}
        right=screen.event_outcomes([b],rows)[0]['horizons']['1'];self.assertEqual(left,right);self.assertNotIn('FUTURE',json.dumps(right))
    def test_bad_cached_response_never_erases_count_evidence(self):
        e=event();result=screen.analyze(inventory(),stream(),e,e['targets'][0],CORE,ADAPTER,inventory())
        self.assertTrue(result['1']['count_valid']);self.assertFalse(result['1']['full_transfer_response_available']);self.assertIn('error',result['1']['response_evidence']['HHE'])
    def test_predeclared_metadata_family_never_falls_back_after_sample_failure(self):
        e=event();inv=inventory();inv[0][0].channels+=inventory(family='12Z')[0][0].channels[:2]
        result=screen.analyze(inv,stream(family='12Z'),e,e['targets'][0],CORE,ADAPTER)
        self.assertEqual(result['1']['sensor_codes'],['HHE','HHN','HHZ']);self.assertFalse(result['1']['count_valid'])
    def test_clipping_flags_are_separate_from_counts_validity(self):
        e=event();st=stream()
        for tr in st:tr.data[:600]=0
        h=screen.analyze(inventory(),st,e,e['targets'][0],CORE,ADAPTER)['1'];self.assertTrue(h['count_valid']);self.assertFalse(h['clipping_screen_passed'])
        targets=screen.initial_targets([e]);targets[0]['horizons']['1']=h;summary=screen.summary([e],targets,True)
        self.assertEqual(summary['events']['horizons']['1']['count_available'],1);self.assertEqual(summary['events']['horizons']['1']['clean_screen_available'],0)
    def test_budget_exception_propagates_from_optional_response_panel(self):
        e=event();error=type('InventedBudget',(RuntimeError,),{})
        with mock.patch.object(ADAPTER,'response_evidence',side_effect=error('deadline')):
            with self.assertRaises(error):screen.analyze(inventory(),stream(),e,e['targets'][0],CORE,ADAPTER,inventory(),error)
    def test_component_allocation_failure_propagates(self):
        e=event()
        with mock.patch.object(CORE,'component',side_effect=MemoryError('invented component allocation')):
            with self.assertRaises(MemoryError):screen.analyze(inventory(),stream(),e,e['targets'][0],CORE,ADAPTER)
    def test_pinned_response_adapter_propagates_allocation_failure(self):
        e=event();response=Response(instrument_sensitivity=InstrumentSensitivity(1,1,'M/S','COUNTS'),response_stages=[ResponseStage(1,1,1,'M/S','COUNTS')])
        with mock.patch.object(response,'get_evalresp_response_for_frequencies',side_effect=MemoryError('invented evalresp allocation')):
            with self.assertRaises(MemoryError):screen.analyze(inventory(),stream(),e,e['targets'][0],CORE,ADAPTER,inventory(response))

class ResourceAndWorkerTests(unittest.TestCase):
    def test_public_miniseed_headers_actualmemory_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'a';p.write_bytes(miniseed());n,size=counts.wave_headers(p);st=counts.wave_decode(p,n)
            self.assertEqual(n,3000);self.assertEqual(sum(tr.stats.npts for tr in st),n);self.assertLess(size,16*counts.MIB)
    def test_declared_memory_guard_precedes_full_decode(self):
        huge=[types.SimpleNamespace(stats=types.SimpleNamespace(npts=64*counts.MIB//8+1))]
        with mock.patch('obspy.read',return_value=huge),mock.patch.object(deps,'read',return_value=b'invented'):
            with self.assertRaises(counts.ResourceLimit):counts.wave_headers(Path('invented'))
    def test_actual_memory_and_header_mismatch_fail_closed(self):
        huge=[types.SimpleNamespace(stats=types.SimpleNamespace(npts=1),data=types.SimpleNamespace(nbytes=64*counts.MIB+1))]
        with mock.patch('obspy.read',return_value=huge),mock.patch.object(deps,'read',return_value=b'invented'):
            with self.assertRaises(counts.ResourceLimit):counts.wave_decode(Path('invented'),1)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'a';p.write_bytes(miniseed())
            with self.assertRaisesRegex(ValueError,'differs'):counts.wave_decode(p,2)
    def test_nul_dtd_entity_and_oversized_xml_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'a'
            for body in (b'\x00',b'<!DOCTYPE x>',b'<!ENTITY x>'):
                p.write_bytes(body)
                with self.assertRaisesRegex(ValueError,'forbidden'):counts.xml_inventory(p)
            p.write_bytes(b'x'*(4*counts.MIB+1))
            with self.assertRaisesRegex(ValueError,'bounded'):counts.xml_inventory(p)
    def plan(self):
        events=[event(0)]+[event(k,False) for k in range(1,96)];meta,batches=selection.queries(events,CORE,{})
        return {'events':events,'metadata_requests':meta,'waveform_batches':batches,'cache':{},'processing_files':{},'reviewed_dependencies':{},'runtime':{},'input_receipt_sha256':'0'*64,'specification':{'caps':counts.specification()['caps']},'station_denominator':1}
    def worker_run(self,fail_channel=None,header_error=None,cache_waveform=None,second_target=False,corrupt_cache_pin=False):
        plan=self.plan();lib=deps.module('downloader');real=deps.module;factories=[]
        if second_target:
            e=plan['events'][0];e['targets'].append(dict(e['targets'][0],station='ST02'))
            for h in ('1','3','5'):e['current_station_masks'][h].append('ST02')
        class FakeFetcher:
            def __init__(self,root,**kwargs):self.root=root;self.log=[];self.bytes=0;self.clock=time.monotonic;self.deadline=time.monotonic()+1000;factories.append(self)
            def check(self):pass
            def fetch(self,url,name,cap):
                is_channel=name.startswith('channel');entry={'url':url,'file':name,'status':'ok','bytes':0};self.log.append(entry)
                if is_channel and fail_channel:
                    entry['status']=type(fail_channel).__name__;raise fail_channel
                body=b'invented-xml' if is_channel else miniseed();self.bytes+=len(body);entry['bytes']=len(body);entry['sha256']=deps.sha(body);(self.root/name).write_bytes(body);return body
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp)
            if cache_waveform is not None:
                p=out/'cached.mseed';p.write_bytes(cache_waveform);plan['cache']={'invented0|ST01':{'waveform':{'path':str(p),'pin':counts.pin(p)}}}
                if corrupt_cache_pin:plan['cache']['invented0|ST01']['waveform']['pin']['sha256']='0'*64
            plan['metadata_requests'],plan['waveform_batches']=selection.queries(plan['events'],CORE,plan['cache'])
            patches=[mock.patch.object(deps,'module',side_effect=lambda n:lib if n=='downloader' else real(n)),mock.patch.object(counts,'xml_inventory',return_value=inventory())]
            if header_error:patches.append(mock.patch.object(counts,'wave_headers',side_effect=header_error))
            with patches[0],patches[1]:
                if header_error:
                    with patches[2]:code=counts.worker(plan,out,'1'*64,'2'*64,time.monotonic()+7200,FakeFetcher)
                else:code=counts.worker(plan,out,'1'*64,'2'*64,time.monotonic()+7200,FakeFetcher)
            manifest=json.loads((out/'manifest.json').read_text());targets=json.loads((out/'target_outcomes.json').read_text());events=json.loads((out/'event_outcomes.json').read_text());summary=json.loads((out/'summary.json').read_text())
            return code,manifest,targets,events,summary,factories[0].log
    def test_channel_failure_does_not_suppress_frozen_waveform_attempt(self):
        exc=urllib.error.HTTPError('https://invented.invalid',404,'invented',{},None)
        code,m,t,e,s,requests=self.worker_run(fail_channel=exc)
        exc.close()
        self.assertEqual(code,0);self.assertEqual([r['file'] for r in requests],['channel_000.xml','waveform_00.mseed']);self.assertEqual(len(e),96)
        self.assertIn('channel_metadata_unresolved',t[0]['error']);self.assertEqual(s['events']['event_denominator'],96);self.assertEqual(s['events']['common_count_available'],0)
    def test_timeout_stops_incomplete_retaining96x3_and_active_slot(self):
        code,m,t,e,s,requests=self.worker_run(fail_channel=TimeoutError('invented20s'))
        self.assertEqual(code,2);self.assertFalse(m['completed']);self.assertEqual(len(e),96);self.assertEqual(len(requests),1);self.assertEqual(t[0]['status'],'incomplete');self.assertFalse(s['scientific_interpretation_allowed'])
    def test_memory_cap_stops_incomplete_without_replacement(self):
        code,m,t,e,s,requests=self.worker_run(header_error=counts.ResourceLimit('invented64MiB'))
        self.assertEqual(code,2);self.assertFalse(m['completed']);self.assertEqual(t[0]['status'],'incomplete');self.assertEqual(len(e),96);self.assertEqual(len(requests),2)
    def test_header_allocation_failure_stops_incomplete(self):
        code,m,t,e,s,requests=self.worker_run(header_error=MemoryError('invented header allocation'))
        self.assertEqual(code,2);self.assertFalse(m['completed']);self.assertEqual(t[0]['status'],'incomplete');self.assertEqual(len(e),96);self.assertFalse(s['scientific_interpretation_allowed']);self.assertEqual(len(requests),2)
    def test_decode_and_analysis_allocation_failures_stop_incomplete(self):
        for name in ('wave_decode','analyze'):
            owner=counts if name=='wave_decode' else screen
            with self.subTest(name=name),mock.patch.object(owner,name,side_effect=MemoryError('invented '+name+' allocation')):
                code,m,t,e,s,requests=self.worker_run()
                self.assertEqual(code,2);self.assertFalse(m['completed']);self.assertEqual(t[0]['status'],'incomplete');self.assertEqual(len(e),96);self.assertFalse(s['scientific_interpretation_allowed']);self.assertEqual(len(requests),2)
    def test_retrieval_and_cached_read_allocation_failures_propagate(self):
        code,m,t,e,s,requests=self.worker_run(fail_channel=MemoryError('invented retrieval allocation'))
        self.assertEqual(code,2);self.assertFalse(m['completed']);self.assertEqual(t[0]['status'],'incomplete');self.assertEqual(len(e),96);self.assertFalse(s['scientific_interpretation_allowed']);self.assertEqual(len(requests),1)
        with mock.patch.object(deps,'read',side_effect=MemoryError('invented cached read allocation')):
            with self.assertRaises(MemoryError):counts.verified_cache_body(Path('invented'),{'bytes':1,'sha256':'0'*64},100)
    def test_successful_counts_do_not_require_response_or_three_stations(self):
        code,m,t,e,s,requests=self.worker_run()
        self.assertEqual(code,0);self.assertEqual(s['events']['common_count_available'],1);self.assertEqual(s['events']['horizons']['1']['full_response_consistent_count_available'],0)
    def test_bad_cached_waveform_decode_does_not_trigger_refetch(self):
        code,m,t,e,s,requests=self.worker_run(cache_waveform=b'invented invalid miniSEED')
        self.assertEqual(code,0);self.assertEqual(len(requests),1);self.assertEqual(t[0]['waveform_source'],'exact_cache');self.assertEqual(t[0]['status'],'unresolved_engineering')
    def test_unrelated_bad_native_batch_does_not_erase_valid_cached_prefix(self):
        real_headers=counts.wave_headers
        def bad_native(path,*args):
            if path.name.startswith('waveform'):raise ValueError('invented bad new batch')
            return real_headers(path,*args)
        code,m,t,e,s,requests=self.worker_run(cache_waveform=miniseed(),second_target=True,header_error=bad_native)
        self.assertEqual(code,0);self.assertEqual(t[0]['waveform_source'],'exact_cache');self.assertTrue(t[0]['horizons']['1']['count_valid']);self.assertFalse(t[1]['horizons']['1']['count_valid']);self.assertEqual(len(requests),3)
    def test_changed_frozen_cache_pin_is_incomplete_provenance_not_waveform_absence(self):
        code,m,t,e,s,requests=self.worker_run(cache_waveform=miniseed(),corrupt_cache_pin=True)
        self.assertEqual(code,2);self.assertFalse(m['completed']);self.assertEqual(t[0]['status'],'incomplete');self.assertEqual(len(requests),1);self.assertFalse(s['scientific_interpretation_allowed'])
    def test_missing_cached_response_and_changed_wave_decode_bytes_raise_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'missing'
            with self.assertRaises(counts.ProvenanceError):counts.xml_inventory(p,{'bytes':1,'sha256':'0'*64})
            p.write_bytes(miniseed());expected=counts.pin(p);declared=counts.wave_headers(p,expected)[0];p.write_bytes(b'changed after headonly')
            with self.assertRaises(counts.ProvenanceError):counts.wave_decode(p,declared,expected)
    def test_inputs_gate_rejected_without_accessing_live_collection(self):
        with mock.patch.object(counts,'local',side_effect=lambda p:Path(p)),mock.patch.object(deps,'read',return_value=b'{"version":"invalid"}') as read:
            with self.assertRaisesRegex(ValueError,'verified completed'):counts.input_objects(Path('invented'))
            self.assertEqual(read.call_count,1)
    def test_output_escape_and_symlink_refused(self):
        with self.assertRaisesRegex(ValueError,'local_runs'):counts.local('/tmp/invented-outside')
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            p=Path(temp)/'f';p.write_bytes(b'hi');q=Path(temp)/'link';q.symlink_to(p)
            with self.assertRaisesRegex(ValueError,'nonsymlink'):deps.read(q,20)
    def test_parent_missing_receipt_cannot_reserve_directory(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            out=Path(temp)/'never'
            with mock.patch.object(counts,'validate',side_effect=ValueError('invented receipt')):
                with self.assertRaisesRegex(ValueError,'receipt'):counts.collect(Path('p'),Path('r'),out)
            self.assertFalse(out.exists())
    def test_nonzero_child_exit_invalidates_even_a_completed_worker_summary(self):
        plan=self.plan();process=mock.Mock(pid=987654);process.poll.return_value=-9
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            out=Path(temp)/'out'
            def stopped_after_manifest(*args,**kwargs):
                counts.checkpoint(out,plan,screen.initial_targets(plan['events']),True)
                counts.dump(out/'manifest.json',{'completed':True,'files':{'summary.json':counts.pin(out/'summary.json')}})
                return -9
            process.wait.side_effect=stopped_after_manifest
            with mock.patch.object(counts,'validate',return_value=(plan,'1'*64,'2'*64)),mock.patch.object(counts,'local',side_effect=lambda p:Path(p)),mock.patch.object(counts.subprocess,'Popen',return_value=process):
                with self.assertRaisesRegex(RuntimeError,'unsuccessfully: -9'):counts.collect(Path('p'),Path('r'),out)
            summary=json.loads((out/'summary.json').read_bytes());manifest=json.loads((out/'manifest.json').read_bytes())
            self.assertFalse(summary['completed']);self.assertFalse(summary['scientific_interpretation_allowed']);self.assertEqual(summary['events']['event_denominator'],96)
            self.assertFalse(manifest['completed']);self.assertTrue(manifest['artifact_pins_incomplete']);self.assertEqual(manifest['worker_exit_code'],-9);self.assertEqual(manifest['files'],{})
            self.assertEqual(len(json.loads((out/'event_outcomes.json').read_bytes())),96);self.assertTrue((out/'outer_interruption.json').exists())
    def test_forced_child_exit_is_awaited_before_recovery_checkpoint_read(self):
        plan=self.plan();process=mock.Mock(pid=987654);process.poll.side_effect=[None,0];process.wait.side_effect=[subprocess.TimeoutExpired('invented',7200),subprocess.TimeoutExpired('invented',5),0]
        real_load=counts.load;timers=[]
        def checked_load(path,*args):
            if path.name in ('manifest.json','target_outcomes.json'):
                self.assertEqual(process.wait.call_count,3);timers.append(signal.getitimer(signal.ITIMER_REAL)[0])
            return real_load(path,*args)
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            out=Path(temp)/'out'
            with mock.patch.object(counts,'validate',return_value=(plan,'1'*64,'2'*64)),mock.patch.object(counts,'local',side_effect=lambda p:Path(p)),mock.patch.object(counts,'load',side_effect=checked_load),mock.patch.object(counts.subprocess,'Popen',return_value=process),mock.patch.object(counts.os,'killpg') as kill:
                with self.assertRaises(subprocess.TimeoutExpired):counts.collect(Path('p'),Path('r'),out)
                self.assertEqual(kill.call_args_list,[mock.call(process.pid,signal.SIGTERM),mock.call(process.pid,signal.SIGKILL)]);self.assertTrue(all(t>0 for t in timers));self.assertEqual(len(json.loads((out/'event_outcomes.json').read_text())),96)
    def test_parent_sigterm_routes_to_cleanup_and_restores_handler(self):
        plan=self.plan();process=mock.Mock(pid=987654);process.poll.side_effect=[None,0];prior=signal.getsignal(signal.SIGTERM)
        def wait(*args,**kwargs):
            if process.wait.call_count==1:counts.os.kill(counts.os.getpid(),signal.SIGTERM)
            self.assertIs(signal.getsignal(signal.SIGTERM),signal.SIG_IGN);return 0
        process.wait.side_effect=wait
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            with mock.patch.object(counts,'validate',return_value=(plan,'1'*64,'2'*64)),mock.patch.object(counts,'local',side_effect=lambda p:Path(p)),mock.patch.object(counts.subprocess,'Popen',return_value=process),mock.patch.object(counts.os,'killpg'):
                with self.assertRaises(counts.Deadline):counts.collect(Path('p'),Path('r'),Path(temp)/'out')
        self.assertIs(signal.getsignal(signal.SIGTERM),prior)

class FrozenTransportTests(unittest.TestCase):
    def test_frozen_post_body_method_and_chunk_accounting(self):
        lib=deps.module('downloader');spec={'file':'invented.mseed','url':'https://invented.invalid/query','method':'POST','post_body':'NZ ST01 -- HH? x y\n','post_body_sha256':selection.digest('NZ ST01 -- HH? x y\n')}
        sock=mock.Mock();raw=types.SimpleNamespace(_sock=sock);response=mock.MagicMock(status=200,headers={'Content-Length':'3'},fp=types.SimpleNamespace(raw=raw));response.__enter__.return_value=response;response.read1.side_effect=[b'abc',b'']
        opener=mock.Mock();opener.open.return_value=response
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(transport.urllib.request,'build_opener',return_value=opener):
            f=transport.factory(lib,time.monotonic(),[spec])(Path(temp),request_alarm=False)
            self.assertEqual(f.fetch(spec['url'],spec['file'],100),b'abc');request=opener.open.call_args.args[0]
            self.assertEqual(request.get_method(),'POST');self.assertEqual(request.data,spec['post_body'].encode('ascii'));self.assertEqual(f.log[0]['post_body_sha256'],spec['post_body_sha256']);self.assertEqual(f.bytes,3)
    def test_frozen_post_body_mutation_is_rejected_before_connection(self):
        lib=deps.module('downloader');spec={'file':'invented.mseed','url':'https://invented.invalid/query','method':'POST','post_body':'changed','post_body_sha256':'0'*64};opener=mock.Mock()
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(transport.urllib.request,'build_opener',return_value=opener):
            f=transport.factory(lib,time.monotonic(),[spec])(Path(temp),request_alarm=False)
            with self.assertRaisesRegex(ValueError,'POST body'):f.fetch(spec['url'],spec['file'],100)
            opener.open.assert_not_called()

class ExactCacheTests(unittest.TestCase):
    def fixture(self,temp,kind='dataselect',window_shift=0,status='ok',url_suffix=''):
        wave=Path(temp)/'old';root=wave/'local_runs/audit';raw=root/'raw';raw.mkdir(parents=True)
        e=event();envelope=selection.envelope(e,e['targets'][0],CORE)
        if window_shift:envelope['starttime']=CORE.iso(window_shift*CORE.NS)
        import urllib.parse
        extra={'format':'miniseed'} if kind=='dataselect' else {'level':'response','format':'xml'}
        url='https://service.geonet.org.nz/fdsnws/'+kind+'/1/query?'+urllib.parse.urlencode(envelope|extra)+url_suffix;name='001.mseed' if kind=='dataselect' else '000.xml'
        body=b'invented retrieval, not decoded samples';(raw/name).write_bytes(body);bodypin={'bytes':len(body),'sha256':deps.sha(body)}
        original_wave=counts.WAVE
        for n in ('audit.py','core.py','PROTOCOL_v1.md','census_input_pins.json'):(wave/n).write_bytes((original_wave/n).read_bytes())
        source={n:deps.sha((wave/n).read_bytes()) for n in ('audit.py','core.py','PROTOCOL_v1.md','census_input_pins.json')}
        plan={'requests':[{'event_id':e['event_id'],'station':'ST01','kind':kind,'url':url,'file':name}],'source_files':source}
        paths={n:root/(n+'.json') for n in ('plan','parent_receipt','requests','manifest')}
        counts.dump(paths['plan'],plan);plan_sha=deps.sha(paths['plan'].read_bytes())
        counts.dump(paths['parent_receipt'],{'plan_sha256':plan_sha,'source_files':source,'dependency_receipt_sha256':deps.pins()['dependency_receipt']['sha256'],'acquisition_authorized':True,'code_only_review_clean':True,'parent_pre_acquisition_commit':'a'*40})
        counts.dump(paths['requests'],[dict(bodypin,file=name,url=url,status=status,http_status=200)])
        counts.dump(paths['manifest'],{'completed':True,'plan_sha256':plan_sha,'parent_receipt_sha256':deps.sha(paths['parent_receipt'].read_bytes()),'files':{'raw/'+name:bodypin,'requests.json':counts.pin(paths['requests'])}})
        config={'root':str(root),'files':{n:{'path':str(p),'sha256':deps.sha(p.read_bytes())} for n,p in paths.items()}}
        return wave,{'cache':config},[e],raw/name
    def test_exact_semantic_get_to_post_body_cache_and_method_provenance(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            wave,inputs,events,path=self.fixture(temp)
            with mock.patch.object(counts,'WAVE',wave):cache,provenance=counts.cached_candidates(inputs,events,CORE)
            hit=cache['invented0|ST01']['waveform'];self.assertEqual(hit['original_method'],'GET');self.assertEqual(hit['method_difference'],'GET_to_POST_selection_equivalence')
            meta,batches=selection.queries(events,CORE,cache);self.assertEqual(len(meta),1);self.assertEqual(batches[0]['slots'],[])
    def test_overlapping_but_different_window_never_matches(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            wave,inputs,events,path=self.fixture(temp,window_shift=-1)
            with mock.patch.object(counts,'WAVE',wave):cache,_=counts.cached_candidates(inputs,events,CORE)
            self.assertEqual(cache,{})
    def test_blank_extra_or_duplicate_query_keys_never_match_exact_cache(self):
        for suffix in ('&extra=','&channel=','#invented'):
            with self.subTest(suffix=suffix),tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
                wave,inputs,events,path=self.fixture(temp,url_suffix=suffix)
                with mock.patch.object(counts,'WAVE',wave):cache,_=counts.cached_candidates(inputs,events,CORE)
                self.assertEqual(cache,{})
    def test_failed_or_partial_retrieval_is_not_successbytes(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            wave,inputs,events,path=self.fixture(temp,status='TimeoutError')
            with mock.patch.object(counts,'WAVE',wave):cache,_=counts.cached_candidates(inputs,events,CORE)
            self.assertEqual(cache,{})
    def test_response_level_body_is_never_channel_get_cache_hit(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            wave,inputs,events,path=self.fixture(temp,kind='station')
            with mock.patch.object(counts,'WAVE',wave):cache,_=counts.cached_candidates(inputs,events,CORE)
            self.assertEqual(set(cache['invented0|ST01']),{'response'});self.assertEqual(len(selection.queries(events,CORE,cache)[0]),1)
    def test_corrupted_pinned_success_body_stops_preparation(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            wave,inputs,events,path=self.fixture(temp);path.write_bytes(b'changed')
            with mock.patch.object(counts,'WAVE',wave):
                with self.assertRaisesRegex(ValueError,'body/member'):counts.cached_candidates(inputs,events,CORE)
    def test_changed_ledger_claim_cannot_override_original_manifest_status_pin(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            wave,inputs,events,path=self.fixture(temp,status='TimeoutError');ledger=Path(inputs['cache']['files']['requests']['path']);entries=json.loads(ledger.read_bytes());entries[0]['status']='ok';counts.dump(ledger,entries);inputs['cache']['files']['requests']['sha256']=deps.sha(ledger.read_bytes())
            with mock.patch.object(counts,'WAVE',wave):
                with self.assertRaisesRegex(ValueError,'ledger differs'):counts.cached_candidates(inputs,events,CORE)
    def test_identical_ledger_at_another_run_path_is_not_the_original_member(self):
        with tempfile.TemporaryDirectory(dir=counts.BASE) as temp:
            wave,inputs,events,path=self.fixture(temp);original=Path(inputs['cache']['files']['requests']['path']);other=original.parent/'other.json';other.write_bytes(original.read_bytes());inputs['cache']['files']['requests']['path']=str(other)
            with mock.patch.object(counts,'WAVE',wave):
                with self.assertRaisesRegex(ValueError,'another run'):counts.cached_candidates(inputs,events,CORE)

if __name__=='__main__':unittest.main(verbosity=2)

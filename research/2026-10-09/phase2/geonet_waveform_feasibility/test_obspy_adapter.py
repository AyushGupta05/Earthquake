"""Invented local public-API round trips; never real inventory or waveforms."""
import copy
import io
import unittest
import json
from pathlib import Path
import tempfile
import time
import types
import sys
import obspy
import warnings
from unittest.mock import patch
import numpy as np
from obspy import Stream, Trace, UTCDateTime, read, read_inventory
from obspy.core.inventory import Inventory, Network, Station, Channel, Site
from obspy.core.inventory.response import Response
import audit
import core


T0=UTCDateTime('2020-01-01T00:00:00Z')
TARGET={'network':'NZ','station':'AAA','location':'10','prefix':'HH','pick_ns':T0.ns,'queryable':True}
EVENT={'t0_ns':T0.ns}


def inventory():
    response=Response.from_paz(zeros=[0j], poles=[-1+0j], stage_gain=1000.,
        stage_gain_frequency=1., input_units='M/S', output_units='COUNTS',
        normalization_frequency=1.)
    channels=[Channel(code='HH'+suffix,location_code='10',latitude=-40.,longitude=175.,
        elevation=0.,depth=0.,azimuth=azimuth,dip=dip,sample_rate=100.,
        start_date=T0-10,end_date=None,response=copy.deepcopy(response))
        for suffix,azimuth,dip in (('E',90.,0.),('N',0.,0.),('Z',0.,-90.))]
    station=Station(code='AAA',latitude=-40.,longitude=175.,elevation=0.,
        channels=channels,site=Site(name='Invented synthetic station'),start_date=T0-100)
    return Inventory(networks=[Network(code='NZ',stations=[station],start_date=T0-100)],source='Invented fixtures')


def stream():
    traces=[]
    for i,suffix in enumerate('ENZ'):
        traces.append(Trace(data=(np.arange(1101,dtype=np.int32)+i*2000), header={
            'network':'NZ','station':'AAA','location':'10','channel':'HH'+suffix,
            'sampling_rate':100.,'starttime':T0-5}))
    return Stream(traces=traces)


class ObsPyAdapterTests(unittest.TestCase):
    def test_public_miniseed_and_stationxml_roundtrip(self):
        st=stream(); wave=io.BytesIO(); st.write(wave,format='MSEED',encoding='INT32')
        headers=read(io.BytesIO(wave.getvalue()),format='MSEED',headonly=True,details=True)
        decoded=read(io.BytesIO(wave.getvalue()),format='MSEED',details=True)
        self.assertEqual(sum(tr.stats.npts for tr in headers),3303)
        self.assertEqual(len(decoded),3)
        for before,after in zip(st,decoded):
            self.assertTrue(np.array_equal(before.data,after.data)); self.assertEqual(before.id,after.id)
            self.assertEqual(before.stats.starttime.ns,after.stats.starttime.ns)
        inv=inventory(); xml=io.BytesIO(); inv.write(xml,format='STATIONXML',validate=True)
        parsed=read_inventory(io.BytesIO(xml.getvalue()),format='STATIONXML')
        result=audit.analyze(parsed,decoded,EVENT,TARGET)
        for horizon in ('1','3','5'):
            row=result[horizon]; self.assertEqual(row['status'],'audited')
            self.assertTrue(row['three_component_prefix_available']); self.assertTrue(row['clipping_screen_passed'])
            self.assertFalse(row['physically_calibrated_prefix_verified'])
            self.assertEqual(row['components']['HHE']['samples'],(5+int(horizon))*100)
            for response in row['responses'].values():
                self.assertTrue(response['full_transfer_response_available'])
                self.assertFalse(response['physically_calibrated_prefix_verified'])
                self.assertGreater(response['transfer_magnitude_at_reference'],0)

    def test_all_horizons_future_suffix_poison_changes_no_prefix_results(self):
        inv=inventory(); baseline=audit.analyze(inv,stream(),EVENT,TARGET)
        for horizon in (1,3,5):
            mutated=stream()
            for trace in mutated:
                trace.data=trace.data.astype(np.float64)
                cut=(5+horizon)*100
                trace.data[cut:]=np.nan
                trace.data[-1]=1e100
            actual=audit.analyze(inv,mutated,EVENT,TARGET)
            self.assertEqual(actual[str(horizon)],baseline[str(horizon)])
        # A second entirely future record cannot create a prefix gap or bad rate.
        mutated=stream(); extra=mutated[0].copy(); extra.stats.starttime=T0+6
        extra.data=np.full(10,np.nan); mutated+=extra
        self.assertEqual(audit.analyze(inv,mutated,EVENT,TARGET),baseline)

    def test_same_rate_half_sample_shift_fails_three_component_alignment(self):
        st=stream(); st.select(channel='HHN')[0].stats.starttime+=0.005
        result=audit.analyze(inventory(),st,EVENT,TARGET)
        for row in result.values():
            self.assertEqual(row['status'],'audited')
            self.assertTrue(all(c['available'] for c in row['components'].values()))
            self.assertFalse(row['three_component_prefix_available'])

    def test_event_epoch_boundaries_and_future_epoch_do_not_change_earlier_prefix(self):
        inv=inventory(); inv[0][0][0].end_date=T0+1
        future=copy.deepcopy(inv[0][0][0]); future.start_date=T0+1; future.end_date=None
        inv[0][0].channels.append(future)
        result=audit.analyze(inv,stream(),EVENT,TARGET)
        self.assertEqual(result['1']['status'],'audited')
        self.assertEqual(result['3']['status'],'failed'); self.assertIn('ambiguous',result['3']['error'])
        missing=inventory(); missing[0][0][0].start_date=T0-4
        for row in audit.analyze(missing,stream(),EVENT,TARGET).values():
            self.assertEqual(row['status'],'failed'); self.assertIn('span',row['error'])

    def test_network_epoch_narrows_effective_channel_epoch(self):
        inv=inventory(); inv[0].end_date=T0+1
        result=audit.analyze(inv,stream(),EVENT,TARGET)
        self.assertEqual(result['1']['status'],'audited')
        self.assertEqual(result['3']['status'],'failed'); self.assertIn('span',result['3']['error'])

    def test_future_missing_orientation_ignored_until_its_epoch(self):
        inv=inventory(); baseline=audit.analyze(inv,stream(),EVENT,TARGET)
        future=copy.deepcopy(inv[0][0][0]);future.start_date=T0+6;future.azimuth=None;future.sample_rate=None
        inv[0][0].channels.append(future)
        self.assertEqual(audit.analyze(inv,stream(),EVENT,TARGET),baseline)
        inv[0][0][0].azimuth=None
        for row in audit.analyze(inv,stream(),EVENT,TARGET).values():
            self.assertEqual(row['status'],'failed');self.assertIn('rate/orientation',row['error'])

    def test_future_parent_epoch_with_missing_channel_start_ignored(self):
        inv=inventory();baseline=audit.analyze(inv,stream(),EVENT,TARGET)
        future=copy.deepcopy(inv[0]);future.start_date=T0+6
        for channel in future[0]:channel.start_date=None
        inv.networks.append(future)
        self.assertEqual(audit.analyze(inv,stream(),EVENT,TARGET),baseline)
        missing=inventory();missing[0][0][0].start_date=None
        for row in audit.analyze(missing,stream(),EVENT,TARGET).values():
            self.assertEqual(row['status'],'failed');self.assertIn('span',row['error'])

    def test_response_warnings_retained_after_later_component_failure(self):
        for failure in ('exception','nonfinite'):
            inv=inventory();e=inv[0][0][0].response;n=inv[0][0][1].response
            original=e.get_evalresp_response_for_frequencies
            def earlier(*args,**kwargs):
                warnings.warn('invented successful E warning');return original(*args,**kwargs)
            def later(*args,**kwargs):
                warnings.warn('invented failing N warning')
                if failure=='exception':raise RuntimeError('invented evalresp failure')
                return [complex(float('nan'),0)]
            with patch.object(e,'get_evalresp_response_for_frequencies',side_effect=earlier),patch.object(n,'get_evalresp_response_for_frequencies',side_effect=later):
                result=audit.analyze(inv,stream(),EVENT,TARGET)
            for row in result.values():
                self.assertEqual(row['status'],'failed')
                self.assertEqual(row['responses']['HHE']['warnings'],['invented successful E warning'])
                self.assertEqual(row['responses']['HHN']['warnings'],['invented failing N warning'])
                self.assertFalse(row['responses']['HHN']['full_transfer_response_available'])
                json.dumps(row,allow_nan=False)

    def test_physical_units_and_missing_response_fail(self):
        for change in ('units','response'):
            inv=inventory()
            if change=='units': inv[0][0][0].response.instrument_sensitivity.input_units='VOLTS'
            else: inv[0][0][0].response=None
            for row in audit.analyze(inv,stream(),EVENT,TARGET).values():
                self.assertEqual(row['status'],'failed')

    def test_budget_exception_never_becomes_negative_horizon_result(self):
        class LimitReached(Exception): pass
        with patch.object(audit,'response_evidence',side_effect=LimitReached('invented budget')):
            with self.assertRaises(LimitReached):
                audit.analyze(inventory(),stream(),EVENT,TARGET,LimitReached)

    def test_worker_partial_transfer_cap_retains_all_frozen_targets(self):
        class LimitReached(Exception): pass
        class LimitedFetcher:
            def __init__(self,*args,**kwargs):
                self.log=[]; self.bytes=0; self.clock=time.monotonic; self.started=self.clock()
            def fetch(self,url,file,cap):
                self.log.append({'status':'partial_body_cap','bytes':7}); self.bytes+=7
                raise LimitReached('invented transfer cap')
        events=[dict(EVENT,event_id=f'invented{i}',stations=[dict(TARGET,station=s) for s in ('AAA','BBB','CCC')]) for i in range(6)]
        plan={'events':events,'requests':audit.requests_for(events)}
        module=types.SimpleNamespace(Fetcher=LimitedFetcher,LimitReached=LimitReached,alarm_handler=audit.outer_alarm)
        with tempfile.TemporaryDirectory() as tmp, patch.object(audit,'local_path',lambda p:p), patch.object(audit,'validate_execution',return_value=plan), patch.object(audit,'downloader',return_value=module):
            root=Path(tmp); plan_path=root/'plan'; receipt_path=root/'receipt'; out=root/'out'
            plan_path.write_text('{}');receipt_path.write_text('{}')
            self.assertEqual(audit.worker(plan_path,receipt_path,out),2)
            rows=json.loads((out/'outcomes.json').read_text()); manifest=json.loads((out/'manifest.json').read_text())
            self.assertEqual(len(rows),18); self.assertEqual(rows[0]['status'],'incomplete_stationxml')
            self.assertTrue(all(r['status']=='unattempted' for r in rows[1:]))
            self.assertFalse(manifest['completed']);self.assertEqual(manifest['response_body_bytes'],7)
            self.assertEqual(manifest['request_attempts'],1)

    def test_full_parent_gate_validates_frozen_query_and_dependency_bindings(self):
        from test_audit import metadata
        groups,outcomes=metadata(); pins={'invented_input.json':'0'*64}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in audit.BINDINGS: (root/name).write_text('invented '+name)
            for name in ('requirements.lock','dependency_wheels_receipt.json'): (root/name).write_text('invented '+name)
            files={name:audit.sha((root/name).read_bytes()) for name in audit.BINDINGS}
            dependency={'synthetic_adapter_smoke_passed':True,'obsPy_version':obspy.__version__,'numpy_version':np.__version__,
                'python_executable':str(Path(sys.executable).absolute()),'dependency_lock_sha256':audit.sha((root/'requirements.lock').read_bytes()),
                'published_wheels_receipt_sha256':audit.sha((root/'dependency_wheels_receipt.json').read_bytes()),'installed_resolved_packages':{'inventedpkg':'1.2.3'}}
            audit.dump(root/'dependency_receipt.json',dependency)
            events=core.choose(groups,outcomes)
            plan={'version':core.VERSION,'limits':{'seconds':1800,'requests':100,'body_bytes':128*1024*1024},
                'input_root':str(root),'input_pins':pins,'events':events,'requests':audit.requests_for(events),'source_files':files}
            plan_path=root/'plan'; receipt_path=root/'receipt'; audit.dump(plan_path,plan)
            receipt={'acquisition_authorized':True,'parent_pre_acquisition_commit':'a'*40,'code_only_review_clean':True,
                'plan_sha256':audit.sha(plan_path.read_bytes()),'source_files':files,'dependency_receipt_sha256':audit.sha((root/'dependency_receipt.json').read_bytes())}
            audit.dump(receipt_path,receipt)
            dist=types.SimpleNamespace(version='1.2.3',locate_file=lambda _:root/'.venv/lib/site-packages')
            with patch.object(audit,'BASE',root), patch.object(audit,'local_path',lambda p:p), patch.object(audit,'census_inputs',return_value=({'groups.json':groups,'outcomes.json':outcomes},pins)), patch.object(audit.importlib.metadata,'distribution',return_value=dist):
                self.assertEqual(audit.validate_execution(plan_path,receipt_path),plan)
                changed=copy.deepcopy(plan); changed['requests'][0]['url']='https://invalid.example/';audit.dump(plan_path,changed)
                receipt['plan_sha256']=audit.sha(plan_path.read_bytes());audit.dump(receipt_path,receipt)
                with self.assertRaisesRegex(ValueError,'query list'):audit.validate_execution(plan_path,receipt_path)
                audit.dump(plan_path,plan);receipt['plan_sha256']=audit.sha(plan_path.read_bytes());audit.dump(receipt_path,receipt)
                dist.version='9.9.9'
                with self.assertRaisesRegex(ValueError,'dependency changed'):audit.validate_execution(plan_path,receipt_path)


if __name__=='__main__': unittest.main()

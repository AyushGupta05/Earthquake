import math
import io
import json
import tarfile
import tempfile
from pathlib import Path
from dataclasses import dataclass
from unittest.mock import patch
from types import SimpleNamespace
import unittest
import numpy as np
from obspy.core.inventory.response import Response, InstrumentSensitivity, PolesZerosResponseStage, CoefficientsTypeResponseStage
from audit_response import (evaluate_response, descriptor_for_channel, covering_epoch, FREQUENCIES, canonical_unit, load_archive, sha, atomic_json, finite_json)


def fixture():
    pz=PolesZerosResponseStage(stage_sequence_number=1, stage_gain=3, stage_gain_frequency=1,
        input_units='M/S',output_units='V',pz_transfer_function_type='LAPLACE (RADIANS/SECOND)',
        normalization_frequency=1,zeros=[],poles=[-2*math.pi+0j],normalization_factor=2*math.pi*math.sqrt(2))
    gain=CoefficientsTypeResponseStage(stage_sequence_number=2,stage_gain=2,stage_gain_frequency=1,
        input_units='V',output_units='COUNTS',cf_transfer_function_type='DIGITAL',numerator=[],denominator=[],
        decimation_input_sample_rate=100,decimation_factor=1,decimation_offset=0,decimation_delay=0,decimation_correction=0)
    return Response(instrument_sensitivity=InstrumentSensitivity(6,1,'M/S','COUNTS'),response_stages=[pz,gain])


class ResponseTests(unittest.TestCase):
    def test_analytic_chain_no_sensitivity_double_multiplication(self):
        value=evaluate_response(fixture());self.assertTrue(value['valid_response'],value)
        actual=np.array(value['transfer_real'])+1j*np.array(value['transfer_imag'])
        expected=6*math.sqrt(2)/(1+1j*FREQUENCIES)
        np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-12)
        self.assertLess(value['stage_product_relative_error'],1e-12)
        self.assertLess(value['grid_relative_error'],1e-12)
        self.assertAlmostEqual(value['calibration_gain_ratio'],1)

    def test_rate_mask_and_zero_fallback(self):
        r=fixture();r.response_stages[-1].decimation_factor=5
        value=evaluate_response(r);d=descriptor_for_channel(value,20)
        np.testing.assert_array_equal(d[:,3],[1,1,1,1,0,0])
        np.testing.assert_array_equal(d[4:],np.zeros((2,4)))
        for fs in (None,0,-1,float('nan')):
            np.testing.assert_array_equal(descriptor_for_channel(value,fs),np.zeros((6,4)))

    def test_channel_rate_mismatch_fails_closed(self):
        value=evaluate_response(fixture())
        self.assertFalse(descriptor_for_channel(value,50).any())

    def test_inconsistent_sensitivity_fails_closed(self):
        r=fixture();r.instrument_sensitivity.value=20
        value=evaluate_response(r)
        self.assertFalse(value['valid_response'])
        self.assertIn('reported_fullstage_sensitivity_mismatch_gt5pct',value['reasons'])
        self.assertFalse(descriptor_for_channel(value,100).any())

    def test_stage_units_and_numbers_rejected(self):
        r=fixture();r.response_stages[1].input_units='M/S'
        self.assertIn('stage_unit_discontinuity',evaluate_response(r)['reasons'])
        r=fixture();r.response_stages[1].stage_sequence_number=3
        self.assertIn('noncontiguous_stage_numbers',evaluate_response(r)['reasons'])

    def test_gain_reexpression_shape_descriptor_invariant(self):
        a=fixture();b=fixture();b.instrument_sensitivity.value*=7;b.response_stages[-1].stage_gain*=7
        va,vb=evaluate_response(a),evaluate_response(b)
        self.assertTrue(va['valid_response']);self.assertTrue(vb['valid_response'])
        np.testing.assert_allclose(descriptor_for_channel(va,100),descriptor_for_channel(vb,100),rtol=1e-12,atol=1e-12)

    def test_whole_interval_and_touch_ambiguity(self):
        def e(a,b):return SimpleNamespace(start=a,end=b,usable=True)
        self.assertEqual(covering_epoch([e(0,10)],1,9)[0],'matched')
        self.assertEqual(covering_epoch([e(0,5)],1,9)[0],'partial_epoch_cover')
        self.assertEqual(covering_epoch([e(0,5),e(5,10)],1,5)[0],'multiple_overlapping_epochs')
        self.assertEqual(covering_epoch([e(2,1)],0,9)[0],'outside_epoch')
        self.assertEqual(covering_epoch([],1,2)[0],'no_channel_key')
        self.assertEqual(covering_epoch([],float('nan'),2)[0],'invalid_window')

    def test_missing_response_archive_json_and_join_key_roundtrip(self):
        from obspy.core.inventory import Inventory, Network, Station, Channel, Site
        @dataclass
        class Epoch:
            channel: str
            sample_rate_hz: float = 100.
            @property
            def key(self): return ('XX','SYN','',self.channel)
        channels=[Channel(code=code,location_code='',latitude=0,longitude=0,elevation=0,
                          depth=0,sample_rate=100,response=response)
                  for code,response in [('HHE',fixture()),('HHN',None)]]
        inventory=Inventory([Network(code='XX',stations=[Station(code='SYN',latitude=0,
            longitude=0,elevation=0,site=Site(name='synthetic'),channels=channels)])],source='synthetic')
        stream=io.BytesIO();inventory.write(stream,format='STATIONXML');content=stream.getvalue()
        module=SimpleNamespace(parse_xml=lambda root,name:[Epoch('HHE'),Epoch('HHN')])
        with tempfile.TemporaryDirectory() as d:
            archive=Path(d)/'fixture.tgz'
            with tarfile.open(archive,'w:gz') as tar:
                info=tarfile.TarInfo('fixture.xml');info.size=len(content);tar.addfile(info,io.BytesIO(content))
            with patch('audit_response.ARCHIVE_SHA',sha(archive)):
                epochs,responses,_,_=load_archive(archive,module)
            atomic_json(Path(d)/'responses.json',finite_json(responses))
            restored=json.loads((Path(d)/'responses.json').read_text())
            for _,record in epochs:
                self.assertIn(record['response_id'],restored)
            missing=epochs[1][1]
            self.assertEqual(missing['response_id'],'missing_response')
            self.assertEqual(restored[missing['response_id']]['reasons'],['no_response'])
            self.assertFalse(np.asarray(missing['descriptor']).any())

    def test_missing_scalar_sensitivity_fields_fail_closed(self):
        for field in ('value','frequency'):
            r=fixture();setattr(r.instrument_sensitivity,field,None)
            value=evaluate_response(r)
            self.assertEqual(value['reasons'],['invalid_scalar_sensitivity'])
            self.assertFalse(descriptor_for_channel(value,100).any())

    def test_unresolved_digital_clock_rejected_but_analog_allowed(self):
        pz=PolesZerosResponseStage(stage_sequence_number=1,stage_gain=1,stage_gain_frequency=1,
            input_units='M/S',output_units='COUNTS',pz_transfer_function_type='DIGITAL (Z-TRANSFORM)',
            normalization_frequency=1,zeros=[],poles=[],normalization_factor=1)
        r=Response(instrument_sensitivity=InstrumentSensitivity(1,1,'M/S','COUNTS'),response_stages=[pz])
        value=evaluate_response(r)
        self.assertIn('digital_sampling_clock_unresolved',value['reasons'])
        self.assertFalse(descriptor_for_channel(value,100).any())
        pz.pz_transfer_function_type='LAPLACE (RADIANS/SECOND)'
        self.assertTrue(evaluate_response(r)['valid_response'])

    def test_unknown_unit_and_missing_stages(self):
        r=fixture();r.instrument_sensitivity.input_units='PA'
        self.assertIn('unsupported_units',evaluate_response(r)['reasons'])
        r=fixture();r.response_stages=[]
        self.assertEqual(evaluate_response(r)['reasons'],['missing_sensitivity_or_stages'])
        self.assertEqual(canonical_unit('M/S**2'),'M/S^2')


if __name__=='__main__':unittest.main()

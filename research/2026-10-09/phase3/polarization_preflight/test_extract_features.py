import importlib.util
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
import h5py

import extract_features as extract


def inventory_module():
    here = Path(__file__).resolve().parent
    paths = [here/'context/instrument_inventory.py',
             here.parent/'repo/research/2026-10-09/phase2/instrument_inventory.py']
    path = next(p for p in paths if p.exists())
    spec = importlib.util.spec_from_file_location('fixture_inventory', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.module = inventory_module()
        self.row = {'source_id':'fixture-event', 'trace_name':'fixture-trace.N.S..HH',
                    'trace_start_time':'2020-01-01T00:00:00Z','trace_P_arrival_sample':'200',
                    'trace_dt_s':'.01','trace_npts':'700','station_network_code':'N',
                    'station_code':'S','station_location_code':'','station_channels':'HH',
                    'station_elevation_m':'1','station_vs_30_mps':'500',
                    'source_magnitude':'4','path_hyp_distance_km':'10','source_depth_km':'3'}
        timestamp = self.module.utc_seconds(self.row['trace_start_time'])
        self.epochs = [self.module.Epoch('N','S','','HH'+c,timestamp-1,timestamp+20,
                       100.,1.,'M/S','COUNTS',100.,az,dip,0.,0.,1.,'sensor','fixture')
                       for c,az,dip in [('E',90.,0.),('N',0.,0.),('Z',0.,-90.)]]
        self.inventory = self.module.Inventory(self.epochs)

    def test_metadata_and_static_allowlist(self):
        reason, response = extract.metadata_reason(self.row,self.inventory,self.module)
        self.assertIsNone(reason)
        static, gain, units = extract.static_and_response(self.row,self.inventory,self.module)
        altered = dict(self.row, source_magnitude='8',source_depth_km='200',path_hyp_distance_km='500')
        other, _, _ = extract.static_and_response(altered,self.inventory,self.module)
        np.testing.assert_array_equal(static,other)
        self.assertEqual(static.shape,(34,))
        np.testing.assert_array_equal(gain,[100]*3)
        self.assertEqual(units,['m/s']*3)

    def test_invalid_metadata_and_orientation(self):
        for key,value,reason in [('trace_P_arrival_sample','199','window'),
                                 ('trace_dt_s','.02','window'),('source_depth_km','-1','target'),
                                 ('source_magnitude','nan','target'),('source_id','','identity')]:
            self.assertEqual(extract.metadata_reason(dict(self.row,**{key:value}),self.inventory,self.module)[0],reason)
        from dataclasses import replace
        inventory = self.module.Inventory([replace(self.epochs[0],azimuth_deg=0),*self.epochs[1:]])
        self.assertEqual(extract.metadata_reason(self.row,inventory,self.module)[0],'orientation')

    def test_mixed_unit_and_competing_epoch_fail_closed(self):
        from dataclasses import replace
        inventory = self.module.Inventory([replace(self.epochs[0],input_units='M/S**2'),*self.epochs[1:]])
        self.assertEqual(extract.metadata_reason(self.row,inventory,self.module)[0],'units')
        inventory = self.module.Inventory(self.epochs+[replace(self.epochs[0],start=self.epochs[0].start+5)])
        self.assertEqual(extract.metadata_reason(self.row,inventory,self.module)[0],'response')

    def test_covering_epoch_not_trace_start_epoch(self):
        from dataclasses import replace
        row = dict(self.row,trace_P_arrival_sample='500',trace_npts='1000')
        timestamp = self.module.utc_seconds(row['trace_start_time'])
        epochs = [replace(e,start=timestamp+2,end=timestamp+30,sensitivity=200.) for e in self.epochs]
        epochs += [replace(e,end=timestamp+1,sensitivity=100.) for e in self.epochs]
        _, gain, _ = extract.static_and_response(row,self.module.Inventory(epochs),self.module)
        np.testing.assert_array_equal(gain,[200]*3)

    def test_metadata_eligible_unknown_family_has_static_features(self):
        from dataclasses import replace
        row = dict(self.row,station_channels='BH',trace_name='fixture-trace.N.S..BH')
        epochs = [replace(e,channel='BH'+e.channel[-1]) for e in self.epochs]
        inventory = self.module.Inventory(epochs)
        self.assertIsNone(extract.metadata_reason(row,inventory,self.module)[0])
        static, gain, units = extract.static_and_response(row,inventory,self.module)
        np.testing.assert_array_equal(static[:6],[0,0,0,0,0,1])
        np.testing.assert_array_equal(gain,[100]*3)

    def test_actual_hdf_prefix_validity_and_no_other_trace_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.h5'
            rng = np.random.default_rng(123)
            waveform = rng.normal(size=(3,700))
            waveform[:,300:] = np.nan
            with h5py.File(path,'w') as raw:
                raw.create_dataset('data/'+self.row['trace_name'],data=waveform)
                raw.create_dataset('data/forbidden-VAL-fixture',data=np.zeros((1,1)))
            with h5py.File(path,'r') as raw:
                values, invalid, degenerate = extract.extract_record(raw,self.row,np.ones(3),['m/s']*3,np.zeros(34))
            self.assertEqual(invalid.tolist(),[0,2,2])
            self.assertTrue(np.isfinite(values[0]).all())
            self.assertTrue(np.isnan(values[1:]).all())

    def test_missing_trace_wrong_shape_and_path_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with h5py.File(Path(directory)/'fixture.h5','w') as raw:
                raw.create_group('data')
                args = (np.ones(3),['m/s']*3,np.zeros(34))
                _, invalid, _ = extract.extract_record(raw,self.row,*args)
                self.assertEqual(invalid.tolist(),[128]*3)
                raw.create_dataset('data/'+self.row['trace_name'],shape=(3,699),dtype='f8')
                _, invalid, _ = extract.extract_record(raw,self.row,*args)
                self.assertEqual(invalid.tolist(),[256]*3)
                with self.assertRaises(ValueError):
                    extract.extract_record(raw,dict(self.row,trace_name='../outside'),*args)

    def test_cache_config_and_format(self):
        config = SimpleNamespace()
        assigned = []
        fake = SimpleNamespace(id=SimpleNamespace(get_mdc_config=lambda:config,set_mdc_config=assigned.append))
        extract.configure_cache(fake)
        self.assertIs(assigned[0],config)
        self.assertEqual(config.initial_size,128*1024*1024)
        self.assertEqual(config.max_size,config.min_size)
        with tempfile.TemporaryDirectory() as directory:
            with h5py.File(Path(directory)/'fixture.h5','w') as raw:
                for key,value in [('component_order','ENZ'),('dimension_order','CW'),('unit','counts'),('instrument_response','not restituted')]:
                    raw.create_dataset('data_format/'+key,data=np.bytes_(value))
                self.assertEqual(extract.verify_format(raw)['component_order'],'ENZ')
                del raw['data_format/component_order']
                raw.create_dataset('data_format/component_order',data=np.bytes_('ZNE'))
                with self.assertRaises(ValueError):
                    extract.verify_format(raw)

    def test_dry_run_does_not_access_real_paths(self):
        with patch.object(sys,'argv',['extract_features.py','--output','/unused/fixture']), \
             patch.object(extract,'sha',side_effect=AssertionError('Read real path')), \
             patch('builtins.print') as output:
            extract.main()
            self.assertIn('"execute": false',output.call_args.args[0])


if __name__ == '__main__':
    unittest.main()

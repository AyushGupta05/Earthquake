import unittest
from types import SimpleNamespace
import numpy as np
from join_train_metadata import window,row_join
from audit_response import load_module
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'repo/research/2026-10-09/phase2/instrument_inventory.py'
INV=load_module('test_join_inventory',ROOT)


def fixture():
    row={'source_row_index':'0','source_id':'E','trace_name':'E.IV.A..HH','trace_start_time':'2020-01-01T00:00:00Z',
         'trace_P_arrival_sample':'200','trace_dt_s':'.01','trace_npts':'700','station_network_code':'IV',
         'station_code':'A','station_location_code':'','station_channels':'HH'}
    ts=INV.utc_seconds(row['trace_start_time']);index={};details={}
    for c in 'ENZ':
        e=SimpleNamespace(start=ts,end=ts+7,usable=True,input_units='M/S',dip_deg=-90 if c=='Z' else 0,
                          azimuth_deg=90 if c=='E' else 0)
        index[('IV','A','', 'HH'+c)]=[e]
        details[id(e)]={'epoch_id':'epoch'+c,'response_id':'response'+c,'descriptor':np.ones((6,4)).tolist(),'response_reasons':[]}
    return row,index,details


class JoinTests(unittest.TestCase):
    def test_valid_boundary_and_strict_identity(self):
        row,index,details=fixture();v=row_join(row,index,details,INV);self.assertTrue(v['metadata_eligible'])
        row['source_id']='wrong'
        with self.assertRaises(ValueError):row_join(row,index,details,INV)

    def test_no_future_quality_in_metadata_gate(self):
        row,index,details=fixture()
        details[next(iter(details))]['descriptor']=np.zeros((6,4)).tolist()
        self.assertTrue(row_join(row,index,details,INV)['metadata_eligible'])
        self.assertEqual(row_join(row,index,details,INV)['channels'][0]['valid_frequencies'],0)

    def test_clock_and_window_checks(self):
        for key,value in [('trace_P_arrival_sample','199'),('trace_npts','699'),('trace_dt_s','.02'),('trace_P_arrival_sample','nan')]:
            row,index,details=fixture();row[key]=value
            self.assertIsNone(window(row,INV));self.assertFalse(row_join(row,index,details,INV)['metadata_eligible'])

    def test_units_orientation_and_epoch_crossing(self):
        row,index,details=fixture();e=index[('IV','A','','HHE')][0];e.input_units='M/S**2'
        self.assertFalse(row_join(row,index,details,INV)['metadata_eligible'])
        e.input_units='M/S';e.azimuth_deg=92
        self.assertFalse(row_join(row,index,details,INV)['metadata_eligible'])
        e.azimuth_deg=90;e.end-=.001
        self.assertEqual(row_join(row,index,details,INV)['channels'][0]['status'],'partial_epoch_cover')


if __name__=='__main__':unittest.main()

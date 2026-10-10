import copy
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
import numpy as np
from synthetic_shared_fixture import fixture
from response_data import (CompletedExport,fit_export_normalizers,fit_normalizers,raw_amplitudes,gain_reexpression,
                           fitting_population_digest,file_sha)
from export_waveforms import (write_export,complete,validate_authoritative,basic_valid)


class ExportDataTests(unittest.TestCase):
    def make_export(self,directory,mutate=None):
        raw,rows,expected,provider=fixture()
        if mutate:mutate(raw,rows,expected,provider)
        output=Path(directory)/'export'
        write_export(raw,rows,expected,provider,output,{'synthetic':True})
        complete(output)
        return CompletedExport(output),raw,rows,expected,provider

    def test_roundtrip_exact_counts_identity_masks_and_forward_fields(self):
        with tempfile.TemporaryDirectory() as d:
            ds,raw,rows,expected,_=self.make_export(d)
            for i,row in enumerate(rows):np.testing.assert_array_equal(ds.counts[i],raw['data'][row['trace_name']][:,200:])
            np.testing.assert_array_equal(ds.metadata['valid'],expected['valid'])
            batch=ds.inference_batch([0,1],1)
            self.assertEqual(set(batch),{'counts','sensitivity','static','response'})
            self.assertEqual(batch['counts'].shape,(2,3,100))
            self.assertEqual(fitting_population_digest(ds.metadata,1)['rows'],4)

    def test_late_nonfinite_keeps_earlier_validity(self):
        def modify(raw,rows,e,p):
            raw['data'][rows[0]['trace_name']][0,650]=np.nan;e['valid'][0,2]=False;e['invalid_codes'][0,2]=2
        with tempfile.TemporaryDirectory() as d:
            ds,*_=self.make_export(d,modify)
            self.assertTrue(np.isfinite(ds.inference_batch([0],1)['counts']).all())
            self.assertTrue(np.isfinite(ds.inference_batch([0],3)['counts']).all())
            with self.assertRaises(ValueError):ds.inference_batch([0],5)
            norms,prov=fit_export_normalizers(ds)
            self.assertEqual(prov['per_deadline_fit_population']['1']['rows'],4)
            self.assertEqual(prov['per_deadline_fit_population']['5']['rows'],3)
            self.assertTrue(all(np.isfinite(v).all() for v in norms.values()))

    def test_authoritative_invalid_is_not_reclassified_or_replaced(self):
        def modify(raw,rows,e,p):e['valid'][0,0]=False;e['invalid_codes'][0,0]=64
        with tempfile.TemporaryDirectory() as d:
            ds,*_=self.make_export(d,modify)
            self.assertNotIn(0,ds.valid_rows('fit',1));self.assertIn(0,ds.valid_rows('fit',3))
            self.assertEqual(len(ds.counts),8)

    def test_incomplete_and_tampered_exports_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            raw,rows,e,p=fixture();out=Path(d)/'x';write_export(raw,rows,e,p,out,{})
            with self.assertRaises(FileNotFoundError):CompletedExport(out)
            complete(out)
            with open(out/'counts.npy','ab') as f:f.write(b'x')
            with self.assertRaises(ValueError):CompletedExport(out)

    def test_shared_identity_target_gain_and_partition_guards(self):
        raw,rows,e,p=fixture()
        for key in ('source_id','trace_name','source_row_index'):
            changed=copy.deepcopy(rows);changed[0][key]='wrong' if key!='source_row_index' else 99
            with self.assertRaises(ValueError):validate_authoritative(changed,e)
        changed=copy.deepcopy(rows);changed[0]['source_magnitude']='9'
        with self.assertRaises(ValueError):validate_authoritative(changed,e)
        bad=copy.deepcopy(e);bad['source_id'][4]=bad['source_id'][0]
        changed=copy.deepcopy(rows);changed[4]['source_id']=changed[0]['source_id']
        with self.assertRaises(ValueError):validate_authoritative(changed,bad)
        with tempfile.TemporaryDirectory() as d:
            bad=copy.deepcopy(e);bad['sensitivities'][0,0]*=2
            with self.assertRaises(ValueError):write_export(raw,rows,bad,p,Path(d)/'x',{})
            self.assertFalse((Path(d)/'x/COMPLETE.json').exists())

    def test_provider_response_fallback_guard(self):
        raw,rows,e,p=fixture()
        def bad_provider(row):
            static,gain,unit,response,epochs=p(row)
            response=response.copy();response[3]=.5
            return static,gain,unit,response,epochs
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):write_export(raw,rows,e,bad_provider,Path(d)/'x',{})
            self.assertFalse((Path(d)/'x/COMPLETE.json').exists())

    def test_mismatched_raw_prefix_aborts(self):
        raw,rows,e,p=fixture();raw['data'][rows[0]['trace_name']][0,250]=np.nan
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):write_export(raw,rows,e,p,Path(d)/'x',{})

    def test_fit_only_normalization_and_prefix_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            ds,*_=self.make_export(d)
            n,prov=fit_export_normalizers(ds);m=ds.metadata
            x=np.array(ds.counts);x[4:]=1e12
            static=m['static'].copy();static[4:]+=1e8
            response=m['response'].copy();response[4:]=np.nan
            n2=fit_normalizers(x,m['sensitivity'],static,response,m['valid'],m['subset'],m['sampling_weight'])
            for key in n:np.testing.assert_array_equal(n[key],n2[key])
            x=np.array(ds.counts);x[:,:,100:]*=1000
            n3=fit_normalizers(x,m['sensitivity'],m['static'],m['response'],m['valid'],m['subset'],m['sampling_weight'])
            for key in ('counts_amplitude_mean','counts_amplitude_std','native_amplitude_mean','native_amplitude_std'):
                np.testing.assert_array_equal(n[key][0],n3[key][0])
            self.assertFalse(prov['labels_used']);self.assertFalse(prov['held_rows_used'])

    def test_coherent_gain_reexpression_invariance_and_rng_isolation(self):
        raw,rows,e,p=fixture();x=np.array([raw['data'][r['trace_name']][:,200:] for r in rows]);g=e['sensitivities'];s=np.array([p(r)[0] for r in rows])
        np.random.seed(77);before=np.random.get_state()
        xx,gg,ss=gain_reexpression(x,g,s,e['source_row_index'],20261009,2)
        after=np.random.get_state()
        self.assertTrue(all(np.array_equal(a,b) for a,b in zip(before,after)))
        for t in (1,3,5):
            np.testing.assert_allclose(raw_amplitudes(x,g,t)[1],raw_amplitudes(xx,gg,t)[1],rtol=1e-13,atol=1e-13)
        one=gain_reexpression(x[:,:,:100],g,s,e['source_row_index'],20261009,2)
        np.testing.assert_array_equal(xx[:,:,:100],one[0])
        np.testing.assert_allclose(ss[:,[11,19,27]],np.log10(gg),rtol=1e-15,atol=1e-15)

    def test_production_cli_default_is_no_read_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'not-created'
            command=[sys.executable,str(Path(__file__).with_name('export_waveforms.py'))]
            for name in ('polarization-source','polarization-output','response-audit'):
                command += ['--'+name,str(Path(d)/'nonexistent')]
            command += ['--output',str(output),'--polarization-manifest-sha256','0'*64,'--response-join-sha256','0'*64]
            result=subprocess.run(command,text=True,capture_output=True,check=True)
            self.assertFalse(json.loads(result.stdout)['execute']);self.assertFalse(output.exists())

    def test_basic_validity_does_not_inspect_future(self):
        segment=np.random.default_rng(1).normal(size=(3,700));g=np.ones(3)
        self.assertTrue(basic_valid(segment,g,1));segment[:,600:]=np.nan
        self.assertTrue(basic_valid(segment,g,1));self.assertTrue(basic_valid(segment,g,3));self.assertFalse(basic_valid(segment,g,5))


if __name__=='__main__':unittest.main()

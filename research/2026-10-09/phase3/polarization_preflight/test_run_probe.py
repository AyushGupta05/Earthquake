import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import numpy as np
from run_probe import (atomic_json,verify_execution_code,invalidate_abnormal_exit,run_with_timeout,main,load_cache,worker,PROTOCOL_SHA256,
                       EXPECTED_METADATA,EXPECTED_INVENTORY,EXPECTED_SOURCE,sha)
from population import bucket
from features import FEATURE_NAMES,masks


def wait_fixture():
    time.sleep(10)


def completed_fixture():
    return


class RunnerTests(unittest.TestCase):
    def test_abnormal_exit_invalidates_persisted_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            atomic_json(path/'results.json',{'status':'complete','gate':{'pass':True}})
            invalidate_abnormal_exit(path,{'timed_out':False,'exit_code':1})
            result = json.loads((path/'results.json').read_text())
            self.assertEqual(result['status'],'failed_worker_exit')
            self.assertFalse(result['gate']['pass'])
    def test_provenance_failure_invalidates_persisted_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'source.py').write_text('original')
            expected = {'source.py':sha(path/'source.py')}
            atomic_json(path/'results.json',{'status':'complete','gate':{'pass':True}})
            (path/'source.py').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Code changed'):
                verify_execution_code(path,path,expected)
            result = json.loads((path/'results.json').read_text())
            self.assertEqual(result['status'],'failed_provenance')
            self.assertFalse(result['gate']['pass'])

    def fixture_cache(self,directory):
        directory.mkdir()
        rng = np.random.default_rng(20261009)
        fit_events = [f'fit{i}' for i in range(200) if bucket('polarization-event-v1',f'fit{i}')>=2][:40]
        eval_events = [f'eval{i}' for i in range(300) if bucket('polarization-event-v1',f'eval{i}')<2][:24]
        stations = {held:next(f'station{i}' for i in range(100) if (bucket('polarization-station-v1',f'station{i}')<2)==held) for held in (False,True)}
        events = fit_events+eval_events+eval_events
        n = len(events)
        subsets = np.array(['fit']*len(fit_events)+['eval_seen']*len(eval_events)+['eval_held']*len(eval_events))
        groups = np.array([stations[s=='eval_held'] for s in subsets])
        values = rng.normal(size=(n,3,127))
        valid = np.ones((n,3),dtype=bool); valid[0,2] = False
        values[~valid] = np.nan
        magnitude = {event:4.+(i%10)*.1 for i,event in enumerate(sorted(set(events)))}
        target = np.array([[magnitude[event],10.,3.] for event in events])
        for j in range(3):
            values[valid[:,j],j,0] = target[valid[:,j],0]
        arrays = dict(features=values,valid=valid,invalid_codes=(~valid).astype('uint16')*2,
                      targets=target,deadlines=np.array([1,3,5]),feature_names=np.array(FEATURE_NAMES),
                      source_row_index=np.arange(n),trace_name=np.array([f'trace{i}' for i in range(n)]),
                      source_id=np.array(events),station_group=groups,subset=subsets,
                      event_bucket=np.array([bucket('polarization-event-v1',event) for event in events]),
                      station_bucket=np.array([bucket('polarization-station-v1',group) for group in groups]),
                      sampling_weight=np.ones(n),n_metadata_eligible=np.ones(n),n_sampled=np.ones(n),
                      native_units=np.array(['m/s']*n),station_channels=np.array(['HH']*n))
        arrays.update({'mask_'+arm:mask for arm,mask in masks().items()})
        np.savez(directory/'features.npz',**arrays)
        here = Path(__file__).resolve().parent
        manifest = {'status':'complete','protocol_sha256':PROTOCOL_SHA256,
                    'pinned_sha256':dict(metadata=EXPECTED_METADATA,inventory=EXPECTED_INVENTORY,source=EXPECTED_SOURCE,protocol=PROTOCOL_SHA256),
                    'outputs_sha256':{'features.npz':sha(directory/'features.npz')},
                    'code_sha256':{name:sha(here/name) for name in ('extract_features.py','features.py','population.py','audit_metadata.py')},
                    'quality':{'scope':'synthetic fixture only'}}
        atomic_json(directory/'manifest.json',manifest)
        return arrays

    def test_synthetic_end_to_end_18_fits_and_identity_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            arrays = self.fixture_cache(path/'cache')
            (path/'out').mkdir()
            with patch('builtins.print'):
                worker(str(path/'cache'),str(path/'out'))
            result = json.loads((path/'out/results.json').read_text())
            self.assertEqual(result['status'],'complete')
            self.assertEqual(len(result['completed_fits']),18)
            self.assertEqual(len(result['comparisons']),6)
            for arm in ('B','D','F'):
                with np.load(path/'out'/f'5s_{arm}_ensemble_predictions.npz',allow_pickle=False) as artifact:
                    np.testing.assert_array_equal(artifact['source_row_index'],arrays['source_row_index'])
                    np.testing.assert_array_equal(artifact['valid'],arrays['valid'][:,2])
                    self.assertTrue(np.isnan(artifact['prediction'][0]).all())

    def test_final_hash_failure_invalidates_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture_cache(path/'cache')
            (path/'out').mkdir()
            def fail_final_hash(filename):
                if str(filename).endswith('_model.npz'):
                    raise OSError('Synthetic final artifact failure')
                return sha(filename)
            with patch('builtins.print'),patch('run_probe.sha',side_effect=fail_final_hash),patch('run_probe.gate',return_value={'pass':True}):
                with self.assertRaisesRegex(OSError,'final artifact'):
                    worker(str(path/'cache'),str(path/'out'))
            result = json.loads((path/'out/results.json').read_text())
            self.assertEqual(result['status'],'failed')
            self.assertFalse(result['gate']['pass'])

    def test_cache_integrity_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.fixture_cache(path/'cache')
            load_cache(path/'cache')
            with (path/'cache/features.npz').open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum'):
                load_cache(path/'cache')

    def test_hard_watchdog_and_normal_exit(self):
        result = run_with_timeout(wait_fixture,(),.5)
        self.assertTrue(result['timed_out'])
        self.assertLess(result['elapsed_seconds'],4)
        self.assertEqual(run_with_timeout(completed_fixture,(),5)['exit_code'],0)

    def test_dry_run_no_real_paths(self):
        import sys
        with patch.object(sys,'argv',['run_probe.py','--cache','/unused','--output','/unused2']), \
             patch('run_probe.sha',side_effect=AssertionError('Real path accessed')),patch('builtins.print'):
            main()

    def test_incomplete_cache_rejected_and_atomic_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            atomic_json(path/'manifest.json',{'status':'started','protocol_sha256':PROTOCOL_SHA256})
            self.assertEqual(json.loads((path/'manifest.json').read_text())['status'],'started')
            self.assertFalse((path/'manifest.json.tmp').exists())
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                load_cache(path)


if __name__ == '__main__':
    unittest.main()

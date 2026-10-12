"""Invented native records and scalar checks only; no actual/private inputs."""
import copy
import hashlib
import math
import unittest
from unittest.mock import patch

import amplitude_adapter as aa
import adapter as native
import activity
import producer
import test_adapter as invented


def manifest(plan,qualified,metadata):
    rows=[]
    for row,qrow,meta in zip(plan['rows'],qualified['rows'],metadata):
        cells=[]
        codes=producer.channels(row)
        for h,qcell in zip((1,3,5),qrow['cells']):
            if qcell['joint']['status']=='complete':
                by={c['channel']:c for c in qcell['components']}
                c=by[codes[0]]
                cells.append({'horizon':h,'status':'available','reason':'supported',
                              'array':'wave_%02d_%d'%(row['ordinal'],h),'shape':[3,c['count']],
                              'first':c['first'],'period':[125000000,1],'precontext_count':24,
                              'channels':codes,'view_sha256':[by[code]['view_sha256'] for code in codes]})
            else:
                cells.append({'horizon':h,'status':'unavailable','reason':'metadata_unknown',
                              'array':None,'shape':None,'first':None,'period':None,'precontext_count':None,
                              'channels':codes,'view_sha256':None})
        rows.append({'ordinal':row['ordinal'],'partition':row['partition'],'group':int(meta['group']),
                     'mw':float(meta['mw']),'cohort':all(c['status']=='available' for c in cells),'cells':cells})
    return {'schema':'earthquake-native-count-artifact-v1','study':producer.STUDY,'rows':rows,
            'denominators':{'rows':65,'cells':195,'train':41,'dev':24,'test_excluded':31}}


class AmplitudeTests(unittest.TestCase):
    def setUp(self):
        self.plan,self.q,self.bodies,self.meta,_=invented.fixture()
        for i,meta in enumerate(self.meta):meta['group']=str(i)
        self.m=manifest(self.plan,self.q,self.meta)

    def run_source(self,decoder=invented.decode):
        return aa.run(self.plan,self.q,self.bodies,decoder,self.meta,self.m)

    def rebind(self,body):
        self.bodies={i:body for i in range(17)}
        for b in self.plan['batches']:
            b['body_bytes']=len(body);b['body_sha256']=hashlib.sha256(body).hexdigest()
        self.q=producer.qualify(self.plan,self.bodies,invented.decode)
        self.m=manifest(self.plan,self.q,self.meta)

    def deny_common(self,slot):
        row=self.m['rows'][slot];row['cohort']=False
        for c in row['cells']:
            c.update(status='unavailable',reason='operational_ineligible',array=None,shape=None,
                     first=None,period=None,precontext_count=None,view_sha256=None)

    def test_fixed65_195_train_only_literal_tie_and_native_features(self):
        calls=[]
        def trace(raw,descriptor):
            calls.append(descriptor['ordinal']);return invented.decode(raw,descriptor)
        out=self.run_source(trace)
        self.assertEqual(len(out['events']),65)
        self.assertEqual(len(calls),41*6)
        self.assertTrue(out['aggregate']['fixed_common_train_complete'])
        self.assertTrue(all(v is False for v in out['claims'].values()))
        f=out['events'][0]['horizons'][0]['features']
        self.assertEqual(f['selected_component'],'HHE')
        self.assertEqual(f['peak'],20)
        self.assertEqual(f['noise'],1)
        self.assertAlmostEqual(f['y'],math.log10(20))
        self.assertEqual(f['L'],0)
        self.assertEqual(f['u'],1)
        self.assertTrue(f['noise_floor'])
        self.assertFalse(f['censored'])
        for e in out['events'][41:]:
            self.assertTrue(all(c['status']=='DEFERRED_DEV' and c['features'] is None for c in e['horizons']))

    def test_noncommon_never_decode_and_no_cohort_replacement(self):
        for i in range(41):self.deny_common(i)
        out=self.run_source(lambda *_:self.fail('non-common decoder'))
        self.assertEqual(len(out['events']),65)
        self.assertFalse(out['aggregate']['fixed_common_train_complete'])
        self.assertTrue(all(c['status']=='NON_COMMON' for e in out['events'][:41] for c in e['horizons']))

    def test_mutated_common_flag_rejects_before_decoder(self):
        self.m['rows'][0]['cohort']=False
        with self.assertRaisesRegex(aa.InvalidInput,'manifest_common'):
            self.run_source(lambda *_:self.fail('mutated common decoder'))

    def test_manifest_view_binding_before_decoder(self):
        self.m['rows'][0]['cells'][0]['view_sha256'][0]='0'*64
        with self.assertRaisesRegex(aa.InvalidInput,'manifest_view'):
            self.run_source(lambda *_:self.fail('bad view decoder'))

    def test_native_sample_hash_binding(self):
        self.q['records'][0]['samples_sha256']='0'*64
        with self.assertRaisesRegex(native.InvalidInput,'sample_hash'):self.run_source()

    def test_clock_and_raw_hash_binding(self):
        self.q['records'][0]['raw_sha256']='0'*64
        with self.assertRaisesRegex(native.InvalidInput,'raw_hash'):self.run_source()

    def test_current_cutoff_excludes_future_and_noise_is_identical(self):
        baseline=self.run_source()['events'][0]['horizons']
        body=b''.join(invented.record('HH'+s,i,[0]*24+[20]*8 if i==0 else [1000000]*32)
                      for s in 'EN12Z' for i in (0,1))
        self.rebind(body)
        cells=self.run_source()['events'][0]['horizons']
        self.assertEqual(cells[0]['features'],baseline[0]['features'])
        self.assertEqual(cells[1]['features']['peak'],1000000)
        self.assertEqual([c['features']['noise'] for c in cells],[1,1,1])

    def test_censor_floor_at_one_count_and_zero_signal(self):
        body=b''.join(invented.record('HH'+s,i,[0]*32) for s in 'EN12Z' for i in (0,1))
        self.rebind(body)
        f=self.run_source()['events'][0]['horizons'][0]['features']
        self.assertTrue(f['censored']);self.assertEqual(f['y'],f['L']);self.assertEqual(f['peak'],0)
        body=b''.join(invented.record('HH'+s,i,[0]*24+[1]*8 if i==0 else [1]*32)
                      for s in 'EN12Z' for i in (0,1))
        self.rebind(body)
        self.assertTrue(self.run_source()['events'][0]['horizons'][0]['features']['censored'])

    def test_original_pick_window_excludes_pre_pick_and_is_never_reclocked(self):
        self.plan['rows'][0]['pick_ns']=self.plan['rows'][0]['t0_ns']+250000000
        body=b''.join(invented.record('HH'+s,i,[0]*24+[10000,10000]+[2]*6 if i==0 else [2]*32)
                      for s in 'EN12Z' for i in (0,1))
        self.rebind(body)
        f=self.run_source()['events'][0]['horizons'][0]['features']
        self.assertEqual(f['peak'],2);self.assertEqual(f['u'],.75)
        self.assertEqual(self.plan['rows'][0]['pick_ns'],self.plan['rows'][0]['t0_ns']+250000000)

    def test_pre_t0_original_pick_uses_native_window_without_clamping(self):
        self.plan['rows'][0]['pick_ns']=self.plan['rows'][0]['t0_ns']-250000000
        self.q=producer.qualify(self.plan,self.bodies,invented.decode);self.m=manifest(self.plan,self.q,self.meta)
        f=self.run_source()['events'][0]['horizons'][0]['features']
        self.assertEqual(f['u'],1.25)
        self.assertEqual(self.plan['rows'][0]['pick_ns'],self.plan['rows'][0]['t0_ns']-250000000)

    def test_late_current_age_retained_without_common_shrink(self):
        self.plan['rows'][0]['pick_ns']=self.plan['rows'][0]['t0_ns']+875000000
        self.q=producer.qualify(self.plan,self.bodies,invented.decode);self.m=manifest(self.plan,self.q,self.meta)
        out=self.run_source()
        self.assertTrue(out['events'][0]['common'])
        self.assertEqual(out['events'][0]['horizons'][0]['status'],'UNSUPPORTED')
        self.assertFalse(out['aggregate']['fixed_common_train_complete'])
        self.assertEqual(out['aggregate']['original_common_train_events'],41)

    def test_noise_ratio_selects_literal_component_not_raw_peak(self):
        components=[]
        for name,noise,signal in [('HHE',10,30),('HHN',1,10),('HHZ',1,1)]:
            values=[noise,-noise]*12+[signal]*40
            components.append({'name':name,'pieces':[{'start_ns':invented.START,
                              'rational_period':[125000000,1],'values':values}]})
        cells=aa.extract(components,self.plan['rows'][0],aa.time.monotonic())
        f=cells[0]['features']
        self.assertEqual(f['selected_component'],'HHN');self.assertEqual(f['noise'],1)
        self.assertEqual(f['peak'],10);self.assertFalse(f['noise_floor'])

    def test_noise_coverage_unknown_retains_horizons(self):
        components=[{'name':'HH'+s,'pieces':[{'start_ns':invented.START+125000000,
                    'rational_period':[125000000,1],'values':[0]*64}]} for s in 'ENZ']
        cells=aa.extract(components,self.plan['rows'][0],aa.time.monotonic())
        self.assertTrue(all(c['status']=='BAD_NOISE' for c in cells))

    def test_period_unsupported_retains_fixed_common(self):
        with patch.object(native,'reconstruct',side_effect=native.UnsupportedNativeGrid):
            out=self.run_source(lambda *_:self.fail('unsupported native grid decode'))
        self.assertEqual(out['aggregate']['original_common_train_events'],41)
        self.assertFalse(out['aggregate']['fixed_common_train_complete'])
        self.assertTrue(all(c['status']=='UNSUPPORTED' for c in out['events'][0]['horizons']))

    def test_deadline_and_output_caps(self):
        with patch.object(aa.time,'monotonic',side_effect=[0,301]):
            with self.assertRaisesRegex(aa.InvalidInput,'wall_timeout'):self.run_source(lambda *_:self.fail('deadline'))
        with patch.object(aa,'MAX_PRIVATE',1):
            with self.assertRaisesRegex(aa.InvalidInput,'output_cap'):self.run_source()

    def test_group_label_slot_bindings(self):
        self.meta[0]['mw']=self.meta[0]['mw']+.1
        with self.assertRaisesRegex(aa.InvalidInput,'manifest_row'):self.run_source(lambda *_:self.fail('label decoder'))

    def test_all65_statuses_accounted(self):
        out=self.run_source()
        for h in (1,3,5):self.assertEqual(sum(out['aggregate']['status_counts'][str(h)].values()),65)


if __name__=='__main__':unittest.main()

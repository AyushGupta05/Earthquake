"""Combined custody/masking/replay/archive tests, all invented."""
import copy
import io
import json
import struct
import time
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
import artifact
import invented
from new_decode_contract import ObservedDecodeFailure


class CombinedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f=invented.fixture();cls.arrays,cls.manifest=invented.build(cls.f)

    def test_preserve_original_bytes_and_namespace_roundtrip(self):
        a,m=self.arrays,self.manifest
        self.assertEqual(len(m['rows']),115);self.assertEqual(sum(len(r['cells']) for r in m['rows']),345)
        self.assertEqual(m['native_namespaces'],dict(original_rows=65,original_bodies=17,new_rows=50,new_bodies=13))
        for key in ('contexts','amplitudes','magnitudes','partitions'):
            self.assertEqual(a[key][:65].tobytes(),self.f[3][key].tobytes())
        for r in self.f[4]['rows']:
            i=r['ordinal'];self.assertEqual(m['rows'][i]['original_group'],r['group']);self.assertEqual(m['rows'][i]['original_cohort'],r['cohort'])
            for c in r['cells']:
                if c['status']=='available':self.assertEqual(a['wave_%03d_%d'%(i,c['horizon'])].tobytes(),self.f[3][c['array']].tobytes())
        raw=artifact.save_npz(a,processing_begin=time.monotonic());loaded=artifact.load_npz(raw,m,processing_begin=time.monotonic())
        self.assertLessEqual(len(loaded),351)
        for k in a:np.testing.assert_array_equal(a[k],loaded[k])

    def test_new_metadata_before_vendor_and_pin_before_loading(self):
        meta=copy.deepcopy(self.f[7]);meta[70]['mw']=True
        with self.assertRaises(ValueError):invented.build(invented.changed(self.f,'metadata',meta),lambda *a:self.fail('decode'))
        f=list(self.f);f[2]=copy.deepcopy(f[2]);f[2]['old_npz']['sha256']='0'*64
        with patch.object(artifact.old,'load_npz',side_effect=AssertionError('load')):
            with self.assertRaises(ValueError):invented.build(tuple(f),lambda *a:self.fail('decode'))

    def test_old_mw_partition_static_context_and_unknown_group(self):
        for key,value in [('mw',9.),('partition','DEV'),('station_latitude',12.),('group',True)]:
            meta=copy.deepcopy(self.f[7]);meta[0][key]=value
            with self.assertRaises(ValueError):invented.build(invented.changed(self.f,'metadata',meta))
        meta=copy.deepcopy(self.f[7]);meta[0].update(group=-1,operational_eligible=False)
        a,m=invented.build(invented.changed(self.f,'metadata',meta));self.assertEqual(a['groups'][0],-1);self.assertFalse(m['rows'][0]['cohort'])
        self.assertEqual(a['wave_000_1'].tobytes(),self.arrays['wave_000_1'].tobytes())
        meta[0]['operational_eligible']=True
        with self.assertRaises(ValueError):invented.build(invented.changed(self.f,'metadata',meta))

    def test_global_bridge_masks_all_without_deleting_old_values(self):
        meta=copy.deepcopy(self.f[7]);meta[65]['group']=41
        a,m=invented.build(invented.changed(self.f,'metadata',meta))
        for i in (41,65):self.assertFalse(m['rows'][i]['cohort']);self.assertFalse(m['rows'][i]['operational_eligible'])
        self.assertEqual(a['wave_041_1'].tobytes(),self.arrays['wave_041_1'].tobytes())
        self.assertEqual(m['rows'][65]['cells'][0]['reason'],'operational_ineligible');self.assertNotIn('wave_065_1',a)

    def test_no_target_retains_unknown_clock_and_empty_batch(self):
        f=invented.fixture(missing=list(range(4)));a,m=invented.build(f)
        for i in range(65,69):self.assertEqual(m['rows'][i]['cells'][0]['reason'],'selection_unknown');self.assertFalse(m['rows'][i]['cohort'])
        self.assertEqual(f[5]['batches'][0]['transport'],'no_selection');self.assertIsNone(f[1][0])

    def test_old17_or_global_repacking_rejected_before_decode(self):
        p=copy.deepcopy(self.f[5]);p['rows'][0]['global_ordinal']=0
        with self.assertRaises(ValueError):invented.build(invented.changed(self.f,'new_plan',p),lambda *a:self.fail('decode'))
        f=list(self.f);f[1]={i:b'X' for i in range(17)}
        with self.assertRaises(ValueError):invented.build(tuple(f),lambda *a:self.fail('decode'))

    def test_native_raw_sample_view_and_exact_lattice(self):
        q=copy.deepcopy(self.f[6]);q['records'][0]['samples_sha256']='0'*64
        with self.assertRaises(ValueError):invented.build(invented.changed(self.f,'new_qualified',q))
        q=copy.deepcopy(self.f[6]);next(c for c in q['rows'][0]['cells'][0]['components'] if c['channel']=='HHE')['view_sha256']='0'*64
        a,m=invented.build(invented.changed(self.f,'new_qualified',q));self.assertEqual(m['rows'][65]['cells'][0]['reason'],'reconstruction_unknown');self.assertFalse(m['rows'][65]['cohort'])
        q=copy.deepcopy(self.f[6]);next(c for c in q['rows'][0]['cells'][0]['components'] if c['channel']=='HHE')['first'][0]+=1
        a,m=invented.build(invented.changed(self.f,'new_qualified',q));self.assertEqual(m['rows'][65]['cells'][0]['reason'],'grid_mismatch')

    def test_observed_overdelivery_charged_before_wrong_clock_and_exception(self):
        def oversized(*args):return dict(start_ns=-1,rate=1.,dtype='i4',values=np.zeros(8_000_001,dtype=np.int32))
        with self.assertRaisesRegex(RuntimeError,'artifact_observed_cap'):invented.build(self.f,oversized)
        for n in (8_000_001,True,-1):
            def failure(*args):raise ObservedDecodeFailure(n)
            with self.assertRaises(RuntimeError):invented.build(self.f,failure)
        def invalid(*args):
            failure=ObservedDecodeFailure(1);failure.observed_samples=True;raise failure
        with self.assertRaises(ValueError):invented.build(self.f,invalid)
        def bounded(*args):raise ObservedDecodeFailure(1)
        with self.assertRaisesRegex(ValueError,'record_decode_failure'):invented.build(self.f,bounded)

    def test_future_samples_do_not_change_first_prefix(self):
        native=np.array([[2**30+i for i in range(9)]]*3,dtype=np.int32)
        w,a=artifact.preprocess(native[:,:4],3);native[:,4:]=0
        np.testing.assert_array_equal(w,artifact.preprocess(native[:,:4],3)[0]);np.testing.assert_allclose(w,[[-.5,0,.5,1]]*3)

    def test_member_header_object_bounds_and_deadlines(self):
        with patch.object(artifact,'MAX_ELEMENTS',3):
            with self.assertRaises(ValueError):artifact.save_npz(self.arrays,processing_begin=time.monotonic())
        for fn,args in ((artifact.save_npz,(self.arrays,)),(artifact.inspect_npz,(b'',)),(artifact.load_npz,(b'',self.manifest))):
            with self.assertRaises(RuntimeError):fn(*args,processing_begin=time.monotonic()-301)
        raw,pins=self.f[0],self.f[2]
        with self.assertRaises(RuntimeError):artifact.build_combined(raw['old_npz'],raw['old_manifest'],raw['new_plan'],raw['new_qualified'],self.f[1],raw['metadata'],lambda *a:self.fail('decode'),pins=pins,processing_begin=time.monotonic()-301)
        def zipraw(entries):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as z:
                for name,b in entries:z.writestr(name,b)
            return out.getvalue()
        bad=io.BytesIO();np.save(bad,np.array([object()],dtype=object))
        for v in (zipraw([('../wave_065_1.npy',bad.getvalue())]),zipraw([('wave_115_1.npy',bad.getvalue())]),zipraw([('wave_065_1.npy',bad.getvalue())]),zipraw([('wave_065_1.npy',b'\x93NUMPY\x01\x00'+struct.pack('<H',4097)+b'x'*4097)])):
            with self.assertRaises(ValueError):artifact.inspect_npz(v,processing_begin=time.monotonic())

    def test_manifest_and_numeric_role_tamper(self):
        for i,key,value in [(64,'cohort',True),(0,'operational_eligible',False),(64,'group',False),(64,'source','new50')]:
            m=copy.deepcopy(self.manifest);m['rows'][i][key]=value
            with self.assertRaises(ValueError):artifact.validate_arrays(self.arrays,m)
        a=dict(self.arrays);a['groups']=a['groups'].copy();a['groups'][65]=0
        with self.assertRaises(ValueError):artifact.validate_arrays(a,self.manifest)

    def test_JSON_duplicate_nonfinite_depth_and_integer_admission(self):
        for raw in (b'{"x":1,"x":2}',b'NaN',b'1e1000',b'['*34+b'0'+b']'*34,b'1'*1025):
            with self.assertRaises(ValueError):artifact._json(raw,2000)

    def test_NEW_context_missingness_exact_units_and_forbidden_fields(self):
        meta=copy.deepcopy(self.f[7]);meta[65].update(station_latitude=91.,station_longitude=None,station_elevation=None,sensitivities=[0,None,10.],units=['m/s','M/S','M/S**2'])
        a,m=invented.build(invented.changed(self.f,'metadata',meta));c=a['contexts'][65,0]
        np.testing.assert_array_equal(c[3:9],[0,0,0,1,1,1])
        np.testing.assert_array_equal(c[11:17],[0,0,1,1,1,0])
        np.testing.assert_array_equal(c[17:],[0,0,0,1,1,0,0,0,0,1,0,0])
        for key in ('origin_latitude','source_distance','event_id','station_id','absolute_date','p_to_t0'):
            meta=copy.deepcopy(self.f[7]);meta[65][key]=0
            with self.assertRaises(ValueError):invented.build(invented.changed(self.f,'metadata',meta),lambda *a:self.fail('decode'))

    def test_NEW_local_age_floor_and_old_descriptive_preservation(self):
        p=copy.deepcopy(self.f[5]);p['rows'][0]['pick_ns']=p['rows'][0]['t0_ns']+800000000
        q=artifact.qc.qualify(p,self.f[1],invented.prior.fake_decode)
        f=invented.changed(invented.changed(self.f,'new_plan',p),'new_qualified',q)
        a,m=invented.build(f);self.assertEqual(m['rows'][65]['cells'][0]['reason'],'local_age');self.assertFalse(m['rows'][65]['cohort'])
        self.assertEqual(m['rows'][65]['cells'][1]['status'],'available')
        oldarrays={k:v.copy() for k,v in self.f[3].items()};oldarrays['contexts'][0,0,1]=.2
        f=list(self.f);f[0]=dict(f[0]);f[0]['old_npz']=artifact.old.save_npz(oldarrays);f[2]=dict(f[2]);f[2]['old_npz']=invented.pin(f[0]['old_npz'])
        a,m=invented.build(tuple(f));self.assertFalse(m['rows'][0]['cohort']);self.assertTrue(m['rows'][0]['original_cohort'])
        self.assertEqual(a['contexts'][:65].tobytes(),oldarrays['contexts'].tobytes());self.assertEqual(m['rows'][0]['cells'][0]['status'],'available')

    def test_duplicate_record_before_decode_and_whole_observed_cap(self):
        q=copy.deepcopy(self.f[6]);q['records'].append(copy.deepcopy(q['records'][0]))
        with self.assertRaises(ValueError):invented.build(invented.changed(self.f,'new_qualified',q),lambda *a:self.fail('decode'))
        with self.assertRaisesRegex(RuntimeError,'artifact_observed_cap'):
            artifact._reconstruct(self.f[5],self.f[6],self.f[1],invented.prior.fake_decode,0,[artifact.qc.MAX_TOTAL_SAMPLES-1],time.monotonic())
        q=copy.deepcopy(self.f[6]);q['batches'][0]['observed_samples']+=1
        with self.assertRaisesRegex(ValueError,'batch_observed_binding'):invented.build(invented.changed(self.f,'new_qualified',q))

    def test_callback_late_completion_cannot_be_accepted(self):
        clock=[100.]
        def late(raw,d):
            out=invented.prior.fake_decode(raw,d);clock[0]=401.;return out
        with patch.object(artifact.time,'monotonic',side_effect=lambda:clock[0]):
            raw,bodies,pins,*_=self.f
            with self.assertRaisesRegex(RuntimeError,'artifact_deadline'):
                artifact.build_combined(raw['old_npz'],raw['old_manifest'],raw['new_plan'],raw['new_qualified'],bodies,raw['metadata'],late,pins=pins,processing_begin=100.)

if __name__=='__main__':unittest.main()

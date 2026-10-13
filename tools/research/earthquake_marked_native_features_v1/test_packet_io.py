"""Invented numeric packet custody and fail-closed schema tests."""
import copy
import io
import json
import math
import time
import unittest
import zipfile
import numpy as np
import fixtures as f
import marked_native as m
import packet_io as store


class StorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=f.corpus();cls.packet=f.build(cls.c)
        cls.archive,cls.manifest=store.save(cls.packet,processing_begin=time.monotonic())

    def load(self,a=None,b=None):
        a=self.archive if a is None else a;b=self.manifest if b is None else b
        return store.load(a,b,pins=dict(archive=m.pin(a),manifest=m.pin(b)),processing_begin=time.monotonic())

    def test_roundtrip_each_payload_bitwise_and_strict_caps(self):
        p=self.load()
        self.assertLess(len(self.archive),store.MAX_ARCHIVE);self.assertLess(len(self.manifest),store.MAX_MANIFEST)
        total=0
        for r,s in zip(self.packet['rows'],p['rows']):
            for (name,obj,key),(name2,obj2,key2) in zip(store.arrays_of(r),store.arrays_of(s)):
                self.assertEqual(name,name2);self.assertTrue(m.bit_equal(obj[key],obj2[key2]));total+=obj[key].nbytes
        self.assertLess(total,store.MAX_PAYLOAD)

    def test_manifest_duplicate_key_nonfinite_extra_member_rejected(self):
        for raw in (b'{"schema":1,"schema":1}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):self.load(b=raw)
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.archive)) as src,zipfile.ZipFile(out,'w') as dst:
            for item in src.infolist():dst.writestr(item.filename,src.read(item))
            dst.writestr('../unregistered.npy',b'anything')
        with self.assertRaisesRegex(ValueError,'storage_member_set'):self.load(a=out.getvalue())

    def test_payload_or_npy_dtype_change_cannot_pass_recomputed_outer_pins(self):
        for mutation in ('payload','dtype'):
            out=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(self.archive)) as src,zipfile.ZipFile(out,'w') as dst:
                first=True
                for item in src.infolist():
                    body=src.read(item)
                    if first:
                        body=(body[:-1]+bytes([body[-1]^1])) if mutation=='payload' else body.replace(b'<f8',b'<i8',1)
                        first=False
                    dst.writestr(item.filename,body)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.load(a=out.getvalue())

    def test_reference_alias_and_mark_semantics_fail(self):
        top=json.loads(self.manifest)
        top['packet']['rows'][4]['precontext']='r_005_precontext'
        with self.assertRaisesRegex(ValueError,'storage_reference'):self.load(b=m.canonical(top))
        p=copy.deepcopy(self.packet);p['rows'][4]['horizons'][0]['censor'][0,0]^=1
        with self.assertRaisesRegex(ValueError,'storage_mark_semantics'):store.save(p,processing_begin=time.monotonic())

    def test_noise_shared_support_cannot_be_component_permuted(self):
        p=copy.deepcopy(self.packet);v=p['rows'][4]['noise']['nu'];v[:,0]=v[::-1,0]
        with self.assertRaisesRegex(ValueError,'storage_noise_support'):store.save(p,processing_begin=time.monotonic())

    def test_noncommon_payload_or_population_change_rejected(self):
        p=copy.deepcopy(self.packet);p['rows'][0]['precontext']=np.zeros(34)
        with self.assertRaisesRegex(ValueError,'storage_unavailable'):store.save(p,processing_begin=time.monotonic())
        p=copy.deepcopy(self.packet);p['denominators']['test_excluded']=30
        with self.assertRaisesRegex(ValueError,'storage_denominators'):store.save(p,processing_begin=time.monotonic())

    def test_noncontiguous_f32_or_object_arrays_not_cast(self):
        for dtype in (np.float32,object):
            p=copy.deepcopy(self.packet);p['rows'][4]['precontext']=p['rows'][4]['precontext'].astype(dtype)
            with self.assertRaisesRegex(ValueError,'storage_array'):store.save(p,processing_begin=time.monotonic())
        p=copy.deepcopy(self.packet);p['rows'][4]['noise']['powers']=np.asfortranarray(p['rows'][4]['noise']['powers'])
        with self.assertRaisesRegex(ValueError,'storage_array'):store.save(p,processing_begin=time.monotonic())

    def test_censor_threshold_and_unrepresentable_log_are_not_repaired(self):
        self.assertEqual(m.report_ratio(0.),(-12.,1))
        self.assertEqual(m.report_ratio(m.CENSOR_LIMIT),(-12.,1))
        above=m.CENSOR_LIMIT
        while math.log(above)<=-12:above=math.nextafter(above,float('inf'))
        self.assertEqual(m.report_ratio(above)[1],0)
        rounded=math.nextafter(m.CENSOR_LIMIT,float('inf'))
        if math.log(rounded)==-12:
            with self.assertRaisesRegex(ValueError,'censor_log_roundoff'):m.report_ratio(rounded)


if __name__=='__main__':unittest.main()

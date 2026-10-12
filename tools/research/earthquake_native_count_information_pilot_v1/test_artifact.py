"""Meaningful invented reconstruction, bounds and leakage tests."""
import copy
from fractions import Fraction
import hashlib
import io
import struct
import unittest
from unittest.mock import patch
import zipfile
import numpy as np
import artifact
import qualified_core as qc
import invented


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan,cls.bodies,cls.qualified,cls.arrays,cls.manifest=invented.build_fixture()

    def test_fixed_manifest_grid_and_roundtrip(self):
        a,m=self.arrays,self.manifest
        self.assertEqual(len(m["rows"]),65)
        self.assertEqual(sum(len(r["cells"]) for r in m["rows"]),195)
        self.assertEqual(int(a["cohort"].sum()),61)
        self.assertEqual(m["rows"][64]["cells"][0]["reason"],"metadata_unknown")
        self.assertEqual(m["rows"][0]["cells"][0]["shape"],[3,4])
        self.assertEqual(m["rows"][0]["cells"][0]["precontext_count"],3)
        loaded=artifact.load_npz(artifact.save_npz(a),m)
        for k in a:np.testing.assert_array_equal(a[k],loaded[k])

    def test_context_order_missingness_exact_units(self):
        meta=invented.metadata()[0];meta.update(station_latitude=100,station_longitude=None,station_elevation=float("nan"),sensitivities=[0,None,10.],units=["m/s","M/S","M/S**2"])
        c=artifact.context(self.plan["rows"][0],meta,1,Fraction(10))
        self.assertEqual(len(c),29)
        np.testing.assert_array_equal(c[3:9],[0,0,0,1,1,1])
        np.testing.assert_array_equal(c[9:17],[1,0,0,0,1,1,1,0])
        np.testing.assert_array_equal(c[17:],[0,0,0,1,1,0,0,0,0,1,0,0])
        self.assertEqual(c[1],.5)

    def test_native_float64_before_float32_and_prefix_no_future(self):
        # Values above float32 precision still preserve small native differences.
        native=np.array([[2**30+i for i in range(9)]]*3,dtype=np.int32)
        wave,amp=artifact.preprocess(native[:,:4],3)
        np.testing.assert_allclose(wave,[[ -.5,0,.5,1]]*3)
        self.assertAlmostEqual(float(amp[0]),np.log10(2),places=6)
        changed=native.copy();changed[:,4:]=0
        np.testing.assert_array_equal(artifact.preprocess(changed[:,:4],3)[0],wave)

    def test_shared_scale_rms_floor_and_finiteness(self):
        wave,amp=artifact.preprocess(np.zeros((3,4)),3)
        self.assertEqual(amp.tolist(),[0,-12,-12,-12])
        self.assertEqual(float(wave.sum()),0)
        for value in (np.full((3,4),np.nan),np.zeros((3,0))):
            with self.assertRaises(ValueError):artifact.preprocess(value,3)

    def test_wrong_record_and_view_hash_cannot_promote(self):
        q=copy.deepcopy(self.qualified);q["records"][0]["raw_sha256"]="0"*64
        with self.assertRaises(ValueError):artifact.build(self.plan,q,self.bodies,invented.metadata(),invented.fake_decode)
        q=copy.deepcopy(self.qualified);next(c for c in q["rows"][0]["cells"][0]["components"] if c["channel"]=="HHE")["view_sha256"]="0"*64
        a,m=artifact.build(self.plan,q,self.bodies,invented.metadata(),invented.fake_decode)
        self.assertEqual(m["rows"][0]["cells"][0]["reason"],"reconstruction_unknown")
        self.assertFalse(m["rows"][0]["cohort"])

    def test_ledger_duplicate_or_boolean_ordinal_before_decode(self):
        for change in (lambda q:q["records"].append(copy.deepcopy(q["records"][0])),lambda q:q["records"][0].update(ordinal=False)):
            q=copy.deepcopy(self.qualified);change(q)
            with self.assertRaises(ValueError):artifact.build(self.plan,q,self.bodies,invented.metadata(),lambda *a:self.fail("decode"))

    def test_exact_component_phase_mismatch_retained(self):
        q=copy.deepcopy(self.qualified);c=next(c for c in q["rows"][0]["cells"][0]["components"] if c["channel"]=="HHE");c["first"][0]+=1
        a,m=artifact.build(self.plan,q,self.bodies,invented.metadata(),invented.fake_decode)
        self.assertEqual(m["rows"][0]["cells"][0]["reason"],"grid_mismatch")

    def test_exact_internal_lattice_rejects_tolerance_accepted_join(self):
        # Prior qualifier permits 1us timing tolerance; dense artifact requires exact join.
        body=b"".join(invented.raw_record("HH"+s,values=range(4))+invented.raw_record("HH"+s,values=range(5),start_second=4,micros=1) for s in "EN12Z")
        p,b=invented.inputs(body);q=qc.qualify(p,b,invented.fake_decode)
        self.assertEqual(q["rows"][0]["cells"][2]["joint"]["status"],"complete")
        a,m=artifact.build(p,q,b,invented.metadata(),invented.fake_decode)
        self.assertEqual(m["rows"][0]["cells"][2]["reason"],"reconstruction_unknown")

    def test_original_cross_partition_group_ineligible(self):
        meta=invented.metadata();meta[41]["group"]=0
        a,m=artifact.build(self.plan,self.qualified,self.bodies,meta,invented.fake_decode)
        self.assertEqual(m["rows"][0]["cells"][0]["reason"],"operational_ineligible")
        self.assertEqual(m["rows"][41]["cells"][0]["reason"],"operational_ineligible")

    def test_cap_before_dense_assembly_and_writer(self):
        with patch.object(artifact,"MAX_ELEMENTS",3):
            with self.assertRaises(RuntimeError):artifact.build(self.plan,self.qualified,self.bodies,invented.metadata(),invented.fake_decode)
            with patch.object(np,"savez_compressed",side_effect=AssertionError("writer")):
                with self.assertRaises(ValueError):artifact.save_npz(self.arrays)

    def test_object_wrong_dtype_and_nonfinite_writer_reject(self):
        for value in (np.ones((3,4),dtype=object),np.ones((3,4),dtype=np.float64),np.full((3,4),np.nan,dtype=np.float32)):
            a=dict(self.arrays);a["wave_00_1"]=value
            with self.assertRaises(ValueError):artifact.save_npz(a)

    def test_duplicate_path_pickle_and_header_caps(self):
        def archive(entries):
            s=io.BytesIO()
            with zipfile.ZipFile(s,"w") as z:
                for name,data in entries:z.writestr(name,data)
            return s.getvalue()
        v=io.BytesIO();np.save(v,np.array([object()],dtype=object))
        for raw in (archive([("../wave_00_1.npy",v.getvalue())]),archive([("wave_00_1.npy",v.getvalue())]),archive([("wave_00_1.npy",v.getvalue()),("wave_00_1.npy",v.getvalue())]),archive([("wave_00_1.npy",b"\x93NUMPY\x01\x00"+struct.pack("<H",4097)+b"x"*4097)])):
            with self.assertRaises(ValueError):artifact.inspect_npz(raw)

    def test_numeric_metadata_bound_to_manifest_and_strict_bool(self):
        raw=artifact.save_npz(self.arrays)
        for mutate in (lambda m:m["rows"][0].update(mw=99.),lambda m:m["rows"][0].update(ordinal=False),lambda m:m["rows"][0].update(cohort=1)):
            m=copy.deepcopy(self.manifest);mutate(m)
            with self.assertRaises(ValueError):artifact.load_npz(raw,m)

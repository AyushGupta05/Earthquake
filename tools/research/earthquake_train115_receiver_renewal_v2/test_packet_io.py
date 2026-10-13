"""Invented numeric-only packet persistence/tamper/preallocation tests."""
import copy
import hashlib
import io
import json
import time
import unittest
import zipfile
import numpy as np
import packet_io
import pilot
import observations as obs
from test_renewal115 import make_packet


def pins(archive,manifest):
    return {k:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in [('archive',archive),('manifest',manifest)]}


class PacketIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet,*_=make_packet();cls.archive,cls.manifest=packet_io.save(cls.packet,processing_begin=time.monotonic())
    def test_roundtrip_exact_numeric_arrays_roles_and_closed_members(self):
        out=packet_io.load(self.archive,self.manifest,pins=pins(self.archive,self.manifest),processing_begin=time.monotonic())
        self.assertEqual(pilot.validate(out),pilot.validate(self.packet))
        for a,b in zip(out['rows'],self.packet['rows']):
            self.assertEqual((a['ordinal'],a['partition'],a['mw'],a['group'],a['common']),(b['ordinal'],b['partition'],b['mw'],b['group'],b['common']))
            if a['common']:
                for x,y in zip([a['initial']]+a['horizons'],[b['initial']]+b['horizons']):
                    for k in ('wave','amplitude','context'):self.assertEqual(x[k].tobytes(),y[k].tobytes());self.assertEqual(x[k].dtype,y[k].dtype)
        self.assertEqual(len(json.loads(self.manifest)['arrays']),87*12)
    def test_byte_pins_checked_before_archive_or_json_parse(self):
        with self.assertRaisesRegex(ValueError,'storage_pin'):packet_io.load(self.archive+b'x',self.manifest,pins=pins(self.archive,self.manifest),processing_begin=time.monotonic())
    def test_payload_hash_and_exact_row_reference_veto(self):
        manifest=json.loads(self.manifest);name=next(iter(manifest['arrays']));manifest['arrays'][name]['sha256']='0'*64;raw=obs.canonical(manifest)
        with self.assertRaisesRegex(ValueError,'storage_payload_hash'):packet_io.load(self.archive,raw,pins=pins(self.archive,raw),processing_begin=time.monotonic())
        manifest=json.loads(self.manifest);manifest['packet']['rows'][4]['initial']['wave']=manifest['packet']['rows'][5]['initial']['wave'];raw=obs.canonical(manifest)
        with self.assertRaisesRegex(ValueError,'storage_reference'):packet_io.load(self.archive,raw,pins=pins(self.archive,raw),processing_begin=time.monotonic())
    def test_pickle_dtype_member_extra_and_declared_shape_preallocation_denied(self):
        arrays=json.loads(self.manifest)['arrays'];bad=copy.deepcopy(arrays);name=next(iter(bad));bad[name]['dtype']='|O'
        with self.assertRaises(ValueError):packet_io.inspect(self.archive,bad,time.monotonic())
        bad=copy.deepcopy(arrays);bad[name]['shape']=[3,20_000_001]
        with self.assertRaises(ValueError):packet_io.inspect(self.archive,bad,time.monotonic())
        stream=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.archive)) as old,zipfile.ZipFile(stream,'w') as new:
            for member in old.infolist():new.writestr(member.filename,old.read(member.filename))
            new.writestr('../extra.npy',b'forbidden')
        with self.assertRaisesRegex(ValueError,'storage_member_set'):packet_io.inspect(stream.getvalue(),arrays,time.monotonic())
    def test_complete_source_storage_cap_and_deadline(self):
        from unittest.mock import patch
        with patch.object(packet_io,'MAX_ARCHIVE',1):
            with self.assertRaises(ValueError):packet_io.save(self.packet,processing_begin=time.monotonic())
        with self.assertRaises(ValueError):packet_io.load(self.archive,self.manifest,pins=pins(self.archive,self.manifest),processing_begin=time.monotonic()-301)


if __name__=='__main__':unittest.main()

"""Independent manual byte-vector and cross-contract packet identity tests."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
import numpy as np
import packet_digest as d
import transport as tx
import auditor,fixtures as f
from math_core import AuditFailure

class StreamingVectors(unittest.TestCase):
 def test_none_known_vector(self):self.assertEqual(d.sha(None),'81ea3b9b1a9442841824adb002ce5b98734bb43b663c034b20e5eb3f35da81ce')
 def test_empty_dictionary_known_vector(self):self.assertEqual(d.sha({}),'6814ef46f686990cf4e946f966167b0507e1d642c44e51f61bffb0bba2d4672b')
 def test_nested_empty_tuple_known_vector(self):self.assertEqual(d.sha([()]),'271b2622fc45df7f4ffea9e8bfb56b48e444834843eba0e306f3eeeb8d6739c8')
 def test_unicode_and_boolean_dictionary_known_vector(self):self.assertEqual(d.sha({'b':[1,False],'a':'é'}),'f9c46eff5bf0ce5ce7ee6d4230e4f8cc890aa45f8400f3b33229c29fcfa30ba6')
 def test_original_array_raw_negative_zero_known_vector(self):self.assertEqual(d.sha(np.asarray([1.,-0.],dtype='<f8')),'690472a9bd36b1f0a34708d88b54fe12c252592babe7d3c73a7394666842ba5a')
 def test_empty_uint_array_known_vector(self):self.assertEqual(d.sha(np.empty(0,dtype=np.uint8)),'f00bb81cefe318f4bfae8121d17dd229a3d80d93fbf584895d4a5027a8c6626f')
 def test_literal_manual_stream_nested_shape_dtype_payload(self):
  packet={'x':np.asarray([[1.]],dtype='<f8'),'y':[None,True,2,-0.]};literal=b'D"x"A{"dtype":"<f8","shape":[1,1]}'+bytes.fromhex('000000000000f03f')+b'"y"LVnullVtrueV2V-0.0EE';self.assertEqual(d.sha(packet),hashlib.sha256(literal).hexdigest())
 def test_dict_order_and_tuple_list_equivalence(self):self.assertEqual(d.sha({'a':(1,False),'b':None}),d.sha({'b':None,'a':[1,False]}))
 def test_array_bits_and_shape_untouched(self):
  self.assertNotEqual(d.sha(np.asarray([0.],dtype='<f8')),d.sha(np.asarray([-0.],dtype='<f8')));self.assertNotEqual(d.sha(np.asarray([1.],dtype='<f8')),d.sha(np.asarray([[1.]],dtype='<f8')))
 def test_json_numeric_snapshot_not_packet_fingerprint(self):
  x={'a':np.asarray([1.],dtype='<f8')};self.assertNotEqual(d.sha(x),tx.sha(x));self.assertEqual(tx.sha(x),hashlib.sha256(tx.canonical(x)).hexdigest())
 def test_streaming_hash_fixture_accepts_canonical_rejected_as_packet(self):
  p=f.packet_fixture();ad=f.admission_fixture(p);auth={'packet_sha256':d.sha(p)};auditor.admission_checked(ad,p,auth);bad=copy.deepcopy(ad);bad['packet_sha256']=tx.sha(p)
  with self.assertRaises(AuditFailure):auditor.admission_checked(bad,p,{'packet_sha256':tx.sha(p)})
 def test_initial_checkpoint_schema_order_score_hashes_still_canonical(self):
  p=f.packet_fixture();ad=f.admission_fixture(p);cp=f.checkpoint_fixture(ad);score=f.score_fixture(p,ad,cp);self.assertEqual(ad['packet_sha256'],d.sha(p));self.assertEqual(cp['initial_sha256'],tx.sha(cp['parameters']));self.assertEqual(cp['order_sha256'],tx.sha(ad['models']['20261012:P']['order']));self.assertEqual(cp['admission_sha256'],tx.sha(ad));self.assertEqual(score['checkpoint_sha256'],tx.sha(cp));self.assertEqual(score['admission_sha256'],tx.sha(ad));self.assertEqual(score['packet_sha256'],d.sha(p))
 def test_nonfinite_and_unsupported_packet_dtype_rejected(self):
  for value in(float('nan'),np.asarray([np.inf]),np.asarray([1.],dtype=np.float32)):
   with self.assertRaises(AuditFailure):d.sha(value)
 def test_unchanged_scientific_modules_positive_origin_pins(self):
  root=Path(__file__).parent;origin=json.loads((root/'ORIGIN_V1.json').read_bytes())
  for name in('math_core.py','packet.py','metrics.py','transport.py'):
   self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),origin['files'][name]['sha256'])

if __name__=='__main__':unittest.main()

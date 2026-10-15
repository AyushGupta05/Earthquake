"""Independent streaming numeric-tree packet identity, no producer/model imports."""
import hashlib
import json
import math
import numpy as np
from math_core import need

def json_bytes(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

def sha(packet):
 digest=hashlib.sha256();nodes=0;payload=0
 def walk(value,depth):
  nonlocal nodes,payload
  nodes+=1;need(nodes<=2_000_000 and depth<=32,'packet_hash_structure')
  if type(value)is np.ndarray:
   need(value.dtype.str in('<f8','|u1')and value.flags.c_contiguous and value.nbytes<=1024*1024,'packet_hash_array');payload+=value.nbytes;need(payload<=1024*1024 and np.isfinite(value).all(),'packet_hash_payload');digest.update(b'A');digest.update(json_bytes(dict(dtype=value.dtype.str,shape=list(value.shape))));digest.update(value.tobytes(order='C'))
  elif type(value)is dict:
   need(all(type(k)is str for k in value),'packet_hash_keys');digest.update(b'D')
   for key in sorted(value):digest.update(json_bytes(key));walk(value[key],depth+1)
   digest.update(b'E')
  elif type(value)in(list,tuple):
   digest.update(b'L')
   for item in value:walk(item,depth+1)
   digest.update(b'E')
  else:
   need(value is None or type(value)in(str,bool,int,float),'packet_hash_scalar')
   if type(value)is float:need(math.isfinite(value),'packet_hash_finite')
   if type(value)is int:need(value.bit_length()<=1024,'packet_hash_integer')
   digest.update(b'V');digest.update(json_bytes(value))
 walk(packet,0);return digest.hexdigest()

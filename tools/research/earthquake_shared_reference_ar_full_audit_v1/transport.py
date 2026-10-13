"""Bounded canonical numeric snapshots; no pickle, producer imports or IO."""
import hashlib
import json
import math
import numpy as np
from math_core import need

ALLOWED={'<f8':np.dtype('<f8'),'<f4':np.dtype('<f4'),'<i8':np.dtype('<i8'),'|u1':np.dtype('|u1')}

def encode(v):
 if type(v)is np.ndarray:
  dtype=v.dtype.str;need(dtype in ALLOWED and v.flags.c_contiguous and v.nbytes<=2*1024*1024,'array_transport');return {'__array__':dtype,'shape':list(v.shape),'hex':v.tobytes().hex()}
 if type(v)is dict:return {k:encode(x)for k,x in v.items()}
 if type(v)is list:return [encode(x)for x in v]
 need(v is None or type(v)in(str,bool,int,float),'scalar_transport')
 if type(v)is float:need(math.isfinite(v),'finite_scalar')
 return v

def canonical(v):return json.dumps(encode(v),sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def sha(v):return hashlib.sha256(canonical(v)).hexdigest()

def decode(value,cap=2*1024*1024):
 need(type(cap)is int and 0<cap<=16*1024*1024,'transport_cap');used=[0];nodes=[0]
 def visit(v,depth):
  nodes[0]+=1;need(nodes[0]<=2_000_000 and depth<=32,'transport_structure')
  if type(v)is dict:
   need(all(type(k)is str for k in v),'transport_keys')
   if '__array__'in v:
    need(set(v)=={'__array__','shape','hex'}and v['__array__']in ALLOWED and type(v['shape'])is list and len(v['shape'])<=8 and all(type(n)is int and 0<=n<=100_000 for n in v['shape'])and type(v['hex'])is str,'array_schema');dt=ALLOWED[v['__array__']];size=math.prod(v['shape'])*dt.itemsize;need(size<=cap and len(v['hex'])==2*size and used[0]+size<=cap,'array_cap');need(all(c in'0123456789abcdef'for c in v['hex']),'array_hex');used[0]+=size;a=np.frombuffer(bytes.fromhex(v['hex']),dtype=dt).copy().reshape(tuple(v['shape']));need(not np.issubdtype(dt,np.floating)or np.isfinite(a).all(),'finite_array');return a
   return {k:visit(x,depth+1)for k,x in v.items()}
  if type(v)is list:return [visit(x,depth+1)for x in v]
  need(v is None or type(v)in(str,bool,int,float),'transport_scalar')
  if type(v)is float:need(math.isfinite(v),'finite_scalar')
  if type(v)is int:need(v.bit_length()<=1024,'integer_cap')
  return v
 return visit(value,0)

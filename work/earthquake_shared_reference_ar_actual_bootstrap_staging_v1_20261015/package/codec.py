"""Canonical historical numeric transport; no imports of numerical libraries."""
import math

class Numeric:
    def __init__(self,io,*,transport=None,np=None):
        self.io=io;self.tx=transport;self.np=np
        io.need((transport is None)!=(np is None),'codec_dependency')
    def encode(self,value):
        raw=self.tx.canonical(value) if self.tx is not None else self.io.canonical(self._encode(value))
        self.io.need(type(raw)is bytes and len(raw)<=16*1024*1024,'numeric_output_cap');return raw
    def decode(self,raw,digest,*,cap=16*1024*1024):
        self.io.need(type(cap)is int and 0<cap<=16*1024*1024 and type(raw)is bytes and len(raw)<=cap and self.io.pin(raw)['sha256']==digest,'numeric_pin')
        parsed=self.io.json_read(raw)
        value=self.tx.decode(parsed,cap=cap) if self.tx is not None else self._decode(parsed,cap)
        self.io.need(self.encode(value)==raw,'canonical_numeric');return value
    def _encode(self,v):
        np=self.np
        if type(v)is np.ndarray:
            self.io.need(v.dtype.str in ('<f8','<f4','<i8','|u1') and v.flags.c_contiguous and v.nbytes<=2*1024*1024 and bool(np.isfinite(v).all()),'array_transport')
            return {'__array__':v.dtype.str,'shape':list(v.shape),'hex':v.tobytes().hex()}
        if type(v)is dict:return {k:self._encode(x)for k,x in v.items()}
        if type(v)is list:return [self._encode(x)for x in v]
        self.io.need(v is None or type(v)in(str,bool,int,float),'scalar_transport')
        if type(v)is float:self.io.need(math.isfinite(v),'finite_scalar')
        return v
    def _decode(self,value,cap):
        np=self.np;used=nodes=0
        def visit(v,depth):
            nonlocal used,nodes
            nodes+=1;self.io.need(nodes<=2_000_000 and depth<=32,'transport_structure')
            if type(v)is dict:
                self.io.need(all(type(k)is str for k in v),'transport_keys')
                if '__array__'in v:
                    self.io.need(set(v)=={'__array__','shape','hex'} and v['__array__']in('<f8','<f4','<i8','|u1') and type(v['shape'])is list and len(v['shape'])<=8 and all(type(n)is int and 0<=n<=100000 for n in v['shape']) and type(v['hex'])is str,'array_schema')
                    dt=np.dtype(v['__array__']);size=math.prod(v['shape'])*dt.itemsize
                    self.io.need(size<=cap and len(v['hex'])==2*size and used+size<=cap and all(c in'0123456789abcdef'for c in v['hex']),'array_cap')
                    used+=size;a=np.frombuffer(bytes.fromhex(v['hex']),dtype=dt).copy().reshape(tuple(v['shape']))
                    self.io.need(not np.issubdtype(dt,np.floating) or bool(np.isfinite(a).all()),'finite_array');return a
                return {k:visit(x,depth+1)for k,x in v.items()}
            if type(v)is list:return [visit(x,depth+1)for x in v]
            self.io.need(v is None or type(v)in(str,bool,int,float),'transport_scalar')
            if type(v)is float:self.io.need(math.isfinite(v),'finite_scalar')
            if type(v)is int:self.io.need(v.bit_length()<=1024,'integer_cap')
            return v
        return visit(value,0)

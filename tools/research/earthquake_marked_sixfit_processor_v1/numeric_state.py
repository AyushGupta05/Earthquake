"""Bounded pure-bytes numeric snapshots. No paths, pickle or arbitrary objects."""
import hashlib
import json
import math
import numpy as np

CAP = 2 * 1024 * 1024


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    count = [0]
    def visit(x, depth=0):
        count[0] += 1
        need(depth <= 32 and count[0] <= 100000, 'snapshot_structure')
        if type(x) is np.ndarray:
            need(x.dtype.str in ('<f8', '<f4', '<i8', '|u1') and x.flags.c_contiguous
                 and x.size <= 100000 and np.isfinite(x).all(), 'snapshot_array')
            return {'__array__': x.dtype.str, 'shape': list(x.shape), 'hex': x.tobytes().hex()}
        if type(x) is dict:
            need(all(type(k) is str and k != '__array__' for k in x), 'snapshot_key')
            return {k: visit(v, depth+1) for k, v in x.items()}
        if type(x) in (list, tuple):
            return [visit(v, depth+1) for v in x]
        need(x is None or type(x) in (str, bool, int, float), 'snapshot_type')
        if type(x) is str:
            need(len(x) <= 4096, 'snapshot_string')
        if type(x) is int:
            need(x.bit_length() <= 64, 'snapshot_integer')
        if type(x) is float:
            need(math.isfinite(x), 'snapshot_nonfinite')
        return x
    raw = json.dumps(visit(value), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    need(len(raw) <= CAP, 'snapshot_cap')
    return raw


def decode(raw, sha256):
    need(type(raw) is bytes and len(raw) <= CAP and digest(raw) == sha256, 'snapshot_pin')
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'snapshot_duplicate')
            out[k] = v
        return out
    def bad(_):
        raise ValueError('snapshot_nonfinite')
    obj = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    count = [0]
    def visit(x, depth=0):
        count[0] += 1
        need(depth <= 32 and count[0] <= 100000, 'snapshot_structure')
        if type(x) is dict:
            if '__array__' in x:
                need(set(x) == {'__array__', 'shape', 'hex'} and x['__array__'] in ('<f8','<f4','<i8','|u1'), 'snapshot_dtype')
                shape = x['shape']
                need(type(shape) is list and len(shape) <= 4 and all(type(v) is int and 0 <= v <= 100000 for v in shape), 'snapshot_shape')
                size = math.prod(shape)
                need(size <= 100000 and type(x['hex']) is str, 'snapshot_array')
                data = bytes.fromhex(x['hex'])
                need(len(data) == size*np.dtype(x['__array__']).itemsize, 'snapshot_size')
                a = np.frombuffer(data, dtype=x['__array__']).reshape(shape).copy()
                need(np.isfinite(a).all(), 'snapshot_nonfinite')
                return a
            return {k: visit(v, depth+1) for k,v in x.items()}
        if type(x) is list:
            return [visit(v, depth+1) for v in x]
        need(x is None or type(x) in (str,bool,int,float), 'snapshot_type')
        if type(x) is float:
            need(math.isfinite(x), 'snapshot_nonfinite')
        if type(x) is int:
            need(x.bit_length() <= 64, 'snapshot_integer')
        if type(x) is str:
            need(len(x) <= 4096, 'snapshot_string')
        return x
    answer = visit(obj)
    need(encode(answer) == raw, 'snapshot_canonical')
    return answer

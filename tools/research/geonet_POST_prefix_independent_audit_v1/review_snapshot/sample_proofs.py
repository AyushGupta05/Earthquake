"""Independent local amplitude/digest/run evidence, no serialized arrays."""
import hashlib
import math
from strict import Reject


def scalar(value):
    if type(value) is int:
        return value
    value = float(value)
    if not math.isfinite(value):
        raise Reject('nonfinite_scalar')
    return value


def dtype_code(data):
    import numpy as np
    if type(data) is not np.ndarray or data.ndim != 1:
        raise Reject('array')
    code = data.dtype.kind + str(data.dtype.itemsize)
    if code not in ('i4', 'f4', 'f8'):
        raise Reject('dtype')
    return code


def digest(data, dtype):
    # Preserve numeric bits, including signed zero/nonfinite overdelivery bits.
    return hashlib.sha256(dtype.encode('ascii') + b'\0' + data.astype('<' + dtype, copy=False).tobytes(order='C')).hexdigest()


def stats(data):
    import numpy as np
    if not bool(np.isfinite(data).all()):
        return {'finite': False, 'minimum': None, 'maximum': None, 'first_value': None,
                'last_value': None, 'first_run': None, 'last_run': None,
                'min_run': None, 'max_run': None, 'flat': None}
    if not len(data):
        raise Reject('empty_piece')
    minimum = scalar(data.min().item()); maximum = scalar(data.max().item())
    first = scalar(data[0].item()); last = scalar(data[-1].item())
    changes = np.flatnonzero(data[1:] != data[:-1]) + 1
    boundaries = np.concatenate((np.array([0]), changes, np.array([len(data)])))
    lengths = np.diff(boundaries)
    run_values = data[boundaries[:-1]]
    first_run = int(lengths[0]); last_run = int(lengths[-1])
    min_run = int(lengths[run_values == minimum].max())
    max_run = int(lengths[run_values == maximum].max())
    return {'finite': True, 'minimum': minimum, 'maximum': maximum,
            'first_value': first, 'last_value': last, 'first_run': first_run, 'last_run': last_run,
            'min_run': min_run, 'max_run': max_run, 'flat': minimum == maximum}


def aggregate_stats(pieces):
    if not all(p['finite'] for p in pieces):
        return {'finite': False, 'minimum': None, 'maximum': None, 'flat': None, 'extreme_run': None}
    minimum = min(p['minimum'] for p in pieces); maximum = max(p['maximum'] for p in pieces)
    longest = 0
    for extreme, field in ((minimum, 'min_run'), (maximum, 'max_run')):
        trailing = 0
        for piece in pieces:
            if piece['minimum' if field == 'min_run' else 'maximum'] == extreme:
                longest = max(longest, piece[field])
            if piece['first_value'] == extreme:
                longest = max(longest, trailing + piece['first_run'])
            trailing = ((trailing + piece['count']) if piece['flat'] and piece['first_value'] == extreme
                        else piece['last_run'] if piece['last_value'] == extreme else 0)
    return {'finite': True, 'minimum': minimum, 'maximum': maximum, 'flat': minimum == maximum, 'extreme_run': longest}

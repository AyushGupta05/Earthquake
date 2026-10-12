"""Fresh one-record ObsPy decode; shared decoder limits independence."""
import io
from geometry import rate_agrees
from strict import Reject


def decode_record(raw, header, expected_start, expected_rate):
    """Decode only an already structurally supported bounded raw record.

    Caller/parent must prove pinned runtime and an effective Linux cgroup first.
    This function cannot establish those external facts or authenticate timing.
    """
    import numpy as np
    import obspy
    if obspy.__version__ != '1.5.1':
        raise Reject('decoder_version')
    if type(raw) is not bytes or len(raw) != header['length'] or len(raw) > 1_048_576:
        raise Reject('record_bytes')
    if header['npts'] == 0:
        return None
    try:
        stream = obspy.read(io.BytesIO(raw), format='MSEED')
    except MemoryError:
        raise
    except Exception as exc:
        raise Reject('decoder_failure') from exc
    if len(stream) != 1:
        raise Reject('trace_cardinality')
    trace = stream[0]
    data = trace.data
    if (type(data) is not np.ndarray or data.ndim != 1
            or data.dtype.kind not in 'if' or data.dtype.itemsize not in (2, 4, 8)
            or data.size != header['npts'] or trace.stats.npts != header['npts']
            or data.size > 8_000_000 or data.nbytes > 64_000_000):
        raise Reject('observed_array')
    nslc = [trace.stats.network, trace.stats.station, trace.stats.location, trace.stats.channel]
    if nslc != header['nslc']:
        raise Reject('decoder_identity')
    if type(trace.stats.starttime.ns) is not int or trace.stats.starttime.ns != expected_start:
        raise Reject('decoder_start')
    if not rate_agrees(trace.stats.sampling_rate, expected_rate):
        raise Reject('decoder_rate')
    return data

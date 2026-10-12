"""Fresh one-record ObsPy observation with pre-rejection sample accounting."""
import io
from strict import Reject


class ObservedDecodeFailure(ValueError):
    """Independent public-contract failure; replay validates signed64 count."""
    def __init__(self,observed_samples):
        self.observed_samples=observed_samples
        super().__init__('observed_decode_failure')


def decode_record(raw,header,expected_start,expected_rate):
    # Start/rate agreement is intentionally deferred until replay charges values.
    import numpy as np
    import obspy
    from obspy.io.mseed import ObsPyMSEEDError
    if obspy.__version__!='1.5.1':raise Reject('decoder_version')
    if type(raw) is not bytes or len(raw)!=header['length'] or len(raw)>1_048_576:raise Reject('record_bytes')
    if header['npts']==0:return None
    stream=trace=data=None
    try:
        try:stream=obspy.read(io.BytesIO(raw),format='MSEED')
        except (ValueError,ObsPyMSEEDError) as error:raise Reject('decoder_failure') from error
        # Count scalar arrays across every trace before cardinality/identity/dtype.
        observed=0
        for trace in stream:
            if type(trace.data) is not np.ndarray:raise RuntimeError('unaccountable_vendor_array')
            observed+=int(trace.data.size)
        if observed>2**63-1:raise RuntimeError('unaccountable_vendor_count')
        try:
            if len(stream)!=1:raise Reject('trace_cardinality')
            trace=stream[0];data=trace.data
            if data.ndim!=1 or data.dtype.kind not in 'if' or data.dtype.itemsize not in (2,4,8):raise Reject('observed_array')
            if trace.stats.npts!=data.size or [trace.stats.network,trace.stats.station,trace.stats.location,trace.stats.channel]!=header['nslc']:raise Reject('decoder_identity_count')
            start=trace.stats.starttime.ns;rate=float(trace.stats.sampling_rate)
            if type(start) is not int:raise Reject('decoder_clock_type')
            return dict(start_ns=start,rate=rate,dtype=data.dtype.kind+str(data.dtype.itemsize),values=data)
        except (ValueError,TypeError,AttributeError,OverflowError) as error:
            raise ObservedDecodeFailure(observed) from error
    finally:
        stream=trace=data=None

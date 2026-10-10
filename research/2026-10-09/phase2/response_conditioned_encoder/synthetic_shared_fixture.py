"""Deterministic invented records. Contains no real earthquake inputs/labels."""
import numpy as np


def fixture(n=8):
    rng=np.random.default_rng(20261009)
    raw={'data':{}};rows=[];gains=[];statics=[];responses=[]
    for i in range(n):
        station='A' if i<n-2 else 'H'
        trace=f'synthetic{i}.XX.{station}..HH'
        row=dict(source_row_index=i,trace_name=trace,source_id=f'synthetic{i}',station_id='XX.'+station,
                 station_group='XX.'+station,subset='fit' if i<n-4 else ('eval_seen' if i<n-2 else 'eval_held'),
                 sampling_weight=float(i%3+1),source_magnitude=str(1+i*.1),path_hyp_distance_km='20',source_depth_km='5',
                 trace_P_arrival_sample='200',trace_npts='700',event_bucket=3 if i<n-4 else 0,
                 station_bucket=3 if i<n-2 else 0,n_metadata_eligible=(i%3+1)*4,n_sampled=4)
        rows.append(row);raw['data'][trace]=rng.normal(size=(3,700))*100*(i+1)
        gain=np.array([1e6,2e6,3e6]);gains.append(gain)
        static=np.zeros(34);static[0]=1;static[6]=500+i;static[8]=400
        for c in range(3):
            start=10+8*c;static[start+1]=np.log10(gain[c]);static[start+2]=1
            static[start+4]=np.log(2);static[start+6]=np.log(101)
        statics.append(static)
        response=np.zeros((3,6,4));response[...,0]=rng.normal(size=(3,6))*.1;response[...,1]=1;response[...,3]=1
        if i==0:response[0,-1]=0
        responses.append(response.ravel())
    expected={key:np.array([r[key] for r in rows]) for key in ('source_row_index','trace_name','source_id','station_id',
         'station_group','subset','sampling_weight','event_bucket','station_bucket','n_metadata_eligible','n_sampled')}
    expected.update(valid=np.ones((n,3),dtype=bool),invalid_codes=np.zeros((n,3),dtype=np.uint16),deadlines=np.array([1,3,5]),
        target_names=np.array(['source_magnitude','path_hyp_distance_km','source_depth_km']),
        targets=np.array([[float(r[k]) for k in ('source_magnitude','path_hyp_distance_km','source_depth_km')] for r in rows]),
        sensitivities=np.array(gains),native_units=np.full(n,'m/s'))
    def provider(row):
        i=int(row['source_row_index'])
        return statics[i],gains[i],['m/s']*3,responses[i],[f'synthetic-epoch-{c}' for c in 'ENZ']
    return raw,rows,expected,provider

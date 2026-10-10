"""Pure NumPy fit-only normalizers, identity checks, and gain augmentation.

No labels are accepted by normalization. This module never opens real data or
trains a model on import. Dataset loading requires an atomic completed export.
"""
import hashlib
import json
from pathlib import Path
import numpy as np

DEADLINES=(1,3,5)
GAIN_INDICES=(11,19,27)


def file_sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()


def moments(values,weights,mask=None):
    values=np.asarray(values,dtype=np.float64);weights=np.asarray(weights,dtype=np.float64)
    if values.ndim<2 or weights.shape!=(len(values),) or (weights<=0).any() or not np.isfinite(weights).all():
        raise ValueError('Invalid fit weights or values shape')
    shape=values.shape[1:];flat=values.reshape(len(values),-1)
    valid=np.ones_like(flat,dtype=bool) if mask is None else np.broadcast_to(mask,values.shape).reshape(flat.shape)
    if not np.isfinite(flat[valid]).all():raise ValueError('Nonfinite valid fit coordinate')
    w=weights[:,None]*valid;den=w.sum(0)
    safe=np.where(valid,flat,0.)
    mean=np.divide((w*safe).sum(0),den,out=np.zeros(flat.shape[1]),where=den>0)
    variance=np.divide((w*(safe-mean)**2).sum(0),den,out=np.zeros_like(mean),where=den>0)
    std=np.sqrt(np.maximum(variance,0)).clip(1e-6)
    std[den==0]=1
    return mean.reshape(shape).astype(np.float32),std.reshape(shape).astype(np.float32)


def raw_amplitudes(counts,gain,seconds):
    if seconds not in DEADLINES:raise ValueError('Invalid deadline')
    x=np.asarray(counts[:,:,:seconds*100],dtype=np.float64)
    if x.shape[1:]!=(3,seconds*100) or not np.isfinite(x).all():raise ValueError('Invalid exact available prefix')
    gain=np.asarray(gain,dtype=np.float64)
    if gain.shape!=(len(x),3) or not np.isfinite(gain).all() or (gain<=0).any():raise ValueError('Invalid gains')
    x=x-x.mean(-1,keepdims=True)
    rms=np.sqrt(np.maximum((x*x).mean(-1),1e-16));peak=np.maximum(abs(x).max(-1),1e-8)
    amp=np.concatenate([np.log(rms),np.log(peak)],axis=1)
    return amp,amp-np.tile(np.log(gain),(1,2))


def fit_normalizers(counts,gain,static,response,valid,subset,weights):
    n=len(counts)
    static=np.asarray(static);response=np.asarray(response);valid=np.asarray(valid);subset=np.asarray(subset)
    weights=np.asarray(weights)
    if counts.shape!=(n,3,500) or static.shape!=(n,34) or response.shape!=(n,72) or valid.shape!=(n,3) or subset.shape!=(n,) or weights.shape!=(n,):
        raise ValueError('Normalizer source alignment mismatch')
    if valid.dtype!=np.bool_:raise ValueError('Validity must be boolean')
    fit=np.flatnonzero(subset=='fit')
    if len(fit)==0:raise ValueError('No fitting rows')
    result={}
    result['static_mean'],result['static_std']=moments(static[fit],weights[fit])
    r=response[fit].reshape(-1,3,6,4);mask=r[...,3]
    if not np.isin(mask,[0,1]).all() or (r[...,:3]*(1-mask[...,None])!=0).any():raise ValueError('Invalid response mask/fallback')
    result['response_mean'],result['response_std']=moments(r[...,:3],weights[fit],mask[...,None].astype(bool))
    ca=[];cs=[];na=[];ns=[]
    for j,t in enumerate(DEADLINES):
        rows=fit[valid[fit,j]]
        if len(rows)==0:raise ValueError('No valid fitting rows at deadline')
        # At most1024prefixes are materialized at once; held/future samples
        # never participate in this deadline's fit statistics.
        amplitudes=[];native=[]
        for start in range(0,len(rows),1024):
            ix=rows[start:start+1024]
            a,b=raw_amplitudes(counts[ix,:,:100*t],np.asarray(gain)[ix],t)
            amplitudes.append(a);native.append(b)
        m,s=moments(np.concatenate(amplitudes),weights[rows]);ca.append(m);cs.append(s)
        m,s=moments(np.concatenate(native),weights[rows]);na.append(m);ns.append(s)
    result.update(counts_amplitude_mean=np.stack(ca),counts_amplitude_std=np.stack(cs),
                  native_amplitude_mean=np.stack(na),native_amplitude_std=np.stack(ns))
    return result


def gain_reexpression(counts,gain,static,row_indices,seed,epoch):
    """Deterministic coherent ADC re-expression, independent of all training RNG.

    Same source row/epoch/component has the same multiplier at every deadline.
    Response H/g descriptor is unchanged and must NOT be multiplied again.
    """
    x=np.asarray(counts);g=np.asarray(gain);s=np.asarray(static)
    rows=np.asarray(row_indices)
    if x.ndim!=3 or x.shape[1]!=3 or g.shape!=(len(x),3) or s.shape!=(len(x),34) or rows.shape!=(len(x),):raise ValueError('Augmentation alignment')
    if not np.isfinite(x).all() or not np.isfinite(g).all() or (g<=0).any() or not np.isfinite(s).all():raise ValueError('Invalid augmentation input')
    if not np.allclose(s[:,GAIN_INDICES],np.log10(g),atol=1e-5,rtol=1e-5):raise ValueError('Gain/static disagreement')
    exponent=np.empty((len(x),3),dtype=np.float64)
    for i,row in enumerate(rows):
        for c in range(3):
            d=hashlib.sha256(f'response-gain-v1\0{int(seed)}\0{int(epoch)}\0{int(row)}\0{c}'.encode()).digest()
            u=(int.from_bytes(d[:8],'big')+.5)/2**64
            exponent[i,c]=2*u-1
    factor=10**exponent
    new_static=s.astype(np.float64,copy=True);new_static[:,GAIN_INDICES]+=exponent
    return x*factor[...,None],g*factor,new_static


class CompletedExport:
    """Immutable identity/array reader, no targets passed into forward batches."""
    def __init__(self,path):
        self.path=Path(path)
        completion=json.loads((self.path/'COMPLETE.json').read_text())
        manifest_path=self.path/'manifest.json'
        if completion['manifest_sha256']!=file_sha(manifest_path):raise ValueError('Completion/manifest hash mismatch')
        self.manifest=json.loads(manifest_path.read_text())
        if self.manifest['status']!='complete':raise ValueError('Incomplete export')
        for name,digest in self.manifest['outputs_sha256'].items():
            if name not in ('counts.npy','metadata.npz'):raise ValueError('Unexpected export artifact')
            if file_sha(self.path/name)!=digest:raise ValueError('Export artifact changed: '+name)
        if set(self.manifest['outputs_sha256'])!={'counts.npy','metadata.npz'}:raise ValueError('Missing export artifact')
        self.counts=np.load(self.path/'counts.npy',mmap_mode='r',allow_pickle=False)
        with np.load(self.path/'metadata.npz',allow_pickle=False) as archive:self.metadata={k:archive[k] for k in archive.files}
        n=len(self.counts)
        if self.counts.shape!=(n,3,500) or self.counts.dtype!=np.float64:raise ValueError('Export count shape/dtype mismatch')
        shapes={'valid':(n,3),'invalid_codes':(n,3),'sensitivity':(n,3),'static':(n,34),'response':(n,72),
                **{k:(n,) for k in ('source_row_index','trace_name','source_id','station_group','subset','sampling_weight','targets')}}
        if any(self.metadata[k].shape!=v for k,v in shapes.items()):raise ValueError('Export row/metadata shape mismatch')
        if self.metadata['valid'].dtype!=np.bool_ or not np.array_equal(self.metadata['valid'],self.metadata['invalid_codes']==0):raise ValueError('Export validity/codes mismatch')
        if not np.array_equal(self.metadata['deadlines'],DEADLINES):raise ValueError('Export deadline order mismatch')
        if not np.isin(self.metadata['subset'],('fit','eval_seen','eval_held')).all():raise ValueError('Export subset mismatch')
        if not np.isfinite(self.metadata['sampling_weight']).all() or (self.metadata['sampling_weight']<=0).any():raise ValueError('Invalid export weights')
        if not np.isfinite(self.metadata['targets']).all():raise ValueError('Invalid export targets')
        if len(set(self.metadata['trace_name'].tolist()))!=n or len(set(self.metadata['source_row_index'].tolist()))!=n:raise ValueError('Duplicate export identity')
        fit=self.metadata['subset']=='fit';held=self.metadata['subset']=='eval_held'
        if set(self.metadata['source_id'][fit])&set(self.metadata['source_id'][~fit]):raise ValueError('Event overlap')
        if set(self.metadata['station_group'][fit])&set(self.metadata['station_group'][held]):raise ValueError('Station overlap')

    def valid_rows(self,subset,seconds):
        return np.flatnonzero((self.metadata['subset']==subset)&self.metadata['valid'][:,DEADLINES.index(seconds)])

    def inference_batch(self,indices,seconds):
        if seconds not in DEADLINES:raise ValueError('Invalid deadline')
        ix=np.asarray(indices,dtype=np.int64)
        if ix.ndim!=1 or (ix<0).any() or (ix>=len(self.counts)).any():raise ValueError('Invalid selected rows')
        if not self.metadata['valid'][ix,DEADLINES.index(seconds)].all():raise ValueError('Selected invalid deadline observation')
        return {'counts':np.array(self.counts[ix,:,:100*seconds],copy=True),
                **{k:np.array(self.metadata[k][ix],copy=True) for k in ('sensitivity','static','response')}}


def fitting_population_digest(metadata,seconds=None):
    """Order-bound identities/weights, excluding target values and held rows."""
    select=np.asarray(metadata['subset'])=='fit'
    if seconds is not None:select &= metadata['valid'][:,DEADLINES.index(seconds)]
    indices=np.flatnonzero(select);h=hashlib.sha256()
    for i in indices:
        record={'source_row_index':int(metadata['source_row_index'][i]),
                'trace_name':str(metadata['trace_name'][i]),'source_id':str(metadata['source_id'][i]),
                'sampling_weight':float(metadata['sampling_weight'][i])}
        h.update(json.dumps(record,sort_keys=True,separators=(',',':')).encode()+b'\n')
    return {'rows':len(indices),'sha256':h.hexdigest()}


def fit_export_normalizers(dataset):
    m=dataset.metadata
    normalizers=fit_normalizers(dataset.counts,m['sensitivity'],m['static'],m['response'],m['valid'],m['subset'],m['sampling_weight'])
    provenance={'export_manifest_sha256':file_sha(dataset.path/'manifest.json'),
        'metadata_fit_population':fitting_population_digest(m),
        'per_deadline_fit_population':{str(t):fitting_population_digest(m,t) for t in DEADLINES},
        'normalizer_source_sha256':file_sha(__file__),
        'labels_used':False,'held_rows_used':False,
        'arrays_sha256':{k:hashlib.sha256(np.asarray(v,dtype='<f4').tobytes()).hexdigest() for k,v in normalizers.items()}}
    return normalizers,provenance

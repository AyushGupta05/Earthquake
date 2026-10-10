"""Fresh finite-prefix density with matched early/late response conditioning.

No data I/O, fitting, future windows, labels, original CNN features or station
identifiers enter this module. Scalar gain affects retained amplitudes, not a
second normalized waveform. FiLM and categorical densities are established.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F

DEADLINES=(1,3,5)
STATIC_NAMES=([f'family_{f}' for f in ('HH','EH','HN','HL','EN','unknown')]
    +[v for n in ('station_elevation_m','station_vs_30_mps') for v in (n,n+'_missing')]
    +[f'{c}_{s}' for c in 'ENZ' for s in ('response_missing','log10_sensitivity','velocity','acceleration',
       'log1p_sensitivity_frequency_hz','sensitivity_frequency_hz_missing',
       'log1p_native_sample_rate_hz','native_sample_rate_hz_missing')])
GAIN_INDICES=tuple(STATIC_NAMES.index(c+'_log10_sensitivity') for c in 'ENZ')
CONDITION_INDICES=tuple(i for i in range(10,34) if i not in GAIN_INDICES)
NORMALIZER_SHAPES={'static_mean':(34,),'static_std':(34,), 'response_mean':(3,6,3),'response_std':(3,6,3),
    'counts_amplitude_mean':(3,6),'counts_amplitude_std':(3,6),
    'native_amplitude_mean':(3,6),'native_amplitude_std':(3,6)}


def identity_normalizers():
    """Only for synthetic tests; production must supply fit-only statistics."""
    return {key:torch.ones(shape) if key.endswith('_std') else torch.zeros(shape)
            for key,shape in NORMALIZER_SHAPES.items()}


class ResidualBlock(nn.Module):
    """Same compact residual block as the reviewed independent baseline."""
    def __init__(self,in_channels,out_channels):
        super().__init__()
        self.body=nn.Sequential(nn.Conv1d(in_channels,out_channels,5,stride=2,padding=2,bias=False),
            nn.GroupNorm(8,out_channels),nn.SiLU(),nn.Conv1d(out_channels,out_channels,3,padding=1,bias=False),
            nn.GroupNorm(8,out_channels))
        self.skip=nn.Conv1d(in_channels,out_channels,1,stride=2,bias=False)
    def preactivation(self,x):return self.body(x)+self.skip(x)
    def forward(self,x):return F.silu(self.preactivation(x))


class ResponseConditionedModel(nn.Module):
    def __init__(self,arm,normalizers):
        super().__init__()
        if arm not in ('A','B','C','D'):raise ValueError('Unknown architecture arm')
        if set(normalizers)!=set(NORMALIZER_SHAPES):raise ValueError('Exact fit-normalizer schema required')
        self.arm=arm
        for key,shape in NORMALIZER_SHAPES.items():
            value=torch.as_tensor(normalizers[key],dtype=torch.float32).clone()
            if tuple(value.shape)!=shape or not torch.isfinite(value).all():raise ValueError('Invalid normalizer '+key)
            if key.endswith('_std') and (value<=0).any():raise ValueError('Nonpositive scale '+key)
            self.register_buffer(key,value)
        self.stem=nn.Sequential(nn.Conv1d(3,32,9,stride=2,padding=4,bias=False),nn.GroupNorm(8,32),nn.SiLU(),
                               ResidualBlock(32,64),ResidualBlock(64,96))
        self.last=ResidualBlock(96,128)
        self.conditioner=nn.Sequential(nn.Linear(93,32),nn.SiLU(),nn.Linear(32,256))
        # All arms initialize every parameter in exactly the same order.
        nn.init.zeros_(self.conditioner[-1].weight);nn.init.zeros_(self.conditioner[-1].bias)
        self.project=nn.Sequential(nn.Linear(369,128),nn.LayerNorm(128),nn.SiLU())
        self.state_update=nn.GRUCell(128,128)
        self.decoder=nn.Linear(128,66)

    def parameter_count(self):return sum(p.numel() for p in self.parameters())

    @staticmethod
    def _pool(z):return torch.cat([z.mean(-1),z.amax(-1)],dim=1)

    def _inputs(self,batch,seconds):
        if seconds not in DEADLINES:raise ValueError('Only1/3/5second prefixes accepted')
        required=('counts','sensitivity','static','response')
        if any(k not in batch for k in required):raise ValueError('Missing inference input')
        device,dtype=self.decoder.weight.device,self.decoder.weight.dtype
        x,g,static,response=[batch[k].to(device=device,dtype=dtype) for k in required]
        if x.ndim!=3 or tuple(x.shape[1:])!=(3,100*seconds) or len(x)==0:raise ValueError('Exact prefix length required')
        n=len(x)
        if g.shape!=(n,3) or static.shape!=(n,34) or response.shape!=(n,72):raise ValueError('Inference metadata shape mismatch')
        if not all(torch.isfinite(v).all() for v in (x,g,static,response)) or (g<=0).any():raise ValueError('Invalid supplied values')
        if not torch.allclose(static[:,GAIN_INDICES],g.log10(),rtol=1e-5,atol=1e-5):raise ValueError('Gain/static disagreement')
        response=response.reshape(n,3,6,4)
        mask=response[...,3]
        if not ((mask==0)|(mask==1)).all():raise ValueError('Response validity mask must be binary')
        if not (response[...,:3]*(1-mask[...,None])==0).all():raise ValueError('Masked raw response values must be zero')
        normalized_response=((response[...,:3]-self.response_mean)/self.response_std).clamp(-8,8)*mask[...,None]
        normalized_response=torch.cat([normalized_response,mask[...,None]],dim=-1).flatten(1)
        normalized_static=((static-self.static_mean)/self.static_std).clamp(-8,8)
        return x,g,normalized_static,normalized_response

    def forward_prefix(self,batch,seconds):
        """Use exactly this prefix; batch labels/identities, if present, ignored.

        Deployment requires only counts,sensitivity,static,response. No target
        argument, preceding posterior, full5s tensor or future target is read.
        """
        x,g,static,response=self._inputs(batch,seconds)
        q=x-x.mean(-1,keepdim=True)
        rms=q.square().mean(-1).clamp_min(1e-16).sqrt()
        peak=q.abs().amax(-1).clamp_min(1e-8)
        amp=torch.cat([rms.log(),peak.log()],dim=1)
        t=DEADLINES.index(seconds)
        if self.arm in ('B','C'):
            amp=amp-torch.cat([g.log(),g.log()],dim=1)
            amp=((amp-self.native_amplitude_mean[t])/self.native_amplitude_std[t]).clamp(-8,8)
        else:
            amp=((amp-self.counts_amplitude_mean[t])/self.counts_amplitude_std[t]).clamp(-8,8)
        z=self.last.preactivation(self.stem(q/rms[...,None]))
        condition=torch.cat([response,static[:,CONDITION_INDICES]],dim=1)
        a,b=self.conditioner(condition).chunk(2,dim=1)
        gamma=1+.5*a.tanh();beta=.5*b.tanh()
        if self.arm=='C':
            pooled=self._pool(F.silu(gamma[...,None]*z+beta[...,None]))
        else:
            pooled=self._pool(F.silu(z))*torch.cat([gamma,gamma],1)+torch.cat([beta,beta],1)
        duration=x.new_full((len(x),1),math.log(seconds))
        encoded=self.project(torch.cat([pooled,amp,duration,static,response],dim=1))
        state=self.state_update(encoded,torch.zeros_like(encoded))
        return self.decoder(state)

    def forward(self,batch,seconds):return self.forward_prefix(batch,seconds)

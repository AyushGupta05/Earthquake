"""CPU five-arm models with effective matched branches and initial-only C/H API."""
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


class Encoder(nn.Module):
    def __init__(self):
        super().__init__();self.convs=nn.ModuleList([nn.Conv1d(3,8,9,padding='same'),nn.Conv1d(8,16,5,padding='same'),nn.Conv1d(16,16,5,padding='same')])
    def forward(self,wave,amplitude,mask):
        if wave.ndim!=3 or wave.shape[1]!=3 or amplitude.shape!=(wave.shape[0],4) or mask.shape!=(wave.shape[0],wave.shape[2]) or mask.dtype!=torch.bool or not torch.all(mask.any(1)):raise ValueError('encoder_shape')
        valid=mask[:,None,:];value=wave.masked_fill(~valid,0)
        for conv in self.convs:value=F.silu(conv(value))*valid
        mean=value.sum(-1)/mask.sum(-1,keepdim=True);maximum=value.masked_fill(~valid,-torch.inf).amax(-1)
        return torch.cat((mean,maximum,amplitude),dim=1)


class Base(nn.Module):
    def __init__(self,dimension):
        super().__init__();self.hidden=nn.Linear(dimension,32);self.head=nn.Linear(32,15)
    def initialize(self,mean,std):
        with torch.no_grad():
            self.head.weight.zero_();self.head.bias.zero_();self.head.bias[5:10]=mean+.01*torch.randn(5)
            self.head.bias[10:15]=math.log(math.expm1(max(float(std),.1)-.05))
    def forward(self,x):return self.head(F.silu(self.hidden(x)))


def mixture(raw):
    return F.log_softmax(raw[...,:5],dim=-1),raw[...,5:10],.05+F.softplus(raw[...,10:15])


def nll(y,raw):
    logw,mu,sigma=mixture(raw)
    return -torch.logsumexp(logw-torch.log(sigma)-.5*math.log(2*math.pi)-.5*((y[:,None]-mu)/sigma)**2,dim=-1)


def edges(states,mask):
    if states.ndim!=2 or states.shape!=mask.shape or states.shape[1]>20 or mask.dtype!=torch.bool or not torch.all(mask[:,0]):raise ValueError('states_shape')
    if not torch.all((states[mask]==0)|(states[mask]==1)) or torch.any(mask[:,1:]&~mask[:,:-1]):raise ValueError('states_prefix')
    idx=states[:,:-1].long();changed=(states[:,1:]!=states[:,:-1]).to(dtype=torch.float64)
    age=torch.ones_like(states,dtype=torch.float64)
    for j in range(1,states.shape[1]):age[:,j]=torch.where(states[:,j]==states[:,j-1],age[:,j-1]+1,torch.ones_like(age[:,j-1]))
    u=.25*torch.arange(1,states.shape[1],device=states.device,dtype=torch.float64)
    return idx,changed,u,age[:,:-1],mask[:,1:]


class Hazards(nn.Module):
    def __init__(self,arm,mref):
        super().__init__()
        if arm not in ('C','H','T'):raise ValueError('hazard_arm')
        self.arm=arm;self.mref=float(mref)
        self.alpha=nn.Parameter(torch.zeros(2));self.beta=nn.Parameter(torch.zeros(2));self.z_weights=nn.Parameter(torch.zeros(2,36))
        self.c_weights=nn.Parameter(torch.zeros(2,35));self.gamma=nn.Parameter(torch.zeros(2));self.extra=nn.Parameter(torch.zeros(2))
    def likelihood(self,m,z,c,states,mask):
        idx,y,u,r,valid=edges(states,mask)
        if z.shape!=(states.shape[0],36) or c.shape!=(states.shape[0],35):raise ValueError('initial_dimensions')
        dtype=m.dtype;z=z.to(dtype);c=c.to(dtype)
        common=self.alpha.to(dtype)[None,:]+z@self.z_weights.to(dtype).T+c@self.c_weights.to(dtype).T
        base=common.gather(1,idx)+self.gamma.to(dtype)[idx]*torch.log1p(u.to(dtype))[None,:]
        if self.arm=='C':base=base+self.extra.to(dtype)[idx]*torch.log1p(r.to(dtype))
        elif self.arm=='T':base=base+self.extra.to(dtype)[idx]*torch.log1p(4*u.to(dtype))[None,:]
        else:
            interaction=torch.stack((z[:,0]*z[:,1],z[:,0]*c[:,0]),dim=1)
            base=base+(interaction*self.extra.to(dtype)[None,:]).gather(1,idx)
        dimensions=m.ndim-1
        shape=(m.shape[0],)+(1,)*dimensions+(base.shape[1],)
        ell=base.reshape(shape)+(m[...,None]-self.mref)*self.beta.to(dtype)[idx].reshape(shape)
        change=y.to(dtype).reshape(shape);active=valid.reshape(shape)
        factors=-F.softplus(torch.where(change==1,-ell,ell))
        return factors.masked_fill(~active,0).sum(-1)


class Net(nn.Module):
    def __init__(self,arm,mref):
        super().__init__()
        if arm not in ('B','F','H','T','C'):raise ValueError('arm')
        self.arm=arm;self.encoder=Encoder()
        self.base=Base(71 if arm in ('C','H','T') else 76 if arm=='F' else 72)
        if arm=='F':self.feature=nn.Conv1d(5,2,1)
        if arm in ('C','H','T'):self.hazards=Hazards(arm,mref)
    def initialize(self,mean,std):self.base.initialize(mean,std)
    def initial(self,wave,amplitude,context,mask):
        if self.arm not in ('C','H','T') or context.shape!=(wave.shape[0],35):raise ValueError('initial_api')
        z=self.encoder(wave,amplitude,mask)
        return self.base(torch.cat((z,context),1)),z
    def current(self,wave,amplitude,context,mask,activity=None,activity_mask=None):
        if self.arm not in ('B','F') or context.shape!=(wave.shape[0],36):raise ValueError('current_api')
        z=self.encoder(wave,amplitude,mask)
        if self.arm=='F':
            if activity is None or activity.ndim!=3 or activity.shape[1]!=5 or activity_mask is None or activity_mask.shape!=(wave.shape[0],activity.shape[2]) or not torch.all(activity_mask.any(1)):raise ValueError('activity_feature_shape')
            valid=activity_mask[:,None,:];value=F.silu(self.feature(activity.masked_fill(~valid,0)))*valid
            pooled=torch.cat((value.sum(-1)/activity_mask.sum(-1,keepdim=True),value.masked_fill(~valid,-torch.inf).amax(-1)),1)
            z=torch.cat((z,pooled),1)
        elif activity is not None or activity_mask is not None:raise ValueError('B_extra_features')
        return self.base(torch.cat((z,context),1))


def parameter_counts():
    counts={a:sum(p.numel() for p in Net(a,5.).parameters() if p.requires_grad) for a in ('B','F','H','T','C')}
    if max(counts.values())/min(counts.values())>1.05:raise ValueError('capacity_mismatch')
    return counts


def torch_gh(raw,hazards,z,c,states,mask,order):
    if order not in (64,128):raise ValueError('quadrature_order')
    logw,mu,sigma=mixture(raw.to(torch.float64));x,w=np.polynomial.hermite.hermgauss(order)
    nodes=mu[:,:,None]+math.sqrt(2)*sigma[:,:,None]*torch.as_tensor(x,dtype=torch.float64,device=raw.device)
    mass=logw[:,:,None]+torch.log(torch.as_tensor(w,dtype=torch.float64,device=raw.device))[None,None,:]-.5*math.log(math.pi)
    mass=mass+hazards.likelihood(nodes,z,c,states,mask)
    logz=torch.logsumexp(mass.flatten(1),1);mean=(torch.exp(mass-logz[:,None,None])*nodes).sum((1,2))
    if not torch.isfinite(logz).all() or not torch.isfinite(mean).all():raise RuntimeError('torch_quadrature_nonfinite')
    return logz,mean

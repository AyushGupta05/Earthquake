"""Frozen CPU endpoint-statistic encoder and proper five-Gaussian density."""

import math
import torch
from torch import nn
from torch.nn import functional as F


class PilotNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.convs=nn.ModuleList([nn.Conv1d(3,8,9,padding="same"),
                                 nn.Conv1d(8,16,5,padding="same"),
                                 nn.Conv1d(16,16,5,padding="same")])
        self.hidden=nn.Linear(65,32)
        self.head=nn.Linear(32,15)

    def initialize(self,mean,std):
        with torch.no_grad():
            self.head.weight.zero_();self.head.bias.zero_()
            self.head.bias[5:10]=mean+.01*torch.randn(5)
            sigma=max(float(std),.1)
            self.head.bias[10:15]=math.log(math.expm1(sigma-.05))

    def forward(self,wave,amplitude,context,mask,metadata_only=False,return_log=False):
        if metadata_only:
            wave=torch.zeros_like(wave);amplitude=torch.zeros_like(amplitude)
        valid=mask[:,None,:]
        if not torch.all(mask.any(-1)):raise ValueError("empty_mask")
        value=wave.masked_fill(~valid,0)
        for conv in self.convs:value=F.silu(conv(value))*valid
        mean=value.sum(-1)/mask.sum(-1,keepdim=True)
        maximum=value.masked_fill(~valid,-torch.inf).amax(-1)
        value=torch.cat((mean,maximum,amplitude,context),dim=1)
        parameters=self.head(F.silu(self.hidden(value)))
        alpha,mu,rho=parameters[:,:5],parameters[:,5:10],parameters[:,10:15]
        weights=F.log_softmax(alpha,dim=-1) if return_log else F.softmax(alpha,dim=-1)
        return weights,mu,.05+F.softplus(rho)


def mixture_nll(y,weights,mu,sigma,log_input=False):
    logpi=weights if log_input else torch.log(weights)
    return -torch.logsumexp(logpi-torch.log(sigma)-.5*math.log(2*math.pi)
                           -.5*((y[:,None]-mu)/sigma)**2,dim=-1)

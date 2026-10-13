"""Pure float64 all-positive S/P/D operators; no data IO, optimizer or authority."""
import math
import time
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from scipy.special import ndtr
from scipy.optimize import brentq
from scipy.integrate import quad, IntegrationWarning
import warnings


def need(ok,why):
    if not ok:raise ValueError(why)


def tensor(x,shape):
    need(type(x) in (torch.Tensor,nn.Parameter) and x.dtype==torch.float64 and x.device.type=='cpu' and tuple(x.shape)==shape and bool(torch.isfinite(x).all()),'tensor')
    need(bool((x.detach().abs()<=1e6).all()),'input_representation')


def scalar(x):return float(x.detach().cpu())


def precision(x,label):
    for value in x.detach().flatten().tolist():need(math.isfinite(value) and math.ulp(value)<=1e-10,label)


class Budget:
    def __init__(self,begin):
        need(type(begin) in (int,float) and math.isfinite(begin) and 0<=begin<=time.monotonic(),'processing_begin')
        self.begin=begin;self.points=0;self.terms=0
    def check(self,points=0,terms=0):
        self.points+=points;self.terms+=terms
        need(self.points<=1000000,'evaluation_cap');need(time.monotonic()-self.begin<=10,'deadline')
    def record(self):return dict(density_points=self.points,scalar_terms=self.terms,seconds=time.monotonic()-self.begin)


class Prior(nn.Module):
    def __init__(self,k):
        super().__init__();need(type(k) is int and 0<=k<=30,'prior_dimension');self.k=k
        self.first=nn.Linear(k,16,dtype=torch.float64) if k else None;self.first_bias=nn.Parameter(torch.zeros(16,dtype=torch.float64)) if not k else None;self.second=nn.Linear(16,16,dtype=torch.float64);self.head=nn.Linear(16,14,dtype=torch.float64)
    def initialize(self,train_mean,train_std):
        need(type(train_mean) in (int,float) and math.isfinite(train_mean) and abs(train_mean)<=1e6 and type(train_std) in (int,float) and math.isfinite(train_std) and 0<=train_std<=1e6,'train_initialization')
        with torch.no_grad():
            self.head.weight.normal_(0.,1e-3);self.head.bias.zero_()
            self.head.bias[4:9]=train_mean+.01*torch.randn(5,dtype=torch.float64)
            self.head.bias[9:14]=(lambda v:v+math.log(-math.expm1(-v)))(max(train_std,.1)-.05)

    def forward(self,context):
        tensor(context,(self.k,));first=self.first(context) if self.k else self.first_bias;v=self.head(F.silu(self.second(F.silu(first))))
        logw=F.log_softmax(torch.cat((v[:4],v.new_zeros(1))),dim=0)
        return logw,v[4:9],.05+F.softplus(v[9:14])


def validate_prior(prior):
    need(type(prior) in (tuple,list) and len(prior)==3,'prior')
    for value in prior:tensor(value,(5,))
    logw,mu,sigma=prior;need(abs(scalar(torch.logsumexp(logw,0)))<=1e-12 and bool((sigma>=.05).all()),'proper_prior')


def admit_allpositive(all_common_marks):
    # Caller must positively bind the full65/22 roster; no filtering API exists.
    need(type(all_common_marks) in (tuple,list) and len(all_common_marks)==87,'common_denominator')
    for horizons in all_common_marks:
        need(type(horizons) in (tuple,list) and len(horizons)==3,'horizons')
        counts=[]
        for mark in horizons:
            need(type(mark) is torch.Tensor and mark.ndim==2 and mark.shape[1]==3,'marks')
            tensor(mark,tuple(mark.shape));need(1<=mark.shape[0]<=20 and bool((mark>-12).all()),'allpositive_admission');counts.append(mark.shape[0])
        need(counts[1]-counts[0]==8 and counts[2]-counts[1]==8 and all(torch.equal(horizons[j][:counts[j-1]],horizons[j-1]) for j in (1,2)),'prefix')
    return True


def summary_mask(train_summary):
    need(type(train_summary) is torch.Tensor and train_summary.shape==(195,20),'summary_denominator');tensor(train_summary,(195,20))
    need(bool((train_summary[:,[4,9,14]]==0).all()),'allpositive_admission')
    varying=(train_summary!=train_summary[0]).any(0);return tuple(i for i in range(20) if i not in (4,9,14) and bool(varying[i]))


def capacity(k,active):
    need(type(k) is int and 0<=k<=30 and type(active) is tuple and len(set(active))==len(active) and all(type(i) is int and 0<=i<20 and i not in (4,9,14) for i in active),'capacity_schema')
    shared=16*k+526;counts={'S':shared+18,'P':shared+18,'D':shared+len(active)+1}
    need(max(counts.values())/min(counts.values())<=1.05,'capacity_spread');return counts


def summaries(marks,nu):
    need(type(marks) is torch.Tensor and marks.ndim==2 and marks.shape[1]==3,'marks');tensor(marks,tuple(marks.shape));tensor(nu,(12,3))
    j=len(marks);need(1<=j<=20 and bool((marks>-12).all()),'allpositive_admission')
    u=.25*torch.arange(j,dtype=torch.float64);du=u-u.mean();den=du.square().sum();values=[]
    for c in range(3):
        column=marks[:,c];slope=(du*(column-column.mean())).sum()/den if j>1 else column.new_zeros(())
        values.extend((column[-1],column.mean(),column.max(),slope,column.new_zeros(())))
    values.extend((marks.new_tensor(math.log1p(.25*j)),marks.new_tensor(float(j))))
    values.extend((nu.square().sum(0)/12).sqrt().unbind())
    return torch.stack(values)


def summary_scaler(train_summary):
    active=summary_mask(train_summary);varying=(train_summary!=train_summary[0]).any(0)
    std=torch.where(varying,train_summary.std(0,unbiased=False),torch.zeros(20,dtype=torch.float64))
    return train_summary.mean(0),std,active


def standardized_summary(value,mean,std):
    for x in (value,mean,std):tensor(x,(20,))
    need(bool((std>=0).all()),'summary_std');valid=std>0
    return torch.where(valid,(value-mean)/torch.where(valid,std,torch.ones_like(std)),torch.zeros_like(value))


def affine(coeff,marks,mref):
    tensor(coeff,(3,6));need(type(marks) is torch.Tensor and marks.ndim==2 and marks.shape[1]==3,'marks');tensor(marks,tuple(marks.shape))
    need(1<=marks.shape[0]<=20 and bool((marks>-12).all()),'allpositive_admission')
    need(type(mref) in (int,float) and math.isfinite(mref) and abs(mref)<=1e6,'mref')
    values=[]
    for j in range(marks.shape[0]):
        t=math.log1p(.25*j);previous=marks[j-1] if j else marks.new_zeros(3)
        a,b,d,e,rho,rawsigma=coeff.unbind(1);beta=b+e*t
        intercept=a+d*t+rho*previous-beta*mref;scale=.05+F.softplus(rawsigma)
        for value in (intercept,beta,scale):tensor(value,(3,))
        values.append((intercept,beta,scale,marks[j]))
    return values


class Posterior:
    def __init__(self,logw,mu,sigma,logz,budget,reference):
        need(logw.ndim==mu.ndim==sigma.ndim==1 and len(logw)==len(mu)==len(sigma)<=60,'posterior_shape')
        need(bool(torch.isfinite(logw).all()) and bool(torch.isfinite(mu).all()) and bool(torch.isfinite(sigma).all()) and bool((sigma>0).all()),'posterior_nonfinite')
        self.logw=logw;self.mu=mu;self.sigma=sigma;self.logz=logz;self.budget=budget;self.reference=reference
    def nll(self,target):
        need(type(target) is torch.Tensor and target.ndim==0 and target.dtype==torch.float64 and target.device.type=='cpu' and bool(torch.isfinite(target)),'target')
        self.budget.check(len(self.mu));terms=self.logw-torch.log(self.sigma)-.5*math.log(2*math.pi)-.5*((target-self.mu)/self.sigma).square()
        result=-torch.logsumexp(terms,0);precision(result,'target_precision');return result
    def mean(self):
        self.budget.check();return (self.logw.exp()*self.mu).sum()
    def arrays(self):return tuple(x.detach().cpu().numpy().copy() for x in (self.logw.exp(),self.mu,self.sigma))
    def cdf(self,x):
        need(type(x) in (int,float) and math.isfinite(x),'cdf_input');p,m,s=self.arrays();self.budget.check(len(p),len(p))
        answer=math.fsum(float(w*ndtr((x-u)/v)) for w,u,v in zip(p,m,s))/math.fsum(float(w) for w in p)
        need(0<=answer<=1,'cdf_probability');return answer
    def crps(self,target):
        need(type(target) in (int,float) and math.isfinite(target),'target');p,m,s=self.arrays();p=p/math.fsum(float(w) for w in p)
        def absolute(d,sd):
            self.budget.check(int(np.size(d)),int(np.size(d)));z=d/sd
            value=2*sd*np.exp(-.5*z*z)/math.sqrt(2*math.pi)+d*(2*ndtr(z)-1)
            need(np.isfinite(value).all() and all(math.ulp(float(v))<=1e-10 for v in value.flatten()),'proper_precision');return value
        first=float(np.sum(p*absolute(target-m,s)));pair=float(np.sum(p[:,None]*p[None,:]*absolute(m[:,None]-m[None,:],np.sqrt(s[:,None]**2+s[None,:]**2))))
        result=first-.5*pair;need(math.isfinite(result) and result>=0,'crps');return result
    def quantile(self,probability):
        need(type(probability) is float and 0<probability<1,'quantile_probability');_,m,s=self.arrays();lo=float(np.min(m-s));hi=float(np.max(m+s));span=hi-lo
        need(math.isfinite(span) and span>0,'quantile_bracket')
        for _ in range(1024):
            self.budget.check();fl=self.cdf(lo)-probability;fh=self.cdf(hi)-probability
            if fl<=0 and fh>=0:break
            if fl>0:lo-=span
            if fh<0:hi+=span
            span*=2;need(math.isfinite(lo) and math.isfinite(hi) and math.isfinite(span),'quantile_bracket')
        else:raise ValueError('quantile_bracket')
        return float(brentq(lambda x:self.cdf(x)-probability,lo,hi,xtol=1e-11,rtol=1e-14))


def marked(prior,marks,coeff,nu,arm,mref,*,processing_begin):
    budget=Budget(processing_begin);budget.check();validate_prior(prior);tensor(nu,(12,3));need(arm in ('S','P'),'arm')
    facts=affine(coeff,marks.clone(),mref);nu=nu.clone();logw,means,scales=(x.clone() for x in prior)
    support=nu if arm=='S' else nu.new_zeros(1,3);mass=(logw[None,:]-math.log(len(support))).expand(len(support),5).reshape(-1).clone()
    mean=means[None,:].expand(len(support),5).reshape(-1).clone();variance=scales.square()[None,:].expand(len(support),5).reshape(-1).clone()
    for a,b,s,y in facts:
        for c in range(3):
            budget.check(len(mean));intercept=(a[c]+support[:,c,None]).expand(len(support),5).reshape(-1)
            total=s[c].square()+b[c].square()*variance;innovation=y[c]-intercept-b[c]*mean
            mass=mass-.5*(torch.log(2*math.pi*total)+innovation.square()/total);precision(mass,'evidence_precision')
            first=mean*s[c].square();second=variance*b[c]*(y[c]-intercept);newmean=(first+second)/total;newvariance=variance*(s[c].square()/total)
            for f,g,n,t,sd in zip(first.detach().tolist(),second.detach().tolist(),newmean.detach().tolist(),total.detach().tolist(),newvariance.detach().sqrt().tolist()):
                bound=(4*math.ulp(f)+6*math.ulp(g)+math.ulp(f+g))/t+3*math.ulp(n);need(math.isfinite(bound) and bound<=1e-10*sd,'gaussian_mean_precision')
            mean,variance=newmean,newvariance
    logz=torch.logsumexp(mass,0);precision(logz,'evidence_precision');weights=mass-logz
    reference=dict(prior=tuple(x.detach().clone() for x in prior),facts=tuple(tuple(x.detach().clone() for x in f) for f in facts),nu=nu.detach().clone(),arm=arm)
    result=Posterior(weights,mean,variance.sqrt(),logz,budget,reference);budget.check();return result


def direct(prior,summary,theta,tau,active,*,processing_begin):
    budget=Budget(processing_begin);budget.check();validate_prior(prior);tensor(summary,(20,));capacity(0,active);tensor(theta,(len(active),));tensor(tau,())
    shift=(summary.clone()[list(active)]*theta).sum();logw,mu,sigma=prior;scales=.05+torch.exp(tau)*(sigma-.05)
    final=(logw,mu+shift,scales);validate_prior(final)
    result=Posterior(logw,mu+shift,scales,logw.new_zeros(()),budget,dict(prior=tuple(x.detach().clone() for x in final),facts=(),nu=summary.new_zeros(12,3),arm='P'));budget.check();return result


def checked_scores(posterior,target,reference):
    """Parent injects pinned independent frozen reference; no authority implied."""
    need(type(posterior) is Posterior and type(target) in (int,float) and math.isfinite(target),'score_input');budget=posterior.budget;budget.check()
    data=posterior.reference;p,mu,sigma=data['prior'];noise=data['nu'].tolist() if data['arm']=='S' else [[0.,0.,0.]]*12;w=[1/12]*12 if data['arm']=='S' else [1.]+[0.]*11
    state=reference.start(p.exp().tolist(),mu.tolist(),sigma.tolist(),noise,w)
    if data['facts']:state=reference.append(state,[dict(cell=j,a=a.tolist(),b=b.tolist(),sigma=s.tolist(),value=y.tolist()) for j,(a,b,s,y) in enumerate(data['facts'],1)])
    # All-positive frozen core: at most60 components, each1 constant-kernel
    # point plus3 target evaluations; reserve240 BEFORE reference construction.
    budget.check(240);independent=reference.Posterior(state,target,processing_begin=budget.begin)
    need(independent.budget.points<=240 and independent.budget.cdf_terms==0,'reference_reservation')
    score=dict(mean=scalar(posterior.mean()),nll=scalar(posterior.nll(torch.tensor(target,dtype=torch.float64))),crps=posterior.crps(target),pit=posterior.cdf(target))
    errors={k:abs(score[k]-independent.integrals['adaptive'][k]) for k in ('mean','nll')};errors['log_normalizer']=abs(scalar(posterior.logz)-independent.logz)
    need(all(v<=1e-4 for v in errors.values()),'independent_parity')
    def independent_cdf(x):
        budget.check(len(independent.components),len(independent.components));return independent.cdf(float(x))
    with warnings.catch_warnings():
        warnings.simplefilter('error',IntegrationWarning)
        _,centers,scales=posterior.arrays()
        knots=sorted(set([float(target)]+[float(m+k*s) for m,s in zip(centers,scales) for k in (-8,-4,-1,0,1,4,8)]))
        need(all(math.isfinite(x) for x in knots),'proper_knots')
        terms=[];quad_errors=[]
        def integrand(x):
            cdf=independent_cdf(float(x));return cdf*cdf if x<=target else (1-cdf)**2
        # Finite intervals use unit-interval coordinates; tails extend to infinity
        # from the outer component knot with an explicit local scale. No truncation.
        for lo,hi in zip(knots[:-1],knots[1:]):
            width=hi-lo;value,error=quad(lambda t:integrand(lo+width*t)*width,0.,1.,epsabs=1e-9,epsrel=1e-9,limit=200);terms.append(value);quad_errors.append(error)
        scale=float(np.max(scales));need(math.isfinite(scale) and scale>0,'proper_scale')
        for end,sign in ((knots[0],-1.),(knots[-1],1.)):
            value,error=quad(lambda t:integrand(end+sign*scale*t)*scale,0.,math.inf,epsabs=1e-9,epsrel=1e-9,limit=200);terms.append(value);quad_errors.append(error)
        proper_reference=math.fsum(terms);proper_error=math.fsum(quad_errors)
    errors['crps']=abs(score['crps']-proper_reference);errors['pit']=abs(score['pit']-independent_cdf(target))
    need(math.isfinite(proper_error) and proper_error<=1e-6 and errors['crps']<=1e-6 and errors['pit']<=1e-6,'proper_parity')
    quantiles={str(q):posterior.quantile(q) for q in (.025,.1,.25,.5,.75,.9,.975)}
    need(all(abs(independent_cdf(v)-float(q))<=1e-6 for q,v in quantiles.items()),'quantile_parity');score['quantiles']=quantiles;score['median']=quantiles['0.5']
    for level,lo,hi in ((50,.25,.75),(80,.1,.9),(95,.025,.975)):score['coverage_'+str(level)]=bool(quantiles[str(lo)]<=target<=quantiles[str(hi)])
    budget.check();score['diagnostics']=dict(errors=errors,work=budget.record(),allpositive_only=True,reference_reserved_points=240,reference_actual_points=independent.budget.points);return score


def forecast(prior,marks,coeff,nu,arm,mref,horizon,arrival_offset_ns,*,processing_begin):
    need(type(horizon) is int and horizon in (1,3,5) and type(arrival_offset_ns) is int and 0<=arrival_offset_ns<=750000000,'clock')
    count=(horizon*1000000000-arrival_offset_ns)//250000000
    need(type(marks) is torch.Tensor and marks.ndim==2 and len(marks)==count,'deadline_cells')
    return marked(prior,marks,coeff,nu,arm,mref,processing_begin=processing_begin)


class MarkedNet(nn.Module):
    def __init__(self,k,arm,mref):
        super().__init__();need(arm in ('S','P') and type(mref) in (int,float) and math.isfinite(mref) and abs(mref)<=1e6,'model')
        self.prior=Prior(k);self.arm=arm;self.mref=float(mref)
        initial=torch.tensor([[0.,.1,0.,.01,.1,math.log(math.expm1(.95))]]*3,dtype=torch.float64)
        self.coefficients=nn.Parameter(initial)
    def forward(self,context,marks,nu,*,processing_begin):
        return marked(self.prior(context),marks,self.coefficients,nu,self.arm,self.mref,processing_begin=processing_begin)


class DirectNet(nn.Module):
    def __init__(self,k,active):
        super().__init__();capacity(k,active);self.prior=Prior(k);self.active=active
        self.theta=nn.Parameter(torch.zeros(len(active),dtype=torch.float64));self.tau=nn.Parameter(torch.zeros((),dtype=torch.float64))
    def forward(self,context,standardized_summaries,*,processing_begin):
        return direct(self.prior(context),standardized_summaries,self.theta,self.tau,self.active,processing_begin=processing_begin)

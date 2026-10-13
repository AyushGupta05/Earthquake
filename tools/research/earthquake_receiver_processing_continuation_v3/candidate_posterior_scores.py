"""All-real adaptive posterior scores, with mode-scaled components and no truncation."""
import math
import warnings
import numpy as np
from scipy.integrate import quad,IntegrationWarning
from scipy.optimize import brentq
import numerical_core as core


class Posterior:
    def __init__(self,mixture,hazard,z,c,states,logz,mean,deadline):
        self.mean=float(mean);self.deadline=deadline;self.components=[]
        idx,y,u,r=core.transitions(states)
        intercept=hazard.logits(hazard.mref,z,c,idx,u,r);beta=hazard.beta[idx]
        sign=np.where(y==1,-1.,1.)
        def ll(m):
            deadline();value=-float(np.logaddexp(0.,sign*(intercept+(m-hazard.mref)*beta)).sum())
            if not math.isfinite(value):raise core.NumericalFailure('score_likelihood')
            return value
        for weight,mu,sigma in zip(mixture.weights,mixture.means,mixture.sigmas):
            if weight==0:continue
            slopes=beta*sigma;bound=float(np.abs(slopes).sum())
            def derivative(x):return float(-x+np.sum(slopes*(y-core._sigmoid(intercept+(mu+sigma*x-hazard.mref)*beta))))
            mode=0. if bound==0 else brentq(derivative,-bound,bound,xtol=1e-12,maxiter=500)
            prob=core._sigmoid(intercept+(mu+sigma*mode-hazard.mref)*beta)
            scale=1/math.sqrt(float(1.+np.sum(slopes*slopes*prob*(1-prob))))
            peak=-.5*mode*mode-.5*math.log(2*math.pi)+ll(mu+sigma*mode)
            def density(t,mu=float(mu),sigma=float(sigma),mode=mode,scale=scale,peak=peak):
                x=mode+scale*t
                if not math.isfinite(x) or not math.isfinite(mu+sigma*x):raise core.NumericalFailure('score_point')
                exponent=-.5*x*x-.5*math.log(2*math.pi)+ll(mu+sigma*x)-peak
                if exponent>1e-7:raise core.NumericalFailure('score_mode')
                return math.exp(exponent)
            mass=self.integrate(density,-np.inf,np.inf)
            if mass<=0:raise core.NumericalFailure('score_mass')
            logmass=math.log(weight)+peak+math.log(scale)+math.log(mass)
            self.components.append((float(mu),float(sigma),mode,scale,density,mass,logmass))
        computed=float(core._lse([x[-1] for x in self.components]))
        if abs(computed-logz)>1e-4:raise core.NumericalFailure('score_normalizer_parity')
        self.weights=np.exp(np.asarray([x[-1] for x in self.components])-computed)

    def integrate(self,fn,lo,hi):
        self.deadline()
        with warnings.catch_warnings():
            warnings.simplefilter('error',IntegrationWarning)
            result=quad(fn,lo,hi,epsabs=1e-9,epsrel=1e-9,limit=200,full_output=1)
        if len(result)!=3:raise core.NumericalFailure('score_integral_convergence')
        value,error,_=result
        if not math.isfinite(value) or not math.isfinite(error) or error>max(1e-7,abs(value)*1e-7):raise core.NumericalFailure('score_integral_error')
        return value

    def cdf(self,value):
        self.deadline();total=0.
        for weight,(mu,sigma,mode,scale,fn,mass,_) in zip(self.weights,self.components):
            t=((value-mu)/sigma-mode)/scale
            # Choose the nearer all-real tail to avoid cancellation near one.
            part=self.integrate(fn,-np.inf,t)/mass if t<=0 else 1.-self.integrate(fn,t,np.inf)/mass
            total+=float(weight)*part
        if not math.isfinite(total) or total< -1e-7 or total>1+1e-7:raise core.NumericalFailure('score_cdf_bounds')
        return min(1.,max(0.,total)) # Only integration roundoff, never magnitude/density support.

    def quantile(self,q):
        if not 0<q<1:raise ValueError('score_quantile')
        width=max(1.,max(x[1] for x in self.components));lo=self.mean-width;hi=self.mean+width
        for _ in range(128):
            self.deadline()
            if self.cdf(lo)<=q<=self.cdf(hi):return float(brentq(lambda x:self.cdf(x)-q,lo,hi,xtol=1e-9,maxiter=200))
            width*=2;lo=self.mean-width;hi=self.mean+width
            if not math.isfinite(width):break
        raise core.NumericalFailure('score_quantile_bracket')

    def crps(self,target):
        first=rank=0.
        for weight,(mu,sigma,mode,scale,fn,mass,_) in zip(self.weights,self.components):
            boundary=((target-mu)/sigma-mode)/scale
            def magnitude(t):return mu+sigma*(mode+scale*t)
            term=lambda t:abs(magnitude(t)-target)*fn(t)
            # Keep the mode inside an all-real integral even for far-tail labels.
            absolute=(self.integrate(term,-np.inf,boundary)+self.integrate(term,boundary,np.inf)) if abs(boundary)<=8 else self.integrate(term,-np.inf,np.inf)
            first+=float(weight)*absolute/mass
            rank+=float(weight)*self.integrate(lambda t:(magnitude(t)-self.mean)*(2*self.cdf(magnitude(t))-1)*fn(t),-np.inf,np.inf)/mass
        value=first-rank
        if not math.isfinite(value) or value< -1e-7:raise core.NumericalFailure('score_crps')
        return max(0.,value)


def scores(mixture,hazard,z,c,states,target,checked,deadline):
    if not checked['accepted']:raise core.NumericalFailure('unaccepted_density')
    posterior=Posterior(mixture,hazard,z,c,states,checked['adaptive'].log_normalizer,checked['adaptive'].mean,deadline)
    quantiles={str(q):posterior.quantile(q) for q in (.025,.1,.25,.5,.75,.9,.975)}
    return dict(mean=checked['gh64'].mean,median=quantiles['0.5'],nll=checked['gh64'].nll,crps=posterior.crps(target),
                pit=posterior.cdf(target),quantiles=quantiles,coverage_50=quantiles['0.25']<=target<=quantiles['0.75'],
                coverage_80=quantiles['0.1']<=target<=quantiles['0.9'],coverage_95=quantiles['0.025']<=target<=quantiles['0.975'])

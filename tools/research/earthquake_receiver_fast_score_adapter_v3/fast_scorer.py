"""Vectorized all-real scoring of the unchanged affine-logistic mixture."""
import math
import time
from functools import lru_cache
import numpy as np
from numpy.polynomial.legendre import legvander
from scipy.optimize import brentq
from scipy.special import expit, logsumexp, roots_legendre


class NumericalFailure(ValueError):
    def __init__(self,reason,evidence=None):
        self.evidence=evidence
        super().__init__(reason)


def number(v):return type(v)in(int,float)and math.isfinite(v)


@lru_cache(maxsize=4)
def rule(n):
    nodes,weights=roots_legendre(n)
    vander=legvander(nodes,n)
    primitive=np.empty((n,n));primitive[:,0]=nodes+1
    for k in range(1,n):primitive[:,k]=(vander[:,k+1]-vander[:,k-1])/(2*k+1)
    coefficients=(vander[:,:n]*weights[:,None]*((2*np.arange(n)+1)/2)[None,:]).T
    return nodes,weights,coefficients,primitive


class Density:
    def __init__(self,pi,mu,sigma,affine,*,processing_begin,budget_seconds=10):
        if any(type(v)is not list or len(v)!=5 for v in(pi,mu,sigma))or any(not number(x)for v in(pi,mu,sigma)for x in v):raise NumericalFailure('mixture')
        if any(x<0 for x in pi)or abs(math.fsum(pi)-1)>1e-6 or any(x<.05 for x in sigma):raise NumericalFailure('mixture')
        if type(affine)is not list or len(affine)>19 or any(type(p)is not list or len(p)!=2 or any(not number(x)for x in p)for p in affine):raise NumericalFailure('affine')
        if not number(processing_begin)or not 0<=processing_begin<=time.monotonic()or not number(budget_seconds)or not 0<budget_seconds<=10:raise NumericalFailure('deadline')
        self.started=processing_begin;self.budget=budget_seconds;self.evaluations=0
        self.pi,self.mu,self.sigma=(np.asarray(v,dtype=np.float64)for v in(pi,mu,sigma));self.affine=affine
        self.a=np.asarray([v[0]for v in affine]);self.b=np.asarray([v[1]for v in affine])
        modes=[];widths=[];peaks=[]
        for p,m,s in zip(self.pi,self.mu,self.sigma):
            if p==0:continue
            def derivative(x):
                self.check()
                return -(x-m)/(s*s)+float(np.dot(self.b,expit(-(self.a+self.b*x))))
            lo=float(m+s*s*np.minimum(self.b,0).sum());hi=float(m+s*s*np.maximum(self.b,0).sum())
            if not math.isfinite(lo)or not math.isfinite(hi):raise NumericalFailure('mode')
            flo,fhi=derivative(lo),derivative(hi)
            if flo<0 or fhi>0:raise NumericalFailure('mode_bracket')
            mode=lo if lo==hi or flo==0 else hi if fhi==0 else brentq(derivative,lo,hi,xtol=1e-11,rtol=1e-13,maxiter=200)
            logits=self.a+self.b*mode;curvature=1/(s*s)+float(np.dot(self.b*self.b,expit(logits)*expit(-logits)))
            width=1/math.sqrt(curvature)
            if not math.isfinite(width)or width<=0:raise NumericalFailure('mode_scale')
            modes.append(mode);widths.append(width)
            peaks.append(math.log(float(p))-math.log(float(s))-.5*math.log(2*math.pi)-.5*((mode-m)/s)**2-float(np.logaddexp(0,-logits).sum()))
        self.modes=np.asarray(modes);self.widths=np.asarray(widths);self.offset=float(max(peaks))
        self.center=float(self.modes.min()/2+self.modes.max()/2)
        self.scale=float(max(self.sigma.max(),np.max(np.abs(self.modes-self.center)+self.widths)))
        if not number(self.scale)or self.scale<=0 or not number(self.offset):raise NumericalFailure('representation')
        anchors=[]
        for p,m,s in zip(self.pi,self.mu,self.sigma):
            if p:
                for k in(-8,-4,-1,0,1,4,8):anchors.append(float(m+k*s))
        for m,w in zip(modes,widths):
            for k in(-4,-1,0,1,4):anchors.append(m+k*w)
        for a,b in affine:
            if b:anchors.append(-a/b)
        self.anchors=anchors
        self.check()

    def check(self):
        if time.monotonic()-self.started>self.budget:raise NumericalFailure('deadline')
        if self.evaluations>2_000_000:raise NumericalFailure('evaluation_cap')

    def compact(self,x):
        r=(np.asarray(x,dtype=np.float64)-self.center)/self.scale
        t=2*r/(1+np.hypot(1,2*r))
        if not np.isfinite(t).all()or np.any(np.abs(t)>=1):raise NumericalFailure('compact_representation')
        return t

    def real(self,t):return self.center+self.scale*t/(1-t*t)

    def log_pdf_unnormalized(self,x):
        value=np.asarray(x,dtype=np.float64);flat=value.reshape(-1)
        self.evaluations+=flat.size;self.check()
        with np.errstate(over='ignore',invalid='raise',divide='ignore'):
            lognormal=np.where(self.pi>0,np.log(self.pi),-np.inf)[None,:]-np.log(self.sigma)[None,:]-.5*math.log(2*math.pi)-.5*((flat[:,None]-self.mu[None,:])/self.sigma[None,:])**2
            likelihood=-np.logaddexp(0,-(self.a[None,:]+flat[:,None]*self.b[None,:])).sum(axis=1)
            out=logsumexp(lognormal,axis=1)+likelihood
        if np.isnan(out).any()or np.isposinf(out).any():raise NumericalFailure('log_density')
        return out.reshape(value.shape)

    def transformed(self,t):
        m=self.real(t);jac=self.scale*(1+t*t)/(1-t*t)**2
        logg=self.log_pdf_unnormalized(m)-self.offset+np.log(jac)
        with np.errstate(over='raise',invalid='raise'):
            g=np.exp(logg)
        if not np.isfinite(g).all():raise NumericalFailure('density')
        return m,jac,g


class Table:
    def __init__(self,density,cuts,n):
        self.density=density;self.cuts=np.asarray(cuts);self.n=n
        nodes,weights,coef,primitive=rule(n)
        self.mid=(self.cuts[:-1]+self.cuts[1:])/2;self.half=(self.cuts[1:]-self.cuts[:-1])/2
        t=self.mid[:,None]+self.half[:,None]*nodes[None,:]
        self.m,self.jac,self.g=density.transformed(t)
        self.coefficients=self.g@coef.T
        self.mass=np.sum(self.g*weights[None,:],axis=1)*self.half
        self.total=float(self.mass.sum())
        if not math.isfinite(self.total)or self.total<=0 or np.any(self.mass<0):raise NumericalFailure('mass')
        self.prefix=np.r_[0.,np.cumsum(self.mass)[:-1]];self.suffix=np.r_[np.cumsum(self.mass[::-1])[::-1][1:],0.]
        partial=(self.coefficients@primitive.T)*self.half[:,None]
        reverse=(self.coefficients*((-1.)**np.arange(n))[None,:])@primitive[::-1].T*self.half[:,None]
        self.cdf=(self.prefix[:,None]+partial)/self.total;self.sf=(self.suffix[:,None]+reverse)/self.total
        self.weights=self.g*weights[None,:]*self.half[:,None]/self.total
        if not np.isfinite(self.cdf).all()or not np.isfinite(self.sf).all():raise NumericalFailure('cdf')
        self.log_normalizer=density.offset+math.log(self.total)
        self.mean=float(density.center+np.sum(self.weights*(self.m-density.center)))

    def cdf_survival_compact(self,t):
        if t==-1:return 0.,1.
        if t==1:return 1.,0.
        index=int(np.searchsorted(self.cuts,t,side='right')-1)
        index=min(max(index,0),len(self.half)-1)
        z=(t-self.mid[index])/self.half[index]
        v=legvander(np.asarray([z,-z]),self.n)
        primitive=np.empty((2,self.n));primitive[:,0]=np.asarray([z,-z])+1
        for k in range(1,self.n):primitive[:,k]=(v[:,k+1]-v[:,k-1])/(2*k+1)
        left=float((self.prefix[index]+self.half[index]*np.dot(self.coefficients[index],primitive[0]))/self.total)
        right=float((self.suffix[index]+self.half[index]*np.dot(self.coefficients[index]*(-1.)**np.arange(self.n),primitive[1]))/self.total)
        # The spectral antiderivative is a numerical approximation. Retain
        # its tiny endpoint roundoff internally; never clip probabilities.
        if not -1e-10<=left<=1+1e-10 or not -1e-10<=right<=1+1e-10:raise NumericalFailure('cdf_probability')
        return (left,1-left)if left<=.5 else(1-right,right)

    def quantile(self,q):
        t=brentq(lambda t:self.cdf_survival_compact(t)[0]-q,-1.,1.,xtol=1e-14,rtol=1e-14,maxiter=200)
        return float(self.density.real(t))

    def scores(self,target):
        d=self.density
        absolute=float(np.sum(self.weights*np.abs(self.m-target)))
        # The pair half-absolute-distance term uses one expectation and a
        # continuous spectral antiderivative, not nested scalar integrations.
        pair=float(np.sum(self.weights*(self.m-self.mean)*(self.cdf-self.sf)))
        crps=absolute-pair
        alternative=absolute-float(np.sum(rule(self.n)[1][None,:]*self.half[:,None]*self.jac*self.cdf*self.sf))
        quantiles={str(q):self.quantile(q)for q in(.025,.1,.25,.5,.75,.9,.975)}
        out=dict(log_normalizer=self.log_normalizer,mean=self.mean,nll=float(-d.log_pdf_unnormalized(target)+self.log_normalizer),crps=crps,median=quantiles['0.5'],pit=self.cdf_survival_compact(float(d.compact(target)))[0],quantiles=quantiles)
        for c in(.5,.8,.95):out['coverage_%d'%round(c*100)]=float(quantiles[str((1-c)/2)]<=target<=quantiles[str((1+c)/2)])if c==.5 else float(quantiles['0.1'if c==.8 else'0.025']<=target<=quantiles['0.9'if c==.8 else'0.975'])
        out['absolute_moment']=absolute;out['pair_half_moment']=pair;out['cdf_product']=absolute-alternative
        return out,alternative

    def gradients(self):
        """Analytic log-Z derivatives evaluated by accepted quadrature.

        This differentiates the continuous operator, not the adaptive mesh or
        a Torch graph. Logit derivatives refer to a normalized softmax prior.
        """
        d=self.density;m=self.m.reshape(-1);w=self.weights.reshape(-1)
        with np.errstate(over='raise',invalid='raise',divide='ignore'):
            component=np.where(d.pi>0,np.log(d.pi),-np.inf)[None,:]-np.log(d.sigma)[None,:]-.5*math.log(2*math.pi)-.5*((m[:,None]-d.mu[None,:])/d.sigma[None,:])**2
            responsibilities=np.exp(component-logsumexp(component,axis=1)[:,None])
            gaussian_mu=(m[:,None]-d.mu[None,:])/d.sigma[None,:]**2
            gaussian_log_sigma=((m[:,None]-d.mu[None,:])/d.sigma[None,:])**2-1
            logistic=expit(-(d.a[None,:]+m[:,None]*d.b[None,:]))
        return dict(logits=(np.sum(w[:,None]*responsibilities,axis=0)-d.pi/d.pi.sum()).tolist(),
                    mu=np.sum(w[:,None]*responsibilities*gaussian_mu,axis=0).tolist(),
                    log_sigma=np.sum(w[:,None]*responsibilities*gaussian_log_sigma,axis=0).tolist(),
                    intercept=np.sum(w[:,None]*logistic,axis=0).tolist(),
                    slope=np.sum(w[:,None]*logistic*m[:,None],axis=0).tolist())


def _difference(a,b):
    fields=('log_normalizer','mean','nll','crps','median','pit')
    out={k:abs(a[k]-b[k])for k in fields}
    out['quantiles']=max(abs(a['quantiles'][k]-b['quantiles'][k])for k in a['quantiles'])
    return out


def score(pi,mu,sigma,affine,target,*,processing_begin,budget_seconds=10,tolerance=1e-6,require_gh=True,gradients=False):
    """Same operator, all-real numerical score; no actual-study authority."""
    if not number(target)or not number(tolerance)or not 1e-8<=tolerance<=1e-6 or type(require_gh)is not bool or type(gradients)is not bool:raise NumericalFailure('arguments')
    d=Density(pi,mu,sigma,affine,processing_begin=processing_begin,budget_seconds=budget_seconds)
    cuts=sorted(set([-1.,1.]+[float(d.compact(x))for x in d.anchors+[target]]))
    if len(cuts)>128:raise NumericalFailure('initial_intervals')
    error=None
    for iteration in range(8):
        d.check();low=Table(d,cuts,32);high=Table(d,cuts,64)
        try:
            ls,la=low.scores(target);hs,ha=high.scores(target)
            error=_difference(ls,hs);error['crps_identity']=abs(hs['crps']-ha)
            defect=max(0.,-float(high.cdf.min()),-float(high.sf.min()),float(high.cdf.max())-1,float(high.sf.max())-1)
            error['cdf_internal_defect']=defect
            probability=defect<=1e-10
            passed=probability and all(v<=tolerance*(1+abs(hs[k] if k in hs and number(hs[k])else hs['crps'] if k=='crps_identity'else 1.))for k,v in error.items())
        except NumericalFailure:
            passed=False
        if passed:break
        # Refine intervals whose mass/moment disagree; also split when a
        # score/CDF error remains despite small mass error.
        indicator=np.abs(low.mass-high.mass)+np.abs(np.sum(low.weights*low.m,axis=1)-np.sum(high.weights*high.m,axis=1))*high.total
        ids=np.flatnonzero(indicator>max(1e-12,high.total*tolerance/len(indicator)))
        if not len(ids):ids=np.arange(len(indicator))
        cuts=sorted(set(cuts+[(cuts[i]+cuts[i+1])/2 for i in ids]))
        if len(cuts)>513:raise NumericalFailure('interval_cap',error)
    else:raise NumericalFailure('convergence',error)
    # Independent mode-scaled QUADPACK reference is authored prior source,
    # with no candidate core. Only a handful of CDF evaluations are needed.
    from reference import Posterior,hermite
    class TimedReference(Posterior):
        @staticmethod
        def _quad(function,left,right):
            def checked(x):d.check();return function(x)
            return Posterior._quad(checked,left,right)
    reference=TimedReference(pi,mu,sigma,affine)
    try:
        ref=dict(log_normalizer=reference.log_normalizer,mean=reference.mean,nll=-reference.log_pdf(target))
        parity={k:abs(hs[k]-ref[k])for k in ref}
        cdf_errors=[abs(reference.cdf_survival(x)[0]-q)for q,x in((float(k),v)for k,v in hs['quantiles'].items())]
        reference_pit=reference.cdf_survival(target)[0]
        cdf_errors.append(abs(reference_pit-hs['pit']))
        parity['cdf']=max(cdf_errors)
        # Seed every local mode in the absolute-moment reference. A single
        # remote label split can miss a narrow mode in infinite-interval quad.
        absolute_parts=[]
        for weight,component in zip(reference.weights,reference.components):
            split=(target-component['mode'])/component['scale']
            knots=sorted(set([-math.inf,-8.,-4.,-1.,0.,1.,4.,8.,split,math.inf]))
            def absolute_kernel(t):return abs(component['mode']+component['scale']*t-target)*component['kernel'](t)
            integral=math.fsum(reference._quad(absolute_kernel,a,b)for a,b in zip(knots,knots[1:]))
            absolute_parts.append(float(weight)*integral/component['integral'])
        parity['absolute_moment']=abs(hs['absolute_moment']-math.fsum(absolute_parts))
        if any(not math.isfinite(v)or v>1e-4 for v in parity.values()):raise NumericalFailure('reference_parity',parity)
        if hs['crps']<0 or not all(number(hs[k])for k in('log_normalizer','mean','nll','crps','median','pit','absolute_moment','pair_half_moment','cdf_product')):raise NumericalFailure('score')
        gh64=hermite(pi,mu,sigma,affine,target,64);gh128=hermite(pi,mu,sigma,affine,target,128)
        gh_errors={k:max(ref[k],gh64[k],gh128[k])-min(ref[k],gh64[k],gh128[k])for k in ref}
        if require_gh and any(not math.isfinite(v)or v>1e-4 for v in gh_errors.values()):raise NumericalFailure('gh_parity',gh_errors)
        hs['pit']=reference_pit  # always use the independent adaptive target CDF
        derivatives=high.gradients()if gradients else None
        if derivatives is not None:
            lower=low.gradients()
            gradient_error=max((max((abs(x-y)for x,y in zip(derivatives[k],lower[k])),default=0.)for k in derivatives),default=0.)
            if not math.isfinite(gradient_error)or gradient_error>1e-5:raise NumericalFailure('gradient_parity',gradient_error)
        else:gradient_error=None
        d.check()
        return dict(accepted=require_gh,diagnostic_only=not require_gh,score=hs,error=error,reference_error=parity,gh_error=gh_errors,gh_required=require_gh,gradients=derivatives,gradient_error=gradient_error,work=dict(vector_points=d.evaluations,reference_points=reference.evaluations,intervals=len(cuts)-1,refinements=iteration),method='vectorized-all-real-legendre-CDF-v3')
    finally:
        reference._cdf_cache.clear();reference.components.clear()

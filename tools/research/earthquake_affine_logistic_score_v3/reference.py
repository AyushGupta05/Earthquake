"""Independent all-real adaptive affine-logistic mixture integration."""
import math
import warnings
import numpy as np
from scipy.integrate import quad, IntegrationWarning
from scipy.optimize import brentq
from scipy.special import expit, logsumexp, ndtr

MAX_EVALUATIONS = 2_000_000


class NumericalFailure(ValueError):
    def __init__(self,reason,evidence=None):
        self.evidence=evidence
        super().__init__(reason)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def ages(states):
    if type(states) is not list or not 1 <= len(states) <= 20 or any(type(b) is not int or b not in (0, 1) for b in states):
        raise NumericalFailure('states')
    out = []
    for i, b in enumerate(states):
        out.append(out[-1] + 1 if i and b == states[i-1] else 1)
    return out


def factors(mode, states, z, c, hazard, mref):
    """Signed affine factors for observed edges only; no terminal exit."""
    run = ages(states)
    if mode not in ('C', 'H', 'T') or not finite(mref):
        raise NumericalFailure('mode')
    if type(z) is not list or type(c) is not list or len(z) < 2 or len(c) < 1 or any(not finite(v) for v in z+c):
        raise NumericalFailure('context')
    if type(hazard) is not dict or set(hazard) != {'alpha', 'beta', 'v', 'w', 'gamma', 'eta'}:
        raise NumericalFailure('hazard')
    for name in ('alpha', 'beta', 'gamma', 'eta'):
        value = hazard[name]
        if type(value) is not list or len(value) != 2 or any(not finite(v) for v in value):
            raise NumericalFailure('hazard')
    for name, width in (('v', len(z)), ('w', len(c))):
        value = hazard[name]
        if type(value) is not list or len(value) != 2 or any(type(row) is not list or len(row) != width or any(not finite(v) for v in row) for row in value):
            raise NumericalFailure('hazard')
    result = []
    for j in range(1, len(states)):
        s = states[j-1]  # on=0, off=1
        intercept = (hazard['alpha'][s] + math.fsum(a*b for a,b in zip(hazard['v'][s],z))
                     + math.fsum(a*b for a,b in zip(hazard['w'][s],c))
                     + hazard['gamma'][s]*math.log1p(j/4) - hazard['beta'][s]*mref)
        extra = math.log1p(run[j-1]) if mode == 'C' else math.log1p(j) if mode == 'T' else z[0]*z[1] if s == 0 else z[0]*c[0]
        intercept += hazard['eta'][s]*extra
        sign = 1 if states[j] != states[j-1] else -1
        pair = [sign*intercept, sign*hazard['beta'][s]]
        if any(not finite(v) for v in pair):
            raise NumericalFailure('affine_overflow')
        result.append(pair)
    return result


class Posterior:
    """Numerical posterior, component-wise log-concave all-real integration.

    Factors are signed [intercept,slope] in log sigmoid(intercept+slope*m).
    The affine mode bracket is for root finding only, never integral support.
    """
    def __init__(self, pi, mu, sigma, affine):
        if any(type(v) is not list or len(v) != 5 for v in (pi,mu,sigma)) or any(not finite(x) for v in (pi,mu,sigma) for x in v):
            raise NumericalFailure('mixture')
        if any(x < 0 for x in pi) or abs(math.fsum(pi)-1) > 1e-6 or any(x < .05 for x in sigma):
            raise NumericalFailure('mixture')
        if type(affine) is not list or len(affine) > 19 or any(type(p) is not list or len(p) != 2 or any(not finite(x) for x in p) for p in affine):
            raise NumericalFailure('affine')
        self.pi, self.mu, self.sigma = (np.asarray(v,dtype=np.float64) for v in (pi,mu,sigma))
        self.a = np.asarray([p[0] for p in affine],dtype=np.float64)
        self.b = np.asarray([p[1] for p in affine],dtype=np.float64)
        self.evaluations = 0
        self.components = []
        for weight, mean, sd in zip(self.pi,self.mu,self.sigma):
            mean,sd = float(mean),float(sd)
            if weight == 0:
                continue
            def derivative(x):
                logits = self._logits(x)
                return -(x-mean)/(sd*sd) + float(np.dot(self.b,expit(-logits)))
            lo = float(mean + sd*sd*float(np.minimum(self.b,0).sum()))
            hi = float(mean + sd*sd*float(np.maximum(self.b,0).sum()))
            if not math.isfinite(lo) or not math.isfinite(hi):
                raise NumericalFailure('mode_bracket')
            mode = lo if lo == hi or derivative(lo) == 0 else hi if derivative(hi) == 0 else brentq(derivative,lo,hi,xtol=1e-11,rtol=1e-13,maxiter=200)
            logits = self._logits(mode)
            curvature = float(1/(sd*sd) + np.dot(self.b*self.b,expit(logits)*expit(-logits)))
            scale = 1/math.sqrt(curvature)
            if not math.isfinite(scale) or scale <= 0:
                raise NumericalFailure('curvature')
            def log_kernel(x, mean=mean, sd=sd):
                return -.5*((x-mean)/sd)**2 + self.log_likelihood(x)
            peak = log_kernel(mode)
            def kernel(t, mode=mode, scale=scale, peak=peak, log_kernel=log_kernel):
                self.evaluations += 1
                if self.evaluations > MAX_EVALUATIONS:
                    raise NumericalFailure('evaluation_cap')
                difference = log_kernel(mode+scale*t)-peak
                if math.isnan(difference) or difference > 1e-5:
                    raise NumericalFailure('mode_scale')
                return math.exp(difference)
            integral = self._quad(kernel,-math.inf,math.inf)
            moment = self._quad(lambda t: t*kernel(t),-math.inf,math.inf)
            if integral <= 0:
                raise NumericalFailure('zero_mass')
            log_mass = math.log(float(weight)) - math.log(float(sd)) - .5*math.log(2*math.pi) + peak + math.log(scale) + math.log(integral)
            self.components.append(dict(mode=mode,scale=scale,kernel=kernel,integral=integral,log_mass=log_mass,mean=mode+scale*moment/integral))
        self.log_normalizer = float(logsumexp([v['log_mass'] for v in self.components]))
        raw_weights = np.exp(np.asarray([v['log_mass'] for v in self.components])-self.log_normalizer)
        self.weights = raw_weights / raw_weights.sum()  # normalization of the integrated posterior
        self.mean = float(np.dot(self.weights,[v['mean'] for v in self.components]))
        if not math.isfinite(self.log_normalizer) or not math.isfinite(self.mean):
            raise NumericalFailure('moment')
        self._cdf_cache = {}

    def _logits(self, x):
        with np.errstate(over='raise',invalid='raise'):
            value = self.a + self.b*x
        if not np.isfinite(value).all():
            raise NumericalFailure('logit_overflow')
        return value

    def log_likelihood(self, x):
        return float(-np.logaddexp(0,-self._logits(x)).sum())

    @staticmethod
    def _quad(function, left, right):
        with warnings.catch_warnings():
            warnings.simplefilter('error',IntegrationWarning)
            try:
                value,error = quad(function,left,right,epsabs=1e-9,epsrel=1e-9,limit=200)
            except (IntegrationWarning,OverflowError,FloatingPointError) as exc:
                raise NumericalFailure('quadrature') from exc
        if not math.isfinite(value) or not math.isfinite(error) or error > 2e-7*(1+abs(value)):
            raise NumericalFailure('quadrature_error')
        return float(value)

    def log_pdf(self, x):
        if not finite(x):
            raise NumericalFailure('target')
        with np.errstate(over='raise',invalid='raise',divide='ignore'):
            value = np.where(self.pi>0,np.log(self.pi),-np.inf)-np.log(self.sigma)-.5*math.log(2*math.pi)-.5*((x-self.mu)/self.sigma)**2
        return float(logsumexp(value)+self.log_likelihood(x)-self.log_normalizer)

    def cdf_survival(self, x):
        if x in self._cdf_cache:
            return self._cdf_cache[x]
        if not finite(x):
            raise NumericalFailure('cdf_argument')
        lefts,rights = [],[]
        for component in self.components:
            t = (x-component['mode'])/component['scale']
            if t <= 0:
                left = self._quad(component['kernel'],-math.inf,t)/component['integral']
                right = 1-left
            else:
                right = self._quad(component['kernel'],t,math.inf)/component['integral']
                left = 1-right
            if not 0 <= left <= 1 or not 0 <= right <= 1:
                raise NumericalFailure('cdf_probability')
            lefts.append(left);rights.append(right)
        left,right = float(np.dot(self.weights,lefts)),float(np.dot(self.weights,rights))
        value = (left,1-left) if left <= .5 else (1-right,right)
        if len(self._cdf_cache) >= 50_000:
            raise NumericalFailure('cdf_cache_cap')
        self._cdf_cache[x] = value
        return value

    def quantile(self, q):
        if not finite(q) or not 0 < q < 1:
            raise NumericalFailure('quantile')
        modes = [c['mode'] for c in self.components]
        step = max(float(self.sigma.max()),max(c['scale'] for c in self.components),1.)
        lo,hi = min(modes)-step,max(modes)+step
        for _ in range(100):
            if self.cdf_survival(lo)[0] <= q <= self.cdf_survival(hi)[0]:
                return float(brentq(lambda x:self.cdf_survival(x)[0]-q,lo,hi,xtol=1e-8,rtol=1e-12,maxiter=200))
            step *= 2;lo,hi = min(modes)-step,max(modes)+step
            if not math.isfinite(lo) or not math.isfinite(hi):
                break
        raise NumericalFailure('quantile_bracket')

    def crps(self, target):
        absolute = 0.
        for weight,c in zip(self.weights,self.components):
            split = (target-c['mode'])/c['scale']
            def f(t):
                return abs(c['mode']+c['scale']*t-target)*c['kernel'](t)
            absolute += float(weight)*(self._quad(f,-math.inf,split)+self._quad(f,split,math.inf))/c['integral']
        center = self.mean
        scale = max(float(self.sigma.max()),max(abs(c['mode']-center)+c['scale'] for c in self.components),1.)
        knots = sorted(set((c['mode']-center)/scale for c in self.components))
        def f(t):
            cdf,survival = self.cdf_survival(center+scale*t)
            return scale*cdf*survival
        pair_half = math.fsum(self._quad(f,a,b) for a,b in zip([-math.inf]+knots,knots+[math.inf]))
        result = absolute-pair_half
        if not math.isfinite(result) or result < -1e-7:
            raise NumericalFailure('crps')
        return result

    def score(self, target):
        value = dict(log_normalizer=self.log_normalizer,mean=self.mean,nll=-self.log_pdf(target),
                     median=self.quantile(.5),pit=self.cdf_survival(target)[0],crps=self.crps(target))
        for coverage in (.5,.8,.95):
            value['coverage_%d'%round(coverage*100)] = float(self.quantile((1-coverage)/2)<=target<=self.quantile((1+coverage)/2))
        if any(not math.isfinite(v) for v in value.values()):
            raise NumericalFailure('score')
        return value


def mixture_from_raw(raw):
    if type(raw) is not list or len(raw)!=15 or any(not finite(v) for v in raw):
        raise NumericalFailure('base_raw')
    value=np.asarray(raw,dtype=np.float64)
    pi=np.exp(value[:5]-logsumexp(value[:5]))
    sigma=.05+np.logaddexp(0,value[10:])
    return pi.tolist(),value[5:10].tolist(),sigma.tolist()


def hermite(pi,mu,sigma,affine,target,n):
    """Independent NumPy polynomial GH check; adaptive remains primary reference."""
    from numpy.polynomial.hermite import hermgauss
    nodes,weights=hermgauss(n)
    p,m,s=(np.asarray(v,dtype=np.float64)for v in (pi,mu,sigma))
    x=m[:,None]+math.sqrt(2)*s[:,None]*nodes
    likelihood=np.zeros_like(x)
    with np.errstate(over='raise',invalid='raise',divide='ignore'):
        for a,b in affine:likelihood-=np.logaddexp(0,-(a+b*x))
        terms=np.where(p[:,None]>0,np.log(p[:,None]),-np.inf)+np.log(weights)[None,:]-.5*math.log(math.pi)+likelihood
        logz=float(logsumexp(terms));center=float(np.dot(p,m)/p.sum())
        mean=float(center+np.sum(np.exp(terms-logz)*((m-center)[:,None]+math.sqrt(2)*s[:,None]*nodes)))
        logbase=float(logsumexp(np.where(p>0,np.log(p),-np.inf)-np.log(s)-.5*math.log(2*math.pi)-.5*((target-m)/s)**2))
        logl=math.fsum(-float(np.logaddexp(0,-(a+b*target)))for a,b in affine)
    return dict(method='GH%d'%n,log_normalizer=logz,mean=mean,nll=-logbase-logl+logz)


def gaussian_score(target,pi,mu,sigma):
    """Analytic independent base-mixture path with no likelihood factors."""
    if not finite(target)or any(type(v)is not list or len(v)!=5 for v in(pi,mu,sigma))or any(not finite(x)for v in(pi,mu,sigma)for x in v):raise NumericalFailure('mixture')
    if any(x<0 for x in pi)or abs(math.fsum(pi)-1)>1e-6 or any(x<.05 for x in sigma):raise NumericalFailure('mixture')
    p,m,s=(np.asarray(v,dtype=np.float64)for v in(pi,mu,sigma))
    def cdf(x):return float(np.dot(p,ndtr((x-m)/s)))
    def quantile(q):
        lo,hi=float(np.min(m-s)),float(np.max(m+s));step=float(max(s.max(),1))
        for _ in range(100):
            if cdf(lo)<=q<=cdf(hi):return float(brentq(lambda x:cdf(x)-q,lo,hi,xtol=1e-9,rtol=1e-13))
            step*=2;lo-=step;hi+=step
        raise NumericalFailure('quantile_bracket')
    def absolute(delta,sd):
        z=delta/sd;return sd*math.sqrt(2/math.pi)*np.exp(-.5*z*z)+delta*(2*ndtr(z)-1)
    with np.errstate(over='raise',invalid='raise',divide='ignore'):
        logpdf=logsumexp(np.where(p>0,np.log(p),-np.inf)-np.log(s)-.5*math.log(2*math.pi)-.5*((target-m)/s)**2)
        crps=float(np.dot(p,absolute(target-m,s))-.5*np.sum(p[:,None]*p[None,:]*absolute(m[:,None]-m[None,:],np.hypot(s[:,None],s[None,:]))))
    out=dict(mean=float(np.dot(p,m)),median=quantile(.5),nll=float(-logpdf),crps=crps,pit=cdf(target))
    for coverage in(.5,.8,.95):out['coverage_%d'%round(coverage*100)]=float(quantile((1-coverage)/2)<=target<=quantile((1+coverage)/2))
    if any(not math.isfinite(v)for v in out.values()):raise NumericalFailure('score')
    return out

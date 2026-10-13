"""Independent synthetic diagnostics with explicit log-concave tail bounds."""
import math
import numpy as np
from scipy.integrate import cumulative_trapezoid,trapezoid
from scipy.special import logsumexp,ndtr
from scipy.optimize import brentq
from reference import Posterior


def grid_reference(pi,mu,sigma,affine,target,*,resolution=80,radius=12):
    p,m,s=(np.asarray(v,dtype=np.float64)for v in(pi,mu,sigma));a=np.asarray([v[0]for v in affine]);b=np.asarray([v[1]for v in affine]);modes=[];peaks=[];widths=[]
    def likelihood(x):return -float(np.logaddexp(0,-(a+b*x)).sum())
    from scipy.special import expit
    for weight,mean,sd in zip(p,m,s):
        if weight==0:continue
        def derivative(x):return -(x-mean)/(sd*sd)+float(np.dot(b,expit(-(a+b*x))))
        lo=float(mean+sd*sd*np.minimum(b,0).sum());hi=float(mean+sd*sd*np.maximum(b,0).sum())
        mode=lo if lo==hi or derivative(lo)==0 else hi if derivative(hi)==0 else brentq(derivative,lo,hi)
        modes.append(mode);widths.append(sd);peaks.append(math.log(float(weight))-math.log(float(sd))-.5*math.log(2*math.pi)-.5*((mode-mean)/sd)**2+likelihood(mode))
    left=min(x-radius*w for x,w in zip(modes,widths));right=max(x+radius*w for x,w in zip(modes,widths))
    if not left<=target<=right:raise ValueError('target_outside_reference_grid')
    count=math.ceil((right-left)/(min(widths)/resolution))+1
    if count>2_000_000:raise ValueError('grid_cap')
    grid=np.linspace(left,right,count);offset=max(peaks)
    logpdf=logsumexp(np.where(p>0,np.log(p),-np.inf)[None,:]-np.log(s)[None,:]-.5*math.log(2*math.pi)-.5*((grid[:,None]-m[None,:])/s[None,:])**2,axis=1)
    logpdf-=np.logaddexp(0,-(a[None,:]+grid[:,None]*b[None,:])).sum(axis=1)
    density=np.exp(logpdf-offset);mass=float(trapezoid(density,grid));density/=mass
    cdf=cumulative_trapezoid(density,grid,initial=0.)
    logz=offset+math.log(mass);mean=float(trapezoid(grid*density,grid))
    absolute=float(trapezoid(np.abs(grid-target)*density,grid));pair_half=float(trapezoid(cdf*(1-cdf),grid));crps=absolute-pair_half
    pit=float(np.interp(target,grid,cdf));base=logsumexp(np.where(p>0,np.log(p),-np.inf)-np.log(s)-.5*math.log(2*math.pi)-.5*((target-m)/s)**2)
    # Bounds use curvature everywhere, not an assumption that a floating
    # root is the exact mode. At each anchor x0, retain its derivative d.
    # Upper envelope: peak+d*u-u²/(2*sd²). Lower envelope uses
    # K=1/sd²+sum(b²)/4; its Gaussian integral lower-bounds whole Z.
    bounds=[];lower_normalizer=0.
    # Modes/peaks omit zero weights; take original components in order.
    active=[(mean,sd)for weight,mean,sd in zip(p,m,s)if weight>0]
    for peak,anchor,(component_mean,sd)in zip(peaks,modes,active):
        derivative=-(anchor-component_mean)/(sd*sd)+float(np.dot(b,expit(-(a+b*anchor))))
        curvature=1/(sd*sd)+float(np.dot(b,b))/4
        lower_normalizer+=math.exp(float(peak)-offset+derivative*derivative/(2*curvature))*math.sqrt(2*math.pi/curvature)
        shifted=anchor+derivative*sd*sd
        upper_multiplier=math.exp(float(peak)-offset+.5*(derivative*sd)**2)
        bounds.append((shifted,sd,upper_multiplier))
    tail_probability=0.;tail_absolute=0.
    for shifted,sd,multiplier in bounds:
        zleft=(left-shifted)/sd;zright=(right-shifted)/sd
        if not zleft<0<zright:raise ValueError('tail_envelope_geometry')
        tails=float(ndtr(zleft))+float(ndtr(-zright))
        mass_bound=sd*math.sqrt(2*math.pi)*tails
        distance_bound=sd*sd*(math.exp(-zleft*zleft/2)+math.exp(-zright*zright/2))
        tail_probability+=multiplier*mass_bound/lower_normalizer
        tail_absolute+=multiplier*(distance_bound+abs(shifted-target)*mass_bound)/lower_normalizer

    return dict(log_normalizer=float(logz),mean=mean,nll=float(-base-likelihood(target)+logz),pit=pit,absolute_moment=absolute,cdf_product=pair_half,crps=crps,
                log_normalizer_lower_bound=float(offset+math.log(lower_normalizer)),grid_points=count,step=float(grid[1]-grid[0]),tail_probability_bound=float(tail_probability),tail_absolute_bound=float(tail_absolute))


def missed_mode_diagnostic(pi,mu,sigma,affine,target):
    old=Posterior(pi,mu,sigma,affine);individual=[];fixed_absolute=0.
    try:
        for weight,c in zip(old.weights,old.components):
            split=(target-c['mode'])/c['scale']
            def f(t):return abs(c['mode']+c['scale']*t-target)*c['kernel'](t)
            original=old._quad(f,-math.inf,split)+old._quad(f,split,math.inf)
            cuts=sorted(set([-math.inf,-8.,-4.,-1.,0.,1.,4.,8.,split,math.inf]))
            revised=math.fsum(old._quad(f,a,b)for a,b in zip(cuts,cuts[1:]))
            contribution=float(weight)*revised/c['integral'];fixed_absolute+=contribution
            individual.append(dict(mode=c['mode'],curvature_scale=c['scale'],label_split=split,posterior_weight=float(weight),original_absolute=original/c['integral'],mode_split_absolute=revised/c['integral']))
        original_crps=old.crps(target)
        original_abs=sum(v['posterior_weight']*v['original_absolute']for v in individual)
        return dict(log_normalizer=old.log_normalizer,mean=old.mean,nll=-old.log_pdf(target),pit=old.cdf_survival(target)[0],components=individual,
                    original_absolute_moment=original_abs,mode_split_absolute_moment=fixed_absolute,original_cdf_product=original_abs-original_crps,original_crps=original_crps)
    finally:old.components.clear();old._cdf_cache.clear()


def gaussian_absolute_moments(pi,mu,sigma,target):
    """Analytic untransformed mixture identity, independently authored."""
    def A(delta,sd):
        z=delta/sd
        return 2*sd*math.exp(-z*z/2)/math.sqrt(2*math.pi)+delta*(2*float(ndtr(z))-1)
    absolute=math.fsum(w*A(target-m,s)for w,m,s in zip(pi,mu,sigma))
    pair=.5*math.fsum(pi[i]*pi[j]*A(mu[i]-mu[j],math.hypot(sigma[i],sigma[j]))for i in range(5)for j in range(5))
    return dict(absolute_moment=absolute,cdf_product=pair,crps=absolute-pair)

"""Independent scalar Gaussian-mixture scores and fixed descriptive diagnostics."""

import math

SQRT2 = math.sqrt(2)
SQRT2PI = math.sqrt(2*math.pi)


def validate(pi,mu,sigma):
    if (len(pi)!=5 or len(mu)!=5 or len(sigma)!=5
            or any(not math.isfinite(x) for x in [*pi,*mu,*sigma])
            or any(x<0 for x in pi) or abs(sum(pi)-1)>1e-6
            or any(x<.05 for x in sigma)):
        raise ValueError("density_parameters")


def cdf(x,pi,mu,sigma):
    return sum(p*.5*(1+math.erf((x-m)/(s*SQRT2))) for p,m,s in zip(pi,mu,sigma))


def nll(y,pi,mu,sigma):
    validate(pi,mu,sigma)
    terms=[math.log(p)-math.log(s)-math.log(SQRT2PI)-.5*((y-m)/s)**2
           for p,m,s in zip(pi,mu,sigma) if p>0]
    maximum=max(terms)
    return -(maximum+math.log(sum(math.exp(x-maximum) for x in terms)))


def _a(delta,sigma):
    z=delta/sigma
    return 2*sigma*math.exp(-.5*z*z)/SQRT2PI + delta*math.erf(z/SQRT2)


def crps(y,pi,mu,sigma):
    validate(pi,mu,sigma)
    first=sum(p*_a(y-m,s) for p,m,s in zip(pi,mu,sigma))
    second=sum(pi[i]*pi[j]*_a(mu[i]-mu[j],math.hypot(sigma[i],sigma[j]))
               for i in range(5) for j in range(5))
    return first-.5*second


def quantile(q,pi,mu,sigma):
    validate(pi,mu,sigma)
    if not 0<q<1:raise ValueError("quantile")
    if q==.5:
        lo,hi=min(mu),max(mu)
    else:
        lo=min(m-40*s for m,s in zip(mu,sigma));hi=max(m+40*s for m,s in zip(mu,sigma))
    for _ in range(64):
        middle=(lo+hi)/2
        if cdf(middle,pi,mu,sigma)<q:lo=middle
        else:hi=middle
    return (lo+hi)/2


def mean_action(pi,mu):
    return sum(p*m for p,m in zip(pi,mu))

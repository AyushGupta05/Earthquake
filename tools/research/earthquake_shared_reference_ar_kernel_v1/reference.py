"""Independent Decimal Gaussian completion and all-real mixture scores.

No Torch or kernel import. Derive joint support component likelihood in one
closed normal-regression completion; suffix appends retain the same support.
"""
from decimal import Decimal, localcontext
import math
import time
import warnings
import numpy as np
from scipy.special import ndtr, logsumexp
from scipy.optimize import brentq
from scipy.integrate import quad, IntegrationWarning

D=Decimal
LOG2PI=D('1.83787706640934548356065947281123527972279494727556682563430')

def need(v,why):
    if not v:raise ValueError(why)
def decimal(x):
    v=float(x);need(math.isfinite(v),'finite');return D.from_float(v)
class Budget:
    def __init__(self,begin):
        need(type(begin)in(int,float)and math.isfinite(begin)and 0<=begin<=time.monotonic(),'processing_begin');self.begin=begin;self.points=0;self.check()
    def check(self,count=0):
        self.points+=count;need(self.points<=1000000,'evaluation_cap');need(time.monotonic()-self.begin<=10,'deadline')

def array(v,shape):
    need(type(v)is np.ndarray and v.dtype==np.float64 and v.shape==shape and v.flags.c_contiguous and bool(np.isfinite(v).all()),'array')
def input_array(v,shape):
    array(v,shape);need(bool((np.abs(v)<=1e6).all()),'input_representation')

def softplus(v):
    x=decimal(v)
    if x>D(20):return x
    return (D(1)+x.exp()).ln()

def facts(marks,coeff,mref,mode,*,start=0,previous=None):
    input_array(coeff,(3,6));need(type(marks)is np.ndarray and marks.ndim==2 and 1<=len(marks)<=20,'marks');input_array(marks,(len(marks),3));need(mode in('L','S','P') and type(start)is int and 0<=start<20 and start+len(marks)<=20,'mode')
    need(type(mref)in(int,float)and math.isfinite(mref)and abs(mref)<=1e6,'mref')
    if start:input_array(previous,(3,))
    else:need(previous is None,'first_previous')
    need(bool((marks>-12).all()),'allpositive')
    result=[]
    with localcontext()as ctx:
        ctx.prec=60
        for j,row in enumerate(marks,start):
            # Time covariate remains the same fixed float64 math.log1p value.
            t=decimal(math.log1p(.25*j));prev=previous if j==start and start else marks[j-start-1]if j>start else np.zeros(3)
            component=[]
            for c in range(3):
                a,b,d,e,rho,raw=[decimal(v)for v in coeff[c]];beta=b+e*t;intercept=a+d*t+rho*decimal(prev[c])-beta*decimal(mref);scale=D('.05')+softplus(raw)
                need(all(abs(float(v))<=1e6 for v in(intercept,beta,scale)),'factor_representation')
                loading=D(1)-rho if mode=='L'and j>0 else D(1)
                component.append((intercept,beta,scale,loading,decimal(row[c])))
            result.extend(component)
    return tuple(result)

def start(prior,nu,mode,*,processing_begin):
    need(type(prior)in(tuple,list)and len(prior)==3 and mode in('L','S','P'),'prior')
    for v in prior:input_array(v,(5,))
    input_array(nu,(12,3));need(abs(float(logsumexp(prior[0])))<=1e-12 and bool((prior[2]>=.05).all()),'proper_prior')
    # All source inputs copied, fixed empirical joint support used once.
    return dict(prior=tuple(v.copy()for v in prior),nu=nu.copy(),mode=mode,facts=(),cells=0,previous=None,budget=Budget(processing_begin))

def append(state,marks,coeff,mref):
    state['budget'].check();f=facts(marks,coeff,mref,state['mode'],start=state['cells'],previous=state['previous'])
    return dict(state, facts=state['facts']+f,cells=state['cells']+len(marks),previous=marks[-1].copy())

def complete(state):
    state['budget'].check();prior=state['prior'];nu=state['nu']if state['mode']!='P'else np.zeros((1,3));means=[];scales=[];mass=[]
    with localcontext()as ctx:
        ctx.prec=60
        for support in nu:
            for k in range(5):
                mu0=decimal(prior[1][k]);sd0=decimal(prior[2][k]);precision=D(1)/(sd0*sd0);B=mu0*precision;C=mu0*mu0*precision;normal=(sd0*sd0).ln()
                for n,(a,b,sd,loading,y)in enumerate(state['facts']):
                    state['budget'].check(1)
                    residual=y-a-loading*decimal(support[n%3]);inverse=D(1)/(sd*sd);precision+=b*b*inverse;B+=b*residual*inverse;C+=residual*residual*inverse;normal+=LOG2PI+(sd*sd).ln()
                variance=D(1)/precision;center=B/precision;loglik=-D('.5')*(normal+precision.ln()+C-B*B/precision)
                mass.append(float(decimal(prior[0][k])-D(len(nu)).ln()+loglik));means.append(float(center));scales.append(float(variance.sqrt()))
    mass=np.asarray(mass);logz=float(logsumexp(mass));return Mixture(mass-logz,np.asarray(means),np.asarray(scales),logz,state['budget'])

class Mixture:
    def __init__(self,logw,mu,sd,logz,budget):
        for v in(logw,mu,sd):array(v,(len(mu),))
        need(len(mu)in(5,60)and bool((sd>0).all())and math.isfinite(logz),'mixture');self.logw=logw;self.mu=mu;self.sd=sd;self.logz=logz;self.budget=budget;self.budget.check();self.w=np.exp(logw);self.w/=math.fsum(self.w.tolist())
    def cdf(self,x):
        self.budget.check(len(self.mu));need(type(x)in(int,float)and math.isfinite(x),'cdf');return math.fsum(float(w)*float(ndtr((x-m)/s))for w,m,s in zip(self.w,self.mu,self.sd))
    def nll(self,x):
        self.budget.check(len(self.mu));need(type(x)in(int,float)and math.isfinite(x),'target');result=-float(logsumexp(self.logw-np.log(self.sd)-.5*math.log(2*math.pi)-.5*((x-self.mu)/self.sd)**2));need(math.isfinite(result)and math.ulp(result)<=1e-10,'target_precision');return result
    def quantile(self,q):
        need(type(q)is float and 0<q<1,'q');lo=float(np.min(self.mu-self.sd));hi=float(np.max(self.mu+self.sd));span=hi-lo
        for _ in range(1024):
            if self.cdf(lo)<=q<=self.cdf(hi):break
            if self.cdf(lo)>q:lo-=span
            if self.cdf(hi)<q:hi+=span
            span*=2;need(math.isfinite(span)and math.isfinite(lo)and math.isfinite(hi),'bracket')
        else:raise ValueError('bracket')
        return float(brentq(lambda x:self.cdf(x)-q,lo,hi,xtol=1e-11,rtol=1e-14))
    def crps(self,x):
        def absolute(d,sd):return 2*sd*np.exp(-.5*(d/sd)**2)/math.sqrt(2*math.pi)+d*(2*ndtr(d/sd)-1)
        self.budget.check(len(self.mu)+len(self.mu)**2);first=math.fsum((self.w*absolute(x-self.mu,self.sd)).tolist());pairs=self.w[:,None]*self.w[None,:]*absolute(self.mu[:,None]-self.mu[None,:],np.sqrt(self.sd[:,None]**2+self.sd[None,:]**2))
        answer=first-.5*math.fsum(pairs.flatten().tolist());need(math.isfinite(answer)and answer>=0,'crps');return answer
    def integrated_crps(self,x):
        knots=sorted(set([float(x)]+[float(m+k*s)for m,s in zip(self.mu,self.sd)for k in(-8,-4,-1,0,1,4,8)]));terms=[];errors=[]
        with warnings.catch_warnings():
            warnings.simplefilter('error',IntegrationWarning)
            def f(v):p=self.cdf(v);return p*p if v<=x else (1-p)**2
            for lo,hi in zip(knots[:-1],knots[1:]):
                width=hi-lo;value,error=quad(lambda t:f(lo+width*t)*width,0.,1.,epsabs=1e-10,epsrel=1e-10,limit=200);terms.append(value);errors.append(error)
            scale=float(max(self.sd))
            for end,sign in((knots[0],-1.),(knots[-1],1.)):
                value,error=quad(lambda t:f(end+sign*scale*t)*scale,0.,math.inf,epsabs=1e-10,epsrel=1e-10,limit=200);terms.append(value);errors.append(error)
        total=math.fsum(terms);error=math.fsum(errors);need(math.isfinite(total)and error<=1e-6,'integration');return total,error
    def scores(self,x):
        need(type(x)in(int,float)and math.isfinite(x),'target');result=dict(mean=math.fsum((self.w*self.mu).tolist()),nll=self.nll(x),pit=self.cdf(x),median=self.quantile(.5),quantiles={str(q):self.quantile(q)for q in(.025,.1,.25,.5,.75,.9,.975)},crps=self.crps(x));self.budget.check();return result

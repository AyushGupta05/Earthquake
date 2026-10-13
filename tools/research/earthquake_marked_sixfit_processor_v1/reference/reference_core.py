"""Independent pure marked/noise likelihood; no data IO, fit or run authority."""
from dataclasses import dataclass
import math
import time
import statistics
import warnings
import numpy as np
from scipy.special import log_ndtr,erfcx,logsumexp,ndtr
from scipy.optimize import brentq
from scipy.integrate import quad,IntegrationWarning

DELTA=-12.
MAX_ABS=1e6
MAX_LOG_ULP=1e-10


class NumericalFailure(ValueError):
    def __init__(self,reason,evidence=None):
        self.evidence=evidence
        super().__init__(reason)


def need(ok,reason):
    if not ok:raise NumericalFailure(reason)


def number(x):return type(x) in (int,float) and math.isfinite(x) and abs(x)<=MAX_ABS


def vector(values,n):
    need(type(values) in (list,tuple) and len(values)==n and all(number(x) for x in values),'vector')
    return tuple(float(x) for x in values)


def weights(values,n):
    result=vector(values,n);total=math.fsum(result)
    need(all(x>=0 for x in result) and abs(total-1)<=1e-12,'weights')
    return tuple(x/total for x in result)


def noise_support(powers):
    need(type(powers) in (list,tuple) and len(powers)==3,'noise')
    columns=[]
    for values in powers:
        need(type(values) in (list,tuple) and len(values)==12 and all(type(x) in (int,float) and math.isfinite(x) and 0<=x<=1e24 for x in values),'noise')
        v=tuple(float(x) for x in values)
        eta=[math.log(max(1.,statistics.median(v[:j]+v[j+1:]))) for j in range(12)]
        center=math.fsum(eta)/12;columns.append([x-center for x in eta])
    return tuple(tuple(columns[c][j] for c in range(3)) for j in range(12)),(1/12,)*12


@dataclass(frozen=True)
class State:
    pi: tuple
    mu: tuple
    sigma: tuple
    noise: tuple
    noise_weights: tuple
    cells: tuple=()
    arrival_offset_ns: int=0


def start(pi,mu,sigma,noise,noise_weights,*,arrival_offset_ns=0):
    need(type(arrival_offset_ns) is int and 0<=arrival_offset_ns<=750000000,'arrival_offset')
    p=weights(pi,5);m=vector(mu,5);s=vector(sigma,5);need(all(x>=.05 for x in s),'sigma')
    need(type(noise) in (list,tuple) and len(noise)==12,'noise')
    support=tuple(vector(row,3) for row in noise);w=weights(noise_weights,12)
    return State(p,m,s,support,w,(),arrival_offset_ns)


def append(state,cells):
    validate_state(state)
    need(type(state) is State and type(cells) in (list,tuple) and 1<=len(cells) and len(state.cells)+len(cells)<=20,'cells')
    copied=parse_cells(cells,len(state.cells)+1)
    return State(state.pi,state.mu,state.sigma,state.noise,state.noise_weights,state.cells+copied,state.arrival_offset_ns)


def parse_cells(cells,first):
    copied=[]
    for j,cell in enumerate(cells,first):
        need(type(cell) is dict and set(cell)=={'cell','a','b','sigma','value'} and type(cell['cell']) is int and cell['cell']==j,'cell_index')
        a,b,s=(vector(cell[k],3) for k in ('a','b','sigma'));need(all(x>=.05 for x in s),'cell_sigma')
        value=cell['value'];need(type(value) in (list,tuple) and len(value)==3 and all(x is None or number(x) and x>DELTA for x in value),'observation')
        copied.append((j,a,b,s,tuple(None if x is None else float(x) for x in value)))
    return tuple(copied)


def validate_state(state):
    need(type(state) is State and type(state.cells) is tuple and len(state.cells)<=20,'state')
    need(all(type(x) is tuple for x in (state.pi,state.mu,state.sigma,state.noise,state.noise_weights)) and all(type(x) is tuple for x in state.noise),'state_immutable')
    start(state.pi,state.mu,state.sigma,state.noise,state.noise_weights,arrival_offset_ns=state.arrival_offset_ns)
    if state.cells:
        cells=[]
        for value in state.cells:
            need(type(value) is tuple and len(value)==5,'state_cell')
            j,a,b,s,y=value
            need(all(type(x) is tuple for x in (a,b,s,y)),'state_immutable')
            cells.append(dict(cell=j,a=a,b=b,sigma=s,value=y))
        parse_cells(cells,1)


def evidence_precision(value,label):
    # Parity cannot detect a common offset that erased small density terms.
    if not math.isfinite(value) or math.ulp(value)>MAX_LOG_ULP:
        raise NumericalFailure('evidence_precision',{'label':label,'value':value,'maximum_log_ulp':MAX_LOG_ULP})
    return value


def gaussian_update(mean,variance,logmass,a,b,sigma,y):
    innovation=y-a-b*mean;total=sigma*sigma+b*b*variance
    need(math.isfinite(total) and total>0,'gaussian_representation')
    logmass+=-.5*(math.log(2*math.pi*total)+innovation*innovation/total)
    # Weighted completion avoids subtracting nearly equal prior and innovation.
    first=mean*sigma*sigma;second=variance*b*(y-a)
    numerator=math.fsum((first,second));newmean=numerator/total
    newvariance=variance*(sigma*sigma/total)
    # Reject means unresolved at the conditional scale instead of shared false parity.
    roundoff=(4*math.ulp(first)+6*math.ulp(second)+math.ulp(numerator))/total+3*math.ulp(newmean)
    if not math.isfinite(roundoff) or roundoff>1e-10*math.sqrt(newvariance):
        raise NumericalFailure('gaussian_mean_precision',{'roundoff_bound':roundoff,'conditional_sd':math.sqrt(newvariance)})
    mean,variance=newmean,newvariance
    need(all(math.isfinite(x) for x in (mean,variance,logmass)) and variance>0,'gaussian_representation')
    evidence_precision(logmass,'positive_logmass')
    return mean,variance,logmass


class Budget:
    def __init__(self,begin,seconds):
        need(type(begin) in (int,float) and math.isfinite(begin) and 0<=begin<=time.monotonic() and number(seconds) and 0<seconds<=10,'budget')
        self.begin=begin;self.seconds=seconds;self.points=0;self.cdf_terms=0
    def check(self,points=0,cdf_terms=0):
        self.points+=points;self.cdf_terms+=cdf_terms
        if self.points>1000000:raise NumericalFailure('evaluation_cap',self.evidence())
        if time.monotonic()-self.begin>self.seconds:raise NumericalFailure('deadline',self.evidence())
    def evidence(self):return {'density_points':self.points,'cdf_scalar_terms':self.cdf_terms,'seconds':time.monotonic()-self.begin}


class Component:
    def __init__(self,mean,variance,logmass,censors,noise_index,budget):
        self.mean=mean;self.sd=math.sqrt(variance);self.mass=evidence_precision(logmass,'component_logmass');self.noise_index=noise_index;self.budget=budget
        self.a=np.asarray([(DELTA-a-b*mean)/sigma for a,b,sigma in censors],dtype=np.float64)
        self.b=np.asarray([-b*self.sd/sigma for a,b,sigma in censors],dtype=np.float64)
        need(np.isfinite(self.a).all() and np.isfinite(self.b).all(),'censor_representation')
        self.constant=not np.any(self.b)
        if self.constant:
            self.logz=float(np.sum(log_ndtr(self.a)));self.posterior_mean=mean;self.mode=0.;self.width=1.;self.integral=math.sqrt(2*math.pi);self.peak=self.logz-.5*math.log(2*math.pi)
            evidence_precision(self.logz,'constant_censor_logmass');evidence_precision(self.peak,'constant_censor_peak')
            budget.check(1,len(censors));return
        def derivative(t):
            z=self.a+self.b*t;budget.check(1,len(self.a))
            ratio=np.empty_like(z);negative=z<0
            ratio[negative]=math.sqrt(2/math.pi)/erfcx(-z[negative]/math.sqrt(2))
            ratio[~negative]=np.exp(-.5*z[~negative]*z[~negative]-.5*math.log(2*math.pi)-log_ndtr(z[~negative]))
            value=-t+math.fsum(float(x) for x in self.b*ratio)
            need(math.isfinite(value),'mode_derivative');return value
        lo,hi=-1.,1.
        for _ in range(64):
            dl,dh=derivative(lo),derivative(hi)
            if dl>=0 and dh<=0:break
            if dl<0:lo*=2
            if dh>0:hi*=2
        else:raise NumericalFailure('mode_bracket')
        self.mode=brentq(derivative,lo,hi,xtol=1e-11,rtol=1e-13)
        # A finite difference of the analytic derivative only scales integration;
        # it does not alter the original probability density or integration domain.
        step=1e-4;curvature=-(derivative(self.mode+step)-derivative(self.mode-step))/(2*step)
        need(math.isfinite(curvature) and curvature>0,'mode_curvature');self.width=1/math.sqrt(curvature)
        self.peak=evidence_precision(float(self.logkernel(np.asarray([self.mode]))[0]),'censor_peak')
        self.integral=self.integrate(-math.inf,math.inf,0)
        need(self.integral>0,'adaptive_mass');self.logz=self.peak+math.log(self.width)+math.log(self.integral)
        evidence_precision(self.logz,'censor_logmass')
        centered=self.integrate(-math.inf,math.inf,1)/self.integral
        self.posterior_mean=self.mean+self.sd*(self.mode+self.width*centered)
    def logkernel(self,t):
        value=np.asarray(t,dtype=np.float64);self.budget.check(value.size,value.size*len(self.a))
        with np.errstate(over='raise',invalid='raise'):
            out=-.5*value*value-.5*math.log(2*math.pi)+np.sum(log_ndtr(self.a+value[...,None]*self.b),axis=-1)
        need(np.isfinite(out).all(),'kernel');return out
    def integrate(self,lo,hi,moment):
        def kernel(u):
            logvalue=float(self.logkernel(np.asarray([self.mode+self.width*u]))[0])-self.peak
            need(logvalue<=1e-7,'mode_peak')
            return math.exp(logvalue)*(u if moment else 1.)
        with warnings.catch_warnings():
            warnings.simplefilter('error',IntegrationWarning)
            answer,error=quad(kernel,lo,hi,epsabs=1e-10,epsrel=1e-10,limit=200)
        need(math.isfinite(answer) and math.isfinite(error) and error<=1e-7*(1+abs(answer)),'adaptive_error');return answer
    def gh(self,order):
        if self.constant:return self.logz,self.mean
        x,w=np.polynomial.hermite.hermgauss(order);t=math.sqrt(2)*x
        self.budget.check(len(t),len(t)*len(self.a));ll=np.sum(log_ndtr(self.a+t[:,None]*self.b),axis=1)
        mass=np.log(w)-.5*math.log(math.pi)+ll;z=float(logsumexp(mass));mean=self.mean+self.sd*float(np.sum(np.exp(mass-z)*t))
        need(math.isfinite(z) and math.isfinite(mean),'GH_nonfinite');return z,mean
    def logdensity_unnormalized(self,m):
        t=(m-self.mean)/self.sd
        return self.mass+float(self.logkernel(np.asarray([t]))[0])-math.log(self.sd)
    def cdf(self,m):
        if self.constant:return float(ndtr((m-self.mean)/self.sd))
        end=((m-self.mean)/self.sd-self.mode)/self.width
        probability=self.integrate(-math.inf,end,0)/self.integral if end<=0 else 1-self.integrate(end,math.inf,0)/self.integral
        need(0<=probability<=1,'cdf_probability');return probability


class Posterior:
    def __init__(self,state,target,*,processing_begin,budget_seconds=10):
        self.components=[];self.current_component=None;self.integrals={};self.errors={}
        need(type(state) is State and len(state.cells)<=20 and type(target) in (int,float) and math.isfinite(target),'state')
        validate_state(state)
        self.state=state;self.target=target;self.budget=Budget(processing_begin,budget_seconds)
        for ell,(noise,w) in enumerate(zip(state.noise,state.noise_weights)):
            if w==0:continue
            for weight,mean,sd in zip(state.pi,state.mu,state.sigma):
                if weight==0:continue
                variance=sd*sd;mass=math.log(w)+math.log(weight);censors=[]
                for _,a,b,s,values in state.cells:
                    for c,y in enumerate(values):
                        self.budget.check()
                        if y is None:censors.append((a[c]+noise[c],b[c],s[c]))
                        else:mean,variance,mass=gaussian_update(mean,variance,mass,a[c]+noise[c],b[c],s[c],y)
                self.current_component=Component.__new__(Component)
                self.current_component.__init__(mean,variance,mass,censors,ell,self.budget)
                self.components.append(self.current_component);self.current_component=None
        need(bool(self.components),'components')
        self.integrals={}
        for method in ('adaptive','gh64','gh128'):
            logmasses=[];means=[]
            for c in self.components:
                z,m=(c.logz,c.posterior_mean) if method=='adaptive' else c.gh(int(method[2:]))
                logmasses.append(evidence_precision(c.mass+z,'integrated_logmass'));means.append(m)
            logz=float(logsumexp(logmasses));prob=np.exp(np.asarray(logmasses)-logz)
            mean=math.fsum(float(p*m) for p,m in zip(prob,means))
            logtarget=evidence_precision(float(logsumexp([c.logdensity_unnormalized(target) for c in self.components])),'target_logmass')
            nll=logz-logtarget
            self.integrals[method]={'log_normalizer':logz,'mean':mean,'nll':nll}
        self.errors={k:max(self.integrals[v][k] for v in self.integrals)-min(self.integrals[v][k] for v in self.integrals) for k in ('log_normalizer','mean','nll')}
        if not all(math.isfinite(x) and x<=1e-4 for x in self.errors.values()):raise NumericalFailure('quadrature_parity',{'errors':self.errors,'integrals':self.integrals,'work':self.budget.evidence()})
        self.logz=self.integrals['adaptive']['log_normalizer'];self.probabilities=np.exp(np.asarray([c.mass+c.logz for c in self.components])-self.logz)
        denominator=math.fsum(float(p) for p in self.probabilities)
        self.noise_probabilities=[math.fsum(float(p) for c,p in zip(self.components,self.probabilities) if c.noise_index==ell)/denominator for ell in range(12)]
        self.budget.check()
    def cdf(self,m):
        if m==-math.inf:return 0.
        if m==math.inf:return 1.
        need(type(m) in (int,float) and math.isfinite(m),'cdf_input');self.budget.check()
        result=math.fsum(float(p)*c.cdf(m) for p,c in zip(self.probabilities,self.components))/math.fsum(float(p) for p in self.probabilities);need(0<=result<=1,'cdf_probability');return result
    def density(self,m):
        need(type(m) in (int,float) and math.isfinite(m),'density_input');return math.exp(float(logsumexp([c.logdensity_unnormalized(m) for c in self.components]))-self.logz)
    def summary(self):
        return {'accepted':True,'cells':len(self.state.cells),'components':len(self.components),'integrals':self.integrals,'errors':self.errors,'noise_probabilities':self.noise_probabilities,'pit':self.cdf(self.target),'work':self.budget.evidence(),'censored_CRPS_verified':False}


def partial_evidence(posterior,failure):
    result={'failure':failure,'integrals':getattr(posterior,'integrals',{}),'errors':getattr(posterior,'errors',{}),'noise_probabilities':getattr(posterior,'noise_probabilities',None)}
    budget=getattr(posterior,'budget',None);result['work']=budget.evidence() if budget is not None else None
    def component_record(component):
        record={key:getattr(component,key) for key in ('mean','sd','mass','noise_index','mode','width','peak','integral','logz','posterior_mean') if hasattr(component,key)}
        for key in ('a','b'):
            if hasattr(component,key):record[key]=getattr(component,key).tolist()
        return record
    result['completed_components']=[component_record(c) for c in getattr(posterior,'components',[])]
    current=getattr(posterior,'current_component',None);result['current_component']=component_record(current) if current is not None else None
    return result


def infer(state,target,*,processing_begin,budget_seconds=10):
    posterior=None
    try:
        # Keep allocation visible even if initialization stops part-way through.
        posterior=Posterior.__new__(Posterior)
        posterior.__init__(state,target,processing_begin=processing_begin,budget_seconds=budget_seconds)
        return posterior.summary()
    except Exception as error:
        evidence=getattr(error,'evidence',None)
        if posterior is not None:evidence=partial_evidence(posterior,evidence)
        return {'accepted':False,'reason':str(error)[:128],'exception_type':type(error).__name__,'evidence':evidence,'state':state,'target':target}


def forecast(state,target,horizon,*,processing_begin,budget_seconds=10):
    # Only this wrapper claims a deadline forecast; lower-level infer is mathematical.
    try:
        validate_state(state)
        need(type(horizon) is int and horizon in (1,3,5),'horizon')
        count=(horizon*1000000000-state.arrival_offset_ns)//250000000
        need(1<=count<=20 and len(state.cells)==count,'deadline_cells')
    except Exception as error:
        return {'accepted':False,'reason':str(error)[:128],'exception_type':type(error).__name__,'evidence':getattr(error,'evidence',None),'state':state,'target':target}
    return infer(state,target,processing_begin=processing_begin,budget_seconds=budget_seconds)


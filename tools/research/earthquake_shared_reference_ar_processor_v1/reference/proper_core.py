"""Independent Gaussian completion and all-real mixture scoring; no producer imports."""
import math
import time
import warnings
import numpy as np
from scipy.special import logsumexp,ndtr,expit
from scipy.integrate import quad,IntegrationWarning
from scipy.optimize import brentq

EPS=np.finfo(np.float64).eps
Q=(.025,.1,.25,.5,.75,.9,.975)

class AuditFailure(ValueError):pass

def need(v,reason):
 if not v:raise AuditFailure(reason)

def array(v,shape=None):
 need(type(v)is np.ndarray and v.dtype==np.float64 and v.flags.c_contiguous and np.isfinite(v).all(),'float64_array')
 if shape is not None:need(v.shape==shape,'array_shape')
 return v

class Budget:
 def __init__(self,begin=None):self.begin=time.monotonic()if begin is None else begin;self.points=0;self.terms=0;self.tick()
 def tick(self):
  now=time.monotonic();need(type(self.begin)in(int,float)and math.isfinite(self.begin)and 0<=self.begin<=now and now-self.begin<=10,'record_deadline')
 def charge(self,points,terms):
  need(type(points)is int and type(terms)is int and points>=0 and terms>=0,'work');need(self.points+points<=1_000_000,'record_work_cap');self.points+=points;self.terms+=terms;self.tick()

def softplus(x,error=None):
 x=np.asarray(x,dtype=np.float64);error=np.zeros_like(x)if error is None else np.asarray(error,dtype=np.float64);need(np.isfinite(x).all()and np.isfinite(error).all()and(error>=0).all(),'softplus_input');need(not np.any((x-error<=20)&(x+error>20)),'softplus_branch_ambiguous');out=np.empty_like(x);linear=x>20;out[linear]=x[linear];other=x[~linear];out[~linear]=np.maximum(other,0)+np.log1p(np.exp(-np.abs(other)));return out

def bound_ok(value,error):
 need(np.isfinite(value).all()and np.isfinite(error).all()and(error>=0).all()and np.all(error<=1e-10*(1+np.abs(value))),'forward_bound_unresolved')

def compare(value,expected,error):
 a=np.asarray(value);b=np.asarray(expected);need(a.dtype==np.float64 and b.dtype==np.float64 and a.shape==b.shape and np.isfinite(a).all()and np.isfinite(b).all(),'forward_dtype');bound_ok(b,error);need(np.all(np.abs(a-b)<=error),'checkpoint_forward_disagreement')

def linear(x,e,w,b):
 n=x.size;gamma=(n+2)*EPS/(1-(n+2)*EPS);y=w@x+b;bound=np.abs(w)@e+2*gamma*(np.abs(w)@np.abs(x)+np.abs(b));bound_ok(y,bound);return y,bound

def silu(x,e):
 y=x*expit(x);bound=1.1*e+16*EPS*(1+np.abs(y));bound_ok(y,bound);return y,bound

def prior_forward(context,parameters,K,context_error=None):
 array(context,(K,));need(bool((np.abs(context)<=1e6).all()),'prior_context_domain');e=np.zeros(K)if context_error is None else array(context_error,(K,));bound_ok(context,e)
 if K:
  w=array(parameters['prior.first.weight'],(16,K));b=array(parameters['prior.first.bias'],(16,));x,e=linear(context,e,w,b)
 else:x=array(parameters['prior.first_bias'],(16,)).copy();e=np.zeros(16)
 x,e=silu(x,e);x,e=linear(x,e,array(parameters['prior.second.weight'],(16,16)),array(parameters['prior.second.bias'],(16,)));x,e=silu(x,e);out,e=linear(x,e,array(parameters['prior.head.weight'],(14,16)),array(parameters['prior.head.bias'],(14,)));logits=np.r_[out[:4],0.];el=np.r_[e[:4],0.];logz=float(logsumexp(logits));logw=logits-logz;ew=el+np.max(el)+16*EPS*(1+np.abs(logw));means=out[4:9];em=e[4:9];scales=.05+softplus(out[9:14],e[9:14]);es=e[9:14]+16*EPS*(1+np.abs(scales))
 for value,error in((logw,ew),(means,em),(scales,es)):bound_ok(value,error);need(bool((np.abs(value)<=1e6).all()),'prior_output_domain')
 return (logw,means,scales),(ew,em,es)

def summaries(marks,nu):
 array(marks);array(nu,(12,3));need(marks.ndim==2 and marks.shape[1]==3 and 1<=len(marks)<=20 and(marks>-12).all(),'positive_marks');J=len(marks);u=.25*np.arange(J,dtype=np.float64);center=float(u.mean());den=math.fsum(float((v-center)**2)for v in u);result=[]
 for c in range(3):
  y=marks[:,c];slope=0. if J==1 else math.fsum(float((t-center)*(v-float(y.mean())))for t,v in zip(u,y))/den;result.extend([float(y[-1]),float(y.mean()),float(y.max()),slope,0.])
 result.extend([math.log1p(.25*J),float(J)]);result.extend(math.sqrt(math.fsum(float(v*v)for v in nu[:,c])/12)for c in range(3));return np.asarray(result,dtype=np.float64)

def factors(marks,coeff,mref,evidence=None):
 array(marks);array(coeff,(3,6));need(bool((np.abs(coeff)<=1e6).all()),'coefficient_domain');need(type(mref)in(int,float)and math.isfinite(mref),'mref');need(evidence is None or type(evidence)is list,'factor_evidence');facts=[]if evidence is None else evidence;sigma=.05+softplus(coeff[:,5])
 for j,y in enumerate(marks):
  # Frozen operator API admits statistical tensors/factors only within abs<=1e6.
  t=math.log1p(.25*j);beta=coeff[:,1]+coeff[:,3]*t;prev=np.zeros(3)if j==0 else marks[j-1];a=coeff[:,0]+coeff[:,2]*t+coeff[:,4]*prev-beta*mref;facts.append([a.copy(),beta.copy(),sigma.copy(),y.copy()]);need(np.isfinite(a).all()and np.isfinite(beta).all()and np.isfinite(sigma).all()and np.max(np.abs(a))<=1e6 and np.max(np.abs(beta))<=1e6 and np.max(np.abs(sigma))<=1e6,'affine_domain')
 return facts

class Mixture:
 def __init__(self,logw,means,scales,logz=0.,budget=None):
  self.budget=Budget()if budget is None else budget;self.logw=np.asarray(logw,dtype=np.float64);self.mu=np.asarray(means,dtype=np.float64);self.sd=np.asarray(scales,dtype=np.float64);n=len(self.mu);need(n in(5,60)and self.logw.shape==self.mu.shape==self.sd.shape and np.isfinite(self.logw).all()and np.isfinite(self.mu).all()and np.isfinite(self.sd).all()and(self.sd>0).all(),'mixture');need(abs(float(logsumexp(self.logw)))<=1e-12 and type(logz)in(int,float)and math.isfinite(logz),'normalization');self.pi=np.exp(self.logw);self.logz=float(logz);self.noise=None
 def cdf(self,x,survival=False):
  self.budget.charge(1,len(self.mu));z=(x-self.mu)/self.sd;return float(np.dot(self.pi,ndtr(-z if survival else z)))
 def nll(self,y):
  self.budget.charge(1,len(self.mu));z=(y-self.mu)/self.sd;kernels=self.logw-.5*z*z-np.log(self.sd)-.5*math.log(2*math.pi);value=-float(logsumexp(kernels));ez=4*EPS*(abs(y)+np.abs(self.mu))/self.sd+4*EPS*np.abs(z);ek=np.abs(z)*ez+.5*ez*ez+32*EPS*(1+np.abs(self.logw)+z*z+np.abs(np.log(self.sd)));lower=float(logsumexp(kernels-ek));upper=float(logsumexp(kernels+ek));error=max(abs(-value-lower),abs(upper+value))+32*EPS*(1+abs(value))
  if not(math.isfinite(value)and math.isfinite(error)and math.ulp(value)<=1e-10 and error<=1e-10):
   import struct
   failure=AuditFailure('nll_representation');failure.numeric_evidence=dict(candidate_float64_hex=struct.pack('<d',value).hex(),bound_float64_hex=struct.pack('<d',error).hex(),ulp_float64_hex=struct.pack('<d',math.ulp(value)).hex());raise failure
  return value
 def mean(self):self.budget.charge(0,len(self.mu));return float(math.fsum(float(w*m)for w,m in zip(self.pi,self.mu)))
 def quantile(self,q):
  need(type(q)is float and 0<q<1,'quantile');width=max(1.,float(self.sd.max()));lo=float(self.mu.min())-8*width;hi=float(self.mu.max())+8*width
  while self.cdf(lo)>q:width*=2;lo-=width;need(math.isfinite(lo),'quantile_bracket')
  while self.cdf(hi)<q:width*=2;hi+=width;need(math.isfinite(hi),'quantile_bracket')
  root=float(brentq(lambda x:self.cdf(x)-q,lo,hi,xtol=1e-12,rtol=8*EPS,maxiter=200));need(abs(self.cdf(root)-q)<=1e-6,'quantile_probability');return root
 def crps(self,y):
  def moment(d,s):
   z=d/s;return s*math.sqrt(2/math.pi)*np.exp(-.5*z*z)+d*(2*ndtr(z)-1)
  self.budget.charge(0,len(self.mu)**2+len(self.mu));first=math.fsum(float(w*v)for w,v in zip(self.pi,moment(y-self.mu,self.sd)));d=self.mu[:,None]-self.mu[None,:];s=np.sqrt(self.sd[:,None]**2+self.sd[None,:]**2);second=math.fsum(float(v)for v in(self.pi[:,None]*self.pi[None,:]*moment(d,s)).ravel());value=first-.5*second;need(math.isfinite(value)and value>=-1e-10,'crps');return value
 def integral_crps(self,y):
  # Every component, including distant low-mass modes, supplies finite split points.
  knots=sorted({float(y)}|{float(m+t*s)for m,s in zip(self.mu,self.sd)for t in(-8.,-2.,0.,2.,8.)});bounds=[-math.inf]+knots+[math.inf];total=[]
  for lo,hi in zip(bounds,bounds[1:]):
   if lo==hi:continue
   survival=lo>=y
   def f(x):v=self.cdf(x,survival);return v*v
   with warnings.catch_warnings():
    warnings.simplefilter('error',IntegrationWarning);value,error=quad(f,lo,hi,epsabs=1e-9/max(1,len(bounds)),epsrel=1e-9,limit=150)
   need(math.isfinite(value)and math.isfinite(error)and error<=1e-7*(1+abs(value)),'cdf_integral');total.append(value);self.budget.tick()
  return math.fsum(total)
 def scores(self,y,crosscheck=True,evidence=None):
  need(type(y)in(int,float)and math.isfinite(y),'target');need(evidence is None or type(evidence)is dict,'proper_evidence');value={}if evidence is None else evidence
  value['mean']=self.mean();value['median']=self.quantile(.5)
  try:value['nll']=self.nll(y)
  except AuditFailure as error:
   if hasattr(error,'numeric_evidence'):value['rejected_nll']=error.numeric_evidence
   raise
  value['crps']=self.crps(y);value['pit']=self.cdf(y);q={};value['quantiles']=q
  for p in Q:q[str(p)]=self.quantile(p)
  for level in(50,80,95):tail={50:.25,80:.1,95:.025}[level];lo=q[str(tail)];hi=q[str({50:.75,80:.9,95:.975}[level])];value['coverage_'+str(level)]=bool(lo<=y<=hi)
  if crosscheck:need(abs(value['crps']-self.integral_crps(y))<=1e-6,'independent_crps_disagreement')
  self.budget.tick();return value

def complete(prior,facts,nu,arm,budget):
 logw,mu,sd=(array(v,(5,))for v in prior);array(nu,(12,3));need(abs(float(logsumexp(logw)))<=1e-12 and(sd>=.05).all()and arm in('S','P'),'prior');need(len(facts)<=20,'factor_count');support=nu if arm=='S'else np.zeros((1,3));outw=[];outmu=[];outsd=[];weights=[]
 for ell,noise in enumerate(support):
  for k in range(5):
   budget.charge(0,6*len(facts)+1);v=[];b=[];s=[];ev=[]
   for f in facts:
    need(type(f)is list and len(f)==4,'factor');a,bb,ss,y=(array(x,(3,))for x in f);need((ss>=.05).all()and(y>-12).all(),'positive_factor');v.extend(float(yy-aa-nn-bb1*mu[k])for yy,aa,nn,bb1 in zip(y,a,noise,bb));ev.extend(8*EPS*(abs(float(yy))+abs(float(aa))+abs(float(nn))+abs(float(bb1*mu[k])))for yy,aa,nn,bb1 in zip(y,a,noise,bb));b.extend(float(x)for x in bb);s.extend(float(x)for x in ss)
   precision=math.fsum((bb/ss)**2 for bb,ss in zip(b,s));A=1+sd[k]**2*precision;delta=sd[k]**2*math.fsum(bb*vv/(ss*ss)for bb,vv,ss in zip(b,v,s))/A;mean=float(mu[k]+delta);sigma=float(sd[k]/math.sqrt(A));mean_error=completion_mean_error(float(mu[k]),float(sd[k]),v,ev,b,s,precision,A,delta,mean,sigma);residual=math.fsum(((vv-bb*delta)/ss)**2 for vv,bb,ss in zip(v,b,s));mass=float(logw[k]-math.log(len(support))-.5*(residual+(delta/sd[k])**2)-math.fsum(math.log(ss)for ss in s)-len(s)*.5*math.log(2*math.pi)-.5*math.log(A));need(all(math.isfinite(x)for x in(mean,sigma,mass))and math.ulp(mass)<=1e-10 and math.ulp(mean)<=1e-10*sigma and mean_error<=1e-10*sigma,'completion_representation');outw.append(mass);outmu.append(mean);outsd.append(sigma)
 logz=float(logsumexp(outw));need(math.ulp(logz)<=1e-10,'evidence_representation');mix=Mixture(np.asarray(outw)-logz,np.asarray(outmu),np.asarray(outsd),logz,budget)
 if arm=='S':mix.noise=np.exp(mix.logw).reshape(12,5).sum(1)
 return mix


def summary_error(marks,nu):
 # Operational float64/libm bounds, not a formal transcendental certificate.
 J=len(marks);g=(J+4)*EPS/(1-(J+4)*EPS);u=.25*np.arange(J);uc=float(u.mean());den=math.fsum(float((t-uc)**2)for t in u);error=[]
 for column in marks.T:
  mean=float(column.mean());em=2*g*float(np.mean(np.abs(column)))+16*EPS*(1+abs(mean));products=[float((t-uc)*(v-mean))for t,v in zip(u,column)];slope_error=0. if J==1 else (math.fsum(abs(float(t-uc))*(em+2*EPS*(abs(float(v))+abs(mean)))for t,v in zip(u,column))+2*g*math.fsum(abs(v)for v in products))/den+2*EPS*abs(math.fsum(products)/den)
  error.extend([0.,em,0.,slope_error,0.])
 error.extend([16*EPS*(1+abs(math.log1p(.25*J))),0.]);error.extend(64*EPS*(1+float(np.max(np.abs(nu[:,i]))))for i in range(3));return np.asarray(error,dtype=np.float64)

def standardize_bound(raw,error,mean,std):
 value=np.divide(raw-mean,std,out=np.zeros_like(raw),where=std>0);bound=np.divide(error+8*EPS*(np.abs(raw)+np.abs(mean)),std,out=np.zeros_like(raw),where=std>0)+8*EPS*np.abs(value);bound_ok(value,bound);return value,bound

def direct_shift(raw,error,scaler,theta):
 z,ez=standardize_bound(raw,error,scaler['mean'],scaler['std']);need(bool((np.abs(z)<=1e6).all())and bool((np.abs(theta)<=1e6).all()),'direct_input_domain');active=scaler['active'];v=z[active];e=ez[active];n=len(v);g=(n+2)*EPS/(1-(n+2)*EPS);shift=float(np.dot(v,theta));bound=float(np.dot(np.abs(theta),e)+2*g*np.dot(np.abs(v),np.abs(theta)));bound_ok(np.asarray(shift),np.asarray(bound));return shift,bound


def completion_mean_error(mu,sd,v,ev,b,s,precision,A,delta,mean,sigma):
 # Exact float64 inputs; explicit roundoff propagation through positive precision,
 # signed information accumulation, product/division and final mean addition.
 n=len(v);gamma=(2*n+8)*EPS/(1-(2*n+8)*EPS);ep=gamma*precision;s2=sd*sd;es2=EPS*abs(s2);ea=s2*ep+precision*es2+ep*es2+4*EPS*(1+abs(s2*precision));terms=[bb*vv/(ss*ss)for bb,vv,ss in zip(b,v,s)];et=math.fsum(abs(bb)*ee/(ss*ss)+8*EPS*abs(term)for bb,ee,ss,term in zip(b,ev,s,terms))+2*EPS*math.fsum(abs(t)for t in terms);information=math.fsum(terms);en=s2*et+abs(information)*es2+es2*et+2*EPS*abs(s2*information);need(math.isfinite(ea)and math.isfinite(en)and A>ea,'completion_precision_unresolved');ed=(en+abs(delta)*ea)/(A-ea)+2*EPS*abs(delta);error=ed+2*EPS*(abs(mu)+abs(delta));need(math.isfinite(error)and error>=0,'completion_roundoff');return error

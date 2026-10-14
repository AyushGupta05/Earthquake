"""Invented call-contract fixtures; no NumPy/SciPy/Torch imports."""
from contextlib import contextmanager
import hashlib,json,math,sys,types,unittest
from unittest.mock import patch
import smoke

def ns(**v):return types.SimpleNamespace(**v)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def pin(x):return dict(bytes=len(x),sha256=hashlib.sha256(x).hexdigest())
IO=ns(pin=pin,canonical=canonical,json_read=json.loads)

class Value:
 def __init__(self,v=1.,shape=(),backward=None):self.value=v;self.shape=shape;self.grad=None;self.dtype='float64';self.device=ns(type='cpu');self._backward=backward
 def detach(self):return self
 def clone(self):return Value(self.value,self.shape)
 def abs(self):return Value(abs(self.value),self.shape)
 def sum(self):return Value(self.value)
 def max(self):return Value(self.value)
 def mean(self):return self
 def all(self):return bool(self.value)
 def any(self):return bool(self.value)
 def numel(self):return math.prod(self.shape) if self.shape else 1
 def __float__(self):return float(self.value)
 def __ne__(self,o):return Value(self.value!=o)
 def __le__(self,o):return Value(self.value<=o)
 def __sub__(self,o):return Value(self.value-o.value,self.shape)
 def __iter__(self):return iter([Value(self.value,self.shape[1:]) for _ in range(self.shape[0])])
 def backward(self):self._backward()

class ProducerFixture:
 def __init__(self):
  self.parameters=[];self.calls=[];self.steps=0;self.bad_grad=False;self.bad_coefficient_entry=False;self.lazy_failure=False;self.step_failure=0;owner=self
  class Prior:
   def __init__(self,k):owner.calls.append(('Prior',k));self.params=[Value(.1,(2,)),Value(.2,(5,))];owner.parameters.extend(self.params)
   def initialize(self,a,b):owner.calls.append(('initialize',a,b))
   def parameters(self):return self.params
   def __call__(self,x):return tuple(Value(v,(5,)) for v in (0.,3.5,.7))
  class Adam:
   def __init__(self,parameters,lr):
    owner.calls.append(('Adam',lr,len(parameters)))
    if owner.lazy_failure:raise ModuleNotFoundError('invented lazy import')
    self.parameters=parameters;self.state={p:dict(step=0) for p in parameters}
   def zero_grad(self,set_to_none):
    owner.calls.append(('zero',set_to_none))
    for p in self.parameters:p.grad=None
   def step(self):
    owner.steps+=1
    if owner.steps==owner.step_failure:raise RuntimeError('invented Adam failure')
    for p in self.parameters:p.value-=.001;self.state[p]['step']+=1
  def tensor(data,dtype):
   shape=[];v=data
   while isinstance(v,list):shape.append(len(v));v=v[0] if v else 0
   return Value(float(v),tuple(shape))
  def parameter(v):owner.parameters.append(v);return v
  torch=ns(manual_seed=lambda seed:self.calls.append(('seed',seed)),float64='float64',tensor=tensor,nn=ns(Parameter=parameter),optim=ns(Adam=Adam),stack=lambda xs:Value(xs[0].value,(len(xs),)+xs[0].shape),logsumexp=lambda v,dim:Value(0.,(3,)),isfinite=lambda v:Value(math.isfinite(v.value)))
  def backward():
   for p in self.parameters:p.grad=Value(0. if self.bad_grad else 1.,p.shape)
   if self.bad_coefficient_entry:self.parameters[-1].grad.all=lambda:False
  def marked_nll(prior,marks,coeff,nu,targets,arm,mref,horizons,offsets,*,processing_begin):
   self.calls.append(('kernel',arm,horizons,offsets,tuple(m.shape for m in marks),coeff.shape,nu.shape))
   return dict(mu=Value(3.5,(3,60)),logw=Value(-math.log(60),(3,60)),nll=Value(1.,(3,),backward),density_points=(780,2220,3660))
  self.groups=dict(gaussian=dict(gaussian_operator=ns(torch=torch,Prior=Prior)),kernel=dict(kernel=ns(torch=torch,marked_nll=marked_nll)))

class Array:
 def __init__(self,data):self.data=data;self.shape=(len(data),len(data[0])) if data and isinstance(data[0],list) else (len(data),)
 def __iter__(self):return iter(self.data)
 def __len__(self):return len(self.data)
 def __ge__(self,v):return ns(all=lambda:all(x>=v for x in self.data))

class IndependentFixture:
 def __init__(self):
  self.calls=[];self.fail_horizon=None;self.bad_score=False;owner=self
  class Budget:
   def __init__(self,begin):self.points=0;self.terms=0
   def tick(self):pass
  def build_reference(prior,marks,coeff,nu,mref,h,offset,*,budget):self.calls.append(('build',h,marks.shape,coeff.shape,nu.shape,offset));return dict(h=h,budget=budget)
  class Mix:
   def __init__(self,ref):self.mu=[0.]*60;self.noise=Array([1/12]*12);self.logz=-1.;self.ref=ref
   def scores(self,target,crosscheck,evidence):
    owner.calls.append(('scores',self.ref['h'],crosscheck));evidence['mean']=.5
    if self.ref['h']==owner.fail_horizon:raise ValueError('invented late proper deadline')
    evidence.update(mean=.5,median=.5,nll=1.,crps=math.nan if owner.bad_score else .2,pit=.5,quantiles={str(q):q for q in smoke.Q},coverage_50=True,coverage_80=True,coverage_95=True)
    self.ref['budget'].points=100;self.ref['budget'].terms=6000;return evidence
   def cdf(self,v):return v
  core=ns(np=ns(asarray=lambda data,dtype:Array(data),float64='float64'),Budget=Budget,build_reference=build_reference,complete=lambda ref,budget:Mix(ref))
  self.groups=dict(auditor=dict(ar_core=core))

class Tests(unittest.TestCase):
 def pp(self):return dict(updates=[],synthetic_steps=0)
 def ip(self):return dict(records=[])
 def test_fixed_prefix_and_noise(self):
  coeff,nu,rows=smoke.invented();self.assertEqual([len(r['marks']) for r in rows],[4,12,20]);self.assertEqual(rows[2]['marks'][:12],rows[1]['marks']);self.assertEqual(rows[1]['marks'][:4],rows[0]['marks']);self.assertEqual(len(nu),12);self.assertTrue(all(abs(math.fsum(n[c] for n in nu))<1e-14 for c in range(3)));self.assertEqual([r[4] for r in coeff],[.3,-.2,.8])
 def test_exact_three_updates(self):
  f=ProducerFixture();p=self.pp();out=smoke.producer(f.groups,p,lambda:None,lambda:10.)
  self.assertEqual(f.steps,3);self.assertEqual(p['synthetic_steps'],3);self.assertEqual(out['parameters'],25);self.assertEqual([v['step'] for v in p['updates']],[1,2,3]);self.assertNotIn('current_work',p)
  calls=[c for c in f.calls if c[0]=='kernel'];self.assertEqual(len(calls),3);self.assertTrue(all(c[1:4]==('L',(1,3,5),(0,0,0)) for c in calls));self.assertEqual(calls[0][4:],(((4,3),(12,3),(20,3)),(3,6),(3,12,3)));self.assertIn(('Adam',.001,3),f.calls)
 def test_zero_gradient_rejected_before_step(self):
  f=ProducerFixture();f.bad_grad=True;p=self.pp()
  with self.assertRaisesRegex(ValueError,'genuine_gradients'):smoke.producer(f.groups,p,lambda:None,lambda:10.)
  self.assertEqual(f.steps,0);self.assertEqual(p['synthetic_steps'],0)
 def test_one_zero_coefficient_rejected(self):
  f=ProducerFixture();f.bad_coefficient_entry=True;p=self.pp()
  # Preserve any()=True but reject the single zero element via the all18 check.
  original=Value.__ne__
  def compare(v,o):
   result=original(v,o)
   if 'all' in vars(v):result.all=v.all
   return result
  with patch.object(Value,'__ne__',compare),self.assertRaisesRegex(ValueError,'all18_coefficient_gradients'):smoke.producer(f.groups,p,lambda:None,lambda:10.)
  self.assertEqual(f.steps,0)
 def test_partial_adam_progress(self):
  f=ProducerFixture();f.step_failure=2;p=self.pp()
  with self.assertRaisesRegex(RuntimeError,'Adam'):smoke.producer(f.groups,p,lambda:None,lambda:10.)
  self.assertEqual(p['synthetic_steps'],1);self.assertEqual(p['optimizer_step_calls'],2);self.assertEqual(len(p['updates']),1);self.assertEqual(p['current_work']['step'],2)
 def test_lazy_adam_failure(self):
  f=ProducerFixture();f.lazy_failure=True;p=self.pp()
  with self.assertRaises(ModuleNotFoundError):smoke.producer(f.groups,p,lambda:None,lambda:10.)
  self.assertEqual(p['current_work']['phase'],'optimizer_construction');self.assertEqual(p['updates'],[])
 def test_independent_three_horizons_sixty_components(self):
  f=IndependentFixture();p=self.ip();out=smoke.independent(f.groups,p,lambda:None,lambda:10.);self.assertEqual([r['horizon'] for r in p['records']],[1,3,5]);self.assertTrue(all(r['components']==60 for r in p['records']));self.assertEqual([c for c in f.calls if c[0]=='scores'],[('scores',h,True) for h in (1,3,5)]);self.assertEqual(out['crosscheck'],'cdf-integral-crps');self.assertNotIn('current_work',p)
 def test_partial_proper_evidence(self):
  f=IndependentFixture();f.fail_horizon=3;p=self.ip()
  with self.assertRaisesRegex(ValueError,'late proper'):smoke.independent(f.groups,p,lambda:None,lambda:10.)
  self.assertEqual(len(p['records']),1);self.assertEqual(p['current_work']['scores'],{'mean':.5});self.assertEqual(p['current_work']['horizon'],3)
 def test_nonfinite_proper_rejected_preserved(self):
  f=IndependentFixture();f.bad_score=True;p=self.ip()
  with self.assertRaisesRegex(ValueError,'proper_finite'):smoke.independent(f.groups,p,lambda:None,lambda:10.)
  safe=smoke.failure_numeric(p);json.dumps(safe,allow_nan=False);self.assertIn('rejected_float64_hex',safe['current_work']['scores']['crps'])
 def setup_run(self,mode='independent',exit_error=False):
  raw=canonical({});self.calls=[];self.active=False
  @contextmanager
  def load(given,config,**kwargs):
   self.calls.append('enter');self.active=True;kwargs['check']()
   try:yield dict(mode=given,adapter_config_pin=pin(raw),groups={},observed_versions={'python':'invented'})
   finally:
    self.calls.append('exit');self.active=False
    if exit_error:raise ValueError('late loader check')
  self.kw=dict(raw_pin=pin(raw),expected_config_pin=pin(raw),io=IO,sb=object(),adapter=ns(load=load),processing_begin=10.,check=lambda:self.calls.append('check'),prefix='eew_l_smoke',clock=lambda:11.)
  def work(groups,progress,tick,clock):
   self.assertTrue(self.active);self.calls.append('work');tick();progress['synthetic_steps']=3 if mode=='producer' else 0;return {'rows':3}
  return raw,work
 def test_context_held_until_return(self):
  raw,work=self.setup_run()
  with patch.object(smoke,'independent',work):out=smoke.run('independent',raw,**self.kw)
  self.assertLess(self.calls.index('work'),self.calls.index('exit'));self.assertFalse(self.active);self.assertEqual(out['scienceactual'],0);self.assertEqual(out['phase'],'complete')
 def test_producer_dispatch(self):
  raw,work=self.setup_run('producer')
  with patch.object(smoke,'producer',work):out=smoke.run('producer',raw,**self.kw)
  self.assertEqual(out['synthetic_steps'],3)
 def test_bad_raw_pin_preload(self):
  raw,_=self.setup_run();self.kw['raw_pin']=pin(b'wrong')
  with self.assertRaises(smoke.SmokeFailure) as e:smoke.run('independent',raw,**self.kw)
  self.assertNotIn('enter',self.calls);self.assertIn('config_raw_pin',e.exception.evidence['reason'])
 def test_bad_canonical_pin_preload(self):
  raw,_=self.setup_run();self.kw['expected_config_pin']=pin(b'wrong')
  with self.assertRaises(smoke.SmokeFailure):smoke.run('independent',raw,**self.kw)
  self.assertNotIn('enter',self.calls)
 def test_expired_before_parse(self):
  self.setup_run();self.kw['clock']=lambda:311.
  with self.assertRaises(smoke.SmokeFailure) as e:smoke.run('independent',b'not JSON',**self.kw)
  self.assertIn('source_deadline',e.exception.evidence['reason']);self.assertNotIn('enter',self.calls)
 def test_nested_record_deadline_near_source_expiry(self):
  raw,_=self.setup_run();self.kw['clock']=lambda:305.
  def work(groups,progress,tick,record_clock):
   begin=record_clock();self.assertEqual(begin,300.);self.assertEqual(begin+10,self.kw['processing_begin']+300)
   return {'rows':3}
  with patch.object(smoke,'independent',work):out=smoke.run('independent',raw,**self.kw)
  self.assertEqual(out['seconds'],295.)
 def test_nested_record_deadline_preserves_full_ten_seconds_early(self):
  raw,_=self.setup_run()
  def work(groups,progress,tick,record_clock):
   self.assertEqual(record_clock(),11.);return {'rows':3}
  with patch.object(smoke,'producer',work):smoke.run('producer',raw,**self.kw)
 def test_late_context_failure_not_success(self):
  raw,work=self.setup_run(exit_error=True)
  with patch.object(smoke,'independent',work),self.assertRaises(smoke.SmokeFailure) as e:smoke.run('independent',raw,**self.kw)
  self.assertEqual(e.exception.evidence['status'],'incomplete');self.assertEqual(e.exception.evidence['detail'],{'rows':3})
 def test_external_lease_failure(self):
  raw,_=self.setup_run();self.kw['check']=lambda:(_ for _ in ()).throw(ValueError('lease'))
  with self.assertRaises(smoke.SmokeFailure) as e:smoke.run('independent',raw,**self.kw)
  self.assertIn('lease',e.exception.evidence['reason']);self.assertNotIn('enter',self.calls)
 def test_no_vendor_import(self):self.assertFalse({'torch','numpy','scipy'}&set(sys.modules))

if __name__=='__main__':unittest.main()

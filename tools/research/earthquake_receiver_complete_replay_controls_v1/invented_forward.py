"""Tiny constant saved-state fake model, no candidate import or fitting."""
import contextlib
import copy
from types import SimpleNamespace
import numpy as np
import controller as p

class Tensor(np.ndarray):
 def __new__(cls,value):return np.asarray(value).view(cls)
 def detach(self):return self
 def cpu(self):return self
 def double(self):return self.astype(np.float64)
 def numpy(self):return np.asarray(self)

class Net:
 created=[]
 def __init__(self,arm,mean):
  self.arm=arm;self.w=2.;self.hazards=SimpleNamespace(mref=mean,**{k:Tensor(np.full((2,36)if k=='z_weights'else(2,35)if k=='c_weights'else(2,),2.,dtype=np.float32))for k in('alpha','beta','z_weights','c_weights','gamma','extra')});self.created.append(self)
 def state_dict(self):return {'w':Tensor(np.array([self.w],dtype=np.float32))}
 def load_state_dict(self,value,strict):assert strict and set(value)=={'w'};self.w=float(value['w'][0])
 def eval(self):pass
 def current(self,*args):return Tensor(np.full((1,15),self.w,dtype=np.float32))
 def initial(self,*args):return self.current(),Tensor(np.full((1,36),self.w,dtype=np.float32))

class Mix:
 @staticmethod
 def from_raw(raw):return SimpleNamespace(weights=np.full(5,.2),means=np.asarray(raw[5:10]),sigmas=np.ones(5))

def setup(result,g):
 result=copy.deepcopy(result);rows=[dict(ordinal=i,mw=4.,group=i,initial={'context':np.zeros(35)},horizons=[{'rate':[100,1]}for _ in(1,3,5)])for i in range(115)];packet={'rows':rows};stats={k:np.ones(35 if k.startswith('initial')else 36,dtype=np.float64)for k in('initial_mean','initial_std','current_mean','current_std')}
 def batch(*args):return (None,None,Tensor(np.zeros((1,35),dtype=np.float32)),None)
 pilot=SimpleNamespace(validate=lambda packet:{'TRAIN':list(range(65)),'DEV':g['dev_ordinals']},scaler=lambda *args:stats,batch=batch,state_batch=lambda *args:(Tensor([[0,1]]),Tensor([[True,True]])))
 torch=SimpleNamespace(no_grad=contextlib.nullcontext,from_numpy=lambda a:Tensor(a));mods={'pilot':pilot,'models':SimpleNamespace(Net=Net),'numerical_core':SimpleNamespace(Mixture=Mix)}
 for fit in result['fits']:
  fit['train_population_std']=0.
  for item in fit['predictions']:
   item.update(target=4.,group=item['ordinal'],receiver=[0.,0.,0.],family='12Z',rate=[100,1])
   if fit['arm']in('C','H','T'):item['numerical']=dict(base_raw=[2.]*15,z=[2.]*36,c=[0.]*35,states=[0,1],mref=4.,hazard={k:np.full((2,36)if k=='z_weights'else(2,35)if k=='c_weights'else(2,),2.).tolist()for k in('alpha','beta','z_weights','c_weights','gamma','extra')})
   else:item['numerical']=dict(pi=[.2]*5,mu=[2.]*5,sigma=[1.]*5)
 return result,packet,stats,torch,mods

"""Invented callback fixtures; no real rows, models, funding or OS operations."""
import controller as c
import child

class Clock:
    def __init__(self): self.now=100.
    def __call__(self): return self.now

class Store:
    def __init__(self,clock): self.values={}; self.clock=clock; self.fail=None; self.delay=None; self.corrupt=False
    def exists(self,name): return name in self.values
    def read(self,name): return self.values[name]+(b' ' if self.corrupt else b'')
    def write(self,name,raw,replace=False,total_cap=0):
        if self.fail and self.fail in name: raise OSError('invented disk failure')
        if not replace and name in self.values: raise FileExistsError(name)
        c.need(sum(map(len,self.values.values()))-len(self.values.get(name,b''))+len(raw)<=total_cap,'disk_cap')
        self.values[name]=raw
        if self.delay and self.delay[0] in name: self.clock.now+=self.delay[1]
        return dict(status='durable',pin=c.pin(raw))

class Numeric:
    @staticmethod
    def encode(value): return c.canonical(value)
    @staticmethod
    def decode(raw,sha):
        c.need(c.pin(raw)['sha256']==sha,'hash'); return c.parse(raw)

class Processor:
    def __init__(self): self.calls=[]; self.skip=None; self.failure_step=None
    def prepare(self,packet,bindings,emit,processing_begin):
        self.calls.append('admission')
        for s,a in c.ORDER:
            if self.skip=='initial' and a=='D': continue
            emit('initial',c.canonical(dict(seed=s,arm=a,status='initial',update=0,study=c.STUDY,parameters={'fixture':1.})))
        raw=c.canonical(dict(status='admitted',study=c.STUDY,schema={'dev':list(range(65,87))},probe_terms=195,models=6))
        emit('admission',raw); return raw
    def fit_one(self,packet,admission,admission_sha,bindings,emit,seed,arm,processing_begin):
        self.calls.append(('fit',seed,arm)); history=[]
        value=dict(seed=seed,arm=arm,study=c.STUDY,status='initial',update=0,history=history)
        emit('begin_fit',c.canonical(value))
        for i in range(1,301):
            if i==self.failure_step: raise RuntimeError('invented update failure')
            history.append(dict(update=i,loss=1./i,gradient_norm=1.,ordinals=list(range(8))))
            value.update(status='partial',update=i,history=history); emit('step',c.canonical(value))
        value['status']='final'; raw=c.canonical(value); receipt=emit('final',raw)
        return dict(status='complete',checkpoint=raw,receipt=receipt)
    def score_final(self,packet,admission,admission_sha,checkpoint,checkpoint_sha,bindings,emit,processing_begin):
        saved=Numeric.decode(checkpoint,checkpoint_sha); self.calls.append(('score',saved['seed'],saved['arm']))
        rows=[]
        for ordinal in range(65,87):
            for h in (1,3,5):
                row=dict(seed=saved['seed'],arm=saved['arm'],ordinal=ordinal,horizon=h,status='complete',mean=2.)
                emit('forecast',c.canonical(row)); rows.append(row)
        raw=c.canonical(dict(seed=saved['seed'],arm=saved['arm'],study=c.STUDY,status='complete',predictions=rows,no_optimizer=True))
        receipt=emit('score_final',raw); return dict(status='complete',result=raw,receipt=receipt)
    def aggregate(self,packet,admission,admission_sha,new,strong,bindings,processing_begin):
        self.calls.append('aggregate'); c.need(len(new)==6,'six'); return dict(status='complete',pass_all=False,original24=[False]*24,additional12=[False]*12)

class Adapter:
    def __init__(self,clock,store,g):
        self.clock=clock; self.store=store; self.g=g; self.processor=Processor(); self.runs=[]; self.stops=[]; self.bad_live=False
        self.cleanup_bad=False; self.authorization_bad=False; self.run_bad=None; self.inputs={k:k.encode() for k in c.INPUTS}
    def authorize(self,g,spec,now):
        return dict(authorized=not self.authorization_bad,gate_sha256=c.identity(g),index=spec['index'],unit=spec['unit'],funding_pin=g['funding_pin'],expires=now+spec['manager_seconds'],
                    verified=dict(source_runtime=True,native_agreement=True,strong_closure=True,owned_unit_available=True))
    def run(self,request,timeout):
        self.runs.append(request['stage']['index']); self.request=request
        if self.run_bad=='exception': raise RuntimeError('uncertain transport')
        if self.run_bad=='malformed': return None
        report=child.execute(request,self.store,self,source_begin=self.clock(),clock=self.clock)
        return dict(code=0 if report['status']=='complete' else 1,timeout=False,stdout=b'fixture',stderr=b'',streams_complete=True)
    def live(self,unit):
        spec=self.request['stage']; return dict(unit=unit,active=not self.bad_live,limits=spec['limits'],runtime_max_seconds=spec['manager_seconds'])
    def load(self,name,expected): return self.inputs[name]
    def bind(self,request,raw):
        return dict(processor=self.processor,bindings=None,numeric=Numeric,packet=dict(schema=c.FEATURE,study=c.FEATURE_STUDY),strong_results=[],
                    binding_receipt=dict(verified=True,gate_sha256=c.identity(self.g),source_pins=self.g['source_pins'],runtime_pin=self.g['runtime_pin'],input_pins=self.g['input_pins']))
    def stop(self,unit,timeout): self.stops.append(unit); return dict(stopped=True,unit=unit)
    def inspect(self,unit,timeout):
        if self.cleanup_bad: raise RuntimeError('no cgroup observation')
        return dict(unit=unit,result='success',active_state='inactive',control_group='')

def fixture():
    clock=Clock(); store=Store(clock); p=c.pin(b'invented source')
    g=dict(schema='marked-sixfit-parent-gate-v1',study=c.STUDY,feature_schema=c.FEATURE,feature_study=c.FEATURE_STUDY,experiment_id='fixture-only',experiment_begin=clock(),
           source_pins={k:p for k in ('processor','operator','native','reference','parent','protocol')},runtime_pin=p,input_pins={k:c.pin(k.encode()) for k in c.INPUTS},funding_pin=p,storage_limit_bytes=16*1024*1024)
    return g,clock,store,Adapter(clock,store,g)

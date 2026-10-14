"""No models/data/cloud: invented callbacks, in-memory journal and manager EOF."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

path=Path(__file__).parent/'reference/secure_io.py'
pins=json.loads((Path(__file__).parent/'INHERITED_PINS.json').read_text());raw=path.read_bytes();p=pins['reference/secure_io.py'];assert len(raw)==p['bytes'] and hashlib.sha256(raw).hexdigest()==p['sha256']
spec=importlib.util.spec_from_file_location('secure_io',path);io=importlib.util.module_from_spec(spec);sys.modules['secure_io']=io;spec.loader.exec_module(io)
import control as c
import child

class Clock:
    def __init__(self):self.now=1000.
    def __call__(self):return self.now

class Memory:
    def __init__(self):self.files={};self.after=None;self.fail=None
    def write(self,i,name,raw,replace=False):
        if self.fail==name:raise OSError('invented fsync failure')
        if (i,name)in self.files and not replace:raise FileExistsError(name)
        self.files[i,name]=raw
        if self.after:self.after(i,name)
        return dict(status='durable',sha256=io.pin(raw)['sha256'])
    def object(self,i,name,value):return self.write(i,name,io.canonical(value))
    def read(self,i,name,expected=None):
        raw=self.files[i,name]
        if expected is not None:assert io.pin(raw)==expected
        return raw
    def exists(self,i,name):return (i,name)in self.files
    def inventory(self):return {str(i):{name:io.pin(raw) for (n,name),raw in self.files.items()if n==i}for i in range(9)}

class Numeric:
    encode=staticmethod(io.canonical)
    @staticmethod
    def decode(raw,digest):
        assert io.pin(raw)['sha256']==digest
        return c.parse(raw)

class Processor:
    def prepare(self,packet,bindings,emit,processing_begin):
        for seed in (20261012,20261013):emit('initial',Numeric.encode(dict(seed=seed,arm='L',status='initial',update=0,study=c.STUDY)))
        raw=Numeric.encode(dict(status='admitted',study=c.STUDY,schema=dict(dev=list(range(22)))))
        emit('admission',raw);return raw
    def fit_one(self,packet,adraw,adpin,bindings,emit,seed,arm,processing_begin):
        base=dict(seed=seed,arm=arm,study=c.STUDY,status='initial',update=0,history=[]);emit('begin_fit',Numeric.encode(base))
        for update in range(1,301):
            base.update(status='partial',update=update);base['history'].append(dict(update=update));emit('step',Numeric.encode(base))
        base['status']='final';raw=Numeric.encode(base);receipt=emit('final',raw);return dict(status='complete',checkpoint=raw,receipt=receipt)
    def score_final(self,packet,adraw,adpin,cpraw,cppin,bindings,emit,processing_begin):
        cp=Numeric.decode(cpraw,cppin);pred=[]
        for ordinal in range(22):
            for h in(1,3,5):
                value=dict(seed=cp['seed'],arm='L',ordinal=ordinal,horizon=h,status='complete');pred.append(value);emit('forecast',Numeric.encode(value))
        value=dict(seed=cp['seed'],arm='L',status='complete',study=c.STUDY,no_optimizer=True,predictions=pred);raw=Numeric.encode(value);receipt=emit('score_final',raw);return dict(status='complete',result=raw,receipt=receipt)
    def aggregate(self,*args,**kwargs):return dict(status='complete',pass_all=False,original24=[False]*24,additional18=[False]*18,record_counts=dict(new_L=132,reused_SPD=396,reused_BFHT=528,total=1056))
    @staticmethod
    def failure_numeric(x):return x

class Auditor:
    def audit_fit(self,score,packet,ad,old,checkpoint,authority,processing_begin,retain):
        rows=[]
        for i in range(66):
            value=dict(position=i,status='pass',fresh={'ordinal':i});retain(value);rows.append(value)
        report=dict(schema='shared-reference-AR-L-independent-audit-v1',status='pass',checked=66,seed=score['seed'],arm='L',records=rows);retain(report);return report
    def aggregate(self,fits,scores,packet,ad,old,closed,origins,authority,processing_begin,retain):
        value=dict(schema='shared-reference-AR-L-independent-aggregate-v1',status='pass',checked=132,record_counts=dict(new_L=132,reused_SPD=396,reused_BFHT=528,total=1056),paired=[None]*42,advance=dict(pass_all=False,checks=[False]*24,additional=[False]*18));retain(value);return value

class Adapter:
    def __init__(self,j,clock):
        self.j=j;self.clock=clock;self.called=[];self.stopped=[];self.live_bad=False;self.proof_bad=False;self.noheld=False;self.answer_change=None;self.post_bad=False;self.bind_failure=False;self.model=Processor();self.auditor=Auditor()
        self.documents_raw={k:io.canonical({'invented':k})for k in('funding','publication','protocol','root_context')}
        self.inputs={k:io.canonical({'invented_input':k})for k in c.INPUTS}
    def config(self):
        return dict(schema='shared-reference-AR-L-nine-stage-config-v1',study=c.STUDY,feature_schema='earthquake-TRAIN115-marked-noise-observations-v1',feature_study='earthquake-TRAIN115-marked-noise-study-v1',experiment_id='invented-only',whole_begin=1000.,lease_deadline=8400.,source_pins={k:io.pin(k.encode())for k in c.SOURCES},runtime_pin=io.pin(b'runtime'),input_pins={k:io.pin(raw)for k,raw in self.inputs.items()},funding_pin=io.pin(self.documents_raw['funding']),publication_pin=io.pin(self.documents_raw['publication']),protocol_pin=io.pin(self.documents_raw['protocol']),storage_limit_bytes=9*64*1024*1024)
    def documents(self,scope):return self.documents_raw
    def authorize(self,scope,documents,now):
        g=scope;proofs=dict(source=io.pin(io.canonical(g['source_pins'])),runtime=g['runtime_pin'],native=g['input_pins']['feature_authority'],original_initialization=g['input_pins']['original_admission_authority'],reused924=g['input_pins']['comparator_authority'],resources=io.pin(b'fake-resource'),storage=io.pin(b'fake-storage'))
        if self.proof_bad:proofs['native']=io.pin(b'wrong')
        return dict(schema='root-shared-reference-AR-L-stage-authority-v1',scope=copy.deepcopy(scope),decision='authorized',expires=scope['lease_deadline'],proofs=proofs)
    def prior_closed(self,g,i,closed,inventory):
        if self.noheld:raise ValueError('no ROOT last return')
        return dict(schema='root-shared-reference-AR-L-prior-closure-v1',stage=i,config_pin=c.config_pin(g),closed_pin=io.pin(self.j.read(i,'closed.json')),result_pin=closed['result_pin'],known_return_pin=io.pin(io.canonical(closed)))
    def live(self,unit):
        for i in range(9):
            s=c.spec(self.g,i)
            if s['unit']==unit:return dict(unit=unit,active=not self.live_bad,limits=s['limits'],runtime_max_seconds=s['manager_seconds'])
    def load(self,name,p):return self.inputs[name]
    def bind(self,request,raw):
        if self.bind_failure:raise ValueError('before scientific import')
        g=request['config'];return dict(processor=self.model if request['stage']['index']<6 else None,bindings=None,numeric=Numeric,packet=dict(schema=g['feature_schema'],study=g['feature_study']),original_admission={},reused_results=[],strong_results=[],closed_comparator_report={},origins=[],auditor=self.auditor,binding_receipt=dict(verified=True,config_pin=request['config_pin'],source_pins=g['source_pins'],runtime_pin=g['runtime_pin'],input_pins=g['input_pins']))
    def audit_authority(self,*args):return {'invented':True}
    def run(self,request,timeout):
        self.called.append(request['stage']['index']);child.execute(request,self.j,self,expected_config_pin=c.config_pin(self.g),source_begin=self.clock(),clock=self.clock)
        answer=dict(code=0,timeout=False,streams_complete=True,exception=None,stdout=b'invented EOF',stderr=b'')
        answer['stream_custody']={k:dict(original_bytes=len(answer[k]),original_sha256=io.pin(answer[k])['sha256'],retained_bytes=len(answer[k]),truncated=False,complete_observation=True)for k in('stdout','stderr')}
        if self.answer_change:self.answer_change(answer)
        return answer
    def stop(self,unit,timeout):self.stopped.append(unit);return {'unit':unit,'stopped':True}
    def inspect(self,unit,timeout):return dict(unit=unit,result='success',active_state='active'if self.post_bad else'inactive',control_group='uncertain'if self.post_bad else'')


def setup():
    clock=Clock();j=Memory();adapter=Adapter(j,clock);g=adapter.config();adapter.g=g;return clock,j,adapter,g

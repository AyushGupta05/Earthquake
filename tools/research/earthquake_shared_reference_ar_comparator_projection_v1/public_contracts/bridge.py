"""ROOT-dependent L deployment Adapter; source-only, no permissive authority."""
import copy
import math
import re
import time
from codec import Numeric

SEEDS=(20261012,20261013)
REUSED=tuple((s,a)for s in SEEDS for a in('S','P','D'))
STRONG=tuple((s,a)for s in SEEDS for a in('B','F','H','T'))


def digest(io,value):
    io.need(type(value)is str and re.fullmatch('[0-9a-f]{64}',value),'digest');return value


def filespec(io,spec,cap):
    io.need(type(spec)is dict and set(spec)=={'path','pin','mode'} and spec['mode']==0o400,'readonly_spec')
    io.parts(spec['path'],True);io.pin_check(spec['pin'],cap);io.need(spec['pin']['bytes']>0,'positive_pin')


class Adapter:
    def __init__(self,g,*,expected_config_pin,input_specs,historical_specs,loader_config,expected_loader_config_pin,io,sb,runtime_adapter,control,systemd,trusted,stack,check,source_begin,prefix,python,clock=time.monotonic):
        self.g=copy.deepcopy(g);self.expected=copy.deepcopy(expected_config_pin);self.io=io;self.control=control;self.clock=clock
        control.config_check(self.g,clock(),self.expected);check()
        io.need(type(input_specs)is dict and set(input_specs)==control.INPUTS,'input_specs')
        for name,spec in input_specs.items():filespec(io,spec,16*1024*1024);io.need(spec['pin']==g['input_pins'][name],'input_subject')
        io.need(type(historical_specs)is dict and set(historical_specs)=={'reused_scores','stronger_envelope'} and type(historical_specs['reused_scores'])is list and len(historical_specs['reused_scores'])==6,'historical_specs')
        for entry,pair in zip(historical_specs['reused_scores'],REUSED):
            io.need(type(entry)is dict and set(entry)=={'seed','arm','spec'} and type(entry['seed'])is int and (entry['seed'],entry['arm'])==pair,'historical_order');filespec(io,entry['spec'],2*1024*1024)
        filespec(io,historical_specs['stronger_envelope'],16*1024*1024)
        io.pin_check(expected_loader_config_pin);io.need(io.pin(io.canonical(loader_config))==expected_loader_config_pin,'held_loader_pin')
        io.need(type(source_begin)in(int,float) and math.isfinite(source_begin) and 0<=source_begin<=clock() and type(prefix)is str and re.fullmatch('eew_l_[a-z0-9_]{1,64}',prefix),'source_clock_prefix')
        io.need(type(python)is str and python.startswith('/') and python==loader_config['runtime']['python'],'python_subject')
        for name in('documents','authorize','prior_closed','launch','authenticate_raw','project_comparators','previous_raw','authenticate_previous','verify_audit_authority'):io.need(callable(getattr(trusted,name,None)),'ROOT_callback')
        self.input_specs=copy.deepcopy(input_specs);self.history=copy.deepcopy(historical_specs);self.loader_config=copy.deepcopy(loader_config);self.loader_pin=copy.deepcopy(expected_loader_config_pin)
        self.sb=sb;self.loader=runtime_adapter;self.sd=systemd;self.trusted=trusted;self.stack=stack;self.check=check;self.source_begin=source_begin;self.prefix=prefix;self.python=python;self.used=False;self.receipt=None;self.bound=None;self.input_scope=None
        self.previous_raws=None;self.previous_scope=None;self.bound_request_pin=None
        self.units={control.spec(self.g,i)['unit']:control.spec(self.g,i)for i in range(9)}
        for unit in self.units:systemd.own(unit)
    def request(self,request):
        self.check();self.io.need(type(request)is dict and request['config_pin']==self.expected and request['config']==self.g and request['stage']==self.control.spec(self.g,request['stage']['index']),'request_subject')
    def documents(self,scope):self.check();return self.trusted.documents(scope)
    def authorize(self,scope,documents,now):self.check();return self.trusted.authorize(scope,documents,now)
    def prior_closed(self,g,index,closed,inventory):
        self.check();self.io.need(g==self.g,'prior_config');return self.trusted.prior_closed(g,index,closed,inventory)
    def run(self,request,timeout):
        self.request(request);launch=self.trusted.launch(request)
        self.io.need(type(launch)is dict and set(launch)=={'python','code','code_pin','request_pin'} and launch['python']==self.python and type(launch['code'])is str and launch['request_pin']==self.io.pin(self.io.canonical(request)) and self.io.pin(launch['code'].encode())==launch['code_pin'],'launch_subject')
        self.check();return self.sd.run(self.control.command(request['stage'],self.python,launch['code']),timeout,request['stage']['unit'])
    def stop(self,unit,timeout):self.io.need(unit in self.units,'foreign_unit');return self.sd.stop(unit,timeout)
    def inspect(self,unit,timeout):self.io.need(unit in self.units,'foreign_unit');return self.sd.inspect(unit,timeout)
    def live(self,unit):self.io.need(unit in self.units,'foreign_unit');return self.sd.live(self.units[unit])
    def load(self,name,pin):
        self.check();self.io.need(name in self.input_specs and pin==self.input_specs[name]['pin'],'input_role');raw=self.io.read_file(self.input_specs[name],16*1024*1024);self.check();return raw
    def bind(self,request,raw_inputs):
        self.request(request);self.io.need(not self.used,'bind_once');self.used=True
        io=self.io;io.need(type(raw_inputs)is dict and set(raw_inputs)==self.control.INPUTS,'raw_inputs')
        for name,raw in raw_inputs.items():io.need(type(raw)is bytes and io.pin(raw)==self.g['input_pins'][name],'raw_input_pin')
        raw_history=[]
        for entry in self.history['reused_scores']:self.check();raw_history.append(io.read_file(entry['spec'],2*1024*1024))
        stronger_raw=io.read_file(self.history['stronger_envelope'],16*1024*1024);self.check()
        mode='producer' if request['stage']['index']<6 else 'independent'
        loaded=self.stack.enter_context(self.loader.load(mode,self.loader_config,expected_config_pin=self.loader_pin,io=io,sb=self.sb,check=self.check,prefix=self.prefix))
        io.need(loaded['mode']==mode and loaded['adapter_config_pin']==self.loader_pin,'loader_subject');groups=loaded['groups']
        roles={'operator','native_validator','reference','kernel','processor','protocol','numeric_state'}
        io.need(type(loaded['source_pins'])is dict and set(loaded['source_pins'])==roles and loaded['source_pins']=={k:self.g['source_pins'][k]for k in roles} and loaded['original_source_pins']==self.loader_config['original_source_pins'],'loader_source_subjects')
        scope=dict(schema='L-bridge-input-scope-v1',config_pin=self.expected,stage=request['stage'],unit=request['stage']['unit'],mode=mode,source_begin=self.source_begin,loader_config_pin=self.loader_pin,input_pins=self.g['input_pins'],historical_pins=dict(reused_scores=[io.pin(v)for v in raw_history],stronger_envelope=io.pin(stronger_raw)),source_pins=loaded['source_pins'],original_source_pins=loaded['original_source_pins'])
        receipt=self.trusted.authenticate_raw(scope,raw_inputs,dict(reused_scores=raw_history,stronger_envelope=stronger_raw),self.clock())
        io.need(type(receipt)is dict and set(receipt)=={'schema','scope','decision','packet_sha256','original_execution_closure_sha256','source_pins','original_source_pins','proof_pin'} and receipt['schema']=='root-L-bridge-input-authentication-v1' and receipt['scope']==scope and receipt['decision']=='authorized' and receipt['source_pins']==loaded['source_pins'] and receipt['original_source_pins']==loaded['original_source_pins'],'input_authentication')
        for k in('packet_sha256','original_execution_closure_sha256'):digest(io,receipt[k])
        io.pin_check(receipt['proof_pin']);io.need(receipt['proof_pin']['bytes']>0,'input_proof')
        self.receipt=receipt;self.input_scope=scope;self.check() # NO decoding before this positive ROOT boundary.
        # Frozen child decodes prior admission immediately after bind returns.
        # Authenticate its exact pinned prior bytes here, before exposing any codec.
        self.bound_request_pin=io.pin(io.canonical(request));i=request['stage']['index']
        needed={0:(),1:(0,),2:(0,1),3:(0,),4:(0,3),5:(0,2,4),6:(0,1,2),7:(0,3,4),8:(0,2,4,6,7)}[i]
        self.previous_raws={}
        for n in needed:
            self.check();v=self.trusted.previous_raw(request,n,request['previous'][n]['result_pin']);io.need(type(v)is bytes and len(v)<=16*1024*1024 and io.pin(v)==request['previous'][n]['result_pin'],'previous_raw');self.previous_raws[str(n)]=v
        self.previous_scope=dict(schema='L-bridge-audit-scope-v1',input_scope=self.input_scope,stage=request['stage'],previous_pins={n:io.pin(v)for n,v in self.previous_raws.items()})
        if needed:
            authenticated=self.trusted.authenticate_previous(self.previous_scope,self.previous_raws,self.receipt,self.clock())
            io.need(type(authenticated)is dict and set(authenticated)=={'schema','scope','decision','proof_pin'} and authenticated['schema']=='root-L-bridge-previous-authentication-v1' and authenticated['scope']==self.previous_scope and authenticated['decision']=='authorized','previous_authentication');io.pin_check(authenticated['proof_pin']);io.need(authenticated['proof_pin']['bytes']>0,'previous_proof')
        self.check()
        native=groups['native']['packet_io'];packet=native.load(raw_inputs['feature_archive'],raw_inputs['feature_manifest'],pins=dict(archive=self.g['input_pins']['feature_archive'],manifest=self.g['input_pins']['feature_manifest']),processing_begin=self.source_begin)
        if mode=='producer':
            pg=groups['processor'];op=pg['processor'];numeric=pg['numeric_state'];historical=Numeric(io,np=native.np);packet_sha=op.packet_hash(packet)
        else:
            io.need(set(groups)=={'native','auditor'},'independent_groups');ag=groups['auditor'];numeric=historical=Numeric(io,transport=ag['transport']);op=None;packet_sha=ag['packet_digest'].sha(packet)
        io.need(packet_sha==receipt['packet_sha256'],'packet_identity')
        old_raw=raw_inputs['original_admission'];old_pin=self.g['input_pins']['original_admission']['sha256'];original=historical.decode(old_raw,old_pin,cap=2*1024*1024)
        io.need(original['study']=='earthquake-TRAIN115-marked-noise-fitting-v2' and original['status']=='admitted' and original['source_pins']==loaded['original_source_pins'] and original['packet_sha256']==packet_sha,'original_admission_subject')
        six=[historical.decode(v,io.pin(v)['sha256'],cap=2*1024*1024)for v in raw_history]
        stronger=historical.decode(stronger_raw,io.pin(stronger_raw)['sha256'])
        closed=historical.decode(raw_inputs['closed_comparator_report'],self.g['input_pins']['closed_comparator_report']['sha256'])
        origins=historical.decode(raw_inputs['comparator_origins'],self.g['input_pins']['comparator_origins']['sha256'])
        io.need(type(closed)is dict and closed['schema']=='marked-sixfit-independent-aggregate-v1' and closed['status']=='pass' and len(closed['fits'])==6 and len(closed['stronger'])==8,'closed924')
        io.need(sum(len(v['records'])for v in closed['fits'])==396 and sum(len(v['records'])for v in closed['stronger'])==528 and type(origins)is list and len(origins)==14,'closed924_counts')
        projection=self.trusted.project_comparators(scope,packet,six,stronger,closed,origins,receipt)
        io.need(type(projection)is dict and set(projection)=={'reused_results','strong_results','origins'} and io.pin(historical.encode(projection['origins']))==self.g['input_pins']['comparator_origins'],'origin_projection')
        for key,expected in(('reused_results',REUSED),('strong_results',STRONG)):
            records=projection[key];io.need(type(records)is list and len(records)==len(expected) and [(v['seed'],v['arm'])for v in records]==list(expected),'projected_order')
            for v in records:io.need(v['status']=='complete' and v['no_optimizer']is True and v['packet_sha256']==packet_sha and len(v['predictions'])==66,'projected_population')
        if mode=='producer':bindings=op.Bindings(groups['gaussian']['gaussian_operator'],native,groups['reference']['ar_core'],groups['kernel']['kernel'],loaded['source_pins'],old_raw,old_pin,loaded['original_source_pins']);auditor=None
        else:bindings=None;auditor=groups['auditor']['l_auditor']
        self.check();self.bound=dict(processor=op,bindings=bindings,numeric=numeric,packet=packet,original_admission=original,reused_results=projection['reused_results'],strong_results=projection['strong_results'],closed_comparator_report=closed,origins=origins,auditor=auditor,binding_receipt=dict(verified=True,config_pin=self.expected,source_pins=self.g['source_pins'],runtime_pin=self.g['runtime_pin'],input_pins=self.g['input_pins']))
        return self.bound
    def audit_authority(self,request,previous_pins,bound):
        self.request(request);self.io.need(bound is self.bound and self.receipt is not None and request['stage']['index']in(6,7,8) and self.io.pin(self.io.canonical(request))==self.bound_request_pin,'audit_scope')
        io=self.io;i=request['stage']['index']
        io.need(previous_pins==[dict(stage=n,result_pin=v['result_pin'])for n,v in enumerate(request['previous'])],'previous_scope')
        raw=self.previous_raws;scope=self.previous_scope;self.check()
        numeric=bound['numeric'];decoded={n:numeric.decode(v,io.pin(v)['sha256'])for n,v in raw.items()}
        candidate=dict(schema='root-shared-reference-AR-L-audit-authority-v1'if i<8 else'root-shared-reference-AR-L-aggregate-authority-v1',packet_sha256=self.receipt['packet_sha256'],admission_sha256=io.pin(raw['0'])['sha256'],original_admission_sha256=self.g['input_pins']['original_admission']['sha256'],original_execution_closure_sha256=self.receipt['original_execution_closure_sha256'],source_pins=self.receipt['source_pins'],original_source_pins=self.receipt['original_source_pins'])
        if i<8:
            ck,score=('1','2')if i==6 else('3','4');candidate.update(checkpoint_sha256=io.pin(raw[ck])['sha256'],score_sha256=io.pin(raw[score])['sha256']);flags={'verified','native_verified','optimizer_history_verified','gradient_probes_verified','original_initialization_verified'}
        else:
            candidate.update(closed_comparator_report_sha256=self.g['input_pins']['closed_comparator_report']['sha256'],origins_sha256=self.g['input_pins']['comparator_origins']['sha256'],fits=[])
            for seed,score_idx,audit_idx in((20261012,'2','6'),(20261013,'4','7')):
                a=decoded[audit_idx];score=decoded[score_idx];candidate['fits'].append(dict(seed=seed,arm='L',audit_sha256=io.pin(raw[audit_idx])['sha256'],authority_sha256=digest(io,a['authority_sha256']),score_sha256=io.pin(raw[score_idx])['sha256'],checkpoint_sha256=digest(io,score['checkpoint_sha256'])))
            flags={'verified','native_verified','original_initialization_verified','comparators_verified'}
        self.check();approval=self.trusted.verify_audit_authority(scope,candidate,raw,self.receipt,self.clock())
        io.need(type(approval)is dict and set(approval)=={'schema','scope','decision','authority','proof_pin'} and approval['schema']=='root-L-bridge-audit-verification-v1' and approval['scope']==scope and approval['decision']=='authorized','audit_verification')
        io.pin_check(approval['proof_pin']);io.need(approval['proof_pin']['bytes']>0,'audit_proof');authority=approval['authority']
        io.need(type(authority)is dict and set(authority)==set(candidate)|flags and all(authority[k]==v for k,v in candidate.items()) and all(authority[k]is True for k in flags),'audit_authority_subject');self.check();return authority


def make_adapter(*args,**kwargs):return Adapter(*args,**kwargs)

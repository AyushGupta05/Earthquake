"""Narrow ROOT composition for the frozen nine-stage L bridge.

All proof semantics are mandatory independently bound read-only primitives.
No cloud action, evidence inference, numerical model, or permissive authorizer.
"""
import copy
from contextlib import ExitStack, contextmanager
import math
import re
import time

ROLES={'operator','native_validator','reference','kernel','processor','protocol','numeric_state'}
PRIOR={0:(),1:(0,),2:(0,1),3:(0,),4:(0,3),5:(0,2,4),6:(0,1,2),7:(0,3,4),8:(0,2,4,6,7)}
MODULES=('secure_io','vendor_inventory','generated_source','metadata_finder',
         'source_binding','systemd_adapter','codec','bridge','runtime_adapter',
         'control','child','journal','projection','comparator_population','root_glue')


class Root:
    def __init__(self,held,*,expected_pin,root_spec,io,control,projection,population,
                 primitives,custody,journal,modules,source_begin=None,clock=time.monotonic):
        self.io=io;self.c=control;self.projection=projection;self.population=population
        self.primitives=primitives;self.custody=custody;self.journal=journal
        self.modules=modules;self.clock=clock;self.source_begin=source_begin
        self.h=copy.deepcopy(held);self.expected=copy.deepcopy(expected_pin)
        self.root_spec=copy.deepcopy(root_spec);self.active=None;self.receipt=None
        self.prior={};self.projector=None;self.launches=set();self.loaded=None;self.comparison_group=None;self.issued={};self.requests={}
        io.need(type(held)is dict and set(held)=={'schema','execution','execution_pin','loader','loader_pin',
            'inputs','history','documents','evidence','facts','launch'},'root_fields')
        io.need(held['schema']=='root-held-L-composition-v1','root_schema')
        self._spec(root_spec,2*1024*1024);io.pin_check(expected_pin,2*1024*1024)
        io.need(root_spec['pin']==expected_pin and io.pin(io.canonical(held))==expected_pin,'independent_root_pin')
        io.need(io.read_file(root_spec,2*1024*1024)==io.canonical(held),'root_raw')
        control.config_check(self.h['execution'],clock(),self.h['execution_pin'])
        io.need(io.pin(io.canonical(self.h['loader']))==self.h['loader_pin'],'loader_pin')
        io.need(population.SOURCE_PROCESSOR_PIN==self.h['loader']['sources']['processor']['files']['processor.py'],'frozen_population_source')
        io.need(type(self.h['inputs'])is dict and set(self.h['inputs'])==control.INPUTS,'input_roles')
        for name,spec in self.h['inputs'].items():
            self._spec(spec,16*1024*1024);io.need(spec['pin']==self.g['input_pins'][name],'input_subject')
        history=self.h['history'];io.need(type(history)is dict and set(history)=={'reused_scores','stronger_envelope'}and type(history['reused_scores'])is list and len(history['reused_scores'])==6,'history_roles')
        for entry,pair in zip(history['reused_scores'],((s,a)for s in(20261012,20261013)for a in('S','P','D'))):
            io.need(type(entry)is dict and set(entry)=={'seed','arm','spec'}and type(entry['seed'])is int and(entry['seed'],entry['arm'])==pair,'history_order');self._spec(entry['spec'],2*1024*1024)
        self._spec(history['stronger_envelope'],16*1024*1024)
        io.need(type(self.h['documents'])is dict and set(self.h['documents'])=={'funding','publication','protocol','root_context'},'document_roles')
        io.need(type(self.h['evidence'])is dict and set(self.h['evidence'])=={'source_runtime','current','inputs','projection','audit'},'evidence_roles')
        for group in('documents','evidence'):
            for spec in self.h[group].values():self._spec(spec,16*1024*1024)
        for name in('funding','publication','protocol'):io.need(self.h['documents'][name]['pin']==self.g[name+'_pin'],'document_subject')
        io.need(self.h['documents']['root_context']['pin']['bytes']<=1024*1024,'root_context_cap')
        io.need(type(self.h['facts'])is dict and set(self.h['facts'])=={'packet_sha256','original_execution_closure_sha256'},'facts')
        for value in self.h['facts'].values():self._digest(value)
        launch=self.h['launch'];io.need(type(launch)is dict and set(launch)=={'bootstrap','primitive_source','modules','store_directory','prefix','python','commands'},'launch_fields')
        for name in('bootstrap','primitive_source'):self._spec(launch[name],16*1024*1024)
        io.need(type(launch['modules'])is dict and set(launch['modules'])==set(MODULES),'bootstrap_modules')
        for spec in launch['modules'].values():self._spec(spec,16*1024*1024)
        io.parts(launch['store_directory'],True)
        io.need(launch['python']==self.h['loader']['runtime']['python'] and type(launch['python'])is str and launch['python'].startswith('/'),'python')
        io.need(type(launch['prefix'])is str and re.fullmatch('eew_l_[a-z0-9_]{1,64}',launch['prefix']),'prefix')
        for name in('source_runtime','current','inputs','prior','audit'):io.need(callable(getattr(primitives,name,None)),'mandatory_primitive')
        io.need(callable(getattr(custody,'snapshot',None)),'readonly_custody')
        if source_begin is not None:io.need(type(source_begin)in(int,float)and math.isfinite(source_begin)and self.g['whole_begin']<=source_begin<=clock(),'held_source_clock')
        self._source(self._root_scope(),clock())

    @property
    def g(self):return self.h['execution']

    def _digest(self,value):
        self.io.need(type(value)is str and re.fullmatch('[0-9a-f]{64}',value),'digest')

    def _spec(self,spec,cap):
        io=self.io;io.need(type(spec)is dict and set(spec)=={'path','pin','mode'}and type(spec['mode'])is int and spec['mode']==0o400,'readonly_spec')
        io.parts(spec['path'],True);io.pin_check(spec['pin'],cap);io.need(spec['pin']['bytes']>0,'positive_spec')

    def check(self):
        now=self.clock();self.c.config_check(self.g,now,self.h['execution_pin'])
        self.io.need(now<=min(self.g['whole_begin']+7200,self.g['lease_deadline']),'whole_deadline')
        if self.active is not None:
            self.io.need(self.source_begin is not None and now-self.source_begin<=self.active['stage']['source_seconds'],'source_deadline')
            self.io.need(now<=self.active['parent_authority']['expires'],'parent_deadline')

    def _root_scope(self):return dict(schema='root-L-composition-scope-v1',root_pin=self.expected,execution_pin=self.h['execution_pin'],loader_pin=self.h['loader_pin'])

    def _evidence(self,name):
        self.check();raw=self.io.read_file(self.h['evidence'][name],16*1024*1024);self.check();return raw

    def _attest(self,result,kind,scope,evidence_pin):
        io=self.io;io.need(type(result)is dict and set(result)=={'schema','kind','scope_pin','evidence_pin','claims'}and result['schema']=='root-L-primitive-verification-v1'and result['kind']==kind and result['scope_pin']==io.pin(io.canonical(scope))and result['evidence_pin']==evidence_pin and type(result['claims'])is dict,'primitive_attestation')
        io.pin_check(evidence_pin);self.check();return result['claims']

    def _source(self,scope,now):
        raw=self._evidence('source_runtime');r=self.primitives.source_runtime(scope,copy.deepcopy(self.h),dict(support=self.modules,scientific=self.loaded),raw,now)
        claims=self._attest(r,'source_runtime',scope,self.h['evidence']['source_runtime']['pin'])
        self.io.need(claims==dict(source=self.io.pin(self.io.canonical(self.g['source_pins'])),runtime=self.g['runtime_pin']),'source_runtime_subject')
        return claims

    def _stage_scope(self,scope):
        i=scope['stage']['index'];phase=scope['phase'];self.io.need(scope==self.c.scope(self.g,self.c.spec(self.g,i),phase),'held_stage_scope');return i,phase

    def _request(self,request):
        self.check();i=request['stage']['index'];self.io.need(request['config']==self.g and request['config_pin']==self.h['execution_pin'] and request['stage']==self.c.spec(self.g,i),'held_request')
        self.c.receipt_checked(self.g,request['stage'],'parent',request['parent_authority'],request['dispatch_begin'])
        self.io.need(type(request['previous'])is list and len(request['previous'])==i and all(v['stage']==n for n,v in enumerate(request['previous'])),'previous_order')
        return i

    def documents(self,scope):
        self._stage_scope(scope);self.check()
        return {k:self.io.read_file(s,1024*1024 if k=='root_context'else 16*1024*1024)for k,s in self.h['documents'].items()}

    def authorize(self,scope,documents,now):
        _,phase=self._stage_scope(scope);self.io.need(documents==self.documents(scope),'exact_documents')
        source=self._source(scope,now);raw=self._evidence('current')
        r=self.primitives.current(scope,copy.deepcopy(self.h),documents,raw,now)
        claims=self._attest(r,'current',scope,self.h['evidence']['current']['pin'])
        self.io.need(set(claims)=={'expires','resources','storage'},'current_claims')
        for k in('resources','storage'):self.io.pin_check(claims[k]);self.io.need(claims[k]['bytes']>0,'current_proof')
        base={k:self.io.read_file(s,16*1024*1024)for k,s in self.h['inputs'].items()}
        history=dict(reused_scores=[self.io.read_file(v['spec'],2*1024*1024)for v in self.h['history']['reused_scores']],stronger_envelope=self.io.read_file(self.h['history']['stronger_envelope'],16*1024*1024))
        self._input_attestation(scope,base,history,now)
        proofs=dict(source, native=self.g['input_pins']['feature_authority'],original_initialization=self.g['input_pins']['original_admission_authority'],reused924=self.g['input_pins']['comparator_authority'],resources=claims['resources'],storage=claims['storage'])
        receipt=dict(schema='root-shared-reference-AR-L-stage-authority-v1',scope=copy.deepcopy(scope),decision='authorized',expires=claims['expires'],proofs=proofs)
        self.c.receipt_checked(self.g,scope['stage'],phase,receipt,now);self.issued[scope['stage']['index'],phase]=copy.deepcopy(receipt);return receipt

    def _closed(self,index,scope,inventory=None):
        io=self.io;snapshot=self.custody.snapshot(index)
        io.need(type(snapshot)is dict and set(snapshot)=={'known_raw','known_pin','files','inventory'},'custody_snapshot')
        io.need(type(snapshot['known_raw'])is bytes and len(snapshot['known_raw'])<=1024*1024 and io.pin(snapshot['known_raw'])==snapshot['known_pin'],'known_return_raw')
        r=self.primitives.prior(scope,copy.deepcopy(self.h),snapshot,inventory,self.clock())
        claims=self._attest(r,'prior',scope,snapshot['known_pin'])
        io.need(set(claims)=={'known_return_pin','closed_pin','result_pin'}and claims['known_return_pin']==snapshot['known_pin'],'prior_claims')
        files=snapshot['files'];io.need(type(files)is dict and {'closed.json','result.json','child_report.json','claim.json','dispatch.json'}<=set(files)and not({'late_or_failed.json','child_failure.json'}&set(files)),'closure_files')
        raw={}
        for name,spec in files.items():
            io.need(type(name)is str and '/'not in name,'closure_name');self._spec(spec,16*1024*1024);raw[name]=io.read_file(spec,16*1024*1024)
        io.need(io.pin(raw['closed.json'])==claims['closed_pin']and io.pin(raw['result.json'])==claims['result_pin'],'closed_subjects')
        closed=io.json_read(raw['closed.json']);known=io.json_read(snapshot['known_raw'])
        io.need(type(known)is dict and set(known)=={'schema','stage','config_pin','returned','inventory'}and known['schema']=='root-L-known-parent-return-v1'and known['stage']==index and known['config_pin']==self.h['execution_pin']and known['returned']==closed and known['inventory']==snapshot['inventory'],'known_exact_return')
        io.need(closed['schema']=='shared-reference-AR-L-parent-return-v1'and closed['status']=='complete'and closed['stage']==index and closed['config_pin']==self.h['execution_pin']and closed['unit']==self.c.spec(self.g,index)['unit']and closed['cleanup_verified']is True and closed['errors']==[]and closed['no_retry']is True and closed['result_pin']==claims['result_pin'],'new_closed_manager')
        self.prior[index]=(copy.deepcopy(claims),raw,copy.deepcopy(snapshot))
        return claims,raw

    def prior_closed(self,g,index,closed,inventory):
        self.io.need(g==self.g,'prior_config');scope=dict(schema='root-L-prior-scope-v1',root_scope=self._root_scope(),stage=index,closed_pin=self.io.pin(self.io.canonical(closed)))
        claims,raw=self._closed(index,scope,inventory);self.io.need(raw['closed.json']==self.io.canonical(closed),'requested_closed')
        return dict(schema='root-shared-reference-AR-L-prior-closure-v1',stage=index,config_pin=self.h['execution_pin'],**claims)

    def previous_raw(self,request,index,result_pin):
        i=self._request(request);self.io.need(index in PRIOR[i]and request['previous'][index]['result_pin']==result_pin,'requested_prior')
        scope=dict(schema='root-L-prior-scope-v1',root_scope=self._root_scope(),stage=index,request_pin=self.io.pin(self.io.canonical(request)),result_pin=result_pin)
        claims,raw=self._closed(index,scope);item=request['previous'][index]
        self.io.need(claims['result_pin']==result_pin and item['closed_pin']==claims['closed_pin']and item['known_return_pin']==claims['known_return_pin']and item['claim_pin']==self.io.pin(raw['claim.json']),'held_previous_pin');return raw['result.json']

    def _input_scope(self,stage):
        i=stage['index'];io=self.io
        io.need(self.source_begin is not None and stage==self.c.spec(self.g,i),'child_source_scope')
        return dict(schema='L-bridge-input-scope-v1',config_pin=self.h['execution_pin'],stage=stage,unit=stage['unit'],mode='producer'if i<6 else'independent',source_begin=self.source_begin,loader_config_pin=self.h['loader_pin'],input_pins=self.g['input_pins'],historical_pins=dict(reused_scores=[v['spec']['pin']for v in self.h['history']['reused_scores']],stronger_envelope=self.h['history']['stronger_envelope']['pin']),source_pins={k:self.g['source_pins'][k]for k in ROLES},original_source_pins=self.h['loader']['original_source_pins'])

    def authenticate_raw(self,scope,raw_base,raw_history,now):
        io=self.io;io.need(scope==self._input_scope(scope['stage']),'held_input_scope');self._source(scope,now)
        io.need(type(raw_base)is dict and set(raw_base)==set(self.h['inputs'])and all(type(v)is bytes and io.pin(v)==self.h['inputs'][k]['pin']for k,v in raw_base.items()),'held_base_raw')
        io.need(type(raw_history)is dict and set(raw_history)=={'reused_scores','stronger_envelope'}and [io.pin(v)for v in raw_history['reused_scores']]==scope['historical_pins']['reused_scores']and io.pin(raw_history['stronger_envelope'])==scope['historical_pins']['stronger_envelope'],'held_history_raw')
        claims,projection_raw=self._input_attestation(scope,raw_base,raw_history,now)
        self.receipt=dict(schema='root-L-bridge-input-authentication-v1',scope=copy.deepcopy(scope),decision='authorized',**claims,source_pins=scope['source_pins'],original_source_pins=scope['original_source_pins'],proof_pin=self.h['evidence']['inputs']['pin'])
        # Only independently authenticated held projection bytes are parsed.
        self.projection_held=io.json_read(projection_raw);io.need(type(self.projection_held)is dict and set(self.projection_held)=={'schema','joins','comparison_schema'}and self.projection_held['schema']=='root-L-held-comparator-joins-v1','held_projection_schema')
        return copy.deepcopy(self.receipt)

    def _input_attestation(self,scope,base,history,now):
        raw=self._evidence('inputs');projection_raw=self._evidence('projection')
        r=self.primitives.inputs(scope,copy.deepcopy(self.h),base,history,raw,projection_raw,now)
        claims=self._attest(r,'inputs',scope,self.h['evidence']['inputs']['pin']);self.io.need(claims==self.h['facts'],'independent_input_facts')
        return claims,projection_raw

    def authenticate_previous(self,scope,raw,receipt,now):
        io=self.io;io.need(receipt==self.receipt and scope['input_scope']==receipt['scope']and scope['stage']==receipt['scope']['stage'],'previous_input_subject')
        i=scope['stage']['index'];io.need(set(raw)=={str(n)for n in PRIOR[i]}and scope['previous_pins']=={n:io.pin(v)for n,v in raw.items()},'previous_roles')
        claims=[]
        for n,value in raw.items():
            entry=self.prior[int(n)];io.need(entry[1]['result.json']==value,'authenticated_previous_raw');claims.append(entry[0])
        proof=io.pin(io.canonical(dict(scope=scope,closures=claims)))
        self.previous_scope=copy.deepcopy(scope);self.previous_bytes=copy.deepcopy(raw)
        return dict(schema='root-L-bridge-previous-authentication-v1',scope=copy.deepcopy(scope),decision='authorized',proof_pin=proof)

    def project_comparators(self,scope,packet,six,stronger,closed,origins,receipt):
        io=self.io;io.need(receipt==self.receipt and scope==self._input_scope(scope['stage'])and self.loaded is not None,'projector_subject')
        a=self._comparison_modules();canonical=a['transport'].canonical;packet_digest=a['packet_digest'].sha;check_closed=a['l_auditor'].comparators_checked
        authority=dict(closed_comparator_report_sha256=self.g['input_pins']['closed_comparator_report']['sha256'],origins_sha256=self.g['input_pins']['comparator_origins']['sha256'])
        expected=dict(schema='root-held-L-comparator-projection-v1',scope=self._input_scope(scope['stage']),receipt=self.receipt,inputs=dict(reused_scores=scope['historical_pins']['reused_scores'],stronger_envelope=scope['historical_pins']['stronger_envelope'],closed_comparator_report=self.g['input_pins']['closed_comparator_report'],comparator_origins=self.g['input_pins']['comparator_origins']),joins=self.projection_held['joins'])
        # This contract is composed by ROOT from independently authenticated held
        # evidence and its captured clock, never from an unverified caller hash.
        def checked(report,origins,packet):return check_closed(report,origins,packet,self.projection_held['comparison_schema'],authority)
        project=self.projection.make_projector(expected,expected_pin=io.pin(canonical(expected)),canonical=canonical,packet_digest=packet_digest,validate_population=self.population.validate_comparators,check_closed=checked)
        return project(scope,packet,six,stronger,closed,origins,receipt)

    def _comparison_modules(self):
        io=self.io;io.need(self.loaded is not None,'active_cold_context')
        if self.loaded['mode']=='independent':return self.loaded['groups']['auditor']
        if self.comparison_group is None:
            # Reuse the already admitted full-auditor35 profile under the active
            # unchanged V6 guard. No new path whitelist or scientific source edit.
            runtime=self.modules['runtime_adapter'];specs=self.h['loader']['sources'];sb=self.modules['source_binding']
            raw=runtime._source(specs['auditor'],'auditor',io,sb,self.check)
            a=runtime._group('auditor',runtime.AUDIT_NAMES,self.h['launch']['prefix']+'_comparison',specs,{'auditor':raw},io,sb,self.check)
            np=self.loaded['groups']['native']['packet_io'].np
            for module in a.values():io.need(module.np is np,'comparison_numpy_identity')
            m=a['math_core']
            for name in('transport','packet_digest','packet','metrics'):io.need(a[name].need is m.need,'comparison_core_alias')
            io.need(a['packet'].array is m.array and a['packet'].summaries is m.summaries,'comparison_packet_alias')
            for name,targets in {'auditor':dict(core='math_core',pkt='packet',tx='transport',packet_digest='packet_digest',metrics='metrics'),'ar_core':dict(p='proper_core'),'l_auditor':dict(old='auditor',core='math_core',ar='ar_core',pkt='packet',packet_digest='packet_digest',tx='transport',metrics='metrics')}.items():
                for attr,target in targets.items():io.need(getattr(a[name],attr)is a[target],'comparison_auditor_alias')
            self.comparison_group=a
        return self.comparison_group

    def verify_audit_authority(self,scope,candidate,raw,receipt,now):
        io=self.io;io.need(receipt==self.receipt and scope==self.previous_scope and raw==self.previous_bytes and scope['stage']['index']in(6,7,8),'audit_input_subject')
        evidence=self._evidence('audit');r=self.primitives.audit(scope,copy.deepcopy(self.h),raw,receipt,copy.deepcopy(self.prior),evidence,now)
        claims=self._attest(r,'audit',scope,self.h['evidence']['audit']['pin'])
        io.need(set(claims)=={'authority'},'audit_claims');authority=claims['authority'];flags={'verified','native_verified','original_initialization_verified'}|({'optimizer_history_verified','gradient_probes_verified'}if scope['stage']['index']<8 else{'comparators_verified'})
        io.need(type(authority)is dict and set(authority)==set(candidate)|flags and all(authority[k]==v for k,v in candidate.items())and all(authority[k]is True for k in flags),'verified_exact_authority')
        return dict(schema='root-L-bridge-audit-verification-v1',scope=copy.deepcopy(scope),decision='authorized',authority=copy.deepcopy(authority),proof_pin=io.pin(io.canonical(r)))

    def launch(self,request):
        i=self._request(request);io=self.io;io.need(i not in self.launches,'launch_once');self.launches.add(i)
        io.need(self.issued.get((i,'parent'))==request['parent_authority'],'locally_issued_parent_authority')
        self.requests[i]=copy.deepcopy(request)
        io.need(self.journal.read(i,'dispatch.json')==io.canonical(request),'immutable_dispatch')
        launch=dict(schema='root-L-stage-bootstrap-v1',request=request,root_spec=self.root_spec)
        raw=io.canonical(launch);io.need(len(raw)<=512*1024,'bootstrap_control_cap');self.journal.write(i,'bootstrap.json',raw)
        path=self.h['launch']['store_directory']+'/stage_%02d/bootstrap.json'%i
        boot=self.h['launch']['bootstrap'];self._spec(boot,16*1024*1024);io.read_file(boot,16*1024*1024)
        # Bootstrap is opened component-by-component without symlink traversal.
        code=("import time;SOURCE_BEGIN=time.monotonic();import os,stat,hashlib;"
              "p=%r;d=os.open('/',os.O_RDONLY|os.O_DIRECTORY);"
              "exec(\"for n in p.split('/')[1:-1]:\\n q=os.open(n,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=d);os.close(d);d=q\");"
              "f=os.open(p.split('/')[-1],os.O_RDONLY|os.O_NOFOLLOW,dir_fd=d);os.close(d);"
              "s=os.fstat(f);assert stat.S_ISREG(s.st_mode)and stat.S_IMODE(s.st_mode)==256 and s.st_nlink==1;"
              "b=os.read(f,%d);os.close(f);assert len(b)==%d and hashlib.sha256(b).hexdigest()==%r;"
              "exec(compile(b,p,'exec'),dict(__name__='__main__',__file__=p,SOURCE_BEGIN=SOURCE_BEGIN,LAUNCH_PATH=%r,LAUNCH_PIN=%r))")%(boot['path'],boot['pin']['bytes']+1,boot['pin']['bytes'],boot['pin']['sha256'],path,io.pin(raw))
        io.need(len(code.encode())<=262144,'inline_launch_cap');self.check()
        return dict(python=self.h['launch']['python'],code=code,code_pin=io.pin(code.encode()),request_pin=io.pin(io.canonical(request)))


class Relay:
    def __init__(self,runtime,root):self.runtime=runtime;self.root=root
    @contextmanager
    def load(self,*args,**kwargs):
        with self.runtime.load(*args,**kwargs)as loaded:
            self.root.loaded=loaded
            try:yield loaded
            finally:self.root.loaded=None;self.root.comparison_group=None


def compose(root,*,bridge,runtime,systemd,stack):
    root.loaded=None;h=root.h
    return bridge.make_adapter(root.g,expected_config_pin=h['execution_pin'],input_specs=h['inputs'],historical_specs=h['history'],loader_config=h['loader'],expected_loader_config_pin=h['loader_pin'],io=root.io,sb=root.modules['source_binding'],runtime_adapter=Relay(runtime,root),control=root.c,systemd=systemd,trusted=root,stack=stack,check=root.check,source_begin=root.source_begin if root.source_begin is not None else root.g['whole_begin'],prefix=h['launch']['prefix'],python=h['launch']['python'],clock=root.clock)


def execute_child(held,request,*,expected_pin,root_spec,modules,primitives,custody,journal,systemd,source_begin,clock=time.monotonic):
    """ROOT calls after positively loading the exact supporting modules."""
    with ExitStack()as stack:
        root=Root(held,expected_pin=expected_pin,root_spec=root_spec,io=modules['secure_io'],control=modules['control'],projection=modules['projection'],population=modules['comparator_population'],primitives=primitives,custody=custody,journal=journal,modules=modules,source_begin=source_begin,clock=clock)
        root._request(request);root.active=request
        adapter=compose(root,bridge=modules['bridge'],runtime=modules['runtime_adapter'],systemd=systemd,stack=stack)
        result=modules['child'].execute(request,journal,adapter,expected_config_pin=held['execution_pin'],source_begin=source_begin,clock=clock)
        # Frozen child has persisted returned/full failure reports before here.
        root.check();return result


class ObservedSystemd:
    def __init__(self,systemd):self.systemd=systemd;self.answer=None
    def __getattr__(self,name):return getattr(self.systemd,name)
    def run(self,*args,**kwargs):
        self.answer=self.systemd.run(*args,**kwargs);return self.answer


def run_parent(held,index,*,expected_pin,root_spec,modules,primitives,custody,journal,systemd,retain_return,clock=time.monotonic):
    """Retain exact actual return/transport before any later stage may proceed.

    retain_return is ROOT's mandatory durable last-return custody operation; it
    must independently verify actual streams/OS cleanup/issued lease/inventory.
    It is called for failures too and grants no retry or stage advancement.
    """
    modules['secure_io'].need(callable(retain_return),'mandatory_root_retention')
    with ExitStack()as stack:
        root=Root(held,expected_pin=expected_pin,root_spec=root_spec,io=modules['secure_io'],control=modules['control'],projection=modules['projection'],population=modules['comparator_population'],primitives=primitives,custody=custody,journal=journal,modules=modules,clock=clock)
        observed=ObservedSystemd(systemd);adapter=compose(root,bridge=modules['bridge'],runtime=modules['runtime_adapter'],systemd=observed,stack=stack)
        result=root.c.run_stage(root.g,root.h['execution_pin'],index,journal,adapter,clock=clock)
        retained=retain_return(index,result,journal.inventory(),observed.answer,root.requests.get(index))
        io=root.io;io.need(type(retained)is dict and set(retained)=={'schema','stage','return_pin','proof_pin'}and retained['schema']=='root-L-last-return-retention-v1'and retained['stage']==index and retained['return_pin']==io.pin(io.canonical(result)),'retained_actual_return')
        io.pin_check(retained['proof_pin']);io.need(retained['proof_pin']['bytes']>0,'last_return_proof')
        request=root.requests.get(index);deadline=min(root.g['whole_begin']+7400,root.g['lease_deadline'])
        if request is not None:deadline=min(deadline,request['parent_authority']['expires'])
        if result['status']=='complete':
            claim=io.json_read(journal.read(index,'claim.json',result['claim_pin']));deadline=min(deadline,claim['authority']['expires'])
        if clock()>deadline:
            result['status']='incomplete';result['errors'].append('late_root_retention')
            if not journal.exists(index,'late_or_failed.json'):journal.object(index,'late_or_failed.json',result)
            raise ValueError('root_retention_deadline')
        return result

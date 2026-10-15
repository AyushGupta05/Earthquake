"""Concrete stdlib ROOT proof/custody primitives. No import-time IO or science.

External ROOT pins are the trust anchors. Receipt wrappers authenticate already
independently performed checks; they cannot manufacture native or optimizer truth.
All underlying raw receipts and actual manager custody remain required.
"""
import copy
import ast
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import marshal
import math
import os
import re
import stat
import struct
import sys
import time
import types
import uuid

CAP = 16 * 1024 * 1024
ROLES = {'operator','native_validator','reference','kernel','processor','protocol','numeric_state'}
OLD = {'operator','native_validator','reference','processor','protocol'}
SUBJECTS = dict(native={'feature_archive','feature_manifest','feature_authority'},
                initialization={'original_admission','original_admission_authority'},
                comparators={'closed_comparator_report','comparator_origins','comparator_authority'})
STATIC_SCOPE = ('experiment_id','whole_begin','lease_deadline','source_pins','runtime_pin',
                'input_pins','protocol_pin','storage_limit_bytes','study')


def keys(io, value, names, why):
    io.need(type(value) is dict and set(value) == set(names), why)


def finite(io, x, why):
    io.need(type(x) in (int,float) and math.isfinite(x), why)
    return x


def owned_read(io, spec, cap=CAP):
    keys(io,spec,('path','pin','mode'),'readonly_spec')
    io.need(type(spec['mode']) is int and spec['mode'] == 0o400,'readonly_mode')
    io.pin_check(spec['pin'],cap);io.need(spec['pin']['bytes']>0,'positive_spec')
    names=io.parts(spec['path'],True)
    d=io.directory('/'+'/'.join(names[:-1])) if len(names)>1 else os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        s=os.stat(names[-1],dir_fd=d,follow_symlinks=False)
        io.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.geteuid(),'readonly_owner')
        return io.read_at(d,names[-1],cap,0o400,spec['pin'])
    finally:os.close(d)


def parsed(io, raw, cap=CAP):
    value=io.json_read(raw,cap)
    io.need(io.canonical(value)==raw,'canonical_proof')
    return value


def read_object(io, spec, cap=CAP):
    return parsed(io,owned_read(io,spec,cap),cap)


def raw_receipt(io,spec,cap=CAP):
    """Retain original observation formatting; authenticate bytes, then parse.

    Only explicit external raw-receipt edges use this. New controls, wrappers,
    dossiers and scientific journals retain canonical encoding requirements.
    """
    return io.json_read(owned_read(io,spec,cap),cap)


def tree(io, directory, expected=None):
    """Complete flat journal inventory, no links, subdirectories or partial temps."""
    d=io.directory(directory);out={}
    try:
        s=os.fstat(d)
        io.need(s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700,'custody_directory')
        names=os.listdir(d);io.need(len(names)<=384,'custody_member_count')
        for name in names:
            io.need(re.fullmatch(r'[a-z0-9_]+\.json',name),'unfinished_or_unknown_member')
            s=os.stat(name,dir_fd=d,follow_symlinks=False)
            io.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.geteuid()
                    and stat.S_IMODE(s.st_mode)==0o400 and s.st_size<=CAP,'custody_member')
            raw=io.read_at(d,name,CAP,0o400)
            out[name]=io.pin(raw)
        io.need(sum(v['bytes'] for v in out.values())<=64*1024*1024,'custody_stage_bytes')
    finally:os.close(d)
    if expected is not None:io.need(out==expected,'complete_inventory')
    return out


def read_tree(io, directory, inventory):
    tree(io,directory,inventory)
    raw={name:owned_read(io,dict(path=directory+'/'+name,pin=p,mode=0o400)) for name,p in inventory.items()}
    tree(io,directory,inventory)
    io.need(not any(n in raw for n in ('late_or_failed.json','child_failure.json','child_late_or_failed.json','failure.json')),'failed_stage')
    return raw


def answer_wire(io, answer):
    if answer is None:return None
    keys(io,answer,('code','timeout','stdout','stderr','streams_complete','stream_custody','exception'),'actual_transport')
    io.need(type(answer['stdout']) is bytes and type(answer['stderr']) is bytes,'actual_stream_bytes')
    out=copy.deepcopy(answer)
    out['stdout']=answer['stdout'].hex();out['stderr']=answer['stderr'].hex()
    return out


def answer_unwire(io, value):
    keys(io,value,('code','timeout','stdout','stderr','streams_complete','stream_custody','exception'),'retained_transport')
    out=copy.deepcopy(value)
    for k,cap in (('stdout',65536),('stderr',131072)):
        io.need(type(value[k]) is str and re.fullmatch('[0-9a-f]*',value[k]) and len(value[k])<=2*cap,'retained_stream_hex')
        out[k]=bytes.fromhex(value[k])
    return out


def old_streams(io, value):
    keys(io,value,('code','exception','stderr','stdout','streams_complete','timeout'),'original_transport')
    io.need(type(value['code']) is int and value['code']==0 and value['timeout'] is False
            and value['streams_complete'] is True and value['exception'] is None,'original_transport_complete')
    for name,cap in (('stdout',65536),('stderr',131072)):
        s=value[name];keys(io,s,('original_pin','retained_hex','truncated'),'original_stream')
        io.need(s['truncated'] is False and type(s['retained_hex']) is str
                and re.fullmatch('[0-9a-f]*',s['retained_hex']) and len(s['retained_hex'])<=cap*2,'original_stream_complete')
        io.need(io.pin(bytes.fromhex(s['retained_hex']))==s['original_pin'],'original_full_stream_hash')


def saved_streams(io, control, value):
    keys(io,value,('code','exception','stderr','stdout','stream_custody','streams_complete','timeout'),'saved_transport')
    answer={k:copy.deepcopy(value[k]) for k in ('code','exception','stream_custody','streams_complete','timeout')}
    for name,cap in (('stdout',65536),('stderr',131072)):
        s=value[name];keys(io,s,('retained_hex','retained_pin','truncated'),'saved_stream')
        io.need(s['truncated'] is False and type(s['retained_hex']) is str
                and re.fullmatch('[0-9a-f]*',s['retained_hex']) and len(s['retained_hex'])<=cap*2,'saved_stream_complete')
        answer[name]=bytes.fromhex(s['retained_hex'])
        io.need(io.pin(answer[name])==s['retained_pin'],'saved_stream_pin')
    control.streams_checked(answer)
    io.need(type(answer['code']) is int and answer['code']==0 and answer['timeout'] is False
            and answer['streams_complete'] is True and answer['exception'] is None,'saved_transport_success')
    return answer


def post_checked(io, value, unit):
    keys(io,value,('active_state','control_group','result','unit'),'post_fields')
    io.need(value['unit']==unit and value['active_state'] in ('inactive','failed')
            and value['control_group']=='' and value['result']=='success','post_cleanup')


def live_boot(module):
    return module.live_read('/proc/sys/kernel/random/boot_id',128).decode('ascii').strip()


def monotonic_seconds(io,value):
    io.need(type(value) is str and re.fullmatch(r'(?:[0-9]+(?:\.[0-9]+)?(?:us|ms|s|min|h|d|w)(?: |$))+',value),'monotonic_duration')
    factors={'us':Decimal('.000001'),'ms':Decimal('.001'),'s':1,'min':60,'h':3600,'d':86400,'w':604800}
    return float(sum((Decimal(n)*factors[u] for n,u in re.findall(r'([0-9]+(?:\.[0-9]+)?)(us|ms|s|min|h|d|w)',value)),Decimal(0)))


def _code_map(code):
    return {c.co_name:c for c in code.co_consts if isinstance(c,types.CodeType)}


def module_code(io,module,raw):
    """Check executed top-level functions/classes against authenticated source.

    Runtime aliases are checked separately by the frozen dependency verifier.
    Do not execute a second copy of a source module merely to check its code.
    """
    compiled=_code_map(compile(raw,module.__file__,'exec'))
    def checked(value,expected):
        io.need(isinstance(value,types.FunctionType),'loaded_source_function')
        if hasattr(value,'__wrapped__'):
            wrapped=value.__wrapped__
            io.need(isinstance(wrapped,types.FunctionType) and any(c.cell_contents is wrapped for c in value.__closure__ or ())
                    and marshal.dumps(value.__code__)==marshal.dumps(contextmanager(wrapped).__code__),'wrapped_function_binding')
            value=wrapped
        io.need(value.__globals__ is vars(module),'loaded_function_globals')
        io.need(marshal.dumps(value.__code__)==marshal.dumps(expected),'loaded_function_code')
    # Walk source declarations, not just currently retained module members: a
    # foreign replacement or deleted validator must fail rather than be skipped.
    for node in ast.parse(raw,module.__file__).body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            checked(vars(module).get(node.name),compiled[node.name])
        elif isinstance(node,ast.ClassDef):
            value=vars(module).get(node.name)
            io.need(isinstance(value,type) and value.__module__==module.__name__,'loaded_source_class')
            methods=_code_map(compiled[node.name])
            for method in node.body:
                if not isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
                member=vars(value).get(method.name)
                if isinstance(member,(staticmethod,classmethod)):member=member.__func__
                if isinstance(member,property):member=member.fget
                checked(member,methods[method.name])


class Custody:
    """Read-only access to independently persisted actual parent returns."""
    def __init__(self,primitives):self.p=primitives
    def dossier(self,index):
        p=self.p;io=p.io;io.need(type(index) is int and 0<=index<9,'custody_stage')
        directory=p.current_doc['retention_directory'];fd=io.directory(directory)
        try:
            s=os.fstat(fd);io.need(s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700,'root_custody_directory')
            names=os.listdir(fd)
            io.need(all(n=='.root.lock' or re.fullmatch(r'stage_0[0-8]\.json',n) for n in names),'root_custody_unfinished')
            raw=io.read_at(fd,'stage_%02d.json'%index,1024*1024,0o400)
        finally:os.close(fd)
        doc=parsed(io,raw,1024*1024)
        keys(io,doc,('schema','known','files','observed','request','retained_at','boot_id','root_post','root_post_transport'),'retained_dossier')
        io.need(doc['schema']=='root-L-retained-stage-v1' and doc['boot_id']==p.boot,'retained_boot')
        known=doc['known'];keys(io,known,('schema','stage','config_pin','returned','inventory'),'known_return')
        io.need(known['schema']=='root-L-known-parent-return-v1' and known['stage']==index
                and known['config_pin']==p.h['execution_pin'],'known_subject')
        p.verify_new(doc,index)
        return doc
    def snapshot(self,index):
        doc=self.dossier(index);raw=self.p.io.canonical(doc['known'])
        self.p.io.need(len(raw)<=1024*1024,'known_cap')
        return dict(known_raw=raw,known_pin=self.p.io.pin(raw),files=copy.deepcopy(doc['files']),inventory=copy.deepcopy(doc['known']['inventory']))


class Primitives:
    def __init__(self,held,*,expected_root_pin,root_spec,modules,source_begin=None,clock=time.monotonic):
        self.io=modules['secure_io'];io=self.io
        io.need(root_spec['pin']==expected_root_pin and owned_read(io,root_spec,2*1024*1024)==io.canonical(held),'external_root_anchor')
        self.h=copy.deepcopy(held);self.modules=modules;self.clock=clock;self.source_begin=source_begin
        self.root_pin=copy.deepcopy(expected_root_pin)
        self.g=self.h['execution'];self.c=modules['control'];self.c.config_check(self.g,clock(),self.h['execution_pin'])
        self.sr=self.evidence('source_runtime','root-L-source-runtime-proof-v1')
        keys(io,self.sr,('schema','execution_pin','loader_pin','runtime_spec_pin','source_pins','boot_id'),'source_proof_fields')
        self.boot=self.sr['boot_id'];io.need(type(self.boot) is str and re.fullmatch('[0-9a-f-]{36}',self.boot),'boot_uuid')
        self.current_doc=self.evidence('current','root-L-current-proof-v1')
        keys(io,self.current_doc,('schema','execution_pin','boot_id','expires','retention_directory','timer','resources','storage'),'current_proof_fields')
        io.parts(self.current_doc['retention_directory'],True)
        io.need(self.current_doc['retention_directory']!=self.h['launch']['store_directory'] and not self.current_doc['retention_directory'].startswith(self.h['launch']['store_directory']+'/'),'separate_root_custody')
        self.inputs_verified=False;self.verified_input_pin=None;self.custody=Custody(self)
        self.runtime_seal=None;self.input_seal=None;self.input_paths=set()
        self.input_directories={};self.input_profiles=[]

    def evidence(self,name,schema,raw=None):
        spec=self.h['evidence'][name];held=owned_read(self.io,spec)
        if raw is not None:self.io.need(raw==held,'held_evidence_bytes')
        value=parsed(self.io,held);self.io.need(value.get('schema')==schema,'evidence_schema')
        return value
    def check(self,now=None,closure=False):
        io=self.io;now=self.clock() if now is None else now
        self.c.config_check(self.g,now,self.h['execution_pin'])
        io.need(self.g['whole_begin']<=now<=min(self.g['whole_begin']+(7400 if closure else 7200),self.g['lease_deadline']),'whole_deadline')
        io.need(live_boot(self.modules['systemd_adapter'])==self.boot,'same_boot')
        return now
    def subject(self,held,scope,now):
        self.io.need(held==self.h,'held_composition');self.check(now)
        if scope.get('schema')=='shared-reference-AR-L-stage-scope-v1':
            i=scope['stage']['index'];self.io.need(scope==self.c.scope(self.g,self.c.spec(self.g,i),scope['phase']),'exact_stage_scope')
        elif scope.get('schema')=='root-L-composition-scope-v1':
            self.io.need(scope==dict(schema='root-L-composition-scope-v1',root_pin=self.io.pin(self.io.canonical(self.h)),execution_pin=self.h['execution_pin'],loader_pin=self.h['loader_pin']),'root_scope')
        elif scope.get('schema')=='L-bridge-input-scope-v1':
            keys(self.io,scope,('schema','config_pin','stage','unit','mode','source_begin','loader_config_pin','input_pins','historical_pins','source_pins','original_source_pins'),'input_scope_fields')
            i=scope['stage']['index'];self.io.need(scope['config_pin']==self.h['execution_pin'] and scope['loader_config_pin']==self.h['loader_pin'] and scope['stage']==self.c.spec(self.g,i) and scope['input_pins']==self.g['input_pins']
                and scope['unit']==scope['stage']['unit'] and scope['mode']==('producer' if i<6 else 'independent')
                and self.g['whole_begin']<=finite(self.io,scope['source_begin'],'source_begin')<=now
                and scope['historical_pins']==dict(reused_scores=[v['spec']['pin'] for v in self.h['history']['reused_scores']],stronger_envelope=self.h['history']['stronger_envelope']['pin'])
                and scope['source_pins']=={k:self.g['source_pins'][k] for k in ROLES}
                and scope['original_source_pins']==self.h['loader']['original_source_pins'],'input_scope')
        elif scope.get('schema')=='root-L-prior-scope-v1':
            self.io.need(set(scope) in ({'schema','root_scope','stage','closed_pin'},{'schema','root_scope','stage','request_pin','result_pin'}),'prior_scope_fields')
            self.c.spec(self.g,scope['stage'])
            self.subject(held,scope['root_scope'],now)
        elif scope.get('schema')=='L-bridge-audit-scope-v1':
            keys(self.io,scope,('schema','input_scope','stage','previous_pins'),'audit_scope_fields')
            self.subject(held,scope['input_scope'],now)
            self.io.need(scope['stage']==scope['input_scope']['stage'],'audit_scope_stage')
        else:self.io.need(False,'primitive_scope')
    def attest(self,kind,scope,claims,pin=None):
        return dict(schema='root-L-primitive-verification-v1',kind=kind,scope_pin=self.io.pin(self.io.canonical(scope)),evidence_pin=copy.deepcopy(pin or self.h['evidence'][kind]['pin']),claims=copy.deepcopy(claims))

    def seal(self,paths):
        out={}
        for path in sorted(paths):
            names=self.io.parts(path,True);d=self.io.directory('/'+'/'.join(names[:-1]))
            try:s=os.stat(names[-1],dir_fd=d,follow_symlinks=False)
            finally:os.close(d)
            self.io.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'sealed_regular_file')
            out[path]=(s.st_dev,s.st_ino,s.st_size,s.st_mode,s.st_uid,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
        return out

    def runtime_paths(self):
        io=self.io;r=self.h['loader']['runtime'];sb=self.modules['source_binding']
        files,links,_=sb.inventory(r['directory']+'/venv',True)
        paths={r['directory']+'/venv/'+n for n in files}
        paths.update(r['critical'])
        for k in ('manifest','symlinks','vendor_inventory','generated_source','metadata_finder'):
            spec=r[k]
            if type(spec) is dict and set(spec)=={'path','pin','mode'}:paths.add(spec['path'])
        vendor=io.json_read(io.read_file(r['vendor_inventory']))
        paths.update(vendor['files']);paths.update(v['path'] for v in vendor['records'].values())
        return paths,links

    def source_runtime(self,scope,held,graph,raw,now):
        io=self.io;self.subject(held,scope,now);d=self.evidence('source_runtime','root-L-source-runtime-proof-v1',raw)
        io.need(d==self.sr and d['execution_pin']==self.h['execution_pin'] and d['loader_pin']==self.h['loader_pin']
                and d['runtime_spec_pin']==io.pin(io.canonical(self.h['loader']['runtime']))
                and d['source_pins']==self.g['source_pins'],'source_subjects')
        keys(io,graph,('support','scientific'),'module_graph');support=graph['support']
        io.need(support is self.modules,'held_support_graph')
        if graph['scientific'] is not None:io.need(self.inputs_verified,'raw_authentication_before_numerics')
        else:io.need(not any(n=='numpy' or n.startswith('numpy.') or n=='torch' or n.startswith('torch.') for n in sys.modules),'preloaded_numerics')
        adapter=support['runtime_adapter'];sb=support['source_binding'];loader=self.h['loader'];specs=loader['sources']
        io.need(io.pin(io.canonical(loader))==self.h['loader_pin'],'loader_pin')
        raw_sources={role:adapter._source(spec,role,io,sb,self.check) for role,spec in specs.items()}
        adapter._injected(loader,io,sb);adapter._copies(raw_sources,io)
        io.need(adapter._roles(loader,raw_sources,io)=={k:self.g['source_pins'][k] for k in ROLES},'semantic_sources')
        for role,profile in (('auditor','auditor'),('executor','executor'),('adapters','bootstrap')):
            io.need(self.g['source_pins'][role]==specs[profile]['manifest']['pin'],'support_semantic_subject')
        for name,module in support.items():
            io.need(isinstance(module,types.ModuleType) and type(getattr(module,'__file__',None)) is str,'support_module')
            spec=dict(path=module.__file__,pin=io.pin(b'x'),mode=0o400)
            matches=[(role,n) for role,s in specs.items() for n in s['files'] if s['directory']+'/'+n==module.__file__]
            io.need(len(matches)==1,'support_profile_member');role,n=matches[0]
            module_code(io,module,raw_sources[role][n])
        io.need(io.pin(io.canonical(loader['runtime']))==self.g['runtime_pin'],'runtime_semantic_subject')
        if self.runtime_seal is None:
            sb.runtime(loader['runtime'],self.check)
            paths,links=self.runtime_paths();self.runtime_seal=(self.seal(paths),links)
        else:
            paths,links=self.runtime_paths()
            io.need((self.seal(paths),links)==self.runtime_seal,'verified_runtime_mutation')
        sb.interpreter_check(loader['runtime'])
        if graph['scientific'] is not None:
            loaded=graph['scientific'];mode=loaded['mode'];g=loaded['groups'];np=g['native']['packet_io'].np
            torch=g['processor']['processor'].torch if mode=='producer' else None
            adapter._identities(mode,g,np,torch,io)
            if mode=='independent':adapter._independent_clean(specs,io)
        self.check()
        return self.attest('source_runtime',scope,dict(source=io.pin(io.canonical(self.g['source_pins'])),runtime=self.g['runtime_pin']))

    def show(self,unit,names):
        io=self.io;io.need(type(unit) is str and re.fullmatch(r'[a-zA-Z0-9_.@-]{1,200}',unit),'held_unit')
        command=self.h['launch']['commands']['systemctl'];io.read_file(command)
        answer=self.modules['systemd_adapter'].process([command['path'],'--user','show',unit]+sum((['-p',n] for n in names),[]),5)
        self.c.streams_checked(answer)
        io.need(type(answer['code']) is int and answer['code']==0 and answer['timeout'] is False and answer['streams_complete'] is True,'live_property_transport')
        self.last_show=copy.deepcopy(answer)
        return self.modules['systemd_adapter'].properties(answer['stdout'],names)

    def current(self,scope,held,documents,raw,now):
        io=self.io;self.subject(held,scope,now);d=self.evidence('current','root-L-current-proof-v1',raw)
        io.need(d==self.current_doc and d['execution_pin']==self.h['execution_pin'] and d['boot_id']==self.boot,'current_subject')
        keys(io,documents,('funding','publication','protocol','root_context'),'document_roles')
        for name,spec in self.h['documents'].items():io.need(owned_read(io,spec)==documents[name],'actual_document')
        funding=parsed(io,documents['funding']);publication=parsed(io,documents['publication'])
        static={k:self.g[k] for k in STATIC_SCOPE}
        keys(io,funding,('schema','scope','expires','task_ceiling_cents','reservation_cents','spent_upper_cents','future_upper_cents','eligible_credit_cents','other_reserved_cents','eligibility'),'funding_fields')
        io.need(funding['schema']=='root-L-funding-reservation-v1' and funding['scope']==static,'funding_subject')
        for k in ('task_ceiling_cents','reservation_cents','spent_upper_cents','future_upper_cents','eligible_credit_cents','other_reserved_cents'):io.need(type(funding[k]) is int and funding[k]>=0,'integer_cents')
        io.need(0<funding['reservation_cents']<=45000 and funding['reservation_cents']<=funding['task_ceiling_cents']<=200000
                and funding['spent_upper_cents']+funding['future_upper_cents']<=funding['reservation_cents']
                and funding['eligible_credit_cents']-funding['other_reserved_cents']>=funding['future_upper_cents'],'funding_reservation')
        keys(io,publication,('schema','scope','expires'),'publication_fields')
        io.need(publication['schema']=='root-L-publication-authority-v1' and publication['scope']==static,'publication_subject')
        expires=min(finite(io,d['expires'],'expiry'),finite(io,funding['expires'],'expiry'),finite(io,publication['expires'],'expiry'),self.g['lease_deadline'])
        resources=read_object(io,d['resources']);storage=read_object(io,d['storage'])
        keys(io,resources,('schema','execution_pin','boot_id','whole_begin','science_deadline','closure_deadline','expires','limits','quota'),'resource_fields')
        io.need(resources['schema']=='root-L-resource-reservation-v1' and resources['execution_pin']==self.h['execution_pin'] and resources['boot_id']==self.boot
                and resources['whole_begin']==self.g['whole_begin'] and resources['science_deadline']==self.g['whole_begin']+7200
                and resources['closure_deadline']==self.g['whole_begin']+7400 and resources['limits']==self.c.LIMITS,'resource_subject')
        expires=min(expires,finite(io,resources['expires'],'expiry'))
        eligibility=read_object(io,funding['eligibility'])
        keys(io,eligibility,('schema','scope','expires','eligible_services','raw_credit_readback'),'credit_window_fields')
        io.need(eligibility['schema']=='root-L-credit-window-v1' and eligibility['scope']==static
                and type(eligibility['eligible_services']) is list and 'Amazon Elastic Compute Cloud' in eligibility['eligible_services'],'eligible_credit_service')
        # ROOT independently validates provider-specific credit terms. Preserve
        # that exact raw record; do not infer an account balance from a flag.
        credit_raw=raw_receipt(io,eligibility['raw_credit_readback'])
        io.need(type(credit_raw) is dict and credit_raw.get('schema')=='root-live-eligible-credit-refresh-v1','raw_credit_readback')
        quota=read_object(io,resources['quota'])
        keys(io,quota,('schema','scope','expires','limit_vcpu','used_vcpu','additional_vcpu','resource_readback'),'quota_window_fields')
        io.need(quota['schema']=='root-L-quota-window-v1' and quota['scope']==static and type(quota['limit_vcpu']) is int
                and quota['limit_vcpu']==16 and type(quota['used_vcpu']) is int and quota['used_vcpu']>=0
                and type(quota['additional_vcpu']) is int and quota['additional_vcpu']==0,'cpu_only_quota_scope')
        resource_raw=raw_receipt(io,quota['resource_readback'])
        keys(io,resource_raw,('checked_utc','no_resource_start_or_change','raw','schema'),'provider_resource_fields')
        io.need(resource_raw['schema']=='root-scoped-aws-readonly-refresh-v1' and resource_raw['no_resource_start_or_change'] is True,'readonly_resource_receipt')
        provider=resource_raw['raw'];keys(io,provider,('account','instances','owned_volumes','quota','running_G_VT'),'provider_resource_roles')
        io.need(provider['quota']['Quota']['Value']==16,'raw_quota16')
        usage=provider['running_G_VT'];io.need(type(usage) is dict and not usage.get('NextToken') and type(usage.get('Reservations')) is list,'complete_running_usage')
        used=0
        for reservation in usage['Reservations']:
            io.need(type(reservation.get('Instances')) is list,'usage_instances')
            for instance in reservation['Instances']:
                if instance['State']['Name'] not in ('running','pending'):continue
                io.need(re.fullmatch(r'(?:g|vt)[0-9][a-z0-9-]*\.[a-z0-9]+',instance['InstanceType']),'quota_instance_family')
                cpu=instance['CpuOptions'];io.need(type(cpu['CoreCount']) is int and cpu['CoreCount']>0 and type(cpu['ThreadsPerCore']) is int and cpu['ThreadsPerCore']>0,'raw_vcpu')
                used+=cpu['CoreCount']*cpu['ThreadsPerCore']
        io.need(used==quota['used_vcpu'] and used+quota['additional_vcpu']<=quota['limit_vcpu'],'shared_quota_readback')
        expires=min(expires,finite(io,eligibility['expires'],'expiry'),finite(io,quota['expires'],'expiry'))
        io.need(now<expires and (scope['phase']!='parent' or now+scope['stage']['manager_seconds']<=expires),'current_expiry')
        keys(io,storage,('schema','execution_pin','directory','reserved_bytes','minimum_free_bytes'),'storage_fields')
        io.need(storage['schema']=='root-L-storage-reservation-v1' and storage['execution_pin']==self.h['execution_pin'] and storage['directory']==self.h['launch']['store_directory']
                and type(storage['reserved_bytes']) is int and storage['reserved_bytes']==self.g['storage_limit_bytes']
                and type(storage['minimum_free_bytes']) is int and storage['minimum_free_bytes']>=storage['reserved_bytes'],'storage_reservation')
        fd=io.directory(storage['directory'])
        try:v=os.fstatvfs(fd);io.need(v.f_bavail*v.f_frsize>=storage['minimum_free_bytes'],'live_storage_free')
        finally:os.close(fd)
        timer=d['timer'];keys(io,timer,('unit','service','exec_start','deadline'),'timer_fields')
        deadline=finite(io,timer['deadline'],'timer_deadline')
        io.need(now<deadline<=min(self.g['whole_begin']+7400,self.g['lease_deadline']),'installed_whole_stop')
        props=self.show(timer['unit'],('ActiveState','Unit','NextElapseUSecMonotonic'))
        io.need(props['ActiveState']=='active' and props['Unit']==timer['service']
                and abs(monotonic_seconds(io,props['NextElapseUSecMonotonic'])-deadline)<=1e-6,'live_timer')
        expires=min(expires,deadline)
        io.need(now<expires and (scope['phase']!='parent' or now+scope['stage']['manager_seconds']<=expires),'installed_stop_stage_cover')
        service=self.show(timer['service'],('ExecStart','LoadState'))
        io.need(service['LoadState']=='loaded' and service['ExecStart']==timer['exec_start'] and bool(timer['exec_start']),'live_stop_service')
        if scope['phase']=='parent':
            sd=self.modules['systemd_adapter'].Systemd(self.h['launch']['commands'])
            for i in range(scope['stage']['index'],9):sd.own(self.c.spec(self.g,i)['unit']);sd.available(self.c.spec(self.g,i)['unit'])
        self.check()
        return self.attest('current',scope,dict(expires=expires,resources=d['resources']['pin'],storage=d['storage']['pin']))

    def historical(self,proof):
        io=self.io;old=read_object(io,proof['original_execution'])
        keys(io,old,('TEST_opened','bootstrap_source_pin','controller_source_pin','deployment_config_pin','gate_sha256','schema','source_commit','stages'),'old14_fields')
        io.need(old['schema']=='root-marked-original-fourteen-execution-v1' and old['TEST_opened'] is False and type(old['stages']) is list and len(old['stages'])==14,'old14_identity')
        io.need(proof['original_execution']['pin']['sha256']==self.h['facts']['original_execution_closure_sha256'],'original_closure_identity')
        self.input_paths.add(proof['original_execution']['path'])
        for index,entry in enumerate(old['stages']):
            self.check();keys(io,entry,('directory','files','index','last_return','unit'),'old14_stage')
            io.need(type(entry['index']) is int and entry['index']==index,'old14_order')
            raw=read_tree(io,entry['directory'],entry['files']);closed=parsed(io,raw['closed.json']);child=parsed(io,raw['child_report.json'])
            self.input_paths.update(entry['directory']+'/'+name for name in entry['files'])
            self.input_directories[entry['directory']]=copy.deepcopy(entry['files'])
            io.need(closed==entry['last_return'] and closed['schema']=='marked-sixfit-parent-return-v1' and closed['index']==index and closed['unit']==entry['unit'] and closed['gate_sha256']==old['gate_sha256'],'old14_actual_return')
            io.need(closed['status']=='complete' and closed['cleanup_verified'] is True and closed['errors']==[] and closed['no_retry'] is True,'old14_complete')
            io.need(io.pin(raw['child_report.json'])==closed['report_pin'] and io.pin(raw['result.json'])==closed['result_pin']
                    and child['status']=='complete' and child['index']==index and child['gate_sha256']==old['gate_sha256'] and child['within_source'] is True and child['within_experiment'] is True
                    and child['result_pin']==closed['result_pin'],'old14_child_chain')
            old_streams(io,parsed(io,raw['manager_return.json']));post_checked(io,parsed(io,raw['post.json']),entry['unit'])
            bootstrap=parsed(io,raw['bootstrap.json']);keys(io,bootstrap,('config','expected_deployment_config_pin','request','schema'),'old_bootstrap_fields')
            request=bootstrap['request'];gate=request['gate'];original=self.h['loader']['original_source_pins'];config=bootstrap['config']
            io.need(bootstrap['schema']=='marked-stage-launch-v1' and bootstrap['expected_deployment_config_pin']==old['deployment_config_pin']
                    and io.pin(io.canonical(config))==old['deployment_config_pin'] and raw['claim.json']==io.canonical(request)
                    and child['request_pin']==io.pin(io.canonical(request)) and request['schema']=='marked-sixfit-stage-request-v1','old_bootstrap_request')
            parent=config['sources']['parent']
            io.need(old['controller_source_pin']==parent['files']['controller.py'] and old['bootstrap_source_pin']==config['bootstrap']['pin'],'historical_source_subjects')
            io.need(io.pin(io.canonical(gate))['sha256']==old['gate_sha256'] and gate['source_pins']==dict(processor=original['processor'],operator=original['operator'],native=original['native_validator'],reference=original['reference'],protocol=original['protocol'],parent=parent['manifest']['pin']),'original_source_edges')
            if index==0:
                # Exact original32 parent profile; preserve the old subject/count.
                self.modules['source_binding'].source(parent,'parent',self.check)
                self.input_paths.update(parent['directory']+'/'+n for n in parent['files'])
                self.input_profiles.append(copy.deepcopy(parent))
            if index==0:io.need(io.pin(raw['result.json'])==self.g['input_pins']['original_admission'],'archived_original_admission')
            if index in (2,4,6,8,10,12):io.need(io.pin(raw['result.json'])==self.h['history']['reused_scores'][index//2-1]['spec']['pin'],'archived_score_origin')
        io.need(type(proof['independent_returns']) is list and len(proof['independent_returns'])==7,'closed7_count')
        for index,spec in enumerate(proof['independent_returns']):
            self.check();entry=read_object(io,spec)
            self.input_paths.add(spec['path'])
            keys(io,entry,('config_pin','directory','files','inventory','last_return','root_manager','root_observation','schema','stage'),'audit7_root_fields')
            io.need(entry['schema']=='root-seven-audit-last-return-v1' and type(entry['stage']) is int and entry['stage']==index,'audit7_order')
            raw=read_tree(io,entry['directory'],entry['inventory']);closed=parsed(io,raw['closed.json']);child=parsed(io,raw['child_report.json'])
            self.input_paths.update(entry['directory']+'/'+name for name in entry['inventory'])
            self.input_directories[entry['directory']]=copy.deepcopy(entry['inventory'])
            io.need(closed==entry['last_return'] and closed['schema']=='marked-seven-audit-manager-return-v1' and closed['stage']==index and closed['config_pin']==entry['config_pin']
                    and closed['status']=='complete' and closed['cleanup_verified'] is True and closed['errors']==[] and closed['no_retry'] is True,'audit7_actual_return')
            for role,name in dict(claim='claim.json',closed='closed.json',report='raw_report_000.json',return_='return.json').items():
                key='return' if role=='return_' else role;io.need(owned_read(io,entry['files'][key])==raw[name],'audit7_file_subject')
            io.need(io.pin(raw['child_report.json'])==closed['child_report_pin'] and io.pin(raw['raw_report_000.json'])==closed['report_pin'] and io.pin(raw['return.json'])==closed['return_pin']
                    and child['status']=='complete' and child['stage']==index and child['within_source'] is True and child['config_pin']==entry['config_pin']
                    and child['request_pin']==io.pin(raw['dispatch.json']) and child['claim_pin']==io.pin(raw['claim.json']),'audit7_child_chain')
            saved_streams(io,self.c,parsed(io,raw['manager_return.json']))
            post_checked(io,parsed(io,raw['post.json']),closed['unit']);post_checked(io,entry['root_observation'],closed['unit'])
            # ROOT's independent manager leg must itself have full observed-stream custody.
            saved_streams(io,self.c,entry['root_manager'])
            report=parsed(io,raw['raw_report_000.json']);io.need(report.get('status')=='pass','independent_report_pass')
            if index<6:
                pair=[(s,a) for s in (20261012,20261013) for a in ('S','P','D')][index]
                io.need(report['schema']=='marked-sixfit-independent-audit-v1' and report['checked']==66 and len(report['records'])==66 and (report['seed'],report['arm'])==pair,'old_independent66')
            else:io.need(io.pin(raw['raw_report_000.json'])==self.g['input_pins']['closed_comparator_report'],'full924_report_origin')
        return old

    def check_input_seal(self):
        # Existing inode seals cannot detect an additional failure/temp member.
        # Recheck complete flat inventories and the old closed source profile.
        for directory,inventory in self.input_directories.items():tree(self.io,directory,inventory)
        for profile in self.input_profiles:self.modules['source_binding'].source(profile,'parent',self.check)
        self.io.need(self.seal(self.input_paths)==self.input_seal,'authenticated_input_custody_mutation')

    def inputs(self,scope,held,base,history,raw,projection,now):
        io=self.io;self.subject(held,scope,now);proof=self.evidence('inputs','root-L-input-proof-v1',raw)
        keys(io,proof,('schema','execution_pin','loader_pin','facts','projection_pin','original_execution','independent_returns','native_receipt','initialization_receipt','comparator_receipt'),'input_proof_fields')
        io.need(proof['execution_pin']==self.h['execution_pin'] and proof['loader_pin']==self.h['loader_pin'] and proof['facts']==self.h['facts']
                and proof['projection_pin']==self.h['evidence']['projection']['pin'] and owned_read(io,self.h['evidence']['projection'])==projection,'input_proof_subject')
        keys(io,base,self.c.INPUTS,'base_roles')
        for name,value in base.items():io.need(type(value) is bytes and owned_read(io,self.h['inputs'][name])==value and io.pin(value)==self.g['input_pins'][name],'held_raw_input')
        keys(io,history,('reused_scores','stronger_envelope'),'history_roles')
        io.need(type(history['reused_scores']) is list and len(history['reused_scores'])==6,'history_count')
        for raw_score,entry in zip(history['reused_scores'],self.h['history']['reused_scores']):io.need(raw_score==owned_read(io,entry['spec']),'historical_raw_score')
        io.need(history['stronger_envelope']==owned_read(io,self.h['history']['stronger_envelope']),'stronger_raw')
        report=parsed(io,base['closed_comparator_report']);origins=parsed(io,base['comparator_origins'])
        io.need(report['schema']=='marked-sixfit-independent-aggregate-v1' and report['status']=='pass'
                and len(report['fits'])==6 and len(report['stronger'])==8
                and sum(len(v['records']) for v in report['fits'])==396
                and sum(len(v['records']) for v in report['stronger'])==528 and type(origins) is list and len(origins)==14,'complete924_and_origins')
        if self.input_seal is not None:
            self.check_input_seal()
            self.check();return self.attest('inputs',scope,self.h['facts'])
        self.historical(proof)
        new={k:self.g['source_pins'][k] for k in ROLES};old=self.h['loader']['original_source_pins']
        for kind,names in SUBJECTS.items():
            receipt=read_object(io,proof[{'native':'native_receipt','initialization':'initialization_receipt','comparators':'comparator_receipt'}[kind]])
            self.input_paths.add(proof[{'native':'native_receipt','initialization':'initialization_receipt','comparators':'comparator_receipt'}[kind]]['path'])
            keys(io,receipt,('schema','subjects','source_pins','original_source_pins','closure'),'input_receipt')
            subjects={k:self.g['input_pins'][k] for k in names}
            io.need(receipt['schema']=='root-L-held-'+kind+'-receipt-v1' and receipt['subjects']==subjects and receipt['source_pins']==new and receipt['original_source_pins']==old,'input_receipt_subject')
            closure=read_object(io,receipt['closure'])
            self.input_paths.add(receipt['closure']['path'])
            keys(io,closure,('schema','kind','subjects','source_pins','original_source_pins','packet_sha256','original_execution_closure_sha256','evidence'),'input_closure_fields')
            io.need(closure['schema']=='root-L-independent-input-check-v1' and closure['kind']==kind and closure['subjects']==subjects and closure['source_pins']==new
                    and closure['original_source_pins']==old and all(closure[k]==v for k,v in self.h['facts'].items()),'input_closure_subject')
            io.need(type(closure['evidence']) is dict and closure['evidence'],'actual_raw_check_evidence')
            for spec in closure['evidence'].values():raw_receipt(io,spec);self.input_paths.add(spec['path'])
            if kind=='initialization':io.need(closure['evidence'].get('original_execution')==proof['original_execution'],'original_execution_receipt_edge')
        self.input_seal=self.seal(self.input_paths)
        self.inputs_verified=True;self.verified_input_pin=self.h['evidence']['inputs']['pin'];self.check()
        return self.attest('inputs',scope,self.h['facts'])

    def verify_new(self,doc,index):
        io=self.io;c=self.c;g=self.g;known=doc['known'];closed=known['returned'];request=doc['request'];s=c.spec(g,index)
        io.need(doc['boot_id']==self.boot and known['config_pin']==self.h['execution_pin'],'new_custody_scope')
        io.need(type(doc['files']) is dict and doc['files'],'new_files')
        directory=self.h['launch']['store_directory']+'/stage_%02d'%index
        inventory={name:spec['pin'] for name,spec in doc['files'].items()}
        for name,spec in doc['files'].items():io.need(spec['path']==directory+'/'+name,'stage_file_path')
        raw=read_tree(io,directory,inventory)
        io.need(closed==parsed(io,raw['closed.json']) and closed['schema']=='shared-reference-AR-L-parent-return-v1'
                and closed['stage']==index and closed['unit']==s['unit'] and closed['config_pin']==self.h['execution_pin']
                and closed['status']=='complete' and closed['cleanup_verified'] is True and closed['errors']==[] and closed['no_retry'] is True,'actual_new_return')
        io.need(request==parsed(io,raw['dispatch.json']) and request['config']==g and request['config_pin']==self.h['execution_pin'] and request['stage']==s,'actual_new_dispatch')
        child=parsed(io,raw['child_report.json']);claim=parsed(io,raw['claim.json'])
        io.need(io.pin(raw['child_report.json'])==closed['child_report_pin'] and io.pin(raw['claim.json'])==closed['claim_pin'] and io.pin(raw['result.json'])==closed['result_pin']
                and child['status']=='complete' and child['stage']==index and child['config_pin']==self.h['execution_pin'] and child['request_pin']==io.pin(raw['dispatch.json'])
                and child['within_source'] is True and child['within_experiment'] is True and child['claim_pin']==closed['claim_pin'] and child['result_pin']==closed['result_pin'],'new_child_chain')
        io.need(claim['stage']==index and claim['config_pin']==self.h['execution_pin'] and claim['request_pin']==io.pin(raw['dispatch.json']),'new_claim_chain')
        c.receipt_checked(g,s,'parent',request['parent_authority'],request['dispatch_begin'])
        c.receipt_checked(g,s,'child',claim['authority'],request['dispatch_begin'])
        end=finite(io,doc['retained_at'],'retention_time')
        io.need(request['dispatch_begin']<=end<=min(g['whole_begin']+7400,g['lease_deadline'],request['parent_authority']['expires'],claim['authority']['expires'])
                and claim['authority']['expires']<=request['parent_authority']['expires'],'actual_return_lease')
        actual=answer_unwire(io,doc['observed']);c.streams_checked(actual)
        io.need(type(actual['code']) is int and actual['code']==0 and actual['timeout'] is False and actual['streams_complete'] is True and actual['exception'] is None,'actual_manager_success')
        io.need(saved_streams(io,c,parsed(io,raw['manager_return.json']))==actual,'actual_manager_readback')
        post_checked(io,parsed(io,raw['post.json']),s['unit'])
        post_checked(io,doc['root_post'],s['unit'])
        root_answer=answer_unwire(io,doc['root_post_transport']);c.streams_checked(root_answer)
        io.need(type(root_answer['code']) is int and root_answer['code']==0 and root_answer['timeout'] is False and root_answer['streams_complete'] is True,'root_cleanup_transport')
        props=self.modules['systemd_adapter'].properties(root_answer['stdout'],('Result','ActiveState','ControlGroup'))
        io.need(doc['root_post']==dict(unit=s['unit'],result=props['Result'],active_state=props['ActiveState'],control_group=props['ControlGroup']),'root_cleanup_readback')
        return raw

    def prior(self,scope,held,snapshot,requested_inventory,now):
        io=self.io;self.subject(held,scope,now);index=scope['stage'];actual=self.custody.snapshot(index)
        io.need(snapshot==actual,'independently_retained_snapshot')
        known=parsed(io,snapshot['known_raw'],1024*1024)
        if requested_inventory is not None:
            # The journal grows between stages; verify its frozen prior-stage
            # entries and never require equality to an older whole-store total.
            io.need(io.canonical(self.whole_inventory())==io.canonical(requested_inventory),'requested_inventory_readback')
        doc=self.custody.dossier(index);raw_files=self.verify_new(doc,index)
        io.need(('closed_pin' not in scope or scope['closed_pin']==io.pin(raw_files['closed.json']))
                and ('result_pin' not in scope or scope['result_pin']==known['returned']['result_pin']),'prior_requested_subject')
        return self.attest('prior',scope,dict(known_return_pin=snapshot['known_pin'],closed_pin=io.pin(raw_files['closed.json']),result_pin=known['returned']['result_pin']),snapshot['known_pin'])

    def audit(self,scope,held,previous,receipt,cache,raw,now):
        io=self.io;self.subject(held,scope,now);proof=self.evidence('audit','root-L-audit-proof-v1',raw)
        keys(io,proof,('schema','execution_pin','input_evidence_pin'),'audit_proof_fields')
        io.need(self.inputs_verified and proof['execution_pin']==self.h['execution_pin'] and proof['input_evidence_pin']==self.verified_input_pin
                and receipt['proof_pin']==self.verified_input_pin and receipt['packet_sha256']==self.h['facts']['packet_sha256']
                and receipt['scope']==scope['input_scope'] and scope['previous_pins']=={k:io.pin(v) for k,v in previous.items()},'audit_input_authentication')
        index=scope['stage']['index'];needed={6:(0,1,2),7:(0,3,4),8:(0,2,4,6,7)}
        io.need(index in needed and set(previous)=={str(n) for n in needed[index]},'audit_prior_roles')
        docs={}
        for n in needed[index]:
            snap=self.custody.snapshot(n);dossier=self.custody.dossier(n);files=self.verify_new(dossier,n)
            io.need(n in cache and cache[n][2]==snap and cache[n][1]==files and previous[str(n)]==files['result.json'],'audit_actual_previous')
            docs[n]=parsed(io,files['result.json'])
        ad=docs[0];io.need(ad['status']=='admitted' and ad['study']==self.c.STUDY and ad['packet_sha256']==self.h['facts']['packet_sha256']
                          and ad['original_admission_sha256']==self.g['input_pins']['original_admission']['sha256'],'actual_L_admission')
        original=read_object(io,self.h['inputs']['original_admission'],2*1024*1024)
        io.need(ad['schema']==original['schema'] and ad['slots']==original['slots'] and ad['denominators']==original['denominators']
                and ad['capacity']==dict(original['capacity'],L=original['capacity']['S'])
                and max(ad['capacity'].values())<=1.05*min(ad['capacity'].values()),'original_L_schema_capacity')
        for seed in (20261012,20261013):
            item=ad['models'][str(seed)+':L'];s=original['models'][str(seed)+':S'];plugin=original['models'][str(seed)+':P']
            io.need(item['initial']==s['initial']==plugin['initial'] and item['order']==s['order']
                    and item['original_initial_sha256']==io.pin(io.canonical(s['initial']))['sha256'],'archived_SP_initial_states')
            self.probe(item['probe'],item['initial'])
        authority=dict(schema='root-shared-reference-AR-L-'+('audit' if index<8 else 'aggregate')+'-authority-v1',
                       packet_sha256=self.h['facts']['packet_sha256'],admission_sha256=io.pin(previous['0'])['sha256'],
                       original_admission_sha256=self.g['input_pins']['original_admission']['sha256'],original_execution_closure_sha256=self.h['facts']['original_execution_closure_sha256'],
                       source_pins={k:self.g['source_pins'][k] for k in ROLES},original_source_pins=self.h['loader']['original_source_pins'])
        if index<8:
            cp,sc=(1,2) if index==6 else (3,4);checkpoint=docs[cp]
            files=self.verify_new(self.custody.dossier(cp),cp)
            io.need(checkpoint['status']=='final' and checkpoint['update']==300 and len(checkpoint['history'])==300,'actual_L_optimizer_final')
            self.optimizer(checkpoint['optimizer'],checkpoint['parameters'])
            for number in range(1,301):
                update=parsed(io,files['update_%03d.json'%number]);io.need(update['update']==number and update['history_last']==checkpoint['history'][number-1],'durable_history_order')
            child=parsed(io,files['child_report.json']);steps=[v for v in child['callbacks'] if v['kind']=='step']
            io.need(len(steps)==300 and all(steps[n-1]['pin']==parsed(io,files['update_%03d.json'%n])['checkpoint_pin'] for n in range(1,301)),'actual_step_callbacks')
            latest=parsed(io,files['latest_update.json']);begin=parsed(io,files['begin_fit.json']);item=ad['models'][str(checkpoint['seed'])+':L']
            io.need(steps[-1]['pin']==io.pin(files['latest_update.json']),'final_step_checkpoint_readback')
            io.need(latest['update']==300 and all(latest[k]==checkpoint[k] for k in ('parameters','optimizer','history'))
                    and begin['update']==0 and begin['parameters']==item['initial'],'actual_initial_final_state_custody')
            self.probe(checkpoint['final_probe'],checkpoint['parameters'])
            order=item['order'];keys(io,order,('__array__','shape','hex'),'actual_order_array')
            io.need(order['__array__']=='<i8' and order['shape']==[300,8],'actual_order_shape')
            order_values=struct.unpack('<2400q',bytes.fromhex(order['hex']))
            io.need(all(v['update']==n+1 and v['ordinals']==list(order_values[n*8:n*8+8]) for n,v in enumerate(checkpoint['history'])),'actual_order_history')
            io.need(checkpoint['admission_sha256']==authority['admission_sha256'] and docs[sc]['checkpoint_sha256']==io.pin(previous[str(cp)])['sha256'],'actual_L_checkpoint_chain')
            authority.update(checkpoint_sha256=io.pin(previous[str(cp)])['sha256'],score_sha256=io.pin(previous[str(sc)])['sha256'],optimizer_history_verified=True,gradient_probes_verified=True)
        else:
            authority.update(closed_comparator_report_sha256=self.g['input_pins']['closed_comparator_report']['sha256'],origins_sha256=self.g['input_pins']['comparator_origins']['sha256'],fits=[])
            for seed,score,audit in ((20261012,2,6),(20261013,4,7)):
                report=docs[audit];io.need(report['schema']=='shared-reference-AR-L-independent-audit-v1' and report['status']=='pass' and report['checked']==66 and len(report['records'])==66 and report['seed']==seed and report['arm']=='L','actual_independent66')
                authority['fits'].append(dict(seed=seed,arm='L',audit_sha256=io.pin(previous[str(audit)])['sha256'],authority_sha256=report['authority_sha256'],score_sha256=io.pin(previous[str(score)])['sha256'],checkpoint_sha256=docs[score]['checkpoint_sha256']))
            authority['comparators_verified']=True
        authority.update(verified=True,native_verified=True,original_initialization_verified=True)
        self.check();return self.attest('audit',scope,dict(authority=authority))

    def probe(self,p,parameters=None):
        io=self.io;io.need(p['events']==65 and p['horizons']==3 and p['terms']==195 and type(p['total']) is int and p['used']==p['total'] and p['total']>0,'actual_gradient_probe')
        io.need(type(p['masks']) is dict and p['masks'],'actual_probe_masks')
        count=0
        if parameters is not None:io.need(set(p['masks'])==set(parameters),'probe_parameter_names')
        for name,a in p['masks'].items():
            keys(io,a,('__array__','shape','hex'),'raw_probe_array');io.need(a['__array__']=='|u1' and type(a['shape']) is list and all(type(n) is int and n>=0 for n in a['shape']),'probe_mask_dtype')
            io.need(type(a['hex']) is str and a['hex']=='01'*math.prod(a['shape']),'all_used_probe')
            count+=math.prod(a['shape'])
            if parameters is not None:io.need(a['shape']==parameters[name]['shape'],'probe_parameter_shape')
        io.need(count==p['total'],'probe_genuine_degree_count')

    def optimizer(self,value,parameters):
        io=self.io;keys(io,value,[str(i) for i in range(len(parameters))],'actual_optimizer_structure')
        names=(['coefficients'] if 'coefficients' in parameters else ['theta','tau'])
        names+=(['prior.first.weight','prior.first.bias'] if 'prior.first.weight' in parameters else ['prior.first_bias'])
        names+=['prior.second.weight','prior.second.bias','prior.head.weight','prior.head.bias']
        io.need(set(names)==set(parameters),'optimizer_parameter_names')
        for i,name in enumerate(names):
            entry=value[str(i)];keys(io,entry,('step','exp_avg','exp_avg_sq'),'adam_fields')
            for key,array in entry.items():
                keys(io,array,('__array__','shape','hex'),'optimizer_array')
                dtype=array['__array__'];io.need(dtype in ('<f8','<f4') and type(array['shape']) is list and all(type(n) is int and n>=0 for n in array['shape']),'optimizer_array_shape')
                raw=bytes.fromhex(array['hex']);size=8 if dtype=='<f8' else 4
                io.need(len(raw)==size*math.prod(array['shape']),'optimizer_array_bytes')
                vals=[v[0] for v in struct.iter_unpack('<d' if size==8 else '<f',raw)]
                io.need(all(math.isfinite(v) and (key!='exp_avg_sq' or v>=0) for v in vals),'optimizer_array_finite')
                if key=='step':io.need(array['shape']==[] and vals==[300.],'optimizer_step300')
                else:io.need(dtype=='<f8' and array['shape']==parameters[name]['shape'],'optimizer_parameter_shape')

    def whole_inventory(self):
        io=self.io;directory=self.h['launch']['store_directory'];fd=io.directory(directory);out={};j=self.modules['journal']
        try:
            for name in os.listdir(fd):
                if name=='.audit.lock':continue
                io.need(re.fullmatch('stage_0[0-8]',name),'unknown_journal_stage')
                members=tree(io,directory+'/'+name);payload=controls=0
                for member,pin in members.items():
                    ispayload=bool(j.PAYLOAD.fullmatch(member)) or member=='return.json'
                    io.need(ispayload or member in j.CONTROLS,'unknown_journal_member')
                    if ispayload:payload+=pin['bytes']
                    else:controls+=pin['bytes']
                io.need(payload<=j.STAGE-j.RESERVE and controls<=j.RESERVE,'journal_storage_partition')
                out[name]=(payload+controls,payload,controls,len(members))
        finally:os.close(fd)
        return out

    def retain_return(self,index,result,inventory,answer,request):
        """Persist real call arguments first, including failed/late returns."""
        io=self.io;io.need(type(index) is int and 0<=index<9,'retention_index')
        directory=self.h['launch']['store_directory']+'/stage_%02d'%index
        files=tree(io,directory);specs={n:dict(path=directory+'/'+n,pin=p,mode=0o400) for n,p in files.items()}
        io.need(io.canonical(self.whole_inventory())==io.canonical(inventory),'actual_retention_inventory')
        known=dict(schema='root-L-known-parent-return-v1',stage=index,config_pin=self.h['execution_pin'],returned=copy.deepcopy(result),inventory=copy.deepcopy(inventory))
        root_post=root_transport=None
        try:
            props=self.show(self.c.spec(self.g,index)['unit'],('Result','ActiveState','ControlGroup'))
            root_post=dict(unit=self.c.spec(self.g,index)['unit'],result=props['Result'],active_state=props['ActiveState'],control_group=props['ControlGroup'])
            root_transport=answer_wire(io,self.last_show)
        except Exception as exc:root_post=dict(error=type(exc).__name__)
        doc=dict(schema='root-L-retained-stage-v1',known=known,files=specs,observed=answer_wire(io,answer),request=copy.deepcopy(request),retained_at=self.clock(),boot_id=self.boot,root_post=root_post,root_post_transport=root_transport)
        raw=io.canonical(doc);io.need(len(raw)<=1024*1024,'root_retention_cap')
        target=self.current_doc['retention_directory'];fd=io.directory(target);lock=None
        try:
            s=os.fstat(fd);io.need(s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700,'root_retention_owner')
            io.need(all(n=='.root.lock' or re.fullmatch(r'stage_0[0-8]\.json',n) for n in os.listdir(fd)),'root_unfinished_retention')
            lock=os.open('.root.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=fd)
            s=os.fstat(lock);io.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o600,'retention_lock')
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            name='stage_%02d.json'%index;temp='.tmp-'+uuid.uuid4().hex
            f=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=fd)
            try:
                pending=memoryview(raw)
                while pending:n=os.write(f,pending);io.need(n>0,'retention_short_write');pending=pending[n:]
                os.fchmod(f,0o400);io.file_sync(f)
            finally:os.close(f)
            os.link(temp,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False);os.unlink(temp,dir_fd=fd);os.fsync(fd)
            io.need(io.read_at(fd,name,1024*1024,0o400)==raw,'root_retention_readback')
        finally:
            if lock is not None:os.close(lock)
            os.close(fd)
        if result['status']=='complete':self.verify_new(doc,index);self.check(closure=True)
        return dict(schema='root-L-last-return-retention-v1',stage=index,return_pin=io.pin(io.canonical(result)),proof_pin=io.pin(raw))


def make_primitives(held,*,expected_root_pin,root_spec,modules,source_begin=None,clock=time.monotonic):
    p=Primitives(held,expected_root_pin=expected_root_pin,root_spec=root_spec,modules=modules,source_begin=source_begin,clock=clock)
    return p,p.custody

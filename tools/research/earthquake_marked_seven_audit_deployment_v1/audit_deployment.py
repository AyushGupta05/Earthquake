"""Independent audit loading and real adapters; no producer/operator imports."""
import os
import sys
import time
from pathlib import Path
import secure_io as io
import source_binding as sb
import audit_control as ctl
import audit_journal as journal

ROLES={'v6','native','auditor','wrapper','input_adapter','harness'}
AUDITOR=('math_core','transport','packet_digest','packet','metrics','auditor')
V6=('secure_io','vendor_inventory','generated_source','metadata_finder','source_binding','systemd_adapter')

def closed_source(spec,check):
    """All ROOT-pinned files, including first-clean/checksum documents, are mandatory."""
    io.need(type(spec)is dict and set(spec)=={'directory','files','manifest','upload_manifest'} and 1<=len(spec['files'])<=128,'closed_spec')
    expected=set(spec['files']);files,links,dirs=sb.inventory(spec['directory'])
    for name in expected:io.parts(name)
    if spec['upload_manifest'] is not None:
        u=spec['upload_manifest'];io.need(u['path']==spec['directory']+'/parent_upload_manifest.private.json' and u['mode']==0o400,'upload_name')
        io.need(io.json_read(io.read_file(u))==spec['files'],'upload_binding');expected.add('parent_upload_manifest.private.json')
    wanted_dirs={str(p) for n in expected for p in Path(n).parents if str(p)!='.'}
    io.need(set(files)==expected and not links and dirs==wanted_dirs,'source_closed')
    raw={}
    for name,pin in spec['files'].items():
        check();value=io.read_file(dict(path=spec['directory']+'/'+name,pin=pin,mode=0o400))
        if name.endswith('.py'):raw[name]=value
    m=spec['manifest'];io.need(m['mode']==0o400 and m['path'].startswith(spec['directory']+'/'),'manifest_role')
    rel=m['path'][len(spec['directory'])+1:];io.need(rel in spec['files'] and m['pin']==spec['files'][rel],'manifest_binding')
    io.read_file(m);check();return raw

def independent_modules(config,raw,prefix,check):
    """Caller holds vendor_guard throughout the audit, including lazy imports."""
    import numpy as np
    import scipy
    expected=config['runtime']['versions']
    io.need(dict(python='.'.join(map(str,sys.version_info[:3])),numpy=np.__version__,scipy=scipy.__version__)=={k:expected[k] for k in ('python','numpy','scipy')},'audit_versions')
    io.need(not any(n=='torch' or n.startswith('torch.') for n in sys.modules),'auditor_torch_forbidden')
    specs=config['sources']
    native=sb.load_group(specs['native'],raw['native'],('marked_native','packet_io'),prefix+'_native')
    audit=sb.load_group(specs['auditor'],raw['auditor'],AUDITOR,prefix+'_audit')
    wrapper=sb.load_group(specs['wrapper'],raw['wrapper'],('wrapper',),prefix+'_wrapper')['wrapper']
    adapter=sb.load_group(specs['input_adapter'],raw['input_adapter'],('adapter',),prefix+'_input')['adapter']
    io.need(native['packet_io'].m is native['marked_native'] and audit['auditor'].core is audit['math_core'] and audit['auditor'].pkt is audit['packet'] and audit['auditor'].tx is audit['transport'] and audit['auditor'].packet_digest is audit['packet_digest'] and audit['auditor'].metrics is audit['metrics'],'audit_alias_binding')
    io.need(all(m.np is np for m in (*native.values(),*audit.values())),'numpy_binding')
    check();return native,audit,wrapper,adapter

class Deployment:
    def __init__(self,config,hooks,systemd,*,clock=time.monotonic):
        ctl.config_check(config,clock());io.need(set(config['sources'])==ROLES,'audit_source_roles')
        io.need(all(callable(getattr(hooks,n,None)) for n in ('authorize','authenticate_input','project_stronger','stage_spec')),'hooks_required')
        self.config=config;self.hooks=hooks;self.systemd=systemd;self.clock=clock;self.source_begin=None;self.raw=None;self.current=None
    def check(self):
        c=self.config;now=self.clock();io.need(now<=min(c['whole_begin']+7200,c['lease_deadline']),'audit_whole_deadline')
        if self.source_begin is not None:io.need(0<=now-self.source_begin<=900,'audit_source_deadline')
    def verify(self):
        self.check();c=self.config
        self.raw={r:(sb.source(s,'adapters' if r=='v6' else 'native',self.check) if r in ('v6','native') else closed_source(s,self.check)) for r,s in c['sources'].items()}
        # Frozen reference bytes are context only, but if supplied in this packet
        # they must equal the actual positively bound V6 execution helpers.
        for name in V6:
            key='reference/'+name+'.py'
            if key in self.raw['harness']:io.need(self.raw['harness'][key]==self.raw['v6'][name+'.py'],'v6_reference_copy')
        sb.runtime(c['runtime'],self.check)
        docs={n:io.read_file(c[n]) for n in ('publication','protocol','hooks_config')}
        io.read_file(c['hooks_source']);io.read_file(c['bundle_template']);self.check();return docs
    def authorize(self,s,phase,bundle_spec):
        io.need(s==ctl.spec(self.config,s['index']) and phase in ('parent','child'),'audit_stage')
        self.systemd.own(s['unit']);docs=self.verify();docs['bundle']=io.read_file(bundle_spec)
        if phase=='parent':self.systemd.available(s['unit'],5)
        c=self.config
        scope=dict(schema='marked-seven-audit-authorization-scope-v1',config_pin=ctl.config_pin(c),audit_id=c['audit_id'],study=c['study'],stage=s['index'],unit=s['unit'],phase=phase,binding_sha256=c['binding_sha256'],bundle_pin=io.pin(docs['bundle']),source_manifest_pins={r:v['manifest']['pin'] for r,v in c['sources'].items()},runtime_subject_pin=io.pin(io.canonical(c['runtime'])),publication_pin=io.pin(docs['publication']),protocol_pin=io.pin(docs['protocol']),whole_begin=c['whole_begin'],lease_deadline=c['lease_deadline'])
        receipt=self.hooks.authorize(scope,docs,self.clock())
        io.need(type(receipt)is dict and set(receipt)=={'schema','scope','decision','expires','disk_available_bytes','disk_reserve_bytes','proofs'} and receipt['schema']=='root-marked-seven-audit-authorization-v1' and receipt['scope']==scope and receipt['decision']=='authorized','audit_root_authority')
        io.need(ctl.finite(receipt['expires']) and self.clock()+(960 if phase=='parent' else 0)<=receipt['expires']<=c['lease_deadline'],'audit_authority_lease')
        io.need(all(type(receipt[k])is int and receipt[k]>=0 for k in ('disk_available_bytes','disk_reserve_bytes')) and receipt['disk_available_bytes']-receipt['disk_reserve_bytes']>=64*1024*1024,'audit_disk_reservation')
        io.need(set(receipt['proofs'])=={'source','runtime','native','stronger','history_gradient','resources'},'audit_proofs')
        for p in receipt['proofs'].values():io.need(type(p)is dict and set(p)=={'known_verified','sha256'} and p['known_verified']is True and type(p['sha256'])is str and len(p['sha256'])==64 and all(x in '0123456789abcdef' for x in p['sha256']),'audit_proof')
        self.check();self.current=(s,bundle_spec,receipt);return receipt
    def run(self,request,timeout):
        end=self.clock()+timeout;io.need(self.current is not None and self.current[0]==request['stage'] and self.current[1]==request['bundle_spec'] and request['config_pin']==ctl.config_pin(self.config),'dispatch_authority')
        s=request['stage'];c=self.config;launch=dict(schema='marked-seven-audit-launch-v1',request=request,config=c,expected_config_pin=ctl.config_pin(c))
        raw=io.canonical(launch);io.need(len(raw)<=256*1024,'bootstrap_cap')
        j=journal.Journal(c['store_directory'])
        try:j.write(s['index'],'bootstrap.json',raw)
        finally:j.close()
        own=c['sources']['harness'];path=own['directory']+'/audit_bootstrap.py';pin=own['files']['audit_bootstrap.py'];launch_path=c['store_directory']+'/stage_%02d/bootstrap.json'%s['index']
        # All parent source bytes were positively verified immediately before
        # dispatch. Bootstrap verifies path ancestry and every module again.
        code=("import time;begin=time.monotonic();import os,sys,hashlib;f=os.open(%r,os.O_RDONLY|os.O_NOFOLLOW);b=os.read(f,%d);os.close(f);assert len(b)==%d and hashlib.sha256(b).hexdigest()==%r;sys.argv=[%r,%r,%r];exec(compile(b,%r,'exec'),dict(__name__='__main__',__file__=%r,SOURCE_BEGIN=begin))")%(path,pin['bytes']+1,pin['bytes'],pin['sha256'],path,launch_path,io.pin(raw)['sha256'],path,path)
        remaining=end-self.clock();io.need(remaining>0,'audit_transport_preparation')
        return self.systemd.run(ctl.command(s,c['runtime']['python'],code),remaining,s['unit'])
    def stop(self,unit,timeout):return self.systemd.stop(unit,timeout)
    def inspect(self,unit,timeout):return self.systemd.inspect(unit,timeout)

def execute(request,j,dep,*,source_begin):
    """Full report retained before late checks; no audit/science retry."""
    c=dep.config;s=request['stage'];i=s['index'];dep.source_begin=source_begin
    returned=None;report=None;errors=[]
    try:
        io.need(request['schema']=='marked-seven-audit-request-v1' and request['config_pin']==ctl.config_pin(c) and s==ctl.spec(c,i),'child_request')
        io.need(j.read(i,'dispatch.json')==io.canonical(request),'dispatch_custody')
        io.need(request['previous']==ctl.prior(c,i,j),'prior_custody')
        receipt=dep.authorize(s,'child',request['bundle_spec']);dep.systemd.live(s)
        def authorized_check():
            dep.check();io.need(dep.clock()<=receipt['expires'],'child_authorization_expired')
        authorized_check()
        with sb.vendor_guard(c['runtime'],c['sources'],(c['hooks_source'],),authorized_check):
            native,audit,wrapper,adapter=independent_modules(c,dep.raw,'independent_'+str(os.getpid())+'_'+str(i),authorized_check)
            tx=audit['transport']
            raw=io.read_file(request['bundle_spec']);bundle=io.json_read(raw)
            io.need(io.canonical(bundle)==raw and bundle['binding_sha256']==c['binding_sha256'] and bundle['wrapper_binding_sha256']==c['wrapper_binding_sha256'],'bundle_custody')
            def decode(raw,sha):
                io.need(io.pin(raw)['sha256']==sha,'numeric_input_hash');value=tx.decode(io.json_read(raw),cap=16*1024*1024);io.need(tx.canonical(value)==raw,'numeric_canonical');return value
            def load_native(archive,manifest,*,processing_begin):
                return native['packet_io'].load(archive,manifest,pins={'archive':bundle['native']['feature_archive']['pin'],'manifest':bundle['native']['feature_manifest']['pin']},processing_begin=processing_begin)
            b=adapter.Bindings(read=io.read_file,decode=decode,canonical=tx.canonical,load_native=load_native,packet_sha=audit['packet_digest'].sha,project_stronger=dep.hooks.project_stronger,authenticate=dep.hooks.authenticate_input,stage_spec=dep.hooks.stage_spec,binding_sha256=c['binding_sha256'])
            prepared=adapter.prepare_inputs(i,bundle,b,processing_begin=source_begin);authorized_check()
            gate=dict(schema='root-marked-sixfit-audit-wrapper-gate-v1',study=c['study'],stage=i,root_verified=True,proofs=prepared['proofs'],binding_sha256=c['wrapper_binding_sha256'],inputs_sha256=prepared['inputs_sha256'],whole_begin=c['whole_begin'],whole_seconds=7200,closure_seconds=200,lease_deadline=min(c['lease_deadline'],receipt['expires']),disk_available_bytes=receipt['disk_available_bytes'],disk_reserve_bytes=receipt['disk_reserve_bytes'],stage_payload_cap_bytes=64*1024*1024,previous=prepared['previous'])
            def claim(raw,sha):io.need(io.pin(raw)['sha256']==sha,'claim_hash');return j.write(i,'claim.json',raw)
            def retain(kind,ordinal,raw,sha):
                io.need(kind in ('record','raw_report','wrapper_failure') and type(ordinal)is int and 0<=ordinal<70 and io.pin(raw)['sha256']==sha,'retained_binding')
                return j.write(i,'%s_%03d.json'%(kind,ordinal),raw)
            bindings=wrapper.Bindings(audit['auditor'].audit_fit,audit['auditor'].aggregate,tx.canonical,c['wrapper_binding_sha256'])
            returned=wrapper.run_stage(i,prepared['inputs'],gate,bindings,claim=claim,retain=retain,processing_begin=source_begin)
            encoded=tx.canonical(returned);j.write(i,'return.json',encoded) # before tick/interpretation
            io.need(returned['status']=='complete','wrapper_incomplete');authorized_check()
            j.read(i,'raw_report_000.json',returned['report_pin'])
            cp=io.pin(j.read(i,'claim.json'));io.need(cp['sha256']==returned['claim_sha256'],'wrapper_claim_pin')
            report=dict(schema='marked-seven-audit-child-report-v1',status='complete',stage=i,config_pin=ctl.config_pin(c),request_pin=io.pin(io.canonical(request)),return_pin=io.pin(encoded),report_pin=returned['report_pin'],claim_pin=cp,within_source=True)
            j.object(i,'child_report.json',report);authorized_check()
        authorized_check();return report
    except Exception as exc:
        failure=dict(schema='marked-seven-audit-child-failure-v1',status='incomplete',stage=i,config_pin=ctl.config_pin(c),reason=str(exc)[:256],exception=type(exc).__name__,no_retry=True)
        # No fallible science clock before preserving the error.
        try:j.object(i,'child_failure.json',failure)
        except Exception:failure['retention_unverified']=True
        return failure

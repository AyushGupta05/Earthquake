"""ROOT-configured real deployment adapters. Authority callback has no permissive default."""
import os
import math
import sys
import time
import secure_io as io
import source_binding as sb
from comparison_join import project


class Deployment:
    def __init__(self,config,root_authority,systemd,*,clock=time.monotonic):
        keys={'schema','sources','runtime','inputs','protocol','publication','bootstrap','store_directory','storage_limit_bytes','commands','authority_source','authority_config'}
        io.need(type(config) is dict and set(config)==keys and config['schema']=='marked-deployment-config-v1','deployment_config')
        io.need(type(config['sources']) is dict and set(config['sources'])=={'processor','gaussian','native','parent','adapters'},'source_roles')
        io.need(callable(root_authority),'real_root_authority_required')
        self.config=config;self.authority=root_authority;self.systemd=systemd;self.clock=clock;self.raw=None;self.parent=None;self.stage=None;self.request=None;self.science_begin=None
    def check(self):
        if self.request is not None:
            now=self.clock();g=self.request['gate'];io.need(now<=g['experiment_begin']+7200,'whole_source_deadline')
            if self.science_begin is not None:io.need(now-self.science_begin<=self.request['stage']['source_seconds'],'stage_source_deadline')
    def verify(self,g):
        io.need(self.config['storage_limit_bytes']==g['storage_limit_bytes'],'storage_envelope')
        self.raw={role:sb.source(spec,role,self.check) for role,spec in self.config['sources'].items()}
        sb.cross_copies(self.raw);sb.runtime(self.config['runtime'],self.check)
        expected=dict(processor=self.config['sources']['processor']['manifest']['pin'],operator=self.config['sources']['gaussian']['manifest']['pin'],
                      reference=self.config['sources']['gaussian']['manifest']['pin'],native=self.config['sources']['native']['manifest']['pin'],
                      parent=self.config['sources']['parent']['manifest']['pin'],protocol=self.config['protocol']['pin'])
        io.need(g['source_pins']==expected and g['runtime_pin']==self.config['runtime']['manifest']['pin'],'gate_source_runtime_binding')
        io.need(set(self.config['inputs'])==set(g['input_pins']) and all(self.config['inputs'][k]['pin']==p for k,p in g['input_pins'].items()),'input_specs')
        self.inputs={k:io.read_file(spec) for k,spec in self.config['inputs'].items()}
        io.read_file(self.config['protocol']);publication=io.read_file(self.config['publication'])
        bootstrap=self.config['bootstrap'];io.need(bootstrap['path']==self.config['sources']['adapters']['directory']+'/bootstrap.py'
                and bootstrap['pin']==self.config['sources']['adapters']['files']['bootstrap.py'],'bootstrap_registered')
        io.read_file(bootstrap)
        io.read_file(self.config['authority_source'])
        io.read_file(self.config['authority_config'])
        self.check();return publication
    def root_receipt(self,g,spec,publication,phase):
        """Actual independent ROOT verification is mandatory, not a fixture Boolean."""
        scope=dict(gate_sha256=io.pin(io.canonical(g))['sha256'],config_pin=io.pin(io.canonical(self.config)),index=spec['index'],unit=spec['unit'],
                   source_pins=g['source_pins'],runtime_pin=g['runtime_pin'],input_pins=g['input_pins'],funding_pin=g['funding_pin'],
                   publication_pin=io.pin(publication),phase=phase)
        # ROOT verifies current funding/publication and actual old/native semantic
        # proofs from these exact raw bytes; this adapter cannot create that proof.
        receipt=self.authority(scope,dict(publication=publication,feature_authority=self.inputs['feature_authority'],strong_authority=self.inputs['strong_authority'],strong_results=self.inputs['strong_results']),self.clock())
        io.need(type(receipt) is dict and set(receipt)=={'schema','scope','decision','expires','evidence_pins'} and receipt['schema']=='root-marked-stage-authority-v1'
                and receipt['scope']==scope and receipt['decision']=='authorized' and type(receipt['expires']) in (int,float) and math.isfinite(receipt['expires']),'root_authority')
        io.need(receipt['evidence_pins']==dict(publication=io.pin(publication),feature=io.pin(self.inputs['feature_authority']),strong=io.pin(self.inputs['strong_authority']),funding=g['funding_pin']), 'authority_evidence')
        io.need(receipt['expires']>=self.clock()+spec['manager_seconds'] if phase=='parent' else receipt['expires']>=self.clock(),'authority_lease')
        return receipt
    def authorize(self,g,spec,now):
        self.request=dict(gate=g,stage=spec);self.stage=spec;self.systemd.own(spec['unit'])
        publication=self.verify(g);self.systemd.available(spec['unit'],5)
        receipt=self.root_receipt(g,spec,publication,'parent')
        return dict(authorized=True,gate_sha256=io.pin(io.canonical(g))['sha256'],index=spec['index'],unit=spec['unit'],funding_pin=g['funding_pin'],expires=receipt['expires'],
                    verified=dict(source_runtime=True,native_agreement=True,strong_closure=True,owned_unit_available=True))
    def run(self,request,timeout):
        transport_end=self.clock()+timeout
        io.need(self.stage==request['stage'] and self.request['gate']==request['gate'],'authorized_stage');self.request=request
        # Launch specification is a separate immutable control artifact, never a
        # feature/checkpoint. It is included in ROOT's existing store envelope.
        store=io.Store(self.config['store_directory'],self.config['storage_limit_bytes'])
        try:
            raw=io.canonical(dict(schema='marked-stage-launch-v1',request=request,config=self.config,expected_deployment_config_pin=io.pin(io.canonical(self.config))))
            name='stage_%02d/bootstrap.json'%request['stage']['index']
            receipt=store.write(name,raw,total_cap=self.config['storage_limit_bytes'])
        finally:store.close()
        argv=[self.config['store_directory']+'/'+name,receipt['pin']['sha256']]
        parent=sb.load_group(self.config['sources']['parent'],self.raw['parent'],('controller','child'),'parent_dispatch_'+str(os.getpid())+'_'+str(request['stage']['index']))
        path=self.config['bootstrap']['path'];sha=self.config['bootstrap']['pin']['sha256'];size=self.config['bootstrap']['pin']['bytes']
        code=("import time;begin=time.monotonic();import os,sys,hashlib;"
              "f=os.open(%r,os.O_RDONLY|os.O_NOFOLLOW);b=os.read(f,%d);os.close(f);"
              "assert len(b)==%d and hashlib.sha256(b).hexdigest()==%r;"
              "sys.argv=[%r,%r,%r];exec(compile(b,%r,'exec'),dict(__name__='__main__',__file__=%r,SOURCE_BEGIN=begin))")%(path,size+1,size,sha,path,argv[0],argv[1],path,path)
        command=parent['controller'].systemd_command(request,self.config['runtime']['python'],code)
        remaining=transport_end-self.clock();io.need(remaining>0,'transport_preparation_expired')
        return self.systemd.run(command,remaining,request['stage']['unit'])
    def stop(self,unit,timeout):return self.systemd.stop(unit,timeout)
    def inspect(self,unit,timeout):return self.systemd.inspect(unit,timeout)
    def live(self,unit):
        io.need(self.request is not None and unit==self.request['stage']['unit'],'child_request');self.systemd.own(unit);return self.systemd.live(self.request['stage'])
    def load(self,name,expected):
        spec=self.config['inputs'][name];io.need(spec['pin']==expected,'input_pin');return io.read_file(spec)
    def bind(self,request,raw_inputs):
        self.request=request;self.stage=request['stage'];publication=self.verify(request['gate'])
        io.need(raw_inputs==self.inputs,'input_read_changed');self.root_receipt(request['gate'],request['stage'],publication,'child')
        native,gaussian,proc=sb.scientific_modules(self.config['sources'],self.raw,self.config['runtime'],'marked_'+str(os.getpid())+'_'+str(request['stage']['index']),extra_sources=(self.config['authority_source'],),check=self.check)
        packet=native['packet_io'].load(raw_inputs['feature_archive'],raw_inputs['feature_manifest'],pins={'archive':request['gate']['input_pins']['feature_archive'],'manifest':request['gate']['input_pins']['feature_manifest']},processing_begin=self.science_begin)
        processor=proc['processor'];pins=request['gate']['source_pins']
        bindings=processor.Bindings(gaussian['gaussian_operator'],native['packet_io'],gaussian['reference_core'],dict(operator=pins['operator'],native_validator=pins['native'],reference=pins['reference'],processor=pins['processor'],protocol=pins['protocol']))
        processor.validate_packet(packet,bindings,self.science_begin,request['stage']['source_seconds'])
        # Closure is separately authorized; the projection itself checks actual
        # old/new role/target/group/ordinal/horizon equality and preserves origins.
        strong=project(packet,io.json_read(raw_inputs['strong_results']),request['gate']['input_pins']['strong_authority'],processor.packet_hash(packet))
        for fit in strong:processor.validate_population(fit['predictions'],packet,fit['seed'],fit['arm'])
        self.check()
        return dict(processor=processor,bindings=bindings,numeric=proc['numeric_state'],packet=packet,strong_results=strong,
                    binding_receipt=dict(verified=True,gate_sha256=io.pin(io.canonical(request['gate']))['sha256'],source_pins=request['gate']['source_pins'],runtime_pin=request['gate']['runtime_pin'],input_pins=request['gate']['input_pins']))

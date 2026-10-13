"""ROOT-only read-only closure checks and exclusive metadata publication.

No model/score/provider code; source-bound IO, Journal and OS observer injected.
"""
import hashlib
import json
import os
import stat
import uuid

BASE={'bootstrap.json','dispatch.json','claim.json','return.json','raw_report_000.json','child_report.json','manager_return.json','post.json','closed.json'}
PAIRS=tuple((s,a)for s in(20261012,20261013)for a in('S','P','D'))
ROLES={'claim':'claim.json','return':'return.json','report':'raw_report_000.json','closed':'closed.json'}

def need(v,reason):
    if not v:raise ValueError(reason)
def keys(v,names):need(type(v)is dict and set(v)==set(names),'keys')
def plain(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def pin(v):return dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest())
def integer(v,n):need(type(v)is int and v==n,'integer')
def schema(raw):
    def pairs(items):
        v={}
        for k,val in items:need(k not in v,'duplicate_key');v[k]=val
        return v
    obj=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in()).throw(ValueError('nonfinite')));need(plain(obj)==raw,'canonical_json');return obj

def durable(io,directory,name,value,cap=1048576):
    """No-overwrite atomic400/fsync/readback; unfinished temp is retained on failure."""
    need(type(name)is str and name and '/'not in name and name not in('.','..'),'metadata_name');raw=plain(value);need(len(raw)<=cap,'metadata_cap');fd=io.directory(directory);temp='.tmp-'+uuid.uuid4().hex
    try:
        s=os.fstat(fd);need(s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700,'metadata_directory')
        try:os.stat(name,dir_fd=fd,follow_symlinks=False)
        except FileNotFoundError:pass
        else:raise FileExistsError(name)
        f=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=fd)
        try:
            view=memoryview(raw)
            while view:
                n=os.write(f,view);need(n>0,'short_write');view=view[n:]
            os.fchmod(f,0o400);io.file_sync(f)
        finally:os.close(f)
        os.link(temp,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False);os.unlink(temp,dir_fd=fd);os.fsync(fd)
        expected=pin(raw);need(io.read_at(fd,name,cap,0o400,expected)==raw,'metadata_readback');return dict(path=directory+'/'+name,pin=expected,mode=0o400)
    finally:os.close(fd)

def dynamic_bundle(config,index,io,known_root_return):
    integer(index,index);need(0<=index<7,'stage');template_raw=io.read_file(config['bundle_template']);template=schema(template_raw);need(template['previous_audits']==[],'template_empty_previous')
    ac=schema(io.read_file(config['hooks_config']));root=ac['last_return_evidence_directory'];previous=[]
    for i in range(index):
        held=known_root_return(io,root+'/stage_%02d.private.json'%i)
        need(held['schema']=='root-seven-audit-last-return-v1' and type(held['stage'])is int and held['stage']==i and held['config_pin']==pin(plain(config)),'held_previous')
        own=config['store_directory']+'/stage_%02d'%i;need(held['directory']==own,'previous_directory');keys(held['files'],ROLES)
        previous.append({role:dict(path=own+'/'+name,pin=held['files'][role],mode=0o400)for role,name in ROLES.items()})
    value=dict(template,previous_audits=previous);return value

def complete_closure(config,index,actual_return,j,io,inspect,*,bundle_spec):
    """Independent ROOT postflight: no persisted flag establishes actual return truth."""
    integer(index,index);need(0<=index<7,'stage');cp=pin(plain(config));unit='eew-marked-'+config['audit_id']+'-%02d.service'%index
    need(type(actual_return)is dict and actual_return['schema']=='marked-seven-audit-manager-return-v1' and actual_return['status']=='complete' and type(actual_return['stage'])is int and actual_return['stage']==index and actual_return['config_pin']==cp and actual_return['unit']==unit and actual_return['cleanup_verified']is True and actual_return['errors']==[] and actual_return['no_retry']is True,'actual_return')
    # Journal inventory enforces owner400/no links/private dirs/caps over all stages.
    inventory=j.inventory();need('stage_%02d'%index in inventory,'stage_inventory')
    root=config['store_directory']+'/stage_%02d'%index;fd=io.directory(root)
    expected=BASE|{'record_%03d.json'%i for i in range(66 if index<6 else 1)}
    try:
        need(set(os.listdir(fd))==expected,'exact_success_inventory');raw={name:io.read_at(fd,name,16*1024*1024,0o400)for name in expected};need(set(os.listdir(fd))==expected,'stable_inventory')
    finally:os.close(fd)
    inv={n:pin(b)for n,b in raw.items()};v={n:schema(b)for n,b in raw.items()};need(v['closed.json']==actual_return,'final_return_agreement')
    observed=inspect(unit,5);need(observed==dict(unit=unit,result='success',active_state='inactive',control_group='') and v['post.json']==observed,'fresh_owned_cleanup')
    manager=v['manager_return.json'];keys(manager,('code','timeout','streams_complete','exception','stdout','stderr','stream_custody'));integer(manager['code'],0);need(manager['timeout']is False and manager['streams_complete']is True and manager['exception']is None,'raw_manager_complete');keys(manager['stream_custody'],('stdout','stderr'))
    for stream,cap in(('stdout',65536),('stderr',131072)):
        clip=manager[stream];meta=manager['stream_custody'][stream];keys(clip,('retained_hex','retained_pin','truncated'));keys(meta,('original_bytes','original_sha256','retained_bytes','truncated','complete_observation'));need(type(clip['retained_hex'])is str and len(clip['retained_hex'])<=2*cap,'raw_stream_cap');data=bytes.fromhex(clip['retained_hex']);integer(meta['original_bytes'],len(data));integer(meta['retained_bytes'],len(data));need(clip['truncated']is False and pin(data)==clip['retained_pin'] and meta['original_sha256']==pin(data)['sha256'] and meta['truncated']is False and meta['complete_observation']is True,'raw_stream_custody')
    dispatch=v['dispatch.json'];keys(dispatch,('schema','config_pin','stage','dispatch_begin','previous','bundle_spec'));need(dispatch['schema']=='marked-seven-audit-request-v1' and dispatch['config_pin']==cp and type(dispatch['stage']['index'])is int and dispatch['stage']['index']==index and dispatch['stage']['unit']==unit and dispatch['bundle_spec']==bundle_spec,'dispatch_binding')
    integer(dispatch['stage']['source_seconds'],900);integer(dispatch['stage']['manager_seconds'],960)
    need(dispatch['stage']['limits']==dict(memory=2147483648,swap=0,tasks=64,cpu_weight=10,threads=1,cuda_hidden=True,kill_mode='control-group',stop_seconds=5),'fixed_limits')
    need(v['bootstrap.json']==dict(schema='marked-seven-audit-launch-v1',request=dispatch,config=config,expected_config_pin=cp),'bootstrap_binding')
    child=v['child_report.json'];keys(child,('schema','status','stage','config_pin','request_pin','return_pin','report_pin','claim_pin','within_source'));integer(child['stage'],index)
    need(child['schema']=='marked-seven-audit-child-report-v1' and child['status']=='complete' and child['config_pin']==cp and child['request_pin']==inv['dispatch.json'] and child['return_pin']==inv['return.json'] and child['report_pin']==inv['raw_report_000.json'] and child['claim_pin']==inv['claim.json'] and child['within_source']is True,'child_custody')
    need(actual_return['child_report_pin']==inv['child_report.json'] and actual_return['return_pin']==inv['return.json'] and actual_return['report_pin']==inv['raw_report_000.json'],'parent_child_pins')
    returned=v['return.json'];claim=v['claim.json'];report=v['raw_report_000.json'];need(returned['advance']==report['advance'],'advance_unchanged');integer(returned['stage'],index);integer(claim['stage'],index)
    need(returned['schema']=='marked-sixfit-audit-wrapper-return-v1' and returned['status']=='complete' and returned['binding_sha256']==config['wrapper_binding_sha256'] and returned['report_pin']==inv['raw_report_000.json'] and returned['claim_sha256']==inv['claim.json']['sha256'] and claim['schema']=='marked-sixfit-audit-wrapper-claim-v1' and claim['study']==config['study'] and claim['inputs_sha256']==returned['input_sha256'] and claim['binding_sha256']==returned['binding_sha256'] and claim['whole_begin']==config['whole_begin'],'wrapper_custody')
    if index<6:
        seed,arm=PAIRS[index];integer(returned['seed'],seed);integer(claim['seed'],seed);integer(report['seed'],seed);need(returned['arm']==claim['arm']==report['arm']==arm,'fit_identity');integer(report['checked'],66);need(report['schema']=='marked-sixfit-independent-audit-v1' and report['status']=='pass' and type(report['records'])is list and len(report['records'])==66,'fit_report')
        bundle=schema(io.read_file(bundle_spec));score=schema(io.read_file(bundle['stages'][2*index+2]['result.json']));need(type(score['predictions'])is list and len(score['predictions'])==66,'original_score66')
        for i,pred in enumerate(score['predictions']):
            record=v['record_%03d.json'%i];integer(record['position'],i);need(record['status']=='pass' and record['fresh']==report['records'][i] and record['source_sha256']==pin(plain(pred['source']))['sha256'],'record_order_source')
    else:
        need(returned['seed']is None and returned['arm']is None and claim['seed']is None and claim['arm']is None,'aggregate_identity');integer(report['checked'],396);need(report['schema']=='marked-sixfit-independent-aggregate-v1' and report['status']=='pass' and len(report['fits'])==6 and len(report['stronger'])==8 and raw['record_000.json']==raw['raw_report_000.json'],'aggregate_report')
    records=[raw['record_%03d.json'%i]for i in range(66 if index<6 else 1)];count=len(records)+1;retained=sum(map(len,records))+len(raw['raw_report_000.json'])
    for field in('retained_count','attempted_count'):integer(returned[field],count)
    for field in('retained_bytes','attempted_bytes'):integer(returned[field],retained)
    need(sum(p['bytes']for p in inv.values())<=64*1024*1024,'stage_disk_cap')
    return dict(schema='root-seven-audit-last-return-v1',stage=index,config_pin=cp,directory=root,files={role:inv[name]for role,name in ROLES.items()},inventory=inv,last_return=actual_return,root_observation=observed,root_manager=manager)

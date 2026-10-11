#!/usr/bin/env python3
"""Local CPU counts screen; collect requires exact reviewed parent freeze receipt."""
import time
PROCESS_STARTED=time.monotonic()
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import urllib.parse
import dependencies as deps
import selection
import screen
import transport

BASE=Path(__file__).resolve().parent
BULK=BASE.parent/'geonet_bulk_metadata'
WAVE=BASE.parent/'geonet_waveform_feasibility'
CENSUS=BASE.parent/'geonet_tail_census/local_runs/recovery_20261010'
MIB=1024*1024
OUTER=7200
RESERVE=10
GENERATED_CAP=1024*MIB
FILES=('counts.py','dependencies.py','selection.py','screen.py','transport.py','test_counts.py','PROTOCOL_v1.md','specification.json','reviewed_dependencies.json')
BULK_MEMBERS=('local_runs/planned_inputs_final.json','local_runs/parent_receipt_final.json','local_runs/collection_final/manifest.json','local_runs/collection_final/outcomes.json','local_runs/collection_final/summary.json','local_runs/collection_final/requests.json')

def load(path,cap=32*MIB):return json.loads(deps.read(path,cap))
def dump(path,obj):transport.checkpoint(path,obj)
def local(path):
    allowed=BASE/'local_runs';p=Path(path)
    if allowed.is_symlink() or p.is_symlink() or not p.resolve().is_relative_to(allowed) or p.resolve()==allowed:raise ValueError('private nonsymlink local_runs required')
    return p.resolve()
def pin(path,cap=GENERATED_CAP):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('artifact bounds exceeded')
    digest=hashlib.sha256();total=0
    with path.open('rb') as f:
        while part:=f.read(65536):
            total+=len(part)
            if total>cap:raise ValueError('artifact grew')
            digest.update(part)
    return {'bytes':total,'sha256':digest.hexdigest()}
def sources():return {n:deps.sha(deps.read(BASE/n,4*MIB)) for n in FILES}
def specification():
    spec=load(BASE/'specification.json',MIB)
    expected={'events':96,'station_targets':768,'metadata_requests':768,'waveform_batches':6,'attempts':800,'body_bytes':512*MIB,'metadata_body_bytes':4*MIB,'waveform_body_bytes':16*MIB,'declared_decoded_sample_bytes':64*MIB,'actual_decoded_sample_bytes':64*MIB,'outer_seconds':OUTER,'finalization_reserve_seconds':RESERVE,'request_seconds':20,'start_spacing_seconds':1,'retries':0,'redirects':0,'replacement':0,'resume':False,'AWS':0,'fits':0}
    if spec['caps']!=expected or spec['events']!=96 or spec['arrival_station_cap']!=8 or spec['horizons_seconds']!=[1,3,5] or spec['batch_events']!=16:raise ValueError('frozen specification changed')
    return spec

def input_objects(input_path):
    input_path=local(input_path);body=deps.read(input_path,2*MIB);receipt=json.loads(body)
    if receipt.get('version')!='geonet-counts-selection-inputs-v1' or receipt.get('completed_bulk_independently_replayed') is not True or receipt.get('bulk_gate_passed') is not True:raise ValueError('parent verified completed bulk gate required')
    pins=receipt.get('bulk_files',{})
    if set(pins)!=set(BULK_MEMBERS):raise ValueError('exact completed bulk input members required')
    if pins[BULK_MEMBERS[0]]!=specification()['bulk_plan_sha256']:raise ValueError('frozen prior bulk plan changed')
    objects={}
    for name,digest in pins.items():
        data=deps.read(BULK/name,32*MIB)
        if deps.sha(data)!=digest:raise ValueError('bulk input pin mismatch')
        objects[name]=json.loads(data)
    replay_path=Path(receipt['bulk_independent_replay_path'])
    if replay_path.is_symlink() or not replay_path.resolve().is_relative_to(BULK.resolve()):raise ValueError('bulk replay must stay in its original directory')
    replay=deps.read(replay_path,2*MIB)
    if deps.sha(replay)!=receipt['bulk_independent_replay_sha256'] or json.loads(replay).get('all_checks_pass') is not True:raise ValueError('independent bulk replay missing')
    plan=objects[BULK_MEMBERS[0]];parent=objects[BULK_MEMBERS[1]];manifest=objects[BULK_MEMBERS[2]];outcomes=objects[BULK_MEMBERS[3]];summary=objects[BULK_MEMBERS[4]]
    root=BULK/'local_runs/collection_final'
    if manifest.get('completed') is not True or manifest.get('artifact_pins_incomplete') or (root/'outer_interruption.json').exists() or summary.get('metadata_missingness_gate_pass') is not True or summary.get('completed') is not True:raise ValueError('bulk completed gate not satisfied')
    if manifest['plan_sha256']!=pins[BULK_MEMBERS[0]] or manifest['parent_receipt_sha256']!=pins[BULK_MEMBERS[1]] or parent.get('plan_sha256')!=pins[BULK_MEMBERS[0]]:raise ValueError('bulk provenance mismatch')
    for name,digest in plan['input_pins'].items():
        if deps.sha(deps.read(CENSUS/name,32*MIB))!=digest:raise ValueError('original census input changed')
    if plan['input_pins']['groups.json']!='2270bd1969f8565dfd2cc683a17c08c766324ab67425d289956f9b68f19a44a8':raise ValueError('original CMT frame changed')
    for relative in ('outcomes.json','summary.json','requests.json'):
        if pin(root/relative)!=manifest['files'][relative]:raise ValueError('completed bulk member mismatch')
    if len(outcomes)!=495 or len({r['event_id'] for r in outcomes})!=495 or {r['event_id'] for r in outcomes}!={r['event_id'] for r in plan['rows']}:raise ValueError('lost bulk denominator')
    return receipt,body,plan,{r['event_id']:r for r in outcomes}

def cached_candidates(receipt,events,core):
    config=receipt.get('cache')
    if config is None:return {},None
    if Path(config['root']).is_symlink():raise ValueError('cache root symlink forbidden')
    root=Path(config['root']).resolve()
    if not root.is_relative_to((WAVE/'local_runs').resolve()):raise ValueError('cache must stay in completed waveform local_runs')
    paths={n:Path(p['path']) for n,p in config['files'].items()}
    if set(paths)!={'manifest','plan','parent_receipt','requests'}:raise ValueError('cache provenance members required')
    objects={}
    for n,p in paths.items():
        if not p.resolve().is_relative_to((WAVE/'local_runs').resolve()):raise ValueError('cache input escaped')
        body=deps.read(p,32*MIB)
        if deps.sha(body)!=config['files'][n]['sha256']:raise ValueError('cache input pin mismatch')
        objects[n]=json.loads(body)
    m=objects['manifest'];p=objects['plan'];r=objects['parent_receipt']
    if paths['manifest'].resolve()!=root/'manifest.json' or paths['requests'].resolve()!=root/'requests.json':raise ValueError('cache ledger/manifest from another run')
    if pin(paths['requests'],32*MIB)!=m['files']['requests.json']:raise ValueError('cache ledger differs from completed manifest member')
    if m.get('completed') is not True or (root/'OUTER_INCOMPLETE.json').exists() or (root/'PROCESS_INCOMPLETE.json').exists():raise ValueError('cache acquisition incomplete')
    if m['plan_sha256']!=config['files']['plan']['sha256'] or m['parent_receipt_sha256']!=config['files']['parent_receipt']['sha256'] or r['plan_sha256']!=config['files']['plan']['sha256']:raise ValueError('cache receipt provenance mismatch')
    if r.get('acquisition_authorized') is not True or r.get('code_only_review_clean') is not True or not re.fullmatch('[0-9a-f]{40}',r.get('parent_pre_acquisition_commit','')):raise ValueError('cache original parent freeze missing')
    names=('audit.py','core.py','PROTOCOL_v1.md','census_input_pins.json')
    expected={n:deps.sha(deps.read(WAVE/n,4*MIB)) for n in names}
    if p.get('source_files')!=expected or r.get('source_files')!=expected:raise ValueError('cache reviewed source changed')
    if expected['audit.py']!=deps.pins()['adapter']['sha256'] or expected['core.py']!=deps.pins()['core']['sha256']:raise ValueError('cache adapter/core source changed')
    if r.get('dependency_receipt_sha256')!=deps.pins()['dependency_receipt']['sha256']:raise ValueError('cache runtime receipt changed')
    query_map={q['file']:q for q in p['requests']};cache={}
    targets={(e['event_id'],t['station']):(e,t) for e in events for t in e['targets'] if t['queryable']}
    for entry in objects['requests']:
        if entry.get('status')!='ok' or entry.get('http_status')!=200 or not entry.get('bytes'):continue
        q=query_map.get(entry['file'])
        if q is None or q['url']!=entry['url']:raise ValueError('cache request differs from frozen original query')
        pair=(q['event_id'],q['station'])
        if pair not in targets:continue
        event,target=targets[pair];canonical=selection.envelope(event,target,core)
        parsed=urllib.parse.urlsplit(q['url']);args=urllib.parse.parse_qs(parsed.query,strict_parsing=True,keep_blank_values=True)
        extra={'level':'response','format':'xml'} if q['kind']=='station' else {'format':'miniseed'}
        endpoint='/fdsnws/'+q['kind']+'/1/query'
        if parsed.scheme!='https' or parsed.netloc!='service.geonet.org.nz' or parsed.path!=endpoint or parsed.fragment or args!={k:[v] for k,v in (canonical|extra).items()}:continue
        if Path(entry['file']).name!=entry['file'] or (root/'raw').is_symlink():raise ValueError('cache raw path escaped')
        f=root/'raw'/entry['file'];expected_pin=m['files']['raw/'+entry['file']]
        if pin(f,16*MIB)!=expected_pin or expected_pin!={'bytes':entry['bytes'],'sha256':entry['sha256']}:raise ValueError('cache body/member/request mismatch')
        slot=event['event_id']+'|'+target['station'];kind='response' if q['kind']=='station' else 'waveform'
        if kind in cache.setdefault(slot,{}):raise ValueError('ambiguous exact cache candidate')
        cache[slot][kind]={'path':str(f),'pin':expected_pin,'canonical':canonical,'format':extra['format'],'original_method':'GET','method_difference':'GET_to_POST_selection_equivalence' if kind=='waveform' else None}
    return cache,config

def make_plan(input_path):
    spec=specification();runtime=deps.runtime();receipt,input_body,bulk,outcomes=input_objects(input_path)
    core=deps.module('core');events=selection.choose(bulk['rows'],outcomes,core,spec)
    cache,cache_provenance=cached_candidates(receipt,events,core);metadata,batches=selection.queries(events,core,cache)
    return {'version':'geonet-counts-screen-plan-v1','input_receipt_path':str(local(input_path)),'input_receipt_sha256':deps.sha(input_body),'bulk_input_pins':receipt['bulk_files'],
        'bulk_replay_sha256':receipt['bulk_independent_replay_sha256'],'runtime':runtime,'processing_files':sources(),'reviewed_dependencies':deps.pins(),'specification':spec,
        'event_denominator':96,'station_denominator':sum(len(e['targets']) for e in events),'event_order_sha256':selection.list_hash(e['event_id'] for e in events),
        'events':events,'cache':cache,'cache_provenance':cache_provenance,'metadata_requests':metadata,'waveform_batches':batches,
        'new_request_count':len(metadata)+sum(bool(b['slots']) for b in batches)}

def validate(plan_path,receipt_path):
    body=deps.read(local(plan_path),4*MIB);plan=json.loads(body);receipt_body=deps.read(local(receipt_path),MIB);receipt=json.loads(receipt_body)
    if receipt.get('version')!='geonet-counts-parent-receipt-v1' or receipt.get('acquisition_authorized') is not True or receipt.get('code_only_review_clean') is not True or not re.fullmatch('[0-9a-f]{40}',receipt.get('git_freeze_commit','')):raise ValueError('parent pushed source/review receipt required')
    fields=('processing_files','reviewed_dependencies','runtime','input_receipt_sha256','bulk_input_pins','bulk_replay_sha256')
    if receipt.get('plan_sha256')!=deps.sha(body) or any(receipt.get(f)!=plan.get(f) for f in fields) or plan!=make_plan(plan['input_receipt_path']):raise ValueError('frozen plan/source/input/runtime changed')
    return plan,deps.sha(body),deps.sha(receipt_body)

class ProvenanceError(RuntimeError):pass

def verified_cache_body(path,expected,cap):
    try:body=deps.read(path,cap)
    except MemoryError:raise
    except Exception as exc:raise ProvenanceError('frozen cached body unavailable') from exc
    if {'bytes':len(body),'sha256':deps.sha(body)}!=expected:raise ProvenanceError('frozen cached body checksum changed')
    return body

def xml_inventory(path,expected_pin=None):
    from obspy import read_inventory
    body=verified_cache_body(path,expected_pin,4*MIB) if expected_pin is not None else deps.read(path,4*MIB);text=body.decode('utf-8-sig')
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise ValueError('DTD/entity/NUL XML forbidden')
    return read_inventory(io.BytesIO(body),format='STATIONXML')

class ResourceLimit(RuntimeError):pass

def wave_headers(path,expected_pin=None):
    from obspy import read
    body=verified_cache_body(path,expected_pin,16*MIB) if expected_pin is not None else deps.read(path,16*MIB);headers=read(io.BytesIO(body),format='MSEED',headonly=True,details=True)
    counts=[int(tr.stats.npts) for tr in headers]
    if any(n<0 for n in counts):raise ValueError('negative declared sample count')
    if sum(counts)*8>64*MIB:raise ResourceLimit('declared decoded sample cap exceeded')
    return sum(counts),len(body)

def wave_decode(path,declared_count,expected_pin=None):
    from obspy import read
    body=verified_cache_body(path,expected_pin,16*MIB) if expected_pin is not None else deps.read(path,16*MIB)
    stream=read(io.BytesIO(body),format='MSEED',details=True)
    if sum(tr.data.nbytes for tr in stream)>64*MIB:raise ResourceLimit('actual decoded sample cap exceeded')
    if sum(int(tr.stats.npts) for tr in stream)!=declared_count:raise ValueError('decoded count differs from header')
    return stream

def fail_slots(targets,slots,reason,status):
    for r in targets:
        if r['slot'] not in slots:continue
        r.update(status=status,error=reason)
        for h,v in r['horizons'].items():
            if v['status']!='not_in_current_arrival_subset':r['horizons'][h]={'status':status,'reason':reason,'count_valid':False}

def checkpoint(out,plan,targets,completed=False):
    dump(out/'target_outcomes.json',targets);dump(out/'event_outcomes.json',screen.event_outcomes(plan['events'],targets));dump(out/'summary.json',screen.summary(plan['events'],targets,completed))

def worker(plan,out,plan_sha,receipt_sha,deadline,fetch_factory=None):
    lib=deps.module('downloader');core=deps.module('core');adapter=deps.module('adapter');targets=screen.initial_targets(plan['events']);lookup={r['slot']:r for r in targets}
    specs=plan['metadata_requests']+[b for b in plan['waveform_batches'] if b['slots']]
    raw=out/'raw';raw.mkdir();checkpoint(out,plan,targets)
    fetch=(fetch_factory or transport.factory(lib,deadline-OUTER,specs))(raw,max_seconds=max(0,deadline-time.monotonic()-RESERVE),max_bytes=512*MIB,max_requests=800,request_alarm=True)
    state={'completed':False,'plan_sha256':plan_sha,'parent_receipt_sha256':receipt_sha,'event_denominator':96,'station_denominator':len(targets),'processing_files':plan['processing_files'],
           'reviewed_dependencies':plan['reviewed_dependencies'],'runtime':plan['runtime'],'input_receipt_sha256':plan['input_receipt_sha256'],'outer_deadline_monotonic':deadline,'caps':plan['specification']['caps']}
    channel_paths={};channel_errors={};code=2;active_slots=set()
    def terminate(signum,frame):raise lib.LimitReached('parent cancellation')
    previous_term=signal.signal(signal.SIGTERM,terminate)
    def retrieve(r,cap):
        try:return fetch.fetch(r['url'],r['file'],cap)
        except Exception as exc:
            if isinstance(exc,(lib.LimitReached,TimeoutError,MemoryError)) or isinstance(getattr(exc,'reason',None),TimeoutError):raise
            return None
    try:
        # Every channel query is independent of every frozen waveform selection.
        # Store bytes on disk, never retain hundreds of decoded inventories.
        for r in plan['metadata_requests']:
            fetch.check();active_slots={r['slot']};lookup[r['slot']]['channel_retrieval_status']='attempting';checkpoint(out,plan,targets)
            body=retrieve(r,4*MIB)
            if body is not None:channel_paths[r['slot']]=raw/r['file']
            else:channel_errors[r['slot']]=fetch.log[-1].get('status','retrieval_failed')
            lookup[r['slot']]['channel_retrieval_status']='ok' if body is not None else channel_errors[r['slot']]
            del body;active_slots=set();checkpoint(out,plan,targets)
        for block,batch in enumerate(plan['waveform_batches']):
            fetch.check();batch_events=plan['events'][block*16:block*16+16]
            all_slots=[e['event_id']+'|'+t['station'] for e in batch_events for t in e['targets'] if t['queryable']]
            active_slots=set(all_slots)
            native=None;native_path=None;native_count=0;native_error=None
            if batch['slots']:
                body=retrieve(batch,16*MIB)
                if body is not None:native_path=raw/batch['file']
                else:native_error='waveform_retrieval:'+fetch.log[-1].get('status','failed')
                del body
            declared={};cache_errors={}
            if native_path is not None:
                try:native_count,_=wave_headers(native_path)
                except Exception as exc:
                    if isinstance(exc,(lib.LimitReached,TimeoutError,ResourceLimit,ProvenanceError,MemoryError)):raise
                    native_error=type(exc).__name__+': '+str(exc)[:200];native_path=None
            for slot in all_slots:
                cached=plan['cache'].get(slot,{}).get('waveform')
                lookup[slot]['waveform_source']='exact_cache' if cached else 'new_batch'
                lookup[slot]['waveform_retrieval_status']='cached_verified_success' if cached else 'new_success' if native_path is not None else native_error or 'unavailable'
                if cached:
                    try:
                        path=Path(cached['path'])
                        declared[slot]=wave_headers(path,cached['pin'])[0]
                    except Exception as exc:
                        if isinstance(exc,(lib.LimitReached,TimeoutError,ResourceLimit,ProvenanceError,MemoryError)):raise
                        cache_errors[slot]=type(exc).__name__+': '+str(exc)[:200]
            if (native_count+sum(declared.values()))*8>64*MIB:raise ResourceLimit('combined declared batch sample cap exceeded')
            if native_path is not None:
                try:native=wave_decode(native_path,native_count)
                except Exception as exc:
                    if isinstance(exc,(lib.LimitReached,TimeoutError,ResourceLimit,ProvenanceError,MemoryError)):raise
                    native_error=type(exc).__name__+': '+str(exc)[:200]
            for event in batch_events:
                for target in event['targets']:
                    slot=event['event_id']+'|'+target['station'];row=lookup[slot]
                    if not target['queryable']:continue
                    fetch.check();cache=plan['cache'].get(slot,{});stream=None
                    try:
                        if slot in cache_errors:raise ValueError(cache_errors[slot])
                        if cache.get('waveform'):stream=wave_decode(Path(cache['waveform']['path']),declared[slot],cache['waveform']['pin'])
                        elif native is not None:stream=native
                        else:raise ValueError(native_error or 'waveform_unavailable')
                        if slot not in channel_paths:raise ValueError('channel_metadata_unresolved:'+channel_errors.get(slot,'unattempted'))
                        inventory=xml_inventory(channel_paths[slot]);stronger=None;row['cached_response_status']='not_cached'
                        if cache.get('response'):
                            try:
                                p=Path(cache['response']['path'])
                                stronger=xml_inventory(p,cache['response']['pin']);row['cached_response_status']='decoded'
                            except Exception as exc:
                                if isinstance(exc,(lib.LimitReached,TimeoutError,ResourceLimit,ProvenanceError,MemoryError)):raise
                                row['cached_response_status']='cache_error';row['cached_response_error']=type(exc).__name__+': '+str(exc)[:200]
                        row.update(status='audited',horizons=screen.analyze(inventory,stream,event,target,core,adapter,stronger,lib.LimitReached))
                        del inventory,stronger
                    except Exception as exc:
                        if isinstance(exc,(lib.LimitReached,TimeoutError,ResourceLimit,ProvenanceError,MemoryError)):raise
                        fail_slots(targets,{slot},type(exc).__name__+': '+str(exc)[:200],'unresolved_engineering')
                    finally:
                        stream=None
                    active_slots.discard(slot);checkpoint(out,plan,targets)
            native=None;checkpoint(out,plan,targets)
        if fetch.clock()>=fetch.deadline:raise lib.LimitReached('time limit after final audit')
        state['completed']=True;code=0
    except Exception as exc:
        state['stop_reason']=type(exc).__name__+': '+str(exc)[:200]
        fail_slots(targets,active_slots,state['stop_reason'],'incomplete')
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGTERM,signal.SIG_IGN)
        dump(out/'requests.json',fetch.log);checkpoint(out,plan,targets,state['completed'])
        state.update(worker_elapsed_seconds=time.monotonic()-PROCESS_STARTED,request_attempts=len(fetch.log),response_body_bytes=fetch.bytes)
        state['files']={str(p.relative_to(out)):pin(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('manifest.json','native_worker.log')}
        dump(out/'manifest.json',state);signal.signal(signal.SIGTERM,previous_term)
    return code

class Deadline(RuntimeError):pass
def soft_stop(signum,frame):raise Deadline('counts parent deadline/cancellation')
def hard_watchdog(deadline,process):
    def stop(signum,frame):
        if process is not None and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        os._exit(2)
    signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))
def stop_child(process,deadline,graceful):
    if process is None or process.poll() is not None:return
    if graceful:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=max(.001,min(5,deadline-time.monotonic())));return
        except subprocess.TimeoutExpired:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    try:process.wait(timeout=max(.001,deadline-time.monotonic()))
    except subprocess.TimeoutExpired:os._exit(2)

def collect(plan_path,receipt_path,out):
    process=None;plan=None;reserved=False;code=None;deadline=PROCESS_STARTED+OUTER
    prior_term=signal.getsignal(signal.SIGTERM);prior_alarm=signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGTERM,soft_stop);signal.signal(signal.SIGALRM,soft_stop);signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-RESERVE-time.monotonic()))
        plan,plan_sha,receipt_sha=validate(plan_path,receipt_path);out=local(out);out.parent.mkdir(parents=True,exist_ok=True);out.mkdir();reserved=True
        checkpoint(out,plan,screen.initial_targets(plan['events']))
        dump(out/'manifest.json',{'completed':False,'initial_checkpoint':True,'event_denominator':96,'station_denominator':plan['station_denominator'],'plan_sha256':plan_sha,'parent_receipt_sha256':receipt_sha})
        with (out/'native_worker.log').open('xb') as log:
            process=subprocess.Popen([sys.executable,'-B',str(BASE/'counts.py'),'_worker','--plan',str(local(plan_path)),'--receipt',str(local(receipt_path)),'--output',str(out),'--deadline',str(deadline)],stdout=log,stderr=log,start_new_session=True)
            code=process.wait(timeout=max(.001,deadline-RESERVE-time.monotonic()))
        state=load(out/'manifest.json',2*MIB)
        if state.get('initial_checkpoint'):raise RuntimeError('worker final manifest missing')
        if code!=0:raise RuntimeError('worker exited unsuccessfully: '+str(code))
        state.update(worker_exit_code=code,outer_elapsed_seconds=time.monotonic()-PROCESS_STARTED);state['files']['native_worker.log']=pin(out/'native_worker.log',4*MIB);dump(out/'manifest.json',state)
        return code
    except BaseException as exc:
        signal.signal(signal.SIGTERM,signal.SIG_IGN);hard_watchdog(deadline,process)
        if reserved:dump(out/'outer_interruption.json',{'completed':False,'stop_type':type(exc).__name__,'worker_exit_code':code,'event_denominator':96,'station_denominator':plan['station_denominator'],'plan_sha256':plan_sha,'parent_receipt_sha256':receipt_sha})
        stop_child(process,deadline,True)
        if reserved:
            state=load(out/'manifest.json',2*MIB);state.update(completed=False,files={},artifact_pins_incomplete=True,worker_exit_code=code);dump(out/'manifest.json',state)
            if (out/'requests.json').exists():
                attempts=load(out/'requests.json',32*MIB)
                for r in attempts:
                    sidecar=out/'raw'/(r['file']+'.received')
                    if sidecar.exists():
                        body=deps.read(sidecar,16*MIB);r.update(bytes=len(body),sha256=deps.sha(body),status='interrupted');dump(out/'requests.json',attempts);sidecar.replace(out/'raw'/r['file'])
                dump(out/'requests.json',attempts)
            targets=load(out/'target_outcomes.json',GENERATED_CAP);checkpoint(out,plan,targets,False)
        raise
    finally:
        if process is not None and process.poll() is None:hard_watchdog(deadline,process);stop_child(process,deadline,False)
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGTERM,prior_term);signal.signal(signal.SIGALRM,prior_alarm)

def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('prepare');p.add_argument('--inputs',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    for name in ('collect','_worker'):
        p=sub.add_parser(name);p.add_argument('--plan',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
        if name=='_worker':p.add_argument('--deadline',type=float,required=True)
    args=parser.parse_args()
    if args.mode=='prepare':
        plan=make_plan(args.inputs);dest=local(args.plan);dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('x') as f:f.write(json.dumps(plan,indent=2,sort_keys=True,allow_nan=False)+'\n')
        return 0
    if args.mode=='collect':return collect(args.plan,args.receipt,args.output)
    plan,plan_sha,receipt_sha=validate(args.plan,args.receipt);out=local(args.output)
    if not 0<args.deadline-time.monotonic()<=OUTER or not (out/'manifest.json').exists() or not load(out/'manifest.json').get('initial_checkpoint') or (out/'raw').exists():raise ValueError('fresh parent reservation/shared deadline required')
    return worker(plan,out,plan_sha,receipt_sha,args.deadline)

if __name__=='__main__':sys.exit(main())

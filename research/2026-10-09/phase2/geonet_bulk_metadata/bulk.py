#!/usr/bin/env python3
"""Frozen metadata-only preparation/collection. collect requires a parent receipt."""
import time
PROCESS_STARTED=time.monotonic()
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import types
import urllib.parse

import aggregate
import origin
import sampling
import transport

BASE=Path(__file__).resolve().parent
INPUT=BASE.parent/'geonet_tail_census'/'local_runs'/'recovery_20261010'
LIBRARY=BASE.parent/'geonet_tail_census'/'census.py'
LIBRARY_SHA='076c9fcb419b801c91fa95a01cec21f708284887f6dfae8e7878b513ba1780b8'
REQUIRED_PYTHON_SHA='2477b47fa3ae65b9574eb18a15edb364e96948eaa1875ad3f1c80d780efc9c12'
FILES=('bulk.py','sampling.py','origin.py','aggregate.py','transport.py','test_bulk.py','PROTOCOL_v1.md','sample_specification.json','census_input_pins.json','IMPLEMENTATION.md')
FINALIZATION_RESERVE=10
MIB=1024*1024
GENERATED_CAP=1024*MIB
CAPS={'planned_event_queries':346,'total_new_attempt_ceiling':400,'total_response_body_bytes_ceiling':128*MIB,
      'per_event_body_bytes_ceiling':4*MIB,'outer_seconds':1800,'per_request_seconds':20,
      'minimum_request_start_spacing_seconds':1,'retries':0,'redirects':0,'replacement_events':0,
      'automatic_resume':False,'source_refetch':False,'AWS_actions':0}


class Deadline(RuntimeError):pass


def alarm(signum,frame):raise Deadline('1800-second outer launch deadline')


def parent_terminate(signum,frame):raise Deadline('collecting parent SIGTERM cancellation')


def hard_watchdog(deadline,process):
    def stop(signum,frame):
        if process is not None and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        # Preserve existing atomic checkpoints; never extend the launch for cleanup.
        os._exit(2)
    signal.signal(signal.SIGALRM,stop)
    signal.setitimer(signal.ITIMER_REAL,max(.001,deadline-time.monotonic()))


def sha(body):return hashlib.sha256(body).hexdigest()


def read(path,cap):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError('regular nonsymlink input required')
    if path.stat().st_size>cap:raise ValueError('bounded input size exceeded')
    with path.open('rb') as f:body=f.read(cap+1)
    if len(body)>cap:raise ValueError('bounded input grew')
    return body


def load(path,cap=2*MIB):return json.loads(read(path,cap))


def artifact_pin(path,cap=GENERATED_CAP):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>cap:raise ValueError('generated artifact ceiling exceeded')
    total=0;digest=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(65536):
            total+=len(chunk)
            if total>cap:raise ValueError('generated artifact grew past ceiling')
            digest.update(chunk)
    return {'bytes':total,'sha256':digest.hexdigest()}


def dump(path,obj):
    temporary=path.with_name(path.name+'.temporary.'+str(os.getpid()))
    temporary.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n')
    temporary.replace(path)


def local(path):
    allowed=BASE/'local_runs'
    if allowed.is_symlink():raise ValueError('local_runs cannot be a symlink')
    path=Path(path)
    if path.is_symlink():raise ValueError('local destination cannot be a symlink')
    resolved=path.resolve()
    if not resolved.is_relative_to(allowed) or resolved==allowed:raise ValueError('destination must be inside this helper local_runs')
    return resolved


def runtime():
    binary=Path(sys.executable).resolve()
    return {'executable':str(Path(sys.executable).absolute()),'resolved_executable':str(binary),
            'binary_sha256':sha(read(binary,128*MIB)),'version':sys.version,
            'cache_tag':sys.implementation.cache_tag,'machine':os.uname().machine,
            'stdlib_only':True,'installations':0}


def sources():return {name:sha(read(BASE/name,4*MIB)) for name in FILES}


def library():
    body=read(LIBRARY,4*MIB)
    if sha(body)!=LIBRARY_SHA:raise ValueError('reviewed census library checksum changed')
    module=types.ModuleType('checksum_pinned_census');module.__file__=str(LIBRARY)
    exec(compile(body,str(LIBRARY),'exec'),module.__dict__)
    return module


def utc_compatibility(lib):
    for width in range(1,7):
        digits='123456'[:width]
        expected=dt.datetime(2020,1,1,microsecond=int(digits.ljust(6,'0')),tzinfo=dt.timezone.utc)
        try:actual=lib.utc('2020-01-01T00:00:00.'+digits+'Z')
        except (ValueError,OverflowError) as exc:raise ValueError('reviewed UTC fractional-width runtime incompatible') from exc
        if actual!=expected:raise ValueError('reviewed UTC fractional-width semantics changed')


def inputs():
    pins=load(BASE/'census_input_pins.json')
    if set(pins)!={'manifest.json','groups.json','rows.json','outcomes.json','query_order.json','summary.json','requests.json'}:raise ValueError('input pin membership changed')
    objects={}
    for name,pin in pins.items():
        if not re.fullmatch('[0-9a-f]{64}',pin):raise ValueError('invalid input checksum')
        body=read(INPUT/name,32*MIB)
        if sha(body)!=pin:raise ValueError('census input checksum changed: '+name)
        objects[name]=json.loads(body)
    m=objects['manifest.json']
    if not m.get('completed'):raise ValueError('census must be completed')
    return pins,objects


def query(eid):
    # Reuse the exact reviewed census event endpoint; default service includes arrivals.
    return 'https://service.geonet.org.nz/fdsnws/event/1/query?'+urllib.parse.urlencode({'eventid':eid})


def make_plan():
    pins,obj=inputs();spec=load(BASE/'sample_specification.json')
    actual_runtime=runtime()
    if actual_runtime['version']!=obj['manifest.json'].get('python') or actual_runtime['binary_sha256']!=REQUIRED_PYTHON_SHA:raise ValueError('exact original census Python 3.14.5 runtime required')
    lib=library();utc_compatibility(lib)
    if spec['caps']!=CAPS:raise ValueError('frozen caps changed')
    new,tail,denominators,rejected=sampling.select(obj['groups.json'],spec)
    tail_ids={r['event_id'] for r in tail}
    if tail_ids!=set(obj['query_order.json']) or tail_ids!=set(obj['outcomes.json']):raise ValueError('reused tail identity set changed')
    if len(obj['query_order.json'])!=len(tail_ids):raise ValueError('duplicate original tail query identity')
    raw_pins={}
    for entry in obj['requests.json']:
        eid=Path(entry['file']).stem
        if eid not in tail_ids:continue
        name='raw/'+entry['file'];pinned=obj['manifest.json']['files'][name]
        if eid in raw_pins or entry['file']!=eid+'.xml' or entry['url']!=query(eid) or entry['status']!='ok':raise ValueError('original tail request provenance changed')
        if pinned!={'bytes':entry['bytes'],'sha256':entry['sha256']}:raise ValueError('original tail artifact/request pin mismatch')
        body=read(INPUT/name,4*MIB)
        if len(body)!=pinned['bytes'] or sha(body)!=pinned['sha256']:raise ValueError('tail raw checksum changed')
        # Compatibility is a preparation/prelaunch invariant, before any output
        # reservation or request, rather than an after-start worker discovery.
        if lib.parse_quakeml(body,eid)!=obj['outcomes.json'][eid]:raise ValueError('prelaunch reused parser outcome changed')
        raw_pins[eid]={'relative_file':name,**pinned}
    if set(raw_pins)!=tail_ids:raise ValueError('missing reused raw artifact')
    groups={g['event_id']:g for g in obj['groups.json']}
    rows=[]
    for source,items in (('new_lower_M',new),('reused_tail',tail)):
        for item in items:
            group=groups[item['event_id']]
            row=dict(item,source=source,cmt_methods=group['methods'],cmt_row_indices=group['row_indices'],external_wphase=group['external_wphase'])
            if source=='new_lower_M':row['query_url']=query(item['event_id'])
            else:row.update(inclusion_probability=1.0,inverse_probability=1.0,reused_artifact=raw_pins[item['event_id']])
            rows.append(row)
    return {'version':'geonet-bulk-metadata-plan-v1','processing_files':sources(),'library_sha256':LIBRARY_SHA,
            'input_pins':pins,'runtime':actual_runtime,'caps':CAPS,'selected_set_sha256':spec['selected_set_sha256'],
            'query_order_sha256':spec['query_order_sha256'],'denominators':denominators,'rejected_group_denominator':len(rejected),
            'rejected_group_reasons':dict(sorted(__import__('collections').Counter(x for r in rejected for x in r['reasons']).items())),
            'combined_denominator':len(rows),'new_denominator':len(new),'reused_denominator':len(tail),'rows':rows}


def validate(plan_path,receipt_path):
    plan_path=local(plan_path);receipt_path=local(receipt_path)
    body=read(plan_path,2*MIB);plan=json.loads(body);receipt=load(receipt_path,1*MIB)
    if (receipt.get('version')!='geonet-bulk-parent-receipt-v1' or receipt.get('acquisition_authorized') is not True
        or receipt.get('code_only_review_clean') is not True or not re.fullmatch('[0-9a-f]{40}',receipt.get('git_freeze_commit',''))):raise ValueError('parent pre-acquisition Git/review receipt required')
    if receipt.get('plan_sha256')!=sha(body) or receipt.get('processing_files')!=plan.get('processing_files'):raise ValueError('receipt plan/source mismatch')
    if receipt.get('library_sha256')!=LIBRARY_SHA or receipt.get('input_pins')!=plan.get('input_pins') or receipt.get('runtime')!=plan.get('runtime'):raise ValueError('receipt library/input/runtime mismatch')
    if plan!=make_plan():raise ValueError('frozen execution plan changed')
    return plan,sha(body),sha(read(receipt_path,1*MIB))


def placeholders(plan):return [dict(row,outcome_status='unattempted' if row['source']=='new_lower_M' else 'reuse_pending') for row in plan['rows']]


def parse_row(lib,body,row):
    status='parsed'
    try:base=lib.parse_quakeml(body,row['event_id'])
    except (UnicodeError,ValueError,OverflowError,lib.ET.ParseError) as exc:
        base={'event_id':row['event_id'],'status':'parse_failed','error_type':type(exc).__name__};status='parse_failed'
    return dict(row,outcome_status=status,base=base,origin=origin.offline_origin(lib,body,row['event_id'],row['cmt_time'],base))


def execute(plan,out,plan_sha,receipt_sha,fetch_factory=None,outer_deadline=None):
    """Worker transaction. Tests inject a fake fetcher; production uses pinned Fetcher."""
    lib=library();spec=load(BASE/'sample_specification.json');rows=placeholders(plan)
    state={'version':'geonet-bulk-metadata-run-v1','completed':False,'stop_reason':None,'plan_sha256':plan_sha,
           'parent_receipt_sha256':receipt_sha,'processing_files':plan['processing_files'],'library_sha256':LIBRARY_SHA,
           'input_pins':plan['input_pins'],'runtime':plan['runtime'],'caps':CAPS,'new_denominator':plan['new_denominator'],
           'reused_denominator':plan['reused_denominator'],'combined_denominator':plan['combined_denominator']}
    # Persist all denominators before any raw reuse, network call or import-heavy parse.
    dump(out/'outcomes.json',rows);dump(out/'summary.json',aggregate.summarize(rows,plan['denominators'],spec,False))
    (out/'raw').mkdir();outer_deadline=outer_deadline or PROCESS_STARTED+1800
    remaining=max(0,outer_deadline-time.monotonic()-FINALIZATION_RESERVE)
    fetch=(fetch_factory or transport.factory(lib,outer_deadline-1800))(out/'raw',max_seconds=remaining,max_bytes=128*MIB,max_requests=400,request_alarm=True)
    def terminate(signum,frame):raise lib.LimitReached('parent interruption')
    prior_term=signal.signal(signal.SIGTERM,terminate)
    code=2
    try:
        old=load(INPUT/'outcomes.json',32*MIB)
        for i,row in enumerate(rows):
            if row['source']!='reused_tail':continue
            fetch.check();pin=row['reused_artifact'];body=read(INPUT/pin['relative_file'],4*MIB)
            if len(body)!=pin['bytes'] or sha(body)!=pin['sha256']:raise ValueError('reused artifact changed')
            parsed=parse_row(lib,body,row)
            if parsed['base']!=old[row['event_id']]:raise ValueError('reused reviewed parser outcome changed')
            parsed['outcome_status']='reused_verified';rows[i]=parsed
            dump(out/'outcomes.json',rows)
        for i,row in enumerate(rows):
            if row['source']!='new_lower_M':continue
            fetch.check();attempts=len(fetch.log)
            try:
                body=fetch.fetch(row['query_url'],row['event_id']+'.xml',4*MIB)
                rows[i]=parse_row(lib,body,row)
            except lib.LimitReached:
                if len(fetch.log)>attempts:rows[i]=dict(row,outcome_status='incomplete')
                raise
            except TimeoutError:
                if len(fetch.log)>attempts:rows[i]=dict(row,outcome_status='incomplete',error_type='TimeoutError')
                raise
            except Exception as exc:
                if isinstance(getattr(exc,'reason',None),TimeoutError):
                    rows[i]=dict(row,outcome_status='incomplete',error_type='TimeoutError');raise
                rows[i]=dict(row,outcome_status='retrieval_failed' if not fetch.log or fetch.log[-1]['status']!='ok' else 'parse_failed',error_type=type(exc).__name__)
            dump(out/'outcomes.json',rows)
        state['completed']=True;code=0
    except Exception as exc:state['stop_reason']=type(exc).__name__+': '+str(exc)[:200]
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        dump(out/'requests.json',fetch.log)
        state.update(worker_elapsed_seconds=time.monotonic()-PROCESS_STARTED,request_attempts=len(fetch.log),response_body_bytes=fetch.bytes)
        dump(out/'outcomes.json',rows);dump(out/'summary.json',aggregate.summarize(rows,plan['denominators'],spec,state['completed']))
        state['files']={str(p.relative_to(out)):artifact_pin(p)
                        for p in sorted(out.rglob('*')) if p.is_file() and p.name not in ('manifest.json','native_worker.log')}
        dump(out/'manifest.json',state)
        signal.signal(signal.SIGTERM,prior_term)
    return code


def collect(plan_path,receipt_path,out):
    # The parent alarm starts from initial module loading, before all validation.
    prior_term=signal.getsignal(signal.SIGTERM);prior_alarm=signal.getsignal(signal.SIGALRM)
    process=None;plan=None;reserved=False
    try:
        signal.signal(signal.SIGTERM,parent_terminate)
        signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,1800-FINALIZATION_RESERVE-(time.monotonic()-PROCESS_STARTED)))
        plan,pin,receipt_pin=validate(plan_path,receipt_path)
        out=local(out);out.parent.mkdir(parents=True,exist_ok=True);out.mkdir();reserved=True
        # Durable denominator skeleton also survives a child initialization failure.
        dump(out/'outcomes.json',placeholders(plan))
        dump(out/'summary.json',aggregate.summarize(placeholders(plan),plan['denominators'],load(BASE/'sample_specification.json'),False))
        dump(out/'manifest.json',{'completed':False,'initial_denominator_checkpoint':True,'plan_sha256':pin,'parent_receipt_sha256':receipt_pin,
                                 'new_denominator':plan['new_denominator'],'reused_denominator':plan['reused_denominator'],'combined_denominator':plan['combined_denominator']})
        with (out/'native_worker.log').open('xb') as log:
            process=subprocess.Popen([sys.executable,'-B',str(BASE/'bulk.py'),'_worker','--plan',str(local(plan_path)),
                                      '--receipt',str(local(receipt_path)),'--output',str(out),'--outer-deadline',str(PROCESS_STARTED+1800)],stdout=log,stderr=log,start_new_session=True)
            code=process.wait(timeout=max(.001,1800-FINALIZATION_RESERVE-(time.monotonic()-PROCESS_STARTED)))
        state=load(out/'manifest.json',2*MIB)
        if state.get('initial_denominator_checkpoint'):raise RuntimeError('worker exited without final manifest')
        if code!=0:state['completed']=False
        state.update(outer_elapsed_seconds=time.monotonic()-PROCESS_STARTED,worker_exit_code=code)
        logbody=read(out/'native_worker.log',4*MIB);state['files']['native_worker.log']={'bytes':len(logbody),'sha256':sha(logbody)}
        dump(out/'manifest.json',state)
        return code
    except BaseException as exc:
        # Further soft cancellation cannot interrupt child shutdown or recovery;
        # the absolute hard watchdog remains independent throughout cleanup.
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        hard_watchdog(PROCESS_STARTED+1800,process)
        if reserved:
            # The marker is durable before waiting or reconciling large artifacts;
            # its presence forbids a completed scientific interpretation.
            dump(out/'outer_interruption.json',{'completed':False,'stop_type':type(exc).__name__,
                 'new_denominator':plan['new_denominator'],'reused_denominator':plan['reused_denominator'],
                 'combined_denominator':plan['combined_denominator'],'outer_elapsed_seconds':time.monotonic()-PROCESS_STARTED,
                 'plan_sha256':pin,'parent_receipt_sha256':receipt_pin})
        if process is not None and process.poll() is None:
            remaining=PROCESS_STARTED+1800-time.monotonic()
            if remaining>0:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=min(FINALIZATION_RESERVE/2,remaining))
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait(timeout=max(.001,PROCESS_STARTED+1800-time.monotonic()))
            else:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                process.wait(timeout=max(.001,PROCESS_STARTED+1800-time.monotonic()))
        if reserved:
            # Child termination is now confirmed before reading or rewriting
            # worker-owned checkpoints, even after a forced SIGKILL.
            state=load(out/'manifest.json',2*MIB)
            state.update(completed=False,files={},artifact_pins_incomplete=True,outer_stop_type=type(exc).__name__)
            dump(out/'manifest.json',state)
            # Preserve checkpoints; recompute aggregate from the last atomic all-row file.
            rows=load(out/'outcomes.json',GENERATED_CAP)
            # A killed worker may leave an in-flight chunk sidecar. Reconcile it
            # without parsing, requesting or completing that scientific outcome.
            if (out/'requests.json').exists():
                attempts=load(out/'requests.json',32*MIB)
                interrupted_ids=set()
                for entry in attempts:
                    sidecar=out/'raw'/(entry['file']+'.received')
                    if sidecar.exists():
                        body=read(sidecar,4*MIB);entry.update(bytes=len(body),sha256=sha(body),status='interrupted')
                        dump(out/'requests.json',attempts)
                        sidecar.replace(out/'raw'/entry['file'])
                    if entry.get('status') in ('started','in_flight','interrupted'):interrupted_ids.add(Path(entry['file']).stem)
                    if any(r['event_id']==Path(entry['file']).stem and r['outcome_status']=='unattempted' for r in rows):interrupted_ids.add(Path(entry['file']).stem)
                rows=[dict(r,outcome_status='incomplete',error_type='OuterInterruption') if r['event_id'] in interrupted_ids and r['outcome_status']=='unattempted' else r for r in rows]
                dump(out/'requests.json',attempts);dump(out/'outcomes.json',rows)
            dump(out/'summary.json',aggregate.summarize(rows,plan['denominators'],load(BASE/'sample_specification.json'),False))
            if (out/'manifest.json').exists():
                state=load(out/'manifest.json',2*MIB);state.update(completed=False,files={},artifact_pins_incomplete=True,outer_stop_type=type(exc).__name__);dump(out/'manifest.json',state)
        raise
    finally:
        # Recovery itself can fail (including filesystem errors). A live child
        # must still be stopped before this parent's independent timer is disarmed.
        if process is not None and process.poll() is None:
            hard_watchdog(PROCESS_STARTED+1800,process)
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:process.wait(timeout=max(.001,PROCESS_STARTED+1800-time.monotonic()))
            except subprocess.TimeoutExpired:os._exit(2)
        signal.setitimer(signal.ITIMER_REAL,0)
        signal.signal(signal.SIGTERM,prior_term)
        signal.signal(signal.SIGALRM,prior_alarm)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('prepare','collect','_worker'))
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--receipt',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--outer-deadline',type=float)
    args=parser.parse_args()
    if args.mode=='prepare':
        prepared=make_plan();plan=local(args.plan);plan.parent.mkdir(parents=True,exist_ok=True)
        with plan.open('x') as f:json.dump(prepared,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
        return 0
    if args.receipt is None or args.output is None:parser.error('collection requires parent receipt and output')
    if args.mode=='collect':return collect(args.plan,args.receipt,args.output)
    # Direct worker calls retain the same source/input/runtime/receipt gate.
    if args.outer_deadline is None or not __import__('math').isfinite(args.outer_deadline) or args.outer_deadline>PROCESS_STARTED+1800:raise ValueError('shared parent deadline required')
    signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,args.outer_deadline-time.monotonic()-FINALIZATION_RESERVE))
    plan,pin,receipt_pin=validate(args.plan,args.receipt);out=local(args.output)
    if not out.is_dir() or (out/'raw').exists() or not load(out/'manifest.json').get('initial_denominator_checkpoint'):raise ValueError('fresh parent-reserved worker output required')
    return execute(plan,out,pin,receipt_pin,outer_deadline=args.outer_deadline)


if __name__=='__main__':sys.exit(main())

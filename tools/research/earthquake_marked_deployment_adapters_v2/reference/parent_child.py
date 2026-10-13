"""Fresh contained stage dispatch around an injected, positively bound processor."""
import time
from controller import (CAP,STUDY,FEATURE,FEATURE_STUDY,ORDER,Journal,artifact_name,canonical,
                        gate_check,identity,need,number,pin,receipt_ok,stage_spec)


def execute(request,store,adapter,*,source_begin,clock=time.monotonic):
    """ROOT captures source_begin before all imports, not immediately before this call.

    adapter.bind(request, raw_inputs) verifies whole reviewed source/runtime maps and
    returns processor, bindings, numeric, packet, strong_results. It must never load
    a scientific module until its source and runtime have been positively verified.
    """
    g=request['gate']; spec=request['stage']; i=spec['index']; journal=Journal(store,g['storage_limit_bytes'])
    report=dict(schema='marked-sixfit-child-report-v1',index=i,gate_sha256=identity(g),request_pin=pin(canonical(request)),
                status='incomplete',result_pin=None,within_source=False,within_experiment=False,callbacks=[],failure=None,exception_evidence_pin=None)
    def check():
        now=clock(); need(number(source_begin) and 0<=g['experiment_begin']<=request['dispatch_begin']<=source_begin<=now,'source_clock')
        need(now-source_begin<=spec['source_seconds'],'source_deadline'); need(now<=g['experiment_begin']+7200,'experiment_deadline')
        need(now<=request['authority']['expires'],'authority_deadline')
    try:
        check(); gate_check(g,clock()); need(request['schema']=='marked-sixfit-stage-request-v1' and request['gate_sha256']==identity(g)
             and spec==stage_spec(g,i),'request')
        # Authorization was obtained before dispatch. Do not demand another full
        # manager interval after process startup; verify the original lease instead.
        receipt_ok(request['authority'],g,spec,request['dispatch_begin'])
        need(journal.read(artifact_name(i,'claim.json'))==canonical(request),'exclusive_claim')
        live=adapter.live(spec['unit'])
        need(live==dict(unit=spec['unit'],active=True,limits=spec['limits'],runtime_max_seconds=spec['manager_seconds']), 'live_unit_caps')
        check()
        raw_inputs={}
        for name,expected in g['input_pins'].items():
            check(); raw=adapter.load(name,expected); need(type(raw) is bytes and len(raw)<=16*1024*1024 and pin(raw)==expected,'input_binding'); raw_inputs[name]=raw
        bound=adapter.bind(request,raw_inputs)
        need(type(bound) is dict and set(bound)=={'processor','bindings','numeric','packet','strong_results','binding_receipt'},'bound_modules')
        need(bound['binding_receipt']==dict(verified=True,gate_sha256=identity(g),source_pins=g['source_pins'],runtime_pin=g['runtime_pin'],input_pins=g['input_pins']),'bound_receipt')
        op,ns,packet=bound['processor'],bound['numeric'],bound['packet']
        need(packet['schema']==FEATURE and packet['study']==FEATURE_STUDY,'feature_v1')
        check(); count=dict(initial=0,step=0,forecast=0); terminal=False; began=False
        def previous(index):
            value=request['previous'][str(index)]
            need(value['name']==artifact_name(index,'result.json'),'previous_name')
            return journal.read(value['name'],value['pin'])
        admission_raw=previous(0) if i else None
        admission=ns.decode(admission_raw,pin(admission_raw)['sha256']) if i else None
        def emit(kind,raw):
            nonlocal terminal,began
            need(type(raw) is bytes and len(raw)<=CAP,'callback_cap'); value=ns.decode(raw,pin(raw)['sha256'])
            failure=kind in ('admission_failure','failure','score_failure')
            # Retain processor failure evidence even when the source clock expired.
            if not failure: check(); need(not terminal,'callback_after_terminal')
            if failure:
                need(kind=={'admission':'admission_failure','fit':'failure','score':'score_failure'}.get(spec['kind']),'failure_kind')
                name='failure.json'; terminal=True
            elif spec['kind']=='admission':
                if kind=='initial':
                    n=count['initial']; need(n<6 and (value['seed'],value['arm'])==ORDER[n] and value['status']=='initial' and value['update']==0 and value['study']==STUDY,'initial_order')
                    name='initial_%02d.json'%n; count['initial']+=1
                else:
                    need(kind=='admission' and count['initial']==6 and value['status']=='admitted' and value['study']==STUDY,'admission_terminal')
                    name='result.json'; terminal=True
            elif spec['kind']=='fit':
                need(value['study']==STUDY and (value['seed'],value['arm'])==(spec['seed'],spec['arm']),'fit_identity')
                if kind=='begin_fit':
                    need(not began and count['step']==0 and value['status']=='initial' and value['update']==0,'begin_once'); name='begin_fit.json'; began=True
                elif kind=='step':
                    need(began and count['step']<300 and value['status']=='partial' and type(value['update']) is int and value['update']==count['step']+1
                         and len(value['history'])==value['update'],'update_order')
                    need([x['update'] for x in value['history']]==list(range(1,value['update']+1)),'history_order')
                    name='latest_update.json'; count['step']+=1
                else:
                    need(kind=='final' and began and count['step']==300 and value['status']=='final' and value['update']==300 and len(value['history'])==300,'final300')
                    name='result.json'; terminal=True
            elif spec['kind']=='score':
                need((value['seed'],value['arm'])==(spec['seed'],spec['arm']),'score_identity')
                if kind=='forecast':
                    n=count['forecast']; expected=[(r,h) for r in admission['schema']['dev'] for h in (1,3,5)]
                    need(n<66 and value['status']=='complete' and (value['ordinal'],value['horizon'])==expected[n],'forecast_order')
                    name='forecast_%02d.json'%n; count['forecast']+=1
                else:
                    need(kind=='score_final' and count['forecast']==66 and value['status']=='complete' and value['study']==STUDY
                         and value['no_optimizer'] is True and len(value['predictions'])==66,'score66')
                    name='result.json'; terminal=True
            else: raise ValueError('aggregate_callback')
            p=journal.put(artifact_name(i,name),raw,replace=kind=='step')
            if kind=='step':
                journal.object(artifact_name(i,'update_%03d.json'%count['step']),dict(update=count['step'],checkpoint_pin=p,history_last=value['history'][-1]))
            report['callbacks'].append(dict(kind=kind,name=name,pin=p))
            if not failure: check()
            return dict(status='durable',sha256=p['sha256'])
        if spec['kind']=='admission':
            raw=op.prepare(packet,bound['bindings'],emit,processing_begin=source_begin)
            need(terminal and count['initial']==6,'admission_missing'); need(journal.read(artifact_name(i,'result.json'))==raw,'admission_return')
        elif spec['kind']=='fit':
            result=op.fit_one(packet,admission_raw,pin(admission_raw)['sha256'],bound['bindings'],emit,seed=spec['seed'],arm=spec['arm'],processing_begin=source_begin)
            raw=result['checkpoint']; need(result['status']=='complete' and terminal and count['step']==300 and journal.read(artifact_name(i,'result.json'))==raw,'fit_return')
        elif spec['kind']=='score':
            checkpoint=previous(i-1)
            result=op.score_final(packet,admission_raw,pin(admission_raw)['sha256'],checkpoint,pin(checkpoint)['sha256'],bound['bindings'],emit,processing_begin=source_begin)
            raw=result['result']; need(result['status']=='complete' and terminal and count['forecast']==66 and journal.read(artifact_name(i,'result.json'))==raw,'score_return')
        else:
            new=[ns.decode(previous(j),request['previous'][str(j)]['pin']['sha256']) for j in (2,4,6,8,10,12)]
            result=op.aggregate(packet,admission_raw,pin(admission_raw)['sha256'],new,bound['strong_results'],bound['bindings'],processing_begin=source_begin)
            raw=ns.encode(result); journal.put(artifact_name(i,'result.json'),raw)
            need(result['status']=='complete' and type(result['pass_all']) is bool,'aggregate_incomplete')
        # Save full processor output before final expiry checks; no report truncation.
        report['result_pin']=pin(raw); check(); report['status']='complete'
    except Exception as exc:
        report['failure']=dict(type=type(exc).__name__,reason=str(exc)[:512])
        # Frozen processor failures can carry the current gradients/IEEE evidence
        # even when its own failure callback could not finish. Preserve it separately.
        if 'op' in locals() and hasattr(exc,'evidence'):
            try:
                raw_failure=ns.encode(op.failure_numeric(exc.evidence))
                report['exception_evidence_pin']=journal.put(artifact_name(i,'exception_evidence.json'),raw_failure)
            except Exception:
                report['failure']['exception_evidence_unverified']=True
    now=clock()
    report['within_source']=number(source_begin) and 0<=source_begin<=now and now-source_begin<=spec['source_seconds']
    report['within_experiment']=now<=g['experiment_begin']+7200
    if not report['within_source'] or not report['within_experiment']: report['status']='incomplete'
    # This is the complete result envelope, written even for expired/failed stages.
    try:
        journal.object(artifact_name(i,'child_report.json'),report)
        check()
    except Exception as exc:
        report['status']='incomplete'; report['failure']=dict(type=type(exc).__name__,reason=str(exc)[:512])
        try: journal.object(artifact_name(i,'child_late_or_failed.json'),report)
        except Exception: pass
    return report

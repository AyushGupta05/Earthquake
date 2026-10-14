"""Nine-stage contained dispatch; science and all authority positively injected."""
import time
import control as c
import secure_io as io

CODEC_CAP=2*1024*1024


def execute(request,j,adapter,*,expected_config_pin,source_begin,clock=time.monotonic):
    g=request['config'];s=request['stage'];i=s['index']
    report=dict(schema='shared-reference-AR-L-child-report-v1',stage=i,config_pin=request['config_pin'],request_pin=io.pin(io.canonical(request)),status='incomplete',result_pin=None,claim_pin=None,within_source=False,within_experiment=False,callbacks=[],failure=None,exception_evidence_pin=None)
    receipt=None;bound=None
    def check():
        now=clock();io.need(c.finite(source_begin) and 0<=g['whole_begin']<=request['dispatch_begin']<=source_begin<=now,'source_clock')
        io.need(now-source_begin<=s['source_seconds'],'source_deadline');io.need(now<=g['whole_begin']+7200 and now<=g['lease_deadline'],'whole_deadline')
        io.need(now<=request['parent_authority']['expires'] and (receipt is None or now<=receipt['expires']),'authority_deadline')
    try:
        check();c.config_check(g,clock(),expected_config_pin);io.need(request['config_pin']==expected_config_pin,'child_held_config_pin')
        io.need(type(request)is dict and set(request)=={'schema','config','config_pin','stage','dispatch_begin','previous','parent_authority'} and request['schema']=='shared-reference-AR-L-stage-request-v1' and s==c.spec(g,i) and type(request['previous'])is list and len(request['previous'])==i,'request')
        io.need(request['parent_authority']['scope']==c.scope(g,s,'parent') and request['parent_authority']['decision']=='authorized','parent_scope')
        io.need(j.read(i,'dispatch.json')==io.canonical(request),'dispatch_once')
        receipt=c.authorize(g,s,'child',adapter,clock());io.need(receipt['expires']<=request['parent_authority']['expires'],'child_lease_extension')
        io.need(adapter.live(s['unit'])==dict(unit=s['unit'],active=True,limits=s['limits'],runtime_max_seconds=s['manager_seconds']),'live_unit_caps')
        claim=dict(schema='shared-reference-AR-L-child-claim-v1',stage=i,request_pin=report['request_pin'],config_pin=request['config_pin'],authority=receipt)
        report['claim_pin']=io.pin(io.canonical(claim));j.object(i,'claim.json',claim)
        check();raw_inputs={}
        for name,expected in g['input_pins'].items():
            check();raw=adapter.load(name,expected);io.need(type(raw)is bytes and len(raw)<=16*1024*1024 and io.pin(raw)==expected,'input_binding');raw_inputs[name]=raw
        # The ROOT binder verifies full closed source/runtime/globals BEFORE science imports.
        bound=adapter.bind(request,raw_inputs)
        keys={'processor','bindings','numeric','packet','original_admission','reused_results','strong_results','closed_comparator_report','origins','auditor','binding_receipt'}
        io.need(type(bound)is dict and set(bound)==keys,'bound_modules')
        io.need(bound['binding_receipt']==dict(verified=True,config_pin=request['config_pin'],source_pins=g['source_pins'],runtime_pin=g['runtime_pin'],input_pins=g['input_pins']),'binding_receipt')
        op=bound['processor'];ns=bound['numeric'];packet=bound['packet']
        io.need(packet['schema']==g['feature_schema'] and packet['study']==g['feature_study'],'feature_identity');check()
        def previous(index):
            item=request['previous'][index];io.need(item['stage']==index,'previous_order')
            return j.read(index,'result.json',item['result_pin'])
        admission_raw=previous(0) if i else None
        admission=ns.decode(admission_raw,io.pin(admission_raw)['sha256']) if i else None
        count=dict(initial=0,step=0,forecast=0,audit_records=0,audit_reports=0);terminal=False;began=False
        def emit(kind,raw):
            nonlocal terminal,began
            io.need(type(raw)is bytes and len(raw)<=CODEC_CAP,'callback_cap');value=ns.decode(raw,io.pin(raw)['sha256'])
            failure=kind in ('admission_failure','failure','score_failure')
            if not failure:check();io.need(not terminal,'callback_after_terminal')
            if failure:
                io.need(kind=={'admission':'admission_failure','fit':'failure','score':'score_failure'}.get(s['kind']),'failure_kind');name='failure.json';terminal=True
            elif s['kind']=='admission':
                if kind=='initial':
                    n=count['initial'];io.need(n<2 and (value['seed'],value['arm'])==((20261012,'L'),(20261013,'L'))[n] and value['status']=='initial' and value['update']==0 and value['study']==c.STUDY,'initial_order');name='initial_%02d.json'%n;count['initial']+=1
                else:
                    io.need(kind=='admission' and count['initial']==2 and value['status']=='admitted' and value['study']==c.STUDY,'admission_terminal');name='result.json';terminal=True
            elif s['kind']=='fit':
                io.need(value['study']==c.STUDY and (value['seed'],value['arm'])==(s['seed'],s['arm']),'fit_identity')
                if kind=='begin_fit':
                    io.need(not began and count['step']==0 and value['status']=='initial' and value['update']==0,'begin_once');name='begin_fit.json';began=True
                elif kind=='step':
                    io.need(began and count['step']<300 and value['status']=='partial' and type(value['update'])is int and value['update']==count['step']+1 and len(value['history'])==value['update'],'update_order')
                    io.need([v['update'] for v in value['history']]==list(range(1,value['update']+1)),'history_order');name='latest_update.json';count['step']+=1
                else:
                    io.need(kind=='final' and began and count['step']==300 and value['status']=='final' and value['update']==300 and len(value['history'])==300,'final300');name='result.json';terminal=True
            elif s['kind']=='score':
                io.need((value['seed'],value['arm'])==(s['seed'],s['arm']),'score_identity')
                if kind=='forecast':
                    n=count['forecast'];expected=[(r,h)for r in admission['schema']['dev']for h in(1,3,5)]
                    io.need(n<66 and value['status']=='complete' and (value['ordinal'],value['horizon'])==expected[n],'forecast_order');name='forecast_%02d.json'%n;count['forecast']+=1
                else:
                    io.need(kind=='score_final' and count['forecast']==66 and value['status']=='complete' and value['study']==c.STUDY and value['no_optimizer']is True and len(value['predictions'])==66,'score66');name='result.json';terminal=True
            else:raise ValueError('producer_callback_kind')
            result=j.write(i,name,raw,replace=kind=='step');p=io.pin(raw);io.need(result==dict(status='durable',sha256=p['sha256']),'durable_callback')
            if kind=='step':j.object(i,'update_%03d.json'%count['step'],dict(update=count['step'],checkpoint_pin=p,history_last=value['history'][-1]))
            report['callbacks'].append(dict(kind=kind,name=name,pin=p))
            if not failure:check()
            return result
        def retain(value):
            # Auditor retains a failed/late candidate BEFORE caller deadline interpretation.
            n=count['audit_records'];is_report=value.get('schema') in ('shared-reference-AR-L-independent-audit-v1','shared-reference-AR-L-independent-aggregate-v1')
            if is_report:
                io.need(count['audit_reports']==0,'audit_report_once');name='audit_report.json';count['audit_reports']+=1
            else:
                io.need(n<67,'audit_record_count');name='record_%03d.json'%n;count['audit_records']+=1
            raw=ns.encode(value);io.need(type(raw)is bytes and len(raw)<=16*1024*1024,'audit_member_cap');result=j.write(i,name,raw)
            io.need(result==dict(status='durable',sha256=io.pin(raw)['sha256']),'audit_retention_receipt');report['callbacks'].append(dict(kind='retain',name=name,pin=io.pin(raw)))
        if s['kind']=='admission':
            raw=op.prepare(packet,bound['bindings'],emit,processing_begin=source_begin)
            io.need(terminal and count['initial']==2 and j.read(i,'result.json')==raw,'admission_return')
        elif s['kind']=='fit':
            result=op.fit_one(packet,admission_raw,io.pin(admission_raw)['sha256'],bound['bindings'],emit,seed=s['seed'],arm='L',processing_begin=source_begin)
            raw=result['checkpoint'];io.need(result['status']=='complete' and terminal and count['step']==300 and j.read(i,'result.json')==raw,'fit_return')
        elif s['kind']=='score':
            checkpoint=previous(i-1);result=op.score_final(packet,admission_raw,io.pin(admission_raw)['sha256'],checkpoint,io.pin(checkpoint)['sha256'],bound['bindings'],emit,processing_begin=source_begin)
            raw=result['result'];io.need(result['status']=='complete' and terminal and count['forecast']==66 and j.read(i,'result.json')==raw,'score_return')
        elif s['kind']=='aggregate':
            scores=[ns.decode(previous(n),request['previous'][n]['result_pin']['sha256'])for n in(2,4)]
            result=op.aggregate(packet,admission_raw,io.pin(admission_raw)['sha256'],scores,bound['reused_results'],bound['strong_results'],bound['bindings'],processing_begin=source_begin)
            raw=ns.encode(result);io.need(len(raw)<=CODEC_CAP,'producer_result_cap');j.write(i,'result.json',raw)
            io.need(result['status']=='complete' and type(result['pass_all'])is bool and len(result['original24'])==24 and len(result['additional18'])==18 and result['record_counts']==dict(new_L=132,reused_SPD=396,reused_BFHT=528,total=1056),'aggregate42')
        else:
            pins=[dict(stage=n,result_pin=item['result_pin'])for n,item in enumerate(request['previous'])]
            authority=adapter.audit_authority(request,pins,bound);check()
            auditor=bound['auditor']
            if s['kind']=='audit_fit':
                score_index=2 if i==6 else 4
                score=ns.decode(previous(score_index),request['previous'][score_index]['result_pin']['sha256'])
                checkpoint=ns.decode(previous(score_index-1),request['previous'][score_index-1]['result_pin']['sha256'])
                result=auditor.audit_fit(score,packet,admission,bound['original_admission'],checkpoint,authority,processing_begin=source_begin,retain=retain)
                valid=result.get('schema')=='shared-reference-AR-L-independent-audit-v1' and result.get('status')=='pass' and result.get('checked')==66 and (result.get('seed'),result.get('arm'))==(s['seed'],'L') and len(result.get('records',[]))==66 and count['audit_records']==66 and count['audit_reports']==1
            else:
                fits=[ns.decode(previous(n),request['previous'][n]['result_pin']['sha256'])for n in(6,7)]
                scores=[ns.decode(previous(n),request['previous'][n]['result_pin']['sha256'])for n in(2,4)]
                result=auditor.aggregate(fits,scores,packet,admission,bound['original_admission'],bound['closed_comparator_report'],bound['origins'],authority,processing_begin=source_begin,retain=retain)
                valid=result.get('schema')=='shared-reference-AR-L-independent-aggregate-v1' and result.get('status')=='pass' and result.get('checked')==132 and count['audit_reports']==1 and result.get('record_counts')==dict(new_L=132,reused_SPD=396,reused_BFHT=528,total=1056) and len(result.get('paired',[]))==42 and len(result.get('advance',{}).get('checks',[]))==24 and len(result.get('advance',{}).get('additional',[]))==18 and type(result.get('advance',{}).get('pass_all'))is bool
            raw=ns.encode(result);j.write(i,'result.json',raw) # full returned failure/pass before budget/status checks
            io.need(valid,'independent_audit_incomplete')
        report['result_pin']=io.pin(raw);check();report['status']='complete'
    except Exception as exc:
        report['failure']=dict(type=type(exc).__name__,reason=str(exc)[:512])
        if bound is not None and hasattr(exc,'evidence'):
            try:
                numeric=bound['numeric'];processor=bound['processor']
                value=processor.failure_numeric(exc.evidence) if processor is not None else exc.evidence
                raw=numeric.encode(value);report['exception_evidence_pin']=io.pin(raw);j.write(i,'exception_evidence.json',raw)
            except Exception:report['failure']['exception_evidence_unverified']=True
    now=clock();report['within_source']=c.finite(source_begin) and 0<=source_begin<=now and now-source_begin<=s['source_seconds'];report['within_experiment']=now<=g['whole_begin']+7200
    if not report['within_source'] or not report['within_experiment']:report['status']='incomplete'
    try:
        j.object(i,'child_report.json',report);check()
    except Exception as exc:
        report['status']='incomplete';report['failure']=dict(type=type(exc).__name__,reason=str(exc)[:512])
        try:j.object(i,'child_failure.json',report)
        except Exception:pass
    return report

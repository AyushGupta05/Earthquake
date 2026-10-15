"""Concrete sole-run ROOT parent for frozen nine-stage L execution."""
import os
import time
import traceback
import parent_stop as stop

REQUEST_KEYS={'schema','root_spec','expected_root_pin','bootstrap_spec','entry_source_spec',
              'parent_source_spec','stop_source_spec','stop_request_spec','stop_receipt_spec','parent_store_directory'}


def run(request,held,modules,*,clock=time.monotonic):
    io=modules['secure_io'];c=modules['control'];g=held['execution'];sdmod=modules['systemd_adapter']
    io.need(type(request)is dict and set(request)==REQUEST_KEYS and request['schema']=='ROOT-L-parent-entry-v1','parent_request')
    io.need(request['root_spec']['pin']==request['expected_root_pin'] and io.read_file(request['root_spec'],2*1024*1024)==io.canonical(held),'held_root_raw')
    io.need(request['bootstrap_spec']==held['launch']['bootstrap'],'bootstrap_subject')
    c.config_check(g,clock(),held['execution_pin'])
    stop_request=io.json_read(io.read_file(request['stop_request_spec'],2*1024*1024))
    stop_receipt=io.json_read(io.read_file(request['stop_receipt_spec'],2*1024*1024))
    io.need(stop_request['experiment_id']==g['experiment_id'] and stop_request['whole_begin']==g['whole_begin']
            and stop_request['lease_deadline']==g['lease_deadline'] and stop_request['commands']==held['launch']['commands'],'stop_execution_subject')
    current=io.json_read(io.read_file(held['evidence']['current']))
    io.need(current['timer']==stop_receipt['timer'] and current['boot_id']==stop_request['boot_id'],'held_stop_authority')
    parent_path=request['parent_store_directory'];children=held['launch']['store_directory'];retention=current['retention_directory']
    paths=(parent_path,children,retention,stop_request['stop_store_directory'])
    io.need(len(set(paths))==4 and all(not a.startswith(b+'/') for a in paths for b in paths if a!=b),'separate_custody_directories')
    # Whole clock already exists. These stdlib-only preparations consume it;
    # no clock is captured here to reset or extend scientific work.
    records=stop.new_store(parent_path,io);journal=None;systemd=None;counter=[0]
    report=dict(schema='ROOT-L-nine-stage-orchestrator-return-v1',status='incomplete',
                root_pin=request['expected_root_pin'],execution_pin=held['execution_pin'],whole_begin=g['whole_begin'],
                stages=[],cleanup=None,no_retry=True)
    def record(value):
        name='cleanup_%03d.json'%counter[0];counter[0]+=1
        stop.store_object(records,9,name,value,io)
    try:
        stop.store_object(records,9,'parent_claim.json',dict(root_pin=request['expected_root_pin'],request=request),io)
        stop.inspect_stop(stop_request,stop_receipt,io=io,sd=sdmod,clock=clock,record=lambda v:stop.store_object(records,9,'initial_stop_readback.json',v,io))
        primitive=modules['root_primitives']
        primitives,custody=primitive.make_primitives(held,expected_root_pin=request['expected_root_pin'],
            root_spec=request['root_spec'],modules=modules,source_begin=None,clock=clock)
        io.need(callable(primitives.retain_return),'concrete_return_retainer')
        journal=modules['journal'].Journal(children)
        io.need(journal.inventory()=={},'new_child_journal')
        systemd=sdmod.Systemd(held['launch']['commands'])
        for index in range(9):
            s=c.spec(g,index);systemd.own(s['unit']);systemd.available(s['unit'])
        for index in range(9):
            c.config_check(g,clock(),held['execution_pin'])
            io.need(clock()+c.spec(g,index)['manager_seconds']<=min(g['whole_begin']+7200,g['lease_deadline']),'remaining_science_budget')
            stop.store_object(records,index,'attempt.json',dict(stage=index,root_pin=request['expected_root_pin']),io)
            # Real frozen implementation authorizes source/current/inputs before
            # dispatch and persists actual manager answers via concrete primitives.
            result=modules['root_glue'].run_parent(held,index,expected_pin=request['expected_root_pin'],
                root_spec=request['root_spec'],modules=modules,primitives=primitives,custody=custody,
                journal=journal,systemd=systemd,retain_return=primitives.retain_return,clock=clock)
            result_pin=stop.store_object(records,index,'actual_parent_return.json',result,io)
            report['stages'].append(dict(stage=index,return_pin=result_pin,status=result['status']))
            io.need(result['status']=='complete','terminal_stage_failure')
            io.need(clock()<=min(g['whole_begin']+7400,g['lease_deadline']),'parent_return_expired')
        report['status']='complete'
    except BaseException as exc:
        report['failure']=dict(reason=type(exc).__name__+':'+str(exc),traceback=traceback.format_exc())
    finally:
        try:stop.store_object(records,9,'before_cleanup.json',report,io)
        except BaseException as exc:
            report['status']='incomplete';report['retention_error']=type(exc).__name__+':'+str(exc)
        # Resource closure is independent of numerical outcome, and does not
        # disarm the stop timer unless all9 stage services are positively empty.
        try:
            report['cleanup']=stop.cleanup(stop_request,io=io,sd=sdmod,record=record,clock=clock)
            if report['cleanup']['status']!='complete':report['status']='incomplete'
        except BaseException as exc:
            report['status']='incomplete';report['cleanup_error']=type(exc).__name__+':'+str(exc)
        if journal is not None:
            try:journal.close()
            except BaseException as exc:report['status']='incomplete';report['journal_close_error']=str(exc)
        report['whole_seconds']=clock()-g['whole_begin']
        if clock()>min(g['whole_begin']+7400,g['lease_deadline']):report['status']='incomplete';report['late']=True
        try:
            final_pin=stop.store_object(records,9,'final_report.json',report,io)
            if clock()>min(g['whole_begin']+7400,g['lease_deadline']):
                report['status']='incomplete';stop.store_object(records,9,'late_finalization.json',dict(status='incomplete',final_pin=final_pin),io)
        finally:records.close()
    return dict(status=report['status'],final_report=dict(path=parent_path+'/stage_09/final_report.json',pin=final_pin,mode=0o400),no_retry=True)

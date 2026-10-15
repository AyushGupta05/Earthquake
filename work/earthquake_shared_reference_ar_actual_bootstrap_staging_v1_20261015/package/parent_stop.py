"""Fixed nine-unit stop installation and conservative closure; stdlib only."""
import math
import os
import re
import stat
import time

INSTALL_KEYS = {'schema', 'experiment_id', 'whole_begin', 'lease_deadline',
                'commands', 'bash', 'stop_store_directory', 'boot_id'}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def duration(text):
    """systemctl absolute monotonic times may include weeks and days."""
    need(type(text) is str, 'duration_type')
    parts = re.findall(r'([0-9]+(?:\.[0-9]+)?)(us|ms|min|s|h|d|w)', text)
    need(parts and ''.join(n+u for n,u in parts) == text.replace(' ', ''), 'duration')
    scales = dict(us=1e-6, ms=1e-3, s=1, min=60, h=3600, d=86400, w=604800)
    value = sum(float(n)*scales[u] for n,u in parts)
    need(math.isfinite(value), 'finite_duration')
    return value


def names(ident):
    need(type(ident) is str and re.fullmatch('[a-z0-9-]{1,48}', ident), 'experiment_id')
    return ['eew-marked-'+ident+'-%02d.service'%i for i in range(9)]


def wire(value):
    if isinstance(value, bytes): return {'hex':value.hex()}
    if isinstance(value, dict): return {k:wire(v) for k,v in value.items()}
    if isinstance(value, (tuple,list)): return [wire(v) for v in value]
    return value


def props(answer, *, absence=False):
    need(answer['timeout'] is False and answer['streams_complete'] is True, 'incomplete_systemctl')
    out = {}
    for line in answer['stdout'].decode().splitlines():
        need('=' in line, 'property_line'); key,val = line.split('=',1)
        need(key not in out, 'duplicate_property'); out[key] = val
    missing = (absence and answer['code'] in (1,4) and out in (
        dict(LoadState='not-found',ActiveState='inactive'),
        dict(LoadState='not-found',ActiveState='inactive',ControlGroup='')))
    need(answer['code']==0 or missing, 'systemctl_exit')
    return out


def new_store(path, io):
    """Fresh metadata only, outside child journal and last-return custody."""
    io.parts(path, True); parent, base = os.path.split(path); fd = io.directory(parent)
    try:
        os.mkdir(base,0o700,dir_fd=fd); os.fsync(fd)
    finally: os.close(fd)
    return io.Store(path,8*1024*1024,member_cap=128)


def store_object(store, index, name, value, io):
    raw = io.canonical(wire(value)); store.write('stage_%02d/%s'%(index,name),raw,total_cap=store.total_cap)
    return io.pin(raw)


def command(commands,key,args,*,io,sd,timeout):
    need(timeout>0, 'command_budget'); spec=commands[key]
    io.read_file(spec,16*1024*1024)
    return sd.process([spec['path']]+args,timeout)


def show(commands,unit,fields,*,io,sd,timeout):
    return command(commands,'systemctl',['--user','show',unit,'--property='+','.join(fields)],io=io,sd=sd,timeout=timeout)


def validate_request(request,io,sd,clock):
    need(type(request) is dict and set(request)==INSTALL_KEYS and request['schema']=='ROOT-L-stop-install-v1','install_schema')
    units=names(request['experiment_id'])
    for key in ('whole_begin','lease_deadline'):
        need(type(request[key]) in (int,float) and math.isfinite(request[key]), 'install_clock')
    now=clock(); target=min(request['whole_begin']+7400,request['lease_deadline'])
    need(0<=request['whole_begin']<=now<request['whole_begin']+7200
         and request['whole_begin']<request['lease_deadline']<=request['whole_begin']+7400
         and now+20<target, 'fixed_install_deadline')
    need(set(request['commands'])=={'systemctl','systemd_run'},'commands')
    need(request['commands']['systemctl']['path']=='/usr/bin/systemctl'
         and request['commands']['systemd_run']['path']=='/usr/bin/systemd-run'
         and request['bash']['path']=='/usr/bin/bash','executable_paths')
    for spec in list(request['commands'].values())+[request['bash']]:io.read_file(spec,16*1024*1024)
    need(sd.live_read('/proc/sys/kernel/random/boot_id').decode().strip()==request['boot_id'],'install_boot')
    return units,target


def inspect_stop(request,receipt,*,io,sd,clock=time.monotonic,record=None):
    """Fresh readback; receipt never replaces actual timer/unit observations."""
    units,target=validate_request(request,io,sd,clock)
    need(receipt['schema']=='ROOT-L-installed-stop-v1' and receipt['request_pin']==io.pin(io.canonical(request))
         and receipt['units']==units and receipt['whole_begin']==request['whole_begin'],'stop_receipt_subject')
    stop_spec=receipt['stop_script'];body=io.read_file(stop_spec,65536)
    need(body==stop_body(units),'stop_script_bytes')
    timer='eew-marked-'+request['experiment_id']+'-stop.timer';service=timer[:-6]+'.service'
    need(receipt['timer']['unit']==timer and receipt['timer']['service']==service,'stop_names')
    remaining=min(5,target-clock());need(remaining>0,'stop_readback_budget')
    tr=show(request['commands'],timer,('LoadState','ActiveState','Unit','AccuracyUSec','TimersMonotonic','NextElapseUSecMonotonic'),io=io,sd=sd,timeout=remaining)
    remaining=min(5,target-clock());need(remaining>0,'stop_readback_budget')
    sr=show(request['commands'],service,('LoadState','ActiveState','ExecStart'),io=io,sd=sd,timeout=remaining)
    if record:record(dict(timer=tr,service=sr))
    t,s=props(tr),props(sr);due=duration(t['NextElapseUSecMonotonic'])
    need(t['LoadState']=='loaded' and t['ActiveState']=='active' and t['Unit']==service
         and s['LoadState']=='loaded' and s['ActiveState']=='inactive','installed_stop_state')
    need(duration(t['AccuracyUSec'])<=1 and target-10<=due<=target and clock()<due,'fixed_stop_due')
    interval=re.findall(r'OnActive(?:USec|Sec)=([^;]+)',t['TimersMonotonic'])
    need(len(interval)==1 and 0<duration(interval[0].strip())<=7400,'relative_stop_interval')
    argv=re.findall(r'argv\[\]=([^;]*)(?:;|$)',s['ExecStart'])
    need(len(argv)==1 and argv[0].split()==['/usr/bin/bash',stop_spec['path']],'stop_exec')
    need(receipt['timer']['exec_start'] in ('',s['ExecStart']), 'stop_exec_changed')
    need(receipt['timer']['deadline'] in (None,due), 'stop_due_changed')
    return dict(unit=timer,service=service,exec_start=s['ExecStart'],deadline=due)


def stop_body(units):
    need(len(units)==9 and all(re.fullmatch(r'eew-marked-[a-z0-9-]+-0[0-8]\.service',u)for u in units),'stop_units')
    return ('#!/usr/bin/bash\nstatus=0\n'+''.join(
        '/usr/bin/systemctl --user stop '+u+'\nif [ "$?" -ne 0 ]; then status=1; fi\n'for u in units)+'exit "$status"\n').encode()


def cleanup(request,*,io,sd,record,clock=time.monotonic):
    """Do not disarm an independent stop while any stage remains unverified."""
    units=names(request['experiment_id']);end=min(request['whole_begin']+7400,request['lease_deadline'])
    result=dict(status='incomplete',services=[],errors=[],timer_retained=True)
    def bounded():
        r=min(5,end-clock());need(r>0,'cleanup_expired');return r
    def inspect(unit):
        fields=('LoadState','ActiveState')if unit.endswith('.timer')else('LoadState','ActiveState','ControlGroup')
        a=show(request['commands'],unit,fields,io=io,sd=sd,timeout=bounded());record(dict(kind='show',unit=unit,answer=a));v=props(a,absence=True)
        need(v['ActiveState']=='inactive' and v['LoadState'] in ('loaded','not-found')
             and (unit.endswith('.timer') or v['ControlGroup']==''),'unclosed_unit')
        return v
    for unit in units:
        try:
            a=command(request['commands'],'systemctl',['--user','stop',unit],io=io,sd=sd,timeout=bounded())
            record(dict(kind='stop',unit=unit,answer=a));need(a['streams_complete']and not a['timeout'],'stop_transport')
            # A missing service can yield5; only separate exact readback earns closure.
            v=inspect(unit);need(a['code']==0 or v==dict(LoadState='not-found',ActiveState='inactive',ControlGroup=''),'stop_nonzero_loaded')
            result['services'].append(dict(unit=unit,properties=v))
        except BaseException as exc:result['errors'].append(type(exc).__name__+':'+str(exc))
    if result['errors']:return result
    timer='eew-marked-'+request['experiment_id']+'-stop.timer'
    for unit in (timer,timer[:-6]+'.service'):
        try:
            a=command(request['commands'],'systemctl',['--user','stop',unit],io=io,sd=sd,timeout=bounded())
            record(dict(kind='stop',unit=unit,answer=a));need(a['streams_complete']and not a['timeout'],'stop_transport')
            v=inspect(unit);missing=dict(LoadState='not-found',ActiveState='inactive')
            if unit.endswith('.service'):missing['ControlGroup']=''
            need(a['code']==0 or v==missing,'stop_nonzero_loaded')
            result['services'].append(dict(unit=unit,properties=v))
        except BaseException as exc:result['errors'].append(type(exc).__name__+':'+str(exc));return result
    result.update(status='complete',timer_retained=False);return result


def install_stop(request,*,expected_pin,io,sd,clock=time.monotonic):
    need(io.pin(io.canonical(request))==expected_pin,'held_install_request')
    units,target=validate_request(request,io,sd,clock)
    store=new_store(request['stop_store_directory'],io);armed=False;receipt=None;counter=[0]
    def record(value):
        name='evidence_%03d.json'%counter[0];counter[0]+=1
        store_object(store,0,name,value,io)
    try:
        store_object(store,0,'request.json',request,io)
        timer='eew-marked-'+request['experiment_id']+'-stop.timer';service=timer[:-6]+'.service'
        for unit in units+[service,timer]:
            fields=('LoadState','ActiveState')if unit.endswith('.timer')else('LoadState','ActiveState','ControlGroup')
            a=show(request['commands'],unit,fields,io=io,sd=sd,timeout=min(5,target-clock()));record(dict(kind='absence',unit=unit,answer=a));v=props(a,absence=True)
            expected=dict(LoadState='not-found',ActiveState='inactive')
            if unit.endswith('.service'):expected['ControlGroup']=''
            need(v==expected,'existing_stop_namespace')
        body=stop_body(units);store.write('stage_00/stop_script.json',body,total_cap=store.total_cap)
        stop_spec=dict(path=request['stop_store_directory']+'/stage_00/stop_script.json',pin=io.pin(body),mode=0o400)
        interval=math.floor((target-clock()-5)*1e6)/1e6;need(interval>10,'install_margin')
        armed=True;a=command(request['commands'],'systemd_run',['--user','--unit='+service[:-8],
            '--on-active=%.6fs'%interval,'--timer-property=AccuracySec=1s','--property=Type=oneshot',
            '--property=TimeoutStartSec=60','/usr/bin/bash',stop_spec['path']],io=io,sd=sd,timeout=min(10,target-clock()))
        record(dict(kind='install',answer=a));need(a['code']==0 and a['streams_complete']and not a['timeout'],'install_return')
        receipt=dict(schema='ROOT-L-installed-stop-v1',request_pin=expected_pin,units=units,whole_begin=request['whole_begin'],
                     stop_script=stop_spec,timer=dict(unit=timer,service=service,exec_start='',deadline=None))
        receipt['timer']=inspect_stop(request,receipt,io=io,sd=sd,clock=clock,record=record)
        raw=io.canonical(receipt);store.write('stage_00/installed_stop.json',raw,total_cap=store.total_cap)
        need(clock()<receipt['timer']['deadline'],'install_finalization')
        return dict(path=request['stop_store_directory']+'/stage_00/installed_stop.json',pin=io.pin(raw),mode=0o400)
    except BaseException as exc:
        try:store_object(store,0,'failure.json',dict(status='incomplete',reason=type(exc).__name__+':'+str(exc),armed=armed,partial=receipt),io)
        finally:
            if armed:
                result=cleanup(request,io=io,sd=sd,record=record,clock=clock)
                store_object(store,0,'cleanup.json',result,io)
        raise
    finally:store.close()

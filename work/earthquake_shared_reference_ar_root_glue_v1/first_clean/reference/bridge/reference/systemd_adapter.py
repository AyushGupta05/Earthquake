"""Owned unit control and bounded transport. No invocation on import."""
import hashlib
import os
import re
import selectors
import subprocess
import sys
import time
import secure_io as io

THREAD_KEYS=('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')


def process(args,timeout,*,popen=subprocess.Popen,clock=time.monotonic):
    io.need(type(args) is list and args and all(type(x) is str for x in args) and type(timeout) in (int,float) and timeout>0,'transport_args')
    start=clock();end=start+timeout;buffers={k:bytearray() for k in ('stdout','stderr')};sizes={k:0 for k in buffers};hashes={k:hashlib.sha256() for k in buffers}
    caps=dict(stdout=65536,stderr=131072);proc=None;select=None;expired=False;failure=None;code=None
    try:
        proc=popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True);select=selectors.DefaultSelector()
        for key,pipe in (('stdout',proc.stdout),('stderr',proc.stderr)):
            os.set_blocking(pipe.fileno(),False);select.register(pipe,selectors.EVENT_READ,key)
        while select.get_map():
            remaining=end-clock()
            if remaining<=min(2,timeout/4):expired=True;break
            for key,_ in select.select(min(.05,max(0,remaining-min(2,timeout/4)))):
                b=os.read(key.fileobj.fileno(),65536)
                if not b:select.unregister(key.fileobj);continue
                name=key.data;hashes[name].update(b);sizes[name]+=len(b);buffers[name].extend(b[:max(0,caps[name]-len(buffers[name]))])
                if sum(sizes.values())>32*1024*1024:raise ValueError('transport_observed_cap')
        code=proc.poll()
        if code is None and not expired:
            remaining=end-clock()
            if remaining>0:
                try:code=proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:expired=True
            else:expired=True
    except Exception as exc:failure=type(exc).__name__;expired=True
    finally:
        if proc is not None and proc.poll() is None:
            try:proc.terminate()
            except Exception:pass
            remaining=max(0,end-clock())
            if remaining:
                try:code=proc.wait(timeout=remaining)
                except Exception:pass
            if proc.poll() is None:
                try:proc.kill()
                except Exception:pass
            code=proc.poll()
        if select is not None:select.close()
        if proc is not None:
            for pipe in (proc.stdout,proc.stderr):
                try:pipe.close()
                except Exception:expired=True
    observed=not expired and failure is None and code is not None and clock()<=end
    streams={k:dict(original_bytes=sizes[k],original_sha256=hashes[k].hexdigest(),retained_bytes=len(buffers[k]),truncated=sizes[k]>caps[k],complete_observation=observed) for k in buffers}
    return dict(code=code,timeout=expired or clock()>end,stdout=bytes(buffers['stdout']),stderr=bytes(buffers['stderr']),
                streams_complete=observed and all(not x['truncated'] for x in streams.values()),stream_custody=streams,exception=failure)


def properties(raw,expected):
    io.need(type(raw) is bytes and len(raw)<=16384,'properties_cap');out={}
    for line in raw.decode('utf8').splitlines():
        io.need('=' in line,'property_line');key,value=line.split('=',1);io.need(key not in out,'property_duplicate');out[key]=value
    io.need(set(out)==set(expected),'property_fields');return out


def seconds(value):
    io.need(type(value) is str and re.fullmatch(r'(?:[0-9]+(?:\.[0-9]+)?(?:us|ms|s|min|h)(?: |$))+',value),'duration')
    factors={'us':1e-6,'ms':1e-3,'s':1,'min':60,'h':3600}
    return sum(float(n)*factors[u] for n,u in re.findall(r'([0-9]+(?:\.[0-9]+)?)(us|ms|s|min|h)',value))


def live_read(path,cap=16384):
    names=io.parts(path,True);d=io.directory('/'+'/'.join(names[:-1]))
    try:return io.read_at(d,names[-1],cap)
    finally:os.close(d)


class Systemd:
    def __init__(self,commands,*,runner=process,popen=subprocess.Popen,clock=time.monotonic,read_live=live_read,environ=None,pid=None,bytecode=None):
        io.need(type(commands) is dict and set(commands)=={'systemctl','systemd_run'},'commands')
        for spec in commands.values():io.read_file(spec,16*1024*1024)
        self.commands=commands;self.runner=runner;self.popen=popen;self.clock=clock;self.read_live=read_live
        self.environ=os.environ if environ is None else environ;self.pid=os.getpid() if pid is None else pid;self.bytecode=sys.dont_write_bytecode if bytecode is None else bytecode;self.owned=set()
    def own(self,unit):
        io.need(type(unit) is str and re.fullmatch('eew-marked-[a-z0-9-]{1,48}-[0-9]{2}\\.service',unit),'owned_unit');self.owned.add(unit)
    def _owned(self,unit):io.need(unit in self.owned,'foreign_unit')
    def _command(self,key):
        spec=self.commands[key];io.read_file(spec,16*1024*1024);return spec['path']
    def show(self,unit,names,timeout,*,allow_not_found=False):
        self._owned(unit);io.need(timeout>0,'no_inspection_budget')
        end=self.clock()+timeout
        args=[self._command('systemctl'),'--user','show',unit]
        for n in names:args+=['-p',n]
        remaining=end-self.clock();io.need(remaining>0,'inspection_preparation_expired')
        answer=self.runner(args,remaining)
        io.need(answer['timeout'] is False and answer['streams_complete'] is True,'systemctl_failed')
        values=properties(answer['stdout'],names)
        missing=(allow_not_found and type(answer['code']) is int and answer['code'] in (1,4)
                 and values==dict(LoadState='not-found',ActiveState='inactive',ControlGroup=''))
        io.need(answer['code']==0 or missing,'systemctl_failed')
        return values
    def available(self,unit,timeout=5):
        v=self.show(unit,('LoadState','ActiveState','ControlGroup'),timeout,allow_not_found=True)
        io.need(v['LoadState']=='not-found' and v['ActiveState']=='inactive' and v['ControlGroup']=='','unit_already_exists')
    def inspect(self,unit,timeout):
        v=self.show(unit,('Result','ActiveState','ControlGroup'),timeout)
        return dict(unit=unit,result=v['Result'],active_state=v['ActiveState'],control_group=v['ControlGroup'])
    def stop(self,unit,timeout):
        self._owned(unit);io.need(type(timeout) in (int,float) and timeout>=0,'stop_timeout')
        end=self.clock()+timeout
        command=self.commands['systemctl']['path'] if timeout==0 else self._command('systemctl')
        args=[command,'--user','--no-block','stop',unit]
        if timeout==0:
            # Request without waiting after expiry. It is deliberately NOT proof
            # that systemd received/completed the stop; ROOT must reconcile.
            p=self.popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)
            return dict(unit=unit,requested=True,nonblocking=True,helper_pid=p.pid,cleanup_verified=False)
        remaining=end-self.clock();io.need(remaining>0,'stop_preparation_expired')
        answer=self.runner(args,remaining)
        return dict(unit=unit,requested=True,nonblocking=False,code=answer['code'],transport_complete=answer['streams_complete'],cleanup_verified=False)
    def run(self,argv,timeout,unit):
        self._owned(unit);io.need(argv[0]=='systemd-run' and '--unit='+unit[:-8] in argv,'launch_unit')
        end=self.clock()+timeout
        argv=[self._command('systemd_run')]+argv[1:];remaining=end-self.clock();io.need(remaining>0,'launch_preparation_expired')
        return self.runner(argv,remaining)
    def live(self,spec):
        unit=spec['unit'];self._owned(unit);paths=[s[3:] for s in self.read_live('/proc/'+str(self.pid)+'/cgroup').decode().splitlines() if s.startswith('0::')]
        io.need(len(paths)==1 and paths[0].startswith('/') and paths[0].split('/')[-1]==unit,'live_cgroup')
        group='/sys/fs/cgroup'+paths[0]
        caps={n:self.read_live(group+'/'+n,128).decode().strip() for n in ('memory.max','memory.swap.max','pids.max','cpu.weight')}
        io.need(caps=={'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64','cpu.weight':'10'} and str(self.pid) in self.read_live(group+'/cgroup.procs').decode().split(),'live_caps')
        names=('RuntimeMaxUSec','TimeoutStopUSec','KillMode','ActiveState','CPUWeight','MainPID','ControlGroup')
        props=self.show(unit,names,5)
        io.need(seconds(props['RuntimeMaxUSec'])==spec['manager_seconds'] and seconds(props['TimeoutStopUSec'])==5 and props['KillMode']=='control-group'
                and props['ActiveState']=='active' and props['CPUWeight']=='10' and props['MainPID']==str(self.pid) and props['ControlGroup']==paths[0],'live_systemd')
        io.need(self.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(self.environ.get(k)=='1' for k in THREAD_KEYS) and self.bytecode is True,'live_environment')
        return dict(unit=unit,active=True,limits=spec['limits'],runtime_max_seconds=spec['manager_seconds'])

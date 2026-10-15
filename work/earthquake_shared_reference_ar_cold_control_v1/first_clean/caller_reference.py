"""ROOT one-shot assembly of frozen source APIs; only synthetic cold readiness."""
import time
BEGIN=time.monotonic()
import hashlib,importlib.util,io as stdio,json,os,stat,sys,traceback,types,unittest
from pathlib import Path

def pin(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def read(path,p):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  st=os.fstat(fd);assert stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode)==0o400 and st.st_size==p['bytes']
  with os.fdopen(fd,'rb',closefd=False)as f:raw=f.read(p['bytes']+1)
  assert pin(raw)==p;return raw
 finally:os.close(fd)
def direct(path,p,name):
 raw=read(path,p);module=types.ModuleType(name);module.__file__=path;module.__spec__=importlib.util.spec_from_file_location(name,path);sys.modules[name]=module;exec(compile(raw,path,'exec'),module.__dict__);return module

config_path,config_sha,config_size,control_path,control_sha,control_size,mode=sys.argv[1:]
report={'schema':'L-cold-source-readiness-v1','mode':mode,'scienceactual':0,'status':'incomplete'}
try:
 config_raw=read(config_path,dict(bytes=int(config_size),sha256=config_sha));config=json.loads(config_raw)
 control_raw=read(control_path,dict(bytes=int(control_size),sha256=control_sha));control=json.loads(control_raw)
 assert mode in ('fixtures','independent','producer') and mode in control['units']
 source=config['sources']['v6'];root=source['directory']
 first=direct(root+'/secure_io.py',source['files']['secure_io.py'],'eew_l_seed_io')
 previous={};loaded={}
 try:
  for name in ('secure_io','vendor_inventory','generated_source','metadata_finder','source_binding','systemd_adapter'):
   previous[name]=sys.modules.get(name);module=direct(root+'/'+name+'.py',source['files'][name+'.py'],'eew_l_helpers_'+name);loaded[name]=module;sys.modules[name]=module
 finally:
  for name,old in previous.items():
   if old is None:sys.modules.pop(name,None)
   else:sys.modules[name]=old
 io=loaded['secure_io'];sb=loaded['source_binding'];sd=loaded['systemd_adapter'].Systemd(control['commands'])
 unit=control['units'][mode];sd.own(unit);last=[-1e9]
 def check():
  now=time.monotonic();assert 0<=now-BEGIN<=(120 if mode=='fixtures' else 300) and now<=control['whole_begin']+1000,'source_or_whole_deadline'
  assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'))
  if now-last[0]>=5:
   report['live']=sd.live(dict(unit=unit,manager_seconds=(180 if mode=='fixtures' else 360),limits=control['limits']));last[0]=now
 check();bootstrap=config['sources']['bootstrap'];raw={n:io.read_file(dict(path=bootstrap['directory']+'/'+n,pin=p,mode=0o400))for n,p in bootstrap['files'].items()if n in ('smoke.py','test_smoke.py')}
 if mode=='fixtures':
  sb.runtime(config['runtime'],check);check()
  mods=sb.load_group(bootstrap,raw,('smoke','test_smoke'),'eew_l_fixture')
  assert not {'numpy','scipy','torch'}&set(sys.modules)
  output=stdio.StringIO();result=unittest.TextTestRunner(stream=output,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(mods['test_smoke']))
  report['test_log']=output.getvalue();report['tests']=dict(run=result.testsRun,errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped));assert result.testsRun==19 and result.wasSuccessful()and not result.skipped
 else:
  a=config['sources']['adapter'];araw={'runtime_adapter.py':io.read_file(dict(path=a['directory']+'/runtime_adapter.py',pin=a['files']['runtime_adapter.py'],mode=0o400))}
  adapter=sb.load_group(a,araw,('runtime_adapter',),'eew_l_bound')['runtime_adapter'];smoke=sb.load_group(bootstrap,raw,('smoke',),'eew_l_smoke')['smoke']
  report['synthetic']=smoke.run(mode,config_raw,raw_pin=pin(config_raw),expected_config_pin=pin(canonical(config)),io=io,sb=sb,adapter=adapter,processing_begin=BEGIN,check=check,prefix='eew_l_cold_'+mode)
 check();report['seconds']=time.monotonic()-BEGIN;report['status']='complete'
except BaseException as exc:
 report['reason']=type(exc).__name__+':'+str(exc)[:512];report['traceback']=traceback.format_exc();report['partial']=getattr(exc,'evidence',None);report['seconds']=time.monotonic()-BEGIN
raw=(json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();assert len(raw)<=1024*1024
out=Path(control_path).parent/(mode+'_report.private.json');fd=os.open(str(out),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
with os.fdopen(fd,'wb')as f:f.write(raw);f.flush();os.fsync(f.fileno())
print(json.dumps(dict(status=report['status'],mode=mode,report_path=str(out),report_pin=pin(raw),seconds=report['seconds']),sort_keys=True),flush=True)
sys.exit(0 if report['status']=='complete' else 2)

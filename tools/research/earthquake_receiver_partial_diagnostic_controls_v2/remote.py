from pathlib import Path
import json,subprocess,sys,os,hashlib
def make_output_directory(out):
 out.mkdir(mode=0o700)
 directory_fd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:os.fsync(directory_fd)
 finally:os.close(directory_fd)
p=json.loads(sys.stdin.buffer.read(262144));out=Path('/home/ec2-user/eew-renewal115-partial-replay-output-v1');assert not out.exists();assert subprocess.check_output(['git','-C','/home/ec2-user/Earthquake','rev-parse','HEAD'],text=True,timeout=5).strip()==p['gate']['source_commit'];make_output_directory(out)
def put(name,value,cap=16777216):
 if type(cap) is not int or not 0<cap<=16777216:raise ValueError('private_payload_cap')
 if type(name) is not str or not name or name in ('.','..') or '/' in name or '\\' in name:raise ValueError('private_name')
 b=(json.dumps(value,sort_keys=True,allow_nan=False)+'\n').encode('utf8')
 if len(b)>cap:raise ValueError('private_payload_cap')
 directory_fd=os.open(out,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:
  fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=directory_fd)
  with os.fdopen(fd,'wb')as f:os.fchmod(f.fileno(),0o400);f.write(b);f.flush();os.fsync(f.fileno())
  os.fsync(directory_fd)
 finally:os.close(directory_fd)
put('parent_gate.private.json',p['gate']);unit=p['gate']['unit'];args=['systemd-run','--user','--unit='+unit[:-8],'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=']+['--setenv='+k+'=1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')]+['-p','MemoryMax=2147483648','-p','MemorySwapMax=0','-p','TasksMax=64','-p','CPUWeight=10','-p','RuntimeMaxSec=960','-p','TimeoutStopSec=5','-p','KillMode=control-group','/home/ec2-user/eew-prefix-runtime-v2/venv/bin/python','-I','-B','-c',p['child']]
try:r=subprocess.run(args,capture_output=True,timeout=980);x={'unit_exit':r.returncode,'stdout':r.stdout[:65536].decode('utf8','replace'),'stderr':r.stderr[:65536].decode('utf8','replace')}
except subprocess.TimeoutExpired as exc:
 put('manager_timeout.private.json',{'no_retry':True,'reason':'manager_timeout'});x={'unit_exit':None,'stdout':(exc.stdout or b'')[:65536].decode('utf8','replace'),'stderr':(exc.stderr or b'')[:65536].decode('utf8','replace')}
 try:
  stopped=subprocess.run(['systemctl','--user','stop',unit],capture_output=True,timeout=15);x['stop_exit']=stopped.returncode
 except (subprocess.TimeoutExpired,OSError)as stop_error:
  x['stop_error_type']=type(stop_error).__name__
  x['stop_timeout']=isinstance(stop_error,subprocess.TimeoutExpired)
put('manager_return.private.json',x);st=subprocess.check_output(['systemctl','--user','show',unit,'-p','Result','-p','ControlGroup','-p','ActiveState'],text=True,timeout=5);x['post_properties']=st;assert ('ActiveState=inactive'in st or'ActiveState=failed'in st)and'ControlGroup=\n'in st;x['files']={}
for q in out.iterdir():
 assert q.is_file()and not q.is_symlink()and q.stat().st_size<=16777216 and q.stat().st_mode&0o777==0o400;b=q.read_bytes();x['files'][q.name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'mode':'0o400'}
assert len(x['files'])<=220;put('parent_return.private.json',x);print(json.dumps(x,sort_keys=True))

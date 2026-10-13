from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess,shlex,os

def persist(path,value):
 payload=(json.dumps(value,sort_keys=True,allow_nan=False)+chr(10)).encode();assert len(payload)<=262144
 with path.open('xb')as stream:stream.write(payload);stream.flush();os.fchmod(stream.fileno(),0o400);os.fsync(stream.fileno())
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def bounded_stream(value):
 if value is None:value=b''
 if isinstance(value,str):value=value.encode('utf8',errors='replace')
 assert isinstance(value,bytes);original_bytes=len(value);digest=hashlib.sha256(value).hexdigest();text=value.decode('utf8',errors='replace');lo=0;hi=len(text)
 while lo<hi:
  middle=(lo+hi+1)//2
  if len(json.dumps(text[:middle],ensure_ascii=True).encode())<=61440:lo=middle
  else:hi=middle-1
 retained=text[:lo];return retained,{'original_bytes':original_bytes,'original_sha256':digest,'retained_serialized_bytes':len(json.dumps(retained,ensure_ascii=True).encode()),'truncated':lo<len(text),'decoding':'UTF8 replacement'}
def transport(args,payload,timeout):
 try:
  answer=subprocess.run(args,input=payload,capture_output=True,timeout=timeout);stdout,sm=bounded_stream(answer.stdout);stderr,em=bounded_stream(answer.stderr)
  return {'ssh_exit':answer.returncode,'status':'incomplete'if sm['truncated']or em['truncated']else'transport_returned','reason':'transport_output_truncated'if sm['truncated']or em['truncated']else None,'stdout':stdout,'stderr':stderr,'stream_custody':{'stdout':sm,'stderr':em},'no_retry':True}
 except subprocess.TimeoutExpired as error:
  stdout,sm=bounded_stream(error.stdout);stderr,em=bounded_stream(error.stderr)
  return {'ssh_exit':None,'status':'incomplete','reason':'ssh_outer_timeout','stdout':stdout,'stderr':stderr,'stream_custody':{'stdout':sm,'stderr':em},'no_retry':True,'uncertain_invocation_requires_reconciliation':True,'owned_unit':'eew-train115-receiver-renewal-fits-v2-20261013.service'}

R=Path('/Users/ayush/Documents/Codex/2026-10-09/ok-x20');W=R/'work';D=W/'earthquake_train115_receiver_renewal_v2';pub=json.loads((W/'earthquake_train115_receiver_parent_source_push_v1_20261013.json').read_bytes());assert pub['all_members_git_and_working_byte_verified']
parent_agreement=json.loads((W/'earthquake_train115_receiver_observation_parent_agreement_v1_20261013.private.json').read_bytes());assert parent_agreement['independent_all_observation_bytes_agree']and parent_agreement['events']==115 and parent_agreement['common']=={'TRAIN':65,'DEV':22}
roundtrip=json.loads((W/'earthquake_train115_receiver_observations_actual_v2/numeric_roundtrip.private.json').read_bytes());assert roundtrip['all_exact']and roundtrip['numeric_arrays']==1044
runtime=json.loads(json.loads((W/'earthquake_cpu_pilot_runtime_pin_v1_20261012.private.json').read_bytes())['stdout']);assert runtime['CUDA_hidden_and_uninitialized']and not runtime['existing_runtime_modified']
def pin(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
sourcepins={n:pin((D/n).read_bytes())for n in(D/'ALLOWED_PUBLIC_FILES.txt').read_text().splitlines()};assert len(sourcepins)==69
rt=json.loads((W/'geonet_POST_linux_runtime_manifest_20261012.private.json').read_bytes());rtcanon=hashlib.sha256(json.dumps(rt,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode()).hexdigest()
gate={'schema':'sole115-receiver-renewal-tenfits-v2','checked_utc':datetime.now(timezone.utc).isoformat(),'source_commit':pub['pushed_commit'],'source_pins':sourcepins,'packet_pins':roundtrip['output_pins'],'native_audit_pin':parent_agreement['audit_result_pin'],'prefix_runtime_canonical_sha256':rtcanon,'actual_invocations':1,'arms':['B','F','H','T','C'],'seeds':[20261012,20261013],'maximum_fits':10,'updates':300,'per_fit_seconds':300,'source_seconds':3300,'manager_seconds':3500,'stop_reserve_seconds':5,'CPUWeight':10,'memory':2147483648,'swap':0,'tasks':64,'CUDA_hidden':True,'common':{'TRAIN':65,'DEV':22},'research_ceiling':2000,'conservative_resource_envelope':335,'eligible_credits_verified':True,'private_task_output_total_bytes':268435456,'private_task_members_maximum':64,'diagnostic_failure_export_not_normal_scientific_result':True,'no_fit_replacement':True,'new_resources':0,'source_before_actual_features_published_commit':'442e83620805eee2f8e20bbcad514cf78263afce'}
childpath=Path(__file__).resolve().parent/'fit_child.py';childraw=childpath.read_bytes();expected_child_pin={'bytes': 8459, 'sha256': 'a3481a54f738062b43c7bb16a8fd0a089302c452d2e82c0d70fe4598811042b7'};assert childpath.is_file()and not childpath.is_symlink()and childpath.stat().st_mode&0o777==0o400 and pin(childraw)==expected_child_pin;child=childraw.decode('utf8');gate['reviewed_child_pin']=expected_child_pin;compile(child,'rootcontrolledtenfit','exec');p=W/'earthquake_train115_receiver_tenfit_gate_v2_20261013.private.json';assert not p.exists()
persist(p,gate)
remote=r'''from pathlib import Path
import json,sys,subprocess,hashlib,os
def bounded_stream(value):
 if value is None:value=b''
 if isinstance(value,str):value=value.encode('utf8',errors='replace')
 assert isinstance(value,bytes);original_bytes=len(value);digest=hashlib.sha256(value).hexdigest();text=value.decode('utf8',errors='replace');lo=0;hi=len(text)
 while lo<hi:
  middle=(lo+hi+1)//2
  if len(json.dumps(text[:middle],ensure_ascii=True).encode())<=61440:lo=middle
  else:hi=middle-1
 retained=text[:lo];return retained,{'original_bytes':original_bytes,'original_sha256':digest,'retained_serialized_bytes':len(json.dumps(retained,ensure_ascii=True).encode()),'truncated':lo<len(text),'decoding':'UTF8 replacement'}

p=json.loads(sys.stdin.buffer.read(262144));child_bytes=p['child'].encode('utf8');assert {'bytes':len(child_bytes),'sha256':hashlib.sha256(child_bytes).hexdigest()}==p['gate']['reviewed_child_pin'];out=Path('/home/ec2-user/eew-train115-receiver-renewal-fits-v2');assert not out.exists();assert subprocess.check_output(['git','-C','/home/ec2-user/Earthquake','rev-parse','HEAD']).decode().strip()==p['gate']['source_commit'];out.mkdir(mode=0o700);dfd=os.open(out.parent,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(dfd)
finally:os.close(dfd)
for n,x in(('parent_gate.private.json',p['gate']),('runtime_pins.private.json',p['runtime'])):
 q=out/n
 with q.open('xb')as f:f.write((json.dumps(x,sort_keys=True,allow_nan=False)+chr(10)).encode());f.flush();os.fchmod(f.fileno(),0o400);os.fsync(f.fileno())
 dfd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(dfd)
 finally:os.close(dfd)
unit='eew-train115-receiver-renewal-fits-v2-20261013'
args=['systemd-run','--user','--unit='+unit,'--pipe','--wait','--setenv=CUDA_VISIBLE_DEVICES=','--setenv=OPENBLAS_NUM_THREADS=1','--setenv=OMP_NUM_THREADS=1','--setenv=MKL_NUM_THREADS=1','--setenv=NUMEXPR_NUM_THREADS=1','-p','MemoryMax=2147483648','-p','MemorySwapMax=0','-p','TasksMax=64','-p','CPUWeight=10','-p','RuntimeMaxSec=3500','-p','TimeoutStopSec=5','-p','KillMode=control-group','/home/ec2-user/eew-prefix-runtime-v2/venv/bin/python','-I','-B','-c',p['child']]
manager_timeout=False;stop_evidence=None
try:r=subprocess.run(args,capture_output=True,timeout=3520);code=r.returncode;stdout=r.stdout;stderr=r.stderr
except subprocess.TimeoutExpired as expiry:
 manager_timeout=True;code=124;stdout,sm=bounded_stream(expiry.stdout);stderr,em=bounded_stream(expiry.stderr)
 marker={'reason':'own_unit_outer_timeout','stdout':stdout,'stderr':stderr,'stream_custody':{'stdout':sm,'stderr':em},'no_retry':True}
 q=out/'manager_timeout.private.json'
 with q.open('xb')as f:f.write((json.dumps(marker,sort_keys=True)+chr(10)).encode());f.flush();os.fchmod(f.fileno(),0o400);os.fsync(f.fileno())
 dfd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(dfd)
 finally:os.close(dfd)
 try:
  stopped=subprocess.run(['systemctl','--user','stop',unit+'.service'],capture_output=True,text=True,timeout=10);stop_evidence={'returncode':stopped.returncode}
 except Exception as stop_failure:stop_evidence={'exception_type':type(stop_failure).__name__,'no_retry':True}
if manager_timeout:stdout_custody=sm;stderr_custody=em
else:stdout,stdout_custody=bounded_stream(stdout);stderr,stderr_custody=bounded_stream(stderr)
raw_output_oversized=stdout_custody['original_bytes']>65536 or stderr_custody['original_bytes']>131072;manager_output_limited=raw_output_oversized or stdout_custody['truncated']or stderr_custody['truncated'];manager_status='incomplete'if manager_timeout or manager_output_limited else'returned'
journal={'status':'incomplete_pending_control_group_verification','unit_exit':code,'stdout':stdout,'stderr':stderr,'manager_timeout':manager_timeout,'manager_output_limited':manager_output_limited,'manager_stream_custody':{'stdout':stdout_custody,'stderr':stderr_custody},'stop_evidence':stop_evidence,'no_retry':True};q=out/'manager_return.private.json'
with q.open('xb')as f:f.write((json.dumps(journal,sort_keys=True,allow_nan=False)+chr(10)).encode());f.flush();os.fchmod(f.fileno(),0o400);os.fsync(f.fileno())
dfd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(dfd)
finally:os.close(dfd)
st=subprocess.check_output(['systemctl','--user','show',unit+'.service','-p','Result','-p','ActiveState','-p','ControlGroup'],text=True,timeout=5);assert('ActiveState=inactive'in st or 'ActiveState=failed'in st)and 'ControlGroup=\n'in st;files={};total=0
for q in out.iterdir():
 assert q.is_file()and not q.is_symlink()and q.stat().st_size<=16777216;q.chmod(0o400);b=q.read_bytes();total+=len(b);files[q.name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'mode':'0o400'}
assert total<=268435456 and len(files)<=64
result={'unit_exit':code,'stdout':stdout,'stderr':stderr,'post_properties':st,'files':files,'actual_invocations':1,'no_retries':True,'source_commit':p['gate']['source_commit'],'manager_timeout':manager_timeout,'stop_evidence':stop_evidence,'manager_status':manager_status,'manager_output_limited':manager_output_limited,'manager_stream_custody':{'stdout':stdout_custody,'stderr':stderr_custody}};q=out/'parent_return.private.json';
with q.open('xb')as f:f.write((json.dumps(result,sort_keys=True,allow_nan=False)+chr(10)).encode());f.flush();os.fchmod(f.fileno(),0o400);os.fsync(f.fileno())
dfd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(dfd)
finally:os.close(dfd)
print(json.dumps(result,sort_keys=True))
'''
answer=transport(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','instancebaseline','/usr/bin/python3 -I -B -c '+shlex.quote(remote)],json.dumps({'gate':gate,'runtime':runtime,'child':child}).encode(),3540)
p=W/'earthquake_train115_receiver_tenfit_return_v2_20261013.private.json';assert not p.exists();persist(p,answer)
if answer['ssh_exit']!=0 or answer['status']=='incomplete':print('Incomplete SSH invocation retained; reconcile owned unit and preserve artifacts before any next action');raise SystemExit(1)
x=json.loads(answer['stdout']);
if x['manager_status']!='returned':print('Incomplete remote manager receipt retained; reconcile artifacts without repeating fits');raise SystemExit(1)
print('Sole tenfit comparison unit_exit',x['unit_exit'],'private checkpoints/history/predictions retained; independently replay beforeclaims')

from pathlib import Path
import os,sys,json,hashlib,subprocess,time
begin=time.monotonic();root=Path('/home/ec2-user');source=root/'eew-train115-receiver-renewal-source-v2-frozen';artifactdir=root/'eew-train115-receiver-observations-output-v2';out=root/'eew-train115-receiver-renewal-fits-v2';unit='eew-train115-receiver-renewal-fits-v2-20261013.service'
def raw(p,cap):
 assert p.is_file()and not p.is_symlink()and p.stat().st_size<=cap
 with p.open('rb')as f:b=f.read(cap+1)
 assert len(b)<=cap;return b
output_bytes=0;output_members=0
def put(name,value,cap):
 global output_bytes,output_members
 b=value if isinstance(value,bytes)else(json.dumps(value,sort_keys=True,allow_nan=False)+chr(10)).encode();assert len(b)<=cap and output_bytes+len(b)<=268435456 and output_members<64;output_bytes+=len(b);output_members+=1
 with(out/name).open('xb')as f:f.write(b);f.flush();os.fchmod(f.fileno(),0o400);os.fsync(f.fileno())
 fd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
c=Path('/proc/self/cgroup').read_text().strip().split('::',1)[1];assert c.endswith('/'+unit);g=Path('/sys/fs/cgroup')/c.lstrip('/');limits={n:raw(g/n,128).decode().strip()for n in('memory.max','memory.swap.max','pids.max')};assert limits=={'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64'}
manager=subprocess.check_output(['systemctl','--user','show',unit,'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode','-p','ActiveState','-p','CPUWeight'],text=True,timeout=5);assert 'RuntimeMaxUSec=58min 20s'in manager and 'TimeoutStopUSec=5s'in manager and 'KillMode=control-group'in manager and'ActiveState=active'in manager and'CPUWeight=10'in manager;assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
pins=json.loads(raw(source/'parent_upload_manifest.private.json',1048576))
for n,pin in pins.items():b=raw(source/n,1048576);assert len(b)==pin['bytes']and hashlib.sha256(b).hexdigest()==pin['sha256']and(source/n).stat().st_mode&0o777==0o400
runtime=json.loads(raw(out/'runtime_pins.private.json',1048576));assert runtime['CUDA_hidden_and_uninitialized']and not runtime['existing_runtime_modified']
for n,pin in runtime['critical_runtime_files'].items():
 p=Path(n);assert p.is_file()and not p.is_symlink()and p.stat().st_size==pin['bytes']and oct(p.stat().st_mode&0o777)==pin['mode'];sha=hashlib.sha256()
 with p.open('rb')as f:
  while True:
   b=f.read(1048576)
   if not b:break
   sha.update(b)
 assert sha.hexdigest()==pin['sha256']
# All positive gates are parent-frozen before any import/load/model/probe.
proof=json.loads(raw(out/'parent_gate.private.json',131072));assert subprocess.check_output(['git','-C',str(root/'Earthquake'),'rev-parse','HEAD'],text=True,timeout=5).strip()==proof['source_commit'];assert pins==proof['source_pins']
v=root/'eew-prefix-runtime-v2';manifest=json.loads(raw(v/'runtime_manifest.private.json',4194304));assert hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode()).hexdigest()==proof['prefix_runtime_canonical_sha256'];actual={str(p.relative_to(v))for p in(v/'venv').rglob('*')if p.is_file()and not p.is_symlink()};assert actual==set(manifest['files'])and len(actual)==10112
for n,z in manifest['files'].items():
 p=v/n;assert p.is_file()and not p.is_symlink()and p.stat().st_size==z['bytes']and p.stat().st_mode&0o777==0o444;h=hashlib.sha256()
 with p.open('rb')as f:
  while True:
   b=f.read(1048576)
   if not b:break
   h.update(b)
 assert h.hexdigest()==z['sha256']
for n in('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):assert os.environ.get(n)=='1'
archive=raw(artifactdir/'observations.private.npz',134217728);mr=raw(artifactdir/'observations_manifest.private.json',4194304)
for b,z in((archive,proof['packet_pins']['archive']),(mr,proof['packet_pins']['manifest'])):assert len(b)==z['bytes']and hashlib.sha256(b).hexdigest()==z['sha256']
assert json.loads(raw(artifactdir/'completed.private.json',131072))['status']=='complete'
auditraw=raw(root/'eew-train115-receiver-observation-audit-output-v1/audit_result.private.json',16777216);assert {'bytes':len(auditraw),'sha256':hashlib.sha256(auditraw).hexdigest()}==proof['native_audit_pin'];audit=json.loads(auditraw);promotion=json.loads(raw(root/'eew-train115-receiver-observation-audit-output-v1/parent_agreement.private.json',131072));assert promotion['independent_all_observation_bytes_agree']and promotion['audit_result_pin']==proof['native_audit_pin']
put('live_controls_before_import.private.json',{'limits':limits,'manager':manager,'critical_runtime_files_verified':len(runtime['critical_runtime_files']),'prefix_regular_pins':10112,'source_members_verified':len(pins),'CUDA_hidden':True,'source_commit':proof['source_commit'],'native_semantic_audit_pass':True},131072)
sys.path.append('/home/ec2-user/Earthquake/.venv/lib/python3.9/site-packages');sys.path.insert(0,str(source));import packet_io,pilot,numpy as np,torch,scipy
assert torch.__version__=='2.8.0+cu128'and np.__version__=='2.0.2'and scipy.__version__=='1.13.1'and not torch.cuda.is_initialized();torch.set_num_interop_threads(1)
packet=packet_io.load(archive,mr,pins=proof['packet_pins'],processing_begin=begin);roles=pilot.validate(packet);assert len(roles['TRAIN'])==65 and len(roles['DEV'])==22
checkpoint_names=set();historyfiles={};historycounts={}
def checkpoint(seed,arm,state,stats):
 import io
 assert seed in(20261012,20261013)and arm in('B','F','H','T','C');name='checkpoint_%s_%s.private.npz'%(seed,arm);assert name not in checkpoint_names
 assert type(state)is dict and type(stats)is dict and set(stats)=={'initial_mean','initial_std','current_mean','current_std'}and all(type(v)is np.ndarray and v.dtype.kind=='f'and np.isfinite(v).all()for v in list(state.values())+list(stats.values()))
 assert not(set(state)&{'scaler_'+k for k in stats});arrays=state|{'scaler_'+k:v for k,v in stats.items()};stream=io.BytesIO();np.savez_compressed(stream,**arrays);put(name,stream.getvalue(),8388608);checkpoint_names.add(name)
def history(seed,arm,row):
 assert seed in(20261012,20261013)and arm in('B','F','H','T','C');name='history_%s_%s.private.jsonl'%(seed,arm);p=out/name
 new_history=name not in historyfiles
 if new_history:historyfiles[name]=p.open('xb');os.fchmod(historyfiles[name].fileno(),0o400);historycounts[name]=0
 assert type(row['update'])is int and row['update']==historycounts[name]+1 and row['update']<=300
 f=historyfiles[name];b=(json.dumps(row,sort_keys=True,allow_nan=False)+chr(10)).encode();assert len(b)<=4096;f.write(b);f.flush();os.fsync(f.fileno());historycounts[name]+=1;assert f.tell()<=1048576
 if new_history:
  fd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
try:
 result=pilot.run(packet,checkpoint,history,processing_begin=begin)
 # An explicitly oversized incomplete result cannot use the normal bounded export.
 if result.get('bounded_export',True)is False:
  marker={k:result[k]for k in('status','reason','exception_type','exception_reason','bounded_export','advance')if k in result};put('bounded_export_failure.private.json',marker,131072)
  for k,f in enumerate(result['fits']):put('retained_fit_%02d.private.json'%k,f,16777216)
  if 'comparisons'in result:put('retained_comparisons.private.json',result['comparisons'],16777216)
 else:put('result.private.json',result,16777216)
 put('completed.private.json',{'status':result['status'],'complete_fits':sum(f['status']=='complete'for f in result['fits']),'attempted_fits':len(result['fits']),'advance':result['advance'],'elapsed_s':time.monotonic()-begin,'CUDA_uninitialized':not torch.cuda.is_initialized(),'actual_invocations':1,'normal_bounded_export':result.get('bounded_export',True)},131072)
 print(json.dumps({'status':result['status'],'complete_fits':sum(f['status']=='complete'for f in result['fits']),'attempted_fits':len(result['fits']),'advance':result['advance'],'elapsed_s':time.monotonic()-begin}),flush=True)
except BaseException as error:
 put('parent_processing_failure.private.json',{'exception_type':type(error).__name__,'exception_reason':str(error)[:128],'checkpoint_names':sorted(checkpoint_names),'historycounts':historycounts,'no_automatic_replacement':True,'elapsed_s':time.monotonic()-begin},131072);raise
finally:
 for f in historyfiles.values():
  f.flush();os.fchmod(f.fileno(),0o400);os.fsync(f.fileno());f.close()
 fd=os.open(out,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)

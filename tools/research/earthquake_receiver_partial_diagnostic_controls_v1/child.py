from pathlib import Path
import os,sys,json,time,hashlib,subprocess,math
begin=time.monotonic();root=Path('/home/ec2-user');out=root/'eew-renewal115-partial-replay-output-v1';gate=json.loads((out/'parent_gate.private.json').read_bytes());unit=gate['unit'];g=Path('/sys/fs/cgroup')/Path('/proc/self/cgroup').read_text().strip().split('::',1)[1].lstrip('/');assert g.name==unit
assert {k:(g/k).read_text().strip()for k in('memory.max','memory.swap.max','pids.max')}=={'memory.max':'2147483648','memory.swap.max':'0','pids.max':'64'}
manager=subprocess.check_output(['systemctl','--user','show',unit,'-p','RuntimeMaxUSec','-p','TimeoutStopUSec','-p','KillMode','-p','ActiveState','-p','CPUWeight'],text=True,timeout=5);assert 'RuntimeMaxUSec=16min'in manager and'TimeoutStopUSec=5s'in manager and'KillMode=control-group'in manager and'ActiveState=active'in manager and'CPUWeight=10'in manager
assert os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='1'for k in('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'))
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
def bound(p,pin,cap=16777216):
 assert p.is_file()and not p.is_symlink()and p.stat().st_size<=cap and p.stat().st_mode&0o777==0o400
 with p.open('rb')as f:b=f.read(cap+1)
 assert len(b)<=cap and len(b)==pin['bytes']and hashlib.sha256(b).hexdigest()==pin['sha256'];return b
def sourcecheck(source):
 pins=json.loads((source/'parent_upload_manifest.private.json').read_bytes())
 for n,z in pins.items():assert '/'not in n;bound(source/n,z)
 return pins
source=root/'eew-train115-receiver-renewal-source-v2-frozen';audit_source=root/'eew-train115-receiver-renewal-score-audit-source-v2';sourcepins=sourcecheck(source);auditpins=sourcecheck(audit_source);assert sourcepins==gate['fit_proof']['source_pins']and auditpins==gate['audit_source_pins']
fitsdir=root/'eew-train115-receiver-renewal-fits-v2';result=json.loads(bound(fitsdir/'result.private.json',gate['input_pins']['result.private.json']));runtime=json.loads(bound(fitsdir/'runtime_pins.private.json',gate['input_pins']['runtime_pins.private.json']))
for name,pin in runtime['critical_runtime_files'].items():
 p=Path(name);assert p.is_file()and not p.is_symlink()and p.stat().st_size==pin['bytes']and oct(p.stat().st_mode&0o777)==pin['mode'];h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 assert h.hexdigest()==pin['sha256']
v=root/'eew-prefix-runtime-v2';m=json.loads((v/'runtime_manifest.private.json').read_bytes());assert hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':'),allow_nan=False,ensure_ascii=False).encode()).hexdigest()==gate['fit_proof']['prefix_runtime_canonical_sha256'];actual={str(p.relative_to(v))for p in(v/'venv').rglob('*')if p.is_file()and not p.is_symlink()};assert actual==set(m['files'])and len(actual)==10112
for n,z in m['files'].items():
 p=v/n;assert p.stat().st_size==z['bytes']and p.stat().st_mode&0o777==0o444;h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 assert h.hexdigest()==z['sha256']
a=root/'eew-train115-receiver-observations-output-v2';archive=bound(a/'observations.private.npz',gate['fit_proof']['packet_pins']['archive'],134217728);manifest=bound(a/'observations_manifest.private.json',gate['fit_proof']['packet_pins']['manifest'],4194304)
put('live_controls.private.json',dict(manager=manager,source_members=len(sourcepins),audit_members=len(auditpins),runtime_members=len(actual),input_pins_verified=True,no_optimizer=True))
sys.path.append('/home/ec2-user/Earthquake/.venv/lib/python3.9/site-packages');sys.path.insert(0,str(source));import numpy as np,torch,packet_io,pilot,numerical_core as core;from models import Net
assert torch.__version__=='2.8.0+cu128'and np.__version__=='2.0.2'and not torch.cuda.is_initialized();torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
packet=packet_io.load(archive,manifest,pins=gate['fit_proof']['packet_pins'],processing_begin=begin);roles=pilot.validate(packet);stats=pilot.scaler(packet,roles['TRAIN'])
sys.path.insert(0,str(audit_source));import auditor,packet_validation as pv
assert Path(auditor.__file__).parent==audit_source and Path(pv.__file__).parent==audit_source
indroles=pv.validate(packet);indstats=pv.scaler(packet,indroles);assert roles==indroles
assert all(np.allclose(stats[k],indstats[k],rtol=1e-6,atol=1e-8)for k in stats)
structural=auditor.audit(result,packet,processing_begin=begin,wall_seconds=900);assert structural['status']=='fail'and structural['advance']=={'pass_all':False,'checks':[]};put('complete_study_rejection.private.json',structural)
def validate_saved_records(packet,roles,fit):
 expected=[(i,h)for i in roles['DEV']for h in(1,3,5)];records=fit['predictions'];arm=fit['arm']
 assert type(arm)is str and arm in('B','F','H')and type(records)is list and len(expected)==66
 assert len(records)==66 if arm in('B','F')else 0<=len(records)<=66
 pairs=[]
 for record in records:
  assert type(record)is dict and type(record['ordinal'])is int and type(record['horizon'])is int
  i,h=record['ordinal'],record['horizon'];assert i in roles['DEV']and h in(1,3,5);pairs.append((i,h))
  row=packet['rows'][i];obs=row['horizons'][(1,3,5).index(h)];context=row['initial']['context']
  assert type(record['target'])in(int,float)and math.isfinite(record['target'])and record['target']==row['mw']
  assert type(record['group'])is int and record['group']==row['group']
  assert type(record['receiver'])is list and len(record['receiver'])==3 and all(type(v)in(int,float)and math.isfinite(v)for v in record['receiver'])and record['receiver']==[float(v)for v in context[9:12]]
  assert type(record['family'])is str and record['family']==('ENZ'if context[15]==1. else'12Z')
  assert type(record['rate'])is list and len(record['rate'])==2 and all(type(v)is int and v>0 for v in record['rate'])and math.gcd(*record['rate'])==1 and record['rate']==obs['rate']
 assert pairs==expected[:len(records)]
for fit in result['fits']:validate_saved_records(packet,roles,fit)
forward_count=0;maxdelta=0.;verified=[]
for fit in result['fits']:
 seed,arm=fit['seed'],fit['arm'];name='checkpoint_%s_%s.private.npz'%(seed,arm);b=bound(fitsdir/name,gate['input_pins'][name],8388608);net=Net(arm,fit['mref'])
 import io
 with np.load(io.BytesIO(b),allow_pickle=False)as packed:
  assert set(packed.files)==set(net.state_dict())|{'scaler_'+k for k in stats};state={}
  for k,t in net.state_dict().items():x=packed[k];assert x.dtype==np.float32 and x.shape==tuple(t.shape)and np.isfinite(x).all();state[k]=torch.from_numpy(x.copy())
  for k,v in stats.items():assert packed['scaler_'+k].tobytes()==v.tobytes()
 net.load_state_dict(state,strict=True);net.eval();historyname='history_%s_%s.private.jsonl'%(seed,arm);history=[json.loads(b)for b in bound(fitsdir/historyname,gate['input_pins'][historyname]).splitlines()];assert history==fit['history'];auditor.history(history,arm)
 with torch.no_grad():
  for record in fit['predictions']:
   assert time.monotonic()-begin<900;i,h=record['ordinal'],record['horizon'];assert i in roles['DEV']and h in(1,3,5)
   if arm in('B','F'):
    raw=net.current(*pilot.batch(packet,[i],stats,False,h,arm=='F'))[0].double().numpy();mixture=core.Mixture.from_raw(raw);fresh={'pi':mixture.weights.tolist(),'mu':mixture.means.tolist(),'sigma':mixture.sigmas.tolist()};stored=record['numerical'];assert auditor.close(stored,fresh,1e-8)
   else:
    w,a,c,mask=pilot.batch(packet,[i],stats,True);raw,z=net.initial(w,a,c,mask);stored=record['numerical'];fresh={'base_raw':raw[0].double().tolist(),'z':z[0].double().tolist(),'c':c[0].double().tolist(),'hazard':{k:getattr(net.hazards,k).double().tolist()for k in('alpha','beta','z_weights','c_weights','gamma','extra')}};assert all(fresh[k]==stored[k]for k in fresh)
   forward_count+=1
 verified.append({'seed':seed,'arm':arm,'history_updates':len(history),'checkpoint_forward_records':len(fit['predictions']),'scalers_exact':True})
put('checkpoint_forward.private.json',dict(records=forward_count,fits=verified,initial_context_train_only=True,CUDA_uninitialized=not torch.cuda.is_initialized(),no_refit=True,seconds=time.monotonic()-begin))
cache={};count=0;failures=[]
for fit in result['fits']:
 for record in fit['predictions']:
  assert time.monotonic()-begin<900;i,h=record['ordinal'],record['horizon'];row=packet['rows'][i];obs=row['horizons'][(1,3,5).index(h)]
  try:
   fresh,_=auditor.numerical_record(record['numerical'],fit['arm'],row,obs,indstats,row['mw'],fit['mref'],cache);assert all(auditor.close(record[k],value)for k,value in fresh.items());status='agree'
  except Exception as exc:
   failures.append({'arm':fit['arm'],'ordinal':i,'horizon':h,'type':type(exc).__name__,'reason':str(exc)[:128]});status='disagree'
  put('score_%03d.private.json'%count,{'index':count,'arm':fit['arm'],'ordinal':i,'horizon':h,'status':status,'seconds':time.monotonic()-begin});cache.clear();count+=1
  if failures:break
 if failures:break
put('diagnostic_result.private.json',dict(status='agree'if not failures else'disagree',retained_predictions=forward_count,independently_scored=count,failures=failures,incomplete_scientific_study=True,advance=False,seconds=time.monotonic()-begin,no_optimizer=True))
print(json.dumps(dict(checkpoint_records=forward_count,scored=count,failures=len(failures),seconds=time.monotonic()-begin,no_optimizer=True)),flush=True)
